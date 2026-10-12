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
`tests/unit/test_dependency_boundary.py` hält die Grenze per Quelltextsuche. Verworfen: TF-IDF und NMF selbst
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
Verworfen: der Vergleich als „optionale Eingabe" von `report` (das Schrittregister kennt keine). Verglichen
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
