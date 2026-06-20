@echo off
REM BRAG - Building Retrieval-Augmented Generation - one-click status check for Windows.
REM Double-click this file to see whether the whole system is working.
cd /d "%~dp0"

echo === BRAG - Status check ===
echo.

REM 1. Docker running?
docker info >nul 2>&1
if errorlevel 1 (
  echo   [FAIL]  Docker is not running - open Docker Desktop, wait until it
  echo           says "running", then run this again.
  echo.
  pause
  exit /b 1
)
echo   [ OK ]  Docker is running

REM 2. Containers up?
for %%C in (brag-qdrant brag-app) do (
  docker ps --format "{{.Names}}" | findstr /x "%%C" >nul && (
    echo   [ OK ]  Container %%C is up
  ) || (
    echo   [FAIL]  Container %%C is NOT up - run:  docker compose up -d
  )
)
echo.

REM 3. Deep checks inside the app container
docker ps --format "{{.Names}}" | findstr /x "brag-app" >nul && (
  docker exec brag-app python -m brag.health
  echo.
)

REM 4. Claude Desktop wired up?
set "CFG=%APPDATA%\Claude\claude_desktop_config.json"
if exist "%CFG%" (
  findstr /c:"brag.mcp_server" "%CFG%" >nul && (
    echo   [ OK ]  Claude Desktop is connected to the BRAG tools
  ) || (
    echo   [FAIL]  Claude Desktop BRAG connection 'brag' missing
    echo           in %CFG%
    echo           Fix: re-run setup.bat ^(it shows the exact entry to paste if it
    echo           cannot write it^), then fully quit Claude Desktop
    echo           ^(tray ^> Quit^) and reopen it.
  )
) else (
  echo   [FAIL]  Claude Desktop config not found at %CFG%
  echo           Fix: start Claude Desktop once so it creates the config, then
  echo           re-run setup.bat.
)

echo.
pause
