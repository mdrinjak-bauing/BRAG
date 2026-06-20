"""Generate the sample corpus used by the `e2e` CI workflow.

Three fixtures, each carrying unique marker tokens so the smoke test can assert
both retrieval and page-citation behaviour:

1. ``e2e_sample.pdf``            — 2 pages, marker on page 2 (basic ingest +
                                   search + page-citation).
2. ``projectA/collide.pdf`` and
   ``projectB/collide.pdf``      — SAME filename in two folders, different
                                   markers (regression for B1: path-qualified
                                   source identity; same-named files must not
                                   delete/overwrite each other).
3. ``e2e_multipage.pdf``         — 3 pages, dense filler on pages 1-2 and the
                                   marker on page 3 (regression for H2: a
                                   multi-page section must cite real per-chunk
                                   pages, not collapse everything to page 1).

Runs on the CI runner (needs ``fpdf2``), writing into the
``WissensWIKI/sources/`` folder that docker-compose bind-mounts into /vault.
"""

from pathlib import Path

from fpdf import FPDF

SOURCES = Path("WissensWIKI/sources")

# ~2 KB of ordinary body text so a page is dense enough to form its own chunk
# (MAX_CHUNK_CHARS defaults to 2000), which is what makes the H2 fixture force
# the page-3 marker into a chunk that does NOT start on page 1.
FILLER = ("This is ordinary body text used as filler so that the page is dense "
          "enough to occupy a chunk on its own. ") * 30


def write_pdf(rel: str, pages: list[str]) -> None:
    out = SOURCES / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    for text in pages:
        pdf.add_page()
        pdf.set_font("helvetica", size=12)
        pdf.multi_cell(0, 8, text)
    pdf.output(str(out))
    print(f"wrote {out} ({out.stat().st_size} bytes)")


def main() -> None:
    # 1) basic: marker on page 2
    write_pdf("e2e_sample.pdf", [
        "Page one. Introduction to the BRAG end-to-end test document. "
        "This page covers general matters only.",
        "Page two. Change orders and altered works are discussed here. "
        "This sentence carries the unique token BRAGZ9QXMARKER for retrieval "
        "testing.",
    ])

    # 2) B1 regression: identical filename in two different project folders
    write_pdf("projectA/collide.pdf", [
        "Project A document. The unique token COLLIDEMARKERA identifies the "
        "content that belongs to project A."])
    write_pdf("projectB/collide.pdf", [
        "Project B document. The unique token COLLIDEMARKERB identifies the "
        "content that belongs to project B."])

    # 3) H2 regression: single long section, marker physically on page 3
    write_pdf("e2e_multipage.pdf", [
        "Chapter introduction. " + FILLER,
        "Continued discussion of the same topic. " + FILLER,
        "Final remarks. This sentence carries the unique token MULTIPAGEMARKER "
        "and is physically located on the third page of the document.",
    ])


if __name__ == "__main__":
    main()
