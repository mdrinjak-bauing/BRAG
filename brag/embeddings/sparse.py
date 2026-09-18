"""BM25 sparse vectors via fastembed, with language-aware Snowball stemming."""

import threading

from brag import config

_model = None
_LOCK = threading.Lock()  # double-checked init across concurrent bridge threads


def get_sparse_model():
    global _model
    if _model is None:
        with _LOCK:
            if _model is None:
                from fastembed import SparseTextEmbedding
                _model = SparseTextEmbedding(
                    model_name="Qdrant/bm25", language=config.VAULT_LANGUAGE
                )
    return _model


def embed_sparse_documents(texts: list[str]):
    """BM25 sparse vectors for a batch of texts. Returns a list ALIGNED to the
    input: one entry per text, in order, None where that text failed — so the
    caller's chunk<->vector pairing stays correct and one bad chunk cannot fail
    the whole document. Mirrors the dense path (local_st.embed_documents): try
    the batch call, and on failure fall back to per-text so the offender is
    isolated instead of aborting the batch."""
    from qdrant_client.models import SparseVector

    if not texts:
        return []

    def _to_vec(e):
        return SparseVector(indices=e.indices.tolist(), values=e.values.tolist())

    try:
        return [_to_vec(e) for e in get_sparse_model().embed(texts)]
    except Exception:  # noqa: BLE001 — isolate failures via the per-text path
        out: list = []
        for t in texts:
            try:
                out.append(_to_vec(next(iter(get_sparse_model().embed([t])))))
            except Exception:  # noqa: BLE001
                out.append(None)
        return out


# ── Konservative Kompositazerlegung (2026-07-21, hier mit Sprachriegel) ────────────
# Absichtlich eigenstaendig: BRAG kennt keine Indexierungspipeline. Falls eine
# externe Pipeline denselben Korpus indexiert, muesste SIE dieselbe Liste +
# Logik auf der Indexseite anwenden, damit der Bonus-Token hier etwas trifft
# (siehe Wirkradius-Hinweis unten) — diese Liste ist stabil, aber nicht an
# einen bestimmten externen Indexer gekoppelt. Zweck: eine Suche
# nach dem LANGEN Kompositum „Nachtragsmanagement" gewinnt zusaetzlich den kurzen
# Stamm „Nachtrag" im BM25-Zweig — NICHT umgekehrt. decompose_compounds("Nachtrag")
# liefert [] (8 Zeichen, unter der 12-Zeichen-Schwelle); der lange Begriff geht
# rein, der kurze Stamm kommt raus.
#
# Ehrlich zum Wirkradius in DIESEM Repo: das greift nur auf der Frageseite.
# embed_sparse_documents() zerlegt nichts — der Bonus-Token „Nachtrag" trifft im
# BM25-Index nur dann etwas, wenn die Indexierungsseite beim Einlesen dieselbe
# Zerlegung vorgenommen hat. Ohne einen kompositabewussten Indexer ist das hier
# Frageseiten-Dekoration ohne Recall-Gewinn.
#
# Riegel (2026-09-17, hier ergaenzt): der alte Stand rief das unbedingt auf, mit 71
# fest verdrahteten deutschen Bau-Staemmen — waehrend BRAG standardmaessig auf
# VAULT_LANGUAGE="english" steht. Gemessen: "Systematically" beginnt mit dem Stamm
# "system" (Rest "atically", 9 Zeichen >= _MIN_REMAINDER) und haengt so still den
# Token "System" an eine englische Anfrage an. Deshalb nur bei
# VAULT_LANGUAGE=="german" aktiv.
_COMPOUND_BASES = frozenset({
    "nachtrag", "mehrkosten", "kosten", "forderung", "anspruch", "vereinbarung",
    "vertrag", "vergabe", "ausschreibung", "angebot", "abrechnung", "zahlung",
    "ablauf", "bauablauf", "störung", "behinderung", "termin", "frist", "verzug",
    "unterbrechung", "beschleunigung", "verzögerung",
    "qualität", "mangel", "mängel", "prüfung", "kontrolle", "überwachung",
    "sicherung", "sicherheit", "abnahme", "gewährleistung",
    "kalkulation", "leistung", "aufwand", "aufwandswert", "produktivität",
    "berechnung", "ermittlung", "erfassung", "kennzahl", "kennwert",
    "management", "steuerung", "planung", "verfahren", "prozess", "modell",
    "system", "methode", "konzept", "dokumentation", "organisation",
    "assistenz", "assistenzsystem", "digitalisierung", "automatisierung",
    "anwendung", "einführung", "akzeptanz", "kompetenz", "schulung",
    "baustelle", "bauausführung", "bauleistung", "bauleitung", "bauwerk",
    "bauprozess", "bauvertrag", "bauzeit", "baubetrieb",
})
_MIN_COMPOUND_LEN = 12
_MIN_REMAINDER = 4
_FUGEN = ("s", "es", "n", "en", "")


def decompose_compounds(text: str) -> list[str]:
    """Bestandteil-Tokens für lange deutsche Bau-Komposita (konservativ). Wirkt nur
    hier auf der Frageseite (siehe Modul-Kommentar); eine externe Indexierungspipeline
    muss dieselbe Zerlegung anwenden, damit die Bonus-Tokens im BM25-Index etwas
    treffen — ohne das ist der Aufruf Frageseiten-Dekoration ohne Recall-Gewinn.

    Gated auf VAULT_LANGUAGE (dieselbe Pruefung wie status_note.py und
    ingest/pipeline.py: .strip().lower().startswith("german"), nicht der
    strengere Vergleich auf exakt "german" — "German", " german", "GERMAN"
    sind dort schon Deutsch und sollen es hier auch sein): die Staemme und
    die Heuristik (Grossschreibung, Mindestlaenge) sind deutsch, ein
    englischer Vault soll davon unberuehrt bleiben (siehe Modul-Kommentar)."""
    if not config.VAULT_LANGUAGE.strip().lower().startswith("german"):
        return []
    import re as _re
    out: list[str] = []
    seen: set[str] = set()
    for w in _re.findall(r"[A-ZÄÖÜ][a-zäöüß]{%d,}" % (_MIN_COMPOUND_LEN - 1), text):
        wl = w.lower()
        for base in _COMPOUND_BASES:
            if wl == base:
                continue
            if wl.endswith(base) and len(wl) - len(base) >= _MIN_REMAINDER:
                cap = base.capitalize()
                if cap not in seen:
                    seen.add(cap); out.append(cap)
            for fug in _FUGEN:
                pre = base + fug
                if wl.startswith(pre) and len(wl) - len(pre) >= _MIN_REMAINDER:
                    cap = base.capitalize()
                    if cap not in seen:
                        seen.add(cap); out.append(cap)
                    break
    return out


def embed_sparse_query(text: str):
    from qdrant_client.models import SparseVector
    extra = decompose_compounds(text)
    q = f"{text} {' '.join(extra)}" if extra else text
    emb = next(get_sparse_model().query_embed(q))
    return SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())
