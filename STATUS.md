# Status

Stand 2026-10-11, Branch `refactor/phase-1`. Fakten mit Datum, Invarianten ohne.

## Phase 0 (Netz spannen): abgeschlossen, `v0.1.0` auf `main`

uv-Projekt auf Python 3.14 mit Polars 2.0, Charakterisierungstests, nox, pre-commit, CI (erster Lauf
grün am 2026-10-11), mechanische Ruff-Commits in `.git-blame-ignore-revs`.

## Phase 1 (Risiken schließen): Code fertig, CI-Lauf und Merge offen

- Paket `georep` aus Phase 2 vorgezogen (uv_build, `py.typed`, mypy strict): `io` (atomare
  Schreibvorgänge), `http` (Session mit Timeout 180 s, Retry mit Backoff, User-Agent; `Transport`-Protokoll
  als Testnaht), `errors` (Domänenfehler).
- Altcode: alle 15 Schreibstellen atomar; alle 6 Request-Stellen über die Session, bandit B113 leer;
  PDF-Download isoliert Fehler pro Datei und berichtet Zahlen; Metadaten-Download speichert nach jeder
  Seite und wirft statt still zu verkürzen; Wahlergebnis byteweise gespeichert; Guards in `prep_papers`
  (keine PDFs, schrumpfender Korpus), `reverse_index` und `analyse` (leere Ergebnisse), `prep_voters`
  (Pflichtspalten); Nicht-PDF-Antworten abgewiesen; unlesbarer lokaler Stand ist ein Fehler; Index
  sortiert, zwei Läufe byteidentisch; Wikidata-Entität und Sprache verdrahtet; Log-Level über
  `GEOREP_LOG_LEVEL`, Standard INFO.
- Tests: 51, davon einer `slow`; jede Verhaltensänderung mit Test, Netz über eine Fake-Session.
- `uv run nox` grün: lint, typecheck, baseline (14 Fehler im Altcode, Schwelle), test, golden.

## Bekannt

- `except Exception` bleibt in `dataset_wikidata` (2) und `dataset_streets` (1) als Isolation pro Element,
  ohne Test; Phase 3 ersetzt beide Module.
- `run.py` ruft die Schritte weiter ohne Exit-Code-Logik; Domänenfehler beenden ihn jetzt mit Traceback
  statt still. Die CLI in Phase 2 übernimmt Exit-Codes.
- Altcode: 14 mypy-Fehler, Spaltennamen hart kodiert, Pfade aus `config.py`. Phase 2.
- pandas steht noch im Lockfile: Altcode, geopandas, osmnx. Phase 3.
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab (`docs/baseline-2026-10-10.md`).

## Nächster Schritt

Phase 2: Settings (TOML + pydantic-settings), Layout mit `reference/` und `data_root`, Modelle,
Schrittregister mit Stamps, CLI, Strangler Fig modulweise nach Polars.
