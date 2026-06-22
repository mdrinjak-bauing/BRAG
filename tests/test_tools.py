"""Tests for the extracted tool logic (brag.tools) and hit formatting — the
file-based and formatting paths that need no Qdrant / models."""

from brag import config, tools
from brag.formatting import format_hit, parse_meta_filter


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
    assert "WissensWIKI/methods/maturity.md" in msg  # path is relative to WissensWIKI
    assert tools.read_note("methods/maturity.md").startswith("# Maturity")


def test_read_note_rejects_escape_and_non_notebook(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    config.PASSAGES_DIR.mkdir(parents=True, exist_ok=True)
    (config.PASSAGES_DIR / "p.md").write_text("quote", encoding="utf-8")
    assert "notebook" in tools.read_note("../outside.md")    # escape -> refused
    assert "notebook" in tools.read_note("Passagen/p.md")    # Passagen is indexed, not notebook


def test_write_note_rejects_escape(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    assert "Refused" in tools.write_note("../../evil.md", "x")
    assert "Refused" in tools.write_note("Passagen/sneak.md", "x")  # can't write the indexed area


def test_list_notebook_lists_wissenswiki(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    tools.write_note("a.md", "x")                          # -> WissensWIKI/a.md
    tools.write_note("Notizen/Smith_2020.md", "note")      # -> WissensWIKI/Notizen/...
    config.PASSAGES_DIR.mkdir(parents=True, exist_ok=True)
    (config.PASSAGES_DIR / "topic.md").write_text("p", encoding="utf-8")
    out = tools.list_notebook()
    assert "a.md" in out
    assert "Notizen/Smith_2020.md" in out
    assert "Passagen" not in out                           # indexed, not part of the notebook


def test_list_passages_empty_and_listing(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    assert "No passages" in tools.list_passages()
    config.PASSAGES_DIR.mkdir(parents=True, exist_ok=True)
    (config.PASSAGES_DIR / "method.md").write_text(
        "# Passages: Method\n\n### Smith\n> quote\n", encoding="utf-8")
    out = tools.list_passages()
    assert "method" in out
    assert tools.list_passages("Method").startswith("# Passages: Method")


def test_parse_meta_filter_normalises_and_drops_blanks():
    # both tool surfaces (tools.search_text + the thin mcp_client) share this:
    # keys lower-cased, spaces → underscores, blank key/value pairs dropped.
    assert parse_meta_filter("project=School Center") == {"project": "School Center"}
    assert parse_meta_filter("Course Name=CM, semester=WS25") == {
        "course_name": "CM", "semester": "WS25"}
    assert parse_meta_filter("") == {}
    assert parse_meta_filter("garbage, =noval, nokey=") == {}


def test_format_hit_offset_larger_than_page_falls_back(monkeypatch):
    # A bad/too-large page_offset must never produce a zero or negative printed
    # page — the citation falls back to the physical page (link unaffected).
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"source_file": "b.pdf", "rel_path": "sources/b.pdf", "page_start": 5,
           "page_offset": 20, "text": "x"}
    assert "p. 5" in format_hit(1, hit)


def test_format_hit_non_numeric_offset_is_ignored(monkeypatch):
    # A non-numeric page_offset (e.g. a typo'd _meta.txt) is treated as 0.
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"source_file": "b.pdf", "rel_path": "sources/b.pdf", "page_start": 12,
           "page_offset": "abc", "text": "x"}
    assert "p. 12" in format_hit(1, hit)


def test_search_text_threads_levers(monkeypatch):
    # The model-facing levers must reach run_search; 0/empty mean "use defaults"
    # (top_k -> None, max_per_source -> None, mode -> 'normal').
    captured = {}

    def fake_run_search(*a, **k):
        captured.clear()
        captured.update(k)
        return []

    monkeypatch.setattr(tools, "run_search", fake_run_search)
    tools.search_text("q", max_per_source=12, mode="deep", top_k=40)
    assert captured.get("max_chunks_per_source") == 12
    assert captured.get("mode") == "deep"
    assert captured.get("top_k") == 40
    tools.search_text("q")  # defaults
    assert captured.get("max_chunks_per_source") is None
    assert captured.get("top_k") is None
    assert captured.get("mode") == "normal"


def test_mode_presets_resolve():
    # mode maps to (top_k, max_per_source); an explicit value overrides the preset.
    from brag.search import query
    assert query._MODE_PRESETS["review"][0] >= 30      # broad survey = wide net
    assert query._MODE_PRESETS["deep"][1] >= 8          # deep = many per source
    assert query._MODE_PRESETS["precise"][0] <= 8       # precise = few hits
