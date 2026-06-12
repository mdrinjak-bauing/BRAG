#!/bin/bash
# Academic Second Brain — one-click setup for macOS.
# Double-click this file. It starts the app and opens the setup assistant
# in your browser; this window finishes the restart afterwards.
cd "$(dirname "$0")"

echo "=== Academic Second Brain ==="
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

echo "Starting..."
rm -f .setup_complete
docker compose up -d || { echo "Start failed — see message above."; read -r -p "Press Enter to close..."; exit 1; }

echo
echo "Opening the setup assistant in your browser..."
sleep 3
open "http://localhost:8765/setup"

echo
echo "Finish the setup in your browser — this window waits for you."
while [ ! -f .setup_complete ]; do
  sleep 2
done

echo "Applying your settings..."
docker compose up -d --force-recreate app >/dev/null 2>&1

echo
echo "All done! Quit Claude Desktop completely (Cmd+Q) and reopen it."
read -r -p "Press Enter to close..."
