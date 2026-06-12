# FAQ & Troubleshooting

## Setup

**"Docker is not installed" although I installed it.**
Open the Docker Desktop app once and wait until it says "running", then run
setup again. On Windows, a restart after installation can be required.

**The setup window closed before I could read the message.**
Run it from a terminal instead: open Terminal/Command Prompt in the project
folder and run `./setup.command` (Mac) or `setup.bat` (Windows).

**Claude Desktop doesn't show the tools.**
1. Quit Claude Desktop **completely** (Cmd+Q / tray icon → Quit) and reopen —
   a window close is not enough.
2. Check the container is running: `docker ps` should list `asb-app`.
3. Check the config file (see [OBSIDIAN.md](OBSIDIAN.md) for the path)
   contains the `academic-rag-and-second-brain` entry.

## Indexing

**I dropped a PDF and nothing happens.**
- Wait ~30 seconds (the folder is checked every 10 seconds, files must
  finish copying first).
- Check the logs: `docker compose logs -f app`.
- Files inside `sources/_inbox/` are deliberately ignored (staging area).

**"Scanned PDF without text layer."**
The PDF contains only images of text. OCR support is on the roadmap; for
now, run the PDF through an OCR tool first (e.g. Acrobat, or macOS Preview's
built-in text recognition won't embed a layer — use `ocrmypdf` or similar).

**Indexing is slow.**
The first document downloads the layout-analysis models once. A 50-page
paper typically takes 1–3 minutes; a 500-page book proportionally longer.
Profiles B/C are slower than A.

**"Rate limit" messages during indexing (Cloud profile).**
The free Gemini tier has per-minute/per-day limits. The system waits and
retries automatically — let it run; nothing is lost. Failed chunks are
recorded in `vault/.asb/failed_chunks.jsonl`.

## Searching

**Claude says it found nothing, but the document is there.**
- Ask Claude to try different phrasings (synonyms, English terms).
- Ask: *"Use inspect_chunks on <source name>"* — this shows what is actually
  stored and usually reveals the problem (e.g. a table extracted badly).
- Check the document is indexed: *"List my sources."*

**The PDF link doesn't open at the right page.**
The link opens in your browser, which jumps to the page via `#page=N`. Some
browsers/PDF settings ignore the page anchor — Chrome and Edge handle it
best. The page number is also stated in the search hit itself.

**Search quality is worse in my language.**
Set `VAULT_LANGUAGE` in `.env` to your language (affects keyword stemming)
and `ANSWER_LANGUAGE` for generated text, then re-index new documents.

## Operations

**How do I stop / start everything?**
`docker compose down` / `docker compose up -d` in the project folder.
Docker Desktop's autostart brings it back after a reboot.

**How do I update to a new version?**
Download the new release, replace the folder contents (keep your `.env` and
`vault/`), then `docker compose build && docker compose up -d`.

**How do I back up?**
Your documents and notes are in `vault/` — back that folder up like any
other folder. The search index can always be rebuilt from the vault (delete
nothing, just let reconciliation re-index after a restore).

**How do I remove a document?**
Delete the file from `sources/` — its index entries and the auto-note are
cleaned up automatically.
