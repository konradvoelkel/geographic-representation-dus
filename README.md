# Geographic Representation DUS

Wie sichtbar sind die 41 Kommunalwahlbezirke Düsseldorfs in den Dokumenten des Stadtrats, und hängt
das mit der Wahlbeteiligung zusammen? Für jeden Wahlbezirk wird ein Wörterbuch aus Straßennamen
(OpenStreetMap) und Orten (Wikidata, Wikipedia) gebaut, die Ratsdokumente der Wahlperiode 2020–2025
(OParl-Schnittstelle des Ratsinformationssystems) werden danach durchsucht, und die Trefferquote je
Bezirk wird mit der Wahlbeteiligung der Kommunalwahl 2025 in Beziehung gesetzt.

Ursprung: Bachelorarbeit von Lukas Bartzsch, Heinrich-Heine-Universität Düsseldorf, Januar 2026
(<https://github.com/lubar102/geographic-representation-dus>). Dieser Fork baut den Code schrittweise um;
Ziel und Phasen stehen in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md), der aktuelle Stand in [STATUS.md](STATUS.md),
Änderungen aus Nutzersicht in [CHANGELOG.md](CHANGELOG.md).

## Loslegen

```bash
git clone git@github.com:konradvoelkel/geographic-representation-dus.git
cd geographic-representation-dus
uv sync                                 # Python 3.14 und alle Pakete aus uv.lock
uv run georep bootstrap                 # Datensatz der Arbeit nach data_root übernehmen
uv run georep run                       # sieben Schritte, etwa 5 s; ein zweiter Lauf überspringt alle
uv run georep regress --exclude 1 10    # Tabelle 5 der Arbeit
uv run georep export                    # CSV neben die Parquet-Ergebnisse
uv run nox                              # lint, typecheck, baseline, test
```

Systemabhängigkeiten: keine. Wer die Umgebung woanders ablegen will, setzt vor `uv sync` die Variablen
`UV_PROJECT_ENVIRONMENT` und `UV_CACHE_DIR`.

## Befehle

`georep run [SCHRITT …] [--force] [--dry-run] [--online]` führt die Schritte aus und überspringt, was
aktuell ist; Netzschritte laufen nur mit `--online`. `georep fetch [SCHRITT …] [--force] [--limit N]`
führt die Netzschritte aus (`opendata`, `papers`, `pdfs`, `streets_osm`, `pois_wiki`) und danach `texts`;
`--limit` begrenzt neue PDF-Downloads je Lauf. `georep steps` zeigt Eingaben und Ausgaben, `georep status`
Settings, Pfade, Stores und die Frische jedes Schritts mit Grund, `georep bootstrap [--force]` übernimmt die
Referenz, `georep export` schreibt CSV, `georep regress [--exclude …]` rechnet die Regression.
`georep profile [SCHRITT …] [--top N] [--sort tottime] [--online]` führt Schritte erzwungen unter cProfile
aus und schreibt `docs/profiling/<datum>-<schritt>.prof` für `snakeviz` (`docs/profiling/README.md`).
`--settings DATEI` legt eine weitere TOML-Schicht darüber. Exit-Codes: 0 gut, 1 Domänenfehler (eine Zeile
auf stderr), 2 Bedienfehler.

Ein voller Abruf von Grund auf (`georep fetch` auf leerem `data_root`) dauert Stunden: der OParl-Server
brauchte am 2026-10-09 85 s pro Seite, die PDFs kommen seriell mit einer Sekunde Pause. Alles ist
wiederaufnehmbar: Metadaten werden nach jeder Seite gespeichert, PDFs einzeln, HTTP-Antworten liegen in
`cache_root/http.sqlite`, und ein zweiter `fetch` holt nur Geändertes (`modified_since`) und fehlende PDFs.

## Pipeline

| Schritt | Netz | liest | schreibt |
|---|---|---|---|
| `opendata` | ja | Open-Data-Portal | `external/Stimmbezirk_Wahlergebnis.csv`, `external/Stimmbezirke_2025.geojson` |
| `papers` | ja | OParl-Liste, neueste zuerst, Abbruch unter dem Periodenbeginn | `raw/papers.jsonl` |
| `pdfs` | ja | Download-URLs der Paper | `cache/pdf/*.pdf`, `cache/pdf/manifest.jsonl` |
| `streets_osm` | ja | Overpass je Stimmbezirk | `raw/streets_per_district.json` |
| `pois_wiki` | ja | Wikidata-SPARQL, Wikipedia-GeoSearch je Stimmbezirk | `raw/wikipedia_dict.json` |
| `texts` | nein | PDFs, die noch keinen Text haben | `cache/text/texts.parquet` |
| `voters` | nein | Wahlergebnis-CSV | `processed/wahlbezirke_waehler.parquet` |
| `streets` | nein | Straßen je Stimmbezirk | `processed/wahlbezirke_strassen.parquet` |
| `pois` | nein | Orte | `processed/wikidata_vis.parquet`, `wikidata_agg.parquet` |
| `dictionary` | nein | Orte und Straßen je Wahlbezirk | `processed/combined_searchdict.parquet` |
| `corpus` | nein | Metadaten und Texte | `interim/papers.parquet` |
| `index` | nein | Wörterbuch, Korpus | `processed/inverted_index.parquet` |
| `results` | nein | Wörterbuch, Index, Wähler | `processed/wahlbezirke_auswertung.parquet` |

Neben jeder Ausgabe liegt ein Stamp mit den Hashes der Eingaben, dem Fingerprint der Settings, der
Code-Version und der Schema-Version des Schritts. Ändert sich eines davon, läuft der Schritt und alles
dahinter neu; sonst wird er übersprungen und sagt das. Alle Schreibvorgänge sind atomar, ein leeres
Ergebnis wird nicht geschrieben, und unter `reference/` schreibt nichts.

Geometrie: die Stimmbezirke (EPSG:4647) werden einmal ins metrische EPSG:25832 projiziert, dort repariert
und per STRtree abgefragt; nach lon/lat geht es an genau einer Stelle zurück (Overpass-Polygone, GeoSearch-
Boxen). Der Overpass-Filter bildet den `network_type="all"` von osmnx nach, mit dem die Daten der Arbeit
entstanden; Treue gegen die Referenz steht in `tests/fixtures/http/README.md`.

## Konfiguration

Alle Parameter stehen mit Begründung in [`src/georep/defaults.toml`](src/georep/defaults.toml). Darüber
mischen sich tief `./settings.toml` und `./settings.local.toml` (gitignored, rechnerspezifisch), darüber
Umgebungsvariablen `GEOREP_<FELD>`, verschachtelt mit `__`. Unbekannte Schlüssel sind ein Fehler.

```toml
# settings.local.toml: Daten und Cache auf einer anderen Platte
data_root = "/media/konrad/xtraspace/georep/data"
cache_root = "/media/konrad/xtraspace/georep/cache"
```

## Daten

`reference/` ist der eingefrorene Datensatz der Arbeit: Rohdaten (Wahlergebnis, Stimmbezirke, Straßen,
Orte), die Metadaten und extrahierten Texte von 19108 Ratsdokumenten (die PDFs selbst nicht) und
die Ergebnistabellen. Er wird nur gelesen. Läufe schreiben nach `data_root` (Standard `./data`),
Caches nach `cache_root` (Standard `data_root/cache`). Abgeleitete Daten sind Parquet; `georep export`
legt CSV daneben.

## Entwicklung

- Prüfungen: `uv run nox` (lint, typecheck, deps, test) lokal und in CI rufen dieselben Sessions; `deps` verbietet pandas, geopandas, osmnx und scikit-learn im Lockfile; `test` läuft parallel mit Abdeckung als Untergrenze (90 %); `uv run pytest -m slow` läuft die Kette über die volle Referenz und vergleicht mit den Ergebnissen der Arbeit. `uv run nox -s bench` misst die heißen Pfade mit pytest-benchmark gegen den letzten gespeicherten Lauf (rot ab 20 % langsamer im Minimum), `uv run nox -s profile -- SCHRITT` profiliert einen echten Schritt; Zahlen und Befunde datiert in `docs/profiling/README.md`.
- Tests in drei Schichten: `tests/unit/` (eine Funktion, ein Verhalten), `tests/property/` (hypothesis-Invarianten; `tests/property/oracle_matcher.py` ist die lesbare Referenz des Matcher-Vertrags, die jeder Ersatz bestehen muss), `tests/golden/` (Mini-Fixture und Referenz gegen die eingefrorenen Ergebnisse der Arbeit); dazu `tests/bench/` (Laufzeit, nur in `nox -s bench`). `HYPOTHESIS_PROFILE=ci` erhöht die Beispielzahl. Mutationstests stehen noch aus: mutmut 3 forkt, Polars blockiert im Kind (`docs/mutation-2026-10-11.md`).
- Vor dem Commit: `uvx pre-commit install` einmalig; die Hooks formatieren und linten mit Ruff.
- Regeln für Commits und für Agenten: [CLAUDE.md](CLAUDE.md). Befund vor dem Umbau: [docs/baseline-2026-10-10.md](docs/baseline-2026-10-10.md).
- Struktur: `src/georep/` ist das ganze Programm (`settings`, `layout`, `io`, `http`, `geo`, `oparl`, `records`, `stores`, `errors`, `bootstrap`, `pipeline`, `profiling`, `cli`, `export`, `sources/`, `prep/`, `search/`, `analysis/`); vom Code der Arbeit ist nichts mehr übrig, ihr Datensatz liegt unter `reference/`. `tests/` mit `unit/`, `property/`, `golden/`, `bench/` und `fixtures/` (Mini-Datensatz, PDFs, OParl-Seite, aufgezeichnete HTTP-Antworten).
- Netz in Tests: nie echte Endpunkte; das `Transport`-Protokoll und die Fake-Session in `tests/fakes.py` liefern aufgezeichnete Antworten.

## Lizenz

CC0 1.0, wie das Original.
