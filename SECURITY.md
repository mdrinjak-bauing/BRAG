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

## Known threat model: the local HTTP bridge is loopback-only, not authenticated

BRAG runs a small HTTP bridge on `127.0.0.1:8765` (published **only to loopback**
in `docker-compose.yml`). The persistent app uses it to serve your documents for
page-deep-links (`/file/…`) and to answer search/notebook tool calls for extra
projects (`/api/…`). It carries **no per-request token**: any process on the
**same machine** can call it and read or modify any registered project's data.

This is a **deliberate, accepted trade-off** for a single-user, local-first
desktop tool — the same model as other localhost developer services (Ollama, LM
Studio, a local Qdrant dashboard). The bridge is **not reachable from the
network**: the `127.0.0.1:` prefix on the published port plus a Host-header
allowlist (which also defeats DNS-rebinding) keep it loopback-only; `/file/` is
path-traversal-guarded and serves non-PDF files as downloads (no same-origin
script execution); and no CORS headers are sent, so a cross-origin web page
cannot read responses.

Practical guidance: don't run BRAG on a shared/multi-user host if you don't trust
the other local users, and **do not remove the `127.0.0.1:` prefix** from the
published port (`docker-compose.yml` / `BRIDGE_HOST_PORT`) — that would expose
your documents and tools to the local network without authentication.

## Supported versions

Only the latest release receives security fixes.
