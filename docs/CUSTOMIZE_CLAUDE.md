# Customize Claude for your research

**🇬🇧 English | 🇩🇪 [Deutsch](CUSTOMIZE_CLAUDE.de.md)**

The single highest-impact thing you can do after installation is to fill in
**`wissensspeicher/CLAUDE.md`**. It is read automatically by Claude (in Claude Desktop
Projects and Claude Code) and turns a generic assistant into one that knows
your field, your conventions, and your corpus.

## What goes into CLAUDE.md

| Section | Why it matters |
|---|---|
| Who I am / my research | Claude tailors depth and terminology to your field |
| Knowledge-store layout | Claude knows what is evidence (`sources/`) vs. your own thinking (`wiki/`) |
| How to search | The instruction "always search before answering, try multiple phrasings" is what makes answers grounded instead of made up |
| Citation style | Claude cites the way your discipline expects, with page numbers |
| Conventions | Language, note naming, anything you'd otherwise repeat every session |

**Rule of thumb:** whenever you correct Claude twice about the same thing,
that correction belongs in CLAUDE.md.

## What goes into AGENTS.md

`wissensspeicher/AGENTS.md` holds **extra rules for autonomous work** — when Claude
operates on its own (long tasks, scheduled jobs, agent sessions) rather than
in a conversation with you. Typical content: "never delete files in
sources/", "propose changes instead of bulk-editing", "summarize what you
changed". Keep it short; it inherits everything from CLAUDE.md.

## Three example openings

**History professor:**
> I am a professor of early modern history. My corpus contains scanned
> primary sources (16th–17th c.) and secondary literature. Quotations from
> primary sources must be verbatim, with archive signature and folio.
> Citation style: footnotes, full reference on first mention.

**Mechanical engineering chair:**
> Our group works on fatigue of welded joints. The corpus mixes German
> standards (DIN/EN/ISO), dissertations and English journal papers. When I
> ask for values, always check `chunk_type="table"` hits and name the test
> conditions. Citation style: (Author Year).

**PhD student, construction management:**
> I am writing my dissertation on AI-assisted quality management for SMEs.
> Search in German AND English — half my corpus is English. Citation style:
> (cf. Author, Year, p. X). When a hit is useful for a chapter, offer to
> save it as a passage under that chapter's topic.

## Using it in Claude Desktop

Create a **Project** in Claude Desktop for your research and paste the
content of your CLAUDE.md into the project instructions — then every chat in
that project starts with your context loaded.
