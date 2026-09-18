"""A rename must not delete payload fields it does not recognise.

`patch_source_metadata` re-keys an indexed document after a rename/move without
re-embedding. Because `set_payload` only MERGES, custom fields defined by the OLD
folder's `_meta.txt` would survive a move into a folder that no longer defines
them (a stale `project=A` leaking across the project filter), so the function
sweeps them away first.

The sweep was written as "delete every key I cannot name": keep a hardcoded
`_PRESERVE` list, keep whatever `metadata_payload()` re-supplies, drop the rest.
That inverts the safe default. The list can only ever enumerate the fields THIS
codebase writes — and the index is not necessarily filled by this codebase. A
document ingested by an external pipeline carries fields no list here mentions,
and a single rename strips them from every chunk of that document. Silently: the
call reports "N chunks updated" and returns success.

Measured on a real 228-document corpus built by such a pipeline: every single
document would lose between 10 and 24 payload fields, among them the topic axis
used for filtering, the printed-page fields behind every citation, and the figure
references. Upstream widened the list by three keys after being bitten the same
way; widening it again would repeat the mistake rather than fix it.

The fix is to make the sweep precise instead of exhaustive: record at ingest
which keys came from a `_meta.txt`, and delete only those of them the new
location no longer defines. Then no content field can be touched, whoever wrote
it. A document with nothing recorded — every document indexed before this change
— loses nothing at all.
"""
import pytest

from brag import storage
from brag.ingest.extract import Chunk, metadata_payload
from pathlib import Path


class FakeClient:
    """Minimal Qdrant stand-in that really applies the payload operations, so the
    assertions below read the resulting state rather than the calls made."""

    def __init__(self, payloads):
        self.payloads = [dict(p) for p in payloads]

    def count(self, collection_name, count_filter=None, exact=True):
        return type("R", (), {"count": len(self.payloads)})()

    def scroll(self, collection_name, scroll_filter=None, limit=1,
               with_payload=True, with_vectors=False):
        pts = [type("P", (), {"payload": dict(p)})() for p in self.payloads[:limit]]
        return pts, None

    def delete_payload(self, collection_name, keys, points):
        for p in self.payloads:
            for k in keys:
                p.pop(k, None)

    def set_payload(self, collection_name, payload, points):
        for p in self.payloads:
            p.update(payload)


def _renamed(payloads, new_path="Fachbuch/KI/Autor_2024_Titel.pdf"):
    """Run a rename over these chunk payloads and return the resulting state."""
    client = FakeClient(payloads)
    payload = metadata_payload(Path(new_path))
    storage.patch_source_metadata(client, "Alt/Autor_2024_Titel", payload,
                                  collection_name="test_collection")
    return client.payloads


# ── The bug ──────────────────────────────────────────────────────────────────

# Exactly the fields a real chunk of the measured corpus carries beyond what this
# codebase knows how to name.
EXTERNAL_FIELDS = {
    "topic": "example-topic",   # Wert ohne Bedeutung: geprueft wird der SCHLUESSEL
    "title": "Titel des Werks",
    "pdf_page_start": 42, "pdf_page_end": 43,
    "page_label_start": "28", "page_label_end": "29",
    "page_basis": "pagelabels",
    "seq": 17, "token_count": 380,
    "picture_class": "none", "cr_version": "v3", "ingest_version": "7",
    "publisher": "Springer", "isbn": "978-3-16-148410-0",
    "images": ["fig_p42_1.png"],
}


def test_a_rename_keeps_fields_written_by_another_pipeline():
    """The measured failure: a document this codebase did not ingest is entered
    into the index with its own fields, and a rename must leave them alone."""
    chunk = {"text": "t", "context": "c", "chunk_type": "text",
             "source_file": "Alt/Autor_2024_Titel", "rel_path": "Alt/x.pdf",
             "page_start": 42, "page_end": 43, "chapter": "3", "section": "3.1",
             "doc_type": "Fachbuch", "author": "Autor", "year": "2024",
             "year_num": 2024, "language": "de", "chunk_id": "abc",
             "ingest_timestamp": "2026-01-01T00:00:00", **EXTERNAL_FIELDS}

    nachher = _renamed([chunk])[0]

    verloren = sorted(k for k in EXTERNAL_FIELDS if k not in nachher)
    assert not verloren, f"a rename deleted these fields: {verloren}"


def test_a_document_with_nothing_recorded_loses_nothing():
    """Every document indexed before this change has no record of its custom
    keys. The safe reading of "no record" is "delete nothing" — the opposite
    reading is the bug itself."""
    chunk = {"text": "t", "source_file": "Alt/X", "chunk_id": "a",
             "irgendein_feld": "wert", "noch_eins": 5}

    nachher = _renamed([chunk])[0]

    assert nachher["irgendein_feld"] == "wert"
    assert nachher["noch_eins"] == 5


# ── The purpose the sweep actually serves must keep working ──────────────────

def test_a_stale_custom_field_is_still_removed():
    """The reason the sweep exists: a `project=A` from the old folder's _meta.txt
    must not survive a move into a folder that no longer defines it, or it leaks
    across the project filter."""
    chunk = {"text": "t", "source_file": "Alt/X", "chunk_id": "a",
             "project": "A", "_meta_keys": ["project"]}

    nachher = _renamed([chunk])[0]

    assert "project" not in nachher, "the stale custom field survived the move"


def test_a_stale_looking_field_survives_without_any_record_or_caller_knowledge():
    """The direct contrast to the test above: the SAME field name, "project",
    looking exactly as stale — but this chunk has no `_meta_keys` record, and
    `_renamed()` (like a bare patch_source_metadata call) passes no
    `alte_meta_keys` either. Nothing tells the sweep this field ever came from
    a _meta.txt, so case 3 of the three-way rule applies: absent proof, the
    safe reading is "delete nothing" — never "this name looks like the kind of
    thing a _meta.txt would set, so guess and remove it". Guessing from the
    name is exactly the bug this whole change exists to close; only an actual
    record (`_meta_keys`) or actual caller knowledge (`alte_meta_keys`) may
    ever trigger a deletion."""
    chunk = {"text": "t", "source_file": "Alt/X", "chunk_id": "a",
             "project": "A"}

    nachher = _renamed([chunk])[0]

    assert nachher["project"] == "A", "a stale-looking field was deleted on a guess"


def test_a_custom_field_the_new_folder_still_defines_is_kept():
    """Only fields the new location no longer defines are stale. Here the new
    folder's _meta.txt still defines `project`, so the value is overwritten
    rather than removed."""
    chunk = {"text": "t", "source_file": "Alt/X", "chunk_id": "a",
             "project": "A", "_meta_keys": ["project"]}

    client = FakeClient([chunk])
    # what metadata_payload() yields for a folder whose _meta.txt says project: B
    payload = {"source_file": "Neu/X", "rel_path": "Neu/X.pdf", "author": "Autor",
               "year": "2024", "year_num": 2024, "doc_type": "Fachbuch",
               "_meta_keys": ["project"], "project": "B"}
    storage.patch_source_metadata(client, "Alt/X", payload,
                                  collection_name="test_collection")

    assert client.payloads[0]["project"] == "B", "the new folder's value must win"


def test_ingest_records_which_keys_came_from_a_meta_file():
    """Without this record the sweep cannot be precise — this is the field the
    fix reads."""
    chunk = Chunk(
        text="t", chunk_type="text", source_file="A/B", rel_path="A/B.pdf",
        page_start=1, page_end=1, chapter="", section="", doc_type="Fachbuch",
        author="Autor", year="2024",
        custom_meta={"project": "A", "kurs": "LOG200"},
    )

    p = chunk.payload()

    assert set(p.get("_meta_keys", [])) == {"project", "kurs"}


def test_a_document_without_custom_meta_records_an_empty_list():
    """An empty record still means "nothing to sweep" — and must not be confused
    with the absent record of an externally ingested document."""
    chunk = Chunk(
        text="t", chunk_type="text", source_file="A/B", rel_path="A/B.pdf",
        page_start=1, page_end=1, chapter="", section="", doc_type="Fachbuch",
        author="Autor", year="2024",
    )

    assert chunk.payload().get("_meta_keys") == []


def test_a_meta_file_cannot_dictate_what_a_rename_deletes():
    """`_meta_keys` is the record the removal reads, so a _meta.txt must not be
    able to write it. Otherwise a careless (or hostile) `_meta_keys: text` line
    in a corpus folder re-opens the very hole this record closes."""
    chunk = Chunk(
        text="t", chunk_type="text", source_file="A/B", rel_path="A/B.pdf",
        page_start=1, page_end=1, chapter="", section="", doc_type="Fachbuch",
        author="Autor", year="2024",
        custom_meta={"project": "A", "_meta_keys": ["text", "context"]},
    )

    p = chunk.payload()

    assert p["_meta_keys"] == ["project"], "a _meta.txt overwrote the record"
