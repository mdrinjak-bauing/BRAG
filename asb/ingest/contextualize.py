"""Contextual retrieval: every chunk gets 1-2 sentences of LLM-generated
context before embedding (Anthropic, 2024 — reduces retrieval failures
substantially).

Design notes ported from the originating production system:
- hierarchical context (table of contents + current chapter) instead of the
  whole document — better grounding at lower token cost
- chunks are processed in batches of CR_BATCH_SIZE per LLM call
- figures: when VISION_ENABLED and the LLM is multimodal, the figure's image
  is sent to the model for an honest description (embedded so figures become
  findable by content). Without a usable image or a multimodal model, figures
  fall back to the HONEST caption-only prompt: the model has not seen the
  image, so it only locates the figure in its chapter and never describes
  content (otherwise hallucinated descriptions poison the embeddings)
- a failed LLM call leaves the context empty — never blocks the ingest
"""

import re

from asb import config
from asb.ingest.extract import Chunk
from asb.llm_backends import get_llm

CONTEXT_TAG = re.compile(r'<context id="(\d+)">(.*?)</context>', re.DOTALL)


def _toc(full_markdown: str) -> str:
    lines = [l.strip() for l in full_markdown.splitlines() if l.strip().startswith("#")]
    return "\n".join(lines)[: config.TOC_MAX_CHARS]


def _chapter_text(full_markdown: str, chapter: str) -> str:
    if not chapter:
        return ""
    lines = full_markdown.splitlines()
    capturing, level, result = False, None, []
    for line in lines:
        s = line.strip()
        if not capturing:
            if s.startswith("#") and chapter.lower() in s.lower():
                capturing = True
                level = len(s) - len(s.lstrip("#"))
                result.append(line)
        else:
            if s.startswith("#") and (len(s) - len(s.lstrip("#"))) <= level:
                break
            result.append(line)
    return "\n".join(result)[: config.CHAPTER_CONTEXT_CHARS]


def _doc_context(full_markdown: str, toc: str, chapter: str) -> str:
    chapter_text = _chapter_text(full_markdown, chapter)
    if chapter_text:
        return (
            f"<table_of_contents>\n{toc}\n</table_of_contents>\n\n"
            f'<current_chapter title="{chapter}">\n{chapter_text}\n</current_chapter>'
        )
    return f"<document>\n{full_markdown[: config.CONTEXT_DOC_CHARS]}\n</document>"


def _build_prompt(doc_context: str, batch: list[tuple[int, Chunk]], figures_only: bool) -> str:
    chunks_xml = "\n".join(
        f'<chunk id="{i}">\n{c.text}\n</chunk>' for i, (_, c) in enumerate(batch)
    )
    if figures_only:
        task = (
            "You are given ONLY the captions of figures — the images themselves "
            "are not available to you.\n"
            "For each chunk, write ONE sentence locating the figure within the "
            "chapter context (e.g. 'Figure in chapter 4 illustrating the workflow').\n"
            "IMPORTANT: Do NOT describe what the figure shows — you cannot know. "
            "Do not invent anything."
        )
    else:
        task = (
            "For each of the following chunks from an academic document, write "
            "1-2 concise sentences of anchoring context for semantic search. "
            "Mention explicitly, if present: section/norm references, key "
            "terminology, and quantitative statements with their reference "
            "value. If the chunk contains none of these, write 'General "
            "background text from chapter X.' Never invent anything — if a "
            "term is not in the chunk, do not mention it."
        )
    fmt = "\n".join(f'<context id="{i}">...</context>' for i in range(len(batch)))
    return (
        f"{doc_context}\n\n{task}\n\n"
        f"Respond in {config.ANSWER_LANGUAGE}.\n\n{chunks_xml}\n\n"
        f"Answer ONLY in this exact format, nothing else:\n{fmt}"
    )


def _vision_prompt(doc_context: str) -> str:
    task = (
        "You are shown a figure (image) from an academic document, together "
        "with its surrounding context. In 1-3 concise sentences, describe what "
        "the figure actually shows for semantic search: the figure type (e.g. "
        "diagram, photo, chart), its main elements, and any axes, labels or "
        "relationships that are clearly legible. Do not guess illegible text "
        "and never invent data or numbers."
    )
    return (
        f"{doc_context}\n\n{task}\n\n"
        f"Respond in {config.ANSWER_LANGUAGE}. Give the description only, no preamble."
    )


def _contextualize_batched(llm, group, full_markdown, toc, contexts, figures_only):
    """Original batched contextual-retrieval path (text chunks, and figures
    that have no usable image / when vision is off)."""
    for start in range(0, len(group), config.CR_BATCH_SIZE):
        batch = group[start : start + config.CR_BATCH_SIZE]
        prompt = _build_prompt(
            _doc_context(full_markdown, toc, batch[0][1].chapter),
            batch, figures_only,
        )
        answer = llm.chat(prompt, max_tokens=200 * len(batch) + 100) or ""
        parsed = dict(CONTEXT_TAG.findall(answer))
        for local_i, (idx, _) in enumerate(batch):
            ctx = parsed.get(str(local_i), "").strip()
            if ctx:
                contexts[idx] = ctx


def _contextualize_figures_vision(llm, figures, full_markdown, toc, contexts):
    """Send each figure's image to the multimodal LLM for an honest
    description. Returns the figures that could NOT be described this way (no
    image, or the model is not multimodal) for the caption-only fallback."""
    leftover, described, vision_alive = [], 0, True
    for idx, chunk in figures:
        if vision_alive and chunk.image_b64:
            prompt = _vision_prompt(_doc_context(full_markdown, toc, chunk.chapter))
            desc = llm.chat(prompt, max_tokens=220, images=[chunk.image_b64])
            if desc and desc.strip():
                contexts[idx] = desc.strip()
                described += 1
                continue
            # First failure with an image present: assume the model cannot see
            # images; stop trying and fall back for all remaining figures.
            vision_alive = False
            print("  [vision] figure description unavailable — falling back to "
                  "caption-only context for remaining figures")
        leftover.append((idx, chunk))
    if described:
        print(f"  [vision] described {described} figure(s)")
    return leftover


def contextualize(chunks: list[Chunk], full_markdown: str) -> list[Chunk]:
    if not config.CR_ENABLED or not full_markdown:
        return chunks

    llm = get_llm()
    toc = _toc(full_markdown)
    text_like = [(i, c) for i, c in enumerate(chunks) if c.chunk_type != "figure"]
    figures = [(i, c) for i, c in enumerate(chunks) if c.chunk_type == "figure"]
    contexts = [""] * len(chunks)

    _contextualize_batched(llm, text_like, full_markdown, toc, contexts, False)

    if figures:
        vision_on = config.VISION_ENABLED and getattr(llm, "vision_capable", False)
        leftover = (
            _contextualize_figures_vision(llm, figures, full_markdown, toc, contexts)
            if vision_on else figures
        )
        if leftover:
            _contextualize_batched(llm, leftover, full_markdown, toc, contexts, True)
        # image bytes are no longer needed (never stored in Qdrant)
        for _, chunk in figures:
            chunk.image_b64 = ""

    for chunk, ctx in zip(chunks, contexts):
        chunk.context = ctx
    generated = sum(1 for c in chunks if c.context)
    print(f"  {generated}/{len(chunks)} chunks contextualized")
    return chunks
