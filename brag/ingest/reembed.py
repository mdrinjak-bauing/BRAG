"""Rebuild the DENSE vectors of an existing index from its own payload.

Adding the document header (author · title · type · chapter) to the dense text
changes what a vector means. An index built before it would otherwise be MIXED:
old chunks embedded without the header, new ones with — inconsistent ranking
between documents, and no way for a user to tell.

The repair is cheap because everything the dense text is built from already
lives in the stored payload. No source files, no Docling, no LLM, no API cost —
one pass of the embedder over the index itself.

The SPARSE vector is never touched. The header must stay out of BM25, where an
identical header on every chunk of a work would blur document discrimination.

    python -m brag.ingest.reembed --dry-run
    python -m brag.ingest.reembed
"""
from brag import config, storage
from brag.embeddings import get_embedder
from brag.ingest.extract import dense_text_from_payload

SCROLL_BATCH = 256


def reembed_dense(client=None, collection: str | None = None, batch: int = 64,
                  dry_run: bool = False, source_file: str | None = None,
                  progress=print) -> dict:
    """Replace every point's dense vector with one built from its payload.

    `source_file` restricts the run to one document — used after a metadata
    patch, which rewrites author/year/doc_type/source_file in the payload
    without touching the vector and would otherwise leave the two disagreeing.

    Returns {"total", "updated", "skipped", "would_update"}.
    """
    eigener_client = client is None
    client = client or storage.get_client()
    collection = collection or config.COLLECTION_NAME
    embedder = None if dry_run else get_embedder()
    bericht = {"total": 0, "updated": 0, "skipped": 0, "would_update": 0}
    flt = _source_filter(source_file)
    try:
        gesamt = (client.count(collection, exact=True, count_filter=flt).count
                  if flt else client.count(collection, exact=True).count)
        bericht["total"] = gesamt
        if not gesamt:
            progress("nothing indexed — nothing to re-embed")
            return bericht
        progress(f"re-embedding {gesamt} chunks from their stored payload "
                 f"({'dry run' if dry_run else 'writing'}) …")
        offset, puffer, fertig = None, [], 0
        while True:
            punkte, offset = (
                client.scroll(collection, limit=SCROLL_BATCH, offset=offset,
                              scroll_filter=flt, with_payload=True,
                              with_vectors=False)
                if flt else
                client.scroll(collection, limit=SCROLL_BATCH, offset=offset,
                              with_payload=True, with_vectors=False)
            )
            for p in punkte:
                text = dense_text_from_payload(p.payload or {})
                if not text.strip():
                    # A point with no text at all cannot be embedded, and an
                    # empty vector would be worse than leaving the old one.
                    bericht["skipped"] += 1
                    continue
                puffer.append((p.id, text))
                if len(puffer) >= batch:
                    fertig += _flush(client, collection, embedder, puffer,
                                     dry_run, bericht)
                    puffer.clear()
                    progress(f"  {fertig}/{gesamt}")
            if not offset:
                break
        if puffer:
            fertig += _flush(client, collection, embedder, puffer, dry_run, bericht)
        getan = bericht['would_update'] if dry_run else bericht['updated']
        wort = 'would be re-embedded' if dry_run else 're-embedded'
        progress(f"done: {getan} {wort}, {bericht['skipped']} skipped (no text)")
        return bericht
    finally:
        if eigener_client:
            client.close()


def _source_filter(source_file: str | None):
    """Restrict to one document, with the same NFC/NFD/raw triple-probe
    storage.patch_source_metadata uses — a single-form match silently misses
    payloads written under a different unicode normalization."""
    if not source_file:
        return None
    from qdrant_client.models import FieldCondition, Filter, MatchAny

    return Filter(must=[FieldCondition(
        key="source_file",
        match=MatchAny(any=config.source_key_variants(source_file)),
    )])


def _flush(client, collection, embedder, puffer, dry_run, bericht) -> int:
    if dry_run:
        bericht["would_update"] += len(puffer)
        return len(puffer)
    from qdrant_client.models import PointVectors

    vektoren = embedder.embed_documents([t for _, t in puffer])
    if len(vektoren) != len(puffer):
        # A backend broke the one-entry-per-text contract. Pairing by position
        # would write each chunk's vector onto a DIFFERENT chunk — silent, and
        # unrecoverable without a full re-ingest. pipeline.py guards the same
        # call the same way.
        raise RuntimeError(
            f"embedder returned {len(vektoren)} vectors for {len(puffer)} texts "
            "— refusing to pair them by position"
        )
    punkte = [
        PointVectors(id=pid, vector={config.DENSE_VECTOR: v})
        for (pid, _), v in zip(puffer, vektoren) if v is not None
    ]
    if punkte:
        client.update_vectors(collection_name=collection, points=punkte)
    bericht["updated"] += len(punkte)
    bericht["skipped"] += len(puffer) - len(punkte)
    return len(puffer)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be re-embedded, write nothing")
    ap.add_argument("--batch", type=int, default=64,
                    help="chunks per embedder call (default 64)")
    ap.add_argument("--collection", default=None,
                    help="override the collection (default: the active one)")
    a = ap.parse_args()
    if a.collection:
        reembed_dense(collection=a.collection, batch=a.batch, dry_run=a.dry_run)
        return 0
    # Every project has its own collection (registry.collection_for). Repairing
    # only the default one and reporting success would leave the others silently
    # mixed, with nothing to discover them by. The watcher loops the same way.
    from brag import registry

    slugs = [p["slug"] for p in registry.projects()] or [None]
    for slug in slugs:
        with config.project_context(slug):
            if slug:
                print(f"── project {slug} ({config.COLLECTION_NAME})")
            reembed_dense(batch=a.batch, dry_run=a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
