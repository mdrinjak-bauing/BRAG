# Install on Windows 10/11

Time needed: ~20 minutes (most of it is downloads).

## 1. Install Docker Desktop

1. Download from <https://www.docker.com/products/docker-desktop/>.
2. Run the installer. If it asks about **WSL 2**, accept (it may install it
   for you; a restart can be required).
3. Open Docker Desktop and wait until the status says "running".

> If Docker complains about virtualization: enable it in your BIOS/UEFI
> (usually called "Intel VT-x" or "AMD-V"). Your computer vendor's support
> page explains where.

## 2. Install Claude Desktop

Download from <https://claude.com/download> and install. Sign in once.

## 3. Get a free Gemini API key (Cloud profile)

1. Go to <https://aistudio.google.com/apikey> (Google account required).
2. Click "Create API key" and copy it.

## 4. Download and set up Academic RAG and Second Brain

1. On the GitHub page: green **Code** button → **Download ZIP**, unpack it
   (e.g. to `C:\Users\<you>\academic-rag-and-second-brain`).
2. Double-click **`setup.bat`**.
   - If Windows SmartScreen warns: "More info" → "Run anyway".
3. Answer the three questions (profile, API key, document language).
4. When the wizard finishes, **quit Claude Desktop completely** (right-click
   the tray icon → Quit) and reopen it.

## 5. First document

Put a PDF into the `vault\sources\` folder. Indexing starts automatically
within ~30 seconds. Then ask Claude:

> What documents are in my knowledge base?

## Notes

- **OneDrive:** Keeping the project folder inside OneDrive is fine — the
  database lives inside Docker, safely outside any sync folder.
- **Stopping/starting:** To stop, open a command prompt in the project folder
  and run `docker compose down`. To start: `docker compose up -d`.
- **Profiles B/C:** install [Ollama](https://ollama.com) (recommended on
  Windows) first, then run setup. See [PROFILES.md](PROFILES.md).
