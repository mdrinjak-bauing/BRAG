#!/usr/bin/env python3
"""Remove BRAG's MCP entry from a Claude Desktop config — safely.

Designed to run inside a throwaway container so the uninstaller needs no Python
on the host, e.g.:

  docker run --rm -v "<ClaudeConfigDir>":/cfg -v "<repo>/tools":/tools \
    python:3.12-slim python /tools/remove_claude_mcp.py /cfg/claude_desktop_config.json

Behaviour (mirrors, in reverse, brag/setup_core.py:write_claude_config):
- Backs up the config to <name>.json.backup before changing anything.
- Removes ONLY BRAG's key ('brag', plus the legacy name) — other MCP servers stay.
- Drops an empty 'mcpServers' object afterwards.
- No-op (exit 0) if the file, the mcpServers section, or the key is absent.
- On unreadable/invalid JSON: leaves the file untouched and asks the user to
  remove the entry by hand (exit 1), never discarding their other servers.
"""

import json
import os
import shutil
import sys

KEY = "brag"
LEGACY_KEYS = ("academic-rag-and-second-brain",)


def main(path: str) -> int:
    if not os.path.exists(path):
        print(f"No Claude config at {path} — nothing to remove.")
        return 0
    try:
        # utf-8-sig tolerates a UTF-8 BOM (Windows editors like Notepad add one)
        # as well as a plain BOM-less file — without it, json.load chokes on the
        # BOM and the uninstaller would needlessly refuse a perfectly valid config.
        with open(path, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Could not read {path} ({e}). Please remove the '{KEY}' "
              "entry from mcpServers by hand.")
        return 1

    servers = cfg.get("mcpServers")
    keys = [k for k in (KEY, *LEGACY_KEYS)
            if isinstance(servers, dict) and k in servers]
    if not keys:
        print(f"BRAG entry '{KEY}' not found — nothing to remove.")
        return 0

    shutil.copy(path, path + ".backup")
    for k in keys:
        del servers[k]
    if not servers:
        cfg.pop("mcpServers", None)

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, path)
    print(f"Removed '{KEY}' from the Claude config (backup: {os.path.basename(path)}.backup).")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/cfg/claude_desktop_config.json"
    sys.exit(main(target))
