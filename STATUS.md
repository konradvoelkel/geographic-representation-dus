# Status

Stand 2026-10-10, Branch `refactor/phase-0`. Fakten mit Datum, Invarianten ohne.

## Phase 0 (Netz spannen)

- uv-Projekt: `pyproject.toml`, `uv.lock` (161 Pakete), Python 3.14, Polars 2.0. Noch kein installierbares Paket (`package = false`), Altcode liegt flach in `src/`.
- Charakterisierungstests: 14 Tests, davon einer `slow` (volles Korpus, 5 s). Mini-Fixture mit 200 Dokumenten und drei Wahlbezirken; vier PDF-Fixtures mit Herkunft.
- Automatisierung: `noxfile.py` (lint, typecheck, baseline, test, golden), `.pre-commit-config.yaml`, GitHub Actions per SHA gepinnt.
- Mechanische Commits: `ruff --select UP --fix`, Ruff-Autofixes, `ruff format`, in `.git-blame-ignore-revs`.
- Offen in Phase 0: Push des Branches und erster CI-Lauf; Merge nach `main` und Tag `v0.1.0`.

## Bekannt

- Altcode: 14 mypy-Fehler (Schwelle in `noxfile.py`), 12 × `except Exception`, keine Timeouts. Alles Phase 1.
- pandas steht noch im Lockfile: direkt für den Altcode, transitiv über geopandas und osmnx. Geht mit Phase 3.
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab (`docs/baseline-2026-10-10.md`).

## Nächster Schritt

Phase 1: Timeouts, atomare Schreibvorgänge, Guards gegen leere Ergebnisse, Fehlerisolation beim Download.
