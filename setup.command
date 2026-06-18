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

echo "Building the application (first run downloads ~3 GB, please be patient)..."
docker compose build || { echo "Build failed — see message above."; read -r -p "Press Enter to close..."; exit 1; }

echo "Starting the setup assistant..."
rm -f .setup_complete
# If a previous session left the app running, stop it so the setup service can
# use the bridge port (no-op on a fresh install).
docker compose stop app >/dev/null 2>&1
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
while [ ! -f .setup_complete ]; do
  sleep 2
done

echo "Applying your settings..."
# Tear down the setup service (frees the port and drops its mounts), then start
# the persistent app — which never mounts the project dir or the Claude config.
docker compose --profile setup rm -sf setup >/dev/null 2>&1
docker compose up -d >/dev/null 2>&1

echo
echo "All done! Quit Claude Desktop completely (Cmd+Q) and reopen it."
read -r -p "Press Enter to close..."
