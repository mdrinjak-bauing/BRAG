"""OpenAI embedding backend (Profile: openai)."""

import json
import urllib.request

from brag import config
from brag.embeddings.base import EmbeddingBackend

DEFAULT_URL = "https://api.openai.com/v1"


class OpenAIEmbedder(EmbeddingBackend):
    def __init__(self):
        if not config.OPENAI_API_KEY:
            raise EnvironmentError(
                "OPENAI_API_KEY is not set. Add it to your .env file "
                "(get a key at https://platform.openai.com/api-keys)."
            )
        self.dim = config.EMBEDDING_DIM
        self._model = config.EMBEDDING_MODEL

    def _embed(self, text: str) -> list[float]:
        payload = json.dumps({"model": self._model, "input": text[:8000]}).encode()
        req = urllib.request.Request(
            f"{DEFAULT_URL}/embeddings", data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["data"][0]["embedding"]

    def embed_document(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
