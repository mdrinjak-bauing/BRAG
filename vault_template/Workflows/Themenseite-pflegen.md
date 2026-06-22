# Workflow: Themenseite pflegen (Wissen verdichten)

**Auslöser:** „halt das fest" · „pflege das in die Themenseite" · „das gehört ins Wissen"

Ziel: eine gute Erkenntnis **einmal** sauber ablegen und beim nächsten Mal
**aktualisieren statt duplizieren** — so wächst das Wissen, statt zu zerfasern.

1. Bestimme das Thema → `Wissen/<Thema>.md`. Gibt es die Notiz noch nicht, lege sie an
   (Titel = Thema, `#tags` + `[[Wikilinks]]` zu verwandten Notizen).
2. `read_note('Wissen/<Thema>.md')` — was steht schon da?
3. **Oben** den Status/Kernstand aktualisieren (der gilt *jetzt*). Neue Belege,
   Details und Abwägungen als **datierten Abschnitt darunter** anhängen — alte
   Abschnitte bleiben (Historie). Widerspricht Neues dem Alten, markiere es offen
   („früher X, seit JJJJ-MM-TT eher Y"), statt still zu überschreiben.
4. Belege bleiben Belege: zitierfähige Quellen mit `save_passage` sichern (→
   `Quellenbelege/`, inkl. Link aufs Korpus-Dokument) — nicht den Quelltext in die
   Notiz kopieren.
5. `Wissen/Übersicht.md` ergänzen/aktualisieren (eine Zeile zum Thema) und in
   `Wissen/Verlauf.md` eine datierte Zeile anhängen.
