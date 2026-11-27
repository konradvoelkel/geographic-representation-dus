# Validierung 16-ortsbezug-2-f4

Erzeugt von `georep validate merge` am 2026-11-27; nicht von Hand ändern. Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).

- **Codebuch**: `codebuch.toml`, Version 2026-11-23.2; Einheit `document`, 4 Fragen.
- **Stichprobe**: 100 Einheiten aus Profil `duesseldorf`, geschichtet nach `schicht`, gewichtet mit N_h/n_h (`stichprobe.csv`, `stichprobe.json`).
- **Kodierer**: zwei KI-Kodierer, unabhängig voneinander und ohne die Ausgabe des geprüften Verfahrens; die eine Uneinigkeit entschied ein dritter Agent (Schlichtung). **Kein menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem stärkeren Modell, nicht mit Menschen.
- **Modelle**: Kodierer A `claude-opus-5-5`, Kodierer B `claude-opus-5-5`, Schlichtung `claude-opus-5-5`.
- **Datum**: 2026-11-27.

Übereinstimmung A–B je Frage; Stufe 3 verlangt α ≥ 0,80 (ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal):

| Frage | Skala | gestellt | gleich | Cohens κ | Krippendorffs α | genügt |
|---|---|---|---|---|---|---|
| `bezug` | nominal | 100 | 99 von 100 (99,0 %) | 0,974 | 0,974 | ja |
| `begriffe_kein_bezug` | open | 100 | 100 von 100 (100,0 %) | 1,000 | 1,000 | ja |
| `beleg_zeile` | interval | 100 | 84 von 100 (84,0 %) | 0,835 | 0,996 | ja |
| `unsicher` | binary | 100 | 93 von 100 (93,0 %) | 0,594 | 0,595 | nein |

## labels.csv

| Spalte | Inhalt |
|---|---|
| `id` | Schlüssel der Einheit (`stichprobe.csv` trägt seine Teile einzeln) |
| `frage` | die Frage aus dem Codebuch |
| `kodierer_a`, `kodierer_b` | die Antworten von A und B; leer, wo die Frage nicht gestellt war |
| `schlichtung` | die Antwort der Schlichtung; leer, wo A und B einig waren |
| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |
