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
Folge — **und nur dann, wenn sie genau eine Organisation nennt** (siehe unten).

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

**Was damit auf den Einwand aus Punkt 57 antwortet.** Dort war „die Amtsnummern über ihre
`consultation`-Organisation auf Ausschüsse abbilden" aus drei Gründen verworfen: der Netzschritt
`organizations` für eine abgeschlossene Periode, eine Abbildung von Organisations-IDs auf Kürzel und
die Annahme, dass die erste Beratungsstation das Gremium *ist*. Zwei davon sind weg: die Abbildung
ist **aus den Nummern gelernt** und braucht `organizations.json` nicht (für Düsseldorf ist der
Katalog nie abgerufen worden), und die Annahme wird **nicht** gemacht — entschieden wird nur, wo die
Folge genau eine Organisation nennt, also wo es keine „erste" Station zu wählen gibt. Der dritte
Grund bleibt richtig und ist der Grund für die Reihenfolge: eine Amtsnummer bedeutet weiter kein
Gremium, und die 7 313 Dokumente mit einer bekommen ihres nicht aus ihrer Nummer, sondern aus ihrer
Folge — und nur, wenn die eindeutig ist.

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
Nummer zu welcher Bezirksvertretung gehört, ist ebenfalls gemessen: die **167 Dokumente**, deren
Folge genau eine Bezirksvertretung nennt und die mindestens einen Treffer haben, verteilen 683
Dokument-Bezirk-Paare so, dass jede Bezirksvertretung in den Wahlbezirken ihres eigenen
Stadtbezirks die größte Zelle hat — in ihrer Zeile und in ihrer Spalte (Nord 144 von 244 = 59 %,
Ost 91 von 149 = 61 %, Süd 68 von 131 = 52 %, West 89 von 159 = 56 %; die ganze Matrix steht als
Kommentar über `[bodies.district_body_names]` im Profil, damit die Aussage nachzusehen ist).
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
  wäre keine Güte. `classify.enabled = false` steht mit diesem Grund im Profil — und aus demselben
  Grund steht dort seit dem Review vom 2026-10-14 auch `topics.seed = "none"`: mit der Saat bekamen
  acht Ausschüsse ein eigenes Thema, gesät aus 11 bis 21 Dokumenten mit Text, und ihre Namen
  standen danach als Zeilen in der Sensitivitätstabelle der Seite. Das sah nach einer Zuordnung aus,
  die diese 650 Texte nicht tragen; freie Themen sagen dasselbe, ohne einen Ausschuss zu behaupten.

## 59. Eine Dokumentart kann die Urheberklasse nennen, ohne den Urheber zu nennen (2026-10-14)

Punkt 3 der Befunde vom 2026-10-14 (`docs/befunde-2026-10-14.md`, § 2 und § 6): Mönchengladbachs
Stadtseite zeigte keine Urheber, weil `[originators]` im Profil leer war und der Schritt `parties`
darum fehlte. Die Daten geben die Zuordnung her, aber **an einer anderen Stelle als in Düsseldorf**:
dort nennt die Dokumentart die Fraktion („Anfrage SPD", „Antrag CDU/Grüne"), hier nennt sie nur die
**Klasse** — `3 - Fraktionsantrag` (581 Dokumente), `6.1 - Mitgliederantrag` (36) — und wer den
Antrag gestellt hat, steht im Titel oder im Briefkopf des Texts.

**Zwei neue Listen statt einer neuen Quelle.** `[originators]` kannte `admin_types` (Verwaltung) und
`citizen_types` (Eingabe); neu sind `fraction_types` und `person_types`. Steht die Art dort, ist die
Klasse entschieden, und gesucht wird nur noch die Partei: zuerst im Titel („Fraktionsantrag von DIE
LINKE und DIE FRAKTION vom 18.02."), dann im **ganzen** Textkopf statt in einem Fenster um einen
Marker. Das Fenster ist bei dieser Art falsch: bei einer Dokumentart, die den Urheber schon benennt,
ist der Kopf der Briefkopf des Antragstellers und keine Fundstelle in einem fremden Text — die
Briefköpfe stehen über 300 Zeichen weit („mönchengladbach ratsfraktion franz-meyers-haus
regentenstr. 11 … email: fraktion@cdu-mg.de"), ein Fenster von 80 Zeichen erreicht sie nicht. Nennt
keine der beiden Quellen eine Partei, bleibt es bei der Klasse, so wie bei einem interfraktionellen
Antrag.

**Alle 16 Dokumentarten dieser Periode sind eindeutig** (gemessen am 2026-10-14 an
`reference/moenchengladbach/raw/papers.jsonl`, Summe 2 895): 14 Arten mit 2 278 Dokumenten sind
Vorlagen der Verwaltung und ihrer Betriebe (`1.1 - Beratungsvorlage` 1 144, `2.1 - Berichtsvorlage`
946, die vier `8.x GMMG` 83, die zwei `7.x EWMG` 3, `4 - Änderungsvorlage` 12 und fünf weitere),
`3 - Fraktionsantrag` ist die Fraktionsklasse und `6.1 - Mitgliederantrag` die Person. „Urheber
unbekannt" ist damit **0,0 %**, und das ist keine Schönung: die Klasse steht in der Dokumentart, die
der Server mitliefert, nicht in einem Muster über einem Text, den es bei 2 245 Dokumenten nicht gibt.
Die offene Zahl steht eine Ebene tiefer — **239 der 581 Fraktionsanträge (41,1 %) nennen ihre
Partei** (242 vor Punkt 63 und 64). Die übrigen 342 sind eine Fraktion ohne nennbare Partei: 314
von ihnen tragen gar keinen Text, die 28 anderen einen Briefkopf, der nur
„fraktionsantragfraktion im rat der stadt mönchengladbach" sagt. Ohne Text sind insgesamt 390
Fraktionsanträge, und 76 davon nennen ihre Partei trotzdem — im Titel.

**Die acht Fraktionen stehen im Profil, mit ihren Namen aus `raw/organizations.json`** (Abruf vom
2026-10-14, `classification = "Fraktion"`): CDU, SPD, BÜNDNIS 90/DIE GRÜNEN, FDP / VOLT, AfD MG,
DIE LINKE / DIE PARTEI, Die FRAKTION, Fraktionslos. Sechs tragen eine Stimmenspalte
(`columns.results.parties`, D1 bis D6) und werden `[[originators.parties]]`; VOLT und DIE PARTEI
sitzen in einer Fraktion mit FDP beziehungsweise DIE LINKE und werden `[[originators.groups]]`, wie
Die FRAKTION. **Fraktionslos bekommt keine Zeile**: das ist der Sammelplatz für Mandate ohne
Fraktion und kein Urheber, der sich in einem Briefkopf nennt — das Wort steht in keinem Titel und in
keinem Textkopf dieser Periode. Eine Zeile mit einem Muster, das nichts trifft, wäre eine Behauptung
ohne Beleg.

**Die Grenze dieser Quelle steht auf der Seite.** „Methode und Grenzen" sagt, dass ein eigener
Briefkopf vor der Dokumentart gilt (Punkt 62), dass bei einer Dokumentart, die nur die Klasse nennt
(hier 617 Dokumente), die Partei aus Titel oder Briefkopf kommt, und dass vom Titel nur zählt, was
hinter seinem letzten Bezug steht (Punkt 63) — weil davor der Antrag genannt wird, auf den sich das
Dokument bezieht. Der Satz entfällt in einer Stadt ohne solche Dokumentarten
(``model.originator_types`` ist dort 0).

**Der Satz des Abschnitts zählt jetzt seine Quellen.** „Der Urheber steht stattdessen in der
Dokumentart, im Titel oder im Textkopf („Anfrage SPD", „Antrag der CDU-Fraktion", „(anfrage
cdu-fraktion vom 28. Juli 2023)")" war ein Satz mit drei Düsseldorfer Belegen in einer Vorlage, die
jede Stadt rendert; auf der Mönchengladbacher Seite war er falsch, denn keine Dokumentart dieser
Stadt nennt eine Partei. Der Satz nennt stattdessen die gemessenen Zähler je Quelle
(`OriginatorFigures.sources`, eine Quelle ohne Beitrag fehlt): „2 656 aus der Dokumentart, 142 aus
dem Titel und 97 aus dem Textkopf".

**Verworfen:**

- **Mönchengladbachs Dokumentarten in Düsseldorfs `motion_prefixes` und Muster einpassen**:
  `3 - Fraktionsantrag` enthält kein Antragspräfix mit einer Partei dahinter, und ein Muster, das
  aus „Fraktionsantrag" eine Fraktion macht, wäre genau das, was die beiden neuen Listen jetzt als
  Daten sagen — nur versteckt in einem Regex.
- **`4 - Änderungsvorlage` offen lassen**: alle zwölf sind Nachträge („3373/X-1") zu Vorlagen der
  Verwaltung, und die beiden mit Text nennen ihren Fachbereich („fachbereich fb 51", „fb 14
  rechnungsprüfung"). Der Änderungsantrag einer Fraktion heißt in dieser Stadt
  `3 - Fraktionsantrag` — die Art ist also eindeutig, nicht nur plausibel.
- **Den Briefkopf auch in Düsseldorf ganz lesen** statt in einem Fenster: dort nennt die
  Dokumentart die Klasse **nicht**, der Text muss also erst sagen, dass es überhaupt ein
  Fraktionsantrag ist. Ohne das Fenster zählte „die cdu-fraktion beantragt" in einer
  Verwaltungsvorlage mit (Option 04, § 2).
- **`[originators]` in `defaults.toml` ablegen, damit jede Stadt etwas erbt**: die Dokumentarten
  sind das Stadtspezifischste, was es gibt (16 hier, 39 dort, und keine einzige gemeinsam). Eine
  geerbte Liste wäre in jeder zweiten Stadt falsch, und `deep_merge` ersetzt Listen ohnehin.

## 60. Die Vorlagenform einer Stadt vor 2020 wird ein Textmarker im Stadtprofil, kein Periodenprofil (2026-10-14)

Punkt 4 der Befunde vom 2026-10-14 (`docs/befunde-2026-10-14.md`, § 5 und § 6): in der Wahlperiode
2014 bis 2020 blieben **12 418 von 22 215 Urhebern unbekannt (55,9 %)**, gegen 1,7 % in der
Hauptperiode. Der Grund stand in zwei Zahlen: die beiden häufigsten Dokumentarten jener Periode,
`Vorlage aus der Politik` (9 601) und `Verwaltungsvorlage` (8 337), zusammen 80,7 %, standen in
keiner Liste von `[originators]`, und beide nennen keine Fraktion.

**Die Taxonomie hatte zwei Hälften, und eine davon ist die Verwaltung.** `Verwaltungsvorlage` ist
der Gegenbegriff zu `Vorlage aus der Politik`; er steht in dieser Periode 8 337-mal und in der
Hauptperiode wie in der laufenden **kein einziges Mal**. Er gehört darum in `admin_types`. Von den
197 Dokumenten, die bis dahin über Titel oder Textkopf zu einer Fraktion wurden, sind damit **161
richtig** eingeordnet — Vorlagen der Verwaltung, die einen Fraktionsantrag **zitieren**, genau der
Fehler, gegen den das Fenster um einen Marker gebaut ist (Option 04, § 2). Die **anderen 36 waren
es nicht**: sie tragen ihren eigenen Fraktionsbriefkopf, und mit ihnen elf weitere, die vorher
unbekannt waren. Zusammen 47 Dokumente, und sie sind der Grund für Punkt 62 (*Review 2026-10-14*;
der erste Satz dieses Punktes hieß „damit sind auch die 197 richtig eingeordnet" und war falsch).
Dasselbe gilt für `Bezirksvertretung Eingabe nach 24Go` (2 Dokumente), die dritte Schreibweise
derselben Eingabe.

**Die andere Hälfte steht im Briefkopf, und der ist ein Formular.** Jede `Vorlage aus der Politik`
trägt denselben Kopf:

```
vorlage 173/ 85/2014   seite 1 von 2 rsd vorlage x öffentlich  nicht öffentlich
  fraktion die linke  der bezirksvertretung 3   an den  bezirksvorsteher …
```

Der Urheber steht zwischen der Formularzeile und dem Gremium, und zwar in 8 090 von 9 601 Fällen in
einem Block, der sich zählen lässt: `cdu-fraktion` 1 276, `spd-fraktion` 982, `fraktion bündnis
90/die grünen` 439, `interfraktioneller antrag` 263, `fdp-fraktion` 245 und so weiter. Der neue
Textmarker ist genau diese Formularzeile plus das Wort „fraktion" innerhalb von 80 Zeichen; die
Parteien kommen wie überall aus dem Fenster um den Treffer.

**Wirkung** (gemessen 2026-10-14 am Paket `snapshots/2014-2020/`, eingefroren in
`tests/golden/test_parties_numbers.py`):

| Klasse | vorher | nachher |
|---|---|---|
| Verwaltung | 2 285 | **10 622** |
| Fraktion | 7 008 | **8 768** |
| Person | 486 | 449 |
| Eingabe | 18 | 20 |
| **unbekannt** | **12 418 (55,9 %)** | **2 356 (10,6 %)** |

Was offen bleibt, bleibt sichtbar offen: 2 122 `Vorlage aus der Politik`, deren Kopf das Wort
„fraktion" nicht trägt (Jugendratsmitglieder, Einzelmandate, Listen des Integrationsrats), 135
`Antrag`, 96 `Anfrage` und 3 `zAnfrage Piraten`.

**Das Muster steht im Stadtprofil, nicht im Periodenprofil**, aus demselben Grund wie die
Nummerntabelle aus Punkt 57: die Vorlagenform gehört der Stadt, in einer älteren Schreibung. Dass
das die anderen Perioden nichts kostet, ist nicht argumentiert, sondern **gemessen und als Test
eingefroren**: die Zuordnung aller 19 108 Dokumente der Hauptperiode und aller 4 095 der laufenden
ist mit und ohne die drei neuen Einträge **dieselbe Tabelle**, byteidentisch. Der Grund ist
mechanisch — der Korpus schneidet den Text an `search.text_split_marker` („betrifft") ab, und die
Formularzeile liegt davor; in beiden Perioden kommt der Anker in 0 Dokumenten vor.

**Die Schreibweisen der Parteien reichten schon.** Konrads Vermutung, die alte Periode brauche
eigene Namen, trifft nicht: von 5 454 Briefköpfen mit Fraktion nennen 5 168 eine Partei, die die
vorhandenen Muster kennen, und die 286 übrigen sind „interfraktioneller antrag" — also richtig eine
Fraktion ohne Partei. `bündnis90/die grünen` ohne Leerzeichen, `bü90/die grünen`, `b90/die grünen`,
`die linke.` mit Punkt und `AFD` in Großbuchstaben treffen alle auf vorhandene Muster.

**Verworfen:**

- **Piraten, REP, FWG und die Zentrumspartei als eigene Gruppen aufnehmen**: sie kommen in dieser
  Periode vor (41, 80, 83 und 482 Dokumente mit dem Wort im Volltext), aber die Zeilen kosten mehr
  als sie bringen. `topics.stop_sources = ["fraktionen", …]` nimmt jedes Wort aus jedem Parteimuster
  in die Stoppwortliste des **Themenmodells** — „piraten", „rep", „fwg" und bei der AfD-Variante
  „alternative für deutschland" auch „alternative" und „deutschland", und die beiden stehen in 518
  und 587 Dokumenten der **Hauptperiode**. Ein Wort mehr in der Stoppwortliste ist ein anderes
  Vokabular, ein anderes NMF und andere `thema_NN`-Zeilen auf der Hauptseite. Gewonnen wären 3
  Dokumente (die `zAnfrage Piraten`, die heute unbekannt sind); die 21 anderen Piraten- und 12
  REP-Dokumente sind schon richtig als Person eingeordnet, weil ihr Titel einen Mandatsträger nennt.
- **Personenmarker im Textkopf**: 1 503 Köpfe tragen einen Personenmarker ohne „fraktion" in der
  Nähe, aber in 776 Fällen ist der Treffer die **Anrede** („an herrn bezirksvorsteher", „herrn
  wolfgang scheffler, vorsitzender des schulausschusses") und nicht der Urheber — diese Dokumente
  bekommen ihre Fraktion heute richtig aus dem Titel. Ein Marker, der in der Hälfte der Fälle den
  Empfänger für den Absender nimmt, ist keine Quelle. Darum nennt die alte Periode weiterhin nur
  449 Personen, und die Mandatsträger ohne das Wort „Fraktion" im Kopf bleiben unbekannt.
- **`Vorlage aus der Politik` als `fraction_types`** (Punkt 59): die Art ist **nicht** eindeutig.
  Sie trägt Fraktionsanträge, Anträge einzelner Bezirksvertreter, Anfragen von
  Jugendratsmitgliedern („leon brink  mitglied des jugendrates"), Listen des Integrationsrats
  („giol grüne internationale offene liste") und sogar Verwaltungsakte („Bestellung der
  Schriftführerin des Rates"). Eine Klasse aus der Art wäre hier eine Behauptung; der Briefkopf
  sagt es genauer.
- **Die Muster in `duesseldorf-2014.toml`**: `deep_merge` ersetzt Listen, das Periodenprofil müsste
  also die beiden vorhandenen Textmarker und alle acht Verwaltungsarten mitschreiben, um einen Wert
  zu ergänzen. Zwei Wahrheiten über dieselbe Stadt in zwei Dateien, und jede Änderung an der einen
  müsste in der anderen nachgezogen werden.

## 61. Die Spalte „ohne Ausreißer" bleibt, heißt explorativ und wird an der zweiten Periode gemessen (2026-10-14)

Punkt 2 der Befunde vom 2026-10-14 (`docs/befunde-2026-10-14.md`, § 1 und § 6): die eine Spalte von
Tabelle 5, in der die Arbeit ein signifikantes p berichtet (ohne die Wahlbezirke 1 und 10,
p = 0,037), ist in der Wahlperiode 2014 bis 2020 mit **p = 0,082 nicht signifikant** — dieselbe
Methode, dieselbe Stadt, ein anderer Zeitraum. Konrads Frage war: Satz auf der Seite oder Spalte
weg.

**Die Spalte bleibt, und sie sagt selbst, was sie ist.** Tabelle 5 ist die Tabelle der Arbeit, und
die Seite zeigt beide Spalten, seit sie existiert; eine Spalte stillschweigend zu entfernen hieße,
die Arbeit anders darzustellen, als sie ist. Stattdessen trägt der Spaltenkopf jetzt das Wort
**„explorativ"**, und unter der Tabelle steht ein Absatz mit zwei Sätzen: der erste sagt, dass die
Spalte **nach** dem Ansehen der Daten entstanden ist (ausgeschlossen sind die beiden Bezirke mit
den höchsten Trefferquoten — eine Entscheidung über diesen Datensatz, keine Vorhersage, die er
prüfen könnte, `docs/methodik-review-2026-10.md`, § 2.7); der zweite nennt beide p-Werte und sagt,
was daraus folgt.

**Kein Satz trägt eine Zahl hart.** Beide p-Werte, beide r und beide Steigungen kommen aus dem
Modell, die eigenen aus `model.regression`, die anderen aus `model.comparison.previous_pair` —
derselben Rechnung über die `results` der anderen Periode, aus der auch ihr `summary.json` entsteht.
**Das Urteil kommt aus den Zahlen und nicht aus dem Text**, und zwar in drei unabhängigen Stücken:
wie weit die beiden *r* auseinanderliegen („zwei nah beieinander liegende" gegen „zwei deutlich
verschiedene Schätzungen", Grenze 0,1), auf welchen Seiten der 5-%-Grenze die beiden p liegen (vier
Fälle, und „knapp" statt „deutlich" darüber nur unter 0,15), und ob die Steigung um mehr als die
Hälfte schwankt. Ein `parametrize`-Test rendert die Fälle. Ohne das Vergleichsprofil bleibt es beim
ersten Satz, und ohne zweite Spalte (`analysis.exclude_districts` leer, so bei Mönchengladbach)
fehlt der Absatz ganz.

*Review 2026-10-14:* der Satz hieß zuerst „dieselbe Methode, dieselbe Stadt, ein anderer Zeitraum,
und von der Signifikanz bleibt nichts". Das tragen die Daten nicht: die beiden *r* liegen 0,053
auseinander (0,335 gegen 0,282), und ein Vergleich der beiden Korrelationen nach Fisher-z gibt
p = 0,80 — sie sind nicht unterscheidbar. Was wirklich schwankt, ist die **Steigung**: 216 gegen 82,
Faktor 2,6. Die Spalte ist also nicht „nichts", sie ist **ein Zusammenhang ähnlicher Stärke, dessen
p einmal knapp unter und einmal knapp über der Grenze liegt** — und genau das ist der Grund, warum
sie explorativ heißt. Der Satz sagt das jetzt so.

**Dazu ein Satz je Periode im Abschnitt „Zwei Wahlperioden"** mit r und p **beider** Spalten und
demselben Urteil aus den Zahlen (ein Jinja-Makro `verdict`, fünf Zweige, weil dort auch „über alle
Wahlbezirke signifikant, ohne die beiden nicht" vorkommen kann). Wer die Tabellen nicht
nebeneinanderlegen will, liest dort beide Perioden in zwei Sätzen.

**Was es kostet** (gemessen 2026-10-14 an der Hauptseite): 878 Byte der Absatz unter Tabelle 5,
542 Byte der Satz je Periode, 1 103 Byte der Absatz in „Methode und Grenzen", 40 Byte der
Kopfhinweis.

**Verworfen:**

- **Die Spalte entfernen**: Tabelle 5 ist die Tabelle der Arbeit. Sie zu beschneiden macht die
  Seite nicht ehrlicher, sondern unvollständiger — und die Abweichung der Arbeit in genau dieser
  Spalte (`docs/baseline-2026-10-10.md`) wäre dann nicht mehr nachzuvollziehen. Mit Lukas zu klären
  bleibt sie trotzdem.
- **Die p-Werte aus `summary.json` der anderen Periode nachladen**: die Zahl steht schon im Modell
  (`comparison.previous_pair`), aus derselben Quelle gerechnet. Ein zweiter Weg zu derselben Zahl
  ist eine zweite Wahrheit, und er hinge daran, dass der Lauf der anderen Periode seine Seite schon
  geschrieben hat.
- **Nur die Fußnote und keinen Absatz in „Methode und Grenzen"** (Review-Befund 12): die Fußnote
  verweist mit „(siehe Methode und Grenzen)" dorthin, und dort stand nichts dazu. Jetzt steht dort
  ein Absatz, der dasselbe länger sagt: warum die Nummern in den Einstellungen stehen, warum ein
  p-Wert aus einem nachträglich gewählten Modell nicht misst, wie überraschend das Muster ist, dass
  eine hohe Trefferquote vor allem ein großes Wörterbuch anzeigt (*r* = 0,760 zwischen Treffern und
  Begriffen gegen 0,173 zu den Wahlberechtigten, gerechnet aus `analysis.scaling.dictionary_bias`) — also genau die Eigenschaft, nach der ausgeschlossen wird —, und dass
  41 Wahlbezirke keine Stichprobe sind, sondern die ganze Grundgesamtheit.
- **Den Hinweis auch über die Spalte „ohne 1 und 10" der zweiten Tabelle schreiben** (dieselbe
  Rechnung je Begriff im Wörterbuch, Punkt 46): dort steht der Satz schon, und zwar stärker — mit
  dieser Kennzahl bleibt von der Signifikanz ohnehin nichts (p = 0,80). Zwei Hinweise übereinander
  lesen sich wie zwei verschiedene Einschränkungen.
- **Eine automatische Ausreißerregel** (robuster z, Cook-Distanz) statt der zwei Nummern: sie füllte
  die Spalte von Lauf zu Lauf anders, und der Methodik-Review hat sie mit diesem Grund schon
  zurückgestellt (§ 2.7). Nach Regel 1 ist Bezirk 10 ohnehin kein Ausreißer mehr (robuster
  z = 2,69), Bezirk 1 dagegen weiter einer (z = 9,71) — die Liste beschreibt also heute zwei
  verschiedene Dinge, und auch das ist ein Grund für das Wort „explorativ".

## 62. Der eigene Briefkopf steht vor der Dokumentart (Review 2026-10-14)

Befund 1 des Reviews zu den Punkten 59 bis 61. Punkt 60 hat `Verwaltungsvorlage` in `admin_types`
geschrieben, und weil die Dokumentart vor dem Textkopf gefragt wird, standen danach **47 echte
Fraktionsanträge als Verwaltung** da: sie liegen im Ratsinformationssystem unter dieser Art und
tragen trotzdem den Fraktionsbriefkopf der alten Vorlagenform (`vo/58872`, Titel „Antrag der
Ratsfraktionen von SPD, BÜ90/GRÜ und FDP …", Kopf „rsd vorlage x öffentlich nicht öffentlich  spd
ratsfraktion ratsfraktion bündnis 90/die grünen fdp ratsfraktion"). 36 von ihnen galten vor
Punkt 60 als Fraktion, 11 waren unbekannt.

**Die Dokumentart sagt, wie das System die Vorlage geführt hat; der Briefkopf sagt, wer sie
geschrieben hat.** Wo beides sich widerspricht, gewinnt der Briefkopf — aber nur, wenn das Muster
dafür ein *Briefkopf* ist und kein Zitat treffen kann. `[originators]` bekommt dafür eine eigene
Liste `letterhead_markers`, die **vor** allen Dokumentart-Listen gefragt wird; die vorhandenen
`text_markers` bleiben, wo sie waren (nach dem Titel), denn „antrag der cdu-fraktion" steht genauso
in einer Vorlage, die den Antrag zitiert.

**Die Bedingung ist gemessen, nicht geschätzt** (2026-10-14, eingefroren in
`tests/golden/test_parties_numbers.py::test_an_own_letterhead_beats_the_document_type_but_a_citation_does_not`):
die Formularzeile trifft **keine** der 161 Verwaltungsvorlagen, die einen Fraktionsantrag nur
zitieren, **keine** der beiden Eingaben nach § 24 GO NRW und **keines** der 28 Dokumente, deren
Titel einen Mandatsträger nennt. Der Grund ist mechanisch: der Korpus schneidet den Text am
`search.text_split_marker` („betrifft") ab, und wo ein Dokument zitiert, beginnt sein Text hinter
diesem Marker — die Formularzeile des *fremden* Antrags liegt davor und ist weg.

**Wirkung** auf die Wahlperiode 2014 bis 2020: Verwaltung 10 622 → **10 575**, Fraktion 8 768 →
**8 815**; „unbekannt" bleibt bei 2 356 (10,6 %), Person bei 449, Eingabe bei 20. 39 der 47 nennen
auch ihre Partei, die acht übrigen sagen „interfraktioneller antrag". Dokumente je Partei: CDU
3 598 → 3 647, SPD 2 650 → 2 708, GRÜNE 2 363 → 2 417, FDP 1 285 → 1 335, Die Linke 494 → 505.
Die Hauptperiode, die laufende Periode und Mönchengladbach bleiben **byteidentisch** (dieselbe
Zusage und derselbe Test wie in Punkt 60: die Formularzeile kommt dort in 0 Dokumenten vor).

**Verworfen:**

- **Die Formularzeile in `text_markers` lassen und `Verwaltungsvorlage` wieder aus `admin_types`
  nehmen**: dann stünden 8 112 Verwaltungsvorlagen wieder als „unbekannt" da, um 47 Dokumente
  richtig zu bekommen.
- **Alle `text_markers` vor die Dokumentart stellen**: „antrag der cdu-fraktion" steht in 161
  Vorlagen, die den Antrag nur zitieren — sie würden alle zu Fraktionsanträgen. Die Reihenfolge
  ist nicht pauschal falsch, sie ist nur für einen Briefkopf falsch.
- **Die 47 im Profil als Ausnahmeliste führen**: eine Liste von 47 Dokument-IDs ist keine Regel,
  und beim nächsten Abruf wäre sie falsch.

## 63. Im Titel zählt nur, was hinter dem letzten Bezugsmarker steht (Review 2026-10-14)

Befund 2 des Reviews. Punkt 59 lässt bei einer Dokumentart aus `fraction_types` den **ganzen** Titel
nach Parteien durchsuchen, weil dort kein Fraktionsmarker als Tor davorsteht. Mönchengladbachs Titel
stapeln aber Bezüge: „Evaluation und Ausbau Rats-TV Fraktionsantrag DIE LINKE; **hier:** Antrag der
Ratsfraktionen von SPD, Bündnis 90/Die Grünen und FDP" nennt zwei Urheber — den **zitierten** vor
dem Marker und den **eigenen** dahinter. Drei Dokumente bekamen so die falsche Partei: `0590/X` und
`0591/X` zusätzlich DIE LINKE, `3732/X` zusätzlich SPD, Grüne und FDP statt nur CDU.

**`title_split_markers` im Profil, der letzte Marker gewinnt.** Mönchengladbach nennt `hier ?:`;
142 der 581 Fraktionsanträge tragen den Marker, und `0591/X` trägt ihn zweimal („…; hier: Antrag der
Ratsfraktion DIE LINKE vom 26.02.2021; hier: Antrag der Ratsfraktionen von SPD, … vom 16.03.2021").
Darum der letzte und nicht der erste: jeder weitere Bezug schiebt den eigenen Gegenstand nach
hinten. Der Briefkopf bestätigt die Zuordnung in allen drei Fällen, in denen es einen gibt.

**Gefragt wird nur bei `fraction_types`**, nicht im allgemeinen Titelpfad. Dort steht das Tor der
`fraction_markers` davor und danach das Fenster um den Textmarker; die Quelle ist also nie der ganze
Titel allein. Düsseldorf lässt die Liste darum leer, und seine Zahlen sind unberührt.

**Wirkung** auf Mönchengladbach (gemessen 2026-10-14): die Klassen bleiben (Verwaltung 2 278,
Fraktion 581, Person 36, unbekannt 0), die Quellen verschieben sich auf 2 656 Dokumentart, 142
Titel, 97 Textkopf, und von den 581 Fraktionsanträgen nennen **239 statt 242** eine Partei.
Dokumente je Partei: CDU 107 (vorher 108), FDP 78 (79), Die Linke 34 (37), Die FRAKTION 5 (7) —
die letzte Zahl auch wegen Punkt 64.

**Verworfen:**

- **Den Marker im Code** (`"hier:"` in `parties.py`): kein Stadtwort im Code, und ob eine Stadt
  „hier:", „betreffend:" oder gar nichts schreibt, ist ihre Vorlagenform.
- **Den ersten statt den letzten Marker nehmen**: `0591/X` zeigt, dass Bezüge gestapelt werden.
- **Den Titel bei `fraction_types` ganz weglassen und nur den Briefkopf fragen**: 390 der 581
  Fraktionsanträge tragen gar keinen Text, und 76 von ihnen nennen ihre Partei im Titel.

## 64. Ein Parteimuster braucht Wortgrenzen, wo sein Name ein Wortanfang ist (Review 2026-10-14)

Befund 3 des Reviews. Das Muster `die fraktion` der Mönchengladbacher Gruppe *Die FRAKTION* traf
auch „vertreten durch **die Fraktion**svorsitzende" und machte `1785/X` — einen Antrag der
Deutschen Zentrumspartei — zu einem Antrag dieser Gruppe. Mit `\bdie fraktion\b` sind es sieben
Fundstellen in dieser Periode, und alle sieben nennen wirklich die Gruppe. `1785/X` bleibt
Fraktion **ohne Partei**: die Zentrumspartei hat in dieser Stadt keine Stimmenspalte und keine
Fraktion im Organisationskatalog, also auch keine Zeile in `[originators]` — und eine Zeile ohne
Beleg wäre schlechter als die offene Klasse (Punkt 59).

Der Kommentar im Profil sagte „alle acht Fundstellen nennen wirklich die Gruppe". Das waren sieben
plus die eine falsche; die Messung war nicht falsch gelesen, sondern zu früh gemacht — gezählt
wurde, was das Muster trifft, nicht, was es treffen soll.
## 65. Die Flächen einer Stadt dürfen eine ArcGIS-Operation sein, und es ist `identify` (2026-10-14)

Mönchengladbachs Stimmbezirksflächen rechneten bis hierher mit dem Datensatz „Wahlen" vom
08.06.2022 (Punkt 35, Landtagswahl 2022): 175 der 179 Urnen-Stimmbezirke der Kommunalwahl 2025
kamen darin vor, vier fehlten (`11006`, `21406`, `32906`, `40106`), fünf gab es nur dort. Die
Flächen zum Stand der Wahl **gibt es**, nur nicht als Datei: sie sind Layer 16
(„Kommunalwahl 2025 Stimmbezirke") des Dienstes
`geoportal.moenchengladbach.de/server/rest/services/K12_Politik_und_Wahlen/K12_Politik_und_Wahlen/MapServer`,
179 Flächen, Esri-JSON mit `rings`, `wkid` 25832, Attribut `Nummer` fünfstellig wie bisher,
Datenlizenz Deutschland – Zero – Version 2.0, Aktualität „Kommunalwahl 2025".

**Darum eine dritte Quellform `esri-identify` neben `geojson` und `shapefile-zip`** (Punkt 35: eine
neue Quellform ist eine weitere Funktion). Das Profil nennt die ganze Abruf-URL mit Query-String;
`fetch_districts_file` holt sie byteweise wie jede andere, denn ein GET bleibt ein GET, TOML liest
das `&` wörtlich, und `http.cache_pattern` deckt die Anfrage mit seinem `*` ab. Neu geprüft wird
nur, was diese Form eigen hat: ein ArcGIS-Dienst meldet seine Fehler **mit HTTP 200** und einem
`error`-Objekt, und ohne diese Prüfung lägen sie als Datei in `external/`.

**Warum `identify` und nicht `query`.** `query` ist die Operation, die man nähme, und sie hat an
diesem Layer zwei Haken, beide am 2026-10-14 nachgesehen:

- **Sie liefert für Layer 16 keine Geometrie.** Mit `returnGeometry=true` kommen die Attribute und
  kein `geometry`-Mitglied; der eigene Dienst `Stimmbezirke_Kommunalwahl_2025`, der sie hätte, ist
  **gestoppt**.
- **Ihr `maxRecordCount` ist 2 000 und sie blättert.** Das reicht hier für 179 Flächen, aber eine
  Form, die ab einer Grenze blättert, verlangt eine Schleife mit `resultOffset` und einen Vertrag
  über das Ende. `identify` antwortet in **einem** GET mit allem, was im Umschlag liegt.

`identify` ist dafür gemacht, an einer Stelle nachzusehen, nicht eine Fläche abzuholen; hier ist
die „Stelle" der Umschlag der ganzen Stadt (`geometry=310000,5662000,328000,5681000`,
`geometryType=esriGeometryEnvelope`, `tolerance=0`, `layers=all:16`). Das ist der Preis: eine
Anfrage, die ihren Zweck nicht im Namen trägt. Dafür steht sie vollständig im Profil, ein zweiter
Mensch kann sie in die Adresszeile kopieren, und die Antwort ist **1 043 618 Byte mit 179 Flächen
und 25 187 Stützpunkten**, SHA-256 `c2d3de4b862e615e6ddc998c6b7b4dd3f58bf35c4d4137a1b41b25ac4d093b94`
(abgerufen am 2026-10-14).

**Die URL pinnt die Genauigkeit, und das ist nachgemessen.** Derselbe Dienst antwortet auf dieselbe
Anfrage mit `maxAllowableOffset=1` in 443 085 Byte mit nur 17 326 Stützpunkten und auf zwei
Nachkommastellen gerundeten Koordinaten — je Fläche bis **1 465 m²** Unterschied (am größten bei
`40201`), in der Summe 48 736 m², und beide runden trotzdem auf 170,47 km². Welche von zwei
vorliegenden Antworten die URL liefert, war offline nicht zu entscheiden; ein Abruf am 2026-10-14
hat es entschieden: ohne den Parameter kommt die volle Genauigkeit, und `maxAllowableOffset=0`
ändert daran **nichts** (byte- und prüfsummengleich). Der Parameter steht trotzdem in der URL, denn
sonst hinge die Genauigkeit an einer Servervorgabe, die sich ändern darf.

`geometryPrecision` steht **nicht** in der URL, obwohl der Dienst es annimmt. Mit `11` wächst die
Antwort auf 1 073 358 Byte, und die Koordinaten sind dieselben Fließkommazahlen in längerer
Schreibweise (gemessen: wertgleich bis aufs Bit, dieselben 25 187 Stützpunkte). Das wäre mehr Text
ohne mehr Genauigkeit — die Rundung, die es verhindern soll, kommt hier von
`maxAllowableOffset`.

**Abgeschnitten ist schlimmer als kaputt.** Eine Antwort mit 1 000 von 1 200 Flächen ist gültiges
Esri-JSON: sie läuft durch die ganze Kette und macht eine Stadt kleiner, ohne dass irgendwo ein
Fehler steht. Darum zwei Marken, und beide sind nötig: der Dienst setzt `exceededTransferLimit`,
wenn er gekürzt hat (seine Auskunft, aber nicht jede Fassung setzt sie), und das Profil nennt mit
`precincts.min_areas` die Zahl der Flächen der Stadt (die Auskunft der Stadt, aber sie veraltet).
Mönchengladbach steht auf 179. Geprüft wird die Zahl an den beiden Formen, die sich ohne Zerlegen
zählen lassen -- GeoJSON an seinen Features, Esri-JSON an seinen `results`; beim Shapefile-Zip
bleibt es bei der Zeile des Schritts `shapes`.

**Die Ringe sind die eigentliche Arbeit.** Esri-JSON kennt kein Feld für „Loch"; das Vorzeichen der
Ringfläche sagt es (äußere Ringe im Uhrzeigersinn, innere dagegen — ArcGIS REST API, Geometry
Objects), und GeoJSON hält es umgekehrt und schachtelt Löcher in die Fläche, zu der sie gehören.
`geometry_from_esri_rings` dreht darum jeden Ring und ordnet jedes Loch dem **kleinsten** äußeren
Ring zu, der es enthält. Mönchengladbach hat beide Fälle, und zwar in derselben Ecke: Stimmbezirk
`11003` trägt einen Ring gegen den Uhrzeigersinn (ein Loch von 1 641 m²), `11001` an dieser Stelle
einen im Uhrzeigersinn (eine zweite Fläche von 1 639 m², also ein MultiPolygon). Wer beide gleich
behandelte, läge bei `11003` um 1 641 m² zu hoch und bei `11001` um 1 639 m² zu niedrig, und die
Stadtfläche stimmte zufällig trotzdem fast.

Geprüft ist das an der Fläche: die Nachbedingung der Umwandlung ist, dass die Netto-Fläche der
Ringe erhalten bleibt (Esri zählt außen negativ, also ist sie die negierte Summe über alle Ringe).
Über alle 179 Flächen der Antwort sind das **170,47 km²** — dieselbe Zahl, die das Shapefile von
2022 ergibt (`docs/plans/01-staedte.md`, § 3.2) und die Stadtfläche Mönchengladbachs. Dazu
hypothesis-Tests über Rechtecke (Umlaufrichtung, Loch, zweite Fläche, Flächentreue), crosshair über
`ring_signed_area` und `point_in_ring`, und Beispieltests an der echten Antwort.

**Verworfen:**

- **Das Shapefile von 2022 behalten und die Lücke auf der Seite nennen** (der Stand bis hierher).
  Die Flächen des Wahltags sind erreichbar, und „je Wahlbezirk gerechnet, kleine Neuzuschnitte
  fallen heraus" war eine Einschränkung aus Mangel, nicht aus Methode.
- **Die Flächen aus OpenStreetMap herleiten.** OSM kennt keine Stimmbezirke; sie wären aus
  Straßenabschnitten zu konstruieren, und das Ergebnis wäre eine eigene Behauptung statt einer
  amtlichen Angabe.
- **Die Flächen aus dem amtlichen Straßenverzeichnis der Wahl herleiten** (Straße und Hausnummern
  je Stimmbezirk). Dasselbe Problem eine Ebene tiefer: aus Adressen entstünden Polygone nur über
  eine Hüllen- oder Voronoi-Annahme, und die Übereinstimmung mit dem Verzeichnis, die die Seite
  heute als Maß zeigt, wäre danach per Konstruktion 100 % und sagte nichts mehr.
- **Den gestoppten Dienst `Stimmbezirke_Kommunalwahl_2025` bei der Stadt anfragen.** Eine Mail
  (`gdi@moenchengladbach.de`) wäre weiter sinnvoll — für eine Datei statt einer Operation und für
  eine Lizenzangabe bei der ITK Rheinland (Frage 1.4) —, aber sie ist kein nächster Schritt,
  sondern eine Bitte mit offener Antwortzeit.

**Kosten:** `member` und `dbf_encoding` entfallen im Profil der Stadt, `source_crs` kommt dazu (als
Rückfallebene, der Dienst nennt sein CRS selbst). Die Settings prüfen jetzt, **welche Schlüssel zu
welcher Quellform gehören**: `member` an einem GeoJSON sagt nichts, und `source_crs` an einem
Shapefile sieht aus, als gälte es — es gilt das `.prj` im Zip. Und die Zahlen der Stadt ändern
sich: 179 statt 180 Flächen im Schritt `shapes`, die vier bisher fehlenden Stimmbezirke kommen
dazu, und die Übereinstimmung mit dem Straßenverzeichnis wird neu gemessen.

**Gerechnet und gepackt am 2026-10-15.** Der Abruf lieferte genau die Antwort der Recherche
(1 043 618 Byte, dieselbe Prüfsumme), `shapes` rechnet 179 Stimmbezirke in 33 Wahlbezirken mit
170,47 km² und 25 187 Stützpunkten, und das Paket im Repo trägt die `identify`-Antwort statt des
Zips. Die vier Stimmbezirke, die 2022 fehlten, haben Straßen; die fünf, die es nur 2022 gab, sind
weg.

**Der erhoffte Sprung bleibt aus, und das ist das Ergebnis.** Die Übereinstimmung mit dem
amtlichen Straßenverzeichnis steigt von 86,2 % auf **88,8 %** je Wahlbezirk und von 66,5 % auf
**70,8 %** je Stimmbezirk (2 667 statt 2 651 Zuordnungen mit bekanntem Namen) — und bleibt damit unter den 90 %,
die `docs/runbook-stadt.md`, § 4 als Grenze nennt. Das Alter der Flächen war also **nicht** der
ganze Grund. Was bleibt, ist ein Unterschied der Bezugsgrößen, kein Fehler: das Verzeichnis ordnet
eine Straße über **Adressen** genau einem Stimmbezirk zu, Overpass liefert sie über die
**Geometrie** des Straßenzugs, und ein Zug, der eine Bezirksgrenze überschreitet, zählt in beiden
Bezirken. Die 315 Zuordnungen mit Namen, die das Verzeichnis gar nicht kennt, sind vor und nach
dem Wechsel dieselben.

**Nachgerechnet, nicht plausibel gemacht** (2026-10-15): von den 2 667 Zuordnungen mit bekanntem
Namen weichen **300 (11,2 %)** im Wahlbezirk ab, und sie verteilen sich auf 248 verschiedene
Namen. **Alle 300** betreffen Namen, die Overpass in **mehr als einem** Wahlbezirk liefert --
während das Verzeichnis nur bei **48** davon mehrere Bezirke nennt. Die Abweichung ist damit
nicht verteilt, sondern sitzt genau dort, wo ein Straßenzug eine Bezirksgrenze überschreitet: OSM
gibt ihn beiden Bezirken, das Verzeichnis einem. Das ist der Rest, den auch die Flächen des
Wahltags nicht einsammeln können. Die Grenze von 90 % misst damit für eine Stadt wie diese nicht nur den Stand der
Flächen; ob sie so bleiben soll, gehört in die nächste Runde am Runbook.

**Was sich sonst in den Zahlen bewegt hat:** 1 682 Treffer statt 1 704, 5 759 Begriffe, 2 219 Orte
statt 2 373 — und **489 Dokumente mit Treffer wie zuvor**, die Kachel der Seite ändert sich also
nicht. Die geometrieunabhängigen Golden Master (Urheber, Gremien, Korpus) sind unberührt; die
ganze `slow`-Suite blieb grün, ohne dass eine eingefrorene Zahl nachgezogen werden musste.

## 66. Was eine Abhängigkeitsrunde zurückhält: pypdf unter 7, crosshair bei 0.0.111 (2026-11-15)

Die Runde vom 2026-11-15 hob alles, was sich als wirkungsgleich messen ließ, und hält zwei Pakete
mit Absicht fest. `pyproject.toml` nennt beide Grenzen mit Grund, damit ein nacktes
`uv lock --upgrade` sie nicht mitnimmt (vorher hatte nur polars eine Obergrenze).

**Wie gemessen wurde.** Ein Paket, das Zahlen der Seite rechnet, bekommt einen A/B-Bau statt nur
der Tests: alle Seiten wie in `pages.yml` aus den Datenpaketen, einmal in einem Worktree am alten
Lock, einmal am neuen, je in eigener Datenwurzel über `GEOREP_SETTINGS`. Parquet wird als Frame
verglichen (die Bytes tragen den Schreiber), alles andere byteweise; `generated_at` und die daraus
abgeleiteten Prüfsummen der Download-Tabelle sind herausgerechnet. **Zwei Bauten am selben Lock
sind danach in allen 606 Dateien gleich**, das Rauschen ist also null und jede Abweichung ein
Befund. Ergebnis: polars 2.0.0 → 2.1.0 und numpy 2.5.3 → 2.5.4 ändern keine Zahl (in den
HTML-Seiten weichen allein sieben Größenangaben von Parquet-Dateien ab, weil der Schreiber von 2.1
dieselben Frames kleiner ablegt); pydantic 2.14.3 und pydantic-settings 2.16.3 lassen Fingerprint
und vollen Settings-Dump aller fünf Profile unverändert; unter loguru 0.8.0 ist die
Konsolenausgabe eines ganzen Baus zeilengleich. Die Laufzeit ist gepaart gemessen (alter und neuer
Stand abwechselnd, Minimum aus je drei Läufen), weil der Rechner unter Fremdlast stand.

**pypdf bleibt unter 7.** Der Name des Extraktors ist `pypdf-<Version>` und steht an jedem Text;
jede neue Version macht darum alle extrahierten Texte veraltet (Punkt 14). Gemessen an den 27 062
lokal gecachten PDFs (200 der Hauptperiode, 22 116 aus 2014 bis 2020, 4 088 der laufenden Periode,
658 aus Mönchengladbach):

| Vergleich | gleicher Text | anderer Text | Fehler |
|---|---|---|---|
| 6.21.4 gegen die abgelegten Texte aus 6.20.0 | 27 047 | 0 | 15 |
| 7.1.0 gegen 6.21.4 | 9 972 | 17 075 | 15 (dieselben) |

- **6.21.4 ist textgleich mit 6.20.0**, bis auf 15 PDFs aus 2014 bis 2020, die jetzt an einer
  neuen Schutzgrenze scheitern (`Reached maximum number of tokens per stream`). Ihr alter Text
  bleibt im Store stehen, denn `extract_missing` zählt sie als fehlerhaft und löscht nichts; jeder
  Lauf versucht sie erneut. Die Pakete im Repo tragen weiter `pypdf-6.20.0` und sind richtig.
- **7.1.0 ändert 63 % der Texte, und immer auf dieselbe Art**: einzelne Leerzeichen mitten im Wort
  fallen weg („ver putzt" → „verputzt", „halt estelle" → „haltestelle"; in vier Stichproben waren
  alle 63 Änderungen ein gelöschtes Leerzeichen). Das ist der bessere Text. Kein neuer Fehler: die
  im Netz gemeldete Ausnahme bei abgekürzten Filternamen trifft keine dieser PDFs.
- **Die Treue zur Arbeit sinkt von 197 auf 123 von 200 Texten** (zeichengleich mit den Texten der
  Arbeit; 6.20.0 und 6.21.4 erreichen beide 197).
- **Der Golden Master der Extraktion wird rot**: einer der vier Snapshots,
  `test_text_after_marker_snapshot[00439409.pdf]`.
- **Rund ein Prozent mehr Treffer**, bei gleicher Rangfolge der Wahlbezirke:

| Datensatz | Treffer 6.21.4 | Treffer 7.1.0 | Dokumente mit Treffer | Spearman der Quoten |
|---|---|---|---|---|
| Mönchengladbach | 1 682 | 1 700 (+1,1 %) | 489 → 490 | 0,9990 |
| laufende Periode | 5 448 | 5 453 (+0,1 %) | 2 173 → 2 173 | 0,9993 |
| 2014 bis 2020 | 36 324 | 36 788 (+1,3 %) | 12 977 → 13 085 | 0,9991 |

  Die Regression bewegt sich nicht (2014 bis 2020: r 0,2384 → 0,2368, p 0,133 → 0,136).

Warum es trotzdem nicht mitging: der Golden Master ist rot, also ist es kein Refactoring; die
19 033 Texte der Hauptperiode sind die der Arbeit und ließen sich nur nach einem Abruf aller
19 108 PDFs neu extrahieren — ohne ihn rechneten die Perioden mit zwei Extraktoren, und der
Abschnitt „Zwei Wahlperioden" vergliche auch die; und drei Pakete wären neu zu packen (rund 34 MB
neue Blobs). Das ist eine Methodenentscheidung mit eigenem Lauf, keine Abhängigkeitsrunde. Die
Untergrenze steigt auf 6.21.4, den Stand der Sicherheitskorrekturen vom 2026-11-09.

**Entschieden am 2026-11-16: pypdf 7.1.0 wird der Extraktor, siehe Punkt 67.** Was hier als Grund
fürs Zurückhalten steht, ist dort der Zwischenstand, den die Entscheidung in Kauf nimmt.

**crosshair-tool bleibt bei 0.0.111.** 0.0.113 (mit z3-solver 5.4.1) fand ein echtes Gegenbeispiel,
das 0.0.111 nie fand — `district_weight(n)` jenseits des größten floats, behoben mit rotem Test —,
stürzte danach aber in einem von vier vollen Läufen von `nox -s verify` selbst ab
(`ValueError: wrong parameter order: keyword-only parameter before variadic positional parameter`
in `dynamic_typing.intersect_signatures`, beim Ausformulieren eines Gegenbeispiels). 37 Einzelläufe
und sechs Teilläufe mit einer Hülle um die Meldung fanden kein Ziel dazu. Der Wochenlauf
`quality.yml` soll nur bei einem echten Befund rot werden; darum bleibt das gemessene Gespann
stehen, `crosshair-tool` 0.0.111 mit `z3-solver` 5.1.0.0 und `typeshed-client` 2.13.0 (die beiden
transitiven über `constraint-dependencies`). 0.0.112 ist nicht gemessen.

**Nebenbefund: die Extraktion hängt an der Umgebung.** pypdf meldet über die 27 062 PDFs 2 886 Mal,
dass fontTools fehlt („required to fully parse the encoding of a CFF Type1 font"). Ist es installiert,
ändern sich 12 der 27 062 Texte (alle aus 2014 bis 2020: der weiche Trennstrich U+00AD wird zum
Bindestrich). fontTools kommt nur über matplotlib in der Gruppe `notebook` ins Lock; extrahiert
wird in der Standardumgebung ohne diese Gruppe, und so sind die Pakete entstanden.

Verworfen: pypdf 7 still im Lock mitnehmen (der nächste lokale Lauf extrahierte alles neu, und
`georep pack` schriebe andere Texte ins Repo als die veröffentlichten); crosshair 0.0.113 behalten
und den Absturz hinnehmen; numpy 2.5.5 mitnehmen, das am Abend der Runde erschien und beim Heben
des Rests zweieinhalb Stunden alt war (gemessen ist 2.5.4).

## 67. pypdf 7.1.0 ist der Extraktor; die Hauptperiode zieht nach, wenn ihre PDFs da sind (2026-11-16)

Konrads Entscheidung auf die Messung in Punkt 66: pypdf 7 wird der Extraktor, der Abruf der
19 108 PDFs der Hauptperiode ist aufgeschoben.

**Was umgestellt ist.** `pyproject.toml` nennt `pypdf==7.1.0`, mit Absicht genau eine Version: der
Extraktorname trägt sie, und jede andere macht alle extrahierten Texte veraltet. Der Golden Master
der Extraktion ist bewusst erneuert, eine Zeile in einem von vier Snapshots (`chars` 2880 → 2879 in
`00439409.pdf`: das Leerzeichen vor einem Punkt). Die drei Datensätze mit lokalem PDF-Bestand sind
neu extrahiert und neu gepackt — je aus ihrem Paket aufgesetzt, die PDFs als Kopie daneben, die
Kette gerechnet, `georep pack --force`. In jedem Paket ändert sich allein `cache/text/texts.parquet`.

| Datensatz | neu extrahiert | Zeichen im Store | Treffer | Dokumente mit Treffer |
|---|---|---|---|---|
| Mönchengladbach | 658 von 658 | 3 394 323 → 3 388 824 | 1 682 → **1 700** | 489 → 490 |
| laufende Periode | 4 088 von 4 088 | 9 961 880 → 9 959 847 | 5 448 → **5 453** | 2 173 → 2 173 |
| 2014 bis 2020 | 22 101 von 22 116 | 67 852 547 → 67 697 693 | 36 324 → **36 788** | 12 977 → 13 085 |

**Kein Urteil der Seite kippt.** Was sich an den Aussagen bewegt:

| Größe | pypdf 6.20.0 | pypdf 7.1.0 |
|---|---|---|
| 2014 bis 2020, Tabelle 5 über alle 41 | r = 0,2384, p = 0,13330 | r = 0,2368, p = 0,13605 |
| 2014 bis 2020, ohne 1 und 10 | r = 0,2819, p = 0,08211 | r = 0,2808, p = 0,08334 |
| Regression der Differenzen zwischen den Perioden | r = 0,1008, p = 0,53045 | r = 0,1050, p = 0,51365 |
| Spearman der Trefferquoten zwischen den Perioden | 0,8106 | 0,8127 |
| Δ Trefferquote, Median (Spanne) | −0,0099 (−0,0865 bis +0,0079) | −0,0115 (−0,0870 bis +0,0059) |
| Mönchengladbach, Tabelle 5 | r = 0,1384, p = 0,44238 | r = 0,1294, p = 0,47310 |
| Mönchengladbach, Trefferquote max/min | 27,12 | 28,93 |

Die Urheber der alten Periode sind mit dem heutigen Profil dieselben geblieben (10 575 Verwaltung,
8 815 Fraktion, 2 356 unbekannt), ebenso alle Zahlen Mönchengladbachs zu Urhebern und Parteien.
Bewegt hat sich nur die Gegenprobe ohne den alten Vorlagenkopf (Punkte 60 und 62): mit den neuen
Texten zählt sie 7 014 statt 7 008 Fraktionsdokumente und 163 statt 161 Verwaltungsvorlagen, die
einen Fraktionsantrag nur zitieren. Die zwei Erwartungen in `tests/golden/test_parties_numbers.py`
sind bewusst nachgezogen, mit dem alten Wert im Kommentar.

**Der Zwischenstand, und was er kostet.** Die Hauptperiode rechnet weiter mit den 19 033 Texten
der Arbeit (`reference/`, Extraktor „pypdf (Arbeit, Januar 2026)"), die drei anderen Datensätze mit
7.1.0. Der Abschnitt „Zwei Wahlperioden" und der Städtevergleich stellen damit Datensätze
nebeneinander, die mit zwei Extraktoren gelesen sind. Der Extraktor allein hebt die Treffer der
alten Periode um 1,3 % (464 von 36 788) und die Mönchengladbachs um 1,1 %; gegen die Unterschiede,
die diese Abschnitte beschreiben (der Median der Trefferquote der Hauptperiode liegt 16 % unter
dem der alten), ist das klein, aber nicht null — und die Seite nennt den Extraktor nicht
(`docs/todo.md`, Punkt 7). Aufgelöst wird es mit dem Abruf der PDFs der Hauptperiode: dann lässt
auch sie sich mit 7.1.0 lesen. Das ist eine eigene Entscheidung, denn sie löst die Zahlen der
Hauptseite von den Texten der Arbeit; `bartzsch-exakt` bleibt der Anker (`docs/todo.md`, Punkt 8;
damals der Abruf der PDFs der Hauptperiode, erledigt am 2026-11-18; die Nummer trägt heute einen
anderen Punkt).

**Die 15 PDFs.** In 2014 bis 2020 tragen 15 Texte weiter `pypdf-6.20.0`: ihre PDFs weist pypdf seit
6.21 an einer Schutzgrenze ab (Punkt 66), `extract_missing` lässt den alten Text stehen, und die
Spalte `extractor` des Stores sagt es je Zeile. Wer die Periode ohne den alten Store aus den PDFs
extrahiert, bekommt diese 15 nicht.

**Der letzte Stand mit den Texten aus 6.20.0** ist der Tag `v0.14.0` und jeder Commit bis
`e340ade`. Lokale Textstores tragen ihn weiter, bis der Schritt `texts` dort wieder läuft; er
extrahiert dann alles neu (rund 20 Minuten für die drei Datensätze) und kommt bei den Texten der
Pakete an. Die 200 lokal gecachten PDFs der Hauptperiode liest ein lokaler Lauf ebenfalls mit
7.1.0, und 77 davon weichen dann von den Texten der Arbeit ab (mit 6.20.0 waren es drei); in CI
gibt es diese PDFs nicht, die veröffentlichte Hauptseite rechnet also rein mit den Texten der Arbeit.

Verworfen: die Schutzgrenze anheben, damit die 15 PDFs wieder lesbar sind (eine
Sicherheitskorrektur zurücknehmen für 15 Dokumente); die 15 alten Texte löschen (verliert ihre
Treffer, und der Store sagt je Zeile, woher ein Text kommt); eine Spanne statt einer Version
(`>=7.1,<8` ließe ein Patch-Release alle Texte veralten, ohne dass es jemand gemessen hätte); mit
dem Umstellen warten, bis die PDFs der Hauptperiode da sind (Konrad: jetzt umstellen, Abruf später).

## 68. Die Hauptperiode liest ihre Texte mit pypdf 7.1.0, aus einem eigenen Textpaket (2026-11-18)

Konrads Entscheidung, nachdem die PDFs da waren: die Hauptseite nimmt die Texte aus pypdf 7.1.0,
nicht mehr die 19 033 Texte der Arbeit. Damit liest jeder Datensatz der Seite mit demselben
Extraktor, und der Zwischenstand aus Punkt 67 ist aufgelöst.

**Woher die PDFs kommen.** `georep fetch pdfs` hat am 2026-11-17 von 22:40 bis 04:34 die fehlenden
17 892 der 19 092 Hauptdateien geholt (5 h 35 min, keine fehlgeschlagen, zusammen 2,7 GB). Die
19 108 Dokumente der Arbeit haben 19 092 PDFs: 16 nennen keine Hauptdatei, keine Datei gehört zu
zwei Dokumenten. Der Server war am Tag davor ausgefallen (jede Adresse `503`, `STATUS.md`,
„Bekannt").

**Wie die Texte ins Repo kommen.** Die Paper bleiben die der Arbeit (`reference/`, Altformat), nur
die Texte sind neu. Ein ganzes Paket wie für die anderen Perioden wäre ein zweites `reference/`;
ein Paket nur mit dem Textstore, wie das der Beratungsfolge (Punkt 58), ist genau die Änderung:

- `georep pack --texts <ziel>` packt nur `cache/text/texts.parquet` eines gelaufenen Profils, prüft
  ihn wie `pack` (jede Zeile aus einem Lauf, jeder Name ein Paper) und verweigert einen Store ohne
  einen einzigen Text aus einem PDF — das wäre der Store der Referenz ein zweites Mal.
- `[bootstrap].texts` nennt das Paket, `bootstrap` füllt die Stores wie bisher und legt danach den
  Store des Pakets über den Textstore (`overlay_texts`) — **nur, wenn er genau die Hauptdateien der
  Paper trägt**. Sonst ist es das Paket eines anderen Datensatzes, und die Texte der Referenz
  bleiben, mit einer Zeile im Bericht. Das ist keine Vorsicht um ihrer selbst willen: die
  Mini-Fixture bootstrappt mit den Settings der Hauptperiode und hat 200 ihrer Dateien; ohne die
  Bedingung trüge ihr Golden Master die neuen Texte.
- `profiles/duesseldorf.toml` setzt den Schlüssel auf `snapshots/duesseldorf-texte/…`, die beiden
  Periodenprofile nehmen ihn zurück, der Vergleich erbt ihn. `bootstrap` steht außerhalb des
  Settings-Fingerprints; was die Kette bemerkt, ist der neue Textstore.

Das Paket trägt 19 092 Texte, einen je Hauptdatei: 19 091 aus pypdf 7.1.0, 59 davon leer (PDFs ohne
Textschicht, die die Arbeit ebenfalls ohne Text führte), und einen Text der Arbeit. Gegen die Arbeit
sind 11 002 der 19 033 Texte mit Inhalt zeichengleich und 8 031 verschieden (42 %); das ist die
Sorte aus Punkt 66, Leerzeichen mitten im Wort, die der Extraktor der Arbeit setzte. 15 563 293
Bytes; alle Pakete zusammen 160 396 687 Bytes.

**Was sich bewegt** (A/B-Bau aller Seiten aus den Datenpaketen, wie `pages.yml`, am 2026-11-18;
dieselben Regeln, nur die Texte verschieden):

| Größe | Texte der Arbeit | pypdf 7.1.0 |
|---|---|---|
| Treffer (Dokument-Bezirk-Paare) | 29 010 | **29 330** (+1,1 %) |
| Dokumente mit Treffer | 10 739 | **10 799** |
| Median der Trefferquote (Spanne) | 0,0604 (0,0261 bis 0,1513) | 0,0612 (0,0263 bis 0,1535) |
| Tabelle 5 über alle 41 | r = 0,1891, p = 0,23641 | r = 0,1901, p = 0,23383 |
| Tabelle 5 ohne 1 und 10 | r = 0,3351, p = 0,03705 | r = 0,3363, p = 0,03635 |
| Treffer je Begriff, Regression über alle | r = −0,1118, p = 0,48644 | r = −0,1125, p = 0,48365 |
| Kontrollen, Modell B (Term der Quote) | 43,531, p = 0,14476 | 41,602, p = 0,16280 |
| Regression der Differenzen zwischen den Perioden | r = 0,1050, p = 0,51365 | r = 0,0982, p = 0,54136 |
| Spearman der Trefferquoten zwischen den Perioden | 0,8127 | 0,8230 |
| Δ Trefferquote, Median (Spanne) | −0,0115 (−0,0870 bis +0,0059) | −0,0102 (−0,0865 bis +0,0070) |
| Trefferquote max/min (Städtevergleich) | 5,80 | 5,84 |
| stadtweite Begriffe (über 64 Dokumenten) | 55 | 57 |

Jeder der 41 Wahlbezirke bekommt Treffer dazu (1 bis 25), keiner verliert; die Rangfolge der Quoten
bleibt fast gleich (Spearman 0,9983, 14 Bezirke rücken um höchstens zwei Plätze, 2 und 10 tauschen
den zweiten und dritten Platz). **Kein Urteil der Seite kippt**: die eine Spalte mit signifikantem p
bleibt es, und von den 32 Termen der Trefferquote in den Regressionen mit Kontrollen kreuzt keiner
die 0,05 (am nächsten „Migrationshintergrund, ohne 1 und 10" mit 0,067 → 0,054). Die Seiten der
Periode 2014 bis 2020, der laufenden Periode und Mönchengladbachs bleiben, wie sie sind; das
Themenmodell behält seine Themen, nur hintere Wörter der Beschriftungen wechseln.

**Was die Golden-Master-Tests prüfen.** Gegen die Arbeit wird weiter mit ihren Texten gerechnet:
`as_in_the_thesis` nimmt das Paket zurück, und `test_the_rules_change_the_reference_as_measured`
misst die beiden Regeln aus Punkt 44 allein. Was das Paket dazu ändert, hält
`test_the_text_package_moves_the_reference_as_measured` fest; dass es zu genau den Dateien der Arbeit
gehört, ein `slow`-Test in `tests/unit/test_data_packages.py`. `reference/` bleibt unberührt, der Tag
`bartzsch-exakt` der Anker für die Zahlen der Arbeit, und der letzte Stand der Hauptseite mit den
Texten der Arbeit ist `v0.15.0` samt jedem Commit bis `648bfe4`.

**Was dabei auffiel: vier Sätze der Seite stimmten nicht.** Die Seite nannte die ausgeschlossenen
Wahlbezirke 1 und 10 an vier Stellen „die (beiden) höchsten Trefferquoten" (Tabelle 5, ihre
Fußnote, „Methode und Grenzen", die Fußnote der Gewichtung), fest im Text. Mit den neuen Texten
steht 10 auf Platz 3 — und auf der Seite der Periode 2014 bis 2020 stehen die beiden schon seit
ihrer Veröffentlichung auf Platz 2 und 9. `RegressionPair` trägt jetzt die Plätze der
ausgeschlossenen Bezirke (`excluded_ranks`), und das Makro `excluded_rates` sagt „die beiden
höchsten" nur, wenn es stimmt, sonst „Trefferquoten auf den Plätzen 1 und 3". Der Ausschluss selbst
bleibt, wie er ist: er ist die Entscheidung der Arbeit, und Punkt 61 begründet, warum keine Regel
ihn ersetzt.

**Der eine Text der Arbeit.** `00403713.pdf` (6,5 MB) ist mit AES verschlüsselt; pypdf braucht dafür
das Paket `cryptography`, das nicht im Lock steht, und meldet `CorruptPdfError: cryptography>=3.1 is
required for AES algorithm`. `extract_missing` lässt den alten Text stehen (187 472 Zeichen). Ob
`cryptography` ins Lock kommt, ist eine eigene Frage: es ist eine kompilierte Abhängigkeit für ein
einziges Dokument der Hauptperiode, und in den anderen drei Datensätzen fehlt kein Text aus diesem
Grund.

Verworfen: ein ganzes Paket der Hauptperiode im eigenen Format (verdoppelte die Paper der Arbeit,
die sich nicht ändern, und trennte sie von `reference/`); die neuen Texte nach `reference/` schreiben
(der Golden Master der Arbeit ist nur lesbar, Punkt 56); das Paket ohne die Bedingung der gleichen
Dateien übernehmen (die Mini-Fixture bekäme fremde Texte); die Bedingung über eine Prüfsumme des
Korpus der Arbeit statt über die Dateinamen (strenger, aber ein Paket aus einem neuen Abruf der
Metadaten bräuchte dann eine neue Prüfsumme, obwohl seine Dateien dieselben wären).

## 69. Vorhaben tragen bei, statt den Kern zu ändern: Register für Schritte, Tabellen, Unterseiten; ein Schema für Spannen (2026-11-23)

Fundament F2 und F3 der Vorverarbeitung 2026-11 (`docs/plan-vorverarbeitung-2026-11.md`, § 2.3,
§ 2.4 und § 7), gebaut vom Supervisor direkt auf `main`, bevor Agenten parallel Code schreiben.

**Das Problem.** Neunzehn Vorhaben würden dieselben Stellen ändern: `pipeline.build_steps` (eine
Funktion von rund 950 Zeilen), `report/tables.py` (das Register der veröffentlichten Tabellen),
`report/model.py` (2 401 Zeilen) und die Abschnitte von `index.html`. Beim Merge der acht Optionen
im Oktober endeten an rund zwölf Stellen beide Konfliktseiten mitten in einer Funktion. Und
`index.html` hat bis zum Budget von 1,0 MB (Punkt 50) nur rund 60 KB Luft.

**Die Lösung.** `georep.enrich.CONTRIBUTIONS` ist ein Tupel von `Contribution`-Objekten, je Vorhaben
eines, mit Schritten (`steps(settings, layout)`), veröffentlichten Tabellen und Unterseiten:

- Die Schritte stehen in `build_steps` unmittelbar vor `report`, in Registerfolge; ein doppelter
  Name ist ein `DuplicateStepError`.
- Die Tabellen hängt `report.tables.all_tables` hinter die des Kerns; `published`, `csv_plan` und
  das Aufräumen alter Downloads lesen nur noch diese Funktion. Ein doppelter Name ist ein
  `SchemaError`, denn er ist Dateiname im Download-Ordner.
- Eine Unterseite (`report.pages.Page`) hat einen eigenen Schritt `page_<name>` hinter `report`,
  mit demselben Vorlagen-Hash im Stamp (Punkt 53), und steht im Abschnitt `58-weitere` der
  Hauptseite, der ohne Unterseiten fehlt. Ihr Rahmen (`templates/page.html.j2`) bindet dieselben
  zwei Teilvorlagen ein wie die Hauptseite: `templates/frame/style.css.j2` (Farbtokens hell und
  dunkel, Typografie, Tabellen, Vorschau, Dialog) und `templates/frame/script.js.j2`
  (`window.georep`). Sie sind aus `report.html.j2` herausgelöst; `{% include … +%}` hält den
  Zeilenumbruch, den `trim_blocks` sonst schluckt.
- `pipeline` und `report.tables` importieren das Register erst in der Funktion: die Beiträge bauen
  `Step` und `PublishedTable` aus diesen Modulen, und ein Import auf Modulebene wäre ein Kreis.

Die gemeinsame Stelle eines Vorhabens schrumpft damit auf eine Importzeile und einen Eintrag in
`georep/enrich/__init__.py`; Settings bleiben bei der Anhängeregel aus
`docs/plans/00-synergien.md`, § 2.

**Spannen (F3).** `georep.spans` legt ein Schema für jede Stelle im Text fest: `id`, `start`, `end`
(halboffen), `kind`, `value`, `norm`, `section`, `extractor`, sortiert nach `id, start, end,
kind`. `check_spans` prüft Schema, Grenzen gegen die Textlänge je Dokument und die Folge und nennt
die erste verletzende Zeile; `excerpt` liefert eine Spanne mit Kontext für Kodieraufträge.
`extractor` steht an jeder Zeile, weil es zwei Textstores gibt (kleingeschrieben und, ab F1, roh) und
eine Position nur in ihrem eigenen Text etwas bedeutet.

**Geprüft.** Ein A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt 66, vor (`ab/f2-a`) und
nach F2 (`ab/f2-b`), mit dem Vergleichsskript `ab/ab_vergleich.py` auf xtraspace. Ohne Beiträge ist
jede Seite gleich bis auf die Prüfsummen, die an `generated_at` hängen.

**Verworfen.** `Step` in ein eigenes Modul verschieben, um den Importkreis aufzulösen (sauberer,
aber ein Konflikt mit jedem Branch, der gerade ein Feld an `Step` hängt, wie F5); ein Register auch
für die Settings (jedes Vorhaben ein eigenes Settings-Modul, das sich anmeldet: pydantic will die
Felder zur Klassendefinition kennen, und die Anhängeregel hat im Oktober gereicht); neue Abschnitte
auf `index.html` mit größerem Budget (das Budget ist eine Zusage an die Leser, Punkt 50);
Unterseiten ohne den Rahmen der Hauptseite, wie `vergleich.html` (eine zweite Kopie der Farben, die
auseinanderläuft).

## 70. Sitzungen, Beratungen und Personen sind drei Netzschritte, und der Server bestimmt, wie sie nachholen (Fundament F6, 2026-11-23)

Fundament F6 (`docs/plan-vorverarbeitung-2026-11.md`, § 7) holt, was die Vorhaben 26 bis 28 brauchen:
Sitzungen mit Tagesordnung und Ergebnis, die Beratungen, die ein Paper mit ihnen verbinden, und
Personen mit ihren Mitgliedschaften. Grundlage ist eine Netzstichprobe vom 2026-11-23 (41 s
Antwortzeit, je ein, zwei Seiten, `tests/fixtures/http/README.md`) und der Paper-Abruf vom
2026-10-13/14, dessen Seiten noch im HTTP-Cache liegen. Die Zahlen stehen in
`docs/runbook-sitzungen.md`, § 2 bis 4.

**Drei Schritte, drei Listen, ein Abruf.** `meetings` (Liste `meetings`, die Tagesordnung ist
eingebettet), `consultations` (Liste `consultations`) und `persons` (Liste `people`, die
Mitgliedschaften sind eingebettet); jeder fehlt, wo das Profil unter `[council]` keinen Endpunkt nennt,
und die Vorgaben sind stadtneutral leer. `fetch_objects` liest jede Liste mit der Mechanik von
`fetch_papers` und prüft jedes Objekt gegen sein Modell; `OparlObject` ist die gemeinsame Basis, ein
Umschlag `ListPage` ersetzt eine Seitenklasse je Liste. Die Schritte heißen nach dem, was sie
schreiben (`persons`), die Endpunkte nach dem Server (`…/people`).

**Nachholen mit `modified_since` nur, wo `modified` stimmt.** Bei 69 von 314 Sitzungen mit
Tagesordnung ist ein Punkt jünger als die Sitzung (bis 245 Tage), bei 91 von 198 Personen eine
Mitgliedschaft jünger als die Person. Ein Lauf mit Filter verpasste also nachgetragene Ergebnisse und
neue Mitgliedschaften. `council.incremental` nennt darum nur `consultations`; `meetings` und `persons`
holen jedes Mal alles, geschätzt drei und zweieinhalb Minuten.

**Sitzungen ab dem Periodenbeginn, ohne Obergrenze.** Eine Vorlage vom Periodenende wird oft erst in
der nächsten Periode beraten; mit Obergrenze fehlte ihr Ergebnis. Die Liste ist nach ID absteigend
(Anlegedatum), nicht nach Beginn, und `start − created` reichte in 400 Sitzungen von −418 bis +447
Tagen. Der Abruf endet darum erst nach einer Seite, deren jüngste Sitzung mehr als
`council.created_margin_days` (500) vor dem Periodenbeginn angelegt wurde (Review 2026-11-23). Die
erste Fassung fragte wie bei den Papers nach dem Beginn und hätte nach einer nachgetragenen alten
Sitzung aufgehört, vor einer früh angelegten der Periode auf der nächsten Seite. Verworfen auch
„nach zwei Seiten ganz vor dem Beginn": die Marge folgt aus der Sortierung und einer gemessenen
Grenze, nicht daraus, wie viele nachgetragene Sitzungen zufällig auf einer Seite stehen, und kostet
höchstens die Seiten der 500 Tage davor.

**Personen ohne Kontaktdaten, durch das Modell.** Der Server schickt zu jeder Person Telefon, E-Mail
und Anschrift, auch von Fraktionsmitarbeitern und sachkundigen Einwohnern. `OparlPerson` kennt diese
Felder nicht (`PERSON_PRIVATE_KEYS`), also steht keines in einer Datei eines Laufs; ein Test hält
beides fest, und die Fixture ist geschwärzt.

**Die Verbindung zum Ergebnis läuft über die ID der Beratung.** Jedes Paper bettet seine Beratungen
mit `meeting` und `agendaItem` ein (98,9 %), jeder Tagesordnungspunkt nennt seine Beratung. Verbunden
wird über `agendaItem.consultation == consultation.id`, denn eine vertagte Vorlage steht auf zwei
Tagesordnungen, und die Beratung nennt nur den späteren Punkt (340 von 3 880 Fällen auf einer Seite).
Die 19 108 Paper müssen dafür nicht neu abgerufen werden; die Beratungen liefert der Schritt
`consultations` oder einmalig ein Auszug aus dem Cache.

**Eine Probe ist der Anfang des Abrufs, und nur ein vollständiger schreibt.** Jede Seite geht mit
`fsync` in eine Teildatei, danach der Fortschritt nach `raw/<schritt>.progress.json`: nächste URL,
Zeilen je Teildatei, die gemeldeten Löschungen, Beginn und ein Schlüssel aus Endpunkt,
`period.start` und dem Hash von `[council]`. Die Ausgabe schreibt erst der Abruf, der beim letzten
Blatt ankommt; eine Probe mit `--max-pages` lässt sie stehen, und der nächste Lauf setzt fort. So
kommt `since` nur aus einer vollständigen Ausgabe. Eine Fortsetzung kürzt die Teildateien auf die
Zeilen des Fortschritts und verwirft ihn, wenn er älter als die Marge von `since` ist (ein Tag),
eine Teildatei fehlt oder kürzer ist oder der Schlüssel abweicht; die Zeile sagt warum.
`freshness` meldet einen Netzschritt mit offenem Fortschritt als „Abruf unvollständig", und eine
Sperre auf `raw/<schritt>.lock` lässt jeden Schritt je Ordner `raw/` nur einmal laufen
(`duesseldorf-vergleich` teilt ihn mit `duesseldorf`). Die erste Fassung schrieb die Seiten einer
Probe als Ausgabe, verlor Löschungen bei einer Fortsetzung und ließ zwei gleichzeitige Läufe die
Ausgabe kürzen (Review 2026-11-23, Befunde 1, 2, 4, 5). `fetch papers` hat die Schwäche der Probe
noch (`docs/todo.md`); dieser Punkt ändert es nicht.

**Hinter einem Schalter, außerhalb des Fingerprints.** `council.enabled` ist aus; ohne ihn fehlen
die drei Schritte, und ein bloßes `georep fetch` nimmt sie nicht mit — volle Abrufe sind Konrads
Läufe (Plan 2026-11, § 4 und § 7). `[council]` steht nicht im globalen Fingerprint, denn es
betrifft nur diese drei Schritte; ihr Stamp trägt seinen Hash als `extra` (wie Punkt 53), und das
Einschalten lässt die Kette nicht neu rechnen. Eine volle Seite ohne `links.next` ist ein
`FetchError` statt eines stillen Endes; nur `pagination` könnte sie als letzte belegen, und dieser
Server setzt `totalPages` nicht.

**Die Pfade gehören dem Modul, nicht dem Layout.** `georep.council.council_files(layout)` nennt die
fünf Dateien unter `raw/`; `Layout` und `pipeline.py` bekommen damit nur die drei Step-Zeilen, und die
Vorhaben, die die Dateien lesen, finden sie an einer Stelle.

**Was der Server nicht füllt, steht in Tests.** `resolutionText`, `resolutionFile`, `cancelled`,
`meetingState`: nie. `resultsProtocol`, `verbatimProtocol` und `invitation` sind dieselbe Datei, ein
Nachtrag zur Tagesordnung; die Niederschrift ist eine Anlage („Niederschrift Ö"). Ändert der Server
das, wird `tests/unit/test_oparl_council.py` rot.

Verworfen: die Liste `agendaitems` statt der Sitzungen (sie ist mit 0,77 s je Seite schnell, braucht
aber für rund 90 000 Punkte rund 450 Seiten mit je einer Sekunde Pause, die Sitzungsliste 18 und
bringt Datum und Gremium mit); die Liste `memberships` neben den Personen (dieselben Objekte, 80 von
80 gleich); die 19 108 Paper neu abrufen, um die Beratungen zu behalten (Stunden für eine Angabe, die
die Liste `consultations` oder der Cache liefert); Tagesordnungspunkt und Paper über den Titel
verbinden (97,4 % wortgleich, als Rückfall brauchbar, als Schlüssel nicht); `resultsProtocol` als
Niederschrift lesen (es ist keine); die drei Listen im HTTP-Cache halten (die Teildateien ersetzen ihn
für die Fortsetzung, und `http.sqlite` wüchse um rund 70 MB je Abruf der Sitzungen); die Felder
`auxiliaryFile`, `consultation` und `subordinatedPaper` jetzt in `PaperRecord` aufnehmen (berührt den
Korpus und gehört zu Vorhaben 14 oder 26; Empfehlung im Runbook, § 3); Niederschriften jetzt holen
(Vorhaben 26 braucht sie nicht, `result` trägt das Ergebnis; erst Vorhaben 28 entscheidet nach einer
Stichprobe, Runbook, § 7).
## 71. Validierung mit zwei KI-Kodierern: Codebuch je Vorhaben, Stichprobe ohne Zufallsgenerator, Maße in reinem Python (2026-11-23)

Fundament F4 des Plans [plan-vorverarbeitung-2026-11.md](plan-vorverarbeitung-2026-11.md) (§ 2.6,
§ 7). Konrad kodiert nicht selbst; jede Messung der neunzehn Vorhaben braucht trotzdem eine geprüfte
Stichprobe, und Stufe 3 zeigt nur, was validiert ist. Gebaut ist das Paket `georep.validation` mit
`georep validate sample|tasks|merge|score`; das Handbuch mit den Prompt-Vorlagen ist
[validierung.md](validierung.md).

**Zwei unabhängige Kodier-Agenten und ein Schlicht-Agent, kein menschlicher Goldstandard.** Die
Kodierer sehen je ihren eigenen Ordner (Auftrag, Codebuch, Antworten), nicht die Ausgabe des
Verfahrens und nicht einander, und dieselben Einheiten in verschiedener, fester Folge. Gestartet
werden sie als frische Agenten, nicht als Fork des Supervisors, dessen Kontext die Ausgabe trüge.
Die Schlichtung bekommt nur die strittigen Einheiten mit beiden Urteilen. Was das misst, sagt die
Seite wörtlich: „geprüft von zwei KI-Kodierern an *n* Dokumenten, nicht von Menschen". Weil beide
Kodierer dasselbe Modell sind, ist α eine obere Schätzung der Schärfe des Codebuchs, keine der
Richtigkeit; die Schwelle α ≥ 0,8 für Stufe 3 steht als `validation.min_alpha` in den Settings.

**Das Codebuch ist eine TOML-Datei im Repo** (`validierung/<NN-name>/codebuch.toml`), geprüft von
pydantic: Einheit (`document`, `document_pair`, `span`, `query_document`), Frage, Optionen mit
Definition und Beispiel, Skala (nominal, ordinal, binär), Anweisungen und die Regeln für Stichprobe,
Auftrag und Auswertung. Es ist das Instrument und wird versioniert; wer es an den Uneinigkeiten
schärft, kodiert eine neue Stichprobe.

**Die Stichprobe zieht kein Zufallsgenerator, sondern ein Rang**: SHA-256 über Seed und Schlüssel,
je Schicht die kleinsten Ränge (bottom-k), die Aufteilung ganzzahlig (proportional mit einer
Einheit je Schicht und größtem Rest, oder gleich je Schicht). Damit ist sie auf jedem Rechner und
mit jeder Bibliotheksversion dieselbe, hängt nicht an der Zeilenfolge und verschiebt sich um
höchstens eine Einheit, wenn die Grundgesamtheit eine dazubekommt (hypothesis hält beides fest).

**Was ins Repo kommt**: Codebuch, Stichprobe (nur Schlüssel und Schicht), `labels.csv` (`id`,
`kodierer_a`, `kodierer_b`, `schlichtung`, `label`), README und `guete.json`. Aufträge und Antworten
tragen Ausschnitte aus Ratsdokumenten und Begründungen, die sie zitieren dürfen; sie liegen unter
`validation.coding_root` (auf Konrads Rechner `messdaten/kodierung/` auf xtraspace, sonst
`data_root/kodierung/`), und das Paket verweigert einen solchen Ordner unter `validation.root`.
Der Block `[validation]` zählt nicht zum Fingerprint: kein Schritt der Kette liest ihn.

**Die Maße sind reines Python** (`georep.validation.measures`): Wilson-Intervall, Cohens κ,
Krippendorffs α (nominal, ordinal, intervall, mit fehlenden Werten), Präzision, Recall, F1 je Klasse,
mikro und makro, Konfusionsmatrix, nDCG@k. Geprüft gegen eine Rechnung von Hand (Wilson), die
Rechenbeispiele aus Krippendorff (2011) und scikit-learn (`cohen_kappa_score`,
`precision_recall_fscore_support`, `confusion_matrix`, `ndcg_score`), dazu hypothesis und
`deal.cases`; fünf Funktionen stehen in `VERIFY_TARGETS`. Undefiniertes ist `None`, nicht 0.

Verworfen: scikit-learn im Paket (es darf nur in zwei Modulen von `analysis/` stehen, und sein Import
kostet jeden Befehl 0,4 s; als Gegenprobe in den Tests genügt es); das PyPI-Paket `krippendorff`
(eine Abhängigkeit für rund vierzig Zeilen, die die veröffentlichten Beispiele ohnehin prüfen);
numpy oder Polars zum Ziehen (ihre Zufallsfolgen sind über Versionen nicht zugesichert); ein
Kodierer allein (keine Reliabilität, nur ein Urteil); Kodierer, die die Ausgabe des Verfahrens
sehen (sie messen dann Zustimmung statt Güte); Wald-Intervalle (über 1 und null breit an den
Rändern, wo die Präzisionen der Kriterien liegen); ein Wilson-Intervall für F1 und Makromittel (sie
sind keine Anteile; ein Bootstrap gehört, wo nötig, ins Messskript); eine HTML-Ansicht für Menschen
(niemand kodiert von Hand, Plan § 7); die Aufträge im Repo (Ratstext, Plan § 4).

**Zweite Runde nach dem Review (2026-11-23).** Die Vorhaben 11 bis 14 stellen je Einheit mehrere
Fragen, teils bedingt; das Codebuch trägt darum `[[questions]]` mit eigener Skala (dazu `interval`
für Zeilennummern, `open` für freie JSON-Werte, `spans` für Markierungen), `only_if` und
`adjudicate`, und Übereinstimmung, Schlichtung und Labels (`id, frage, kodierer_a, kodierer_b,
schlichtung, label`) gibt es je Frage. Eine geschichtete Stichprobe wird nicht mehr wie eine
einfache ausgezählt: jede Zeile trägt N_h (`schicht_n`), `score` gibt je Schicht, in der Stichprobe
und für die Grundgesamtheit (Σ W_h·p_h mit Wilson bei Kishs effektivem n; verworfen: geschichteter
Bootstrap und geschichtete Normalnäherung, beide null breit, wenn Schichten nur Treffer haben), und
`allocate` teilt proportional ohne vorab gesetzte Mindesteinheit. Eine zweite Kodierrunde mit
neuem Codebuch ist ein eigener Ordner (`14-vorgaenge-2-f4`), nicht eine zweite Datei im selben:
Codebuch, Stichprobe und Labels gehören zusammen. Vorläufige Antworten von vor F4 übernimmt
`georep validate import` nach `[provisional]` im Codebuch, ohne die Quelldateien zu ändern; für
Vorhaben 14 rechnet das die Zahlen des Messdokuments nach (α 1,000 / 0,819 / 0,935,
Kantenpräzision 139/150 = 0,927, gewichtet 0,922; Runde 2: 85/100 = 0,850, gewichtet 0,840).
Die übertragenen Vorhaben liegen in eigenen Ordnern `<NN-name>-f4` neben den Ordnern der Messungen, weil deren Messskripte die alten Dateien lesen und ihre Unverändertheit prüfen (Supervisor, dritte Runde). Verworfen: den Leerraum in offenen Antworten ganz zu entfernen, wie es die vorläufigen Auswertungen
von 11 und 12 taten („66 - Amt" gleich „66-Amt"): das ist eine Entscheidung über die Frage, nicht
über die Form, und gehört, wenn überhaupt, als Einstellung je Frage ins Codebuch.

**Das Modell je Rolle und die Form des Satzes (F4-Nachzug V3, 2026-11-27).** Seit Konrads
Antwort auf Frage 19 (2026-11-26) ist Kodierer B für neue Messungen ein anderes Modell als A und
die Schlichtung. `merge` nimmt darum das Modell je Rolle (`--model-a`, `--model-b`,
`--model-adjudicator`; `--model` bleibt die Kurzform für alle drei, eine eigene Angabe geht vor,
und fehlt einer Rolle ihr Modell, ist es ein Bedienfehler). `guete.json` führt `modelle` mit
`kodierer_a`, `kodierer_b` und `schlichtung` an der Stelle des früheren `modell`, das README eine
Zeile **Modelle**. Der `satz` hat genau eine von zwei Formen:

- A und B dasselbe Modell: „geprüft von zwei KI-Kodierern desselben Modells (claude-opus-5-5) an
  600 Textstellen, nicht von Menschen";
- zwei Modelle: „geprüft von zwei KI-Kodierern (claude-opus-5-5 und *B*) an 52 Dokumentpaaren,
  Schlichtung durch claude-opus-5-5, nicht von Menschen".

„Schlichtung durch …" steht, wo es Uneinigkeiten gab und die Schlichtung nicht das eine Modell
aller drei Rollen ist; sind alle drei gleich, sagt „desselben Modells" es für die Schlichtung mit
(so lauten alle Sätze der Labels bis zum 2026-11-26). Ohne Uneinigkeit nennt der Satz keine
Schlichtung, weil keine stattfand; README und `guete.json` nennen ihr Modell trotzdem. Die Zahl der
Einheiten steht vor der Schlichtung, „nicht von Menschen" immer am Ende, damit eine Seite den Satz
unverändert übernimmt. Verworfen: der Satz ohne Modell (er sagt nicht, ob ein Modell sich selbst
geprüft hat) und „geschlichtet von …" vor der Zahl (der Satz läse sich, als hätte die Schlichtung
alle Einheiten geprüft).

## 72. Lokale Modelle über ollama: eine Naht mit Cache, Kennung im Stamp und Schalter (2026-11-23, Fundament F5)

Drei Vorhaben des Plans zur Vorverarbeitung brauchen ein Sprach- oder Einbettungsmodell
(`docs/plan-vorverarbeitung-2026-11.md`, § 7 und § 11: 18 Einbettungen, 19 Politikfelder, 20
Kurzfassungen). Fundament F5 legt fest, wie ein Schritt ein Modell benutzt; welches Modell er wofür
nimmt, entscheidet jedes Vorhaben in seiner Messung.

**Warum lokal.** Plan § 2.8 und Konrads Antwort auf Frage 3: die Dokumente verlassen den Rechner
nicht, ein Lauf kostet je Dokument nichts, und Modellname und Digest im Stamp machen ihn
wiederholbar. Ein externer Dienst kommt nur für eine Kalibrierungsstichprobe in Frage (Frage 4),
und die übernehmen Opus-Agenten. Der Rechner hat eine RTX 4090 mit 24 GB.

**Warum ollama über HTTP und keine Python-Bibliothek.** Der Client in `georep.ml.ollama` spricht
sechs Endpunkte über `requests`, das ohnehin im Lock steht:

- **Keine neue Abhängigkeit.** Die Bibliothek `ollama` brächte `httpx` und nichts, was diese sechs
  Endpunkte nicht auch tun. `sentence-transformers` oder `transformers` brächten `torch` mit CUDA
  (mehrere GB) ins Lock, das CI ohne GPU installieren müsste; `llama-cpp-python` ist ein Kompilat je
  Rechner. Die Gewichte gehören nicht in die Umgebung des Pakets.
- **Ein Modell im Speicher für alle.** Der Server hält ein geladenes Modell über Prozesse hinweg
  (`keep_alive`); zwei Läufe, ein Rauchtest und `georep ml bench` teilen es, und die
  GPU-Warteschlange des Supervisors (Plan § 5) stellt die Aufträge nur hintereinander. Ein
  Modell im eigenen Prozess lüde 17 GB je Aufruf von `georep`.
- **Dieselbe Testnaht wie jede Quelle.** `Transport` und ein Server als Tabelle (`FakeOllama`);
  kein Test braucht eine GPU, und die Antworten prüft pydantic an der Grenze wie bei OParl.
- **Der Digest ist eine genaue Kennung.** `/api/tags` nennt den SHA-256 des Modellmanifests; ein
  `ollama pull` mit neuem Stand ändert ihn, auch wenn der Name bleibt.

Verworfen außerdem: vLLM (ein eigener Server mit eigenem Speicherverwalter, für eine Karte und
Stapel von Hunderten Dokumenten kein Gewinn, den ollama nicht auch hat) und die OpenAI-kompatible
Schnittstelle von ollama (`/v1/…`; sie nennt weder Digest noch Fähigkeiten, und die Kennung im
Stamp braucht beides).

**Wie ein Schritt das Modell bekannt gibt.** `Step` bekommt **ein** Feld `models`: das Modell im
Schritt als `ModelUse` (`EmbeddingUse`, `GenerationUse`), mit `identity` (Name, Digest,
Prompt-Version, Schlüssel der Optionen, bei Einbettungen der des Fensters `num_ctx` und
`truncate`) und `stamp` (dazu `limit`, `open`, `failed` des letzten Laufs). Ist es gesetzt, läuft
der Schritt nur mit `georep run --models`, wie ein Netzschritt nur mit `--online`, und ohne
Schalter kommt sein Ergebnis aus einem Paket. Ein Feld statt zweier (`models: bool` und eine
Kennung daneben), weil zwei Felder zwei falsche Zustände zulassen: ein Modellschritt ohne Kennung
(ein neues Modell machte ihn nicht veraltet) und eine Kennung ohne Schalter (der Server würde ohne
`--models` gefragt). Ein Objekt statt eines festen Werts, weil den Digest nur der Server kennt
(`build_steps`, `georep steps` und jeder Lauf ohne Schalter fragen ihn nie) und weil erst der Lauf
weiß, was offen blieb. Und dasselbe Objekt geht an `embed_texts` oder `generate_texts`: es bildet
auch die Prompt-Version im Cache-Schlüssel, so können Kennung im Stamp und Schlüssel im Cache nicht
auseinanderlaufen. Die Kennung steht lesbar unter `"models"` im Stamp, nicht als Hash in `extra`,
damit ein Mensch sieht, mit welchem Modell eine Datei entstand; Stamps anderer Schritte bekommen
den Schlüssel nicht und bleiben gültig. Der Diff in `pipeline.py` ist ein Feld, die Bedingung und
die Fehlerbehandlung in `run_step` und ein Zusatz in `expected_stamp` und `stamp_mismatch`.

**Nichts aus `[ml]` steht im Settings-Fingerprint.** Was ein Ergebnis bestimmt (Modell, Digest,
Optionen, Fenster), steht in der Kennung im Stamp des Modellschritts; ein Teillauf (`--limit`, oder
Eingaben, die ohne Abweisung scheiterten) steht dort als `open` und macht den Schritt nicht aktuell
(„offen: n Eingaben"). Der Rest ist Ort und Laufzeit. Im globalen Fingerprint ließ jede Änderung an
`[ml]`, auch ein `--limit`, alle Schritte neu laufen, auch die ohne Modell, und der Merge von F5
hätte die ganze Kette einmal neu gerechnet; so ändert F5 den Fingerprint nicht. `--limit` ohne
`--models` und ein negatives `--limit` sind Bedienfehler.

**Was das Review vom 2026-11-23 geändert hat.** Elf Befunde mit Proben des Reviewers, je ein
Commit: das Fenster des Einbetters in Schlüssel und Kennung (vorher kam ein Vektor mit 64 Token aus
dem Cache eines mit 512); abgeschnittene Antworten markiert statt als vollständig gecacht (`Reply`,
Spalte `truncated`, Schema 2); `[ml]` aus dem Fingerprint und Teilläufe als offen; ein Lese-Timeout
nicht wiederholt; ohne Server eine Probe je Prozess, ein Schritt
„fehlgeschlagen" statt eines abgebrochenen Laufs, „unbekannt" in `status`, `--dry-run` plant
weiter; `SQLITE_BUSY` beim gleichzeitigen ersten Öffnen wiederholt; ein abgewiesener Text scheitert
allein, und der Lauf geht weiter (zehn in Folge brechen ab); `ml status` liest den Cache nur;
`--limit` geprüft; Doku; und der Server muss auf diesem Rechner laufen (`is_loopback_url`, sonst
`ml.allow_remote = true`), die Session liest keine Proxys aus der Umgebung.

**Die dritte Runde: abgewiesen ist erledigt, gescheitert ist offen.** Die Nachprüfung fand, dass ab
zehn dauerhaft abgewiesenen Eingaben jeder weitere Lauf an „zehn Fehlschläge in Folge" scheiterte:
im nächsten Lauf standen genau sie als einzige fehlende hintereinander. Ein realistischer Auslöser
ist `ml.embedding.truncate = false`. Darum unterscheidet der Stapellauf jetzt zwei Arten und merkt
sich beide mit Grund in der Tabelle `failures` des Modellcaches (Schema 3):

- **abgewiesen** (`ModelRejectedError`, 400, 413 oder 422): das Modell nimmt diese Eingabe so nicht.
  Eine zweite Frage gäbe dieselbe Antwort. Spätere Läufe überspringen sie, sie zählen nicht in die
  Fehlschläge in Folge, und im Stamp stehen sie als `rejected`, **nicht** als `open`: der Schritt
  ist aktuell und sagt „aktuell, n Eingaben abgewiesen" (auch in `georep status`). Wer sie erneut
  fragen will, etwa nach einem größeren Fenster, setzt `ml.retry_rejected` (`--retry-rejected`);
  dann gilt der Schritt als offen. Verworfen: abgewiesene als `open` zählen. Dann wäre der Schritt
  nie aktuell, jeder Lauf fragte sie erneut und endete mit Exit 1, obwohl nichts mehr zu tun ist.
- **gescheitert** (jeder andere `ModelError`: Lese-Timeout, 408, 409, 425, 429 und 5xx nach den
  Wiederholungen, unbrauchbare Antwort): vielleicht vorübergehend. Er bleibt offen (`open`, `failed`), und spätere
  Läufe fragen ihn erneut, aber hinter allem Neuen, damit er nicht bei jedem Lauf zuerst `limit`
  verbraucht.

Ein Lese-Timeout ist seitdem kein `ModelUnreachableError` mehr: die Probe hatte den Server erreicht,
nur dieser Text dauerte zu lange. `ModelUnreachableError` heißt nur noch „Verbindung abgelehnt" und
bricht den Lauf ab. `ModelUse.record` summiert die Stapelläufe eines Schritts, `run_step` setzt vor
jedem Lauf zurück; vorher meldete ein Schritt mit zwei Stapelläufen nach dem zweiten „aktuell",
obwohl Eingaben des ersten fehlten. `CacheStat` nennt die Datei, aus der es zählt.

**Die vierte Runde: wann ein Lauf anhält.** Zehn Fehlschläge in Folge hielten jeden Lauf an, sobald
zehn bekannte Fehlschläge ans Ende sortiert hintereinander standen, und die Ausnahme kam, bevor der
Schritt seine Ausgabe schrieb: neue Dokumente lagen im Cache, nicht in der Ausgabe. Seitdem:

- In die Serie zählen nur Eingaben, die in diesem Lauf zum ersten Mal scheitern.
- Zehn davon in Folge halten den Stapellauf an, **ohne Ausnahme**: der laufende Stapel wird noch
  gespeichert, der Rest bleibt offen (`BatchReport.stopped`). Der Schritt schreibt, was er hat, sein
  Stamp nennt den Rest offen, und `run_step` meldet ihn trotzdem „fehlgeschlagen" (Exit 1), damit
  ein systematischer Fehler sichtbar bleibt. Verworfen: der Abbruch vor dem Rechnen (zehn
  Fehlschläge sieht man erst, wenn sie da sind) und die Ausnahme (die Ausgabe hinkte dem Cache
  hinterher, und jeder Lauf endete gleich).
- Die Abweisungen der Serie, die den Lauf anhielt, gelten als „gescheitert": zehn Abweisungen in
  Folge kommen eher von einer falschen Anfrage (einer Option außerhalb des Schlüssels) als von zehn
  schlechten Texten, und dauerhaft gemerkt blieben sie nach dem Berichtigen liegen.
- Abweisung heißt nur noch 400, 413, 422; 408, 409, 425 sind vorübergehend wie 429; 401 und 403 sind
  Konfiguration und brechen den Lauf ab, ohne etwas zu merken (`ModelUnreachableError`).
- `retry_rejected` steckt in der `ModelUse`; `run_step` setzt es aus den Settings. Vorher war es ein
  Parameter der Stapelläufe, und ein Schritt nach dem Gerüst gab ihn nicht weiter.

**Cache: SQLite je Modell, nicht Parquet-Scherben.** Ein Eintrag ist (Digest, Prompt-Version,
SHA-256 der Eingabe) → Wert, und die Eingabe ist, was das Modell sieht. Gemessen am 2026-11-23 auf
xtraspace, unter Fremdlast (Lastmittel um 90): 50 000 Einbettungen zu 3 KB in Stapeln zu 32
schreiben 9,0 s, alle Schlüssel lesen 50 ms, alle Werte 1,6 s, die Datei hat 214 MB; 50 000 Texte zu
512 B mit je einer Transaktion kosten 0,22 ms je Eintrag, gegen Sekunden je Antwort des Modells.
Mit `WITHOUT ROWID` lagen die Werte im Schlüsselbaum, und dieselben Lesungen kosteten 708 ms und
4,6 s; darum eine Rowid-Tabelle mit eigenem Schlüsselindex. Parquet-Scherben hätten je Stapel eine
Datei bedeutet (1 600 bei 50 000 Einträgen) oder ein Umschreiben, beim Nachschlagen das Lesen
aller Scherben und beim Lesen das Entfernen von Dubletten; SQLite gibt mit der Standardbibliothek
eine Transaktion je Stapel (atomar, nach einem Abbruch fortsetzbar), Nachschlagen über den
Primärschlüssel und parallele Leser (WAL). Parquet bleibt das Format der Ausgaben und Pakete: ein
Schritt liest aus dem Cache und schreibt seine Tabelle. Eine Datei je Modell, damit `georep ml status`
die Größe je Modell ohne Abfrage kennt und ein ausgedientes Modell mit einer Datei verschwindet.

**Was F5 nicht entscheidet.** Welche Texte ein Vorhaben einbettet (Rohtext aus F1, Abschnitte aus
11, Zerteilung bei mehr als 512 Token), welche Prompts es schreibt und mit welcher Version, und ob
ein Ergebnis ins Repo darf (Kurzfassungen nicht, Plan § 10, Frage 6).

## 73. Der Rohtext bekommt einen zweiten Store; der Textstore bleibt, wie die Arbeit ihn verlangt (Fundament F1, 2026-11-23)

Der Textstore (`cache_root/<profil>/text/texts.parquet`) hält den Text so, wie die Arbeit ihn las:
kleingeschrieben, ohne Zeilenumbrüche, erst ab dem Marker (`search.text_split_marker`). Das bleibt
so, denn die Suche und jede Zahl der Seite hängen daran. Abschnitte, Beträge, Kopfdaten und
Kurzfassungen (Vorhaben 11, 12, 18 und 20 aus `docs/plan-vorverarbeitung-2026-11.md`) brauchen
aber Groß- und Kleinschreibung, Zeilen, Seiten und gerade den Vorlagenkopf, den der Marker
abschneidet. Darum kommt ein zweiter Store dazu, kein Umbau des ersten.

**Was gebaut ist.**

- `cache_root/<profil>/text/rohtexte.parquet` (`Layout.raw_texts`, `stores.RawTextStore`,
  Schema-Version 2) mit den Spalten `name`, `text`, `pages`, `chars`, `extractor`, `pdf_sha256` und
  `form_feeds`; zwischen zwei Seiten steht ein `\f` (`stores.PAGE_BREAK`). Der Extraktor ist
  derselbe wie im Textstore (`pypdf==7.1.0`, Punkt 67) und heißt hier `pypdf-7.1.0+roh`, damit
  niemand die beiden Stores verwechselt, ohne es an einer Zeile zu merken. Eine Datei mit anderer
  Schema-Version liest der Store als leer, und der Schritt liest dann jedes PDF neu.
- Der Schritt `raw_texts` steht direkt nach `texts`, mit `RAW_TEXT_SCHEMA_VERSION` und Stamp.
  `prep.raw_texts.extract_raw_missing` folgt `extract_missing` Zeile für Zeile: neu gelesen wird nur
  bei anderem PDF-Hash oder Extraktor, `CorruptPdfError` zählt als fehlerhaft, ein alter Text bleibt
  stehen. Ohne PDFs (CI, GitHub Pages) schreibt der Schritt einen leeren Store oder lässt den stehen,
  den `bootstrap` aus einem Paket gelegt hat. `PypdfExtractor.pages` liefert die Seiten, `extract`
  verbindet dieselbe Liste mit `\n` (ein eigenes Refactoring vorab, Textstore bytegleich).
  `georep fetch` nimmt den Schritt mit, wie `texts`, weil beide die gerade geholten PDFs lesen.
- `georep pack --raw-texts` packt den Store eines Profils. Es prüft die Brücke zum Textstore (je
  Name derselbe PDF-Hash, Extraktor des Textstores mit `+roh`) und schreibt den Store mit zstd auf
  Stufe 19 neu statt ihn zu kopieren (16,8 % kleiner als die Vorgabe von Polars, 24 s einmal beim
  Packen). `[bootstrap].raw_texts` legt das Paket beim Bootstrap an. Gepackt ist nur die
  Hauptperiode: `snapshots/duesseldorf-rohtexte/`, 14 183 802 Bytes (13,5 MiB; alle Pakete
  zusammen 166,49 MiB). Konrad hat Rohtextpakete im Repo freigegeben
  (`docs/plan-vorverarbeitung-2026-11.md`, § 10, Frage 6); ob weitere kommen, entscheidet er
  (Frage 18). Die Seite zeigt keinen Rohtext.
- Anders als ein Textpaket (Punkt 68) muss ein Rohtextpaket nicht jede Hauptdatei tragen: das
  AES-verschlüsselte `00403713.pdf` hat keinen Rohtext, weil `cryptography` nicht im Lock steht,
  und der Textstore führt dafür weiter den Text der Arbeit. `bootstrap` verlangt darum nur, dass
  jeder Name eine Hauptdatei des Datensatzes ist und das Paket die aktuelle Schema-Version trägt;
  die Mini-Fixture, die mit den Settings der Hauptperiode bootstrappt, lehnt das Paket damit weiter
  ab. Ein Store am Ziel, der leer ist oder eine alte Version trägt, zählt wie ein fehlender: sonst
  käme das Paket nach einem Lauf ohne PDFs ohne `--force` nie mehr an. Ein halber Store (ein
  eigener Lauf über einen Teil der PDFs, etwa nach `fetch pdfs --limit N`) wird nicht ersetzt,
  sondern um die fehlenden Namen ergänzt, über dieselbe Brücke wie beim Packen (gleicher
  PDF-Hash, Extraktor des Textstores mit `+roh`); die eigenen Zeilen bleiben.
- Der Schlüssel `raw_texts` steht im Block `[bootstrap]` von `defaults.toml` neben `texts` und nicht
  in einem eigenen Block am Ende: TOML erlaubt eine Tabelle nur einmal. `bootstrap` liegt außerhalb
  des Settings-Fingerprints, ein Merge rechnet darum nichts neu. Ein Schalter für den Schritt fehlt
  mit Absicht: er ist ein Kernschritt, und ohne PDFs kostet er nichts.
- „Methode und Grenzen" nennt jetzt aus dem Modell, womit die Texte gelesen sind und wie viele aus
  der Arbeit stammen (`docs/todo.md`, Punkt 7, damit erledigt), und den Rohtext in einem Satz --
  aber nur, wenn der Rohtextstore vollständig ist: aktuelle Schema-Version, ein Extraktor, und
  jeder Text, den derselbe Extraktor gelesen hat, hat seinen Rohtext zu demselben PDF-Hash
  (`complete_raw_texts`; gezählt werden diese Texte, nicht die Zeilen des Rohtextstores). Dann
  stimmt der Satz auf jedem Rechner, der ihn zeigt; rechnerabhängig bleibt nur, ob er erscheint
  (eine Periode ohne Paket zeigt ihn lokal mit PDFs, auf Pages nicht). Keine Zahl der Seite ändert
  sich. Der Rohtextstore ist eine **optionale** Eingabe von `report` (`Step.optional`): ihr Hash
  steht im Stamp, eine fehlende als `fehlt`, und ihr Fehlen bricht nichts ab -- als harte Eingabe
  brach `georep run report` auf jeder Datenwurzel von vor F1 ab.

**Die Eigenschaft, an der der Store hängt.** Der Rohtext eines Dokuments, geplättet
(`prep.raw_texts.flatten`: `\f` zu `\n`, die `\f` aus dem Text einer Seite an den Offsets in
`form_feeds` zurück, dann `normalise_text`, dann `after_marker`), ist **genau** der Text des
Textstores, für jedes Dokument und ohne Ausnahme. Nur dann ist eine Stelle, die ein späteres
Vorhaben im Rohtext findet, die Stelle, die die Suche zählt. Geprüft ist das dreifach: als
hypothesis-Eigenschaft über Zufallsseiten, auch solche mit eigenen `\f`, gegen den Text, wie
`extract_missing` ihn aus denselben Seiten bildet (`tests/property/test_raw_text_props.py`, auch
über beide Schritte mit einem Fake-Extraktor), an den vier Fixture-PDFs und als `slow`-Test über die
beiden Pakete der Hauptperiode (`tests/unit/test_data_packages.py`: 0 Abweichungen, derselbe
PDF-Hash je Name). Ergebnis über die Hauptperiode: **19 091 von 19 091 Rohtexten**; ohne Rohtext ist
allein `00403713.pdf`, dessen Text der Arbeit der Textstore behält. In Mönchengladbach (658) und der
laufenden Periode (4 088) gibt es ebenfalls keine Abweichung, in 2014 bis 2020 keine unter den
22 101 Rohtexten (geprüft am 2026-11-23 mit einem Messskript gegen die Stores im Cache; die acht
PDFs mit eigenen `\f` dort einzeln mit dem neuen Format); ohne Rohtext sind dort die 15 PDFs, die
pypdf seit 6.21 an einer Schutzgrenze abweist und deren Text aus 6.20.0 der Textstore behält
(Punkt 66). Gegen die Messdatei, die der Supervisor in Phase 0 eigens extrahiert hat
(`messdaten/rohtext/<profil>.parquet`, Seiten ebenfalls mit `\f` verbunden), sind in allen vier
Datensätzen alle Rohtexte zeichengleich, bis auf neun Dateien, die sich nur an den Stellen der
Formfeeds unterscheiden (dort `\f`, hier das Ersatzzeichen).

**Formfeeds im Text einer Seite.** Eine Seite kann selbst ein `\f` tragen: in `00532917.pdf`
liefert eine defekte Schriftkodierung Steuerzeichen statt Buchstaben, darunter 41 Formfeeds (in
2014 bis 2020 acht weitere PDFs mit 2 bis 525, in allen neun Fällen Zeichensalat). Stünden sie im
Rohtext, hieße `\f` nicht mehr „Seitenwechsel", und wer die Seiten von `00532917.pdf` zählt, zählte
44 statt drei. Im Rohtext steht dort darum ein Leerzeichen (`stores.PAGE_BREAK_STANDIN`), und die
Spalte `form_feeds` nennt die Offsets; jede Seite behält ihre Länge, und `flatten` setzt die `\f`
zurück, bevor es normalisiert und schneidet. Die erste Fassung (Schema-Version 1) ließ die Offsets
weg und nahm die Abweichung an diesen Stellen hin; der Review vom 2026-11-23 fand dazu einen Marker,
den das Leerzeichen erst erzeugt („a\fb" wird „a b"), und die Entscheidung war: die Plättung bleibt
genau. Darum ist `form_feeds` ein Pflichtargument von `flatten(raw, marker, form_feeds)`: eine
Vorgabe `()` plättete einen Aufruf ohne Offsets still wie Version 1 (Review, dritte Runde); aus dem
Store kommen sie mit `RawTextStore.form_feeds(name)`.

**Laufzeit** des Schritts beim ersten Lauf je Profil, seriell wie `texts`, am 2026-11-23 unter
starker Fremdlast (Lastmittel bis 144 auf 16 Kernen), mit `nice -n 10`, in Schema-Version 1; die
Hauptperiode in Version 2 danach mit weniger Last:

| Profil | PDFs | gelesen | Seiten | Sekunden | Store im Cache |
|---|---|---|---|---|---|
| Hauptperiode, Version 2 | 19 092 | 19 091 (1 fehlerhaft) | 39 965 | 827,8 | 17 045 208 Bytes |
| Hauptperiode, Version 1 | 19 092 | 19 091 (1 fehlerhaft) | 39 965 | 1 178,1 | 17 044 606 Bytes |
| 2014 bis 2020 | 22 116 | 22 101 (15 fehlerhaft, 26 Namen ohne PDF) | 50 861 | 1 817,2 | 21 809 955 Bytes |
| laufende Periode | 4 088 | 4 088 | 8 265 | 152,3 | 3 311 563 Bytes |
| Mönchengladbach | 658 | 658 (2 213 ohne PDF) | 2 485 | 52,5 | 1 079 714 Bytes |

Der Textstore der Hauptperiode brauchte am 2026-11-18 ohne Fremdlast 628,5 s für dieselben PDFs. Dass
die längere Zeit die Last ist und nicht der Schritt, zeigt eine gepaarte Messung an 200 PDFs der
Hauptperiode, beide Schritte abwechselnd in je drei Runden: im Minimum 12,7 s für den Textstore und
12,9 s für den Rohtext; die übrigen Runden streuen unter der Last zwischen 14 und 76 s. Beide lesen je
Seite dasselbe `extract_text`. Danach ist der Schritt aktuell und kostet nur die SHA-256 der PDFs.
Die Stores der drei anderen Profile im Cache tragen noch Version 1; ihr nächster Lauf liest sie neu.

Verworfen: den Textstore umbauen, sodass er Zeilen und Großschreibung behält (änderte jede Zahl der
Seite und die Treue zur Arbeit); den Textstore aus dem Rohtext ableiten, statt jedes PDF zweimal zu
lesen (halbierte die Laufzeit, ändert aber Schritt und Stamp des Textstores, der bytegleich bleiben
soll; ein eigener Schritt für später, wenn sich die doppelte Laufzeit lohnt); die Seiten als Liste
(`List(String)`) statt mit `\f` (die Eigenschaft wäre dieselbe, aber jede Textsuche über das ganze
Dokument müsste die Liste erst verbinden, und `\f` ist die Konvention von `pdftotext`); ein `\f`
im Seitentext stehen lassen, wie die Messdatei aus Phase 0 es tut (die Seitenzahl ließe sich dann
aus dem Text nicht mehr ablesen); das Ersatzzeichen ohne Offsets (Version 1: neun Dokumente wichen
ab, siehe oben); dieselbe Bedingung wie beim Textpaket, gleiche Namensmenge (das Paket der
Hauptperiode wäre wegen des einen verschlüsselten PDFs abgelehnt); ein paralleler Extraktor (die
Polars-Threads blockieren nach einem `fork`, `docs/mutation-2026-10-11.md`; seriell wie `texts`);
der Rohtextstore als harte Eingabe von `report` (brach ohne ihn ab) und als Eingabe nur, wenn er
beim Bauen des Registers existiert (legt `raw_texts` ihn im selben Lauf an, fehlte er im Stamp, und
der zweite Lauf rechnete die Seite neu); der Satz über den Rohtext mit der bloßen Zeilenzahl (stand
auch bei einem halben Store); die Schema-Version des Textstores beim Laden prüfen wie hier (dasselbe
Muster, aber ein eigener Eingriff in einen Store, an dem jede Zahl hängt; notiert, nicht gebaut).

## 74. Fundament-Nachzug F7: frühe Beiträge, `http` an den Beiträgen, Zusatzspalten an Spannen, Stelle im Rohtext je Zeichen (2026-11-23)

Die Synergien der Stufe 1 (`docs/plans/00-synergien-2026-11.md`, § 2.2, Konflikte 1, 3, 6 und 7;
§ 3.1, Punkt 2) fanden vier Stellen, an denen F1 bis F3 (Punkte 69 und 73) für Stufe 2 nicht
reichten. Alle vier sind vor dem ersten Merge einer Stufe 2 nachgezogen, ohne dass sich eine Zahl
der Seite bewegt.

**Frühe Beiträge (Konflikt 6).** Die Schritte eines Beitrags standen nur unmittelbar vor `report`,
also hinter `weights`. Vorhaben 16 (`places`) erweitert `document_weights` um einen Faktor und
braucht dafür die Abschnitte von 11 (`sections`); 13 (`families`) plant eine Variante. `weights`
liefe dann vor der Ausgabe, die es liest. `Contribution.early_steps` ist eine zweite Fabrik mit
derselben Signatur wie `steps`; `build_steps` setzt ihre Schritte unmittelbar vor `weights`, hinter
`index`, `results`, `metrics` und `body_hits`, sodass ein früher Schritt alles lesen kann, was der
Kern vor `weights` schreibt. `check_unique_names` prüft wie bisher die ganze Liste, früh, spät und
Kern. Das Feld steht am Ende der Dataclass, damit kein Aufruf mit Positionen seine Bedeutung ändert.
Dass ein früher Schritt keine Ausgabe eines späten liest, stand zuerst nur im Docstring; seit dem
Review (2026-11-24, M1) prüft es `check_step_order` am Ende von `build_steps` für jeden Schritt:
`StepOrderError`, wenn er eine Eingabe oder eine optionale Eingabe liest, die erst ein späterer
schreibt, und `DuplicateOutputError`, wenn zwei Schritte dieselbe Datei schreiben. Der Kern erfüllt
beides in allen fünf Paketprofilen (ein Test je Profil).

*Warum ein zweites Feld und nicht `stage`.* Mit einem Feld `stage = "early" | "late"` landete ein
Beitrag ganz vorn oder ganz hinten; ein Vorhaben mit beiden Arten (ein Schritt, den `weights` liest,
und einer, der die Gewichte oder die Urheber aus `parties` liest) bräuchte dann zwei Beiträge, gegen
die Regel „ein Beitrag je Vorhaben, mit allen Schritten" (§ 2.1 der Synergien). Ein Feld je Schritt
hätte `Step` geändert, an dem gerade andere Branches Felder anhängen (Punkt 69, „Verworfen"). Zwei
Fabriken halten beides: ein Eintrag im Register, und die Stelle steht am Namen des Felds.

**`http` an den Beiträgen (Konflikt 7).** `Contribution.steps` bekam `(settings, layout)`; ein
Netzschritt eines Vorhabens (22 `need_data`) hätte eine eigene Session bauen müssen und wäre ohne
Fake-Session nicht testbar (CLAUDE.md, „Nie"). Jetzt bekommen beide Fabriken `(settings, layout,
http)`. `build_steps` reicht die übergebene Session durch; ohne Angabe ein `http.DeferredTransport`,
der die gecachte Session erst beim ersten `get` oder `post` über dieselbe Fabrik holt wie die
Netzschritte des Kerns. So legt `georep steps` oder ein Lauf ohne `--online` weiter kein
`http.sqlite` an (Test `test_ohne_netzschritt_entsteht_keine_session`).

**Zusatzspalten an Spannen (Konflikt 3, Entscheidung des Supervisors).** `check_spans` prüft die
acht Spalten von `SPAN_SCHEMA` vorn, in Folge und mit ihren Typen, Nullwerte nur dort; Spalten
dahinter gehören dem Vorhaben (12: `attr`) und sind frei, auch leer. `sort_spans` stellt sie in
ihrer Folge hinter die acht und ordnet die Zeilen wie ohne sie (hypothesis,
`tests/property/test_spans.py`). Die Grenzprüfung rechnet nur über die acht, damit eine Zusatzspalte
auch `zeile` oder `length` heißen darf. Die Kodieraufträge von F4 lesen weiter nur `start`, `end`,
`kind` und den Text; eine Zusatzspalte erreicht die Kodierer nicht. Verworfen: `attr` in einer
Nebentabelle (ein Join mehr für jeden Leser, ohne dass F3 einfacher würde). Nach dem Review
(2026-11-24): der Kopf wird als Liste verglichen, nicht als dict, sonst bestanden acht vertauschte
Spalten die Schemaprüfung (K1); `sort_spans` sortiert bei Gleichstand von `id, start, end, kind`
nach den übrigen vier, damit zwei Spannen an derselben Stelle, etwa aus zwei Extraktoren, nicht in
der Folge der Eingabe stehen (N2, hypothesis über vertauschte Zeilen); `empty_spans(extra)` legt
die Zusatzspalten leer an, damit ein Vorhaben ohne Treffer dasselbe Schema schreibt wie mit (N3).

**Stelle im Rohtext je Zeichen (Konflikt 1).** `prep.raw_texts.flatten_with_offsets(raw, marker,
form_feeds) -> (text, offsets)`: `text` ist genau `flatten(...)`, `offsets[i]` der Index im Rohtext
des Zeichens, aus dem Zeichen `i` entstand. Gleich lang und aufsteigend; zwei gleiche nebeneinander
nur, wo ein Zeichen klein zu mehreren wird (`"İ".lower()`), und ein `\f` aus dem Text einer Seite
zeigt auf seinen Offset aus `form_feeds`. Eine Spanne `[i, j)` im Textstore ist im Rohtext
`[offsets[i], offsets[j - 1] + 1)`. Damit können 14 und 17 ihre Spannen auf den Rohtext schreiben,
wo die Abschnitte von 11 liegen, und 16 kann sie statt seines Nachbaus `store_view` nehmen. Die
Offsets entstehen je Zeile als `range`, nicht je Zeichen; die Verträge prüfen Gleichheit mit
`flatten`, Länge und Folge (`sorted` statt einer Schleife, weil sie je Dokument laufen), crosshair
einzeln mit Exit 0 nach 44 s („Not confirmed"), das Ziel steht in `VERIFY_TARGETS`.

Geprüft als hypothesis-Eigenschaft über Zufallsseiten, auch mit eigenen `\f`, İ und Σ: der Text ist
der von `flatten`, und jedes Zeichen ist die Kleinschreibung des Rohtextzeichens an seiner Stelle
(die einzige Kontextregel von `str.lower` ist das Schluss-Sigma). Über die Hauptperiode als
`slow`-Test aus dem Paket: 19 091 von 19 091 Rohtexten ohne Abweichung, kein Zeichen falsch
verortet, die 41 inneren `\f` von `00532917.pdf` auf genau ihren gespeicherten Offsets (6,6 s).
Gegen die Stores im Cache (Messskript, nur lesend, 2026-11-24, alle vier in Schema-Version 2):
2014 bis 2020 22 101, Mönchengladbach 658 und die laufende Periode 4 088 Rohtexte ohne Abweichung,
kein Zeichen falsch verortet, und in den acht PDFs mit eigenen `\f` in 2014 bis 2020 (2 bis 525)
zeigt jedes auf seinen gespeicherten Offset. Eine erste Messung am 2026-11-23 traf den Store von
2014 bis 2020 noch in Version 1 ohne `form_feeds` und fand dort genau diese acht abweichend, wie
`flatten` auf demselben Store.

**Geprüft, dass die Seite gleich bleibt.** A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt 66
(Skripte `ab/ab_bau.sh`, `ab/ab_vergleich.py` auf xtraspace), vor dem Nachzug (`main`, `444a611`)
und danach, je in eigener Datenwurzel: die fünf Profile mit `bootstrap` und `run`, dann `publish
--strict-budget`. Unter `site/` 194 Dateien in beiden, 0 Abweichungen (Parquet als Frame, JSON ohne
`generated_at`, HTML ohne „Erzeugt am“ und Prüfsummen). Über die ganzen Datenwurzeln 677 Dateien in
beiden; abweichend sind nur 71 Stamps, und an ihnen allein die Zeit `written`. `CONTRIBUTIONS` ist
leer; ändern kann sich erst etwas, wenn ein Vorhaben einträgt.

**Verworfen.** `weights` hinter die Beiträge schieben (verschiebt den Kern, Konflikt 6 der
Synergien); eine eigene Gewichtstabelle für 16 (dann liest `report/model.py` sie, genau die Stelle,
die F2 schützen soll); `stage` statt einer zweiten Fabrik (oben); eine Session, die `build_steps`
immer baut (legte `http.sqlite` in jedem Lauf an, auch ohne Netz); eine Prüfung je Zeichen als
Vertrag von `flatten_with_offsets` (rund 55 Millionen Zeichen in der Hauptperiode, je Lauf; sie
steht in den Tests).

## 75. Funktion und Antragsteller je Dokument: Variante B, drei Quellen für die Antragsteller, Ratsmehrheiten stadtweit je Wahlperiode des Rates (Vorhaben 15, 2026-11-24)

Vorhaben 15 der Vorverarbeitung (`docs/plans/15-funktion.md`, § 5 bis § 7 und § 10), Stufe 2. Die
Messung hat das Regelwerk gegen zwei KI-Kodierer an 150 Dokumenten geprüft: κ = 0,905 für
Variante B (Bootstrap-95-% 0,840–0,960), 0,829 für Variante A, Antragsteller mit Präzision 119/119
und Recall 119/138. Gebaut ist genau dieses Regelwerk, als erster Beitrag nach Punkt 69; die
Fabrik der Schritte hat die Signatur aus Punkt 74 (`settings, layout, http`), beide Schritte sind
offline und fragen den Transport nie, und beide bestehen `check_step_order` in jedem Paketprofil.

**Was gebaut ist.** Der Beitrag `15-funktion` (`georep.enrich.functions`) bringt zwei
Offline-Schritte hinter `bodies` und `parties`, nur mit `functions.enabled` (in beiden
Stadtprofilen an) und mit Urhebern im Profil:

- `functions` schreibt `processed/dokumente_funktion.parquet`: je Korpus-ID `funktion` (Kontrolle,
  Information, Initiative, Symbol, Vollzug oder `rest`, auf der Seite „Funktion nicht erkannt"),
  `instrument`, `quelle` (`art`, `titel`, `text`, leer genau bei `rest`) und `variante`. Die Regeln
  stehen rein in `analysis/functions.py`: Dokumentart als ganzer Wert, dann ihr Präfix; die
  Sammelarten einer alten Vorlagenform über Titel und Textkopf; Symbolpolitik aus dem Titel nur für
  Initiativen aus der Politik; Variante B liest den Beschlusstext eines Antrags (Erklärung →
  Symbol, Berichtswunsch → Kontrolle). Variante A bleibt als Schalter.
- `cosponsors` schreibt `processed/dokumente_antragsteller.parquet` (nach der Konvention
  `dokumente_<attribut>`, nicht `mitantraege`): je Korpus-ID `antragsteller`, `fraktionen`, `quelle`,
  `gemeinsam` und `lager`, rein in `analysis/cosponsors.py`.
- Beide Tabellen haben eine Zeile je Korpus-ID (`one_row_per_document`) und ihre Schema-Version aus
  der Konstante des Moduls; `functions_files(layout)` nennt die Pfade für 14, 24 und 28.
- `analysis/practice.observed_expected` rechnet beobachtet gegen erwartet gegen die Praxis der
  Schichten (indirekte Standardisierung, Schicht Gremium und Periode), ohne Settings; 15 nimmt sie
  für die Kontrolle je Fraktion, 14 in Stufe 3 für die Antworten je Fraktion.

Gegen das Messskript Dokument für Dokument auf den Läufen vom 2026-11-23: Funktion (beide
Varianten) und Antragsteller in **0 von 48 313 Dokumenten** verschieden (vier Datensätze). Ein
slow-Test rechnet κ, die Treffer und die Präzision der Fraktionen aus
`validierung/15-funktion/labels.csv` nach; ein Umbau, der sie senkt, ist kein Refactoring.

**Antragsteller aus drei Quellen, nicht aus `parteien`.** Option 04 nimmt die erste Quelle mit
Treffer und übersieht bei 281 Dokumenten Mitantragsteller. Die Antragsteller sind die Vereinigung
aus der Dokumentart hinter dem Antragspräfix (`originators.motion_prefixes`, wie die Synergie
verlangt), dem Autorenteil des Titels (vom ersten Instrumentwort bis zum ersten Trenner) und dem
Verfasserblock des Briefkopfs der alten Vorlagenform; nennt keiner eine Partei, bleibt `parteien`.
`analysis/parties.py` ist unverändert; ob Option 04 nachzieht und damit „Dokumente je Partei" auf
`index.html` ändert, ist Frage 25 an Konrad.

**Fraktionen mit Zeitraum.** `[[functions.fractions]]` fasst Parteischlüssel zu einer Fraktion,
solange sie besteht: in Düsseldorf SPD+VOLT ab 2020-11-01 und T_FW+PARTEI ab 2025-11-01, in
Mönchengladbach „FDP / VOLT" und „DIE LINKE / DIE PARTEI", wie `raw/organizations.json` sie nennt,
erst ab dem 2025-11-01: sie gehören zum Rat ab 2025, im Datensatz 2020 bis 2025 steht „volt" in
keinem Text, und die Briefköpfe von 2024 und 2025 nennen Linke und PARTEI getrennt (Review
2026-11-24). In diesem Datensatz ändern die beiden Zeilen also kein Dokument, auch keines der 70
gemeinsamen. Eine Partei gehört an keinem Tag zu zwei Fraktionen; das prüft der Validator.

**Ein stadtweiter Mehrheitenblock, je Wahlperiode des Rates.** `[majorities]` steht im Stadtprofil,
weder unter `[functions]` noch unter `[council]` (Synergien 2026-11, § 1): je Zeile Wahlperiode,
Parteien, Gültigkeit, die Vereinbarung aus Vorhaben 25 mit Datum, so genau die Quelle es sagt, und
Drucksachen, die die Mehrheit im Korpus nennen. `body_kinds` sagt, wo die Mehrheit des Rates gilt
(Rat und Ausschüsse); in den Bezirksvertretungen ist das Lager `ohne_lager`, dort gibt es keine
Konkordanz zu messen, bis Vorhaben 27 deren Mehrheiten kennt. **Anders als die Messung** gilt eine
Mehrheit nicht für einen Datensatz, sondern für die Wahlperiode des Rates, die am 1. November nach
der Wahl beginnt (an diesem Tag beginnen die Ratsfraktion SPD/Volt und die Ratsgruppe der laufenden
Periode, das Einzelmandat der AfD und die Gruppe T_FW enden am 31. Oktober davor). Die 437
Dokumente der Hauptperiode vor dem 2020-11-01 stammen vom alten Rat, seine Mehrheit war die Ampel,
und ein Antrag der SPD vom Oktober 2020 ist ein Antrag der Mehrheit. K3 der Hauptperiode (Variante
B) wird dadurch **41 / 1 333 statt 43 / 1 336**; 2014 bis 2020 (49 / 653) und ab 2025 (0 / 312)
bleiben, die gemeinsamen Dokumente (1 397, 1 202, 204) auch. Wer die Mehrheit je Datensatz will,
setzt die Grenzen auf die Profile; das Ergebnis ist dann wieder das der Messung (nachgerechnet).

**Das Lager eines Dokuments ohne Fraktion** heißt `ohne_partei`, auch bei einer Vorlage der
Verwaltung: die sieben Klassen des Bauplans bleiben, und wer K1 bis K3 rechnet, filtert ohnehin auf
die Urheberklasse Fraktion. `ohne_lager` steht genau dort, wo das Gremium nicht auf der Stadtebene
liegt oder das Profil keine Mehrheit für das Datum kennt (Mönchengladbach überall).

**Die Wörter der Ratssprache stehen in `defaults.toml`**, nicht in beiden Stadtprofilen, abweichend
von § 6 des Bauplans: Symbol, Antrag, Anfrage, Änderungs-, Haushalts-, Prüf- und Berichtsantrag, die
Instrumente des Vollzugs, der Autorenteil des Titels und der Beschlusstext der Variante B greifen in
Mönchengladbach ohne Änderung (§ 3.3); doppelt stünden rund zwanzig gleiche Zeilen in zwei
Dateien, die auseinanderlaufen. Was nur eine Stadt kennt, steht im Stadtprofil: die
Dokumentarten als „funktion/instrument" (beim Laden gegen `FUNCTION_INSTRUMENTS` geprüft), die
Präfixe, die Sammelarten mit ihren Textregeln und dem Briefkopf, die Fraktionen, die Mehrheiten,
dazu zwei Wörter Düsseldorfs (der Schreibfehler „pürfantrag" der Quelle und der „60er-Beschluss"
nach § 60 GO NRW; Review 2026-11-24). Für sie wiederholt das Profil die Listen `review_title` und
`enforcement`, weil `deep_merge` Listen ersetzt; ein Test hält sie gleich der Vorgabe plus diesen
Wörtern. Der Supervisor hat die Abweichung abgenommen (Messdokument § 10, Punkt 10). Kein
Stadtwort im Code.

**Ein Befund am Messskript.** Beobachtet gegen erwartet ergibt für 2020 bis 2025 und ab 2025 die
Zahlen der Messung (CDU 0,74, AfD 1,75, Tierschutz/FW 1,67 …), für 2014 bis 2020 aber CDU 0,98
statt 0,99, SPD 0,78 statt 0,79, Tierschutz/FW 1,45 statt 1,53. Dort haben 105 Fraktionsdokumente
kein Gremium, und das Messskript gab ihnen beim Join ohne null-Schlüssel keine Erwartung, zählte
sie aber beobachtet mit; `observed_expected` führt sie als eigene Schicht. Das Muster aus § 3.7
(Tierschutz/FW und AfD fragen mehr, die Mehrheit weniger) bleibt.

**Verworfen.** `[[functions.majorities]]` (die Synergie macht den Block stadtweit, 24 und 28 lesen
ihn); die Mehrheit je Datensatz (die Messung; ein Antrag des alten Rates bekäme die Mehrheit des
neuen); Gültigkeit erst ab der Unterzeichnung der Vereinbarung (Januar 2021, Dezember 2025: die
Wahlperiode ist eine belegte Grenze; ob und ab wann die Partner vor der Unterzeichnung gemeinsam
handelten, ist nicht geprüft, und Wochen ohne Lager mitten in einer Periode wären die größere
Verzerrung); die Mehrheit aus den gemeinsamen Anträgen ableiten (für K3 zirkulär); eine
dritte Datei mit den Kanten des Netzes (eine Gruppierung über `dokumente_antragsteller`, die
Unterseite rechnet sie, Bauplan § 6); `parties.py` nachziehen (Frage 25); eine achte Lagerklasse
für Dokumente ohne Fraktion (der Bauplan hat sieben, und der Filter auf die Urheberklasse genügt);
`classify_function` und `cosponsors` in `VERIFY_TARGETS` (ihre Regeln tragen `re.Pattern`, dasselbe
Werkzeugartefakt wie bei `parse_reference`; geprüft wird `camp`, die übrigen über hypothesis).

## 76. Vorgänge: nur starke Kanten, ein Wald statt Komponenten, Antworten aus den Anlagen, Nachbarperioden aus ihren Paketen (Vorhaben 14, 2026-11-24)

Vorhaben 14 der Vorverarbeitung (`docs/plans/14-vorgaenge.md`, Stufe 2) verbindet Drucksachen, die
zusammengehören: Anfrage und Antwort, Antrag und Umsetzung, Vorlage und Änderungsantrag, Original
und Nachtrag, Bedarfs- und Ausführungsbeschluss. Gebaut ist ein Beitrag nach F2 (Punkt 69) mit
zwei Schritten hinter `procedures.enabled`: `references` schreibt jede Drucksachennummer im Text
als Spanne nach F3 (`processed/verweise.parquet`) und jede Kante, deren nennende Drucksache zum
eigenen Korpus gehört (`processed/vorgang_kanten.parquet`); `procedures` setzt daraus die Vorgänge
(`processed/dokumente_vorgang.parquet`, eine Zeile je Korpus-ID) und die Antworten auf Anfragen
(`processed/antwortzeiten.parquet`) zusammen. Die Rechnung liegt in `prep.references` (Nummern,
Fundstellen, Rollen, Typen) und `analysis.procedures` (Kanten, Wald, Antworten); Formen der Nummer,
Dokumentarten, Antwortanlagen und Pakete stehen im Stadtprofil.

**Nur starke Kanten zählen (Rückfallregel).** Die Regel war vorab festgelegt (Messdokument § 5.2,
Frage 9.16): verfehlt die Regelfassung .2 an einer frischen Stichprobe 0,95, gilt ohne weitere
Runde, dass eine Kante nur stark ist, wenn die nennende Drucksache die Nummer im Titel oder im
Namen einer Anlage trägt, ein Nachtrag über die Nummer ist oder ein Sammelbericht
(Beschlusskontrolle, Umsetzungsstand …). Fassung .2 kam an 100 Kanten auf 0,850; die Rückfallregel
an beiden Stichproben auf 104 von 106 (0,981, Wilson 0,934 bis 0,995), geprüft von zwei
KI-Kodierern desselben Modells, nicht von Menschen. Reine Textverweise bleiben als schwache Kanten
in den Daten (`stark = false`, `quelle = text`) und zählen nicht für Vorgang und Antwort. Die
Merkmale der Fassung .2 (Aufzählung, Verweiszeichen) sind nicht gebaut, die Typen .2 schon: unter
den Rückfall-Kanten waren die typisierten 89 von 89 dieselbe Sache.

**Ein Vorgang ist ein Baum, keine Zusammenhangskomponente.** Über alle Kanten hingen 4 619
Düsseldorfer Drucksachen in einer Komponente, weil Grundsatzbeschlüsse viele Folgen sammeln und ein
drittes Dokument zwei Vorgänge verschmilzt (§ 3.5). Jede Drucksache hängt darum am ältesten
Dokument, das sie über eine starke typisierte Kante nennt; die Wurzel ist der Vorgang. Ein
Sammelbericht (`kontrolle`) und ein bloßer `bezug` lassen keinen Vorgang wachsen. Neu gegen das
Messskript: ein Vorgänger vom selben Tag muss die kleinere ID haben. Dann fällt jede Kette in
(Datum, ID) streng, und ein Kreis ist unmöglich, statt dass ihn das Messskript still abbrach; auf
den Daten vom 2026-11-23 zeigt keiner der sieben Vorgänger vom selben Tag auf eine größere ID, und
die Zahlen bleiben dieselben. Ein Kreis wäre trotzdem ein `CycleError`, kein stilles Ende.

**Antworten kommen aus den Anlagen.** Die Antwort der Verwaltung auf eine Anfrage steht fast immer
als Anlage an der Anfrage selbst („Antwort der Verwaltung"), selten als eigene Drucksache (24 von
3 237 nach der Rückfallregel). Die Anlagen stehen weder im Korpus noch in einem Paket, nur in den
OParl-Objekten des HTTP-Caches; `georep pack --attachments` zieht sie in ein Paket je Stadt
(`snapshots/duesseldorf-anlagen/`, alle drei Perioden, 303 400 Bytes; `snapshots/moenchengladbach-anlagen/`,
63 910 Bytes), `bootstrap` kopiert es nach `raw/anlagen.parquet`. Eine Zeile je Drucksache mit dem
Abruftag und der Liste der Anlagen (Name, Datum): so ist eine Drucksache ohne Anlage (leere Liste)
von einer unbekannten (keine Zeile) zu trennen, und das Alter beim Abruf ist rechenbar. Ein
Anlagendatum vom Umstellungstag des Ratsinformationssystems (2019-07-03, 26 542 Anlagen) zählt als
Antwort ohne Datum. Personennamen hinter einer Anrede oder einem Titel ersetzt `pack` durch „…"
(Review 2026-11-24, Entscheidung des Supervisors; `procedures.person_titles`): 15 Anlagennamen in
Düsseldorf, einer in Mönchengladbach, keine Nummer und keine Antwort ändert sich dadurch, und was
das Paket noch an Personenbezug trägt, steht in seinem README. `praxis_gremium` steht an jeder Anfrage, weil „keine Antwort im Datensatz"
Praxis des Gremiums ist und nicht „unbeantwortet" heißt (§ 3.8: der Rat antwortet in der Sitzung,
0,2 % mit Anlage, BV 7 zu 93 %); eine rohe Antwortquote je Fraktion rechnet der Schritt nicht.

**Nachbarperioden aus ihren Paketen, und jedes Profil rechnet dieselbe Stadt.** 2 599 Düsseldorfer
Kanten gehen über eine Wahl, 254 davon stark; ein Vorgang endet nicht an der Periodengrenze. Jedes
Profil liest darum die Nummern, Titel und Dokumentarten seiner Nachbarperioden aus deren Paketen
(`[[procedures.related]]`: `raw/papers.jsonl` und Textstore; die Hauptperiode als Nachbar aus
`reference/raw/paper_objects.json`, dieselben 19 108 Paper mit denselben Feldern wie
`paper_with_text.json`, in einem Zehntel der Zeit), und ihre Hashes stehen im Stamp. Für den Wald
braucht ein Profil auch die starken Kanten der Nachbarn; nach der Rückfallregel hat die nur, wer eine
Nummer im Titel oder in einer Anlage trägt, ein Nachtrag oder ein Sammelbericht ist. Nur deren Texte
liest der Schritt `procedures` aus den Nachbarpaketen (`strong_candidates`), denn der Text
entscheidet über Felder und Änderungszeichen derselben Kante. So hat jede Drucksache in ihrem
Profil denselben Vorgang wie in der Rechnung über die ganze Stadt; `vorgang` darf auf eine ID einer
Nachbarperiode zeigen, und `groesse` zählt alle Mitglieder. Ein `slow`-Test rechnet beides aus den
Paketen nach: die Zahlen des Messdokuments (14 483 und 387 Kanten, 3 392 und 171 stark, 2 169
Vorgänge mit 4 643 Dokumenten, 99 mit 217, 3 237 von 8 168 Anfragen mit Antwort, Median 18 Tage
bei n = 1 948) und, je Düsseldorfer Periode, dass die eigenen Kanten der drei Profile zusammen die
Stadt ergeben und jeder Vorgang und jede Antwort gleich ist.

**Spannen auf dem Rohtext.** Titel- und Anlagentreffer sind keine Stellen im Text und stehen nur
in den Kanten (`felder`, `quelle`; Synergie, Konflikt 1). Gesucht wird im kleingeschriebenen
Textstore, denn dort hat die Messung gezählt; die Stellen legt `references` danach über
`flatten_with_offsets` (Punkt 74) auf den Rohtext, wo ihn der Rohtextstore hat und er geplättet
**genau** den Text ergibt, in dem die Nummer gefunden wurde. `value` ist dann der Rohtext an der
Stelle, wörtlich (groß geschrieben; 59 der 10 214 Spannen der Hauptperiode laufen über einen
Zeilenumbruch), und `extractor` nennt den Rohtext (`pypdf-7.1.0+roh/drucksachen-1`). In der
Hauptperiode liegen so alle 10 214 Spannen aus 5 135 Dokumenten auf dem Rohtext. Wo es keinen
Rohtext gibt -- auf Pages tragen nur die Hauptperiode und ihr Paket einen (Synergie, Konflikt 14)
--, bleibt die Spanne auf dem Textstore, und `extractor` nennt den. Der Rohtextstore ist darum eine
optionale Eingabe des Schritts (`Step.optional`, wie bei `report`). `section` bleibt leer, bis
Vorhaben 11 die Abschnitte bringt. Kanten, Vorgänge und Antworten hängen nicht daran; der
`slow`-Test hält sie mit dem Rohtext der Hauptperiode gleich.

**Laufzeit** im ersten Lauf je Profil am 2026-11-24 (Worktree, `nice -n 10`, Lastmittel 9 bis 25
durch andere Läufe auf demselben Rechner): `references` 13,3 s in der Hauptperiode, 11,9 s in 2014
bis 2020, 2,3 s in der laufenden Periode, 0,3 s in Mönchengladbach; `procedures` 4,8 s, 3,2 s,
3,7 s und 0,1 s, davon das Lesen der Nachbarpakete und von 1 090, 2 309 und 2 707 Nachbartexten.
Beide bleiben unter dem Ziel von 20 s je Profil (§ 6). Seit die Spannen auf den Rohtext
gehen, kostet `references` in der Hauptperiode 21,3 s (Lastmittel 16): rund 7 s rechnet
`flatten_with_offsets` die Stellen der 5 135 Dokumente mit einer Nummer im Text. Die Summen der drei Düsseldorfer Läufe sind
die Zahlen der Messung: 7 310 + 5 704 + 1 469 = 14 483 eigene Kanten, 1 960 + 1 093 + 339 = 3 392
starke, 1 239 + 1 750 + 248 = 3 237 Anfragen mit Antwort.

**Abweichungen vom Bauplan** (§ 6 des Messdokuments, § 10 nach der Synergie):
`dokumente_vorgang.parquet` statt `vorgaenge.parquet`; das Anlagenpaket mit einer Zeile je
Drucksache statt je Anlage (303 KB statt der geschätzten 519, zstd auf Stufe 19); die Typen .2 im
Code als Vokabular des Codebuchs statt einer Tabelle `edge_types` im Profil (sie hängen an
Änderungszeichen und Sammelbericht, nicht nur an den Rollen); die Titel der Sammelberichte und die
Änderungszeichen in `defaults.toml`, weil sie Verwaltungsdeutsch sind und in beiden Städten gelten
(Mönchengladbach hat 17 Sammelberichte, ohne sie fehlte eine seiner 171 starken Kanten); kein
Schalter `text_edges_strong`; `tage` einer Kante darf negativ sein (1,2 % zeigen nach vorn, § 3.3),
nur die Antwortzeit nicht.

**Verworfen.** Die Nachbarperioden aus ihren Läufen lesen (`data_root/<profil>/interim/`): Pages
baut die Hauptperiode zuerst, und die Kanten hingen an der Reihenfolge der Läufe. Ein eigenes
Nummernverzeichnis als Paket (eine zweite Kopie der Metadaten dreier Perioden, die mit jeder
Korrektur am Korpus veraltet). Alle Texte der Nachbarn lesen (dreimal der Regexlauf je Profil, für
Kanten, die nach der Rückfallregel ohnehin schwach sind). Bäume je Periode (der Vorgang endete an
der Wahl, gegen § 3.3). `PaperRecord` um die Anlagen erweitern (ein Schemasprung des Korpus mit
Golden-Master-Risiko; das Paket genügt, Synergie § 4); für die laufende Periode ist das der Weg
danach, denn das Paket veraltet mit jedem Tag (Frage 9.1).

## 77. Einbettungen über Stücke, ähnliche Dokumente als Paket, Suche mit der Einbettung als Vorgabe (Vorhaben 18, 2026-11-24)

Vorhaben 18 der Vorverarbeitung (`docs/plans/18-einbettungen.md`, § 5 bis § 7 und § 10), Stufe 2.
Die Messung hat zwei Fragen gegen zwei KI-Kodierer entschieden: die Suche nach Bedeutung schlägt die
Wortsuche (nDCG@10 an 50 Fragen: Einbettung 0,883, Mischung 0,846, BM25 0,709), und die ähnlichen
Dokumente tragen (Präzision@5 0,832 an 50 Ankern, TF-IDF 0,652 verfehlt die Schwelle). Gebaut ist
genau das gemessene Verfahren; Punkt 45c (Einbettungen verworfen, Oktober) ist damit für Suche und
Nachbarn überholt, für Cluster nicht (§ 3.5 der Messung: nicht bauen).

**Was gebaut ist.** Der Beitrag `18-einbettungen` (`georep.enrich.embeddings`) hinter 15 und 14,
mit zwei Schritten hinter `embeddings.enabled` (beide Stadtprofile, die Perioden erben):

- `embeddings` ist ein **Schritt mit Modell** (F5, Punkt 72) und läuft nur mit
  `georep run --models`. Je PDF-Datei mit Rohtext eine Einheit unter der kleinsten Korpus-ID
  (`search.units`), der Rohtext mit den Formfeeds der Seiten zurück (`restore_form_feeds`), wie
  die Messdatei ihn trug. Stücke nach `18-stuecke-1` (`prep.chunks.split_chunks`, das `zerteile`
  der Messung mit denselben Schleifen und der Stelle jedes Stücks im Rohtext), Präfix aus
  `[ml.embedding]`, `embed_texts` über den Modellcache. Nur lokal geschrieben:
  `processed/einbettungen_stuecke.parquet` und `processed/einbettungen_dokumente.parquet`
  (Mittel der ersten drei normierten Stückvektoren, normiert; eine Zeile je Korpus-ID mit
  Rohtext). Eine Datei, deren erste drei Stücke nicht alle da sind (Teillauf, Abweisung), bekommt
  keinen Dokumentvektor: das Mittel über die übrigen wäre ein anderer Vektor.
- `neighbors` (offline) schreibt `processed/aehnliche_dokumente.parquet`, zehn Nachbarn je
  Korpus-ID, nie die eigene Datei. Der Rang folgt der ungerundeten Ähnlichkeit (float32);
  Gleichstände der ungerundeten Ähnlichkeit stehen nach ID, auch an der Grenze zum zehnten Platz
  (`search.vectors._top` nimmt alle Werte gleich dem zehnten und sortiert sie). Die Spalte
  `aehnlichkeit` ist auf vier Stellen gerundet; gleich gerundete Nachbarn stehen darum nicht immer
  nach ID (in der Hauptperiode 647 von 1 300 solchen Paaren). Ohne
  Dokumentvektoren nimmt er die Kopie des Pakets, die `bootstrap` nach
  `raw/aehnliche_dokumente_paket.parquet` legt, ohne beides schreibt er eine leere Tabelle mit
  demselben Schema. Beide Eingaben sind **optional** (`Step.optional`): so steht ihr Hash im Stamp,
  und ein Modellschritt, der ohne `--models` nicht läuft, bricht die Kette nicht ab.
- `georep pack --neighbors` packt nur die Nachbartabelle (`snapshots/duesseldorf-aehnlich/`,
  905 998 Bytes), und nur, wenn sie aus den Dokumentvektoren daneben stammt (deren Hash im Stamp
  von `neighbors`) und diese aus einem vollständigen Lauf (`open` 0 im Stamp von `embeddings`);
  das README nennt Modell, Digest, Prompt-Version und Optionen. `bootstrap` übernimmt das Paket
  nur, wenn jede ID und jeder Nachbar ein Paper des Datensatzes ist; die Perioden nehmen den
  Schlüssel `neighbors_package` zurück.
- `georep search "<frage>" [--method embedding|hybrid|bm25] [--n 10]` (`search/query.py`,
  `search/command.py`), lokal; ohne Server oder ohne Stückvektoren BM25 mit einer Zeile dazu.

**Wo die Nachbarn herkommen.** Ein Paket gibt es nur für die Hauptperiode; der Vergleich
(`duesseldorf-vergleich`) rechnet in ihrem Ordner und erbt es. In 2014 bis 2020, der laufenden
Periode und Mönchengladbach entsteht die Tabelle nur lokal aus den Vektoren eines Laufs mit
`--models`; auf Pages und in CI bleibt sie dort leer. Eine Datenwurzel von vor diesem Stand bekommt
die Paketkopie nur mit einem `georep bootstrap` (ohne `--force`). Ohne ihn schreibt `neighbors` auch
in der Hauptperiode still eine leere Tabelle, wo es keine Dokumentvektoren gibt; nur die Laufzeile
sagt es („keine Dokumentvektoren und kein Paket: leere Tabelle"). Kein Schritt der Seite liest die
Tabelle vor Stufe 3, darum ist das kein Abbruch.

**Die Zahl der IDs ohne Rohtext steht in der Laufzeile** von `embeddings` („… 76 ohne Rohtext …"),
nicht im Stamp. Der Stamp trägt außer der Kennung des Modells kein Feld, das `georep status`
zeigt, und `extra` ginge in den Vergleich des Stamps ein (er wäre nach jedem Lauf veraltet); sie
dort zu zeigen, bräuchte eine Änderung am Kern (Review Runde 1, N9).

**Gegen die Messung geprüft** (2026-11-24, Hauptperiode): alle 47 407 Stücktexte samt Präfix und
Titel sind die des Messskripts, darum kamen alle 47 312 verschiedenen aus dem Modellcache (0 neu
gerechnet); alle 190 320 Zeilen der Nachbartabelle (Nachbar und Ähnlichkeit) sind die der Probe
`groessen/aehnliche_dokumente.parquet`; die Rangfolgen der 50 Suchfragen sind für Einbettung,
Mischung und BM25 je 50 von 50 gleich `rangfolgen.parquet`. Ein `slow`-Test hält die Zahl der
Stücke und die BM25-Rangfolgen aus den Paketen fest (`tests/unit/test_search_slow.py`), für die
Einbettung nur Invarianten (das Paket in `test_data_packages.py`): die GPU rundet je Rechner anders.

**Was das Modell sieht, steht in der Prompt-Version.** Die Präfixe `search_document: ` und
`search_query: ` gehören zum Modell und stehen in `[ml.embedding]`, also außerhalb des
Fingerprints (Punkt 72). Damit eine Änderung dort die Kennung im Stamp nicht verfehlt, hängt
`chunk_prompt` an `18-stuecke-1` einen Hash, sobald Präfix oder Zuschnitt von der gemessenen Fassung
abweichen (ebenso `query_prompt` an `18-anfrage-1`). Mit den gemessenen Werten trifft ein Lauf die
Vektoren der Messung; der Cache-Schlüssel hängt ohnehin am SHA-256 des Texts samt Präfix.

**Der Stemmer ist der klassische.** Die Messung hat den Snowball-Stemmer für Deutsch vor Snowball
3.0 benutzt; 3.0 hat ihn 2023 bis 2025 geändert (ae/oe/ue, -erin, -ln, -et, Apostroph). Die
Prüfliste kommt darum aus dem Datenrepositorium von snowballstem.org am letzten Stand vor der
Änderung (Commit `8d35251e4561`), einmal abgerufen am 2026-11-24 (§ 10, Punkt 4 des
Messdokuments); `search.stem.stem` trifft alle 35 033 Paare, im Repo liegt jedes 17.
(`tests/fixtures/snowball/`, BSD-3-Clause, mit Prüfsummen). Eine eigene Umsetzung statt
`snowballstemmer` (Frage 9.4), wie `krippendorff` in F4.

**Ein Modellschritt zählt in den Tests wie ein Netzschritt.** Zehn bestehende Testdateien ließen
„alle Schritte außer den Netzschritten" laufen oder zählten sie und verlangten „ausgeführt";
`embeddings` ist ohne `--models` übersprungen. Sie nehmen ihn jetzt aus wie einen Netzschritt
(`s.models is not None`).

**Geprüft, dass die Seite gleich bleibt.** A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt
66 (`ab/ab_bau.sh`, `ab/ab_vergleich.py`), `main` (`v0.25.0`) gegen diesen Branch, je in eigener
Datenwurzel und mit `POLARS_MAX_THREADS=4`, `OMP_NUM_THREADS=2`: unter `site/` 194 Dateien in beiden,
0 Abweichungen. Auf der B-Seite kam die Nachbartabelle der Hauptperiode (und des Vergleichs) aus dem
Paket, die übrigen Profile schrieben eine leere; kein Schritt der Seite liest sie bis Stufe 3.

**Laufzeit** (2026-11-24, Worktree, `nice -n 10`, Lastmittel 11 bis 18): `embeddings` in der
Hauptperiode 7,4 s ohne neue Einbettung (alle aus dem Cache), `neighbors` 4,2 s. Die übrigen Profile unter der GPU-Sperre, je ein Lauf `georep run --models
embeddings neighbors`, das ollama-Log mit „offloaded 13/13 layers to GPU", 1,5 GB Grafikspeicher:
Mönchengladbach 2 931 Stücke in 49 s (650 Dateien), die laufende Periode 9 590 neue Stücke in
150 s, 2014 bis 2020 59 750 neue in 908 s, je rund 65 Stücke je Sekunde unter einem Lastmittel
von 13 bis 31 (ohne Fremdlast rund 90, Messdokument § 3.3). Zusammen rund 19 Minuten unter der
Sperre, davon rund 18 GPU-Minuten Rechnung; die Hochrechnung der Messung lag bei 17.

**Bekannt: Zeichensalat sprengt das Fenster.** In 2014 bis 2020 hat ein Dokument
(`00330474.pdf`, eine defekte Schriftkodierung mit Steuerzeichen statt Buchstaben) neun Stücke über
512 Token, und ollama 0.24.0 weist sie trotz `truncate` ab (400, „the input length exceeds the
context length"). Die Annahme der Zerteilung, mindestens 3,47 Zeichen je Token, gilt für solchen
Text nicht. Nach F5 sind die neun abgewiesen und erledigt (der Schritt sagt „aktuell, 9 Eingaben
abgewiesen"); das Dokument hat keinen Dokumentvektor und keine Nachbarn, 21 713 von 21 714 Dateien
haben einen. In der Hauptperiode, der laufenden Periode und Mönchengladbach kommt es nicht vor.
`georep search` braucht beim ersten Aufruf 9,7 s für die Wortmatrix (danach 2,8 s zum Laden),
die Einbettung 0,64 s je Frage aus dem Cache.

**Abweichungen vom Bauplan** (§ 6 und § 10 des Messdokuments): `zerteile` heißt `split_chunks`
(die Namen im Paket sind englisch) und hat dieselben Schleifen; geprüft gegen eine wörtliche Kopie
als Orakel (`tests/property/oracle_chunks.py`, hypothesis) und über die Hauptperiode. Die
Dokumentvektoren tragen zusätzlich `datei`, damit `neighbors` die Einheiten ohne den Korpus bildet.
Die Paketkopie in `raw/` heißt `aehnliche_dokumente_paket.parquet` (siehe unten). Die
Settings-Klassen heißen `Bm25` und `Embeddings` wie die übrigen Blöcke. Mönchengladbach schaltet
die Schritte auch ein (Prüfstein der Stadtneutralität, § 6 „Profile"); ohne Paket bleibt seine
Nachbartabelle auf Pages leer. Die Wortmatrix des Befehls ist `processed/suche_wortmatrix.parquet`,
eine Zeile je Einheit mit Stämmen und Anzahlen.

**Was das Review (Runde 1, 2026-11-24) geändert hat**, je ein Commit: `bm25`, `rrf_k` und
`fusion_depth` stehen nicht mehr im Fingerprint, denn nur `georep search` liest sie (N4); der
Client des Einbetters entsteht erst bei Bedarf (`DeferredEmbedder`), sodass ein verweigertes
`ml.base_url` nur `embeddings` mit `--models` scheitern lässt und die Suche auf BM25 zurückfällt
(N5); die Suche prüft neben Modell und Digest auch Prompt-Version und Fenster der Stücke (N2) und
nimmt die GPU-Sperre aus `ml.gpu_lock` nicht blockierend, sonst BM25 (N1; die Vorgabe ist leer,
der Pfad gehört in `settings.local.toml`); ohne Korpus nennt sie den Handgriff statt `[Errno 2]`,
und die Hinweiszeile nennt die Zahl des gewählten Verfahrens und dass sie für die Hauptperiode gilt
(N6). Dazu die Wortlaute oben zu Gleichständen (N3), Herkunft des Pakets (K1) und Stamp (N9).

**Verworfen.** Vektoren ins Repo (Dokumentvektoren 7,5 bis 25,7 MiB, Stückvektoren 64 MiB für die
Hauptperiode allein; die Seite braucht nur die IDs, und aus Einbettungen lässt sich Text teilweise
zurückgewinnen, Fragen 9.1 und 9.7). Die Wortmatrix als Schritt der Kette (sie kostete jede Kette,
auch auf Pages, 6 bis 10 s je Profil, und nur der lokale Befehl liest sie; sie liegt darum mit ihrem
Schlüssel neben den Vektoren). Die Mischung als Vorgabe der Suche (bei Stichwörtern im Amtswortlaut
war sie am besten, insgesamt die Einbettung; eine andere Vorgabe wäre eine neue Messung mit neuen
Fragen, Frage 9.12). Der Stemmer von Snowball 3.0 (eine neue Fassung der Wortsuche, nicht gemessen).
Die Paketkopie unter demselben Namen wie die Ausgabe (`georep steps` zeigte dann
`aehnliche_dokumente.parquet -> aehnliche_dokumente.parquet`). Die Tempo-Probe vor dem ersten
Stapel (Frage 9.5) in diesem Schritt: sie gehört nach F5 (`docs/todo.md`, Punkt 11 d); im Bau ist
das Tempo von Hand geprüft. Cluster über Einbettungen (Messung § 3.5).

## 78. Zeit und Neuigkeiten: Wahljahre statt Monate, ein Lexikon als Paketdatei, Spannen auf dem Rohtext, Feeds aus den Daten (Vorhaben 17, 2026-11-24)

Vorhaben 17 der Vorverarbeitung (`docs/plans/17-zeit.md`, § 5 bis § 8 und § 10), Stufe 2. Die
Messung hat drei Hypothesen vor dem ersten Lauf festgelegt (Commit `9c7b3d6`, 2026-11-23 19:45),
das Lexikon bundespolitischer Begriffe an 100 Treffern kodieren lassen (94 richtig, α 0,957 und
0,928) und 41 Feeds gegen RFC 4287 geprüft. Gebaut ist genau das, als zweiter Beitrag nach Punkt 69
mit der Fabrik aus Punkt 74; alle vier Schritte sind offline und fragen den Transport nie.

**Was gebaut ist.** Der Beitrag `17-zeit` (`georep.enrich.cycles`, die Rechnung rein in
`analysis/cycles.py`, `analysis/lexicon.py`, `analysis/hypotheses.py` und `report/feeds.py`):

- `cycles` schreibt `processed/zeit_monate.parquet` (Dokumente je Monat, Gremienart, Urheberklasse
  und Instrument, mit Wahljahr, Dokumenten mit Text und Haushaltsanträgen; jede Kombination, die
  vorkommt, steht in jedem Monat) und `processed/haushaltsmonate.parquet`. Je Monat summiert die
  Tabelle zur Monatsreihe aus `timeline`, sonst bricht der Schritt ab.
- `vocabulary` schreibt `processed/dokumente_bundesvokabular.parquet` (eine Zeile je Korpus-ID, die
  Kategorien in Titel und Text und in Titel und den ersten 2 000 Zeichen, die Lexikonversion) und
  die Treffer im Text als Spannen nach F3 (`processed/bundesvokabular_spannen.parquet`).
- `cycle_tests` schreibt `processed/zeit_hypothesen.parquet`: die drei Haupttests mit Holm und ihre
  Sensitivitäten aus § 8 als eigene Zeilen.
- `feeds` schreibt je Wahlbezirk `site/feeds/wahlbezirk-NN.xml` und als erste Ausgabe die Liste
  `processed/wahlbezirke_feeds.parquet`; Feeds von Wahlbezirken, die es nicht mehr gibt, nimmt er weg.

Gegen das Messskript `docs/plans/17-zeit-messung.py` auf den Läufen vom 2026-11-24: jede Zahl aus
§ 3.1 bis § 3.3 und § 8.5 gleich, auf die gedruckte Stelle (H17.1 −4,9 %, p = 0,847; H17.2
+83,1 %, p = 1/27 720, Holm 0,0001; H17.3 5,98 / 3,16 / 3,47 %, p = 0,987; alle 25 Zeilen), und
die Feeds der laufenden Periode bis auf die Version im Kopf bytegleich mit dem Prototyp des
Messskripts, 40 von 41; der Feed von Wahlbezirk 22 nennt sieben der neuesten 50 Dokumente nicht
mehr, die nur über „schulweg" trafen, einen Begriff, den die Seite zählt, aber nicht zeigt
(`search.hide_in_display`, Review N1). Ein
slow-Test rechnet die Zahlen und die Präzision 94 von 100 aus `validierung/17-zeit/labels.csv` gegen
die gebaute Ausgabe nach (`tests/golden/test_cycles_numbers.py`).

**Wahljahr und Vorwahljahr aus Periode und Wahltagen, nicht aus einer Liste.** Das Messskript nannte
die vollständigen Wahljahre je Datensatz von Hand. Gebaut ist die Regel dahinter: ein Wahljahr ist
vollständig, wenn die Periode (`period.start` bis `period.end`, offen bis zum letzten Datum des
Korpus) es abdeckt und nur sein erster Monat um die Tage vor dem Beginn gekürzt ist; die
Hauptperiode beginnt am 13. September 2020 und hat das Wahljahr 2020/21, Juni bis August 2014 und
der 1. bis 12. September 2020 der alten Periode gehören zu keinem. Sie ergibt dieselben zwölf
Wahljahre. Das Vorwahljahr einer Wahl ist das letzte vollständige Wahljahr, das vor dem Wahltag
endet, wenn es unmittelbar vor dem Wahljahr der Wahl liegt; die Wahltage stehen in
`cycles.elections` im Stadtprofil mit Quelle (Synergien 2026-11, Konflikt 16: `period.election` ist
die Wahl für Nenner und Zuschnitt). Das Anlaufjahr ist das erste vollständige Wahljahr einer
Periode; H17.1 nimmt die Perioden, die ein Vorwahljahr haben.

**H17.2 über Zellsummen.** Das Messskript zentrierte je Zuordnung die Indikatormatrix doppelt.
Weil jede Zeile genau eine Eins trägt, ist der Nenner Σ TT² für jede Anordnung derselben Multimenge
gleich (er hängt nur an der Zahl der Jahre je Haushaltsmonat), und der Zähler Σ TT·YT ist die Summe
der zentrierten Zellen der Zuordnung, weil YT doppelt zentriert ist. So rechnet der Test die 27 720
Zuordnungen in einem Schritt; ein hypothesis-Test hält ihn gegen die wörtliche Rechnung des
Messskripts fest.

**Der Kern der Hypothesentabellen** (Synergien 2026-11, § 1; nach dem Review vom 2026-11-24, K2
und N7, so festgelegt, wie 22 ihn übernimmt): `hypothese`, `p`, `p_holm`, `ergebnis`, `n`,
`festgelegt`, Zusatzspalten dahinter. **Die Familie sind die Zeilen mit `p_holm`**: dort sind
Kennung, `p` in [0, 1], `n` und `festgelegt` Pflicht, jede Kennung steht einmal darin, und `p_holm`
und `ergebnis` sind Holm über die Familie, wie sie in der Tabelle steht, bei der vorab festgelegten
Familiengröße `m` (`check_hypotheses` rechnet nach). Fehlt einer festgelegten Hypothese die
Eingabe, steht sie mit leerem `p`, `p_holm` und `ergebnis` außerhalb der Familie und zählt für Holm
trotzdem mit: `holm`, `family` und `check_hypotheses` nehmen `m` (Vorgabe die Zahl der
Familienzeilen, kleiner ist ein Vertragsbruch), und die fehlende Hypothese wirkt wie eine mit p = 1
am Ende der Folge (Supervisor, 2026-11-26, der Fall von 22; bei 17 sind es drei Familienzeilen und
m = 3). Außerhalb -- Sensitivität, Robustheit, explorativ, beschreibend -- stehen `p_holm` und
`ergebnis` leer, damit niemand eine solche Zeile als bestätigt liest, und `p`, `n`, `festgelegt` und
die Kennung dürfen leer sein (22 trägt Robustheit ohne p und Paare ohne Kennung). Eindeutig ist
eine Zeile über einen Schlüssel, den der Aufrufer nennt (`key`, Vorgabe die Kennung). Die Schwelle
ist ein Parameter: `strict=False` verwirft bei `p <= alpha / (m - j + 1)` (17), `strict=True` bei
`<` (22, „p_Holm < 0,05"). Entschieden wird nach Holms Schrittregel, nicht über den Vergleich des
angepassten Werts mit alpha: beides ist mathematisch gleich, in Gleitkommazahlen nicht (m = 11,
p = 0,05/11 gibt 11 · p = 0,05000000000000001); ein hypothesis-Orakel hält die Schrittregel fest.
Die Tabelle von `feat/22-bedarf` (32 Zeilen) geht so durch `check_hypotheses`
(`tests/fixtures/hypotheses/bedarf_hypothesen_22.json`). `vorläufig` heißt: Holm hätte
entschieden, aber das Maß ist nicht validiert; H17.3 ist es, solange `analysis.lexicon.VALIDATED`
für die Lexikonversion keine Präzision von mindestens 0,9 nennt.

**Das Lexikon als Paketdatei, Version 1 unverändert.** `src/georep/lexika/bundespolitik.toml` hat
denselben Blob wie `docs/plans/17-zeit-lexikon.toml` im Commit der Festlegung; ein Test hält den
SHA-256 gleich, ein anderer die bekannten Fehler von Version 1 fest (Energiesicherungsstelle,
genderneutrale Toiletten, eine Webadresse, ukrainische Musik). Name, Version und Hash stehen im
Stamp von `vocabulary` und `cycle_tests`; eine Version 2 bräuchte eine neue Stichprobe (Frage 9.16).
Jedes Muster wird beim Laden mit Python `re` und mit Polars übersetzt: Polars zählt die Dokumente,
Python findet die Stellen, und ein Muster, das nur eines kann (Lookbehind), wäre still verschieden.
`pyproject.toml` bleibt, wie es ist: `uv_build` nimmt die Datei ins Rad.

**Spannen auf dem Rohtext** (Konflikt 1, Punkt 74). Gesucht wird wie gemessen im
kleingeschriebenen Text; `flatten_with_offsets` macht eine Stelle dort zu einer im Rohtext, mit Groß-
und Kleinschreibung und einem Zeilenumbruch, wo das Wort über eine Zeile lief. `extractor` nennt den
Rohtext und die Lexikonversion, `section` bleibt leer, bis Vorhaben 11 die Abschnitte bringt. Ein
Treffer im Titel ist keine Stelle im Text und keine Spanne. Ein Dokument ohne Rohtext, oder mit einem,
der nicht zu seinem Text plättet, hat keine Spannen und zählt in der Meldung des Schritts; seine
Kategorien hat es trotzdem. Hauptperiode: 6 506 Spannen in 1 997 Dokumenten (36 über einen Zeilenumbruch), ohne Rohtext nur das
verschlüsselte `00403713.pdf` (Punkt 73); 2014 bis 2020: 6 466 in 1 512 Dokumenten, ohne Rohtext nur
`61/ 141/2016` (`00278070.pdf`), eines der 15 PDFs, die pypdf seit 6.21 an einer Schutzgrenze
abweist und deren Text der Textstore aus pypdf 6.20.0 behält (Punkte 66 und 73); laufende Periode
555, Mönchengladbach 407 (dort tragen 81 der 161 Dokumente mit Treffer ihn nur im Titel).

**`cycle_tests` im Profil `duesseldorf-vergleich`** (Konflikt 13). Die Tests lesen die Ausgaben von
drei Perioden; das Profil, das schon `compare` über zwei rechnet und auf Pages die Hauptseite
zuletzt baut, nennt sie (`cycles.periods`). Fehlt eine Periode, bricht `run` mit dem Pfad der
Datei ab, wie bei `compare`. Damit muss `.github/workflows/pages.yml` die laufende Periode **vor**
`duesseldorf-vergleich` rechnen; die Änderung macht der Supervisor (das gh-Token hat keinen
`workflow`-Scope). Die Perioden tragen Dateien gleichen Namens; seit Punkt 76
(`pipeline.input_key`) stehen gleichnamige Eingaben mit ihrem Pfad im Stamp, und eine Änderung in
jeder Periode macht den Schritt veraltet (ein Test ändert eine andere Periode und sieht das).

**Feeds aus den Daten.** `feed/id` ist `urn:uuid:` aus Stadt, Ordner und Wahlbezirk, `feed/updated`
das jüngste `updated` der Einträge und nie die Laufzeit, `entry/updated` OParls `modified` in der
Zone des Profils, nie vor dem Vorlagendatum (00:00 Ortszeit, `feeds.timezone`); eine Zeit ohne Zone
gilt in dieser Zone (Review N4), und sortiert und verglichen wird als Zeitpunkt, nicht als Text
(N3). Dieselben Daten geben dieselben Bytes, ein Lauf ohne neues Dokument schreibt keinen Feed neu.
Jeder Wahlbezirk des Wörterbuchs hat einen Feed, auch ohne Treffer: dann leer, mit dem Stand der
Daten (letztes Vorlagendatum, 00:00 Ortszeit) als `updated`; weg kommt nur der Feed eines Bezirks,
den das Wörterbuch nicht mehr kennt (N2). Ein Feed nennt nur Dokumente, die die Seite zeigt: ohne
die Begriffe aus `search.hide_in_display`, die zählen, aber kein Dokument zeigen (N1). Kein `category` und kein `rel="self"` (Fragen 27 und
28, Annahme). Ein Titel verliert nur, was XML 1.0 verbietet. Die Feeds sind keine Ausgaben des
Registers (ihre Zahl kennt der Schritt erst beim Lauf); die Liste ist es. `atom_problems` prüft jeden
Feed beim Schreiben ohne Netz und ohne lxml (normative Regeln, Form nach Anhang B, Projektregeln);
gegen das RELAX-NG-Schema aus RFC 4287 sind die gebauten Feeds einmal mit lxml des System-Pythons
geprüft (41 von 41 gültig, die Gegenprobe des Messdokuments fällt durch; 2026-11-24). lxml kommt nicht in die Entwicklungsgruppe (Frage 9.8): die Tests brauchen es nicht.

**Abweichungen vom Bauplan** (§ 6 des Messdokuments). `zeit_monate` trägt zusätzlich das
`instrument` im Schlüssel: S1.5 ist vorab festgelegt und braucht Anfragen und Anträge je Wahljahr;
die Regel (Dokumentart, sonst Titelwort) steht in `defaults.toml`, die Arten `zAnfrage` und `zAntrag`
im Stadtprofil. `zeit_hypothesen` trägt den Kern, dazu `rolle`, `effekt_unten`, `effekt_oben`
(90 %, H17.1), `einheit`, `p_randomisierung`, `zuordnungen` und `anteile` (gepoolt je Periode,
H17.3); die beschreibenden S1.6 und S2.3 sind keine Tests und stehen nicht darin, die Unterseite
rechnet sie aus `zeit_monate`. Neu sind `cycles.head_chars` (S3.1), `cycles.instrument_types` und
`instrument_titles` (S1.5) und `feeds.timezone`; `feeds` schreibt zusätzlich die Liste
`wahlbezirke_feeds.parquet` (je Wahlbezirk Datei, Einträge, Dokumente, neue der letzten 30 Tage,
Stand, Bytes), die Stufe 3 für die Linkliste liest.

**Laufzeit** am 2026-11-24 unter Fremdlast (Lastmittel 18 bis 38, `nice -n 10`, Polars auf vier
Threads): `cycles` 0,1 bis 0,6 s, `vocabulary` 0,4 s (Mönchengladbach) bis 7,2 s (2014 bis 2020),
`cycle_tests` 0,9 s, `feeds` 0,7 s.

**Verworfen.** Zwei Beiträge `cycles` und `feeds` (Synergien 2026-11, § 2.1: ein Beitrag je
Vorhaben); `cycle_tests` im Hauptprofil (der erste `georep run` auf Pages und der Lauf des Monitors
brächen ab, solange die anderen Perioden fehlen); ein eigenes Profil nur für die Tests (ein drittes
Profil im Ordner der Hauptperiode mit eigenem Fingerprint: jeder Wechsel rechnete die Kette neu, und
die Hauptseite käme von dem, das zuletzt lief); die Wahljahre je Datensatz als Liste im Profil
(die Regel ergibt sie aus der Periode); das Instrument für S1.5 aus `dokumente_funktion` von
Vorhaben 15 (validiert, aber nicht die vorab festgelegte Regel; S1.5 bleibt „nicht deutbar", § 3.1);
S3.5 „ohne Migration" in der Tabelle (nachträglich und an eine Kategorie des Lexikons gebunden; die
Unterseite kann es aus den Spalten rechnen); eine Datei je Feed als Ausgabe des Schritts (die
Wahlbezirke kennt erst das Wörterbuch); lxml für den Test des Schemas.

## 79. Die Beschlusslage ist die letzte Entscheidung in der Sache; der Prüfauftrag bleibt eine Spalte (Vorhaben 26, 2026-11-24)

Vorhaben 26 der Vorverarbeitung (`docs/plans/26-beschluesse.md`, § 5, § 6 und § 10), Stufe 2. Die
Messung hat die Abbildung der Einträge der Sitzungsleitung auf Klassen an 150 Anträgen gegen zwei
KI-Kodierer geprüft: `ergebnis` 150 von 150 (Wilson 0,975–1,000), der beantragte Prüfauftrag 57 von
65 (Recall 0,73) -- das Urteil war „bauen, mit Rückfall 1". Gebaut ist genau diese Regel, als dritter
Beitrag nach Punkt 69, hinter 15 und 14.

**Was gebaut ist.** Der Beitrag `26-beschluesse` (`georep.enrich.outcomes`) bringt zwei
Offline-Schritte vor `report`, nur mit `outcomes.enabled` (in allen drei Düsseldorfer Perioden an):

- `council_results` schreibt den Beratungsverlauf `processed/beratungsverlauf.parquet`: je Beratung
  einer Drucksache jeder Tagesordnungspunkt mit Gremium (Kürzel aus `[bodies.organizations]`, sonst
  der Schlüssel `gr/NN`), Beginn der Sitzung, Nummer, Folge, dem Eintrag `result` und seiner Stufe.
  Die Quelle ist der Netzlauf von Fundament F6 (die drei JSONL-Dateien unter `raw/`, gelesen mit den
  Modellen aus `georep.oparl`), sonst das Paket `snapshots/duesseldorf-beschluesse/` aus `georep
  pack --outcomes`, das `bootstrap` nach `raw/tagesordnungspunkte.parquet` legt; ohne beides ein
  `MissingInputError`. Der Name ist nicht `beratungsfolge` (Punkt 58 behält ihn, Messdokument § 10).
- `outcomes` schreibt die Beschlusslage je Korpus-ID (`processed/beschlusslage.parquet`) und den
  Antragserfolg je Fraktion und Gremienart (`processed/antragserfolg.parquet`). Er liest die Rollen
  über `prep.references.role_of` und die starken Kanten (`vorgang_kanten`) von Vorhaben 14 und die
  Antragsteller von Vorhaben 15; ohne deren Schritte fehlt er, der Beratungsverlauf bleibt.
- Die Regeln stehen rein in `analysis/outcomes.py`, mit Verträgen an den Batch-Grenzen (eine Zeile je
  Korpus-ID, Klasse aus der Aufzählung, maßgeblicher Punkt genau bei einem Eintrag und im Verlauf
  desselben Dokuments, Prüfauftrag nur bei angenommenen Anträgen, `n >= angenommen >= 0`); die
  Prädikate in `georep.contracts`. Schema-Version aus `OUTCOMES_SCHEMA_VERSION`, die des Pakets aus
  `AGENDA_SCHEMA_VERSION`.

**Die letzte Entscheidung in der Sache.** Maßgeblich ist der späteste Tagesordnungspunkt der Stufe
`sache` (beschlossen, geändert, abgelehnt, zurückgezogen, auch als Empfehlung), sonst der späteste
überhaupt (Kenntnisnahme, Vertagung, Verweisung), sonst `ohne_ergebnis`; „spätest" nach Beginn der
Sitzung, Folge auf der Tagesordnung und ID des Punkts. Welche Stufe und Klasse ein Wert trägt, sagt
der Wortschatz `[outcomes.results]` im Stadtprofil (21 Werte in Düsseldorf), geprüft gegen
`OUTCOME_STAGES`; ein Wert, den er nicht kennt, ist ein `UnknownResultError` mit Wortlaut, Zahl und
Beleg, nie still `ohne_ergebnis`. Gegen das Messskript Dokument für Dokument auf den Netzläufen vom
2026-11-23: Klasse, maßgeblicher Punkt, Gremium, Datum und Zahl der Beratungen in **0 von 45 418**
Dokumenten der drei Perioden verschieden, die Klassen der Anträge gleich der Tabelle in § 3.4 (auch
für 2014 bis 2020 mit dem eigenen Abruf der Beratungen, Frage 9.10). Die Regel des Messskripts steht
wörtlich in `tests/property/oracle_outcomes.py`, und hypothesis vergleicht beide; ein Mutant ohne
den Rang der Stufe fällt dort durch.

**Der Prüfauftrag nach der Kodierung nicht auf der Seite (Rückfall 1, Recall 0,73).** Die Regel des
Messskripts (Commit `94da91f`) steht unverändert als `review_only`, ihre Muster als Listen in
`[outcomes.review]` von `defaults.toml` (Sprache der Ratsdokumente, keine Stadt): 0 von 45 418
Dokumenten verschieden. Sie füllt nur die beschreibende Spalte `pruefauftrag_beantragt`, und nur
bei angenommenen Anträgen; „offene Prüfaufträge" entfallen. Der slow-Test hält die 57 von 65 und
die acht Fehler aus § 4.1 als dokumentierte Grenze fest: eine bessere Regel wäre eine neue Messung
(Frage 9.8), kein Refactoring.

**Praxiszellen.** In einem Gremium-Jahr, in dem mindestens 40 % der Anträge mit Ergebnis „erledigt"
sind und mindestens zehn (`practice_share`, `practice_min`), ist „erledigt" eine Praxis der
Sitzungsleitung und kein Ergebnis: `eintrag_tragfaehig` ist dort false. Gezählt wird je Profil
über das Jahr der maßgeblichen Sitzung; es trifft BV9 2014, 2015 und 2016 und den Rat 2016, 240
Anträge, alle in 2014 bis 2020 -- wie in § 5. Die Spalte steht nur bei Anträgen mit Ergebnis
(sonst null): eine Informationsvorlage „zur Kenntnis genommen" ist ihr richtiger Eintrag. Die
Schwelle ist nach dem Blick auf die Daten gesetzt (Lücke zwischen 16 % und 47 %), also eine
Variante, die die Kodierung nicht misst.

**Angenommen statt beschlossen/geändert auf der Seite.** `grob` fasst beschlossen und geändert zu
`angenommen` zusammen (dazu `abgelehnt`, `ohne_sachbeschluss`, `offen`, `ohne_ergebnis`, wie
Rückfall 2). Bei Vorlagen ist „abweichend" uneinheitlich eingetragen (§ 3.8); die Unterscheidung
bleibt in `klasse`, die Seite zeigt sie in Stufe 3 nur als Unterzahl.

**Was vom Bauplan abweicht.**

- *Schlüssel des Verlaufs* ist (`id`, `beratung`, `top`), nicht (`id`, `top`): eine Beratung, deren
  Tagesordnungspunkt nicht in der Sitzungsliste der Periode steht, behält eine Zeile mit `top` null
  (276 in der Hauptperiode). So zählt `beratungen` jede Beratung, wie im Messskript; doppelte
  Punkte je Dokument gibt es in keinem der drei Abrufe.
- *`sitzung` ist der Beginn mit Uhrzeit* (Ortszeit des Servers, ohne Zone), nicht das Datum: die
  Regel ordnet nach Beginn, und zwei Sitzungen desselben Tages ordnete das Datum allein nach der
  Folge der Punkte. `entscheidung_datum` ist das Datum.
- *Die Rolle* kommt aus der Regel von 14 (`role_of`), weil 14 sie nicht als Spalte schreibt; kein
  Nachbau.
- *Das Paket* hat eine Datei je Periode (`raw/tagesordnungspunkte-<ordner>.parquet`, zusammen
  631 944 Bytes, zstd auf Stufe 19) unter dem Namen aus `outcomes.package`; es trägt die Schlüssel
  der Organisationen, nicht die Kürzel, damit die Kürzel aus Frage 9.17 kein neues Paket brauchen.
  Wo der Netzlauf liegt, gilt er; aus denselben Dateien geben beide Wege denselben Verlauf.
- *Antragserfolg* ist je Gremienart getrennt (`by`) und standardisiert je Gremium der Drucksache.
  Die Fraktionen kommen aus 15 (mit Zeitraum, Punkt 75), nicht aus der Einheit des Messskripts;
  „SPD" (Dokumente vor dem 2020-11-01) und „SPD+VOLT" bleiben darum getrennte Zeilen, wie 15 sie
  liefert. Der Filter auf `eintrag_tragfaehig` ändert heute nichts: false steht nur bei „erledigt",
  und das ist keine Sachentscheidung.
- *Die Quote einer Schicht zählt dieselben Zeilen wie die Beobachtung* (Review 2026-11-24, N2,
  Entscheidung des Supervisors): je Antrag und beteiligter Fraktion eine Zeile, ein Antrag ohne
  Fraktion gar nicht. Das Messskript zählte die Quote je Antrag einmal, Anträge ohne Fraktion
  eingeschlossen; dann verteilte die Standardisierung im Rat der Hauptperiode 361,3 erwartete
  Annahmen auf 524 beobachtete, und beobachtet/erwartet lag für die Mehrheit fast überall über 1.
  Jetzt gilt je Schicht Σ beobachtet = Σ erwartet, als Nachbedingung von `motion_success` und als
  hypothesis-Eigenschaft. Eine bewusste Abweichung vom Messskript in einer explorativen Größe; die
  Werte (Hauptperiode, alt → neu): Rat CDU 2,83 → 1,95, Grüne 2,77 → 1,91, SPD/Volt 1,14 → 0,79,
  FDP 0,75 → 0,52, Linke 0,29 → 0,20, AfD und T_FW 0 → 0; Ausschüsse CDU 1,93 → 1,55, Grüne
  1,90 → 1,53; in den Bezirksvertretungen ändert sich kaum etwas (CDU 1,03 → 1,02, Grüne 1,00 →
  0,98); die Reihenfolge der Fraktionen bleibt dort in jeder Gremienart dieselbe. Im Rat seit
  2025 (18 und 19 Anträge, alle angenommen) CDU und Grüne 11,65 → 6,45.
- *Gremium ohne Organisation* ist null, nicht „?".

**Folgevorlage je Profil, eine Untergrenze.** `folgevorlage` ist die früheste Drucksache der
Verwaltung (Rollen aus `followup_roles`), die den Antrag über eine starke Kante nennt. Die Kanten von
14 tragen nur nennende Drucksachen des eigenen Korpus; eine Folgevorlage der nächsten Periode sieht
ein Profil darum nicht. Über alle drei Perioden zusammen sind es 1 508 Anträge mit Folgevorlage
(gleich der Messung, § 3.7), je Profil 1 394: 114 fehlen, fast alle Anträge vom Ende einer
Periode. Ob 14 die Kanten aus den Nachbarperioden in den eigenen Korpus mitschreibt, ist eine Frage
an den Supervisor; bis dahin ist die Spalte eine Untergrenze, wie § 3.7 sie ohnehin nennt.

**Mönchengladbach bleibt aus** (§ 10, Punkt 6). Sein Netzlauf trägt an den Punkten seiner 2 895
Dokumente 48 andere Werte, darunter mehrere ohne eindeutige Klasse: „Siehe Niederschrift" (40),
„Getrennte Abstimmung (s. Niederschrift)" (32), „Ohne Abstimmung" (43), „Geheime Abstimmung" (3),
„-" (3), „In den nächsten Ratszug geschoben" (70), „Die Bezirksvertretung wurde angehört" (211).
`outcomes.enabled` bleibt dort aus; ein Wortschatz für Mönchengladbach wäre eine eigene Messung.

**Laufzeit** (2026-11-24, Lastmittel um 20, `nice -n 10`, Polars auf vier Threads):
`council_results` aus dem Netzlauf 3,2 s in der Hauptperiode (davon 2,2 s Laden der JSONL über
pydantic), 3,5 s in 2014 bis 2020, 1,7 s seit 2025; aus dem Paket 0,1 bis 0,2 s; `outcomes` 1,3 s,
0,9 s, 0,2 s (aus dem Paket 1,2 s).

**Geprüft, dass die Seite gleich bleibt.** A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt 66
(`ab/ab_bau.sh`, `ab/ab_vergleich.py` auf xtraspace; A `main` 098d556, B dieser Branch, beide mit
`POLARS_MAX_THREADS=4`, `OMP_NUM_THREADS=2`): unter `site/` 194 Dateien in beiden, **0
Abweichungen**. Über die Datenwurzeln 721 Dateien in A, 739 in B: dazu kommen genau die 18 Dateien
dieses Vorhabens (je Periode das Paket in `raw/`, drei Tabellen unter `processed/` und zwei Stamps),
und abweichend sind nur 87 Stamps (der Settings-Fingerprint hat neue Schlüssel). B rechnet ohne
Netzlauf aus dem Paket, wie Pages, und kommt auf dieselben Klassen wie der Netzlauf im Worktree.

**Verworfen.** Die Rollen aus dem Messskript von 14 (`art2`; § 10: kein Nachbau); eine eigene Klasse
für Einträge, die keine sind (die Praxiszellen sind eine Spalte neben der Klasse, Frage 9.2); der
Prüfauftrag als Klasse oder auf der Seite (Rückfall 1); die Kürzel `gr/400224` und `gr/65` jetzt
eintragen (§ 10, Punkt 7: vor Stufe 3, mit A/B-Bau); die Tabelle des Pakets mit Kürzeln oder
Klassen (ein neues Profil brauchte ein neues Paket); ein Paket für alle drei Perioden in einer
Datei (jedes Profil packt seine eigene, der Name steht im Profil); den Wortschatz in
`defaults.toml` (er ist der einer Sitzungsleitung, Mönchengladbach hat einen anderen).
## 80. Bedarf und Aufmerksamkeit je Wahlbezirk: Punkte mit Randband, Auszüge als Paket, die Tests der Messung (Vorhaben 22, 2026-11-24)

Vorhaben 22 der Vorverarbeitung (`docs/plans/22-bedarf.md`, § 5 bis § 8 und § 10), Stufe 2. Die
Messung fand vier Bedarfsquellen mit freier Lizenz und passender Raumeinheit (Quartiersatlas,
Unfallatlas, Zensus-Gitter, Schulsozialindex) und rechnete drei vorab festgelegte Hypothesen; gebaut
ist genau diese Rechnung, als sechster Beitrag nach Punkt 69 (hinter 15, 14, 18, 17 und 26), mit dem
Netzschritt über `http` (Punkt 74).

**Was gebaut ist.**

- `crosswalk.point_shares`: je Punkt gleiche Anteile an jede Einheit (Wahlbezirk oder Stimmbezirk),
  deren Fläche näher als `band_m` liegt; Band 0 ist Punkt in Fläche, ein Punkt auf einer Grenze liegt
  in beiden geschlossenen Flächen und wird geteilt. Ein STRtree, eine Abfrage für alle Punkte. 16
  (Hausnummern) und 21 (Beträge) rufen dieselbe Funktion (Synergien 2026-11, § 1).
- `prep/context.py` liest die Quellen, wie sie kommen (`read_accidents` in den drei Namensformen der
  Jahrgänge, mit BOM und Dezimalkomma; `read_grid`; `read_schools` mit der Zeile `sep=;` und dem
  Sozialindex in Codepage 850) und rechnet je Wahlbezirk (`need_table`); ein Verhältnis ohne Nenner
  ist null, nie NaN. Einen Unfall oder eine Schule ohne Koordinate verwirft der Leser und zählt sie
  für die Zeile von `need_data` (`Located`); vorher hielt erst `point_shares` mit einem
  `PreContractError` an (Review 2026-11-24, N3). Heute hat keine Quelle eine solche Zeile.
- `analysis/need.py` rechnet die Tests: Spearman, Permutationen, Bootstrap, Holm, Robustheit,
  explorativ innerhalb der Stadtbezirke und Moran's I. Die Zufallszahlen kommen in der Folge des
  Messskripts, die Korrelationen für alle Permutationen zugleich.
- Beitrag `22-bedarf` (`enrich/need.py`): `need_data` (Netz) legt die zehn Archive unter
  `cache_root/bedarf/` ab und schneidet die Gemeinde heraus (`external/bedarf/`, mit
  `quellen.json`); `need` schreibt `wahlbezirke_bedarf.parquet` und, wo das Profil Hypothesen nennt,
  `bedarf_hypothesen.parquet` (ohne Hypothesen und Paare entfernt es eine alte aus einem früheren
  Lauf, Review 2026-11-24, N9). Pfade in `need_files`, keine Property in `layout.py`.
- Pakete `snapshots/duesseldorf-bedarf/` (198 018 Bytes) und `snapshots/moenchengladbach-bedarf/`
  (91 866 Bytes) über `georep pack --need`; `bootstrap` kopiert sie nach `external/bedarf/`, die
  eigenen eines Datensatzes zuerst (die Mini-Fixture).

**Gleich mit der Messung.** Auf dem Lauf vom 2026-11-24 ist jede Spalte von
`wahlbezirke_bedarf`, die auch die Tabelle des Messskripts hat (22 der 25 neben dem Schlüssel, mit
den Namen unten), gleich (größte Abweichung 1e-13, Summenfolge), und `bedarf_hypothesen` trägt jede
Zahl aus § 3.4 und § 3.5: H1 ρ = 0,343 (95 % 0,051 bis 0,593), p = 0,0143, p_Holm = 0,0429,
bestätigt; H2 −0,336, p_Holm 0,0692; H3 −0,059; innerhalb der Stadtbezirke −0,062, −0,204, 0,465;
Moran's I der Residuen 0,341, 0,050, 0,262. 11 501 Unfälle im Zeitraum, 3 170 im Band geteilt,
611 134 Einwohner. Ein `slow`-Test (`tests/golden/test_need_numbers.py`) rechnet die Zahlen aus dem
Paket nach.

**Nachtrag 2026-11-26: die Klassenanteile gelten je Rechner.** Der CI-Lauf 45887973775 (0.29.0,
Azure, vier Kerne, Python 3.14.10) rechnete H1 mit ρ = 0,3465 (95 % 0,0537 bis 0,6000), ohne die
Wahlbezirke 1 und 10 0,4215, innerhalb der Stadtbezirke −0,0530; hier waren es auf jedem Lauf
0,3427, 0,417 und −0,062, auch ohne Drosselung, mit 1, 4 und 13 Polars-Threads, 1 bis 16
BLAS-Threads, zwei anderen OpenBLAS-Kernen, zwei Hash-Seeds und in der Folge der slow-Tests des CI.
Alle CI-Werte samt beiden Bootstrap-Grenzen entstehen bitgleich, wenn Wahlbezirk 18 in
`anteil_verkehr` eine Rangstelle höher steht, also ein Dokument mehr in `OVA` liegt; keine einzelne
Änderung der Unfälle erzeugt sie. Die Ursache liegt vor 22: die logistische Regression des Schritts
`committees` (Punkt 45) ist nur bis auf ihre Toleranz bestimmt. lbfgs hält mit `tol` 1e-4 nach 46
Iterationen an, mit 1e-10 nach 132; dazwischen liegen die Wahrscheinlichkeiten bis 0,011 auseinander,
und 18 von 19 033 Dokumenten wechseln die Klasse. Threads und BLAS-Kerne bewegen sie hier um höchstens
1e-12, ein anderer Rechner hält an einer anderen Stelle. Wie beim Themenmodell (`STATUS.md`) gelten
die Zahlen von H1 und H3 darum **je Rechner**; H2, die Paare ohne Klassen und alle Summen der
Bedarfsseite hängen an keiner Klasse und sind überall gleich. Die vorab festgelegten Urteile
halten: H1 bestätigt mit p_Holm 0,0414 im CI, 0,0411 mit `tol` 1e-10 und 0,0429 hier, H2 und H3
nicht bestätigt. Der `slow`-Test prüft seither die Urteile, die Deutungen und p_Holm < 0,05 für
H1 genau, H2 und die klassenfreien Zahlen wie gemessen, H1 und H3 mit 0,02 (Korrelationen, Grenzen,
Moran's I) und 0,01 (p); gesehen waren höchstens 0,009. Offen, als Frage an Punkt 45 und nicht an
22: eine engere Toleranz des Klassifikators machte die Klassen rechnerfest, verschöbe aber 18
Dokumente und damit die gemessenen Zahlen von H1 und H3 (H1 ρ 0,3470) -- das wäre ein A/B-Bau und
eine Entscheidung für sich.

**Anders als der Bauplan, mit Grund.**

- *Paket unter `snapshots/` als Parquet*, nicht CSV unter `context/` (Konflikt 11): `context/` hält
  Portaldateien unverändert. Parquet hält die Typen und die vollen Koordinaten, und es sind 290 KB statt
  der geschätzten rund 1 MB; alle Pakete zusammen 168,59 MiB von 180 (mit den Paketen von 14, 18 und 26).
- *Die Quellen stehen in `defaults.toml`*, nicht in jedem Stadtprofil: sie sind bundes- oder
  landesweit und für beide Städte dieselben zehn URLs, wie die Ratssprache in Punkt 75. Das Profil
  schaltet ein und nennt Paket, Klassen, Hypothesen und Paare; die Gemeinde ist `city.ags`.
- *Mönchengladbach bekommt sein Paket gleich mit* (Konflikt 11 nennt `moenchengladbach-bedarf`):
  Unfälle, Einwohner, Miete und Schulsozialindex je Wahlbezirk, ohne Klassen und Hypothesen
  (Frage 22.6). Die Periodenprofile schalten ab (Frage 22.5).
- *`cells_to_districts` gibt es nicht*: `point_shares` mit Band 0 ist genau das.
- *Spalten*: `sozialindex_schulen` statt `sozialindex_gs` und `schulen_mit_index` statt
  `grundschulen` (das Messskript zählte nur Grundschulen mit Stufe; die Schulformen stehen jetzt in
  den Settings), dazu `schulen` mit allen Schulen dieser Formen, auch ohne Stufe (88 gegen 87); so
  ist auch der Abgleich oben gerechnet (Review 2026-11-24, N6). `unfaelle_geteilt` (Anteile aus Unfällen,
  die auf mehrere Wahlbezirke gehen) statt `unfaelle_am_rand`, das im Messskript auch die Stadtgrenze
  zählte (3 268 gegen 3 170); Zählungen aus Anteilen sind Float64, weil ein Punkt auf einer Grenze
  geteilt wird.
- *Die Hypothesentabelle* trägt den Kern der Synergie vorn (`hypothese`, `p`, `p_holm`, `ergebnis`,
  `n`, `festgelegt`) und ist lang: je Zeile eine Rechnung (`haupttest`, `robustheit`, `innerhalb`,
  `moran_*`, `paar`) mit `mass` und `wert`, weil Moran's I kein ρ ist. Die Robustheit trägt nur ρ, wie
  in § 3.4. `ergebnis` steht nur am Haupttest, dahinter `deutung` mit den drei Wörtern aus § 8
  („Aufmerksamkeit folgt dem Bedarf", „ungleiche Aufmerksamkeit", „kein Zusammenhang nachweisbar"):
  `ergebnis` sagte bei der zweiseitigen H2 nicht, in welche Richtung Holm verwirft (Review
  2026-11-24, K1). Die einseitigen H1 und H3 haben nur den ersten und den letzten Ausgang.
- *Die Hypothesen stehen im Stadtprofil* mit dem Commit ihrer Festlegung (`fixed`): sie nennen
  Variablen des Quartiersatlas. Auch die Wahlbezirke der Robustheit „ohne 1 und 10" stehen in jeder
  Hypothese (`robust_without`), nicht in `analysis.exclude_districts`, das die Regression der Seite
  steuert und sich ändern darf, ohne dass sich eine vorab festgelegte Rechnung mitändert (Review
  2026-11-24, N8; die Zahlen 0,417, −0,411, −0,144 bleiben, ein `slow`-Test hält sie). Der Commit ist `67f7250`; das Messdokument nannte `9da9fe1`, den Hash
  vor dem Rebase, den es in keinem Zweig gibt (berichtigt).
- *Der Netzschritt hinter einem eigenen Schalter*: `need_data` gibt es nur mit
  `context.need.fetch` (Vorgabe aus, auch in den Stadtprofilen, nicht im Fingerprint), derselbe
  Mechanismus wie `council.enabled` (Review F6 2026-11-23, Befund 6): volle Abrufe sind Konrads
  Läufe, und mit `enabled` allein lud ein bloßes `georep fetch` die zehn Archive (Review
  2026-11-24, N1). Abgerufen wird mit `GEOREP_CONTEXT__NEED__FETCH=true georep fetch need_data`.
- *Archive mit Lebensdauer*: `need_data` lädt ein Archiv erst wieder, wenn es älter ist als
  `cache.opendata_s` (dieselbe Lebensdauer wie die übrigen Portaldateien), eine Datei nach der
  anderen mit `context.need.delay_s` Pause. Ein Neuladen bei jedem Lauf hieße 105 MB je Stadt und
  Lauf; eine Cache-Regel der Session legte sie in die geteilte `http.sqlite` (heute 800 MB).
- *Zehn Schulen mit `null` als CRS* (Seminare, neue Schulen, keine Grundschule) gelten als im
  erklärten CRS; ein anderes, genanntes CRS bleibt ein Fehler. Der erste echte Lauf brach daran ab.
- *Neun Gitterzellen nur in der Mietdatei* bleiben mit null Einwohnern im Auszug und haben kein
  Gewicht; das Messskript verlor sie beim Verbinden (7 658 statt 7 667 Zellen, dieselben Zahlen).
- *Ohne Fremddaten oder Klassen bleibt die Zeile ohne p*: eine Hypothese über eine Variable des
  Quartiersatlas oder einen Anteil der Klassen hat in einem Lauf ohne `context.root` oder ohne
  Klassifikator keine Werte. Ihre Zeile bleibt, mit `p` null und ohne `p_holm`, Ergebnis und
  Deutung (ein Test ohne Werte stünde sonst als „nicht bestätigt" da), und Holm rechnet weiter über
  alle vorab festgelegten, m = 3 (Review 2026-11-24, N2; vorher fiel die Hypothese weg, und Holm
  rechnete über den Rest). Die Zeile des Laufs nennt sie. Im Lauf der Hauptperiode fehlt nichts;
  die Tests der Kette laufen auch ohne Fremddaten.
- *Holm und die Wortwahl aus dem Kern von 17* (`analysis/hypotheses.py`, Punkt 78): `family` mit
  `strict=True`, weil § 8 „p_Holm < 0,05" festlegt (die Vorgabe des Kerns ist `<=`), und `m` gleich
  der Zahl der vorab festgelegten Hypothesen, damit eine ohne Eingabe außerhalb der Familie steht
  und für Holm trotzdem zählt (Supervisor, 2026-11-26). Der Vertrag von `hypothesis_table` ruft
  `check_hypotheses` mit dem Schlüssel `ROW_KEY` (Hypothese, Rechnung, Bedarf, Aufmerksamkeit,
  Kontrolle, ohne), denn 22 trägt je Hypothese mehrere Rechnungen. Bis zum Merge von 17 lagen
  `holm` und `verdict` als Übergang in `analysis/need.py`; ihr Ziel in `VERIFY_TARGETS` fiel mit
  ihnen weg, `georep.analysis.hypotheses.holm` steht dort seit 17. Die Zahlen von H1 bis H3 sind
  dieselben (der `slow`-Test).

**Geprüft, dass die Seite gleich bleibt.** A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt 66
(`ab/ab_bau.sh`, `ab/ab_vergleich.py` auf xtraspace), beide mit `POLARS_MAX_THREADS=4` und
`OMP_NUM_THREADS=2`: zuerst `main` `61fcdd5` gegen den Branch vor dem Merge (`9520f86`), dann `main`
`098d556` (mit Vorhaben 14) gegen den zusammengeführten Branch. Beide Male unter `site/` 194
Dateien in A und B, 0 Abweichungen. Über die Datenwurzeln weichen nur Stamps ab (79 und 87 Stück),
und in B liegen 13 Dateien mehr: die acht Auszüge unter `external/bedarf/` beider Städte, die drei
Tabellen unter `processed/` und ihre zwei Stamps. Im Bau aus den Paketen (ohne Netz) rechnet `need`
dieselben Zahlen wie im Lauf mit `need_data`.

**H1′ und H3′** (Frage 22.10) sind in § 8.1 des Messdokuments prospektiv festgelegt, an der laufenden
Periode, gerechnet erst mit zwölf Monaten Unfällen (Unfallatlas 2026, Juli 2027); gebaut ist dafür
nichts.

**Verworfen.** Die Auszüge als CSV unter `context/` (Konflikt 11); eine eigene Session für den
Netzschritt (ohne Fake-Session nicht testbar, Punkt 74); die Archive in `http.sqlite` (oben); ein
dritter Schritt nur für die Tests (eine Datei mehr im Register für eine Rechnung von einer Sekunde, die
dieselben Eingaben liest); `PrecinctIndex.locate` je Punkt (13 500 Aufrufe statt einer Abfrage); die
Tabellen auf der Seite schon in Stufe 2 (sie gehören zu `bedarf.html`, Stufe 3, und änderten sonst
`index.html`); der Lärm 2018 (braucht die 90 MB der Gebäudereferenzen, Frage 22.2); ein räumliches
Modell (Frage 29: Moran's I und die Rechnung innerhalb der Stadtbezirke genügen).

## 81. Abschnitte und Kopf aus dem Rohtext: der validierte Entwurf unverändert, Rumpf und Gremiennamen als Nachbearbeitung, ein früher Schritt (Vorhaben 11, 2026-11-24)

Vorhaben 11 der Vorverarbeitung (`docs/plans/11-struktur.md`, § 5 bis § 7 und § 10), Stufe 2. Die
Messung hat das Regelwerk `struktur-entwurf-1` gegen zwei KI-Kodierer an 200 Dokumenten der
Hauptperiode geprüft: Beschlussvorschlag zeilengenau 188 von 200 (Kriterium 180), Amt 125/125,
Amtsbezeichnung 69/69, Zeilen der Beratungsfolge 160/168, α ≥ 0,99 zwischen den Kodierern.

**Regeln statt Modell, und genau die validierten.** `prep/structure.py` trägt das Regelwerk als
`struktur-1`; `analyse_draft` folgt `analyse` des Messskripts Zeile für Zeile, die Muster stehen
unverändert im Profil (`[structure]`; ein Test vergleicht jedes Muster mit `ENTWURF` im
Messskript). Gegen das Messskript auf allen 19 091 Rohtexten der Hauptperiode: **0 Dokumente
verschieden** in Abschnitten, Kopffeldern und Quellen (slow-Test), ebenso in 2014 bis 2020 (Block
`duesseldorf-2014`, 22 101 Rohtexte), in der laufenden Periode (4 088) und in Mönchengladbach (658),
geprüft mit einem Messskript gegen die Stores im Cache. Der slow-Test rechnet
die Zahlen der Kodierung aus `validierung/11-struktur-f4/labels.csv` nach (188 und 190 von 200,
125/125, 69/69, 160/168, 73/73, 48/48) und die der Messung (Beschlussvorschlag in 10 506 von 10 784
Dokumenten der Arten, die einen erwarten; Quellen 9 236 / 927 / 343). Die zwölf Fehler am Ende des
Beschlussvorschlags bleiben: eine Schärfung an denselben Labels wäre eine Entwurfsschätzung
(Synergien 2026-11, Konflikt 8); sie kommt nur als `struktur-2` mit frischer Stichprobe. Drei Muster,
die im Entwurf im Code standen, stehen jetzt im Profil, unverändert: die Grußformel des
Unterschriftsblocks (`head.closing`), die Nummernform eines Amts (`head.office`), die Monatsnamen
(`months`, als Sprache in `defaults.toml`).

**Spannen auf dem Rohtext, nicht auf dem Textstore.** Der Textstore ist kleingeschrieben, ohne
Zeilen und erst ab „betrifft"; Überschriften, Zeilen und der Kopf stehen nur im Rohtext (F1,
Punkt 73). Die Spannen tragen `extractor = "struktur-1/pypdf-7.1.0+roh"`, damit keine Position auf
den falschen Text zeigt; ein Vorhaben, das im Textstore sucht, kommt über `flatten_with_offsets`
(Punkt 74) herüber und liest den Abschnitt mit `spans.section_of`. Ebene 1 heißt `kind = "abschnitt"`
und `section == norm`; eine Spanne der Ebene 2 (Finanzen, Klima) nennt in `section` den Abschnitt
um sie herum, die Kopffelder `kopf`. **`value` folgt der Regel von F3** (Entscheidung des
Eigentümers vom 2026-11-24, Review K1): ein Kopffeld trägt den Text an seiner Stelle wörtlich, die
bearbeitete Form (Amt als „Nummer Name", Zeile der Beratungsfolge als „Gremium|Datum|Qualität")
steht in `norm`; ein Abschnitt ist eine Positionsspanne mit leerem `value`, gelesen über
`read_span`, und das Label wie geschrieben fällt weg. Die Amtsbezeichnung im Unterschriftsblock
steht, wie sie geschrieben ist (der Entwurf schrieb den ersten Buchstaben groß). Die Stellenmarke
des Entwurfs für eine Amtsbezeichnung ohne erkannten Titel (eine Spanne von einem Zeichen; gelesen
ergäbe sie das erste Zeichen eines Namens; 702 in 2014 bis 2020, in den anderen Datensätzen keine)
wird nicht geschrieben (Review, Runde 3); `dokumente_kopf` hat dort wie zuvor keine
Amtsbezeichnung. Ein leeres `value` gibt es damit nur bei Abschnitten. `structure_tables` schreibt
die Spannen so (`literal`) und prüft sie mit `check_spans(..., texts=..., positions={"abschnitt"})`;
`analyse_draft` bleibt der Entwurf, damit der Vergleich mit dem Messskript Zeile für Zeile bleibt.

**Was nach dem Entwurf kommt, berührt keine validierte Frage.** (1) Der **Rumpf** (Synergien § 4):
Text im Abschnitt `kopf_*` hinter dem letzten Kopffeld und Text außerhalb jedes Abschnitts zwischen
Betreff und Grußformel, ohne die Zeilen der Überschriften der Ebene 1 -- die Regel, mit der 16 die
Lücke im Messskript schloss. Ein Abschnitt `kopf_*` endet dann am letzten Kopffeld; die Kopffelder
sind vorher gelesen. In der Hauptperiode haben 7 664 Dokumente einen Rumpf (7 857 Spannen), darunter
1 303 Informationsvorlagen der Bezirksvertretungen (Text unter der Beratungsfolge) und die meisten
Anfragen (die Einleitung vor den Fragen). (2) **Kein
Abschnitt der Ebene 1 beginnt in einem anderen**, und **der Beschlussvorschlag bleibt, wie der
Entwurf ihn fand.** Im Entwurf beginnt ein Abschnitt in einem anderen, wo das Regelwerk ihn
nachträglich anfügt: in der Hauptperiode zweimal der Beschlusssatz ohne Überschrift (hypothesis
fand es), einmal im Abschnitt des Amts und einmal im Betreff -- dort beginnen Betreff und
Beschlusssatz an derselben Stelle, und das Dokument hat seit der ersten Fassung keinen Betreff --,
in 2014 bis 2020 305-mal, fast immer ein Betreff unter dem
Formulartitel, der über die nächste Überschrift reicht (275-mal in einen Beschlussvorschlag, 12 in
eine Sachdarstellung, 8 in Fragen). Der vordere Abschnitt endet dann vor dem hinteren -- außer, er
ist der Beschlussvorschlag: in acht Dokumenten von 2014 bis 2020 begann der Betreff unter dem
Formulartitel in einem Beschlussvorschlag (siebenmal aus einem Einleitungssatz, einmal aus einer
Überschrift), und die erste Fassung kürzte den Vorschlag auf „Antrag" (Review K2). Jetzt beginnt, was in einem Beschlussvorschlag beginnt, erst
hinter ihm oder entfällt (hier der Betreff). Geprüft in allen vier Datensätzen: jeder
Beschlussvorschlag gleich dem des Entwurfs, keine Überlappung mehr. (3) **Gremiennamen über `[bodies]`**,
keine zweite Tabelle: `BodyNames` vergleicht einen geschriebenen Namen mit den Namen und Kürzeln aus
`BodyRules` über einen Schlüssel ohne Groß- und Kleinschreibung, Satzzeichen und Genitivendung
(„Ausschusses für Gesundheit und Soziales", „Rates", „Stadtrates" über `city.council`,
„Bezirksvertretung10", „AÖE"); ein Schlüssel für zwei Kürzel fällt weg. Die Sitzung eines Briefs
trägt danach Kürzel und Namen im Nominativ, ohne den Ort dahinter (`head.session_suffix`): 48 von 48
gegen die Kodierung, wörtlich waren es im Entwurf 27. Gegen die OParl-Beratungsfolge desselben
Dokuments stehen 12 763 von 13 232 Kopfzeilen mit Kürzel (96,5 %), über `resolve_organizations` wie
im Schritt `bodies`. Die Zahl ist zum Teil zirkulär (Review N2): die sechs Namen aus Frage 15
stammen aus genau dieser Paarung von Kopfzeile und OParl-Gremium. Ohne ihre Zeilen sind es 10 454
von 10 917 (95,8 %; die Messung zählte 95,7 % mit den Namen des Profils allein); nur diese Zahl
misst die Präzision, und der slow-Test hält beide fest. (4) **Sechs Ausschussnamen**
aus dem Kopf (Frage 15, eigener Commit; KUA, JHA, SCHUA, AGS, HFA, AWM, je n von n Dokumenten mit
genau einer Kopfzeile und genau einem OParl-Gremium): sie ändern Text der Seite und die Zahl der
Kürzel ohne gesicherten Namen, sonst keine Zahl (unten, A/B-Bau). Der Stand der Namen
(`bodies.names_as_of`) ist seitdem der 2026-11-24, und die Quelle im Satz zur Gremientabelle kommt
aus dem Profil (`bodies.names_source`, Review K3): die Vorgabe in `defaults.toml` ist der Satz, den
die Seite fest trug (Mönchengladbach bleibt gleich), Düsseldorf nennt dazu den Kopf der Vorlagen.
Beides ist Anzeige, nicht im Fingerprint, aber im Vorlagen-Hash des Schritts `report` (Punkt 53).
(5) **`rumpf_leer`** zählt den Text hinter dem ersten Betreff ohne die Abschnitte und Felder des
Kopfs, ohne Seitenkopfzeilen und Leerraum; unter 80 Zeichen ist der Rumpf leer. „Was hinter dem Kopf
steht" ging nicht: die alte Vorlagenform setzt die Beratungsfolge ans Ende der ersten Seite, hinter den
Text, und 2014 bis 2020 hatte so 7 773 leere Rümpfe; jetzt 518, davon 387 ohne jeden Text. In der
Hauptperiode 132 (59 ohne Text). Die Messung zählte unter den 278 Dokumenten ohne gefundenen
Beschlussvorschlag 104 mit leerem Rumpf; leer sind 34, die übrigen 70 haben Text ohne Überschrift
unter der Beratungsfolge, in 65 davon einen Beschlusssatz („Bezirksvertretung 8 beschließt …", 58 aus
BV 8). Den sieht der Entwurf nicht, weil er den Beschlusssatz erst hinter dem ganzen Abschnitt
`kopf_beratungsfolge` sucht -- ein Kandidat für `struktur-2` (`docs/todo.md`, Punkt 14), nicht für
diesen Bau.

**Je Korpus-ID eine Zeile, auch ohne Rohtext.** `dokumente_kopf` hat genau die IDs des Korpus
(`one_row_per_document`), zwei IDs mit derselben PDF-Datei bekommen beide Spannen und Zeile
(Synergien § 1). Ohne Rohtext -- auf Pages für jedes Profil außer der Hauptperiode, Konflikt 14 --
läuft der Schritt und schreibt keine Spanne und leere Zeilen; `extractor` ist dann null.
Amtsbezeichnung und Unterzeichnerrolle stammen aus den Listen des Profils (Nachbedingung), kein Feld
trägt einen Namen.

**Ein früher Schritt.** `sections` steht als `early_steps` unmittelbar vor `weights` (Punkt 74),
weil 16 die Stelle eines Treffers aus den Abschnitten rechnet und `weights` sie liest; er liest
Korpus, Rohtextstore und die Beratungsfolge und besteht `check_step_order` in jedem Paketprofil.
Laufzeit beim ersten Lauf je Profil am 2026-11-24 (Worktree, `nice -n 10`, Lastmittel 17 bis 19
durch andere Läufe): Hauptperiode 30,0 s (19 108 Dokumente, 19 091 mit Rohtext, 145 269 Spannen),
mit Vergleich 37,1 s, 2014 bis 2020 20,4 s (22 215, 22 101, 162 306), laufende Periode 9,6 s (4 095,
4 088, 30 093), Mönchengladbach 1,3 s (2 895, 658, 5 805). Der erste Lauf über 2014 bis 2020 brach ab:
`name_key` nahm „²" als Zahl (`isdigit` statt `isdecimal`); seitdem prüft eine hypothesis-Eigenschaft
den Schlüssel für jeden Text.

**Geprüft, dass die Seite gleich bleibt.** A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt 66
(`ab/ab_bau.sh`, `ab/ab_vergleich.py` auf xtraspace, je `POLARS_MAX_THREADS=4`,
`OMP_NUM_THREADS=2`, in der Reihenfolge von `pages.yml` seit Punkt 78), `main` (`00e1791`, v0.27.0)
gegen den Branch nach Runde 2 des Reviews (2026-11-26): unter `site/` 235 Dateien in beiden, 3
Abweichungen, alle aus Frage 15 und K3 --
`index.html` der Hauptperiode, von 2014 bis 2020 und der laufenden Periode nennen die sechs
Ausschüsse mit Namen statt Kürzel (Themen, Gremientabelle, Legende), und der Satz zur Gremientabelle
trägt den neuen Stand (24.11.2026 statt 14.10.2026), die Quelle mit dem Kopf der Vorlagen und die
Zahl der Kürzel ohne gesicherten Namen (5 statt 11, in den Perioden 3 statt 9). Sonst ändert sich
keine Zahl; Mönchengladbach, `vergleich.html` und die Feeds sind gleich. Über die ganzen Datenwurzeln
881 gegen 893 Dateien: neu sind je Profil die beiden Dateien von `sections` mit Stamp (in den drei Profilen
ohne Rohtextpaket ohne Spannen und mit leeren Zeilen), anders sonst nur die drei Seiten (und ihre
Kopien unter den Profilordnern) und Stamps (der Fingerprint trägt jetzt `[structure]`). Keine Datei
unter `site/` stammt aus `sections`; die Kopftabelle kommt erst mit Stufe 3 als Download. Die
Hauptperiode schreibt 0,89 MB Abschnitte (seit die Abschnitte kein Label mehr tragen) und 0,21 MB
Kopf.

**Verworfen.** Das Ende des Beschlussvorschlags an den Labels nachschärfen (Konflikt 8); eine
Zusatzspalte `quelle` an den Spannen (die Quelle steht in `dokumente_kopf`, Frage 9.3); `start` und
`end` als UInt32 und die Folge `id, start` aus dem Bauplan (F3 hat Int64 und `id, start, end, kind`,
Konflikt 2); den Rumpf in `analyse_draft` (dann wäre der Vergleich mit dem Messskript nicht mehr
Zeile für Zeile); eine Tabelle der Gremiennamen im Profil neben `[bodies]`; den Gremiennamen der
Sitzung aus der OParl-Folge raten, wo der Text ihn nicht trifft (die Folge hält die tatsächliche
Beratung, der Brief die geplante); ein eigenes Paket (die Ausgaben rechnen in rund 20 s aus dem
Rohtextpaket); `split_lines` ohne regulären Ausdruck für crosshair (es geht auch mit ihm, Exit 0).

## 82. Kennungen und Beträge als Spannen: vier Arten in der validierten Fassung, Rolle und Fristfunktion verworfen, Haushalt und Rechtsgrundlage gefallen (Vorhaben 12, 2026-11-24)

Vorhaben 12 der Vorverarbeitung (`docs/plans/12-kennungen.md`, § 4 bis § 6 und § 10), Stufe 2.
Die Messung hat sechs Arten von Kennungen mit regulären Ausdrücken gezogen und gegen zwei
KI-Kodierer und einen Schlichter geprüft (kein menschlicher Goldstandard; in Runde 2 waren Kodierer
und Schlichter dasselbe Modell, Frage 19). Kriterium je Art: Präzision ≥ 0,95 und Recall ≥ 0,85,
streng; die Rolle eines Betrags und die Funktion `frist` eines Termins je ≥ 0,8.

**Was gebaut ist**, genau in der Fassung, die bestanden hat, ohne nachgeschärfte Regel:

- **Bauleitplanung** (`bplan`, `fnp`), Fassung 1: Präzision 1,000 (n 100), Recall 64/71.
- **Betrag** (`betrag`), Fassung 1, ohne Rolle: Präzision 0,962, Recall 84/88. Die Korrekturen der
  Fassung 2 („+" in der Spanne, „Euro" vorn, kein Jahr im Tabellenkopf) bestanden die Bestätigung
  nicht (Schicht neu 18/20, verlangt höchstens ein Fehler) und fehlen mit Absicht; „2021 Mio. EUR"
  bleibt ein Betrag, „Euro 172.000" bleibt unerkannt (Tests halten beides fest).
- **Termin** (`termin`), Fassung 2, ohne Funktion: an der Bestätigung 30 von 30.
- **Verwaltungseinheit** (`amt`, `dezernat`), Fassung 2: Präzision 0,956, Recall 71/80; knapp, die
  untere Intervallgrenze liegt bei 0,85.

**Verworfen nach der Messung** (die Messungen bleiben im Messdokument): die **Rolle** eines Betrags
(Kosten, Zuschuss, Ertrag, Verfügungsmittel …; Übereinstimmung 0,508 [0,389; 0,626], n 98 — die
Regeln der Kodierer brauchen Wissen über Dokument und Tabelle, das Schlüsselwörter im Satz nicht
tragen), die **Funktion** `frist` eines Termins (Präzision der Klasse 15/30, Übereinstimmung über vier
Klassen 0,613), der **Haushalt** (Produkt, Sachkonto, PSP-Element, Investition; Fassung 2 mit
Präzision 1,000, aber Recall 0,716 an der Bestätigung) und die **Rechtsgrundlage** (Fassung 2 mit
Präzision 0,861; auch die vorab festgelegte Rückfallregel „nur Gesetz und erster Paragraph" verfehlte
das Gesetz im Normwert mit 0,805). Wer Rolle oder Frist für 21 oder 29 braucht, misst neu, mit einem
Modell über F5 an frischen Labels; die Vorschläge S1 bis S10 des Schlichters liegen für eine Fassung 3
bereit (Messdokument § 9).

**Ausgabe.** Der Beitrag `12-kennungen` (`georep.enrich.identifiers`) bringt einen Offline-Schritt
`identifiers` vor `report`, nur mit `identifiers.enabled` (beide Stadtprofile, die Perioden erben).
Er schreibt `processed/kennungen.parquet`: Spannen nach F3 auf dem Rohtext aus F1, dahinter `attr`
mit der **Form**, nie einer Deutung (Punkt 74): `je` und `spanne` bei Beträgen, `tag`, `monat`,
`quartal`, `jahr`, `relativ` bei Terminen, `kopf`, `name`, `nummer`, `text`, `wort` bei Ämtern.
`extractor` ist `kennungen-1/` vor dem Extraktor des Rohtexts. **Jede** Korpus-ID, deren Paper die
Datei trägt, bekommt ihre Spannen (Synergien 2026-11, § 1, Konflikt 4), nicht nur die kleinste wie in
der Messung. `section` kommt aus den Abschnitten von Vorhaben 11 (`dokumente_abschnitte.parquet`
als optionale Eingabe, `spans.section_of`: der Abschnitt der Ebene 1, in dem der Anfang einer
Spanne liegt; nachgezogen nach Punkt 81); ohne die Datei bleibt `section` leer. In der Hauptperiode
tragen danach 100 665 von 116 349 Spannen einen Abschnitt (am häufigsten `sachdarstellung` 40 087,
`kopf_beratungsfolge` 13 536, `beschlussvorschlag` 12 203, `rumpf` 11 593, `kopf_amt` 10 055;
2026-11-26). Ein Vertrag prüft,
dass die Abschnitte auf demselben Rohtext stehen (ihr `extractor` endet mit dem des Stores). Ohne Rohtext (ein Profil ohne PDFs und ohne Rohtextpaket, auf Pages alle außer der
Hauptperiode) schreibt der Schritt dieselbe Tabelle leer und sagt es, statt den Lauf scheitern zu
lassen (Konflikt 14). Kein Paket: der Schritt rechnet aus dem Rohtextpaket in unter einer Minute.

**Die Sprache in `defaults.toml`, die Stadt im Profil.** Schlüsselwörter der Bauleitplanung,
Einheiten, Faktoren und Spannenwörter der Beträge, Monate, Zusätze und relative Termine, Amtswörter
und die Schwellen des Ämterverzeichnisses stehen stadtneutral in `[identifiers.plans]`, `.amounts`,
`.dates` und `.offices`; das Nummernformat der Bebauungspläne mit seinen Normalformen
(`[[identifiers.plans.norms]]`: Muster und Vorlage, die erste passende gilt), das Kopffeld des
federführenden Amts, eine zweite Nummernform („FB 64") und Einheiten, die eine Stadt ohne
Verzeichnis nennt („Bezirksverwaltungsstelle 10"), im Stadtprofil. Im Code steht nur, wie Ziffern,
Leerraum und die Teile zusammengesetzt sind; ein leerer Teil trifft nie. Die Muster aus dem
Messskript stehen wörtlich in den Settings, jedes Teil in eine nicht fangende Gruppe gesetzt, was
nichts an der Bedeutung ändert. Das **Ämterverzeichnis** (Name → Nummer) entsteht je Lauf aus den
Kopffeldern des Korpus, wie in der Messung; die Synergie nennt dafür `dokumente_kopf` von 11.
**Verglichen nach dem Merge von 11** (Konflikt 5, slow-Test `tests/golden/test_identifiers_heads.py`,
2026-11-26): mit denselben Schwellen aus `dokumente_kopf` gebaut, enthielte das Verzeichnis alle 55
Namen von 12 mit derselben Nummer und sieben mehr, und keiner davon ist ein Amt, das 12 im Text suchen
sollte (zwei Ämter in einer Kopfzeile wie „Amt für Gebäudemanagement 67 - Stadtentwässerungsbetrieb",
ein Verein hinter dem Sportamt, „Stadtkämmerin"). 12 bleibt darum beim validierten Verzeichnis aus
den eigenen Kopffeldern; ein Wechsel auf das von 11 wäre eine neue Regel mit neuer Messung. Das
**federführende Amt** selbst (die erste Kopfspanne von 12 gegen `amt_nr`, ohne Nummer `amt_name`
von 11): in 9 994 Dokumenten nennen beide eines, in 9 957 dasselbe; die 37 übrigen sind Kopffelder
mit dreistelliger Unternummer oder ohne Bindestrich („40/603 - VHS", „02/0 Stadtkämmerin"), deren
Nummer die Kopfform von 12 nicht trifft, sodass Fassung 2 den ganzen Wert als Norm nimmt; ein
Dokument hat nur bei 12 ein Kopf-Amt. Nutzer des federführenden Amts lesen es aus 11 (Konflikt 5).
Ein Dezernat kommt nur aus dem Text („Dezernat 06"), keine Profiltabelle (sammelt 24).

**Verträge.** `identifier_spans` ist die Batch-Grenze: F3 mit `attr` dahinter (`check_spans`),
`value` wörtlich der Text an der Stelle (Review N2; seit Vorhaben 11 mit der Prüfung von F3,
`check_spans(..., texts=..., positions=())`: 12 hat keine Positionsspanne, ein leeres `value` ist
also ein Fehler), ein Betrag als Dezimalzahl mit zwei Stellen, ein Termin in einer Normform des Codebuchs
.2, jede Form zu
ihrer Art, und innerhalb einer Art keine zwei überlappenden Spannen eines Dokuments — **außer einem
Paar bei Ämtern**: Fassung 2 nimmt die Nummer vor einem Namen in die Spanne („10 – Hauptamt"), und
eine Nummernnennung direkt davor („Amt 10") bleibt eine eigene Spanne. So validiert, gezählt am
2026-11-24: 3 Paare in der Hauptperiode, 8 in 2014 bis 2020, 111 in Mönchengladbach (Ämterlisten in
sechs Dokumenten). Erlaubt ist genau dieses Paar (`MAY_OVERLAP`, `overlaps_are_allowed`; Review N1):
die frühere Spanne mit der Form `nummer`, die spätere mit `name`, die hinter ihr beginnt, nicht vor
ihr endet und mit einer Ziffer anfängt, vor der in der Nummer keine Ziffer steht; nicht die ganze
Art. `find_identifiers` prüft je Text, dass jede Spanne im Text liegt und die Folge
stimmt (`deal.safe`, kein `deal.pure`: die Funktion läuft je Dokument). `iso_date` steht in
`VERIFY_TARGETS` (ein Datum genau dann, wenn der Kalender den Tag zwischen 1950 und 2040 kennt;
crosshair einzeln 23 s, „Not confirmed"). Eine Zahl mit mehr Stellen, als `Decimal` hält, ist kein
Betrag statt eines Absturzes; im Korpus kommt sie nicht vor.

**Geprüft gegen die Messung.** Dieselben Spannen wie das Messskript (Bauleitplanung und Betrag aus
`kennungen-messung-v1`, Termin und Verwaltungseinheit aus `-v2`, Form wie oben abgebildet), Dokument
für Dokument auf den Rohtextstores vom 2026-11-24: **0 Abweichungen** unter 116 349 Spannen der
Hauptperiode, 151 205 von 2014 bis 2020, 22 357 ab 2025 und 7 428 in Mönchengladbach; die
Ämterverzeichnisse gleich, auch in der Folge (55, 35, 29 und 14 Namen). **Mit einer Ausnahme seit dem
Review** (K1, 2026-11-24): die Nummer vor einem Namen („64 - Amt für Wohnungswesen") nahm die
Messfassung um die Länge des Treffers nach vorn; trifft das `$` des Musters vor einem Zeilenwechsel
am Ende des Fensters („Amt 19 - ⏎Amt für …"), ist der Treffer ein Zeichen kürzer, und die Spanne
begann mitten in der Nummer. Der Bau beginnt sie an der Fundstelle. Das ist ein Fehler der Grenzen,
nicht der Regel, und er ändert genau acht Spannen um ein Zeichen, bei gleicher Norm: eine in der
Hauptperiode (`00472505.pdf`), eine von 2014 bis 2020 (`00300693.pdf`), sechs in zwei Dokumenten in
Mönchengladbach; keine lag in einer Aufgabe der Stichprobe. Der Vergleich gegen das Messskript zählt
diese acht als erwartete Abweichung, sonst 0. Ein slow-Test
(`tests/golden/test_identifiers_labels.py`) rechnet aus dem Rohtextpaket die Zahlen nach, auf denen
das Urteil steht: Bauleitplanung 1,000 und 64/71, Betrag 0,962 und 84/88 an Runde 1, Termin 30/30
und Verwaltungseinheit 0,956 und 71/80 an Runde 2, dazu die Entwurfsschätzung der Fassung 2 an
Runde 1 (Termin 1,000 und 200/200, Verwaltungseinheit 0,976 und 51/52). Ein Umbau, der eine davon
ändert, ist kein Refactoring. Nebenbefund: die Quote einer Schicht zählt im Messskript über alle
Arten der Stichprobe, und „neu" steht in Runde 2 in fünf Arten; je Art gerechnet wäre die Präzision
der Verwaltungseinheit 0,962 statt 0,956, die der Rechtsgrundlage 0,859 statt 0,861. Kein Urteil
ändert sich (Nachtrag in § 4.4 des Messdokuments).

**Geprüft, dass die Seite gleich bleibt.** A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt 66
(`ab/ab_bau.sh`, `ab/ab_vergleich.py`), `main` bei `62ea8eb` (v0.30.0, nach Vorhaben 11) gegen den
Branch darauf, beide mit `POLARS_MAX_THREADS=4` und `OMP_NUM_THREADS=2` (2026-11-26): unter `site/`
235 Dateien in beiden, 0 Abweichungen. Über die ganzen Datenwurzeln 924 gegen 932 Dateien: neu sind
nur die vier `kennungen.parquet` mit ihren Stamps; an den 113 übrigen Stamps, die abweichen, ändern
sich allein der Settings-Fingerprint (ein neuer Schlüssel) und die Zeit `written`, an zweien dazu
die Pfade der Datenwurzel in den Schlüsseln der Eingaben (Punkt 76), nicht ihre Hashes. Aus den
Paketen rechnet nur die Hauptperiode Spannen; 2014 bis 2020, ab 2025 und Mönchengladbach haben dort
keinen Rohtext und schreiben die Tabelle leer. Lokal, mit Rohtext für alle Profile, tragen 100 665
von 116 349 Spannen der Hauptperiode einen Abschnitt, 141 381 von 151 205 von 2014 bis 2020,
18 946 von 22 357 ab 2025 und 6 471 von 7 428 in Mönchengladbach.

**Laufzeit.** Der Schritt braucht für die Hauptperiode 36 bis 60 s, für 2014 bis 2020 51 bis 74 s,
ab 2025 6 bis 14 s, für Mönchengladbach 3 bis 4 s, in einem Prozess und unter Fremdlast
(Lastmittel 8 bis 50 am 2026-11-24); das Ämterverzeichnis davon unter einer Sekunde. Auf Pages
läuft er für die Hauptperiode zweimal: im Profil `duesseldorf` und im Profil
`duesseldorf-vergleich`, das im selben Ordner rechnet (im A/B-Bau 46,9 und 46,7 s). Den zweiten Lauf
verursacht nicht 12: `compare.period` steht im globalen Settings-Fingerprint, darum gilt im
Vergleichsprofil jeder Stamp des Ordners als veraltet, und jeder Schritt der Hauptperiode rechnet
dort noch einmal (im A/B-Bau 27 ausgeführt, übersprungen nur die sieben Netzschritte).
`nox -s bench` hat eine Stufe über 200 Rohtexte der Hauptperiode
(`test_identifiers_over_200_raw_texts`).

**Verworfen.** Ein früher Schritt vor `weights` (keiner der Kernschritte und kein früher Beitrag liest
die Spannen; 16 hat die Plannummern verworfen, § 3 seines Messdokuments); `pack --identifiers`
(Konflikt 12); eine Liste der Ämter im Profil (die Synergie will sie je Lauf aus den Kopffeldern);
eine Profiltabelle Amt → Dezernat (24 sammelt sie); die Fassung 2 auch für Beträge (bestand nicht);
die Rolle als Schalter, der aus ist (eine Regel unter dem Kriterium gehört nicht in den Code, sondern
ins Messdokument); `;r10` und `;iso` als eigene Formen in `attr` (der Bauplan nennt fünf Formen eines
Termins; eine vervollständigte erste Angabe ist ein Tag); die Extraktoren in `VERIFY_TARGETS` (ihre
Regeln tragen `re.Pattern`, dasselbe Werkzeugartefakt wie bei `parse_reference`; ihre Eigenschaften
prüft `tests/property/test_identifiers_props.py`).

## 83. Kurzfassungen: gebaut, validiert, aber aus; nur lokal, Treue deterministisch, die Rolle in der Eingabe (Vorhaben 20, 2026-11-26)

**Ergebnis zuerst.** Gebaut und an der Messung validiert sind die Eingabe Fassung 2 und die
deterministische Treueprüfung. Die Nachmessung von `unbelegt` vor dem Stapellauf (Messdokument
§ 5.4, Grenze 2 von 50) hat **beide Modelle verworfen**: `gemma4` 4 von 50 (in der ersten
Bewertung ohne Rolle 12 von 50), `qwen3.6:27b` 5 von 50 (Entscheidung des Supervisors, weil α
0,544 und ein Kodierer allein unter der Grenze; die Zahl liegt mehr als doppelt darüber, das
geschichtete Intervall ganz). **Darum gibt es keinen Stapellauf, und der Schritt ist in allen
Profilen aus** (`summaries.enabled = false`; an, startete jedes `georep run --models`, etwa für die
Einbettungen von 18, einen Stapel von 5 bis 8 GPU-Stunden). Er bleibt im Paket und lässt sich für
eine spätere Messung mit `GEOREP_SUMMARIES__ENABLED=true` einschalten; `summaries.model` bleibt
`gemma4` (weniger Beanstandungen als qwen, 2,7-mal schneller). Weiter ginge es nur mit einem
Codebuch Fassung 2 (Fragen 20.10, 20.11, 20.15: Rollen, Verallgemeinerung, Modalität, Kopfdaten,
gestrichene Einschränkungen) an einer frischen Stichprobe, als eigenes Vorhaben. Die
deterministische Prüfung und die Kodierer fanden in beiden Nachmessungen **disjunkte** Fehler (0
und 2 gegen 4 und 5): die Prüfung ersetzt die Bewertung nicht.

Vorhaben 20 der Vorverarbeitung (`docs/plans/20-kurzfassungen.md`: Urteil § 5.3, Bauplan § 6,
Nachmessung § 5.4, Synergie § 10), Stufe 2. Zwei, drei Sätze je Dokument mit einem lokalen Modell,
für den Vorlagenspiegel einer Fraktion (Vorhaben 29). Die Nummer bekommt der Eintrag beim Merge.

**Nie veröffentlicht, darum nie unter `data_root`.** Konrads Antwort auf Frage 6 (2026-11-23):
Kurzfassungen nein. Beide Tabellen des Schritts `summaries` liegen unter
`cache_root/<profil>/summaries/` (`summaries_files`), die Antworten selbst im Modellcache von F5.
`report`, `publish` und `pack` lesen nur unter `data_root` und aus `package_files`; ein Test hält
beides fest. `georep summary` liest lokal und schreibt eine HTML-Liste nur in denselben Ordner
(Frage 20.3). Ohne `--models` wird der Schritt übersprungen, und kein Paket ersetzt ihn. Verworfen:
die Tabellen unter `processed/` mit einer Ausnahme in `publish` und `pack` (eine Ausnahme mehr, die
der nächste Umbau vergisst); ein Paket wie bei den Nachbarn von Vorhaben 18 (Frage 6).

**Die Treue prüft eine reine Funktion, die Rolle prüfen Kodierer.** `enrich.fidelity` sucht in jeder
Kurzfassung Zahlen, Daten, Drucksachennummern und Namen und sieht nach, ob ihre Eingabe sie trägt
(Messdokument § 3.1), mit Klasse e in Fassung 2 (§ 5.2: ein seltenes großgeschriebenes Wort ist nur
ein Name, wenn es kein Abstraktum, kein Wort und keine Zusammensetzung des Korpus ist) und den drei
Korrekturen aus Frage 20.12 („ca. März 2022", „Dezember2022", Votum/Voten). Gegen das Messskript
Dokument für Dokument an den 800 Kurzfassungen beider Runden: dasselbe Lexikon, dieselben Urteile
bis auf genau diese Korrekturen. Drucksachennummern liest sie mit den Formen des Stadtprofils aus
Vorhaben 14 statt mit einem eigenen Muster (kein Stadtwort im Code; an den 800 ohne Folge).
Personennamen (Regel 5) zählt sie daneben (`personennamen`, nicht in `ok`): in 2014 bis 2020
beginnt der Rumpf bei rund 4 095 Dokumenten mit dem Namen aus der Kopfzeile des Dezernats (Review
von 11), und ein abgeschriebener Name ist belegt. Was sie nicht sieht, ist der wichtigste Fehler:
eine falsche Rolle (Rat oder Bezirksvertretung als Antragsteller einer Vorlage der Verwaltung,
§ 4.1); den misst die Frage `unbelegt` der Kodier-Agenten, vor dem Stapellauf an frischen 50
(§ 5.4). Verworfen: die beanstandeten Angaben als Datei (sie sind Text der Kurzfassung; `georep
summary` rechnet sie nach); eine Rundungsregel (Regel 3 verlangt die Zahl, wie sie dasteht).

**gemma4 als Modell des Schalters, und es steht unter `[summaries]`.** Nach dem Kriterium aus § 3.1 bestand nur
gemma Teil 1 (0,984 an frischen 200), und es rechnet ein Drittel der Zeit von `qwen3.6:27b`. Das
Modell steht nicht in `[ml.generation]`, weil Vorhaben 19 dort ein anderes nennen darf; die
Optionen kommen von dort. Der Client entsteht erst bei Bedarf (`DeferredGenerator`, wie
`DeferredEmbedder` in Punkt 77).

**Eingabe und Prompt Fassung 2: die Rolle steht in der Eingabe.** Eine von vier Kurzfassungen von
gemma sagte in der Bewertung falsch, wer etwas will (§ 5.3, Vorbehalt 2). Statt die Rolle raten zu
lassen, nennt die Eingabe sie: `Absender` aus der Urheberklasse (Option 04) und den Fraktionen aus
Vorhaben 15; `Beratung` aus der Beratungsfolge im Kopf (Vorhaben 11) in ihrer Folge und mit
Qualität („Rat (Entscheidung)"), sonst aus der OParl-Folge (Punkt 58) und dem Gremium der Nummer.
Die Qualität ist in 11 validiert (Tripel je Zeile 160 von 168, mit dem Platzhalter „-" 168 von
168), die Folge gegen dieselben Labels 27 von 27; OParl kennt keine Folge. Regel 1 sagt, wie die
Zeilen zu lesen sind, Regel 3 verbietet selbst gezählte und gerechnete Zahlen (Frage 20.12),
Regel 5 nimmt Straßennamen aus (Frage 20.8). Die Abschnitte sind Positionsspannen von 11; ihren
Text liest nur `read_span` mit den Seitenmustern des Profils, keine eigene Säuberung. Nach einer
Kürzung folgt nichts mehr (wie § 3.1 es beschreibt; das Messskript nahm danach noch Abschnitte),
ohne Text nach dem Kopf (`rumpf_leer` oder weniger als 50 Zeichen) gibt es keine Eingabe (Frage
20.6). Weil `read_span` anders liest als die Messung, trifft der Bau deren Cache nicht; das ist
hingenommen. Verworfen: die Rollen aus 14 (sie sagen, wie ein Dokument zu einem anderen steht,
nicht wer es einbringt); eine Zeile „beschließt" aus OParl (die Folge fehlt dort).

## 84. Dubletten und Dokumentfamilien: verworfen, es gibt kaum Dubletten (Vorhaben 13, 2026-11-23)

**Ergebnis zuerst.** Vorhaben 13 der Vorverarbeitung ist nach seiner vorab festgelegten Regel
**verworfen**; es gibt keinen Schritt `families`, keine Datei `dokumentfamilien.parquet`, keine
Gewichtsvariante `familie` und keine Familie im Dokumentdialog. Der Befund ist „es gibt kaum
Dubletten": selbst an der besten Grenze lägen nur 0,5 % der Dokumente in Familien, und kein Wahlbezirk
verlöre mehr als 1,4 % seiner Treffer. Messdokument: `docs/plans/13-dubletten.md` (Urteil § 5, Regeln
des Schlichters § 9), Messskript daneben, Codebuch, Stichprobe und Labels unter
`validierung/13-dubletten/`. Die Nummer bekommt der Eintrag beim Merge.

**Verfahren und Kriterium.** Wort-Shingles der Länge 5 über den Korpustext, MinHash mit LSH in 32
Bändern zu 4 Zeilen, für jeden Kandidaten die exakte Jaccard-Ähnlichkeit; nur die Hauptdatei, wie
die Trefferquote. Kriterium aus dem Briefing (Meta-Plan § 11), unverändert: Präzision ≥ 0,95; weiter
nur, wenn mindestens 3 % der Dokumente in Familien liegen oder ein Wahlbezirk mindestens 5 % seiner
Treffer verliert. Vorab festgelegt war die Grenze τ* als kleinste der Grenzen 0,70, 0,80, 0,85, 0,90,
0,95, an der die gewichtete Präzision über alle Paare mit J ≥ τ* mindestens 0,95 erreicht.

**Gemessen** an 200 Paaren, kodiert von zwei KI-Kodierern und einem Schlichter desselben Modells
(α 0,941; Frage 19): keine Grenze erreicht 0,95. Am nächsten liegt τ = 0,9 mit 0,948 (0,866–0,964,
58 kodierte Paare); darunter fällt die Präzision auf 0,745 (0,85), 0,538 (0,8) und 0,411 (0,7), und
ab 0,95 ist sie 0,812, weil dort drei wortgleiche Förderanträge verschiedener Jahre liegen. Das Urteil
hängt nicht an der knappen Zahl bei 0,9: läge sie über 0,95, verfehlten 0,5 % der Dokumente und
1,4 % Verlust beide Schwellen für „weiter".

**Was bleibt.** Der MinHash-Prototyp und seine Parameter gingen an Vorhaben 23 (dort ebenfalls
verworfen, nächster Eintrag); Fortschreibungen (`X/1`) deckt Vorhaben 14 über seine Nachtragskanten
ab; Verteilervorlagen (dieselbe Vorlage an mehrere Bezirksvertretungen) sind dort zurückgestellt
(`docs/plans/14-vorgaenge.md`, Frage 9.13).

**Was eine Neumessung bräuchte.** Ein neues Vorhaben, keine zweite Runde an diesen Labels: ein
Codebuch Fassung 2 mit den Regeln des Schlichters (ein an ein Haushaltsjahr gebundener Antrag ist je
Jahr eine eigene Sache; die Endung `/1` ist ein Hinweis, kein Kriterium; dieselbe Vorlage an mehrere
Bezirksvertretungen ist „gleich"; eine Wahl mit getauschter Person zur selben Besetzung ist „fast
gleich"), dabei die Grenze für einen ungeklärten Längenrest vorab festgelegt (der Schlichter hat 2 %
selbst gesetzt), eine frische Stichprobe und ein vorab festgelegtes Kriterium. Lohnen würde sie sich
nur, wenn sich die Lage ändert, etwa wenn Anlagen in den Korpus kommen (Verteilervorlagen
unterscheiden sich oft nur dort, Messdokument Frage 13.3).

## 85. Textübernahme: verworfen, die Art der Übernahme trägt nicht (Vorhaben 23, 2026-11-23)

**Ergebnis zuerst.** Vorhaben 23 der Vorverarbeitung ist nach seiner vorab festgelegten Regel
**verworfen**; es gibt keinen Schritt `reuse`, keine Datei `textuebernahmen.parquet` und keinen
Abschnitt auf `akteure.html`. Gemeinsamen Text findet das Verfahren zuverlässig, aber seine Einteilung
in politische Arten erreicht das Kriterium nicht. Messdokument: `docs/plans/23-textuebernahme.md`
(Urteil § 5, Regeln des Schlichters § 9), Messskript daneben, Codebuch und Stichprobe unter
`validierung/23-textuebernahme/`; die Fremddaten (Korpus von Cherif, CC BY 4.0) liegen nur lokal. Die
Nummer bekommt der Eintrag beim Merge.

**Verfahren und Kriterium.** Kandidaten über MinHash auf Fenstern von rund 50 Wörtern (Prototyp aus
Vorhaben 13), lokale Ausrichtung (Smith-Waterman auf Wörtern) auf den Kandidatenpaaren, dann eine
Regel über Metadaten (Urheber, Parteien, Gremium, Verweise, Floskeln), die jedem Paar eine Art gibt.
Kriterium aus dem Briefing: Präzision ≥ 0,9; weiter nur, wenn es Familien über Partei- oder
Stadtgrenzen gibt. Vom Supervisor vor der Kodierung festgelegt (Frage 32): die Präzision gilt **je
politischer Art** (Musterantrag; Übernahme über Fraktionsgrenzen), nicht über beide zusammen, damit
837 gute Musteranträge nicht 76 schwache Übernahmen mittragen. Bauen nur, wenn beide Arten 0,9
erreichen; umbauen, wenn nur die Musteranträge es tun; sonst verwerfen.

**Gemessen** an 100 Paaren, kodiert von zwei KI-Kodierern und einem Schlichter desselben Modells
(α 0,950; Frage 19): Musteranträge 0,889 (0,633–0,972), Übernahmen über Fraktionsgrenzen 0,296
(0,117–0,595). Gemeinsamer Text waren alle 92 kodierten Paare über der Zufallsgrenze, der Recall der
Kandidatensuche liegt bei 91,3 %. Familien über Grenzen gibt es (9 bestätigte Paare über
Fraktionsgrenzen, 3 über Stadtgrenzen), aber die Musteranträge verfehlen 0,9, also verworfen. Die
Entscheidung ist knapp: die Lesart eines einzigen Grenzfalls bewegt den Wert zwischen 0,64 und 0,89,
ohne ihn liegt er bei 0,894. Der Befund: Textübernahme zwischen Ratsdokumenten ist vor allem
Wiederholung derselben Urheber (24 398 Paare), Formular (68 125) und Zitat (Recht 14 352, Verfahren
4 193); politische Übernahme ist selten, Übernahmen über Fraktionsgrenzen gibt es nur in der
Größenordnung von 20 bis 25.

**Was eine Neumessung bräuchte** (`docs/todo.md`, „Textübernahme neu messen"). Ein eigenes Vorhaben
mit neuer Regel, neuem Codebuch und frischer Stichprobe, nicht eine zweite Runde an diesen Labels:
die starken Kanten aus Vorhaben 14 statt der Nummernsuche im Text (die Fehler sind vor allem Zitate
im selben Verfahren), die Abschnitte aus Vorhaben 11 (Briefkopf, Unterschrift) gegen Bausteine, die
Antragsteller aus Vorhaben 15 als Datei, die Regeln des Schlichters für ein Codebuch Fassung 2
(Musterantrag nur zwischen Gliederungen derselben Partei, ein Baustein-Test, die Regel der dritten
Quelle, gleiche Forderungen zum selben Haushaltsposten), dazu optional Einbettungen aus Vorhaben 18
als zweite Kandidatenquelle und die Musteranträge der kommunalpolitischen Vereinigungen als Korpus,
um Vorlage und Wiederholung zu trennen (Messdokument, Fragen 23.2, 23.4). Die lokale Ausrichtung
bleibt als Werkzeug im Messskript, etwa für Vorhaben 25.

## 86. Abschnitte aus fremden Beiträgen: ein Feld am Beitrag, Folge nach Rang, eine fehlende Zielseite entfällt mit einer Zeile im Log (Vorarbeit V1, 2026-11-27)

Vorarbeit V1 aus `docs/plan-zeigen-2026-11.md`, § 4, der F2-Nachzug, den die Synergien 2026-11
(§ 1, „Unterseiten, die mehrere Vorhaben füllen") vor Stufe 3 von 23, 24 und 26 bis 28 verlangt
haben. Gebaut auf `fund/V1-abschnitte` ab `main` `b5d7038` (`v0.32.1`). Die Nummer bekommt der
Eintrag beim Merge.

**Das Problem.** F2 (Punkt 69) kennt nur die Seite eines Beitrags: `Contribution.pages` trägt
`report.pages.Page`, und deren Vorlage schreibt der Beitrag selbst. 26 soll drei Abschnitte auf
`vorgaenge.html` von 14 zeigen, 28 (später 24 und 27) einen auf `akteure.html` von 15. Ohne Nachzug
hätte 26 die Seite von 14 ändern müssen, also genau die fremde Datei, die das Register vermeiden
soll.

**Die Lösung.** `Contribution.sections` ist ein Tupel von `report.pages.PageSection` mit Zielseite
(`page`, ein `Page.name`), Name, Rang, Eingaben, Daten, optionalem Schalter und erlaubten Links; das
Feld steht am Ende der Dataclass wie `early_steps` (Punkt 74). Die Vorlage liegt unter
`templates/pages/<seite>/<name>.html.j2`, daneben optional `<name>.css` und `<name>.js`; der Pfad
folgt aus Seite und Name, wie bei `Page`, darum steht er nicht als Feld da.

- `sections_for(settings)` gibt die Abschnitte je gebauter Seite zurück, nach Rang aufsteigend, bei
  gleichem Rang nach Name, nie nach der Folge des Registers. Die folgt der Merge-Reihenfolge
  (Synergien, § 2.1) und soll auf der Seite nicht zu sehen sein.
- Der Rahmen `templates/page.html.j2` bindet die Abschnitte nach dem eigenen Inhalt der Seite ein,
  in `<main>`, jeden in `<section id="<name>">` und mit seinen eigenen Daten als `data`
  (`{% with %}`), sodass er die Daten der Seite nicht sieht und seine Vorlage nicht an deren Namen
  hängt. Ihr CSS steht hinter dem der Seite, ihr JavaScript ebenso, aber je Datei in einem eigenen
  `<script>` (Review N2): ein Fehler im Skript eines Gasts hält das der Seite und der übrigen Gäste
  nicht an. Die Hauptseite fasst das JavaScript ihrer Abschnitte weiter in einem Block zusammen und
  bleibt, wie sie ist. CSS und JavaScript liest `render_page` jetzt über den Jinja-Loader statt über
  `importlib.resources`, damit die Testnaht `env` auch sie trägt; für die Dateien im Paket ist das
  derselbe Inhalt, auch bei den Zeilenenden: `\r\n` und `\r` werden `\n` wie bei `read_text`
  (Review N3; der Loader liest Bytes, und eine CSS-Datei mit CRLF änderte die Seite um 4 Byte).
- **Gastgeber und Gast wissen voneinander** (Review K1). 15 verlinkt auf den Abschnitt, den 28
  anhängt (`docs/plans/15-funktion.md`, § 7, Konkordanz), und 26 ersetzt auf der Seite von 14 den
  Hinweis „Antworten stehen in der Niederschrift" (`docs/plans/26-beschluesse.md`, § 7). Darum sieht
  die Vorlage der Seite `guests`, die Namen ihrer Gäste in diesem Profil, und die Zusage dazu: steht
  ein Name darin, gibt es `#<name>` auf der Seite. Der Link oder der Hinweis hängt an
  `{% if "<name>" in guests %}`. Der Anker steht auch, wenn der Gast mit leeren Daten nichts zeigt,
  damit ein Link nie ins Leere geht. Dass jeder Anker genau einmal vorkommt, also mit keiner ID der
  Seite, des Rahmens (`docs`, `tooltip`) oder des Gasts selbst kollidiert, ist eine Nachbedingung
  von `render_page`.
- Der Schritt `page_<name>` liest die Eingaben seiner Abschnitte mit (`page_inputs`, jede Datei
  einmal), und die Vorlagen unter `templates/pages/` zählen über `report_fingerprint` ohnehin im
  Stamp mit (Punkt 53). Die Seite erlaubt die Links ihrer Abschnitte zu den eigenen.
- **Verträge.** Unabhängig vom Profil prüft `section_problems` das Register: ein Ziel, das keine
  registrierte Seite ist, und ein Rang oder Name, den zwei Abschnitte derselben Seite teilen, sind
  ein `SectionError` beim Aufbau der Schritte, mit Beitrag und Abschnitt in der Meldung. Ein Test
  prüft das echte Register, ein zweiter, dass jede Vorlage dort im Paket liegt und mit
  `{% if data.` beginnt (Review N5; `data` trägt den Schlüssel immer, denn unter `StrictUndefined`
  ist ein fehlender Schlüssel ein Fehler, kein falscher Wert). `order_sections` trägt dieselbe Eindeutigkeit als `deal.pre` und die Folge als
  `deal.ensure`. Verwaiste Dateien unter `templates/pages/` sind ein `SchemaError`, wie bei den
  Abschnitten der Hauptseite (Review N4, `check_page_files`): ein `.css` oder `.js` ohne Vorlage
  gleichen Namens, ein Ordner `<seite>/` oder eine Vorlage `<seite>.html.j2` ohne registrierte
  Seite, eine Vorlage im Ordner ohne registrierten Abschnitt.
- **Profil.** Wird die Zielseite in einem Profil nicht gebaut, weil ihr Schalter aus ist, entfällt
  der Abschnitt mit einer Zeile im Log (`INFO`, Name, Beitrag, Seite und Profil) und ohne Fehler.
  Ein Abschnitt mit eigenem abgeschaltetem Schalter fehlt still, wie eine abgeschaltete Seite.
  `enabled` und `inputs` folgen den Schaltern der eigenen Schritte (Review N1): ist der Schritt
  eines Gasts in einem Profil aus, bleibt der Gast nach Plan § 6 („jede Seite sagt, was in diesem
  Profil fehlt") an, `inputs` ist leer, und `data` sagt, was fehlt. Ein Test über das echte
  Register und alle fünf Paketprofile prüft, dass jede Eingabe jedes `page_*` ein früherer Schritt
  schreibt (kein Modellschritt) oder schon ein Schritt davor liest, also `bootstrap` sie bringt;
  heute ohne Seiten, ein Probefall zeigt, dass er einen Gast ohne Schreiber findet.

*Warum ein Rang, der je Seite eindeutig sein muss, und dennoch der Name als zweite Stufe.* Teilen
sich zwei Vorhaben einen Rang, entschiede sonst der Name, den keiner von beiden mit Blick auf den
anderen gewählt hat; der Fehler macht den Konflikt beim Merge sichtbar. Der Name im Schlüssel hält
die Folge nur dort fest, wo die Prüfung nicht vorausgeht (`order_sections` allein, mit
abgeschalteten Verträgen).

*Warum ein Fehler für ein unbekanntes Ziel, aber nur eine Logzeile für eine abgeschaltete Seite.*
Welche Unterseite in welchem Profil erscheint, hängt am Schalter ihres Beitrags (Plan, § 6: in
2014–2020 und in der laufenden Periode gibt es nur `akteure`, `vorgaenge` und `zeit`); das ist
erwartet. Ein Zielname, den keine Seite im Register trägt, ist ein Tippfehler und sähe im Lauf
genauso aus.

**Geprüft.**

- Tests: `tests/unit/test_report_page_sections.py` mit einer Seite und Abschnitten, deren Vorlagen
  nur ein `DictLoader` der Tests kennt (Register, Folge, Log, Fehler, Stamp, Schritt, Rahmen, CSS
  und JavaScript, Links; nach dem Review: Anker und `guests`, Eingaben je Paketprofil, ein Skript
  je Datei, Zeilenenden, verwaiste Dateien, `{% if data.`, Folge von CSS und JavaScript);
  `tests/property/test_page_sections_props.py` (hypothesis): für jede Verteilung von Abschnitten
  auf Beiträge und jede Folge der Beiträge und der Abschnitte darin dieselben Abschnitte je Seite,
  nach Rang aufsteigend.
- Rahmen ohne Abschnitte bytegleich: eine Probeseite ohne Abschnitte, mit `main` `b5d7038` und mit
  diesem Stand gerendert, ist in beiden Fällen dieselbe Datei (27 154 Byte, `cmp` ohne Abweichung);
  nach Runde 2 des Reviews ebenso eine Probeseite mit eigenem CSS und JavaScript, auf A aus dem
  Paket gelesen, auf B über den Loader (27 258 Byte).
- A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt 66 (`scripts/ab_bau.sh`,
  `scripts/ab_vergleich.py`), `POLARS_MAX_THREADS=4 OMP_NUM_THREADS=2`, A aus `main` `b5d7038`,
  B aus dem Baum dieses Eintrags, Wurzeln `ab/V1-a` und `ab/V1-b` auf xtraspace, die fünf Profile
  mit `bootstrap` und `run`, dann `publish --strict-budget`; nach Runde 2 des Reviews B noch einmal
  aus `30331e4` in frischer Wurzel `ab/V1-b2`, gegen dasselbe A, mit denselben Zahlen. Unter
  `site/` 235 Dateien in beiden, 0 Abweichungen. Über die ganzen Datenwurzeln 932 Dateien in
  beiden; abweichend sind nur 117 Stamps: 109 allein in der Zeit `written`, 6 dazu in `extra` (der
  Stamp von `index.html` der vier Profile mit Seite und seine Kopien in den beiden Periodenordnern
  der Stadtseite, weil `report_fingerprint` die geänderte Vorlage `page.html.j2` mitzählt) und 2 in
  `inputs`, dort nur in der Wurzel der absoluten Pfade, mit denselben Hashes. Kein Beitrag trägt
  einen Abschnitt; ändern kann sich erst etwas, wenn einer einträgt.

**Verworfen.** Abschnitte in der `Page` des Gastgebers anmelden (`Page.sections`): dann änderte 26
das Modul von 14, die Konfliktstelle, die F2 beseitigt hat. Eine Stelle für die fremden Abschnitte,
die die Vorlage der Seite selbst setzt: jede Seite müsste ihre Gäste vorhersehen, und ein neuer Gast
hieße, die Vorlage eines anderen anzufassen. Die Stelle ist darum fest, nach dem eigenen Inhalt; was
die geplanten Gäste darüber hinaus brauchen, ist, dass der Gastgeber von ihnen weiß (der Link von 15
auf 28, der Hinweis von 14, den 26 ersetzt), und das tragen `guests` und die Anker, nicht die Stelle.
Die erste Fassung dieses Eintrags hielt die feste Stelle allein für genug; das Review (K1) fand die
beiden Fälle. Ein eigener Schritt je Abschnitt, der ein HTML-Stück schreibt, das die Seite
einliest: eine Datei und ein Stamp mehr je Abschnitt für nichts, was die Eingaben im Stamp der
Seite nicht schon leisten. Die Folge des Registers: sie hinge an der Merge-Reihenfolge. Ein Fehler,
wenn die Zielseite in einem Profil fehlt: dann bräche jedes Profil, in dem der Gastgeber aus ist.

## 87. Prüfsatz mit dem Modell je Rolle, die Labels von 12 Runde 2 und 16 im Format von F4, eine Prüfstichprobe der Rückfallregel (F4-Nachzug V3, 2026-11-27)

Vorarbeit V3 des Plans [plan-zeigen-2026-11.md](plan-zeigen-2026-11.md) (§ 3, § 4) nach Konrads
Antwort auf Frage 19 (2026-11-26): für neue Messungen ist Kodierer B ein anderes Modell als A und
die Schlichtung, die bisherigen Labels bleiben, und jede Seite nennt, wie geprüft wurde. Die Nummer
bekommt der Eintrag beim Merge.

**Das Modell je Rolle** (`merge --model-a`, `--model-b`, `--model-adjudicator`; `--model` als
Kurzform) und die Form des Satzes stehen in Punkt 71 (Nachtrag vom 2026-11-27). `guete.json` führt
`modelle` an der Stelle von `modell`, das README eine Zeile **Modelle**.

**Die bisherigen Labels bekommen Satz und Modellfelder aus dem, was `guete.json` schon sagt**
(`georep validate restate`): das eine `modell` gilt für alle drei Rollen, und der Lauf schreibt nur
`modelle`, `satz` und im README die Zeilen **Kodierer** und **Modelle**; jede andere Zeile und jeder
andere Schlüssel bleibt an seiner Stelle. Die alte Zeile **Kodierer** muss ohne „Modell `M`," genau
die sein, die merge aus `uneinig` und `schlichtung_herkunft` schriebe, sonst bricht der Lauf ab.
Gelaufen über alle 15 Ordner mit `guete.json`; ein Test lässt ihn über den Stand im Repo laufen und
verlangt Bytegleichheit. Verworfen: Modelle als Argumente des Laufs (er könnte dann Tatsachen
ändern, nicht nur ihre Form; ein anderes Modell trägt `merge` ein) und das README ganz neu aus
`guete.json` zu bauen (ältere READMEs stammen aus älteren Fassungen von `readme()` und änderten
sich an Stellen, die mit den Modellen nichts zu tun haben).

**Positionsspannen im Kodierauftrag** (`docs/todo.md`, Punkt 14 (d)): `tasks` prüft `value` wie
`check_spans(…, texts=…, positions=…)`, leer nur bei den Abschnitten aus Vorhaben 11; die eigene
Prüfung bleibt, weil ihre Meldung beide Texte und den Extraktor nennt.

**Die Labels von 12 Runde 2 und von 16 kommen aus den Labeldateien der Messungen im Repo**
(`validate import` mit `[provisional] labels`: `labels-2.csv`, `labels.csv`, Werte als JSON), nicht
aus den lokalen Antwortdateien wie bei Runde 1 von 12. So rechnet ein Test in CI die Zahlen der
Messdokumente aus Dateien im Repo nach (12 § 4.4: Art 360/360, Grenzen 354/357 α 0,939, Norm
340/357 α 0,952; 16 § 4.1 und § 4.4: `bezug` 195/200 α 0,917 und 99/100 α 0,974, „handelt von"
hochgerechnet 0,821 und 0,783), und jedes Endlabel gleicht dem der Messung. Ein Objekt mit
`auswerter` in der Spalte `schlichtung` ist ein Entscheid des Auswerters und zählt als `herkunft`
(12-2-0001). Die beiden Runden von 16 sind zwei Ordner (`16-ortsbezug-f4`, `16-ortsbezug-2-f4`),
weil ihre Codebücher verschieden sind (§ 2 von validierung.md); in `12-kennungen-2-f4` tragen die
Schichten „neu" und „alt" ihre Artgruppe davor, weil derselbe Name in mehreren Arten mit
verschiedener Größe steht. Verworfen: ein Ordner für beide Runden von 16 (zwei Codebuchfassungen
in einer Antwortdatei weist `merge` ab, und die Gewichte gehören je Ziehung); die Recall-Dokumente
von 12 Runde 2 mitzunehmen (F4 wertet Markierungen noch nicht aus, § 6). Was F4 nicht rechnet,
bleibt in den Messskripten: die Präzision je Art von 12 und das F1 der Regel von 16.

**Die Prüfstichprobe der Rückfallregel von 14** (`14-vorgaenge-3-f4`, Messdokument § 4.3, vorab
in einem eigenen Commit): 50 starke Kanten der Hauptperiode, proportional nach der Fundstelle
(Titel 43, Nachtrag 4, Sammelbericht 2, Anlage 1), Codebuch Fassung .2 mit dem Material von F4,
kodiert nach der neuen Regel. Proportional, weil die Frage 9.18 das Intervall der ganzen Regel
schließen soll; verworfen: gleich viele je Fundstelle (Kishs
n_eff 17, die untere Grenze bliebe auch ohne Fehler bei 0,817) und alle vier Datensätze in einer
Stichprobe (`validate tasks` liest die Dokumente eines Profils; die Nachbarperioden heißen auf der
Seite „explorativ"). Sie ist die erste Messung mit Kodierer B auf einem anderen Modell (A und
Schlichtung `claude-opus-5-5`, B `claude-sonnet-5-5`); ihr Prüfsatz in `guete.json` lautet
„geprüft von zwei KI-Kodierern (claude-opus-5-5 und claude-sonnet-5-5) an 50 Dokumentpaaren,
Schlichtung durch claude-opus-5-5, nicht von Menschen". Ergebnis: 50 von 50, α von `selbe_sache`
mangels Streuung nicht definiert und nach Entscheidung des Supervisors als vollständige
Übereinstimmung erfüllt (Messdokument § 4.3).

**Volle Einigkeit genügt, wo α nicht definiert ist** (Supervisor, 2026-11-27, nach dieser
Messung; die Regel gehört nach F4, nicht in den Bau einer Seite). Urteilen beide Kodierer an jeder
Einheit, bei der die Frage gestellt war, gleich und mit demselben Wert, ist die erwartete
Uneinigkeit null und α nicht definiert; beobachtet ist aber volle Übereinstimmung, und einen
Zufallsabgleich gibt es nicht. Dann ist `alpha_genuegt = true` mit dem Vermerk `alpha_vermerk`
„volle Einigkeit, α nicht definiert" in `guete.json` und im README (`merge.unanimous`, von `merge`
und `score` gleich geschrieben). Genug Einheiten heißt: die untere Wilson-Grenze der
Übereinstimmung, n/(n + 1,96²), erreicht `validation.min_alpha`, bei 0,8 ab 16; so trägt die Regel
dieselbe Schwelle wie α und keine neue Zahl. Jedes andere undefinierte α (keine paarbare Einheit,
zu wenige, eine Einheit nur von einem Kodierer, Markierungen ohne eine einzige) genügt weiter
nicht. Verworfen: die Ausnahme nur auf der Seite (dann sagte `guete.json` etwas anderes als die
Seite) und volle Einigkeit an beliebig wenigen Einheiten (9 von 9 hat eine untere Wilson-Grenze von
0,70). Gelaufen ist sie für `14-vorgaenge-3-f4` (erneuter merge und score: nur `alpha_genuegt` und
der Vermerk bei `selbe_sache` und die Zeile im README änderten sich). Ein neuer `score` über alle
Ordner im Kratzordner zeigt nur einen weiteren, den die Regel ändert: `11-struktur-f4`,
`bv_mehrteilig` (114 von 114, alle „nein"); dort ist `score` nicht neu gelaufen, weil er auch
Felder nachtrüge, die spätere Fassungen von `score` schreiben.

## 88. Die erste Unterseite `akteure.html`: Prüfsatz aus `guete.json`, Lager je Paar am Datum, Links und Tabellen der Beiträge mit Layout (Vorhaben 15, Stufe 3, 2026-11-27)

Stufe 3 von Vorhaben 15 nach `docs/plans/15-funktion.md`, § 7 und § 10 (Punkt 8), und nach
`docs/plan-zeigen-2026-11.md` (§ 5, `v0.35.0`). Die erste Unterseite nach F2 (Punkt 69): sie legt das
Muster fest, nach dem 14, 17 und 22 folgen, und Konrad sieht sie an Haltepunkt Z1 an. Gebaut auf
`feat/15-akteure` ab `main` `344ecdc` (`v0.34.0`). Die Nummer bekommt der Eintrag beim Merge.

**Was gebaut ist.** Der Beitrag `15-funktion` trägt jetzt außer den Schritten die Seite und zwei
Tabellen bei, alle hinter `functions_enabled` (`functions.enabled` und Urheber im Profil), also in
allen fünf Paketprofilen:

- `akteure.html` (`report/actors.py`, `templates/pages/akteure.html.j2`, `.css`, `.js`) mit den fünf
  Abschnitten aus § 7: Funktionen der Dokumente (je Urheberklasse eine gestapelte Leiste als SVG
  über die sechs Klassen, die Zahlen als Tabelle, die Instrumente), Instrumente je Fraktion
  (Kontrolle roh und beobachtet gegen erwartet über `analysis.practice.observed_expected` mit dem
  Gremium als Schicht, „explorativ", unter 30 Dokumenten kein Verhältnis), Wer mit wem (je Ebene
  eine Matrix Fraktion × Fraktion), Konkordanz (K3 mit Wilson-Intervall und n, dasselbe mit
  Anfragen, die Mehrheiten mit Vereinbarung und Drucksachen, alle Dokumente über die Grenze) und
  Erklärungen und Appelle (die Liste, keine Rangfolge je Fraktion, mit der Definition aus dem
  Codebuch).
- Die Downloads `dokumente_funktion` und `dokumente_antragsteller` (Parquet und CSV, Spaltendoku in
  `schema.json`); der Name ist der aus § 10, Punkt 1, und Punkt 75, nicht `mitantraege`.
- Der Linkblock auf `index.html` ist der Abschnitt `58-weitere` aus F2; er erscheint, sobald eine
  Seite im Register steht. Neu auf `index.html` sind damit dieser Abschnitt und je Tabelle zwei
  Zeilen in den Downloads und ein Eintrag im Spaltenschema.

**Der Prüfsatz kommt aus `guete.json`, die Treffer des Regelwerks aus einer geprüften Konstante.**
`validierung/15-funktion-f4/guete.json` trägt den Satz (Modelle, Einheiten, „nicht von Menschen"),
die Modelle je Rolle und die Übereinstimmung der Kodierer (149 von 150 bei `funktion`); das liest
`read_check`, und eine geänderte Datei ändert die Seite (Test). Was die Datei nicht trägt, ist das
Regelwerk gegen die Endlabels: κ 0,905 (0,840–0,960) für B, 0,829 (0,748–0,900) für A an 135
Dokumenten, 125 Treffer, Antragsteller 119/119 und 119/138. Das steht als `RULE_CHECK` in
`report/actors.py`, und der slow-Test `tests/golden/test_functions_numbers.py` rechnet Treffer, κ und
die Zahlen der Antragsteller aus `validierung/15-funktion/labels.csv` gegen genau diese Konstante
nach; das Intervall ist der Bootstrap des Messskripts und wird nicht nachgerechnet. `RULE_CHECK`
trägt die Codebuchversion und die Zahl der Einheiten seiner Messung, und `read_check` bricht mit
`SchemaError` ab, wenn `guete.json` eine andere Kodierung beschreibt (Review 2026-11-27, N1): sonst
stünde nach einer neuen Kodierung ein neuer Satz neben alten Treffern. Der Satz „bei
zwei Kodierern desselben Modells ist das ein schwacher Beleg" hängt an `modelle` (A gleich B), der
Hinweis auf die vorsichtige Zahl der nicht gewählten Variante an `RULE_CHECK.selected_on_labels`
(Synergien § 10, Punkt 8). Verworfen: `georep validate score --pred` über die 150 Dokumente laufen
zu lassen, damit `guete.json` die Treffer trägt. `score` rechnet Präzision, Recall und Genauigkeit
über alle gelabelten Einheiten, auch „unklar" und die Restklasse, also nicht die Basis nach Frage 17,
und kein κ mit Bootstrap; und ein neuer `score` trüge Felder nach, die spätere Fassungen schreiben
(Punkt 87). Ebenso verworfen: die Zahlen ins Stadtprofil (sie sind keine Einstellung einer Stadt).

**Gemessen oder explorativ.** Ein Datensatz ist gemessen, wenn sein Ordner (`settings.profile`) der
Ordner eines Profils aus `stichprobe.json` ist (`settings.profile_folder`): die drei Düsseldorfer
Datensätze, mit ihnen `duesseldorf-vergleich`, das im Ordner der Hauptperiode rechnet;
Mönchengladbach nicht. Dort heißt jede Überschrift „explorativ", und der Prüfsatz sagt, an welchen
Datensätzen gemessen ist, mit Stadt und Periode aus deren Profilen, nicht mit Profilnamen (Review N5) (Plan § 8, Gültigkeitsregel). Unabhängig davon tragen „Instrumente je
Fraktion" und „Konkordanz" in jedem Datensatz „explorativ" (Messdokument § 8, Frage 14), die
Konkordanz aber nur, wo es sie gibt: in Mönchengladbach fehlt sie (keine Mehrheit im Profil), ihre
Überschrift trägt dort kein „explorativ", weil darunter keine Zahl steht, sondern nur der Satz, was
fehlt (Review 2026-11-27, N4).

**Das Lager einer Zelle ist das des Paars am Datum jedes Dokuments.** Ein Dokument von vier
Fraktionen über die Grenze ist für das Paar zweier Mehrheitsfraktionen darin „beide in der
Mehrheit"; das rechnet `analysis.cosponsors.camp` mit genau den beiden Fraktionen und der Mehrheit an
seinem Datum. Wechselt die Mehrheit im Datensatz, kann ein Paar zwei Lager haben: in der
Hauptperiode Grüne und FDP (25 über die Grenze, 2 unter der Ampel bis zum 2020-10-31); die Zelle
trägt das häufigere, ein Stern führt zur Fußnote mit beiden. Lager gibt es nur auf der Ebene der
Ratsmehrheit (`majorities.body_kinds`); die Matrix der Bezirksvertretungen ist ungefärbt. Die Farben
sind die Mischungen `--d1` bis `--d3` des Rahmens, deren Kontrast dort nachgerechnet ist. Als Tönung
hinter Zahlen sind sie unter Rot-Grün-Schwäche nicht sicher zu trennen (Validator der Skill dataviz,
alle Paare: Grau und Orange hell ΔE 3,0 unter Protanopie, dunkel 5,2 unter Deuteranopie); darum
trägt jede gefärbte Zelle ein sichtbares Kürzel, M, Ü oder O, das die Legende erklärt, dazu den Titel
und einen versteckten Text für Screenreader (Review 2026-11-27, K2). Die
beiden Matrizen schaltet ein eigenes Skript um, nicht `fieldset.switcher` des Rahmens: der tauscht
Stufen der Rampen `q` und `d`, und ein Lager als `d`-Stufe hieße, dass dieselbe Klasse auf zwei
Flächen zweierlei bedeutet (CLAUDE.md). Ohne JavaScript stehen beide Matrizen untereinander, und
der Umschalter ist verborgen: das Attribut `hidden` allein genügte nicht, weil der Rahmen `fieldset`
auf `inline-flex` setzt; `akteure.css` hebt das für `fieldset.matrix-ebene[hidden]` auf (Review
2026-11-27, K1, mit Bildschirmfotos ohne Skripte belegt).

**Zwei Nachzüge am Rahmen, die erst eine echte Seite zeigt.**

- `Page.links` und `PageSection.links` bekommen `(layout, settings)` wie `inputs` und `data`. Die
  Seite verlinkt die PDF-Dateien ihrer Listen im Ratsinformationssystem, und die erlaubten Links
  stehen damit in den Daten. Mit `Layout.from_settings(settings)` im Callable hätte die Mini-Kette
  der Tests (eigenes `Layout`) den falschen Korpus gelesen. Erlaubt sind die PDF-Dateien des eigenen
  Korpus, das Messdokument und das README der Prüfung.
- Die Tabellen der Beiträge zählen im Stamp von `report` (`report.tables.contributed_table_files`):
  `report` kopiert sie nach `site/data/` und schreibt ihre Prüfsummen auf die Seite, und ohne sie im
  Stamp blieb der Schritt nach einer geänderten Tabelle aktuell. Eine Tabelle mit `optional=True`
  (beide von 15) ist eine optionale Eingabe, weil `published` sie ohne Datei auslässt, jede andere
  eine harte (Review 2026-11-27, N10); `check_step_order` sieht in beiden Fällen, dass ihr Schritt
  vorher läuft.

`guete.json`, `stichprobe.json` und `codebuch.toml` sind Eingaben von `page_akteure`; sie liegen im
Repo, nicht im Lauf. Der Test, dass jede Eingabe jedes `page_*` im Lauf entsteht (Punkt 86), lässt darum zu, was
unter `validation.root` liegt. Tests, die das Register durch Probebeiträge ersetzen, ersetzen auch
den Ordner `templates/pages/` (`pages_folder`), sonst wäre `akteure.html.j2` darin verwaist
(`check_page_files`).

**Für alle Fraktionen gleich gebaut.** Dieselben Spalten für jede Fraktion, die Folge nach
Dokumenten, die Namen aus dem Profil (Kurznamen, „SPD/Volt" aus `[[functions.fractions]]`); Tests
verlangen, dass kein Parteiname eines Paketprofils in den Vorlagen steht, in einer mit neutralen
Fraktionen gerenderten Seite und in der Spaltendoku der beiden Tabellen (Review 2026-11-27, K4:
dort stand „wie SPD+VOLT", jetzt „wie A+B"). Der Satz aus § 3.12 über
den Umgang mit Anträgen einer bestimmten Fraktion heißt darum auf der Seite „mit den Anträgen
einzelner Fraktionen". Die Spalte Erklärung/Appell bleibt in der Tabelle je Fraktion, wie § 7 sie
nennt, ist aber nicht sortierbar; die Liste steht im letzten Abschnitt (Frage 9.8, § 10 Punkt 8).
„Kontrolle roh" sortiert ebenso wenig (Frage 14: je Fraktion nur standardisiert; Review
2026-11-27, N3); sortierbar ist das Verhältnis.

**„Erklärung oder Appell" statt „Symbolpolitik"** (Konrad, 2026-11-27, nach den Bildschirmfotos:
das Wort ist wertend). Die Klasse heißt überall, wo ein Leser sie sieht, „Erklärung oder Appell",
kurz „Erklärung/Appell" in Leisten, Legenden und Spalten; in `dokumente_funktion` ist der Wert
`erklaerung` statt `symbol` (`FUNCTIONS_SCHEMA_VERSION` 2), in den Tabellen der Settings ebenso
(`FUNCTION_CLASSES`, `FUNCTION_INSTRUMENTS`, im Stadtprofil `erklaerung/resolution`). Die Klasse
hieß in Messung und Codebuch `symbol`; die Definition ist unverändert, und die Validierung gilt
weiter: `settings.CODEBOOK_FUNCTIONS` übersetzt das Label des Codebuchs, und der slow-Test rechnet
κ mit dieser Übersetzung nach (dieselben 125 Treffer). Die Seite zeigt die Definition wörtlich aus
`validierung/15-funktion-f4/codebuch.toml` (eine weitere Eingabe von `page_akteure`); ein Test
verlangt, dass die gebaute Unterseite, die Hauptseite, `schema.json` und die CSV der beiden Tabellen
das Wort nicht enthalten. Intern bleiben die Namen der Settings `symbol_title` und `symbol_text`:
sie stehen in keiner Ausgabe, und ein Umbenennen änderte jedes Stadtprofil. Das Messskript und das
Messdokument bleiben, wie gemessen. Der Abschnitt heißt „Erklärungen und Appelle" (Anker
`#erklaerungen`).

**Eine laufende Periode heißt laufend** (Messdokument § 9.11, Review 2026-11-27, K3). Ist
`period.end` leer, sagt die Konkordanz unter den Kacheln, bis wann die Daten reichen und dass ein
kleines K3 dort noch kein Befund ist; in der Periode seit 2025 sind es 0 von 312.

**Die Listen nennen Gremien beim Namen** (Review 2026-11-27, N5): wie die Hauptseite aus `[bodies]`
(Rat, Ausschüsse, Beiräte; eine Bezirksvertretung über `district_body_name` und den Stadtbezirk),
sonst das Kürzel. Ein Fraktionsdokument ohne genannte Fraktion heißt in der Spalte Antragsteller
„Fraktion nicht erkannt", nicht „Fraktionen".

**Zwei Randfälle** (Review 2026-11-27, N7): ohne eine Initiative mit Beteiligung der Opposition
zeigt die Kachel K3 einen Strich und den Grund, nicht „0,0 %" bei „0 von 0"; und in der Aufzählung
der Praxis je Gremienart heißt die Klasse ohne erkanntes Gremium „Gremium unbekannt", nicht
„unbekannt".

**Der Gast von 28 heißt `abstimmungen`.** Der Abschnitt Konkordanz verlinkt
`{% if "abstimmungen" in guests %}` auf `#abstimmungen` (Punkt 86), sonst sagt er, dass Beschlüsse
und Abstimmungen noch fehlen. Der Name folgt dem Bauplan von 28 (§ 7, „ein Abschnitt
Abstimmungen"); wählt 28 einen anderen, ändert sich eine Zeile der Vorlage.

**Bewusst anders als § 7.**

1. `dokumente_antragsteller` statt `mitantraege` (§ 10, Punkt 1).
2. Eine Leiste je Urheberklasse (Verwaltung, Fraktionen, einzelne Mandatsträger, Eingaben,
   Urheber nicht erkannt) statt zweier für Verwaltung und Politik: die Klassen „Person" und
   „unbekannt" zeigen ein anderes Verhältnis von Kontrolle und Initiative als die Fraktionen, und
   eine Klasse ohne Dokumente fehlt.
3. Die Seite ist 58 bis 106 KB groß statt 40 bis 70: der Rahmen allein (Stil und Skript der
   Hauptseite) sind rund 31 KB, die beiden Listen in der Hauptperiode zusammen rund 40 KB. Das Budget
   von 500 KB je Unterseite hält sie mit weitem Abstand (Zahlen unten).
4. Unter „Über die Grenze" stehen alle Dokumente über die Grenze mit der Zahl ihrer Fraktionen, nicht
   nur die „Allparteienanträge"; wie viele mindestens vier Fraktionen tragen, sagt ein Satz (27 von
   41 in der Hauptperiode, 42 von 50 für 2014–2020, wie § 3.11).
5. „Funktion nicht erkannt" heißt im Prüfsatz „fast alle Vorlagen ohne lesbaren Text oder mit einer
   Anlage am Anfang" (§ 4.2) statt „Vorlagen ohne lesbaren Text": unter den 1 231 Dokumenten der
   Periode 2014–2020 sind auch Vorlagen, deren Text mit einer Anlage beginnt.
6. Beobachtet gegen erwartet ist das der gebauten Variante B; die Tabelle in § 3.7 ist an Variante A
   gerechnet (Hauptperiode CDU 0,73 statt 0,74, Tierschutz/FW 1,64 statt 1,67, AfD 1,72 statt 1,75).
   SPD vor dem 2020-11-01 und SPD/Volt danach sind zwei Fraktionen (Punkt 75), § 3.7 zählte sie
   zusammen; ein Satz unter der Tabelle sagt das, aus `valid_from` der Fraktion (Review N2).
7. Neben K3 steht dasselbe Maß mit Anfragen (§ 3.11, Spalte „alle Funktionen"), und die Matrix zählt
   gemeinsame Dokumente aus Beiräten und ohne Gremium nicht, sondern nennt ihre Zahl.

**Verworfen.** Ein Graph-Layout des Netzes und eine Bibliothek für die Leisten (§ 7); die Zellen der
Matrix nach der Zahl einzufärben (die Zahl steht in der Zelle, die Farbe trägt das Lager); eine
dritte Matrix „alle Gremien" (sie mischte die Ebene mit und ohne Lager); `links(settings)` mit
`Layout.from_settings` (siehe oben).

**Geprüft.**

- Tests: `tests/unit/test_report_actors.py` (Bausteine an erfundenen Tabellen, Prüfsatz aus einer
  geänderten `guete.json`, gemessen oder explorativ je Paketprofil, Abschnitte und Überschriften,
  der Link auf den Gast, keine Partei in den Vorlagen, Register, Linkblock, Downloads mit
  Spaltendoku, Stamp von `report`, erlaubte Links); slow in `tests/golden/test_functions_numbers.py`
  die Zahlen der Seite in den drei Düsseldorfer Datensätzen (Erklärungen 55, 52, 3; die zwei
  Zählungen 144, 179, 7, zusammen 330 wie § 3.8; K3 mit Anfragen 50/1 565, 41/2 731, 1/778; über
  die Grenze 50 davon 42, 41 davon 27, 1 davon 0; beobachtet gegen erwartet in Variante B; CDU und
  Grüne in Rat und Ausschüssen der Hauptperiode 577, beide in der Mehrheit), die zweite Stadt ohne
  Konkordanz und explorativ, und jede Seite unter 500 KB.
- Bildschirmfotos mit headless Chrome bei 1280 und 390 Pixeln Breite, hell und dunkel, und bei 390
  und 1280 ohne Skripte (an einer Kopie der Seite ohne `<script>`; mit
  `--blink-settings=scriptEnabled=false` schreibt headless Chrome kein Bild): dort stehen beide
  Matrizen untereinander und kein Umschalter; mit JavaScript ist der Umschalter sichtbar und die
  zweite Matrix verborgen.
- A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt 66 (`scripts/ab_bau.sh`,
  `scripts/ab_vergleich.py`), `POLARS_MAX_THREADS=4 OMP_NUM_THREADS=2`, A aus `main` `344ecdc`
  (`git archive`), B aus dem Stand nach Review Runde 2 (`9d372ab`), Wurzeln `ab/15-a` und
  `ab/15-b` auf xtraspace, die fünf Profile mit `bootstrap` und `run` in der Folge von `pages.yml`,
  dann `publish --strict-budget`. Unter `site/` 235 Dateien in A, 255 in B, 28 Abweichungen, alle
  erwartet: je Stadtseite (Hauptperiode, 2014–2020, laufende Periode, Mönchengladbach) neu
  `akteure.html` und die vier Downloads, anders `index.html` (je Profil fünf Stellen: Abschnitt
  „Weitere Auswertungen", die Zahl der Downloadzeilen, vier Zeilen in den Downloads, die Größe von
  `schema.json`, zwei Einträge im Spaltenschema; sonst bytegleich bis auf die Prüfsummen, die an
  `generated_at` hängen) und `schema.json` (die beiden Tabellen); `vergleich.html` und jede
  `summary.json` gleich, und kein veröffentlichter Text enthält „Symbol". Über die ganzen
  Datenwurzeln 932 und 988 Dateien, 197 Abweichungen: dieselben Seiten und Downloads in den Ordnern
  der Profile; von den Parquets unter `processed/` und `interim/` nur `dokumente_funktion` in allen
  vier Datensätzen, und dort nur der umbenannte Wert (`symbol` → `erklaerung` bei 52, 55, 3 und 5
  Dokumenten; nach Abbildung gleich); 123 Stamps (81 nur im Settings-Fingerprint, weil das Profil
  der Stadt jetzt `erklaerung/resolution` sagt, 24 in Mönchengladbach nur in `written`, 6 neue von
  `akteure.html`, 6 von `index.html` in `extra` und den optionalen Eingaben, 4 von
  `dokumente_funktion` in der Schema-Version 2, 2 nur in der Wurzel der absoluten Pfade).
- Größen, veröffentlicht (`publish`): `index.html` der Hauptperiode 937 391 → 941 988 Byte
  (+4 597; Budget 1 000 000, Ziel der Phase höchstens +30 KB), `2014-2020/` 822 762 → 827 359,
  `2025/` 718 700 → 723 285, `moenchengladbach/` 806 195 → 810 780. `akteure.html`: Hauptperiode
  105 563, 2014–2020 102 499, laufende Periode 67 163, Mönchengladbach 58 198 Byte; zusammen
  333 423. Die Downloads machen die veröffentlichte Seite 10,2 MB größer (36,7 → 46,9 MB), vor
  allem die CSV je Dokument (Hauptperiode 1,87 und 1,94 MB), wie bei `dokumente_urheber`; die
  Pakete im Repo ändern sich nicht.

## 89. Die Downloads von 11 und 12: nur gemessen und mit Rohtext, eine Sicht ohne Namen, der Prüfsatz unter der Tabelle (Vorhaben 11 und 12, Stufe 3, 2026-11-27)

Stufe 3 von Vorhaben 11 und 12 nach `docs/plans/11-struktur.md` und `docs/plans/12-kennungen.md`
(je § 7 und § 10) und nach `docs/plan-zeigen-2026-11.md` (§ 5, `v0.37.0`; V5: `sitzung_gremium` in
`schema.json`). Keine Unterseite, je eine Zeile in den Downloads der Hauptseite. Gebaut auf
`feat/11-12-downloads` ab `main` `f27473f` (`v0.35.0`), parallel zu 14 und 17. Die Nummer bekommt
der Eintrag beim Merge.

**Was veröffentlicht wird.**

- `dokumente_kopf.parquet` (11), nur als Parquet: die Beratungsfolge ist eine Liste von Strukturen
  ohne CSV-Form, und als CSV wäre der Kopf fünf- bis achtmal so groß (§ 7). Ohne die Spalte
  `unterzeichner_rolle`: sie stammt aus der Liste des Profils und ist kein Name, aber
  „Oberbürgermeister" oder „Fraktionsvorsitzender" unter einem Brief zeigt auf eine Person, und § 7
  sieht keinen Unterzeichner vor. `dezernat_titel` bleibt, es ist nur die Amtsbezeichnung aus der
  Liste des Profils (Nachbedingung von `structure_tables`). Die Abschnitte selbst nicht (Rohtext).
- `kennungen.parquet` (12) mit allen sechs Arten, dazu `kennungen.csv` nur mit Bebauungsplänen,
  FNP-Änderungen und Beträgen (§ 7): alle Arten wären als CSV 17,8 MB.
- Unter der Download-Tabelle je Tabelle ein Absatz mit dem Prüfsatz; `schema.json` und das
  Spaltenschema der Seite beschreiben jede veröffentlichte Spalte, `sitzung_gremium` mit beiden
  Formen (Name aus dem Profil, wo `sitzung_kuerzel` gesetzt ist, sonst wie im Text; `docs/todo.md`,
  Punkt 14 (e)).

**Nur gemessen und nur mit Rohtext.** Ein Download erscheint, wo der Datensatz zur Stichprobe gehört
(`report.downloads.measured`, dieselbe Regel wie `akteure.html`: der Ordner eines Profils aus
`stichprobe.json`; das Vergleichsprofil rechnet im Ordner der Hauptperiode; ein Profil, das es im
Paket nicht gibt, ist ein Fehler, kein stilles „nicht gemessen") und die Tabelle Zeilen
aus einem Rohtext hat (`has_extracted_rows`). Auf Pages ist das die Hauptperiode, wie § 6 des Plans
es erwartet; die anderen Profile haben dort keinen Rohtext und bekommen weder Zeile noch Satz. Lokal
haben 2014 bis 2020, die laufende Periode und Mönchengladbach Rohtext, aber ihr Kopf ist nicht
gemessen, und in 2014 bis 2020 läuft er oft in fremde Felder: 168 Amtszeilen tragen dort das Feld
der Dezernentin oder des Dezernenten mit Namen, zwölf Zeilen der Beratungsfolge sind Textreste mit
Namen („… Herr …"), 13 Ämter von 12 heißen „Beigeordnete …". Ein Satz „explorativ" hätte die
Zahlen gerettet, nicht die Namen. Verworfen: die Downloads in jedem Profil mit Rohtext und
„explorativ" (die Gültigkeitsregel des Plans, § 8) — der Namensschutz unten fängt nur Namen hinter
einem Titel, und „Dezernentin: …" ohne Titel stand dort schon vor ihm.

**Ohne Namen: eine Sicht statt der Kopie.** Ein Eintrag im Register kann jetzt eine Sicht
veröffentlichen (`PublishedTable.view`): `head_view` lässt `unterzeichner_rolle` weg und leert einen
Freitext (`formular`, `amt_name`, `sitzung_gremium`, das Gremium einer Zeile der Beratungsfolge), in
dem hinter einem Titel ein Name beginnt; `spans_view` lässt eine solche Spanne ganz weg, weil F3 ein
leeres `value` nur bei Positionsspannen kennt. Den Titel nennt `report.names.person_titles`
(Verwaltungsdeutsch in `defaults.toml`, die Anreden wie `summaries.person_titles` und die Rollen aus
`structure.head.signer_roles`; Polars, also ohne Lookarounds), das Muster setzt `named` zusammen:
Titel, Leerraum oder Doppelpunkt, ein Großbuchstabe. So trifft es „Beigeordneter Hans …",
„Stadtkämmerin…" ohne Leerraum und „Dezernentin: …", nicht „Büro Oberbürgermeister" und nicht
„Stadtdirektor und Dezernat für …". Eine Nachbedingung der beiden Sichten prüft, dass danach kein
Wert mehr trifft. In der Hauptperiode leert die Sicht vier Amtszeilen und lässt keine Kennung weg
(gezählt am 2026-11-27 über alle Spalten mit Text); in 2014 bis 2020 wären es 168 und zwölf und 13,
in der laufenden Periode zwei Amtszeilen der Form „Stadtkämmerin Amt für …" (ein Fehltreffer, der
nichts kostet), in Mönchengladbach keine. `report.names` steht unter `[report]`, weil es nur die
Seite betrifft: es zählt im Stamp von `report` (`report_fingerprint`), nicht im Settings-Fingerprint,
und kein anderer Schritt rechnet neu. Die Abschnitte von 11 bleiben, wie validiert; die Amtszeile am
nächsten Feldlabel zu schneiden, wäre eine neue Regel für `struktur-2` (`docs/todo.md`, Punkt 14 (f)).
Verworfen: den Namen im Wert abschneiden statt den Wert zu leeren (ein Schnitt am Label ließe einen
Namen ohne Label stehen); `unterzeichner_rolle` aus `dokumente_kopf` selbst nehmen (das änderte die
Ausgabe der Stufe 2 und ihr Schema); eine eigene Datei für den Download (doppelt).

**Der Prüfsatz kommt aus `guete.json`, die Zahlen aus einer geprüften Konstante** (wie `RULE_CHECK`
von 15, Punkt 88). `read_quality` liest `satz`, `modelle` und `uneinig` und bricht mit `SchemaError`
ab, wenn Codebuch oder Zahl der Einheiten nicht die der Messung sind. Wo Kodierer und Schlichtung
dasselbe Modell sind und es Uneinigkeiten gab, hängt „geschlichtet von demselben Modell" an den Satz
(`merge.sentence` nennt die Schlichtung dann nicht; § 7 von 12 will es sagen). Die Zahlen:

- 11 (`HEAD_CHECK`, `11-struktur-f4`): Beschlussvorschlag zeilengenau 188 von 200, im Kopf Amt
  125/125, Amtsbezeichnung 69/69, Zeilen der Beratungsfolge 160/168, Briefdatum 73/73, Datum der
  Sitzung 48/48, je mit dem Intervall nach Wilson (§ 4.1; 0,898–0,965 und so fort, ein Test hält die
  Werte des Messdokuments fest). Der slow-Test `test_structure_numbers.py` vergleicht die Konstante
  mit den Zahlen, die er aus `labels.csv` rechnet. Die Gremien der Sitzung (48/48 nach der
  Normalisierung) stehen nicht im Satz: die Normalisierung kam nach der Kodierung.
- 12 (`ROUND_1`, `ROUND_2`): die Präzision je Art (Art und Grenzen richtig, gewichtet mit
  `schicht_n`, Wilson mit dem effektiven n nach Kish), Bauleitplanung 1,000 (0,957–1,000; n 100)
  und Betrag 0,962 (0,885–0,988; n 100) aus Runde 1 (`12-kennungen-f4`), Termin 1,000 (0,726–1,000;
  n 30) und Verwaltungseinheit 0,956 (0,851–0,988; n 100) aus der Bestätigung in Runde 2
  (`12-kennungen-2-f4`). Beide Ordner, weil die Arten an verschiedenen Runden gemessen sind; der
  Auftrag nannte nur Runde 2, die Bauleitplanung und Beträge aber nicht trägt. Der slow-Test
  `test_identifiers_labels.py` rechnet Anteil, n und Intervall aus den Labels nach. Der Recall steht
  nicht im Satz (Plan, § 4, V3). Dazu: Beträge tragen keine Rolle, Termine keine Frist.

`guete.json` und `stichprobe.json` der drei Ordner sind Eingaben von `report`
(`contributed_check_files`), wie die von `page_akteure`.

**Volle Einigkeit bei `bv_mehrteilig`** (Punkt 87): nicht nachgetragen. Ein `georep validate score
11-struktur-f4` in einem Kratzordner ändert außer `alpha_genuegt` und `alpha_vermerk` dieser Frage
an allen zehn Fragen einen Schlüssel (`markierungen: null`, den spätere Fassungen von `score`
schreiben), und das README schreibt `score` nicht neu: dort stünde weiter „genügt nein". Der Prüfsatz
liest `alpha_genuegt` nicht; `bv_mehrteilig` steht in keiner Zahl der Zeile.

**Vier Felder am Register**, alle am Ende von `PublishedTable`, damit kein Aufruf mit Positionen
seine Bedeutung ändert: `csv` (`CsvPlan`: die Zeilen der CSV und ein Satz für ihre Downloadzeile;
`None` heißt keine CSV, und `csv_plan` lässt die Tabelle dann aus, sonst bräche `georep export` an
der Liste von Strukturen ab), `view`, `shown` (an Datei und Settings; ohne Settings kein Download)
und `check` (`TableCheck`: Dateien und Satz). Eine Sicht wird mit der Schema-Version ihrer Quelle
geschrieben, ihre Spaltendoku an einer leeren Tabelle bestimmt.

**Größen.** Hauptperiode, veröffentlicht: `dokumente_kopf.parquet` 204 485 Byte, `kennungen.parquet`
1 245 173, `kennungen.csv` 4 593 264 (30 180 Zeilen, 2,1 MB davon die Spalte `id`; `docs/todo.md`,
Punkt 35). Auf `index.html` der Hauptperiode: drei Downloadzeilen (390, 371, 419 Byte), zwei
Prüfsätze (578 und 701 Byte) und zwei Einträge im Spaltenschema (rund 2,7 und 1,7 KB). Das sind
rund 7 KB statt „je unter 1 KB" aus § 5 des Plans: die Schätzung zählte das Spaltenschema und den
Prüfsatz nicht. Das Ziel der Phase (höchstens 30 KB über dem Bau vor `v0.33.0`) hält es.

**Geprüft.**

- Tests: `tests/unit/test_report_downloads.py` (eine Kette mit zwei erfundenen Rohtexten, in deren
  Kopf ein Name steht: kein Name in einem veröffentlichten Text, kein Unterzeichner; die Sichten an
  erfundenen Zeilen; jede veröffentlichte Spalte beschrieben, auch in `schema.json`; nur gemessene
  Datensätze; ohne Rohtext weder Zeile noch Absatz; CSV nur mit Plänen und Beträgen, keine vom Kopf,
  `georep export` ohne sie; die Prüfdateien im Stamp von `report`; der Prüfsatz aus `guete.json`, ein
  geänderter Satz ändert ihn, eine andere Kodierung bricht ab). Rot vor der Änderung, gegen `main`
  `f27473f`: Exit 1, `test_mit_rohtext_parquet_und_die_csv_der_plaene_und_betraege`,
  `test_der_bericht_liest_die_pruefung_mit`, `test_der_pruefsatz_steht_unter_den_downloads`
  (die übrigen brauchen Namen, die es dort nicht gibt: Exit 2 beim Sammeln). Slow:
  `test_structure_numbers.py` und `test_identifiers_labels.py` binden die Konstanten an die Labels,
  `test_published_page.py` die Größen der drei Dateien und der fünf Zeilen auf der Seite. Drei
  slow-Tests der vollen Kette zählten zwei Dateien je Tabelle und lasen `published` ohne Settings
  (rot nach `f755777`, etwa `assert 52 == ((2 * 22) + 5)`); sie zählen jetzt über
  `PublishedTable.download_names` (`76b327c`, die Ausgabe von `report` bleibt gleich).
- A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt 66 (`scripts/ab_bau.sh`,
  `scripts/ab_vergleich.py`), `POLARS_MAX_THREADS=4 OMP_NUM_THREADS=2`, A aus `main` `f27473f`
  (`git archive`), B aus `f755777`, Wurzeln `ab/1112-a` und `ab/1112-b` auf xtraspace, die fünf
  Profile in der Folge von `pages.yml`, dann `publish --strict-budget`. Unter `site/` 255 Dateien in
  A, 258 in B, 5 Abweichungen, alle erwartet: neu `data/dokumente_kopf.parquet`,
  `data/kennungen.parquet` und `data/kennungen.csv` der Hauptperiode, anders deren `index.html`
  (die drei Downloadzeilen, die Zahl der Zeilen im Knopf, 60 statt 57, die Größe von
  `schema.json`, die zwei Prüfsätze, zwei Einträge im Spaltenschema; sonst bytegleich bis auf die
  Prüfsummen, die an `generated_at` hängen) und `schema.json` (die beiden Tabellen). Die Seiten von
  2014–2020, der laufenden Periode und Mönchengladbach, `vergleich.html`, `akteure.html` und jede
  `summary.json` sind gleich, bis auf Zeitstempel. Über die ganzen Datenwurzeln 988 und 994
  Dateien, 133 Abweichungen: dieselben Seiten und Downloads im Ordner der Hauptperiode, kein Parquet
  unter `processed/` und `interim/`, 123 Stamps (109 nur in `written`, der Settings-Fingerprint ist
  gleich; 6 von `index.html` in `extra` und den neuen Eingaben, 6 von `akteure.html` in `extra`, weil
  der Vorlagen-Hash `70-downloads` mitzählt; 2 nur in der Wurzel der absoluten Pfade).
- Größen, veröffentlicht (`publish`): `index.html` der Hauptperiode 941 988 → 948 839 Byte (+6 851;
  seit dem Bau vor `v0.33.0` +11 448, Ziel der Phase höchstens +30 KB), `schema.json` 40 717 →
  45 663; die anderen Seiten gleich groß. Die veröffentlichte Seite wächst um 6,1 MB (46,9 → 53,0
  MB), fast nur `kennungen.csv`.

## 90. Die Unterseite `zeit.html`: Zählungen beschreibend, die Familie mit Wort und Commit, das Vokabular mit seiner Ebene, die Feeds mit ihrem Stand (Vorhaben 17, Stufe 3, 2026-11-27)

Stufe 3 von Vorhaben 17 nach `docs/plans/17-zeit.md`, § 7 und § 10 (Punkte 8 und 9), und nach
`docs/plan-zeigen-2026-11.md` (§ 5, `v0.38.0`; § 7, die Feeds), im Muster von `akteure.html`
(Punkt 88). Gebaut auf `feat/17-zeit-seite` ab `main` `f27473f` (`v0.35.0`). Die Nummer bekommt der
Eintrag beim Merge.

**Was gebaut ist.** Der Beitrag `17-zeit` trägt außer den vier Schritten jetzt die Seite und vier
Tabellen bei, hinter `time_enabled` (Schritt `cycles` an: `cycles.enabled` und Urheber), also in allen
fünf Paketprofilen:

- `zeit.html` (`report/cycles.py`, `templates/pages/zeit.html.j2`, `.css`) mit fünf Abschnitten:
  *Rhythmus der Ratsarbeit* (je Urheberklasse eine Reihe Monatsbalken, die Haushaltsmonate als Band,
  die vollständigen Wahljahre mit ihrer Rolle in H17.1 und ihrem Haushaltsmonat, beschreibend S1.6
  je Vorwahljahr, der Median je Kalendermonat, die Zahlen je Monat als Tabelle); *Vorab festgelegte
  Hypothesen*; *Bundespolitisches Vokabular*; *Ereignisspuren* (explorativ); *Neuigkeiten je
  Wahlbezirk* (nur mit `feeds.enabled`).
- Die Downloads `zeit_monate`, `haushaltsmonate`, `dokumente_bundesvokabular` (Kennung, Kategorien,
  Kopf, Lexikon) und, nur im Profil mit `cycles.periods`, `zeit_hypothesen`, je Parquet und CSV mit
  Spaltendoku in `schema.json`; die Listen trennt in der CSV „; ". Die CSV des Vokabulars trägt nur
  die Dokumente mit Treffer und nicht die Spalte `lexikon` (`CsvPlan` aus Punkt 89, Review N2); das
  Parquet bleibt vollständig, eine Zeile je Korpus-ID.
- Der Linkblock „Weitere Auswertungen" auf `index.html` (Abschnitt `58-weitere`) trägt `zeit.html` in
  jedem Profil. Einen Link auf die Feeds trägt `index.html` nicht, auch nicht in der laufenden Periode
  (Plan § 7, Frage 9.11): die Liste erreicht man über den Linkblock, und „höchstens ein Link" heißt
  hier keiner.

**Der Prüfsatz kommt aus `guete.json`, die Zahlen je Kategorie aus den Labels, gebunden an
`VALIDATED`.** `read_check` liest `validierung/17-zeit-f4/guete.json` (Satz, Modelle, Übereinstimmung
bei Thema und Ebene) und zählt aus `stichprobe.csv` und `labels.csv` je Kategorie „richtig k von n"
(„unklar" gezählt, nicht gewertet, Frage 9.13) und „nennt die Bundesebene m von k" unter den
richtigen (§ 4.1). Die Summe muss `analysis.lexicon.VALIDATED` für die Version des Lexikons gleichen
(94 von 100), sonst `SchemaError`: eine neue Kodierung macht die Konstante ungültig, wie `RULE_CHECK`
bei `akteure.html` (Punkt 88, N1). Nennt `VALIDATED` die Version nicht, zeigt die Seite keine Zahl je
Kategorie und sagt, dass die Version nicht geprüft ist. Verworfen: die Präzision als Konstante neben
`VALIDATED` (zwei Stellen für eine Zahl) und die Zahlen je Kategorie als Konstante (sie stehen in
Dateien im Repo, und ein Test rechnet sie aus ihnen nach).

**Die Familie mit Wort, Holm und Commit; „nicht bestätigt" so groß wie „bestätigt".** Die Seite liest
`zeit_hypothesen` und zeigt die Zeilen mit `p_holm` als Tabelle (Ergebnis, Effekt, p, Holm, n) und je
Hypothese einen Absatz mit dem Satz aus § 8 (`HYPOTHESES`), Maß, Test und Commit der Festlegung
(`PREREGISTRATION`: `9c7b3d6`, 2026-11-23 um 19:45, verlinkt). Beide Wörter stehen im selben Element
mit derselben Klasse. H17.1 nennt die Randomisierung, die nicht entscheidet; H17.2 den Satz zu S2.1
(Frage 9.14: ohne die Haushaltsanträge 12,9 % unter dem Kalendermonat, zweiseitig p = 0,246, also
trägt der Haushalt die Spitze selbst); H17.3 seine Gültigkeit aus `VALIDATED` und `MIN_PRECISION`.
Die übrigen Zeilen stehen darunter ohne Wort, je mit Rolle (Sensitivität, explorativ). Trägt die
Tabelle eine Festlegung, die nicht `PREREGISTRATION` ist, oder eine Hypothese der Familie, die
`HYPOTHESES` nicht kennt, ist das ein `SchemaError`. Die Tabelle gibt es nur im Profil, das die Tests
rechnet; sonst sagt `tests_elsewhere` aus den Paketprofilen, über welche Perioden die Tests rechnen
und auf welcher Seite sie stehen (2014–2020 und laufende Periode: auf der der Hauptperiode;
Hauptperiode ohne Vergleich: erst im Lauf, der die Perioden vergleicht), oder dass für den Datensatz
keine festgelegt sind (Mönchengladbach). Keine Seite verlinkt eine andere Periode: die Unterseiten
liegen auf Pages unter der Stadtseite, im Monitor aber allein.

**Gemessen oder explorativ.** Das Lexikon ist an den drei Düsseldorfer Datensätzen gemessen
(`stichprobe.json`); ein Datensatz außerhalb heißt beim Vokabular „explorativ", mit Stadt und Periode
der gemessenen (Punkt 88, N5). Die Ereignisspuren heißen es immer (§ 8.4), die Zeilen je Kategorie
ebenso (S3.3). Die Zählungen des Rhythmus heißen „beschreibend": sie prüfen nichts.

**Was einem Profil fehlt, sagt die Seite** (Plan § 6). Mönchengladbach hat in keinem Wahljahr einen
Haushaltsmonat (`docs/todo.md`, Punkt 13 (d)): unter „In diesem Profil fehlt" und im Abschnitt steht,
dass in keinem vollständigen Wahljahr fünf Haushaltsanträge stehen (zusammen 2), und dass die
Zählung nicht zeigt, ob sie dort anders heißen. Die laufende Periode hat ein Wahljahr, also keinen
Median je Kalendermonat und noch kein Vorwahljahr; beides steht dort.

**Die Feeds mit dem Stand der Daten** (Plan § 7, Frage Z.3 mit ihrer Annahme). Der Abschnitt listet die
Feeds aus `wahlbezirke_feeds` mit relativem Link auf `feeds/wahlbezirk-NN.xml` (Einträge, Dokumente
der Periode, neue der letzten 30 Tage, zuletzt geändert), dazu den Stand: das neueste Vorlagendatum,
dasselbe, das der Schritt `feeds` als Stand nimmt (13.10.2026 im Paket). Darunter der Satz, dass die
Feeds ohne laufenden Abruf diesen Stand zeigen und sich erst mit einem neuen Schnappschuss oder einem
Timer ändern. Damit der Satz wegfällt, wenn der Timer läuft, ist `feeds.timer` neu (Vorgabe aus;
`deploy/monitor.env.example` setzt `GEOREP_FEEDS__TIMER=true`). Er ist reine Anzeige und steht
darum nicht im Settings-Fingerprint, sondern im Zusatz von `report` und der Unterseiten
(`report_fingerprint`, Review K2): ein Wechsel öffnet nur diese Schritte, ein Test prüft das. Verworfen: den Timer aus dem Stamp
des Netzschritts `papers` zu erschließen (auf einem Rechner, der einmal abgerufen hat, fiele der Satz
weg, ohne dass ein Timer läuft). Kein `rel="self"` (Frage 28), keine Straßennamen (Frage 27).

**Für alle Fraktionen und Gremien gleich gebaut.** Die Seite nennt keine Fraktion; die Gremien der
Ereignisspuren heißen beim Namen aus `[bodies]` (`actors.body_name`), nach Treffern geordnet, ab 20
Dokumenten mit Text. Tests verlangen, dass kein Parteiname eines Paketprofils in den Vorlagen, im
Text einer gerenderten Seite und in der Spaltendoku steht; die Vorlagen tragen kein Stadtwort
(`test_report_city.py`).

**Bewusst anders als § 7.**

1. Keine feste Markierung der Sommerpause: welche Monate Ferien sind, ist je Land und Jahr anders und
   stünde als Stadtwissen in der Seite. Die Seite nennt den schwächsten Kalendermonat im Median aus den
   Daten (Hauptperiode: Juli, 130 Dokumente), die Monatstabelle zeigt den Rest.
2. Drei Reihen (Verwaltung, Fraktionen, Übrige) mit je eigenem Maßstab statt gestapelter Balken: die
   Tests zählen die Fraktionen, und in einem Stapel wären ihre Monate nicht abzulesen. Je Reihe ein
   SVG-Pfad statt eines Rechtecks mit Titel je Monat (14 KB weniger in der Hauptperiode); die Zahlen
   stehen in der Tabelle darunter, die Beschriftung der Wahljahre als HTML unter den Reihen, damit sie
   bei 390 Pixeln lesbar bleibt (`preserveAspectRatio="none"` streckt nur die Balken).
3. Die Hypothesen als Tabelle mit einer Zeile je Hypothese für die Zahlen und je Hypothese ein Absatz
   für Satz, Maß, Test und Festlegung, statt alles in einer Zeile: auf einem schmalen Bildschirm
   wäre die Zeile nicht zu lesen.
4. Die Tabelle des Vokabulars zeigt die Wahljahre des eigenen Datensatzes; die Anteile aller drei
   Perioden stehen bei H17.3. Der kleine Balken misst je Zeile (der höchste Wert der Zeile füllt die
   Zelle), weil die Kategorien zwei Größenordnungen auseinanderliegen. Die Summenzeile der
   Strukturkategorien heißt nur dort „das Maß von H17.3", wo für den Datensatz Tests festgelegt sind
   (nicht in Mönchengladbach, Review N3).
5. Ereignisspuren über den ganzen Datensatz und die Gremien nach Treffern mit ihrem Anteil im
   Datensatz, nicht die Fenster und Vorjahre aus § 3.5: die waren nach dem Ansehen gewählt, und eine
   feste Regel gilt für jede Stadt gleich. Ein Monat trägt einen Anteil erst ab 20 Dokumenten mit Text
   (`MIN_MONTH_DOCUMENTS`, dieselbe Grenze wie für ein Gremium): in Mönchengladbach wäre sonst „2 von
   3" im November 2021 die Spitze gewesen; dort bleiben 55 von 61 Monaten leer, und die Seite sagt
   das. Einen höchsten Monat nennt die Seite erst ab fünf Treffern in ihm (`MIN_PEAK_HITS`, Review
   N3: in der laufenden Periode war sonst ein Treffer unter 51 Dokumenten des angebrochenen Oktobers
   2026 die Spitze des Kriegs). Der Monat des Datenstands heißt in der Monatstabelle und an einer
   Spitze „angebrochen", wenn das neueste Dokument vor seinem Ende liegt. Ortsereignisse
   (`[[lokal]]` im Lexikon) fehlen (Frage 9.12).
6. Größe 59 bis 82 KB statt 40 bis 80: der Rahmen allein sind rund 31 KB (Zahlen unten).
7. `analysis.cycles.wahljahr_of` ist öffentlich: die Seite zählt je Wahljahr mit derselben Zuordnung
   wie H17.3.

**Verworfen.** Ein eigenes Skript für die Seite (sie braucht keines; Tabellen und Vorschau kommen
aus dem Rahmen); Links von einer Periodenseite auf die der Hauptperiode (siehe oben); die
Sensitivitäten auf einer eigenen Seite (22 Zeilen, rund 4 KB).

**Geprüft.**

- Roter Lauf zuerst, ohne Registrierung von Seite und Tabellen, ohne `templates/pages/zeit.*` und
  ohne `feeds.timer`: `uv run pytest tests/unit/test_report_cycles.py -n 3` mit Exit 1, 17 von 38
  rot (Commit-Body nennt sie).
- Tests: `tests/unit/test_report_cycles.py` (Bausteine an erfundenen Tabellen, Prüfsatz aus einer
  geänderten `guete.json`, `VALIDATED` gegen geänderte Labels, eine ungeprüfte Lexikonversion, die
  Wahljahre mit Rolle und S1.6, kein Haushaltsmonat, die Familie mit Wort und Commit, eine fremde
  Festlegung, wo die Tests stehen je Profil, explorativ, die Feeds mit Stand und Satz und mit
  `timer`, kein Parteiname, Register, Linkblock, kein Feed-Link auf `index.html`, Downloads mit
  Spaltendoku, Stamp von `report`, Eingaben von `page_zeit` je Profil). Slow in
  `tests/golden/test_cycles_numbers.py` die Zahlen der Seite in den drei Düsseldorfer Datensätzen:
  Fraktionsdokumente und Haushaltsmonat je Wahljahr (§ 3.1, § 3.2), die Anteile der
  Strukturkategorien und aller Kategorien je Wahljahr (§ 3.3, S3.2), S1.6 (1 380 gegen 1 399,0, Rang
  3 von 5; 1 434 gegen 1 573,3, Rang 4 von 4), Wort, p und Holm der Familie, die Spitzen der
  Ereignisse (§ 3.5: Corona im Juli 2021 mit 33 von 119, der Krieg im März 2022 mit 24 von 413) und
  jede Seite unter 500 KB.
- Bildschirmfotos mit headless Chrome bei 1280 und 390 Pixeln Breite und bei 390 ohne Skripte (an
  einer Kopie ohne `<script>`, deren `<noscript>`-Stil wirkt), je für die Hauptperiode und die
  laufende Periode mit der Feed-Liste: die Beschriftung der Wahljahre bleibt bei 390 Pixeln lesbar;
  ohne JavaScript stehen alle Zeilen der Tabellen offen und kein Knopf „alle Zeilen zeigen". Danach
  brechen der Name eines Feeds und der Monat nicht mehr um (Folgecommit, nur CSS).
- Review Runde 1 (2026-11-27): K1 (der Ort der Tests auf den Periodenseiten), K2 (`feeds.timer`
  nicht im Settings-Fingerprint), N2 (die CSV des Vokabulars), N3 (Spitze ab fünf Treffern, der
  angebrochene Monat, die Summenzeile ohne Tests) je mit rotem Test zuerst; N1 (Spaltenschema nur in
  `schema.json`) nimmt der Supervisor als Rückstand für das ganze Register auf.
- A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt 66 (`scripts/ab_bau.sh`,
  `scripts/ab_vergleich.py`), `POLARS_MAX_THREADS=4 OMP_NUM_THREADS=2`, A aus `main` `36fad29`
  (`v0.36.0`, mit den Downloads von 11 und 12), B aus `a0c2ff1` (nach Runde 2 und dem Merge von
  `36fad29`), beide über `git archive`, Wurzeln `ab/17s-a2` und `ab/17s-b2` auf xtraspace, die fünf
  Profile mit `bootstrap` und `run` in der Folge von `pages.yml`, dann `publish --strict-budget`.
  Unter `site/` 258 Dateien in A, 288 in B, 38 Abweichungen, alle erwartet: je Stadtseite
  (Hauptperiode, 2014–2020, laufende Periode, Mönchengladbach) neu `zeit.html` und die sechs
  Downloads von `zeit_monate`, `haushaltsmonate` und `dokumente_bundesvokabular`, in der
  Hauptperiode dazu die zwei von `zeit_hypothesen`; anders nur `index.html` (Linkblock, Zahl der
  Downloadzeilen, die neuen Zeilen in den Downloads, die Größe von `schema.json`, die Einträge im
  Spaltenschema; sonst bytegleich bis auf die Prüfsummen, die an `generated_at` hängen) und
  `schema.json` je Stadtseite. Die 41 Feeds unter `2025/feeds/` sind bytegleich, ebenso
  `akteure.html`, `vergleich.html` und jede `summary.json`. Über die ganzen Datenwurzeln 994 und
  1 074 Dateien, 223 Abweichungen: dieselben Seiten und Downloads in den Ordnern der Profile, kein
  Parquet unter `processed/` oder `interim/` anders, und 129 Stamps: 6 neue von `zeit.html`, 109 nur
  in der Schreibzeit (der Settings-Fingerprint ist nach K2 gleich; im ersten A/B-Bau gegen
  `f27473f` standen dieselben 109 Stamps mit anderem Fingerprint da), 6 von `akteure.html` in
  `extra`, weil die Vorlagen der Seiten im Hash des Berichts stehen, 6 von `index.html` in `extra`
  und den neuen optionalen Eingaben, 2 nur in der Wurzel der absoluten Pfade
  (`wahlbezirke_vergleich`, `zeit_hypothesen`).
- Größen, veröffentlicht (`publish`): `index.html` der Hauptperiode 948 839 → 957 828 Byte
  (+8 989, davon die Spaltendoku von `zeit_hypothesen` mit 19 Spalten; Budget 1 000 000; mit 15, 11
  und 12 jetzt +20 300 über dem Bau vor `v0.33.0`, Ziel der Phase höchstens +30 KB),
  `2014-2020/` 827 359 → 833 053 (+5 694), `2025/` 723 285 → 728 964 (+5 679),
  `moenchengladbach/` 810 780 → 816 466 (+5 686). `zeit.html`: Hauptperiode 81 612, 2014–2020
  77 643, laufende Periode 58 618, Mönchengladbach 68 901 Byte; mit `akteure.html` sind es je
  Profil 126 bis 187 KB Unterseiten (Budget 1 MB). `dokumente_bundesvokabular.csv` nach N2:
  Hauptperiode 1 965 933 → 176 649 Byte, 2014–2020 2 272 822 → 142 023, laufende Periode
  420 986 → 16 413, Mönchengladbach 295 230 → 14 741. Die Downloads von 17 machen die
  veröffentlichte Seite 1,2 MB größer (53,0 → 54,2 MB); die Pakete im Repo ändern sich nicht.

## 91. Die Unterseite `vorgaenge.html` und der allgemeine Dialog-Haken: Prüfsatz aus drei `guete.json`, gemessen nur die Hauptperiode, `verweise` kein Download (Vorhaben 14, Stufe 3, und Vorarbeit V2, 2026-11-27)

Stufe 3 von Vorhaben 14 nach `docs/plans/14-vorgaenge.md`, § 7 und § 10, und Vorarbeit V2 nach
`docs/plan-zeigen-2026-11.md` (§ 4, § 5, `v0.36.0`), im Muster von `akteure.html` (Punkt 88). Gebaut
auf `feat/14-vorgaenge-seite` ab `main` `f27473f` (`v0.35.0`). Die Nummer bekommt der Eintrag beim
Merge.

**Der Dialog-Haken (V2).** Ein Beitrag hängt im Dokumentdialog der Hauptseite je Dokument eine Zeile
an, ohne dass `dokumente.json` wächst: `Contribution.dialogs` trägt `report.dialog.DialogHook`
(Name, Titel, Satz für die Downloads, Eingaben, Zeilen je Korpus-ID, Schalter), und `report` schreibt
nach `dokumente.json` je Haken `data/<name>.json`. Format 2 (seit Review K3; 1 ohne `show`): Wörter (`labels`), die Felder eines Ziels als Text des Links (`show`), eigene Ziele
(`documents`, je `[link, datum, drucksache, titel]`) und Zeilen `{Index in dokumente.json: [[wort],
[wort, ziel], …]}`; ein Ziel ≥ 0 ist ein Index in `dokumente.json`, < 0 ein Dokument der Datei. Ein
Eintrag ohne Ziel ist nur ein Wort („angenommen im Rat am …" für 26), ein Eintrag mit Ziel ein Wort
und eine Drucksache mit Link (14) oder eine Liste ähnlicher Dokumente (18). `data-extras` am
`<dialog>` nennt die Dateien; `frame/dialog.js.j2` lädt jede beim ersten Öffnen einmal
(`loadJson`), hängt „Titel: Wort Drucksache; …" unter jedes Dokument mit einer Zeile und den Satz
der Datei (`note`, etwa der Prüfsatz) hinter den Hinweis oben im Dialog, den `showDocuments` bei
jedem Öffnen neu setzt. Ohne JavaScript gibt es keinen Dialog, die Seiten bleiben lesbar.

- *Indizes statt Kennungen*: `dokumente.json` trägt keine Korpus-IDs, und fünf Ziffern sind kürzer
  als eine OParl-URL (in der Hauptperiode rund 75 Zeichen). Beide Dateien schreibt derselbe Schritt
  aus derselben Folge (`documents.document_order`, aus der `documents_payload` seine Liste baut, ein
  Refactoring mit denselben Bytes); `write_dialogs` liest Präfix und Länge der eben geschriebenen
  `dokumente.json` und bricht ab, wenn die Länge nicht zur Folge passt. Zeilen gibt es nur für
  Dokumente, die der Dialog zeigen kann.
- Die Eingaben der Haken stehen im Stamp von `report` (`dialog.contributed_dialog_files`, eine Datei,
  die schon als Tabelle dasteht, nur einmal); die Datei eines abgeschalteten Hakens fliegt aus
  `site/data/`. Ein Name unter `data/` ist nur einmal zu haben (nicht `dokumente`, `begriffe`,
  `schema`, `summary`). Die Datei steht ohne Leerzeichen nach den Trennern da (in der Hauptperiode
  rund ein Zehntel kleiner) und als JSON-Zeile in den Downloads.
- *Größe*: anfangs wuchs das Skript des Rahmens um 1 013 Byte auf jeder Seite; seit Review N1 steht
  der Haken nur dort, wo der Dialog `data-extras` trägt (heute nur auf der Hauptseite), und mit den
  Punkten K3 und N3 des Reviews (unten) wächst `index.html` um 1 541 Byte samt Attribut. Das
  Budget von „unter 1 KB" (Plan § 5) ist damit überschritten; der Test misst die ganze Hauptseite
  mit und ohne Haken und hält sie unter 1 600. Die Erklärung steht als Jinja-Kommentar in der
  Vorlage und kostet nichts; das Skript nutzt `line` des Rahmens (gibt das Element dann zurück) und
  `new URL(link, base)`.

*Verworfen*: `dokumente.json` erweitern (Synergien § 1: es wächst nicht); Kennungen als Schlüssel
(siehe oben); die Datei im Schritt der Unterseite schreiben (er kennt die Folge von `dokumente.json`
nicht, ohne sie nachzubauen); ein Skript je Haken (18 und 26 hängen sich nur mit Daten an).

**Was `vorgaenge.html` zeigt** (`report/procedures.py`, `templates/pages/vorgaenge.*`), in allen fünf
Paketprofilen hinter `procedures.enabled`:

1. *Antworten je Gremium*: Anfragen, Antwort im Ratsinformationssystem gefunden (Zahl und Anteil),
   Median und Q3 der gültig datierten Antwortzeit ab 30 datierten Antworten (Review K1), deren n
   daneben; eine Zeile je Gremium ab 30
   Anfragen, Gremien beim Namen wie auf `akteure.html`. Darüber der Satz, dass ein fehlender Anhang
   keine fehlende Antwort ist, und für Gremien unter 20 % der Hinweis (†) auf die Sitzung und die
   Niederschrift. **Der Gast von 26 heißt `in-der-sitzung`**: steht er auf der Seite
   (`{% if data.session_guest in guests %}`, Punkt 86), verlinkt der Satz dorthin, und † fällt weg.
   Der Name folgt dem Bauplan von 26 (§ 7, Abschnitt 3 „in der Sitzung beantwortet"); wählt 26
   einen anderen, ändert sich `procedures.SESSION_GUEST`.
2. *Je Fraktion*, in jedem Datensatz „explorativ" (Frage 14): Anfragen, beobachtet gegen erwartet über
   `analysis.practice.observed_expected` (Schicht das Gremium, die Fraktionen aus den Antragstellern
   von 15, Synergien Konflikt 10) mit dem exakten 95-%-Intervall nach Poisson, nicht sortierbar
   (Review K2), daneben der Median der Antwortzeit ab 30 datierten Antworten mit deren Zahl. Keine rohe Quote und keine Spalte, aus der sie folgte; der Median steht, wie er ist,
   und sortiert nicht (wie „Kontrolle roh" auf `akteure.html`). Eine Partei neben ihrer späteren
   Fraktion bekommt den Satz aus Punkt 88, aber nur, wenn ihre Anfragen alle vor dem Beginn der
   Fraktion liegen.
3. *Ohne gefundene Antwort: Kandidaten*: Drucksache mit Link, Datum, Gremium, Urheber, Tage beim
   Abruf; nur Gremien mit einer Praxis ab 70 % in der Periode und älter als P90 der Antwortzeit.
4. *Vorgänge*: Zahl, Dokumente, Größenverteilung (Tabelle mit Balken), die starken Kanten nach Typ
   und Fundstelle, die schwachen als Zahl mit dem Grund, warum sie nicht zählen.

Die Downloads `vorgang_kanten` (mit `stark`), `dokumente_vorgang` und `antwortzeiten` als Parquet und
CSV mit Spaltendoku; kein Parteiname und kein Stadtwort in Vorlage, Spaltendoku und gerenderter
Seite (Tests).

**Der Prüfsatz kommt aus drei `guete.json`, nicht aus zweien.** Die Kennzahl ist die Prüfstichprobe der
Rückfallregel (`14-vorgaenge-3-f4`, Punkt 87): 50 von 50 Verbindungen als dieselbe Sache bestätigt,
für die 1 710 Verbindungen gewichtet 1,000 (Wilson bei Kishs n 0,928–1,000), mit dem Satz und den
Modellen daraus und der Folge der Schichten (Titel 43, Nachtrag 4, Sammelbericht 2, Anlage 1; „je
Fundstelle keine Prüfung"). Warum Nummern nur im Text nicht zählen, sagen die beiden Stichproben davor:
Regelfassung .1 an Stichprobe 1 (`14-vorgaenge-f4`, 139 von 150) und Regelfassung .2 an der
Bestätigung (`14-vorgaenge-2-f4`, 85 von 100), beide unter dem vorab festgelegten 0,95, beide von
Kodierern desselben Modells. Der Auftrag nannte `-f4` und `-3-f4`; den Satz aus § 7 („weil sie an 100
geprüften Kanten nur zu 85 % trugen") trägt aber die Bestätigung, und eine Zahl auf der Seite kommt
nur aus `guete.json` (Synergien § 10). Die 104 von 106 und die 154 von 156 aus § 5.1 und § 4.3
stehen nicht auf der Seite: sie sind keine Zahl einer `guete.json`. Die Namensregel der
Antwortanlagen (712 verschiedene Namen an den Anfragen der Hauptperiode) ist von keinem Kodierer
geprüft (Frage 48, Messdokument Frage 9.5); die Seite sagt das.

**Gemessen ist nur die Hauptperiode.** `stichprobe.json` der Prüfstichprobe nennt `duesseldorf`; mit
ihr gilt `duesseldorf-vergleich` als gemessen (derselbe Ordner). Die beiden anderen Düsseldorfer
Perioden und die zweite Stadt heißen in jeder Überschrift „explorativ" (Gültigkeitsregel, Plan § 8;
Messdokument § 4.3, „Was folgt"). Das ist anders als bei `akteure.html`, wo die Stichprobe aus allen
drei Düsseldorfer Perioden gezogen ist. Die zweite Stadt ist der Prüfstein: ohne die Rolle Anfrage
im Profil sagen die drei ersten Abschnitte, was fehlt, und nur die Vorgänge stehen da.

**Der Vorgang im Dialog** (der Haken `vorgaenge`, `procedures.dialog_rows`): je Dokument seine
starken Kanten in beide Richtungen mit einem Wort je Typ und Richtung („Antwort auf", „beantwortet
in", „umgesetzt in", „geändert durch", „genannt im Sammelbericht", …), neueste zuerst; `bezug`
höchstens fünf, dann „und N weitere Nennungen" (Frage 9.7). Keine Textkante, auch nicht als
„ungeprüft" (§ 5.1). Ziele in einer Nachbarperiode kommen mit Link aus deren Paket (0,2 s). Der Satz
der Datei nennt die Regel und die Prüfung aus `guete.json`, außerhalb der Hauptperiode mit
„explorativ". Grenze: eine Kante, die eine Drucksache einer *späteren* Periode auf ein Dokument
legt, kennt nur das spätere Profil; im Dialog des früheren fehlt sie (`docs/todo.md`, Punkt 12 (g)).

**`verweise.parquet` ist kein Download** (todo 12 (e)). Wo seine Spannen liegen, hängt vom Rechner
ab: lokal auf dem Rohtext aller Profile, auf Pages nur in der Hauptperiode, deren Paket einen
Rohtextstore trägt; dieselbe Zeile meint dann je nach Rechner andere Zeichen, und nur `extractor`
sagt es. Eine veröffentlichte Datei soll auf jedem Rechner dasselbe heißen. Die Kanten und die
Vorgänge hängen nicht am Rohtext (sie kommen aus dem Textstore und den Titeln) und sind Downloads.
Wenn jedes Profil einen Rohtext trägt oder die Spannen immer auf dem Textstore liegen, kann die
Tabelle nachkommen.

**Bewusst anders als § 7.**

1. Drei `guete.json` statt der „104 von 106" (siehe oben).
2. Ein Verhältnis je Fraktion erst ab 10 *erwarteten* Antworten, nicht nur ab 30 Anfragen: in der
   Hauptperiode hat eine Fraktion 129 Anfragen, fragt aber fast nur im Rat, der in der Sitzung
   antwortet; erwartet sind rund zwei Antworten, und das Verhältnis (1,45) hinge an einer einzigen.
3. Kandidaten nur aus Gremien, deren Praxis an mindestens 30 Anfragen gemessen ist (wie § 3.8: „27
   Gremien mit mindestens 30 Anfragen"); sonst stand ein Ausschuss mit drei von vier Antworten (0,75)
   unter den Gremien mit Praxis.
4. Die Seite ist 36 bis 132 KB groß statt unter 50: der Rahmen allein ist rund 31 KB (wie bei
   `akteure.html`), die Kandidaten in 2014–2020 sind 301 Zeilen (82 KB). Das Budget von 500 KB je
   Unterseite hält sie mit Abstand.
5. Der Median je Fraktion sortiert nicht, nur Anfragen und das Verhältnis (Frage 14).
6. Neben den Typen stehen die Fundstellen der starken Kanten als zweite kleine Tabelle; eine
   Grafik gibt es nur als Balken in der Tabelle der Größen.
7. Titel der Ziele im Dialog sind auf 100 Zeichen gekürzt und stehen nur als `title` am Link: so
   bleibt `vorgaenge.json` der Hauptperiode unter 100 KB (95 011 Byte, gzip 30 491).

**Geprüft.**

- Tests: `tests/unit/test_report_dialog.py` (Format, Indizes, Ziele, die Folge von `dokumente.json`,
  Register, Stamp von `report`, Schreiben und Aufräumen, eine fremde Folge bricht ab, Attribut am
  Dialog, Größe des Hakens); `tests/unit/test_report_procedures.py` (Bausteine an einer erfundenen
  Stadt, Prüfsatz aus `guete.json` je Paketprofil, eine geänderte `guete.json` ändert die Seite,
  explorativ außerhalb der Hauptperiode, der Gast `in-der-sitzung`, kein Parteiname, Register,
  Linkblock, Downloads mit Spaltendoku, der Haken auf der Hauptseite, erlaubte Links); slow in
  `tests/golden/test_procedures_page.py` die Zahlen der Hauptperiode aus den Paketen (3 952
  Anfragen, 1 239 mit Antwort, 1 223 als Anlage; Median 18 Tage, Q1 13, Q3 71, P90 139 an 1 238;
  27 Gremien, 15 unter 20 %; 110 Kandidaten; 1 525 Vorgänge mit 3 100 Dokumenten, 1 346 Paare;
  1 960 von 7 310 Kanten stark; beobachtet gegen erwartet je Fraktion), die zweite Stadt ohne
  Anfragen und explorativ, beide Seiten unter 500 KB.
- Bildschirmfotos mit headless Chrome von `vorgaenge.html` der Hauptperiode bei 1280 Pixeln hell
  und dunkel, bei 390 Pixeln und bei 390 ohne Skripte (an einer Kopie ohne `<script>` und mit dem
  Inhalt von `<noscript>`: alle 110 Kandidaten stehen da, keine Schaltfläche), der zweiten Stadt bei
  1280, und vom Dokumentdialog der Hauptseite über einen lokalen Webserver, geöffnet für einen
  Begriff mit neun Dokumenten: acht tragen ihre Zeile „Vorgang: …" mit verlinkter Drucksache, der
  Satz zur Prüfung steht oben. Die Fotos fanden die Tabelle der Gremien, die mit `nowrap` über die
  Breite ging (bei 1280 fiel die Spalte Median heraus), und einen verschluckten Zeilenumbruch im
  Skript; beides in `d7c4890` behoben.
- A/B-Bau aller Seiten aus den Datenpaketen wie in Punkt 66 (`scripts/ab_bau.sh`,
  `scripts/ab_vergleich.py`), `POLARS_MAX_THREADS=4 OMP_NUM_THREADS=2`, A aus `main` `f27473f`
  (`git archive`), B aus `d7c4890`, Wurzeln `ab/14s-a` und `ab/14s-b` auf xtraspace, die fünf
  Profile in der Folge von `pages.yml`, dann `publish --strict-budget`. Unter `site/` 255 Dateien
  in A, 287 in B, 44 Abweichungen, alle erwartet: je Stadtseite (Hauptperiode, 2014–2020, laufende
  Periode, Mönchengladbach) neu `vorgaenge.html`, `data/vorgaenge.json` und die sechs Downloads;
  anders `index.html` (der Eintrag unter „Weitere Auswertungen", sieben Zeilen in den Downloads,
  die Zahl der Downloadzeilen, die Größe von `schema.json`, drei Einträge im Spaltenschema,
  `data-extras` am Dialog und der Haken im Skript; sonst bytegleich bis auf die Prüfsummen, die an
  `generated_at` hängen), `akteure.html` (nur der Haken im Skript des Rahmens, 1 013 Byte) und
  `schema.json` (die drei Tabellen); `vergleich.html` und jede `summary.json` gleich. Über die
  ganzen Datenwurzeln 988 und 1 074 Dateien, 239 Abweichungen: dieselben Seiten und Downloads in
  den Ordnern der Profile, **kein Parquet unter `processed/` oder `interim/`**, und 129 Stamps
  (109 nur in `written`, 6 neue von `vorgaenge.html`, 6 von `akteure.html` in `extra`, weil
  `report_fingerprint` die geänderten Vorlagen zählt, 6 von `index.html` in `extra` und den
  Eingaben, 2 nur in der Wurzel der absoluten Pfade).
- Größen, veröffentlicht (`publish`): `index.html` der Hauptperiode 941 988 → 950 043 Byte
  (+8 055: Haken 1 037, das Übrige Linkblock, Downloadzeilen und Spaltenschema; Budget 1 000 000,
  mit `akteure.html` zusammen 12,7 KB des Ziels von höchstens +30 KB der Phase), `2014-2020/`
  827 359 → 835 406, `2025/` 723 285 → 731 326, `moenchengladbach/` 810 780 → 818 794.
  `vorgaenge.html`: Hauptperiode 82 308, 2014–2020 132 066, laufende Periode 49 674,
  Mönchengladbach 36 737 Byte. `vorgaenge.json`: 95 011 (gzip 30 491), 45 112, 20 624, 6 650 Byte;
  zusammen rund 167 KB nachgeladen, im Budget von 1,5 MB je Profil. Die Downloads machen die
  veröffentlichte Seite 11,4 MB größer (46,9 → 58,4 MB): je Profil 4,67, 4,68, 1,02 und 0,51 MB,
  fast alles CSV und davon am meisten `dokumente_vorgang.csv` (2,80, 3,22, 0,60, 0,42 MB, eine
  Zeile je Dokument mit zwei OParl-URLs). Die Pakete im Repo ändern sich nicht.

**Nachtrag (Supervisor, 2026-11-27, vor dem Review): die CSV von `dokumente_vorgang` trägt nur die
Dokumente in einem Vorgang.** Ein Dokument mit `rolle = ohne` (`groesse = 1`, in der Hauptperiode
16 008 von 19 108) sagt in der CSV nichts, was nicht aus seinem Fehlen folgt. Gebaut über den
`CsvPlan` aus Punkt 89 (`procedure_csv_rows`), wie das Vokabular von 17 (Punkt 90); das Parquet
bleibt vollständig, Downloadzeile und Spaltendoku (`groesse`) sagen es. Die CSV schrumpft je
Datensatz von 2,80 auf 0,46 MB (Hauptperiode, 3 100 Zeilen), 3,22 auf 0,15 (2014–2020, 1 042),
0,60 auf 0,08 (laufende Periode, 501) und 0,42 auf 0,03 MB (Mönchengladbach, 217), zusammen von
7,05 auf 0,73 MB. Die beiden anderen CSV bleiben vollständig: in `vorgang_kanten` sind die
schwachen Kanten (73 % der Zeilen in der Hauptperiode) selbst eine Aussage (B nennt A im Text),
die die Seite nennt; nur die starken hießen 2,55 statt 0,63 MB über alle vier Datensätze, das wäre
eine andere Tabelle. In `antwortzeiten` ist jede Zeile eine Anfrage, und „keine" ist die Aussage,
von der die Kandidaten handeln (0,85 MB zusammen).

**Nachtrag: Review Runde 1 (2026-11-27).** Das Review von `0f75b71` fand keine falsche Zahl;
nachgezogen, je Punkt ein Commit mit rotem Test:

- *K1* (`7ea843c`): Median und Q3 je Gremium erst ab 30 datierten Antworten wie je Fraktion
  (`procedures.at_least`); in der Hauptperiode steht bei 16 der 27 Gremien „unter 30".
- *K2* (`c24873d`): hinter jedem Verhältnis je Fraktion das exakte 95-%-Intervall nach Poisson
  (`poisson_ratio_interval`, Garwood), die Spalte sortiert nicht; in allen drei Düsseldorfer
  Perioden enthält jedes Intervall 1, und der Satz unter der Tabelle sagt, was das heißt.
- *K3* (`661a872`): der Haken trägt 18 und 26 jetzt wirklich nur mit Daten. Je Dokument und Haken
  ein Platzhalter in Registerfolge, gleich in welcher Folge die Dateien ankommen; die Sätze der
  Dateien unter der Liste; das Wort eines Eintrags nur beim Wechsel; `DialogHook.show` wählt die
  Felder eines Ziels als Text des Links (Format 2 von `data/<name>.json`).
- *N1* (`2d47ef0`): der Haken nur auf Seiten mit `data-extras`; die Unterseiten tragen das Skript
  wieder wie `main`, Byte für Byte, und der Test misst die ganze Hauptseite mit und ohne Haken.
- *N3* (`d3b4860`): ein Zähler je Öffnen, eine zu spät angekommene Datei schreibt nichts mehr; ein
  Link, den `new URL` nicht lesen kann, kostet nur sich.
- *N4* (`794b06f`): `write_dialogs` vergleicht auch den ersten und den letzten Link mit der Folge.
- *K4*: `a72d76c` und `d7c4890` sind in zwei slow-Tests rot (`test_context_pipeline`,
  `test_parties_numbers`: sie zählten die Datei des Hakens unter `site/data/` noch nicht mit);
  `0f75b71` macht sie grün, ein Umschreiben der Geschichte über den Merge von `main` hinweg lohnt
  nicht.
- N2 (Seite 36 bis 132 KB statt unter 50) bleibt, im Budget von 500 KB; N5 steht in
  `docs/todo.md`, Punkt 35.

Vorher, auf Wunsch des Supervisors: `main` `cd9c143` (`v0.37.0`, Punkte 89 und 90) hereingenommen
(`dbcb903`) und die CSV von `dokumente_vorgang` gekürzt (`809240a`, Nachtrag oben).

*A/B-Bau nach Runde 1* wie oben, A aus `main` `cd9c143`, B aus `794b06f`, Wurzeln `ab/14s-a2` und
`ab/14s-b2`. Unter `site/` 288 Dateien in A, 320 in B, 40 Abweichungen, alle erwartet: je Stadtseite
neu `vorgaenge.html`, `vorgaenge.json` und die sechs Downloads, anders nur `index.html` und
`schema.json`; `akteure.html`, `zeit.html`, `vergleich.html` und jede `summary.json` sind gleich.
Über die Datenwurzeln 1 074 und 1 160 Dateien, 235 Abweichungen, keine unter `processed/` oder
`interim/`: 100 unter den Seiten und 135 Stamps (109 nur `written`, 6 neue von `vorgaenge.html`,
12 von `akteure.html` und `zeit.html` nur in `extra` -- `report_fingerprint` zählt die geänderten
Vorlagen --, 6 von `index.html` in `extra` und den Eingaben, 2 nur in der Wurzel der absoluten
Pfade). `index.html` vorher → nachher: Hauptperiode 957 828 → 966 522 (+8 694, davon der Haken
1 541), `2014-2020/` 833 053 → 841 739, `2025/` 728 964 → 737 644, `moenchengladbach/`
816 466 → 825 119. `vorgaenge.html` 82 069, 131 956, 49 257, 35 724 Byte; `vorgaenge.json`
95 022 (gzip 30 499), 45 123, 20 635, 6 661. Die sechs Downloads je Datensatz 2,34, 1,61, 0,49
und 0,12 MB; die veröffentlichte Seite wächst von 54,2 auf 59,3 MB.

## 92. Die Auswertung als `details.html`, eine vorläufige Startseite, alte Anker per Skript (Startseite, Stufe U, 2026-11-27)

[plan-startseite-2026-11.md](plan-startseite-2026-11.md), § 3 und § 9 (U), freigegeben von Konrad
am 2026-11-27. Ein Umzug ohne neue Zahl: der Schritt `report` schreibt den bisherigen Inhalt von
`index.html` als `details.html` und an seine Stelle eine vorläufige Startseite; Karte, Zeitregler und
Kurzfassung bringt Stufe B.

**Was gebaut ist.**

- `Layout.site_details` (`site/details.html`); `Layout.site_index` bleibt `index.html` und mit ihm
  alles, was an der Startseite hängt: der Stamp des Schritts (erste Ausgabe), die Prüfung in
  `publish`, ob eine Stadt gelaufen ist, das Monitor-Skript und `georep paths`. `details.html` ist
  die zweite Ausgabe von `report`.
- `details.html` trägt im Kopf eine Zeile „Zur Startseite"; Titel, Abschnitte und Skripte bleiben.
- Die Startseite (`report/start.py`, `templates/start.html.j2`, aus demselben `ReportModel`): Kopf
  mit Datenstand, Linkblock (Details, Downloads `details.html#downloads`, die Unterseiten aus
  `model.pages`, die Hauptperiode, die ältere und die laufende Periode), die Marke für „Weitere
  Städte", ein `<noscript>`-Satz und ganz oben, vor dem Stil, `redirect_script` (unter 0,5 KB): jede
  Adresse, deren Anker kein Schlüssel der Startseite ist, ersetzt `location.replace` durch
  `details.html` mit demselben Anker, ohne Eintrag in der Chronik. Schlüssel der Startseite sind ids
  mit `start-` und in der Adresse `zeitraum` und `gremium` (`START_PREFIX`, `START_KEYS`).
- Die Unterseiten heißen im Kopf „Zur Startseite" (weiter `index.html`, die Startseite derselben
  Periode) und verweisen im Fuß für Quellen und Lizenzen auf `details.html`; `karte.html` führt
  „zurück zur Auswertung" auf `details.html`. `details` ist als Seitenname reserviert.
- `publish` setzt die Zeile „Weitere Städte" in beide Seiten (`NEIGHBOUR_PAGES`) und prüft das
  Budget je Datei: `_over_budget(root, budget, by_name)` nimmt je Dateiname eine eigene Grenze, in U
  noch keine; die 150 000 Byte der Startseite kommen mit Stufe B.
- Die Links mit Anker aus `docs/inhalt.md` (6) und `docs/workflow-ratsmitglied.md` (13) zeigen auf
  `details.html#…`, ebenso die Tabelle der Abschnitte je Seite in `inhalt.md`.

**Tests.** `tests/unit/test_report_start.py`: `details.html` trägt jeden Abschnitt des Profils in
der Folge der Nummern und die Startseite keinen; keine id auf `details.html` ist ein Schlüssel der
Startseite, und jede id der Startseite beginnt mit `start-`; der reguläre Ausdruck der
Weiterleitung, aus der Seite gelesen, lässt an zehn Ankern genau die richtigen stehen; jeder Link
`details.html#…` des Linkblocks trifft eine id. `test_published_page.py` verlangt alle 18
Abschnitte an der veröffentlichten Seite. Die 14 Testdateien, die den Inhalt der Auswertung
lasen, lesen `details.html`; der Schnappschuss von `georep steps` nennt die zweite Ausgabe.

**Geprüft im Browser** (headless Chrome über Port 8777 auf dem B-Bau): `/#suche=Benrath`,
`/#bezirk-17`, `/#suche=grafenberger%20allee`, `/2025/#monate` und
`/moenchengladbach/index.html#gremien` landen auf `details.html` mit demselben Anker;
`/#start-links`, `/#gremium=OVA`, `/#zeitraum=2024-10..2025-09&gremium=OVA` und `/` bleiben.

**A/B-Bau** aller fünf Profile wie `pages.yml` (`scripts/ab_bau.sh`, `POLARS_MAX_THREADS=4
OMP_NUM_THREADS=2`), A aus `main` `a6b1aab` (`ab/st-a`), B aus `e74027b` (`ab/st-b`; der
Doku-Commit danach ändert keine Seite). Verglichen wurde je Stadtseite und Periode das alte
`index.html` mit dem neuen `details.html`, sonst wie `scripts/ab_vergleich.py`. Unter `site/` 320
Dateien in A, 324 in B: neu sind die vier `details.html`. Je `details.html` genau eine Zeile anders
als das alte `index.html`, die Zeile „Zur Startseite" (+75 Byte), sonst gleich bis auf Zeitstempel
und Prüfsummen. Die übrigen 20 Abweichungen sind die erwarteten: je Seite der Stadt und Periode
`akteure.html`, `vorgaenge.html` und `zeit.html` in Kopf und Fuß (zwei Zeilen) und `karte.html`
im Rückweg (eine Zeile). `vergleich.html` und jede Datei unter `data/` sind gleich. Über die
Datenwurzeln 1 160 und 1 170 Dateien: neu die zehn `details.html`, anders 135 Stamps (Schreibzeit)
und 60 Seiten; kein Parquet, kein JSON unter `processed/`, `interim/` oder `site/data/` anders.
Bytes vorher → nachher:

| | `index.html` A | `details.html` B | `index.html` B (Startseite) |
|---|---|---|---|
| Hauptperiode | 966 522 | 966 597 | 15 848 |
| `2014-2020/` | 841 739 | 841 814 | 15 661 |
| `2025/` | 737 644 | 737 719 | 15 730 |
| `moenchengladbach/` | 825 119 | 825 194 | 15 649 |

**Bewusst nicht in U.** Der Kommentar in `15-suche.js` und im Rahmen nennt noch
`index.html#suche=…` und `index.html#bezirk-17`; beide stehen in `details.html` und hätten den
A/B-Vergleich um eine Zeile vergrößert. Die Unterseiten sprechen im Text von der „Hauptseite"
(Dokumentdialog, Zählung je Partei); das gilt für `details.html` weiter, mit Stufe B trägt auch die
Startseite den Dialog. `deploy/bin/georep-monitor.sh` misst als `PAGE_KB` jetzt die Startseite.

## 93. Die Startseite: Kurzfassung aus dem Modell, Karte aus eigenen Vektordaten, Straßenpunkte als Paket, Zeitregler in Monaten (Startseite, Stufe B, 2026-11-27)

[plan-startseite-2026-11.md](plan-startseite-2026-11.md), § 3 bis § 8, mit Konrads Antworten auf
§ 10 (S.3 ohne K5, S.4 `karte.html` unverändert, S.9 und S.10 nicht in B). Auf Punkt 92 (Stufe U)
folgt die eigentliche Startseite. Keine Zahl der Auswertung ändert sich; der Golden Master bleibt.

**Was gebaut ist.**

- *Kurzfassung* (`report/start.py`, `summary_sentences`): K1 Umfang (liegt der Anteil mit Text unter
  90 %, sagt der Satz es zuerst), K2 der sichtbarste und der am wenigsten sichtbare Wahlbezirk mit dem
  Vorbehalt der Wörterbuchgröße (`bias.hits_terms`), K3 die Leitfrage nur aus der Spalte über alle
  Wahlbezirke (ohne Regression: der Satz zur laufenden Periode), K4 die Gremien der Dokumente mit
  Treffer aus `model.bodies`. Jeder Satz verlinkt den Abschnitt von `details.html`, aus dem seine Zahl
  stammt. Die englische Kurzfassung ist das Makro `english` auf beiden Seiten; auf der Startseite ohne
  den Satz zur Sensitivität (K5) und mit dem Link auf die Downloads.
- *Karte* (`report/startkarte.py`, `templates/start/`): je Ort (Begriff, Wahlbezirk) ein Punkt;
  Lage aus Wikidata, aus dem Paket der Straßenpunkte, aus den Stimmbezirken des Straßenverzeichnisses
  oder aus der Fläche des Wahlbezirks (`ART_*`, der Satz dazu steht im Dialog). Grundkarte als
  inline-SVG in einer viewBox von 2 000 Breite (`compact_path`: ganze Zahlen, relative Schritte;
  41 Wahlbezirke 18 KB statt rund 52 KB auf der Hauptkarte), Grenzen der Stadtbezirke, Namen der
  Stadtteile; ohne Skript die Choroplethe der letzten zwölf Monate (`charts.classify`), dazu die Liste
  der 20 Orte. Mit Skript Kreise mit Fläche proportional zur Zahl, Punkte/Flächen, Zeitregler,
  Gremium, Ausschnitt je Stadtbezirk, Abstandssuche im Umkreis von 24 px, `aria-live`-Zeile, Dialog
  über `georep.showDocumentList`.
- *`data/karte.json`*, Format 1, mit Downloadzeile; *Straßenpunkte* als Netzschritt `street_points`,
  Paket (`georep pack --street-points`) und `bootstrap`, nach dem Muster von Punkt 80.
- *Budgets je Datei*: `report.start_budget_bytes` (150 000), `report.map_budget_bytes` (500 000);
  `SiteSummary` nennt die Startseite über ihrem Budget, `publish` prüft `index.html` und
  `karte.json` gegen ihre Grenze (`page_budgets`).
- *Nachzug aus U* (Supervisor, 2026-11-27): die Unterseiten nennen Details und Startseite statt der
  Hauptseite, die Kommentare im Rahmen `details.html#…`, der Monitor misst `details.html` als
  `seite_kb` und die Startseite als `startseite_kb`.

**Anders als der Plan oder dort offen, mit Grund.**

- *K2 nur bei vollem Text, der Halbsatz zum Wörterbuch erst ab r = 0,5* (Review von B, Supervisor,
  2026-11-27). Haben weniger als 90 % der Dokumente einen Text (dieselbe Grenze wie der Zusatzsatz in
  K1, `TEXT_SHARE`), entfällt K2 ganz, und die Kurzfassung hat drei Sätze: Mönchengladbach (650 von
  2 895 Dokumenten mit Text) nannte sonst das 28,9-Fache zwischen 0,065 und 0,002, eine Spreizung, die
  vor allem misst, welche Dokumente lesbar sind. Der Halbsatz „ein Teil davon liegt am Wörterbuch"
  sollte derselben Bedingung folgen, unter der `details.html` auf die Verzerrung hinweist. Dort steht
  der Absatz zur Größe des Wörterbuchs, sobald sich die Korrelationen rechnen lassen
  (`{% if model.bias %}` in `60-methode.html.j2`, `None` nur ohne Streuung): eine technische
  Bedingung, keine über die Stärke. Darum gilt die Grenze des Reviews, r ≥ 0,5 (`BIAS_R`, Treffer
  gegen Zahl der Begriffe). Mit ihr nennen die Hauptperiode (0,76), 2014–2020 (0,55) und die laufende
  Periode (0,69) den Halbsatz; Mönchengladbach (0,18) hätte ihn nicht, dort entfällt K2 ohnehin.
- *Sammeldokumente zählen in den Flächen*: ein Dokument mit mehr als 20 Orten trägt in `docs` statt
  der Orte seine Wahlbezirke als negative Zahlen. So steht es nicht als Punkt (§ 4.3), zählt aber in
  der Choroplethe und im Dialog eines Wahlbezirks, wie in der Auswertung.
- *Was die Karte zählt*: Dokumente aus `dokumente.json`, also über angezeigte Begriffe; die zehn
  Dokumente, die nur an einem versteckten Begriff hängen, fehlen hier wie im Dialog. Die Flächen
  zeigen Dokumente je Wahlbezirk, keine Quote; die Quote steht auf `details.html`.
- *Grenzen der Stadtbezirke*: die Wahlbezirke, vereinigt nach ihrem größten Anteil in
  `wahlbezirke_stadtbezirke`. Wahlbezirk 40 liegt in Düsseldorf zu 65 % in Stadtbezirk 9 und zu 35 % in
  10 und zählt auf der Karte ganz zu 9; die kanonischen Stimmbezirke tragen keinen Stadtbezirk.
- *Das Paket trägt alle Paare des Wörterbuchs*, nicht nur die mit Treffer (2 929 statt der 2 427 der
  Messung): die Perioden teilen das Wörterbuch, und die laufende Periode bekommt neue Treffer. 36 491
  und 23 063 Bytes statt der geschätzten 31 144.
- *`[street_points]` steht nicht im Settings-Fingerprint*; der Stamp des Netzschritts trägt Quelle,
  Raster und Namen als `extra` (Muster Punkt 53). Ein neuer Block im Fingerprint hätte jeden Schritt
  jedes Profils veralten lassen.
- *Medoid exakt*, nicht Median mit nächstem Punkt wie im Messskript des Entwurfs: der Punkt mit der
  kleinsten Summe der Abstände, bei Gleichstand der kleinste Ost-, dann Nordwert (hypothesis-Test).
- *`karte.json` trägt mehr als § 4.5*: `window` (die Voreinstellung), `ended` (für „Ende der
  Wahlperiode"), `max_places`, `arten` (die Arten der Gremien mit Wort) und `arts` (der Satz zur Lage);
  zusammen unter einem Kilobyte.
- *`showDocumentList` hat ein viertes Argument* (ein Link unter dem Satz, „Alle Zahlen zu diesem
  Begriff" auf `details.html#suche=…`), und `indizes` und `satz` dürfen Funktionen der Datei sein; so
  geht `showDocuments` darauf zurück, und die Liste wird an einer Stelle gezeichnet.
- *Adresse des Gremiums*: `#gremium=OVA` für ein Gremium, `#gremium=art:bezirksvertretung` für eine
  Art.
- *Größe der Kreise*: Radius 2,5 + 1,2 · √n Pixel; auf einer Karte unter 800 Pixeln Breite bis auf die
  Hälfte kleiner, und die Namen stehen dort erst im Ausschnitt eines Stadtbezirks.
- *Reihenfolge der Seite*: Kopf, Kurzfassung, Karte, Linkblock mit der englischen Kurzfassung, Fuß;
  die englische steht hinter der Karte, damit die Karte bei 1 280 Pixeln in der ersten Bildschirmhöhe
  beginnt. Die Karte ist höchstens 82 % der Fensterhöhe hoch.
- *Schaltflächen der Orte* heißen `start-place`: auf `button.term` hört der Rahmen und öffnet die
  Dokumente eines Begriffs.

**Probeabruf.** Einmal, am 2026-11-27, `GEOREP_STREET_POINTS__FETCH=true georep fetch street_points`
für Düsseldorf (mit der Quelle der Stadtteile aus der Shell, bevor das Profil sie nannte): die
Gebäudereferenzen (90 258 596 Bytes) und die Stadtteilgrenzen (1 335 152 Bytes), beide mit den SHA-256
der Kopien der Messung unter `fremddaten/opendata/`; 84 193 Hausnummern der Gemeinde, 2 929 von 3 589
Paaren mit Punkt, 50 Stadtteile, 48 s. Mönchengladbach las dasselbe Archiv aus
`cache_root/startkarte/` ohne Netz: 65 412 Hausnummern, 1 871 von 2 225 Paaren. Lage der 3 146 Orte
mit Treffer in der Hauptperiode: 352 aus Wikidata, 2 368 am Medoid der Hausnummern, 426 auf den
Stimmbezirken des Straßenverzeichnisses, keiner nur auf der Fläche des Wahlbezirks; von den
Straßenorten liegen damit 84,8 % am Medoid (Messung: 84,9 %).

**Leistung** (headless Chrome über Port 8777 auf dem B-Bau, vierfache CPU-Drossel, Hauptperiode mit
3 146 Orten, 16 Zustände des Reglers vom ganzen Zeitraum über die Fenster von zwölf Monaten zurück;
Zeit bis nach dem nächsten gezeichneten Bild, ein leeres Bild 16,5 ms): Neuzeichnen in JavaScript
Median 14 ms, höchstens 41 ms; mit dem Bild Median 31 ms, höchstens 92 ms, bei 1 280 und bei 390
Pixeln gleich; Umschalten auf die Flächen 40 ms. Über 50 ms liegt nur der Sprung auf den ganzen
Zeitraum, bei dem alle 3 146 Kreise zugleich erscheinen. Canvas lohnt nicht (§ 4.3). Die erste
Fassung brauchte 1,2 s: `getBoundingClientRect` je Kreis erzwang nach jedem gesetzten Radius ein
neues Layout (`02b295c`).

**Tests.** `tests/unit/test_report_start.py`: jede Zahl der Kurzfassung gegen das Modell an der
Mini-Fixture, jeder Link trifft eine id auf `details.html`, kein Partei- oder Fraktionswort in
Kurzfassung und Karte und keine Partei auf der ganzen Seite, kein Wort „Ressort", `karte.json` passt zu
`dokumente.json` (je Dokument eine Zeile, Orte in der viewBox, kein Paar Name × Wahlbezirk doppelt),
die Choroplethe ohne Skript ist die Zählung aus `karte.json`, Kontrast der Kreise mindestens 3:1 gegen
`--surface` und die neutralen Flächen in beiden Modi, Budget der Startseite, Downloadzeile von
`karte.json`. `tests/unit/test_street_points.py` und `tests/property/test_street_points_props.py`
für Lesen, Medoid, Netzschritt, Paket und `bootstrap`; `test_data_packages.py` für die beiden Pakete
(keine Hausnummer, jeder Punkt auf dem 25-m-Raster). Kein Stadtwort im Code
(`test_report_city.py` läuft über die neuen Module und Vorlagen).

**A/B-Bau** aller fünf Profile wie `pages.yml` (`scripts/ab_bau.sh`, `POLARS_MAX_THREADS=4
OMP_NUM_THREADS=2`), A aus `main` `8784b82` (`v0.39.0`, `ab/st2-a`), B aus `9c715fb` (`ab/st2-b`;
danach nur der Satz zur fehlenden Kartendatei und Doku). Unter `site/` 324 und 328 Dateien, 24
Abweichungen, alle erwartet: neu die vier `data/karte.json`; anders die vier Startseiten, die vier
`details.html` (Downloadzeile von `karte.json` und die Zeile über der Tabelle, `showDocumentList` im
Rahmen, die Kommentare zu `details.html#…`) und je Stadt und Periode `akteure.html`,
`vorgaenge.html`, `zeit.html` (`showDocumentList` im Rahmen, „Details" und „Startseite" statt
„Hauptseite"). `karte.html`, `vergleich.html` und jede andere Datei unter `data/` sind gleich. Über die
Datenwurzeln 1 170 und 1 191 Dateien: neu die Kopien der Pakete unter `external/startkarte/` und die
`karte.json`, anders 135 Stamps und 50 Seiten; kein Parquet unter `processed/` oder `interim/` anders.

| | `index.html` vorher → nachher | gzip | `details.html` vorher → nachher | `karte.json` | gzip |
|---|---|---|---|---|---|
| Hauptperiode | 15 848 → 92 713 | 29 449 | 966 597 → 968 010 | 382 585 | 113 175 |
| `2014-2020/` | 15 661 → 92 303 | 29 337 | 841 814 → 843 227 | 448 872 | 127 884 |
| `2025/` | 15 730 → 92 111 | 29 288 | 737 719 → 739 131 | 123 803 | 39 212 |
| `moenchengladbach/` | 15 649 → 87 101 | 28 199 | 825 194 → 826 601 | 45 067 | 14 711 |

Alle Startseiten unter dem Ziel von 120 000 Byte, jede `karte.json` unter 500 000. Die Pakete wachsen
um 59 554 Bytes.

**Bewusst nicht in B.** E1 bis E5 und S.10 (Plan § 9, § 10); `karte.html` bleibt bis zu Frage S.4
unverändert. Die Orte sind über die Tastatur nur über „Als Liste" und die Flächen der Wahlbezirke
erreichbar, nicht einzeln. Die Grenze der Stadtbezirke in einem geteilten Wahlbezirk (oben).

## 94. Das Spaltenschema auf `spalten.html`: je Tabelle ein Abschnitt mit ihrem Namen als Anker, auf keiner anderen Seite (Punkt 36, 2026-11-27)

`docs/todo.md`, Punkt 36, Phase „Zeigen“ (`docs/plan-zeigen-2026-11.md`). `details.html` wog in der
Hauptperiode 968 010 Byte (hart 1 000 000; Ziel der Phase höchstens 30 000 über den 937 528 vor
`v0.33.0`). Der Abschnitt `downloads` war 78 843 Byte groß, davon 50 990 die Liste „Spaltenschema“: je
Tabelle ein `<details>` mit Spalte, Typ, Bedeutung und Einheit. Jede Tabelle eines neuen Vorhabens
wuchs dort mit (15, 11/12, 17 und 14 je rund 3 bis 6 KB), als Nächstes 22 mit zwei. Die Regel gilt
für das ganze Register, nicht für einzelne Tabellen. Gebaut auf `feat/36-spalten` ab `main`
`a8e4d42` (`v0.40.0`). Die Nummer bekommt der Eintrag beim Merge.

**Was gebaut ist.**

- *`spalten.html` je Profil*, geschrieben vom Schritt `report` neben `details.html` und `karte.html`
  (`render.render_columns`, `templates/spalten.html.j2`), keine Beitragsseite und darum kein Schritt
  `page_*`. Je Tabelle ein `<section id="<tabelle>">` mit dem Namen als Überschrift, einer Zeile mit
  Beschreibung und Dateien der Tabelle (aus `model.downloads`) und der Tabelle Spalte, Typ, Bedeutung,
  Einheit aus `model.columns`, also aus denselben Zeilen, die `write_schema` nach `schema.json`
  schreibt, in derselben Folge; darüber ein Verzeichnis der Tabellen. Kopf mit „Zur Startseite“ und
  „Details: Downloads“ (`details.html#downloads`) und dem Link auf `schema.json`, Fuß wie die
  Unterseiten: `frame/page_footer.html.j2`, aus `page.html.j2` herausgezogen (eine Probeseite war mit
  alter und neuer Rahmenvorlage bytegleich, der A/B-Bau zeigt es an allen Unterseiten). Der Stil des
  Rahmens, kein Skript, kein Dialog. Nachbedingungen: jeder Anker genau einmal (`anchors_once`), nach
  außen nur Repository und Lizenzen (`COLUMNS_ALLOWED_LINKS`).
- *`details.html`*: jede Downloadzeile einer Tabelle, Parquet, CSV und `wahlbezirke.geojson`, trägt
  hinter der Beschreibung „· Spalten“ mit Link auf `spalten.html#<tabelle>` (`Download.table`, gesetzt
  in `write_tables` und beim GeoJSON); die JSON-Dateien tragen ihre Felder selbst und keinen. An der
  Stelle der Überschrift „Spaltenschema“ steht ein Satz mit Link auf `spalten.html` und auf
  `data/schema.json`. Die Abschnittsvorlage bekommt die Liste `tables` nicht mehr.
- *Budget*: `report.columns_budget_bytes = 500000`; `publish` prüft es je Datei (`page_budgets`), und
  die Meldung von `--strict-budget` nennt es. Wie bei `karte.json` prüft nur `publish` die eigene Grenze;
  `SiteSummary` zählt die Seite unter Dateien und Bytes mit.
- `spalten` ist als Seitenname reserviert (`pages.RESERVED`); `spalten.html` ist die fünfte Ausgabe von
  `report`, der Stamp hängt weiter an der Startseite. `write_neighbours` bleibt bei `index.html` und
  `details.html`: `spalten.html` trägt wie `karte.html` keine Zeile „Weitere Städte“.

**Entscheidungen.**

- *Der Anker ist der Tabellenname, ohne Präfix.* Die Seite hat sonst keine id (das Verzeichnis trägt
  keine, Dialog und Tooltip fehlen), eine Kollision entsteht also erst, wenn jemand eine id hinzufügt,
  die wie eine Tabelle heißt; dann bricht die Nachbedingung den Bau ab.
- *Offene Abschnitte statt `<details>`*: auf einer eigenen Seite ist nichts zu sparen, und ein Sprung
  auf `#<tabelle>` soll die Spalten zeigen, nicht einen Aufklapper.
- *Spaltennamen brechen nur hinter einem Unterstrich.* Der Rahmen setzt `code` auf
  `overflow-wrap: anywhere`; in den Aufklappern stand auf 390 px darum „wahlkr|eis_id“. Auf
  `spalten.html` steht hinter jedem Unterstrich ein `<wbr>` (beim Kopieren unsichtbar, rund 800 Byte in
  der Hauptperiode), und die Zelle des Namens bricht sonst nicht. Die Tabelle scrollt auf schmalen
  Schirmen weiter waagrecht wie jede breite Tabelle der Seiten: die längsten Wörter der Beschreibungen
  („Kommunalwahlbezirks“) und vier Spalten passen nicht in 358 px.
- *Die Prüfsätze bleiben unter den Downloads.* Sie sagen, wie eine Tabelle geprüft ist (`TableCheck`,
  Punkt 89), betreffen also den Download und keine einzelne Spalte. Hinweise, die eine Spalte erklären,
  gab es unter den Schemablöcken keine; das steht in den Beschreibungen selbst und wandert mit ihnen.
- *Der Link steht in der Zelle „Beschreibung“*, nicht in einer eigenen Spalte: die Tabelle behält
  ihre sechs Spalten, und eine Zeile ohne Tabelle bekommt keine leere Zelle.
- *Die Startseite bleibt unverändert.* Ihr Linkblock führt über „Downloads“ auf
  `details.html#downloads`, und dort verlinkt jede Zeile ihr Schema; keine Verbindung fällt weg.
- *Die Unterseiten* `akteure.html`, `vorgaenge.html` und `zeit.html` hatten keine eigenen
  Schemablöcke; ihre Tabellen standen im Schema von `details.html` und stehen jetzt auf `spalten.html`.
- Verworfen: das Schema nur in `schema.json` (ohne Werkzeug sähe niemand mehr die Bedeutung einer
  Spalte); eine Seite je Tabelle (rund 30 Dateien mit je Kopf und Stil); das Schema per Skript in die
  Downloads nachladen (aus `file://` leer, und die Zahl der Abschnitte bliebe an der Seite hängen).

**Tests.** `tests/unit/test_report_columns.py`: keine Seite der Mini-Fixture außer `spalten.html`
(Startseite, Auswertung, Karte, jede Unterseite des Profils) trägt eine Tabelle, deren Kopf „Spalte“ und
„Typ“ nennt, `spalten.html` genau eine je Tabelle; jede Tabelle des Registers hat ihren Anker genau
einmal, die Abschnitte stehen in der Folge von `schema.json` und tragen dessen Zeilen; jede
Downloadzeile einer Tabelle verlinkt genau ihren Abschnitt, die übrigen keinen, jeder Link trifft einen
Anker, und der Satz nennt Seite und `schema.json`; Kopf und Fuß wie die Unterseiten; das Budget;
Escaping; die Nachbedingung allein. `test_report_render.py` liest die Spalten auf `spalten.html`,
`test_report_pages.py` den reservierten Namen, `test_report_downloads.py` den Prüfsatz unter den
Downloads und nicht auf `spalten.html` (am Lauf mit Rohtext, wo `dokumente_kopf` und `kennungen`
erscheinen) und `spalten.html` in der Suche nach Namen, `test_report_actors.py` das Wort „symbol“
auch dort, `test_cli.py` die Grenze in der Meldung. Golden: `test_publish.py` je Stadt die Seite ohne
Städtezeile und ihr eigenes Budget; slow `test_published_page.py` an der vollen Referenz über alles,
was `publish` ablegt, und die Seite unter 500 000 Byte. Rot vor der Änderung (die Quellen gestasht):
Exit 1, acht Tests und zwei Module beim Sammeln (Liste im Commit).

**A/B-Bau** aller fünf Profile wie `pages.yml` (`scripts/ab_bau.sh`, `POLARS_MAX_THREADS=4
OMP_NUM_THREADS=2`), A aus `main` `a8e4d42` (`v0.40.0`, `ab/36-a`), B aus `8a5726d` (`ab/36-b`; der
Doku-Commit danach ändert keine Seite). Unter `site/` 328 Dateien in A, 332 in B, acht Abweichungen,
alle erwartet: neu die vier `spalten.html`, anders die vier `details.html`. Je `details.html` fehlen
Überschrift und Aufklapper des Spaltenschemas (36, 30, 27 und 28 Tabellen, so viele wie in
`schema.json`), 70, 59, 53 und 55 Downloadzeilen tragen den Link, dazu der Satz; sonst gleich bis auf
Zeitstempel und Prüfsummen. Gleich sind die Startseiten, `karte.html`, `akteure.html`,
`vorgaenge.html`, `zeit.html` (also auch der herausgezogene Fuß), `vergleich.html` und jede Datei unter
`data/`; `schema.json` bis auf `generated_at`. Über die Datenwurzeln 1 191 und 1 201 Dateien: neu die
zehn `spalten.html`, anders die zehn `details.html` und 135 Stamps (Schreibzeit); kein Parquet, kein
JSON anders. `georep publish --strict-budget` lief in beiden Bauten durch.

| | `details.html` A → B | gzip A → B | `spalten.html` | gzip |
|---|---|---|---|---|
| Hauptperiode | 968 010 → 921 158 (−46 852) | 205 493 → 198 055 | 77 302 | 15 581 |
| `2014-2020/` | 843 227 → 810 574 (−32 653) | 184 512 → 179 630 | 60 234 | 12 592 |
| `2025/` | 739 131 → 708 924 (−30 207) | 158 740 → 154 182 | 56 594 | 12 055 |
| `moenchengladbach/` | 826 601 → 796 047 (−30 554) | 160 174 → 155 554 | 57 194 | 12 103 |

`details.html` der Hauptperiode liegt damit 16 370 Byte unter dem Bau vor `v0.33.0` (937 528) und
78 842 unter der harten Grenze. `spalten.html` ist größer als die entfernten Blöcke (50 990 Byte in der
Hauptperiode), weil sie den Stil des Rahmens (rund 12 KB), das Verzeichnis und je Tabelle Überschrift
und Dateizeile trägt; bis zur Grenze von 500 000 Byte bleiben rund 420 000.

**Geprüft im Browser** (headless Chrome über Port 8778 auf dem B-Bau, je 390 und 1 280 px):
`spalten.html` (Kopf, Verzeichnis, erste Tabelle, die Tabelle der Kontrollvariablen mit den längsten
Namen) und der Abschnitt Downloads von `details.html`.

**Nicht in diesem Punkt.** Auf 390 px ist die Download-Tabelle von `details.html` je Zeile rund 350 px
hoch, in A genauso; vermutlich drückt die Spalte SHA-256 (`code`, `overflow-wrap: anywhere`) die
Beschreibung zusammen, untersucht ist es nicht. Der Linkblock der Startseite nennt bei „Downloads“ weiter „mit
Prüfsummen und Spaltenschema“; das Schema ist von dort einen Link weiter.

## 95. Die Unterseite `bedarf.html`: die Klasse an Dokumenten ohne Ausschussberatung geprüft, ohne verlässliches Maß; der Stadtbezirk als Mittelpunkt statt als Farbe (Vorhaben 22, Stufe 3, 2026-11-27)

Stufe 3 von Vorhaben 22 nach `docs/plans/22-bedarf.md`, § 7 mit § 10, und `docs/plan-zeigen-2026-11.md`
(§ 5, Zeile zu 22; § 4, V5). Gebaut auf `feat/22-bedarf-seite` ab `main` `a8e4d42` (`v0.40.0`). Die
Nummer bekommt der Eintrag beim Merge.

**Die Prüfung der Klasse kam zuerst** (Frage 22.3: für Stufe 3 ja). H1 zählt im Anteil „Ordnung und
Verkehr" 1 425 Dokumente mit Treffer, und 958 davon (67,2 %) wurden in keinem Ausschuss beraten; an
solchen ist der Ausschussklassifikator (Punkt 45) nie geprüft worden. Der Supervisor legte die
Prüfung am 2026-11-27 fest, der Bau-Agent schrieb sie vor der Stichprobe als § 4.1 ins
Messdokument, mit Codebuch (Fassung 2026-11-27.1, Grenzfälle eingeschlossen) und Messskript
(`docs/plans/22-bedarf-ova.py`), in einem Commit: 100 der 958, geschichtet nach Gremium, Seed
20261127; Kodierer A und Schlichtung `claude-opus-5-5`, B `claude-sonnet-5-5` (Frage 19); der
Bau-Agent kodierte nicht. Ergebnis: einig bei 99 von 100, A einmal `nein`, B nie; κ 0,000,
Krippendorffs α 0,000; die eine Uneinigkeit (Lärmschutzwände einer Bahnstrecke) entschied die
Schlichtung als `nein`. Endlabels `ja` 99, `nein` 1. α genügt nicht, und die Regel der vollen
Einigkeit (`validierung.md`, § 3, Schritt 8) greift nicht. Es gilt darum der vorab festgelegte Fall 3:
die Seite nennt keine geprüfte Präzision, sondern den Satz, was beobachtet wurde, und dass α bei fast
keiner Streuung kein verlässliches Maß ist. α ist hier nicht klein, weil die Kodierer oft verschieden
urteilten, sondern weil fast alle Labels gleich sind; die Regel bleibt trotzdem, wie sie festgelegt
war, und was daraus für künftige Messungen folgt, steht im Rückstand (Supervisor). Die Unschärfen,
die der Schlichter nennt, stehen als „Fassung 2" in § 4.1; das Codebuch bleibt.

**Was gebaut ist.** Der Beitrag `22-bedarf` trägt außer den Schritten die Seite und zwei Tabellen
bei, alle hinter `need_enabled` (`context.need.enabled`):

- `bedarf.html` (`report/need.py`, `templates/pages/bedarf.html.j2`, `.css`) mit den vier Abschnitten
  aus § 7 und dem Kasten „Wie geprüft" (Summen, scharf gegen unscharf, Handlungsbedarf gegen
  Schulsozialindex aus den Tabellen; die Klasse aus `guete.json`).
- Die Downloads `wahlbezirke_bedarf` und, wo das Profil Hypothesen oder Paare nennt,
  `bedarf_hypothesen` (Parquet und CSV, die Liste `ohne` mit „; "), mit Spaltendoku.
- V5: `NeedAttribution.modified`, der Veränderungshinweis, den dl-de/by-2-0 im Quellenvermerk
  verlangt; die drei Quellen in `defaults.toml` sagen, was verändert ist, der Quartiersatlas auf der
  Seite „auf Wahlbezirke umgerechnet". `NeedHypothesis.fixed_on` trägt den Tag der Festlegung
  (2026-11-23) neben dem Commit. Beide sind Anzeige und stehen nicht im Fingerprint (die Fingerprints
  der Hauptperiode und des Vergleichsprofils sind unverändert), aber im Zusatz von `report` und den
  Unterseiten (`report_fingerprint`, Punkt 53): sonst bliebe die Seite nach einer geänderten
  Namensnennung aktuell.

**Je Profil** (Plan § 6): in der Hauptperiode (und im Vergleichsprofil, das in ihrem Ordner rechnet)
alles; in Mönchengladbach Bedarf ohne Klassen: keine Fremddaten zur sozialen Lage, also die Karte des
Schulsozialindex statt des Handlungsbedarfs, keine Anteile der Klassen, keine Tests, und die Seite
sagt in drei Sätzen, was fehlt. Die Perioden 2014–2020 und ab 2025 schalten `context.need` ab
(Fragen 22.5 und 22.10) und haben die Seite nicht.

**Bewusst anders als § 7.**

1. *Der Stadtbezirk als Mittelpunkt, nicht als Farbe.* Zehn Stadtbezirke sind zehn Kategorien; ein
   Streudiagramm trägt nach der Skill `dataviz` höchstens drei unterscheidbare Farben (alle Paare
   liegen nebeneinander), und eine zehnte Farbe wäre Rauschen. Jeder Stadtbezirk trägt darum seine
   Nummer im Mittelpunkt seiner Wahlbezirke, und dünne Linien führen zu ihnen: steigen die
   Mittelpunkte, ohne dass die Linien um einen Mittelpunkt eine Richtung zeigen, liegt der
   Zusammenhang zwischen den Stadtbezirken (H1); umgekehrt bei H3.
2. *Die Sätze zu „innerhalb" und Moran's I entstehen aus den Zahlen*, nicht aus einem festen Text:
   „besteht zwischen den Stadtbezirken, nicht innerhalb", wenn der Test bestätigt ist und die
   Rechnung innerhalb p ≥ 0,05 hat; „zeigt sich innerhalb", wenn er nicht bestätigt ist und sie
   p < 0,05 hat; der Satz zur räumlichen Abhängigkeit, wenn Moran's I der Residuen p < 0,05 hat. Für
   H1 sagt das genau den Satz aus § 7.
3. *Keine Lesart je Paar.* Das Messdokument deutet jedes explorative Paar in einer Spalte; die Seite
   zeigt ρ, p und n und den Satz, dass jedes Paar eine Frage für eine neue Festlegung ist.
4. *Die Gegenprobe der Einwohner* (Zensus gegen Quartiersatlas, r 0,947) und die Prüfsummen stehen
   nicht als Zahl auf der Seite: sie rechnet nur das Messskript aus den Fremddaten. Die Seite nennt
   die Gegenproben, die sich aus den Tabellen nachrechnen lassen, und verweist für die übrigen auf
   § 4.
5. *Die Genauigkeit des Klassifikators an Ausschussdokumenten* (0,941, Kreuzvalidierung 2026-10,
   Punkt 45) steht als Konstante `CLASS_CHECK_ACCURACY` in `report/need.py`; sie ist eine Messung
   der Hauptperiode und keine Einstellung einer Stadt.

**Verworfen.** Eine Farbe je Stadtbezirk (oben); die Präzision 0,990 mit Intervall trotz α unter der
Schwelle (Fall 3 ist vorab festgelegt); die Klassen „Ordnung und Verkehr" und „Jugend und Schule" als
Anzeigenamen in den Settings (sie hängen an den Klassen des Ausschussklassifikators, Frage 22.11,
und stehen als Konstanten in `report/need.py`); eine Teilvorlage `pages/bedarf/klasse.html.j2` für
den Satz zur Prüfung (`check_page_files` hielte sie für einen Gast ohne Eintrag; sie ist ein Makro in
der Vorlage).

**Geprüft.** Tests in `tests/unit/test_report_need.py` (Bausteine, die Prüfung im Repo als Fall 3,
die drei Fälle an geänderten Kopien von `guete.json`, die echte Seite der Mini-Fixture mit
Linkblöcken, Namensnennung und Veränderungshinweis, Tag und Commit, Downloads mit Spaltendoku, ohne
Fremddaten, Klassen und Hypothesen, Eingaben des Schritts, der Zusatz im Stamp) und
`tests/unit/test_need_settings.py` (V5, `fixed_on`); slow `tests/golden/test_need_page.py` an den
Paketen (Hauptperiode: 958 von rund 1 425, Fall 3, drei Tests, drei Karten, 11 501 Unfälle, Spearman
0,980, ρ 0,772, Power 0,39 und 0,46; die zweite Stadt ohne Klassen und Tests, zwei Karten, drei Sätze;
beide unter 500 KB). Seit Punkt 94 stehen beide Tabellen auf `spalten.html`, jede Downloadzeile
verlinkt ihren Abschnitt, und die Seite verweist auf `spalten.html#wahlbezirke_bedarf`.

- A/B-Bau aller fünf Profile wie `pages.yml` (`scripts/ab_bau.sh`, `POLARS_MAX_THREADS=4
  OMP_NUM_THREADS=2`), A aus `main` `e50762c` (`v0.41.0`, `ab/22s-a`), B aus `9643fb7` (`ab/22s-b`;
  danach kamen nur dieser Eintrag und `main` `3b0c486`, das `enrich/fidelity.py` von Vorhaben 20
  ändert, dessen Schritt überall aus ist). Unter `site/` 332 Dateien in A, 340 in B, 16 Abweichungen,
  alle erwartet: neu `bedarf.html` und die Downloads (Hauptperiode vier, Mönchengladbach zwei, ohne
  `bedarf_hypothesen`), anders je Stadtseite `index.html` (der Linkblock, +213 Byte), `details.html`
  (Linkblock, die Zahl der Downloadzeilen, die neuen Zeilen mit Link auf `spalten.html`, die Größe von
  `schema.json`; sonst nur Prüfsummen von `dokumente.json`, `vorgaenge.json`, `begriffe.json`,
  `karte.json` und `summary.json`, die an `generated_at` hängen), `spalten.html` (die zwei
  beziehungsweise eine neue Tabelle) und `schema.json`. Die Perioden 2014–2020 und ab 2025 und
  `vergleich.html` sind gleich. Über die Datenwurzeln 1 201 und 1 219 Dateien, 169 Abweichungen: neben
  denselben Seiten und Downloads in den Ordnern der Profile nur Stamps, kein Parquet unter
  `processed/` oder `interim/` (keine Zahl der Auswertung ändert sich). Von den 137 Stamps tragen 109
  nur eine andere Schreibzeit, 18 den neuen Zusatz (`report_fingerprint`) der Unterseiten
  `akteure.html`, `vorgaenge.html` und `zeit.html`, 4 dazu nur die Wurzel der absoluten Pfade (die
  Startseiten der Perioden), 2 nur die Wurzel (`wahlbezirke_vergleich`, `zeit_hypothesen`), 2 sind
  neu (`bedarf.html`), und die Startseiten der Hauptperiode und Mönchengladbachs lesen die zwei
  Tabellen als Eingaben.
- Größen (veröffentlicht, B): `bedarf.html` Hauptperiode 242 267 Byte, Mönchengladbach 133 866
  (Budget 500 000; geplant 150 bis 250 KB: drei Karten zu je rund 36 KB, drei Streudiagramme zu je
  rund 17 KB, die Tabelle je Wahlbezirk rund 33 KB). `details.html` Hauptperiode 921 158 → 923 125
  (+1 967), Mönchengladbach 796 047 → 797 144 (+1 097), nur Linkblock und Downloadzeilen; `index.html`
  je +213;
  `spalten.html` 77 302 → 85 247 und 57 194 → 61 890; `schema.json` 56 870 → 65 598 und
  36 974 → 42 100.
- Bildschirmfotos mit headless Chrome über `http://127.0.0.1:8779` (eine Kopie der Seite von B) bei
  1280 und 390 Pixeln, hell, dunkel (`--blink-settings=preferredColorScheme=0`) und ohne Skripte (eine
  Kopie ohne `<script>`, `<noscript>` ausgepackt): die Karten stehen bei 1280 nebeneinander, bei 390
  untereinander; ohne Skripte steht die ganze Tabelle da, mit Skripten die Vorschau; dunkel tragen
  Karten, Streudiagramme und der Kasten die Farben des Rahmens. Bei 1280 brach der Name des
  Wahlbezirks in drei bis vier Zeilen; eine Mindestbreite der Spalte hält ihn bei zwei.
