# Status

Stand 2026-10-14, `main` auf `v0.12.0`: der Rückstand nach dem Ausbau (`docs/todo.md`, sechs Punkte) ist
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
  `georep publish` nennt jede veröffentlichte Seite darüber. 886 328 von 1 000 000 Byte, also
  113 672 Byte Luft (11,4 %) — sie trug den Abschnitt „Zwei Wahlperioden" (geschätzt rund 35 KB),
  der am 2026-10-14 mit den Datenpaketen dazugekommen ist (zusammen mit „Laufende Wahlperiode"
  45 946 Byte, Seite 932 274, noch 6,8 % Luft). Dafür sind die `<title>` der 1196 Orte gefallen (73 842 Byte;
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
auf die Fragen 1.2, 2.1 und 3.3 („können so erstmal ins Repo, ist ja alles relativ klein") ist damit
umgesetzt.

| Paket | Bytes | Inhalt | Profil |
|---|---|---|---|
| `reference/moenchengladbach/` | 3 980 958 | `external/` (4), `raw/` (3), `cache/text/texts.parquet` | `moenchengladbach` |
| `snapshots/2014-2020/` | 37 875 851 | `external/` (4), `raw/papers.jsonl`, Textstore | `duesseldorf-2014` |
| `snapshots/2025/` | 13 894 254 | `external/` (2), `raw/papers.jsonl`, Textstore | `duesseldorf-2025` |

Zusammen 53,2 MiB neben `reference/` (81,8 MiB) und `context/` (2,1 MiB), also 137,1 MiB in fünf Paketen.
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
  187 Dateien, 34,6 MB" und `PublishSummary.over_budget` ist leer.

## Zahlen (2026-10-14, `v0.11.0` plus Punkt 44, 45, 46, 47, 52 und 56)

- Tests: 1106 schnelle (nox-Gate, parallel in rund 51 s, Abdeckung 98,4 %), 28 `slow` (3 min 9 s über die
  volle Referenz und die drei Datenpakete), 17 `bench` (grün gegen die Baseline), 4 `network` (nur von
  Hand). Alle drei am 2026-10-14 mit Exit 0 gelaufen.
- Register: 29 Schritte; `georep steps` zeigt 27 für Düsseldorf, 28 mit Vergleich, 22 im Periodenprofil
  2014 bis 2020, 21 in der laufenden Periode, 22 für Mönchengladbach. Voller Offline-Lauf auf der Referenz
  rund 23 s (Themenmodell 7,4 s, passender Ausschuss 6,5 s, Index 4,2 s, Berichtsseite 1,7 s, Kennzahlen
  0,1 s).
- Berichtsseite: `index.html` der Hauptseite 932 274 Bytes (Budget 1 000 000, **6,8 % Luft**) mit beiden
  Periodenabschnitten, 55 Dateien zusammen 13,2 MB; ohne die Abschnitte „Zwei Wahlperioden" und „Laufende
  Wahlperiode" sind es 886 328 Bytes (die beiden Umschalter kosten 110 KB, die Literaturübersicht 13,2 KB,
  die Vorschau langer Tabellen 4,1 KB, `begriffe.json` liegt mit 96 KB daneben). Siebzehn Abschnitte in
  Nummernfolge (kernzahlen, suche, karte, zusammenhang, kontrollvariablen, gewichtung, perioden,
  parteien, wahlbezirke, gremien, begriffe, monate, methode, abgeleitete-daten, literatur, downloads,
  laufend). Die Unterseiten: `2014-2020/` 818 486, `2025/` 717 246, `moenchengladbach/` 641 633,
  `vergleich.html` 88 979 Bytes.
- Quelltext: 59 Python-Dateien unter `src/`, rund 16 600 Zeilen; fünf Profile im Paket.
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
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab (`docs/baseline-2026-10-10.md`).
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
  damit auf rund einem Viertel der Periode und ist mit Düsseldorf nicht der Höhe nach vergleichbar; der
  Städtevergleich sagt das im Abschnitt „Vergleichbarkeit". Woran die 404 liegen, sagt der Server nicht.
- **Mönchengladbachs Straßen stimmen nur zu 86,2 % je Wahlbezirk mit dem amtlichen Verzeichnis überein**
  (2 651 bekannte Namen, 66,5 % im selben Stimmbezirk; gemessen 2026-10-13). Die Grenze des Runbooks ist
  90 %, also ist Frage 1.3 fällig: die Flächen stammen aus dem Datensatz „Wahlen" vom 08.06.2022, die Wahl
  war am 14.09.2025. Gerechnet wird je Wahlbezirk, kleine Neuzuschnitte innerhalb eines Bezirks fallen
  heraus; der Satz an `gdi@moenchengladbach.de` steht aus (Konrads Handgriff).
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
- **56 % der Urheber der Periode 2014 bis 2020 bleiben unbekannt**: die Dokumentart heißt dort in 9 601 von
  22 215 Fällen `Vorlage aus der Politik` und nennt keine Fraktion, während die Hauptperiode `Antrag CDU`,
  `Anfrage SPD/Volt` und so weiter führt (39 Dokumentarten in jeder Periode, aber andere). Die Muster in
  `[originators]` beschreiben die heutige Benennung; eigene für die alte wären eine neue Messung am Textkopf
  und sind nicht gebaut (`docs/plans/04-parteien.md`). Die Seite dieser Periode zeigt den Anteil offen.
- **Der Schnappschuss `snapshots/2025/` veraltet mit jedem Lauf des Monitors**, und das ist in Ordnung: er
  ist der Erstabruf vom 2026-10-13 (4 095 Dokumente), GitHub Pages zeigt diesen Stand, und die Seite nennt
  ihr Abrufdatum selbst. Die aktuelle Fassung liefert der Timer auf kookaburra oder dem VPS — Konrads
  späterer Schritt. Neu gepackt wird der Schnappschuss nur von Hand (`snapshots/2025/README.md`).
- **Die Hauptseite hat mit beiden Periodenabschnitten nur noch 6,8 % Luft im Budget** (932 274 von
  1 000 000 Byte, gemessen 2026-10-14). Die Abschätzung in `docs/seitengroesse-2026-10.md` lag bei rund
  35 KB für „Zwei Wahlperioden"; zusammen mit „Laufende Wahlperiode" sind es 45 946 Byte. Rund 40 KB
  Reserve liegen gemessen in § 5 jenes Dokuments (doppelte SVG-Pfade der Parteikarten 28 KB, Suchindex
  8 KB, Leerraum 4,4 KB), falls ein weiterer Abschnitt dazukommt.
- **`pages.yml` endet mit `georep status`, und der sagt seitdem für jeden Schritt „offen: Settings
  geändert"**: die Hauptseite baut zuletzt das Profil `duesseldorf-vergleich`, dessen Settings-Fingerprint
  ein anderer ist als der des Standardprofils, mit dem `status` läuft. Der Fingerprint ist global (siehe
  unten), die Zeile ist eine Diagnose und kein Gate; der Schritt endet mit Exit 0.
- Der Stadtbezirk Mönchengladbachs steckt im ersten Zeichen der Stimmbezirksnummer (`10401`: Stadtbezirk 1, Wahlbezirk 04, Stimmbezirk 01); das Profil liest ihn mit `columns.results.city_district_from_precinct`. Bestätigt ist die Regel bisher nur an der Fixture (Wahlbezirke 04, 09, 23) und an der Zahl der Stadtbezirke (vier); der volle Lauf prüft sie gegen die Wahlbezirks-CSV (`docs/plans/01-staedte.md`, § 8, Frage 1.13).

## Nächster Schritt

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
   `reference/moenchengladbach/` und `vergleich.html` aus `georep publish`.
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
- **Die Anfrage an Mönchengladbach** nach den Stimmbezirksflächen von 2025 (Frage 1.3): mit 86,2 %
  Übereinstimmung je Wahlbezirk liegt die Stadt unter der Grenze des Runbooks.

Der Rückstand `docs/todo.md` ist abgearbeitet (`v0.12.0`): Punkt 4, Bartzschs Methodik, am 2026-10-12
(`docs/methodik-review-2026-10.md`, Regeln in `docs/decisions.md`, Punkte 43 und 44); Punkt 1, das Themenmodell,
am 2026-10-12 (`docs/themenmodell-2026-10.md`, offene Annahmen in dessen § 7); Punkt 3, die Skalierung der
Kennzahlen, am 2026-10-13 (`docs/skalierung-2026-10.md`, § 8); Punkt 5, die Literaturübersicht, am 2026-10-13
(Punkt 47; Titel der Arbeit und die Kölner Untersuchung sind nachzutragen); Punkt 2, die Seitengröße, am
2026-10-13 (`docs/seitengroesse-2026-10.md`, § 8); Punkt 6, die Lizenz, am 2026-10-12 (Punkt 42).
Die acht wichtigsten Fragen aus `docs/plans/fragen.md` hat Konrad am 2026-10-13 beantwortet; umgesetzt sind
davon der Umzug nach `data/duesseldorf/` (Frage 1.7, Punkt 52, am 2026-10-13) und die Datenpakete im Repo
(Fragen 1.2, 2.1, 3.3, Punkt 56, am 2026-10-14). Offen bleibt der VPS samt Domain, später. Zurückgestellt (`docs/plans/00-synergien.md`, § 8): Fingerprint je Schritt. Außerdem offen,
wenn jemand es will: ein Ersatz für FlashText oder pypdf nur nach neuer Messung (`docs/decisions.md`, Punkt 14);
die beiden deal-Eigenheiten upstream melden; die Abweichung in Tabelle 5 „ohne Ausreißer" mit Lukas klären.
