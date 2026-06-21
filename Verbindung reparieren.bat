@echo off
REM BRAG - repair / refresh the Claude Desktop (+ LM Studio) connections.
REM Double-click this FROM EXPLORER (not from inside Claude) if a BRAG connector
REM is missing after adding/removing a project or changing settings. It fully
REM closes Claude so the entry persists, then re-writes ALL BRAG connectors from
REM the project registry. Run from the "BRAG Assistent" folder.
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul 2>nul

echo === BRAG - repair connections ===
echo.
echo NOTE: this closes Claude Desktop completely (required so the entry sticks).
echo If you launched Claude Code INSIDE Claude, that session ends too - but this
echo console keeps running and finishes the job. Reopen Claude when it says done.
echo.

docker info >nul 2>nul
if errorlevel 1 (
  echo Docker is not running - start Docker Desktop, wait until it says "running",
  echo then double-click this again.
  pause
  exit /b 1
)
docker ps --format "{{.Names}}" | findstr /b "brag-app" >nul
if errorlevel 1 (
  echo BRAG is not running yet - double-click setup.bat first, then try again.
  pause
  exit /b 1
)

REM Close Claude first (the helper offers to), so the write is not clobbered by a
REM running Claude, then sync ALL brag/brag-<project> connectors from the registry.
call "%~dp0tools\ensure_claude_closed.bat"
echo Writing the BRAG connectors...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_claude_config.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_lmstudio_config.ps1"

echo.
echo Done. Open Claude Desktop again - all your BRAG connectors should be there.
echo (If you use LM Studio, fully restart it too.)
pause
