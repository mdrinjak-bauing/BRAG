"""Ein echter Bridge-Fehler darf sich nicht wie eine Anlaufphase lesen.

Der Thin-Client fing `(URLError, OSError, …)` — und HTTPError ist eine Subklasse
von URLError. Eine Antwort mit 404/413/500, die eine konkrete Ursache mitbringt,
landete damit im selben Zweig wie ein nicht erreichbarer Port und kam beim Nutzer
als „service is starting up or unavailable" an. Am teuersten ist das beim
Umschalten: dort wartet man dann auf eine Aufwaermphase, die es nicht gibt.
"""
import io
import json
import urllib.error


def _http_error(status: int, body: dict):
    return urllib.error.HTTPError(
        url="http://localhost:8770/api/index-op", code=status, msg="err",
        hdrs=None, fp=io.BytesIO(json.dumps(body).encode()))


def test_a_bridge_error_body_reaches_the_user(monkeypatch):
    from brag import mcp_client as c
    antwort = {"ok": False, "message": "unknown project 'thesis' — re-run setup"}

    def _raise(*a, **k):
        raise _http_error(404, antwort)

    monkeypatch.setattr(c.urllib.request, "urlopen", _raise)
    assert c._post("/api/index-op", {}) == antwort
    # …und der Aufrufer zeigt die echte Ursache statt der Aufwaerm-Meldung.
    text = c._index_op("list_sources")
    assert "re-run setup" in text
    assert text != c._BUSY


def test_an_unreachable_bridge_still_reads_as_starting_up(monkeypatch):
    """Die Unterscheidung ist der ganze Punkt: der Transportfall bleibt _BUSY."""
    from brag import mcp_client as c

    def _raise(*a, **k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(c.urllib.request, "urlopen", _raise)
    assert c._post("/api/index-op", {}) is None
    assert c._index_op("list_sources") == c._BUSY


def test_an_http_error_without_a_usable_body_falls_back_to_busy(monkeypatch):
    """Eine Fehlerantwort ohne JSON-Körper (nackte Gateway-Seite) traegt keine
    Ursache — dann ist die allgemeine Meldung wieder die ehrlichere."""
    from brag import mcp_client as c

    def _raise(*a, **k):
        raise urllib.error.HTTPError(
            url="http://localhost:8770/api/search", code=502, msg="bad gateway",
            hdrs=None, fp=io.BytesIO(b"<html>502</html>"))

    monkeypatch.setattr(c.urllib.request, "urlopen", _raise)
    assert c._post("/api/search", {}) is None
    assert c._index_op("list_sources") == c._BUSY
