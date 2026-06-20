"""BM25 sparse vectors via fastembed, with language-aware Snowball stemming."""

from brag import config

_model = None


def get_sparse_model():
    global _model
    if _model is None:
        from fastembed import SparseTextEmbedding
        _model = SparseTextEmbedding(
            model_name="Qdrant/bm25", language=config.VAULT_LANGUAGE
        )
    return _model


def embed_sparse_documents(texts: list[str]):
    """BM25 sparse vectors for a batch of texts. Returns a list ALIGNED to the
    input: one entry per text, in order, None where that text failed — so the
    caller's chunk<->vector pairing stays correct and one bad chunk cannot fail
    the whole document. Mirrors the dense path (local_st.embed_documents): try
    the batch call, and on failure fall back to per-text so the offender is
    isolated instead of aborting the batch."""
    from qdrant_client.models import SparseVector

    if not texts:
        return []

    def _to_vec(e):
        return SparseVector(indices=e.indices.tolist(), values=e.values.tolist())

    try:
        return [_to_vec(e) for e in get_sparse_model().embed(texts)]
    except Exception:  # noqa: BLE001 — isolate failures via the per-text path
        out: list = []
        for t in texts:
            try:
                out.append(_to_vec(next(iter(get_sparse_model().embed([t])))))
            except Exception:  # noqa: BLE001
                out.append(None)
        return out


def embed_sparse_query(text: str):
    from qdrant_client.models import SparseVector
    emb = next(get_sparse_model().query_embed(text))
    return SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())
