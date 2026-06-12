"""BM25 sparse vectors via fastembed, with language-aware Snowball stemming."""

from asb import config

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
    from qdrant_client.models import SparseVector
    return [
        SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
        for e in get_sparse_model().embed(texts)
    ]


def embed_sparse_query(text: str):
    from qdrant_client.models import SparseVector
    emb = next(get_sparse_model().query_embed(text))
    return SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())
