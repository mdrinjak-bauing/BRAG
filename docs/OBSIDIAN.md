# Connect Obsidian

**🇬🇧 English | 🇩🇪 [Deutsch](OBSIDIAN.de.md)**

Your knowledge store is a folder of plain Markdown files — Obsidian is the
perfect way to read and write it.

## Part 1: Open the knowledge store in Obsidian

1. Install [Obsidian](https://obsidian.md) (free).
2. "Open folder as vault" → choose the `WissensWIKI/` folder inside your
   BRAG directory.
3. Done. Literature notes appear in `notes/`, your saved passages in
   `passages/`, your own thinking goes into `wiki/`.

## Part 2 (optional): Let Claude read and write your notes

The search index covers your **sources**. If you also want Claude Desktop to
read and edit your **notes and wiki pages**, add the community plugin
"MCP Tools":

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

Now Claude has two complementary tool sets: **search** over your sources
(this project) and **read/write** access to your notes (Obsidian MCP Tools).
That separation is deliberate — your own notes are never part of the search
index, so your thinking never comes back disguised as evidence.

> Obsidian must be running for the note tools to work. If they stop working
> after an Obsidian update, re-run "Install Server" in the MCP Tools settings.
