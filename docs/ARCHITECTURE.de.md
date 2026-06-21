# Architektur

**🇬🇧 [English](ARCHITECTURE.md) | 🇩🇪 Deutsch**

Für Neugierige und Mitwirkende. Zwei Container, ein eingebundener Ordner,
Claude Desktop als Benutzeroberfläche.

```
 HOST                                   DOCKER
┌──────────────────┐                   ┌─────────────────────────────────┐
│ Claude Desktop   │── docker exec ───▶│ brag-app                         │
│  (MCP, stdio)    │   (mcp_server)    │  ├─ watcher (polling)           │
│                  │                   │  ├─ ingest pipeline             │
│ Browser ◀────────┼── localhost:8765 ─┤  ├─ http bridge (PDF links)    │
│  (PDF at page N) │                   │  └─ search (hybrid + rerank)   │
│                  │                   │            │                    │
│ WissensWIKI/  ◀────────┼─── bind mount ───▶│            ▼                    │
│  sources/ notes/ │                   │ brag-qdrant (vector DB,          │
│  passages/ wiki/ │                   │  named volume — no sync risk)   │
│                  │                   └─────────────────────────────────┘
│ LM Studio       ◀── host.docker.internal (nur Profil Hybrid)
└──────────────────┘
```

## Einlese-Pipeline (pro Dokument)

1. **Extract** (`brag/ingest/extract.py`) — Docling analysiert das Layout:
   Kapitel, Abschnitte, Tabellen, Abbildungsunterschriften, Seitenzahlen. Der
   Tabellenmodus ist fest auf ACCURATE gesetzt, damit Bibliotheks-Updates die
   Qualität nicht still verschlechtern können. Bei aktivem Vision-Pass werden
   Abbildungsbilder gerendert (`generate_picture_images`) und im
   Contextualize-Schritt beschrieben. Das Ergebnis ist **kein Fließtext**,
   sondern ein *geordneter Strom typisierter Elemente* — Überschrift,
   Textabsatz, Tabelle, Abbildung — jedes mit der Seite, auf der es steht.
   - **Zwischen Extract und Chunk** (`extract.py` läuft durch diesen Strom):
     aufeinanderfolgende Textabsätze werden pro Abschnitt gesammelt (mit ihren
     Seitenzahlen). An jeder Strukturgrenze — neue Überschrift, Tabelle oder
     Abbildung — oder am Dokumentende wird der gesammelte Text an den Chunker
     übergeben. **Tabellen und Abbildungen laufen nicht durch das Textfenster**:
     Jede wird hier direkt zu einem eigenen Chunk (mit Seite; eine Abbildung
     trägt zusätzlich ihre Vision-Beschreibung).
2. **Chunk** (`chunking.py`) — der Abschnittstext aus Schritt 1 läuft durch ein
   gleitendes Fenster auf Absatzebene (2000 Zeichen, 200 Überlappung); jeder
   Text-Chunk behält den **echten Seitenbereich** der enthaltenen Absätze
   (`page_start..page_end`), sodass eine Stelle auf Seite 18 als Seite 18
   zitiert wird und nicht als erste Seite des Abschnitts. Lange Tabellen werden
   zeilenweise geteilt, die Kopfzeile je Teil wiederholt; ein „harter" Splitter
   behandelt OCR-Text ohne Absatzgrenzen.
3. **Contextualize** (`contextualize.py`) — jeder Abschnitt erhält 1–2 Sätze
   LLM-Kontext (Inhaltsverzeichnis + aktuelles Kapitel als Verankerung),
   Verarbeitung in Batches (Standard 5 Abschnitte pro LLM-Aufruf). Abbildungen
   durchlaufen den **Vision-Pass** (`VISION_ENABLED`, Standard an): das
   gerenderte Bild geht an das multimodale LLM für eine ehrliche Beschreibung,
   die mit eingebettet wird. Ohne Vision-Modell oder Bild Rückfall auf den
   ehrlichen Nur-Bildunterschrift-Prompt (nie ungesehene Inhalte erfinden).
4. **Embed** — dichter Vektor (arctic, 1024 Dim.) + dünnbesetzter BM25-Vektor
   mit sprachabhängiger Wortstamm-Reduktion. Fehlgeschlagene Embeddings werden
   protokolliert und übersprungen — nie als Null-Vektoren gespeichert.
5. **Store** (`pipeline.py` / `storage.py`) — die neuen Punkte werden **zuerst**
   eingespielt (gebündelter Upsert, 100 pro Päckchen, `wait=True`) in eine
   hybride Qdrant-Collection (dicht + dünn mit IDF-Modifikator); erst **danach**,
   wenn jeder Punkt serverseitig bestätigt ist, werden die verbleibenden alten
   Abschnitte derselben Quelle gelöscht (idempotentes Neu-Einlesen). Ein Crash
   zwischen den beiden Schritten hinterlässt höchstens harmlose Waisen, nie ein
   halb-gelöschtes Dokument.
6. **Note** (`notes.py`) — eine Obsidian-kompatible Literaturnotiz; der
   Abschnitt „Meine Notizen" des Nutzers übersteht jede Neugenerierung.

## Abfrage-Pipeline

Dichter + dünner Vorababruf (je 80) → Reciprocal Rank Fusion → Top 40 →
Cross-Encoder-Reranking (`BAAI/bge-reranker-v2-m3`) → Quellen-Diversitätsgrenze
(max. 3 Abschnitte/Quelle) → Top k (Standard 15). Diese Breiten steuert der
`RERANK_PROFILE`-Regler (Standard `eco` = 160 laden, 40 reranken; daneben
`off`/`balanced`/`full`). Rerank-Werte werden
ausgewiesen, aber nie als harter Filter genutzt — Cross-Encoder-Werte sind nicht
absolut kalibriert, und jede Untergrenze schneidet bei Faktenfragen legitime
Spitzentreffer ab.

## Designentscheidungen

- **Pollender Watcher** statt FS-Events: Events überschreiten die
  Docker-Mount-Grenze nicht; Polling verhält sich auf macOS- und Windows-Hosts
  identisch.
- **Benanntes Volume für Qdrant**: hält die Datenbank aus iCloud/OneDrive heraus
  (mmap-Dateien + Cloud-Sync = Korruption) und immun gegen falsch gemountete
  Pfade.
- **Collection-Name leitet sich vom Embedding-Backend ab**: ein Modellwechsel
  kann nie inkompatible Vektoren in eine bestehende Collection schreiben.
- **Ein Container für die App-Belange**: Der MCP-Server läuft als Prozess pro
  Verbindung (`docker exec`) im selben Container wie der Watcher und teilt sich
  Konfiguration und Modell-Caches.
- **NFC-Normalisierung** aller Quell-Schlüssel: macOS-Dateinamen kommen als NFD
  an; Vergleiche mit gespeicherten Payloads dürfen nicht von der Plattform
  abhängen.
