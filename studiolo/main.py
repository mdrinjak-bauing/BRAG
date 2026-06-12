"""Container entrypoint: HTTP bridge (background thread) + watcher (foreground)."""

from studiolo import config
from studiolo.http_bridge import start_bridge_in_background
from studiolo.watcher import run_watcher


def main():
    print(f"Studiolo — profile: {config.PROFILE_NAME}, "
          f"collection: {config.COLLECTION_NAME}")
    # Seed an empty/custom vault with the template (CLAUDE.md, folders);
    # never overwrites existing files.
    from studiolo.setup_core import seed_vault_if_empty
    seed_vault_if_empty(config.VAULT)
    start_bridge_in_background()
    run_watcher()


if __name__ == "__main__":
    main()
