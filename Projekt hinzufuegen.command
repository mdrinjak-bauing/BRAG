#!/bin/bash
# BRAG - add another project: its own knowledge folder, its own search database
# and its own connector in Claude / LM Studio, alongside the ones you have.
# Double-click. Pick a folder anywhere; BRAG creates a WissensWIKI inside it and
# wires it up. Run from your installed "RAG Setup" folder.
cd "$(dirname "$0")"

echo "=== BRAG - add a project ==="
echo

if [ ! -f ".ragsetup_home" ] && [ ! -f ".setup_complete" ]; then
  echo "Please run setup.command first - this adds a project to an existing install."
  read -r -p "Press Enter to close..."
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running - open Docker Desktop, then double-click this again."
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "=== Choose the folder for this project (a picker opens) ==="
PROJDIR="$(osascript -e 'POSIX path of (choose folder with prompt "Choose the folder for this project. A WissensWIKI is created inside it.")' 2>/dev/null)"
PROJDIR="${PROJDIR%/}"
[ -n "$PROJDIR" ] || { echo "No folder chosen."; read -r -p "Press Enter to close..."; exit 1; }

# Reject '$' (Docker Compose would interpolate the mounted path).
case "$PROJDIR" in
  *'$'*) echo "That folder path contains a '\$', which Docker cannot handle - pick another."; read -r -p "Press Enter to close..."; exit 1 ;;
esac

printf "Project name (e.g. Dissertation): "
read -r PROJNAME
[ -n "$PROJNAME" ] || { echo "No name given."; read -r -p "Press Enter to close..."; exit 1; }

# Create + seed the project's WissensWIKI (only when new).
if [ ! -d "$PROJDIR/WissensWIKI" ]; then
  mkdir -p "$PROJDIR/WissensWIKI"
  cp -R vault_template/. "$PROJDIR/WissensWIKI"/ 2>/dev/null || true
fi

echo "Registering \"$PROJNAME\"..."
docker compose run --rm setup python -m brag.projects migrate >/dev/null 2>&1
if ! docker compose run --rm setup python -m brag.projects add "$PROJNAME" "$PROJDIR"; then
  echo "Could not register the project."
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "Applying..."
docker compose up -d >/dev/null 2>&1

# Connect to Claude (after it is fully quit, so it persists) + LM Studio.
if command -v python3 >/dev/null 2>&1; then
  while pgrep -x Claude >/dev/null 2>&1; do
    echo
    echo "Claude Desktop is still running - quit it fully so the connector persists"
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
echo "Done! Reopen Claude Desktop - the connector for \"$PROJNAME\" appears next to"
echo "your other ones. Drop documents into: $PROJDIR/WissensWIKI/sources/"
read -r -p "Press Enter to close..."
