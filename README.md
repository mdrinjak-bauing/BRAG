# Academic RAG and Second Brain

**🇬🇧 English | 🇩🇪 [Deutsch](README.de.md)**  ·  **Version 0.2.0** ([changes](#versions))

**Your personal, searchable research knowledge base — talk to your document
corpus through Claude Desktop.**

Drop PDFs into a folder. They are automatically parsed (including tables and
figures, with AI image descriptions), enriched with AI-generated context, and indexed for hybrid
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

### What is Docker — and where do the ~3 GB live?

Docker is a kind of sealed mini-system. Instead of installing Python,
databases and AI libraries one by one (and fighting version conflicts), Docker
starts a ready-made box that already contains everything, identically on any
machine. You install Docker Desktop once; the project starts the rest. That is
what turns setup into "double-click and answer three questions" instead of a
page of commands.

Two of these boxes run side by side: the **app container** (reads documents,
answers searches) and **Qdrant** (the search database). On first launch Docker
downloads the program building blocks and the document-analysis AI models once
— about **3 GB** together. These files do not live in your project folder but
in Docker's own managed storage (the Docker image plus a named volume for the
database). You never touch them directly; uninstall Docker and they are gone.
Your `vault/` folder is completely untouched by all this — it holds only your
own files.

### Under the hood: the two pipelines

![Pipeline: ingest (parsing, chunking, contextual retrieval, embeddings, index) and query (prefetch, RRF fusion, cross-encoder reranking, cited answer)](docs/assets/pipeline.svg)

Answer quality comes from two workflows — one when a document is **ingested**,
and one on every **question**.

**On ingest**, the decisive step is *contextual retrieval*: an AI writes 1–2
sentences locating every chunk in the document's argument — terse academic
prose becomes findable. In parallel each chunk gets two "fingerprints": one for
**meaning** (the embedding, for semantic search) and one for **exact terms**
(for keyword search).

**On every question**, your query runs through this query pipeline — from the
question in Claude to the cited answer:

1. **Two searches at once.** The question runs in parallel through the
   *meaning search* (finds related passages even in different words —
   "rules for extra costs" hits "change-order management") and the *keyword
   search* (the BM25 method: finds exact terms where wording matters more than
   meaning — abbreviations, section numbers like § 71, proper names, file
   references). Each returns its best ~150 candidates.
2. **Merge (RRF).** The two hit lists are fused into one. Passages that *both*
   methods consider relevant rise to the top; about 80 candidates remain.
3. **Re-order — the reranker.** Why this step? The first two stages are fast
   but coarse: they measure similarity, not whether a passage actually
   *answers* the question. The reranker (a cross-encoder) reads your question
   together with each of the ~80 passages and scores the real fit. That is the
   difference between "contains the search terms" and "answers the question" —
   and the biggest lever for precision.
4. **Trim and mix.** The best hits remain (15 by default, at most 3 from the
   same source so a single book can't take every slot). This count is *top-K*.
5. **Answer.** Claude reads only these selected passages and writes the answer
   — every statement cited with source and page, one click opening the PDF at
   the exact spot.

Relevance scores are shown openly rather than hiding weak hits — you stay in
control of what you believe. Both quality stages — contextual retrieval on
ingest and the reranker on search — are on by default; every parameter is
documented in [`.env.example`](.env.example).

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

The profile chooses only the **text AI** (which writes chunk context, describes
figures and classifies documents). The **meaning-index (embeddings) always runs
locally** on your computer (arctic model, no GPU needed) — the same way the
re-ranker already does. So you can switch the AI provider below at any time
**without re-indexing your corpus.**

| Profile | Text AI provider | Cheapest model preset | Hardware | Doc text leaves machine |
|---|---|---|---|---|
| **Gemini** (default) | Google Gemini (free tier) | gemini-2.5-flash-lite | any laptop | yes (Google) |
| **OpenAI** | OpenAI / ChatGPT | gpt-4o-mini | any laptop | yes (OpenAI) |
| **Claude** | Anthropic Claude | claude-haiku-4-5 | any laptop | yes (Anthropic) |
| **Hybrid** | LM Studio (on your Mac) | your local model | Apple Silicon, 32 GB+ | no |
| **Local** | Ollama (on your machine) | llama3.1 | decent CPU, 16 GB+ | no |

With a cloud profile, the **text** of each chunk is sent to the provider to
generate context — and, with the vision pass on (the default), the **images of
your figures** too. Whole files and the embeddings are never sent. On the two
local profiles nothing leaves the machine at all.

> ⚠️ **Privacy note:** On the **free Gemini tier** (the default), Google may use
> the submitted text and images to improve its products, and they may be
> reviewed by humans. For confidential, personal or licensed content, choose a
> **local profile** or a paid tier (image upload is off with `VISION_ENABLED=false`).
> Details and the full legal notice: **[docs/LEGAL.md](docs/LEGAL.md)**.

Decision guide and model recommendations: [docs/PROFILES.md](docs/PROFILES.md).
**Note:** switching the AI provider needs no re-indexing. Only opting into
*cloud embeddings* (an advanced `.env` option for fast bulk ingest on weak
hardware) changes the index and triggers a one-time re-ingest — the system
handles this safely into a separate collection.

### Which model saves money?

You don't have to pick anything by hand — each cloud profile is already preset
to its **cheapest capable model**:

| Provider | Preset model | Why this one |
|---|---|---|
| Google Gemini | `gemini-2.5-flash-lite` | free tier, **no** daily cap for bulk ingest |
| OpenAI / ChatGPT | `gpt-4o-mini` | cheapest capable OpenAI chat model |
| Anthropic / Claude | `claude-haiku-4-5` | cheapest Claude model |

What matters for the bill: the **text excerpt of each chunk** is sent to the
provider for context generation (plus your figure images when the vision pass is
on) — never whole files, never the embeddings, and never your later questions
(Claude Desktop answers those separately). For a
typical corpus that keeps the cost in the **cents range**. If you deliberately
want a stronger (pricier) model, set it as `LLM_MODEL` in `.env` — e.g.
`gemini-2.5-flash` for a bit more quality (capped at 10,000 requests/day, so
best used *after* the initial bulk ingest). Money-saving tip: bulk ingest is
the only step that generates many requests. Ingest with the cheap model and, if
needed, switch to a stronger one for individual tasks afterwards.

### The meaning index (embeddings) and your hardware

Don't confuse two kinds of model here:

- The **text AI** (the LLM in the table above) writes the context. *It* depends
  on the provider and cost (cloud) or on your hardware (local).
- The **meaning index** — the *embedding model* — turns each chunk into a
  searchable vector. You **don't choose** it: every profile automatically uses
  the local model **arctic** (`snowflake-arctic-embed-l-v2.0`, 1024 dimensions)
  — on the CPU, **no GPU**, on any laptop. It downloads ~2.3 GB into the model
  cache once and is free afterwards; your document vectors never leave the
  machine.

**Do I need strong hardware?** Not for embeddings — arctic runs anywhere on
CPU. Capable hardware is only needed if you want to run the **text AI locally**
(Hybrid/Local profiles): rules of thumb — LM Studio on an Apple Silicon Mac
with `qwen2.5-14b-instruct` from 32 GB RAM, `gemma-3-27b-it` from 64 GB; Ollama
needs 16 GB (default model `llama3.1`), and a GPU helps a lot.

**When is a different embedding model worth it?** Only in one case: weak
hardware *and* a very large corpus where local ingest is too slow. Then you can
switch in `.env` to a **cloud embedding** (`gemini-embedding-001`, 3072 dims,
or OpenAI `text-embedding-3-small`, 1536) — noticeably faster for bulk ingest.
The price: document vectors are then computed at the provider (so they leave the
machine), and this is the **only** change that triggers a one-time re-ingest
(safely into a separate collection). For almost everyone arctic is the right
choice; details in [docs/PROFILES.md](docs/PROFILES.md).

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
- ⚖️ [Legal notices (privacy, copyright)](docs/LEGAL.md)

## Versions

Current version: **0.2.0** (June 2026). The full list of changes lives in
[CHANGELOG.md](CHANGELOG.md).

- **0.2.0** — Added **OpenAI/ChatGPT** and **Anthropic/Claude** as cloud
  providers alongside Google Gemini; the setup wizard is bilingual (EN/DE); the
  meaning index (arctic) now runs locally in **every** profile, so switching
  provider no longer requires re-indexing; this guide was reworked — full query
  pipeline plus new sections on Docker, cost and hardware. Also new: the
  **vision pass** — figures are described by a multimodal model so they become
  findable by content (on by default, disable with `VISION_ENABLED=false`).
- **0.1.0** — Initial release: Google Gemini cloud profile, hybrid search with
  reranking, the vault structure and the search MCP for Claude Desktop.

## Status

Early release (0.2.0). The **Gemini profile** is the tested happy path; the
other profiles are functional but less battle-tested. Roadmap: automatic file
naming, corpus overview modes (coverage/clusters), optional knowledge-graph
layer.

## License

[MIT](LICENSE)
