"""Shared, dependency-light formatting for search hits.

Used by the MCP server, the thin MCP client and the bridge. Imports only
http_bridge.pdf_link (config + stdlib) — NO `mcp` and no model libraries — so
the thin client can format hits without pulling the heavy stack.
"""

from brag.http_bridge import pdf_link

PREVIEW_CHARS = 1000  # tables are never truncated; long text gets a preview


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
        meta = f"source: your notebook (passages/){origin}"
        score = hit.get("rerank_score")
        if score is not None:
            meta += f" | rerank: {score:.3f}"
        return f"{header}\n{meta}\n\n{hit.get('text', '')}\n"
    src = hit.get("source_file", "?")
    author, year = hit.get("author", ""), hit.get("year", "")
    phys_page = hit.get("page_start", "")  # physical PDF page — used for the link
    # If a document's printed page numbers differ from the PDF's physical page
    # count (a book with front matter, a journal offprint), the user sets
    # `page_offset` in a _meta.txt: printed page = physical page − offset. The
    # CITATION then shows the printed/book page, while the LINK still jumps to
    # the physical PDF page so the viewer lands on the right one.
    try:
        offset = int(hit.get("page_offset", 0) or 0)
    except (TypeError, ValueError):
        offset = 0
    book_page = phys_page
    if isinstance(phys_page, int) and offset and phys_page - offset >= 1:
        book_page = phys_page - offset  # printed page; guard against a bad offset
    link = pdf_link(hit.get("rel_path", ""), phys_page, project)
    cite = f"{author} ({year})" if author and author != "Unknown" else src
    header = f"### [{i}] [{cite} — p. {book_page}](<{link}>)"
    meta = (
        f"source: `{src}` | type: {hit.get('doc_type', '')}/{hit.get('chunk_type', '')}"
        f" | chapter: {hit.get('chapter', '') or '—'}"
    )
    score = hit.get("rerank_score")
    if score is not None:
        meta += f" | rerank: {score:.3f}"
    text = hit.get("text", "")
    if hit.get("chunk_type") != "table" and len(text) > PREVIEW_CHARS:
        text = text[:PREVIEW_CHARS] + " …"
    return f"{header}\n{meta}\n\n{text}\n"
