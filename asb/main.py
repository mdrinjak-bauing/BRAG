"""Container entrypoint: HTTP bridge (background thread) + watcher (foreground)."""

from asb import config
from asb.http_bridge import start_bridge_in_background
from asb.watcher import run_watcher


def main():
    print(f"ASB — Academic RAG & Second Brain — profile: {config.PROFILE_NAME}, "
          f"collection: {config.COLLECTION_NAME}")
    # Seed an empty/custom knowledge store with the template (CLAUDE.md, folders);
    # never overwrites existing files.
    from asb.setup_core import seed_vault_if_empty
    seed_vault_if_empty(config.VAULT)
    start_bridge_in_background()
    run_watcher()


if __name__ == "__main__":
    main()
