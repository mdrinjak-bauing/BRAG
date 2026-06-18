"""Gemini LLM backend (Profile A)."""

from brag import config
from brag.llm_backends.base import LLMBackend
from brag.llm_backends.retry import call_with_retry


class GeminiLLM(LLMBackend):
    vision_capable = True  # Gemini models are multimodal

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

    def chat(
        self, prompt: str, max_tokens: int = 1024, images: list[str] | None = None
    ) -> str | None:
        import base64

        from google.genai import types

        contents: list = [prompt]
        for img in images or []:
            contents.append(
                types.Part.from_bytes(
                    data=base64.b64decode(img), mime_type="image/png"
                )
            )

        def call():
            result = self._client.models.generate_content(
                model=config.LLM_MODEL, contents=contents
            )
            text = getattr(result, "text", None)
            if not text:
                raise ValueError("empty response")
            return text

        return call_with_retry(call, label="gemini chat")
