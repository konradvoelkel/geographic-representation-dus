# Paket Bedarf Düsseldorf (Vorhaben 22, gepackt am 2026-11-24)

Die **Stadtauszüge der Bedarfsquellen** von Vorhaben 22 (`docs/plans/22-bedarf.md`, § 6 und § 10):
Unfälle mit Personenschaden aus dem Unfallatlas, die Zellen des Zensus-Gitters 2022 mit Einwohnern
und Miete, die Schulen mit ihrem Sozialindex. Abgeleitet aus bundes- und landesweiten Archiven, nicht
unverändert gespeichert; darum liegen sie hier und nicht unter `context/` (Synergien 2026-11,
Konflikt 11). Die kleinen Pakete der Stufe 2 sind mit der Annahme zu Frage 26 freigegeben.

Das Paket gibt es, weil GitHub Pages ohne Netz baut: ohne es hätte der Schritt `need` dort keine
Eingaben. `profiles/duesseldorf.toml` nennt den Ordner als `[context.need].package`; `bootstrap`
kopiert die vier Dateien nach `external/bedarf/`, der Netzschritt `need_data` schreibt sie aus den
Archiven neu. Der Ordner wird **nur gelesen**; die pre-commit-Hooks lassen `snapshots/` aus, und
`.gitattributes` hält die Bytes unverändert.

Erzeugt mit

```bash
georep fetch need_data          # die Archive nach cache_root/bedarf/, die Auszüge nach external/bedarf/
georep pack --need snapshots/duesseldorf-bedarf
```

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `external/bedarf/unfaelle.parquet` | 161 284 | `88a8aeea92beb9e64dcab2033e0761b0fd63425821ac776c040e9e5b2bb1b61f` |
| `external/bedarf/zensus2022.parquet` | 29 884 | `025e7b6c4dc3f47802bcec116bd36f4cc97c1368c055505ff1b0297a6c7a6322` |
| `external/bedarf/schulen.parquet` | 3 638 | `a9cf9c4b3723bf48df2eb4ee612c52fd40f1547a5600b484c9569665d0a67887` |
| `external/bedarf/quellen.json` | 3 212 | `3f5d4e41f8a61ec7471ab1d450d9935a4a728340754367b95a080e68cad5afeb` |

Zusammen 198 018 Bytes, Parquet mit zstd, Schema-Version 1 (`prep.context.NEED_DATA_SCHEMA_VERSION`).
`tests/unit/test_data_packages.py` hält diese Tabelle gegen die Dateien im Repo.

## Was drin ist

| Datei | Zeilen | Spalten | Auswahl |
|---|---|---|---|
| `unfaelle.parquet` | 13 507 | `jahr`, `monat`, `kategorie` (1 Getötete, 2 Schwer-, 3 Leichtverletzte), `rad`, `fuss`, `x`, `y` (EPSG:25832, Punkt auf der Straßenachse) | Gemeindeschlüssel 05 1 11 000, Unfalljahre 2020 bis 2025: 2 224, 2 019, 2 087, 2 427, 2 343, 2 407 |
| `zensus2022.parquet` | 7 667 | `x`, `y` (Mittelpunkt der 100-m-Zelle, EPSG:3035), `einwohner`, `miete` (€ je m²), `miete_zeichen` | Zellen mit Mittelpunkt in einem der 306 Stimmbezirke; 611 134 Einwohner, 6 229 Zellen mit Miete (12 mit `KLAMMERN`), 9 nur in der Mietdatei (ohne Einwohnerzahl) |
| `schulen.parquet` | 185 | `schulnummer`, `schulform`, `x`, `y` (EPSG:25832), `sozialindex` (1 bis 9) | Gemeindeschlüssel 05111000; 88 Grundschulen (Schulform 02), 87 davon mit Stufe |
| `quellen.json` | 10 Archive | je Archiv `url`, `datei`, `bytes`, `sha256`, `abgerufen` | die Gemeinde (`ags`) und die zehn Archive aus `[context.need]` |

Der Schritt `need` nimmt davon die Unfälle der Monate der Periode (2020-09 bis 2025-09: 11 501), ordnet
sie mit einem Band von 20 m den Wahlbezirken zu und rechnet je Wahlbezirk; die Zahlen stehen im
Messdokument, § 3, und sind mit denen der Messung gleich.

## Herkunft und Lizenz

Die Archive liegen unverändert in `cache_root/bedarf/`; ihre SHA-256 stehen in `quellen.json` und sind
die der Messung unter `fremddaten/opendata/` (geladen am 2026-11-23). Am 2026-11-24 hat `need_data` je
Quelle eine Datei frisch von der Quelle geladen (Unfälle 2025, Zensus-Einwohner, Schuldaten,
Sozialindex), mit gleicher Prüfsumme; die übrigen sechs kamen aus der Ablage der Messung.

| Quelle | Archive | Herausgeber | Lizenz | Namensnennung |
|---|---|---|---|---|
| Unfallatlas, Straßenverkehrsunfälle mit Personenschaden | `Unfallorte2020_EPSG25832_CSV.zip` bis `Unfallorte2025_EPSG25832_CSV.zip` von <https://www.opengeodata.nrw.de/produkte/transport_verkehr/unfallatlas/> | Statistische Ämter des Bundes und der Länder | Datenlizenz Deutschland – Namensnennung – Version 2.0, <https://www.govdata.de/dl-de/by-2-0> | „Statistische Ämter des Bundes und der Länder, Unfallatlas, dl-de/by-2-0" |
| Zensus 2022, Gitterdaten 100 m | `Zensus2022_Bevoelkerungszahl.zip`, `Zensus2022_Durchschn_Nettokaltmiete.zip` von <https://www.destatis.de/static/DE/zensus/gitterdaten/> | Statistisches Bundesamt (Destatis) | Datenlizenz Deutschland – Namensnennung – Version 2.0 (open.nrw; Destatis: „zur freien Nutzung (mit Namensnennung)") | „Statistisches Bundesamt (Destatis), Zensus 2022, dl-de/by-2-0" |
| Amtliche Schuldaten (Eckdaten) | `schuldaten.csv` von <https://apps.schulministerium.nrw.de/BiPo/OpenData/Schuldaten/schuldaten.csv> | Ministerium für Schule und Bildung des Landes Nordrhein-Westfalen | Datenlizenz Deutschland – Namensnennung – Version 2.0 | „Ministerium für Schule und Bildung NRW, Schuldaten, dl-de/by-2-0" |
| Schulsozialindex, Schuljahr 2025/26 | `schulliste_sj_25_26_open_data.csv` von <https://www.schulministerium.nrw/system/files/media/document/file/schulliste_sj_25_26_open_data.csv> | Ministerium für Schule und Bildung des Landes Nordrhein-Westfalen | Datenlizenz Deutschland – Namensnennung – Version 2.0 | „Ministerium für Schule und Bildung NRW, Schulsozialindex, dl-de/by-2-0" |

## Was am Lauf auffiel

- Zehn Schulen der Stadt (Seminare, das ZfsL, vier neue Schulen; keine Grundschule) nennen in der
  Spalte `EPSG` das Wort `null`; ihre Koordinaten liegen im Bereich der übrigen und gelten als
  EPSG:25832 (`prep.context.read_schools`).
- Die neun Zellen nur in der Mietdatei tragen keine Einwohnerzahl und damit kein Gewicht; an Einwohnern
  und Miete je Wahlbezirk ändern sie nichts. Die Messung hatte sie beim Verbinden verloren (7 658 Zellen).
- Nicht im Paket: der Straßenverkehrslärm 2018 und die Gebäudereferenzen NRW (90 MB), die ihn verorten
  (Frage 22.2), und die Kitas.
