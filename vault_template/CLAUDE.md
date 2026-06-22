# My knowledge store — Instructions for Claude

<!-- This file teaches Claude how to work with YOUR research. HOW it reaches Claude:
- Claude Code reads it from the folder automatically.
- Claude Desktop does NOT — create a Project and paste this file's content into the
  Project's custom instructions.
- LM Studio does NOT — paste this content into its system-prompt field.
Only THIS file needs pasting; everything else (your notes, your workflows) Claude
fetches on demand through the BRAG tools. Fill in the placeholders — concrete beats
generic — and keep it updated: whenever you correct Claude twice about the same
thing, the correction belongs in here. -->

## Who I am and what I research

<!-- Example: "I am a professor of structural engineering at X University.
My current focus is fatigue behavior of welded joints. I supervise 4 PhD students." -->

(your field, institution, current projects)

## My knowledge-store layout

- The **project folder itself is my searchable corpus** — my **immutable knowledge
  base**. I drop documents (PDFs, DOCX) straight in, any subfolder at any depth, and
  everything is indexed. **Read-only — never edit or move corpus files.** The first
  subfolder level names the document type (e.g. `papers/`, `reports/`).
- `WissensWIKI/` is my workspace. **Nothing under it is indexed EXCEPT
  `Quellenbelege/`** — so my own thinking never echoes back into search:
  - `Quellenbelege/` — quotable **source evidence** I save with `save_passage` (I
    just say "save this passage"). **Indexed**, so I can search my curated evidence;
    each entry keeps its source + page + a clickable link back to the corpus document.
  - `Wissen/` — my **notebook**: my own `.md` notes, free subfolders, even reference
    PDFs I keep but don't want searched. Claude reads/writes here (`read_note` /
    `write_note`). Use `#tags` and `[[wikilinks]]` to connect notes into a graph
    (browsable in Obsidian). **Never treat notebook content as external evidence.**
    - `Wissen/Übersicht.md` — the **map** (my current focus + a one-line catalog of
      my topic notes). **Read it first** to get oriented; keep it current.
    - `Wissen/Verlauf.md` — an **append-only, dated** log of what happened. Append at
      the bottom; never overwrite or reorder.
  - `Workflows/` — my reusable task recipes (see "My workflows" below).
  - `CLAUDE.md` / `AGENTS.md` — these guides.

## How to search my corpus

- Always use the `search` tool before answering content questions — never answer from memory about my documents.
- **Scale retrieval to the task** with `search`'s `mode`: `'precise'` for a single fact, `'normal'` (default), `'review'` for a literature survey across many sources (run several differently-phrased searches), `'deep'` (with `source_file=`) to dig into one report. To read or evaluate a whole document end-to-end, use `read_source`. (Advanced: override `top_k`/`max_per_source`.)
- **Big tasks → decompose (map-reduce).** Evaluating *many* reports/sources is NOT one search: enumerate them (`list_sources` / `recent_sources` / a `meta_filter`), then run one focused `read_source` or `search` **per item**, summarise each, and only then synthesise.
- Try multiple phrasings: my native-language term, the English term, a paraphrase.
- Use `chunk_type="table"` when I ask for numbers or statistics, `chunk_type="figure"` for diagrams.
- Every hit has a clickable PDF link — carry it into your answer when citing.
- If the corpus has nothing on a topic, say so plainly. Never invent sources or page numbers.
- When a hit is genuinely useful, offer to save it with `save_passage` (→ `Quellenbelege/`).

## How you grow my knowledge store (so a new session knows where we are)

The corpus is the immutable base; my **notebook is where our work compounds**. Chats
forget — the folder doesn't. So get context from there instead of asking me for it.

- **Read first.** At the start, read `Wissen/Übersicht.md` (and the latest
  `Wissen/Verlauf.md` lines) to know my current focus and where we left off.
- **"What's the status on X?" / "Let's continue on X."** → open `Wissen/<X>.md`,
  recap the state + open points, and carry on there. Don't ask me for background.
- **Compounding — knowledge grows, it doesn't sprawl.** When an answer is worth
  keeping, file it **once** into `Wissen/<Topic>.md` and **update it next time
  instead of duplicating**: refresh the status on top, append a dated section below
  (old sections stay = history). If new info contradicts old, flag it openly ("was
  X, since YYYY-MM-DD rather Y") instead of silently overwriting.
- **Evidence stays evidence.** A quotable source → `save_passage` (→ `Quellenbelege/`,
  searchable, linked to the corpus). My own thinking/results → `write_note`
  (→ `Wissen/`, not indexed).
- **Keep the map + log current:** update the topic's line in `Wissen/Übersicht.md`
  and append a dated line to `Wissen/Verlauf.md`.
- **At the end of a session**, proactively offer to write the new state + next steps
  into the topic note, so the next chat picks up seamlessly.
- **I source and ask; you maintain** — but **propose, don't silently rewrite**: for
  any bigger reorganisation, show me the plan first.

## My workflows (treat these as commands — don't ask me to explain)

When my message matches a trigger, READ that file in `Workflows/` (via `read_note`)
and run its steps with the tools, without asking me for background:

- „hol mich auf den Stand" / „woran haben wir gearbeitet?" → `Workflows/Hol-mich-auf-den-Stand.md`
- „halt das fest" / „pflege das in die Themenseite" → `Workflows/Themenseite-pflegen.md`
- „mach einen Wissens-Check" / „prüf mein Notizbuch" → `Workflows/Wissens-Check.md`
- „aktualisier das Quellenverzeichnis" / „die Quellenliste" → `Workflows/Quellenverzeichnis-aktualisieren.md`

To add one: drop a new `.md` in `Workflows/`, then add a trigger line here.

## Citation style

<!-- Example: "(cf. Author, Year, p. X)" or APA 7 or your discipline's norm. -->

(your citation format, with one example)

## Conventions

- Language for answers and notes: (your language)
- New notes go to `WissensWIKI/Wissen/`, named `Topic_Name.md`, with `[[wikilinks]]` and `#tags` to related notes.
