#!/usr/bin/env python3
"""Merge BRAG's MCP entry into Claude Desktop's config — host-side (macOS).

Mirrors tools/merge_claude_config.ps1 (Windows). Claude Desktop rewrites this
file while it is running and would drop an entry added underneath it, so
setup.command calls this AFTER Claude is fully quit — that makes the connection
persist (the in-container write during the wizard is best-effort and a running
Claude can clobber it).

Safe: backs up the existing config, preserves every other key (including other
MCP servers), migrates the old key name, writes UTF-8 without a BOM, and
verifies. Best-effort — never raises, so it cannot break setup.
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
    cfg = (Path.home() / "Library" / "Application Support" / "Claude"
           / "claude_desktop_config.json")
    cfg.parent.mkdir(parents=True, exist_ok=True)

    root: dict = {}
    if cfg.exists():
        try:
            raw = cfg.read_text(encoding="utf-8-sig")
            root = json.loads(raw) if raw.strip() else {}
        except (json.JSONDecodeError, OSError):
            try:
                cfg.rename(cfg.parent / "claude_desktop_config.json.broken.bak")
            except OSError:
                pass
            print("  WARNING: Claude config was not valid JSON (backed up); "
                  "writing a fresh one.")
            root = {}
        else:
            try:
                (cfg.parent / "claude_desktop_config.json.backup").write_text(
                    raw, encoding="utf-8")
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
        print(f"  Could not write Claude config ({e}); add the 'brag' entry by hand.")
        return 0

    try:
        chk = json.loads(cfg.read_text(encoding="utf-8-sig"))
        if isinstance(chk.get("mcpServers"), dict) and KEY in chk["mcpServers"]:
            print("  [ OK ]  BRAG is connected to Claude Desktop.")
            return 0
    except (json.JSONDecodeError, OSError):
        pass
    print("  [note] Could not confirm the Claude entry; add 'brag' by hand.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — never break setup
        print(f"  Claude MCP config skipped ({e}).")
        sys.exit(0)
