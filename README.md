# Geographic Representation DUS

Wie sichtbar sind die 41 Kommunalwahlbezirke Düsseldorfs in den Dokumenten des Stadtrats, und hängt das
mit der Wahlbeteiligung zusammen? Für jeden Wahlbezirk entsteht ein Wörterbuch aus Straßennamen
(OpenStreetMap) und Orten (Wikidata, Wikipedia); die 19 108 Ratsdokumente der Wahlperiode 2020 bis 2025
(OParl-Schnittstelle des Ratsinformationssystems) werden danach durchsucht; die Trefferquote je Bezirk wird
mit der Wahlbeteiligung der Kommunalwahl 2025 in Beziehung gesetzt.

Ursprung: Bachelorarbeit von Lukas Bartzsch, Heinrich-Heine-Universität Düsseldorf, Januar 2026
(<https://github.com/lubar102/geographic-representation-dus>). Dieser Fork hat den Code in sieben Phasen
umgebaut und reproduziert die Ergebnisse der Arbeit auf alle Stellen. Aufbau: [docs/architecture.md](docs/architecture.md);
Gründe und verworfene Alternativen: [docs/decisions.md](docs/decisions.md); Stand und Bekanntes:
[STATUS.md](STATUS.md); Änderungen aus Nutzersicht: [CHANGELOG.md](CHANGELOG.md).

## Loslegen

Voraussetzung ist [uv](https://docs.astral.sh/uv/); Python 3.14 und alle Pakete kommen aus `uv.lock`,
Systemabhängigkeiten gibt es keine (alle Wheels sind vorgebaut).

```bash
git clone git@github.com:konradvoelkel/geographic-representation-dus.git
cd geographic-representation-dus
uv sync --locked                        # Umgebung aus dem Lockfile
uv run georep bootstrap                 # Datensatz der Arbeit nach ./data übernehmen
uv run georep run                       # dreizehn Offline-Schritte, rund 16 s; schreibt auch die Berichtsseite data/site/index.html
uv run georep regress --exclude 1 10    # Tabelle 5 der Arbeit
```

Geprüft am 2026-10-11 aus einem frischen Klon. Wer die Umgebung woanders ablegen will, setzt vor `uv sync`
`UV_PROJECT_ENVIRONMENT` und `UV_CACHE_DIR`; wer Daten und Cache woanders haben will, schreibt `data_root`
und `cache_root` in eine `settings.local.toml` (siehe Konfiguration).

## Berichtsseite

`georep run` endet mit dem Schritt `report`: `data/site/index.html` ist eine in sich geschlossene Seite (rund
850 KB, kein externes JavaScript, keine Kartenkacheln, offline aus dem Dateisystem zu öffnen) mit Kernzahlen,
einem Suchfeld für Straßen und Orte (4176 Einträge in der Seite, darum ohne Netz: die Auswahl nennt Art,
Wahlbezirke und Dokumente und markiert sie auf der Karte; `index.html#suche=hofgarten` ist teilbar),
der Karte der 41 Wahlbezirke (Trefferquote oder Wahlbeteiligung, Tooltips, Klick-Markierung, die 1309 Orte als
Punkte), dem Streudiagramm mit beiden Regressionsgeraden und Tabelle 5, einer sortierbaren Tabelle je
Wahlbezirk, den Begriffen (ein Klick zeigt die Dokumente mit Datum, Drucksache und PDF-Link), Methode und
Grenzen, Lizenzen. Der Abschnitt „Was ändert die Gewichtung?" stellt der binären Trefferquote 26 gewichtete
Varianten zur Seite (Spezifität je Begriff, Gewicht je Dokumentart, ein Thema je Zeile) und zeigt Tabelle 5
unter jeder davon; mit Einheitsgewichten steht dort dieselbe Zeile wie oben. `data/site/karte.html` zeigt dieselben Flächen und Orte auf OpenStreetMap-Kacheln (Leaflet,
braucht Netz). Daneben liegen unter `data/site/data/` die Ergebnisse zum Weiterverarbeiten: die
zehn Ergebnistabellen als Parquet und CSV, `wahlbezirke.geojson` (EPSG:4326), `schema.json` mit dem Spaltenschema
und `dokumente.json` (Dokumente mit Treffer ohne Texte); Größe und SHA-256 jeder Datei stehen auf der Seite. Der Workflow
`.github/workflows/pages.yml` baut die Seite bei jedem Push auf `main` aus den Referenzdaten (`bootstrap`, `run`,
kein Netzabruf) und veröffentlicht sie über GitHub Pages unter
<https://konradvoelkel.github.io/geographic-representation-dus/> (Plan und Entscheidungen:
[docs/plan-report-2026-10.md](docs/plan-report-2026-10.md); Aufbau: [docs/architecture.md](docs/architecture.md),
Abschnitt „Berichtsseite").

## Befehle

| Befehl | Was er tut |
|---|---|
| `georep run [SCHRITT …] [--force] [--dry-run] [--online]` | führt die Schritte aus und überspringt, was aktuell ist; Netzschritte nur mit `--online` |
| `georep fetch [SCHRITT …] [--force] [--limit N]` | die Netzschritte `opendata`, `papers`, `pdfs`, `streets_osm`, `pois_wiki`, danach `texts`; `--limit` begrenzt neue PDF-Downloads |
| `georep steps` | Schritte mit Eingaben und Ausgaben |
| `georep status` | Settings, Pfade, Stores, Frische jedes Schritts mit Grund |
| `georep bootstrap [--force]` | den Datensatz der Arbeit nach `data_root` übernehmen |
| `georep export` | die Parquet-Ergebnisse als CSV daneben schreiben |
| `georep regress [--exclude …] [--varianten]` | lineare Regression Trefferquote gegen Wahlbeteiligung; `--varianten` dieselbe Rechnung je Gewichtungsvariante aus `wahlbezirke_gewichtet.parquet` |
| `georep profile [SCHRITT …] [--top N] [--sort tottime]` | einen echten Schritt unter cProfile, `.prof` für snakeviz |

`--settings DATEI` legt eine weitere TOML-Schicht über die Konfiguration. Exit-Codes: 0 gut, 1 Domänenfehler
(eine Zeile auf stderr), 2 Bedienfehler. Jeder Schritt druckt, worauf er gewirkt hat, und warum er lief oder
nicht; ein Lauf ohne Änderung ist ein No-op.

Ein voller Abruf von Grund auf (`georep fetch` auf leerem `data_root`) dauert Stunden: der OParl-Server
brauchte am 2026-10-09 85 s pro Seite, die PDFs kommen seriell mit einer Sekunde Pause (Hochrechnung 2026-10-11:
5,8 h für 19 108 PDFs, 2,8 GB). Alles ist wiederaufnehmbar; ein zweiter `fetch` holt nur Geändertes.

## Konfiguration

Alle Parameter stehen mit Begründung in [`src/georep/defaults.toml`](src/georep/defaults.toml). Darüber
mischen sich tief `./settings.toml` und `./settings.local.toml` (gitignored, rechnerspezifisch), darüber
`--settings`, darüber Umgebungsvariablen `GEOREP_<FELD>`, verschachtelt mit `__`. Unbekannte Schlüssel sind
ein Fehler. `contracts = "off"` schaltet die deal-Verträge ab (Programmierfehler-Prüfungen an den
Batch-Grenzen, Overhead unter einem Prozent).

```toml
# settings.local.toml: Daten und Cache auf einer anderen Platte
data_root = "/media/konrad/xtraspace/georep/data"
cache_root = "/media/konrad/xtraspace/georep/cache"
```

## Daten und Herkunft

| Daten | Quelle | im Repo |
|---|---|---|
| Wahlergebnis je Stimmbezirk, Kommunalwahl 14.09.2025 | Open-Data-Portal der Stadt Düsseldorf (CSV, Datenlizenz Deutschland Namensnennung 2.0) | `reference/external/` |
| Stimmbezirke 2025 (ETRS89, EPSG:4647) | Open-Data-Portal der Stadt Düsseldorf (GeoJSON, Datenlizenz Deutschland – Zero – Version 2.0) | `reference/external/` |
| Ratsdokumente 2020 bis 2025, Metadaten und Texte | Ratsinformationssystem Düsseldorf über OParl 1.1 (`ris-oparl.itk-rheinland.de`, Body 0015) | `reference/interim/`, die PDFs nicht |
| Straßennamen je Stimmbezirk | OpenStreetMap über die Overpass-API (ODbL), Stand der Arbeit November 2025 | `reference/raw/` |
| Orte je Stimmbezirk | Wikidata (CC0) per SPARQL, Wikipedia-GeoSearch | `reference/raw/` |
| Kürzel und Namen der Gremien (Rat, Bezirksvertretungen, Ausschüsse, Beiräte) | Organisationsliste des Ratsinformationssystems (Stand 11.10.2026) und Dokumenttitel; das Gremium je Dokument liest der Parser aus der Drucksachennummer | `src/georep/defaults.toml`, Block `[bodies]` |

`reference/` ist der eingefrorene Datensatz der Arbeit und wird nur gelesen; Läufe schreiben nach `data_root`
(Standard `./data`), Caches nach `cache_root` (Standard `data_root/cache`). Abgeleitete Daten sind Parquet;
`georep export` legt CSV daneben, die Berichtsseite unter `data_root/site/` bietet beides zum Download an.

## Entwicklung

`uv run nox` (Ruff, mypy strict, Lockfile-Prüfung, Tests mit Abdeckung) lokal und in CI rufen dieselben
Sessions; `uv run pytest -m slow` läuft die Kette über die volle Referenz und vergleicht mit den Ergebnissen
der Arbeit; `nox -s bench`, `profile`, `verify` und `mutate` messen und prüfen von Hand. Test-Schichten,
Nähte für Ersatz-Matcher und -Extraktor und die nox-Sessions beschreibt [docs/architecture.md](docs/architecture.md);
Regeln für Commits und für Agenten stehen in [CLAUDE.md](CLAUDE.md). Vor dem Commit einmalig
`uvx pre-commit install`.

## Lizenz

CC0 1.0, wie das Original.
