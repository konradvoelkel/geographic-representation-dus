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

## 22. Suche inline, kanonische Begriffe, eigene Combobox (Option 08, 2026-10-12)

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

## 23. Gremien aus der Drucksachennummer (Option 05, 2026-10-12)

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

## 24. scikit-learn für das Themenmodell (Option 06, 2026-10-12)

`noxfile.py` verbot `scikit-learn` im Lockfile, weil es in der Arbeit nur mittelbar über pandas hing. Für die
Themen je Dokument (Option 6, [plans/06-gewichtung.md](plans/06-gewichtung.md)) ist es seit dem 2026-10-12
Laufzeitabhängigkeit (`scikit-learn>=1.9`): Konrad hat es am 2026-10-11 ausdrücklich freigegeben
([plans/fragen.md](plans/fragen.md), Nr. 3) mit dem Satz, dass TF-IDF von Hand und gensim nicht nötig sind.
Gemessen am 2026-10-11 auf den 19 033 Texten der Referenz: TF-IDF 2,2 s, NMF mit 20 Themen 3,8 s, zweiter Lauf
byteidentisch; LDA (online, 10 Iterationen) brauchte 47 s und lieferte Themen aus Funktionswörtern, also bleibt
es bei NMF. 1.9.1 zieht nur joblib, threadpoolctl, scipy und numpy, kein pandas; `nox -s deps` verbietet pandas,
geopandas und osmnx weiter. Der Import kostet rund 0,4 s und soll `georep status` nicht verteuern: er steht
allein in `analysis/topics.py`, die Pipeline lädt das Modul erst im Schritt `topics`, und
`tests/unit/test_dependency_boundary.py` hält die Grenze per Quelltextsuche.
**Nachtrag 2026-10-13 (Punkt 45c):** mit dem Klassifikator des passenden Ausschusses gibt es eine
zweite solche Stelle, `analysis/committees.py`; der Test nennt beide und keine dritte. Die
Schema-Versionen der zwei Ausgaben liegen darum in `georep/schema.py` und nicht in den
Modellmodulen -- `build_steps` braucht sie bei jedem `georep status`, und eine Zahl soll den
Import nicht auslösen. Verworfen: TF-IDF und NMF selbst
schreiben (mehr Code als Nutzen, Konrad hat es abgelehnt); gensim (dieselbe Abhängigkeitsfrage, schlechtere
Determinismus-Lage); kein Themenmodell und nur Spezifität je Begriff (dann fehlt der Tabelle die inhaltliche
Variante, die zeigt, ob der Zusammenhang an einem Thema hängt).

## 25. Gewichtete Trefferquoten als lange Tabelle (Option 06, 2026-10-12)

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


## 26. Kontrollvariablen aus Fremddaten (Option 03, 2026-10-12)

Die Regression der Arbeit (Tabelle 5) stellt die Wahlbeteiligung allein der Trefferquote gegenüber. Tabelle 6
nimmt Sozialdaten der Stadt dazu, damit sichtbar wird, ob die Trefferquote mehr ist als ein Spiegel der
Sozialstruktur. Die Entscheidungen dazu, mit dem, was verworfen wurde:

**OLS ohne statsmodels.** `analysis/ols.py` rechnet die kleinsten Quadrate mit `numpy.linalg.lstsq` und
`scipy.stats` (rund 230 Zeilen für Koeffizienten, Standardfehler, t, p, R², adjustiertes R², F-Test, VIF,
standardisierte Koeffizienten und partielle Residuen). statsmodels zieht pandas, und `nox -s deps` verbietet
es (Konrads Vorgabe, Punkt 4). Einmalig verglichen am 2026-10-12 in einer Wegwerf-Umgebung ohne Lockfile
(`uv run --isolated --no-project --with statsmodels --with pandas`): statsmodels 0.15.0 stimmt in allen
genannten Größen der Modelle A, B und C bis auf eine relative Abweichung von 4,0e-14 überein; die Zahlen
stehen seither als Konstanten in `tests/golden/test_regression_numbers.py`. Verworfen: scikit-learn (liefert
weder Standardfehler noch p-Werte); die Formeln je Aufrufstelle wiederholen.

**Raumeinheiten statt Stadtteilen, Flächen statt Attributen.** Die Fremddaten liegen je Sozialraum vor (171,
feiner als die 50 Stadtteile; 31 von 41 Wahlbezirken umfassen mehrere Stadtteile). `crosswalk.area_shares`
schneidet die 306 Stimmbezirksflächen mit ihnen und `district_weights` wiegt mit den Wahlberechtigten je
Stimmbezirk: Wahlberechtigte sind die Bezugsgröße von Trefferquote und Wahlbeteiligung, reine Flächenanteile
zählten Parks wie Wohngebiete. Normiert wird auf die Schnittsumme, nicht auf die Quellfläche, weil die Grenzen
zweier Portaldateien um Meter abweichen; wie weit, sagt die Spalte `coverage` (auf der Referenz mindestens
0,99988, Grenze `min_coverage = 0,9`). Beide Schlüssel der Anteile sind Text und nicht `target_id` als Int64
wie in `plans/00-synergien.md` § 2 Punkt 4 vorgesehen: die Schlüssel der Einheiten tragen eine führende Null.
Geprüft gegen die Stadt (`tests/golden/test_crosswalk_methods.py`): verschmilzt man die Einheiten zu
Stadtteilen und vergleicht mit der Zuordnung ganzer Stimmbezirke aus dem GeoJSON, weichen 227 Paare im Mittel
um 0,001 ab, höchstens um 0,067 (Wahlbezirk 22, Stadtteile 053 und 054), und der dominante Stadtteil stimmt in
40 von 41 Wahlbezirken; das ist der Unterschied der Methoden (ganzer Stimmbezirk gegen Fläche), kein Fehler.
Verworfen: die Stadtteilgrenzen 2025 als zweite Datei für diesen Vergleich (verschmolzene Einheiten prüfen nur
die Methode und sparen einen Datensatz); die Zuordnung über den Präfix der Einheitennummer (ersetzt die
Flächenanteile nicht).

**Fremddaten im Repo.** `context/` trägt die drei Portaldateien (2,3 MB) mit README (Quelle, Lizenz,
Datenstand, Abrufdatum, SHA-256); `Layout.context_root` ist die zweite nur lesbare Wurzel, `bootstrap` kopiert
nach `external/`, der Netzschritt `context_data` holt frisch. So baut der Pages-Workflow ohne Netz, und das
Portal darf seine Dateien umbenennen. Verworfen: Ablage unter `reference/` (vermischt Arbeit und Ausbau);
Abruf im Workflow (Netz in CI); nur Prüfsummen und URLs (Frage 3.3, Konrads Entscheidung steht aus).

**Modelle sparsam bei n = 41.** Drei Modelle (A: nur die Trefferquote, B: plus Handlungsbedarf-Score, Anteil
65 und älter, Fluktuationsrate, C: plus CDU- und AfD-Anteil) und je eine Variable einzeln (Tabelle 6b), beides
für beide Stichproben der Arbeit. Alles steht in `defaults.toml`; der Code kennt weder die Variablen noch die
Stadt. Ordinale Stufen werden gleichabständig zu einem Score 1 bis 5 (Frage 3.2); als stetige Gegenprobe steht
die Mindestsicherungsquote in Tabelle 6b. Fehlende Werte (die Quelle anonymisiert Zahlen unter 3, eine Einheit
war 2021 unbebaut) fallen aus dem Mittel, die übrigen Gewichte werden renormiert, und je Variable steht das
Fehlgewicht in der Tabelle; über `max_missing_weight` bricht der Schritt ab (auf der Referenz höchstens 0,057).
Verworfen: stilles Auffüllen mit 0; schrittweise Modellwahl (bei n = 41 ein Zufallsgenerator); alle sechs
Parteianteile in einem Modell (VIF bis 76). Das Parteimodell C erreicht VIF 6,7 (Handlungsbedarf), mehr als
die im Plan erhofften 5, aber unter der Grenze 10, ab der ein Modell nicht mehr zu deuten ist; ein Test hält
sie, und die Spalte VIF steht auf der Seite.

**Ergebnis, das die Seite zeigt.** Modell A reproduziert Tabelle 5 auf alle Stellen (62,13, p 0,314). Mit den
Kontrollvariablen erklärt Modell B R² = 0,887 statt 0,026, und der Koeffizient der Trefferquote sinkt auf
41,33 mit p 0,133: was Tabelle 5 als schwachen Zusammenhang zeigt, erklärt vor allem der soziale
Handlungsbedarf (standardisiert −0,96). Das steht so auf der Seite, erzeugt aus den Zahlen, mit dem Hinweis
auf n = 41, den Datenstand 31.12.2021 und die Endogenität der Stimmenanteile.

## 27. Urheber aus Metadaten und Textkopf, OParl-Felder vorbereitet (Option 04, 2026-10-12)

OParl 1.1 hat für den Urheber einer Vorlage drei Felder (`originatorPerson`, `originatorOrganization`,
`underDirectionOf`). Der Server der ITK Rheinland füllt sie für Düsseldorf nicht: keines der sechs Paper der
echten Seite vom 2026-10-09 trägt eines, auch der „Antrag FDP" nicht, und die 19 108 Rohobjekte der Arbeit
haben sie nie getragen. Der Urheber steht stattdessen im `paperType` („Anfrage SPD"), im Titel („Antrag der
SPD-Fraktion") und im Textkopf („(anfrage cdu-fraktion vom 28. juli 2023)"). Gewählt: der Urheber wird aus
diesen drei Feldern abgeleitet, in dieser Reihenfolge, und `originatorOrganization` steht als erste Quelle
davor, damit sie ohne Codeänderung greift, sobald der Server sie füllt. Die Muster, die Verwaltungs- und
Eingabe-`paperType`s und die Parteien stehen vollständig in `defaults.toml` unter `[originators]`, nichts
davon im Code; eine zweite Kommune bringt andere Werte mit (Option 10). Jede Zuordnung veröffentlicht ihre
Quelle und die getroffene Zeichenkette, also ist sie nachprüfbar.

Belegt durch eine geschichtete Stichprobe von 50 Dokumenten, von Hand gegen Titel und Textkopf geprüft: der
erste Durchgang fand sieben Fehler (14 %), alle in der Klasse „unbekannt", und zeigte drei Lücken — Punkte in
Abkürzungen zwischen Antragswort und „Fraktion", die umgekehrte Leserichtung „(interfraktioneller antrag)",
und eine Partei in einer Antragsklammer ohne das Wort „Fraktion". Nach dem Nachziehen der Muster bleibt ein
Fehler in 50 (2 %), und die Klasse „unbekannt" fällt von 616 auf 327 Dokumente (1,7 %).

Verworfen: auf den Vollabruf der Metadaten warten (2 bis 3 h und nach dem Befund ohne Ertrag für den Urheber;
er bleibt als Lauf dokumentiert, weil er `modified` für Option 7 und `consultation` für Option 5 bringt); ein
gelernter Klassifikator (es gibt nichts zu lernen, die Zuordnung steht wörtlich im Text); den ganzen Text
durchsuchen statt nur den Kopf (Verwaltungsvorlagen zitieren Fraktionen); Personen über `memberships` und
`persons` den Fraktionen zuordnen (Hunderte Anfragen für 865 Dokumente, zurückgestellt); die Personenmarker
auch auf den Textkopf anwenden (die Anreden der Vorlagen, „sehr geehrter Herr Oberbürgermeister", machten
halbe Anträge zu Personen — die Folge ist ein dokumentierter Fehler in der Stichprobe). Kosten: eine
Ableitung, keine Angabe der Quelle; der Methodentext der Seite sagt das, und 1,7 % bleiben ohne Urheber.

Kooperationspapiere (1 168, davon 844 CDU und Grüne) zählen für jede beteiligte Partei voll, mit
`treffer_allein` als Gegenprobe; Bruchteile 1/k wären schwerer zu prüfen und ergäben halbe Dokumente. Der
Abgleich mit den Hochburgen bleibt bei Pearson *r* und *p* je Partei mit dem Bonferroni-Hinweis (bei sechs
Tests und n = 41 ist ein „signifikanter" Wert zu erwarten; nur die FDP bleibt unter 0,05/6); ein Modell
gehört zu Option 3. Bezirke ohne Wahlvorschlag einer Partei bleiben im Abgleich außen vor, sonst läse sich
„nicht angetreten" wie „keine Zustimmung" (Wahlbezirk 11, Die Linke).
## 28. Eine Wahlperiode ist ein Profil, keine zweite Installation (Option 02, 2026-10-12)

Die Wahlperiode 2014 bis 2020 läuft durch dieselbe Kette wie die Hauptperiode, nur mit einer zweiten
Paketprofil (`profiles/duesseldorf-2014.toml`): `profile = "2014-2020"` legt Daten unter `data_root/2014-2020/` und
PDFs und Texte unter `cache_root/2014-2020/`, der HTTP-Cache bleibt geteilt. Verworfen: ein zweites
`data_root` in `settings.local.toml` (nicht committbar, die CI kennt es nicht) und ein geteilter Textstore
(die Perioden hätten sich gegenseitig den Stamp von `texts` entwertet).

**Dasselbe Wörterbuch für beide Perioden** (`period.dictionary = "base"`): Straßen und Orte je Wahlbezirk
2025, Stand November 2025. So unterscheiden sich die Perioden nur in den Dokumenten, und keine Trefferquote
muss zwischen zwei Zuschnitten umgerechnet werden — Treffer sind Dokumentmengen, keine Summen, und ließen
sich gar nicht anteilig verteilen. Der Preis steht auf der Seite: Dokumente von 2016 werden mit den
Straßennamen von heute gesucht. Verworfen: ein Wörterbuch je Stimmbezirk 2020 (zwei weitere Netzläufe über
316 Polygone, und 87 der 306 Stimmbezirke 2025 liegen nicht zu 99 % in einem Wahlbezirk 2020).

## 29. Wahlzahlen über Flächenanteile umrechnen, Anteile erst danach (Option 02, 2026-10-12)

Kein Wahlbezirk von 2020 blieb unter 1 % Flächenänderung gegenüber 2025; ein Vergleich über die Nummer wäre
sinnlos. Umgerechnet wird darum von den 316 Stimmbezirken 2020 auf die 41 Wahlbezirke 2025, mit dem
Flächenanteil der Schnittfläche als Gewicht, normiert auf die Schnittsumme (Stadtgrenze und Rhein lassen bis
zu 2,2 % Rand unbedeckt; `crosswalk.min_coverage` fängt echte Lücken wie ein falsches CRS). Übertragen
werden nur additive Zählgrößen — Wahlberechtigte, Wähler, Stimmen —, je Zielbezirk nach dem Verfahren des
größten Restes ganzzahlig gerundet, sodass die Stadtsumme exakt erhalten bleibt; Wahlbeteiligung und
Parteianteile entstehen **danach** aus den übertragenen Zahlen. Verworfen: Ganzzuordnung jedes Stimmbezirks
zum Mehrheitsbezirk (83 von 316 sind geteilt, bis 2,6 Prozentpunkte Beteiligung und 4 262 Wahlberechtigte
Abweichung je Bezirk) und Bevölkerungsgewichte aus dem Zensusraster (genauer, aber eine weitere Quelle;
Kandidat für später). Die Annahme bleibt, dass sich die Wahlberechtigten innerhalb eines Stimmbezirks
gleichmäßig über die Fläche verteilen; die Seite sagt das.

**Briefwahl**: 110 265 der 247 356 Wähler von 2020 (44,6 %) wählten per Brief, und die 138 Briefwahlbezirke
haben weder Geometrie noch Wahlbezirk. Ihre Zahl je Wahlbezirk ist die Differenz zwischen der
Wahlbezirkszeile und der Summe ihrer Urnenstimmbezirke; verteilt wird proportional zu den Wahlberechtigten
mit Sperrvermerk W, also mit Wahlschein (gegen proportional zu allen Wahlberechtigten: bis 5,1
Prozentpunkte je Bezirk, Median 0,6). Verteilt werden auch die Parteistimmen, sonst wären die Anteile
urnenlastig. Drei Proben sichern das ab: die Wahlberechtigten je Wahlbezirk müssen exakt stimmen (das prüft
zugleich die geometrische Zuordnung), keine Lücke darf negativ sein, und die Summe der Briefwahlzeilen muss
die Lücke genau füllen. Verworfen: die Briefwahl weglassen (die Beteiligung wäre fast halbiert).

## 30. Der Vergleich ist ein eigener Schritt, kein stiller Seitenteil (Option 02, 2026-10-12)

`compare` läuft nur mit `compare.period` und schreibt `wahlbezirke_vergleich.parquet`; der Schritt `report`
nimmt die Datei als Eingabe, und der Abschnitt „Zwei Wahlperioden" existiert nur mit ihr. Fehlende Eingaben
sind nach Regel 3 der Architektur ein Fehler, kein stilles Überspringen — also muss der Vergleich
ausdrücklich eingeschaltet werden (`profiles/duesseldorf-vergleich.toml`), und die Kette von `main` bleibt unverändert.
Verworfen: der Vergleich als „optionale Eingabe" von `report` (das Schrittregister kennt keine). **Bei `pending` darf auch `title` leer bleiben**, und dann schreibt die Vorlage
„[Titel nachzutragen]": der Titel der Arbeit steht nirgends — ihr Repositorium hat keine Beschreibung, sein
README nennt nur den Zweck des Programms (am 2026-10-13 gelesen) —, und ein selbst formulierter Titel in
einem `<cite>` wäre eine Behauptung, die niemand geprüft hat, auf einer veröffentlichten Seite (Review
2026-10-13). Verifizierbar ist allein der Name des Repositoriums, und der steht als solcher im Begleitsatz.
Marker und Zitation trennt ein Gedankenstrich, in der Vorlage und im README gleich; es gibt genau zwei
Marker, „[Titel nachzutragen]" für den fehlenden Titel und „[Angaben nachzutragen]" sonst. Verglichen
wird die Schnittmenge der Wahlbezirke beider Perioden: ein Bezirk, den nur eine Periode kennt, fällt weg,
statt mit einer erfundenen Null zu erscheinen; die Seite nennt die Zahl.

## 31. Kanonische Spaltennamen statt Quellnamen (Option 02, 2026-10-12)

Die Wahlergebnis-CSV von 2020 nennt die Wahlberechtigten `A`, die Wähler `B` und die Parteien `D1` bis
`D16`; die von 2025 nennt sie wie die Arbeit. `read_results_csv` benennt beim Lesen um, sodass
`wahlbezirke_waehler.parquet` in jeder Periode dasselbe Schema trägt und die Auswertung die Namen als
Konstanten liest statt aus den Settings. Für die Hauptperiode ist die Umbenennung die Identität, der Golden
Master bleibt unberührt. Verworfen: die Quellnamen durchreichen (dann hieße eine veröffentlichte Spalte
`A`), und eine Namenstabelle in den Settings (eine Abbildung, die nur eine Richtung kennt, gehört in den
Code).

## 32. `[columns]` beschreibt den Zielzuschnitt, `[crosswalk]` den alten (Option 02, 2026-10-12)

Ein Periodenprofil liest zwei Zuschnitte: seinen eigenen (die Stimmbezirke von 2020, deren GeoJSON nur
`Stimmbezchar` trägt) und den der Auswertung (die Stimmbezirke der Hauptperiode mit Wahlbezirksnummer und
-namen). Beide haben andere Eigenschaftsnamen. `[columns]` beschreibt weiter den Zielzuschnitt — so lesen
Karte, Bezirkstabelle und Namen der Berichtsseite unverändert —, und die drei Eigenschaften des alten
Zuschnitts stehen in `[crosswalk]`. `Layout.target_view` ist die eine Stelle, die den Unterschied kennt.
Verworfen: `read_precincts` mit leeren Wahlbezirksspalten (dann hätte die Seite des Profils keine
Bezirksnamen mehr) und ein zweiter kompletter `[columns]`-Block (vier Schlüssel doppelt).

## 33. Der Abruf der alten Periode ist je Seite wiederaufnehmbar (Option 02, 2026-10-12)

Rund 235 Seiten à 85 s sind drei Stunden; ein Abbruch darf nicht drei Stunden kosten. `fetch_papers` meldet
nach jeder Seite ihre Paper und die URL der nächsten, der Schritt speichert beides (`raw/papers.jsonl` und
`raw/papers.progress.json`), und der nächste Lauf beginnt dort. Die Fortschrittsdatei existiert nur,
solange ein Abruf unvollständig ist. `sources.oparl.first_page` überspringt die Seiten der jüngeren
Perioden; die Liste ist neueste zuerst, also ist eine zu kleine Startseite nur langsam, eine zu große
verlöre Dokumente. Seite 90 trug am 2026-10-12 den Bereich Januar bis März 2022 und liegt damit rund 28
Seiten (40 Minuten) vor der Grenze — bewusst mit Vorlauf, weil jedes neue Paper die alten Seiten nach
hinten schiebt. `incremental = false`, weil `modified` bei alten Papern das Migrationsdatum 2024-12-30 ist.
## 34. pyshp statt GDAL für Shapefiles (Option 01, 2026-10-12)

Mönchengladbach veröffentlicht seine Stimmbezirksflächen nur als Shapefile im Zip
(`Wahlen_EPSG25832_SHAPE.zip`, DL-DE Zero 2.0). `pyshp` 3.1.6 liest `.shp`, `.shx` und `.dbf` direkt aus dem
Archiv, ist reines Python, hat keine eigenen Abhängigkeiten und steht unter MIT; das CRS kommt aus dem `.prj`
über pyproj, das ohnehin im Projekt ist. Verworfen: `fiona` oder `pyogrio` (GDAL-Binärwheels, rund 20 MB, mehr
Angriffsfläche und ein zweiter Geometrie-Stack neben shapely); Konvertierung von Hand mit `ogr2ogr` (nicht aus
`georep fetch` reproduzierbar, und CI hat kein GDAL); geopandas (durch `nox -s deps` verboten, Konrads Vorgabe).
Kosten: ein weiteres Paket im Lockfile und ein mypy-Override, weil pyshp Annotationen, aber keine
`py.typed`-Marke mitbringt.

## 35. ein kanonischer Stand der Stimmbezirke (Option 01, 2026-10-12)

Zwischen der Quelldatei und allem, was Flächen liest, steht jetzt der Schritt `shapes`: aus GeoJSON oder
Shapefile-Zip entsteht `interim/stimmbezirke.geojson` mit genau drei Eigenschaften (`stimmbezirk`,
`wahlbezirk`, `wahlbezirk_name`) und dem CRS der Quelle. Die Regeln (welche Eigenschaft die Nummer trägt, ob
der Wahlbezirk eine eigene Spalte ist oder als Zeichenausschnitt in der Nummer steckt, woher die Namen kommen)
stehen in `[precincts]` im Profil; `geo.read_canonical_precincts` liest nur diese Datei, neben dem Leser der
Quellgeometrie `geo.read_precincts`, den der Crosswalk (Option 02) und die Raumeinheiten (Option 03)
brauchen. Die Koordinaten bleiben die der Quelle: Düsseldorf rechnet weiter in einem Schritt
von EPSG:4647 ins Arbeits-CRS, der Golden Master der 1 996 Orte bleibt grün. Verworfen: `read_precincts` mit
immer mehr Parametern (jeder Leser wüsste von jeder Quelle); Umprojektion auf EPSG:4326 im kanonischen GeoJSON
(zwei Transformationen statt einer, Rauschen an Bezirksgrenzen). Kosten: ein Schritt mehr in `georep steps`
(Snapshot bewusst erneuert) und eine Zwischendatei; `georep fetch` führt ihn mit, weil die Netzschritte
`streets_osm` und `pois_wiki` ihn brauchen. Der Name `shapes` statt `precincts`, weil Option 02 einen Schritt
`precincts` hat (die Umrechnung eines älteren Zuschnitts) und zwei Schritte nicht gleich heißen können; wo
eine Periode den Zuschnitt einer anderen rechnet, entfällt `shapes` (`precincts.enabled = false`).

## 36. Stadt, Quellen und Allowlist der Seite aus dem Profil (Option 01, 2026-10-12)

Kopf, Fuß und „Methode und Grenzen" der Berichtsseite nennen jetzt die Stadt aus `[city]`
(Name, Genitiv, Adjektiv, Rat, Wahl), die Quellen mit Lizenz und Prüfdatum aus `[[report.sources]]`
und den Marker aus `search.text_split_marker`; stadtspezifische Sätze stehen als `report.notes` im
Profil. Die Allowlist der Links entsteht aus Konstanten (Repository, Arbeit, Architektur, OSM,
Wikidata, Wikipedia, CC0, ODbL) plus den URLs des Profils: Links aus dem Profil sind per
Konstruktion erlaubt, Links aus Daten weiterhin nicht, und die Nachbedingung von `render_report`
prüft gegen diese Menge statt gegen eine Konstante. Verworfen: eine Allowlist je Stadt im Code
(dann wäre jede neue Stadt eine Codeänderung); Lizenztexte in der Vorlage mit `{% if city %}`
(dieselbe Verzweigung in jeder Zeile). Kosten: `render_report` bekommt ein drittes Argument
(`Links`), und die Spaltendoku der Parteien entsteht zur Laufzeit aus `columns.results`
(`PublishedTable.extra_columns`), weil sie je Stadt verschieden ist.

## 37. summary.json als Schnittstelle der Stadtseite (Option 01, 2026-10-12)

Neben `schema.json` schreibt der Schritt `report` jetzt `site/data/summary.json`: Stadt,
Datenstand, Kernzahlen und beide Regressionen als JSON, beschrieben in `schema.json` unter
`summary`. Der Städtevergleich (`georep publish`) und Dritte lesen damit nur den veröffentlichten
Ordner einer Stadt, nie ihre Zwischenergebnisse; der Vergleich hängt nicht an zwei Layouts und
nicht an Parquet-Schemata. Verworfen: der Vergleich liest `processed/*.parquet` beider Läufe (dann
wäre jede Änderung an einer Zwischentabelle ein Bruch des Vergleichs) und `summary.json` als
`PublishedTable` (es ist keine Tabelle, es hat keine Spalten).

## 38. Städtevergleich als eigene Seite aus den veröffentlichten Ordnern (Option 01, 2026-10-12)

`georep publish` trägt die Stadtseiten nach `data/site/` zusammen und baut daraus `vergleich.html`. Gelesen
wird je Stadt nur, was auf ihrer Seite zum Download steht (`summary.json`, `wahlbezirke.geojson`,
`wahlbezirke_auswertung.parquet`): die Stadtseite ist die Schnittstelle, nicht ihr Zwischenstand, und der
Vergleich hängt an keinem Parquet-Schema der Pipeline. Die erste Stadt aus `publish.cities` bleibt an der
Wurzel (Düsseldorfs veröffentlichte Adresse und das Repository heißen `…-dus`), jede weitere liegt unter
ihrem Slug. Die beiden kleinen Karten teilen sich die Quantilklassen; sonst verglichen sie Farben, die
nichts miteinander zu tun haben. Verworfen: ein Vergleichsabschnitt in jeder Stadtseite (doppelt, kostet
Budget und macht zwei Läufe voneinander abhängig); eine Landing-Page an der Wurzel (bricht die
veröffentlichte Adresse); der Vergleich aus `processed/*.parquet` beider Läufe (jede Änderung an einer
Zwischentabelle wäre ein Bruch). Kosten: `publish` muss wissen, welche Stadt flach liegt, und kopiert sie
dann nicht; fehlt eine Stadt, löscht es einen alten Vergleich, der sonst eine Lüge wäre.

Nachtrag (Punkt 52, 2026-10-13): keine Stadt liegt mehr flach, auch die erste wird also kopiert. Die Wurzel
bleibt ihre Adresse, nur gehört ihr der Ordner nicht mehr selbst.

## 39. was eine zweite Stadt nicht hat, fehlt als Block (Option 01, 2026-10-12)

Beim Rebase auf `main` mit sechs gemergten Optionen zeigte Mönchengladbach vier Stellen, an denen die Kette
Düsseldorfer Daten voraussetzte. Die Regel dagegen ist überall dieselbe: der Block fehlt im Profil, und der
Schritt, der ihn braucht, entfällt. `[context]` (Option 03) darf ganz fehlen — `context.root = None` schaltete
die drei Schritte schon ab, nur verlangte das Modell die Beschreibung des Datensatzes; sie ist jetzt erst
Pflicht, sobald `root` gesetzt ist. `[originators]` ohne Parteien heißt: kein Schritt `parties`, und der
Bericht lässt den Abschnitt weg (das tat er schon, er prüft die Dateien). `bodies.reference_pattern` darf leer
sein — Mönchengladbachs Drucksachennummern tragen kein Kürzel (`0682/XI`), und dann ist jedes Dokument
„unbekannt", sichtbar mit Anteil auf der Seite, wie Option 05 es für unbekannte Nummern ohnehin vorsieht. Den
Stadtbezirk je Stimmbezirk (Option 05) liest das Profil aus einer Spalte oder, wie bei votemanager, aus der
Stimmbezirksnummer (`city_district_from_precinct`, dieselbe Form wie `district_from_precinct`).

Verworfen: je Option ein eigenes `enabled`-Feld (vier Schalter für denselben Sachverhalt „es gibt diese Daten
nicht"); Pflichtblöcke mit erfundenen Werten im Profil der zweiten Stadt (ein Muster, das nie trifft, oder ein
Datum, das nichts bedeutet, wären eine stille Lüge in der Namensnennung); Option 05 für eine Stadt ohne
Gremiumskürzel abzuschalten (der Abschnitt zeigt dann ehrlich 100 % „unbekannt", und der volle Lauf kann die
Frage beantworten, siehe `docs/plans/01-staedte.md`, § 8, Fragen 1.12 und 1.13).

## 40. Gebietsnummern sind ASCII-Ziffern (Option 01, 2026-10-12)

`str.isdigit()` ist für `²` wahr, `int('²')` wirft; arabisch-indische Ziffern läse `int` zwar, aber eine
Stimmbezirks- oder Wahlbezirksnummer besteht aus 0 bis 9. `prep.precincts.is_number` prüft darum
`isascii() and isdigit()`, und alle drei Stellen, die eine Nummer aus einer Quelle lesen, benutzen sie.
Gefunden hat das crosshair (`nox -s verify`) als Gegenbeispiel zum Vertrag von `district_from_id`; der Test
nennt beide Fälle. Verworfen: `isdecimal()` (es ließe arabisch-indische Ziffern durch) und ein `try: int(...)`
(dann wäre der Fehler eine Ausnahme von `int`, keine Aussage über die Quelle).

## 41. Die laufende Wahlperiode als zweites Profil mit eigenem Lauf (Option 07, 2026-10-12)

Die Periode seit der Kommunalwahl vom 14.09.2025 wird fortgeschrieben, ohne die Kette der Arbeit anzufassen:
ein Paketprofil `profiles/duesseldorf-2025.toml` (`base = "duesseldorf"`, `profile = "2025"`, `period.start = 2025-09-15`, `end` leer,
`election = 2025-09-14`) legt Daten unter `data_root/2025/` und PDFs wie Texte unter `cache_root/2025/`. Der
Abruf holt je Lauf nur Geändertes (`modified_since`), der Store entfernt gelöschte Paper, der neue Schritt
`timeline` zählt Dokumente je Monat, und die Seite des Profils entsteht aus derselben Vorlage mit zwei
Zweigen weniger (keine Regression, kein Kartenumschalter) und zwei Abschnitten mehr („Je Monat", und auf der
Hauptseite „Laufende Wahlperiode"). Der wiederkehrende Lauf ist ein idempotentes Skript hinter einem
systemd-Timer (`deploy/`), nicht GitHub Actions: Actions hat keinen dauerhaften Speicher für 600 MB PDFs und
ein Zeitlimit von sechs Stunden. Das Wörterbuch aus Straßen und Orten bleibt eingefroren (Stand der Arbeit,
November 2025), damit Änderungen der Treffer nur von den Dokumenten kommen.

Verworfen: eine Datenwurzel mit Periodenfilter im Schritt `corpus` (jeder Schritt müsste filtern, der Golden
Master verschöbe sich); `end = 2030-09-13` als Platzhalter statt eines offenen Endes (der Wahltermin steht
nicht fest, und ein Datum in der Zukunft sagt „geschlossen"); den Korpus der Arbeit in den Store des Profils
zu kopieren (dann lüde `pdfs` 19 108 alte PDFs); ein Monitoring-Abschnitt in der Hauptseite statt einer
Unterseite (Pages kann keine zweite Datenwurzel lesen); cron statt systemd (kein `Persistent=`, kein Journal,
keine Credentials); feste Pfade im Skript. Kosten: ein Schritt und zwei Tabellen mehr in jedem Profil, rund
34 KB mehr auf der Hauptseite, und ein Rechner, der täglich zwei Minuten arbeitet. Offene Fragen (Hostname,
R2-Bucket, Freigabe des Erstabrufs) stehen in [plans/fragen.md](plans/fragen.md).

## 42. Quelltext unter GPL-3.0-or-later, Ergebnisse bleiben CC0 (Konrad, 2026-10-12)

Der Code wechselt nach dem Tag `v0.11.0` von CC0 1.0 auf GPL-3.0-or-later: Ableitungen des Programms sollen
unter derselben Lizenz offen bleiben. Das Original von Lukas Bartzsch steht unter CC0, das die
Weiterlizenzierung erlaubt; sein Name bleibt in `pyproject.toml` und im README als Ursprung. Die Ergebnisse
(Tabellen, `summary.json`, die Berichtsseite) bleiben CC0 1.0, damit sie ohne Bedingungen weiterverwendet
werden können; die Daten behalten die Lizenz ihrer Quelle. Der Fuß der Seite nennt beides getrennt.

Verworfen: MIT oder Apache-2.0 (kein Copyleft); AGPL (die Seite ist statisch, es gibt keinen Dienst, dessen
Nutzung die Quelle erzwingen müsste); die Ergebnisse ebenfalls unter GPL (Daten sind keine Software, und CC0
ist für sie die üblichere Lizenz).

## 43. Die Zahlen der Arbeit müssen nur noch ungefähr reproduziert werden (Konrad, 2026-10-12)

Bis `v0.11.0` galt: jede Änderung muss Tabelle 5 und die Treffer der Arbeit exakt reproduzieren (Golden
Master, Punkt 11). Der Tag `bartzsch-exakt` zeigt auf `v0.11.0` und friert diesen Stand ein. Ab jetzt darf
die Methodik von der Arbeit abweichen, wenn die Abweichung begründet, dokumentiert und in ihrer Wirkung auf
die Zahlen gemessen ist (`docs/todo.md`, Punkt 4); eine ungefähre Reproduktion genügt. Die exakte
Reproduktion bleibt als Test erhalten, solange sie mit abgeschalteten neuen Regeln gilt; die Golden-Master-
Dateien unter `tests/fixtures/mini/expected/` werden dann nicht mehr blind, sondern mit einem Eintrag hier
und im Commit erneuert.

Verworfen: die exakte Reproduktion ganz aufgeben (dann wüsste niemand mehr, wo die Arbeit endet und das
Programm beginnt); eine Toleranz ohne Messung (jede Abweichung muss benannt sein).

## 44. Einrichtungen mit Stadtnamen und stadtweite Begriffe (2026-10-12)

Zwei Regeln aus `docs/todo.md`, Punkt 4; die erste wirkt auf die Zahlen, die zweite auf die Seite.

### 44a. Einrichtungen mit Stadtnamen sind keine Orte

Erste bewusste Abweichung von der Arbeit nach Punkt 43. Das Wörterbuch enthält alles, was in einem
Stimmbezirk eine Koordinate hat, ohne Rücksicht auf den Typ (Punkt 7 und `architecture.md`, „Pipeline"); damit
steht „Stadtwerke Düsseldorf" als Ort im Wahlbezirk 10. Gemessen am 2026-10-12 auf der Referenz ist das der
Begriff mit der **zweithöchsten Dokumenthäufigkeit aller 5841 Begriffe** (190 Dokumente; Median 1,
99-%-Quantil 64, Maximum 205 für „grafenberger allee"), und **177 der 1189 Treffer des Wahlbezirks 10
(14,9 %) hängen allein daran**. Weiter: „hochschule düsseldorf" 80, „flughafen düsseldorf" 80, „messe
düsseldorf" 61, „stadtsparkasse düsseldorf" 45, „feuerwehr düsseldorf" 43. Diese Dokumente handeln von der
Einrichtung, nicht von ihrem Wahlbezirk.

**Die Regel** (`search.city_facilities`, standardmäßig an, weil sie für jede Stadt gilt;
`georep.prep.pois.is_city_facility`): nach dem Entfernen der Klammerzusätze ist ein Ortslabel eine
Einrichtung, wenn (1) kein Wort darin auf ein Gattungswort aus `search.place_words` endet **und** (2) das
Städteadjektiv darin steht oder der Stadtname am Ende steht. Verglichen werden die letzten Wörter, so viele
wie der Stadtname hat: „Stadtwerke Frankfurt am Main" ist eine Einrichtung, „Bahnhof Frankfurt am Main Süd"
ein Ort (ein mehrwortiger Stadtname kann nie „das letzte Wort" sein). Eine leere `place_words`-Liste bei
eingeschalteter Regel weist der Settings-Validator zurück: die Regel wäre sonst still „Stadtname zuletzt
genügt" und träfe jeden Bahnhof mit. Stadtname und Adjektiv kommen aus `[city]`
des Profils, die Gattungswörter stadtneutral aus `defaults.toml`, die Ausnahmen aus
`search.city_facilities_keep` des Profils (Düsseldorf: ein Eintrag, „Castello Düsseldorf"). Die Regel wirkt im
Schritt `pois` auf beide Ausgaben, also auch auf die Karte; **Straßen laufen nie durch sie**, weil sie am
Ortsteil der Kette hängt und nicht am Wörterbuch. Das Prädikat trägt `deal.safe`, nicht `deal.pure`: es
läuft über jedes Label, und der Patcher von `deal.pure` ist prozessweit, nicht reentrant und kostet das
Achtfache je Aufruf (1,80 µs gegen 0,23 µs, gemessen am 2026-10-12; CLAUDE.md, „Nie"). Dass die Funktion
rein ist, sichern `deal.cases` und das crosshair-Ziel, wie bei `parse_reference`.

**Warum zwei Bedingungen.** Drei Varianten wurden am 2026-10-12 an allen 1309 Rohlabels der Referenz
gemessen:

| Variante | Labels | davon mit Treffern | Fehlurteile |
|---|---|---|---|
| Stadtname irgendwo außerhalb der Klammer | 183 | 59 | erklärt 19 Orte mit Treffern zur Einrichtung: neun Bahnhöfe und Haltepunkte, „Düsseldorf Arcaden", den Stadtwald, zwei Gymnasien, zwei Stadtteilnamen |
| nur Stadtname zuletzt (Struktur) | 140 | 45 | lässt „Düsseldorfer Stadtwald" und zwei Gymnasien fallen |
| nur Gattungswörter | 131 | 46 | erklärt die Bahnhöfe mit Ortsteil („Bahnhof Düsseldorf-Rath") zur Einrichtung |
| **beide Bedingungen (gewählt)** | **114** | **41** | ein Fall, „Castello Düsseldorf" (6 Dokumente), über die Ausnahmeliste des Profils: dann 113 Labels und 40 mit Treffern |

Daraus folgen zwei Einzelheiten: Gattungswörter werden am **Wortende** verglichen, nicht als Vorkommen —
sonst bliebe „Stadtsparkasse Düsseldorf" (45 Dokumente) ein Ort, weil „park" in „Sparkasse" steckt —, und
„halle" und „schule" stehen **nicht** in der Liste, weil sonst die Tonhalle, die Kunsthalle und die
Hochschule einer Stadt Orte blieben, genau die Einrichtungen, um die es geht.

**Wirkung** (Referenz, 2026-10-12, aus einem Lauf `uv run georep run`; alle Zahlen in
`methodik-review-2026-10.md`, § 4): Orte 1309 → 1196, Wörterbuch 5841 → 5727 Begriffe, Treffer
29 573 → 29 010 (−1,9 %), 12 der 41 Wahlbezirke ändern sich. Tabelle 5 über alle 41 geht von r = 0,1612,
p = 0,31385 auf r = 0,1891, p = 0,23641 — der Befund der Arbeit bleibt, der Zusammenhang bleibt nicht
signifikant. Die Spalte „ohne Ausreißer" ändert sich in der dritten Stelle (r = 0,3385 → 0,3351,
p = 0,03507 → 0,03705). Der Wahlbezirk 10 fällt von robustem z = 4,04 auf 2,69 und ist damit kein Ausreißer
mehr; der Wahlbezirk 1 bleibt bei z = 9,71, denn seine hohe Quote kommt von der Größe seines Wörterbuchs
(812 Begriffe gegen 147 im Median), nicht von einer Benennung. Zwei Nebenwirkungen stehen im Review, § 4:
weil der längste Begriff gewinnt, treffen „tonhalle" (72 statt 67) und „nrw-forum" (11 statt 10) nach dem
Entfernen der längeren Labels mehr Dokumente, und genau darin liegt die Grenze der Regel — ein Kurzname
ohne Stadtnamen bleibt ein Ort.

**Golden Master.** `tests/golden/test_pipeline.py` rechnet mit `as_in_the_thesis(...)` (conftest), also mit
abgeschalteter Regel, und vergleicht unverändert gegen `reference/` und `tests/fixtures/mini/expected/`; die
Erwartungsdateien der Mini-Fixture bleiben damit die der Arbeit, obwohl die Regel dort 62 ihrer 493 Labels
trifft (`tests/fixtures/mini/README.md`). Der zweite slow-Test
`test_the_rules_change_the_reference_as_measured` friert die Zahlen mit den Regeln an ein. Geändert haben sich nur zwei eigene Zahlen dieses Repos: die eingefrorenen
Gremienzahlen der Mini-Fixture (Option 05) sinken von (96, 63, 14) auf (89, 59, 14) Treffern.

Verworfen: einzelne Labels je Stadt in `search.exclude` (Handarbeit, nicht übertragbar — genau was
`docs/todo.md`, Punkt 4 nicht will); eine Typfilterung über Wikidata `P31` (richtig, aber ein neuer Abruf von
Stunden und je Stadt neu zu prüfen, Review § 2.1); die Dokumenthäufigkeit als einziges Kriterium (trifft auch
„hofgarten" und „schulweg", also echte Orte — das ist Regel 2 und eine andere Frage); die Regel nur auf das
Wörterbuch wirken zu lassen und die Karte unverändert zu lassen (dann zeigte die Karte Orte, die nicht
zählen).

### 44b. Stadtweite Begriffe werden benannt, nicht stillschweigend gezählt

Regel 1 urteilt über Namen und findet darum nicht, was ohne Stadtnamen stadtweit vorkommt. Gemessen am
2026-10-12 auf der Referenz: „grafenberger allee" steht in 205 Dokumenten, „hofgarten" in 172, „königsallee"
in 146, „schulweg" in 144 — bei einem Median von 1 Dokument je Begriff. Ein Park, eine Prachtstraße oder ein
Gattungswort wird in der ganzen Stadt besprochen; der Wahlbezirk, dessen Wörterbuch den Begriff führt, bekommt
die Treffer trotzdem.

**Die Regel** (`georep.analysis.hits.citywide_terms`): Begriffe, deren Dokumenthäufigkeit über einer Schwelle
liegt, stehen auf der Seite im Abschnitt „Begriffe" als eigene Liste mit Dokumentzahl und Wahlbezirk. Die
Schwelle ist **entweder** ein Quantil der Dokumenthäufigkeit (`search.citywide_quantile = 0.99`, auf der
Referenz 64 Dokumente und 55 der 5727 Begriffe mit Regel 1, 58 der 5841 ohne sie) **oder** ein Vielfaches
des Medians
(`search.citywide_median_factor`), nie beides — zwei Schwellen wären zwei Wahrheiten, und die Settings weisen
die Kombination beim Laden zurück. Das Quantil ist die Vorgabe, weil es sich dem Datensatz anpasst; auf der
Referenz ist der Median 1 Dokument, ein Vielfaches davon wäre willkürlich. 0,95 statt 0,99 wären 276
Begriffe und damit keine Liste mehr, die jemand liest.

**Die Schwelle ist mindestens 1**, ein stadtweiter Begriff steht also in mindestens zwei Dokumenten. Ohne
diese Untergrenze wäre in einem dünnen Index — eine neue Stadt mit kleinem Korpus hat Tausende Begriffe ohne
Treffer — das Quantil 0 und jeder Begriff mit einem einzigen Dokument stadtweit; über den Median mit Wert 0
dasselbe. Das Quantil zählt dabei **alle** Begriffe des Index, auch die ohne Treffer: ein Begriff ohne
Dokument ist eine Tatsache über das Wörterbuch, kein fehlender Wert. Verworfen, aber gemessen: nur die
Begriffe mit mindestens einem Dokument als Grundgesamtheit (auf der Referenz 3000 von 5727) ergäbe die
Schwelle 84 statt 64 und 29 statt 55 Begriffe — eine andere Regel, nicht eine schärfere Fassung derselben.

**Nur Anzeige, und zwar ausschließlich.** Die Regel ändert keine Zahl. Die Schwelle trifft auch echte
Ortsnamen („hofgarten", „königsallee"), und sie zu entfernen wäre eine Korrektur, die niemand begründen
kann; die Liste ist eine Offenlegung und zeigt dem Leser genau die Fälle, über die das Review streitet,
„schulweg" eingeschlossen (`methodik-review-2026-10.md`, § 2.3).

Einen Schalter `search.citywide_exclude`, der die Begriffe aus der Zählung nahm, gab es am 2026-10-12 für
drei Commits. Er ist wieder weg, weil er nur halb wirkte: er filterte das Wörterbuch im Schritt `results`
im Speicher, während `timeline`, `weights` und das Berichtsmodell weiter das ungefilterte Wörterbuch von
der Platte lasen. Auf der Mini-Fixture mit Schalter an: `results` zählte 65, 49 und 14 Treffer, die Zeile
„Einheit" der Gewichtungstabelle aber 89, 59 und 14 — und die Seite behauptet an dieser Stelle, die Zeile
„Einheit" trage dieselben Zahlen wie Tabelle 5. Der saubere Weg wäre ein gefiltertes Wörterbuch als eigene
Ausgabe mit Stamp, das alle Verbraucher lesen (plus eine Antwort auf die Frage, was mit einem Wahlbezirk
geschieht, dessen Wörterbuch dadurch leer wird). Das ist ein Umbau der Kette für eine Rechnung, die nach
der Begründung oben niemand haben soll — also kein Schalter.

Verworfen: die Begriffe stumm ausschließen (dann wäre die Zahl eine andere und niemand wüsste, warum); ein
Schalter dafür (siehe oben); eine feste Schwelle in Dokumenten (hängt an der Korpusgröße und gilt für keine
zweite Stadt); `hide_in_display` zu erweitern (das versteckt sie in der Anzeige und zählt sie weiter, also
genau die Lösung, die das Review der Arbeit vorhält); die Liste in einen eigenen Seitenabschnitt (sie
gehört zu den Begriffen, und ein Abschnitt mehr kostet eine Nummer in der festen Reihenfolge).

## 45. Lesbare Themen: Stoppwörter aus dem Profil, Saat je Ausschuss, ein passender Ausschuss je Dokument (2026-10-12)

`docs/todo.md`, Punkt 1: die 20 Themen aus TF-IDF und NMF trugen nicht. Gemessen am 2026-10-12 auf der
Referenz prägten Fraktions- und Personennamen sieben der 20 Themen (Thema 3 „antrag, gez, fraktion, cdu,
grünen", Thema 16 „linke, sönke, voigt, julia"). Die Messung aller vier Wege des TODO steht in
`docs/themenmodell-2026-10.md`, das Skript daneben rechnet sie nach. Drei Entscheidungen:

### 45a. Die Stoppwörter kommen aus dem Profil und aus dem Korpus, nicht aus einer zweiten Liste

`topics.stop_sources` wählt die Quellen. `fraktionen` liest Namen, Kürzel und Muster der Parteien und
Gruppen samt der Fraktions-, Gemeinschafts- und Personenmarker aus `[originators]` (Option 04), `gremien`
die Kürzel aus `[bodies]` (Option 05) — **nur die Kürzel**, denn „Verkehrsausschuss" ist ein Themenwort und
„OVA" keines. `namen` erkennt Personennamen daran, dass ein Wort fast nur in einem Namensfenster steht:
`topics.name_window` Zeichen hinter einem Marker aus `topics.name_markers` (Unterschrift und
Amtsbezeichnungen, deutschsprachig und stadtneutral wie `search.place_words`) oder hinter einem
Personenmarker im Textkopf, den Option 04 schon kennt. Über `topics.name_share` (0,8) ist es ein Name: 254
Wörter auf der Referenz, 1,8 s. Wirkung: NPMI der Topwörter +0,4164 → +0,4208 (nach Stufen bis +0,4386),
und die Partei- und Personenblöcke verschwinden; dafür entstehen Schule, Aufsichtsratsbesetzungen und
Verfügungsmittel als eigene Themen. Die Ausnahmen nennt das Profil (`topics.stop_keep`, Düsseldorf:
„klima", „tierschutz" und „bau"). Die ersten zwei sind Sachwörter in einem Gruppennamen; „bau" ist der
Fall, den das Review am 2026-10-13 aufgedeckt hat: **auch ein Gremienkürzel kann mit einem Sachwort
zusammenfallen.** „BAU" ist als Wort „bau" und steht in 1101 von 19 033 Dokumenten (5,8 %); ohne die
Ausnahme fiel die Kohärenz der Stufe `gremien` von +0,4386 auf +0,4282, mit ihr liegt sie bei +0,4364.
„rat" (3751 Dokumente) und „aus" (9320) bleiben Stoppwörter, weil sie wirklich das Gremium nennen; alle
drei Entscheidungen stehen mit ihrer Zahl im Profil.

Verworfen: eine gepflegte Liste von Partei- und Personennamen im Paket (eine zweite Wahrheit neben dem
Profil, und für jede Stadt eine neue); nur den Textkopf lesen (die Namen der Verwaltung stehen unter der
Vorlage, nicht im Kopf); ein Namenslexikon oder `memberships` aus OParl (ein neuer Abruf; damit bleiben
sechs Namen in den Labels, benannt als Grenze); die Gremiennamen mitnehmen (sie sind die Saatwörter von
45b).

### 45b. Ein Thema je Ausschuss, mit fester Wortmatrix

`topics.seed = "committees"` (Vorgabe) gibt jedem Ausschuss mit mindestens `seed_min_documents` beratenen
Dokumenten ein Thema, höchstens `k − free` viele (Referenz: 17 von 23). Die Saat sind die
`seed_words` (30) Wörter mit dem größten Log-Odds-Verhältnis gegen die **anderen Ausschüsse**, mit
informativem Dirichlet-Prior (`seed_prior` Pseudo-Token, Monroe u. a. 2008), beschränkt auf Wörter, die
der Ausschuss auch benutzt (ein Wort, das in keinem Ausschuss steht, bekommt sonst ein positives z, weil
der kleinere Ausschuss weniger Token im Nenner hat; aufgedeckt am 2026-10-13, auf der Referenz ohne
Wirkung); die Zeile der Wortmatrix trägt
sie mit dem TF-IDF-Mittelwert ihres Ausschusses und wird **nicht mehr verändert**
(`non_negative_factorization(..., update_H=False)`). Die `free` (3) übrigen Themen rechnen freie NMF auf dem
Rest `max(X − W·H, 0)`, blockweise auf dem Träger von X gerechnet (die dichte Differenz wären 3 GB). Ein
Thema trägt damit das Kürzel seines Gremiums (`themen.parquet`, Spalte `gremium`, Schema-Version 2) und auf
der Seite seinen Namen aus dem Profil. Treue 0,72 bis 1,00 (Median 0,83), Reinheit 0,15 bis 0,57 — ein Thema
zieht mehr Dokumente an, als in diesem Ausschuss beraten wurden, und ist damit eine Sachkategorie und kein
Abbild der Beratungsfolge. Die Kohärenz fällt dabei von +0,4208 auf +0,3349: gesäte Topwörter sind die, die
einen Ausschuss trennen, nicht die, die am häufigsten zusammen stehen. Das ist der Preis für Namen statt
Nummern, und er ist bewusst bezahlt; `seed = "none"` rechnet weiter freie NMF.

Verworfen: H nur initialisieren (`init="custom"` mit freiem H; NMF wanderte binnen 58 Iterationen von der
Saat weg, Treue 0,00 bis 0,23, und das „OVA"-Thema war der Formelblock der Bezirksvertretungen); binäre
Saatgewichte statt des Zentroids (NPMI +0,2170 gegen +0,3640, und die Labels fallen alphabetisch aus, weil
alle Saatwörter gleich stark sind); anchored CorEx (eine neue Abhängigkeit für dieselbe Idee); die
Ausschüsse von Hand mit Startwörtern beschreiben (Düsseldorf-Wissen im Code, und für jede Stadt neu).

### 45c. Der passende Ausschuss ist eine überwachte Zuordnung mit Restklasse

Der neue Offline-Schritt `committees` lernt mit TF-IDF (Parameter aus `[topics]`, damit es eine Wahrheit
darüber gibt, was ein Wort ist) und logistischer Regression auf den Dokumenten, deren Drucksachennummer ein
Ausschusskürzel trägt, und ordnet jedem Dokument mit Text einen Ausschuss zu — auch denen, die nur im Rat
oder in einer Bezirksvertretung waren. Klassen sind die Ausschüsse mit mindestens
`classify.min_documents` (10) beratenen Dokumenten; unter `classify.min_probability` (0,4, das Achtfache des
Zufalls bei 20 Klassen) bleibt ein Dokument in der **Restklasse**. Güte (fünf Faltungen,
`docs/themenmodell-2026-10-messung.py`): Genauigkeit 0,941, Makro-F1 0,878. Konrads Frage, ob sich jedes
Schriftstück zuordnen lässt, ist damit beantwortet: **nein** — 10,9 % der Ausschussdokumente, aber 81,2 %
der BV- und 87,4 % der Ratsdokumente liegen unter der Schwelle, weil ein BV-Antrag über drei Gegenstände
kein Ausschussthema hat und eine Haushaltsvorlage alle. Von den Ausschussdokumenten treffen 88,9 % ihr
eigenes Gremium.

Ein Teil dieser Güte ist geschenkt (`docs/themenmodell-2026-10.md`, § 4.3): der Volltext trägt die
Beratungsfolge und darin den Namen des Ausschusses (ABA 100 %, SPOA 96,8 %, OVA 91,7 % seiner
Dokumente). Das **Kürzel** ist unschädlich, aber nur, weil Punkt 45a es zum Stoppwort macht — diese
Kopplung ist Absicht und hier ausgesprochen. Sperrt man zusätzlich alle 44 Vokabularwörter mit
„ausschuss", fällt die Kreuzvalidierung auf 0,929 / 0,864 und die Restklasse der BV-Dokumente von
81,2 % auf 79,1 %; die Zahlen oben sind damit eine **Untergrenze** für die Zuordenbarkeit, keine
Schätzung. Gesperrt wird trotzdem nicht: der Gegenversuch kostet eineinhalb Punkte Güte und verschiebt
die Aussage um zwei Punkte. Die genauere Antwort wäre ein Lauf auf dem Text ohne Beratungsfolge und ist
ein eigener Punkt.

Die Zuordnung je Dokument bleibt unter `processed/` (`papers_ausschuss.parquet`, 19 033 Zeilen, als CSV
1,5 MB und nicht aus der dokumentierten Regel ableitbar); veröffentlicht wird die Zusammenfassung
`ausschuss_zuordnung.parquet` (eine Zeile je Ausschuss plus Restklasse, mit „davon ohne
Ausschussberatung"), und der Abschnitt „Gremien" zeigt sie. Die Kette trainiert einmal (6,5 s auf der
Referenz, Grenze waren 30 s); kreuzvalidiert wird nur im Messskript, denn eine Messung ist kein Schritt der
Kette.

Gelernt am 2026-10-13 (Review): die Zuordnung rechnet an **einem** Frame. Vorher kam die Spalte mit dem
beratenen Ausschuss aus einem linken Join und wurde positionell gegen den Korpus und gegen die
Ausgabe verwendet; ein Join legt die Zeilenfolge nicht fest (`crosswalk.py`, `prep/context.py`), und das
ging nur zufällig auf. Jetzt baut `_labelled` einen Frame mit Text und Ausschuss, sortiert nach
Dokument-ID, und Matrix, Klassen und beide Ausgaben entstehen daraus; eine Vorbedingung verlangt eine
Zeile je Dokument in den Gremien (`contracts.unique_keys`), die Nachbedingung ist das gemeinsame
`one_row_per_document`.

Verworfen: die Kreuzvalidierung in den Schritt (verdreifacht seine Zeit für eine Zahl, die niemand je Lauf
braucht); Titel und Drucksachennummer als Merkmale (der Titel nennt oft den Ausschuss, die Güte wäre
geschönt); keine Restklasse (dann hätte jede Haushaltsvorlage einen „passenden" Ausschuss); die Zuordnung je
Dokument veröffentlichen (1,5 MB CSV für eine Schätzung); Einbettungen (`docs/themenmodell-2026-10.md`, § 5:
1 bis 3 Stunden je Durchgang, 800 MB Abhängigkeiten, keine nachlesbaren Wörter — und die billigen Wege
reichen).

## 46. Jede Kennzahl mit Nenner bekommt einen Umschalter, die Mitte ist ungewichtet (2026-10-13)

`docs/todo.md`, Punkt 3, und die stärkste offene Empfehlung des Methodik-Reviews
([methodik-review-2026-10.md](methodik-review-2026-10.md), § 2.6 und § 6). Konrad will auf den Parteikarten
nicht sehen, wo eine Partei viel über Wahlbezirke redet, sondern wie viel mehr oder weniger als der
Durchschnitt aller Parteien. Das Inventar aller Kennzahlen der Seite mit Zähler, Nenner und den möglichen
Normierungen steht in [skalierung-2026-10.md](skalierung-2026-10.md); hier stehen die Entscheidungen.

**Umschalter nur dort, wo eine Normierung etwas ändert.** Von den 35 Kennzahlen der Seite tragen 16 schon
einen Nenner (Anteile der Gremien, Lokalität, Ausschuss-Zuordnung, ρ der Gewichtungstabelle, die
standardisierten Koeffizienten der Kontrollvariablen), sechs sind Modell- oder Güteangaben. Offen waren genau
die zwei Stellen, über die Konrad gestolpert ist: die Treffer je Wahlbezirk (Karte, Tabelle, Kernzahlen) und
die Parteianteile (sechs Karten, zwei Tabellen). Gremien, Monate, Gewichtung, Kontrollvariablen und Begriffe
bekommen **keinen** Umschalter, je mit Grund in § 5 des Konzepts — ein Monat hat keine Wahlberechtigten, ein
Begriff keinen Nenner, und die Gewichtungstabelle *ist* die Sensitivitätsanalyse.

**Die Varianten.** Wahlbezirke: Trefferquote (Standard, unverändert), Treffer absolut, Treffer je Begriff im
Wörterbuch, Abweichung vom Stadtmittel in Prozent. Parteien: Anteil (Standard, unverändert), Abweichung vom
Mittel aller Parteien in Prozentpunkten, Verhältnis zum Mittel. **Die Standardansicht ändert sich nicht**, und
Tabelle 5, die Treffer (29 010) und das Wörterbuch (5727) bleiben unberührt.

**Das Mittel ist das ungewichtete Mittel der Einheiten** — der 41 Bezirksquoten beziehungsweise der sechs
Parteianteile im selben Bezirk. Bei den Bezirken ist die Wahl für die Zahlen gleichgültig (ungewichtet
0,061808 gegen gepoolt 0,061759, Faktor 1,0008) und folgt darum der Regel: ein Wahlbezirk ist eine Einheit,
nicht eine Menge Personen. Bei den Parteien ist sie es nicht: das nach Dokumentzahl gewichtete Mittel wird von
GRÜNEN (2308 Dokumente), CDU (2140) und SPD (2107) fast allein gesetzt, die AfD (183) trägt nichts dazu bei —
wer das Mittel setzt, weicht von ihm kaum ab, und 18 der 29 Vorzeichenwechsel zwischen beiden Mitteln treffen
genau SPD und CDU. **Verworfen:** das gewichtete Mittel als Settings-Schalter (ρ = 0,976 zum ungewichteten,
also fast dieselbe Ordnung, aber ein neuer Settings-Schlüssel, ein neuer Fingerprint und eine zweite Legende
für eine schwerer erklärbare Größe; wer es will, rechnet es aus der veröffentlichten Tabelle).

**Divergierend heißt feste, symmetrische Grenzen, keine Quantile.** Die Abweichung vom Stadtmittel ist eine
streng monotone Umrechnung der Trefferquote; Quantilklassen darüber wären dieselben Klassen, nur anders
gefärbt. Darum stehen die Grenzen fest in `defaults.toml` (`report.diverging`): ±10 % und ±25 % vom
Stadtmittel (Klassen mit 6, 12, 11, 8, 4 Bezirken), ±0,5 und ±2 Prozentpunkte für die Parteien (23, 67, 64,
72, 20 Zellen) und 0,5 / 0,8 / 1,25 / 2,0 für das Verhältnis (61, 32, 60, 78, 15 Zellen; log-symmetrisch um
1). Die mittlere Klasse ist die um das Mittel; sie trägt wie jede andere ihren Bereich als Beschriftung
(„−10 % bis unter +10 %"), und der Begleitsatz der Legende sagt „etwa im Mittel". **Verworfen:** das
Log-Verhältnis, das `docs/todo.md` als
Möglichkeit nennt — 20 der 246 Parteizellen sind exakt 0 (die AfD bedient 41 Bezirke mit 183 Dokumenten), und
`log(x + ε)` macht die Grenzen von ε abhängig.

**Die Klassen der neuen Parteivarianten sind gemeinsam, die der Standardvariante bleiben je Partei.** Der
Anteil ist zwischen einer Fraktion mit 2308 und einer mit 183 Dokumenten nicht vergleichbar (darum rechnet die
Seite dort Quantile je Partei, Punkt 27); Abweichung und Verhältnis sind in derselben Einheit gegen dieselbe
Bezugsgröße gemessen, und die Vergleichbarkeit über die sechs Karten ist der Zweck der Variante.

**Ein Muster, nicht drei.** Der Umschalter ist ein `fieldset` mit Radios, das Makro `metric_switcher` in
`templates/macros.html.j2` baut es; die Varianten hängen als `data-class-<variante>`,
`data-text-<variante>` und `data-value-<variante>` an Flächen, Zellen und Zeilen, und ein generisches Stück
JavaScript im Rahmen tauscht sie je Radiogruppe **innerhalb ihres `<section>`** samt Legende
(`#legend-<variante>`). Der Kartenumschalter aus dem Fundament F1 (Punkt 21) ist darauf umgestellt, ohne sein
Verhalten zu ändern. Keine zweite Kopie der Karten-SVGs: die 41 Flächen stehen weiter einmal in `<defs>`, die
Varianten sind Attribute (rund 52 KB für alle Umschalter zusammen, Budget 1,5 MB). Ohne JavaScript zeigt die
Seite die Standardvariante.

**Eine nicht angetretene Partei zählt im Mittel mit.** Wo eine Partei keinen Wahlvorschlag hatte
(Düsseldorf: Die Linke im Wahlbezirk 11), bleibt ihr Dokumentanteil eine echte Zahl — sie hat dort
Dokumente geschrieben oder nicht, unabhängig vom Wahlzettel —, und das Mittel aller Parteien ist das Mittel
aller sechs Anteile. Ausgelassen wird dieser Bezirk nur beim Abgleich mit dem Stimmenanteil (`r` und `p`,
Punkt 27): dort ist ein Anteil von 0 keine Zustimmung von 0. Beide Regeln stehen jetzt in der Spaltendoku
von `wahlbezirke_parteien` und in „Methode und Grenzen".

**Was die Grenzen nicht auslösen.** `[report.diverging]` steht unter `[report]` und ist damit aus dem
Settings-Fingerprint ausgenommen (`docs/plans/00-synergien.md`, § 5.4): eine andere Grenze färbt die Karte
um, rechnet aber keine Zahl neu. Der Preis ist, dass `georep status` den Schritt `report` nach einer
geänderten Grenze als „aktuell" meldet — wie nach einer geänderten Vorlage; beides braucht ein
`georep run report --force` und steht in `STATUS.md` unter „Bekannt".

**Wo die Zahlen herkommen.** Der neue Offline-Schritt `metrics` schreibt
`processed/wahlbezirke_kennzahlen.parquet` (Treffer, Begriffe, Treffer je Begriff, Treffer je 1000
Wahlberechtigte, Stadtmittel, Abweichung); `wahlbezirke_parteien` bekommt drei Spalten (`mittel_anteil`,
`abweichung_mittel`, `verhaeltnis_mittel`). **Verworfen:** die Spalten in `wahlbezirke_auswertung` — die Datei
ist Golden Master (`tests/fixtures/mini/expected/`, Punkt 11), und eine Kennzahl, die nicht von der Arbeit
stammt, gehört nicht hinein.

**Nicht gebaut, mit Grund** (ausführlich in § 5 des Konzepts): „je 1000 Wahlberechtigte" als eigenes Radio
(es *ist* der Standard mit einem positiven Faktor — jede Fläche behielte ihre Klasse und ihre Farbe; die
Lesart steht als Satz an der Legende, während „Treffer absolut" eine eigene Variante ist, weil sich dort 17
von 41 Klassen ändern); das Verhältnis zum Stadtmittel (1 + Abweichung, dieselbe Information zweimal — bei
den Parteien sind beide nötig, weil dort jeder Bezirk ein anderes Mittel hat); „je Einwohner" (keine
Bevölkerungszahl je Wahlbezirk in den Daten, `wahlbezirke_kontext` trägt nur Anteile und Punktwerte) und „je
Fläche" (misst Dichte, nicht Repräsentation).

**Der zweite Zusammenhang gehört dazu.** Mit x = Treffer je Begriff im Wörterbuch bleibt vom Befund der
Arbeit nichts, nicht einmal das Vorzeichen: über alle 41 Bezirke r = −0,1118 und p = 0,48644 (Trefferquote:
0,1891 und 0,23641), ohne die Ausreißer 1 und 10 r = −0,0419 und p = 0,80000 (Trefferquote: 0,3351 und
0,03705). Die einzige „signifikante" Spalte der Arbeit verschwindet, sobald die Wörterbuchgröße
herausgerechnet ist — das stützt ihren Befund und entkräftet ihre zweite Spalte, und es ist nach Tabelle 6
(Punkt 26) die dritte unabhängige Prüfung mit demselben Ergebnis. Tabelle 5 selbst bleibt unverändert.

## 47. Die Literaturübersicht ist Daten, nicht Vorlage; die Stadt ergänzt, sie ersetzt nicht (2026-10-13)

`docs/todo.md`, Punkt 5. Die Seite nannte die Arbeit nur im Nebensatz von „Methode und Grenzen"; jetzt steht
zwischen „Abgeleitete Daten" und „Downloads" der Abschnitt „Literatur und verwandte Arbeiten" (`#literatur`,
Abschnittsnummer 67) mit fünfzehn Einträgen, je mit vollständiger Zitation und einem oder zwei Sätzen, was die
Arbeit beiträgt und wie dieses Vorhaben sich dazu verhält.

**Die Einträge stehen in einer eigenen Paketdatei, nicht in `defaults.toml`.** `src/georep/report/literatur.toml`
trägt die stadtneutralen Einträge, `[[report.literature]]` im Profil die stadtspezifischen;
`report/literature.py` stellt die des Profils vor die der Paketdatei. Grund ist `deep_merge`: es mischt
Tabellen rekursiv und **ersetzt** Listen, ein Profil könnte eine Liste in `defaults.toml` also nur
überschreiben, nicht ergänzen — und genau das Erben ist der Zweck, damit eine zweite Stadt die allgemeinen
Einträge bekommt, ohne sie zu kopieren (Mönchengladbach erbt heute alle dreizehn). Dazu passt, dass `defaults.toml`
Parameter mit Begründung sammelt, keine Bibliografie: ein Literaturverzeichnis ist Inhalt, kein Schalter, und
es würde die Datei verdoppeln. **Verworfen:** `[[literature]]` in `defaults.toml` plus ein zweiter Schlüssel
`extra_literature` im Profil (zwei Listen für eine Liste); die Einträge in der Vorlage (dann wäre jede neue
Quelle eine Vorlagenänderung, und `georep run report --force` nötig, ohne dass es jemand sieht); eine
Markdown-Datei unter `docs/` als Quelle (sie müsste geparst werden, und die Validierung fiele weg).

**Die Arbeit zur Stadt ist ein Profileintrag und steht oben.** Sie ist der Ursprung der Seite, aber sie
handelt von einer Stadt; im stadtneutralen Teil hätte sie nichts zu suchen (`tests/unit/test_report_literature.py`
prüft die Datei mit derselben Stadtwortliste wie Code und Vorlagen). Darum stehen die Profileinträge vorn und
die allgemeinen dahinter. Folge, bewusst in Kauf genommen: die Seite einer zweiten Stadt verlinkt in „Methode
und Grenzen" weiter das Original-Repository, führt die Arbeit aber nicht in ihrer Literatur — sie ist der
Ursprung des Programms, nicht der Untersuchung dieser Stadt.

**Ein Eintrag muss nachprüfbar sein.** `LiteratureEntry` (in `georep.settings`, neben `ReportSource`) verlangt
Autor, Titel wörtlich wie in der Quelle, Ort oder Institution, ein Jahr zwischen 1900 und 2100, einen Satz
zum Beitrag und entweder eine `https`-URL mit Abrufdatum oder einen DOI der Form `10.xxxx/…`; der Schlüssel
ist die Anker-ID `lit-<key>` und darf nur einmal vorkommen, auch nicht einmal im Profil und einmal im Paket.
Das Abrufdatum liegt zwischen 1990 (das Jahr, in dem das Web öffentlich wurde) und 2100 — ein festes Fenster
statt „nicht nach heute", denn eine Uhr in der Validierung der Settings machte dieselbe Datei morgen gültig
und gestern nicht (Punkt 10: Zeit ist eine Eingabe). Der Satz zum Beitrag ist Pflicht, weil die Übersicht
sonst eine Linksammlung wäre und der Vergleich mit dem README für einen leeren Wert tautologisch. Alle Links waren am 2026-10-13 erreichbar
(Statuscode geprüft), alle DOI über Crossref aufgelöst. **Die eine Ausnahme ist `pending = true`:** ein
Eintrag, der aus dem Literaturverzeichnis einer nicht öffentlichen Arbeit nachzutragen ist, darf Jahr und Link
vermissen, und die Seite schreibt „Angaben nachzutragen" sichtbar daneben, statt eine Zitation zu behaupten.
Zwei Einträge sind so markiert: die Arbeit selbst und die Kölner
Untersuchung, die die Arbeit zitiert — am 2026-10-13 in OpenAlex, Crossref, arXiv, Hochschulrepositorien und
auf GitHub nicht auffindbar. **Verworfen:** die Kölner Untersuchung weglassen (dann wäre die Lücke
unsichtbar) und einen Platzhalter mit erfundenem Jahr (eine Zahl, die niemand geprüft hat, ist schlimmer als
keine).

**Die URLs kommen über die Settings in die Allowlist.** `render.model_links` liest sie aus
`model.literature`, so wie es die Quellen aus `[[report.sources]]` liest (Punkt 36); die Nachbedingung von
`render_report` bleibt unverändert, und kein Link einer Zitation zwingt eine Konstante mit einem Orts- oder
Projektnamen in den Code. Erlaubt ist damit nicht „was im Paket steht", sondern was die Lesereihenfolge der
Settings hergibt — neben `literatur.toml` und dem Profil auch `settings.toml`, `settings.local.toml`, eine
Datei hinter `--settings` und `GEOREP_REPORT__LITERATURE`. Das ist dieselbe Grenze wie bei Punkt 36 und
derselbe Grund: wer die Settings schreibt, bestimmt die Seite ohnehin; ein Link aus den **Daten** (einem
Dokumenttitel etwa) bleibt verboten.
Die Links sehen aus wie jeder andere auf der Seite: kein `target="_blank"`, also auch kein
`rel="noopener"` — das wirkt nur mit `target`. Der Abschnitt hatte es an jedem Link, der Dialog der Dokumente
an den PDF-Links, die übrigen zwanzig Links der Seite nicht; jetzt steht es nirgends, und die eine Regel ist,
dass diese Seite keinen Link in einem neuen Fenster öffnet (Review 2026-10-13). Ein Test zählt stattdessen
die Links der Einträge gegen die Links im Abschnitt, damit keiner fehlt.

**Das README pflegt dieselbe Liste von Hand, ein Test hält beide zusammen.** Der Abschnitt „Literatur" im
README trägt Autor, Titel, Ort, Jahr, Link, Abrufdatum und denselben Satz je Eintrag, in derselben
Reihenfolge; `tests/unit/test_report_literature.py` vergleicht Feld für Feld.
**Verworfen:** das README zur Bauzeit erzeugen (das Repo hat keinen Generator-Schritt für versionierte
Dateien, und eine erzeugte Datei im Repo braucht eine Prüfung in CI — also denselben Test, nur mit einem
Werkzeug mehr).

Kosten: `index.html` wächst um 13 166 Bytes auf 1 281 464 Bytes (Budget 1,5 MB): 12 429 der Abschnitt samt
Zeilenumbruch, 663 sein CSS, 102 der Satz in „Methode und Grenzen", minus 28 für das `rel="noopener"`, das
mit diesem Abschnitt aus dem Rahmen verschwand (gemessen am 2026-10-13). Der Settings-Fingerprint ändert
sich **nicht**, denn `[report]` ist aus ihm ausgenommen (Punkt 46, STATUS.md unter „Bekannt“) — nach einer neuen Quelle meldet
`georep status` den Schritt `report` als „aktuell", und die Seite braucht wie nach jeder Vorlagenänderung ein
`georep run report --force`.

## 48. Lange Tabellen zeigen drei Zeilen, und die Vorschau ist eine CSS-Regel (2026-10-13)

`docs/todo.md`, Punkt 2, erster Teil: die Seite steht ganz ausgeklappt da, 43 Tabellen, vier davon mit
41 Zeilen. Konrad wünscht „Tabellen zu, nur zwei bis drei Zeilen sichtbar, der Rest auf Bedarf". Die
Messung je Abschnitt, je Tabelle und je Element steht in [seitengroesse-2026-10.md](seitengroesse-2026-10.md).

**Ein `<button>`, kein `<details>`.** Das Inhaltsmodell von `<tbody>` erlaubt nur `<tr>` und
skript-tragende Elemente; ein `<details>` um die hinteren Zeilen trägt der HTML-Parser aus der Tabelle
heraus (foster parenting), die Zeilen landen davor und sind keine Tabellenzeilen mehr. Also ein
`<button type="button">` mit `aria-expanded` und `aria-controls` auf die Tabelle, gebaut vom Makro
`more(id, rows, preview)` in `templates/macros.html.j2`. Er steht **vor** seiner Tabelle, wie das
Aufklappmuster der WAI-ARIA Authoring Practices es vorsieht: hinter 41 Zeilen rutschte er beim
Aufklappen mit dem Fokus aus dem Bild (von y = 436 auf y = 3924, Review 2026-10-13). Ein Dreieck
aus `::before` zeigt den Zustand (`▸` zu, `▾` offen) und kommt aus `aria-expanded`, nicht aus
JavaScript — es kann also nicht lügen, und die Zeile sieht nach Bedienelement aus statt nach Link. **Verworfen:** die Tabelle in zwei Tabellen
zerlegen und die zweite in ein `<details>` stecken (zwei Spaltenbreiten, zwei Sortierungen, der Kopf
gilt nur noch für die Vorschau); ein `<details>` je Zeile (41 Aufklapper sind keine Tabelle mehr).

**Die Vorschau ist eine Regel, kein Attribut je Zeile.** `table.preview tbody tr:nth-child(n+N)`
verbirgt, was über die Vorschau hinausgeht, und `table.preview.open tbody tr, table.preview tbody
tr.selected` zeigt es wieder. Das ist nicht nur kleiner (240 Byte für elf Tabellen statt rund 3 KB
`hidden` an 428 Zeilen), sondern macht drei Dinge ohne eine Zeile JavaScript richtig: nach dem
Sortieren zählt `nth-child` die **neue** Folge, also stimmt die Vorschau weiter; eine Zeile, die
`georep.select(ids, scroll)` markiert, klappt von allein auf und wird gescrollt, und beim nächsten
`select` räumt dieselbe Mechanik auf, weil `select` die Klasse überall entfernt; `@media print` zeigt
alles. Die Umschalter der Normierung (Punkt 46) suchen im ganzen Dokument und bedienen verborgene
Zeilen unverändert — geprüft mit headless Chrome, nicht nur im Test.

**Ohne JavaScript steht alles offen.** Ein `<noscript><style>` im Kopf hebt die Vorschau auf und
blendet die Schaltfläche aus, die ohne Skript nichts tun könnte; beides mit `!important`, weil die
Vorschauregel über `:nth-child` spezifischer ist. **Verworfen:** die Vorschau erst im JavaScript
aufbauen (dann sieht jeder Leser die Tabelle einmal lang und dann kurz, ein Sprung im Layout);
`hidden` im Markup ohne `<noscript>` (dann wäre die Seite ohne Skript unvollständig).

**Welche Tabellen.** Vorschau bekommen die zwölf Aufzählungen, elf davon auf der heutigen Seite und
`perioden-tabelle`, sobald die zweite Periode Daten hat. Offen bleiben die Kernzahlen, Tabelle 5,
Tabelle 6 und 6b: das ist der Befund, und wer die Zahl sucht, um die es geht, soll sie ohne Klick
sehen — das Kriterium ist die Rolle und nicht die Zeilenzahl (Tabelle 6b hat 13 Zeilen und bleibt
offen). Dass eine kurze Aufzählung keine Schaltfläche bekommt, erledigt das Makro von selbst: es
setzt sie erst über der Vorschauzahl. Die sechs Tabellen der Spaltendoku stehen schon je in einem
`<details>` und brauchen nichts.

**Der Kontrast war zu klein.** `--accent` trug in Hell 4,19:1 auf `--bg` — unter den 4,5:1, die
WCAG AA für 14,4-px-Text verlangt, und das betraf jeden Link der Seite, nicht nur die neue
Schaltfläche (Review 2026-10-13). Hell ist `--accent` jetzt `#1f68c0` (5,24:1 auf `--bg`, 5,38:1
auf `--surface`), Dunkel bleibt `#3987e5` (5,34:1 und 4,79:1); `--q2` bleibt `#2a78d6`, denn die
Farbskala der Karte trägt keinen Text. Die vier Zahlen stehen als Kommentar an der Palette, und ein
Test rechnet sie aus der gerenderten Seite nach, damit sie nicht allein im Kommentar stehen.

**Drei Zeilen stehen in den Settings** (`report.table_preview_rows`, 0 heißt „nichts einklappen"), weil
die Zahl Geschmack ist und nicht Technik; sie gilt für alle Tabellen gleich. `[report]` zählt nicht zum
Settings-Fingerprint, eine andere Zahl braucht also `georep run report --force` (wie jede
Vorlagenänderung, STATUS.md unter „Bekannt"). Kosten: die Seite wächst um 4130 Byte.

## 49. Die Begriffslisten je Wahlbezirk werden nachgeladen (2026-10-13)

`docs/todo.md`, Punkt 2, zweiter Teil. Die 41 Listen (3946 `<li>` mit je einer Schaltfläche) waren mit
333 750 Byte der größte Posten der Seite — 26 % — und standen dort in zugeklappten `<details>`: Daten,
die niemand sieht, der sie nicht aufklappt. Sie liegen jetzt als `data/begriffe.json` (96 KB) neben der
Seite, und `sections/50-begriffe.js` holt sie beim ersten Aufklappen, wie der Dialog `dokumente.json`
beim ersten Klick auf einen Begriff holt.

**Was inline bleibt**, weil es den Abschnitt trägt: die zwanzig trefferstärksten Begriffe stadtweit,
die 55 stadtweiten Begriffe (Punkt 44), die fünf häufigsten Begriffe je Wahlbezirk in der
Bezirkstabelle und je Wahlbezirk seine Zahl in der Zusammenfassung des `<details>`. Wer den Abschnitt
nur liest, braucht nichts nachzuladen.

**Der Unterschied zur Suche ist der Zweck, nicht die Größe.** Der Vorschlagsindex (139 KB) liegt
bewusst in der Seite, weil Vorschläge ohne Webserver funktionieren müssen und `fetch` unter `file://`
verboten ist (Punkt 22). Eine Begriffsliste je Wahlbezirk ist kein Einstieg, sondern ein Stöbern im
Ergebnis: aus `file://` steht dort derselbe Satz, den der Dokumentdialog seit Stufe G zeigt —
`georep.offlineNote(was, datei)` im Rahmen formuliert ihn einmal für beide. Welcher Satz, entscheidet
`location.protocol`: aus dem Dateisystem verbietet der Browser `fetch`, über http ist es ein 404 oder
eine halbe Datei, und beides mit derselben Erklärung zu bedienen schickte den Leser auf eine falsche
Fährte (Review 2026-10-13, Befund 11). Die beiden Zweige prüft ein Test mit `node`. **Verworfen:** die Listen
in `dokumente.json` mitführen (2,3 MB laden, um 72 Begriffe zu zeigen); sie im Browser aus
`combined_searchdict.parquet` lesen (eine Bibliothek für Parquet, und die Trefferzahlen fehlen dort);
eine Unterseite je Wahlbezirk (41 Dateien, und die Reihenfolge der Abschnitte bleibt,
`docs/plans/00-synergien.md`, § 5.1).

**Eine veröffentlichte Datei, kein Nebenprodukt.** `begriffe.json` steht mit Zeilenzahl (3946 Paare
aus Wahlbezirk und Begriff **mit Treffer**; die 6877 Paare des Schritts `metrics` zählen auch die
Begriffe ohne Treffer, Review 2026-10-13), Größe und SHA-256 unter „Downloads" wie `dokumente.json`; die Regel, dass
jede Datei unter `site/data/` auf der Seite genannt wird, hält ein Test. Ins `schema.json` kommt sie
nicht — das beschreibt die Spalten der Tabellen, und die beiden JSON-Dateien tragen ihre Felder selbst
(`fields`).

**Eine Datei wird einmal geholt.** `georep.loadJson(pfad)` im Rahmen hält je Pfad ein Versprechen;
`georep.forget(pfad)` wirft es weg, damit ein zweiter Versuch nach einem Fehler erlaubt bleibt. Dazu
hängt der Klick auf einen Begriff jetzt als **ein** Zuhörer am Dokument (`closest("button.term")`)
statt an jeder Schaltfläche: eine nachgeladene Liste wirkt damit ohne weitere Verdrahtung, und die
Seite legt rund viertausend Zuhörer weniger an.

Kosten und Wirkung: `index.html` 1 285 594 → 958 527 Byte (−327 067, −25 %); `site/data/` wächst um
96 413 Byte auf 53 Dateien. Ohne JavaScript bleiben die Listen leer — der Abschnitt sagt das in einem
`<noscript>` und nennt die Datei.

## 50. Das Budget der Seite steht in den Settings und ist 1,0 MB (2026-10-13)

`docs/todo.md`, Punkt 2, dritter Teil. Das Budget war `1_500_000` als Zahl in vier Tests (Fundament F1,
Punkt 21) und hat nie gezuckt, während die Seite zwischen dem 2026-10-11 und dem 2026-10-13 um 594 KB
wuchs (Suche 142 KB, Umschalter 110 KB, Parteikarten 63 KB, Gewichtung 33 KB, Monate 30 KB, Literatur
13 KB). Jetzt steht es als `report.page_budget_bytes = 1000000` in `defaults.toml`, die slow-Tests
lesen es von dort, und der Schritt `report` meldet eine Überschreitung in seiner Zeile („Seite über
dem Budget (1,05 von 1,00 MB)") — damit es nicht erst der slow-Test oder niemand merkt. `0` schaltet
die Prüfung ab.

**Das Budget muss den Abschnitt „Zwei Wahlperioden" tragen.** Er kommt nach Konrads Lauf dazu und
kostet gemessen rund 35 KB (6859 Byte fest und 551 je Wahlbezirk an der Mini-Periode, dazu 41 statt
drei Punkte im Änderungsdiagramm); „Laufende Wahlperiode" und die Städtezeile aus `georep publish`
kommen obendrauf. Mit 958 527 Byte blieben 41 473 Byte Luft — zu wenig (Review 2026-10-13, Befund 2).
Darum ist **ein Hebel aus § 5 gezogen**: die `<title>` der 1196 Orts-Kreise, 73 842 Byte. Sie waren
kein Verlust, denn ihre Ebene ist `aria-hidden="true"` und ohne JavaScript nie sichtbar — der Titel
erreichte keinen Screenreader und wiederholte nur, was der Tooltip aus `data-name` und
`data-district` zeigt. Die Seite trägt jetzt 886 328 Byte, also **113 672 Byte Luft (11,4 %)**, und
der Abschnitt passt mit rund 79 KB Rest. **Verworfen:** das Budget auf die Zahl zu heben, die der
Vergleich braucht (dieselbe Blindheit, nur später); 1,1 MB; das Budget im Code (es ist eine
Verabredung über die Anzeige, keine Grenze der Technik, und `[report]` zählt nicht zum
Settings-Fingerprint); den Schritt bei Überschreitung scheitern lassen (eine Seite, die 20 KB zu groß
ist, soll trotzdem entstehen — die Zeile sagt es, der Test hält es).

**Geprüft wird an drei Stellen.** Der Schritt `report` nennt eine zu große Seite in seiner Zeile; die
slow-Tests prüfen sie über `within_budget` aus `tests/conftest.py` (0 heißt dort wirklich „keine
Prüfung", vorher wurden die vier Zusicherungen mit 0 rot); und `georep publish` prüft **jede**
kopierte Seite (`PublishSummary.over_budget`), denn erst dort kommen die Zeile „Weitere Städte" und
die Vergleichsseite dazu. Die Seite mit dem Abschnitt „Zwei Wahlperioden" hat ihre eigene Zusicherung
in `tests/golden/test_period_pipeline.py` — sie ist die einzige, die den Abschnitt überhaupt zeigt.

**Was nicht gemacht wurde, steht gemessen daneben** (§ 5, rund 40 KB Reserve): ein gemeinsames
`<defs>` für die 41 Flächen (28 KB) verlangt, dass auch die Hauptkarte ihre Flächen als `<use>`
zeichnet, und dort hängen Klick, Hover, `tabindex="0"`, Tooltip und der Klassentausch des Umschalters
— ob Selektoren den geklonten Inhalt treffen und ob ein `<use>` überall fokussierbar ist,
unterscheidet sich zwischen SVG 1.1 und SVG 2 und ist hier nur in Chrome prüfbar; 3,2 % sind das
Risiko am Herzstück der Seite nicht wert. Der Minify-Schritt für Leerraum fällt mit 0,50 % unter die
Grenze von 5 %, die der Auftrag gesetzt hat; die Vorlagen schreiben mit `trim_blocks` und
`lstrip_blocks`, es steht also schon fast kein Leerraum in der Datei.

## 51. Ein Schnittstück unter `crosswalk.min_share` ist ein Splitter (2026-10-13)

Zwei Flächen, die nur eine Grenze teilen, schneiden sich in Fließkomma nicht in 0, sondern in etwas
wie 4,44e-16. `area_shares` nahm jedes Stück mit `area > 0.0` und machte daraus eigene Zeilen: die
veröffentlichte `wahlbezirke_crosswalk.parquet` trug 20 Zeilen mit Gewichten bis 1,3e-10, die
kleinste 2,9e-17. Das ist kein kleines Gewicht, sondern keines — und es ist nicht einmal stabil: ob
so ein Nichts über 0 liegt, hängt an den Koordinaten und nicht an der Geografie. hypothesis hat
genau das gefunden (`test_scaling_the_grid_does_not_change_the_shares`, 2026-10-13): dasselbe
Rechteck ergab in einem um 1,4603 gestreckten Gitter eine Zeile mehr, und die Eigenschaft „Anteile
sind dimensionslos" brach.

**Die Schwelle ist ein Anteil der Quellfläche, kein Maß in m².** `crosswalk.min_share = 1e-9`
(0 schaltet ab) heißt: ein Schnittstück unter einem Milliardstel der Quellfläche fällt **vor** der
Normierung weg, zählt also weder als Zeile noch zur Bedeckung, und die übrigen Anteile summieren
weiter zu 1 (`sums_to_one` bleibt, `min_coverage` bleibt der Wächter dafür, dass die beiden
Gliederungen überhaupt zusammengehören). Ein Anteil ist dimensionslos und skaliert mit der Karte;
genau das verlangt die Eigenschaft, an der der Fehler aufgefallen ist. **Verworfen:** eine absolute
Schwelle in m² (sie hängt an der Einheit des CRS — in Grad gerechnet wäre 1e-9 m² eine andere
Größe — und sie bricht dieselbe Eigenschaft wieder, sobald eine Karte skaliert wird); die Schwelle
nur im Test (dann stünde das Rauschen weiter in der veröffentlichten Tabelle, und der Test prüfte
nicht mehr, was das Programm tut); `shapely.set_precision` auf den Eingabegeometrien (ein Gitter
über alle Koordinaten ändert echte Flächen, um ein Rechenartefakt zu treffen).

**Gemessen auf der Referenz** (2026-10-13, Stimmbezirke gegen die 171 Sozialräume des
Quartiersatlas): `area_shares` liefert 1134 statt 1244 Zeilen, der kleinste Anteil steigt von
6,8e-19 auf 1,1e-09, die kleinste Bedeckung bleibt 0,99987530. Die veröffentlichte
`wahlbezirke_crosswalk` hat 465 statt 485 Zeilen (das größte entfallene Gewicht ist 1,3e-10, die
größte Änderung an einem bleibenden Gewicht 1,7e-10). Weiter: `wahlbezirke_kontext` ändert sich um
höchstens 8,9e-09 (relativ 6,4e-11), Tabelle 6 um höchstens 3,9e-08 an einem Koeffizienten, 3,2e-11
an einem R², 5,6e-10 an einem p. **Auf der Seite ändert sich keine gedruckte Stelle:** die
Abschnitte Kernzahlen, Zusammenhang (Tabelle 5), Kontrollvariablen (Tabelle 6 und 6b),
Abgeleitete Daten, Wahlbezirke, Gewichtung, Parteien, Gremien, Monate, Begriffe und Methode sind
byteidentisch, `wahlbezirke_auswertung.parquet` ist byteidentisch, die Treffer bleiben 29 010 und das
Wörterbuch 5727. Verschoben haben sich nur die Zeilenzahl und die Prüfsumme der beiden
Crosswalk-Dateien im Abschnitt „Downloads".

**Zuerst der rote Test.** Die Eigenschaft „kein Anteil unter der Schwelle in der Ausgabe"
(`tests/property/test_crosswalk_props.py`) und zwei Beispiele mit zwei Flächen an einer gemeinsamen
Grenze (`tests/unit/test_crosswalk.py`: die Berührung wird keine Zeile; ein Zipfel von 1e-7 bleibt
mit der Vorgabe und fällt mit einer groben Schwelle weg, und der Rest ist dann genau 1) waren vor
der Änderung rot (Exit 1, `TypeError: <lambda>() got an unexpected keyword argument 'min_share'`
im Vertrag und ein Importfehler für `MIN_SHARE`), danach grün — samt dem gespeicherten
Gegenbeispiel in `.hypothesis`. Die Vorgabe steht zweimal, als `crosswalk.MIN_SHARE` (Vorgabe der
Funktion) und in `settings.py`: `georep.geo` liest die Settings und `crosswalk` liest `geo`, ein
Import wäre ein Zyklus. Ein Test hält beide Zahlen zusammen.

Kosten: ein neuer Settings-Schlüssel, also ein neuer Fingerprint und ein einmaliger Lauf aller
Offline-Schritte (23 s, STATUS.md unter „Bekannt").

## 52. Auch die Stadt der Arbeit rechnet unter ihrem Slug (Konrad, 2026-10-13)

Jede Kommune bekam mit Option 01 einen Unterordner unter `data_root` und `cache_root` (ihren Slug), nur
Düsseldorf blieb flach: `profile = ""`. Das war die Annahme der Phase 3 zu Frage 1.7 und eine Ausnahme ohne
Grund im Code — sie lebte davon, dass genau eine Stadt die veröffentlichte Adresse besitzt. Konrad hat die
Frage am 2026-10-13 mit „Umzug gewünscht" beantwortet. Seitdem steht `profile = "duesseldorf"` im Profil,
und die Hauptperiode liegt unter `data_root/duesseldorf/` und `cache_root/duesseldorf/`; `http.sqlite`
bleibt geteilt, sein Schlüssel ist die URL.

**Die veröffentlichte Adresse bleibt, weil sie `georep publish` setzt, nicht der Lauf.** Die erste Stadt aus
`publish.cities` kommt an die Wurzel von `data_root/site/`, jede weitere nach `site/<slug>/` (Punkt 38); neu
ist nur, dass auch die erste Stadt kopiert wird, weil ihr Ordner nicht mehr die Wurzel ist. Das ist die
bessere Ordnung: die Quellseite trägt die Zeile „Weitere Städte" nie, erst die Kopie bekommt sie, und ein
zweiter Lauf ist dadurch von sich aus wiederholbar. `pages.yml` ruft darum `publish` (das tat es schon) und
legt die Unterseite der zweiten Periode in den Ordner der **Stadt**, nicht nach `data/site/`: der Abschnitt
„Zwei Wahlperioden" verlinkt `<profil>/` relativ zur Stadtseite, und nur so nimmt die Kopie sie mit.

**Wo die Hauptperiode liegt, sagt `Settings.base_profile`, und das ist `city.slug`.** Zwei Stellen lasen sie
vorher als `for_profile("")`: das Wörterbuch eines Periodenprofils (`period.dictionary = "base"`) und der
Zielzuschnitt eines Crosswalk-Profils (`Layout.target_view`). Der Slug ist der Dateiname des Stadtprofils
(`_slugs_match_their_file`), und eine Periode erbt ihn über `base`; im Stadtprofil selbst steht er zweimal,
als `city.slug` (der Name) und als `profile` (der Ordner), weil `profile` je Profil setzbar sein muss — eine
Periode hat einen anderen. Dass beide zusammenpassen, prüft seit dem Review vom 2026-10-13 das Laden:
`_slugs_match_their_file` verlangt von jedem Profil, das `city.slug` setzt, denselben Wert als `profile`
(geerbt käme dort der leere Ordner aus `defaults.toml` heraus, und `base_profile` wäre eine Lüge).
`_period_profile_is_consistent` verlangt umgekehrt für ein Profil mit dem Wörterbuch der Hauptperiode einen
anderen Ordner als sie, mit je einem Satz für die zwei Fälle (derselbe Ordner; `profile = ""`, das gar keiner
ist, sondern die Wurzel darüber). Ein Test über alle Paketprofile hält dazu fest, dass in einem Ordner nie
zwei Städte rechnen.

**Verworfen:** `base_profile` als eigener Settings-Schlüssel (er stünde neben `profile` ein zweites Mal im
Stadtprofil und wäre ein Tippfehler von einem Lauf im falschen Ordner entfernt); den Ordner der Wurzel des
Profilbaums beim Laden merken (dasselbe Ergebnis, aber ein Feld, das nur `load_settings` füllt, und
`Settings(**merged)` aus einem Test hätte es nicht); Düsseldorf flach lassen und jeder zweiten Stadt ihren
Pfad explizit setzen (`settings.local.toml` gewinnt über das Profil, zwei Städte überschrieben sich); eine
Landing-Page an der Wurzel statt der ersten Stadt (bricht die veröffentlichte Adresse, Punkt 38).

**Gemessen am 2026-10-13** auf Konrads Rechner (`bootstrap`, dann `run`, 23 s): 27 der 28 Parquet-Dateien
unter `processed/` und `interim/` sind byteidentisch zu denen des flachen Laufs, `index.html` ist 886 328 Byte
wie vorher. Die 28., `interim/papers.parquet`, unterscheidet sich an genau drei von 19 108 Texten — und das
ist nicht der Umzug: der flache Lauf nahm diese drei aus den 200 lokal extrahierten PDFs, wo pypdf 6.20.0
drei Texte der Arbeit nicht zeichengleich reproduziert (STATUS.md, „Bekannt"). Keine Tabelle danach merkt es. Die Seite nennt keinen Datenpfad, und so unterscheiden sich die beiden Dateien nur an den Stellen,
die Zeit und Version ohnehin tragen: Erzeugungszeit, Commit, dreimal die Versionsnummer in einer
nachgeladenen JSON-Datei und deren Prüfsummen (0.11.0 gegen 0.12.0, der flache Lauf ist vom 2026-10-13,
05:58 UTC). Der Settings-Fingerprint ändert sich nicht, denn `profile` ist ein Pfad und darum ausgenommen —
ein Lauf im neuen Ordner rechnet also nicht wegen des Umzugs neu, sondern weil dort noch keine Ausgabe liegt.

**Zuerst der rote Test** (Exit 1, 13 Tests): `test_layout.py` mit dem neuen Fall „Hauptprofil mit Slug",
`test_settings.py` mit dem Ordner je Paketprofil und `base_profile`, `test_cli.py` mit den Pfaden aus dem
`Layout` statt von Hand, `test_publish.py` mit der kopierten ersten Stadt und
`test_period_pipeline.py::test_the_profile_writes_into_its_own_subfolder` — der hielt den Umzug am
deutlichsten fest, weil die Basis der Mini-Periode mitziehen musste, sonst fände das Periodenprofil ihr
Wörterbuch nicht. Die Mini-Fixture und die Golden-Master-Läufe rechnen seitdem unter dem Profil der
Settings, nicht flach; der Golden Master selbst (`tests/fixtures/mini/expected/`) ist unberührt.

**Kosten:** ein Handgriff auf Konrads Rechner (die flachen Ordner `data/{external,raw,interim,processed,site}`
und `cache/{pdf,text}` löschen oder nach `duesseldorf/` verschieben, STATUS.md unter „Nächster Schritt") und
ein `bootstrap` plus `run` in jedem Klon, der schon Daten hat. Der PDF-Cache ist der einzige Grund, zu
verschieben statt neu zu rechnen: 19 108 Dateien lädt niemand ein zweites Mal.

## 53. Absicherung statt Ausbau: was gemessen wird, was ein Vertrag sagt, wo eine Lehre steht (Konrad, 2026-10-13)

Ein Tag ohne neue Funktion: das Vorhandene härten, messen und die Lehren an den Ort bringen, an dem sie
wirken. Die Übersicht mit allen Zahlen steht in [absicherung-2026-10.md](absicherung-2026-10.md), der
Mutationslauf in [mutation-2026-10-13.md](mutation-2026-10-13.md). Vier Entscheidungen hält dieser Punkt
fest.

**Mutationstests laufen je Modul als eigene Sitzung, mit genau den Testdateien des Moduls.** Nicht aus
Bequemlichkeit: die abdeckungsgeführte Testauswahl von pytest-gremlins liefert in diesem Repo **keine
Daten** („Coverage collection returned no data", mit `--gremlin-explain` bestätigt: „Covering set
(0 tests)"), und ohne sie läuft **jeder** Mutant gegen **alle** übergebenen Tests. Mit `tests/unit
tests/property tests/golden` als Auswahl war deshalb nach vier Minuten noch kein einziger Mutant durch
(Review 2026-10-13); je Modul sind es 539 s für die acht schnellen und rund 20 Minuten für alle
dreizehn. Für die Quote ist der leere Vorlauf übrigens gut: kein Mutant überlebt wegen eines fehlenden
Tests. Die Zuordnung Modul → Ziele und Testdateien steht als `MUTATION_SCOPE` im `noxfile.py`, damit der
nächste Lauf dieselbe hat; ausgenommen wird nur mit Grund. **Drei Arbeiter, nicht sechs**: mit sechs
wurde die Sitzung am 2026-10-12 unter Last abgeschossen. Verworfen: die Sitzung zum Gate machen
(Punkt 12 gilt weiter — 99 der 164 Überlebenden sind Vertragsgrenzen, und ein Gate zwänge dazu, sie
nachzuziehen); `--no-cov` in der Sitzung, weil ungemessen.

**Eine Annahme über die Eingabe gehört in die Vorbedingung, nicht in die Nachbedingung.** Alle vier
crosshair-Gegenbeispiele dieses Tages waren von dieser Sorte: `terms_payload` nahm an, dass die Begriffe
Treffer tragen und absteigend stehen; `fit`, dass die Bounding Box endlich ist; `body_figures`, dass die
Gremienklasse bekannt und die Dokumentzahl nicht negativ ist; `bars`, dass die Leinwand endliche positive
Maße hat. Jedes Mal brach eine Nachbedingung an einer gültigen Eingabe, und die Meldung zeigte auf die
Funktion statt auf ihren Aufrufer. Die Nachbedingung bleibt trotzdem stehen, wo sie beschreibt, was die
Ausgabe zusagt — sie wird nur nicht mehr als Eingabeprüfung missbraucht. Dieselbe Lehre wie bei
`nice_ticks` am 2026-10-12, dreimal am selben Tag: **eine Vorbedingung über Zahlen sagt, dass sie endlich
sind.** Verworfen: die Gegenbeispiele als „Artefakt des Werkzeugs" abtun (sie sind gültige Eingaben des
Typs, den die Signatur zusagt); ein Ziel aus `VERIFY_TARGETS` nehmen, weil es rot ist — ausgenommen wird
nur, wo das Gegenbeispiel über crosshair und nicht über das Programm redet (`bars`, `parse_reference`).

**Ein Schritt darf einen eigenen Zusatz im Stamp haben.** Der Settings-Fingerprint ist global und lässt
`[report]` aus, weil der Block nur die Anzeige betrifft; für die Parquet-Dateien ist das richtig, für
`index.html` war es falsch. Dazu stand keine Datei des Pakets im Stamp, und ein Vorlagenwechsel machte ihn
nicht ungültig. `Step.extra` schließt beides mit einem Hash, den nur `report` füllt. **Mit Vorgabe
gelesen** (`stamped.get("extra", "")`), damit ein Stamp von vor diesem Feld für jeden Schritt ohne Zusatz
gültig bleibt und genau ein Schritt einmal neu läuft. Verworfen: `[report]` in den globalen Fingerprint
nehmen (dann rechnete die ganze Kette nach einer geänderten Klassengrenze neu — 23 s für eine Farbe);
einen Fingerprint je Schritt einführen (bleibt zurückgestellt, `docs/plans/00-synergien.md`, § 8); die
Code-Version des Pakets bei jeder Vorlagenänderung hochzählen (eine Version ist eine Aussage über das
Programm, nicht über eine Zeile CSS).

**STATUS sagt, was ist; CLAUDE.md sagt, wie man arbeitet.** „Bekannt" war auf 34 Punkte gewachsen und
trug beides. Elf Arbeitsregeln sind nach `CLAUDE.md` „Arbeitsweise" umgezogen, je als ein Satz mit Datum;
die Fakten, Zahlen und Messungen bleiben in STATUS und in den datierten Dokumenten unter `docs/`. Der
Unterschied ist der Lesezeitpunkt: STATUS liest man, um den Stand zu erfahren, CLAUDE.md, bevor man etwas
anfasst. Verworfen: die Regeln in beiden Dateien führen (eine Dopplung veraltet an einer der beiden
Stellen); eine dritte Datei nur für Lehren (CLAUDE.md ist die Datei, die jede Sitzung ohnehin liest).

## 54. Das Rechenbudget der Overpass-Abfrage ist ein Setting und steht auf 25 s (2026-10-13)

`overpass_query` schrieb `[timeout:90]` fest in den Kopf der Abfrage. Gemessen am Mönchengladbach-Lauf
vom 2026-10-13: mit dieser Zahl weisen **alle vier** öffentlichen Instanzen (overpass-api.de, lz4, z,
maps.mail.ru) genau diese Stimmbezirksabfrage unter Last nach wenigen Sekunden mit `504 Gateway Timeout`
ab, während dieselbe Abfrage mit `[timeout:25]` in 2 s mit 124 Elementen antwortet; die Trivialabfrage
lief überall. Das `[timeout:N]` ist kein Netz-Timeout des Clients (der steht in `http.timeout_s` und
bleibt bei 180 s), sondern das Rechenbudget, das der Server der Abfrage zusagt — und er schätzt die
Kosten **vorab** und lehnt ab, was sein Slot-Budget überschreitet. Für eine Abfrage, die zwei Sekunden
braucht, ist ein großes Budget darum kein Sicherheitsnetz, sondern der Grund der Ablehnung.

Die Zahl steht jetzt als `sources.osm.query_timeout_s` in `defaults.toml` mit der Messung daneben,
Bereich 5 bis 180 (unter 5 s rechnet keine Instanz die Polygonabfrage durch, über 180 s weist jede sie
ab), und wird über `fetch_streets_per_precinct` und `fetch_street_names` bis `overpass_query`
durchgereicht. Dass sie im Profil liegt und nicht im Code, ist der Punkt: welches Budget eine Instanz
gewährt, ist eine Eigenschaft des Servers und des Tages, nicht der Stadt und nicht der Abfrage.

**Zwei Folgen, beide gewollt.** Der POST-Body ist der Cache-Schlüssel (Punkt 9): die Antworten, die vor
dem 2026-10-13 mit `[timeout:90]` erfolgreich waren, liegen unter ihrem alten Schlüssel in
`http.sqlite` und werden nicht mehr getroffen. Sie werden einmal neu geholt — mit 2 s je Abfrage ist das
billiger, als den Schlüssel künstlich stabil zu halten. Und der Settings-Fingerprint ist global, ein
neuer Schlüssel in `sources` macht also jeden Stamp ungültig; `georep status` sagt nach diesem Commit
für jeden gerechneten Schritt „offen: Settings geändert". Das ist das bekannte Verhalten eines neuen
Parameters, kein Fehler.

Verworfen: die Zahl im Code lassen und nur kleiner machen (dann steht die Messung an einer Stelle, an
der sie beim nächsten Lauf keiner sieht, und eine Instanz mit anderem Budget braucht einen Commit);
`[timeout:N]` ganz weglassen (Overpass setzt dann seinen eigenen Standard, und der ist 180 s — genau
das, was abgelehnt wird); den Wert aus der Polygongröße rechnen (die Abfragezeit hängt an der
Straßendichte, nicht an der Fläche, und 2 s gegen 25 s Budget ist kein Grenzfall, der eine Formel
rechtfertigt); die aufgezeichneten Abfragen in `tests/fixtures/http/*.query.txt` auf 25 umschreiben —
sie sind **Aufzeichnungen** dessen, was wirklich gesendet wurde (zwei tragen 60, vier tragen 90), und
der Schlüssel der Fake-Session ist die URL, nicht der Abfragetext. Eine Aufzeichnung wird nicht
rückdatiert, damit ein Test hübscher aussieht.

## 55. Ein 504 kostet einen Stimmbezirk, nicht den ganzen Schritt (2026-10-13)

Der Schritt `streets_osm` brach beim ersten `504 Gateway Timeout` ab. Gemessen am 2026-10-13: je
Versuch kamen rund 27 der 306 Abfragen durch, bevor der nächste 504 kam — der Schritt brauchte also
ein Dutzend Anläufe, und nur der HTTP-Cache (Punkt 9) machte das überhaupt erträglich, weil ein
erneuter Lauf dort weiterging, wo er aufhörte. Das ist der Cache als Krücke für fehlende
Wiederholung, nicht als Cache.

**Die Wiederholung liegt in `fetch_street_names`, nicht in der Session.** `make_session` wiederholt
429 und 5xx schon (504 steht in `RETRY_STATUSES`), aber nur für `GET` und `HEAD` — die
Overpass-Abfrage ist ein `POST` und fällt darum durch. Drei Gründe, das nicht durch ein `POST` in
`allowed_methods` zu lösen, sondern in der Quelle: die Regel gälte für **jeden** POST der Session
und damit für jede künftige nicht-idempotente Abfrage; urllib3 schläft echt, ein Test müsste also
warten statt ein `sleep` einzusetzen; und 500 soll gerade **nicht** wiederholt werden (er
wiederholt sich auch beim vierten Versuch), während die Session ihn in der Liste hat. Dass hier
nicht doppelt wiederholt wird, hängt an genau einer Zeile in `make_session`, und
`tests/unit/test_http.py` schreibt sie fest: `POST not in retry.allowed_methods`. Wer POST dort
aufnimmt, bekommt das Produkt beider Budgets.

Bis zu `sources.osm.retries` (Standard 3) Wiederholungen **je Stimmbezirk** bei 504 und 429, mit
wachsender Pause (`delay_s`, dann 2×, 4×) und injizierbarem `sleep`. Nach dem letzten Versuch gilt
der Status, wie er ist: `raise_for_status` wird über `network_errors` ein `NetworkError` — nicht
`FetchError`, denn die Antwort ist nicht kaputt, der Dienst war nach allen Wiederholungen nicht
erreichbar (Punkt 16, und so sagt es `docs/architecture.md` unter „Netz" schon). Der letzte Versuch
steht hinter der Schleife, nicht darin: so hat die Funktion keinen unerreichbaren Zweig und keine
Abbruchbedingung, die man zweimal lesen muss.

Verworfen: unbegrenzt wiederholen, bis es klappt (ein Dienst, der dauerhaft 504 sagt, hinge den
Lauf auf, und der Unterschied zwischen Überlast und Ausfall ist genau die Zahl der Versuche); den
Schritt bei Abbruch wieder aufnehmbar machen wie `papers` (Punkt 33) — der HTTP-Cache leistet das
bereits, und ein zweiter Fortschrittszeiger für dieselbe Sache wäre eine zweite Wahrheit;
Instanzen durchprobieren (am 2026-10-13 wiesen alle vier dieselbe Abfrage ab, es ist kein Problem
einer Instanz, sondern der Abfrage — die löst Punkt 54); den Fehler je Stimmbezirk überspringen und
den Schritt mit Lücke grün melden (eine fehlende Straßenliste verschiebt die Treffer eines Bezirks
still nach unten, und das ist das Ergebnis der Arbeit).

## 56. Die Datenpakete der Läufe liegen im Repo, nicht in einem Bucket (Konrad, 2026-10-13)

Drei Netzläufe vom 2026-10-13 liefern Daten, aus denen GitHub Pages Seiten bauen soll, die es
selbst nicht abrufen kann (Actions hat sechs Stunden Zeitlimit, der OParl-Server braucht Stunden):
Mönchengladbach, die Wahlperiode 2014 bis 2020 und die laufende Periode seit 2025. Konrad hat die
gebündelte Frage (fragen.md, oben 2; Fragen 1.2, 2.1, 3.3) am 2026-10-13 mit „die Datenpakete
kommen ins Repo, sie sind klein" beantwortet. Seitdem liegen sie als eingefrorene **Eingaben**
unter `reference/moenchengladbach/` (3 980 958 Bytes), `snapshots/2014-2020/` (37 875 851) und
`snapshots/2025/` (13 894 254), zusammen 55 751 063 Bytes (53,17 MiB) neben den 85 771 896 der
Referenz der Arbeit (81,80 MiB) und den 2 242 316 unter `context/` (2,14 MiB) -- **fünf Pakete,
143 765 275 Bytes, 137,11 MiB**. Gezählt sind überall die Datendateien **ohne** das README: es
beschreibt das Paket und ist nicht sein Inhalt (Review-Befund 14, 2026-10-14).

**Ein Paket trägt genau die Eingaben**, in der Form, in der das Programm sie schreibt:
`external/` (die Dateien der Portale, unverändert), `raw/papers.jsonl` (Metadaten),
`cache/text/texts.parquet` (der Textstore) und, wo das Profil sein Wörterbuch selbst holt,
`raw/streets_per_district.json` und `raw/wikipedia_dict.json`. Dieselbe Funktion liest alle drei
(`bootstrap.seed_stores_from_native`); `Layout.reference_view` setzt `cache_root` auf
`<reference_root>/cache`, daher liegt der Textstore unter `cache/text/`. Jedes Paket hat ein
README mit Herkunft, Lizenz, Abrufdatum, den Zahlen des Laufs und der SHA-256 jeder Datei — wie
`context/README.md` es seit Punkt 26 tut.

**Die PDFs liegen in keinem Paket**, nur die Texte daraus: 233 MB, 3,9 GB und 585 MB, und
urheberrechtlich ungeklärt (Frage 7.3). Ebenso draußen bleiben die Stamps (`*.stamp.json`: sie
beschreiben einen Lauf, nicht seine Eingaben), `manifest.jsonl`, `papers.progress.json` und
`http.sqlite`. Was ein Paket enthalten darf, steht nicht nur im README, sondern in
`tests/unit/test_data_packages.py`: Dateiliste, Größe und Prüfsumme je Datei, eine Obergrenze je
Paket und eine über alle, und eine Liste verbotener Endungen und Namen. Die pre-commit-Hooks
`check-added-large-files`, `trailing-whitespace` und `end-of-file-fixer` lassen `snapshots/` wie
`reference/` und `context/` aus; die Pakete sind absichtlich groß und byteweise die Quelle.

**Verworfen:** das R2-Bucket aus Option 07 mit einem Download-Schritt in Actions — Konrad hat am
2026-10-13 „kein Bucket, kaum Traffic und kleine Dateien" geantwortet, und ein Secret in Actions
plus ein Schritt `fetch snapshot` wären zwei neue Teile für 53 MiB; die abgeleiteten Tabellen
committen statt der Eingaben (dann baut `report` nicht, weil `dokumente.json` den Korpus braucht,
und jede Änderung an einer Zwischentabelle wäre ein Bruch); das Altformat der Arbeit
(`paper_with_text.json`, rund 80 MB unkomprimiert für dieselben Daten); git-lfs (ein zweites
Protokoll, und GitHub Pages zieht die Dateien dann über eine Bandbreitenquote); die Texte
komprimieren (Parquet ist es schon).

**Gemessen am 2026-10-14** (zweimal: vor und nach Punkt 57, dessen Gremienzahlen die Unterseite der
alten Periode um 314 Byte wachsen lassen): der Pages-Workflow von Hand auf einer frischen
Datenwurzel, genau die Schritte aus `.github/workflows/pages.yml`, baut aus den Paketen alle
Seiten. Zuletzt gemessen nach dem
Review (2026-10-14, veröffentlichter Ordner): Hauptseite **932 306** Bytes (Budget 1 000 000,
67 694 Byte Luft, 6,8 %) mit den Abschnitten „Zwei Wahlperioden" (45 417 Byte) und „Laufende
Wahlperiode" (374), `2014-2020/index.html` 818 602, `2025/index.html` 717 361,
`moenchengladbach/index.html` 641 660, `vergleich.html` 89 597; `georep publish --strict-budget`
meldet „2 Städte, 1 Vergleich, 187 Dateien, 34,6 MB" und endet mit Exit 0.

## 57. Die Nummernform einer Stadt vor 2019 wird eine Tabelle im Profil, kein zweites Muster (2026-10-14)

Der volle Abruf der Wahlperiode 2014 bis 2020 (Konrads Lauf vom 2026-10-13, Paket
`snapshots/2014-2020/`) brachte 18 070 von 22 215 Dokumenten mit „Gremium unbekannt" — gegen 0 von
19 108 in der Hauptperiode. Der Grund steht in den Drucksachennummern: **bis ins Jahr 2019 hieß eine
Drucksache `<Amtsnummer>/ <laufende Nummer>/<Jahr>`** (`61/ 12/2014`), nicht `BV7/108/2019`. 18 018
Nummern haben die alte Form, 4 197 die heutige; `bodies.reference_pattern` (Punkt 23) verlangt
Buchstaben vor dem ersten Schrägstrich und trifft die alte Form darum nicht.

**Ein Amt ist kein Gremium**, und 22 der 32 Köpfe sind Amtsnummern (7 313 Dokumente: `01`, `61`,
`66`, …). Jeder von ihnen zeigt zwar in über 98 % seiner Dokumente auf dieselbe
`consultation`-Organisation, aber das ist der zuständige Fachausschuss der Verwaltungsvorlage und
nicht das Gremium, das die Nummer vergibt; welchen Namen die Organisations-ID trägt, sagt nur
`raw/organizations.json`, und das ist ein Netzschritt. Gemessen am 2026-10-14 nennt der Text eines
`01`-Dokuments in 628 von 1 331 Fällen den Rat und in 540 gar kein Gremium — zu wenig für eine
Zuordnung. Diese 7 313 Dokumente bleiben „unbekannt", sichtbar mit Anteil auf der Seite (Punkt 39).

**Eindeutig sind genau die zehn Bezirksvertretungen**: `17X` ist die Bezirksvertretung des
Stadtbezirks X, `170` die zehnte (10 705 Dokumente). Nachgewiesen an den Dokumenttexten des Pakets:
von den 10 008 dieser Dokumente, deren Text überhaupt eine Bezirksvertretung nennt, nennt er in
9 999 (**99,91 %**) genau die des dritten Zeichens. Die Gegenprobe mit dem heutigen Kürzel `BVn`
derselben Periode trifft zu 99,89 % — **die Zuordnung ist so gut wie die, die der Parser schon
benutzt**, und das ist das Argument: sie ist keine schwächere Quelle, sie ist dieselbe Quelle in
einer älteren Schreibweise. Dazu passt, dass die zehn Köpfe auf zehn aufeinanderfolgende
`consultation`-Organisationen zeigen (`gr/32` bis `gr/41`), jeder auf genau eine.

**Umgesetzt als `[bodies.aliases]` im Stadtprofil**, einer Tabelle „Kopf der Nummer (alles vor dem
ersten `/`) → Kürzel" mit zehn Zeilen. `parse_reference` befragt sie **nur, wenn das Muster nicht
trifft**, und übersetzt den Kopf in ein Kürzel, das dann dieselben zwei Regeln durchläuft wie ein
Kürzel aus dem Muster (`_from_code`). Daraus folgt alles Wichtige von selbst: die Hauptperiode und
die laufende Periode merken nichts (dort trifft das Muster jede Nummer, 19 108 und 4 095),
Mönchengladbach ohne Muster merkt nichts, und ein Alias ins Nichts ist ein Settings-Fehler — der
Validator lässt nur Ziele zu, die in einer Tabelle des Profils stehen oder das Kürzel der
Bezirksvertretungen mit einer Nummer ab 1 sind.

**Verworfen:**

- **Ein zweites Muster** (`reference_pattern` als Liste, oder ein `legacy_pattern` daneben): ein
  Regex kann `171` nicht in `BV1` umschreiben, also bräuchte die alte Form ein eigenes
  `district_body` („17") und damit ein zweites Kürzel für dieselbe Bezirksvertretung — in einer
  Periode hieße sie `BV1`, in der anderen `171`, und jede Tabelle und jede Karte müsste beides
  kennen. Dazu kommt, dass `170` als Stadtbezirk 0 gelesen würde und die Regel „Nummer ab 1" die
  zehnte Bezirksvertretung verwerfen müsste; „0 bedeutet 10" wäre eine Düsseldorfer Eigenheit im
  Code. Zehn Zeilen Daten sagen dasselbe und sind nachlesbar.
- **Die Amtsnummern über ihre `consultation`-Organisation auf Ausschüsse abbilden**: das verlangte
  den Netzschritt `organizations` für eine abgeschlossene Periode, eine Abbildung von
  Organisations-IDs auf Kürzel und die Annahme, dass die erste Beratungsstation das Gremium *ist*.
  Offen, mit Zahlen begründet, und der ehrliche Anteil „unbekannt" bleibt sichtbar.
- **Das Muster der alten Form in das Periodenprofil** `duesseldorf-2014.toml` statt in das
  Stadtprofil: die Nummernform gehört der Stadt und nicht einer Periode (ein Dokument aus 2019 kann
  in beiden Formen auftreten, und beide Perioden lesen dieselbe Tabelle). Weil die Tabelle nur bei
  einem Fehlschlag des Musters greift, kostet sie die anderen Profile nichts.
- **Die Zuordnung aus den Dokumenttexten rechnen** statt aus der Nummer: das wäre ein neuer Schritt
  mit 22 116 Volltexten, 99,91 % Trefferquote statt einer Regel, und für 2 108 Dokumente ohne
  nutzbaren Text gar keine Antwort. Der Text war das Orakel, nicht die Quelle.

**Zahlen vorher/nachher** auf dem Paket (`tests/golden/test_bodies_reference.py`, `slow`):
Bezirksvertretung 2 539 → 13 244, Rat 338, Ausschuss 1 193, Beirat 75 unverändert, unbekannt
18 070 → **7 365** (81,3 % → 33,2 %). Die Hauptperiode bleibt bei 10 999 / 2 301 / 5 360 / 448 / 0.
*Nachtrag 2026-10-14:* seit `POA` in `[bodies.committees]` steht (Punkt 58) sind es 1 244 Ausschüsse
und 18 019 beziehungsweise **7 314** unbekannte; die 10 705 der Aliastabelle sind unberührt.

## 58. Die Beratungsfolge ist die zweite Quelle des Gremiums, und sie entscheidet nur, wenn sie eindeutig ist (2026-10-14)

Punkt 1 der Befunde vom 2026-10-14 (`docs/befunde-2026-10-14.md`, § 4 und § 6): neben der
Drucksachennummer (Punkt 23) und ihrer älteren Form (Punkt 57) bekommt das Gremium eine zweite
Quelle, nämlich die Gremien, die ein Dokument **beraten** haben — OParl liefert sie als
`consultation[].organization`, und der Server füllt sie, während er die Urheberfelder leer lässt
(0 von 19 109).

**Die Nummer entscheidet, die Folge ergänzt.** Wo die Nummer ein bekanntes Gremium nennt, bleibt
es dabei, auch wenn die Folge etwas anderes sagt; die Folge wird dann gezählt (bestätigt oder
Widerspruch) und erscheint als Zahl auf der Seite. Wo die Nummer keines nennt, entscheidet die
Folge — **und nur dann, wenn sie genau ein Gremium nennt**.

**Dass sie bei mehreren nicht entscheidet, ist gemessen und nicht vorsichtig.**
`georep.oparl.OparlPaper.consultation_organizations` liest die Liste sortiert und entdoppelt, die
Reihenfolge der Beratung ist also nicht in den Daten; damit fällt die naheliegende Regel „die erste
Station" weg. Fünf Regeln, die ohne Reihenfolge auskommen, am 2026-10-14 gegen die Nummer gemessen
— die Grundmenge sind die Dokumente, deren Folge **mehr als ein Kürzel auflöst** und deren Nummer
ein Gremium nennt, also genau die, bei denen eine Auswahlregel überhaupt etwas zu wählen hätte
(1 658 in der Hauptperiode, 371 in der Periode 2014 bis 2020):

| Regel | Hauptperiode | 2014 bis 2020 |
|---|---|---|
| die seltenste Organisation | **993 (59,9 %)** | **214 (57,7 %)** |
| alphabetisch das erste Kürzel | 844 (50,9 %) | 175 (47,2 %) |
| das seltenste Kürzel | 667 (40,2 %) | 141 (38,0 %) |
| Klassenvorrang (BV, dann Ausschuss, Beirat, Rat), darin die seltenste | 437 (26,4 %) | 99 (26,7 %) |
| die häufigste Organisation | 243 (14,7 %) | 75 (20,2 %) |

Bei **eindeutiger** Folge sind es dagegen 16 902 von 17 047 (99,1 %) beziehungsweise 14 419 von
14 449 (99,8 %). Das Kürzel der Nummer steht in 96,1 % der mehrdeutigen Fälle überhaupt in der
Menge — die Information ist also da, nur nicht die Stelle. Die beste Regel wäre damit in zwei von
fünf Fällen ein erfundenes Gremium in genau der Spalte, die die Seite zeigt; der ehrliche Anteil
„unbekannt" ist das bessere Ergebnis (Punkt 39).

**Die Abbildung Organisation → Kürzel ist gelernt, nicht geraten.** Die Folge nennt URLs
(`…/organizations/gr/6`), die Nummer nennt Kürzel. Wo eine Folge genau eine Organisation nennt,
sagt das Kürzel der Nummer, welche das ist; über alle Dokumente einer Periode entsteht daraus eine
Tabelle mit messbarer Reinheit. `georep learn-bodies` rechnet sie je Stadt, druckt den Katalog (mit
`shortName`, `classification` und Namen aus `raw/organizations.json`, wenn sie vorliegt), den
TOML-Block und die Gegenprobe mit der Tabelle, die das Profil **jetzt** trägt — und schreibt
nichts: die Tabelle kommt von Hand ins Profil, wie die Aliastabelle aus Punkt 57. Für Düsseldorf
sind es 35 Organisationen aus 17 047 Dokumenten mit einer Reinheit von 16 902/17 047 = **99,1 %**;
dieselbe Rechnung auf der Periode 2014 bis 2020 (30, 99,8 %) und auf der laufenden (32, 99,3 %)
widerspricht in **keiner** der 29 beziehungsweise 30 gemeinsamen Zeilen. Die Abbildung ist damit
eine Eigenschaft der Stadt und steht im Stadtprofil, nicht in einem Periodenprofil.

**Mönchengladbach lebt von dieser Quelle.** Dort trägt keine Drucksachennummer ein Kürzel
(`0682/XI`), und bis zum 2026-10-14 standen alle 2 895 Dokumente unter „Gremium unbekannt". Alle
2 895 tragen eine Beratungsfolge, sie nennt 27 Organisationen, und 1 620 (56,0 %) nennen genau
eine: „unbekannt" fällt auf 1 275 (44,0 %). Die Namen kommen aus einem Abruf von
`…/bodies/0011/organizations` (eine Seite, 122 Organisationen, 3,8 s); er liegt als
`raw/organizations.json` im Paket der Stadt, damit die Quelle der Namen im Repo steht. Welche
Nummer zu welcher Bezirksvertretung gehört, ist ebenfalls gemessen: die Dokumente mit genau einer
BV in der Folge treffen mehrheitlich Wahlbezirke ihres eigenen Stadtbezirks (Nord 59 % in 1, Ost
61 % in 2, Süd 52 % in 3, West 56 % in 4 — je die größte Zelle ihrer Zeile und Spalte), und
`[bodies.district_body_names]` gibt ihnen ihren Namen statt einer Nummer.

**Das Paket.** Der Korpus der Hauptperiode Düsseldorfs kommt aus dem Altformat der Arbeit und trägt
die Folge nicht; Konrads Vollabruf der Metadaten vom 2026-10-14 (122 Seiten, 36 Minuten) hat sie
geholt. `georep pack --consultations` schreibt daraus
`snapshots/duesseldorf-beratungsfolge/raw/beratungsfolge.parquet` (90 455 Bytes, drei Spalten,
README mit Prüfsummen), das Profil nennt es als `[bodies].consultations`, `bootstrap` kopiert es
nach `raw/`. **Parquet statt JSONL**, anders als `raw/papers.jsonl`: derselbe Inhalt kostet als
JSONL 4 467 207 Bytes, also fast fünfzigmal so viel. Jede andere Periode trägt die Folge in ihrem
eigenen `raw/papers.jsonl` und setzt den Schlüssel wieder leer; bringt ein eingefrorener Datensatz
eine eigene Datei mit, gilt seine (so hat die Mini-Fixture ihre 200 Zeilen).

**Jede Spalte sagt, woher sie kommt.** `papers_gremien.parquet` bekommt `quelle` (`nummer`,
`alias`, `beratungsfolge`, `unbekannt`), `folge_gremium` (was die Folge allein sagen würde) und
`folge_anzahl` (wie viele Gremien sie auflöst), Schema-Version 2. Zustimmung, Widerspruch und
Mehrdeutigkeit sind damit Abfragen auf der Tabelle und keine Rechnung an einer zweiten Stelle; die
Nachbedingungen halten die beiden Aussagen zusammen (`quelle = unbekannt` genau bei
`gremium_art = unbekannt`, `folge_gremium` genau bei `folge_anzahl = 1`). Der Abschnitt „Gremien"
nennt die Anteile beider Quellen in einem Satz aus diesen Spalten.

**Wirkung** (Läufe vom 2026-10-14, „unbekannt" vorher → nachher):

| Profil | Dokumente | unbekannt vorher | nachher | ergänzt | mehrdeutig | bestätigt | Widerspruch |
|---|---|---|---|---|---|---|---|
| `duesseldorf` | 19 108 | 0 (0,0 %) | 0 (0,0 %) | 0 | 0 | 16 902 | 145 |
| `duesseldorf-2014` | 22 215 | 7 314 (32,9 %) | **1 655 (7,4 %)** | 5 659 | 1 535 | 14 464 | 30 |
| `duesseldorf-2025` | 4 095 | 55 (1,3 %) | **0 (0,0 %)** | 0 | 0 | 3 665 | 26 |
| `moenchengladbach` | 2 895 | 2 895 (100,0 %) | **1 275 (44,0 %)** | 1 620 | 1 275 | 0 | 0 |

„Vorher" ist die Drucksachennummer allein, und zwar mit den beiden Kürzeln `POA` und `ACI`, die
der Review vom 2026-10-14 in `[bodies.committees]` nachgetragen hat (siehe unten): sie lösen 51
Nummern der alten Periode selbst auf, darum stehen dort 7 314 statt der 7 365 aus Punkt 57. In der
laufenden Periode sind es die 55 Nummern mit `ACI`, und weil sie jetzt aus der Nummer kommen, fällt
„unbekannt" dort auf 0, ohne dass die Beratungsfolge eine Zeile beiträgt.

Die Befunde hatten für die alte Periode 1,6 % geschätzt, weil sie die mehrdeutigen mitzählten; mit
der Regel „nur eindeutig" sind es 8,5 %. Das ist der Preis der Entscheidung und steht so auf der
Seite.

**Die Eindeutigkeit zählt die genannten Organisationen, nicht die aufgelösten Kürzel** (Review
2026-10-14). Eine Folge aus zwei Organisationen, von denen die Tabelle nur eine kennt, löst genau
ein Kürzel auf — und entschied damit zuerst, ganz leise, aus einer **Lücke in der Tabelle**:
`ACI/001/2026` und `ACI/022/2026` nennen `gr/400237` (damals ohne Zeile) und `gr/9` und wurden so
zu AGS, obwohl ihre Nummer `ACI` trägt; `01/ 281/2014` wurde aus `{gr/26, gr/6}` zum Rat und
`66/ 7/2016` aus `{gr/25, gr/26}` zum Ordnungs- und Verkehrsausschuss. Betroffen waren 31
Dokumente der Periode 2014 bis 2020, 2 der laufenden und 2 der Hauptperiode. Die Regel heißt darum
„genau eine **genannte** Organisation" (`consultation_body`), und `folge_anzahl` zählt ebenso: so
hängt die Entscheidung nicht daran, wie vollständig die Tabelle ist. Eine Organisation, die sie
nicht kennt, ergibt `folge_anzahl = 1` **ohne** Kürzel — die Nachbedingung ist darum eine
Implikation und keine Gleichheit.

**Verworfen:**

- **Eine Auswahlregel bei mehreren Gremien** (die fünf oben): höchstens 59,9 % Treffer, siehe die
  Tabelle. Eine Regel, die in zwei von fünf Fällen falsch liegt, ist keine Quelle, sondern ein
  Rauschen mit Vorzeichen.
- **Die Folge über die Nummer stellen**, wo beide etwas sagen: die 145 Widersprüche der
  Hauptperiode sind keine Fehler des Parsers, und sie zerfallen in zwei Klassen, die beide für die
  Nummer sprechen (gemessen 2026-10-14, eingefroren in
  `tests/golden/test_bodies_reference.py::test_the_two_kinds_of_disagreement`):

  | Klasse | Dokumente | Paare Nummer → Folge |
  |---|---|---|
  | das Kürzel der Nummer hat **keine eigene Organisation** und teilt sie mit einem anderen Gremium | **88** | BAU → SEBD 57, RPAU → RAT 30, WPA → RAT 1 |
  | beide haben eine, und die Folge nennt eine **andere Beratungsstation** | **57** | RAT → HFA 14, OVA → RAT 9, KUA → RAT 8, APS → RAT 3, SPOA → RAT 3, GLA 7 auf fünf Ziele, … |

  Die erste Klasse ist eine Grenze der Quelle: die Folge *kann* `BAU` nicht nennen, weil der
  Bauausschuss im Organisationsregister die Organisation von `SEBD` führt. Die zweite ist der
  eigentliche Grund für die Reihenfolge der Quellen: **die Folge ist ein Weg, die Nummer ist eine
  Akte.** Eine Ratsvorlage, die nur im Haupt- und Finanzausschuss beraten wurde (`RAT/388/2020`,
  14 solche Fälle), ist eine Vorlage *des Rates*; ein Nachtrag eines Ausschusses, der nur im Rat
  lief (`OVA/153/2023/1`), gehört in die Akte seines Ausschusses. Wer hier die Folge vorzieht,
  verschiebt Dokumente auf das Gremium, das sie zuletzt angefasst hat. GLA gehört seit
  `gr/400242` (eigene Organisation in der laufenden Periode) in die zweite Klasse und nicht mehr in
  die erste — bis zum Review vom 2026-10-14 stand es dort falsch.
- **Die Folge in den Korpus mischen** (Schritt `corpus` statt `bodies`): dann trüge
  `interim/papers.parquet` eine Angabe, die der Abruf dieser Periode nicht geliefert hat, und der
  Schritt, der die Frage beantwortet, wäre nicht der, der die Quelle liest. Der Schritt `bodies`
  liest beides und schreibt, was er daraus gemacht hat.
- **Die Tabelle im Code** (eine Abbildung `gr/6 → RAT` in `prep/bodies.py`): dieselbe Regel wie
  immer — kein Stadtwort im Code. Sie ist Daten im Profil, mit Zahlen je Zeile.
- ~~**`gr/26 → POA` und `gr/400237 → ACI` weglassen**~~, weil ihre Kürzel in keiner Kürzeltabelle
  standen: **zurückgenommen im Review vom 2026-10-14**. Beide sind echte Ausschüsse, und beide
  Namen sind belegt — `POA` ist der *Personal- und Organisationsausschuss* (der Name steht 19-mal in
  den Texten der 51 POA-Dokumente der Periode 2014 bis 2020, „Sitzungstermine des Personal- und
  Organisationsausschusses"), `ACI` der *Ausschuss für Chancengerechtigkeit und Integration* (im
  Titel von `ACI/003/2025`). Sie stehen seitdem in `[bodies.committees]`, und damit darf auch ihre
  Organisation in `[bodies.organizations]` stehen. Gewonnen: in der alten Periode 241 Dokumente
  (51 aus der Nummer, 190 aus der Folge, „unbekannt" 1 896 → **1 655**), in der laufenden alle 55
  (aus der Nummer, „unbekannt" 55 → **0**). Dass die Zeilen fehlten, war kein Argument für die
  Lücke, sondern ihr Grund.
- **Den Ausschuss-Klassifikator für Mönchengladbach einschalten**, nun da die Stadt Ausschüsse hat:
  nur 650 der 2 895 Dokumente tragen Text, und welche das sind, entscheidet das
  Ratsinformationssystem (2 213 Hauptdateien antworten mit `404`). Eine Güte an dieser Stichprobe
  wäre keine Güte. `classify.enabled = false` steht mit diesem Grund im Profil.
