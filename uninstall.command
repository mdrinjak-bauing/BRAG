#!/bin/bash
# BRAG - Building Retrieval-Augmented Generation - uninstall for macOS.
# Removes BRAG's containers, the model cache, the app image, the local config
# and the Claude Desktop connection. KEEPS your documents (WissensWIKI/) and
# the search index (the qdrant_data volume), so a re-install finds your corpus
# again. Double-click is fine; it runs from the project folder.
cd "$(dirname "$0")"

echo "=== BRAG - uninstall ==="
echo
echo "This will REMOVE:"
echo "  - the BRAG containers and network"
echo "  - the ~3 GB model cache (re-downloads on a fresh install)"
echo "  - the BRAG app image"
echo "  - the local .env (it holds your API key)"
echo "  - the BRAG entry in Claude Desktop and LM Studio (your other MCP servers are kept)"
echo
echo "This will KEEP:"
echo "  - your documents in WissensWIKI/"
echo "  - the search index (the qdrant_data volume)"
echo
read -r -p "Type y and press Enter to continue (anything else cancels): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
  echo "Cancelled - nothing was changed."
  exit 0
fi

# Capture the compose project name now, while the containers still exist, so we
# can remove exactly this install's model-cache volume later.
PROJ="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' brag-app 2>/dev/null)"
[ -n "$PROJ" ] || PROJ="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' brag-qdrant 2>/dev/null)"

# 1. Remove BRAG's Claude Desktop entry - in a throwaway Python container, so no
#    Python is needed on the host. Backs up the config and keeps other servers.
CLAUDE_DIR="$HOME/Library/Application Support/Claude"
if [ -f "$CLAUDE_DIR/claude_desktop_config.json" ]; then
  echo "Removing the Claude Desktop connection..."
  docker run --rm -v "$CLAUDE_DIR":/cfg -v "$(pwd)/tools":/tools python:3.12-slim python /tools/remove_claude_mcp.py /cfg/claude_desktop_config.json
fi
# Also remove the LM Studio connection if present (same helper; it strips the
# 'brag' key and the legacy name, keeping any other MCP servers).
if [ -f "$HOME/.lmstudio/mcp.json" ]; then
  echo "Removing the LM Studio connection..."
  docker run --rm -v "$HOME/.lmstudio":/cfg -v "$(pwd)/tools":/tools python:3.12-slim python /tools/remove_claude_mcp.py /cfg/mcp.json
fi

# 2. Stop and remove the containers + network. No -v, so the volumes survive.
echo "Stopping and removing the containers..."
docker compose down

# 3. Remove ONLY the model-cache volume; the qdrant_data index stays.
if [ -n "$PROJ" ]; then
  echo "Removing the ~3 GB model cache..."
  docker volume rm "${PROJ}_models_cache" >/dev/null 2>&1
else
  docker volume ls -q --filter "label=com.docker.compose.volume=models_cache" | while read -r v; do
    docker volume rm "$v" >/dev/null 2>&1
  done
fi

# 4. Remove the BRAG app image (shared Qdrant/Python base images are left).
echo "Removing the BRAG image..."
for ref in "ghcr.io/mdrinjak-bauing/brag" "brag"; do
  IDS="$(docker images -q "$ref" 2>/dev/null)"
  [ -n "$IDS" ] && docker rmi -f $IDS >/dev/null 2>&1
done

# 5. Remove local setup state (the .env holds your API key) + the multi-project
#    registry and the generated compose override.
rm -f .env .setup_complete projects.json docker-compose.override.yml

echo
echo "Done - BRAG is uninstalled."
echo "  KEPT: your documents in WissensWIKI/ and the search index."
echo "  You can delete this folder now if you no longer need the documents."
echo "  Docker Desktop and Claude Desktop are untouched - uninstall them the"
echo "  normal way if you only used them for BRAG."
read -r -p "Press Enter to close..."
