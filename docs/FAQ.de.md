# FAQ & Fehlersuche

**🇬🇧 [English](FAQ.md) | 🇩🇪 Deutsch**

## Setup

**„Docker ist nicht installiert", obwohl ich es installiert habe.**
Öffne die Docker-Desktop-App einmal und warte, bis sie „running" anzeigt, dann
das Setup erneut starten. Unter Windows kann nach der Installation ein Neustart
nötig sein.

**Das Setup-Fenster schloss sich, bevor ich die Meldung lesen konnte.**
Führe es stattdessen aus einem Terminal aus: Terminal/Eingabeaufforderung im
Projektordner öffnen und `./setup.command` (Mac) bzw. `setup.bat` (Windows)
ausführen.

**Claude Desktop zeigt die Werkzeuge nicht an.**
1. Claude Desktop **komplett** beenden (Cmd+Q / Tray-Symbol → Beenden) und neu
   öffnen — ein Schließen des Fensters genügt nicht.
2. Prüfen, ob der Container läuft: `docker ps` sollte `asb-app` auflisten.
3. Prüfen, ob die Konfigurationsdatei (Pfad siehe [OBSIDIAN.de.md](OBSIDIAN.de.md))
   den Eintrag `academic-rag-and-second-brain` enthält.

## Indexierung

**Ich habe ein PDF abgelegt und es passiert nichts.**
- ~30 Sekunden warten (der Ordner wird alle 10 Sekunden geprüft, Dateien müssen
  erst fertig kopiert sein).
- Die Logs prüfen: `docker compose logs -f app`.
- Dateien in `sources/_inbox/` werden absichtlich ignoriert (Staging-Bereich).

**„Gescanntes PDF ohne Textebene."**
Das PDF enthält nur Bilder von Text. OCR-Unterstützung ist auf der Roadmap;
bis dahin das PDF zuerst durch ein OCR-Werkzeug laufen lassen (z. B. Acrobat;
die Texterkennung der macOS-Vorschau bettet keine Ebene ein — `ocrmypdf` oder
Ähnliches verwenden).

**Die Indexierung ist langsam.**
Das erste Dokument lädt einmalig die Layout-Analyse-Modelle herunter. Ein
50-seitiges Paper dauert typisch 1–3 Minuten; ein 500-seitiges Buch
entsprechend länger. Die Profile Hybrid/Lokal sind langsamer als die
Cloud-Profile.

**„Rate limit"-Meldungen während der Indexierung (Cloud-Profil).**
Der kostenlose Gemini-Tarif hat Limits pro Minute/Tag. Das System wartet und
versucht es automatisch erneut — einfach laufen lassen; nichts geht verloren.
Fehlgeschlagene Abschnitte werden in `vault/.asb/failed_chunks.jsonl` vermerkt.

**Werden Abbildungen/Bilder ausgewertet?**
Ja. Standardmäßig ist der **Vision-Pass** aktiv: Jedes Abbildungsbild wird beim
Einlesen an die multimodale Text-KI geschickt, die kurz und ehrlich beschreibt,
was zu sehen ist; diese Beschreibung wird mit eingebettet, sodass du Abbildungen
über ihren **Inhalt** findest (nicht nur über die Bildunterschrift). Mit einem
nicht-multimodalen lokalen Modell — oder wenn ein Bild fehlt — fällt das System
automatisch auf „nur Bildunterschrift + Kapitel" zurück. Abschalten mit
`VISION_ENABLED=false` in der `.env`. Hinweis: Bei Cloud-Profilen wird dabei auch
das Bild an den Anbieter übermittelt (siehe [LEGAL.de.md](LEGAL.de.md)).

## Leistung

**Ist die Nutzung in Docker langsamer als nativ auf dem Rechner?**
Für den Normalbetrieb nein — ein PDF ablegen und Fragen stellen ist in Docker
wie nativ eine Sache von Sekunden. Spürbar wird es nur beim **einmaligen
Masseneinlesen großer Korpora**, und das hängt vom Betriebssystem ab:

- **Linux:** Container teilen sich den Kernel des Hosts → praktisch nativ.
- **Windows:** läuft in einer schlanken Linux-VM (WSL2); CPU nahezu nativ.
- **macOS (Apple Silicon):** läuft in einer Linux-VM; CPU nahezu nativ, **aber
  kein Zugriff auf die Metal-GPU im Container**. Eine native Installation könnte
  Embedding und Reranker per GPU (MPS) beschleunigen — in Docker laufen sie auf
  der CPU.

Der Tausch ist bewusst gewählt: Docker kostet etwas Tempo beim Masseneinlesen
und bringt dafür Reproduzierbarkeit und die „Doppelklick"-Einrichtung. Genau für
den Fall „schwache Hardware + sehr großer Korpus" gibt es die `.env`-Option
**Cloud-Embeddings** (siehe [PROFILES.de.md](PROFILES.de.md)).

## Suche

**Claude sagt, es habe nichts gefunden, aber das Dokument ist da.**
- Bitte Claude, andere Formulierungen zu probieren (Synonyme, englische
  Begriffe).
- Frage: *„Nutze inspect_chunks für <Quellenname>"* — das zeigt, was wirklich
  gespeichert ist, und offenbart meist das Problem (z. B. eine schlecht
  extrahierte Tabelle).
- Prüfe, ob das Dokument indexiert ist: *„Liste meine Quellen."*

**Der PDF-Link öffnet nicht die richtige Seite.**
Der Link öffnet im Browser, der über `#page=N` zur Seite springt. Manche
Browser/PDF-Einstellungen ignorieren den Seitenanker — Chrome und Edge kommen am
besten damit zurecht. Die Seitenzahl steht außerdem im Suchtreffer selbst.

**Die Suchqualität ist in meiner Sprache schlechter.**
Setze `VAULT_LANGUAGE` in der `.env` auf deine Sprache (betrifft die
Stichwort-Wortstämme) und `ANSWER_LANGUAGE` für generierten Text, dann neue
Dokumente neu indexieren.

## Betrieb

**Wie prüfe ich mit einem Klick, ob alles läuft?**
Doppelklick auf **`status.command`** (Mac) bzw. **`status.bat`** (Windows) im
Projektordner. Der Check meldet ✓/✗ für: Docker läuft, die Container `asb-app`
und `asb-qdrant` sind oben, Qdrant erreichbar, der Korpus ist indexiert (mit
Anzahl Quellen/Chunks), der Watcher läuft, das KI-Textmodell ist erreichbar, und
Claude Desktop ist angebunden. Bei einem ✗ steht direkt dabei, was zu tun ist.

**Wie stoppe / starte ich alles?**
`docker compose down` / `docker compose up -d` im Projektordner. Der Autostart
von Docker Desktop bringt es nach einem Neustart zurück.

**Wie aktualisiere ich auf eine neue Version?**
Die neue Version herunterladen, den Ordnerinhalt ersetzen (deine `.env` und
`vault/` behalten), dann `docker compose build && docker compose up -d`.

**Wie sichere ich meine Daten?**
Deine Dokumente und Notizen liegen in `vault/` — sichere diesen Ordner wie jeden
anderen. Der Suchindex lässt sich jederzeit aus deinem Wissensordner neu aufbauen (nichts
löschen; nach einer Wiederherstellung gleicht das System nach einem Neustart neu
ab).

**Wie entferne ich ein Dokument?**
Die Datei aus `sources/` löschen — ihre Indexeinträge und die automatische Notiz
werden automatisch bereinigt.

**Kann ich den Projektordner oder die ZIP-Datei löschen?**
Die **ZIP-Datei** kannst du nach dem Entpacken löschen. Den **Projektordner**
(die entpackte ZIP) aber **behalten** — er enthält deine Konfiguration (`.env`),
die Steuerung (`docker-compose.yml`) und standardmäßig deinen Wissensordner
(`vault/`) mit allen Dokumenten. Löschen würde deine Wissensbasis entfernen und
das Starten/Stoppen unmöglich machen. Verschieben ist in Ordnung. Die ~3 GB
Modelle liegen ohnehin in Dockers Speicher, nicht im Ordner — Löschen gibt
diesen Platz also nicht frei.
