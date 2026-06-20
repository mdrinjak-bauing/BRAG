"""File watcher: auto-ingest documents dropped into WissensWIKI/sources/.

Uses a PollingObserver — file system events do not propagate across the
Docker bind-mount boundary, polling does (and it behaves identically on
macOS and Windows hosts). Includes:
- stable-file wait (don't ingest half-copied files)
- self-rename dedup (renames must not trigger a second ingest)
- startup reconciliation (documents added while the watcher was down)
"""

import threading
import time
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from brag import config, storage
from brag.ingest.pipeline import (
    ingest, reapply_folder_metadata, remove_source, rename_source,
)

# Paths currently being ingested, so a second event for the same file (the
# PollingObserver can dispatch on multiple threads, and a rename fires both a
# move and a create on some hosts) doesn't start a duplicate ingest. Guarded by
# a lock: the check-and-add must be atomic or two threads can both pass the
# "not in set" test.
_processing: set[str] = set()
_processing_lock = threading.Lock()


def _claim(path: Path) -> bool:
    """Atomically mark a path as being processed. Returns False if another
    thread already claimed it (caller should then do nothing)."""
    key = str(path)
    with _processing_lock:
        if key in _processing:
            return False
        _processing.add(key)
        return True


def _release(path: Path) -> None:
    with _processing_lock:
        _processing.discard(str(path))


def _is_relevant(path: Path) -> bool:
    if path.suffix.lower() not in config.SUPPORTED_SUFFIXES:
        return False
    if path.name.startswith("."):
        return False
    return not any(part in config.WATCH_IGNORE_DIRS for part in path.parts)


def _is_meta_file(path: Path) -> bool:
    """A `_meta.txt` under sources/ (outside ignored dirs). Editing it must
    refresh the folder's already-indexed documents — unlike a document file,
    `_meta.txt` is not a SUPPORTED_SUFFIX, so the normal ingest path skips it."""
    if path.name != "_meta.txt":
        return False
    try:
        path.resolve().relative_to(config.SOURCES_DIR.resolve())
    except (ValueError, OSError):
        return False
    return not any(part in config.WATCH_IGNORE_DIRS for part in path.parts)


def _refresh_folder_meta(path: Path, verb: str) -> None:
    """Re-apply folder metadata to already-indexed docs after a _meta.txt change."""
    n = reapply_folder_metadata(path.parent)
    if n:
        print(f"_meta.txt {verb} in {path.parent.name}/ — refreshed "
              f"metadata on {n} document(s) (no re-ingest)")


def _wait_for_stable_file(path: Path, min_wait=3, max_wait=120, poll=2) -> bool:
    """Wait until the file size stops changing (fully copied)."""
    if not path.exists():
        return False
    time.sleep(min_wait)
    last_size, waited = -1, min_wait
    while waited < max_wait:
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size > 0 and size == last_size:
            return True
        last_size = size
        time.sleep(poll)
        waited += poll
    return True


def _changed_since_ingest(path: Path, states: dict) -> bool:
    """True if `path` was modified AFTER its last ingest — i.e. the document was
    overwritten in place and its indexed chunks are now stale. Missing files are
    caught by the corpus check and under-limit partials by the retry check; this
    ALSO catches a file edited in place after ANY prior ingest, including a
    retry-exhausted partial the user re-saved to fix. (An unchanged partial is
    not re-driven here, because its mtime has not advanced — so this never
    reintroduces an unbounded retry of a permanently-failing document.) `states`
    is the per-source ingest-log map (fetch once, reuse across files); the small
    margin absorbs copy-time jitter so a file is never re-ingested right after
    its first ingest."""
    st = states.get(config.source_key_from_path(path))
    if not st or not st.get("ingested_at"):
        return False
    try:
        ingested = datetime.fromisoformat(st["ingested_at"]).timestamp()
        return path.stat().st_mtime > ingested + 5
    except (ValueError, OSError):
        return False


class DocumentHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if _is_meta_file(path):
            _refresh_folder_meta(path, "added")
            return
        if not _is_relevant(path) or not _claim(path):
            return
        try:
            print(f"new document detected: {path.name}")
            if _wait_for_stable_file(path):
                ingest(path)
        except Exception as e:  # noqa: BLE001 — watcher must survive anything
            print(f"ingest error for {path.name}: {e}")
        finally:
            _release(path)

    def on_modified(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        # The one editable non-document file that affects the index is _meta.txt.
        if _is_meta_file(path):
            _refresh_folder_meta(path, "changed")
            return
        # A document overwritten IN PLACE (same path, new content) must be
        # re-indexed, or its OLD chunks would linger forever. Re-ingest only when
        # the file actually changed since its last successful ingest, so routine
        # modify events (and our own just-finished ingest) don't trigger needless
        # work. ingest() is idempotent (upsert-then-delete-by-source).
        if not _is_relevant(path) or not _claim(path):
            return
        try:
            from brag.ingest.pipeline import _ingest_log_states
            if _changed_since_ingest(path, _ingest_log_states()):
                print(f"document changed: {path.name} — re-indexing")
                if _wait_for_stable_file(path):
                    ingest(path)
        except Exception as e:  # noqa: BLE001 — watcher must survive anything
            print(f"re-ingest error for {path.name}: {e}")
        finally:
            _release(path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if _is_meta_file(path):
            # Metadata reverts to the remaining (parent) _meta.txt chain.
            _refresh_folder_meta(path, "removed")
            return
        if not _is_relevant(path):
            return
        try:
            n = remove_source(config.source_key_from_path(path))
            print(f"document removed: {path.name} — {n} chunks cleaned up")
        except Exception as e:  # noqa: BLE001
            print(f"cleanup error for {path.name}: {e}")

    def on_moved(self, event):
        if event.is_directory:
            return
        src, dest = Path(event.src_path), Path(event.dest_path)
        src_ok, dest_ok = _is_relevant(src), _is_relevant(dest)

        # Rename/move WITHIN sources/: same content, only the name changed —
        # patch the filename-derived metadata in place instead of re-embedding.
        if src_ok and dest_ok:
            if not _claim(dest):
                return
            try:
                n = rename_source(config.source_key_from_path(src), dest)
                if n:
                    print(f"document renamed: {dest.name} — metadata updated on "
                          f"{n} chunks (no re-ingest)")
                else:
                    print(f"renamed file {dest.name} was not indexed yet — ingesting")
                    if _wait_for_stable_file(dest):
                        ingest(dest)
            except Exception as e:  # noqa: BLE001 — watcher must survive anything
                print(f"rename handling error for {dest.name}: {e}")
            finally:
                _release(dest)
            return

        # Moved OUT of sources/ (e.g. into _inbox or trash): drop old chunks.
        if src_ok:
            try:
                remove_source(config.source_key_from_path(src))
            except Exception as e:  # noqa: BLE001
                print(f"cleanup error for {src.name}: {e}")
        # Moved INTO sources/ from elsewhere: index it fresh.
        if dest_ok and _claim(dest):
            try:
                print(f"document moved in: {dest.name} — indexing")
                if _wait_for_stable_file(dest):
                    ingest(dest)
            except Exception as e:  # noqa: BLE001
                print(f"ingest error for {dest.name}: {e}")
            finally:
                _release(dest)


def reconcile_on_startup():
    """Index documents that arrived while the watcher was not running.
    Retries while Qdrant is still booting (compose race at startup)."""
    corpus = None
    orphans: list[str] = []
    last_error = None
    for attempt in range(6):
        try:
            client = storage.get_client()
            storage.ensure_collection(client)
            corpus = storage.list_corpus_sources(client)
            orphans = storage.orphaned_collections(client)
            client.close()
            break
        except Exception as e:  # noqa: BLE001
            last_error = e
            if attempt < 5:
                print("waiting for Qdrant to come up ...")
                time.sleep(10)
    if corpus is None:
        # Surface the real cause (not just "unreachable") — a dimension clash,
        # auth or broken volume is otherwise swallowed and undiagnosable here.
        print(f"reconciliation skipped — Qdrant not reachable: {str(last_error)[:160]}")
        return
    # Surface (never auto-delete) Qdrant collections left over from a previous
    # embedding backend/dimension — COLLECTION_NAME encodes both, so a change
    # targets a NEW collection and the old one lingers, consuming disk.
    if orphans:
        print("note: leftover Qdrant collection(s) from a previous embedding "
              f"setting, not in use: {', '.join(orphans)} — they consume disk; "
              "drop them deliberately (Qdrant dashboard) when you are sure.")

    from brag.ingest.pipeline import _ingest_log_states, sources_needing_retry
    retry = sources_needing_retry()
    log_states = _ingest_log_states()

    files = [p for p in sorted(config.SOURCES_DIR.rglob("*"))
             if p.is_file() and _is_relevant(p)]
    fs_keys = {config.source_key_from_path(p) for p in files}

    # Prune documents deleted while the watcher was DOWN: the live on_deleted
    # handler cannot see a deletion that happened with the container stopped (or
    # a delete event the poller missed), so reconcile removes corpus entries
    # whose source file is gone. Skip passages (passage:* keys have no file on
    # disk). GUARD: never prune when the filesystem scan found ZERO files — a
    # broken/unmounted bind mount would otherwise wipe the entire index.
    if files:
        orphaned = sorted(
            k for k in corpus
            if k not in fs_keys and not k.startswith("passage:")
        )
        if orphaned:
            print(f"reconciliation: pruning {len(orphaned)} deleted document(s)")
            for key in orphaned:
                try:
                    n = remove_source(key)
                    print(f"  pruned {key} — {n} chunks removed")
                except Exception as e:  # noqa: BLE001
                    print(f"  prune failed for {key}: {str(e)[:80]}")

    # Re-drive documents that are: absent from the corpus; OR whose last ingest
    # was only partial (transient embedding failures — retry the missing pages);
    # OR that were edited in place since their last successful ingest (stale).
    backlog = [
        p for p in files
        if (config.source_key_from_path(p) not in corpus
            or config.source_key_from_path(p) in retry
            or _changed_since_ingest(p, log_states))
    ]
    if not backlog:
        print("reconciliation: index is complete")
        return
    print(f"reconciliation: {len(backlog)} document(s) to index")
    for i, path in enumerate(backlog, 1):
        print(f"[{i}/{len(backlog)}] {path.name}")
        try:
            ingest(path)
        except Exception as e:  # noqa: BLE001
            print(f"  failed: {e}")
        time.sleep(2)


def run_watcher():
    config.SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    reconcile_on_startup()
    observer = PollingObserver(timeout=config.WATCH_POLL_SECONDS)
    observer.schedule(DocumentHandler(), str(config.SOURCES_DIR), recursive=True)
    observer.start()
    print(f"watching {config.SOURCES_DIR} (poll every {config.WATCH_POLL_SECONDS}s)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
