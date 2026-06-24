@echo off
REM BRAG - Building Retrieval-Augmented Generation - one-click UPDATE for Windows.
REM Rebuilds the app with the latest code and restarts it WITHOUT touching your
REM data: your .env, the search index (Qdrant volume), the connectors and your
REM project folder all stay. This is an UPDATE, not a reinstall.
cd /d "%~dp0"

echo === BRAG - Update ===
echo.

REM 1. Docker running?
docker info >nul 2>&1
if errorlevel 1 goto no_docker
echo   [ OK ]  Docker is running

REM 2. Get the latest code if this folder is a git checkout. A ZIP install has
REM    no .git - download the new ZIP, extract it over this folder (keep .env),
REM    then run this again; we build whatever source is here.
if not exist ".git" goto no_git
where git >nul 2>&1
if errorlevel 1 goto no_git
echo   [ .. ]  Fetching the latest code (git)...
git pull --ff-only
if errorlevel 1 goto git_dirty
echo   [ OK ]  Code updated
goto build

:git_dirty
echo   [note]  Could not fast-forward (local changes / different branch) -
echo           building the code currently in this folder.
goto build

:no_git
echo   [note]  Not a git checkout - building the code currently in this folder.
echo           ZIP install? Re-download the new ZIP, extract it over this
echo           folder keeping your .env, then run this again.

:build
echo.
echo   [ .. ]  Rebuilding the app (this can take a few minutes)...
docker compose build
if errorlevel 1 goto build_failed
echo   [ OK ]  App image rebuilt
echo   [ .. ]  Restarting...
docker compose up -d
echo.
echo   [ OK ]  BRAG is up to date and running.
echo.
echo   Your .env, search index, connectors and documents were kept.
echo   Folder-exclusion and the page-link change work right away. To try the new
echo   SETUP wizard ^(model dropdown / exclude-folder picker^), run setup.bat
echo   once - it is data-safe ^(it does NOT delete your index^).
echo.
pause
exit /b 0

:no_docker
echo   [FAIL]  Docker is not running - open Docker Desktop, wait until it
echo           says "running", then run this again.
echo.
pause
exit /b 1

:build_failed
echo   [FAIL]  Build failed - see the messages above.
echo.
pause
exit /b 1
