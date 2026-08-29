# Backend Profiles — which one is for you?

**🇬🇧 English | 🇩🇪 [Deutsch](PROFILES.de.md)**

The profile decides **which AI writes the text work** — the 1–2 sentence
context for each chunk during indexing and the figure descriptions. (The
document type comes from the folder path, not from an LLM.) You choose it once
during setup and can switch later.

**The meaning-index (embeddings) always runs locally**, in every profile
(`snowflake-arctic-embed-l-v2.0`, 1024 dim, on CPU — no GPU needed). So:

- **Switching the AI provider** (Gemini ↔ OpenAI ↔ Claude ↔ a local LLM)
  needs **no re-indexing** — every profile writes into the same collection.
- The embeddings are **free** (no embedding API cost) and your document
  vectors **never leave the machine**.

The cross-encoder re-ranker already runs locally on CPU for every profile, so
doing the embeddings locally too is consistent. The trade-off: the first
ingest downloads the arctic model (~2.3 GB into the model cache) and bulk
ingest on a weak CPU is slower than a cloud embedding API would be. The
re-ranker is also the main CPU cost of each *search* — on a weak machine, lower
it (or turn it off) with `RERANK_PROFILE` (`off`/`eco`/`balanced`/`full`,
default `eco`); see `.env.example`.

## Quick decision guide

- *"I just want it to work, on this laptop."* → **Gemini** (free tier)
- *"I already pay for ChatGPT / Claude and want to use it."* → **OpenAI** / **Claude**
- *"My documents are confidential and I want to process them locally."* → **Hybrid**

## Cloud-LLM profiles (any laptop, need an API key)

All three use local arctic embeddings; only the text LLM differs. With a cloud
profile, the **text** of each chunk is sent to the provider for context
generation — and, with the vision pass on (the default), the images of your
figures too — never the whole files, never the embeddings.

| Profile | Text LLM | Cheapest preset | Get a key |
|---|---|---|---|
| **Gemini** (default) | Google Gemini | `gemini-2.5-flash-lite` | <https://aistudio.google.com/apikey> (free tier) |
| **OpenAI** | OpenAI / ChatGPT | `gpt-4o-mini` | <https://platform.openai.com/api-keys> |
| **Claude** | Anthropic Claude | `claude-haiku-4-5` | <https://console.anthropic.com/> |

The "cheapest preset" is what the setup wizard **preselects**: after your key
validates, the wizard fetches that provider's models and shows them as a
dropdown with this model chosen — pick another from the list if you like (no
need to type an exact id). You can switch provider or model later without
re-indexing (re-run setup → "⚙ Change a setting").

Your key stays on your machine: it is stored only in the local `.env` file
(owner-readable) and used solely to authenticate your own requests to the
provider you chose — never sent to the makers of this app or any third party.
The local profiles below need no key at all.

Gemini's free tier covers steady personal use; heavy bulk indexing may hit
daily limits (the system backs off and retries automatically). OpenAI and
Anthropic are paid per token — the cheapest models above keep this to a few
cents for a typical corpus.

## Local-LLM profiles (nothing leaves your machine)

| | **Hybrid** (cross-platform) |
|---|---|
| Text LLM | your model in [LM Studio](https://lmstudio.ai) |
| Needs | LM Studio running on the host with a loaded model |
| Hardware | ~16 GB RAM runs a ~7B model (`qwen2.5-7b-instruct`); 32 GB a 14B (`qwen2.5-14b-instruct`); 64 GB+ a 27B (`gemma-3-27b-it`) — give LM Studio the model's full path from its model browser (e.g. the Hugging Face id); a GPU helps a lot |
| Images | **the model must be multimodal** — otherwise captions only (see below) |
| Privacy | nothing leaves your machine |

### The model has to be able to see images

The same model writes the text context **and** describes figures. If it cannot
see images, BRAG falls back to each figure's **caption** — the graphic itself is
never described and cannot be found by its content. The run does tell you
(`[vision] figure description unavailable — falling back to caption-only
context`), but only mid-ingest and only after two failed attempts. Better to
check beforehand.

**Careful with the examples above:** `qwen2.5-7b-instruct` and
`qwen2.5-14b-instruct` are **text-only**. Loading them costs you every figure
description. In LM Studio a multimodal model carries an image icon next to its
name; the model id often contains `VL`, `vision` or `multimodal`.

If your machine cannot host a multimodal model, there are two clean ways out:
set `VISION_ENABLED=false` (then you know figures are out of scope) — or index
the corpus **once** with a cloud profile and work locally afterwards. The figure
descriptions then live in the index and are never needed again.

You **don't** pull an embedding model — arctic runs inside the container on its
own. The app runs in Docker and reaches LM Studio on the host via
`host.docker.internal` (port 1234). The local profile is named **Hybrid** in
LM Studio. A single-project install registers one connector named `brag` (in
Claude / LM Studio); once you add more projects, each gets its own labelled
connector — the default becomes `brag-<folder>` and every extra one is
`brag-<name>`, so none is left unlabelled.

## Mixing (advanced)

Every component can be overridden individually in `.env`. The main reason to do
so: **fast cloud embeddings** on weak hardware with a large corpus — set
`EMBEDDING_BACKEND=gemini` (or `openai`) with the matching `EMBEDDING_MODEL` /
`EMBEDDING_DIM`. Note this is the one change that *does* require a one-time
re-ingest (into a separate collection, handled safely). See `.env.example`.

**Privacy note:** this override sends your document text to the embedding
provider (Gemini/OpenAI) — not for confidential or personal content. For
local-only, keep the standard-profile embedder.
