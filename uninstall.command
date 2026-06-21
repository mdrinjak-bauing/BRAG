#!/bin/bash
# BRAG - Building Retrieval-Augmented Generation - uninstall / remove a project
# (macOS). You choose: remove ONE project connection (keep BRAG + your other
# projects + all documents), or remove the WHOLE BRAG system (a full Docker clean).
# Double-click is fine; it runs from the "BRAG Assistent" folder. Your documents
# on disk are NEVER deleted.
cd "$(dirname "$0")"

echo "=== BRAG - uninstall ==="
echo
echo "What do you want to remove?"
echo "  [1] One project connection  (keep BRAG and your other projects)"
echo "  [2] The WHOLE BRAG system   (full Docker clean)"
echo "  [C] Cancel"
echo
read -r -p "Choose 1, 2 or C: " MODE

# Quit Claude Desktop fully so a connector write to its config persists - a running
# Claude rewrites that file from memory and would resurrect dead entries. Used by
# BOTH paths.
quit_claude() {
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
}

remove_one() {
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running - start Docker Desktop, then try again."
    read -r -p "Press Enter to close..."; exit 1
  fi
  # The numbered picker + the registry/override/index removal all run in the
  # one-shot setup container (it owns the registry and reaches Qdrant), so the
  # same prompt serves macOS and Windows. Exit: 0 removed, 2 cancelled, 1 error.
  docker compose run --rm setup python -m brag.projects remove-interactive
  rc=$?
  if [ "$rc" = "2" ]; then echo "Cancelled - nothing was changed."; exit 0; fi
  if [ "$rc" != "0" ]; then
    echo "Could not remove the project - see the message above."
    read -r -p "Press Enter to close..."; exit 1
  fi
  echo
  echo "Applying the change to the running app..."
  # --force-recreate so brag-app re-reads the rewritten projects.json (a single-file
  # bind mount pins the old inode until the container is recreated).
  docker compose up -d --force-recreate app
  # Drop the removed project's connector. The merge helpers run via host python3
  # (they pipe the config through the container); warn clearly if python3 is missing
  # rather than silently leaving a dead connector behind.
  if command -v python3 >/dev/null 2>&1; then
    quit_claude
    python3 tools/merge_claude_config.py || true
    python3 tools/merge_lmstudio_config.py || true
  else
    echo
    echo "NOTE: python3 was not found, so the connector list could not be updated."
    echo "The project IS removed, but Claude/LM Studio may still show its dead"
    echo "connector. Install python3, then run 'Verbindung reparieren.command'."
  fi
  echo
  echo "Done - the project connection was removed. BRAG and your other projects stay,"
  echo "and that project's documents on disk are untouched. Reopen Claude Desktop."
  read -r -p "Press Enter to close..."
  exit 0
}

remove_all() {
  echo
  echo "This removes EVERYTHING BRAG put on your machine - a full Docker clean:"
  echo "  - the BRAG containers, network and any leftover one-shot containers"
  echo "  - BOTH Docker volumes: the ~3 GB model cache AND the search index"
  echo "  - the BRAG app image"
  echo "  - the local .env (it holds your API key) + the project registry + override"
  echo "  - the BRAG entries in Claude Desktop and LM Studio (other MCP servers kept)"
  echo
  echo "This KEEPS your documents in every project folder. The search index can be"
  echo "rebuilt from them on a fresh install (re-ingest)."
  echo
  read -r -p "Type y and press Enter to continue (anything else cancels): " CONFIRM
  if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Cancelled - nothing was changed."; exit 0
  fi
  # Quit Claude FIRST so deleting its brag entries actually persists (a running
  # Claude rewrites the file from memory and resurrects the dead connectors).
  quit_claude
  CLAUDE_DIR="$HOME/Library/Application Support/Claude"
  if [ -f "$CLAUDE_DIR/claude_desktop_config.json" ]; then
    echo "Removing the Claude Desktop connections..."
    docker run --rm -v "$CLAUDE_DIR":/cfg -v "$(pwd)/tools":/tools python:3.12-slim python /tools/remove_claude_mcp.py /cfg/claude_desktop_config.json
  fi
  if [ -f "$HOME/.lmstudio/mcp.json" ]; then
    echo "Removing the LM Studio connections..."
    docker run --rm -v "$HOME/.lmstudio":/cfg -v "$(pwd)/tools":/tools python:3.12-slim python /tools/remove_claude_mcp.py /cfg/mcp.json
  fi
  echo "Stopping and removing the containers, network and ALL BRAG volumes..."
  # -p brag pins the project name so teardown works even if .env is already gone;
  # -v removes the named volumes (model cache + search index); --remove-orphans
  # sweeps one-shot setup/run containers; --profile setup includes 'setup'.
  docker compose -p brag --profile setup down -v --remove-orphans
  # Belt-and-suspenders against a missing .env / odd state.
  docker volume rm brag_models_cache brag_qdrant_data >/dev/null 2>&1
  docker rm -f brag-app brag-qdrant brag-setup >/dev/null 2>&1
  docker network rm brag_default >/dev/null 2>&1
  echo "Removing the BRAG image..."
  for ref in "ghcr.io/mdrinjak-bauing/brag" "brag"; do
    IDS="$(docker images -q "$ref" 2>/dev/null)"
    [ -n "$IDS" ] && docker rmi -f $IDS >/dev/null 2>&1
  done
  rm -f .env .setup_complete projects.json docker-compose.override.yml
  echo
  echo "Verifying the Docker clean-up..."
  if docker ps -a --filter "name=brag-" --format '{{.Names}}' | grep -q . \
     || docker volume ls -q | grep -Eqx "brag_(models_cache|qdrant_data)"; then
    echo "  Note: some BRAG Docker items remain - re-run this, or check 'docker ps -a'."
  else
    echo "  [ OK ]  No BRAG containers or volumes remain."
  fi
  echo
  echo "Done - BRAG is uninstalled and Docker is clean."
  echo "  KEPT: your documents in every project folder."
  echo "  The base images (Qdrant, Python) are left in case other tools use them."
  echo "  You can delete this 'BRAG Assistent' folder now."
  read -r -p "Press Enter to close..."
  exit 0
}

case "$MODE" in
  1) remove_one;;
  2) remove_all;;
  C|c) echo "Cancelled - nothing was changed.";;
  *) echo "Invalid choice - nothing was changed.";;
esac
