# Plan: Berichtsseite mit Karte und Download der Ergebnisse

Abgeschlossen am 2026-10-11: Stufen A bis F umgesetzt (`v0.9.0`, Workflow `pages.yml`), Pages auf „GitHub Actions"
gestellt, Seite unter <https://konradvoelkel.github.io/geographic-representation-dus/> abgenommen. Stufe G am
selben Tag nachgezogen (`v0.10.0`: Dokumente je Begriff, Orte mit Namen, `karte.html` mit Leaflet); nur der
VPS-Umzug bleibt optional. Dieser Plan wird nicht fortgeschrieben.

Stand 2026-10-11, Auftrag von Konrad am selben Tag, offene Fragen am selben Tag beantwortet (§ 7); der Plan
ist damit freigegeben. Er ist so geschrieben, dass ein frischer Agent ihn
ohne weitere Rückfragen übernehmen kann: Ziel, Entscheidungen, Datenlage, Bauplan in Stufen mit
Abnahmekriterien, Fallstricke. Arbeitsregeln (Commits, nox, Verträge, nie unter `reference/` schreiben)
stehen in [../CLAUDE.md](../CLAUDE.md); der Aufbau des Programms in [architecture.md](architecture.md).
Vor dem ersten Diagramm die Skill `dataviz` laden, falls vorhanden; sie liefert Form- und Farbregeln.

## 1. Ziel

Eine HTML-Seite, die die Ergebnisse ansprechend aufbereitet: Kernzahlen, eine Karte der 41 Wahlbezirke mit
der Trefferquote, das Streudiagramm mit Regressionsgerade (Tabelle 5 der Arbeit), eine sortierbare Tabelle je
Wahlbezirk, die Suchbegriffe mit Trefferzahlen, Methode und Herkunft. Dieselbe Seite bietet die berechneten
Ergebnisse zum Weiterverarbeiten an: Parquet (primär) und CSV, mit dokumentiertem Spaltenschema, Prüfsumme
und Datenstand. Die Seite entsteht aus den Parquet-Ergebnissen als letzter Schritt der Pipeline und wird aus
den Referenzdaten reproduzierbar gebaut und veröffentlicht.

Nicht Ziel: ein Server, eine Datenbank, ein JavaScript-Framework, ein Build mit npm, Kartenkacheln von
Dritten, Tracking. Nicht Ziel: die Texte der 19 108 Dokumente veröffentlichen (15 MB, fremde Dokumente); es
reichen IDs und URLs.

## 2. Entscheidungen (getroffen, nicht neu zu diskutieren)

| Frage | Entscheidung | Warum, und was verworfen wurde |
|---|---|---|
| Form | eine einzige, in sich geschlossene `index.html` ohne externe Ressourcen (CSS, JS, SVG inline), daneben ein Ordner `data/` mit den Download-Dateien | funktioniert offline, aus dem Dateisystem, in zehn Jahren; archivierbar; kein CDN, keine Cookie-Frage. Verworfen: Leaflet mit OSM-Kacheln (braucht Netz, Kachel-Nutzungsregeln, externes JS); React/Vue (Build-Kette für eine Seite) |
| Karte | inline SVG, aus den Geometrien in Python gezeichnet (shapely, EPSG:25832, also schon metrisch und formtreu), Choroplethe der Trefferquote, Hover-Tooltips und Klick-Markierung mit wenigen Zeilen eigenem JavaScript | die Geometrie liegt vor (306 Stimmbezirke, zu 41 Wahlbezirken vereinigt); SVG ist textuell, testbar, barrierearm. Verworfen: PNG aus matplotlib (nicht interaktiv, nicht skalierbar) |
| Diagramme | inline SVG aus Python, kein matplotlib | wie die Karte; matplotlib bleibt nur für das Notebook (Abhängigkeit darf in die Gruppe `notebook` wandern) |
| Vorlage | Jinja2 mit Autoescape (`uv add jinja2`), eine Vorlage `src/georep/report/templates/report.html.j2`, geladen über `importlib.resources` wie `defaults.toml` | Autoescape gegen Begriffe mit `<` oder `&` in Labels; typisiert; überall bekannt. Verworfen: `string.Template` (kein Escaping, keine Schleifen), handgeschriebene Konkatenation |
| Tabellen | Polars bis zum Schluss; die Vorlage bekommt Listen von dataclasses, keine Frames | wie der Rest des Pakets; mypy strict |
| Downloads | Parquet ist das primäre Format, CSV daneben (über die vorhandene `export`-Logik), dazu `wahlbezirke.geojson` in EPSG:4326 und `schema.json`; Prüfsumme SHA-256 und Größe stehen auf der Seite | Parquet trägt Typen und Listen; CSV für Tabellenkalkulationen; GeoJSON für GIS |
| Zahlenformat | deutsch, von Hand (`format_de`): Tausender mit schmalem Leerzeichen, Dezimalkomma, feste Nachkommastellen je Größe | kein `locale`-Modul (plattformabhängig); eine kleine reine Funktion mit Vertrag |
| Integration | neuer Pipeline-Schritt `report` am Ende der Kette, Eingaben und Stamp wie alle anderen; keine neue CLI-Unterbefehle, `georep run report` reicht | derselbe Mechanismus für Frische, `--force`, `--dry-run`; die Seite ist ein Ergebnis wie die Parquet-Dateien |
| Ort der Ausgabe | `data_root/site/` (`Layout.site`, `Layout.site_index`, `Layout.site_data`) | neben den anderen Ergebnissen, gitignored, nie unter `reference/` |
| Veröffentlichung | zuerst GitHub Pages aus einem Actions-Workflow, der die Seite aus den Referenzdaten baut (`bootstrap`, `run`), also ohne Netzabrufe; Quelle „GitHub Actions" in den Repo-Einstellungen. Später nach Bedarf Konrads VPS (statische Dateien, `rsync`), optional unter `georep.konradvoelkel.de` | reproduzierbar aus dem Repo; kein eigener Branch (Konrad, 2026-10-11: keine Branches mehr). Die Seite benutzt nur relative Pfade (`data/…`), damit der Umzug ein Kopieren ist. Verworfen: `gh-pages`-Branch, Veröffentlichung von Hand |
| Sprache | Deutsch; eine englische Kurzfassung von drei bis vier Sätzen im Kopf (`<p lang="en">`), sonst nichts Englisches | Konrad, 2026-10-11 |
| Lizenzhinweise | auf der Seite: Ergebnisse CC0; Straßennamen abgeleitet aus OpenStreetMap (ODbL, Namensnennung „© OpenStreetMap-Mitwirkende"); Wikidata CC0; Wikipedia-Artikeltitel; Open-Data-Portal Düsseldorf mit der Lizenz, die das Portal nennt (vor dem Veröffentlichen dort nachsehen und wörtlich zitieren) | Pflicht bei ODbL-abgeleiteten Daten |

## 3. Datenlage (Stand 2026-10-11, Spalten exakt)

Alles liegt nach `georep run` unter `data_root/processed/` beziehungsweise `external/`:

- `wahlbezirke_auswertung.parquet` (41 Zeilen): `wahlkreis_id` Int64, `suchbegriffe` List(String) (Anzeigeliste,
  ohne `hide_in_display`), `paper_ids` List(String) (OParl-URLs der Dokumente mit Treffer), `anzahl_treffer` Int64,
  `Wahlberechtigte_insgesamt`, `Waehler`, je Partei `<Partei>_Stimmen` Int64 (CDU, GRUENE, SPD, FDP, Die_Linke,
  AfD), `wahlbeteiligung` Float64 (Anteil 0 bis 1), je Partei `<Partei>_anteil` Float64, `trefferquote` Float64
  (Treffer je Wahlberechtigtem, z. B. 0,16).
- `inverted_index.parquet` (5841 Zeilen): `suchbegriffe` String, `paper_ids` List(String), `anzahl_treffer` Int64.
- `combined_searchdict.parquet` (41 Zeilen): `wahlkreis_id`, `suchbegriffe` List(String) (alle Begriffe, auch versteckte).
- `wahlbezirke_waehler.parquet` (41 Zeilen): wie die Wählerspalten oben.
- `wikidata_vis.parquet` (1309 Zeilen): `label`, `wahlkreis_id`, `lon`, `lat` (die Orte nach Bereinigung).
- `wahlbezirke_strassen.parquet` (41 Zeilen): `wahlkreis_id`, `suchbegriffe` List(String) (Straßennamen).
- `external/Stimmbezirke_2025.geojson`: 306 Features in EPSG:4647 (`crs.properties.name`), Eigenschaften
  `Stimm-/ Wahlbezirk`, `Kommunalwahlbezirk Nr.`, `Kommunalwahlbezirk Name` (z. B. 1 = „Altstadt, Carlstadt,
  Hofgarten"), dazu Stadtteil, Stadtbezirk, Bundestags- und Landtagswahlkreis. `georep.geo.read_precincts`
  liefert daraus `Precinct(precinct_id, district_id, district_name, geometry)` im Arbeits-CRS.
- Regression: `georep.analysis.regression.regress(results)` und `regress(results, exclude=(1, 10))` liefern
  `RegressionResult(n, slope, intercept, r, p, stderr)`; die Arbeit skaliert y auf Prozent (`y_scale=100`).
- Datenstand: die Stamps `<datei>.stamp.json` neben jeder Ausgabe tragen `written` (ISO-Zeit) und `code`.

Größen: alle sechs Parquet-Dateien zusammen unter 400 KB; das GeoJSON 1,8 MB (wird für die Seite zu 41
Wahlbezirken vereinigt und vereinfacht; Ziel unter 300 KB SVG).

Lücke, die zuerst geschlossen werden muss: die Mini-Fixture (`tests/fixtures/mini/`) hat kein GeoJSON
(`bootstrap` meldet dort „1 in der Referenz nicht gefunden"). Der Schritt `report` braucht es als Eingabe,
und `tests/golden/test_pipeline.py` läuft alle Schritte auf der Mini-Fixture. Also `make_mini.py` erweitern:
die Stimmbezirke der drei Mini-Wahlbezirke (1, 10, 38) aus `reference/external/Stimmbezirke_2025.geojson`
ausschneiden nach `tests/fixtures/mini/external/Stimmbezirke_2025.geojson` (rund 20 Features, unter 200 KB).
Die Dateien unter `expected/` dürfen dabei nicht neu erzeugt werden (Golden Master, siehe
`tests/fixtures/mini/README.md`); nur die neue Eingabedatei kommt hinzu, mit Herkunftszeile im README.

## 4. Inhalt der Seite (von oben nach unten)

1. **Kopf**: Titel „Geografische Repräsentation in Düsseldorfer Ratsdokumenten", ein Absatz mit der Frage,
   Datenstand (Wahl 14.09.2025, Dokumente 13.09.2020 bis 14.09.2025, Straßen und Orte mit Abrufdatum aus den
   Stamps), Version `georep x.y.z`, Link zum Repository. Darunter die englische Kurzfassung: drei bis vier
   Sätze in einem `<p lang="en">` (Frage, Methode, Ergebnis in einer Zahl, Hinweis auf die Downloads); das ist
   das einzige Englisch auf der Seite.
2. **Kernzahlen** als Kacheln: 41 Wahlbezirke, 306 Stimmbezirke, 19 108 Dokumente (19 033 mit Text), 5841
   Begriffe, Dokumente mit mindestens einem Treffer (Vereinigung aller `paper_ids`), Median und Spannweite der
   Trefferquote, Median der Wahlbeteiligung. Jede Zahl aus den Daten, keine fest kodiert.
3. **Karte**: Choroplethe der Trefferquote je Wahlbezirk; Farbskala sequenziell mit fünf Klassen (Quantile,
   Grenzen in der Legende als Zahlen); Hover zeigt Nr., Name, Treffer, Wahlberechtigte, Trefferquote,
   Wahlbeteiligung, die fünf häufigsten Begriffe; Klick hebt den Bezirk und seine Tabellenzeile hervor.
   Umschalter (zwei Radiobuttons) Trefferquote / Wahlbeteiligung. Optionaler Layer: die 1309 Orte als kleine
   Punkte. Nordpfeil und Maßstabsbalken sind nicht nötig; eine Zeile „EPSG:25832, vereinfacht auf 15 m" reicht.
4. **Zusammenhang**: Streudiagramm Trefferquote (x) gegen Wahlbeteiligung in Prozent (y), Punkte beschriftet
   mit der Nr., Regressionsgerade „alle" und gestrichelt „ohne 1 und 10", darunter Tabelle 5 (n, Steigung,
   Achsenabschnitt, r, R², p) für beide Varianten, mit dem Satz, dass p = 0,31 keinen Zusammenhang belegt.
5. **Tabelle je Wahlbezirk**, sortierbar per Klick auf die Spaltenköpfe (vanilla JS, kein Framework): Nr.,
   Name, Treffer, Wahlberechtigte, Wähler, Wahlbeteiligung %, Trefferquote, Anzahl Begriffe, die fünf
   häufigsten Begriffe. Alle 41 Zeilen, keine Paginierung.
6. **Begriffe**: je Wahlbezirk aufklappbar (`<details>`) die Begriffe mit Dokumentzahl, absteigend; darüber die
   zwanzig trefferstärksten Begriffe stadtweit mit Bezirk. Versteckte Begriffe (`hide_in_display`, heute
   „schulweg") bleiben versteckt, mit einer Fußnote, dass sie in der Zählung enthalten sind (Verhalten der Arbeit).
7. **Methode und Grenzen**: fünf bis acht Sätze; Verweis auf die Arbeit und `docs/architecture.md`; die
   bekannten Grenzen aus `STATUS.md` (Kommas in Labels, Tabelle 5 „ohne Ausreißer").
8. **Downloads**: Tabelle mit Datei, Format, Zeilen, Größe, SHA-256, Beschreibung; darunter das Spaltenschema
   je Tabelle (Spalte, Typ, Bedeutung, Einheit). Dateien: die sechs Parquet-Tabellen aus § 3, dieselben als
   CSV, `wahlbezirke.geojson`, `schema.json` (maschinenlesbar dieselben Beschreibungen).
9. **Fuß**: Lizenzen (§ 2), Erzeugungszeit, Commit, „gebaut mit georep x.y.z".

Gestaltung: eine Spalte, maximal 72 em breit, Systemschrift, hell und dunkel über `prefers-color-scheme`,
Farbskala farbenblind-sicher (z. B. ein sequenzielles Blau oder Viridis-artige fünf Stufen), Kontraste nach
WCAG AA, Tabellen mit `<th scope>`, jede SVG-Fläche mit `<title>`, `lang="de"`. Keine Animationen, kein
Scroll-Hijacking. Die ganze Seite unter 3 MB; Ziel unter 1,5 MB.

## 5. Bauplan in Stufen

Jede Stufe ist ein oder zwei Commits, nach jedem `uv run nox` grün, Verträge an den Batch-Grenzen, Tests in
`tmp_path` mit `Layout(tmp/data, tmp/cache, mini_root)`. Neue Module unter `src/georep/report/`.

### Stufe A: Mini-Fixture und Layout

1. `tests/fixtures/make_mini.py`: GeoJSON der drei Mini-Wahlbezirke ausschneiden (Features filtern über
   `Kommunalwahlbezirk Nr.` in {1, 10, 38}, `crs` übernehmen), nach `tests/fixtures/mini/external/`. README der
   Fixture ergänzen. `expected/` unangetastet (Test: `git status` zeigt dort nichts).
2. `georep.layout`: `site`, `site_index` (`site/index.html`), `site_data` (`site/data`); `runtime_dirs` ergänzen.
3. Abnahme: `uv run nox` grün; `bootstrap` auf der Mini-Fixture meldet „0 in der Referenz nicht gefunden".

### Stufe B: Datenmodell `report/model.py`

1. dataclasses (frozen): `DistrictRow` (id, name, hits, eligible, voters, turnout, rate, terms_total,
   top_terms: list[tuple[str, int]]), `TermRow`, `KeyFigures`, `RegressionPair` (alle, ohne 1 und 10),
   `Download` (name, format, rows, bytes, sha256, description), `ColumnDoc` (table, column, dtype,
   description, unit), `ReportModel` mit allem plus `generated_at: datetime`, `version`, `data_stand`
   (aus den Stamps).
2. `build_report_model(layout, settings, *, now)`: liest die Parquet-Dateien mit Polars, verbindet Wörterbuch
   und Index zu Begriffszahlen je Bezirk, holt Namen aus `read_precincts`, rechnet beide Regressionen.
   `now` ist Eingabe (Testnaht), nie `datetime.now()` im Modul.
3. `COLUMN_DOCS`: ein Dict Tabelle -> Spalte -> (Bedeutung, Einheit) in Deutsch; ein Test prüft, dass jede
   Spalte jeder veröffentlichten Tabelle eine Beschreibung hat und keine Beschreibung ins Leere zeigt.
4. Verträge: `build_report_model` post: `len(districts) == results.height`, Quoten ≥ 0, Namen nicht leer,
   `top_terms` sortiert absteigend.
5. Tests auf der Mini-Fixture (3 Bezirke): Zahlen gegen `pl.read_parquet` nachgerechnet; hypothesis für
   `format_de` (idempotent auf dem Ergebnis, Rundung, negative Zahlen, 0).

### Stufe C: Geometrie und Karte `report/geometry.py`, `report/charts.py`

1. `district_shapes(precincts, tolerance_m=15)`: `unary_union` je `district_id`, `simplify`, `make_valid`;
   liefert `dict[int, BaseGeometry]` im Arbeits-CRS. Vertrag: 41 Schlüssel (Mini: 3), keine leere Fläche,
   Flächensumme bis auf 1 % gleich der Summe der Stimmbezirke.
2. `to_svg_paths(shapes, width, height)`: Bounding Box auf eine `viewBox` abbilden, y spiegeln, Polygone und
   Multipolygone zu `d`-Attributen mit zwei Nachkommastellen; Löcher über `fill-rule="evenodd"`.
3. `choropleth(model, shapes, metric)`: SVG-String mit einer `<path>` je Bezirk (`data-id`, `<title>`, Klasse
   nach Quantil), Legende mit fünf Klassen und Grenzen (`format_de`), Umschalter-Daten als `data-rate` und
   `data-turnout` Attribute, damit das JavaScript die Füllklasse wechselt, ohne das SVG neu zu bauen.
4. `scatter(model)`: Achsen mit Ticks, Punkte mit Nr. als `<text>`, zwei Geraden aus `RegressionPair`,
   `<title>` je Punkt. Reine Funktion von Zahlen zu SVG.
5. `wahlbezirke_geojson(shapes, names, rows)`: nach EPSG:4326 (`georep.geo.to_lonlat`, die eine
   Rückprojektion), Eigenschaften `wahlkreis_id`, `name`, `anzahl_treffer`, `trefferquote`, `wahlbeteiligung`.
6. Tests: Zahl der `<path>` gleich Zahl der Bezirke; `viewBox` positiv; alle Koordinaten endlich; SVG parst mit
   `xml.etree.ElementTree`; Snapshot (syrupy) nur für die Legende der Mini-Fixture (klein, stabil).

### Stufe D: Vorlage und Rendering `report/render.py`

1. `uv add jinja2`; Vorlage `templates/report.html.j2` mit `autoescape=True`; CSS und JS inline in der Vorlage
   (Sortierung der Tabelle, Hover-Tooltip, Umschalter, Klick-Markierung; zusammen unter 150 Zeilen, keine
   Abhängigkeit).
2. `render_report(model, svg_map, svg_scatter) -> str`; Vertrag post: beginnt mit `<!doctype html>`, enthält
   `lang="de"`, keine Zeichenkette `src="http` oder `href="http` außer den erlaubten Links (Repository,
   Arbeit, Quellen; Allowlist im Modul).
3. Tests: HTML parst (`html.parser`), genau ein `<h1>`, jeder Bezirksname kommt vor, jede Download-Datei ist
   verlinkt, Größe unter 3 MB auf der vollen Referenz (als `slow`-Test), Snapshot der Download-Tabelle auf
   der Mini-Fixture.

### Stufe E: Schritt `report`, Downloads, Dokumentation, Version

1. `pipeline.build_steps`: Schritt `report` mit Eingaben `results`, `dictionary`, `index`, `voters`,
   `pois_table`, `streets_by_district`, `districts_geojson`; Ausgaben `site_index` (zuerst, trägt den Stamp)
   und `site/data/schema.json`. Der Schritt kopiert die Parquet-Dateien atomar nach `site/data/`, schreibt die
   CSVs mit der Logik aus `export.py` (die Funktion dafür herausziehen, damit `georep export` und der Schritt
   dieselbe nutzen), das GeoJSON, `schema.json`, dann `index.html`. Rückgabe: „41 Wahlbezirke, 13 Dateien,
   1,2 MB".
2. `georep steps`-Snapshot (`tests/unit/__snapshots__/test_cli.ambr`) aktualisieren, bewusst, mit Diff.
3. `tests/golden/test_pipeline.py`: `offline` erwartet jetzt 9 Schritte statt 8; die CLI-Tests mit „8
   ausgeführt" anpassen; der slow-Test prüft zusätzlich, dass `site/index.html` existiert und die Zahl 41 trägt.
4. Doku: README (Loslegen: `uv run georep run` erzeugt auch `data/site/index.html`; Befehle), `docs/architecture.md`
   (Modultabelle `report/`, Pipeline-Tabelle, Datenhaltung `site/`), `CHANGELOG.md` 0.9.0, `STATUS.md`, Version
   in `pyproject.toml`, `__init__.py`, `uv lock`. matplotlib in die Gruppe `notebook` verschieben.
5. Abnahme aus frischem Klon: `uv sync --locked && uv run georep bootstrap && uv run georep run` erzeugt
   `data/site/index.html`; die Datei öffnet im Browser ohne Netz mit Karte, Diagramm, Tabelle, Downloads;
   `uv run nox`, `uv run pytest -m slow`, `uv run nox -s bench` grün (Rauschen beachten, Schwelle 20 %).

### Stufe F: Veröffentlichung

1. `.github/workflows/pages.yml`: bei Push auf `main` und von Hand (`workflow_dispatch`): `uv sync --locked`,
   `uv run georep bootstrap`, `uv run georep run`, `actions/upload-pages-artifact` mit `data/site`,
   `actions/deploy-pages`; Actions per SHA gepinnt wie in `ci.yml`; Berechtigungen `pages: write`,
   `id-token: write`. Push per SSH (das gh-Token hat keinen `workflow`-Scope, SSH-Pushes sind davon nicht
   betroffen).
2. Konrad schaltet in den Repo-Einstellungen Pages auf „GitHub Actions" (Settings, Pages, Source). Danach die URL
   `https://konradvoelkel.github.io/geographic-representation-dus/` in README und auf der Seite.
3. Abnahme: der Workflow läuft grün (Actions-REST-API abfragen, `gh run list` liefert hier leer), die Seite ist
   unter der Pages-URL erreichbar, Downloads laden, die SHA-256 auf der Seite stimmen mit den Dateien überein.
4. Variante VPS, später nach Bedarf (Konrad, 2026-10-11): die Seite ist statisch und benutzt nur relative Pfade,
   der Umzug ist `rsync -a --delete data/site/ <vps>:/var/www/georep/` plus ein statischer vhost (nginx oder
   Caddy, `index.html`, korrekte MIME-Typen für `.parquet` als `application/vnd.apache.parquet` und `.geojson`
   als `application/geo+json`). Optional die Domain `georep.konradvoelkel.de`: als CNAME auf Pages (Datei
   `CNAME` im Artefakt, DNS-Eintrag bei Konrad) oder als vhost auf dem VPS; beides ohne Änderung an der Seite.
   Ein kleines nox-Target `publish -- <ziel>` darf das `rsync` kapseln, mit Trockenlauf als Standard.

### Stufe G (optional, erst nach F)

Je Begriff eine Unterseite oder ein Filter mit den Dokumenten (Titel, Datum, Link ins Ratsinformationssystem);
dafür braucht die Seite den Korpus ohne Texte (`interim/papers.parquet` ohne Spalte `text`, rund 2 MB). Zweite
Karte mit den Orten als interaktiven Punkten. Leaflet-Variante mit OSM-Kacheln als zweite Datei, falls gewünscht.

## 6. Fallstricke, schon bekannt

- Nie unter `reference/` schreiben, Tests arbeiten in `tmp_path`; `Layout.guard_writable` auf jedem Zielpfad.
- `deal.pure`/`deal.has()` nicht auf rekursive Funktionen; `deal.raises` vergleicht exakte Typen (CLAUDE.md).
- Kein pandas, kein geopandas, kein matplotlib im Berichtscode; `nox -s deps` wacht über das Lockfile.
- Begriffe können `<`, `&`, Anführungszeichen enthalten: Autoescape an, und ein Test mit einem Begriff
  `"<b>" & Co` auf der Mini-Fixture (als zusätzlicher Eintrag im Modell, nicht in den Fixturen).
- Die Mini-Fixture hat drei Bezirke: Quantile mit fünf Klassen brauchen einen Zweig für weniger Bezirke als
  Klassen (dann so viele Klassen wie Bezirke).
- Floating-Point: Quoten nie auf Gleichheit testen, `pytest.approx` oder gerundete Anzeige vergleichen.
- Zeit ist Eingabe: `now` injizieren; der Stamp trägt ohnehin `written`.
- Die Seite ist ein Ergebnis: ein zweiter `georep run` ohne Änderung überspringt `report` und sagt „aktuell".
- Jinja2 ist eine Laufzeitabhängigkeit; `uv add jinja2`, nicht `--group dev`.
- Vor dem ersten Diagramm die Skill `dataviz` laden (Farbskalen, Achsen, Legenden), falls der Agent sie hat.

## 7. Antworten von Konrad (2026-10-11)

- Domain: zuerst GitHub Pages unter der Standard-URL; später nach Bedarf Umzug auf Konrads VPS; eine eigene
  Domain ist kaum nötig, möglich wäre `georep.konradvoelkel.de`. Umgesetzt in § 2 und Stufe F.
- Sprache: alles Deutsch, eine kleine englische Kurzfassung genügt. Umgesetzt in § 2 und § 4, Punkt 1.
- Dokument-URLs je Treffer auf der Seite: nicht beantwortet, der Vorschlag gilt: zunächst nur in den Downloads
  (`paper_ids` in `wahlbezirke_auswertung.parquet` und `inverted_index.parquet`), Unterseiten in Stufe G.

## 8. Start für den frischen Agenten

1. Lesen, in dieser Reihenfolge: `CLAUDE.md` (Regeln, Umgebung, Lehren), `STATUS.md`, diesen Plan ganz,
   `docs/architecture.md` (Abschnitte Pipeline, Datenhaltung, Verträge, Tests), `src/georep/pipeline.py`,
   `src/georep/export.py`, `src/georep/geo.py`, `tests/golden/test_pipeline.py`, `tests/fixtures/make_mini.py`.
2. Einstieg nach CLAUDE.md: `git switch main && git pull`; auf Konrads Rechner die uv-Variablen setzen (sonst
   legt uv eine `.venv` auf der vollen Primärplatte an); `uv sync && uv run nox && uv run pytest -m slow` grün.
3. Stufen A bis E in der Reihenfolge des Plans, je Stufe ein bis zwei Commits direkt auf `main`, nach jedem
   Commit `uv run nox`, dann Push; Verhaltensänderungen zuerst mit rotem Test. Nach Stufe E: Version 0.9.0
   (`pyproject.toml`, `src/georep/__init__.py`, `uv lock`), eine Zeile im `CHANGELOG.md`, `STATUS.md`
   nachziehen, Tag `v0.9.0`, Push von `main` und Tag. Dann Stufe F; der Schritt „Pages aktivieren" ist Konrads.
4. Vor dem ersten Diagramm die Skill `dataviz` laden, falls vorhanden.
5. Definition of Done: aus einem frischen Klon erzeugen `uv sync --locked && uv run georep bootstrap &&
   uv run georep run` die Datei `data/site/index.html`; sie öffnet ohne Netz mit Karte, Diagramm, Tabelle und
   Downloads; `uv run nox`, `uv run pytest -m slow` und `uv run nox -s bench` sind grün; der Pages-Workflow
   läuft grün, sobald Pages aktiviert ist. `docs/architecture.md` und `STATUS.md` beschreiben den neuen Stand;
   dieser Plan bekommt oben die Zeile „abgeschlossen am <Datum>" und wird nicht fortgeschrieben.
