# Plan 01: Städte

Stand 2026-10-11, Branch `feat/01-staedte`. Status: geplant.

Briefing: [../plan-ausbau-2026-10.md](../plan-ausbau-2026-10.md), § 7.1. Alle Zahlen in § 3 sind am 2026-10-11
nachgesehen (Dateien im Scratchpad geladen, Spalten mit Python gezählt, Geometrie mit shapely und `ogrinfo` geprüft);
gegen den OParl-Server lief genau eine Anfrage (§ 3.3). Nichts davon ist im Worktree umgesetzt.

## 1. Ziel und Nicht-Ziel

Ziel: Dieselbe Kette, die heute Düsseldorf rechnet, läuft über ein Profil für eine zweite Kommune am OParl-Server
der ITK Rheinland bis zur Berichtsseite, ohne dass `main` für Düsseldorf anders rechnet (Golden Master bleibt
grün, Seite bleibt unter derselben URL). Erste zweite Stadt ist **Mönchengladbach** (Begründung § 3.7). Dazu
kommt ein Städtevergleich als eigene Seite `vergleich.html` (Tabelle, kleine Karten, ein gemeinsames
Streudiagramm), dessen Zahlen zur Build-Zeit aus den veröffentlichten Seitenordnern beider Städte stammen. Alles
Düsseldorf-Spezifische verlässt den Code und wandert in ein Profil `duesseldorf.toml`; ein zweites Profil
`moenchengladbach.toml` ist der Beweis, dass das reicht.

Der volle Abruf für Mönchengladbach (Metadaten, PDFs, Straßen, Orte: Stunden) ist nicht Teil der
Implementierung. Der Plan bereitet ihn vor (Profil, Fetcher, Fixtures aus aufgezeichneten Antworten, Trockenlauf,
Probe mit einer Seite) und beschreibt ihn als Lauf, den Konrad von Hand startet (Stufe G). Bis die Ergebnisse
dieses Laufs als Paket im Repo liegen, baut `georep publish` die Vergleichsseite nur mit den Städten, deren Lauf
vorliegt, und sagt, welche fehlt.

Nicht Ziel: Neuss, Grevenbroich und der Rhein-Kreis Neuss in diesem Branch (keine Stimmbezirksflächen als Open
Data, § 3.4 bis 3.6; der Weg dorthin steht in § 9); eine Änderung der Methode (Wörterbuch, Matcher, Trefferquote,
Regression bleiben); ein Mehrsprachen- oder Mehrperioden-Mechanismus (Option 2 und 7 nutzen dieselben
Profilschichten, siehe § 9); eine Datenbank oder ein Server.

## 2. Entscheidungen (mit verworfenen Alternativen und Kosten)

| Frage | Entscheidung | Warum, und was verworfen wurde |
|---|---|---|
| Erste zweite Stadt | Mönchengladbach (AGS 05116000, OParl-Body 0011 laut `defaults.toml`) | die einzige der vier Kommunen mit Stimmbezirksflächen als Open Data (Shapefile, DL-DE Zero 2.0), Wahlergebnis je Stimmbezirk im selben Format wie Düsseldorf, 1 185 Wikidata-Orte (Düsseldorf: 995), 33 Wahlbezirke. Verworfen: Neuss (Konrads Vorschlag; 29 Wahlbezirke, Wahlergebnis und Straßenverzeichnis liegen vor, aber keine Flächen; sie müssten aus dem Straßenverzeichnis und OSM-Adressen gebaut werden, § 9), Grevenbroich (keine Flächen, 77 Orte), Rhein-Kreis Neuss (Kreistag, keine Stimmbezirksebene im Ergebnis) |
| Profil je Stadt | eine TOML-Datei je Stadt im Paket, `src/georep/profiles/<slug>.toml`, gewählt über `profile = "…"` (Standard `duesseldorf` in `defaults.toml`), `--profile` und `GEOREP_PROFILE`; Reihenfolge `defaults.toml < profiles/<slug>.toml < settings.toml < settings.local.toml < --settings < Umgebung` | das Profil enthält alles Stadtspezifische an einem Ort mit Begründungen; `defaults.toml` wird stadtneutral (Option 10). Verworfen: eine `[city]`-Tabelle mit allen Städten in einer Datei (die Tabellen `sources`, `columns`, `search`, `report` müssten je Stadt dupliziert werden, der tiefe Merge wüsste nicht, welche gilt); nur `--settings settings.<stadt>.toml` ohne Profilschicht (Konrads `settings.local.toml` mit `data_root` läge dann *unter* dem Stadtprofil und ein vergessenes `--settings` überschriebe Düsseldorfs Daten mit Mönchengladbachs Lauf) |
| Layout je Stadt | `Layout.from_settings` hängt den Slug an: `data_root/<slug>/…`, `cache_root/<slug>/pdf` und `…/text`; `http.sqlite` bleibt geteilt (Schlüssel ist die URL); `reference_root` kommt aus dem Profil (`./reference` für Düsseldorf, `./reference/moenchengladbach` für die zweite Stadt) | zwei Städte können denselben `data_root` und `cache_root` aus `settings.local.toml` nutzen, ohne sich zu überschreiben; Dateinamen der OParl-PDFs (`00252290.pdf`) sind je Body vergeben und kollidierten sonst im geteilten Cache. Kosten: Düsseldorfs Dateien ziehen einmalig von `data/` nach `data/duesseldorf/` und von `cache/pdf` nach `cache/duesseldorf/pdf` (dokumentierter Handgriff, oder `bootstrap && run` neu, 7 s); README, `pages.yml`, `georep status` nennen den neuen Pfad. Verworfen: `data_root` je Profil explizit setzen (siehe oben: `settings.local.toml` gewinnt über das Profil) |
| Stimmbezirke kanonisch | neuer Offline-Schritt `precincts`: aus der Rohdatei (`external/`, Format der Quelle: GeoJSON oder Shapefile-Zip) entsteht `interim/stimmbezirke.geojson` mit festen Eigenschaften `stimmbezirk` (Text), `wahlbezirk` (Zahl), `wahlbezirk_name` (Text) und dem `crs`-Mitglied der Quelle; `streets_osm`, `pois_wiki` und `report` lesen nur noch diese Datei | die Regeln (welche Eigenschaft die Nummer trägt, wie der Wahlbezirk daraus folgt, woher die Namen kommen) sind je Quelle verschieden und gehören an eine Stelle; die Koordinaten bleiben unverändert, darum rechnet Düsseldorf numerisch exakt wie heute (4647 → 25832 in einem Schritt). Verworfen: `read_precincts` mit immer mehr Parametern (jeder Leser wüsste von jeder Quelle); Umprojektion auf EPSG:4326 im kanonischen GeoJSON (zwei Transformationen statt einer, Rauschen an Bezirksgrenzen, Golden Master der 1 996 Orte in Gefahr) |
| Shapefile lesen | `pyshp` 3.1.6 (reines Python, MIT, keine Abhängigkeiten, Python ≥ 3.9) liest `.shp`/`.dbf`/`.prj` direkt aus dem Zip; Eintrag in `decisions.md`, `nox -s deps` prüft weiter | Mönchengladbach liefert nur Shapefile. Verworfen: `fiona`/`pyogrio` (GDAL-Binärwheels, 20 MB, mehr Angriffsfläche); Konvertierung von Hand mit `ogr2ogr` (nicht aus `georep fetch` reproduzierbar, CI hat kein GDAL); geopandas (verboten) |
| Wahlergebnis-Quelle | die votemanager-Präsentation der ITK Rheinland (`wep.itk-rheinland.de/vm/prod/kw_2025/<AGS>/daten/opendata/…`) als zweite Quellform neben dem Portal-CSV; Spalten `A`, `B`, `D1…Dn` werden über das Profil auf die kanonischen Namen der Arbeit abgebildet (`Wahlberechtigte_insgesamt`, `Waehler`, `<Partei>_Stimmen`) | Düsseldorfs Portal-CSV ist Zelle für Zelle der votemanager-Export mit umbenannten Spalten (§ 3.1); dieselbe Quelle gibt es für alle Kommunen der ITK Rheinland und, mit gleichem Format, bei citeq, kdvz und kdo (Option 10). Die kanonischen Namen bleiben die der Arbeit, damit Golden Master und die Optionen 3 und 4 keine Umbenennung erleben. Verworfen: neue schlanke Namen (`wahlberechtigte`, `waehler`): hätte `tests/fixtures/mini/expected/` entwertet und jede Option mit Wählerdaten berührt |
| Wahlbezirk aus der Stimmbezirksnummer | `columns.results.district` darf leer sein; dann gilt `district_from_precinct = [start, stop]` als Zeichenausschnitt der Stimmbezirksnummer (Mönchengladbach `"10401"[1:3]` → 4, Neuss `"0011"[0:3]` → 1); dieselbe Regel in `[precincts]` für die Geometrie | votemanager führt den Wahlbezirk nicht als Spalte; die Zuordnung steckt in der Nummer und ist für alle drei Städte durch Summenvergleich mit der Wahlbezirks-CSV bestätigt (§ 3.2 bis 3.4). Verworfen: eine Zuordnungstabelle Stimmbezirk → Wahlbezirk als weitere Datei (redundant, veraltet still) |
| Wahlbezirksnamen | aus der Wahlbezirks-CSV von votemanager (`…-Ratswahl-Wahlbezirk.csv`), wenn die Geometrie keine Namen trägt; sonst aus der Geometrie wie bei Düsseldorf | das Shapefile kennt nur `Nummer`; die Namen („Rheindahlen/Mennrath") stehen in der Ergebnisdatei je Wahlbezirk. Verworfen: Namen im Profil tippen (33 Zeilen, fehleranfällig, nicht aus `georep fetch` reproduzierbar) |
| Geometriestand | das Shapefile vom 2022-06-08 (Landtagswahl 2022) wird verwendet; `prep/streets.py` misst die Übereinstimmung mit dem Straßenverzeichnis 2025 und die Seite nennt sie | 175 der 179 Urnen-Stimmbezirke 2025 kommen im Shapefile vor, alle 33 Wahlbezirkspräfixe; gerechnet wird je Wahlbezirk (Vereinigung), kleine Neuzuschnitte innerhalb eines Wahlbezirks fallen heraus. Verworfen: auf Flächen von 2025 warten (gibt es nicht als Open Data; Frage 3) |
| Städtevergleich | eigene Seite `vergleich.html` an der Wurzel des veröffentlichten Ordners, gebaut vom neuen Befehl `georep publish`; jede Stadtseite bekommt im Kopf eine Zeile „Weitere Städte: … · Städtevergleich" | die Zahlen kommen aus zwei Läufen, also aus zwei Layouts; ein Schritt der Stadt-Pipeline kann sie nicht kennen. Das Seitenbudget (1,5 MB je `index.html`) bleibt unberührt. Verworfen: Vergleichsabschnitt in jeder `index.html` (doppelt, Budget, Abhängigkeit zwischen Läufen) |
| Schnittstelle des Vergleichs | `publish` liest je Stadt nur den veröffentlichten Ordner `data/<slug>/site/`: `data/summary.json` (neu, Kernzahlen und Regression als JSON), `data/wahlbezirke.geojson` (EPSG:4326, mit Kennzahlen), `data/wahlbezirke_auswertung.parquet`; es kopiert die Stadtordner nach `data/site/` (Düsseldorf an die Wurzel, andere Städte nach `data/site/<slug>/`) und schreibt `vergleich.html` | die Stadtseite ist damit die Schnittstelle, nicht die Zwischenergebnisse; Option 7 (Monitoring) und Dritte lesen `summary.json` genauso. Düsseldorf bleibt an der Wurzel, damit die veröffentlichte URL und das Repo (`…-dus`) stimmen. Verworfen: Landing-Page an der Wurzel (bricht Links und die Erwartung aus README und STATUS) |
| Stadtpaket für CI | die Ergebnisse von Konrads vollem Lauf kommen als Paket nach `reference/moenchengladbach/` (`external/`, `raw/papers.jsonl`, `raw/streets_per_district.json`, `raw/wikipedia_dict.json`, `text/texts.parquet`); `bootstrap` kennt dieses Format neben dem Altformat der Arbeit; `pages.yml` baut daraus die zweite Seite ohne Netz | wie Düsseldorf: reproduzierbar aus dem Repo, Golden Master aus dem einmaligen echten Lauf. Größe geschätzt 10 bis 20 MB (Düsseldorfs Referenz: 82 MB). Verworfen bis zur Antwort auf Frage 2: R2-Bucket (Konrads Antwort zu Option 7 nennt ihn für größere Daten; für 20 MB ist Git einfacher und CI braucht kein Secret) |
| Ausreißer der Regression | `[analysis] exclude_districts` je Profil (Düsseldorf `[1, 10]` wie Tabelle 5; Mönchengladbach `[]` bis zum ersten Lauf, dann die beiden höchsten Trefferquoten nach derselben Regel wie die Arbeit) | `OUTLIERS = (1, 10)` in `report/model.py` ist ein Düsseldorf-Literal. Verworfen: automatische Regel „zwei höchste" im Code (die Arbeit hat die Bezirke benannt, nicht eine Regel; eine Regel wäre Option 6) |
| Erlaubte Links der Seite | `ALLOWED_LINKS` wird aus Konstanten (Repository, Arbeit, Architektur, OSM, Wikidata, Wikipedia, CC0, ODbL, DL-DE) und den URLs aus `[report.sources]` und `[city]` des Profils gebaut; die Nachbedingung von `render_report` bleibt | die Quellen und Lizenzen sind je Stadt verschieden und müssen wörtlich auf die Seite; Links aus dem Profil sind per Konstruktion erlaubt, Links aus Daten weiterhin nicht. Verworfen: Allowlist pro Stadt im Code |
| Netzprobe | `georep fetch papers --max-pages N` (reicht `max_pages` von `fetch_papers` durch) und `--dry-run` für alle Netzschritte; der volle Lauf bleibt Konrads Handgriff (Stufe G) | Konrads Vorgabe: Abrufe nur stichprobenartig, rund fünf Minuten. Verworfen: ein eigener Befehl `probe` (eine Option weniger ist besser) |

## 3. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

### 3.1 Düsseldorf heute, und was im Code Düsseldorf-spezifisch ist

`grep -rn "Düsseldorf\|0015\|Q1718\|duesseldorf\|Stimmbezirke_2025\|Stimmbezirk_Wahlergebnis\|betrifft\|4647" src/`
ohne `defaults.toml` findet (2026-10-11):

- `src/georep/defaults.toml`: Endpoint Body 0015, beide Portal-URLs, `entity = "Q1718"`, `columns.*` mit den Düsseldorfer Spaltennamen, `search.exclude` mit 63 Düsseldorfer Stadtteil- und Stadtbezirksnamen, `text_split_marker = "betrifft"`, Periode 2020-09-13 bis 2025-09-14.
- `src/georep/layout.py:78,82`: Dateinamen `external/Stimmbezirk_Wahlergebnis.csv` und `external/Stimmbezirke_2025.geojson`.
- `src/georep/report/render.py:25`: `OPENDATA = "https://opendata.duesseldorf.de/"`; `DL_DE_BY`/`DL_DE_ZERO` mit dem Kommentar zu den Düsseldorfer Datensatzseiten; `ALLOWED_LINKS` als Konstante.
- `src/georep/report/geometry.py:168`: `"name": "Kommunalwahlbezirke Düsseldorf 2025"`.
- `src/georep/report/model.py`: `OUTLIERS = (1, 10)`; `_VOTER_COLUMNS` mit den sechs Düsseldorfer Parteispalten und „(1 bis 41)".
- `src/georep/report/templates/report.html.j2`: `<title>`, `<meta description>`, `<h1>`, Lead, englische Kurzfassung, Abschnitt „Methode" („Open-Data-Portal der Stadt Düsseldorf", „ab dem ersten „betrifft""), Fußzeile mit den Düsseldorfer Lizenzen und „Landeshauptstadt Düsseldorf".
- `src/georep/report/templates/map.html.j2:7`: „Die 41 Düsseldorfer Kommunalwahlbezirke".
- `src/georep/sources/opendata.py:1`, `src/georep/geo.py:5,55`, `src/georep/prep/extract.py:4`: Docstrings („Open-Data-Portal Düsseldorf", EPSG:4647, „Düsseldorfer Vorlagenkopf"); nur Text.
- Tests, die Düsseldorf voraussetzen und das weiter dürfen (Standardprofil): `tests/unit/test_settings.py` (Endpoint 0015, „Düsseldorf" in `exclude`, 63 Einträge), `tests/unit/test_sources_osm_wiki.py` (Q1718), die Fixtures unter `tests/fixtures/`.

Düsseldorfs Wahlergebnis im Portal ist der votemanager-Export: `reference/external/Stimmbezirk_Wahlergebnis.csv`
(65 982 Bytes, latin-1 mit UTF-8-BOM, `;`, 467 Zeilen: 306 Urnen- und 161 Briefwahlbezirke, 35 Spalten) gegen
`https://wep.itk-rheinland.de/vm/prod/kw_2025/05111000/daten/opendata/Open-Data-05111000-Ratswahl-Stimmbezirk.csv`
(57 448 Bytes, UTF-8 ohne BOM, 467 Zeilen, 32 Spalten): die 25 Zahlenspalten sind in allen 11 675 Zellen gleich.
Das Portal hat die Spalten umbenannt (`A1` → `Wahlberechtigte_ohne_Sperrvermerk_W`, `A2` → `…_mit_Sperrvermerk_W`,
`A3` → `…_nicht_im_Waehlerverzeichnis`, `A` → `Wahlberechtigte_insgesamt`, `B` → `Waehler`, `B2` →
`Davon_mit_Wahlschein`, `C` → `Ungueltige_Stimmen`, `D` → `Gueltige_Stimmen`, `D1` → `CDU_Stimmen`, `D2` →
`GRUENE_Stimmen`, `D3` → `SPD_Stimmen`, `D4` → `FDP_Stimmen`, `D5` → `Die_Linke_Stimmen`, `D6` → `AfD_Stimmen`, `D7`
bis `D17` die übrigen elf Listen) und drei Spalten `Kommunalwahlbezirk`, `Stadtbezirk`, `Stadtteil` vorangestellt. Die
Düsseldorfer Stimmbezirksnummer kodiert den Stadtteil, nicht den Wahlbezirk (`0101` liegt in Wahlbezirk 41); die
Spalte `Kommunalwahlbezirk` bleibt dort nötig. STATUS.md: die Portaldatei heißt inzwischen `…_Stimmbezirke_1.csv`.

Die votemanager-Präsentation einer Kommune liegt unter `https://wep.itk-rheinland.de/vm/prod/kw_2025/<AGS>/`;
`daten/opendata/open_data.json` listet die CSV-Dateien je Wahl und Ebene (`Gemeinde`, `Wahlbezirk`, `Stimmbezirk`,
bei Mönchengladbach auch `Stadtbezirk`), dazu `opendata-strassen.csv` (Straßenverzeichnis) und
`opendata-wahllokale.csv`; `daten/api/termin.json` nennt die Wahl-IDs, `daten/api/wahl_<id>/ergebnis_<gebiet>_0.json`
die Parteien in der Reihenfolge der Spalten `D1…Dn` (Legende). Eine Lizenzangabe steht nicht auf diesen Seiten
(`config.json` trägt `"lizenz": true`, `lizenz.html` antwortet 404); siehe Frage 4.

### 3.2 Mönchengladbach (AGS 05116000, Wikidata Q2758)

| Datei | URL | Größe, Format | Inhalt | Lizenz |
|---|---|---|---|---|
| Wahlergebnis je Stimmbezirk | `https://wep.itk-rheinland.de/vm/prod/kw_2025/05116000/daten/opendata/Open-Data-05116000-Ratswahl-Stimmbezirk.csv` | 30 574 Bytes, UTF-8 ohne BOM, `;` | 249 Zeilen (179 Urnen `W`, 70 Briefwahl `B`), 28 Spalten: `datum;wahl;ags;gebiet-nr;gebiet-name;max-schnellmeldungen;anz-schnellmeldungen;A1;A2;A3;A;B;B2;C;D;D1;…;D13`. `gebiet-nr` fünfstellig (`10401` = Stadtbezirk 1, Wahlbezirk 04, Stimmbezirk 01; Briefwahl `10497`…, dort `A` leer). Legende, durch Spaltensummen gegen `wahl_89/ergebnis_ebene_3_id_2_0.json` bestätigt: D1 CDU 31 834, D2 SPD 27 229, D3 GRÜNE 8 242, D4 AfD 15 079, D5 FDP 2 666, D6 Die Linke 5 382, D7 Die PARTEI 1 865, D8 dieBasis 102, D9 BSW 2 031, D10 FREIE WÄHLER 175, D11 Einzelbewerber Jansen, Erik 46, D12 Volt 1 267, D13 WerteUnion 81. Summen: A 204 219, B 96 880, D 95 999, Beteiligung 47,4 %. Wahlbezirk aus `gebiet-nr[1:3]`: Summen von A, B, D, D1 je Präfix stimmen für alle 33 Wahlbezirke mit der Wahlbezirks-CSV überein; Wahlberechtigte je Wahlbezirk 5 303 bis 7 108 | nicht angegeben (Frage 4) |
| Wahlbezirke (Namen, Summen) | `…/Open-Data-05116000-Ratswahl-Wahlbezirk.csv` | 4 429 Bytes | 33 Zeilen, `gebiet-nr` `01`…`33`, `gebiet-name` z. B. `Rheindahlen/Mennrath`, `Alter Markt/Gründerzeitviertel`, `Amtsgericht/Innenstadt`, `Wickrath-Land`; gleiche Zahlenspalten | wie oben |
| Straßenverzeichnis | `…/opendata-strassen.csv` | 99 117 Bytes, UTF-8, `;` | 1 905 Zeilen, Spalten `datum;ags;Strassen-Name;Hausnummern-Bereich;PLZ;Ortsteil;Bezirk-Nr`; 1 568 Straßennamen, 1 341 davon in genau einem Stimmbezirk, 565 Zeilen mit Hausnummernbereich (`12-45,60-86 ger.`), `Ortsteil` leer | wie oben |
| Wahllokale | `…/opendata-wahllokale.csv` | 33 116 Bytes | 248 Zeilen, Spalten `datum;ags;Bezirk-Nr;Bezirk-Name;Bezirk-Art;Wahlraum-Bezeichnung;Wahlraum-Adresse;Wahlraum-Barrierefrei;Wahlraum-Barrierefrei-Ergaenzung`; `Bezirk-Art` W 179, B 70 | wie oben |
| Stimmbezirksflächen | `https://geoportal.moenchengladbach.de/wms/Hotlinks/OpenData/Wahlen_EPSG25832_SHAPE.zip` (Datensatz `wahlen_1655185102` auf Open.NRW: „Wahlen", Stadt Mönchengladbach, Ressource vom 2022-06-14, Metadaten geändert 2026-09-17, „Aktualisierung nach Bedarf") | 199 548 Bytes Zip; darin `Wahlen_EPSG25832_SHAPE/Stimmbezirke_MG.{shp,shx,dbf,prj}` (shp 396 948 Bytes) und `Wahllokale_MG.*`, Dateidatum 2022-06-08 | 180 Polygone, Attribute `OBJECTID`, `Nummer` (fünf Zeichen, `10401`), `SHAPE_STAr`, `SHAPE_STLe`; `.prj` ETRS89/UTM 32N = EPSG:25832; alle gültig, keine Überlappung über 1 m², Flächensumme 170,47 km² (Stadtfläche), 24 173 Stützpunkte, Bounding Box 310 651–327 694 / 5 662 523–5 680 462. Als GeoJSON 1 279 633 Bytes (25832) bzw. 635 054 Bytes (4326, sechs Nachkommastellen). Gegen 2025: 175 der 179 Urnenbezirke gleich; nur 2025: `11006`, `21406`, `32906`, `40106`; nur 2022: `10506`, `11204`, `21505`, `32405`, `32805`; alle 33 Wahlbezirkspräfixe in beiden. `Wahllokale_MG`: 180 Punkte mit `Adresse`, `Bezeichnun`, `Wahlkreis`, `Stimmbezir`, `Strasse`, `Hausnummer`, `PLZ`, `Stadt`, `Gkz` | Datenlizenz Deutschland – Zero – Version 2.0 (laut Open.NRW) |
| Stadtteile (für `search.exclude`) | `https://opendata.moenchengladbach.de/api/explore/v2.1/catalog/datasets/stadtteildemografie-20241231/exports/json` | 327 956 Bytes JSON | 44 Zeilen mit `stadtteilschluessel`, `stadtbezirk`, `stadtteil`, Geometrie; Stadtteile: Am Wasserturm, Bettrath, Hoven, Bonnenbroich, Geneicken, Bungt, Dahl, Eicken, Flughafen, Geistenbeck, Giesenkirchen-Mitte, Giesenkirchen-Nord, Gladbach, Grenzlandstadion, Hardt-Mitte, Hardter Wald, Hardterbroich, Pesch, Hauptquartier 2, Hehn, Heyden, Hockstein, Holt, Lürrip, Mülfort, Neuwerk-Mitte, Odenkirchen-Mitte, Odenkirchen-West, Ohler, Pongs, Rheindahlen-Land, Rheindahlen-Mitte, Rheydt, Sasserath, Schelsen, Schloss Rheydt, Schmölderpark, Schrievers, Uedding, Venn, Waldhausen, Wanlo, Westend, Wickrath-Mitte, Wickrath-West, Wickrathberg, Windberg; Stadtbezirke Nord, Ost, Süd, West | CC BY-SA 4.0 (nur als Quelle der Namensliste, nicht veröffentlicht) |
| Orte | Wikidata-SPARQL wie `sources/wiki.py` mit `Q2758` | — | 1 185 Objekte mit Koordinate, P131* Mönchengladbach und deutschem Artikel (Düsseldorf: 995); GeoSearch je Stimmbezirk: 179 Abfragen | CC0 |
| Ratsdokumente | OParl Body 0011 (`defaults.toml`), nicht abgefragt (die eine erlaubte Anfrage ging an Neuss, § 3.3) | — | Umfang unbekannt; Schätzung nach Größe (270 000 Einwohner, Rat plus vier Bezirksvertretungen) 8 000 bis 12 000 Vorlagen 2020–2025, also 40 bis 60 Seiten mit `stop_when_older`, 1,5 bis 2 GB PDF, 3 bis 5 h Abruf bei 1 s Pause | Ratsinformationssystem; die Seite nennt nur Kennungen |

Die Kommunalwahl fand in ganz NRW am 13.09.2020 und 14.09.2025 statt; die Periode aus `defaults.toml` gilt
unverändert. Auf den Portalen Open.NRW (`ckan.open.nrw.de`, Suche `Stimmbezirke 2025`, `Wahl Mönchengladbach`:
null Treffer), GovData (`Stimmbezirke Kommunalwahl 2025`: 40 Treffer, keiner der vier Kommunen) und
`opendata.moenchengladbach.de` (29 Datensätze, kein Wahl-Datensatz) gibt es nichts Weiteres für 2025.

### 3.3 Neuss (AGS 05162024, Wikidata Q2948, OParl Body 0009)

- OParl, die eine Anfrage dieser Planung (2026-10-11 23:46, `GET /Oparl/bodies/0009/papers`): 200 OK in 5,2 s
  (nicht 85 s), 426 567 Bytes, 200 Paper, `body` überall `…/bodies/0009`, Datumsbereich 2026-06-03 bis 2026-10-07
  (neueste zuerst), `pagination` ohne `totalElements` wie bei Düsseldorf, `links.next` = `?page=2`. IDs
  `…/bodies/0009/papers/vo/30449`, `reference` wie `41/0315/2026`, `paperType` unter anderem `Anfrage`, `Antrag`,
  `Antrag CDU`, `Antrag SPD`, `Antrag B90 Die Grünen`, `Antrag DIE LINKE`, `Antrag AFD`, `Beratungsunterlage`,
  `Mitteilung der Verwaltung`, `ISN Beratungsunterlage` (Infrastruktur Stadt Neuss). 67 von 200 ohne `mainFile`,
  164 mit `auxiliaryFile` (`primary_file` greift). Dateien `…/bodies/0009/downloadfiles/00252290.pdf`: derselbe
  Namensraum wie Düsseldorfs `004394xx.pdf`, darum der Cache je Stadt (§ 2). Hochrechnung: 200 Paper in vier
  Monaten, rund 3 000 je Wahlperiode, 15 Seiten. Die Seite liegt im Scratchpad und kann in Phase 3 als
  Fixture `tests/fixtures/oparl/papers_page_0009.json` dienen (Vertrag für Paper ohne `mainFile`).
- Wahlergebnis: `…/kw_2025/05162024/daten/opendata/Open-Data-05162024-Ratswahl-Stimmbezirk.csv`, 16 007 Bytes,
  130 Zeilen (90 W, 40 B), 27 Spalten (`D1…D12`: CDU, SPD, GRÜNE, AfD, FDP, Die Linke, UWG/Freie Wähler Neuss,
  TIERSCHUTZ, Aktiv für Neuss, Die PARTEI, BSW, Neuss JETZT!, per Summen bestätigt). Wahlbezirk = `gebiet-nr[0:3]`
  (`0011` → 1), bestätigt für alle 29 gegen `…-Ratswahl-Wahlbezirk.csv` (3 784 Bytes); A 117 834, B 61 630,
  Beteiligung 52,3 %; Wahlberechtigte je Wahlbezirk 3 574 bis 4 633. Straßenverzeichnis 55 309 Bytes, 1 105 Zeilen,
  1 041 Straßen, 988 in genau einem Stimmbezirk; Wahllokale 15 863 Bytes, 130 Zeilen.
- Geometrie: keine. Das Kreisportal `opendata.rhein-kreis-neuss.de` (OpenDataSoft, 430 Datensätze, Katalog als
  JSON geladen) hat für Neuss `stadt-neuss-2024-europawahl-nach-wahlbezirken` (CC0, 140 Zeilen), aber nur als
  Wahllokal-**Punkte** (`geo_point_2d`), keine Flächen; dasselbe gilt für alle acht Kreiskommunen und den Kreis
  (`rhein-kreis-neuss-2024-europawahl-nach-wahlbezirken`, 498 Punkte). `Kreistagswahl-2020-Stimmbezirke` (63 Zeilen)
  ist ohne Geometrie. Die Stadt führt eine „Wahlkarte" im Stadtplan-Viewer und ein GIS (GeoAS), veröffentlicht die
  Flächen aber nicht; Kontakt `geodaten@stadt.neuss.de`. Die Statistik-Broschüre
  `statistik-neuss_wahlen_KW2025.pdf` (970 188 Bytes, 08.10.2025) listet die 29 Wahlbezirke mit Namen und
  Kreistagswahlbezirk (Abb. 1) und alle Stimmbezirksergebnisse im Anhang (30 Seiten), nichts Maschinenlesbares.
- Orte: 160 Wikidata-Objekte (SPARQL mit Q2948).

### 3.4 Grevenbroich (AGS 05162008, Wikidata Q3973, OParl Body 0013)

Wahlergebnis `Open-Data-05162008-Ratswahl-Stimmbezirk.csv`: 8 172 Bytes, 69 Zeilen (44 W, 25 B), 26 Spalten
(`D1…D11`: SPD, CDU, GRÜNE, FDP, MEIN GREVENBROICH, UWG, GGV, AfD, DIE LINKE, Einzelbewerber Mathieu Boulay, Die
PARTEI; bestätigt); 25 Wahlbezirke (`gebiet-nr` `1`…`25`, Präfixregel `[0:3]` bestätigt); A 51 977, B 28 860.
Straßenverzeichnis 764 Zeilen, 732 Straßen; Wahllokale 69 Zeilen. Geometrie: keine (Kreisportal nur Punkte,
70 Zeilen Europawahl 2024). Orte: 77. Zu klein für ein Wörterbuch, das Treffer trägt.

### 3.5 Rhein-Kreis Neuss (AGS 05162000, Wikidata Q6253, OParl Body 0019)

votemanager liefert die Kreistagswahl nur auf den Ebenen Kreis, Gemeinde und Kreiswahlbezirk (33); Straßen- und
Wahllokaldateien sind leer. Flächen nur für die acht Gemeinden (`rhein-kreis-neuss-2020-kreistagswahl`). Ein Kreistag
ist zudem kein Stadtrat; die Fragestellung der Arbeit passt nicht.

### 3.6 Andere Portale (für Option 10 notiert)

Open.NRW und GovData führen 2025er Stimmbezirke mit Ergebnissen für Dortmund (`kommunalwahl-ratswahl-2025`, DL-DE
Zero), Bielefeld (`kommunalwahl-2025`, CC BY 4.0), Flächen für Dortmund, Soest, Kleve, Wuppertal, Köln, Remscheid,
Hamm (WMS). Die votemanager-Exporte gleichen Formats gibt es auch bei citeq (Münster), kdvz und kdo. Der in § 2
gewählte Zuschnitt (Profil, kanonische Stimmbezirke, Spaltenlegende) deckt diese Fälle, sobald jemand ein Profil
schreibt.

### 3.7 Begründung der Wahl

Die Abnahme des Briefings verlangt die ganze Kette bis zur Seite. Dafür braucht es Flächen je Stimmbezirk
(Overpass-Polygone, GeoSearch-Boxen, STRtree, Karte). Nur Mönchengladbach hat sie als Open Data, dazu das
Wahlergebnis im Düsseldorfer Format, 1 185 Orte und einen Rat mit vier Bezirksvertretungen, also eine Dokumentmenge,
die Treffer trägt. Neuss wäre Konrads nächste Nachbarin und hat alles außer Flächen; der Weg über das
Straßenverzeichnis (§ 9) ist ein eigenes Vorhaben und lohnt erst, wenn der Profilmechanismus steht.

## 4. Berührungspunkte im bestehenden Code (Datei, Funktion, was sich ändert)

| Datei | Funktion oder Stelle | Änderung |
|---|---|---|
| `src/georep/settings.py` | `Settings`, `load_settings`, `settings_files`, neue Modelle `City`, `Precincts`, `ReportSources`, `Analysis`, `Publish` | `profile: str` (Standard aus `defaults.toml`); `load_settings(explicit, cwd, profile=None)` liest zuerst die Schichten, bestimmt den Profilnamen (`--profile` > `GEOREP_PROFILE` > TOML), lädt `profiles/<name>.toml` aus dem Paket zwischen `defaults.toml` und `settings.toml`; `[city]` (`slug`, `name`, `genitive`, `adjective`, `ags`, `council`, `election`), `[precincts]` (`file_name`, `format` = `geojson`\|`shapefile-zip`, `member`, `source_crs`, `id_property`, `district_property` oder `district_from_id`, `name_property` oder `names_from_results`), `[columns.results]` erweitert um `precinct`, optionales `district`, `district_from_precinct`, `party_names` (Anzeigename je Schlüssel), `[report]` (`[[report.sources]]` mit `name`, `publisher`, `url`, `license`, `license_url`, `checked`; `ris_url`), `[analysis] exclude_districts`, `[publish] cities`; `fingerprint()` schließt `city.slug` ein (er ändert das Ergebnis), nicht die Pfade |
| `src/georep/defaults.toml` | ganze Datei | stadtneutral: nur `profile = "duesseldorf"`, Pfade, `http`, `cache`, `geo`, Overpass- und Wikidata-Endpunkte, Periode, `search.hide_in_display`, `publish.cities`; alles andere zieht nach `profiles/duesseldorf.toml` |
| `src/georep/profiles/duesseldorf.toml` (neu) | — | Body 0015, Portal-URLs, Q1718, `columns` wie heute (`district = "Kommunalwahlbezirk"`), `precincts` (GeoJSON, `Stimm-/ Wahlbezirk`, `Kommunalwahlbezirk Nr.`, `Kommunalwahlbezirk Name`), `search.exclude` (63), `betrifft`, `[city]`, `[report.sources]` mit den heutigen Lizenztexten, `exclude_districts = [1, 10]`, `reference_root = "./reference"` |
| `src/georep/profiles/moenchengladbach.toml` (neu) | — | § 3.2: Body 0011, die vier votemanager-Dateien, Shapefile-Zip, Q2758, `district_from_precinct = [1, 3]`, `parties = { CDU = "D1", SPD = "D2", GRUENE = "D3", AfD = "D4", FDP = "D5", Die_Linke = "D6" }`, `search.exclude` (Mönchengladbach, Gladbach, Rheydt, Niers, Stadtbezirk Nord/Ost/Süd/West, 44 Stadtteile), `text_split_marker` (Annahme `betrifft`, Frage 5), `exclude_districts = []`, `reference_root = "./reference/moenchengladbach"` |
| `src/georep/layout.py` | `Layout.from_settings`, neue Properties | `data_root / slug`, `cache_root / slug` für `pdf_dir`, `text_dir`; `http_cache` bleibt `cache_root / "http.sqlite"`; `districts_source` (= `external / precincts.file_name`), `districts_geojson` zeigt auf `interim / "stimmbezirke.geojson"` (kanonisch), `streets_directory` (`external / "opendata-strassen.csv"`, optional), `district_names_csv` (optional), `site_summary` (`site/data/summary.json`); `reference_view()` unverändert (liest die Referenznamen) |
| `src/georep/sources/opendata.py` | `fetch_results_csv` (bleibt), neu `fetch_districts_file(http, url, format)` (GeoJSON-Prüfung wie heute oder Zip-Prüfung: Mitglieder `.shp`, `.dbf`, `.prj` vorhanden), `fetch_streets_directory` (CSV mit `Bezirk-Nr` in der Kopfzeile) | Docstring stadtneutral; `deal.raises(FetchError, NetworkError)` bleibt |
| `src/georep/geo.py` | `read_precincts(path, columns, working_crs)` | liest nur noch das kanonische GeoJSON mit festen Eigenschaften; `Columns`-Parameter entfällt; Nachbedingung bleibt |
| `src/georep/prep/precincts.py` (neu) | `read_source_geojson`, `read_source_shapefile_zip` (pyshp), `canonical_precincts(features, rules, names) -> FeatureCollection` | Vorbedingung: jede Quellgeometrie hat die ID-Eigenschaft; Nachbedingung: Eigenschaften genau `stimmbezirk`, `wahlbezirk`, `wahlbezirk_name`, IDs eindeutig, jeder Wahlbezirk hat einen nicht leeren Namen, `crs` gesetzt; `SchemaError`, wenn eine Regel ins Leere greift |
| `src/georep/prep/voters.py` | `read_results_csv`, `aggregate_voters` | Wahlbezirk aus `columns.district` oder per Ausschnitt aus `columns.precinct`; Umbenennung der Zähl- und Parteispalten auf die kanonischen Namen (`Wahlberechtigte_insgesamt`, `Waehler`, `<Partei>_Stimmen`) vor der Aggregation; für Düsseldorf Identität. Verträge wie heute, zusätzlich: Ausgabe hat genau die kanonischen Spalten |
| `src/georep/prep/streets.py` | neu `directory_agreement(streets_per_precinct, directory) -> Agreement` | je Stimmbezirk: Anteil der OSM-Straßennamen, die das Straßenverzeichnis diesem Stimmbezirk (und, gröber, seinem Wahlbezirk) zuordnet; Vertrag `0 ≤ share ≤ 1`, `n_matched ≤ n_streets`; reine Polars-Funktion |
| `src/georep/pipeline.py` | `build_steps` | `opendata` lädt bis zu vier Dateien (Ergebnis, Geometrie, optional Straßenverzeichnis und Wahlbezirksnamen); neuer Schritt `precincts` (Eingaben `districts_source`, optional `district_names_csv`; Ausgabe `interim/stimmbezirke.geojson`); `streets_osm`, `pois_wiki`, `report` lesen die kanonische Datei; `streets` berechnet die Übereinstimmung, wenn ein Verzeichnis vorliegt; `report` schreibt zusätzlich `summary.json`; `papers` bekommt `max_pages` |
| `src/georep/bootstrap.py` | `bootstrap` | kennt das Paketformat (`raw/papers.jsonl` und `text/texts.parquet` kopieren) neben dem Altformat (`paper_with_text.json`); kopiert `districts_source` unter dem Profilnamen |
| `src/georep/cli.py` | `build_parser`, `main`, `_cmd_status`, neu `_cmd_publish`, `_cmd_profiles` | `--profile`, `fetch papers --max-pages N`, `georep publish [--out DIR]`, `georep profiles`; `status` nennt Profil und Stadt |
| `src/georep/report/model.py` | `OUTLIERS`, `_VOTER_COLUMNS`, `COLUMN_DOCS`, `build_report_model`, `regression_pair`, neu `summary_payload` | Ausreißer aus `settings.analysis.exclude_districts`; Spaltendoku für Parteien aus `columns.results.parties` und `party_names` erzeugt; „(1 bis 41)" wird „(1 bis n)" aus den Daten; `ReportModel` trägt `city`, `sources`, `agreement` (optional); `summary_payload(model)` liefert Kernzahlen, Regression, Datenstand als JSON-taugliches Dict |
| `src/georep/report/geometry.py` | `wahlbezirke_geojson` | `name` aus `city.name` und Wahljahr |
| `src/georep/report/render.py` | `ALLOWED_LINKS`, `render_report`, `render_map`, neu `render_comparison` | Allowlist aus Konstanten und Profil-URLs gebaut (`allowed_links(settings)`); Vorlage bekommt `city`, `sources`, `marker`, `agreement`, `other_cities`; `render_comparison(models, visuals)` mit eigener Allowlist; Nachbedingungen wie heute |
| `src/georep/report/templates/report.html.j2`, `map.html.j2` | Kopf, Methode, Fuß | alle Düsseldorf-Wörter werden Variablen (`city.adjective`, `city.genitive`, `city.name`, `city.council`), Methode nennt `marker` und die Quellen aus `sources`, Fuß rendert `sources` mit Lizenz und Prüfdatum; neue Zeile „Weitere Städte" |
| `src/georep/report/templates/vergleich.html.j2` (neu) | — | Tabelle, kleine Choroplethen (gemeinsame Quantilklassen), Streudiagramm mit beiden Städten, Hinweise zur Vergleichbarkeit; CSS aus `report.html.j2` geteilt (Makro oder gemeinsame Teilvorlage) |
| `src/georep/report/build.py` | `build_site`, neu `write_summary` | schreibt `summary.json` in `site/data/`; Zahl der Dateien im `SiteSummary` steigt um eins |
| `src/georep/report/publish.py` (neu) | `publish_sites(settings, now, commit) -> PublishSummary` | liest je Slug aus `publish.cities` den Ordner `data/<slug>/site/`, kopiert atomar nach `data/site/` (Düsseldorf an die Wurzel), baut `vergleich.html` aus `summary.json`, `wahlbezirke.geojson`, `wahlbezirke_auswertung.parquet`; fehlt eine Stadt, steht sie in der Zusammenfassung als „kein Lauf", und `vergleich.html` entsteht nur ab zwei Städten |
| `src/georep/sources/oparl.py` | `fetch_papers` | unverändert; die CLI reicht `max_pages` durch |
| `src/georep/sources/__init__.py` | `cached_session` | Cache-Regeln für Zip, Straßenverzeichnis, Wahlbezirks-CSV (30 Tage wie `opendata_s`) |
| `src/georep/export.py` | `csv_plan` | unverändert (kanonische Namen) |
| `pyproject.toml`, `uv.lock` | Abhängigkeiten | `pyshp>=3.1`, Eintrag in `decisions.md`; `nox -s deps` bleibt |
| `noxfile.py` | `VERIFY_TARGETS` | neue reine Funktionen: `prep.precincts.district_from_id`, `prep.voters.canonical_columns` |
| `tests/unit/test_settings.py` | alle | Profilmechanismus: Standardprofil liefert heutige Werte; `--profile`/Umgebung; unbekanntes Profil ist ein Fehler mit Liste; Fingerprint ändert sich mit dem Slug |
| `tests/unit/test_layout.py` | alle | Slug im Pfad; zwei Profile, ein `data_root`, disjunkte Verzeichnisse |
| `tests/unit/test_geo.py`, `test_report_geometry.py`, `tests/property/test_geo_props.py`, `tests/golden/test_network_steps.py`, `tests/unit/test_sources_osm_wiki.py` | Aufrufe von `read_precincts` | lesen die kanonische Datei (Fixture-Erzeugung aus der Referenz über `canonical_precincts`) |
| `tests/unit/__snapshots__/test_cli.ambr` | `georep steps` | bewusst erneuert: Schritt `precincts`, neue Eingaben von `opendata` |
| `tests/unit/test_cli.py` | Zählungen „9 ausgeführt" | 10 Offline-Schritte; `publish` und `profiles` getestet |
| `tests/fixtures/mg/` (neu), `tests/fixtures/make_mini_mg.py` (neu), `tests/fixtures/http/` (neue Aufzeichnungen), `tests/fixtures/oparl/papers_page_0009.json` (neu) | — | § 5, Stufe E |
| `tests/golden/test_pipeline.py` | neu `test_pipeline_runs_for_the_second_city` | Kette auf `tests/fixtures/mg/` mit dem Profil `moenchengladbach` |
| `.github/workflows/pages.yml`, `README.md`, `CLAUDE.md` (Befehle), `docs/architecture.md`, `docs/decisions.md`, `CHANGELOG.md`, `STATUS.md` | Befehle und Pfade | `georep run`, `georep --profile moenchengladbach run`, `georep publish`; Datenhaltung `data/<slug>/`, `data/site/`; Umzugshinweis für vorhandene `data/`- und `cache/`-Ordner |

## 5. Bauplan in Stufen

Jede Stufe ein bis drei Commits, Verhaltensänderung zuerst mit rotem Test, nach jedem Commit `uv run nox`; Tests in
`tmp_path` mit `Layout(...)` direkt oder über `load_settings(profile=…)`. Aufwand in Arbeitstagen eines Agenten.

### Stufe A: Profile und Layout je Stadt (1 Tag)

1. `settings.py`: `profile`, Profilschicht, `City`, `Analysis`, `Publish`; `defaults.toml` stadtneutral,
   `profiles/duesseldorf.toml` mit allen heutigen Werten und Kommentaren (ein Commit nur Verschiebung, ein Commit
   nur Mechanik). `georep profiles` listet die Dateien im Paket.
2. `layout.py`: Slug in `data_root` und `cache_root`; `reference_root` aus dem Profil.
3. CLI: `--profile`, `status` nennt Profil und Stadt. Doku des Umzugs (`mv data/{external,raw,interim,processed,site}
   data/duesseldorf/`, `mv cache/pdf cache/duesseldorf/pdf`, `mv cache/text cache/duesseldorf/text`) in README und
   CHANGELOG; `pages.yml` lädt weiter `data/site` hoch (Stufe F füllt es), bis dahin `data/duesseldorf/site`.
4. Tests: Standardprofil liefert exakt die heutigen Settings (Vergleich `model_dump()` gegen eine vor der Stufe
   gespeicherte Kopie, dann wieder entfernt); Reihenfolge der Schichten; unbekanntes Profil; Fingerprint je Slug;
   Layout-Disjunktheit.
5. Verträge: `deep_merge` bleibt; `load_settings` Nachbedingung „Profilname steht in `profile`".
6. Abnahme: `uv run nox`, `uv run pytest -m slow` grün ohne Änderung an `expected/`; `georep status` zeigt
   `Profil: duesseldorf (Düsseldorf)` und `data_root: …/data/duesseldorf`; `georep --profile gibtsnicht status`
   endet mit Exit 1 und nennt die verfügbaren Profile.

### Stufe B: Kanonische Stimmbezirke (1 Tag)

1. `uv add pyshp`; `decisions.md` Punkt 21 (pyshp statt GDAL, Kosten: ein weiteres reines Paket).
2. `prep/precincts.py`: Leser für GeoJSON und Shapefile-Zip (pyshp über `zipfile`, `.prj` zu CRS über
   `pyproj.CRS.from_wkt`), `district_from_id(id, start, stop)` (rein, Vertrag: Ergebnis positiv, `stop > start`),
   `canonical_precincts`; Namen aus Eigenschaft oder Wahlbezirks-CSV.
3. Schritt `precincts` in `build_steps`; `geo.read_precincts` ohne `Columns`; alle Leser auf
   `layout.districts_geojson` (kanonisch). `opendata` lädt die Geometrie unter `precincts.file_name`.
4. Tests: hypothesis für `district_from_id`; Mini-Fixture Düsseldorf: kanonische Datei hat 22 Features, drei
   Wahlbezirke, Namen wie heute, Koordinaten byteidentisch zur Quelle (kein Reprojizieren); Shapefile-Zip aus drei
   Polygonen (mit pyshp im Test geschrieben) liest Nummern und CRS; Golden Master unverändert.
5. Abnahme: `uv run pytest -m slow` grün (1 996 Orte zugeordnet wie bisher, `wahlbezirke_auswertung` gleich);
   `georep steps` zeigt `precincts <- Stimmbezirke_2025.geojson -> stimmbezirke.geojson`; Snapshot bewusst erneuert.

### Stufe C: Wahlergebnis aus votemanager (0,5 Tag)

1. `ResultsColumns`: `precinct`, optionales `district`, `district_from_precinct`, `party_names`; Validator: genau
   eines von `district` und `district_from_precinct`.
2. `prep/voters.py`: Umbenennung auf kanonische Namen, Wahlbezirk per Ausschnitt; `read_results_csv` mit
   `encoding = "utf-8"` und ohne BOM.
3. `sources/opendata.py`: `fetch_streets_directory`, `fetch_district_names_csv`; `cached_session` mit Regeln.
4. Tests: die Mönchengladbacher Stimmbezirks-CSV (Ausschnitt, § 5 E) aggregiert zu 33 Zeilen, deren Summen gleich
   der Wahlbezirks-CSV sind (das ist der Test aus § 3.2 als Golden Master); Düsseldorf unverändert (Identität der
   Umbenennung, Golden Master). Property: Umbenennung ist eine Bijektion auf den konfigurierten Spalten.
5. Abnahme: `uv run nox` grün; `aggregate_voters` liefert für beide Städte genau die kanonischen Spalten.

### Stufe D: Berichtsseite je Stadt (1 Tag)

1. `report/model.py`: Ausreißer, Parteidoku, `city`, `sources`, `summary_payload`; `report/build.py` schreibt
   `summary.json` (Kernzahlen, beide Regressionen, Datenstand, Version, Stadt) und listet es unter Downloads.
2. `render.py`: `allowed_links(settings)`; Vorlagen mit Variablen; Methode nennt den Marker; Fuß rendert `sources`
   (Name, Herausgeber, Lizenz mit Link, geprüft am); Zeile „Weitere Städte" aus `publish.cities` (Links relativ:
   `../` beziehungsweise `<slug>/`).
3. `geometry.py`: Name der FeatureCollection aus dem Profil.
4. Tests: Düsseldorf-Seite enthält weiter „Düsseldorfer Ratsdokumenten", keine Zeichenkette „Düsseldorf" im
   Modul `report/` außer in Tests (`grep` als Test); ein Modell mit erfundener Stadt rendert ohne Düsseldorf-Wort;
   Allowlist lässt Profil-URLs durch und fremde nicht (Vertragstest); `summary.json` parst und trägt dieselben
   Zahlen wie die Kacheln (Vergleich im Test); `schema.json` dokumentiert `summary.json`.
5. Abnahme: `grep -rn "Düsseldorf\|0015\|Q1718\|duesseldorf" src/` zeigt nur `profiles/duesseldorf.toml`;
   Seite der Referenz mit headless Chrome angesehen (Kopf, Methode, Fuß; § 8.4 des Meta-Plans); Snapshot der
   Download-Tabelle bewusst erneuert (eine Zeile mehr).

### Stufe E: Profil Mönchengladbach, Fixture, Übereinstimmung (1 Tag, davon rund fünf Minuten Netz)

1. `profiles/moenchengladbach.toml` nach § 3.2 und § 4.
2. Aufzeichnungen (innerhalb des Fünf-Minuten-Budgets, mit `delay_s` wie konfiguriert): drei Overpass-Antworten
   (Stimmbezirke `11001` Zentralbibliothek in Wahlbezirk 10, `32201` in Wahlbezirk 22, `40201` in Wahlbezirk 02,
   nach dem Muster in
   `tests/fixtures/http/README.md`), die SPARQL-Antwort für Q2758 (erste 25 Bindings), drei GeoSearch-Antworten,
   eine OParl-Seite von Body 0011 (bestätigt den Body; 85 s eingeplant) und bis zu acht PDFs daraus (unter 110 KB,
   je Dokumentart eine, mit `PROVENANCE.md`), dazu die Seite von Body 0009 aus dem Scratchpad als Vertrag für Paper
   ohne `mainFile`. Je Antwort Anfrage daneben, README mit Datum. Der OParl-Fixture-Test prüft, dass das Modell
   jeden Schlüssel kennt.
3. `tests/fixtures/make_mini_mg.py`: aus den vier öffentlichen Dateien (im Scratchpad geladen, in Phase 3 neu
   geholt) die Zeilen der drei Wahlbezirke 10, 22 und 02 (18 Urnen-Stimmbezirke: `11001`–`11006`, `32201`–`32205`,
   `40201`–`40207`, dazu ihre Briefwahlbezirke), ein reduziertes Shapefile-Zip (pyshp Writer, die vorhandenen
   Polygone dieser Nummern, `.prj` kopiert), Straßenverzeichnis und Wahlbezirks-CSV der drei; `raw/` aus den
   Aufzeichnungen; Korpus aus den PDFs (`papers.jsonl`, `text/texts.parquet`); README mit Herkunft. Erwartung
   (`expected/`) zunächst aus der eigenen Kette (Charakterisierung, so gekennzeichnet), ersetzt in Stufe G durch
   den Golden Master aus dem echten Lauf.
4. `prep/streets.py::directory_agreement`; der Schritt `streets` nennt sie in seiner Zeile, das Modell zeigt sie
   in „Methode und Grenzen" („Flächen vom 08.06.2022; Übereinstimmung mit dem Straßenverzeichnis 2025 je
   Stimmbezirk x %, je Wahlbezirk y %"). Schwelle erst nach Messung auf dem echten Lauf (CLAUDE.md), vorläufig
   Warnung unter 90 % je Wahlbezirk.
5. Tests: `test_pipeline_runs_for_the_second_city` (alle Offline-Schritte, Stamps, Wiederholung No-op, Seite mit 3
   Bezirken und „Mönchengladbacher"); Netzschritte gegen die Fake-Session mit den Aufzeichnungen; `text_split_marker`:
   Anteil der Fixture-Texte mit Marker wird gemessen und steht im Test als Zahl (Frage 5).
6. `georep --profile moenchengladbach run --dry-run` auf leerem `data_root` plant 10 Offline-Schritte und meldet
   fehlende Eingaben mit dem Hinweis auf `fetch`; `fetch --dry-run --online` plant die Netzschritte.
7. Abnahme: `uv run nox` grün inklusive der neuen Golden-Master-Datei; `uv run georep --profile moenchengladbach
   bootstrap && run` auf `reference_root = tests/fixtures/mg` (per `--settings` im Test) baut
   `data/moenchengladbach/site/index.html`; `grep` nach Düsseldorf-Literalen im neuen Code leer.

### Stufe F: Städtevergleich und Veröffentlichung (1,5 Tage)

1. `report/publish.py`, `vergleich.html.j2`, `render_comparison`; gemeinsame Quantilklassen über beide Städte
   (`charts.classify` auf der Vereinigung), kleine Choroplethen (`MAP_WIDTH` 320), ein Streudiagramm mit zwei
   Punktfarben und je einer Geraden (Farben wie `dataviz`-Skill, vor dem ersten Diagramm laden), Tabelle:
   Wahlbezirke, Stimmbezirke, Dokumente, Begriffe, Dokumente mit Treffer, Median Trefferquote, Median
   Wahlbeteiligung, r, p; Hinweise zur Vergleichbarkeit (Wahlberechtigte je Wahlbezirk: Düsseldorf rund 11 500,
   Mönchengladbach rund 6 200; Dokumente je Einwohner; Geometriestand; Marker).
2. `georep publish`: kopiert, baut, meldet „2 Städte, 1 Vergleich, 34 Dateien, 16,9 MB" oder „1 Stadt, kein
   Vergleich (moenchengladbach: kein Lauf unter data/moenchengladbach/site)". Exit 0 in beiden Fällen.
3. `pages.yml`: `georep bootstrap && georep run && georep publish` (Mönchengladbach kommt in Stufe G dazu); README,
   CLAUDE.md (Befehle), `architecture.md` (Module, Pipeline, Datenhaltung mit `data/<slug>/` und `data/site/`),
   `decisions.md` Punkt 22 (Profile und Layout je Stadt, verworfene Alternativen aus § 2), CHANGELOG unter
   „Unreleased".
4. Tests: `publish` auf zwei Mini-Läufen (Düsseldorf-Mini und MG-Mini) in `tmp_path`: Ordnerstruktur, `vergleich.html`
   parst, enthält beide Namen, nur erlaubte Links, Größe unter 400 KB; mit nur einer Stadt kein Vergleich, aber
   Kopie und Meldung; zweimal `publish` ist idempotent (byteidentisch bis auf Zeit, die Eingabe ist).
5. Abnahme: aus frischem Klon `uv sync --locked && uv run georep bootstrap && uv run georep run && uv run georep
   publish` erzeugt `data/site/index.html` (Düsseldorf, unverändert erreichbar) und `data/site/vergleich.html`
   nur, wenn zwei Städte vorliegen; Pages-Workflow grün (Actions-REST-API), Seite live.

### Stufe G: Der volle Abruf für Mönchengladbach, dokumentiert und vorbereitet (0,5 Tag Agent, 3 bis 5 h Konrads Rechner)

1. `docs/runbook-stadt.md` (neu): Schrittfolge für Konrad auf kookaburra mit Zeiten und Prüfpunkten:
   `export UV_*`; `uv run georep --profile moenchengladbach fetch opendata` (Sekunden; prüft Spalten, Zip,
   Legende); `… fetch papers --max-pages 1` (Probe: Body 0011 antwortet, Paper tragen `body` 0011, Datum im
   Zeitraum); `… fetch papers` (40 bis 60 Seiten, mit `stop_when_older`, 1 bis 1,5 h bei 85 s je Seite, 5 min bei
   5 s); `… fetch pdfs --limit 200` als Stichprobe, Extraktion, Markeranteil prüfen (`georep status`, ein kleines
   Skript im Runbook zählt Texte mit Marker); dann `… fetch pdfs` (Stunden, wiederaufnehmbar); `… fetch streets_osm
   pois_wiki` (179 Overpass-, 179 GeoSearch-Abfragen, rund 15 min); `… run`; Seite ansehen; Übereinstimmung mit dem
   Straßenverzeichnis lesen.
2. Paketbildung: `uv run georep --profile moenchengladbach export-reference` (neuer Befehl oder dokumentiertes
   `rsync`): `external/`, `raw/`, `text/texts.parquet` nach `reference/moenchengladbach/` mit README (Datum, Zahlen,
   Lizenzen); Golden Master `tests/fixtures/mg/expected/` aus diesem Lauf neu erzeugen und als solcher im README
   markieren; `pages.yml` um `georep --profile moenchengladbach bootstrap && run` ergänzen; `publish.cities` um
   `moenchengladbach` erweitert (steht schon, wirkt erst mit Paket).
3. Abnahme: Runbook von oben nach unten ausführbar (jeder Befehl endet mit Exit 0 oder sagt, warum nicht);
   `georep --profile moenchengladbach status` zeigt alle 15 Schritte aktuell; Vergleichsseite zeigt zwei Städte;
   `uv run pytest -m slow` prüft auch das Paket (Zahl der Wahlbezirke 33, Trefferquoten endlich, Seite unter
   1,5 MB). Die Regression ohne Ausreißer wird mit den beiden höchsten Trefferquoten ins Profil geschrieben
   (Frage 6).

Summe: rund 6,5 Agententage plus Konrads Lauf. Reihenfolge A bis F ohne Netz; E braucht die fünf Minuten; G ist
Konrads.

## 6. Auswirkung auf die Berichtsseite (Abschnitt, Größe in KB, Unterseite ja/nein)

- `index.html` (Düsseldorf, Wurzel): Kopfzeile „Weitere Städte: Mönchengladbach · Städtevergleich" (unter 1 KB),
  Fuß und Methode aus dem Profil (Text gleich, Herkunft anders), Download `summary.json` (unter 2 KB). Größe bleibt
  bei rund 690 KB; Budget 1,5 MB hält.
- `moenchengladbach/index.html`, `moenchengladbach/karte.html`, `moenchengladbach/data/` (neu): dieselbe Vorlage;
  erwartet 33 Bezirke, rund 500 bis 700 KB `index.html`, `dokumente.json` 1 bis 2 MB.
- `vergleich.html` (neu, Unterseite an der Wurzel): zwei kleine Choroplethen (je rund 40 KB SVG bei 15 m
  Vereinfachung), ein Streudiagramm (rund 15 KB), eine Tabelle; Ziel unter 300 KB, ohne Fremdressourcen, eigene
  Allowlist (Repository, die beiden Stadtseiten relativ).
- `data/site/` insgesamt: rund 17 MB für zwei Städte (heute 8,4 MB).

## 7. Risiken und Fallstricke

- **Body 0011 ist unbestätigt**; erst die Probe mit `--max-pages 1` in Stufe E zeigt, ob es Mönchengladbach ist.
  Fällt sie anders aus, nennt `defaults.toml`-Kommentar die Alternativen; der Body-Katalog `/Oparl/bodies` ist eine
  Anfrage.
- **Umfang des Abrufs unbekannt** (8 000 bis 12 000 Vorlagen geschätzt); der OParl-Server antwortete am
  2026-10-11 in 5 s statt 85 s, das kann schwanken. Alles ist wiederaufnehmbar; das Runbook plant die Stichprobe
  mit `--limit 200` vor dem Rest.
- **Geometrie von 2022 gegen Wahlberechtigte von 2025**: 4 neue und 5 entfallene Stimmbezirke, Wahlbezirksgrenzen
  können sich an diesen Stellen verschoben haben. Die Übereinstimmung mit dem Straßenverzeichnis wird gemessen
  und steht auf der Seite; eine Anfrage an die Stadt (Frage 3) kann die Flächen von 2025 bringen, das Profil
  tauscht dann nur die URL.
- **`text_split_marker`**: ob Mönchengladbacher Vorlagen „betrifft" tragen, ist offen; ohne Marker durchsucht die
  Kette den ganzen Text (mehr Treffer im Vorlagenkopf, z. B. Adressen der Verwaltung). Die PDF-Stichprobe in
  Stufe E misst den Anteil; ein anderer Marker ist eine Zeile im Profil.
- **Lizenz der votemanager-CSV** steht nirgends; ohne Antwort (Frage 4) nennt die Seite die Quelle mit „Lizenz
  laut Anbieter nicht angegeben; Nutzung als amtliche Wahlstatistik" und keine Lizenzkurzform. Das Shapefile ist
  sauber (DL-DE Zero 2.0).
- **Namenskollisionen im Cache**: PDFs beider Bodies heißen `000xxxxx.pdf`; ohne Slug im Cache würde ein
  Neusser PDF ein Düsseldorfer überschreiben. Der Umzug `cache/pdf → cache/duesseldorf/pdf` ist Pflicht vor dem
  ersten Lauf einer zweiten Stadt; `georep status` warnt, wenn `cache_root/pdf` noch existiert.
- **Golden Master der zweiten Stadt** ist bis Stufe G eine Charakterisierung der eigenen Kette, kein unabhängiges
  Orakel; so im Fixture-README gekennzeichnet. Für Düsseldorf ändert sich nichts an `expected/`.
- **Vergleichbarkeit**: Wahlbezirke verschiedener Größe (Düsseldorf 41 für 469 732 Wahlberechtigte,
  Mönchengladbach 33 für 204 219), verschiedene Dokumentmengen und Vorlagenformate. Die Vergleichsseite sagt das
  und vergleicht Verteilungen, keine Absolutwerte.
- **Stadtteile als Wahlbezirksnamen**: in Mönchengladbach heißen Wahlbezirke wie Stadtteile („Venn", „Lürrip",
  „Hardt"); die Ausschlussliste nimmt sie trotzdem heraus (Regel der Arbeit, sonst zählte der Begriff für den
  Stadtteil als Treffer eines Wahlbezirks, der nur einen Teil davon umfasst). Dokumentiert in „Grenzen".
- **`settings.local.toml` in acht Worktrees**: der Slug im Layout verhindert Kollisionen zwischen Städten, nicht
  zwischen Worktrees; `data_root` bleibt je Worktree eigen (§ 4 des Meta-Plans).
- **Snapshots und Zählungen** (`georep steps`, „9 ausgeführt") ändern sich durch den Schritt `precincts`: bewusst
  erneuern, mit Diff im Commit.
- **pyshp liest `.dbf` als latin-1 oder cp1252**: Mönchengladbachs `Nummer` ist ASCII; für Namen in anderen
  Shapefiles die Kodierung im Profil (`precincts.dbf_encoding`, Standard `utf-8` mit Fallback `latin-1`).

## 8. Offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | Warum sie zählt | Annahme |
|---|---|---|---|
| 1 | Ist Mönchengladbach als erste zweite Stadt recht, obwohl das Briefing Neuss als Nachbarin nennt? | Neuss hätte Flächen aus dem Straßenverzeichnis gebraucht (ein eigenes Vorhaben, § 9); Mönchengladbach läuft mit der Kette, wie sie ist | Mönchengladbach; Neuss als Folgeprofil, sobald § 9 umgesetzt ist |
| 2 | Darf das Paket des vollen Laufs (`raw/papers.jsonl`, `text/texts.parquet`, geschätzt 10 bis 20 MB, Texte fremder Dokumente wie bei der Referenz) nach `reference/moenchengladbach/` ins Repo? | CI baut die Seite nur aus dem Repo; die Alternative (R2-Bucket, Antwort zu Option 7) braucht ein Secret in Actions und einen Download-Schritt | ja, ins Repo, wie die Referenz der Arbeit (82 MB) |
| 3 | Soll Konrad die Stadt Mönchengladbach (Fachbereich Geoinformation, `gdi@moenchengladbach.de` laut Open.NRW) nach den Stimmbezirksflächen der Kommunalwahl 2025 fragen? | 4 beziehungsweise 5 Stimmbezirke weichen zwischen 2022 und 2025 ab; mit Flächen von 2025 entfällt die Unschärfe | Flächen von 2022 mit gemessener Übereinstimmung; die Anfrage ist ein Satz, den der Plan nicht selbst stellen darf |
| 4 | Unter welcher Lizenz stehen die votemanager-Open-Data-CSVs der ITK Rheinland? (`config.json` sagt `lizenz: true`, eine Lizenzseite gibt es nicht; Düsseldorfs Portal stellt dieselben Daten unter DL-DE BY 2.0) | die Seite muss die Lizenz wörtlich nennen (Regel der Berichtsseite) | Quelle und Herausgeber werden genannt, Lizenzfeld „nicht angegeben"; Konrad kann die ITK Rheinland oder die Stadt fragen |
| 5 | Welcher Marker trennt den Vorlagenkopf in Mönchengladbacher Vorlagen? | ohne Marker zählen Treffer im Kopf (Adressen, Gremienlisten) | `betrifft` wie Düsseldorf (gleiches Ratsinformationssystem, gleicher Betreiber); die PDF-Stichprobe in Stufe E misst, der Test nennt die Zahl, das Profil wird angepasst, wenn sie unter 90 % liegt |
| 6 | Welche Wahlbezirke schließt die zweite Regression („ohne Ausreißer") für Mönchengladbach aus? | Tabelle 5 der Arbeit nennt 1 und 10 für Düsseldorf (die beiden höchsten Trefferquoten) | leer bis zum echten Lauf; danach die beiden höchsten Trefferquoten nach derselben Regel, als Liste im Profil (Stufe G) |
| 7 | Soll Düsseldorfs `data_root` auf `data/duesseldorf/` wandern (README, `pages.yml`, Konrads Ordner auf xtraspace betroffen), oder soll Düsseldorf die Ausnahme ohne Slug bleiben? | ohne Slug müsste jede zweite Stadt ihren Pfad explizit setzen, und `settings.local.toml` könnte ihn überschreiben (§ 2) | Slug für alle Städte, Umzug dokumentiert; `georep status` erkennt alte Ordner und sagt, wohin |
| 8 | Vergleich als Unterseite `vergleich.html` an der Wurzel, oder lieber als Abschnitt in beiden Stadtseiten? | Unterseite hält das Budget und trennt die Läufe; Abschnitt wäre sichtbarer | Unterseite mit Teaser-Zeile im Kopf jeder Stadtseite |
| 9 | Wie lange darf der volle Abruf für Mönchengladbach laufen, und auf welchem Rechner (kookaburra, VPS)? | 3 bis 5 h geschätzt; über fünf Minuten braucht alles Konrads Freigabe | Konrad startet ihn nach dem Merge nach dem Runbook auf kookaburra; bis dahin baut `publish` die Seite ohne Mönchengladbach |

## 9. Vorbereitung für Option 10 (was wird konfigurierbar, welche Modulgrenze entsteht)

Konfigurierbar wird alles, was heute Düsseldorf ist: Stadt (`[city]`), Datenquellen und ihre Formate
(`[sources.*]`, `[precincts]`, `[columns.results]` mit Legende), Ausschlussliste und Marker (`[search]`), Quellen und
Lizenzen der Seite (`[report.sources]`), Ausreißer (`[analysis]`), welche Städte veröffentlicht werden
(`[publish]`). Ein neues Profil ist eine TOML-Datei; der Code kennt keine Stadt. Die Profilschicht trägt genauso
eine Periode (Option 2: `profiles/duesseldorf-2014.toml` mit `period` und `reference_root`) oder ein offenes
Ende (Option 7: `period.end` optional); das Layout hängt dann Periode an Slug (`duesseldorf-2014`), ohne neuen
Mechanismus. Die Synergiephase sollte Slug, Profilschicht und `publish` als Fundament vorziehen (§ 5 Phase 2 des
Meta-Plans erwartet genau das für 1, 2 und 7).

Modulgrenzen, die entstehen:

- **Quelle → kanonische Stimmbezirke** (`prep/precincts.py`): jede Geometriequelle endet in einem GeoJSON mit drei
  Eigenschaften und dem CRS der Quelle; alles dahinter (Overpass, GeoSearch, STRtree, Karte) kennt nur dieses Format.
  Ein dritter Leser (WFS, GeoPackage, oder die Flächen aus dem Straßenverzeichnis) ist eine Funktion mit demselben
  Rückgabetyp.
- **Quelle → kanonisches Wahlergebnis** (`prep/voters.py` mit Legende): votemanager-Codes oder beliebige Spaltennamen
  enden in den Spalten der Arbeit; Parteien sind die Schlüssel der Legende.
- **Stadtseite als Schnittstelle** (`site/data/summary.json`, `wahlbezirke.geojson`, die Parquet-Tabellen): der
  Vergleich und Option 7 lesen nur veröffentlichte Dateien, nie Zwischenstände.
- **Profil** als die eine Datei, die ein Lehrbeispiel braucht: „nimm `moenchengladbach.toml`, ändere AGS, Body,
  Entität, vier URLs und die Ausschlussliste".

Neuss, Grevenbroich und die übrigen Kreiskommunen werden erreichbar über einen weiteren Leser in
`prep/precincts.py`: Straßenverzeichnis (`opendata-strassen.csv`: Straße, Hausnummernbereich, Stimmbezirk) plus
OSM-Adresspunkte (eine Overpass-Abfrage `node["addr:street"]["addr:housenumber"]` innerhalb der Stadtgrenze, die
das Kreisportal als GeoJSON liefert: `stadt-neuss-stadtgrenze`) ergeben je Adresse einen Stimmbezirk; Voronoi-Zellen
der Adressen (`shapely.voronoi_polygons`), je Stimmbezirk vereinigt und an der Stadtgrenze geschnitten, sind die
Fläche. Verträge: jede Adresse liegt in der Fläche ihres Stimmbezirks, die Flächen überdecken die Stadtgrenze, die
Summe der Flächen ist die Stadtfläche. Das ist ein eigener Plan (zwei bis drei Tage), nicht Teil dieses Branches;
die Daten dafür sind in § 3.3 benannt.

## 10. Änderungen durch die Synergiephase

Füllt der Supervisor.
