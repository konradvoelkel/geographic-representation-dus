# Plan 07: Monitoring

Stand 2026-10-12, Branch `feat/07-monitoring`. Status: im Review.

Auftrag: Briefing § 7.7 des Meta-Plans ([../plan-ausbau-2026-10.md](../plan-ausbau-2026-10.md)) und Konrads
Antwort zu Frage 4 ([fragen.md](fragen.md)): die laufende Wahlperiode ab dem 15.09.2025 inkrementell abrufen
und auf der Seite zeigen; zuerst auf kookaburra simulieren, von Anfang an für den VPS vorbereiten; große
aktualisierte Daten in ein Cloudflare-R2-Bucket, fertige Datensätze auf dem VPS, später eine Datenplattform.
Dieser Plan ist so geschrieben, dass ein frischer Agent ihn in Phase 3 ohne Rückfragen umsetzen kann. Die
Arbeitsregeln stehen in [../../CLAUDE.md](../../CLAUDE.md), der Aufbau in [../architecture.md](../architecture.md).
Zahlen in § 3 sind am 2026-10-11 nachgesehen (Polars, `ls -l`, eine einzelne OParl-Seite); nichts ist geraten.

## 1. Ziel und Nicht-Ziel

Ziel: Ein zweiter, dauerhafter Lauf derselben Kette für die Wahlperiode seit dem 15.09.2025 mit offenem Ende.
Er holt je Lauf nur Geändertes (`modified_since`), lädt nur neue PDFs, extrahiert nur neue Texte, rechnet die
Treffer je Wahlbezirk auf den Wahlbezirken und Wahlberechtigten der Kommunalwahl 2025 und baut daraus eine
eigene Seite: Treffer je Wahlbezirk seit der Wahl, Neuzugänge je Monat, Datenstand. Der Lauf ist ein
idempotentes Skript (`fetch`, `run`, `publish`) hinter einem systemd-Timer; Skript und Unit-Dateien liegen im
Repo, alles Rechnerspezifische kommt aus Settings und Umgebung. PDFs und Textstore gehen in ein privates
R2-Bucket, die fertigen Tabellen als Downloads auf den VPS; für eine spätere Datenplattform nennt § 2 die
Kandidaten. Ohne Freigabe kein echter Abruf: Phase 3 endet mit Tests gegen die Fake-Session und einer
Simulation auf kookaburra mit Trockenlauf; den Erstabruf (§ 5, Stufe G) startet Konrad.

Nicht Ziel: eine Regression für die laufende Periode (es gibt keine Wahlbeteiligung dazu); ein neuer
Abruf von Straßen und Orten (das Wörterbuch bleibt das der Referenz, § 2); die PDFs der Periode 2020 bis 2025
nachzuladen; GitHub Actions als Laufzeitumgebung (kein dauerhafter Speicher, sechs Stunden Limit); ein Upload
auf Zenodo oder Hugging Face in dieser Option (vorbereitet, nicht ausgeführt); Änderungen am Infra-Repo
(`~/files/work/server` gehört Konrad, Playbook § 3.10: ein Repo besitzt den Server).

## 2. Entscheidungen (mit verworfenen Alternativen und Kosten)

| Frage | Entscheidung | Warum, und was verworfen wurde |
|---|---|---|
| Wo lebt die laufende Periode | ein Settings-Profil `settings.2025.toml` mit `profile = "2025"`; `Layout.from_settings` hängt den Profilnamen an `data_root` (`<data_root>/2025/`), `cache_root` bleibt unabhängig davon | Stamps und Ergebnisse zweier Perioden dürfen nicht kollidieren; die Referenzkette auf `main` bleibt byteidentisch. Verworfen: eine Datenwurzel mit Periodenfilter im Schritt `corpus` (ändert den Golden-Master-Pfad, jeder Schritt müsste filtern); `data_root` im Profil setzen (gewinnt über `settings.local.toml` und landet auf der vollen Primärplatte) |
| Offene Periode | `Period.end` wird optional; neu `Period.election` (Wahltag, dessen Ergebnis Nenner und Zuschnitt liefert); bei gesetztem `end` ist `election` standardmäßig `end`, bei offenem Ende Pflicht | `data_stand` und die Seite brauchen den Wahltag unabhängig vom Periodenende; `in_period` ohne Ende heißt „ab `start`". Verworfen: `end = 2030-09-13` als Platzhalter (der Wahltermin steht nicht fest, und ein Datum in der Zukunft sagt „geschlossen") |
| Wörterbuch | eingefroren: Straßen und Orte der Referenz (November 2025); das Profil ruft `opendata`, `streets_osm`, `pois_wiki` nie ab, `bootstrap` kopiert sie | Änderungen der Treffer sollen nur von den Dokumenten kommen; derselbe Vorschlag steht im Briefing von Option 2. Verworfen: jährlich neues Wörterbuch (Vergleichbarkeit weg, Overpass-Abruf 306 Abfragen). Offene Frage 8 |
| Korpus im Profil | `[bootstrap] seed_corpus = false` im Profil: `bootstrap` kopiert nur die vier Eingaben, kein `papers.jsonl` und kein Textstore aus der Arbeit | sonst stünden 19 108 Paper von 2020 bis 2025 im Monitoring-Store, und `pdfs` lüde deren PDFs (Stunden). Verworfen: Datumsfilter in `seed_stores_from_legacy` (Magie an der falschen Stelle) |
| Inkrement | je Lauf `georep --settings settings.2025.toml fetch papers --force`, dann `fetch pdfs texts`, dann `run`; `modified_since` = letztes `modified` minus ein Tag (vorhanden); gelöschte Paper (`deleted: true`) fliegen aus dem Store | `papers` hat keine Eingaben, also ist sein Stamp nach dem ersten Lauf „aktuell" und der Schritt würde ohne `--force` übersprungen (so verhält sich `tests/golden/test_network_steps.py`). Der Server beachtet `modified_since` und liefert dabei Gelöschte (§ 3). Verworfen vorerst: ein `max_age_s` je Schritt (mehr Code für dasselbe Ergebnis; kann die Synergiephase einführen) |
| Monatsreihe | neuer Offline-Schritt `timeline` nach `index`: `processed/monatsreihe.parquet` (stadtweit) und `processed/wahlbezirke_monate.parquet` (je Wahlbezirk); läuft in beiden Profilen | ein erstklassiges, gestempeltes Ergebnis mit Schema, Export und Download, statt einer Nebenrechnung in `report`. Kosten: `georep steps` bekommt eine Zeile, Snapshots und Zähler in Tests ändern sich bewusst |
| Seite | das Profil baut mit demselben Schritt `report` seine eigene `index.html` (unter `<data_root>/2025/site/`) aus derselben Vorlage mit Zweigen: ohne Streudiagramm und Tabelle 5 (`[report] regression = false`), mit Abschnitt „Je Monat" (Balken) und einem Datenstand aus den Stamps der Netzschritte; die Hauptseite bekommt den Link auf die laufende Periode nur, wenn `[report] monitoring_url` gesetzt ist (relativ, auf dem VPS `2025/`), Pages bleibt ohne toten Link | die Hauptseite entsteht in Actions aus der Referenz und kann eine zweite Datenwurzel nicht lesen; eine Unterseite ist der Mechanismus, den der Meta-Plan § 2 für das Seitenbudget vorsieht. Verworfen: ein Monitoring-Abschnitt in der Hauptseite (Datenwurzel-übergreifendes Lesen, Pages bräuchte Netz); eine zweite Vorlage (doppelte 400 Zeilen) |
| Kennzahl | `trefferquote` wie bisher (Dokumente mit Treffer je Wahlberechtigtem 2025), dazu die absolute Zahl; die Seite sagt, dass die Spanne kürzer ist als fünf Jahre; keine Regression, kein Wahlbeteiligungs-Umschalter auf der Karte | dieselbe Spalte behält dieselbe Bedeutung in Schema und Downloads; ein Zusammenhang mit der Wahl vor der Periode wäre eine andere Frage |
| Betrieb | `deploy/bin/georep-monitor.sh` (bash, `set -u`, jede Prüfung mit eigener Exit-Abfrage, keine Pipes vor Prüfungen, `flock`, zählt und druckt je Schritt), `deploy/systemd/georep-monitor.service` und `.timer`, `deploy/monitor.env.example`; Konfiguration nur über `EnvironmentFile=%E/georep/monitor.env` (`%E` ist `$XDG_CONFIG_HOME` für Nutzereinheiten, `/etc` für Systemeinheiten) und die Settings; der Pfad zum Repo kommt als `${GEOREP_REPO}` aus der Umgebung in `ExecStart` | dieselben Unit-Dateien laufen auf kookaburra als Nutzereinheit (`Linger=yes` ist gesetzt) und auf dem VPS als Systemeinheit über die Infra-Rolle; Playbook § 3.10 und `bubatz-daily` als Vorbild. Verworfen: cron (kein `Persistent=`, kein Journal, keine Credentials); Actions-Cron (Speicher, Zeitlimit); fester Pfad in `ExecStart` |
| Zugangsdaten | nie im Repo; rclone-Konfiguration per `LoadCredential=rclone.conf:%E/georep/rclone.conf` in einem Drop-in `georep-monitor.service.d/r2.conf` (Vorlage im Repo), im Skript `RCLONE_CONFIG=$CREDENTIALS_DIRECTORY/rclone.conf`; ein Token je Rechner mit „Object Read & Write, nur Bucket" | Playbook § 3.6 (ein Credential je Verwendung, 0600) und bb `DEPLOY.md` § 0. Verworfen: `~/.config/rclone/rclone.conf` (gilt für alle Remotes, wandert mit) |
| R2 | zweites Bucket `georep` (WEUR, privat, keine Domain, kein `r2.dev`); Inhalt `cache/pdf/`, `cache/text/texts.parquet`, `cache/pdf/manifest.jsonl`, `2025/raw/papers.jsonl`, `2025/processed/*.parquet`; `rclone sync` für `pdf/`, `copyto` für Einzeldateien; der Lauf druckt die Zahl der übertragenen Objekte | das Bucket ist Sicherung und Übergabe zwischen kookaburra und VPS, nicht Auslieferung. Kosten: der Freibetrag gilt je Konto über alle Buckets, ein zweites Bucket kostet nichts, solange die Summe unter 10 GB-Monat bleibt (§ 3: bubatzblick rund 6,5 GB, georep 0,6 GB plus 0,55 GB je Jahr); darüber 0,015 $ je GB-Monat. Verworfen: PDFs in GitHub-Releases (2 GB je Datei, keine Synchronisation); PDFs im Repo |
| VPS | Dokumentwurzel: `/` die Hauptseite (Spiegel von Pages, aus der Referenz gebaut), `/2025/` die Seite des Profils mit `data/`, `/2025/snapshots/<JJJJ-MM>/` monatliche Kopien von `data/` mit `SHA256SUMS`, Aufbewahrung `SNAPSHOT_KEEP` (Standard 24, der Lauf druckt, wie viele er entfernt hat); Übertragung mit der kanonischen Zeile `rsync -a --chmod=D755,F644 --delete --itemize-changes ${DRY_RUN:+--dry-run} "$out/" "$VPS_HOST:$VPS_WWW/"`; ohne `VPS_HOST` endet der Lauf im lokalen `PUBLISH_DIR` (Simulation) | unter 10 GB bleibt das bei weitem (ein Schnappschuss rund 10 MB). Verworfen: Push-to-deploy wie bubatzblick (die Daten entstehen auf dem Server, nicht im Commit) |
| Datenplattform später | Vorschlag: Zenodo für zitierfähige Jahresstände mit DOI, Hugging Face Hub für die Parquet-Tabellen mit Vorschau und Versionierung, GovData nur über eine Hochschulstelle als Katalogeintrag; vorbereitet werden Datensatzkarte, Lizenzzeile und `CITATION.cff`, hochgeladen wird nichts | Tabelle in § 3 mit Lizenz, Größe, DOI, Parquet; Open.NRW nimmt nur Behörden und Kommunen. Offene Frage 7 |
| Hauptseite in Actions | unverändert: `pages.yml` baut weiter aus der Referenz; der neue Schritt `timeline` läuft dort mit (Sekunden) | kein Netz in Actions; die Monatsreihe 2020 bis 2025 kostet rund 15 KB SVG (§ 6) |

## 3. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

Bestand im Worktree nach `bootstrap` und `run` (2026-10-11, `data_root` des Worktrees, `cache_root` geteilt
unter `/media/konrad/xtraspace/georep/cache`):

| Datei | Zeilen | Bytes | Spalten |
|---|---|---|---|
| `raw/papers.jsonl` | 19 108 | 9 245 584 | `id`, `name`, `reference`, `date`, `paper_type`, `main_file`, `file_name`, `download_url`, `modified` (in allen 19 108 Zeilen `null`: die Referenz stammt aus `paper_with_text.json`, `from_legacy` kennt kein `modified`); `date` von 2020-09-14 bis 2025-09-12, keine Zeile ohne Datum |
| `interim/papers.parquet` | 19 108 | 15 677 746 | `id` String, `name` String, `reference` String, `date` Date, `paper_type` String, `main_file` String, `file_name` String, `download_url` String, `text` String (Schema-Version 2) |
| `cache/text/texts.parquet` | 19 033 | 15 018 867 | `name`, `text`, `extractor`, `pdf_sha256`, `source`, `chars`; alle mit `source = "reference"`, `extractor = "pypdf (Arbeit, Januar 2026)"` |
| `cache/pdf/manifest.jsonl` | 200 | 50 198 | `name`, `url`, `sha256`, `size`, `fetched_at`; die 200 PDFs darunter: 29,0 MB, Mittel 145 KB, Median 118 KB |
| `cache/http.sqlite` | | 2 666 496 | requests-cache |
| `processed/wahlbezirke_auswertung.parquet` | 41 | 135 841 | `wahlkreis_id` Int64, `suchbegriffe` List(String), `paper_ids` List(String), `anzahl_treffer` Int64, `Wahlberechtigte_insgesamt`, `Waehler`, `CDU_Stimmen`, `GRUENE_Stimmen`, `SPD_Stimmen`, `FDP_Stimmen`, `Die_Linke_Stimmen`, `AfD_Stimmen` Int64, `wahlbeteiligung`, `CDU_anteil`, `GRUENE_anteil`, `SPD_anteil`, `FDP_anteil`, `Die_Linke_anteil`, `AfD_anteil`, `trefferquote` Float64 |
| `processed/inverted_index.parquet` | 5 841 | 152 045 | `suchbegriffe` String, `paper_ids` List(String), `anzahl_treffer` Int64 |
| `processed/combined_searchdict.parquet` | 41 | 44 255 | `wahlkreis_id` Int64, `suchbegriffe` List(String) |
| `processed/wahlbezirke_waehler.parquet` | 41 | 9 519 | wie die Wählerspalten oben ohne `trefferquote` |
| `processed/wikidata_vis.parquet` | 1 309 | 30 819 | `label` String, `wahlkreis_id` Int64, `lon`, `lat` Float64 |
| `processed/wikidata_agg.parquet`, `wahlbezirke_strassen.parquet` | 41, 41 | 14 354, 25 413 | `wahlkreis_id` Int64, `suchbegriffe` List(String) |
| `site/index.html`, `site/karte.html` | | 686 088, 255 263 | `site/data/`: 15 Dateien, 7,1 MB, davon `dokumente.json` 2 148 551 |

Stamps tragen `written` (ISO-Zeit, UTC); `report.model.stamp_written` liest es heute für `streets` und `pois`.

**Der OParl-Server, geprüft mit der einen erlaubten Seite am 2026-10-11, 21:42 UTC:**
`GET https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers?modified_since=2026-10-01T00:00:00+00:00`
(User-Agent wie in `defaults.toml`): HTTP 200 nach 44,5 s, 266 355 Bytes, 141 Paper; alle 141 haben
`modified` zwischen `2026-10-01T09:54:11+02:00` und `2026-10-09T15:24:32+02:00`, keines davor, der Filter
wird also beachtet. Fünf Einträge tragen `deleted: true` und kein `date` (OParl 1.1: bei `modified_since`
muss der Server Gelöschte mitliefern, `modified` ist der Löschzeitpunkt; ohne den Parameter dürfen sie nicht
erscheinen). Kein `next`-Link (eine Seite, unter 200 Einträgen); `pagination` ist `{"elementsPerPage": 200,
"currentPage": 1}` ohne `totalElements`; `links.first` und `links.self` tragen den Parameter. Sortierung nach
`date` absteigend, die datumslosen Gelöschten zuerst. 136 Paper haben `date` ab 2025-09-15 (2026-05-15 bis
2026-10-08), 136 eine `download_url`. Das pydantic-Modell kennt jeden gelieferten Schlüssel. Die Fixture
`tests/fixtures/oparl/papers_page.json` vom 2026-10-09 zeigt die ungefilterte erste Seite: `links.next =
…?page=2`, `date` 2026-10-01 bis 2026-10-07, `modified` mit `+02:00`. Der Server brauchte am 2026-10-09
85 s je Seite, heute 44,5 s.

**Hochrechnung für die laufende Periode** (aus der Referenz: 19 108 Paper in 60 Monaten, 318 je Monat):
vom 15.09.2025 bis heute rund 4 100 Paper, 21 Seiten à 200, rund 7,8 MB JSON (1,9 KB je Paper auf der
heutigen Seite); PDFs 4 100 × 145 KB ≈ 600 MB, je Jahr rund 3 800 Paper und 550 MB. Erstabruf: 21 Seiten ×
45 bis 85 s = 16 bis 30 min Metadaten, PDFs seriell mit 1 s Pause rund 2,3 h, Extraktion 38 ms je PDF rund
3 min. Danach je Lauf: in den neun Tagen bis zum 2026-10-09 wurden 141 Paper geändert, also rund 15 je Tag;
ein täglicher Lauf holt eine Seite (45 s) und rund 15 PDFs (30 s). Ein wöchentlicher Lauf bleibt unter einer
Seite. Der Textstore des Profils bleibt klein (etwa 3 MB je Jahr).

**Rechner und Werkzeuge** (2026-10-11): kookaburra, 16 Kerne, 62 GB RAM; `/media/konrad/xtraspace` 322 GB
frei, Primärplatte 23 GB frei (96 %); systemd 255, `loginctl show-user konrad` meldet `Linger=yes`;
`/usr/bin/rclone` 1.60.1 (Ubuntu; meldet laut bb `DEPLOY.md` geglückte Uploads als Fehler) und
`~/.local/bin/rclone` 1.75.1 (dieses nehmen, Pfad in `monitor.env`); `hf` 2.0.0 in `~/.local/bin`; kein
`wrangler`, kein `aws`. Der VPS: Hetzner, Debian 13, Caddy, verwaltet nur über `~/files/work/server`
(Ansible; dort liegen die Vorlagen `bubatz-daily.service.j2` und `.timer.j2` mit `LoadCredential`,
`EnvironmentFile`, `Type=oneshot`, `Persistent=true`, `RandomizedDelaySec=10m`).

**Cloudflare R2** (Preisseite, 2026-10-11): Freibetrag je Monat 10 GB-Monat Speicher, 1 Million Class-A-
und 10 Millionen Class-B-Operationen, Egress frei; darüber 0,015 $ je GB-Monat, 4,50 $ je Million Class A,
0,36 $ je Million Class B; bis 1 000 000 Buckets je Konto, Objekte bis 5 TiB. Die Abrechnung läuft je Konto,
ein Bucket selbst kostet nichts. bubatzblick belegt laut dessen Doku rund 6,5 GB (`basemap.pmtiles` 5,7 GB,
`zonen.pmtiles` rund 365 MB plus Vorgänger). georep käme mit 0,6 GB dazu und wüchse um 0,55 GB je Jahr:
unter dem Freibetrag bis etwa 2031; eine Überschreitung um 1 GB kostete 1,5 Cent im Monat. Ein täglicher
`rclone sync` über 4 100 Objekte braucht rund 5 List-Aufrufe (Class A) und 15 PUTs: weit unter den Grenzen.

**Kandidaten für die spätere Datenplattform** (geprüft 2026-10-11, wo nicht anders vermerkt):

| Plattform | Wer darf | Größe | DOI | Parquet | Lizenz | Einordnung |
|---|---|---|---|---|---|---|
| Zenodo (CERN) | jeder | 50 GB je Record, mehr auf Anfrage; alle Formate; Aufbewahrung für die Lebensdauer des Repositoriums (CERN, mindestens 20 Jahre) | ja, je Version, Konzept-DOI über Versionen; Metadaten CC0 | als Datei, ohne Vorschau | Lizenz ist Pflicht je Record (CC0 passt) | erste Wahl für zitierfähige Jahresstände (ein Record „georep Düsseldorf 2025–", je Jahr eine Version) |
| Hugging Face Hub (Datasets) | jeder; Datensatzkarte ist Pflicht | öffentlich „best-effort" ohne Gebühr, privat 100 GB frei; Empfehlung unter 10 000 Dateien je Ordner, Dateien unter 200 GB | ja, über DataCite je Revision („Generate DOI"); danach kein Löschen oder Umbenennen ohne Support | nativ, mit Dataset-Viewer und Versionierung (Git) | Lizenzfeld in der Karte | zweite Wahl für die Tabellen mit Vorschau; `hf upload` liegt auf kookaburra bereit |
| GovData | öffentliche Stellen, Unternehmen der Daseinsvorsorge, Hochschulen, Forschende und Forschungseinrichtungen; Private nicht | nur Metadaten, die Dateien bleiben beim Bereitsteller | nein (verweist) | egal | Nutzungsbestimmung Pflicht: dl-de/by-2-0, dl-de/zero-2-0 oder CC | Katalogeintrag auf den VPS- oder Zenodo-Link, nur über eine Hochschulstelle (HHU) |
| Open.NRW | Behörden des Landes und Kommunen ohne eigenes Portal, seit 2022 Daseinsvorsorge; Private nicht | nur Metadaten (Harvesting oder Erfassungsmaske) | nein | egal | wie GovData | nicht erreichbar für uns, nur über die Stadt Düsseldorf |
| OSF (Open Science Framework) | jeder | 50 GB je öffentlichem Projekt, 5 GB privat | ja | als Datei | wählbar | Alternative zu Zenodo, weniger verbreitet für Daten |
| GitHub Releases | wir | 2 GB je Datei (nicht neu geprüft) | nein | als Datei | Repo-Lizenz CC0 | Notlösung für Schnappschüsse, keine Plattform |

Lizenzen der Eingaben bleiben, wie sie auf der Seite stehen: Ergebnisse CC0, Straßen ODbL, Wikidata CC0,
Open-Data-Portal dl-de/by-2-0 (Wahlergebnis) und dl-de/zero-2-0 (Stimmbezirke). Die PDFs und Texte des
Ratsinformationssystems werden nicht veröffentlicht (Entscheidung der Berichtsseite § 1, offene Frage 3).

## 4. Berührungspunkte im bestehenden Code (Datei, Funktion, was sich ändert)

| Datei | Funktion oder Stelle | Änderung |
|---|---|---|
| `src/georep/settings.py` | `Period` | `end: date \| None = None`, neu `election: date \| None = None`; Validator: `end` nicht vor `start`; ohne `end` ist `election` Pflicht; mit `end` und ohne `election` wird `election = end` (`model_validator`, frozen: über `model_copy`) |
| | `Settings` | neu `profile: str = ""` (Validator: nur `[A-Za-z0-9_-]`), `bootstrap: Bootstrap` (`seed_corpus: bool = True`), `report: Report` (`regression: bool = True`, `monitoring_url: str = ""`, Validator: kein `://`); `fingerprint()` schließt `profile` aus (ein Pfad) und nimmt `report` und `bootstrap` nicht auf (sie ändern kein Ergebnis der Parquet-Kette); `settings_files` unverändert (`--settings settings.2025.toml`) |
| `src/georep/defaults.toml` | neue Schlüssel mit Kommentar | `profile = ""`, `[period] election` (leer: gleich `end`), `[bootstrap] seed_corpus = true`, `[report] regression = true`, `monitoring_url = ""` |
| `settings.2025.toml` (neu, Repo-Wurzel) | das Profil | `profile = "2025"`, `[period] start = 2025-09-15`, kein `end`, `election = 2025-09-14`, `[bootstrap] seed_corpus = false`, `[report] regression = false`; sonst nichts (Pfade kommen aus `settings.local.toml` und der Umgebung) |
| `src/georep/layout.py` | `Layout.from_settings` | `data_root / settings.profile`, wenn `profile` gesetzt; neu `timeline` (`processed/monatsreihe.parquet`), `district_timeline` (`processed/wahlbezirke_monate.parquet`) |
| `src/georep/oparl.py` | `OparlPaper.in_period(start, end)` | `end: date \| None`; ohne Ende zählt `start <= date` |
| `src/georep/sources/oparl.py` | `fetch_papers`, `FetchReport` | Gelöschte werden gesammelt: `FetchReport.deleted_ids: tuple[str, ...]` (Standard leer), `summary()` nennt „n gelöscht"; `in_period` bekommt `period.end` wie bisher (jetzt optional); `stop_when_older` unverändert (Gelöschte haben kein Datum und zählen nicht) |
| `src/georep/stores.py` | `PaperStore.upsert(incoming, *, deleted=())`, `UpsertReport.removed` | Gelöschte IDs verschwinden aus dem Store; Nachbedingung: `added + updated <= total`, `removed` zählt nur vorhandene |
| `src/georep/pipeline.py` | `papers()` | `store.upsert(records, deleted=fetched.deleted_ids)`; Zusammenfassung mit Löschungen |
| | `build_steps` | neuer Schritt `timeline` nach `index`: Eingaben `corpus`, `index`, `dictionary`; Ausgaben `timeline`, `district_timeline`; `report` bekommt `timeline` und `district_timeline` als Eingaben |
| `src/georep/analysis/timeline.py` (neu) | `monthly_series(corpus_meta, index)`, `district_months(dictionary, index, corpus_meta)` | reine Polars-Funktionen mit Verträgen (§ 5, Stufe C) |
| `src/georep/bootstrap.py` | `bootstrap(layout, *, force, seed_corpus=True)` | ohne Seed bleiben `papers.jsonl` und Textstore unberührt; Report sagt „Stores nicht aus der Referenz gefüllt" |
| `src/georep/cli.py` | `_cmd_bootstrap` | gibt `settings.bootstrap.seed_corpus` weiter; sonst keine neuen Unterbefehle |
| `src/georep/export.py` | `csv_plan` | zwei Zeilen für `monatsreihe` und `wahlbezirke_monate` (Spaltentrenner `,`, keine Listen) |
| `src/georep/report/model.py` | `DataStand` | neu `period_open: bool`, `papers_fetched`, `pdfs_fetched` (aus den Stamps von `papers.jsonl` und `manifest.jsonl`), `newest_document: date \| None`, `documents_without_text: int`; `election` aus `settings.period.election` |
| | `ReportModel` | `regression: RegressionPair \| None` (None bei `report.regression = false`), neu `timeline: tuple[MonthRow, ...]`, `monitoring_url: str` |
| | `COLUMN_DOCS`, `published_tables`, `key_figures` | zwei Tabellen mehr; Kernzahlen bekommen „Dokumente ohne Text" |
| `src/georep/report/charts.py` | neu `bars(months, …)` | Balken je Monat, zwei Reihen (Dokumente, mit Treffer), Achsen mit `nice_ticks`, `<title>` je Balken, CSS-Klassen wie bisher |
| `src/georep/report/build.py` | `build_site`, `DESCRIPTIONS`, `write_tables` | Scatter nur mit Regression; Balken immer; Downloads plus zwei Parquet und zwei CSV; `SiteSummary` unverändert |
| `src/georep/report/render.py` | `render_report`, `Visuals` | `Visuals.bars_svg`, `scatter_svg: str \| None`; Nachbedingung der Links unverändert (nur relative `monitoring_url`) |
| `src/georep/report/templates/report.html.j2` | Kopf, `#zusammenhang`, Karte, neue `#monate`, `#laufend` | Datenstand mit Abrufdaten und offener Periode; Regression und Umschalter „Wahlbeteiligung" nur mit `model.regression`; Abschnitt „Je Monat" mit Balken und Tabelle; auf der Hauptseite ein Absatz mit Link, wenn `model.monitoring_url` |
| `tests/unit/__snapshots__/test_cli.ambr` | `test_steps_output_is_stable` | eine Zeile `timeline` mehr, bewusst mit Diff erneuert |
| `tests/unit/test_cli.py`, `tests/golden/test_pipeline.py`, `tests/unit/test_report_build.py` | Zähler | „9 ausgeführt" wird 10, `len(offline) == 9` wird 10, 15 Download-Dateien werden 19 |
| `tests/unit/test_settings.py`, `test_oparl.py`, `test_sources_oparl.py`, `test_stores.py`, `test_report_model.py`, `test_report_render.py`, `tests/golden/test_network_steps.py` | neue Tests | § 5 |
| `tests/fixtures/oparl/papers_modified_since.json` (neu) | Fixture | sechs Einträge der heute geprüften Seite (davon zwei mit `deleted: true`), `links` ohne `next`; README mit URL und Datum; Aufzeichnung ist eine weitere einzelne Seite (45 s) in Phase 3 |
| `deploy/bin/georep-monitor.sh`, `deploy/systemd/georep-monitor.service`, `georep-monitor.timer`, `georep-monitor.service.d/r2.conf.example`, `deploy/monitor.env.example`, `deploy/README.md` (alle neu) | Betrieb | § 5, Stufen E und F |
| `.github/workflows/pages.yml` | unverändert | läuft `timeline` mit; der Link zur laufenden Periode bleibt dort aus, weil `monitoring_url` leer ist |
| `docs/architecture.md`, `docs/decisions.md`, `README.md`, `CHANGELOG.md` („Unreleased"), `STATUS.md` | Doku | Modultabelle (`analysis/timeline`, `deploy/`), Pipeline-Tabelle (15 Schritte), Datenhaltung (`<data_root>/<profile>/`), Abschnitt „Betrieb", Entscheidung mit verworfenen Alternativen |

## 5. Bauplan in Stufen (je Stufe: Schritte, Tests, Verträge, Abnahmekriterium, geschätzter Aufwand)

Jede Stufe sind ein bis drei Commits, Verhaltensänderung zuerst mit rotem Test, nach jedem Commit
`uv run nox` (im Alltag `uv run pytest -n 2 …`). Tests arbeiten in `tmp_path` mit
`Layout(tmp/data, tmp/cache, mini_root)` und der Fake-Session aus `tests/fakes.py`; kein Test spricht mit
einem echten Endpunkt. Aufwand in Agentenstunden, ohne Konrads Handgriffe.

### Stufe A: Profil, offene Periode, Layout (3 h)

1. `Period`: `end` optional, `election` wie in § 4; `OparlPaper.in_period` mit offenem Ende. Tests:
   `test_settings.py` (offene Periode ohne `election` ist ein Fehler mit lesbarer Meldung; `end` vor `start`
   bleibt ein Fehler; Fingerprint unterscheidet offene und geschlossene Periode; `election` wird aus `end`
   gefüllt), `test_oparl.py` (`in_period(start, None)` ab `start` einschließlich, ohne Datum nie); ein
   hypothesis-Test in `tests/property/test_models_props.py`: für jedes Datum gilt
   `in_period(start, None) == (date >= start)`.
2. `Settings.profile`, `Bootstrap`, `Report`; `defaults.toml`; `Layout.from_settings` mit Profil;
   `settings.2025.toml`. Tests: `Layout.from_settings` hängt das Profil an `data_root`, nicht an
   `cache_root`; `profile = "../x"` ist ein Fehler; `load_settings(explicit=settings.2025.toml)` liefert
   offene Periode, `election = 2025-09-14`, `seed_corpus = False`, `regression = False`; `georep --settings
   settings.2025.toml status` zeigt `data_root` mit `/2025`.
3. `bootstrap(..., seed_corpus=False)`: kopiert die vier Eingaben, lässt Stores in Ruhe, Report sagt es.
   Test in `test_bootstrap.py`; `test_cli.py` prüft die Zeile.
4. Abnahme: `uv run nox` grün; `uv run georep --settings settings.2025.toml bootstrap` im Worktree legt
   `data/2025/external/` und `data/2025/raw/` mit den vier Dateien an und kein `papers.jsonl`;
   `uv run georep run` im Standardprofil bleibt ein No-op („aktuell" auf allen Offline-Schritten).

### Stufe B: Inkrementeller Abruf mit Löschungen (3 h)

1. Fixture `tests/fixtures/oparl/papers_modified_since.json` aufzeichnen (eine Seite, URL aus § 3, sechs
   Einträge mit zwei Gelöschten, README mit Datum); `test_oparl.py` prüft, dass das Modell jeden Schlüssel
   kennt und `deleted` liest.
2. `fetch_papers`: `deleted_ids` im Report; Test in `test_sources_oparl.py`: Gelöschte stehen im Report und
   nicht in den Records; `modified_since` nur auf der ersten Anfrage (vorhanden); offene Periode nimmt
   Paper nach dem 15.09.2025 ohne obere Grenze.
3. `PaperStore.upsert(deleted=…)`: entfernt, zählt; Test in `test_stores.py` (Löschen eines unbekannten
   Schlüssels zählt nicht; Löschen gewinnt über ein gleichzeitiges Update derselben ID nicht, weil der
   Server die ID entweder gelöscht oder lebend liefert; `save` bleibt deterministisch, zwei Upserts ohne
   Änderung schreiben identische Bytes). hypothesis-Eigenschaft: nach `upsert(records, deleted)` ist der
   Schlüsselsatz `(alt ∪ neu) \ gelöscht`.
4. Pipeline-Test `tests/golden/test_network_steps.py::test_incremental_runs_add_pages_and_keep_old`: eine
   Fake-Session, deren `routes` zwischen den Läufen umgeschrieben werden (das Dict ist veränderlich). Lauf 1
   (offene Periode, `seed_corpus=False`, vier PDF-Fixtures als Antworten): Seite mit A (2025-10-01) und B
   (2025-11-02), eine Antwort vor dem Periodenbeginn (2025-09-01) bleibt draußen; `papers`, `pdfs`, `texts`,
   `corpus`, `timeline` laufen, Korpus 2. Lauf 2 mit `force` auf `papers`: Seite mit C (neu, 2026-01-05), A'
   (`modified` später, neuer Dateiname) und D gelöscht (nie gesehen): Aufruf trägt
   `modified_since = max(modified) − 1 Tag`; Store A', B, C; `pdfs` lädt genau zwei (C und A'); `texts` sagt
   „2 extrahiert, 1 aktuell"; `corpus` 3 Zeilen; Lauf 3 ohne Änderung: alles „übersprungen" außer `papers`
   (erzwungen, „0 neu, 0 aktualisiert"). Dann Lauf 4: B gelöscht: Store A', C; Korpus 2.
5. Abnahme: `uv run nox` grün; `uv run georep --settings settings.2025.toml run --dry-run --online papers`
   plant den Schritt und sagt „vollständig" (kein Store); kein echter Abruf.

### Stufe C: Schritt `timeline` (3 h)

1. `analysis/timeline.py`: `monthly_series(corpus_meta, index)` liefert `monat` Date (Monatserster),
   `dokumente` Int64 (Paper mit `date` im Monat), `mit_text` Int64, `mit_treffer` Int64 (Dokumente mit
   mindestens einem Treffer in irgendeinem Begriff des Index), Monate lückenlos vom ersten bis zum letzten
   mit Nullen, sortiert; Dokumente ohne Datum in einer Zeile mit `monat = null` am Ende, falls es welche gibt.
   `district_months(dictionary, index, corpus_meta)` liefert `wahlkreis_id` Int64, `monat` Date,
   `anzahl_treffer` Int64 (Dokumente mit Treffer in einem Begriff des Bezirks, je Monat einmal), sortiert
   nach beiden Schlüsseln. Verträge: Vorbedingungen Pflichtspalten (`has_columns`), Nachbedingungen
   `sorted_unique` auf `monat` beziehungsweise dem Paar, `sum(dokumente) == corpus.height`,
   `mit_treffer <= mit_text <= dokumente` je Zeile, alle Zahlen nicht negativ; `ensure`: die Summe von
   `anzahl_treffer` je Bezirk gleicht `hits_by_district` (dieselbe Mengenlogik, nur nach Monat zerlegt).
2. hypothesis in `tests/property/test_timeline_props.py`: zufällige kleine Korpora (Daten in zwei Jahren,
   Texte leer oder nicht) und Indizes: Summen, Lückenlosigkeit, Monotonie; Beispieltest gegen die
   Mini-Fixture, nachgerechnet mit `pl.read_parquet(...).group_by(pl.col("date").dt.truncate("1mo"))`.
3. Schritt im Register, Layout, `csv_plan`, `COLUMN_DOCS`; Snapshot `test_cli.ambr` erneuern (Diff lesen),
   Zähler in `test_cli.py`, `test_pipeline.py` anpassen; `test_two_runs_write_identical_parquet` nimmt
   `timeline` auf.
4. Abnahme: `uv run georep run` im Worktree führt genau `timeline` und `report` aus (Eingabe geändert),
   `monatsreihe.parquet` hat 61 Zeilen (2020-09 bis 2025-09, lückenlos) und `sum(dokumente) == 19108`;
   `uv run pytest -m slow` grün; `uv run nox -s bench` grün (kein heißer Pfad betroffen).

### Stufe D: Berichtsseite des Profils und der Hauptseite (6 h)

1. `DataStand` und `ReportModel` wie § 4; `regression_pair` nur mit `report.regression`; `MonthRow` aus
   `monatsreihe.parquet`; `key_figures.documents_without_text`. Tests in `test_report_model.py`: auf der
   Mini-Fixture bleibt alles wie heute (Regression vorhanden, `period_open = False`, `papers_fetched is
   None`); mit einem Profil-Layout aus dem Stufe-B-Test: `regression is None`, `period_open`, Abrufdaten aus
   den Stamps, `newest_document` gleich dem größten `date` im Korpus, `timeline` mit so vielen Zeilen wie
   Monate.
2. `charts.bars`: reine Funktion Zahlen zu SVG; Tests: ein `<rect>` je Monat und Reihe, SVG parst mit
   `xml.etree`, Achsen decken den Wertebereich (`nice_ticks`), Snapshot (syrupy) nur für drei Monate.
   Vor dem ersten Diagramm die Skill `dataviz` laden, falls vorhanden (Farbregeln wie bei der Karte).
3. Vorlage: Zweige für `model.regression`, `model.stand.period_open`, `model.timeline`, `model.monitoring_url`;
   Kopfzeile des Profils: „Datenstand: Dokumente seit 15.09.2025, Metadaten abgerufen am …, PDFs am …,
   neuestes Dokument vom …, n Dokumente noch ohne Text; Wahlbezirke und Wahlberechtigte der Kommunalwahl
   14.09.2025" (alles aus dem Modell, nichts fest kodiert); Karte ohne Umschalter; neuer Abschnitt „Je
   Monat" (Balken, darunter Tabelle Monat, Dokumente, mit Text, mit Treffer); Hinweis, dass die Trefferquote
   eine kürzere Spanne misst. Hauptseite: Abschnitt „Laufende Wahlperiode" mit einem Satz und Link nur bei
   `monitoring_url`. Tests in `test_report_render.py`: beide Zweige rendern, parsen, genau ein `<h1>`; ohne
   Regression keine `scatter`-Klasse und kein Radiobutton `turnout`; mit `monitoring_url = "2025/"` genau ein
   Link darauf und keiner ohne; Nachbedingung der externen Links hält.
4. `build.py`: Downloads plus `monatsreihe.parquet`, `monatsreihe.csv`, `wahlbezirke_monate.parquet`,
   `wahlbezirke_monate.csv`; `schema.json` kennt beide Tabellen; `test_report_build.py` zählt 19 Dateien
   und prüft Prüfsummen wie heute.
5. Seite ansehen mit headless Chrome (Meta-Plan § 8.4) in hell und dunkel, Breite 375 px gemessen
   (`scrollWidth <= clientWidth`, Playbook § 3.10); Größe von `index.html` beider Profile notieren (§ 6).
6. Abnahme: `uv run nox`, `uv run pytest -m slow` grün; die Hauptseite aus der Referenz ist bis auf den
   Abschnitt „Je Monat" und die Datenstandzeile unverändert; die Profilseite aus dem Stufe-B-Testdatensatz
   (vier Dokumente, drei Monate) zeigt Balken, Tabelle, Karte und Downloads; `index.html` beider Profile
   unter 1,5 MB.

### Stufe E: Lauf-Skript und Unit-Dateien, Simulation auf kookaburra (5 h)

1. `deploy/monitor.env.example`: `GEOREP_REPO`, `GEOREP_PROFILE` (`settings.2025.toml`), `GEOREP_DATA_ROOT`,
   `GEOREP_CACHE_ROOT`, `UV_PROJECT_ENVIRONMENT`, `UV_CACHE_DIR`, `PATH` (uv und rclone liegen in
   `~/.local/bin`, systemd kennt keinen Login-PATH, Playbook § 3.2), `PUBLISH_DIR`, `VPS_HOST` (leer =
   keine Übertragung), `VPS_WWW`, `R2_REMOTE` (leer = kein R2), `RCLONE` (Pfad zur Version ≥ 1.61),
   `SNAPSHOT_KEEP=24`, `HEALTHCHECK_URL` (leer), `DRY_RUN` (leer). Keine Werte, nur Kommentare und Beispiele.
2. `deploy/bin/georep-monitor.sh` (`set -u`, `cd "$GEOREP_REPO" || exit 1`, `flock -n` auf
   `$GEOREP_DATA_ROOT/.monitor.lock`, jede Prüfung als `cmd || fail "…"`, nirgends `cmd | tail`):
   (1) `uv sync --locked`; (2) `georep --settings $GEOREP_PROFILE bootstrap`; (3) `… fetch papers --force`;
   (4) `… fetch pdfs texts`; (5) `… run`; (6) Hauptseite: `georep bootstrap && GEOREP_REPORT__MONITORING_URL=2025/ georep run`
   (Sekunden, nur bei Codeänderung mehr als ein No-op); (7) `out/` unter `PUBLISH_DIR` zusammenstellen:
   Hauptseite nach `out/`, Profilseite nach `out/2025/`, am ersten Lauf eines Monats `out/2025/snapshots/<JJJJ-MM>/`
   als Kopie von `data/` mit `SHA256SUMS`, ältere über `SNAPSHOT_KEEP` hinaus entfernen und die Zahl
   drucken; `out/2025/stand.json` mit Beginn, Ende, Ergebnis, den Zusammenfassungszeilen der Schritte;
   (8) R2 nur mit `R2_REMOTE` (Stufe F); (9) VPS nur mit `VPS_HOST` (Stufe F); (10) `HEALTHCHECK_URL`
   optional (`/start`, `/fail`, Erfolg); Abschluss: eine Zeile „georep-monitor: n neue Paper, n PDFs, n
   Texte, Seite n KB, Schnappschuss ja/nein, Dauer". Mit `DRY_RUN=1` laufen (3) und (4) als
   `run --dry-run --online`, (5) als `run --dry-run`, rsync mit `--dry-run`, rclone mit `--dry-run`.
3. `deploy/systemd/georep-monitor.service`: `Type=oneshot`, `After=network-online.target`,
   `EnvironmentFile=%E/georep/monitor.env`, `ExecStart=/usr/bin/bash ${GEOREP_REPO}/deploy/bin/georep-monitor.sh`,
   `TimeoutStartSec=6h`, `Nice=10`; keine Pfade. `georep-monitor.timer`: `OnCalendar=*-*-* 04:17:00`,
   `RandomizedDelaySec=30m`, `Persistent=true`, `WantedBy=timers.target` (ohne `Unit=`, der Dienst heißt
   gleich). `georep-monitor.service.d/r2.conf.example`: `LoadCredential=rclone.conf:%E/georep/rclone.conf`
   und `Environment=RCLONE_CONFIG=%d/rclone.conf` (im Unit-File löst systemd `%d` auf; nur `systemd-run -p`
   tut es nicht, Playbook § 3.10). Die Härtung aus `bubatz-daily.service.j2` (`ProtectSystem=strict`,
   `ReadWritePaths`, `SystemCallFilter`) kommt in den VPS-Drop-in der Infra-Rolle, nicht ins Nutzer-Unit
   (dort fehlen die Rechte für einige Direktiven).
4. `deploy/README.md`: Installation auf kookaburra als Nutzereinheit (`mkdir -p ~/.config/georep
   ~/.config/systemd/user`, `monitor.env` aus der Vorlage, `cp deploy/systemd/georep-monitor.* ~/.config/systemd/user/`,
   `systemctl --user daemon-reload && systemctl --user enable --now georep-monitor.timer`,
   `systemctl --user list-timers`, `journalctl --user -u georep-monitor -n 50`); „von Hand" heißt durch die
   Umgebung der Einheit: `systemctl --user start georep-monitor.service` oder eine transiente Einheit
   `systemd-run --user --collect --unit=georep-monitor-hand -p EnvironmentFile=… bash …` (Playbook); Erstabruf
   (Stufe G); VPS (Stufe F); Umzug kookaburra zu VPS (`rclone copy` des Caches aus R2). Takt und Last stehen
   dabei (eine Seite 45 bis 85 s, rund 15 Paper je Tag).
5. Smoke-Test `tests/unit/test_monitor_script.py`: läuft das Skript mit `bash` in `tmp_path`, einem Stub
   `georep` am Anfang von `PATH` (schreibt eine Zeile je Aufruf in eine Datei und legt eine leere Seite an),
   `DRY_RUN=1`, `VPS_HOST=`, `R2_REMOTE=`; prüft die Reihenfolge der Aufrufe, dass `out/2025/stand.json`
   entsteht, dass ein zweiter Aufruf bei gehaltenem Lock sofort mit „läuft bereits" endet, und dass ein
   fehlschlagender Stub (`exit 1`) das Skript mit Exit 1 und „FEHLER: fetch papers" beendet; `bash -n` über
   das Skript als eigener Test. Keine Netz- oder systemd-Abhängigkeit.
6. Simulation auf kookaburra (kein echter Abruf): `monitor.env` zeigt auf den Worktree, `GEOREP_DATA_ROOT`
   und `GEOREP_CACHE_ROOT` auf eigene Ordner unter `/media/konrad/xtraspace/georep/monitor/` (nicht der
   geteilte Cache: `TextStore.save` schreibt die ganze Datei, zwei gleichzeitige Schreiber verlören Zeilen),
   `PUBLISH_DIR` ebenda, `DRY_RUN=1`; `systemd-run --user` der Einheit; danach `journalctl --user` lesen
   und `python3 -m http.server 8777 --directory …/out` zur Ansicht. Timer noch nicht aktivieren.
7. Abnahme: `uv run nox` grün; der Trockenlauf durch die Nutzereinheit endet mit Exit 0 und der
   Abschlusszeile; ein zweiter Trockenlauf ändert nichts (`rsync --dry-run` würde nichts übertragen, die
   Stamps sagen „aktuell"); `deploy/README.md` reicht, um die Einheit ohne diesen Plan zu installieren.

### Stufe F: R2 und VPS (4 h, dazu Konrads Handgriffe)

1. Skript, Schritt (8): `rclone --config … sync "$CACHE/pdf" "$R2_REMOTE/cache/pdf" --exclude manifest.jsonl`,
   dann `copyto` für `manifest.jsonl`, `text/texts.parquet`, `raw/papers.jsonl` nach `$R2_REMOTE/2025/raw/`,
   `processed/*.parquet` nach `$R2_REMOTE/2025/processed/`; `--stats-one-line` auf stderr, keine Pipe; S3-PUT
   ist atomar. Unter `DRY_RUN` mit `--dry-run`. Test: Stub `rclone` im Smoke-Test, der die Argumente
   protokolliert; mit `R2_REMOTE` gesetzt stehen die vier Aufrufe in der richtigen Reihenfolge, ohne nicht.
2. Schritt (9): die kanonische rsync-Zeile, `${DRY_RUN:+--dry-run}`, Exit-Code allein geprüft; `--delete`
   mit `--exclude=/2025/snapshots/` ist nicht nötig, weil `out/` die Schnappschüsse selbst führt. MIME-Typen
   (`.parquet` als `application/vnd.apache.parquet`, `.geojson` als `application/geo+json`) gehören in den
   Caddy-Block des Infra-Repos (Stufe F.4 des Berichtsplans).
3. Konrads Handgriffe, im `deploy/README.md` als Liste: R2-Bucket `georep` (WEUR, privat, keine Domain) und
   zwei Token (kookaburra, VPS) mit „Object Read & Write, nur Bucket"; `~/.config/georep/rclone.conf` (0600,
   Remote `georep`, `provider = Cloudflare`, `no_check_bucket = true`, Vorlage aus bb `DEPLOY.md` § 0);
   `R2_REMOTE=georep:georep`; im Infra-Repo eine Rolle `georep` (Nutzer, uv, rclone, Klon des Repos,
   `/etc/georep/monitor.env`, `/etc/georep/rclone.conf` per `LoadCredential`, die beiden Unit-Dateien aus
   `deploy/systemd/` plus Härtungs-Drop-in, Caddy-Block mit MIME-Typen); DNS zuerst (offene Frage 1), dann
   Caddy (Playbook § 3.10: sonst die ZeroSSL-Falle).
4. Abnahme: Smoke-Test grün; auf kookaburra ein echter `rclone` Trockenlauf gegen das Bucket (`--dry-run`,
   listet, überträgt nichts), sobald Konrad Bucket und Token angelegt hat; ohne Bucket endet die Stufe mit
   dem Smoke-Test und der Liste der Handgriffe. Kein Lauf gegen den VPS vor der Infra-Rolle.

### Stufe G: Erstabruf, Betrieb, Doku (2 h, Konrads Lauf rund 3 h Wanduhr)

1. Der Erstabruf ist Konrads Lauf (§ 2 des Meta-Plans): auf kookaburra durch die Nutzereinheit ohne
   `DRY_RUN`, als transiente Einheit mit derselben Umgebungsdatei, damit Log und Grenzen gelten:
   `systemd-run --user --collect --unit=georep-monitor-erstlauf -p EnvironmentFile=%h/.config/georep/monitor.env
   -p WorkingDirectory=<Repo> /usr/bin/bash <Repo>/deploy/bin/georep-monitor.sh`; erwartet 21 Seiten in 16 bis
   30 min, 4 100 PDFs in rund 2,3 h, Extraktion 3 min, Seite in Sekunden. Davor einmal mit
   `GEOREP_SOURCES__OPARL__PDF_LIMIT=50` als Stichprobe (fünf Minuten, Meta-Plan § 2), um Format, Dateinamen
   und Textextraktion der neuen PDFs zu sehen.
2. Danach `systemctl --user enable --now georep-monitor.timer`; nach dem ersten Timer-Lauf `journalctl`
   lesen und messen: Seiten, Dauer, übertragene Objekte; Zahlen datiert nach `docs/profiling/README.md`
   („Betrieb") und `STATUS.md`.
3. Doku: `architecture.md` (Module, Pipeline 15 Schritte, Datenhaltung mit Profil, Abschnitt „Betrieb"),
   `decisions.md` (ein Punkt mit den verworfenen Alternativen aus § 2), README (Profil, Befehle, Betrieb in
   drei Sätzen mit Verweis auf `deploy/README.md`), `CHANGELOG.md` unter „Unreleased", `STATUS.md`.
4. Abnahme: alle Abnahmen von A bis F; `uv run nox`, `uv run pytest -m slow`, `uv run nox -s bench` grün;
   `grep -rn "Düsseldorf\|0015" src/` zeigt nur `defaults.toml`, Vorlagentexte und Docstrings; die Profilseite
   der Simulation wurde mit headless Chrome angesehen; ohne Konrads Freigabe bleibt G.1 und G.2 als
   dokumentierter Lauf offen und wird im Abschlussbericht so genannt.

Summe: rund 26 Agentenstunden, 15 bis 20 Commits; Konrads Zeit: Bucket und Token (15 min), DNS und
Infra-Rolle (nach eigenem Ermessen), Erstabruf (3 h Wanduhr, unbeaufsichtigt).

## 6. Auswirkung auf die Berichtsseite (Abschnitt, Größe in KB, Unterseite ja/nein)

- Hauptseite (`index.html`, heute 686 KB): Datenstandzeile unverändert lang; neuer Abschnitt „Je Monat" mit
  61 Balken und Tabelle, geschätzt 15 KB SVG plus 6 KB Tabelle; Abschnitt „Laufende Wahlperiode" nur mit
  gesetzter `monitoring_url` (unter 1 KB); Downloads vier Zeilen mehr (`monatsreihe.parquet` rund 2 KB,
  `wahlbezirke_monate.parquet` rund 15 KB, dazu CSVs). Erwartet rund 710 KB, Budget 1,5 MB hält. Fällt die
  Synergiephase den Abschnitt „Je Monat" aus Budgetgründen, bleibt er der Profilseite.
- Unterseite: ja, die Seite des Profils unter `2025/` (eigene `index.html`, `karte.html`, `data/`), aus
  derselben Vorlage; Größe bei 4 100 Dokumenten geschätzt 450 KB (`dokumente.json` rund 0,5 MB statt 2,1 MB,
  weniger Begriffe mit Treffer); Abschnitte: Kopf mit Datenstand, Kernzahlen (Dokumente, mit Text, ohne
  Text, Dokumente mit Treffer, Begriffe), Karte (Treffer, Trefferquote), „Je Monat", „Je Wahlbezirk" (ohne
  Wahlbeteiligungsspalte), Begriffe mit Dialog, Methode und Grenzen (Spanne, eingefrorenes Wörterbuch),
  Downloads, Fuß.
- `pages.yml`: Laufzeit plus Sekunden; die Seite dort zeigt keinen Monitoring-Link.

## 7. Risiken und Fallstricke

- Der Server beachtet `modified_since` heute; tut er es eines Tages nicht mehr, liest der Lauf alle Seiten
  bis zum Periodenbeginn (`stop_when_older`): 21 und mehr Seiten, 16 bis 30 min, kein Fehler. Das Skript
  druckt die Seitenzahl aus `FetchReport`; ein Sprung ist im Journal sichtbar.
- `papers` ohne `--force` wird nach dem ersten Lauf übersprungen (Stamp ohne Eingaben): im Skript steht das
  `--force`; wer von Hand `georep --settings settings.2025.toml fetch` ruft, holt sonst nichts.
- Ein geändertes Paper mit neuem Dateinamen hinterlässt das alte PDF und den alten Text im Cache; Korpus
  und Seite nutzen nur den aktuellen Namen. Harmlos, aber `georep status` zählt dann mehr PDFs als Paper.
- Gelöschte Paper verschwinden nur, wenn der Lauf sie sieht (`modified_since` liefert sie, die
  ungefilterte Liste nicht): bei einem Vollabruf ohne Store bleiben keine Leichen, bei `modified_since`
  kommen sie mit. Beide Pfade sind getestet.
- Geteilter `cache_root` während Phase 3: acht Worktrees teilen `/media/konrad/xtraspace/georep/cache`,
  `TextStore.save` schreibt die ganze Datei. Die Simulation bekommt einen eigenen Cache (Stufe E.6); auf dem
  VPS gibt es nur einen Schreiber.
- Ein leerer Store nach einem fehlgeschlagenen Erstabruf: `results` wirft `EmptyResultError` (kein Treffer),
  das Skript endet mit Exit 1 und „FEHLER: run"; richtig so, nicht abfangen.
- `uv sync --locked` in der Einheit braucht Netz zu PyPI, wenn der Cache kalt ist; auf dem VPS ist das in
  Ordnung, `--offline` wäre beim ersten Lauf falsch.
- `systemd-run -p Environment=` löst `%d` nicht auf; in Unit-Dateien schon. Credential darum im Drop-in als
  `%d/rclone.conf`, in transienten Einheiten als `$CREDENTIALS_DIRECTORY/rclone.conf` im Kommando.
- rclone 1.60.1 aus Ubuntu meldet geglückte Uploads als Fehler (bb `DEPLOY.md`): `RCLONE` zeigt auf 1.75.1.
- Playbook § 3.10, mehrfach gelernt: nie `rsync | grep`, nie `|| true` hinter einer Pipeline; jede Zählung
  druckt die Zahl, nicht dass sie lief.
- `Persistent=true` holt einen verpassten Lauf nach dem Aufwachen von kookaburra nach, auch tagsüber; mit
  `RandomizedDelaySec=30m` bis zu 30 min später. Gewollt.
- Der Monatserste als `Date` in Parquet: Polars `dt.truncate("1mo")` liefert ihn; Zeitzonen spielen keine
  Rolle, weil `date` ein Datum ist. `modified` ist zeitzonenbewusst (`+02:00`), `modified_since` wird mit
  Offset gesendet; der Server hat heute `+00:00` angenommen.
- Snapshots in `test_cli.ambr` und `test_report_charts.ambr` ändern sich bewusst; nie blind `--snapshot-update`.
- Seitenbudget: beide Seiten messen, nicht schätzen (Stufe D.5).
- Düsseldorf-Konstanten: Daten nur in `settings.2025.toml` und `defaults.toml`; die Vorlage formuliert mit
  `model.stand.election`, nicht mit „2025".

## 8. Offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | Warum sie zählt | Annahme |
|---|---|---|---|
| 1 | Unter welchem Hostnamen und Pfad liegt die Seite auf dem VPS (`georep.konradvoelkel.de/` mit `/2025/`, oder ein Pfad unter einer bestehenden Domain)? | DNS muss vor Caddy stehen; die Hauptseite verlinkt relativ, ein absoluter Link von Pages bräuchte die Domain in `ALLOWED_LINKS` | `georep.konradvoelkel.de`, Hauptseite als Spiegel unter `/`, Profil unter `/2025/`; bis DNS und Rolle stehen, läuft nur die Simulation auf kookaburra und R2 |
| 2 | Bleibt GitHub Pages die Hauptseite, oder übernimmt der VPS sie? | entscheidet, ob Pages irgendwann auf den VPS verweist und ob `monitoring_url` auf Pages absolut gesetzt wird | Pages bleibt unverändert; der VPS spiegelt sie zusätzlich; nur die VPS-Kopie trägt den relativen Link |
| 3 | Dürfen die PDFs und die extrahierten Texte der laufenden Periode veröffentlicht werden (VPS, Zenodo)? | Ratsdokumente sind öffentlich, aber die Berichtsseite hat entschieden, Texte nicht zu veröffentlichen; urheberrechtlich nicht geklärt | nein: Downloads sind Metadaten und abgeleitete Tabellen; PDFs und Texte bleiben im privaten Bucket |
| 4 | Name, Region und Token des R2-Buckets | Konrads Konto; ohne Bucket endet Stufe F mit dem Smoke-Test | Bucket `georep`, WEUR, privat, zwei Token mit Bucket-Beschränkung wie bei bubatzblick; `R2_REMOTE=georep:georep` |
| 5 | Takt des Timers: täglich 04:17 Uhr plus bis 30 min, oder wöchentlich? | Last am Server (eine Seite je Lauf) und Aktualität der Seite | täglich; die Last liegt bei rund zwei Minuten und 15 Papern je Tag |
| 6 | Freigabe des Erstabrufs (16 bis 30 min Metadaten, rund 2,3 h PDFs, einmalig) und der Stichprobe (fünf Minuten, 50 PDFs) | ohne ihn gibt es keine echte Profilseite; Phase 3 endet sonst mit der Simulation | der Agent ruft nichts ab; Konrad startet die dokumentierte Einheit nach Stufe G.1 |
| 7 | Datenplattform: Zenodo-Record je Jahr mit DOI plus Hugging-Face-Dataset für die Parquet-Tabellen, oder nur eines davon; unter wessen Namen und Affiliation (HHU für GovData)? | bestimmt Datensatzkarte, Lizenzzeile, `CITATION.cff` und ob ein GovData-Eintrag überhaupt möglich ist | beides vorbereiten (Karte, Lizenz, Zitierdatei), nichts hochladen; GovData nicht verfolgen |
| 8 | Bleibt das Wörterbuch der Referenz (November 2025) für die ganze laufende Periode eingefroren, oder wird es jährlich erneuert? | Vergleichbarkeit der Monatsreihe gegen Aktualität neuer Straßen und Orte | eingefroren; eine Erneuerung wäre ein eigener, datierter Lauf mit neuem Stamp |
| 9 | Soll die Monatsreihe 2020 bis 2025 auch auf der Hauptseite stehen (rund 20 KB)? | Seitenbudget und Fokus der Hauptseite | ja, weil das Budget es erlaubt; die Synergiephase darf sie streichen |
| 11 | Soll der Trockenlauf (`DRY_RUN=1`) die Hauptseite wirklich bauen, oder soll auch sie nur geplant werden? | ohne eine echte Seite zeigt die Simulation nichts; die Hauptseite braucht kein Netz und schreibt nur in die eigene Datenwurzel | ja, sie wird gebaut; nur Abruf, rclone und rsync bleiben trocken (so umgesetzt, `deploy/README.md`) |
| 12 | Soll die Kachel „Wahlbeteiligung, Median" auf der Profilseite stehen, obwohl es zur laufenden Periode keine Wahl gibt? | sonst widerspricht die Kachel dem Satz, dass es keine Wahlbeteiligung gibt | sie bleibt und nennt die Wahl, aus der sie stammt („je Wahlbezirk, Kommunalwahl 14.09.2025") |
| 13 | Bleibt die Pages-Seite dauerhaft ohne Link auf die laufende Periode, oder soll sie später absolut auf den VPS zeigen? | ein absoluter Link bräuchte die Domain in `ALLOWED_LINKS` und damit einen Codecommit | Pages bleibt ohne Link (`report.monitoring_url` ist dort leer), nur die VPS-Kopie trägt ihn relativ |
| 10 | Reicht `modified_since` = letztes `modified` minus ein Tag, oder soll der Lauf gelegentlich (monatlich) die Liste ohne Filter bis zum Periodenbeginn lesen, um Lücken zu schließen? | ein Paper, dessen `modified` älter als der Filter ist, würde nie nachgeholt (Server-Uhrzeitfehler) | minus ein Tag reicht; ein monatlicher Volllauf (`GEOREP_SOURCES__OPARL__INCREMENTAL=false`, 21 Seiten) steht als Befehl im README, der Timer macht ihn nicht |

## 9. Vorbereitung für Option 10 (was wird konfigurierbar, welche Modulgrenze entsteht)

Konfigurierbar: `profile` (eine Datenwurzel je Profil, gemeinsam nutzbar mit Option 1 Städte und Option 2
Zeitreihe); `period.end` optional und `period.election` (Wahltag getrennt vom Periodenende, für jede Kommune
und Periode); `bootstrap.seed_corpus`; `report.regression` und `report.monitoring_url`; der ganze Betrieb über
`monitor.env` (Repo, Profil, Pfade, Ziele, Takt im Timer) ohne Code- oder Pfadänderung. Nichts
Düsseldorf-Spezifisches kommt in den Code; `settings.2025.toml` ist das Vorbild für jedes weitere Profil.

Modulgrenzen: `georep.analysis.timeline` ist eine reine Polars-Schicht (Frame zu Frame, Verträge an der
Batch-Grenze, keine Pfade); `georep.sources.oparl` und `georep.stores` tragen den Aktualisierungsmechanismus
von OParl 1.1 vollständig (geändert, gelöscht), unabhängig vom Body; `georep.report` rendert aus einem Modell
mit optionalen Teilen (Regression, Monatsreihe, Datenstand), ohne zu wissen, welches Profil es ist; `deploy/`
liegt außerhalb des Pakets und spricht mit ihm nur über die CLI, Settings und Umgebungsvariablen. Die
Infrastruktur des Servers bleibt im Infra-Repo. Gemeinsame Bausteine mit anderen Optionen: das Profil
(1, 2), erweiterte `PaperRecord`-Felder und der Upsert (4, 5), der Abschnittsmechanismus und das Seitenbudget
(alle), der Dokumentdialog auf der Profilseite (8).

## 10. Änderungen durch die Synergiephase

Stand 2026-10-12, geschrieben vom Supervisor nach [00-synergien.md](00-synergien.md). Das Fundament liegt auf
`main` (Commits `d7df0ed` bis `b8e44b1`, Branch rebased); was unten steht, gilt vor den Stufen in § 5. Für alle
Optionen (00-synergien.md, § 2 und § 5):

- **Vorlage**: `report.html.j2` ist Rahmen; ein neuer Abschnitt ist eine neue Datei
  `src/georep/report/templates/sections/NN-name.html.j2` (Nummern in 00-synergien.md § 5.1), optional mit
  `NN-name.css` und `NN-name.js` daneben; `render.sections()` bindet sie in Nummernfolge ein. Das Makro
  `term` kommt aus `templates/macros.html.j2` (`{% from "macros.html.j2" import term %}`). Ein Abschnitt, der
  nur mit einem Modellteil existiert, steht in `{% if model.<teil> %} … {% endif %}`, das Feld in `ReportModel`
  hat Default `None` und steht am Ende der Klasse.
- **JavaScript**: Abschnitts-Skripte sprechen mit `window.georep` (`select(ids, scroll)` für Zahl, Array
  oder `null`; `showDocuments(terms, title)` mit mehreren Begriffen; `rows`). Der Kartenumschalter ist
  generisch: Radio `input[name="metric"]` mit `value`, Attribut `data-class-<value>` je Fläche
  (`charts.choropleth(..., extra_classes={"<value>": classification})`), Legende `.legend#legend-<value>`.
- **Tabellen**: jede neue veröffentlichte Tabelle ist ein `PublishedTable`-Eintrag am Ende von `TABLES` in
  `src/georep/report/tables.py` (Name, Pfad-Lambda, Beschreibung, Spaltendoku, CSV-Regeln, `optional`);
  `published_tables`, `COLUMN_DOCS`, `DESCRIPTIONS` und `export.csv_plan` gibt es nicht mehr.
- **Regression**: `analysis.regression.regression_pair(frame, exclude, *, x, y, y_scale)` rechnet beide
  Spalten von Tabelle 5 für jede Kennzahlspalte; die Ausreißer kommen aus `settings.analysis.exclude_districts`
  (`defaults.toml`, `[analysis]`), `OUTLIERS` gibt es nicht mehr.
- **Settings**: neue Tabellen am Ende von `defaults.toml` in einem Block `# --- Option NN`, neue Modelle vor
  `class Settings`, neue Felder am Ende von `Settings`; Pfade und reine Anzeigewerte aus `fingerprint()`
  ausschließen (Kommentar dort). Neue Layout-Properties am Ende der Klasse vor `runtime_dirs`.
- **Pipeline**: neue Schritte mit Kommentar `# --- Option NN` an der Stelle ihrer Abhängigkeit; neue Eingaben
  von `report` am Ende seines Tupels.
- **Tests**: `test_cli.py`, `test_pipeline.py`, `test_report_build.py` zählen Schritte und Dateien aus
  `build_steps` und dem Register; eigene Erwartungen in eigene Tests. Den Snapshot `test_cli.ambr`
  (`georep steps`) bewusst erneuern, Diff im Commit.
- **Doku**: `decisions.md` neuer Punkt ohne feste Nummer („## Punkt: <Titel> (Option NN, Datum)"; Punkt 21
  ist das Fundament, der Supervisor nummeriert beim Merge); CHANGELOG unter „Unreleased" als eigener Absatz.
- **Vorschau**: lokaler Server auf Port `8700 + NN`; `.claude/launch.json` je Worktree anlegen. Browser-Prüfung
  nach § 8.4 des Meta-Plans.
- **Cache**: `cache_root` ist geteilt; nichts außer `bootstrap` schreibt den Textstore der Hauptperiode.
- **Fragen**: die Antworten und Vorentscheidungen stehen in [fragen.md](fragen.md); neue Fragen in § 8 dieses
  Plans eintragen, der Supervisor sammelt sie.

Für Option 7 im Besonderen:

- **Stufe A ist kleiner**: `Settings.profile`, `Layout` mit Profil (`data_root/2025/`, `cache_root/2025/pdf`
  und `cache_root/2025/text/texts.parquet`), `Period.end` optional, `Period.election` und `election_day` liegen
  im Fundament F4. Im Profil `settings.2025.toml`: `profile = "2025"`, `[period] start = 2025-09-15`,
  `end = ""` (der tiefe Merge ließe das Datum aus `defaults.toml` sonst stehen), `election = 2025-09-14`.
  `data_stand` nimmt `period.election_day`; `DataStand.period_end` ist `None` bei offener Periode und der Rahmen
  schreibt dann „bis heute (laufende Wahlperiode)". Zu bauen bleiben `[bootstrap] seed_corpus`, `[report]
  regression` und `monitoring_url`, `in_period` kennt das offene Ende schon.
- **Cache je Profil**: PDFs und Textstore der laufenden Periode liegen unter `cache_root/2025/`; das
  R2-Layout folgt dem (`cache/2025/pdf/`, `cache/2025/text/texts.parquet`); `rclone sync` entsprechend.
- **Abschnitte**: `sections/55-monate.html.j2` (Balken über `charts.Axes`, Fundament F7) und
  `sections/75-laufend.html.j2` (nur mit `model.monitoring_url`); die Zweige für `model.regression is None`
  liegen in `sections/30-zusammenhang.html.j2` und `sections/20-karte.html.j2` (`{% if %}` um Streudiagramm,
  Tabelle 5 und das Radio „Wahlbeteiligung").
- **Tabellen**: `monatsreihe`, `wahlbezirke_monate` als Einträge in `TABLES`.
- **Record und Löschungen**: 04 merged vor 07 und erweitert `PaperRecord` (Schema 3); `FetchReport.deleted_ids`
  und `PaperStore.upsert(deleted=…)` baut 07 darauf.
- **Paketprofil**: nach dem Merge von 01 wandert `settings.2025.toml` nach `src/georep/profiles/` und wird mit
  `--profile 2025` geladen; bis dahin `--settings settings.2025.toml`.
- **Reihenfolge**: 07 merged als Letzte.
- **Fragen**: 7.1, 7.2, 7.4, 7.6 offen (fragen.md); 7.3, 7.5, 7.7 bis 7.10 wie angenommen.

## 11. Umsetzung: Abweichungen vom Bauplan und Messwerte (2026-10-12)

Umgesetzt sind die Stufen A bis F und die Doku aus G; der Erstabruf (G.1, G.2) bleibt Konrads Lauf.
Abweichungen vom Bauplan, je mit Grund:

- **Umgebungsvariablen des Skripts heißen `MONITOR_*`, nicht `GEOREP_*`** (§ 5, Stufe E.1 hatte
  `GEOREP_REPO` und `GEOREP_PROFILE` vorgesehen). `GEOREP_` ist das Präfix von pydantic-settings:
  `GEOREP_PROFILE=settings.2025.toml` beendet jeden `georep`-Aufruf mit einem Validierungsfehler, weil
  `profile` ein Ordnername ist (nachgestellt am 2026-10-12). Nur `GEOREP_DATA_ROOT`, `GEOREP_CACHE_ROOT`
  und `GEOREP_LOG_LEVEL` sind weiter echte Einstellungen aus der Umgebung. Den Profilnamen selbst
  nennt die Umgebungsdatei nicht: das Skript fragt ihn mit `georep paths` ab (siehe unten).
- **`DRY_RUN=1` baut die Hauptseite wirklich.** Sonst hätte die Simulation keinen
  Veröffentlichungsordner zu zeigen: ohne Abruf hat das Profil keine Dokumente, seine Kette kann nur
  planen. Netzschritte, rclone und rsync bleiben trocken (Frage 11).
- **Der Kettentest der Stufe B lässt `timeline` aus.** Der Schritt braucht den Index, und die vier
  PDF-Fixtures treffen keinen Begriff des Mini-Wörterbuchs (nachgerechnet). Die Monatsreihe prüfen
  stattdessen `tests/unit/test_timeline.py` (Mini-Fixture, gegen Polars nachgerechnet) und
  `tests/property/test_timeline_props.py`.
- **`KeyFigures.documents_without_text` ist eine Eigenschaft, kein Feld** (abgeleitet aus zwei Zahlen,
  die schon im Modell stehen).
- **`Axes.axis_titles` lässt leere Titel weg und `tick_labels(x=False)` die x-Zahlen** (Fundament F7
  erweitert, Ausgabe des Streudiagramms unverändert); die y-Achse der Balken bekommt ganze Zahlen, weil
  `nice_ticks` bei wenigen Dokumenten je Monat halbe Dokumente beschriftet hätte.
- **Zwei Prädikate mehr in `georep.contracts`**: `months_in_order` und `keys_sorted_unique`.
- **Gefundener Fehler, nicht geplant**: die Nachbedingung `added + updated <= total` von
  `PaperStore.upsert` galt schon vor dieser Option nicht, wenn eine Charge dieselbe ID zweimal enthält
  (die hypothesis-Eigenschaft hat es gefunden); sie heißt jetzt `added <= total + removed`.

### Nach dem Review (2026-10-12)

Das Review fand zehn Punkte, alle im Betriebsteil; jeder ist behoben, die meisten mit einem roten
Test zuerst:

1. **Die Einheit wäre nie gestartet**: `WorkingDirectory=${MONITOR_REPO}` — systemd ersetzt
   Variablen nur in `ExecStart=` und Verwandten, `systemd-analyze --user verify` meldete „path is
   not absolute". Die Zeile ist weg (das Skript wechselt selbst), und ein Test lässt
   `systemd-analyze --user verify` über beide Unit-Dateien laufen. Die Simulation lief an dem
   Fehler vorbei, weil `systemd-run` das Arbeitsverzeichnis selbst setzt.
2. **`stand.json` fehlte im veröffentlichten Baum**: er entstand nach dem rsync, und der rsync der
   Profilseite hatte ihn mit `--delete` zuvor entfernt. Jetzt steht er davor und ist vom `--delete`
   ausgenommen; `dauer_s` zählt bis dahin, die Abschlusszeile nennt die ganze Dauer.
3. **Ein abgebrochener Schnappschuss blockierte alle späteren Läufe** (der Monatsordner ist die
   Sperre). Er entsteht jetzt in `.<monat>.neu` daneben und wandert per `mv` hinein.
4. **Der Profilname stand zweimal da** (`settings.2025.toml` und `monitor.env`). Neu: `georep paths`
   druckt Profil und alle Layout-Pfade als `key=wert`, das Skript liest sie; `MONITOR_PROFILE` gibt
   es nicht mehr. Verworfen: das Skript aus `georep status` parsen (Menschentext, den jede weitere
   Option umformulieren darf) und den Namen weiter spiegeln (die Abweichung fiel erst im Betrieb
   auf). Fehlt im echten Lauf danach eine Seite, ist das ein Fehler statt eines stillen Exit 0.
5. Die Monatsspalte sortiert numerisch (`data-value` = Jahr mal zwölf plus Monat).
6. Die Beschriftungen der Balken überlappten bei 14 bis 23 Monaten mit nur einem Januar; der
   Abstand kommt jetzt aus der Breite eines Balkenplatzes, geprüft über acht Reihenlängen.
7. `flock` wird wie `rsync` vorher geprüft (sonst endete jeder Lauf still mit „läuft bereits");
   `deploy/README.md` sagt, dass die Ausgabe eines Schritts erst nach dem Schritt im Journal steht.
8. `index.html.stamp.json` wird nicht mehr veröffentlicht.
9. `monitor.env.example` trägt nur noch Platzhalter; README-Zahlen nachgezogen.
10. `systemd-run -p EnvironmentFile=%h/…` löst `%h` nicht auf („Path %h/… is not absolute",
    am 2026-10-12 mit einer transienten Einheit geprüft, die nur `true` ausführt); die Anleitung
    schreibt `$HOME` aus.

Dazu ein Test für den Kopfzweig „Dokumente ohne Text" (auf einem Korpus mit leeren Texten) und die
Einzahl in diesem Satz.

Gemessen am 2026-10-12 im Worktree (13 Kerne geteilt, `POLARS_MAX_THREADS=4`):

| Größe | Wert |
|---|---|
| `uv run nox` | 16 bis 25 s |
| `uv run pytest -m slow` | 12 s |
| `uv run georep run` (nur `timeline` und `report` offen) | 3,3 s, davon `timeline` 0,2 s |
| `uv run georep run --force` (zehn Offline-Schritte) | 11,5 s, davon `timeline` 0,2 s und `report` 1,4 s |
| `monatsreihe.parquet` | 61 Zeilen (2020-09 bis 2025-09, lückenlos), 2 490 Bytes, Summe 19 108 Dokumente |
| `wahlbezirke_monate.parquet` | 2 491 Zeilen, 3 740 Bytes, Summe 29 573 Treffer |
| Hauptseite `index.html` | 721 092 Bytes (vorher 686 088), Budget 1,5 MB |
| Profilseite aus dem Testdatensatz | 126 312 Bytes, vier Dokumente in vier Monaten |
| Trockenlauf durch die Nutzereinheit | 7 bis 9 s, Exit 0 |

`uv run nox -s bench` ist unter der Last dieser Phase nicht aussagekräftig: derselbe Commit verglich
sich am 2026-10-12 bei `load average` 14 einmal rot (pypdf-Extraktion und FlashText-Matcher 25 bis 53 %
über der Minute alten Baseline) und unmittelbar danach grün. Beide Messpunkte liegen in Funktionen, die
diese Option nicht anfasst; der Schritt `timeline` hat keine Bench-Stufe, weil er 0,2 s auf dem vollen
Korpus braucht. Die Messung gehört bei ruhigem Rechner wiederholt.

Die Seiten sind in Hell und Dunkel mit headless Chrome angesehen (Streifen im Scratchpad); bei 375 px
Breite ist `scrollWidth` gleich `clientWidth`, es gibt kein waagerechtes Scrollen.
