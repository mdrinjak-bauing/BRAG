"""LLM backend interface."""

from abc import ABC, abstractmethod


class LLMBackend(ABC):
    @abstractmethod
    def chat(self, prompt: str, max_tokens: int = 1024) -> str | None:
        """Single-turn completion. Returns None on unrecoverable failure —
        callers must treat missing output as 'skip, heal later', never crash
        the pipeline over one failed call."""
        ...
