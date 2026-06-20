"""Embeddings via Ollama's OpenAI-compatible endpoint (Profile C)."""

import json
import urllib.request

from brag import config
from brag.embeddings.base import EmbeddingBackend


class OllamaEmbedder(EmbeddingBackend):
    def __init__(self):
        self.dim = config.EMBEDDING_DIM
        self._url = (config.LLM_BASE_URL or "http://host.docker.internal:11434/v1").rstrip("/")

    def _embed(self, text: str) -> list[float]:
        payload = json.dumps({
            "model": config.EMBEDDING_MODEL,
            "input": text[:config.EMBEDDING_INPUT_MAX_CHARS],
        }).encode()
        req = urllib.request.Request(
            f"{self._url}/embeddings", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return data["data"][0]["embedding"]

    def embed_document(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    # No embed_documents override on purpose: Ollama's OpenAI-compatible
    # /embeddings endpoint is effectively one-text-per-request for most
    # embedding models (batch support is model/version-dependent and not
    # guaranteed), so it keeps the safe inherited per-text loop from
    # EmbeddingBackend rather than risk a silently truncated/misaligned batch.
