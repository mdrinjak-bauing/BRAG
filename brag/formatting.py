"""Shared, dependency-light formatting for search hits.

Used by the MCP server, the thin MCP client and the bridge. Imports only
http_bridge.pdf_link (config + stdlib) — NO `mcp` and no model libraries — so
the thin client can format hits without pulling the heavy stack.
"""

from brag.http_bridge import pdf_link

PREVIEW_CHARS = 1000  # tables are never truncated; long text gets a preview


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
        return f" — p. {label}", ""
    try:
        offset = int(hit.get("page_offset", 0) or 0)
    except (TypeError, ValueError):
        offset = 0  # free text from _meta.txt, never validated — ignore it
    if offset and isinstance(phys_page, int) and phys_page - offset >= 1:
        # Name the key, never echo its value: page_offset is not in
        # RESERVED_KEYS, so a ")" or ">" in it would break the markdown link.
        return f" — p. {phys_page - offset}", " | printed page via page_offset"
    if phys_page == "" or phys_page is None:
        return "", ""
    return f" — PDF p. {phys_page}", ""


def format_hit(i: int, hit: dict, project: str = "") -> str:
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
    author, year = hit.get("author", ""), hit.get("year", "")
    phys_page = hit.get("page_start", "")  # physical PDF page — used for the link
    seite, seiten_notiz = cite_page(hit, phys_page)
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
    if hit.get("chunk_type") != "table" and len(text) > PREVIEW_CHARS:
        text = text[:PREVIEW_CHARS] + " …"
    return f"{header}\n{meta}\n\n{text}\n"
