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

**The app container** — the worker inside that box. It watches your folder,
reads documents, and answers searches.

**Qdrant** — a *search database for meaning*. A normal database finds exact
words; Qdrant finds text that *means* something similar, even if it uses
different words. It's what lets you ask "rules for extra payments" and get a
passage that says "Nachtragsmanagement". It runs as a second small box next to
the app.

**Claude Desktop** — your interface. You don't open the app or the database;
you just talk to Claude, and Claude quietly uses them through a connection
called MCP.

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
