# Entwicklungsplan: geographic-representation-dus auf Vordermann

Stand 2026-10-10, freigegeben von Konrad am selben Tag mit zwei Änderungen: Polars statt pandas und Parquet wo möglich; Python 3.14. Dieser Plan wird nach Abschluss durch Beschreibungen ersetzt
(README, `docs/`), nicht fortgeschrieben. Befund und Messlatte: `docs/baseline-2026-10-10.md`.

## 1. Ziel

Den Code so umbauen, dass

1. kein Befehl Daten zerstört: Läufe sind idempotent, Schreibvorgänge atomar, Referenzdaten unantastbar;
2. alle Netzabrufe gecacht sind, konfigurierbar über `settings.yml`, Daten und Cache standardmäßig außerhalb des Repos (bei Konrad auf xtraspace);
3. `ruff`, `mypy --strict`, `uv` mit `pyproject.toml` und `uv.lock` der Normalzustand sind;
4. eine Testsuite existiert, die in Sekunden läuft und das heutige Verhalten als Netz hält;
5. Profiling einzelner Funktionen und ganzer Abläufe ein Befehl ist, mit gespeicherten Baselines;
6. der Weg von Type Hints über Tests zu Design by Contract (deal + hypothesis, crosshair) gegangen ist, damit ein Agent nach jeder Änderung in Sekunden eine belastbare Antwort bekommt;
7. die heißen Pfade hinter Protokollen liegen, sodass eine Rust-Implementierung ein Austausch ist, kein Umbau.

## 2. Leitplanken (aus dem eipy-Skript und dem Playbook)

- Reihenfolge nicht verhandelbar: verstehen, zum Laufen bringen, Verhalten einfrieren, modernisieren, umbauen.
- Eine Refactoring-Sorte pro Commit. Formatierung und Modernisierung sind je ein eigener Commit und stehen in `.git-blame-ignore-revs`. Keine inhaltliche Änderung fährt mit.
- Nach jedem Commit läuft der Charakterisierungstest. Wird er rot, war es kein Refactoring.
- Definition of Done pro Phase: läuft aus frischem Klon (`git clone`, `uv sync`, `uv run …`), Charakterisierungstest grün, ruff und mypy nicht schlechter als die Baseline, eine Zeile im Changelog.
- Zeit, Zufall und Netz sind Eingaben, keine Umwelt: injizieren, dann testen.
- Golden Master klein halten, nichts Schwankendes einfrieren, nie blind aktualisieren.
- Ruff-Regelsatz zuerst `E, F, I, UP, B`, dann `SIM, RUF, ANN`; `mypy strict = true` für neuen Code von Anfang an; Stubs statt `ignore_missing_imports`, Ausnahmen pro Modul mit Begründung.
- Pydantic validiert an der Systemgrenze (OParl-JSON, Settings, Manifeste), Verträge sichern das Innere. `deal` und `icontract` nicht mischen. `deal test` ist mit typeguard 4 kaputt; Testgenerierung über hypothesis mit `deal.cases` und über `crosshair check`.
- Erst messen, dann optimieren, dann nachmessen. Ein Rust-Port nur für einen gemessenen Flaschenhals.
- Ein Cache oder Guard muss die Änderung sehen können, auf die er reagieren soll: Schlüssel enthalten Eingabe-Hashes, Settings-Hash und Code-Version.
- Ein Schritt druckt die Anzahl, auf die er gewirkt hat, nicht nur, dass er lief.
- Polars statt pandas, Parquet wo möglich (Vorgabe Konrad, 2026-10-10). Neuer Code fasst pandas nicht an. pandas bleibt bis zum Ende von Phase 3 nur als Abhängigkeit des Altcodes (direkt) und von osmnx/geopandas (transitiv) und verschwindet dann aus dem Lockfile; ein CI-Check (`uv tree --invert --package pandas` leer) belegt das.
- Rejected alternatives werden mit ihren Kosten festgehalten (§ 7).

## 3. Zielarchitektur

### 3.1 Paket und Layout

```
pyproject.toml            uv_build, [project.scripts] georep = "georep.cli:main"
uv.lock  .python-version  settings.toml (Defaults, eingecheckt)  settings.local.toml (gitignored)
src/georep/
  settings.py             pydantic-settings; TOML + Env-Präfix GEOREP_ + --settings
  layout.py               DataLayout: raw/ interim/ processed/ cache/ unter data_root; reference_root nur lesend
  io.py                   atomic_write, read/write JSONL, CSV, Manifest, Stamp
  http.py                 Session-Factory: Timeout, Retry mit Backoff, User-Agent, requests-cache
  models.py               Paper, POI, DistrictStreets, SearchTerm…: pydantic an der Grenze, dataclass/TypedDict innen
  sources/  oparl.py opendata.py osm.py wiki.py      fetch_*(transport, params) -> Modelle; Transport injizierbar; osm.py fragt Overpass direkt
  geo.py                  shapely + pyproj: GeoJSON lesen, nach EPSG:4326 projizieren, STRtree-Zuordnung Punkt -> Bezirk
  prep/     papers.py voters.py streets.py wiki.py   reine Funktionen pl.DataFrame -> pl.DataFrame (Polars, LazyFrame wo es Pushdown bringt)
  search/   dictionary.py matcher.py index.py         KeywordMatcher-Protokoll, FlashText-Implementierung
  analysis/ hits.py regression.py                     Notebook-Mathematik als Modul, Notebook wird dünn
  pipeline.py             Schrittregister: Name, Eingaben, Ausgaben, run(); Frische, --force, --dry-run
  cli.py                  argparse, main(argv) -> int; Unterbefehle run, steps, status, bootstrap, profile
tests/  conftest.py  unit/  property/  golden/  fixtures/mini/  fixtures/http/
reference/                heutiges data/, eingefroren: der Datensatz der Arbeit, nie beschrieben
docs/                     baseline, Entscheidungen, Profiling-Ergebnisse (datiert)
noxfile.py                Sessions lint, typecheck, test, golden, verify, profile; CI ruft dieselben
.github/workflows/ci.yml  uv sync --locked, nox; Actions per SHA gepinnt
```

Paketname `georep`, weil der Code über Düsseldorf hinaus verwendet werden soll. Die Umstellung
läuft als Strangler Fig: `src/georep/` wächst neben `src/*.py`, alte Module werden Shims, dann gelöscht.

### 3.2 Settings

Format: TOML, nicht YAML (geändert 2026-10-11 nach Blick auf bubatzblick: dort `config/pipeline.toml`,
gelesen mit `tomllib`, Modelle pydantic, Wurzel `BaseSettings` mit Env-Präfix und `__` als
Verschachtelung; die Begründung jeder Zahl steht als Kommentar neben ihr). Kein pyyaml nötig.

```toml
# settings.toml (eingecheckt; Defaults relativ zum Repo)
data_root = "./data"                 # Laufzeitdaten, gitignored
cache_root = ""                      # leer = data_root/cache
reference_root = "./reference"       # nur lesen
contracts = "on"                     # on | off; off = deal.disable()
log_level = "INFO"

[period]
start = 2020-09-13
end = 2025-09-14

[sources.oparl]
endpoint = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers"
delay_s = 1.0                        # der Server ist langsam, nicht wir; Downloads seriell
timeout_s = 180                      # 85 s pro Seite gemessen am 2026-10-09
retries = 5

[sources.wikidata]
entity = "Q1718"
language = "de"
geosearch_limit = 500

[geo]
working_crs = "EPSG:25832"           # metrisch rechnen, wie bubatzblick; Eingabe ist EPSG:4647
output_crs = "EPSG:4326"             # genau eine Reprojektionsstelle, always_xy

[schema]                             # Spaltennamen der Quellen, heute hart kodiert
district_id = "Kommunalwahlbezirk Nr."
precinct_id = "Stimm-/ Wahlbezirk"

[schema.results]
sep = ";"
encoding = "latin-1"
district = "Kommunalwahlbezirk"
eligible = "Wahlberechtigte_insgesamt"
voters = "Waehler"

[search]
exclude = ["Düsseldorf", "Düssel", "Stadtbezirk 1"]   # gekürzt
generic_terms_count = true           # heute zählt "schulweg", wird nur nicht angezeigt
```

```toml
# settings.local.toml (gitignored), Konrads Rechner
data_root = "/media/konrad/xtraspace/georep/data"
```

Auflösung: Defaults < `settings.toml` < `settings.local.toml` < `GEOREP_*` (verschachtelt mit `__`)
< `--settings pfad`. Pfade werden expandiert und bei Bedarf angelegt, nie geleert.

### 3.3 Caching und Datenhaltung

| Quelle | Cache | Schlüssel | Invalidierung |
|---|---|---|---|
| OParl-Seiten | requests-cache (SQLite unter `cache_root/http.sqlite`) | URL | TTL kurz (Entwicklung); Metadaten selbst werden pro Paper gespeichert, Seiten sind keine stabilen IDs |
| OParl-Metadaten | `raw/papers.jsonl`, eine Zeile pro Paper | OParl-ID | inkrementell: Seiten sind neueste zuerst, Abbruch sobald Datum < start; bekannte IDs werden übersprungen |
| PDFs | `cache_root/pdf/<sha1(url)>.pdf` + `manifest.jsonl` (url, sha256, Größe, HTTP-Status, Zeit) | URL | nie; Prüfung `%PDF`-Magic und Größe > 0; defekte Einträge werden neu geladen |
| Text je PDF | `cache_root/text/<sha256(pdf)>.txt` | Inhalt des PDF | nie; neue Extraktor-Version = neuer Schlüsselpräfix |
| OSM | osmnx-Cache eingeschaltet unter `cache_root/osmnx` + Ergebnis je Stimmbezirk unter `raw/streets/<geom-hash>.json` | Geometrie-Hash | manuell (`--force`) |
| Wikidata/Wikipedia | requests-cache + `raw/pois.jsonl` | Query bzw. BBox | TTL 30 Tage |
| Schritte | `<ausgabe>.stamp.json` mit Hashes der Eingaben, Settings-Hash, Code-Version und `schema_version` des Schritts | alle vier | automatisch, wenn einer sich ändert; `schema_version` wird von Hand erhöht, wenn sich Spalten oder Zeilenformat der Ausgabe ändern (Lehre bubatzblick 2026-09-28: ein Cache, der sein eigenes Ausgabeschema nicht kennt, übernimmt alte Zellen still) |

Formate: alles Abgeleitete als Parquet (zstd), gelesen mit `pl.scan_parquet`, Sortierung deterministisch.
Append-only-Protokolle (Roh-Metadaten je Paper, PDF-Manifest) bleiben JSONL, weil eine Parquet-Datei
unveränderlich ist; `prep` verdichtet sie zu Parquet. Der Korpus liegt als `interim/papers.parquet`
(Spalten id, date, paper_type, text) und wird mit Projektion gelesen, wo der Text nicht gebraucht wird.
CSV nur als Export für Menschen (`georep export`). Referenzdaten bleiben im Upstream-Format,
`bootstrap` konvertiert sie beim Kopieren.

### 3.4 Sicherheit: was „nichts geht kaputt" konkret heißt

1. Die Pipeline schreibt nie unter `reference_root`; ein Test prüft das (Verzeichnis read-only einhängen, Lauf, kein Fehler).
2. Jeder Schreibvorgang: Temporärdatei im Zielverzeichnis, `fsync`, `os.replace`. Ein Abbruch hinterlässt die alte Datei.
3. Jeder Schritt hat Vor- und Nachbedingungen: Eingaben vorhanden und nicht leer, Pflichtspalten da; Ausgabe nicht leer, Zeilenzahl plausibel. Verletzung = Abbruch vor dem Schreiben. Beispiel: `prep_papers` verweigert, wenn null PDFs vorliegen oder das Ergebnis weniger Texte hätte als die bestehende Ausgabe.
4. Wiederholung ohne Änderung ist ein No-op und sagt das (`übersprungen: 6 Schritte aktuell`).
5. `--dry-run` zeigt den Plan, `--force` erzwingt, `clean` löscht nur unter `data_root` und nennt vorher, was.
6. Netz: Timeout auf jedem Aufruf, Retry mit Backoff, Fehler pro Element isoliert, Fehlerzähler im Ergebnis, Teilergebnis bleibt erhalten, Exit-Code ungleich null ab einer Fehlerquote.
7. Keine `except Exception` mehr: Domänenfehler (`FetchError`, `CorruptPdfError`, `SchemaError`) werden behandelt, Vertragsverletzungen sind Bugs und laufen durch.
8. Deterministische Ausgaben (sortierte Begriffe und IDs), damit Golden-Vergleiche byteweise möglich sind.

### 3.5 Heiße Pfade und Rust (Stand 2026-10-11, nach Phase 5)

Geo-Schicht ist fertig (`georep.geo`: shapely, pyproj, STRtree, Arbeits-CRS EPSG:25832, eine Rückprojektion).

Heiße Pfade und ihre Nähte:

- Matcher: `georep.search.matcher.KeywordMatcher` (Protokoll: `add_terms`, `extract(text) -> set[str]`),
  Implementierung `FlashTextMatcher` (reines Python, FlashText 2.7 von 2018). Vertrag als Orakel in
  `tests/property/oracle_matcher.py` (längster Treffer an Wortgrenzen, Umlaute sind Grenzen, Terminator wird
  verbraucht); jeder Ersatz muss `tests/property/test_matcher_contract.py` bestehen. Gemessen am 2026-10-11:
  4,1 s für 5841 Begriffe über 19108 Dokumente (Schritt `index`), davon 3,8 s Eigenzeit in FlashTexts
  `extract_keywords`, reines Python; der einzige heiße Pfad der Offline-Kette (6,3 s gesamt).
- Extraktion: `georep.prep.extract` hinter dem Protokoll `PdfTextExtractor` (`name` ist der Cache-Schlüssel im
  Textstore, `extract(path) -> str` der rohe Text aller Seiten); `PypdfExtractor` ist die Implementierung der
  Arbeit (Phase 5). Gemessen am 2026-10-11 über 200 PDFs: 38 ms je PDF, 17 ms je Seite, hochgerechnet 12 min
  für alle 19108; der Abruf mit 1 s Pause ist dreißigmal teurer. pypdf 6.20.0 reproduziert 197 von 200 Texten
  der Arbeit zeichengleich, der Index danach ist byteidentisch.
- Aggregation und Index-Join: Polars, je unter 0,1 s; gemessen, unkritisch.

Messung und Empfehlung stehen in `docs/profiling/README.md` (2026-10-11): kein Flaschenhals, den Python nicht
in Sekunden erledigt; pypdf und FlashText bleiben, kein Rust-Port, solange der Index nur einmal je
Datenänderung läuft. Kandidaten, falls sich das ändert: `pyahocorasick` (C, liefert überlappende Treffer, die
nachgefiltert werden müssten) oder ein PyO3-Modul auf `aho-corasick` (maturin, optionales Extra, Crate-Name
ungleich Modulname); `pypdfium2` oder `pymupdf` nur, wenn Treue zu den Texten der Arbeit nicht mehr zählt.
Python bleibt Orakel. cargo 1.98 ist installiert, maturin nicht.

## 4. Phasen

Jede Phase läuft auf einem Branch `refactor/phase-<n>`, endet mit der Definition of Done aus § 2 und nach dem Merge nach `main` mit einem Tag `v0.<n+1>.0` (Phase 0 → `v0.1.0`).

### Phase 0: Netz spannen (keine Verhaltensänderung) — abgeschlossen 2026-10-11, `v0.1.0`

1. `pyproject.toml` ohne Umzug: `[tool.uv] package = false`, Abhängigkeiten aus den Pins, `dependency-groups.dev` (ruff, mypy, pandas-stubs, types-requests, pytest, pytest-cov, syrupy, hypothesis, deal, nox), `[tool.ruff]` (E F I UP B, line-length 100, target py314), `[tool.mypy]` (strict, Overrides mit Begründung für geopandas, osmnx, shapely, flashtext, loguru, pandas im Altcode), `[tool.pytest.ini_options]` (`testpaths`, `--strict-markers`, Marker `slow`, `network`). `.python-version` 3.14, `uv.lock`, `requirements.txt` entfällt. Polars, pydantic, pydantic-settings kommen dazu; pandas, geopandas, osmnx, scikit-learn bleiben als markierte Altlast, bis Phase 3 sie entfernt.
2. venv-Ort: `UV_PROJECT_ENVIRONMENT=/media/konrad/xtraspace/venvs/georep` dokumentiert in README und `.envrc`; der heutige Symlink `.venv` entfällt.
3. Charakterisierungstests (`tests/golden/`, mit Polars geschrieben): Offline-Kette auf `reference/` gegen `wahlbezirke_auswertung.csv` (Treffer je Wahlbezirk exakt, Quoten `approx`), invertierter Index als Menge von (Begriff, sortierte IDs), Regressionskennzahlen auf vier Nachkommastellen (Tabelle 5). Kleine Fixture `tests/fixtures/mini/` (200 Dokumente, 3 Wahlbezirke, deterministisch aus `reference/` erzeugt, Skript liegt bei) für Tests unter 2 s; der volle Lauf als `slow`.
4. Drei bis fünf kleine echte PDFs (je unter 150 KB) als Fixtures für `get_text_from_pdf` und den `betrifft`-Schnitt; einmalig geladen, eingecheckt, Herkunft dokumentiert.
5. CI am ersten Tag: GitHub Actions, `uv sync --locked`, `nox -s lint typecheck test`; Push eines trivialen Commits und zusehen.
6. Mechanik, je ein Commit, in `.git-blame-ignore-revs`: `ruff check --select UP --fix` (4), `ruff check --fix` nur sichere Fixes (23), `ruff format` (14 Dateien).
7. `STATUS.md` und `CLAUDE.md` (Arbeitsregeln für Agenten: Befehle, was nie laufen darf, wo Daten liegen).

### Phase 1: Risiken schließen (kleine, einzeln begründete Verhaltensänderungen, je mit rotem Test zuerst) — Code fertig 2026-10-11

Vorgezogen aus Phase 2: das Paket `src/georep/` mit `uv_build`, weil die neuen Helfer (`io`, `http`, `errors`) einen strict-typisierten Ort brauchten. Dazugekommen gegenüber der Liste: Nicht-PDF-Antworten abweisen, unlesbarer lokaler Metadatenstand ist ein Fehler, Metadaten-Download wirft statt still zu verkürzen.

1. Timeouts, Session mit Retry/Backoff, User-Agent (schließt B113 ×4).
2. `atomic_write` und Einsatz in allen Schreibstellen.
3. Guards: `prep_papers` ohne PDFs, leere Ergebnisse in `reverse_index` und `analyse`, Pflichtspalten in `prep_voters`.
4. Download-Schleife: Fehler pro Datei, Zähler, Weiterlaufen.
5. `response.content` statt latin-1-Text schreiben.
6. Deterministische Sortierung der Ausgaben.
7. `TARGET_ENTITY` in die SPARQL-Query verdrahten (für Q1718 verhaltensneutral).
8. Logging konfigurierbar statt beim Import auf DEBUG.

### Phase 2: Struktur (Strangler Fig, eine Refactoring-Sorte pro Commit) — abgeschlossen 2026-10-11

Abweichungen: Settings in TOML (§ 3.2). Bootstrap kopiert nur; der Schritt `corpus` wandelt das Altformat.
OParl 1.1 ist als pydantic-Modell mit echter Fixture vertraglich festgehalten (`georep.oparl`), auf Konrads
Frage hin vorgezogen. Extract Function auf den drei C-Funktionen des Altcodes entfiel: `index_documents`
ist durch `georep.search.index` ersetzt, `download_paper_metadata` und `get_streets_per_district` werden in
Phase 3 neu geschrieben. Die Altmodule der Offline-Kette sind gelöscht, nicht nur verhüllt; der Golden
Master sind die eingefrorenen Ausgaben in `tests/fixtures/mini/expected` und `reference/processed`.

1. `[project.scripts]` und Shims; `src/georep/` mit `uv_build` existiert seit Phase 1.
2. `settings.py` + `settings.toml` + `settings.local.toml`; `config.py` wird Shim und stirbt zuletzt.
3. `layout.py`; `data/` → `reference/` (git mv); `data_root` gitignored; `georep bootstrap` kopiert Rohdaten und Korpus aus `reference/` nach `data_root`, damit die Offline-Kette ohne Netz läuft.
4. Modelle (`models.py`), Spaltennamen aus den Settings, drei Module ohne hart kodierte Schlüssel. Jedes nach `georep` gezogene Modul ist Polars-nativ; der Golden Master belegt die Gleichheit mit dem pandas-Altcode.
5. Schrittregister `pipeline.py` mit Eingaben/Ausgaben/Stamps; `cli.py` mit `run`, `steps`, `status`, `bootstrap`, `--dry-run`, `--force`.
6. Extract Function auf den drei C-Funktionen; Parameter Objects, wo vier Werte gemeinsam reisen.
7. `mypy --strict` ohne Fehler für `georep`; Legacy-Shims unter Override, bis sie weg sind.
8. Notebook-Mathematik nach `analysis/regression.py` mit numpy und `scipy.stats.linregress`; scikit-learn entfällt (es lieferte nur ein zweites R²). Notebook ruft nur noch auf.

### Phase 3: Fetch- und Cache-Schicht — abgeschlossen 2026-10-11

Abweichungen: der Textstore ist eine Parquet-Datei statt je Dateiname eine Datei (19108 Dateien mit fsync
kosteten 143 s); Straßen werden nicht je Geometrie-Hash gecacht, sondern über requests-cache je Overpass-
Abfrage (POST-Body als Schlüssel), was dasselbe leistet; `texts` ist ein Offline-Schritt mit dem
PDF-Manifest als Eingabe. Der Vertrag mit OParl (`georep.oparl`) kam schon in Phase 2. Treue der neuen
Quellen gegen die Referenz: `tests/fixtures/http/README.md`.

1. `http.py`: Session-Factory, requests-cache, `Transport`-Protokoll; `FakeTransport` liefert aufgezeichnete Antworten aus `tests/fixtures/http/` (einmal real aufgenommen, klein geschnitten).
2. PDF-Store mit Manifest; `--limit`, `--since`; Parallelität konfigurierbar, Standard sequenziell mit `delay_s` (der Server ist langsam, nicht wir).
3. Text-Store je PDF-Hash; Korpus als JSONL; `prep_papers` wird inkrementell.
4. OParl inkrementell (neueste zuerst, Abbruch unter `start`); `modified_since` ausprobieren und dokumentieren, ob der Server es kann.
5. Straßen per Overpass je Stimmbezirk, Ergebnis je Geometrie-Hash gecacht; POIs per shapely-STRtree statt Schleife; danach osmnx, geopandas, pandas, scikit-learn aus `pyproject.toml` entfernen und den Lockfile-Check in CI aktivieren.
6. Netz-Integrationstests als `network`, nicht in CI; ein `georep status` zeigt Cache-Füllstände mit Zahlen.

### Phase 4: Tests ausbauen — abgeschlossen 2026-10-11

Abweichungen: Snapshots nur für `georep steps` und die PDF-Texte (die Golden-Frames vergleichen
`polars.testing.assert_frame_equal`, dafür braucht es kein syrupy). Mutationstests vertagt, weil mutmut 3
forkt und Polars im Kind blockiert (`docs/mutation-2026-10-11.md`). Dazugekommen: das Matcher-Orakel in
`tests/property/oracle_matcher.py` als Spezifikation für jeden Ersatz-Matcher (Phase 5).

1. Unit-Tests für reine Funktionen (Wörterbuchaufbau, Normalisierung, Aggregation, Zuordnung).
2. hypothesis-Eigenschaften: `expand_street_names` ist idempotent, Obermenge, kleingeschrieben; jeder POI landet in höchstens einem Bezirk; Summe über Stimmbezirke gleich Wahlbezirk; jede ID im Index kommt im Korpus vor; `anzahl_treffer` gleich Mächtigkeit der ID-Menge; Trefferquote ≥ 0.
3. Golden Master als `syrupy`-Snapshots, klein, mit Diff-Pflicht; Frame-Vergleiche über `polars.testing.assert_frame_equal`.
4. Coverage als Untergrenze (`--cov-fail-under=80` für `georep`), nicht als Ziel; `mutmut` auf `search/` und `analysis/` einmal pro Phase, nicht als Gate.

### Phase 5: Profiling-Infrastruktur — abgeschlossen 2026-10-11

Ergebnis (2026-10-11): alle vier Schritte umgesetzt, Zahlen und Empfehlung in `docs/profiling/README.md`. Die
Entscheidung über einen Ersatz fällt gegen den Austausch aus, solange nichts Neues gemessen wird: pypdf und
FlashText bleiben, kein Rust. Abweichungen: `.prof`-Dateien sind gitignored (rechnerspezifisch), die Zahlen
stehen im README; `nox -s bench` legt beim ersten Lauf nur die Baseline an, weil pytest-benchmark
`--benchmark-compare-fail` ohne Vergleichslauf als Bedienfehler behandelt; die Schwelle ist 20 % statt 10 %,
weil 10 % unter dem gemessenen Rauschen der Millisekunden-Stufen lagen (12,7 % ohne Codeänderung); ein Nebenbefund (`.gitignore` las
Kommentare hinter Mustern als Teil des Musters) ist behoben.

Werkzeuge noch nicht in der Dev-Gruppe (mit `uv add --group dev …` aufnehmen): `pytest-benchmark`,
`snakeviz`; bei Bedarf `line_profiler`, `scalene`, `memray`, `py-spy` (Reihenfolge und Aufrufe: Skript,
Kapitel Profiling). PDF-Stichprobe ohne stundenlangen Abruf: `uv run georep fetch pdfs --limit 200`
(Metadaten kommen aus `bootstrap`, 200 Dateien seriell mit 1 s Pause, rund 5 Minuten; die vier PDFs unter
`tests/fixtures/pdf/` reichen für Benchmarks, nicht für Profile).

1. `georep profile <schritt>`: cProfile nach `docs/profiling/<datum>-<schritt>.prof`, `snakeviz` als Anzeige;
   `nox -s profile -- <schritt>`. Profiliert wird der echte Schritt über `build_steps`, nicht ein Nachbau.
2. `pytest-benchmark` für Matcher über die Mini-Fixture (`tests/fixtures/mini`), Extraktion je PDF, Aggregation
   und Index-Join; `--benchmark-autosave`, Vergleich gegen gespeicherte Baseline, Fail bei Verschlechterung über
   10 %; `.benchmarks/` ist gitignored, die Baseline-Zahlen stehen datiert in `docs/profiling/README.md`.
3. `PdfTextExtractor`-Protokoll einziehen (siehe § 3.5), damit der Austausch ein Austausch ist.
4. Erstes datiertes Ergebnis in `docs/profiling/`: Verteilung der Laufzeit eines vollen Offline-Laufs und einer
   Extraktion über die 200 PDFs. Danach erst die Entscheidung über pyahocorasick, pypdfium2 oder Rust; ein
   Ersatz-Matcher muss das Orakel bestehen, ein Ersatz-Extraktor den Golden Master der vier Fixture-PDFs
   (`tests/unit/__snapshots__/test_extract.ambr`) oder seine Abweichung dokumentieren.

### Phase 6: Design by Contract

Voraussetzungen sind da: `deal` und `crosshair-tool` stehen in der Dev-Gruppe, `settings.contracts` („on"/„off")
existiert, wird aber noch nirgends gelesen. `deal test` ist mit typeguard 4 kaputt (Skript, Stand 2026-09-25);
Testgenerierung läuft über `deal.cases` in pytest und `crosshair check`.

1. `deal` auf den reinen Funktionen in `georep.search` (`normalise_terms`, `build_dictionary`, `build_index`),
   `georep.prep` (`aggregate_voters`, `clean_pois`, `streets_by_district`, `after_marker`), `georep.analysis`
   (`hits_by_district`, `join_voters`, `regress`), `georep.geo` (`PrecinctIndex.locate`, `overpass_polygon`) und
   `georep.layout` (`guard_writable`): `@deal.pre` (nicht leer, Pflichtspalten, Begriffe kleingeschrieben und ohne
   Komma, Arbeits-CRS metrisch), `@deal.post`/`@deal.ensure` (Längen, Teilmengen, Nichtnegativität, Sortierung),
   `@deal.pure` wo zutreffend, `@deal.raises(FetchError, …)` an den Fetchern in `georep.sources`, `@deal.inv` auf
   `PaperStore` und `TextStore`. Die hypothesis-Invarianten aus Phase 4 sind die Vorlage für die Nachbedingungen.
2. Verträge an Batch-Grenzen, nicht pro Dokument in der heißen Schleife; `settings.contracts = "off"` ruft
   `deal.disable()` beim Start (CLI), gemessener Overhead steht in `docs/`.
3. `deal.cases` in pytest, damit hypothesis die Verträge direkt angreift; `crosshair check` als `nox -s verify` auf
   die rein-pythonischen Module (`oracle_matcher`, `after_marker`, `parse_point`, `cache_pattern`, `deep_merge`)
   mit `--report_all` (ein Nicht-Fund ist nur eine Zeitangabe). Polars-Funktionen bekommen nur Laufzeitverträge
   plus hypothesis; crosshair kann keine Rust-Erweiterung symbolisch ausführen.
4. Pydantic bleibt an der Systemgrenze (OParl, Records, Settings), Verträge im Inneren; die Abgrenzung wie im
   Skript. Mutationstests erneut versuchen, diesmal mit `pytest-gremlins` oder `fest` (`docs/mutation-2026-10-11.md`).

### Phase 7: Abschluss

1. README aus Sicht eines frischen Klons (drei Befehle), Systemabhängigkeiten (keine erwartet; geopandas-Wheels bringen pyogrio/pyproj mit), Datenherkunft, Lizenz CC0 bleibt.
2. Plan durch Beschreibungen ersetzen: `docs/architecture.md`, `docs/decisions.md` mit verworfenen Alternativen und Kosten, `CHANGELOG.md`.
3. Optional ein Pull Request an `lubar102` mit den risikoschließenden Änderungen aus Phase 1, falls gewünscht.

## 4a. Lehren aus bubatzblick (gesichtet 2026-10-11)

Konrads Geo-Pipeline für Sichtfelder löst verwandte Aufgaben; übernommen wird:

- **Konfiguration** wie dort: TOML plus pydantic `BaseSettings`, Env-Präfix, Begründungen als Kommentar neben der Zahl (§ 3.2).
- **Ein metrisches Arbeits-CRS, eine Reprojektionsstelle, `always_xy=True`**; Treue der eigenen Projektion gegen pyproj-Referenzpunkte testen, falls je eine eigene Implementierung entsteht (§ 3.5).
- **Cache-Schlüssel enthalten Parameterversion und Ausgabeschema**; ein Manifest weist eine Wiederaufnahme bei geänderten Eingaben ab, statt alte Teile still für fertig zu halten; Vollständigkeitsmarken (`.stamp`) statt geratener Dateinamen; Parquet-Metadaten tragen den Schlüssel (§ 3.3).
- **Downloads seriell**, Timeout 180 s, wenige Versuche mit wachsender Wartezeit, Prüfsumme oder Magic-Bytes vor dem Übernehmen, atomar über Geschwisterdatei (Phase 3).
- **Rust als Austausch, nicht als Umbau**: Python bleibt Orakel (`tests/test_rust_vs_reference.py`), Toleranzen werden gemessen und mit Luft als Schranke festgeschrieben, Begründung steht im Test; PyO3 + maturin für das Testorakel, Crate-Name ungleich Modulname; für den Keyword-Matcher ist der Vertrag Mengengleichheit, nicht Toleranz (Phase 5).
- **Tests**: `pytest -n auto` (xdist), hypothesis mit kalibrierten Schranken und ausgeschriebener Begründung, Golden-Läufe auf winzigen Fixtures, Vertragstests mit Namen, die die Eigenschaft nennen (Phase 4, 6).
- **Polars-Entscheidung dort**: geopandas blieb, weil jede Tabelle Geometrie trägt; Polars für rein tabellarische Stufen. Hier ist Geometrie klein (306 Polygone, 2010 Punkte) und gehört in shapely, alle Tabellen in Polars; GeoParquet wird nicht gebraucht.
- **Ein Lauf druckt die Zahl, auf die er gewirkt hat**, und ein Veröffentlichungsschritt steht hinter einer Prüfkette mit atomarem Tausch (§ 3.4, Regel 4 und 6).

Nicht übernommen: Make als Orchestrierung (nox reicht, keine a priori unbekannten Ausgabemengen), PBF-Diffs (wir fragen Overpass je Polygon), Kachelstufen.

## 5. Aufwand (grob, in Arbeitssitzungen von zwei bis drei Stunden)

| Phase | Sitzungen |
|---|---|
| 0 Netz | 1 |
| 1 Risiken | 1 |
| 2 Struktur | 2 |
| 3 Fetch/Cache | 2 |
| 4 Tests | 1–2 |
| 5 Profiling | 1 |
| 6 DbC | 1–2 |
| 7 Abschluss | 0,5 |

## 6. Entscheidungen, die vor Phase 0 feststehen sollten (mit Vorschlag)

| Frage | Vorschlag | Alternative und Kosten |
|---|---|---|
| Paketname | `georep` | `grd`, `geographic_representation`; nur Benennung, später teuer zu ändern |
| Python | 3.14 (Konrad, 2026-10-10), an drei Stellen (`requires-python >=3.14`, `.python-version 3.14`, `mypy python_version`) | 3.15: kompilierte Abhängigkeiten (numpy, scipy, shapely, pydantic-core, polars) liefern Wheels erst Wochen bis Monate nach dem Release; 3.13 verschenkt ein Jahr |
| DataFrames und Format | Polars, Parquet für alles Abgeleitete (Konrad, 2026-10-10) | pandas und CSV: größere Verbreitung, aber langsamer, kein Lazy/Pushdown, Typen schwächer |
| Geo-Schicht | shapely + pyproj + Overpass direkt (Phase 3) | geopandas/osmnx: weniger eigener Code, aber pandas als Pflichtabhängigkeit und ein Graphaufbau für eine Namensliste |
| Datenlayout | `data/` → `reference/` (eingefroren), Laufzeit in `data_root` außerhalb des Repos | `data/` behalten und beschreiben lassen: jeder Lauf erzeugt Diffs, Fehlläufe überschreiben die Arbeit |
| Settings-Format | TOML über pydantic-settings (geändert 2026-10-11, Muster bubatzblick) | YAML (pyyaml als Abhängigkeit, kein Vorbild in Konrads Repos); JSON (keine Kommentare) |
| Verträge | `deal` | `icontract` hat besseres Fehlerbild, aber `deal.cases` und crosshair-Pfad fehlen; mischen verboten |
| CLI | `argparse`, `main(argv)` | typer: hübscher, zieht click und rich mit, mypy-Overhead; später austauschbar |
| Automatisierung | `nox` + pre-commit + GitHub Actions | justfile/Makefile: einfacher, aber CI und lokal driften |
| venv-Ort | `UV_PROJECT_ENVIRONMENT` auf xtraspace | `.venv` im Repo auf der vollen Primärplatte (4,7 GB frei) |
| Upstream-PR | nicht geplant | bei Interesse Phase-1-Änderungen als PR; Lukas' Entscheidung |

## 7. Risiken des Refactorings selbst

- Der Golden Master deckt nur die Offline-Kette; die Fetch-Schicht wird gegen aufgezeichnete Antworten getestet, der echte OParl-Server ist langsam und verändert sich täglich. Netztests bleiben manuell.
- pandas 3.0 (Copy-on-Write, String-Dtype) ist jung; Pins bleiben über `uv.lock` eingefroren, Upgrades sind bewusste Commits mit grünem Golden Master.
- crosshair kann keine C-Erweiterungen symbolisch ausführen; es prüft nur die rein-pythonischen Module. Das ist eine Einschränkung, keine Lücke im Netz.
- `deal`-Dekoratoren mit `lambda` sind für mypy blind; Verträge werden zusätzlich durch hypothesis-Tests mit echten Typen abgedeckt.
- FlashText ist unbetreut; das Protokoll in § 3.5 ist die Versicherung dagegen.
- Polars 2.0.0 ist vom 2026-10-06, vier Tage alt. Pin `polars>=2,<3`; sollte ein Blocker auftauchen, ist 1.x die Rückfallebene, die API-Unterschiede sind klein und das Lockfile macht den Wechsel zu einem Commit.
- crosshair auf Python 3.14 ist nicht gesichert; die nox-Session `verify` darf auf 3.13 laufen, der Rest auf 3.14.
- Verworfen: pandas (Vorgabe Konrad); DuckDB (Polars deckt den Bedarf, eine Abhängigkeit weniger); Hydra/OmegaConf für Settings (für eine Pipeline mit einem Lauf zu schwer); `requests` durch `httpx` ersetzen (kein Gewinn).
