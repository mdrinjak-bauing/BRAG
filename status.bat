@echo off
REM ASB - Academic RAG and Second Brain - one-click status check for Windows.
REM Double-click this file to see whether the whole system is working.
cd /d "%~dp0"

echo === ASB - Status check ===
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
for %%C in (asb-qdrant asb-app) do (
  docker ps --format "{{.Names}}" | findstr /x "%%C" >nul && (
    echo   [ OK ]  Container %%C is up
  ) || (
    echo   [FAIL]  Container %%C is NOT up - run:  docker compose up -d
  )
)
echo.

REM 3. Deep checks inside the app container
docker ps --format "{{.Names}}" | findstr /x "asb-app" >nul && (
  docker exec asb-app python -m asb.health
  echo.
)

REM 4. Claude Desktop wired up?
set "CFG=%APPDATA%\Claude\claude_desktop_config.json"
if exist "%CFG%" (
  findstr /c:"academic-rag-and-second-brain" "%CFG%" >nul && (
    echo   [ OK ]  Claude Desktop is connected to the search tools
  ) || (
    echo   [FAIL]  Claude Desktop entry missing - re-run setup.bat, then fully
    echo           quit Claude Desktop ^(tray ^> Quit^) and reopen it.
  )
) else (
  echo   [FAIL]  Claude Desktop config not found - re-run setup.bat.
)

echo.
pause
