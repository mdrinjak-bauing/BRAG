# Third-Party Notices

BRAG (*Building Retrieval-Augmented Generation*) is licensed under the
[MIT License](LICENSE).

This project **does not redistribute** the model weights, libraries or engine
listed below. They are fetched **at runtime or build time** by their respective
package managers (pip / Hugging Face / Docker) on your machine, and each remains
under **its own license**. The notices below are provided for attribution and
convenience; the upstream license text always governs.

## Models (downloaded at first run from Hugging Face)

Not redistributed by this project — downloaded on first use and cached locally.

| Model | License | Role |
| --- | --- | --- |
| [Snowflake/snowflake-arctic-embed-l-v2.0](https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0) | Apache-2.0 | Local embedding model |
| [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | Apache-2.0 | Local cross-encoder reranker |
| Docling layout & table models (IBM) | downloaded by the `docling` library | Document layout / table structure |

## Key Python dependencies

Pinned versions are listed in [`requirements.txt`](requirements.txt).

| Package | Version | License |
| --- | --- | --- |
| [docling](https://github.com/docling-project/docling) | 2.103.0 | MIT |
| [qdrant-client](https://github.com/qdrant/qdrant-client) | 1.18.0 | Apache-2.0 |
| [sentence-transformers](https://github.com/UKPLab/sentence-transformers) | 5.4.1 | Apache-2.0 |
| [torch](https://github.com/pytorch/pytorch) | (via dependencies) | BSD-3-Clause |
| [fastembed](https://github.com/qdrant/fastembed) | 0.8.0 | Apache-2.0 |
| [google-genai](https://github.com/googleapis/python-genai) | 2.8.0 | Apache-2.0 |
| [mcp](https://github.com/modelcontextprotocol/python-sdk) | 1.28.0 | MIT |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.2.2 | BSD-3-Clause |
| [watchdog](https://github.com/gorakhargosh/watchdog) | 6.0.0 | Apache-2.0 |
| [fpdf2](https://github.com/py-pdf/fpdf2) | (CI tests only) | LGPL-3.0 |

`torch` is pulled in transitively by `sentence-transformers`. `fpdf2` is used
**only in the CI test suite** to generate sample PDFs and is not part of the
runtime image.

## Vector engine

| Component | License | How it is used |
| --- | --- | --- |
| [Qdrant](https://github.com/qdrant/qdrant) (`qdrant/qdrant` Docker image) | Apache-2.0 | Pulled as a Docker image and **run** locally — not redistributed |

---

*If you spot an incorrect license or a missing attribution, please open an issue
or email markodri92@gmail.com.*
