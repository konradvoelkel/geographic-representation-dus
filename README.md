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
uv run georep run                       # fünfzehn Offline-Schritte, rund 16 s; schreibt auch die Berichtsseite data/site/index.html
uv run georep regress --exclude 1 10    # Tabelle 5 der Arbeit
uv run georep regress --controls        # Tabelle 6 mit den Kontrollvariablen
```

Geprüft am 2026-10-11 aus einem frischen Klon, die Kontrollvariablen am 2026-10-12. Wer die Umgebung woanders ablegen will, setzt vor `uv sync`
`UV_PROJECT_ENVIRONMENT` und `UV_CACHE_DIR`; wer Daten und Cache woanders haben will, schreibt `data_root`
und `cache_root` in eine `settings.local.toml` (siehe Konfiguration).

## Berichtsseite

`georep run` endet mit dem Schritt `report`: `data/site/index.html` ist eine in sich geschlossene Seite (rund
990 KB, kein externes JavaScript, keine Kartenkacheln, offline aus dem Dateisystem zu öffnen) mit Kernzahlen,
einem Suchfeld für Straßen und Orte (4176 Einträge in der Seite, darum ohne Netz: die Auswahl nennt Art,
Wahlbezirke und Dokumente und markiert sie auf der Karte; `index.html#suche=hofgarten` ist teilbar),
der Karte der 41 Wahlbezirke (Trefferquote oder Wahlbeteiligung, Tooltips, Klick-Markierung, die 1309 Orte als
Punkte), dem Streudiagramm mit beiden Regressionsgeraden und Tabelle 5, einer sortierbaren Tabelle je
Wahlbezirk, den Begriffen (ein Klick zeigt die Dokumente mit Datum, Drucksache und PDF-Link), den
Dokumenten je Monat, Methode und
Grenzen, Lizenzen. Der Abschnitt „Was ändert die Gewichtung?" stellt der binären Trefferquote 26 gewichtete
Varianten zur Seite (Spezifität je Begriff, Gewicht je Dokumentart, ein Thema je Zeile) und zeigt Tabelle 5
unter jeder davon; mit Einheitsgewichten steht dort dieselbe Zeile wie oben. `data/site/karte.html` zeigt dieselben Flächen und Orte auf OpenStreetMap-Kacheln (Leaflet,
braucht Netz). Daneben liegen unter `data/site/data/` die Ergebnisse zum Weiterverarbeiten: die
sechzehn Ergebnistabellen als Parquet und CSV, `wahlbezirke.geojson` (EPSG:4326), `schema.json` mit dem Spaltenschema
810 KB, kein externes JavaScript, keine Kartenkacheln, offline aus dem Dateisystem zu öffnen) mit Kernzahlen,
der Karte der 41 Wahlbezirke (Trefferquote oder Wahlbeteiligung, Tooltips, Klick-Markierung, die 1309 Orte als
Punkte), dem Streudiagramm mit beiden Regressionsgeraden und Tabelle 5, einer sortierbaren Tabelle je
Wahlbezirk, dem Abschnitt „Urheber und Parteien" (sechs kleine Karten je Partei, Tabelle je Partei mit dem
Abgleich zum Stimmenanteil, Tabelle je Wahlbezirk mit den Urheberklassen), den Begriffen (ein Klick zeigt die
Dokumente mit Datum, Drucksache, Urheber und PDF-Link), Methode und Grenzen, Lizenzen. `data/site/karte.html` zeigt dieselben Flächen und Orte auf OpenStreetMap-Kacheln (Leaflet,
braucht Netz). Daneben liegen unter `data/site/data/` die Ergebnisse zum Weiterverarbeiten: die neun
Ergebnistabellen als Parquet und CSV, `wahlbezirke.geojson` (EPSG:4326), `schema.json` mit dem Spaltenschema
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
| `georep fetch [SCHRITT …] [--force] [--limit N] [--max-pages N]` | die Netzschritte `opendata`, `context_data`, `papers`, `organizations`, `pdfs`, `streets_osm`, `pois_wiki`, danach `shapes` und `texts`; `--limit` begrenzt neue PDF-Downloads, `--max-pages` die Metadatenseiten |
| `georep steps` | Schritte mit Eingaben und Ausgaben |
| `georep status` | Settings, Pfade, Stores, Frische jedes Schritts mit Grund |
| `georep profiles` | die Profile im Paket mit Stadt und amtlichem Gemeindeschlüssel |
| `georep publish [--out DIR]` | die Stadtseiten nach `data/site/` zusammentragen und `vergleich.html` bauen |
| `georep bootstrap [--force]` | den eingefrorenen Datensatz (`reference_root`) nach `data_root` übernehmen |
| `georep export` | die Parquet-Ergebnisse als CSV daneben schreiben |
| `georep regress [--exclude …] [--varianten]` | lineare Regression Trefferquote gegen Wahlbeteiligung; `--varianten` dieselbe Rechnung je Gewichtungsvariante aus `wahlbezirke_gewichtet.parquet` |
| `georep regress --controls` | Tabelle 6: dieselbe Regression mit Kontrollvariablen, je Modell und Stichprobe |
| `georep profile [SCHRITT …] [--top N] [--sort tottime]` | einen echten Schritt unter cProfile, `.prof` für snakeviz |

`--profile SLUG` wählt die Stadt (`georep profiles` listet sie; sonst gilt `GEOREP_PROFILE`, sonst
`default_profile` aus den Settings). `--settings DATEI` legt eine weitere TOML-Schicht über die
Konfiguration. Exit-Codes: 0 gut, 1 Domänenfehler
(eine Zeile auf stderr), 2 Bedienfehler. Jeder Schritt druckt, worauf er gewirkt hat, und warum er lief oder
nicht; ein Lauf ohne Änderung ist ein No-op.

Ein voller Abruf von Grund auf (`georep fetch` auf leerem `data_root`) dauert Stunden: der OParl-Server
brauchte am 2026-10-09 85 s pro Seite, die PDFs kommen seriell mit einer Sekunde Pause (Hochrechnung 2026-10-11:
5,8 h für 19 108 PDFs, 2,8 GB). Alles ist wiederaufnehmbar; ein zweiter `fetch` holt nur Geändertes.

### Der eine schnelle Netzschritt und die Probe auf die Urheberfelder

`organizations` ist der kurze Abruf: eine Seite mit 58 Fraktionen, Ausschüssen und
Bezirksvertretungen, am 2026-10-11 in 0,47 s. Daraus liest der Schritt `parties` die Abbildung von
Organisations-URL auf Parteikürzel, falls der Server eines Tages `originatorOrganization` füllt.

```bash
uv run georep fetch organizations         # eine Seite, Sekunden; schreibt raw/organizations.json
uv run georep fetch papers --max-pages 1  # Probe, rund 90 s: "1 Seiten, 200 Paper gesehen, …, davon N mit Urheberfeld"
uv run georep run                         # corpus bis report neu, rund 7 s
```

Ist `N` null, liefert der Server keine Urheber, und der Urheber kommt weiter aus `paperType`, Titel
und Textkopf (Stand 2026-10-09: null von 19 108). Nur wenn `N > 0` ist oder die `modified`-Zeitstempel
gebraucht werden, lohnt der volle Metadatenabruf:

```bash
uv run georep fetch papers --force        # rund 95 Seiten mit stop_when_older, je 85 s plus 1 s Pause: 2 bis 3 h.
                                          # Nicht seitenweise wiederaufnehmbar (ein Abbruch beginnt von vorn, der
                                          # HTTP-Cache hält Seiten eine Stunde; für einen zweiten Versuch
                                          # cache.oparl_pages_s erhöhen). Danach uv run georep run.
uv run georep status                      # pdfs steht danach auf "Settings geändert", solange max_pages im Stamp
                                          # steht: das ist richtig, nicht kaputt
```

## Zwei Wahlperioden

Eine Wahlperiode ist ein **Profil** im Paket, das mit `base` auf dem Profil seiner Stadt aufbaut. Ihre Daten
liegen getrennt unter `data_root/<profil>/`, ihre PDFs und Texte unter `cache_root/<profil>/`; der HTTP-Cache
bleibt geteilt. Im Paket liegen
[`profiles/duesseldorf-2014.toml`](src/georep/profiles/duesseldorf-2014.toml) für die Wahlperiode 2014 bis
2020 (Ratswahl 13.09.2020) und
[`profiles/duesseldorf-vergleich.toml`](src/georep/profiles/duesseldorf-vergleich.toml), das auf der
Hauptperiode den Vergleich beider Perioden einschaltet.

```bash
uv run georep --profile duesseldorf-2014 status      # Periode, Pfade, Frische jedes Schritts
uv run georep --profile duesseldorf-2014 bootstrap   # Eingaben aus snapshots/2014-2020/
uv run georep --profile duesseldorf-2014 run         # Kette der alten Periode, Seite unter data/2014-2020/site/
uv run georep --profile duesseldorf-vergleich run    # Hauptperiode mit dem Abschnitt „Zwei Wahlperioden"
```

Beide Perioden werden mit **demselben Wörterbuch** durchsucht (Straßen und Orte je Wahlbezirk 2025, Stand
November 2025): `period.dictionary = "base"` liest die Rohdaten der Hauptperiode, die Netzschritte
`streets_osm` und `pois_wiki` gibt es im Profil darum nicht. So unterscheiden sich die Perioden nur in den
Dokumenten, und keine Trefferquote muss zwischen zwei Zuschnitten umgerechnet werden.

Die Wahlbeteiligung der Ratswahl 2020 liegt dagegen auf den **316 Stimmbezirken von 2020**, die Auswertung auf
den **41 Wahlbezirken von 2025**. Der Schritt `precincts` rechnet um: Flächenanteile der Stimmbezirke an den
Zielbezirken, Zählgrößen (Wahlberechtigte, Wähler, Stimmen) proportional übertragen und je Zielbezirk nach
größtem Rest ganzzahlig gerundet, sodass die Stadtsumme exakt erhalten bleibt. Die 44,6 % Briefwähler von 2020
haben keine Geometrie; sie werden je Wahlbezirk aus der Differenz zur Wahlbezirks-CSV erschlossen und
proportional zu den Wahlberechtigten mit Wahlschein auf die Stimmbezirke verteilt. Die Zuordnung steht als
`stimmbezirke_zuordnung.parquet` zum Download und macht beides nachrechenbar.

### Zweite Periode abrufen

Der Abruf der alten Periode ist ein eigener, von Hand zu startender Lauf (geschätzt 25 000 bis 30 000
Dokumente, 3,7 bis 4,4 GB PDFs, zehn bis vierzehn Stunden); kein Agent und keine CI startet ihn.

```bash
export UV_PROJECT_ENVIRONMENT=… UV_CACHE_DIR=…               # wie in FORK-NOTES.md
P="--profile duesseldorf-2014"
uv run georep $P fetch opendata        # vier Portaldateien, Sekunden
uv run georep $P fetch papers          # rund 3 h; speichert jede Seite, wiederaufnehmbar
uv run georep $P fetch pdfs --limit 50 # Stichprobe zuerst, dann ohne --limit: 8 bis 11 h
uv run georep $P run                   # Extraktion rund 17 min, der Rest Sekunden
uv run georep $P status                # alles aktuell?
```

- **Wiederaufnahme.** `fetch papers` speichert nach jeder Seite in den Store und schreibt die nächste URL nach
  `data_root/2014-2020/raw/papers.progress.json`. Bricht der Lauf ab, macht der nächste dort weiter, nicht bei
  `sources.oparl.first_page`. Die Datei verschwindet, sobald ein Abruf durchgelaufen ist; wer von vorn
  beginnen will, löscht sie — auch `--force` tut das nicht, denn es umgeht den Stamp, nicht den Netz-Cursor,
  und ein zweiter Durchlauf derselben Seiten schreibt dieselben Paper. `fetch pdfs` ist je Datei
  wiederaufnehmbar.
- **`first_page = 90`** überspringt die Seiten der Hauptperiode (die Liste ist neueste zuerst, Stand 2026-10
  tragen die Seiten 1 bis 95 die Periode 2020 bis 2025). Jedes neue Paper schiebt die alten Seiten nach
  hinten; der Netztest
  [`tests/golden/test_network_period.py`](tests/golden/test_network_period.py) (`uv run pytest -m network`)
  prüft, dass Seite 90 noch vor dem Wahltag liegt.
- **`incremental = false`** ist Absicht: `modified` ist bei alten Papern das Migrationsdatum 2024-12-30, ein
  `modified_since` holte nach dem ersten Lauf nichts mehr.
- **Platz.** Die PDFs liegen unter `cache_root/2014-2020/pdf/`; xtraspace hatte am 2026-10-11 322 GB frei.
- **Danach** entsteht aus `raw/papers.jsonl`, `cache/text/<profil>/texts.parquet` und `external/` der
  eingefrorene Schnappschuss `snapshots/2014-2020/` (geschätzt 35 bis 40 MB), auf den `reference_root` des
  Profils zeigt; `bootstrap` erkennt dieses Format und kopiert nur. Erst damit baut GitHub Pages beide
  Perioden ohne Netz.

## Laufende Wahlperiode

Neben der Periode der Arbeit (2020 bis 2025) gibt es ein zweites Profil für die Wahlperiode seit der
Kommunalwahl am 14.09.2025: [`settings.2025.toml`](settings.2025.toml). Es legt Daten unter `data/2025/`,
PDFs und Texte unter `<cache_root>/2025/`, holt je Lauf nur Geändertes und baut eine eigene Seite ohne
Regression (zu einer laufenden Periode gibt es keine Wahlbeteiligung), dafür mit der Monatsreihe.

```bash
uv run georep --settings settings.2025.toml bootstrap   # nur die vier Eingaben, kein Korpus der Arbeit
uv run georep --settings settings.2025.toml fetch papers --force   # eine OParl-Seite, rund 45 s
uv run georep --settings settings.2025.toml run         # Kette und Seite unter data/2025/site/
```

Im Betrieb macht das ein Skript hinter einem systemd-Timer: `deploy/bin/georep-monitor.sh` holt, rechnet,
stellt beide Seiten zusammen (Hauptseite und darunter `2025/`), sichert PDFs und Texte optional in ein
privates R2-Bucket und überträgt das Ergebnis per `rsync` auf einen Server. Alles Rechnerspezifische steht
in einer Umgebungsdatei, nichts im Code; Installation, Trockenlauf und der einmalige Erstabruf stehen in
[deploy/README.md](deploy/README.md).

## Konfiguration

Die stadtneutralen Parameter stehen mit Begründung in
[`src/georep/defaults.toml`](src/georep/defaults.toml), alles Stadtspezifische (Endpunkte, Spaltennamen,
Ausschlussliste, Quellen mit Lizenz) in genau einer Datei je Stadt unter
[`src/georep/profiles/`](src/georep/profiles/). Darüber mischen sich tief `./settings.toml` und
`./settings.local.toml` (gitignored, rechnerspezifisch), darüber `--settings`, darüber Umgebungsvariablen
`GEOREP_<FELD>`, verschachtelt mit `__`. Unbekannte Schlüssel sind
ein Fehler. `contracts = "off"` schaltet die deal-Verträge ab (Programmierfehler-Prüfungen an den
Batch-Grenzen, Overhead unter einem Prozent).

```toml
# settings.local.toml: Daten und Cache auf einer anderen Platte
data_root = "/media/konrad/xtraspace/georep/data"
cache_root = "/media/konrad/xtraspace/georep/cache"
```

## Mehrere Städte

Dieselbe Kette rechnet jede Kommune, deren Profil im Paket liegt; der Code kennt keine Stadt. Heute sind
das Düsseldorf (Standard, flach unter `data/`) und Mönchengladbach (`data/moenchengladbach/`).

```bash
uv run georep profiles                                   # welche Städte es gibt
uv run georep --profile moenchengladbach status          # Pfade und Frische dieser Stadt
uv run georep --profile moenchengladbach fetch opendata  # Sekunden; der Rest dauert Stunden
uv run georep publish                                    # data/site/ mit allen Städten und vergleich.html
```

Der volle Abruf einer weiteren Stadt ist ein Handgriff mit Prüfpunkten:
[`docs/runbook-stadt.md`](docs/runbook-stadt.md). Bis er gelaufen ist, meldet `georep publish` die Stadt als
„kein Lauf“ und baut die Vergleichsseite nicht.

## Daten und Herkunft

| Daten | Quelle | im Repo |
|---|---|---|
| Wahlergebnis je Stimmbezirk, Kommunalwahl 14.09.2025 | Open-Data-Portal der Stadt Düsseldorf (CSV, Datenlizenz Deutschland Namensnennung 2.0) | `reference/external/` |
| Stimmbezirke 2025 (ETRS89, EPSG:4647) | Open-Data-Portal der Stadt Düsseldorf (GeoJSON, Datenlizenz Deutschland – Zero – Version 2.0) | `reference/external/` |
| Ratsdokumente 2020 bis 2025, Metadaten und Texte | Ratsinformationssystem Düsseldorf über OParl 1.1 (`ris-oparl.itk-rheinland.de`, Body 0015) | `reference/interim/`, die PDFs nicht |
| Straßennamen je Stimmbezirk | OpenStreetMap über die Overpass-API (ODbL), Stand der Arbeit November 2025 | `reference/raw/` |
| Orte je Stimmbezirk | Wikidata (CC0) per SPARQL, Wikipedia-GeoSearch | `reference/raw/` |
| Kürzel und Namen der Gremien (Rat, Bezirksvertretungen, Ausschüsse, Beiräte) | Organisationsliste des Ratsinformationssystems (Stand 11.10.2026) und Dokumenttitel; das Gremium je Dokument liest der Parser aus der Drucksachennummer | `src/georep/profiles/duesseldorf.toml`, Block `[bodies]` |
| Sozialdaten je Sozialraum, Stand 31.12.2021 (Kontrollvariablen) | Quartiersatlas Düsseldorf 2024, Open-Data-Portal der Stadt Düsseldorf (CSV und GeoJSON, Datenlizenz Deutschland Namensnennung 2.0) | `context/` |
| Fraktionen, Ausschüsse und Bezirksvertretungen | Ratsinformationssystem Düsseldorf über OParl 1.1, Endpunkt `organizations` | nein, `georep fetch organizations` holt sie |
| Wahlergebnis je Stimmbezirk und je Wahlbezirk, Ratswahl 13.09.2020 | Open-Data-Portal der Stadt Düsseldorf (CSV, Datenlizenz Deutschland Namensnennung 2.0) | nein, Abruf über `--profile duesseldorf-2014` |
| Stimmbezirke und Kommunalwahlbezirke 2020 (ETRS89, EPSG:4647) | Open-Data-Portal der Stadt Düsseldorf (GeoJSON, Datenlizenz Deutschland – Zero – Version 2.0) | nein, Abruf über `--profile duesseldorf-2014` |
| Ratsdokumente 2014 bis 2020 | Ratsinformationssystem Düsseldorf über OParl 1.1, Body 0015, ab Seite 90 | noch nicht; nach Konrads Lauf als `snapshots/2014-2020/` |
| Mönchengladbach: Wahlergebnis, Wahlbezirke, Straßenverzeichnis | votemanager der ITK Rheinland (`wep.itk-rheinland.de`, Lizenz laut Anbieter nicht angegeben) | Stichprobe in `tests/fixtures/mg/` |
| Mönchengladbach: Stimmbezirksflächen (Stand 08.06.2022) | Geoportal der Stadt Mönchengladbach (Shapefile, Datenlizenz Deutschland – Zero – Version 2.0) | Stichprobe in `tests/fixtures/mg/` |

`context/` trägt die Fremddaten, aus denen die Kontrollvariablen entstehen, mit Herkunft, Lizenz, Datenstand,
Abrufdatum und Prüfsummen in [context/README.md](context/README.md); die Seite nennt unter „Abgeleitete Daten"
je Variable, was daraus wurde. Namensnennung nach Lizenz: Landeshauptstadt Düsseldorf, Amt für Statistik und
Wahlen: Quartiersatlas Düsseldorf 2024 (Open-Data-Portal), dl-de/by-2-0.

`reference/` und `context/` werden nur gelesen; Läufe schreiben nach `data_root`
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
