"""MCP server for Claude Desktop (stdio transport) — single-project entry.

Claude Desktop starts this via `docker exec -i brag-app python -m brag.mcp_server`
inside the running container — the setup wizard writes that config entry. The
tool LOGIC lives in brag/tools.py (shared with the HTTP-bridge dispatcher that a
thin per-project MCP client calls); this module is just the FastMCP surface —
the tool names, signatures and docstrings Claude sees.

Tools: search, list_sources, inspect_chunks, read_source, remove_source,
rename_source, save_passage, list_passages, list_notebook, read_note, write_note,
recent_sources, set_metadata, delete_note, delete_passage, move_note.
"""

from mcp.server.fastmcp import FastMCP

from brag import config, pdf_open, tools, vault

mcp = FastMCP("brag")


@mcp.tool()
def search(query: str, top_k: int = 0, doc_type: str = "",
           chunk_type: str = "", year_min: int = 0, year_max: int = 0,
           source_file: str = "", meta_filter: str = "",
           reranking: bool | None = None, max_per_source: int = 0,
           mode: str = "normal") -> str:
    """Hybride Suche (Bedeutung + Stichwort) über den Dokumenten-Korpus.

    Wähle `mode` passend zur Aufgabe (setzt sinnvolle Breite/Tiefe):
    - 'precise' punktgenaue Einzelfrage (wenige, fokussierte Treffer);
    - 'normal'  normale Frage (Standard);
    - 'review'  Literaturrecherche / breite Übersicht über viele Quellen (weites
      Netz; dazu mehrere Suchen mit verschiedenen Formulierungen, dann zusammenführen);
    - 'deep'    einen/wenige konkrete Berichte vertieft lesen — mit source_file= kombinieren.
    Feineinstellung (optional): top_k = genaue Trefferzahl; max_per_source = wie viele
    Treffer aus derselben Quelle kommen dürfen.

    Probiere mehrere Formulierungen (Synonyme, deutsch/englisch).
    chunk_type='table' für Zahlen/Statistiken, 'figure' für Abbildungen.
    meta_filter schränkt auf eigene Metadaten-Felder ein (in _meta.txt im
    Wissensspeicher definiert), Format 'schlüssel=wert', mehrere mit Komma, z. B.
    meta_filter='projekt=Schulzentrum' oder 'kurs=Baumanagement, semester=WS25'.
    Nennt der Nutzer einen Projekt-/Kurs-/Mandanten-Kontext, setze diesen Filter
    IMMER — sonst mischen sich Treffer aus fremden Projekten in die Ergebnisse.
    Jede Treffer-Überschrift ist ein anklickbarer Link, der das PDF an der richtigen
    Seite öffnet — übernimm ihn IMMER in deine Antwort, wenn du die Quelle zitierst.
    """
    return tools.search_text(
        query, top_k=top_k, doc_type=doc_type, chunk_type=chunk_type,
        year_min=year_min, year_max=year_max, source_file=source_file,
        meta_filter=meta_filter, reranking=reranking, max_per_source=max_per_source,
        mode=mode)


@mcp.tool()
def list_sources(doc_type: str = "") -> str:
    """Listet alle indexierten Dokumente (nach Typ gruppiert, mit Chunk-Anzahl).
    Nutze dies ZUERST, um vor einer Literaturrecherche den Korpus zu sichten und
    die genauen `source_file`-Schlüssel zu sehen, die search/read_source erwarten."""
    return tools.list_sources(doc_type=doc_type)


@mcp.tool()
def coverage(query: str, top_k: int = 50, min_score: float = 0.4,
             mode: str = "broad") -> str:
    """Stand der Forschung / „Wer schreibt zu X?" — aggregiert die Treffer PRO QUELLE
    (statt einer flachen Trefferliste) und teilt sie in substanziell vs. peripheral.
    `mode`: 'broad' (Quellen mit ≥3 Treffern, „wer schreibt VIEL"), 'specific'
    (fokussierte Spezialquellen mit einem starken Treffer zuerst) oder 'both'.
    Für eine Literaturübersicht/„Stand der Forschung" zu einem Thema."""
    return tools.coverage(query, top_k=top_k, min_score=min_score, mode=mode)


@mcp.tool()
def clusters(query: str, top_k: int = 40, n_clusters: int = 5) -> str:
    """Themen-Map: clustert die Treffer via K-Means im Embedding-Raum in Sub-Themen
    und gibt pro Cluster einen Repräsentanten + die Quellen-/Kapitel-Verteilung aus.
    Für „Welche Sub-Aspekte/Teilthemen hat Y?" — explorativ statt einer Rangliste."""
    return tools.clusters(query, top_k=top_k, n_clusters=n_clusters)


@mcp.tool()
def compare_positions(query: str, sources: list[str], top_k_per_source: int = 3) -> str:
    """Stellt 2–7 KONKRETE Quellen zu einer Frage SIDE-BY-SIDE gegenüber — je Quelle die
    Top-Treffer. `sources` = Liste von `source_file`-Schlüsseln (siehe list_sources).
    Für „Wie definieren/bewerten Quelle A und B das Thema X?"."""
    return tools.compare_positions(query, sources, top_k_per_source=top_k_per_source)


@mcp.tool()
def open_pdf(source_file: str, pdf_page: int = 0, book_page: str = "",
             page: int = 0) -> str:
    """Öffnet eine Korpus-PDF an einer bestimmten Seite in Skim (deterministisch via
    AppleScript — zuverlässiger als Browser/Vorschau, die `#page=N` oft ignorieren).
    Nutze dies, wenn der Nutzer einen Treffer im PDF nachlesen will.

    `source_file` = der Quelle-Schlüssel aus den Suchergebnissen (ohne .pdf).
    Seitenangabe (EINE genügt): `book_page` = die in der Suche angezeigte gedruckte
    Seite „S. X" (wird via /PageLabels in die physische Seite übersetzt — der Normalfall);
    `pdf_page` = bereits die physische PDF-Seite, falls bekannt. Ohne Angabe: Seite 1."""
    return pdf_open.open_pdf(
        source_file,
        pdf_page=(pdf_page or None),
        book_page=(book_page or None),
        page=(page or None),
    )


# ── Vault-Dateien — BRAG als EIN MCP für Korpus UND echte Notiz-Ordner ──
# Diese Werkzeuge lesen/schreiben die echten Ordner des Nutzers direkt — sie ersetzen
# ein separates Filesystem-/Obsidian-MCP. Welche Ordner schreibgeschützt sind, steuert
# VAULT_WRITE_PROTECT (z. B. ein read-only Korpus oder ein Code-Bereich).

@mcp.tool()
def vault_read(path: str) -> str:
    """Liest eine **Text/Markdown**-Datei (.md/.txt/.csv) aus dem Vault (Pfad relativ zur
    Wurzel, z. B. `notes/Topic.md`). Standard-Werkzeug für Notizen und eigene Dateien —
    alles, was KEINE Korpus-Suche ist (dafür search/read_source). Für PDF/Word/Excel
    `vault_extract` (nur auf ausdrückliche Aufforderung). Eine zweite, benannte Wurzel wird
    mit Präfix angesprochen (z. B. `alt:reports/x.md`); ohne Präfix = Default-Vault.
    (Gilt für alle `vault_*`-Werkzeuge.)"""
    return vault.vault_read(path)


@mcp.tool()
def vault_list(subdir: str = "") -> str:
    """Listet Dateien/Ordner unter einem Vault-Pfad (leer = Vault-Wurzel). Zum
    Orientieren in der Ordnerstruktur, bevor du liest oder schreibst."""
    return vault.vault_list(subdir)


@mcp.tool()
def vault_search(query: str, content: bool = True, limit: int = 40, root: str = "") -> str:
    """Sucht Vault-DATEIEN (Notizen, Exposé, Belege, Konzepte …) nach Datei-Name und
    optional Inhalt — NICHT den Literatur-Korpus (dafür `search`). Standard = Haupt-Vault;
    `root="fh"` durchsucht stattdessen die so benannte Extra-Wurzel. Für „wo liegt meine
    Notiz/Datei zu X". Überspringt im Haupt-Vault die in VAULT_SEARCH_SKIP gesetzten Bereiche."""
    return vault.vault_search(query, content=content, limit=limit, root=root)


@mcp.tool()
def vault_write(path: str, content: str, overwrite: bool = False) -> str:
    """Schreibt/erstellt eine Vault-Datei am angegebenen Pfad. Überschreibt eine bereits
    vorhandene Datei NUR mit `overwrite=True` (sonst Hinweis; vorher abklären).
    Schreibgeschützt sind die in `VAULT_WRITE_PROTECT` konfigurierten Top-Level-Ordner."""
    return vault.vault_write(path, content, overwrite=overwrite)


@mcp.tool()
def vault_append(path: str, content: str) -> str:
    """Hängt Text an eine Vault-Datei an (legt sie an, falls nicht vorhanden). Der Weg
    für Belege, Tagebucheinträge, Logs u. Ä. Gleicher Schreibschutz wie vault_write."""
    return vault.vault_append(path, content)


@mcp.tool()
def vault_edit(path: str, old_string: str, new_string: str,
               replace_all: bool = False) -> str:
    """Ändert einen exakten Textausschnitt in einer BESTEHENDEN Vault-Datei in place —
    das chirurgische Gegenstück zu vault_write (ganze Datei) und vault_append (nur ans
    Ende). Für „Status oben auffrischen" in einer Notiz, eine einzelne Zeile in einer
    Übersicht/Liste nachziehen oder einen Tippfehler korrigieren — ohne die ganze Datei
    neu zu schreiben. Wie der Code-Editor:
    `old_string` muss EXAKT passen (inkl. Einrückung/Zeilenumbrüche) und EINDEUTIG sein,
    sonst wird der Edit verweigert — dann mehr Kontext aufnehmen oder `replace_all=True`
    für alle Vorkommen. Gleicher Schreibschutz wie vault_write; legt keine neue Datei an."""
    return vault.vault_edit(path, old_string, new_string, replace_all=replace_all)


@mcp.tool()
def vault_extract(path: str, page_from: int = 0, page_to: int = 0) -> str:
    """Extrahiert **Text aus einer Vault-PDF/-Word/-Excel** (`.pdf`/`.docx`/`.xlsx`) —
    **nur auf ausdrückliche Aufforderung** („lies die Word-Datei …", „extrahier das PDF").
    Standard für Notizen bleibt `vault_read` (Markdown/Text); dieses Tool ist der explizite
    Pfad für Binär-Dokumente, read-only. Erkennt das Format an der Endung; PDF optional auf
    `page_from`/`page_to` (1-basiert) einschränken; lange Dokumente werden gedeckelt. Greift
    auch auf Extra-Wurzeln zu (`alt:reports/…`). Scans ohne Textebene liefern keinen Text
    (OCR ist nicht enthalten)."""
    return vault.vault_extract(path, page_from=page_from, page_to=page_to)


@mcp.tool()
def inspect_chunks(source_file: str, page: int = 0, limit: int = 10) -> str:
    """Diagnose-Werkzeug — zeigt die roh gespeicherten Chunks einer Quelle, um die
    Suche zu debuggen („warum findet search X nicht?"). NICHT zum Beantworten einer
    Frage (dafür search bzw. read_source). Optional nach Seitenzahl filtern."""
    return tools.inspect_chunks(source_file, page=page, limit=limit)


@mcp.tool()
def read_source(source_file: str, page_from: int = 0, page_to: int = 0,
                limit: int = 25) -> str:
    """Liest ein Dokument in LESEREIHENFOLGE (nach Seite) — um einen ganzen Bericht
    zusammenzufassen oder zu bewerten, nicht zum Suchen. Keine Suchanfrage, kein
    Reranking; gibt die Abschnitte in Seitenreihenfolge zurück. `source_file` ist der
    Schlüssel aus list_sources. Optional grenzen page_from/page_to einen Seitenbereich
    ein; `limit` begrenzt die Zahl der Abschnitte (für lange Dokumente erhöhen oder
    einen Seitenbereich nutzen). Für VIELE Berichte: pro Bericht EINMAL aufrufen, jeden
    einzeln auswerten, dann zusammenführen — nicht alles in eine Abfrage zwängen."""
    return tools.read_source(source_file, page_from=page_from, page_to=page_to,
                             limit=limit)


@mcp.tool()
def remove_source(source_file: str) -> str:
    """Entfernt ein Dokument aus dem SUCHINDEX — um eine falsche, doppelte oder
    veraltete Quelle loszuwerden, die der Nutzer nicht mehr in den Treffern will.

    Sicher und umkehrbar: Die Datei wird NICHT gelöscht, sondern in einen _inbox/
    verschoben (ein Bereich, den der Watcher ignoriert), damit sie nicht neu indexiert
    wird; ihre Chunks + Literaturnotiz werden aus dem Index entfernt. `source_file` ist
    der von list_sources gezeigte Schlüssel (z. B. 'projekte/Bericht'). Pro Quelle
    einmal aufrufen."""
    return tools.remove_source(source_file)


@mcp.tool()
def rename_source(source_file: str, new_name: str) -> str:
    """Benennt ein indexiertes Dokument um / legt es neu ab und aktualisiert seine
    Index-Metadaten AN ORT UND STELLE (kein erneutes Embedding). Benennt/verschiebt
    die DATEI im Projektordner; `new_name` darf einen relativen Ordner enthalten, um
    sie auch zu verschieben (z. B. 'projekte/Schulzentrum/Endbericht'). Die
    ursprüngliche Dateiendung bleibt erhalten, wenn du sie weglässt. `source_file` ist
    der aktuelle Schlüssel aus list_sources."""
    return tools.rename_source(source_file, new_name)


@mcp.tool()
def save_passage(topic: str, text: str, source: str, page: str = "",
                 note: str = "") -> str:
    """Sichert eine zitierfähige Passage unter einem Thema (z. B. ein Kapitel/Motiv).

    WANN was: ein wörtliches ZITAT aus einer Quelle → save_passage (wird durchsuchbarer
    Beleg); EIGENER Text (Notizen, Entwürfe, Schlüsse) → write_note bzw. vault_write.

    Baut die Belegsammlung in WissensWIKI/Quellenbelege/<thema>.md auf UND indexiert die
    Passage für die semantische Suche, sodass ein späterer Chat sie über `search`
    wiederfindet — klar markiert als „gespeicherte Passage", getrennt von Primärquellen."""
    return tools.save_passage(topic, text, source, page=page, note=note)


@mcp.tool()
def list_passages(topic: str = "") -> str:
    """Listet gespeicherte Passagen: mit Thema die darunter gesicherten Passagen, ohne
    Thema eine Übersicht aller Themen (markiert als „gespeicherte Passage")."""
    return tools.list_passages(topic=topic)


# ── Notebook (WissensWIKI/) — your own thinking, NOT search-indexed ────────────
# A second "connection" without a second MCP server: instead of a separate
# filesystem MCP (extra dependency + its own Claude-config entry), the notebook
# read/write tools live in THIS server. The corpus stays read-only via search();
# the search index is never touched by these. The notebook is WissensWIKI/ minus
# the indexed Quellenbelege/ — any .md files and subfolders you like.
@mcp.tool()
def list_notebook() -> str:
    """Listet dein NOTIZBUCH — deine eigenen .md-Notizen und Unterordner in
    WissensWIKI/. Bewusst NICHT indexiert (für den Korpus search(), für gesicherte
    Passagen list_passages()). Öffnen mit read_note, anlegen/ergänzen mit write_note."""
    return tools.list_notebook()


@mcp.tool()
def read_note(path: str) -> str:
    """Liest eine NOTIZBUCH-Markdown-Datei. `path` ist relativ zu WissensWIKI/, z. B.
    'prozessreife.md' oder 'Wissen/Mueller_2023.md'. Erreichbar ist nur das Notizbuch
    (WissensWIKI/, ohne das indexierte Quellenbelege/) — der Korpus und der Suchindex nicht
    (dafür search())."""
    return tools.read_note(path)


@mcp.tool()
def write_note(path: str, content: str) -> str:
    """Legt eine NOTIZBUCH-Notiz an oder HÄNGT einen datierten Abschnitt an eine
    bestehende an — überschreibt nie still, dein gesammeltes Denken bleibt sicher. Für
    EIGENEN Text (Konzepte, Entwürfe, Schlüsse); für ein wörtliches Quellenzitat, das
    durchsuchbarer Beleg werden soll, stattdessen save_passage. Wird als reines Markdown
    unter WissensWIKI/ gespeichert und bewusst NIE in den Suchindex aufgenommen. `path`
    ist relativ zu WissensWIKI/, z. B. 'prozessreife.md' oder 'Kapitel/2.md' (beliebiger
    Unterordner). Korpus und Suchindex werden nie berührt."""
    return tools.write_note(path, content)


@mcp.tool()
def recent_sources(limit: int = 15) -> str:
    """Zeigt die ZULETZT aufgenommenen/aktualisierten Dokumente (nach Indexier-
    Zeitpunkt absteigend) — um zu sehen, was neu im Projektordner gelandet ist.
    `limit` begrenzt die Anzahl."""
    return tools.recent_sources(limit=limit)


@mcp.tool()
def set_metadata(folder: str, key: str, value: str) -> str:
    """Setzt ein eigenes Metadaten-Feld für einen KORPUS-Ordner (schreibt/ergänzt
    dessen _meta.txt) und wendet es sofort auf die bereits indexierten Dokumente an
    (kein erneutes Embedding). So taggst du z. B. einen Ordner mit projekt=…/kunde=…/
    phase=… und filterst danach mit search(meta_filter='…'). `folder` ist relativ zum
    Projektordner (z. B. 'Nachtraege' oder 'projekte/Schulzentrum')."""
    return tools.set_metadata(folder, key, value)


@mcp.tool()
def delete_note(path: str, confirm: bool = False) -> str:
    """Löscht eine Notiz im WissensWIKI-Notizbuch (Wissen/, …) — NICHT Quellenbelege/
    (dafür delete_passage) und nie den Korpus. Schutzabfrage:
    ohne confirm=True wird nur rückgefragt, erst confirm=True löscht. Zum Korrigieren:
    löschen und mit write_note neu schreiben."""
    return tools.delete_note(path, confirm=confirm)


@mcp.tool()
def delete_passage(topic: str, confirm: bool = False) -> str:
    """Löscht alle gespeicherten Passagen eines Themas (WissensWIKI/Quellenbelege/<thema>.md)
    UND entfernt sie aus dem Suchindex. Schutzabfrage: ohne confirm=True wird nur
    rückgefragt, erst confirm=True löscht. Zum Korrigieren: löschen und mit save_passage
    neu sichern."""
    return tools.delete_passage(topic, confirm=confirm)


@mcp.tool()
def move_note(path: str, new_path: str) -> str:
    """Verschiebt oder benennt eine NOTIZBUCH-Datei im WissensWIKI um (legt Ziel-
    Unterordner automatisch an, überschreibt nie). So räumst du dein Notizbuch um
    oder benennst Dateien um. Nur das Notizbuch (Wissen/, …) — NICHT Quellenbelege/
    (dort delete_passage + save_passage) und nie den Korpus. `path`/`new_path` sind
    relativ zu WissensWIKI/, z. B. move_note('Wissen/x.md', 'Kapitel/2/x.md')."""
    return tools.move_note(path, new_path)


def _warmup_reranker() -> None:
    """Load the (local, CPU) cross-encoder in the background so the FIRST search
    isn't blocked by the one-time model load. Best-effort; errors go to stderr
    (stdout is the JSON-RPC channel and must not be polluted)."""
    import sys
    try:
        from brag.search.query import _get_reranker
        _get_reranker()
    except Exception as e:  # noqa: BLE001 — warmup must never break the server
        print(f"reranker warmup skipped: {e}", file=sys.stderr)


if __name__ == "__main__":
    if config.RERANK_ENABLED and config.RERANK_WARMUP:
        import threading
        threading.Thread(target=_warmup_reranker, daemon=True).start()
    mcp.run()
