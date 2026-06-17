"""Shared setup logic used by both the browser wizard (setup_web routes in
http_bridge) and the terminal fallback (setup_wizard)."""

import json
import shutil
from pathlib import Path

from asb.profiles import PROFILES

WORKSPACE = Path("/workspace")
CLAUDE_CONFIG_DIR = Path("/claude-config")
VAULT_TEMPLATE = Path(__file__).parent.parent / "vault_template"
SETUP_MARKER = WORKSPACE / ".setup_complete"

MCP_ENTRY = {
    "command": "docker",
    "args": ["exec", "-i", "asb-app", "python", "-m", "asb.mcp_server"],
}


def read_existing_env() -> dict:
    env_path = WORKSPACE / ".env"
    values = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    return values


def write_env(profile: str, api_key: str, language: str,
              vault_path: str = "./vault", llm_model: str = "") -> None:
    existing = read_existing_env()
    answer_lang = "German" if language == "german" else "English"
    lines = [
        "# Academic RAG and Second Brain — written by the setup wizard.",
        "# Re-run setup to change these safely. Full reference: .env.example",
        f"PROFILE={profile}",
        f"VAULT_LANGUAGE={language}",
        f"ANSWER_LANGUAGE={answer_lang}",
        f"VAULT_PATH={vault_path or './vault'}",
    ]
    # Write the API key under the active provider's env var (cloud profiles only).
    key_env = PROFILES.get(profile, {}).get("key_env")
    if key_env and api_key:
        lines.append(f"{key_env}={api_key}")
    if llm_model:
        lines.append(f"LLM_MODEL={llm_model}")
    # Preserve the host's Claude config dir (set by setup.command / setup.bat)
    if existing.get("CLAUDE_CONFIG_DIR"):
        lines.append(f"CLAUDE_CONFIG_DIR={existing['CLAUDE_CONFIG_DIR']}")
    (WORKSPACE / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_vault() -> bool:
    """Copy the vault template to ./vault. Returns False if it already existed."""
    vault = WORKSPACE / "vault"
    if vault.exists():
        return False
    shutil.copytree(VAULT_TEMPLATE, vault)
    return True


def seed_vault_if_empty(vault: Path) -> None:
    """Seed a custom (possibly empty) vault folder with the template files
    without overwriting anything that exists. Called at app startup."""
    if not VAULT_TEMPLATE.exists():
        return
    vault.mkdir(parents=True, exist_ok=True)
    for item in VAULT_TEMPLATE.iterdir():
        target = vault / item.name
        if target.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def write_claude_config() -> tuple[bool, str]:
    """Add the MCP entry to Claude Desktop's config. Returns (ok, message)."""
    if not CLAUDE_CONFIG_DIR.exists():
        return False, "Claude config folder not mounted"
    config_path = CLAUDE_CONFIG_DIR / "claude_desktop_config.json"
    try:
        existing = (
            json.loads(config_path.read_text(encoding="utf-8"))
            if config_path.exists() else {}
        )
    except json.JSONDecodeError:
        backup = config_path.with_suffix(".json.backup")
        shutil.copy(config_path, backup)
        existing = {}
    existing.setdefault("mcpServers", {})["academic-rag-and-second-brain"] = MCP_ENTRY
    config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return True, "Claude Desktop configured"


def mark_setup_complete() -> None:
    """Signal the host-side setup script to restart the app with the new .env."""
    SETUP_MARKER.write_text("done\n", encoding="utf-8")


def validate_api_key(provider: str, api_key: str) -> tuple[bool, str]:
    """Live check of a cloud provider's API key (REST, no SDK overhead).
    provider: 'gemini' | 'openai' | 'anthropic'."""
    import urllib.error
    import urllib.request

    if not api_key or len(api_key) < 20:
        return False, "That doesn't look like a complete API key."

    if provider == "gemini":
        url = ("https://generativelanguage.googleapis.com/v1beta/models"
               f"?pageSize=1&key={api_key}")
        req = urllib.request.Request(url)
        rejected_hint = ("The key was rejected by Google. Copy it again from "
                         "https://aistudio.google.com/apikey")
    elif provider == "openai":
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        rejected_hint = ("The key was rejected by OpenAI. Copy it again from "
                         "https://platform.openai.com/api-keys")
    elif provider == "anthropic":
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        )
        rejected_hint = ("The key was rejected by Anthropic. Copy it again from "
                         "https://console.anthropic.com/")
    else:
        return False, f"Unknown provider: {provider}"

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                return True, "Key works!"
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 403):
            return False, rejected_hint
        return False, f"The provider answered with an error (HTTP {e.code}). Try again."
    except OSError:
        return False, ("Could not reach the provider — check your internet "
                       "connection and try again.")
    return False, "Unexpected response — please try again."


def validate_gemini_key(api_key: str) -> tuple[bool, str]:
    """Back-compat wrapper used by the terminal wizard."""
    return validate_api_key("gemini", api_key)
