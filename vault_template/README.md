# WissensWIKI — your workspace

This folder is **your** space inside the project. Everything here is **not**
bulk-indexed — EXCEPT `Quellenbelege/` — so your own thinking never echoes back into
search:

- **`Quellenbelege/`** — **source evidence** you save with the `save_passage` tool
  (just ask Claude to "save this passage"). **Indexed**, so you can search your
  curated evidence; each entry keeps its source, page and a link back to the corpus
  document.
- **`Wissen/`** — your **notebook**: your own `.md` notes, any subfolders, even
  reference PDFs you keep but don't want searched. **Not indexed.** Claude reads and
  writes here (`read_note` / `write_note`); use `#tags` and `[[wikilinks]]` to weave
  notes into a graph (browsable in Obsidian). It also holds `Übersicht.md` (the map
  Claude reads first) and `Verlauf.md` (a dated log).
- **`Workflows/`** — reusable task recipes (named workflows like "catch me up" or
  "save this to the topic page"). Name one and Claude follows it; add your own.
- **`CLAUDE.md`** — teach Claude about your field (fill it in, then paste it into
  your Claude Project's instructions — Claude Desktop doesn't read it on its own).
- **`AGENTS.md`** — extra rules for code agents (Claude Code / autonomous runs).

**Your documents do NOT go in here.** Drop them straight into the **project folder**
(the folder that contains this one) — everything there, in any subfolder, is the
searchable corpus (your immutable knowledge base).
