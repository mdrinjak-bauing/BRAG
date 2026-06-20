"""MCP server for Claude Desktop (stdio transport).

Claude Desktop starts this via `docker exec -i brag-app python -m brag.mcp_server`
inside the running container — the setup wizard writes that config entry.

Tools: search, list_sources, inspect_chunks, remove_source, rename_source,
save_passage, list_passages, list_notebook, read_note, write_note.
"""

import re
import shutil
from datetime import date

from mcp.server.fastmcp import FastMCP

from brag import config, storage
from brag.http_bridge import pdf_link
from brag.search.query import search as run_search

mcp = FastMCP("brag")

PREVIEW_CHARS = 1000  # tables are never truncated, text gets a preview


def _format_hit(i: int, hit: dict) -> str:
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
    link = pdf_link(hit.get("rel_path", ""), phys_page)
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
    meta = {}
    for part in meta_filter.split(","):
        if "=" in part:
            key, _, value = part.partition("=")
            if key.strip() and value.strip():
                meta[key.strip().lower().replace(" ", "_")] = value.strip()
    hits = run_search(
        query, top_k=top_k, reranking=reranking,
        doc_type=doc_type or None, chunk_type=chunk_type or None,
        year_min=year_min or None, year_max=year_max or None,
        source_file=source_file or None, meta=meta or None,
    )
    if not hits:
        return ("No hits. Try different phrasing, fewer filters, or check "
                "list_sources() whether the document is indexed at all.")
    out = [f"**{len(hits)} hits** for: {query}\n"]
    out += [_format_hit(i + 1, h) for i, h in enumerate(hits)]
    return "\n".join(out)


@mcp.tool()
def list_sources(doc_type: str = "") -> str:
    """List all indexed documents with chunk counts, grouped by type."""
    client = storage.get_client()
    try:
        counts: dict[tuple[str, str], int] = {}
        offset = None
        while True:
            points, offset = client.scroll(
                config.COLLECTION_NAME, limit=1000, offset=offset,
                with_payload=["source_file", "doc_type"], with_vectors=False,
            )
            for p in points:
                pl = p.payload or {}
                key = (pl.get("doc_type", "?"), pl.get("source_file", "?"))
                counts[key] = counts.get(key, 0) + 1
            if not offset:
                break
    finally:
        client.close()
    if not counts:
        return "The index is empty — drop documents into RAG-Verbindungsordner/sources/."
    by_type: dict[str, list] = {}
    for (dtype, src), n in sorted(counts.items()):
        if doc_type and dtype != doc_type:
            continue
        by_type.setdefault(dtype, []).append((src, n))
    out = [f"**{sum(len(v) for v in by_type.values())} sources indexed**\n"]
    for dtype, items in sorted(by_type.items()):
        out.append(f"## {dtype} ({len(items)})")
        out += [f"- `{src}` — {n} chunks" for src, n in items]
        out.append("")
    return "\n".join(out)


@mcp.tool()
def inspect_chunks(source_file: str, page: int = 0, limit: int = 10) -> str:
    """Show what is actually stored in the index for a source (debugging:
    'why doesn't the search find X?'). Optionally filter by page number."""
    from qdrant_client.models import FieldCondition, Filter, MatchAny, Range

    must = [FieldCondition(
        key="source_file",
        match=MatchAny(any=config.source_key_variants(source_file)),
    )]
    if page:
        # A chunk can span pages (page_start..page_end), so match every chunk
        # whose range COVERS the requested page — not only those that start on
        # it, which would miss a chunk beginning on an earlier page.
        must.append(FieldCondition(key="page_start", range=Range(lte=page)))
        must.append(FieldCondition(key="page_end", range=Range(gte=page)))
    client = storage.get_client()
    try:
        points, _ = client.scroll(
            config.COLLECTION_NAME, limit=limit,
            scroll_filter=Filter(must=must),
            with_payload=True, with_vectors=False,
        )
    finally:
        client.close()
    if not points:
        return (f"No chunks found for '{source_file}'"
                + (f" on page {page}" if page else "")
                + ". Check the exact name via list_sources().")
    standard_keys = {
        "text", "context", "chunk_type", "source_file", "rel_path",
        "page_start", "page_end", "chapter", "section", "doc_type",
        "author", "year", "year_num", "language", "chunk_id",
        "ingest_timestamp",
    }
    out = [f"**{len(points)} chunks** for `{source_file}`"
           + (f", page {page}" if page else "") + "\n"]
    first_pl = points[0].payload or {}
    custom = {k: v for k, v in first_pl.items() if k not in standard_keys}
    if custom:
        out.append("Custom metadata: "
                   + ", ".join(f"`{k}={v}`" for k, v in sorted(custom.items()))
                   + "\n")
    for p in sorted(points, key=lambda x: (x.payload or {}).get("page_start", 0)):
        pl = p.payload or {}
        out.append(
            f"--- p. {pl.get('page_start')} | {pl.get('chunk_type')} "
            f"| chapter: {pl.get('chapter') or '—'}\n"
            f"context: {pl.get('context') or '(empty)'}\n"
            f"text: {(pl.get('text') or '')[:600]}\n"
        )
    return "\n".join(out)


def _find_source_file(key: str):
    """Locate the on-disk document under sources/ whose identity key matches
    `key` (any supported suffix), skipping the ignored _inbox staging area.
    Returns the Path or None."""
    for p in config.SOURCES_DIR.rglob("*"):
        if (p.is_file()
                and p.suffix.lower() in config.SUPPORTED_SUFFIXES
                and "_inbox" not in p.parts
                and config.source_key_from_path(p) == key):
            return p
    return None


@mcp.tool()
def remove_source(source_file: str) -> str:
    """Remove a document from the SEARCH INDEX — use it to drop a wrong,
    duplicate or outdated source the user no longer wants in results.

    Safe and reversible: the file is NOT deleted, it is moved into
    sources/_inbox/ (a staging area the watcher ignores) so it can't be
    re-indexed, and its chunks + literature note are removed from the index.
    `source_file` is the key shown by list_sources (e.g. 'projects/Bericht').
    Call once per source."""
    from brag.ingest.pipeline import remove_source as _remove_source

    key = config.normalize_source_key(source_file)
    if not key or key.startswith("passage:"):
        return "Provide a document source_file from list_sources() (not a saved passage)."
    moved_to = ""
    src = _find_source_file(key)
    if src is not None:
        try:
            inbox = config.SOURCES_DIR / "_inbox"
            inbox.mkdir(parents=True, exist_ok=True)
            dest = inbox / src.name
            i = 1
            while dest.exists():
                dest = inbox / f"{src.stem}_{i}{src.suffix}"
                i += 1
            shutil.move(str(src), str(dest))
            moved_to = dest.name
        except OSError as e:
            return f"Could not move the file out of the index: {e}"
    n = _remove_source(key)
    if not n and not moved_to:
        return (f"Nothing to remove — no indexed chunks and no file found for "
                f"'{source_file}'. Check the exact key via list_sources().")
    msg = f"Removed `{key}` from the index ({n} chunks)"
    if moved_to:
        msg += f"; the file was moved to sources/_inbox/{moved_to} (not deleted)"
    return msg + "."


@mcp.tool()
def rename_source(source_file: str, new_name: str) -> str:
    """Rename / re-file an indexed document and update its index metadata IN
    PLACE (no re-embedding). Renames the FILE under sources/; `new_name` may
    include a relative folder to also move it (e.g.
    'projects/School_Center/Final_Report'). The original file suffix is kept if
    you omit it. `source_file` is the current key from list_sources."""
    from brag.ingest.pipeline import rename_source as _rename_source

    key = config.normalize_source_key(source_file)
    if not key or key.startswith("passage:"):
        return "Provide a document source_file from list_sources() (not a saved passage)."
    current = _find_source_file(key)
    if current is None:
        return (f"No file found for '{source_file}' under sources/. "
                "Check the exact key via list_sources().")
    rel = new_name.strip().replace("\\", "/").lstrip("/")
    if not rel:
        return "Provide a new name."
    new_path = config.SOURCES_DIR / rel
    if new_path.suffix.lower() not in config.SUPPORTED_SUFFIXES:
        new_path = new_path.with_suffix(current.suffix)
    try:
        new_path.resolve().relative_to(config.SOURCES_DIR.resolve())
    except ValueError:
        return "Refused: the new name escapes sources/."
    if new_path.resolve() == current.resolve():
        return "The new name is the same as the current one."
    if new_path.exists():
        return f"A file named {new_path.name} already exists there — choose another name."
    try:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current), str(new_path))
    except OSError as e:
        return f"Could not rename the file: {e}"
    n = _rename_source(key, new_path)
    return (f"Renamed to `{config.source_key_from_path(new_path)}` "
            f"({n} chunks updated in place, no re-embedding).")


def _passage_file(topic: str):
    slug = re.sub(r"[^\w\-]+", "_", topic.strip()).strip("_") or "general"
    config.PASSAGES_DIR.mkdir(parents=True, exist_ok=True)
    return config.PASSAGES_DIR / f"{slug}.md", slug


@mcp.tool()
def save_passage(topic: str, text: str, source: str, page: str = "",
                 note: str = "") -> str:
    """Save a quotable passage under a topic (e.g. a chapter or theme).

    Builds your evidence base in RAG-Verbindungsordner/passages/<topic>.md AND indexes
    the passage for semantic search, so a later chat (even with a different
    provider) finds it again via `search` — it appears as a clearly marked
    "saved passage", distinct from primary sources. Use this to persist the
    findings, decisions and definitions of a working session so the knowledge
    lives in the folder, not in one chat's history."""
    path, slug = _passage_file(topic)
    is_new = not path.exists()
    block = [
        "" if is_new else "\n---\n",
        f"### {source}" + (f", p. {page}" if page else ""),
        f"_saved {date.today().isoformat()}_",
        "",
        f"> {text.strip()}",
    ]
    if note:
        block += ["", f"**Note:** {note}"]
    header = f"# Passages: {topic}\n\n" if is_new else ""
    with open(path, "a", encoding="utf-8") as f:
        f.write(header + "\n".join(block) + "\n")
    from brag.ingest.pipeline import index_passage
    indexed = index_passage(topic, text, source, page, note)
    suffix = " and indexed for search" if indexed else " (saved to file; search index unavailable)"
    return f"Saved to `passages/{slug}.md`{suffix}."


@mcp.tool()
def list_passages(topic: str = "") -> str:
    """List saved passages — for one topic, or an overview of all topics."""
    if not config.PASSAGES_DIR.exists():
        return "No passages saved yet."
    files = sorted(config.PASSAGES_DIR.glob("*.md"))
    if not files:
        return "No passages saved yet."
    if topic:
        path, slug = _passage_file(topic)
        if not path.exists():
            return f"No passages for '{topic}'. Topics: " + ", ".join(
                f.stem for f in files)
        return path.read_text(encoding="utf-8")
    out = ["**Saved passage topics:**\n"]
    for f in files:
        n = f.read_text(encoding="utf-8").count("### ")
        out.append(f"- `{f.stem}` — {n} passages")
    return "\n".join(out)


# ── Notebook (wiki/ + notes/) — your own thinking, NOT search-indexed ──────────
# A second "connection" without a second MCP server: instead of a separate
# filesystem MCP (extra dependency + its own Claude-config entry), the notebook
# read/write tools live in THIS server. The source library stays read-only via
# search(); the search index is never touched by these.
def _resolve_under(rel, base):
    """Resolve `rel` under `base`, or None if it escapes (path-traversal guard)."""
    base = base.resolve()
    target = (base / str(rel).replace("\\", "/").lstrip("/")).resolve()
    try:
        target.relative_to(base)
        return target
    except ValueError:
        return None


def _is_within(target, base) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


@mcp.tool()
def list_notebook() -> str:
    """List your NOTEBOOK — your own wiki pages and the auto-generated literature
    notes. This is the part of the knowledge store deliberately NOT search-indexed
    (use search() for the source library). Open one with read_note, create or
    update a wiki page with write_note."""
    out = []
    for label, d in (("wiki", config.WIKI_DIR), ("notes", config.NOTES_DIR)):
        files = sorted(d.rglob("*.md")) if d.exists() else []
        out.append(f"## {label}/ ({len(files)})")
        out += [f"- {p.relative_to(config.VAULT).as_posix()}" for p in files]
    joined = "\n".join(out).strip()
    return joined or "Notebook is empty — no wiki/ or notes/ files yet."


@mcp.tool()
def read_note(path: str) -> str:
    """Read a NOTEBOOK markdown file. `path` is relative to the knowledge store,
    e.g. 'wiki/process-maturity.md' or 'notes/Mueller_2023.md'. Only the notebook
    (wiki/, notes/) is reachable here — the source library and the search index
    are not (use search() for those)."""
    target = _resolve_under(path, config.VAULT)
    if target is None:
        return "Refused: path escapes the knowledge store."
    if not (_is_within(target, config.WIKI_DIR) or _is_within(target, config.NOTES_DIR)):
        return "read_note only reads the notebook (wiki/, notes/). Use search() for sources."
    if not target.is_file():
        return f"No such note: {path}"
    return target.read_text(encoding="utf-8")


@mcp.tool()
def write_note(path: str, content: str) -> str:
    """Create or overwrite a WIKI note — YOUR own thinking (concepts, drafts,
    conclusions, intermediate results). Saved as plain Markdown under wiki/ and
    deliberately NEVER added to the search index. `path` is relative to wiki/,
    e.g. 'process-maturity.md' or 'methods/maturity-models.md'. The source
    library (sources/) and the search index are never touched."""
    rel = path.strip().replace("\\", "/").lstrip("/")
    if rel.startswith("wiki/"):
        rel = rel[len("wiki/"):]
    target = _resolve_under(rel, config.WIKI_DIR)
    if target is None:
        return "Refused: path escapes wiki/."
    if target.suffix.lower() != ".md":
        target = target.with_suffix(".md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    rel_out = target.relative_to(config.WIKI_DIR).as_posix()
    return f"Saved to wiki/{rel_out} — your notebook (not indexed)."


def _warmup_reranker() -> None:
    """Load the (local, CPU) cross-encoder in the background so the FIRST search
    isn't blocked by the one-time model load. Best-effort; runs only off the
    start path — a multi-second synchronous load here could outlast Claude
    Desktop's MCP initialize handshake. Errors go to stderr (stdout is the
    JSON-RPC channel and must not be polluted)."""
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
