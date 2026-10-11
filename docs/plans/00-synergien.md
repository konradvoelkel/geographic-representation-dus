# Synergien der acht Pläne

Stand 2026-10-12, geschrieben vom Supervisor nach Lesen aller acht Pläne (`01-staedte.md` bis `08-suche.md`,
je auf dem Branch `feat/NN-name`). Meta-Plan: [../plan-ausbau-2026-10.md](../plan-ausbau-2026-10.md), § 5
Phase 2. Dieses Dokument nennt die gemeinsamen Bausteine, die Konflikte und ihre Auflösung, das Fundament, das
vorab auf `main` kommt, die Merge-Reihenfolge und die Regeln, die in Phase 3 für alle gelten. Was sich je Plan
ändert, steht kurz in § 7 und ausführlich in § 10 des jeweiligen Plans.

Umfang der acht Pläne zusammen: rund 160 Agentenstunden, 100 bis 120 Commits, zwölf neue Pipeline-Schritte,
rund zwanzig neue veröffentlichte Tabellen, sieben neue Seitenabschnitte, drei Unterseiten (Periode 2014 bis
2020, Profil 2025, Städtevergleich). Kein Plan braucht mehr Netz als die erlaubte Stichprobe; vier Pläne
bereiten einen Lauf vor, den Konrad startet (01, 02, 04 optional, 07).

## 1. Gemeinsame Bausteine

| Baustein | Wer braucht ihn | Wer hat ihn geplant | Auflösung |
|---|---|---|---|
| **Abschnittsmechanismus der Berichtsseite**: Vorlage als Rahmen plus eine Datei je Abschnitt, Reihenfolge über Nummern; Basis-JavaScript mit einer Schnittstelle (`georep.select`, `georep.showDocuments`); Umschalter der Karte generisch über `data-class-<kennzahl>` | 02, 03, 04, 05, 06, 07, 08 (alle Seitenoptionen) | 08 (§ 6, ausgearbeitet), 05 (generischer Umschalter), 04 und 02 (optionale Abschnitte mit `{% if %}`) | **Fundament F1** |
| **Register der veröffentlichten Tabellen** (Name, Pfad, Beschreibung, Spaltendoku, CSV-Regeln an einer Stelle) | 02, 03, 04, 05, 06, 07 (je drei bis vier neue Tabellen) | 06, 03 (vorgeschlagen), 04 | **Fundament F2**: `report/tables.py` ersetzt `published_tables`, `COLUMN_DOCS`, `DESCRIPTIONS`, `csv_plan` |
| **Regression je Kennzahlvariante** (`regression_pair` mit Spaltenname und Ausreißerliste) und `analysis.exclude_districts` in den Settings statt `OUTLIERS = (1, 10)` | 03, 05, 06, 01, 02 | 06 (Umzug nach `analysis/regression.py`), 01 (Ausreißer je Profil), 03 (OLS daneben) | **Fundament F3** |
| **Profil** (eine Datenwurzel je Stadt oder Periode unter `data_root/<profil>/`, Cache je Profil, offenes Periodenende, Wahltag getrennt vom Periodenende) | 01, 02, 07 | 01 (`profile` als Slug mit Paketprofilen), 02 (`period.name`), 07 (`profile`, `Period.end` optional, `Period.election`) | **Fundament F4**: ein Schlüssel `profile`; Paketprofile und `--profile` bleiben Option 1 |
| **Umrechnung von Gebietseinheiten auf Wahlbezirke** (`georep/crosswalk.py`) | 02 (Stimmbezirke 2020 auf Wahlbezirke 2025), 03 (Sozialräume und Stadtteile), 05 (Stadtbezirke), 08 (Stadtteile als Sucheinträge, später) | 02, 03, 05 je eigenes Modul | **Fundament F5**: ein Modul mit dem Attribut-Crosswalk (`unit_weights`) und dem Vertragsprädikat; 03 baut `area_shares`, 02 ergänzt `target_weights`, `transfer_counts`, `largest_remainder` |
| **Attribute je Dokument** (eine Zeile je Korpus-ID): Urheber (04), Gremium (05), Dokumentart-Gewicht (06) | 04, 05, 06 | 04 (`dokumente_urheber`), 05 (`papers_gremien` mit `herkunft`), 06 (Regeln auf `paper_type`) | Konvention (§ 5.6): Schlüssel `id`, eine Zeile je Korpus-ID, keine gemeinsame Datei. **04 besitzt die Urheberklasse**, 05 streicht `herkunft` |
| **OParl-Vertrag und `PaperRecord`** erweitern: Urheberfelder (04), `consultation`-Organisationen (05 später, 04 nimmt sie mit), Gelöschte (07), Startseite und Fortschritt (02) | 02, 04, 05, 07 | 04, 07, 02 | ein Schema-Sprung des Korpus (2 auf 3) in 04; 07 und 02 bauen darauf (Merge-Reihenfolge) |
| **Achsen-Helfer der Diagramme** (`charts._axes` aus `scatter` herausgezogen) | 02 (`delta_scatter`), 03 (Added-Variable-Plots), 07 (Balken) | 02, 03 je als Refactoring | **Fundament F7** (reines Refactoring, Ausgabe byteidentisch) |
| **Zählende Tests** („9 ausgeführt", `len(offline) == 9`, „15 Dateien") | alle mit Schritten oder Tabellen | alle merken es als Konflikt an | **Fundament F6**: Zahlen aus `build_steps` und dem Register ableiten |
| Kleine Karten per `<defs>` und `<use>` | 04 (sechs Parteikarten), 01 (Städtevergleich) | 04 | 04 baut `party_maps`; 01 nutzt dasselbe Muster, wenn 04 gemerged ist |
| `fetch papers --max-pages N` als Probe und Zähler im `FetchReport` | 01, 02, 04, 07 | 04, 01 | 04 baut es (`max_pages` in `OparlSource`), die anderen nutzen es |
| `raw/organizations.json` (`OparlOrganization`, `classification`) | 04, 05 (Gremiennamen) | 04 | 04 baut es; 05 nennt in den Settings die Namen aus der einen Seite vom 2026-10-11 und kann sie später daraus ersetzen |
| Dokumentdialog mit mehreren Begriffen und weiteren Feldern | 08 (Vereinigung der Schreibweisen), 04 (Urheber im Dialog), 05 (Gremium) | 08, 04 | F1 gibt `showDocuments(terms, title)`; Felder in `dokumente.json` hängt 04 an (`FIELDS` wächst), 05 darf ein weiteres anhängen |

## 2. Konflikte und ihre Auflösung

Dieselben Dateien berühren fast alle Pläne. Die Auflösung ist je Datei eine Regel, damit Konflikte beim
Rebase mechanisch bleiben:

| Datei | Wer | Regel |
|---|---|---|
| `src/georep/defaults.toml` | 01, 02, 03, 04, 05, 06, 07 | Neue Tabellen **am Ende der Datei** in einem Block mit Kopfzeile `# --- Option NN: <Name>`; jede Zahl mit Kommentar. Nur 01 darf vorhandene Zeilen verschieben (stadtneutrales `defaults.toml`), darum merged 01 spät |
| `src/georep/settings.py` | dieselben | Neue Modelle **vor** `class Settings`, neue Felder **am Ende** von `Settings` (nach `search`), je mit Kommentar `# Option NN`; Validatoren beim Modell. Pfade und reine Anzeigewerte aus dem Fingerprint ausschließen, alles andere zählt |
| `src/georep/layout.py` | 01, 02, 03, 04, 05, 06, 07 | Neue Properties **am Ende** der Klasse vor `runtime_dirs`, Block mit Kommentar `# Option NN`. `Layout` bekommt mit F4 ein viertes Feld `profile: str = ""`; weitere Felder nur mit Default am Ende (03: `context_root`) |
| `src/georep/pipeline.py` `build_steps` | 01, 02, 03, 04, 05, 06, 07 | Innere Funktionen und `Step`-Einträge an der Stelle ihrer Abhängigkeit, je Option ein Kommentar `# --- Option NN` über der Funktion und über dem Eintrag; keine Umsortierung fremder Schritte. Der Schritt `report` bekommt seine neuen Eingaben **am Ende** seines Tupels |
| `src/georep/report/model.py` | alle Seitenoptionen | Neue dataclasses vor `ReportModel`, neue Felder **am Ende** von `ReportModel` mit Default (`None` oder leeres Tupel), Füllung am Ende von `build_report_model`; Spaltendoku und Tabellen nur über F2 |
| `src/georep/report/tables.py` (F2) | 02, 03, 04, 05, 06, 07 | Je Option **ein** `append`-Block am Ende der Liste `TABLES`, Kommentar `# Option NN` |
| `src/georep/report/templates/` (F1) | alle Seitenoptionen | Neue Abschnitte sind **neue Dateien** `sections/NN-name.html.j2` (plus `.css`, `.js`); vorhandene Abschnitte ändert nur, wer muss (05: `20-karte`, 01: Rahmen, 02 und 07: Rahmen für Periodentexte). Nummern in § 5.1 |
| `tests/unit/__snapshots__/test_cli.ambr` (`georep steps`) | alle mit Schritten | Jede Option erneuert den Snapshot in ihrem Branch bewusst (Diff im Commit); beim Merge rendert der Supervisor ihn neu und liest den Diff. Nie `--snapshot-update` ohne Diff |
| `tests/unit/test_cli.py`, `tests/golden/test_pipeline.py`, `tests/unit/test_report_build.py` | alle | F6 nimmt die Literale heraus; Optionen ergänzen eigene Erwartungen in **eigenen Tests**, nicht in den gemeinsamen Zeilen |
| `docs/architecture.md`, `decisions.md`, `README.md`, `CHANGELOG.md`, `STATUS.md` | alle | Jede Option schreibt in ihren Branch; Konflikte sind Textkonflikte, der Supervisor löst sie beim Merge. CHANGELOG: je Option ein Absatz unter „Unreleased", neueste oben. `decisions.md`: Nummern vergibt der Supervisor beim Merge (die Pläne schreiben „Punkt 21", das wird je nach Reihenfolge 21 bis 29) |

Inhaltliche Konflikte, entschieden:

1. **Urheber gegen Herkunft** (04 `urheber_art` mit fünf Klassen, 05 `herkunft` mit vier): 04 besitzt die
   Klassifikation; 05 streicht `herkunft` und die drei Herkunftsregeln aus seinem Plan. 06 behält seine
   Regex-Regeln auf `paper_type` (sie liefern Gewichte, keine Klassen).
2. **Profilname**: `profile` (07, 01) statt `period.name` (02). Ein Schlüssel, ein Verzeichnis
   `data_root/<profil>/`, Cache `cache_root/<profil>/pdf` und `…/text` (02 wollte nur den Textstore trennen,
   01 auch die PDFs wegen gleicher Dateinamen je Body; die Trennung beider Caches je Profil deckt beides).
   Düsseldorfs Hauptperiode bleibt `profile = ""`, also flach wie heute (01, Frage 7, bleibt offen).
3. **Paketprofile** (`src/georep/profiles/<slug>.toml`, `--profile`): bleiben Option 1. In Phase 3 liegen
   `settings.2014.toml` (02) und `settings.2025.toml` (07) an der Repo-Wurzel und werden mit `--settings`
   geladen; nach dem Merge von 01 zieht 07 sein Profil in das Paketverzeichnis (02 ist dann schon gemerged;
   01 übernimmt den Umzug von `settings.2014.toml` in seiner Stufe A als eigenen Commit).
4. **Crosswalk**: ein Modul `georep/crosswalk.py`. F5 liefert `unit_weights` (Gewichte je Wahlbezirk und
   Einheit aus einer Spalte je Stimmbezirk, etwa Wahlberechtigte) und das Prädikat `sums_to_one`. 05 nutzt
   `unit_weights` für Stadtbezirke. 03 baut `area_shares(sources, targets, *, min_coverage)` und
   `district_weights`; 02 (merged nach 03) nutzt `area_shares` und ergänzt `assign_by_point`, `target_weights`,
   `transfer_counts`, `largest_remainder`. 03 legt `area_shares` so an, wie 02 es braucht: Rückgabe
   `source_id` String, `target_id` Int64, `share` Float64, `coverage` Float64, Anteile auf die Schnittsumme
   normiert, `SchemaError` unter `min_coverage`.
5. **Kanonische Spaltennamen der Wählertabelle** (02, 01): `Wahlberechtigte_insgesamt`, `Waehler`,
   `<Partei>_Stimmen` bleiben die Namen der Arbeit; Quellspalten werden beim Lesen umbenannt (02 für 2020, 01
   für votemanager). 02 merged vor 01 und baut die Umbenennung in `prep/voters.py`; 01 erweitert sie um die
   Legende `D1…Dn`.
6. **Reihenfolge der Seitenabschnitte** nach „Trefferquote und Wahlbeteiligung": erst die Erweiterungen der
   Regression (03 Kontrollvariablen, 06 Gewichtung), dann der Periodenvergleich (02), dann die Parteien (04),
   dann die Tabelle je Wahlbezirk, dann die Gremien (05). Nummern in § 5.1.
7. **Seitenbudget**: die Summe der Schätzungen (08: +150 KB, 04: +80, 03: +65, 02: +45, 06: +20, 05: +20,
   07: +20) bringt `index.html` von 686 KB auf rund 1,1 MB, unter 1,5 MB. Keine weitere Unterseite nötig;
   die geplanten Unterseiten (02: `2014-2020/`, 07: `2025/`, 01: `vergleich.html` und `<slug>/`) bleiben.
   Reserve, falls es knapp wird: die `<title>`-Elemente der 1309 Orte im Karten-SVG (rund 60 KB) durch den
   Tooltip ersetzen (betrifft `charts.py`, entscheidet der Supervisor beim Merge).
8. **Pages-Workflow**: 02 und 01 erweitern `pages.yml` (zweite Periode, `publish`); 07 nicht. Reihenfolge
   der Merges deckt das; der Supervisor prüft nach jedem Merge, dass der Workflow aus der Referenz ohne
   Netz baut.
9. **Fingerprint**: jede Option, die Settings-Schlüssel ergänzt, macht einmalig alle Stamps ungültig
   (7 s Neulauf). Hinzunehmen; steht im CHANGELOG der Sammelversion. Ein Fingerprint je Schritt (06,
   Vorschlag) ist zurückgestellt (§ 8).
10. **Geteilter `cache_root` in Phase 3**: `TextStore.save` schreibt die ganze Datei. Kein Unteragent schreibt
    in `cache_root/text/texts.parquet` außer über `bootstrap` (idempotent, gleicher Inhalt). Wer extrahiert
    oder simuliert (07), nutzt ein Profil (eigener Cache unter `cache_root/<profil>/`) oder einen eigenen
    `cache_root` in `settings.local.toml`.

## 3. Fundament auf `main`

Klein, getestet, mit Vertrag, mit Eintrag in `decisions.md`; je Punkt ein bis zwei Commits, `nox` grün, die
Ausgaben der Kette byteidentisch (Golden Master), die Seite inhaltlich gleich (Snapshot der Download-Tabelle,
Render-Tests). Danach werden alle acht Branches auf `main` rebased.

### F1 Abschnittsmechanismus und Basis-JavaScript

- `templates/report.html.j2` wird Rahmen: `<head>` mit dem Basis-CSS, Kopf, `<main>` mit den Abschnitten in
  Nummernfolge, Fuß, Dialog, Tooltip, Basis-JavaScript. Die Abschnitte liegen in `templates/sections/`:
  `10-kernzahlen`, `20-karte`, `30-zusammenhang`, `40-wahlbezirke`, `50-begriffe`, `60-methode`,
  `70-downloads`, je `NN-name.html.j2`; daneben optional `NN-name.css` und `NN-name.js`, die der Rahmen in
  den `<style>`-Block beziehungsweise in einen eigenen `<script>`-Block nach dem Basis-Skript einfügt.
  `render.py` listet das Verzeichnis über `importlib.resources`, sortiert nach Namen. Makros (`term`) liegen in
  `templates/macros.html.j2` und werden je Abschnitt importiert.
- Basis-JavaScript: `select(ids, scroll)` nimmt eine Zahl, ein Array oder `null`, `scroll` ist standardmäßig
  wahr; `showDocuments(terms, title)` vereinigt die Indizes mehrerer Begriffe (aufsteigend, Dokumente sind
  neueste zuerst); `window.georep = {select, showDocuments, rows}` als Schnittstelle für Abschnitts-Skripte.
  Der Umschalter der Karte liest `data-class-<kennzahl>` je `<path>` und blendet `#legend-<kennzahl>` ein;
  eine neue Kennzahl ist ein Radio mit `value`, ein Attribut je Pfad und eine Legende. `choropleth` bekommt
  dafür `extra_classes: Mapping[str, Classification]`.
- Budget: der slow-Test prüft `index.html` unter 1 500 000 Byte (bisher 3 000 000).
- Verträge: `render_report` behält die Nachbedingungen (Doctype, `lang="de"`, nur erlaubte Links); neu: die
  Liste der Abschnitte ist nicht leer und jede Nummer eindeutig.
- Tests: Render-Tests wie heute; neu ein Test, dass die Abschnittsdateien in Nummernfolge im HTML stehen und
  dass eine `.js`-Datei ohne `.html.j2`-Geschwister ein Fehler ist. Browser-Prüfung der Grundfunktionen
  (Klick, Umschalter, Dialog, Sortierung) nach § 8.4 des Meta-Plans vor dem Commit.

### F2 Register der veröffentlichten Tabellen

- `report/tables.py`: `PublishedTable(name, path: Callable[[Layout], Path], description, columns:
  Mapping[str, tuple[str, str]], joins: Mapping[str, str], separator: str, optional: bool = False)`; die Liste
  `TABLES` mit den sechs heutigen Tabellen in heutiger Reihenfolge, dazu `GEOJSON_COLUMNS` für
  `wahlbezirke.geojson`. Funktionen: `published(layout) -> list[PublishedTable]` (ohne die optionalen, deren
  Datei fehlt), `csv_plan(layout)` (für `georep export`, enthält weiter `wikidata_agg`, das nicht veröffentlicht
  wird), `column_docs(layout)`.
- `model.py` behält `ColumnDoc`, `column_docs` ruft das Register; `COLUMN_DOCS` und `published_tables`
  verschwinden; `build.py` liest Beschreibungen aus dem Register; `export.py` ruft `tables.csv_plan`.
- Vertrag: Namen eindeutig, jede Tabelle dokumentiert jede Spalte (der Test gegen die Parquet-Schemata bleibt).
- Ausgabe byteidentisch: Download-Tabelle (Snapshot), `schema.json`, CSV-Dateien.

### F3 Ausreißer in den Settings, Regression je Variante

- `defaults.toml`: `[analysis] exclude_districts = [1, 10]` mit Kommentar (Tabelle 5 der Arbeit); Modell
  `Analysis` in `settings.py`; zählt zum Fingerprint.
- `analysis/regression.py`: `RegressionPair` und `regression_pair(results, exclude, *, x=RATE, y=TURNOUT,
  y_scale=100.0)` (Umzug aus `report/model.py`; `without` ist `None`, wenn `exclude` leer ist oder zu wenige
  Bezirke bleiben). `report/model.py` importiert beides; `OUTLIERS` verschwindet.
- Tests: die vorhandenen Regressionstests plus ein Test, dass `exclude=()` kein `without` liefert.

### F4 Profil und offene Periode

- `Settings.profile: str = ""` (nur `[a-z0-9][a-z0-9-]*` oder leer; nicht im Fingerprint, es ist ein Pfad).
  `Period.end: date | None = None`, `Period.election: date | None = None`; Validator: ohne `end` ist `election`
  Pflicht, ohne `election` gilt `election = end`, `end` nicht vor `start`, `election` nicht vor `start`.
- `Layout(data_root, cache_root, reference_root, profile="")`: mit Profil liegen `external`, `raw`, `interim`,
  `processed`, `site` unter `data_root/<profil>/` und `pdf_dir`, `text_dir` unter `cache_root/<profil>/`;
  `http_cache` bleibt geteilt; `reference_view()` bleibt flach. `Layout.for_profile(name)` liefert dasselbe
  Layout mit anderem Profil (02 liest damit Straßen und Orte der Hauptperiode). `from_settings` setzt es.
- `OparlPaper.in_period(start, end: date | None)`: ohne Ende zählt `start <= date`. `data_stand` nimmt
  `period.election` als Wahltag.
- Tests: Layout flach wie heute (Properties gleich), mit Profil disjunkt; Settings-Validatoren mit
  Gegenbeispielen; hypothesis für `in_period` ohne Ende; `georep status` zeigt das Profil.

### F5 Crosswalk-Kern

- `georep/crosswalk.py`: `unit_weights(frame, district, unit, weight) -> pl.DataFrame` mit Spalten
  `wahlkreis_id` Int64, `<unit>` Int64, `<weight>` Int64 (Summe), `gewicht` Float64; Zeilen mit Gewicht 0
  fallen weg. Verträge: Pflichtspalten, Gewichte positiv; post `gewicht` in (0, 1], `sums_to_one` je
  Wahlbezirk (Toleranz 1e-9), sortiert nach Wahlbezirk und Gewicht absteigend, jeder Wahlbezirk mit Gewicht
  kommt vor. `contracts.sums_to_one(frame, group, column, tol)`.
- Tests: Handbeispiel (Zweifachfall wie Wahlbezirk 40), hypothesis (Summen 1, Skalierung ändert nichts,
  eine Einheit ergibt 1,0).

### F6 Zählende Tests entkoppeln

- `test_cli.py`, `test_pipeline.py`, `test_report_build.py`: erwartete Zahlen aus `build_steps` (Anzahl der
  Offline-Schritte) und aus dem Register (Anzahl der Downloads) ableiten; die Namen bleiben geprüft.
- Konvention für Phase 3: eine Option, die Schritte oder Tabellen ergänzt, schreibt ihre Erwartung in einen
  eigenen Test und lässt die gemeinsamen Zeilen in Ruhe.

### F7 Achsen-Helfer der Diagramme

- `charts.py`: aus `scatter` wird `Axes` (Ränder, Skalen, `sx`, `sy`, Ticks, Gitter, Achsenlinien,
  Tick-Beschriftungen, Achsentitel) als eigene Klasse mit `render_grid()`, `render_axes()`, `render_ticks()`;
  `scatter` nutzt sie. Reines Refactoring, SVG byteidentisch (im Scratchpad per `diff` geprüft, Test auf der
  Mini-Fixture gegen die vorher gespeicherte Ausgabe).

Nicht Fundament, obwohl mehrfach gewünscht: Fingerprint je Schritt (06), gemeinsame Datei „Attribute je
Dokument" (04), Allowlist aus Settings (01), Quellen und Lizenzen als Daten im Fuß (01). Gründe in § 8.

## 4. Merge-Reihenfolge

| Pos. | Option | Warum an dieser Stelle |
|---|---|---|
| 1 | 08 Suche | kleinster Fußabdruck (ein Modul, ein Abschnitt), kein Schritt, keine Settings; prüft den Abschnittsmechanismus als Erste |
| 2 | 05 Gremien | offline, eine Settings-Tabelle, zwei Schritte, drei Tabellen; nutzt den generischen Umschalter und F5; keine fremden Abhängigkeiten |
| 3 | 06 Gewichtung | offline, neue Abhängigkeit scikit-learn (Lockfile früh ändern, damit alle folgenden Rebases sie sehen), zwei Schritte, vier Tabellen, nutzt F3 |
| 4 | 03 Kontrollvariablen | offline bis auf 2,3 MB Fremddaten (einmalig, erlaubt); baut `area_shares` (02 braucht es), drei Schritte, drei Tabellen; `Layout.context_root` als Feld mit Default |
| 5 | 04 Parteien | ändert Korpus-Schema (2 auf 3), Record, OParl-Vertrag, `dokumente.json`-Felder: nach den reinen Offline-Optionen, vor 02 und 07, die den Record erweitern |
| 6 | 02 Zeitreihe | nutzt F4 (Profil) und 03 (`area_shares`); baut Umrechnung, zweite Periode, Vergleich, Unterseite; größter Plan der Offline-Gruppe |
| 7 | 01 Städte | breitester Umbau der Settings (stadtneutrales `defaults.toml`, Paketprofile, `[city]`, `publish`): spät, damit es über alle Settings-Blöcke der anderen rebased und die Vorlage am Ende parametrisiert |
| 8 | 07 Monitoring | nur Ergänzungen (Schritt `timeline`, `deploy/`, Profil 2025); nutzt 04 (`deleted`-Handhabung im Record), F4 und nach 01 das Paketprofil |

Alle acht dürfen gleichzeitig arbeiten (§ 4 des Meta-Plans); die Reihenfolge gilt für den Merge, nicht für den
Start. Der Supervisor startet 08, 05, 06, 03 zuerst und 04, 02, 01, 07 kurz danach.

## 5. Regeln für Phase 3

### 5.1 Nummern der Seitenabschnitte

| Nummer | Abschnitt | Option |
|---|---|---|
| 10 | `kernzahlen` | vorhanden |
| 15 | `suche` | 08 |
| 20 | `karte` | vorhanden; 05 ergänzt Radio, Legende, Tooltip-Zeile |
| 30 | `zusammenhang` | vorhanden |
| 32 | `kontrollvariablen` | 03 |
| 34 | `gewichtung` | 06 |
| 36 | `perioden` | 02 (nur mit Vergleich) |
| 38 | `parteien` | 04 |
| 40 | `wahlbezirke` | vorhanden |
| 45 | `gremien` | 05 |
| 50 | `begriffe` | vorhanden |
| 55 | `monate` | 07 |
| 60 | `methode` | vorhanden; 01, 02, 03, 04, 05 hängen je einen Absatz **am Ende** an, Kommentar `{# Option NN #}` |
| 65 | `abgeleitete-daten` | 03 |
| 70 | `downloads` | vorhanden |
| 75 | `laufend` | 07 (nur mit `monitoring_url`) |

Kopf und Fuß des Rahmens ändern 01 (Stadt), 02 und 07 (Periode, Datenstand), 03 und 02 (Lizenzsätze); das
sind Textkonflikte, die der Supervisor beim Merge löst. Ein Abschnitt, der nur mit einem Modellteil existiert,
beginnt mit `{% if model.<teil> %}` und endet mit `{% endif %}`; das Modellfeld hat Default `None`.

### 5.2 Vorschau und Ports

Lokaler Server je Worktree auf Port `8700 + NN` (`08-suche`: 8708); Port 8765 ist belegt, 8777 gehört dem
Hauptklon. `.claude/launch.json` ist gitignored und wird je Worktree angelegt.

### 5.3 Cache und Daten

`cache_root` ist geteilt; nur `bootstrap` schreibt den Textstore der Hauptperiode. Extraktion oder Simulation
nur mit Profil (eigener Cache) oder eigenem `cache_root`. `data_root` ist je Worktree eigen (steht in
`settings.local.toml`).

### 5.4 Settings-Fingerprint

Neue Schlüssel zählen zum Fingerprint, außer Pfade (`profile`, `context.root`, Dateinamen) und reine
Anzeigewerte (`report.*`, `bootstrap.*`); der Ausschluss steht als Kommentar an `fingerprint()`.

### 5.5 Netz

Wie § 2 des Meta-Plans: Stichproben bis rund fünf Minuten mit Rate-Limiting; aufgezeichnete Antworten als
Fixtures mit README (URL, Datum, Auswahl); alles Längere ist ein dokumentierter Lauf für Konrad. Die vier
Läufe (01 Mönchengladbach, 02 Periode 2014 bis 2020, 04 Vollabruf optional, 07 Erstabruf) stehen gebündelt in
`fragen.md`.

### 5.6 Attribute je Dokument

Tabellen mit einer Zeile je Korpus-ID (`id` String, sortiert, eindeutig, genau die IDs des Korpus) heißen
`dokumente_<attribut>.parquet` und tragen das Prädikat `one_row_per_document` (Option 04 legt es in
`contracts.py` an, 05 und 06 nutzen es nach dem Rebase; bis dahin dieselbe Bedingung inline).

### 5.7 Commits und Doku

Wie CLAUDE.md. Je Option am Ende: Status im eigenen Plan auf „im Review", Abschlussbericht nach § 5 Phase 3
des Meta-Plans. `decisions.md`: neuen Punkt ohne feste Nummer schreiben („## Punkt: <Titel> (Option NN,
Datum)"); der Supervisor nummeriert beim Merge.

## 6. Fragen an Konrad

Alle offenen Fragen der acht Pläne (66) stehen in [fragen.md](fragen.md), je mit Annahme. Der Supervisor hat
vorentschieden, was die Synergiephase entscheiden kann (dort als „Supervisor" markiert), und hebt die hervor,
deren Antwort den Umfang ändert oder eine Handlung von Konrad braucht (Netzläufe, Daten im Repo, Lizenzen, R2,
VPS, Mönchengladbach statt Neuss, Düsseldorf unter `data/duesseldorf/`). Keine Frage blockiert die Arbeit in
Phase 3.

## 7. Änderungen je Plan (Kurzfassung; ausführlich in § 10 der Pläne)

- **01 Städte**: Profil-Schlüssel kommt aus F4 (Stufe A baut nur noch Paketprofile, `--profile`, `[city]`
  und die stadtneutrale `defaults.toml`); Düsseldorf bleibt in Phase 3 flach (Frage 7 offen); Cache je Profil
  liefert F4; `exclude_districts` aus F3; Allowlist aus Settings bleibt Teil von 01; Vorlage ist Rahmen plus
  Abschnitte; `publish.cities` und `vergleich.html` unverändert; übernimmt `settings.2014.toml` und
  `settings.2025.toml` in `profiles/`, soweit vorhanden.
- **02 Zeitreihe**: `period.name` wird `profile` (F4), Textstore und PDFs je Profil aus F4; `Period.election`
  aus F4; `period.label`, `period.dictionary` bleiben 02; Crosswalk: `area_shares` kommt von 03, 02 baut
  `assign_by_point`, `target_weights`, `transfer_counts`, `largest_remainder`; `_axes` aus F7; Vergleichstabelle
  über F2; Abschnitt `36-perioden`; kanonische Spaltennamen wie geplant.
- **03 Kontrollvariablen**: Crosswalk-Modul heißt `georep/crosswalk.py` (nicht `prep/crosswalk`), nutzt
  `unit_weights` aus F5 für den Attribut-Crosswalk, baut `area_shares` in der Form aus § 2 Punkt 4;
  `Layout.context_root` als fünftes Feld mit Default `None`; `_axes` aus F7; drei Tabellen über F2;
  Abschnitte `32-kontrollvariablen` und `65-abgeleitete-daten`; `regression_pair` aus F3 für Modell A.
- **04 Parteien**: Record bekommt zusätzlich `consultation_organizations: tuple[str, ...]` im selben
  Schema-Sprung; `max_pages` und der Zähler bleiben 04; `FIELDS` von `dokumente.json` wächst um `urheber`;
  `showDocuments` aus F1; Abschnitt `38-parteien`; drei Tabellen über F2; Prädikat `one_row_per_document`.
- **05 Gremien**: `herkunft` und die Herkunftsregeln entfallen (04 besitzt den Urheber); Crosswalk über
  `georep.crosswalk.unit_weights` (F5) statt eines eigenen Moduls; generischer Umschalter aus F1 (05 ergänzt
  nur Radio, `extra_classes`, Legende, Tooltip-Zeile); drei Tabellen über F2; Abschnitt `45-gremien`;
  Gremiennamen aus den Settings wie geplant.
- **06 Gewichtung**: `regression_pair` und `exclude_districts` kommen aus F3 (Stufe A kleiner); vier Tabellen
  über F2; Abschnitt `34-gewichtung`; scikit-learn wie geplant (früh gemerged).
- **07 Monitoring**: `profile`, `Period.end` optional, `Period.election` aus F4 (Stufe A kleiner); Cache je
  Profil liegt unter `cache_root/2025/` (R2-Layout entsprechend); Abschnitte `55-monate` und `75-laufend`;
  zwei Tabellen über F2; nach dem Merge von 01 wandert `settings.2025.toml` nach `profiles/`.
- **08 Suche**: Abschnittsmechanismus, `georep`-Objekt und das Budget kommen aus F1 (Stufen B.2, C.1 und D.1
  entfallen); Abschnitt `15-suche`; Port 8708; sonst unverändert.

## 8. Zurückgestellt

- **Fingerprint je Schritt** (06): richtig, aber ein Umbau des Stamp-Mechanismus mit eigenen Risiken; nach
  der Sammelversion als eigener Punkt.
- **Gemeinsame Datei „Attribute je Dokument"** (04): drei Tabellen mit demselben Schlüssel reichen; eine
  Vereinigung ist ein Join zur Lesezeit.
- **Allowlist und Lizenztexte aus Settings** (01): gehört zu 01, nicht ins Fundament, weil nur 01 sie braucht
  und die anderen Optionen ihre Links als Konstanten ergänzen können.
- **Umzug Düsseldorfs nach `data/duesseldorf/`** (01): wartet auf Konrads Antwort; technisch nach F4 ein
  Einzeiler (`profile = "duesseldorf"` im Profil) plus Umzug der Ordner.
- **Option 9 und 10** wie im Meta-Plan.
