"""LLM backends. get_llm() returns the configured implementation."""

from asb import config

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        if config.LLM_BACKEND == "gemini":
            from asb.llm_backends.gemini import GeminiLLM
            _llm = GeminiLLM()
        elif config.LLM_BACKEND == "openai":
            from asb.llm_backends.openai import OpenAILLM
            _llm = OpenAILLM()
        elif config.LLM_BACKEND == "anthropic":
            from asb.llm_backends.anthropic import AnthropicLLM
            _llm = AnthropicLLM()
        elif config.LLM_BACKEND == "openai_compatible":
            from asb.llm_backends.openai_compatible import OpenAICompatibleLLM
            _llm = OpenAICompatibleLLM()
        else:
            raise ValueError(f"Unknown LLM_BACKEND: {config.LLM_BACKEND}")
    return _llm
