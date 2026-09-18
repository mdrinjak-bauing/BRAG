"""A failing reranker must degrade to fusion order, not kill the search.

The error goes to stderr: stdout is the JSON-RPC channel of the MCP server, and a stray
line there corrupts the protocol.

Storage and the embedder are faked out (no live Qdrant, no real cross-encoder loaded) —
same convention as the rest of this suite (see test_research_tools.py, test_reembed.py).
The literal brief test calls query.search() against live infrastructure; QDRANT_URL
defaults to the docker-internal host "qdrant", which does not resolve/connect outside a
container, so the unmocked version hangs here rather than failing for the intended reason.
Faking storage + the embedder keeps the test fast, isolated, and lets it fail for the
right reason: the reranker's RuntimeError, not a network timeout.
"""
from qdrant_client.models import SparseVector


def test_a_broken_reranker_still_returns_hits(monkeypatch, capsys):
    from brag import storage
    from brag.search import query

    class _Point:
        def __init__(self, pid, score, payload):
            self.id, self.score, self.payload, self.vector = pid, score, payload, None

    class _Result:
        points = [
            _Point("1", 0.9, {"text": "Qualitätssicherung in der Bauausführung.",
                               "source_file": "A.pdf"}),
            _Point("2", 0.8, {"text": "Ein zweiter Treffer zum Thema.",
                               "source_file": "B.pdf"}),
        ]

    class _Client:
        def query_points(self, **kwargs):
            return _Result()

        def close(self):
            pass

    monkeypatch.setattr(storage, "get_client", lambda: _Client())

    class _Embedder:
        def embed_query(self, text):
            return [0.0, 0.1, 0.2]

    monkeypatch.setattr(query, "get_embedder", lambda: _Embedder())
    monkeypatch.setattr(query, "embed_sparse_query",
                         lambda text: SparseVector(indices=[0], values=[0.1]))

    def explodiert(*a, **k):
        raise RuntimeError("reranker kaputt")

    # No raising=False: if _rerank is ever renamed again without updating this
    # test, setattr must fail loudly here rather than silently patching nothing
    # and leaving the guard unexercised (exactly what happened when this test
    # targeted the pre-rename public name "rerank").
    monkeypatch.setattr(query, "_rerank", explodiert)
    treffer = query.search("Qualitätssicherung Bauausführung", top_k=5)

    assert treffer, "the search returned nothing instead of the fusion order"
    out = capsys.readouterr()
    assert "kaputt" in out.err, "the degrade message never reached stderr — guard not exercised"
    assert "kaputt" not in out.out, "error written to stdout (JSON-RPC channel)"
