# Installation unter macOS

**🇬🇧 [English](INSTALL_MAC.md) | 🇩🇪 Deutsch**

Zeitbedarf: ~15 Minuten (das meiste sind Downloads). Du brauchst nur deine Maus
und einmal kurz das Terminal — keine Programmierkenntnisse.

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

## 4. ASB herunterladen und einrichten

**Was du tust:**
1. Auf der GitHub-Seite den grünen Knopf **`Code`** → **`Download ZIP`** klicken.
   Entpacke die ZIP per Doppelklick (z. B. in deinen Benutzerordner — siehe
   Hinweis zu iCloud unten). Es entsteht ein Ordner namens
   `academic-rag-and-second-brain` (oder ähnlich).
2. Öffne diesen Ordner im Finder und mache einen Doppelklick auf
   **`setup.command`**.
   - Blockiert macOS mit „nicht verifizierter Entwickler": **Rechtsklick** auf
     die Datei → **Öffnen** → im Dialog erneut **Öffnen**.

**Was du siehst:** Es öffnet sich ein kleines schwarzes Terminal-Fenster und
kurz darauf **automatisch dein Browser** mit dem Einrichtungs-Assistenten. Dort
beantwortest du in einfacher Sprache:
- **Wo soll die KI rechnen?** (Cloud oder lokal) — für den Start „Cloud".
- **Anbieter & Schlüssel:** Gemini wählen und den kopierten Schlüssel einfügen.
  Der Assistent prüft ihn **live** und zeigt einen grünen Haken, wenn er gültig
  ist.
- **Sprache deiner Dokumente** und optional ein eigener Vault-Ordner.

Am Ende schreibt der Assistent die ganze Konfiguration selbst — inklusive des
Eintrags in Claude Desktop. **Du editierst keine einzige Datei.** Das
Terminal-Fenster baut nun im Hintergrund die Docker-Container und lädt einmalig
~3 GB Modelle (das dauert ein paar Minuten und ist nur beim ersten Mal nötig).

3. Wenn der Assistent „fertig" meldet: **Claude Desktop komplett beenden** — also
   **Cmd+Q** drücken (nur das Fenster zu schließen genügt nicht!) — und Claude
   neu öffnen.

## 5. Erstes Dokument

**Was du tust:** Lege eine PDF-Datei in den Ordner `vault/sources/` (innerhalb
des Projektordners).

**Was du siehst:** Nichts Sichtbares — die Verarbeitung läuft im Hintergrund.
Nach ~30 Sekunden ist ein kurzes Dokument indexiert. Wenn du zusehen willst,
öffne das Terminal im Projektordner und gib ein:

```
docker compose logs -f app
```

Du siehst dann Zeilen wie `[1/4] extracting …` bis `done: N chunks indexed`. Mit
`Strg+C` beendest du die Anzeige (das stoppt **nicht** die App).

Stelle Claude jetzt eine Frage:

> Welche Dokumente sind in meiner Wissensbasis?

## Woran erkenne ich, dass alles läuft?

- **Wal-Symbol** in der Menüleiste steht ruhig → Docker läuft.
- Im Terminal im Projektordner zeigt `docker ps` die zwei Container **`asb-app`**
  und **`asb-qdrant`**.
- In Claude Desktop erscheinen die Werkzeuge (z. B. `search`, `list_sources`) —
  sichtbar über das Werkzeug-/Steckersymbol im Eingabefeld. Fehlen sie, hast du
  Claude vermutlich nur geschlossen statt mit **Cmd+Q** beendet.

## Hinweise

- **iCloud:** Du darfst den Projektordner (und den Vault) in einem
  iCloud-synchronisierten Ort liegen lassen — die Datenbank selbst liegt in
  Docker, sicher außerhalb jedes Sync-Ordners.
- **Stoppen/Starten:** Docker Desktop startet die App nach dem Hochfahren
  automatisch. Zum manuellen Stoppen: Terminal im Projektordner öffnen,
  `docker compose down`. Zum Starten: `docker compose up -d`.
- **Profile Hybrid/Lokal:** zuerst [LM Studio](https://lmstudio.ai) oder
  [Ollama](https://ollama.com) installieren, ein Modell laden, dann das Setup
  ausführen. Siehe [PROFILES.de.md](PROFILES.de.md).
- Probleme? Siehe [FAQ.de.md](FAQ.de.md).
