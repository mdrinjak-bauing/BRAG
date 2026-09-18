"""BRAG must import on whichever mcp major version is installed.

mcp 2.x renamed FastMCP to MCPServer and left a tombstone module behind:
`mcp/server/fastmcp.py` raises ModuleNotFoundError with the migration hint. Two
import lines in BRAG point at it, so on mcp 2.x the MCP server and the thin
client fail to import at all — the connector simply never starts.

The unit CI job installs mcp UNPINNED while users get requirements.txt's pin, so
what CI proves and what users run are not the same thing. That is the reason
this went unnoticed: only the e2e job touches these modules.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_the_mcp_server_imports_on_the_installed_mcp():
    import brag.mcp_server as s
    assert s.mcp is not None
    assert hasattr(s.mcp, "tool") and hasattr(s.mcp, "run")


def test_the_thin_client_imports_on_the_installed_mcp():
    import brag.mcp_client as c
    assert c.mcp is not None
    assert hasattr(c.mcp, "tool") and hasattr(c.mcp, "run")


def test_the_server_still_registers_every_tool():
    """A shim that imports but registers nothing would pass the tests above and
    leave the assistant with no tools at all."""
    import re
    quelle = (REPO / "brag" / "mcp_server.py").read_text(encoding="utf-8")
    erwartet = len(re.findall(r"^@mcp\.tool\(\)", quelle, re.M))
    assert erwartet >= 20, f"only {erwartet} @mcp.tool() decorators found — parse error?"
    import asyncio

    import brag.mcp_server as s
    werkzeuge = asyncio.run(s.mcp.list_tools())
    assert len(werkzeuge) == erwartet, (
        f"{erwartet} tools are decorated but {len(werkzeuge)} are registered"
    )


def test_ci_installs_the_same_mcp_users_get():
    """The unit job pip-installed mcp unpinned, so it silently tested a
    different major version than requirements.txt ships. That is exactly how an
    import break reaches users through green CI."""
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    lose = [z.strip() for z in ci.splitlines()
            if "pip install" in z and re.search(r"\bmcp\b(?!==)", z)]
    assert not lose, f"mcp is installed unpinned in CI: {lose}"



def test_the_remote_audit_sees_tools_behind_a_stacked_decorator():
    """Die Selbstpruefung der Remote-Instanz suchte den Dekorator mit einem
    regulaeren Ausdruck, der ihn DIREKT ueber `def` verlangte. Steht dazwischen ein
    weiterer Dekorator (@with_topic_hint, @with_passage_layout_note), war das Tool
    unsichtbar — gemessen 25 statt 27, ausgerechnet `search` und `save_passage`.
    Die harte Absicherung greift weiter, verloren war die Drift-Warnung: ein neues,
    unklassifiziertes Tool mit Zusatz-Dekorator haette niemand gemeldet."""
    import ast

    from brag.mcp_server_remote import _declared_tools
    quelle = (REPO / "brag" / "mcp_server.py").read_text(encoding="utf-8")

    gefunden = _declared_tools(quelle)
    assert {"search", "save_passage"} <= gefunden, (
        "genau die Tools mit Zusatz-Dekorator fehlen wieder")

    # Gegenprobe gegen den Syntaxbaum selbst: KEIN dekoriertes Tool darf fehlen.
    alle = {k.name for k in ast.walk(ast.parse(quelle))
            if isinstance(k, (ast.FunctionDef, ast.AsyncFunctionDef))
            for d in k.decorator_list
            if getattr(getattr(d, "func", d), "attr", "") == "tool"}
    assert gefunden == alle
    # Der alte regulaere Ausdruck sah weniger — daran haengt der Befund.
    alt = set(re.findall(r"@mcp\.tool\([^)]*\)\s*\ndef\s+(\w+)", quelle))
    assert len(alt) < len(gefunden)


def test_every_remote_tool_is_classified():
    """Was die Warnung eigentlich absichert: jedes Tool ist entweder freigegeben
    oder gesperrt — ein neues faellt per Default auf 'nicht exponiert', soll aber
    auffallen."""
    from brag.mcp_server_remote import EXPOSED, WITHHELD, _declared_tools
    quelle = (REPO / "brag" / "mcp_server.py").read_text(encoding="utf-8")
    unklassifiziert = _declared_tools(quelle) - set(EXPOSED) - set(WITHHELD)
    assert not unklassifiziert, f"nicht klassifizierte Tools: {sorted(unklassifiziert)}"


def test_the_topic_filter_is_a_parameter_on_both_search_surfaces():
    """Der alte Thin-Client bot `search(..., topic=…)`; der neue nicht mehr. Die
    Filterung selbst lief weiter ueber meta_filter='topic=…' — aber die eigene
    Doku fuehrt `topic` als Filter, und jede gespeicherte Anweisung, die
    search(topic="…") aufruft, scheiterte an der Schema-Pruefung."""
    import inspect

    import brag.mcp_client as c
    import brag.mcp_server as s
    for fn in (c.search, s.search):
        assert "topic" in inspect.signature(fn).parameters, fn.__module__


def test_the_topic_parameter_lands_on_the_existing_meta_mechanism(monkeypatch):
    """Kein zweiter Filtermechanismus: `topic` ist ein gewoehnliches Payload-Feld
    und wird auf denselben meta-Weg abgebildet."""
    import brag.mcp_client as c
    import brag.mcp_server as s

    gesehen = {}
    monkeypatch.setattr(c, "_post", lambda pfad, body, **k: gesehen.update(body) or None)
    c.search("frage", topic="beispiel-thema")
    assert gesehen["meta"] == {"topic": "beispiel-thema"}

    # Ein ausdrueckliches meta_filter='topic=…' behaelt Vorrang.
    gesehen.clear()
    c.search("frage", topic="A", meta_filter="topic=B, projekt=X")
    assert gesehen["meta"] == {"topic": "B", "projekt": "X"}

    # Serverseitig dasselbe, ueber tools.search_hits' meta_filter-String.
    gesehen.clear()
    monkeypatch.setattr(s.tools, "search_hits",
                        lambda *a, **k: gesehen.update(k) or [])
    s.search("frage", topic="beispiel-thema")
    from brag.formatting import parse_meta_filter
    assert parse_meta_filter(gesehen["meta_filter"]) == {"topic": "beispiel-thema"}
