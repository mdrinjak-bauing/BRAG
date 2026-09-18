"""Klick-Bridge — kleiner HTTP-Server auf localhost, der Treffer-Links klickbar macht.

Claude Desktop blockiert `file://`-Links (Sicherheit), rendert aber
`http://localhost`-Links als anklickbare Buttons. Dieser Server übersetzt
`/open?source=<stem>&book_page=<X>` (bzw. `&pdf_page=<N>`) in `pdf_open.open_pdf`
(öffnet Skim an der richtigen Seite). So tragen BRAGs Treffer-Überschriften einen
echten Klick-Link — der Nutzer öffnet das PDF selbst, der Assistent muss es nicht
automatisch tun.

Läuft als Daemon-Thread im MCP-Subprozess (stirbt mit ihm), bindet NUR an
127.0.0.1 (loopback). Portkonflikt/Fehler werden geschluckt; die Treffer bleiben
nutzbar. Port und Aktivierung kommen aus der Konfiguration
(BRAG_OPEN_BRIDGE, BRAG_OPEN_BRIDGE_PORT); die Vorgabe liegt neben BRIDGE_PORT,
nicht darauf.
"""

from __future__ import annotations

import sys
import threading
from urllib.parse import parse_qs, quote, urlparse

from brag import config


def _port() -> int:
    """Read live, so an environment override is honoured without re-import."""
    return config.OPEN_BRIDGE_PORT

_started = False
_LOCK = threading.Lock()


def open_link(source_file: str, page, physical: bool = False) -> str:
    """Anklickbarer localhost-Link, der das PDF in Skim an der Seite öffnet.
    physical=True: `page` ist die PHYSISCHE PDF-Seite und wird als `pdf_page`
    übergeben — open_pdf springt direkt dorthin, OHNE Buch→physisch-Umrechnung
    (2026-07-21: behebt die fehleranfällige Laufzeit-Auflösung). physical=False:
    `page` ist die Buchseite (`book_page`), open_pdf löst via /PageLabels auf."""
    src = quote(str(source_file or ""), safe="")
    out = f"http://localhost:{_port()}/open?source={src}"
    if page not in (None, ""):
        key = "pdf_page" if physical else "book_page"
        out += f"&{key}={quote(str(page), safe='')}"
    return out


def _make_handler():
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):  # noqa: A002 — silence default logging
            pass

        def _send(self, code: int, ctype: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _host_ok(self) -> bool:
            """Nur an localhost adressierte Anfragen zulassen (Anti-DNS-Rebinding):
            verhindert, dass eine beliebige Webseite im Browser per GET das PDF-Oeffnen
            (und damit pdf_open) fernausloest."""
            host = self.headers.get("Host", "")
            name = host.rsplit(":", 1)[0].strip("[]").lower() if host else ""
            return name in ("localhost", "127.0.0.1", "::1", "")

        def do_GET(self):  # noqa: N802 — http.server API
            if not self._host_ok():
                self._send(403, "text/plain; charset=utf-8", b"forbidden")
                return
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                self._send(200, "text/plain; charset=utf-8", b"ok")
                return
            if parsed.path == "/open":
                import unicodedata as ud

                from brag import pdf_open
                qs = parse_qs(parsed.query)
                source = qs.get("source", [""])[0]
                book_page = qs.get("book_page", [None])[0]
                pdf_page = qs.get("pdf_page", [None])[0]
                pp = int(pdf_page) if pdf_page and pdf_page.isdigit() else None
                # NFC/NFD-robust: macOS-Dateinamen sind NFD, Links können NFC sein.
                candidate = "PDF nicht gefunden."
                result = None
                for variant in dict.fromkeys([
                    ud.normalize("NFC", source), ud.normalize("NFD", source), source,
                ]):
                    candidate = pdf_open.open_pdf(variant, pdf_page=pp, book_page=book_page)
                    if candidate.startswith("✓") or candidate.startswith("Timeout"):
                        result = candidate
                        break
                result = result or candidate
                html = (
                    "<!doctype html><meta charset='utf-8'><title>PDF</title>"
                    "<body style='font-family:system-ui;padding:2em'>"
                    f"<h2>📂 PDF wird in Skim geöffnet</h2><p>{result}</p>"
                    "<p><small>Du kannst diesen Tab schließen.</small></p>"
                    "<script>setTimeout(()=>window.close(),1500)</script></body>"
                )
                self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))
                return
            self._send(404, "text/plain; charset=utf-8", b"not found")

    return _Handler


def start() -> None:
    """Startet die Klick-Bridge als Daemon-Thread (idempotent)."""
    global _started
    with _LOCK:
        if _started:
            return
        _started = True

    port = _port()

    def _serve():
        import socketserver
        try:
            socketserver.TCPServer.allow_reuse_address = True
            httpd = socketserver.TCPServer(("127.0.0.1", port), _make_handler())
        except OSError as e:  # Port belegt (z. B. andere BRAG-Instanz) — Links zeigen
            # trotzdem auf denselben Port; die laufende Bridge bedient sie.
            print(f"open-bridge: Port {port} nicht gebunden ({e})", file=sys.stderr)
            return
        httpd.serve_forever()

    threading.Thread(target=_serve, daemon=True).start()
