# So funktioniert's — in einfachen Worten

**🇬🇧 [English](HOW_IT_WORKS.md) | 🇩🇪 Deutsch**

Kein Informatik-Wissen nötig. Diese Seite erklärt, was auf deinem Rechner
passiert, wo deine Daten liegen und wie aus einer Frage eine belegte Antwort wird.

---

## Die Bausteine — und wozu jeder da ist

**Docker** — stell es dir wie ein versiegeltes Gerät vor. Statt Python,
Datenbanken und KI-Bibliotheken von Hand zu installieren (und mit
Versionskonflikten zu kämpfen), startet Docker eine fertige Box, die alles
schon enthält — auf jedem Rechner identisch. Du installierst einmal Docker; den
Rest startet es. Deshalb ist die Einrichtung „doppelklicken und drei Fragen
beantworten" statt einer Seite voller Befehle.

**Der App-Container** — der Arbeiter in dieser Box. Er überwacht deinen Ordner,
liest Dokumente und beantwortet Suchen.

**Qdrant** — eine *Suchdatenbank für Bedeutung*. Eine normale Datenbank findet
exakte Wörter; Qdrant findet Text, der etwas Ähnliches *meint*, auch mit anderen
Wörtern. Genau deshalb kannst du nach „Regeln für Mehrkosten" fragen und eine
Stelle bekommen, die „Nachtragsmanagement" sagt. Läuft als zweite kleine Box
neben der App.

**Claude Desktop** — deine Oberfläche. Du öffnest weder die App noch die
Datenbank; du sprichst einfach mit Claude, und Claude nutzt beides im
Hintergrund über eine Verbindung namens MCP.

---

## Wo deine Sachen liegen

| Was | Wo | Hinweis |
|---|---|---|
| Deine Dokumente & Notizen | der Ordner `vault/` auf deinem Rechner | einfache PDF-/Markdown-Dateien — gehören dir, sichern wie jeden Ordner |
| Der Suchindex (Qdrant) | in Docker, in einem verwalteten Speicherbereich | jederzeit aus dem Vault neu aufbaubar; nie in iCloud/OneDrive legen |
| Programmcode & KI-Modelle | im Docker-Image | einmal beim ersten Build geladen (~3 GB); fasst du nie an |
| Einstellungen & API-Schlüssel | die Datei `.env` im Projektordner | vom Setup-Assistenten geschrieben; nie teilen |

Der wichtige Punkt: **deine Bibliothek (`sources/`) und dein Notizbuch (`wiki/`,
`notes/`) sind ganz normale Dateien, die dir gehören.** Die Datenbank ist nur
ein abgeleiteter Index — ginge er verloren, baut ihn das System aus deinen
Dateien neu auf.

---

## Was beim Ablegen eines Dokuments passiert (Einlesen)

Du legst ein PDF in `vault/sources/`. Binnen Sekunden bemerkt die App es und
durchläuft fünf Schritte:

1. **Das Layout lesen — „Docling".** Docling ist das Werkzeug, das *die Seite
   versteht*: es trennt Überschriften, Absätze, Tabellen und Abbildungen und
   merkt sich, von welcher Seite jedes Stück stammt. (Dieses Seiten-Gedächtnis
   ist es, was später jede Antwort auf die genaue Seite verlinken lässt.)

2. **In Stücke schneiden.** Ein ganzes Buch ist zu groß, um als Klumpen
   durchsucht zu werden — also wird es in handliche Passagen geschnitten.
   Tabellen bleiben ganz (mit wiederholter Kopfzeile, wenn sie lang sind), damit
   Zahlen nicht auseinandergerissen werden.

3. **Kontext ergänzen — „Contextual Retrieval".** Das ist der Qualitäts-Trick.
   Für sich genommen ist eine Passage wie *„die Quote lag bei 12 %"* nutzlos —
   12 % wovon? Also schreibt die KI zu jedem Stück ein, zwei Sätze Kontext
   („Dies stammt aus dem Kapitel zu Nacharbeitskosten und behandelt…") und legt
   sie daneben ab. Erst dann findet die Suche es. Dieser eine Schritt ist der
   größte Grund für gute Antworten.

4. **Zwei „Fingerabdrücke" erzeugen.** Jede Passage bekommt einen
   *Bedeutungs-Fingerabdruck* (für die Ähnlichkeits-Suche) und einen
   *Stichwort-Fingerabdruck* (für exakte Begriffe wie GEG oder § 71). Beides zu
   haben ist der Grund, warum das System Dinge findet — egal ob du das genaue
   Wort erinnerst oder nur die Idee.

5. **In Qdrant ablegen** + eine kurze Literaturnotiz in `notes/` schreiben.

Ein kurzes Paper dauert 1–3 Minuten, ein Buch länger. Du wartest nicht — es
passiert im Hintergrund, und eine gelöschte Datei wird automatisch aus dem Index
entfernt.

---

## Was beim Fragen passiert (Suche)

Du fragst Claude etwas. Hinter den Kulissen:

1. **Zwei Suchen gleichzeitig.** Deine Frage läuft durch *beide* Suchen —
   Bedeutung und Stichwort. Jede liefert ihre besten ~150 Kandidaten.

2. **Zusammenführen.** Die zwei Kandidatenlisten werden zu einer verschmolzen
   (ein Schritt namens RRF) — Passagen, die beide Verfahren mochten, steigen
   nach oben. Etwa 80 bleiben übrig.

3. **Neu sortieren — der Präzisionsschritt.** Eine zweite, gründlichere KI (der
   „Reranker") liest deine echte Frage *zusammen mit* jeder dieser 80 Passagen
   und ordnet sie danach, wie gut sie wirklich antworten. Das ist der
   Unterschied zwischen „enthält die Wörter" und „beantwortet die Frage".

4. **Kürzen und durchmischen.** Die besten Treffer bleiben (standardmäßig 15,
   höchstens 3 aus einer einzelnen Quelle, damit ein Buch nicht alles
   verdrängt). Diese „wie viele behalten"-Zahl ist das **top-K**.

5. **Antworten.** Claude liest diese Passagen und schreibt eine Antwort — jede
   Quelle mit Seite belegt und einem Link, der das PDF genau dort öffnet.

Das System zeigt dir, *warum* jeder Treffer gewählt wurde (ein Relevanz-Wert),
statt schwache Treffer zu verstecken — du behältst die Kontrolle, was du glaubst.

---

## In einem Satz

Du hältst einfache Dateien in einem Ordner; die App macht daraus still einen
bedeutungs-bewussten Index; und Claude beantwortet deine Fragen aus *deinen*
Dokumenten, mit seitengenauen Belegen — alles auf deinem eigenen Rechner.

Siehe auch: [Architektur-Diagramm & Voreinstellungen](ARCHITECTURE.md) ·
[Backend-Profile](PROFILES.md)
