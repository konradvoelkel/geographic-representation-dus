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

`georep run [SCHRITT …] [--force] [--dry-run]` führt die Schritte aus und überspringt, was aktuell ist.
`georep steps` zeigt Eingaben und Ausgaben, `georep status` Settings, Pfade und die Frische jedes Schritts
mit Grund, `georep bootstrap [--force]` kopiert die Referenz, `georep export` schreibt CSV,
`georep regress [--exclude …]` rechnet die Regression. `--settings DATEI` legt eine weitere TOML-Schicht
darüber. Exit-Codes: 0 gut, 1 Domänenfehler (eine Zeile auf stderr), 2 Bedienfehler.

Der volle Lauf mit allen Netzschritten ist `uv run python run.py`: er lädt Metadaten und PDFs neu und
dauert Stunden, der OParl-Server brauchte am 2026-10-09 85 s pro Seite. Die Netzschritte sind noch der
Code der Arbeit; Phase 3 ersetzt sie durch gecachte, wiederaufnehmbare Abrufe.

## Pipeline

| Schritt | liest | schreibt |
|---|---|---|
| `voters` | `external/Stimmbezirk_Wahlergebnis.csv` | `processed/wahlbezirke_waehler.parquet` |
| `streets` | `raw/streets_per_district.json` | `processed/wahlbezirke_strassen.parquet` |
| `pois` | `raw/wikipedia_dict.json` | `processed/wikidata_vis.parquet`, `wikidata_agg.parquet` |
| `dictionary` | Orte und Straßen je Wahlbezirk | `processed/combined_searchdict.parquet` |
| `corpus` | `interim/paper_with_text.json` | `interim/papers.parquet` |
| `index` | Wörterbuch, Korpus | `processed/inverted_index.parquet` |
| `results` | Wörterbuch, Index, Wähler | `processed/wahlbezirke_auswertung.parquet` |

Neben jeder Ausgabe liegt ein Stamp mit den Hashes der Eingaben, dem Fingerprint der Settings, der
Code-Version und der Schema-Version des Schritts. Ändert sich eines davon, läuft der Schritt und alles
dahinter neu; sonst wird er übersprungen und sagt das. Alle Schreibvorgänge sind atomar, ein leeres
Ergebnis wird nicht geschrieben, und unter `reference/` schreibt nichts.

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

- Prüfungen: `uv run nox` lokal und in CI (`.github/workflows/ci.yml`) rufen dieselben Sessions; `uv run pytest -m slow` läuft die Kette über die volle Referenz und vergleicht mit den Ergebnissen der Arbeit.
- Vor dem Commit: `uvx pre-commit install` einmalig; die Hooks formatieren und linten mit Ruff.
- Regeln für Commits und für Agenten: [CLAUDE.md](CLAUDE.md). Befund vor dem Umbau: [docs/baseline-2026-10-10.md](docs/baseline-2026-10-10.md).
- Struktur: `src/georep/` ist das Paket (`settings`, `layout`, `io`, `http`, `oparl`, `errors`, `bootstrap`, `pipeline`, `cli`, `export`, `prep/`, `search/`, `analysis/`); `src/*.py` ist der verbliebene Code der Arbeit für die Netzschritte; `tests/` mit `unit/`, `golden/` und `fixtures/`.

## Lizenz

CC0 1.0, wie das Original.
