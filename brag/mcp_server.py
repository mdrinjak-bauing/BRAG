"""MCP server for Claude Desktop (stdio transport) — single-project entry.

Claude Desktop starts this via `docker exec -i brag-app python -m brag.mcp_server`
inside the running container — the setup wizard writes that config entry. The
tool LOGIC lives in brag/tools.py (shared with the HTTP-bridge dispatcher that a
thin per-project MCP client calls); this module is just the FastMCP surface —
the tool names, signatures and docstrings Claude sees.

Tools: search, list_sources, inspect_chunks, remove_source, rename_source,
save_passage, list_passages, list_notebook, read_note, write_note, save_report.
"""

from mcp.server.fastmcp import FastMCP

from brag import config, tools

mcp = FastMCP("brag")


@mcp.tool()
def search(query: str, top_k: int = 15, doc_type: str = "",
           chunk_type: str = "", year_min: int = 0, year_max: int = 0,
           source_file: str = "", meta_filter: str = "",
           reranking: bool | None = None) -> str:
    """Hybrid search (semantic + keyword) over the document corpus.

    Try multiple phrasings (synonyms, English/native-language variants).
    Use chunk_type='table' for numbers/statistics, 'figure' for diagrams.
    meta_filter restricts hits by the user's own metadata fields (defined
    in _meta.txt files in the knowledge store), format 'key=value' with commas for
    several, e.g. meta_filter='project=School Center' or
    'course=Construction Management, semester=WS25'. If the user names a
    project/course/client context, ALWAYS set this filter — otherwise hits
    from unrelated projects mix into the results.
    Every hit header is a clickable link that opens the PDF at the right
    page — ALWAYS carry that link into your answer when citing the source.
    """
    return tools.search_text(
        query, top_k=top_k, doc_type=doc_type, chunk_type=chunk_type,
        year_min=year_min, year_max=year_max, source_file=source_file,
        meta_filter=meta_filter, reranking=reranking)


@mcp.tool()
def list_sources(doc_type: str = "") -> str:
    """List all indexed documents with chunk counts, grouped by type."""
    return tools.list_sources(doc_type=doc_type)


@mcp.tool()
def inspect_chunks(source_file: str, page: int = 0, limit: int = 10) -> str:
    """Show what is actually stored in the index for a source (debugging:
    'why doesn't the search find X?'). Optionally filter by page number."""
    return tools.inspect_chunks(source_file, page=page, limit=limit)


@mcp.tool()
def remove_source(source_file: str) -> str:
    """Remove a document from the SEARCH INDEX — use it to drop a wrong,
    duplicate or outdated source the user no longer wants in results.

    Safe and reversible: the file is NOT deleted, it is moved into an
    _inbox/ (a staging area the watcher ignores) so it can't be re-indexed, and
    its chunks + literature note are removed from the index. `source_file` is the
    key shown by list_sources (e.g. 'projects/Bericht'). Call once per source."""
    return tools.remove_source(source_file)


@mcp.tool()
def rename_source(source_file: str, new_name: str) -> str:
    """Rename / re-file an indexed document and update its index metadata IN
    PLACE (no re-embedding). Renames/moves the FILE in your project folder;
    `new_name` may include a relative folder to also move it (e.g.
    'projects/School_Center/Final_Report'). The original file suffix is kept if
    you omit it. `source_file` is the current key from list_sources."""
    return tools.rename_source(source_file, new_name)


@mcp.tool()
def save_passage(topic: str, text: str, source: str, page: str = "",
                 note: str = "") -> str:
    """Save a quotable passage under a topic (e.g. a chapter or theme).

    Builds your evidence base in WissensWIKI/Passagen/<topic>.md AND indexes
    the passage for semantic search, so a later chat (even with a different
    provider) finds it again via `search` — it appears as a clearly marked
    "saved passage", distinct from primary sources. Use this to persist the
    findings, decisions and definitions of a working session so the knowledge
    lives in the folder, not in one chat's history."""
    return tools.save_passage(topic, text, source, page=page, note=note)


@mcp.tool()
def list_passages(topic: str = "") -> str:
    """List saved passages — for one topic, or an overview of all topics."""
    return tools.list_passages(topic=topic)


# ── Notebook (WissensWIKI/) — your own thinking, NOT search-indexed ────────────
# A second "connection" without a second MCP server: instead of a separate
# filesystem MCP (extra dependency + its own Claude-config entry), the notebook
# read/write tools live in THIS server. The corpus stays read-only via search();
# the search index is never touched by these. The notebook is WissensWIKI/ minus
# the indexed Passagen/ — any .md files and subfolders you like.
@mcp.tool()
def list_notebook() -> str:
    """List your NOTEBOOK — your own .md notes and subfolders in WissensWIKI/.
    Deliberately NOT search-indexed (use search() for the corpus, list_passages()
    for verified passages). Open one with read_note, create or update with
    write_note."""
    return tools.list_notebook()


@mcp.tool()
def read_note(path: str) -> str:
    """Read a NOTEBOOK markdown file. `path` is relative to WissensWIKI/, e.g.
    'process-maturity.md' or 'Notizen/Mueller_2023.md'. Only the notebook
    (WissensWIKI/, excluding the indexed Passagen/) is reachable here — the corpus
    and the search index are not (use search() for those)."""
    return tools.read_note(path)


@mcp.tool()
def write_note(path: str, content: str) -> str:
    """Create a NOTEBOOK note, or APPEND a dated section to an existing one — it
    never silently overwrites, so your accumulated thinking is safe. YOUR own
    notes (concepts, drafts, conclusions). Saved as plain Markdown under
    WissensWIKI/ and deliberately NEVER added to the search index. `path` is
    relative to WissensWIKI/, e.g. 'process-maturity.md' or 'Kapitel/2.md' (any
    subfolder). The corpus and the search index are never touched."""
    return tools.write_note(path, content)


@mcp.tool()
def save_report(title: str, content: str) -> str:
    """Compile a RESULT/REPORT into the notebook for cheap reuse — a table of
    findings, a comparison, an analysis summary. Saved as Markdown under
    WissensWIKI/Berichte/<title>.md and NOT search-indexed, so you can read it
    back later with read_note('Berichte/<title>.md') instead of re-deriving it
    (no extra tokens). Writing the same title again appends a dated section."""
    return tools.save_report(title, content)


def _warmup_reranker() -> None:
    """Load the (local, CPU) cross-encoder in the background so the FIRST search
    isn't blocked by the one-time model load. Best-effort; errors go to stderr
    (stdout is the JSON-RPC channel and must not be polluted)."""
    import sys
    try:
        from brag.search.query import _get_reranker
        _get_reranker()
    except Exception as e:  # noqa: BLE001 — warmup must never break the server
        print(f"reranker warmup skipped: {e}", file=sys.stderr)


if __name__ == "__main__":
    if config.RERANK_ENABLED and config.RERANK_WARMUP:
        import threading
        threading.Thread(target=_warmup_reranker, daemon=True).start()
    mcp.run()
