#!/bin/bash
# BRAG — Building Retrieval-Augmented Generation — one-click setup for macOS.
# Double-click this file. On the FIRST run from the unpacked ZIP it asks where
# your "RAG connection folder" should live, copies itself in there as
# "RAG Setup" next to a "WissensWIKI" knowledge folder, and continues from that
# new location. It then starts the app and opens the setup assistant in your
# browser; this window finishes the restart afterwards.
cd "$(dirname "$0")"

echo "=== BRAG — Building Retrieval-Augmented Generation ==="
echo

# ============ FIRST RUN: relocate into the chosen RAG connection folder ============
if [ ! -f ".ragsetup_home" ] && [ ! -f ".setup_complete" ]; then
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

  echo "=== Choose WHERE your BRAG folder should be created ==="
  echo "A 'RAG connection folder' with your knowledge (WissensWIKI) and the"
  echo "program (RAG Setup) will be placed inside it. A picker window opens..."
  RAGDIR="$(osascript -e 'POSIX path of (choose folder with prompt "Choose WHERE your BRAG folder should be created. WissensWIKI (your documents + notes) and RAG Setup (the program) go inside it.")' 2>/dev/null)"
  RAGDIR="${RAGDIR%/}"

  # Reject a literal '$' in the chosen path: Docker Compose interpolates the
  # bind-mount source, and a '$' there cannot be round-tripped (raw is eaten,
  # doubled survives as $$), so it would silently mount the WRONG/empty folder.
  # Fall back to an in-place install (its default ./WissensWIKI has no '$').
  case "$RAGDIR" in
    *'$'*)
      echo "  That folder path contains a '\$', which Docker cannot handle — installing in this folder instead."
      RAGDIR="" ;;
  esac

  # Never relocate INTO the unpacked folder itself (or a subfolder of it): the
  # copy source is the current dir, so the destination would sit inside the
  # source and copy itself. Install in place in that case.
  if [ -n "$RAGDIR" ]; then
    SRC_REAL="$(pwd -P)"
    RAG_REAL="$(cd "$RAGDIR" 2>/dev/null && pwd -P || printf '%s' "$RAGDIR")"
    case "$RAG_REAL/" in
      "$SRC_REAL"/*)
        echo "  That location is inside the unpacked folder — installing in this folder instead."
        RAGDIR="" ;;
    esac
  fi

  if [ -z "$RAGDIR" ]; then
    echo "  Installing in this folder (no separate connection folder)."
  else
    TARGET="$RAGDIR/RAG Setup"
    VAULTDIR="$RAGDIR/WissensWIKI"

    if [ -f "$TARGET/.ragsetup_home" ]; then
      echo "BRAG is already installed at: $TARGET — continuing there..."
      open "$TARGET/setup.command"
      exit 0
    fi

    echo
    echo "Setting up your RAG connection folder:"
    echo "  $RAGDIR"
    echo "      /WissensWIKI   (your documents and notes)"
    echo "      /RAG Setup     (the program)"

    # Create + seed the knowledge folder right away (only when new, so a re-run
    # never overwrites your documents or edited CLAUDE.md). The app also seeds
    # anything still missing on first start.
    if [ ! -d "$VAULTDIR" ]; then
      mkdir -p "$VAULTDIR"
      cp -R vault_template/. "$VAULTDIR"/ 2>/dev/null || true
    fi
    mkdir -p "$TARGET"

    # Copy the program into <RAGDIR>/RAG Setup. Anchored excludes (leading slash)
    # skip ONLY a top-level destination/knowledge folder, plus VCS/caches and
    # per-install files written fresh in the new copy. No cp fallback: the
    # containment guard above already ruled out a self-copy, a bare cp could
    # recurse, and a failed rsync is caught by the check below.
    rsync -a \
      --exclude='/RAG Setup/' --exclude='/WissensWIKI/' \
      --exclude='/RAG-Verbindungsordner/' --exclude='/wissensspeicher/' --exclude='/vault/' \
      --exclude='.git' --exclude='.env' --exclude='.ragpick' \
      --exclude='.ragsetup_home' --exclude='.setup_complete' \
      --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
      ./ "$TARGET"/
    if [ ! -f "$TARGET/setup.command" ]; then
      echo "The copy did not include setup.command — cannot continue safely."
      echo "Please move this folder into your RAG connection folder by hand."
      read -r -p "Press Enter to close..."
      exit 1
    fi

    # Marker (records the RAG connection folder) + a fresh bootstrap .env that the
    # wizard rewrites later. The chosen path has no '$' (rejected above), so the
    # values are written raw. Don't clobber an existing .env (keeps an API key if
    # the marker was removed by hand). The compose project name is left to default
    # (the stable "RAG Setup" folder), so the search-index volume stays attached.
    CLAUDE_DIR="$HOME/Library/Application Support/Claude"
    printf '%s\n' "$RAGDIR" > "$TARGET/.ragsetup_home"
    if [ ! -f "$TARGET/.env" ]; then
      {
        echo "CLAUDE_CONFIG_DIR=$CLAUDE_DIR"
        echo "VAULT_PATH=$VAULTDIR"
      } > "$TARGET/.env"
    fi
    chmod +x "$TARGET/setup.command" "$TARGET/status.command" 2>/dev/null || true

    echo
    echo "Organized. Continuing setup from the new location (a new window opens)..."
    open "$TARGET/setup.command"
    echo
    echo "You can close this window and delete this original unpacked folder now —"
    echo "everything lives in your RAG connection folder from here on."
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
docker compose --profile setup up -d setup || { echo "Start failed — see message above."; read -r -p "Press Enter to close..."; exit 1; }

echo
echo "Opening the setup assistant in your browser..."
sleep 3
PORT="$(grep -E '^BRIDGE_HOST_PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2 | tr -d '[:space:]')"
open "http://localhost:${PORT:-8765}/setup"

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
  echo "All done! Your knowledge lives in the WissensWIKI folder next to this one."
  echo "Quit Claude Desktop completely (Cmd+Q) and reopen it."
else
  echo "Almost done — but the Claude Desktop connection could not be confirmed."
  echo "Run status.command to check it, or re-run setup.command. Config file:"
  echo "  $CLAUDE_DIR/claude_desktop_config.json"
fi
echo "(If you use LM Studio, also fully restart it so the new connection loads.)"
read -r -p "Press Enter to close..."
