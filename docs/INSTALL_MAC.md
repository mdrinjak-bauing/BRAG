# Install on macOS

**🇬🇧 English | 🇩🇪 [Deutsch](INSTALL_MAC.de.md)**

> **First time using the Terminal?** This guide has you run a couple of commands
> by hand. Take your time and read each step — and if anything is unclear, an AI
> assistant like [Claude Code](https://claude.com/claude-code) can walk you
> through it and explain what each command does.

Time needed: about **15 minutes of active work** — mostly your mouse (the
Terminal only for the optional log view in step 5), no programming required. On top of that, the first build and
the one-time model downloads run mostly **unattended** in the background; on a
first install, allow roughly **30–60 minutes total** depending on your internet
connection.

## 1. Install Docker Desktop

**What to do:**
1. Open <https://www.docker.com/products/docker-desktop/> and download Docker
   Desktop (choose "Apple Silicon" for M1/M2/M3 Macs, "Intel chip" for older
   Macs).
2. Open the downloaded `.dmg` (in your Downloads folder) and **drag the Docker
   icon into the Applications folder**, as the window shows.
3. Start Docker once from Applications. Accept the license on first launch;
   signing in is **not** required (you can skip it).

**What you see:** A small **whale icon** 🐳 appears in the menu bar (top right).
While it animates, Docker is still starting. **Wait until it stops moving** —
then Docker is ready.

## 2. Install Claude Desktop

**What to do:** Download Claude Desktop from <https://claude.com/download>, drag
it into Applications, open it, and sign in once.

**What you see:** A normal chat window. The connection to your knowledge base is
set up automatically in step 4 — nothing to do here yet.

## 3. Get a free Gemini API key (default profile)

**What to do:**
1. Open <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **"Create API key"**.
3. **Copy** the key shown (a long string) — you'll paste it into setup next.

> ⚠️ The free tier is not suitable for confidential or licensed content (Google
> may use the text). For such content, choose a local profile later — see
> [LEGAL.md](LEGAL.md) and [PROFILES.md](PROFILES.md).

## 4. Download and set up BRAG

> **One-time macOS note — and why it's safe.** A script downloaded from the
> internet is "quarantined", so macOS shows an "unidentified developer" warning
> the first time. `setup.command` is a short, readable text file (it only checks
> Docker, writes a local config and starts the containers). The right-click →
> **Open** below tells macOS to trust it once. To avoid the prompt entirely you
> can instead `git clone` the repo (cloned files are not quarantined).

**What to do:**
1. On the GitHub page, click the green **`Code`** button → **`Download ZIP`**.
   Unpack the ZIP by double-clicking it (e.g. into your home folder — see the
   iCloud note below). The unpacked BRAG folder appears (its name comes from
   the ZIP). *Prefer the terminal?* `git clone https://github.com/mdrinjak-bauing/BRAG.git`
   avoids the quarantine prompt altogether.
2. Open that folder in Finder and double-click **`setup.command`**.
   - If macOS blocks it ("unidentified developer" / "Apple could not verify…"):
     **do not click "Move to Trash"** — the file is safe. **Right-click** it →
     **Open** → **Open** again in the dialog.
   - On newer macOS the right-click dialog may show no "Open" button. Then open
     **System Settings** → **Privacy & Security**, scroll down, and next to
     *"setup.command was blocked…"* click **"Open Anyway"**; confirm with Touch ID,
     then double-click `setup.command` again. (Normal for any unsigned downloaded
     script — you only confirm it once.)

**Setup asks two things in order.** First a folder picker asks *where the
`BRAG Assistent` program should live* (e.g. on your Desktop) — pick anywhere you
like. Then a second picker asks for *your project folder* (your documents). BRAG
copies the program into a `BRAG Assistent` folder, creates a `WissensWIKI`
workspace inside your project folder, and continues from there in a fresh window.
*(If you cancel the first picker, the program just installs in the unpacked
folder; the project folder in the second step is required.)*

**What you see:** A small black Terminal window opens and, shortly after, **your
browser opens automatically** with the setup assistant. There you answer, in
plain language:
- **Where should the AI run?** (cloud or local) — pick "Cloud" to start.
- **Provider & key:** pick your provider (**Gemini** recommended, or OpenAI /
  Anthropic) and paste the copied key. The assistant checks it **live** (green
  check when valid) and then offers that provider's models as a **dropdown** with
  the cheapest preselected — so you don't have to type an exact model id ("Other"
  lets you enter one anyway). Your key is stored only in a local `.env` file on
  your computer (owner-readable only) and is used solely to authenticate your own
  requests to the provider you chose — never sent to the makers of this app or any
  third party; the live check just sends one small test request. The local profile
  (LM Studio) needs no key at all.
- **Your document language.** (Your project folder was already chosen by the
  folder picker above.)
- **Folders to exclude (optional).** Tick any top-level folders you want kept
  **out** of the search — or just name a folder starting with `_` (e.g.
  `_Archiv/`), which is never indexed.

At the end the assistant writes the whole configuration itself — including the
Claude Desktop entry. **You never edit a single file.** The Terminal then builds
the Docker containers in the background and downloads ~3 GB of models once (a few
minutes, first time only).

3. When the assistant says "done": **quit Claude Desktop completely** — press
   **Cmd+Q** (closing the window is not enough!) — and reopen Claude.

## 5. First document

**What to do:** Drop a PDF straight into your project folder (any subfolder works
too) — everything in the project folder is searched, except the `WissensWIKI`
workspace, hidden folders, and anything whose name starts with `_`.

**What you see:** Nothing visible — processing runs in the background. Note that
the **very first** document also downloads the Docling layout models, so this one
can take a few minutes (later documents are much faster). It's best to confirm
the pipeline works with a small **1–2 page PDF** first; after that, expect about
**1–3 minutes** for a normal 50-page paper. To watch it, open Terminal in the
project folder and run:

```
docker compose logs -f app
```

You'll see lines like `[1/4] extracting …` up to `done: N chunks indexed`. Press
`Ctrl+C` to stop the display (this does **not** stop the app).

Now ask Claude:

> What documents are in my knowledge base?

## How do I know it's running?

- **Easiest:** double-click **`status.command`** — a one-click check of Docker,
  Qdrant, the watcher, the corpus and the AI connection, with a ✓/✗ per item.
- The **whale icon** in the menu bar is steady → Docker is running.
- `docker ps` (Terminal, in the project folder) lists the two containers
  **`brag-app`** and **`brag-qdrant`**.
- In Claude Desktop the tools (e.g. `search`, `list_sources`) appear via the
  tools/plug icon in the input box. If they're missing, you likely only closed
  Claude instead of quitting it with **Cmd+Q**.

## Notes

- **iCloud:** It is fine to keep the project folder (and the knowledge store) in an
  iCloud-synced location — the database itself lives inside Docker, safely
  outside any sync folder.
- **Stopping/starting:** Docker Desktop starts the app automatically after boot.
  To stop manually: open Terminal in the project folder, `docker compose down`.
  To start: `docker compose up -d`.
- **Updating (no reinstall):** put the new files into your **BRAG Assistent**
  folder (keep your `.env`), then double-click **`update.command`** — it rebuilds
  and restarts the app while keeping your `.env`, the search index, the connectors
  and your documents. To just **change the model/reranker**, double-click
  `setup.command` from this folder and pick **"⚙ Change a setting"** — no folder
  questions, no re-indexing.
- **Hybrid profile (LM Studio):** install [LM Studio](https://lmstudio.ai) first,
  load a model, then run setup. Setup auto-connects the BRAG tools (the connector
  is named `brag` for your first project) to LM Studio's chat too (not just Claude);
  if you install LM Studio *after* setup, just run `setup.command` again to add the
  connection. See [PROFILES.md](PROFILES.md).
- **Add another project:** double-click **`Projekt hinzufuegen.command`**, pick a
  second project folder and name it. BRAG creates a `WissensWIKI/` workspace inside
  it and adds a `brag-<name>` connector next to your first one; the engine and the
  ~3 GB models stay shared. Nothing from one project leaks into another.
- **Remove BRAG:** double-click **`uninstall.command`**. A menu offers **[1]**
  remove one project's connection (keeps BRAG and your other projects), **[2]**
  remove the whole system (a full Docker clean: containers, model cache, search
  index, Claude/LM Studio connection), or **[C]** cancel. Either way **your
  documents on disk are never deleted** — a re-install picks them up again.
- Trouble? See [FAQ.md](FAQ.md).
