"""Container entrypoint: HTTP bridge (background thread) + watcher (foreground)."""

from brag import config
from brag.http_bridge import start_bridge_in_background
from brag.watcher import run_watcher


def _warmup_models_in_background() -> None:
    """Pre-load the search models in this persistent process so the first
    /api/search is fast and the models live in RAM exactly once — the per-project
    MCP clients are thin and never load models themselves."""
    import threading

    def _warm():
        try:
            from brag.embeddings import get_embedder
            from brag.embeddings.sparse import get_sparse_model
            get_embedder()
            get_sparse_model()
            if config.RERANK_ENABLED:
                from brag.search.query import _get_reranker
                _get_reranker()
        except Exception as e:  # noqa: BLE001 — warmup is best-effort
            print(f"model warmup skipped: {e}")

    threading.Thread(target=_warm, daemon=True).start()


def main():
    print(f"BRAG — Building Retrieval-Augmented Generation — profile: {config.PROFILE_NAME}, "
          f"collection: {config.COLLECTION_NAME}")
    # Seed an empty/custom knowledge store with the template (CLAUDE.md, folders);
    # never overwrites existing files.
    from brag.setup_core import seed_vault_if_empty
    seed_vault_if_empty(config.VAULT)
    start_bridge_in_background()
    _warmup_models_in_background()
    run_watcher()


if __name__ == "__main__":
    main()
