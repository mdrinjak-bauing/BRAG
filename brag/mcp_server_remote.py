"""BRAG — remote MCP surface (streamable-http), read + vault-write, NO delete.

Zweiter Einstieg NEBEN dem lokalen stdio-Server (``mcp_server.py``, den Claude
Desktop nutzt und der unangetastet bleibt). Gedacht fuer den Fernzugriff (z. B.
Handy ueber einen Tunnel): exponiert die Such-/Lese-Werkzeuge UND die
Vault-Schreib-/Bearbeiten-Werkzeuge — aber KEIN Loeschen und keine Korpus-Admin-
bzw. GUI-Werkzeuge (siehe EXPOSED/WITHHELD). vault_write respektiert
config.VAULT_WRITE_PROTECT, sodass Korpus/Code unantastbar bleiben. Die
Tool-Implementierungen werden 1:1 aus ``mcp_server`` uebernommen (kein Duplikat) —
hier wird nur die Teilmenge re-registriert.

Konfiguration ueber Umgebungsvariablen (dieselbe BRAG-Env wie die stdio-Instanz):
  BRAG_REMOTE_HOST           Bind-Adresse (Default 127.0.0.1 — lokal, sicher)
  BRAG_REMOTE_PORT           Port (Default 8811)
  BRAG_REMOTE_ALLOWED_HOSTS  Komma-Liste zusaetzlicher erlaubter Host-Header
                             (fuer den spaeteren oeffentlichen Tunnel-Namen;
                             leer = nur localhost, DNS-Rebinding-Schutz an)
  BRAG_REMOTE_PUBLIC_URL     Oeffentliche HTTPS-Basis (z. B. der Funnel-Name).
                             Gesetzt ⇒ OAuth-PFLICHT: /mcp nur mit Bearer-Token,
                             Login via brag.remote_auth (Ein-Nutzer-Passwort).
                             Leer ⇒ kein Auth (nur fuer rein lokalen Betrieb).
"""
from __future__ import annotations

import ast
import os
import sys

# mcp 2.x renamed FastMCP to MCPServer and left a tombstone module behind. Without
# this switch the remote connector does not import at all on mcp >= 2 — and the
# pinned requirement is 2.1.1, so that is the default install. Same shim as
# mcp_server.py and mcp_client.py; constructor, .tool() and .run() are
# call-compatible across both lines.
try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as FastMCP
except ModuleNotFoundError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from brag import mcp_server as _srv  # nur Import der Tool-Funktionen — startet KEINEN Server

# --- Tool-Freigabe: explizit gelistet, damit die Grenze auditierbar ist -----------
# Exponiert = Lesen + Vault-Schreiben/-Bearbeiten. LOESCHEN bleibt AUS (2026-07:
# mobil dieselben Vault-Funktionen wie lokal, nur ohne Loeschen).
EXPOSED = [
    # Lesen / Suche
    "search", "list_sources", "coverage", "clusters", "compare_positions",
    "vault_read", "vault_list", "vault_search", "vault_extract",
    "inspect_chunks", "read_source", "list_passages", "list_notebook",
    "read_note", "recent_sources",
    # Schreiben / Bearbeiten (KEIN Loeschen). vault_write respektiert
    # config.VAULT_WRITE_PROTECT → Korpus/Code bleiben unantastbar;
    # move_note verschiebt/benennt um, ueberschreibt aber nie.
    "vault_write", "vault_append", "vault_edit", "write_note", "save_passage",
    "set_metadata", "move_note",
]
WITHHELD = [  # NIE ueber die Remote-Instanz
    # Echtes Loeschen
    "delete_note", "delete_passage", "remove_source",
    # Korpus-Admin (kein Vault) bzw. GUI-Nebenwirkung auf dem Heim-Mac
    "rename_source", "open_pdf",
]

# --- Netzwerk-Einstellungen --------------------------------------------------------
HOST = os.environ.get("BRAG_REMOTE_HOST", "127.0.0.1").strip()
PORT = int(os.environ.get("BRAG_REMOTE_PORT", "8811"))

_extra = [h.strip() for h in
          os.environ.get("BRAG_REMOTE_ALLOWED_HOSTS", "").split(",") if h.strip()]
_transport_security = None
if _extra:
    # Oeffentlicher Betrieb: DNS-Rebinding-Schutz AN, aber Tunnel-Host freigeben.
    _allowed = ["127.0.0.1:*", "localhost:*", "[::1]:*", *[f"{h}:*" for h in _extra], *_extra]
    _transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_allowed,
        allowed_origins=_allowed + [f"https://{h}" for h in _extra],
    )
# Ohne _extra: transport_security=None → das SDK aktiviert bei host=127.0.0.1
# automatisch den localhost-Schutz (rein lokaler Baustein-1-Betrieb).

# --- OAuth (Pflicht fuer oeffentlichen Betrieb) ------------------------------------
PUBLIC_URL = os.environ.get("BRAG_REMOTE_PUBLIC_URL", "").strip().rstrip("/")

# Fail-closed (#3): ein oeffentlich erreichbarer Bind/Host DARF nicht ohne Auth starten.
# Sobald ein Nicht-localhost-Host erlaubt ist ODER nicht an localhost gebunden wird,
# ist BRAG_REMOTE_PUBLIC_URL (und damit OAuth) PFLICHT — sonst hart abbrechen.
_public_reachable = bool(_extra) or HOST not in ("127.0.0.1", "localhost", "::1")
if _public_reachable and not PUBLIC_URL:
    raise SystemExit(
        "brag-remote: ABBRUCH (fail-closed) — oeffentlich erreichbarer Host/Bind "
        f"(HOST={HOST}, ALLOWED_HOSTS={_extra or '—'}) OHNE BRAG_REMOTE_PUBLIC_URL, "
        "d. h. ohne OAuth. Entweder PUBLIC_URL setzen oder nur an localhost binden.")
_auth_kwargs: dict = {}
_auth_provider = None
if PUBLIC_URL:
    from mcp.server.auth.settings import (
        AuthSettings,
        ClientRegistrationOptions,
        RevocationOptions,
    )

    from brag.remote_auth import PASSWORD_FILE, BragAuthProvider

    if not PASSWORD_FILE.exists():
        raise SystemExit(
            "brag-remote: ABBRUCH — BRAG_REMOTE_PUBLIC_URL gesetzt, aber kein "
            "Fernzugriffs-Passwort. Erst anlegen: python3 -m brag.remote_auth generate")
    _auth_provider = BragAuthProvider(issuer_url=PUBLIC_URL)
    _auth_kwargs = {
        "auth_server_provider": _auth_provider,
        "auth": AuthSettings(
            issuer_url=PUBLIC_URL,
            resource_server_url=f"{PUBLIC_URL}/mcp",
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=["read"], default_scopes=["read"]),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=["read"],
        ),
    }

mcp = FastMCP(
    "brag-remote (vault read+write, no delete)",
    host=HOST,
    port=PORT,
    transport_security=_transport_security,
    **_auth_kwargs,
)

if _auth_provider is not None:
    from brag.remote_auth import install_login_routes
    install_login_routes(mcp, _auth_provider)

# --- Nur die freigegebenen Tools registrieren (Funktionen 1:1 aus mcp_server) ------
_registered: list[str] = []
for _name in EXPOSED:
    _fn = getattr(_srv, _name, None)
    if _fn is None:
        print(f"brag-remote: WARN — Tool '{_name}' fehlt in mcp_server", file=sys.stderr)
        continue
    mcp.add_tool(_fn)  # Name/Beschreibung/Schema aus der Funktion abgeleitet
    _registered.append(_name)


def _declared_tools(src: str) -> set[str]:
    """Alle mit @mcp.tool() dekorierten Funktionen in `src` — ueber den Syntaxbaum.

    Vorher stand hier ein regulaerer Ausdruck, der den Dekorator DIREKT ueber `def`
    verlangte. Sobald zwischen beiden ein weiterer Dekorator steht (@with_topic_hint,
    @with_passage_layout_note), war das Tool fuer die Pruefung unsichtbar: gemessen
    25 statt 27, ausgerechnet `search` und `save_passage`. Die harte Absicherung
    unten greift weiter, es ging also nichts nach draussen — verloren war die
    Drift-Warnung, und zwar genau fuer die Tools mit der groessten Reichweite. Der
    Syntaxbaum kennt alle Dekoratoren einer Funktion, also kann sich keines mehr
    hinter einem anderen verstecken.
    """
    namen: set[str] = set()
    for knoten in ast.walk(ast.parse(src)):
        if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dek in knoten.decorator_list:
            ziel = dek.func if isinstance(dek, ast.Call) else dek
            if getattr(ziel, "attr", None) == "tool" or getattr(ziel, "id", None) == "tool":
                namen.add(knoten.name)
                break
    return namen


def _audit() -> None:
    """Sicherheits-Selbstpruefung: warnt, falls BRAG neue Tools hat, die weder als
    'lesen' noch als 'schreiben' klassifiziert sind (Default = NICHT exponiert)."""
    try:
        src = open(_srv.__file__, encoding="utf-8").read()
        defined = _declared_tools(src)
    except (OSError, SyntaxError):
        return
    unclassified = defined - set(EXPOSED) - set(WITHHELD)
    if unclassified:
        print(f"brag-remote: WARN — nicht klassifizierte Tools (NICHT exponiert): "
              f"{sorted(unclassified)}", file=sys.stderr)
    leaked = set(_registered) & set(WITHHELD)
    if leaked:  # darf nie passieren — harte Absicherung
        raise SystemExit(f"brag-remote: ABBRUCH — gesperrtes Tool exponiert: {sorted(leaked)}")


if __name__ == "__main__":
    _audit()
    print(f"brag-remote: {len(_registered)} Tools (lesen + Vault-schreiben, ohne "
          f"loeschen) auf http://{HOST}:{PORT}/mcp "
          f"({'oeffentlich erlaubt: ' + ','.join(_extra) if _extra else 'nur localhost'}; "
          f"{'OAuth AKTIV — Issuer ' + PUBLIC_URL if PUBLIC_URL else 'OHNE Auth (lokal)'})",
          file=sys.stderr)
    mcp.run(transport="streamable-http")
