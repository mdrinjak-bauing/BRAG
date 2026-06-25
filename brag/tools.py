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
from brag.search import analytics
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


def coverage(query: str, top_k: int = 50, min_score: float = 0.4,
             mode: str = "broad", collection_name: str | None = None) -> str:
    """Stand der Forschung: aggregiert die Treffer pro Quelle (substanziell/peripheral)."""
    agg = analytics.source_coverage(query, top_k=top_k, min_score=min_score,
                                    mode=mode, collection_name=collection_name)
    if agg.get("error"):
        return f"Coverage fehlgeschlagen: {agg['error']}"
    label = {
        "broad": f"Substanziell — ≥3 Treffer mit max-Score ≥{min_score}",
        "specific": f"Spezifisch — max-Score ≥{min_score}, fokussierte Quellen zuerst",
        "both": f"Substanziell (breit) — ≥3 Treffer mit max-Score ≥{min_score}",
    }.get(mode, f"Substanziell — ≥3 Treffer mit max-Score ≥{min_score}")
    out = [f"**Coverage zu:** {query}",
           f"Analysiert: **{agg['total_chunks_analyzed']} Treffer aus "
           f"{agg['total_sources']} Quellen** (top_k={top_k}, min_score={min_score})\n",
           f"### {label} ({len(agg['substantial'])})"]
    if agg["substantial"]:
        for sf, count, maxs, _sample, page, chapters in agg["substantial"]:
            ch = f" · Kapitel: {', '.join(chapters[:3])}" if chapters else ""
            out.append(f"- `{sf}` — {count} Treffer, max {maxs:.3f} (S. {page}){ch}")
    else:
        out.append("_(keine)_")
    if mode == "both" and agg.get("substantial_specific"):
        out.append(f"\n### Spezifisch — fokussierte Quellen ({len(agg['substantial_specific'])})")
        for sf, count, maxs, _sample, page, _ch in agg["substantial_specific"][:15]:
            out.append(f"- `{sf}` — {count} Treffer, max {maxs:.3f} (S. {page})")
    out.append(f"\n### Peripheral — Randbezug ({len(agg['peripheral'])})")
    if agg["peripheral"]:
        for sf, count, maxs, _s, _p, _c in agg["peripheral"][:20]:
            out.append(f"- `{sf}` — {count} Treffer, max {maxs:.3f}")
        if len(agg["peripheral"]) > 20:
            out.append(f"… und {len(agg['peripheral']) - 20} weitere")
    else:
        out.append("_(keine)_")
    return "\n".join(out)


def clusters(query: str, top_k: int = 40, n_clusters: int = 5,
             collection_name: str | None = None) -> str:
    """Themen-Map: clustert die Treffer im Embedding-Raum (K-Means) in Sub-Themen."""
    res = analytics.topic_clusters(query, top_k=top_k, n_clusters=n_clusters,
                                   collection_name=collection_name)
    if res.get("error"):
        return f"Cluster-Analyse fehlgeschlagen: {res['error']}"
    out = [f"**Themen-Map zu:** {query}",
           f"{res['total_chunks']} Treffer in {len(res['clusters'])} Cluster\n"]
    for n, c in enumerate(res["clusters"], 1):
        rep = c["representative"]
        srcs = ", ".join(f"`{s}` ({k})" for s, k in c["sources"][:4])
        out.append(f"### Cluster {n} — {c['n_chunks']} Chunks aus {c['n_sources']} Quellen")
        out.append(f"Quellen: {srcs}")
        if c["chapters"]:
            out.append(f"Kapitel: {', '.join(c['chapters'][:5])}")
        sc = rep.get("score")
        sc_s = f" (Score {sc:.3f})" if isinstance(sc, (int, float)) else ""
        out.append(f"Repräsentant: `{rep['source_file']}` S. {rep['page']}{sc_s}")
        out.append(f"> {(rep['text'] or '').strip()[:220]}…\n")
    return "\n".join(out)


def compare_positions(query: str, sources: list[str], top_k_per_source: int = 3,
                      collection_name: str | None = None) -> str:
    """Stellt mehrere Quellen zu einer Frage side-by-side gegenüber."""
    res = analytics.compare_positions(query, sources, top_k_per_source=top_k_per_source,
                                      collection_name=collection_name)
    out = [f"**Side-by-side zu:** {query}\n"]
    for src, hits in res["results_by_source"].items():
        out.append(f"### {src}")
        for h in hits:
            sc = h.get("rerank_score") or h.get("score")
            sc_s = f"{sc:.3f}" if isinstance(sc, (int, float)) else "—"
            text = (h.get("text") or "").strip().replace("\n", " ")[:240]
            out.append(f"- S. {h.get('page_start', '?')} (Score {sc_s}): {text}…")
        out.append("")
    if res["missing"]:
        out.append(f"_Nicht im Korpus gefunden: {', '.join(res['missing'])}_")
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
    return f"Saved to `WissensWIKI/Quellenbelege/{slug}.md`{suffix}."


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
    indexed Quellenbelege/ nor the hidden .brag/. The user may use any subfolders."""
    return (_is_within(target, config.NOTEBOOK_DIR)
            and not _is_within(target, config.PASSAGES_DIR)
            and not _is_within(target, config.DATA_DIR))


def list_notebook() -> str:
    nb = config.NOTEBOOK_DIR
    files = (sorted(p for p in nb.rglob("*.md") if _is_notebook_path(p))
             if nb.exists() else [])
    if not files:
        return ("Notebook is empty. Write into WissensWIKI/ (any .md, any subfolder "
                "you like — Wissen/, Kapitel/, …) with write_note; it is NOT indexed.")
    out = [f"**Notebook — {len(files)} note(s) in WissensWIKI/**\n"]
    out += [f"- {p.relative_to(config.WISSENSWIKI_DIR).as_posix()}" for p in files]
    return "\n".join(out)


def read_note(path: str) -> str:
    target = _resolve_under(path, config.WISSENSWIKI_DIR)
    if target is None or not _is_notebook_path(target):
        return ("read_note reads your WissensWIKI notebook only — not Quellenbelege/ or "
                "the corpus (use search() for documents, list_passages() for passages).")
    if not target.is_file():
        return f"No such note: {path}"
    return target.read_text(encoding="utf-8")


def write_note(path: str, content: str) -> str:
    target = _resolve_under(path, config.WISSENSWIKI_DIR)
    if target is None or not _is_notebook_path(target):
        return ("Refused: write_note only writes inside WissensWIKI/ "
                "(not Quellenbelege/ or .brag/).")
    if target.suffix.lower() != ".md":
        target = target.with_suffix(".md")
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    if existed:
        # Never silently overwrite — a running note, or an auto-generated
        # literature note in Wissen/, must not be clobbered. Append a dated
        # section so the user's accumulated thinking is preserved (WIK-01/TOOL-F02).
        with open(target, "a", encoding="utf-8") as f:
            f.write(f"\n\n---\n\n_added {date.today().isoformat()}_\n\n"
                    f"{content.rstrip()}\n")
    else:
        target.write_text(content.rstrip() + "\n", encoding="utf-8")
    rel_out = target.relative_to(config.WISSENSWIKI_DIR).as_posix()
    verb = "Appended a dated section to" if existed else "Saved"
    return f"{verb} WissensWIKI/{rel_out} — your notebook (not indexed)."


def recent_sources(limit: int = 15, collection_name: str | None = None) -> str:
    collection_name = collection_name or config.COLLECTION_NAME
    client = storage.get_client()
    try:
        latest: dict[str, tuple[str, str]] = {}  # source -> (timestamp, doc_type)
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name, limit=1000, offset=offset,
                with_payload=["source_file", "ingest_timestamp", "doc_type"],
                with_vectors=False,
            )
            for p in points:
                pl = p.payload or {}
                src = pl.get("source_file", "?")
                ts = pl.get("ingest_timestamp", "") or ""
                if src not in latest or ts > latest[src][0]:
                    latest[src] = (ts, pl.get("doc_type", "?"))
            if not offset:
                break
    finally:
        client.close()
    if not latest:
        return ("Der Index ist leer — lege Dokumente in deinen Projektordner.")
    ranked = sorted(latest.items(), key=lambda kv: kv[1][0], reverse=True)
    ranked = ranked[:limit] if limit and limit > 0 else ranked
    out = [f"**Zuletzt aufgenommen ({len(ranked)}):**\n"]
    for src, (ts, dtype) in ranked:
        out.append(f"- `{src}` — {ts[:10] or '?'} ({dtype})")
    return "\n".join(out)


def set_metadata(folder: str, key: str, value: str) -> str:
    """Write/merge `key: value` into a corpus folder's _meta.txt and re-apply it to
    the already-indexed documents there (no re-embedding)."""
    key = key.strip().lower().replace(" ", "_")
    value = value.strip()
    if not key or not value:
        return ("Gib key UND value an, z. B. "
                "set_metadata('Nachtraege', 'projekt', 'Schulzentrum').")
    target_dir = _resolve_under(folder, config.SOURCES_DIR)
    if target_dir is None or not config.is_corpus_path(target_dir):
        return "Abgelehnt: Der Ordner muss im Korpus liegen (nicht WissensWIKI/)."
    if not target_dir.is_dir():
        return (f"Kein Ordner '{folder}' im Projektordner. "
                "Prüfe die Ordner über list_sources().")
    meta_file = target_dir / "_meta.txt"
    lines, found = [], False
    if meta_file.exists():
        for line in meta_file.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#") and ":" in s:
                k = s.split(":", 1)[0].strip().lower().replace(" ", "_")
                if k == key:
                    lines.append(f"{key}: {value}")
                    found = True
                    continue
            lines.append(line)
    if not found:
        lines.append(f"{key}: {value}")
    meta_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    n = -1
    try:
        from brag.ingest.pipeline import reapply_folder_metadata
        n = reapply_folder_metadata(target_dir)
    except Exception:  # noqa: BLE001 — index refresh is best-effort; the file is written
        pass
    tail = f"; {n} indexierte Chunks aktualisiert" if n >= 0 else ""
    return (f"Metadaten '{key}={value}' für Ordner '{folder}' gesetzt{tail}. "
            f"Jetzt filterbar mit meta_filter='{key}={value}'.")


def delete_note(path: str, confirm: bool = False) -> str:
    """Delete a WissensWIKI notebook file (Wissen/, … — NOT Quellenbelege/ nor the
    corpus). Two-step: refuses unless confirm=True."""
    target = _resolve_under(path, config.WISSENSWIKI_DIR)
    if target is None or not _is_notebook_path(target):
        return ("delete_note löscht nur im WissensWIKI-Notizbuch (Wissen/, …) — nicht "
                "Quellenbelege/ (dafür delete_passage) und nie den Korpus.")
    if target.suffix.lower() != ".md":
        target = target.with_suffix(".md")
    if not target.is_file():
        return f"Keine Notiz: {path}"
    rel = target.relative_to(config.WISSENSWIKI_DIR).as_posix()
    if not confirm:
        return (f"Sicher? Das löscht WissensWIKI/{rel} unwiderruflich. "
                "Zum Bestätigen erneut mit confirm=True aufrufen.")
    target.unlink()
    return f"Gelöscht: WissensWIKI/{rel}."


def _unindex_passage(slug: str) -> int:
    """Drop a saved passage's points from the search index (Qdrant)."""
    from brag.ingest.pipeline import remove_source as _remove
    return _remove(f"passage:{slug}")


def delete_passage(topic: str, confirm: bool = False) -> str:
    """Delete all saved passages of a topic (Quellenbelege/<slug>.md) AND their index
    points. Two-step: refuses unless confirm=True. Index is removed first, so a
    failure leaves the file (and index) intact rather than orphaning entries."""
    slug = config.slugify_topic(topic)
    path = config.PASSAGES_DIR / f"{slug}.md"
    if not path.is_file():
        return (f"Keine Passagen-Datei für '{topic}'. "
                "Themen siehst du über list_passages().")
    if not confirm:
        return (f"Sicher? Das löscht ALLE Passagen unter '{topic}' "
                f"(WissensWIKI/Quellenbelege/{slug}.md) UND entfernt sie aus dem Suchindex. "
                "Zum Bestätigen erneut mit confirm=True aufrufen.")
    try:
        removed = _unindex_passage(slug)
    except Exception:  # noqa: BLE001 — keep file+index consistent: abort if index down
        return ("Der Suchindex ist gerade nicht erreichbar — die Passage wurde NICHT "
                "gelöscht (sonst bliebe ein verwaister Index-Eintrag). Bitte erneut "
                "versuchen, sobald BRAG läuft.")
    path.unlink()
    return (f"Gelöscht: WissensWIKI/Quellenbelege/{slug}.md, "
            f"{removed} Chunks aus dem Suchindex entfernt.")


def move_note(path: str, new_path: str) -> str:
    """Move or rename a notebook file within WissensWIKI (creates target subfolders;
    never overwrites). Notebook only — not Quellenbelege/ nor the corpus."""
    src = _resolve_under(path, config.WISSENSWIKI_DIR)
    if src is None or not _is_notebook_path(src):
        return ("move_note bewegt nur Notizbuch-Dateien (Wissen/, …) — "
                "nicht Quellenbelege/ und nicht den Korpus.")
    if src.suffix.lower() != ".md":
        src = src.with_suffix(".md")
    if not src.is_file():
        return f"Keine Notiz: {path}"
    dst = _resolve_under(new_path, config.WISSENSWIKI_DIR)
    if dst is None or not _is_notebook_path(dst):
        return ("Abgelehnt: Das Ziel muss im Notizbuch liegen "
                "(nicht Quellenbelege/ oder Korpus).")
    if dst.suffix.lower() != ".md":
        dst = dst.with_suffix(".md")
    src_rel = src.relative_to(config.WISSENSWIKI_DIR).as_posix()
    if dst.resolve() == src.resolve():
        return "Quelle und Ziel sind identisch."
    if dst.exists():
        return f"Am Ziel existiert bereits {dst.name} — wähle einen anderen Namen."
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(src), str(dst))
    except OSError as e:
        return f"Konnte die Notiz nicht verschieben: {e}"
    dst_rel = dst.relative_to(config.WISSENSWIKI_DIR).as_posix()
    return f"Verschoben: WissensWIKI/{src_rel} → WissensWIKI/{dst_rel}."
