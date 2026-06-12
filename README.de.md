# Academic Second Brain

**🇬🇧 [English](README.md) | 🇩🇪 Deutsch**

**Deine persönliche, durchsuchbare Forschungs-Wissensbasis — sprich über
Claude Desktop mit deinem Literaturkorpus.**

PDFs in einen Ordner legen — sie werden automatisch ausgelesen (inklusive
Tabellen und Abbildungsunterschriften), mit KI-generiertem Kontext
angereichert und für die hybride Suche (semantisch + Stichwort) indexiert.
Danach stellst du Claude Fragen zu deiner Literatur — die Antworten sind in
deinen Quellen verankert, seitengenau belegt und einen Klick vom Original-PDF
entfernt.

Gebaut für Forschende, Professorinnen und Doktoranden — **ohne
Programmierkenntnisse nutzbar**. Alles läuft in Docker.

---

## Die Idee: eine Bibliothek und ein Notizbuch

Ein „Second Brain" für die Forschung hat zwei Hälften — und ihre strikte
Trennung ist der Kern dieses Designs:

|  | 📚 **Deine Bibliothek** | 📓 **Dein Notizbuch** |
|---|---|---|
| Ordner | `vault/sources/` | `vault/wiki/`, `vault/notes/`, `vault/passages/` |
| Enthält | externe Quellen: Paper, Bücher, Berichte | **dein eigenes Denken**: Konzepte, Entwürfe, Entscheidungen, Lesenotizen |
| Von Claude durchsuchbar? | ja — hybride Volltextsuche mit seitengenauen Belegen | bewusst **nein** |
| Kann Claude lesen/schreiben? | nur lesen (über die Suche) | ja — über die optionale Obsidian-Anbindung (siehe unten) |

**Warum ist das Notizbuch vom Suchindex ausgeschlossen?** Wegen des
Echo-Effekts: Wären deine eigenen Notizen indexiert, würdest du eines Tages
deine eigene Zusammenfassung eines Papers „finden" und als Beleg zitieren —
ohne zu merken, dass du dich selbst zitierst. Die Bibliothek beantwortet
*„Was sagen meine Quellen?"*; das Notizbuch enthält, *was du daraus machst*.
Claude arbeitet mit beidem — verwechselt sie aber nie.

## So funktioniert es

![Architektur: Vault, Docker-Container, Claude Desktop und die zwei MCP-Anschlüsse](docs/assets/architecture.svg)

Alles läuft in zwei Docker-Containern auf deinem Rechner. Im empfohlenen
Cloud-Profil verarbeitet Googles kostenlose Gemini-API die Dokumenttexte; in
den Lokal-Profilen verlässt nichts deinen Rechner (siehe
[Profile](#wähle-dein-profil)).

### Unter der Haube: die zwei Pipelines

![Pipeline: Einlesen (Parsing, Chunking, Contextual Retrieval, Embeddings, Index) und Abfrage (Prefetch, RRF-Fusion, Cross-Encoder-Reranking, belegte Antwort)](docs/assets/pipeline.svg)

Zwei Stufen leisten die Hauptarbeit für die Antwortqualität: das
**Contextual Retrieval** beim Einlesen (eine KI schreibt zu jedem Chunk 1–2
Sätze, die ihn im Argument des Dokuments verorten — knapper Wissenschaftstext
wird dadurch auffindbar) und der **Cross-Encoder-Reranker** bei der Suche
(er liest deine Frage zusammen mit jedem Kandidaten und sortiert nach
tatsächlicher Passung statt bloßer Ähnlichkeit). Beides ist standardmäßig
aktiv; alle Parameter sind in [`.env.example`](.env.example) dokumentiert.

## Die zwei Claude-Anschlüsse (MCP)

Claude Desktop spricht über zwei MCP-Server mit deinem Second Brain — einer
pro Hälfte:

### 1. Der Such-Anschluss (dieses Projekt — wird automatisch eingerichtet)

Der Setup-Assistent trägt ihn für dich in Claude Desktop ein. Er gibt Claude
diese Werkzeuge:

| Werkzeug | Was es tut | Beispielfrage an Claude |
|---|---|---|
| `search` | Hybride Suche mit Filtern (Dokumenttyp, Jahr, nur Tabellen/Abbildungen, Quelle) | *„Was sagt mein Korpus zum Nachtragsmanagement?"* — *„Finde Tabellen mit Kostenzahlen zu Nacharbeit."* |
| `list_sources` | Inventar aller indexierten Dokumente | *„Welche Dokumente sind in meiner Wissensbasis?"* |
| `inspect_chunks` | Zeigt, was zu einer Quelle wirklich gespeichert ist — dein Diagnose-Röntgenbild | *„Zeig mir, was von Müller 2023, Seite 14 indexiert wurde."* |
| `save_passage` | Speichert einen zitierfähigen Treffer unter einem Thema in `passages/` | *„Speichere dieses Zitat für mein Methodenkapitel."* |
| `list_passages` | Zeigt gespeicherte Passagen pro Thema | *„Was habe ich fürs Methodenkapitel schon gesammelt?"* |

Jeder Suchtreffer trägt einen klickbaren Link, der das PDF **an der
zitierten Seite** im Browser öffnet.

### 2. Der Notizbuch-Anschluss (optional — 5 Minuten Handarbeit)

Damit Claude auch dein Notizbuch (`wiki/`, `notes/`) lesen und fortschreiben
kann, ergänzt du das Community-Plugin **MCP Tools für Obsidian**. Dann kann
Claude deine Notizen zusammenfassen, Konzeptseiten pflegen und
Literaturnotizen ergänzen — während der Suchindex unberührt bleibt.
Schritt-für-Schritt-Anleitung: **[docs/OBSIDIAN.md](docs/OBSIDIAN.md)**.

Mit beiden Anschlüssen geht das in einem einzigen Gespräch:
*„Such in meinem Korpus nach Definitionen von Prozessreife (Bibliothek),
vergleiche sie mit meiner Konzeptnotiz zu Reifegradmodellen (Notizbuch) und
ergänze die Notiz um das, was fehlt — mit Belegen."*

## Warum Obsidian?

Du musst es nicht nutzen — der Vault ist ein normaler Ordner mit Markdown-
und PDF-Dateien, der dir vollständig gehört. Aber
[Obsidian](https://obsidian.md) (kostenlos) ist der ideale Betrachter dafür:

- **Einfache Dateien, kein Lock-in** — Obsidian arbeitet direkt auf dem Ordner; nichts wird importiert oder konvertiert.
- **Wikilinks & Graph** — Konzeptnotizen mit `[[Links]]` verbinden und das eigene Denken als Netz sehen.
- **Suche & tägliche Notizen** — komfortables Schreiben für die Notizbuch-Hälfte.
- Es ist das Standardwerkzeug der akademischen Notiz-Community — Anleitungen und Plugins gibt es reichlich.

Den `vault/`-Ordner als Obsidian-Vault öffnen — fertig
([docs/OBSIDIAN.md](docs/OBSIDIAN.md), Teil 1).

## Dein Wissensordner (der Vault)

Der Vault ist **ein Ordner auf deinem Rechner** — standardmäßig `vault/` im
Projektverzeichnis. Beim Setup kannst du stattdessen jeden anderen Ordner
angeben (Erweiterte Optionen → eigener Pfad), z. B. eine bestehende
Literatursammlung. Die Struktur:

```
vault/
├── CLAUDE.md      ← bringt Claude DEINE Forschung bei — ausfüllen!
├── AGENTS.md      ← Zusatzregeln für autonome Agenten-Aufgaben
├── sources/       ← 📚 Dokumente hier ablegen (PDF, DOCX); Unterordner = Dokumenttypen
│   └── _inbox/    ← Staging-Bereich, wird vom Indexer ignoriert (bei Bedarf anlegen)
├── notes/         ← auto-generierte Literaturnotiz pro Quelle (+ deine Ergänzungen)
├── passages/      ← über Claude gespeicherte Zitate, nach Themen gruppiert
└── wiki/          ← 📓 dein eigenes Denken — wird nie indexiert
```

Umbenennen oder Löschen in `sources/` wird automatisch nachgezogen (Index
und Literaturnotiz folgen). Unterordner-Namen werden zum filterbaren
Dokumenttyp: `sources/Paper/`, `sources/Fachbuecher/`, `sources/Berichte/` …

## Voraussetzungen

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (kostenlos)
- [Claude Desktop](https://claude.com/download) (kostenlos)
- Cloud-Profil: ein kostenloser [Gemini-API-Schlüssel](https://aistudio.google.com/apikey)
- Lokal-Profile: [LM Studio](https://lmstudio.ai) oder [Ollama](https://ollama.com) (der Setup-Assistent führt dich durch — inklusive der Frage, welches Modell du laden solltest)

## Schnellstart

1. **Herunterladen:** dieses Repository (grüner „Code"-Knopf → „Download ZIP") und entpacken.
2. **Doppelklick auf `setup.command`** (Mac) bzw. **`setup.bat`** (Windows).
   Der Setup-Assistent öffnet sich **im Browser** und führt dich durch:
   - wo die KI-Verarbeitung laufen soll (zwei Alltagsfragen, kein Fachjargon),
   - deinen API-Schlüssel (mit Live-Prüfung) *oder* die lokale KI-App (mit
     Modell-Empfehlungen für deine Hardware und Verbindungstest),
   - die Sprache deiner Dokumente und optional einen eigenen Vault-Ordner.
   Er schreibt die gesamte Konfiguration **inklusive des Claude-Desktop-
   Eintrags** — du editierst nie eine Config-Datei.
3. **Claude Desktop komplett beenden** (Cmd+Q / Tray → Beenden) und neu öffnen.
4. **Ein PDF in `vault/sources/` legen** — wird binnen Sekunden automatisch indexiert.
5. Claude fragen: *„Welche Dokumente sind in meiner Wissensbasis?"*

Der erste Build lädt einmalig ~3 GB Dokumentanalyse-Modelle.
Ausführliche Anleitungen: [macOS](docs/INSTALL_MAC.md) · [Windows](docs/INSTALL_WINDOWS.md)

## Wähle dein Profil

| | A — Cloud (Standard) | B — Hybrid | C — Lokal |
|---|---|---|---|
| KI-Verarbeitung | Google Gemini API (Free Tier) | LM Studio auf deinem Rechner | Ollama auf deinem Rechner |
| Benötigte Hardware | jeder Laptop | Mac mit Apple Silicon, 32 GB+ | ordentliche CPU, 16 GB+ |
| Dokumente verlassen den Rechner | ja (Google) | nein | nein |
| Geschwindigkeit | schnell | mittel | langsam |

Entscheidungshilfe und Modell-Empfehlungen: [docs/PROFILES.md](docs/PROFILES.md).
**Hinweis:** Ein späterer Profilwechsel erfordert Neu-Indexierung
(Embedding-Modelle sind mathematisch inkompatibel — das System fängt das
sicher ab, aber die Arbeit läuft erneut).

## Ein typischer Tag damit

1. Eine Kollegin schickt dir ein Paper → du legst es in `sources/Paper/`.
2. Zwanzig Minuten später fragst du Claude: *„Widerspricht das neue Paper
   dem, was Müller 2021 zu Nacharbeitskosten sagt? Vergleiche."*
3. Claude durchsucht beide, antwortet mit seitenverlinkten Belegen; du
   klickst — das PDF öffnet sich an der Stelle.
4. *„Speichere das zweite Zitat für mein Kapitel Qualitätskosten."* → landet
   in `passages/qualitaetskosten.md`.
5. Deine eigene Einordnung schreibst du in `wiki/Nacharbeitskosten.md` —
   in Obsidian, oder du lässt Claude über den Notizbuch-Anschluss einen
   Entwurf anlegen. Als „Suchtreffer" taucht sie später nie auf. Genau das
   ist der Zweck.

## Dokumentation

- [Installation macOS](docs/INSTALL_MAC.md) · [Installation Windows](docs/INSTALL_WINDOWS.md)
- [Backend-Profile](docs/PROFILES.md) · [Obsidian + Notizbuch-MCP anbinden](docs/OBSIDIAN.md)
- [Claude auf deine Forschung einstellen](docs/CUSTOMIZE_CLAUDE.md)
- [FAQ & Fehlersuche](docs/FAQ.md) · [Architektur](docs/ARCHITECTURE.md)

*(Die Detail-Dokumentation ist derzeit auf Englisch; deutsche Fassungen
folgen.)*

## Status

Frühe Version. Das Cloud-Profil (A) ist der getestete Hauptweg; die Profile
B/C funktionieren, sind aber weniger erprobt. Roadmap: KI-Bildbeschreibungen
für Abbildungen (Vision-Pass), automatische Dateibenennung, Korpus-
Überblicksmodi (Coverage/Cluster), optionale Wissensgraph-Ebene.

## Lizenz

[MIT](LICENSE)
