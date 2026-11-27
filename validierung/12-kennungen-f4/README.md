# Validierung 12-kennungen-f4

Erzeugt von `georep validate merge` am 2026-11-23; nicht von Hand ändern. Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).

- **Codebuch**: `codebuch.toml`, Version 1; Einheit `span`, 7 Fragen.
- **Stichprobe**: 600 Einheiten aus Profil `duesseldorf`, geschichtet nach `schicht`, gewichtet mit N_h/n_h (`stichprobe.csv`, `stichprobe.json`).
- **Kodierer**: zwei KI-Kodierer, unabhängig voneinander und ohne die Ausgabe des geprüften Verfahrens; die 62 Uneinigkeiten entschied ein dritter Agent (Schlichtung); davon 4 Einheiten: Auswerter nach den Regeln des Schlichters, Runde 1. **Kein menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem stärkeren Modell, nicht mit Menschen.
- **Modelle**: Kodierer A `claude-opus-5-5`, Kodierer B `claude-opus-5-5`, Schlichtung `claude-opus-5-5`.
- **Datum**: 2026-11-23.

Übereinstimmung A–B je Frage; Stufe 3 verlangt α ≥ 0,80 (ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal):

| Frage | Skala | gestellt | gleich | Cohens κ | Krippendorffs α | genügt |
|---|---|---|---|---|---|---|
| `art` | nominal | 600 | 600 von 600 (100,0 %) | 1,000 | 1,000 | ja |
| `grenzen` | nominal | 597 | 597 von 597 (100,0 %) | 1,000 | 1,000 | ja |
| `text_korrigiert` | open | 41 | 40 von 41 (97,6 %) | 0,975 | 0,975 | ja |
| `norm` | open | 597 | 555 von 597 (93,0 %) | 0,929 | 0,929 | ja |
| `rolle` | nominal | 98 | 90 von 98 (91,8 %) | 0,901 | 0,901 | ja |
| `frist` | nominal | 100 | 89 von 100 (89,0 %) | 0,850 | 0,850 | ja |
| `sicher` | binary | 600 | 530 von 600 (88,3 %) | 0,616 | 0,616 | nein |

## labels.csv

| Spalte | Inhalt |
|---|---|
| `id` | Schlüssel der Einheit (`stichprobe.csv` trägt seine Teile einzeln) |
| `frage` | die Frage aus dem Codebuch |
| `kodierer_a`, `kodierer_b` | die Antworten von A und B; leer, wo die Frage nicht gestellt war |
| `schlichtung` | die Antwort der Schlichtung; leer, wo A und B einig waren |
| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |
