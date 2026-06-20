"""LLM backends. get_llm() returns the configured implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from brag import config

if TYPE_CHECKING:
    from brag.llm_backends.base import LLMBackend

_llm = None


def get_llm() -> LLMBackend:
    global _llm
    if _llm is None:
        if config.LLM_BACKEND == "gemini":
            from brag.llm_backends.gemini import GeminiLLM
            _llm = GeminiLLM()
        elif config.LLM_BACKEND == "openai":
            from brag.llm_backends.openai import OpenAILLM
            _llm = OpenAILLM()
        elif config.LLM_BACKEND == "anthropic":
            from brag.llm_backends.anthropic import AnthropicLLM
            _llm = AnthropicLLM()
        elif config.LLM_BACKEND == "openai_compatible":
            from brag.llm_backends.openai_compatible import OpenAICompatibleLLM
            _llm = OpenAICompatibleLLM()
        else:
            raise ValueError(f"Unknown LLM_BACKEND: {config.LLM_BACKEND}")
    return _llm
