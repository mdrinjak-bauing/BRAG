# Your knowledge store

This folder is your knowledge base. It is a normal folder of files — you can
open it with [Obsidian](https://obsidian.md) as a vault, back it up, or sync
it however you like.

| Folder | What it is | Who writes here |
|---|---|---|
| `sources/` | Your documents (PDF, DOCX, ...). Drop files in — they are indexed automatically within seconds. Subfolders become document types. | You |
| `notes/` | One literature note per indexed document. Add your own thoughts under "My notes" — that section is never overwritten. | The system + you |
| `passages/` | Quotable passages you save while researching with Claude, grouped by topic. | Claude (on your request) |
| `wiki/` | Your own thinking: concepts, drafts, decisions. Deliberately **not** part of the search index — your notes should never come back disguised as evidence. | You |

`CLAUDE.md` tells Claude how to work with your research — fill in the
placeholders, it makes a real difference. `sources/_inbox/` (create it if
you want) is a staging area the indexer ignores.

**Own metadata:** put a `_meta.txt` (one `key: value` per line, e.g.
`project: School Center`) into any folder under `sources/` — all documents
in it carry those fields, and Claude can filter searches by them.
