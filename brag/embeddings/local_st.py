"""Local embeddings via sentence-transformers (Profile B).

Device selection is automatic (CUDA > MPS > CPU). Note: inside a Docker
container on Apple Silicon there is no GPU access, so this runs on CPU —
fine for steady ingest, slower for bulk re-ingest.
"""

from brag import config
from brag.embeddings.base import EmbeddingBackend

# Total embedding input is bounded by the shared config.EMBEDDING_INPUT_MAX_CHARS
# so every backend (local, OpenAI, Ollama, Gemini) truncates identically —
# asymmetric per-backend truncation silently loses context (a hard-won
# lesson). Aliased here for the call sites below.
MAX_INPUT_CHARS = config.EMBEDDING_INPUT_MAX_CHARS


class SentenceTransformerEmbedder(EmbeddingBackend):
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        kwargs = {"revision": config.EMBEDDING_REVISION} if config.EMBEDDING_REVISION else {}
        self._model = SentenceTransformer(config.EMBEDDING_MODEL, **kwargs)
        self.dim = self._model.get_sentence_embedding_dimension()
        # The Qdrant collection is created with config.EMBEDDING_DIM; if the
        # model's real dimension differs (e.g. EMBEDDING_MODEL overridden but
        # EMBEDDING_DIM left at the profile default), every upsert would crash
        # with an opaque dimension error. Fail early and clearly instead.
        if self.dim != config.EMBEDDING_DIM:
            raise ValueError(
                f"Embedding model '{config.EMBEDDING_MODEL}' produces "
                f"{self.dim}-dim vectors, but EMBEDDING_DIM is "
                f"{config.EMBEDDING_DIM}. Set EMBEDDING_DIM={self.dim} in .env "
                f"(and re-ingest, since the collection name encodes the dim)."
            )

    def embed_document(self, text: str) -> list[float]:
        return self._model.encode(text[:MAX_INPUT_CHARS]).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float] | None]:
        """Batch encode — far better CPU/BLAS use than one call per chunk.
        Each text keeps the SAME per-text MAX_INPUT_CHARS bound as the single
        path, and the output stays in input order (entry i ↔ text i), so the
        caller's vector↔chunk alignment holds. If the batch call itself raises,
        fall back to per-text encoding so one bad text can't fail the whole
        document."""
        if not texts:
            return []
        bounded = [t[:MAX_INPUT_CHARS] for t in texts]
        try:
            vecs = self._model.encode(bounded, batch_size=config.EMBED_BATCH_SIZE)
            return [v.tolist() for v in vecs]
        except Exception:  # noqa: BLE001 — isolate failures via the per-text path
            out: list[list[float] | None] = []
            for t in bounded:
                try:
                    out.append(self._model.encode(t).tolist())
                except Exception:  # noqa: BLE001
                    out.append(None)
            return out

    def embed_query(self, text: str) -> list[float]:
        # Same input bound as documents — keep query/document regimes symmetric.
        text = text[:MAX_INPUT_CHARS]
        # arctic-embed uses a dedicated query prompt; fall back gracefully
        try:
            return self._model.encode(text, prompt_name="query").tolist()
        except (KeyError, ValueError):
            return self._model.encode(text).tolist()
