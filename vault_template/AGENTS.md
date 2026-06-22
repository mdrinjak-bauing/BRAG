# Rules for code agents (Claude Code & autonomous runs)

These rules apply ONLY to **code agents** — Claude Code or another agent working
autonomously on this knowledge store (long tasks, scheduled runs). **Claude Desktop
and LM Studio chat do not read this file** (only Claude Code does), so it doesn't
affect normal chatting — it's a guardrail for unattended/code work.

All instructions in [CLAUDE.md](CLAUDE.md) apply. In addition:

- Never delete or move files in the project folder (the searchable corpus) without asking first.
- Never bulk-edit files in `WissensWIKI/Wissen/` or `WissensWIKI/Quellenbelege/` — propose changes instead.
- Long indexing runs: one at a time, never in parallel.
- When a task finishes, summarize what was changed and where.
