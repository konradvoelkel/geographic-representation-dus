# Technik: Schnittstellen, Daten, Kette, Veröffentlichung

Stand 2026-10-14, `v0.13.0`. Die veröffentlichte Seite ist aus Commit `813827e` gebaut und zeigt
alles bis **Punkt 58** (die Beratungsfolge als zweite Quelle des Gremiums); die **Punkte 59 bis 61**
(Urheber Mönchengladbachs, Urheber der Periode 2014 bis 2020, die Spalte „explorativ") liegen seit
dem 2026-10-14 auf `main` und sind in der veröffentlichten Seite noch nicht zu sehen — wo eine
Angabe unten davon betroffen ist, steht es dabei. Diese Sicht beantwortet: **womit spricht das Programm, was liegt wo, wie
läuft es, wie kommt es ins Netz.** Sie beschreibt nicht, wie der Code gebaut ist (das ist
[architecture.md](architecture.md)) und nicht, warum er so gebaut ist (das ist
[decisions.md](decisions.md)). Die drei anderen Sichten: [inhalt.md](inhalt.md) (was es gibt und was
die Seite kann), [statistik.md](statistik.md) (die Auswertungen),
[workflow-ratsmitglied.md](workflow-ratsmitglied.md) (ein Arbeitsablauf).

## 1. Schnittstellen und Datenplattformen

Alle Quellen sind öffentlich lesbar, keine braucht Zugangsdaten. Gezählt nach **Host** sind es
sieben (`ris-oparl.itk-rheinland.de`, `opendata.duesseldorf.de`, `wep.itk-rheinland.de`,
`geoportal.moenchengladbach.de`, `overpass-api.de`, `query.wikidata.org`, `de.wikipedia.org`); die
Tabelle führt sie je **Abruf** auf, weil derselbe Host mehrere Endpunkte mit verschiedenen Formaten
und Abrufregeln hat. Die Endpunkte stehen nie im Code, sondern im Profil der Stadt (`src/georep/profiles/<slug>.toml`) oder stadtneutral in
`src/georep/defaults.toml`.

| Quelle | Endpunkt | Format | Lizenz | woraus es wird |
|---|---|---|---|---|
| OParl 1.1, Ratsinformationssystem der ITK Rheinland (Düsseldorf, Body 0015) | `https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers` | JSON (OParl 1.1 `Paper`, `File`) | kein Lizenzhinweis am Endpunkt; die Seite nennt nur Kennungen | `raw/papers.jsonl` → Korpus, Gremien, Urheber, Themen |
| OParl 1.1, **Beratungsfolge** desselben Endpunkts (`consultation[].organization`) | wie oben; die Hauptperiode aus dem Vollabruf vom 2026-10-14 | JSON, im Repo als Parquet | wie oben | `raw/beratungsfolge.parquet` → zweite Quelle des Gremiums (Punkt 58) |
| OParl 1.1, Organisationen desselben Bodys | `…/bodies/0015/organizations` | JSON (OParl `Organization`) | wie oben | `raw/organizations.json` → Organisations-URL auf Parteikürzel |
| OParl 1.1, Hauptdateien (PDF) | `…/bodies/0015/downloadfiles/<datei>.pdf` | PDF | wie oben | `cache_root/<profil>/pdf/` → Textstore |
| OParl 1.1, Mönchengladbach (Body 0011) | `…/bodies/0011/papers` | JSON | wie oben | dieselbe Kette unter dem Slug `moenchengladbach` |
| OParl 1.1, Organisationen Mönchengladbachs | `…/bodies/0011/organizations` | JSON | wie oben | `raw/organizations.json` im Paket der Stadt → Namen und Kürzel ihrer 27 Gremien (Punkt 58) und die Namen ihrer acht Fraktionen (`classification = "Fraktion"`, Punkt 59) |
| Open-Data-Portal Düsseldorf, Wahlergebnis und Stimmbezirke | `https://opendata.duesseldorf.de/sites/default/files/…` | CSV (latin-1, `;`), GeoJSON in EPSG:4647 | Ergebnis dl-de/by-2-0, Geometrie dl-de/zero-2-0 | `external/` → Wähler, Zuschnitt |
| Open-Data-Portal Düsseldorf, Quartiersatlas 2024 | `…/Daten_QA_2024.csv`, `…Sozialräume_QA_Daten_WGS84_EPSG_4326.geojson`, `…Erläuterung_Indikatoren_QA_0.csv` | CSV (utf-8, `;`, Dezimalkomma), GeoJSON in CRS84 | dl-de/by-2-0 (Namensnennung: Landeshauptstadt Düsseldorf, Amt für Statistik und Wahlen) | `context/` → Kontrollvariablen je Wahlbezirk |
| votemanager der ITK Rheinland (Mönchengladbach, AGS 05116000) | `https://wep.itk-rheinland.de/vm/prod/kw_2025/05116000/daten/opendata/…csv` | CSV | **laut Anbieter nicht angegeben**; die Seite nennt Quelle und Herausgeber | Wahlergebnis je Stimm- und Wahlbezirk, amtliches Straßenverzeichnis |
| Geoportal Mönchengladbach | `…/K12_Politik_und_Wahlen/MapServer/identify?…&layers=all:16&maxAllowableOffset=0&f=json` (die ganze Anfrage steht im Profil) | Esri-JSON mit Ringen (`wkid` 25832), ein GET auf die Operation `identify` | dl-de/zero-2-0 | Stimmbezirksflächen, Aktualität Kommunalwahl 2025 (Punkt 65); bis zum 2026-10-14 das Shapefile-Zip `Wahlen_EPSG25832_SHAPE.zip` vom 08.06.2022 |
| Overpass-API / OpenStreetMap | `https://overpass-api.de/api/interpreter` (POST) | Overpass-JSON | ODbL, © OpenStreetMap-Mitwirkende | Straßennamen je Stimmbezirk |
| Wikidata SPARQL | `https://query.wikidata.org/sparql` | SPARQL-JSON | CC0 | Orte mit Koordinate in der Verwaltungseinheit (`P131*`) |
| Wikipedia GeoSearch | `https://de.wikipedia.org/w/api.php` | MediaWiki-JSON | Artikeltitel aus der deutschsprachigen Wikipedia | Orte je Stimmbezirks-Bounding-Box |

Die Entität je Stadt steht im Profil (`sources.wikidata.entity`: Düsseldorf `Q1718`, Mönchengladbach
`Q2758`), der Body-Katalog unter `https://ris-oparl.itk-rheinland.de/Oparl/bodies`.
Die ITK Rheinland betreibt mehrere Bodys desselben Servers: 0009 Neuss, 0011 Mönchengladbach,
0013 Grevenbroich, 0015 Düsseldorf, 0019 Rhein-Kreis Neuss.

## 2. Abrufverhalten

Alle Quellen sprechen über das `Transport`-Protokoll (`get`, `post`). Global gelten `http.timeout_s`
= 180 s je Aufruf und `http.retries` = 5 mit exponentiellem Backoff bei 429 und 5xx; der User-Agent
nennt das Repository. Antworten gehen durch `cache_root/http.sqlite` (requests-cache, Schlüssel ist
die URL beziehungsweise bei Overpass der POST-Body), PDFs **nie** — die gehören in den PDF-Store.

| Quelle | Einheit je Aufruf | Pause | Wiederholung | HTTP-Cache | gemessen |
|---|---|---|---|---|---|
| OParl `papers` | eine Seite = 200 Paper, neueste zuerst | 1 s (`sources.oparl.delay_s`) | global (5×, Backoff) | 1 h (`cache.oparl_pages_s`) | **85 s je Seite** (2026-10-09); Vollabruf der Hauptperiode 122 Seiten in 36 min (2026-10-14) |
| OParl `organizations` | eine Seite | — | global | 1 h | Düsseldorf 58 Objekte in **0,47 s** (2026-10-11), Mönchengladbach 122 Organisationen in **3,8 s** (2026-10-14) |
| OParl Hauptdateien | eine Datei | 1 s | global | **nie** | 38 ms Extraktion je PDF; Hochrechnung 5,8 h für 19 108 PDFs, 2,8 GB |
| Open-Data-Portal / votemanager / Geoportal | eine Datei | — | global | 30 Tage (`cache.opendata_s`) | vier Dateien Mönchengladbachs in 1,7 s |
| Overpass | ein Stimmbezirkspolygon (Außenring des größten Polygons, um 2 m vereinfacht) | 1 s | **eigene**: bis zu `sources.osm.retries` = 3 mal je Stimmbezirk bei 504/429, Pause 1×, 2×, 4× | 30 Tage | mit `[timeout:25]` 2 s je Abfrage, mit `[timeout:90]` 504 von allen vier öffentlichen Instanzen (2026-10-13) |
| Wikidata SPARQL | **eine** Abfrage für alle Objekte der Stadt | — | global | 30 Tage | — |
| Wikipedia GeoSearch | eine Bounding-Box je Stimmbezirk, `geosearch_limit` = 500 | 1 s | global | 30 Tage | 179 Overpass- plus 179 GeoSearch-Abfragen Mönchengladbachs in rund 15 min |

Drei Eigenheiten, die man nicht erwartet:

- **`[timeout:N]` ist nicht der Netz-Timeout**, sondern das Rechenbudget, das Overpass der Abfrage
  gibt. Der Server schätzt die Kosten vorab gegen sein Slot-Budget und weist ein großes Budget unter
  Last ab. `sources.osm.query_timeout_s` steht darum auf 25 (decisions.md, Punkt 54); wer sie
  hochdreht, macht es schlechter und verliert außerdem alle gecachten Antworten, weil der POST-Body
  der Cache-Schlüssel ist.
- **Die Session wiederholt den Overpass-POST nicht**: ihre Retry-Regel erlaubt GET und HEAD. Darum
  wiederholt `fetch_street_names` selbst, und zwar je Stimmbezirk — ein einzelner 504 soll nicht die
  Bezirke danach kosten (Punkt 55).
- **Abbruchregeln statt Vollabruf.** `sources.oparl.stop_when_older` hält an, sobald eine Seite nur
  noch Paper vor `period.start` trägt (spart 270 von 365 Seiten); `incremental` holt beim zweiten Lauf
  nur `modified_since` (letztes `modified` minus ein Tag) und liefert dann auch gelöschte Paper;
  `first_page` überspringt die Seiten jüngerer Perioden (2014 bis 2020: ab Seite 90); `--max-pages N`
  ist die billige Probe, `--limit N` begrenzt neue PDF-Downloads. `--limit` und `--max-pages` landen
  im Settings-Fingerprint des Stamps, darum meldet `georep status` den Schritt danach als „offen:
  Settings geändert" — das ist richtig, nicht kaputt.

**Wiederaufnahme, je Quelle verschieden.** Der Metadatenabruf speichert nach **jeder Seite** in den
Store und schreibt die nächste URL nach `data_root/<profil>/raw/papers.progress.json`
(`pipeline.py` ruft `read_progress`/`write_progress` für jedes Profil, nicht nur für eine alte
Periode); bricht der Lauf ab, macht der nächste bei dieser URL weiter und nicht bei
`sources.oparl.first_page`. Die Datei verschwindet, sobald ein Abruf durchgelaufen ist — wer von
vorn beginnen will, löscht sie, denn `--force` umgeht den Stamp, nicht den Netz-Cursor, und ein
zweiter Durchlauf derselben Seiten schreibt dieselben Paper. Dazu kommt der HTTP-Cache: OParl-Seiten
liegen eine Stunde (`cache.oparl_pages_s`), ein zweiter Versuch innerhalb dieser Stunde liest also
die schon geholten Seiten aus dem Cache statt vom Server, und für einen langen zweiten Versuch lohnt
es, den Wert zu erhöhen. `fetch pdfs` ist je Datei wiederaufnehmbar, `streets_osm` je Stimmbezirk
(und zwar allein über den HTTP-Cache, der die Antworten 30 Tage hält).

Fehlerverhalten: jeder Fetcher wirft nur `FetchError` (Antwort nicht brauchbar) oder `NetworkError`
(nicht erreichbar nach allen Wiederholungen), gesichert durch `deal.raises`. Der PDF-Download isoliert
jeden Fehler je Datei und berichtet Zähler; Antworten ohne `%PDF` werden abgewiesen. Jede OParl-Seite
geht durch das pydantic-Modell in `georep.oparl`, ein fehlendes oder falsch getyptes Feld ist ein
Fehler an der Grenze.

## 3. Was lokal liegt

```
reference/                  Datensatz der Arbeit, nur lesbar (Layout.guard_writable)
  moenchengladbach/         Paket der zweiten Stadt, mit raw/organizations.json
snapshots/2014-2020/        Paket der zweiten Wahlperiode
snapshots/2025/             Paket des Erstabrufs der laufenden Periode
snapshots/duesseldorf-beratungsfolge/   nur raw/beratungsfolge.parquet: die Beratungsfolge je
                            Dokument der Hauptperiode, deren Korpus sie nicht trägt (Punkt 58)
context/                    Fremddaten (Quartiersatlas), nur lesbar
data_root/                  Standard ./data, gitignored
  <profil>/{external,raw,interim,processed,site}/
       raw/                 papers.jsonl, organizations.json, beratungsfolge.parquet,
                            streets_per_district.json, wikipedia_dict.json
  site/                     was georep publish zusammenträgt und Pages hochlädt
cache_root/                 Standard data_root/cache
  <profil>/pdf/             PDFs plus manifest.jsonl (URL, SHA-256, Größe, Zeit)
  <profil>/text/texts.parquet   Texte mit Extraktorname, PDF-Hash, Herkunft, Zeichenzahl
  http.sqlite               requests-cache, von allen Profilen geteilt
```

**Die sechs Datenpakete im Repo** sind die eingefrorenen *Eingaben* der Läufe; GitHub Pages baut
damit jede Seite ohne einen einzigen Netzaufruf (decisions.md, Punkt 56). Ein Paket ist ein
`reference_root`: `Layout.reference_view()` liest es als Datenwurzel mit `cache_root =
<reference_root>/cache`, darum liegt sein Textstore unter `cache/text/`.

| Paket | Bytes | Inhalt | Profil |
|---|---|---|---|
| `reference/` | 85 771 896 (81,80 MiB) | Altformat `interim/paper_with_text.json`, `external/`, `raw/`, dazu `processed/` mit den Golden-Master-CSVs der Arbeit | `duesseldorf` |
| `reference/moenchengladbach/` | 4 405 625 (4,2 MiB) | `external/` (4), `raw/` (4, seit Punkt 58 mit `organizations.json`), `cache/text/texts.parquet` | `moenchengladbach` |
| `snapshots/2014-2020/` | 37 875 851 (36,1 MiB) | `external/` (4), `raw/papers.jsonl`, Textstore | `duesseldorf-2014` |
| `snapshots/2025/` | 13 894 254 (13,2 MiB) | `external/` (2), `raw/papers.jsonl`, Textstore | `duesseldorf-2025` |
| `snapshots/duesseldorf-beratungsfolge/` | 90 455 (88 KiB) | `raw/beratungsfolge.parquet`: `id`, `consultation_organizations`, `modified` (Punkt 58) | `duesseldorf` |
| `context/` | 2 242 316 (2,14 MiB) | drei Dateien des Quartiersatlas | alle Düsseldorf-Profile |

Zusammen **144 280 397 Bytes, 137,60 MiB**, 76 % der Grenze von 180 MiB im Test; gezählt sind die
Datendateien ohne die READMEs. Jedes Paket trägt ein README mit Herkunft, Lizenz, Abrufdatum, den
Zahlen des Laufs und der SHA-256 jeder Datei; `tests/unit/test_data_packages.py` hält Dateiliste,
Größe und Prüfsumme dagegen und lässt keine PDFs, Stamps, Manifeste und Caches hinein. **Die PDFs
liegen in keinem Paket** (233 MB Mönchengladbach, 3,9 GB Periode 2014 bis 2020, 585 MB laufende
Periode) — nur die Texte daraus.

Das Paket der Beratungsfolge gibt es nur, weil der Korpus der Hauptperiode aus dem **Altformat der
Arbeit** stammt und dieses Format die Folge nicht führt; jede andere Periode trägt sie in ihrem
eigenen `raw/papers.jsonl` (`snapshots/2014-2020` für 22 066 von 22 215 Dokumenten, `snapshots/2025`
für 3 966 von 4 095, `reference/moenchengladbach` für alle 2 895) und setzt `[bodies].consultations`
wieder leer. Es ist **Parquet statt JSONL**: derselbe Inhalt kostet als JSONL 4 467 207 Bytes, also
fast fünfzigmal so viel.

`georep pack ZIEL` ist die Gegenrichtung von `bootstrap`: es schreibt aus einem gelaufenen Profil
genau die Dateien, die `bootstrap` später sucht, mit Prüfsummentabelle und README-Gerüst. Es bricht
ab, statt ein halbes Paket zu schreiben, wenn eine Eingabe fehlt, wenn der Textstore Zeilen trägt,
die nicht aus einem Lauf kommen, oder wenn ein Text kein Paper hat. `georep pack --consultations`
packt stattdessen nur die Beratungsfolge je Dokument.

## 4. Wie die Kette läuft

**Neunundzwanzig Schritte** stehen im Register; welche ein Lauf hat, entscheiden die Settings, und
`georep steps` zeigt es. Jeder Schritt nennt Eingaben, Ausgaben und eine Schema-Version; die
Schritt-für-Schritt-Tabelle mit Netzflagge steht in [architecture.md](architecture.md), Abschnitt
„Pipeline".

| Profil | Schritte | was fehlt oder dazukommt |
|---|---|---|
| `duesseldorf` | 27 | der Standard |
| `duesseldorf-vergleich` | 28 | zusätzlich `compare` |
| `duesseldorf-2014` | 22 | `crosswalk.enabled` bringt `precincts`; `period.dictionary = "base"` nimmt `streets_osm` und `pois_wiki` |
| `duesseldorf-2025` | 21 | keine Regression, keine Kontrollvariablen, Wörterbuch der Hauptperiode |
| `moenchengladbach` | 23 | keine Fremddaten (`context.root` leer); seit Punkt 58 kein `committees` (`classify.enabled = false`), dafür `organizations` als Netzschritt; seit Punkt 59 **mit** `parties` |

Der Schritt `bodies` liest seit Punkt 58 zwei Quellen: den Korpus (`id`, `reference`,
`consultation_organizations`) und, wo das Profil eines nennt, `raw/beratungsfolge.parquet`. Seine
Ausgabe `papers_gremien.parquet` trägt dafür drei Spalten mehr (`quelle`, `folge_gremium`,
`folge_anzahl`, Schema-Version 2), und `georep learn-bodies` rechnet die Abbildung
Organisation → Kürzel aus den Daten nach, ohne etwas zu schreiben.

**Stamps.** Neben der ersten Ausgabe jedes Schritts liegt `<datei>.stamp.json` mit den
SHA-256-Hashes der Eingaben, dem Settings-Fingerprint, der Code-Version, der Schema-Version und einem
optionalen Zusatz. Stimmt alles, ist der Schritt aktuell und wird übersprungen; sonst läuft er und
sagt, warum („Eingabe geändert: texts.parquet", „Code-Version 0.6.0 -> 0.7.0"). Zwei Schritte haben
einen eigenen Zusatz: `report` einen Hash über die Vorlagendateien des Pakets, `literatur.toml` und
`settings.report` (sonst machte ein Vorlagenwechsel den Stamp nicht ungültig), `topics` einen über
die Stoppwortliste. Der Settings-Fingerprint ist **global**: ein neuer Schlüssel lässt alle Schritte
einmal neu laufen. `--force` erzwingt, `--dry-run` plant nur, ein Lauf ohne Änderung ist ein No-op.

**Profile.** Ein Profil ist eine Stadt *oder* eine Wahlperiode; mit `base` baut es auf einem anderen
auf. Seine Daten liegen unter `data_root/<profil>/`, seine PDFs und Texte unter
`cache_root/<profil>/`, der HTTP-Cache bleibt geteilt. `Settings.base_profile` (= `city.slug`) nennt
die Hauptperiode einer Stadt; von dort liest ein Periodenprofil mit `period.dictionary = "base"` sein
Wörterbuch, damit sich zwischen zwei Perioden nur die Dokumente unterscheiden.

**Zeiten** (voller Offline-Lauf auf der Referenz, rund 23 s): Themenmodell 7,4 s, passender Ausschuss
6,5 s, Index 4,1 s, Berichtsseite 1,7 s, Gremien 0,3 s (seit Punkt 58), Kennzahlen 0,1 s. Der Index
ist der einzige heiße Pfad der Offline-Kette: 3,78 s seiner 4,1 s sind FlashTexts
`extract_keywords` über die **19 033 Texte** des Korpus, gemessen am 2026-10-11 mit 5 841 Begriffen
(vor Regel 1); die Zerlegung steht in [profiling/README.md](profiling/README.md).

**Reproduzierbarkeit.** Zwei Läufe auf denselben Eingaben schreiben byteidentische Parquet-Dateien:
alle Ausgaben sind sortiert, Mengen werden zu sortierten Listen. Eingaben behalten das Format ihrer
Quelle, alles Abgeleitete ist Parquet mit `georep.schema_version` in den Metadaten, append-artige
Metadaten bleiben JSONL, CSV entsteht nur für Menschen. Eine Ausnahme vom Determinismus ist das
Themenmodell: es ist je Rechner und je Thread-Zahl reproduzierbar, nicht darüber hinaus (zwischen 13
und 2 BLAS-Threads unterscheiden sich `themen.parquet` und `themen_anteile.parquet` in den letzten
Stellen; Labels und Kennzahlen bleiben gleich).

## 5. Wie veröffentlicht wird

**Drei Wege, dieselben Dateien.**

| Weg | wer | was | Netz |
|---|---|---|---|
| GitHub Pages | `.github/workflows/pages.yml` bei jedem Push auf `main` | alle Seiten aus den sechs Paketen | keines |
| von Hand | `georep run` plus `georep publish` | die Stadtseiten, die lokal gerechnet sind | keines |
| Betrieb | `deploy/bin/georep-monitor.sh` hinter einem systemd-Timer | laufende Periode fortschreiben, Hauptseite dazu | OParl und PDFs |

**Der Pages-Workflow** läuft `uv sync --locked`, `georep bootstrap`, `georep run`, dann je einen
bedingten Block für die zweite Periode, die laufende Periode und die zweite Stadt (jeder prüft, ob
sein Paket im Repo liegt), dann `georep publish --strict-budget`, dann `georep status` je Profil und
lädt `data/site/` als Pages-Artefakt hoch. Veröffentlicht ist das unter
<https://konradvoelkel.github.io/geographic-representation-dus/>.

**`georep publish`** liest je Stadt nur deren veröffentlichten Ordner (`summary.json`,
`wahlbezirke.geojson`, `wahlbezirke_auswertung.parquet`), legt die erste Stadt aus `publish.cities`
an die Wurzel von `data_root/site/` und jede weitere nach `site/<slug>/`, setzt in jede kopierte
Seite die Zeile „Weitere Städte" (die Quellseite hinterlässt dort nur die Marke
`<!--georep:weitere-staedte-->`) und baut `vergleich.html`. `*.stamp.json` bleibt beim Kopieren
draußen. Weil `publish` beim Kopieren löscht, nimmt es nur seinen eigenen Zielordner an: die
Standardwurzel, ein leeres Verzeichnis oder eines mit seiner Markerdatei `.georep-publish`.
`--strict-budget` endet mit Exit 1, wenn eine veröffentlichte Seite über `report.page_budget_bytes`
(1 000 000) liegt; von Hand bleibt es bei einer Zeile.

**Der Monitor** unter `deploy/` ist ein Lauf-Skript plus zwei systemd-Einheiten (täglich 04:17 plus
bis zu 30 min Streuung, verpasste Läufe werden nachgeholt). Er trägt keinen Pfad: alles
Rechnerspezifische steht in `%E/georep/monitor.env`, und wohin ein Profil schreibt, fragt das Skript
mit `georep paths` beim Paket ab. Ein Lauf: `uv sync --locked`, `bootstrap` der Hauptperiode, dann
des Monitorprofils, `fetch papers --force` (eine OParl-Seite mit `modified_since`, 45 bis 85 s),
`fetch pdfs texts` (rund 15 neue PDFs je Tag), `run`, die Hauptseite mit dem Link auf die laufende
Periode, `out/` zusammenstellen (beim ersten Lauf eines Monats zusätzlich
`out/2025/snapshots/<JJJJ-MM>/` mit `SHA256SUMS`), optional R2 und `rsync` auf einen VPS, zuletzt
`out/2025/stand.json`. Eine `flock`-Sperre lässt nur einen Lauf zu; ein Fehler bricht mit Exit 1 ab
und nennt den Schritt. `DRY_RUN=1` spricht mit nichts von außen. Details, Trockenlauf und Erstabruf
in [../deploy/README.md](../deploy/README.md).

**Stand 2026-10-14**: der Timer läuft noch nicht, VPS und Domain stehen aus. Bis dahin zeigt die
veröffentlichte Unterseite `2025/` den Stand des Schnappschusses vom 2026-10-13, und die Seite nennt
ihr Abrufdatum selbst.

## 6. Was eine neue Stadt braucht

Der Code kennt keine Stadt (ein grep-Test hält das fest), also ist eine neue Stadt eine Profildatei
plus ein Abruf. Der ausführliche Ablauf mit Prüfpunkten steht in
[runbook-stadt.md](runbook-stadt.md); dies ist die Liste dessen, was zu beschaffen ist.

| Was | Woher | Pflicht? |
|---|---|---|
| OParl-Body der Stadt | Serverkatalog, etwa `https://ris-oparl.itk-rheinland.de/Oparl/bodies` | ja |
| Wahlergebnis je Stimmbezirk (CSV) mit Wahlberechtigten, Wählern und Stimmen je Partei | Open-Data-Portal oder votemanager | ja |
| Flächen der Stimmbezirke (GeoJSON, Shapefile-Zip oder Esri-JSON einer ArcGIS-Operation) mit Stimmbezirks- und Wahlbezirksnummer | Portal oder Geoportal | ja |
| Wikidata-Entität der Stadt (`Q…`) | Wikidata | ja |
| Spaltennamen und Parteien der Ergebnis-CSV (`[columns.results]`) | aus der Datei ablesen | ja |
| Ausschlussliste der Stadtteil- und Stadtbezirksnamen (`search.exclude`) | von Hand, einmal je Stadt | ja — ohne sie dominiert der Stadtname (in Düsseldorf stünde „düsseldorf" in 8 385 Dokumenten) |
| Marker, ab dem der Text durchsucht wird (`search.text_split_marker`) | Stichprobe: in über 90 % der Texte? | nein, aber zu prüfen |
| Kürzel und Namen der Gremien (`[bodies]`) samt `reference_pattern` | OParl `organizations` und Dokumenttitel | nein — ohne Muster muss die Beratungsfolge einspringen (siehe unten) |
| Abbildung OParl-Organisation → Kürzel (`[bodies.organizations]`) | `georep learn-bodies` druckt sie; ohne Kürzel in den Nummern aus `fetch organizations` von Hand | nein — ohne sie entfällt die zweite Quelle des Gremiums (Punkt 58) |
| Muster für die Urheber (`[originators]`): **jede** Dokumentart in genau eine der vier Listen | die Dokumentarten der Stadt auszählen; nennen sie die Fraktion (Düsseldorf: „Anfrage SPD") oder nur die Klasse (Mönchengladbach: `3 - Fraktionsantrag`)? Der Ablauf steht als § 4c in [runbook-stadt.md](runbook-stadt.md) | nein — ohne sie fehlt der Schritt `parties` ganz, und eine Art ohne Liste steht sichtbar als „Urheber unbekannt" auf der Seite |
| Fremddaten je Raumeinheit (`[context]`) | Portal der Stadt | nein — ohne sie fehlen die beiden Abschnitte der Kontrollvariablen |
| Quellen mit Lizenz und Prüfdatum (`[[report.sources]]`) | Datensatzseiten | ja, für den Fuß der Seite |
| `publish.cities` in **allen** Profilen um den Slug erweitern | — | ja, sonst baut `publish` die Stadt nicht |

Drei Dinge, die der Mönchengladbach-Lauf gelehrt hat und die vor dem langen Teil zu prüfen sind:

Drei Prüfwerte, die der Mönchengladbach-Lauf gelehrt hat; was sie für die Auswertung bedeuten,
steht in [statistik.md](statistik.md).

1. **Abrufquote der Hauptdateien.** `fetch pdfs --limit 200` vor dem langen Teil: die Zeile des
   Schritts nennt, wie viele von 200 kamen, und dieselbe Quote ist für den Korpus zu erwarten. Die
   Quote gehört ins README des Pakets und in die Kernzahlen der Seite. Deutung in
   [statistik.md](statistik.md), § 8.
2. **Übereinstimmung mit dem amtlichen Straßenverzeichnis.** Die Zeile des Schritts `streets` nennt
   sie; unter 90 % je Wahlbezirk ist eine Anfrage an die Stadt nach aktuellen Flächen fällig.
   Deutung ebenda.
3. **Trägt die Drucksachennummer ein Gremium?** Wenn nicht (Mönchengladbach: `0682/XI`, über alle
   2 895 Nummern bestätigt), bleibt `bodies.reference_pattern` leer und die **Beratungsfolge**
   springt ein: `fetch organizations` holt die Namen, `georep learn-bodies` druckt den Katalog, die
   Tabelle kommt von Hand ins Profil. Der Ablauf samt beiden Prüfungen steht als § 4b in
   [runbook-stadt.md](runbook-stadt.md), die Wirkung je Profil in
   [statistik.md](statistik.md), § 10.

Nach dem Lauf macht **ein Befehl** das Paket für das Repo:
`uv run georep --profile <slug> pack reference/<slug>`.

## 7. Prüfungen und Werkzeuge

| Befehl | Was |
|---|---|
| `uv run nox` | Ruff, mypy strict, Lockfile ohne pandas/geopandas/osmnx, schnelle Suite parallel (1 186 Tests, rund 58 s, Abdeckung 98,5 %, Untergrenze 90 %) |
| `uv run pytest -m slow` | 36 Tests über die volle Referenz, die sechs Datenpakete, das Paket der Periode 2014 bis 2020 und die veröffentlichte Seite, rund 4 min |
| `uv run pytest -m network` | 4 Netztests, nur von Hand; in CI läuft kein Netz |
| `uv run nox -s bench` | 18 heiße Pfade gegen die gespeicherte Baseline, rot ab 20 % langsamer im Minimum |
| `uv run nox -s verify` | crosshair über die reinen Funktionen mit Verträgen, rund zehn Minuten (33 Ziele „Not confirmed" am 2026-10-14) |
| `uv run nox -s mutate` | pytest-gremlins, eine Sitzung je Modul mit genau seinen Testdateien; 81,3 % getötet über die dreizehn Module des Ausbaus |
| `uv run nox -s alone` | Reihenfolgeunabhängigkeit: jede Testdatei einmal allein, dann die Suite rückwärts |
| `uv run georep profile index` | ein echter Schritt unter cProfile, `.prof` nach `docs/profiling/` |

`verify` und die gezielte Mutationssitzung laufen zusätzlich wöchentlich in
`.github/workflows/quality.yml`. Netz kommt in Tests nie von echten Endpunkten: es geht über das
`Transport`-Protokoll und die Fake-Session in `tests/fakes.py` mit den aufgezeichneten Antworten unter
`tests/fixtures/http/`. Zeit (`today`) und Zufall (hypothesis-Profile) sind ebenso Eingaben.
