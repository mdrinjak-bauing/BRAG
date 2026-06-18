"""Embedding backends. get_embedder() returns the configured implementation."""

from brag import config

_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        if config.EMBEDDING_BACKEND == "gemini":
            from brag.embeddings.gemini import GeminiEmbedder
            _embedder = GeminiEmbedder()
        elif config.EMBEDDING_BACKEND == "openai":
            from brag.embeddings.openai import OpenAIEmbedder
            _embedder = OpenAIEmbedder()
        elif config.EMBEDDING_BACKEND == "local_st":
            from brag.embeddings.local_st import SentenceTransformerEmbedder
            _embedder = SentenceTransformerEmbedder()
        elif config.EMBEDDING_BACKEND == "ollama":
            from brag.embeddings.ollama import OllamaEmbedder
            _embedder = OllamaEmbedder()
        else:
            raise ValueError(f"Unknown EMBEDDING_BACKEND: {config.EMBEDDING_BACKEND}")
    return _embedder
