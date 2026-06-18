"""Hybrid search: dense + BM25 prefetch → RRF fusion → cross-encoder
reranking → source diversity.

Parameter defaults (prefetch 150, fusion limit 80, no rerank score floor)
were validated against a retrieval gold standard in the originating system.
Notably: cross-encoder sigmoid scores are NOT absolutely calibrated — any
hard score floor cuts legitimate top hits on factual queries, so scores are
reported transparently instead of filtered.
"""

from brag import config
from brag.embeddings import get_embedder
from brag.embeddings.sparse import embed_sparse_query

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(config.RERANKER_MODEL)
    return _reranker


def _build_filter(doc_type=None, chunk_type=None, year_min=None, year_max=None,
                  author=None, source_file=None, meta=None):
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
        must.append(FieldCondition(key="year_num", range=Range(
            gte=int(year_min) if year_min else None,
            lte=int(year_max) if year_max else None,
        )))
    # User-defined metadata fields from _meta.txt (e.g. project, course)
    for key, value in (meta or {}).items():
        must.append(FieldCondition(key=key, match=MatchValue(value=value)))
    return Filter(must=must) if must else None


def search(query: str, top_k: int = None, reranking: bool = None,
           max_chunks_per_source: int = None, **filters) -> list[dict]:
    """Run hybrid search, return ranked hits as plain dicts."""
    from qdrant_client.models import FusionQuery, Prefetch
    from brag import storage

    top_k = top_k or config.DEFAULT_TOP_K
    if reranking is None:
        reranking = config.RERANK_ENABLED
    if max_chunks_per_source is None:
        max_chunks_per_source = config.MAX_CHUNKS_PER_SOURCE

    embedder = get_embedder()
    dense_q = embedder.embed_query(query)
    sparse_q = embed_sparse_query(query)
    qfilter = _build_filter(**filters)

    client = storage.get_client()
    try:
        result = client.query_points(
            collection_name=config.COLLECTION_NAME,
            prefetch=[
                Prefetch(query=dense_q, using=config.DENSE_VECTOR,
                         limit=config.RERANK_PREFETCH, filter=qfilter),
                Prefetch(query=sparse_q, using=config.SPARSE_VECTOR,
                         limit=config.RERANK_PREFETCH, filter=qfilter),
            ],
            query=FusionQuery(fusion="rrf"),
            limit=config.RERANK_FUSION_LIMIT,
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
        scores = _get_reranker().predict(pairs)
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        candidates.sort(key=lambda c: c["rerank_score"], reverse=True)

    # Source diversity: cap hits per source so one book cannot fill the list
    hits, per_source = [], {}
    for c in candidates:
        src = c.get("source_file", "")
        if per_source.get(src, 0) >= max_chunks_per_source:
            continue
        per_source[src] = per_source.get(src, 0) + 1
        hits.append(c)
        if len(hits) >= top_k:
            break
    return hits
