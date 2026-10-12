# Plan 03: Kontrollvariablen

Stand 2026-10-12, Branch `feat/03-kontrollvariablen`. Status: gemerged am 2026-10-12 (Stufen A bis F umgesetzt am 2026-10-12).

Briefing: [../plan-ausbau-2026-10.md](../plan-ausbau-2026-10.md), § 7.3 mit Konrads Antworten vom 2026-10-11
(Quartiersatlas ausdrücklich erlaubt, andere Daten mit Lizenz und einem Abschnitt „Abgeleitete Daten" auf der
Seite, scikit-learn erlaubt, statsmodels eine Entscheidung dieses Plans). Regeln in [../../CLAUDE.md](../../CLAUDE.md)
und § 2 des Meta-Plans; Aufbau in [../architecture.md](../architecture.md), Gründe in [../decisions.md](../decisions.md).
Alle Quellen wurden am 2026-10-11 nachgesehen (Abrufdatum unten je Datei); heruntergeladen wurde in dieser Phase
nichts, nur Kopf- und Schlusszeilen über HTTP-Range-Anfragen, Größen über `HEAD`.

## 1. Ziel und Nicht-Ziel

Ziel: eine multiple lineare Regression der Wahlbeteiligung (in Prozent, wie Tabelle 5) auf die Trefferquote plus
Kontrollvariablen je Wahlbezirk, als Pipeline-Schritte mit Parquet-Ausgaben, und auf der Berichtsseite eine
„Tabelle 6" mit Koeffizienten, Standardfehlern, p-Werten, R² und adjustiertem R² je Modell, partiellen
Streudiagrammen (Added-Variable-Plots) für das Hauptmodell, einem Satz zur Deutung, der aus den Zahlen folgt, und
einem Abschnitt „Abgeleitete Daten" mit Quelle, Lizenz, Datenstand und Abrufdatum je Variable. Die
Kontrollvariablen kommen aus dem Quartiersatlas 2024 der Stadt (sozialer Handlungsbedarf, Fluktuation,
Altersstruktur) und aus den schon vorhandenen Parteianteilen; die Raumeinheiten der Stadt (Sozialräume,
Stadtteile) werden über die Stimmbezirke mit den Wahlberechtigten gewichtet auf die 41 Wahlbezirke umgerechnet.

Nicht Ziel: ein kausaler Anspruch (n = 41, die Trefferquote bleibt ein Maß der Sichtbarkeit); Modellsuche über
viele Spezifikationen (ein Hauptmodell, ein Parteimodell, eine Sensitivitätstabelle, fertig); die repräsentative
Wahlstatistik (Stichprobe, nur stadtweit veröffentlicht, § 3.6); Daten aus `statistik.duesseldorf.de` (ein
Single-Page-Portal ohne Export, die Daten liegen im Open-Data-Portal); neue Abhängigkeiten (statsmodels zieht
pandas, § 2); eine Unterseite (das Budget reicht, § 6).

## 2. Entscheidungen (mit verworfenen Alternativen und Kosten)

| Frage | Entscheidung | Warum, und was verworfen wurde |
|---|---|---|
| OLS-Bibliothek | numpy (`lstsq` auf der Designmatrix mit Konstante) und `scipy.stats.t` für die p-Werte, `scipy.stats.f` für den F-Test, VIF aus Hilfsregressionen; ein Modul `analysis/ols.py` von rund 120 Zeilen | Die Probe im Scratchpad (2026-10-11) reproduziert `linregress` auf der Referenz auf alle Stellen (Steigung 62,1337, Achsenabschnitt 49,1993, Standardfehler 60,894, p 0,31385). Verworfen: statsmodels (hängt von pandas ab, das `nox -s deps` verbietet; nur für zehn Zahlen eine 30-MB-Abhängigkeit); scikit-learn (erlaubt, aber `LinearRegression` liefert weder Standardfehler noch p-Werte, man rechnete sie doch von Hand). Einmalig wird das Modul von Hand in einer Wegwerf-Umgebung (`uv run --with statsmodels --isolated`, nie ins Lockfile) gegen statsmodels verglichen; die Zahlen stehen danach als Konstanten in `tests/golden/test_regression_numbers.py` |
| Quelle des Quartiersatlas | Open-Data-Portal, Datensatz „Quartiersatlas Düsseldorf 2024 - Sozialer Handlungsbedarf und Fluktuation" (CSV und GeoJSON, § 3.3), Lizenz Datenlizenz Deutschland Namensnennung 2.0 | Das Briefing vermutete PDF; die Daten liegen seit 2026-09-17 als CSV vor. Verworfen: PDF-Tabellen parsen (nicht nötig); das Statistikportal (JavaScript-Anwendung, kein Export gefunden, § 3.6) |
| Raumeinheit | Sozialräume (171, Zuschnitt 2021) direkt auf Wahlbezirke, über Flächenanteile je Stimmbezirk und Wahlberechtigte je Stimmbezirk; Stadtteile nur als Attribut-Crosswalk zur Validierung | Die Sozialräume sind feiner als die 50 Stadtteile (31 von 41 Wahlbezirken umfassen mehrere Stadtteile, der kleinste dominante Stadtteilanteil liegt bei 41 %, § 3.2); eine Aggregation Sozialraum → Stadtteil → Wahlbezirk verschenkte das. Verworfen: nur Stadtteile (gröber, dafür ohne Geometrie); Zuordnung über den Code-Präfix der Sozialräume (die Sozialraumnummer beginnt mit der Stadtteilnummer, `011001` = Altstadt, aber das ersetzt die Flächenanteile nicht) |
| Gewichtung | Gewicht eines Sozialraums im Wahlbezirk = Σ über die Stimmbezirke des Wahlbezirks von Wahlberechtigte(Stimmbezirk) × Flächenanteil(Sozialraum am Stimmbezirk), geteilt durch die Wahlberechtigten des Wahlbezirks; Vertrag: Gewichte je Wahlbezirk summieren zu 1 | Wahlberechtigte sind die Bezugsgröße der Trefferquote und der Wahlbeteiligung; reine Flächenanteile gewichteten Parks wie Wohngebiete. Verworfen: Bevölkerung je Baublock als Gewicht (genauer, aber ein weiterer Datensatz mit eigener Lizenz, und die Stimmbezirke sind schon fein genug: 306 Stück, 297 bis 2 331 Wahlberechtigte) |
| Altersstruktur | aus dem Quartiersatlas (sieben Altersgruppen als Anteile, Jugend- und Altenquotient), derselbe Stand und dieselbe Lizenz wie die anderen Kontrollvariablen | Eine Altersstruktur je Stadtteil gibt es im Portal nicht: das „Demografiemonitoring" ist stadtweit (945 Bytes, § 3.5), die Stadtteil-CSV führt nur Gesamtzahlen. Verworfen: „Mit Hauptwohnsitz gemeldete Bevölkerung 2020 nach Altersklassen - Sozialräume" (feinere Gruppen, aber Stand 2020 und ein zweiter Datensatz) |
| Modelle, sparsam bei n = 41 | A: Tabelle 5 (Trefferquote allein, über `ols` nachgerechnet); B, Hauptmodell: Trefferquote + Handlungsbedarf-Score + Anteil 65 Jahre und älter + Fluktuationsrate (k = 4, 36 Freiheitsgrade); C, Parteimodell: B + CDU-Anteil + AfD-Anteil (k = 6); Tabelle 6b: der Trefferquote-Koeffizient, wenn jede Kontrollvariable einzeln dazukommt (k = 2 je Zeile); alle mit VIF je Term | Die Probe mit allen sechs Parteianteilen ergab VIF bis 76 (die Anteile summieren zu 0,89 bis 0,96); CDU und AfD allein haben VIF 1,0 bis 1,2 und sind die beiden mit der geringsten Korrelation untereinander (r = −0,09). Verworfen: alle Parteien in einem Modell; schrittweise Modellwahl (bei n = 41 ein Zufallsgenerator); Standardisierte Koeffizienten kommen als zusätzliche Spalte, weil die Einheiten verschieden sind |
| Ordinale Variablen | `Sozialer_HB` und `HB_Fluktuation` bekommen eine Skala in den Settings (gering = 1, eher gering = 2, mittel = 3, erhöht = 4, hoch = 5), das gewichtete Mittel heißt Score | Der städtische Index ist das, was „sozialer Handlungsbedarf" im Briefing meint; eine Dummy-Kodierung kostete vier Freiheitsgrade. Als stetige Alternative steht `Mindestsicherungsquote` in Tabelle 6b. Die fünf Stufen stammen aus den gelesenen Zeilen (§ 3.3) und werden in Stufe A gegen die ganze Datei geprüft; eine unbekannte Stufe ist ein `SchemaError` |
| Anonymisierte Werte | „." (Werte unter 3) wird null; gewichtete Mittel lassen null aus und renormieren; liegt mehr als 10 % des Gewichts eines Wahlbezirks auf null, ist das ein `EmptyResultError` mit Variable und Wahlbezirk | Stilles Auffüllen mit 0 verfälschte Anteile; ein harter Abbruch schon bei einem kleinen Sozialraum wäre übertrieben. Die Schwelle steht in den Settings |
| Ablage der Fremddaten | ein neues Verzeichnis `context/` im Repo (CSV 48 KB, GeoJSON 2,2 MB, Erläuterung 13 KB, README mit Quelle, Lizenz, Datenstand, Abrufdatum, SHA-256), `context_root` in den Settings, `guard_writable` verweigert Schreiben darunter; `bootstrap` kopiert nach `data_root/external/`, ein Netzschritt `context_data` holt sie bei Bedarf frisch | Der Pages-Workflow baut ohne Netz aus dem Repo; `reference/` bleibt der eingefrorene Datensatz der Arbeit. Verworfen: unter `reference/external/` (vermischt Arbeit und Ausbau); Abruf im Workflow (Netz in CI, und das Portal benennt Dateien um, siehe STATUS.md); `tests/fixtures/` (keine Produktionsdaten). Kosten: 2,3 MB mehr im Repo (neben 82 MB Referenz) |
| Fetcher | `sources/opendata.py` bleibt die eine Quelle für das Portal: `fetch_results_csv` (prüft das Trennzeichen in der Kopfzeile) und `fetch_districts_geojson` (prüft die FeatureCollection) decken beide Formate; `fetch_results_csv` wird zu `fetch_csv` mit altem Namen als Alias | Abweichung vom Briefing (`sources/statistik.py`): es gibt keine zweite Quelle. Kosten: keine |
| Partielle Streudiagramme | Added-Variable-Plots nach Frisch-Waugh-Lovell: Residuum von y auf die übrigen Terme gegen Residuum des Terms auf die übrigen, je Term des Hauptmodells, mit Gerade (Steigung = Koeffizient), Punkte mit Wahlbezirksnummer; inline SVG aus denselben Achsen-Helfern wie das Streudiagramm | Zeigt den Beitrag jedes Terms bei festgehaltenen anderen; die Steigung der Geraden ist exakt der OLS-Koeffizient, das ist testbar. Verworfen: einfache Streudiagramme y gegen jede Variable (zeigen nicht die Kontrolle); matplotlib (Entscheidung der Berichtsseite) |
| Stichprobe ohne Ausreißer | alle Modelle werden für „alle" und „ohne 1 und 10" gerechnet und in Parquet geschrieben; die Seite zeigt Tabelle 6 für alle 41 und nennt für das Hauptmodell den Trefferquote-Koeffizienten ohne 1 und 10 in einem Satz | Konsistenz mit Tabelle 5; zwei volle Tabellen verdoppelten die Seite ohne neue Aussage |
| Integration | drei Pipeline-Schritte: `context_data` (Netz, wie `opendata`), `context` (Crosswalk und Variablen je Wahlbezirk), `controls` (Modelle); `report` bekommt die drei Parquet-Dateien als Eingaben; `georep regress --controls` druckt Tabelle 6 | Derselbe Mechanismus für Frische, `--force`, `--dry-run`; die Tabellen sind Ergebnisse wie die anderen und werden als Download veröffentlicht |

## 3. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

Alle Zahlen am 2026-10-11 nachgesehen: lokale Dateien mit Polars und `ls -l` im Worktree nach `georep run`,
Portaldateien mit `HEAD`, Range-Anfragen und der CKAN-API von open.nrw (die Düsseldorfer DKAN-API antwortet mit
einem Redirect ohne Inhalt).

### 3.1 Vorhanden im Worktree

- `data/processed/wahlbezirke_auswertung.parquet` (135 841 Bytes, 41 Zeilen, 20 Spalten): `wahlkreis_id` Int64,
  `suchbegriffe` List(String), `paper_ids` List(String), `anzahl_treffer` Int64, `Wahlberechtigte_insgesamt`,
  `Waehler`, `CDU_Stimmen`, `GRUENE_Stimmen`, `SPD_Stimmen`, `FDP_Stimmen`, `Die_Linke_Stimmen`, `AfD_Stimmen` Int64,
  `wahlbeteiligung`, `CDU_anteil`, `GRUENE_anteil`, `SPD_anteil`, `FDP_anteil`, `Die_Linke_anteil`, `AfD_anteil`,
  `trefferquote` Float64. Trefferquote 0,026 bis 0,163 (Median 0,061), Wahlbeteiligung 0,357 bis 0,670 (Median
  0,540). Die sechs Parteianteile summieren je Wahlbezirk zu 0,887 bis 0,955.
- `data/processed/wahlbezirke_waehler.parquet` (9 519 Bytes, 41 Zeilen, 16 Spalten): dieselben Wählerspalten.
- `data/external/Stimmbezirk_Wahlergebnis.csv` (65 982 Bytes, 467 Datenzeilen, latin-1, `;`, UTF-8-BOM in der
  ersten Spalte): `gebietnr` (vierstellig), `gebietname`, `Kommunalwahlbezirk` (`01` bis `41`), `Stadtbezirk`
  (`01` bis `10`), `Stadtteil` (dreistellig, `011` bis `102`, 49 verschiedene; `033` Hafen fehlt, siehe unten),
  `Wahlberechtigte_insgesamt`, `Waehler`, Parteistimmen. 306 Zeilen sind Urnenstimmbezirke (zusammen 469 732
  Wahlberechtigte, 297 bis 2 331 je Stimmbezirk, Mittel 1 535), 161 sind Briefwahlbezirke (`gebietname`
  „Briefwahlbezirk", Wahlberechtigte leer, also 0, aber 105 739 Wähler). Die Gewichte kommen daher nur aus den
  306 Urnenbezirken; ihre Wahlberechtigten-Summe je Wahlbezirk ist genau die Spalte `Wahlberechtigte_insgesamt`
  der Auswertung (geprüft: Wahlbezirk 1 = 11 637).
- `data/external/Stimmbezirke_2025.geojson` (7 927 291 Bytes, 306 Features, EPSG:4647): Eigenschaften
  `Stimm-/ Wahlbezirk` (String, Schlüssel zu `gebietnr`), `Kommunalwahlbezirk Nr.` (Int), `Kommunalwahlbezirk
  Name`, `Stadtteil Nr.` (Int, 50 Werte 11 bis 102), `Stadtteil Name`, `Stadtbezirk Nr.` (Int, 1 bis 10),
  `Bundestagswahlkreis Nr.`/`Name`, `Landtagswahlkreis Nr.`/`Name`, `BezirksZuordnungen — Zuordnung_Briefwahlbezirk`.
  Alle 306 Schlüssel finden sich in der CSV. CSV und GeoJSON stimmen in Wahlbezirk, Stadtbezirk und Stadtteil
  für 305 Stimmbezirke überein; die eine Abweichung ist Stimmbezirk `3301` (Friedenstraße 29, 297
  Wahlberechtigte): GeoJSON Stadtteil 33 (Hafen), CSV `032` (Unterbilk). Der Attribut-Crosswalk nimmt das
  GeoJSON, wie das Briefing es vorsieht, und ein Test hält die Abweichung fest.

### 3.2 Crosswalk Stadtteil zu Wahlbezirk (Probe, Scratchpad 2026-10-11)

Aus Urnenstimmbezirken, Gewicht = Wahlberechtigte: 84 Paare (Wahlbezirk, Stadtteil); 11 Wahlbezirke liegen in
einem Stadtteil, 21 in zwei, 5 in drei, 4 in vier; 23 Stadtteile verteilen sich auf mehrere Wahlbezirke
(Pempelfort auf 1, 2, 3, 4; Bilk auf 14, 15, 16, 18). Kleinstes Paar: 827 Wahlberechtigte (Wahlbezirk 5,
Derendorf). Kleinster dominanter Anteil: 0,41 (Wahlbezirk 28: Grafenberg, Ludenberg, Hubbelrath, Knittkuhl).
Die Gewichte summieren je Wahlbezirk auf 1,0 (maximale Abweichung 0,0). Wahlbezirk 40 ist der einzige mit zwei
Stadtbezirken (9 und 10). Mini-Fixture: Wahlbezirk 1 = Altstadt 0,150, Carlstadt 0,155, Stadtmitte 0,241,
Pempelfort 0,454; Wahlbezirk 10 = Flingern Süd 0,581, Flingern Nord 0,419; Wahlbezirk 38 = Benrath 0,155,
Hassels 0,845.

### 3.3 Quartiersatlas Düsseldorf 2024 (Open-Data-Portal)

Datensatzseite <https://opendata.duesseldorf.de/dataset/quartiersatlas-d%C3%BCsseldorf-2024-sozialer-handlungsbedarf-und-fluktuation>,
Herausgeber „Landeshauptstadt Düsseldorf – Amt für Statistik und Wahlen", Lizenz „Datenlizenz Deutschland
Namensnennung 2.0" (<https://www.govdata.de/dl-de/by-2-0>, schon in `ALLOWED_LINKS`), im Portal angelegt
2026-09-17, Metadaten geändert 2026-06-18 (so die Harvester-Felder), Stand der Daten 31.12.2021, Sozialräume im
Zuschnitt 2021 (171 laut Stadt; die Zeilenzahl wird in Stufe A geprüft). Hinweis des Portals: Werte unter 3
sind mit einem Punkt anonymisiert.

- `https://opendata.duesseldorf.de/sites/default/files/Daten_QA_2024.csv` (47 742 Bytes, Last-Modified
  2026-02-02, UTF-8, `;`, Dezimalkomma, Vorzeichen `+` bei positivem Wanderungssaldo). 54 Spalten: `SRG_2021_Nr`
  (sechsstellig, Präfix = Stadtteilnummer), `SRG_2021_Name`, `Bevoelkerung_abs`, `weiblich_Ant`, `u6_abs`, `u6_Ant`,
  `6_bis_u18_abs`, `6_bis_u18_Ant`, `18_bis_u30_abs`, `18_bis_u30_Ant`, `30_bis_u50_abs`, `30_bis_u50_Ant`,
  `50_bis_u65_abs`, `50_bis_u65_Ant`, `65_bis_u80_abs`, `65_bis_u80_Ant`, `ue80_abs`, `ue80_Ant`, `Jugendquotient`,
  `Altenquotient`, `Auslaender_Ant`, `Migrationshintergrund_Ant`, `Wanderungssaldo`, `Fluktuationsrate`,
  `Durchschn_Wohndauer_Monate`, `Haushalte_abs`, `EinpersonenHH_Ant`, `HH_mit_Kindern_Ant`, `AlleinerziehendenHH_Ant`,
  `Senioren-Single-Haushalte_Ant`, `Arbeitslose_abs`, `Arbeitslose_Ant`, `SGBII_abs`, `SGBII_Ant`, `SGBII_Kinder_Ant`,
  `SGBXII_Ant`, `Mindestsicherungsquote`, `Wohngeldbeziehende_HH_Ant`, `Schueler_Primarstufe_abs`,
  `Schueler_Sekundarstufe_abs`, `Schueler_Hauptschule_Ant`, `Schueler_Realschule_Ant`, `Schueler_Gymnasium_Ant`,
  `Schueler_Gesamtschule_Ant`, `Uebergangsquote_Gymnasium`, `Wohnflaechenstandard`, `Oeff_gefoerderte_Whg_Ant`,
  `Wohneigentumsquote`, `Flaeche_abs`, `Bevoelkerungsdichte`, `Wohnflaechen_Ant`, `Gruenflaechen_Ant`, `Sozialer_HB`,
  `HB_Fluktuation`. Erste Zeile `011001;Altstadt;2370;44,3;…;mittel;hoch`, letzte `102002;Hellerhof-Ost;…;mittel;gering`.
  Gesehene Stufen der beiden Ordinalspalten: gering, eher gering, mittel, erhöht, hoch.
- `https://opendata.duesseldorf.de/sites/default/files/Sozialr%C3%A4ume_QA_Daten_WGS84_EPSG_4326.geojson`
  (2 181 075 Bytes, Last-Modified 2026-02-02, CRS `urn:ogc:def:crs:OGC:1.3:CRS84`, also lon/lat): je Feature
  `STADTBEZIR` (Int), `SOZIALRAUM` (String, sechsstellig, Schlüssel zu `SRG_2021_Nr`) und alle CSV-Spalten als
  Strings mit Präfix `Daten_QA_2024_`. Genommen wird daraus nur die Geometrie und `SOZIALRAUM`.
- `https://opendata.duesseldorf.de/sites/default/files/Erl%C3%A4uterung_Indikatoren_QA_0.csv` (13 499 Bytes,
  Last-Modified 2026-02-17): `Indikator;Berechnung;Aussagekraft;Datenquelle`, eine Zeile je Indikator; liefert die
  Definitionen für die Seite (Fluktuationsrate = Zu-, Fortzüge und Binnenwanderung je 1 000 Einwohner;
  Altenquotient = 65 und älter je 100 Einwohner von 18 bis unter 65).
- Alternative Geometrie, nicht genommen: „Sozialraumgrenzen Düsseldorf 31.12.2021", `Sozialräume_ETRS89.geojson`
  (2 179 592 Bytes, EPSG:4647, Datenlizenz Deutschland Zero 2.0); Eigenschaftsnamen nicht gesehen, und die
  Quartiersatlas-Datei trägt den bestätigten Schlüssel.

Ablage im Repo nach Stufe A: `context/quartiersatlas_2024.csv`, `context/sozialraeume_2021.geojson`,
`context/quartiersatlas_2024_indikatoren.csv`, `context/README.md` (Quelle, Lizenz, Stand, Abrufdatum, SHA-256,
Umbenennung); umbenannt wie die Dateien der Arbeit (`Stimmbezirk_Wahlergebnis.csv` heißt im Portal anders), ohne
Umlaut im Namen.

### 3.4 Stadtteilgrenzen (nur für die Mini-Fixture und den Validierungstest)

„Stadtteilgrenzen Düsseldorf 2025", `https://opendata.duesseldorf.de/sites/default/files/Stadtteilgrenzen_2025_ETRS89_EPSG4647.geojson`
(1 616 652 Bytes, Last-Modified 2025-03-26, EPSG:4647, Datenlizenz Deutschland Zero 2.0): je Feature `Name`,
`Nummer` (dreistellig, `044`). Kommt nicht nach `context/`; `make_mini.py` schneidet die acht Stadtteile der drei
Mini-Wahlbezirke aus (11, 12, 13, 14, 21, 22, 95, 98) nach `tests/fixtures/mini/context/stadtteile_2025.geojson`,
damit ein Test den geometrischen Crosswalk gegen den Attribut-Crosswalk prüfen kann (Stufe B).

### 3.5 Geprüft und nicht genommen

- „Bevölkerung mit Hauptwohnsitz nach Altersgruppen, Geschlecht und Staatsangehörigkeit - Demografiemonitoring"
  (`Bevölkerung nach Altersgruppen mit Hauptwohnsitz seit 2013_1.csv`, 945 Bytes, Jahre 2013 bis 2020): stadtweit,
  keine Raumeinheit.
- „Bevölkerung in Düsseldorf seit 2012", `Bevölkerungsstand in den Stadtteilen seit 2012_2.csv` (4 649 Bytes,
  Last-Modified 2026-08-31, Datenlizenz Deutschland Zero 2.0): `Stadtteilnummer;Stadtteilname;Jahr_2012;…;Jahr_2025`,
  nur Gesamtzahlen. Bleibt als Option für eine Einwohnerzahl je Wahlbezirk (Stand 2025), falls je gebraucht.
- „Mit Hauptwohnsitz gemeldete Bevölkerung in Düsseldorf 2020 nach Altersklassen - Sozialräume" (33 100 Bytes,
  Datenlizenz Deutschland Zero 2.0, Spalten `Stadtbezirk;Sozialraum;Jugendquotient;Altenquotient;Personen
  insgesamt;Davon unter 3 Jahre;…`): älterer Stand, feinere Gruppen; Reserve, falls der Quartiersatlas nicht reicht.
- „Stadtteilprofile" (`011 Altstadt_0.csv` usw.) und „Prognose … bis 2035": Prognosewerte 2019 und 2035, kein
  Datenstand zur Wahl; die Prognose führt „032 Unterbilk / 033 Hafen" zusammen.
- Die 2016er Sozialraum-Datensätze (Alter, Arbeitslose, SGB II, Haushalte, Wanderung) tragen „Andere geschlossene
  Lizenz" und den alten Zuschnitt 2017; nicht verwendbar.

### 3.6 Repräsentative Wahlstatistik und Statistikportal

Die Stadt veröffentlicht die „Analyse der repräsentativen Wahlstatistik zur Wahl des Rates am 14. September 2025"
(<https://www.duesseldorf.de/statistik-und-wahlen/statistik-und-stadtforschung/analysen/kommunalwahl-2025-analyse-der-ergebnisse-1-1>)
nur als interaktives Online-Format mit Verweis auf `statistik.duesseldorf.de`; im Open-Data-Portal gibt es keinen
Datensatz dazu (CKAN-Suche „repräsentative Wahlstatistik" am 2026-10-11 ohne Treffer). Eine repräsentative
Wahlstatistik ist eine Stichprobe ausgewählter Stimmbezirke und wird nur aggregiert veröffentlicht; je Wahlbezirk
gibt es sie nicht. `statistik.duesseldorf.de` liefert eine 1,4 KB große JavaScript-Hülle (Quartiersatlas unter
`#app/mainpage////02DC901A-…`), kein Export, keine API gefunden. Beides bleibt draußen; die Seite erwähnt die
repräsentative Wahlstatistik nicht.

## 4. Berührungspunkte im bestehenden Code (Datei, Funktion, was sich ändert)

| Datei | Funktion oder Stelle | Änderung |
|---|---|---|
| `src/georep/defaults.toml` | neu `[context]` | `root = "./context"`, Trennzeichen und Fehlwert der CSV, `[[context.sources]]` je Datei (Name, URL, Dateiname, Datensatzseite, Lizenz, Lizenz-URL, Namensnennung, Stand), `[context.units]` (GeoJSON-Datei, Schlüsseleigenschaft `SOZIALRAUM`, CSV-Schlüssel `SRG_2021_Nr`), `[context.scales.Sozialer_HB]` und `…HB_Fluktuation`, `[[context.variables]]` (Name, Label, Einheit, Quelle, Spalte oder Spalten, Art: `share`, `sum_share`, `value`, `ordinal`, `party`; Skalierung), `[context.models]` (`main`, `parties`, `single`), `max_missing_weight = 0.1`, `min_coverage = 0.9`, `y_scale = 100`; jede Zahl mit Kommentar |
| `src/georep/settings.py` | neue Modelle `ContextSource`, `ContextUnits`, `ContextVariable`, `ContextModels`, `ContextSettings`; `Settings.context`; `fingerprint()` | `context.root` ist ein Pfad und wird wie die anderen Pfade ausgeschlossen (`exclude={"context": {"root"}}`), alles andere zählt zum Fingerprint; Validator: jede Modellvariable existiert in `variables` oder ist `trefferquote` oder ein Parteianteil, Skalen kennen keine Dubletten |
| `src/georep/layout.py` | `Layout` (neues Feld `context_root: Path`), `from_settings`, `guard_writable`, neue Pfade | `guard_writable` verweigert auch Pfade unter `context_root`; Eingaben `quartiersatlas_csv` (`external/quartiersatlas_2024.csv`), `units_geojson` (`external/sozialraeume_2021.geojson`), `indicators_csv`; Ergebnisse `crosswalk` (`processed/wahlbezirke_crosswalk.parquet`), `context_table` (`processed/wahlbezirke_kontext.parquet`), `controls` (`processed/regression_kontrollen.parquet`); `context_view()` analog `reference_view()` |
| `src/georep/bootstrap.py` | `bootstrap`, `BootstrapReport.summary` | drei weitere Paare aus `context_root` nach `external/`; der Bericht nennt „in Referenz oder Kontext nicht gefunden"; fehlende Kontextdateien sind `missing`, kein Abbruch |
| `src/georep/sources/opendata.py` | `fetch_results_csv` → `fetch_csv` (Alias bleibt) | keine Verhaltensänderung; der Netzschritt ruft `fetch_csv` und `fetch_districts_geojson` für die Kontextdateien |
| `src/georep/sources/__init__.py` | `cached_session` | Cache-Regel `opendata_s` auch für jede `context.sources[].url` |
| `src/georep/crosswalk.py` (neu) | `attribute_weights(precinct_table, unit_column)`, `area_shares(precincts, units)`, `district_weights(precinct_table, shares)` | Modul für die Umrechnung beliebiger Flächeneinheiten auf Wahlbezirke über Stimmbezirke und ein Gewicht je Stimmbezirk (§ 9) |
| `src/georep/prep/context.py` (neu) | `read_quartiersatlas_csv`, `read_units_geojson`, `precinct_table(precincts, results_csv)`, `ordinal_scores`, `aggregate_context(weights, units, variables)` | Polars-Funktionen Frame zu Frame mit Verträgen; nichts Düsseldorf-Spezifisches im Code |
| `src/georep/analysis/ols.py` (neu) | `fit_ols(frame, y, terms, *, y_scale)`, `OlsResult`, `vif`, `partial_residuals`, `models_table` | numpy und scipy; `regress` bleibt unverändert, ein Test zeigt die Gleichheit |
| `src/georep/analysis/regression.py` | unverändert | Golden Master (Tabelle 5) bleibt die Referenz |
| `src/georep/pipeline.py` | `build_steps` | Schritte `context_data` (Netz, nach `opendata`), `context` (nach `voters`), `controls` (nach `results`); `report` liest zusätzlich `crosswalk`, `context_table`, `controls`; die Zählung in `architecture.md` wird 17 Schritte |
| `src/georep/cli.py` | `_cmd_regress`, `build_parser` | `georep regress --controls` druckt Tabelle 6 aus `processed/regression_kontrollen.parquet`; `fetch` nimmt `context_data` automatisch mit (es ist ein Netzschritt) |
| `src/georep/export.py` | `csv_plan` | drei Zeilen für die neuen Tabellen (keine Listen, Trenner `,`) |
| `src/georep/report/model.py` | `published_tables`, `COLUMN_DOCS`, `ReportModel`, `build_report_model`, neue dataclasses `ControlTerm`, `ControlModel`, `SingleAddition`, `DerivedVariable`, `ControlsSection` | drei Tabellen mehr in Downloads und Schema; `ReportModel.controls` (Modelle A, B, C, Tabelle 6b, Satz zur Deutung als Daten) und `ReportModel.derived` (je Variable Quelle, Lizenz, Stand, Abrufdatum aus dem Stamp von `context_data` oder aus `context/README.md`-Werten in den Settings) |
| `src/georep/report/charts.py` | `scatter` (Refactoring: Achsen, Gitter, Ticks in `_axes(...)` ausgelagert), neu `added_variable_plot(points, slope, labels)` | ein Refactoring-Commit, dessen Ausgabe für die Mini-Fixture byteidentisch bleibt (im Scratchpad verglichen), dann die neue Funktion |
| `src/georep/report/render.py` | `ALLOWED_LINKS`, `render_report`, `Visuals` | Datensatzseite des Quartiersatlas und die Portal-URL der Erläuterung in die Allowlist; `Visuals.partial_svgs: Sequence[tuple[str, str]]` |
| `src/georep/report/templates/report.html.j2` | neue Abschnitte `#kontrollvariablen` (nach `#zusammenhang`) und `#abgeleitete-daten` (vor `#downloads`); Fuß | Tabelle 6, Tabelle 6b, Added-Variable-Plots, Satz zur Deutung; Tabelle Variable, Quelle, Lizenz, Stand, Abrufdatum, Definition; im Fuß ein Satz zum Quartiersatlas mit Namensnennung |
| `src/georep/report/build.py` | `DESCRIPTIONS`, `build_site` | Beschreibungen der drei Tabellen; die Plots in `Visuals` |
| `tests/fixtures/make_mini.py`, `tests/fixtures/mini/context/`, `tests/fixtures/mini/README.md` | `write_inputs` | Kontext-Fixture: Quartiersatlas-Zeilen und Sozialraum-Features, die die 22 Stimmbezirke schneiden (rund 15 bis 20), die acht Stadtteile (§ 3.4), README mit Herkunft; `expected/` bleibt unangetastet (Test: `git status` zeigt dort nichts) |
| `tests/conftest.py` | `mini_run`, neue Fixture `mini_context` | `Layout(root/"data", root/"cache", MINI, MINI/"context")` |
| `tests/unit/test_cli.py`, `tests/unit/__snapshots__/test_cli.ambr` | Zählungen, Snapshot `georep steps` | „9 geplant" → „11 geplant", „5 übersprungen" → „6", „9 ausgeführt" → „11"; Snapshot bewusst mit Diff erneuert |
| `tests/golden/test_pipeline.py` | `offline`, `third`, slow-Test | 9 → 11 Offline-Schritte; `third` erwartet `context` und `controls` als „übersprungen" bzw. „ausgeführt" (die Änderung an `pois` zieht `results`, `controls`, `report` nach, nicht `context`); `site_data` 15 → 21 Dateien |
| `tests/unit/test_report_build.py`, `test_bootstrap.py`, `test_layout.py`, `test_settings.py` | Dateizahlen, Kopierliste, Guard, Fingerprint | 15 → 21; „4 Dateien kopiert" → „7"; Guard gegen `context_root`; Fingerprint ignoriert `context.root`, sieht `context.models` |
| `tests/golden/test_regression_numbers.py` | neu Tabelle 6 | Konstanten aus dem einmaligen statsmodels-Vergleich (Stufe D) |
| `noxfile.py` | `VERIFY_TARGETS` | `georep.prep.context.ordinal_score` (rein) dazu; `mutate` deckt `analysis/ols.py` automatisch ab |
| `docs/architecture.md`, `docs/decisions.md`, `README.md`, `CHANGELOG.md`, `STATUS.md` | Module, Pipeline (17 Schritte), Datenhaltung (`context/`), Berichtsseite; ein Punkt je Entscheidung aus § 2; README „Daten und Herkunft" plus zwei Zeilen, Befehle plus `regress --controls`; Unreleased | im selben Branch |

## 5. Bauplan in Stufen

Jede Stufe ein bis drei Commits, nach jedem `uv run nox` (im Alltag `uv run pytest -n 2 …`), Verhaltensänderung
zuerst mit rotem Test, Tests in `tmp_path` mit `Layout(tmp/data, tmp/cache, mini_root, mini_root/"context")`.
Aufwand in Agentenstunden, geschätzt am 2026-10-11; zusammen rund 22 h.

### Stufe A: Kontextdaten, Settings, Layout, Bootstrap, Netzschritt (3 h)

1. Einmaliger Abruf der drei Dateien aus § 3.3 nach `context/` (2,3 MB, unter einer Minute; erlaubt nach § 2 des
   Meta-Plans), `context/README.md` mit Quelle, Lizenz, Stand, Abrufdatum, SHA-256 und der Umbenennung. Dabei
   prüfen: Zeilenzahl der CSV (erwartet 171), die Stufen von `Sozialer_HB` und `HB_Fluktuation`, ob jede
   `SRG_2021_Nr` genau ein Feature im GeoJSON hat, und ob das GeoJSON mit `CRS84` über `pyproj` sauber nach
   EPSG:25832 kommt (`CRS.from_user_input("urn:ogc:def:crs:OGC:1.3:CRS84")`, `always_xy`).
2. `settings.py` und `defaults.toml` (§ 4); Tests: Defaults laden, unbekannter Schlüssel in `[context]` ist ein
   Fehler, Modell mit unbekannter Variable ist ein Fehler, Fingerprint ignoriert `context.root`.
3. `layout.py`: `context_root`, Pfade, Guard; `bootstrap.py`: Kopien; `pipeline.py`: Schritt `context_data` mit
   `fetch_csv` und `fetch_districts_geojson` über die Fake-Session (Test mit aufgezeichneten Kopfzeilen, nicht den
   ganzen Dateien).
4. Mini-Fixture: `make_mini.py` schreibt `tests/fixtures/mini/context/` (§ 4), README ergänzt.
5. Abnahme: `uv run nox` grün; `georep bootstrap` im Worktree meldet „7 Dateien kopiert … 0 nicht gefunden" und auf
   der Mini-Fixture ebenso; `georep steps` zeigt `context_data` mit drei Ausgaben unter `external/`;
   `git status` unter `tests/fixtures/mini/expected/` leer; `context/` liegt im Repo mit README und Prüfsummen.

### Stufe B: Crosswalk `georep.crosswalk` (4 h)

1. `precinct_table(precincts, results_csv, columns)` in `prep/context.py`: eine Zeile je Urnenstimmbezirk mit
   `stimmbezirk_id`, `wahlkreis_id`, `stadtteil_nr`, `stadtbezirk_nr` (aus dem GeoJSON) und `wahlberechtigte`
   (aus der CSV, Briefwahlbezirke fallen weg, weil sie keine Fläche haben). Vertrag: Wahlberechtigte positiv,
   eine Zeile je Stimmbezirk, Summe je Wahlbezirk gleich `Wahlberechtigte_insgesamt` der Wählertabelle (Test
   gegen `wahlbezirke_waehler.parquet`).
2. `attribute_weights(table, unit_column)` → Frame `wahlkreis_id`, `einheit`, `gewicht`: Summe der Wahlberechtigten
   je (Wahlbezirk, Einheit) geteilt durch die Summe je Wahlbezirk. Verträge: `deal.post` Gewichte in (0, 1],
   sortiert und eindeutig nach (Wahlbezirk, Einheit), Summe je Wahlbezirk gleich 1 bis auf 1e-9; `deal.ensure`
   Wahlbezirke gleich denen der Eingabe. hypothesis in `tests/property/test_crosswalk_props.py`: beliebige
   Tabellen mit positiven Gewichten erfüllen die Nachbedingungen; Skalieren aller Wahlberechtigten mit einer
   Konstante ändert kein Gewicht; ein Wahlbezirk mit einer Einheit bekommt 1,0.
3. `area_shares(precincts, units, *, min_coverage)` → Frame `stimmbezirk_id`, `einheit`, `anteil`: Schnittfläche
   mit shapely (STRtree über die Einheiten, `intersection(...).area`), normiert auf die bedeckte Fläche des
   Stimmbezirks; liegt die bedeckte Fläche unter `min_coverage` der Stimmbezirksfläche, `SchemaError` mit
   Stimmbezirk und Anteil. `district_weights(table, shares)` kombiniert beides zu Gewichten je (Wahlbezirk,
   Einheit) mit denselben Verträgen wie 2. hypothesis: synthetische Rechtecke (Einheiten als Gitterzellen,
   Stimmbezirke als Kästen) liefern die bekannten Flächenanteile; Summen 1,0.
4. Validierung: auf der Mini-Fixture liefert `district_weights` mit den acht Stadtteilgrenzen dieselben Gewichte
   wie `attribute_weights` über `Stadtteil Nr.` bis auf 0,02 (Grenzverläufe der beiden Portaldateien sind nicht
   identisch); auf der Referenz (Scratchpad, dokumentiert in `decisions.md`) ebenso, bis auf den Stimmbezirk 3301.
5. Abnahme: `nox` grün; der Crosswalk Sozialräume auf der Referenz hat 41 Wahlbezirke mit Gewichtssumme 1,0, keine
   Bedeckung unter 0,9 (sonst die Schwelle begründet senken und in `decisions.md` notieren); Laufzeit unter 2 s
   (306 × 171 Schnitte mit STRtree-Vorauswahl).

### Stufe C: Variablen je Wahlbezirk, Schritt `context` (3 h)

1. `read_quartiersatlas_csv(path, settings)`: Polars, `;`, alles als Text lesen, Dezimalkomma und `+` behandeln,
   `.` zu null, Schlüssel als String; `SchemaError`, wenn eine in den Settings genannte Spalte fehlt oder eine
   Ordinalstufe nicht in der Skala steht. Test mit einer kleinen handgeschriebenen CSV (inklusive `.`, `+30,5`,
   unbekannte Stufe).
2. `ordinal_score(value, scale)` rein, mit Vertrag (Ergebnis in der Skala) und `deal.cases`; in `VERIFY_TARGETS`.
3. `aggregate_context(weights, units_table, variables, *, max_missing_weight)` → eine Zeile je Wahlbezirk:
   `wahlkreis_id`, je Variable eine Float64-Spalte, je Variable `<name>_fehlgewicht` (Anteil des Gewichts auf
   null); Verträge: eine Zeile je Wahlbezirk des Crosswalks, Anteile in [0, 100], Scores in [1, 5],
   `fehlgewicht` ≤ `max_missing_weight` (sonst `EmptyResultError`). hypothesis: gewichtetes Mittel liegt zwischen
   Minimum und Maximum der Einheiten; konstante Einheiten ergeben die Konstante; null-Einheiten unter der Schwelle
   ändern das Ergebnis nur durch Renormierung.
4. Schritt `context`: Eingaben `Stimmbezirke_2025.geojson`, `Stimmbezirk_Wahlergebnis.csv`,
   `quartiersatlas_2024.csv`, `sozialraeume_2021.geojson`, `wahlbezirke_waehler.parquet`; Ausgaben
   `wahlbezirke_kontext.parquet` (zuerst, Stamp) und `wahlbezirke_crosswalk.parquet` (`wahlkreis_id`, `einheit`,
   `einheit_name`, `gewicht`); Parteianteile werden aus der Wählertabelle mit `scale = 100` übernommen, damit alle
   Variablen in Tabelle 6 lesbare Einheiten haben. Rückgabe: „41 Wahlbezirke, 171 Sozialräume, 9 Variablen".
5. Abnahme: `nox` grün; auf der Referenz liegt `anteil_65plus` zwischen 10 und 30 %, `hb_score` zwischen 1 und 5,
   kein `fehlgewicht` über 0,1 (sonst Schwelle begründen); zwei Läufe schreiben byteidentische Parquet-Dateien
   (Test wie `test_two_runs_write_identical_parquet`); `georep status` zeigt `context` aktuell.

### Stufe D: OLS `georep.analysis.ols`, Schritt `controls` (4 h)

1. `fit_ols(frame, y, terms, *, y_scale)` → `OlsResult(n, k, terms, coef, se, t, p, beta_std, vif, r2, r2_adj,
   f, f_p, residuals, fitted)`: Designmatrix mit Konstante, `numpy.linalg.lstsq`, Kovarianz σ² (XᵀX)⁻¹,
   p zweiseitig über `scipy.stats.t.sf`, VIF je Term aus Hilfsregressionen, standardisierte Koeffizienten
   b · sd(x)/sd(y). Verträge: `deal.pre` `n ≥ k + 2`, Terme vorhanden und verschieden, `y_scale > 0`; `deal.post`
   p in [0, 1], R² in [0, 1], adjustiertes R² ≤ R², VIF ≥ 1, Standardfehler ≥ 0; `deal.raises(EmptyResultError)`
   bei singulärer Matrix (Konditionszahl über 1e12) oder ohne Streuung in y.
2. Tests: bivariat gleich `regress` auf der Mini-Fixture und der Referenz (Steigung, Achsenabschnitt,
   Standardfehler, p, R² bis 1e-9 relativ); hypothesis in `tests/property/test_ols_props.py`: Zufallsdaten,
   bivariat gleich `linregress`; R² wächst nie, wenn ein Term dazukommt; p in [0, 1]; standardisierter Koeffizient
   im bivariaten Fall gleich r; die Steigung des Added-Variable-Plots gleich dem Koeffizienten (Frisch-Waugh-Lovell).
3. Einmaliger Vergleich mit statsmodels in einer Wegwerf-Umgebung (`uv run --isolated --with statsmodels python
   …`, nie `uv add`): Koeffizienten, Standardfehler, p, R², adjustiertes R², F-p für die Modelle A, B, C auf der
   Referenz bis 1e-8; die Zahlen kommen als Konstanten in `tests/golden/test_regression_numbers.py`, der Lauf steht
   datiert in `decisions.md`.
4. `partial_residuals(frame, y, terms, term)` für die Plots; `models_table(settings, context_table)` baut die
   lange Tabelle `regression_kontrollen.parquet`: `modell` (A, B, C, `single:<variable>`), `stichprobe` (`alle`,
   `ohne_1_10`), `term`, `koeffizient`, `standardfehler`, `t`, `p`, `beta_std`, `vif`, `n`, `k`, `r2`, `r2_adj`,
   `f_p`; Modelle, für die `n < k + 2` gilt (Mini-Fixture: alles außer A), fehlen in der Tabelle, und `controls`
   meldet „2 von 15 Modellen geschätzt (n = 3)".
5. Schritt `controls`: Eingaben `wahlbezirke_auswertung.parquet`, `wahlbezirke_kontext.parquet`; Ausgabe
   `regression_kontrollen.parquet`; `georep regress --controls` druckt Tabelle 6 wie `summary()`.
6. Abnahme: `nox`, `pytest -m slow` grün; Modell A in der Tabelle gleich Tabelle 5 auf alle Stellen; VIF aller
   Terme in B und C unter 5 (sonst das Parteimodell in § 8 Frage 1 neu entscheiden); `nox -s mutate` einmal über
   `analysis/` mit Quote nicht unter 75 % (Stand 79 %).

### Stufe E: Berichtsseite (6 h)

1. `report/model.py`: dataclasses und `ReportModel.controls`, `ReportModel.derived`; `published_tables` und
   `COLUMN_DOCS` für `wahlbezirke_kontext`, `wahlbezirke_crosswalk`, `regression_kontrollen` (der Test
   `column_docs_cover_every_published_column` erzwingt die Vollständigkeit); Datenstand und Abrufdatum je Variable
   aus `settings.context.sources[].stand` und dem Stamp von `context_data` (ohne Stamp: das Abrufdatum aus
   `context/README.md`, das in den Settings als `fetched` steht); der Satz zur Deutung entsteht aus Schwellen
   (p < 0,05, Vorzeichen, R²-Zuwachs gegenüber A), nie fest kodiert.
2. `report/charts.py`: Refactoring (Achsen-Helfer aus `scatter` herausziehen; Ausgabe der Mini-Fixture vorher und
   nachher im Scratchpad per `diff` identisch; ein Commit), dann `added_variable_plot` (ein SVG je Term des
   Hauptmodells, rund 10 KB, Punkte mit Nummer und `<title>`, Gerade durch den Ursprung mit der Steigung des
   Koeffizienten, Achsenbeschriftung „… bei festgehaltenen übrigen Variablen"). Vor dem ersten Plot die Skill
   `dataviz` laden, falls vorhanden.
3. Vorlage: Abschnitt „Kontrollvariablen" mit Tabelle 6 (Zeilen: Terme mit Koeffizient, Standardfehler, p,
   standardisiert, VIF; Fuß: n, R², adjustiertes R², F-p; Spalten: Modelle A, B, C), Tabelle 6b (Variable,
   Trefferquote-Koeffizient, Standardfehler, p, R²), die Plots, der Satz zur Deutung, ein Hinweis auf n = 41 und
   den Stand 31.12.2021; Abschnitt „Abgeleitete Daten" (Variable, Definition aus der Erläuterungs-CSV, Quelle mit
   Link auf die Datensatzseite, Lizenz, Datenstand, Abrufdatum, Umrechnung „Sozialräume → Wahlbezirke, gewichtet
   mit Wahlberechtigten je Stimmbezirk und Flächenanteil"); Fuß: Satz zur Namensnennung. Tabellen mit `<th scope>`,
   Zahlen über `num`, Escaping durch Autoescape.
4. Downloads: die drei Tabellen als Parquet und CSV (über `published_tables`), Beschreibungen, Schema.
5. Tests: Rendering parst, enthält „Tabelle 6", jede Variable des Hauptmodells kommt im Abschnitt vor, nur erlaubte
   Links; Added-Variable-Plot hat so viele Punkte wie Zeilen und parst als XML; Mini-Fixture (n = 3) zeigt Modell A
   und den Hinweis „nicht geschätzt"; Snapshot nur für die Download-Tabelle (bestehend, bewusst mit Diff erneuert).
   Seite mit headless Chrome in Hell und Dunkel ansehen (§ 8.4 des Meta-Plans), Tabelle 6 und die Plots auf
   Lesbarkeit prüfen.
6. Abnahme: `nox`, `pytest -m slow` grün; `index.html` auf der Referenz unter 800 KB (§ 6); 21 Dateien unter
   `site/data/`; die SHA-256 der neuen Dateien stehen auf der Seite; Hell und Dunkel ohne unlesbare Stellen.

### Stufe F: Dokumentation, Steps-Snapshot, Abschluss (2 h)

1. `georep steps`-Snapshot erneuern (Diff lesen: drei neue Schritte, `report` mit drei weiteren Eingaben);
   CLI-Zählungen; `architecture.md` (Modultabelle `crosswalk`, `prep/context`, `analysis/ols`; Pipeline 17
   Schritte; Datenhaltung `context/`; Berichtsseite), `decisions.md` (OLS ohne statsmodels; Sozialräume und
   Crosswalk; `context/`; Modellwahl mit VIF-Probe), README (Herkunftstabelle plus Quartiersatlas, Befehl
   `regress --controls`, Lizenzzeile), `CHANGELOG.md` unter „Unreleased", `STATUS.md` (Zahlen: Tests, Laufzeit,
   Schritte).
2. `uv run nox -s bench` (die neuen Schritte sind nicht in den Benchmarks; der Index darf nicht langsamer werden).
3. Abnahme: aus dem Worktree `uv run georep bootstrap && uv run georep run` endet mit 11 ausgeführten
   Offline-Schritten; `uv run georep run` ein zweites Mal überspringt alles mit „aktuell"; `uv run nox`,
   `uv run pytest -m slow`, `uv run nox -s bench` grün; `grep -rn "Düsseldorf\|0015\|Sozialraum" src/` trifft nur
   `defaults.toml` und Docstrings mit Verweis auf die Settings; Abschlussbericht an den Supervisor nach § 5 Phase 3
   des Meta-Plans, mit den Laufzeiten.

## 6. Auswirkung auf die Berichtsseite

- Neuer Abschnitt „Kontrollvariablen" nach „Trefferquote und Wahlbeteiligung": Tabelle 6 (drei Modelle, rund
  6 KB HTML), Tabelle 6b (zwölf Zeilen, rund 3 KB), vier Added-Variable-Plots (je rund 10 bis 12 KB SVG, wie das
  Streudiagramm mit 41 beschrifteten Punkten), ein Absatz Deutung und Grenzen.
- Neuer Abschnitt „Abgeleitete Daten" vor „Downloads": eine Tabelle mit rund neun Zeilen (Variable, Definition,
  Quelle, Lizenz, Datenstand, Abrufdatum, Umrechnung), rund 4 KB.
- Downloads: drei Parquet- und drei CSV-Dateien mehr (`wahlbezirke_kontext` 41 Zeilen, `wahlbezirke_crosswalk`
  rund 250 Zeilen, `regression_kontrollen` rund 90 Zeilen; zusammen unter 60 KB), sechs Zeilen mehr in der
  Download-Tabelle, drei Blöcke mehr im Spaltenschema.
- Größe: `index.html` heute 686 088 Bytes auf der Referenz (README nennt noch 400 KB); erwartet rund 750 KB,
  Budget 1,5 MB. Keine Unterseite. `karte.html` unverändert.
- Berührung mit anderen Optionen: die Karte bekommt keinen weiteren Umschalter (Option 5 plant einen); der
  Abschnitt steht zwischen „Zusammenhang" und „Je Wahlbezirk", wo Option 6 ihre Sensitivitätstabelle plant; die
  Synergiephase legt die Reihenfolge fest (§ 10).

## 7. Risiken und Fallstricke

- Datenstand: der Quartiersatlas trägt den 31.12.2021, die Wahl ist vom 14.09.2025; Sozialräume mit viel Neubau
  (Derendorf, Hafen, Unterbilk) sind 2025 anders als 2021. Die Seite sagt das; eine Aktualisierung des Atlas
  kommt als neue Datei mit neuem Stand in die Settings.
- Sozialräume gegen Stimmbezirke: beide Portaldateien stammen aus verschiedenen Jahren und Werkzeugen; Grenzen
  weichen um Meter ab, und Stimmbezirke am Rhein oder im Hafen können Flächen ohne Sozialraum enthalten
  (`min_coverage`). Die Probe gegen den Attribut-Crosswalk der Stadtteile (Stufe B.4) zeigt, wie groß das ist.
- `CRS84` im GeoJSON: lon/lat in Achsenreihenfolge; `read_precincts` nimmt heute `geojson_crs` wörtlich, pyproj
  kennt `urn:ogc:def:crs:OGC:1.3:CRS84`; ein Test mit einem bekannten Punkt (Rathaus) sichert die Richtung.
- Multikollinearität: Parteianteile summieren fast zu 1; mehr als zwei im Modell sind unbrauchbar (VIF 76). Die
  VIF-Spalte steht in jeder Tabelle; ein Test schlägt an, wenn ein Modell in den Settings VIF über 10 erreicht.
- n = 41 und k = 6 im Parteimodell: 34 Freiheitsgrade; keine weiteren Terme ohne Beschluss in § 8.
- Anonymisierte Werte (`.`) fallen in kleinen Sozialräumen besonders bei `Arbeitslose_abs`, `SGBII_abs` an; die
  Anteilsspalten sind seltener betroffen; der Plan nutzt Anteile und die Fehlgewicht-Spalte zeigt den Rest.
- Die Mini-Fixture hat n = 3: alle Modelle außer A fehlen; Vorlage, Modell und Tests müssen das ohne Sonderfall
  im Code tragen (eine leere Liste von Modellen, ein Hinweis).
- Stamps: `report` bekommt drei neue Eingaben und jede Settings-Änderung unter `[context]` ändert den Fingerprint
  aller Schritte; das ist richtig, kostet aber auf der Referenz einen Lauf von 7 s plus die neuen Schritte (Ziel:
  `context` unter 3 s, `controls` unter 1 s).
- Konflikte in der Synergiephase: `pipeline.build_steps`, `report.html.j2`, `model.COLUMN_DOCS`,
  `published_tables`, der `steps`-Snapshot und die CLI-Zählungen ändern sich in fast jeder Option; ein Register
  der Abschnitte und veröffentlichten Tabellen als Fundament nähme die Konflikte heraus (§ 9).
- `deal`: keine Verträge in der Schnittflächenschleife (306 × k Aufrufe); Verträge an `area_shares` als Ganzem.
  `deal.pure` nur auf `ordinal_score`.
- Umlaute in Portal-Dateinamen (`Sozialräume_…`, `Erläuterung_…`): die Settings tragen die URL
  prozentkodiert, `requests` kodiert selbst; die lokalen Namen sind ASCII.
- Lizenz: DL-DE BY 2.0 verlangt die Namensnennung mit Quelle und Datensatz; der Fuß der Seite, `context/README.md`
  und die README nennen „Landeshauptstadt Düsseldorf, Amt für Statistik und Wahlen, Quartiersatlas 2024
  (Open-Data-Portal), dl-de/by-2-0".

## 8. Offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | Warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 3.1 | Welche Kontrollvariablen gehören ins Hauptmodell B: Handlungsbedarf-Score, Anteil 65 und älter, Fluktuationsrate; und sollen Parteianteile überhaupt als Kontrollvariablen gelten (sie sind Ergebnisse derselben Wahl wie die Wahlbeteiligung)? | Bestimmt Tabelle 6 und die Plots; Parteianteile im Modell sind inhaltlich angreifbar, das Briefing nennt sie aber ausdrücklich | B wie in § 2; Parteianteile nur im Parteimodell C (CDU, AfD) und einzeln in Tabelle 6b, mit einem Satz zur Endogenität auf der Seite |
| 3.2 | Darf die Skala gering = 1 bis hoch = 5 für `Sozialer_HB` gleichabständig sein, oder wäre `Mindestsicherungsquote` als stetige Größe lieber? | Ordinal als metrisch ist eine Annahme; die Stadt veröffentlicht den Index ohne Zahlenwerte | gleichabständige Skala in den Settings, `Mindestsicherungsquote` in Tabelle 6b als Gegenprobe |
| 3.3 | Sind 2,3 MB Fremddaten unter `context/` im Repo in Ordnung (Namensnennung erfüllt), oder sollen nur Prüfsummen und URLs ins Repo und der Pages-Workflow lädt? | Repo-Größe und Reproduzierbarkeit ohne Netz; das Portal benennt Dateien um (`…_0.csv` → `…_1.csv` beim Wahlergebnis) | ins Repo, mit README und SHA-256 |
| 3.4 | Ist der Datenstand 31.12.2021 für eine Wahl 2025 akzeptabel, oder soll die Option warten, bis die Stadt den Quartiersatlas fortschreibt? | Deutung der Koeffizienten; eine Fortschreibung hat kein bekanntes Datum | ja, mit Hinweis auf der Seite; die Settings machen einen Wechsel zu einem Satz Dateien |
| 3.5 | Soll Tabelle 6 wie Tabelle 5 auch die Variante ohne die Wahlbezirke 1 und 10 zeigen? | Seitenlänge gegen Konsistenz | beide Stichproben in Parquet; auf der Seite nur „alle" als Tabelle und ein Satz zum Hauptmodell ohne 1 und 10 |
| 3.6 | Sollen Terme in Prozent (Anteile × 100) und die Trefferquote unskaliert bleiben, wie in Tabelle 5? | Lesbarkeit der Koeffizienten gegen Vergleichbarkeit mit Tabelle 5 | Prozent für Anteile, Trefferquote unskaliert, dazu standardisierte Koeffizienten als Spalte |
| 3.7 | Welcher der beiden Datensätze entscheidet bei Stimmbezirk 3301 (GeoJSON Hafen, CSV Unterbilk)? | Nur 297 Wahlberechtigte; betrifft den Attribut-Crosswalk, nicht die Sozialräume | das GeoJSON, wie im Briefing; Test dokumentiert die Abweichung |

| 3.8 | Das Parteimodell C erreicht VIF 6,7 (Handlungsbedarf-Score), ohne die Ausreißer 7,5 -- mehr als die in Stufe D.6 erhofften 5. Reicht die Grenze 10, oder soll C ohne die Parteianteile auskommen? | Deutbarkeit des Parteimodells | Grenze 10, umgesetzt und getestet; die Spalte VIF steht auf der Seite, der Hinweis dazu auch | offen, blockiert nicht (2026-10-12) |
| 3.9 | Tabelle 6 steht als eine Tabelle je Modell auf der Seite (Term × Koeffizient, Standardfehler, p, standardisiert, VIF) statt als eine breite Tabelle mit einer Spalte je Modell. Ist das recht? | vier Zahlen je Term und Modell wären zwölf Spalten geworden | je Modell eine Tabelle; der Vergleich steht im Satz zur Deutung und in Tabelle 6b | offen, blockiert nicht (2026-10-12) |

Keine Frage blockiert; alles läuft unter den Annahmen weiter.

## 9. Vorbereitung für Option 10 (was wird konfigurierbar, welche Modulgrenze entsteht)

- Konfigurierbar in `[context]`: das Verzeichnis, jede Quelle mit URL, Dateiname, Lizenz, Namensnennung und Stand;
  die Raumeinheit (GeoJSON, Schlüsseleigenschaft, CSV-Schlüssel, Trennzeichen, Dezimalzeichen, Fehlwert); die
  Skalen ordinaler Spalten; die Variablen (Spalte, Art, Skalierung, Label, Einheit); die Modelle (Listen von
  Termen); die Schwellen (`max_missing_weight`, `min_coverage`); `y_scale`. Eine andere Stadt tauscht die Tabelle
  aus, der Code kennt weder „Sozialraum" noch „Quartiersatlas" (Namen kommen aus den Settings in Seite und Doku).
- Modulgrenzen: `georep.crosswalk` ist die eine Umrechnung von Flächeneinheiten auf Wahlbezirke über Stimmbezirke
  und ein Gewicht je Stimmbezirk; Option 2 (Wahlbezirke 2020 → 2025 über Stimmbezirksflächen mit Wahlberechtigten)
  und Option 5 (Stadtbezirk je Wahlbezirk aus `Stadtbezirk Nr.`, `attribute_weights`) können sie unverändert
  nutzen. `georep.analysis.ols` ist die Regression mit mehreren Termen; Option 6 kann ihre Sensitivitätstabelle
  (Tabelle 5 unter jeder Gewichtung) darüber rechnen, und die „Kennzahlvariante mit eigener Regression" aus § 5
  Phase 2 des Meta-Plans wäre ein Frame plus Termliste. `georep.prep.context` ist die Aufbereitung tabellarischer
  Fremddaten je Einheit zu Variablen je Wahlbezirk.
- Für das Fundament vorgeschlagen (Supervisor): ein Register veröffentlichter Tabellen (Name, Pfad, Beschreibung,
  Spaltendoku, CSV-Regeln an einer Stelle statt in `published_tables`, `COLUMN_DOCS`, `DESCRIPTIONS`, `csv_plan`);
  ein Register der Seitenabschnitte mit Reihenfolge und Budget; `context_root` als allgemeiner Ort für Fremddaten
  aller Optionen (Option 1: Daten der zweiten Stadt; Option 2: Zuschnitt 2020).
- Docstrings verweisen auf `architecture.md`; jede Entscheidung aus § 2 bekommt einen Punkt in `decisions.md`.

## 10. Änderungen durch die Synergiephase

Stand 2026-10-12, geschrieben vom Supervisor nach [00-synergien.md](00-synergien.md). Das Fundament liegt auf
`main` (Commits `d7df0ed` bis `b8e44b1`, Branch rebased); was unten steht, gilt vor den Stufen in § 5. Für alle
Optionen (00-synergien.md, § 2 und § 5):

- **Vorlage**: `report.html.j2` ist Rahmen; ein neuer Abschnitt ist eine neue Datei
  `src/georep/report/templates/sections/NN-name.html.j2` (Nummern in 00-synergien.md § 5.1), optional mit
  `NN-name.css` und `NN-name.js` daneben; `render.sections()` bindet sie in Nummernfolge ein. Das Makro
  `term` kommt aus `templates/macros.html.j2` (`{% from "macros.html.j2" import term %}`). Ein Abschnitt, der
  nur mit einem Modellteil existiert, steht in `{% if model.<teil> %} … {% endif %}`, das Feld in `ReportModel`
  hat Default `None` und steht am Ende der Klasse.
- **JavaScript**: Abschnitts-Skripte sprechen mit `window.georep` (`select(ids, scroll)` für Zahl, Array
  oder `null`; `showDocuments(terms, title)` mit mehreren Begriffen; `rows`). Der Kartenumschalter ist
  generisch: Radio `input[name="metric"]` mit `value`, Attribut `data-class-<value>` je Fläche
  (`charts.choropleth(..., extra_classes={"<value>": classification})`), Legende `.legend#legend-<value>`.
- **Tabellen**: jede neue veröffentlichte Tabelle ist ein `PublishedTable`-Eintrag am Ende von `TABLES` in
  `src/georep/report/tables.py` (Name, Pfad-Lambda, Beschreibung, Spaltendoku, CSV-Regeln, `optional`);
  `published_tables`, `COLUMN_DOCS`, `DESCRIPTIONS` und `export.csv_plan` gibt es nicht mehr.
- **Regression**: `analysis.regression.regression_pair(frame, exclude, *, x, y, y_scale)` rechnet beide
  Spalten von Tabelle 5 für jede Kennzahlspalte; die Ausreißer kommen aus `settings.analysis.exclude_districts`
  (`defaults.toml`, `[analysis]`), `OUTLIERS` gibt es nicht mehr.
- **Settings**: neue Tabellen am Ende von `defaults.toml` in einem Block `# --- Option NN`, neue Modelle vor
  `class Settings`, neue Felder am Ende von `Settings`; Pfade und reine Anzeigewerte aus `fingerprint()`
  ausschließen (Kommentar dort). Neue Layout-Properties am Ende der Klasse vor `runtime_dirs`.
- **Pipeline**: neue Schritte mit Kommentar `# --- Option NN` an der Stelle ihrer Abhängigkeit; neue Eingaben
  von `report` am Ende seines Tupels.
- **Tests**: `test_cli.py`, `test_pipeline.py`, `test_report_build.py` zählen Schritte und Dateien aus
  `build_steps` und dem Register; eigene Erwartungen in eigene Tests. Den Snapshot `test_cli.ambr`
  (`georep steps`) bewusst erneuern, Diff im Commit.
- **Doku**: `decisions.md` neuer Punkt ohne feste Nummer („## Punkt: <Titel> (Option NN, Datum)"; Punkt 21
  ist das Fundament, der Supervisor nummeriert beim Merge); CHANGELOG unter „Unreleased" als eigener Absatz.
- **Vorschau**: lokaler Server auf Port `8700 + NN`; `.claude/launch.json` je Worktree anlegen. Browser-Prüfung
  nach § 8.4 des Meta-Plans.
- **Cache**: `cache_root` ist geteilt; nichts außer `bootstrap` schreibt den Textstore der Hauptperiode.
- **Fragen**: die Antworten und Vorentscheidungen stehen in [fragen.md](fragen.md); neue Fragen in § 8 dieses
  Plans eintragen, der Supervisor sammelt sie.

Für Option 3 im Besonderen:

- **Crosswalk-Modul heißt `georep/crosswalk.py`** (Fundament F5, nicht `prep/crosswalk`): `unit_weights(frame,
  unit, weight)` ist der Attribut-Crosswalk (Stadtteil zu Wahlbezirk über Wahlberechtigte je Stimmbezirk), mit
  Verträgen und `contracts.sums_to_one`; `precinct_table` aus `prep/context.py` liefert ihm die Eingabe.
  `area_shares(sources, targets, *, min_coverage)` und `district_weights` baut 03 in diesem Modul, in der Form
  aus 00-synergien.md § 2 Punkt 4 (`source_id` String, `target_id` Int64, `share` Float64, `coverage` Float64;
  Anteile auf die Schnittsumme normiert; `SchemaError` unter `min_coverage`), weil Option 2 dieselbe Funktion
  für Stimmbezirke 2020 auf Wahlbezirke 2025 nutzt.
- **`Layout.context_root`**: als fünftes Feld mit Default `None` nach `profile`; `guard_writable` verweigert
  auch Pfade darunter. Tests, die `Layout(a, b, c)` positional bauen, bleiben gültig.
- **Modell A** über `regression_pair` aus `analysis/regression.py` (Fundament F3; Ausreißer aus
  `analysis.exclude_districts`), das OLS-Modul daneben.
- **Added-Variable-Plots**: `charts.Axes` (Fundament F7) liefert Gitter, Achsen, Ticks und Titel; das in
  Stufe E geplante Refactoring von `scatter` entfällt.
- **Tabellen**: `wahlbezirke_kontext`, `wahlbezirke_crosswalk`, `regression_kontrollen` als Einträge in
  `TABLES`, `optional=True` (sie fehlen in Profilen ohne Kontextdaten).
- **Abschnitte**: `sections/32-kontrollvariablen.html.j2` und `sections/65-abgeleitete-daten.html.j2`; der
  Lizenzsatz zum Quartiersatlas im Fuß des Rahmens (Textkonflikt mit 02, der Supervisor löst ihn).
- **Reihenfolge**: 03 merged als Vierte (nach 08, 05, 06); 05 hat dann `columns.results.city_district` und
  nutzt `unit_weights` für Stadtbezirke; 03 ergänzt den Stadtteil daneben.
- **Fragen**: 3.1 und 3.3 offen (fragen.md); 3.2, 3.4, 3.5, 3.6, 3.7 wie angenommen.

## 11. Was beim Bauen anders kam (2026-10-12)

Umgesetzt sind alle Stufen; diese Punkte weichen vom Plan ab, je mit Grund.

- **`area_shares` liefert beide Schlüssel als Text**, nicht `target_id` als Int64 (00-synergien.md § 2 Punkt 4):
  die Schlüssel der Raumeinheiten tragen eine führende Null (`011001`), ein Int64 könnte sie nicht führen. Die
  Spaltennamen bleiben, wie verabredet; Option 02 castet beim Join, wenn sie Int64 braucht.
- **Die Probe gegen den Attribut-Crosswalk** (Stufe B.4) nutzt die zu Stadtteilen verschmolzenen Raumeinheiten
  statt der Stadtteilgrenzen 2025: so prüft sie die Methode und nicht zwei Portaldateien verschiedener
  Jahrgänge, und ein Datensatz weniger wandert in die Fixture. Die erwarteten 0,02 Abweichung waren zu
  optimistisch; gemessen sind im Mittel 0,001 und höchstens 0,067, weil die Stadt einen Stimmbezirk ganz einem
  Stadtteil zuordnet und die Fläche ihn teilt. Der dominante Stadtteil stimmt in 40 von 41 Wahlbezirken.
- **Keine Stadtteilnummer in den Settings.** Produktiv wird sie nicht gebraucht (die Variablen kommen aus den
  Raumeinheiten), nur in der Probe; der Test liest die Eigenschaft des Mini-GeoJSON selbst. Wenn Option 05
  `columns.results.city_district` bringt, steht der Stadtteil daneben, ohne dass hier etwas wartet.
- **Tabelle 6 ist je Modell eine Tabelle** (§ 8, Frage 3.9), und **Modell A kommt aus `fit_ols`** statt aus
  `regression_pair`: ein Test hält beide auf allen Stellen gleich, und so stehen in Tabelle 6 überall dieselben
  Größen (t, standardisiert, VIF, adjustiertes R²), die `regression_pair` nicht liefert. Tabelle 5 rechnet
  unverändert `regression_pair`.
- **Die Plots tragen nur `data-id`** statt der vollen Tooltip-Attribute: vier Plots mit je 41 Punkten kosteten
  sonst 95 KB statt 37 KB. Ein Abschnitts-Skript bindet den Klick an `window.georep.select`; der Tooltip bleibt
  Karte und Streudiagramm.
- **`PublishedTable.describe`** ist neu im Register (F2): die Spalten von `wahlbezirke_kontext` stehen in den
  Settings, eine statische Spaltendoku könnte sie nicht nennen. `column_docs` nimmt dafür die Settings entgegen.
- **VIF im Parteimodell** erreicht 6,7 statt der erhofften unter 5 (§ 8, Frage 3.8); die Grenze 10 hält ein Test.
- **Kein Alias `fetch_results_csv`.** Der Plan sah ihn beim Umbenennen vor; es gibt drei Aufrufstellen, alle
  im Repo, und ein Alias ohne Nutzer ist Ballast.
- **Der Vertrag „Anteile in [0, 100], Scores in [1, 5]"** aus Stufe C.3 ist durch die Arten der Variablen
  ersetzt: `aggregate_context` prüft ordinale Mittel gegen ihre eigene Skala (aus den Settings, nicht gegen
  feste 1 bis 5), und eine Obergrenze 100 gilt nicht für alle Variablen -- Fluktuationsrate (je 1 000) und
  Wohndauer (Monate) liegen darüber. Dass ein gewichtetes Mittel zwischen Minimum und Maximum der Einheiten
  liegt, prüft stattdessen ein hypothesis-Test.
- **Zwei Funde nebenbei**: ein Polars-Join legt die Zeilenfolge nicht fest, und eine Fließkommasumme hängt von
  ihr im letzten Bit ab -- `aggregate_context` und `district_weights` sortieren jetzt vor dem `group_by`, sonst
  schrieben zwei Läufe verschiedene Parquet-Dateien. Und `erhöht` als nackter TOML-Schlüssel ist ein
  Syntaxfehler (TOML erlaubt nur `[A-Za-z0-9_-]`), was `tomllib` als „Expected '=' after a key" meldet.

## 12. Rebase auf `main` mit 08, 05 und 06 (2026-10-12)

27 Commits ohne Nachbesserung übernommen; die Konflikte lagen an den verabredeten Anhängestellen
(`defaults.toml`, `settings.py`, `layout.py`, `pipeline.py`, `cli.py`, `report/model.py`, `report/tables.py`,
`sections/60-methode.html.j2`, die Tests, der Snapshot und die fünf Doku-Dateien) und waren bis auf drei
Punkte mechanisch:

- **`UNIT` war zweimal da.** `crosswalk.UNIT` (Spalte der Raumeinheit, Option 03) und `weights.UNIT` (Name der
  Einheitsvariante, Option 06) sind beide der String `"einheit"` und kollidierten im Import von
  `report/model.py`. Der Crosswalk-Name heißt dort jetzt `CROSSWALK_UNIT`; beide Bedeutungen bleiben getrennt
  lesbar, am Verhalten ändert sich nichts.
- **`column_docs` brauchte beide Argumente.** Option 06 hatte `published(layout, settings)` eingeführt
  (Tabellen abgeschalteter Stufen), Option 03 `_table_docs(table, path, settings)` (Spalten aus den Settings).
  Die vereinte Fassung nimmt `settings` verpflichtend und reicht es an beide weiter.
- **Ein zählender Test im slow-Lauf.** `test_context_pipeline.py` verlangte elf Offline-Schritte und eine
  Seite unter 800 KB; beides war vor dem Rebase richtig. Die Zahl kommt jetzt aus `build_steps` (F6), das
  Budget ist das der Seite (1,5 MB), und die Dateizahl steht nicht mehr als Literal daneben.

Gemessen nach dem Rebase: `nox` grün (492 schnelle Tests, Abdeckung 98,5 %), `pytest -m slow` grün (elf
Tests, 49 s), `nox -s bench` zweimal grün, `index.html` 986 KB (gzip 168 KB), zwölf Abschnitte in der
Reihenfolge aus 00-synergien.md § 5.1, Tabelle 6 und die vier Added-Variable-Plots in Hell und Dunkel
gelesen.
