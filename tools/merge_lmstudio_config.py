#!/usr/bin/env python3
"""Merge BRAG's MCP connectors into LM Studio's mcp.json — host-side, macOS.

LM Studio uses the same { "mcpServers": {...} } schema as Claude, so the SAME
container command (brag.claude_sync) computes the synced result. Thin pipe; only
touches it when LM Studio is installed (~/.lmstudio exists). brag-app must be
running. Best-effort — never raises.
"""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    dir_ = Path.home() / ".lmstudio"
    if not dir_.is_dir():
        print("  LM Studio not detected (no ~/.lmstudio folder) - skipped.")
        return 0
    cfg = dir_ / "mcp.json"
    current = ""
    if cfg.exists():
        try:
            current = cfg.read_text(encoding="utf-8-sig")
            (dir_ / "mcp.json.backup").write_text(current, encoding="utf-8")
        except OSError:
            pass
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "brag-app", "python", "-m", "brag.claude_sync"],
            input=current, capture_output=True, text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.SubprocessError):
        print("  (Could not reach brag-app for the LM Studio entry; skipped.)")
        return 0
    if r.returncode != 0 or not (r.stdout or "").strip():
        print("  (LM Studio entry not written - is brag-app running?)")
        return 0
    try:
        cfg.write_text(r.stdout, encoding="utf-8")
        print("  [ OK ]  BRAG connected to LM Studio.")
    except OSError as e:
        print(f"  Could not write LM Studio mcp.json ({e}).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 — never break setup
        print(f"  LM Studio MCP config skipped ({e}).")
        sys.exit(0)
