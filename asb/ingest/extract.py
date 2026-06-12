"""Document extraction via Docling (PDF, DOCX, PPTX, Markdown, HTML).

Produces structured chunks (text / table / figure-caption) with chapter,
section and page metadata, plus the full markdown for contextual retrieval.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from asb import config
from asb.ingest.chunking import split_long_table, split_text


@dataclass
class Chunk:
    text: str
    chunk_type: str          # "text" | "table" | "figure"
    source_file: str         # file stem, NFC-normalized
    rel_path: str            # path relative to the vault (for PDF links)
    page_start: int
    page_end: int
    chapter: str
    section: str
    doc_type: str
    author: str
    year: str
    language: str = "en"
    context: str = ""        # LLM-generated context (contextual retrieval)
    chunk_id: str = field(default="")

    def __post_init__(self):
        if not self.chunk_id:
            raw = f"{self.source_file}|{self.page_start}|{self.text[:120]}"
            self.chunk_id = hashlib.sha256(raw.encode()).hexdigest()[:32]

    def qdrant_id(self) -> int:
        return int(hashlib.sha256(self.chunk_id.encode()).hexdigest()[:15], 16)

    def embedding_text(self) -> str:
        return f"{self.context}\n\n{self.text}" if self.context else self.text

    def payload(self) -> dict:
        from datetime import datetime
        return {
            "text": self.text, "context": self.context,
            "chunk_type": self.chunk_type, "source_file": self.source_file,
            "rel_path": self.rel_path, "page_start": self.page_start,
            "page_end": self.page_end, "chapter": self.chapter,
            "section": self.section, "doc_type": self.doc_type,
            "author": self.author, "year": self.year,
            "year_num": int(self.year) if self.year.isdigit() else 0,
            "language": self.language, "chunk_id": self.chunk_id,
            "ingest_timestamp": datetime.now().isoformat(timespec="seconds"),
        }


def parse_filename(stem: str) -> tuple[str, str]:
    """Derive (author, year) from 'Author_YYYY_Title' style names."""
    m = re.match(r"^([A-Za-zÀ-ſ]+(?:-[A-Za-zÀ-ſ]+)*)_(\d{4})_.+$", stem)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^([A-Za-zÀ-ſ]+)\s+(\d{4})\s*-\s*.+$", stem)
    if m:
        return m.group(1), m.group(2)
    return "Unknown", "????"


def doc_type_from_path(path: Path) -> str:
    """First subfolder under sources/ acts as the document type."""
    try:
        rel = path.relative_to(config.SOURCES_DIR)
        if len(rel.parts) > 1:
            return rel.parts[0]
    except ValueError:
        pass
    return "document"


def detect_language(sample: str) -> str:
    sample = sample[:4000].lower()
    de = sum(sample.count(t) for t in ("der ", "die ", "und ", "ist ", "mit ", "für "))
    en = sum(sample.count(t) for t in ("the ", "and ", " of ", " in ", " to ", "with "))
    if max(de, en) < 5:
        return "mixed"
    return "de" if de >= en else "en"


def extract(path: Path) -> tuple[list[Chunk], str]:
    """Run Docling and build chunks. Returns (chunks, full_markdown)."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import (
        PictureItem, SectionHeaderItem, TableItem, TextItem,
    )

    stem = config.normalize_source_key(path.stem)
    author, year = parse_filename(stem)
    doc_type = doc_type_from_path(path)
    try:
        rel_path = str(path.relative_to(config.VAULT))
    except ValueError:
        rel_path = path.name

    # Pin table mode explicitly so a future Docling default change cannot
    # silently degrade table quality.
    opts = PdfPipelineOptions()
    opts.do_table_structure = True
    opts.table_structure_options.mode = TableFormerMode.ACCURATE
    opts.table_structure_options.do_cell_matching = True
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )
    doc = converter.convert(str(path)).document

    try:
        full_markdown = doc.export_to_markdown()
    except Exception:
        full_markdown = ""
    language = detect_language(full_markdown)

    chunks: list[Chunk] = []
    chapter, section = "", ""
    buffer: list[str] = []
    buf_page_start, buf_page_end = 1, 1

    def meta(**kw) -> dict:
        base = dict(
            source_file=stem, rel_path=rel_path, chapter=chapter,
            section=section, doc_type=doc_type, author=author,
            year=year, language=language,
        )
        base.update(kw)
        return base

    def flush():
        nonlocal buffer, buf_page_start
        if not buffer:
            return
        full = "\n\n".join(buffer).strip()
        buffer = []
        if len(full) < config.MIN_CHUNK_CHARS:
            return
        prefix = f"[Chapter: {chapter}]" if chapter else ""
        if section:
            prefix += f" [Section: {section}]"
        if prefix:
            prefix += "\n"
        for sub in split_text(full, config.MAX_CHUNK_CHARS, config.OVERLAP_CHARS):
            chunks.append(Chunk(
                text=prefix + sub, chunk_type="text",
                page_start=buf_page_start, page_end=buf_page_end, **meta(),
            ))
        buf_page_start = buf_page_end

    for item, level in doc.iterate_items():
        page = item.prov[0].page_no if getattr(item, "prov", None) else 1

        if isinstance(item, SectionHeaderItem):
            flush()
            buf_page_start = page
            if level <= 1:
                chapter, section = item.text.strip(), ""
            else:
                section = item.text.strip()

        elif isinstance(item, TableItem):
            flush()
            try:
                table_md = item.export_to_markdown(doc=doc)
            except Exception:
                table_md = "[table could not be extracted]"
            header = f"[Chapter: {chapter}] [Section: {section}]\n" if chapter else ""
            parts = split_long_table(table_md, config.MAX_TABLE_CHARS)
            for i, part in enumerate(parts):
                label = "" if len(parts) == 1 else f" part {i + 1}/{len(parts)}"
                chunks.append(Chunk(
                    text=f"{header}**Table (p. {page}){label}:**\n\n{part}",
                    chunk_type="table", page_start=page, page_end=page, **meta(),
                ))
            buf_page_start = page

        elif isinstance(item, PictureItem):
            flush()
            caption = ""
            try:
                caption = (item.caption_text(doc) or "").strip()
            except Exception:
                pass
            header = f"[Chapter: {chapter}] [Section: {section}]\n" if chapter else ""
            display = caption or "No caption available"
            chunks.append(Chunk(
                text=f"{header}**Figure (p. {page}):** {display}",
                chunk_type="figure", page_start=page, page_end=page, **meta(),
            ))
            buf_page_start = page

        elif isinstance(item, TextItem):
            txt = (item.text or "").strip()
            if txt:
                buffer.append(txt)
                buf_page_end = page

    flush()
    return chunks, full_markdown[: config.CONTEXT_DOC_CHARS]
