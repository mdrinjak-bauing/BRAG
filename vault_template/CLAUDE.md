# My Research Vault — Instructions for Claude

<!-- This file teaches Claude how to work with YOUR research. Claude Desktop
(in a Project) and Claude Code read it automatically. Fill in the
placeholders — concrete beats generic. Keep it updated: whenever you correct
Claude twice about the same thing, the correction belongs in here. -->

## Who I am and what I research

<!-- Example: "I am a professor of structural engineering at X University.
My current focus is fatigue behavior of welded joints. I supervise 4 PhD
students and teach two courses." -->

(your field, institution, current projects)

## My vault layout

- `sources/` — my document corpus (PDFs, DOCX). **Read-only — never edit or move files here.** Subfolder names become the document type (e.g. `sources/papers/`, `sources/books/`).
- `notes/` — auto-generated literature notes, one per source. The section "My notes" is mine; everything above it is regenerated.
- `passages/` — quotable passages I saved via `save_passage`, grouped by topic.
- `wiki/` — my own thinking (concepts, drafts, decisions). **Never treat wiki content as external evidence** — these are my notes, not sources.

## How to search my corpus

- Always use the `search` tool before answering content questions — never answer from memory about my documents.
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
- New concept notes go to `wiki/`, named `Topic_Name.md`, with `[[wikilinks]]` to related notes.
