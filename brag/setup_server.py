"""Setup entrypoint: serves the browser wizard only, no watcher.

Run by the one-shot `setup` compose service, which — unlike the persistent
`app` service — mounts the project directory and the Claude Desktop config so
the wizard can write `.env` and the MCP entry. The launcher (setup.command /
setup.bat) starts this, opens the browser at /setup, waits for the
`.setup_complete` marker, then tears this down and starts the persistent app.

Requires SETUP_MODE=1 (set by the setup service) so the bridge actually serves
the wizard and its config-writing API.
"""

import time

from brag import config
from brag.http_bridge import start_bridge_in_background


def main():
    if not config.SETUP_MODE:
        print("setup_server started without SETUP_MODE=1 — refusing "
              "(the wizard is meant to run only in the one-shot setup service).")
        return
    start_bridge_in_background()
    print(f"BRAG setup ready — open http://localhost:{config.BRIDGE_PORT}/setup "
          "in your browser. This service exits once setup is complete.")
    # Stay alive while the user completes the browser wizard; the launcher
    # tears this container down after the .setup_complete marker appears.
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
