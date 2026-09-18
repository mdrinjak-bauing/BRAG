"""A wide search must shrink its previews instead of silently losing its tail."""


def test_preview_shrinks_as_the_hit_count_grows():
    from brag import formatting
    assert formatting.preview_chars_for(5) > formatting.preview_chars_for(40)


def test_preview_never_falls_below_the_floor():
    from brag import formatting
    assert formatting.preview_chars_for(10_000) == formatting.MIN_PREVIEW_CHARS


def test_preview_chars_is_env_overridable(monkeypatch):
    import importlib
    monkeypatch.setenv("PREVIEW_CHARS", "777")
    from brag import formatting
    importlib.reload(formatting)
    try:
        assert formatting.PREVIEW_CHARS == 777
    finally:
        monkeypatch.delenv("PREVIEW_CHARS")
        importlib.reload(formatting)        # sonst erbt die naechste Testdatei den Wert


def test_the_budget_is_env_overridable(monkeypatch):
    import importlib
    monkeypatch.setenv("RESPONSE_BUDGET_CHARS", "10000")
    from brag import formatting
    importlib.reload(formatting)
    try:
        assert formatting.RESPONSE_BUDGET_CHARS == 10000
        assert formatting.max_hits_for_budget() == 10000 // formatting.MIN_PREVIEW_CHARS
    finally:
        monkeypatch.delenv("RESPONSE_BUDGET_CHARS")
        importlib.reload(formatting)        # sonst erbt die naechste Testdatei den Wert


# --- the note-building code in mcp_client.py: a hit budget bites in two ways —
# hits dropped outright, or previews shortened — and either way the answer says
# so instead of quietly reading like a complete list. Not part of the brief's
# verbatim test block; added because the mcp_client.search() behaviour change
# itself has no other coverage.

def _hit(source_file: str, text: str) -> dict:
    return {"source_file": source_file, "rel_path": source_file, "text": text}


def test_search_notes_when_hits_are_dropped_for_budget(monkeypatch):
    from brag import config
    from brag import mcp_client as c

    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765", raising=False)
    monkeypatch.setattr(config, "OPEN_BRIDGE_ENABLED", False, raising=False)
    monkeypatch.setattr(c, "max_hits_for_budget", lambda: 2)
    monkeypatch.setattr(c, "preview_chars_for", lambda n: 500)
    hits = [_hit(f"S{i}.pdf", "x") for i in range(5)]
    monkeypatch.setattr(c, "_post", lambda *a, **k: {"ok": True, "hits": hits})

    out = c.search("frage")
    assert "**2 hits**" in out
    assert "3 further ranked hits omitted" in out


def test_search_notes_the_source_denominator_when_more_contribute(monkeypatch):
    # "8 hits" alone says nothing about whether that is most of the field or a
    # sliver of it — a _coverage dict attached to hits[0] by query.search() carries
    # the denominator, and mcp_client.search() must surface it and strip the
    # internal key back out (it is search metadata, not a payload field).
    from brag import config
    from brag import mcp_client as c

    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765", raising=False)
    monkeypatch.setattr(config, "OPEN_BRIDGE_ENABLED", False, raising=False)
    monkeypatch.setattr(c, "max_hits_for_budget", lambda: 50)
    monkeypatch.setattr(c, "preview_chars_for", lambda n: 500)
    hits = [_hit("A.pdf", "x")]
    hits[0]["_coverage"] = {"gezeigt": 1, "beitragend": 4}
    monkeypatch.setattr(c, "_post", lambda *a, **k: {"ok": True, "hits": hits})

    out = c.search("frage")
    assert "showing 1 of 4 sources that contribute to this question" in out
    assert "_coverage" not in out


def test_search_omits_source_denominator_note_when_all_shown(monkeypatch):
    from brag import config
    from brag import mcp_client as c

    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765", raising=False)
    monkeypatch.setattr(config, "OPEN_BRIDGE_ENABLED", False, raising=False)
    monkeypatch.setattr(c, "max_hits_for_budget", lambda: 50)
    monkeypatch.setattr(c, "preview_chars_for", lambda n: 500)
    hits = [_hit("A.pdf", "x")]
    hits[0]["_coverage"] = {"gezeigt": 1, "beitragend": 1}
    monkeypatch.setattr(c, "_post", lambda *a, **k: {"ok": True, "hits": hits})

    out = c.search("frage")
    assert "contribute to this question" not in out


def test_source_denominator_numerator_tracks_the_budget_trim(monkeypatch):
    # N-1 (re-review): query.search() computes _coverage from its OWN (pre
    # mcp_client-budget) hit list. mcp_client.search() then trims that list to
    # ITS OWN ceiling and popped the stale _coverage unchanged — the header
    # could claim more sources "shown" than hit blocks actually rendered, which
    # is exactly the kind of false count the denominator exists to prevent.
    # Reproduced with the reviewer's own numbers: top_k=200 (300 contributing
    # sources), which exceeds the real default ceiling
    # (45000 // 350 == 128) — no mocking of max_hits_for_budget/preview_chars_for
    # here, so this is the real budget math, not a synthetic ceiling.
    from brag import config
    from brag import mcp_client as c

    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765", raising=False)
    monkeypatch.setattr(config, "OPEN_BRIDGE_ENABLED", False, raising=False)
    hits = [_hit(f"S{i}.pdf", "kurz") for i in range(200)]
    hits[0]["_coverage"] = {"gezeigt": 200, "beitragend": 300}
    monkeypatch.setattr(c, "_post", lambda *a, **k: {"ok": True, "hits": hits})

    out = c.search("frage")
    rendered = out.count("\n### [")   # one header per hit block actually shown
    import re
    m = re.search(r"showing (\d+) of (\d+) sources", out)
    assert m, "source-denominator note missing"
    assert int(m.group(1)) == rendered, (
        f"header claims {m.group(1)} sources shown, but {rendered} hit blocks "
        f"were actually rendered")


def test_search_notes_when_previews_are_shortened(monkeypatch):
    from brag import config
    from brag import mcp_client as c

    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765", raising=False)
    monkeypatch.setattr(config, "OPEN_BRIDGE_ENABLED", False, raising=False)
    monkeypatch.setattr(c, "max_hits_for_budget", lambda: 50)
    monkeypatch.setattr(c, "preview_chars_for", lambda n: 500)
    hits = [_hit("S.pdf", "x" * 2000)]
    monkeypatch.setattr(c, "_post", lambda *a, **k: {"ok": True, "hits": hits})

    out = c.search("frage")
    assert "previews shortened to 500 chars" in out
    assert ("x" * 500 + " …") in out
    assert "x" * 501 not in out
