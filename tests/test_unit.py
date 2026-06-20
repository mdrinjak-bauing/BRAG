"""Light unit tests — no heavy runtime deps (no torch / qdrant / docling), so CI
can run them without installing the full image. They lock in the pure helpers
most worth protecting from regression:

- B1: path-qualified source identity (same-named files in different folders
  must produce distinct keys).
- H2: page-aware chunk splitting (a chunk reports the real page range of the
  paragraphs it contains, not the section's first page).
- the .env value sanitizer (no newline injection from wizard input).
"""

from brag import config
from brag.ingest.chunking import hard_split, split_text, split_text_paged
from brag.setup_core import _env_safe


# ── B1: source identity ─────────────────────────────────────────
def test_source_key_top_level_is_plain_stem():
    assert config.source_key_from_path(config.SOURCES_DIR / "Bericht.pdf") == "Bericht"


def test_source_key_is_path_qualified_and_distinct():
    a = config.source_key_from_path(config.SOURCES_DIR / "projectA" / "Bericht.pdf")
    b = config.source_key_from_path(config.SOURCES_DIR / "projectB" / "Bericht.pdf")
    assert a == "projectA/Bericht"
    assert b == "projectB/Bericht"
    assert a != b  # same filename, different folders → no collision (no data loss)


def test_normalize_source_key_idempotent():
    n = config.normalize_source_key("Bericht_2021")
    assert config.normalize_source_key(n) == n


def test_source_key_variants_nonempty():
    assert config.source_key_variants("projectA/Bericht")


# ── chunk_id collision-resistance (full-text hash, not a 120-char prefix) ──
def _mk_chunk(text):
    from brag.ingest.extract import Chunk
    return Chunk(
        text=text, chunk_type="text", source_file="A/x",
        rel_path="sources/A/x.pdf", page_start=1, page_end=1,
        chapter="", section="", doc_type="doc", author="", year="",
        language="en",
    )


def test_chunk_id_distinguishes_same_120char_prefix():
    # Two distinct chunks whose first 120 chars are identical (a long
    # "[Chapter…][Section…]" prefix, boilerplate, or split table parts) must NOT
    # collide on one id — else one silently overwrites the other on upsert.
    common = "x" * 200
    a, b = _mk_chunk(common + " ALPHA"), _mk_chunk(common + " BETA")
    assert a.chunk_id != b.chunk_id
    assert a.qdrant_id() != b.qdrant_id()


def test_chunk_id_deterministic_for_identical_chunk():
    # Same content+location → same id, so an idempotent re-ingest overwrites in
    # place instead of duplicating.
    assert _mk_chunk("same text").chunk_id == _mk_chunk("same text").chunk_id


# ── H2: page-aware chunking ─────────────────────────────────────
def test_split_text_paged_keeps_real_page_ranges():
    paras = [(f"P{pg} " + "x" * 600, pg) for pg in range(10, 14)]  # pages 10..13
    out = split_text_paged(paras, max_chars=2000, overlap=200)
    assert out, "expected at least one chunk"
    assert out[0][1] == 10            # first chunk starts on page 10
    assert out[-1][2] == 13           # last chunk ends on page 13
    assert any(ps > 10 for _, ps, _ in out)  # not all collapsed to the first page


def test_split_text_paged_single_page():
    assert split_text_paged([("short text on one page", 5)], 2000, 200) == [
        ("short text on one page", 5, 5)
    ]


def test_split_text_and_hard_split_basic():
    assert hard_split("abc", 200) == ["abc"]
    assert split_text("para one\n\npara two", 2000, 200) == ["para one\n\npara two"]


# ── .env sanitizer ──────────────────────────────────────────────
def test_env_safe_strips_newlines_and_spaces():
    assert _env_safe("./my docs") == "./my docs"
    assert "\n" not in _env_safe("evil\nINJECTED=1")
    assert _env_safe("  spaced  ") == "spaced"


# ── write_env: language mapping, perf options, key preservation ──
def test_write_env_maps_answer_language_for_all_offered_languages(tmp_path, monkeypatch):
    import brag.setup_core as sc
    monkeypatch.setattr(sc, "WORKSPACE", tmp_path)
    for lang, expected in [("english", "English"), ("german", "German"),
                           ("french", "French"), ("portuguese", "Portuguese")]:
        sc.write_env("gemini", "", lang)
        env = (tmp_path / ".env").read_text(encoding="utf-8")
        assert f"VAULT_LANGUAGE={lang}" in env
        assert f"ANSWER_LANGUAGE={expected}" in env  # no longer collapses to English


def test_write_env_writes_rerank_and_vision(tmp_path, monkeypatch):
    import brag.setup_core as sc
    monkeypatch.setattr(sc, "WORKSPACE", tmp_path)
    sc.write_env("gemini", "", "english", rerank_profile="full", vision_enabled=False)
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "RERANK_PROFILE=full" in env
    assert "VISION_ENABLED=false" in env


def test_write_env_preserves_unmanaged_user_keys(tmp_path, monkeypatch):
    import brag.setup_core as sc
    monkeypatch.setattr(sc, "WORKSPACE", tmp_path)
    (tmp_path / ".env").write_text(
        "BRIDGE_HOST_PORT=8770\nBRIDGE_PUBLIC_URL=http://localhost:8770\n"
        "CLAUDE_CONFIG_DIR=/some/dir\n", encoding="utf-8")
    sc.write_env("gemini", "", "english")  # a re-run must not drop these
    env = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "BRIDGE_HOST_PORT=8770" in env
    assert "BRIDGE_PUBLIC_URL=http://localhost:8770" in env
    assert "CLAUDE_CONFIG_DIR=/some/dir" in env


# ── write_claude_config: backup / refuse-on-broken-JSON safety ───
def test_write_claude_config_adds_entry_and_backs_up(tmp_path, monkeypatch):
    import json
    import brag.setup_core as sc
    monkeypatch.setattr(sc, "CLAUDE_CONFIG_DIR", tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_MOUNTED", "1")
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text('{"mcpServers": {"other": {"command": "x"}}}', encoding="utf-8")
    ok, _ = sc.write_claude_config()
    assert ok
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert "brag" in data["mcpServers"]
    assert "other" in data["mcpServers"]  # existing MCP servers preserved
    assert (tmp_path / "claude_desktop_config.json.backup").exists()


def test_write_claude_config_refuses_and_keeps_broken_json(tmp_path, monkeypatch):
    import brag.setup_core as sc
    monkeypatch.setattr(sc, "CLAUDE_CONFIG_DIR", tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_MOUNTED", "1")
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text("{ not valid json", encoding="utf-8")
    ok, _ = sc.write_claude_config()
    assert not ok
    assert cfg.read_text(encoding="utf-8") == "{ not valid json"  # original untouched


def test_write_claude_config_refuses_when_not_mounted(monkeypatch):
    import brag.setup_core as sc
    monkeypatch.delenv("CLAUDE_CONFIG_MOUNTED", raising=False)
    ok, _ = sc.write_claude_config()
    assert not ok


# ── embed_documents contract (P1 safety net) ────────────────────
# The batched ingest relies on embed_documents returning ONE entry per input,
# in order, with None for a failed item — otherwise a vector lands on the wrong
# chunk (silent wrong-page citation). Lock that contract in on the default impl.
def _fake_embedder(fail_on=()):
    from brag.embeddings.base import EmbeddingBackend

    class _Fake(EmbeddingBackend):
        dim = 3

        def embed_document(self, text):
            if text in fail_on:
                raise RuntimeError("boom")
            return [float(len(text)), 0.0, 0.0]

        def embed_query(self, text):
            return [0.0, 0.0, 0.0]

    return _Fake()


def test_embed_documents_aligns_inputs_and_outputs():
    out = _fake_embedder().embed_documents(["a", "bb", "ccc"])
    assert out == [[1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0]]


def test_embed_documents_isolates_a_failure_as_none_without_shifting():
    out = _fake_embedder(fail_on={"bb"}).embed_documents(["a", "bb", "ccc"])
    assert len(out) == 3            # one entry per input — never dropped
    assert out[0] == [1.0, 0.0, 0.0]
    assert out[1] is None          # failure isolated in place
    assert out[2] == [3.0, 0.0, 0.0]  # later items keep their correct vector


def test_embed_documents_empty():
    assert _fake_embedder().embed_documents([]) == []


# ── retry classification + overall deadline (R2) ────────────────
def test_retry_returns_value_on_success():
    from brag.llm_backends.retry import call_with_retry
    assert call_with_retry(lambda: "ok") == "ok"


def test_retry_fails_fast_on_unclassified_error():
    from brag.llm_backends.retry import call_with_retry
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise ValueError("not a rate limit or network issue")

    assert call_with_retry(boom, label="t") is None
    assert calls["n"] == 1  # unclassified → no retry


def test_retry_waits_then_succeeds_on_rate_limit(monkeypatch):
    import brag.llm_backends.retry as r
    sleeps = []
    monkeypatch.setattr(r.time, "sleep", lambda s: sleeps.append(s))
    seq = [Exception("HTTP 429 too many requests"), "ok"]

    def fn():
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    assert r.call_with_retry(fn, label="t") == "ok"
    assert len(sleeps) == 1  # backed off once before the successful retry


def test_retry_deadline_skips_unaffordable_backoff(monkeypatch):
    import brag.llm_backends.retry as r
    sleeps = []
    monkeypatch.setattr(r.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(r.time, "monotonic", lambda: 0.0)  # no time elapses

    def always_rate_limited():
        raise Exception("rate limit: 429")

    # First backoff is >= 60s; with a 10s deadline it must give up immediately.
    assert r.call_with_retry(always_rate_limited, deadline_seconds=10) is None
    assert sleeps == []  # never slept past the deadline


# ── config: _env default handling and RERANK preset fallback ────
def test_env_empty_or_missing_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("BRAG_TEST_ENV_KEY", raising=False)
    assert config._env("BRAG_TEST_ENV_KEY", "def") == "def"
    monkeypatch.setenv("BRAG_TEST_ENV_KEY", "")
    assert config._env("BRAG_TEST_ENV_KEY", "def") == "def"  # empty == unset
    monkeypatch.setenv("BRAG_TEST_ENV_KEY", "value")
    assert config._env("BRAG_TEST_ENV_KEY", "def") == "value"


def test_unknown_rerank_profile_falls_back_to_eco(monkeypatch):
    import importlib
    monkeypatch.setenv("RERANK_PROFILE", "nonsense")
    importlib.reload(config)
    try:
        assert config.RERANK_ENABLED is True
        assert config.RERANK_PREFETCH == 80
        assert config.RERANK_FUSION_LIMIT == 40  # the "eco" preset
    finally:
        monkeypatch.delenv("RERANK_PROFILE", raising=False)
        importlib.reload(config)  # restore module state for other tests
