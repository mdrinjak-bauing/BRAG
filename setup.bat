@echo off
REM Academic Second Brain - one-click setup for Windows.
REM Double-click this file.
cd /d "%~dp0"

echo === Academic Second Brain ===
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

echo Building the application (first run downloads ~3 GB, please be patient)...
docker compose build
if errorlevel 1 (
  echo Build failed - see message above.
  pause
  exit /b 1
)

if not exist "%APPDATA%\Claude" mkdir "%APPDATA%\Claude"

docker compose run --rm -v "%cd%":/workspace -v "%APPDATA%\Claude":/claude-config app python -m asb.setup_wizard
if errorlevel 1 (
  pause
  exit /b 1
)

echo.
echo Starting the application...
docker compose up -d

echo.
echo All running. Quit Claude Desktop completely and reopen it.
pause
