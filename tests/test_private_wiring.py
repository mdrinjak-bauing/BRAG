"""The private layer is only useful if it is actually WIRED IN.

Both features below shipped once as modules that nothing imported: the click
bridge (hit links pointing at the local PDF viewer) and the activity log (raw
material for downstream automation). Each file was present, each was importable,
and neither did anything. Import tests would not have caught that — these do.

Nothing here asserts the layout of a link or a log line; that is covered
elsewhere. These tests only pin the wiring: enabled means used, and every
mutating operation reports itself.
"""
import json
from pathlib import Path

import pytest

from brag import config, tools, vault
from brag.formatting import format_hit

HIT = {"source_file": "Mueller_2020", "rel_path": "sources/Mueller_2020.pdf",
       "author": "Müller", "year": "2020", "page_start": 12,
       "pdf_page_start": 26, "text": "Ein Satz."}


def test_click_bridge_off_by_default_keeps_the_browser_link(monkeypatch):
    monkeypatch.setattr(config, "OPEN_BRIDGE_ENABLED", False, raising=False)
    assert "/open?source=" not in format_hit(1, dict(HIT))


def test_click_bridge_when_enabled_is_actually_used(monkeypatch):
    """The regression this guards: open_bridge.py present but imported nowhere,
    so the switch existed and changed nothing."""
    monkeypatch.setattr(config, "OPEN_BRIDGE_ENABLED", True, raising=False)
    out = format_hit(1, dict(HIT))
    assert "/open?source=Mueller_2020" in out
    assert "pdf_page=26" in out, "the stored physical page must go through as-is"


def _ports_in_a_fresh_interpreter(bridge_port: str) -> tuple[int, int]:
    """(BRIDGE_PORT, OPEN_BRIDGE_PORT) as a fresh import of brag.config computes
    them — both are read at import time, so this process's values say nothing."""
    import os
    import subprocess
    import sys
    env = dict(os.environ)
    env["BRIDGE_PORT"] = bridge_port
    env.pop("BRAG_OPEN_BRIDGE_PORT", None)
    lauf = subprocess.run(
        [sys.executable, "-c",
         "from brag import config; print(config.BRIDGE_PORT, config.OPEN_BRIDGE_PORT)"],
        capture_output=True, text=True, env=env,
        cwd=str(Path(__file__).resolve().parent.parent), check=True)
    a, b = lauf.stdout.split()
    return int(a), int(b)


def test_click_bridge_port_cannot_collide_with_the_http_bridge():
    """Both defaulted to 8765 once. The click bridge binds a real socket, so a
    collision costs the feature silently (the bind error is swallowed).

    This used to assert `config.OPEN_BRIDGE_PORT != config.BRIDGE_PORT`, which is
    true by construction — the default IS BRIDGE_PORT + 1, so the assertion could
    not fail. What CAN fail is the DERIVATION: a hardcoded literal drifts back into
    a collision the moment BRIDGE_PORT is moved, and BRIDGE_PORT is a documented
    deployment knob. So move it and check the click bridge follows.
    """
    for gesetzt in ("8765", "9100"):
        http_port, klick_port = _ports_in_a_fresh_interpreter(gesetzt)
        assert http_port == int(gesetzt)
        assert klick_port != http_port, f"collision at BRIDGE_PORT={gesetzt}"
        assert klick_port == http_port + 1


def test_the_hit_link_uses_the_configured_click_bridge_port(monkeypatch):
    """The port in the link and the port the server binds are the same value read
    live — a link pointing at a port nobody listens on fails exactly as silently."""
    from brag import open_bridge
    monkeypatch.setattr(config, "OPEN_BRIDGE_PORT", 9993, raising=False)
    assert ":9993/open?" in open_bridge.open_link("Mueller_2020", 3)
    assert open_bridge._port() == 9993


@pytest.fixture
def vault_mit_log(tmp_path, monkeypatch):
    """A throwaway vault plus a capture file for the activity log.

    config.VAULT comes from the module __getattr__ (_SCOPED_ATTRS) — patching it
    with setattr would plant a real attribute and poison the whole session, so
    the vault is swapped via project_context instead.
    """
    root = tmp_path.resolve()
    (root / "WissensWIKI" / "Wissen").mkdir(parents=True)
    (root / "WissensWIKI" / "Quellenbelege").mkdir(parents=True)
    # An ordinary corpus subfolder — the only kind set_metadata may write in.
    (root / "Berichte").mkdir()
    log = tmp_path / "activity.jsonl"
    monkeypatch.setenv("BRAG_ACTIVITY_LOG", str(log))
    with config.project_context({"vault": str(root)}):
        yield log


def _ops(log) -> list:
    if not log.exists():
        return []
    return [json.loads(z)["op"] for z in log.read_text(encoding="utf-8").splitlines() if z.strip()]


def test_every_mutating_op_reports_itself(vault_mit_log):
    """Was 1 of 9 call sites: only save_passage logged, so everything written or
    moved through the notebook and the vault dropped out of the record.

    set_metadata is exercised on an ordinary corpus subfolder. It used to be called
    with folder="" here — the vault ROOT, which the tool accepted because it had no
    write-protection check at all. That made this wiring test double as a pin on the
    hole; the two refusal tests below now cover the boundary, and this one only
    proves the log entry.
    """
    tools.write_note("Wissen/a.md", "Text")
    tools.move_note("Wissen/a.md", "Wissen/b.md")
    tools.delete_note("Wissen/b.md", confirm=True)
    assert "Abgelehnt" not in tools.set_metadata("Berichte", "topic", "x")
    vault.vault_write("WissensWIKI/Wissen/c.md", "Inhalt")
    vault.vault_append("WissensWIKI/Wissen/c.md", "\nmehr")
    vault.vault_edit("WissensWIKI/Wissen/c.md", "Inhalt", "Neu")

    assert _ops(vault_mit_log) == [
        "write_note", "move_note", "delete_note", "set_metadata",
        "vault_write", "vault_append", "vault_edit",
    ]


def test_set_metadata_refuses_a_write_protected_folder(vault_mit_log, monkeypatch):
    """set_metadata does not just drop a _meta.txt — reapply_folder_metadata then
    rewrites author/year/doc_type/rel_path on every indexed chunk below that folder.
    On a protected top-level folder (read-only corpus, code area) that is a silent
    corpus-wide relabelling, and the tool is reachable from the remote server."""
    root = Path(config.VAULT)
    (root / "Korpus").mkdir()
    monkeypatch.setattr(config, "VAULT_WRITE_PROTECT", {"Korpus"}, raising=False)

    antwort = tools.set_metadata("Korpus", "topic", "x")

    assert "Abgelehnt" in antwort and "VAULT_WRITE_PROTECT" in antwort
    assert not (root / "Korpus" / "_meta.txt").exists()
    assert _ops(vault_mit_log) == [], "a refused write must not be logged as one"


def test_set_metadata_refuses_the_vault_root(vault_mit_log):
    """SOURCES_DIR is the vault root itself, so folder="" resolves to the root and
    would relabel the WHOLE corpus in one call — the widest blast radius the tool
    has, and it needs no protected-folder configuration to reach."""
    root = Path(config.VAULT)

    antwort = tools.set_metadata("", "topic", "x")

    assert "Abgelehnt" in antwort
    assert not (root / "_meta.txt").exists()
    assert _ops(vault_mit_log) == []


def test_the_log_stays_off_when_no_target_is_configured(vault_mit_log, monkeypatch):
    """Opt-in: without BRAG_ACTIVITY_LOG nothing is written anywhere."""
    monkeypatch.delenv("BRAG_ACTIVITY_LOG", raising=False)
    vault.vault_write("WissensWIKI/Wissen/d.md", "Inhalt")
    assert _ops(vault_mit_log) == []
