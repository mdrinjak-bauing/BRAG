"""Tests for the ingest-quality package: junk-figure filter, printed page
labels (PageLabels), related-sources note section, and the plain-language
status note — all file-/logic-level, no Qdrant/models needed."""

import base64
import io

import pytest

from brag import config
from brag.ingest import junk_filter, notes
from brag.ingest.extract import Chunk, _page_label_map, collision_report
from brag.formatting import format_hit


def _chunk(text="**Figure (p. 3):** No caption available", chunk_type="figure",
           context="", image_b64="", **kw):
    defaults = dict(source_file="papers/X", rel_path="papers/X.pdf",
                    page_start=3, page_end=3, chapter="", section="",
                    doc_type="paper", author="A", year="2024")
    defaults.update(kw)
    return Chunk(text=text, chunk_type=chunk_type, context=context,
                 image_b64=image_b64, **defaults)


def _tiny_png(w=40, h=40) -> str:
    image_mod = pytest.importorskip("PIL.Image")
    buf = io.BytesIO()
    image_mod.new("RGB", (w, h)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ── junk filter ──────────────────────────────────────────────────────────────

def test_strong_pattern_is_junk_even_with_caption():
    c = _chunk(text="**Figure (p. 3):** Abb. 5: Mehr Informationen",
               context="Diese Abbildung ist ein QR-Code mit einem Link.")
    junk, reason = junk_filter.is_junk_figure(c)
    assert junk and "QR" in reason


def test_weak_pattern_junk_only_without_caption():
    desc = "Die Abbildung zeigt das Logo der Bergischen Universität."
    uncaptioned = _chunk(context=desc)
    captioned = _chunk(text="**Figure (p. 3):** Abb. 1.2: Universitätsstandort",
                       context=desc)
    assert junk_filter.is_junk_figure(uncaptioned)[0] is True
    assert junk_filter.is_junk_figure(captioned)[0] is False


def test_english_patterns_and_thumbs_up():
    c = _chunk(context="The image shows a thumbs-up icon.")
    assert junk_filter.is_junk_figure(c)[0] is True
    c2 = _chunk(context="A Creative Commons license badge.",
                text="**Figure (p. 3):** CC BY 4.0")
    assert junk_filter.is_junk_figure(c2)[0] is True   # strong beats caption


def test_tiny_image_junk_only_without_caption():
    pytest.importorskip("PIL")
    uncaptioned = _chunk(image_b64=_tiny_png())
    captioned = _chunk(text="**Figure (p. 3):** Fig. 2: sensor detail",
                       image_b64=_tiny_png())
    junk, reason = junk_filter.is_junk_figure(uncaptioned)
    assert junk and "tiny" in reason
    assert junk_filter.is_junk_figure(captioned)[0] is False


def test_real_diagram_survives():
    c = _chunk(text="**Figure (p. 3):** Abb. 4: Implementierungsbarrieren",
               context="Diagramm zeigt KI-Implementierungsbarrieren im Bau.")
    assert junk_filter.is_junk_figure(c)[0] is False
    # Text/table chunks are never classified, whatever their content says.
    t = _chunk(text="Das Logo der Universität ist bekannt.", chunk_type="text")
    assert junk_filter.is_junk_figure(t)[0] is False


def test_drop_junk_figures_counts():
    chunks = [
        _chunk(context="ein QR-Code"),                       # junk (strong)
        _chunk(text="Ein normaler Absatz.", chunk_type="text"),
        _chunk(text="**Figure (p. 3):** Abb. 7: Prozessmodell",
               context="Flussdiagramm des Prozesses."),
    ]
    kept, dropped = junk_filter.drop_junk_figures(chunks)
    assert dropped == 1 and len(kept) == 2
    assert all(junk_filter.is_junk_figure(c)[0] is False for c in kept)


# ── page labels ──────────────────────────────────────────────────────────────

def test_page_label_payload_only_when_set():
    c = _chunk()
    assert "page_label_start" not in c.payload()
    c.page_label_start, c.page_label_end = "xii", "xiii"
    p = c.payload()
    assert p["page_label_start"] == "xii" and p["page_label_end"] == "xiii"


def test_page_label_map_non_pdf_and_missing_file(tmp_path):
    assert _page_label_map(tmp_path / "doc.docx") == {}
    # A .pdf path that does not exist (or pypdfium2 unavailable) must yield {}
    # without raising — labels are an enhancement, never a blocker.
    assert _page_label_map(tmp_path / "ghost.pdf") == {}


def test_format_hit_label_beats_offset(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hit = {"source_file": "b", "rel_path": "b.pdf", "page_start": 20,
           "page_offset": 8, "page_label_start": "xii", "text": "x"}
    out = format_hit(1, hit)
    assert "p. xii" in out          # label wins the citation ...
    assert "page=20" in out or "#page=20" in out or "b.pdf" in out
    # ... while the offset fallback still works when no label is present.
    hit.pop("page_label_start")
    assert "p. 12" in format_hit(1, hit)


# ── related sources in literature notes ──────────────────────────────────────

def test_write_note_renders_related_and_preserves_user_notes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    chunks = [_chunk(text="Absatz.", chunk_type="text", chapter="1 Einleitung")]
    notes.write_note(chunks, related=[("papers/Nachbar", 0.87),
                                      ("buecher/Werk", 0.81)])
    note = (config.NOTES_DIR / "papers__X.md").read_text(encoding="utf-8")
    assert "## Related sources" in note
    assert "[[papers__Nachbar|papers/Nachbar]] — similarity 0.870" in note
    # User text below "## My notes" survives a re-ingest rewrite.
    (config.NOTES_DIR / "papers__X.md").write_text(
        note + "\nMeine eigene Erkenntnis.\n", encoding="utf-8")
    notes.write_note(chunks, related=[("papers/Anders", 0.5)])
    again = (config.NOTES_DIR / "papers__X.md").read_text(encoding="utf-8")
    assert "Meine eigene Erkenntnis." in again
    assert "papers__Anders" in again and "papers__Nachbar" not in again


def test_write_note_without_related_has_no_section(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    notes.write_note([_chunk(text="Absatz.", chunk_type="text")], related=[])
    assert "## Related sources" not in (
        config.NOTES_DIR / "papers__X.md").read_text(encoding="utf-8")


# ── status note ──────────────────────────────────────────────────────────────

def test_status_note_written_german_with_bad_qdrant(tmp_path, monkeypatch):
    from brag import status_note
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    monkeypatch.setattr(config, "VAULT_LANGUAGE", "german", raising=False)
    monkeypatch.setattr(config, "QDRANT_URL", "http://127.0.0.1:9", raising=False)
    status_note.write_status_note()
    out = (config.WISSENSWIKI_DIR / "SYSTEM-STATUS.md").read_text(encoding="utf-8")
    assert "System-Status" in out
    assert "❌" in out                       # unreachable search DB is visible
    assert "Profil:" in out


def test_status_note_english_and_never_raises(tmp_path, monkeypatch):
    from brag import status_note
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    monkeypatch.setattr(config, "VAULT_LANGUAGE", "english", raising=False)
    monkeypatch.setattr(config, "QDRANT_URL", "http://127.0.0.1:9", raising=False)
    status_note.write_status_note()
    out = (config.WISSENSWIKI_DIR / "SYSTEM-STATUS.md").read_text(encoding="utf-8")
    assert "System status" in out and "Profile:" in out


# ── Collision guard ───────────────────────────────────────────────────────────
# A duplicate Qdrant id is a SILENT loss: the second point overwrites the first,
# nothing raises, and the counters keep reporting the number of chunks we built.
# chunk_id hashes the full text so this should never happen — these tests keep
# the guard honest if that ever changes.

def _text_chunk(text, page=1):
    return _chunk(text=text, chunk_type="text", page_start=page, page_end=page)


def test_collision_report_silent_on_distinct_chunks():
    chunks = [_text_chunk("first"), _text_chunk("second"), _text_chunk("third", 2)]
    assert collision_report(chunks) is None


def test_collision_report_names_the_loss():
    chunks = [_text_chunk("same"), _text_chunk("same"), _text_chunk("other")]
    msg = collision_report(chunks)
    assert msg is not None
    assert "1 of 3" in msg and "2 would be stored" in msg


def test_collision_report_same_text_different_page_is_fine():
    # page_start is part of chunk_id, so a repeated header on two pages is safe.
    assert collision_report([_text_chunk("same"), _text_chunk("same", 2)]) is None
