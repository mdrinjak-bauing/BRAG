# Academic RAG and Second Brain

**🇬🇧 [English](README.md) | 🇩🇪 Deutsch**  ·  **Version 0.2.0** ([Änderungen](#versionen))

**Deine persönliche, durchsuchbare Forschungs-Wissensbasis — sprich über
Claude Desktop mit deinem Literaturkorpus.**

PDFs in einen Ordner legen — sie werden automatisch ausgelesen (inklusive
Tabellen und Abbildungen, samt KI-Bildbeschreibungen), mit KI-generiertem Kontext
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

### Was ist Docker — und wo liegen die ~3 GB?

Docker ist eine Art versiegeltes Mini-System. Statt Python, Datenbanken und
KI-Bibliotheken einzeln zu installieren und mit Versionskonflikten zu kämpfen,
startet Docker eine fertig geschnürte Box, in der bereits alles passend
zusammengestellt ist — auf jedem Rechner identisch. Du installierst einmal
Docker Desktop; den Rest startet das Projekt selbst. Genau das macht die
Einrichtung zu „doppelklicken und drei Fragen beantworten" statt einer Seite
voller Befehle.

Zwei dieser Boxen laufen nebeneinander: der **App-Container** (liest Dokumente
und beantwortet Suchen) und **Qdrant** (die Suchdatenbank). Beim ersten Start
lädt Docker einmalig die Programmbausteine und die KI-Modelle für die
Dokumentanalyse herunter — zusammen rund **3 GB**. Diese Dateien liegen nicht
in deinem Projektordner, sondern in Dockers eigenem, verwaltetem Speicher (dem
Docker-Image sowie einem benannten Volume für die Datenbank). Du fasst sie nie
direkt an; deinstallierst du Docker, verschwinden sie wieder. Dein
`vault/`-Ordner bleibt davon vollständig unberührt — er enthält ausschließlich
deine eigenen Dateien.

### Unter der Haube: die zwei Pipelines

![Pipeline: Einlesen (Parsing, Chunking, Contextual Retrieval, Embeddings, Index) und Abfrage (Prefetch, RRF-Fusion, Cross-Encoder-Reranking, belegte Antwort)](docs/assets/pipeline.svg)

Die Antwortqualität entsteht in zwei Arbeitsabläufen — einem beim **Einlesen**
eines Dokuments und einem bei jeder **Frage**.

**Beim Einlesen** ist der entscheidende Schritt das *Contextual Retrieval*:
Eine KI schreibt zu jedem Textabschnitt ein bis zwei einordnende Sätze, die ihn
im Argument des Dokuments verorten — knapper Wissenschaftstext wird so
überhaupt erst auffindbar. Parallel erhält jeder Abschnitt zwei
„Fingerabdrücke": einen für die **Bedeutung** (das Embedding, für die
semantische Suche) und einen für **exakte Begriffe** (für die Stichwortsuche).

**Bei jeder Frage** durchläuft deine Anfrage die folgende Abfragepipeline —
von der Frage in Claude bis zur belegten Antwort:

1. **Zwei Suchen gleichzeitig.** Die Frage läuft parallel durch die
   *Bedeutungssuche* (sie findet sinnverwandte Stellen, auch mit anderen
   Worten — „Regeln für Mehrkosten" trifft „Nachtragsmanagement") und die
   *Stichwortsuche* (Verfahren BM25: sie findet exakte Begriffe, bei denen es
   nicht auf Bedeutung, sondern auf den genauen Wortlaut ankommt — Abkürzungen
   wie GEG, Paragraphen wie § 71, Eigennamen, Aktenzeichen). Jede Suche liefert
   ihre besten rund 150 Kandidaten.
2. **Zusammenführen (RRF).** Beide Trefferlisten werden zu einer einzigen
   verschmolzen. Stellen, die *beide* Verfahren für relevant halten, steigen
   nach oben; rund 80 Kandidaten bleiben übrig.
3. **Neu sortieren — der Reranker.** Wozu dieser Schritt? Die ersten beiden
   Stufen sind schnell, aber grob: Sie messen Ähnlichkeit, nicht, ob eine
   Stelle die Frage tatsächlich *beantwortet*. Der Reranker (ein sogenannter
   Cross-Encoder) liest deine Frage gemeinsam mit jeder der rund 80 Stellen und
   bewertet die wirkliche Passung. Das ist der Unterschied zwischen „enthält
   die Suchworte" und „beantwortet die Frage" — und der größte Hebel für die
   Präzision der Antwort.
4. **Kürzen und mischen.** Die besten Treffer bleiben übrig (standardmäßig 15,
   davon höchstens 3 aus derselben Quelle, damit ein einzelnes Buch nicht alle
   Plätze belegt). Diese Anzahl heißt *top-K*.
5. **Antworten.** Claude liest ausschließlich diese ausgewählten Stellen und
   formuliert daraus die Antwort — jede Aussage mit Quelle und Seite belegt,
   ein Klick öffnet das PDF genau an der zitierten Stelle.

Die Relevanzwerte werden dabei offen ausgewiesen, statt schwache Treffer zu
verbergen — so behältst du die Kontrolle darüber, was du glaubst. Beide
Qualitätsstufen — Contextual Retrieval beim Einlesen und der Reranker bei der
Suche — sind standardmäßig aktiv; alle Parameter sind in
[`.env.example`](.env.example) dokumentiert.

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

### Deine eigenen Metadaten (Projekte, Kurse, Auftraggeber …)

Die eingebauten Metadaten — Autor, Jahr, Typ, Kapitel, Seite — werden
automatisch abgeleitet. Für alles, was **nur du wissen kannst** — zu welchem
Bauprojekt ein Leistungsverzeichnis gehört, zu welchem Modul und Semester
ein Vorlesungsskript — legst du eine `_meta.txt` in einen beliebigen Ordner
unter `sources/`:

```
# sources/Projekte/Schulzentrum/_meta.txt
projekt: Schulzentrum
auftraggeber: Stadt Hamm
```

Eine Zeile pro `schlüssel: wert`, mehr muss niemand lernen. Jedes Dokument
in diesem Ordner (und seinen Unterordnern) trägt diese Felder; tiefere
Ordner können Felder ergänzen oder überschreiben. Im Gespräch filtert
Claude danach:

> *„Such **nur im Projekt Schulzentrum**: Welche Position deckt die
> Erdarbeiten ab?"*

— ohne diesen Filter würden Treffer aus anderen Projekten in die Ergebnisse
mischen. Über denselben Mechanismus lassen sich auch `author`, `year` oder
`doc_type` korrigieren, wenn der Dateiname sie nicht hergibt. Hinweis: Die
`_meta.txt` wird beim Einlesen gelesen — nach einer Änderung ein Dokument
kurz aus dem Ordner heraus- und wieder hineinschieben, damit der Eintrag
aktualisiert wird.

## Voraussetzungen

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (kostenlos)
- [Claude Desktop](https://claude.com/download) (kostenlos)
- Ein Cloud-Profil: ein API-Schlüssel deines Anbieters — [Gemini](https://aistudio.google.com/apikey) (Free Tier), [OpenAI](https://platform.openai.com/api-keys) oder [Anthropic](https://console.anthropic.com/)
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

Das Profil wählt nur die **Text-KI** (die den Chunk-Kontext schreibt,
Abbildungen beschreibt und Dokumente klassifiziert). Der **Bedeutungs-Index
(Embeddings) läuft immer lokal** auf deinem Rechner (arctic-Modell, keine GPU
nötig) — genau wie der Reranker es ohnehin schon tut. Du kannst den KI-Anbieter
unten also jederzeit wechseln, **ohne den Korpus neu zu indexieren.**

| Profil | Text-KI-Anbieter | Günstigstes Modell | Hardware | Dokumenttext verlässt Rechner |
|---|---|---|---|---|
| **Gemini** (Standard) | Google Gemini (Free Tier) | gemini-2.5-flash-lite | jeder Laptop | ja (Google) |
| **OpenAI** | OpenAI / ChatGPT | gpt-4o-mini | jeder Laptop | ja (OpenAI) |
| **Claude** | Anthropic Claude | claude-haiku-4-5 | jeder Laptop | ja (Anthropic) |
| **Hybrid** | LM Studio (auf deinem Mac) | dein lokales Modell | Apple Silicon, 32 GB+ | nein |
| **Lokal** | Ollama (auf deinem Rechner) | llama3.1 | ordentliche CPU, 16 GB+ | nein |

Bei einem Cloud-Profil wird der **Text** jedes Chunks zur Kontext-Erzeugung an
den Anbieter geschickt — und bei aktivem Vision-Pass (Standard) zusätzlich die
**Bilder deiner Abbildungen**. Nie übermittelt werden ganze Dateien und die
Embeddings. Bei den beiden lokalen Profilen verlässt nichts den Rechner.

> ⚠️ **Datenschutz-Hinweis:** Beim **kostenlosen Gemini-Tarif** (Standard) kann
> Google die übermittelten Texte und Bilder zur Produktverbesserung nutzen und
> von Menschen prüfen lassen. Für vertrauliche, personenbezogene oder
> lizenzierte Inhalte daher ein **lokales Profil** oder einen kostenpflichtigen
> Tarif wählen (Bildversand abschaltbar mit `VISION_ENABLED=false`).
> Einzelheiten und der vollständige Rechtshinweis: **[docs/LEGAL.de.md](docs/LEGAL.de.md)**.

Entscheidungshilfe und Modell-Empfehlungen: [docs/PROFILES.md](docs/PROFILES.md).
**Hinweis:** Der Wechsel des KI-Anbieters erfordert KEINE Neu-Indexierung. Nur
das Opt-in zu *Cloud-Embeddings* (eine fortgeschrittene `.env`-Option für
schnellen Massen-Ingest auf schwacher Hardware) ändert den Index und löst einen
einmaligen Re-Ingest aus — sicher in eine separate Collection.

### Welches Modell spart Geld?

Du musst nichts von Hand auswählen — jedes Cloud-Profil ist bereits auf sein
**günstigstes brauchbares Modell** voreingestellt:

| Anbieter | Voreingestelltes Modell | Warum diese Wahl |
|---|---|---|
| Google Gemini | `gemini-2.5-flash-lite` | kostenloser Tarif, **kein** Tageslimit beim Masseneinlesen |
| OpenAI / ChatGPT | `gpt-4o-mini` | günstigstes leistungsfähiges Chat-Modell von OpenAI |
| Anthropic / Claude | `claude-haiku-4-5` | günstigstes Claude-Modell |

Entscheidend fürs Budget: An den Anbieter geht der **Textauszug jedes
Abschnitts** zur Kontext-Erzeugung (bei aktivem Vision-Pass zusätzlich die
Bilder deiner Abbildungen) — nie ganze Dateien, nie die Embeddings und auch
nicht deine späteren Fragen (die beantwortet Claude Desktop separat). Für
einen typischen Korpus bleiben die Kosten damit im **Cent-Bereich**. Wer
bewusst ein stärkeres (und teureres) Modell einsetzen möchte, trägt es als
`LLM_MODEL` in der `.env` ein — etwa `gemini-2.5-flash` für etwas mehr Qualität
(gedeckelt auf 10.000 Anfragen/Tag, daher erst *nach* dem ersten Masseneinlesen
sinnvoll). Praktischer Spartipp: Das Masseneinlesen ist der einzige Schritt,
der viele Anfragen erzeugt. Mit dem günstigen Modell einlesen und bei Bedarf
erst danach für einzelne Aufgaben ein stärkeres wählen — das hält die Rechnung
niedrig.

### Der Bedeutungs-Index (Embeddings) und deine Hardware

Hier bitte zwei Modellarten nicht verwechseln:

- Die **Text-KI** (das LLM aus der Tabelle oben) schreibt den Kontext. *Sie*
  hängt am Anbieter und an den Kosten (Cloud) bzw. an deiner Hardware (lokal).
- Der **Bedeutungs-Index** — das *Embedding-Modell* — wandelt jeden Abschnitt
  in einen durchsuchbaren Vektor. Den musst du **nicht auswählen**: In jedem
  Profil läuft dafür automatisch das lokale Modell **arctic**
  (`snowflake-arctic-embed-l-v2.0`, 1024 Dimensionen) — auf der CPU, **ohne
  GPU**, auf jedem Laptop. Es lädt einmalig rund 2,3 GB in den Modell-Cache und
  ist danach kostenlos; deine Dokument-Vektoren verlassen den Rechner nie.

**Brauche ich starke Hardware?** Für die Embeddings nicht — arctic läuft überall
auf der CPU. Leistungsfähige Hardware ist nur nötig, wenn du die **Text-KI
lokal** betreiben willst (Profile Hybrid/Lokal). Faustregeln dafür: LM Studio
auf einem Apple-Silicon-Mac — `qwen2.5-14b-instruct` ab 32 GB RAM,
`gemma-3-27b-it` ab 64 GB; für Ollama genügen 16 GB (Standardmodell
`llama3.1`), eine GPU beschleunigt deutlich.

**Wann lohnt ein anderes Embedding-Modell?** Nur in einem Fall: schwache
Hardware *und* ein sehr großer Korpus, bei dem das lokale Einlesen zu langsam
wird. Dann kannst du in der `.env` auf ein **Cloud-Embedding** umstellen
(`gemini-embedding-001` mit 3072 Dimensionen oder OpenAI
`text-embedding-3-small` mit 1536) — das ist beim Masseneinlesen spürbar
schneller. Der Preis dafür: Die Dokument-Vektoren werden dann beim Anbieter
berechnet, verlassen also den Rechner, und es ist die **einzige** Umstellung,
die eine einmalige Neu-Indexierung auslöst (sicher in eine separate
Collection). Für die allermeisten ist arctic die richtige Wahl; Details in
[docs/PROFILES.md](docs/PROFILES.md).

## Tägliche Wissensarbeit damit

Das Prinzip hinter allem: **Chats vergessen — dein Vault nicht.**
Ein Gespräch mit Claude ist weg, sobald das Fenster zugeht. Deshalb legt
jedes Gespräch, das etwas Bleibendes erzeugt, sein Ergebnis *im Vault* ab —
als gespeicherte Passage, Literaturnotiz oder Konzeptseite — und jedes
künftige Gespräch kann genau dort weitermachen. Wissen akkumuliert in
deinen Dateien, die dir gehören und die du sichern kannst; der Chat ist nur
die Werkbank.

**Wenn neue Literatur eintrifft** — ein Paper von einer Kollegin, ein
Buchkapitel, ein Branchenbericht:

1. In `sources/` ablegen → in Minuten indexiert.
2. *„Was ergänzt das zu dem, was ich schon zu Nacharbeitskosten habe?
   Widerspricht es Müller 2021? Vergleiche."* — Antworten kommen mit
   seitenverlinkten Belegen; ein Klick öffnet das PDF an der Stelle.
3. Überall wiederverwenden: *„Entwirf drei Klausurfragen aus Kapitel 4,
   mit Seitenangaben"* (Lehre), *„Fasse die Methodik für meinen
   Stand-der-Forschung-Abschnitt zusammen"* (Schreiben), *„Lohnt sich das
   gründliche Lesen für mein Projekt?"* (Sichtung).

**Wenn du eine Idee entwickelst** — die Schleife, die daraus ein *zweites
Gehirn* macht:

1. Brainstorming auf Basis deines Korpus: *„Was sagen meine Quellen zu
   Reifegradmodellen? Wo widersprechen sie sich? Was fehlt?"*
2. Ergebnis festhalten: *„Schreib das als Konzeptnotiz nach `wiki/`, mit
   den offenen Fragen am Ende."* (über den Notizbuch-Anschluss — oder du
   überträgst es selbst in Obsidian)
3. Tage später, in einem **neuen Chat**: *„Öffne meine Konzeptnotiz zu
   Reifegradmodellen — lass uns mit offener Frage 2 weitermachen."* Das
   neue Gespräch beginnt exakt dort, wo das alte endete.

**Wenn du schreibst:**

- Beim Lesen zitierfähige Passagen je Thema sammeln: *„Speichere dieses
  Zitat fürs Kapitel Qualitätskosten."* → `passages/qualitaetskosten.md`
- Beim Entwerfen: *„Was habe ich zu Qualitätskosten gesammelt? Entwirf den
  Absatz aus diesen Passagen, Belege beibehalten."*

### Claudes Instruktionen mitwachsen lassen

Die dritte Säule neben Bibliothek und Notizbuch: **`vault/CLAUDE.md`** (und
die Projekt-Anweisungen in Claude Desktop). Sie sagt Claude, wer du bist,
wie es deinen Korpus durchsuchen und wie es zitieren soll — und sie sollte
mit dir wachsen. Faustregel: Wenn du Claude zweimal dieselbe Sache
korrigierst, gehört die Korrektur in die CLAUDE.md, nicht in den nächsten
Chat. Eine gepflegte Instruktionsdatei macht aus einem generischen
Assistenten *deinen* Assistenten — Anleitung mit Beispielen:
[docs/CUSTOMIZE_CLAUDE.md](docs/CUSTOMIZE_CLAUDE.md).

## Dokumentation

- **[So funktioniert's — in einfachen Worten](docs/HOW_IT_WORKS.de.md)** (kein Technik-Wissen nötig)
- [Installation macOS](docs/INSTALL_MAC.de.md) · [Installation Windows](docs/INSTALL_WINDOWS.de.md)
- [Backend-Profile](docs/PROFILES.de.md) · [Obsidian + Notizbuch-MCP anbinden](docs/OBSIDIAN.de.md)
- [Claude auf deine Forschung einstellen](docs/CUSTOMIZE_CLAUDE.de.md)
- [FAQ & Fehlersuche](docs/FAQ.de.md) · [Architektur](docs/ARCHITECTURE.de.md)
- ⚖️ [Rechtliche Hinweise (Datenschutz, Urheberrecht)](docs/LEGAL.de.md)

## Versionen

Aktuelle Version: **0.2.0** (Juni 2026). Die vollständige Liste aller
Änderungen steht in [CHANGELOG.md](CHANGELOG.md).

- **0.2.0** — Neben Google Gemini stehen jetzt auch **OpenAI/ChatGPT** und
  **Anthropic/Claude** als Cloud-Anbieter zur Wahl. Der Einrichtungs-Assistent
  ist zweisprachig (Deutsch/Englisch). Der Bedeutungs-Index (arctic) läuft in
  **jedem** Profil lokal, sodass ein Anbieterwechsel keine Neu-Indexierung mehr
  erfordert. Diese Anleitung wurde überarbeitet — mit der vollständigen
  Abfragepipeline sowie neuen Abschnitten zu Docker, Kosten und Hardware. Neu
  außerdem der **Vision-Pass**: Abbildungen werden von einem multimodalen Modell
  beschrieben und damit über ihren Inhalt auffindbar (standardmäßig an,
  abschaltbar mit `VISION_ENABLED=false`).
- **0.1.0** — Erste Veröffentlichung: Cloud-Profil mit Google Gemini, hybride
  Suche mit Reranking, Vault-Struktur und Such-MCP für Claude Desktop.

## Status

Frühe Version (0.2.0). Das **Gemini-Profil** ist der getestete Hauptweg; die
übrigen Profile funktionieren, sind aber weniger erprobt. Roadmap: automatische
Dateibenennung, Korpus-Überblicksmodi (Coverage/Cluster), optionale
Wissensgraph-Ebene.

## Lizenz

[MIT](LICENSE)
