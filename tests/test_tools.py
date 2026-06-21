"""Tests for the extracted tool logic (brag.tools) and hit formatting — the
file-based and formatting paths that need no Qdrant / models."""

from brag import config, tools
from brag.formatting import format_hit


def test_format_hit_source_has_link_citation_and_rerank(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"source_file": "papers/Smith.pdf", "rel_path": "sources/papers/Smith.pdf",
           "author": "Smith", "year": "2020", "page_start": 12, "doc_type": "paper",
           "chunk_type": "text", "text": "hello", "rerank_score": 0.5}
    out = format_hit(1, hit)
    assert "Smith (2020)" in out
    assert "p. 12" in out
    assert "localhost:8765/file/" in out
    assert "rerank: 0.500" in out


def test_format_hit_page_offset_shows_printed_page(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"source_file": "b.pdf", "rel_path": "sources/b.pdf", "page_start": 20,
           "page_offset": 8, "text": "x"}
    # printed page = physical (20) - offset (8) = 12; the link still uses page 20
    assert "p. 12" in format_hit(1, hit)


def test_format_hit_carries_project_in_link(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"source_file": "a.pdf", "rel_path": "sources/a.pdf", "page_start": 3,
           "text": "x"}
    assert "project=projekta" in format_hit(1, hit, project="projekta")
    assert "project=" not in format_hit(1, hit)  # single-project: no query param


def test_format_hit_passage(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"chunk_type": "passage", "topic": "Method", "text": "quote",
           "from_source": "Smith.pdf", "from_page": "5"}
    out = format_hit(1, hit)
    assert "saved passage" in out.lower()
    assert "Method" in out
    assert "originally from Smith.pdf" in out


def _vault(tmp_path, monkeypatch):
    # Set the default vault root; VAULT / SOURCES_DIR / NOTES_DIR / WIKI_DIR /
    # PASSAGES_DIR all derive from it via config.__getattr__.
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)


def test_write_then_read_note(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    msg = tools.write_note("methods/maturity.md", "# Maturity\nbody")
    assert "wiki/methods/maturity.md" in msg
    assert tools.read_note("wiki/methods/maturity.md").startswith("# Maturity")


def test_read_note_rejects_escape_and_non_notebook(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "x.md").write_text("secret", encoding="utf-8")
    assert "Refused" in tools.read_note("../outside.md")
    assert "only reads the notebook" in tools.read_note("sources/x.md")


def test_write_note_rejects_escape(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    assert "Refused" in tools.write_note("../../evil.md", "x")


def test_list_notebook_counts_wiki_and_notes(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    tools.write_note("a.md", "x")
    (tmp_path / "notes").mkdir(exist_ok=True)
    (tmp_path / "notes" / "Smith_2020.md").write_text("note", encoding="utf-8")
    out = tools.list_notebook()
    assert "wiki/ (1)" in out
    assert "notes/ (1)" in out
    assert "a.md" in out


def test_list_passages_empty_and_listing(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    assert "No passages" in tools.list_passages()
    pdir = tmp_path / "passages"
    pdir.mkdir()
    (pdir / "method.md").write_text(
        "# Passages: Method\n\n### Smith\n> quote\n", encoding="utf-8")
    out = tools.list_passages()
    assert "method" in out
    assert tools.list_passages("Method").startswith("# Passages: Method")
