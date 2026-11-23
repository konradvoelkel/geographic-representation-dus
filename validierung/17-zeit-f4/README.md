# Validierung 17-zeit-f4

Erzeugt von `georep validate merge` am 2026-11-23; nicht von Hand ändern. Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).

- **Codebuch**: `codebuch.toml`, Version 2026-11-23.1; Einheit `document`, 2 Fragen.
- **Stichprobe**: 100 Einheiten aus Profil `duesseldorf, duesseldorf-2014, duesseldorf-2025`, geschichtet nach `kategorie`, gewichtet mit N_h/n_h (`stichprobe.csv`, `stichprobe.json`).
- **Kodierer**: zwei KI-Kodierer, Modell `claude-opus-5-5`, unabhängig voneinander und ohne die Ausgabe des geprüften Verfahrens; die 8 Uneinigkeiten entschied ein dritter Agent (Schlichtung). **Kein menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem stärkeren Modell, nicht mit Menschen.
- **Datum**: 2026-11-23.

Übereinstimmung A–B je Frage; Stufe 3 verlangt α ≥ 0,80 (ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal):

| Frage | Skala | gestellt | gleich | Cohens κ | Krippendorffs α | genügt |
|---|---|---|---|---|---|---|
| `thema` | open | 100 | 96 von 100 (96,0 %) | 0,956 | 0,957 | ja |
| `ebene` | nominal | 100 | 96 von 100 (96,0 %) | 0,927 | 0,928 | ja |

## labels.csv

| Spalte | Inhalt |
|---|---|
| `id` | Schlüssel der Einheit (`stichprobe.csv` trägt seine Teile einzeln) |
| `frage` | die Frage aus dem Codebuch |
| `kodierer_a`, `kodierer_b` | die Antworten von A und B; leer, wo die Frage nicht gestellt war |
| `schlichtung` | die Antwort der Schlichtung; leer, wo A und B einig waren |
| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |
