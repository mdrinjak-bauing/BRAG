# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

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

[0.2.0]: https://github.com/mdrinjak-bauing/Academic-RAG-and-Second-Brain
[0.1.0]: https://github.com/mdrinjak-bauing/Academic-RAG-and-Second-Brain
