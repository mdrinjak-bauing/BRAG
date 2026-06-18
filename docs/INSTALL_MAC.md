# Install on macOS

**🇬🇧 English | 🇩🇪 [Deutsch](INSTALL_MAC.de.md)**

Time needed: about **15 minutes of active work** — you only need your mouse and
the Terminal once, no programming required. On top of that, the first build and
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

**What to do:**
1. On the GitHub page, click the green **`Code`** button → **`Download ZIP`**.
   Unpack the ZIP by double-clicking it (e.g. into your home folder — see the
   iCloud note below). A folder named `Academic-RAG-and-Second-Brain-main`
   appears (the exact name may vary slightly).
2. Open that folder in Finder and double-click **`setup.command`**.
   - If macOS blocks it ("unidentified developer"): **right-click** the file →
     **Open** → **Open** again in the dialog.

**What you see:** A small black Terminal window opens and, shortly after, **your
browser opens automatically** with the setup assistant. There you answer, in
plain language:
- **Where should the AI run?** (cloud or local) — pick "Cloud" to start.
- **Provider & key:** choose Gemini and paste the copied key. The assistant
  checks it **live** and shows a green check when it's valid. Your key is stored
  only in a local `.env` file on your computer (owner-readable only) and is used
  solely to authenticate your own requests to the provider you chose — it is
  never sent to the makers of this app or any third party; the live check just
  sends one small test request to that provider to confirm the key works. Local
  profiles (Ollama / LM Studio) need no key at all.
- **Your document language** and, optionally, a custom knowledge store folder.

At the end the assistant writes the whole configuration itself — including the
Claude Desktop entry. **You never edit a single file.** The Terminal then builds
the Docker containers in the background and downloads ~3 GB of models once (a few
minutes, first time only).

3. When the assistant says "done": **quit Claude Desktop completely** — press
   **Cmd+Q** (closing the window is not enough!) — and reopen Claude.

## 5. First document

**What to do:** Put a PDF into the `wissensspeicher/sources/` folder (inside the project
folder).

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
- **Hybrid/Local profiles:** install [LM Studio](https://lmstudio.ai) or
  [Ollama](https://ollama.com) first, load a model, then run setup. See
  [PROFILES.md](PROFILES.md).
- Trouble? See [FAQ.md](FAQ.md).
