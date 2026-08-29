"""Does the chosen local model actually see images?

BRAG's local backend sets `vision_capable = True` unconditionally: whether the
loaded model is multimodal cannot be read off its name, so the ingest attempts
vision and falls back to caption-only context when the model rejects the image.
That fallback is correct, but the user learns of it MID-INGEST, after two failed
figures — by which point they are hours into indexing and every figure of the
corpus is about to be reduced to its caption.

It can be settled in one request at setup time instead, on the one model the
user actually picked.
"""
import base64


from brag.llm_backends import openai_compatible as oc

# 1x1 transparent PNG — the smallest thing that is unambiguously an image.
_PIXEL = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c63000100000500010d0a2db40000"
    "000049454e44ae426082"
)).decode()


def _backend(monkeypatch, antwort):
    """A backend whose chat() behaves like `antwort` when given an image."""
    from brag import config
    monkeypatch.setattr(config, "LLM_BASE_URL", "http://stub/v1", raising=False)
    b = oc.OpenAICompatibleLLM()
    gesehen = {}

    def chat(prompt, max_tokens=1024, images=None):
        gesehen["images"] = images
        gesehen["max_tokens"] = max_tokens
        if callable(antwort):
            return antwort()
        return antwort

    b.chat = chat
    return b, gesehen


def test_a_model_that_answers_an_image_is_reported_as_capable(monkeypatch):
    b, gesehen = _backend(monkeypatch, "ok")
    kann, grund = b.can_see_images()
    assert kann is True, grund
    assert gesehen["images"], "the probe must actually send an image"
    assert gesehen["max_tokens"] <= 8, (
        "the probe only needs to know whether the request is accepted — asking "
        "for a long answer would make a slow local model slower still"
    )


def test_a_model_that_rejects_the_image_is_reported_as_text_only(monkeypatch):
    import urllib.error

    def raise_400():
        raise urllib.error.HTTPError("u", 400, "no vision", {}, None)

    b, _ = _backend(monkeypatch, raise_400)
    kann, grund = b.can_see_images()
    assert kann is False
    assert grund, "the reason must be reported, not swallowed"


def test_an_empty_answer_counts_as_not_capable(monkeypatch):
    # LM Studio returns None from chat() once its own retries are exhausted.
    b, _ = _backend(monkeypatch, None)
    assert b.can_see_images()[0] is False


def test_an_unreachable_server_is_not_reported_as_text_only(monkeypatch):
    """A model that could not be asked is UNKNOWN, not text-only — telling a
    user their multimodal model is text-only because LM Studio was busy would
    send them off to change a setting that was never the problem."""
    def raise_conn():
        raise OSError("connection refused")

    b, _ = _backend(monkeypatch, raise_conn)
    kann, grund = b.can_see_images()
    assert kann is None, f"expected unknown, got {kann!r} ({grund})"


# ── the setup endpoint ───────────────────────────────────────────────────────

class _Handler:
    """Just enough of the request handler to exercise the endpoint."""

    def __init__(self):
        self.antwort = None

    def _send_json(self, code, payload):
        self.antwort = (code, payload)

    from brag.http_bridge import BridgeHandler as _B
    _check_vision = _B._check_vision


def test_the_endpoint_probes_the_model_the_user_picked(monkeypatch):
    from brag import config
    gesehen = {}

    class _LLM:
        def can_see_images(self):
            gesehen["model"] = config.LLM_MODEL
            return True, "the model accepted an image"

    monkeypatch.setattr("brag.llm_backends.get_llm", lambda: _LLM(), raising=False)
    h = _Handler()
    h._check_vision({"model": "qwen/qwen3-vl-8b"})
    code, payload = h.antwort
    assert code == 200 and payload["ok"] is True
    assert gesehen["model"] == "qwen/qwen3-vl-8b", (
        "the probe must run against the model the user selected, not whatever "
        "happens to be configured"
    )


def test_the_endpoint_restores_the_configured_model_afterwards(monkeypatch):
    from brag import config
    monkeypatch.setattr(config, "LLM_MODEL", "vorher", raising=False)

    class _LLM:
        def can_see_images(self):
            return True, "ok"

    monkeypatch.setattr("brag.llm_backends.get_llm", lambda: _LLM(), raising=False)
    h = _Handler()
    h._check_vision({"model": "etwas anderes"})
    assert config.LLM_MODEL == "vorher", (
        "probing must not leave the setup pointing at a model the user did not "
        "confirm"
    )


def test_an_unknown_result_is_not_presented_as_a_failure(monkeypatch):
    class _LLM:
        def can_see_images(self):
            return None, "could not reach the model server"

    monkeypatch.setattr("brag.llm_backends.get_llm", lambda: _LLM(), raising=False)
    h = _Handler()
    h._check_vision({"model": "m"})
    _, payload = h.antwort
    assert payload["ok"] is None and payload["message"]
