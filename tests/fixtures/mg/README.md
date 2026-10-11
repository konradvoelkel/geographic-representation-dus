# Mini-Fixture Mönchengladbach

Die drei Wahlbezirke 02 (Amtsgericht/Innenstadt), 10 (Alter Markt/Gründerzeitviertel) und 22
(Rheindahlen-Land) der Kommunalwahl 2025, erzeugt mit `uv run python -m tests.fixtures.make_mini_mg`
am 2026-10-12. Sie ist die Eingabe von `tests/golden/test_second_city.py`; der Golden Master dieser
Stufe ist der Vergleich der aggregierten Stimmbezirke mit der Wahlbezirks-CSV der Quelle, nicht eine
Datei unter `expected/` — die gibt es hier (noch) nicht.

**Kein unabhängiges Orakel.** Bis zum vollen Lauf (docs/runbook-stadt.md, Stufe G) ist alles, was
die Kette aus dieser Fixture rechnet, eine Charakterisierung der eigenen Kette. Für Düsseldorf
bleibt `tests/fixtures/mini/expected/` der Golden Master aus dem Altcode.

## Herkunft (einmalige Abrufe am 2026-10-12, zusammen rund vier Minuten)

| Datei | Quelle | Zuschnitt |
|---|---|---|
| `external/Open-Data-05116000-Ratswahl-Stimmbezirk.csv` | `wep.itk-rheinland.de/vm/prod/kw_2025/05116000/daten/opendata/` (30 574 Bytes, 249 Zeilen) | 24 Zeilen: die Urnen- und Briefwahlbezirke der drei Wahlbezirke |
| `external/Open-Data-05116000-Ratswahl-Wahlbezirk.csv` | ebenda (4 429 Bytes, 33 Zeilen) | 3 Zeilen; liefert die Namen der Wahlbezirke und die Soll-Summen |
| `external/opendata-strassen.csv` | ebenda (99 117 Bytes, 1 905 Zeilen) | 173 Zeilen der Stimmbezirke dieser drei Wahlbezirke |
| `external/Wahlen_EPSG25832_SHAPE.zip` | `geoportal.moenchengladbach.de/wms/Hotlinks/OpenData/` (199 548 Bytes, 180 Polygone, Stand 08.06.2022, DL-DE Zero 2.0) | 17 Polygone, mit pyshp neu geschrieben, `.prj` unverändert kopiert |
| `raw/streets_per_district.json` | drei Overpass-Antworten (`tests/fixtures/http/overpass_mg_*.json`) | Stimmbezirke 11001, 32201, 40201, einer je Wahlbezirk; 160 Straßennamen |
| `raw/wikipedia_dict.json` | SPARQL Q2758 (erste 25 von 1 190 Bindings) und drei GeoSearch-Antworten | 104 Orte, 87 einem der drei Bezirke zugeordnet |
| `raw/papers.jsonl` | eine OParl-Seite von Body 0011 (`tests/fixtures/oparl/papers_page_0011.json`) | 6 Paper |
| `text/texts.parquet` | fünf PDFs unter 110 KB daraus (`tests/fixtures/pdf/mg/`) | 5 Texte, mit pypdf extrahiert |

## Was die Stichprobe gezeigt hat

- **Body 0011 ist Mönchengladbach**: alle Paper der Seite tragen `body` `…/bodies/0011`,
  Drucksachennummern der Form `1031/XI`, `pagination.elementsPerPage` 200, `links.next` `?page=2`.
  Die Dokumentarten heißen hier anders als in Düsseldorf (`3 - Fraktionsantrag`,
  `1.1 - Beratungsvorlage`, `6.2 - Berichtsvorlage Sondergremien`).
- **Marker (Frage 1.5)**: keines der fünf PDFs enthält „betrifft“ (0 von 5). Die Seite 1 des
  Servers ist neueste zuerst, die Stichprobe besteht darum aus Fraktionsanträgen der laufenden
  Periode, nicht aus Verwaltungsvorlagen von 2020 bis 2025. Ohne Marker schneidet
  `after_marker` nichts ab, die Kette durchsucht den ganzen Text; das Runbook misst den Anteil
  am echten Korpus und das Profil bekommt dann gegebenenfalls einen anderen Marker.
- **Wahlbezirk aus der Nummer**: `gebiet-nr[1:3]` trifft für alle 33 Wahlbezirke; die Summen der
  180 Stimmbezirke gleichen der Wahlbezirks-CSV (A 204 219, B 96 880, CDU 31 834, SPD 27 229,
  GRÜNE 8 242, AfD 15 079).
