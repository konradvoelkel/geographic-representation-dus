# Paket Mönchengladbach (voller Lauf vom 2026-10-13)

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
| `external/Open-Data-05116000-Ratswahl-Stimmbezirk.csv` | 30 574 | `50a46ec355866504ac1b657005fa66f97a7437b4f311ecb1f8ada530977284e9` |
| `external/Open-Data-05116000-Ratswahl-Wahlbezirk.csv` | 4 429 | `48f806fd70f460dd1cebe83c5f3cddbf28b2e4bdd123c33b6e3b8239948296d2` |
| `external/opendata-strassen.csv` | 99 117 | `d4dcc486eaf2741a8a3fc5c42ead1270aa3872ac2de41357bbb3d9ed1881626e` |
| `external/Wahlen_EPSG25832_SHAPE.zip` | 199 548 | `df6c3bb7e30d1b22db12cb5373cd980618552366aac5b7631390ac5cc513c48b` |
| `raw/papers.jsonl` | 2 157 088 | `d1f92f4c9400697628990548c32272338ddb8c38043acf4834125b478933a9ae` |
| `raw/streets_per_district.json` | 74 291 | `982c87025cf0ce3997ed620aacc7de10d5f4828ad4238cd6aab547146e426067` |
| `raw/wikipedia_dict.json` | 421 707 | `9317b237c3151c0de0e50514582e9c48f4d246bf0098fa93e4dad1138aa4d00c` |
| `cache/text/texts.parquet` | 994 204 | `f65d088bcddc5a09717024a5b1b6d5056f6081dcefab64012b21bd9293f056b8` |

Zusammen 3 980 958 Bytes (3,80 MiB). `tests/unit/test_data_packages.py` hält diese Tabelle gegen
die Dateien im Repo (Größe und Prüfsumme je Zeile, der `slow`-Teil auch die Zeilenzahlen).

## Zahlen des Laufs (2026-10-13)

| Größe | Wert |
|---|---|
| Ratsdokumente der Wahlperiode 14.09.2020 bis 13.09.2025 | 2 895 |
| davon mit Hauptdatei (`mainFile`) | 2 871 |
| abgerufene PDFs | **658** |
| Texte im Store | 658, davon 650 mit Inhalt |
| Zeichen im Store | 3 394 323 |
| Straßenlisten (Overpass) | 180 Stimmbezirke, 1 814 verschiedene Straßennamen |
| Orte (Wikidata Q2758 und Wikipedia-GeoSearch) | 2 373 Einträge |
| Übereinstimmung mit dem amtlichen Straßenverzeichnis | 2 651 bekannte Namen: 66,5 % im selben Stimmbezirk, **86,2 % im selben Wahlbezirk**; 315 nicht im Verzeichnis |
| Dokumentarten | 16, häufigste `1.1 - Beratungsvorlage` (1 144), `2.1 - Berichtsvorlage` (946), `3 - Fraktionsantrag` (581) |

**2 213 der 2 871 Hauptdateien sind nicht abrufbar**: das Ratsinformationssystem antwortet auf
ihre `downloadfiles`-URL mit `404`. Der Abruf isoliert jeden Fehler (Phase 1), der Lauf geht also
durch und die Kette rechnet mit den 658 Texten, die es gibt. Woran es liegt, sagt der Server
nicht; die Metadaten nennen die Datei, der Download verweigert sie. Für die Seite heißt das: die
Trefferzahlen Mönchengladbachs ruhen auf rund einem Viertel der Dokumente der Periode und sind
mit denen Düsseldorfs **nicht** der Höhe nach vergleichbar. Die Stadtseite sagt es in den
Kernzahlen („Ratsdokumente 2 895, 650 mit Text, 2 245 ohne"), der Städtevergleich im Abschnitt
„Vergleichbarkeit".

**Die Flächen sind drei Jahre älter als die Wahl**, und das kostet mehr als gedacht: 86,2 % der
2 651 bekannten Straßennamen liegen im selben Wahlbezirk wie im Verzeichnis der Wahl, 66,5 % im
selben Stimmbezirk. Das Runbook nennt 90 % je Wahlbezirk als die Grenze, unter der eine Anfrage an
die Stadt nach den Flächen von 2025 lohnt (`docs/runbook-stadt.md`, § 4, Frage 1.3); diese Zahl
liegt darunter. Die Stadtseite nennt sie, der Städtevergleich verweist darauf.

**Alle Dokumente stehen unter „Gremium unbekannt"**: Mönchengladbachs Drucksachennummern tragen
kein Kürzel (`0682/XI`), `bodies.reference_pattern` ist im Profil darum leer, und der Abschnitt
„Gremien" zeigt 100 % unbekannt (`docs/decisions.md`, Punkt 39). Der volle Lauf hat die Frage
nicht beantwortet, sondern bestätigt: auch über 2 895 Nummern taucht kein Kürzel auf. Woher das
Gremium käme, bleibt das OParl-Feld `consultation` oder die Sitzungszuordnung
(`docs/plans/01-staedte.md`, § 8, Frage 1.12).

## Herkunft und Lizenz

| Datei | Quelle, abgerufen am 2026-10-13 | Lizenz |
|---|---|---|
| `external/Open-Data-05116000-Ratswahl-*.csv`, `external/opendata-strassen.csv` | `wep.itk-rheinland.de/vm/prod/kw_2025/05116000/daten/opendata/` (votemanager-Wahlpräsentation der ITK Rheinland für die Stadt Mönchengladbach) | laut Anbieter **nicht angegeben**; genannt werden Quelle und Herausgeber (Frage 1.4) |
| `external/Wahlen_EPSG25832_SHAPE.zip` | `geoportal.moenchengladbach.de/wms/Hotlinks/OpenData/` (Datensatz „Wahlen", Stand 08.06.2022) | Datenlizenz Deutschland – Zero – Version 2.0 |
| `raw/papers.jsonl` | Ratsinformationssystem der Stadt Mönchengladbach über OParl 1.1, `ris-oparl.itk-rheinland.de`, Body 0011 | kein Lizenzhinweis am Endpunkt; genannt werden die Kennungen |
| `cache/text/texts.parquet` | aus den 658 PDFs desselben Endpunkts mit pypdf 6.20.0 extrahiert | wie die Dokumente |
| `raw/streets_per_district.json` | OpenStreetMap über die Overpass-API, je Stimmbezirk | ODbL |
| `raw/wikipedia_dict.json` | Wikidata (SPARQL, Q2758) und Wikipedia-GeoSearch | CC0 bzw. CC BY-SA |

## Was im Paket **nicht** liegt

- die PDFs (233 MB) und ihr `manifest.jsonl`,
- die Stamps (`*.stamp.json`): sie gehören zur Datenwurzel eines Laufs, nicht zu seinen Eingaben,
- der HTTP-Cache (`http.sqlite`),
- alles Abgeleitete (`interim/`, `processed/`, `site/`): das rechnet `georep run` in Sekunden neu.

Die Netzstichprobe von drei Wahlbezirken, die ohne diesen vollen Lauf entstand, liegt weiter unter
`tests/fixtures/mg/` und ist die Eingabe der schnellen Tests; dieses Paket ist die Eingabe der
`slow`-Tests und von GitHub Pages.
