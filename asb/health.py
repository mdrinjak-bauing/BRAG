"""One-shot health check — is the RAG system actually working?

Run inside the app container:  python -m asb.health

It verifies the parts that live inside Docker (Qdrant, the corpus index, the
app/watcher process, and the AI text backend). The host-side status.command /
status.bat wrap this and add the checks that can only be seen from outside the
container (Docker itself, the containers being up, the Claude Desktop entry).
"""

import sys
import urllib.request

from asb import config


def _ok(label: str, detail: str = "") -> bool:
    print(f"  [ OK ]  {label}" + (f" — {detail}" if detail else ""))
    return True


def _fail(label: str, detail: str = "") -> bool:
    print(f"  [FAIL]  {label}" + (f" — {detail}" if detail else ""))
    return False


def check_qdrant() -> bool:
    try:
        from asb import storage
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
        from asb import storage
        client = storage.get_client()
        try:
            names = {c.name for c in client.get_collections().collections}
            if config.COLLECTION_NAME not in names:
                return _fail("Corpus index",
                             "not created yet — drop a PDF into wissensspeicher/sources/")
            info = client.get_collection(config.COLLECTION_NAME)
            n = info.points_count or 0
            sources = storage.list_corpus_sources(client)
        finally:
            client.close()
        if n == 0:
            return _fail("Corpus index", "empty — drop a PDF into wissensspeicher/sources/")
        return _ok("Corpus index", f"{len(sources)} sources, {n} chunks")
    except Exception as e:  # noqa: BLE001
        return _fail("Corpus index", str(e)[:60])


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
            from asb.setup_core import validate_api_key
            ok, msg = validate_api_key(backend, key)
        except Exception as e:  # noqa: BLE001
            return _fail(f"AI text model ({backend})", str(e)[:60])
        return (_ok(f"AI text model ({backend})", config.LLM_MODEL)
                if ok else _fail(f"AI text model ({backend})", msg))
    # Local profile (LM Studio / Ollama) reached via host.docker.internal
    try:
        base = (config.LLM_BASE_URL or "").rstrip("/")
        with urllib.request.urlopen(f"{base}/models", timeout=5):
            return _ok("AI text model (local)", config.LLM_MODEL)
    except Exception:  # noqa: BLE001
        return _fail("AI text model (local)",
                     f"not reachable at {config.LLM_BASE_URL} — is LM Studio/Ollama running?")


def main() -> int:
    print(f"\nASB health — profile: {config.PROFILE_NAME}, "
          f"collection: {config.COLLECTION_NAME}\n")
    results = [
        check_qdrant(),
        check_app_watcher(),
        check_corpus(),
        check_llm(),
    ]
    print()
    if all(results):
        print("All checks passed — your RAG system is working. ✅")
        return 0
    print("Some checks need attention (see [FAIL] lines above).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
