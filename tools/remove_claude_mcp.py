#!/usr/bin/env python3
"""Remove BRAG's MCP entries from a Claude Desktop / LM Studio config — safely.

Designed to run inside a throwaway container so the uninstaller needs no Python
on the host, e.g.:

  docker run --rm -v "<ConfigDir>":/cfg -v "<repo>/tools":/tools \
    python:3.12-slim python /tools/remove_claude_mcp.py /cfg/claude_desktop_config.json

Behaviour:
- Backs up the config to <name>.json.backup before changing anything.
- Removes ALL of BRAG's keys ('brag' AND every 'brag-<project>') plus the legacy
  name — the user's OTHER MCP servers stay.
- Drops an empty 'mcpServers' object afterwards.
- No-op (exit 0) if the file, the mcpServers section, or the keys are absent.
- On unreadable/invalid JSON: leaves the file untouched and asks the user to
  remove the entries by hand (exit 1), never discarding their other servers.
"""

import json
import os
import shutil
import sys

KEY = "brag"
LEGACY_KEYS = ("academic-rag-and-second-brain",)


def _is_brag_key(name: str) -> bool:
    return name == KEY or name.startswith(KEY + "-")


def main(path: str) -> int:
    if not os.path.exists(path):
        print(f"No config at {path} — nothing to remove.")
        return 0
    try:
        # utf-8-sig tolerates a UTF-8 BOM (Windows editors add one) as well as a
        # plain BOM-less file, so json.load doesn't choke and the uninstaller does
        # not needlessly refuse a perfectly valid config.
        with open(path, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Could not read {path} ({e}). Please remove the BRAG entries from "
              "mcpServers by hand.")
        return 1

    servers = cfg.get("mcpServers")
    keys = ([k for k in list(servers) if _is_brag_key(k) or k in LEGACY_KEYS]
            if isinstance(servers, dict) else [])
    if not keys:
        print("No BRAG entries found — nothing to remove.")
        return 0

    # copyfile, NOT copy: copy also copies the file mode (chmod), which is
    # "Operation not permitted" on a Windows Docker bind mount.
    shutil.copyfile(path, path + ".backup")
    for k in keys:
        del servers[k]
    if not servers:
        cfg.pop("mcpServers", None)

    # Direct write (NOT tmp + os.replace): the atomic-rename dance does not
    # reliably reach the host on a Windows bind mount.
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"Removed {len(keys)} BRAG entr{'y' if len(keys) == 1 else 'ies'} "
          f"(backup: {os.path.basename(path)}.backup).")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/cfg/claude_desktop_config.json"
    sys.exit(main(target))
