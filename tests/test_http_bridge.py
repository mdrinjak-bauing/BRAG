"""Security-guard tests for the HTTP bridge (finding #6).

The bridge's only real trust boundary is a handful of in-handler guards:

- _host_ok        — Host-header allowlist (the actual "localhost only"
                    enforcement / anti DNS-rebinding, since the server binds
                    0.0.0.0 inside the container).
- _origin_ok      — rejects cross-origin browser POSTs to the setup API.
- _serve_vault_file — path-traversal guard for /file/<rel>; also the
                    inline-PDF vs force-download (stored-XSS) hardening.
- do_POST body cap — refuses an oversized Content-Length (memory DoS).

None of these were exercised before. These tests drive them directly with
adversarial inputs, with no socket, no network, and no heavy deps
(no torch / qdrant / docling) — same constraint as tests/test_unit.py.

BridgeHandler subclasses BaseHTTPRequestHandler, whose __init__ reads from a
socket. We sidestep that by allocating the instance with object.__new__ and
attaching just the attributes the guards touch: a `headers` mapping and a
captured `_send` / `_send_json`.
"""

import json

from brag import config, http_bridge
from brag.http_bridge import (
    LOOPBACK_NAMES,
    MAX_BODY_BYTES,
    SETUP_CSP,
    BridgeHandler,
)


class _Captured:
    """Records the (code, body, mime, extra) of the handler's response."""

    def __init__(self):
        self.code = None
        self.body = None
        self.mime = None
        self.extra = None
        self.json = None


def _make_handler(headers=None):
    """A BridgeHandler with no socket: only `headers` + captured responses."""
    h = object.__new__(BridgeHandler)
    h.headers = dict(headers or {})
    captured = _Captured()

    def fake_send(code, body, mime, extra=None):
        captured.code = code
        captured.body = body
        captured.mime = mime
        captured.extra = extra or {}

    def fake_send_json(code, payload):
        captured.code = code
        captured.json = payload
        captured.body = json.dumps(payload).encode()
        captured.mime = "application/json"

    h._send = fake_send
    h._send_json = fake_send_json
    h.captured = captured
    return h


class _FakeRFile:
    """Stands in for self.rfile; do_POST should never read past the cap."""

    def __init__(self, data=b""):
        self._data = data
        self.reads = 0

    def read(self, n):
        self.reads += 1
        return self._data[:n]


# ── Host-header allowlist (_host_ok) ──────────────────────────────
def test_host_ok_accepts_loopback_names_and_ports():
    # The bridge always listens on a port, so a real IPv6-loopback request
    # carries the bracketed host-with-port form ("[::1]:8765"). A bare, portless
    # "[::1]" is not a real input here and the conservative port-strip leaves it
    # rejected — which is fine: the guard fails CLOSED, never open.
    for host in ("localhost", "127.0.0.1", "localhost:8765",
                 "127.0.0.1:8765", "[::1]:8765", "LOCALHOST"):
        assert _make_handler({"Host": host})._host_ok(), host


def test_host_ok_rejects_foreign_and_rebinding_hosts():
    for host in ("evil.com", "attacker.localhost.evil.com",
                 "localhost.evil.com", "127.0.0.1.evil.com",
                 "169.254.169.254", "example.com:8765",
                 "[::1].evil.com"):  # bracket-confusion must fail closed
        assert not _make_handler({"Host": host})._host_ok(), host


def test_host_ok_rejects_missing_host():
    assert not _make_handler({})._host_ok()
    assert not _make_handler({"Host": ""})._host_ok()


# ── Origin check on POST (_origin_ok) ───────────────────────────
def test_origin_ok_allows_absent_origin():
    # Non-browser caller: no Origin header — the Host check still applies.
    assert _make_handler({})._origin_ok()


def test_origin_ok_allows_loopback_origins():
    for origin in ("http://localhost:8765", "http://127.0.0.1",
                   "https://localhost", "http://[::1]:8765"):
        assert _make_handler({"Origin": origin})._origin_ok(), origin


def test_origin_ok_rejects_cross_origin_post():
    for origin in ("https://evil.com", "http://attacker.localhost.evil.com",
                   "http://127.0.0.1.evil.com", "https://example.com:8765"):
        assert not _make_handler({"Origin": origin})._origin_ok(), origin


def test_origin_ok_rejects_malformed_origin():
    # urlparse(...).hostname is None — a value with no host part must not pass.
    assert not _make_handler({"Origin": "not a url"})._origin_ok()


# ── Path-traversal guard (_serve_vault_file) ────────────────────
def _vault(tmp_path, monkeypatch):
    """Point config.VAULT at a fresh tmp dir holding one real file."""
    monkeypatch.setattr(config, "VAULT", tmp_path)
    (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "note.html").write_text("<script>alert(1)</script>", encoding="utf-8")
    # A secret living OUTSIDE the vault, the target of traversal attempts.
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")
    return secret


def test_serve_vault_file_serves_real_pdf_inline(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    h = _make_handler()
    h._serve_vault_file("doc.pdf")
    assert h.captured.code == 200
    assert h.captured.mime == "application/pdf"
    # Inline render (no forced download) so the browser can jump to #page=N.
    assert "Content-Disposition" not in h.captured.extra


def test_serve_vault_file_forces_download_for_non_pdf(tmp_path, monkeypatch):
    # Stored-XSS hardening: never serve store HTML as active same-origin content.
    _vault(tmp_path, monkeypatch)
    h = _make_handler()
    h._serve_vault_file("note.html")
    assert h.captured.code == 200
    assert h.captured.mime == "application/octet-stream"
    assert h.captured.extra.get("Content-Disposition") == "attachment"


def test_serve_vault_file_blocks_dotdot_escape(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    for rel in ("../secret.txt", "../../secret.txt",
                "sub/../../secret.txt", "./../secret.txt"):
        h = _make_handler()
        h._serve_vault_file(rel)
        assert h.captured.code == 403, rel
        assert h.captured.body == b"forbidden", rel


def test_serve_vault_file_blocks_absolute_path(tmp_path, monkeypatch):
    secret = _vault(tmp_path, monkeypatch)
    for rel in (str(secret), "/etc/passwd", str(secret.resolve())):
        h = _make_handler()
        h._serve_vault_file(rel)
        # An absolute path resolves outside VAULT -> relative_to() raises -> 403.
        # (If it somehow resolved inside, it still would not be a file -> 404;
        #  either way it must never hand back the out-of-vault secret as 200.)
        assert h.captured.code in (403, 404), rel
        assert h.captured.body != b"top secret", rel


def test_serve_vault_file_missing_in_vault_is_404(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    h = _make_handler()
    h._serve_vault_file("does_not_exist.pdf")
    assert h.captured.code == 404


# ── Body-size cap on POST (do_POST) ─────────────────────────
def test_do_post_rejects_oversized_body(monkeypatch):
    # Pass Host + SETUP_MODE so control reaches the Content-Length cap.
    monkeypatch.setattr(config, "SETUP_MODE", True)
    h = _make_handler({"Host": "localhost",
                       "Content-Length": str(MAX_BODY_BYTES + 1)})
    h.path = "/api/setup"
    h.rfile = _FakeRFile(b"x")
    h.do_POST()
    assert h.captured.code == 413
    assert h.captured.json == {"ok": False, "message": "request too large"}
    # The cap must fire BEFORE reading the body (no memory exhaustion).
    assert h.rfile.reads == 0


def test_do_post_blocked_by_host_guard_before_setup(monkeypatch):
    monkeypatch.setattr(config, "SETUP_MODE", True)
    h = _make_handler({"Host": "evil.com"})
    h.path = "/api/setup"
    h.rfile = _FakeRFile(b"{}")
    h.do_POST()
    assert h.captured.code == 403
    assert h.captured.json == {"ok": False, "message": "forbidden"}


def test_do_post_blocked_by_origin_guard(monkeypatch):
    monkeypatch.setattr(config, "SETUP_MODE", True)
    h = _make_handler({"Host": "localhost", "Origin": "https://evil.com"})
    h.path = "/api/setup"
    h.rfile = _FakeRFile(b"{}")
    h.do_POST()
    assert h.captured.code == 403
    assert h.captured.json == {"ok": False, "message": "forbidden"}


# ── Security constants ───────────────────────────────────
def test_loopback_names_are_locked_down():
    assert set(LOOPBACK_NAMES) == {"localhost", "127.0.0.1", "::1"}


def test_body_cap_is_sane():
    assert 0 < MAX_BODY_BYTES <= 5_000_000


def test_setup_csp_is_strict():
    # default-src 'none' + no remote origins — the lock-everything-down baseline.
    assert "default-src 'none'" in SETUP_CSP
    assert "connect-src 'self'" in SETUP_CSP
    assert "base-uri 'none'" in SETUP_CSP
    assert "form-action 'none'" in SETUP_CSP
    assert "http://" not in SETUP_CSP and "https://" not in SETUP_CSP


# ── Shared search service (/api/search) ──────────────────────────
def test_api_search_unknown_project_returns_404(tmp_path, monkeypatch):
    # /api/search must work on the PERSISTENT app (SETUP_MODE off) and 404 a
    # project that is not in the registry.
    monkeypatch.setattr(config, "SETUP_MODE", False)
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "projects.json"))  # empty
    data = json.dumps({"project": "ghost", "query": "x"}).encode()
    h = _make_handler({"Host": "localhost", "Content-Length": str(len(data))})
    h.path = "/api/search"
    h.rfile = _FakeRFile(data)
    h.do_POST()
    assert h.captured.code == 404
    assert h.captured.json["ok"] is False
    assert "ghost" in h.captured.json["message"]


def test_api_search_runs_when_setup_off(tmp_path, monkeypatch):
    # With SETUP_MODE off and no project, /api/search runs against the default
    # collection and returns hits as plain dicts. search() is stubbed so the test
    # needs no Qdrant / models.
    monkeypatch.setattr(config, "SETUP_MODE", False)
    monkeypatch.setenv("BRAG_REGISTRY", str(tmp_path / "projects.json"))
    seen = {}

    def fake_search(query, **kw):
        seen["query"] = query
        seen["collection_name"] = kw.get("collection_name")
        return [{"text": "hi", "source_file": "a.pdf", "score": 1.0}]

    monkeypatch.setattr("brag.search.query.search", fake_search)
    data = json.dumps({"query": "hello", "top_k": 5}).encode()
    h = _make_handler({"Host": "localhost", "Content-Length": str(len(data))})
    h.path = "/api/search"
    h.rfile = _FakeRFile(data)
    h.do_POST()
    assert h.captured.code == 200
    assert h.captured.json["ok"] is True
    assert h.captured.json["hits"][0]["text"] == "hi"
    assert seen["query"] == "hello"
    assert seen["collection_name"] is None  # single-project default


# Keep a reference to http_bridge so the import is obviously load-bearing
# (the module must import cleanly with no heavy deps).
assert http_bridge.BridgeHandler is BridgeHandler
