# Architecture

**🇬🇧 English | 🇩🇪 [Deutsch](ARCHITECTURE.de.md)**

For the curious and for contributors. Two containers, one bind-mounted
folder, Claude Desktop as the user interface.

```
 HOST                                   DOCKER
┌──────────────────┐                   ┌─────────────────────────────────┐
│ Claude Desktop   │── docker exec ───▶│ brag-app                         │
│  (MCP, stdio)    │   (mcp_server)    │  ├─ watcher (polling)           │
│                  │                   │  ├─ ingest pipeline             │
│ Browser ◀────────┼── localhost:8765 ─┤  ├─ http bridge (PDF links)    │
│  (PDF at page N) │                   │  └─ search (hybrid + rerank)   │
│                  │                   │            │                    │
│ project folder/ ◀┼─── bind mount ───▶│            ▼                    │
│  (the corpus)    │                   │ brag-qdrant (vector DB,          │
│  WissensWIKI/    │                   │  named volume — no sync risk)   │
│  (not indexed)   │                   └─────────────────────────────────┘
│ LM Studio        ◀── host.docker.internal (hybrid profile only)
└──────────────────┘
```

## Ingest pipeline (per document)

1. **Extract** (`brag/ingest/extract.py`) — Docling parses layout: chapters,
   sections, tables, figure captions, page numbers. Table mode is pinned to
   ACCURATE so library updates cannot silently degrade quality. With the vision
   pass on, figure images are rendered (`generate_picture_images`) and described
   in the contextualize step. The output is **not flat text** but an *ordered
   stream of typed items* — heading, body paragraph, table, figure — each
   tagged with the page it sits on.
   - **Between extract and chunk** (`extract.py` walks that stream): consecutive
     body paragraphs are collected per section (carrying their page numbers).
     At every structural boundary — a new heading, a table or a figure — or at
     the document's end, the collected text is handed to the chunker. **Tables
     and figures do not go through the text window**: each becomes its own chunk
     right here (with its page; a figure also carries its vision description).
2. **Chunk** (`chunking.py`) — the per-section text from step 1 goes through a
   paragraph-level sliding window (2000 chars, 200 overlap); each text chunk
   keeps the **real page range** of the paragraphs it actually contains
   (`page_start..page_end`), so a passage on page 18 is cited as page 18, not as
   the section's first page. Long tables split by rows with the header
   replicated per part; a hard splitter handles OCR text without paragraph
   boundaries.
3. **Contextualize** (`contextualize.py`) — each chunk gets 1–2 sentences of
   LLM context (table of contents + current chapter as grounding), processed in
   batches (5 chunks per LLM call by default). Figures go through the **vision
   pass** (`VISION_ENABLED`, on by default): the rendered image is sent to the
   multimodal LLM for an honest description that is embedded too. Without a
   vision model or image, it falls back to the honest caption-only prompt (never
   describe unseen content).
4. **Embed** — dense vector (local arctic-embed-l-v2.0, 1024-dim, CPU) + BM25
   sparse vector with language-aware stemming. Failed embeddings are logged and
   skipped — never stored as zero vectors.
5. **Store** (`pipeline.py` / `storage.py`) — the new points are upserted
   **first** (batched, 100 per batch, `wait=True`) into a hybrid Qdrant
   collection (dense + sparse with IDF modifier); only **after** every point is
   server-side confirmed are the remaining stale chunks of the same source
   deleted (idempotent re-ingest). A crash between the two steps leaves at worst
   harmless orphans, never a half-deleted document.
6. **Note** (`notes.py`) — an Obsidian-compatible literature note; the user's
   "My notes" section survives regeneration.

## Query pipeline

dense + sparse prefetch (80 each) → reciprocal rank fusion → top 40 →
cross-encoder reranking (`BAAI/bge-reranker-v2-m3`) → source-diversity cap
(max 3 chunks/source) → top k (15 by default). These breadths follow the
`RERANK_PROFILE` dial (default `eco` = load 160, rerank 40; also
`off`/`balanced`/`full`). Rerank scores are reported, never used as a
hard filter — cross-encoder scores are not absolutely calibrated, and any
floor cuts legitimate top hits on factual queries.

## Design decisions

- **Polling watcher**, not FS events: events don't cross the Docker mount
  boundary; polling behaves identically on macOS and Windows hosts.
- **Named volume for Qdrant**: keeps the database out of iCloud/OneDrive
  sync (mmap files + cloud sync = corruption) and immune to wrong-path
  mounts.
- **Collection name derives from the embedding backend**: switching models
  can never write incompatible vectors into an existing collection.
- **One container for app concerns**: the MCP server runs as a per-connection
  process (`docker exec`) inside the same container as the watcher, sharing
  config and model caches.
- **NFC normalization** of all source keys: macOS file names arrive NFD;
  comparisons against stored payloads must not depend on the platform.
