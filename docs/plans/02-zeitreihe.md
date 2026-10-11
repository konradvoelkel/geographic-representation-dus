# Plan 02: Zeitreihe

Stand 2026-10-11, Branch `feat/02-zeitreihe`. Status: geplant.

Briefing: [../plan-ausbau-2026-10.md](../plan-ausbau-2026-10.md), § 7.2; Regeln: § 2 dort und [../../CLAUDE.md](../../CLAUDE.md);
Aufbau des Programms: [../architecture.md](../architecture.md). Dieser Plan ist so geschrieben, dass ein frischer Agent ihn
nach der Synergiephase ohne Rückfragen umsetzen kann. Alle Zahlen in § 3 wurden am 2026-10-11 nachgesehen (Polars,
`ls -l`, Portalseiten, eine OParl-Seite); die Erkundungsskripte lagen im Scratchpad und sind nicht Teil des Repos.

## 1. Ziel und Nicht-Ziel

**Ziel.** Dieselbe Kette für die Wahlperiode 2014 bis 2020: die Ratsdokumente dieser Periode werden mit dem
Wörterbuch der 41 Wahlbezirke von 2025 durchsucht, die Wahlbeteiligung der Ratswahl vom 13.09.2020 wird von den 316
Stimmbezirken von 2020 über Flächenanteile auf die Wahlbezirke von 2025 umgerechnet, und beide Perioden stehen auf
der Berichtsseite nebeneinander: je Wahlbezirk Trefferquote und Wahlbeteiligung beider Perioden, dazu die Regression
„Änderung der Trefferquote gegen Änderung der Wahlbeteiligung". Eine Periode ist ein Settings-Profil
(`georep --settings settings.2014.toml run`), ihre Daten liegen getrennt unter `data_root/2014-2020/`, die Umrechnung
ist ein eigenes Modul mit Vertrag und hypothesis-Test, und eine synthetische zweite Periode in der Mini-Fixture hält
alles offline testbar. Der volle Abruf der alten Periode (geschätzt 25 000 bis 30 000 Paper, 3,7 bis 4,4 GB PDFs, zehn bis
vierzehn Stunden) ist ein dokumentierter Lauf, den Konrad startet (§ 5, Stufe H); der Plan bereitet ihn vor, führt ihn nicht aus.

**Nicht-Ziel.** Kein Wörterbuch auf dem Zuschnitt von 2020 und keine Straßen oder Orte „von damals" (§ 2, Punkt 1);
keine Umrechnung von Treffern oder Trefferquoten zwischen Zuschnitten (nur additive Zählgrößen werden umgerechnet);
keine dritte Periode 2009 bis 2014 (das Portal hat keine Stimmbezirksgeometrie von 2014, § 3.2); keine
Bevölkerungsraster als Gewichte (Zensus 2022, 100-m-Raster: genauer als Flächen, aber eine weitere Quelle; Kandidat für
später, § 9); keine kausale Deutung der Differenzen auf der Seite (n = 41, zwei Zeitpunkte); kein Abruf gegen den
OParl-Server durch den Agenten über die eine Formatprüfung hinaus.

## 2. Entscheidungen (mit verworfenen Alternativen und Kosten)

| Frage | Entscheidung | Warum, und was verworfen wurde |
|---|---|---|
| Wörterbuch der alten Periode | dasselbe Wörterbuch wie 2020 bis 2025 (Straßen und Orte je Wahlbezirk 2025, Stand der Arbeit); `period.dictionary = "base"` lässt die Schritte `streets`, `pois`, `dictionary` des Profils aus den Rohdaten der Hauptperiode lesen, die Netzschritte `streets_osm` und `pois_wiki` gibt es im Profil nicht | Dann unterscheiden sich die Perioden nur in den Dokumenten, und die Treffer liegen in beiden auf den Wahlbezirken 2025; nichts Nicht-Additives muss umgerechnet werden. Verworfen: ein Wörterbuch je Stimmbezirk 2020 (Overpass und GeoSearch je 316 Polygone, zweimal 5 bis 10 min Netz, und 87 der 306 Stimmbezirke 2025 liegen nicht zu 99 % in einem Wahlbezirk 2020: Trefferquoten wären zwischen Zuschnitten umzurechnen, obwohl Treffer Dokumentmengen sind, keine Summen); OSM und Wikidata „von 2016" (keine öffentliche Attic-Abfrage ohne eigenes Setup; die Referenz der Arbeit ist ohnehin Stand November 2025) |
| Richtung und Gewichte der Umrechnung | Stimmbezirke 2020 (fein) auf Wahlbezirke 2025 (grob), Gewicht = Flächenanteil der Schnittfläche am Stimmbezirk, auf die Schnittsumme normiert; Zählgrößen (Wahlberechtigte, Wähler, Stimmen) werden so übertragen und je Zielbezirk nach größtem Rest ganzzahlig gerundet (Summe exakt erhalten); Anteile (Wahlbeteiligung) entstehen danach aus den übertragenen Zählgrößen. Die Gewichte je Zielbezirk, mit denen ein Anteil direkt übertragbar wäre (Flächenanteil mal Wahlberechtigte, je Ziel normiert), liefert das Modul ebenfalls, mit dem Vertrag „Summe je Zielbezirk gleich 1" | Beide Vertragsrichtungen sind exakt und im Prototyp geprüft (§ 3.4). Verworfen: Wahlbezirk 2020 auf Wahlbezirk 2025 (41 auf 41; kein einziger der 41 Bezirke blieb unter 1 % Flächenänderung, § 3.4); Zuordnung ganzer Stimmbezirke zum Mehrheitsbezirk (83 von 316 Stimmbezirken sind geteilt; Abweichung bis 2,6 Prozentpunkte Wahlbeteiligung und 4 262 Wahlberechtigte je Bezirk); Bevölkerungsgewichte (siehe Nicht-Ziel) |
| Wahlbezirk 2020 je Stimmbezirk 2020 | geometrisch: repräsentativer Punkt des Stimmbezirks in genau einem Polygon der 41 Kommunalwahlbezirke 2020; validiert gegen die Wahlbezirks-CSV (Summe der Wahlberechtigten je Bezirk exakt gleich, 41 von 41) | Weder die Stimmbezirks-CSV noch das Stimmbezirks-GeoJSON von 2020 tragen den Wahlbezirk (§ 3.2). Verworfen: Ableitung aus der Nummer (der Stadtteil-Präfix reicht nicht, Stadtteile sind geteilt) |
| Briefwahl 2020 | Briefwähler je Wahlbezirk 2020 = Wähler laut Wahlbezirks-CSV minus Summe der Urnenwähler seiner Stimmbezirke; verteilt auf die Stimmbezirke proportional zu A2 (Wahlberechtigte mit Sperrvermerk W, also mit Wahlschein) | 110 265 der 247 356 Wähler (44,6 %) wählten per Brief; die 138 Briefwahlbezirke haben weder Geometrie noch Wahlbezirk. Verworfen: Briefwahl weglassen (Beteiligung um fast die Hälfte zu niedrig); proportional zu A (Wahlberechtigte insgesamt; bis 5,1 Prozentpunkte Unterschied je Bezirk, Median 0,6); Briefwahlbezirke per Summenprobe zuordnen (kombinatorisch, fragil) |
| Periode als Profil | `settings.2014.toml` im Repo; `[period]` bekommt `name`, `label`, `election`, `dictionary`; `period.name` wird Unterordner unter `data_root` (leer = flache Ablage der Hauptperiode, nichts ändert sich auf `main`); `cache_root/pdf` und `http.sqlite` bleiben geteilt, der Textstore liegt je Periode unter `cache_root/text/<name>/` | Profile dürfen keine Rechnerpfade kennen; `settings.local.toml` bleibt die einzige Stelle für Pfade. Verworfen: zweites `data_root` in `settings.local.toml` (nicht committbar, Pages kennt es nicht); geteilter Textstore (die beiden Perioden hätten sich gegenseitig den Stamp von `texts` entwertet und `corpus` neu gerechnet) |
| Zeitgrenzen der alten Periode | `start = 2014-05-25` (Ratswahl 2014), `end = 2020-09-12` (Tag vor der Ratswahl 2020), `election = 2020-09-13` | Disjunkt zur Hauptperiode (die beginnt mit dem Wahltag 13.09.2020, wie die Arbeit; ihr ältestes Dokument trägt den 14.09.2020). Verworfen: konstituierende Sitzungen als Grenzen (nicht aus den Daten ableitbar) |
| Vergleich | eigener Schritt `compare` auf der Hauptperiode, nur mit `compare.period = "2014-2020"` (Profil `settings.vergleich.toml`); er schreibt `processed/wahlbezirke_vergleich.parquet` und wird Eingabe von `report`; ohne das Profil ist die Kette von `main` unverändert und der Snapshot von `georep steps` bleibt | Fehlende Eingaben sind nach Regel 3 der Architektur ein Fehler, kein stilles Überspringen; also muss der Vergleich ausdrücklich eingeschaltet werden. Verworfen: Vergleich im Schritt `report` mit „optionaler Eingabe" (das Schrittregister kennt keine) |
| Seite | Abschnitt „Zwei Wahlperioden" auf der Hauptseite (Tabelle je Wahlbezirk, Streudiagramm der Änderungen, Tabelle 5 der alten Periode); die alte Periode bekommt zusätzlich ihre eigene vollständige Seite unter `2014-2020/index.html` als Unterseite | Budget von `index.html` (unter 1,5 MB) hält; die Unterseite ist dieselbe Vorlage mit Periodentexten aus den Settings (§ 6) |
| Schnappschuss der alten Periode | nach Konrads Lauf ein eingefrorener Datensatz `snapshots/2014-2020/` im Repo, im nativen Format (`raw/papers.jsonl`, `cache/text/texts.parquet`, `external/`), geschätzt 35 bis 40 MB; `bootstrap` lernt dieses Format; das Profil setzt `reference_root = "snapshots/2014-2020"`; Pages baut beide Perioden aus dem Repo | So bleibt die Seite aus dem Repo reproduzierbar wie heute. Verworfen: `paper_with_text.json` wie die Arbeit (rund 80 MB unkomprimiert); Abruf in CI (Stunden, Zeitlimit sechs Stunden); nur die kleinen Ergebnisse committen (dann baut `report` der alten Periode nicht, weil `dokumente.json` den Korpus braucht). Offen bleibt der Ort, falls 40 MB zu viel sind (§ 8, Frage 1: R2-Bucket mit Option 7) |
| Abruf der alten Periode | `sources.oparl.first_page` (Standard 1; das Profil setzt 90), `incremental = false`, Seitenfortschritt in `raw/papers.progress.json`, Cache der OParl-Seiten 30 Tage im Profil; Konrad startet ihn | Der Server listet neueste zuerst, die Seiten 1 bis 95 tragen die Hauptperiode (Stand 2026-10); ohne Startseite kosteten sie 2,3 h. `modified` ist bei alten Papern das Migrationsdatum 2024-12-30, `modified_since` wäre nutzlos (§ 3.3). Ein Abbruch nach Seite 150 von rund 235 darf nicht bei Seite 90 neu beginnen |
| Kanonische Spaltennamen der Wählertabelle | `wahlbezirke_waehler.parquet` trägt in beiden Perioden `Wahlberechtigte_insgesamt`, `Waehler`, `<Partei>_Stimmen`; die Quellspalten (2025: dieselben Namen; 2020: `A`, `B`, `D1` bis `D6`) werden beim Lesen umbenannt | Für die Hauptperiode ist das ein No-op (Golden Master unberührt); `COLUMN_DOCS`, `join_voters` und `district_rows` lesen die Konstanten statt `columns.eligible`. Verworfen: Quellnamen durchreichen (dann hieße die Spalte der alten Periode `A`) |
| Parteien 2020 | dieselben sechs wie 2025: `D1` CDU, `D2` SPD, `D3` GRÜNE, `D4` FDP, `D5` DIE LINKE, `D6` AfD (gegen das Ergebnis-GeoJSON mit benannten Spalten geprüft, 0 Abweichungen über 316 Stimmbezirke) | Die übrigen zehn Spalten (PIRATEN bis WIDERSTAND 2020) sind nicht Teil der Auswertung; Option 4 kann sie über `columns.results.parties` ergänzen |

## 3. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

### 3.1 Vorhanden im Worktree (Hauptperiode, nach `bootstrap` und `run`, 2026-10-11)

- `data/external/Stimmbezirk_Wahlergebnis.csv` (65 982 B, latin-1 mit BOM, `;`, 467 Zeilen: 306 Urnenstimmbezirke mit
  Geometrie, der Rest Briefwahlbezirke; Spalten u. a. `gebietnr`, `Kommunalwahlbezirk`, `Stadtbezirk`, `Stadtteil`,
  `Wahlberechtigte_insgesamt`, `Waehler`, `Davon_mit_Wahlschein`, `CDU_Stimmen` … `AfD_Stimmen`; Briefwahlbezirke
  tragen leere Wahlberechtigte und den Wahlbezirk).
- `data/external/Stimmbezirke_2025.geojson` (7 927 291 B, 306 MultiPolygone, EPSG:4647; Eigenschaften
  `Stimm-/ Wahlbezirk`, `Kommunalwahlbezirk Nr.`, `Kommunalwahlbezirk Name`, `Stadtteil Nr.`, `Stadtteil Name`,
  `Stadtbezirk Nr.`, Bundestags- und Landtagswahlkreis, `BezirksZuordnungen — Zuordnung_Briefwahlbezirk`).
- `data/processed/wahlbezirke_waehler.parquet` (41 × 16, 9 519 B): `wahlkreis_id` Int64, `Wahlberechtigte_insgesamt`,
  `Waehler`, sechs `<Partei>_Stimmen` Int64, `wahlbeteiligung` Float64, sechs `<Partei>_anteil` Float64.
- `data/processed/wahlbezirke_auswertung.parquet` (41 × 20, 135 841 B): die Wählerspalten plus `suchbegriffe`
  List(String), `paper_ids` List(String), `anzahl_treffer` Int64, `trefferquote` Float64.
- `data/processed/combined_searchdict.parquet` (41 × 2, 44 255 B), `inverted_index.parquet` (5841 × 3, 152 045 B),
  `wikidata_vis.parquet` (1309 × 4), `wahlbezirke_strassen.parquet` (41 × 2).
- `data/interim/papers.parquet` (19 108 × 9, 15 677 746 B): `id`, `name`, `reference`, `date` Date, `paper_type`,
  `main_file`, `file_name`, `download_url`, `text`; Datumsbereich 2020-09-14 bis 2025-09-12 (2020: 981, 2021: 4307,
  2022: 3923, 2023: 3877, 2024: 3503, 2025: 2517 Dokumente), keine fehlenden Daten.
- `data/raw/papers.jsonl` (9 245 584 B, 19 108 Zeilen) und `cache_root/text/texts.parquet` (15 018 867 B, 19 033 Texte):
  die Maßstäbe für den Schnappschuss der alten Periode (§ 2): rund 13 MB plus 21 MB bei 27 000 Dokumenten.
- Mini-Fixture `tests/fixtures/mini/`: 3 Wahlbezirke (1, 10, 38), 22 Stimmbezirke (`Stimmbezirke_2025.geojson`,
  94 930 B), 200 Dokumente (`paper_with_text.json`, 794 576 B), Ergebnis-CSV 5 438 B.

### 3.2 Open-Data-Portal Düsseldorf (Datensatzseiten am 2026-10-11 nachgesehen, Dateien ins Scratchpad geladen)

| Datensatz, Lizenz | Datei (exakte URL) | Format, Größe, Inhalt |
|---|---|---|
| „Ratswahl 2020 Düsseldorf", Datenlizenz Deutschland Namensnennung 2.0, zuletzt aktualisiert 2026-06-09 | `https://opendata.duesseldorf.de/sites/default/files/Ratswahl%202020%20%20Stimmbezirke-Ergebnis.csv` (zwei Leerzeichen vor `Stimmbezirke`) | CSV, 57 455 B, UTF-8 ohne BOM, `;`, 454 Zeilen: 316 Urnenstimmbezirke und 138 Briefwahlbezirke (`gebiet-name` endet auf „Briefwahlbezirk", `A` = 0, `B` = `B2`). Spalten: `datum;wahl;ags;gebiet-nr;gebiet-name;max-schnellmeldungen;anz-schnellmeldungen;A1;A2;A3;A;B;B2;C;D;D1;…;D16`. `A1` Wahlberechtigte ohne Sperrvermerk, `A2` mit Sperrvermerk W, `A3` nicht im Wählerverzeichnis, `A` insgesamt, `B` Wähler, `B2` davon mit Wahlschein, `C` ungültig, `D` gültig, `D1` bis `D16` Stimmen je Partei in Stimmzettelreihenfolge (§ 2, Parteien). **Keine Wahlbezirksspalte.** `gebiet-nr` vierstellig mit führender Null (`0101`), 316 von 316 Urnen-IDs identisch mit `Stimmbezchar` des GeoJSON. Gemeindesumme: 470 511 Wahlberechtigte, 247 356 Wähler (52,57 %), davon 113 292 mit Wahlschein |
| dito | `https://opendata.duesseldorf.de/sites/default/files/Ratswahl%202020%20%20Wahlbezirke-Ergebnis.csv` | CSV, 6 454 B, 41 Zeilen, gleiche Spalten; `gebiet-nr` `001` bis `041`, `gebiet-name` z. B. „001 Altstadt/Carlstadt/Stadtmitte/Pempelfort West"; `max-schnellmeldungen` = Zahl der Stimmbezirke einschließlich Briefwahl (13 für 001). Liefert Briefwähler je Wahlbezirk und die Validierung der geometrischen Zuordnung |
| dito | `https://opendata.duesseldorf.de/sites/default/files/RW_2020_Endg%C3%BCltiges_Ergebnis.geojson` | GeoJSON, 3 231 046 B, 316 Features, EPSG:4647, Eigenschaften `Stimmbezchar` und 25 benannte Ergebnisspalten (`… Tabelle_CDU Stimmen` usw.), ohne Briefwahl. Nur zur Verifikation der Spaltenzuordnung benutzt, nicht als Eingabe |
| dito | `https://opendata.duesseldorf.de/sites/default/files/Ratswahl%202020%20Gemeinde-Ergebnis.csv` | CSV, 347 B, 1 Zeile (Gemeindesumme), zur Plausibilitätsprüfung |
| „Wahlgebietseinteilung Düsseldorf – Stimmbezirkseinteilung", Datenlizenz Deutschland – Zero – Version 2.0 | `https://opendata.duesseldorf.de/sites/default/files/Stimmbezirke2020_neu_ETRS89_EPSG4647.geojson` | GeoJSON, 2 663 053 B, 316 Features (313 Polygon, 3 MultiPolygon), `crs` `urn:ogc:def:crs:EPSG::4647`, einzige Eigenschaft `Stimmbezchar` (String, `0101` … `9808`); 313 roh gültig, alle 316 nach `make_valid`; Flächensumme 217,32 km². 296 der 316 Nummern kommen auch 2025 vor, bezeichnen aber andere Flächen (Nummern werden wiederverwendet). Dazu Varianten WGS84 (`Stimmbezirke2020_neu_WGS84_EPSG4326.geojson`) und KML; vom Portal gibt es Stimmbezirke nur für 2020 und 2025 |
| „Wahlgebietseinteilung Düsseldorf – Kommunalwahlen", Datenlizenz Deutschland – Zero – Version 2.0 | `https://opendata.duesseldorf.de/sites/default/files/Kommunalwahlbezirke_ETRS89_4647_Stand2020_B_0.geojson` | GeoJSON, 763 620 B, 41 Polygone, EPSG:4647, Eigenschaften `Kommunalwahlbezirk` (Int), `Quelle` („Amt 12/1"), `Stand` („29.01.2020"), `Name`, `Beschreibung` (Grenzverlauf als Text); Flächensumme 217,72 km². Weitere Stände: 2009 (30.08.2009), 2019 (05.12.2019), 2025 |
| „Ratswahl 2014 Düsseldorf", Datenlizenz Deutschland – Zero – Version 2.0, aktualisiert 2026-06-09 | `https://opendata.duesseldorf.de/sites/default/files/Ratswahl%202014%20D%C3%BCsseldorf%20Stimmbezirk_2.csv` | CSV, 64 784 B, 454 Zeilen, anderes Format: `nr;name;maxschnellmeldungen;anzschnellmeldungen;wahlberechtigte;abgegeben;wahlbeteiligung;gueltigestimmzettel;gueltig;ungueltigestimmzettel;ungueltig;cdu;cdu_proz;spd;…`, `nr` ohne führende Null (`101`), keine Wahlbezirksspalte. Keine Stimmbezirksgeometrie 2014 im Portal. **Nicht gebraucht**: die Beteiligung einer Periode ist die der Wahl an ihrem Ende; für eine dritte Periode 2009 bis 2014 fehlt die Geometrie |

Lizenzhinweis für die Seite (wörtlich von den Datensatzseiten, Stand 11.10.2026): Ratswahl 2020 „Datenlizenz
Deutschland Namensnennung 2.0"; Stimmbezirks- und Wahlbezirkseinteilung „Datenlizenz Deutschland – Zero – Version
2.0". Beides steht schon in `ALLOWED_LINKS` (`DL_DE_BY`, `DL_DE_ZERO`).

### 3.3 OParl (eine Seite zur Formatprüfung, 2026-10-11, 56 s Antwortzeit)

`https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers?page=200`: 200 Paper, `date` von 2015-12-09 bis
2017-02-01 (2015: 60, 2016: 138, 2017: 2), kein Paper ohne Datum, keines gelöscht. **Kein Paper hat `mainFile`**, alle
200 haben `auxiliaryFile` (1 bis 8 Dateien; das erste ist die Vorlage: `fileName` `00257472.pdf`, `mimeType`
`application/pdf`, `downloadUrl` `http://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/downloadfiles/00257472.pdf`);
`OparlPaper.primary_file` fällt darauf zurück, `PaperRecord.from_oparl` liefert `file_name` und `download_url` für alle
200. `created` ist bei allen 2019-07-03 und `modified` 2024-12-30 (Migrationen des Systems), `modified_since` ist für
alte Paper also wertlos; `stop_when_older` arbeitet über `date` und bleibt richtig. `paperType` ist eine ältere
Taxonomie: „Verwaltungsvorlage" (119), „Vorlage aus der Politik" (81) statt „Beschlussvorlage", „Antrag" usw.; `reference`
sieht aus wie `174/ 8/2016` (für Option 5 relevant). `PaperPage.model_validate` nimmt die Seite ohne unbekannte Schlüssel
an. Die Seiten sind nicht streng nach Datum sortiert (14 Monate Spanne auf einer Seite).

Hochrechnung mit den Stützstellen Seite 1 ≈ September 2025, Seite 96 ≈ September 2020 (die Arbeit brach nach 95
Seiten ab), Seite 200 ≈ 2016, Seite 365 = älteste (aus `reference/raw/paper_urls.json`): die Periode 2014-05-25 bis
2020-09-12 liegt auf rund den Seiten 96 bis 235, also 25 000 bis 30 000 Paper. Kosten (Maßstab 2026-10-11: 85 s je
Seite, 2,8 GB und 5,8 h je 19 108 PDFs, 38 ms Extraktion je PDF, 4,1 s FlashText je 19 108 Dokumente): Metadaten
rund 3 h, PDFs 8 bis 11 h und 3,7 bis 4,4 GB (xtraspace hat 322 GB frei), Extraktion rund 17 min, Index rund 6 s.

### 3.4 Befunde der Erkundung (Prototyp im Scratchpad, 2026-10-11)

- Zuschnitt 2020 gegen 2025: **kein** Wahlbezirk gleicher Nummer blieb unter 1 % Flächenänderung; die symmetrische
  Differenz reicht von 9 % (Nr. 5) bis 855 % (Nr. 23: 2020 „Unterrath West", 2025 „Kaiserswerth, Lohausen, Stockum").
  Nummern und Namen sind neu vergeben; ein Vergleich über die Nummer wäre sinnlos.
- Stimmbezirke 2020 auf Wahlbezirke 2025: 83 von 316 liegen zu weniger als 99 % in einem Zielbezirk (88 ganz in einem,
  157 in zwei, 62 in drei, 8 in vier, 1 in fünf); 770 Paare mit Anteil über 10⁻⁴; die Abdeckung der Stimmbezirke
  durch die Zielbezirke liegt zwischen 97,76 % und 100 % (Stadtgrenze, Rhein).
- Zuordnung Stimmbezirk 2020 zu Wahlbezirk 2020 über den repräsentativen Punkt: 316 von 316 eindeutig, identisch mit
  der Zuordnung nach größter Schnittfläche (kleinster Hauptanteil 92,95 %); Summe der Wahlberechtigten je Wahlbezirk
  exakt gleich der Wahlbezirks-CSV (41 von 41). Briefwähler je Wahlbezirk 1 457 bis 4 453, Summe 110 265 = Summe der 138
  Briefwahlbezirke; je Wahlbezirk 2 bis 5 Briefwahlbezirke.
- Übertrag: Summe der Wahlberechtigten (470 511) und Wähler (247 356) exakt erhalten; Gewichte je Zielbezirk summieren
  zu 1 (bis 10⁻⁹), höchstens 30 Quellen je Ziel. Identitätsprobe Stimmbezirke 2025 auf Wahlbezirke 2025: 306 von 306
  Anteile gleich 1 (bis 10⁻⁶), jeder Hauptanteil trifft die `district_id` des GeoJSON.
- Umgerechnete Wahlbeteiligung 2020 je Wahlbezirk 2025: 0,373 bis 0,672 (2025: 0,357 bis 0,670); Korrelation mit der
  Beteiligung 2025 r = 0,982. Native Beteiligung je Wahlbezirk 2020: 0,387 bis 0,681.
- Sensitivität: Briefwahl proportional zu A2 gegen proportional zu A ändert die umgerechnete Beteiligung um höchstens
  5,1 Prozentpunkte (Median 0,6); Flächenanteil gegen Ganzzuordnung um höchstens 2,6 Prozentpunkte (Median 0,3) und bis
  4 262 Wahlberechtigte. Beides steht als Satz auf der Seite (§ 6).

### 3.5 Was fehlt

Der Korpus 2014 bis 2020 (Netz, Konrads Lauf), danach der Schnappschuss `snapshots/2014-2020/`. Bis dahin tragen die
synthetische Mini-Periode (§ 5, Stufe E) und die Fake-Session die Tests; die Seite auf `main` zeigt den Vergleich erst
nach Stufe H.

## 4. Berührungspunkte im bestehenden Code (Datei, Funktion, was sich ändert)

| Datei | Funktion oder Stelle | Änderung |
|---|---|---|
| `src/georep/settings.py`, `defaults.toml` | `Period` | neue Felder `name: str = ""` (nur `[a-z0-9-]`, Validator), `label: str`, `election: date \| None` (Standard `end`), `dictionary: Literal["own", "base"] = "own"`; Validator: `election` innerhalb oder am Ende der Periode |
| dito | `OparlSource` | `first_page: int = 1` (≥ 1) |
| dito | `OpendataSource` | `district_shapes_url: str = ""`, `district_results_url: str = ""`, `districts_file: str = "Stimmbezirke_2025.geojson"` (Dateiname der Eingabe, § 2) |
| dito | `ResultsColumns` | `precinct: str = ""`, `eligible_postal: str = ""`, `postal_marker: str = ""`; `district` darf leer sein, dann kommt der Wahlbezirk aus der Zuordnung; `encoding` je Profil (2020: `utf-8`) |
| dito | neu `Crosswalk(_Strict)`, `Compare(_Strict)` | `[crosswalk] target = "base"`, `min_coverage = 0.95`; `[compare] period = ""`; beide Teil des Fingerprints |
| `src/georep/layout.py` | `Layout` | Feld `period: str = ""`; `root` = `data_root / period` oder `data_root`; `external`, `raw`, `interim`, `processed`, `site` hängen an `root`; `text_dir` = `cache_root / "text" / period`; `districts_geojson` = `external / districts_file` (Feld `districts_file`); neu `district_shapes_geojson` (`external / "Kommunalwahlbezirke.geojson"`), `district_results_csv` (`external / "Wahlbezirk_Wahlergebnis.csv"`), `precinct_assignment` (`processed / "stimmbezirke_zuordnung.parquet"`), `comparison` (`processed / "wahlbezirke_vergleich.parquet"`), `papers_progress` (`raw / "papers.progress.json"`); `base()` (dasselbe Layout mit `period=""`), `for_period(name)`; `from_settings` setzt beides; `reference_view()` bleibt flach |
| `src/georep/geo.py` | `read_precincts` | Spalten `district_id`/`district_name` optional (leer): dann `district_id = 0`, `district_name = ""`, und der Aufrufer liefert die Zuordnung; neu `read_shapes(path, id_column, name_column, working_crs) -> dict[int, (name, geometry)]` für die 41 Polygone |
| neu `src/georep/crosswalk.py` | `assign_by_point`, `area_shares`, `target_weights`, `transfer_counts`, `largest_remainder` | das Modul der Umrechnung (§ 5, Stufe B); reine Funktionen auf shapely-Geometrien und Polars-Frames, Verträge in `georep.contracts` |
| `src/georep/contracts.py` | neu `sums_to_one(frame, group, column, tol)`, `columns_preserved(before, after, columns)` | Prädikate der neuen Verträge |
| `src/georep/prep/voters.py` | `read_results_csv`, `aggregate_voters` | Umbenennung auf kanonische Namen (`ELIGIBLE`, `VOTERS`, `<Partei>_Stimmen`) beim Lesen; neu `precinct_counts` (eine Zeile je Urnenstimmbezirk, Briefwahlzeilen über `postal_marker` getrennt), `spread_postal` (Briefwähler je Quellbezirk proportional `eligible_postal`), `aggregate_transferred` (gleiche Ausgabe wie `aggregate_voters`, aus übertragenen Zählgrößen) |
| `src/georep/analysis/hits.py` | `join_voters` | liest `ELIGIBLE` aus `prep.voters`, nicht `columns.eligible` |
| neu `src/georep/analysis/periods.py` | `compare_periods`, `delta_regression` | § 5, Stufe F |
| `src/georep/sources/oparl.py` | `fetch_papers` | `first_page`, `progress`-Callback je Seite, Start von `?page=N`; `FetchReport` nennt Start- und Endseite |
| `src/georep/sources/opendata.py` | neu `fetch_district_shapes`, `fetch_district_results` | dieselben Prüfungen wie die beiden vorhandenen Fetcher |
| `src/georep/bootstrap.py` | `bootstrap` | natives Schnappschuss-Format (`raw/papers.jsonl`, `cache/text/texts.parquet` kopieren) neben dem Altformat; kopiert `Kommunalwahlbezirke.geojson` und `Wahlbezirk_Wahlergebnis.csv`, wenn in der Referenz vorhanden; bei `period.dictionary = "base"` keine Rohdaten für Straßen und Orte |
| `src/georep/pipeline.py` | `build_steps` | `opendata` schreibt bis zu vier Dateien; neuer Schritt `precincts` (nur mit `crosswalk`-Profil, vor `voters`); `voters` wählt den Pfad nach `columns.results.district`; `papers` mit `first_page` und Fortschritt; bei `period.dictionary = "base"` entfallen `streets_osm` und `pois_wiki`, und `streets`, `pois` lesen `layout.base().streets` bzw. `.pois`; neuer Schritt `compare` (nur mit `compare.period`), `report` bekommt dann `layout.comparison` als Eingabe |
| `src/georep/report/model.py` | `DataStand`, `ReportModel`, `build_report_model`, `COLUMN_DOCS`, `published_tables`, `district_rows` | `election` aus `period.election`; neu `PeriodInfo` (name, label, start, end, election) und `PeriodComparison \| None` (Zeilen je Bezirk, Regression der Differenzen, Tabelle 5 der alten Periode, Sensitivitätssätze aus `stimmbezirke_zuordnung`); Spaltendoku für `wahlbezirke_vergleich` und `stimmbezirke_zuordnung`; Wählerspalten über Konstanten |
| `src/georep/report/charts.py` | neu `delta_scatter` | Streudiagramm der Änderungen, Punkte mit Nummer, eine Gerade; wiederverwendet `nice_ticks`, Achsen von `scatter` (herausziehen in `_axes`) |
| `src/georep/report/templates/report.html.j2` | Zeilen 8, 111, 112, 233, 263 (Titel, Datenstand, englische Kurzfassung, Methode, Lizenzen) | Periodentexte aus `model.period` (Label, Wahltag, Jahr der Ratswahl); neuer Abschnitt `<section id="perioden">` zwischen „Trefferquote und Wahlbeteiligung" und „Je Wahlbezirk", nur bei `model.comparison`; Link auf die Unterseite |
| `src/georep/report/templates/map.html.j2` | Zeile 7 | Beschreibung mit Periodenlabel |
| `src/georep/report/build.py` | `DESCRIPTIONS`, `build_site` | „Ratswahl 2025" aus `period.election.year`; Downloads `wahlbezirke_vergleich.parquet/.csv` (Hauptperiode mit Vergleich) und `stimmbezirke_zuordnung.parquet/.csv` (Periode mit Crosswalk); `SiteSummary` zählt sie mit |
| `src/georep/report/geometry.py` | `wahlbezirke_geojson` | `name` aus Periodenlabel statt „Kommunalwahlbezirke Düsseldorf 2025" |
| `src/georep/report/render.py` | Kommentar zu den Lizenzen | Ratswahl 2020 ergänzen; `ALLOWED_LINKS` unverändert |
| `src/georep/export.py` | `csv_plan` | zwei Einträge für Zuordnung und Vergleich, nur wenn die Dateien existieren (so arbeitet `export_csv` schon) |
| `src/georep/cli.py` | `_cmd_status` | zeigt `period.name` und `root`; `fetch` ohne Änderung (Netzschritte des Profils) |
| `noxfile.py` | `VERIFY_TARGETS` | `georep.crosswalk.largest_remainder` |
| `tests/fixtures/make_mini.py` | neu `write_period_fixture` | synthetische Periode `tests/fixtures/mini-2014/` (§ 5, Stufe E) |
| `tests/unit/__snapshots__/test_cli.ambr` | `test_steps_output_is_stable` | unverändert (Default-Profil); neuer Snapshot für `--settings settings.2014.toml steps` |
| `tests/golden/test_pipeline.py`, `tests/unit/test_cli.py` | Zählungen „9 geplant" | unverändert für das Default-Profil; neue Tests für das Profil in `tests/golden/test_period_pipeline.py` |
| `.github/workflows/pages.yml` | Schritte nach `uv sync` | erst die alte Periode (`--settings settings.2014.toml bootstrap`, `run`), dann `--settings settings.vergleich.toml run`, dann `cp -r data/2014-2020/site data/site/2014-2020` (Stufe G) |
| `README.md`, `docs/architecture.md`, `docs/decisions.md`, `CHANGELOG.md`, `STATUS.md` | Abschnitte Befehle, Pipeline, Datenhaltung, Daten und Herkunft, ein Punkt in decisions je Entscheidung aus § 2 | Stufe G |

Neue Dateien im Repo: `settings.2014.toml`, `settings.vergleich.toml`, `src/georep/crosswalk.py`,
`src/georep/analysis/periods.py`, `tests/unit/test_crosswalk.py`, `tests/property/test_crosswalk_props.py`,
`tests/unit/test_periods.py`, `tests/golden/test_period_pipeline.py`, `tests/fixtures/mini-2014/` (mit README),
später `snapshots/2014-2020/` (mit README). Keine neue Abhängigkeit.

## 5. Bauplan in Stufen (je Stufe: Schritte, Tests, Verträge, Abnahmekriterium, geschätzter Aufwand)

Reihenfolge: A bis G offline und vollständig testbar; H ist Konrads Lauf. Jede Stufe ein bis drei Commits,
Verhaltensänderung zuerst mit rotem Test, `uv run nox` nach jedem Commit (Alltag `uv run pytest -n 2`), Tests in
`tmp_path`. Aufwand in Agentenstunden ohne Netzwartezeit; Summe A bis G rund 30 h, H rund 2 h Agent plus zehn bis
vierzehn Stunden Netz bei Konrad.

### Stufe A: Periode als Profil (Settings, Layout, Bootstrap-Grundlagen)

1. `Period` mit `name`, `label`, `election`, `dictionary`; `OparlSource.first_page`; `OpendataSource` mit den drei neuen
   Feldern; `ResultsColumns` mit `precinct`, `eligible_postal`, `postal_marker`; `Crosswalk`, `Compare`. Defaults so,
   dass der Fingerprint der Hauptperiode sich ändert (neue Schlüssel) und alle Stamps einmal „Settings geändert" melden;
   das ist gewollt und steht im Commit. Tests: `test_settings.py` (Profil lädt, `name` validiert, `election` außerhalb
   der Periode ist ein Fehler, `first_page = 0` ist ein Fehler). Abnahme: `uv run georep --settings settings.2014.toml
   status` druckt Periode und Pfade. 2 h.
2. `Layout.period`, `root`, `base()`, `for_period`, `text_dir` je Periode, neue Pfade, `districts_file`; `guard_writable`
   unverändert. Tests: `test_layout.py` (Hauptperiode flach wie bisher; Profil unter `data_root/2014-2020/`; `base()`
   zeigt auf die flache Ablage; Textstore je Periode; `reference_view()` flach). Abnahme: alle vorhandenen
   Layout-Tests grün, Pfade der Hauptperiode byteidentisch zu heute (Test vergleicht die Properties). 2 h.
3. `settings.2014.toml` und `settings.vergleich.toml` im Repo mit Kommentar je Zeile (Warum, wie in `defaults.toml`).
   Abnahme: `load_settings(explicit=…)` für beide; Fingerprints verschieden. 1 h.

### Stufe B: Umrechnung `georep/crosswalk.py`

1. `assign_by_point(sources: Mapping[str, BaseGeometry], targets: Mapping[int, BaseGeometry]) -> dict[str, int]`:
   STRtree über die Ziele, repräsentativer Punkt je Quelle, `within`; Vertrag post: jede Quelle genau ein Ziel;
   `raises(SchemaError)` bei keinem oder mehreren Treffern (Fehlertext nennt die Quelle). 1,5 h.
2. `area_shares(sources, targets, *, min_coverage) -> pl.DataFrame` mit Spalten `source_id` String, `target_id` Int64,
   `share` Float64, `coverage` Float64 (Schnittsumme durch Fläche der Quelle, je Quelle konstant); Anteile auf die
   Schnittsumme normiert, Paare unter 10⁻⁹ fallen weg; sortiert nach (`source_id`, `target_id`). Verträge: pre: alle
   Geometrien gültig und nicht leer, Ziel-IDs eindeutig; post: `0 < share ≤ 1`, `sums_to_one(result, "source_id",
   "share", 1e-9)`, jede Quelle vorhanden, `target_id ⊆ targets`; `raises(SchemaError)` wenn eine Abdeckung unter
   `min_coverage` liegt. 3 h.
3. `target_weights(shares, counts, weight_column) -> pl.DataFrame` (`source_id`, `target_id`, `weight`): Flächenanteil
   mal Zählgröße der Quelle, je Ziel normiert; Vertrag post: `sums_to_one(result, "target_id", "weight", 1e-9)`, Gewichte
   in [0, 1]. Das ist der vom Briefing verlangte Vertrag „Gewichte je Zielbezirk summieren zu 1". 1 h.
4. `largest_remainder(values: Sequence[float]) -> list[int]`: ganzzahlig, Summe gleich der gerundeten Summe der
   Eingabe, jeder Wert weicht um weniger als 1 ab; `deal.pure`, `deal.cases`, crosshair-Ziel. 1 h.
5. `transfer_counts(counts: pl.DataFrame, shares, columns) -> pl.DataFrame` (`target_id` plus die Zählspalten,
   Int64): Anteil mal Wert, Summe je Ziel, dann `largest_remainder` je Spalte; Vertrag ensure: Spaltensummen exakt
   erhalten (`columns_preserved`), `sorted_unique(result, "target_id")`, alle Werte nicht negativ. 2 h.
6. Tests: `tests/unit/test_crosswalk.py` mit Rechtecken (handgerechnete Anteile, ein Loch, ein MultiPolygon, eine
   Quelle ohne Ziel, Abdeckung unter der Schwelle); `tests/property/test_crosswalk_props.py` mit hypothesis: zwei
   Gitter aus zufälligen Schnitten auf [0, 1000]², Zielzellen zufällig zu 1 bis 3 „Bezirken" vereinigt, zufällige
   nicht negative Zählspalten; Eigenschaften: Anteile je Quelle summieren zu 1, Gewichte je Ziel zu 1, Summen je
   Spalte erhalten (vor und nach der Rundung), bei gleichen Schnitten Identität (genau ein Paar je Quelle mit Anteil 1
   und dem eigenen Bezirk), bei verkleinertem Zielgebiet Abdeckung unter 1 nur am Rand und `SchemaError` unter der
   Schwelle. Golden: `area_shares` der 306 Stimmbezirke 2025 auf die 41 vereinigten Wahlbezirke 2025 liefert 306 Paare
   mit Anteil 1 und trifft `district_id` (als `slow`-Test auf der Referenz, auf der Mini-Fixture schnell). 3 h.
7. Abnahme der Stufe: `nox` grün, `nox -s verify` findet kein Gegenbeispiel für `largest_remainder`, Laufzeit von
   `area_shares` für 316 × 41 unter 5 s (Benchmark in `tests/bench`, Baseline anlegen). Gesamt 11,5 h.

### Stufe C: Wähler 2020 auf Wahlbezirken 2025 (Schritte `precincts` und `voters`)

1. `read_shapes` in `geo.py` (41 Polygone mit Nummer und Name) und `read_precincts` mit leeren Wahlbezirksspalten.
   Test mit dem Mini-2014-GeoJSON (Stufe E liefert es; bis dahin ein synthetisches Dreieck im Test). 1,5 h.
2. Schritt `precincts` (nur bei gesetztem `[crosswalk]`): liest `districts_geojson` (Stimmbezirke der Periode),
   `district_shapes_geojson` (Wahlbezirke der Periode) und `layout.base().districts_geojson` (Zielzuschnitt, über
   `district_shapes` aus `report.geometry` vereinigt); schreibt `stimmbezirke_zuordnung.parquet` mit `stimmbezirk_id`
   String, `wahlbezirk_quelle` Int64, `wahlbezirk_quelle_name` String, `wahlkreis_id` Int64 (Ziel), `anteil` Float64,
   `abdeckung` Float64. Eingaben im Schrittregister: die drei GeoJSON-Dateien; `MissingInputError` nennt, dass die
   Hauptperiode zuerst `bootstrap` braucht. 2 h.
3. `prep.voters.precinct_counts(csv, columns)`: eine Zeile je Urnenstimmbezirk mit `stimmbezirk_id`, `ELIGIBLE`,
   `eligible_postal`, `VOTERS`, `<Partei>_Stimmen`; Briefwahlzeilen (Name enthält `postal_marker`) getrennt
   zurückgegeben; Zahlen wie bisher (`_to_int`); Vertrag: Pflichtspalten, keine Dublette je `stimmbezirk_id`.
   `read_district_results(csv, columns)`: 41 Zeilen mit `wahlbezirk_quelle`, `ELIGIBLE`, `VOTERS`. 2 h.
4. `spread_postal(precincts, assignment, district_results)`: Briefwähler je Quellbezirk = `VOTERS` (Bezirk) minus Summe
   der Urnenwähler; verteilt proportional `eligible_postal`; Vertrag ensure: Summe der Wahlberechtigten je Quellbezirk
   gleich der Bezirkszeile (sonst `SchemaError`: „Zuordnung passt nicht zur Wahlbezirks-CSV"), Summe der Wähler nach der
   Verteilung gleich der Summe der Bezirkszeilen (bis 10⁻⁶), keine negativen Briefwähler. 2 h.
5. Schritt `voters` im Profil: `precinct_counts`, `spread_postal`, `transfer_counts` über die Zuordnung, dann
   `aggregate_transferred` (Beteiligung und Anteile wie `aggregate_voters`); Ausgabe `wahlbezirke_waehler.parquet` mit
   genau dem Schema der Hauptperiode (Test: `pl.read_parquet_schema` gleich). Für die Hauptperiode bleibt
   `aggregate_voters` (mit Umbenennung auf die kanonischen Namen, No-op). 2 h.
6. Tests: Unit mit drei Stimmbezirken und zwei Bezirken (Hand gerechnet); hypothesis für `spread_postal` (Summen,
   Nichtnegativität, Verteilung proportional); Golden Master unverändert (`test_pipeline.py`, `pytest -m slow`).
   Abnahme: auf der synthetischen Mini-Periode (Stufe E) laufen `precincts` und `voters`, `wahlbezirke_waehler.parquet`
   hat die Ziel-IDs 1, 10, 38 und die Summe der Wahlberechtigten der CSV. Gesamt 10 h (mit Tests 1,5 h extra).

### Stufe D: Abruf vorbereiten (ohne Netz)

1. `fetch_papers(..., first_page=1, progress=None)`: Start bei `endpoint?page=N` (N > 1), `progress(page_url, pages)`
   nach jeder Seite; `FetchReport` nennt erste und letzte Seite. Schritt `papers` schreibt `raw/papers.progress.json`
   (letzte vollständig gespeicherte Seite, Datum) nach jeder Seite und startet beim nächsten Lauf dort, wenn der Store
   schon Paper hat und `incremental = false`; `--force` setzt den Fortschritt zurück. Test mit `FakeSession` über vier
   Seiten: Abbruch nach Seite 2 (Exception der Fake-Session), zweiter Lauf beginnt bei Seite 3, am Ende alle Paper im
   Store genau einmal. Vertrag post von `fetch_papers` bleibt (`kept == len(records)`). 3 h.
2. `fetch_district_shapes`, `fetch_district_results` in `sources/opendata.py`; Schritt `opendata` schreibt sie nur,
   wenn die URLs gesetzt sind. Tests wie `test_sources_opendata.py`. 1 h.
3. `settings.2014.toml`: `first_page = 90`, `incremental = false`, `cache.oparl_pages_s = 2592000`, die vier Portal-URLs
   aus § 3.2, `columns.results` für das 2020-Format, `period.dictionary = "base"`, `reference_root =
   "snapshots/2014-2020"`. `georep --settings settings.2014.toml run --dry-run --online` plant die Netzschritte ohne
   `streets_osm` und `pois_wiki`. 0,5 h.
4. README-Abschnitt „Zweite Periode abrufen" (Konrads Lauf, Stufe H): Befehle, erwartete Dauer je Schritt, Wiederaufnahme,
   Platzbedarf, was danach zu committen ist. 1 h.
5. Abnahme: `nox` grün; Netztests mit Marker `network` existieren für die vier Portal-Dateien und eine OParl-Seite ab
   `first_page`, laufen nur von Hand. Gesamt 5,5 h.

### Stufe E: Synthetische Mini-Periode und Schnappschuss-Format

1. `bootstrap`: natives Format erkennen (`reference/raw/papers.jsonl` und `reference/cache/text/texts.parquet`
   vorhanden): beides kopieren (Textstore in `cache_root/text/<period>/`), Altformat wie bisher; `district_shapes` und
   `district_results` kopieren, wenn vorhanden; bei `period.dictionary = "base"` werden `streets_per_district.json` und
   `wikipedia_dict.json` nicht erwartet (Report nennt sie nicht als fehlend). Tests in `test_bootstrap.py`. 2 h.
2. `make_mini.write_period_fixture()` schreibt `tests/fixtures/mini-2014/` deterministisch aus der Mini-Fixture:
   `external/Stimmbezirke_2020.geojson` (die 22 Stimmbezirke, davon 6 entlang der Senkrechten durch den Schwerpunkt
   geteilt, 28 Features mit Eigenschaft `Stimmbezchar`, IDs wie `1302a`, `crs` EPSG:4647 wie die Quelle);
   `external/Kommunalwahlbezirke_2020.geojson` (drei Polygone 101, 110, 138 als Vereinigungen mit verschobener
   Zuordnung: 101 = Bezirk 1 plus die a-Hälften aus 10, 110 = Rest von 10 plus a-Hälften aus 38, 138 = Rest von 38;
   Eigenschaften `Kommunalwahlbezirk`, `Name`); `external/Stimmbezirk_Wahlergebnis.csv` im 2020-Format (`A` = Fläche
   mal Wahlberechtigte 2025 des Stimmbezirks, `A2` = 30 % von `A`, `B` = 45 % von `A`, `D1` bis `D6` aus den 2025-Stimmen
   mal Anteil, dazu zwei Briefwahlbezirke je Bezirk mit `A` = 0 und `B` = 80 % der `A2`-Summe des Bezirks, Rest `0`);
   `external/Wahlbezirk_Wahlergebnis.csv` (drei Zeilen, Summen, `max-schnellmeldungen` = Urnen plus 2);
   `raw/papers.jsonl` und `cache/text/texts.parquet` aus jedem zweiten der 200 Mini-Dokumente (100 Stück), `date` um
   sechs Jahre zurückgesetzt (2014 bis 2019), IDs und URLs unverändert; README mit Herkunft und dem Satz, dass alles
   synthetisch ist und keinen Datenstand abbildet. Unter `tests/fixtures/mini/expected/` ändert sich nichts (Test:
   `git status` dort leer). Größe unter 500 KB. 4 h.
3. `tests/golden/test_period_pipeline.py`: Basis-Layout aus `mini_run`, Profil-Layout `Layout(tmp/data, tmp/cache,
   mini-2014, period="2014-2020")`; Settings aus `settings.2014.toml` mit überschriebenen Pfaden (`model_copy`);
   `bootstrap` meldet 0 fehlende Dateien; `run_pipeline` offline: `texts`, `precincts`, `voters`, `streets`, `pois`,
   `dictionary`, `corpus`, `index`, `results`, `report` ausgeführt; zweiter Lauf überspringt alles; Zuordnung hat 28
   Quellen mit Anteilsummen 1; `wahlbezirke_waehler.parquet` hat die IDs 1, 10, 38; `combined_searchdict.parquet`
   byteidentisch mit dem der Basis; Seite baut mit Periodenlabel. CLI-Test: `main(["--settings", "settings.2014.toml",
   "run"])` in einem Projektverzeichnis mit `settings.toml` (Pfade) ist 0. 3 h.
4. Abnahme: `uv run georep --settings settings.2014.toml bootstrap && … run` offline grün auf der Mini-Periode
   (Testfixture als `reference_root`); `nox` grün; Abdeckung über 90 %. Gesamt 9 h.

### Stufe F: Vergleich (`analysis/periods.py`, Schritt `compare`)

1. `compare_periods(current: pl.DataFrame, previous: pl.DataFrame, *, labels: tuple[str, str]) -> pl.DataFrame`:
   Spalten `wahlkreis_id`, `periode_alt`, `periode_neu` (konstante Strings), `anzahl_treffer_alt`,
   `Wahlberechtigte_alt`, `trefferquote_alt`, `wahlbeteiligung_alt`, dieselben vier mit `_neu`, `d_trefferquote`,
   `d_wahlbeteiligung`. Verträge: pre: beide Eingaben haben dieselbe Menge `wahlkreis_id`; post: `sorted_unique`,
   Differenzen gleich neu minus alt (bis 10⁻¹²), Höhe gleich der Eingabe. `delta_regression(frame)` =
   `regress(frame, x="d_trefferquote", y="d_wahlbeteiligung")` (vorhandene Funktion mit Spaltennamen). 2 h.
2. Schritt `compare` (nur mit `compare.period`): Eingaben `layout.results`, `layout.for_period(p).results`,
   `layout.dictionary`, `layout.for_period(p).dictionary`; prüft `digest` beider Wörterbücher gleich (sonst
   `SchemaError`: „Vergleich setzt dasselbe Wörterbuch voraus"); schreibt `wahlbezirke_vergleich.parquet`
   (Schema-Version 1). `csv_plan` kennt die Datei. 1,5 h.
3. Tests: Unit mit drei Bezirken, hypothesis (Differenzen antisymmetrisch beim Tausch der Eingaben, Regression der
   Differenzen mit `r` in [-1, 1]), Golden auf Mini plus Mini-2014. Abnahme: `georep --settings settings.vergleich.toml
   run` auf der Mini-Fixture mit vorher gerechneter Mini-Periode schreibt die Datei mit 3 Zeilen. Gesamt 5 h.

### Stufe G: Seite, Pages, Dokumentation

1. `report.model`: `PeriodInfo`, `PeriodComparison` (Zeilen aus `wahlbezirke_vergleich`, `delta_regression`,
   Tabelle 5 der alten Periode aus `layout.for_period(p).results`, die beiden Sensitivitätszahlen aus
   `stimmbezirke_zuordnung` der alten Periode: Anteil geteilter Stimmbezirke, kleinste Abdeckung); Spaltendoku; Verträge
   post wie bei `district_rows` (eine Zeile je Bezirk, Perioden benannt). 3 h.
2. `charts.delta_scatter`, Abschnitt `<section id="perioden">` in der Vorlage: ein Absatz (Methode der Umrechnung in
   drei Sätzen, Sensitivität), das Streudiagramm, die Regressionstabelle der Differenzen (n, Steigung, r, R², p) und
   Tabelle 5 der alten Periode daneben, die sortierbare Tabelle je Wahlbezirk (Nr., Name, Treffer alt/neu, Trefferquote
   alt/neu, Beteiligung alt/neu, Δ Trefferquote, Δ Beteiligung), Link auf `2014-2020/index.html`; alle Periodentexte
   aus `model.period`. Tests: HTML parst, Abschnitt fehlt ohne Vergleich, jede Zahl aus dem Modell; Snapshot nur für die
   Regressionstabelle der Mini-Daten. 4 h.
3. Unterseite: `build_site` für ein Profil baut dieselbe Seite mit Periodentexten („Wahlperiode 2014 bis 2020",
   „Ratswahl 13.09.2020", Lizenzsatz zur Ratswahl 2020, Hinweis auf die Umrechnung im Datenstand) und den Downloads
   `stimmbezirke_zuordnung.parquet/.csv`. `pages.yml` ergänzen (§ 4). Headless-Chrome-Sicht beider Seiten (§ 8.4 des
   Meta-Plans), hell und dunkel. 3 h.
4. Dokumentation: README (Befehle mit `--settings`, Abschnitt „Zwei Perioden", Daten und Herkunft mit den 2020-Quellen
   und Lizenzen), `architecture.md` (Module `crosswalk`, `analysis/periods`; Pipeline mit `precincts`, `compare`;
   Datenhaltung je Periode), `decisions.md` (ein Punkt je Zeile aus § 2), `CHANGELOG.md` unter „Unreleased", `STATUS.md`.
   2 h.
5. Abnahme: `index.html` unter 1,5 MB (Ziel rund 740 KB, § 6); ohne `settings.vergleich.toml` ist die Seite der
   Hauptperiode bis auf die neuen Settings-Schlüssel im Stamp unverändert (Test: kein Abschnitt `perioden`);
   `nox`, `pytest -m slow`, `nox -s bench` grün; `grep -rn "Düsseldorf\|0015\|2025" src/` trifft nur Settings,
   Docstrings und `defaults.toml`. Gesamt 12 h.

### Stufe H: Konrads Lauf, Schnappschuss, Vergleich live

1. Konrad (nach Freigabe, § 8 Frage 5): `export UV_…`; `uv run georep --settings settings.2014.toml bootstrap` (nur die
   Portaldateien: `fetch opendata`), `uv run georep --settings settings.2014.toml fetch papers` (rund 3 h, wiederaufnehmbar
   je Seite), `… fetch pdfs` (8 bis 11 h, wiederaufnehmbar je Datei; `--limit` für Stichproben), `… run` (Extraktion rund
   17 min, Rest Sekunden). Dauer und Zähler kommen in `docs/profiling/README.md` mit Datum.
2. Agent: `snapshots/2014-2020/` anlegen (Kopie von `external/`, `raw/papers.jsonl`, `cache/text/<period>/texts.parquet`,
   README mit Abrufdatum, Seitenbereich, Zählern, Größen; Ergebnis des Vergleichs `ls -l`), `reference_root` des Profils
   zeigt darauf; `bootstrap` aus dem Schnappschuss reproduziert die Ergebnisse byteidentisch (Test `slow` auf dem
   Schnappschuss, analog zur Referenz); `pages.yml` baut beide Perioden; Seite live mit dem Abschnitt „Zwei
   Wahlperioden"; `STATUS.md` mit den Zahlen. 2 h Agent.
3. Abnahme: Pages grün, Unterseite erreichbar, Prüfsummen stimmen; `georep status` im Profil zeigt alles aktuell.

## 6. Auswirkung auf die Berichtsseite (Abschnitt, Größe in KB, Unterseite ja/nein)

- Hauptseite `index.html` (heute 686 KB): neuer Abschnitt „Zwei Wahlperioden" nach „Trefferquote und Wahlbeteiligung":
  Absatz zur Umrechnung (Stimmbezirke 2020 auf Wahlbezirke 2025 über Flächenanteile, Briefwahl proportional zu den
  Wahlscheinen, die beiden Sensitivitätszahlen aus § 3.4 als Satz), Streudiagramm Δ Trefferquote gegen Δ Wahlbeteiligung
  (rund 20 KB SVG, 41 Punkte mit Nummer, eine Gerade), Regressionstabelle der Differenzen und Tabelle 5 der alten
  Periode nebeneinander (rund 3 KB), sortierbare Tabelle je Wahlbezirk mit neun Spalten (rund 15 KB), Link auf die
  Unterseite. Zuwachs rund 45 KB, Ziel rund 740 KB, Budget 1,5 MB hält. Ohne Vergleichsprofil fehlt der Abschnitt. Die
  Periodentexte im Kopf (Datenstand, Kurzfassung) und im Fuß (Lizenz der Ratswahl) kommen aus den Settings.
- Downloads der Hauptseite: `wahlbezirke_vergleich.parquet` (41 Zeilen, rund 8 KB) und `.csv` (rund 6 KB), mit
  Spaltenschema in `schema.json`.
- Unterseite `2014-2020/index.html` (ja): dieselbe Vorlage für die alte Periode mit eigenem `karte.html` und `data/`;
  zusätzlich `stimmbezirke_zuordnung.parquet/.csv` (770 Zeilen, rund 15 KB) als Download; erwartete Größe wie die
  Hauptseite (rund 700 KB) plus `data/` rund 9 MB (`dokumente.json` der alten Periode rund 3 MB). Die Seite gesamt
  wächst von 8,4 MB auf rund 18 MB.
- `karte.html` unverändert bis auf die Beschreibung.

## 7. Risiken und Fallstricke

- **Der Abruf ist der kritische Pfad.** Zehn bis vierzehn Stunden Netz, nur Konrad darf ihn starten (§ 2 des Meta-Plans);
  ohne ihn bleibt der Vergleich auf `main` unsichtbar. Alles davor ist mit der synthetischen Periode und der Fake-Session
  prüfbar; die Reihenfolge A bis G hält `main` unabhängig vom Lauf.
- **Seitenverschiebung.** `first_page = 90` gilt für den Stand 2026-10; jedes neue Paper schiebt die alten Seiten um
  1/200 nach hinten. Der Wert liegt deshalb fünf Seiten vor der Grenze, und `in_period` filtert; `papers.progress.json`
  hält die zuletzt gespeicherte Seite als URL, nicht als Annahme. Unsichtbar bleibt, wenn der Server die Sortierung
  ändert; der Fetch-Report nennt die Datumsspanne jeder Seite im Log.
- **`modified` ist das Migrationsdatum.** `incremental = true` im Profil würde nach dem ersten Lauf nichts mehr holen;
  der Validator von `Period` warnt nicht, aber `settings.2014.toml` und der README-Abschnitt sagen es. Für Option 7
  (laufende Periode) bleibt `incremental` richtig.
- **`stop_when_older` mit 14 Monaten Spanne je Seite.** Der Abbruch kommt erst, wenn eine ganze Seite vor dem
  Periodenbeginn liegt; das kostet höchstens einige Seiten nach 2014-05, keine Paper.
- **Zuordnung ohne Schlüssel.** Die 2020-Dateien tragen keinen Wahlbezirk; die geometrische Zuordnung ist durch die
  Summenprobe gegen die Wahlbezirks-CSV abgesichert (Vertrag in `spread_postal`). Ändert das Portal eine Datei, schlägt
  die Probe an, bevor etwas Falsches entsteht.
- **Briefwahl 44,6 %.** Die Verteilung auf Stimmbezirke ist ein Modell (§ 2); bis 5,1 Prozentpunkte je Bezirk hängen
  daran. Die Seite sagt das, und `stimmbezirke_zuordnung.parquet` macht es nachrechenbar.
- **Abdeckung unter 100 %.** Stadtgrenze und Rhein lassen 2,2 % Fläche unbedeckt; die Normierung auf die Schnittsumme
  erhält die Summen, die Schwelle `min_coverage = 0.95` fängt echte Lücken (etwa ein falsches CRS).
- **Fließkomma.** Anteile und Gewichte nie auf Gleichheit testen; Toleranzen 10⁻⁹ für Summen, `largest_remainder` macht
  die Zählgrößen ganzzahlig und die Summen exakt.
- **Stamps und Fingerprint.** Neue Settings-Schlüssel ändern den Fingerprint der Hauptperiode einmalig (alle Schritte
  laufen einmal neu, 7 s; die Ergebnisse bleiben byteidentisch, Test vorhanden). `period.name` im Fingerprint trennt die
  Stamps der Perioden; der Textstore je Periode verhindert gegenseitige Entwertung. Geteilt bleibt `cache/pdf`
  (Dateinamen sind IDs) und `http.sqlite`.
- **Namen der 2020-Bezirke** enthalten `/` und Leerzeichen („Himmelgeist/Holthausen/ Itter"); sie erscheinen nur in der
  Zuordnungstabelle, nie in Pfaden.
- **Vorlage.** Jede Zeile mit „2025" oder „2020 bis 2025" in `report.html.j2` ist in § 4 aufgelistet; ein Test prüft,
  dass die Seite des Profils kein „2025" außerhalb von Lizenz- und Zuschnittsätzen enthält (Allowlist der Sätze).
- **Golden Master.** Kein Schritt der Hauptperiode ändert Ergebnisse; die Umbenennung auf kanonische Spaltennamen ist
  ein No-op, der `slow`-Test bleibt das Maß. Wird er rot, war es keine Umstellung.
- **paperType und reference der alten Periode** folgen einer anderen Taxonomie (§ 3.3); für diesen Plan ohne Folge, für
  Option 5 und 6 ein Hinweis in `00-synergien.md`.
- **Schnappschuss-Größe.** 35 bis 40 MB im Repo neben den 62 MB der Arbeit; falls Konrad das nicht will, R2 (§ 8, Frage 1).

## 8. Offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | Warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 1 | Darf der Schnappschuss der alten Periode (35 bis 40 MB, natives Format) ins Repo, oder soll er in das R2-Bucket aus Option 7 und von Pages heruntergeladen werden? | Entscheidet, ob Pages die Seite weiter rein aus dem Repo baut und ob `bootstrap` einen Download lernt | ins Repo unter `snapshots/2014-2020/`, solange unter 50 MB; sonst R2 mit demselben Layout und einem Schritt `fetch snapshot` |
| 2 | Dasselbe Wörterbuch (Straßen und Orte je Wahlbezirk 2025, Stand November 2025) für beide Perioden, wie der Meta-Plan vorschlägt? | Die Alternative (Wörterbuch auf dem Zuschnitt 2020, Netz je 316 Polygone) macht Trefferquoten nicht additiv umrechenbar und kostet zwei Netzläufe | ja; die Seite nennt es als Grenze (Straßennamen von heute in Dokumenten von 2016) |
| 3 | Zeitgrenzen 2014-05-25 bis 2020-09-12 mit Wahltag 13.09.2020 als Beteiligungsdatum? | Verschiebt wenige Dokumente am Rand und die Zahl der Seiten | ja, disjunkt zur Hauptperiode, Wahltage als Grenzen wie in der Arbeit |
| 4 | Briefwahl proportional zu den Wahlberechtigten mit Sperrvermerk (A2) verteilen? | Bis 5,1 Prozentpunkte je Bezirk gegenüber proportional zu A | A2; die Alternative steht als Satz auf der Seite und ist eine Settings-Zeile (`eligible_postal`) |
| 5 | Freigabe des Abrufs der alten Periode (rund 3 h Metadaten, 8 bis 11 h PDFs, 3,7 bis 4,4 GB auf xtraspace) auf Konrads Rechner, Start durch Konrad? | Ohne ihn kein echter Vergleich; der Plan liefert bis dahin alles offline | Konrad startet nach Stufe G mit den Befehlen aus dem README; der Agent ruft nichts ab |
| 6 | Soll Pages beide Perioden bauen (plus rund eine Minute Laufzeit), sobald der Schnappschuss da ist? | Sonst bleibt die Unterseite lokal | ja, `pages.yml` wie in § 4 |
| 7 | Sollen die zehn weiteren Parteispalten 2020 (`D7` bis `D16`) in die Wählertabelle, für Option 4? | Ändert das Schema von `wahlbezirke_waehler.parquet` der alten Periode gegenüber der neuen | nein; dieselben sechs Parteien wie 2025, der Rest bleibt Option 4 über `columns.results.parties` |
| 8 | Reicht der eine Abschnitt auf der Hauptseite plus Unterseite, oder soll der Vergleich eine eigene Unterseite werden (Budget)? | 45 KB Zuwachs bleiben weit unter 1,5 MB; mit mehreren Optionen entscheidet die Synergiephase | Abschnitt auf der Hauptseite |

## 9. Vorbereitung für Option 10 (was wird konfigurierbar, welche Modulgrenze entsteht)

Konfigurierbar, nichts davon im Code fest: die Periode (`period.name`, `label`, `start`, `end`, `election`,
`dictionary`), die Startseite und der Modus des Metadatenabrufs (`sources.oparl.first_page`, `incremental`), die vier
Eingabedateien einer Periode mit ihren Spaltennamen (`sources.opendata.*_url`, `districts_file`, `columns.precinct_id`,
`columns.results.precinct`, `eligible_postal`, `postal_marker`, `parties`), die Umrechnung (`crosswalk.target`,
`min_coverage`) und der Vergleich (`compare.period`). Ein Profil ist eine TOML-Datei; eine andere Stadt (Option 1) oder
eine laufende Periode (Option 7) ist ein weiteres Profil mit denselben Schlüsseln.

Modulgrenzen, die entstehen: `georep.crosswalk` kennt nur Geometrien und Frames mit `source_id`, `target_id`, `share`
(keine Settings, kein Layout) und ist damit der Baustein für jede Umrechnung zwischen Gebietseinteilungen, auch Stadtteil
auf Wahlbezirk (Option 3, 5; dort kommen die Gewichte aus den Eigenschaften des GeoJSON statt aus Schnittflächen, die
Funktionen `target_weights` und `transfer_counts` sind dieselben). `georep.analysis.periods` rechnet auf zwei
Ergebnis-Frames und einer Spaltenkonvention, ohne zu wissen, woher sie stammen. `Layout.period` und `base()` sind die
Naht für mehrere Datenstände unter einer Wurzel; `Layout.for_period` ist die einzige Stelle, die die Verzeichnisstruktur
kennt. Die Berichtsseite bekommt mit `PeriodInfo` und dem optionalen `PeriodComparison` den ersten optionalen Abschnitt;
dasselbe Muster (Modellteil `None`, Abschnitt in der Vorlage mit `{% if %}`) taugt für die Abschnitte der anderen
Optionen. Docstrings der neuen Module verweisen auf `docs/architecture.md`, jede Entscheidung aus § 2 bekommt einen Punkt
in `decisions.md`, keine neue Abhängigkeit.

## 10. Änderungen durch die Synergiephase (füllt der Supervisor)
