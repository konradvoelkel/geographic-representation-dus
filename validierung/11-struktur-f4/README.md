# Validierung 11-struktur-f4

Erzeugt von `georep validate merge` am 2026-11-23; nicht von Hand ändern. Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).

- **Codebuch**: `codebuch.toml`, Version 2026-11-23; Einheit `document`, 10 Fragen.
- **Stichprobe**: 200 Einheiten aus Profil `duesseldorf`, geschichtet nach `schicht`, gewichtet mit N_h/n_h (`stichprobe.csv`, `stichprobe.json`).
- **Kodierer**: zwei KI-Kodierer, unabhängig voneinander und ohne die Ausgabe des geprüften Verfahrens; die eine Uneinigkeit entschied ein dritter Agent (Schlichtung). **Kein menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem stärkeren Modell, nicht mit Menschen.
- **Modelle**: Kodierer A `claude-opus-5-5`, Kodierer B `claude-opus-5-5`, Schlichtung `claude-opus-5-5`.
- **Datum**: 2026-11-23.

Übereinstimmung A–B je Frage; Stufe 3 verlangt α ≥ 0,80 (ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal):

| Frage | Skala | gestellt | gleich | Cohens κ | Krippendorffs α | genügt |
|---|---|---|---|---|---|---|
| `bv_vorhanden` | binary | 200 | 200 von 200 (100,0 %) | 1,000 | 1,000 | ja |
| `bv_erste_zeile` | interval | 114 | 114 von 114 (100,0 %) | 1,000 | 1,000 | ja |
| `bv_letzte_zeile` | interval | 114 | 114 von 114 (100,0 %) | 1,000 | 1,000 | ja |
| `bv_mehrteilig` | binary | 114 | 114 von 114 (100,0 %) | nicht definiert | nicht definiert | nein |
| `amt` | open | 200 | 200 von 200 (100,0 %) | 1,000 | 1,000 | ja |
| `dezernat_titel` | nominal | 200 | 200 von 200 (100,0 %) | 1,000 | 1,000 | ja |
| `beratungsfolge` | open | 200 | 200 von 200 (100,0 %) | 1,000 | 1,000 | ja |
| `sitzung` | open | 200 | 199 von 200 (99,5 %) | 0,990 | 0,990 | ja |
| `briefdatum` | open | 200 | 200 von 200 (100,0 %) | 1,000 | 1,000 | ja |
| `unsicher` | binary | 200 | 199 von 200 (99,5 %) | 0,921 | 0,921 | ja |

## labels.csv

| Spalte | Inhalt |
|---|---|
| `id` | Schlüssel der Einheit (`stichprobe.csv` trägt seine Teile einzeln) |
| `frage` | die Frage aus dem Codebuch |
| `kodierer_a`, `kodierer_b` | die Antworten von A und B; leer, wo die Frage nicht gestellt war |
| `schlichtung` | die Antwort der Schlichtung; leer, wo A und B einig waren |
| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |
