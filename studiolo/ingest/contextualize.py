"""Contextual retrieval: every chunk gets 1-2 sentences of LLM-generated
context before embedding (Anthropic, 2024 — reduces retrieval failures
substantially).

Design notes ported from the originating production system:
- hierarchical context (table of contents + current chapter) instead of the
  whole document — better grounding at lower token cost
- chunks are processed in batches of CR_BATCH_SIZE per LLM call
- figure-caption chunks get an HONEST prompt: the model has not seen the
  image, so it must locate the figure in its chapter, never describe content
  (otherwise hallucinated descriptions poison the embeddings permanently)
- a failed LLM call leaves the context empty — never blocks the ingest
"""

import re

from studiolo import config
from studiolo.ingest.extract import Chunk
from studiolo.llm_backends import get_llm

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


def contextualize(chunks: list[Chunk], full_markdown: str) -> list[Chunk]:
    if not config.CR_ENABLED or not full_markdown:
        return chunks

    llm = get_llm()
    toc = _toc(full_markdown)
    text_like = [(i, c) for i, c in enumerate(chunks) if c.chunk_type != "figure"]
    figures = [(i, c) for i, c in enumerate(chunks) if c.chunk_type == "figure"]
    contexts = [""] * len(chunks)
    done, total = 0, len(chunks)

    for group, figures_only in ((text_like, False), (figures, True)):
        for start in range(0, len(group), config.CR_BATCH_SIZE):
            batch = group[start : start + config.CR_BATCH_SIZE]
            prompt = _build_prompt(
                _doc_context(full_markdown, toc, batch[0][1].chapter),
                batch, figures_only,
            )
            answer = llm.chat(prompt, max_tokens=200 * len(batch) + 100) or ""
            parsed = dict(CONTEXT_TAG.findall(answer))
            missing = 0
            for local_i, (idx, _) in enumerate(batch):
                ctx = parsed.get(str(local_i), "").strip()
                contexts[idx] = ctx
                missing += 0 if ctx else 1
                done += 1
            if missing:
                print(f"  [CR] {missing}/{len(batch)} chunks without context tag")
            if done % 25 == 0 or done == total:
                print(f"  context {done}/{total} done")

    for chunk, ctx in zip(chunks, contexts):
        chunk.context = ctx
    generated = sum(1 for c in chunks if c.context)
    print(f"  {generated}/{total} chunks contextualized")
    return chunks
