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
Hauptseite von den Texten der Arbeit; `bartzsch-exakt` bleibt der Anker (`docs/todo.md`, Punkt 8).

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

## NN. Einbettungen über Stücke, ähnliche Dokumente als Paket, Suche mit der Einbettung als Vorgabe (Vorhaben 18, 2026-11-24)

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
