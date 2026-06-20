#!/usr/bin/env python3
"""Merge BRAG's MCP entry into LM Studio's mcp.json — host-side, cross-platform.

LM Studio (v0.3.17+) is an MCP host: its chat can use BRAG's search + notebook
tools. Its config is ~/.lmstudio/mcp.json with the same {"mcpServers": {...}}
schema as Claude Desktop. We only touch it when LM Studio is installed (the
~/.lmstudio folder exists) and never create it otherwise. Safe: backs up,
preserves other servers, migrates the old key name, writes UTF-8 without a BOM.
Best-effort — never raises, so it cannot break setup. Used by setup.command
(macOS); Windows uses tools/merge_lmstudio_config.ps1.
"""

import json
import sys
from pathlib import Path

KEY = "brag"
LEGACY_KEYS = ("academic-rag-and-second-brain",)
ENTRY = {
    "command": "docker",
    "args": ["exec", "-i", "brag-app", "python", "-m", "brag.mcp_server"],
}


def main() -> int:
    dir_ = Path.home() / ".lmstudio"
    if not dir_.is_dir():
        print("  LM Studio not detected (no ~/.lmstudio folder) - skipped.")
        return 0
    cfg = dir_ / "mcp.json"

    root: dict = {}
    if cfg.exists():
        try:
            raw = cfg.read_text(encoding="utf-8-sig")
            root = json.loads(raw) if raw.strip() else {}
        except (json.JSONDecodeError, OSError):
            try:
                cfg.rename(dir_ / "mcp.json.broken.bak")
            except OSError:
                pass
            print("  WARNING: LM Studio mcp.json was not valid JSON "
                  "(backed up); writing a fresh one.")
            root = {}
        else:
            try:
                (dir_ / "mcp.json.backup").write_text(raw, encoding="utf-8")
            except OSError:
                pass
    if not isinstance(root, dict):
        root = {}

    servers = root.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
        root["mcpServers"] = servers
    for old in LEGACY_KEYS:
        servers.pop(old, None)  # migrate older installs to the new key
    servers[KEY] = ENTRY

    try:
        cfg.write_text(json.dumps(root, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"  Could not write LM Studio mcp.json ({e}); add the 'brag' entry by hand.")
        return 0
    print("  [ OK ]  BRAG is connected to LM Studio.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — never break setup
        print(f"  LM Studio MCP config skipped ({e}).")
        sys.exit(0)
