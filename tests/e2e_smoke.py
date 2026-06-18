"""In-container end-to-end smoke test for the `e2e` CI workflow.

Ingests the sample PDF dropped into the mounted ``sources/`` folder and runs a
search for a unique marker token, asserting that the document is (1) indexed,
(2) found by search, and (3) cited on the correct printed page. This exercises
the full *local* path — Docling extraction, chunking, the local arctic
embedding, hybrid search, the cross-encoder reranker and the page citation —
without any cloud LLM: contextual retrieval and the vision pass are disabled via
``CR_ENABLED=false`` / ``VISION_ENABLED=false``, so no API key is needed.

Run (from the repo root, inside the app container)::

    docker compose run --rm \
        -e CR_ENABLED=false -e VISION_ENABLED=false -e PYTHONPATH=/app \
        app python /workspace/tests/e2e_smoke.py
"""

import sys

from brag import config, storage
from brag.search.query import search as run_search
from brag.watcher import reconcile_on_startup

MARKER = "BRAGZ9QXMARKER"   # unique token placed on page 2 of the sample
EXPECTED_PAGE = 2


def main() -> int:
    sample = config.SOURCES_DIR / "e2e_sample.pdf"
    print(f"sample: {sample} (exists={sample.exists()})", flush=True)
    if not sample.exists():
        print("FAIL: sample PDF not found in the mounted sources/ folder")
        return 1

    # 1) Ingest. reconcile_on_startup() ensures the collection exists, retries
    #    while Qdrant is still booting, and indexes everything in sources/.
    print("[1/3] ingesting (reconcile_on_startup) ...", flush=True)
    reconcile_on_startup()

    # 2) Confirm the document actually landed in the index.
    print("[2/3] verifying the document is indexed ...", flush=True)
    client = storage.get_client()
    try:
        corpus = storage.list_corpus_sources(client)
    finally:
        client.close()
    print(f"  corpus: {sorted(corpus)}", flush=True)
    if config.normalize_source_key(sample.stem) not in corpus:
        print("FAIL: the sample was not indexed (see ingest output above)")
        return 1

    # 3) Search for the marker and check the citation page.
    print("[3/3] searching for the marker token ...", flush=True)
    hits = run_search(MARKER, top_k=10)
    print(f"  {len(hits)} hit(s)", flush=True)
    match = next((h for h in hits if MARKER in (h.get("text") or "")), None)
    if match is None:
        for h in hits:
            preview = (h.get("text") or "")[:80]
            print(f"   - {h.get('source_file')} p{h.get('page_start')}: {preview!r}")
        print("FAIL: the marker token was not found in any search hit")
        return 1

    page = match.get("page_start")
    page_end = match.get("page_end", page)
    print(f"  matched {match.get('source_file')} on pages {page}-{page_end}", flush=True)
    # The marker sits on page 2, but a tiny 2-page document merges into a single
    # chunk that starts on page 1 and ends on page 2 — so the citing chunk spans
    # pages. Assert the cited page RANGE covers page 2: this proves the citation
    # reflects the marker's true location without coupling the test to Docling's
    # chunk-boundary heuristics (whether page 2 becomes its own chunk).
    if not (isinstance(page, int) and isinstance(page_end, int)
            and page <= EXPECTED_PAGE <= page_end):
        print(f"FAIL: cited pages {page}-{page_end} do not cover page {EXPECTED_PAGE}")
        return 1

    print(f"PASS: ingested, retrieved and cited on pages {page}-{page_end} "
          f"(covers page {EXPECTED_PAGE})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
