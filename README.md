# Academic Second Brain

**🇬🇧 English | 🇩🇪 [Deutsch](README.de.md)**

**Your personal, searchable research knowledge base — talk to your document
corpus through Claude Desktop.**

Drop PDFs into a folder. They are automatically parsed (including tables and
figure captions), enriched with AI-generated context, and indexed for hybrid
semantic + keyword search. Then ask Claude questions about your literature —
with answers grounded in your sources, page-precise, and one click away from
the original PDF.

Built for researchers, professors and PhD students — **no programming
required**. Everything runs in Docker.

---

## The idea: a library and a notebook

A research "second brain" has two halves, and keeping them apart is the
whole point of this design:

|  | 📚 **Your library** | 📓 **Your notebook** |
|---|---|---|
| Folder | `vault/sources/` | `vault/wiki/`, `vault/notes/`, `vault/passages/` |
| Contains | external sources: papers, books, reports | **your own thinking**: concepts, drafts, decisions, reading notes |
| Searchable by Claude? | yes — full hybrid search with page-precise citations | deliberately **no** |
| Claude can read/write it? | read-only (via search) | yes — via the optional Obsidian connection (see below) |

**Why is the notebook excluded from the search index?** Because of the echo
effect: if your own notes were indexed, you would one day "find" your own
summary of a paper and cite it as evidence — without noticing that you are
quoting yourself. The library answers *"what do my sources say?"*; the
notebook holds *what you make of it*. Claude can work with both, but never
confuses one for the other.

## How it works

![Architecture: vault, Docker containers, Claude Desktop and the two MCP connections](docs/assets/architecture.svg)

```
 you drop a PDF into vault/sources/
        │
        ▼ (automatic, ~1–3 min per paper)
 parse layout → split into chunks → AI adds context  → hybrid index
 (tables,        (tables kept       to every chunk      (semantic +
  figures,        intact)            for better          keyword)
  chapters,                          retrieval
  pages)
        │
        ▼
 you ask Claude Desktop a question
        │
        ▼
 Claude searches your corpus → answers with citations →
 every citation links to the PDF, opened at the right page
```

Everything runs in two Docker containers on your machine. In the recommended
Cloud profile, document text is processed by Google's free Gemini API; in the
local profiles, nothing leaves your computer (see [Profiles](#choose-your-profile)).

## The two Claude connections (MCP)

Claude Desktop talks to your second brain through two MCP servers — one for
each half:

### 1. The search connection (this project — set up automatically)

The setup wizard registers it in Claude Desktop for you. It gives Claude
these tools:

| Tool | What it does | Example question to Claude |
|---|---|---|
| `search` | Hybrid search with filters (document type, year, tables/figures only, source) | *"What does my corpus say about contract change management?"* — *"Find tables with cost figures on rework."* |
| `list_sources` | Inventory of all indexed documents | *"What documents are in my knowledge base?"* |
| `inspect_chunks` | Shows what is actually stored for a source — your debugging x-ray | *"Show me what was indexed from Smith 2023, page 14."* |
| `save_passage` | Saves a quotable hit under a topic in `passages/` | *"Save this quote for my methods chapter."* |
| `list_passages` | Shows saved passages per topic | *"What have I collected for the methods chapter so far?"* |

Every search hit carries a clickable link that opens the PDF **at the cited
page** in your browser.

### 2. The notebook connection (optional — 5 manual minutes)

To let Claude also read and write your notebook (`wiki/`, `notes/`), add the
community plugin **MCP Tools for Obsidian**. Then Claude can summarize your
notes, maintain concept pages, and update literature notes — while the search
index stays untouched. Step-by-step guide: **[docs/OBSIDIAN.md](docs/OBSIDIAN.md)**.

With both connections active, a single conversation can do this:
*"Search my corpus for definitions of process maturity (library), compare
them with my concept note on maturity models (notebook), and update the note
with what's missing — with citations."*

## Why Obsidian?

You don't have to use it — the vault is a normal folder of Markdown and PDF
files that you fully own. But [Obsidian](https://obsidian.md) (free) is the
ideal viewer for it:

- **Plain files, no lock-in** — Obsidian works directly on the folder; nothing is imported or converted.
- **Wikilinks & graph** — connect concept notes with `[[links]]` and see your thinking as a network.
- **Search & daily notes** — comfortable editing for the notebook half.
- It is the standard tool of the academic note-taking community, so guides and plugins abound.

Open the `vault/` folder as an Obsidian vault and you are done
([docs/OBSIDIAN.md](docs/OBSIDIAN.md), part 1).

## Your knowledge folder (the vault)

The vault is **one folder on your computer** — by default `vault/` inside
the project directory. During setup you can point the system at any other
folder instead (Advanced options → custom path), e.g. an existing literature
collection. The structure:

```
vault/
├── CLAUDE.md      ← teaches Claude about YOUR research — fill it in!
├── AGENTS.md      ← extra rules for autonomous agent tasks
├── sources/       ← 📚 drop documents here (PDF, DOCX); subfolders = document types
│   └── _inbox/    ← staging area, ignored by the indexer (create if needed)
├── notes/         ← auto-generated literature note per source (+ your additions)
├── passages/      ← quotes you saved via Claude, grouped by topic
└── wiki/          ← 📓 your own thinking — never indexed
```

Renaming or deleting a file in `sources/` is handled automatically (the index
and the literature note follow). Subfolder names become the document type you
can filter by: `sources/papers/`, `sources/books/`, `sources/reports/` …

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free)
- [Claude Desktop](https://claude.com/download) (free)
- Cloud profile: a free [Gemini API key](https://aistudio.google.com/apikey)
- Local profiles: [LM Studio](https://lmstudio.ai) or [Ollama](https://ollama.com) (the setup assistant guides you, including which model to download)

## Quickstart

1. **Download** this repository (green "Code" button → "Download ZIP") and unpack it.
2. **Double-click `setup.command`** (Mac) or **`setup.bat`** (Windows).
   The setup assistant opens **in your browser** and walks you through:
   - where AI processing should happen (two plain questions, no jargon),
   - your API key (with live validation) *or* the local AI app (with model
     recommendations for your hardware and a connection check),
   - your document language and, optionally, a custom vault folder.
   It writes all configuration **including the Claude Desktop entry** —
   you never edit a config file.
3. **Quit Claude Desktop completely** (Cmd+Q / tray → Quit) and reopen it.
4. **Drop a PDF** into `vault/sources/` — indexed automatically within seconds.
5. Ask Claude: *"What documents are in my knowledge base?"*

First build downloads ~3 GB of document-analysis models (one time).
Detailed guides: [macOS](docs/INSTALL_MAC.md) · [Windows](docs/INSTALL_WINDOWS.md)

## Choose your profile

| | A — Cloud (default) | B — Hybrid | C — Local |
|---|---|---|---|
| AI processing | Google Gemini API (free tier) | LM Studio on your machine | Ollama on your machine |
| Hardware needed | any laptop | Mac with Apple Silicon, 32 GB+ | decent CPU, 16 GB+ |
| Documents leave your machine | yes (Google) | no | no |
| Speed | fast | medium | slow |

Decision guide and model recommendations: [docs/PROFILES.md](docs/PROFILES.md).
**Note:** switching profiles later requires re-indexing (different embedding
models are mathematically incompatible — the system handles this safely, but
the work runs again).

## A typical day with it

1. A colleague sends you a paper → you drop it into `sources/papers/`.
2. Twenty minutes later you ask Claude: *"Does the new paper contradict what
   Müller 2021 says about rework cost drivers? Compare them."*
3. Claude searches both, answers with page-linked citations; you click one
   and the PDF opens at the page.
4. *"Save the second quote for my chapter on quality costs."* → lands in
   `passages/quality_costs.md`.
5. You jot your own take in `wiki/Rework_Cost_Drivers.md` — Obsidian, or ask
   Claude to draft it via the notebook connection. It will never show up as
   a "search hit" later. That's the point.

## Why not RAGFlow / RAG-Anything / …?

Excellent projects — different goals. [RAGFlow](https://github.com/infiniflow/ragflow)
is an enterprise platform (7 services, 16 GB+ RAM, its own web UI).
[RAG-Anything](https://github.com/HKUDS/RAG-Anything) is a research framework
built on knowledge graphs, without page-precise citations. **Academic Second
Brain is deliberately small**: one container + one database, Claude Desktop as
the interface, citations that hold up in academic writing, and a plain-files
vault you fully own.

## Documentation

- [Install on macOS](docs/INSTALL_MAC.md) · [Install on Windows](docs/INSTALL_WINDOWS.md)
- [Backend profiles](docs/PROFILES.md) · [Connect Obsidian + notebook MCP](docs/OBSIDIAN.md)
- [Customize Claude for your research](docs/CUSTOMIZE_CLAUDE.md)
- [FAQ & troubleshooting](docs/FAQ.md) · [Architecture](docs/ARCHITECTURE.md)

## Status

Early release. The Cloud profile (A) is the tested happy path; profiles B/C
are functional but less battle-tested. Roadmap: AI image descriptions for
figures (vision pass), automatic file naming, corpus overview modes
(coverage/clusters), optional knowledge-graph layer.

## License

[MIT](LICENSE)
