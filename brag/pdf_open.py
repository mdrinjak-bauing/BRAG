"""Native macOS PDF opening (Skim) at a precise page.

Skim is the only macOS reader with a reliable AppleScript page-navigation API;
`file://...#page=N` is silently ignored by Preview/Safari/Chrome/Acrobat on many
PDFs. This drives the Skim app on the user's Mac, so it lives OUTSIDE tools.py
(which is shared with the container HTTP-bridge, where no GUI exists).

The printed-page -> physical-page translation reads the PDF's /PageLabels via
pypdfium2 (imported lazily; falls back to treating the label as a physical page
number when the library or the labels are absent — exactly the local behaviour).
"""

from __future__ import annotations

from pathlib import Path

from brag import config

# {normalized stem -> absolute path}. Built lazily on first use and rebuilt when a
# requested stem is missing (a PDF may have been added since the first build).
_PDF_INDEX: dict[str, Path] | None = None


def _build_pdf_index() -> dict[str, Path]:
    idx: dict[str, Path] = {}
    try:
        for p in Path(config.SOURCES_DIR).rglob("*.pdf"):
            if config.is_corpus_path(p):
                idx[config.normalize_source_key(p.stem)] = p.resolve()
    except Exception:  # noqa: BLE001 — a missing/locked dir must not crash the tool
        pass
    return idx


def _resolve_path(source_file: str):
    """Resolve a source_file stem to an absolute PDF path. Returns (path, None) or
    (None, error_message). Exact NFC match first, then a one-time index rebuild,
    then a unique case-insensitive substring fallback."""
    global _PDF_INDEX
    if _PDF_INDEX is None:
        _PDF_INDEX = _build_pdf_index()
    key = config.normalize_source_key(source_file)
    path = _PDF_INDEX.get(key)
    if not path:
        _PDF_INDEX = _build_pdf_index()  # may have been ingested since first build
        path = _PDF_INDEX.get(key)
    if path:
        return path, None
    cands = [k for k in _PDF_INDEX if source_file.lower() in k.lower()]
    if len(cands) == 1:
        return _PDF_INDEX[cands[0]], None
    if len(cands) > 1:
        return None, (f"Mehrdeutig — passt auf {len(cands)} PDFs: "
                      f"{', '.join(cands[:5])}")
    return None, (f"PDF '{source_file}' nicht im Korpus gefunden. "
                  f"Tipp: list_sources() zeigt alle verfügbaren Dateinamen.")


def _resolve_book_page(pdf_path: Path, book_page) -> int | None:
    """Translate a printed book page into a physical PDF page (1-based) via
    /PageLabels. Falls back to treating a numeric label as the physical page when
    pypdfium2 is unavailable or no label matches. None if nothing matches."""
    try:
        import ctypes

        import pypdfium2 as pdfium
        import pypdfium2.raw as pdfium_c
    except Exception:  # noqa: BLE001 — no pypdfium2 -> numeric fallback only
        return int(book_page) if str(book_page).isdigit() else None

    target = str(book_page).strip()
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        for i in range(len(pdf)):
            needed = pdfium_c.FPDF_GetPageLabel(pdf.raw, i, None, 0)
            if needed <= 2:
                continue
            buf = ctypes.create_string_buffer(needed)
            pdfium_c.FPDF_GetPageLabel(pdf.raw, i, buf, needed)
            label = buf.raw[:needed - 2].decode("utf-16le", errors="ignore")
            if label == target:
                return i + 1
        if str(book_page).isdigit():
            n = int(book_page)
            if 1 <= n <= len(pdf):
                return n
        return None
    finally:
        pdf.close()


def open_pdf(source_file: str, pdf_page: int | None = None,
             book_page: int | str | None = None, page: int | None = None) -> str:
    """Open a corpus PDF in Skim at a given page (deterministic via AppleScript).
    Page priority: pdf_page (physical, preferred) > page (legacy alias) >
    book_page (printed page, translated via /PageLabels). Empty -> page 1."""
    pdf_path, err = _resolve_path(source_file)
    if err:
        return err

    target_page = pdf_page if pdf_page is not None else page
    label_for_msg = str(target_page) if target_page else None
    if target_page is None and book_page is not None:
        target_page = _resolve_book_page(pdf_path, book_page)
        label_for_msg = str(book_page)
        if target_page is None:
            return (f"Buchseite '{book_page}' konnte in {pdf_path.name} nicht gefunden "
                    f"werden. Tipp: pdf_page= mit der physischen Seite übergeben.")
    if target_page is None:
        target_page = 1
        label_for_msg = "1"

    import subprocess

    pdf_posix = str(pdf_path)
    # Poll until Skim has loaded the document (open is async) — otherwise
    # `go to page` lands on an empty doc and silently fails.
    applescript = (
        'tell application "Skim"\n'
        '    activate\n'
        f'    set theDoc to (open POSIX file "{pdf_posix}")\n'
        '    set maxWait to 50\n'
        '    set waited to 0\n'
        '    repeat while (count of pages of theDoc) is 0 and waited < maxWait\n'
        '        delay 0.1\n'
        '        set waited to waited + 1\n'
        '    end repeat\n'
        f'    tell theDoc to go to page {target_page}\n'
        'end tell\n'
    )
    try:
        res = subprocess.run(
            ["osascript", "-e", applescript],
            check=False, timeout=15, capture_output=True, text=True,
        )
        if res.returncode != 0:
            from urllib.parse import quote
            url = f"file://{quote(pdf_posix, safe='/')}#page={target_page}"
            subprocess.run(["open", url], check=True, timeout=5)
            return (f"⚠ {pdf_path.name} via Standard-App geöffnet, Skim-Navigation "
                    f"gescheitert (Anchor wird ggf. ignoriert). "
                    f"osascript: {(res.stderr or '')[:200]}")
        if label_for_msg != str(target_page):
            return (f"✓ {pdf_path.name} an Buchseite {label_for_msg} "
                    f"(= PDF-Seite {target_page}) in Skim geöffnet.")
        return f"✓ {pdf_path.name} an S. {target_page} in Skim geöffnet."
    except subprocess.TimeoutExpired:
        return f"Timeout beim Öffnen von {pdf_path.name} — vermutlich trotzdem geöffnet."
    except Exception as e:  # noqa: BLE001
        return f"Fehler beim Öffnen von {pdf_path.name}: {e}"
