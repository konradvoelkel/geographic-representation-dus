# Entscheidungen

Jede Entscheidung mit Datum, Begründung und den verworfenen Alternativen samt ihren Kosten. Was daraus
gebaut wurde, beschreibt [architecture.md](architecture.md). Reihenfolge: grob chronologisch.

## 1. Umbau statt Neuschreiben, Verhalten zuerst einfrieren (2026-10-10)

Der Code der Bachelorarbeit lief und reproduzierte Tabelle 5. Reihenfolge: verstehen, zum Laufen bringen,
Verhalten einfrieren (Charakterisierungstests, Golden Master), modernisieren, umbauen; eine
Refactoring-Sorte pro Commit, Formatierung und Modernisierung in `.git-blame-ignore-revs`. Verworfen:
Neuschreiben ohne Netz. Kosten: man weiß erst am Ende, ob die Ergebnisse noch stimmen.

## 2. Paketname `georep`, Python 3.14 (2026-10-10)

`georep`, weil der Code über Düsseldorf hinaus verwendbar sein soll (OParl-Body, Entität, Spaltennamen sind
Settings). Python 3.14 an drei Stellen (`requires-python`, `.python-version`, mypy). Verworfen: 3.15, weil
kompilierte Abhängigkeiten (numpy, scipy, shapely, pydantic-core, polars) Wheels erst Wochen bis Monate nach
dem Release liefern; 3.13 verschenkt ein Jahr.

## 3. Polars und Parquet statt pandas und CSV (Konrad, 2026-10-10)

Alle Tabellen Polars, alles Abgeleitete Parquet (zstd) mit Schema-Version in den Metadaten; CSV nur als Export
für Menschen. Der Golden Master belegt die Gleichheit mit dem pandas-Altcode. Verworfen: pandas und CSV
(größere Verbreitung, aber langsamer, kein Lazy, schwächere Typen); DuckDB (Polars deckt den Bedarf, eine
Abhängigkeit weniger). Die nox-Session `deps` verbietet pandas im Lockfile, damit es nicht zurückkommt.

## 4. `data/` wird `reference/` und wird nur gelesen (2026-10-11)

Der Datensatz der Arbeit ist eingefroren; Läufe schreiben nach `data_root` außerhalb des Repos,
`guard_writable` verweigert jeden Pfad unter der Referenz. Verworfen: `data/` behalten und beschreiben
lassen, wie im Original. Kosten dort: jeder Lauf erzeugt Diffs, ein Fehllauf überschreibt die Arbeit.

## 5. Settings in TOML über pydantic-settings (2026-10-11, nach Blick auf bubatzblick)

`defaults.toml` im Paket mit einer Begründung neben jeder Zahl, darüber `settings.toml`,
`settings.local.toml`, `--settings`, Umgebung `GEOREP_*`; tiefer Merge, unbekannte Schlüssel sind ein Fehler.
Verworfen: YAML (pyyaml als Abhängigkeit, kein Vorbild in Konrads Repos); JSON (keine Kommentare);
Hydra/OmegaConf (für eine Pipeline mit einem Lauf zu schwer).

## 6. OParl 1.1 als pydantic-Vertrag an der Grenze (2026-10-11)

Antworten werden gegen typisierte Modelle geprüft, eine echte Antwort liegt als Fixture bei, und ein Test
schlägt an, sobald der Server unbekannte Schlüssel liefert. Verworfen: `.get()`-Ketten auf dicts (das
Original). Kosten: ein Modell je Objekt; Gewinn: der Rest des Codes arbeitet mit Typen.

## 7. Geometrie mit shapely und pyproj, Straßen direkt von Overpass (2026-10-11)

Ein metrisches Arbeits-CRS (EPSG:25832), `always_xy=True`, eine Rückprojektionsstelle, `make_valid` statt
`buffer(0)`, STRtree statt Schleife über 306 Polygone; der Overpass-Filter bildet `network_type="all"` von
osmnx nach, damit die Referenz reproduziert wird. Verworfen: geopandas und osmnx (weniger eigener Code, aber
pandas als Pflichtabhängigkeit und ein Graphaufbau für eine Namensliste). GeoParquet wird nicht gebraucht,
die Geometrie ist klein (306 Polygone, 2010 Punkte) und gehört in shapely.

## 8. Ein Textstore als eine Parquet-Datei (2026-10-11)

Alle extrahierten Texte in `cache/text/texts.parquet`, Schlüssel Dateiname, Frische über Extraktorname und
PDF-Hash. Verworfen: eine Datei je Text, wie geplant. Gemessen: 19 108 Dateien mit je zwei fsync kosteten
143 s, eine Datei unter einer Sekunde.

## 9. Straßen über requests-cache statt Geometrie-Hash (2026-10-11)

Die Overpass-Antwort wird im HTTP-Cache mit dem POST-Body als Schlüssel gehalten (30 Tage), das leistet
dasselbe wie ein eigener Cache je Geometrie-Hash und braucht keinen Code. Verworfen: `raw/streets/<hash>.json`.

## 10. Netz, Zeit und Zufall sind Eingaben (2026-10-11)

`Transport`-Protokoll mit Fake-Session und aufgezeichneten Antworten, `sleep` injizierbar, `today` an der
Profiling-Naht, hypothesis-Profile `dev` und `ci`. Netztests tragen den Marker `network` und laufen nie in CI
(der OParl-Server braucht 85 s je Seite). Verworfen: Mocking mit `responses` oder `unittest.mock` auf
`requests` (koppelt Tests an die Bibliothek statt an die Naht).

## 11. Test-Schichten und Golden Master (2026-10-11)

Unit, property (hypothesis), golden (Mini-Fixture mit Erwartung aus dem Altcode `v0.2.0`, volle Referenz als
`slow`), bench. Snapshots (`syrupy`) nur für kleine, stabile Ausgaben (`georep steps`, PDF-Texte); Frames
vergleicht `polars.testing.assert_frame_equal`. Abdeckung ist Untergrenze (90 %), kein Ziel. Das
Matcher-Orakel ist die lesbare Spezifikation des FlashText-Vertrags; hypothesis fand darüber das verbrauchte
Grenzzeichen („köölberg"). Verworfen: Snapshots für ganze Tabellen (schwankend, nie lesbar).

## 12. Mutationstests: mutmut verworfen, pytest-gremlins (2026-10-11)

mutmut 3 startet Arbeiter mit `fork()`, Polars blockiert im Kind, 181 Mutanten endeten alle mit Timeout;
pytest-gremlins läuft mit Subprocess-Executor und liefert 79 % getötete Mutanten in `search/` und
`analysis/`. Verworfen: Polars-Threads nur für ein Werkzeug drosseln, denn das misst nicht das Programm, das
ausgeliefert wird. Mutationstests bleiben einmal pro größerer Änderung, kein Gate
([mutation-2026-10-11.md](mutation-2026-10-11.md)).

## 13. Benchmarks mit pytest-benchmark, Schwelle 20 % im Minimum (2026-10-11)

Vergleich gegen den letzten gespeicherten Lauf; der erste Lauf legt nur die Baseline an. Die geplanten 10 %
lagen unter dem gemessenen Rauschen der Millisekunden-Polars-Stufen (12,7 % ohne Codeänderung über sechs
Läufe); 20 % liegen über allem Gemessenen und fangen jede echte Verschlechterung der heißen Pfade. Das Minimum
rauscht weniger als Median und Mittelwert. `.benchmarks/` und `.prof`-Dateien bleiben lokal, die Zahlen stehen
datiert in [profiling/README.md](profiling/README.md). Als die Verträge zwei 1-ms-Stufen um 33 bis 51 %
verteuerten, war der Gate rot und wurde mit Begründung neu gesetzt.

## 14. pypdf und FlashText bleiben, kein Rust-Port (2026-10-11)

Gemessen: der volle Offline-Lauf dauert 6,3 s, davon 4,1 s der Index (reines Python in FlashText); die
Extraktion kostet 38 ms je PDF, der Abruf mit 1 s Pause ist dreißigmal teurer; pypdf 6.20.0 reproduziert 197
von 200 Texten der Arbeit zeichengleich. Kein Flaschenhals, den Python nicht in Sekunden erledigt. Verworfen,
bis sich das ändert: `pyahocorasick` (C; liefert überlappende Treffer, die nachgefiltert werden müssten) oder
ein PyO3-Modul auf `aho-corasick` (maturin, optionales Extra, Crate-Name ungleich Modulname); `pypdfium2` oder
`pymupdf` (schneller, aber andere Texte als die der Arbeit). Die Nähte dafür stehen: `KeywordMatcher`,
`PdfTextExtractor`; Python bleibt Orakel, für den Matcher ist der Vertrag Mengengleichheit.

## 15. Verträge mit deal, Pydantic an der Grenze (2026-10-11)

deal an den Batch-Grenzen, Prädikate in `georep.contracts`, `settings.contracts` schaltet, Overhead unter
einem Prozent; `deal.cases` und crosshair statt `deal test` (mit typeguard 4 kaputt). Verworfen: `icontract`
(besseres Fehlerbild, aber kein `deal.cases` und kein crosshair-Pfad; mischen verboten); Verträge in heißen
Schleifen (`deal.inv` auf dem Textstore liefe je Dokument quadratisch). Zwei Eigenheiten von deal 4.24.6
bestimmten die Form: `deal.raises` vergleicht exakte Typen, darum wandeln die Fetcher requests-Fehler in
`NetworkError`; der `has()`-Patcher ist nicht reentrant, darum `deal.safe` auf dem rekursiven `deep_merge`.
Nicht upstream gemeldet.

## 16. Domänenfehler am Rand, Vertragsverletzungen laufen durch (2026-10-11)

`GeorepError` und seine Kinder werden an genau einer Stelle gefangen (`cli.main`, Exit 1 mit einer Zeile);
kaputte Quellantworten sind `FetchError`, Netzfehler `NetworkError`, fehlende Streuung in der Regression
`EmptyResultError`, ein leerer Marker ein Settings-Fehler. `deal.ContractError` ist ein Programmierfehler und
wird nicht gefangen. Verworfen: `except Exception` (zwölfmal im Original).

## 17. Werkzeuge: uv, Ruff, mypy strict, nox, pre-commit, GitHub Actions (2026-10-10)

CI ruft dieselben nox-Sessions wie die Hand; Actions per SHA gepinnt, `uv sync --locked`. Verworfen:
justfile/Makefile (CI und lokal driften); typer für die CLI (zieht click und rich, mypy-Overhead; argparse
mit `main(argv)` reicht und ist testbar). `bench`, `verify` und `mutate` laufen nicht in CI: Laufzeit und
Rauschen gehören auf einen Rechner mit Baseline, nicht in einen Gate je Push.

## 18. Konrads Rechner: Umgebung, Cache und Daten auf xtraspace (2026-10-09)

Die Primärplatte ist voll; `UV_PROJECT_ENVIRONMENT` und `UV_CACHE_DIR` zeigen auf `/media/konrad/xtraspace`,
`settings.local.toml` ebenso für `data_root` und `cache_root` ([../FORK-NOTES.md](../FORK-NOTES.md)).
Verworfen: `.venv` im Repo.

## 19. Kein Pull Request an das Original (Konrad, 2026-10-11)

Die risikoschließenden Änderungen aus Phase 1 waren als optionaler PR an `lubar102` vorgesehen. Lukas
Bartzsch arbeitet inzwischen an anderen Projekten; der Fork bleibt eigenständig unter
`konradvoelkel/geographic-representation-dus`, Lizenz CC0 wie das Original.

## 20. Der Plan wird durch Beschreibungen ersetzt (2026-10-11)

Nach Abschluss der sieben Phasen liegt der Plan abgeschlossen unter
[development-plan-2026-10.md](development-plan-2026-10.md) und wird nicht fortgeschrieben; `architecture.md`
beschreibt den Stand, diese Datei die Gründe, `CHANGELOG.md` die Änderungen, `STATUS.md` den Stand und das
Bekannte. Code-Docstrings verweisen auf `architecture.md`, nicht auf Planparagraphen.
