"""Tests for the per-project MCP data model + the additive/sync write of the
Claude Desktop config (brag.setup_core)."""

import json

from brag import registry, setup_core


def test_mcp_key_and_entry_default():
    assert setup_core.mcp_key_for(None) == "brag"
    assert setup_core.mcp_key_for("default") == "brag"
    e = setup_core.entry_for_slug(None)
    assert "brag.mcp_server" in e["args"]   # default keeps the battle-tested server
    assert "-e" not in e["args"]            # no BRAG_PROJECT for the default


def test_mcp_key_and_entry_project():
    assert setup_core.mcp_key_for("projekta") == "brag-projekta"
    e = setup_core.entry_for_slug("projekta")
    assert "brag.mcp_client" in e["args"]   # extra projects use the thin client
    assert "BRAG_PROJECT=projekta" in e["args"]


def test_connectors_for_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    assert set(setup_core.connectors_for_registry()) == {"brag"}  # empty -> default
    registry.synthesize_default("D:/V", "asb_x")    # slug 'default' -> 'brag'
    registry.register("ProjektA", "D:/A", "asb_x")  # -> 'brag-projekta'
    conns = setup_core.connectors_for_registry()
    assert set(conns) == {"brag", "brag-projekta"}
    assert "brag.mcp_server" in conns["brag"]["args"]
    assert "BRAG_PROJECT=projekta" in conns["brag-projekta"]["args"]


def test_write_claude_config_syncs_brag_connectors(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    monkeypatch.setenv("CLAUDE_CONFIG_MOUNTED", "1")
    cdir = tmp_path / "claude"
    cdir.mkdir()
    monkeypatch.setattr(setup_core, "CLAUDE_CONFIG_DIR", cdir)
    cfg = cdir / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {
        "other-tool": {"command": "x"},                       # foreign — must survive
        "brag": {"command": "old"},                           # default — updated
        "brag-gone": {"command": "stale"},                    # removed project — dropped
        "academic-rag-and-second-brain": {"command": "old"},  # legacy — migrated away
    }}), encoding="utf-8")
    registry.synthesize_default("D:/V", "asb_x")    # -> brag (default)
    registry.register("ProjektA", "D:/A", "asb_x")  # -> brag-projekta

    ok, _ = setup_core.write_claude_config()
    assert ok
    servers = json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"]
    assert set(servers) == {"other-tool", "brag", "brag-projekta"}
    assert servers["other-tool"] == {"command": "x"}          # untouched
    assert "brag.mcp_server" in servers["brag"]["args"]
    assert "BRAG_PROJECT=projekta" in servers["brag-projekta"]["args"]


def test_seed_vault_seeds_only_wissenswiki(tmp_path):
    setup_core.seed_vault_if_empty(tmp_path)
    wiki = tmp_path / "WissensWIKI"
    assert (wiki / "Passagen").is_dir()
    assert (wiki / "CLAUDE.md").exists()
    # The project ROOT is the corpus; the template must NOT land there (or the
    # guides/notes would be indexed and echo back into search).
    assert not (tmp_path / "Passagen").exists()
    assert not (tmp_path / "CLAUDE.md").exists()


def test_write_env_drops_stale_model_on_profile_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_core, "WORKSPACE", tmp_path)
    (tmp_path / ".env").write_text(
        "PROFILE=hybrid\nLLM_MODEL=gemma-4-12b-it\nVAULT_PATH=/vault\n", encoding="utf-8")
    setup_core.write_env("gemini", "KEY", "german")   # provider switch, no model passed
    out = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "gemma-4-12b-it" not in out                # stale local model dropped
    assert "PROFILE=gemini" in out


def test_write_env_keeps_api_key_on_same_profile_rerun(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_core, "WORKSPACE", tmp_path)
    (tmp_path / ".env").write_text(
        "PROFILE=gemini\nGEMINI_API_KEY=SECRET123\nVAULT_PATH=/vault\n", encoding="utf-8")
    setup_core.write_env("gemini", "", "german")   # same profile, NO new key entered
    out = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=SECRET123" in out       # kept -> no re-typing the key


def test_write_env_keeps_model_on_same_profile_rerun(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_core, "WORKSPACE", tmp_path)
    (tmp_path / ".env").write_text(
        "PROFILE=hybrid\nLLM_MODEL=gemma-4-12b-it\nVAULT_PATH=/vault\n", encoding="utf-8")
    setup_core.write_env("hybrid", "", "german")      # same-profile re-run keeps it
    out = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "LLM_MODEL=gemma-4-12b-it" in out


def test_seed_vault_is_idempotent_and_nondestructive(tmp_path):
    wiki = tmp_path / "WissensWIKI"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text("MY EDITS", encoding="utf-8")
    setup_core.seed_vault_if_empty(tmp_path)
    # an existing file is never overwritten ...
    assert (wiki / "CLAUDE.md").read_text(encoding="utf-8") == "MY EDITS"
    # ... but missing pieces are still added.
    assert (wiki / "Passagen").is_dir()
