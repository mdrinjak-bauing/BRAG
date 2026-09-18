"""Shared, dependency-light formatting for search hits.

Used by the MCP server, the thin MCP client and the bridge. Imports only
http_bridge.pdf_link (config + stdlib) — NO `mcp` and no model libraries — so
the thin client can format hits without pulling the heavy stack.
"""

import os

from brag import config
from brag.http_bridge import pdf_link
from brag.open_bridge import open_link

# Tables are never truncated; long text gets a preview. Default 2000 covers ~90 %
# of text chunks in full (p90 ≈ 1900 chars) — at the old 1000, half of all text
# chunks were cut mid-chunk and the model reasoned over half a chunk unknowingly.
# Override per deployment via env PREVIEW_CHARS.
try:
    PREVIEW_CHARS = int(os.environ.get("PREVIEW_CHARS", "2000"))
except ValueError:
    PREVIEW_CHARS = 2000

# MCP answers travel through a token-bounded channel. A long hit list at the full
# preview length can blow past that budget and get rejected outright — the mode
# built for recall ('review') would then return nothing at all. Budget the WHOLE
# list rather than shortening every preview uniformly: a short answer keeps the
# full PREVIEW_CHARS length, and only long lists shrink to fit. Override via env
# RESPONSE_BUDGET_CHARS.
try:
    RESPONSE_BUDGET_CHARS = int(os.environ.get("RESPONSE_BUDGET_CHARS", "45000"))
except ValueError:
    RESPONSE_BUDGET_CHARS = 45000

# Below this a preview stops being readable — better to show fewer hits than stubs.
MIN_PREVIEW_CHARS = 350


def preview_chars_for(n_hits: int) -> int:
    """Preview length per hit that keeps the whole list inside the response budget."""
    if n_hits <= 0:
        return PREVIEW_CHARS
    return max(MIN_PREVIEW_CHARS, min(PREVIEW_CHARS, RESPONSE_BUDGET_CHARS // n_hits))


def max_hits_for_budget() -> int:
    """How many hits still fit at the minimum readable preview length."""
    return max(1, RESPONSE_BUDGET_CHARS // MIN_PREVIEW_CHARS)


def with_topic_hint(fn):
    """Decorator: names the configured values of the corpus-wide `topic` field in the
    search tool's description — built at RUNTIME from config.TOPIC_VALUES, so an empty
    value simply yields no list and no install inherits another one's taxonomy.

    Filtering itself needs no code: `topic` is an ordinary payload field, reachable via
    meta_filter='topic=<value>'. Only the hint is configurable. Apply BELOW the MCP
    decorator, which reads `__doc__` when it registers the tool."""
    if config.TOPIC_VALUES:
        fn.__doc__ = ((fn.__doc__ or "").rstrip() + "\n\n    "
                      + "Der Korpus führt ein thematisches Feld `topic` (quer über alle "
                      + "doc_types) — filtern mit meta_filter='topic=<Wert>'. Werte: "
                      + ", ".join(config.TOPIC_VALUES) + ".\n    ")
    return fn


def with_passage_layout_note(fn):
    """Decorator: says which passage store THIS install writes to, and whether the
    saved passage is findable via `search` afterwards.

    One description covered two incompatible behaviours and promised indexing
    unconditionally. Under the chapter layout that promise is false: the passage is
    plain file storage, `search` never sees it — and the model, going by the
    description, tells the user their evidence is findable when it is not. The layout
    is fixed for the process, so the honest sentence can be chosen once, at import.

    Apply BELOW the MCP decorator, which reads `__doc__` when it registers the tool."""
    if config.PASSAGES_LAYOUT == "promotion":
        satz = (
            "Ablage dieser Installation: eine Datei je KAPITEL (`KapN_*.md`), "
            "Pflichtfeld ist `chapter`. Reine Datei-Ablage — die Passage wird NICHT "
            "indexiert und ist über `search` NICHT auffindbar; wiederfinden über "
            "`list_passages(chapter=…)`.")
    else:
        satz = (
            "Ablage dieser Installation: eine Datei je THEMA unter "
            "`WissensWIKI/Quellenbelege/<thema>.md`, Pflichtfeld ist `topic`. Die "
            "Passage wird zusätzlich für die semantische Suche indexiert, sodass ein "
            "späterer Chat sie über `search` wiederfindet — klar markiert als "
            "„gespeicherte Passage\", getrennt von Primärquellen.")
    fn.__doc__ = (fn.__doc__ or "").rstrip() + "\n\n    " + satz + "\n    "
    return fn


def parse_meta_filter(meta_filter: str) -> dict:
    """Parse a 'key=value, key2=value2' meta-filter string into a dict.

    Keys are normalised (lower-cased, spaces → underscores) to match the stored
    payload field names; blank keys/values are dropped. Shared by the MCP server
    (tools.search_text) and the thin MCP client so the two surfaces parse the
    user's filter identically."""
    meta: dict = {}
    for part in meta_filter.split(","):
        if "=" in part:
            key, _, value = part.partition("=")
            if key.strip() and value.strip():
                meta[key.strip().lower().replace(" ", "_")] = value.strip()
    return meta


def cite_reference(source: str, page) -> str:
    """"source, p. 12" — but never "source, p. PDF p. 12".

    A hit shows "PDF p. 61" when the printed page is unknown, and the caller
    passes back what it read. Prefixing that a second time mangles the reference
    in the very file footnotes are written from, so the prefix is applied only
    when the page does not already carry one. The caveat itself is kept: a
    passage saved off an unverified page must still say so.
    """
    seite = str(page or "").strip()
    if not seite:
        return source
    if seite.lower().lstrip().startswith(("p.", "pdf p.", "s.", "pdf s.")):
        return f"{source}, {seite}"
    return f"{source}, p. {seite}"


def page_span(start, end) -> str:
    """"46–48" when the chunk really runs across pages, "46" when it does not.

    A chunk may span a page break, and the hit is the only place the reading
    model learns where the passage ENDS: save_passage takes its page values from
    what the model read here, so a start-only citation quietly drops page_end
    from every piece of evidence filed afterwards.
    """
    if start in ("", None):
        return ""
    if end in ("", None):
        return str(start)
    try:
        return f"{start}–{end}" if int(end) > int(start) else str(start)
    except (TypeError, ValueError):
        # Roman or mixed labels ("xii", "A-3") have no arithmetic order — print a
        # range only when the two labels genuinely differ.
        return f"{start}–{end}" if str(end) != str(start) else str(start)


def cite_page(hit: dict, phys_page) -> tuple[str, str]:
    """What goes into the citation, and a note for the meta line.

    The citation NAMES which page count it means instead of printing a bare
    number that could be either:

      "p. xii"      the page printed on the paper — the PDF's own /PageLabels
      "p. 12"       the printed page, derived from the manual `page_offset`
      "PDF p. 12"   the 12th page of the file; the printed page is not known
      (nothing)     the source has no page numbers at all

    Naming the number rather than appending a warning to it is deliberate: a
    caveat after "p. 61" is dropped the moment someone copies the citation into
    a manuscript, while "PDF p. 61" travels with it.

    A chunk that spans a page break is cited as a RANGE ("p. 46–48"), in
    whichever page count the branch is citing — never a printed start with a
    physical end.

    The LINK always uses the physical page, whatever the citation says.
    """
    rel = str(hit.get("rel_path", "") or "")
    if rel and not rel.lower().endswith(".pdf"):
        # Docling reports no provenance for DOCX/PPTX, so _page_range falls back
        # to (1, 1) for every chunk of the file. Printing "p. 1" on all of them
        # would invent a page number that was never measured.
        return "", ""
    label = str(hit.get("page_label_start", "") or "")
    if label:
        return f" — p. {page_span(label, hit.get('page_label_end'))}", ""
    try:
        offset = int(hit.get("page_offset", 0) or 0)
    except (TypeError, ValueError):
        offset = 0  # free text from _meta.txt, never validated — ignore it
    if offset and isinstance(phys_page, int) and phys_page - offset >= 1:
        # Name the key, never echo its value: page_offset is not in
        # RESERVED_KEYS, so a ")" or ">" in it would break the markdown link.
        phys_end = hit.get("page_end")
        end = phys_end - offset if isinstance(phys_end, int) else None
        return (f" — p. {page_span(phys_page - offset, end)}",
                " | printed page via page_offset")
    if phys_page == "" or phys_page is None:
        return "", ""
    return f" — PDF p. {page_span(phys_page, hit.get('page_end'))}", ""


def format_hit(i: int, hit: dict, project: str = "",
                preview_chars: int | None = None) -> str:
    if hit.get("chunk_type") == "passage":
        topic = hit.get("topic", "") or hit.get("source_file", "").replace("passage:", "")
        frm = hit.get("from_source", "")
        frm_page = hit.get("from_page", "")
        origin = ""
        if frm:
            origin = f" · originally from {frm}"
            if frm_page and frm_page not in ("", "None"):
                origin += f", p. {frm_page}"
        header = f"### [{i}] 💡 Your saved passage — {topic}"
        meta = f"source: your notebook (WissensWIKI/Quellenbelege/){origin}"
        score = hit.get("rerank_score")
        if score is not None:
            meta += f" | rerank: {score:.3f}"
        return f"{header}\n{meta}\n\n{hit.get('text', '')}\n"
    src = hit.get("source_file", "?")
    # In an edited volume the file-level `author` is the EDITOR. A chunk that knows
    # its own contributor (`contribution_author`, set per contribution via _meta.txt)
    # must be cited under that name — otherwise a conference-volume passage is
    # attributed to the wrong person, in the very line the citation is copied from.
    author = hit.get("contribution_author") or hit.get("author", "")
    year = hit.get("year", "")
    phys_page = hit.get("page_start", "")  # physical PDF page — used for the link
    seite, seiten_notiz = cite_page(hit, phys_page)
    if config.OPEN_BRIDGE_ENABLED:
        # Click bridge on: the hit links to the local viewer instead of the browser.
        # A stored physical page goes straight through (no book->physical guessing
        # at request time); otherwise the printed page is resolved via /PageLabels.
        pdf_page = hit.get("pdf_page_start")
        link = (open_link(src, pdf_page, physical=True) if isinstance(pdf_page, int)
                else open_link(src, phys_page))
    else:
        link = pdf_link(hit.get("rel_path", ""), phys_page, project)
    cite = f"{author} ({year})" if author and author != "Unknown" else src
    header = f"### [{i}] [{cite}{seite}](<{link}>)"
    meta = (
        f"source: `{src}` | type: {hit.get('doc_type', '')}/{hit.get('chunk_type', '')}"
        f" | chapter: {hit.get('chapter', '') or '—'}{seiten_notiz}"
    )
    score = hit.get("rerank_score")
    if score is not None:
        meta += f" | rerank: {score:.3f}"
    # Also expose the raw deep-link on its own line: clients that don't render a
    # Markdown link (e.g. LM Studio) still show a clickable/copy-paste URL to the
    # exact page; Claude Desktop just renders it as a second link to the same page.
    if hit.get("rel_path"):
        meta += f"\n🔗 {link}"
    text = hit.get("text", "")
    limit = PREVIEW_CHARS if preview_chars is None else preview_chars
    if hit.get("chunk_type") != "table" and len(text) > limit:
        text = text[:limit] + " …"
    # The generated anchoring context (which chapter/argument this chunk sits in)
    # already powers the embeddings — show it to the reading model too. Without
    # this line the model never sees it, and chunks that open with an anaphor
    # ("Diese Annahme …") read as if context were missing. That WAS the measured
    # complaint the context sentence was generated to answer.
    ctx = (hit.get("context") or "").strip()
    if ctx:
        return f"{header}\n{meta}\n\n> Kontext: {ctx}\n\n{text}\n"
    return f"{header}\n{meta}\n\n{text}\n"
