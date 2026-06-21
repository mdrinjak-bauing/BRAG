#!/bin/bash
# BRAG - Building Retrieval-Augmented Generation - uninstall / remove a project
# (macOS). You choose: remove ONE project connection (keep BRAG + your other
# projects + all documents), or remove the WHOLE BRAG system. Double-click is
# fine; it runs from the "BRAG Assistent" folder. Your documents are never deleted.
cd "$(dirname "$0")"

echo "=== BRAG - uninstall ==="
echo
echo "What do you want to remove?"
echo "  [1] One project connection  (keep BRAG and your other projects)"
echo "  [2] The WHOLE BRAG system"
echo "  [C] Cancel"
echo
read -r -p "Choose 1, 2 or C: " MODE

remove_one() {
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running - start Docker Desktop, then try again."
    read -r -p "Press Enter to close..."; exit 1
  fi
  echo "Your projects (slug | name | folder | collection):"
  docker compose run --rm setup python -m brag.projects list
  echo
  echo "Note: the 'default' project can only be removed via the full uninstall [2]."
  read -r -p "Type the slug to remove (or C to cancel): " SLUG
  case "$SLUG" in C|c|"") echo "Cancelled - nothing was changed."; exit 0;; esac
  if [ "$SLUG" = "default" ]; then
    echo "The 'default' project is removed only via the full uninstall."
    read -r -p "Press Enter to close..."; exit 0
  fi
  read -r -p "Also delete this project's search index? Your documents stay. (y/N): " DELIDX
  RMFLAG=""
  case "$DELIDX" in y|Y) RMFLAG="--delete-index";; esac
  echo "Removing project '$SLUG'..."
  if ! docker compose run --rm setup python -m brag.projects remove "$SLUG" $RMFLAG; then
    echo "Could not remove '$SLUG' - check the slug from the list above."
    read -r -p "Press Enter to close..."; exit 1
  fi
  echo "Applying..."
  docker compose up -d
  # Drop this project's connector from Claude + LM Studio. Claude rewrites its
  # config while running, so quit it first for the change to persist.
  if command -v python3 >/dev/null 2>&1; then
    while pgrep -x Claude >/dev/null 2>&1; do
      echo
      echo "Claude Desktop is still running - quit it fully so the change persists"
      echo "(it keeps running after you close the window)."
      printf "  Type Q to let BRAG quit Claude, or quit it yourself then press Enter: "
      read -r ans
      if [ "$ans" = "Q" ] || [ "$ans" = "q" ]; then
        osascript -e 'quit app "Claude"' >/dev/null 2>&1 || pkill -x Claude 2>/dev/null || true
      fi
      sleep 2
    done
    python3 tools/merge_claude_config.py || true
    python3 tools/merge_lmstudio_config.py || true
  fi
  echo
  echo "Done - project '$SLUG' removed. BRAG and your other projects stay."
  echo "Its documents on disk are untouched. Reopen Claude Desktop to refresh the list."
  read -r -p "Press Enter to close..."
  exit 0
}

remove_all() {
  echo
  echo "This will REMOVE:"
  echo "  - the BRAG containers and network"
  echo "  - the ~3 GB model cache (re-downloads on a fresh install)"
  echo "  - the BRAG app image"
  echo "  - the local .env (it holds your API key) + the project registry"
  echo "  - the BRAG entries in Claude Desktop and LM Studio (other MCP servers kept)"
  echo
  echo "This will KEEP:"
  echo "  - your documents in every project folder"
  echo "  - the search index (the qdrant_data volume)"
  echo
  read -r -p "Type y and press Enter to continue (anything else cancels): " CONFIRM
  if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Cancelled - nothing was changed."; exit 0
  fi
  # Capture the compose project name now, while the containers still exist.
  PROJ="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' brag-app 2>/dev/null)"
  [ -n "$PROJ" ] || PROJ="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' brag-qdrant 2>/dev/null)"
  # Remove ALL BRAG entries (brag / brag-<project>) from Claude + LM Studio.
  CLAUDE_DIR="$HOME/Library/Application Support/Claude"
  if [ -f "$CLAUDE_DIR/claude_desktop_config.json" ]; then
    echo "Removing the Claude Desktop connections..."
    docker run --rm -v "$CLAUDE_DIR":/cfg -v "$(pwd)/tools":/tools python:3.12-slim python /tools/remove_claude_mcp.py /cfg/claude_desktop_config.json
  fi
  if [ -f "$HOME/.lmstudio/mcp.json" ]; then
    echo "Removing the LM Studio connections..."
    docker run --rm -v "$HOME/.lmstudio":/cfg -v "$(pwd)/tools":/tools python:3.12-slim python /tools/remove_claude_mcp.py /cfg/mcp.json
  fi
  echo "Stopping and removing the containers..."
  docker compose down
  # Remove ONLY the model-cache volume; the qdrant_data index stays.
  if [ -n "$PROJ" ]; then
    echo "Removing the ~3 GB model cache..."
    docker volume rm "${PROJ}_models_cache" >/dev/null 2>&1
  else
    docker volume ls -q --filter "label=com.docker.compose.volume=models_cache" | while read -r v; do
      docker volume rm "$v" >/dev/null 2>&1
    done
  fi
  echo "Removing the BRAG image..."
  for ref in "ghcr.io/mdrinjak-bauing/brag" "brag"; do
    IDS="$(docker images -q "$ref" 2>/dev/null)"
    [ -n "$IDS" ] && docker rmi -f $IDS >/dev/null 2>&1
  done
  # Remove local setup state (.env holds the API key) + registry + override.
  rm -f .env .setup_complete projects.json docker-compose.override.yml
  echo
  echo "Done - BRAG is uninstalled."
  echo "  KEPT: your documents in every project folder + the search index."
  echo "  You can delete this 'BRAG Assistent' folder now if you no longer need it."
  echo "  Docker Desktop and Claude Desktop are untouched."
  read -r -p "Press Enter to close..."
  exit 0
}

case "$MODE" in
  1) remove_one;;
  2) remove_all;;
  *) echo "Cancelled - nothing was changed.";;
esac
