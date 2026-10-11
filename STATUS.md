# Status

Stand 2026-10-11, `main` auf `v0.10.0`. Der Umbau in sieben Phasen ist abgeschlossen
(`docs/development-plan-2026-10.md`), die Berichtsseite ist gebaut und veröffentlicht (`docs/plan-report-2026-10.md`,
Stufen A bis G, Seite unter <https://konradvoelkel.github.io/geographic-representation-dus/>). Aufbau in
`docs/architecture.md`, Gründe in `docs/decisions.md`. Fakten mit Datum, Invarianten ohne.

## Abgeschlossen

- Phase 0 (`v0.1.0`): uv-Projekt auf Python 3.14, Charakterisierungstests, nox, pre-commit, CI, mechanische Ruff-Commits.
- Phase 1 (`v0.2.0`): atomare Schreibvorgänge, Session mit Timeout und Retry, Fehlerisolation im Download, Guards, deterministische Ausgaben, Domänenfehler.
- Phase 2 (`v0.3.0`): Settings in TOML, OParl 1.1 als Vertrag, Layout mit Schreibschutz auf `reference/`, Polars-Kette mit Parquet, Schrittregister mit Stamps, CLI `georep`.
- Phase 3 (`v0.4.0`): Fetch- und Cache-Schicht ohne geopandas und osmnx; der Code der Arbeit ist vollständig ersetzt.
- Phase 4 (`v0.5.0`): Tests ausgebaut. `tests/property/` mit hypothesis: ein lesbares Orakel des Matcher-Vertrags, Invarianten für Wörterbuch, Aggregation, POI-Bereinigung, Straßen, Treffer, Index, STRtree, OParl-Roundtrip, Stores und `deep_merge`. Snapshot für `georep steps`, nox `test` parallel mit Abdeckung als Untergrenze (90 %).
- Phase 5 (`v0.6.0`): Profiling-Infrastruktur. `georep profile`, `nox -s bench` (pytest-benchmark, rot ab 20 % langsamer im Minimum), Protokoll `PdfTextExtractor`. Messung in `docs/profiling/README.md`: Offline-Lauf 6,3 s, davon 4,1 s FlashText; Extraktion 38 ms je PDF; pypdf 6.20.0 reproduziert 197 von 200 Texten der Arbeit zeichengleich. Empfehlung: pypdf und FlashText bleiben, kein Rust-Port.
- Phase 6 (`v0.7.0`): Design by Contract. 80 deal-Decorators an 30 Funktionen in `search`, `analysis`, `prep`, `geo`, `layout`, `stores`, `http`, `settings` und `sources`; Prädikate in `georep.contracts`; `settings.contracts = "off"` schaltet ab, Overhead unter einem Prozent. Fetcher werfen nur `FetchError` oder `NetworkError`, die CLI meldet einen abgebrochenen Abruf als eine Zeile. `deal.cases` greift zehn reine Funktionen an, `nox -s verify` (crosshair) fand und `nox -s mutate` (pytest-gremlins, 79 % getötet) deckte je einen echten Fehler auf: `street_names` bei kaputter Overpass-Antwort und deals nicht reentranter `HasPatcher`, der nach `deep_merge` Socket und stdout gepatcht ließ. Beides behoben, `docs/mutation-2026-10-11.md`.
- Phase 7 (`v0.8.0`): Abschluss. README aus Sicht eines frischen Klons (geprüft am 2026-10-11 auf xtraspace: `uv sync --locked`, `bootstrap`, `run` in 6 s, `regress`, `nox`, slow-Test), `docs/architecture.md` und `docs/decisions.md` ersetzen den Plan, der archiviert ist; Code-Docstrings verweisen auf die lebenden Beschreibungen. Kein Pull Request an `lubar102` (Konrads Entscheidung, decisions.md Punkt 19).

- Berichtsseite (`v0.9.0`): Schritt `report` als neunter Offline-Schritt; `data/site/index.html` (400 KB, inline SVG und JavaScript, hell und dunkel, Deutsch mit englischer Kurzfassung) und `data/site/data/` mit den sechs Tabellen als Parquet und CSV, `wahlbezirke.geojson`, `schema.json`, je mit SHA-256 auf der Seite. Mini-Fixture mit GeoJSON, `report/` mit `model`, `geometry`, `charts`, `render`, `build`; Lizenzen des Open-Data-Portals am 2026-10-11 auf den Datensatzseiten nachgesehen. Geprüft in Hell und Dunkel mit headless Chrome.

- Stufe G (`v0.10.0`): Dokumente je Begriff als nachgeladener Dialog aus `dokumente.json`, Orte mit Namen auf der Karte, `karte.html` mit Leaflet (gepinnt) und OpenStreetMap-Kacheln als zweite Datei.

- Option 08 Suche (Branch `feat/08-suche`, 2026-10-12, im Review): Abschnitt `15-suche` auf der Berichtsseite mit Suchfeld, Vorschlagsliste nach dem APG-Combobox-Muster, Ergebnisblock und Markierung auf der Karte; `report/search.py` baut 4176 Einträge (2828 Straßen, 1239 Orte, 68 beides, 41 Wahlbezirksnamen), die als JSON in der Seite liegen. Plan und Abnahme: `docs/plans/08-suche.md`.
- Option 02, Zeitreihe (Branch `feat/02-zeitreihe`, auf `main` rebased 2026-10-12, im Review): eine Wahlperiode ist ein
  Profil (`profiles/duesseldorf-2014.toml`, Daten unter `data_root/2014-2020/`), der Flächen-Crosswalk rechnet die
  Wahlzahlen eines älteren Stimmbezirkszuschnitts summentreu auf die Wahlbezirke der Auswertung um, der
  Schritt `compare` und der Abschnitt „Zwei Wahlperioden" stellen beide Perioden nebeneinander
  (`profiles/duesseldorf-vergleich.toml`). Geprüft offline auf der erfundenen Mini-Periode
  `tests/fixtures/mini-2014/`; der echte Abruf der Periode 2014 bis 2020 (rund 3 h Metadaten, 8 bis 11 h
  PDFs) ist vorbereitet und wartet auf Konrads Lauf (README, „Zweite Periode abrufen"). Bis dahin fehlt der
  Abschnitt auf der veröffentlichten Seite.
- Option 01, Städte (Branch `feat/01-staedte`, auf `main` rebased 2026-10-12, im Review): jede Kommune ist ein
  Profil im Paket (`src/georep/profiles/<slug>.toml`, gewählt mit `--profile`, `GEOREP_PROFILE` oder
  `default_profile`, mit `base` auf einem anderen aufbauend); `defaults.toml` ist stadtneutral, im Code steht
  kein Stadtwort. Neu sind der Schritt `shapes` (jede Quellgeometrie wird `interim/stimmbezirke.geojson`,
  GeoJSON oder Shapefile-Zip über pyshp), `data/summary.json` je Stadt und `georep publish` mit der
  Vergleichsseite `vergleich.html`. Mitgeliefert ist neben Düsseldorf das Profil Mönchengladbach (AGS
  05116000, OParl-Body 0011, votemanager der ITK Rheinland); Düsseldorf rechnet unverändert (Golden Master,
  gleiche Zahlen, gleiche Adresse). Plan und Abnahme: `docs/plans/01-staedte.md`, Runbook für den vollen
  Abruf einer neuen Stadt: `docs/runbook-stadt.md`.

## Zahlen (2026-10-11)

- Option 06 Gewichtung (Branch `feat/06-gewichtung`, 2026-10-12, im Review): `analysis/weights.py` rechnet gewichtete Trefferquoten (Maximum über die Begriffe mal Dokumentart mal Thema, jeder Faktor in [0, 1]), `analysis/topics.py` ein Themenmodell mit TF-IDF und NMF (scikit-learn, der einzige Ort mit diesem Import). Zwei Schritte (`topics` 9 s, `weights` 1 s), vier Tabellen, der Seitenabschnitt `34-gewichtung` mit der Sensitivitätstabelle. Einheitsgewichte reproduzieren `anzahl_treffer` (29 573) und Tabelle 5 exakt; `wahlbezirke_auswertung.parquet` und `inverted_index.parquet` bleiben byteidentisch.

- Option 03, Kontrollvariablen (Branch `feat/03-kontrollvariablen`, 2026-10-12, im Review): Fremddaten je
  Raumeinheit unter `context/` (Quartiersatlas 2024, 2,3 MB, dl-de/by-2-0, README mit Prüfsummen), die drei
  Schritte `context_data`, `context` und `controls`, `georep.crosswalk.area_shares`/`district_weights`,
  `georep.analysis.ols` (einmal gegen statsmodels geprüft, Abweichung 4,0e-14), drei Download-Tabellen und die
  Abschnitte „Kontrollvariablen" und „Abgeleitete Daten" auf der Seite. Befund: mit den Kontrollvariablen
  erklärt das Hauptmodell R² = 0,89 statt 0,03, der Koeffizient der Trefferquote sinkt auf 41,33 mit p 0,133.

## Zahlen (2026-10-12, Branch `feat/03-kontrollvariablen` nach dem Rebase auf 08, 05 und 06)

- Tests: 517 gesammelt, davon 492 schnelle, elf `slow` und vierzehn `bench`; schnelle Suite parallel in rund 22 s; Abdeckung 98,5 %; `nox -s verify` rund 4 min (mit `ordinal_score`).
- Laufzeit: voller Offline-Lauf rund 16 s über fünfzehn Schritte (Themenmodell 7,4 s, Index 4,1 s, Gewichtung 0,5 s, `context` 0,4 s, `controls` unter 0,1 s, Berichtsseite 1,4 s); `pytest -m slow` 49 s; `nox -s bench` grün gegen die frische Baseline.
- Berichtsseite: `index.html` 986 KB (gzip 168 KB, Budget 1,5 MB), sechzehn veröffentlichte Tabellen, 37 Dateien zusammen 10,6 MB; alle zwölf Abschnitte in Nummernfolge, in Hell und Dunkel mit headless Chrome angesehen.
- Quelltext: 51 Python-Dateien unter `src/`, rund 9800 Zeilen.

Davor, je vor dem Rebase gemessen: Option 06 rund 19 s Lauf und `index.html` 933 KB; Option 03 allein 10 s
Lauf und 764 KB. Mutation: `analysis/weights.py` 83 % (`docs/mutation-2026-10-12.md`), `analysis/` auf dem
Branch 03 tötet 133 von 175 Mutanten (76 %); die Überlebenden sind Vertrags-Lambdas an ihren Grenzen und
`frozen=True` an dataclasses. Mit sechs Arbeitern wurde die Sitzung unter der Last der acht parallelen
Agenten abgeschossen (SIGTERM bei 190 von 208); drei Arbeiter und nur `analysis/` laufen in sieben Minuten
durch.

## Bekannt

- deal 4.24.6: `deal.raises` vergleicht exakte Typen, keine Unterklassen; `deal.has()`/`deal.pure` sind nicht reentrant (Patch bleibt nach Rekursion stehen). Beides umschifft (NetworkError, `deal.safe` für `deep_merge`), nicht upstream gemeldet.
- Zwölf überlebende Mutanten liegen in Vertrags-Lambdas (Grenzen von r und p); kein Test verletzt sie genau an der Grenze. Bewusst nicht nachgezogen; in `analysis/weights.py` sind es 25 derselben Sorte plus ein äquivalenter (`docs/mutation-2026-10-12.md`).
- `nox -s mutate` lässt `analysis/topics.py` aus: jeder Mutant dort lässt die schnelle Suite laufen, und die rechnet seit dem Themenmodell mehrfach NMF (Lauf am 2026-10-12 nach 35 Minuten abgebrochen, gezielt je Modul vier Minuten). Die schnelle Suite selbst ist dadurch rund 5 s langsamer; hingenommen.
- Ein voller `georep fetch` von Grund auf lief noch nie; er dauert Stunden und ist wiederaufnehmbar. Hochrechnung aus der Stichprobe: 5,8 h Abruf, 2,8 GB, 12 min Extraktion.
- Auf Konrads Rechner liegen seit dem 2026-10-11 die ersten 200 PDFs nach Paper-ID unter `cache_root/pdf/`; `georep status` zeigt `pdfs` als „offen: Settings geändert", weil `--limit 200` im Stamp steht. Das ist richtig so.
- Labels, die sich nur durch ein Komma unterscheiden, fallen in der POI-Bereinigung zusammen (Verhalten der Arbeit, durch das Wörterbuch harmlos).
- Das Themenmodell ist je Rechner und je Thread-Zahl reproduzierbar, nicht darüber hinaus: zwischen 13 und 2 BLAS-Threads unterscheiden sich `themen.parquet` und `themen_anteile.parquet` in den letzten Stellen (gemessen 2026-10-12), Labels und Kennzahlen bleiben gleich. Die Golden-Master-Tests prüfen darum Invarianten, nicht Zahlen.
- Die Themen tragen Wörter, keine Deutung: die Nummern gelten nur für diesen Datenstand, ein Lauf über andere Dokumente vergibt sie neu. Thema 19 ist das breite Stadtthema („düsseldorf, innen, …"), der Stadtname steht bewusst nicht in der Stoppwortliste.
- Der Settings-Fingerprint ist global: ein neuer Schlüssel unter `[weights]` oder `[topics]` lässt alle Schritte einmal neu laufen (19 s). Hinnehmbar; ein Fingerprint je Schritt ist zurückgestellt (`docs/plans/00-synergien.md`, § 8).
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab (`docs/baseline-2026-10-10.md`).
- Der Stamp des Schritts `report` liegt als `site/index.html.stamp.json` im veröffentlichten Ordner; harmlos, aber mit dabei.
- Der OParl-Server liefert für Düsseldorf keine Urheberfelder: 0 von 19 108 Rohobjekten und keines der sechs Paper der Seite vom 2026-10-09, auch der „Antrag FDP" nicht. Option 04 leitet den Urheber darum aus `paperType`, Titel und Textkopf ab (Deckung 98,3 %); `georep fetch papers --max-pages 1` ist die Probe, ob sich das geändert hat, und die Quelle `oparl` greift dann ohne Codeänderung.
- Im Wahlbezirk 11 ist Die Linke nicht angetreten (0 Stimmen; die Stimmbezirks-CSV führt dort die 0, anderswo Dutzende). Der Abgleich Dokumentanteil gegen Stimmenanteil lässt solche Bezirke je Partei aus, Die Linke hat also n = 40 statt 41.
- Die Ergebnis-CSV der Ratswahl heißt im Open-Data-Portal inzwischen `…_Stimmbezirke_1.csv` (Datensatzseite am 2026-10-11); `profiles/duesseldorf.toml` zeigt auf `…_0.csv`, woher die Referenz stammt. Vor einem `fetch opendata` nachsehen.
- Mönchengladbach (Option 01, 2026-10-12): Profil, Kette und Vergleichsseite stehen, der volle Abruf steht aus (`docs/runbook-stadt.md`, 3 bis 5 h). Bis sein Paket unter `reference/moenchengladbach/` liegt, meldet `georep publish` die Stadt als „kein Lauf“ und baut keine Vergleichsseite; CI überspringt sie. Der Marker `betrifft` kam in der PDF-Stichprobe in 0 von 5 Dokumenten vor (alles Fraktionsanträge der laufenden Periode) — ohne Marker durchsucht die Kette den ganzen Text; das Runbook misst am echten Korpus nach (Frage 1.5).
- Die votemanager-CSVs der ITK Rheinland tragen keine Lizenzangabe; die Seite nennt Quelle und Herausgeber und schreibt „Lizenz laut Anbieter nicht angegeben“ (Frage 1.4).
- Mönchengladbachs Drucksachennummern tragen kein Kürzel des Gremiums (`0682/XI`, Stichprobe vom 2026-10-12, Body 0011). Das Profil lässt `bodies.reference_pattern` darum leer; der Abschnitt „Gremien" zeigt für diese Stadt 100 % „unbekannt". Woher das Gremium käme (OParl-Feld `organization` der Vorlage oder die Sitzungszuordnung), misst der volle Lauf nach (`docs/plans/01-staedte.md`, § 8, Frage 1.12).
- Der Stadtbezirk Mönchengladbachs steckt im ersten Zeichen der Stimmbezirksnummer (`10401`: Stadtbezirk 1, Wahlbezirk 04, Stimmbezirk 01); das Profil liest ihn mit `columns.results.city_district_from_precinct`. Bestätigt ist die Regel bisher nur an der Fixture (Wahlbezirke 04, 09, 23) und an der Zahl der Stadtbezirke (vier); der volle Lauf prüft sie gegen die Wahlbezirks-CSV (`docs/plans/01-staedte.md`, § 8, Frage 1.13).

## Nächster Schritt

Der Ausbau in acht Optionen nach `docs/plan-ausbau-2026-10.md` (Städte, Zeitreihe, Kontrollvariablen, Parteien,
Gremien, Gewichtung, Monitoring, Suche), geführt von einem Supervisor-Agenten mit acht Unteragenten auf eigenen
Branches. Stand 2026-10-12: Phase 0 und 1 abgeschlossen (acht Worktrees auf xtraspace, acht Pläne unter
`docs/plans/` auf den Branches), Phase 2 abgeschlossen: `docs/plans/00-synergien.md` und das Fundament F1 bis F7
auf `main` (Abschnittsmechanismus der Seite, Register der Tabellen, `regression_pair`, Profil und offene Periode,
Crosswalk-Kern, Achsen-Helfer, Zähl-Tests), die Fragen der Pläne gebündelt in `docs/plans/fragen.md`; Phase 3
(Implementierung) läuft; Option 08 (Suche) ist gemerged (2026-10-12), Option 05 (Gremien) ist auf `feat/05-gremien` fertig und im Review: zwei neue
Offline-Schritte (`bodies`, `body_hits`, zusammen 0,2 s), drei neue veröffentlichte Tabellen, ein dritter
Kartenumschalter und der Abschnitt „Gremien"; 304 Tests statt 272, voller Offline-Lauf rund 9 s,
`index.html` 732 KB, `wahlbezirke_auswertung.parquet` byteidentisch. Der Plan der Berichtsseite ist mit Stufe G vollständig umgesetzt. Die Seite wird bei jedem Push auf `main` neu gebaut und veröffentlicht Option 07 (Monitoring) liegt auf `feat/07-monitoring` im Review: Profil der laufenden Periode, inkrementeller Abruf mit Löschungen, Schritt `timeline`, Abschnitte „Je Monat" und „Laufende Wahlperiode", Lauf-Skript und systemd-Einheiten unter `deploy/`. Der Erstabruf (16 bis 30 min Metadaten, rund 2,3 h PDFs) ist dokumentiert, aber nicht gelaufen; er gehört Konrad (`deploy/README.md`).
(`.github/workflows/pages.yml`, Pages-Quelle „GitHub Actions" seit 2026-10-11); abgenommen am 2026-10-11: Workflow
grün, Seite erreichbar, Downloads laden, SHA-256 stimmen. Optional nach Bedarf: Stufe G des Plans (Dokumente je
Begriff: erledigt) und der Umzug auf Konrads VPS (`rsync` von `data/site`, Stufe F.4).

Außerdem offen, wenn jemand es will: ein voller `georep fetch` von Grund
auf (Stunden; zeigt, ob der OParl-Server `modified_since` beachtet); ein Ersatz für FlashText oder pypdf nur
nach neuer Messung (`docs/decisions.md`, Punkt 14); die beiden deal-Eigenheiten upstream melden; die Abweichung
in Tabelle 5 „ohne Ausreißer" mit Lukas klären, falls es je wieder darauf ankommt.
