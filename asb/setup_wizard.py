"""Terminal fallback for the setup (the primary path is the browser wizard
at http://localhost:8765/setup). Run via:
  docker compose run --rm -v "$PWD":/workspace \
    -v "<claude config dir>":/claude-config app python -m asb.setup_wizard
"""

import sys

from asb import setup_core

PROFILE_INFO = """
Choose your backend profile:

  [1] Cloud (RECOMMENDED) — free Google Gemini API, works on any computer.
      Document text is sent to Google for processing.
  [2] Hybrid — local AI via LM Studio (strong Apple Silicon Mac needed).
  [3] Local — local AI via Ollama (cross-platform, slower).
"""

PROFILE_KEYS = {"1": "cloud", "2": "hybrid", "3": "local"}


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def main():
    print("\n=== Academic RAG and Second Brain — Setup (terminal) ===")
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
            print("No API key — cannot continue with the Cloud profile.")
            sys.exit(1)
        ok, message = setup_core.validate_gemini_key(api_key)
        print(f"  {'OK:' if ok else 'WARNING:'} {message}")
        if not ok and ask("Continue anyway? (y/n)", "n").lower() != "y":
            sys.exit(1)

    language = ask("\nMain language of your documents "
                   "(english/german/french/...)", "english").lower()

    print("\nSetting things up:")
    setup_core.write_env(profile, api_key, language)
    print("  configuration saved")
    created = setup_core.create_vault()
    print("  vault/ created" if created else "  vault/ already exists — kept")
    claude_ok, claude_msg = setup_core.write_claude_config()
    print(f"  {claude_msg}")
    if not claude_ok:
        import json
        print("  Add this entry manually to claude_desktop_config.json:")
        print(json.dumps({"academic-rag-and-second-brain": setup_core.MCP_ENTRY}, indent=2))
    setup_core.mark_setup_complete()

    print("\n=== Setup complete ===")
    print("1. Quit Claude Desktop completely and reopen it.")
    print("2. Drop a PDF into vault/sources/.")
    print("3. Ask Claude: 'What documents are in my knowledge base?'")
    if profile in ("hybrid", "local"):
        app = "LM Studio" if profile == "hybrid" else "Ollama"
        print(f"\nRemember: {app} must be running whenever documents are indexed.")


if __name__ == "__main__":
    main()
