# Academic Second Brain

**Your personal, searchable research knowledge base — talk to your document
corpus through Claude Desktop.**

Drop PDFs into a folder. They are automatically parsed (including tables and
figure captions), enriched with AI-generated context, and indexed for hybrid
semantic + keyword search. Then ask Claude questions about your literature —
with answers grounded in your sources, page-precise, and one click away from
the original PDF.

Built for researchers, professors and PhD students — **no programming
required**. Everything runs in Docker.

## What it does

- **Automatic ingest** — drop a PDF/DOCX into `vault/sources/`, done. Tables are kept intact, long tables are split with repeated headers, figures are indexed by caption.
- **Contextual retrieval** — every text chunk gets 1–2 sentences of AI-generated context before indexing ([Anthropic, 2024](https://www.anthropic.com/news/contextual-retrieval)) — dramatically better recall on terse academic prose.
- **Hybrid search** — semantic similarity + exact keyword match (BM25 with language-aware stemming), fused and re-ranked by a cross-encoder.
- **Claude Desktop integration (MCP)** — `search`, `list_sources`, `inspect_chunks`, `save_passage`, `list_passages` as native tools in your Claude conversations.
- **Page-precise citations** — every search hit links to the PDF, opening in your browser at the right page.
- **Obsidian-compatible vault** — literature notes are auto-generated as Markdown; your own notes live alongside, never overwritten.

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free)
- [Claude Desktop](https://claude.com/download) (free)
- For the recommended Cloud profile: a free [Gemini API key](https://aistudio.google.com/apikey)

## Quickstart (5 minutes + first build)

1. **Download** this repository (green "Code" button → "Download ZIP") and unpack it.
2. **Run setup:** double-click `setup.command` (Mac) or `setup.bat` (Windows). The wizard asks three questions (profile, API key, language) and configures everything — including Claude Desktop.
3. **Restart Claude Desktop** completely (quit and reopen).
4. **Drop a PDF** into the `vault/sources/` folder.
5. Ask Claude: *"What documents are in my knowledge base?"* — then ask real questions.

The first build downloads ~3 GB (document-analysis models). After that,
everything is instant.

## Choose your profile

| | A — Cloud (default) | B — Hybrid | C — Local |
|---|---|---|---|
| AI processing | Google Gemini API (free tier) | LM Studio on your machine | Ollama on your machine |
| Hardware needed | any laptop | Mac with Apple Silicon, 32 GB+ | decent CPU, 16 GB+ |
| Documents leave your machine | yes (Google) | no | no |
| Speed | fast | medium | slow |

Details and a decision guide: [docs/PROFILES.md](docs/PROFILES.md).
**Note:** switching profiles later requires re-indexing your documents
(different embedding models are mathematically incompatible).

## Why not RAGFlow / RAG-Anything / ...?

Excellent projects — different goals. [RAGFlow](https://github.com/infiniflow/ragflow)
is an enterprise platform (7 services, 16 GB+ RAM, its own web UI).
[RAG-Anything](https://github.com/HKUDS/RAG-Anything) is a research framework
built on knowledge graphs, without page-precise citations. **Academic Second
Brain is deliberately small**: one container + one database, Claude Desktop as
the interface, citations that hold up in academic writing, and a plain-files
vault you fully own.

## Documentation

- [Install on macOS](docs/INSTALL_MAC.md) · [Install on Windows](docs/INSTALL_WINDOWS.md)
- [Backend profiles](docs/PROFILES.md) · [Connect Obsidian](docs/OBSIDIAN.md)
- [Customize Claude for your research](docs/CUSTOMIZE_CLAUDE.md)
- [FAQ & troubleshooting](docs/FAQ.md) · [Architecture](docs/ARCHITECTURE.md)

## Status

Early release. The Cloud profile (A) is the tested happy path; profiles B/C
are functional but less battle-tested. Roadmap: AI image descriptions for
figures (vision pass), automatic file naming, corpus overview modes.

## License

[MIT](LICENSE)
