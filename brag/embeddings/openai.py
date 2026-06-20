"""OpenAI embedding backend (Profile: openai)."""

import json
import urllib.request

from brag import config
from brag.embeddings.base import EmbeddingBackend
from brag.llm_backends.retry import call_with_retry

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
        payload = json.dumps(
            {"model": self._model, "input": text[:config.EMBEDDING_INPUT_MAX_CHARS]}
        ).encode()
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

    def embed_documents(self, texts: list[str]) -> list[list[float] | None]:
        """Real batched embedding — the OpenAI /embeddings endpoint accepts a
        list of inputs in a single request, so we send EMBED_BATCH_SIZE texts
        per call instead of one HTTP round-trip per chunk. The result stays
        ALIGNED to ``texts`` (one entry per input, in order, ``None`` where a
        text/batch failed), so the pipeline's vector<->chunk pairing holds. The
        API does not guarantee response order, so each batch is re-sorted by its
        ``index`` field. On a batch-level failure we fall back to per-text for
        just that batch so one bad input cannot null out the whole document."""
        out: list[list[float] | None] = []
        for start in range(0, len(texts), config.EMBED_BATCH_SIZE):
            batch = [t[:config.EMBEDDING_INPUT_MAX_CHARS]
                     for t in texts[start : start + config.EMBED_BATCH_SIZE]]

            def call(batch=batch):
                payload = json.dumps({"model": self._model, "input": batch}).encode()
                req = urllib.request.Request(
                    f"{DEFAULT_URL}/embeddings", data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                    },
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())
                items = sorted(data["data"], key=lambda d: d["index"])
                return [it["embedding"] for it in items]

            vecs = call_with_retry(call, label="openai embeddings batch")
            if vecs is not None and len(vecs) == len(batch):
                out.extend(vecs)
            else:  # batch failed or broke the count contract — isolate per text
                for t in batch:
                    try:
                        out.append(self._embed(t))
                    except Exception:  # noqa: BLE001
                        out.append(None)
        return out
