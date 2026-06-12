"""Ingest pipeline orchestration.

Stages: extract (Docling) → contextualize (LLM) → dense + sparse embedding
→ idempotent upsert into Qdrant → literature note → ingest log.

Failure principles (hard-won lessons from the originating system):
- a chunk whose embedding fails is SKIPPED and logged, never stored as a
  zero vector (zero vectors are undefined in cosine space = silent data loss)
- old chunks of the same source are deleted before upsert, so re-ingests
  with shifted chunk boundaries leave no orphans
- post-stage failures (note writing, logging) never fail the ingest
"""

import json
from datetime import datetime
from pathlib import Path

from asb import config, storage
from asb.embeddings import get_embedder
from asb.embeddings.sparse import embed_sparse_documents
from asb.ingest.contextualize import contextualize
from asb.ingest.extract import extract
from asb.ingest.notes import write_note

UPSERT_BATCH = 100


def _log_failed_chunk(chunk, reason: str) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "chunk_id": chunk.chunk_id, "source_file": chunk.source_file,
        "page_start": chunk.page_start, "chunk_type": chunk.chunk_type,
        "text": chunk.text, "context": chunk.context, "reason": reason,
        "logged_at": datetime.now().isoformat(),
    }
    with open(config.FAILED_CHUNKS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _append_ingest_log(source_file: str, path: Path, n_chunks: int) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "source_file": source_file, "file": str(path.name),
        "chunks": n_chunks, "ingested_at": datetime.now().isoformat(),
        "collection": config.COLLECTION_NAME,
    }
    with open(config.INGEST_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def ingest(path: Path) -> bool:
    """Full ingest of one document. Returns True on success."""
    print(f"\n=== Ingest: {path.name} ===")
    if not path.exists():
        print("  file not found")
        return False

    print("  [1/4] extracting (Docling — first run downloads models)...")
    chunks, full_markdown = extract(path)
    n_text = sum(1 for c in chunks if c.chunk_type == "text")
    n_table = sum(1 for c in chunks if c.chunk_type == "table")
    n_fig = sum(1 for c in chunks if c.chunk_type == "figure")
    print(f"  {len(chunks)} chunks: {n_text} text | {n_table} tables | {n_fig} figures")
    if not chunks:
        print("  no chunks extracted — scanned PDF without text layer?")
        return False
    # Plausibility check against layout misclassification (body text
    # mistaken for headers shows up as 0 text chunks but many figures/tables)
    if n_text == 0 and (n_fig + n_table) >= 3:
        print("  WARNING: 0 text chunks — extraction looks wrong, please inspect")

    print("  [2/4] contextual retrieval...")
    chunks = contextualize(chunks, full_markdown)

    print("  [3/4] embedding (dense + sparse)...")
    embedder = get_embedder()
    paired = []
    for i, chunk in enumerate(chunks):
        try:
            vec = embedder.embed_document(chunk.embedding_text())
            paired.append((chunk, vec))
        except Exception as e:  # noqa: BLE001
            print(f"  embedding failed (p. {chunk.page_start}): {str(e)[:80]}")
            _log_failed_chunk(chunk, "embedding_failed")
        if (i + 1) % 25 == 0 or i + 1 == len(chunks):
            print(f"  dense {i + 1}/{len(chunks)}")
    if not paired:
        print("  no chunk could be embedded — aborting")
        return False
    skipped = len(chunks) - len(paired)
    if skipped:
        print(f"  {skipped} chunks skipped (see failed_chunks.jsonl)")

    chunks = [c for c, _ in paired]
    dense = [v for _, v in paired]
    sparse = embed_sparse_documents([c.embedding_text() for c in chunks])

    print("  [4/4] storing in Qdrant...")
    from qdrant_client.models import PointStruct
    client = storage.get_client()
    try:
        storage.ensure_collection(client)
        removed = storage.delete_chunks_by_source(client, chunks[0].source_file)
        if removed:
            print(f"  removed {removed} old chunks of this source (idempotent re-ingest)")
        points = [
            PointStruct(
                id=c.qdrant_id(),
                vector={config.DENSE_VECTOR: dv, config.SPARSE_VECTOR: sv},
                payload=c.payload(),
            )
            for c, dv, sv in zip(chunks, dense, sparse)
        ]
        for start in range(0, len(points), UPSERT_BATCH):
            client.upsert(config.COLLECTION_NAME, points[start : start + UPSERT_BATCH])
    finally:
        client.close()

    try:
        write_note(chunks)
        _append_ingest_log(chunks[0].source_file, path, len(chunks))
    except Exception as e:  # noqa: BLE001 — post-stages never fail the ingest
        print(f"  note/log writing failed (non-fatal): {e}")

    print(f"  done: {len(chunks)} chunks indexed\n")
    return True


def remove_source(source_file: str) -> int:
    """Remove a deleted document from the index and clean up its note."""
    from asb.ingest.notes import delete_note
    client = storage.get_client()
    try:
        n = storage.delete_chunks_by_source(client, source_file)
    finally:
        client.close()
    delete_note(source_file)
    return n
