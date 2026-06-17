# Rechtliche Hinweise

**🇬🇧 [English](LEGAL.md) | 🇩🇪 Deutsch**

> **Kein Rechtsrat.** Dieser Text fasst nur allgemeine Punkte zusammen (Stand
> Juni 2026) und ersetzt keine rechtliche Beratung. Die Rechtslage ändert sich
> und hängt von deinem Land, deinen Dokumenten und deinen Verträgen ab. Im
> Zweifel hole fachkundigen Rat ein.

## Gewährleistungsausschluss

Diese Software wird unter der [MIT-Lizenz](../LICENSE) „wie besehen" („as is")
bereitgestellt, **ohne jede Gewährleistung** und ohne Garantie für Eignung,
Fehlerfreiheit, Datenschutz oder Rechtskonformität. Die Nutzung erfolgt auf
eigenes Risiko und in eigener Verantwortung. Die Autoren und Mitwirkenden haften
nicht für Schäden, Datenverluste oder rechtliche Folgen aus der Nutzung.

## Datenschutz / Vertraulichkeit

Was deinen Rechner verlässt, hängt vom gewählten **Profil** ab:

- **Lokale Profile (Hybrid, Lokal):** Es verlässt **nichts** deinen Rechner —
  weder Dokumenttext noch Embeddings. Der Bedeutungs-Index wird ohnehin in jedem
  Profil lokal erzeugt.
- **Cloud-Profile (Gemini, OpenAI, Claude):** Zur Kontext-Erzeugung wird der
  **Textauszug jedes Abschnitts** an den jeweiligen Anbieter übermittelt — und
  bei aktivem **Vision-Pass** (standardmäßig an) zusätzlich die **gerenderten
  Bilder deiner Abbildungen**. Nicht übermittelt werden ganze Dateien, die
  Embeddings und deine späteren Chat-Fragen. Damit verlassen Inhalte deiner
  Dokumente deinen Rechner und unterliegen den Bedingungen des Anbieters. Den
  Bildversand kannst du mit `VISION_ENABLED=false` abschalten.

**Wichtig — kostenloser Gemini-Tarif (Standard):** Beim *kostenlosen* Tarif von
Google AI Studio kann Google die übermittelten Eingaben und Ausgaben zur
**Verbesserung seiner Produkte verwenden**, und sie können **von Menschen
geprüft** werden. Für vertrauliche, geheime oder personenbezogene Inhalte ist
der kostenlose Tarif daher **nicht geeignet** — nutze stattdessen ein **lokales
Profil** oder einen kostenpflichtigen Tarif (z. B. Google Cloud/Vertex AI), bei
dem Daten laut Anbieter nicht zum Training verwendet werden.

Zur Einordnung der anderen Cloud-Anbieter (Stand Juni 2026, ohne Gewähr —
maßgeblich sind stets die aktuellen Bedingungen des Anbieters):

- **OpenAI-API:** API-Daten werden standardmäßig **nicht** zum Training genutzt;
  kurze Aufbewahrung zur Missbrauchserkennung (typisch bis ~30 Tage).
- **Anthropic-API:** API-Daten werden **nicht** zum Training genutzt; kurze
  Aufbewahrung (standardmäßig 7 Tage). Für Geschäftskunden ist „Zero Data
  Retention" verfügbar.

**DSGVO:** Enthalten deine Dokumente personenbezogene Daten und nutzt du ein
Cloud-Profil, bist in der Regel **du** der datenschutzrechtlich Verantwortliche.
Prüfe dann eigenverantwortlich u. a. Rechtsgrundlage, Auftragsverarbeitung (AVV)
mit dem Anbieter und einen etwaigen Drittlandtransfer. Dieses Projekt stellt
keine AVV bereit und garantiert keine DSGVO-Konformität.

## Einsatz im beruflichen oder organisationalen Kontext

Wer BRAG beruflich einsetzt — besonders mit **personenbezogenen** oder
geschäftskritischen Daten — sollte das **vor** dem Einsatz mit den zuständigen
Stellen abstimmen: Datenschutzbeauftragte/r, IT-Sicherheit, ggf. Betriebs- oder
Personalrat und die Rechtsabteilung. Das ist kein Formalismus, sondern schützt
dich und deine Organisation.

Aus Sicht der Datensicherheit sind in diesem Kontext **lokale Profile klar zu
bevorzugen** (Hybrid/Lokal): Dokumenttexte und Bilder verlassen den Rechner
nicht, es entsteht kein Drittlandtransfer und keine Auftragsverarbeitung mit
externen Anbietern. Für vertrauliche oder personenbezogene Unterlagen ist das
der bedenkenlose Standardweg.

**IT-Abteilungen** können BRAG für den organisationalen Einsatz
**professionalisieren** — etwa durch: ausschließlich lokale Modelle
(LM Studio/Ollama oder ein selbst gehostetes Inferenz-Backend), zentral
verwaltete Konfiguration und Schlüssel, Zugriffs- und Netzwerkbeschränkungen,
Backup- und Löschkonzepte für Wissensspeicher und Index sowie eine dokumentierte Bewertung
(z. B. eine Datenschutz-Folgenabschätzung, sofern erforderlich). Die offene
Architektur (Docker, einfache Module, MCP) ist genau dafür ausgelegt.

## Urheberrecht und lizenzierte Werke

Du bist **allein dafür verantwortlich**, nur Dokumente einzulesen und zu
verarbeiten, an denen du die erforderlichen Rechte hast.

- **Eigene wissenschaftliche Analyse:** Für rechtmäßig zugängliche Werke können
  die EU-Schranken zum Text- und Data-Mining greifen (Art. 3 und 4 der
  DSM-Richtlinie; in Deutschland umgesetzt in **§ 60d UrhG** für die
  wissenschaftliche Forschung und **§ 44b UrhG** für allgemeines TDM). Sie
  erlauben unter Voraussetzungen eigene Vervielfältigungen zur automatisierten
  Analyse. Eine rein private Indexierung rechtmäßig erworbener Werke fällt häufig
  hierunter oder unter die Privatkopie (§ 53 UrhG).
- **Aber:** Diese Schranken sind **begrenzt.** Vertrags-/Lizenzbedingungen
  (z. B. von Verlagen, Datenbanken, E-Book-Anbietern) können die Nutzung
  einschränken, und beim allgemeinen TDM (§ 44b UrhG / Art. 4) dürfen
  Rechteinhaber einen **maschinenlesbaren Nutzungsvorbehalt (Opt-out)** erklären.
- **Cloud-Übermittlung beachten:** Der Versand urheberrechtlich geschützter
  Texte an einen Cloud-Anbieter ist eine **zusätzliche Vervielfältigung bzw.
  Übermittlung an Dritte** und nicht zwingend von einer TDM-Schranke gedeckt.
  Bei lizenzierten oder vertraulichen Werken im Zweifel ein **lokales Profil**
  verwenden, sodass nichts den Rechner verlässt.
- **Keine Schutzmaßnahmen umgehen:** Kopierschutz/DRM (z. B. bei E-Books) darf
  nicht umgangen werden.

## Anbieter-Bedingungen

Bei Nutzung eines Cloud-Profils musst du die jeweiligen Nutzungsbedingungen
einhalten — [Google](https://ai.google.dev/gemini-api/terms),
[OpenAI](https://openai.com/policies/) bzw.
[Anthropic](https://www.anthropic.com/legal). Dieses Projekt steht in keiner
Verbindung zu diesen Anbietern.

---

*Stand: Juni 2026. Angaben ohne Gewähr.*
