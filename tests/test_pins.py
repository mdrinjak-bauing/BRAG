"""Why the pinned versions are what they are.

A bare `docling==2.108.0` invites the next contributor — or the next dependabot
PR — to bump it, watch unit+lint+docker-build go green, and merge. The one job
that catches the problem is e2e, and what it catches is not a crash: it is
SILENT TEXT LOSS. On the same 2848-byte fixture, docling 2.108.0 extracts 4
chunks and 2.123.0 extracts 2, and the page-3 marker disappears from the corpus
entirely (CI runs 33275343462 vs 33273838065).

So the pin needs a reason recorded next to it, and that reason needs a test —
otherwise it is a comment someone deletes while tidying.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _requirements() -> str:
    return (REPO / "requirements.txt").read_text(encoding="utf-8")


def test_docling_is_pinned_exactly():
    zeilen = [z for z in _requirements().splitlines() if z.strip().startswith("docling")]
    assert zeilen and all("==" in z for z in zeilen), (
        f"docling must be pinned exactly, not floated: {zeilen}"
    )


def test_the_docling_pin_says_why_it_is_held():
    """A version held back against upstream needs its reason in the file, not
    only in a changelog entry nobody reads while merging a dependabot PR."""
    text = _requirements()
    kopf = text.split("docling==")[0]
    assert "docling" in kopf.lower(), (
        "requirements.txt pins docling but nothing above the pin explains why it "
        "is held back — see CI runs 33275343462 (4 chunks) vs 33273838065 (2)"
    )


def test_the_image_disables_torch_runtime_compilation():
    """docling 2.118.0-2.120.2 shipped with compile_torch_models=True and a
    layout engine that calls torch.compile; the slim image has no C++ compiler,
    so EVERY pdf conversion failed with InvalidCxxCompiler (CI run 32389948150).
    Upstream turned the flag off again in 2.121.0, which means today's failure
    is gone by luck, not by design. Pin the behaviour rather than the luck."""
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert "DOCLING_INFERENCE_COMPILE_TORCH_MODELS=false" in dockerfile, (
        "nothing stops a future docling from re-enabling torch.compile inside an "
        "image that cannot compile"
    )
