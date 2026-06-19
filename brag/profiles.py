"""Backend profile definitions.

A profile bundles the embedding backend, the LLM backend and their models.
The active profile is chosen once during setup (PROFILE in .env) and can be
overridden per component via environment variables (see config.py).

── Design decision: embeddings are LOCAL by default in every profile ──
All profiles use the same local sentence-transformers embedding model
(Snowflake arctic, 1024 dim, CPU — no GPU needed). The chosen provider only
controls the *text LLM* (contextual retrieval, image descriptions). The doc
type is derived from the folder path, not from an LLM (no cloud transfer).
This buys two things:

  1. Switching the cloud LLM provider (Gemini ↔ OpenAI ↔ Claude) needs NO
     re-indexing — every profile writes into the same 1024-dim collection.
  2. Embeddings are free (no embedding API cost/quota) and the document
     vectors never leave the machine.

The reranker already runs locally on CPU for every profile, so doing the
embeddings locally too is consistent — the machine already does cross-encoder
work during search. The trade-off: the first ingest downloads the arctic model
(~2.3 GB into the model cache) and bulk ingest on a weak CPU is slower than a
cloud embedding API would be.

Power users who specifically want fast cloud embeddings on weak hardware can
still opt in by setting EMBEDDING_BACKEND / EMBEDDING_MODEL / EMBEDDING_DIM in
.env (see .env.example → "fast cloud embeddings").

IMPORTANT: The embedding model determines the vector dimension of the Qdrant
collection. Changing the EMBEDDING_BACKEND override therefore requires a full
re-ingest into a new collection (the collection name is derived from the
embedding backend, so nothing breaks — but documents must be processed again).
Changing only the PROFILE (i.e. the LLM provider) does NOT.
"""

# Local embedding shared by every profile (arctic, 1024 dim, CPU).
_LOCAL_EMBEDDING = {
    "embedding_backend": "local_st",
    "embedding_model": "Snowflake/snowflake-arctic-embed-l-v2.0",
    "embedding_dim": 1024,
}

PROFILES = {
    # ── Cloud LLM: Google Gemini (recommended default — cheapest) ──
    "gemini": {
        **_LOCAL_EMBEDDING,
        "llm_backend": "gemini",
        "llm_model": "gemini-2.5-flash-lite",  # no daily request cap (bulk-safe)
        "llm_base_url": None,
        "key_env": "GEMINI_API_KEY",
    },
    # ── Cloud LLM: OpenAI / ChatGPT ──
    "openai": {
        **_LOCAL_EMBEDDING,
        "llm_backend": "openai",
        "llm_model": "gpt-4o-mini",  # cheapest capable OpenAI chat model
        "llm_base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
    },
    # ── Cloud LLM: Anthropic / Claude ──
    "anthropic": {
        **_LOCAL_EMBEDDING,
        "llm_backend": "anthropic",
        "llm_model": "claude-haiku-4-5",  # cheapest Claude model
        "llm_base_url": None,
        "key_env": "ANTHROPIC_API_KEY",
    },
    # ── Local LLM via LM Studio (strong Mac) ──
    "hybrid": {
        **_LOCAL_EMBEDDING,
        "llm_backend": "openai_compatible",
        "llm_model": "google/gemma-3-27b-it",
        "llm_base_url": "http://host.docker.internal:1234/v1",
        "key_env": None,
    },
    # ── Local LLM via Ollama (cross-platform, fully private) ──
    "local": {
        **_LOCAL_EMBEDDING,
        "llm_backend": "openai_compatible",
        "llm_model": "llama3.1",
        "llm_base_url": "http://host.docker.internal:11434/v1",
        "key_env": None,
    },
}

# Back-compat alias: the original single cloud profile was named "cloud".
PROFILES["cloud"] = PROFILES["gemini"]
