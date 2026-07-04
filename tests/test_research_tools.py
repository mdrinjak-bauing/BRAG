"""Tests for the research package: figure images (storage + search attachment),
coverage, clusters and compare_positions — all against synthetic hits, no
Qdrant/models needed."""

import base64
import io

import pytest

from brag import config, images, tools
from brag.ingest.extract import Chunk


def _png_bytes(size=(2000, 1400), mode="RGBA") -> bytes:
    PIL = pytest.importorskip("PIL")
    img = PIL.Image.new(mode, size, (200, 30, 30, 128) if mode == "RGBA"
                        else (200, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── images.py ────────────────────────────────────────────────────────────────

def test_encode_compact_downscales_and_bounds_size():
    pytest.importorskip("PIL")
    from PIL import Image
    out = images.encode_compact(_png_bytes())
    assert out is not None
    with Image.open(io.BytesIO(out)) as im:
        assert im.format == "JPEG"
        assert max(im.size) <= 1300          # longest edge downscaled
        assert im.mode == "RGB"              # alpha flattened
    # Quality ladder targets 150 KB; a flat-color test image lands far below.
    assert len(out) <= 150 * 1024


def test_encode_compact_garbage_returns_none():
    assert images.encode_compact(b"not an image") is None


def _figure_chunk(png: bytes) -> Chunk:
    return Chunk(text="**Figure (p. 3):** workflow", chunk_type="figure",
                 source_file="papers/X", rel_path="papers/X.pdf",
                 page_start=3, page_end=3, chapter="", section="",
                 doc_type="paper", author="A", year="2024",
                 image_b64=base64.b64encode(png).decode())


def test_save_figure_image_writes_jpeg_and_payload_key(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    chunk = _figure_chunk(_png_bytes())
    rel = images.save_figure_image(chunk)
    assert rel == f"figures/{chunk.chunk_id}.jpg"
    assert (config.DATA_DIR / rel).is_file()
    chunk.image_file = rel
    assert chunk.payload()["image_file"] == rel
    # A chunk without a stored image carries NO image_file key (payload stays
    # clean for text/table chunks and pre-feature indexes).
    assert "image_file" not in _figure_chunk(_png_bytes()).payload()


def test_save_figure_image_bad_b64_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    chunk = _figure_chunk(b"")
    chunk.image_b64 = "%%%not-base64%%%"
    assert images.save_figure_image(chunk) == ""


def test_collect_hit_images_caps_dedupes_and_skips_missing(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    (config.DATA_DIR / "figures").mkdir(parents=True)
    for name in ("a", "b", "c", "d"):
        (config.DATA_DIR / "figures" / f"{name}.jpg").write_bytes(
            images.encode_compact(_png_bytes(size=(50, 50), mode="RGB")))
    hits = [
        {"chunk_id": "1", "image_file": "figures/a.jpg"},
        {"chunk_id": "2"},                                  # no image → skipped
        {"chunk_id": "3", "image_file": "figures/a.jpg"},   # duplicate file
        {"chunk_id": "4", "image_file": "figures/missing.jpg"},
        {"chunk_id": "5", "image_file": "figures/b.jpg"},
        {"chunk_id": "6", "image_file": "figures/c.jpg"},
        {"chunk_id": "7", "image_file": "figures/d.jpg"},   # over the cap of 3
    ]
    imgs, attached = images.collect_hit_images(hits)
    assert len(imgs) == 3
    assert attached == {"1", "5", "6"}
    assert all(img["mime"] == "image/jpeg" and img["b64"] for img in imgs)


def test_collect_hit_images_blocks_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_DEFAULT_VAULT", tmp_path)
    config.DATA_DIR.mkdir(parents=True)
    (config.DATA_DIR.parent / "secret.jpg").write_bytes(b"outside")
    hits = [{"chunk_id": "1", "image_file": "../secret.jpg"}]
    imgs, attached = images.collect_hit_images(hits)
    assert imgs == [] and attached == set()


def test_format_hits_marks_attached_images(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hits = [{"chunk_id": "abc", "source_file": "p/X", "rel_path": "p/X.pdf",
             "page_start": 3, "text": "t", "chunk_type": "figure"}]
    assert "🖼️" in tools.format_hits(hits, "q", attached_ids={"abc"})
    assert "🖼️" not in tools.format_hits(hits, "q", attached_ids=set())


# ── analytics: coverage / clusters / compare (brag/search/analytics.py) ─────

def _hit(src, score, chapter="", text="lorem", page=1, hid=None):
    return {"source_file": src, "rerank_score": score, "score": score,
            "chapter": chapter, "text": text, "page_start": page,
            "rel_path": f"{src}.pdf", "id": hid or f"{src}-{score}-{page}"}


def test_coverage_broad_needs_count_and_score(monkeypatch):
    from brag.search import analytics
    hits = ([_hit("Big", 0.9)] * 3          # count 3, high score → substantial
            + [_hit("Thin", 0.95)]           # count 1 → peripheral in broad
            + [_hit("Weak", 0.1)] * 4)       # count 4 but low score → peripheral
    monkeypatch.setattr(analytics, "run_search", lambda *a, **k: hits)
    agg = analytics.source_coverage("x", min_score=0.4, mode="broad")
    assert [e[0] for e in agg["substantial"]] == ["Big"]
    assert {e[0] for e in agg["peripheral"]} == {"Thin", "Weak"}
    assert agg["total_sources"] == 3


def test_coverage_specific_promotes_focused_source(monkeypatch):
    # 'specific' drops the count gate and ranks by max_score × spec-factor:
    # the narrow source with ONE excellent hit outranks the broad one.
    from brag.search import analytics
    hits = [_hit("Broad", 0.8)] * 10 + [_hit("Focused", 0.8)]
    monkeypatch.setattr(analytics, "run_search", lambda *a, **k: hits)
    agg = analytics.source_coverage("x", min_score=0.4, mode="specific")
    assert agg["substantial"][0][0] == "Focused"


def test_coverage_both_returns_second_table(monkeypatch):
    from brag.search import analytics
    monkeypatch.setattr(analytics, "run_search",
                        lambda *a, **k: [_hit("A", 0.9)] * 3)
    agg = analytics.source_coverage("x", min_score=0.4, mode="both")
    assert "substantial_specific" in agg


def test_coverage_tool_renders(monkeypatch):
    from brag.search import analytics
    monkeypatch.setattr(analytics, "run_search",
                        lambda *a, **k: [_hit("Big", 0.9, chapter="4 Methodik")] * 3)
    out = tools.coverage("Reifegrad")
    assert "Coverage zu:" in out and "Big" in out and "Methodik" in out


def test_clusters_groups_two_obvious_clusters(monkeypatch):
    pytest.importorskip("sklearn")
    from brag.search import analytics
    hits = ([_hit("A", 0.9, hid=f"a{i}") for i in range(6)]
            + [_hit("B", 0.9, hid=f"b{i}") for i in range(6)])
    monkeypatch.setattr(analytics, "run_search", lambda *a, **k: hits)

    class _Pt:
        def __init__(self, pid, vec):
            self.id, self.vector = pid, {"dense": vec}

    class _Client:
        def retrieve(self, collection_name, ids, with_vectors, with_payload):
            return [_Pt(i, [1.0, 0.0, 0.0] if str(i).startswith("a")
                        else [0.0, 1.0, 0.0]) for i in ids]

        def close(self):
            pass

    from brag import storage
    monkeypatch.setattr(storage, "get_client", lambda: _Client())
    res = analytics.topic_clusters("thema", n_clusters=2)
    assert not res.get("error")
    assert len(res["clusters"]) == 2
    tops = {c["sources"][0][0] for c in res["clusters"]}
    assert tops == {"A", "B"}


def test_compare_positions_found_and_missing(monkeypatch):
    from brag.search import analytics

    def fake_search(query, top_k=None, source_file=None, **kw):
        return [_hit(source_file, 0.8)] if source_file == "Drittler" else []

    monkeypatch.setattr(analytics, "run_search", fake_search)
    res = analytics.compare_positions("Bauablaufstörung",
                                      ["Drittler", "Unbekannt"])
    assert list(res["results_by_source"]) == ["Drittler"]
    assert res["missing"] == ["Unbekannt"]
    out = tools.compare_positions("Bauablaufstörung", ["Drittler", "Unbekannt"])
    assert "Drittler" in out and "Unbekannt" in out


def test_search_text_unchanged_contract(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    monkeypatch.setattr(tools, "run_search", lambda *a, **k: [_hit("S", 0.7)])
    out = tools.search_text("frage")
    assert out.startswith("**1 hits**") and "S" in out
    monkeypatch.setattr(tools, "run_search", lambda *a, **k: [])
    assert tools.search_text("frage") == tools.NO_HITS_MSG
