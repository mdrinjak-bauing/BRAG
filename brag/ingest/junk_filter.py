"""Junk-figure detection: keep logos, UI icons and license seals out of the index.

Finding from the sister pipeline's sample audit (2026-05-15): 40% of the figure
chunks in a real academic corpus were UI elements (thumbs-up, "check for
updates" badges), university/publisher logos and Creative-Commons license
seals — zero semantic value for retrieval, but they dilute figure search and
(since the research package) would even be attached as images to answers.

Conservative strategy (high precision, verified on audit samples — all chunks
it flagged were junk):
- STRONG patterns mark a figure as junk even when it has a real caption
  (a QR code stays a QR code, captioned or not).
- WEAK patterns (logos, icons) only apply when the figure has NO caption —
  a captioned "Fig. 1.2: university campus" survives even if the description
  mentions a logo.
- A tiny image (both sides < 100 px or area < 15 000 px²) is junk only
  WITHOUT a caption — stricter than the sister pipeline, which sized-filtered
  regardless of caption.

Patterns cover German AND English: the vision description follows
ANSWER_LANGUAGE, captions follow the document language.
"""

import re

# Junk even WITH a caption.
STRONG_JUNK_PATTERNS = [
    (r"\b(QR.{0,3}Code|Barcode|Strichcode|Strich.{0,2}Code)\b", "QR/barcode"),
    (r"(Creative Commons|CC.{0,5}(Lizenz|license)|Lizenzsiegel|Lizenzlogo|"
     r"license (seal|badge|logo))", "license seal"),
    (r"(Copyright.{0,5}(Symbol|Zeichen|symbol|sign)|©.{0,5}(Symbol|Zeichen|symbol))",
     "copyright symbol"),
]

# Junk only WITHOUT a caption.
WEAK_JUNK_PATTERNS = [
    (r"\b(Daumen[.\s-]?hoch|Daumen[.\s-]?Symbol|thumbs?[.\s-]?up)\b", "thumbs-up icon"),
    (r"(Check for [Uu]pdates|Update[.\s-]?(Symbol|Indikator|icon|badge)|"
     r"Aktualisierungs[.\s-]?Symbol)", "update badge"),
    (r"((ein|das|a|the)\s+Logo\b|\bLogo\s+(der|des|von|of)\b|"
     r"(Universitäts|Verlags|Firmen|Schul|Hochschul|university|publisher|"
     r"company).{0,5}logo)", "logo"),
]

# extract.py writes this display text when Docling found no caption.
NO_CAPTION_MARKER = "No caption available"

# Icons and UI elements are typically tiny.
MIN_SIDE_PX = 100
MIN_AREA_PX = 15_000


def _tiny_image(image_b64: str) -> str:
    """Return a reason string if the rendered figure is icon-sized, else ""."""
    if not image_b64:
        return ""
    try:
        import base64
        import io

        from PIL import Image
        with Image.open(io.BytesIO(base64.b64decode(image_b64))) as im:
            w, h = im.size
    except Exception:  # noqa: BLE001 — unknown size is never junk (conservative)
        return ""
    if w < MIN_SIDE_PX and h < MIN_SIDE_PX:
        return f"tiny ({w}×{h} px)"
    if w * h < MIN_AREA_PX:
        return f"tiny area ({w}×{h} px)"
    return ""


def is_junk_figure(chunk) -> tuple[bool, str]:
    """Classify a figure chunk after contextualization.

    Uses the vision description (chunk.context — may be empty when the vision
    pass is off/failed), the caption embedded in chunk.text, and the rendered
    image's pixel size. Returns (is_junk, reason). Non-figure chunks are never
    junk."""
    if chunk.chunk_type != "figure":
        return False, ""
    has_caption = NO_CAPTION_MARKER not in (chunk.text or "")
    haystack = f"{chunk.context or ''}\n{chunk.text or ''}"

    for pattern, label in STRONG_JUNK_PATTERNS:
        if re.search(pattern, haystack, re.IGNORECASE):
            return True, label
    if not has_caption:
        for pattern, label in WEAK_JUNK_PATTERNS:
            if re.search(pattern, haystack, re.IGNORECASE):
                return True, label
        size_reason = _tiny_image(chunk.image_b64)
        if size_reason:
            return True, size_reason
    return False, ""


def drop_junk_figures(chunks: list) -> tuple[list, int]:
    """Filter junk figures out of a chunk list. Returns (kept, n_dropped);
    prints one line per dropped figure so the ingest log shows what was cut."""
    kept, dropped = [], 0
    for c in chunks:
        junk, reason = is_junk_figure(c)
        if junk:
            dropped += 1
            print(f"  junk figure dropped (p. {c.page_start}): {reason}")
        else:
            kept.append(c)
    return kept, dropped
