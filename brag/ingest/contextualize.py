"""Contextual retrieval: every chunk gets 1-2 sentences of LLM-generated
context before embedding (Anthropic, 2024 — reduces retrieval failures
substantially).

Design notes (validated over earlier iterations):
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

from brag import config
from brag.ingest.extract import Chunk
from brag.llm_backends import get_llm

CONTEXT_TAG = re.compile(r'<context id="(\d+)">(.*?)</context>', re.DOTALL)


def _toc(full_markdown: str) -> str:
    lines = [l.strip() for l in full_markdown.splitlines() if l.strip().startswith("#")]
    return "\n".join(lines)[: config.TOC_MAX_CHARS]


def _norm_heading(s: str) -> str:
    r"""Normalize a heading for matching: drop markdown backslash-escapes
    (Docling emits e.g. '1\. Introduction'), collapse internal whitespace,
    lowercase. Only representation-level noise is removed — this never changes
    WHICH logical heading a string denotes — so exact equality on the normalized
    form stays safe against matching the wrong chapter."""
    s = re.sub(r"\\(.)", r"\1", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _strip_section_number(s: str) -> str:
    """Drop a leading numeric section label like '2.1.1', '1.3' or '4.' so a
    Docling-captured heading ('2.1.1 Projektleitung') still matches a markdown
    heading that renders the number differently. ONLY a digits-and-dots prefix is
    stripped — never a leading word — so 'Chapter 4' or 'Tabellenverzeichnis'
    are untouched."""
    return re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", s).strip()


def _chapter_text(full_markdown: str, chapter: str) -> str:
    if not chapter:
        return ""
    # Collect every markdown heading once: (line index, level, normalized text).
    lines = full_markdown.splitlines()
    headings = [
        (i, len(s) - len(s.lstrip("#")), _norm_heading(s.lstrip("#")))
        for i, line in enumerate(lines)
        for s in (line.strip(),)
        if s.startswith("#")
    ]
    target = _norm_heading(chapter)
    # 1) EXACT normalized match — safest; can never pick the wrong section.
    matches = [h for h in headings if h[2] == target]
    # 2) Guarded number-stripped fallback: tolerate a numeric-prefix rendering
    #    difference ('2.1.1 Projektleitung' vs 'Projektleitung'), but ACCEPT it
    #    ONLY when exactly one heading matches the number-stripped target. A
    #    repeated bare title yields >1 candidate and is refused, never guessed —
    #    this preserves the no-wrong-chapter guarantee.
    if not matches:
        target_ns = _strip_section_number(target)
        if target_ns:
            cand = [h for h in headings if _strip_section_number(h[2]) == target_ns]
            if len(cand) == 1:
                matches = cand
    if not matches:
        return ""
    # Capture from the matched heading down to the next heading of equal/higher
    # level (i.e. the body of this section).
    start_idx, level, _ = matches[0]
    result = [lines[start_idx]]
    for line in lines[start_idx + 1:]:
        s = line.strip()
        if s.startswith("#") and (len(s) - len(s.lstrip("#"))) <= level:
            break
        result.append(line)
    return "\n".join(result)[: config.CHAPTER_CONTEXT_CHARS]


def _doc_context(full_markdown: str, toc: str, chapter: str, section: str = "") -> str:
    # Try the DEEPEST heading first: a chunk under '2.1.1 Projektleitung' carries
    # that in `section`, while only the level<=1 `chapter` used to be tried — so
    # deep headings could never match. Fall back to chapter, then whole-document.
    chapter_text, matched = "", ""
    for heading in (section, chapter):
        if heading:
            chapter_text = _chapter_text(full_markdown, heading)
            if chapter_text:
                matched = heading
                break
    if chapter_text:
        return (
            f"<table_of_contents>\n{toc}\n</table_of_contents>\n\n"
            f'<current_chapter title="{matched}">\n{chapter_text}\n</current_chapter>'
        )
    if chapter or section:
        # A heading was named but none matched — the chunk now gets the weaker
        # whole-document grounding. Make that visible instead of silent.
        print(f"  [contextualize] chapter heading not found, using "
              f"whole-document context: {(section or chapter)!r}")
    return f"<document>\n{full_markdown[: config.CONTEXT_DOC_CHARS]}\n</document>"


def _fit_doc_context(doc_context: str, fixed_chars: int) -> str:
    """Trim the grounding-context block so the WHOLE prompt stays within
    config.CR_PROMPT_MAX_CHARS. ``fixed_chars`` is the length of everything else
    in the prompt (chunk texts, task, format, language line). This is the single
    guarantee that the request fits the model's context window — it bounds BOTH
    the whole-document fallback AND the chapter-found path, regardless of how the
    individual *_CHARS caps are set. The outermost wrapper tag of a truncated
    block is re-closed so the XML the model sees is never left dangling."""
    budget = config.CR_PROMPT_MAX_CHARS - fixed_chars
    if len(doc_context) <= budget:
        return doc_context
    if budget <= 0:
        # The fixed parts alone already fill the budget (e.g. very large chunk
        # texts) — drop grounding entirely rather than emit a request that cannot
        # fit. The chunk is still contextualized from its own text; weaker
        # grounding beats an HTTP 400 that yields zero context.
        return ""
    head = doc_context[:budget].rstrip()
    # Re-close the outermost wrapper tag if truncation cut it off, so the model
    # receives well-formed context instead of a half-open element.
    m = re.match(r"\s*<([a-z_]+)", doc_context)
    if m:
        close = f"</{m.group(1)}>"
        if close not in head:
            head = head[: max(0, budget - len(close) - 1)].rstrip() + f"\n{close}"
    return head


def _build_prompt(doc_context: str, batch: list[tuple[int, Chunk]], figures_only: bool) -> str:
    # Bound each chunk's text so the chunk payload + scaffolding always leaves
    # room for the grounding block within CR_PROMPT_MAX_CHARS — otherwise one
    # oversized chunk (e.g. an 8000-char table) blows a local model's context
    # window even after grounding is dropped. The FULL chunk text is still stored
    # and embedded; this only bounds what the LLM SEES to write the 1-2 sentence
    # context. Cloud's large budget leaves normal and table chunks untouched.
    n = max(1, len(batch))
    per_chunk = max(400, (config.CR_PROMPT_MAX_CHARS - 1500) // n)
    chunks_xml = "\n".join(
        f'<chunk id="{i}">\n{c.text[:per_chunk]}\n</chunk>'
        for i, (_, c) in enumerate(batch)
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
    # Assemble the fixed parts first, then trim ONLY the grounding-context block
    # to whatever budget remains, so the total prompt can never exceed
    # config.CR_PROMPT_MAX_CHARS (the guarantee that the request fits a local
    # model's context window — on BOTH the chapter-found and whole-doc paths).
    tail = (
        f"\n\n{task}\n\n"
        f"Respond in {config.ANSWER_LANGUAGE}.\n\n{chunks_xml}\n\n"
        f"Answer ONLY in this exact format, nothing else:\n{fmt}"
    )
    return f"{_fit_doc_context(doc_context, len(tail))}{tail}"


def _vision_prompt(doc_context: str) -> str:
    task = (
        "You are shown a figure (image) from an academic document, together "
        "with its surrounding context. In 1-3 concise sentences, describe what "
        "the figure actually shows for semantic search: the figure type (e.g. "
        "diagram, photo, chart), its main elements, and any axes, labels or "
        "relationships that are clearly legible. Do not guess illegible text "
        "and never invent data or numbers."
    )
    tail = (
        f"\n\n{task}\n\n"
        f"Respond in {config.ANSWER_LANGUAGE}. Give the description only, no preamble."
    )
    # Bound the vision prompt the same way. Image tokens are NOT counted here —
    # only a local model that accepts images reaches this path, and one image
    # plus this (already small) trimmed text fits a vision model's window.
    return f"{_fit_doc_context(doc_context, len(tail))}{tail}"


# After this many CONSECUTIVE failing LLM calls within a single document, stop
# calling the LLM for the rest of that document and fall back to raw-text
# embedding. Mirrors the vision consecutive-failure latch: a broken, missing or
# over-context LLM then costs seconds (a couple of failed batches), not many
# minutes (every batch failing), and ingest still COMPLETES with raw text.
LLM_FAIL_LATCH_THRESHOLD = 2


class _LLMHealth:
    """Per-document latch shared across the text and figure-caption passes, so
    consecutive failures in EITHER stop further LLM calls for the whole document.
    Starts healthy; latches off after LLM_FAIL_LATCH_THRESHOLD consecutive
    failures; any success resets the counter."""

    def __init__(self):
        self.alive = True
        self._consecutive_fail = 0

    def record_success(self):
        self._consecutive_fail = 0

    def record_failure(self):
        self._consecutive_fail += 1
        if self._consecutive_fail >= LLM_FAIL_LATCH_THRESHOLD:
            self.alive = False
            print(f"  [contextualize] LLM failed {self._consecutive_fail}x in a "
                  "row — disabling contextualization for the rest of this "
                  "document; remaining chunks embed as raw text")


def _contextualize_batched(llm, group, full_markdown, toc, contexts, figures_only,
                           health):
    """Original batched contextual-retrieval path (text chunks, and figures
    that have no usable image / when vision is off)."""
    for start in range(0, len(group), config.CR_BATCH_SIZE):
        if not health.alive:
            # Latched off earlier in this document — skip the (futile) call and
            # leave these chunks' context empty so they embed as raw text.
            return
        batch = group[start : start + config.CR_BATCH_SIZE]
        prompt = _build_prompt(
            _doc_context(full_markdown, toc, batch[0][1].chapter, batch[0][1].section),
            batch, figures_only,
        )
        answer = llm.chat(prompt, max_tokens=200 * len(batch) + 100)
        if not answer:
            # The LLM call failed (None / empty) — count it toward the latch so a
            # persistently broken LLM stops wasting time on every batch.
            health.record_failure()
            continue
        parsed = dict(CONTEXT_TAG.findall(answer))
        if not parsed:
            # Reachable but unparseable output (wrong format / off-context) is
            # still a failure for these chunks; treat it like a failed call.
            health.record_failure()
            continue
        health.record_success()
        for local_i, (idx, _) in enumerate(batch):
            ctx = parsed.get(str(local_i), "").strip()
            if ctx:
                contexts[idx] = ctx


def _contextualize_figures_vision(llm, figures, full_markdown, toc, contexts, health):
    """Send each figure's image to the multimodal LLM for an honest
    description. Returns the figures that could NOT be described this way (no
    image, or the model is not multimodal) for the caption-only fallback.

    Vision keeps its OWN latch (``vision_alive``): two empty replies most likely
    mean a non-multimodal model, so the figures should fall through to the
    caption-only TEXT path rather than be abandoned. But each failure ALSO feeds
    the shared document-level ``health`` latch, and each success resets it — so a
    wholesale broken/over-context LLM (failing text AND vision) stops the
    caption-only fallback too, instead of failing every remaining batch."""
    leftover, described = [], 0
    vision_alive, consecutive_fail = True, 0
    for idx, chunk in figures:
        if vision_alive and health.alive and chunk.image_b64:
            prompt = _vision_prompt(
                _doc_context(full_markdown, toc, chunk.chapter, chunk.section))
            desc = llm.chat(prompt, max_tokens=220, images=[chunk.image_b64])
            if desc and desc.strip():
                contexts[idx] = desc.strip()
                described += 1
                consecutive_fail = 0
                health.record_success()
                continue
            # Don't disable vision on a single transient empty response; only
            # latch off after two in a row (then assume a non-multimodal model)
            # so one hiccup can't cost a whole document's figure descriptions.
            consecutive_fail += 1
            health.record_failure()
            if consecutive_fail >= 2:
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
    # Per-document failure latch shared across the text and figure passes.
    health = _LLMHealth()

    _contextualize_batched(llm, text_like, full_markdown, toc, contexts, False, health)

    if figures:
        vision_on = config.VISION_ENABLED and getattr(llm, "vision_capable", False)
        leftover = (
            _contextualize_figures_vision(
                llm, figures, full_markdown, toc, contexts, health)
            if vision_on else figures
        )
        if leftover:
            _contextualize_batched(
                llm, leftover, full_markdown, toc, contexts, True, health)
        # image bytes are no longer needed (never stored in Qdrant)
        for _, chunk in figures:
            chunk.image_b64 = ""

    for chunk, ctx in zip(chunks, contexts):
        chunk.context = ctx
    generated = sum(1 for c in chunks if c.context)
    missing = len(chunks) - generated
    print(f"  {generated}/{len(chunks)} chunks contextualized")
    if missing:
        # Surface the silent degradation: these chunks are still embedded as raw
        # text (the intended fallback), but without this line a failed anchoring-
        # sentence LLM call leaves no trace once the run scrolls past. The count
        # is also persisted to the ingest log by the caller.
        src = chunks[0].source_file if chunks else "?"
        print(f"  WARNING: {missing}/{len(chunks)} chunks have NO context "
              f"(embedded as raw text) for {src} — contextualization may have failed")
    return chunks
