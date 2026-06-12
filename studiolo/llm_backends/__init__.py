"""LLM backends. get_llm() returns the configured implementation."""

from studiolo import config

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        if config.LLM_BACKEND == "gemini":
            from studiolo.llm_backends.gemini import GeminiLLM
            _llm = GeminiLLM()
        elif config.LLM_BACKEND == "openai_compatible":
            from studiolo.llm_backends.openai_compatible import OpenAICompatibleLLM
            _llm = OpenAICompatibleLLM()
        else:
            raise ValueError(f"Unknown LLM_BACKEND: {config.LLM_BACKEND}")
    return _llm
