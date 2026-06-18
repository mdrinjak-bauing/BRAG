"""Generate the tiny 2-page sample PDF used by the `e2e` CI workflow.

Page 2 carries a unique marker token (`BRAGZ9QXMARKER`) so the end-to-end test
can verify both that the document is retrieved *and* that it is cited on the
correct printed page. Runs on the CI runner (needs `fpdf2`), writing into the
`wissensspeicher/sources/` folder that docker-compose bind-mounts into /vault.
"""

from pathlib import Path

from fpdf import FPDF

OUT = Path("wissensspeicher/sources/e2e_sample.pdf")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()

    pdf.add_page()
    pdf.set_font("helvetica", size=14)
    pdf.multi_cell(
        0, 10,
        "Page one. Introduction to the BRAG end-to-end test document. "
        "This page covers general matters only.",
    )

    pdf.add_page()
    pdf.set_font("helvetica", size=14)
    pdf.multi_cell(
        0, 10,
        "Page two. Change orders and altered works are discussed here. "
        "This sentence carries the unique token BRAGZ9QXMARKER for retrieval "
        "testing.",
    )

    pdf.output(str(OUT))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
