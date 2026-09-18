"""Tests for the extracted tool logic (brag.tools) and hit formatting — the
file-based and formatting paths that need no Qdrant / models."""

import pytest

from brag import config, tools, vault
from brag.formatting import format_hit, parse_meta_filter


def test_format_hit_source_has_link_citation_and_rerank(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    # This test covers the browser deep-link. Pin the optional click bridge to
    # off so an enabled one in the environment cannot swap the link format.
    monkeypatch.setattr(config, "OPEN_BRIDGE_ENABLED", False, raising=False)
    hit = {"source_file": "papers/Smith.pdf", "rel_path": "sources/papers/Smith.pdf",
           "author": "Smith", "year": "2020", "page_start": 12, "doc_type": "paper",
           "chunk_type": "text", "text": "hello", "rerank_score": 0.5}
    out = format_hit(1, hit)
    assert "Smith (2020)" in out
    # No /PageLabels and no page_offset, so 12 is the FILE's page count, not the
    # page printed on the paper — and the citation has to say which one it is.
    # ("p. 12" alone would also match "PDF p. 12" and pin nothing.)
    assert "PDF p. 12" in out
    assert "rerank: 0.500" in out
    # The raw deep-link also appears on its own line so clients that don't render
    # Markdown links (e.g. LM Studio) still show a clickable/copy-paste URL.
    assert "🔗 http://localhost:8765/file/" in out


def test_format_hit_passage_has_no_bare_link(monkeypatch):
    # Saved passages have no source PDF, so they carry no deep-link line.
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"chunk_type": "passage", "topic": "Method", "text": "quote"}
    assert "🔗" not in format_hit(1, hit)


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
    # This test covers the browser deep-link. Pin the optional click bridge to
    # off so an enabled one in the environment cannot swap the link format.
    monkeypatch.setattr(config, "OPEN_BRIDGE_ENABLED", False, raising=False)
    hit = {"source_file": "a.pdf", "rel_path": "sources/a.pdf", "page_start": 3,
           "text": "x"}
    assert "project=projekta" in format_hit(1, hit, project="projekta")
    assert "project=" not in format_hit(1, hit)  # single-project: no query param


def test_format_hit_cites_the_contribution_author_not_the_editor(monkeypatch):
    """In einem Sammelband ist der datei-weite `author` der HERAUSGEBER. Kennt ein
    Chunk seinen eigenen Verfasser, muss die Zitatzeile diesen nennen — sonst
    wandert ein Tagungsbandbeitrag unter fremdem Namen ins Manuskript, und zwar
    aus genau der Zeile, aus der zitiert wird."""
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"source_file": "BBB_2024", "rel_path": "sources/BBB_2024.pdf",
           "author": "BBB", "contribution_author": "Schmidt", "year": "2024",
           "page_start": 46, "page_label_start": "46", "text": "Beitragstext."}
    out = format_hit(1, hit)
    assert "Schmidt (2024)" in out
    assert "BBB (2024)" not in out


def test_format_hit_falls_back_to_the_file_author_without_a_contribution(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"source_file": "BBB_2024", "rel_path": "sources/BBB_2024.pdf",
           "author": "BBB", "year": "2024", "page_start": 46, "text": "x"}
    assert "BBB (2024)" in format_hit(1, hit)


def test_format_hit_cites_a_page_range_when_the_chunk_spans_pages(monkeypatch):
    """Ein Chunk kann ueber einen Seitenumbruch laufen. Der Treffer ist die einzige
    Stelle, an der das lesende Modell das Ende erfaehrt — save_passage uebernimmt
    seine Seitenwerte aus dem, was im Treffer stand, also faellt page_end sonst aus
    jedem spaeter abgelegten Beleg heraus."""
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    monkeypatch.setattr(config, "OPEN_BRIDGE_ENABLED", False, raising=False)
    gedruckt = {"source_file": "a", "rel_path": "sources/a.pdf", "page_start": 46,
                "page_end": 48, "page_label_start": "46", "page_label_end": "48",
                "text": "x"}
    assert "p. 46–48" in format_hit(1, gedruckt)
    # Der LINK bleibt auf der physischen Startseite, egal was das Zitat sagt.
    assert "#page=46" in format_hit(1, gedruckt)

    physisch = {"source_file": "a", "rel_path": "sources/a.pdf", "page_start": 46,
                "page_end": 48, "text": "x"}
    assert "PDF p. 46–48" in format_hit(1, physisch)

    versetzt = {"source_file": "a", "rel_path": "sources/a.pdf", "page_start": 56,
                "page_end": 58, "page_offset": 10, "text": "x"}
    assert "p. 46–48" in format_hit(1, versetzt)


def test_format_hit_prints_no_range_for_a_single_page(monkeypatch):
    """Kein Umbruch, kein Bereich: "S. 46–46" behauptet eine Ausdehnung, die es
    nicht gibt, und waere im Beleg genauso falsch wie eine fehlende Endseite."""
    from brag.formatting import page_span
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"source_file": "a", "rel_path": "sources/a.pdf", "page_start": 46,
           "page_end": 46, "page_label_start": "46", "page_label_end": "46",
           "text": "x"}
    assert "p. 46]" in format_hit(1, hit) or "p. 46](" in format_hit(1, hit)
    assert "–" not in format_hit(1, hit).splitlines()[0].split("](")[0]
    # Roemische/gemischte Labels haben keine arithmetische Ordnung.
    assert page_span("xii", "xiv") == "xii–xiv"
    assert page_span("xii", "xii") == "xii"
    assert page_span("A-3", None) == "A-3"


def test_format_hit_renders_the_generated_context_sentence(monkeypatch):
    """Der Kontext-Satz steckt im Payload und speist die Embeddings — wurde dem
    lesenden Modell aber nicht gezeigt. Genau das war die gemessene Beschwerde
    „der Kontext fehlt": ein Chunk, der mit einem Rueckverweis anfaengt
    („Diese Annahme …"), liest sich ohne ihn wie ein Fragment."""
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"source_file": "c.pdf", "rel_path": "sources/c.pdf", "page_start": 7,
           "context": "Abschnitt 3.2, Argument zur Qualitaetssicherung.",
           "text": "Diese Annahme traegt jedoch nur bedingt."}
    out = format_hit(1, hit)
    assert "> Kontext: Abschnitt 3.2, Argument zur Qualitaetssicherung." in out
    assert "Diese Annahme traegt jedoch nur bedingt." in out


def test_format_hit_without_a_context_stays_unchanged(monkeypatch):
    """Nicht jeder Chunk traegt einen Kontext (Altbestand, Tabellen, abgeschaltete
    Kontextualisierung) — dann darf keine leere Zitatzeile erscheinen."""
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    ohne = {"source_file": "c.pdf", "rel_path": "sources/c.pdf", "page_start": 7,
            "text": "Reiner Text."}
    leer = dict(ohne, context="   ")
    for hit in (ohne, leer):
        out = format_hit(1, hit)
        assert "Kontext" not in out
        assert out.endswith("Reiner Text.\n")


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
    assert "notebook" in tools.read_note("Quellenbelege/p.md")  # indexed, not notebook


def test_write_note_rejects_escape(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    assert "Refused" in tools.write_note("../../evil.md", "x")
    assert "Refused" in tools.write_note("Quellenbelege/sneak.md", "x")  # indexed area


def test_list_notebook_lists_wissenswiki(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    tools.write_note("a.md", "x")                          # -> WissensWIKI/a.md
    tools.write_note("Wissen/Smith_2020.md", "note")      # -> WissensWIKI/Wissen/...
    config.PASSAGES_DIR.mkdir(parents=True, exist_ok=True)
    (config.PASSAGES_DIR / "topic.md").write_text("p", encoding="utf-8")
    out = tools.list_notebook()
    assert "a.md" in out
    assert "Wissen/Smith_2020.md" in out
    assert "Quellenbelege" not in out                           # indexed, not part of the notebook


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


# ── vault_edit: chirurgischer In-Place-Edit (String-Ersetzung wie der Code-Editor) ──

def test_vault_edit_replaces_unique_string(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    (tmp_path / "note.md").write_text("Status: alt\nRest bleibt\n", encoding="utf-8")
    out = vault.vault_edit("note.md", "Status: alt", "Status: neu")
    assert out.startswith("✓")
    assert (tmp_path / "note.md").read_text(encoding="utf-8") == "Status: neu\nRest bleibt\n"


def test_vault_edit_missing_string_refused(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    (tmp_path / "note.md").write_text("hello", encoding="utf-8")
    out = vault.vault_edit("note.md", "absent", "x")
    assert "Text nicht gefunden" in out
    assert (tmp_path / "note.md").read_text(encoding="utf-8") == "hello"   # unverändert


def test_vault_edit_ambiguous_refused_unless_replace_all(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    (tmp_path / "note.md").write_text("x\nx\n", encoding="utf-8")
    out = vault.vault_edit("note.md", "x", "y")
    assert "nicht eindeutig" in out
    assert (tmp_path / "note.md").read_text(encoding="utf-8") == "x\nx\n"   # unverändert
    out2 = vault.vault_edit("note.md", "x", "y", replace_all=True)
    assert out2.startswith("✓")
    assert (tmp_path / "note.md").read_text(encoding="utf-8") == "y\ny\n"


def test_vault_edit_write_protected_and_missing_file(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "VAULT_WRITE_PROTECT", {"protected"}, raising=False)
    prot = tmp_path / "protected"
    prot.mkdir()
    (prot / "config.py").write_text("X = 1", encoding="utf-8")
    assert "Schreibgeschützt" in vault.vault_edit("protected/config.py", "X = 1", "X = 2")
    assert (prot / "config.py").read_text(encoding="utf-8") == "X = 1"     # unangetastet
    assert "Datei nicht gefunden" in vault.vault_edit("ghost.md", "a", "b")  # Edit ≠ Anlegen


def test_vault_edit_rejects_escape_and_noop(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    assert "außerhalb" in vault.vault_edit("../evil.md", "a", "b")
    (tmp_path / "n.md").write_text("a", encoding="utf-8")
    assert "identisch" in vault.vault_edit("n.md", "a", "a")              # No-op abgefangen


# ── Mehrwurzeligkeit: zweite benannte Vault-Wurzel (z. B. fh:) ──

def test_vault_multiroot_read_write_and_per_root_protection(tmp_path, monkeypatch):
    main, fh = tmp_path / "promotion", tmp_path / "fh"
    main.mkdir(); fh.mkdir()
    monkeypatch.setattr(config, "_DEFAULT_VAULT", main)
    monkeypatch.setattr(config, "EXTRA_VAULT_ROOTS", {"fh": str(fh)}, raising=False)
    # schreiben + lesen in der FH-Wurzel über das Präfix; Ausgabe trägt das Präfix
    out = vault.vault_write("fh:Lehre/note.md", "hi")
    assert out.startswith("✓") and "fh:Lehre/note.md" in out
    assert (fh / "Lehre" / "note.md").read_text(encoding="utf-8") == "hi"
    assert vault.vault_read("fh:Lehre/note.md") == "hi"
    # Default-Vault schützt den konfigurierten Ordner weiterhin …
    monkeypatch.setattr(config, "VAULT_WRITE_PROTECT", {"protected"}, raising=False)
    (main / "protected").mkdir()
    (main / "protected" / "c.py").write_text("X", encoding="utf-8")
    assert "Schreibgeschützt" in vault.vault_write("protected/c.py", "Y", overwrite=True)
    # … der Schutz gilt aber NUR im Default-Vault, nicht in der Extra-Wurzel
    assert vault.vault_write("fh:protected/ok.md", "z").startswith("✓")
    # Escape aus der FH-Wurzel wird abgewiesen
    assert "außerhalb" in vault.vault_read("fh:../escape.md")


def test_vault_list_extra_root(tmp_path, monkeypatch):
    main, fh = tmp_path / "promotion", tmp_path / "fh"
    main.mkdir(); fh.mkdir()
    (fh / "Lehre").mkdir()
    monkeypatch.setattr(config, "_DEFAULT_VAULT", main)
    monkeypatch.setattr(config, "EXTRA_VAULT_ROOTS", {"fh": str(fh)}, raising=False)
    out = vault.vault_list("fh:")
    assert "fh:Lehre/" in out


def test_vault_search_extra_root(tmp_path, monkeypatch):
    main, fh = tmp_path / "promotion", tmp_path / "fh"
    main.mkdir(); fh.mkdir()
    (fh / "Lehre").mkdir()
    (fh / "Lehre" / "modul.md").write_text("Thema: Baurecht Vertiefung", encoding="utf-8")
    monkeypatch.setattr(config, "_DEFAULT_VAULT", main)
    monkeypatch.setattr(config, "EXTRA_VAULT_ROOTS", {"fh": str(fh)}, raising=False)
    # FH durchsuchen → Treffer mit fh:-Präfix
    out = vault.vault_search("baurecht", root="fh")
    assert "fh:Lehre/modul.md" in out
    # unbekannte Wurzel wird abgewiesen
    assert "Unbekannte" in vault.vault_search("x", root="zz")
    # Default-Vault-Suche findet FH-Inhalt NICHT (getrennte Wurzeln)
    assert "Keine Vault-Datei" in vault.vault_search("baurecht")


# ── vault_extract: expliziter Binär-Pfad (PDF/Word/Excel), Standard bleibt vault_read ──

def test_vault_extract_dispatch_and_guards(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    (tmp_path / "n.md").write_text("# hi", encoding="utf-8")
    assert "vault_read" in vault.vault_extract("n.md")          # Text → verweist auf vault_read
    (tmp_path / "x.zip").write_text("zip", encoding="utf-8")
    assert "unterstützt" in vault.vault_extract("x.zip")        # nicht unterstütztes Format
    assert "Datei nicht gefunden" in vault.vault_extract("ghost.pdf")
    assert "außerhalb" in vault.vault_extract("../e.pdf")        # Escape


def test_vault_extract_docx_roundtrip(tmp_path, monkeypatch):
    docx = pytest.importorskip("docx")                          # python-docx optional
    _vault(tmp_path, monkeypatch)
    d = docx.Document()
    d.add_paragraph("Hallo aus Word")
    d.save(str(tmp_path / "brief.docx"))
    out = vault.vault_extract("brief.docx")
    assert "Hallo aus Word" in out and "brief.docx" in out


def test_vault_extract_xlsx_roundtrip(tmp_path, monkeypatch):
    openpyxl = pytest.importorskip("openpyxl")                  # openpyxl optional
    _vault(tmp_path, monkeypatch)
    wb = openpyxl.Workbook()
    wb.active["A1"] = "Pos"; wb.active["B1"] = 42
    wb.save(str(tmp_path / "lv.xlsx"))
    out = vault.vault_extract("lv.xlsx")
    assert "Pos" in out and "42" in out


# ── The citation must say WHICH page count it means ───────────────────────────
# A hit header read "p. 47" whether that 47 was the page printed on the paper or
# merely the 47th page of the file. Same word, same position, no way to tell —
# and for a book with front matter the two differ by the whole front matter. The
# number is now NAMED instead of marked: "p. 47" is the printed page, "PDF p. 47"
# is the file's own count. A renaming survives being copied into a manuscript;
# a trailing warning clause does not.

def _fmt(monkeypatch, **hit):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    basis = {"source_file": "b.pdf", "rel_path": "sources/b.pdf", "text": "x"}
    basis.update(hit)
    return format_hit(1, basis)


def test_page_without_labels_or_offset_is_named_as_the_pdf_page(monkeypatch):
    out = _fmt(monkeypatch, page_start=12)
    assert "PDF p. 12" in out, out
    # and NOT presented as the printed page
    assert "— p. 12]" not in out, out


def test_page_from_pdf_labels_is_the_printed_page(monkeypatch):
    out = _fmt(monkeypatch, page_start=24, page_label_start="xii")
    assert "— p. xii]" in out, out
    assert "PDF p." not in out, out


def test_page_from_offset_is_printed_but_says_where_it_came_from(monkeypatch):
    out = _fmt(monkeypatch, page_start=20, page_offset=8)
    assert "— p. 12]" in out, out       # 20 − 8, as before
    assert "PDF p." not in out, out
    assert "page_offset" in out, out    # named, so the reader can check it


def test_unusable_offset_falls_back_to_the_pdf_page(monkeypatch):
    # An offset larger than the page number cannot be right; showing "p. -5" or
    # silently keeping "p. 3" as if it were printed would both be worse.
    out = _fmt(monkeypatch, page_start=3, page_offset=20)
    assert "PDF p. 3" in out, out


def test_offset_value_never_reaches_the_markdown_link(monkeypatch):
    # page_offset is free text from _meta.txt — it is not in RESERVED_KEYS and is
    # never validated. A ')' or '>' in it must not be able to break the link.
    out = _fmt(monkeypatch, page_start=20, page_offset="8) [x](http://evil")
    kopf = out.splitlines()[0]
    assert "evil" not in kopf, kopf


def test_a_source_without_pages_is_cited_without_one(monkeypatch):
    # Docling gives no provenance for DOCX/PPTX, so _page_range returns (1, 1)
    # for every chunk. Printing "p. 1" on all of them invents a page number.
    out = _fmt(monkeypatch, rel_path="sources/notes.docx", page_start=1)
    assert "p. 1" not in out, out
    assert "PDF p." not in out, out


# ── The caveat must survive into the notebook, not be mangled ────────────────
# A hit now reads "PDF p. 61" when the printed page is unknown. The model passes
# what it read straight into save_passage's `page`, which prefixed it a second
# time: "### source, p. PDF p. 61". The prefix has to be applied only when it is
# not already there — and the caveat must be kept, because Quellenbelege is the
# file footnotes get written from.

def test_saved_passage_does_not_double_the_page_prefix():
    from brag.tools import cite_reference
    assert cite_reference("src", "PDF p. 61") == "src, PDF p. 61"
    assert cite_reference("src", "p. 61") == "src, p. 61"


def test_saved_passage_still_prefixes_a_bare_page():
    from brag.tools import cite_reference
    assert cite_reference("src", "61") == "src, p. 61"
    assert cite_reference("src", "xii") == "src, p. xii"


def test_saved_passage_without_a_page_is_unchanged():
    from brag.tools import cite_reference
    assert cite_reference("src", "") == "src"
    assert cite_reference("src", "   ") == "src"
