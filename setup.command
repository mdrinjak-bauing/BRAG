#!/bin/bash
# BRAG — Building Retrieval-Augmented Generation — one-click setup for macOS.
# Double-click this file. On the FIRST run from the unpacked ZIP it asks (1) WHERE
# the "BRAG Assistent" program should live and (2) your PROJECT folder (your
# documents). It copies itself into "BRAG Assistent", creates a WissensWIKI
# workspace inside your project, then continues from the new location, builds the
# app and opens the setup assistant in your browser.
cd "$(dirname "$0")"

echo "=== BRAG — Building Retrieval-Augmented Generation ==="
echo

# ============ FIRST RUN: install the program + pick a project folder ============
if [ ! -f ".ragsetup_home" ] && [ ! -f ".setup_complete" ]; then
  echo "First-time install — this asks you for TWO folders (program + documents)."
  echo "ALREADY have BRAG installed (e.g. you just unpacked an update ZIP)?"
  echo "Then DON'T continue here: copy these files into your existing"
  echo "'BRAG Assistent' folder and double-click setup.command THERE — it skips"
  echo "the folder questions and goes straight to the settings."
  echo
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed."
    echo "Please install Docker Desktop first: https://www.docker.com/products/docker-desktop/"
    echo "Then double-click this file again."
    read -r -p "Press Enter to close..."
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but not running."
    echo "Please open the Docker Desktop app, wait until it says 'running',"
    echo "then double-click this file again."
    read -r -p "Press Enter to close..."
    exit 1
  fi

  # ── Step 1 of 2: where the BRAG Assistent program should live ──────────────
  echo "=== Step 1 of 2: where should the BRAG Assistent (the program) live? ==="
  echo "A 'BRAG Assistent' folder is created there — it IS the tool; keep it, don't delete it."
  ENGINEPARENT="$(osascript -e 'POSIX path of (choose folder with prompt "Step 1/2: choose WHERE the BRAG Assistent program should live. A BRAG Assistent folder is created there — do not delete it later.")' 2>/dev/null)"
  ENGINEPARENT="${ENGINEPARENT%/}"

  # Reject a literal '$' (Docker Compose interpolates the bind-mount source and a
  # '$' cannot be round-tripped) — fall back to an in-place program install.
  case "$ENGINEPARENT" in
    *'$'*)
      echo "  That path contains a '\$' — installing the program in this folder instead."
      ENGINEPARENT="" ;;
  esac

  # Never relocate INTO the unpacked folder itself (the copy would copy itself).
  if [ -n "$ENGINEPARENT" ]; then
    SRC_REAL="$(pwd -P)"
    ENG_REAL="$(cd "$ENGINEPARENT" 2>/dev/null && pwd -P || printf '%s' "$ENGINEPARENT")"
    case "$ENG_REAL/" in
      "$SRC_REAL"/*)
        echo "  That location is inside the unpacked folder — installing the program here instead."
        ENGINEPARENT="" ;;
    esac
  fi

  INPLACE=0
  if [ -z "$ENGINEPARENT" ]; then INPLACE=1; else ENGINE="$ENGINEPARENT/BRAG Assistent"; fi

  # ── Step 2 of 2: the project folder (the documents to index) ───────────────
  echo
  echo "=== Step 2 of 2: choose your PROJECT folder (your documents) ==="
  echo "Everything in it is indexed, except the WissensWIKI workspace."
  PROJDIR="$(osascript -e 'POSIX path of (choose folder with prompt "Step 2/2: choose your PROJECT folder — the folder with the documents to index. A WissensWIKI workspace is created inside it.")' 2>/dev/null)"
  PROJDIR="${PROJDIR%/}"
  if [ -z "$PROJDIR" ]; then
    echo "No project folder chosen — cannot continue. Re-run and choose your documents folder."
    read -r -p "Press Enter to close..."
    exit 1
  fi
  case "$PROJDIR" in
    *'$'*)
      echo "That project path contains a '\$', which Docker cannot handle. Choose a folder without it."
      read -r -p "Press Enter to close..."
      exit 1 ;;
  esac

  # Seed the WissensWIKI workspace inside the project (only when new, so a re-run
  # never overwrites your notes). The app also seeds anything missing on start.
  if [ ! -d "$PROJDIR/WissensWIKI" ]; then
    mkdir -p "$PROJDIR/WissensWIKI"
    cp -R vault_template/. "$PROJDIR/WissensWIKI"/ 2>/dev/null || true
  fi

  CLAUDE_DIR="$HOME/Library/Application Support/Claude"

  if [ "$INPLACE" = "1" ]; then
    # Install the program in THIS (unpacked) folder; mark it, then fall through to
    # REAL SETUP below. VAULT_PATH = the PROJECT ROOT (the whole folder is the
    # corpus); the app never mounts the engine, so it never sees .env/scripts.
    bash tools/mark_engine_folder.command "$(pwd -P)" 2>/dev/null || true
    printf '%s\n' "$(pwd -P)" > ".ragsetup_home"
    if [ ! -f ".env" ]; then
      { echo "CLAUDE_CONFIG_DIR=$CLAUDE_DIR"; echo "VAULT_PATH=$PROJDIR"
        echo "COMPOSE_PROJECT_NAME=brag"; } > ".env"
    fi
  else
    if [ -f "$ENGINE/.ragsetup_home" ]; then
      echo "BRAG Assistent already installed at: $ENGINE — continuing there..."
      open "$ENGINE/setup.command"
      exit 0
    fi
    echo
    echo "Installing the program into: $ENGINE"
    mkdir -p "$ENGINE"
    # Anchored excludes skip a top-level engine/workspace folder, plus VCS/caches
    # and per-install files written fresh in the new copy.
    rsync -a \
      --exclude='/BRAG Assistent/' --exclude='/WissensWIKI/' \
      --exclude='.git' --exclude='.env' --exclude='.ragpick' \
      --exclude='.ragsetup_home' --exclude='.setup_complete' \
      --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
      ./ "$ENGINE"/
    if [ ! -f "$ENGINE/setup.command" ]; then
      echo "The copy did not include setup.command — cannot continue safely."
      echo "Please move this folder into place by hand."
      read -r -p "Press Enter to close..."
      exit 1
    fi
    bash "$ENGINE/tools/mark_engine_folder.command" "$ENGINE" 2>/dev/null || true
    printf '%s\n' "$ENGINE" > "$ENGINE/.ragsetup_home"
    if [ ! -f "$ENGINE/.env" ]; then
      # Pin COMPOSE_PROJECT_NAME so the index + model-cache volumes have stable
      # names regardless of the engine folder name.
      { echo "CLAUDE_CONFIG_DIR=$CLAUDE_DIR"; echo "VAULT_PATH=$PROJDIR"
        echo "COMPOSE_PROJECT_NAME=brag"; } > "$ENGINE/.env"
    fi
    chmod +x "$ENGINE/setup.command" "$ENGINE/status.command" 2>/dev/null || true
    echo
    echo "Organized. Continuing setup from the BRAG Assistent folder (a new window opens)..."
    open "$ENGINE/setup.command"
    echo "You can close this window and delete this unpacked folder now."
    read -r -p "Press Enter to close..."
    exit 0
  fi
fi

# ====================== REAL SETUP (runs in the installed copy) ======================
# Remember where Claude Desktop keeps its config (the wizard, inside the
# container, writes the MCP entry there — this works on macOS bind mounts).
CLAUDE_DIR="$HOME/Library/Application Support/Claude"
mkdir -p "$CLAUDE_DIR"
if [ ! -f .env ]; then
  echo "CLAUDE_CONFIG_DIR=$CLAUDE_DIR" > .env
elif ! grep -q "^CLAUDE_CONFIG_DIR=" .env; then
  echo "CLAUDE_CONFIG_DIR=$CLAUDE_DIR" >> .env
fi
export CLAUDE_CONFIG_DIR="$CLAUDE_DIR"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running — open Docker Desktop, wait until it says 'running',"
  echo "then double-click setup.command again."
  read -r -p "Press Enter to close..."
  exit 1
fi

# Prefer the prebuilt image from GHCR (fast); fall back to building locally.
echo "Fetching the prebuilt application image..."
if ! docker compose pull app >/dev/null 2>&1; then
  echo "No prebuilt image available — building it locally (first run downloads ~3 GB)..."
  docker compose build || { echo "Build failed — see message above."; read -r -p "Press Enter to close..."; exit 1; }
fi

echo "Starting the setup assistant..."
rm -f .setup_complete
docker compose stop app >/dev/null 2>&1
docker rm -f brag-setup >/dev/null 2>&1

# Which host port the bridge will publish (default 8765; .env may override).
PORT="$(grep -E '^BRIDGE_HOST_PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2 | tr -d '[:space:]')"
PORT="${PORT:-8765}"
# Preflight AFTER stopping our own app (so we only flag a FOREIGN program): a busy
# port otherwise surfaces only Docker's raw "address already in use" error - a dead
# end for non-technical users. Check first and explain the fix in plain language.
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo
  echo "Port $PORT is already in use by another program (another BRAG, or another"
  echo "tool). BRAG needs it for the setup assistant and the page-precise PDF links."
  echo "Fix it one of two ways, then double-click setup.command again:"
  echo "  - quit the program currently using port $PORT, or"
  echo "  - pick a free port: add these two lines to the .env next to this file,"
  echo "      BRIDGE_HOST_PORT=8770"
  echo "      BRIDGE_PUBLIC_URL=http://localhost:8770"
  read -r -p "Press Enter to close..."
  exit 1
fi

docker compose --profile setup up -d setup || { echo "Start failed — see message above."; read -r -p "Press Enter to close..."; exit 1; }

echo
echo "Opening the setup assistant in your browser..."
sleep 3
open "http://localhost:$PORT/setup"

echo
echo "Finish the setup in your browser — this window waits for you."
echo "(If you closed or cancelled the assistant: close this window and double-click setup.command again.)"
waited=0
while [ ! -f .setup_complete ]; do
  sleep 2
  waited=$((waited + 2))
  if [ $((waited % 30)) -eq 0 ]; then printf "."; fi
  if [ "$waited" -ge 2700 ]; then
    echo
    echo "Timed out after 45 minutes. If you didn't finish the assistant, close this"
    echo "window and run setup.command again."
    docker compose --profile setup rm -sf setup >/dev/null 2>&1
    exit 1
  fi
done
echo

echo "Applying your settings..."
docker compose --profile setup rm -sf setup >/dev/null 2>&1
docker compose up -d >/dev/null 2>&1

# Connect BRAG to Claude Desktop from the HOST. Claude rewrites its config while
# running and would drop an entry added underneath it, so wait until it is fully
# quit, then write — that makes the connection stick (the in-container write
# during the wizard is best-effort and a running Claude can clobber it).
if command -v python3 >/dev/null 2>&1; then
  # Claude rewrites its config while running and would drop the entry, so loop
  # until it is fully quit (it keeps running after the window is closed); offer to
  # quit it. No timeout-write — the entry must never be written while Claude runs.
  while pgrep -x Claude >/dev/null 2>&1; do
    echo
    echo "Claude Desktop is still running - to save the BRAG connection it must be"
    echo "fully quit (it keeps running after you close the window)."
    printf "  Type Q to let BRAG quit Claude, or quit it yourself then press Enter: "
    read -r ans
    if [ "$ans" = "Q" ] || [ "$ans" = "q" ]; then
      osascript -e 'quit app "Claude"' >/dev/null 2>&1 || pkill -x Claude 2>/dev/null || true
    fi
    sleep 2
  done
  echo "Connecting BRAG to Claude Desktop..."
  python3 tools/merge_claude_config.py || true
fi

# Also connect LM Studio if it is installed (its chat is an MCP host too). The
# helper no-ops when LM Studio is absent.
if [ -d "$HOME/.lmstudio" ]; then
  echo
  echo "Connecting BRAG to LM Studio..."
  if command -v python3 >/dev/null 2>&1; then
    python3 tools/merge_lmstudio_config.py || true
  else
    echo "  LM Studio detected but python3 is unavailable - add the 'brag' MCP entry to ~/.lmstudio/mcp.json by hand (see README)."
  fi
fi

echo
# Confirm the container actually wrote the Claude Desktop entry (reliable on a
# macOS bind mount, but verify rather than claim success blindly).
if grep -q '"brag"' "$CLAUDE_DIR/claude_desktop_config.json" 2>/dev/null; then
  echo "All done! Your documents stay in your project folder; this 'BRAG Assistent'"
  echo "folder is the program (don't delete it). Drop more documents into your"
  echo "project folder anytime — they are indexed automatically."
  echo "Quit Claude Desktop completely (Cmd+Q) and reopen it."
else
  echo "Almost done — but the Claude Desktop connection could not be confirmed."
  echo "Run status.command to check it, or re-run setup.command. Config file:"
  echo "  $CLAUDE_DIR/claude_desktop_config.json"
fi
echo "(If you use LM Studio, also fully restart it so the new connection loads.)"
read -r -p "Press Enter to close..."
