# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [0.3.0] — 2026-06

### Changed
- **Renamed the project to BRAG** (*Building Retrieval-Augmented Generation*).
  This is a branding change only — the internal package, container names, MCP
  server key and environment variables are unchanged, so existing installations
  keep working without reconfiguration.
- Knowledge-store default folder renamed `vault/` → `wissensspeicher/`. The
  `VAULT_PATH` / `VAULT_DIR` environment variables and the internal `/vault`
  mount point are kept for backwards compatibility.

### Added
- **One-click status check** (`status.command` / `status.bat`) and an
  `asb.health` module: verifies Docker, the `asb-app`/`asb-qdrant` containers,
  Qdrant, the corpus index, the folder watcher, the AI text backend, and the
  Claude Desktop connection, with a ✓/✗ per item.
- **Lightweight rename of indexed files**: renaming or moving a file that is
  already in the index now patches the filename-derived metadata
  (`source_file`, author, year, doc_type, rel_path, custom `_meta` fields) on
  the existing chunks and moves the literature note, instead of re-embedding the
  whole document. Re-ingest only happens when the file was not indexed yet.
- New doc **"Which Claude surface?"** (`docs/WHICH_CLAUDE.md` / `.de.md`):
  when to use Chat vs. Cowork vs. Code, and why Chat is BRAG's home.

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

[0.2.0]: https://github.com/mdrinjak-bauing/academic-rag-and-second-brain
[0.1.0]: https://github.com/mdrinjak-bauing/academic-rag-and-second-brain
