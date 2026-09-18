"""A filename must never become AppleScript source.

upstream builds the script by interpolation:
    f'set theDoc to (open POSIX file "{pdf_posix}")'
A file named  a" & (do shell script "…") & "b.pdf  closes the string and appends an
expression that runs before `open` is ever reached. Both `"` and newline are legal in
APFS filenames, and _resolve_path's unique-substring fallback means the user never types it.
"""
import ast

import pytest
from pathlib import Path

QUELLE = Path(__file__).resolve().parent.parent / "brag" / "pdf_open.py"


def test_the_path_is_not_interpolated_into_the_script():
    baum = ast.parse(QUELLE.read_text(encoding="utf-8"))
    schuldig = []
    for k in ast.walk(baum):
        if not isinstance(k, ast.JoinedStr):          # ein f-String
            continue
        roh = ast.dump(k)
        if "posix" in roh.lower() and "open POSIX file" in ast.unparse(k):
            schuldig.append(ast.unparse(k)[:80])
    assert not schuldig, f"path interpolated into AppleScript: {schuldig}"


def test_the_path_is_passed_as_an_argument():
    quelle = QUELLE.read_text(encoding="utf-8")
    assert "on run argv" in quelle, "the script does not take arguments"
    assert "item 1 of argv" in quelle, "the script does not read the path from argv"


# ── Gedruckte Seite -> physische Seite ────────────────────────────────────────
# Ohne /PageLabels galt "gedruckt = physisch". Bei jedem Buch mit Vorspann
# (Titelei, Impressum, roemisch paginiertes Vorwort) ist das konstant falsch —
# gemessen "mal 2, mal 18 Seiten daneben". Falsche Druckseiten waren die
# haeufigste Fehlerquelle im Manuskript-Audit, und der Sprung landet auf einer
# plausibel aussehenden Seite: es faellt nicht auf.

def _pdf_mit_vorspann(ziel, vorspann=3, gedruckte=8):
    """PDF ohne /PageLabels: `vorspann` Seiten Titelei, danach gedruckte Seiten
    1..n mit der Nummer in der Fusszeile. Gedruckte Seite N liegt physisch auf
    N + vorspann."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.set_auto_page_break(False)      # die Fusszeile muss AUF ihrer Seite bleiben
    pdf.set_font("Helvetica", size=14)
    for titel in ("Titelblatt", "Impressum", "Vorwort")[:vorspann]:
        pdf.add_page()
        pdf.cell(0, 10, titel)          # bewusst ohne jede Ziffer
    for gedruckt in range(1, gedruckte + 1):
        pdf.add_page()
        pdf.cell(0, 10, "Kapiteltext ohne Zahlen im Fliesstext")
        pdf.set_y(-20)
        pdf.cell(0, 10, str(gedruckt), align="C")
    pdf.output(str(ziel))
    return ziel


def test_printed_page_is_found_behind_the_front_matter(tmp_path):
    pytest.importorskip("fpdf")
    pytest.importorskip("pypdfium2")
    from brag import pdf_open
    buch = _pdf_mit_vorspann(tmp_path / "buch.pdf")

    # Genau das, was die naive Annahme "gedruckt = physisch" liefern wuerde:
    assert pdf_open._resolve_book_page(buch, 1) == 4     # nicht 1
    assert pdf_open._resolve_book_page(buch, 2) == 5     # nicht 2
    assert pdf_open._resolve_book_page(buch, 5) == 8     # nicht 5


def test_the_naive_fallback_survives_when_the_scan_finds_nothing(tmp_path, monkeypatch):
    """Der Scan ist ein Zwischenschritt, kein Ersatz: sind die Seitenzahlen als
    Grafik gesetzt, findet er nichts — dann muss der alte Notnagel greifen."""
    pytest.importorskip("fpdf")
    pytest.importorskip("pypdfium2")
    from brag import pdf_open
    buch = _pdf_mit_vorspann(tmp_path / "buch.pdf")
    monkeypatch.setattr(pdf_open, "_scan_printed_number", lambda *a, **k: None)

    assert pdf_open._resolve_book_page(buch, 2) == 2     # Notnagel, wie gehabt
    assert pdf_open._resolve_book_page(buch, 99) is None  # ausserhalb -> keine Erfindung


def test_a_bare_number_in_the_body_text_is_not_mistaken_for_a_page_number():
    """Nur Kopf- und Fussbereich zaehlen (je 200 Zeichen). Sonst wuerde die erste
    Seite, die irgendwo '7' erwaehnt, als gedruckte Seite 7 durchgehen."""
    from brag import pdf_open

    class _Seite:
        def __init__(self, text):
            self._text = text

        def get_textpage(self):
            return self

        def get_text_range(self):
            return self._text

        def close(self):
            pass

    class _Doc:
        def __init__(self, seiten):
            self._s = [_Seite(t) for t in seiten]

        def __len__(self):
            return len(self._s)

        def __getitem__(self, i):
            return self._s[i]

    fuell = "Fliesstext ohne jede Seitenzahl. " * 12          # > 400 Zeichen
    mitte = fuell + "im Jahr 7 der Reihe " + fuell            # die 7 steckt in der MITTE
    rand = "Kapitel" + " " * 5 + "\n7"                        # die 7 steht am RAND
    assert pdf_open._scan_printed_number(_Doc([mitte] * 7 + [rand]), 7) == 8
