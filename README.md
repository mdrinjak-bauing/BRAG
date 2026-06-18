![BRAG — talk to your own sources, with every answer cited](docs/assets/header.en.svg)

# BRAG — Building Retrieval-Augmented Generation

**🇬🇧 English | 🇩🇪 [Deutsch](README.de.md)**  ·  **Version 0.3.1** ([changes](#versions))

> **Your own AI assistant — one that knows your knowledge.** Put your documents
> — PDFs, Word, PowerPoint, your notes — in a folder. Claude or ChatGPT **pulls
> the right passages itself**
> (page-precise citations, one click to the original) and **writes what you
> discuss back as a note** into the same folder. Your knowledge lives with
> *you* — not in the chat history: every new chat, even on a different provider,
> picks up right where you left off. Local, provider-independent, yours.

The name **BRAG** stands for *Building Retrieval-Augmented Generation* — a play
on my field (civil engineering) and on what it does: it **builds up** your
knowledge and retrieves it on demand. Under the hood, a **hybrid search**
(meaning + keyword, with reranking) makes sure the AI finds the *relevant*
passages — not just any. How that works in detail is further down.

A "second brain" isn't a new idea. What I tried to do here is make a version
that holds up day to day — no hype, no lock-in, just plain files that you own. I
use it myself every day and I think it adapts well to other kinds of work, but
that's really for you to judge: I'd genuinely welcome feedback, criticism, and
anyone who wants to try it out.

**Who is it for?** Researchers, lecturers and PhD students — and just as much
practitioners who need to stay on top of standards, reports, bills of quantities
and trade literature in everyday project work. **No programming required.**

---

![From PDF to cited answer: drop a document into sources, it is indexed, you ask Claude, you get a page-cited answer](docs/assets/flow.en.svg)

## What you do with it

- 🔎 **Find instead of leaf through** — *"What does my corpus say about
  change-order management?"* Answer with a page citation, one click opens the
  PDF right there.
- 📊 **Pull numbers & tables** — *"Find tables with cost figures on rework"* —
  figures are described by content too, so they're findable.
- ✍️ **Write with citations** — collect quotable passages while reading, then
  *"draft the paragraph from these passages, keep the citations."*
- 🎓 **Prep teaching** — *"Draft three exam questions from chapter 4, with page
  references."*
- 🧠 **Capture thinking** — results land as a note in your knowledge store; a fresh chat
  days later picks up exactly where the last one stopped.
- 🗂️ **Filter by project/course** — *"Search **only in the School Center
  project**: which position covers the earthworks?"*

The core idea: **chats forget — your knowledge store doesn't.** Knowledge accumulates in
your files, not in a throwaway chat log.

## Setup — realistically about an hour

There's little active work; the time is almost all **downloads** (Docker
Desktop, Claude Desktop, and the ~3 GB of analysis models on first run). It runs
on a **normal computer** — with a cloud profile (the default) about **8 GB of
RAM** is plenty and any modern CPU will do; you only need a strong machine if you
also run the *text* AI locally (see the profile table below).

**You need** (all free): [Docker Desktop](https://www.docker.com/products/docker-desktop/),
[Claude Desktop](https://claude.com/download) and an API key — easiest is
[Gemini](https://aistudio.google.com/apikey) (free tier); or
[OpenAI](https://platform.openai.com/api-keys) / [Anthropic](https://console.anthropic.com/).
Prefer fully local? That works too — with [LM Studio](https://lmstudio.ai) or
[Ollama](https://ollama.com).

1. **Download:** green "Code" button → "Download ZIP" → unpack.
2. **Double-click** `setup.command` (Mac) or `setup.bat` (Windows). The
   assistant opens **in your browser** and asks, in plain language: where the AI
   should run, your key (with a live check), your document language. It writes
   the whole configuration itself — **you never edit a file.**
3. **Quit Claude Desktop completely** (Cmd+Q / tray → Quit) and reopen it.
4. **Drop a PDF into `wissensspeicher/sources/`** — indexed automatically within seconds.
5. Ask Claude: *"What documents are in my knowledge base?"*

**Everything working?** Double-click `status.command` (Mac) / `status.bat`
(Windows) for a one-click check of Docker, Qdrant, the watcher, the corpus and
the AI connection — ✓/✗ per item.

**Something off?** Start with the [FAQ & troubleshooting](docs/FAQ.md) — it
covers the common cases. If it looks like a real bug, please [open a GitHub
issue](../../issues) with your OS, the profile you use, what you did and what
happened, plus the status output above (details in
[CONTRIBUTING](CONTRIBUTING.md)).

First run downloads ~3 GB of analysis models once. Detailed, with "what you
see": [Install macOS](docs/INSTALL_MAC.md) · [Windows](docs/INSTALL_WINDOWS.md).

## The idea: a library and a notebook

A research "second brain" has two halves — and keeping them strictly apart is
the heart of the design:

|  | 📚 **Your library** | 📓 **Your notebook** |
|---|---|---|
| Folder | `wissensspeicher/sources/` | `wissensspeicher/wiki/`, `wissensspeicher/notes/` |
| Contains | external sources: papers, books, reports | **your own thinking**: concepts, drafts, reading notes |
| Searchable by Claude? | yes — hybrid search with page-precise citations | deliberately **no** |
| Claude can read/write it? | read-only (via search) | yes — via the optional Obsidian connection |

**Plus a third, in-between layer — saved passages.** When you tell Claude
*"save this passage,"* it writes the quote (with its source and page) into
`wissensspeicher/passages/` **and indexes it** — so any later chat, even with a
different AI provider, finds it again via `search`, clearly marked as *your
saved passage*. This is curated evidence you chose to keep (a real quote from a
real source), not the AI's own output — which is exactly why it is searchable
while the rest of the notebook is not.

**Why is the rest of the notebook excluded from the index?** The echo effect:
if your own concept notes and auto-summaries were indexed, you'd one day "find"
your own summary of a paper and cite it as evidence — without noticing you're
quoting yourself. The library answers *"what do my sources say?"*; the notebook
holds *what you make of it*. Claude works with both, but never confuses one for
the other.

### Your notebook — and why plain Markdown files

The notebook (`wiki/`) is the part that turns search into a *second brain*: this
is **your** thinking — concept pages, lines of argument, open questions,
decisions. Not what the sources say, but what *you* make of it.

**Why plain Markdown (`.md`) files?** Markdown is just text with a few
characters for headings, lists and links. Sounds unremarkable — but it's the
decisive advantage:

- **It's yours and it lasts.** You can open a `.md` file in 20 years, in any
  editor, with no special program and no subscription. No proprietary format, no
  vendor that can shut down — no lock-in.
- **It runs everywhere.** The same file is read and written by Obsidian, Claude,
  your text editor, your backup, Git. Move, copy, back it up like any other file.
- **It links up.** With `[[wikilinks]]` you connect concepts into a network —
  your knowledge becomes walkable instead of buried in documents.

**The uncomfortable part:** a second brain doesn't build itself — you have to
**make documenting a habit.** The sources accumulate automatically; your
insights don't. Rule of thumb: after a good conversation with Claude or an
important passage, **jot down what stuck** — three rough sentences beat the
perfect note that never gets written. Claude can help you write (via the
Obsidian connection). Over time this becomes what no chat log ever can: **your**
growing, searchable knowledge.

## How it works

![Architecture: knowledge store, Docker containers, Claude Desktop and the two MCP connections](docs/assets/architecture.svg)

Everything runs in two Docker containers on your machine. In a cloud profile an
AI provider only processes document text; in the local profiles nothing leaves
your computer. A thorough, jargon-free explanation lives in
**[How it works](docs/HOW_IT_WORKS.md)** — here's the gist.

**What is Docker?** Instead of installing Python, databases and AI libraries by
hand (and fighting version conflicts), Docker runs a ready-made box that is
identical on every machine. You install Docker Desktop once; the project starts
the rest. The ~3 GB of models live in Docker's managed storage — **not** in your
project folder; your `wissensspeicher/` holds only your own files.

![Pipeline: ingest and query](docs/assets/pipeline.svg)

Answer quality comes from two workflows:

**On ingest**, an AI writes 1–2 anchoring sentences for each text chunk
(*contextual retrieval*) — terse trade prose becomes findable in the first
place. Figures are described by a multimodal model (*vision pass*). Each chunk
gets two "fingerprints": one for **meaning** (semantic search) and one for
**exact terms** (keyword search).

**On every question** the query pipeline runs — from question to evidence:

1. **Two searches at once** — meaning search (finds related things, even in
   different words) **and** keyword search (BM25; finds exact terms like
   abbreviations, section numbers, file references). ~60 candidates each.
2. **Merge (RRF)** — both lists fuse; ~40 remain.
3. **Reranker** — a cross-encoder reads your question together with each passage
   and sorts by true fit. The difference between "contains the search terms" and
   "answers the question". It runs **locally on your CPU** — the main cost of a
   search — so its effort is a setting: `RERANK_PROFILE=off/eco/balanced/full`
   (default `eco`; pick `off`/`eco` on a weak PC, `full` on a strong one).
4. **Trim** — the best hits remain (15 by default, max 3 per source).
5. **Answer** — Claude writes from exactly these passages, every statement cited
   with source and page.

More depth (with numbers) in [How it works](docs/HOW_IT_WORKS.md) and
[Architecture](docs/ARCHITECTURE.md); every parameter in [`.env.example`](.env.example).

## The two Claude connections (MCP)

Claude Desktop talks to your second brain through two MCP servers:

**1. The search connection** (this project — set up automatically) gives Claude
these tools:

| Tool | What it does | Example question |
|---|---|---|
| `search` | Hybrid search with filters (type, year, tables/figures only, source) | *"What does my corpus say about change-order management?"* |
| `list_sources` | Inventory of all indexed documents | *"What documents are in my knowledge base?"* |
| `inspect_chunks` | Shows what is stored for a source (diagnostics) | *"Show what was indexed from Smith 2023, p. 14."* |
| `save_passage` | Saves a quotable hit under a topic | *"Save this quote for my methods chapter."* |
| `list_passages` | Shows collected passages per topic | *"What have I collected for the methods chapter?"* |

**2. The notebook connection** (optional, ~5 minutes) lets Claude also read and
extend your notes via the **MCP Tools for Obsidian** plugin, while the search
index stays untouched. Guide: [docs/OBSIDIAN.md](docs/OBSIDIAN.md).

With both: *"Search definitions of process maturity (library), compare with my
concept note (notebook), and fill in what's missing — with citations."*

## Choose your profile

The profile only picks the **text AI** (writing context, describing figures,
classifying). The **meaning index (embeddings) always runs locally** (arctic
model, no GPU needed) — so you can switch provider any time **without
re-indexing.**

| Profile | Text AI | Cheapest model | Hardware | Data leaves machine |
|---|---|---|---|---|
| **Gemini** (default) | Google Gemini (free tier) | gemini-2.5-flash-lite | any laptop | yes (Google) |
| **OpenAI** | OpenAI / ChatGPT | gpt-4o-mini | any laptop | yes (OpenAI) |
| **Claude** | Anthropic Claude | claude-haiku-4-5 | any laptop | yes (Anthropic) |
| **Hybrid** | LM Studio (on your Mac) | your local model | Apple Silicon, 32 GB+ | no |
| **Local** | Ollama (on your machine) | llama3.1 | decent CPU, 16 GB+ | no |

With a cloud profile the **text excerpt** of each chunk goes to the provider —
plus, with the vision pass on (the default), the **images of your figures**.
Whole files and the embeddings are never sent. With local profiles nothing
leaves the machine.

> ⚠️ **Privacy, short and honest:** On the **free Gemini tier** (default) Google
> may use the submitted text/images. Rule of thumb: what you wouldn't have shown
> Claude doesn't go up here either. For confidential or personal material use a
> **local profile** (nothing leaves the machine) or turn off image upload with
> `VISION_ENABLED=false`. And if you want it elegant, build an anonymizer as an
> add-on tool (see [Extension](#extension--automation-with-claude-code--co)).
> More under [Legal & privacy](#legal--privacy).

**Cost:** each profile is preset to its cheapest capable model; for a typical
corpus the cost stays in the **cents range**. **Hardware:** you only need
strong hardware for a *local* text AI — embeddings run on CPU everywhere.
Details, model recommendations and the cloud-embedding opt-in:
[docs/PROFILES.md](docs/PROFILES.md).

## Your knowledge store

Here's the most important distinction — **two folders, two roles:**

- **The project folder** = the **program** (the unpacked ZIP). You need it to
  start/stop the app; **don't delete it.** *Where* it lives doesn't matter
  (your work/project directory, OneDrive …) — just keep it.
- **Your knowledge store** = your **content**. By default that's the
  `wissensspeicher/` subfolder *inside* the project folder. During setup you can
  instead point it at an **existing folder** — e.g. your current "Project XY"
  folder — and grant access to it.

**The one rule that explains everything:** exactly **this one folder** is
searched. Anything you put in `sources/` is automatically added to the search
database (the index); take a file back out or delete it and it disappears from
the database too. Nothing else on your computer is touched.

This is how the knowledge store is laid out:

```
wissensspeicher/
├── CLAUDE.md      ← teaches Claude about YOUR research — fill it in!
├── AGENTS.md      ← extra rules for autonomous agent tasks
├── sources/       ← 📚 drop documents here (PDF, DOCX); subfolders = document types
│   └── _inbox/    ← staging area, ignored by the indexer
├── notes/         ← auto-generated literature note per source
├── passages/      ← quotes you saved via Claude, grouped by topic
└── wiki/          ← 📓 your own thinking — never indexed
```

Renaming or deleting in `sources/` is handled automatically: renaming an
**already-indexed** file just updates its metadata (author, year, type, PDF
path) in place — **no re-ingest** (no re-embedding, no API cost); deleting it
removes it from the database. Subfolder names become the filterable document
type (`sources/papers/`, `sources/reports/` …).

**Your own metadata** (project, course, client …) goes into a `_meta.txt` in any
folder under `sources/` — one `key: value` per line:

```
# sources/projects/School_Center/_meta.txt
project: School Center
client: City of Hamm
```

Every document in that folder carries these fields; Claude filters by them in a
conversation, so hits from other projects don't bleed into your results.

**Book page vs. PDF page.** If a document's printed page numbers don't match the
PDF's physical pages (a book with front matter, a journal offprint), add a
`page_offset` — then citations show the *printed* page while the link still
opens the right PDF page. The rule is `page_offset = physical PDF page − printed
page` (look at any page: if PDF page 28 shows printed "14", the offset is 14):

```
# sources/books/Mueller_2021/_meta.txt
page_offset: 14
```

Set it before indexing the document, or re-drop the file afterwards so it is
re-indexed with the offset.

### Obsidian: a nicer view of the same folder

You can open the knowledge store with [Obsidian](https://obsidian.md) (free) —
it renders the Markdown files far more nicely and makes writing in the notebook
pleasant. Important to understand: **Obsidian is not a second copy, just a view
onto the exact same folder.** It works directly on the files — **delete a file
in Obsidian and it's gone from the normal folder (and the index) too.** Nothing
is imported or copied; it's the same structure, just nicer to work with.
Step by step: [docs/OBSIDIAN.md](docs/OBSIDIAN.md).

## Day to day: how your knowledge grows

**New literature arrives:** drop it into `sources/` → indexed in minutes →
*"What does this add to what I have on rework costs? Does it contradict Müller
2021?"* — answer with page-linked citations.

**Developing an idea:** *"What do my sources say about maturity models? Where do
they disagree?"* → write the result as a concept note in `wiki/` → days later,
in a fresh chat, continue exactly there.

**While writing:** collect quotable passages per topic, then have the paragraph
drafted from them — citations preserved.

**Let Claude grow with you:** whenever you correct Claude twice about the same
thing, that correction belongs in **`wissensspeicher/CLAUDE.md`**, not in the next chat. A
well-kept instruction file turns a generic assistant into *yours* — examples:
[docs/CUSTOMIZE_CLAUDE.md](docs/CUSTOMIZE_CLAUDE.md).

## Extension & automation (with Claude Code & co.)

The foundation is deliberately open: plain files, small readable Python modules,
Docker, and **MCP** — the same open standard Claude uses to reach its tools.
That makes this a **base to build on**, not a closed app. With **Claude Code** or
another coding agent you can have the code read, add new tools and automate
workflows — the [architecture](docs/ARCHITECTURE.md) is documented for exactly
that.

Possible directions (open architecture, not yet built in):

- **Connect more data sources** — email and calendar, cloud storage, reference
  managers (e.g. Zotero), websites/feeds: as extra sources or as their own MCP
  tools Claude uses in the same conversation.
- **Integrate professional software** — project-specific connections to the
  programs in your field (e.g. cost-estimation/ERP/document-management systems),
  so Claude can look things up there or prepare entries.
- **Automations** — automatic file naming, periodic summaries of new sources,
  watcher-triggered reports, scheduled tasks via agent sessions (rules in
  `wissensspeicher/AGENTS.md`).

A coding agent can implement exactly these extensions step by step — a new MCP
tool here, an extra pipeline stage there. If you build in this direction,
contributions back are very welcome.

## Legal & privacy

Short version — details and the full notice: **[docs/LEGAL.md](docs/LEGAL.md)**.

- **No warranty.** Open source under [MIT](LICENSE), "as is", with no guarantee
  of data protection or legal compliance. Use at your own responsibility.
- **Verify AI output.** AI-generated answers and citations can be incorrect or
  fabricated; always verify them against the linked original page before relying
  on or citing them.
- **Your API key stays local.** It's stored only in a local `.env` file on your
  computer (owner-readable only) and is used solely to authenticate your own
  requests to the provider you chose — never sent to the makers of this app or
  any third party. Local profiles need no key at all.
- **Privacy — the honest rule of thumb.** Local profiles: nothing leaves the
  machine. Cloud profiles: text excerpts (and figure images with vision) go to
  the provider, and the **free Gemini tier** may use them. So: what you wouldn't
  have shown Claude doesn't belong in the cloud here either — personal or
  confidential material runs on a **local profile** (build an anonymizer in
  front if you like). If your documents contain personal data, in the cloud case
  you are generally the GDPR controller.
- **Professional use.** In a company or public body — especially with personal
  data — clear it up front with the responsible bodies (data protection officer,
  IT security, works council where applicable). From a data-security standpoint
  **local profiles are clearly preferable**; IT departments can harden BRAG for
  organizational use.
- **Copyright.** Sure, technically you can put anything in the folder — but you
  are responsible for the rights to your sources. Your own scientific analysis
  of lawfully accessible works may fall under the text-and-data-mining
  exceptions; licence terms can restrict it. For licensed or confidential works
  the answer is simple: local profile, and everything stays on your machine.

*Not legal advice (as of June 2026). When in doubt, get qualified advice.*

## Documentation

- **[How it works — in plain words](docs/HOW_IT_WORKS.md)** (no tech background needed)
- [Install on macOS](docs/INSTALL_MAC.md) · [Install on Windows](docs/INSTALL_WINDOWS.md)
- [Backend profiles](docs/PROFILES.md) · [Connect Obsidian + notebook MCP](docs/OBSIDIAN.md)
- [Customize Claude for your work](docs/CUSTOMIZE_CLAUDE.md)
- [Which Claude surface? Chat, Cowork or Code](docs/WHICH_CLAUDE.md)
- [FAQ & troubleshooting](docs/FAQ.md) · [Architecture](docs/ARCHITECTURE.md)
- ⚖️ [Legal notices (privacy, copyright)](docs/LEGAL.md)

## Versions

Current version: **0.3.0** (June 2026). Full list: [CHANGELOG.md](CHANGELOG.md).

- **0.3.0** — Renamed the project to **BRAG** (*Building Retrieval-Augmented
  Generation*) end to end — package, Docker image and containers included (no
  indexed data is lost; **existing installs re-run the setup once**, see
  [CHANGELOG](CHANGELOG.md)). **One-click status check** (Docker, Qdrant,
  watcher, corpus, AI backend, Claude connection). **Renaming an indexed file**
  is now a lightweight metadata update instead of a full re-ingest. Security
  hardening of the setup bridge (Host-header allowlist, download-only static
  files, atomic config writes). Knowledge-store folder renamed `vault/` →
  `wissensspeicher/`. New doc: which Claude surface to use (Chat / Cowork / Code).
- **0.2.0** — Added **OpenAI/ChatGPT** and **Anthropic/Claude** alongside Google
  Gemini. Bilingual setup wizard. The meaning index (arctic) runs locally in
  **every** profile (switch provider without re-indexing). Reworked guide (query
  pipeline, Docker, cost, hardware, legal). New: the **vision pass** — figures
  are described by content (on by default, disable with `VISION_ENABLED=false`).
- **0.1.0** — Initial release: Gemini cloud profile, hybrid search with
  reranking, the knowledge store structure and the search MCP for Claude Desktop.

## Status

Early release (0.3.0). The **Gemini profile** is the tested happy path; the
other profiles work but are less battle-tested. Roadmap: automatic file naming,
corpus overview modes (coverage/clusters), optional knowledge-graph layer — and
the integrations sketched above.

## License

[MIT](LICENSE). Third-party models and dependencies (each under its own
license) are listed in [NOTICE.md](NOTICE.md).
