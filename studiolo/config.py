"""Central configuration.

All values come from environment variables (populated by docker-compose from
the project .env file, which the setup wizard writes). No user-specific values
live in code. Component-level overrides allow mixing profiles, e.g. cloud
embeddings with a local LLM.
"""

import os
from pathlib import Path

from studiolo.profiles import PROFILES

try:  # .env is loaded by docker-compose; this is a fallback for local runs
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env(name: str, default):
    value = os.environ.get(name, "")
    return value if value != "" else default


# ── Profile ─────────────────────────────────────────────────────
PROFILE_NAME = _env("PROFILE", "cloud")
_profile = PROFILES.get(PROFILE_NAME, PROFILES["cloud"])

# ── Paths (container view; host paths are mapped in docker-compose) ─
VAULT = Path(_env("VAULT_DIR", "/vault"))
SOURCES_DIR = VAULT / "sources"
NOTES_DIR = VAULT / "notes"
PASSAGES_DIR = VAULT / "passages"
DATA_DIR = VAULT / ".studiolo"            # ingest log, failed-chunk log
INGEST_LOG = DATA_DIR / "ingest_log.jsonl"
FAILED_CHUNKS_LOG = DATA_DIR / "failed_chunks.jsonl"

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
EMBEDDING_DIM = int(_env("EMBEDDING_DIM", _profile["embedding_dim"]))
LLM_BACKEND = _env("LLM_BACKEND", _profile["llm_backend"])
LLM_MODEL = _env("LLM_MODEL", _profile["llm_model"])
LLM_BASE_URL = _env("LLM_BASE_URL", _profile["llm_base_url"])
GEMINI_API_KEY = _env("GEMINI_API_KEY", "")

# Collection name is tied to the embedding backend — switching backends
# automatically targets a different collection (no silent dimension clash).
COLLECTION_NAME = _env(
    "COLLECTION_NAME", f"studiolo_{EMBEDDING_BACKEND}_{EMBEDDING_DIM}"
)

# ── Chunking (values empirically validated in the originating system) ─
MAX_CHUNK_CHARS = int(_env("MAX_CHUNK_CHARS", 2000))
OVERLAP_CHARS = int(_env("OVERLAP_CHARS", 200))
MIN_CHUNK_CHARS = int(_env("MIN_CHUNK_CHARS", 80))
MAX_TABLE_CHARS = int(_env("MAX_TABLE_CHARS", 8000))

# ── Contextual retrieval ────────────────────────────────────────
CR_ENABLED = _env("CR_ENABLED", "true").lower() == "true"
CR_BATCH_SIZE = int(_env("CR_BATCH_SIZE", 5))
CONTEXT_DOC_CHARS = int(_env("CONTEXT_DOC_CHARS", 15000))
TOC_MAX_CHARS = int(_env("TOC_MAX_CHARS", 3000))
CHAPTER_CONTEXT_CHARS = int(_env("CHAPTER_CONTEXT_CHARS", 10000))

# ── Retrieval ───────────────────────────────────────────────────
RERANKER_MODEL = _env("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RERANK_ENABLED = _env("RERANK_ENABLED", "true").lower() == "true"
RERANK_PREFETCH = int(_env("RERANK_PREFETCH", 150))
RERANK_FUSION_LIMIT = int(_env("RERANK_FUSION_LIMIT", 80))
DEFAULT_TOP_K = int(_env("DEFAULT_TOP_K", 15))
MAX_CHUNKS_PER_SOURCE = int(_env("MAX_CHUNKS_PER_SOURCE", 3))

# ── HTTP bridge ─────────────────────────────────────────────────
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
