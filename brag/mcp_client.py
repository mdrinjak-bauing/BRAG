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

# mcp 2.x renamed FastMCP to MCPServer and left a tombstone module behind that
# raises ModuleNotFoundError with the migration hint. The constructor, the
# .tool() decorator and .run() are call-compatible across both lines, so one
# import covers 1.x and 2.x — and BRAG keeps working whichever version the user
# ends up with, instead of the connector silently failing to start.
try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _MCPServer
except ModuleNotFoundError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _MCPServer
from mcp.types import ImageContent, TextContent

from brag import config
from brag.formatting import (
    PREVIEW_CHARS,
    format_hit,
    max_hits_for_budget,
    parse_meta_filter,
    preview_chars_for,
    with_topic_hint,
)

mcp = _MCPServer("brag")

PROJECT = os.environ.get("BRAG_PROJECT", "").strip()
_BASE = f"http://localhost:{config.BRIDGE_PORT}"
_BUSY = ("BRAG's search service is starting up or unavailable — your documents "
         "are safe; please retry in a few seconds.")


def _post(path: str, payload: dict, timeout: int = 180) -> dict | None:
    """POST JSON to the in-container bridge. Returns the parsed dict, or None on
    any transport/parse failure (the caller turns that into a friendly message —
    a bridge hiccup must never crash the MCP session). An HTTP ERROR response is
    not a transport failure: its body is passed through."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        _BASE + path, data=data,
        headers={"Content-Type": "application/json", "Host": "localhost"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        # Die Bridge HAT geantwortet (404/413/500 mit ok:False + message) — den Body
        # durchreichen, damit die echte Ursache beim Nutzer ankommt statt _BUSY
        # ("startet gerade"). HTTPError ist Subklasse von URLError und muss deshalb
        # VOR dem Transportfall stehen; sonst liest sich jeder echte Fehler als
        # Anlaufphase — am teuersten beim Umschalten, wo man dann auf eine
        # Aufwaermphase wartet, die es gar nicht gibt.
        try:
            return json.loads(e.read() or b"{}")
        except (OSError, json.JSONDecodeError, ValueError):
            return None
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
@with_topic_hint
def search(query: str, top_k: int = 0, doc_type: str = "",
           chunk_type: str = "", year_min: int = 0, year_max: int = 0,
           source_file: str = "", topic: str = "", meta_filter: str = "",
           reranking: bool | None = None, max_per_source: int = 0,
           mode: str = "normal", include_images: bool = True):
    """Hybride Suche (Bedeutung + Stichwort) über den Dokumenten-Korpus.

    Wähle `mode` passend zur Aufgabe (setzt sinnvolle Breite/Tiefe):
    - 'precise' punktgenaue Einzelfrage (wenige, fokussierte Treffer);
    - 'normal'  normale Frage (Standard);
    - 'review'  Literaturrecherche / breite Übersicht über viele Quellen (weites
      Netz; dazu mehrere Suchen mit verschiedenen Formulierungen, dann zusammenführen);
    - 'deep'    einen/wenige konkrete Berichte vertieft lesen — mit source_file= kombinieren.
    Für AUSWERTUNGEN statt einer Trefferliste: coverage() („wer schreibt zu X"),
    clusters() (Themen-Map) und compare_positions() (Quellen side-by-side).
    Feineinstellung (optional): top_k = genaue Trefferzahl; max_per_source = wie viele
    Treffer aus derselben Quelle kommen dürfen.

    Probiere mehrere Formulierungen (Synonyme, deutsch/englisch).
    chunk_type='table' für Zahlen/Statistiken, 'figure' für Abbildungen. Treffer
    auf Abbildungen legen der Antwort BIS ZU 3 BILDER bei (include_images=False
    schaltet das ab) — sieh sie dir an und lies konkrete Werte direkt daraus ab.
    topic=… filtert thematisch über ALLE doc_types hinweg, für „alles zu Thema X"
    (Kurzform von meta_filter='topic=…'; gültige Werte nennt der Hinweis unten,
    sofern dieser Korpus ein topic-Feld führt).
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
        # `topic` ist ein gewoehnliches Payload-Feld — der eigene Parameter ist nur
        # die Kurzform des dokumentierten Filters und wird hier darauf abgebildet.
        # Ein ausdruecklich gesetztes meta_filter='topic=…' behaelt Vorrang.
        "meta": {"topic": topic.strip(), **parse_meta_filter(meta_filter)}
                if topic.strip() else parse_meta_filter(meta_filter),
        "include_images": bool(include_images),
    })
    if resp is None:
        return _BUSY
    if not resp.get("ok"):
        return resp.get("message", "search failed")
    hits = resp.get("hits", [])
    if not hits:
        return ("No hits. Try different phrasing, fewer filters, or check "
                "list_sources() whether the document is indexed at all.")
    # Keep the answer inside the MCP response budget — and SAY SO when it bites. A
    # silently shortened list is the actual problem: it reads exactly like a
    # complete one, so nobody thinks to ask for more.
    ceiling = max_hits_for_budget()
    dropped = max(0, len(hits) - ceiling)
    if dropped:
        hits = hits[:ceiling]
    per_hit = preview_chars_for(len(hits))
    images = resp.get("images") or []
    attached = set(resp.get("attached_ids") or [])
    notes = []
    # Quellen-Nenner: "8 hits" allein sagt nichts darueber, ob das viel oder wenig
    # vom Feld ist. _coverage ist Such-Metadatum (kein Payload-Feld) — abgeworfen,
    # bevor der erste Treffer formatiert wird. gezeigt kommt aus query.search()'s
    # EIGENER (Vor-Budget-)Trefferliste — trifft der Budget-Deckel hier oben noch
    # zusaetzlich zu, ist das ein veralteter Zaehler; aus der tatsaechlich
    # gerenderten (bereits gekuerzten) hits-Liste neu berechnet, sonst behauptet
    # der Kopf mehr gezeigte Quellen, als Trefferbloecke folgen (N-1, Re-Review).
    cov = hits[0].pop("_coverage", None) if hits else None
    if cov:
        cov = {**cov, "gezeigt": len({h.get("source_file") for h in hits
                                       if h.get("source_file")})}
    if cov and cov.get("beitragend", 0) > cov.get("gezeigt", 0):
        notes.append(f"showing {cov['gezeigt']} of {cov['beitragend']} sources that "
                     f"contribute to this question")
    # Ist die Liste ZU ENDE oder nur ABGESCHNITTEN? Am Bildschirm sieht beides
    # gleich aus; die Reranker-Scores kennen den Unterschied (query._saturation,
    # Aufgabe 8). _saturation ist wie _coverage Such-Metadatum — abgeworfen, nicht
    # gerendert, aus demselben (Vor-Budget-)Treffer-Objekt. Der Riegel-Zustand
    # "unbewertet" (kein Reranker-Score vorhanden, z. B. RERANK_PROFILE=off, oder
    # der Rest nur teilweise bewertet, M-7) rendert BEWUSST KEINE Notiz — Stille
    # ist hier die richtige Antwort, nicht eine gehedgte: der Riegel existiert
    # genau dafuer, keine Behauptung ohne Bewertungsgrundlage zu machen.
    sat = hits[0].pop("_saturation", None) if hits else None
    if sat and sat.get("state") == "abgeschnitten":
        notes.append(f"list CUT OFF — {sat['weitere']} further hits are still relevant but "
                     f"were held back by top_k or by the per-source cap; re-run with a "
                     f"larger top_k / max_per_source to see them")
    elif sat and sat.get("state") == "erschoepft":
        notes.append("list EXHAUSTED — scores drop off after the last hit, "
                     "nothing relevant follows")
    if dropped:
        notes.append(f"{dropped} further ranked hits omitted to fit the response limit "
                     f"— narrow the query or re-run with a smaller top_k to see them")
    if per_hit < PREVIEW_CHARS:
        notes.append(f"previews shortened to {per_hit} chars; full text via read_source()")
    head = f"**{len(hits)} hits** for: {query}"
    if notes:
        head += "\n_(" + " · ".join(notes) + ")_"
    out = [head + "\n"]
    for i, h in enumerate(hits):
        block = format_hit(i + 1, h, project=PROJECT, preview_chars=per_hit)
        if attached and str(h.get("chunk_id", "")) in attached:
            block += "🖼️ Die Abbildung liegt dieser Antwort als Bild bei.\n"
        out.append(block)
    text = "\n".join(out)
    if not images:
        return text
    return [TextContent(type="text", text=text)] + [
        ImageContent(type="image", data=img.get("b64", ""),
                     mimeType=img.get("mime", "image/jpeg"))
        for img in images if img.get("b64")
    ]


@mcp.tool()
def coverage(query: str, top_k: int = 50, min_score: float | None = None,
             mode: str = "broad") -> str:
    """Stand der Forschung / „Wer schreibt zu X?" — aggregiert die Treffer PRO QUELLE
    (statt einer flachen Trefferliste) und teilt sie in substanziell vs. peripheral.
    `mode`: 'broad' (Quellen mit ≥3 Treffern, „wer schreibt VIEL"), 'specific'
    (fokussierte Spezialquellen mit einem starken Treffer zuerst) oder 'both'.
    Für eine Literaturübersicht/„Stand der Forschung" zu einem Thema."""
    return _index_op("coverage", query=query, top_k=top_k,
                     min_score=min_score, mode=mode)


@mcp.tool()
def clusters(query: str, top_k: int = 40, n_clusters: int = 5) -> str:
    """Themen-Map: clustert die Treffer via K-Means im Embedding-Raum in Sub-Themen
    und gibt pro Cluster einen Repräsentanten + die Quellen-/Kapitel-Verteilung aus.
    Für „Welche Sub-Aspekte/Teilthemen hat Y?" — explorativ statt einer Rangliste."""
    return _index_op("clusters", query=query, top_k=top_k,
                     n_clusters=n_clusters)


@mcp.tool()
def compare_positions(query: str, sources: list[str], top_k_per_source: int = 3) -> str:
    """Stellt 2–7 KONKRETE Quellen zu einer Frage SIDE-BY-SIDE gegenüber — je Quelle die
    Top-Treffer. `sources` = Liste von `source_file`-Schlüsseln (siehe list_sources).
    Für „Wie definieren/bewerten Quelle A und B das Thema X?"."""
    return _index_op("compare_positions", query=query, sources=sources,
                     top_k_per_source=top_k_per_source)


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
    einen Seitenbereich nutzen). Für VIELE Berichte: pro Bericht EINMAL aufrufen, jeden
    einzeln auswerten, dann zusammenführen — nicht alles in eine Abfrage zwängen."""
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


if config.PASSAGES_LAYOUT == "promotion":
    # Signatures kept identical to brag.mcp_server; the bridge routes this layout
    # to brag.passages_promotion (one file per chapter, not indexed).
    @mcp.tool()
    def save_passage(source: str, text: str, chapter: str, author: str = "",
                     year: str = "", page_start: str = "", page_end: str = "",
                     note: str = "") -> str:
        """Store a corpus passage as evidence for a chapter. Required: source, text,
        chapter; author/year/page_start/page_end/note refine the citation line."""
        return _index_op("save_passage", source=source, text=text, chapter=chapter,
                         author=author, year=year, page_start=page_start,
                         page_end=page_end, note=note)

    @mcp.tool()
    def list_passages(chapter: str = "") -> str:
        """Show stored evidence: with `chapter` the chapter file's contents, without it
        an overview of all chapter files and how many passages each holds."""
        return _index_op("list_passages", chapter=chapter)
else:
    @mcp.tool()
    def save_passage(topic: str, text: str, source: str, page: str = "",
                     note: str = "") -> str:
        """Sichert eine zitierfähige Passage unter einem Thema (z. B. ein Kapitel/Motiv).

        WANN was: ein wörtliches ZITAT aus einer Quelle → save_passage (wird durchsuchbarer
        Beleg); EIGENER Text (Notizen, Entwürfe, Schlüsse, auch ein zusammengestelltes
        Ergebnis) → write_note.

        Baut deine Belegsammlung in WissensWIKI/Quellenbelege/<thema>.md auf UND indexiert die
        Passage für die semantische Suche, sodass ein späterer Chat (auch mit einem anderen
        Anbieter) sie über `search` wiederfindet — sie erscheint klar markiert als
        „gespeicherte Passage", getrennt von Primärquellen. So hältst du Erkenntnisse,
        Entscheidungen und Definitionen einer Arbeitssitzung fest, damit das Wissen im
        Ordner lebt und nicht in einem Chat-Verlauf."""
        return _index_op("save_passage", topic=topic, text=text, source=source,
                         page=page, note=note)

    @mcp.tool()
    def list_passages(topic: str = "") -> str:
        """Listet gespeicherte Passagen: mit Thema die darunter gesicherten Passagen,
        ohne Thema eine Übersicht aller Themen. (Gespeicherte Passagen erscheinen auch in
        der Suche, markiert als „gespeicherte Passage" — dies ist die Themen-Übersicht.)"""
        return _index_op("list_passages", topic=topic)


@mcp.tool()
def list_notebook() -> str:
    """Listet dein NOTIZBUCH — deine eigenen .md-Notizen und Unterordner in
    WissensWIKI/. Bewusst NICHT indexiert (für den Korpus search(), für gesicherte
    Passagen list_passages()). Öffnen mit read_note, anlegen/ergänzen mit write_note."""
    return _index_op("list_notebook")


@mcp.tool()
def read_note(path: str) -> str:
    """Liest eine NOTIZBUCH-Markdown-Datei. `path` ist relativ zu WissensWIKI/, z. B.
    'prozessreife.md' oder 'Wissen/Mueller_2023.md'. Erreichbar ist nur das Notizbuch
    (WissensWIKI/, ohne das indexierte Quellenbelege/) — der Korpus und der Suchindex nicht
    (dafür search())."""
    return _index_op("read_note", path=path)


@mcp.tool()
def write_note(path: str, content: str) -> str:
    """Legt eine NOTIZBUCH-Notiz an oder HÄNGT einen datierten Abschnitt an eine
    bestehende an — überschreibt nie still, dein gesammeltes Denken bleibt sicher. Für
    EIGENEN Text (Konzepte, Entwürfe, Schlüsse); für ein wörtliches Quellenzitat, das
    durchsuchbarer Beleg werden soll, stattdessen save_passage. Wird als reines Markdown
    unter WissensWIKI/ gespeichert und bewusst NIE in den Suchindex aufgenommen. `path`
    ist relativ zu WissensWIKI/, z. B. 'prozessreife.md' oder 'Kapitel/2.md' (beliebiger
    Unterordner). Korpus und Suchindex werden nie berührt."""
    return _index_op("write_note", path=path, content=content)


@mcp.tool()
def recent_sources(limit: int = 15) -> str:
    """Zeigt die ZULETZT aufgenommenen/aktualisierten Dokumente (nach Indexier-
    Zeitpunkt absteigend) — um zu sehen, was neu im Projektordner gelandet ist.
    `limit` begrenzt die Anzahl."""
    return _index_op("recent_sources", limit=limit)


@mcp.tool()
def set_metadata(folder: str, key: str, value: str) -> str:
    """Setzt ein eigenes Metadaten-Feld für einen KORPUS-Ordner (schreibt/ergänzt
    dessen _meta.txt) und wendet es sofort auf die bereits indexierten Dokumente an
    (kein erneutes Embedding). So taggst du z. B. einen Ordner mit projekt=…/kunde=…/
    phase=… und filterst danach mit search(meta_filter='…'). `folder` ist relativ zum
    Projektordner (z. B. 'Nachtraege' oder 'projekte/Schulzentrum')."""
    return _index_op("set_metadata", folder=folder, key=key, value=value)


@mcp.tool()
def delete_note(path: str, confirm: bool = False) -> str:
    """Löscht eine Notiz im WissensWIKI-Notizbuch (Wissen/, …) — NICHT Quellenbelege/
    (dafür delete_passage) und nie den Korpus. Schutzabfrage:
    ohne confirm=True wird nur rückgefragt, erst confirm=True löscht. Zum Korrigieren:
    löschen und mit write_note neu schreiben."""
    return _index_op("delete_note", path=path, confirm=confirm)


@mcp.tool()
def delete_passage(topic: str, confirm: bool = False) -> str:
    """Löscht alle gespeicherten Passagen eines Themas (WissensWIKI/Quellenbelege/<thema>.md)
    UND entfernt sie aus dem Suchindex. Schutzabfrage: ohne confirm=True wird nur
    rückgefragt, erst confirm=True löscht. Zum Korrigieren: löschen und mit save_passage
    neu sichern."""
    return _index_op("delete_passage", topic=topic, confirm=confirm)


@mcp.tool()
def move_note(path: str, new_path: str) -> str:
    """Verschiebt oder benennt eine NOTIZBUCH-Datei im WissensWIKI um (legt Ziel-
    Unterordner automatisch an, überschreibt nie). So räumst du dein Notizbuch um
    oder benennst Dateien um. Nur das Notizbuch (Wissen/, …) — NICHT Quellenbelege/
    (dort delete_passage + save_passage) und nie den Korpus. `path`/`new_path` sind
    relativ zu WissensWIKI/, z. B. move_note('Wissen/x.md', 'Kapitel/2/x.md')."""
    return _index_op("move_note", path=path, new_path=new_path)


@mcp.tool()
def open_pdf(source_file: str, pdf_page: int = 0, book_page: str = "",
             page: int = 0) -> str:
    """Open a corpus PDF at a given page in the desktop viewer. `source_file` is the
    source key from the search results. Give either `book_page` (the printed page shown
    in a hit, resolved via /PageLabels) or `pdf_page` (the physical page)."""
    return _index_op("open_pdf", source_file=source_file, pdf_page=pdf_page,
                     book_page=book_page, page=page)


# ── Vault files — BRAG as a single MCP for corpus and notes alike ──────────────
# Forwarded to the bridge process, which holds the vault paths and enforces the
# write protection configured for it.

@mcp.tool()
def vault_read(path: str) -> str:
    """Read a text/Markdown file (.md/.txt/.csv) from the vault; `path` is relative to
    the vault root. For PDF/Word/Excel use `vault_extract`."""
    return _index_op("vault_read", path=path)


@mcp.tool()
def vault_list(subdir: str = "") -> str:
    """List files and folders under a vault path (empty = vault root)."""
    return _index_op("vault_list", subdir=subdir)


@mcp.tool()
def vault_search(query: str, content: bool = True, limit: int = 40, root: str = "") -> str:
    """Search vault FILES by name and optionally by content — not the corpus (use
    `search` for that). `root` selects a configured secondary vault root."""
    return _index_op("vault_search", query=query, content=content, limit=limit, root=root)


@mcp.tool()
def vault_write(path: str, content: str, overwrite: bool = False) -> str:
    """Write or create a vault file. An existing file is replaced only with
    `overwrite=True`. Write-protected areas are refused."""
    return _index_op("vault_write", path=path, content=content, overwrite=overwrite)


@mcp.tool()
def vault_append(path: str, content: str) -> str:
    """Append text to a vault file, creating it if absent. Same write protection as
    `vault_write`."""
    return _index_op("vault_append", path=path, content=content)


@mcp.tool()
def vault_edit(path: str, old_string: str, new_string: str,
               replace_all: bool = False) -> str:
    """Replace an exact snippet in an EXISTING vault file in place — the surgical
    counterpart to `vault_write` (whole file) and `vault_append` (end only).
    `old_string` must match exactly and be unique, otherwise the edit is refused; use
    `replace_all=True` for every occurrence. Creates no new file."""
    return _index_op("vault_edit", path=path, old_string=old_string,
                     new_string=new_string, replace_all=replace_all)


@mcp.tool()
def vault_extract(path: str, page_from: int = 0, page_to: int = 0) -> str:
    """Extract text from a vault PDF/Word/Excel file (.pdf/.docx/.xlsx), read-only.
    Use it only when explicitly asked; `vault_read` stays the default for notes. PDFs
    can be limited to `page_from`/`page_to` (1-based). Scans without a text layer
    return nothing — no OCR here."""
    return _index_op("vault_extract", path=path, page_from=page_from, page_to=page_to)


if __name__ == "__main__":
    mcp.run()
