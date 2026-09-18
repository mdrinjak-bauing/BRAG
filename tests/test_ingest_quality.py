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


# ── A rename must not wipe the printed page labels ────────────────────────────
# patch_source_metadata deletes stale custom fields from the old folder's
# _meta.txt so they cannot survive a move (e.g. a stale `project=A` leaking
# into project B). Which keys count as stale is no longer a hardcoded
# _PRESERVE set (Aufgabe 3 removed it): the precise answer is the sampled
# chunk's own `_meta_keys` record (Chunk.payload, extract.py), naming exactly
# which keys IT owes to a _meta.txt; a caller-supplied `alte_meta_keys` is the
# fallback for a chunk indexed before that record existed; with neither,
# nothing is deleted. page_label_start/_end and image_file are content, not
# folder metadata — metadata_payload() never carries them (extract.py) and no
# chunk ever records them in `_meta_keys`, so they can never be swept either
# way. Before this record existed, renaming a file — or merely editing a
# _meta.txt, which the watcher re-applies by itself (watcher.py:70, :220) —
# silently stripped the printed pages and the figure images from every chunk
# of a document. The citation then degraded from the printed page to the
# physical PDF page with no visible change in the hit.

class _PatchClient:
    """Minimal stand-in for the Qdrant client used by patch_source_metadata.
    Takes the actual sampled-point payload dict (not just a list of key names)
    so a test can control real values, e.g. an explicit `_meta_keys` list."""

    def __init__(self, payload):
        self._payload = dict(payload)
        self.deleted = None
        self.patched = None

    def count(self, collection_name, count_filter, exact):
        from types import SimpleNamespace
        return SimpleNamespace(count=7)

    def scroll(self, collection_name, scroll_filter, limit,
               with_payload, with_vectors):
        from types import SimpleNamespace
        return [SimpleNamespace(payload=dict(self._payload))], None

    def delete_payload(self, collection_name, keys, points):
        self.deleted = sorted(keys)

    def set_payload(self, collection_name, payload, points):
        self.patched = dict(payload)


def test_rename_keeps_printed_page_labels_and_figure_images():
    """The realistic case: a document ingested after Aufgabe 3, so the sampled
    chunk carries its own `_meta_keys` record — the precise path, case 1 of the
    three-way rule in patch_source_metadata."""
    from brag import storage
    client = _PatchClient({
        "source_file": "x", "page_start": "x", "text": "x",
        "page_label_start": "x", "page_label_end": "x", "image_file": "x",
        "projekt": "x",  # a genuinely stale custom field from the old folder
        "_meta_keys": ["projekt"],  # recorded at ingest: owed to a _meta.txt
    })
    storage.patch_source_metadata(
        client, "alt.pdf", {"source_file": "neu.pdf"}, collection_name="c",
    )
    weg = set(client.deleted or [])
    assert "page_label_start" not in weg and "page_label_end" not in weg, (
        f"a rename deletes the printed page labels: {sorted(weg)}"
    )
    assert "image_file" not in weg, (
        f"a rename deletes the figure image: {sorted(weg)}"
    )
    assert "projekt" in weg, "the genuinely stale custom field must still go"


def test_alte_meta_keys_still_cleans_up_a_chunk_indexed_before_the_record_existed():
    """The migration case: a chunk indexed before Aufgabe 3 carries no
    `_meta_keys` at all, so the precise path (case 1) has nothing to read. The
    caller may then name what it separately knows — rename_source does this by
    reading the OLD folder's still-existing `_meta.txt` chain (case 2 of the
    three-way rule) — and the sweep still finds the stale field. Without this
    fallback, every already-indexed document would stop being cleaned up on
    rename forever, not just until its next re-ingest."""
    from brag import storage
    client = _PatchClient({
        "source_file": "x", "page_label_start": "x", "image_file": "x",
        "projekt": "x",  # stale, but unprovable from the payload alone
    })
    storage.patch_source_metadata(
        client, "alt.pdf", {"source_file": "neu.pdf"}, collection_name="c",
        alte_meta_keys={"projekt"},
    )
    weg = set(client.deleted or [])
    assert "projekt" in weg, "alte_meta_keys must still let the migration case clean up"
    assert "page_label_start" not in weg and "image_file" not in weg, (
        "alte_meta_keys must not sweep content fields it was never told about: "
        f"{sorted(weg)}"
    )


def test_every_chunk_payload_key_survives_a_rename_except_a_named_stale_one():
    """The bug class, not just the three keys that fell into it.

    A rename patches the payload with metadata_payload() and then sweeps stale
    keys. Any key a chunk writes must therefore either be re-supplied by
    metadata_payload() or simply not be named as stale — otherwise adding a
    field to Chunk.payload() silently makes a rename destroy it, months later
    and with no error.

    The sweep mechanism changed (Aufgabe 3): it no longer reads a hardcoded
    `_PRESERVE` set out of the source text — that variable no longer exists,
    so a test introspecting for it would now always fail regardless of
    correctness — but reads the chunk's own recorded `_meta_keys`. This test
    exercises that mechanism end to end (real Chunk.payload() through real
    patch_source_metadata) instead of parsing it out of source code, so the
    check keeps testing the actual behaviour rather than a text pattern.
    """
    from brag import storage
    from brag.ingest.extract import metadata_payload
    from pathlib import Path

    chunk = _chunk(
        chunk_type="text", text="t", context="c", image_file="figures/a.jpg",
        page_label_start="xii", page_label_end="xiii",
        custom_meta={"projekt": "A"},
    )
    geschrieben = chunk.payload()
    assert geschrieben["_meta_keys"] == ["projekt"]  # sanity: the record exists

    client = _PatchClient(geschrieben)
    neuer_ordner_payload = metadata_payload(Path("papers/A_2024_X.pdf"))  # no "projekt"
    storage.patch_source_metadata(client, chunk.source_file, neuer_ordner_payload,
                                  collection_name="c")

    weg = set(client.deleted or [])
    verloren = weg - {"projekt"}
    assert not verloren, (
        "these payload keys are written at ingest but were swept away by a "
        "rename that should only remove what this chunk's own _meta_keys "
        f"record names: {sorted(verloren)}"
    )
    assert "projekt" in weg, "the one field the record actually names must still be removed"


def test_every_structural_payload_key_is_named_in_reserved_or_overridable_keys():
    """The drift guard the test above no longer provides.

    The original test_every_chunk_payload_key_survives_a_rename computed
    `chunk_payload_keys - metadata_payload_keys - _PRESERVE` and went red
    whenever ANY new field was added to Chunk.payload() without being
    accounted for somewhere — "the bug class, not just the three keys that
    fell into it" (its own docstring). The rewrite above
    (test_every_chunk_payload_key_survives_a_rename_except_a_named_stale_one)
    pins one concrete scenario end to end through the real sweep, which is
    worth keeping on its own — but with `weg` constructed so it can only ever
    contain `{"projekt"}` by construction, its assertion cannot go red no
    matter what Chunk.payload() writes. The drift property is gone.

    Under the new design the equivalent invariant is structural rather than
    behavioural: every key Chunk.payload() writes OTHER than what custom_meta
    contributes — the system's own fields — must be named in RESERVED_KEYS or
    OVERRIDABLE_KEYS. Both sets are exactly what _parse_meta_file and
    payload()'s own custom-field computation filter custom_meta against. If a
    new structural field is ever added to payload() but forgotten in both
    sets, a _meta.txt happening to define a key of that same name would then
    both silently overwrite the structural value at ingest (no longer
    filtered out as reserved) AND get treated as if it belonged to that
    _meta.txt, so a later rename into a folder without that key would sweep
    the SYSTEM field away as if it were stale custom data — the same bug
    class this whole file exists to guard against, narrowed to "which keys is
    a _meta.txt even allowed to touch". `_meta_keys` itself needs no separate
    allowance here: Aufgabe 3 already put it inside RESERVED_KEYS, precisely
    so a _meta.txt cannot dictate it (see test_a_meta_file_cannot_dictate_
    what_a_rename_deletes in test_rename_payload.py).

    Verified today: 20 structural keys, 0 uncovered.
    """
    from brag.ingest.extract import OVERRIDABLE_KEYS, RESERVED_KEYS

    chunk = _chunk(
        chunk_type="text", text="t", context="c", image_file="figures/a.jpg",
        page_label_start="xii", page_label_end="xiii",
        custom_meta={"projekt": "A"},
    )
    strukturell = set(chunk.payload()) - {"projekt"}
    unbekannt = strukturell - (RESERVED_KEYS | OVERRIDABLE_KEYS)
    assert not unbekannt, (
        "Chunk.payload() writes structural keys that neither RESERVED_KEYS "
        "nor OVERRIDABLE_KEYS names, so a same-named _meta.txt field could "
        "overwrite them at ingest and a rename could later sweep them away "
        f"as if they were stale custom data: {sorted(unbekannt)}"
    )


# ── A label that CONFIRMS the physical page is a result, not a non-result ─────
# The post-pass stored page_label_start only when the label DIFFERED from the
# physical page. So "the PDF says its page 12 is printed 12" — a verification —
# was thrown away, and became indistinguishable from "this PDF has no labels at
# all". The display then had to call an exactly-correct page "PDF p. 12".

def test_a_label_equal_to_the_physical_page_is_still_recorded():
    from brag.ingest.extract import apply_page_labels
    c = _chunk(text="t", chunk_type="text", page_start=12, page_end=12)
    apply_page_labels([c], {12: "12"})
    assert c.page_label_start == "12", (
        "a label confirming the physical page is a verification and must be kept"
    )


def test_a_roman_label_still_wins():
    from brag.ingest.extract import apply_page_labels
    c = _chunk(text="t", chunk_type="text", page_start=4, page_end=5)
    apply_page_labels([c], {4: "xii", 5: "xiii"})
    assert (c.page_label_start, c.page_label_end) == ("xii", "xiii")


def test_a_chunk_on_an_unlabelled_page_gets_nothing():
    from brag.ingest.extract import apply_page_labels
    c = _chunk(text="t", chunk_type="text", page_start=99, page_end=99)
    apply_page_labels([c], {4: "xii"})
    assert c.page_label_start == "" and "page_label_start" not in c.payload()


def test_an_empty_label_map_changes_nothing():
    from brag.ingest.extract import apply_page_labels
    c = _chunk(text="t", chunk_type="text", page_start=4, page_end=4)
    apply_page_labels([c], {})
    assert c.page_label_start == ""


# ── The document header in the dense vector ──────────────────────────────────
# A chunk's vector saw only its context and its text, so it carried no trace of
# WHICH work it came from. "What does Hofstadler write about productivity" then
# had to match on the body text alone. Prepending a short, deterministic header
# (author year · title · type) is the port of the sister pipeline's dense_text.
#
# It goes into the DENSE vector only: an identical header on every chunk of a
# work would blur document discrimination in the BM25 index, where every chunk
# of the book would then match "Hofstadler".
#
# The CHAPTER is deliberately NOT in the header: every chunk's text already
# opens with "[Chapter: …]" (extract.py:396-405), so repeating it would put the
# noisiest field into the vector twice.

def test_header_names_author_year_title_and_type():
    from brag.ingest.extract import document_header
    h = document_header(author="Hofstadler", year="2007", doc_type="Fachbuch",
                        source_file="Fachbuch/Hofstadler_2007_Bauablaufplanung_und_Logistik")
    assert h == "Hofstadler 2007 · Bauablaufplanung und Logistik · Fachbuch"


def test_header_reads_the_title_out_of_the_other_filename_form():
    from brag.ingest.extract import document_header
    # parse_filename also accepts "Author YYYY - Title"; the title is what
    # follows the dash, and the author/year must not be repeated inside it.
    h = document_header(author="Hofstadler", year="2007", doc_type="Fachbuch",
                        source_file="Fachbuch/Hofstadler 2007 - Bauablaufplanung")
    assert h == "Hofstadler 2007 · Bauablaufplanung · Fachbuch"
    assert h.count("Hofstadler") == 1 and h.count("2007") == 1


def test_header_keeps_a_filename_that_IS_the_title():
    from brag.ingest.extract import document_header
    # Books are often filed under their own name — exactly the ones that gain
    # most from being findable under it.
    h = document_header(doc_type="Fachbuch", source_file="buecher/Die Bauleiterschule")
    assert h == "Die Bauleiterschule · Fachbuch"


def test_header_drops_a_stem_that_is_neither_parseable_nor_a_title():
    from brag.ingest.extract import document_header
    # "scan_04_final" has no four-digit year, so parse_filename reads no author
    # from it either; the stem reads as a filename, not as a work title.
    h = document_header(doc_type="Fachbuch", source_file="x/scan_04_final")
    assert h == "Fachbuch"


def test_header_omits_fields_that_are_not_set():
    from brag.ingest.extract import document_header
    # year empty -> omitted, but author, title and type still appear
    assert document_header(author="Smith", year="", doc_type="paper",
                           source_file="p/Smith_2020_X") == "Smith · X · paper"


def test_header_never_invents_an_unknown_author():
    from brag.ingest.extract import document_header
    # parse_filename yields "Unknown"/"????" when it cannot read them; putting
    # those into every vector of the document is worse than saying nothing.
    h = document_header(author="Unknown", year="????", doc_type="paper",
                        source_file="p/x_y")
    assert "Unknown" not in h and "????" not in h and h == "paper"


def test_empty_metadata_yields_no_header():
    from brag.ingest.extract import document_header
    assert document_header(source_file="x/a_b") == ""


def test_header_parts_are_normalised():
    """Observed on real data: extracted values arrive with runs of spaces and
    sometimes lead with a separator of their own, which would then render as an
    empty field ("Fachbuch · · …")."""
    from brag.ingest.extract import document_header
    h = document_header(author="  Leimböck ", year="2015", doc_type="· Fachbuch  ",
                        source_file="b/Leimböck 2015 - Baukalkulation  und  Controlling")
    assert h == "Leimböck 2015 · Baukalkulation und Controlling · Fachbuch"


def test_a_part_that_is_only_punctuation_is_dropped():
    from brag.ingest.extract import document_header
    assert document_header(author="X", year="2020", doc_type="—",
                           source_file="p/X 2020 - Y") == "X 2020 · Y"


def test_the_chapter_is_not_repeated_in_the_header():
    """extract.py:396-405 already prefixes every text chunk with
    "[Chapter: …]", so the chapter is in the embedded text either way."""
    c = _chunk(text="[Chapter: 4 Logistik]\nDer Text.", chunk_type="text",
               author="Hofstadler", year="2007", doc_type="Fachbuch",
               chapter="4 Logistik",
               source_file="Fachbuch/Hofstadler 2007 - Bauablaufplanung")
    kopf = c.dense_text().split("\n")[0]
    assert kopf == "Hofstadler 2007 · Bauablaufplanung · Fachbuch"
    assert c.dense_text().count("4 Logistik") == 1


def test_dense_text_carries_the_header_and_sparse_text_does_not():
    c = _chunk(text="Produktivität hängt von der Arbeitsvorbereitung ab.",
               chunk_type="text", context="Kapitel 3 behandelt …",
               author="Hofstadler", year="2007", doc_type="Fachbuch",
               source_file="Fachbuch/Hofstadler 2007 - Bauablaufplanung")
    dicht, bm25 = c.dense_text(), c.embedding_text()
    assert dicht.startswith("Hofstadler 2007 · Bauablaufplanung · Fachbuch\n")
    assert dicht.endswith(bm25)
    assert "Hofstadler" not in bm25, (
        "the header must stay out of the BM25 text — an identical header on every "
        "chunk of a work destroys document discrimination there"
    )


def test_dense_text_without_metadata_equals_the_plain_text():
    c = _chunk(text="x", chunk_type="text", author="Unknown", year="????",
               doc_type="", source_file="a/b_c")
    assert c.dense_text() == c.embedding_text()
