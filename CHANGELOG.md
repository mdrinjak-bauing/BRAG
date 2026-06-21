# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [0.4.0] — 2026-06-21

Multiple projects from one engine, and a clearer "your folder IS the corpus"
layout — plus a friendlier install, a quick settings page and a granular
uninstall. Fresh installs only (no published predecessor to migrate); supersedes
the unreleased 0.3.4 install/layout below.

### Added
- **Multiple projects from one engine.** Connect several knowledge bases, each at
  any location, each with its own search index and its own `brag-<folder>`
  connector in Claude / LM Studio — while the program, the ~3 GB models and Qdrant
  are shared exactly once. Add one with **`Projekt hinzufuegen`**; remove one (or
  everything) via the new **uninstall menu**. Many open project connectors share a
  single in-container model set, so RAM stays flat.
- **Your project folder is the corpus.** Drop documents straight into the folder
  you pick — every subfolder is searched — EXCEPT the **`WissensWIKI/`** workspace.
  WissensWIKI holds `Passagen/` (verified passages you save via Claude — indexed),
  `Notizen/` and your own subfolders (a notebook Claude reads/writes but that is
  NOT indexed, so notes never echo into search), and the CLAUDE.md / AGENTS.md
  guides.
- **"Change a setting" page** in the setup wizard — adjust the model, reranker,
  vision or language on one screen without re-walking setup; the provider and API
  key are kept.
- **`Verbindung reparieren`** — a one-click tool that re-writes the Claude / LM
  Studio connectors if one ever goes missing.
- **Crash-loop guard.** A document whose indexing is interrupted repeatedly (e.g.
  a PC reset under heavy local-LLM GPU load) is skipped with a visible note instead
  of re-crashing the machine on every auto-restart; optional
  `LOCAL_LLM_PACING_SECONDS` paces local LLM calls.

### Changed
- **The program is now "BRAG Assistent"** (renamed from "RAG Setup"), installed in
  its own location with a do-not-delete note and a Windows folder icon. Setup asks
  two things: where the program goes, and your project folder. The app mounts ONLY
  your project folder — never the engine dir — so `.env` and scripts stay out of
  the long-running container.
- Volumes are pinned to a stable compose project name (`brag_qdrant_data`,
  `brag_models_cache`), independent of the engine folder name.

### Fixed
- Switching from a local to a cloud profile no longer carries the stale local model
  name (which made every contextualization call fail), and the API key is kept on a
  same-provider re-run — so changing one setting needs no re-typing.
- A `.gitattributes` enforces CRLF for Windows scripts (`.bat`/`.cmd`/`.ps1`) so a
  `git clone` or a GitHub source ZIP runs on Windows (LF made `cmd.exe` fail).

## [0.3.4] — 2026-06-21

A plug-and-play install and a clearer on-disk layout. No re-indexing needed.

### Added
- **Self-organizing install.** On first run the launcher opens a native folder
  picker (PowerShell on Windows, osascript on macOS) and asks *where* to create
  your **RAG connection folder**. BRAG then copies itself into a `RAG Setup/`
  subfolder, creates your knowledge folder `WissensWIKI/` next to it, and
  continues setup from the new location. Cancel the picker to install in place.
- **WissensWIKI is seeded immediately** with its `sources/ notes/ wiki/
  passages/` structure (and the CLAUDE.md / AGENTS.md guides), so you see the
  full layout right after choosing the folder — not only after the first start.
- **LM Studio on the final screen + status check.** The done screen now also
  describes the LM Studio connection (restart it, enable the `brag` integration),
  and `status.bat` / `status.command` verify the LM Studio `brag` entry alongside
  Claude Desktop.

### Changed
- **Knowledge folder renamed to `WissensWIKI`** (the default was previously the
  generic `RAG-Verbindungsordner`). Clear three-part model: the **RAG connection
  folder** is the container; **`WissensWIKI/`** is the searched knowledge vault;
  **`RAG Setup/`** is the program. Existing installs keep their current
  `VAULT_PATH`; nothing is moved or re-indexed.

### Fixed
- **Claude Desktop connection now persists.** A running Claude Desktop rewrites
  its own config file and would silently drop the `brag` entry added underneath
  it — the connection appeared "missing" after setup. The launcher now writes the
  entry only **after** Claude is fully quit (it waits for you), so it sticks.
  Added a host-side `tools/merge_claude_config.py` so macOS gets the same
  reliable, post-quit write as Windows, and the wizard's final-screen wording now
  explains this.
- **An empty wizard folder field no longer repoints a chosen vault.** The wizard
  now preserves the `VAULT_PATH` written by the picker/relocation instead of
  coercing it back to the default — so your documents stay where you put them.
- **Picker robustness:** the chosen path is rejected if it contains shell-unsafe
  characters; Windows uses a UTF-8 codepage so umlaut paths survive; macOS
  escapes `$` so Docker Compose never mis-reads the mounted path.

## [0.3.3] — 2026-06-20

### Removed
- **Ollama support dropped.** BRAG is driven by an MCP host, and Ollama is a
  model backend, not an MCP host — so it could never auto-connect the way Claude
  Desktop and LM Studio do. **LM Studio is now the single local-LLM option** (it
  runs on Windows, macOS and Linux, including weaker laptops — ~16 GB RAM handles
  a ~7B model). Removed the `local` profile, the Ollama embedding backend, the
  wizard's Ollama step, and every Ollama reference across docs and setup. Existing
  installs on `PROFILE=local`: switch to `hybrid` (LM Studio) or a cloud profile
  and re-run setup.

## [0.3.2] — 2026-06-20

A reliability, security and documentation hardening release following a full
pre-publication audit (correctness, security, licensing/privacy and
release-readiness), plus a clean rebrand and LM Studio auto-configuration. Most
changes need no re-indexing — see **Migration** for the one exception.

### Fixed
- **Silent data loss with same-named files (critical).** A document's identity
  was its bare filename, so two files with the same name in different folders
  (e.g. `projectA/Bericht.pdf` and `projectB/Bericht.pdf`) collided — ingesting
  one deleted the other's chunks, and deleting one wiped both. Identity is now
  **path-qualified**.
- **Page citations across multi-page sections.** Every chunk of a section that
  spanned pages inherited the section's *first* page, so a passage physically on
  page 18 was cited (and deep-linked) to page 10. Each chunk now carries the
  **real page range** of the text it contains.
- **Partial ingests no longer lose pages silently.** A document whose chunks
  partly failed to embed (e.g. a transient cloud rate-limit) was logged as
  complete and never retried; it is now re-driven on the next start, with a
  bounded number of attempts.
- **`inspect_chunks(page=N)`** now returns chunks whose page range *covers* N,
  not only chunks that start on N.
- **Watcher concurrency** — the in-progress set is lock-guarded so the polling
  observer cannot start a duplicate ingest of the same file.
- **Large `top_k` searches** are no longer silently capped by the rerank/fusion
  presets.
- **Clear error on an embedding-dimension mismatch** (model dim vs
  `EMBEDDING_DIM`) instead of an opaque crash on every upsert.
- **Search robustness** — a malformed `year` filter value is now coerced away
  instead of crashing the query, and an absurd `top_k` is clamped by a generous
  sanity bound (ordinary large `top_k` stays supported).
- **Bounded retry waits** — cloud LLM/embedding retries honour an overall
  deadline, so repeated rate-limit backoffs can no longer hang a single call for
  minutes.
- **Deletions made while the app was stopped are now cleaned up.** On start,
  index entries whose source file no longer exists are pruned (guarded so an
  unmounted knowledge folder can never wipe the index) — this also clears stale
  entries left over from the path-qualified-identity change.
- **Edited documents are re-indexed automatically.** Overwriting a file in place
  is detected (file mtime vs. last ingest) and the document is re-indexed — live
  and on startup — instead of keeping the old content forever.
- **Chunk-id collisions removed.** The per-chunk id now hashes the full chunk
  text (not a 120-character prefix), so two chunks that share a long
  chapter/section prefix can no longer overwrite each other on upsert.
- **The setup wizard no longer drops hand-set `.env` keys** (e.g. `LLM_MODEL`,
  `EMBEDDING_*`, rerank overrides) when you re-run it.

### Performance
- **Batched local embeddings** — document chunks are embedded in batches (one
  model call per batch instead of one per chunk), markedly faster bulk ingest on
  the local, CPU-bound embedder that every profile uses. The batch contract
  keeps each vector aligned to its chunk (no misattributed page citations) and
  falls back to per-chunk embedding on any inconsistency.
- **Reranker warm-up** — the local cross-encoder is loaded in a background
  thread at MCP-server start, so the *first* search is no longer blocked by the
  one-time model load.
- **Deeper rerank candidate pool** — each `RERANK_PROFILE` now retrieves a
  larger pool before reranking (prefetch raised, e.g. `eco` 80+80 instead of
  60+60), so the cross-encoder picks from better recall **without scoring more
  pairs** — i.e. essentially no extra CPU, since retrieval is cheap and the
  rerank count is unchanged.

### Security
- **Setup is now a separate one-shot service.** The persistent app container no
  longer mounts the project directory or the Claude Desktop config — only the
  short-lived `setup` service does. A compromised ingest/parse path can no
  longer read `.env` or rewrite the host's Claude Desktop configuration.
- **Qdrant telemetry disabled** by default (`QDRANT__TELEMETRY_DISABLED`).
- **`.env` injection guard** — wizard-supplied values are sanitised so a newline
  cannot inject extra `.env` entries.
- Added **`SECURITY.md`** (private reporting + the prompt-injection threat model).

### Added
- A real **end-to-end CI test** (build → ingest a PDF → search → page citation)
  and a light **unit-test suite**, both run in CI.
- **`NOTICE.md`** (third-party model and dependency licenses).
- **`CODE_OF_CONDUCT.md`**, GitHub issue forms and a pull-request template.
- Optional **model-revision pinning** (`EMBEDDING_REVISION` / `RERANKER_REVISION`)
  for reproducible, supply-chain-safe model downloads.
- Documented `BRIDGE_HOST_PORT` / `BRIDGE_PUBLIC_URL` in `.env.example`.
- More **unit tests** (embedding-batch alignment contract, retry classification
  and deadline, config fallbacks) and a **`pyproject.toml`** ruff configuration
  (line length + whitespace) that now drives the CI lint step.
- **Corpus management from Claude**: `remove_source` (drops a source from the
  index and moves its file to `sources/_inbox/`, reversible) and `rename_source`
  (re-files an indexed document, metadata patched in place, no re-embedding).
- **Notebook tools in the MCP server**: `list_notebook`, `read_note`,
  `write_note` — Claude reads and extends your notebook (wiki/notes) directly,
  without a second server; the search index is never touched.
- **Optional cloud-model picker** in the setup wizard.
- **LM Studio auto-configured too.** Setup now adds the BRAG connection to LM
  Studio's `mcp.json` if LM Studio is installed (not only Claude Desktop), so its
  chat can use the same search + notebook tools. Ollama is a model backend, not an
  MCP host, so there is nothing to configure there.
- Startup now **flags leftover Qdrant collections** from a previous embedding
  setting (never auto-deleted) so unused collections don't silently waste disk.

### Changed
- **Renamed for a clean public release** (backward-compatible): the assistant
  connection now shows as **`brag`** (was a long internal name; setup migrates
  older installs), and the default knowledge folder for new installs is
  **`RAG-Verbindungsordner/`** (existing installs keep their `VAULT_PATH`); the
  not-indexed marker now follows the language setting. `pyproject.toml` declares
  package metadata and `brag` now exposes `__version__`.
- A clear **API-key handling** note (stored only locally in `.env`, only ever
  sent to your chosen provider, never to the project or third parties) now
  appears in the setup wizard and across the docs.
- The ingest-pipeline docs now explain the **extract→chunk** handoff.
- A **hallucination / citation-accuracy disclaimer** was added to the README and
  the legal notice.
- `PROFILE` now defaults to `gemini` (previously the equivalent `cloud` alias).
- Routine dependency updates (sentence-transformers, GitHub Actions).

### Migration
Pull and **re-run setup once** (`setup.command` / `setup.bat`) so the new
one-shot setup service writes your configuration. **Top-level documents are
unaffected.** If you keep documents in **subfolders** of `sources/`, their
identity keys change to include the folder path: they are re-indexed
automatically on next start, but the old entries linger — for a clean index,
rebuild it (re-ingest your corpus, or remove the Qdrant volume and let it
re-index).

## [0.3.0] — 2026-06

### Changed
- **Renamed the project to BRAG** (*Building Retrieval-Augmented Generation*),
  end to end: user-facing branding, the Python package (`asb` → `brag`), the
  Docker image (`asb:latest` → `brag:latest`) and the containers
  (`asb-app`/`asb-qdrant` → `brag-app`/`brag-qdrant`). The MCP server key, the
  environment variable names (`VAULT_PATH`, …) and the Qdrant collection name
  (internal `asb_…` prefix) are intentionally kept so **no indexed data is
  lost**.
  **Migration for existing installs:** pull, run `docker compose up -d --build`
  (your knowledge store and index are preserved via the named volume), then
  **re-run the setup once** (`setup.command` / `setup.bat`) so Claude Desktop
  points at the new `docker exec brag-app …` command.
- Knowledge-store default folder renamed `vault/` → `wissensspeicher/`. The
  `VAULT_PATH` / `VAULT_DIR` environment variables and the internal `/vault`
  mount point are kept for backwards compatibility.
- **Search-speed dial (`RERANK_PROFILE`).** The local cross-encoder reranker is
  the main CPU cost of a search, so it is now a single setting: `off` /
  **`eco`** (new default — load 120 candidates, rerank 40) / `balanced` (rerank
  60) / `full` (rerank 120). The previous heavier behaviour (prefetch 150,
  rerank 80) is roughly the `full` preset; the lighter default keeps searches
  responsive on consumer PCs. Individual values can still be pinned via
  `RERANK_ENABLED` / `RERANK_PREFETCH` / `RERANK_FUSION_LIMIT`. The `search` MCP
  tool now follows the configured default instead of forcing reranking on.

### Added
- **One-click status check** (`status.command` / `status.bat`) and an
  `brag.health` module: verifies Docker, the `brag-app`/`brag-qdrant` containers,
  Qdrant, the corpus index, the folder watcher, the AI text backend, and the
  Claude Desktop connection, with a ✓/✗ per item.
- **Lightweight rename of indexed files**: renaming or moving a file that is
  already in the index now patches the filename-derived metadata
  (`source_file`, author, year, doc_type, rel_path, custom `_meta` fields) on
  the existing chunks and moves the literature note, instead of re-embedding the
  whole document. Re-ingest only happens when the file was not indexed yet.
- New doc **"Which Claude surface?"** (`docs/WHICH_CLAUDE.md` / `.de.md`):
  when to use Chat vs. Cowork vs. Code, and why Chat is BRAG's home.
- **Saved passages are now searchable.** `save_passage` not only writes the
  quote into `wissensspeicher/passages/` but also indexes it, so a later chat —
  even with a different AI provider — finds it again via `search`, tagged as a
  *saved passage* and kept distinct from primary sources. This makes the
  "knowledge lives in the folder, not the chat history" promise literally true.
  (The rest of the notebook — `wiki/`, `notes/` — stays out of the index by
  design; see the README "library and notebook" section.)
- The `sources/_inbox/` staging area now ships in the knowledge-store template,
  matching the documented folder layout.

### Security
- HTTP bridge now enforces a **localhost Host-header allowlist** (and an Origin
  check on POSTs), defeating DNS-rebinding attacks against the setup API that
  writes the API key and the Claude Desktop config.
- Knowledge-store files other than PDFs are served as downloads with
  `X-Content-Type-Options: nosniff` instead of active `text/html` — closes a
  stored-XSS-to-config-write path on the bridge's own origin.
- Claude Desktop config writes are now **atomic** (temp file + replace), always
  back up a valid config first, and **refuse** (rather than discard) an existing
  config that is not valid JSON. Added `no-new-privileges` to the app container
  and a `CLAUDE_CONFIG_MOUNTED` guard so the wizard no longer reports success
  when no real Claude config dir is mounted.
- Setup page builds the local-model dropdown from DOM nodes instead of
  `innerHTML` and is served with a strict **Content-Security-Policy** — closes a
  reflected-XSS vector via attacker-controlled local-model names.
- App container now runs as a **non-root user** with **all Linux capabilities
  dropped** (`cap_drop: ALL`). The `.env` file (which holds the API key) is
  written atomically and set to mode `0600`, and the setup API caps the request
  body size. Added `pip-audit` to CI and a Dependabot config (pip + Actions).

### Fixed
- `source_file` filters (search, `inspect_chunks`, delete) now use an
  **NFC/NFD/raw triple-probe** instead of NFC-only, so a source whose payload
  was written under a different Unicode normalization is still found.
- Query embeddings are truncated to the same bound as document embeddings
  (`MAX_INPUT_CHARS`), keeping query/document input regimes symmetric.
- Retry classifier treats HTTP **529** (Anthropic overload) as retryable.
- A single transient empty vision response no longer disables figure
  descriptions for the rest of a document (latches off only after two in a row).
- Docs: corrected leftover "profile B/C" naming in `ARCHITECTURE.md` and
  `FAQ.md`; fixed a German "see also" link that pointed at the English docs.
- **Rename in place** now uses the NFC/NFD/raw triple-probe too, so a file whose
  chunks were stored under a different Unicode form is patched in place instead
  of silently re-ingested; and stale custom `_meta` fields from a previous
  folder are removed on a move, so a moved document no longer leaks into the old
  project/course filter.
- Page links no longer drift by one after a table or figure (text-chunk
  `page_end` is now reset together with `page_start`).
- Contextual retrieval matches a chunk's chapter by the **exact** heading text
  instead of a case-insensitive substring, so short/repeated titles no longer
  pull in the wrong section's context.
- The setup wizard no longer wrongly requires an Ollama embedding model
  (`nomic-embed-text`) for the local profile — embeddings are always local
  (arctic), so only a chat model is needed.
- A heavy batch of embedding failures (e.g. a sustained cloud rate limit) now
  aborts the document instead of freezing a partial index, so reconciliation
  retries it later.
- The setup launcher opens the right URL when `BRIDGE_HOST_PORT` is customized
  (port 8765 already in use); the cross-encoder reranker takes an explicit batch
  size for predictable latency on weak CPUs; and the knowledge-store template no
  longer ships files titled "Vault".
- **Citations can show the printed (book) page, not the physical PDF page.** Set
  `page_offset` in a `_meta.txt` (printed page = physical page − offset): the
  citation then shows the printed page while the deep-link still jumps to the
  correct physical PDF page. Documented the `#page=` viewer behaviour — Chrome,
  Edge and Firefox honour it; Safari opens page 1, so **Skim** (macOS) /
  **SumatraPDF** (Windows) are recommended as page-jumping viewers.

## [0.2.0] — 2026-06

### Added
- **Vision pass for figures** (`VISION_ENABLED`, on by default): each figure
  image is rendered and sent to the multimodal text LLM for an honest 1–3
  sentence description that is embedded, so figures become findable by content.
  Works with any multimodal model (all cloud presets; local profiles need a
  vision model) and falls back safely to caption-only otherwise. With a cloud
  profile the figure images are sent to the provider (documented in LEGAL).
- **OpenAI/ChatGPT** and **Anthropic/Claude** cloud providers alongside Google
  Gemini, each preset to its cheapest capable model (`gpt-4o-mini`,
  `claude-haiku-4-5`, `gemini-2.5-flash-lite`).
- **Bilingual setup wizard** (German/English) with hardware-aware model
  recommendations for the local profiles.
- Documentation: a full walkthrough of the **query pipeline** (hybrid search →
  RRF fusion → cross-encoder reranking → top-K), plus new sections on **Docker**
  (what it is, why, and where the ~3 GB of models live), **cost/model choice**,
  and the **local embedding model vs. hardware** distinction.
- **German translations** of every doc that previously existed only in English
  (install guides, profiles, FAQ, Obsidian, customizing Claude, architecture),
  each with a language switcher.
- **Legal notices** (`docs/LEGAL.md` / `LEGAL.de.md`): disclaimer, data-privacy
  guidance (incl. the free-Gemini caveat that submissions may be used to improve
  Google's products and reviewed by humans), and copyright/TDM notes — linked
  from both READMEs with a privacy caution near the profile table.
- Step-by-step install walkthroughs with "what to open / what you see" cues and
  a "how do I know it's running?" check; a "where does this get installed?"
  section and a plain-words tour of the subsystems (watcher, ingest, search,
  HTTP bridge, MCP server) in *How it works*.

### Changed
- The **meaning index (arctic embeddings) now runs locally in every profile**.
  As a result, switching the AI provider no longer requires re-indexing the
  corpus — every profile writes into the same collection.
- Local profiles no longer pull a separate embedding model; arctic is handled
  automatically inside the container.
- Guide rewritten in a more mature register and version-stamped.

## [0.1.0] — initial release

### Added
- Cloud profile with Google Gemini for contextual retrieval, figure
  descriptions and document classification.
- Hybrid search (dense + sparse/BM25) with reciprocal-rank fusion and
  cross-encoder reranking, page-precise citations, and clickable PDF links.
- Knowledge store (library vs. notebook) and the search MCP server for
  Claude Desktop.

[0.3.3]: https://github.com/mdrinjak-bauing/BRAG/releases/tag/v0.3.3
[0.3.2]: https://github.com/mdrinjak-bauing/BRAG/releases/tag/v0.3.2
[0.3.0]: https://github.com/mdrinjak-bauing/BRAG/releases/tag/v0.3.0
[0.2.0]: https://github.com/mdrinjak-bauing/BRAG/releases/tag/v0.2.0
[0.1.0]: https://github.com/mdrinjak-bauing/BRAG/releases/tag/v0.1.0
