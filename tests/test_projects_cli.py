import sys
import types

from brag import projects, registry


def _interactive(monkeypatch, answers):
    """Drive cmd_remove_interactive: fake a TTY + scripted input() answers."""
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(it))
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(isatty=lambda: True))


def test_cmd_remove_drops_project_keeps_others(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    registry.synthesize_default("D:/V", "asb_local_st_1024")
    registry.register("Projekt A", "D:/A", "asb_local_st_1024")  # -> slug projekt_a
    assert registry.get("projekt_a") is not None

    assert projects.cmd_remove("projekt_a", delete_index=False) == 0
    assert registry.get("projekt_a") is None      # removed
    assert registry.get("default") is not None    # other projects untouched
    # the compose override was regenerated next to the registry
    assert (tmp_path / "docker-compose.override.yml").exists()


def test_cmd_remove_unknown_returns_error(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    assert projects.cmd_remove("nope", delete_index=False) == 1


def test_cmd_remove_interactive_numbered_selection(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    registry.synthesize_default("D:/V", "asb_local_st_1024")        # [1] default
    registry.register("Projekt A", "D:/A", "asb_local_st_1024")     # [2] projekt_a
    _interactive(monkeypatch, ["2", "n"])   # pick the 2nd, keep its index
    assert projects.cmd_remove_interactive() == 0
    assert registry.get("projekt_a") is None       # the chosen one is gone
    assert registry.get("default") is not None      # the other is untouched


def test_cmd_remove_interactive_can_remove_the_default(monkeypatch, tmp_path):
    # The whole point of the fix: project 1 (the default) is removable individually,
    # not only via the full uninstall.
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    registry.synthesize_default("D:/Test Projekt 1", "asb_local_st_1024")
    registry.register("Projekt A", "D:/A", "asb_local_st_1024")
    _interactive(monkeypatch, ["1", "n"])   # the default is offered as [1]
    assert projects.cmd_remove_interactive() == 0
    assert registry.get("default") is None
    assert registry.get("projekt_a") is not None


def test_cmd_remove_interactive_cancel_changes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    registry.synthesize_default("D:/V", "asb_local_st_1024")
    registry.register("Projekt A", "D:/A", "asb_local_st_1024")   # 2 -> picker shown
    _interactive(monkeypatch, ["C"])
    assert projects.cmd_remove_interactive() == 2     # cancelled at the picker
    assert registry.get("default") is not None
    assert registry.get("projekt_a") is not None


def test_cmd_remove_interactive_invalid_index_changes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    registry.synthesize_default("D:/V", "asb_local_st_1024")
    registry.register("Projekt A", "D:/A", "asb_local_st_1024")
    _interactive(monkeypatch, ["9"])   # out of range
    assert projects.cmd_remove_interactive() == 2
    assert registry.get("default") is not None
    assert registry.get("projekt_a") is not None


def test_cmd_remove_interactive_refuses_last_project(monkeypatch, tmp_path):
    # The ONLY project cannot be removed via [1] (it would empty the registry and
    # the connector sync would re-add a bare 'brag'); send the user to [2] instead.
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    registry.synthesize_default("D:/V", "asb_local_st_1024")   # the only project
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(  # refused before any prompt -> input() must not be called
        "builtins.input",
        lambda prompt="": (_ for _ in ()).throw(AssertionError("input() called")))
    assert projects.cmd_remove_interactive() == 2
    assert registry.get("default") is not None


def test_cmd_remove_interactive_non_tty_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    registry.synthesize_default("D:/V", "asb_local_st_1024")
    registry.register("Projekt A", "D:/A", "asb_local_st_1024")   # 2 -> past the only-one guard
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(  # input() must never be reached in the fallback
        "builtins.input",
        lambda prompt="": (_ for _ in ()).throw(AssertionError("input() called")))
    assert projects.cmd_remove_interactive() == 2
    assert registry.get("default") is not None
    assert registry.get("projekt_a") is not None


def test_cmd_remove_interactive_empty_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    assert projects.cmd_remove_interactive() == 2   # nothing to remove
