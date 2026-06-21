@echo off
REM BRAG - Building Retrieval-Augmented Generation - one-click setup for Windows.
REM Double-click this file. On the FIRST run from the unpacked ZIP it asks where
REM your "RAG connection folder" should live, copies itself in there as
REM "RAG Setup" next to a "WissensWIKI" knowledge folder, and continues from
REM that new location. It then starts the app and opens the setup assistant in
REM your browser; this window finishes the restart afterwards.
setlocal EnableExtensions
cd /d "%~dp0"
REM UTF-8 so a knowledge-folder path with non-ASCII characters (e.g. German
REM umlauts) round-trips correctly through .ragpick and into .env.
chcp 65001 >nul 2>nul

echo === BRAG - Building Retrieval-Augmented Generation ===
echo.

REM If this copy already lives inside a RAG connection folder (marker present),
REM or a previous run already finished setup here (in-place), skip relocation.
if exist ".ragsetup_home" goto real_setup
if exist ".setup_complete" goto real_setup

REM ============ FIRST RUN: relocate into the chosen RAG connection folder ============

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

echo === Choose WHERE your BRAG folder should be created ===
echo A "RAG connection folder" with your knowledge ^(WissensWIKI^) and the
echo program ^(RAG Setup^) will be placed inside it. A picker window opens...
echo.
del ".ragpick" >nul 2>nul
powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0tools\pick_folder.ps1"
if not exist ".ragpick" (
  echo No location chosen - installing in this folder instead.
  goto real_setup
)
set "RAGDIR="
set /p RAGDIR=<".ragpick"
del ".ragpick" >nul 2>nul
if not defined RAGDIR goto real_setup

set "TARGET=%RAGDIR%\RAG Setup"
set "VAULTDIR=%RAGDIR%\WissensWIKI"

REM Already installed there? Just continue in the existing copy.
if exist "%TARGET%\.ragsetup_home" (
  echo BRAG is already installed at: %TARGET%
  echo Continuing there...
  start "" "%TARGET%\setup.bat"
  exit /b 0
)

echo.
echo Setting up your RAG connection folder:
echo   "%RAGDIR%"
echo       \WissensWIKI   ^(your documents and notes^)
echo       \RAG Setup     ^(the program^)
REM Create + seed the knowledge folder (sources, notes, wiki, passages + guides)
REM right away, so you see the full structure immediately. Only when it is new,
REM so a re-run never overwrites your documents or edited CLAUDE.md. The app also
REM seeds anything still missing on first start.
if not exist "%VAULTDIR%" (
  mkdir "%VAULTDIR%"
  robocopy "%~dp0vault_template" "%VAULTDIR%" /E /NFL /NDL /NJH /NJS /NP >nul
)
if not exist "%TARGET%" mkdir "%TARGET%"

REM Copy the program into <RAGDIR>\RAG Setup. Exclude VCS, any nested target
REM names, and per-install files that must be written fresh in the new copy.
robocopy "%~dp0." "%TARGET%" /E /NFL /NDL /NJH /NJS /NP /XD ".git" "%TARGET%" "%VAULTDIR%" /XF ".ragpick" ".env" ".setup_complete" .ragsetup_home >nul
if errorlevel 8 (
  echo.
  echo Could not copy the program to "%TARGET%".
  echo Please move this folder there by hand, or re-run setup.
  pause
  exit /b 1
)
if not exist "%TARGET%\setup.bat" (
  echo.
  echo The copy did not include setup.bat - cannot continue safely.
  echo Please move this folder into your RAG connection folder by hand.
  pause
  exit /b 1
)

REM Write the installed-copy marker and a fresh .env. Each value is written on
REM its OWN line (not inside a parenthesized block) so a folder path containing
REM parentheses cannot terminate the block early. The compose project name is
REM left to default (the stable "RAG Setup" folder name), so the search-index
REM volume stays attached without a machine-global pin.
>"%TARGET%\.ragsetup_home" echo %RAGDIR%
REM Only write a fresh .env if none exists (keeps an API key if the marker was
REM removed by hand). Done with goto, NOT a parenthesized block, so a folder path
REM containing parentheses cannot close the block early.
if exist "%TARGET%\.env" goto env_ready
>"%TARGET%\.env" echo CLAUDE_CONFIG_DIR=%APPDATA%\Claude
>>"%TARGET%\.env" echo VAULT_PATH=%VAULTDIR%
:env_ready

echo.
echo Organized. Continuing setup from the new location ^(a new window opens^)...
start "" "%TARGET%\setup.bat"
echo.
echo You can CLOSE this window and DELETE this original unpacked folder now -
echo everything lives in your RAG connection folder from here on.
pause
exit /b 0

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
docker compose --profile setup up -d setup
if errorlevel 1 (
  echo Start failed - see message above.
  pause
  exit /b 1
)

echo.
echo Opening the setup assistant in your browser...
timeout /t 3 /nobreak >nul
set "PORT=8765"
for /f "tokens=2 delims==" %%P in ('findstr /b "BRIDGE_HOST_PORT=" .env 2^>nul') do set "PORT=%%P"
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
REM reliably reach the host on Windows), then LM Studio if it is installed.
REM Claude Desktop REWRITES this config while running and would drop an entry
REM added underneath it, so wait until Claude is fully closed before writing -
REM that is what makes the connection persist.
echo.
REM Make sure Claude is fully closed first, so the entry persists (Claude rewrites
REM its config while running and would drop it). The helper offers to close Claude.
call "%~dp0tools\ensure_claude_closed.bat"
echo Connecting BRAG to Claude Desktop...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_claude_config.ps1"

echo.
echo Connecting BRAG to LM Studio (if installed)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_lmstudio_config.ps1"

echo.
echo All done! Your knowledge lives in the WissensWIKI folder next to this one.
echo Quit Claude Desktop completely ^(tray ^> Quit^) and reopen it.
echo (If you use LM Studio, also fully restart it so the new connection loads.)
pause
