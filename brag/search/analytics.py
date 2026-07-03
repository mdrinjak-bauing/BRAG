"""Analytic retrieval modes — coverage, topic clusters, side-by-side position comparison.

Three capabilities that go beyond a flat ranked hit list, each built on top of
search():

  - source_coverage()  — "who writes on X": aggregate the hits PER SOURCE and split
                          into substantial vs. peripheral.
  - topic_clusters()   — a topic map: K-Means over the hits' dense vectors, one
                          representative + source/chapter spread per cluster.
  - compare_positions()— put 2–7 named sources side by side for one question.

The heavy deps (numpy, scikit-learn) are imported INSIDE topic_clusters so this
module — and tools.py, which imports it — stay light to import (no model stack).
Logic is faithful to the local system; the only adaptation is BRAG's result-dict
key names (source_file, and page_start where the local DB carried extra page fields).
"""

from __future__ import annotations

from collections import defaultdict

from brag import config
from brag.search.query import search as run_search


def source_coverage(query: str, top_k: int = 50, min_score: float = 0.4,
                    mode: str = "broad", collection_name: str | None = None) -> dict:
    """Aggregate hits per source. mode:
      'broad'    — substantial = count>=3 AND max_score>=min_score (who writes A LOT);
      'specific' — substantial = max_score>=min_score, ranked by max_score x spec_factor
                   (a narrow specialist with one strong hit ranks above a broad source);
      'both'     — returns both tables (keys `substantial` = broad, `substantial_specific`).
    Returns total_sources / total_chunks_analyzed / mode and lists of
    (source_file, count, max_score, sample_text, page, chapters_list)."""
    try:
        results = run_search(query, top_k=top_k, reranking=True,
                             max_chunks_per_source=10, collection_name=collection_name)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "total_sources": 0, "substantial": [], "peripheral": []}

    by_source = defaultdict(lambda: {
        "count": 0, "max_score": 0.0, "sample": None, "page": None, "chapters": set(),
    })
    for r in results:
        sf = r.get("source_file", "<unbekannt>")
        score = float(r.get("rerank_score") or r.get("score") or 0)
        by_source[sf]["count"] += 1
        if score > by_source[sf]["max_score"]:
            by_source[sf]["max_score"] = score
            by_source[sf]["sample"] = (r.get("text") or "")[:300]
            by_source[sf]["page"] = r.get("page_start")
        ch = (r.get("chapter") or "").strip()
        if ch:
            by_source[sf]["chapters"].add(ch)

    # broad: count>=3 AND max_score>=min_score
    broad_sub, broad_peri = [], []
    for sf, info in by_source.items():
        entry = (sf, info["count"], info["max_score"], info["sample"],
                 info["page"], sorted(info["chapters"]))
        if info["count"] >= 3 and info["max_score"] >= min_score:
            broad_sub.append(entry)
        else:
            broad_peri.append(entry)
    broad_sub.sort(key=lambda x: (-x[1], -x[2]))
    broad_peri.sort(key=lambda x: (-x[2], -x[1]))

    # specific: max_score>=min_score, ranked by max_score x spec_factor in [0.5, 1.0].
    specific_sub, specific_peri = [], []
    for sf, info in by_source.items():
        spec_factor = 0.5 + 0.5 * (info["max_score"] / max(info["count"], 1))
        final_score = info["max_score"] * spec_factor
        entry = (sf, info["count"], info["max_score"], info["sample"],
                 info["page"], sorted(info["chapters"]))
        if info["max_score"] >= min_score:
            specific_sub.append((final_score, entry))
        else:
            specific_peri.append((final_score, entry))
    specific_sub.sort(key=lambda x: -x[0])
    specific_peri.sort(key=lambda x: -x[0])
    specific_sub_list = [e for _, e in specific_sub]
    specific_peri_list = [e for _, e in specific_peri]

    out = {
        "total_sources": len(by_source),
        "total_chunks_analyzed": len(results),
        "mode": mode,
    }
    if mode == "specific":
        out["substantial"] = specific_sub_list
        out["peripheral"] = specific_peri_list
    elif mode == "both":
        out["substantial"] = broad_sub
        out["substantial_specific"] = specific_sub_list
        out["peripheral"] = broad_peri
    else:
        out["substantial"] = broad_sub
        out["peripheral"] = broad_peri
    return out


def compare_positions(query: str, sources: list[str], top_k_per_source: int = 3,
                      collection_name: str | None = None) -> dict:
    """Per source, search with a source_file filter (NFC/NFD/raw triple-probe so a
    macOS-normalized stem still matches). Returns results_by_source + missing."""
    import unicodedata

    out: dict = {"query": query, "results_by_source": {}, "missing": []}
    for src in sources:
        results = []
        for variant in dict.fromkeys([
            unicodedata.normalize("NFC", src),
            unicodedata.normalize("NFD", src),
            src,
        ]):
            try:
                results = run_search(
                    query, top_k=top_k_per_source, source_file=variant,
                    reranking=True, max_chunks_per_source=top_k_per_source,
                    collection_name=collection_name,
                )
            except Exception:  # noqa: BLE001
                continue
            if results:
                break
        if results:
            out["results_by_source"][src] = results
        else:
            out["missing"].append(src)
    return out


def topic_clusters(query: str, top_k: int = 40, n_clusters: int = 5,
                   collection_name: str | None = None) -> dict:
    """Fetch top_k hits, reload their dense vectors from Qdrant, cluster via K-Means
    in the (L2-normalized -> spherical) embedding space, and return per cluster a
    representative (closest to centroid) + source/chapter distribution."""
    import numpy as np
    from sklearn.cluster import KMeans

    from brag import storage

    collection_name = collection_name or config.COLLECTION_NAME
    try:
        results = run_search(query, top_k=top_k, reranking=True,
                             max_chunks_per_source=4, collection_name=collection_name)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}

    if len(results) < n_clusters:
        return {"error": f"Nur {len(results)} Treffer — weniger als {n_clusters} Cluster"}

    point_ids = [r.get("id") for r in results if r.get("id") is not None]
    if not point_ids:
        return {"error": "Keine Point-IDs in den Treffern"}
    client = storage.get_client()
    try:
        pts_with_vec = client.retrieve(
            collection_name=collection_name, ids=point_ids,
            with_vectors=[config.DENSE_VECTOR], with_payload=False,
        )
    finally:
        client.close()

    id_to_vec = {p.id: p.vector[config.DENSE_VECTOR] for p in pts_with_vec if p.vector}
    vectors, valid_results = [], []
    for r in results:
        rid = r.get("id")
        if rid in id_to_vec:
            vectors.append(id_to_vec[rid])
            valid_results.append(r)
    if len(vectors) < n_clusters:
        return {"error": f"Nur {len(vectors)} Vektoren ladbar — weniger als {n_clusters} Cluster"}

    X = np.array(vectors)
    X = X / np.linalg.norm(X, axis=1, keepdims=True)  # L2 -> spherical K-Means
    n_clusters = min(n_clusters, max(2, len(vectors) // 4))  # ~4 points / cluster
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    clusters = []
    for cluster_id in range(n_clusters):
        members = [(i, valid_results[i]) for i in range(len(valid_results))
                   if labels[i] == cluster_id]
        if not members:
            continue
        centroid = km.cluster_centers_[cluster_id]
        rep_idx = min(((i, float(np.linalg.norm(X[i] - centroid))) for i, _ in members),
                      key=lambda x: x[1])[0]
        rep = valid_results[rep_idx]
        src_counts: dict = defaultdict(int)
        chapters_set = set()
        for _, r in members:
            src_counts[r.get("source_file", "<?>")] += 1
            ch = (r.get("chapter") or "").strip()
            if ch:
                chapters_set.add(ch)
        clusters.append({
            "cluster_id": cluster_id,
            "n_chunks": len(members),
            "n_sources": len(src_counts),
            "sources": sorted(src_counts.items(), key=lambda x: -x[1]),
            "chapters": sorted(chapters_set),
            "representative": {
                "source_file": rep.get("source_file"),
                "page": rep.get("page_start"),
                "score": rep.get("rerank_score", rep.get("score")),
                "text": (rep.get("text") or "")[:300],
            },
        })
    clusters.sort(key=lambda c: -c["n_chunks"])
    return {"total_chunks": len(valid_results), "clusters": clusters}
