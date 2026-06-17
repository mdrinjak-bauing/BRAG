"""Qdrant access: client factory, collection setup, deletion helpers."""

from asb import config


def get_client():
    from qdrant_client import QdrantClient
    return QdrantClient(url=config.QDRANT_URL)


def ensure_collection(client=None):
    """Create the hybrid collection if missing.

    Sparse vectors get Modifier.IDF from day one — BM25 without IDF silently
    degrades to TF-only scoring (a bug that survived four weeks unnoticed in
    the originating system).
    """
    from qdrant_client.models import (
        Distance, Modifier, SparseIndexParams, SparseVectorParams, VectorParams,
    )

    own_client = client is None
    client = client or get_client()
    existing = {c.name for c in client.get_collections().collections}
    if config.COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=config.COLLECTION_NAME,
            vectors_config={
                config.DENSE_VECTOR: VectorParams(
                    size=config.EMBEDDING_DIM, distance=Distance.COSINE
                ),
            },
            sparse_vectors_config={
                config.SPARSE_VECTOR: SparseVectorParams(
                    index=SparseIndexParams(on_disk=False),
                    modifier=Modifier.IDF,
                ),
            },
            on_disk_payload=True,
        )
        for field, schema in [
            ("source_file", "keyword"), ("doc_type", "keyword"),
            ("chunk_type", "keyword"), ("author", "keyword"),
            ("year", "keyword"), ("year_num", "integer"),
            ("page_start", "integer"),
        ]:
            client.create_payload_index(
                collection_name=config.COLLECTION_NAME,
                field_name=field, field_schema=schema,
            )
    if own_client:
        client.close()


def delete_chunks_by_source(client, source_file: str) -> int:
    """Remove all chunks of one source. Returns the number deleted."""
    from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchAny

    flt = Filter(must=[FieldCondition(
        key="source_file", match=MatchAny(any=config.source_key_variants(source_file)),
    )])
    count = client.count(config.COLLECTION_NAME, count_filter=flt, exact=True).count
    if count:
        client.delete(
            collection_name=config.COLLECTION_NAME,
            points_selector=FilterSelector(filter=flt),
        )
    return count


def list_corpus_sources(client) -> set[str]:
    """All source_file values currently in the collection (NFC-normalized)."""
    sources: set[str] = set()
    offset = None
    while True:
        points, offset = client.scroll(
            config.COLLECTION_NAME, limit=1000, offset=offset,
            with_payload=["source_file"], with_vectors=False,
        )
        for p in points:
            sf = (p.payload or {}).get("source_file")
            if sf:
                sources.add(config.normalize_source_key(sf))
        if not offset:
            break
    return sources
