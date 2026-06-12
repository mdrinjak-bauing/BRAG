"""HTTP bridge: serves vault PDFs to the host browser so search results can
link directly to the right page (…/pdf/<path>#page=N opens the browser's
PDF viewer at that page). Runs inside the container, bound to 0.0.0.0.
"""

import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from asb import config

MIME = {
    ".pdf": "application/pdf",
    ".md": "text/markdown; charset=utf-8",
    ".html": "text/html; charset=utf-8",
}


class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep container logs quiet
        pass

    def do_GET(self):  # noqa: N802 — http.server API
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/healthz":
            self._send(200, b"ok", "text/plain")
            return
        if parsed.path.startswith("/file/"):
            rel = urllib.parse.unquote(parsed.path[len("/file/"):])
            self._serve_vault_file(rel)
            return
        self._send(404, b"not found", "text/plain")

    def _serve_vault_file(self, rel: str):
        # Resolve against the vault and refuse anything that escapes it
        target = (config.VAULT / rel).resolve()
        try:
            target.relative_to(config.VAULT.resolve())
        except ValueError:
            self._send(403, b"forbidden", "text/plain")
            return
        if not target.is_file():
            self._send(404, b"file not found", "text/plain")
            return
        mime = MIME.get(target.suffix.lower(), "application/octet-stream")
        data = target.read_bytes()
        self._send(200, data, mime)

    def _send(self, code: int, body: bytes, mime: str):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


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
