"""Embedding backend interface."""

from abc import ABC, abstractmethod


class EmbeddingBackend(ABC):
    """Produces dense vectors. Documents and queries may use different
    task instructions/prefixes depending on the model."""

    dim: int

    @abstractmethod
    def embed_document(self, text: str) -> list[float]:
        ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        ...
