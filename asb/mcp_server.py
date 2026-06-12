"""MCP server for Claude Desktop (stdio transport).

Claude Desktop starts this via `docker exec -i asb-app python -m asb.mcp_server`
inside the running container — the setup wizard writes that config entry.

Tools: search, list_sources, inspect_chunks, save_passage, list_passages.
"""

import re
from datetime import date

from mcp.server.fastmcp import FastMCP

from asb import config, storage
from asb.http_bridge import pdf_link
from asb.search.query import search as run_search

mcp = FastMCP("academic-second-brain")

PREVIEW_CHARS = 1000  # tables are never truncated, text gets a preview


def _format_hit(i: int, hit: dict) -> str:
    src = hit.get("source_file", "?")
    author, year = hit.get("author", ""), hit.get("year", "")
    page = hit.get("page_start", "")
    link = pdf_link(hit.get("rel_path", ""), hit.get("page_start"))
    cite = f"{author} ({year})" if author and author != "Unknown" else src
    header = f"### [{i}] [{cite} — p. {page}](<{link}>)"
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
           reranking: bool = True) -> str:
    """Hybrid search (semantic + keyword) over the document corpus.

    Try multiple phrasings (synonyms, English/native-language variants).
    Use chunk_type='table' for numbers/statistics, 'figure' for diagrams.
    meta_filter restricts hits by the user's own metadata fields (defined
    in _meta.txt files in the vault), format 'key=value' with commas for
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
        return "The index is empty — drop documents into vault/sources/."
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
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    must = [FieldCondition(
        key="source_file",
        match=MatchValue(value=config.normalize_source_key(source_file)),
    )]
    if page:
        must.append(FieldCondition(key="page_start", match=MatchValue(value=page)))
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


def _passage_file(topic: str):
    slug = re.sub(r"[^\w\-]+", "_", topic.strip()).strip("_") or "general"
    config.PASSAGES_DIR.mkdir(parents=True, exist_ok=True)
    return config.PASSAGES_DIR / f"{slug}.md", slug


@mcp.tool()
def save_passage(topic: str, text: str, source: str, page: str = "",
                 note: str = "") -> str:
    """Save a quotable passage under a topic (e.g. a chapter or theme).
    Builds your evidence base in vault/passages/<topic>.md."""
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
    return f"Saved to `passages/{slug}.md`."


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


if __name__ == "__main__":
    mcp.run()
