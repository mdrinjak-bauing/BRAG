# Welche Claude-Oberfläche? Chat, Cowork oder Code

**🇬🇧 [English](WHICH_CLAUDE.md) | 🇩🇪 Deutsch**

Anthropic bietet Claude in mehreren „Oberflächen" an, die auf denselben Modellen
laufen, sich aber darin unterscheiden, **für wen** sie gedacht sind und **wie viel
sie eigenständig erledigen**. Für BRAG lautet die kurze Antwort: **nimm den Chat in
Claude Desktop.** Warum — und wann die anderen sinnvoll sind. (Mit den offiziellen
Anthropic-Beschreibungen abgeglichen; Quellen am Ende. Stand Juni 2026.)

## Auf einen Blick

| Oberfläche | Was sie ist (offizielle Einordnung) | Läuft wo | Am besten für | Eignung für BRAG |
|---|---|---|---|---|
| **Claude (Chat)** | „Denken, Entwerfen und Analyse, du bei jedem Schritt dabei" — Zug um Zug | die Claude-Desktop-App; deine MCP-Server laufen auf deinem Rechner | belegte Recherche, Schreiben, Fragen an deinen Korpus | ✅ **BRAGs Zuhause** |
| **Claude Cowork** | „Gib ihm ein Ziel, und Claude arbeitet auf deinem Rechner, mit lokalen Dateien und Apps, und liefert ein fertiges Ergebnis" — autonom | eine **sandboxed Linux-VM in der Claude-Desktop-App** (Pro/Max/Team) | mehrstufige Datei-/App-Aufgaben im Hintergrund | ⚠️ nicht der BRAG-Weg |
| **Claude Code** | „Der Entwickler-Agent für Code, Git und Terminal — plant und führt aus, du prüfst die Diffs" | dein Terminal / IDE / Web | das System bauen & erweitern | 🛠️ um **BRAG zu verbessern** |

## Warum der Chat das richtige Zuhause für BRAG ist

BRAG ist in den **Chat von Claude Desktop** eingebunden — und genau dafür ist es
gebaut:

- Der Einrichtungs-Assistent trägt BRAG als **lokalen MCP-Server** ein (er schreibt
  einen `docker exec … brag.mcp_server`-Eintrag in die
  `claude_desktop_config.json`). Die Werkzeuge `search`, `list_sources`,
  `inspect_chunks`, … erscheinen dann **direkt im Chat**.
- Die **PDF-Deep-Links** in jeder Antwort öffnen im Browser an der zitierten Seite
  — ein Desktop-/Chat-Ablauf.
- Über **Projekte** in Claude Desktop fügst du den Inhalt deiner
  `WissensWIKI/CLAUDE.md` in die Projekt-Anweisungen ein (Claude Desktop liest die
  Datei nicht von allein), sodass jeder Chat mit deinem Fach und deiner Zitierweise startet.
- Du bleibst **in der Schleife**: fragen, die belegten Stellen lesen, nachschärfen.
  Genau dieser Recherche-Rhythmus ist BRAGs Idee — und er ist am
  token-sparsamsten (siehe unten).

## Was Cowork ist — und warum es nicht der BRAG-Weg ist

**Cowork** ist Anthropics **autonomer Agent für Wissensarbeit** (allgemein
verfügbar seit 9. April 2026), gebaut für Forschende, Analystinnen, Operations-,
Finanz- und Rechtsteams — „Menschen, die täglich mit Dokumenten und Dateien
arbeiten und ihre Zeit lieber in die Urteilsentscheidungen als in die Fleißarbeit
stecken". Du gibst ein Ziel vor, es arbeitet im Hintergrund und liefert ein
Ergebnis.

Entscheidend für BRAG: Cowork **läuft in einer sandboxed Linux-VM** auf deinem Mac
oder Windows-PC (Ubuntu, per Apple-Virtualization-Framework hardware-isoliert, mit
bubblewrap/seccomp-Sandbox). Es sieht nur den **Ordner, den du ausdrücklich
freigibst**, und ist auf **Remote-MCP-Connectors** aus einem Katalog ausgelegt —
nicht auf einen host-seitigen `docker exec`-Server wie den von BRAG. Community-
Anleitungen, lokale MCP-Server in Cowork zu bekommen, gibt es, aber das ist
bewusst nicht der Standardweg.

Also: Cowork ist großartig für „erledige diese ganze mehrstufige Aufgabe für mich"
— aber die **belegte Recherche im Chat**, die BRAG bietet, lebt im normalen
**Chat**. Verfügbar in den Tarifen Pro, Max und Team (Team-Admins können es
freischalten).

## Wofür Claude Code da ist

**Claude Code** ist der **Entwickler-Agent** — Terminal, Dateisystem, Git, und du
prüfst die Diffs. Es ist das richtige Werkzeug, um **BRAG zu bauen und zu
erweitern**: ein neues MCP-Werkzeug ergänzen, die Pipeline härten, einen Audit-Fix
einspielen. (Dieses Repository wird mit Claude Code entwickelt.) Es ist nicht die
Oberfläche für die tägliche Literaturrecherche. Eine Randnotiz zur Verwandtschaft:
Cowork lässt im Grunde Claude Codes Motor in seiner Sandbox-VM für Nicht-
Entwickler laufen.

## Token-/Kostenverbrauch (was die Rechnung wirklich treibt)

- **Chat + BRAG-Suche:** Eine Frage schickt nur die **top-K-Treffer** (standardmäßig
  15) an das Modell — schlank. Dein gesamter Korpus geht nie ans Modell, nur die
  passenden Ausschnitte. Eine Breitensuche schickt *bewusst* mehr.
- **Cowork:** Ein autonomer Lauf liest Dateien, plant und iteriert über viele
  Schritte — er verbraucht **deutlich mehr Tokens** als eine einzelne belegte
  Antwort, weil er eine ganze Aufgabe erledigt, nicht eine Frage beantwortet.
- **Claude Code:** verbraucht Tokens fürs Lesen und Ändern von Code; top zum
  Bauen, aber nicht der Weg für tägliches Lesen.

**Faustregel:** Um *Fragen aus deinem Korpus zu beantworten*, ist der Chat sowohl
die richtige Wahl **als auch** die sparsamste, weil das Retrieval den Kontext klein
hält.

## In einem Satz

**Chat = deine Wissensbasis nutzen · Code = ihre Werkzeuge bauen · Cowork = eine
ganze Aufgabe abgeben.** BRAG ist für das Erste gebaut.

---

*Quellen (offizielle Anthropic-Einordnung und Berichterstattung, Juni 2026):*
[Claude Cowork — Produktseite](https://www.anthropic.com/product/claude-cowork) ·
[Claude / Code / Cowork — welches wann](https://hatchworks.com/blog/claude/claude-vs-claude-code-vs-cowork/) ·
[Unterschied Claude Code und Cowork (Forte Labs)](https://fortelabs.com/blog/the-difference-between-claude-code-and-cowork/) ·
[Inside Claude Cowork: die lokale VM](https://pvieito.com/2026/01/inside-claude-cowork) ·
[Cowork GA & Enterprise-Features (9to5Mac)](https://9to5mac.com/2026/04/09/anthropic-scales-up-with-enterprise-features-for-claude-cowork-and-managed-agents/)
