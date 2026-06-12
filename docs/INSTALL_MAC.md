# Install on macOS

Time needed: ~15 minutes (most of it is downloads).

## 1. Install Docker Desktop

1. Download from <https://www.docker.com/products/docker-desktop/> (choose "Apple Silicon" for M-series Macs, "Intel" otherwise).
2. Open the downloaded file, drag Docker into Applications, open it once.
3. Wait until the whale icon in the menu bar stops animating.

## 2. Install Claude Desktop

Download from <https://claude.com/download> and install. Sign in once.

## 3. Get a free Gemini API key (Cloud profile)

1. Go to <https://aistudio.google.com/apikey> (Google account required).
2. Click "Create API key" and copy it — you'll paste it into the setup.

## 4. Download and set up Studiolo

1. On the GitHub page, click the green **Code** button → **Download ZIP**, unpack it (e.g. into your home folder — see note below about iCloud).
2. Double-click **`setup.command`**.
   - If macOS blocks it ("unidentified developer"): right-click → Open → Open.
3. Answer the three questions (profile, API key, document language).
4. When the wizard finishes, **quit Claude Desktop completely (Cmd+Q)** and reopen it.

## 5. First document

Put a PDF into the `vault/sources/` folder. Within ~30 seconds the indexing
starts (watch it with `docker compose logs -f app` if you're curious — but
you don't have to). Then ask Claude:

> What documents are in my knowledge base?

## Notes

- **iCloud:** It is fine to keep the project folder (and the vault) in an
  iCloud-synced location — the database itself lives inside Docker, safely
  outside any sync folder.
- **Stopping/starting:** Docker Desktop starts the app automatically. To stop
  everything: open Terminal in the project folder and run `docker compose down`.
  To start again: `docker compose up -d`.
- **Profiles B/C:** install [LM Studio](https://lmstudio.ai) or
  [Ollama](https://ollama.com) first, load a model, then run setup. See
  [PROFILES.md](PROFILES.md).
