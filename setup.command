#!/bin/bash
# Academic Second Brain — one-click setup for macOS.
# Double-click this file (or run it in Terminal).
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

echo "Building the application (first run downloads ~3 GB, please be patient)..."
docker compose build || { echo "Build failed — see message above."; read -r -p "Press Enter to close..."; exit 1; }

CLAUDE_DIR="$HOME/Library/Application Support/Claude"
mkdir -p "$CLAUDE_DIR"

echo
docker compose run --rm \
  -v "$PWD":/workspace \
  -v "$CLAUDE_DIR":/claude-config \
  app python -m asb.setup_wizard || { read -r -p "Press Enter to close..."; exit 1; }

echo
echo "Starting the application..."
docker compose up -d

echo
echo "All running. Quit Claude Desktop completely (Cmd+Q) and reopen it."
read -r -p "Press Enter to close..."
