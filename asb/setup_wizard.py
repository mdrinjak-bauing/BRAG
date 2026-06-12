"""Interactive setup wizard. Runs INSIDE the container via setup.command /
setup.bat, which mount the project dir at /workspace and the Claude Desktop
config dir at /claude-config.

Writes: .env, the vault skeleton, and the Claude Desktop MCP entry.
Audience is non-developers — every failure needs a plain-language message.
"""

import json
import shutil
import sys
from pathlib import Path

WORKSPACE = Path("/workspace")
CLAUDE_CONFIG_DIR = Path("/claude-config")
VAULT_TEMPLATE = Path(__file__).parent.parent / "vault_template"

PROFILE_INFO = """
Choose your backend profile:

  [1] Cloud (RECOMMENDED) — uses the free Google Gemini API.
      Works on any computer. Documents are sent to Google for processing.
      Needs: a free API key from https://aistudio.google.com/apikey

  [2] Hybrid — local AI via LM Studio (good Mac with Apple Silicon needed).
      Documents never leave your computer.
      Needs: LM Studio installed and running on your computer.

  [3] Local — local AI via Ollama (Mac/Windows/Linux, slower).
      Documents never leave your computer.
      Needs: Ollama installed and running on your computer.
"""

PROFILE_KEYS = {"1": "cloud", "2": "hybrid", "3": "local"}


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def write_env(profile: str, api_key: str, language: str) -> None:
    env_path = WORKSPACE / ".env"
    lines = [
        "# Academic Second Brain — written by the setup wizard.",
        "# Re-run setup (setup.command / setup.bat) to change these safely.",
        f"PROFILE={profile}",
        f"GEMINI_API_KEY={api_key}",
        f"VAULT_LANGUAGE={language}",
        f"ANSWER_LANGUAGE={'German' if language == 'german' else 'English'}",
        "VAULT_PATH=./vault",
    ]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {env_path.name}")


def create_vault() -> None:
    vault = WORKSPACE / "vault"
    if vault.exists():
        print("  vault/ already exists — keeping it untouched")
        return
    shutil.copytree(VAULT_TEMPLATE, vault)
    print("  created vault/ (sources, notes, passages, wiki)")


def write_claude_config() -> bool:
    if not CLAUDE_CONFIG_DIR.exists():
        return False
    config_path = CLAUDE_CONFIG_DIR / "claude_desktop_config.json"
    try:
        existing = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except json.JSONDecodeError:
        backup = config_path.with_suffix(".json.backup")
        shutil.copy(config_path, backup)
        print(f"  your Claude config was not valid JSON — backed it up to {backup.name}")
        existing = {}
    servers = existing.setdefault("mcpServers", {})
    servers["academic-second-brain"] = {
        "command": "docker",
        "args": ["exec", "-i", "asb-app", "python", "-m", "asb.mcp_server"],
    }
    config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print("  added 'academic-second-brain' to Claude Desktop")
    return True


def main():
    print("\n=== Academic Second Brain — Setup ===\n")

    print(PROFILE_INFO)
    choice = ""
    while choice not in PROFILE_KEYS:
        choice = ask("Profile (1/2/3)", "1")
    profile = PROFILE_KEYS[choice]

    api_key = ""
    if profile == "cloud":
        print("\nGet your free API key at: https://aistudio.google.com/apikey")
        api_key = ask("Paste your Gemini API key")
        if not api_key:
            print("\nNo API key — setup cannot continue with the Cloud profile.")
            print("Get a key (it is free), then run setup again.")
            sys.exit(1)

    print("\nWhich language are most of your documents in?")
    print("(affects keyword search quality and the language of generated notes)")
    language = ask("Language (english/german/french/spanish/...)", "english").lower()

    print("\nSetting things up:")
    write_env(profile, api_key, language)
    create_vault()
    if not write_claude_config():
        print("\n  NOTE: Claude Desktop config folder was not found.")
        print("  Add this entry manually to claude_desktop_config.json:")
        print(json.dumps({
            "academic-second-brain": {
                "command": "docker",
                "args": ["exec", "-i", "asb-app", "python", "-m", "asb.mcp_server"],
            }
        }, indent=2))

    print("\n=== Setup complete ===")
    print("Next steps:")
    print("  1. The app starts automatically after this wizard.")
    print("  2. QUIT Claude Desktop completely and reopen it.")
    print("  3. Drop a PDF into the vault/sources/ folder.")
    print("  4. Ask Claude: 'What documents are in my knowledge base?'")
    if profile in ("hybrid", "local"):
        app = "LM Studio" if profile == "hybrid" else "Ollama"
        print(f"\n  Remember: {app} must be running on your computer "
              f"whenever documents are being indexed.")


if __name__ == "__main__":
    main()
