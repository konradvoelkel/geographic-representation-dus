# Fork-Notizen

Lokaler Fork von <https://github.com/lubar102/geographic-representation-dus> (Lukas Bartzsch,
Bachelorarbeit HHU, Januar 2026, Lizenz CC0). Remotes: `upstream` = Original,
`origin` = GitHub-Fork <https://github.com/konradvoelkel/geographic-representation-dus>. Angelegt 2026-10-09.

## Umgebung

Seit 2026-10-10 ein uv-Projekt (`pyproject.toml`, `uv.lock`, Python 3.14). Die Projektumgebung
liegt auf der zweiten Platte, weil die Primärplatte voll ist:

```bash
export UV_PROJECT_ENVIRONMENT=/media/konrad/xtraspace/venvs/georep
export UV_CACHE_DIR=/media/konrad/xtraspace/uv-cache
uv sync
```

Ohne die beiden Variablen legt uv `.venv` im Repo an, das funktioniert ebenfalls. Alle Befehle
laufen als `uv run …`; die Prüfungen als `uv run nox` (Sessions: lint, typecheck, baseline, test, golden).
Die alte venv `/media/konrad/xtraspace/venvs/geographic-representation-dus` (Python 3.12, pip-Pins)
wird nicht mehr gebraucht und kann gelöscht werden.

## Pipeline (`run.py`) und was davon offline geht

| Schritt | Modul | Netz | Dauer | Ausgabe | im Repo? |
|---|---|---|---|---|---|
| 1 | `dataset_oparl` | ja | Stunden | `data/raw/paper_objects.json`, `data/raw/oparl_paper_pdf/` | Metadaten ja, PDFs nein |
| 2 | `dataset_opendata` | ja | Sekunden | `data/external/*.csv`, `*.geojson` | ja |
| 3 | `dataset_streets` | ja (OSM) | lang | `data/raw/streets_per_district.json` | ja |
| 4 | `dataset_wikidata` | ja | Minuten | `data/raw/wikipedia_dict.json` | ja |
| 5 | `prep_papers` | nein | Minuten | `data/interim/paper_with_text.json` (60 MB) | ja |
| 6 | `prep_voters`, `prep_wiki`, `prep_streets` | nein | Sekunden | `data/processed/wahlbezirke_*.csv`, `wikidata_*.csv` | ja |
| 7 | `combine_searchdicts`, `reverse_index`, `analyse` | nein | Sekunden | `combined_searchdict.csv`, `inverted_index.csv`, `wahlbezirke_auswertung.csv` | ja |
| 8 | `regression.ipynb` | nein | Sekunden | Plots, Kennzahlen | – |

Stand 2026-10-09 antwortet der OParl-Papers-Endpunkt mit rund 85 s pro Seite (200 Einträge,
365 Seiten für 2020–2025), also 8–9 h allein für die Metadaten; `requests.get` läuft dort ohne
Timeout. Neueste Einträge kommen zuerst, die Datumsfilterung (`START`/`ENDE`) passiert clientseitig.

**Achtung:** `prep_papers` ohne vorhandene PDFs überschreibt `paper_with_text.json` mit leeren
Texten. Nicht aufrufen, solange `data/raw/oparl_paper_pdf/` leer ist (Wiederherstellen mit
`git checkout -- data/interim/`).

Offline-Reproduktion ab Schritt 6 (schreibt in `data/processed/`, danach `git checkout -- data/`):

```bash
for m in prep_voters prep_wiki prep_streets combine_searchdicts reverse_index analyse; do uv run python -m src.$m; done
```

Ohne Schreiben ins Repo macht dasselbe der Test `uv run pytest -m slow` über `tests/legacy_runner.py`.

Stand 2026-10-09: Ergebnis identisch mit den committeten Dateien (Diff nur Zeilenreihenfolge in
`inverted_index.csv`). Notebook liefert Steigung 62,13, Achsenabschnitt 49,20, r = 0,1613,
p = 0,3138, R² = 0,0260, exakt Tabelle 5 der Arbeit (Modell mit allen 41 Wahlbezirken).

Korpus: 19108 Vorlagen/Anträge/Anfragen vom 2020-09-14 bis 2025-09-12, 19033 davon mit Text,
365 OParl-Seiten. Suchwörterbuch: 5841 Begriffe (OSM-Straßen + Wikipedia/Wikidata-POIs).

## Anpassungspunkte für andere Kommunen oder Fragestellungen

- `src/config.py` bündelt fast alles: `OPARL_ENDPOINT`, die beiden Open-Data-URLs, `START`/`ENDE`,
  `WIKI_EXCLUDE_LIST`, `DELAY`. Der ITK-Rheinland-OParl-Server bietet neben Düsseldorf (0015)
  auch Neuss (0009), Mönchengladbach (0011), Grevenbroich (0013) und Rhein-Kreis Neuss (0019).
- Falle: `TARGET_ENTITY` wird nirgends verwendet; `wd:Q1718` steht literal im SPARQL-String `QUERY`.
  Bei anderer Kommune beides ändern.
- GeoJSON-Spaltennamen sind hart kodiert in `dataset_streets.py` und `dataset_wikidata.py`:
  `"Stimm-/ Wahlbezirk"`, `"Kommunalwahlbezirk Nr."`, `"Kommunalwahlbezirk Name"`.
- Wahlergebnis-CSV: `prep_voters.py` erwartet `sep=';'`, `latin-1` und die Spalten
  `Kommunalwahlbezirk`, `Wahlberechtigte_insgesamt`, `Waehler`, `<Partei>_Stimmen`.
- `prep_papers.py` schneidet den Text vor dem ersten `betrifft` ab (Düsseldorfer Vorlagenkopf).
  Bei anderen Ratsinformationssystemen prüfen.
- `analyse.py` filtert `schulweg` nur aus der Anzeigeliste der Suchbegriffe, nicht aus der
  Trefferzählung (`paper_ids`). Generische Namen (Schulweg, Marktplatz, Hellweg, Kölner Straße)
  zählen also voll; vgl. Kapitel 4.3.5 der Arbeit.
- `dataset_oparl.download_paper_pdf`: das `try` umschließt die ganze Schleife, der erste
  fehlgeschlagene Download beendet alle weiteren. Vor einem Re-Download `try/except` in die
  Schleife ziehen.
- `dataset_opendata.get_wahlergebnis` schreibt `response.text` als latin-1; sicherer ist
  `response.content` binär zu schreiben.
