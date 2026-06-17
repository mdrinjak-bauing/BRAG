# Legal Notices

**🇬🇧 English | 🇩🇪 [Deutsch](LEGAL.de.md)**

> **Not legal advice.** This text only summarizes general points (as of June
> 2026) and is no substitute for legal counsel. The law changes and depends on
> your country, your documents and your contracts. When in doubt, seek
> qualified advice.

## Disclaimer of warranty

This software is provided under the [MIT License](../LICENSE) "as is", **without
any warranty** and without any guarantee of fitness, correctness, data
protection or legal compliance. You use it at your own risk and on your own
responsibility. The authors and contributors are not liable for any damages,
data loss or legal consequences arising from its use.

## Data protection / confidentiality

What leaves your machine depends on the chosen **profile**:

- **Local profiles (Hybrid, Local):** **nothing** leaves your machine — neither
  document text nor embeddings. The meaning index is computed locally in every
  profile anyway.
- **Cloud profiles (Gemini, OpenAI, Claude):** to generate context, the **text
  excerpt of each chunk** is sent to the respective provider (never whole files,
  never the embeddings, never your later chat questions). So content from your
  documents leaves your machine and is subject to the provider's terms.

**Important — free Gemini tier (the default):** On the *free* tier of Google AI
Studio, Google may **use** the submitted inputs and outputs to **improve its
products**, and they may be **reviewed by humans**. The free tier is therefore
**not suitable** for confidential, secret or personal content — use a **local
profile** instead, or a paid tier (e.g. Google Cloud/Vertex AI) where, per the
provider, data is not used for training.

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
