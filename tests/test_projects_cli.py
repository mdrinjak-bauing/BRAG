from brag import projects, registry


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
