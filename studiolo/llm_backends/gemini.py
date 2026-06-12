"""Gemini LLM backend (Profile A)."""

from studiolo import config
from studiolo.llm_backends.base import LLMBackend
from studiolo.llm_backends.retry import call_with_retry


class GeminiLLM(LLMBackend):
    def __init__(self):
        from google import genai
        from google.genai import types
        if not config.GEMINI_API_KEY:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. Add it to your .env file "
                "(get a free key at https://aistudio.google.com/apikey)."
            )
        self._client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=60_000),
        )

    def chat(self, prompt: str, max_tokens: int = 1024) -> str | None:
        def call():
            result = self._client.models.generate_content(
                model=config.LLM_MODEL, contents=prompt
            )
            text = getattr(result, "text", None)
            if not text:
                raise ValueError("empty response")
            return text

        return call_with_retry(call, label="gemini chat")
