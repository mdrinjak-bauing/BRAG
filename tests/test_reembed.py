"""Rebuilding the dense vectors of an existing index from its own payload.

Adding the document header to the dense text changes what a vector means. An
index built before it would otherwise be MIXED — old chunks embedded without the
header, new ones with — which is exactly the state a corpus should never be left
in. Since the payload already holds everything the dense text is built from,
the repair costs one pass of the embedder: no source files, no Docling, no LLM.
"""
from types import SimpleNamespace

import pytest

from brag.ingest import reembed


class _Punkt:
    def __init__(self, pid, payload):
        self.id, self.payload = pid, payload


class _Client:
    """Records what a real Qdrant client would have been asked to do."""

    def __init__(self, punkte, seiten=1):
        self._punkte, self._seiten = punkte, seiten
        self.updates = []
        self.closed = False

    def count(self, collection_name, exact=True):
        return SimpleNamespace(count=len(self._punkte))

    def scroll(self, collection_name, limit, offset=None,
               with_payload=True, with_vectors=False):
        i = 0 if offset is None else int(offset)
        teil = self._punkte[i:i + limit]
        weiter = i + limit if i + limit < len(self._punkte) else None
        return teil, weiter

    def update_vectors(self, collection_name, points):
        self.updates.extend(points)

    def close(self):
        self.closed = True


class _Embedder:
    def __init__(self):
        self.gesehen = []

    def embed_documents(self, texts):
        self.gesehen.extend(texts)
        return [[float(len(t)), 0.0] for t in texts]


@pytest.fixture
def welt(monkeypatch):
    emb = _Embedder()
    monkeypatch.setattr(reembed, "get_embedder", lambda: emb)
    return emb


def _payload(**kw):
    p = {"text": "Ein Satz.", "context": "", "author": "Hofstadler",
         "year": "2022", "doc_type": "Fachbuch", "chapter": "3 AV",
         "source_file": "b/Hofstadler 2022 - Produktivitaet im Bau"}
    p.update(kw)
    return p


def test_every_point_gets_a_new_dense_vector(welt):
    client = _Client([_Punkt(i, _payload()) for i in range(5)])
    bericht = reembed.reembed_dense(client=client, collection="c", batch=2)
    assert bericht["updated"] == 5
    assert [u.id for u in client.updates] == [0, 1, 2, 3, 4]


def test_the_embedded_text_carries_the_document_header(welt):
    client = _Client([_Punkt(1, _payload())])
    reembed.reembed_dense(client=client, collection="c")
    assert welt.gesehen == [
        "Hofstadler 2022 · Produktivitaet im Bau · Fachbuch\nEin Satz."
    ]


def test_the_sparse_vector_is_never_touched(welt):
    client = _Client([_Punkt(1, _payload())])
    reembed.reembed_dense(client=client, collection="c")
    geschrieben = client.updates[0].vector
    assert set(geschrieben) == {"dense"}, (
        "re-embedding must replace the dense vector only — rewriting sparse "
        "would put the header into BM25, the one place it must never go"
    )


def test_a_dry_run_writes_nothing_but_still_reports(welt):
    client = _Client([_Punkt(i, _payload()) for i in range(3)])
    bericht = reembed.reembed_dense(client=client, collection="c", dry_run=True)
    assert client.updates == []
    assert bericht["would_update"] == 3 and bericht["updated"] == 0


def test_a_point_without_text_is_skipped_not_embedded_as_empty(welt):
    client = _Client([_Punkt(1, _payload()), _Punkt(2, {"text": ""})])
    bericht = reembed.reembed_dense(client=client, collection="c")
    assert bericht["updated"] == 1 and bericht["skipped"] == 1
    assert len(welt.gesehen) == 1


def test_an_empty_collection_is_not_an_error(welt):
    client = _Client([])
    assert reembed.reembed_dense(client=client, collection="c")["updated"] == 0


# ── A metadata patch makes the dense vector stale ────────────────────────────
# The header is built from author, year, doc_type and source_file. All four are
# rewritten IN PLACE by storage.patch_source_metadata — on a rename, on a
# _meta.txt edit (the watcher does this by itself), and on set_metadata. The
# payload then says "Hofstadler" while the vector still says "Unknown". Nothing
# reported it, and the user was told no re-embedding was needed.

class _FilterClient(_Client):
    def __init__(self, punkte):
        super().__init__(punkte)
        self.filter_gesehen = "kein Aufruf"

    def count(self, collection_name, exact=True, count_filter=None):
        self.filter_gesehen = count_filter
        return super().count(collection_name, exact=exact)

    def scroll(self, collection_name, limit, offset=None, scroll_filter=None,
               with_payload=True, with_vectors=False):
        return super().scroll(collection_name, limit, offset,
                              with_payload, with_vectors)


def test_one_source_can_be_re_embedded_on_its_own(welt):
    client = _FilterClient([_Punkt(1, _payload())])
    bericht = reembed.reembed_dense(client=client, collection="c",
                                    source_file="Fachbuch/Hofstadler 2022 - X")
    assert bericht["updated"] == 1
    assert client.filter_gesehen not in (None, "kein Aufruf"), (
        "a per-source run must restrict the scroll to that source, not walk the "
        "whole collection"
    )


def test_a_rename_re_embeds_the_document_it_renamed(monkeypatch, tmp_path):
    """The metadata patch alone leaves the vector disagreeing with the payload."""
    from brag.ingest import pipeline
    gerufen = {}
    monkeypatch.setattr(pipeline.storage, "get_client", lambda: _Client([]))
    monkeypatch.setattr(pipeline.storage, "patch_source_metadata",
                        lambda *a, **k: 7)
    monkeypatch.setattr("brag.ingest.notes.rename_note", lambda *a, **k: None)
    monkeypatch.setattr(
        reembed, "reembed_dense",
        lambda **kw: gerufen.update(kw) or {"updated": 7, "skipped": 0},
    )
    neu = tmp_path / "Fachbuch" / "Hofstadler 2007 - Bauablaufplanung.pdf"
    neu.parent.mkdir(parents=True)
    neu.write_bytes(b"%PDF-1.4\n")
    n = pipeline.rename_source("Fachbuch/Hofstadler_2007_Bauablauf", neu)
    assert n == 7
    assert gerufen.get("source_file"), (
        "after patching the metadata in place, the renamed document's dense "
        "vectors still carry the OLD header and must be rebuilt"
    )


def test_the_command_repairs_every_project_not_just_the_default(monkeypatch, tmp_path):
    """Each project has its own collection (registry.collection_for). Repairing
    only the default one and reporting success would leave the others silently
    mixed, with nothing to discover them by — the watcher already loops this way.
    """
    from brag import config, registry
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "projects.json"))
    registry.register("Projekt A", str(tmp_path / "a"), "asb_local_st_1024")
    registry.register("Projekt B", str(tmp_path / "b"), "asb_local_st_1024")
    besucht = []
    monkeypatch.setattr(
        reembed, "reembed_dense",
        lambda **kw: besucht.append(config.COLLECTION_NAME) or
        {"updated": 1, "skipped": 0, "would_update": 0, "total": 1},
    )
    monkeypatch.setattr("sys.argv", ["reembed", "--dry-run"])
    reembed.main()
    assert len(besucht) == 2 and len(set(besucht)) == 2, besucht


def test_an_explicit_collection_overrides_the_project_loop(monkeypatch, tmp_path):
    from brag import registry
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "projects.json"))
    registry.register("Projekt A", str(tmp_path / "a"), "asb_local_st_1024")
    rufe = []
    monkeypatch.setattr(reembed, "reembed_dense",
                        lambda **kw: rufe.append(kw) or
                        {"updated": 0, "skipped": 0, "would_update": 0, "total": 0})
    monkeypatch.setattr("sys.argv", ["reembed", "--collection", "genau_die"])
    reembed.main()
    assert len(rufe) == 1 and rufe[0]["collection"] == "genau_die"


def test_a_misaligned_embedder_batch_is_refused_not_paired_by_position(monkeypatch):
    """pipeline.py carries this guard for the identical call and says why:
    pairing by position would write each chunk's vector onto a DIFFERENT chunk.
    Here that is worse still — the wrong vectors are written over good ones, and
    only a full re-ingest could undo it."""
    class _Kaputt:
        def embed_documents(self, texts):
            return [[1.0, 0.0]] * (len(texts) - 1)   # one short

    monkeypatch.setattr(reembed, "get_embedder", lambda: _Kaputt())
    client = _Client([_Punkt(i, _payload()) for i in range(3)])
    with pytest.raises(RuntimeError, match="refusing to pair"):
        reembed.reembed_dense(client=client, collection="c")
    assert client.updates == [], "nothing may be written once the batch is suspect"
