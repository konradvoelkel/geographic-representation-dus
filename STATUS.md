# Status

Stand 2026-10-11, Branch `refactor/phase-2`. Fakten mit Datum, Invarianten ohne.

## Abgeschlossen

- Phase 0 (`v0.1.0`): uv-Projekt auf Python 3.14, Charakterisierungstests, nox, pre-commit, CI, mechanische Ruff-Commits.
- Phase 1 (`v0.2.0`): atomare Schreibvorgänge, Session mit Timeout und Retry, Fehlerisolation im Download, Guards, deterministische Ausgaben, Domänenfehler.
- Phase 2 (dieser Branch): Settings (TOML-Schichten, Umgebung, Fingerprint), OParl 1.1 als pydantic-Vertrag mit echter Fixture, Layout mit Schreibschutz auf `reference/`, Bootstrap, die Offline-Kette komplett in Polars mit Parquet, Schrittregister mit Stamps, CLI `georep`, CSV-Export, Notebook als dünner Client. Der Altcode der Offline-Kette ist gelöscht; `run.py` ruft nach den Netzschritten die neue Kette.

## Zahlen (2026-10-11)

- Tests: 87, davon einer `slow` (volle Referenz, 6 s); `uv run nox` grün.
- Neuer Code `src/georep/`: rund 1500 Zeilen, mypy strict ohne Befund, Komplexität im Schnitt A, keine Funktion über B.
- Altcode `src/*.py` und `run.py`: rund 1100 Zeilen (vier Netzschritte, `prep_papers`, `utils`, Shim `config.py`); 4 mypy-Fehler (Schwelle in `noxfile.py`), drei Funktionen mit C.
- Volle Kette auf der Referenz: `bootstrap` plus `run` rund 5 s, davon 4 s FlashText über 19108 Dokumente.

## Bekannt

- pandas steht transitiv im Lockfile (geopandas, osmnx), beide nur von den Netzschritten gebraucht. Phase 3 ersetzt sie durch shapely, pyproj und Overpass.
- `except Exception` bleibt in `dataset_wikidata` (2) und `dataset_streets` (1) ohne Test bis Phase 3.
- Die PDF-Extraktion (`src/prep_papers.py`) schreibt noch das Altformat `paper_with_text.json`; der Schritt `corpus` wandelt es. Phase 3 bringt Extraktion mit Textcache direkt nach Parquet.
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab (`docs/baseline-2026-10-10.md`).

## Nächster Schritt

Phase 3: Fetch- und Cache-Schicht (requests-cache, PDF-Store mit Manifest, Textcache je PDF-Hash, inkrementeller OParl-Abruf über das Modell, Overpass statt osmnx, STRtree statt Schleife), danach verschwinden geopandas, osmnx und pandas aus dem Lockfile.
