"""Gemini embedding backend (Profile A)."""

from brag import config
from brag.embeddings.base import EmbeddingBackend
from brag.llm_backends.retry import call_with_retry


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
                contents=text[:config.EMBEDDING_INPUT_MAX_CHARS],
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

    def embed_documents(self, texts: list[str]) -> list[list[float] | None]:
        """Real batched embedding — embed_content accepts a list of contents in
        one request, so we send EMBED_BATCH_SIZE texts per call instead of one
        API round-trip per chunk. result.embeddings comes back in input order,
        so the output stays ALIGNED to ``texts`` (one entry per input, in order,
        ``None`` where a text/batch failed). On a batch-level failure we fall
        back to the single-text path for just that batch so one bad input cannot
        null out the whole document. Reuses the same call_with_retry wrapper."""
        from google.genai import types

        out: list[list[float] | None] = []
        for start in range(0, len(texts), config.EMBED_BATCH_SIZE):
            batch = [t[:config.EMBEDDING_INPUT_MAX_CHARS]
                     for t in texts[start : start + config.EMBED_BATCH_SIZE]]

            def call(batch=batch):
                result = self._client.models.embed_content(
                    model=config.EMBEDDING_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=self.dim,
                    ),
                )
                return [list(e.values) for e in result.embeddings]

            vecs = call_with_retry(call, label="gemini embeddings batch")
            if vecs is not None and len(vecs) == len(batch):
                out.extend(vecs)
            else:  # batch failed or broke the count contract — isolate per text
                for t in batch:
                    try:
                        out.append(self._embed(t, "RETRIEVAL_DOCUMENT"))
                    except Exception:  # noqa: BLE001
                        out.append(None)
        return out
