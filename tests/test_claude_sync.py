"""Tests for brag.claude_sync — the single connector-merge used by the host
launchers (piped via docker exec) and by the in-container write."""

import json

from brag import claude_sync, registry


def test_sync_empty_config_gets_default(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    out = json.loads(claude_sync.sync(""))
    assert set(out["mcpServers"]) == {"brag"}  # empty registry -> default connector


def test_sync_preserves_foreign_and_syncs_projects(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    registry.synthesize_default("D:/V", "asb_x")     # default folder "V" -> brag-v
    registry.register("ProjektA", "D:/A", "asb_x")   # -> brag-projekta
    current = json.dumps({"mcpServers": {
        "other": {"command": "x"},                       # foreign — keep
        "brag": {"command": "old"},                      # old bare default — replaced
        "brag-gone": {"command": "stale"},               # removed project — drop
        "academic-rag-and-second-brain": {"command": "legacy"},  # legacy — migrate away
    }})
    out = json.loads(claude_sync.sync(current))["mcpServers"]
    assert set(out) == {"other", "brag-v", "brag-projekta"}
    assert out["other"] == {"command": "x"}
    assert "BRAG_PROJECT=projekta" in out["brag-projekta"]["args"]


def test_sync_invalid_json_degrades(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    out = json.loads(claude_sync.sync("{ not valid"))
    assert "brag" in out["mcpServers"]  # resets to a fresh config + the default


def test_sync_refuses_to_clobber_malformed_mcpservers(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "p.json"))
    # mcpServers PRESENT but not an object (corrupt config): must NOT be
    # overwritten — returned unchanged, no 'brag' key added (MP-F10).
    out = json.loads(claude_sync.sync(json.dumps({"mcpServers": ["oops"], "keep": 1})))
    assert out["mcpServers"] == ["oops"]   # preserved, not clobbered
    assert out["keep"] == 1
