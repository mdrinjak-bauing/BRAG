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

**Die Setup-Seite im Browser öffnet nicht, oder Port 8765 ist schon belegt.**
Vielleicht nutzt ein anderes Programm auf deinem Rechner bereits Port 8765. Öffne
die `.env`-Datei im Projektordner und trage einen freien Port ein, zum Beispiel:

```
BRIDGE_HOST_PORT=8780
BRIDGE_PUBLIC_URL=http://localhost:8780
```

Dann das Setup erneut starten. Der Launcher (`setup.command` / `setup.bat`) liest
`BRIDGE_HOST_PORT` aus der `.env` und öffnet die richtige URL. **Beide** Variablen
müssen gesetzt sein: `BRIDGE_HOST_PORT` verschiebt den Port, und
`BRIDGE_PUBLIC_URL` muss dazu passen — sonst funktionieren die PDF-Deep-Links in
den Antworten (die zur richtigen Seite springen) nicht mehr.

**Der Build ist fehlgeschlagen oder hängt fest.**
Der erste Lauf lädt umfangreiche Abhängigkeiten und ~3 GB Modelle herunter. Bei
einer wackeligen Verbindung — oder wenn Docker zu wenig Speicherplatz hat — kann
dieser Download abbrechen oder stehen bleiben. Öffne Docker Desktop und prüfe,
dass dort „running" steht und du Internet hast, dann mache einfach erneut einen
Doppelklick auf das Setup. Es setzt aus dem Cache fort und fängt nicht von vorn
an.

**Was passiert mit meinem API-Schlüssel?**
Dein API-Schlüssel wird nur in einer lokalen `.env`-Datei auf deinem Rechner
gespeichert (nur für dich lesbar) und dient ausschließlich dazu, deine eigenen
Anfragen beim gewählten Anbieter (Gemini / OpenAI / Anthropic) zu
authentifizieren. Er wird nie an die Macher dieser App oder an Dritte gesendet;
die Live-Prüfung beim Setup sendet lediglich eine kleine Testanfrage an diesen
Anbieter, um die Gültigkeit zu bestätigen. Das lokale Profil (LM Studio)
braucht gar keinen Schlüssel.

**macOS: Ein Doppelklick auf `setup.command` bewirkt nichts (kein Fenster).**
Das ist etwas anderes als die Gatekeeper-Warnung „nicht verifizierter Entwickler"
(dafür: Rechtsklick → Öffnen). Wenn *gar kein* Fenster erscheint, hat die Datei
womöglich ihr Ausführbar-Bit verloren. Öffne das Terminal im Projektordner und
gib ein:

```
chmod +x setup.command status.command
```

Dann erneut einen Doppelklick auf `setup.command` machen.

**Claude Desktop zeigt die Werkzeuge nicht an.**
1. Claude Desktop **komplett** beenden (Cmd+Q / Tray-Symbol → Beenden) und neu
   öffnen — ein Schließen des Fensters genügt nicht.
2. Prüfen, ob der Container läuft: `docker ps` sollte `brag-app` auflisten.
3. Prüfen, ob die Konfigurationsdatei (Pfad siehe [OBSIDIAN.de.md](OBSIDIAN.de.md))
   den Eintrag `brag` enthält (ältere Installationen zeigen ggf. noch den langen
   Alt-Namen, bis du das Setup erneut ausführst).

## Indexierung

**Welche Dateitypen kann ich ablegen?**
PDF, Word (`.docx`), PowerPoint (`.pptx`), Markdown (`.md`) und HTML — einfach in
deinen Projektordner legen (beliebiger Unterordner, beliebige Tiefe). Seitengenaue
Deep-Links gibt es bei PDFs; die anderen Formate werden indexiert und durchsucht,
aber ohne Seiten-Link zitiert. **Excel (`.xlsx`) wird noch nicht unterstützt.**

**Ich habe ein PDF abgelegt und es passiert nichts.**
- ~30 Sekunden warten (der Ordner wird alle 10 Sekunden geprüft, Dateien müssen
  erst fertig kopiert sein).
- Die Logs prüfen: `docker compose logs -f app`.
- Dateien in einem `_inbox/` werden absichtlich ignoriert (Staging-Bereich).

**„Gescanntes PDF ohne Textebene."**
Das PDF enthält nur Bilder von Text. OCR-Unterstützung ist auf der Roadmap;
bis dahin das PDF zuerst durch ein OCR-Werkzeug laufen lassen (z. B. Acrobat;
die Texterkennung der macOS-Vorschau bettet keine Ebene ein — `ocrmypdf` oder
Ähnliches verwenden).

**Die Indexierung ist langsam.**
Das erste Dokument lädt einmalig die Layout-Analyse-Modelle herunter. Ein
50-seitiges Paper dauert typisch 1–3 Minuten; ein 500-seitiges Buch
entsprechend länger. Das lokale Profil (LM Studio) ist langsamer als die
Cloud-Profile.

**„Rate limit"-Meldungen während der Indexierung (Cloud-Profil).**
Der kostenlose Gemini-Tarif hat Limits pro Minute/Tag. Das System wartet und
versucht es automatisch erneut — einfach laufen lassen; nichts geht verloren.
Fehlgeschlagene Abschnitte werden in `WissensWIKI/.brag/failed_chunks.jsonl` vermerkt.

**Werden Abbildungen/Bilder ausgewertet?**
Ja. Standardmäßig ist der **Vision-Pass** aktiv: Jedes Abbildungsbild wird beim
Einlesen an die multimodale Text-KI geschickt, die kurz und ehrlich beschreibt,
was zu sehen ist; diese Beschreibung wird mit eingebettet, sodass du Abbildungen
über ihren **Inhalt** findest (nicht nur über die Bildunterschrift). Mit einem
nicht-multimodalen lokalen Modell — oder wenn ein Bild fehlt — fällt das System
automatisch auf „nur Bildunterschrift + Kapitel" zurück. Abschalten mit
`VISION_ENABLED=false` in der `.env`. Hinweis: Bei Cloud-Profilen wird dabei auch
das Bild an den Anbieter übermittelt (siehe [LEGAL.de.md](LEGAL.de.md)).

**Ich benenne eine schon eingelesene Datei um — stimmen die Metadaten dann noch?**
Ja. Der Watcher erkennt die Umbenennung und aktualisiert Autor, Jahr, Typ und den
PDF-Pfad **direkt im Index** — **ohne die Datei neu zu verarbeiten** (kein
erneutes Embedding, keine API-Kosten); die Literaturnotiz wird mitgezogen. Das
gilt für eine echte Umbenennung (gleiche Datei, neuer Name). Meldet das System es
stattdessen als Löschen + Neuanlegen, läuft ein normaler Re-Ingest — gleiches
Ergebnis, nur langsamer.

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

**Die Suche ist langsam / mein Rechner ächzt bei einer Frage.** Der lokale
Cross-Encoder-Reranker ist der größte CPU-Posten einer Suche. Stell in der
`.env` `RERANK_PROFILE` ein, um Qualität gegen Tempo zu tauschen: `eco`
(Standard) lädt 160 Kandidaten und rerankt 40; `off` schaltet das Reranking ganz
ab (am schnellsten); `balanced` und `full` reranken auf starken Rechnern mehr.
Nach dem Ändern der `.env` die App neu starten (`docker compose up -d`).
Vollständige Liste: [Backend-Profile](PROFILES.de.md).

**Claude sagt, es habe nichts gefunden, aber das Dokument ist da.**
- Bitte Claude, andere Formulierungen zu probieren (Synonyme, englische
  Begriffe).
- Frage: *„Nutze inspect_chunks für <Quellenname>"* — das zeigt, was wirklich
  gespeichert ist, und offenbart meist das Problem (z. B. eine schlecht
  extrahierte Tabelle).
- Prüfe, ob das Dokument indexiert ist: *„Liste meine Quellen."*

**Der PDF-Link öffnet Seite 1 statt der zitierten Seite.**
Der Link nutzt den Standard-Parameter `#page=N`. Die **eingebauten PDF-Viewer von
Chrome, Edge und Firefox** befolgen ihn, **Safari nicht** — dort öffnet Seite 1.
Öffne die Links in Chrome/Edge/Firefox, oder installiere einen kostenlosen Viewer,
der zur Seite springt, und setze ihn als PDF-Standard: **Skim** (macOS) oder
**SumatraPDF** (Windows). Die zitierte Seitenzahl steht außerdem im Suchtreffer.

**Im Chat wird die PDF-Seite zitiert, nicht die gedruckte (Buch-)Seite.**
Standardmäßig ist der Beleg die physische PDF-Seite. Bei Dokumenten mit
abweichender Zählung (Buch mit Vorspann, Zeitschriften-Sonderdruck) setz einen
`page_offset` in einer `_meta.txt` — dann zeigt der Beleg die gedruckte Seite,
während der Link weiter die richtige PDF-Seite öffnet. Regel: `page_offset =
physische Seite − gedruckte Seite` (siehe `_meta.txt`-Abschnitt im README).
Danach das Dokument neu indexieren.

**Die Suchqualität ist in meiner Sprache schlechter.**
Setze `VAULT_LANGUAGE` in der `.env` auf deine Sprache (betrifft die
Stichwort-Wortstämme) und `ANSWER_LANGUAGE` für generierten Text, dann neue
Dokumente neu indexieren.

## Betrieb

**Wie prüfe ich mit einem Klick, ob alles läuft?**
Doppelklick auf **`status.command`** (Mac) bzw. **`status.bat`** (Windows) im
Projektordner. Der Check meldet ✓/✗ für: Docker läuft, die Container `brag-app`
und `brag-qdrant` sind oben, Qdrant erreichbar, der Korpus ist indexiert (mit
Anzahl Quellen/Chunks), der Watcher läuft, das KI-Textmodell ist erreichbar, und
Claude Desktop ist angebunden. Bei einem ✗ steht direkt dabei, was zu tun ist.

**Wie stoppe / starte ich alles?**
`docker compose down` / `docker compose up -d` im Projektordner. Der Autostart
von Docker Desktop bringt es nach einem Neustart zurück.

**Wie aktualisiere ich auf eine neue Version?**
Die neue Version herunterladen und den Inhalt des **BRAG Assistent**-
Programmordners ersetzen (deine `.env` behalten), dann `docker compose build &&
docker compose up -d`. Dein Projektordner mit deinen Dokumenten und dem
WissensWIKI-Arbeitsbereich bleibt unangetastet.

**Wie sichere ich meine Daten?**
Deine Dokumente liegen in deinem Projektordner, deine Notizen und belegten
Passagen im WissensWIKI-Arbeitsbereich darin — sichere diesen Ordner wie jeden
anderen. Der Suchindex lässt sich jederzeit aus deinen Dokumenten neu aufbauen
(nichts löschen; nach einer Wiederherstellung gleicht das System nach einem
Neustart neu ab).

**Wie entferne ich ein Dokument?**
Die Datei aus deinem Projektordner löschen (oder herausbewegen) — ihre
Indexeinträge und die automatische Notiz werden automatisch bereinigt. Du kannst
Claude auch bitten, *„entferne diese Quelle aus meinem Index"* (das Werkzeug
`remove_source`): es verschiebt die Datei in ein `_inbox/` (umkehrbar, nicht
gelöscht) und räumt ihre Chunks ab. Löschungen, die du bei gestoppter App machst,
werden beim nächsten Start automatisch bereinigt.

**Ich habe eine Datei aktualisiert/überschrieben, die Suche zeigt aber noch den alten Inhalt.**
Ja, ein gleichnamiges Überschreiben wird automatisch erkannt: Der Watcher
indexiert die Datei neu, sobald sich die Änderung beruhigt hat (die alten Chunks
werden ersetzt). Gib ihm ein paar Sekunden; im Log siehst du die Zeile
*„document changed … re-indexing"* in `docker compose logs -f app`.

**Kann ich den Projektordner oder die ZIP-Datei löschen?**
Die **ZIP-Datei** kannst du nach dem Entpacken löschen. Aber **behalte zwei
Dinge.** Erstens den **BRAG Assistent**-Programmordner — er enthält deine
Konfiguration (`.env`) und die Steuerung (`docker-compose.yml`), sein Löschen
würde das Starten/Stoppen unmöglich machen. Zweitens deinen **Projektordner** —
er enthält deine Dokumente und den WissensWIKI-Arbeitsbereich (deine Notizen und
belegten Passagen). Beide zu verschieben ist in Ordnung. Die ~3 GB Modelle liegen
ohnehin in Dockers Speicher, nicht in diesen Ordnern — Löschen gibt diesen Platz
also nicht frei.

**Mein PC friert ein oder startet neu beim Indexieren (lokales Profil).**
Lokale KI (LM Studio) erzeugt dauerhafte GPU-Last. Bei knappem Netzteil oder
schwacher Kühlung kann das den PC mitten im Indexieren hart neu starten. BRAG
versucht ein wiederholt abgebrochenes Dokument **nicht endlos** erneut — nach
einigen Versuchen überspringt es die Datei und schreibt eine Notiz
`INDEXIERUNG-GESTOPPT.md`, statt die Maschine erneut zu überlasten. Die echte
Lösung ist, die Last zu senken:
- **Am einfachsten & sichersten:** auf ein **Cloud-Profil** wechseln (Setup neu →
  Cloud). Dann rechnet die schwere KI außerhalb deines Rechners — deine GPU wird
  gar nicht belastet.
- **Lokal bleiben:** GPU-**Power-Limit** kappen (z. B. ~80 % in MSI Afterburner)
  oder Undervolt; **andere GPU-Programme schließen** (Spiele / Launcher / Browser)
  für freien VRAM; ein **kleineres Modell (Q4, ~7 GB)** laden, damit es mit Puffer
  passt; und ein **ausreichendes Netzteil** sicherstellen. Du kannst außerdem
  `LOCAL_LLM_PACING_SECONDS=1` in der `.env` setzen, damit die GPU zwischen den
  Aufrufen Luft bekommt.
