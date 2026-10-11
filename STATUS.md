# Status

Stand 2026-10-11, `main` auf `v0.5.0`, offener Branch `refactor/phase-5`. Fakten mit Datum, Invarianten ohne.

## Abgeschlossen

- Phase 0 (`v0.1.0`): uv-Projekt auf Python 3.14, Charakterisierungstests, nox, pre-commit, CI, mechanische Ruff-Commits.
- Phase 1 (`v0.2.0`): atomare Schreibvorgänge, Session mit Timeout und Retry, Fehlerisolation im Download, Guards, deterministische Ausgaben, Domänenfehler.
- Phase 2 (`v0.3.0`): Settings in TOML, OParl 1.1 als Vertrag, Layout mit Schreibschutz auf `reference/`, Polars-Kette mit Parquet, Schrittregister mit Stamps, CLI `georep`.
- Phase 3 (`v0.4.0`): Fetch- und Cache-Schicht ohne geopandas und osmnx; der Code der Arbeit ist vollständig ersetzt.
- Phase 4 (`v0.5.0`): Tests ausgebaut. `tests/property/` mit hypothesis: ein lesbares Orakel des Matcher-Vertrags (FlashText stimmt in 400 Zufallsfällen überein), Invarianten für Wörterbuch, Aggregation, POI-Bereinigung, Straßen, Treffer, Index, STRtree, OParl-Roundtrip, Stores und `deep_merge`. Abdeckungslücken geschlossen, Snapshot für `georep steps`, nox `test` parallel mit Abdeckung als Untergrenze (90 %), hypothesis-Profile `dev` und `ci`.

## Zahlen (2026-10-11)

- Tests: 122, davon einer `slow`; schnelle Suite parallel in 8 s; Abdeckung 98 %.
- Code `src/georep/`: 33 Dateien, rund 2700 Zeilen, mypy strict ohne Befund.

## Bekannt

- Mutationstests stehen aus: mutmut 3 forkt, Polars blockiert im Kind (`docs/mutation-2026-10-11.md`); Kandidaten pytest-gremlins oder fest in Phase 6.
- Ein voller `georep fetch` von Grund auf lief noch nie; er dauert Stunden und ist wiederaufnehmbar. Ob der OParl-Server `modified_since` beachtet, zeigt erst dieser Lauf.
- Labels, die sich nur durch ein Komma unterscheiden, fallen in der POI-Bereinigung zusammen (Verhalten der Arbeit, durch das Wörterbuch harmlos).
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab (`docs/baseline-2026-10-10.md`).

## Nächster Schritt

Phase 5 auf `refactor/phase-5` (siehe `DEVELOPMENT_PLAN.md` § 4, Phase 5, mit Werkzeugliste und dem Rezept
für eine PDF-Stichprobe): Profiling als Befehl, pytest-benchmark mit gespeicherten Baselines für Matcher,
Extraktion und Aggregation; erst dann die Entscheidung über pyahocorasick, pypdfium2 oder Rust. Danach
Phase 6 (deal, crosshair).
