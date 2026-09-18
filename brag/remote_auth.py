"""BRAG remote auth — Ein-Nutzer-OAuth-2.1-Autorisierung fuer den Fernzugriff.

Implementiert das ``OAuthAuthorizationServerProvider``-Protokoll des MCP-SDK fuer
GENAU EINEN Nutzer (Passwort-Login). Gedacht fuer ``mcp_server_remote`` hinter
einem HTTPS-Tunnel (z. B. Tailscale Funnel): Claude registriert sich selbst
(Dynamic Client Registration), der Browser zeigt eine Login-Seite, danach laufen
kurzlebige Access-Tokens (1 h) + rotierende Refresh-Tokens (90 Tage).

Sicherheits-Eckpunkte:
- Passwort nur als scrypt-Hash auf der Platte (``password.json``, chmod 600).
- Tokens werden NUR als SHA-256-Hash persistiert — ein geleaktes State-File
  ergibt keine verwendbaren Tokens.
- PKCE (S256) prueft das SDK im Token-Handler; Authorization-Codes sind
  einmal verwendbar und verfallen nach 5 Minuten.
- Login-Rate-Limit: nach 5 Fehlversuchen 15 Minuten Sperre (global — es gibt
  nur einen legitimen Nutzer).

CLI (einmalige Einrichtung):
    python3 -m brag.remote_auth generate   # starkes Passwort erzeugen + speichern
    python3 -m brag.remote_auth set        # eigenes Passwort von stdin setzen
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import os
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

STATE_DIR = Path(os.environ.get(
    "BRAG_REMOTE_STATE_DIR",
    Path.home() / "Library" / "Application Support" / "brag-remote"))
PASSWORD_FILE = STATE_DIR / "password.json"
STATE_FILE = STATE_DIR / "auth_state.json"

SCOPE = "read"
ACCESS_TTL = 3600                 # 1 h
REFRESH_TTL = 90 * 24 * 3600      # 90 Tage, rotierend
CODE_TTL = 300                    # 5 min
TXN_TTL = 600                     # Login-Fenster 10 min
MAX_FAILS = 5
LOCKOUT = 900                     # 15 min
# Nur diese Redirect-Hosts duerfen sich registrieren/autorisieren (blockt Phishing-
# Clients mit fremder redirect_uri trotz offener Selbstregistrierung). claude.ai ist
# der reale Host der App; localhost fuer lokale Tests. Ueber Env erweiterbar.
ALLOWED_REDIRECT_HOSTS = {h.strip().lower() for h in os.environ.get(
    "BRAG_REMOTE_REDIRECT_HOSTS",
    "claude.ai,claude.com,localhost,127.0.0.1").split(",") if h.strip()}
MAX_CLIENTS = int(os.environ.get("BRAG_REMOTE_MAX_CLIENTS", "20"))   # DCR-Deckel gegen Spam
MAX_TXNS = 256                     # In-Memory-Deckel fuer offene Login-Transaktionen


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _write_private(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


# --------------------------------------------------------------------------- #
#  Passwort (scrypt)                                                          #
# --------------------------------------------------------------------------- #

def set_password(password: str) -> None:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    _write_private(PASSWORD_FILE, {"salt": salt.hex(), "hash": h.hex()})


def verify_password(password: str) -> bool:
    try:
        d = json.loads(PASSWORD_FILE.read_text(encoding="utf-8"))
        h = hashlib.scrypt(password.encode(), salt=bytes.fromhex(d["salt"]), n=2**14, r=8, p=1)
        return secrets.compare_digest(h.hex(), d["hash"])
    except (OSError, KeyError, ValueError):
        return False


# --------------------------------------------------------------------------- #
#  Provider                                                                   #
# --------------------------------------------------------------------------- #

class BragAuthProvider(
        OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    """Ein-Nutzer-Authorization-Server: Clients + Token-Hashes in STATE_FILE,
    Authorization-Codes/Login-Transaktionen nur im Speicher."""

    def __init__(self, issuer_url: str):
        self.issuer = issuer_url.rstrip("/")
        self._codes: dict[str, AuthorizationCode] = {}
        self._txns: dict[str, dict] = {}          # Login-Transaktionen
        self._fails: list[float] = []             # Zeitstempel fehlgeschlagener Logins
        self._state = self._load()

    # ---- Persistenz -------------------------------------------------------
    def _load(self) -> dict:
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"clients": {}, "access": {}, "refresh": {}}

    def _save(self) -> None:
        now = time.time()
        for kind in ("access", "refresh"):   # Abgelaufenes beim Speichern ausfegen
            self._state[kind] = {k: v for k, v in self._state[kind].items()
                                 if v.get("expires_at") and v["expires_at"] > now}
        _write_private(STATE_FILE, self._state)

    # ---- Client-Registrierung (RFC 7591, von Claude automatisch genutzt) ---
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        d = self._state["clients"].get(client_id)
        return OAuthClientInformationFull.model_validate(d) if d else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        # #5b: Host-Allowlist schon bei der Registrierung. authorize() prueft sie zwar
        # ohnehin (ein fremder Client bekommt nie einen Code) — aber ein abgewiesener
        # Client wuerde sonst trotzdem einen Slot im FIFO-Deckel MAX_CLIENTS belegen
        # und damit den echten Claude-Client aus dem Zustand verdraengen.
        # redirect_uris ist `list | None` typisiert — None passiert die Validierung.
        if not client_info.redirect_uris:
            raise RegistrationError(
                "invalid_redirect_uri",
                "redirect_uris fehlt — ohne Redirect-Ziel ist kein Code-Flow moeglich")
        for uri in client_info.redirect_uris:
            host = (urlparse(str(uri)).hostname or "").lower()
            if host not in ALLOWED_REDIRECT_HOSTS:
                raise RegistrationError(
                    "invalid_redirect_uri",
                    f"redirect_uri host '{host}' ist nicht zugelassen")
        clients = self._state["clients"]
        clients[client_info.client_id] = client_info.model_dump(mode="json")
        if len(clients) > MAX_CLIENTS:                 # #1: FIFO-Deckel gegen DCR-Spam-DoS
            for old in list(clients)[:len(clients) - MAX_CLIENTS]:
                clients.pop(old, None)
        self._save()

    # ---- Authorize: auf die Login-Seite umleiten ---------------------------
    async def authorize(self, client: OAuthClientInformationFull,
                        params: AuthorizationParams) -> str:
        # #5: Redirect-Ziel muss auf der Host-Allowlist stehen — sonst kein Login-Fenster,
        # kein Code. Blockt Phishing-Clients mit attacker.tld-redirect (offene DCR bleibt,
        # aber der Code kann nur zu claude.ai zurueckfliessen).
        host = (urlparse(str(params.redirect_uri)).hostname or "").lower()
        if host not in ALLOWED_REDIRECT_HOSTS:
            raise AuthorizeError("access_denied",
                                 f"redirect_uri host '{host}' ist nicht zugelassen")
        now = time.time()
        self._txns = {k: v for k, v in self._txns.items() if v["expires_at"] > now}  # #2: prunen
        if len(self._txns) >= MAX_TXNS:
            self._txns.pop(min(self._txns, key=lambda k: self._txns[k]["expires_at"]), None)
        txn = secrets.token_urlsafe(24)
        self._txns[txn] = {"client_id": client.client_id, "params": params,
                           "client_name": client.client_name or "Claude",
                           "expires_at": now + TXN_TTL}
        return f"{self.issuer}/login?txn={txn}"

    # ---- Codes -------------------------------------------------------------
    async def load_authorization_code(self, client: OAuthClientInformationFull,
                                      authorization_code: str) -> AuthorizationCode | None:
        code = self._codes.get(authorization_code)
        if not code or code.client_id != client.client_id or code.expires_at < time.time():
            return None
        return code

    async def exchange_authorization_code(self, client: OAuthClientInformationFull,
                                          authorization_code: AuthorizationCode) -> OAuthToken:
        if self._codes.pop(authorization_code.code, None) is None:   # Einmal-Verwendung
            raise TokenError("invalid_grant", "authorization code already used")
        return self._issue_tokens(client.client_id, authorization_code.scopes)

    # ---- Refresh (mit Rotation) --------------------------------------------
    async def load_refresh_token(self, client: OAuthClientInformationFull,
                                 refresh_token: str) -> RefreshToken | None:
        d = self._state["refresh"].get(_hash(refresh_token))
        if not d or d["client_id"] != client.client_id or d["expires_at"] < time.time():
            return None
        return RefreshToken(token=refresh_token, client_id=d["client_id"],
                            scopes=d["scopes"], expires_at=int(d["expires_at"]))

    async def exchange_refresh_token(self, client: OAuthClientInformationFull,
                                     refresh_token: RefreshToken,
                                     scopes: list[str]) -> OAuthToken:
        self._state["refresh"].pop(_hash(refresh_token.token), None)   # Rotation
        return self._issue_tokens(client.client_id, scopes or refresh_token.scopes)

    # ---- Access ------------------------------------------------------------
    async def load_access_token(self, token: str) -> AccessToken | None:
        d = self._state["access"].get(_hash(token))
        if not d or d["expires_at"] < time.time():
            return None
        return AccessToken(token=token, client_id=d["client_id"],
                           scopes=d["scopes"], expires_at=int(d["expires_at"]))

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        h = _hash(token.token)
        self._state["access"].pop(h, None)
        self._state["refresh"].pop(h, None)
        self._save()

    # ---- intern ------------------------------------------------------------
    def _issue_tokens(self, client_id: str, scopes: list[str]) -> OAuthToken:
        scopes = scopes or [SCOPE]
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = time.time()
        self._state["access"][_hash(access)] = {
            "client_id": client_id, "scopes": scopes, "expires_at": now + ACCESS_TTL}
        self._state["refresh"][_hash(refresh)] = {
            "client_id": client_id, "scopes": scopes, "expires_at": now + REFRESH_TTL}
        self._save()
        return OAuthToken(access_token=access, expires_in=ACCESS_TTL,
                          scope=" ".join(scopes), refresh_token=refresh)

    # ---- Login-Seite (wird als custom_route am FastMCP registriert) --------
    def _recent_fails(self) -> int:
        cutoff = time.time() - LOCKOUT
        self._fails = [t for t in self._fails if t > cutoff]
        return len(self._fails)

    def _login_page(self, txn: str, client_name: str, target: str = "",
                    error: str = "") -> HTMLResponse:
        err = f"<p style='color:#c0392b'>{html.escape(error)}</p>" if error else ""
        tgt = (f"<p style='color:#555;font-size:.9em'>Rückleitung an: "
               f"<code>{html.escape(target)}</code></p>") if target else ""
        return HTMLResponse(f"""<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BRAG — Anmeldung</title>
<body style="font-family:system-ui;max-width:420px;margin:8vh auto;padding:0 1.5em">
<h2>🔐 BRAG-Fernzugriff</h2>
<p><b>{html.escape(client_name)}</b> möchte auf deinen BRAG-Wissensspeicher
zugreifen — Korpus und Notizen lesen, Notizen schreiben, nichts löschen.</p>{tgt}{err}
<form method="post" action="login">
  <input type="hidden" name="txn" value="{html.escape(txn)}">
  <input type="password" name="password" placeholder="Passwort" autofocus required
         style="width:100%;padding:.7em;font-size:1.1em;box-sizing:border-box">
  <button type="submit" style="width:100%;padding:.7em;margin-top:.8em;font-size:1.1em">
    Zugriff erlauben</button>
</form></body>""")

    async def handle_login_get(self, request: Request):
        txn = request.query_params.get("txn", "")
        t = self._txns.get(txn)
        if not t or t["expires_at"] < time.time():
            return HTMLResponse("<p>Anmelde-Link abgelaufen — bitte in der App neu verbinden.</p>",
                                status_code=400)
        return self._login_page(txn, t["client_name"],
                                (urlparse(str(t["params"].redirect_uri)).hostname or ""))

    async def handle_login_post(self, request: Request):
        form = await request.form()
        txn, password = str(form.get("txn", "")), str(form.get("password", ""))
        t = self._txns.get(txn)
        if not t or t["expires_at"] < time.time():
            return HTMLResponse("<p>Anmelde-Link abgelaufen — bitte in der App neu verbinden.</p>",
                                status_code=400)
        target = urlparse(str(t["params"].redirect_uri)).hostname or ""
        # #4: progressive Verzoegerung statt hartem Lockout — bremst Rateraten, sperrt
        # aber den legitimen Nutzer NIE dauerhaft aus (jeder Unauth-Request konnte vorher
        # einen globalen 429 ausloesen). Async-Sleep blockiert den Event-Loop nicht.
        recent = self._recent_fails()
        if recent >= MAX_FAILS:
            await asyncio.sleep(min(1.0 + 0.5 * recent, 8.0))
        if not verify_password(password):
            self._fails.append(time.time())
            return self._login_page(txn, t["client_name"], target, "Falsches Passwort.")
        self._fails.clear()
        self._txns.pop(txn, None)                      # Transaktion ist einmalig
        now = time.time()
        # #2: Codes prunen
        self._codes = {k: v for k, v in self._codes.items() if v.expires_at > now}
        params: AuthorizationParams = t["params"]
        code = secrets.token_urlsafe(32)
        self._codes[code] = AuthorizationCode(
            code=code, scopes=params.scopes or [SCOPE], expires_at=time.time() + CODE_TTL,
            client_id=t["client_id"], code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource)
        return RedirectResponse(
            construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state),
            status_code=302)


def install_login_routes(mcp, provider: BragAuthProvider) -> None:
    """Registriert GET/POST /login am FastMCP-App (ausserhalb des Bearer-Schutzes)."""
    mcp.custom_route("/login", methods=["GET"])(provider.handle_login_get)
    mcp.custom_route("/login", methods=["POST"])(provider.handle_login_post)


# --------------------------------------------------------------------------- #
#  CLI: Passwort setzen                                                        #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "generate":
        pw = secrets.token_urlsafe(15)
        set_password(pw)
        print(f"Neues Fernzugriffs-Passwort (einmalige Anzeige, sicher verwahren):\n\n  {pw}\n")
        print(f"Hash gespeichert in {PASSWORD_FILE} (chmod 600).")
    elif cmd == "set":
        pw = sys.stdin.readline().strip()
        if len(pw) < 12:
            sys.exit("Abbruch: mindestens 12 Zeichen.")
        set_password(pw)
        print(f"Passwort gesetzt ({PASSWORD_FILE}).")
    else:
        sys.exit("Nutzung: python3 -m brag.remote_auth generate | set")
