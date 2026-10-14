# Mini-Fixture Mönchengladbach

Die drei Wahlbezirke 04 (Hardt), 09 (Hermges/Dahl/Ohler) und 23 (Dorfbroich/Hövel) der
Kommunalwahl 2025, erzeugt mit `uv run python -m tests.fixtures.make_mini_mg` am 2026-10-12, die
Flächen neu am 2026-10-14. Sie ist die Eingabe von `tests/golden/test_second_city.py`; der Golden
Master dieser Stufe ist der Vergleich der aggregierten Stimmbezirke mit der Wahlbezirks-CSV der
Quelle, nicht eine Datei unter `expected/` — die gibt es hier (noch) nicht.

Für die Flächen hat das Skript **je Quellform einen Zweig** und schreibt die, die
`precincts.format` im Profil nennt: `write_shapefile_zip` schreibt das Zip mit pyshp neu,
`write_identify_json` schneidet die `results` der Dienstantwort auf die drei Bezirke, ohne eine
Zahl anzufassen. Dass der Zuschnitt die Datei im Repo zeichengleich wieder herstellt, prüft
`test_the_fixture_maker_cuts_the_identify_answer_and_writes_json`.

**Beide Quellformen der Flächen.** Seit dem 2026-10-14 liegen unter `external/` sowohl das
Shapefile-Zip von 2022 (`format = "shapefile-zip"`) als auch die Antwort des ArcGIS-Dienstes zum
Stand der Kommunalwahl 2025 (`format = "esri-identify"`, `docs/decisions.md`, Punkt 62). Beide
tragen dieselben 17 Stimmbezirke; gelaufen wird mit der Form, die das Profil nennt, und das ist
seit Punkt 62 die zweite. Die erste bleibt liegen, weil `tests/unit/test_precincts.py` den
Shapefile-Weg weiter prüft und weil ein Vergleich der beiden Stände ohne sie nicht mehr möglich
wäre.

**Warum diese drei Bezirke.** Nur ihre Straßennamen kommen in der PDF-Stichprobe überhaupt vor
(Vorster Straße und Winkeln in 04, Brandenberger Straße in 09, Hauptstraße in 23) — und zwar in
Briefköpfen von Fraktionsanträgen. Mit drei beliebigen Bezirken fände die Kette keinen einzigen
Treffer und der Schritt `index` bräche mit `EmptyResultError` ab. Für das Verhalten der Kette ist
das genug; über Mönchengladbach sagen die vier Treffer nichts.

**Kein unabhängiges Orakel.** Bis zum vollen Lauf (`docs/runbook-stadt.md`) ist alles, was die Kette
aus dieser Fixture rechnet, eine Charakterisierung der eigenen Kette. Für Düsseldorf bleibt
`tests/fixtures/mini/expected/` der Golden Master aus dem Altcode.

## Herkunft (einmalige Abrufe am 2026-10-12, zusammen rund vier Minuten)

| Datei | Quelle | Zuschnitt |
|---|---|---|
| `external/Open-Data-05116000-Ratswahl-Stimmbezirk.csv` | `wep.itk-rheinland.de/vm/prod/kw_2025/05116000/daten/opendata/` (30 574 Bytes, 249 Zeilen) | 24 Zeilen: die Urnen- und Briefwahlbezirke der drei Wahlbezirke |
| `external/Open-Data-05116000-Ratswahl-Wahlbezirk.csv` | ebenda (4 429 Bytes, 33 Zeilen) | 3 Zeilen; liefert die Namen der Wahlbezirke und die Soll-Summen |
| `external/opendata-strassen.csv` | ebenda (99 117 Bytes, 1 905 Zeilen) | 180 Zeilen der Stimmbezirke dieser drei Wahlbezirke |
| `external/Wahlen_EPSG25832_SHAPE.zip` | `geoportal.moenchengladbach.de/wms/Hotlinks/OpenData/` (199 548 Bytes, 180 Polygone, Stand 08.06.2022) | 17 Polygone, mit pyshp neu geschrieben, `.prj` unverändert kopiert (19 617 Bytes) |
| `external/Stimmbezirke_Kommunalwahl_2025.json` | die Antwort der Abruf-URL **aus dem Profil**, Wort für Wort (Abruf am 2026-10-14: 1 043 618 Bytes, 179 Flächen, 25 187 Stützpunkte, SHA-256 `c2d3de4b862e615e6ddc998c6b7b4dd3f58bf35c4d4137a1b41b25ac4d093b94`) | 17 Flächen (2 276 Stützpunkte), dieselben Nummern wie das Zip; mit `json` neu geschrieben (kürzeste Fließkommaschreibung, wertgleich), 85 200 Bytes |
| `raw/streets_per_district.json` | drei Overpass-Antworten (`tests/fixtures/http/overpass_mg_{10404,10906,32301}.json`) | ein Stimmbezirk je Wahlbezirk; 39 Straßennamen |
| `raw/wikipedia_dict.json` | SPARQL Q2758 (erste 25 von 1 190 Bindings) und die drei GeoSearch-Antworten | 75 Orte, 51 einem der drei Bezirke zugeordnet |
| `raw/papers.jsonl` | eine OParl-Seite von Body 0011 (`tests/fixtures/oparl/papers_page_0011.json`) | 6 Paper: die fünf mit PDF unten und eines ohne `mainFile` |
| `text/texts.parquet` | fünf PDFs unter 110 KB daraus (`tests/fixtures/pdf/mg/`) | 5 Texte, mit pypdf extrahiert |

Lizenzen: die votemanager-Dateien der ITK Rheinland tragen **keine Lizenzangabe** (`config.json`
sagt `lizenz: true`, eine Lizenzseite gibt es nicht; Frage 1.4) — genannt werden Quelle und
Herausgeber. Das Shapefile steht unter der Datenlizenz Deutschland – Zero – Version 2.0 (Open.NRW,
Datensatz „Wahlen" der Stadt Mönchengladbach). Die PDFs liegen unter `tests/fixtures/pdf/mg/` mit
eigener `PROVENANCE.md`; die Texte im Store sind aus ihnen extrahiert.

## Was die Stichprobe gezeigt hat

- **Body 0011 ist Mönchengladbach**: alle Paper der Seite tragen `body` `…/bodies/0011`,
  Drucksachennummern der Form `1031/XI`, `pagination.elementsPerPage` 200, `links.next` `?page=2`.
  Die Dokumentarten heißen hier anders als in Düsseldorf (`3 - Fraktionsantrag`,
  `1.1 - Beratungsvorlage`, `6.2 - Berichtsvorlage Sondergremien`).
- **Marker (Frage 1.5)**: keines der fünf PDFs enthält „betrifft", zwei enthalten „gegenstand".
  Seite 1 des Servers ist neueste zuerst, die Stichprobe besteht darum aus Fraktionsanträgen der
  laufenden Periode, nicht aus Verwaltungsvorlagen von 2020 bis 2025. Ohne Marker schneidet
  `after_marker` nichts ab, die Kette durchsucht den ganzen Text; das Runbook misst den Anteil am
  echten Korpus und das Profil bekommt dann gegebenenfalls einen anderen Marker.
- **Wahlbezirk aus der Nummer**: `gebiet-nr[1:3]` trifft für alle 33 Wahlbezirke; die Summen der
  180 Stimmbezirke gleichen der Wahlbezirks-CSV (A 204 219, B 96 880, CDU 31 834, SPD 27 229,
  GRÜNE 8 242, AfD 15 079).
