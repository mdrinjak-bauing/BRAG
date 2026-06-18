# Install on Windows 10/11

**🇬🇧 English | 🇩🇪 [Deutsch](INSTALL_WINDOWS.de.md)**

Time needed: ~20 minutes (most of it is downloads). You only need your mouse and
the Command Prompt once — no programming required.

## 1. Install Docker Desktop

**What to do:**
1. Download Docker Desktop from
   <https://www.docker.com/products/docker-desktop/> and run the installer.
2. If it asks about **WSL 2**, accept (it may install it for you; a **restart**
   can then be required — go ahead and do it).
3. After the restart, open **Docker Desktop**.

**What you see:** The Docker window with a status indicator at the bottom left.
**Wait until it says "Engine running" / "running"** in green — only then is
Docker ready. A whale icon also appears in the taskbar tray (bottom right,
possibly under the "show hidden icons" arrow).

> If Docker complains about **virtualization**: reboot into BIOS/UEFI and enable
> it (usually "Intel VT-x" or "AMD-V"). Your computer vendor's support page
> explains where the option is.

## 2. Install Claude Desktop

**What to do:** Download Claude Desktop from <https://claude.com/download>,
install it, open it, and sign in once.

**What you see:** A normal chat window. The connection to the knowledge base is
set up automatically in step 4.

## 3. Get a free Gemini API key (default profile)

**What to do:**
1. Open <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **"Create API key"**.
3. **Copy** the key shown — you'll paste it into setup next.

> ⚠️ The free tier is not suitable for confidential or licensed content (Google
> may use the text). For such content, choose a local profile later — see
> [LEGAL.md](LEGAL.md) and [PROFILES.md](PROFILES.md).

## 4. Download and set up BRAG

**What to do:**
1. On the GitHub page, click the green **`Code`** button → **`Download ZIP`**.
   Right-click the ZIP → **"Extract All"** (e.g. to
   `C:\Users\<you>\academic-rag-and-second-brain`). Important: **extract** first
   — don't run it from inside the ZIP.
2. Open the extracted folder and double-click **`setup.bat`**.
   - If **Windows SmartScreen** warns ("Windows protected your PC"): click **"More
     info"** → **"Run anyway"**.

**What you see:** A black Command Prompt window opens and, shortly after, **your
browser opens automatically** with the setup assistant. There you answer, in
plain language:
- **Where should the AI run?** (cloud or local) — pick "Cloud" to start.
- **Provider & key:** choose Gemini and paste the copied key. The assistant
  checks it **live** and shows a green check when it's valid.
- **Your document language** and, optionally, a custom knowledge store folder.

At the end the assistant writes the whole configuration itself — including the
Claude Desktop entry. **You never edit a single file.** The window then builds
the Docker containers in the background and downloads ~3 GB of models once (a few
minutes, first time only).

3. When the assistant says "done": **quit Claude Desktop completely** —
   right-click the Claude icon in the taskbar tray (bottom right) → **Quit**
   (closing the window is not enough!) — and reopen Claude.

## 5. First document

**What to do:** Put a PDF into the `wissensspeicher\sources\` folder (inside the project
folder).

**What you see:** Nothing visible — processing runs in the background. A short
document is indexed within ~30 seconds. To watch, open a Command Prompt in the
project folder and run:

```
docker compose logs -f app
```

You'll see lines like `[1/4] extracting …` up to `done: N chunks indexed`. Press
`Ctrl+C` to stop the display (this does **not** stop the app).

Now ask Claude:

> What documents are in my knowledge base?

## How do I know it's running?

- **Easiest:** double-click **`status.bat`** — a one-click check of Docker,
  Qdrant, the watcher, the corpus and the AI connection, with a ✓/✗ per item.
- In **Docker Desktop** the status reads "running".
- `docker ps` (Command Prompt, in the project folder) lists the two containers
  **`asb-app`** and **`asb-qdrant`**.
- In Claude Desktop the tools (e.g. `search`, `list_sources`) appear. If they're
  missing, you likely only closed Claude instead of **quitting** it.

## Notes

- **OneDrive:** Keeping the project folder inside OneDrive is fine — the database
  lives inside Docker, safely outside any sync folder.
- **Stopping/starting:** To stop, open a Command Prompt in the project folder and
  run `docker compose down`. To start: `docker compose up -d`.
- **Hybrid/Local profiles:** install [Ollama](https://ollama.com) (recommended
  on Windows) first, then run setup. See [PROFILES.md](PROFILES.md).
- Trouble? See [FAQ.md](FAQ.md).
