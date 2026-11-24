# Paket Bedarf Mönchengladbach (Vorhaben 22, gepackt am 2026-11-24)

Die **Stadtauszüge der Bedarfsquellen** von Vorhaben 22 für die zweite Stadt, aus denselben
bundes- und landesweiten Archiven wie `snapshots/duesseldorf-bedarf/` (dort steht, warum das Paket hier
und nicht unter `context/` liegt). Mönchengladbach hat keinen Quartiersatlas und keinen
Ausschussklassifikator (`classify.enabled = false`): der Schritt `need` rechnet Unfälle, Einwohner,
Miete und Schulsozialindex je Wahlbezirk, aber keine Anteile der Klassen und keine Hypothesen (Frage
22.6). `profiles/moenchengladbach.toml` nennt den Ordner als `[context.need].package`.

Erzeugt mit

```bash
georep --profile moenchengladbach fetch need_data
georep --profile moenchengladbach pack --need snapshots/moenchengladbach-bedarf
```

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `external/bedarf/unfaelle.parquet` | 66 800 | `23cd39246a0d616cf6296143498669645e6b79839e5c85e7f512e21897056570` |
| `external/bedarf/zensus2022.parquet` | 19 019 | `c9da4c60829d0894282e52fd93adaec4e4981f53cfdfe679fc8200eb6e24318a` |
| `external/bedarf/schulen.parquet` | 2 835 | `906b25afadc8ae21a0a064d7968c6468adcd9894e939dde5eff07e645d32a953` |
| `external/bedarf/quellen.json` | 3 212 | `63459e5896814079467fbcaf855b0135d34383fb44199949ffc0ff08c1214f22` |

Zusammen 91 866 Bytes, Parquet mit zstd, Schema-Version 1. `tests/unit/test_data_packages.py` hält
diese Tabelle gegen die Dateien im Repo.

## Was drin ist

| Datei | Zeilen | Auswahl |
|---|---|---|
| `unfaelle.parquet` | 5 301 | Gemeindeschlüssel 05 1 16 000, Unfalljahre 2020 bis 2025: 812, 792, 838, 920, 901, 1 038 (wie die Messung, § 2.1) |
| `zensus2022.parquet` | 5 530 | Zellen mit Mittelpunkt in einem der 179 Stimmbezirke; 263 914 Einwohner, 3 692 Zellen mit Miete (67 mit `KLAMMERN`), 9 nur in der Mietdatei |
| `schulen.parquet` | 85 | Gemeindeschlüssel 05116000; 38 Grundschulen, 35 davon mit Stufe |
| `quellen.json` | 10 Archive | die Gemeinde und dieselben zehn Archive wie in Düsseldorf, mit denselben Prüfsummen |

Die Spalten und ihre Bedeutung sind die des Düsseldorfer Pakets. Im Zeitraum der Periode (2020-09 bis
2025-09) sind es 4 592 Unfälle, 1 017 davon im Band von 20 m auf zwei Wahlbezirke geteilt, 2 ohne
Wahlbezirk; 33 Wahlbezirke, fünf ohne Grundschule.

## Herkunft und Lizenz

Wie `snapshots/duesseldorf-bedarf/README.md`, „Herkunft und Lizenz": Unfallatlas (Statistische Ämter
des Bundes und der Länder), Zensus 2022 (Destatis), amtliche Schuldaten und Schulsozialindex
(Ministerium für Schule und Bildung NRW), alle unter der Datenlizenz Deutschland – Namensnennung –
Version 2.0, <https://www.govdata.de/dl-de/by-2-0>, mit denselben Namensnennungen. Am 2026-11-24 aus
den Archiven in `cache_root/bedarf/` geschnitten, ohne neuen Abruf.
