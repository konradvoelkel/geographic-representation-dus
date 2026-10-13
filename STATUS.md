# Status

Stand 2026-10-13, `main` auf `v0.11.0` plus die beiden Methodikregeln aus `docs/todo.md`, Punkt 4,
das tragfähige Themenmodell aus Punkt 1, die Skalierung der Kennzahlen aus Punkt 3, die
Literaturübersicht aus Punkt 5 und die Vorschau langer Tabellen aus Punkt 2 (nicht
getaggt; `bartzsch-exakt` zeigt auf den letzten exakt reproduzierenden Stand). Der Umbau in sieben Phasen ist abgeschlossen
(`docs/development-plan-2026-10.md`), die Berichtsseite ist gebaut und veröffentlicht (`docs/plan-report-2026-10.md`,
Stufen A bis G, Seite unter <https://konradvoelkel.github.io/geographic-representation-dus/>), und der Ausbau in
acht Optionen ist gemerged (`docs/plan-ausbau-2026-10.md`, Pläne und Abnahmen unter `docs/plans/`). Aufbau in
`docs/architecture.md`, Gründe in `docs/decisions.md`. Fakten mit Datum, Invarianten ohne.

## Abgeschlossen

- Phase 0 (`v0.1.0`): uv-Projekt auf Python 3.14, Charakterisierungstests, nox, pre-commit, CI, mechanische Ruff-Commits.
- Phase 1 (`v0.2.0`): atomare Schreibvorgänge, Session mit Timeout und Retry, Fehlerisolation im Download, Guards, deterministische Ausgaben, Domänenfehler.
- Phase 2 (`v0.3.0`): Settings in TOML, OParl 1.1 als Vertrag, Layout mit Schreibschutz auf `reference/`, Polars-Kette mit Parquet, Schrittregister mit Stamps, CLI `georep`.
- Phase 3 (`v0.4.0`): Fetch- und Cache-Schicht ohne geopandas und osmnx; der Code der Arbeit ist vollständig ersetzt.
- Phase 4 (`v0.5.0`): Tests ausgebaut. `tests/property/` mit hypothesis: ein lesbares Orakel des Matcher-Vertrags, Invarianten für Wörterbuch, Aggregation, POI-Bereinigung, Straßen, Treffer, Index, STRtree, OParl-Roundtrip, Stores und `deep_merge`. Snapshot für `georep steps`, nox `test` parallel mit Abdeckung als Untergrenze (90 %).
- Phase 5 (`v0.6.0`): Profiling-Infrastruktur. `georep profile`, `nox -s bench` (pytest-benchmark, rot ab 20 % langsamer im Minimum), Protokoll `PdfTextExtractor`. Messung in `docs/profiling/README.md`: Offline-Lauf 6,3 s, davon 4,1 s FlashText; Extraktion 38 ms je PDF; pypdf 6.20.0 reproduziert 197 von 200 Texten der Arbeit zeichengleich. Empfehlung: pypdf und FlashText bleiben, kein Rust-Port.
- Phase 6 (`v0.7.0`): Design by Contract. 80 deal-Decorators an 30 Funktionen in `search`, `analysis`, `prep`, `geo`, `layout`, `stores`, `http`, `settings` und `sources`; Prädikate in `georep.contracts`; `settings.contracts = "off"` schaltet ab, Overhead unter einem Prozent. Fetcher werfen nur `FetchError` oder `NetworkError`, die CLI meldet einen abgebrochenen Abruf als eine Zeile. `deal.cases` greift zehn reine Funktionen an, `nox -s verify` (crosshair) fand und `nox -s mutate` (pytest-gremlins, 79 % getötet) deckte je einen echten Fehler auf: `street_names` bei kaputter Overpass-Antwort und deals nicht reentranter `HasPatcher`, der nach `deep_merge` Socket und stdout gepatcht ließ. Beides behoben, `docs/mutation-2026-10-11.md`.
- Phase 7 (`v0.8.0`): Abschluss. README aus Sicht eines frischen Klons (geprüft am 2026-10-11 auf xtraspace: `uv sync --locked`, `bootstrap`, `run` in 6 s, `regress`, `nox`, slow-Test), `docs/architecture.md` und `docs/decisions.md` ersetzen den Plan, der archiviert ist; Code-Docstrings verweisen auf die lebenden Beschreibungen. Kein Pull Request an `lubar102` (Konrads Entscheidung, decisions.md Punkt 19).
- Berichtsseite (`v0.9.0`): Schritt `report` als neunter Offline-Schritt; `data/site/index.html` (400 KB, inline SVG und JavaScript, hell und dunkel, Deutsch mit englischer Kurzfassung) und `data/site/data/` mit den sechs Tabellen als Parquet und CSV, `wahlbezirke.geojson`, `schema.json`, je mit SHA-256 auf der Seite. Mini-Fixture mit GeoJSON, `report/` mit `model`, `geometry`, `charts`, `render`, `build`; Lizenzen des Open-Data-Portals am 2026-10-11 auf den Datensatzseiten nachgesehen. Geprüft in Hell und Dunkel mit headless Chrome.
- Stufe G (`v0.10.0`): Dokumente je Begriff als nachgeladener Dialog aus `dokumente.json`, Orte mit Namen auf der Karte, `karte.html` mit Leaflet (gepinnt) und OpenStreetMap-Kacheln als zweite Datei.
- Ausbau in acht Optionen (`v0.11.0`, 2026-10-12): ein Supervisor-Agent und je Option ein Unteragent auf
  `feat/NN-name` in eigenen Worktrees, Synergiephase mit Fundament F1 bis F7 (`docs/plans/00-synergien.md`:
  Abschnittsmechanismus der Seite, Register der Tabellen, `regression_pair`, Profil und offene Periode,
  Crosswalk-Kern, Achsen-Helfer, Zähl-Tests), Review je Branch (Opus, Stufe high) und Merge mit `--no-ff` in
  der Reihenfolge 08, 05, 06, 03, 04, 02, 01, 07. Fragen an Konrad gebündelt in `docs/plans/fragen.md`; die
  Agenten haben nichts abgerufen, alle Netzläufe sind Konrads (siehe „Nächster Schritt").
  - Option 08 Suche (`docs/plans/08-suche.md`): Abschnitt „Straße oder Ort suchen" mit Vorschlagsliste nach
    dem APG-Combobox-Muster aus 4176 Einträgen (Straßen, Orte, Wahlbezirksnamen) in der Seite, Ergebnisblock,
    Markierung in Karte, Tabelle und Streudiagramm, teilbar als `#suche=…`.
  - Option 05 Gremien (`docs/plans/05-gremien.md`): Gremium je Dokument aus der Drucksachennummer (auf der
    Referenz 0 von 19 108 unbekannt), Schritte `bodies` und `body_hits`, Abschnitt „Gremien", dritter
    Kartenumschalter „Anteil eigene Bezirksvertretung", Stadtbezirk je Wahlbezirk über die Wahlberechtigten.
  - Option 06 Gewichtung (`docs/plans/06-gewichtung.md`): Themenmodell mit TF-IDF und NMF (scikit-learn, 20
    Themen), gewichtete Trefferquoten je Begriff, Dokumentart und Thema, Abschnitt „Was ändert die
    Gewichtung?" mit Tabelle 5 unter 26 Gewichtungen; Einheitsgewichte reproduzieren die Arbeit exakt.
  - Option 03 Kontrollvariablen (`docs/plans/03-kontrollvariablen.md`): Quartiersatlas 2024 unter `context/`
    (dl-de/by-2-0, Prüfsummen), Umrechnung über Flächenanteile und Wahlberechtigte, OLS in
    `analysis/ols.py` (gegen statsmodels geprüft), Tabelle 6 und 6b, Added-Variable-Plots, Abschnitt
    „Abgeleitete Daten". Befund: R² 0,89 statt 0,03, die Trefferquote erklärt nichts mehr für sich.
  - Option 04 Parteien (`docs/plans/04-parteien.md`): Urheber je Dokument aus Dokumentart, Titel und
    Textkopf (der OParl-Server füllt die Felder nicht), Parteien bei Fraktionen, Schritt `parties` und
    Netzschritt `organizations`, Abschnitt „Urheber und Parteien" mit sechs kleinen Karten und dem Abgleich
    gegen den Stimmenanteil (Pearson r, Bonferroni-Hinweis).
  - Option 02 Zeitreihe (`docs/plans/02-zeitreihe.md`): eine Wahlperiode ist ein Profil
    (`duesseldorf-2014`, Daten unter `data/2014-2020/`), Wahlzahlen von 2020 über Flächenanteile
    summentreu auf die Wahlbezirke von 2025 umgerechnet (`precincts`, `largest_remainder`), Schritt
    `compare` und Abschnitt „Zwei Wahlperioden" (`duesseldorf-vergleich`). Offline an der Mini-Periode
    `tests/fixtures/mini-2014/` geprüft; der Abruf der alten Periode ist Konrads Lauf.
  - Option 01 Städte (`docs/plans/01-staedte.md`): jede Kommune ist ein Paketprofil
    (`src/georep/profiles/<slug>.toml`, `--profile`, `GEOREP_PROFILE`, `base`), `defaults.toml` ist
    stadtneutral und im Code steht kein Stadtwort (grep-Test). Schritt `shapes` (GeoJSON oder Shapefile-Zip
    über pyshp), `summary.json` je Stadt, `georep publish` mit `vergleich.html`; Profil Mönchengladbach mit
    Netzstichprobe als Fixture, Runbook `docs/runbook-stadt.md`. Düsseldorf rechnet unverändert.
  - Option 07 Monitoring (`docs/plans/07-monitoring.md`): Profil `duesseldorf-2025` für die laufende
    Periode (offenes Ende, Wörterbuch der Hauptperiode, 19 Schritte), inkrementeller Abruf mit
    `modified_since` und Löschungen, Schritt `timeline`, Abschnitte „Je Monat" und „Laufende Wahlperiode",
    `georep paths`, Betrieb unter `deploy/` (Lauf-Skript, systemd-Service und -Timer, Schnappschuss mit
    `SHA256SUMS`), Trockenlauf in einer transienten Nutzereinheit geprüft.

## Methodikregeln (2026-10-12, `docs/methodik-review-2026-10.md`)

Das Review zu `docs/todo.md`, Punkt 4, geht die Entscheidungen der Arbeit durch und setzt zwei Regeln um
(`docs/decisions.md`, Punkt 44). Beide stehen als Schalter in `defaults.toml`; mit `city_facilities = false`
rechnet die Kette wie die Arbeit, und genau so messen die Golden-Master-Tests
(`as_in_the_thesis(...)` in `tests/conftest.py`).

- **Regel 1, Einrichtung mit Stadtnamen** (an): 113 der 1309 Ortslabels fallen aus dem Wörterbuch und von der
  Karte, davon 40 mit Treffern (Stadtwerke Düsseldorf 190 Dokumente, Hochschule 80, Flughafen 80, Messe 61,
  Stadtsparkasse 45, Feuerwehr 43). Begriffe 5841 → 5727, Treffer 29 573 → 29 010 (−1,9 %), 12 der 41
  Wahlbezirke ändern sich: Bezirk 10 −177 (−14,9 %), Bezirk 1 −133, Bezirk 23 −91, Bezirk 6 −64, Bezirk 13
  −42. Tabelle 5 über alle 41: 79,9539 · x + 48,1709, r = 0,1891, R² = 0,0358, p = 0,23641 (vorher 62,1337 /
  49,1993 / 0,1612 / 0,0260 / 0,31385); ohne 1 und 10: 216,2416 · x + 40,5715, r = 0,3351, R² = 0,1123,
  p = 0,03705 (vorher 215,3341 / 40,5046 / 0,3385 / 0,1146 / 0,03507). Der Befund der Arbeit bleibt.
- **Ausreißer**: robust gemessen (Median 0,0604, MAD 0,0094) fällt Bezirk 10 von z = 4,04 auf 2,69 und ist
  kein Ausreißer mehr (zweithöchster: Bezirk 2 mit 2,58); Bezirk 1 bleibt bei z = 9,71, weil seine Quote von
  der Größe seines Wörterbuchs kommt (812 Begriffe gegen 147 im Median).
- **Regel 2, stadtweite Begriffe** (nur Anzeige): 55 Begriffe liegen über dem 99-%-Quantil der
  Dokumenthäufigkeit (64 Dokumente) und stehen im Abschnitt „Begriffe" mit Dokumentzahl und Wahlbezirk.
  `search.citywide_exclude` würde sie auch aus der Zählung nehmen und ist aus.
- **Die stärkste Verzerrung bleibt unbehandelt**: die Trefferzahl eines Wahlbezirks korreliert mit der Größe
  seines Wörterbuchs mit r = 0,767, mit seinen Wahlberechtigten nur mit r = 0,176. Empfehlung des Reviews
  (§ 2.6, offen): „Treffer je Begriff im Wörterbuch" als zweite Kennzahl, zusammen mit `docs/todo.md`,
  Punkt 3.

## Themenmodell (2026-10-12, `docs/themenmodell-2026-10.md`)

`docs/todo.md`, Punkt 1: die 20 Themen trugen nicht, weil Fraktions- und Personennamen sieben von
ihnen prägten. Alle vier Wege des TODO sind abgearbeitet und gemessen (Entscheidungen in
`docs/decisions.md`, Punkt 45; Nachrechnen mit `docs/themenmodell-2026-10-messung.py`):

- **Stoppwörter aus dem Profil und aus dem Korpus** (`topics.stop_sources`): Parteien, Fraktionen
  und Personenmarker aus `[originators]`, Gremienkürzel aus `[bodies]`, Personennamen daraus, dass
  ein Wort fast nur hinter einer Unterschrift oder einer Amtsbezeichnung steht (254 Wörter,
  insgesamt 627 statt 313). NPMI der Topwörter +0,4164 → +0,4208; die Partei- und Personenblöcke
  sind weg, Schule, Aufsichtsratsbesetzungen und Verfügungsmittel sind neue Themen. Ausnahmen im
  Profil (`topics.stop_keep`: „klima", „tierschutz", „bau" — auch ein Gremienkürzel kann mit einem
  Sachwort zusammenfallen, 2026-10-13).
- **Gesäte Themen je Ausschuss** (`topics.seed = "committees"`, 17 von 20 gesät): Log-Odds mit
  Dirichlet-Prior liefert die Saatwörter (nur solche, die der Ausschuss benutzt), die Wortmatrix
  bleibt fest. Treue 0,72 bis 1,00 (Median 0,83), Reinheit 0,15 bis 0,57; NPMI fällt auf +0,3349 —
  bezahlt für Namen statt Nummern.
- **Passender Ausschuss je Dokument** (Schritt `committees`, 6,5 s): Kreuzvalidierung 0,941
  Genauigkeit, 0,878 Makro-F1 über 20 Klassen. Konrads Frage ist mit Nein beantwortet: 10,9 % der
  Ausschussdokumente, aber 81,2 % der BV- und 87,4 % der Ratsdokumente bleiben unter der Schwelle
  von 0,4. Ein Teil der Güte hängt daran, dass der Volltext die Beratungsfolge und darin den Namen
  des Ausschusses trägt (ABA 100 %, OVA 91,7 %): ohne die 44 Wörter mit „ausschuss" sind es
  0,929 / 0,864, die Zahlen sind also eine Untergrenze (§ 4.3 des Dokuments).
- **Einbettungen**: nicht gebaut, mit Zahlen begründet (§ 5 des Dokuments).

Tabelle 5, die Treffer (29 010) und das Wörterbuch (5727) sind unberührt; nur die
`thema_NN`-Zeilen der Gewichtungstabelle tragen andere Zahlen.

## Skalierung der Kennzahlen (2026-10-13, `docs/skalierung-2026-10.md`)

`docs/todo.md`, Punkt 3: Konrad will nicht sehen, wo eine Partei viel über Wahlbezirke redet, sondern wie
viel mehr oder weniger als der Durchschnitt aller Parteien. Das Konzept nimmt alle 35 Kennzahlen der Seite
mit Zähler und Nenner auf; von ihnen tragen 16 schon einen Nenner und sechs sind Modellangaben, offen waren
genau die Treffer je Wahlbezirk und die Parteianteile (Entscheidungen in `docs/decisions.md`, Punkt 46).

- **Umschalter als ein Muster**: ein `fieldset.switcher` mit Radios (Makro `switcher`), die Varianten als
  `data-class-/data-text-/data-value-<variante>` an Flächen, Zellen und Köpfen, ein generisches Stück
  JavaScript im Rahmen, Legende `#legend-<variante>`; ohne JavaScript steht die Standardvariante da.
- **Parteien**: Anteil (Standard) / Abweichung vom Mittel aller Parteien in Prozentpunkten / Verhältnis zum
  Mittel, für die sechs Karten, die Spalte „im Mittel" und die Parteispalten. Konrads Frage in einer Zeile:
  AfD 0,89 % Anteil im Mittel, −1,49 pp, Verhältnis **0,32**; GRÜNE 3,57 %, +1,19 pp, **1,59**; CDU 1,33,
  SPD 1,21, FDP 0,97, Die Linke 0,57. Das Mittel ist ungewichtet; das gewichtete setzen GRÜNE, CDU und SPD
  fast allein (18 der 29 Vorzeichenwechsel treffen SPD und CDU), es ist gemessen und verworfen.
- **Wahlbezirke**: die Karte bietet zusätzlich Treffer absolut (17 der 41 Quantilklassen anders als bei der
  Quote), Treffer je Begriff im Wörterbuch (28 anders; Median 4,5656, Spannweite 2,2485 bis 9,5472) und die
  Abweichung vom Stadtmittel (ungewichtetes Mittel 0,061808; −57,8 % bis +144,8 %). Die Kennzahlspalte der
  Bezirkstabelle zeigt dieselbe Einfärbung als Zahl.
- **Zweite Regression** (die stärkste offene Empfehlung des Methodik-Reviews): mit x = Treffer je Begriff
  bleibt nichts, nicht einmal das Vorzeichen — alle 41 Bezirke −0,5570 · x + 55,7576, r = −0,1118,
  R² = 0,0125, p = 0,48644; ohne 1 und 10 −0,2400 · x + 54,4333, r = −0,0419, R² = 0,0018, p = 0,80000. Die
  einzige Spalte, in der die Arbeit ein signifikantes p berichtet, hängt an der Größe der Wörterbücher.
- **Divergierend heißt feste Grenzen**, keine Quantile (`[report.diverging]`): ±10 % und ±25 % vom
  Stadtmittel, ±0,5 und ±2 Prozentpunkte, 0,5 / 0,8 / 1,25 / 2,0 beim Verhältnis.
- Nicht gebaut, je mit Grund in § 5 des Konzepts: „je 1000 Wahlberechtigte" als eigenes Radio (es *ist* der
  Standard mit einem Faktor), das Verhältnis zum Stadtmittel, je Einwohner, je Fläche, das Log-Verhältnis
  (20 Parteizellen sind exakt 0) und Umschalter in den Abschnitten Gremien, Monate, Gewichtung,
  Kontrollvariablen und Begriffe.
- Tabelle 5, die Treffer (29 010) und das Wörterbuch (5727) sind unberührt, und die Standardansicht der
  Seite ist dieselbe wie vorher.

## Literaturübersicht (2026-10-13, `docs/decisions.md`, Punkt 47)

`docs/todo.md`, Punkt 5: die Seite trägt zwischen „Abgeleitete Daten" und „Downloads" den Abschnitt
„Literatur und verwandte Arbeiten" (`#literatur`, Abschnittsnummer 67) mit fünfzehn Einträgen, je mit
vollständiger Zitation und einem oder zwei Sätzen zum Beitrag. Dieselbe Liste steht im README unter
„Literatur"; `tests/unit/test_report_literature.py` vergleicht beide Feld für Feld.

- **Daten, nicht Vorlage**: `src/georep/report/literatur.toml` im Paket trägt die dreizehn stadtneutralen
  Einträge, `[[report.literature]]` im Profil die zwei stadtspezifischen; `report/literature.py` stellt die
  des Profils voran. `deep_merge` ersetzt Listen, darum steht die allgemeine Liste nicht in `defaults.toml` —
  sonst könnte ein Profil sie nur überschreiben. Mönchengladbach erbt heute alle dreizehn.
- **Belegt**: alle Links am 2026-10-13 mit Statuscode geprüft, alle DOI über Crossref aufgelöst. Neu und
  vorher nicht genannt ist die methodisch nächste Forschung: Harmening u. a. 2025 (EJPR, zwölf deutsche
  Großstädte, dasselbe Wörterbuchverfahren), Nyhuis u. a. 2025 (die Wörterbuchfrage selbst), Zittel u. a.
  2019 (der Ursprung des Ansatzes), Cherif 2026 (offenes OParl-Volltextkorpus).
- **Zwei Lücken stehen sichtbar da** (`pending = true`): der **Titel der Arbeit** ist unbekannt und das Feld
  darum leer — ihr Repositorium hat keine Beschreibung, sein README nennt nur den Zweck des Programms (am
  2026-10-13 gelesen); die Seite schreibt „[Titel nachzutragen]" statt einer eigenen Formulierung, und Titel,
  Monat der Einreichung und Betreuung sind bei Lukas zu erfragen. Die zweite ist die **Kölner Untersuchung**,
  die die Arbeit zitiert: am 2026-10-13 in OpenAlex, Crossref, arXiv, Hochschulrepositorien und auf GitHub
  nicht auffindbar, und das öffentliche Repositorium der Arbeit enthält kein Literaturverzeichnis; die
  Zitation ist nur aus der Arbeit selbst zu holen.
- `index.html` wächst um 13 166 Bytes auf 1 281 464 Bytes (Budget 1,5 MB), die Seite hat fünfzehn
  Abschnitte. Gemessen am 2026-10-13 nach dem Review: 12 429 der Abschnitt samt Zeilenumbruch, 663 sein
  CSS, 102 der Satz in „Methode und Grenzen", minus 28 für das entfernte `rel="noopener"` im Rahmen.

## Kompaktere Seite (2026-10-13, `docs/seitengroesse-2026-10.md`)

`docs/todo.md`, Punkt 2: die Seite stand mit 1 281 464 Byte und 43 Tabellen ganz ausgeklappt da.
Die Messung je Abschnitt, je Tabelle und je Element steht im Dokument, das Skript daneben
(`docs/seitengroesse-2026-10-messung.py`); § 5 geht acht weitere Posten mit gemessenen Bytes durch
und sagt je, warum sie liegen bleiben.

- **Vorschau langer Tabellen** (`docs/decisions.md`, Punkt 48): elf Aufzählungen zeigen Kopf und
  die ersten `report.table_preview_rows` Zeilen (Vorgabe 3), darunter „alle *n* Zeilen zeigen"
  (`<button>` mit `aria-expanded` und `aria-controls`; `<details>` geht in einer Tabelle nicht, das
  Inhaltsmodell von `<tbody>` erlaubt nur `<tr>`). Welche Zeilen sichtbar sind, entscheidet eine
  CSS-Regel: darum stimmt die Vorschau nach dem Sortieren, eine aus Karte, Streudiagramm oder
  Suche markierte Zeile klappt von allein auf, `@media print` zeigt alles, und ein
  `<noscript><style>` hebt die Vorschau ohne JavaScript auf. Offen bleiben die Kernzahlen und die
  Tabellen 5, 6 und 6b. Kosten: 4130 Byte.

## Zahlen (2026-10-13, `v0.11.0` plus Punkt 44, 45, 46 und 47)

- Tests: 991 schnelle (nox-Gate, parallel in rund 44 s, Abdeckung 98,3 %), 20 `slow` (rund 2 min über die volle
  Referenz), 17 `bench` (grün gegen die Baseline), 4 `network` (nur von Hand).
- Register: 29 Schritte; `georep steps` zeigt 27 für Düsseldorf, 28 mit Vergleich, 22 im Periodenprofil
  2014 bis 2020, 21 in der laufenden Periode, 22 für Mönchengladbach. Voller Offline-Lauf auf der Referenz
  rund 23 s (Themenmodell 7,4 s, passender Ausschuss 6,5 s, Index 4,2 s, Berichtsseite 1,7 s, Kennzahlen
  0,1 s).
- Berichtsseite: `index.html` 1,29 MB (1 285 594 Bytes, Budget 1,5 MB; die beiden Umschalter kosten
  110 KB, die Literaturübersicht 13,2 KB, die Vorschau langer Tabellen 4,1 KB), 52 Dateien zusammen
  13,4 MB, fünfzehn
  Abschnitte in Nummernfolge (kernzahlen, suche, karte, zusammenhang, kontrollvariablen, gewichtung,
  parteien, wahlbezirke, gremien, begriffe, monate, methode, abgeleitete-daten, literatur, downloads); „Zwei
  Wahlperioden" und „Laufende Wahlperiode" erscheinen erst mit den Daten aus Konrads Läufen.
- Quelltext: 59 Python-Dateien unter `src/`, rund 16 600 Zeilen; fünf Profile im Paket.
- Mutation (vor dem Ausbau gemessen): `analysis/weights.py` 83 % (`docs/mutation-2026-10-12.md`), `analysis/`
  auf dem Branch 03 133 von 175 Mutanten (76 %); die Überlebenden sind Vertrags-Lambdas an ihren Grenzen und
  `frozen=True` an dataclasses. Mit sechs Arbeitern wurde die Sitzung unter der Last der acht parallelen
  Agenten abgeschossen; drei Arbeiter und nur `analysis/` laufen in sieben Minuten durch.

## Bekannt

- deal 4.24.6: `deal.raises` vergleicht exakte Typen, keine Unterklassen; `deal.has()`/`deal.pure` sind nicht reentrant (Patch bleibt nach Rekursion stehen). Beides umschifft (NetworkError, `deal.safe` für `deep_merge`), nicht upstream gemeldet.
- `nox -s verify` (crosshair) läuft wieder durch und ist grün (Exit 0, 16 Ziele „Not confirmed", 6 Minuten
  am 2026-10-12). Davor brach die Sitzung mit `re.PatternError` ab, bevor sie berichtete: `parse_reference`
  bekommt ein `BodyRules`, dessen Feld `pattern` den Typ `re.Pattern[str] | None` hat, und crosshair ruft
  für den Union-Zweig `re.compile` auf einem symbolischen String. Ein Artefakt des Werkzeugs (crosshair
  0.0.111, Python 3.14), kein Befund — der Code kompiliert keinen Regex aus Daten; das Ziel ist in
  `noxfile.py` mit Begründung ausgenommen und wird weiter von `deal.cases` angegriffen. Die zwei echten
  Gegenbeispiele, die danach sichtbar wurden, sind behoben: `canonical_term` ließ eine Abkürzung stehen,
  wenn die eingesetzte Langform mit dem nächsten Zeichen eine neue bildete (ersetzt jetzt bis zum
  Festpunkt), und `nice_ticks` warf einen `OverflowError` bei zwei endlichen Grenzen mit unendlicher
  Differenz (Vorbedingung verlangt eine endliche Spanne).
- Überlebende Mutanten liegen in Vertrags-Lambdas (Grenzen von r und p); kein Test verletzt sie genau an der Grenze. Bewusst nicht nachgezogen (`docs/mutation-2026-10-12.md`).
- `nox -s mutate` lässt `analysis/topics.py` aus: jeder Mutant dort lässt die schnelle Suite laufen, und die rechnet seit dem Themenmodell mehrfach NMF (Lauf am 2026-10-12 nach 35 Minuten abgebrochen, gezielt je Modul vier Minuten). Die schnelle Suite selbst ist dadurch rund 5 s langsamer; hingenommen.
- Ein voller `georep fetch` von Grund auf lief noch nie; er dauert Stunden und ist wiederaufnehmbar. Hochrechnung aus der Stichprobe: 5,8 h Abruf, 2,8 GB, 12 min Extraktion.
- Auf Konrads Rechner liegen seit dem 2026-10-11 die ersten 200 PDFs nach Paper-ID unter `cache_root/pdf/`; `georep status` zeigt `pdfs` als „offen: Settings geändert", weil `--limit 200` im Stamp steht. Das ist richtig so.
- Labels, die sich nur durch ein Komma unterscheiden, fallen in der POI-Bereinigung zusammen (Verhalten der Arbeit, durch das Wörterbuch harmlos).
- Regel 1 sieht nur Namen: zwei der 113 entfernten Einrichtungen haben einen Kurznamen, der als eigenes
  Wikipedia-Lemma im Wörterbuch bleibt („tonhalle" 72 Dokumente, „nrw-forum" 11). Beide stehen damit in der
  Liste der stadtweiten Begriffe. Dass „tonhalle" nach dem Entfernen von „tonhalle düsseldorf" von 67 auf 72
  Dokumente steigt, ist der Matcher: der längste Begriff gewinnt, und der längere fehlt jetzt.
- Die Abkürzungsregel der Arbeit ersetzt „straße" überall im Begriff, nicht nur am Wortende; aus
  „Straßenbahn Düsseldorf" entstand der Begriff „str.nbahn düsseldorf" (trifft nichts, 2026-10-12 bemerkt).
- Das Themenmodell ist je Rechner und je Thread-Zahl reproduzierbar, nicht darüber hinaus: zwischen 13 und 2 BLAS-Threads unterscheiden sich `themen.parquet` und `themen_anteile.parquet` in den letzten Stellen (gemessen 2026-10-12), Labels und Kennzahlen bleiben gleich. Die Golden-Master-Tests prüfen darum Invarianten, nicht Zahlen.
- Die Nummern der Themen gelten nur für diesen Datenstand; ein Lauf über andere Dokumente vergibt sie neu. Seit Punkt 45 trägt ein gesätes Thema zusätzlich das Kürzel seines Ausschusses, und das ist stabil. Der Stadtname steht bewusst nicht in der Stoppwortliste; er prägt jetzt eines der drei freien Themen.
- Sechs Personennamen überleben den Namensfilter des Themenmodells („hans", „christian", „stephan", „cardeneo", „kühbacher", „tobias"): sie stehen in ihren Ausschussdokumenten oft, aber nie neben einer Amtsbezeichnung (`docs/themenmodell-2026-10.md`, § 2.2). Eine Mandatsträgerliste aus OParl `memberships` würde das schließen und ist nicht abgerufen.
- Ein Join legt die Zeilenfolge nicht fest, auch ein linker nicht: wer eine Spalte daraus positionell
  gegen einen anderen Frame verwendet, hat einen stillen Versagensmodus (Review vom 2026-10-13 fand das
  im Klassifikator; dieselbe Lehre stand schon in `crosswalk.py` und `prep/context.py`). Nach dem Join
  sortieren und alles aus demselben Frame lesen.
- Ein Schritt, dessen `Step` keine Schema-Version bekommt, bleibt bei 1, und `stamp_mismatch` meldet
  „Schema geändert" nie — die Version in den Parquet-Metadaten allein genügt nicht
  (`tests/unit/test_pipeline_steps.py` hält beides zusammen, seit 2026-10-13).
- Ein Test darf die Jahreszahl einer anderen Periode nicht im ganzen HTML suchen: ein `data-value`
  wie „0.040124486620252926" enthält „2025" zufällig. Seit 2026-10-13 sucht er zwischen den Tags.
  Dieselbe Falle ein zweites Mal, am selben Tag: der Literaturabschnitt (Punkt 47) zitiert fremde
  Veröffentlichungen und nennt darum Jahre und Monate, die nichts mit der Periode oder den Daten
  dieser Seite zu tun haben — zwei Tests wurden rot („Dezember" aus einem Eintrag zu Open.NRW, 2025
  aus zwei Aufsätzen). `without_literature(page)` in `tests/conftest.py` schneidet den Abschnitt
  heraus; wer ein Wort im ganzen HTML sucht, nimmt sie.
- Ein Test, der ein Element über sein Markup sucht, darf das schließende `>` nicht mitnehmen:
  `<table id="districts">` fand nichts mehr, als die Tabelle `class="preview"` bekam (sechs Tests
  und ein Snapshot wurden am 2026-10-13 rot). Seitdem steht in den Tests `<table id="districts"`
  ohne Klammer. Dieselbe Lehre für die Konvention der Abschnitte: eine Vorlage, die an einem
  Modellteil hängt, muss mit `{% if model.… %}` **beginnen** (`tests/unit/test_report_render.py`
  liest das aus der Datei); ein `{% from "macros.html.j2" import … %}` davor machte „monate" und
  „perioden" für den Test zu Pflichtabschnitten. Der Import steht darum dahinter.
- Eine CSS-Klasse, die ein Umschalter tauscht, muss auf jeder Fläche dasselbe bedeuten: die Parteizellen
  trugen `p<n>` aus dem Abschnitts-CSS, der Umschalter schrieb `q<n>`, und `.q0` bis `.q4` setzen nur `fill`
  — nach einem Klick auf „Anteil" war die Tönung weg (gefunden am 2026-10-13 mit headless Chrome, nicht von
  einem Test). Seitdem gilt `q<n>` auf einer SVG-Fläche als `fill` und in einer Tabellenzelle als Tönung
  desselben Rangs, beides im Rahmen definiert.
- Dasselbe gilt für die Klassengrenzen unter `[report.diverging]` (Punkt 46) und für alles unter
  `[report]`: der Block ist aus dem Settings-Fingerprint ausgenommen, weil er nur die Anzeige betrifft, und
  darum meldet `georep status` den Schritt `report` nach einer geänderten Grenze als „aktuell". Richtig ist
  das für die Parquet-Dateien, nicht für `index.html`; wer eine Grenze ändert, braucht
  `georep run report --force`.
- Ein Vorlagenwechsel (`templates/sections/*.j2`) macht den Stamp des Schritts `report` nicht ungültig: er trägt die Code-Version des Pakets, nicht den Hash der Vorlagen. Nach einer Änderung an einer Vorlage ohne Versionssprung braucht die Seite ein `georep run report --force` (bemerkt am 2026-10-12).
- Der Settings-Fingerprint ist global: ein neuer Schlüssel lässt alle Schritte einmal neu laufen. Hinnehmbar; ein Fingerprint je Schritt ist zurückgestellt (`docs/plans/00-synergien.md`, § 8).
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab (`docs/baseline-2026-10-10.md`).
- Der Stamp des Schritts `report` liegt als `site/index.html.stamp.json` im veröffentlichten Ordner; harmlos, aber mit dabei.
- Der OParl-Server liefert für Düsseldorf keine Urheberfelder: 0 von 19 108 Rohobjekten und keines der sechs Paper der Seite vom 2026-10-09, auch der „Antrag FDP" nicht. Option 04 leitet den Urheber darum aus `paperType`, Titel und Textkopf ab (Deckung 98,3 %); `georep fetch papers --max-pages 1` ist die Probe, ob sich das geändert hat, und die Quelle `oparl` greift dann ohne Codeänderung.
- Im Wahlbezirk 11 ist Die Linke nicht angetreten (0 Stimmen; die Stimmbezirks-CSV führt dort die 0, anderswo Dutzende). Der Abgleich Dokumentanteil gegen Stimmenanteil lässt solche Bezirke je Partei aus, Die Linke hat also n = 40 statt 41.
- Die Ergebnis-CSV der Ratswahl heißt im Open-Data-Portal inzwischen `…_Stimmbezirke_1.csv` (Datensatzseite am 2026-10-11); `profiles/duesseldorf.toml` zeigt auf `…_0.csv`, woher die Referenz stammt. Vor einem `fetch opendata` nachsehen.
- Mönchengladbach (Option 01, 2026-10-12): Profil, Kette und Vergleichsseite stehen, der volle Abruf steht aus (`docs/runbook-stadt.md`, 3 bis 5 h). Bis sein Paket unter `reference/moenchengladbach/` liegt, meldet `georep publish` die Stadt als „kein Lauf" und baut keine Vergleichsseite; CI überspringt sie. Der Marker `betrifft` kam in der PDF-Stichprobe in 0 von 5 Dokumenten vor (alles Fraktionsanträge der laufenden Periode); ohne Marker durchsucht die Kette den ganzen Text, das Runbook misst am echten Korpus nach (Frage 1.5).
- Die votemanager-CSVs der ITK Rheinland tragen keine Lizenzangabe; die Seite nennt Quelle und Herausgeber und schreibt „Lizenz laut Anbieter nicht angegeben" (Frage 1.4).
- Mönchengladbachs Drucksachennummern tragen kein Kürzel des Gremiums (`0682/XI`, Stichprobe vom 2026-10-12, Body 0011). Das Profil lässt `bodies.reference_pattern` darum leer; der Abschnitt „Gremien" zeigt für diese Stadt 100 % „unbekannt". Woher das Gremium käme (OParl-Feld `organization` der Vorlage oder die Sitzungszuordnung), misst der volle Lauf nach (`docs/plans/01-staedte.md`, § 8, Frage 1.12).
- Der Stadtbezirk Mönchengladbachs steckt im ersten Zeichen der Stimmbezirksnummer (`10401`: Stadtbezirk 1, Wahlbezirk 04, Stimmbezirk 01); das Profil liest ihn mit `columns.results.city_district_from_precinct`. Bestätigt ist die Regel bisher nur an der Fixture (Wahlbezirke 04, 09, 23) und an der Zahl der Stadtbezirke (vier); der volle Lauf prüft sie gegen die Wahlbezirks-CSV (`docs/plans/01-staedte.md`, § 8, Frage 1.13).
- Ein Test darf nicht von der Reihenfolge abhängen: `test_a_city_that_lost_its_run_leaves_the_published_folder` war nur grün, wenn ein Test mit Standardziel vorher den Marker `.georep-publish` in die Quellseite geschrieben hatte; allein gestartet deckte er am 2026-10-12 auf, dass `publish` den Marker beim Kopieren der ersten Stadt löschte (behoben in 3f81995). Einen neuen Test einmal allein starten.
- Die Merges liefen über Rebase je Branch; an rund zwölf Stellen endeten beide Konfliktseiten mitten in einer Funktion oder einem `{% if %}`, und ein Auto-Merge legte `Area` und `read_areas` doppelt an. mypy, ruff und die Zähl-Tests fingen alles; nach einem Rebase `def`-Zahlen je Datei vergleichen.

## Nächster Schritt

Konrads Läufe, je mit Runbook; bis dahin fehlen die betroffenen Teile auf der veröffentlichten Seite und der
Pages-Workflow überspringt sie (`.github/workflows/pages.yml`, Pages-Quelle „GitHub Actions"):

1. Periode 2014 bis 2020 (README, „Zweite Periode abrufen": rund 3 h Metadaten, 8 bis 11 h PDFs,
   wiederaufnehmbar), dann der Schnappschuss unter `snapshots/2014-2020` und die Abschnitte „Zwei
   Wahlperioden".
2. Mönchengladbach (`docs/runbook-stadt.md`, 3 bis 5 h), dann das Paket unter `reference/moenchengladbach/`
   und die Vergleichsseite `vergleich.html` aus `georep publish`.
3. Erstabruf der laufenden Periode (`deploy/README.md`, 16 bis 30 min Metadaten, rund 2,3 h PDFs), danach
   Timer auf kookaburra oder dem VPS; Domain, R2-Bucket und Token sind offene Fragen (`docs/plans/fragen.md`,
   Fragen 7.1 bis 7.4).
4. Optional der Vollabruf der Hauptperiode (2 bis 3 h; zeigt, ob der OParl-Server `modified_since` beachtet
   und ob die Urheberfelder inzwischen gefüllt sind).

Rückstand für danach: `docs/todo.md` (offen ist dort nur noch Punkt 2, die Seitengröße;
Punkt 6, die Lizenz, ist am 2026-10-12 mit dem Wechsel auf GPL-3.0-or-later erledigt,
`docs/decisions.md`, Punkt 42. Punkt 5, die Literaturübersicht, ist am 2026-10-13 erledigt,
`docs/decisions.md`, Punkt 47; Punkt 4, Bartzschs Methodik, ist am 2026-10-12 erledigt,
`docs/methodik-review-2026-10.md`, dessen stärkste offene Empfehlung Punkt 3 eingelöst hat; Punkt 1, das
Themenmodell, ebenfalls am 2026-10-12, `docs/themenmodell-2026-10.md`, offene Annahmen in dessen § 7;
Punkt 3, die Skalierung der Kennzahlen, am 2026-10-13, `docs/skalierung-2026-10.md`, offene Annahmen in
dessen § 8). Offene Entscheidungen stehen in `docs/plans/fragen.md`
(die acht wichtigsten oben): Datenpakete im Repo oder im
R2-Bucket, Düsseldorf unter `data/duesseldorf/`, VPS und Domain, Lizenz der votemanager-CSV, Modellwahl der
Kontrollvariablen. Zurückgestellt (`docs/plans/00-synergien.md`, § 8): Fingerprint je Schritt. Außerdem offen,
wenn jemand es will: ein Ersatz für FlashText oder pypdf nur nach neuer Messung (`docs/decisions.md`, Punkt 14);
die beiden deal-Eigenheiten upstream melden; die Abweichung in Tabelle 5 „ohne Ausreißer" mit Lukas klären.
