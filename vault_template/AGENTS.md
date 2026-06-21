# Rules for autonomous agents

All instructions in [CLAUDE.md](CLAUDE.md) apply. In addition, when working
autonomously (long tasks, scheduled runs, agent sessions):

- Never delete or move files in the project folder (the searchable corpus) without asking first.
- Never bulk-edit files in `WissensWIKI/Notizen/` or `WissensWIKI/Passagen/` — propose changes instead.
- Long indexing runs: one at a time, never in parallel.
- When a task finishes, summarize what was changed and where.
