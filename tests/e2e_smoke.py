"""In-container end-to-end smoke test for the `e2e` CI workflow.

Ingests the sample corpus (see make_sample_pdf.py) and asserts, against a live
Qdrant and the full LOCAL path (Docling → arctic embedding → hybrid search →
reranker → page citation), that:

  * basic: a document is indexed, found, and cited on the page the marker is on;
  * B1:    two same-named files in different folders are BOTH retained and
           retrievable (path-qualified source identity — no silent cross-folder
           deletion);
  * H2:    a marker on page 3 of a long single section is cited from its real
           page, not collapsed to the section's first page.

No cloud LLM is needed: contextual retrieval and the vision pass are disabled
via env (CR_ENABLED=false / VISION_ENABLED=false), so no API key is used.

Run (from the repo root, inside the app container)::

    docker compose run --rm \
        -e CR_ENABLED=false -e VISION_ENABLED=false -e PYTHONPATH=/app \
        app python /workspace/tests/e2e_smoke.py
"""

import sys

from brag import config, storage
from brag.search.query import search as run_search
from brag.watcher import reconcile_on_startup


def _find(marker: str, top_k: int = 10):
    """Return (hits, first hit whose text contains the marker or None)."""
    hits = run_search(marker, top_k=top_k)
    return hits, next((h for h in hits if marker in (h.get("text") or "")), None)


def main() -> int:
    failures: list[str] = []

    print("[1/6] ingesting the sample corpus (reconcile_on_startup) ...", flush=True)
    reconcile_on_startup()

    print("[2/6] reading the corpus ...", flush=True)
    client = storage.get_client()
    try:
        corpus = storage.list_corpus_sources(client)
    finally:
        client.close()
    print(f"  corpus: {sorted(corpus)}", flush=True)

    # --- basic: ingest + search + citation covers the marker's page ----------
    print("[3/6] basic citation ...", flush=True)
    _, m = _find("BRAGZ9QXMARKER")
    if m is None:
        failures.append("basic: marker BRAGZ9QXMARKER not found in any hit")
    else:
        ps, pe = m.get("page_start"), m.get("page_end", m.get("page_start"))
        if not (isinstance(ps, int) and isinstance(pe, int) and ps <= 2 <= pe):
            failures.append(f"basic: marker cited pages {ps}-{pe}, expected to cover page 2")
        else:
            print(f"  ✓ basic: found and cited on pages {ps}-{pe}")

    # --- B1: same filename in two folders must not collide -------------------
    print("[4/6] regression checks (B1 collision, H2 multi-page) ...", flush=True)
    for key, marker in [("projectA/collide", "COLLIDEMARKERA"),
                        ("projectB/collide", "COLLIDEMARKERB")]:
        if config.normalize_source_key(key) not in corpus:
            failures.append(f"B1: '{key}' missing from corpus — same-named file was overwritten")
        _, mm = _find(marker)
        if mm is None:
            failures.append(f"B1: marker {marker} not found — its chunks were cross-deleted")
        else:
            print(f"  ✓ B1: {marker} retained in '{mm.get('source_file')}'")

    # --- H2: page-3 marker in a long section is not cited as page 1 ----------
    _, mp = _find("MULTIPAGEMARKER")
    if mp is None:
        failures.append("H2: multipage marker MULTIPAGEMARKER not found")
    else:
        ps = mp.get("page_start")
        if not (isinstance(ps, int) and ps >= 2):
            failures.append(f"H2: multipage marker cited page_start={ps}, "
                            f"expected >= 2 (section collapsed to its first page?)")
        else:
            print(f"  ✓ H2: multipage marker cited from page {ps} (not collapsed to 1)")

    # --- H3: inspect_chunks page filter covers chunks that SPAN the page -----
    # The 2-page sample merges into one chunk (page_start=1, page_end=2); the
    # old page_start==page filter missed it on page 2, the range filter finds it.
    from brag.mcp_server import inspect_chunks
    out = inspect_chunks("e2e_sample", page=2)
    if "BRAGZ9QXMARKER" not in out:
        failures.append("H3: inspect_chunks(page=2) missed the chunk spanning pages 1-2")
    else:
        print("  ✓ H3: inspect_chunks page filter covers spanning chunks")

    # --- C9: re-ingesting the same file is idempotent (upsert-before-delete) -
    print("[5/6] re-ingest idempotency (upsert-before-delete) ...", flush=True)
    from brag.ingest.pipeline import ingest, reapply_folder_metadata
    before = len(corpus)
    ingest(config.SOURCES_DIR / "e2e_sample.pdf")
    client = storage.get_client()
    try:
        corpus2 = storage.list_corpus_sources(client)
    finally:
        client.close()
    if len(corpus2) != before:
        failures.append(f"C9: corpus size changed on re-ingest ({before} -> {len(corpus2)}) "
                        "— upsert-before-delete/exclude_ids idempotency broken")
    elif _find("BRAGZ9QXMARKER")[1] is None:
        failures.append("C9: marker lost after re-ingesting the same file")
    else:
        print("  ✓ C9: re-ingest left the corpus stable and the marker retrievable")

    # --- C8: a _meta.txt change re-patches already-indexed docs (no re-ingest)-
    print("[6/6] _meta.txt live-update (reapply_folder_metadata) ...", flush=True)
    (config.SOURCES_DIR / "projectA" / "_meta.txt").write_text(
        "client: TestClientX\n", encoding="utf-8")
    patched = reapply_folder_metadata(config.SOURCES_DIR / "projectA")
    if patched < 1:
        failures.append(f"C8: reapply_folder_metadata patched {patched} docs in projectA/, "
                        "expected >= 1 (already-indexed doc not re-tagged)")
    else:
        print(f"  ✓ C8: _meta.txt change re-applied to {patched} already-indexed doc(s)")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\nPASS: basic citation, B1 no-collision, H2 multi-page citation, "
          "H3 page-range inspect, C9 re-ingest idempotency and C8 _meta.txt "
          "live-update all verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
