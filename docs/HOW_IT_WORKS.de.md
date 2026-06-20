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

In dieser Box laufen zwei „Geräte" nebeneinander:

**1. Der App-Container** (`brag-app`) — der eigentliche Arbeiter. Du startest
ihn nie von Hand; in ihm stecken mehrere kleine Teilsysteme:

- **Der Watcher** — die Wache. Er schaut alle ~10 Sekunden in deinen
  `sources/`-Ordner: Ist etwas Neues dazugekommen? Wurde etwas umbenannt oder
  gelöscht? Je nachdem stößt er das Einlesen an oder räumt den Index auf. Du
  musst also nie etwas „importieren" — Datei hineinlegen genügt, der Watcher
  bemerkt es von selbst.
- **Die Einlese-Pipeline** — verarbeitet ein neu entdecktes Dokument: lesen,
  zerschneiden, mit Kontext anreichern, einbetten, ablegen (Details unten).
- **Die Suche** — beantwortet jede Frage von Claude (zwei Suchen + Reranker,
  siehe unten).
- **Die HTTP-Brücke** — ein winziger Webserver auf `localhost:8765`. Er sorgt
  dafür, dass die Links in den Antworten dein PDF im Browser genau auf der
  zitierten Seite öffnen.
- **Der MCP-Server** — die Sprechverbindung zu Claude Desktop. Immer wenn
  Claude sucht, läuft kurz ein Prozess in diesem Container an, holt die
  Ergebnisse und gibt sie zurück.

**2. Qdrant** (`brag-qdrant`) — eine *Suchdatenbank für Bedeutung*. Eine normale
Datenbank findet exakte Wörter; Qdrant findet Text, der etwas Ähnliches
*meint*, auch mit anderen Wörtern. Genau deshalb kannst du nach „Regeln für
Mehrkosten" fragen und eine Stelle bekommen, die „Nachtragsmanagement" sagt.
Läuft als zweite kleine Box neben der App.

**Claude Desktop** — deine Oberfläche, läuft ganz normal auf dem Rechner (nicht
in Docker). Du öffnest weder die App noch die Datenbank; du sprichst einfach mit
Claude, und Claude nutzt beides im Hintergrund über eine Verbindung namens MCP.

---

## Wo wird das auf meinem Rechner installiert?

Es gibt **zwei** Orte — und es hilft sehr, sie auseinanderzuhalten:

**1. Der Projektordner — der, den du selbst angelegt hast.** Als du die
ZIP-Datei von GitHub entpackt hast, ist der entpackte BRAG-Ordner entstanden —
genau dort, wo du entpackt hast (z. B. unter `~/` auf dem Mac oder
`C:\Users\<du>\` unter Windows; sein Name stammt aus der ZIP). Darin liegen: die
Setup-Dateien, die `docker-compose.yml`, deine Einstellungsdatei `.env` und
standardmäßig der `WissensWIKI/`-Ordner mit deinen Dokumenten. Diesen Ordner kannst du
sehen, sichern, verschieben — er gehört dir.

**2. Dockers eigener Speicher — den du nie direkt anfasst.** Beim ersten Start
lädt Docker den Programmcode und die KI-Modelle (zusammen ~3 GB) herunter und
legt sie in seinem eigenen, verwalteten Bereich ab — *nicht* in deinem
Projektordner. Dort lebt auch die Qdrant-Datenbank (als „benanntes Volume").
Das ist Absicht: So landet die Datenbank nie versehentlich in iCloud/OneDrive
(wo sie beschädigt würde), und die 3 GB Modelle müllen deinen Projektordner
nicht zu. Deinstallierst du Docker, verschwindet dieser Bereich wieder — dein
Projektordner und dein Wissensspeicher bleiben unberührt.

Kurz gesagt: **Deine Dateien liegen im Projektordner (sichtbar, deins). Das
laufende System und der Suchindex liegen in Docker (unsichtbar, automatisch
verwaltet).**

Willst du nachsehen, ob alles läuft, öffne im Projektordner ein Terminal und gib
`docker ps` ein — es sollten die beiden Boxen `brag-app` und `brag-qdrant`
auftauchen.

---

## Wo deine Sachen liegen

| Was | Wo | Hinweis |
|---|---|---|
| Deine Dokumente & Notizen | der Ordner `WissensWIKI/` auf deinem Rechner | einfache PDF-/Markdown-Dateien — gehören dir, sichern wie jeden Ordner |
| Der Suchindex (Qdrant) | in Docker, in einem verwalteten Speicherbereich | jederzeit aus deinem Wissensspeicher neu aufbaubar; nie in iCloud/OneDrive legen |
| Programmcode & KI-Modelle | im Docker-Image | einmal beim ersten Build geladen (~3 GB); fasst du nie an |
| Einstellungen & API-Schlüssel | die Datei `.env` im Projektordner | vom Setup-Assistenten geschrieben; der Schlüssel bleibt hier (nur für dich lesbar), dient nur der Authentifizierung deiner eigenen Anfragen beim gewählten Anbieter und wird nie an die Macher der App oder an Dritte gesendet |

Der wichtige Punkt: **deine Bibliothek (`sources/`) und dein Notizbuch (`wiki/`,
`notes/`) sind ganz normale Dateien, die dir gehören.** Die Datenbank ist nur
ein abgeleiteter Index — ginge er verloren, baut ihn das System aus deinen
Dateien neu auf.

---

## Was beim Ablegen eines Dokuments passiert (Einlesen)

Du legst ein PDF in `WissensWIKI/sources/`. Binnen Sekunden bemerkt die App es und
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

### Und was ist mit Abbildungen?

Abbildungen werden **angeschaut**: Beim Einlesen rendert das System jedes Bild
und schickt es an die (multimodale) Text-KI, die in ein, zwei ehrlichen Sätzen
beschreibt, *was* zu sehen ist — Diagrammtyp, Hauptelemente, lesbare Achsen oder
Beschriftungen. Diese Beschreibung wird mit eingebettet, sodass du eine
Abbildung über ihren **Inhalt** findest, nicht nur über ihre Bildunterschrift.

Damit nichts erfunden wird, ist der Auftrag bewusst nüchtern: nur beschreiben,
was klar erkennbar ist, unlesbaren Text nicht raten, keine Zahlen erfinden.

Dieser **Vision-Pass ist standardmäßig aktiv** und funktioniert mit jedem
multimodalen Modell — alle Cloud-Voreinstellungen (Gemini, OpenAI, Claude)
können es. Im lokalen Profil brauchst du ein Vision-Modell; fehlt eines (oder
hat eine Abbildung kein Bild), fällt das System automatisch auf den sicheren Weg
„nur Bildunterschrift + Kapitel" zurück. Abschalten lässt sich der Vision-Pass
mit `VISION_ENABLED=false` in der `.env` (spart Kosten und Zeit).

> ⚠️ Bei einem Cloud-Profil wird dabei auch das **Bild** an den Anbieter
> übermittelt. Für vertrauliche oder lizenzierte Abbildungen ein lokales Profil
> oder `VISION_ENABLED=false` nutzen (siehe [LEGAL.de.md](LEGAL.de.md)).

Ein kurzes Paper dauert 1–3 Minuten, ein Buch länger. Du wartest nicht — es
passiert im Hintergrund, und eine gelöschte Datei wird automatisch aus dem Index
entfernt.

---

## Was beim Fragen passiert (Suche)

Du fragst Claude etwas. Hinter den Kulissen:

1. **Zwei Suchen gleichzeitig.** Deine Frage läuft durch *beide* Suchen —
   Bedeutung und Stichwort. Jede liefert ihre besten ~80 Kandidaten.

2. **Zusammenführen.** Die zwei Kandidatenlisten werden zu einer verschmolzen
   (ein Schritt namens RRF) — Passagen, die beide Verfahren mochten, steigen
   nach oben. Etwa 40 bleiben übrig (Standard — einstellbar, siehe unten).

3. **Neu sortieren — der Präzisionsschritt.** Eine zweite, gründlichere KI (der
   „Reranker") liest deine echte Frage *zusammen mit* jeder dieser ~40 Passagen
   und ordnet sie danach, wie gut sie wirklich antworten. Das ist der
   Unterschied zwischen „enthält die Wörter" und „beantwortet die Frage".
   Der Reranker läuft **lokal auf deiner CPU** und ist der teuerste Teil einer
   Suche — wie viele Passagen er bewertet (oder ob überhaupt) ist daher eine
   Einstellung (`RERANK_PROFILE`: `off` / `eco` / `balanced` / `full`): auf
   schwachen Rechnern `eco` (Standard) oder `off`, auf starken `full`.

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

Siehe auch: [Architektur-Diagramm & Voreinstellungen](ARCHITECTURE.de.md) ·
[Backend-Profile](PROFILES.de.md)
