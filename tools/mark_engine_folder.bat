@echo off
REM Mark a folder as the BRAG Assistent program folder: a "do not delete" note and
REM a Windows folder icon (desktop.ini -> brag.ico). Arg 1 = the folder path.
REM ASCII-only, best-effort (must never fail the install).
setlocal
set "F=%~1"
if "%F%"=="" goto :done
>"%F%\BITTE NICHT LOESCHEN.txt" echo Dies ist das BRAG-Programm (der BRAG Assistent). Bitte diesen Ordner NICHT loeschen oder verschieben - sonst funktioniert BRAG nicht mehr. Deine Dokumente liegen in deinem Projektordner und sind davon NICHT betroffen.
if exist "%~dp0brag.ico" copy /y "%~dp0brag.ico" "%F%\brag.ico" >nul 2>nul
>"%F%\desktop.ini" echo [.ShellClassInfo]
if exist "%F%\brag.ico" >>"%F%\desktop.ini" echo IconResource=brag.ico,0
>>"%F%\desktop.ini" echo InfoTip=BRAG Assistent - das Programm. Bitte nicht loeschen.
REM +r on the folder makes Explorer honor desktop.ini; hide the .ini itself.
attrib +r "%F%" >nul 2>nul
attrib +s +h "%F%\desktop.ini" >nul 2>nul
:done
endlocal
goto :eof
