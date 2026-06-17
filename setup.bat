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

echo Starting...
if exist .setup_complete del .setup_complete
docker compose up -d
if errorlevel 1 (
  echo Start failed - see message above.
  pause
  exit /b 1
)

echo.
echo Opening the setup assistant in your browser...
timeout /t 3 /nobreak >nul
start "" "http://localhost:8765/setup"

echo.
echo Finish the setup in your browser - this window waits for you.
:waitloop
if not exist .setup_complete (
  timeout /t 2 /nobreak >nul
  goto waitloop
)

echo Applying your settings...
docker compose up -d --force-recreate app >nul 2>nul

echo.
echo All done! Quit Claude Desktop completely and reopen it.
pause
