# Status

Stand 2026-10-11, `main` auf `v0.6.0`, nächster Branch `refactor/phase-6`. Fakten mit Datum, Invarianten ohne.

## Abgeschlossen

- Phase 0 (`v0.1.0`): uv-Projekt auf Python 3.14, Charakterisierungstests, nox, pre-commit, CI, mechanische Ruff-Commits.
- Phase 1 (`v0.2.0`): atomare Schreibvorgänge, Session mit Timeout und Retry, Fehlerisolation im Download, Guards, deterministische Ausgaben, Domänenfehler.
- Phase 2 (`v0.3.0`): Settings in TOML, OParl 1.1 als Vertrag, Layout mit Schreibschutz auf `reference/`, Polars-Kette mit Parquet, Schrittregister mit Stamps, CLI `georep`.
- Phase 3 (`v0.4.0`): Fetch- und Cache-Schicht ohne geopandas und osmnx; der Code der Arbeit ist vollständig ersetzt.
- Phase 4 (`v0.5.0`): Tests ausgebaut. `tests/property/` mit hypothesis: ein lesbares Orakel des Matcher-Vertrags (FlashText stimmt in 400 Zufallsfällen überein), Invarianten für Wörterbuch, Aggregation, POI-Bereinigung, Straßen, Treffer, Index, STRtree, OParl-Roundtrip, Stores und `deep_merge`. Abdeckungslücken geschlossen, Snapshot für `georep steps`, nox `test` parallel mit Abdeckung als Untergrenze (90 %), hypothesis-Profile `dev` und `ci`.
- Phase 5 (`v0.6.0`): Profiling-Infrastruktur. `georep profile` (echter Schritt unter cProfile, `.prof` für snakeviz), `nox -s bench` mit pytest-benchmark gegen die gespeicherte Baseline (rot ab 20 % langsamer im Minimum, über dem gemessenen Rauschen von 13 %), Protokoll `PdfTextExtractor`. Erste Messung in `docs/profiling/README.md`: Offline-Lauf 6,3 s, davon 4,1 s FlashText (reines Python); Extraktion 38 ms je PDF über 200 PDFs; pypdf 6.20.0 reproduziert 197 von 200 Texten der Arbeit zeichengleich. Empfehlung: pypdf und FlashText bleiben, kein Rust-Port.

## Zahlen (2026-10-11)

- Tests: 137, davon einer `slow` und zehn `bench`; schnelle Suite parallel in 8 s; Abdeckung 98 %.
- Code `src/georep/`: 34 Dateien, rund 2860 Zeilen, mypy strict ohne Befund.
- Laufzeit: voller Offline-Lauf 6,3 s (Index 4,1 s); 200 PDFs abgerufen in 218 s, extrahiert in 8,3 s.

## Bekannt

- Mutationstests stehen aus: mutmut 3 forkt, Polars blockiert im Kind (`docs/mutation-2026-10-11.md`); Kandidaten pytest-gremlins oder fest in Phase 6.
- Ein voller `georep fetch` von Grund auf lief noch nie; er dauert Stunden und ist wiederaufnehmbar. Ob der OParl-Server `modified_since` beachtet, zeigt erst dieser Lauf. Hochrechnung aus der Stichprobe: 5,8 h Abruf, 2,8 GB, 12 min Extraktion.
- Auf Konrads Rechner liegen seit dem 2026-10-11 die ersten 200 PDFs nach Paper-ID unter `cache_root/pdf/`; `georep status` zeigt `pdfs` als „offen: Settings geändert", weil `--limit 200` im Settings-Fingerprint des Stamps steht. Das ist richtig so: mit Limit 0 fehlen noch 18 892 PDFs.
- Labels, die sich nur durch ein Komma unterscheiden, fallen in der POI-Bereinigung zusammen (Verhalten der Arbeit, durch das Wörterbuch harmlos).
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab (`docs/baseline-2026-10-10.md`).

## Nächster Schritt

Phase 6 auf `refactor/phase-6` (siehe `DEVELOPMENT_PLAN.md` § 4, Phase 6): `deal`-Verträge auf den reinen
Funktionen, `settings.contracts = "off"` verdrahten und den Overhead messen (`nox -s bench` ist dafür da),
`deal.cases` und `crosshair check` als `nox -s verify`, Mutationstests erneut mit pytest-gremlins oder fest.
Die Empfehlung aus Phase 5 (kein Ersatz für pypdf und FlashText) steht in `docs/profiling/README.md` zur
Entscheidung; Phase 6 hängt nicht davon ab.
