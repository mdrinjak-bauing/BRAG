"""Embedding backends. get_embedder() returns the configured implementation."""

from studiolo import config

_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        if config.EMBEDDING_BACKEND == "gemini":
            from studiolo.embeddings.gemini import GeminiEmbedder
            _embedder = GeminiEmbedder()
        elif config.EMBEDDING_BACKEND == "local_st":
            from studiolo.embeddings.local_st import SentenceTransformerEmbedder
            _embedder = SentenceTransformerEmbedder()
        elif config.EMBEDDING_BACKEND == "ollama":
            from studiolo.embeddings.ollama import OllamaEmbedder
            _embedder = OllamaEmbedder()
        else:
            raise ValueError(f"Unknown EMBEDDING_BACKEND: {config.EMBEDDING_BACKEND}")
    return _embedder
