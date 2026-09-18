"""Belege (gespeicherte Passagen) im KAPITEL-Layout (`BRAG_PASSAGES_LAYOUT=promotion`).

Im Unterschied zu BRAGs eingebautem save_passage (das nach `PASSAGES_DIR` schreibt
und die Passage in den Such-Index aufnimmt) legt dieses Modul eine Datei je Kapitel
an (`KapN_*.md`) — reine Datei-Ablage, kein DB-Index.

Der Kapitel-Dateiname wird dynamisch bestimmt: aus einer Gliederungsdatei
(Zeilenform `# Kapitel N — Name`) plus Kontinuitätsregel (existiert schon eine
`KapN_*.md`, gewinnt deren Name, damit Belege bei einer Umbenennung nicht zerfallen).

Alle drei Ablageorte kommen aus der Umgebung und sind ohne Konfiguration leer —
`BRAG_PASSAGES_ROOT`, `BRAG_OUTLINE_FILE`, `BRAG_LITNOTES_DIR` (siehe `config`).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from brag import activity_log, config


def _passages_dir() -> Path:
    """Ordner der Kapiteldateien. `BRAG_PASSAGES_ROOT` (vault-relativ) gewinnt;
    ohne Wert die generische Belegablage des Standard-Layouts."""
    rel = config.PASSAGES_ROOT
    return (Path(config.VAULT) / rel) if rel else Path(config.PASSAGES_DIR)


def _gliederung() -> Path | None:
    """Gliederungsdatei (vault-relativ) aus `BRAG_OUTLINE_FILE`, oder None."""
    rel = config.OUTLINE_FILE
    return (Path(config.VAULT) / rel) if rel else None


def _kapitel_kuerzel() -> dict:
    """Kapitelnummer → `KapN_<Slug>`: aus der Gliederungsdatei, mit Kontinuitätsregel
    (vorhandene KapN_*.md im Passagen-Ordner gewinnt). Leeres/fehlendes Mapping ist ok —
    dann wird der `chapter`-Wert als freier Dateiname genutzt."""
    mapping: dict[str, str] = {}
    gliederung = _gliederung()
    try:
        for line in (gliederung.read_text(encoding="utf-8").splitlines()
                     if gliederung else []):
            m = re.match(r"^#\s+Kapitel\s+(\d+)\s*[—–-]\s*(.+?)\s*$", line)
            if m:
                num = m.group(1)
                slug = re.sub(r"[^\wÄÖÜäöüß]+", "_", m.group(2)).strip("_")
                mapping[num] = f"Kap{num}_{slug}"
    except OSError:
        pass
    pdir = _passages_dir()
    if pdir.exists():
        for num in set(mapping) | {str(n) for n in range(1, 13)}:
            existing = sorted(pdir.glob(f"Kap{num}_*.md"))
            if existing:
                mapping[num] = existing[0].stem
    return mapping


def _filename_for(chapter: str) -> str:
    fn = _kapitel_kuerzel().get(chapter.strip(), chapter.strip().replace(" ", "_"))
    return fn if fn.endswith(".md") else fn + ".md"


def _append_to_litnote(source: str, chapter: str, pages: str, note: str, text: str) -> None:
    """Trägt den Beleg zusätzlich in die Notiz (Steckbrief) der Quelle ein — Abschnitt
    'Belegt in der Dissertation' —, damit von der Quelle aus sichtbar ist, welche
    Aussagen sie trägt. Ordner: `BRAG_LITNOTES_DIR` (vault-relativ), ohne Wert der
    generische Notizordner. Still, wenn keine Notiz existiert oder der Beleg schon steht."""
    base = (Path(config.VAULT) / config.LITNOTES_DIR) if config.LITNOTES_DIR \
        else Path(config.NOTES_DIR)
    lit = base / f"{source}.md"
    if not lit.exists():
        return
    try:
        content = lit.read_text(encoding="utf-8")
    except OSError:
        return
    kap = _kapitel_kuerzel().get(chapter.strip(), chapter.strip())
    claim = (note.strip() or text.strip()[:160])
    bel = (f"- **{kap}**{(' (' + pages + ')') if pages else ''}: {claim} "
           f"— [[Quellenbelege/{_filename_for(chapter)[:-3]}]]")
    if bel.split("—")[0].strip() in content:          # grobe Dublettensperre
        return
    header = "## Belegt in der Dissertation"
    content = (content.rstrip() + "\n" + bel + "\n") if header in content \
        else (content.rstrip() + f"\n\n{header}\n\n{bel}\n")
    lit.write_text(content, encoding="utf-8")


def save_passage(source: str, text: str, chapter: str, author: str = "",
                 year: str = "", page_start: str = "", page_end: str = "",
                 note: str = "") -> str:
    """Hängt einen Beleg an die Kapiteldatei an (legt sie mit Kopf an, falls neu)."""
    if not (str(source).strip() and str(text).strip() and str(chapter).strip()):
        return "⚠️ save_passage braucht mindestens: source, text, chapter."

    pdir = _passages_dir()
    pdir.mkdir(parents=True, exist_ok=True)
    filepath = pdir / _filename_for(chapter)

    if not str(page_start).strip():
        pages = ""
    elif not str(page_end).strip() or str(page_start) == str(page_end):
        pages = f"S. {page_start}"
    else:
        pages = f"S. {page_start}–{page_end}"

    if not filepath.exists():
        titel = _kapitel_kuerzel().get(chapter.strip(), chapter.strip())
        filepath.write_text(
            f"# Passagen — {titel}\n\n_Automatisch angelegt am "
            f"{datetime.now().strftime('%Y-%m-%d')}_\n\n---\n\n",
            encoding="utf-8")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    cite_bits = ", ".join(
        b for b in [str(author).strip(), str(year).strip(), pages] if b) or source
    open_hint = ""
    if str(page_start).strip():
        open_hint = f" · öffnen: `open_pdf(\"{source}\", book_page=\"{page_start}\")`"
    entry = f"## ({cite_bits})\n"
    entry += f"**Quelle:** {source}{open_hint}  \n"
    entry += f"**Gespeichert:** {timestamp}  \n"
    if note:
        entry += f"**Notiz:** {note}  \n"
    entry += f"\n> {text.strip()}\n\n---\n\n"

    with filepath.open("a", encoding="utf-8") as f:
        f.write(entry)
    _append_to_litnote(source, chapter, pages, note, text)  # 2026-07-01: auch in die Literaturnotiz
    activity_log.log_op("save_passage", chapter=chapter.strip(), source=source,
                        pages=pages)
    return f"Beleg gespeichert in {filepath.name}: ({cite_bits})"


def list_passages(chapter: str = "") -> str:
    """Übersicht aller Kapiteldateien (ohne `chapter`) oder Inhalt einer Datei."""
    pdir = _passages_dir()
    if not chapter:
        files = sorted(pdir.glob("*.md")) if pdir.exists() else []
        if not files:
            try:                                   # Ort nennen, ohne den Vault-Pfad zu zeigen
                wo = pdir.relative_to(Path(config.VAULT))
            except ValueError:
                wo = pdir
            return f"Noch keine Belege gespeichert ({wo})."
        lines = [f"## Belege — Übersicht ({len(files)} Kapitel)\n"]
        for f in files:
            count = f.read_text(encoding="utf-8").count("\n## (")
            lines.append(f"- **{f.stem}** — {count} Beleg(e)")
        return "\n".join(lines)
    filepath = pdir / _filename_for(chapter)
    if not filepath.exists():
        return f"Keine Belege für '{chapter}' — Datei existiert noch nicht."
    return filepath.read_text(encoding="utf-8")
