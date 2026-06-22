"""Thin per-project MCP client for Claude Desktop / LM Studio.

Started per project as
  docker exec -i -e BRAG_PROJECT=<slug> brag-app python -m brag.mcp_client

It loads NO models: every tool forwards to the persistent app's HTTP bridge
(search via /api/search, all other tools via /api/index-op), where the embedder,
sparse model and reranker live exactly ONCE. So opening 5–10 project connectors
at the same time does not multiply model RAM — the whole point of the
multi-project design. The connector's BRAG_PROJECT env selects which project's
collection/vault every call targets.

Same tool surface, names and docstrings as brag.mcp_server, so Claude sees an
identical set of tools — only the implementation is a thin HTTP forwarder.
"""

import json
import os
import urllib.error
import urllib.request

from mcp.server.fastmcp import FastMCP

from brag import config
from brag.formatting import format_hit, parse_meta_filter

mcp = FastMCP("brag")

PROJECT = os.environ.get("BRAG_PROJECT", "").strip()
_BASE = f"http://localhost:{config.BRIDGE_PORT}"
_BUSY = ("BRAG's search service is starting up or unavailable — your documents "
         "are safe; please retry in a few seconds.")


def _post(path: str, payload: dict, timeout: int = 180) -> dict | None:
    """POST JSON to the in-container bridge. Returns the parsed dict, or None on
    any transport/parse failure (the caller turns that into a friendly message —
    a bridge hiccup must never crash the MCP session)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        _BASE + path, data=data,
        headers={"Content-Type": "application/json", "Host": "localhost"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return None


def _index_op(op: str, **args) -> str:
    resp = _post("/api/index-op", {"op": op, "project": PROJECT, "args": args})
    if resp is None:
        return _BUSY
    if not resp.get("ok"):
        return resp.get("message", f"{op} failed")
    return resp.get("text", "")


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
    resp = _post("/api/search", {
        "project": PROJECT, "query": query, "top_k": top_k,
        "doc_type": doc_type, "chunk_type": chunk_type,
        "year_min": year_min, "year_max": year_max,
        "source_file": source_file, "reranking": reranking,
        "meta": parse_meta_filter(meta_filter),
    })
    if resp is None:
        return _BUSY
    if not resp.get("ok"):
        return resp.get("message", "search failed")
    hits = resp.get("hits", [])
    if not hits:
        return ("No hits. Try different phrasing, fewer filters, or check "
                "list_sources() whether the document is indexed at all.")
    out = [f"**{len(hits)} hits** for: {query}\n"]
    out += [format_hit(i + 1, h, project=PROJECT) for i, h in enumerate(hits)]
    return "\n".join(out)


@mcp.tool()
def list_sources(doc_type: str = "") -> str:
    """List all indexed documents with chunk counts, grouped by type."""
    return _index_op("list_sources", doc_type=doc_type)


@mcp.tool()
def inspect_chunks(source_file: str, page: int = 0, limit: int = 10) -> str:
    """Diagnostic tool — show the raw chunks stored in the index for one source,
    to debug retrieval ('why doesn't search find X?'). NOT for answering a
    question (use search for that). Optionally filter by page number."""
    return _index_op("inspect_chunks", source_file=source_file, page=page, limit=limit)


@mcp.tool()
def remove_source(source_file: str) -> str:
    """Remove a document from the SEARCH INDEX — use it to drop a wrong,
    duplicate or outdated source the user no longer wants in results.

    Safe and reversible: the file is NOT deleted, it is moved into an
    _inbox/ (a staging area the watcher ignores) so it can't be re-indexed, and
    its chunks + literature note are removed from the index. `source_file` is the
    key shown by list_sources (e.g. 'projects/Bericht'). Call once per source."""
    return _index_op("remove_source", source_file=source_file)


@mcp.tool()
def rename_source(source_file: str, new_name: str) -> str:
    """Rename / re-file an indexed document and update its index metadata IN
    PLACE (no re-embedding). Renames/moves the FILE in your project folder;
    `new_name` may include a relative folder to also move it (e.g.
    'projects/School_Center/Final_Report'). The original file suffix is kept if
    you omit it. `source_file` is the current key from list_sources."""
    return _index_op("rename_source", source_file=source_file, new_name=new_name)


@mcp.tool()
def save_passage(topic: str, text: str, source: str, page: str = "",
                 note: str = "") -> str:
    """Save a quotable passage under a topic (e.g. a chapter or theme).

    WHEN to use which: a verbatim QUOTE from a source → save_passage (it becomes
    searchable evidence); YOUR OWN text (notes, drafts, conclusions) → write_note;
    a finished/compiled deliverable → save_report.

    Builds your evidence base in WissensWIKI/Passagen/<topic>.md AND indexes
    the passage for semantic search, so a later chat (even with a different
    provider) finds it again via `search` — it appears as a clearly marked
    "saved passage", distinct from primary sources. Use this to persist the
    findings, decisions and definitions of a working session so the knowledge
    lives in the folder, not in one chat's history."""
    return _index_op("save_passage", topic=topic, text=text, source=source,
                     page=page, note=note)


@mcp.tool()
def list_passages(topic: str = "") -> str:
    """List saved passages: pass a topic to see the passages saved under it, or
    leave it empty for an overview of all topics. (Saved passages also surface in
    search, marked as a "saved passage" — this is the by-topic browse view.)"""
    return _index_op("list_passages", topic=topic)


@mcp.tool()
def list_notebook() -> str:
    """List your NOTEBOOK — your own .md notes and subfolders in WissensWIKI/.
    Deliberately NOT search-indexed (use search() for the corpus, list_passages()
    for verified passages). Open one with read_note, create or update with
    write_note."""
    return _index_op("list_notebook")


@mcp.tool()
def read_note(path: str) -> str:
    """Read a NOTEBOOK markdown file. `path` is relative to WissensWIKI/, e.g.
    'process-maturity.md' or 'Notizen/Mueller_2023.md'. Only the notebook
    (WissensWIKI/, excluding the indexed Passagen/) is reachable here — the corpus
    and the search index are not (use search() for those)."""
    return _index_op("read_note", path=path)


@mcp.tool()
def write_note(path: str, content: str) -> str:
    """Create a NOTEBOOK note, or APPEND a dated section to an existing one — it
    never silently overwrites, so your accumulated thinking is safe. For YOUR OWN
    text (concepts, drafts, conclusions); for a verbatim source quote that should
    be searchable evidence use save_passage instead. Saved as plain Markdown under
    WissensWIKI/ and deliberately NEVER added to the search index. `path` is
    relative to WissensWIKI/, e.g. 'process-maturity.md' or 'Kapitel/2.md' (any
    subfolder). The corpus and the search index are never touched."""
    return _index_op("write_note", path=path, content=content)


@mcp.tool()
def save_report(title: str, content: str) -> str:
    """Compile a RESULT/REPORT into the notebook for cheap reuse — a table of
    findings, a comparison, an analysis summary. Saved as Markdown under
    WissensWIKI/Berichte/<title>.md and NOT search-indexed, so you can read it
    back later with read_note('Berichte/<title>.md') instead of re-deriving it
    (no extra tokens). Writing the same title again appends a dated section."""
    return _index_op("save_report", title=title, content=content)


if __name__ == "__main__":
    mcp.run()
