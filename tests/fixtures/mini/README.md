# Mini-Fixture

Eingaben (`external/`, `raw/`, `interim/`): deterministische Stichprobe aus `reference/`, erzeugt mit
`uv run python -m tests.fixtures.make_mini` (Wahlbezirke 1, 10, 38; 200 Dokumente).

`expected/`: die sieben Ausgaben des Altcodes der Arbeit (pandas, FlashText) auf genau diesen
Eingaben, erzeugt am 2026-10-11 auf dem Stand des Tags `v0.2.0`. Sie sind der Golden Master für
die Polars-Kette und werden nicht neu erzeugt. Falls doch nötig:

```bash
git worktree add /tmp/georep-v0.2.0 v0.2.0
cd /tmp/georep-v0.2.0 && uv sync && uv run python -m tests.fixtures.make_mini
```
