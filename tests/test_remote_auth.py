"""Tests fuer die Client-Selbstregistrierung (RFC 7591) in brag.remote_auth.

Der Fernzugang laesst offene Dynamic Client Registration zu, damit die
Claude-App sich ohne Vorab-Konfiguration anmelden kann. Ein Client mit
fremdem redirect_uri-Host bekommt zwar per Allowlist in authorize() nie
einen Code — er belegt aber einen Slot im FIFO-Deckel MAX_CLIENTS und kann
damit den echten Claude-Client aus dem Zustand verdraengen. register_client
muss solche Clients deshalb schon bei der Registrierung abweisen.
"""

import asyncio

import pytest
from mcp.server.auth.provider import RegistrationError
from mcp.shared.auth import OAuthClientInformationFull

from brag import remote_auth


def _provider(tmp_path, monkeypatch) -> remote_auth.BragAuthProvider:
    """Provider mit isoliertem Zustand — fasst die echte auth_state.json nie an."""
    monkeypatch.setattr(remote_auth, "STATE_DIR", tmp_path)
    monkeypatch.setattr(remote_auth, "STATE_FILE", tmp_path / "auth_state.json")
    monkeypatch.setattr(remote_auth, "PASSWORD_FILE", tmp_path / "password.json")
    return remote_auth.BragAuthProvider("https://beispiel.test")


def _client(client_id: str, *redirect_uris: str) -> OAuthClientInformationFull:
    return OAuthClientInformationFull(
        client_id=client_id,
        client_secret="geheim",
        redirect_uris=list(redirect_uris),
        grant_types=["authorization_code", "refresh_token"],
    )


def test_register_weist_fremden_redirect_host_ab(tmp_path, monkeypatch):
    provider = _provider(tmp_path, monkeypatch)

    with pytest.raises(RegistrationError) as exc:
        asyncio.run(provider.register_client(_client("fremd", "https://attacker.tld/cb")))

    assert exc.value.error == "invalid_redirect_uri"
    assert asyncio.run(provider.get_client("fremd")) is None


def test_register_weist_ab_wenn_nur_eine_von_mehreren_uris_fremd_ist(tmp_path, monkeypatch):
    provider = _provider(tmp_path, monkeypatch)

    with pytest.raises(RegistrationError):
        asyncio.run(provider.register_client(_client(
            "gemischt",
            "https://claude.ai/api/mcp/auth_callback",
            "https://attacker.tld/cb",
        )))

    assert asyncio.run(provider.get_client("gemischt")) is None


def test_register_nimmt_zugelassenen_redirect_host_an(tmp_path, monkeypatch):
    provider = _provider(tmp_path, monkeypatch)

    asyncio.run(provider.register_client(_client(
        "claude", "https://claude.ai/api/mcp/auth_callback")))

    gespeichert = asyncio.run(provider.get_client("claude"))
    assert gespeichert is not None
    assert str(gespeichert.redirect_uris[0]) == "https://claude.ai/api/mcp/auth_callback"


def test_register_weist_client_ohne_redirect_uris_ab(tmp_path, monkeypatch):
    """redirect_uris ist als `list | None` typisiert — None kommt durch die
    Pydantic-Validierung und darf die Host-Pruefung nicht umgehen (und erst
    recht keinen TypeError werfen). Ohne Redirect-Ziel ist der einzige
    unterstuetzte Grant (authorization_code) ohnehin nicht nutzbar."""
    provider = _provider(tmp_path, monkeypatch)
    client = _client("ohne", "https://claude.ai/api/mcp/auth_callback")
    object.__setattr__(client, "redirect_uris", None)

    with pytest.raises(RegistrationError) as exc:
        asyncio.run(provider.register_client(client))

    assert exc.value.error == "invalid_redirect_uri"
    assert asyncio.run(provider.get_client("ohne")) is None
