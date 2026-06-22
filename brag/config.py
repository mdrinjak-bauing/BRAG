"""Central configuration.

All values come from environment variables (populated by docker-compose from
the project .env file, which the setup wizard writes). No user-specific values
live in code. Component-level overrides allow mixing profiles, e.g. cloud
embeddings with a local LLM.
"""

import contextlib
import contextvars
import os
from pathlib import Path

from brag.profiles import PROFILES

try:  # .env is loaded by docker-compose; this is a fallback for local runs
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env(name: str, default):
    value = os.environ.get(name, "")
    return value if value != "" else default


# ── Profile ─────────────────────────────────────────────────────
PROFILE_NAME = _env("PROFILE", "gemini")
_profile = PROFILES.get(PROFILE_NAME, PROFILES["cloud"])

# ── Paths (container view; host paths are mapped in docker-compose) ─
# Multi-project: the vault (and its derived paths + the Qdrant collection) is
# resolved DYNAMICALLY from the active project — a ContextVar set per watcher
# callback / per bridge request via project_context(). With no active project
# (the single-project install and every existing caller) it falls back to these
# env-derived defaults, so behaviour is unchanged. The public names VAULT,
# SOURCES_DIR, …, COLLECTION_NAME are served by module __getattr__ (below) so a
# plain `config.SOURCES_DIR` is always the CURRENT project's path, never a value
# captured at import time.
_DEFAULT_VAULT = Path(_env("VAULT_DIR", "/vault"))
_active_project: "contextvars.ContextVar[dict | None]" = contextvars.ContextVar(
    "brag_active_project", default=None)


def _vault() -> Path:
    rec = _active_project.get()
    if rec and rec.get("vault"):
        return Path(rec["vault"])
    return _DEFAULT_VAULT

# Subfolders of sources/ that the watcher ignores (staging area)
WATCH_IGNORE_DIRS = {"_inbox"}

# ── Language ────────────────────────────────────────────────────
# Controls BM25 stemming and the language of generated chunk contexts/notes.
VAULT_LANGUAGE = _env("VAULT_LANGUAGE", "english")   # snowball stemmer name
ANSWER_LANGUAGE = _env("ANSWER_LANGUAGE", "English")  # for LLM prompts

# ── Qdrant ──────────────────────────────────────────────────────
QDRANT_URL = _env("QDRANT_URL", "http://qdrant:6333")
DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"

# ── Backends (profile defaults, individually overridable) ──────
EMBEDDING_BACKEND = _env("EMBEDDING_BACKEND", _profile["embedding_backend"])
EMBEDDING_MODEL = _env("EMBEDDING_MODEL", _profile["embedding_model"])
# Optional Hugging Face revision (commit SHA / tag) to PIN the model weights for
# reproducible, supply-chain-safe downloads. Empty = latest (current behaviour).
EMBEDDING_REVISION = _env("EMBEDDING_REVISION", "")
EMBEDDING_DIM = int(_env("EMBEDDING_DIM", _profile["embedding_dim"]))
# How many chunk texts the embedder processes per batch during ingest. Batching
# the local sentence-transformers model uses CPU/BLAS far better than one call
# per chunk; conservative default keeps peak memory bounded on weak machines.
EMBED_BATCH_SIZE = int(_env("EMBED_BATCH_SIZE", 32))
# Upper bound on the characters of any single text handed to an embedding
# backend, applied UNIFORMLY across all backends (local sentence-transformers,
# OpenAI, Gemini). Each backend previously hard-coded its own cap (local
# 20000, OpenAI 8000, Gemini none), so the SAME text could embed
# differently depending only on the active backend — non-reproducible vectors
# across profiles. One shared, env-overridable dial removes that asymmetry.
EMBEDDING_INPUT_MAX_CHARS = int(_env("EMBEDDING_INPUT_MAX_CHARS", 20000))
LLM_BACKEND = _env("LLM_BACKEND", _profile["llm_backend"])
LLM_MODEL = _env("LLM_MODEL", _profile["llm_model"])
LLM_BASE_URL = _env("LLM_BASE_URL", _profile["llm_base_url"])

# Whether the active LLM runs on-device (LM Studio via the
# OpenAI-compatible backend). Local models have SMALL, fixed context windows
# (LM Studio defaults to ~4k tokens), so the contextualization prompt must be
# bounded far more tightly than for cloud providers (which have 100k+ windows).
# Used only to pick safe DEFAULTS below; every value remains env-overridable.
LLM_IS_LOCAL = LLM_BACKEND == "openai_compatible"

# Cloud API keys — one per provider; only the active provider's key is needed.
GEMINI_API_KEY = _env("GEMINI_API_KEY", "")
OPENAI_API_KEY = _env("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY", "")

# Collection name is tied to the embedding backend — switching backends
# automatically targets a different collection (no silent dimension clash).
# NOTE: the "asb_" prefix is deliberately kept (not renamed to "brag_") so
# that installations created before the BRAG rename keep finding their
# existing Qdrant data. It is an internal identifier and never user-visible.
_DEFAULT_COLLECTION = _env(
    "COLLECTION_NAME", f"asb_{EMBEDDING_BACKEND}_{EMBEDDING_DIM}"
)


def _active_collection() -> str:
    rec = _active_project.get()
    if rec and rec.get("collection"):
        return rec["collection"]
    return _DEFAULT_COLLECTION


# ── Vault layout ────────────────────────────────────────────────
# NEW model: the chosen PROJECT folder is the vault root, and EVERYTHING under it
# is the searchable corpus EXCEPT the WissensWIKI/ workspace (and hidden dirs).
# WissensWIKI is the user's space: Quellenbelege/ (verified passages, indexed via
# save_passage), the user's own .md + free subfolders (the notebook — read/write,
# NOT indexed, so notes don't echo the corpus), and a hidden .brag/ for logs.
WISSENSWIKI_NAME = "WissensWIKI"
PASSAGES_NAME = "Quellenbelege"
NOTES_NAME = "Wissen"            # notebook (your own .md + auto literature notes), not indexed
DATA_NAME = ".brag"

# Names whose value depends on the active project. Served via module __getattr__
# so every `config.<NAME>` read is resolved live (never frozen at import).
_SCOPED_ATTRS = {
    "VAULT": lambda: _vault(),
    # Corpus scan root = the project root itself (filtered by is_corpus_path).
    "SOURCES_DIR": lambda: _vault(),
    "WISSENSWIKI_DIR": lambda: _vault() / WISSENSWIKI_NAME,
    "PASSAGES_DIR": lambda: _vault() / WISSENSWIKI_NAME / PASSAGES_NAME,
    "NOTES_DIR": lambda: _vault() / WISSENSWIKI_NAME / NOTES_NAME,
    "NOTEBOOK_DIR": lambda: _vault() / WISSENSWIKI_NAME,
    "DATA_DIR": lambda: _vault() / WISSENSWIKI_NAME / DATA_NAME,
    "INGEST_LOG": lambda: _vault() / WISSENSWIKI_NAME / DATA_NAME / "ingest_log.jsonl",
    "FAILED_CHUNKS_LOG":
        lambda: _vault() / WISSENSWIKI_NAME / DATA_NAME / "failed_chunks.jsonl",
    "COLLECTION_NAME": lambda: _active_collection(),
}


def is_corpus_path(path) -> bool:
    """True if `path` is part of the active project's searchable corpus: anywhere
    under the project root EXCEPT the WissensWIKI/ workspace and any hidden /
    staging (_inbox) dir. The watcher never indexes WissensWIKI (the notebook
    would echo the corpus); Passagen is indexed via save_passage instead."""
    try:
        # Compare WITHOUT resolving symlinks: a corpus file reached through an
        # in-tree symlinked folder whose target lives outside the vault must still
        # count as corpus (ING-02 — resolve() dropped it silently). abspath()
        # collapses '.'/'..' lexically, so a literal '..' escape is still rejected.
        # (The HTTP /file/ serving guard stays resolve-based — that is separate.)
        rel = Path(os.path.abspath(path)).relative_to(os.path.abspath(_vault()))
    except (ValueError, OSError):
        return False
    parts = rel.parts
    if any(p in WATCH_IGNORE_DIRS or p.startswith(".") for p in parts):
        return False
    return not (parts and parts[0] == WISSENSWIKI_NAME)


def __getattr__(name: str):
    resolver = _SCOPED_ATTRS.get(name)
    if resolver is not None:
        return resolver()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    # Make the PEP 562 scoped names discoverable (they live only in __getattr__,
    # so without this they'd be missing from dir()/enumeration).
    return sorted(list(globals()) + list(_SCOPED_ATTRS))


@contextlib.contextmanager
def project_context(slug_or_record):
    """Scope the vault paths + COLLECTION_NAME to a project for the duration of
    the block, in the CURRENT thread/context ONLY (safe across the watcher's and
    the bridge's worker threads — a new thread does not inherit it). Accepts a
    registry record dict or a slug; None / unknown slug -> the env defaults, i.e.
    the single-project behaviour."""
    rec = slug_or_record
    if isinstance(slug_or_record, str):
        from brag import registry
        rec = registry.get(slug_or_record) if slug_or_record else None
    token = _active_project.set(rec)
    try:
        yield
    finally:
        _active_project.reset(token)

# ── Chunking (values empirically validated) ─
MAX_CHUNK_CHARS = int(_env("MAX_CHUNK_CHARS", 2000))
OVERLAP_CHARS = int(_env("OVERLAP_CHARS", 200))
MIN_CHUNK_CHARS = int(_env("MIN_CHUNK_CHARS", 80))
MAX_TABLE_CHARS = int(_env("MAX_TABLE_CHARS", 8000))

# ── Contextual retrieval ────────────────────────────────────────
CR_ENABLED = _env("CR_ENABLED", "true").lower() == "true"
# Chunks per LLM call. The whole batch's texts share ONE context window, so a
# local model (small window) must use a smaller batch than cloud: 5 chunks at
# MAX_CHUNK_CHARS=2000 are up to 10k chars of payload alone — already the entire
# ≈4k-token local window before any grounding or output. 3 leaves headroom for
# the grounding block and the reserved output tokens. Cloud keeps the proven 5.
CR_BATCH_SIZE = int(_env("CR_BATCH_SIZE", 3 if LLM_IS_LOCAL else 5))
# Per-source-text caps for the grounding context handed to the contextualization
# LLM. Cloud models have huge windows, so the defaults stay generous there; on
# a LOCAL model the same sizes overflow the (≈4k-token) window and the server
# returns HTTP 400 for EVERY batch, producing zero context. Hence the defaults
# are profile-aware. These bound the INDIVIDUAL pieces; CR_PROMPT_MAX_CHARS
# below is the hard cap on the WHOLE assembled prompt and is what actually
# guarantees the request fits — even on the chapter-found path.
CONTEXT_DOC_CHARS = int(_env("CONTEXT_DOC_CHARS", 4000 if LLM_IS_LOCAL else 15000))
TOC_MAX_CHARS = int(_env("TOC_MAX_CHARS", 1500 if LLM_IS_LOCAL else 3000))
CHAPTER_CONTEXT_CHARS = int(
    _env("CHAPTER_CONTEXT_CHARS", 3000 if LLM_IS_LOCAL else 10000)
)
# Hard upper bound on the ENTIRE contextualization prompt (doc context + all
# chunk texts + task/format scaffolding), in characters. _fit_doc_context trims
# the grounding block to whatever budget remains AFTER the chunk texts are
# placed, so the request can never blow the model's context window regardless of
# which grounding path was taken or how the individual caps are set.
#
# Local sizing (≈4k-token default LM Studio window, ≈3.4 chars/token
# for German), worst case at CR_BATCH_SIZE=3:
#   chunk payload   3 × 2000 = 6000 chars   (≈1760 tok)
#   scaffolding     ~700 chars              (≈210 tok)
#   grounding       remainder up to ~2300   (≈680 tok)   ⇒ input ≈ 2650 tok
#   reserved output 200×3 + 100 = 700 tok
#   total           ≈ 3350 tok  <  4096     ✓ comfortably fits
# So 9000 chars is the local cap. Cloud gets a deliberately loose 60k-char cap
# (well under every cloud provider's 100k+ window) so nothing changes for it.
CR_PROMPT_MAX_CHARS = int(
    _env("CR_PROMPT_MAX_CHARS", 9000 if LLM_IS_LOCAL else 60000)
)
# The FULL document markdown handed to contextual retrieval (used to build the
# table-of-contents and to locate each chunk's chapter/section heading) must
# cover the WHOLE document — it must NOT be shrunk to a grounding cap. Previously
# it was truncated to CONTEXT_DOC_CHARS at extraction time (extract.py), which on
# a long document hid every heading past the first ~15k chars and forced the
# whole-document grounding fallback for nearly every chunk (the real cause of the
# "chapter heading not found" storm). Kept large but bounded against a
# pathological multi-hundred-MB export.
MARKDOWN_FULL_MAX_CHARS = int(_env("MARKDOWN_FULL_MAX_CHARS", 2_000_000))

# ── Vision pass (figure descriptions) ───────────────────────────
# When enabled, each figure's image is sent to the (multimodal) text LLM for an
# honest 1-3 sentence description, which is embedded so figures become findable
# by content. On by default; needs a multimodal model (all cloud presets are —
# for local profiles load a vision model, else it falls back to caption-only).
# Disabling it also skips rendering figure images during extraction.
VISION_ENABLED = _env("VISION_ENABLED", "true").lower() == "true"
VISION_IMAGE_SCALE = float(_env("VISION_IMAGE_SCALE", 2.0))

# ── Ingest safety on consumer hardware ──────────────────────────
# Local LLM inference (LM Studio) puts sustained load on the user's GPU; on a
# marginal PSU / cooling that can hard-reset the PC mid-ingest. Docker then
# auto-restarts the app and would re-ingest the SAME document -> a crash loop. The
# pipeline skips a document after this many interrupted (never-completed) attempts
# and surfaces a visible marker instead of hammering the machine again.
INGEST_MAX_ATTEMPTS = int(_env("INGEST_MAX_ATTEMPTS", "2"))
# Optional pause (seconds) between local LLM calls so the GPU is not pegged at
# 100% continuously. Default 0 (off). Raise it (e.g. 0.5-2) if your PC overheats
# or resets during local indexing. Ignored for cloud providers.
LOCAL_LLM_PACING_SECONDS = float(_env("LOCAL_LLM_PACING_SECONDS", "0"))

# ── Retrieval / reranking ───────────────────────────────────────
RERANKER_MODEL = _env("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
# Optional HF revision to pin the reranker weights (see EMBEDDING_REVISION).
RERANKER_REVISION = _env("RERANKER_REVISION", "")

# The LOCAL cross-encoder reranker is the main CPU cost of a search — its load
# scales with the number of passages it SCORES ("rerank" below). The retrieval
# pool ("load" = prefetch PER vector, dense + sparse) is comparatively cheap, so
# a larger pool lets the reranker pick from deeper recall WITHOUT scoring more
# pairs. RERANK_PROFILE is the single dial trading speed against quality:
#   off       reranking disabled — fastest; results come straight from RRF fusion
#   eco       load 160 (80+80),   rerank 40   ← default, gentle on consumer PCs
#   balanced  load 240 (120+120), rerank 60
#   full      load 400 (200+200), rerank 120  ← strong machines, best quality
# Any single value can still be pinned via RERANK_ENABLED / RERANK_PREFETCH /
# RERANK_FUSION_LIMIT, which override the preset.
RERANK_PROFILE = _env("RERANK_PROFILE", "eco").lower()
_RERANK_PRESETS = {
    "off":      {"enabled": False, "prefetch": 80,  "fusion": 40},
    "eco":      {"enabled": True,  "prefetch": 80,  "fusion": 40},
    "balanced": {"enabled": True,  "prefetch": 120, "fusion": 60},
    "full":     {"enabled": True,  "prefetch": 200, "fusion": 120},
}
_rerank = _RERANK_PRESETS.get(RERANK_PROFILE, _RERANK_PRESETS["eco"])

RERANK_ENABLED = _env("RERANK_ENABLED", str(_rerank["enabled"]).lower()).lower() == "true"
RERANK_PREFETCH = int(_env("RERANK_PREFETCH", _rerank["prefetch"]))
RERANK_FUSION_LIMIT = int(_env("RERANK_FUSION_LIMIT", _rerank["fusion"]))
# Cross-encoder batch size — bounds peak memory and keeps reranking responsive
# on weak CPUs (the reranker scores up to RERANK_FUSION_LIMIT pairs per search).
RERANK_BATCH_SIZE = int(_env("RERANK_BATCH_SIZE", 16))
DEFAULT_TOP_K = int(_env("DEFAULT_TOP_K", 15))
MAX_CHUNKS_PER_SOURCE = int(_env("MAX_CHUNKS_PER_SOURCE", 3))
# Cross-source near-duplicate filter: drop a candidate whose chunk text is a
# near-duplicate (token-set / Jaccard similarity) of an already-accepted hit.
# Catches the SAME passage reproduced across DIFFERENT source files (quoted
# text, shared boilerplate, a standard reproduced in several books), which the
# per-source cap above cannot see. High threshold so only genuine duplicates
# are removed; set to 1.0 (or higher) to disable the filter entirely.
DEDUP_SIMILARITY_THRESHOLD = float(_env("DEDUP_SIMILARITY_THRESHOLD", 0.90))
# A generous SANITY bound on top_k — NOT a feature cap. Large top_k stays
# deliberately supported (see search/query.py); this only stops an absurd value
# (e.g. a buggy caller passing a million) from making Qdrant prefetch/fuse a
# pathological number of points and exhausting memory.
MAX_TOP_K = int(_env("MAX_TOP_K", 2000))
# Warm the (local, CPU) cross-encoder reranker in a background thread at MCP
# server start, so the FIRST search isn't blocked by the one-time model load.
# Never loaded synchronously in the start path (that could outlast Claude
# Desktop's MCP handshake). Only warms when reranking is enabled.
RERANK_WARMUP = _env("RERANK_WARMUP", "true").lower() == "true"

# ── HTTP bridge ─────────────────────────────────────────────────
# The browser setup wizard (and its config-writing API) is served ONLY when the
# bridge runs in the one-shot `setup` compose service, which is the only service
# that mounts the project dir and the Claude Desktop config. The persistent app
# runs with SETUP_MODE off, so its bridge serves only PDF deep-links + health —
# it cannot write .env or the Claude config even though it shares the code.
SETUP_MODE = _env("SETUP_MODE", "") == "1"
BRIDGE_PORT = int(_env("BRIDGE_PORT", 8765))
# Public URL prefix as seen from the host browser (links in search results)
BRIDGE_PUBLIC_URL = _env("BRIDGE_PUBLIC_URL", f"http://localhost:{BRIDGE_PORT}")

# ── Watcher ─────────────────────────────────────────────────────
WATCH_POLL_SECONDS = int(_env("WATCH_POLL_SECONDS", 10))
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".pptx", ".md", ".html"}


def normalize_source_key(value) -> str:
    """NFC-normalize file names for robust comparisons (macOS writes NFD)."""
    import unicodedata
    if value is None:
        return ""
    return unicodedata.normalize("NFC", str(value)).strip()


def source_key_from_path(path) -> str:
    """Path-qualified, NFC-normalized identity for a source document: its path
    relative to sources/ with the file suffix dropped and POSIX separators.

    This — not the bare filename stem — is the unique key for a document. Two
    same-named files in different folders (e.g. projectA/Bericht.pdf and
    projectB/Bericht.pdf) would otherwise collide on the stem, so ingesting one
    would delete-then-overwrite the other's chunks and deleting one would wipe
    both (silent data loss). Files directly in sources/ keep their plain stem,
    so the common (un-foldered) case is unchanged.
    """
    p = Path(path)
    try:
        # Identity is the path relative to the ACTIVE project's ROOT (the corpus
        # is the whole project folder now, not a sources/ subfolder).
        rel = p.resolve().relative_to(_vault().resolve())
    except ValueError:
        rel = Path(p.name)
    return normalize_source_key(rel.with_suffix("").as_posix())


def source_key_variants(value) -> list[str]:
    """NFC, NFD and raw forms of a source key, for filters that must match
    payloads written under different Unicode normalizations (snapshot restore,
    manual import, cross-OS moves). A single-NFC filter silently returns zero
    hits for such payloads — the exact 'found nothing, exit 0' failure mode."""
    import unicodedata
    raw = "" if value is None else str(value).strip()
    candidates = [normalize_source_key(raw), unicodedata.normalize("NFD", raw), raw]
    seen, out = set(), []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def slugify_topic(value) -> str:
    """Slug for a passage/report topic — NFC-normalized, lowercased, non-word
    chars collapsed to '_'. Case- and Unicode-form-insensitive, so 'Method',
    'method' and a macOS-NFD variant all map to the SAME file + index key (a
    case-sensitive slug silently created two files and made list_passages miss
    its own passage)."""
    import re
    import unicodedata
    t = unicodedata.normalize("NFC", "" if value is None else str(value)).strip().lower()
    return re.sub(r"[^\w\-]+", "_", t).strip("_") or "general"
