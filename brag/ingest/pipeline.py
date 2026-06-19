"""Ingest pipeline orchestration.

Stages: extract (Docling) → contextualize (LLM) → dense + sparse embedding
→ idempotent upsert into Qdrant → literature note → ingest log.

Failure principles (hard-won lessons from the originating system):
- a chunk whose embedding fails is SKIPPED and logged, never stored as a
  zero vector (zero vectors are undefined in cosine space = silent data loss)
- on re-ingest the new points are upserted first (deterministic ids overwrite
  identical chunks); stale chunks of the same source are then deleted, so a
  crash mid-write can only leave harmless orphans, never a half-deleted document
- post-stage failures (note writing, logging) never fail the ingest
"""

import json
from datetime import date, datetime
from pathlib import Path

from brag import config, storage
from brag.embeddings import get_embedder
from brag.embeddings.sparse import embed_sparse_documents
from brag.ingest.contextualize import contextualize
from brag.ingest.extract import extract
from brag.ingest.notes import write_note

UPSERT_BATCH = 100

# A document that ingested only partially (some chunks failed to embed, e.g. a
# transient cloud rate-limit burst) is re-driven on watcher startup so the
# missing pages are retried — but only this many times, so a chunk that fails
# permanently doesn't re-ingest the whole document on every single startup.
PARTIAL_RETRY_LIMIT = 3


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


def _mark_not_indexed(path: Path) -> None:
    """Make a non-indexable document VISIBLE to the user. A scanned PDF without
    a text layer yields zero chunks and would otherwise vanish silently from the
    corpus — the user keeps believing it is searchable. We append one line per
    affected file to NICHT-INDEXIERT.md in the wissensspeicher root (next to
    sources/notes, where the user will actually see it). Idempotent: a file
    already listed is not added again. Fully best-effort — never crashes the
    ingest (the on-screen log line is printed regardless by the caller)."""
    try:
        marker = config.VAULT / "NICHT-INDEXIERT.md"
        name = config.normalize_source_key(path.name)
        existing = ""
        if marker.exists():
            existing = marker.read_text(encoding="utf-8")
            if name in existing:
                return
        header = (
            "# Nicht indexierte Dokumente\n\n"
            "Diese Dateien konnten nicht in den Wissensspeicher aufgenommen "
            "werden und sind daher **nicht durchsuchbar**.\n\n"
        )
        config.VAULT.mkdir(parents=True, exist_ok=True)
        with open(marker, "a", encoding="utf-8") as f:
            if not existing:
                f.write(header)
            f.write(
                f"- `{name}` — {date.today().isoformat()} — vermutlich "
                "gescanntes PDF ohne Textebene, nicht durchsuchbar; "
                "ggf. OCR anwenden und erneut ablegen\n"
            )
    except Exception as e:  # noqa: BLE001 — marking must never fail the ingest
        print(f"  could not write NICHT-INDEXIERT.md marker (non-fatal): {e}")


def _append_ingest_log(source_file: str, path: Path, n_chunks: int,
                       partial: bool = False, attempts: int = 1) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "source_file": source_file, "file": str(path.name),
        "chunks": n_chunks, "ingested_at": datetime.now().isoformat(),
        "collection": config.COLLECTION_NAME,
        "partial": partial, "attempts": attempts,
    }
    with open(config.INGEST_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _ingest_log_states() -> dict[str, dict]:
    """Latest ingest-log entry per source_file (the log is append-only, so the
    last line for a source wins). Used to find partially-ingested documents."""
    states: dict[str, dict] = {}
    try:
        with open(config.INGEST_LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                sf = e.get("source_file")
                if sf:
                    states[sf] = e
    except FileNotFoundError:
        pass
    return states


def sources_needing_retry() -> set[str]:
    """Sources whose most recent ingest was partial and still under the retry
    limit — the watcher re-drives these so chunks that failed transiently get
    another chance, instead of leaving pages missing from the index forever."""
    return {
        sf for sf, e in _ingest_log_states().items()
        if e.get("partial") and e.get("attempts", 1) < PARTIAL_RETRY_LIMIT
    }


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
        # Make this visible to the user — an empty extraction would otherwise
        # leave the document silently absent from the searchable corpus.
        _mark_not_indexed(path)
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
        # Heavy partial failure (typically a sustained rate limit or outage on
        # cloud embeddings) must NOT be frozen as a partial index. Abort before
        # upserting so nothing lands in the corpus and the document is retried
        # on the next watcher start — instead of silently missing pages forever.
        if skipped >= max(3, len(chunks) // 5):
            print("  too many embedding failures — aborting so this document is "
                  "retried later (no partial index)")
            return False

    chunks = [c for c, _ in paired]
    dense = [v for _, v in paired]
    sparse = embed_sparse_documents([c.embedding_text() for c in chunks])

    print("  [4/4] storing in Qdrant...")
    from qdrant_client.models import PointStruct
    client = storage.get_client()
    try:
        storage.ensure_collection(client)
        # Upsert the NEW points FIRST. Deterministic ids (c.qdrant_id()) mean
        # identical chunks overwrite idempotently. Only after every point is
        # server-side confirmed (wait=True) do we delete the now-stale old
        # chunks of this source — so a crash between the two steps leaves at
        # worst harmless orphans, never a half-deleted document.
        points = [
            PointStruct(
                id=c.qdrant_id(),
                vector={config.DENSE_VECTOR: dv, config.SPARSE_VECTOR: sv},
                payload=c.payload(),
            )
            for c, dv, sv in zip(chunks, dense, sparse)
        ]
        for start in range(0, len(points), UPSERT_BATCH):
            client.upsert(
                config.COLLECTION_NAME,
                points[start : start + UPSERT_BATCH],
                wait=True,
            )
        new_ids = {p.id for p in points}
        removed = storage.delete_chunks_by_source(
            client, chunks[0].source_file, exclude_ids=new_ids
        )
        if removed:
            print(f"  removed {removed} stale chunks of this source (idempotent re-ingest)")
    finally:
        client.close()

    # Record whether this ingest was complete or partial so a partially-indexed
    # document is re-driven on the next watcher start (bounded by attempts)
    # rather than silently keeping missing pages forever.
    partial = skipped > 0
    prev = _ingest_log_states().get(chunks[0].source_file)
    attempts = (prev.get("attempts", 1) + 1) if (partial and prev and prev.get("partial")) else 1
    try:
        write_note(chunks)
        _append_ingest_log(chunks[0].source_file, path, len(chunks),
                           partial=partial, attempts=attempts)
    except Exception as e:  # noqa: BLE001 — post-stages never fail the ingest
        print(f"  note/log writing failed (non-fatal): {e}")

    if partial:
        print(f"  done: {len(chunks)} chunks indexed "
              f"({skipped} skipped — will retry, attempt {attempts}/{PARTIAL_RETRY_LIMIT})\n")
    else:
        print(f"  done: {len(chunks)} chunks indexed\n")
    return True


def remove_source(source_file: str) -> int:
    """Remove a deleted document from the index and clean up its note."""
    from brag.ingest.notes import delete_note
    client = storage.get_client()
    try:
        n = storage.delete_chunks_by_source(client, source_file)
    finally:
        client.close()
    delete_note(source_file)
    return n


def rename_source(old_source_file: str, new_path: Path) -> int:
    """Lightweight rename of an already-indexed source: the content is the same,
    only the name/location changed, so patch the filename-derived metadata on
    the existing chunks (no re-embedding) and move the literature note.

    Returns the number of chunks updated, or 0 if the source was not indexed —
    in which case the caller should fall back to a full ingest.
    """
    from brag.ingest.extract import derive_file_metadata, metadata_payload
    from brag.ingest.notes import rename_note

    payload = metadata_payload(new_path)
    client = storage.get_client()
    try:
        n = storage.patch_source_metadata(client, old_source_file, payload)
    finally:
        client.close()
    if n:
        try:
            rename_note(old_source_file, derive_file_metadata(new_path))
        except Exception as e:  # noqa: BLE001 — the note is non-critical
            print(f"  note rename failed (non-fatal): {e}")
    return n


def reapply_folder_metadata(folder: Path) -> int:
    """Re-derive and patch the metadata of every already-indexed document under
    `folder` — without re-embedding. Used when a `_meta.txt` is added, edited or
    removed: the project/client/custom fields it defines must then propagate to
    documents that were indexed BEFORE the change (which the watcher otherwise
    never revisits, because the document files themselves did not change).

    Reuses the rename path with the same path in and out: rename_source re-reads
    the full `_meta.txt` inheritance chain via metadata_payload and patches the
    payload in place. Best-effort and idempotent; never raises.
    Returns the number of documents whose metadata was refreshed."""
    updated = 0
    try:
        for p in sorted(folder.rglob("*")):
            if (p.is_file()
                    and p.suffix.lower() in config.SUPPORTED_SUFFIXES
                    and not p.name.startswith(".")
                    and not any(part in config.WATCH_IGNORE_DIRS for part in p.parts)):
                try:
                    if rename_source(config.source_key_from_path(p), p):
                        updated += 1
                except Exception as e:  # noqa: BLE001 — one bad file must not stop the rest
                    print(f"  metadata re-apply failed for {p.name}: {str(e)[:80]}")
    except Exception as e:  # noqa: BLE001 — re-apply must never crash the watcher
        print(f"  folder metadata re-apply failed for {folder}: {str(e)[:80]}")
    return updated


def index_passage(topic: str, text: str, source: str, page: str = "",
                  note: str = "") -> bool:
    """Embed a passage the user saved during a chat so it becomes findable by
    the semantic search in any later chat — tagged chunk_type='passage' so it
    stays clearly distinguishable from primary sources. Best-effort: never
    raises, because the file on disk is already saved and a failed index must
    not turn the save_passage tool call into an error."""
    import re

    from qdrant_client.models import PointStruct

    from brag.embeddings import get_embedder
    from brag.embeddings.sparse import embed_sparse_documents
    from brag.ingest.extract import Chunk

    try:
        slug = re.sub(r"[^\w\-]+", "_", topic.strip()).strip("_") or "general"
        body = text.strip()
        if note.strip():
            body += f"\n\nNote: {note.strip()}"
        ref = source + (f", p. {page}" if str(page).strip() else "")
        page_no = int(page) if str(page).strip().isdigit() else 0
        chunk = Chunk(
            text=f"[Saved passage — {topic}] (from {ref})\n\n{body}",
            chunk_type="passage", source_file=f"passage:{slug}", rel_path="",
            page_start=page_no, page_end=page_no, chapter="", section="",
            doc_type="passage", author=source or "saved passage", year="",
            language="en",
            custom_meta={"topic": topic, "from_source": source,
                         "from_page": str(page).strip()},
        )
        embedder = get_embedder()
        dense = embedder.embed_document(chunk.embedding_text())
        sparse = embed_sparse_documents([chunk.embedding_text()])[0]
        client = storage.get_client()
        try:
            storage.ensure_collection(client)
            client.upsert(config.COLLECTION_NAME, [PointStruct(
                id=chunk.qdrant_id(),
                vector={config.DENSE_VECTOR: dense, config.SPARSE_VECTOR: sparse},
                payload=chunk.payload(),
            )])
        finally:
            client.close()
        return True
    except Exception as e:  # noqa: BLE001 — indexing is best-effort
        print(f"  passage indexing failed (non-fatal): {str(e)[:80]}")
        return False
