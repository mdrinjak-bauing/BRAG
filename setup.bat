@echo off
REM BRAG - Building Retrieval-Augmented Generation - one-click setup for Windows.
REM Double-click this file. It starts the app and opens the setup assistant
REM in your browser; this window finishes the restart afterwards.
cd /d "%~dp0"

echo === BRAG - Building Retrieval-Augmented Generation ===
echo.

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker is not installed.
  echo Please install Docker Desktop first: https://www.docker.com/products/docker-desktop/
  echo Then double-click this file again.
  pause
  exit /b 1
)

REM Pre-flight: hardware virtualization must be on for Docker's engine to start.
REM If it is off, Docker Desktop fails with a cryptic message — detect the BIOS
REM cause up front so we can show the actual fix. Defaults to "on" if the query
REM fails, to avoid a false alarm.
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

if not exist "%APPDATA%\Claude" mkdir "%APPDATA%\Claude"
if not exist .env (
  echo CLAUDE_CONFIG_DIR=%APPDATA%\Claude> .env
) else (
  findstr /b "CLAUDE_CONFIG_DIR=" .env >nul || echo CLAUDE_CONFIG_DIR=%APPDATA%\Claude>> .env
)
set "CLAUDE_CONFIG_DIR=%APPDATA%\Claude"

REM Prefer the prebuilt image from GHCR (fast, avoids local "pip install failed"
REM errors); fall back to building locally if none is published yet or we're
REM offline. Pull output is hidden so a "not found" message doesn't alarm.
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
REM If a previous session left the app running, stop it so the setup service can
REM use the bridge port (no-op on a fresh install).
docker compose stop app >nul 2>nul
REM Remove any leftover one-shot setup container from a previous, INTERRUPTED
REM run. Its container_name (brag-setup) is fixed, so a leftover (even from a
REM different project folder) blocks the new one by name — clear it by name so
REM docker compose can recreate it cleanly.
docker rm -f brag-setup >nul 2>nul
REM Only the one-shot setup service runs now - it serves the wizard and is the
REM only container that mounts the project dir + Claude Desktop config.
docker compose --profile setup up -d setup
if errorlevel 1 (
  echo Start failed - see message above.
  pause
  exit /b 1
)

echo.
echo Opening the setup assistant in your browser...
timeout /t 3 /nobreak >nul
REM Honour a custom BRIDGE_HOST_PORT from .env (set it there if 8765 is taken).
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
REM Tear down the setup service (frees the port and drops its mounts), then
REM start the persistent app - which never mounts the project or Claude config.
docker compose --profile setup rm -sf setup >nul 2>nul
docker compose up -d >nul 2>nul

REM Connect BRAG to Claude Desktop from the HOST. Writing this Claude-managed
REM file from INSIDE the container does NOT reliably reach the host on Windows
REM (it silently no-ops while reporting success), so the merge is done here in
REM PowerShell, which works and persists.
echo.
echo Connecting BRAG to Claude Desktop...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_claude_config.ps1"

echo.
echo All done! Quit Claude Desktop completely ^(tray ^> Quit^) and reopen it.
pause
