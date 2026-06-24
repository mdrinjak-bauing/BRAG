#!/bin/bash
# BRAG — Building Retrieval-Augmented Generation — one-click UPDATE for macOS.
# Rebuilds the app with the latest code and restarts it WITHOUT touching your
# data: your .env, the search index (Qdrant volume), the connectors and your
# project folder all stay. This is an UPDATE, not a reinstall.
cd "$(dirname "$0")"

echo "=== BRAG — Update ==="
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

# 2. Get the latest code IF this folder is a git checkout. A ZIP install has no
#    .git — download the new ZIP and extract it over this folder (keep your
#    .env), then run this again; we build whatever source is here.
if [ -d .git ] && command -v git >/dev/null 2>&1; then
  echo "  [ .. ]  Fetching the latest code (git)…"
  if git pull --ff-only; then
    echo "  [ OK ]  Code updated"
  else
    echo "  [note]  Could not fast-forward (local changes / different branch) —"
    echo "          building the code currently in this folder."
  fi
else
  echo "  [note]  Not a git checkout — building the code currently in this folder."
  echo "          (ZIP install? Re-download the new ZIP, extract it over this"
  echo "          folder keeping your .env, then run this again.)"
fi
echo

# 3. Rebuild the app image and restart. The first build can take several minutes.
#    The named Qdrant volume (your index) and your .env are never touched.
echo "  [ .. ]  Rebuilding the app (this can take a few minutes)…"
if ! docker compose build; then
  echo "  [FAIL]  Build failed — see the messages above."
  echo
  read -n1 -r -p "Press any key to close..."
  exit 1
fi
echo "  [ OK ]  App image rebuilt"

echo "  [ .. ]  Restarting…"
docker compose up -d
echo
echo "  [ OK ]  BRAG is up to date and running."
echo
echo "  Your .env, search index, connectors and documents were kept."
echo "  Folder-exclusion and the page-link change work right away. To try the new"
echo "  SETUP wizard (model dropdown · exclude-folder picker), run setup.command"
echo "  once — it is data-safe (it does NOT delete your index)."
echo
read -n1 -r -p "Press any key to close..."
