"""Container entrypoint: HTTP bridge (background thread) + watcher (foreground)."""

from asb import config
from asb.http_bridge import start_bridge_in_background
from asb.watcher import run_watcher


def main():
    print(f"Academic Second Brain — profile: {config.PROFILE_NAME}, "
          f"collection: {config.COLLECTION_NAME}")
    start_bridge_in_background()
    run_watcher()


if __name__ == "__main__":
    main()
