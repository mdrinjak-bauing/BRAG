# My knowledge store — Instructions for Claude

<!-- This file teaches Claude how to work with YOUR research. Claude Desktop
(in a Project) and Claude Code read it automatically. Fill in the
placeholders — concrete beats generic. Keep it updated: whenever you correct
Claude twice about the same thing, the correction belongs in here. -->

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
- **Scale retrieval to the task** with `top_k` (breadth) and `max_per_source` (depth per document): a precise fact → `top_k` 5–8; a normal question → 12–15; a **literature review / broad survey** → `top_k` 30–50 across several differently-phrased searches; to **evaluate a specific report in depth** → set `source_file=` and raise `max_per_source` (e.g. 8–15).
- Try multiple phrasings: my native-language term, the English term, a paraphrase.
- Use `chunk_type="table"` when I ask for numbers or statistics, `chunk_type="figure"` for diagrams.
- Every hit has a clickable PDF link — carry it into your answer when citing.
- If the corpus has nothing on a topic, say so plainly. Never invent sources or page numbers.
- When a hit is genuinely useful for my work, offer to save it with `save_passage`.

## Citation style

<!-- Example: "(cf. Author, Year, p. X)" or APA 7 or your discipline's norm. -->

(your citation format, with one example)

## Conventions

- Language for answers and notes: (your language)
- New concept notes go to `WissensWIKI/Notizen/`, named `Topic_Name.md`, with `[[wikilinks]]` to related notes.
