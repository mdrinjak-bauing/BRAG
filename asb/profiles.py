"""Backend profile definitions.

A profile bundles the embedding backend, the LLM backend and their models.
The active profile is chosen once during setup (PROFILE in .env) and can be
overridden per component via environment variables (see config.py).

Cloud providers (gemini / openai / anthropic) all run on any hardware and need
only an API key. Local providers (hybrid / local) keep documents on the machine.

IMPORTANT: The embedding model determines the vector dimension of the Qdrant
collection. Switching profiles after ingest requires a full re-ingest into a
new collection (the collection name is derived from the embedding backend, so
nothing breaks — but documents must be processed again).

NOTE on Anthropic: Anthropic offers no embedding API. The "anthropic" profile
therefore pairs Claude (Haiku) for the AI text work with LOCAL embeddings
(sentence-transformers on CPU). It is a cloud-LLM / local-embedding hybrid.
"""

PROFILES = {
    # ── Cloud: Google Gemini (recommended default — cheapest, fully cloud) ──
    "gemini": {
        "embedding_backend": "gemini",
        "embedding_model": "gemini-embedding-001",
        "embedding_dim": 3072,
        "llm_backend": "gemini",
        "llm_model": "gemini-2.5-flash-lite",  # no daily request cap (bulk-safe)
        "llm_base_url": None,
        "key_env": "GEMINI_API_KEY",
    },
    # ── Cloud: OpenAI / ChatGPT (fully cloud) ──
    "openai": {
        "embedding_backend": "openai",
        "embedding_model": "text-embedding-3-small",  # cheapest OpenAI embedding
        "embedding_dim": 1536,
        "llm_backend": "openai",
        "llm_model": "gpt-4o-mini",  # cheapest capable OpenAI chat model
        "llm_base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
    },
    # ── Cloud LLM + local embeddings: Anthropic / Claude ──
    # Anthropic has no embedding endpoint, so embeddings run locally (CPU).
    "anthropic": {
        "embedding_backend": "local_st",
        "embedding_model": "Snowflake/snowflake-arctic-embed-l-v2.0",
        "embedding_dim": 1024,
        "llm_backend": "anthropic",
        "llm_model": "claude-haiku-4-5",  # cheapest Claude model
        "llm_base_url": None,
        "key_env": "ANTHROPIC_API_KEY",
    },
    # ── Hybrid: local embeddings + local LLM via LM Studio (strong Mac) ──
    "hybrid": {
        "embedding_backend": "local_st",
        "embedding_model": "Snowflake/snowflake-arctic-embed-l-v2.0",
        "embedding_dim": 1024,
        "llm_backend": "openai_compatible",
        "llm_model": "google/gemma-3-27b-it",
        "llm_base_url": "http://host.docker.internal:1234/v1",
        "key_env": None,
    },
    # ── Local: fully local via Ollama (cross-platform, privacy-first) ──
    "local": {
        "embedding_backend": "ollama",
        "embedding_model": "nomic-embed-text",
        "embedding_dim": 768,
        "llm_backend": "openai_compatible",
        "llm_model": "llama3.1",
        "llm_base_url": "http://host.docker.internal:11434/v1",
        "key_env": None,
    },
}

# Back-compat alias: the original single cloud profile was named "cloud".
PROFILES["cloud"] = PROFILES["gemini"]
