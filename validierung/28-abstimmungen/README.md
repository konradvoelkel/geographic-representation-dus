# Validierung 28-abstimmungen

Erzeugt von `georep validate merge` am 2026-11-24; nicht von Hand ändern. Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).

- **Codebuch**: `codebuch.toml`, Version 2026-11-24.1; Einheit `document`, 5 Fragen.
- **Stichprobe**: 150 Einheiten aus Profil `duesseldorf`, geschichtet nach `schicht`, gewichtet mit N_h/n_h (`stichprobe.csv`, `stichprobe.json`).
- **Kodierer**: zwei KI-Kodierer, unabhängig voneinander und ohne die Ausgabe des geprüften Verfahrens; die 13 Uneinigkeiten entschied ein dritter Agent (Schlichtung). **Kein menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem stärkeren Modell, nicht mit Menschen.
- **Modelle**: Kodierer A `claude-opus-5-5`, Kodierer B `claude-opus-5-5`, Schlichtung `claude-opus-5-5`.
- **Datum**: 2026-11-24.

Übereinstimmung A–B je Frage; Stufe 3 verlangt α ≥ 0,80 (ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal):

| Frage | Skala | gestellt | gleich | Cohens κ | Krippendorffs α | genügt |
|---|---|---|---|---|---|---|
| `abschnitt` | binary | 150 | 150 von 150 (100,0 %) | 1,000 | 1,000 | ja |
| `ergebnis` | nominal | 132 | 129 von 132 (97,7 %) | 0,907 | 0,908 | ja |
| `form` | nominal | 131 | 128 von 129 (99,2 %) | 0,985 | 0,985 | ja |
| `stimmen` | open | 124 | 119 von 123 (96,7 %) | 0,961 | 0,961 | ja |
| `uebrige` | nominal | 124 | 122 von 123 (99,2 %) | 0,885 | 0,885 | ja |

## labels.csv

| Spalte | Inhalt |
|---|---|
| `id` | Schlüssel der Einheit (`stichprobe.csv` trägt seine Teile einzeln) |
| `frage` | die Frage aus dem Codebuch |
| `kodierer_a`, `kodierer_b` | die Antworten von A und B; leer, wo die Frage nicht gestellt war |
| `schlichtung` | die Antwort der Schlichtung; leer, wo A und B einig waren |
| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |
