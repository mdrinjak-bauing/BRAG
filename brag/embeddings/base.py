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

    def embed_documents(self, texts: list[str]) -> list[list[float] | None]:
        """Embed many documents at once. The result is ALIGNED to ``texts``:
        exactly one entry per input, in the same order, with ``None`` where an
        individual embedding failed (callers skip those — same skip-and-log
        behaviour as the per-chunk path). The default embeds one at a time so
        every backend works unchanged; batch-capable backends override this."""
        out: list[list[float] | None] = []
        for text in texts:
            try:
                out.append(self.embed_document(text))
            except Exception:  # noqa: BLE001 — isolate one failure, keep the rest
                out.append(None)
        return out
