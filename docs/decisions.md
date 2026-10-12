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

## 21. Fundament für den Ausbau in acht Optionen (2026-10-12)

Vor der Implementierung der acht Optionen aus [plan-ausbau-2026-10.md](plan-ausbau-2026-10.md) kamen die
Bausteine auf `main`, die mehrere Pläne gleich brauchten ([plans/00-synergien.md](plans/00-synergien.md), § 3):
die Vorlage als Rahmen plus Abschnittsdateien in Nummernfolge mit einer JavaScript-Schnittstelle und einem
generischen Kartenumschalter (sieben Seitenoptionen hätten sonst dieselbe Datei an denselben Stellen geändert);
ein Register der veröffentlichten Tabellen statt vier parallel gepflegter Listen; `regression_pair` mit
Spaltenname und Ausreißern aus `analysis.exclude_districts` statt des Düsseldorf-Literals `OUTLIERS` im
Berichtsmodell; ein Profil (`profile`) als Unterordner je Stadt oder Periode unter `data_root` und `cache_root`
mit optionalem Periodenende und eigenem Wahltag; ein Crosswalk-Modul mit dem Attribut-Crosswalk und dem
Prädikat „Summe je Wahlbezirk 1"; Achsen-Helfer für Diagramme; Tests, die Schritte und Dateien aus dem Register
zählen statt aus Literalen. Alles reine Umbauten mit byteidentischen Ergebnissen (Golden Master, Snapshot der
Download-Tabelle, `cmp` des Streudiagramms), je ein Commit. Verworfen: die Bausteine in der jeweils ersten
Option entstehen lassen (dann hätten die anderen sieben auf deren Merge gewartet oder dasselbe doppelt gebaut);
ein Fingerprint je Schritt (richtig, aber ein Umbau des Stamp-Mechanismus, zurückgestellt); Paketprofile mit
`--profile` schon jetzt (nur Option 1 braucht sie, `--settings` reicht den Perioden-Optionen). Kosten: neue
Settings-Schlüssel ändern den Fingerprint einmalig, alle Stamps laufen einmal neu (7 s); die Pläne der Optionen
bekamen je einen Abschnitt „Änderungen durch die Synergiephase".

## Punkt: Suche inline, kanonische Begriffe, eigene Combobox (Option 08, 2026-10-12)

Die Berichtsseite bekommt ein Suchfeld „Straße oder Ort". Vier Entscheidungen und ihre Alternativen:

**Die Suchdaten liegen inline in der Seite**, als `<script id="suche-daten" type="application/json">` über
`_json_for_script` (`</` wird `<\/`), 143 641 Byte (gzip 36 665). Die Vorschläge sollen auch aus dem
Dateisystem funktionieren, und `fetch` ist unter `file://` verboten — die Seite sagt das heute schon beim
Dokumentdialog. Verworfen: eine Datei `data/suche.json` nachladen (kein `file://`, und der Nutzen der Suche
liegt gerade im Stöbern ohne Server); eine spaltenweise Kodierung (8 KB weniger, dafür vier Indexzugriffe je
Eintrag, als Reserve notiert, falls das Budget knapp wird). `index.html` wächst damit von 687 KB auf 848 KB
(gzip 141 KB), Budget 1,5 MB.

**Ein Eintrag je kanonischem Begriff, Dokumente vereinigt.** Das Wörterbuch führt zu jedem Begriff mit
`straße` auch die Variante mit `str.` (Verhalten der Arbeit); 1705 solcher Paare würden als zwei Vorschläge
erscheinen. `search_entries` zieht die Abkürzung auf die Langform zusammen, sobald die Langform selbst ein
Begriff ist, und vereinigt die `paper_ids` beider Schreibweisen: ein Dokument mit beiden Schreibweisen zählt
einmal (über die Referenz 30 404 statt 30 880). Kosten: die Zahl im Suchergebnis weicht in 256 von 1705
Fällen von den Zahlen hinter den Begriffs-Schaltflächen ab; das Ergebnis sagt darum „beide Schreibweisen
zusammen". Ein `str.`-Begriff ohne Zwilling bleibt ein eigener Eintrag. Verworfen: beide Schreibweisen
getrennt zeigen (doppelte Vorschläge, Summe statt Vereinigung).

**Eine eigene Vorschlagsliste statt `<datalist>`.** Bei `<datalist>` macht der Browser den Abgleich (Chrome
Teilstring, Safari Präfix, Firefox anders), ohne jede Normalisierung — `str.` fände `straße` nicht, und
„muenchener" nichts. Mit 5841 Optionen wäre das Markup nicht kleiner, und für das Ergebnis (Wahlbezirke,
Dokumente, Markierung) bräuchte es ohnehin das JSON. Die eigene Liste folgt dem Muster „Editable Combobox
with List Autocomplete" der WAI-ARIA Authoring Practices: Fokus bleibt im Feld, `aria-activedescendant` zeigt
auf die aktive Option, die Statuszeile ist `aria-live`. Die Tönung der aktiven Option bleibt unter 3:1 gegen
die Fläche; sie bekommt darum zusätzlich einen Rahmen in `--accent` (WCAG 1.4.11; 4,3:1 hell, 4,8:1 dunkel).

**Präfix und Teilstring auf gefalteten Schlüsseln, keine Fuzzy-Suche.** Jeder Eintrag trägt zwei Schlüssel:
einmal ohne Akzente, einmal mit `ä` als `ae`, damit Tastaturen ohne Umlaute treffen. Drei Ränge (Präfix,
Wortanfang, Teilstring), höchstens acht Vorschläge; ein Durchlauf über 4176 Einträge braucht kein Debounce
und keinen Index. Verworfen: Editierdistanz oder Trigramme (eine Fremdressource oder hundert Zeilen eigener
Code für Tippfehler, die der Teilstring meist schon abfängt).

Die Abkürzungsregel steht einmal, als `STREET_ABBREVIATIONS` in `search/dictionary.py`: das Wörterbuch liest
sie, und der Payload trägt sie ins JavaScript, das damit keine deutsche Regel kennt (Vorbereitung für Option
10; die Umlaut-Faltung bleibt sprachspezifisch im Skript und schadet keiner anderen Sprache). `fold` und
`fold_ascii` stehen als Python-Spiegel in `report/search.py`, und `tests/unit/test_report_js_fold.py` lässt
beide Seiten mit `node` über alle Begriffe der Mini-Fixture laufen; über die Referenz prüft der slow-Test,
dass keine zwei Einträge derselben Art nach dem Falten zusammenfallen.

Die 41 Wahlbezirksnamen sind eigene Einträge der Art `w`, weil „Benrath" in der Ausschlussliste steht und in
keinem Wörterbuch vorkommt, die Suche danach aber zu Wahlbezirk 39 führen soll. Die 50 Stadtteile kommen
erst, wenn der Crosswalk Stadtteil zu Wahlbezirk auf `main` liegt (Option 03 beziehungsweise 05); allein
gebaut gäbe es drei Versionen davon.

## Punkt: Gremien aus der Drucksachennummer (Option 05, 2026-10-12)

Jedes Ratsdokument bekommt das Gremium, das es eingebracht hat, aus seiner Drucksachennummer
(`BV6/108/2023`, `RAT/270/2023`, `OVA/117/2023/1`): das Kürzel vor dem ersten Schrägstrich, bei
Bezirksvertretungen mit der Nummer des Stadtbezirks dahinter. Daraus entstehen je Wahlbezirk sechs
Trefferklassen und die Kennzahlen `anteil_eigene_bv` (dritte Karte) und `quote_eigene_bv`.
Entscheidungen und verworfene Alternativen im Einzelnen in [plans/05-gremien.md](plans/05-gremien.md), § 2.

**Quelle.** Die Drucksachennummer, nicht `paper_type` und nicht die Beratungsfolgen der
OParl-Schnittstelle. Das Muster trifft alle 19 108 Nummern der Referenz. Verworfen: `paper_type` (nur
4 173 Dokumente tragen „Bezirksvertretung" im Typ, 6 847 Dokumente einer Bezirksvertretung heißen
„Antrag" oder „Anfrage"; 21 Dokumente tragen den Typ falsch). Verworfen für jetzt:
`consultation[].organization` (genauer, nennt auch mehrere Gremien je Vorlage, braucht aber einen neuen
Metadaten-Abruf von Stunden; der Parser bleibt der Offline-Weg und der Fallback).

**Unbekannt ist sichtbar.** Kürzel stehen explizit in `[bodies]`; was dort fehlt, heißt „unbekannt" und
erscheint mit seinem Anteil auf der Seite (auf der Referenz 0,0 %). Verworfen: „alles, was nicht Rat und
nicht Bezirksvertretung ist, ist Ausschuss" — das ergibt auf jeder Eingabe 0 % unbekannt und damit keine
Aussage, gerade dann, wenn eine neue Wahlperiode oder eine andere Stadt neue Kürzel bringt. Beiräte
(Jugend-, Integrations-, Senioren-, Behindertenrat, 448 Dokumente) sind keine Ausschüsse des Rates und
bleiben eine eigene Klasse.

**Eigene Bezirksvertretung.** Welche Bezirksvertretung für einen Wahlbezirk die eigene ist, folgt aus den
Stadtbezirken seiner Stimmbezirke, gewichtet über die Wahlberechtigten (`crosswalk.unit_weights`); jeder
Stadtbezirk mit Wahlberechtigten zählt. 40 der 41 Wahlbezirke liegen in genau einem Stadtbezirk, der
Wahlbezirk 40 zu 64,7 % in 9 und zu 35,3 % in 10. Verworfen: nur der Mehrheitsstadtbezirk — dann gälten
dessen 293 Treffer aus der Bezirksvertretung 10 als fremd, sein Anteil fiele von 0,77 auf 0,26 und die
Lokalität der Bezirksvertretung 10 von rund 75 % auf 44 %. Verworfen: Bruchzahlen je Dokument (schwer
erklärbar, betrifft einen Bezirk). Die Gewichte sind veröffentlicht, die Seite trägt eine Fußnote.

**Namen.** Kürzel zu Name steht mit Quelle je Zeile in den Settings, Stand als Datum auf der Seite; elf
Kürzel haben keinen gesicherten Namen und erscheinen nur als Kürzel. Verworfen für jetzt: die Namen aus
der OParl-Organisationsliste laden (Netz; Option 4 holt sie ohnehin, dann ersetzt der Abruf die Tabelle,
das Kürzel bleibt der Schlüssel). Namen ändern sich innerhalb einer Wahlperiode, Kürzel nicht.

**Form.** `parse_reference` ist eine reine Funktion über einem vorkompilierten `BodyRules`-Objekt; die
einzige Brücke zu den Settings ist `BodyRules.from_settings`, kein Kürzel steht im Code. Verworfen: das
Muster ein zweites Mal als Polars-`str.extract` (zwei Wahrheiten). Die Batch-Funktion ruft den Parser
19 108 mal, darum trägt er `deal.safe` statt `deal.pure`: `deal.has()` patcht je Aufruf prozessweit und
kostete gemessen 30 % (CLAUDE.md, „Nie"); Reinheit prüfen `deal.cases` und crosshair.

**Zuschnitt.** Zwei neue Schritte (`bodies` am Korpus, `body_hits` an der Auswertung) statt Spalten an
`wahlbezirke_auswertung.parquet`: der Golden Master der Arbeit bleibt byteidentisch, und der Parser ist
für sich profilierbar. Die Zuordnung je Dokument bleibt unveröffentlicht (126 KB Parquet, aber 2,3 MB
CSV für eine Spalte, die aus der Drucksachennummer in `dokumente.json` und der dokumentierten Regel
folgt).

## Punkt: scikit-learn für das Themenmodell (Option 06, 2026-10-12)

`noxfile.py` verbot `scikit-learn` im Lockfile, weil es in der Arbeit nur mittelbar über pandas hing. Für die
Themen je Dokument (Option 6, [plans/06-gewichtung.md](plans/06-gewichtung.md)) ist es seit dem 2026-10-12
Laufzeitabhängigkeit (`scikit-learn>=1.9`): Konrad hat es am 2026-10-11 ausdrücklich freigegeben
([plans/fragen.md](plans/fragen.md), Nr. 3) mit dem Satz, dass TF-IDF von Hand und gensim nicht nötig sind.
Gemessen am 2026-10-11 auf den 19 033 Texten der Referenz: TF-IDF 2,2 s, NMF mit 20 Themen 3,8 s, zweiter Lauf
byteidentisch; LDA (online, 10 Iterationen) brauchte 47 s und lieferte Themen aus Funktionswörtern, also bleibt
es bei NMF. 1.9.1 zieht nur joblib, threadpoolctl, scipy und numpy, kein pandas; `nox -s deps` verbietet pandas,
geopandas und osmnx weiter. Der Import kostet rund 0,4 s und soll `georep status` nicht verteuern: er steht
allein in `analysis/topics.py`, die Pipeline lädt das Modul erst im Schritt `topics`, und
`tests/unit/test_dependency_boundary.py` hält die Grenze per Quelltextsuche. Verworfen: TF-IDF und NMF selbst
schreiben (mehr Code als Nutzen, Konrad hat es abgelehnt); gensim (dieselbe Abhängigkeitsfrage, schlechtere
Determinismus-Lage); kein Themenmodell und nur Spezifität je Begriff (dann fehlt der Tabelle die inhaltliche
Variante, die zeigt, ob der Zusammenhang an einem Thema hängt).

## Punkt: Gewichtete Trefferquoten als lange Tabelle (Option 06, 2026-10-12)

Die Trefferquote der Arbeit ist binär: ein Dokument zählt für einen Wahlbezirk, sobald ein Begriff seines
Wörterbuchs darin vorkommt, und „grafenberger allee" (205 Dokumente) zählt wie ein Begriff mit einem
einzigen Treffer. Option 6 stellt ihr Varianten zur Seite, statt sie zu ersetzen. Die Formel: ein Paar
(Wahlbezirk, Dokument) bekommt das **Maximum** über die getroffenen Begriffe von `w_begriff · w_art ·
w_thema`, jeder Faktor in [0, 1]. Das Maximum, nicht die Summe: so zählt ein Dokument je Bezirk höchstens
einmal, wie die Vereinigung der `paper_ids` in der Arbeit, und bei Einheitsgewichten ist die Summe der
Gewichte **exakt** `anzahl_treffer` (auf der Referenz 29 573; ein deal-`ensure` und ein hypothesis-Test
halten das fest). Verworfen: die Summe über die Begriffe (zählt Dokumente mit vielen Begriffen mehrfach und
bricht die Schranke 1), Noisy-Or (dieselbe Schranke, schwerer zu erklären), Summe mit Kappung (nicht linear
in den Gewichten).

Die Varianten sind **Zeilen einer langen Tabelle** (`wahlbezirke_gewichtet.parquet`: Wahlbezirk, Variante,
gewichtete Treffer, gewichtete Quote), keine Spalten der Auswertung. Damit bleibt
`wahlbezirke_auswertung.parquet` byteidentisch (Golden Master der Arbeit), eine neue Variante kommt ohne
Schemaänderung hinzu, und weitere Kennzahlen (Periode, Gremium) passen in dieselbe Form. Die Gewichte
selbst: `1/n` über die Wahlbezirke, die einen Begriff führen (die Anteile eines Begriffs summieren zu 1),
die normierte inverse Dokumenthäufigkeit `(ln N − ln df) / ln N` (in [0, 1], ohne freien Parameter;
verworfen: `1/(1+ln df)` und BM25-Sättigung), Regex-Regeln auf `paper_type` aus den Settings (verworfen:
39 Dokumentarten einzeln zu gewichten, das wäre Düsseldorf im Code), und je Thema dessen Anteil am Dokument
(weich, nicht hart zugeordnet: nur so zerlegen die K Themenvarianten die Zählung genau). Die Ausreißer der
zweiten Regression sind für jede Variante dieselben (`analysis.exclude_districts`), sonst verglichen die
Zeilen verschiedene Stichproben; ein Satz unter der Tabelle sagt das.

Die Berichtsseite kürt keine „richtige" Gewichtung; sie zeigt, unter wie vielen der Zusammenhang das
5-%-Niveau erreicht (auf der Referenz: 2 von 26 über alle Wahlbezirke, 8 von 26 ohne die Wahlbezirke 1 und
10). Nicht übernommen: die Karte oder die Bezirkstabelle auf gewichtete Quoten umschalten (die lange Tabelle
macht das später möglich), und eine Deutung der Themen.
