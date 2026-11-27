# Validierung 14-vorgaenge-3-f4

Erzeugt von `georep validate merge` am 2026-11-27; nicht von Hand ändern. Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).

- **Codebuch**: `codebuch.toml`, Version 2026-11-27.1; Einheit `pair_with_span`, 3 Fragen.
- **Stichprobe**: 50 Einheiten aus Profil `duesseldorf`, geschichtet nach `quelle`, gewichtet mit N_h/n_h (`stichprobe.csv`, `stichprobe.json`).
- **Kodierer**: zwei KI-Kodierer, unabhängig voneinander und ohne die Ausgabe des geprüften Verfahrens; die eine Uneinigkeit entschied ein dritter Agent (Schlichtung). **Kein menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem stärkeren Modell, nicht mit Menschen.
- **Modelle**: Kodierer A `claude-opus-5-5`, Kodierer B `claude-sonnet-5-5`, Schlichtung `claude-opus-5-5`.
- **Datum**: 2026-11-27.

Übereinstimmung A–B je Frage; Stufe 3 verlangt α ≥ 0,80 (ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal):

| Frage | Skala | gestellt | gleich | Cohens κ | Krippendorffs α | genügt |
|---|---|---|---|---|---|---|
| `nummer_gemeint` | nominal | 50 | 50 von 50 (100,0 %) | 1,000 | 1,000 | ja |
| `selbe_sache` | nominal | 50 | 50 von 50 (100,0 %) | nicht definiert | nicht definiert | ja (volle Einigkeit, α nicht definiert) |
| `beziehung` | nominal | 50 | 49 von 50 (98,0 %) | 0,960 | 0,961 | ja |

## labels.csv

| Spalte | Inhalt |
|---|---|
| `id` | Schlüssel der Einheit (`stichprobe.csv` trägt seine Teile einzeln) |
| `frage` | die Frage aus dem Codebuch |
| `kodierer_a`, `kodierer_b` | die Antworten von A und B; leer, wo die Frage nicht gestellt war |
| `schlichtung` | die Antwort der Schlichtung; leer, wo A und B einig waren |
| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |
