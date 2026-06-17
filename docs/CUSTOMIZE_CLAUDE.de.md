# Claude auf deine Forschung einstellen

**🇬🇧 [English](CUSTOMIZE_CLAUDE.md) | 🇩🇪 Deutsch**

Das Wirkungsvollste, was du nach der Installation tun kannst, ist, die Datei
**`wissensspeicher/CLAUDE.md`** auszufüllen. Sie wird von Claude automatisch gelesen (in
Claude-Desktop-Projekten und in Claude Code) und macht aus einem generischen
Assistenten einen, der dein Fachgebiet, deine Konventionen und deinen Korpus
kennt.

## Was in die CLAUDE.md gehört

| Abschnitt | Warum es zählt |
|---|---|
| Wer ich bin / meine Forschung | Claude passt Tiefe und Terminologie an dein Fach an |
| Ordner-Aufbau | Claude weiß, was Beleg ist (`sources/`) und was dein eigenes Denken (`wiki/`) |
| Wie gesucht wird | Die Anweisung „immer vor dem Antworten suchen, mehrere Formulierungen probieren" sorgt dafür, dass Antworten belegt sind statt erfunden |
| Zitierstil | Claude zitiert so, wie es deine Disziplin erwartet, mit Seitenzahlen |
| Konventionen | Sprache, Notiz-Benennung, alles, was du sonst jede Sitzung wiederholen müsstest |

**Faustregel:** Wenn du Claude zweimal dieselbe Sache korrigierst, gehört die
Korrektur in die CLAUDE.md.

## Was in die AGENTS.md gehört

`wissensspeicher/AGENTS.md` enthält **Zusatzregeln für autonomes Arbeiten** — wenn Claude
eigenständig agiert (lange Aufgaben, geplante Jobs, Agenten-Sitzungen) statt im
Gespräch mit dir. Typischer Inhalt: „nie Dateien in sources/ löschen",
„Änderungen vorschlagen statt massenhaft zu editieren", „zusammenfassen, was
geändert wurde". Kurz halten; alles aus der CLAUDE.md wird übernommen.

## Drei Beispiel-Einstiege

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

## In Claude Desktop nutzen

Lege in Claude Desktop ein **Projekt** für deine Forschung an und füge den
Inhalt deiner CLAUDE.md in die Projektanweisungen ein — dann startet jeder Chat
in diesem Projekt mit geladenem Kontext.
