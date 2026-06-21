# CLAUDE.md — working on BRAG

Onboarding for any AI/contributor session. Read this first; it links to the deeper
docs. (Not to be confused with `vault_template/CLAUDE.md`, which is the END-USER
knowledge-vault template that gets seeded into a project's `WissensWIKI/`.)

## What BRAG is
BRAG ("Building Retrieval-Augmented Generation") is a **local-first RAG tool for
non-technical researchers**. The user drops documents into a folder; BRAG extracts
them (Docling), indexes into Qdrant (hybrid dense + BM25 → RRF → bge-reranker-v2-m3
→ contextual retrieval via an LLM), and exposes search + a notebook over **MCP** to
**Claude Desktop** and **LM Studio**. Everything runs in **Docker**; an HTTP bridge
(localhost:8765) serves the browser setup wizard + PDF deep-links; a polling watcher
auto-ingests new/changed files.

## Non-negotiable goals (the "why")
- **Plug-and-play for non-developers.** No file editing — a double-clicked
  `setup.bat`/`setup.command` + a browser wizard does everything. Every error a user
  can hit needs a plain-language "what to do next". EN **and** DE docs stay in sync.
- **Local-first & private.** Local profiles must mean "nothing leaves your machine".
- **Lean & maintainable.** One app container + Qdrant; no extra services / no web UI
  (see CONTRIBUTING.md "Scope"). Ships via **Docker** — don't re-pitch uvx/pip.
- **No security holes.** The long-running app mounts ONLY the project folder + the
  model cache — never the engine dir (which holds `.env`/scripts) or the Claude config.
- **Windows + macOS** are both first-class.

## Architecture
Full detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). In short:
- `brag/` — the app. `ingest/` (Docling extract → chunk → embed → contextual notes),
  `storage.py` (Qdrant), search + rerank, `mcp_server.py` (default project) +
  `mcp_client.py` (thin, model-free client for extra projects), `http_bridge.py`
  (bridge + wizard API + shared model service), `watcher.py` (PollingObserver),
  `config.py` (everything via `.env`; project-scoped via a ContextVar + `__getattr__`).
- **Multi-project:** ONE engine + ONE Qdrant (a collection per project) + ONE shared
  model service (flat RAM with many projects open). Projects live at arbitrary host
  paths, registered in `projects.json` → bind mounts generated into
  `docker-compose.override.yml` (`brag/compose_gen.py`, `brag/projects.py`,
  `brag/registry.py`). Each project = a `brag-<name>` MCP connector.

## The vault layout (current model)
- The **project folder** the user picks **IS** the searchable corpus — every
  subfolder, any depth — EXCEPT `WissensWIKI/` and hidden/`_inbox` dirs
  (`config.is_corpus_path`). The first subfolder level = the document *type*.
- `WissensWIKI/` is the user's workspace: `Passagen/` (verified passages saved via the
  `/beleg` → `save_passage` tool — **indexed**), `Notizen/` + any free subfolders (the
  notebook — MCP read/write via `read_note`/`write_note`, **NOT** indexed, so notes
  never echo into search), and `CLAUDE.md`/`AGENTS.md` end-user guides (not indexed).
- The engine is the **"BRAG Assistent"** folder — its own location, never opened or
  deleted (gets a Windows folder icon + a do-not-delete note). Setup asks two things:
  where the engine goes, then the project folder. `VAULT_PATH` = the project root.

## Status (update me as it changes — June 2026)
- **0.4.0 shipped:** multi-project + the project-folder-as-corpus layout rework + the
  install rework — all merged to `main`.
- **0.4.1 shipped:** per-connector uninstall now removes the connector (incl. the
  default project) plus a full Docker clean — also merged to `main`.
- **Current version: 0.4.1.** The repo + the GHCR `brag` package are kept **PRIVATE**
  for now. No data migration — fresh installs only.

## Dev workflow — run before every commit
```
python -m compileall brag
python -m ruff check brag tests --select E9,F,E501,W
python -m pytest -q
docker compose build            # must succeed (CONTRIBUTING.md)
```
Validate host scripts too: `bash -n` the `.command` files; PowerShell-parse the `.ps1`
(`[System.Management.Automation.Language.Parser]::ParseFile`). Keep EN/DE doc + i18n
key parity (line-anchored).

## Conventions & hard-won gotchas
- **Line endings (critical).** `.bat`/`.cmd`/`.ps1` MUST be **CRLF** or `cmd.exe`
  "won't start" (goto-heavy scripts especially). `git archive` (GitHub "Download ZIP")
  ignores `eol`, so the Windows scripts are stored verbatim as CRLF via `-text` in
  `.gitattributes`; `.command`/`.sh` are LF. Don't normalize them back.
- **Batch.** Flatten control flow with `goto`; never put a `%VAR%` holding a
  possibly-parenthesized path inside an `if (...)` block (a `)` in the path closes the
  block early). Windows PowerShell 5.1 `.ps1` must be **ASCII-only** (a stray em-dash
  breaks the parser). `.bat` echoes/files are ASCII too.
- **Claude Desktop rewrites its config while running** and drops externally-added MCP
  entries — write connectors only when Claude is fully quit (`tools/ensure_claude_closed`).
- **Don't re-run setup while a document is still indexing.** Setup stops the app
  (Exit 137); ingest only upserts at the very end, so an interrupted ingest leaves 0
  points + no logs. The slow stage is `[2/4] contextual retrieval` (the LLM).
- `COMPOSE_PROJECT_NAME=brag` is pinned in `.env` so the volumes are stable regardless
  of the engine folder name (`brag_qdrant_data`, `brag_models_cache`).
- Container writes don't reliably reach the host on Windows — host-side `.ps1`/`.bat`
  writers handle Claude/LM Studio config; reject `$ & % ^ !` in chosen paths.
- Published image: `ghcr.io/mdrinjak-bauing/brag:latest` (multi-arch). Pushing needs a
  token with `write:packages`.

## Where to look next
README.md / README.de.md (user docs) · docs/ARCHITECTURE.md · docs/INSTALL_*.md ·
docs/FAQ.md · CONTRIBUTING.md · CHANGELOG.md.
