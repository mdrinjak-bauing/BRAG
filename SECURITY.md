# Security Policy

## Scope

BRAG is a **local, self-hosted** tool. It runs on your own machine via Docker,
stores your knowledge index locally (Qdrant), reads API keys from a local
`.env` file, and — during setup — writes a connection entry into your **Claude
Desktop** configuration so the MCP search server can be reached. It is not a
hosted service and exposes no public endpoint by default.

Because it handles **API keys** and **edits your Claude Desktop config**, we
take reports about those areas (key handling, the setup HTTP bridge, config
writes) especially seriously.

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue for a
suspected vulnerability.

- Email: **markodri92@gmail.com**
- Include: a description, affected version/commit, and steps to reproduce (a
  minimal proof of concept helps a lot).

This is a solo, open-source project, so responses are **best-effort**: expect
an initial acknowledgement within about a week, and a fix or mitigation as soon
as is practical thereafter. Please give a reasonable window for a fix before
any public disclosure.

## Known threat model: prompt injection in ingested documents

By design, BRAG ingests arbitrary documents and feeds their text (and, with the
vision pass, figure images) to an LLM. Untrusted documents can therefore contain
**prompt-injection** content that tries to influence AI-generated context,
classifications or answers. This is a **known and accepted** limitation of any
RAG system: treat AI-generated output as untrusted, and verify answers and
citations against the linked original source. For confidential or untrusted
material, prefer a **local profile** so nothing leaves your machine.

## Supported versions

Only the latest release receives security fixes.
