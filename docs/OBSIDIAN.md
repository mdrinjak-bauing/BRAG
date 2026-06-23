# Connect Obsidian

**🇬🇧 English | 🇩🇪 [Deutsch](OBSIDIAN.de.md)**

Your knowledge store is a folder of plain Markdown files. Obsidian is an
**optional** nicer way to read and write it — not a second copy, just a view
onto the exact same `WissensWIKI/` folder. Edit or delete a file in Obsidian and
it changes in the folder (and, for `Quellenbelege/`, in the search index) too. Nothing
is imported or copied.

## Part 1: Open the knowledge store in Obsidian

1. Install [Obsidian](https://obsidian.md) (free).
2. "Open folder as vault" → choose the `WissensWIKI/` folder inside your
   project folder.
3. Done. You'll see your workspace: `Wissen/` (your own notes, any free
   subfolders, plus an auto-generated literature note per source), `Quellenbelege/`
   (passages you saved), `Workflows/` (task
   recipes), and `CLAUDE.md` / `AGENTS.md`.

**Tip — wikilinks.** Write `[[NoteName]]` inside a note to link to the same-named
`.md` file; Obsidian turns these into a clickable graph of related concepts, and
Claude follows the links as it reads.

## Part 2 (optional): Let Claude act inside Obsidian

Claude can **already** read and write your notebook through BRAG's built-in
`list_notebook` / `read_note` / `write_note` tools — you do **not** need Obsidian
for that. This part is only if you *also* want Claude to act inside Obsidian's own
interface (its commands, templates and search). For that, add the community
plugin "MCP Tools":

1. In Obsidian: Settings → Community plugins → Browse → install and enable
   **Local REST API**.
2. Install and enable **MCP Tools** (by Jack Steam). In its settings, click
   **"Install Server"** — this downloads a small helper program into your
   knowledge store.
3. In the **Local REST API** settings, copy the **API key**.
4. Add a second entry to your Claude Desktop config file
   (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`,
   Windows: `%APPDATA%\Claude\claude_desktop_config.json`):

```json
"obsidian-mcp-tools": {
  "command": "<full path to your knowledge store>/.obsidian/plugins/mcp-tools/bin/mcp-server",
  "env": { "OBSIDIAN_API_KEY": "<the key you copied>" }
}
```

5. Quit and reopen Claude Desktop.

Either way — built-in tools or the Obsidian plugin — the boundary holds: your own
notes are never part of the search index, so your thinking never comes back
disguised as evidence. The one deliberate exception is `Quellenbelege/`: you index
those on purpose with `save_passage`.

> Obsidian must be running for the Obsidian-plugin tools to work. If they stop
> working after an Obsidian update, re-run "Install Server" in the MCP Tools
> settings.
