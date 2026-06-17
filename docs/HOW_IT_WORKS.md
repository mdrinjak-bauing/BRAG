# How it works — in plain words

**🇬🇧 English | 🇩🇪 [Deutsch](HOW_IT_WORKS.de.md)**

No computer-science background needed. This page explains what happens on your
machine, where your data lives, and how a question becomes a cited answer.

---

## The pieces, and why each one exists

**Docker** — think of it as a sealed appliance. Instead of you installing
Python, databases and AI libraries by hand (and fighting version conflicts),
Docker runs a ready-made box that already contains everything, identically on
every computer. You install Docker once; it runs the rest. That's why setup is
"double-click and answer three questions" instead of a page of commands.

Two "appliances" run side by side inside that box:

**1. The app container** (`asb-app`) — the actual worker. You never start it by
hand; it bundles several small subsystems:

- **The watcher** — the lookout. Every ~10 seconds it checks your `sources/`
  folder: anything new? renamed or deleted? Accordingly it triggers ingest or
  cleans up the index. So you never "import" anything — dropping in a file is
  enough, the watcher notices on its own.
- **The ingest pipeline** — processes a newly spotted document: read, cut,
  enrich with context, embed, store (details below).
- **Search** — answers every question from Claude (two searches + reranker, see
  below).
- **The HTTP bridge** — a tiny web server on `localhost:8765`. It's what makes
  the links in answers open your PDF in the browser at the exact cited page.
- **The MCP server** — the speaking link to Claude Desktop. Whenever Claude
  searches, a short-lived process spins up in this container, fetches the
  results and hands them back.

**2. Qdrant** (`asb-qdrant`) — a *search database for meaning*. A normal
database finds exact words; Qdrant finds text that *means* something similar,
even if it uses different words. It's what lets you ask "rules for extra
payments" and get a passage that says "Nachtragsmanagement". It runs as a second
small box next to the app.

**Claude Desktop** — your interface, running normally on your machine (not in
Docker). You don't open the app or the database; you just talk to Claude, and
Claude quietly uses them through a connection called MCP.

---

## Where does this get installed on my computer?

There are **two** places — and it really helps to keep them apart:

**1. The project folder — the one you created yourself.** When you unpacked the
ZIP from GitHub, a folder appeared exactly where you unpacked it (e.g.
`~/academic-rag-and-second-brain` on a Mac or
`C:\Users\<you>\academic-rag-and-second-brain` on Windows). It holds: the setup
files, the `docker-compose.yml`, your settings file `.env`, and by default the
`vault/` folder with your documents. You can see, back up and move this folder —
it's yours.

**2. Docker's own storage — which you never touch directly.** On first launch
Docker downloads the program code and the AI models (~3 GB together) and puts
them in its own managed area — *not* in your project folder. The Qdrant database
lives there too (as a "named volume"). That's deliberate: the database never
ends up in iCloud/OneDrive (where it would get corrupted), and the 3 GB of
models don't clutter your project folder. Uninstall Docker and this area is
gone — your project folder and vault stay untouched.

In short: **your files live in the project folder (visible, yours); the running
system and the search index live in Docker (invisible, managed automatically).**

To check everything is running, open a terminal in the project folder and type
`docker ps` — you should see the two boxes `asb-app` and `asb-qdrant`.

---

## Where your things live

| What | Where | Notes |
|---|---|---|
| Your documents & notes | the `vault/` folder on your computer | plain PDF and Markdown files — yours, back them up like any folder |
| The search index (Qdrant) | inside Docker, in a managed storage area | rebuildable anytime from your vault; never put it in iCloud/OneDrive |
| The program code & AI models | inside the Docker image | downloaded once at first build (~3 GB); you never touch it |
| Your settings & API key | the `.env` file in the project folder | written by the setup assistant; never shared |

The important point: **your library (`sources/`) and your notebook (`wiki/`,
`notes/`) are normal files you own.** The database is just a derived index — if
it were ever lost, the system rebuilds it from your files.

---

## What happens when you drop in a document (ingest)

You drop a PDF into `vault/sources/`. Within seconds the app notices it and
runs five steps:

1. **Read the layout — "Docling".** Docling is the tool that *understands the
   page*: it separates headings, paragraphs, tables and figures, and remembers
   which page each piece came from. (That page memory is what later lets every
   answer link to the exact page.)

2. **Cut into chunks.** A whole book is too big to search as one lump, so it's
   cut into bite-sized passages. Tables are kept whole (with their header
   repeated if they're long) so numbers don't get split apart.

3. **Add context — "contextual retrieval".** This is the quality trick. On its
   own, a passage like *"the rate was 12%"* is useless — 12% of what? So the AI
   writes one or two sentences of context for each chunk ("This is from the
   chapter on rework costs, discussing…") and stores it alongside. Now a search
   can actually find it. This single step is the biggest reason answers are
   good.

4. **Make two "fingerprints".** Each passage gets a *meaning fingerprint* (for
   the similar-meaning search) and a *keyword fingerprint* (for exact terms like
   GEG or § 71). Having both is why the system finds things whether you remember
   the exact word or only the idea.

5. **File it in Qdrant** + write a short literature note in `notes/`.

### What about figures?

Important to know: the **image content is not looked at** (yet). On ingest,
Docling detects each figure and takes its **caption** plus the chapter it sits
in — that text becomes a searchable "figure" chunk. So you find a figure through
its caption and context, **not** through what the image actually shows. If a
figure has no caption, only its position is recorded ("No caption available").

This is deliberate: an AI "describing" an **unseen** image would be guessing —
and an invented description would permanently poison the index. So for figures
the context AI gets a deliberately honest task: only locate the figure in its
chapter, **never** invent its content.

A true **vision model** that actually looks at and describes the images
(diagrams, charts, photos) is planned (see the roadmap) but not active yet.

A short paper takes 1–3 minutes; a book, longer. You don't wait — it happens in
the background, and a removed file is cleaned out of the index automatically.

---

## What happens when you ask a question (search)

You ask Claude something. Behind the scenes:

1. **Two searches at once.** Your question is run through *both* the
   meaning-search and the keyword-search. Each returns its best ~150 candidates.

2. **Merge.** The two candidate lists are fused into one (a step called RRF) —
   passages that both methods liked rise to the top. About 80 survive.

3. **Re-rank — the precision step.** A second, more careful AI (the
   "re-ranker") reads your actual question *together with* each of those 80
   passages and re-orders them by how well they truly answer it. This is the
   difference between "contains the words" and "actually answers the question".

4. **Trim and diversify.** The top results are kept (by default 15, at most 3
   from any single source so one book can't crowd out the rest). This "how many
   to keep" number is the **top-K**.

5. **Answer.** Claude reads those passages and writes an answer — citing each
   source with its page, and a link that opens the PDF right there.

The system shows you *why* each hit was chosen (a relevance score) rather than
hiding weak matches — so you stay in control of what to trust.

---

## In one sentence

You keep plain files in a folder; the app quietly turns them into a
meaning-aware index; and Claude answers your questions out of *your* documents,
with page-exact receipts — all on your own computer.

See also: [Architecture diagram & defaults](ARCHITECTURE.md) ·
[Backend profiles](PROFILES.md)
