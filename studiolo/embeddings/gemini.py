"""Gemini embedding backend (Profile A)."""

from studiolo import config
from studiolo.embeddings.base import EmbeddingBackend
from studiolo.llm_backends.retry import call_with_retry


class GeminiEmbedder(EmbeddingBackend):
    def __init__(self):
        from google import genai
        if not config.GEMINI_API_KEY:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. Add it to your .env file "
                "(get a free key at https://aistudio.google.com/apikey)."
            )
        self._client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.dim = config.EMBEDDING_DIM

    def _embed(self, text: str, task_type: str) -> list[float]:
        from google.genai import types

        def call():
            result = self._client.models.embed_content(
                model=config.EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=task_type, output_dimensionality=self.dim
                ),
            )
            return result.embeddings[0].values

        vec = call_with_retry(call, label=f"embedding ({task_type})")
        if vec is None:
            raise RuntimeError("Gemini embedding failed after retries")
        return list(vec)

    def embed_document(self, text: str) -> list[float]:
        return self._embed(text, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, "RETRIEVAL_QUERY")
