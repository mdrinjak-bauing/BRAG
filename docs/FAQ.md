# FAQ & Troubleshooting

**🇬🇧 English | 🇩🇪 [Deutsch](FAQ.de.md)**

## Setup

**"Docker is not installed" although I installed it.**
Open the Docker Desktop app once and wait until it says "running", then run
setup again. On Windows, a restart after installation can be required.

**The setup window closed before I could read the message.**
Run it from a terminal instead: open Terminal/Command Prompt in the project
folder and run `./setup.command` (Mac) or `setup.bat` (Windows).

**The browser setup page doesn't open, or port 8765 is already in use.**
Another program on your computer may already use port 8765. Open the `.env` file
in the project folder and set a free port, for example:

```
BRIDGE_HOST_PORT=8780
BRIDGE_PUBLIC_URL=http://localhost:8780
```

Then run setup again. The launcher (`setup.command` / `setup.bat`) reads
`BRIDGE_HOST_PORT` from `.env` and opens the right URL. **Both** variables must
be set: `BRIDGE_HOST_PORT` moves the port, and `BRIDGE_PUBLIC_URL` must match it
— otherwise the PDF deep-links in answers (which jump to a page) break.

**The build failed or got stuck.**
The first run downloads heavy dependencies and ~3 GB of models. On a flaky
network — or when Docker is low on disk — that download can fail or stall. Open
Docker Desktop and confirm it says "running" and that you have internet, then
simply double-click setup again. It resumes from the cache, so it doesn't start
over.

**What happens to my API key?**
Your API key is stored only in a local `.env` file on your computer
(owner-readable only) and is used solely to authenticate your own requests to the
provider you chose (Gemini / OpenAI / Anthropic). It is never sent to the makers
of this app or any third party; the live check during setup just sends one small
test request to that provider to confirm the key works. The local profile (LM
Studio) needs no key at all.

**macOS: double-clicking `setup.command` does nothing (no window opens).**
This is different from the Gatekeeper "unidentified developer" warning (for that,
right-click → Open). If *no* window appears at all, the file may have lost its
executable bit. Open Terminal in the project folder and run:

```
chmod +x setup.command status.command
```

Then double-click `setup.command` again.

**Claude Desktop doesn't show the tools.**
1. Quit Claude Desktop **completely** (Cmd+Q / tray icon → Quit) and reopen —
   a window close is not enough.
2. Check the container is running: `docker ps` should list `brag-app`.
3. Check the config file (see [OBSIDIAN.md](OBSIDIAN.md) for the path)
   contains the `brag` entry (older installs may show the longer legacy name
   until you re-run setup).

## Indexing

**Which file types can I add?**
PDF, Word (`.docx`), PowerPoint (`.pptx`), Markdown (`.md`) and HTML — just drop
them into `RAG-Verbindungsordner/sources/`. Page-precise deep-links work for PDFs; the
other formats are indexed and searchable but cited without a page link.
**Excel (`.xlsx`) is not supported yet.**

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
The local profile (LM Studio) is slower than the cloud profiles.

**"Rate limit" messages during indexing (Cloud profile).**
The free Gemini tier has per-minute/per-day limits. The system waits and
retries automatically — let it run; nothing is lost. Failed chunks are
recorded in `RAG-Verbindungsordner/.brag/failed_chunks.jsonl`.

**Are figures/images analyzed?**
Yes. The **vision pass** is on by default: on ingest each figure image is sent
to the multimodal text AI, which briefly and honestly describes what it shows;
that description is embedded too, so you can find figures by their **content**
(not just the caption). With a non-multimodal local model — or when an image is
missing — the system falls back automatically to "caption + chapter only". Turn
it off with `VISION_ENABLED=false` in `.env`. Note: on cloud profiles the image
is sent to the provider too (see [LEGAL.md](LEGAL.md)).

**I rename a file that's already indexed — is the metadata still correct?**
Yes. The watcher detects the rename and updates author, year, type and the PDF
path **directly in the index** — **without reprocessing the file** (no
re-embedding, no API cost); the literature note moves along too. This applies to
a true rename (same file, new name). If your system reports it as delete +
create instead, a normal re-ingest runs — same result, just slower.

## Performance

**Is running in Docker slower than natively on the machine?**
For everyday use, no — dropping a PDF and asking questions is a matter of
seconds either way. It only shows during a one-time **bulk ingest of a large
corpus**, and that depends on the OS:

- **Linux:** containers share the host kernel → effectively native.
- **Windows:** runs in a lightweight Linux VM (WSL2); CPU near-native.
- **macOS (Apple Silicon):** runs in a Linux VM; CPU near-native, **but no
  access to the Metal GPU inside the container**. A native install could
  accelerate embeddings and the reranker via GPU (MPS) — in Docker they run on
  CPU.

The trade-off is deliberate: Docker costs a little bulk-ingest speed in return
for reproducibility and double-click setup. For "weak hardware + very large
corpus" there is the `.env` **cloud embeddings** option (see [PROFILES.md](PROFILES.md)).

## Searching

**Searching feels slow / my computer struggles during a query.** The local
cross-encoder reranker is the main CPU cost of a search. Set `RERANK_PROFILE` in
`.env` to trade quality for speed: `eco` (default) loads 160 candidates and
reranks 40; `off` skips reranking entirely (fastest); `balanced` and `full`
rerank more for a strong machine. After editing `.env`, apply it with
`docker compose up -d --force-recreate`. Full list: [Backend profiles](PROFILES.md).

**Claude says it found nothing, but the document is there.**
- Ask Claude to try different phrasings (synonyms, English terms).
- Ask: *"Use inspect_chunks on <source name>"* — this shows what is actually
  stored and usually reveals the problem (e.g. a table extracted badly).
- Check the document is indexed: *"List my sources."*

**The PDF link opens on page 1, not the cited page.**
The link uses the standard PDF `#page=N` parameter. The **built-in PDF viewers
of Chrome, Edge and Firefox honor it**, but **Safari's does not** — it opens
page 1. Either open the links in Chrome/Edge/Firefox, or install a free
dedicated viewer that jumps to the page and set it as your PDF handler:
**Skim** (macOS) or **SumatraPDF** (Windows). The cited page number is always in
the hit text too, so you can navigate by hand if needed.

**The chat cites the PDF page, not the printed (book) page.**
By default the citation is the physical PDF page. For documents whose printed
numbering differs (a book with front matter, a journal offprint), set a
`page_offset` in a `_meta.txt` — then citations show the printed page while the
link still opens the correct PDF page. The rule is `page_offset = physical page
− printed page`; see the `_meta.txt` section in the README. Re-index the
document after setting it.

**Search quality is worse in my language.**
Set `VAULT_LANGUAGE` in `.env` to your language (affects keyword stemming)
and `ANSWER_LANGUAGE` for generated text, then re-index new documents.

## Operations

**How do I check with one click that everything works?**
Double-click **`status.command`** (Mac) or **`status.bat`** (Windows) in the
project folder. It reports ✓/✗ for: Docker running, the `brag-app` and
`brag-qdrant` containers up, Qdrant reachable, the corpus indexed (with source/
chunk counts), the watcher running, the AI text model reachable, and Claude
Desktop wired up. Each ✗ tells you what to do.

**How do I stop / start everything?**
`docker compose down` / `docker compose up -d` in the project folder.
Docker Desktop's autostart brings it back after a reboot.

**How do I update to a new version?**
Download the new release, replace the folder contents (keep your `.env` and
`RAG-Verbindungsordner/`), then `docker compose build && docker compose up -d`.

**How do I back up?**
Your documents and notes are in `RAG-Verbindungsordner/` — back that folder up like any
other folder. The search index can always be rebuilt from the knowledge store (delete
nothing, just let reconciliation re-index after a restore).

**How do I remove a document?**
Delete the file from `sources/` (or move it out) — its index entries and the
auto-note are removed automatically. You can also ask Claude to *"remove that
source from my index"* (the `remove_source` tool): it moves the file into
`sources/_inbox/` (reversible, not deleted) and clears its chunks. Deletions you
make while the app is stopped are pruned automatically on the next start.

**I updated/overwrote a file — will search pick up the new content?**
Yes. Overwriting a file in place is detected automatically: the watcher
re-indexes it once the change settles (the old chunks are replaced). Allow a few
seconds; you can watch for the *"document changed … re-indexing"* line in
`docker compose logs -f app`.

**Can I delete the project folder or the ZIP?**
You can delete the **ZIP** after unpacking. But **keep the project folder** (the
unpacked ZIP) — it holds your configuration (`.env`), the controls
(`docker-compose.yml`) and, by default, your knowledge store (`RAG-Verbindungsordner/`) with all your
documents. Deleting it would remove your knowledge base and make starting/
stopping impossible. Moving it is fine. The ~3 GB of models live in Docker's
storage, not in the folder, so deleting it won't free that space.
