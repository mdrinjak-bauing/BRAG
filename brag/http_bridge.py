"""HTTP bridge (port 8765, mapped to localhost only on the host).

Serves:
- /file/<store-relative-path>   knowledge-store documents for the browser, so search
                                results can deep-link to a PDF page (#page=N)
- /setup + /api/...             the browser-based setup wizard — ONLY when
                                SETUP_MODE=1 (the one-shot `setup` compose
                                service); the persistent app keeps it disabled
- /healthz                      liveness probe
"""

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from brag import config

SETUP_PAGE = Path(__file__).parent / "setup_page.html"

# Setup API bodies are tiny JSON — cap the read so a loopback client cannot
# exhaust memory with a huge Content-Length.
MAX_BODY_BYTES = 1_000_000

# The setup page uses inline script/style and only talks to its own origin.
# A strict CSP keeps it from loading or exfiltrating to anywhere else — a
# second line of defence behind output-escaping on the page itself.
SETUP_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'"
)

# Only requests addressed to the loopback interface are served. The bridge
# binds 0.0.0.0 (Docker port-publishing connects via the container's eth0, so
# binding 127.0.0.1 in-container would break the host mapping), so this
# Host-header allowlist is what actually enforces "localhost only" and defeats
# DNS-rebinding attacks against the setup API.
LOOPBACK_NAMES = ("localhost", "127.0.0.1", "::1")


class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep container logs quiet
        pass

    # ── GET ─────────────────────────────────────────────────────
    def do_GET(self):  # noqa: N802 — http.server API
        if not self._host_ok():
            self._send(403, b"forbidden", "text/plain")
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/healthz":
            self._send(200, b"ok", "text/plain")
        elif parsed.path in ("/", "/setup"):
            # The wizard is served only by the one-shot setup service (the only
            # one with the project + Claude-config mounts). On the persistent
            # app, point the user at the launcher instead of a wizard that
            # could not write anything anyway.
            if not config.SETUP_MODE:
                self._send(200,
                           b"Setup is not running here. Double-click setup.command "
                           b"(macOS) or setup.bat (Windows) to (re-)configure BRAG.",
                           "text/plain")
                return
            self._send(200, SETUP_PAGE.read_bytes(), "text/html; charset=utf-8",
                       extra={"Content-Security-Policy": SETUP_CSP})
        elif parsed.path.startswith("/file/"):
            rel = urllib.parse.unquote(parsed.path[len("/file/"):])
            self._serve_vault_file(rel)
        else:
            self._send(404, b"not found", "text/plain")

    # ── POST (setup API) ────────────────────────────────────────
    def do_POST(self):  # noqa: N802
        if not self._host_ok() or not self._origin_ok():
            self._send_json(403, {"ok": False, "message": "forbidden"})
            return
        # The config-writing setup API exists only in the one-shot setup service.
        if not config.SETUP_MODE:
            self._send_json(404, {"ok": False, "message": "setup not active"})
            return
        parsed = urllib.parse.urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY_BYTES:
                self._send_json(413, {"ok": False, "message": "request too large"})
                return
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "message": "invalid request"})
            return

        if parsed.path == "/api/validate-key":
            from brag.setup_core import validate_api_key
            ok, message = validate_api_key(
                str(body.get("provider", "gemini")), str(body.get("key", "")))
            self._send_json(200, {"ok": ok, "message": message})
        elif parsed.path == "/api/check-local":
            self._check_local(body)
        elif parsed.path == "/api/setup":
            self._apply_setup(body)
        else:
            self._send_json(404, {"ok": False, "message": "unknown endpoint"})

    def _check_local(self, body: dict):
        """Probe the LLM app on the host (LM Studio / Ollama) and list models."""
        import urllib.request
        profile = str(body.get("profile", "hybrid"))
        if profile == "hybrid":
            url, app = "http://host.docker.internal:1234/v1/models", "LM Studio"
            hint = ("Open LM Studio, go to the Developer tab and click "
                    "'Start Server', then check again.")
        else:
            url, app = "http://host.docker.internal:11434/v1/models", "Ollama"
            hint = ("Install Ollama from ollama.com and make sure it is "
                    "running (its icon appears in the menu bar / tray), "
                    "then check again.")
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
            models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        except (OSError, json.JSONDecodeError):
            self._send_json(200, {"ok": False, "models": [],
                                  "message": f"{app} is not reachable. {hint}"})
            return

        # Embeddings are ALWAYS local (arctic, in-container) in every profile —
        # the local/Ollama profile only needs a chat model, NOT a pulled Ollama
        # embedding model. So we gate on the chat model alone.
        chat_models = [m for m in models if "embed" not in m.lower()]
        if not chat_models:
            self._send_json(200, {
                "ok": False, "models": [],
                "message": (f"{app} is running, but no language model is "
                            "loaded yet — see the steps above."),
            })
            return
        self._send_json(200, {
            "ok": True, "models": chat_models,
            "message": f"{app} is running with {len(chat_models)} model(s).",
        })

    def _apply_setup(self, body: dict):
        from brag import setup_core
        steps = []
        try:
            setup_core.write_env(
                profile=str(body.get("profile", "cloud")),
                api_key=str(body.get("api_key", "")),
                language=str(body.get("language", "english")),
                vault_path=str(body.get("vault_path", "")).strip() or "./wissensspeicher",
                llm_model=str(body.get("llm_model", "")).strip(),
            )
            steps.append({"ok": True, "message": "Configuration saved"})
        except OSError as e:
            steps.append({"ok": False, "message": f"Could not save configuration: {e}"})
            self._send_json(200, {"ok": False, "steps": steps})
            return

        custom_vault = bool(str(body.get("vault_path", "")).strip())
        if custom_vault:
            steps.append({"ok": True, "message":
                          "Custom knowledge folder noted — it will be prepared on first start"})
        else:
            created = setup_core.create_vault()
            steps.append({"ok": True, "message":
                          "Knowledge folder created (wissensspeicher/)" if created
                          else "Knowledge folder already exists — kept untouched"})

        claude_ok, claude_msg = setup_core.write_claude_config()
        steps.append({"ok": claude_ok, "message": claude_msg})

        setup_core.mark_setup_complete()
        steps.append({"ok": True, "message": "Restarting with your settings…"})
        self._send_json(200, {
            "ok": True, "steps": steps,
            "claude_manual_snippet": not claude_ok,
        })

    # ── helpers ─────────────────────────────────────────────────
    def _host_ok(self) -> bool:
        """Accept only requests addressed to localhost (anti DNS-rebinding)."""
        host = self.headers.get("Host", "")
        name = host.rsplit(":", 1)[0].strip("[]").lower() if host else ""
        return name in LOOPBACK_NAMES

    def _origin_ok(self) -> bool:
        """For state-changing POSTs, reject cross-origin browser requests."""
        origin = self.headers.get("Origin")
        if not origin:
            return True  # non-browser caller; the Host check still applies
        try:
            name = (urllib.parse.urlparse(origin).hostname or "").lower()
        except ValueError:
            return False
        return name in LOOPBACK_NAMES

    def _serve_vault_file(self, rel: str):
        target = (config.VAULT / rel).resolve()
        try:
            target.relative_to(config.VAULT.resolve())
        except ValueError:
            self._send(403, b"forbidden", "text/plain")
            return
        if not target.is_file():
            self._send(404, b"file not found", "text/plain")
            return
        if target.suffix.lower() == ".pdf":
            # PDFs render inline so the browser can jump to #page=N.
            self._send(200, target.read_bytes(), "application/pdf")
        else:
            # Never serve knowledge-store content (.html/.md/…) as active, same-origin
            # HTML — hand it back as a download (stored-XSS hardening).
            self._send(200, target.read_bytes(), "application/octet-stream",
                       extra={"Content-Disposition": "attachment"})

    def _send(self, code: int, body: bytes, mime: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, payload: dict):
        self._send(code, json.dumps(payload).encode(), "application/json")


def pdf_link(rel_path: str, page: int | None = None) -> str:
    """Public link that opens the document in the host browser at a page."""
    quoted = urllib.parse.quote(rel_path)
    anchor = f"#page={page}" if page else ""
    return f"{config.BRIDGE_PUBLIC_URL}/file/{quoted}{anchor}"


def start_bridge_in_background() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", config.BRIDGE_PORT), BridgeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"HTTP bridge listening on port {config.BRIDGE_PORT}")
    return server
