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
