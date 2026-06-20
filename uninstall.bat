@echo off
REM BRAG - Building Retrieval-Augmented Generation - uninstall for Windows.
REM Removes BRAG's containers, the model cache, the app image, the local config
REM and the Claude Desktop connection. KEEPS your documents (WissensWIKI\)
REM and the search index (the qdrant_data volume), so a re-install finds your
REM corpus again. Double-click is fine; it runs from the project folder.
cd /d "%~dp0"

echo === BRAG - uninstall ===
echo.
echo This will REMOVE:
echo   - the BRAG containers and network
echo   - the ~3 GB model cache ^(re-downloads on a fresh install^)
echo   - the BRAG app image
echo   - the local .env ^(it holds your API key^)
echo   - the BRAG entry in Claude Desktop and LM Studio ^(your other MCP servers are kept^)
echo.
echo This will KEEP:
echo   - your documents in WissensWIKI\
echo   - the search index ^(the qdrant_data volume^)
echo.
set /p CONFIRM="Type y and press Enter to continue (anything else cancels): "
if /i not "%CONFIRM%"=="y" (
  echo Cancelled - nothing was changed.
  pause
  exit /b 0
)

REM Capture the compose project name now, while the containers still exist, so we
REM can remove exactly this install's model-cache volume later.
set "PROJ="
for /f "delims=" %%p in ('docker inspect -f "{{index .Config.Labels \"com.docker.compose.project\"}}" brag-app 2^>nul') do set "PROJ=%%p"
if not defined PROJ for /f "delims=" %%p in ('docker inspect -f "{{index .Config.Labels \"com.docker.compose.project\"}}" brag-qdrant 2^>nul') do set "PROJ=%%p"

REM 1. Remove BRAG's Claude Desktop entry - in a throwaway Python container, so no
REM    Python is needed on the host. Backs up the config and keeps other servers.
if exist "%APPDATA%\Claude\claude_desktop_config.json" (
  echo Removing the Claude Desktop connection...
  docker run --rm -v "%APPDATA%\Claude":/cfg -v "%~dp0tools":/tools python:3.12-slim python /tools/remove_claude_mcp.py /cfg/claude_desktop_config.json
)
REM Also remove the LM Studio connection if present (same helper; it strips the
REM 'brag' key and the legacy name, keeping any other MCP servers).
if exist "%USERPROFILE%\.lmstudio\mcp.json" (
  echo Removing the LM Studio connection...
  docker run --rm -v "%USERPROFILE%\.lmstudio":/cfg -v "%~dp0tools":/tools python:3.12-slim python /tools/remove_claude_mcp.py /cfg/mcp.json
)

REM 2. Stop and remove the containers + network. NO -v, so the volumes survive.
echo Stopping and removing the containers...
docker compose down

REM 3. Remove ONLY the model-cache volume; the qdrant_data index stays.
if defined PROJ (
  echo Removing the ~3 GB model cache...
  docker volume rm "%PROJ%_models_cache" >nul 2>nul
) else (
  REM Containers were already gone - fall back to the compose label.
  for /f "delims=" %%v in ('docker volume ls -q --filter "label=com.docker.compose.volume=models_cache"') do docker volume rm "%%v" >nul 2>nul
)

REM 4. Remove the BRAG app image (shared Qdrant/Python base images are left).
echo Removing the BRAG image...
for /f "delims=" %%i in ('docker images -q "ghcr.io/mdrinjak-bauing/brag" 2^>nul') do docker rmi -f %%i >nul 2>nul
for /f "delims=" %%i in ('docker images -q "brag" 2^>nul') do docker rmi -f %%i >nul 2>nul

REM 5. Remove local setup state (the .env holds your API key).
if exist .env del /q .env
if exist .setup_complete del /q .setup_complete

echo.
echo Done - BRAG is uninstalled.
echo   KEPT: your documents in WissensWIKI\ and the search index.
echo   You can delete this folder now if you no longer need the documents.
echo   Docker Desktop and Claude Desktop are untouched - uninstall them the
echo   normal way if you only used them for BRAG.
pause
