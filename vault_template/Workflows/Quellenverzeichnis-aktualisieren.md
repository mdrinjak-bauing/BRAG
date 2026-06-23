# Workflow: Quellenverzeichnis aktualisieren

**Auslöser:** „aktualisier das Quellenverzeichnis" · „erstell die Quellenliste"

1. `list_sources` — alle indexierten Dokumente abrufen.
2. Baue ein nach Typ gruppiertes Verzeichnis (Autor, Jahr, Titel — soweit aus
   Metadaten/Dateinamen erkennbar).
3. `write_note('Wissen/Quellenverzeichnis.md', <verzeichnis>)` — wird datiert angehängt
   (eigene Notiz, nicht indexiert).
4. Nenne kurz, was seit dem letzten Stand neu hinzugekommen ist.
