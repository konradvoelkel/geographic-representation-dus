# Status

Stand 2026-10-15, `main` auf `v0.14.0` (die Punkte 58 bis 65: die Beratungsfolge als zweite Quelle
des Gremiums, die Urheber Mönchengladbachs und der Wahlperiode 2014 bis 2020, die Spalte „ohne
Ausreißer" als explorativ, die vier Korrekturen ihres Reviews und die Flächen Mönchengladbachs zum
Stand der Wahl, gerechnet und gepackt am 2026-10-15; dazu die Dokumentation in vier Sichten): der Rückstand nach dem Ausbau (`docs/todo.md`, sechs Punkte) ist
abgearbeitet; `bartzsch-exakt` zeigt auf `v0.11.0`, den letzten Stand, der die Zahlen der Arbeit exakt
reproduziert. Der Umbau in sieben Phasen ist abgeschlossen
(`docs/development-plan-2026-10.md`), die Berichtsseite ist gebaut und veröffentlicht (`docs/plan-report-2026-10.md`,
Stufen A bis G, Seite unter <https://konradvoelkel.github.io/geographic-representation-dus/>), und der Ausbau in
acht Optionen ist gemerged (`docs/plan-ausbau-2026-10.md`, Pläne und Abnahmen unter `docs/plans/`). Konrads
vier Netzläufe sind durch (drei am 2026-10-13, der Vollabruf der Metadaten am 2026-10-14 um 02:16), und
die Daten der ersten drei liegen als Pakete im Repo („Datenpakete im Repo"); GitHub Pages baut damit jeden
Teil der Seite ohne Netz. Aufbau in
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
- **Das Budget ist 1,0 MB und steht in den Settings** (`report.page_budget_bytes`,
  `docs/decisions.md`, Punkt 50): die slow-Tests lesen es über `within_budget` (0 schaltet die
  Prüfung wirklich ab), der Schritt `report` meldet eine Überschreitung in seiner Zeile, und
  `georep publish` nennt jede veröffentlichte Seite darüber. Damals 886 328 von 1 000 000 Byte, also
  113 672 Byte Luft (11,4 %) — sie trug den Abschnitt „Zwei Wahlperioden" (geschätzt rund 35 KB,
  gemessen 45 417), der am 2026-10-14 mit den Datenpaketen dazugekommen ist; die Seite steht seitdem
  bei 932 306 Byte und 6,8 % Luft (oben, „Zahlen"). Dafür sind die `<title>` der 1196 Orte gefallen (73 842 Byte;
  ihre Ebene ist `aria-hidden` und ohne JavaScript nie sichtbar, der Tooltip zeigt dasselbe aus
  Datenattributen). Rund 40 KB Reserve liegen gemessen in § 5 des Dokuments (doppelte SVG-Pfade
  der Parteikarten 28 KB, Suchindex 8 KB, Leerraum 4,4 KB); der Minify-Schritt für Leerraum fällt
  mit 0,50 % unter die Grenze von 5 %.
- **Die Begriffslisten je Wahlbezirk werden nachgeladen** (`docs/decisions.md`, Punkt 49): sie
  stehen als `data/begriffe.json` (96 KB, 3946 Paare aus Wahlbezirk und Begriff mit Treffer) neben der Seite
  und kommen beim ersten Aufklappen über `georep.loadJson`, wie die Dokumente beim ersten Klick auf
  einen Begriff. Das war mit 333 750 Byte (26 %) der größte Posten; `index.html` 1 285 594 →
  958 527 Byte. Aus `file://` steht dort derselbe Hinweis wie im Dokumentdialog
  (`georep.offlineNote` formuliert ihn einmal für beide), ohne JavaScript ein `<noscript>` mit dem
  Dateinamen. Der Klick auf einen Begriff hängt seitdem als ein Zuhörer am Dokument.

## Umzug der Hauptperiode (2026-10-13, `docs/decisions.md`, Punkt 52)

Frage 1.7 ist beantwortet: Düsseldorf rechnet wie jede andere Stadt unter seinem Slug. `profile =
"duesseldorf"` steht im Profil, `bootstrap` und `run` schreiben nach `data_root/duesseldorf/` und
`cache_root/duesseldorf/`; `http.sqlite` bleibt geteilt, `reference/` bleibt flach (es ist der eingefrorene
Datensatz, kein Lauf).

- **Die veröffentlichte Adresse bleibt**, weil `georep publish` die erste Stadt aus `publish.cities` an die
  Wurzel von `data_root/site/` legt. Neu ist, dass auch sie kopiert wird; die Quellseite trägt die Zeile
  „Weitere Städte" seitdem nie, erst die Kopie. Der Pages-Workflow legt die Unterseite der zweiten Periode in
  den Ordner der **Stadt** (`<stadt>/site/<periode>/`), nicht nach `data/site/`, und liest beide Pfade mit
  `georep paths`.
- **Wo die Hauptperiode liegt, sagt `Settings.base_profile` (= `city.slug`)**; vorher stand an den zwei
  Stellen `for_profile("")`: das Wörterbuch eines Periodenprofils und der Zielzuschnitt eines
  Crosswalk-Profils. Ein Test über alle Paketprofile hält fest, dass die Zusage stimmt.
- **Der Trockenlauf des Lauf-Skripts ist durchgelaufen** (2026-10-13, Exit 0, 32 s, eigene Datenwurzel auf
  xtraspace, danach gelöscht): `deploy/bin/georep-monitor.sh` findet die Hauptseite über `georep paths` unter
  `data/duesseldorf/site/` und legt sie samt `out/2025/` und `stand.json` richtig ab (`index.html` 886 702
  Byte, 374 mehr als ohne den Link auf die laufende Periode). Der Stub-Test daneben
  (`tests/unit/test_monitor_script.py`) prüft dieselbe Reihenfolge ohne `georep`.
- **Gerechnet ändert sich nichts** (gemessen am 2026-10-13): 27 der 28 Parquet-Dateien sind byteidentisch zum
  flachen Lauf, `index.html` ist 886 328 Byte, der Settings-Fingerprint unverändert (`profile` ist ein Pfad
  und darum ausgenommen). Die 28. Datei, `interim/papers.parquet`, unterscheidet sich an drei von 19 108
  Texten, die der flache Lauf aus lokal extrahierten PDFs nahm (pypdf, siehe „Bekannt"); keine Tabelle danach
  merkt es.

## Datenpakete im Repo (2026-10-14, `docs/decisions.md`, Punkt 56)

Konrads drei Netzläufe vom 2026-10-13 liegen als eingefrorene **Eingaben** im Repo; damit baut GitHub Pages
jede Seite ohne Netz, auch die der zweiten Stadt, der zweiten Periode und der laufenden Periode. Die Antwort
auf die gebündelte Frage („können so erstmal ins Repo, ist ja alles relativ klein") ist damit umgesetzt:
1.2 ist das Paket Mönchengladbachs, 2.1 der Schnappschuss 2014 bis 2020, 3.3 der Quartiersatlas unter
`context/` (der lag schon so da). Für die **laufende** Periode gibt es keine eigene Frage; dass ihr
Schnappschuss ins Repo geht und nicht in ein Bucket, folgt aus Punkt 56 und aus Konrads Antwort auf
Frage 7.4 vom 2026-10-13 („kein Bucket").

| Paket | Bytes | Inhalt | Profil |
|---|---|---|---|
| `reference/moenchengladbach/` | 5 224 917 | `external/` (4), `raw/` (4, seit Punkt 58 mit `organizations.json`), `cache/text/texts.parquet` | `moenchengladbach` |
| `snapshots/2014-2020/` | 37 875 851 | `external/` (4), `raw/papers.jsonl`, Textstore | `duesseldorf-2014` |
| `snapshots/2025/` | 13 894 254 | `external/` (2), `raw/papers.jsonl`, Textstore | `duesseldorf-2025` |
| `snapshots/duesseldorf-beratungsfolge/` | 90 455 | `raw/beratungsfolge.parquet` (Punkt 58) | `duesseldorf` |

Zusammen 56 266 185 Bytes (53,66 MiB) neben `reference/` (85 771 896, 81,80 MiB) und `context/`
(2 242 316, 2,14 MiB): **sechs Pakete, 144 280 397 Bytes, 137,60 MiB**, 76 % der Grenze von 180 MiB im Test.
Gezählt sind überall die Datendateien ohne das README (Review-Befund 14).
Jedes trägt ein README mit Herkunft, Lizenz, Abrufdatum, den Zahlen des Laufs und der SHA-256 jeder Datei;
`tests/unit/test_data_packages.py` hält Dateiliste, Größe und Prüfsumme gegen das README (die Prüfsummen und
die Zeilenzahlen als `slow`-Test) und lässt keine PDFs, Stamps, Manifeste und Caches hinein. Die PDFs liegen
in **keinem** Paket (233 MB, 3,9 GB, 585 MB).

- **Das Format ist dasselbe für alle drei**: `raw/papers.jsonl` und `cache/text/texts.parquet`, gelesen von
  einer Funktion (`bootstrap.seed_stores_from_native`). Der Textstore liegt unter `cache/text/`, weil
  `Layout.reference_view` `cache_root` auf `<reference_root>/cache` setzt. Der Schnappschuss aus
  `deploy/README.md` (`out/2025/snapshots/<JJJJ-MM>/` mit `SHA256SUMS` und `stand.json`) ist etwas anderes:
  ein **Ergebnis** für die Besucher der Seite, nicht eine Eingabe von `bootstrap`.
- **Die laufende Periode hat jetzt ihre eigene Referenz** (`reference_root = "snapshots/2025"`,
  `bootstrap.seed_corpus = true`): `bootstrap` füllt nur einen leeren Store, der fortgeschriebene Stand auf
  kookaburra bleibt also stehen. Nur `bootstrap --force` setzt ihn auf den Stand des Pakets zurück.
- **Die Hauptseite verlinkt `2025/`** (`report.monitoring_url` im Stadtprofil, in beiden Periodenprofilen
  wieder leer); `pages.yml` hat dafür einen Block wie für die zweite Periode und legt die Unterseite nach
  `<stadt>/site/2025/`.
- **Der Nachbau des Pages-Workflows von Hand** (2026-10-14, frische Datenwurzel auf xtraspace, danach
  gelöscht) baut alle Seiten: Hauptseite 932 274 Byte mit den Abschnitten „Zwei Wahlperioden" und „Laufende
  Wahlperiode", `2014-2020/index.html` 818 486, `2025/index.html` 717 246, `moenchengladbach/index.html`
  641 633, `vergleich.html` 88 979, dazu vier `karte.html`; `georep publish` meldet „2 Städte, 1 Vergleich,
  187 Dateien, 34,6 MB" und `PublishSummary.over_budget` ist leer. Die Größen sind der Stand jenes
  Nachbaus; die heutigen stehen unten unter „Zahlen" (die Punkte 58 bis 61 haben sie verschoben,
  Mönchengladbach am stärksten).

## Die Flächen Mönchengladbachs zum Stand der Wahl (2026-10-14, `docs/decisions.md`, Punkt 65)

Frage 1.3 ist beantwortet, und zwar mit Ja: die Stimmbezirksflächen der Kommunalwahl 2025 sind
öffentlich — nicht als Datei, sondern als Layer 16 („Kommunalwahl 2025 Stimmbezirke") des Dienstes
`K12_Politik_und_Wahlen` im Geoportal der Stadt, 179 Flächen, Esri-JSON, `wkid` 25832, Attribut
`Nummer` fünfstellig wie bisher, dl-de/zero-2.0 (recherchiert am 2026-10-14). Darum eine dritte
Quellform `esri-identify` neben `geojson` und `shapefile-zip`, und darum steht im Profil die ganze
Abruf-URL einer **Operation** statt eines Dateinamens.

| | Shapefile „Wahlen" (bis hierher) | Dienst, Layer 16 (ab Punkt 65) |
|---|---|---|
| Stand | 08.06.2022 (Landtagswahl 2022) | Aktualität Kommunalwahl 2025 |
| Flächen | 180 Polygone, davon 175 Stimmbezirke der Wahl 2025 | **179**, genau die Urnen-Stimmbezirke der Wahl |
| Form | Zip mit `.shp/.shx/.dbf/.prj`, pyshp | Esri-JSON mit `rings`, ein GET auf `identify` |
| Fläche | 170,47 km² | **170,47 km²** (dieselbe Stadtfläche; der Prüfpunkt der Ringumwandlung) |
| Abruf | 199 548 Byte | 1 043 618 Byte, 25 187 Stützpunkte, SHA-256 `c2d3de4b…4093b94` |
| Genauigkeit | wie geliefert | von der URL gepinnt (`maxAllowableOffset=0`); mit `=1` wären es 17 326 Stützpunkte und je Fläche bis 1 465 m² Unterschied |

- **`identify`, nicht `query`**: `query` liefert für diesen Layer kein `geometry`-Mitglied (der
  eigene Dienst `Stimmbezirke_Kommunalwahl_2025`, der es hätte, ist gestoppt), und ihr
  `maxRecordCount` ist 2 000 mit Blätterung. `identify` antwortet in einem GET mit allem, was im
  Umschlag liegt; der Umschlag ist hier die ganze Stadt.
- **Die Ringe sind die Arbeit**: Esri-JSON kennt kein Feld für „Loch", das Vorzeichen der
  Ringfläche sagt es (außen im Uhrzeigersinn). Mönchengladbach hat beide Fälle in derselben Ecke:
  `11003` ein Loch von 1 641 m², `11001` dort eine zweite Fläche von 1 639 m². Die Umwandlung dreht
  jeden Ring und schachtelt jedes Loch in den kleinsten äußeren Ring, der es enthält; geprüft ist
  sie an der Fläche, die dabei erhalten bleibt (Vertrag, hypothesis, crosshair und Beispieltests an
  der echten Antwort).
- **Noch nicht gerechnet**: `reference/moenchengladbach/` trägt weiter das Zip von 2022, die
  Stadtseite und alle Zahlen unten stammen daraus, und `bootstrap` meldet die Datei des Profils als
  fehlend. Der Abruf, die Neuberechnung und `georep pack` sind der nächste Schritt.

## Die Beratungsfolge als zweite Quelle des Gremiums (2026-10-14, `docs/decisions.md`, Punkt 58)

Punkt 1 der Befunde vom 2026-10-14 ist umgesetzt: neben der Drucksachennummer entscheidet jetzt die
Beratungsfolge aus OParl (`consultation`), wo die Nummer kein bekanntes Gremium nennt — und nur,
wenn sie **genau eine Organisation** nennt. Dass sie bei mehreren nicht entscheidet, ist gemessen:
die Liste kommt sortiert und entdoppelt, die Reihenfolge der Beratung ist nicht in den Daten, und
von fünf Auswahlregeln trifft die beste 993 von 1 658 Fällen (59,9 %) gegen 99,1 % bei eindeutiger
Folge. **Gezählt werden die genannten Organisationen, nicht die aufgelösten Kürzel** (Review
2026-10-14): sonst entschied eine Lücke in der Tabelle, und 35 Dokumente über alle Profile bekamen
so ein Gremium, das weder ihre Nummer noch ihre Folge eindeutig nennt.

| Profil | Dokumente | unbekannt vorher | nachher | ergänzt | mehrdeutig | bestätigt | Widerspruch |
|---|---|---|---|---|---|---|---|
| `duesseldorf` | 19 108 | 0 (0,0 %) | 0 (0,0 %) | 0 | 0 | 16 902 | 145 |
| `duesseldorf-2014` | 22 215 | 7 314 (32,9 %) | **1 655 (7,4 %)** | 5 659 | 1 535 | 14 464 | 30 |
| `duesseldorf-2025` | 4 095 | 55 (1,3 %) | **0 (0,0 %)** | 0 | 0 | 3 665 | 26 |
| `moenchengladbach` | 2 895 | 2 895 (100,0 %) | **1 275 (44,0 %)** | 1 620 | 1 275 | 0 | 0 |

- **Die Abbildung Organisation → Kürzel ist gelernt, nicht geraten**: `georep learn-bodies` nimmt
  die Dokumente mit eindeutiger Folge und bekanntem Kürzel und lässt sie abstimmen. Düsseldorf: 35
  Organisationen aus 17 047 Dokumenten, Reinheit 16 902/17 047 = **99,1 %**; dieselbe Rechnung auf
  der alten Periode (30, 99,8 %) und der laufenden (32, 99,3 %) widerspricht in **keiner** der 29
  beziehungsweise 30 gemeinsamen Zeilen. Die Tabelle steht als `[bodies.organizations]` im
  Stadtprofil (36 Zeilen, die 36. aus der laufenden Periode).
- **Mönchengladbach hat Gremien**: 27 Organisationen mit Namen und Kürzel aus einem Abruf von
  `…/bodies/0011/organizations` (2026-10-14, eine Seite, 122 Organisationen, 3,8 s; die Datei liegt
  als `raw/organizations.json` im Paket der Stadt). Vier Bezirksvertretungen heißen dort nach der
  Himmelsrichtung; welche Nummer zu welcher gehört, ist an den Treffern belegt — 167 Dokumente mit
  genau einer Bezirksvertretung in der Folge verteilen 683 Dokument-Bezirk-Paare, und die Diagonale
  ist in jeder Zeile und Spalte die größte Zelle (Nord 144/244 = 59 %, Ost 91/149 = 61 %, Süd
  68/131 = 52 %, West 89/159 = 56 %; die Matrix steht im Profil). `classify.enabled` bleibt
  `false`, weil nur 650 der 2 895 Dokumente Text tragen, und seit dem Review vom 2026-10-14 steht
  dort aus demselben Grund `topics.seed = "none"`: acht Themen, gesät aus 11 bis 21 Texten je
  Ausschuss, standen mit Ausschussnamen in der Sensitivitätstabelle und sahen nach mehr aus, als
  diese Texte tragen.
- **Das Paket** `snapshots/duesseldorf-beratungsfolge/` (90 455 Bytes, eine Parquet-Datei mit `id`,
  `consultation_organizations` und `modified`) trägt die Folge der Hauptperiode, deren Korpus aus
  dem Altformat der Arbeit kommt; `georep pack --consultations` schreibt es, `[bodies].consultations`
  nennt es, `bootstrap` kopiert es nach `raw/`. Als JSONL wären es 4 467 207 Bytes.
- `papers_gremien.parquet` trägt `quelle`, `folge_gremium` und `folge_anzahl` (Schema-Version 2);
  der Abschnitt „Gremien" nennt die Anteile beider Quellen in einem Satz, und die Zeile „ohne
  Drucksachennummer" der Gremientabelle heißt jetzt „ohne erkanntes Gremium".
- **`POA` und `ACI` stehen seit dem Review vom 2026-10-14 in `[bodies.committees]`** (Personal- und
  Organisationsausschuss, Ausschuss für Chancengerechtigkeit und Integration; beide Namen belegt),
  und damit auch ihre Organisationen `gr/26` und `gr/400237` in `[bodies.organizations]`. Das löst
  in der alten Periode 241 Dokumente (51 aus der Nummer, 190 aus der Folge) und in der laufenden
  alle 55 — die laufende Periode hat seitdem **0 unbekannte Gremien**. Offen bleibt `gr/27`
  (1 Dokument der Hauptperiode, 21 der alten, keines mit eindeutiger Folge): welches Gremium das
  ist, sagen die Daten nicht.

## Urheber für Mönchengladbach (2026-10-14, `docs/decisions.md`, Punkt 59)

Punkt 3 der Befunde ist umgesetzt: die Stadtseite hat den Abschnitt „Urheber und Parteien". Der
Urheber steht hier in der **Dokumentart**, aber ohne die Fraktion zu nennen, darum kennt
`[originators]` zwei neue Listen — `fraction_types` (`3 - Fraktionsantrag`, 581 Dokumente) und
`person_types` (`6.1 - Mitgliederantrag`, 36). Steht die Art dort, ist die Klasse entschieden, und
die Partei wird im Titel und im **ganzen** Textkopf gesucht statt in einem Fenster um einen Marker:
die Briefköpfe stehen über 300 Zeichen weit.

| Deckung | Mönchengladbach | Düsseldorf, Hauptperiode |
|---|---|---|
| Dokumente | 2 895 | 19 108 |
| Verwaltung | 2 278 (78,7 %) | 9 933 (52,0 %) |
| Fraktion | 581 (20,1 %) | 7 859 (41,1 %) |
| Person | 36 (1,2 %) | 865 (4,5 %) |
| Eingabe | 0 | 124 (0,6 %) |
| **unbekannt** | **0 (0,0 %)** | 327 (1,7 %) |
| Quelle: Dokumentart / Titel / Textkopf | 2 656 / 142 / 97 | 13 432 / 4 618 / 731 |
| Fraktionen mit genannter Partei | **239 von 581 (41,1 %)** | 7 859 von 7 859 bis auf die interfraktionellen |

- **Alle 16 Dokumentarten der Periode sind eindeutig** (Summe 2 895, gemessen 2026-10-14): 14 Arten
  mit 2 278 Dokumenten sind Vorlagen der Verwaltung und ihrer Betriebe, `3 - Fraktionsantrag` ist
  die Fraktion, `6.1 - Mitgliederantrag` die Person. „Urheber unbekannt" ist damit 0,0 % — die
  offene Zahl liegt eine Ebene tiefer: **342 der 581 Fraktionsanträge nennen keine Partei** — 314
  von ihnen tragen gar keinen Text (die 404 des Servers), die 28 übrigen einen Briefkopf ohne
  nennbaren Namen („fraktionsantragfraktion im rat der stadt mönchengladbach"). Ohne Text sind
  insgesamt 390, und 76 davon nennen ihre Partei trotzdem — im Titel.
- **Die acht Fraktionen stehen im Profil**, Namen wörtlich aus `raw/organizations.json`: sechs mit
  Stimmenspalte als `[[originators.parties]]` (CDU, SPD, GRUENE, FDP, Die_Linke, AfD), Die FRAKTION,
  Die PARTEI und Volt als Gruppen ohne Stimmenanteil. „Fraktionslos" bekommt keine Zeile: das Wort
  steht in keinem Titel und in keinem Textkopf dieser Periode.
- **Die Grenzen stehen in „Methode und Grenzen"**: dass der Briefkopf vor der Dokumentart gilt,
  dass bei den 617 Dokumenten, deren Art nur die Klasse nennt, die Partei aus Titel oder Briefkopf
  kommt, und dass vom Titel nur zählt, was hinter seinem letzten Bezug steht. In einer Stadt ohne
  solche Dokumentarten entfällt der Satz.
- **Der Abgleich mit den Hochburgen findet nichts**, in allen 33 Wahlbezirken und für alle sechs
  Parteien: CDU r = −0,012 (p = 0,95), SPD +0,037 (0,84), GRÜNE +0,091 (0,61), FDP −0,199 (0,27),
  Die Linke +0,151 (0,40), AfD −0,098 (0,59). Die Bonferroni-Grenze liegt bei 0,008, erreicht wird
  sie nirgends; die AfD hat 5 Dokumente in 3 Bezirken, ihre Zeile ist eine Zahl ohne Aussage.
- **Der Satz des Abschnitts zählt seine Quellen**, statt drei Düsseldorfer Beispiele zu zitieren
  („2 656 aus der Dokumentart, 142 aus dem Titel und 97 aus dem Textkopf"): auf der
  Mönchengladbacher Seite waren die Beispiele falsch, denn keine Dokumentart dieser Stadt nennt
  eine Partei.
- Die Seite der Stadt wächst von 649 721 auf **819 149 Byte** (Budget 1 000 000, 18,1 % Luft); den
  Zuwachs tragen die sechs Parteikarten mit 33 Flächen und die Tabelle je Wahlbezirk.

## Urheber der Wahlperiode 2014 bis 2020 (2026-10-14, `docs/decisions.md`, Punkt 60)

Punkt 4 der Befunde ist umgesetzt: „Urheber unbekannt" fällt in jener Periode von **12 418
(55,9 %)** auf **2 356 (10,6 %)**. Es brauchte zwei Dokumentarten und einen Briefkopf, alle drei im
Stadtprofil.

| Klasse | vorher | nachher |
|---|---|---|
| Verwaltung | 2 285 (10,3 %) | **10 575 (47,6 %)** |
| Fraktion | 7 008 (31,5 %) | **8 815 (39,7 %)** |
| Person | 486 (2,2 %) | 449 (2,0 %) |
| Eingabe | 18 | 20 |
| **unbekannt** | **12 418 (55,9 %)** | **2 356 (10,6 %)** |
| Quelle: Dokumentart / Titel / Textkopf | 2 866 / 2 821 / 4 110 | **11 158 / 2 462 / 6 239** |

- **`Verwaltungsvorlage` ist die Verwaltung** (8 337 Dokumente, 37,5 % jener Periode, und in der
  Hauptperiode wie in der laufenden kein einziges Mal): sie ist der Gegenbegriff zu `Vorlage aus der
  Politik` in derselben Taxonomie. Damit sind auch die 197 Dokumente richtig, die bis dahin über
  Titel oder Textkopf zu einer Fraktion wurden — Vorlagen, die einen Fraktionsantrag **zitieren**.
- **Der Vorlagenkopf der älteren Form nennt den Urheber**: „vorlage 173/ 85/2014 seite 1 von 2 rsd
  vorlage x öffentlich nicht öffentlich  fraktion die linke  der bezirksvertretung 3  an den
  bezirksvorsteher …". Der Briefkopfmarker ist genau diese Formularzeile plus „fraktion" in 80
  Zeichen; 5 454 Köpfe treffen, 5 168 davon nennen eine Partei, die 286 übrigen sind
  „interfraktioneller antrag". Er steht **vor** der Dokumentart (Punkt 62), denn der Briefkopf
  gehört dem Verfasser und die Dokumentart dem System.
- **Die Hauptperiode und die laufende Periode sind byteidentisch unberührt**, gemessen und als Test
  eingefroren (`tests/golden/test_parties_numbers.py`): `classify_originators` liefert mit und ohne
  die drei neuen Einträge dieselbe Tabelle für alle 19 108 und alle 4 095 Dokumente. Der Anker kommt
  dort in 0 Dokumenten vor, weil der Korpus den Text hinter „betrifft" abschneidet.
- **Neue Parteischreibweisen brauchte es nicht**: `bündnis90/die grünen` ohne Leerzeichen,
  `bü90/die grünen`, `b90/die grünen`, `die linke.` mit Punkt und `AFD` treffen alle auf vorhandene
  Muster. Dokumente je Partei: CDU 3 647, SPD 2 708, GRÜNE 2 417, FDP 1 335, Die Linke 505, AfD 13
  (damals ein Einzelmandat), Tierschutz/Freie Wähler 168.
- **47 Fraktionsanträge liegen unter `Verwaltungsvorlage`** und tragen trotzdem ihren eigenen
  Briefkopf (Review 2026-10-14, Punkt 62). Weil die Dokumentart vor dem Textkopf gefragt wird,
  standen sie als Verwaltung da; seit dem Review gilt ein **Briefkopfmarker vor der Dokumentart**,
  und sie sind Fraktion. Die Bedingung dafür ist gemessen: die Formularzeile trifft keine der 161
  Zitate, keine der beiden Eingaben und keines der 28 Dokumente mit Mandatsträger im Titel.
- **Der Abgleich mit den Hochburgen** (Ratswahl 2020, Parteispalten D1 bis D6 im Profil
  `duesseldorf-2014`): FDP r = +0,395 (p = 0,0106), AfD −0,378 (0,0149), Die Linke −0,255 (0,108),
  SPD +0,127 (0,429), GRÜNE +0,052 (0,748), CDU −0,0005 (0,998). Unter der Bonferroni-Grenze von
  0,008 bleibt **keine** Partei — anders als in der Hauptperiode, wo die FDP mit p = 0,0033 darunter
  liegt.
- Die Seite der Periode wächst von 820 128 auf **820 168 Byte** (Budget 1 000 000).

## Die Spalte „ohne Ausreißer" sagt, was sie ist (2026-10-14, `docs/decisions.md`, Punkt 61)

Punkt 2 der Befunde ist umgesetzt: die Spalte bleibt, trägt im Kopf aber das Wort **„explorativ"**,
und unter Tabelle 5 steht ein Absatz aus zwei Sätzen. Der erste sagt, dass die Spalte **nach** dem
Ansehen der Daten entstanden ist — ausgeschlossen sind die beiden Bezirke mit den höchsten
Trefferquoten, eine Entscheidung über diesen Datensatz und keine Vorhersage. Der zweite nennt beide
p-Werte: „dort steht dieselbe Spalte bei *r* = 0,282 und p = 0,082, hier bei *r* = 0,335 und
p = 0,037 — zwei nah beieinander liegende Schätzungen, von denen eine darunter und eine knapp über
der 5-%-Grenze liegt. Die Signifikanz dieser Spalte trägt damit nicht über die Perioden hinweg; die
geschätzte Steigung schwankt dabei um den Faktor 2,6 (216 gegen 82)." Dass der Satz nicht „von der
Signifikanz bleibt nichts" sagt, ist Review-Befund 10: die beiden *r* liegen 0,053 auseinander und
sind nach Fisher-z nicht unterscheidbar (p = 0,80).

- **Keine Zahl steht hart im Text.** Beide p-Werte, beide *r* und beide Steigungen kommen aus dem
  Modell: die eigenen aus `regression`, die anderen aus `comparison.previous_pair` — derselben
  Rechnung über die `results` der anderen Periode, aus der auch ihr `summary.json` entsteht. Auch
  das Urteil kommt aus den Zahlen, in drei unabhängigen Stücken: wie weit die beiden *r*
  auseinanderliegen (Grenze 0,1), auf welchen Seiten der 5-%-Grenze die beiden p liegen (vier Fälle,
  „knapp" darüber nur unter 0,15) und ob die Steigung um mehr als die Hälfte schwankt;
  `parametrize`-Tests rendern die Fälle, auch die fünf Zweige des Makros im Abschnitt „Zwei
  Wahlperioden".
- **„Methode und Grenzen" sagt es noch einmal länger** (Review-Befund 12): dorthin verweist die
  Fußnote, und dort stand nichts dazu. Der Absatz nennt, warum die Nummern in den Einstellungen
  stehen, dass eine hohe Trefferquote vor allem ein großes Wörterbuch anzeigt (*r* = 0,760 gegen
  0,173 zu den Wahlberechtigten) — also genau die Eigenschaft, nach der ausgeschlossen wird —, und
  dass 41 Wahlbezirke keine Stichprobe sind, sondern die ganze Grundgesamtheit.
- **Ohne Vergleichsprofil nur der erste Satz**, ohne zweite Spalte (`analysis.exclude_districts`
  leer, so bei Mönchengladbach) kein Absatz. Die Seite der Periode 2014 bis 2020 zeigt den ersten
  Satz, die laufende Periode hat keine Regression und damit keinen Abschnitt.
- **Ein Satz je Periode im Abschnitt „Zwei Wahlperioden"** mit *r* und p beider Spalten und dem
  Urteil aus den Zahlen (Jinja-Makro `verdict`, fünf Zweige): „In der Wahlperiode 2014 bis 2020
  liegt die Regression über alle 41 Wahlbezirke bei *r* = 0,238 und p = 0,133, ohne 1 und 10 bei
  *r* = 0,282 und p = 0,082 — in keiner der beiden Spalten signifikant. In der Wahlperiode 2020 bis
  2025 sind es *r* = 0,189 bei p = 0,236 über alle 41 Wahlbezirke und *r* = 0,335 bei p = 0,037 ohne
  1 und 10 — nur in der explorativen zweiten Spalte signifikant."
- Kosten, gemessen an der Hauptseite: **878 Byte** der Absatz unter Tabelle 5, **542 Byte** der
  Satz je Periode, **1 231 Byte** der Absatz in „Methode und Grenzen", **40 Byte** der Kopfhinweis.
- **Mit Lukas zu klären bleibt die Spalte trotzdem**, zusammen mit der Abweichung aus
  `docs/baseline-2026-10-10.md` (siehe „Bekannt").

## Was das Review der Punkte 59 bis 61 geändert hat (2026-10-14)

Die Punkte 62, 63 und 64 sind die Befunde des Reviews mit eigener Entscheidung; je ein Abschnitt in
`docs/decisions.md`, die übrigen stehen in den Punkten 59 bis 61 selbst.

- **Punkt 62, der Briefkopf vor der Dokumentart**: 47 Fraktionsanträge der alten Periode lagen
  unter `Verwaltungsvorlage`; Verwaltung 10 622 → 10 575, Fraktion 8 768 → 8 815.
- **Punkt 63, die letzte `hier:`-Klausel des Titels**: drei Mönchengladbacher Dokumente trugen die
  Partei des zitierten Antrags; Fraktionen mit Partei 242 → 239 von 581.
- **Punkt 64, `\bdie fraktion\b`**: ein Antrag der Zentrumspartei galt als Antrag der Gruppe Die
  FRAKTION, weil das Muster „die Fraktionsvorsitzende" traf.
- **Zwei Verträge mehr in den Settings**: eine Dokumentart darf in höchstens einer der vier Listen
  stehen (sonst entschiede die Reihenfolge im Code, welche Klasse gewinnt), und die
  Eigenschaftstests der Zuordnung laufen über **beide** Konfigurationsformen — Düsseldorf mit
  Antragspräfix, Titel und Textkopf, Mönchengladbach mit `fraction_types` und `title_split_markers`.
- **Drei Stellen auf der Seite sagten etwas anderes als die Zahl darunter**: die Spalte „davon
  allein" der Parteitabelle ist eine **Trefferzahl** und stand neben „Dokumente", wo auf der
  Mönchengladbacher Seite „Dokumente 107 / davon allein 168" zu lesen war — sie heißt jetzt so und
  steht hinter „Treffer" (`PartyRow.hits_alone`). Der Satz zur Deckung nennt nur noch die Klassen,
  die es in der Stadt gibt (vorher „0 Eingaben nach § 24 GO NRW und 0 ohne erkennbaren Urheber",
  Punkt 39). Und der Kommentar zu `person_types` sagt jetzt, was gezählt ist: von den 36 Anträgen
  nennen 10 den Seniorenrat, 3 den Integrationsrat, 2 das Jugendparlament.
- **Die Zahlen Mönchengladbachs sind eingefroren** wie die der alten Periode
  (`tests/golden/test_parties_numbers.py`, `slow`): Klassen, Quellen, Dokumente je Partei, die 239
  mit Partei und die Zerlegung der 342 ohne.
- **Das Themenmodell der Stadt rechnet mit den neuen Stoppwörtern**, und das ist die Absicht:
  `[originators]` bringt über `topics.stop_sources` 13 Wörter in die Liste (cdu, spd, fdp, afd,
  grüne, grünen, gruene, bündnis, linke, partei, volt, fraktion, die). Gemessen am 2026-10-14
  ändern sich dadurch **19 der 20 Themenzeilen** — meist nur ihre Nummer, inhaltlich fallen die
  **zwei Briefkopf-Themen** weg („spd, bündnis, grünen, fdp, fraktion, ratsfraktion" und „cdu,
  ratsfraktion, email, meyers, regentenstr, franz"), und ein Sachthema kommt dafür („auswirkung,
  nrw, abs, finanzielle, nordrhein, hauptausschuss"). Dasselbe hat Punkt 45a in Düsseldorf getan.
  **`stop_keep` braucht die Stadt nicht**: keines der 13 Wörter steht in den 190
  Beschriftungswörtern der Seite als Sachwort, anders als „klima" und „tierschutz" in Düsseldorf.

## Zahlen (2026-10-15, `v0.11.0` plus Punkt 44, 45, 46, 47, 52, 56 und 58 bis 65)

- Tests: 1277 schnelle (nox-Gate, parallel in rund 45 s, Abdeckung 98,5 %), 39 `slow` (rund 5 min über die
  volle Referenz, die sechs Datenpakete, das Paket der Periode 2014 bis 2020 und die veröffentlichte
  Seite), 18 `bench` (grün gegen die
  Baseline), 4 `network` (nur von Hand). Alle drei am 2026-10-14 nach den Punkten 59 bis 64 mit
  Exit 0 gelaufen.
- Register: 29 Schritte; `georep steps` zeigt 27 für Düsseldorf, 28 mit Vergleich, 22 im Periodenprofil
  2014 bis 2020, 21 in der laufenden Periode, 23 für Mönchengladbach (seit Punkt 58 ohne
  `committees`, dafür mit den Gremien aus der Beratungsfolge; seit Punkt 59 mit `parties`). Voller Offline-Lauf auf der Referenz
  rund 23 s (Themenmodell 7,4 s, passender Ausschuss 6,5 s, Index 4,2 s, Berichtsseite 1,7 s, Gremien
  0,3 s seit Punkt 58, Kennzahlen 0,1 s).
- Berichtsseite: `index.html` der Hauptseite **935 619 Bytes veröffentlicht** (Budget 1 000 000,
  **64 381 Byte Luft, 6,4 %**; +524 Byte für den Quellensatz aus Punkt 58, +2 813 für die Punkte 59
  bis 64) mit beiden Periodenabschnitten,
  55 Dateien zusammen 13,2 MB; ohne die Abschnitte „Zwei Wahlperioden" und „Laufende Wahlperiode" sind es
  886 360 Bytes, die beiden kosten also 45 417 und 374 Byte (gemessen 2026-10-14; die beiden Umschalter
  kosten 110 KB, die Literaturübersicht 13,2 KB, die Vorschau langer Tabellen 4,1 KB, `begriffe.json` liegt
  mit 96 KB daneben). Siebzehn Abschnitte in
  Nummernfolge (kernzahlen, suche, karte, zusammenhang, kontrollvariablen, gewichtung, perioden,
  parteien, wahlbezirke, gremien, begriffe, monate, methode, abgeleitete-daten, literatur, downloads,
  laufend). Die Unterseiten: `2014-2020/` 822 027, `2025/` 718 384, `moenchengladbach/` 819 872,
  `vergleich.html` 89 597 Bytes (alle am 2026-10-14 nach den Punkten 59 bis 64 gemessen; am
  2026-10-15 nach Punkt 65 neu: `moenchengladbach/` **807 393** und `vergleich.html` **93 794**,
  die Stadtseite also 12 479 Byte kleiner und der Vergleich 4 197 größer;
  Mönchengladbach wuchs um 170 151 Byte, weil es seit Punkt 59 den Abschnitt „Urheber und Parteien"
  mit sechs Parteikarten über 33 Flächen hat; `georep publish --strict-budget` endet mit Exit 0 und
  meldet „2 Städte, 1 Vergleich, 101 Dateien, 16,5 MB").
- Quelltext: 64 Python-Dateien unter `src/`, rund 19 400 Zeilen; fünf Profile im Paket.
- Mutation (2026-10-13, `docs/mutation-2026-10-13.md`): 882 Mutanten über die dreizehn Module des
  Ausbaus, 717 getötet (81,3 %), 165 Überlebende — davon 100 in Vertragsgrenzen, 27 nachgerechnet
  äquivalent, 38 Grenzen, die nur ein genauer Wert unterscheidet. Auf `v0.12.0` waren es 652 von 876
  (74,4 %). Rund 20 Minuten für alle dreizehn Module mit **drei** Arbeitern, **je Modul eine eigene
  Sitzung mit nur seinen Testdateien** (`nox -s mutate -- fast` sind die acht schnellen in 539 s).
  Älter: `analysis/weights.py` 83 % (`docs/mutation-2026-10-12.md`), `search/` und `analysis/` 79 %
  (`-11.md`).

## Absicherung (2026-10-13, `docs/absicherung-2026-10.md`)

Konrads Auftrag „Absicherung statt Ausbau": keine neuen Funktionen, das Vorhandene härten und messen.
Entscheidungen als Punkt 53 in `docs/decisions.md`.

- **Mutationstest über die dreizehn Module des Ausbaus** (`docs/mutation-2026-10-13.md`): 882 Mutanten
  an HEAD, **717 getötet (81,3 %)**, 165 Überlebende; auf `v0.12.0` waren es 652 von 876 (74,4 %). Die größten Löcher
  waren `analysis/scaling.dictionary_bias` (kein einziger Test), die Vergleichsseite (nur auf
  Anwesenheit geprüft, 46 % → 84 %), die Zahlen des OLS-Modells (nur im slow-Test) und die Spalte
  `treffer` der Urheberzuordnung.
- **crosshair über 31 statt 22 Ziele**; vier Gegenbeispiele, alle echt und alle dieselbe Sorte: eine
  Annahme über die Eingabe, die nur in der Nachbedingung stand (`terms_payload`, `fit`, `body_figures`,
  `bars`). `nox -s verify` Exit 0, 27 „Not confirmed".
- **Zwei Schritte haben einen eigenen Zusatz im Stamp** (`Step.extra`): `report` einen Hash über die
  Vorlagendateien des Pakets, `literatur.toml`, `settings.report` und die vier Anzeigewerte, die der
  globale Fingerprint auslässt (`bodies.names_as_of`, `period.label`, `context.dataset`, die `label`
  der Gewichtungsregeln); `topics` einen über die Stoppwortliste des Pakets, die das Modell prägt,
  während im Fingerprint nur ihr Name steht. Damit sind die zwei Einträge aus „Bekannt" weg, nach
  denen ein Vorlagenwechsel oder eine geänderte Klassengrenze ein `georep run report --force`
  brauchte.
- **Fünf Stellen sortieren nach einem Join** (`dictionary_bias`, drei Regressionsframes, die beiden
  veröffentlichten Tabellen der Kontrollvariablen); die veröffentlichte Tabelle bekam dafür eine eigene
  Funktion mit Vertrag (`prep.context.named_weights`), und der Schritt `context` die Schema-Version 2,
  damit ein alter, unsortierter Lauf einmal neu rechnet.
- **`nox -s alone`** prüft die Reihenfolgeunabhängigkeit: 97 Dateien allein (94 grün, drei ohne schnelle
  Tests), die Suite rückwärts 1065 Tests, zusammen 228 s, Exit 0 — keine Abhängigkeit gefunden.
- **Wöchentlicher Qualitätslauf** in `.github/workflows/quality.yml` (montags und von Hand, verify plus
  die gezielte Mutationssitzung, geschätzt unter 30 min, `timeout-minutes: 45`). Noch nicht erprobt.
- Ungemessen bleiben `report/model.py`, `report/charts.py` und `report/build.py` (rund 3 500 Zeilen);
  das ist der nächste offene Posten dieser Art.

## Bekannt

Hier stehen **Fakten** über das System, die Daten und die Werkzeuge, je mit Datum. Die
**Arbeitsregeln**, die sich daraus ergeben — wie man testet, was ein Join tut, wo eine
Schema-Version hingehört, wie eine Zahl in einem Test gerundet wird —, stehen seit dem 2026-10-13
in `CLAUDE.md` unter „Arbeitsweise", wo sie beim nächsten Handgriff gelesen werden
(`docs/absicherung-2026-10.md`, § 4). Verloren ist nichts, nur umgezogen.

- **1 535 Dokumente der Periode 2014 bis 2020 und 1 275 Mönchengladbachs bleiben „unbekannt",
  obwohl ihre Beratungsfolge Gremien nennt** (2026-10-14, Punkt 58): sie nennt mehrere, und welches
  das federführende ist, steht nicht in den Daten
  (`georep.oparl.OparlPaper.consultation_organizations` liest die Liste sortiert und entdoppelt).
  Fünf Auswahlregeln sind gemessen, die beste trifft 59,9 %; das ist kein Ersatz für eine Quelle.
  Wer es besser wissen will, braucht die Beratungsfolge **mit** Reihenfolge, also einen Abruf der
  `consultation`-Objekte selbst (je Dokument ein Objekt mit `meeting` und `order`).
- **Eine Änderung am Python-Code der Berichtsseite macht den Stamp des Schritts `report` nicht
  ungültig** (2026-10-14, bei Punkt 58 wieder aufgefallen): im Stamp stehen die Paketdateien der
  Vorlagen, `[report]` und die Code-**Version**, nicht der Code. Ohne Versionssprung braucht die
  Seite danach ein `georep run report --force` je Profil. Dasselbe gilt für eine geänderte
  Klassengrenze (siehe `defaults.toml`, `[report.diverging]`).
- deal 4.24.6: `deal.raises` vergleicht exakte Typen, keine Unterklassen; `deal.has()`/`deal.pure` sind nicht reentrant (Patch bleibt nach Rekursion stehen). Beides umschifft (NetworkError, `deal.safe` für `deep_merge`), nicht upstream gemeldet.
- `nox -s verify` (crosshair) läuft wieder durch und ist grün (Exit 0, alle Ziele „Not confirmed";
  **37 Ziele** seit dem 2026-10-15, als die vier Funktionen der Esri-Ringe dazukamen, 10 Minuten bei
  33 Zielen am 2026-10-14; 6 Minuten bei 16 Zielen am 2026-10-12). Der Lauf vom 2026-10-14 fand dabei ein echtes
  Gegenbeispiel in `report.model.body_figures`: ein von Hand gebautes `SourceCounts` mit einer fremden
  Quelle flog als `KeyError` ohne Fehlertext (Punkt 58). Behoben als Vorbedingung `_sources_are_known`,
  dieselbe Sorte wie `_kinds_are_known` vom 2026-10-13. Davor brach die Sitzung mit `re.PatternError` ab, bevor sie berichtete: `parse_reference`
  bekommt ein `BodyRules`, dessen Feld `pattern` den Typ `re.Pattern[str] | None` hat, und crosshair ruft
  für den Union-Zweig `re.compile` auf einem symbolischen String. Ein Artefakt des Werkzeugs (crosshair
  0.0.111, Python 3.14), kein Befund — der Code kompiliert keinen Regex aus Daten; das Ziel ist in
  `noxfile.py` mit Begründung ausgenommen und wird weiter von `deal.cases` angegriffen. Die zwei echten
  Gegenbeispiele, die danach sichtbar wurden, sind behoben: `canonical_term` ließ eine Abkürzung stehen,
  wenn die eingesetzte Langform mit dem nächsten Zeichen eine neue bildete (ersetzt jetzt bis zum
  Festpunkt), und `nice_ticks` warf einen `OverflowError` bei zwei endlichen Grenzen mit unendlicher
  Differenz (Vorbedingung verlangt eine endliche Spanne).
- `nox -s mutate` lässt `analysis/topics.py` aus: jeder Mutant dort lässt die schnelle Suite laufen, und die rechnet seit dem Themenmodell mehrfach NMF (Lauf am 2026-10-12 nach 35 Minuten abgebrochen; gezielt je Modul mit nur seinen Testdateien sind es vier Minuten). Die schnelle Suite selbst ist dadurch rund 5 s langsamer; hingenommen.
- `georep publish` löschte die Markerdatei `.georep-publish` beim Kopieren der ersten Stadt; aufgefallen ist das erst, als der Test einmal allein lief (2026-10-12, behoben in 3f81995). Die Arbeitsregel daraus steht in `CLAUDE.md`, die Prüfung in `nox -s alone`.
- Ein voller `georep fetch` von Grund auf lief noch nie; er dauert Stunden und ist wiederaufnehmbar. Hochrechnung aus der Stichprobe: 5,8 h Abruf, 2,8 GB, 12 min Extraktion.
- Auf Konrads Rechner liegen seit dem 2026-10-11 die ersten 200 PDFs nach Paper-ID unter `cache_root/pdf/`,
  also im **flachen** Ordner der alten Hauptperiode. Das Hauptprofil rechnet seit dem Umzug (Punkt 52) unter
  `cache_root/duesseldorf/` und zeigt dort `0 PDFs` und für `pdfs` „kein Stamp"; das ist der Zustand vor dem
  Handgriff unten, nicht ein Fehler. Erst nach dem Verschieben zeigt `georep status` wieder „offen: Settings
  geändert", weil dann `--limit 200` im mitgezogenen Stamp steht — und auch das ist richtig so.
- Dieselben 200 PDFs sind der Grund, dass der flache Lauf drei Texte anders hat als die Referenz: pypdf 6.20.0
  reproduziert 197 von 200 zeichengleich (`docs/profiling/README.md`). Auf `index.html` und alle
  Ergebnistabellen wirkt sich keiner der drei aus.
- Auf Konrads Rechner liegen die flachen Ordner `data/{external,raw,interim,processed,site}` und
  `cache/{pdf,text}` nach dem Umzug (Punkt 52) weiter da und sind bis zum Ende seiner Netzläufe auch in
  Benutzung: der Lauf im Worktree auf dem Tag `v0.12.0` liest und schreibt sie noch. Der Handgriff dafür steht
  unten unter „Nächster Schritt"; `data/site/` ist seit dem 2026-10-13 die Kopie aus `georep publish` und
  gehört damit ohnehin wieder dem neuen Stand.
- **Overpass unter Last weist `[timeout:90]` ab, `[timeout:25]` nicht** (gemessen am 2026-10-13 am
  Mönchengladbach-Lauf): dieselbe Stimmbezirksabfrage bekam von allen vier öffentlichen Instanzen
  (overpass-api.de, lz4, z, maps.mail.ru) nach wenigen Sekunden `504 Gateway Timeout`, mit 25 s
  Budget antwortete sie in 2 s mit 124 Elementen; die Trivialabfrage lief überall. Der Server
  schätzt die Kosten vorab gegen sein Slot-Budget, ein großes `[timeout:N]` ist darum der Grund der
  Ablehnung, nicht die Absicherung. Die Zahl steht seit dem 2026-10-13 als
  `sources.osm.query_timeout_s` in den Settings (`docs/decisions.md`, Punkt 54). Zwei Folgen: die
  vor dem Wechsel mit 90 s gecachten Antworten liegen unter ihrem alten POST-Body und werden nicht
  mehr getroffen (Punkt 9), und ein neuer Schlüssel in `sources` macht jeden Stamp ungültig —
  `georep status` sagt für jeden gerechneten Schritt einmal „offen: Settings geändert".
- **Je Versuch kamen rund 27 der 306 Overpass-Abfragen durch**, dann kam der nächste 504 und der
  Schritt `streets_osm` endete (gemessen 2026-10-13). Dass ein erneuter Lauf dort weiterging, wo er
  aufhörte, lag allein am HTTP-Cache. Seit dem 2026-10-13 wiederholt `fetch_street_names` bei 504
  und 429 selbst, bis zu `sources.osm.retries` mal je Stimmbezirk mit wachsender Pause
  (`docs/decisions.md`, Punkt 55); die Session tut es nicht, ihre Retry-Regel erlaubt GET und HEAD,
  und die Abfrage ist ein POST. Ein Lauf über alle 306 Bezirke mit der neuen Fassung steht noch
  aus — gemessen ist die Ursache, nicht die Heilung.
- Labels, die sich nur durch ein Komma unterscheiden, fallen in der POI-Bereinigung zusammen (Verhalten der Arbeit, durch das Wörterbuch harmlos).
- Regel 1 sieht nur Namen: zwei der 113 entfernten Einrichtungen haben einen Kurznamen, der als eigenes
  Wikipedia-Lemma im Wörterbuch bleibt („tonhalle" 72 Dokumente, „nrw-forum" 11). Beide stehen damit in der
  Liste der stadtweiten Begriffe. Dass „tonhalle" nach dem Entfernen von „tonhalle düsseldorf" von 67 auf 72
  Dokumente steigt, ist der Matcher: der längste Begriff gewinnt, und der längere fehlt jetzt.
- Die Abkürzungsregel der Arbeit ersetzt „straße" überall im Begriff, nicht nur am Wortende; aus
  „Straßenbahn Düsseldorf" entstand der Begriff „str.nbahn düsseldorf" (trifft nichts, 2026-10-12 bemerkt).
- Das Themenmodell ist je Rechner und je Thread-Zahl reproduzierbar, nicht darüber hinaus: zwischen 13 und 2 BLAS-Threads unterscheiden sich `themen.parquet` und `themen_anteile.parquet` in den letzten Stellen (gemessen 2026-10-12), Labels und Kennzahlen bleiben gleich.
- Die Nummern der Themen gelten nur für diesen Datenstand; ein Lauf über andere Dokumente vergibt sie neu. Seit Punkt 45 trägt ein gesätes Thema zusätzlich das Kürzel seines Ausschusses, und das ist stabil. Der Stadtname steht bewusst nicht in der Stoppwortliste; er prägt jetzt eines der drei freien Themen.
- Sechs Personennamen überleben den Namensfilter des Themenmodells („hans", „christian", „stephan", „cardeneo", „kühbacher", „tobias"): sie stehen in ihren Ausschussdokumenten oft, aber nie neben einer Amtsbezeichnung (`docs/themenmodell-2026-10.md`, § 2.2). Eine Mandatsträgerliste aus OParl `memberships` würde das schließen und ist nicht abgerufen.
- Schnittstücke aus der Fließkomma-Arithmetik sind keine Gewichte mehr (`docs/decisions.md`,
  Punkt 51, 2026-10-13): `crosswalk.area_shares` nahm jedes Stück mit `area > 0.0`, und zwei
  Flächen mit gemeinsamer Grenze schneiden sich in etwa 4,44e-16 statt in 0 — ob dieses Nichts
  über 0 liegt, hängt an den Koordinaten und nicht an der Geografie. hypothesis hat es gefunden
  (`test_scaling_the_grid_does_not_change_the_shares` wurde rot: dasselbe Rechteck ergab in einem
  um 1,4603 gestreckten Gitter eine Zeile mehr). Jetzt fällt ein Stück unter
  `crosswalk.min_share` (1e-9 der Quellfläche, 0 schaltet ab) vor der Normierung weg. Auf der
  Referenz: `area_shares` 1134 statt 1244 Zeilen, `wahlbezirke_crosswalk` 465 statt 485, kleinster
  Anteil 1,1e-09 statt 6,8e-19, kleinstes veröffentlichtes Gewicht 1,3e-10 statt 2,9e-17.
  `wahlbezirke_kontext` ändert sich um höchstens 8,9e-09, Tabelle 6 um 3,9e-08 an einem
  Koeffizienten und 3,2e-11 an einem R²; **keine gedruckte Stelle der Seite ändert sich** (alle
  Abschnitte außer „Downloads" byteidentisch, `wahlbezirke_auswertung.parquet` byteidentisch,
  Treffer 29 010, Wörterbuch 5727). Der neue Schlüssel ändert den globalen Fingerprint, also
  liefen alle Offline-Schritte einmal neu (23 s).
- **Behoben am 2026-10-13** (Punkt 53): der Schritt `report` trägt einen eigenen Zusatz im Stamp, einen
  Hash über die Vorlagendateien des Pakets samt ihrem CSS und JavaScript, über `literatur.toml` und über
  `settings.report`. Davor machte weder ein Vorlagenwechsel noch eine geänderte Klassengrenze unter
  `[report.diverging]` den Stamp ungültig — der Block `[report]` ist aus dem Settings-Fingerprint
  ausgenommen, weil er nur die Anzeige betrifft, und das ist für die Parquet-Dateien richtig, für
  `index.html` war es falsch. `georep run report --force` braucht seitdem niemand mehr dafür, und die
  Datenschritte laufen nicht mit neu (der globale Fingerprint ist unberührt).
- Der Settings-Fingerprint ist global: ein neuer Schlüssel lässt alle Schritte einmal neu laufen. Hinnehmbar; ein Fingerprint je Schritt ist zurückgestellt (`docs/plans/00-synergien.md`, § 8).
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab
  (`docs/baseline-2026-10-10.md`). Seit dem 2026-10-14 heißt die Spalte auf der Seite im Kopf
  „explorativ", und darunter steht, dass dieselbe Spalte in der Wahlperiode 2014 bis 2020 mit
  p = 0,082 nicht signifikant ist (Punkt 61); mit Lukas zu klären ist sie weiterhin.
- Der Stamp des Schritts `report` liegt als `site/index.html.stamp.json` in der Datenwurzel, also in der
  Stadtseite; dort gehört er hin. Im veröffentlichten Ordner ist er seit dem 2026-10-13 nicht mehr dabei:
  `georep publish` lässt `*.stamp.json` beim Kopieren aus, wie die rsync-Zeilen im Monitor-Skript.
- **Der OParl-Server liefert für Düsseldorf keine Urheberfelder, und das ist jetzt über die ganze Periode
  gemessen** (Vollabruf der Metadaten, 2026-10-14, 01:40 bis 02:16 in eine eigene Datenwurzel
  `data-vollabruf/`): 122 Seiten, 24 400 Paper gesehen, 19 109 im Zeitraum, **0 mit Urheberfeld**. Option 04
  leitet den Urheber darum weiter aus `paperType`, Titel und Textkopf ab (Deckung 98,3 %); die Quelle
  `oparl` greift ohne Codeänderung, sobald der Server liefert, und `georep fetch papers --max-pages 1`
  bleibt die billige Probe. Drei Nebenbefunde desselben Laufs:
  - **Ein Dokument mehr als die Referenz der Arbeit**: 19 109 statt 19 108. Es ist `KUA/023/2026`
    („Deutsche Oper am Rhein – Grundsatzbeschluss …", Datum 21.05.2025, Beschlussvorlage); die Nummer
    trägt 2026, das Dokument ist also nach dem Datenstand der Arbeit angelegt und ins Jahr 2025
    zurückdatiert worden. Kein Dokument der Referenz fehlt umgekehrt.
  - **`modified` ist brauchbar**: alle 19 109 tragen einen Zeitstempel, die Spanne reicht bis zum
    25.09.2026, und nur 1 200 tragen das Migrationsdatum 30.12.2024. Für diese Periode greift
    `modified_since` also — anders als für 2014 bis 2020, wo es das Migrationsdatum war (darum steht dort
    `incremental = false`).
  - **18 708 der 19 109 tragen `consultation`**, also die Beratungsfolge. Das ist die Quelle, aus der ein
    Gremium für die alte Nummernform zu holen wäre, wenn man die Organisations-IDs auflösen will
    (`docs/decisions.md`, Punkt 57, dort verworfen).
- Im Wahlbezirk 11 ist Die Linke nicht angetreten (0 Stimmen; die Stimmbezirks-CSV führt dort die 0, anderswo Dutzende). Der Abgleich Dokumentanteil gegen Stimmenanteil lässt solche Bezirke je Partei aus, Die Linke hat also n = 40 statt 41.
- Die Ergebnis-CSV der Ratswahl heißt im Open-Data-Portal inzwischen `…_Stimmbezirke_1.csv` (Datensatzseite am 2026-10-11); `profiles/duesseldorf.toml` zeigt auf `…_0.csv`, woher die Referenz stammt. Vor einem `fetch opendata` nachsehen.
- **Mönchengladbachs Ratsinformationssystem liefert nur 658 von 2 871 Hauptdateien aus** (gemessen am
  vollen Lauf vom 2026-10-13): die übrigen 2 213 antworten auf ihre `downloadfiles`-URL mit `404`. Der Abruf
  isoliert jeden Fehler und läuft durch, die Kette rechnet also mit 650 Texten; die Stadtseite sagt es in
  den Kernzahlen („Ratsdokumente 2 895, 650 mit Text, 2 245 ohne"). Jede absolute Zahl dieser Stadt ruht
  damit auf rund einem Viertel der Periode und ist mit Düsseldorf nicht der Höhe nach vergleichbar. Seit dem
  2026-10-14 sagen die Seiten das selbst (Review-Befund 1): der Städtevergleich führt die Spalte „davon mit
  Text" und nennt im Abschnitt „Vergleichbarkeit" je Stadt beide Zahlen, und die Kachel „Dokumente mit
  Treffer" jeder Stadtseite nennt zusätzlich den Anteil an den Dokumenten **mit Text** (Mönchengladbach
  489 von 650 = 75,2 %, nicht nur 16,9 % aller 2 895). Woran die 404 liegen, sagt der Server nicht.
- **Mönchengladbachs Straßen stimmen zu 88,8 % je Wahlbezirk mit dem amtlichen Verzeichnis überein**
  (2 667 Zuordnungen mit bekanntem Namen, 70,8 % im selben Stimmbezirk; gemessen am 2026-10-15 mit den
  Flächen des Wahltags). Vorher waren es **86,2 %** und **66,5 %** auf 2 651 Zuordnungen, gemessen am
  2026-10-13 mit dem Shapefile vom 08.06.2022. Gezählt werden Paare (Stimmbezirk, Name) und nicht
  Namen: 2 982 Paare über 1 814 verschiedene Namen, davon kennt das Verzeichnis 2 667 Paare mit
  1 563 Namen; die übrigen 315 Paare tragen 251 Namen, die es nicht führt. Die neuen Flächen heben die Zahl also um 2,6 bzw. 4,3 Prozentpunkte — und
  **nicht über die Grenze von 90 %**, die das Runbook nennt. Das Alter der Flächen war damit nicht der
  ganze Grund. Was bleibt, ist der Unterschied der Bezugsgrößen: das Verzeichnis ordnet eine Straße über
  **Adressen** genau einem Stimmbezirk zu, Overpass liefert sie über die **Geometrie** des Straßenzugs,
  und ein Zug über eine Bezirksgrenze zählt in beiden. Nachgerechnet am 2026-10-15: von den 2 667
  Zuordnungen weichen **300 (11,2 %, 248 verschiedene Namen)** im Wahlbezirk ab, und **alle 300**
  betreffen Namen, die Overpass in mehr als einem Wahlbezirk liefert, während das Verzeichnis nur
  bei **48** davon mehrere nennt -- die Abweichung sitzt also genau an den Bezirksgrenzen. Die 315 Namen, die das Verzeichnis gar nicht
  kennt (Fußwege, Plätze, neue Straßen), sind in beiden Messungen dieselben. Frage 1.3 ist beantwortet
  (Punkt 65); der Satz an `gdi@moenchengladbach.de` bleibt eine Bitte um eine Datei statt einer
  Operation, kein Hindernis.
- **Mönchengladbachs Paket und sein Profil nennen dieselben Flächen** (seit dem 2026-10-15,
  Punkt 65): `reference/moenchengladbach/external/Stimmbezirke_Kommunalwahl_2025.json` ist die
  `identify`-Antwort des Dienstes, das Zip von 2022 ist aus dem Paket entfernt. `georep pack` räumt
  **nicht** auf -- die alte Datei musste von Hand weg, und `tests/unit/test_data_packages.py` hätte
  es sonst gemeldet (die Prüfsummentabelle des READMEs passt dann nicht mehr zu den Dateien).
- Mönchengladbach (Option 01, 2026-10-12): der Marker `betrifft` kam in der PDF-Stichprobe in 0 von 5
  Dokumenten vor (alles Fraktionsanträge der laufenden Periode); ohne Marker durchsucht die Kette den ganzen
  Text. Der volle Lauf hat das nicht geändert, der Marker bleibt wirkungslos (Frage 1.5).
- Die votemanager-CSVs der ITK Rheinland tragen keine Lizenzangabe; die Seite nennt Quelle und Herausgeber und schreibt „Lizenz laut Anbieter nicht angegeben" (Frage 1.4).
- Mönchengladbachs Drucksachennummern tragen kein Kürzel des Gremiums (`0682/XI`; über alle 2 895 Nummern
  des vollen Laufs vom 2026-10-13 bestätigt, Body 0011). Das Profil lässt `bodies.reference_pattern` darum
  leer; der Abschnitt „Gremien" zeigt für diese Stadt 100 % „unbekannt". Woher das Gremium käme, bleibt das
  OParl-Feld `consultation` oder die Sitzungszuordnung (`docs/plans/01-staedte.md`, § 8, Frage 1.12).
- **Die Drucksachennummern der Periode 2014 bis 2020 tragen bis 2019 eine Amtsnummer statt eines
  Gremiumskürzels** (gemessen 2026-10-14 an `snapshots/2014-2020/raw/papers.jsonl`): 18 018 der 22 215
  Nummern haben die Form `<Amtsnummer>/ <Nummer>/<Jahr>` (`61/ 12/2014`), die 4 197 übrigen die heutige
  (`BV7/108/2019`, `RAT/270/2020`); der Wechsel liegt im Jahr 2019. Davon sind die zehn Köpfe `170` bis
  `179` eindeutig die Bezirksvertretungen (10 705 Dokumente): `[bodies.aliases]` im Stadtprofil übersetzt
  sie seit dem 2026-10-14 (`docs/decisions.md`, Punkt 57), und **unbekannt fällt von 18 070 auf 7 365**
  (81,3 % → 33,2 %), Bezirksvertretung steigt von 2 539 auf 13 244, die anderen Klassen bleiben. Belegt
  an den Dokumenttexten des Pakets: 9 999 von 10 008 (99,91 %) nennen die Bezirksvertretung des dritten
  Zeichens; die Gegenprobe mit dem heutigen Kürzel `BVn` derselben Periode trifft zu 99,89 %. Die 22
  echten Amtsnummern (7 313 Dokumente) bleiben unbekannt: jede zeigt in über 98 % der Fälle auf dieselbe
  `consultation`-Organisation, aber ein Amt ist kein Gremium, und ohne `raw/organizations.json`
  (Netzschritt) ist die Organisations-ID kein Name. Die Hauptperiode und die laufende Periode sind
  unberührt — dort trifft das Muster jede Nummer, und die Tabelle wird nur sonst befragt.
- **11 % der Urheber der Periode 2014 bis 2020 bleiben unbekannt** (2026-10-14, Punkt 60; vorher 56 %):
  2 122 der 9 601 Dokumente mit der Dokumentart `Vorlage aus der Politik` tragen das Wort „fraktion"
  nicht in ihrem Vorlagenkopf — es sind Jugendratsmitglieder, Einzelmandate und Listen des
  Integrationsrats —, dazu 135 `Antrag`, 96 `Anfrage` und 3 `zAnfrage Piraten`. Ein Personenmarker im
  Textkopf schließt die Lücke **nicht**: in 776 von 1 503 Fällen trifft er die Anrede („an herrn
  bezirksvorsteher") und nicht den Urheber. Die Seite dieser Periode zeigt den Anteil offen.
- **Piraten, REP, FWG und die Zentrumspartei haben keine Zeile in `[originators]`** (2026-10-14,
  Punkt 60): jedes Wort eines Parteimusters wird über `topics.stop_sources` zum Stoppwort des
  Themenmodells, und „alternative" und „deutschland" stehen in 518 und 587 Dokumenten der
  **Hauptperiode**. Drei Dokumente wären zu gewinnen, ein anderes Vokabular der Hauptseite wäre der
  Preis. Die 21 Piraten- und 12 REP-Dokumente sind ohnehin richtig als Person eingeordnet.
- **Der Schnappschuss `snapshots/2025/` veraltet mit jedem Lauf des Monitors**, und das ist in Ordnung: er
  ist der Erstabruf vom 2026-10-13 (4 095 Dokumente), GitHub Pages zeigt diesen Stand, und die Seite nennt
  ihr Abrufdatum selbst. Die aktuelle Fassung liefert der Timer auf kookaburra oder dem VPS — Konrads
  späterer Schritt. Neu gepackt wird der Schnappschuss nur von Hand (`snapshots/2025/README.md`).
- **Die Hauptseite hat mit beiden Periodenabschnitten nur noch 6,8 % Luft im Budget** (932 306 von
  1 000 000 Byte im veröffentlichten Ordner, 67 694 Byte Luft; gemessen 2026-10-14). Die Schätzung in
  `docs/seitengroesse-2026-10.md` lag bei rund 35 KB für „Zwei Wahlperioden" und damit **rund 10 KB zu
  niedrig**: gemessen sind es 45 417 Byte (41 Zeilen mit je sechs `data-value`, nicht hochrechenbar aus
  drei Bezirken der Mini-Periode). „Laufende Wahlperiode" kam mit 374 Byte genau hin, die Zeile „Weitere
  Städte" kostet 155. Rund 40 KB Reserve liegen gemessen in § 5 jenes Dokuments (doppelte SVG-Pfade der
  Parteikarten 28 KB, Suchindex 8 KB, Leerraum 4,4 KB); wer einen weiteren Abschnitt will, holt sie
  zuerst. Seit dem 2026-10-14 hängt die Zusage nicht mehr an einer Zeile: ein `slow`-Test baut die Seite
  und `georep publish --strict-budget` macht den Pages-Lauf rot (Review-Befunde 3 und 12).
- **Behoben am 2026-10-14** (Review-Befund 5): `pages.yml` fragte die Frische zuletzt mit dem
  Standardprofil ab und meldete nach dem Lauf des Vergleichsprofils jeden Schritt als „offen: Settings
  geändert" — der Fingerprint ist global (siehe unten), die Diagnose sagte also nichts. Jetzt läuft
  `georep status` je Profil, eine Zeile nach der anderen.
- **Das Budget der veröffentlichten Seite ist seit dem 2026-10-14 ein Gate** (Review-Befund 3):
  `georep publish --strict-budget` endet mit Exit 1, wenn eine veröffentlichte Seite über
  `report.page_budget_bytes` liegt, und `pages.yml` setzt den Schalter; von Hand bleibt es bei der Zeile.
  Gerechnet wird die Seite seitdem auch in einem Test: `tests/golden/test_published_page.py` (`slow`,
  33 s) baut die volle Referenz mit `snapshots/2014-2020` unter dem Profil `duesseldorf-vergleich` und
  hält `index.html` gegen das Budget — vorher prüften vier Tests das Budget, und keiner baute diese
  Kombination.
- Der Stadtbezirk Mönchengladbachs steckt im ersten Zeichen der Stimmbezirksnummer (`10401`: Stadtbezirk 1, Wahlbezirk 04, Stimmbezirk 01); das Profil liest ihn mit `columns.results.city_district_from_precinct`. Bestätigt ist die Regel bisher nur an der Fixture (Wahlbezirke 04, 09, 23) und an der Zahl der Stadtbezirke (vier); der volle Lauf prüft sie gegen die Wahlbezirks-CSV (`docs/plans/01-staedte.md`, § 8, Frage 1.13).

## Nächster Schritt

**Stand nach dem Merge von Punkt 65 (2026-10-15, `v0.14.0`):** alles aus der Runde vom 2026-10-14 liegt
auf `main` (Merge `1e3e409`, 34 Commits des Branches `feat/esri-identify`, zwei Reviews) und ist gepusht.
Offen und Konrads Entscheidung: ob die Grenze von 90 % im Runbook (§ 4) für Städte bleibt, deren
Verzeichnis über Adressen zuordnet; die drei lokalen Stamps „offen: Settings geändert" (`papers`,
`organizations`, `pdfs` Mönchengladbachs) bleiben alt, bis ein Abruf ohnehin ansteht; die lokale
Hauptseite braucht nach jedem Lauf des Hauptprofils die Kopie der Periodenseiten aus `pages.yml`
(siehe unten). Eine neue Ausbaurunde folgt dem Muster Meta-Plan, Supervisor, Unteragenten (Konrad,
2026-10-13: mittlere Priorität).

**Die Dokumentation steht seit dem 2026-10-14 in vier Sichten** (Konrads Auftrag, Branch `docs/sichten`): `docs/technik.md` (Schnittstellen, Kette, Veröffentlichung), `docs/inhalt.md` (Daten und Seite), `docs/statistik.md` (Auswertungen mit Einwänden), `docs/workflow-ratsmitglied.md` (Arbeitsablauf); das README verweist darauf, `docs/architecture.md` und `docs/decisions.md` sind unberührt.

**Phase 2 zu Punkt 65 ist durch** (2026-10-15): Mönchengladbach rechnet mit den Flächen des
Wahltags, und das Paket im Repo trägt sie. Der Weg dahin und was dabei herauskam:

| Schritt | Ergebnis |
|---|---|
| `fetch opendata` | 1 043 618 Byte, SHA-256 `c2d3de4b…4093b94` — byte- und prüfsummengleich mit der Recherche vom 2026-10-14 |
| `run shapes` | **179 Stimmbezirke in 33 Wahlbezirken**, EPSG:25832, **170,47 km²**, **25 187 Stützpunkte**, jede Fläche gültig |
| `run voters` | 33 Wahlbezirke, 204 219 Wahlberechtigte, 96 880 Wähler (unverändert; sie hängen am Wahlergebnis) |
| `fetch pois_wiki` | 1 190 per SPARQL, 1 029 per GeoSearch, 2 219 Einträge (vorher 2 373), 1 929 Orte nach der Bereinigung |
| `fetch streets_osm` | **179 Stimmbezirke, 2 982 Zuordnungen, 1 814 verschiedene Namen** (245,7 s im Durchlauf, der durchkam) |
| `run` bis `report` | 5 759 Begriffe, **1 682 Treffer** (vorher 1 704), 489 Dokumente mit Treffer (unverändert), Seite 3,2 MB |
| `pack --force` | 9 Dateien, 5 224 917 Byte (vorher 4 405 625); das Zip von 2022 von Hand entfernt |
| `publish --strict-budget` | 2 Städte, 1 Vergleich, 101 Dateien, 16,5 MB, Exit 0 |

**Overpass hat zwei Tage gekostet.** Vom 2026-10-14 15:58 bis zum 2026-10-15 09:13 wies
overpass-api.de fast jede Abfrage mit `504` ab (`Dispatcher_Client::request_read_and_idx::timeout`,
dabei vier freie Slots und derselbe Fehler für eine Trivialabfrage; zeitweise auch `502` und
`Connection refused`). Es lag **nicht** an den neuen Flächen: deren Polygone sind nach
`simplify_m = 2` praktisch gleich groß wie die von 2022 (Punkte je Fläche im Median 79 statt 75,
Maximum in beiden 368). Gerettet hat es der HTTP-Cache — sein Schlüssel ist Host, Methode und
Abfragetext, also setzte jeder Durchlauf auf dem vorigen auf, bis Durchlauf 130 alle 179 Abfragen
beisammen hatte. **Wer so etwas wieder fährt: nichts anfassen, was den Schlüssel ändert** (Endpunkt,
`query_timeout_s`, `simplify_m`), sonst beginnt das Sammeln von vorn.

**Die Falle, die der halbe Stand war**, ist damit weg: `raw/streets_per_district.json` ist der neue
Stand mit 179 Stimmbezirken, die vier Bezirke der Wahl, die im Shapefile von 2022 fehlten (`11006`,
`21406`, `32906`, `40106`), haben Straßen, und die fünf, die es nur 2022 gab, kommen nicht mehr vor.
Geprüft ist das an der Datei, am Wörterbuch und an der Seite.

**Was dabei offen bleibt:**

- **Die Übereinstimmung bleibt unter 90 %** (88,8 % je Wahlbezirk; siehe „Bekannt"). Ob die Grenze
  des Runbooks für eine Stadt, deren Verzeichnis über Adressen und deren Geometrie über Straßenzüge
  geht, überhaupt erreichbar ist, ist eine offene Frage an die Methode, nicht mehr an die Daten.
- **Drei Netzschritte stehen auf „offen: Settings geändert"** (`papers`, `organizations`, `pdfs`):
  die neuen Schlüssel in `[precincts]` haben den Settings-Fingerprint geändert, ihre Daten nicht.
  Ein erneuter Abruf kostet Stunden und brächte dieselben Dateien; ihre Stamps bleiben darum alt.
- **Düsseldorf ist nicht neu gerechnet.** `georep publish` baut den Vergleich aus den
  veröffentlichten Ordnern, nicht aus einem Lauf; die Hauptstadtseite ist der Stand vom 2026-10-13.
  In `data/duesseldorf/site/` fehlen dabei die Unterseiten `2014-2020/` und `2025/`, darum meldet
  `publish` 101 Dateien und nicht 187. **Das ist lokal und kein Schaden an der veröffentlichten
  Seite**: die beiden Periodenseiten entstehen nicht aus `publish` und nicht aus einem Lauf des
  Hauptprofils, sondern aus einer **Kopie**, die `.github/workflows/pages.yml` nach dem Lauf macht
  (`cp -r "$PERIOD" "$MAIN/$PROFILE"`). Jedes Periodenprofil hat seinen eigenen Ordner --
  `georep --profile duesseldorf-2014 paths` nennt `profile=2014-2020` und
  `site=data/2014-2020/site` --, und dort liegen beide Seiten vollständig (822 027 und 718 384
  Byte vom 2026-10-14). Der letzte Lauf des Hauptprofils hat seinen `site`-Ordner neu geschrieben
  und die Kopien damit entfernt; wer sie lokal wieder will, kopiert sie, statt etwas zu rechnen.


**Zuerst zu lesen: der Befundbericht zu den vier Netzläufen** (`docs/befunde-2026-10-14.md`, 2026-10-14).
Er sagt, was die Daten zeigen — die zwei Wahlperioden (Spearman der Trefferquoten 0,8106; die Regression
der Differenzen r = 0,1008, p = 0,53045; Tabelle 5 der alten Periode ohne 1 und 10 **p = 0,08211**, also
nicht signifikant), die zwei Städte, die laufende Periode (die ersten 13 Monate gleichen denen der
Hauptperiode), die **Beratungsfolge** aus dem Vollabruf (18 708 von 19 109 Dokumenten, 98,9 % Deckung mit
dem Gremium der Drucksachennummer; dieselbe Abbildung löst 7 010 der 7 365 unbekannten Gremien der alten
Periode auf) und die Datenqualität über alle vier Läufe. Sein § 6 nennt fünf Punkte, die Konrad
entscheiden könnte; sein § 4 den einen Vorschlag für den nächsten Schritt. Nachrechnen:
`uv run python docs/befunde-2026-10-14-messung.py`.

**Punkt 1 davon ist umgesetzt** (2026-10-14, `docs/decisions.md`, Punkt 58, oben „Die Beratungsfolge
als zweite Quelle des Gremiums"): „unbekannt" fällt in der alten Periode auf 7,4 %, in der
laufenden auf 0 % und in Mönchengladbach auf 44,0 %. Die 1,6 %, die der Befund für die alte Periode
schätzte, sind es **nicht** geworden — die 1 535 mehrdeutigen Folgen zählte er mit, und die
entscheiden nicht (siehe „Bekannt").

**Die Punkte 2, 3 und 4 sind am 2026-10-14 dazugekommen** (`docs/decisions.md`, Punkte 59, 60 und
61; oben je ein Abschnitt): Mönchengladbach zeigt Urheber und Parteien („unbekannt" 100 % → 0 %),
die Wahlperiode 2014 bis 2020 liest ihre Urheber aus `Verwaltungsvorlage` und dem Vorlagenkopf
ihrer Form („unbekannt" 55,9 % → 10,6 %), und die Spalte „ohne Ausreißer" von Tabelle 5 heißt im
Kopf „explorativ" und nennt daneben das p der anderen Periode. **Offen bleibt aus § 6 nur noch
Punkt 5**, die Anfrage an Mönchengladbach nach den Stimmbezirksflächen von 2025 (Konrads
Handgriff).

**Zwei Fremdzeilen-Bestände in Konrads Textstores** (Review-Befund 6, 2026-10-14): die Stores auf xtraspace
tragen noch, was beim Packen herausgefallen ist — `cache/moenchengladbach/text/texts.parquet` 663 Zeilen,
davon 5 mit `source = "stichprobe"`, und `cache/2014-2020/text/texts.parquet` 22 216, davon 100 mit
`source = "fixture"`. **Auf die Ergebnisse wirkt das nicht**: der Join im Schritt `corpus` lässt einen Text
ohne Paper fallen, und genau das sind sie. Nur `georep pack` verweigert den Store, solange sie drin liegen
(mit Zahl und Beispielen). Der Handgriff, wenn er je nötig wird:

```bash
uv run python - <<'EOF'
from pathlib import Path
from georep.stores import TextStore
for path in (
    Path("/media/konrad/xtraspace/georep/cache/moenchengladbach/text/texts.parquet"),
    Path("/media/konrad/xtraspace/georep/cache/2014-2020/text/texts.parquet"),
):
    store = TextStore(path)
    foreign = [n for n, r in store.rows.items() if r["source"] not in ("pdf", "reference")]
    for name in foreign:
        del store.rows[name]
    store.save()
    print(path, "entfernt:", len(foreign), "verbleibend:", len(TextStore(path)))
EOF
uv run georep --profile moenchengladbach status   # texts bleibt aktuell, der Stamp zählt die Eingaben
```

Danach rechnet die Kette `corpus` und alles dahinter einmal neu (dieselben Zahlen, ein anderer
Eingabe-Hash). Wer das nicht will, lässt die Zeilen liegen: die Pakete im Repo sind ohne sie gepackt.

**Ein Handgriff auf Konrads Rechner** (Punkt 52): die flachen Ordner der alten Hauptperiode wegräumen.
**Erst, wenn die Netzläufe unten durch sind** — der Lauf im Worktree auf `v0.12.0` liest und schreibt sie
noch. `data/duesseldorf/` und `data/site/` sind am 2026-10-13 gebaut, es ist also nichts nachzurechnen; PDFs
und Texte sind es wert, verschoben statt gelöscht zu werden (200 PDFs, ein Abruf kostet eine Sekunde pro
Datei, und die 200 Texte daraus hat die Referenz nicht).

```bash
# Die Pfade stehen in settings.local.toml; `uv run georep paths` zeigt sie.
DATA=/media/konrad/xtraspace/georep/data
CACHE=/media/konrad/xtraspace/georep/cache
rm -rf "$DATA"/{external,raw,interim,processed}                  # gerechnet wird unter duesseldorf/
rm -rf "$CACHE/duesseldorf/pdf"  && mv "$CACHE/pdf"  "$CACHE/duesseldorf/pdf"
rm -rf "$CACHE/duesseldorf/text" && mv "$CACHE/text" "$CACHE/duesseldorf/text"
uv run georep status                    # zeigt, was danach noch zu laufen hat
```

Beide Ordner tragen ihre Stamps (`pdf/manifest.jsonl.stamp.json`, `text/texts.parquet.stamp.json`), sie
ziehen also mit um. Was der nächste Lauf danach tut: `pdfs` steht auf „offen: Settings geändert" (`--limit
200` steht in diesem Stamp), `texts` auf „aktuell", solange die PDFs daneben liegen — und weil der
verschobene Store drei Texte aus eigener Extraktion trägt, rechnet die Kette `corpus` und alles dahinter
einmal neu (23 s): dieselben Zahlen, drei andere Texte (siehe „Bekannt"). Wer das nicht will, löscht
`$CACHE/text` statt es zu verschieben; dann steht der Store der Referenz schon im neuen Ordner, und nur
`$CACHE/pdf` zieht um. `data/site/` bleibt in beiden Fällen, wie `georep publish` es gelegt hat.

Wer von vorn anfängt (frischer Klon, anderer Rechner), hat keinen Handgriff — `bootstrap` und `run` legen den
Ordner selbst an.

**Konrads Läufe sind durch** (2026-10-13), und ihre Daten liegen als Pakete im Repo (oben, Punkt 56); der
Pages-Workflow baut damit jeden Teil der Seite (`.github/workflows/pages.yml`, Pages-Quelle „GitHub
Actions"). Erledigt:

1. Periode 2014 bis 2020: 22 215 Dokumente, 22 116 PDFs, 21 838 mit Text, 36 324 Treffer, 77 Monate →
   `snapshots/2014-2020/` und die Abschnitte „Zwei Wahlperioden".
2. Mönchengladbach: 2 895 Dokumente, 658 PDFs (die übrigen `404`), 1 704 Treffer über 33 Wahlbezirke →
   `reference/moenchengladbach/` und `vergleich.html` aus `georep publish`. **Seit dem 2026-10-15 sind
   es 1 682 Treffer** (Punkt 65, die Flächen des Wahltags); die Zahl der Dokumente mit mindestens einem
   Treffer bleibt **489**, die Kachel der Seite also unverändert.
3. Erstabruf der laufenden Periode: 4 095 Dokumente, 4 088 PDFs, 5 448 Treffer, 14 Monate →
   `snapshots/2025/` und die Unterseite `2025/`.

Offen bleibt daran:

- **Der Timer** auf kookaburra oder dem VPS, der die laufende Periode fortschreibt (`deploy/README.md`,
  Installation und Erstabruf sind beschrieben, der Trockenlauf ist gelaufen). Bis dahin zeigt die
  veröffentlichte Seite den Stand des Schnappschusses vom 2026-10-13.
- **VPS und Domain** später, kein R2-Bucket (Konrads Antworten vom 2026-10-13 auf 7.1 und 7.4).
- Nichts mehr am **Vollabruf der Metadaten der Hauptperiode**: er ist am 2026-10-14 um 02:16 mit Exit 0
  durchgelaufen (36 min, Worktree `…/georep/worktrees/netzlauf`, Log
  `…/georep/logs/netzlauf-2026-10-13.log`, Daten in `…/georep/data-vollabruf/`). Seine drei Befunde stehen
  oben unter „Bekannt"; die Datenwurzel kann weg, sobald Konrad sie nicht mehr ansehen will.
- **Die Anfrage an Mönchengladbach** nach den Stimmbezirksflächen von 2025 (Frage 1.3) ist **erledigt**
  (2026-10-15, Punkt 65) und war keine Anfrage: die Flächen des Wahltags sind öffentlich, nur nicht als
  Datei. Die Übereinstimmung stieg damit auf 88,8 % je Wahlbezirk und bleibt unter der Grenze des
  Runbooks -- der Rest liegt an den Bezugsgrößen, nicht am Alter der Flächen (siehe „Bekannt").

Der Rückstand `docs/todo.md` ist abgearbeitet (`v0.12.0`): Punkt 4, Bartzschs Methodik, am 2026-10-12
(`docs/methodik-review-2026-10.md`, Regeln in `docs/decisions.md`, Punkte 43 und 44); Punkt 1, das Themenmodell,
am 2026-10-12 (`docs/themenmodell-2026-10.md`, offene Annahmen in dessen § 7); Punkt 3, die Skalierung der
Kennzahlen, am 2026-10-13 (`docs/skalierung-2026-10.md`, § 8); Punkt 5, die Literaturübersicht, am 2026-10-13
(Punkt 47; Titel der Arbeit und die Kölner Untersuchung sind nachzutragen); Punkt 2, die Seitengröße, am
2026-10-13 (`docs/seitengroesse-2026-10.md`, § 8); Punkt 6, die Lizenz, am 2026-10-12 (Punkt 42).
Die acht wichtigsten Fragen aus `docs/plans/fragen.md` hat Konrad am 2026-10-13 beantwortet; umgesetzt sind
davon der Umzug nach `data/duesseldorf/` (Frage 1.7, Punkt 52, am 2026-10-13) und die Datenpakete im Repo
(Fragen 1.2, 2.1, 3.3 und, für die laufende Periode, 7.4; Punkt 56, am 2026-10-14). Offen bleibt der VPS samt Domain, später. Zurückgestellt (`docs/plans/00-synergien.md`, § 8): Fingerprint je Schritt. Außerdem offen,
wenn jemand es will: ein Ersatz für FlashText oder pypdf nur nach neuer Messung (`docs/decisions.md`, Punkt 14);
die beiden deal-Eigenheiten upstream melden; die Abweichung in Tabelle 5 „ohne Ausreißer" mit Lukas klären.
