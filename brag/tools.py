"""Tool implementations — the engine side of BRAG's MCP tools.

Shared by the MCP server (mcp_server.py, single-project), the HTTP-bridge tool
dispatcher (so a thin per-project MCP client can run them in the persistent app)
and the tests. Pure Python: NO `mcp` import and no model libraries at import
time, so the bridge and tests can import it without the FastMCP / torch stack.

The search and index-read helpers take an optional `collection_name`; it
defaults to the single-project config.COLLECTION_NAME, while the multi-project
bridge passes a per-project collection so each project only sees its own data.
File-side operations (passages, notebook, the file move/rename in remove/rename)
use config's vault paths — the bridge scopes those per project via
config.project_context in a later phase; today they target the single vault.
"""

import shutil
from datetime import date

from brag import config, storage
from brag.formatting import format_hit, parse_meta_filter
from brag.search.query import search as run_search


def search_text(query: str, top_k: int = 0, doc_type: str = "",
                chunk_type: str = "", year_min: int = 0, year_max: int = 0,
                source_file: str = "", meta_filter: str = "",
                reranking: bool | None = None, max_per_source: int = 0,
                mode: str = "normal", collection_name: str | None = None) -> str:
    meta = parse_meta_filter(meta_filter)
    hits = run_search(
        query, top_k=(top_k or None), mode=mode, reranking=reranking,
        collection_name=collection_name,
        max_chunks_per_source=(max_per_source or None),
        doc_type=doc_type or None, chunk_type=chunk_type or None,
        year_min=year_min or None, year_max=year_max or None,
        source_file=source_file or None, meta=meta or None,
    )
    if not hits:
        return ("No hits. Try different phrasing, fewer filters, or check "
                "list_sources() whether the document is indexed at all.")
    out = [f"**{len(hits)} hits** for: {query}\n"]
    out += [format_hit(i + 1, h) for i, h in enumerate(hits)]
    return "\n".join(out)


def list_sources(doc_type: str = "", collection_name: str | None = None) -> str:
    collection_name = collection_name or config.COLLECTION_NAME
    client = storage.get_client()
    try:
        counts: dict[tuple[str, str], int] = {}
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name, limit=1000, offset=offset,
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
        return ("The index is empty — drop documents (and subfolders) straight "
                "into your project folder.")
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


def inspect_chunks(source_file: str, page: int = 0, limit: int = 10,
                   collection_name: str | None = None) -> str:
    from qdrant_client.models import FieldCondition, Filter, MatchAny, Range

    collection_name = collection_name or config.COLLECTION_NAME
    must = [FieldCondition(
        key="source_file",
        match=MatchAny(any=config.source_key_variants(source_file)),
    )]
    if page:
        # A chunk can span pages (page_start..page_end), so match every chunk
        # whose range COVERS the requested page — not only those that start on it.
        must.append(FieldCondition(key="page_start", range=Range(lte=page)))
        must.append(FieldCondition(key="page_end", range=Range(gte=page)))
    client = storage.get_client()
    try:
        points, _ = client.scroll(
            collection_name, limit=limit,
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


def read_source(source_file: str, page_from: int = 0, page_to: int = 0,
                limit: int = 25, collection_name: str | None = None) -> str:
    """Return a source's chunks in reading order (by page) — no query, no rerank.
    For reading/evaluating a whole document; optional page_from..page_to range."""
    from qdrant_client.models import FieldCondition, Filter, MatchAny, Range

    collection_name = collection_name or config.COLLECTION_NAME
    must = [FieldCondition(
        key="source_file",
        match=MatchAny(any=config.source_key_variants(source_file)),
    )]
    if page_from:
        must.append(FieldCondition(key="page_end", range=Range(gte=page_from)))
    if page_to:
        must.append(FieldCondition(key="page_start", range=Range(lte=page_to)))
    client = storage.get_client()
    try:
        points, offset = [], None
        while True:
            batch, offset = client.scroll(
                collection_name, limit=1000, offset=offset,
                scroll_filter=Filter(must=must),
                with_payload=True, with_vectors=False,
            )
            points.extend(batch)
            if not offset:
                break
    finally:
        client.close()
    rng = f" (Seiten {page_from}-{page_to})" if (page_from or page_to) else ""
    if not points:
        return (f"Kein Inhalt für '{source_file}'{rng} gefunden. "
                "Prüfe den genauen Namen über list_sources().")
    points.sort(key=lambda p: ((p.payload or {}).get("page_start", 0),
                               (p.payload or {}).get("page_end", 0)))
    total = len(points)
    shown = points[:limit] if limit and limit > 0 else points
    head = (f"**{source_file}** — {total} Abschnitte in Lesereihenfolge{rng}"
            + (f", erste {len(shown)} gezeigt" if len(shown) < total else "") + "\n")
    out = [head]
    for p in shown:
        pl = p.payload or {}
        out.append(f"--- S. {pl.get('page_start')} | {pl.get('chunk_type')} "
                   f"| {pl.get('chapter') or '—'}\n{pl.get('text') or ''}\n")
    if len(shown) < total:
        out.append(f"\n… {total - len(shown)} weitere Abschnitte. Mit "
                   "page_from/page_to eingrenzen oder limit erhöhen.")
    return "\n".join(out)


def _find_source_file(key: str):
    """Locate the on-disk corpus document whose identity key matches `key` (any
    supported suffix), skipping WissensWIKI + the ignored _inbox staging area."""
    for p in config.SOURCES_DIR.rglob("*"):
        if (p.is_file()
                and p.suffix.lower() in config.SUPPORTED_SUFFIXES
                and config.is_corpus_path(p)
                and config.source_key_from_path(p) == key):
            return p
    return None


def remove_source(source_file: str) -> str:
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
        msg += f"; the file was moved to _inbox/{moved_to} (not deleted)"
    return msg + "."


def rename_source(source_file: str, new_name: str) -> str:
    from brag.ingest.pipeline import rename_source as _rename_source

    key = config.normalize_source_key(source_file)
    if not key or key.startswith("passage:"):
        return "Provide a document source_file from list_sources() (not a saved passage)."
    current = _find_source_file(key)
    if current is None:
        return (f"No file found for '{source_file}' in the project folder. "
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
        return "Refused: the new name escapes the project folder."
    if not config.is_corpus_path(new_path):
        return "Refused: the new name must stay in the corpus (not WissensWIKI/)."
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
    slug = config.slugify_topic(topic)
    config.PASSAGES_DIR.mkdir(parents=True, exist_ok=True)
    return config.PASSAGES_DIR / f"{slug}.md", slug


def save_passage(topic: str, text: str, source: str, page: str = "",
                 note: str = "") -> str:
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
    suffix = (" and indexed for search" if indexed
              else " (saved to file; search index unavailable)")
    return f"Saved to `WissensWIKI/Passagen/{slug}.md`{suffix}."


def list_passages(topic: str = "") -> str:
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


def _is_notebook_path(target) -> bool:
    """A path inside the WissensWIKI notebook — under WissensWIKI/ but NOT the
    indexed Passagen/ nor the hidden .brag/. The user may use any subfolders."""
    return (_is_within(target, config.NOTEBOOK_DIR)
            and not _is_within(target, config.PASSAGES_DIR)
            and not _is_within(target, config.DATA_DIR))


def list_notebook() -> str:
    nb = config.NOTEBOOK_DIR
    files = (sorted(p for p in nb.rglob("*.md") if _is_notebook_path(p))
             if nb.exists() else [])
    if not files:
        return ("Notebook is empty. Write into WissensWIKI/ (any .md, any subfolder "
                "you like — Notizen/, Kapitel/, …) with write_note; it is NOT indexed.")
    out = [f"**Notebook — {len(files)} note(s) in WissensWIKI/**\n"]
    out += [f"- {p.relative_to(config.WISSENSWIKI_DIR).as_posix()}" for p in files]
    return "\n".join(out)


def read_note(path: str) -> str:
    target = _resolve_under(path, config.WISSENSWIKI_DIR)
    if target is None or not _is_notebook_path(target):
        return ("read_note reads your WissensWIKI notebook only — not Passagen/ or "
                "the corpus (use search() for documents, list_passages() for passages).")
    if not target.is_file():
        return f"No such note: {path}"
    return target.read_text(encoding="utf-8")


def write_note(path: str, content: str) -> str:
    target = _resolve_under(path, config.WISSENSWIKI_DIR)
    if target is None or not _is_notebook_path(target):
        return ("Refused: write_note only writes inside WissensWIKI/ "
                "(not Passagen/ or .brag/).")
    if target.suffix.lower() != ".md":
        target = target.with_suffix(".md")
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    if existed:
        # Never silently overwrite — a running note, or an auto-generated
        # literature note in Notizen/, must not be clobbered. Append a dated
        # section so the user's accumulated thinking is preserved (WIK-01/TOOL-F02).
        with open(target, "a", encoding="utf-8") as f:
            f.write(f"\n\n---\n\n_added {date.today().isoformat()}_\n\n"
                    f"{content.rstrip()}\n")
    else:
        target.write_text(content.rstrip() + "\n", encoding="utf-8")
    rel_out = target.relative_to(config.WISSENSWIKI_DIR).as_posix()
    verb = "Appended a dated section to" if existed else "Saved"
    return f"{verb} WissensWIKI/{rel_out} — your notebook (not indexed)."


def save_report(title: str, content: str) -> str:
    slug = config.slugify_topic(title)
    base = config.WISSENSWIKI_DIR / "Berichte"
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"{slug}.md"
    existed = target.exists()
    block = (f"\n\n---\n\n_added {date.today().isoformat()}_\n\n{content.rstrip()}\n"
             if existed else f"# {title}\n\n{content.rstrip()}\n")
    with open(target, "a", encoding="utf-8") as f:
        f.write(block)
    verb = "Appended to" if existed else "Saved report to"
    return (f"{verb} WissensWIKI/Berichte/{slug}.md — reuse it later with "
            f"read_note('Berichte/{slug}.md'); not indexed.")
