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
    monkeypatch.setattr(config, "DATA_DIR", tmp_path, raising=False)
    chunk = _figure_chunk(_png_bytes())
    rel = images.save_figure_image(chunk)
    assert rel == f"figures/{chunk.chunk_id}.jpg"
    assert (tmp_path / rel).is_file()
    chunk.image_file = rel
    assert chunk.payload()["image_file"] == rel
    # A chunk without a stored image carries NO image_file key (payload stays
    # clean for text/table chunks and pre-feature indexes).
    assert "image_file" not in _figure_chunk(_png_bytes()).payload()


def test_save_figure_image_bad_b64_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path, raising=False)
    chunk = _figure_chunk(b"")
    chunk.image_b64 = "%%%not-base64%%%"
    assert images.save_figure_image(chunk) == ""


def test_collect_hit_images_caps_dedupes_and_skips_missing(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path, raising=False)
    (tmp_path / "figures").mkdir()
    for name in ("a", "b", "c", "d"):
        (tmp_path / "figures" / f"{name}.jpg").write_bytes(
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
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "secret.jpg").write_bytes(b"outside")
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


# ── coverage ─────────────────────────────────────────────────────────────────

def _hit(src, score, chapter="", text="lorem", page=1):
    return {"source_file": src, "rerank_score": score, "score": score,
            "chapter": chapter, "text": text, "page_start": page,
            "rel_path": f"{src}.pdf"}


def test_coverage_aggregate_broad_needs_count_and_score():
    hits = ([_hit("Big", 0.9)] * 3          # count 3, high score → substantial
            + [_hit("Thin", 0.95)]           # count 1 → peripheral in broad
            + [_hit("Weak", 0.1)] * 4)       # count 4 but low score → peripheral
    agg = tools._coverage_aggregate(hits, min_score=0.4, coverage_mode="broad")
    assert [e["source"] for e in agg["substantial"]] == ["Big"]
    assert {e["source"] for e in agg["peripheral"]} == {"Thin", "Weak"}
    assert agg["total_sources"] == 3 and agg["total_chunks"] == 8


def test_coverage_aggregate_specific_promotes_focused_source():
    # 'specific' drops the count gate and ranks by max_score × spec-factor:
    # the narrow source with ONE excellent hit outranks the broad one.
    hits = [_hit("Broad", 0.8)] * 10 + [_hit("Focused", 0.8)]
    agg = tools._coverage_aggregate(hits, min_score=0.4,
                                    coverage_mode="specific")
    assert [e["source"] for e in agg["substantial"]][0] == "Focused"


def test_coverage_aggregate_both_returns_second_table():
    agg = tools._coverage_aggregate([_hit("A", 0.9)] * 3, min_score=0.4,
                                    coverage_mode="both")
    assert "substantial_specific" in agg


def test_coverage_text_formats_and_validates(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    monkeypatch.setattr(tools, "run_search",
                        lambda *a, **k: [_hit("Big", 0.9, chapter="4 Methodik")] * 3)
    out = tools.coverage_text("Reifegrad")
    assert "Quellen-Abdeckung" in out and "Big" in out and "Methodik" in out
    assert "localhost:8765/file/" in out          # deep link carried through
    assert "coverage_mode" in tools.coverage_text("x", coverage_mode="bogus") \
        or "Unbekannter coverage_mode" in tools.coverage_text("x", coverage_mode="bogus")
    monkeypatch.setattr(tools, "run_search", lambda *a, **k: [])
    assert tools.coverage_text("nichts") == tools.NO_HITS_MSG


# ── clusters ─────────────────────────────────────────────────────────────────

def _vec_hit(src, vec, text="t", page=1):
    return {"source_file": src, "_vector": vec, "text": text,
            "page_start": page, "rel_path": f"{src}.pdf", "chapter": "K1"}


def test_clusters_text_groups_two_obvious_clusters(monkeypatch):
    pytest.importorskip("numpy")
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    hits = ([_vec_hit("A", [1.0, 0.0, 0.01 * i]) for i in range(6)]
            + [_vec_hit("B", [0.0, 1.0, 0.01 * i]) for i in range(6)])
    monkeypatch.setattr(tools, "run_search", lambda *a, **k: hits)
    out = tools.clusters_text("thema", n_clusters=2)
    assert "Themen-Map" in out
    assert out.count("### Cluster") == 2
    # Each cluster is dominated by one source — both sources appear.
    assert "`A`" in out and "`B`" in out


def test_clusters_text_too_few_hits(monkeypatch):
    monkeypatch.setattr(tools, "run_search",
                        lambda *a, **k: [_vec_hit("A", [1.0, 0.0, 0.0])])
    assert "zu wenig" in tools.clusters_text("x")


def test_kmeans_deterministic():
    np = pytest.importorskip("numpy")
    X = np.array([[1.0, 0.0], [0.99, 0.01], [0.0, 1.0], [0.01, 0.99]])
    X = X / np.linalg.norm(X, axis=1, keepdims=True)
    l1, _ = tools._kmeans(X, 2)
    l2, _ = tools._kmeans(X, 2)
    assert (l1 == l2).all()
    assert l1[0] == l1[1] and l1[2] == l1[3] and l1[0] != l1[2]


# ── compare_positions ────────────────────────────────────────────────────────

def test_compare_positions_side_by_side_and_missing(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)

    def fake_search(query, top_k=None, max_chunks_per_source=None,
                    source_file=None, collection_name=None, **kw):
        return [_hit(source_file, 0.8)] if source_file == "Drittler" else []

    monkeypatch.setattr(tools, "run_search", fake_search)
    out = tools.compare_positions_text("Bauablaufstörung",
                                       ["Drittler", "Unbekannt"])
    assert "Positions-Vergleich" in out
    assert "[1] Drittler" in out
    assert "Nicht gefunden (1)" in out and "Unbekannt" in out
    assert "Diagnose" not in out                      # one source DID match


def test_compare_positions_all_missing_adds_diagnosis(monkeypatch):
    monkeypatch.setattr(tools, "run_search", lambda *a, **k: [])
    out = tools.compare_positions_text("x", ["A", "B"])
    assert "Diagnose" in out and "list_sources()" in out


def test_compare_positions_validates_source_count():
    assert "mindestens 2" in tools.compare_positions_text("x", ["nur-eine"])
    assert "höchstens 7" in tools.compare_positions_text("x", [str(i) for i in range(8)])


def test_search_text_unchanged_contract(monkeypatch):
    monkeypatch.setattr(config, "BRIDGE_PUBLIC_URL", "http://localhost:8765",
                        raising=False)
    monkeypatch.setattr(tools, "run_search", lambda *a, **k: [_hit("S", 0.7)])
    out = tools.search_text("frage")
    assert out.startswith("**1 hits**") and "S" in out
    monkeypatch.setattr(tools, "run_search", lambda *a, **k: [])
    assert tools.search_text("frage") == tools.NO_HITS_MSG
