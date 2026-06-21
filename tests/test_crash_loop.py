from brag import config
from brag.ingest import pipeline


def test_crash_loop_guard_skips_after_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)  # DATA_DIR + VAULT under tmp
    monkeypatch.setattr(config, "INGEST_MAX_ATTEMPTS", 2)
    p = tmp_path / "doc.pdf"
    src = "doc"

    # First two attempts proceed (counted, not skipped) ...
    assert pipeline._crash_loop_skip(src, p) is False
    assert pipeline._crash_loop_skip(src, p) is False
    # ... the third would be the 3rd interruption -> skip + stays skipped.
    assert pipeline._crash_loop_skip(src, p) is True
    assert pipeline._crash_loop_skip(src, p) is True

    # A visible marker was written into the vault root.
    assert list(tmp_path.glob("INDEX*.md")), "expected an indexing-stopped marker"

    # Removing/redropping the source clears the counter -> it retries again.
    pipeline._clear_attempts(src)
    assert pipeline._crash_loop_skip(src, p) is False


def test_clear_attempts_is_noop_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    pipeline._clear_attempts("never-seen")  # must not raise
    assert pipeline._load_attempts() == {}
