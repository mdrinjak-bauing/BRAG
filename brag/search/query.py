"""Hybrid search: dense + BM25 prefetch → RRF fusion → cross-encoder
reranking → source diversity.

Candidate breadth and how many passages the (local, CPU-bound) cross-encoder
scores are set by RERANK_PROFILE (config.py): the default "eco" preset loads
160 candidates (80 + 80) and reranks the top 40 — gentle on consumer CPUs;
"balanced"/"full" rerank more, "off" skips reranking entirely. The "no hard
score floor" design stands regardless: cross-encoder sigmoid scores are NOT
absolutely calibrated — any floor cuts legitimate top hits on factual queries,
so scores are reported transparently instead of filtered.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from brag import config
from brag.embeddings import get_embedder
from brag.embeddings.sparse import embed_sparse_query

if TYPE_CHECKING:
    from qdrant_client.models import Filter

_reranker = None
# The bridge serves searches on multiple threads (one per concurrent project
# connector). Build the reranker once under a double-checked lock so concurrent
# first-calls don't construct N copies, and serialize the CPU forward pass so
# parallel searches queue instead of thrashing the CPU / multiplying RAM.
_INIT_LOCK = threading.Lock()
_RERANK_LOCK = threading.Lock()


def _get_reranker():
    global _reranker
    if _reranker is None:
        with _INIT_LOCK:
            if _reranker is None:
                from sentence_transformers import CrossEncoder
                kwargs = ({"revision": config.RERANKER_REVISION}
                          if config.RERANKER_REVISION else {})
                _reranker = CrossEncoder(config.RERANKER_MODEL, **kwargs)
    return _reranker


def _build_filter(doc_type=None, chunk_type=None, year_min=None, year_max=None,
                  author=None, source_file=None, meta=None) -> Filter | None:
    """Build a Qdrant Filter from the given constraints, or None if none apply."""
    from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, Range
    must = []
    if doc_type:
        must.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_type)))
    if chunk_type:
        must.append(FieldCondition(key="chunk_type", match=MatchValue(value=chunk_type)))
    if author:
        must.append(FieldCondition(key="author", match=MatchValue(value=author)))
    if source_file:
        # NFC/NFD/raw triple-probe: a single-NFC filter misses payloads written
        # under a different normalization (snapshot restore, cross-OS import).
        must.append(FieldCondition(
            key="source_file",
            match=MatchAny(any=config.source_key_variants(source_file)),
        ))
    if year_min or year_max:
        # Coerce defensively: a non-numeric year (malformed call) must drop the
        # bound, not raise and crash the whole search.
        def _as_year(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
        gte = _as_year(year_min) if year_min else None
        lte = _as_year(year_max) if year_max else None
        if gte is not None or lte is not None:
            must.append(FieldCondition(key="year_num", range=Range(gte=gte, lte=lte)))
    # User-defined metadata fields from _meta.txt (e.g. project, course)
    for key, value in (meta or {}).items():
        must.append(FieldCondition(key=key, match=MatchValue(value=value)))
    return Filter(must=must) if must else None


def _token_set(text: str) -> frozenset[str]:
    """Lowercased word-token set of a chunk, for cheap Jaccard similarity."""
    import re
    return frozenset(re.findall(r"\w+", text.lower()))


def _is_near_duplicate(text: str, accepted_tokens: list) -> bool:
    """True if `text` is a near-duplicate of an already-accepted hit.

    Token-set (Jaccard) similarity against each accepted chunk; a hit at or above
    config.DEDUP_SIMILARITY_THRESHOLD is dropped. Empty / whitespace-only text is
    NEVER treated as a duplicate (figure/table chunks may carry content
    elsewhere), and a threshold >= 1.0 disables the filter entirely."""
    if config.DEDUP_SIMILARITY_THRESHOLD >= 1.0:
        return False
    tokens = _token_set(text)
    if not tokens:
        return False
    for prev in accepted_tokens:
        if not prev:
            continue
        union = len(tokens | prev)
        if union and len(tokens & prev) / union >= config.DEDUP_SIMILARITY_THRESHOLD:
            return True
    return False


def _diversify(candidates: list[dict], top_k: int, max_per_source: int) -> list[dict]:
    """Pick up to top_k hits: cap per source and drop near-duplicates, then
    BACKFILL the remaining slots from candidates that only hit the per-source cap
    (never from true duplicates), so a source-skewed pool still returns ~top_k
    instead of a short list (RET-F02). The diverse hits keep their reranked order
    and the backfill is appended in reranked order, so when the pool already
    yields top_k diverse hits the result is identical to a plain per-source cap."""
    hits, per_source, accepted_tokens, overflow = [], {}, [], []
    for c in candidates:
        if _is_near_duplicate(c.get("text", ""), accepted_tokens):
            continue
        src = c.get("source_file", "")
        if per_source.get(src, 0) >= max_per_source:
            overflow.append(c)  # not a dup, only over the per-source cap → backfill
            continue
        per_source[src] = per_source.get(src, 0) + 1
        accepted_tokens.append(_token_set(c.get("text", "")))
        hits.append(c)
        if len(hits) >= top_k:
            return hits
    for c in overflow:
        if _is_near_duplicate(c.get("text", ""), accepted_tokens):
            continue
        accepted_tokens.append(_token_set(c.get("text", "")))
        hits.append(c)
        if len(hits) >= top_k:
            break
    return hits


# Task presets → (top_k, max_per_source). "normal" uses the config defaults; an
# explicit top_k / max_chunks_per_source argument still overrides the preset.
_MODE_PRESETS = {
    "precise": (8, 2),    # a pinpoint fact (+ a little cross-checking)
    "review": (50, 2),    # broad literature survey: wide net, few per source
    "deep": (30, 15),     # dig into one/few specific reports (with source_file)
}


def search(query: str, top_k: int | None = None, reranking: bool | None = None,
           max_chunks_per_source: int | None = None, mode: str = "normal",
           collection_name: str | None = None, **filters) -> list[dict]:
    """Run hybrid search, return ranked hits as plain dicts.

    `mode` picks task-appropriate breadth/depth (precise/normal/review/deep); an
    explicit top_k or max_chunks_per_source overrides the preset. collection_name
    defaults to the single-project config.COLLECTION_NAME; the multi-project bridge
    passes a per-project collection so each project searches only its own data."""
    from qdrant_client.models import FusionQuery, Prefetch
    from brag import storage

    collection_name = collection_name or config.COLLECTION_NAME
    preset = _MODE_PRESETS.get((mode or "normal").strip().lower())
    base_top_k = preset[0] if preset else config.DEFAULT_TOP_K
    base_mps = preset[1] if preset else config.MAX_CHUNKS_PER_SOURCE
    if not top_k or top_k <= 0:
        top_k = base_top_k
    # Large top_k stays deliberately supported (prefetch/fusion scale with it);
    # clamp only against an absurd value that would make Qdrant pathological.
    top_k = min(top_k, config.MAX_TOP_K)
    if reranking is None:
        reranking = config.RERANK_ENABLED
    if max_chunks_per_source is None or max_chunks_per_source <= 0:
        max_chunks_per_source = base_mps

    embedder = get_embedder()
    dense_q = embedder.embed_query(query)
    sparse_q = embed_sparse_query(query)
    qfilter = _build_filter(**filters)

    # A large top_k must not be silently capped by the rerank/fusion presets:
    # fetch at least top_k candidates per vector and fuse at least top_k.
    prefetch_limit = max(top_k, config.RERANK_PREFETCH)
    fusion_limit = max(top_k, config.RERANK_FUSION_LIMIT)

    client = storage.get_client()
    try:
        result = client.query_points(
            collection_name=collection_name,
            prefetch=[
                Prefetch(query=dense_q, using=config.DENSE_VECTOR,
                         limit=prefetch_limit, filter=qfilter),
                Prefetch(query=sparse_q, using=config.SPARSE_VECTOR,
                         limit=prefetch_limit, filter=qfilter),
            ],
            query=FusionQuery(fusion="rrf"),
            limit=fusion_limit,
            with_payload=True,
        )
    finally:
        client.close()

    candidates = [
        {"score": float(p.score), "rerank_score": None, **(p.payload or {})}
        for p in result.points
    ]

    if reranking and candidates:
        pairs = [(query, c.get("context", "") + "\n" + c.get("text", ""))
                 for c in candidates]
        with _RERANK_LOCK:
            scores = _get_reranker().predict(pairs, batch_size=config.RERANK_BATCH_SIZE)
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        candidates.sort(key=lambda c: c["rerank_score"], reverse=True)

    # Source diversity: cap hits per source so one book cannot fill the list and
    # drop cross-source near-duplicates — then backfill so a source-skewed pool
    # still returns ~top_k instead of a short answer (RET-F02).
    return _diversify(candidates, top_k, max_chunks_per_source)
