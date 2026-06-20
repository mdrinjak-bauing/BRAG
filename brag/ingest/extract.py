"""Document extraction via Docling (PDF, DOCX, PPTX, Markdown, HTML).

Produces structured chunks (text / table / figure-caption) with chapter,
section and page metadata, plus the full markdown for contextual retrieval.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from brag import config
from brag.ingest.chunking import split_long_table, split_text_paged


@dataclass
class Chunk:
    text: str
    chunk_type: str          # "text" | "table" | "figure"
    source_file: str         # path-qualified key (rel path under sources/, no suffix)
    rel_path: str            # path relative to the knowledge store (for PDF links)
    page_start: int
    page_end: int
    chapter: str
    section: str
    doc_type: str
    author: str
    year: str
    language: str = "en"
    context: str = ""        # LLM-generated context (contextual retrieval)
    image_b64: str = ""      # base64 PNG of a figure (vision pass); not stored
    custom_meta: dict = field(default_factory=dict)  # user fields from _meta.txt
    chunk_id: str = field(default="")

    def __post_init__(self):
        if not self.chunk_id:
            # Hash the FULL text, not a 120-char prefix: two distinct chunks on
            # the same page whose first 120 chars matched (a long
            # "[Chapter: …] [Section: …]" prefix, repeated boilerplate, or split
            # table parts whose "part i/n" label trails that prefix) would
            # otherwise collide on the same id and silently overwrite each other
            # on upsert. Hashing the whole text stays deterministic, so an
            # idempotent re-ingest of an identical chunk still overwrites in place.
            raw = f"{self.source_file}|{self.page_start}|{self.text}"
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
        } | {k: v for k, v in self.custom_meta.items()
             if k not in RESERVED_KEYS and k not in OVERRIDABLE_KEYS}


# Payload keys owned by the system — user metadata may override the three
# descriptive ones (author, year, doc_type) but never the structural ones.
RESERVED_KEYS = {
    "text", "context", "chunk_type", "source_file", "rel_path",
    "page_start", "page_end", "chapter", "section", "year_num",
    "language", "chunk_id", "ingest_timestamp",
}
OVERRIDABLE_KEYS = {"author", "year", "doc_type"}


def _parse_meta_file(path: Path) -> dict:
    """Parse a `_meta.txt` file: one `key: value` per line, `#` comments.
    Deliberately the most forgiving format possible — no JSON/YAML syntax
    errors for non-technical users."""
    meta: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower().replace(" ", "_")
            if key and key not in RESERVED_KEYS and value.strip():
                meta[key] = value.strip()
    except OSError:
        pass
    return meta


def load_folder_meta(file_path: Path) -> dict:
    """Collect user metadata for a document by merging `_meta.txt` files
    from sources/ down to the document's folder — deeper folders win.

    Example: sources/projects/_meta.txt sets `client: City of Hamm`,
    sources/projects/School_Center/_meta.txt sets `project: School Center`
    → every document in that folder carries both fields, filterable in
    search ("only hits where project = School Center")."""
    meta: dict[str, str] = {}
    try:
        rel_parts = file_path.parent.resolve().relative_to(
            config.SOURCES_DIR.resolve()).parts
    except ValueError:
        rel_parts = ()
    folder = config.SOURCES_DIR
    for part in ("",) + rel_parts:
        if part:
            folder = folder / part
        meta_file = folder / "_meta.txt"
        if meta_file.exists():
            meta.update(_parse_meta_file(meta_file))
    return meta


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


def derive_file_metadata(path: Path) -> dict:
    """How a file's name + folder + _meta.txt map to metadata — the single
    source of truth, used both at ingest and when a file is renamed/moved.
    The three descriptive fields (author, year, doc_type) may be overridden by
    _meta.txt; everything else becomes a custom, filterable field."""
    stem = config.normalize_source_key(path.stem)
    source_file = config.source_key_from_path(path)
    author, year = parse_filename(stem)
    doc_type = doc_type_from_path(path)
    custom_meta = load_folder_meta(path)
    author = custom_meta.pop("author", author)
    year = custom_meta.pop("year", year)
    doc_type = custom_meta.pop("doc_type", doc_type)
    try:
        rel_path = str(path.relative_to(config.VAULT))
    except ValueError:
        rel_path = path.name
    return {
        "source_file": source_file, "author": author, "year": year,
        "doc_type": doc_type, "rel_path": rel_path, "custom_meta": custom_meta,
    }


def metadata_payload(path: Path) -> dict:
    """Just the filename-derived payload fields, ready for a Qdrant set_payload —
    no content fields, so an indexed source can be re-keyed after a rename/move
    WITHOUT re-embedding."""
    m = derive_file_metadata(path)
    payload = {
        "source_file": m["source_file"], "rel_path": m["rel_path"],
        "author": m["author"], "year": m["year"],
        "year_num": int(m["year"]) if m["year"].isdigit() else 0,
        "doc_type": m["doc_type"],
    }
    payload.update({k: v for k, v in m["custom_meta"].items()
                    if k not in RESERVED_KEYS and k not in OVERRIDABLE_KEYS})
    return payload


def detect_language(sample: str) -> str:
    sample = sample[:4000].lower()
    de = sum(sample.count(t) for t in ("der ", "die ", "und ", "ist ", "mit ", "für "))
    en = sum(sample.count(t) for t in ("the ", "and ", " of ", " in ", " to ", "with "))
    if max(de, en) < 5:
        return "mixed"
    return "de" if de >= en else "en"


def _picture_image_b64(item, doc) -> str:
    """Return a figure's rendered image as a base64 PNG string, or "" if the
    image is unavailable. Never raises — a missing image just means no vision
    description for that figure (it still gets caption-only context)."""
    import base64
    import io

    try:
        pil_image = item.get_image(doc)
        if pil_image is None:
            return ""
        if pil_image.mode not in ("RGB", "L"):
            pil_image = pil_image.convert("RGB")
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def extract(path: Path) -> tuple[list[Chunk], str]:
    """Run Docling and build chunks. Returns (chunks, full_markdown)."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import (
        PictureItem, SectionHeaderItem, TableItem, TextItem,
    )

    _m = derive_file_metadata(path)
    source_file, rel_path = _m["source_file"], _m["rel_path"]
    author, year, doc_type = _m["author"], _m["year"], _m["doc_type"]
    custom_meta = _m["custom_meta"]

    # Pin table mode explicitly so a future Docling default change cannot
    # silently degrade table quality.
    opts = PdfPipelineOptions()
    opts.do_table_structure = True
    opts.table_structure_options.mode = TableFormerMode.ACCURATE
    opts.table_structure_options.do_cell_matching = True
    # Render figure images only when the vision pass needs them — keeps
    # extraction fast and memory-light when vision is disabled.
    if config.VISION_ENABLED:
        opts.generate_picture_images = True
        opts.images_scale = config.VISION_IMAGE_SCALE
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
    buffer: list[tuple[str, int]] = []   # (paragraph text, source page)

    def meta(**kw) -> dict:
        base = dict(
            source_file=source_file, rel_path=rel_path, chapter=chapter,
            section=section, doc_type=doc_type, author=author,
            year=year, language=language, custom_meta=custom_meta,
        )
        base.update(kw)
        return base

    def flush():
        nonlocal buffer
        if not buffer:
            return
        paras = buffer
        buffer = []
        if sum(len(t) for t, _ in paras) < config.MIN_CHUNK_CHARS:
            return
        prefix = f"[Chapter: {chapter}]" if chapter else ""
        if section:
            prefix += f" [Section: {section}]"
        if prefix:
            prefix += "\n"
        for sub, page_start, page_end in split_text_paged(
            paras, config.MAX_CHUNK_CHARS, config.OVERLAP_CHARS
        ):
            chunks.append(Chunk(
                text=prefix + sub, chunk_type="text",
                page_start=page_start, page_end=page_end, **meta(),
            ))

    for item, level in doc.iterate_items():
        page = item.prov[0].page_no if getattr(item, "prov", None) else 1

        if isinstance(item, SectionHeaderItem):
            flush()
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

        elif isinstance(item, PictureItem):
            flush()
            caption = ""
            try:
                caption = (item.caption_text(doc) or "").strip()
            except Exception:
                pass
            header = f"[Chapter: {chapter}] [Section: {section}]\n" if chapter else ""
            display = caption or "No caption available"
            image_b64 = _picture_image_b64(item, doc) if config.VISION_ENABLED else ""
            chunks.append(Chunk(
                text=f"{header}**Figure (p. {page}):** {display}",
                chunk_type="figure", page_start=page, page_end=page,
                image_b64=image_b64, **meta(),
            ))

        elif isinstance(item, TextItem):
            txt = (item.text or "").strip()
            if txt:
                buffer.append((txt, page))

    flush()
    # Return the FULL markdown (bounded only against a pathological export) — it
    # feeds the table-of-contents and chapter/section matching in contextualize,
    # which must see the WHOLE document. The grounding fallback is capped
    # separately (CONTEXT_DOC_CHARS) inside _doc_context.
    return chunks, full_markdown[: config.MARKDOWN_FULL_MAX_CHARS]
