# WissensWIKI — your workspace

This folder is **your** space inside the project — and the one folder here that is
**not** bulk-indexed (so your own notes never echo back into search):

- **`Passagen/`** — verified passages you save with the `save_passage` tool (just ask
  Claude to “save this passage”). These **are** indexed, so you can search your curated evidence.
- **`Notizen/`** and any other subfolders you create — your own writing and notes.
  **Not indexed.** Claude can read and write here (read_note / write_note); name
  the subfolders however you like.
- **`Routinen/`** — reusable task recipes (named workflows like “catch me up” or
  “update the bibliography”). Name one and Claude follows it; add your own.
- **`CLAUDE.md`** — teach Claude about your field (fill it in).
- **`AGENTS.md`** — extra rules for autonomous agent tasks.

**Your documents do NOT go in here.** Drop them straight into the **project folder**
(the folder that contains this one) — everything there, in any subfolder, is the
searchable corpus.
