# Academic RAG and Second Brain

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

Everything runs in two Docker containers on your machine. In the recommended
Cloud profile, document text is processed by Google's free Gemini API; in the
local profiles, nothing leaves your computer (see [Profiles](#choose-your-profile)).

### Under the hood: the two pipelines

![Pipeline: ingest (parsing, chunking, contextual retrieval, embeddings, index) and query (prefetch, RRF fusion, cross-encoder reranking, cited answer)](docs/assets/pipeline.svg)

Two stages do the heavy lifting for answer quality: **contextual retrieval**
during indexing (an AI writes 1–2 sentences locating every chunk in the
document's argument — terse academic prose becomes findable) and the
**cross-encoder reranker** during search (it reads your question together
with each candidate passage and re-orders by true fit, not just similarity).
Both are on by default; every parameter is documented in
[`.env.example`](.env.example).

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

### Your own metadata (projects, courses, clients …)

The built-in metadata — author, year, type, chapter, page — is derived
automatically. For everything **only you can know** — which construction
project a bill of quantities belongs to, which course and semester a lecture
script is for — put a `_meta.txt` file into any folder under `sources/`:

```
# sources/projects/School_Center/_meta.txt
project: School Center
client: City of Hamm
```

One `key: value` per line, nothing else to learn. Every document in that
folder (and its subfolders) carries these fields; deeper folders can add or
override fields. In a conversation, Claude filters by them:

> *"Search **only in the School Center project**: which position covers the
> earthworks?"*

— without that filter, hits from other projects would mix into the results.
The same mechanism can correct `author`, `year` or `doc_type` when a
filename can't express them. Note: `_meta.txt` is read at indexing time —
after changing it, move a document out of the folder and back in to refresh
its entry.

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free)
- [Claude Desktop](https://claude.com/download) (free)
- A cloud profile: an API key from your provider — [Gemini](https://aistudio.google.com/apikey) (free tier), [OpenAI](https://platform.openai.com/api-keys), or [Anthropic](https://console.anthropic.com/)
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

Pick where the AI runs. The setup assistant walks you through it.

| Profile | AI provider | Cheapest model preset | Hardware | Docs leave machine |
|---|---|---|---|---|
| **Gemini** (default) | Google Gemini (free tier) | gemini-2.5-flash-lite | any laptop | yes (Google) |
| **OpenAI** | OpenAI / ChatGPT | gpt-4o-mini + text-embedding-3-small | any laptop | yes (OpenAI) |
| **Claude** | Anthropic Claude | claude-haiku-4-5 (+ local embeddings*) | any laptop | yes (Anthropic) |
| **Hybrid** | LM Studio (on your Mac) | your local model | Apple Silicon, 32 GB+ | no |
| **Local** | Ollama (on your machine) | nomic-embed-text + llama3.1 | decent CPU, 16 GB+ | no |

\* Anthropic offers no embedding service, so the Claude profile builds the
meaning-index locally on your computer (no GPU needed) while Claude Haiku does
the text work.

Decision guide and model recommendations: [docs/PROFILES.md](docs/PROFILES.md).
**Note:** switching profiles later requires re-indexing (different embedding
models are mathematically incompatible — the system handles this safely, but
the work runs again).

## Day-to-day knowledge work

The principle behind everything: **chats forget — your vault doesn't.**
A conversation with Claude is gone when the window closes. So every
conversation that produces something worth keeping deposits it *into the
vault* — as a saved passage, a literature note, a concept page — and every
future conversation can pick it up from there. Knowledge accumulates in
your files, which you own, version and back up; the chat is just the
workbench.

**When new literature arrives** — a paper from a colleague, a book chapter,
an industry report:

1. Drop it into `sources/` → indexed within minutes.
2. *"What does this add to what I already have on rework costs? Does it
   contradict Müller 2021? Compare them."* — answers come with page-linked
   citations; one click opens the PDF at the right spot.
3. Reuse it anywhere: *"Draft three exam questions from chapter 4, with
   page references"* (teaching), *"Summarize the method for my related-work
   section"* (writing), *"Is this worth a deep read for my project?"* (triage).

**When you develop an idea** — the loop that makes it a *second brain*:

1. Brainstorm grounded in your corpus: *"What do my sources say about
   maturity models? Where do they disagree? What's missing?"*
2. Keep the result: *"Write this up as a concept note in `wiki/`, with the
   open questions at the end."* (via the notebook connection — or paste it
   into Obsidian yourself)
3. Days later, in a **fresh chat**: *"Open my concept note on maturity
   models — let's continue with open question 2."* The new conversation
   starts exactly where the old one ended.

**When you write:**

- While reading, collect quotable passages per topic: *"Save this quote for
  the quality-costs chapter."* → `passages/quality_costs.md`
- When drafting: *"What have I collected on quality costs? Draft the
  paragraph from those passages, keep the citations."*

### Keep Claude's instructions growing

The third pillar next to library and notebook: **`vault/CLAUDE.md`** (and
the project instructions in Claude Desktop). It tells Claude who you are,
how to search your corpus, and how to cite — and it should grow with you.
Rule of thumb: whenever you correct Claude twice about the same thing, that
correction belongs in CLAUDE.md, not in the next chat. A well-maintained
instruction file is what turns a generic assistant into *your* assistant —
guide with examples: [docs/CUSTOMIZE_CLAUDE.md](docs/CUSTOMIZE_CLAUDE.md).

## Documentation

- **[How it works — in plain words](docs/HOW_IT_WORKS.md)** (no tech background needed)
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
