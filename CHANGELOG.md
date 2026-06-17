# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

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
