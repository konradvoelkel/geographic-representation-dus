# Paket Straßenpunkte Düsseldorf (Startseite, gepackt am 2026-11-27)

Die **Punkte der Straßen** auf der Karte der Startseite (`docs/plan-startseite-2026-11.md`, § 4.1
und § 4.2) und die **Namen der Stadtteile** als Beschriftung der Grundkarte. Abgeleitet aus einem
landesweiten Archiv und einer Datei des Portals, nicht unverändert gespeichert; darum liegen sie
hier und nicht unter `context/` (Muster Punkt 80).

Das Paket gibt es, weil GitHub Pages ohne Netz baut. `profiles/duesseldorf.toml` nennt den Ordner
als `[street_points].package`, die beiden Perioden erben ihn (dasselbe Wörterbuch, dieselben
Wahlbezirke); `bootstrap` kopiert die Dateien nach `external/startkarte/`, der Netzschritt
`street_points` (nur mit dem Schalter `street_points.fetch`) schreibt sie aus den Quellen neu. Der
Ordner wird **nur gelesen**; die pre-commit-Hooks lassen `snapshots/` aus, und `.gitattributes`
hält die Bytes unverändert.

Erzeugt mit

```bash
GEOREP_STREET_POINTS__FETCH=true georep fetch street_points   # Quellen nach cache_root/startkarte/, Auszüge nach external/startkarte/
georep pack --street-points snapshots/duesseldorf-strassenpunkte
```

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `external/startkarte/strassenpunkte.parquet` | 33 675 | `ebde7c5fe5f6ca9a22197b49b90df94fa787fe6db5816fdc54ca693b4ef71f49` |
| `external/startkarte/stadtteile.parquet` | 2 105 | `9b5162e060b53ac68340029353bcc1f43bab85d1e2d81ff81431f69bab148c89` |
| `external/startkarte/quellen.json` | 711 | `cb4499167adc1e77db73fccb7d2bd43d2e33abb67c51bf73260c87c85f464897` |

Zusammen 36 491 Bytes, Parquet mit zstd, Schema-Version 1
(`prep.streetpoints.STREET_POINTS_SCHEMA_VERSION`). `tests/unit/test_data_packages.py` hält diese
Tabelle gegen die Dateien im Repo.

## Was drin ist

| Datei | Zeilen | Spalten | Auswahl |
|---|---|---|---|
| `strassenpunkte.parquet` | 2 929 | `strasse` (Langform, klein), `wahlkreis_id`, `x`, `y` (EPSG:25832, auf 25 m gerundet), `hausnummern` | je Paar (Straße, Wahlbezirk) des Wörterbuchs mit mindestens einer Hausnummer im Wahlbezirk: 2 929 der 3 589 Paare, aus 83 705 der 84 193 Hausnummern der Gemeinde 05111000 |
| `stadtteile.parquet` | 50 | `name`, `x`, `y` (EPSG:25832, ganze Meter) | je Stadtteil der Name und ein Punkt auf seiner Fläche (`representative_point`) |
| `quellen.json` | 2 Dateien | `ags`, `raster_m`, `namen`, je Datei `url`, `datei`, `bytes`, `sha256`, `abgerufen` | die Gemeinde, das Raster und die beiden Quellen aus `[street_points]` |

**Keine Hausnummer.** Der Punkt eines Paars ist der Medoid der Hauskoordinaten dieser Straße im
Wahlbezirk (der Punkt der Menge mit der kleinsten Summe der Abstände, bei Gleichstand der kleinste
Ost-, dann Nordwert), auf 25 m gerundet; dazu steht nur die Zahl der Hausnummern. Eine Hausnummer
gehört zum Wahlbezirk des Stimmbezirks, der sie enthält. Kein Punkt auf der Startseite ist feiner
als „Straße im Wahlbezirk"; Hausnummern aus den Texten werden nie zu Punkten (§ 4.2, Vorhaben 16,
§ 3.4). Hat eine Straße im Wahlbezirk nur eine Hausnummer, liegt ihr Punkt auf deren Raster.

## Herkunft und Lizenz

| Quelle | URL | Abruf | Bytes | SHA-256 | Lizenz |
|---|---|---|---|---|---|
| Gebäudereferenzen NRW (GebRef), Geobasis NRW | https://www.opengeodata.nrw.de/produkte/geobasis/lk/akt/gebref_txt/gebref_EPSG25832_ASCII.zip | 2026-11-27 | 90 258 596 | `ff62bfc23a798f67a2371fa241ceec716a2275297a2706f88e94912a28043fce` | Datenlizenz Deutschland – Zero – Version 2.0 (open.nrw, Datensatz „Gebäudereferenzen NW"), Stand 2026-10-01 |
| Stadtteilgrenzen Düsseldorf 2025, Landeshauptstadt Düsseldorf | https://opendata.duesseldorf.de/sites/default/files/Stadtteile_2025_WGS84_EPSG4326_1.geojson | 2026-11-27 | 1 335 152 | `79a500c6e390089eb4567f7baac53cbb45831ee7dc13b46346282965811c4d2b` | Datenlizenz Deutschland – Zero – Version 2.0 (Portal-API `package_show`, `license_title`), Datei vom 2025-12-02 |

Beide Dateien hat der Netzschritt `street_points` am 2026-11-27 einmal geladen; ihre SHA-256 sind
die der Kopien, die die Messung am 2026-11-23 unter `fremddaten/opendata/` abgelegt hat. Das
Paket fällt unter dieselbe Lizenz, dl-de/zero-2.0: keine Bedingung, keine Namensnennung nötig.

## Was im Paket **nicht** liegt

- die Archive selbst (`cache_root/startkarte/`, rund 90 MB),
- eine Hausnummer, eine Adresse oder ein Punkt je Hausnummer,
- die Flächen der Stadtteile (nur Name und Punkt).
