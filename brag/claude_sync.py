"""Sync BRAG's MCP connectors into a Claude Desktop / LM Studio config.

Both hosts use the same {"mcpServers": {...}} schema. The host launchers cannot
import brag (it lives in the container), and on Windows an in-container write to
the host config does not reach the host — so the launchers pipe the host config
THROUGH this command (run in the container) and write the result back:

  type config.json | docker exec -i brag-app python -m brag.claude_sync > new.json

This is the SINGLE source of truth for the connector set (one entry per
registered project) and the sync rules: drop brag-* connectors whose project was
removed, keep the user's OTHER MCP servers untouched, migrate the legacy key.
setup_core.write_claude_config (the in-container write used on macOS) calls
sync() too, so the merge logic lives in exactly one place.
"""

import json
import sys

from brag import setup_core


def sync(config_text: str) -> str:
    """Return the config JSON with BRAG's connectors synced to the registry.
    Invalid/empty input is treated as an empty config (the caller decides whether
    to refuse on invalid JSON before reaching here)."""
    try:
        root = json.loads(config_text) if config_text.strip() else {}
    except json.JSONDecodeError:
        root = {}
    if not isinstance(root, dict):
        root = {}
    servers = root.get("mcpServers")
    if "mcpServers" in root and not isinstance(servers, dict):
        # Present but malformed (not an object): refuse to overwrite it — return
        # the config unchanged so a recoverable config is never clobbered (MP-F10).
        # BRAG's connector is simply not added until the user fixes the file.
        return json.dumps(root, indent=2)
    if not isinstance(servers, dict):
        servers = {}
        root["mcpServers"] = servers
    for old in setup_core.LEGACY_MCP_KEYS:
        servers.pop(old, None)  # migrate older installs off the legacy name
    desired = setup_core.connectors_for_registry()
    for key in [k for k in list(servers)
                if setup_core._is_brag_key(k) and k not in desired]:
        servers.pop(key, None)
    servers.update(desired)
    return json.dumps(root, indent=2)


def main() -> int:
    sys.stdout.write(sync(sys.stdin.read()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
