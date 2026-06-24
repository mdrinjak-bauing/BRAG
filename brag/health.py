"""One-shot health check — is the RAG system actually working?

Run inside the app container:  python -m brag.health

It verifies the parts that live inside Docker (Qdrant, the corpus index, the
app/watcher process, and the AI text backend). The host-side status.command /
status.bat wrap this and add the checks that can only be seen from outside the
container (Docker itself, the containers being up, the Claude Desktop entry).
"""

import sys
import urllib.request

from brag import config


def _ok(label: str, detail: str = "") -> bool:
    print(f"  [ OK ]  {label}" + (f" — {detail}" if detail else ""))
    return True


def _fail(label: str, detail: str = "") -> bool:
    print(f"  [FAIL]  {label}" + (f" — {detail}" if detail else ""))
    return False


def check_qdrant() -> bool:
    try:
        from brag import storage
        client = storage.get_client()
        try:
            client.get_collections()
        finally:
            client.close()
        return _ok("Qdrant search database", "reachable")
    except Exception as e:  # noqa: BLE001
        return _fail("Qdrant search database", f"not reachable ({str(e)[:60]})")


def check_corpus() -> bool:
    try:
        from brag import storage
        client = storage.get_client()
        try:
            names = {c.name for c in client.get_collections().collections}
            if config.COLLECTION_NAME not in names:
                return _fail("Corpus index",
                             "not created yet — drop a PDF into your project folder")
            info = client.get_collection(config.COLLECTION_NAME)
            n = info.points_count or 0
            sources = storage.list_corpus_sources(client)
        finally:
            client.close()
        if n == 0:
            return _fail("Corpus index", "empty — drop a PDF into your project folder")
        return _ok("Corpus index", f"{len(sources)} sources, {n} chunks")
    except Exception as e:  # noqa: BLE001
        return _fail("Corpus index", str(e)[:60])


def _exclude_reason(name: str) -> str:
    """Why a top-level entry is kept out of the index, or '' if it is corpus."""
    if name == config.WISSENSWIKI_NAME:
        return "your workspace (never indexed)"
    if name.startswith("."):
        return "hidden"
    if name.startswith("_"):
        return 'starts with "_" (kept out of the index)'
    if name in config.EXCLUDE_DIRS:
        return "in EXCLUDE_DIRS (your setup choice)"
    return ""


def show_corpus_folders() -> bool:
    """Plain-language overview: which top-level folders are indexed and which are
    kept out (and why). Informational — always returns True so it never fails the
    overall health check."""
    try:
        vault = config.VAULT
        if not vault.exists():
            return True
        # Indexed-source counts per top-level folder. Source keys are POSIX,
        # suffix-dropped and vault-relative, so the first segment IS the folder.
        counts: dict = {}
        try:
            from brag import storage
            client = storage.get_client()
            try:
                names = {c.name for c in client.get_collections().collections}
                if config.COLLECTION_NAME in names:
                    for s in storage.list_corpus_sources(client):
                        top = s.split("/", 1)[0] if "/" in s else "(root)"
                        counts[top] = counts.get(top, 0) + 1
            finally:
                client.close()
        except Exception:  # noqa: BLE001 — counts are best-effort
            pass
        print("  Folders in your project — what lands in the index:")
        root_files = 0
        for p in sorted(vault.iterdir(), key=lambda q: q.name.lower()):
            reason = _exclude_reason(p.name)
            if not p.is_dir():
                if not reason:
                    root_files += 1
                continue
            if reason:
                print(f"    [ excluded ]  {p.name}/  — {reason}")
            else:
                print(f"    [ indexed  ]  {p.name}/  — {counts.get(p.name, 0)} source(s)")
        if root_files:
            print(f"    [ indexed  ]  (files in the project root)  — "
                  f"{counts.get('(root)', 0)} source(s)")
        print('  Tip: rename a folder to start with "_" to keep it out of the index.')
        return True
    except Exception as e:  # noqa: BLE001
        return _fail("Folder overview", str(e)[:60])


def check_app_watcher() -> bool:
    # The HTTP bridge runs in the same process as the folder watcher; if the
    # bridge answers, the watcher loop is alive too.
    try:
        url = f"http://localhost:{config.BRIDGE_PORT}/healthz"
        with urllib.request.urlopen(url, timeout=5) as r:
            ok = r.read().strip() == b"ok"
        return (_ok("App + folder watcher", "running")
                if ok else _fail("App + folder watcher", "bridge did not answer"))
    except Exception as e:  # noqa: BLE001
        return _fail("App + folder watcher", str(e)[:60])


def check_llm() -> bool:
    backend = config.LLM_BACKEND
    keymap = {
        "gemini": config.GEMINI_API_KEY,
        "openai": config.OPENAI_API_KEY,
        "anthropic": config.ANTHROPIC_API_KEY,
    }
    if backend in keymap:
        key = keymap[backend]
        if not key:
            return _fail(f"AI text model ({backend})", "no API key set — re-run setup")
        try:
            from brag.setup_core import validate_api_key
            ok, msg = validate_api_key(backend, key)
        except Exception as e:  # noqa: BLE001
            return _fail(f"AI text model ({backend})", str(e)[:60])
        return (_ok(f"AI text model ({backend})", config.LLM_MODEL)
                if ok else _fail(f"AI text model ({backend})", msg))
    # Local profile (LM Studio) reached via host.docker.internal
    try:
        base = (config.LLM_BASE_URL or "").rstrip("/")
        with urllib.request.urlopen(f"{base}/models", timeout=5):
            return _ok("AI text model (local)", config.LLM_MODEL)
    except Exception:  # noqa: BLE001
        return _fail("AI text model (local)",
                     f"not reachable at {config.LLM_BASE_URL} — is LM Studio running?")


def main() -> int:
    print(f"\nBRAG health — profile: {config.PROFILE_NAME}, "
          f"collection: {config.COLLECTION_NAME}\n")
    results = [
        check_qdrant(),
        check_app_watcher(),
        check_corpus(),
        check_llm(),
    ]
    print()
    show_corpus_folders()   # informational — not part of the pass/fail tally
    print()
    if all(results):
        print("All checks passed — your RAG system is working. ✅")
        return 0
    print("Some checks need attention (see [FAIL] lines above).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
