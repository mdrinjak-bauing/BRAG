"""Auto-generated literature notes: one markdown file per ingested source,
Obsidian-compatible, written to wissensspeicher/notes/."""

from datetime import date

from asb import config
from asb.ingest.extract import Chunk


def write_note(chunks: list[Chunk]) -> None:
    if not chunks:
        return
    c0 = chunks[0]
    config.NOTES_DIR.mkdir(parents=True, exist_ok=True)
    chapters = []
    for c in chunks:
        if c.chapter and c.chapter not in chapters:
            chapters.append(c.chapter)
    n_tables = sum(1 for c in chunks if c.chunk_type == "table")
    n_figures = sum(1 for c in chunks if c.chunk_type == "figure")

    lines = [
        "---",
        f"source: {c0.source_file}",
        f"author: {c0.author}",
        f"year: '{c0.year}'",
        f"doc_type: {c0.doc_type}",
        f"language: {c0.language}",
        f"ingested: {date.today().isoformat()}",
        "---",
        "",
        f"# {c0.source_file}",
        "",
        f"**File:** `{c0.rel_path}`  ",
        f"**Indexed:** {len(chunks)} chunks "
        f"({n_tables} tables, {n_figures} figures)",
        "",
    ]
    if chapters:
        lines.append("## Structure")
        lines.append("")
        lines.extend(f"- {ch}" for ch in chapters[:40])
        lines.append("")
    lines.append("## My notes")
    lines.append("")
    lines.append("_Add your own thoughts here — this section is never overwritten._")

    note_path = config.NOTES_DIR / f"{c0.source_file}.md"
    if note_path.exists():
        # Preserve everything the user wrote below the "My notes" marker
        old = note_path.read_text(encoding="utf-8")
        marker = "## My notes"
        if marker in old:
            user_part = old.split(marker, 1)[1]
            lines = lines[: lines.index("## My notes")] + [marker + user_part.rstrip()]
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def rename_note(old_source_file: str, meta: dict) -> None:
    """Move a source's literature note to its new name and refresh the
    filename-derived fields (source/author/year/doc_type/title/file path),
    preserving the user's "My notes" section and the structure list. Used by
    the lightweight rename path — no chunks needed."""
    import re

    old = config.NOTES_DIR / f"{config.normalize_source_key(old_source_file)}.md"
    if not old.exists():
        return
    text = old.read_text(encoding="utf-8")
    new_key = meta["source_file"]
    repl = [
        (r"(?m)^source: .*$", f"source: {new_key}"),
        (r"(?m)^author: .*$", f"author: {meta['author']}"),
        (r"(?m)^year: .*$", f"year: '{meta['year']}'"),
        (r"(?m)^doc_type: .*$", f"doc_type: {meta['doc_type']}"),
        (r"(?m)^# .*$", f"# {new_key}"),
        (r"(?m)^\*\*File:\*\* .*$", f"**File:** `{meta['rel_path']}`  "),
    ]
    for pattern, replacement in repl:
        # function replacement avoids backslash interpretation in paths/values
        text = re.sub(pattern, lambda _m, r=replacement: r, text, count=1)
    new = config.NOTES_DIR / f"{new_key}.md"
    new.write_text(text, encoding="utf-8")
    if new.resolve() != old.resolve():
        old.unlink(missing_ok=True)


def delete_note(source_file: str) -> None:
    note = config.NOTES_DIR / f"{config.normalize_source_key(source_file)}.md"
    if note.exists():
        note.unlink()
