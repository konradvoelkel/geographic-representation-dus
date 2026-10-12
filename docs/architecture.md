# Architektur

Stand 2026-10-11, `v0.10.0`. Diese Datei beschreibt, was das Programm ist und wie es gebaut ist. Warum es so
gebaut ist, steht mit den verworfenen Alternativen in [decisions.md](decisions.md); was sich aus Nutzersicht
geändert hat, in [../CHANGELOG.md](../CHANGELOG.md); der Befund vor dem Umbau in
[baseline-2026-10-10.md](baseline-2026-10-10.md); Messwerte datiert in [profiling/README.md](profiling/README.md).
Der Entwicklungsplan, der zu diesem Stand geführt hat, liegt abgeschlossen unter
[development-plan-2026-10.md](development-plan-2026-10.md).

## Aufgabe

Düsseldorf hat 41 Kommunalwahlbezirke aus 306 Stimmbezirken. Für jeden Wahlbezirk entsteht ein Wörterbuch aus
Straßennamen (OpenStreetMap) und Orten (Wikidata, Wikipedia); die 19 108 Ratsdokumente der Wahlperiode
2020 bis 2025 aus dem Ratsinformationssystem (OParl) werden danach durchsucht; je Bezirk zählt die Menge der
Dokumente mit mindestens einem Treffer, geteilt durch die Wahlberechtigten, als Trefferquote; eine lineare
Regression setzt sie zur Wahlbeteiligung der Kommunalwahl 2025 in Beziehung. Die Ergebnisse der
Bachelorarbeit (Tabelle 5) werden auf alle Stellen reproduziert; der Datensatz der Arbeit liegt eingefroren
unter `reference/`.

## Paket `georep`

Ein Paket, `src/georep/`, vollständig typisiert (`mypy --strict` mit deal-Plugin), Polars für Tabellen,
shapely und pyproj für Geometrie, Parquet für alles Abgeleitete.

| Modul | Aufgabe |
|---|---|
| `settings` | `defaults.toml` im Paket, darüber `settings.toml`, `settings.local.toml`, `--settings`, Umgebung `GEOREP_*`; pydantic-settings, unbekannte Schlüssel sind ein Fehler; `fingerprint()` der ergebnisrelevanten Parameter; `profile` (Ordnername je Stadt oder Periode, nicht im Fingerprint), `period.end` optional mit `election` als Wahltag, `analysis.exclude_districts` (Ausreißer von Tabelle 5), `originators` (Muster und Parteien für den Urheber, Option 04), `context` (Fremddaten: Quelle, Lizenz, Dateien, Spaltenform, Ordinalskalen, Variablen, Modelle, Schwellen) |
| `layout` | wo was liegt: `data_root`, `cache_root`, `reference_root`, `profile` (Unterordner `data_root/<profil>/` und `cache_root/<profil>/` für PDFs und Texte, HTTP-Cache geteilt; leer = flach), `context_root` (Fremddaten im Repo, Default `None`); `for_profile` wechselt; `guard_writable` verweigert jeden Pfad unter den beiden nur lesbaren Wurzeln |
| `io` | atomare Schreibvorgänge (Temporärdatei, fsync, `os.replace`), JSON, Parquet mit `schema_version` in den Metadaten, SHA-256 (`digest`) |
| `http` | Session mit Timeout, Retry mit Backoff, User-Agent, requests-cache je Quelle; `Transport`-Protokoll als Testnaht; `network_errors` wandelt requests-Fehler in `NetworkError` |
| `errors` | Domänenfehler: `MissingInputError`, `EmptyResultError`, `SchemaError`, `CorruptPdfError`, `FetchError`, `NetworkError` |
| `oparl` | OParl 1.1 als pydantic-Vertrag (`OparlPaper` mit den drei Urheberfeldern und `consultation_organizations`, `OparlFile`, `OparlOrganization`, `PaperPage`, `OrganizationPage`), echte Antworten als Fixtures |
| `records` | `PaperRecord`: die Zeile in `raw/papers.jsonl`, aus OParl oder dem Altformat der Arbeit; die vier URL-Listen sind Tupel, weil der Record `frozen` und damit hashbar ist |
| `stores` | `PaperStore` (JSONL, Upsert nach `modified`), `TextStore` (eine Parquet-Datei, Schlüssel Dateiname, Frische über Extraktorname und PDF-Hash) |
| `sources/` | reine Fetch-Funktionen über `Transport`: `opendata` (CSV, GeoJSON), `oparl` (Paper-Seiten), `pdfs` (`PdfStore` mit Manifest), `overpass` (Straßen je Polygon), `wiki` (SPARQL, GeoSearch) |
| `geo` | GeoJSON lesen, nach EPSG:25832 projizieren, `make_valid`, `PrecinctIndex` (STRtree), eine Rückprojektion nach lon/lat |
| `prep/` | `extract` (PDF-Text hinter `PdfTextExtractor`), `papers` (Korpus), `voters` (auch `district_units`: Wahlbezirk zu Stadtbezirk über den Crosswalk), `streets`, `pois`, `bodies` (Gremium je Dokument aus der Drucksachennummer: `parse_reference` als reine Funktion über `BodyRules`, `classify_papers` als Batch-Grenze), `context` (Fremddaten je Raumeinheit: Stimmbezirkstabelle, Tabelle der Quelle lesen, gewichtetes Mittel je Wahlbezirk): Polars-Funktionen Frame zu Frame |
| `search/` | `dictionary` (Wörterbuch je Wahlbezirk), `matcher` (`KeywordMatcher`-Protokoll, FlashText), `index` (invertierter Index) |
| `analysis/` | `hits` (Treffer je Wahlbezirk, Join mit Wählern), `regression` (`scipy.stats.linregress`; `regression_pair` rechnet beide Spalten von Tabelle 5 für jede Kennzahlspalte, Ausreißer aus den Settings; `spearman` für die Rangkorrelation zweier Kennzahlen), `ols` (multiple Regression mit numpy und scipy: Koeffizienten, Standardfehler, t, p, R², F-Test, VIF, standardisierte Koeffizienten, Added-Variable-Plots nach Frisch-Waugh-Lovell; `models_table` rechnet die Modelle der Settings je Stichprobe), `bodies` (Treffer je Wahlbezirk nach Gremium, Lokalität je Gremium), `weights` (gewichtete Trefferquoten: Gewicht je Begriff, Dokumentart und Thema, Maximum je Paar, lange Tabelle aller Varianten; reines Polars, kennt weder Dateien noch Settings-Objekte), `topics` (TF-IDF und NMF über die Texte; der einzige Ort mit `sklearn`-Import, mit der Stoppwortliste `stopwords_de.txt` als Paketdatei), `parties` (Urheber je Dokument aus `paperType`, Titel und Textkopf; Urheberklassen je Wahlbezirk; Kennzahlen und Korrelationen je Partei) |
| `crosswalk` | Umrechnung von Gebietseinheiten auf Wahlbezirke: `unit_weights` wiegt je Wahlbezirk die Einheiten (Stadtbezirk, Stadtteil) mit einer Zählgröße je Stimmbezirk, `area_shares` und `district_weights` gehen über Flächenanteile der Stimmbezirke, wenn die Einheiten eine eigene Gliederung sind; Vertrag: Gewichte in (0, 1], Summe je Wahlbezirk 1 |
| `pipeline` | Schrittregister: Name, Eingaben, Ausgaben, `run()`, Schema-Version; Stamps; `run_step`, `run_pipeline`, `build_steps` |
| `bootstrap` | kopiert die Referenz nach `data_root` und baut daraus `papers.jsonl` und den Textstore |
| `contracts` | `configure()` für `settings.contracts` und die Prädikate der deal-Verträge |
| `profiling` | `profile_step`: ein echter Schritt unter cProfile, `.prof` datiert nach `docs/profiling/` |
| `cli` | `georep run, fetch, steps, status, bootstrap, export, regress, profile`; `main(argv) -> int`; Exit 0, 1 (Domänenfehler), 2 (Bedienung) |
| `export` | Parquet-Ergebnisse als CSV neben die Dateien; `csv_plan` und `write_csv` nutzt auch der Schritt `report` |
| `report/` | die Berichtsseite: `model` (frozen dataclasses aus den Parquet-Ergebnissen, `format_de`, Spaltendoku; mit Fremddaten `controls` und `derived` für die beiden neuen Abschnitte), `geometry` (Wahlbezirke vereinigen und vereinfachen, SVG-Pfade, GeoJSON), `charts` (Quantilklassen, Legende, `nice_ticks`, `Axes`, Choroplethe, Streudiagramm und Added-Variable-Plots als SVG), `documents` (Dokumente mit Treffer ohne Texte, Begriffe als Indizes, für `dokumente.json`), `render` (Jinja2 mit Autoescape, Allowlist der Links; `sections` liest die Abschnitte aus `templates/sections/`; `render_map` für die Leaflet-Datei), `search` (Sucheinträge je kanonischem Begriff mit Wahlbezirken, Dokumenten und Art, dazu die Faltung als Spiegel des Abschnitts-Skripts), `tables` (Register der veröffentlichten Tabellen: Datei, Beschreibung, Spaltendoku, CSV-Regeln), `build` (der Schritt `report`: Downloads, Schema, Seiten) |

## Pipeline

Dreiundzwanzig Schritte, jeder mit Eingaben, Ausgaben und einer Schema-Version. Netzschritte laufen nur mit
`--online` oder über `georep fetch`. Mit `topics.k = 0` fehlt der Schritt `topics` im Register; dann ist es
einer weniger, und `weights` rechnet ohne Themenvarianten. Die drei Schritte der Kontrollvariablen
(`context_data`, `context`, `controls`) gibt es nur mit Fremddaten, also wenn `context.root` gesetzt ist;
sonst bleiben es achtzehn.

| Schritt | Netz | liest | schreibt |
|---|---|---|---|
| `opendata` | ja | Open-Data-Portal | `external/Stimmbezirk_Wahlergebnis.csv`, `external/Stimmbezirke_2025.geojson` |
| `context_data` | ja | Open-Data-Portal: Tabelle je Raumeinheit, ihre Flächen, die Erläuterung der Indikatoren | `external/` unter den Namen aus `context.files` |
| `papers` | ja | OParl-Liste, neueste zuerst, Abbruch unter dem Periodenbeginn; beim zweiten Mal `modified_since`, `--max-pages` als Probe | `raw/papers.jsonl` |
| `organizations` | ja | OParl-Endpunkt `organizations`: Fraktionen, Ausschüsse, Bezirksvertretungen (Düsseldorf: eine Seite, 58 Objekte, 0,47 s) | `raw/organizations.json` |
| `pdfs` | ja | Download-URLs der Paper, seriell mit Pause, `--limit` | `cache/pdf/*.pdf`, `cache/pdf/manifest.jsonl` |
| `streets_osm` | ja | Overpass je Stimmbezirkspolygon | `raw/streets_per_district.json` |
| `pois_wiki` | ja | Wikidata-SPARQL, Wikipedia-GeoSearch je Stimmbezirk | `raw/wikipedia_dict.json` |
| `texts` | nein | PDFs ohne aktuellen Text | `cache/text/texts.parquet` |
| `voters` | nein | Wahlergebnis-CSV | `processed/wahlbezirke_waehler.parquet`, `processed/wahlbezirke_stadtbezirke.parquet` |
| `context` | nein | Stimmbezirke (Fläche und Wahlberechtigte), Raumeinheiten, Tabelle der Quelle, Wähler | `processed/wahlbezirke_kontext.parquet`, `processed/wahlbezirke_crosswalk.parquet` |
| `streets` | nein | Straßen je Stimmbezirk | `processed/wahlbezirke_strassen.parquet` |
| `pois` | nein | Orte | `processed/wikidata_vis.parquet`, `processed/wikidata_agg.parquet` |
| `dictionary` | nein | Orte und Straßen je Wahlbezirk | `processed/combined_searchdict.parquet` |
| `corpus` | nein | Metadaten und Texte | `interim/papers.parquet` |
| `topics` | nein | Korpus (Texte) | `processed/themen.parquet`, `processed/themen_dokumente.parquet`, `interim/themen_anteile.parquet` |
| `index` | nein | Wörterbuch, Korpus | `processed/inverted_index.parquet` |
| `results` | nein | Wörterbuch, Index, Wähler | `processed/wahlbezirke_auswertung.parquet` |
| `bodies` | nein | Korpus (`id`, `reference`) | `processed/papers_gremien.parquet` |
| `body_hits` | nein | Auswertung, Gremien je Dokument, Stadtbezirke | `processed/wahlbezirke_gremien.parquet`, `processed/gremien.parquet` |
| `weights` | nein | Wörterbuch, Index, Korpus (`id`, `paper_type`), Wähler, Themenanteile | `processed/wahlbezirke_gewichtet.parquet`, `processed/gewichte_begriffe.parquet` |
| `controls` | nein | Auswertung, Kontrollvariablen | `processed/regression_kontrollen.parquet` |
| `parties` | nein | Korpus, Auswertung, Wähler, dazu `raw/organizations.json`, wenn vorhanden | `processed/dokumente_urheber.parquet`, `processed/wahlbezirke_urheber.parquet`, `processed/wahlbezirke_parteien.parquet` |
| `report` | nein | die Ergebnistabellen, Korpus, Stimmbezirks-GeoJSON, mit Fremddaten auch die drei Tabellen der Kontrollvariablen und die Erläuterung der Indikatoren | `site/index.html`, `site/karte.html`, `site/data/` (Parquet, CSV, `wahlbezirke.geojson`, `schema.json`, `dokumente.json`) |

Neben der ersten Ausgabe jedes Schritts liegt `<datei>.stamp.json` mit den SHA-256-Hashes der Eingaben, dem
Settings-Fingerprint, der Code-Version und der Schema-Version. Stimmt alles, ist der Schritt aktuell und wird
übersprungen; sonst läuft er und sagt, warum („Eingabe geändert: texts.parquet", „Code-Version 0.6.0 ->
0.7.0"). `--force` erzwingt, `--dry-run` plant nur. Jeder Lauf druckt je Schritt eine Zeile mit der Anzahl,
auf die er gewirkt hat, und die Sekunden. Der volle Offline-Lauf auf der Referenz dauert rund 16 s, davon 7 s
das Themenmodell, 4 s der Index, je unter 1 s die Gewichtung, die Kontrollvariablen (`context` 0,4 s,
`controls` unter 0,1 s) und 1,4 s die Berichtsseite (2026-10-12, nach dem Rebase auf 08, 05 und 06; ohne
Themenmodell rund 9 s).

## Datenhaltung

```
reference/                 der Datensatz der Arbeit; wird nur gelesen (guard_writable)
context/                   Fremddaten je Raumeinheit mit README (Quelle, Lizenz, Stand, SHA-256); wird nur gelesen
data_root/                 Standard ./data, gitignored; mit profile = "x" liegt alles unter data_root/x/
  external/                Eingaben des Open-Data-Portals, Dateinamen und Formate der Quelle
  raw/                     papers.jsonl, organizations.json, streets_per_district.json, wikipedia_dict.json
  interim/                 papers.parquet (Korpus: Metadaten plus Text)
  interim/                 papers.parquet (Korpus: Metadaten plus Text), themen_anteile.parquet (Themenanteile je Dokument, nicht veröffentlicht)
  processed/               die Ergebnistabellen als Parquet (zstd), je mit Stamp; mit Fremddaten drei mehr
                           (nicht veröffentlicht: papers_gremien und wikidata_agg)
  site/                    die Berichtsseite: index.html (mit Stamp), karte.html (Leaflet) und data/ mit den Download-Dateien
cache_root/                Standard data_root/cache; mit Profil liegen pdf/ und text/ unter cache_root/x/
  pdf/                     <dateiname>.pdf, manifest.jsonl (URL, SHA-256, Größe, Zeit)
  text/texts.parquet       alle Texte mit Extraktorname, PDF-Hash, Herkunft, Zeichenzahl
  http.sqlite              requests-cache; Lebensdauer je Quelle, PDFs nie
```

Eingaben behalten die Formate der Quellen, weil sie Rohdaten sind; alles Abgeleitete ist Parquet und trägt
`georep.schema_version` in den Metadaten. Append-artige Metadaten (`papers.jsonl`, `manifest.jsonl`) bleiben
JSONL. CSV entsteht nur für Menschen (`georep export`). Zwei Läufe auf denselben Eingaben schreiben
byteidentische Parquet-Dateien: alle Ausgaben sind sortiert, Mengen werden zu sortierten Listen.

## Sicherheit: was „nichts geht kaputt" heißt

1. Unter `reference/` schreibt nichts; `Layout.guard_writable` verweigert jeden Pfad darunter, auch über Symlinks.
2. Jeder Schreibvorgang ist atomar: Temporärdatei im Zielverzeichnis, `fsync`, `os.replace`. Ein Abbruch hinterlässt die alte Datei oder die neue, nie eine halbe.
3. Fehlende Eingaben sind `MissingInputError` vor dem Lauf, leere Ergebnisse `EmptyResultError` vor dem Schreiben, falsche Spalten `SchemaError`.
4. Wiederholung ohne Änderung ist ein No-op und sagt das; `--dry-run` zeigt den Plan.
5. Netz: 180 s Timeout je Aufruf, fünf Wiederholungen mit Backoff bei 429 und 5xx, eine Sekunde Pause zwischen Seiten und Dateien; der PDF-Download isoliert Fehler je Datei und berichtet Zähler; Antworten ohne `%PDF` werden abgewiesen.
6. Domänenfehler (`GeorepError`) werden an genau einer Stelle gefangen, am Rand in `cli.main`, mit einer Zeile auf stderr und Exit 1. Vertragsverletzungen (deal) sind Programmierfehler und laufen durch.
7. Caches sehen, was sie sehen müssen: Stamps tragen Eingabe-Hashes, Settings-Fingerprint, Code- und Schema-Version; der Textstore kennt Extraktorname und PDF-Hash; Parquet-Dateien kennen ihr Schema.

## Netz

Alle Quellen sprechen über das `Transport`-Protokoll (`get`, `post`); `requests.Session` erfüllt es, die
Fake-Session in `tests/fakes.py` auch. `make_session` baut Timeout, Retry, User-Agent und requests-cache
(SQLite) mit Lebensdauer je URL-Muster (`cache_pattern`); PDFs werden nie gecacht, sie gehören in den
PDF-Store. Jeder Fetcher wirft nur `FetchError` (Antwort nicht brauchbar) oder `NetworkError` (nicht
erreichbar, Fehlerstatus nach allen Wiederholungen), gesichert durch `deal.raises`.

- OParl: Paper-Seiten neueste zuerst, Abbruch, sobald eine Seite nur noch Paper vor dem Periodenbeginn trägt
  (spart 270 von 365 Seiten); beim zweiten Lauf `modified_since` (letztes `modified` minus ein Tag). Jede
  Seite wird gegen das pydantic-Modell geprüft. Der Server brauchte am 2026-10-09 85 s je Seite.
  `--max-pages N` liest nur die ersten Seiten; der Abrufbericht zählt, wie viele der gesehenen Paper ein
  Urheberfeld tragen, und ist damit die Probe, ob sich am Befund unten etwas geändert hat.
- OParl `organizations`: die Fraktionen, Ausschüsse und Bezirksvertretungen, eine Seite mit 58 Objekten in
  0,47 s (2026-10-11). Der Server der ITK Rheinland setzt `classification` („Fraktion“, „Ausschuss“,
  „Bezirk“, „Gremium“ oder nichts), nie `organizationType`. Der Schritt `parties` bildet daraus
  Organisations-URLs auf Parteien ab; ohne die Datei greifen nur die URL-Endungen aus den Settings.
- Overpass: je Stimmbezirk der Außenring des größten Polygons, um 2 m vereinfacht, als `(poly:"…")`; der
  Filter bildet `network_type="all"` von osmnx nach, mit dem die Daten der Arbeit entstanden. Treue gegen
  die Referenz: `tests/fixtures/http/README.md`.
- Wikidata: ein SPARQL für alle Objekte mit Koordinate in der Verwaltungseinheit (P131*) und Artikel in der
  Sprache; Wikipedia-GeoSearch je Stimmbezirks-Bounding-Box, ein Treffer zählt nur für den Bezirk, dessen
  Box abgefragt wurde und der den Punkt enthält (Verhalten der Arbeit).

Ein voller Abruf von Grund auf dauert Stunden (Hochrechnung 2026-10-11: 5,8 h für 19 108 PDFs, 2,8 GB) und
ist an jeder Stelle wiederaufnehmbar.

## Geometrie

Die Stimmbezirke kommen als GeoJSON in EPSG:4647 und werden einmal ins metrische EPSG:25832 projiziert
(`always_xy=True`); ungültige Polygone repariert `make_valid`, Linien ohne Fläche fallen weg, nie
`buffer(0)`. `PrecinctIndex` hält einen STRtree über die 306 Flächen und ordnet Punkte (lon, lat) zu; die
Vorbedingung prüft den Gradbereich, denn vertauschte Koordinaten sind der klassische Fehler. Zurück nach
lon/lat geht es an genau einer Stelle (`to_lonlat`), für Overpass-Polygone und GeoSearch-Boxen. Die Zuordnung
der Arbeit wird für alle 1996 Orte reproduziert.

## Nähte: Matcher und Extraktor

- `search.matcher.KeywordMatcher` (`add_terms`, `extract(text) -> set[str]`), Implementierung
  `FlashTextMatcher` (reines Python, FlashText 2.7). Der Vertrag steht lesbar in
  `tests/property/oracle_matcher.py`: Treffer an Wortgrenzen (ASCII-Buchstaben, Ziffern, Unterstrich;
  Umlaute sind Grenzen), längster Begriff gewinnt, keine Überlappung, das beendende Grenzzeichen ist
  verbraucht, Groß/Klein zählt nicht. Jeder Ersatz muss `tests/property/test_matcher_contract.py` bestehen;
  der Vertrag ist Mengengleichheit, keine Toleranz.
- `prep.extract.PdfTextExtractor` (`name` als Cache-Schlüssel, `extract(path) -> str`), Implementierung
  `PypdfExtractor`. Normalisierung (Zeilenumbrüche weg, kleingeschrieben) und der Schnitt am Marker
  `betrifft` liegen außerhalb. Ein Ersatz muss den Golden Master der vier Fixture-PDFs bestehen oder seine
  Abweichung dokumentieren; pypdf 6.20.0 reproduziert 197 von 200 Texten der Arbeit zeichengleich.

Gemessen (2026-10-11): der Matcher kostet 4,1 s für 5841 Begriffe über 19 108 Dokumente, 3,8 s davon reines
Python in FlashText; die Extraktion 38 ms je PDF, 17 ms je Seite. Kein Flaschenhals rechtfertigt derzeit
einen Ersatz; die Kandidaten stehen in decisions.md.

## Berichtsseite

Der letzte Schritt `report` (`georep.report.build.build_site`) macht aus den Parquet-Ergebnissen eine einzige
`site/index.html` ohne externe Ressourcen: CSS, JavaScript und beide SVGs inline, nur relative Pfade, Deutsch
mit einer englischen Kurzfassung, hell und dunkel über `prefers-color-scheme`. Die Vorlage
`templates/report.html.j2` ist der Rahmen (Kopf, Fuß, Dialog, Tooltip, Basis-JavaScript); die Abschnitte liegen
als `templates/sections/NN-name.html.j2` in Nummernfolge, je mit optionalem `NN-name.css` und `NN-name.js`, die
der Rahmen in den Stil- und einen eigenen Skriptblock einfügt (`render.sections`; ein `.css` oder `.js` ohne
Vorlage ist ein Fehler). Das Basis-JavaScript bietet `window.georep` (`select(ids, scroll)`,
`showDocuments(terms, title)`, `rows`) für die Skripte der Abschnitte; der Umschalter der Karte liest
`data-class-<kennzahl>` je Fläche und blendet `#legend-<kennzahl>` ein, eine neue Kennzahl ist ein Radio, ein
Attribut (`choropleth(extra_classes=...)`) und eine Legende. Die veröffentlichten Tabellen stehen im Register
`report/tables.py` (Datei, Beschreibung, Spaltendoku, CSV-Regeln, `optional` für profilabhängige Tabellen);
daraus entstehen Downloads, `schema.json`, CSV-Dateien und die Spaltentabelle. Die Seite bleibt unter 1,5 MB
(slow-Test); mit allen Abschnitten sind es 986 KB (gzip 168 KB). Die beiden Abschnitte der Kontrollvariablen
(`32-kontrollvariablen`, `65-abgeleitete-daten`) stehen in `{% if model.controls %}` beziehungsweise
`{% if model.derived %}` und fehlen ohne sie ganz; ihre Zahlen kommen aus
`processed/regression_kontrollen.parquet`, der Satz zur Deutung entsteht aus p, Vorzeichen, R²-Zuwachs und dem
größten standardisierten Koeffizienten, nicht aus festem Text. Reihenfolge: erst die Dateien
unter `site/data/` (die veröffentlichten Tabellen als Parquet kopiert und als CSV mit den Regeln von `georep export`,
`wahlbezirke.geojson` in EPSG:4326, `schema.json`), dann das Modell (`report.model`: frozen dataclasses, Polars
bis zum Schluss, Zeit und Commit sind Eingaben) mit Größe und SHA-256 jeder Datei, dann die Karte
(`report.geometry`: `unary_union` je Wahlbezirk, um 15 m vereinfacht, Flächensumme bis auf 1 % erhalten, formtreu
aus EPSG:25832 auf eine `viewBox` abgebildet) und das Streudiagramm (`report.charts`), zuletzt die Seite
(`report.render`, Jinja2 mit Autoescape; Nachbedingung: jeder Link nach außen steht in `ALLOWED_LINKS` oder
kommt aus den Settings der Fremddaten, `render.model_links`). Die
Choroplethe hat fünf Quantilklassen (weniger, wenn es weniger verschiedene Werte gibt) in einer Blau-Rampe, die
je Modus getrennt gewählt und mit dem Validator der Skill `dataviz` geprüft ist; der Umschalter auf die
Wahlbeteiligung oder auf den Anteil der eigenen Bezirksvertretung tauscht nur CSS-Klassen über
`data-`-Attribute. Begriffe sind Schaltflächen: ein Klick lädt
`data/dokumente.json` nach (`report.documents`: die Dokumente mit Treffer ohne Texte, neueste zuerst, je Begriff
Indizes; der PDF-Link entsteht aus einem gemeinsamen Präfix) und zeigt die Dokumente in einem `<dialog>` mit
Datum, Titel, Drucksache, Art und Urheber; die Orte der Karte tragen Namen und Wahlbezirk. Der Abschnitt
„Urheber und Parteien“ (`sections/38-parteien`) bringt sechs kleine Karten in einem SVG: die 41 Flächen
stehen einmal in `<defs>`, jedes Panel ist ein `<g transform>` mit 41 `<use>` (`charts.party_maps`), und die
Quantilklassen sind je Partei gerechnet. Seine Tabelle je Wahlbezirk schattiert die Parteispalten nicht mit
der Rampe der Karten, sondern mit fünf Tönungen einer Farbe (`--q2` in `--surface`): die Zellen tragen
Zahlen, und die volle Rampe erreicht in der Mitte in keiner Schriftfarbe den Kontrast 4,5 (nachgerechnet in
`sections/38-parteien.css`). Der Abschnitt `15-suche` ist ein Suchfeld nach dem
Combobox-Muster der WAI-ARIA Authoring Practices: `report/search.py` baut je kanonischem Begriff einen Eintrag
(Abkürzung und Langform zusammengezogen, Dokumente beider Schreibweisen vereinigt) und je Wahlbezirksname
einen weiteren, `render_report` legt sie als `<script id="suche-daten" type="application/json">` in die Seite
(rund 144 KB), und `sections/15-suche.js` gleicht Teilstrings auf zwei gefalteten Schlüsseln ab (einmal ohne
Akzente, einmal mit `ä` als `ae`). Die Vorschläge brauchen kein Netz und funktionieren aus `file://`; die
Auswahl markiert über `georep.select` und zeigt die Dokumente über `georep.showDocuments`. Die
Abkürzungsregel steht einmal als `STREET_ABBREVIATIONS` in `search/dictionary.py`, aus der das Wörterbuch und
der Payload lesen; `tests/unit/test_report_js_fold.py` prüft mit `node`, dass JavaScript und Python gleich
falten. `karte.html` ist die zweite Datei und die einzige mit
Fremdressourcen: Leaflet 1.9.4 per Subresource Integrity gepinnt, OpenStreetMap-Kacheln mit Namensnennung,
Flächen und Orte inline als JSON (`</` escaped), eigene Allowlist in `render_map`. Entscheidungen und verworfene
Alternativen stehen in [plan-report-2026-10.md](plan-report-2026-10.md), § 2. Auf der Referenz: 41 Wahlbezirke,
Alternativen stehen in [plan-report-2026-10.md](plan-report-2026-10.md), § 2. Der Abschnitt
`34-gewichtung` („Was ändert die Gewichtung?", Option 06) steht direkt hinter der Regression: eine
Sensitivitätstabelle mit beiden Spalten von Tabelle 5 je Gewichtungsvariante und der Rangkorrelation zur
ungewichteten Quote, darunter die Themen mit ihren stärksten Wörtern. Die Einheitszeile trägt dieselben
Zahlen wie Tabelle 5 (ein Test vergleicht sie); eine Variante ohne Streuung zeigt „—", und fehlt der ganzen
Tabelle die zweite Regression, entfällt die Spaltengruppe. Auf der Referenz: 41 Wahlbezirke, 43 Dateien,
13,4 MB, davon `index.html` 1,13 MB (144 KB Suchdaten, 63 KB die Parteikarten, 33 KB die Gewichtung),
`karte.html` 255 KB, `dokumente.json` 2,3 MB; 1,5 s (2026-10-12).

## Verträge

deal-Verträge stehen an den Batch-Grenzen, nicht in heißen Schleifen: Vorbedingungen (Pflichtspalten,
Begriffe kleingeschrieben und ohne Komma, Koordinaten in Grad, Wahlberechtigte positiv), Nachbedingungen
(eine Zeile je Schlüssel, Listen sortiert und eindeutig, `anzahl_treffer` gleich Mächtigkeit, Wahlbezirke
nur aus den Eingaben, r in [-1, 1], eine Zerlegung ohne Rest über `parts_sum_to`), `raises` an den
Fetchern, `pure` auf kleinen totalen Funktionen (nicht aber auf solchen, die eine Batch-Funktion je
Zeile ruft: `deal.has()` patcht je Aufruf prozessweit, darum trägt `prep.bodies.parse_reference` nur
`deal.safe` und wird über `deal.cases` und crosshair auf Reinheit geprüft). Die
nur aus den Eingaben, r in [-1, 1]), `raises` an den Fetchern, `pure` auf kleinen totalen Funktionen. Die
Gewichtung hat die ihren: jeder Faktor und jedes Dokumentgewicht in [0, 1] (`in_unit_interval`), eine Zeile
je Paar (Wahlbezirk, Dokument), dieselbe Paarmenge wie die Vereinigung in `hits_by_district`, und als
stärkste Zusage, dass die Variante `einheit` genau `anzahl_treffer` reproduziert und die Themenvarianten
diese Zählung zerlegen; beim Themenmodell: genau `k` Themen, Zeilensummen 1 ± 1e-9, jedes Dokument mit Text
einmal. Die
Prädikate liegen in `georep.contracts`, damit dieselbe Eigenschaft überall gleich heißt. `settings.contracts
= "off"` ruft `deal.disable` beim Start; der Overhead liegt unter einem Prozent (2026-10-11). Pydantic
validiert an der Systemgrenze (OParl, Records, Settings), Verträge sichern das Innere; `icontract` wird
nicht gemischt.

Grenzen von deal 4.24.6, umschifft: `deal.raises` vergleicht exakte Typen (darum `NetworkError` statt der
requests-Unterklassen), und der `has()`-Patcher ist nicht reentrant (darum `deal.safe`, nicht `deal.pure`,
auf dem rekursiven `deep_merge`).

## Tests und Prüfungen

| Schicht | Inhalt |
|---|---|
| `tests/unit/` | eine Funktion, ein Verhalten; Vertragsverletzungen je mit Gegenbeispiel |
| `tests/property/` | hypothesis-Invarianten (darunter: Einheitsgewichte reproduzieren die Zählung exakt, Gewichte in [0, 1], Monotonie, Themenzerlegung), das Matcher-Orakel (400 Zufallsfälle), `deal.cases` auf zwölf reinen Funktionen |
| `tests/golden/` | Mini-Fixture (3 Wahlbezirke, 200 Dokumente, Erwartung aus dem Altcode `v0.2.0`) und die volle Referenz (`slow`) gegen die Ergebnisse der Arbeit |
| `tests/bench/` | pytest-benchmark, nur in `nox -s bench` |
| `tests/fixtures/` | Mini-Datensatz (drei Wahlbezirke mit ihren 22 Stimmbezirken), vier PDFs mit Herkunft, eine OParl-Seite, aufgezeichnete Antworten von Overpass, Wikidata, Wikipedia |

Netz kommt in Tests nie von echten Endpunkten; Zeit (`today`), Zufall (hypothesis-Profile) und Netz
(`Transport`, `sleep`) sind Eingaben.

| nox-Session | Was | wo |
|---|---|---|
| `lint`, `typecheck`, `deps`, `test` | Ruff, mypy strict, Lockfile ohne pandas/geopandas/osmnx, schnelle Suite parallel mit Abdeckung als Untergrenze (90 %) | lokal (`uv run nox`) und CI |
| `golden` | die volle Referenz | CI, lokal `uv run pytest -m slow` |
| `bench` | heiße Pfade gegen den letzten gespeicherten Lauf, rot ab 20 % langsamer im Minimum | lokal |
| `profile -- SCHRITT` | ein echter Schritt unter cProfile | lokal |
| `verify` | crosshair über die reinen Funktionen mit Verträgen, rund drei Minuten | lokal |
| `mutate` | pytest-gremlins über `search/` und `analysis/`, einmal pro größerer Änderung; mit `analysis/topics.py` im Ziel dauert die Session sehr lange (jeder Mutant rechnet NMF), darum besser gezielt je Modul | lokal |

Stand 2026-10-12: 310 Tests, schnelle Suite in 20 bis 25 s, Abdeckung 98,6 %; Mutationsquote 79 % über
`search/` und `analysis/` ([mutation-2026-10-11.md](mutation-2026-10-11.md)), 83 % über das neue
`analysis/weights.py` ([mutation-2026-10-12.md](mutation-2026-10-12.md)).

## Bekannte Grenzen

- Ein voller `georep fetch` von Grund auf lief noch nie; ob der OParl-Server `modified_since` beachtet, zeigt erst er.
- Labels, die sich nur durch ein Komma unterscheiden, fallen in der POI-Bereinigung zusammen (Verhalten der Arbeit, durch das Wörterbuch harmlos).
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab; die Tests frieren die Neuberechnung ein (baseline-2026-10-10.md).
- crosshair prüft nur rein-pythonische Funktionen; Polars-Funktionen haben Laufzeitverträge und hypothesis.
- Der OParl-Server liefert für Düsseldorf keine Urheberfelder (`originatorPerson`, `originatorOrganization`,
  `underDirectionOf`): 0 von 19 108 Rohobjekten und keines der sechs Paper der Seite vom 2026-10-09, auch
  der „Antrag FDP“ nicht. Der Urheber ist deshalb aus `paperType`, Titel und Textkopf abgeleitet und deckt
  98,3 % der Dokumente ab; die Quelle `oparl` greift ohne Codeänderung, sobald der Server die Felder füllt.
  Einzelne Mandatsträger (865 Dokumente) bleiben ohne Partei, auch wenn der Titel eine nennt; nennt erst der
  Textkopf den Mandatsträger, zählt das Dokument als unbekannt (die Anreden der Vorlagen würden sonst halbe
  Anträge zu Personen machen).
- Im Wahlbezirk 11 ist Die Linke nicht angetreten (0 Stimmen). Der Abgleich mit dem Stimmenanteil lässt
  solche Bezirke je Partei aus (`angetreten`), sonst läse sich „kein Wahlvorschlag“ wie „keine Zustimmung“.
