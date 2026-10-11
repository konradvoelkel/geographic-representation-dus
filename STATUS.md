# Status

Stand 2026-10-11, Branch `refactor/phase-3`. Fakten mit Datum, Invarianten ohne.

## Abgeschlossen

- Phase 0 (`v0.1.0`): uv-Projekt auf Python 3.14, Charakterisierungstests, nox, pre-commit, CI, mechanische Ruff-Commits.
- Phase 1 (`v0.2.0`): atomare Schreibvorgänge, Session mit Timeout und Retry, Fehlerisolation im Download, Guards, deterministische Ausgaben, Domänenfehler.
- Phase 2 (`v0.3.0`): Settings in TOML, OParl 1.1 als Vertrag, Layout mit Schreibschutz auf `reference/`, Polars-Kette mit Parquet, Schrittregister mit Stamps, CLI `georep`.
- Phase 3 (dieser Branch): Fetch- und Cache-Schicht. Geo mit shapely, pyproj und STRtree statt geopandas; Overpass statt osmnx; Wikidata und GeoSearch typisiert; requests-cache mit Lebensdauern je Quelle; PDF-Store mit Manifest; Textstore als Parquet mit Extraktor und PDF-Hash; inkrementeller OParl-Abruf mit frühem Abbruch; Netzschritte hinter `--online` und `georep fetch`. Der Code der Arbeit ist vollständig ersetzt und gelöscht; pandas, geopandas, osmnx, scikit-learn und tqdm sind aus dem Lockfile verschwunden, eine nox-Session verbietet ihre Rückkehr.

## Zahlen (2026-10-11)

- Tests: 103, davon einer `slow` (volle Referenz, 8 s); `uv run nox` grün.
- Code `src/georep/`: 33 Dateien, rund 2700 Zeilen, mypy strict ohne Befund.
- Lockfile: 153 Pakete.
- Treue der neuen Quellen gegen die Referenz der Arbeit: Straßen je Stimmbezirk 11/11, 7/7, 11/12 (Rest OSM-Pflege); SPARQL 949 von 950 Labels; Ortszuordnung 1996 von 1996 identisch (`tests/fixtures/http/README.md`, `tests/unit/test_geo.py`).
- Echter Rauchtest am 2026-10-11: `georep fetch opendata` gegen das Portal, danach `georep run` auf den frischen Dateien.

## Bekannt

- Ein voller `georep fetch` von Grund auf (Metadaten, 19108 PDFs, 306 Overpass- und 306 GeoSearch-Abfragen) wurde noch nicht durchlaufen; er dauert Stunden und ist wiederaufnehmbar. Der öffentliche Overpass-Server antwortete bei der Aufzeichnung einmal mit 504; die Session wiederholt mit Backoff.
- Ob der OParl-Server `modified_since` beachtet, ist nicht gemessen; ohne Beachtung liest der inkrementelle Abruf wieder alle Seiten bis zum Periodenbeginn und ist nur durch den Abbruch günstiger.
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab (`docs/baseline-2026-10-10.md`).

## Nächster Schritt

Phase 4 (Tests ausbauen: hypothesis-Eigenschaften, Snapshots, Coverage als Untergrenze, mutmut) und Phase 5
(Profiling als Befehl, pytest-benchmark, Matcher- und Extraktor-Protokolle messen).
