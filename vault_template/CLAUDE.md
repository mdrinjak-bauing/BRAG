# My knowledge store — Instructions for Claude

<!-- This file teaches Claude how to work with YOUR research. Claude Code reads it
automatically; in Claude Desktop it is NOT read on its own — create a Project and
paste this file's content into the Project's custom instructions (see the README,
"Use BRAG with a Claude Project"). Fill in the placeholders — concrete beats
generic. Keep it updated: whenever you correct Claude twice about the same thing,
the correction belongs in here. -->

## Who I am and what I research

<!-- Example: "I am a professor of structural engineering at X University.
My current focus is fatigue behavior of welded joints. I supervise 4 PhD
students and teach two courses." -->

(your field, institution, current projects)

## My knowledge-store layout

- The **project folder itself is my searchable corpus** — I drop documents (PDFs, DOCX) straight into it, in any subfolder at any depth, and everything gets indexed. **Read-only — never edit or move files in the corpus.** The first subfolder level names the document type (e.g. `papers/`, `books/`).
- `WissensWIKI/` is my workspace, and **nothing under it is indexed** (so my notes never echo back into search):
  - `Passagen/` — quotable passages I saved with the `save_passage` tool (I just ask Claude to “save this passage”). These ARE indexed.
  - `Notizen/` + any free subfolders I make — my notebook (concepts, drafts, decisions, thinking). Claude reads and writes here via `read_note`/`write_note`. **Never treat notebook content as external evidence** — these are my notes, not sources.
  - `CLAUDE.md`/`AGENTS.md` — these guides.

## How to search my corpus

- Always use the `search` tool before answering content questions — never answer from memory about my documents.
- **Scale retrieval to the task** with `search`'s `mode`: `'precise'` for a single fact, `'normal'` (default), `'review'` for a literature survey across many sources (run several differently-phrased searches), `'deep'` (with `source_file=`) to dig into one report. To read or evaluate a whole document end-to-end, use `read_source`. (Advanced: override `top_k`/`max_per_source`.)
- **Big tasks → decompose (map-reduce).** Evaluating *many* reports/sources is NOT one search: enumerate them (`list_sources` / `recent_sources` / a `meta_filter`), then run one focused `read_source` or `search` **per item**, summarise each, and only then synthesise. A single search deliberately returns the *most relevant* passages — more chunks ≠ a better answer.
- Try multiple phrasings: my native-language term, the English term, a paraphrase.
- Use `chunk_type="table"` when I ask for numbers or statistics, `chunk_type="figure"` for diagrams.
- Every hit has a clickable PDF link — carry it into your answer when citing.
- If the corpus has nothing on a topic, say so plainly. Never invent sources or page numbers.
- When a hit is genuinely useful for my work, offer to save it with `save_passage`.

## How you take work off my hands (so I don't repeat context)

My knowledge store is our shared memory — chats forget, the folder doesn't. Get
context from there instead of asking me for it.

- **"What's the status on X?"** → first read `Notizen/<X>.md` (and any `Berichte/`),
  then top it up with `search`; summarise the state + open points. Don't ask me for
  background — fetch it.
- **"Let's continue on X."** → open the note/report for X, briefly recap where we
  left off, then carry on there.
- **"Save the results."** → file them yourself in the right place: state/decisions →
  `write_note('Notizen/<X>.md', …)`; a finished deliverable → `save_report`; a
  quotable source → `save_passage`. Append dated; never overwrite.
- **At the end of a working session**, proactively write the new state + next steps
  into the topic note, so the next chat picks up seamlessly.
- **Convention:** one topic = one note `Notizen/<Topic>.md` (status on top, then
  dated sections). Reorganise notes with `move_note` when needed.

## Citation style

<!-- Example: "(cf. Author, Year, p. X)" or APA 7 or your discipline's norm. -->

(your citation format, with one example)

## Conventions

- Language for answers and notes: (your language)
- New concept notes go to `WissensWIKI/Notizen/`, named `Topic_Name.md`, with `[[wikilinks]]` to related notes.
