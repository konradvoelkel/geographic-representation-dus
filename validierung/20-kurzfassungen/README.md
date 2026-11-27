# Validierung 20-kurzfassungen

Erzeugt von `georep validate merge` am 2026-11-24; nicht von Hand ändern. Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).

- **Codebuch**: `codebuch.toml`, Version 1; Einheit `document`, 12 Fragen.
- **Stichprobe**: 50 Einheiten aus Profil `duesseldorf`, geschichtet nach `art`, gewichtet mit N_h/n_h (`stichprobe.csv`, `stichprobe.json`).
- **Kodierer**: zwei KI-Kodierer, unabhängig voneinander und ohne die Ausgabe des geprüften Verfahrens; die 76 Uneinigkeiten entschied ein dritter Agent (Schlichtung). **Kein menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem stärkeren Modell, nicht mit Menschen.
- **Modelle**: Kodierer A `claude-opus-5-5`, Kodierer B `claude-opus-5-5`, Schlichtung `claude-opus-5-5`.
- **Datum**: 2026-11-24.

Übereinstimmung A–B je Frage; Stufe 3 verlangt α ≥ 0,80 (ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal):

| Frage | Skala | gestellt | gleich | Cohens κ | Krippendorffs α | genügt |
|---|---|---|---|---|---|---|
| `k1_unbelegt` | binary | 50 | 48 von 50 (96,0 %) | 0,811 | 0,812 | ja |
| `k1_treue` | ordinal | 50 | 40 von 50 (80,0 %) | 0,617 | 0,870 | ja |
| `k1_vollstaendigkeit` | ordinal | 50 | 38 von 50 (76,0 %) | 0,435 | 0,505 | nein |
| `k1_verstaendlichkeit` | ordinal | 50 | 43 von 50 (86,0 %) | 0,742 | 0,815 | ja |
| `k2_unbelegt` | binary | 50 | 49 von 50 (98,0 %) | 0,898 | 0,899 | ja |
| `k2_treue` | ordinal | 50 | 45 von 50 (90,0 %) | 0,772 | 0,957 | ja |
| `k2_vollstaendigkeit` | ordinal | 50 | 43 von 50 (86,0 %) | 0,560 | 0,688 | nein |
| `k2_verstaendlichkeit` | ordinal | 50 | 41 von 50 (82,0 %) | 0,652 | 0,804 | ja |
| `k3_unbelegt` | binary | 50 | 47 von 50 (94,0 %) | 0,735 | 0,737 | nein |
| `k3_treue` | ordinal | 50 | 41 von 50 (82,0 %) | 0,593 | 0,879 | ja |
| `k3_vollstaendigkeit` | ordinal | 50 | 44 von 50 (88,0 %) | 0,748 | 0,775 | nein |
| `k3_verstaendlichkeit` | ordinal | 50 | 45 von 50 (90,0 %) | 0,764 | 0,771 | nein |

## labels.csv

| Spalte | Inhalt |
|---|---|
| `id` | Schlüssel der Einheit (`stichprobe.csv` trägt seine Teile einzeln) |
| `frage` | die Frage aus dem Codebuch |
| `kodierer_a`, `kodierer_b` | die Antworten von A und B; leer, wo die Frage nicht gestellt war |
| `schlichtung` | die Antwort der Schlichtung; leer, wo A und B einig waren |
| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |
