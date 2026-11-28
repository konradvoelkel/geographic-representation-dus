# Adresspaket Düsseldorf (Vorhaben 16, gepackt am 2026-11-28)

Je **Hausnummer** der Stadt ihr Stimm- und Wahlbezirk, damit der Schritt `places` eine Adresse im
Text („Kürtenstraße 12") ihrem Wahlbezirk zuordnen kann, ohne Netz und ohne das 90-MB-Archiv
(`docs/plans/16-ortsbezug.md`, § 3.4, § 6 und § 10). Abgeleitet aus einem landesweiten Archiv, nicht
unverändert gespeichert; darum liegt es hier und nicht unter `context/` (Muster Punkt 80).

`profiles/duesseldorf.toml` nennt den Ordner als `[places].package`, die beiden Perioden erben ihn
(dasselbe Wörterbuch, dieselben Wahlbezirke); `bootstrap` kopiert die Dateien nach
`external/adressen/`. Der Ordner wird **nur gelesen**; die pre-commit-Hooks lassen `snapshots/` aus,
und `.gitattributes` hält die Bytes unverändert.

Erzeugt mit

```bash
GEOREP_STREET_POINTS__FETCH=true georep fetch street_points   # Archiv nach cache_root/startkarte/ (lag schon dort, kein Abruf)
georep run                                                       # die Stimmbezirke der Karte (interim/stimmbezirke.geojson)
georep pack --addresses snapshots/duesseldorf-adressen
```

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `external/adressen/adressen.parquet` | 104 001 | `ea0d28a446499b52d92e9f40a7d9325068d399543fca53a72408bed5f65c2c51` |
| `external/adressen/quellen.json` | 328 | `8e1383b9789131355e3bcc22404aeddd39dbb3d3bf38b44a085e90a306ba8be7` |

Zusammen 104 329 Bytes, Parquet mit zstd auf Stufe 19, Schema-Version 1
(`prep.addresses.ADDRESS_SCHEMA_VERSION`). `tests/unit/test_data_packages.py` hält diese Tabelle
gegen die Dateien im Repo.

## Was drin ist

| Datei | Zeilen | Spalten | Auswahl |
|---|---|---|---|
| `adressen.parquet` | 84 193 | `strasse` (Langform, klein, `straße` ausgeschrieben, wie `prep.streetpoints.normalize_street`), `nr` (UInt16), `zusatz` (klein, leer ohne Zusatz), `stimmbezirk_id`, `wahlkreis_id` | je Hausnummer der Gemeinde 05111000 mit Ziffernfolge als Nummer und Koordinate ihre Stimmbezirke (`crosswalk.point_shares`, Band 0) und deren Wahlbezirk: 84 193 Hausnummern an 2 652 Straßennamen, keine außerhalb der 306 Stimmbezirke, keine auf einer Grenze |
| `quellen.json` | 1 Archiv | `ags`, `archiv` mit `url`, `datei`, `bytes`, `sha256`, `abgerufen` | die Gemeinde und das Archiv aus `[street_points].url` |

**Keine Koordinate.** Der Schritt `places` braucht nur den Bezirk einer Adresse. Welche Adresse ein
Dokument nennt, steht nur lokal in `processed/adressen_wahlbezirke.parquet` und wird nie
veröffentlicht: unter den Adressen der Texte sind Anschriften von Privatpersonen (§ 3.4,
Datenschutz; Frage 9.7). Die Hausnummern selbst sind öffentliche Geobasisdaten.

## Herkunft und Lizenz

| Quelle | URL | Abruf | Bytes | SHA-256 | Lizenz |
|---|---|---|---|---|---|
| Gebäudereferenzen NRW (GebRef), Geobasis NRW | https://www.opengeodata.nrw.de/produkte/geobasis/lk/akt/gebref_txt/gebref_EPSG25832_ASCII.zip | 2026-11-27 | 90 258 596 | `ff62bfc23a798f67a2371fa241ceec716a2275297a2706f88e94912a28043fce` | Datenlizenz Deutschland – Zero – Version 2.0 (open.nrw, Datensatz „Gebäudereferenzen NW"), Stand 2026-10-01 |
| Stimmbezirke der Kommunalwahl 2025 | wie `interim/stimmbezirke.geojson` des Profils (Open-Data-Portal, Punkt 52) | – | – | – | wie dort |

Das Archiv ist dieselbe Datei, aus der der Netzschritt `street_points` die Straßenpunkte der
Startseite rechnet (`snapshots/duesseldorf-strassenpunkte/`); es lag am 2026-11-28 im geteilten
`cache_root/startkarte/`, `pack --addresses` hat es nicht neu geladen. Seine SHA-256 ist die der
Kopie, die die Messung am 2026-11-23 unter `fremddaten/opendata/` abgelegt hat. Das Paket fällt unter
dieselbe Lizenz, dl-de/zero-2.0: keine Bedingung, keine Namensnennung nötig.

## Was im Paket **nicht** liegt

- die Koordinaten der Hausnummern,
- das Archiv selbst (90 MB) und alles, was andere Gemeinden betrifft,
- Adressen aus den Texten der Ratsdokumente,
- die Stamps (`*.stamp.json`).
