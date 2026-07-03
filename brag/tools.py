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


NO_HITS_MSG = ("No hits. Try different phrasing, fewer filters, or check "
               "list_sources() whether the document is indexed at all.")


def search_hits(query: str, top_k: int = 0, doc_type: str = "",
                chunk_type: str = "", year_min: int = 0, year_max: int = 0,
                source_file: str = "", meta_filter: str = "",
                reranking: bool | None = None, max_per_source: int = 0,
                mode: str = "normal",
                collection_name: str | None = None) -> list[dict]:
    """Run the hybrid search with the tool-surface argument conventions
    (0/"" = default) and return the raw hit dicts. Shared base of search_text
    and the image-attaching MCP search."""
    meta = parse_meta_filter(meta_filter)
    return run_search(
        query, top_k=(top_k or None), mode=mode, reranking=reranking,
        collection_name=collection_name,
        max_chunks_per_source=(max_per_source or None),
        doc_type=doc_type or None, chunk_type=chunk_type or None,
        year_min=year_min or None, year_max=year_max or None,
        source_file=source_file or None, meta=meta or None,
    )


def format_hits(hits: list[dict], query: str, project: str = "",
                attached_ids: set[str] | None = None) -> str:
    """Render hits as the search tool's Markdown block. `attached_ids` marks the
    chunks whose figure image is attached to the same response as an image, so
    the model knows the picture directly below belongs to that hit."""
    out = [f"**{len(hits)} hits** for: {query}\n"]
    for i, h in enumerate(hits):
        block = format_hit(i + 1, h, project=project)
        if attached_ids and str(h.get("chunk_id", "")) in attached_ids:
            block += "🖼️ Die Abbildung liegt dieser Antwort als Bild bei.\n"
        out.append(block)
    return "\n".join(out)


def search_text(query: str, top_k: int = 0, doc_type: str = "",
                chunk_type: str = "", year_min: int = 0, year_max: int = 0,
                source_file: str = "", meta_filter: str = "",
                reranking: bool | None = None, max_per_source: int = 0,
                mode: str = "normal", collection_name: str | None = None) -> str:
    hits = search_hits(
        query, top_k=top_k, doc_type=doc_type, chunk_type=chunk_type,
        year_min=year_min, year_max=year_max, source_file=source_file,
        meta_filter=meta_filter, reranking=reranking,
        max_per_source=max_per_source, mode=mode,
        collection_name=collection_name,
    )
    if not hits:
        return NO_HITS_MSG
    return format_hits(hits, query)


# ── Research analyses: coverage / clusters / compare ────────────────────────
# Ported from the sister pipeline (Promotion, 2026-05/06) where thresholds and
# pool sizes were tuned against a gold-standard query set — the values below
# carry those findings and should not be changed casually.

# Coverage pool: max_chunks_per_source=10 was A/B-tested (2026-05-12): lowering
# to 5 dropped a borderline source (count 3 → under the count>=3 gate) from
# substantial to peripheral. min_score=0.4 matches the local reranker's score
# distribution (0.5 consistently excluded topically relevant sources).
COVERAGE_TOP_K = 50
COVERAGE_MIN_SCORE = 0.4
COVERAGE_PER_SOURCE = 10

# Clusters pool: max_chunks_per_source=4 keeps one dominant source (a book with
# hundreds of chunks) from filling 25% of the pool and skewing the cluster map.
CLUSTERS_TOP_K = 40
CLUSTERS_PER_SOURCE = 4


def _coverage_aggregate(hits: list[dict], min_score: float,
                        coverage_mode: str) -> dict:
    """Group search hits per source and split substantial vs. peripheral.

    coverage_mode: 'broad' — substantial = count>=3 AND max_score>=min_score
    ("who writes A LOT about X?"); 'specific' — substantial = max_score>=
    min_score, ranked by max_score × (0.5 + 0.5 × max_score/count) so a narrow
    specialist source with one excellent hit outranks a broad one with many
    mediocre hits ("who writes FOCUSED about X?"); 'both' — both tables."""
    by_source: dict[str, dict] = {}
    for h in hits:
        src = h.get("source_file", "?")
        info = by_source.setdefault(src, {
            "count": 0, "max_score": 0.0, "sample": None, "chapters": set(),
        })
        score = h.get("rerank_score")
        score = float(score if score is not None else h.get("score", 0.0))
        info["count"] += 1
        if score >= info["max_score"] or info["sample"] is None:
            info["max_score"] = max(info["max_score"], score)
            info["sample"] = h
        chapter = (h.get("chapter") or "").strip()
        if chapter:
            info["chapters"].add(chapter)

    def entry(src, info):
        return {"source": src, "count": info["count"],
                "max_score": info["max_score"], "sample": info["sample"],
                "chapters": sorted(info["chapters"])}

    broad_sub, broad_peri = [], []
    for src, info in by_source.items():
        e = entry(src, info)
        if info["count"] >= 3 and info["max_score"] >= min_score:
            broad_sub.append(e)
        else:
            broad_peri.append(e)
    broad_sub.sort(key=lambda e: (-e["count"], -e["max_score"]))
    broad_peri.sort(key=lambda e: (-e["max_score"], -e["count"]))

    specific_sub, specific_peri = [], []
    for src, info in by_source.items():
        spec_factor = 0.5 + 0.5 * (info["max_score"] / max(info["count"], 1))
        final = info["max_score"] * spec_factor
        e = entry(src, info)
        (specific_sub if info["max_score"] >= min_score
         else specific_peri).append((final, e))
    specific_sub.sort(key=lambda x: -x[0])
    specific_peri.sort(key=lambda x: -x[0])

    result = {"total_sources": len(by_source), "total_chunks": len(hits),
              "coverage_mode": coverage_mode}
    if coverage_mode == "specific":
        result["substantial"] = [e for _, e in specific_sub]
        result["peripheral"] = [e for _, e in specific_peri]
    else:
        result["substantial"] = broad_sub
        result["peripheral"] = broad_peri
        if coverage_mode == "both":
            result["substantial_specific"] = [e for _, e in specific_sub]
    return result


def _coverage_lines(title: str, entries: list[dict], project: str) -> list[str]:
    from brag.http_bridge import pdf_link
    lines = [f"### {title} ({len(entries)})", ""]
    for e in entries:
        s = e["sample"] or {}
        page = s.get("page_start", "")
        link = (pdf_link(s.get("rel_path", ""), page, project)
                if s.get("rel_path") else "")
        head = (f"- [**{e['source']}** — S. {page}](<{link}>)" if link
                else f"- **{e['source']}**")
        lines.append(f"{head} — {e['count']} Treffer, max. Score "
                     f"{e['max_score']:.3f}")
        if e["chapters"]:
            lines.append(f"  Kapitel: {'; '.join(e['chapters'][:6])}")
        sample_text = ((s.get("text") or "").replace("\n", " ").strip())[:220]
        if sample_text:
            lines.append(f"  > {sample_text}…")
    lines.append("")
    return lines


def coverage_text(query: str, top_k: int = 0, min_score: float = 0.0,
                  coverage_mode: str = "broad", project: str = "",
                  collection_name: str | None = None) -> str:
    """'Stand der Forschung': aggregate hits PER SOURCE instead of a flat list
    and split substantial vs. peripheral coverage of the topic."""
    coverage_mode = (coverage_mode or "broad").strip().lower()
    if coverage_mode not in ("broad", "specific", "both"):
        return ("Unbekannter coverage_mode — erwarte 'broad' (wer schreibt viel "
                "zu X), 'specific' (wer schreibt fokussiert zu X) oder 'both'.")
    hits = run_search(query, top_k=(top_k or COVERAGE_TOP_K),
                      max_chunks_per_source=COVERAGE_PER_SOURCE,
                      collection_name=collection_name)
    if not hits:
        return NO_HITS_MSG
    agg = _coverage_aggregate(hits, min_score or COVERAGE_MIN_SCORE,
                              coverage_mode)
    lines = [f"## Quellen-Abdeckung: \"{query}\"", "",
             f"{agg['total_chunks']} Treffer aus {agg['total_sources']} Quellen "
             f"analysiert (Modus: {coverage_mode})", ""]
    label = ("Substanziell (fokussiert)" if coverage_mode == "specific"
             else "Substanziell (viel zum Thema)")
    lines += _coverage_lines(label, agg["substantial"], project)
    if "substantial_specific" in agg:
        lines += _coverage_lines("Substanziell (fokussiert)",
                                 agg["substantial_specific"], project)
    lines += _coverage_lines("Peripher (Randtreffer)", agg["peripheral"],
                             project)
    return "\n".join(lines)


def _kmeans(X, k: int, iters: int = 25, seed: int = 42):
    """Deterministic spherical k-means (numpy only — no sklearn dependency).
    X must be L2-normalized; k-means++ seeding with a fixed RandomState keeps
    results reproducible across runs."""
    import numpy as np
    rng = np.random.RandomState(seed)
    centers = [X[rng.randint(len(X))]]
    for _ in range(1, k):
        d2 = np.min([((X - c) ** 2).sum(axis=1) for c in centers], axis=0)
        total = d2.sum()
        idx = rng.choice(len(X), p=d2 / total) if total > 0 else rng.randint(len(X))
        centers.append(X[idx])
    C = np.array(centers)
    labels = np.zeros(len(X), dtype=int)
    for _ in range(iters):
        labels = ((X[:, None, :] - C[None, :, :]) ** 2).sum(-1).argmin(axis=1)
        newC = np.array([X[labels == j].mean(axis=0) if np.any(labels == j)
                         else C[j] for j in range(k)])
        if np.allclose(newC, C):
            break
        C = newC
    return labels, C


def clusters_text(query: str, top_k: int = 0, n_clusters: int = 5,
                  project: str = "", collection_name: str | None = None) -> str:
    """Explorative topic map: k-means over the hits' dense embeddings — which
    sub-aspects does the corpus hold on this topic, and who writes on each?"""
    import numpy as np
    from brag.http_bridge import pdf_link
    hits = run_search(query, top_k=(top_k or CLUSTERS_TOP_K),
                      max_chunks_per_source=CLUSTERS_PER_SOURCE,
                      collection_name=collection_name, with_vectors=True)
    valid = [h for h in hits if h.get("_vector")]
    if len(valid) < max(4, n_clusters):
        return (f"Nur {len(valid)} Treffer mit Vektoren — zu wenig für eine "
                f"Themen-Map. Query verbreitern oder n_clusters senken.")
    X = np.array([h["_vector"] for h in valid], dtype=float)
    X = X / np.linalg.norm(X, axis=1, keepdims=True)  # spherical k-means
    # Auto-k: at least ~4 points per cluster, so 8 hits never yield 5 singletons.
    k = min(n_clusters, max(2, len(valid) // 4))
    labels, C = _kmeans(X, k)

    clusters = []
    for j in range(k):
        members = [i for i in range(len(valid)) if labels[i] == j]
        if not members:
            continue
        dists = [(i, float(((X[i] - C[j]) ** 2).sum())) for i in members]
        rep = valid[min(dists, key=lambda t: t[1])[0]]
        src_counts: dict[str, int] = {}
        chapters: set[str] = set()
        for i in members:
            h = valid[i]
            src_counts[h.get("source_file", "?")] = (
                src_counts.get(h.get("source_file", "?"), 0) + 1)
            ch = (h.get("chapter") or "").strip()
            if ch:
                chapters.add(ch)
        clusters.append({"n": len(members), "sources": src_counts,
                         "chapters": sorted(chapters), "rep": rep})
    clusters.sort(key=lambda c: -c["n"])

    lines = [f"## Themen-Map: \"{query}\"", "",
             f"{len(valid)} Treffer in {len(clusters)} Cluster gruppiert "
             "(semantische Nähe im Embedding-Raum)", ""]
    for ci, c in enumerate(clusters, 1):
        rep = c["rep"]
        page = rep.get("page_start", "")
        link = (pdf_link(rep.get("rel_path", ""), page, project)
                if rep.get("rel_path") else "")
        srcs = sorted(c["sources"].items(), key=lambda kv: -kv[1])
        lines.append(f"### Cluster {ci} — {c['n']} Treffer aus "
                     f"{len(c['sources'])} Quellen")
        rep_head = f"**{rep.get('source_file', '?')}** — S. {page}"
        lines.append(f"Repräsentativ: [{rep_head}](<{link}>)" if link
                     else f"Repräsentativ: {rep_head}")
        rep_text = ((rep.get("text") or "").replace("\n", " ").strip())[:260]
        lines.append(f"> {rep_text}…")
        lines.append("Quellen: " + ", ".join(f"`{s}` ({n})" for s, n in srcs[:6]))
        if c["chapters"]:
            lines.append("Kapitel: " + "; ".join(c["chapters"][:5]))
        lines.append("")
    return "\n".join(lines)


def compare_positions_text(query: str, sources: list[str],
                           top_k_per_source: int = 3, project: str = "",
                           collection_name: str | None = None) -> str:
    """Side-by-side: what do THESE specific sources say about THIS topic?
    One search per source (source_file filter, NFC/NFD-robust via
    source_key_variants), rendered as one comparison block."""
    sources = [s for s in (sources or []) if str(s).strip()]
    if len(sources) < 2:
        return ("Gib mindestens 2 Quellen an (source_file-Schlüssel aus "
                "list_sources()).")
    if len(sources) > 7:
        return (f"{len(sources)} Quellen — bitte höchstens 7 für einen "
                "lesbaren Vergleich.")
    found: dict[str, list[dict]] = {}
    missing: list[str] = []
    for src in sources:
        try:
            hits = run_search(query, top_k=top_k_per_source,
                              max_chunks_per_source=top_k_per_source,
                              source_file=str(src),
                              collection_name=collection_name)
        except Exception:  # noqa: BLE001 — one bad source must not kill the compare
            hits = []
        if hits:
            found[src] = hits
        else:
            missing.append(src)

    lines = [f"## Positions-Vergleich: \"{query}\"", "",
             f"Gesucht in **{len(sources)} Quellen**, gefunden in "
             f"**{len(found)}** (Top-{top_k_per_source} Treffer pro Quelle)", ""]
    for i, src in enumerate(sources, 1):
        if src not in found:
            continue
        lines.append(f"### [{i}] {str(src)[:80]}")
        lines.append("")
        for j, h in enumerate(found[src], 1):
            lines.append(format_hit(j, h, project=project))
    if missing:
        lines.append(f"### Nicht gefunden ({len(missing)})")
        lines += [f"- {src} — keine Treffer für '{query}' in dieser Quelle"
                  for src in missing]
        if not found:
            lines.append("")
            lines.append(
                "> **Diagnose:** Keine der angefragten Quellen enthält Treffer. "
                "Mögliche Ursachen: (a) Tippfehler im source_file-Schlüssel — "
                "über list_sources() prüfen; (b) die Quellen behandeln das Thema "
                "nicht — Query umformulieren oder andere Quellen wählen.")
    return "\n".join(lines)


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
