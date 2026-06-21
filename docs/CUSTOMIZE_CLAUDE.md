# Customize Claude for your work

**🇬🇧 English | 🇩🇪 [Deutsch](CUSTOMIZE_CLAUDE.de.md)**

The single highest-impact thing you can do after installation is to fill in
**`WissensWIKI/CLAUDE.md`**. It is read automatically by Claude (in Claude
Desktop Projects and Claude Code) and turns a generic assistant into one that
knows your field, your conventions, and your corpus — **whether you do research
or work in practice.**

> **Research or practice?** BRAG works for both. A scholar wants clean citations
> and discipline conventions; a site manager wants to stay on top of the
> contracts, standards and bills of quantities of one specific project. Both
> benefit from **grounded** answers — only the conventions differ. Just describe
> *your* case in CLAUDE.md.

## What goes into CLAUDE.md

| Section | Why it matters |
|---|---|
| Who I am / what I work on | Claude tailors depth and terminology to your field **or your project** |
| Knowledge-store layout | Claude knows what is evidence (the corpus: your project folder except `WissensWIKI/`) vs. your own thinking (`WissensWIKI/Notizen/`, your notebook — not indexed) |
| How to search | "Always search before answering, try multiple phrasings" is what makes answers grounded instead of made up |
| Reference / citation style | Claude cites the way your context expects — a discipline citation *or* **standard + clause**, **contract + section**, **document + date** |
| Project / matter context (practice) | If your corpus mixes several projects/clients, tell Claude to always scope to the current project via `meta_filter` so unrelated matters don't leak in |
| Conventions | Language, note naming, anything you'd otherwise repeat every session |

**Rule of thumb:** whenever you correct Claude twice about the same thing,
that correction belongs in CLAUDE.md.

## What goes into AGENTS.md

`WissensWIKI/AGENTS.md` holds **extra rules for autonomous work** — when Claude
operates on its own (long tasks, scheduled jobs, agent sessions) rather than
in a conversation with you. Typical content: "never delete files from the
corpus (the project folder except `WissensWIKI/`)", "propose changes instead of
bulk-editing", "summarize what you changed". Keep it short; it inherits
everything from CLAUDE.md.

## Example openings

### From research

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

### From practice

**Structural engineer (design office):**
> I design structures to the Eurocodes. My corpus holds standards (DIN EN
> 1990–1999 with national annexes), technical approvals and manufacturer
> documents. When I ask for a value or a factor, always check
> `chunk_type="table"` hits and name the **standard + clause/equation** the
> value comes from. Never invent a factor — if it is not in the hit, say so
> explicitly.

**Site / project manager:**
> I run several construction projects at once. My corpus mixes contracts,
> bills of quantities, standard-form clauses, minutes and correspondence — one
> sub-folder per project with a `_meta.txt` (`project: …`). When I name a
> project, **always** restrict to it via `meta_filter` so no unrelated matters
> bleed in. Reference with **document + date + section**, and answer concisely.

**Variations / claims management:**
> I assess variation claims. Search contracts, bills of quantities and
> correspondence for the contractual basis. Quote verbatim with **document,
> date and clause/item**. When a hit supports a basis of claim, offer to save
> it as a passage under that variation's topic. Never conclude "not in the
> contract" from "not in the top hits" — say you could not substantiate it.

## Using it in Claude Desktop

Create a **Project** in Claude Desktop — for your research topic *or* for a
specific construction project / matter — and paste the content of your CLAUDE.md
into the project instructions; then every chat in that project starts with your
context loaded. If you handle several jobs, a separate Project per job (each with
its project-specific rules and `meta_filter`) is worth it.
