@echo off
REM Ensure Claude Desktop is FULLY closed before BRAG writes its MCP entry.
REM Claude rewrites claude_desktop_config.json while it runs and drops an entry
REM added underneath it, so the write only persists when Claude is closed. Claude
REM keeps running in the system tray after the window is closed, so a plain "wait"
REM can be defeated; this loops until no Claude.exe remains and offers to close it.
REM Called by setup.bat / "Projekt hinzufuegen.bat" right before merge_claude_config.ps1.
:ecc_loop
tasklist /fi "imagename eq Claude.exe" 2>nul | find /i "Claude.exe" >nul
if errorlevel 1 goto :eof
echo.
echo Claude Desktop is still running. To save the BRAG connection it must be
echo COMPLETELY closed (it keeps running in the system tray after you close the
echo window, so closing the window alone is not enough).
echo   [Q] let BRAG close Claude for you now
echo   [Enter] I have fully quit Claude myself (tray icon -^> Quit)
set "ECC="
set /p ECC="Type Q to let BRAG close Claude, or quit it yourself and press Enter: "
if /i "%ECC%"=="Q" taskkill /f /im Claude.exe >nul 2>nul
timeout /t 2 /nobreak >nul
goto ecc_loop
