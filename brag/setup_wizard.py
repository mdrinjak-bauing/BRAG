"""Terminal fallback for the setup — an emergency backstop only. The primary,
recommended path is the browser wizard at http://localhost:8765/setup, started
by setup.command / setup.bat.

Run it against the one-shot `setup` service (it provides the project +
Claude-config mounts and SETUP_MODE; the persistent `app` service deliberately
does not):
  CLAUDE_CONFIG_DIR="<claude config dir>" \
    docker compose --profile setup run --rm setup python -m brag.setup_wizard

Note: this backstop uses the default performance options (reranker eco, vision
on); tune them in the browser wizard or directly in .env.
"""

import sys

from brag import setup_core

PROFILE_INFO = """
Choose your backend profile:

  [1] Gemini (RECOMMENDED) — Google Gemini cloud API (free tier), any computer.
  [2] OpenAI — ChatGPT cloud API (gpt-4o-mini).
  [3] Claude — Anthropic Claude Haiku.
  [4] Local — local LLM via LM Studio (free app, any computer).

The profile picks the TEXT AI only. Embeddings always run locally on your
computer in every profile, so you can switch provider later WITHOUT
re-indexing. Profiles 1-3 send document text to the chosen cloud provider for
that text work; 4 keeps everything local.
"""

PROFILE_KEYS = {"1": "gemini", "2": "openai", "3": "anthropic",
                "4": "hybrid"}
CLOUD_PROFILES = {"gemini", "openai", "anthropic"}


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def main():
    print("\n=== BRAG — Building Retrieval-Augmented Generation — Setup (terminal) ===")
    print(PROFILE_INFO)
    choice = ""
    while choice not in PROFILE_KEYS:
        choice = ask("Profile (1/2/3/4/5)", "1")
    profile = PROFILE_KEYS[choice]

    KEY_URLS = {
        "gemini": "https://aistudio.google.com/apikey",
        "openai": "https://platform.openai.com/api-keys",
        "anthropic": "https://console.anthropic.com/",
    }
    api_key = ""
    if profile in CLOUD_PROFILES:
        print(f"\nGet your API key at: {KEY_URLS[profile]}")
        api_key = ask(f"Paste your {profile} API key")
        if not api_key:
            print("No API key — cannot continue with a cloud profile.")
            sys.exit(1)
        ok, message = setup_core.validate_api_key(profile, api_key)
        print(f"  {'OK:' if ok else 'WARNING:'} {message}")
        if not ok and ask("Continue anyway? (y/n)", "n").lower() != "y":
            sys.exit(1)

    language = ask("\nMain language of your documents "
                   "(english/german/french/...)", "english").lower()

    print("\nSetting things up:")
    # Backstop: reranker/vision stay at their write_env defaults (eco / on);
    # the browser wizard exposes them, here we keep the safe defaults explicit.
    setup_core.write_env(profile, api_key, language,
                         rerank_profile="eco", vision_enabled=True)
    print("  configuration saved")
    created = setup_core.create_vault()
    print(f"  RAG-Verbindungsordner/ {'created' if created else 'already exists — kept'}")
    claude_ok, claude_msg = setup_core.write_claude_config()
    print(f"  {claude_msg}")
    if not claude_ok:
        import json
        print("  Add this entry manually to claude_desktop_config.json:")
        print(json.dumps({setup_core.MCP_KEY: setup_core.MCP_ENTRY}, indent=2))
    setup_core.mark_setup_complete()

    print("\n=== Setup complete ===")
    print("1. Quit Claude Desktop completely and reopen it.")
    print("2. Drop a PDF into RAG-Verbindungsordner/sources/.")
    print("3. Ask Claude: 'What documents are in my knowledge base?'")
    if profile == "hybrid":
        print("\nRemember: LM Studio must be running whenever documents are indexed.")


if __name__ == "__main__":
    main()
