# Geographic Representation DUS

Wie sichtbar sind die 41 Kommunalwahlbezirke Düsseldorfs in den Dokumenten des Stadtrats, und hängt das
mit der Wahlbeteiligung zusammen? Für jeden Wahlbezirk entsteht ein Wörterbuch aus Straßennamen
(OpenStreetMap) und Orten (Wikidata, Wikipedia); die 19 108 Ratsdokumente der Wahlperiode 2020 bis 2025
(OParl-Schnittstelle des Ratsinformationssystems) werden danach durchsucht; die Trefferquote je Bezirk wird
mit der Wahlbeteiligung der Kommunalwahl 2025 in Beziehung gesetzt.

Ursprung: Bachelorarbeit von Lukas Bartzsch, Heinrich-Heine-Universität Düsseldorf, Januar 2026
(<https://github.com/lubar102/geographic-representation-dus>). Dieser Fork hat den Code in sieben Phasen
umgebaut und reproduziert die Ergebnisse der Arbeit auf alle Stellen, solange die eigenen Methodikregeln
abgeschaltet sind. Seit dem 2026-10-12 sind zwei davon an: Orte, deren Name den Stadtnamen trägt
(„Stadtwerke Düsseldorf"), gelten als Einrichtung mit stadtweiter Bedeutung und fallen aus dem Wörterbuch,
und Begriffe mit auffällig hoher Dokumentzahl stehen auf der Seite als eigene Liste. Was das an den Zahlen
ändert, steht gemessen in [docs/methodik-review-2026-10.md](docs/methodik-review-2026-10.md); der Tag
`bartzsch-exakt` (`v0.11.0`) markiert den letzten Stand ohne Abweichung, und `search.city_facilities = false`
stellt ihn jederzeit wieder her. Aufbau: [docs/architecture.md](docs/architecture.md);
Gründe und verworfene Alternativen: [docs/decisions.md](docs/decisions.md); Stand und Bekanntes:
[STATUS.md](STATUS.md); Änderungen aus Nutzersicht: [CHANGELOG.md](CHANGELOG.md).

## Loslegen

Voraussetzung ist [uv](https://docs.astral.sh/uv/); Python 3.14 und alle Pakete kommen aus `uv.lock`,
Systemabhängigkeiten gibt es keine (alle Wheels sind vorgebaut).

```bash
git clone git@github.com:konradvoelkel/geographic-representation-dus.git
cd geographic-representation-dus
uv sync --locked                        # Umgebung aus dem Lockfile
uv run georep bootstrap                 # Datensatz der Arbeit nach ./data/duesseldorf/ übernehmen
uv run georep run                       # zwanzig Offline-Schritte, rund 23 s; schreibt auch die Berichtsseite data/duesseldorf/site/index.html
uv run georep publish                   # dieselbe Seite nach data/site/, der veröffentlichten Wurzel
uv run georep regress --exclude 1 10    # Tabelle 5 der Arbeit
uv run georep regress --controls        # Tabelle 6 mit den Kontrollvariablen
```

Geprüft am 2026-10-11 aus einem frischen Klon, die Kontrollvariablen am 2026-10-12, `bootstrap`, `run` und
`publish` nach dem Umzug in den Stadtordner am 2026-10-13, die ganze Kette aus den Datenpaketen am 2026-10-14.
Die Seite aus diesen zwei Befehlen trägt **einen** Link, der noch ins Leere zeigt: `2025/`, die Unterseite
der laufenden Wahlperiode (`report.monitoring_url` im Stadtprofil). Der Abschnitt „Zwei Wahlperioden" und
sein Link auf `2014-2020/` entstehen erst mit `georep --profile duesseldorf-vergleich run`, und die beiden
Unterseiten selbst mit den Läufen ihrer Profile — unten „Zwei Wahlperioden" und „Laufende Wahlperiode", in
CI `.github/workflows/pages.yml`. Wer die veröffentlichte Seite ganz nachbauen will, läuft die Blöcke dieses
Workflows der Reihe nach. Wer die Umgebung woanders ablegen will, setzt vor `uv sync`
`UV_PROJECT_ENVIRONMENT` und `UV_CACHE_DIR`; wer Daten und Cache woanders haben will, schreibt `data_root`
und `cache_root` in eine `settings.local.toml` (siehe Konfiguration).

## Berichtsseite

`georep run` endet mit dem Schritt `report`: `data/duesseldorf/site/index.html` ist eine in sich geschlossene Seite (rund
0,96 MB bei einem Budget von 1,0 MB, kein externes JavaScript, keine Kartenkacheln, offline aus dem
Dateisystem zu öffnen) mit Kernzahlen,
einem Suchfeld für Straßen und Orte (4176 Einträge in der Seite, darum ohne Netz: die Auswahl nennt Art,
Wahlbezirke und Dokumente und markiert sie auf der Karte; `index.html#suche=hofgarten` ist teilbar),
der Karte der 41 Wahlbezirke (sechs Einfärbungen zur Wahl: Trefferquote, Treffer absolut, Treffer je Begriff
im Wörterbuch, Abweichung vom Stadtmittel, Wahlbeteiligung, Anteil der eigenen Bezirksvertretung; Tooltips,
Klick-Markierung, die 1196 Orte als
Punkte), dem Streudiagramm mit beiden Regressionsgeraden und Tabelle 5 samt derselben Regression je Begriff
im Wörterbuch, einer sortierbaren Tabelle je
Wahlbezirk, dem Abschnitt „Urheber und Parteien" (sechs kleine Karten je Partei mit Umschalter auf die
Abweichung vom Mittel aller Parteien, Tabelle je Partei mit dem Abgleich zum Stimmenanteil, Tabelle je
Wahlbezirk mit den Urheberklassen), dem Abschnitt „Kontrollvariablen" (Tabelle 6 mit dem Quartiersatlas),
den Begriffen (ein Klick zeigt die Dokumente mit Datum, Drucksache, Urheber und PDF-Link), den
Dokumenten je Monat, Methode und
Grenzen, Lizenzen. Lange Tabellen zeigen Kopf und drei Zeilen und klappen über „alle *n* Zeilen zeigen"
auf (`report.table_preview_rows`; ohne JavaScript und im Druck steht alles offen, und eine Zeile, die
aus Karte, Diagramm oder Suche markiert wird, klappt von allein auf). Die Begriffslisten je Wahlbezirk
kommen beim Aufklappen aus `data/begriffe.json`, wie die Dokumente beim ersten Klick aus
`data/dokumente.json`; aus dem Dateisystem geöffnet sagt die Seite, dass der Browser das Nachladen
dort nicht erlaubt. Was die Seite wie groß macht und welche Posten bewusst liegen bleiben, steht
gemessen in [docs/seitengroesse-2026-10.md](docs/seitengroesse-2026-10.md). Der Abschnitt „Was ändert die Gewichtung?" stellt der binären Trefferquote 26 gewichtete
Varianten zur Seite (Spezifität je Begriff, Gewicht je Dokumentart, ein Thema je Zeile) und zeigt Tabelle 5
unter jeder davon; mit Einheitsgewichten steht dort dieselbe Zeile wie oben. Die Themen tragen die Namen
der Ausschüsse, aus deren Dokumenten sie gesät sind, und der Abschnitt „Gremien" nennt daneben, welcher
Ausschuss sachlich zu einem Dokument passt (`docs/themenmodell-2026-10.md`). `karte.html` daneben zeigt dieselben Flächen und Orte auf OpenStreetMap-Kacheln (Leaflet,
braucht Netz). Daneben liegen unter `site/data/` die Ergebnisse zum Weiterverarbeiten: die
dreiundzwanzig Ergebnistabellen als Parquet und CSV, `wahlbezirke.geojson` (EPSG:4326), `schema.json` mit dem Spaltenschema,
`dokumente.json` (Dokumente mit Treffer ohne Texte) und `begriffe.json` (Begriffe mit Treffer je
Wahlbezirk); Größe und SHA-256 jeder Datei stehen auf der Seite. Der Workflow
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
| `georep bootstrap [--force]` | den eingefrorenen Datensatz (`reference_root`) in den Ordner des Profils unter `data_root` übernehmen |
| `georep pack ZIEL [--force] [--consultations]` | die Gegenrichtung: aus dem gelaufenen Profil ein Datenpaket für das Repo schreiben (genau die Eingaben, ohne PDFs, Stamps und Caches), mit Prüfsummentabelle und README-Gerüst; bricht ab, wenn eine Eingabe fehlt oder der Textstore Zeilen trägt, die nicht aus einem Lauf kommen. `--consultations` packt stattdessen nur die Beratungsfolge je Dokument |
| `georep learn-bodies [--min-documents N]` | die Abbildung OParl-Organisation → Gremiumskürzel aus den Daten lernen und als `[bodies.organizations]` drucken, dazu den Katalog der Organisationen und die Gegenprobe mit der Tabelle im Profil; schreibt nichts |
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
und Textkopf. **Am 2026-10-14 ist der volle Metadatenabruf gelaufen und hat es bestätigt**: 122 Seiten,
24 400 Paper gesehen, 19 109 im Zeitraum, davon **null** mit Urheberfeld (36 min in eine eigene
Datenwurzel). Zwei Nebenbefunde: 18 708 der 19 109 tragen `consultation`, und `modified` ist überall
gefüllt und reicht bis zum 25.09.2026 — nur 1 200 Objekte tragen das Migrationsdatum 30.12.2024, für
diese Periode ist `modified_since` also brauchbar (anders als für 2014 bis 2020). Nur wenn `N > 0`
ist oder die `modified`-Zeitstempel gebraucht werden, lohnt der volle Metadatenabruf:

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
November 2025): `period.dictionary = "base"` liest die Rohdaten der Hauptperiode (sie liegt unter dem Slug
ihrer Stadt, `data_root/duesseldorf/`), die Netzschritte
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
- **Gelaufen am 2026-10-13**, Exit 0: 22 215 Dokumente, 22 116 PDFs (26 fehlgeschlagen), 21 838 mit Text,
  36 324 Treffer über die 41 Wahlbezirke, 77 Monate. Daraus entstand der eingefrorene Schnappschuss
  [`snapshots/2014-2020/`](snapshots/2014-2020/README.md) (36,1 MiB: `raw/papers.jsonl`,
  `cache/text/texts.parquet`, `external/`), auf den `reference_root` des Profils zeigt; `bootstrap` erkennt
  dieses Format und kopiert nur. Damit baut GitHub Pages beide Perioden ohne Netz. Wer den Abruf wiederholt,
  packt den Schnappschuss mit einem Befehl neu:
  `uv run georep --profile duesseldorf-2014 pack snapshots/2014-2020 --force` (`georep pack` ist die
  Gegenrichtung von `bootstrap` und verweigert alles, was nicht aus dem Lauf kommt; `docs/runbook-stadt.md`,
  § 5).

## Laufende Wahlperiode

Neben der Periode der Arbeit (2020 bis 2025) gibt es ein zweites Profil für die Wahlperiode seit der
Kommunalwahl am 14.09.2025: das Paketprofil
[`duesseldorf-2025`](src/georep/profiles/duesseldorf-2025.toml). Es legt Daten unter `data/2025/`,
PDFs und Texte unter `<cache_root>/2025/`, holt je Lauf nur Geändertes und baut eine eigene Seite ohne
Regression (zu einer laufenden Periode gibt es keine Wahlbeteiligung), dafür mit der Monatsreihe.
Straßen und Orte liest es bei der Hauptperiode (`period.dictionary = "base"`, also unter deren Slug
`data/duesseldorf/`), damit sich nur die Dokumente unterscheiden; darum will es die Hauptperiode zuerst
gebootstrappt haben.

```bash
uv run georep bootstrap                                      # die Hauptperiode: Straßen und Orte
uv run georep --profile duesseldorf-2025 bootstrap           # die Eingaben aus snapshots/2025/
uv run georep --profile duesseldorf-2025 run                 # Kette und Seite unter data/2025/site/
uv run georep --profile duesseldorf-2025 fetch papers --force  # erst mit Netz: eine OParl-Seite, rund 45 s
```

Seine Referenz ist der eingefrorene Erstabruf
[`snapshots/2025/`](snapshots/2025/README.md) (13,2 MiB, 2026-10-13: 4 095 Dokumente, 4 088 PDFs, 4 075 mit
Text, 5 448 Treffer, 14 Monate). `bootstrap` füllt daraus Metadaten und Texte, **wenn der Store leer ist**;
wer die Periode fortschreibt, behält seinen Stand, und nur `bootstrap --force` setzt ihn auf den des Pakets
zurück. Damit baut GitHub Pages die Unterseite `2025/` ohne Netz, und die Hauptseite verlinkt sie
(`report.monitoring_url = "2025/"` im Stadtprofil). Der Schnappschuss veraltet mit jedem Lauf des Monitors —
das ist Absicht; die Seite nennt ihr Abrufdatum, und die aktuelle Fassung liefert der Timer.

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

Dieselbe Kette rechnet jede Kommune, deren Profil im Paket liegt; der Code kennt keine Stadt. Jede rechnet
unter ihrem Slug: heute Düsseldorf (Standard, `data/duesseldorf/`) und Mönchengladbach
(`data/moenchengladbach/`). `georep publish` legt die erste Stadt aus `publish.cities` an die Wurzel von
`data/site/` und jede weitere nach `data/site/<slug>/`; die veröffentlichte Adresse bleibt dadurch dieselbe,
obwohl der Lauf einen Ordner tiefer rechnet (decisions.md, Punkt 52).

```bash
uv run georep profiles                                   # welche Städte es gibt
uv run georep --profile moenchengladbach status          # Pfade und Frische dieser Stadt
uv run georep --profile moenchengladbach fetch opendata  # Sekunden; der Rest dauert Stunden
uv run georep publish                                    # data/site/ mit allen Städten und vergleich.html
```

Der volle Abruf einer weiteren Stadt ist ein Handgriff mit Prüfpunkten:
[`docs/runbook-stadt.md`](docs/runbook-stadt.md). Bis er gelaufen ist und sein Paket im Repo liegt, meldet
`georep publish` die Stadt als „kein Lauf“ und baut die Vergleichsseite nicht. Mönchengladbachs Lauf ist am
2026-10-13 gelaufen, sein Paket liegt unter
[`reference/moenchengladbach/`](reference/moenchengladbach/README.md): 2 895 Ratsdokumente, von denen das
Ratsinformationssystem nur **658** als PDF ausliefert (die übrigen antworten mit `404`), 1 704 Treffer über 33
Wahlbezirke. Die absoluten Zahlen der beiden Städte sind darum nicht vergleichbar, die Verteilungen schon:
`vergleich.html` führt dafür die Spalte „davon mit Text“ und sagt es im Abschnitt „Vergleichbarkeit“, und die
Kachel „Dokumente mit Treffer“ jeder Stadtseite nennt den Anteil an allen Dokumenten **und** den an denen
mit Text.

Was eine Stadt an Konfiguration mitbringen muss, zeigen die Urheber (Punkt 59): Düsseldorfs
Dokumentarten nennen die Fraktion („Anfrage SPD“), Mönchengladbachs nennen nur die Klasse
(`3 - Fraktionsantrag`). Darum stehen in `[originators]` neben `admin_types` und `citizen_types`
auch `fraction_types` und `person_types` — Dokumentarten, die die Klasse allein entscheiden; die
Partei kommt dann aus Titel und Briefkopf. Mönchengladbachs 16 Dokumentarten sind damit vollständig
zugeordnet (0 % „Urheber unbekannt“), und 242 der 581 Fraktionsanträge nennen ihre Partei.

## Daten und Herkunft

| Daten | Quelle | im Repo |
|---|---|---|
| Wahlergebnis je Stimmbezirk, Kommunalwahl 14.09.2025 | Open-Data-Portal der Stadt Düsseldorf (CSV, Datenlizenz Deutschland Namensnennung 2.0) | `reference/external/` |
| Stimmbezirke 2025 (ETRS89, EPSG:4647) | Open-Data-Portal der Stadt Düsseldorf (GeoJSON, Datenlizenz Deutschland – Zero – Version 2.0) | `reference/external/` |
| Ratsdokumente 2020 bis 2025, Metadaten und Texte | Ratsinformationssystem Düsseldorf über OParl 1.1 (`ris-oparl.itk-rheinland.de`, Body 0015) | `reference/interim/`, die PDFs nicht |
| Straßennamen je Stimmbezirk | OpenStreetMap über die Overpass-API (ODbL), Stand der Arbeit November 2025 | `reference/raw/` |
| Orte je Stimmbezirk | Wikidata (CC0) per SPARQL, Wikipedia-GeoSearch | `reference/raw/` |
| Kürzel und Namen der Gremien (Rat, Bezirksvertretungen, Ausschüsse, Beiräte) | Organisationsliste des Ratsinformationssystems (Stand 11.10.2026) und Dokumenttitel; das Gremium je Dokument liest der Parser aus der Drucksachennummer und, wo die nichts sagt, aus der Beratungsfolge | `src/georep/profiles/duesseldorf.toml`, Block `[bodies]` |
| Beratungsfolge je Dokument 2020 bis 2025 (welche Gremien es beraten haben, Vollabruf der Metadaten 2026-10-14) | Ratsinformationssystem Düsseldorf über OParl 1.1, Body 0015, Feld `consultation` | `snapshots/duesseldorf-beratungsfolge/` (88 KiB) |
| Mönchengladbach: Namen und Kürzel der Gremien (Abruf 2026-10-14) | Ratsinformationssystem Mönchengladbach über OParl 1.1, Body 0011, Endpunkt `organizations` | `reference/moenchengladbach/raw/organizations.json` |
| Mönchengladbach: Namen der acht Fraktionen und die Urheberklasse je Dokumentart | derselbe Abruf (`classification = "Fraktion"`) und die 16 `paperType`-Werte des Pakets | `src/georep/profiles/moenchengladbach.toml`, Block `[originators]` |
| Sozialdaten je Sozialraum, Stand 31.12.2021 (Kontrollvariablen) | Quartiersatlas Düsseldorf 2024, Open-Data-Portal der Stadt Düsseldorf (CSV und GeoJSON, Datenlizenz Deutschland Namensnennung 2.0) | `context/` |
| Fraktionen, Ausschüsse und Bezirksvertretungen | Ratsinformationssystem Düsseldorf über OParl 1.1, Endpunkt `organizations` | nein, `georep fetch organizations` holt sie |
| Wahlergebnis je Stimmbezirk und je Wahlbezirk, Ratswahl 13.09.2020 | Open-Data-Portal der Stadt Düsseldorf (CSV, Datenlizenz Deutschland Namensnennung 2.0) | `snapshots/2014-2020/external/` |
| Stimmbezirke und Kommunalwahlbezirke 2020 (ETRS89, EPSG:4647) | Open-Data-Portal der Stadt Düsseldorf (GeoJSON, Datenlizenz Deutschland – Zero – Version 2.0) | `snapshots/2014-2020/external/` |
| Ratsdokumente 2014 bis 2020, Metadaten und Texte (Abruf 2026-10-13) | Ratsinformationssystem Düsseldorf über OParl 1.1, Body 0015, ab Seite 90 | `snapshots/2014-2020/` (36,1 MiB), die PDFs nicht |
| Mönchengladbach: Wahlergebnis, Wahlbezirke, Straßenverzeichnis | votemanager der ITK Rheinland (`wep.itk-rheinland.de`, Lizenz laut Anbieter nicht angegeben) | `reference/moenchengladbach/external/` |
| Mönchengladbach: Stimmbezirksflächen (Stand 08.06.2022) | Geoportal der Stadt Mönchengladbach (Shapefile, Datenlizenz Deutschland – Zero – Version 2.0) | `reference/moenchengladbach/external/` |
| Mönchengladbach: Ratsdokumente 2020 bis 2025, Metadaten und Texte (Abruf 2026-10-13) | Ratsinformationssystem Mönchengladbach über OParl 1.1, Body 0011 | `reference/moenchengladbach/` (4,2 MiB), die PDFs nicht |
| Ratsdokumente seit der Kommunalwahl 2025, Metadaten und Texte (Erstabruf 2026-10-13) | Ratsinformationssystem Düsseldorf über OParl 1.1, Body 0015, `modified_since` | `snapshots/2025/` (13,2 MiB), die PDFs nicht; veraltet mit jedem Lauf des Monitors |

`context/` trägt die Fremddaten, aus denen die Kontrollvariablen entstehen, mit Herkunft, Lizenz, Datenstand,
Abrufdatum und Prüfsummen in [context/README.md](context/README.md); die Seite nennt unter „Abgeleitete Daten"
je Variable, was daraus wurde. Namensnennung nach Lizenz: Landeshauptstadt Düsseldorf, Amt für Statistik und
Wahlen: Quartiersatlas Düsseldorf 2024 (Open-Data-Portal), dl-de/by-2-0.

**Die Datenpakete im Repo** sind die eingefrorenen Eingaben der Läufe, aus denen GitHub Pages jede Seite ohne
Netz baut (Konrads Entscheidung vom 2026-10-13, `docs/decisions.md`, Punkt 56): `reference/` (82 MiB, der
Datensatz der Arbeit), `reference/moenchengladbach/` (4,2 MiB), `snapshots/2014-2020/` (36,1 MiB),
`snapshots/2025/` (13,2 MiB), `snapshots/duesseldorf-beratungsfolge/` (88 KiB, nur die Beratungsfolge je
Dokument, Punkt 58) und `context/` (2,1 MiB). Jedes trägt ein README mit Herkunft, Lizenz, Abrufdatum, Zahlen und der SHA-256 jeder
Datei; `tests/unit/test_data_packages.py` hält diese Angaben gegen die Dateien und lässt keine PDFs, Stamps
oder Caches hinein. Die PDFs selbst liegen in **keinem** Paket, nur die Texte daraus.

**Was die Daten dieser vier Netzläufe zeigen**, steht mit Zahlen, Deutung und Grenze in
[docs/befunde-2026-10-14.md](docs/befunde-2026-10-14.md) (zwei Wahlperioden, zwei Städte, die laufende
Periode, die Beratungsfolge aus dem Vollabruf der Metadaten, Datenqualität); jede Zahl dort rechnet
`uv run python docs/befunde-2026-10-14-messung.py` aus den Parquet-Dateien und `summary.json` nach.

`reference/`, `snapshots/` und `context/` werden nur gelesen; Läufe schreiben nach `data_root/<profil>/`
(Standard `./data/duesseldorf`), Caches nach `cache_root/<profil>/` (Standard `data/cache/duesseldorf`), nur
`http.sqlite` liegt geteilt in `cache_root`. Abgeleitete Daten sind Parquet; `georep export` legt CSV daneben,
die Berichtsseite unter `data_root/<profil>/site/` bietet beides zum Download an, und `georep publish` trägt
die Stadtseiten nach `data_root/site/` zusammen — das ist der Ordner, den GitHub Pages hochlädt.

## Literatur

Woran dieses Vorhaben anschließt, mit vollständiger Zitation; dieselbe Liste steht auf der Berichtsseite im
Abschnitt „Literatur und verwandte Arbeiten“. Quelle der Einträge sind `src/georep/report/literatur.toml`
(stadtneutral) und `[[report.literature]]` im Profil der Stadt; `tests/unit/test_report_literature.py` hält
diese Liste und die Seite zusammen.

- **Lukas Bartzsch** — [Titel nachzutragen]. Heinrich-Heine-Universität Düsseldorf, Bachelorarbeit, 2026.
  <https://github.com/lubar102/geographic-representation-dus>, abgerufen am 13.10.2026.
  Der Ursprung dieser Seite: Fragestellung, Wörterbuch je Wahlbezirk, Suche über die Ratsdokumente und die
  Regression gegen die Wahlbeteiligung stammen aus dieser Arbeit, und dieses Programm ist ein Umbau ihres
  Quelltextes, der als Repositorium geographic-representation-dus öffentlich ist. Es reproduziert ihre
  Zahlen, solange die eigenen Methodikregeln abgeschaltet sind; Titel, Monat der Einreichung und Betreuung
  sind nachzutragen, denn die Arbeit selbst ist nicht öffentlich und ihr Repositorium nennt sie nicht.
- **Autor nachzutragen: Untersuchung zu Parteien und Stadtteilbezügen in den Ratsdokumenten der Stadt Köln**
  — [Angaben nachzutragen]. Herausgeber und Jahr nachzutragen aus dem Literaturverzeichnis der Arbeit.
  Die Arbeit zitiert eine Kölner Untersuchung zu Parteien und Ratsdokumenten; sie ist am 2026-10-13 nicht
  auffindbar. Gesucht wurde in OpenAlex und Crossref (Ratsinformationssystem, Ratsdokumente, Köln, Text
  Mining, geografische Repräsentation), auf arXiv, in Hochschulrepositorien und auf GitHub, und im
  öffentlichen Quelltext der Arbeit steht kein Literaturverzeichnis — die Zitation ist nur aus der Arbeit
  selbst zu holen. Die nächste belegte Verwandte ist Harmening u. a. 2025 weiter unten, die zwölf deutsche
  Großstädte mit demselben Verfahren untersucht.
- **Morten Harmening, Jona-Frederik Baumert, Sebastian Block, Martin Gross, Dominic Nyhuis, Jan Velimsky:
  Geographic representation in local politics: Evidence from parliamentary questions in German city
  councils**. European Journal of Political Research 64 (4), S. 1999–2017, Cambridge University Press, 2025.
  DOI [10.1111/1475-6765.70019](https://doi.org/10.1111/1475-6765.70019), abgerufen am 13.10.2026.
  Die methodisch nächste verwandte Arbeit: 10 189 Anfragen aus zwölf deutschen Großstädten, je eine
  Wahlperiode, mit einem Stadtteil-Wörterbuch aus Verwaltungsgrenzen, geolokalisierten Wikipedia-Markern und
  Straßennamen aus OpenStreetMap — derselbe Werkzeugkasten wie hier. Befund: Parteien bedienen in ihren
  Anfragen ihre Hochburgen, verstärkt bei räumlich konzentrierter Wählerschaft und bezirksbezogenem
  Wahlsystem; diese Seite prüft denselben Zusammenhang in einer Stadt über alle Dokumentarten statt über
  Anfragen in vielen Städten.
- **Dominic Nyhuis, Sebastian Block, Morten Harmening, Matthias Henneke: Geographic representation in
  parliamentary questions: the benefits of Wikipedia for automated analyses of legislative text**. The
  Journal of Legislative Studies 32 (3), S. 548–560, Taylor & Francis, 2025. DOI
  [10.1080/13572334.2025.2518633](https://doi.org/10.1080/13572334.2025.2518633), abgerufen am 13.10.2026.
  Genau die Frage, an der hier das Wörterbuch hängt: taugen geolokalisierte Wikipedia-Einträge als
  Ortsmarker, oder braucht es fallspezifische Stichwortlisten? Validiert für Deutschland, Frankreich und das
  Vereinigte Königreich; dieses Vorhaben benutzt denselben Weg (Wikidata und Wikipedia-GeoSearch plus
  Straßennamen) und misst in „Methode und Grenzen“, wie stark die Größe des Wörterbuchs die Trefferzahl
  treibt.
- **Thomas Zittel, Dominic Nyhuis, Markus Baumann: Geographic Representation in Party-Dominated
  Legislatures: A Quantitative Text Analysis of Parliamentary Questions in the German Bundestag**.
  Legislative Studies Quarterly 44 (4), S. 681–711, Wiley, 2019. DOI
  [10.1111/lsq.12238](https://doi.org/10.1111/lsq.12238), abgerufen am 13.10.2026.
  Der Ursprung dieses Ansatzes für Deutschland: Ortsbezüge in parlamentarischen Anfragen automatisiert
  zählen und als Maß für geografische Repräsentation lesen, trotz starker Fraktionsdisziplin. Dieses
  Vorhaben überträgt die Idee auf die kommunale Ebene, wo der Wahlbezirk kleiner und die Dokumentart
  vielfältiger ist.
- **Khaled Cherif: Ratsvorlagen-Korpus deutscher Kommunen: 43.127 Dokumente Long-Context-Verwaltungstext
  (Leipzig, Osnabrück, Dresden, Freiburg im Breisgau)**. Zenodo, CC BY 4.0, 2026. DOI
  [10.5281/zenodo.21767760](https://doi.org/10.5281/zenodo.21767760), abgerufen am 13.10.2026.
  Ein offenes Volltextkorpus kommunaler Ratsvorlagen aus vier Städten (43 127 Dokumente, 303 Millionen
  Token), über OParl aus den öffentlichen Teilen der Ratsinformationssysteme gezogen, Stand 29.07.2026,
  veröffentlicht am 03.08.2026. Zeigt, dass ein zitierbarer Datensatz machbar ist; dieses Vorhaben
  veröffentlicht aus Lizenz- und Datenschutzgründen keine Texte, sondern nur abgeleitete Tabellen und
  Kennungen.
- **OParl (Kernteam: Stefan Graupner, Ernesto Ruge, Konstantin Schütze): OParl 1.1 — Spezifikation einer
  einheitlichen Schnittstelle zum Abruf von maschinenlesbaren Informationen aus Ratsinformationssystemen**.
  OParl, Spezifikationsprojekt der Open Knowledge Foundation Deutschland e. V. und der Vitako e. V., 2018.
  <https://dev.oparl.org/spezifikation>, abgerufen am 13.10.2026.
  Der Standard, über den diese Seite ihre Dokumente bekommt: eine einheitliche Schnittstelle auf die
  öffentlichen Teile kommunaler Ratsinformationssysteme, veröffentlicht zwei Jahre nach OParl 1.0. Dieses
  Vorhaben liest ausschließlich darüber und prüft jede Antwort gegen das Datenmodell der Spezifikation,
  statt das Ratsinformationssystem zu scrapen.
- **Open.NRW: 22 Kommunen sind mit OParl gestartet**. Open.NRW, Ministerium für Heimat, Kommunales, Bau und
  Digitalisierung des Landes Nordrhein-Westfalen, 2017. <https://open.nrw/Kommunen-OParl>, abgerufen am
  13.10.2026.
  Hält fest, wie der Standard in die Breite kam: Anfang Dezember 2017 starteten 22 von 27 beteiligten
  nordrhein-westfälischen Kommunen eine OParl-Schnittstelle, gefördert vom Land. Erst diese Verbreitung
  macht die Kette dieses Vorhabens auf eine andere Kommune übertragbar, ohne je Stadt einen eigenen Scraper
  zu schreiben.
- **Stadt Frechen, kommunale Datenverarbeitungszentrale Rhein-Erft-Rur: Transparenzportal für
  Gremiendaten**. interkommunales.nrw, Pilotprojekt „Kommunales Open Government in NRW“ des Landes
  Nordrhein-Westfalen, 2017. <https://interkommunales.nrw/projekt/transparenzportal-fuer-gremiendaten/>,
  abgerufen am 13.10.2026.
  Das interkommunale Transparenzportal für Gremiendaten, federführend die Stadt Frechen mit 24 Verwaltungen,
  nennt als Ausgabekanal das Portal „Politik bei uns“. Diese Seite geht den anderen Weg: sie liest einen
  OParl-Endpunkt selbst und liefert eine statische Auswertung aus, kein Portal.
- **Marian Steinbach: offeneskoeln. Software backend of offeneskoeln.de**. Eigenprojekt, Quelltext auf
  GitHub, 2012. <https://github.com/marians/offeneskoeln>, abgerufen am 13.10.2026.
  Der erste Nachweis, dass sich kommunale Ratsdokumente anders ansehen lassen als im Ratsinformationssystem:
  ein Portal, das Vorlagen nach Stichwort und nach Ort durchsuchbar machte. Dieses Vorhaben greift denselben
  Gedanken auf — Orte statt Gremien — und wertet ihn für eine Frage aus, nämlich welche Wahlbezirke in den
  Dokumenten vorkommen; das Portal selbst ist offline, zitiert ist sein Quelltext, der seit dem 07.01.2019
  archiviert ist.
- **Open Knowledge Foundation Deutschland e. V. (maßgeblich Ernesto Ruge): Politik bei uns**. Berlin, 2015.
  <https://politik-bei-uns.de/>, abgerufen am 13.10.2026.
  Die bundesweite Fortsetzung von Offenes Köln und OpenRuhr:RIS, laut der Projektseite des Portals Anfang
  2015 unter diesem Namen zusammengelegt: eine Oberfläche über die öffentlichen Teile kommunaler
  Ratsinformationssysteme, durchsuchbar nach Stichwort und nach Ort auf einer Karte. Der Blickwinkel ist
  derselbe wie hier; am Abrufdatum stand auf jeder Seite, dass das Portal nicht mehr betreut wird und die
  Daten eingefroren sind.
- **Ernesto Ruge u. a.: Politik bei uns 2. Quelltexte: Abruf-Daemon, Web-Frontend und OParl-Ausgabe**. Open
  Knowledge Foundation Deutschland e. V., Quelltexte auf GitHub, 2017. <https://github.com/politik-bei-uns>,
  abgerufen am 13.10.2026.
  Die Neuentwicklung des Portals, ab Ende 2017 über Open.NRW gefördert; die Repositories zeigen dieselben
  Schritte wie diese Kette — Abruf über OParl, Textextraktion, Georeferenzierung über OpenStreetMap — nur
  hinter Datenbank, Suchindex und Objektspeicher statt in Dateien. Der Daemon wurde zuletzt im März 2020
  angefasst, das Frontend im Januar 2023.
- **Ernesto Ruge: OpenData: bisschen Prototyp, und das war's dann?** binary butterfly (Blog), 2020.
  <https://binary-butterfly.de/artikel/opendata-bisschen-prototyp-und-das-wars-dann/>, abgerufen am
  13.10.2026.
  Der Beitrag vom 09.03.2020, auf den „Politik bei uns“ selbst verweist: er erklärt, warum das Projekt
  einschlief — ein erfolgreiches Portal weckt professionelle Erwartungen an Reaktionszeiten, die
  ehrenamtlich nicht einzuhalten sind, und Förderprogramme finanzieren Neues, nicht den Betrieb. Daran misst
  sich der Zuschnitt dieser Seite: sie ist statisch, entsteht in einem Lauf aus dem Repository und braucht
  keinen Dienst, der betreut werden muss.
- **meine-stadt-transparent (Projekt): meine-stadt-transparent. A website to bring municipal politics to
  citizens**. gefördert vom Prototype Fund, Quelltext auf GitHub, 2017.
  <https://github.com/meine-stadt-transparent/meine-stadt-transparent>, abgerufen am 13.10.2026.
  Die nächste Verwandte dieser Kette: ein freies Ratsinformationssystem für die Öffentlichkeit einer Kommune
  mit Import über OParl, Volltextsuche, Orten auf einer Karte und Abo-Mails je Suchbegriff. Der Unterschied
  liegt in der Betriebsform — eine Instanz je Stadt mit Datenbank und Suchindex gegen eine Auswertung je
  Stadt als eine Datei; das Projekt ist seit dem 25.11.2023 archiviert.
- **OParl: OParl-Validator. A validating OParl API client**. OParl, Quelltext auf GitHub (MIT), 2014.
  <https://github.com/OParl/validator>, abgerufen am 13.10.2026.
  Prüft einen OParl-Server gegen die Spezifikation und macht damit sichtbar, wie verschieden die Server sie
  auslegen. Dieses Vorhaben validiert stattdessen beim Lesen: jede Antwort geht durch ein Datenmodell, und
  ein fehlendes oder falsch getyptes Feld ist ein Fehler an der Grenze, nicht später in der Rechnung. Der
  Quelltext wurde zuletzt im Dezember 2020 angefasst.

## Entwicklung

`uv run nox` (Ruff, mypy strict, Lockfile-Prüfung, Tests mit Abdeckung) lokal und in CI rufen dieselben
Sessions; `uv run pytest -m slow` läuft die Kette über die volle Referenz und vergleicht mit den Ergebnissen
der Arbeit; `nox -s bench`, `profile`, `verify` und `mutate` messen und prüfen von Hand. Test-Schichten,
Nähte für Ersatz-Matcher und -Extraktor und die nox-Sessions beschreibt [docs/architecture.md](docs/architecture.md);
Regeln für Commits und für Agenten stehen in [CLAUDE.md](CLAUDE.md). Vor dem Commit einmalig
`uvx pre-commit install`.

## Lizenz

Quelltext: GPL-3.0-or-later (`LICENSE`), seit dem 2026-10-12 nach dem Tag `v0.11.0`; bis dahin CC0 1.0 wie das
Original von Lukas Bartzsch, dessen CC0 die Weiterlizenzierung erlaubt. Ergebnisse, Tabellen und die
Berichtsseite: CC0 1.0. Daten je Quelle, siehe „Daten und Herkunft".
