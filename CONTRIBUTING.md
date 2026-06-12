# Contributing

Thanks for your interest! This project is young and small — contributions of
all sizes are welcome.

## Reporting problems

Open a GitHub issue with: your OS, the profile you use (cloud/hybrid/local),
what you did, what happened, and the relevant lines from
`docker compose logs app`.

## Code contributions

- Keep the target audience in mind: **non-developers**. Every error a user can
  hit needs a plain-language message that says what to do next.
- Python code and comments in English. No hardcoded paths, no user-specific
  values — everything configurable via `.env` (see `asb/config.py`).
- Don't store zero vectors, don't swallow ingest errors silently — failed
  chunks go to the failed-chunks log.
- Before a PR: `python -m compileall asb` must pass, and
  `docker compose build` must succeed.

## Scope

The project intentionally stays small (one container + Qdrant, Claude Desktop
as the UI). Features that need additional services or a web UI are probably
out of scope — open an issue to discuss before building.
