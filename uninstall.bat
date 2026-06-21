@echo off
REM BRAG - Building Retrieval-Augmented Generation - uninstall / remove a project
REM (Windows). You choose: remove ONE project connection (keep BRAG + your other
REM projects + all documents), or remove the WHOLE BRAG system. Double-click is
REM fine; it runs from the "BRAG Assistent" folder. Your documents are never deleted.
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul 2>nul

echo === BRAG - uninstall ===
echo.
echo What do you want to remove?
echo   [1] One project connection  ^(keep BRAG and your other projects^)
echo   [2] The WHOLE BRAG system
echo   [C] Cancel
echo.
set "MODE="
set /p MODE="Choose 1, 2 or C: "
if /i "%MODE%"=="C" goto cancel
if "%MODE%"=="1" goto remove_one
if "%MODE%"=="2" goto remove_all
echo Invalid choice - nothing was changed.
pause
exit /b 0

REM ===================== remove ONE project =====================
:remove_one
echo.
docker info >nul 2>nul
if errorlevel 1 (
  echo Docker is not running - start Docker Desktop, then try again.
  pause
  exit /b 1
)
echo Your projects ^(slug ^| name ^| folder ^| collection^):
docker compose run --rm setup python -m brag.projects list
echo.
echo Note: the "default" project can only be removed via the full uninstall [2].
set "SLUG="
set /p SLUG="Type the slug to remove (or C to cancel): "
if /i "%SLUG%"=="C" goto cancel
if not defined SLUG goto cancel
if /i "%SLUG%"=="default" (
  echo The "default" project is removed only via the full uninstall.
  pause
  exit /b 0
)
set "DELIDX="
set /p DELIDX="Also delete this project's search index? Your documents stay. (y/N): "
set "RMFLAG="
if /i "%DELIDX%"=="y" set "RMFLAG=--delete-index"
echo Removing project "%SLUG%"...
docker compose run --rm setup python -m brag.projects remove "%SLUG%" %RMFLAG%
if errorlevel 1 (
  echo Could not remove "%SLUG%" - check the slug from the list above.
  pause
  exit /b 1
)
echo Applying...
docker compose up -d
REM Drop this project's connector from Claude + LM Studio. Claude rewrites its
REM config while running, so close it first (the helper offers to) for it to stick.
call "%~dp0tools\ensure_claude_closed.bat"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_claude_config.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_lmstudio_config.ps1"
echo.
echo Done - project "%SLUG%" removed. BRAG and your other projects stay.
echo Its documents on disk are untouched. Reopen Claude Desktop to refresh the list.
pause
exit /b 0

REM ===================== remove the WHOLE system =====================
:remove_all
echo.
echo This will REMOVE:
echo   - the BRAG containers and network
echo   - the ~3 GB model cache ^(re-downloads on a fresh install^)
echo   - the BRAG app image
echo   - the local .env ^(it holds your API key^) + the project registry
echo   - the BRAG entries in Claude Desktop and LM Studio ^(other MCP servers kept^)
echo.
echo This will KEEP:
echo   - your documents in every project folder
echo   - the search index ^(the qdrant_data volume^)
echo.
set "CONFIRM="
set /p CONFIRM="Type y and press Enter to continue (anything else cancels): "
if /i not "%CONFIRM%"=="y" goto cancel

REM Capture the compose project name now, while the containers still exist, so we
REM can remove exactly this install's model-cache volume later.
set "PROJ="
for /f "delims=" %%p in ('docker inspect -f "{{index .Config.Labels \"com.docker.compose.project\"}}" brag-app 2^>nul') do set "PROJ=%%p"
if not defined PROJ for /f "delims=" %%p in ('docker inspect -f "{{index .Config.Labels \"com.docker.compose.project\"}}" brag-qdrant 2^>nul') do set "PROJ=%%p"

REM Remove BRAG's Claude + LM Studio entries (ALL brag/brag-<project> keys) in a
REM throwaway Python container, so no Python is needed on the host. Flat (goto) so
REM a program path containing parentheses cannot break an if-block.
if not exist "%APPDATA%\Claude\claude_desktop_config.json" goto no_claude_cfg
echo Removing the Claude Desktop connections...
docker run --rm -v "%APPDATA%\Claude":/cfg -v "%~dp0tools":/tools python:3.12-slim python /tools/remove_claude_mcp.py /cfg/claude_desktop_config.json
:no_claude_cfg
if not exist "%USERPROFILE%\.lmstudio\mcp.json" goto no_lms_cfg
echo Removing the LM Studio connections...
docker run --rm -v "%USERPROFILE%\.lmstudio":/cfg -v "%~dp0tools":/tools python:3.12-slim python /tools/remove_claude_mcp.py /cfg/mcp.json
:no_lms_cfg

echo Stopping and removing the containers...
docker compose down

REM Remove ONLY the model-cache volume; the qdrant_data index stays.
if not defined PROJ goto cache_fallback
echo Removing the ~3 GB model cache...
docker volume rm "%PROJ%_models_cache" >nul 2>nul
goto cache_done
:cache_fallback
for /f "delims=" %%v in ('docker volume ls -q --filter "label=com.docker.compose.volume=models_cache"') do docker volume rm "%%v" >nul 2>nul
:cache_done

echo Removing the BRAG image...
for /f "delims=" %%i in ('docker images -q "ghcr.io/mdrinjak-bauing/brag" 2^>nul') do docker rmi -f %%i >nul 2>nul
for /f "delims=" %%i in ('docker images -q "brag" 2^>nul') do docker rmi -f %%i >nul 2>nul

REM Remove local setup state (the .env holds your API key) + the multi-project
REM registry and the generated compose override.
if exist .env del /q .env
if exist .setup_complete del /q .setup_complete
if exist projects.json del /q projects.json
if exist docker-compose.override.yml del /q docker-compose.override.yml

echo.
echo Done - BRAG is uninstalled.
echo   KEPT: your documents in every project folder + the search index.
echo   You can delete this "BRAG Assistent" folder now if you no longer need it.
echo   Docker Desktop and Claude Desktop are untouched - uninstall them the
echo   normal way if you only used them for BRAG.
pause
exit /b 0

:cancel
echo Cancelled - nothing was changed.
pause
exit /b 0
