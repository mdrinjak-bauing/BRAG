"""Opt-in activity log: one JSONL line per SUCCESSFUL mutating operation.

Purpose: raw material for downstream automation (e.g. a nightly "wiki gardener"
that distills the day's activity into diary/overview drafts) — especially for
clients that leave no local chat transcript (Claude Desktop, phone). Only
METADATA is logged (operation, path/chapter/source, timestamp), never content.

Off by default; enabled by pointing BRAG_ACTIVITY_LOG at a file path. Give each
long-running process (bridge, remote server) its OWN file so concurrent appends
never interleave. A logging failure must NEVER break the actual operation —
every error here is swallowed (fail-safe no-op).

Not instrumented: the legacy topic-based save_passage layout (tools.save_passage)
and the corpus-admin ops (remove_source/rename_source) — pipeline maintenance,
not knowledge growth.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path


def log_op(op: str, **fields) -> None:
    """Append one activity line — silent, best effort, never raises."""
    try:
        target = os.environ.get("BRAG_ACTIVITY_LOG", "").strip()
        if not target:
            return
        line: dict = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                      "op": op}
        for key, value in fields.items():
            if value:
                line[key] = str(value)[:300]
        path = Path(target).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — logging must never break the real operation
        pass
