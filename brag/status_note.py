"""Plain-language system status note — a "sign of life" for non-technical users.

The watcher rewrites WissensWIKI/SYSTEM-STATUS.md every
STATUS_NOTE_INTERVAL_HOURS so a silent failure (search DB down, documents
stuck, indexing blocked) becomes VISIBLE in the user's own workspace: one
glance at the note answers "is my system healthy?" without opening a terminal.
Ported idea from the sister pipeline's weekly health check (audit 2026-06-09).

Read-only + best-effort: gathers what it can, never raises, starts/stops
nothing. Deliberately NO LLM/API-key calls — a status tick must not spend
quota. Language follows VAULT_LANGUAGE (like the other user-facing markers).
"""

import json
from datetime import datetime

from brag import config

OK, WARN, BAD = "✅", "⚠️", "❌"


def _qdrant_line() -> tuple[str, str, str]:
    """(icon, DE line, EN line) for the search database + corpus size."""
    try:
        from brag import storage
        client = storage.get_client()
        try:
            names = {c.name for c in client.get_collections().collections}
            if config.COLLECTION_NAME not in names:
                return (WARN,
                        "Suchdatenbank läuft, aber der Index ist noch leer — "
                        "lege ein Dokument in den Projektordner.",
                        "Search database is up, but the index is still empty — "
                        "drop a document into your project folder.")
            info = client.get_collection(config.COLLECTION_NAME)
            n_chunks = info.points_count or 0
            n_sources = len(storage.list_corpus_sources(client))
        finally:
            client.close()
        return (OK,
                f"Suchdatenbank läuft: {n_sources} Quellen, {n_chunks} Abschnitte.",
                f"Search database is up: {n_sources} sources, {n_chunks} chunks.")
    except Exception:  # noqa: BLE001 — status must never crash the watcher
        return (BAD,
                "Suchdatenbank NICHT erreichbar — Docker Desktop starten bzw. "
                "status-Skript ausführen.",
                "Search database NOT reachable — start Docker Desktop or run "
                "the status script.")


def _ingest_lines() -> list[tuple[str, str, str]]:
    """Status of the ingest pipeline from the durable logs/markers."""
    out: list[tuple[str, str, str]] = []
    # Last successful ingest + partials from the ingest log.
    try:
        last_ts, partials = "", 0
        with open(config.INGEST_LOG, encoding="utf-8") as f:
            states: dict[str, dict] = {}
            for line in f:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("source_file"):
                    states[e["source_file"]] = e
        for e in states.values():
            ts = e.get("ingested_at", "")
            last_ts = max(last_ts, ts)
            if e.get("partial"):
                partials += 1
        if last_ts:
            out.append((OK,
                        f"Letzte Aufnahme: {last_ts[:16].replace('T', ' ')} Uhr.",
                        f"Last ingest: {last_ts[:16].replace('T', ' ')}."))
        if partials:
            out.append((WARN,
                        f"{partials} Dokument(e) nur teilweise aufgenommen — "
                        "wird beim nächsten Start automatisch nachgeholt.",
                        f"{partials} document(s) only partially ingested — "
                        "retried automatically on the next start."))
    except FileNotFoundError:
        out.append((WARN,
                    "Noch kein Dokument aufgenommen.",
                    "No document ingested yet."))
    except Exception:  # noqa: BLE001
        pass
    # Visible markers written by the pipeline.
    for de_name, en_name, de_msg, en_msg in [
        ("INDEXIERUNG-GESTOPPT.md", "INDEXING-STOPPED.md",
         "Einige Dateien wurden nach Abstürzen gestoppt — siehe {f}.",
         "Some files were stopped after crashes — see {f}."),
        ("NICHT-INDEXIERT.md", "NOT-INDEXED.md",
         "Einige Dateien konnten nicht indexiert werden — siehe {f}.",
         "Some files could not be indexed — see {f}."),
    ]:
        for marker in (de_name, en_name):
            if (config.WISSENSWIKI_DIR / marker).exists():
                out.append((WARN, de_msg.format(f=marker), en_msg.format(f=marker)))
                break
    return out


def _config_line() -> tuple[str, str, str]:
    vision = "an" if config.VISION_ENABLED else "aus"
    vision_en = "on" if config.VISION_ENABLED else "off"
    imgs = "an" if config.SEARCH_IMAGES_ENABLED else "aus"
    imgs_en = "on" if config.SEARCH_IMAGES_ENABLED else "off"
    return (OK,
            f"Profil: {config.PROFILE_NAME} ({config.LLM_MODEL}) · "
            f"Abbildungs-Beschreibung {vision} · Bilder in der Suche {imgs}.",
            f"Profile: {config.PROFILE_NAME} ({config.LLM_MODEL}) · "
            f"figure descriptions {vision_en} · images in search {imgs_en}.")


def write_status_note() -> None:
    """Render and write WissensWIKI/SYSTEM-STATUS.md (overwrites — it is a
    status display, not a log). Never raises."""
    try:
        german = config.VAULT_LANGUAGE.strip().lower().startswith("german")
        rows = [_qdrant_line(), *_ingest_lines(), _config_line()]
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        if german:
            lines = [
                "# System-Status — dein BRAG auf einen Blick",
                "",
                f"_Automatisch aktualisiert: {stamp} (diese Datei wird "
                "überschrieben — nichts hier hineinschreiben)._",
                "",
            ]
            lines += [f"- {icon} {de}" for icon, de, _en in rows]
            lines += [
                "",
                "Wenn hier etwas rot ist: `status`-Skript im BRAG-Ordner "
                "doppelklicken — es erklärt die nächsten Schritte.",
            ]
        else:
            lines = [
                "# System status — your BRAG at a glance",
                "",
                f"_Auto-updated: {stamp} (this file is overwritten — don't "
                "write into it)._",
                "",
            ]
            lines += [f"- {icon} {en}" for icon, _de, en in rows]
            lines += [
                "",
                "If something is red here: double-click the `status` script in "
                "the BRAG folder — it explains the next steps.",
            ]
        config.WISSENSWIKI_DIR.mkdir(parents=True, exist_ok=True)
        (config.WISSENSWIKI_DIR / "SYSTEM-STATUS.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
    except Exception as e:  # noqa: BLE001 — the status tick must never crash anything
        print(f"  status note skipped (non-fatal): {str(e)[:80]}")
