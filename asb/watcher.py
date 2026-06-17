"""File watcher: auto-ingest documents dropped into wissensspeicher/sources/.

Uses a PollingObserver — file system events do not propagate across the
Docker bind-mount boundary, polling does (and it behaves identically on
macOS and Windows hosts). Includes:
- stable-file wait (don't ingest half-copied files)
- self-rename dedup (renames must not trigger a second ingest)
- startup reconciliation (documents added while the watcher was down)
"""

import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from asb import config, storage
from asb.ingest.pipeline import ingest, remove_source

_processing: set[str] = set()


def _is_relevant(path: Path) -> bool:
    if path.suffix.lower() not in config.SUPPORTED_SUFFIXES:
        return False
    if path.name.startswith("."):
        return False
    return not any(part in config.WATCH_IGNORE_DIRS for part in path.parts)


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


class DocumentHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not _is_relevant(path) or str(path) in _processing:
            return
        _processing.add(str(path))
        try:
            print(f"new document detected: {path.name}")
            if _wait_for_stable_file(path):
                ingest(path)
        except Exception as e:  # noqa: BLE001 — watcher must survive anything
            print(f"ingest error for {path.name}: {e}")
        finally:
            _processing.discard(str(path))

    def on_deleted(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not _is_relevant(path):
            return
        try:
            n = remove_source(path.stem)
            print(f"document removed: {path.name} — {n} chunks cleaned up")
        except Exception as e:  # noqa: BLE001
            print(f"cleanup error for {path.name}: {e}")

    def on_moved(self, event):
        if event.is_directory:
            return
        src, dest = Path(event.src_path), Path(event.dest_path)
        if _is_relevant(src):
            try:
                remove_source(src.stem)
            except Exception as e:  # noqa: BLE001
                print(f"cleanup error for {src.name}: {e}")
        if _is_relevant(dest) and str(dest) not in _processing:
            _processing.add(str(dest))
            try:
                print(f"document renamed/moved: {dest.name} — re-indexing")
                if _wait_for_stable_file(dest):
                    ingest(dest)
            except Exception as e:  # noqa: BLE001
                print(f"ingest error for {dest.name}: {e}")
            finally:
                _processing.discard(str(dest))


def reconcile_on_startup():
    """Index documents that arrived while the watcher was not running.
    Retries while Qdrant is still booting (compose race at startup)."""
    corpus = None
    for attempt in range(6):
        try:
            client = storage.get_client()
            storage.ensure_collection(client)
            corpus = storage.list_corpus_sources(client)
            client.close()
            break
        except Exception:  # noqa: BLE001
            if attempt < 5:
                print("waiting for Qdrant to come up ...")
                time.sleep(10)
    if corpus is None:
        print("reconciliation skipped — Qdrant not reachable")
        return

    backlog = [
        p for p in sorted(config.SOURCES_DIR.rglob("*"))
        if p.is_file() and _is_relevant(p)
        and config.normalize_source_key(p.stem) not in corpus
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
