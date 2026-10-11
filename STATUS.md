# Status

Stand 2026-10-11, `main` auf `v0.8.0`. Der Umbau in sieben Phasen ist abgeschlossen
(`docs/development-plan-2026-10.md`); Aufbau in `docs/architecture.md`, Gründe in `docs/decisions.md`. Fakten mit
Datum, Invarianten ohne.

## Abgeschlossen

- Phase 0 (`v0.1.0`): uv-Projekt auf Python 3.14, Charakterisierungstests, nox, pre-commit, CI, mechanische Ruff-Commits.
- Phase 1 (`v0.2.0`): atomare Schreibvorgänge, Session mit Timeout und Retry, Fehlerisolation im Download, Guards, deterministische Ausgaben, Domänenfehler.
- Phase 2 (`v0.3.0`): Settings in TOML, OParl 1.1 als Vertrag, Layout mit Schreibschutz auf `reference/`, Polars-Kette mit Parquet, Schrittregister mit Stamps, CLI `georep`.
- Phase 3 (`v0.4.0`): Fetch- und Cache-Schicht ohne geopandas und osmnx; der Code der Arbeit ist vollständig ersetzt.
- Phase 4 (`v0.5.0`): Tests ausgebaut. `tests/property/` mit hypothesis: ein lesbares Orakel des Matcher-Vertrags, Invarianten für Wörterbuch, Aggregation, POI-Bereinigung, Straßen, Treffer, Index, STRtree, OParl-Roundtrip, Stores und `deep_merge`. Snapshot für `georep steps`, nox `test` parallel mit Abdeckung als Untergrenze (90 %).
- Phase 5 (`v0.6.0`): Profiling-Infrastruktur. `georep profile`, `nox -s bench` (pytest-benchmark, rot ab 20 % langsamer im Minimum), Protokoll `PdfTextExtractor`. Messung in `docs/profiling/README.md`: Offline-Lauf 6,3 s, davon 4,1 s FlashText; Extraktion 38 ms je PDF; pypdf 6.20.0 reproduziert 197 von 200 Texten der Arbeit zeichengleich. Empfehlung: pypdf und FlashText bleiben, kein Rust-Port.
- Phase 6 (`v0.7.0`): Design by Contract. 80 deal-Decorators an 30 Funktionen in `search`, `analysis`, `prep`, `geo`, `layout`, `stores`, `http`, `settings` und `sources`; Prädikate in `georep.contracts`; `settings.contracts = "off"` schaltet ab, Overhead unter einem Prozent. Fetcher werfen nur `FetchError` oder `NetworkError`, die CLI meldet einen abgebrochenen Abruf als eine Zeile. `deal.cases` greift zehn reine Funktionen an, `nox -s verify` (crosshair) fand und `nox -s mutate` (pytest-gremlins, 79 % getötet) deckte je einen echten Fehler auf: `street_names` bei kaputter Overpass-Antwort und deals nicht reentranter `HasPatcher`, der nach `deep_merge` Socket und stdout gepatcht ließ. Beides behoben, `docs/mutation-2026-10-11.md`.
- Phase 7 (`v0.8.0`): Abschluss. README aus Sicht eines frischen Klons (geprüft am 2026-10-11 auf xtraspace: `uv sync --locked`, `bootstrap`, `run` in 6 s, `regress`, `nox`, slow-Test), `docs/architecture.md` und `docs/decisions.md` ersetzen den Plan, der archiviert ist; Code-Docstrings verweisen auf die lebenden Beschreibungen. Kein Pull Request an `lubar102` (Konrads Entscheidung, decisions.md Punkt 19).

## Zahlen (2026-10-11)

- Tests: 171, davon einer `slow` und zehn `bench`; schnelle Suite parallel in 9 s; Abdeckung 98 %.
- Code `src/georep/`: 35 Dateien, rund 3250 Zeilen, mypy strict mit deal-Plugin ohne Befund; Commits seit dem Fork: 78 in sieben Phasen.
- Laufzeit: voller Offline-Lauf 6,4 bis 6,7 s mit wie ohne Verträge (Index 4,1 bis 4,3 s); `nox -s verify` 2,5 bis 3 min; `nox -s mutate` 100 s.

## Bekannt

- deal 4.24.6: `deal.raises` vergleicht exakte Typen, keine Unterklassen; `deal.has()`/`deal.pure` sind nicht reentrant (Patch bleibt nach Rekursion stehen). Beides umschifft (NetworkError, `deal.safe` für `deep_merge`), nicht upstream gemeldet.
- Zwölf überlebende Mutanten liegen in Vertrags-Lambdas (Grenzen von r und p); kein Test verletzt sie genau an der Grenze. Bewusst nicht nachgezogen.
- Ein voller `georep fetch` von Grund auf lief noch nie; er dauert Stunden und ist wiederaufnehmbar. Hochrechnung aus der Stichprobe: 5,8 h Abruf, 2,8 GB, 12 min Extraktion.
- Auf Konrads Rechner liegen seit dem 2026-10-11 die ersten 200 PDFs nach Paper-ID unter `cache_root/pdf/`; `georep status` zeigt `pdfs` als „offen: Settings geändert", weil `--limit 200` im Stamp steht. Das ist richtig so.
- Labels, die sich nur durch ein Komma unterscheiden, fallen in der POI-Bereinigung zusammen (Verhalten der Arbeit, durch das Wörterbuch harmlos).
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab (`docs/baseline-2026-10-10.md`).

## Nächster Schritt

Die Berichtsseite: eine in sich geschlossene HTML-Seite mit Kernzahlen, Karte der Trefferquote je Wahlbezirk,
Streudiagramm mit Regression, sortierbarer Tabelle, Begriffen, Methode und den Ergebnissen zum Download als
Parquet, CSV und GeoJSON mit Spaltenschema; gebaut als Pipeline-Schritt `report`, veröffentlicht über GitHub Pages
aus einem Actions-Workflow, später nach Bedarf auf Konrads VPS, optional unter `georep.konradvoelkel.de`. Plan in
Stufen mit Abnahmekriterien und Startanleitung: `docs/plan-report-2026-10.md` (Konrad, 2026-10-11; offene Fragen
beantwortet, Plan freigegeben). Gearbeitet wird direkt auf `main`, keine Branches mehr. Für Konrad bleibt ein
Handgriff: Pages in den Repo-Einstellungen auf „GitHub Actions" stellen, sobald Stufe F erreicht ist.

Außerdem offen, wenn jemand es will: ein voller `georep fetch` von Grund
auf (Stunden; zeigt, ob der OParl-Server `modified_since` beachtet); ein Ersatz für FlashText oder pypdf nur
nach neuer Messung (`docs/decisions.md`, Punkt 14); die beiden deal-Eigenheiten upstream melden; die Abweichung
in Tabelle 5 „ohne Ausreißer" mit Lukas klären, falls es je wieder darauf ankommt.
