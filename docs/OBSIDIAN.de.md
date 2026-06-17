# Obsidian anbinden

**🇬🇧 [English](OBSIDIAN.md) | 🇩🇪 Deutsch**

Dein Wissensspeicher ist ein Ordner aus einfachen Markdown-Dateien — Obsidian ist der
ideale Weg, ihn zu lesen und zu beschreiben.

## Teil 1: Den Wissensspeicher in Obsidian öffnen

1. [Obsidian](https://obsidian.md) installieren (kostenlos).
2. „Ordner als Vault öffnen" → den Ordner `wissensspeicher/` innerhalb deines
   ASB-Verzeichnisses wählen.
3. Fertig. Literaturnotizen erscheinen in `notes/`, deine gespeicherten
   Passagen in `passages/`, dein eigenes Denken kommt nach `wiki/`.

## Teil 2 (optional): Claude deine Notizen lesen und schreiben lassen

Der Suchindex umfasst deine **Quellen**. Wenn Claude Desktop zusätzlich deine
**Notizen und Wiki-Seiten** lesen und bearbeiten soll, ergänze das
Community-Plugin „MCP Tools":

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

Jetzt hat Claude zwei sich ergänzende Werkzeugsätze: **Suche** über deine
Quellen (dieses Projekt) und **Lese-/Schreibzugriff** auf deine Notizen
(Obsidian MCP Tools). Diese Trennung ist gewollt — deine eigenen Notizen sind
nie Teil des Suchindex, sodass dein Denken nie als Beleg getarnt zurückkommt.

> Obsidian muss laufen, damit die Notiz-Werkzeuge funktionieren. Hören sie nach
> einem Obsidian-Update auf zu arbeiten, in den MCP-Tools-Einstellungen erneut
> „Install Server" ausführen.
