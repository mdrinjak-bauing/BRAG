"""LLM backend interface."""

from abc import ABC, abstractmethod


class LLMBackend(ABC):
    # Whether the configured model can accept images (vision pass). Backends
    # that support it set this True; the default is text-only.
    vision_capable: bool = False

    @abstractmethod
    def chat(
        self, prompt: str, max_tokens: int = 1024, images: list[str] | None = None
    ) -> str | None:
        """Single-turn completion. ``images`` is an optional list of base64-
        encoded PNG strings (no data-URL prefix) for vision-capable models;
        text-only backends ignore it. Returns None on unrecoverable failure —
        callers must treat missing output as 'skip, heal later', never crash
        the pipeline over one failed call."""
        ...
