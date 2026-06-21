"""Tests for the docker-compose override generator (brag.compose_gen)."""

from brag import compose_gen


def test_render_empty_is_noop():
    assert "services: {}" in compose_gen.render_override([])


def test_render_skips_default_project():
    # the default project uses the base /vault mount -> nothing added
    out = compose_gen.render_override([{"slug": "default", "host_path": "/x"}])
    assert "services: {}" in out


def test_render_mounts_additional_project():
    out = compose_gen.render_override([
        {"slug": "projekta", "host_path": "D:\\Arbeit\\Projekt A"},
    ])
    # backslashes -> forward slashes, quoted (handles the space), mounted at /projects/<slug>
    assert '"D:/Arbeit/Projekt A:/projects/projekta"' in out
    assert "services:" in out and "app:" in out and "volumes:" in out


def test_render_rejects_dollar_in_path():
    out = compose_gen.render_override([{"slug": "bad", "host_path": "D:/Ka$h/X"}])
    assert "SKIPPED bad" in out
    assert "Ka$h" not in out            # the unsafe path is never emitted
    assert ":/projects/bad" not in out  # and not mounted


def test_render_skips_missing_host_path():
    out = compose_gen.render_override([{"slug": "p", "host_path": ""}])
    assert "SKIPPED p" in out
    assert ":/projects/p" not in out


def test_write_override(tmp_path):
    p = compose_gen.write_override(workspace=tmp_path, projects=[
        {"slug": "projektb", "host_path": "C:/W/B"},
    ])
    assert p.name == "docker-compose.override.yml"
    assert '"C:/W/B:/projects/projektb"' in p.read_text(encoding="utf-8")
