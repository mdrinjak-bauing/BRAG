#!/bin/bash
# Mark a folder as the BRAG Assistent program folder (macOS): write a clear
# do-not-delete note. Arg 1 = the folder path. Best-effort, never fails setup.
F="$1"
[ -z "$F" ] && exit 0
cat > "$F/BITTE NICHT LOESCHEN.txt" <<'TXT'
Dies ist das BRAG-Programm (der BRAG Assistent). Bitte diesen Ordner NICHT
loeschen oder verschieben - sonst funktioniert BRAG nicht mehr. Deine Dokumente
liegen in deinem Projektordner und sind davon NICHT betroffen.
TXT
exit 0
