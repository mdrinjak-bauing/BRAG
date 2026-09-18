"""Without rerank scores there is nothing to judge saturation by — and saying
"nothing relevant follows" is then a false statement, not a cautious one.

RERANK_PROFILE=off is a documented, supported setting (config.py), and under it EVERY
rerank_score is None. WITHOUT the guard tested below, the remainder list would filter
to empty and _saturation would return "erschoepft" — and mcp_client.search() DOES
render that exact state as "list EXHAUSTED — nothing relevant follows" to the model
(brag/mcp_client.py, wired in the same review round as this guard, review finding I-1).
Measured against the pre-rebase code on 2026-09-17: the unguarded function returned
{'state': 'erschoepft', 'weitere': 0} for 10 unscored hits + 50 unscored candidates —
exactly the false claim this guard exists to prevent. The guard below (and its
partial-scoring closure, M-7) is what keeps that from firing on this codebase now.
"""


def test_without_rerank_scores_no_verdict_is_given():
    from brag.search import query
    hits = [{"chunk_id": str(i), "rerank_score": None} for i in range(10)]
    kandidaten = [{"chunk_id": str(i), "rerank_score": None} for i in range(50)]

    zustand = query._saturation(hits, kandidaten)

    assert zustand.get("state") not in ("erschoepft", "abgeschnitten"), \
        f"gave the verdict {zustand.get('state')!r} although nothing was scored"


def test_with_rerank_scores_the_verdict_is_given():
    from brag.search import query
    hits = [{"chunk_id": str(i), "rerank_score": 0.9 - i * 0.01} for i in range(10)]
    kandidaten = hits + [{"chunk_id": str(i), "rerank_score": 0.05} for i in range(10, 50)]

    assert query._saturation(hits, kandidaten)["state"] == "erschoepft"


def test_partially_scored_remainder_no_verdict_is_given():
    """Review finding M-7: a single scored candidate anywhere in the pool used to
    satisfy the old any(...)-over-everything guard, so a remainder that is scored
    for the shown hits but NOT scored for the rest still fell through to
    "erschoepft" — the same class of false statement Aufgabe 8 exists to prevent,
    reached by a different route. Measured against the pre-fix guard: 5 scored
    hits + 45 unscored non-hit candidates returned {'state': 'erschoepft', ...}.
    Reachable on the owner's own bridge config (RERANK_PREFETCH=150,
    RERANK_FUSION_LIMIT=80), not just a synthetic corner case.
    """
    from brag.search import query
    hits = [{"chunk_id": str(i), "rerank_score": 0.9 - i * 0.01} for i in range(5)]
    kandidaten = hits + [{"chunk_id": str(i), "rerank_score": None} for i in range(5, 50)]

    zustand = query._saturation(hits, kandidaten)

    assert zustand.get("state") not in ("erschoepft", "abgeschnitten"), \
        f"gave the verdict {zustand.get('state')!r} although the remainder " \
        f"beyond the shown hits was only partially scored"
