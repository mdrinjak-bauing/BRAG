"""Qdrant access: client factory, collection setup, deletion helpers."""

from brag import config


def get_client():
    from qdrant_client import QdrantClient
    return QdrantClient(url=config.QDRANT_URL)


def ensure_collection(client=None):
    """Create the hybrid collection if missing.

    Sparse vectors get Modifier.IDF from day one — BM25 without IDF silently
    degrades to TF-only scoring (a subtle, easy-to-miss bug).
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


def delete_chunks_by_source(client, source_file: str,
                            exclude_ids: set | None = None) -> int:
    """Remove chunks of one source. Returns the number actually deleted.

    With exclude_ids set, the points carrying those ids are spared — this is the
    re-ingest case: the new chunks have already been upserted under deterministic
    ids, and only the OLD, now-orphaned chunks (boundaries shifted, so their ids
    are no longer produced) must be removed. Excluding the fresh ids means a
    crash between upsert and delete can leave at worst harmless orphans, never a
    half-deleted document.
    """
    from qdrant_client.models import (
        FieldCondition, Filter, FilterSelector, HasIdCondition, MatchAny,
    )

    must_not = []
    if exclude_ids:
        must_not.append(HasIdCondition(has_id=list(exclude_ids)))
    flt = Filter(
        must=[FieldCondition(
            key="source_file",
            match=MatchAny(any=config.source_key_variants(source_file)),
        )],
        must_not=must_not or None,
    )
    count = client.count(config.COLLECTION_NAME, count_filter=flt, exact=True).count
    if count:
        client.delete(
            collection_name=config.COLLECTION_NAME,
            points_selector=FilterSelector(filter=flt),
        )
    return count


def patch_source_metadata(client, source_file: str, payload: dict) -> int:
    """Update the filename-derived payload fields (source_file, author, year,
    doc_type, rel_path, custom fields) for all chunks of a source IN PLACE —
    no re-embedding. Used when a file is renamed/moved but its content is
    unchanged. Returns the number of points updated."""
    from qdrant_client.models import FieldCondition, Filter, MatchAny

    # NFC/NFD/raw triple-probe (consistent with delete/search/inspect): a
    # single-NFC MatchValue silently misses payloads written under a different
    # normalization, so the rename would wrongly fall back to a full re-ingest.
    flt = Filter(must=[FieldCondition(
        key="source_file", match=MatchAny(any=config.source_key_variants(source_file)),
    )])
    count = client.count(config.COLLECTION_NAME, count_filter=flt, exact=True).count
    if not count:
        return 0
    # set_payload only MERGES — custom fields from the OLD folder's _meta.txt
    # that the new location no longer defines would otherwise survive the move
    # (e.g. a stale `project=A` after moving into project B, leaking across the
    # project/course filter). Remove those stale custom keys explicitly.
    _PRESERVE = {
        "text", "context", "chunk_type", "page_start", "page_end",
        "chapter", "section", "language", "chunk_id", "ingest_timestamp",
    }
    points, _ = client.scroll(
        config.COLLECTION_NAME, scroll_filter=flt, limit=1,
        with_payload=True, with_vectors=False,
    )
    if points:
        existing = set((points[0].payload or {}).keys())
        stale = [k for k in existing if k not in payload and k not in _PRESERVE]
        if stale:
            client.delete_payload(
                collection_name=config.COLLECTION_NAME, keys=stale, points=flt,
            )
    client.set_payload(
        collection_name=config.COLLECTION_NAME, payload=payload, points=flt,
    )
    return count


def orphaned_collections(client) -> list[str]:
    """asb_* collections OTHER than the active one — left behind when the user
    changed the embedding backend/dimension (COLLECTION_NAME encodes both, so a
    change targets a NEW collection and the old one lingers, consuming disk).
    Returned for surfacing only; never auto-deleted (dropping a collection is
    destructive and the user may be mid-migration)."""
    try:
        names = [c.name for c in client.get_collections().collections]
    except Exception:  # noqa: BLE001 — best-effort housekeeping, never fatal
        return []
    return sorted(n for n in names
                  if n.startswith("asb_") and n != config.COLLECTION_NAME)


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
