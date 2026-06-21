#!/bin/bash
# BRAG — Building Retrieval-Augmented Generation — one-click status check for macOS.
# Double-click this file to see whether the whole system is working.
cd "$(dirname "$0")"

echo "=== BRAG — Status check ==="
echo

# 1. Docker running?
if ! docker info >/dev/null 2>&1; then
  echo "  [FAIL]  Docker is not running — open Docker Desktop, wait for the"
  echo "          whale icon to stop animating, then run this again."
  echo
  read -n1 -r -p "Press any key to close..."
  exit 1
fi
echo "  [ OK ]  Docker is running"

# 2. Containers up?
for c in brag-qdrant brag-app; do
  if docker ps --format '{{.Names}}' | grep -qx "$c"; then
    echo "  [ OK ]  Container $c is up"
  else
    echo "  [FAIL]  Container $c is NOT up — run:  docker compose up -d"
  fi
done
echo

# 3. Deep checks inside the app container (Qdrant, corpus, watcher, AI backend)
if docker ps --format '{{.Names}}' | grep -qx 'brag-app'; then
  docker exec brag-app python -m brag.health
  echo
fi

# 4. Claude Desktop wired up?
CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [ ! -f "$CFG" ]; then
  echo "  [FAIL]  Claude Desktop config not found at:"
  echo "          $CFG"
  echo "          Fix: start Claude Desktop once so it creates the config, then"
  echo "          re-run setup.command."
elif grep -q "brag.mcp_server" "$CFG"; then
  echo "  [ OK ]  Claude Desktop is connected to the BRAG tools"
else
  echo "  [FAIL]  Claude Desktop BRAG connection 'brag' missing in:"
  echo "          $CFG"
  echo "          Fix: re-run setup.command (it shows the exact entry to paste if"
  echo "          it cannot write it), then fully quit Claude Desktop (Cmd+Q) and"
  echo "          reopen it."
fi

# LM Studio wired up (only if LM Studio is installed)?
LMS="$HOME/.lmstudio/mcp.json"
if [ -f "$LMS" ]; then
  if grep -q "brag.mcp_server" "$LMS"; then
    echo "  [ OK ]  LM Studio is connected to the BRAG tools"
  else
    echo "  [note]  LM Studio is installed but not connected - re-run setup.command,"
    echo "          then fully restart LM Studio."
  fi
fi

echo
read -n1 -r -p "Press any key to close..."
