# Installation unter Windows 10/11

**🇬🇧 [English](INSTALL_WINDOWS.md) | 🇩🇪 Deutsch**

> **Zum ersten Mal in der Eingabeaufforderung?** Diese Anleitung lässt dich ein
> paar Befehle von Hand ausführen. Lass dir Zeit und lies jeden Schritt — und
> wenn etwas unklar ist, kann dich ein KI-Assistent wie
> [Claude Code](https://claude.com/claude-code) hindurchführen und dir erklären,
> was jeder Befehl tut.

Zeitbedarf: etwa **15–20 Minuten aktive Arbeit** — du brauchst nur deine Maus und
einmal kurz die Eingabeaufforderung, keine Programmierkenntnisse. Hinzu kommen der
erste Build und die einmaligen Modell-Downloads, die größtenteils
**unbeaufsichtigt** im Hintergrund laufen; beim ersten Einrichten solltest du je
nach Internetverbindung mit insgesamt rund **30–60 Minuten** rechnen.

## 1. Docker Desktop installieren

**Was du tust:**
1. Lade Docker Desktop von <https://www.docker.com/products/docker-desktop/>
   herunter und starte den Installer.
2. Fragt er nach **WSL 2**, stimme zu (er installiert es ggf. mit; danach kann
   ein **Neustart** nötig sein — führe ihn durch).
3. Öffne nach dem Neustart **Docker Desktop**.

**Was du siehst:** Das Docker-Fenster und unten links eine Statusanzeige. **Warte,
bis dort „Engine running" / „running"** in Grün steht — erst dann ist Docker
bereit. Ein Wal-Symbol erscheint zusätzlich in der Taskleiste (unten rechts, ggf.
unter dem Pfeil „ausgeblendete Symbole").

> Beschwert sich Docker über **Virtualisierung**: Starte den PC neu ins
> BIOS/UEFI und aktiviere sie (meist „Intel VT-x" oder „AMD-V"). Die Support-Seite
> deines Rechnerherstellers erklärt, wo die Option liegt.

## 2. Claude Desktop installieren

**Was du tust:** Lade Claude Desktop von <https://claude.com/download> herunter,
installiere es, öffne es und melde dich einmal mit deinem Konto an.

**Was du siehst:** Ein normales Chat-Fenster. Die Verbindung zur Wissensbasis
richten wir in Schritt 4 automatisch ein.

## 3. Kostenlosen Gemini-API-Schlüssel holen (Standard-Profil)

**Was du tust:**
1. Öffne <https://aistudio.google.com/apikey> und melde dich mit einem
   Google-Konto an.
2. Klicke auf **„Create API key" / „API-Schlüssel erstellen"**.
3. **Kopiere** den angezeigten Schlüssel — du fügst ihn gleich im Setup ein.

> ⚠️ Der kostenlose Tarif eignet sich nicht für vertrauliche oder lizenzierte
> Inhalte (Google darf die Texte auswerten). Für solche Inhalte später ein
> lokales Profil wählen — siehe [LEGAL.de.md](LEGAL.de.md) und [PROFILES.de.md](PROFILES.de.md).

## 4. BRAG herunterladen und einrichten

> **Einmaliger Windows-Hinweis — und warum es sicher ist.** Windows markiert
> *jedes* aus dem Internet geladene Skript als möglicherweise gefährlich („Der
> Computer wurde geschützt" oder „Diese Datei könnte Ihr Gerät beschädigen") — es
> kann dein eigenes Open-Source-Setup-Skript nicht von einer echten Bedrohung
> unterscheiden. `setup.bat` ist eine kurze, lesbare Textdatei, die du vorher im
> Editor öffnen kannst: Sie prüft nur Docker, schreibt eine lokale Konfiguration
> und startet die Container. Die zwei Optionen unten umgehen die Warnung sauber.

**Was du tust — eine Option wählen:**

- **Option A · ZIP herunterladen (am einfachsten).** Auf der GitHub-Seite den
  grünen Knopf **`Code`** → **`Download ZIP`** klicken. **Vor dem Entpacken die
  ZIP einmal freigeben:** Rechtsklick auf die `.zip` → **Eigenschaften** → unten
  **„Zulassen"** anhaken → **OK**. Das entfernt die Internet-Markierung von
  *allen* Dateien darin auf einen Schlag — so erscheint später keine
  Skript-Warnung. Dann Rechtsklick auf die ZIP → **„Alle extrahieren"** (z. B. in
  deinen Benutzerordner). Wichtig: erst **entpacken** — nicht aus der ZIP heraus
  starten.
- **Option B · git clone (gar keine Warnung).** Wenn du
  [Git für Windows](https://git-scm.com/download/win) hast, öffne die
  Eingabeaufforderung und führe aus:
  `git clone https://github.com/mdrinjak-bauing/BRAG.git`. Von Git erzeugte
  Dateien tragen keine Internet-Markierung — Windows warnt nie.

Dann den Ordner öffnen und **`setup.bat`** doppelklicken.
   - Falls du den Freigabe-Schritt übersprungen hast und Windows trotzdem warnt:
     in der gelben Box **„Datei öffnen – Sicherheitswarnung"** auf **„Ausführen"**;
     in der blauen **SmartScreen**-Box („Der Computer wurde geschützt") auf
     **„Weitere Informationen"** → **„Trotzdem ausführen"**.

**Das Setup fragt nacheinander zwei Dinge.** Zuerst fragt ein
Ordner-Auswahlfenster, *wo das Programm `BRAG Assistent` liegen soll* (z. B. auf
dem Desktop) — wähle einen beliebigen Ort. Dann fragt ein zweites Fenster nach
*deinem Projektordner* (deine Dokumente). BRAG kopiert das Programm in einen
Ordner `BRAG Assistent`, legt in deinem Projektordner einen Arbeitsbereich
`WissensWIKI` an und macht von dort in einem neuen Fenster weiter. *(Brichst du
die erste Auswahl ab, installiert sich das Programm einfach im entpackten Ordner;
der Projektordner im zweiten Schritt ist erforderlich.)*

**Was du siehst:** Ein schwarzes Eingabeaufforderungs-Fenster öffnet sich und
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
  bestätigen. Lokale Profile (LM Studio) brauchen gar keinen Schlüssel.
- **Sprache deiner Dokumente.** (Dein Projektordner wurde oben bereits über die
  Ordnerauswahl festgelegt.)

Am Ende schreibt der Assistent die gesamte Konfiguration selbst — inklusive des
Eintrags in Claude Desktop. **Du editierst keine einzige Datei.** Das Fenster
baut nun im Hintergrund die Docker-Container und lädt einmalig ~3 GB Modelle
(ein paar Minuten, nur beim ersten Mal).

3. Wenn der Assistent „fertig" meldet: **Claude Desktop komplett beenden** —
   Rechtsklick auf das Claude-Symbol in der Taskleiste (unten rechts) →
   **Beenden** (nur das Fenster zu schließen genügt nicht!) — und Claude neu
   öffnen.

## 5. Erstes Dokument

**Was du tust:** Lege eine PDF-Datei direkt in deinen Projektordner (auch jeder
Unterordner geht) — alles im Projektordner wird durchsucht, außer dem
Arbeitsbereich `WissensWIKI`.

**Was du siehst:** Nichts Sichtbares — die Verarbeitung läuft im Hintergrund.
Beachte: Das **allererste** Dokument lädt zusätzlich die Docling-Layout-Modelle
herunter, daher kann gerade dieses ein paar Minuten dauern (spätere Dokumente
sind deutlich schneller). Prüfe die Pipeline am besten zuerst mit einer kleinen
**1–2-seitigen PDF**; danach rechne mit etwa **1–3 Minuten** für ein normales
50-seitiges Paper. Zum Zusehen eine Eingabeaufforderung im Projektordner öffnen
und eingeben:

```
docker compose logs -f app
```

Du siehst Zeilen wie `[1/4] extracting …` bis `done: N chunks indexed`. Mit
`Strg+C` beendest du die Anzeige (das stoppt **nicht** die App).

Stelle Claude jetzt eine Frage:

> Welche Dokumente sind in meiner Wissensbasis?

## Woran erkenne ich, dass alles läuft?

- **Am einfachsten:** Doppelklick auf **`status.bat`** — prüft mit einem Klick
  Docker, Qdrant, den Watcher, den Korpus und den KI-Anschluss und zeigt für
  jeden Punkt ✓/✗.
- In **Docker Desktop** steht der Status auf „running".
- `docker ps` (in der Eingabeaufforderung im Projektordner) zeigt die zwei
  Container **`brag-app`** und **`brag-qdrant`**.
- In Claude Desktop erscheinen die Werkzeuge (z. B. `search`, `list_sources`).
  Fehlen sie, hast du Claude vermutlich nur geschlossen statt **beendet**.

## Hinweise

- **OneDrive:** Den Projektordner in OneDrive zu halten ist in Ordnung — die
  Datenbank liegt in Docker, sicher außerhalb jedes Sync-Ordners.
- **Stoppen/Starten:** Zum Stoppen eine Eingabeaufforderung im Projektordner
  öffnen, `docker compose down`. Zum Starten: `docker compose up -d`.
- **Hybrid-Profil (LM Studio):** zuerst [LM Studio](https://lmstudio.ai) installieren
  (unter Windows empfohlen), dann das Setup ausführen. Das Setup verbindet die
  BRAG-Werkzeuge (Name `brag-<Ordner>`) automatisch auch mit dem LM-Studio-Chat (nicht nur Claude);
  installierst du LM Studio *nach* dem Setup, einfach `setup.bat` erneut
  doppelklicken, um die Verbindung zu ergänzen. Siehe
  [PROFILES.de.md](PROFILES.de.md).
- Probleme? Siehe [FAQ.de.md](FAQ.de.md).
