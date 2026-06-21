"""Shared setup logic used by both the browser wizard (setup_web routes in
http_bridge) and the terminal fallback (setup_wizard)."""

import json
import os
import shutil
from pathlib import Path

from brag.profiles import PROFILES

WORKSPACE = Path("/workspace")
CLAUDE_CONFIG_DIR = Path("/claude-config")
VAULT_TEMPLATE = Path(__file__).parent.parent / "vault_template"
SETUP_MARKER = WORKSPACE / ".setup_complete"

MCP_ENTRY = {
    "command": "docker",
    "args": ["exec", "-i", "brag-app", "python", "-m", "brag.mcp_server"],
}

# The key under which the DEFAULT connector is registered in
# claude_desktop_config.json — the name Claude Desktop shows the user. Older
# installs used a longer legacy name; setup migrates them by removing it.
MCP_KEY = "brag"
LEGACY_MCP_KEYS = ("academic-rag-and-second-brain",)


def mcp_key_for(slug) -> str:
    """Connector key shown in Claude/LM Studio: the plain 'brag' for the default
    (single) project, 'brag-<slug>' for each additional project."""
    return MCP_KEY if slug in (None, "", "default") else f"{MCP_KEY}-{slug}"


def entry_for_slug(slug) -> dict:
    """MCP entry for a project. The DEFAULT keeps the battle-tested single-project
    server (brag.mcp_server, no project env) so existing installs are unchanged;
    each ADDITIONAL project runs the thin client (brag.mcp_client) scoped by
    -e BRAG_PROJECT, so many open project connectors share ONE model set."""
    args = ["exec", "-i"]
    module = "brag.mcp_server"
    if slug not in (None, "", "default"):
        args += ["-e", f"BRAG_PROJECT={slug}"]
        module = "brag.mcp_client"
    args += ["brag-app", "python", "-m", module]
    return {"command": "docker", "args": args}


def _is_brag_key(key: str) -> bool:
    return key == MCP_KEY or key.startswith(f"{MCP_KEY}-")


def connectors_for_registry() -> dict:
    """{connector key: MCP entry} that Claude/LM Studio should contain — one per
    registered project, or just the default 'brag' when the registry is empty
    (the single-project install)."""
    from brag import registry
    projects = registry.projects()
    if not projects:
        return {MCP_KEY: entry_for_slug(None)}
    return {mcp_key_for(p["slug"]): entry_for_slug(p["slug"]) for p in projects}


def _env_safe(value: str) -> str:
    """Strip newlines/carriage returns so a wizard-supplied value (e.g. a custom
    vault path) cannot inject extra lines into the generated .env file."""
    return "".join(ch for ch in str(value) if ch not in "\r\n").strip()


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
              vault_path: str = "", llm_model: str = "",
              rerank_profile: str = "eco", vision_enabled: bool = True) -> None:
    # vault_path defaults to "" (NOT a folder) so an empty wizard field falls
    # through to the existing VAULT_PATH in .env — the absolute path the host
    # launcher's folder picker / relocation wrote (e.g. <RAG folder>\WissensWIKI).
    # Coercing it to a relative default here would silently repoint the vault.
    existing = read_existing_env()
    # Sanitize every value that gets interpolated into a KEY=value line so a
    # newline in (untrusted) wizard input cannot inject extra .env entries.
    profile = _env_safe(profile)
    language = _env_safe(language)
    vault_path = _env_safe(vault_path)
    api_key = _env_safe(api_key)
    llm_model = _env_safe(llm_model)
    rerank_profile = _env_safe(rerank_profile) or "eco"
    # Map the document language to the answer/notes language. Falls back to
    # English for anything outside the wizard's offered set, so a non-German,
    # non-English corpus no longer silently gets English context embedded.
    answer_lang = {
        "english": "English", "german": "German", "french": "French",
        "spanish": "Spanish", "italian": "Italian", "dutch": "Dutch",
        "portuguese": "Portuguese",
    }.get(language, "English")
    lines = [
        "# BRAG — Building Retrieval-Augmented Generation — written by the setup wizard.",
        "# Re-run setup to change these safely. Full reference: .env.example",
        f"PROFILE={profile}",
        f"VAULT_LANGUAGE={language}",
        f"ANSWER_LANGUAGE={answer_lang}",
        f"VAULT_PATH={vault_path or existing.get('VAULT_PATH') or './WissensWIKI'}",
        # Search-quality vs. CPU cost (off/eco/balanced/full) and whether figures
        # are sent to a cloud provider for description. Written explicitly so a
        # later re-run always reflects the wizard's choice, even at the default.
        f"RERANK_PROFILE={rerank_profile}",
        f"VISION_ENABLED={'true' if vision_enabled else 'false'}",
    ]
    # Write the API key under the active provider's env var (cloud profiles only).
    key_env = PROFILES.get(profile, {}).get("key_env")
    if key_env and api_key:
        lines.append(f"{key_env}={api_key}")
    if llm_model:
        lines.append(f"LLM_MODEL={llm_model}")
    # Preserve keys the wizard itself does NOT manage but the user may have set by
    # hand — a re-run must never silently drop them: the Claude config dir, a custom
    # bridge port / public URL, and the advanced embedding / retrieval .env dials.
    preserved = [
        "CLAUDE_CONFIG_DIR", "BRIDGE_HOST_PORT", "BRIDGE_PUBLIC_URL",
        "COMPOSE_PROJECT_NAME", "EMBEDDING_BACKEND",
        "EMBEDDING_MODEL", "EMBEDDING_DIM", "EMBEDDING_REVISION",
        "COLLECTION_NAME", "RERANK_PREFETCH", "RERANK_FUSION_LIMIT",
        "RERANK_BATCH_SIZE", "DEFAULT_TOP_K", "MAX_CHUNKS_PER_SOURCE",
    ]
    # LLM_MODEL + LLM_BASE_URL are provider-specific: carry them over ONLY when the
    # profile is UNCHANGED. Switching providers (e.g. local hybrid -> gemini) must
    # NOT keep the old model name / base URL, or the new provider is handed an
    # invalid model and every contextualization call fails.
    if existing.get("PROFILE") == profile:
        preserved.append("LLM_BASE_URL")
        if not llm_model:
            preserved.append("LLM_MODEL")
    for key in preserved:
        if existing.get(key):
            lines.append(f"{key}={existing[key]}")
    # Atomic write (temp + replace) so a crash mid-write can't truncate the
    # config, and 0600 because this file holds the API key.
    env_path = WORKSPACE / ".env"
    tmp = WORKSPACE / ".env.tmp"
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, env_path)
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass


def create_vault() -> bool:
    """Create the FALLBACK in-engine project root (./project) with its WissensWIKI
    workspace — used only when the user picked no project folder. Returns False if
    it already existed. The normal path mounts the user's project at /vault and
    never calls this. The project root is the corpus; only WissensWIKI is seeded."""
    project = WORKSPACE / "project"
    if (project / "WissensWIKI").exists():
        return False
    shutil.copytree(VAULT_TEMPLATE, project / "WissensWIKI")
    return True


def seed_vault_if_empty(vault: Path) -> None:
    """Seed the project's WissensWIKI workspace from the template without
    overwriting anything that exists. Called at app startup. The project root holds
    the user's documents (the searchable corpus); only the WissensWIKI workspace
    (Passagen/, Notizen/, guides) is seeded — never the root itself."""
    if not VAULT_TEMPLATE.exists():
        return
    wiki = vault / "WissensWIKI"
    wiki.mkdir(parents=True, exist_ok=True)
    for item in VAULT_TEMPLATE.iterdir():
        target = wiki / item.name
        if target.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def write_claude_config() -> tuple[bool, str]:
    """Add the MCP entry to Claude Desktop's config — safely.

    - Never discards a recoverable config: on invalid JSON we back it up and
      refuse, rather than overwriting and losing the user's other MCP servers.
    - Always backs up a valid config before changing it.
    - Writes atomically (temp file + os.replace) so a crash mid-write cannot
      corrupt the shared Claude config.
    """
    import os

    # The compose mount only sets a real config dir when the launcher exported
    # CLAUDE_CONFIG_DIR; otherwise it mounts a throwaway sentinel. Be explicit
    # about WHICH precondition failed so the wizard/log can point at the cause
    # instead of a generic "do it manually".
    if os.environ.get("CLAUDE_CONFIG_MOUNTED") != "1":
        return False, (
            "Claude Desktop config folder was not mounted into setup "
            "(CLAUDE_CONFIG_MOUNTED is not 1) — most likely the launcher could "
            "not find your Claude Desktop config folder. Add the MCP entry "
            "manually (see below)."
        )
    if not CLAUDE_CONFIG_DIR.exists():
        return False, (
            "Claude config folder is not mounted inside the container "
            "(/claude-config missing) — add the MCP entry manually (see below)."
        )

    config_path = CLAUDE_CONFIG_DIR / "claude_desktop_config.json"

    def _backup(path) -> None:
        # copyfile, NOT shutil.copy: shutil.copy ALSO copies the file mode
        # (chmod), which is "Operation not permitted" on a Windows Docker bind
        # mount and would crash the whole setup with a PermissionError (the
        # browser then shows "Failed to fetch" and setup never completes). The
        # backup is best-effort — it must never abort the wizard.
        try:
            shutil.copyfile(path, path.with_suffix(".json.backup"))
        except OSError:
            pass

    # NOTHING in here may raise: a crash here returns "Failed to fetch" to the
    # browser and the setup never completes. On Windows the RELIABLE writer is
    # the host launcher (tools/merge_claude_config.ps1, called by setup.bat);
    # this container write is best-effort and works directly on macOS/Linux.
    try:
        raw = ""
        if config_path.exists():
            try:
                # utf-8-sig tolerates a BOM that some editors add.
                raw = config_path.read_text(encoding="utf-8-sig")
                if raw.strip():
                    json.loads(raw)  # validate only — refuse to clobber bad JSON
            except json.JSONDecodeError:
                _backup(config_path)
                return False, ("Existing Claude config is not valid JSON — backed it "
                               "up; add the MCP entry manually (see below).")
            _backup(config_path)
        # Single source of truth for the connector merge (drop removed brag-*,
        # keep the user's other servers, migrate the legacy key, one entry per
        # project). Direct write (no temp+os.replace): the atomic-rename dance does
        # not reliably reach the host on a Windows bind mount, and chmod is
        # forbidden there; on Windows the host launcher writes the real entry after.
        from brag import claude_sync
        config_path.write_text(claude_sync.sync(raw), encoding="utf-8")
    except OSError as e:
        return False, (
            f"Could not write the Claude config from the container "
            f"({type(e).__name__}); the launcher will set it up, or add the MCP "
            "entry manually (see below)."
        )
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
        # Pass the key in the header (x-goog-api-key), not the URL query, so it
        # cannot leak into proxy/server logs — consistent with OpenAI/Anthropic.
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
            headers={"x-goog-api-key": api_key},
        )
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
