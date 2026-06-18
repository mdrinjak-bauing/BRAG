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
if [ -f "$CFG" ] && grep -q "academic-rag-and-second-brain" "$CFG"; then
  echo "  [ OK ]  Claude Desktop is connected to the search tools"
else
  echo "  [FAIL]  Claude Desktop entry missing — re-run setup.command,"
  echo "          then fully quit Claude Desktop (Cmd+Q) and reopen it."
fi

echo
read -n1 -r -p "Press any key to close..."
