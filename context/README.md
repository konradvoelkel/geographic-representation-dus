# Kontextdaten: Quartiersatlas Düsseldorf 2024

Fremddaten neben dem eingefrorenen Datensatz der Arbeit (`reference/`), aus denen Option 3
(`docs/plans/03-kontrollvariablen.md`) die Kontrollvariablen je Wahlbezirk ableitet. `bootstrap` kopiert
die Dateien nach `data_root/external/`; der Netzschritt `georep fetch context_data` holt sie frisch vom
Portal. Unter `context/` schreibt nichts (`Layout.guard_writable`).

## Quelle

- Datensatz: „Quartiersatlas Düsseldorf 2024 - Sozialer Handlungsbedarf und Fluktuation",
  <https://opendata.duesseldorf.de/dataset/quartiersatlas-d%C3%BCsseldorf-2024-sozialer-handlungsbedarf-und-fluktuation>
- Herausgeber: Landeshauptstadt Düsseldorf, Amt für Statistik und Wahlen
- Lizenz: Datenlizenz Deutschland – Namensnennung – Version 2.0, <https://www.govdata.de/dl-de/by-2-0>.
  Namensnennung: „Landeshauptstadt Düsseldorf, Amt für Statistik und Wahlen: Quartiersatlas Düsseldorf 2024
  (Open-Data-Portal), dl-de/by-2-0".
- Datenstand: 31.12.2021; Sozialräume im Zuschnitt 2021 (171 Stück). Im Portal angelegt am 2026-09-17,
  Dateien vom 2026-02-02 und 2026-02-17 (`Last-Modified`).
- Abgerufen am 2026-10-12 (00:40 Uhr Ortszeit) mit `curl`, unverändert gespeichert; umbenannt wie die
  Dateien der Arbeit (ASCII, ohne Umlaut, mit Jahr).

| Datei hier | Datei im Portal (`https://opendata.duesseldorf.de/sites/default/files/…`) | Bytes | SHA-256 |
|---|---|---|---|
| `quartiersatlas_2024.csv` | `Daten_QA_2024.csv` | 47 742 | `c934da5164fcff2acc405fbff968efe501339a1c728f7b241fd7c8517397eefc` |
| `sozialraeume_2021.geojson` | `Sozialr%C3%A4ume_QA_Daten_WGS84_EPSG_4326.geojson` | 2 181 075 | `396b8bdc863778243c62b4a9ca1facdc4f6b19213548d127c18190c78a77e81c` |
| `quartiersatlas_2024_indikatoren.csv` | `Erl%C3%A4uterung_Indikatoren_QA_0.csv` | 13 499 | `fc056e88f65ece7c07ffd7e83c58c0ef4b84c6ce4727428fbdeb71a45a33a78e` |

Prüfen: `sha256sum context/*.csv context/*.geojson`.

## Inhalt, nachgesehen am 2026-10-12

- `quartiersatlas_2024.csv`: UTF-8, `;`, CRLF, Dezimalkomma, 171 Zeilen, 54 Spalten; Schlüssel `SRG_2021_Nr`
  (sechsstellig, die ersten drei Ziffern sind die Stadtteilnummer), `SRG_2021_Name`. Fehlwerte: `.` für
  anonymisierte Werte unter 3 (Hinweis des Portals; häufig in den Schulspalten), außerdem `x`, `-` und
  `#NV` im Sozialraum 071009 Glasmacherviertel (2021 noch unbebaut, keine Daten). Positive Wanderungssalden
  tragen ein `+`. Die Ordinalspalten `Sozialer_HB` und `HB_Fluktuation` haben die Stufen gering, eher gering,
  mittel, erhöht, hoch.
- `sozialraeume_2021.geojson`: 171 MultiPolygon-Features, CRS `urn:ogc:def:crs:OGC:1.3:CRS84` (lon/lat);
  Eigenschaften `STADTBEZIR`, `SOZIALRAUM` (Schlüssel zu `SRG_2021_Nr`, alle 171 genau einmal) und die
  CSV-Spalten als Text mit Präfix `Daten_QA_2024_`. Drei Flächen sind erst nach `make_valid` gültig;
  Gesamtfläche 217,4 km² in EPSG:25832.
- `quartiersatlas_2024_indikatoren.csv`: `Indikator;Berechnung;Aussagekraft;Datenquelle`, 30 Zeilen; liefert
  die Definitionen für den Abschnitt „Abgeleitete Daten" der Berichtsseite.
