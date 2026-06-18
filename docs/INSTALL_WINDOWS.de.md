# Installation unter Windows 10/11

**🇬🇧 [English](INSTALL_WINDOWS.md) | 🇩🇪 Deutsch**

Zeitbedarf: ~20 Minuten (das meiste sind Downloads). Du brauchst nur deine Maus
und einmal kurz die Eingabeaufforderung — keine Programmierkenntnisse.

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

**Was du tust:**
1. Auf der GitHub-Seite den grünen Knopf **`Code`** → **`Download ZIP`** klicken.
   Rechtsklick auf die ZIP → **„Alle extrahieren"** (z. B. nach
   `C:\Users\<du>\academic-rag-and-second-brain`). Wichtig: erst **entpacken** —
   nicht aus der ZIP heraus starten.
2. Öffne den entpackten Ordner und mache einen Doppelklick auf **`setup.bat`**.
   - Warnt **Windows SmartScreen** („Der Computer wurde geschützt"): klicke auf
     **„Weitere Informationen"** → **„Trotzdem ausführen"**.

**Was du siehst:** Ein schwarzes Eingabeaufforderungs-Fenster öffnet sich und
kurz darauf **automatisch dein Browser** mit dem Einrichtungs-Assistenten. Dort
beantwortest du in einfacher Sprache:
- **Wo soll die KI rechnen?** (Cloud oder lokal) — für den Start „Cloud".
- **Anbieter & Schlüssel:** Gemini wählen und den kopierten Schlüssel einfügen.
  Der Assistent prüft ihn **live** und zeigt einen grünen Haken, wenn er gültig
  ist.
- **Sprache deiner Dokumente** und optional ein eigener Wissensspeicher (eigener Pfad).

Am Ende schreibt der Assistent die gesamte Konfiguration selbst — inklusive des
Eintrags in Claude Desktop. **Du editierst keine einzige Datei.** Das Fenster
baut nun im Hintergrund die Docker-Container und lädt einmalig ~3 GB Modelle
(ein paar Minuten, nur beim ersten Mal).

3. Wenn der Assistent „fertig" meldet: **Claude Desktop komplett beenden** —
   Rechtsklick auf das Claude-Symbol in der Taskleiste (unten rechts) →
   **Beenden** (nur das Fenster zu schließen genügt nicht!) — und Claude neu
   öffnen.

## 5. Erstes Dokument

**Was du tust:** Lege eine PDF-Datei in den Ordner `wissensspeicher\sources\` (innerhalb
des Projektordners).

**Was du siehst:** Nichts Sichtbares — die Verarbeitung läuft im Hintergrund.
Nach ~30 Sekunden ist ein kurzes Dokument indexiert. Zum Zusehen eine
Eingabeaufforderung im Projektordner öffnen und eingeben:

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
  Container **`asb-app`** und **`asb-qdrant`**.
- In Claude Desktop erscheinen die Werkzeuge (z. B. `search`, `list_sources`).
  Fehlen sie, hast du Claude vermutlich nur geschlossen statt **beendet**.

## Hinweise

- **OneDrive:** Den Projektordner in OneDrive zu halten ist in Ordnung — die
  Datenbank liegt in Docker, sicher außerhalb jedes Sync-Ordners.
- **Stoppen/Starten:** Zum Stoppen eine Eingabeaufforderung im Projektordner
  öffnen, `docker compose down`. Zum Starten: `docker compose up -d`.
- **Profile Hybrid/Lokal:** zuerst [Ollama](https://ollama.com) installieren
  (unter Windows empfohlen), dann das Setup ausführen. Siehe
  [PROFILES.de.md](PROFILES.de.md).
- Probleme? Siehe [FAQ.de.md](FAQ.de.md).
