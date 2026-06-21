@echo off
REM BRAG - Building Retrieval-Augmented Generation - uninstall / remove a project
REM (Windows). You choose: remove ONE project connection (keep BRAG + your other
REM projects + all documents), or remove the WHOLE BRAG system (a full Docker clean).
REM Double-click is fine; it runs from the "BRAG Assistent" folder. Your documents
REM on disk are NEVER deleted.
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul 2>nul

echo === BRAG - uninstall ===
echo.
echo What do you want to remove?
echo   [1] One project connection  ^(keep BRAG and your other projects^)
echo   [2] The WHOLE BRAG system   ^(full Docker clean^)
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
if errorlevel 1 goto docker_down
REM The numbered picker + the registry/override/index removal all run in the
REM one-shot setup container (it owns the registry and reaches Qdrant). Exit code:
REM 0 = removed, 2 = cancelled / only-one-project / invalid, 1 = error.
docker compose run --rm setup python -m brag.projects remove-interactive
set "RC=%ERRORLEVEL%"
if "%RC%"=="2" goto cancel
if not "%RC%"=="0" goto remove_one_err
echo.
echo Applying the change to the running app...
REM --force-recreate so brag-app re-reads the just-rewritten projects.json: a Docker
REM single-file bind mount pins the old inode until the container is recreated, so
REM without this the connector merge below could re-add the project we just removed.
docker compose up -d --force-recreate app
REM Drop the removed project's connector from Claude + LM Studio. Claude rewrites
REM its config while running, so close it first (the helper offers to) for it to stick.
call "%~dp0tools\ensure_claude_closed.bat"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_claude_config.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\merge_lmstudio_config.ps1"
echo.
echo Done - the project connection was removed. BRAG and your other projects stay,
echo and that project's documents on disk are untouched. Reopen Claude Desktop to
echo refresh the connector list.
pause
exit /b 0

:remove_one_err
echo.
echo Could not remove the project - see the message above. Nothing was changed.
pause
exit /b 1

:docker_down
echo Docker is not running - start Docker Desktop, wait until it says "running",
echo then double-click this again.
pause
exit /b 1

REM ===================== remove the WHOLE system =====================
:remove_all
echo.
echo This removes EVERYTHING BRAG put on your machine - a full Docker clean:
echo   - the BRAG containers, network and any leftover one-shot containers
echo   - BOTH Docker volumes: the ~3 GB model cache AND the search index
echo   - the BRAG app image
echo   - the local .env ^(it holds your API key^) + the project registry + override
echo   - the BRAG entries in Claude Desktop and LM Studio ^(other MCP servers kept^)
echo.
echo This KEEPS your documents in every project folder. The search index can be
echo rebuilt from them on a fresh install ^(re-ingest^).
echo.
set "CONFIRM="
set /p CONFIRM="Type y and press Enter to continue (anything else cancels): "
if /i not "%CONFIRM%"=="y" goto cancel

REM Close Claude FIRST: it rewrites claude_desktop_config.json from memory while
REM running and would resurrect the brag entries we are about to delete, leaving
REM dead connectors after the containers are gone. The helper loops until Claude is
REM closed (and offers to close it). If you launched Claude Code inside Claude, that
REM session ends - but this console keeps running and finishes the job.
call "%~dp0tools\ensure_claude_closed.bat"

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

echo Stopping and removing the containers, network and ALL BRAG volumes...
REM -p brag pins the project name so teardown works even if .env (and its
REM COMPOSE_PROJECT_NAME) is already gone; -v removes the named volumes (model
REM cache + search index); --remove-orphans sweeps any one-shot setup/run
REM containers; --profile setup includes the profiled 'setup' service.
docker compose -p brag --profile setup down -v --remove-orphans

REM Belt-and-suspenders against a missing .env / odd state: remove the named
REM volumes, the containers and the network by their pinned names too.
docker volume rm brag_models_cache brag_qdrant_data >nul 2>nul
docker rm -f brag-app brag-qdrant brag-setup >nul 2>nul
docker network rm brag_default >nul 2>nul

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
echo Verifying the Docker clean-up...
set "LEFT="
for /f "delims=" %%c in ('docker ps -a --filter "name=brag-" --format "{{.Names}}" 2^>nul') do set "LEFT=1"
for /f "delims=" %%v in ('docker volume ls -q 2^>nul ^| findstr /i /x "brag_models_cache brag_qdrant_data"') do set "LEFT=1"
if defined LEFT goto left_warn
echo   [ OK ]  No BRAG containers or volumes remain.
goto left_done
:left_warn
echo   Note: some BRAG Docker items remain - re-run this, or check 'docker ps -a'.
:left_done

echo.
echo Done - BRAG is uninstalled and Docker is clean.
echo   KEPT: your documents in every project folder.
echo   The base images ^(Qdrant, Python^) are left in case other tools use them;
echo   remove them in Docker Desktop if you want every last byte back.
echo   You can delete this "BRAG Assistent" folder now.
pause
exit /b 0

:cancel
echo Cancelled - nothing was changed.
pause
exit /b 0
