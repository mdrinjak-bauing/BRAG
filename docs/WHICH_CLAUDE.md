# Which Claude surface? Chat, Cowork, or Code

**🇬🇧 English | 🇩🇪 [Deutsch](WHICH_CLAUDE.de.md)**

Anthropic ships Claude in several "surfaces" that run on the same models but
differ in **who they're for** and **how much they do on their own**. For ASB the
short answer is: **use Claude Desktop's chat.** Here is why — and when the others
make sense. (Reconciled with Anthropic's official descriptions; sources at the
bottom. As of June 2026.)

## At a glance

| Surface | What it is (official framing) | Runs where | Best for | Fit for ASB |
|---|---|---|---|---|
| **Claude (Chat)** | "Thinking, drafting and analysis with you in the loop on every step" — turn by turn | the Claude Desktop app; your MCP servers run on your machine | grounded research, writing, Q&A over your corpus | ✅ **ASB's home** |
| **Claude Cowork** | "Give it a goal and Claude works on your computer, local files and applications to return a finished deliverable" — autonomous | a **sandboxed Linux VM inside the Claude Desktop app** (Pro/Max/Team) | multi-step file/app tasks done in the background | ⚠️ not the ASB driver |
| **Claude Code** | "The developer agent for codebases, git and the terminal — it plans and executes, you review the diffs" | your terminal / IDE / web | building & extending the system | 🛠️ use it to **improve ASB** |

## Why Chat is the right home for ASB

ASB is wired into **Claude Desktop's chat**, and that is the surface it was built
for:

- The setup wizard registers ASB as a **local MCP server** (it writes a
  `docker exec … asb.mcp_server` entry into `claude_desktop_config.json`). The
  `search`, `list_sources`, `inspect_chunks`, … tools then appear **directly in
  chat**.
- The **PDF deep-links** in every answer open in your browser at the cited page —
  a desktop/chat workflow.
- Claude Desktop **Projects** let you load your `wissensspeicher/CLAUDE.md` instructions, so
  every chat starts grounded in your field and your citation style.
- It keeps **you in the loop**: ask, read the cited passages, refine. That is
  exactly the research rhythm ASB is designed around — and it is the most
  token-economical (see below).

## What Cowork is — and why it isn't the ASB driver

**Cowork** is Anthropic's **autonomous agent for knowledge work** (generally
available since 9 April 2026), built for researchers, analysts, operations,
finance and legal teams — "people who work with documents and files every day and
would rather spend their time on the judgment calls than the assembly." You give
it a goal and it works in the background to produce a deliverable.

Crucially for ASB, Cowork **runs inside a sandboxed Linux VM** on your Mac or
Windows PC (Ubuntu, hardware-isolated via the Apple Virtualization Framework with
a bubblewrap/seccomp sandbox). It only sees the **folder you explicitly share**
with it, and it is oriented to **remote MCP connectors** from a catalogue — not
to a host-side `docker exec` stdio server like ASB's. Community guides for
getting local MCP servers into Cowork exist, but it is deliberately not the
default path.

So: Cowork is excellent for "go do this whole multi-step task for me," but the
**grounded, cited research chat** that ASB provides lives in regular **Chat**.
Available on Pro, Max and Team plans (Team admins can toggle it).

## What Claude Code is for

**Claude Code** is the **developer agent** — terminal, file system, git, and you
review the diffs. It is the right tool to **build and extend ASB**: add a new MCP
tool, harden the pipeline, run an audit fix. (This very repository is developed
with Claude Code.) It is not the surface for everyday literature research. Fun
fact that shows the lineage: Cowork essentially runs Claude Code's engine inside
its sandbox VM for non-developers.

## Token / cost usage (what actually drives the bill)

- **Chat + ASB search:** a question sends only the **top-K retrieved passages**
  (15 by default) to the model — lean. Your whole corpus never goes to the model;
  only the matched snippets do. A broad search sends more *on purpose*.
- **Cowork:** an autonomous run reads files, plans and iterates over many steps,
  so it can consume **far more tokens** than a single grounded answer — it's
  doing a whole task, not answering one question.
- **Claude Code:** spends tokens reading and editing code; great value for
  building, but not how you'd want to do daily reading.

**Rule of thumb:** for *answering questions from your corpus*, Chat is both the
right fit **and** the most economical, because retrieval keeps the context small.

## In one line

**Chat = use your knowledge base · Code = build its tooling · Cowork = hand off a
whole task.** ASB is built for the first.

---

*Sources (official Anthropic framing and reporting, June 2026):*
[Claude Cowork — product page](https://www.anthropic.com/product/claude-cowork) ·
[Claude / Code / Cowork — which to use](https://hatchworks.com/blog/claude/claude-vs-claude-code-vs-cowork/) ·
[The difference between Claude Code and Cowork (Forte Labs)](https://fortelabs.com/blog/the-difference-between-claude-code-and-cowork/) ·
[Inside Claude Cowork: how the local VM works](https://pvieito.com/2026/01/inside-claude-cowork) ·
[Cowork GA & enterprise features (9to5Mac)](https://9to5mac.com/2026/04/09/anthropic-scales-up-with-enterprise-features-for-claude-cowork-and-managed-agents/)
