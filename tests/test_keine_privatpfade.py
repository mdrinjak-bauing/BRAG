"""No private paths, names or taxonomies in code defaults or tool descriptions.

Tool docstrings ship to every user's model, and config defaults are inherited by
every install. Both must be generic; personal values belong in the environment.

Der Waechter hat zwei Haelften, und das hat einen Grund:

1. GENERISCHE Hygiene-Muster (`GENERISCH`) — immer aktiv, fuer jede Installation
   sinnvoll: absolute Heimatpfade, E-Mail-Adressen, Ordner-Token der Form `NN_Name`.
2. PERSOENLICHE Begriffe aus der Umgebungsvariablen `BRAG_FORBIDDEN_STRINGS`
   (kommagetrennt, Vorgabe leer).

Warum die persoenliche Liste NICHT in dieser Datei steht: sie waere sonst genau
das, was sie verhindern soll. Eine Sperrliste ist die Aufzaehlung dessen, was
geheim bleiben soll — Nachname, Benutzername, Hochschule, der vollstaendige private
Ordnerbaum, im Klartext, in einem oeffentlichen Repository. Der Waechter
veroeffentlichte damit, was er schuetzt.

Wer dieses Projekt uebernimmt, setzt seine eigenen Begriffe in die Umgebung — im
Startskript neben den uebrigen BRAG_*-Werten — und fasst diese Datei nicht an.
Ohne gesetzten Wert laeuft die generische Haelfte weiter: der Test ist dann kein
leeres Gehaeuse, er prueft nur weniger.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
# Der Waechter deckt ALLES ab, was mit veroeffentlicht wird und Text traegt —
# nicht nur das Paket. Ein Test-Fixture und ein Installationsskript liegen genauso
# oeffentlich wie der Code, und `brag/setup_page.html` ist zwar im Paket, aber
# keine .py-Datei. Genau dort sass die erste Fundstelle ausserhalb von brag/:
# ein Taxonomie-Wert als Nutzlast in tests/test_rename_payload.py.
# NICHT erfasst ist die Wurzel mit LICENSE und pyproject.toml — dort steht der
# Name des Urhebers, und der GEHOERT dorthin.
WURZELN = ("brag", "tests", "tools")
SUFFIXE = {".py", ".html", ".ps1", ".bat", ".command"}

# Immer aktiv. Die Ausschluesse sind gemessen, nicht geraten:
#   * `(?<![0-9A-Za-z:_])` vor dem Heimatpfad laesst `C:/Users/me/Docs` durch —
#     eine Windows-Pfadpruefung in tests/test_registry.py, kein fremdes Zuhause.
#   * `(?<![0-9A-Za-z_])` vor dem Ordner-Token laesst `scan_04_final` und
#     `..._for_a_50_hit_review` durch: ein Unterstrich davor heisst Wortteil,
#     ein Anfuehrungszeichen oder Schraegstrich heisst Pfadsegment.
GENERISCH = {
    "Heimatpfad": re.compile(r"(?<![0-9A-Za-z:_])/(?:Users|home)/[A-Za-z0-9._-]+"),
    "E-Mail": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "Nummern-Ordner": re.compile(r"(?<![0-9A-Za-z_])\d{2}_[A-Za-zÄÖÜäöüß][\w-]*"),
}


def _persoenliche_begriffe() -> list[str]:
    return [s.strip() for s in os.environ.get("BRAG_FORBIDDEN_STRINGS", "").split(",")
            if s.strip()]


def _wortmuster(begriff: str) -> re.Pattern:
    """Wortgrenze statt Teilzeichenkette — sonst wird ein Fachbegriff fuer einen
    Namen gehalten. `brag/search/expand.py` fuehrt `Markov logic networks`; dessen
    erste fuenf Zeichen sind auch der Anfang eines Vornamens, und ein
    Teilzeichenketten-Test erzwingt daraufhin die Umbenennung eines Fachworts.

    Grenze ist „kein Buchstabe, keine Ziffer" (`_` und `-` trennen also, damit
    Datei- und Pfadnamen sicher greifen). Ein angehaengtes Genitiv-/Plural-`s`
    gehoert noch zum Wort, jeder andere Buchstabe macht ein anderes Wort daraus."""
    return re.compile(rf"(?<![0-9A-Za-z]){re.escape(begriff)}s?(?![0-9A-Za-z])")


def _dateien():
    for wurzel in WURZELN:
        for p in sorted((WURZEL / wurzel).rglob("*")):
            if p.suffix in SUFFIXE and "__pycache__" not in p.parts:
                yield p


def _scan(begriffe) -> list[str]:
    muster = [(b, _wortmuster(b)) for b in begriffe] + list(GENERISCH.items())
    treffer = []
    for p in _dateien():
        text = p.read_text(encoding="utf-8", errors="replace")
        for nr, zeile in enumerate(text.splitlines(), 1):
            for name, m in muster:
                if m.search(zeile):
                    treffer.append(
                        f"{p.relative_to(WURZEL)}:{nr}: [{name}] {zeile.strip()[:70]}")
    return treffer


def test_no_private_strings_in_the_public_tree():
    treffer = _scan(_persoenliche_begriffe())
    assert not treffer, "private values in code:\n" + "\n".join(treffer)


def test_the_environment_supplied_list_is_really_checked():
    """Sonst waere die zweite Haelfte ein toter Zweig: ohne gesetzte Variable liefe
    nur die generische Pruefung, und niemand merkte, dass die persoenliche gar nicht
    verdrahtet ist. `Qdrant` steht garantiert im Baum und dient hier als Koeder."""
    assert _scan(["Qdrant"]), "BRAG_FORBIDDEN_STRINGS wird nicht ausgewertet"


# Die Vorgabe wird GEZIELT aus dem Aufruf gelesen. Die naheliegende Fassung
#     quelle.split("PASSAGES_LAYOUT")[1][:120]
# kann NICHT durchfallen: der Name steht in derselben Zeile zweimal (einmal als
# Variable, einmal in "BRAG_PASSAGES_LAYOUT"), split() liefert drei Teile, und
# Teil [1] ist das 14 Zeichen kurze Stueck ' = _env("BRAG_' — das Fenster [:120]
# erreicht die Vorgabe nie. Ein solcher Test meldet auch dann gruen, wenn die
# Vorgabe wieder auf "promotion" steht.
_LAYOUT_VORGABE = re.compile(
    r'PASSAGES_LAYOUT\s*=\s*_env\(\s*"BRAG_PASSAGES_LAYOUT"\s*,\s*"([^"]*)"')


def test_passages_layout_does_not_default_to_the_private_one():
    """The switch decides where save_passage writes. Defaulting to the owner's
    chapter layout would silently route a stranger's citations into a file scheme
    that is plain storage, not a search index — and report success while doing it.
    The neutral value is "topic" (chosen in Task 2); the owner's "promotion" comes
    from the environment."""
    quelle = (WURZEL / "brag" / "config.py").read_text(encoding="utf-8")
    m = _LAYOUT_VORGABE.search(quelle)
    assert m, ("PASSAGES_LAYOUT wird nicht mehr als _env(\"BRAG_PASSAGES_LAYOUT\", \"…\") "
               "gesetzt — der Test kann die Vorgabe nicht mehr lesen und darf das nicht "
               "stillschweigend hinnehmen.")
    assert m.group(1) != "promotion", f"private layout is a code default: {m.group(1)!r}"


def test_passages_layout_is_neutral_in_a_clean_environment():
    """Zweite Haelfte: was der Code aus der Vorgabe MACHT.

    Bewusst in einem eigenen Prozess mit von BRAG_*-Werten geleerter Umgebung. Ein
    `if not os.environ.get(...)`-Vorbehalt im laufenden Prozess waere genau dort
    blind, wo es darauf ankommt: die Pruefstrecke aus Aufgabe 11 haengt run.sh an
    und exportiert BRAG_PASSAGES_LAYOUT=promotion — der Vorbehalt schaltete die
    Zusicherung dann ab und der Test meldete gruen, ohne irgendetwas geprueft zu
    haben."""
    umgebung = {k: v for k, v in os.environ.items() if not k.startswith("BRAG_")}
    lauf = subprocess.run(
        [sys.executable, "-c", "from brag import config; print(config.PASSAGES_LAYOUT)"],
        cwd=WURZEL, env=umgebung, capture_output=True, text=True, timeout=120)
    assert lauf.returncode == 0, lauf.stderr[-2000:]
    assert lauf.stdout.strip() == "topic", (
        f"ohne Konfiguration ist das Layout {lauf.stdout.strip()!r} statt 'topic'")
