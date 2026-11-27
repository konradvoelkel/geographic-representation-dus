# Paket Straßenpunkte Mönchengladbach (Startseite, gepackt am 2026-11-27)

Die **Punkte der Straßen** auf der Karte der Startseite (`docs/plan-startseite-2026-11.md`, § 4.2),
gebaut wie `snapshots/duesseldorf-strassenpunkte/` aus den Gebäudereferenzen NRW, gefiltert über
`city.ags` (05116000). Stadtteile nennt das Profil keine; die Karte beschriftet die vier
Stadtbezirke mit den Namen aus `[report.start.city_district_names]`.

`profiles/moenchengladbach.toml` nennt den Ordner als `[street_points].package`; `bootstrap` kopiert
die Dateien nach `external/startkarte/`, der Netzschritt `street_points` (nur mit dem Schalter
`street_points.fetch`) schreibt sie neu. Der Ordner wird **nur gelesen**.

Erzeugt mit

```bash
GEOREP_STREET_POINTS__FETCH=true georep --profile moenchengladbach fetch street_points
georep --profile moenchengladbach pack --street-points snapshots/moenchengladbach-strassenpunkte
```

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `external/startkarte/strassenpunkte.parquet` | 22 677 | `0e47c2b46de0afee27bd8d6277bdadfe4fbaa758074c4bb3e94a13c48a265634` |
| `external/startkarte/quellen.json` | 386 | `432e0d22fa48d32bb715d5fdf1bafb268c2ce1f47ccc2773f15fea5e3d8a3e16` |

Zusammen 23 063 Bytes, Parquet mit zstd, Schema-Version 1. `tests/unit/test_data_packages.py` hält
diese Tabelle gegen die Dateien im Repo.

## Was drin ist

| Datei | Zeilen | Spalten | Auswahl |
|---|---|---|---|
| `strassenpunkte.parquet` | 1 871 | `strasse` (Langform, klein), `wahlkreis_id`, `x`, `y` (EPSG:25832, auf 25 m gerundet), `hausnummern` | je Paar (Straße, Wahlbezirk) des Wörterbuchs mit mindestens einer Hausnummer im Wahlbezirk: 1 871 der 2 225 Paare, aus 65 094 der 65 412 Hausnummern der Gemeinde |
| `quellen.json` | 1 Datei | `ags`, `raster_m`, `namen`, je Datei `url`, `datei`, `bytes`, `sha256`, `abgerufen` | die Gemeinde, das Raster und die Quelle |

**Keine Hausnummer**: je Paar der Medoid der Hauskoordinaten, auf 25 m gerundet, und die Zahl der
Hausnummern, wie im Paket für Düsseldorf (`snapshots/duesseldorf-strassenpunkte/`).

## Herkunft und Lizenz

| Quelle | URL | Abruf | Bytes | SHA-256 | Lizenz |
|---|---|---|---|---|---|
| Gebäudereferenzen NRW (GebRef), Geobasis NRW | https://www.opengeodata.nrw.de/produkte/geobasis/lk/akt/gebref_txt/gebref_EPSG25832_ASCII.zip | 2026-11-27 | 90 258 596 | `ff62bfc23a798f67a2371fa241ceec716a2275297a2706f88e94912a28043fce` | Datenlizenz Deutschland – Zero – Version 2.0 (open.nrw, Datensatz „Gebäudereferenzen NW"), Stand 2026-10-01 |

Das Archiv lag aus dem Lauf für Düsseldorf am selben Tag in `cache_root/startkarte/` und wurde nicht
noch einmal geladen. Das Paket fällt unter dieselbe Lizenz, dl-de/zero-2.0.
