"""Embedding backends. get_embedder() returns the configured implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brag import config

if TYPE_CHECKING:
    from brag.embeddings.base import EmbeddingBackend

_embedder = None


def get_embedder() -> EmbeddingBackend:
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
        else:
            raise ValueError(f"Unknown EMBEDDING_BACKEND: {config.EMBEDDING_BACKEND}")
    return _embedder
