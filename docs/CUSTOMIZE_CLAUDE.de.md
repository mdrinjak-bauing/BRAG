# Claude auf deine Arbeit einstellen

**🇬🇧 [English](CUSTOMIZE_CLAUDE.md) | 🇩🇪 Deutsch**

Das Wirkungsvollste, was du nach der Installation tun kannst, ist, die Datei
**`WissensWIKI/CLAUDE.md`** auszufüllen. Sie macht aus einem generischen
Assistenten einen, der dein Fachgebiet, deine Konventionen und deinen Korpus
kennt — **egal ob du forschst oder in der Praxis arbeitest.** **Claude Code**
liest sie automatisch aus dem Ordner; **Claude Desktop liest sie _nicht_** von
allein — dort legst du ein Projekt an und kopierst ihren Inhalt in die
Projekt-Anweisungen (siehe [In Claude Desktop nutzen](#in-claude-desktop-nutzen)
unten).

> **Forschung oder Praxis?** BRAG funktioniert für beides. Eine Wissenschaftlerin
> will saubere Zitate und Disziplin-Konventionen; ein Bauleiter will den
> Überblick über Verträge, Normen und Leistungsverzeichnisse eines konkreten
> Projekts. Beide profitieren von **belegten** Antworten — es unterscheiden sich
> nur die Konventionen. Schreib in die CLAUDE.md einfach *deinen* Fall.

## Was in die CLAUDE.md gehört

| Abschnitt | Warum es zählt |
|---|---|
| Wer ich bin / woran ich arbeite | Claude passt Tiefe und Terminologie an dein Fach **oder dein Projekt** an |
| Ordner-Aufbau | Claude weiß, was Beleg ist (der Korpus: dein Projektordner außer `WissensWIKI/`) und was dein eigenes Denken (`WissensWIKI/Notizen/` — dein Notizbuch, nicht indexiert) |
| Wie gesucht wird | „Immer vor dem Antworten suchen, mehrere Formulierungen probieren" sorgt dafür, dass Antworten belegt sind statt erfunden |
| Beleg-/Zitierstil | Claude verweist so, wie es dein Umfeld erwartet — Disziplin-Zitat *oder* **Norm + Abschnitt**, **Vertrag + Paragraf**, **Dokument + Datum** |
| Projekt-/Mandatskontext (Praxis) | Mischt dein Korpus mehrere Projekte/Kunden? Sag Claude, immer per `meta_filter` auf das aktuelle Projekt einzugrenzen, damit keine fremden Vorgänge hineinrutschen |
| Konventionen | Sprache, Notiz-Benennung, alles, was du sonst jede Sitzung wiederholen müsstest |
| Routinen-Auslöser | Trag die Auslöser-Stichworte deiner wiederkehrenden Abläufe aus `WissensWIKI/Routinen/` hier ein, damit ein bloßes *„hol mich auf den Stand"* die Routine startet — ganz ohne Erklären |

**Faustregel:** Wenn du Claude zweimal dieselbe Sache korrigierst, gehört die
Korrektur in die CLAUDE.md.

**Routinen.** BRAG legt einen Ordner `WissensWIKI/Routinen/` mit Beispiel-Rezepten
an (kurze Markdown-Dateien, denen Claude folgt, wenn du sie beim Namen nennst).
Trag das Auslöser-Stichwort jeder Routine als Befehl in die CLAUDE.md ein — sobald
das in deiner Projekt-Anweisung steht, startet ein Stichwort die Routine. Eigene
ergänzt du mit einer `.md` in `Routinen/` und einer Auslöser-Zeile hier.

## Was in die AGENTS.md gehört

`WissensWIKI/AGENTS.md` enthält **Zusatzregeln für autonomes Arbeiten** — wenn
Claude eigenständig agiert (lange Aufgaben, geplante Jobs, Agenten-Sitzungen)
statt im Gespräch mit dir. Typischer Inhalt: „nie Dateien aus dem Korpus löschen
(Projektordner außer `WissensWIKI/`)", „Änderungen vorschlagen statt massenhaft
zu editieren", „zusammenfassen, was geändert wurde". Kurz halten; alles aus der
CLAUDE.md wird übernommen.

## Beispiel-Einstiege

### Aus der Forschung

**Geschichtsprofessorin:**
> Ich bin Professorin für Geschichte der Frühen Neuzeit. Mein Korpus enthält
> gescannte Primärquellen (16.–17. Jh.) und Sekundärliteratur. Zitate aus
> Primärquellen müssen wortgetreu sein, mit Archivsignatur und Folio.
> Zitierstil: Fußnoten, vollständiger Nachweis bei Erstnennung.

**Lehrstuhl Maschinenbau:**
> Unsere Gruppe arbeitet zur Ermüdung geschweißter Verbindungen. Der Korpus
> mischt deutsche Normen (DIN/EN/ISO), Dissertationen und englische
> Zeitschriftenaufsätze. Wenn ich nach Werten frage, prüfe immer Treffer mit
> `chunk_type="table"` und nenne die Prüfbedingungen. Zitierstil: (Autor Jahr).

**Doktorand, Baumanagement:**
> Ich schreibe meine Dissertation über KI-gestütztes Qualitätsmanagement für
> KMU. Suche auf Deutsch UND Englisch — die Hälfte meines Korpus ist englisch.
> Zitierstil: (vgl. Autor, Jahr, S. X). Ist ein Treffer für ein Kapitel
> nützlich, biete an, ihn als Passage unter dem Thema dieses Kapitels zu
> speichern.

### Aus der Praxis

**Tragwerksplaner (Statikbüro):**
> Ich bemesse Tragwerke nach Eurocode. Mein Korpus enthält Normen (DIN EN
> 1990–1999 mit nationalen Anhängen), bauaufsichtliche Zulassungen (abZ/aBG)
> und Herstellerunterlagen. Wenn ich nach einem Wert oder Beiwert frage, prüfe
> immer `chunk_type="table"`-Treffer und nenne **Norm + Abschnitt/Gleichung**,
> aus dem der Wert stammt. Erfinde nie einen Beiwert — steht er nicht im
> Treffer, sag das ausdrücklich.

**Bauleiter / Projektsteuerung:**
> Ich betreue mehrere Bauvorhaben gleichzeitig. Mein Korpus mischt Verträge,
> Leistungsverzeichnisse, VOB/B-Auszüge, Protokolle und Schriftverkehr — pro
> Projekt in einem eigenen Unterordner mit `_meta.txt` (`project: …`). Wenn ich
> ein Projekt nenne, grenze **immer** per `meta_filter` darauf ein, damit keine
> fremden Vorgänge hineinrutschen. Verweise mit **Dokument + Datum + Abschnitt**
> und antworte nüchtern und knapp.

**Nachtrags- / Claim-Management:**
> Ich prüfe Nachträge. Suche in Verträgen, Leistungsverzeichnissen und
> Schriftverkehr nach der vertraglichen Grundlage. Zitiere wörtlich mit
> **Dokument, Datum und Paragraf/Position**. Wenn ein Treffer eine
> Anspruchsgrundlage stützt, biete an, ihn als Passage unter dem Nachtragsthema
> zu speichern. Schließe nie aus „nicht in den Top-Treffern" auf „nicht im
> Vertrag" — sag, dass du es nicht belegen konntest.

## In Claude Desktop nutzen

Lege in Claude Desktop ein **Projekt** an — für dein Forschungsthema *oder* für
ein konkretes Bauvorhaben/Mandat — und füge den Inhalt deiner CLAUDE.md in die
Projektanweisungen ein; dann startet jeder Chat in diesem Projekt mit geladenem
Kontext. Betreust du mehrere Vorhaben, lohnt sich je ein eigenes Projekt mit
projektspezifischen Regeln (und der passende `meta_filter` in der CLAUDE.md).
