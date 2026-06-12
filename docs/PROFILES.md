# Backend Profiles — which one is for you?

The profile decides **where the AI processing happens** during indexing and
search. You choose it once during setup; you can switch later, but switching
embedding models requires re-indexing all documents (the vectors of different
models are mathematically incompatible — the system handles this safely by
using a separate collection per model, but the work runs again).

## Quick decision guide

- *"I just want it to work, on this laptop."* → **A — Cloud**
- *"My documents are confidential / I have a strong Mac."* → **B — Hybrid**
- *"Confidential documents, but on Windows/Linux or an older Mac."* → **C — Local**

## A — Cloud (recommended default)

| | |
|---|---|
| Embeddings | Google `gemini-embedding-001` (3072 dim) |
| Context generation | Google Gemini Flash |
| Needs | free API key from <https://aistudio.google.com/apikey> |
| Hardware | anything that runs Docker |
| Privacy | document text is sent to Google for processing |
| Cost | free tier covers steady personal use; heavy bulk indexing may hit daily limits (the system backs off and retries automatically) |

## B — Hybrid (Apple Silicon Macs)

| | |
|---|---|
| Embeddings | `snowflake-arctic-embed-l-v2.0`, local (1024 dim) |
| Context generation | your model in [LM Studio](https://lmstudio.ai) |
| Needs | LM Studio installed and running on the host with a loaded model |
| Hardware | M-series Mac, 32 GB RAM recommended |
| Privacy | nothing leaves your machine |

Note: the app runs in Docker and reaches LM Studio on your Mac via
`host.docker.internal:1234`. In LM Studio, enable the local server
(Developer → Start Server) and load a mid-size instruct model.
Embeddings run inside the container on CPU — fine for steady use, slow for
bulk re-indexing of hundreds of documents.

## C — Local (cross-platform, privacy-first)

| | |
|---|---|
| Embeddings | `nomic-embed-text` via [Ollama](https://ollama.com) (768 dim) |
| Context generation | your model via Ollama (default `llama3.1`) |
| Needs | Ollama installed; run `ollama pull nomic-embed-text` and `ollama pull llama3.1` once |
| Hardware | 16 GB RAM minimum; a GPU helps a lot |
| Privacy | nothing leaves your machine |

## Mixing (advanced)

Every component can be overridden individually in `.env` — e.g. cloud
embeddings with a local LLM for context generation. See `.env.example`.
