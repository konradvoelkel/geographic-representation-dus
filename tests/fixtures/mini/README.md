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

`raw/beratungsfolge.parquet` (seit 2026-10-14, Punkt 58): die Beratungsfolge genau dieser 200
Dokumente, aus `snapshots/duesseldorf-beratungsfolge/raw/beratungsfolge.parquet` gefiltert
(`make_mini.write_consultations`; 200 Zeilen, 195 mit Folge, 27 Organisationen). Der Korpus der
Fixture kommt wie der der Referenz aus dem Altformat der Arbeit und trägt die Folge nicht; so liest
der Schritt `bodies` im Testlauf dieselbe zweite Quelle wie auf dem echten Datensatz, ohne dass die
Fixture an einer Datei außerhalb dieses Ordners hängt. `expected/` kennt sie nicht, und an den
Gremienzahlen der Fixture ändert sie nichts: dort trifft jede Drucksachennummer, und die Nummer
entscheidet.

`raw/tagesordnungspunkte.parquet` (seit 2026-11-24, Vorhaben 26): die Tabelle „Paper ×
Tagesordnungspunkt“ genau dieser 200 Dokumente, aus
`snapshots/duesseldorf-beschluesse/raw/tagesordnungspunkte-duesseldorf.parquet` gefiltert
(`make_mini.write_agenda`; 317 Zeilen). Wie die Beratungsfolge gilt sie vor dem Paket aus
`outcomes.package`, und so liest der Schritt `council_results` dieselben Zeilen auch aus einem
Arbeitsverzeichnis, von dem aus der relative Pfad des Pakets nicht trägt (`tests/unit/test_cli.py`).
`expected/` kennt sie nicht.

`raw/politikfelder_paket.parquet` (seit 2026-11-28, Vorhaben 19): die Politikfelder genau dieser 200
Dokumente, aus `snapshots/duesseldorf-politikfelder/processed/politikfelder.parquet` gefiltert
(`make_mini.write_policy_areas`; 200 Zeilen, alle mit Feld). Wie die Tabelle von Vorhaben 26 gilt sie
vor dem Paket aus `policy_areas.package`; die Codes stehen unter CC BY-NC-SA 4.0 wie im Paket.
`expected/` kennt sie nicht.

`external/bedarf/` (seit 2026-11-24, Vorhaben 22): die Auszüge der Bedarfsquellen für diese drei
Wahlbezirke, aus `snapshots/duesseldorf-bedarf/` gefiltert (`make_mini.write_need`): 2 237 Unfälle im
Band von 20 m um die 22 Stimmbezirke, 463 Gitterzellen und 14 Schulen mit Punkt in einem, dazu
`quellen.json` unverändert (Herkunft, Lizenz und Prüfsummen der Archive im README des Pakets). Die
Mini-Kette liest sie statt des Pakets, wie die Beratungsfolge; `expected/` kennt sie nicht.

`external/adressen/` (seit 2026-11-28, Vorhaben 16): das Adresspaket für die 22 Stimmbezirke, aus
`snapshots/duesseldorf-adressen/` gefiltert (`make_mini.write_addresses`): 5 920 Hausnummern mit
Stimm- und Wahlbezirk, keine Koordinate, dazu `quellen.json` unverändert (Herkunft, Lizenz und
Prüfsumme des Archivs im README des Pakets). Die Mini-Kette liest es statt des Pakets, wie die
Bedarfsdaten; ohne Rohtext schlägt sie darin nichts nach. `expected/` kennt es nicht.

`expected/`: die sieben Ausgaben des Altcodes der Arbeit (pandas, FlashText) auf genau diesen
Eingaben, erzeugt am 2026-10-11 auf dem Stand des Tags `v0.2.0`. Sie sind der Golden Master für
die Polars-Kette und werden nicht neu erzeugt.

**Unverändert seit 2026-10-12, obwohl die Methodik abweicht.** Die Regel „Einrichtung mit
Stadtnamen" (`search.city_facilities`, `docs/decisions.md`, Punkt 44a) trifft in dieser Fixture 62
der 493 Ortslabels — „Kunstakademie Düsseldorf", „Tonhalle Düsseldorf", „Landgericht Düsseldorf"
und so weiter, der Wahlbezirk 1 ist die Altstadt. Gemessen am 2026-10-12 rechnet die Kette hier mit
der Regel 431 Orte, 991 statt 1054 Begriffe und 162 statt 173 Treffer. Die Dateien unter
`expected/` bleiben trotzdem die der Arbeit: der Golden-Master-Test rechnet mit
`as_in_the_thesis(...)` (`tests/conftest.py`), also mit abgeschalteten Regeln, damit sichtbar
bleibt, wo die Arbeit endet und das Programm beginnt.
Geändert haben sich nur zwei eigene Zahlen dieses Repos, die eingefrorenen Gremienzahlen der
Fixture in `tests/unit/test_analysis_bodies.py` (96/63/14 → 89/59/14 Treffer).

Falls die Erwartungsdateien doch neu erzeugt werden müssen:

```bash
git worktree add /tmp/georep-v0.2.0 v0.2.0
cd /tmp/georep-v0.2.0 && uv sync && uv run python -m tests.fixtures.make_mini
```
