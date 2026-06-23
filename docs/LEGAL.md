# Legal Notices

**🇬🇧 English | 🇩🇪 [Deutsch](LEGAL.de.md)**

> **Not legal advice.** This text only summarizes general points (as of June
> 2026) and is no substitute for legal counsel. The law changes and depends on
> your country, your documents and your contracts. When in doubt, seek
> qualified advice.

## Disclaimer of warranty

BRAG is a **privately built personal project** — created by one person alongside
a doctorate and shared as open source, not a commercial product. There is **no
support obligation, no service-level agreement and no warranty of any kind.**

This software is provided under the [MIT License](../LICENSE) "as is", **without
any warranty** and without any guarantee of fitness, correctness, data
protection or legal compliance. You use it at your own risk and on your own
responsibility. The authors and contributors are not liable for any damages,
data loss or legal consequences arising from its use.

**You alone decide which documents and data you process with it** — and,
depending on the chosen profile, where that data is sent (see *Data protection /
confidentiality* below). That choice, and its consequences, are your
responsibility.

AI-generated answers and citations can be incorrect or fabricated; always
verify them against the linked original page before relying on or citing them.

## Data protection / confidentiality

What leaves your machine depends on the chosen **profile**:

- **Local profile (Hybrid):** **nothing** leaves your machine — neither
  document text nor embeddings. The meaning index is computed locally in every
  standard profile anyway. The one exception is the optional cloud-embedding
  override (`EMBEDDING_BACKEND=gemini`/`openai`, documented in `.env.example`):
  it additionally sends your document text to the embedding provider.
- **Cloud profiles (Gemini, OpenAI, Claude):** to generate context, the **text
  excerpt of each chunk** is sent to the respective provider — and, with the
  **vision pass** on (the default), the **rendered images of your figures** as
  well. Whole files, the embeddings and your later chat questions are not sent.
  So content from your documents leaves your machine and is subject to the
  provider's terms. You can disable the image upload with `VISION_ENABLED=false`.

*One-time, in every profile: the very first run downloads the local analysis
models — the embedder, reranker and document parser — from HuggingFace. That is
the only outbound connection for local work; once cached, the local profile
sends nothing.*

**Your API key.** Your API key is stored only in a local `.env` file on your
computer (owner-readable only) and is used solely to authenticate your own
requests to the provider you chose. It is never sent to the makers of this app
or any third party; the live check during setup just sends one small test
request to that provider to confirm the key works. The local profile (LM
Studio) needs no key at all.

**Important — Gemini free vs. paid tier (the default is free):** On the *free*
tier of Google AI Studio / the Gemini API, Google may **use** the submitted
inputs and outputs to **improve its products**, and they may be **reviewed by
humans** — so the free tier is **not suitable** for confidential, secret or
personal content. The lever is the **billing tier, not the model**: if you **set
up billing** on your Google account and load a small amount of credit, the
**paid tier of the same Gemini API key is not used for training** (per Google's
terms). So for sensitive content, either **enable billing** (paid tier) or use a
**local profile**.

For context on the other cloud providers (as of June 2026, no guarantee — the
provider's current terms always govern):

- **OpenAI API:** API data is **not** used for training by default; short
  retention for abuse monitoring (typically up to ~30 days).
- **Anthropic API:** API data is **not** used for training; short retention (7
  days by default). Zero Data Retention is available for business customers.

**GDPR:** If your documents contain personal data and you use a cloud profile,
**you** are generally the controller. In that case it is your own
responsibility to check, among other things, the legal basis, a data-processing
agreement (DPA) with the provider, and any third-country transfer. This project
provides no DPA and guarantees no GDPR compliance.

## Professional or organizational use

If you use BRAG professionally — especially with **personal** or
business-critical data — clear it **before** deployment with the responsible
bodies: your data protection officer, IT security, where applicable the works
council, and the legal department. This is not red tape; it protects you and
your organization.

From a data-security standpoint, the **local profile is clearly preferable** here
(Hybrid): document text and images never leave the machine, there is no
third-country transfer and no data processing with external providers. For
confidential or personal material this is the safe default.

**IT departments** can **harden BRAG for organizational use** — e.g. local
models only (LM Studio or a self-hosted inference backend), centrally
managed configuration and keys, access and network restrictions, backup and
deletion policies for the knowledge store and index, and a documented assessment (such as
a data-protection impact assessment, where required). The open architecture
(Docker, small modules, MCP) is built for exactly that.

## Copyright and licensed works

You are **solely responsible** for only ingesting and processing documents for
which you hold the necessary rights.

- **Your own scientific analysis:** For lawfully accessible works, the EU text-
  and-data-mining exceptions may apply (Articles 3 and 4 of the DSM Directive;
  in Germany implemented as **§ 60d UrhG** for scientific research and **§ 44b
  UrhG** for general TDM). Under conditions they permit making your own copies
  for automated analysis. A purely private index of lawfully obtained works
  often falls under this or under the private-copy exception.
- **But:** these exceptions are **limited.** Contract/licence terms (e.g. from
  publishers, databases, e-book vendors) can restrict use, and for general TDM
  (§ 44b UrhG / Art. 4) rightsholders may declare a **machine-readable
  reservation (opt-out)**.
- **Mind cloud transmission:** sending copyrighted text to a cloud provider is
  an **additional reproduction / transmission to a third party** and is not
  necessarily covered by a TDM exception. For licensed or confidential works,
  when in doubt use a **local profile** so nothing leaves your machine.
- **Do not circumvent protection:** copy protection / DRM (e.g. on e-books) must
  not be circumvented.

## Provider terms

When using a cloud profile you must comply with the respective terms of use —
[Google](https://ai.google.dev/gemini-api/terms),
[OpenAI](https://openai.com/policies/) or
[Anthropic](https://www.anthropic.com/legal). This project is not affiliated
with these providers.

---

*As of June 2026. No guarantee of accuracy.*
