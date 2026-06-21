#!/usr/bin/env python3
"""Merge BRAG's MCP connectors into Claude Desktop's config — host-side (macOS).

A THIN pipe: send the current config through the container's brag.claude_sync
(the single source of truth for the connector set + sync rules) and write the
result back. brag-app must be running. setup.command calls this AFTER Claude is
fully quit, so the write persists. Best-effort — never raises.
"""

import subprocess
import sys
from pathlib import Path


def _sync_via_container(current: str):
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "brag-app", "python", "-m", "brag.claude_sync"],
            input=current, capture_output=True, text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not (r.stdout or "").strip():
        return None
    return r.stdout


def main() -> int:
    cfg = (Path.home() / "Library" / "Application Support" / "Claude"
           / "claude_desktop_config.json")
    cfg.parent.mkdir(parents=True, exist_ok=True)
    current = ""
    if cfg.exists():
        try:
            current = cfg.read_text(encoding="utf-8-sig")
            (cfg.parent / "claude_desktop_config.json.backup").write_text(
                current, encoding="utf-8")
        except OSError:
            pass
    synced = _sync_via_container(current)
    if synced is None:
        print("  (Could not reach brag-app for the Claude entry; re-run setup.)")
        return 0
    try:
        cfg.write_text(synced, encoding="utf-8")
        print("  [ OK ]  BRAG connected to Claude Desktop.")
    except OSError as e:
        print(f"  Could not write Claude config ({e}).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — never break setup
        print(f"  Claude MCP config skipped ({e}).")
        sys.exit(0)
