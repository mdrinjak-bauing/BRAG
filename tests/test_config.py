"""Tests for the multi-project ContextVar scoping in brag.config:
config.project_context() must swap the vault paths + COLLECTION_NAME for the
duration of the block, reset cleanly, and NOT leak across threads."""

import threading
from pathlib import Path

from brag import config, registry


def test_defaults_outside_any_context(monkeypatch):
    monkeypatch.setattr(config, "_DEFAULT_VAULT", Path("/vault"))
    monkeypatch.setattr(config, "_DEFAULT_COLLECTION", "asb_default")
    assert config.VAULT == Path("/vault")
    assert config.SOURCES_DIR == Path("/vault")                    # corpus = project root
    assert config.WISSENSWIKI_DIR == Path("/vault/WissensWIKI")
    assert config.PASSAGES_DIR == Path("/vault/WissensWIKI/Quellenbelege")
    assert config.NOTEBOOK_DIR == Path("/vault/WissensWIKI")
    assert config.NOTES_DIR == Path("/vault/WissensWIKI/Wissen")
    assert config.DATA_DIR == Path("/vault/WissensWIKI/.brag")
    assert config.INGEST_LOG == Path("/vault/WissensWIKI/.brag/ingest_log.jsonl")
    assert config.COLLECTION_NAME == "asb_default"


def test_is_corpus_path(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    # corpus: documents anywhere in the project root (incl. subfolders)
    assert config.is_corpus_path(tmp_path / "Berichte" / "x.pdf")
    assert config.is_corpus_path(tmp_path / "y.pdf")
    # NOT corpus: the whole WissensWIKI workspace (incl. Quellenbelege), hidden, _inbox
    assert not config.is_corpus_path(tmp_path / "WissensWIKI" / "note.md")
    assert not config.is_corpus_path(tmp_path / "WissensWIKI" / "Quellenbelege" / "p.md")
    assert not config.is_corpus_path(tmp_path / "_inbox" / "z.pdf")
    assert not config.is_corpus_path(tmp_path / ".brag" / "log.jsonl")
    assert not config.is_corpus_path(tmp_path.parent / "elsewhere.pdf")  # outside vault


def test_is_corpus_path_underscore_convention(tmp_path, monkeypatch):
    # The visible "don't index" convention: any folder OR file whose name starts
    # with "_" is skipped — at any depth — without touching .env.
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    monkeypatch.setattr(config, "EXCLUDE_DIRS", set())
    assert not config.is_corpus_path(tmp_path / "_Archiv" / "old.pdf")
    assert not config.is_corpus_path(tmp_path / "Projekt" / "_draft" / "x.pdf")
    assert not config.is_corpus_path(tmp_path / "_scratch.pdf")
    # a normal sibling stays indexed
    assert config.is_corpus_path(tmp_path / "Archiv" / "keep.pdf")


def test_is_corpus_path_explicit_exclude_dirs(tmp_path, monkeypatch):
    # The wizard's explicit top-level exclude list (matched on the first segment).
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    monkeypatch.setattr(config, "EXCLUDE_DIRS", {"Rohdaten", "Privat"})
    assert not config.is_corpus_path(tmp_path / "Rohdaten" / "raw.csv")
    assert not config.is_corpus_path(tmp_path / "Privat" / "a" / "b.pdf")
    # only the top level matches: a deeper "Rohdaten" folder is still corpus
    assert config.is_corpus_path(tmp_path / "Projekt" / "Rohdaten" / "x.pdf")
    assert config.is_corpus_path(tmp_path / "Berichte" / "x.pdf")


def test_project_context_scopes_and_resets(monkeypatch):
    monkeypatch.setattr(config, "_DEFAULT_VAULT", Path("/vault"))
    monkeypatch.setattr(config, "_DEFAULT_COLLECTION", "asb_default")
    rec = {"vault": "/projects/a", "collection": "asb_default__a"}
    with config.project_context(rec):
        assert config.VAULT == Path("/projects/a")
        assert config.SOURCES_DIR == Path("/projects/a")
        assert config.PASSAGES_DIR == Path("/projects/a/WissensWIKI/Quellenbelege")
        assert config.NOTEBOOK_DIR == Path("/projects/a/WissensWIKI")
        assert config.COLLECTION_NAME == "asb_default__a"
    # restored after the block
    assert config.VAULT == Path("/vault")
    assert config.COLLECTION_NAME == "asb_default"


def test_project_context_by_slug(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "projects.json"))
    monkeypatch.setattr(config, "_DEFAULT_COLLECTION", "asb_default")
    registry.register("ProjektA", "D:/A", "asb_default")  # -> asb_default__projekta
    with config.project_context("projekta"):
        assert config.COLLECTION_NAME == "asb_default__projekta"
    assert config.COLLECTION_NAME == "asb_default"
    # unknown slug falls back to defaults (no crash)
    with config.project_context("ghost"):
        assert config.COLLECTION_NAME == "asb_default"


def test_project_context_does_not_leak_across_threads(monkeypatch):
    # CRITICAL: a watcher/bridge worker thread must NOT inherit another's project
    # context, or one project's collection could bleed into another's ingest.
    monkeypatch.setattr(config, "_DEFAULT_COLLECTION", "asb_default")
    seen = {}

    def worker():
        seen["collection"] = config.COLLECTION_NAME

    with config.project_context({"collection": "asb_other"}):
        assert config.COLLECTION_NAME == "asb_other"
        t = threading.Thread(target=worker)
        t.start()
        t.join()
    # the spawned thread saw the DEFAULT, not the main thread's active context
    assert seen["collection"] == "asb_default"


def test_nested_project_context(monkeypatch):
    monkeypatch.setattr(config, "_DEFAULT_COLLECTION", "asb_default")
    with config.project_context({"collection": "asb_a"}):
        assert config.COLLECTION_NAME == "asb_a"
        with config.project_context({"collection": "asb_b"}):
            assert config.COLLECTION_NAME == "asb_b"
        assert config.COLLECTION_NAME == "asb_a"  # inner reset restores outer
    assert config.COLLECTION_NAME == "asb_default"
