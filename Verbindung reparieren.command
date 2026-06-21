#!/bin/bash
# BRAG - repair / refresh the Claude Desktop (+ LM Studio) connections.
# Double-click if a BRAG connector is missing after adding/removing a project or
# changing settings. It fully closes Claude (so the entry persists), then
# re-writes ALL BRAG connectors from the project registry.
cd "$(dirname "$0")"

echo "=== BRAG - repair connections ==="
echo

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running - start Docker Desktop, then try again."
  read -r -p "Press Enter to close..."
  exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -q '^brag-app$'; then
  echo "BRAG is not running yet - double-click setup.command first, then try again."
  read -r -p "Press Enter to close..."
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  # Close Claude first (it rewrites its config while running and would drop the
  # entry), then sync all brag/brag-<project> connectors from the registry.
  while pgrep -x Claude >/dev/null 2>&1; do
    echo
    echo "Claude Desktop is still running - quit it fully so the connectors persist"
    echo "(it keeps running after you close the window)."
    printf "  Type Q to let BRAG quit Claude, or quit it yourself then press Enter: "
    read -r ans
    if [ "$ans" = "Q" ] || [ "$ans" = "q" ]; then
      osascript -e 'quit app "Claude"' >/dev/null 2>&1 || pkill -x Claude 2>/dev/null || true
    fi
    sleep 2
  done
  echo "Writing the BRAG connectors..."
  python3 tools/merge_claude_config.py || true
  python3 tools/merge_lmstudio_config.py || true
  echo
  echo "Done. Open Claude Desktop again - all your BRAG connectors should be there."
  echo "(If you use LM Studio, fully restart it too.)"
else
  echo "python3 is not available - add the BRAG entries by hand (see README)."
fi
read -r -p "Press Enter to close..."
