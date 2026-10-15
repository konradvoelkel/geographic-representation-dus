# Paket Mönchengladbach (voller Lauf vom 2026-10-13, Flächen und Geodaten vom 2026-10-15)

Die Eingaben eines echten Laufs der zweiten Stadt, eingefroren, damit GitHub Pages ihre Seite
**ohne Netz** baut. `profiles/moenchengladbach.toml` zeigt mit `reference_root` hierher,
`bootstrap` erkennt dieses Format (Metadaten und Textstore liegen schon so, wie das Programm sie
schreibt) und kopiert nur (`src/georep/bootstrap.py`, `seed_stores_from_native`). Entstanden nach
`docs/runbook-stadt.md`, § 5; Entscheidung: `docs/decisions.md`, Punkt 56 (Frage 1.2).

Dieser Ordner wird **nur gelesen**: `Layout.guard_writable` verweigert jeden Schreibvorgang
darunter, und die pre-commit-Hooks lassen ihn aus. Die Dateien sind unverändert, wie Quelle und
Lauf sie geliefert haben; ein neuer Lauf überschreibt sie nicht, sondern schreibt nach
`data_root/moenchengladbach/`.

**Die PDFs liegen nicht im Paket**, nur ihre Texte — wie bei der Referenz der Arbeit
(`reference/interim/paper_with_text.json`). Die 658 PDFs sind 233 MB; sie bleiben im Cache des
Rechners, der sie geholt hat.

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `cache/text/texts.parquet` | 994 204 | `f65d088bcddc5a09717024a5b1b6d5056f6081dcefab64012b21bd9293f056b8` |
| `external/Open-Data-05116000-Ratswahl-Stimmbezirk.csv` | 30 574 | `50a46ec355866504ac1b657005fa66f97a7437b4f311ecb1f8ada530977284e9` |
| `external/Open-Data-05116000-Ratswahl-Wahlbezirk.csv` | 4 429 | `48f806fd70f460dd1cebe83c5f3cddbf28b2e4bdd123c33b6e3b8239948296d2` |
| `external/Stimmbezirke_Kommunalwahl_2025.json` | 1 043 618 | `c2d3de4b862e615e6ddc998c6b7b4dd3f58bf35c4d4137a1b41b25ac4d093b94` |
| `external/opendata-strassen.csv` | 99 117 | `d4dcc486eaf2741a8a3fc5c42ead1270aa3872ac2de41357bbb3d9ed1881626e` |
| `raw/organizations.json` | 424 667 | `df7f706b091d8ffae3c8e02325b20267e60ff9592f3ed2d135bfd218f379d94c` |
| `raw/papers.jsonl` | 2 157 088 | `d1f92f4c9400697628990548c32272338ddb8c38043acf4834125b478933a9ae` |
| `raw/streets_per_district.json` | 74 549 | `51a9c9b37afcc8ce2496a6df562b2c4cd73091367f5edb9a217178cf4cb093c4` |
| `raw/wikipedia_dict.json` | 396 671 | `e659c421e7216b186b160e3802516fc1c048c67c66a6f72dcd19f3c2b2692254` |

Zusammen 5 224 917 Bytes (4,98 MiB). `tests/unit/test_data_packages.py` hält diese Tabelle gegen
die Dateien im Repo (Größe und Prüfsumme je Zeile, der `slow`-Teil auch die Zeilenzahlen).

## Zahlen des Laufs (2026-10-13 und 2026-10-15)

| Größe | Wert |
|---|---|
| Ratsdokumente der Wahlperiode 14.09.2020 bis 13.09.2025 | 2 895 |
| davon mit Hauptdatei (`mainFile`) | 2 871 |
| abgerufene PDFs | **658** |
| Texte im Store | 658, davon 650 mit Inhalt |
| Zeichen im Store | 3 394 323 |
| Stimmbezirksflächen (Geoportal, `identify`) | **179** Flächen in 33 Wahlbezirken, 170,47 km², 25 187 Stützpunkte |
| Straßenlisten (Overpass) | 179 Stimmbezirke, 2 982 Zuordnungen, 1 814 verschiedene Straßennamen |
| Orte (Wikidata Q2758 und Wikipedia-GeoSearch) | 2 219 Einträge, 2 215 einem Bezirk zugeordnet |
| Übereinstimmung mit dem amtlichen Straßenverzeichnis | 2 667 Zuordnungen (Stimmbezirk, Name) mit einem Namen, den das Verzeichnis kennt — 1 563 verschiedene Namen: 70,8 % im selben Stimmbezirk, **88,8 % im selben Wahlbezirk**; dazu 315 Zuordnungen mit 251 Namen, die das Verzeichnis nicht führt |
| Dokumentarten | 16, häufigste `1.1 - Beratungsvorlage` (1 144), `2.1 - Berichtsvorlage` (946), `3 - Fraktionsantrag` (581) |
| Organisationen im Katalog (`raw/organizations.json`, 2026-10-14) | **122**, davon 8 Fraktionen |
| Organisationen in einer Beratungsfolge | 27; alle 2 895 Dokumente tragen eine |

**2 213 der 2 871 Hauptdateien sind nicht abrufbar**: das Ratsinformationssystem antwortet auf
ihre `downloadfiles`-URL mit `404`. Der Abruf isoliert jeden Fehler (Phase 1), der Lauf geht also
durch und die Kette rechnet mit den 658 Texten, die es gibt. Woran es liegt, sagt der Server
nicht; die Metadaten nennen die Datei, der Download verweigert sie. Für die Seite heißt das: die
Trefferzahlen Mönchengladbachs ruhen auf rund einem Viertel der Dokumente der Periode und sind
mit denen Düsseldorfs **nicht** der Höhe nach vergleichbar. Beide Seiten sagen es seit dem
2026-10-14 selbst: die Stadtseite in den Kernzahlen („Ratsdokumente 2 895, 650 mit Text, 2 245
ohne"; die Kachel „Dokumente mit Treffer" nennt 489 als 16,9 % aller Dokumente **und** 75,2 % der
650 mit Text), der Städtevergleich in der Spalte „davon mit Text" seiner Tabelle und mit einem
Satz im Abschnitt „Vergleichbarkeit".

**Die Flächen sind die des Wahltags** (seit dem 2026-10-15, `docs/decisions.md`, Punkt 65): der
Layer „Kommunalwahl 2025 Stimmbezirke" des Geoportals, alle 179 Urnen-Stimmbezirke. Vorher lag hier
der Datensatz „Wahlen" vom 08.06.2022 mit 180 Polygonen, von denen nur 175 zu Stimmbezirken der
Wahl gehörten.

**Das hebt die Übereinstimmung, aber nicht über die Grenze des Runbooks**: von 86,2 % auf
**88,8 %** je Wahlbezirk und von 66,5 % auf **70,8 %** je Stimmbezirk (2 667 statt 2 651
Zuordnungen mit bekanntem Namen). 90 % je Wahlbezirk nennt `docs/runbook-stadt.md`, § 4 als die Grenze, unter der eine
Anfrage an die Stadt lohnt — die Zahl liegt weiter darunter, und das Alter der Flächen war damit
**nicht** der ganze Grund. Was bleibt, ist der Unterschied der Bezugsgrößen: das Verzeichnis ordnet
eine Straße über Adressen genau einem Stimmbezirk zu, die Overpass-Antwort über die Geometrie des
Straßenzugs, und ein Straßenzug, der eine Bezirksgrenze überschreitet, zählt dann in beiden
Bezirken. Die 315 Namen, die das Verzeichnis gar nicht kennt, sind unverändert. Die Stadtseite
nennt die Zahl, der Städtevergleich verweist darauf.

**Die Drucksachennummer nennt kein Gremium, die Beratungsfolge schon** (Punkt 58, seit dem
2026-10-14): Mönchengladbachs Nummern tragen kein Kürzel (`0682/XI`), `bodies.reference_pattern`
ist im Profil darum leer, und bis zum 2026-10-14 zeigte der Abschnitt „Gremien" 100 % unbekannt.
Das OParl-Feld `consultation` füllt die Lücke zur Hälfte: **alle 2 895 Dokumente** tragen eine
Beratungsfolge, sie nennt 27 verschiedene Organisationen, und 1 620 Dokumente (56,0 %) nennen
genau eine -- die entscheidet dann. Die übrigen 1 275 nennen mehrere; welches davon das
federführende ist, steht nicht in den Daten (die Liste kommt sortiert und entdoppelt), und sie
bleiben darum sichtbar „unbekannt". Die Namen und Kürzel der 27 stehen als `[bodies]` im Profil
und sind aus `raw/organizations.json` gelesen, das darum in diesem Paket liegt.

## Herkunft und Lizenz

| Datei | Quelle und Abrufdatum | Lizenz |
|---|---|---|
| `external/Open-Data-05116000-Ratswahl-*.csv`, `external/opendata-strassen.csv` | `wep.itk-rheinland.de/vm/prod/kw_2025/05116000/daten/opendata/` (votemanager-Wahlpräsentation der ITK Rheinland für die Stadt Mönchengladbach), **abgerufen am 2026-10-14** | laut Anbieter **nicht angegeben**; genannt werden Quelle und Herausgeber (Frage 1.4) |
| `external/Stimmbezirke_Kommunalwahl_2025.json` | Geoportal der Stadt Mönchengladbach, ArcGIS-Dienst `K12_Politik_und_Wahlen`, **Layer 16** („Kommunalwahl 2025 Stimmbezirke"), Operation `identify` mit `maxAllowableOffset=0` und `f=json`; die ganze Anfrage steht in `profiles/moenchengladbach.toml`. **Abgerufen am 2026-10-14**, Stand der Daten „Aktualität Kommunalwahl 2025" | Datenlizenz Deutschland – Zero – Version 2.0 (dl-de/zero-2.0) |
| `raw/papers.jsonl` | Ratsinformationssystem der Stadt Mönchengladbach über OParl 1.1, `ris-oparl.itk-rheinland.de`, Body 0011, abgerufen am 2026-10-13 | kein Lizenzhinweis am Endpunkt; genannt werden die Kennungen |
| `raw/organizations.json` | derselbe Endpunkt, `…/bodies/0011/organizations`, **abgerufen am 2026-10-14** (eine Seite, 122 Organisationen, 3,8 s); Namen und Kürzel der Gremien in `[bodies]` | wie die Dokumente; die Datei nennt Organisationen, keine Personen |
| `cache/text/texts.parquet` | aus den 658 PDFs desselben Endpunkts mit pypdf 6.20.0 extrahiert | wie die Dokumente |
| `raw/streets_per_district.json` | OpenStreetMap über die Overpass-API, je Stimmbezirk, **abgerufen am 2026-10-15** (die Instanz wies die Abfragen zwei Tage lang mit `504` ab, der Abruf lief in 130 Durchläufen über den HTTP-Cache auf) | ODbL |
| `raw/wikipedia_dict.json` | Wikidata (SPARQL, Q2758) und Wikipedia-GeoSearch, **abgerufen am 2026-10-14** | CC0 bzw. CC BY-SA |

## Was im Paket **nicht** liegt

- die PDFs (233 MB) und ihr `manifest.jsonl`,
- die Stamps (`*.stamp.json`): sie gehören zur Datenwurzel eines Laufs, nicht zu seinen Eingaben,
- der HTTP-Cache (`http.sqlite`),
- alles Abgeleitete (`interim/`, `processed/`, `site/`): das rechnet `georep run` in Sekunden neu.

Die Netzstichprobe von drei Wahlbezirken, die ohne diesen vollen Lauf entstand, liegt weiter unter
`tests/fixtures/mg/` und ist die Eingabe der schnellen Tests; dieses Paket ist die Eingabe der
`slow`-Tests und von GitHub Pages.
