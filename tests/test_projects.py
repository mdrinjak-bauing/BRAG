"""Tests for the project-management CLI (brag.projects)."""

from brag import projects, registry


def _reg(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "projects.json"))


def test_add_creates_project_and_override(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    assert projects.main(["add", "My Thesis", "D:/Arbeit/Thesis"]) == 0
    recs = registry.projects()
    assert len(recs) == 1 and recs[0]["slug"] == "my_thesis"
    override = (tmp_path / "docker-compose.override.yml").read_text(encoding="utf-8")
    assert "/projects/my_thesis" in override          # the project mount
    assert "/registry/projects.json:ro" in override   # the registry mount


def test_add_rejects_bad_path(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    assert projects.main(["add", "Bad", "D:/has$dollar"]) == 1
    assert registry.projects() == []


def test_remove_project(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    projects.main(["add", "ProjektA", "D:/A"])
    assert projects.main(["remove", "projekta"]) == 0
    assert registry.get("projekta") is None
    assert projects.main(["remove", "projekta"]) == 1   # already gone


def test_migrate_synthesizes_default(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    import brag.setup_core as sc
    monkeypatch.setattr(sc, "WORKSPACE", tmp_path)
    (tmp_path / ".env").write_text(
        "VAULT_PATH=D:/Old/Vault\nCOLLECTION_NAME=asb_legacy_1024\n", encoding="utf-8")
    assert projects.main(["migrate"]) == 0
    d = registry.get("default")
    assert d is not None
    assert d["collection"] == "asb_legacy_1024"   # reused verbatim — no re-embed
    assert projects.main(["migrate"]) == 0         # idempotent


def test_usage_errors():
    assert projects.main([]) == 2
    assert projects.main(["add", "only-name"]) == 2
    assert projects.main(["bogus"]) == 2
