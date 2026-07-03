"""Figure images: compact storage at ingest, attachment to search results.

At ingest, a figure's Docling-rendered image (chunk.image_b64, produced for the
vision pass) is re-encoded to a compact JPEG and stored under
`WissensWIKI/.brag/figures/<chunk_id>.jpg`; the chunk payload then carries the
relative `image_file` key. At search time, up to MAX_SEARCH_IMAGES of the hits'
stored figures are returned as MCP ImageContent items so the chat model SEES
the actual figure (query-time visual Q&A), not just its ingest-time description.

Why compact JPEG (hard-won on the sister pipeline, 2026-05-17): extracted
figure PNGs run 0.4–1.7 MB. Base64-encoded (×1.37), a single such image blows
the ~1 MB limit Claude Desktop accepts per tool response — and then ALL images
of the response are silently dropped. Downscaling + a JPEG quality ladder keeps
3 images comfortably under the limit (~110–200 KB each).

Pillow is imported lazily; every function degrades gracefully (no image is
always better than a broken ingest or an unrenderable tool response).
"""

from __future__ import annotations

import base64

from brag import config

FIGURES_DIRNAME = "figures"      # under config.DATA_DIR (WissensWIKI/.brag/)
MAX_SEARCH_IMAGES = 3            # ImageContent items per search response
_IMG_MAX_DIM = 1300              # longest edge in px after downscale
_IMG_TARGET_BYTES = 150 * 1024   # JPEG target size — the quality ladder stops here


def encode_compact(data: bytes) -> bytes | None:
    """Re-encode raw image bytes to a compact JPEG (downscale + quality ladder).

    Flattens transparency onto white (JPEG has no alpha), scales the longest
    edge to _IMG_MAX_DIM px and walks quality 85→45 until the result is at or
    under _IMG_TARGET_BYTES. Returns None on any Pillow failure — the caller
    treats that as "no image" rather than risking an oversized payload."""
    try:
        import io

        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            if im.mode in ("RGBA", "LA", "P"):
                rgba = im.convert("RGBA")
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.split()[-1])
                im = bg
            else:
                im = im.convert("RGB")
            if max(im.size) > _IMG_MAX_DIM:
                ratio = _IMG_MAX_DIM / max(im.size)
                im = im.resize(
                    (max(1, round(im.size[0] * ratio)),
                     max(1, round(im.size[1] * ratio))),
                    Image.LANCZOS,
                )
            buf = io.BytesIO()
            for quality in (85, 75, 65, 55, 45):
                buf.seek(0)
                buf.truncate(0)
                im.save(buf, format="JPEG", quality=quality, optimize=True)
                if buf.tell() <= _IMG_TARGET_BYTES:
                    break
        return buf.getvalue()
    except Exception:  # noqa: BLE001 — a bad image must never break its caller
        return None


def save_figure_image(chunk) -> str:
    """Store a figure chunk's rendered image as a compact JPEG.

    Writes DATA_DIR/figures/<chunk_id>.jpg and returns the DATA_DIR-relative
    path for the chunk payload ("figures/<chunk_id>.jpg"), or "" if the image
    could not be decoded/encoded. Deterministic filename = idempotent re-ingest
    (the same chunk overwrites its own image in place). Never raises."""
    try:
        raw = base64.b64decode(chunk.image_b64)
    except Exception:  # noqa: BLE001
        return ""
    compact = encode_compact(raw)
    if compact is None:
        return ""
    try:
        fig_dir = config.DATA_DIR / FIGURES_DIRNAME
        fig_dir.mkdir(parents=True, exist_ok=True)
        rel = f"{FIGURES_DIRNAME}/{chunk.chunk_id}.jpg"
        (config.DATA_DIR / rel).write_bytes(compact)
        return rel
    except OSError:
        return ""


def collect_hit_images(hits: list[dict], max_images: int = MAX_SEARCH_IMAGES,
                       ) -> tuple[list[dict], set[str]]:
    """Gather up to `max_images` stored figure images referenced by search hits.

    Returns (images, attached_chunk_ids): `images` as
    [{"b64": <base64 JPEG>, "mime": "image/jpeg"}, …] in hit order, deduplicated
    by image file; `attached_chunk_ids` so the text formatter can mark which
    hits have their figure attached. Hits without a stored image (older index,
    text/table chunks, deleted file) are simply skipped — search stays fully
    functional without images. Must run inside the right project context
    (config.project_context) so DATA_DIR resolves to the hit's project."""
    images: list[dict] = []
    attached: set[str] = set()
    seen_files: set[str] = set()
    for h in hits:
        if len(images) >= max_images:
            break
        rel = str(h.get("image_file", "") or "")
        if not rel or rel in seen_files:
            continue
        target = (config.DATA_DIR / rel).resolve()
        try:
            target.relative_to(config.DATA_DIR.resolve())  # path-traversal guard
            data = target.read_bytes()
        except (OSError, ValueError):
            continue
        seen_files.add(rel)
        images.append({"b64": base64.standard_b64encode(data).decode("ascii"),
                       "mime": "image/jpeg"})
        attached.add(str(h.get("chunk_id", "")))
    return images, attached
