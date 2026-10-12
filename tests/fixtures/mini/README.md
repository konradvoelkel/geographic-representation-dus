# Mini-Fixture

Eingaben (`external/`, `raw/`, `interim/`): deterministische Stichprobe aus `reference/`, erzeugt mit
`uv run python -m tests.fixtures.make_mini` (Wahlbezirke 1, 10, 38; 200 Dokumente).
`external/Stimmbezirke_2025.geojson` (seit 2026-10-11): die 22 Stimmbezirke dieser drei Wahlbezirke aus
`reference/external/Stimmbezirke_2025.geojson` (Open-Data-Portal Düsseldorf, EPSG:4647), kompakt
geschrieben, mit dem `crs` der Quelle; Eingabe des Schritts `report`. Die Dateien unter `expected/`
kennen keine Geometrie und blieben beim Hinzufügen unverändert.

`context/` (seit 2026-10-12, Option 03): die 24 Raumeinheiten, die diese 22 Stimmbezirke schneiden, aus
`context/` des Repos (Quartiersatlas Düsseldorf 2024, Landeshauptstadt Düsseldorf, Amt für Statistik und
Wahlen, dl-de/by-2-0; Herkunft, Stand und Prüfsummen in `context/README.md`). `quartiersatlas_2024.csv`
ist byte-treu gefiltert (UTF-8, `;`, CRLF, Dezimalkomma), `sozialraeume_2021.geojson` trägt den `crs` der
Quelle (CRS84, lon/lat) und alle Eigenschaften, `quartiersatlas_2024_indikatoren.csv` ist unverändert
(keine Daten je Einheit). Eingaben der Schritte `context` und `controls`; `expected/` kennt sie nicht.

`expected/`: die sieben Ausgaben des Altcodes der Arbeit (pandas, FlashText) auf genau diesen
Eingaben, erzeugt am 2026-10-11 auf dem Stand des Tags `v0.2.0`. Sie sind der Golden Master für
die Polars-Kette und werden nicht neu erzeugt. Falls doch nötig:

```bash
git worktree add /tmp/georep-v0.2.0 v0.2.0
cd /tmp/georep-v0.2.0 && uv sync && uv run python -m tests.fixtures.make_mini
```
