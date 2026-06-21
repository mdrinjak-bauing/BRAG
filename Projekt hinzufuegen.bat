@echo off
REM BRAG - add another project: its own knowledge folder, its own search
REM database and its own connector in Claude / LM Studio, alongside the ones you
REM already have. Double-click. Pick a folder anywhere; BRAG creates a WissensWIKI
REM inside it and wires it up. Run this from your installed "BRAG Assistent" folder.
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul 2>nul

echo === BRAG - add a project ===
echo.

if not exist ".ragsetup_home" if not exist ".setup_complete" (
  echo Please run setup.bat first - this adds a project to an existing BRAG install.
  pause
  exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
  echo Docker is not running - open Docker Desktop, wait until it says "running",
  echo then double-click this again.
  pause
  exit /b 1
)

echo === Choose the folder for this project (a picker opens) ===
echo Everything in it is indexed, except the WissensWIKI workspace created inside it.
echo.
del ".ragpick" >nul 2>nul
powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0tools\pick_folder.ps1" "Choose this project's folder - the folder with the documents to index. A 'WissensWIKI' workspace is created inside it."
if not exist ".ragpick" (
  echo No folder chosen ^(or it contained an unsupported character^).
  pause
  exit /b 1
)
set "PROJDIR="
set /p PROJDIR=<".ragpick"
del ".ragpick" >nul 2>nul
if not defined PROJDIR ( echo No folder chosen. & pause & exit /b 1 )

set "PROJNAME="
set /p PROJNAME="Project name (e.g. Dissertation): "
if not defined PROJNAME ( echo No name given. & pause & exit /b 1 )

REM Create + seed the project's WissensWIKI (only when new).
if not exist "%PROJDIR%\WissensWIKI" (
  mkdir "%PROJDIR%\WissensWIKI"
  robocopy "%~dp0vault_template" "%PROJDIR%\WissensWIKI" /E /NFL /NDL /NJH /NJS /NP >nul
)

REM Register the project (migrate the existing install to 'default' first, so its
REM original 'brag' connector survives the first add), then the CLI regenerates
REM docker-compose.override.yml.
echo Registering "%PROJNAME%"...
docker compose run --rm setup python -m brag.projects migrate >nul 2>nul
docker compose run --rm setup python -m brag.projects add "%PROJNAME%" "%PROJDIR%"
if errorlevel 1 (
  echo Could not register the project ^(unsupported folder path?^).
  pause
  exit /b 1
)

REM Recreate the app so the new folder is mounted and watched.
echo Applying...
docker compose up -d

REM Connect the new project to Claude + LM Studio, alongside the existing ones.
REM Quit Claude first so the entry persists (Claude rewrites its config while up).
echo.
REM Ensure Claude is fully closed so the new connector persists (the helper
REM offers to close Claude for you), then write the connectors.
call "%~dp0tools\ensure_claude_closed.bat"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_claude_config.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_lmstudio_config.ps1"

echo.
echo Done! Reopen Claude Desktop - the connector for "%PROJNAME%" appears next to
echo your other ones. Drop documents straight into your project folder:
echo   %PROJDIR%
pause
