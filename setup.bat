@echo off
REM BRAG - Building Retrieval-Augmented Generation - one-click setup for Windows.
REM Double-click this file. On the FIRST run from the unpacked ZIP it asks (1)
REM WHERE the "BRAG Assistent" program should live and (2) your PROJECT folder
REM (your documents). It copies itself into "BRAG Assistent", creates a WissensWIKI
REM workspace inside your project, then continues from the new location, builds the
REM app and opens the setup assistant in your browser.
setlocal EnableExtensions
cd /d "%~dp0"
REM UTF-8 so a folder path with non-ASCII characters (e.g. German umlauts)
REM round-trips correctly through .ragpick and into .env.
chcp 65001 >nul 2>nul

echo === BRAG - Building Retrieval-Augmented Generation ===
echo.

REM If this copy is already the installed BRAG Assistent (marker present), or a
REM previous run already finished setup here, skip relocation and run the wizard.
if exist ".ragsetup_home" goto real_setup
if exist ".setup_complete" goto real_setup

REM ============ FIRST RUN: install the program + pick a project folder ============

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker is not installed.
  echo Please install Docker Desktop first: https://www.docker.com/products/docker-desktop/
  echo Then double-click this file again.
  pause
  exit /b 1
)

REM Pre-flight: hardware virtualization must be on for Docker's engine to start.
set "VTON=1"
for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "try{[int][bool](Get-CimInstance Win32_Processor).VirtualizationFirmwareEnabled}catch{1}"`) do set "VTON=%%V"

docker info >nul 2>nul
if errorlevel 1 (
  echo Docker is installed but not running.
  echo.
  if "%VTON%"=="0" (
    echo IMPORTANT: Hardware virtualization is DISABLED in your BIOS/UEFI -
    echo Docker's engine cannot start without it. To fix:
    echo   1. Restart and open the BIOS/UEFI ^(usually the Del or F2 key at boot^).
    echo   2. Enable virtualization - on AMD look for "SVM Mode",
    echo      on Intel for "Intel VT-x" / "Virtualization Technology".
    echo   3. Save ^& exit, let Windows boot, open Docker Desktop, then run this again.
  ) else (
    echo Please open the Docker Desktop app, wait until it says "running",
    echo then double-click this file again.
  )
  pause
  exit /b 1
)

REM ── Step 1 of 2: where the BRAG Assistent program should live ────────────────
echo === Step 1 of 2: where should the BRAG Assistent (the program) live? ===
echo A "BRAG Assistent" folder is created there - it IS the tool; keep it, don't
echo delete it. A picker window opens...
echo.
del ".ragpick" >nul 2>nul
powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0tools\pick_folder.ps1" "Step 1/2: choose WHERE the BRAG Assistent program should live. A 'BRAG Assistent' folder is created there - please do not delete it later."
set "INPLACE="
set "ENGINEPARENT="
if not exist ".ragpick" goto step1_done
set /p ENGINEPARENT=<".ragpick"
del ".ragpick" >nul 2>nul
:step1_done
if not defined ENGINEPARENT set "INPLACE=1"
if not defined INPLACE set "ENGINE=%ENGINEPARENT%\BRAG Assistent"

REM ── Step 2 of 2: the project folder (the documents to index) ─────────────────
echo.
echo === Step 2 of 2: choose your PROJECT folder (your documents) ===
echo Everything in it is indexed, except the WissensWIKI workspace. A picker opens...
echo.
del ".ragpick" >nul 2>nul
powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0tools\pick_folder.ps1" "Step 2/2: choose your PROJECT folder - the folder with the documents to index. A 'WissensWIKI' workspace is created inside it."
if not exist ".ragpick" (
  echo No project folder chosen - cannot continue. Re-run and choose your documents folder.
  pause
  exit /b 1
)
set "PROJDIR="
set /p PROJDIR=<".ragpick"
del ".ragpick" >nul 2>nul
if not defined PROJDIR (
  echo No project folder chosen.
  pause
  exit /b 1
)

REM Seed the WissensWIKI workspace inside the project (Passagen + guides), only
REM when new, so a re-run never overwrites your notes. Flat (no parenthesized
REM block) so a project path containing parentheses cannot break it.
if exist "%PROJDIR%\WissensWIKI" goto seeded
mkdir "%PROJDIR%\WissensWIKI"
robocopy "%~dp0vault_template" "%PROJDIR%\WissensWIKI" /E /NFL /NDL /NJH /NJS /NP >nul
:seeded

if defined INPLACE goto engine_inplace

REM ── Relocate the program into the BRAG Assistent folder ──────────────────────
if not exist "%ENGINE%\.ragsetup_home" goto do_relocate
echo BRAG Assistent already installed at: %ENGINE% - continuing there...
start "" "%ENGINE%\setup.bat"
exit /b 0
:do_relocate
if not exist "%ENGINE%" mkdir "%ENGINE%"
robocopy "%~dp0." "%ENGINE%" /E /NFL /NDL /NJH /NJS /NP /XD ".git" "%ENGINE%" /XF ".ragpick" ".env" ".setup_complete" .ragsetup_home >nul
if errorlevel 8 goto relocate_failed
if not exist "%ENGINE%\setup.bat" goto relocate_failed
call "%~dp0tools\mark_engine_folder.bat" "%ENGINE%"
REM Marker + fresh .env in the ENGINE. VAULT_PATH = the PROJECT ROOT (not the
REM WissensWIKI): the whole project folder is the corpus, and the app never mounts
REM the engine, so it never sees .env/scripts. Written flat (parens-safe).
>"%ENGINE%\.ragsetup_home" echo %ENGINE%
if exist "%ENGINE%\.env" goto relaunch
>"%ENGINE%\.env" echo CLAUDE_CONFIG_DIR=%APPDATA%\Claude
>>"%ENGINE%\.env" echo VAULT_PATH=%PROJDIR%
REM Pin the compose project name so the index + model-cache volumes have stable
REM names regardless of the engine folder (a space in "BRAG Assistent" would
REM otherwise make the auto-derived project name unpredictable).
>>"%ENGINE%\.env" echo COMPOSE_PROJECT_NAME=brag
:relaunch
echo.
echo Organized. Continuing setup from the BRAG Assistent folder (a new window opens)...
start "" "%ENGINE%\setup.bat"
echo You can close this window and delete this unpacked folder now.
pause
exit /b 0
:relocate_failed
echo.
echo Could not copy the program to the BRAG Assistent folder.
echo Please move this folder into place by hand, or re-run setup.
pause
exit /b 1

:engine_inplace
REM Install the program in THIS (unpacked) folder; mark it as the BRAG Assistent.
call "%~dp0tools\mark_engine_folder.bat" "%~dp0."
>".ragsetup_home" echo %~dp0
if exist ".env" goto inplace_env_ready
>".env" echo CLAUDE_CONFIG_DIR=%APPDATA%\Claude
>>".env" echo VAULT_PATH=%PROJDIR%
>>".env" echo COMPOSE_PROJECT_NAME=brag
:inplace_env_ready
goto real_setup

REM ====================== REAL SETUP (runs in the installed copy) ======================
:real_setup
cd /d "%~dp0"

if not exist "%APPDATA%\Claude" mkdir "%APPDATA%\Claude"
if not exist ".env" (
  echo CLAUDE_CONFIG_DIR=%APPDATA%\Claude> .env
) else (
  findstr /b "CLAUDE_CONFIG_DIR=" .env >nul || echo CLAUDE_CONFIG_DIR=%APPDATA%\Claude>> .env
)
set "CLAUDE_CONFIG_DIR=%APPDATA%\Claude"

docker info >nul 2>nul
if errorlevel 1 (
  echo Docker is not running - open Docker Desktop, wait until it says "running",
  echo then double-click setup.bat again.
  pause
  exit /b 1
)

REM Prefer the prebuilt image from GHCR (fast); fall back to a local build.
echo Fetching the prebuilt application image...
docker compose pull app >nul 2>nul
if errorlevel 1 (
  echo No prebuilt image available - building it locally instead.
  echo This first run downloads ~3 GB, please be patient.
  docker compose build
  if errorlevel 1 (
    echo Build failed - see message above.
    pause
    exit /b 1
  )
)

echo Starting the setup assistant...
if exist .setup_complete del .setup_complete
docker compose stop app >nul 2>nul
docker rm -f brag-setup >nul 2>nul

REM Which host port the bridge will publish (default 8765; .env may override).
set "PORT=8765"
for /f "tokens=2 delims==" %%P in ('findstr /b "BRIDGE_HOST_PORT=" .env 2^>nul') do set "PORT=%%P"
REM Preflight AFTER stopping our own app (so we only flag a FOREIGN program): a busy
REM port otherwise surfaces only Docker's raw "address already in use" error - a
REM dead end for non-technical users. Check first and explain the fix.
netstat -ano | findstr /c:":%PORT% " | findstr /c:"LISTENING" >nul 2>nul
if not errorlevel 1 (
  echo.
  echo Port %PORT% is already in use by another program ^(another BRAG, or another
  echo tool^). BRAG needs it for the setup assistant and the page-precise PDF links.
  echo Fix it one of two ways, then double-click setup.bat again:
  echo   - quit the program currently using port %PORT%, or
  echo   - pick a free port: add these two lines to the .env next to this file,
  echo       BRIDGE_HOST_PORT=8770
  echo       BRIDGE_PUBLIC_URL=http://localhost:8770
  pause
  exit /b 1
)

docker compose --profile setup up -d setup
if errorlevel 1 (
  echo Start failed - see message above.
  pause
  exit /b 1
)

echo.
echo Opening the setup assistant in your browser...
timeout /t 3 /nobreak >nul
start "" "http://localhost:%PORT%/setup"

echo.
echo Finish the setup in your browser - this window waits for you.
echo (If you closed or cancelled the assistant: close this window and double-click setup.bat again.)
set /a waited=0
:waitloop
if exist .setup_complete goto setupdone
timeout /t 2 /nobreak >nul
set /a waited+=2
if %waited% geq 2700 (
  echo.
  echo Timed out after 45 minutes. If you didn't finish the assistant, close this
  echo window and run setup.bat again.
  docker compose --profile setup rm -sf setup >nul 2>nul
  exit /b 1
)
goto waitloop
:setupdone

echo Applying your settings...
docker compose --profile setup rm -sf setup >nul 2>nul
docker compose up -d >nul 2>nul

REM Connect BRAG to Claude Desktop from the HOST (a container write does not
REM reliably reach the host on Windows), then LM Studio if it is installed. Claude
REM rewrites its config while running and would drop the entry, so the helper makes
REM sure Claude is fully closed first (it offers to close it).
echo.
call "%~dp0tools\ensure_claude_closed.bat"
echo Connecting BRAG to Claude Desktop...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_claude_config.ps1"

echo.
echo Connecting BRAG to LM Studio (if installed)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_lmstudio_config.ps1"

echo.
echo All done! Your documents stay in your project folder; this "BRAG Assistent"
echo folder is the program (don't delete it). Drop more documents into your project
echo folder anytime - they are indexed automatically.
echo Quit Claude Desktop completely ^(tray ^> Quit^) and reopen it.
echo (If you use LM Studio, also fully restart it so the new connection loads.)
pause
