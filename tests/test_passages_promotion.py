"""Tests fuer passages_promotion — die Kapitel-basierte Beleg-Ablage, die der
stdio-MCP bei ``BRAG_PASSAGES_LAYOUT=promotion`` fuer save_passage/list_passages
nutzt. Deckt: Kapitel-Dateiname aus der Gliederungsdatei, Kontinuitaetsregel
(vorhandene KapN_*.md gewinnt), Seiten-Formatierung, den Litnote-Nachtrag — und
dass die drei Ablageorte aus der Umgebung kommen statt aus dem Code."""
import importlib
from pathlib import Path

import pytest

BELEGE = "Wiki/Belege"
NOTIZEN = "Wiki/Notizen"
GLIEDERUNG = "Wiki/Gliederung.md"


@pytest.fixture
def pp(tmp_path, monkeypatch):
    from brag import config
    (tmp_path / BELEGE).mkdir(parents=True)
    (tmp_path / NOTIZEN).mkdir(parents=True)
    (tmp_path / GLIEDERUNG).write_text(
        "# Kapitel 2 — Grundlagen\n\nInhalt\n", encoding="utf-8")
    # PASSAGES_ROOT/OUTLINE_FILE/LITNOTES_DIR sind einfache Modulwerte (NICHT in
    # _SCOPED_ATTRS), setattr darauf ist unkritisch und wird zurueckgerollt.
    monkeypatch.setattr(config, "PASSAGES_ROOT", BELEGE)
    monkeypatch.setattr(config, "OUTLINE_FILE", GLIEDERUNG)
    monkeypatch.setattr(config, "LITNOTES_DIR", NOTIZEN)
    # config.VAULT is served by the module __getattr__ (_SCOPED_ATTRS). Patching it
    # with monkeypatch.setattr would plant a REAL attribute that shadows __getattr__
    # for the rest of the session and knocks later tests off their files. The
    # supported way to point the vault somewhere else is project_context(), which
    # sets a ContextVar and resets it on exit.
    with config.project_context({"vault": str(tmp_path)}):
        import brag.passages_promotion as module
        importlib.reload(module)   # sauberer Modulzustand pro Test
        yield tmp_path, module


def test_save_passage_creates_chapter_file(pp):
    tmp, mod = pp
    out = mod.save_passage(source="Mueller_2020_X", text="Eine belegte Aussage.",
                           chapter="2", author="Müller", year="2020", page_start="5")
    f = tmp / BELEGE / "Kap2_Grundlagen.md"
    assert f.exists(), "Kapitel-Datei aus der Gliederung wurde nicht angelegt"
    body = f.read_text(encoding="utf-8")
    assert "Müller" in body and "S. 5" in body and "Eine belegte Aussage." in body
    assert "Kap2_Grundlagen" in out


def test_page_range_formatting(pp):
    tmp, mod = pp
    mod.save_passage(source="A_2020", text="t", chapter="2", page_start="10", page_end="14")
    body = (tmp / BELEGE / "Kap2_Grundlagen.md").read_text("utf-8")
    assert "S. 10–14" in body


def test_list_passages(pp):
    tmp, mod = pp
    mod.save_passage(source="A_2020", text="t", chapter="2", page_start="1")
    listing = mod.list_passages()
    assert "Kap2_Grundlagen" in listing and "Beleg" in listing


def test_continuity_existing_filename_wins(pp):
    tmp, mod = pp
    pre = tmp / BELEGE / "Kap2_AltName.md"
    pre.write_text("# Passagen — Kapitel 2\n\n---\n\n", encoding="utf-8")
    mod.save_passage(source="A_2020", text="t", chapter="2", page_start="1")
    assert pre.read_text("utf-8").count("## (") == 1, "Beleg landete nicht in vorhandener Datei"
    assert not (tmp / BELEGE / "Kap2_Grundlagen.md").exists()


def test_litnote_append_and_dedup(pp):
    tmp, mod = pp
    lit = tmp / NOTIZEN / "A_2020.md"
    lit.write_text("# A_2020\n\nSteckbrief.\n", encoding="utf-8")
    for _ in range(2):   # zweimal derselbe Beleg — der Nachtrag muss deduplizieren
        mod.save_passage(source="A_2020", text="Aussage.", chapter="2",
                         page_start="7", note="Kernbeleg")
    body = lit.read_text("utf-8")
    assert "Belegt in der Dissertation" in body and "Kernbeleg" in body
    assert body.count("Kernbeleg") == 1, "Litnote-Nachtrag wurde nicht dedupliziert"


def test_unconfigured_install_falls_back_to_the_generic_layout(tmp_path, monkeypatch):
    """Ohne die drei Umgebungswerte darf NICHTS aus einer fremden Ablage geerbt
    werden: die Kapiteldateien landen in der generischen Belegablage, es gibt kein
    Kapitel-Namensmapping (der `chapter`-Wert ist der Dateiname), und der
    Litnote-Nachtrag bleibt still, weil dort keine Notiz liegt."""
    from brag import config
    monkeypatch.setattr(config, "PASSAGES_ROOT", "")
    monkeypatch.setattr(config, "OUTLINE_FILE", "")
    monkeypatch.setattr(config, "LITNOTES_DIR", "")
    with config.project_context({"vault": str(tmp_path)}):
        import brag.passages_promotion as module
        importlib.reload(module)
        assert module._passages_dir() == Path(config.PASSAGES_DIR)
        assert module._gliederung() is None
        out = module.save_passage(source="A_2020", text="t", chapter="Einleitung")
        ziel = Path(config.PASSAGES_DIR) / "Einleitung.md"
        assert ziel.exists() and "Einleitung" in out
