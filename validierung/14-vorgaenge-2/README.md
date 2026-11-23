# Validierung 14-vorgaenge-2

Erzeugt von `georep validate merge` am 2026-11-23; nicht von Hand ändern. Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).

- **Codebuch**: `codebuch.toml`, Version 2026-11-23.2; Einheit `pair_with_span`, 3 Fragen.
- **Stichprobe**: 100 Einheiten aus Profil `mehrere: duesseldorf, duesseldorf-2014, duesseldorf-2025, moenchengladbach`, geschichtet nach `schicht`, gewichtet mit N_h/n_h (`stichprobe.csv`, `stichprobe.json`).
- **Kodierer**: zwei KI-Kodierer, Modell `claude-opus-5-5`, unabhängig voneinander und ohne die Ausgabe des geprüften Verfahrens; die 8 Uneinigkeiten entschied ein dritter Agent (Schlichtung). **Kein menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem stärkeren Modell, nicht mit Menschen.
- **Datum**: 2026-11-23.

Übereinstimmung A–B je Frage; Stufe 3 verlangt α ≥ 0,80 (ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal):

| Frage | Skala | gestellt | gleich | Cohens κ | Krippendorffs α | genügt |
|---|---|---|---|---|---|---|
| `nummer_gemeint` | nominal | 100 | 100 von 100 (100,0 %) | 1,000 | 1,000 | ja |
| `selbe_sache` | nominal | 100 | 98 von 100 (98,0 %) | 0,922 | 0,922 | ja |
| `beziehung` | nominal | 100 | 94 von 100 (94,0 %) | 0,923 | 0,923 | ja |

## labels.csv

| Spalte | Inhalt |
|---|---|
| `id` | Schlüssel der Einheit (`stichprobe.csv` trägt seine Teile einzeln) |
| `frage` | die Frage aus dem Codebuch |
| `kodierer_a`, `kodierer_b` | die Antworten von A und B; leer, wo die Frage nicht gestellt war |
| `schlichtung` | die Antwort der Schlichtung; leer, wo A und B einig waren |
| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |
