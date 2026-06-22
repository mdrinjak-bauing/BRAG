"""Thin per-project MCP client for Claude Desktop / LM Studio.

Started per project as
  docker exec -i -e BRAG_PROJECT=<slug> brag-app python -m brag.mcp_client

It loads NO models: every tool forwards to the persistent app's HTTP bridge
(search via /api/search, all other tools via /api/index-op), where the embedder,
sparse model and reranker live exactly ONCE. So opening 5–10 project connectors
at the same time does not multiply model RAM — the whole point of the
multi-project design. The connector's BRAG_PROJECT env selects which project's
collection/vault every call targets.

Same tool surface, names and docstrings as brag.mcp_server, so Claude sees an
identical set of tools — only the implementation is a thin HTTP forwarder.
"""

import json
import os
import urllib.error
import urllib.request

from mcp.server.fastmcp import FastMCP

from brag import config
from brag.formatting import format_hit, parse_meta_filter

mcp = FastMCP("brag")

PROJECT = os.environ.get("BRAG_PROJECT", "").strip()
_BASE = f"http://localhost:{config.BRIDGE_PORT}"
_BUSY = ("BRAG's search service is starting up or unavailable — your documents "
         "are safe; please retry in a few seconds.")


def _post(path: str, payload: dict, timeout: int = 180) -> dict | None:
    """POST JSON to the in-container bridge. Returns the parsed dict, or None on
    any transport/parse failure (the caller turns that into a friendly message —
    a bridge hiccup must never crash the MCP session)."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        _BASE + path, data=data,
        headers={"Content-Type": "application/json", "Host": "localhost"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return None


def _index_op(op: str, **args) -> str:
    resp = _post("/api/index-op", {"op": op, "project": PROJECT, "args": args})
    if resp is None:
        return _BUSY
    if not resp.get("ok"):
        return resp.get("message", f"{op} failed")
    return resp.get("text", "")


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
    resp = _post("/api/search", {
        "project": PROJECT, "query": query, "top_k": top_k,
        "doc_type": doc_type, "chunk_type": chunk_type,
        "year_min": year_min, "year_max": year_max,
        "source_file": source_file, "reranking": reranking,
        "max_per_source": max_per_source, "mode": mode,
        "meta": parse_meta_filter(meta_filter),
    })
    if resp is None:
        return _BUSY
    if not resp.get("ok"):
        return resp.get("message", "search failed")
    hits = resp.get("hits", [])
    if not hits:
        return ("No hits. Try different phrasing, fewer filters, or check "
                "list_sources() whether the document is indexed at all.")
    out = [f"**{len(hits)} hits** for: {query}\n"]
    out += [format_hit(i + 1, h, project=PROJECT) for i, h in enumerate(hits)]
    return "\n".join(out)


@mcp.tool()
def list_sources(doc_type: str = "") -> str:
    """Listet alle indexierten Dokumente (nach Typ gruppiert, mit Chunk-Anzahl).
    Nutze dies ZUERST, um vor einer Literaturrecherche den Korpus zu sichten und
    die genauen `source_file`-Schlüssel zu sehen, die search/read_source erwarten."""
    return _index_op("list_sources", doc_type=doc_type)


@mcp.tool()
def inspect_chunks(source_file: str, page: int = 0, limit: int = 10) -> str:
    """Diagnose-Werkzeug — zeigt die roh gespeicherten Chunks einer Quelle, um die
    Suche zu debuggen („warum findet search X nicht?"). NICHT zum Beantworten einer
    Frage (dafür search bzw. read_source). Optional nach Seitenzahl filtern."""
    return _index_op("inspect_chunks", source_file=source_file, page=page, limit=limit)


@mcp.tool()
def read_source(source_file: str, page_from: int = 0, page_to: int = 0,
                limit: int = 25) -> str:
    """Liest ein Dokument in LESEREIHENFOLGE (nach Seite) — um einen ganzen Bericht
    zusammenzufassen oder zu bewerten, nicht zum Suchen. Keine Suchanfrage, kein
    Reranking; gibt die Abschnitte in Seitenreihenfolge zurück. `source_file` ist der
    Schlüssel aus list_sources. Optional grenzen page_from/page_to einen Seitenbereich
    ein; `limit` begrenzt die Zahl der Abschnitte (für lange Dokumente erhöhen oder
    einen Seitenbereich nutzen)."""
    return _index_op("read_source", source_file=source_file, page_from=page_from,
                     page_to=page_to, limit=limit)


@mcp.tool()
def remove_source(source_file: str) -> str:
    """Entfernt ein Dokument aus dem SUCHINDEX — um eine falsche, doppelte oder
    veraltete Quelle loszuwerden, die der Nutzer nicht mehr in den Treffern will.

    Sicher und umkehrbar: Die Datei wird NICHT gelöscht, sondern in einen _inbox/
    verschoben (ein Bereich, den der Watcher ignoriert), damit sie nicht neu indexiert
    wird; ihre Chunks + Literaturnotiz werden aus dem Index entfernt. `source_file` ist
    der von list_sources gezeigte Schlüssel (z. B. 'projekte/Bericht'). Pro Quelle
    einmal aufrufen."""
    return _index_op("remove_source", source_file=source_file)


@mcp.tool()
def rename_source(source_file: str, new_name: str) -> str:
    """Benennt ein indexiertes Dokument um / legt es neu ab und aktualisiert seine
    Index-Metadaten AN ORT UND STELLE (kein erneutes Embedding). Benennt/verschiebt
    die DATEI im Projektordner; `new_name` darf einen relativen Ordner enthalten, um
    sie auch zu verschieben (z. B. 'projekte/Schulzentrum/Endbericht'). Die
    ursprüngliche Dateiendung bleibt erhalten, wenn du sie weglässt. `source_file` ist
    der aktuelle Schlüssel aus list_sources."""
    return _index_op("rename_source", source_file=source_file, new_name=new_name)


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
    return _index_op("save_passage", topic=topic, text=text, source=source,
                     page=page, note=note)


@mcp.tool()
def list_passages(topic: str = "") -> str:
    """List saved passages: pass a topic to see the passages saved under it, or
    leave it empty for an overview of all topics. (Saved passages also surface in
    search, marked as a "saved passage" — this is the by-topic browse view.)"""
    return _index_op("list_passages", topic=topic)


@mcp.tool()
def list_notebook() -> str:
    """List your NOTEBOOK — your own .md notes and subfolders in WissensWIKI/.
    Deliberately NOT search-indexed (use search() for the corpus, list_passages()
    for verified passages). Open one with read_note, create or update with
    write_note."""
    return _index_op("list_notebook")


@mcp.tool()
def read_note(path: str) -> str:
    """Read a NOTEBOOK markdown file. `path` is relative to WissensWIKI/, e.g.
    'process-maturity.md' or 'Notizen/Mueller_2023.md'. Only the notebook
    (WissensWIKI/, excluding the indexed Passagen/) is reachable here — the corpus
    and the search index are not (use search() for those)."""
    return _index_op("read_note", path=path)


@mcp.tool()
def write_note(path: str, content: str) -> str:
    """Create a NOTEBOOK note, or APPEND a dated section to an existing one — it
    never silently overwrites, so your accumulated thinking is safe. For YOUR OWN
    text (concepts, drafts, conclusions); for a verbatim source quote that should
    be searchable evidence use save_passage instead. Saved as plain Markdown under
    WissensWIKI/ and deliberately NEVER added to the search index. `path` is
    relative to WissensWIKI/, e.g. 'process-maturity.md' or 'Kapitel/2.md' (any
    subfolder). The corpus and the search index are never touched."""
    return _index_op("write_note", path=path, content=content)


@mcp.tool()
def save_report(title: str, content: str) -> str:
    """Compile a RESULT/REPORT into the notebook for cheap reuse — a table of
    findings, a comparison, an analysis summary. Saved as Markdown under
    WissensWIKI/Berichte/<title>.md and NOT search-indexed, so you can read it
    back later with read_note('Berichte/<title>.md') instead of re-deriving it
    (no extra tokens). Writing the same title again appends a dated section."""
    return _index_op("save_report", title=title, content=content)


if __name__ == "__main__":
    mcp.run()
