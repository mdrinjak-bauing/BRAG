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


def test_health_exclude_reason(monkeypatch):
    # The status check classifies each top-level folder; this is the rule it uses.
    from brag import health
    monkeypatch.setattr(config, "EXCLUDE_DIRS", {"Rohdaten"})
    assert health._exclude_reason(config.WISSENSWIKI_NAME)   # workspace
    assert health._exclude_reason(".git")                    # hidden
    assert health._exclude_reason("_Archiv")                 # underscore
    assert health._exclude_reason("Rohdaten")                # EXCLUDE_DIRS
    assert health._exclude_reason("Vertraege") == ""         # normal -> indexed


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


# ── Docs must not send users to the wrong folder ──────────────────────────────
# setup.command/.bat write .env, docker-compose.yml and the *.command helpers
# into the "BRAG Assistent" PROGRAM folder; into the project folder they write
# only WissensWIKI/. Eight docs in both languages nevertheless told the user to
# open .env "in the project folder" — including the fix for the most common
# setup failure (port already in use), which therefore could not work.

def test_setup_writes_env_into_the_program_folder_not_the_project_folder():
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    setup = (repo / "setup.command").read_text(encoding="utf-8")
    assert '> "$ENGINE/.env"' in setup, "setup writes .env into the engine folder"
    assert '> "$PROJDIR/.env"' not in setup, "nothing writes .env into the project folder"


def test_docs_do_not_locate_env_or_compose_in_the_project_folder():
    import re
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    # Both directions, both languages, on a single line.
    muster = re.compile(
        r"(\.env|docker\s+compose\s+(?:down|up|build|logs))[^\n]{0,40}"
        r"(project folder|Projektordner)"
        r"|(project folder|Projektordner)[^\n]{0,40}"
        r"(\.env|docker\s+compose\s+(?:down|up|build|logs))",
        re.IGNORECASE,
    )
    # "your project folder (documents + wiki) stays untouched" is a correct
    # statement about the project folder, not an instruction to go there. The
    # sentence wraps, so the exemption has to look at the following line too.
    erlaubt = re.compile(r"(stays untouched|bleibt .{0,25}unangetastet)", re.I)
    treffer = []
    for datei in sorted((repo / "docs").glob("*.md")):
        zeilen = datei.read_text(encoding="utf-8").splitlines()
        for nr, zeile in enumerate(zeilen, 1):
            umfeld = " ".join(zeilen[nr - 1 : nr + 1])
            if erlaubt.search(umfeld):
                continue
            if muster.search(zeile):
                treffer.append(f"{datei.name}:{nr}: {zeile.strip()[:70]}")
    assert not treffer, (
        "These lines point users at the project folder for files that live in the "
        "BRAG Assistent folder:\n  " + "\n  ".join(treffer)
    )


# ── Local profile: the model choice decides whether figures get described ─────
# The profile's text model IS the vision model (contextualize.py:323 checks
# llm.vision_capable). A text-only model makes every figure fall back to
# caption-only context — the run says so, but only mid-ingest and only after two
# failures. The place a user picks the model must say it up front.

def _profiles_doc(sprache: str) -> str:
    from pathlib import Path
    name = "PROFILES.de.md" if sprache == "de" else "PROFILES.md"
    return (Path(__file__).resolve().parents[1] / "docs" / name).read_text(encoding="utf-8")


def test_profiles_doc_warns_that_the_local_model_must_be_multimodal_en():
    text = _profiles_doc("en").lower()
    assert "multimodal" in text, (
        "docs/PROFILES.md never tells the reader that the local model must be "
        "multimodal — a text-only model silently reduces every figure to its caption"
    )


def test_profiles_doc_warns_that_the_local_model_must_be_multimodal_de():
    text = _profiles_doc("de").lower()
    assert "multimodal" in text, (
        "docs/PROFILES.de.md never tells the reader that the local model must be "
        "multimodal — a text-only model silently reduces every figure to its caption"
    )


def test_readme_names_the_same_local_default_as_the_code():
    # The README offered qwen2.5-7b-instruct as *the* example while profiles.py
    # defaulted to google/gemma-3-27b-it. A reader following the README loads a
    # model the profile never asks for — and a text-only one at that.
    from pathlib import Path
    from brag.profiles import PROFILES
    modell = PROFILES["hybrid"]["llm_model"]
    repo = Path(__file__).resolve().parents[1]
    fehlt = [n for n in ("README.md", "README.de.md")
             if modell not in (repo / n).read_text(encoding="utf-8")]
    assert not fehlt, (
        f"{', '.join(fehlt)} never mentions the local default {modell!r} from "
        "profiles.py — docs and code have drifted apart"
    )


def test_version_is_the_same_everywhere():
    """pyproject.toml promises "keep in sync with brag/__init__.py:__version__"
    but nothing enforced it, and the READMEs carry the number twice each. Six
    places, no check — so a release could ship saying two different things."""
    import re
    from pathlib import Path
    from brag import __version__
    repo = Path(__file__).resolve().parents[1]

    toml = (repo / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M)
    assert m and m.group(1) == __version__, (
        f"pyproject.toml says {m.group(1) if m else None!r}, "
        f"brag/__init__.py says {__version__!r}"
    )
    for name in ("README.md", "README.de.md"):
        text = (repo / name).read_text(encoding="utf-8")
        gefunden = set(re.findall(r"[Vv]ersion:?\*{0,2}\s*\*{0,2}(\d+\.\d+\.\d+)", text))
        assert gefunden == {__version__}, (
            f"{name} names version(s) {sorted(gefunden)}, code says {__version__!r}"
        )
    changelog = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{__version__}]" in changelog, (
        f"CHANGELOG.md has no released section for {__version__} — either the "
        "bump is half-done or [Unreleased] was never closed"
    )


def test_both_readmes_name_every_tool_the_server_registers():
    """Eight tools — open_pdf and the whole vault_* file layer — existed for
    releases without appearing in either README, so users had no way to learn
    that BRAG can read and write the files in their project folder at all.

    Parsed from the source rather than imported, so this holds whichever mcp
    major version is installed.
    """
    import re
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    quelle = (repo / "brag" / "mcp_server.py").read_text(encoding="utf-8")
    werkzeuge = re.findall(r"@mcp\.tool\(\)\s*\ndef (\w+)", quelle)
    assert len(werkzeuge) >= 20, f"only {len(werkzeuge)} tools parsed — did the syntax change?"
    for name in ("README.md", "README.de.md"):
        text = (repo / name).read_text(encoding="utf-8")
        fehlt = [w for w in werkzeuge if f"`{w}`" not in text]
        assert not fehlt, f"{name} never mentions these tools: {fehlt}"


def _fastembed_cache_in_a_fresh_interpreter(env_wert):
    """Der Pin passiert beim IMPORT von brag.config — in diesem Prozess ist der
    Import laengst gelaufen, also in einem frischen Interpreter messen."""
    import os
    import subprocess
    import sys
    env = dict(os.environ)
    env.pop("FASTEMBED_CACHE_PATH", None)
    if env_wert is not None:
        env["FASTEMBED_CACHE_PATH"] = env_wert
    lauf = subprocess.run(
        [sys.executable, "-c",
         "import os, brag.config; print(os.environ.get('FASTEMBED_CACHE_PATH', ''))"],
        capture_output=True, text=True, env=env,
        cwd=str(Path(__file__).resolve().parent.parent), check=True)
    return lauf.stdout.strip()


def test_the_fastembed_cache_is_pinned_away_from_tmpdir():
    """Ohne Pin cacht fastembed unter $TMPDIR, das macOS periodisch leert. Bei
    kaltem Cache faellt SparseTextEmbedding OHNE Warnung auf eine LEERE
    Stoppwortliste zurueck; die so indexierten Dokumente behalten ihre Stoppwoerter
    im BM25-Vektor, was doc_len aufblaeht und jedes Termgewicht dieses Dokuments
    gegenueber dem restlichen Korpus druckt — es rankt danach lautlos zu tief."""
    pfad = _fastembed_cache_in_a_fresh_interpreter(None)
    assert pfad, "kein FASTEMBED_CACHE_PATH gesetzt — fastembed cacht unter $TMPDIR"
    assert "/tmp" not in pfad and "/T/" not in pfad, f"Cache liegt im Wegwerf-Bereich: {pfad}"


def test_an_explicitly_exported_fastembed_cache_still_wins():
    """setdefault, nicht Zuweisung: eine Deployment-Vorgabe darf nicht ueberschrieben
    werden (z. B. ein gemeinsamer Cache im Container-Volume)."""
    assert _fastembed_cache_in_a_fresh_interpreter("/eigener/cache") == "/eigener/cache"
