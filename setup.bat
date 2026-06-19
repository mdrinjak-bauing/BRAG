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

docker info >nul 2>nul
if errorlevel 1 (
  echo Docker is installed but not running.
  echo Please open the Docker Desktop app, wait until it says "running",
  echo then double-click this file again.
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

echo Building the application (first run downloads ~3 GB, please be patient)...
docker compose build
if errorlevel 1 (
  echo Build failed - see message above.
  pause
  exit /b 1
)

echo Starting the setup assistant...
if exist .setup_complete del .setup_complete
REM If a previous session left the app running, stop it so the setup service can
REM use the bridge port (no-op on a fresh install).
docker compose stop app >nul 2>nul
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

echo.
echo All done! Quit Claude Desktop completely and reopen it.
pause
