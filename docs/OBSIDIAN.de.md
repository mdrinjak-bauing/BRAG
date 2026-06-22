# Obsidian anbinden

**🇬🇧 [English](OBSIDIAN.md) | 🇩🇪 Deutsch**

Dein Wissensspeicher ist ein Ordner aus einfachen Markdown-Dateien. Obsidian ist
ein **optionaler**, schönerer Weg, ihn zu lesen und zu beschreiben — kein zweiter
Speicher, sondern nur eine Ansicht auf genau denselben `WissensWIKI/`-Ordner.
Bearbeitest oder löschst du eine Datei in Obsidian, ändert sie sich im Ordner
(und bei `Quellenbelege/` auch im Suchindex) mit. Nichts wird importiert oder kopiert.

## Teil 1: Den Wissensspeicher in Obsidian öffnen

1. [Obsidian](https://obsidian.md) installieren (kostenlos).
2. „Ordner als Vault öffnen" → den Ordner `WissensWIKI/` innerhalb deines
   Projektordners wählen.
3. Fertig. Du siehst deinen Arbeitsbereich: `Wissen/` (deine eigenen Notizen,
   beliebige freie Unterordner sowie eine automatisch erzeugte Literaturnotiz je
   Quelle), `Quellenbelege/` (gespeicherte Passagen), `Workflows/` (Aufgaben-Rezepte) sowie `CLAUDE.md` / `AGENTS.md`.

**Tipp — Wikilinks.** Schreib `[[Notizname]]` in eine Notiz, um auf die
gleichnamige `.md`-Datei zu verlinken; Obsidian macht daraus einen klickbaren
Graphen verwandter Konzepte, und Claude folgt den Links beim Lesen.

## Teil 2 (optional): Claude innerhalb von Obsidian agieren lassen

Claude kann dein Notizbuch **bereits** über die eingebauten BRAG-Werkzeuge
`list_notebook` / `read_note` / `write_note` lesen und schreiben — dafür brauchst
du Obsidian **nicht**. Dieser Teil ist nur, wenn Claude *zusätzlich* in Obsidians
eigener Oberfläche agieren soll (dessen Befehle, Vorlagen und Suche). Dafür
ergänzt du das Community-Plugin „MCP Tools":

1. In Obsidian: Einstellungen → Community-Plugins → Durchsuchen → **Local REST
   API** installieren und aktivieren.
2. **MCP Tools** (von Jack Steam) installieren und aktivieren. In den
   Einstellungen auf **„Install Server"** klicken — das lädt ein kleines
   Hilfsprogramm in deinen Wissensspeicher.
3. In den Einstellungen von **Local REST API** den **API-Schlüssel** kopieren.
4. Einen zweiten Eintrag in deine Claude-Desktop-Konfigurationsdatei ergänzen
   (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`,
   Windows: `%APPDATA%\Claude\claude_desktop_config.json`):

```json
"obsidian-mcp-tools": {
  "command": "<vollständiger Pfad zu deinem Wissensspeicher>/.obsidian/plugins/mcp-tools/bin/mcp-server",
  "env": { "OBSIDIAN_API_KEY": "<der kopierte Schlüssel>" }
}
```

5. Claude Desktop beenden und neu öffnen.

So oder so — eingebaute Werkzeuge oder Obsidian-Plugin — die Grenze bleibt: deine
eigenen Notizen sind nie Teil des Suchindex, sodass dein Denken nie als Beleg
getarnt zurückkommt. Die eine gewollte Ausnahme ist `Quellenbelege/`: die indexierst
du bewusst mit `save_passage`.

> Obsidian muss laufen, damit die Werkzeuge des Obsidian-Plugins funktionieren.
> Hören sie nach einem Obsidian-Update auf zu arbeiten, in den
> MCP-Tools-Einstellungen erneut „Install Server" ausführen.
