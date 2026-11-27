# Validierung 12-kennungen-2-f4

Erzeugt von `georep validate merge` am 2026-11-27; nicht von Hand ändern. Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).

- **Codebuch**: `codebuch.toml`, Version 2026-11-23.2; Einheit `span`, 4 Fragen.
- **Stichprobe**: 360 Einheiten aus Profil `duesseldorf`, geschichtet nach `schicht`, gewichtet mit N_h/n_h (`stichprobe.csv`, `stichprobe.json`).
- **Kodierer**: zwei KI-Kodierer, unabhängig voneinander und ohne die Ausgabe des geprüften Verfahrens; die 24 Uneinigkeiten entschied ein dritter Agent (Schlichtung); davon 1 Einheit: Auswerter nach dem Codebuch .2, Runde 2. **Kein menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem stärkeren Modell, nicht mit Menschen.
- **Modelle**: Kodierer A `claude-opus-5-5`, Kodierer B `claude-opus-5-5`, Schlichtung `claude-opus-5-5`.
- **Datum**: 2026-11-27.

Übereinstimmung A–B je Frage; Stufe 3 verlangt α ≥ 0,80 (ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal):

| Frage | Skala | gestellt | gleich | Cohens κ | Krippendorffs α | genügt |
|---|---|---|---|---|---|---|
| `art` | nominal | 360 | 360 von 360 (100,0 %) | 1,000 | 1,000 | ja |
| `grenzen` | nominal | 357 | 354 von 357 (99,2 %) | 0,939 | 0,939 | ja |
| `grenzen_korrigiert` | open | 28 | 24 von 25 (96,0 %) | 0,958 | 0,959 | ja |
| `norm` | open | 357 | 340 von 357 (95,2 %) | 0,952 | 0,952 | ja |

## labels.csv

| Spalte | Inhalt |
|---|---|
| `id` | Schlüssel der Einheit (`stichprobe.csv` trägt seine Teile einzeln) |
| `frage` | die Frage aus dem Codebuch |
| `kodierer_a`, `kodierer_b` | die Antworten von A und B; leer, wo die Frage nicht gestellt war |
| `schlichtung` | die Antwort der Schlichtung; leer, wo A und B einig waren |
| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |
