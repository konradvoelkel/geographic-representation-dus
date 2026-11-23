# Validierung 18-einbettungen-nachbarn

Erzeugt von `georep validate merge` am 2026-11-24; nicht von Hand ändern. Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).

- **Codebuch**: `codebuch.toml`, Version 2026-11-23.1; Einheit `document_pair`, 1 Frage.
- **Stichprobe**: 383 Einheiten aus Profil `duesseldorf`, ungeschichtet, selbstgewichtend (`stichprobe.csv`, `stichprobe.json`).
- **Kodierer**: zwei KI-Kodierer, Modell `claude-opus-5-5`, unabhängig voneinander und ohne die Ausgabe des geprüften Verfahrens; die 23 Uneinigkeiten entschied ein dritter Agent (Schlichtung). **Kein menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem stärkeren Modell, nicht mit Menschen.
- **Datum**: 2026-11-24.

Übereinstimmung A–B je Frage; Stufe 3 verlangt α ≥ 0,80 (ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal):

| Frage | Skala | gestellt | gleich | Cohens κ | Krippendorffs α | genügt |
|---|---|---|---|---|---|---|
| `aehnlich` | ordinal | 383 | 360 von 383 (94,0 %) | 0,906 | 0,943 | ja |

## labels.csv

| Spalte | Inhalt |
|---|---|
| `id` | Schlüssel der Einheit (`stichprobe.csv` trägt seine Teile einzeln) |
| `frage` | die Frage aus dem Codebuch |
| `kodierer_a`, `kodierer_b` | die Antworten von A und B; leer, wo die Frage nicht gestellt war |
| `schlichtung` | die Antwort der Schlichtung; leer, wo A und B einig waren |
| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |
