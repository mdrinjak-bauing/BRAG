# Installation unter macOS

**🇬🇧 [English](INSTALL_MAC.md) | 🇩🇪 Deutsch**

> **Zum ersten Mal im Terminal?** Diese Anleitung lässt dich ein paar Befehle von
> Hand ausführen. Lass dir Zeit und lies jeden Schritt — und wenn etwas unklar
> ist, kann dich ein KI-Assistent wie [Claude Code](https://claude.com/claude-code)
> hindurchführen und dir erklären, was jeder Befehl tut.

Zeitbedarf: etwa **15 Minuten aktive Arbeit** — du brauchst nur deine Maus und
einmal kurz das Terminal, keine Programmierkenntnisse. Hinzu kommen der erste
Build und die einmaligen Modell-Downloads, die größtenteils **unbeaufsichtigt**
im Hintergrund laufen; beim ersten Einrichten solltest du je nach
Internetverbindung mit insgesamt rund **30–60 Minuten** rechnen.

## 1. Docker Desktop installieren

**Was du tust:**
1. Öffne <https://www.docker.com/products/docker-desktop/> und lade Docker
   Desktop herunter (für M1/M2/M3-Macs „Apple Silicon", bei älteren Intel-Macs
   „Intel chip" wählen).
2. Öffne die geladene `.dmg`-Datei (im Ordner „Downloads") per Doppelklick und
   **ziehe das Docker-Symbol in den Ordner „Programme"**, wie das Fenster es
   zeigt.
3. Starte Docker einmal aus dem Programme-Ordner. Beim ersten Start akzeptierst
   du die Lizenz; eine Anmeldung ist **nicht** nötig (du kannst sie überspringen).

**Was du siehst:** Oben rechts in der Menüleiste erscheint ein kleines
**Wal-Symbol** 🐳. Solange es sich bewegt/animiert, startet Docker noch. **Warte,
bis es ruhig steht** — dann ist Docker bereit.

## 2. Claude Desktop installieren

**Was du tust:** Lade Claude Desktop von <https://claude.com/download> herunter,
ziehe es in „Programme", öffne es und melde dich einmal mit deinem Konto an.

**Was du siehst:** Ein normales Chat-Fenster. Die Verbindung zu deiner
Wissensbasis richten wir in Schritt 4 automatisch ein — jetzt musst du hier
nichts weiter tun.

## 3. Kostenlosen Gemini-API-Schlüssel holen (Standard-Profil)

**Was du tust:**
1. Öffne <https://aistudio.google.com/apikey> und melde dich mit einem
   Google-Konto an.
2. Klicke auf **„Create API key" / „API-Schlüssel erstellen"**.
3. **Kopiere** den angezeigten Schlüssel (eine lange Zeichenkette) — du fügst
   ihn gleich im Setup ein.

> ⚠️ Der kostenlose Tarif eignet sich nicht für vertrauliche oder lizenzierte
> Inhalte (Google darf die Texte auswerten). Für solche Inhalte später ein
> lokales Profil wählen — siehe [LEGAL.de.md](LEGAL.de.md) und [PROFILES.de.md](PROFILES.de.md).

## 4. BRAG herunterladen und einrichten

> **Einmaliger macOS-Hinweis — und warum es sicher ist.** Ein aus dem Internet
> geladenes Skript steht unter „Quarantäne", daher zeigt macOS beim ersten Mal
> die Warnung „nicht verifizierter Entwickler". `setup.command` ist eine kurze,
> lesbare Textdatei (sie prüft nur Docker, schreibt eine lokale Konfiguration und
> startet die Container). Der Rechtsklick → **Öffnen** unten sagt macOS einmalig,
> dass es der Datei vertrauen soll. Wer die Abfrage ganz vermeiden will, kann das
> Repo stattdessen per `git clone` holen (geklonte Dateien sind nicht in
> Quarantäne).

**Was du tust:**
1. Auf der GitHub-Seite den grünen Knopf **`Code`** → **`Download ZIP`** klicken.
   Entpacke die ZIP per Doppelklick (z. B. in deinen Benutzerordner — siehe
   Hinweis zu iCloud unten). Es entsteht der entpackte BRAG-Ordner (sein Name
   stammt aus der ZIP). *Lieber Terminal?* `git clone https://github.com/mdrinjak-bauing/BRAG.git`
   umgeht die Quarantäne-Abfrage komplett.
2. Öffne diesen Ordner im Finder und mache einen Doppelklick auf
   **`setup.command`**.
   - Blockiert macOS mit „nicht verifizierter Entwickler": **Rechtsklick** auf
     die Datei → **Öffnen** → im Dialog erneut **Öffnen**. (Das ist bei jedem
     unsignierten heruntergeladenen Skript normal — du bestätigst es nur einmal.)

**Das Setup fragt nacheinander zwei Dinge.** Zuerst fragt ein
Ordner-Auswahlfenster, *wo das Programm `BRAG Assistent` liegen soll* (z. B. auf
dem Desktop) — wähle einen beliebigen Ort. Dann fragt ein zweites Fenster nach
*deinem Projektordner* (deine Dokumente). BRAG kopiert das Programm in einen
Ordner `BRAG Assistent`, legt in deinem Projektordner einen Arbeitsbereich
`WissensWIKI` an und macht von dort in einem neuen Fenster weiter. *(Brichst du
die erste Auswahl ab, installiert sich das Programm einfach im entpackten Ordner;
der Projektordner im zweiten Schritt ist erforderlich.)*

**Was du siehst:** Es öffnet sich ein kleines schwarzes Terminal-Fenster und
kurz darauf **automatisch dein Browser** mit dem Einrichtungs-Assistenten. Dort
beantwortest du in einfacher Sprache:
- **Wo soll die KI rechnen?** (Cloud oder lokal) — für den Start „Cloud".
- **Anbieter & Schlüssel:** Gemini wählen und den kopierten Schlüssel einfügen.
  Der Assistent prüft ihn **live** und zeigt einen grünen Haken, wenn er gültig
  ist. Dein API-Schlüssel wird nur in einer lokalen `.env`-Datei auf deinem
  Rechner gespeichert (nur für dich lesbar) und dient ausschließlich dazu, deine
  eigenen Anfragen beim gewählten Anbieter zu authentifizieren — er wird nie an
  die Macher dieser App oder an Dritte gesendet; die Live-Prüfung sendet
  lediglich eine kleine Testanfrage an diesen Anbieter, um die Gültigkeit zu
  bestätigen. Das lokale Profil (LM Studio) braucht gar keinen Schlüssel.
- **Sprache deiner Dokumente.** (Dein Projektordner wurde oben bereits über die
  Ordnerauswahl festgelegt.)

Am Ende schreibt der Assistent die ganze Konfiguration selbst — inklusive des
Eintrags in Claude Desktop. **Du editierst keine einzige Datei.** Das
Terminal-Fenster baut nun im Hintergrund die Docker-Container und lädt einmalig
~3 GB Modelle (das dauert ein paar Minuten und ist nur beim ersten Mal nötig).

3. Wenn der Assistent „fertig" meldet: **Claude Desktop komplett beenden** — also
   **Cmd+Q** drücken (nur das Fenster zu schließen genügt nicht!) — und Claude
   neu öffnen.

## 5. Erstes Dokument

**Was du tust:** Lege eine PDF-Datei direkt in deinen Projektordner (auch jeder
Unterordner geht) — alles im Projektordner wird durchsucht, außer dem
Arbeitsbereich `WissensWIKI`.

**Was du siehst:** Nichts Sichtbares — die Verarbeitung läuft im Hintergrund.
Beachte: Das **allererste** Dokument lädt zusätzlich die Docling-Layout-Modelle
herunter, daher kann gerade dieses ein paar Minuten dauern (spätere Dokumente
sind deutlich schneller). Prüfe die Pipeline am besten zuerst mit einer kleinen
**1–2-seitigen PDF**; danach rechne mit etwa **1–3 Minuten** für ein normales
50-seitiges Paper. Wenn du zusehen willst, öffne das Terminal im Projektordner und
gib ein:

```
docker compose logs -f app
```

Du siehst dann Zeilen wie `[1/4] extracting …` bis `done: N chunks indexed`. Mit
`Strg+C` beendest du die Anzeige (das stoppt **nicht** die App).

Stelle Claude jetzt eine Frage:

> Welche Dokumente sind in meiner Wissensbasis?

## Woran erkenne ich, dass alles läuft?

- **Am einfachsten:** Doppelklick auf **`status.command`** — prüft mit einem Klick
  Docker, Qdrant, den Watcher, den Korpus und den KI-Anschluss und zeigt für
  jeden Punkt ✓/✗.
- **Wal-Symbol** in der Menüleiste steht ruhig → Docker läuft.
- Im Terminal im Projektordner zeigt `docker ps` die zwei Container **`brag-app`**
  und **`brag-qdrant`**.
- In Claude Desktop erscheinen die Werkzeuge (z. B. `search`, `list_sources`) —
  sichtbar über das Werkzeug-/Steckersymbol im Eingabefeld. Fehlen sie, hast du
  Claude vermutlich nur geschlossen statt mit **Cmd+Q** beendet.

## Hinweise

- **iCloud:** Du darfst den Projektordner (und den Wissensspeicher) in einem
  iCloud-synchronisierten Ort liegen lassen — die Datenbank selbst liegt in
  Docker, sicher außerhalb jedes Sync-Ordners.
- **Stoppen/Starten:** Docker Desktop startet die App nach dem Hochfahren
  automatisch. Zum manuellen Stoppen: Terminal im Projektordner öffnen,
  `docker compose down`. Zum Starten: `docker compose up -d`.
- **Profil Hybrid (lokal):** zuerst [LM Studio](https://lmstudio.ai)
  installieren, ein Modell laden, dann das Setup ausführen. Das Setup verbindet
  die `brag`-Werkzeuge automatisch auch mit dem LM-Studio-Chat (nicht nur Claude);
  installierst du LM Studio *nach* dem Setup, einfach `setup.command` erneut
  ausführen, um die Verbindung zu ergänzen. Siehe [PROFILES.de.md](PROFILES.de.md).
- Probleme? Siehe [FAQ.de.md](FAQ.de.md).
