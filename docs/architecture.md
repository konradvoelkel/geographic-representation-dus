# Architektur

Stand 2026-10-13, `v0.12.0`. Diese Datei beschreibt, was das Programm ist und wie es gebaut ist. Warum es so
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
| `settings` | `defaults.toml` (stadtneutral) im Paket, darüber das Profil `profiles/<slug>.toml` (gewählt mit `--profile`, `GEOREP_PROFILE` oder `default_profile`, mit `base` auf einem anderen Profil aufbauend), darüber `settings.toml`, `settings.local.toml`, `--settings`, Umgebung `GEOREP_*`; pydantic-settings, unbekannte Schlüssel sind ein Fehler; `fingerprint()` der ergebnisrelevanten Parameter; `profile` (Ordnername je Stadt oder Periode, nicht im Fingerprint), `period.end` optional mit `election` als Wahltag, `analysis.exclude_districts` (Ausreißer von Tabelle 5), `originators` (Muster und Parteien für den Urheber, Option 04), `context` (Fremddaten: Quelle, Lizenz, Dateien, Spaltenform, Ordinalskalen, Variablen, Modelle, Schwellen; der ganze Block fehlt, wo eine Stadt keine hat), `bodies` (Kürzel und Namen der Gremien; ohne `reference_pattern` tragen die Drucksachennummern keines), `topics` (Themenmodell samt Stoppwortquellen `stop_sources`, Namensfenstern und Saat je Ausschuss, Punkt 45), `classify` (der passende Ausschuss: Mindestzahl je Klasse, Schwelle der Restklasse); je Stadt `[city]`, `[precincts]` (Regeln der Quellgeometrie), `[columns.results]` (Spalten und Parteien), `[report]` (Quellen mit Lizenz, Notizen), `[publish]` (welche Städte veröffentlicht werden) |
| `layout` | wo was liegt: `data_root`, `cache_root`, `reference_root`, `profile` (Unterordner `data_root/<profil>/` und `cache_root/<profil>/` für PDFs und Texte, HTTP-Cache geteilt; jedes Profil setzt ihn, `Settings.base_profile` nennt den der Hauptperiode einer Stadt), `context_root` (Fremddaten im Repo, Default `None`), die Dateinamen der Quellen aus dem Profil (`districts_file`, `results_file`, `streets_file`, `district_names_file`; leer = diese Stadt veröffentlicht die Datei nicht); `for_profile` wechselt; `guard_writable` verweigert jeden Pfad unter den beiden nur lesbaren Wurzeln |
| `schema` | die Schema-Versionen der zwei Modellausgaben (Themen, passender Ausschuss) -- importfrei, damit `build_steps` sie ohne scikit-learn kennt (Punkt 45) |
| `io` | atomare Schreibvorgänge (Temporärdatei, fsync, `os.replace`), JSON, Parquet mit `schema_version` in den Metadaten, SHA-256 (`digest`) |
| `http` | Session mit Timeout, Retry mit Backoff, User-Agent, requests-cache je Quelle; `Transport`-Protokoll als Testnaht; `network_errors` wandelt requests-Fehler in `NetworkError` |
| `errors` | Domänenfehler: `MissingInputError`, `EmptyResultError`, `SchemaError`, `CorruptPdfError`, `FetchError`, `NetworkError` |
| `oparl` | OParl 1.1 als pydantic-Vertrag (`OparlPaper` mit den drei Urheberfeldern und `consultation_organizations`, `OparlFile`, `OparlOrganization`, `PaperPage`, `OrganizationPage`), echte Antworten als Fixtures |
| `records` | `PaperRecord`: die Zeile in `raw/papers.jsonl`, aus OParl oder dem Altformat der Arbeit; die vier URL-Listen sind Tupel, weil der Record `frozen` und damit hashbar ist |
| `stores` | `PaperStore` (JSONL, Upsert nach `modified`), `TextStore` (eine Parquet-Datei, Schlüssel Dateiname, Frische über Extraktorname und PDF-Hash) |
| `sources/` | reine Fetch-Funktionen über `Transport`: `opendata` (`fetch_csv`, `fetch_districts_file` für GeoJSON oder Shapefile-Zip), `oparl` (Paper-Seiten), `pdfs` (`PdfStore` mit Manifest), `overpass` (Straßen je Polygon), `wiki` (SPARQL, GeoSearch) |
| `geo` | GeoJSON lesen, nach EPSG:25832 projizieren, `make_valid`, `PrecinctIndex` (STRtree), eine Rückprojektion nach lon/lat; `read_canonical_precincts` für den kanonischen Stand (drei feste Eigenschaften), `read_precincts` für eine Quellgeometrie mit Wahlbezirksattributen, `read_areas` für Flächen, die nur eine Kennung tragen |
| `prep/` | `extract` (PDF-Text hinter `PdfTextExtractor`), `papers` (Korpus), `precincts` (jede Quellgeometrie zu `interim/stimmbezirke.geojson`, GeoJSON oder Shapefile-Zip über pyshp), `voters` (auch `district_units`: Wahlbezirk zu Stadtbezirk über den Crosswalk), `streets` (dazu die Übereinstimmung mit dem Straßenverzeichnis der Wahl), `pois`, `bodies` (Gremium je Dokument aus der Drucksachennummer: `parse_reference` als reine Funktion über `BodyRules`, `classify_papers` als Batch-Grenze), `context` (Fremddaten je Raumeinheit: Stimmbezirkstabelle, Tabelle der Quelle lesen, gewichtetes Mittel je Wahlbezirk): Polars-Funktionen Frame zu Frame. `voters` benennt die Zählspalten beim Lesen auf die kanonischen Namen um (`Wahlberechtigte_insgesamt`, `Waehler`, `<Partei>_Stimmen`), damit jede Wahl dasselbe Schema liefert, liest Wahlbezirk und Stadtbezirk aus einer Spalte oder aus der Stimmbezirksnummer und kennt für einen älteren Zuschnitt zusätzlich `precinct_counts`, `district_results` und `spread_postal` (Briefwahl ohne Geometrie) |
| `search/` | `dictionary` (Wörterbuch je Wahlbezirk), `matcher` (`KeywordMatcher`-Protokoll, FlashText), `index` (invertierter Index) |
| `analysis/` | `topics` (Themenmodell: TF-IDF und NMF; `TopicRules` trägt die Stoppwörter aus dem Profil und die Saat je Ausschuss, `vectorize` ist die eine Textdarstellung), `committees` (passender Ausschuss je Dokument: logistische Regression mit Restklasse), `hits` (Treffer je Wahlbezirk, Join mit Wählern), `regression` (`scipy.stats.linregress`; `regression_pair` rechnet beide Spalten von Tabelle 5 für jede Kennzahlspalte, Ausreißer aus den Settings; ohne Streuung in x oder y gibt es kein Ergebnis, sondern einen `EmptyResultError`), `periods` (zwei Perioden je Wahlbezirk nebeneinander und die Regression ihrer Änderungen), `timeline` (Dokumente je Monat, stadtweit und je Wahlbezirk; die Nachbedingung prüft gegen `hits_by_district`, Option 07) |
| `crosswalk` | Umrechnung von Gebietseinheiten auf Wahlbezirke: `unit_weights` wiegt je Wahlbezirk die Einheiten (Stadtbezirk, Stadtteil) mit einer Zählgröße je Stimmbezirk; der Flächen-Crosswalk auf einen anderen Zuschnitt kommt mit `assign_by_point` (Zuordnung innerhalb eines Zuschnitts über den repräsentativen Punkt), `area_shares` (Flächenanteile, auf die Schnittsumme normiert, mit Abdeckung `min_coverage` als Wächter und `min_share` gegen Splitter: ein Schnittstück unter diesem Anteil der Quellfläche stammt aus der Fließkomma-Arithmetik einer geteilten Grenze und fällt vor der Normierung weg, Punkt 51), `target_weights` und `transfer_counts` (additive Zählgrößen übertragen, `largest_remainder` macht sie ganzzahlig ohne die Summe zu ändern). Verträge: Anteile je Quelle und Gewichte je Ziel summieren zu 1, Spaltensummen bleiben exakt erhalten |
| `pipeline` | Schrittregister: Name, Eingaben, Ausgaben, `run()`, Schema-Version, optionaler Zusatz im Stamp (`extra`, heute nur `report`); Stamps; `run_step`, `run_pipeline`, `build_steps` |
| `bootstrap` | kopiert die Referenz nach `data_root` und baut daraus `papers.jsonl` und den Textstore |
| `contracts` | `configure()` für `settings.contracts` und die Prädikate der deal-Verträge |
| `profiling` | `profile_step`: ein echter Schritt unter cProfile, `.prof` datiert nach `docs/profiling/` |
| `cli` | `georep run, fetch, steps, status, profiles, publish, bootstrap, export, regress, profile`; global `--profile`; `main(argv) -> int`; Exit 0, 1 (Domänenfehler), 2 (Bedienung) |
| `export` | Parquet-Ergebnisse als CSV neben die Dateien; `csv_plan` und `write_csv` nutzt auch der Schritt `report` |
| `report/` | die Berichtsseite: `model` (frozen dataclasses aus den Parquet-Ergebnissen, `format_de`, Spaltendoku; mit Fremddaten `controls` und `derived` für die beiden neuen Abschnitte), `geometry` (Wahlbezirke vereinigen und vereinfachen, SVG-Pfade, GeoJSON), `charts` (Quantilklassen, Legende, `nice_ticks`, `Axes`, Choroplethe, Streudiagramm und Added-Variable-Plots als SVG), `documents` (Dokumente mit Treffer ohne Texte, Begriffe als Indizes, für `dokumente.json`), `terms` (Begriffe mit Treffer je Wahlbezirk, für `begriffe.json`, Punkt 49), `render` (Jinja2 mit Autoescape, Allowlist der Links; `sections` liest die Abschnitte aus `templates/sections/`; `render_map` für die Leaflet-Datei), `search` (Sucheinträge je kanonischem Begriff mit Wahlbezirken, Dokumenten und Art, dazu die Faltung als Spiegel des Abschnitts-Skripts), `literature` (die Einträge der Literaturübersicht: stadtneutral aus `literatur.toml` im Paket, stadtspezifisch aus dem Profil), `tables` (Register der veröffentlichten Tabellen: Datei, Beschreibung, Spaltendoku, CSV-Regeln), `build` (der Schritt `report`: Downloads, Schema, `summary.json`, Seiten), `comparison` und `publish` (`georep publish`: die Stadtseiten zusammentragen und `vergleich.html` bauen) |
| `deploy/` (kein Modul) | außerhalb des Pakets: `bin/georep-monitor.sh` und die systemd-Einheiten des wiederkehrenden Laufs; sie sprechen mit `georep` nur über CLI, Settings und Umgebung (Abschnitt Betrieb, Option 07) |

## Pipeline

Neunundzwanzig Schritte stehen im Register, jeder mit Eingaben, Ausgaben und einer
Schema-Version; welche ein Lauf hat, entscheiden die Settings, und `georep steps` zeigt es
(nachgezählt am 2026-10-13 aus `build_steps`: siebenundzwanzig für Düsseldorf, achtundzwanzig mit
Vergleich, zweiundzwanzig im Periodenprofil 2014 bis 2020, einundzwanzig in der laufenden Periode,
zweiundzwanzig für Mönchengladbach). Netzschritte laufen nur mit `--online` oder über
`georep fetch`; `georep fetch` führt `shapes` und `texts` mit, weil die Netzschritte die Flächen
brauchen und die Texte sonst im Cache liegen blieben. Mit
`topics.k = 0` fehlt der Schritt `topics`, und `weights` rechnet ohne Themenvarianten; `bodies` steht
vor `topics`, weil die Saat der Themen die Gremien je Dokument liest (Punkt 45). Den Schritt
`committees` gibt es nur mit `classify.enabled` und Ausschüssen im Profil. Die drei
Schritte der Kontrollvariablen (`context_data`, `context`, `controls`) gibt es nur mit Fremddaten,
also wenn `context.root` gesetzt ist; `parties` nur, wenn das Profil Fraktionsnamen mitbringt
(`[originators]`). Option 02 bringt zwei weitere Profilschritte: `precincts`
mit `crosswalk.enabled` und `compare` mit `compare.period`; mit `period.dictionary = "base"`
entfallen dafür `streets_osm` und `pois_wiki`. Option 01 bringt `shapes`: er entfällt, wo eine
Periode den Zuschnitt einer anderen rechnet (`precincts.enabled = false`).

| Schritt | Netz | liest | schreibt |
|---|---|---|---|
| `opendata` | ja | die Quellen des Profils (Wahlergebnis, Flächen, optional Straßenverzeichnis und Wahlbezirksnamen) | `external/` mit den Dateinamen der Quelle |
| `shapes` | nein | die Quellgeometrie (GeoJSON oder Shapefile-Zip) und die Regeln aus `[precincts]` | `interim/stimmbezirke.geojson` (drei Eigenschaften, CRS der Quelle) |
| `context_data` | ja | Open-Data-Portal: Tabelle je Raumeinheit, ihre Flächen, die Erläuterung der Indikatoren | `external/` unter den Namen aus `context.files` |
| `papers` | ja | OParl-Liste, neueste zuerst, Abbruch unter dem Periodenbeginn; beim zweiten Mal `modified_since`, `--max-pages` als Probe | `raw/papers.jsonl` |
| `organizations` | ja | OParl-Endpunkt `organizations`: Fraktionen, Ausschüsse, Bezirksvertretungen (Düsseldorf: eine Seite, 58 Objekte, 0,47 s) | `raw/organizations.json` |
| `pdfs` | ja | Download-URLs der Paper, seriell mit Pause, `--limit` | `cache_root/<profil>/pdf/*.pdf`, `…/pdf/manifest.jsonl` |
| `streets_osm` | ja | Overpass je Stimmbezirkspolygon (aus `interim/stimmbezirke.geojson`) | `raw/streets_per_district.json` |
| `pois_wiki` | ja | Wikidata-SPARQL, Wikipedia-GeoSearch je Stimmbezirk (ebenda) | `raw/wikipedia_dict.json` |
| `texts` | nein | PDFs ohne aktuellen Text | `cache_root/<profil>/text/texts.parquet` |
| `precincts` | nein | nur mit `crosswalk.enabled`: eigenes Stimmbezirks-GeoJSON, eigene Wahlbezirksflächen, Stimmbezirke der Hauptperiode als Zielzuschnitt | `processed/stimmbezirke_zuordnung.parquet` |
| `voters` | nein | Wahlergebnis-CSV; mit `crosswalk.enabled` zusätzlich die Wahlbezirks-CSV, die Zuordnung und die Stadtbezirke der Hauptperiode | `processed/wahlbezirke_waehler.parquet`, `processed/wahlbezirke_stadtbezirke.parquet` |
| `context` | nein | Stimmbezirke (Fläche und Wahlberechtigte), Raumeinheiten, Tabelle der Quelle, Wähler | `processed/wahlbezirke_kontext.parquet`, `processed/wahlbezirke_crosswalk.parquet` |
| `streets` | nein | Straßen je Stimmbezirk | `processed/wahlbezirke_strassen.parquet` |
| `pois` | nein | Orte; mit `search.city_facilities` fallen Einrichtungen mit Stadtnamen aus beiden Ausgaben (decisions.md, Punkt 44a) | `processed/wikidata_vis.parquet`, `processed/wikidata_agg.parquet` |
| `dictionary` | nein | Orte und Straßen je Wahlbezirk | `processed/combined_searchdict.parquet` |
| `corpus` | nein | Metadaten und Texte | `interim/papers.parquet` |
| `bodies` | nein | Korpus (`id`, `reference`) | `processed/papers_gremien.parquet` |
| `topics` | nein | Korpus (Texte), mit Saat auch die Gremien je Dokument | `processed/themen.parquet`, `processed/themen_dokumente.parquet`, `interim/themen_anteile.parquet` |
| `committees` | nein | Korpus (Texte), Gremien je Dokument | `processed/papers_ausschuss.parquet`, `processed/ausschuss_zuordnung.parquet` |
| `index` | nein | Wörterbuch, Korpus | `processed/inverted_index.parquet` |
| `timeline` | nein | Korpus, Index, Wörterbuch | `processed/monatsreihe.parquet`, `processed/wahlbezirke_monate.parquet` |
| `results` | nein | Wörterbuch, Index, Wähler | `processed/wahlbezirke_auswertung.parquet` |
| `metrics` | nein | Auswertung, Wörterbuch | `processed/wahlbezirke_kennzahlen.parquet` |
| `body_hits` | nein | Auswertung, Gremien je Dokument, Stadtbezirke | `processed/wahlbezirke_gremien.parquet`, `processed/gremien.parquet` |
| `weights` | nein | Wörterbuch, Index, Korpus (`id`, `paper_type`), Wähler, Themenanteile | `processed/wahlbezirke_gewichtet.parquet`, `processed/gewichte_begriffe.parquet` |
| `controls` | nein | Auswertung, Kontrollvariablen | `processed/regression_kontrollen.parquet` |
| `parties` | nein | Korpus, Auswertung, Wähler, dazu `raw/organizations.json`, wenn vorhanden | `processed/dokumente_urheber.parquet`, `processed/wahlbezirke_urheber.parquet`, `processed/wahlbezirke_parteien.parquet` |
| `compare` | nein | nur mit `compare.period`: die Auswertung und das Wörterbuch beider Perioden | `processed/wahlbezirke_vergleich.parquet` |
| `report` | nein | die Ergebnistabellen, Korpus, die kanonischen Stimmbezirke des gerechneten Zuschnitts (mit Vergleich auch dessen Tabelle), mit Fremddaten auch die drei Tabellen der Kontrollvariablen und die Erläuterung der Indikatoren, mit Straßenverzeichnis auch dieses | `site/index.html`, `site/karte.html`, `site/data/` (Parquet, CSV, `wahlbezirke.geojson`, `schema.json`, `summary.json`, `dokumente.json`) |

Die Tabelle steht in der Reihenfolge des Registers, also in der Reihenfolge, in der `georep run`
die Schritte plant (`georep steps` zeigt sie für ein Profil). Neben der ersten Ausgabe jedes
Schritts liegt `<datei>.stamp.json` mit den SHA-256-Hashes der Eingaben, dem
Settings-Fingerprint, der Code-Version, der Schema-Version und einem Zusatz, den nur der Schritt
`report` füllt (Punkt 53: ein Hash über die Vorlagendateien des Pakets, `literatur.toml` und
`settings.report` — beides steht in keinem Eingabe-Hash und nicht im globalen Fingerprint). Stimmt alles, ist der Schritt aktuell und wird
übersprungen; sonst läuft er und sagt, warum („Eingabe geändert: texts.parquet", „Code-Version 0.6.0 ->
0.7.0"). `--force` erzwingt, `--dry-run` plant nur. Jeder Lauf druckt je Schritt eine Zeile mit der Anzahl,
auf die er gewirkt hat, und die Sekunden. Der volle Offline-Lauf auf der Referenz dauert rund 23 s, davon
7,4 s das Themenmodell, 6,5 s der passende Ausschuss, 4,2 s der Index, je unter 1 s die Gewichtung, die
Kontrollvariablen (`context` 0,4 s, `controls` unter 0,1 s) und 1,5 s die Berichtsseite (2026-10-12, nach
Punkt 45; ohne Themenmodell und Klassifikator rund 9 s).

## Datenhaltung

```
reference/                 der Datensatz der Arbeit; wird nur gelesen (guard_writable)
context/                   Fremddaten je Raumeinheit mit README (Quelle, Lizenz, Stand, SHA-256); wird nur gelesen
data_root/                 Standard ./data, gitignored
  <profil>/                ein Ordner je Lauf: jede Stadt unter ihrem Slug, jede Periode unter ihrem
                           Namen (Punkt 52); Standard ohne --profile ist der Slug der Stadt der Arbeit
    external/              Eingaben der Quellen, Dateinamen und Formate der Quelle (CSV, GeoJSON, Shapefile-Zip)
    raw/                   papers.jsonl, organizations.json, streets_per_district.json, wikipedia_dict.json
    interim/               papers.parquet (Korpus: Metadaten plus Text), stimmbezirke.geojson (kanonisch),
                           themen_anteile.parquet (Themenanteile je Dokument, nicht veröffentlicht)
    processed/             die Ergebnistabellen als Parquet (zstd), je mit Stamp; mit Fremddaten drei mehr; dazu stimmbezirke_zuordnung (Profil mit Crosswalk)
                           (nicht veröffentlicht: papers_gremien, papers_ausschuss und wikidata_agg)
    site/                  die Berichtsseite: index.html (mit Stamp), karte.html (Leaflet) und data/ mit den Download-Dateien
    site/<periode>/        eine Unterseite, wenn eine zweite Wahlperiode gerechnet ist: der Pages-Workflow
                           legt sie hierher, weil der Abschnitt „Zwei Wahlperioden" sie relativ verlinkt
  site/                    was veröffentlicht wird und was GitHub Pages hochlädt: `georep publish` kopiert
                           die erste Stadt aus publish.cities hierher, jede weitere nach site/<slug>/, und
                           legt vergleich.html daneben
cache_root/                Standard data_root/cache
  <profil>/pdf/            <dateiname>.pdf, manifest.jsonl (URL, SHA-256, Größe, Zeit)
  <profil>/text/texts.parquet   alle Texte mit Extraktorname, PDF-Hash, Herkunft, Zeichenzahl
  http.sqlite              requests-cache, von allen Profilen geteilt (der Schlüssel ist die URL);
                           Lebensdauer je Quelle, PDFs nie
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
  (spart 270 von 365 Seiten); beim zweiten Lauf `modified_since` (letztes `modified` minus ein Tag). Nur mit
  diesem Filter liefert der Server gelöschte Paper (`deleted: true`, ohne Datum); sie kommen als
  `FetchReport.deleted_ids` zurück, und `PaperStore.upsert(deleted=…)` nimmt sie aus dem Store
  (Option 07). Jede Seite wird gegen das pydantic-Modell geprüft. Der Server brauchte am 2026-10-09 85 s je Seite.
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
`showDocuments(terms, title)`, `rows`) für die Skripte der Abschnitte. **Lange Tabellen zeigen eine
Vorschau** (Punkt 48): eine Tabelle mit `class="preview"` zeigt Kopf und die ersten
`report.table_preview_rows` Zeilen, und das Makro `more(id, rows, preview)` aus
`templates/macros.html.j2` setzt darunter die Schaltfläche „alle *n* Zeilen zeigen"
(`aria-expanded`, `aria-controls`), die der Tabelle die Klasse `open` gibt. Welche Zeilen sichtbar
sind, entscheidet eine CSS-Regel im Rahmen (`tbody tr:nth-child(n+N)`, dazu `.open` und
`tr.selected`): darum zählt die Vorschau nach dem Sortieren die neue Folge, eine markierte Zeile
klappt von allein auf (`select` setzt `selected`), `@media print` zeigt alles, und ein
`<noscript><style>` im Kopf hebt die Vorschau ohne JavaScript auf. Die Umschalter bedienen
verborgene Zeilen weiter, weil sie im ganzen Dokument suchen. **Umschalter einer Kennzahl** sind ein
gemeinsames Muster (Punkt 46): das Makro `switcher(group, label, variants)` aus `templates/macros.html.j2`
baut ein `fieldset.switcher` mit einem Radio je Variante (das erste ist die Standardansicht und steht auch
ohne JavaScript da), und das Basis-JavaScript tauscht alles, was eine Variante kennt —
`data-class-<variante>` (Stufe der Farbskala, `choropleth(extra_classes=...)` setzt sie je Fläche),
`data-text-<variante>` (angezeigte Zahl oder Spaltenkopf), `data-value-<variante>` (Sortierwert) und die
Legende `#legend-<variante>`. Die **Standardvariante trägt keine Attribute**: sie ist der Zustand, in dem
die Seite ausgeliefert wird, und das JavaScript merkt sich beim Aufbau je beteiligtem Element Klasse, Text
und Sortierwert und stellt sie wieder her. Gesucht wird im ganzen Dokument, nicht im Abschnitt, denn der Umschalter der
Karte färbt auch die Kennzahlspalte der Tabelle je Wahlbezirk; getrennt halten sich die Gruppen dadurch, dass
kein `value` zweimal vorkommt (ein Test hält das fest). Die Skala steht als `data-scale` am Radio: ohne
Angabe die sequenzielle Blau-Rampe `q`, `d` ist die divergierende um das Mittel (orange darunter, neutrales
Grau in der Mitte, blau darüber; aus `color-mix` von `--selected`, `--muted` und `--q2` in `--surface`, also
ohne zweiten Dunkel-Block, mit nachgerechneten Kontrasten im Rahmen). Dieselbe Klasse bedeutet auf beiden
Flächen dasselbe: auf einer SVG-Fläche färbt `q<n>` den `fill` mit der vollen Rampe, in einer Tabellenzelle
denselben Rang als Tönung (`td.q<n>` auf `--p0` bis `--p4`) — die Zellen tragen Zahlen, und die volle Rampe
erreicht in der Mitte keinen Kontrast 4,5; ein Test verlangt darum je Rampe und Stufe beide Regeln.
Die Legenden stehen in einer `aria-live`-Region, und die Legende fester Grenzen entsteht aus den Grenzen
allein (`charts.legend_for`), nicht aus den Daten. Die Karte bietet damit neben der Trefferquote auch Treffer
absolut, Treffer je Begriff im Wörterbuch und die Abweichung vom Stadtmittel (feste Grenzen aus
`[report.diverging]`, keine Quantile: die Abweichung ist eine streng monotone Umrechnung der Quote, und
Quantile ergäben genau deren Klassen); der Abschnitt „Urheber und Parteien" schaltet seine sechs Karten und
seine Parteispalten zwischen Anteil, Abweichung vom Mittel aller Parteien und Verhältnis zum Mittel um. Woher
die Zahlen kommen, steht in `docs/skalierung-2026-10.md`; die Entscheidungen in `docs/decisions.md`,
Punkt 46. „Methode und Grenzen" schließt mit dem Absatz zur Wörterbuchgröße, dessen Korrelationen
`analysis.scaling.dictionary_bias` messen — ohne Streuung entfällt er. Neben Tabelle 5 steht dieselbe Regression mit `x = Treffer je Begriff` (`model.per_term_regression`),
und ihre Deutungssätze entstehen aus den Zahlen, nicht aus festem Text. Die veröffentlichten Tabellen stehen im Register
`report/tables.py` (Datei, Beschreibung, Spaltendoku, CSV-Regeln, `optional` für profilabhängige Tabellen);
daraus entstehen Downloads, `schema.json`, CSV-Dateien und die Spaltentabelle. Die Seite bleibt unter 1,5 MB
(slow-Test); mit allen Abschnitten sind es 1,27 MB. Die beiden Abschnitte der Kontrollvariablen
(`32-kontrollvariablen`, `65-abgeleitete-daten`) stehen in `{% if model.controls %}` beziehungsweise
`{% if model.derived %}` und fehlen ohne sie ganz; ihre Zahlen kommen aus
`processed/regression_kontrollen.parquet`, der Satz zur Deutung entsteht aus p, Vorzeichen, R²-Zuwachs und dem
größten standardisierten Koeffizienten, nicht aus festem Text. Der Abschnitt
`67-literatur` („Literatur und verwandte Arbeiten", zwischen „Abgeleitete Daten" und „Downloads") ist eine
geordnete Liste aus Daten: `report/literature.py` liest die stadtneutralen Einträge aus
`report/literatur.toml` im Paket und stellt die stadtspezifischen aus `[[report.literature]]` des Profils
davor (die Arbeit, auf der die Stadtseite aufsetzt, ist ihr Ursprung und steht oben); jeder Eintrag ist ein
`LiteratureEntry` aus `georep.settings` (Autor, Titel, Jahr, Ort oder Institution, URL mit Abrufdatum oder
DOI, ein Satz zum Beitrag, `pending` für Angaben, die nachzutragen sind). Die URLs kommen über die Daten in
die Allowlist (`render.model_links`), damit keine Zitation eine Konstante mit einem Ortsnamen in den Code
zwingt; `tests/unit/test_report_literature.py` hält die Liste mit dem Abschnitt „Literatur" des README
zusammen, `tests/property/test_literature_props.py` die Rendering-Invariante (jeder Eintrag genau einmal, in
der Reihenfolge der Datei). Reihenfolge: erst die Dateien
unter `site/data/` (die veröffentlichten Tabellen als Parquet kopiert und als CSV mit den Regeln von `georep export`,
`wahlbezirke.geojson` in EPSG:4326, `summary.json`, `schema.json`), dann das Modell (`report.model`: frozen dataclasses, Polars
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
Datum, Titel, Drucksache, Art und Urheber; die Orte der Karte tragen Namen und Wahlbezirk als Datenattribute für den Tooltip und keinen `<title>` — ihre Ebene ist `aria-hidden` und ohne JavaScript nie sichtbar, der Titel erreichte also niemanden (Punkt 50, 73 842 Byte). **Die
Begriffslisten je Wahlbezirk kommen genauso nach** (Punkt 49): sie stehen in
`data/begriffe.json` (`report.terms`, je Wahlbezirk `[Begriff, Dokumente]` absteigend), und
`sections/50-begriffe.js` holt sie beim ersten Aufklappen eines `<details data-terms>`; inline
bleiben die trefferstärksten Begriffe stadtweit, die stadtweiten Begriffe, die fünf häufigsten je
Wahlbezirk und je Wahlbezirk seine Zahl. Beides geht über `georep.loadJson(pfad)`, das je Pfad ein
Versprechen hält (`forget(pfad)` erlaubt einen zweiten Versuch), und scheitert es — aus `file://`
verbietet der Browser `fetch` —, formuliert `georep.offlineNote(was, pfad)` denselben Satz für
beide. Der Klick auf einen Begriff hängt als ein Zuhörer am Dokument, damit auch nachgeladene
Schaltflächen wirken. Der Abschnitt
„Urheber und Parteien“ (`sections/38-parteien`) bringt sechs kleine Karten in einem SVG: die 41 Flächen
stehen einmal in `<defs>`, jedes Panel ist ein `<g transform>` mit 41 `<use>` (`charts.party_maps`), und die
Quantilklassen sind je Partei gerechnet. Seine Tabelle je Wahlbezirk schattiert die Parteispalten nicht mit
der Rampe der Karten, sondern mit fünf Tönungen einer Farbe (`--q2` in `--surface`): die Zellen tragen
Zahlen, und die volle Rampe erreicht in der Mitte in keiner Schriftfarbe den Kontrast 4,5 (nachgerechnet im
Rahmen, wo die Tönung seit Punkt 46 steht). Der Abschnitt `15-suche` ist ein Suchfeld nach dem
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
Alternativen stehen in [plan-report-2026-10.md](plan-report-2026-10.md), § 2. Der Abschnitt
`34-gewichtung` („Was ändert die Gewichtung?", Option 06) steht direkt hinter der Regression: eine
Sensitivitätstabelle mit beiden Spalten von Tabelle 5 je Gewichtungsvariante und der Rangkorrelation zur
ungewichteten Quote, darunter die Themen mit ihren stärksten Wörtern. Die Einheitszeile trägt dieselben
Zahlen wie Tabelle 5 (ein Test vergleicht sie); eine Variante ohne Streuung zeigt „—", und fehlt der ganzen
Tabelle die zweite Regression, entfällt die Spaltengruppe. Mit gesäten Themen (Punkt 45) trägt eine
Themenzeile den Namen ihres Ausschusses aus dem Profil, und die Themen-Tabelle eine Spalte „Gremium"; der
Abschnitt „Gremien" bekommt daneben die Tabelle „Dokumente je passendem Ausschuss" mit der Spalte „davon
ohne Ausschussberatung". Auf der Referenz: 41 Wahlbezirke, 53 Dateien
(mit `summary.json`, Option 01, `ausschuss_zuordnung`, Punkt 45, `wahlbezirke_kennzahlen`, Punkt 46,
und `begriffe.json`, Punkt 49),
13,1 MB, davon `index.html` 0,89 MB (135 KB Suchdaten, 110 KB die beiden Umschalter, 63 KB die
Parteikarten, 33 KB die Gewichtung, 30 KB die Monatsreihe), `karte.html` 232 KB, `dokumente.json` 2,3 MB,
`begriffe.json` 96 KB; 1,6 s (2026-10-13, nach Punkt 50). Die Zerlegung der Seite in ihre Posten steht
in `docs/seitengroesse-2026-10.md`.

Die Stadtseite kennt ihre Nachbarn nicht: wo die Zeile „Weitere Städte" steht, hinterlässt der Rahmen nur die
Marke `<!--georep:weitere-staedte-->`. Erst `georep publish` (`report.publish`) weiß, welche Stadtseiten es
wirklich gibt, trägt sie zusammen (die erste Stadt aus `publish.cities` bleibt an der Wurzel, jede weitere
kommt unter ihren Slug), setzt die Zeile in jede kopierte Seite und baut `vergleich.html` (`report.comparison`:
Tabelle, zwei kleine Choroplethen mit gemeinsamen Quantilklassen, ein Streudiagramm mit einer Farbe und einer
Markenform je Stadt, eigene Allowlist). Gelesen wird je Stadt nur ihr veröffentlichter Ordner
(`summary.json`, `wahlbezirke.geojson`, `wahlbezirke_auswertung.parquet`). Weil `publish` beim Kopieren löscht,
nimmt es nur seinen eigenen Zielordner an: die Standardwurzel, ein leeres Verzeichnis oder eines mit seiner
Markerdatei `.georep-publish`.

Teile der Seite hängen am Profil. Ohne Wahlbeteiligung zur Periode (`report.regression = false`) ist
`model.regression` leer: Streudiagramm, Tabelle 5 und der Umschalter der Karte entfallen, und Kopf wie
englische Kurzfassung sagen, warum. Der Abschnitt „Je Monat" (`sections/55-monate`) zeichnet aus der
Monatsreihe zwei Balken je Monat über dieselbe `Axes`-Klasse wie das Streudiagramm; der Abschnitt
„Laufende Wahlperiode" (`sections/75-laufend`) erscheint nur, wenn `report.monitoring_url` gesetzt ist, und
verweist relativ auf die Unterseite. Der Datenstand im Kopf nennt die Abrufdaten aus den Stamps von
`papers.jsonl` und `manifest.jsonl`, das neueste Dokument und die Zahl der Dokumente ohne Text — alles aus
dem Modell, nichts fest kodiert.

## Betrieb

Die Hauptperiode entsteht in GitHub Actions aus der Referenz (`bootstrap`, `run`, `publish`; der Workflow
liest die Pfade mit `georep paths`, damit kein Ordnername zweimal dasteht). Die laufende Wahlperiode
(Paketprofil `duesseldorf-2025`, Datenordner `2025`) braucht dagegen einen Rechner mit Speicher: sie ruft je Lauf nur Geändertes ab
(`modified_since`), lädt neue PDFs, extrahiert deren Texte und baut ihre eigene Seite unter
`<data_root>/2025/site/`. Das Skript `deploy/bin/georep-monitor.sh` führt einen solchen Lauf, die beiden
systemd-Einheiten daneben machen daraus einen Timer; beide tragen keinen Pfad, alles kommt aus
`%E/georep/monitor.env`. Dieselben Dateien laufen als Nutzereinheit auf kookaburra und als Systemeinheit auf
dem VPS; die Hauptseite kommt aus dem Ordner der Stadt (`<data_root>/<slug>/site/`, Punkt 52), beide Pfade
aus `georep paths`. PDFs und Textstore gehen optional in ein privates R2-Bucket (`cache/2025/…`), die fertigen Seiten
und Tabellen per `rsync` auf den VPS; ohne die Variablen passiert nichts von beidem. Eine `flock`-Sperre
lässt nur einen Lauf zu, ein Fehler bricht mit Exit 1 ab und nennt den Schritt. Installation, Trockenlauf,
Erstabruf und die Handgriffe für R2 und VPS stehen in [../deploy/README.md](../deploy/README.md), die
Entscheidungen in [decisions.md](decisions.md).

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
einmal, jedes Gremienkürzel höchstens einmal und die gesäten Themen zuerst; beim passenden Ausschuss: eine
Zeile je Dokument mit Text, nur gelernte Kürzel oder die Restklasse, jede Wahrscheinlichkeit über der
Schwelle, und die Tabelle zerlegt die Dokumente ohne Rest. Die
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
| `tests/property/` | hypothesis-Invarianten (darunter: Einheitsgewichte reproduzieren die Zählung exakt, Gewichte in [0, 1], Monotonie, Themenzerlegung, die Stoppwörter aus dem Profil sind Token des Modells), das Matcher-Orakel (400 Zufallsfälle), `deal.cases` auf achtzehn reinen Funktionen |
| Messskripte unter `docs/` | was kein Test tragen kann, weil es am Rechner hängt: die Methodikkennzahlen (`methodik-review-2026-10-messung.py`) und die Kohärenz, Saattreue und Kreuzvalidierung des Themenmodells (`themenmodell-2026-10-messung.py`) |
| `tests/golden/` | Mini-Fixture (3 Wahlbezirke, 200 Dokumente, Erwartung aus dem Altcode `v0.2.0`) und die volle Referenz (`slow`) gegen die Ergebnisse der Arbeit; beide mit `as_in_the_thesis(...)`, also mit abgeschalteten eigenen Regeln (decisions.md, Punkte 43 und 44), und beide unter dem Profil der Settings, nicht flach (Punkt 52) |
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
| `verify` | crosshair über die reinen Funktionen mit Verträgen (31 Ziele), rund zehn Minuten (580 s am 2026-10-13); zwei Ziele sind mit Begründung ausgenommen (`parse_reference`: crosshair baut für `re.Pattern \| None` einen symbolischen Regex und bricht ab; `bars`: sein Gegenbeispiel ist eine Zahl mit 300 Stellen) | lokal, und wöchentlich in Actions (`quality.yml`) |
| `alone` | Reihenfolgeunabhängigkeit: jede Testdatei einmal allein (drei parallel), dann die ganze schnelle Suite rückwärts | lokal |
| `mutate` | pytest-gremlins, **eine Sitzung je Modul** mit genau seinen Testdateien (`MUTATION_SCOPE` im `noxfile.py`), drei Arbeiter, einmal pro größerer Änderung; `analysis/topics.py` ist ausgenommen (jeder Mutant rechnet NMF). Der Zuschnitt ist Pflicht, nicht Bequemlichkeit: ohne Abdeckungsdaten läuft jeder Mutant gegen alle übergebenen Tests | lokal, und wöchentlich in Actions (`quality.yml`) mit `-- fast` |

Stand 2026-10-13: 1062 schnelle Tests in rund 55 s, Abdeckung 98,3 %; Mutationsquote 81 % über die
dreizehn Module des Ausbaus ([mutation-2026-10-13.md](mutation-2026-10-13.md): 882 Mutanten, 717
getötet, 165 Überlebende, davon 100 in Vertragsgrenzen), 79 % über `search/` und `analysis/`
([mutation-2026-10-11.md](mutation-2026-10-11.md)), 83 % über `analysis/weights.py`
([mutation-2026-10-12.md](mutation-2026-10-12.md)).

## Bekannte Grenzen

- Ein voller `georep fetch` von Grund auf lief noch nie; ob der OParl-Server `modified_since` beachtet, zeigt erst er.
- Labels, die sich nur durch ein Komma unterscheiden, fallen in der POI-Bereinigung zusammen (Verhalten der Arbeit, durch das Wörterbuch harmlos).
- Die Regel „Einrichtung mit Stadtnamen" urteilt über den Namen, nicht über die Sache: sie trifft auch, was
  eine Stadt im Namen trägt und kein Ort ist (eine Zeitung, eine Ausstellung), und sie trifft nicht, was ohne
  Stadtnamen stadtweit vorkommt („Hofgarten", „Schulweg") — dafür steht die Liste der stadtweiten Begriffe,
  und die urteilt umgekehrt nur über die Häufigkeit, nicht über die Sache. Die Gattungswortliste ist
  deutschsprachig; eine Stadt in einem anderen Sprachraum ersetzt sie im Profil.
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab; die Tests frieren die Neuberechnung ein (baseline-2026-10-10.md).
- crosshair prüft nur rein-pythonische Funktionen; Polars-Funktionen haben Laufzeitverträge und hypothesis.
- Der passende Ausschuss ist eine Schätzung aus Wörtern, keine Aussage darüber, wo ein Dokument hätte
  beraten werden müssen; vier von fünf Dokumenten der Bezirksvertretungen bleiben in der Restklasse
  (decisions.md, Punkt 45c). Sechs Personennamen überleben den Namensfilter, weil sie nie neben einer
  Amtsbezeichnung stehen (ebenda, 45a).
- Der OParl-Server liefert für Düsseldorf keine Urheberfelder (`originatorPerson`, `originatorOrganization`,
  `underDirectionOf`): 0 von 19 108 Rohobjekten und keines der sechs Paper der Seite vom 2026-10-09, auch
  der „Antrag FDP“ nicht. Der Urheber ist deshalb aus `paperType`, Titel und Textkopf abgeleitet und deckt
  98,3 % der Dokumente ab; die Quelle `oparl` greift ohne Codeänderung, sobald der Server die Felder füllt.
  Einzelne Mandatsträger (865 Dokumente) bleiben ohne Partei, auch wenn der Titel eine nennt; nennt erst der
  Textkopf den Mandatsträger, zählt das Dokument als unbekannt (die Anreden der Vorlagen würden sonst halbe
  Anträge zu Personen machen).
- Im Wahlbezirk 11 ist Die Linke nicht angetreten (0 Stimmen). Der Abgleich mit dem Stimmenanteil lässt
  solche Bezirke je Partei aus (`angetreten`), sonst läse sich „kein Wahlvorschlag“ wie „keine Zustimmung“.
