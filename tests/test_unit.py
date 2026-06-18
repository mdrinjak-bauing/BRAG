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
