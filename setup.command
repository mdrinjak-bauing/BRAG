#!/bin/bash
# BRAG — Building Retrieval-Augmented Generation — one-click setup for macOS.
# Double-click this file. It starts the app and opens the setup assistant
# in your browser; this window finishes the restart afterwards.
cd "$(dirname "$0")"

echo "=== BRAG — Building Retrieval-Augmented Generation ==="
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

# Remember where Claude Desktop keeps its config (used by the wizard)
CLAUDE_DIR="$HOME/Library/Application Support/Claude"
mkdir -p "$CLAUDE_DIR"
if [ ! -f .env ]; then
  echo "CLAUDE_CONFIG_DIR=$CLAUDE_DIR" > .env
elif ! grep -q "^CLAUDE_CONFIG_DIR=" .env; then
  echo "CLAUDE_CONFIG_DIR=$CLAUDE_DIR" >> .env
fi
export CLAUDE_CONFIG_DIR="$CLAUDE_DIR"

# REQUIRED step: choose the knowledge folder (RAG connection folder) via a native
# macOS folder picker, then store it as VAULT_PATH in .env. On cancel/failure it
# falls back to the default folder and never blocks setup.
echo "=== Choose your knowledge folder (a folder-picker window opens) ==="
RAGDIR="$(osascript -e 'POSIX path of (choose folder with prompt "Choose your BRAG knowledge folder (RAG connection folder)")' 2>/dev/null)"
if [ -n "$RAGDIR" ]; then
  if [ -f .env ]; then grep -v '^[[:space:]]*VAULT_PATH[[:space:]]*=' .env > .env.tmp && mv .env.tmp .env; fi
  echo "VAULT_PATH=$RAGDIR" >> .env
  echo "  RAG connection folder: $RAGDIR"
else
  echo "  No folder chosen — the default folder (RAG-Verbindungsordner/) will be used."
fi

# Prefer the prebuilt image from GHCR (fast, avoids local build errors); fall
# back to building locally if none is published yet or we're offline.
echo "Fetching the prebuilt application image..."
if ! docker compose pull app >/dev/null 2>&1; then
  echo "No prebuilt image available — building it locally (first run downloads ~3 GB)..."
  docker compose build || { echo "Build failed — see message above."; read -r -p "Press Enter to close..."; exit 1; }
fi

echo "Starting the setup assistant..."
rm -f .setup_complete
# If a previous session left the app running, stop it so the setup service can
# use the bridge port (no-op on a fresh install).
docker compose stop app >/dev/null 2>&1
# Remove any leftover one-shot setup container from a previous, INTERRUPTED run.
# Its container_name (brag-setup) is fixed, so a leftover (even from a different
# project folder) blocks the new one by name — clear it so compose can recreate.
docker rm -f brag-setup >/dev/null 2>&1
# Only the one-shot setup service runs now — it serves the wizard and is the
# only container that mounts the project dir + Claude Desktop config.
docker compose --profile setup up -d setup || { echo "Start failed — see message above."; read -r -p "Press Enter to close..."; exit 1; }

echo
echo "Opening the setup assistant in your browser..."
sleep 3
# Honour a custom BRIDGE_HOST_PORT from .env (set it there if 8765 is taken).
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
# Tear down the setup service (frees the port and drops its mounts), then start
# the persistent app — which never mounts the project dir or the Claude config.
docker compose --profile setup rm -sf setup >/dev/null 2>&1
docker compose up -d >/dev/null 2>&1

echo
echo "All done! Quit Claude Desktop completely (Cmd+Q) and reopen it."
read -r -p "Press Enter to close..."
