"""Ingest pipeline orchestration.

Stages: extract (Docling) → contextualize (LLM) → dense + sparse embedding
→ idempotent upsert into Qdrant → literature note → ingest log.

Failure principles (hard-won over earlier iterations):
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


def _attempts_path() -> Path:
    return config.DATA_DIR / "ingest_attempts.json"


def _load_attempts() -> dict:
    try:
        return json.loads(_attempts_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save_attempts(counts: dict) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _attempts_path().write_text(json.dumps(counts), encoding="utf-8")


def _clear_attempts(source_key: str) -> None:
    """Reset a source's interrupted-attempt counter. Called on any CLEAN ingest
    return and when a source is removed, so the count only climbs across hard
    crashes (a PC reset kills us before the clean return runs)."""
    counts = _load_attempts()
    if counts.pop(source_key, None) is not None:
        _save_attempts(counts)


def _append_marker(marker_name: str, header: str, key: str, line: str,
                   label: str) -> None:
    """Append one idempotent line to a visible marker file in WissensWIKI/.

    Shared by the two user-facing markers (indexing-stopped, not-indexed). The
    marker lives in WissensWIKI/ — visible to the user but excluded from the
    corpus (is_corpus_path), so it is never itself indexed. Idempotent: if `key`
    already appears in the file, nothing is written; the `header` is written only
    when the file is first created. Best-effort: a marker write must NEVER break
    an ingest, so every error is swallowed with a non-fatal log line."""
    try:
        marker = config.WISSENSWIKI_DIR / marker_name
        existing = marker.read_text(encoding="utf-8") if marker.exists() else ""
        if key in existing:
            return
        config.WISSENSWIKI_DIR.mkdir(parents=True, exist_ok=True)
        with open(marker, "a", encoding="utf-8") as f:
            if not existing:
                f.write(header)
            f.write(line)
    except Exception as e:  # noqa: BLE001 — marking must never fail the ingest
        print(f"  could not write the {label} marker (non-fatal): {e}")


def _mark_ingest_blocked(path: Path, attempts: int) -> None:
    """Make a crash-loop skip VISIBLE to the user (best-effort; never raises)."""
    german = config.VAULT_LANGUAGE.strip().lower().startswith("german")
    key = config.normalize_source_key(path.name)
    if german:
        name = "INDEXIERUNG-GESTOPPT.md"
        header = (
            "# Indexierung gestoppt (Schutz vor Absturz-Schleife)\n\n"
            "Diese Dateien wurden nach mehreren **unerwarteten Abbrüchen** "
            "nicht weiter indexiert — dein PC könnte unter der lokalen KI-Last "
            "neu starten. GPU-Last senken (Power-Limit / andere GPU-Programme "
            "schließen) oder ein Cloud-Profil nutzen, dann die Datei neu "
            "ablegen.\n\n"
        )
        line = f"- `{key}` — nach {attempts} Abbrüchen gestoppt\n"
    else:
        name = "INDEXING-STOPPED.md"
        header = (
            "# Indexing stopped (crash-loop protection)\n\n"
            "These files were not re-indexed after several **unexpected "
            "interruptions** — your PC may be resetting under the local-AI "
            "load. Lower the GPU load (power limit / close other GPU apps) or "
            "use a cloud profile, then drop the file in again.\n\n"
        )
        line = f"- `{key}` — stopped after {attempts} interruptions\n"
    _append_marker(name, header, key, line, "indexing-stopped")


def _crash_loop_skip(source_key: str, path: Path) -> bool:
    """Crash-loop guard. A document interrupted (e.g. a mid-ingest PC reset under
    local-LLM load) more than INGEST_MAX_ATTEMPTS times is SKIPPED instead of
    re-hammering the machine on every auto-restart. Returns True to skip; otherwise
    records this attempt and returns False."""
    counts = _load_attempts()
    n = counts.get(source_key, 0) + 1
    if n > config.INGEST_MAX_ATTEMPTS:
        print(f"  SKIPPED: '{path.name}' was interrupted {n - 1}x without finishing "
              f"- your PC may be resetting under the local-AI load. Lower the GPU "
              f"load (power limit / close other GPU apps) or use a cloud profile, "
              f"then re-drop the file to retry.")
        _mark_ingest_blocked(path, n - 1)
        return True
    counts[source_key] = n
    _save_attempts(counts)
    return False


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
    affected file to a marker file in the WissensWIKI/ workspace — visible to the
    user but NOT part of the searchable corpus, so the marker is never itself
    indexed; its name and text follow VAULT_LANGUAGE. Idempotent: a file already
    listed is not added again. Fully best-effort — never crashes the ingest (the
    on-screen log line is printed regardless by the caller)."""
    german = config.VAULT_LANGUAGE.strip().lower().startswith("german")
    if german:
        marker_name = "NICHT-INDEXIERT.md"
        header = (
            "# Nicht indexierte Dokumente\n\n"
            "Diese Dateien konnten nicht in den Wissensspeicher aufgenommen "
            "werden und sind daher **nicht durchsuchbar**.\n\n"
        )
        reason = ("vermutlich gescanntes PDF ohne Textebene, nicht durchsuchbar; "
                  "ggf. OCR anwenden und erneut ablegen")
    else:
        marker_name = "NOT-INDEXED.md"
        header = (
            "# Documents that could not be indexed\n\n"
            "These files could not be added to the knowledge store and are "
            "therefore **not searchable**.\n\n"
        )
        reason = ("likely a scanned PDF without a text layer, not searchable; "
                  "apply OCR and drop it in again")
    key = config.normalize_source_key(path.name)
    line = f"- `{key}` — {date.today().isoformat()} — {reason}\n"
    _append_marker(marker_name, header, key, line, "not-indexed")


def _append_ingest_log(source_file: str, path: Path, n_chunks: int,
                       partial: bool = False, attempts: int = 1,
                       contextualized: int | None = None) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "source_file": source_file, "file": str(path.name),
        "chunks": n_chunks, "ingested_at": datetime.now().isoformat(),
        "collection": config.COLLECTION_NAME,
        "partial": partial, "attempts": attempts,
    }
    try:
        # Record the source file's mtime + size at ingest so a later in-place
        # overwrite is detected by exact comparison, not a wall-clock margin that
        # misses an edit within seconds of ingest (ING-07). Additive fields —
        # legacy readers ignore them; a missing file just omits them.
        stat = path.stat()
        entry["source_mtime"] = stat.st_mtime
        entry["source_size"] = stat.st_size
    except OSError:
        pass
    if contextualized is not None:
        # Persist contextualization coverage so a document whose anchoring-
        # sentence LLM call failed (chunks embedded as raw text) is visible in
        # the durable log, not just a transient stdout line. Additive field —
        # existing readers ignore it.
        entry["contextualized"] = contextualized
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
    """Full ingest of one document. Returns True on success.

    Wraps the real work in a crash-loop guard: each attempt is counted BEFORE the
    heavy (GPU-/LLM-heavy) work and cleared on any CLEAN return. A hard PC reset
    mid-ingest kills the process before the clean return, so the count survives —
    and after INGEST_MAX_ATTEMPTS the document is skipped (with a visible marker)
    instead of crashing the machine again on the next auto-restart."""
    print(f"\n=== Ingest: {path.name} ===")
    if not path.exists():
        print("  file not found")
        return False
    source_key = config.source_key_from_path(path)
    if _crash_loop_skip(source_key, path):
        return False
    try:
        return _ingest_inner(path)
    finally:
        _clear_attempts(source_key)


def _ingest_inner(path: Path) -> bool:
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
    # Coverage captured on the full chunk list (before any embedding drops),
    # threaded into the ingest log so a silently-failed contextualization is
    # visible per source.
    n_contextualized = sum(1 for c in chunks if c.context)

    print("  [3/4] embedding (dense + sparse)...")
    embedder = get_embedder()
    # Batch the dense embeddings (far better CPU/BLAS use than one call per
    # chunk). embed_documents returns a list ALIGNED to its input: one entry per
    # chunk, in order, None where that chunk failed — so the zip below stays
    # correct and a failed chunk is skipped+logged exactly as before.
    texts = [c.embedding_text() for c in chunks]
    vectors = embedder.embed_documents(texts)
    if len(vectors) != len(chunks):
        # A backend broke the one-entry-per-text contract. Never risk a
        # misaligned vector↔chunk pairing (silent wrong-page citations) — fall
        # back to the safe per-chunk path.
        print("  embedder returned a misaligned batch — using safe per-chunk path")
        vectors = []
        for chunk in chunks:
            try:
                vectors.append(embedder.embed_document(chunk.embedding_text()))
            except Exception:  # noqa: BLE001
                vectors.append(None)
    paired = []
    for chunk, vec in zip(chunks, vectors):
        if vec is None:
            print(f"  embedding failed (p. {chunk.page_start})")
            _log_failed_chunk(chunk, "embedding_failed")
        else:
            paired.append((chunk, vec))
    print(f"  dense {len(paired)}/{len(chunks)}")
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
    # Keep sparse aligned with dense/chunks: a chunk whose BM25 vector failed
    # (None) is skipped+logged exactly like a failed dense embedding, never
    # stored with a missing sparse vector. Mirrors the dense per-chunk path and
    # adds to `skipped` so the document is marked partial and retried.
    if any(sv is None for sv in sparse):
        kept = [(c, dv, sv)
                for c, dv, sv in zip(chunks, dense, sparse) if sv is not None]
        for c, sv in zip(chunks, sparse):
            if sv is None:
                print(f"  sparse embedding failed (p. {c.page_start})")
                _log_failed_chunk(c, "sparse_embedding_failed")
        if not kept:
            print("  no chunk could be sparse-embedded — aborting")
            return False
        skipped += len(chunks) - len(kept)
        chunks = [c for c, _, _ in kept]
        dense = [dv for _, dv, _ in kept]
        sparse = [sv for _, _, sv in kept]

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
                           partial=partial, attempts=attempts,
                           contextualized=n_contextualized)
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
    # Reset the crash-loop counter so re-dropping a previously-blocked file retries.
    _clear_attempts(source_file)
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
                    and config.is_corpus_path(p)):
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
    from qdrant_client.models import PointStruct

    from brag.embeddings import get_embedder
    from brag.embeddings.sparse import embed_sparse_documents
    from brag.ingest.extract import Chunk

    try:
        slug = config.slugify_topic(topic)
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
