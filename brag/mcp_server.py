"""MCP server for Claude Desktop (stdio transport) — single-project entry.

Claude Desktop starts this via `docker exec -i brag-app python -m brag.mcp_server`
inside the running container — the setup wizard writes that config entry. The
tool LOGIC lives in brag/tools.py (shared with the HTTP-bridge dispatcher that a
thin per-project MCP client calls); this module is just the FastMCP surface —
the tool names, signatures and docstrings Claude sees.

Tools: search, list_sources, inspect_chunks, read_source, remove_source,
rename_source, save_passage, list_passages, list_notebook, read_note, write_note,
save_report.
"""

from mcp.server.fastmcp import FastMCP

from brag import config, tools

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
    einen Seitenbereich nutzen)."""
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
    """Save a quotable passage under a topic (e.g. a chapter or theme).

    WHEN to use which: a verbatim QUOTE from a source → save_passage (it becomes
    searchable evidence); YOUR OWN text (notes, drafts, conclusions) → write_note;
    a finished/compiled deliverable → save_report.

    Builds your evidence base in WissensWIKI/Passagen/<topic>.md AND indexes
    the passage for semantic search, so a later chat (even with a different
    provider) finds it again via `search` — it appears as a clearly marked
    "saved passage", distinct from primary sources. Use this to persist the
    findings, decisions and definitions of a working session so the knowledge
    lives in the folder, not in one chat's history."""
    return tools.save_passage(topic, text, source, page=page, note=note)


@mcp.tool()
def list_passages(topic: str = "") -> str:
    """List saved passages: pass a topic to see the passages saved under it, or
    leave it empty for an overview of all topics. (Saved passages also surface in
    search, marked as a "saved passage" — this is the by-topic browse view.)"""
    return tools.list_passages(topic=topic)


# ── Notebook (WissensWIKI/) — your own thinking, NOT search-indexed ────────────
# A second "connection" without a second MCP server: instead of a separate
# filesystem MCP (extra dependency + its own Claude-config entry), the notebook
# read/write tools live in THIS server. The corpus stays read-only via search();
# the search index is never touched by these. The notebook is WissensWIKI/ minus
# the indexed Passagen/ — any .md files and subfolders you like.
@mcp.tool()
def list_notebook() -> str:
    """List your NOTEBOOK — your own .md notes and subfolders in WissensWIKI/.
    Deliberately NOT search-indexed (use search() for the corpus, list_passages()
    for verified passages). Open one with read_note, create or update with
    write_note."""
    return tools.list_notebook()


@mcp.tool()
def read_note(path: str) -> str:
    """Read a NOTEBOOK markdown file. `path` is relative to WissensWIKI/, e.g.
    'process-maturity.md' or 'Notizen/Mueller_2023.md'. Only the notebook
    (WissensWIKI/, excluding the indexed Passagen/) is reachable here — the corpus
    and the search index are not (use search() for those)."""
    return tools.read_note(path)


@mcp.tool()
def write_note(path: str, content: str) -> str:
    """Create a NOTEBOOK note, or APPEND a dated section to an existing one — it
    never silently overwrites, so your accumulated thinking is safe. For YOUR OWN
    text (concepts, drafts, conclusions); for a verbatim source quote that should
    be searchable evidence use save_passage instead. Saved as plain Markdown under
    WissensWIKI/ and deliberately NEVER added to the search index. `path` is
    relative to WissensWIKI/, e.g. 'process-maturity.md' or 'Kapitel/2.md' (any
    subfolder). The corpus and the search index are never touched."""
    return tools.write_note(path, content)


@mcp.tool()
def save_report(title: str, content: str) -> str:
    """Compile a RESULT/REPORT into the notebook for cheap reuse — a table of
    findings, a comparison, an analysis summary. Saved as Markdown under
    WissensWIKI/Berichte/<title>.md and NOT search-indexed, so you can read it
    back later with read_note('Berichte/<title>.md') instead of re-deriving it
    (no extra tokens). Writing the same title again appends a dated section."""
    return tools.save_report(title, content)


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
