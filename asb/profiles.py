"""Backend profile definitions.

A profile bundles the embedding backend, the LLM backend and their models.
The active profile is chosen once during setup (PROFILE in .env) and can be
overridden per component via environment variables (see config.py).

IMPORTANT: The embedding model determines the vector dimension of the Qdrant
collection. Switching profiles after ingest requires a full re-ingest into a
new collection (the collection name is derived from the embedding backend,
so nothing breaks — but documents must be processed again).
"""

PROFILES = {
    # Profile A — Cloud (recommended default, runs on any hardware)
    "cloud": {
        "embedding_backend": "gemini",
        "embedding_model": "gemini-embedding-001",
        "embedding_dim": 3072,
        "llm_backend": "gemini",
        "llm_model": "gemini-2.5-flash",
        "llm_base_url": None,
    },
    # Profile B — Hybrid (local embeddings + local LLM via LM Studio)
    # Requires the LM Studio app running on the host machine.
    "hybrid": {
        "embedding_backend": "local_st",
        "embedding_model": "Snowflake/snowflake-arctic-embed-l-v2.0",
        "embedding_dim": 1024,
        "llm_backend": "openai_compatible",
        "llm_model": "google/gemma-3-27b-it",
        # host.docker.internal reaches the host from inside the container
        "llm_base_url": "http://host.docker.internal:1234/v1",
    },
    # Profile C — Fully local via Ollama (privacy-first, cross-platform)
    # Requires the Ollama app running on the host machine.
    "local": {
        "embedding_backend": "ollama",
        "embedding_model": "nomic-embed-text",
        "embedding_dim": 768,
        "llm_backend": "openai_compatible",
        "llm_model": "llama3.1",
        "llm_base_url": "http://host.docker.internal:11434/v1",
    },
}
