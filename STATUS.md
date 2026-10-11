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

## Zahlen (2026-10-11)
- Option 06 Gewichtung (Branch `feat/06-gewichtung`, 2026-10-12, im Review): `analysis/weights.py` rechnet gewichtete Trefferquoten (Maximum über die Begriffe mal Dokumentart mal Thema, jeder Faktor in [0, 1]), `analysis/topics.py` ein Themenmodell mit TF-IDF und NMF (scikit-learn, der einzige Ort mit diesem Import). Zwei Schritte (`topics` 9 s, `weights` 1 s), vier Tabellen, der Seitenabschnitt `34-gewichtung` mit der Sensitivitätstabelle. Einheitsgewichte reproduzieren `anzahl_treffer` (29 573) und Tabelle 5 exakt; `wahlbezirke_auswertung.parquet` und `inverted_index.parquet` bleiben byteidentisch.

## Zahlen (2026-10-12, Branch `feat/06-gewichtung`)

- Tests: 308, davon zwei `slow` und zwölf `bench`; schnelle Suite parallel in 25 s; Abdeckung 98,6 %.
- Laufzeit: voller Offline-Lauf rund 19 s (Themenmodell 9 s, Index 4 s, Gewichtung 1 s, Berichtsseite 1,6 s); `pytest -m slow` 43 s; `nox -s bench` grün gegen die frische Baseline; `nox -s verify` rund 4 min.
- Berichtsseite: `index.html` 726 KB (Budget 1,5 MB), 23 Download-Dateien, 25 Dateien zusammen 10,2 MB.

## Bekannt

- deal 4.24.6: `deal.raises` vergleicht exakte Typen, keine Unterklassen; `deal.has()`/`deal.pure` sind nicht reentrant (Patch bleibt nach Rekursion stehen). Beides umschifft (NetworkError, `deal.safe` für `deep_merge`), nicht upstream gemeldet.
- Zwölf überlebende Mutanten liegen in Vertrags-Lambdas (Grenzen von r und p); kein Test verletzt sie genau an der Grenze. Bewusst nicht nachgezogen.
- Ein voller `georep fetch` von Grund auf lief noch nie; er dauert Stunden und ist wiederaufnehmbar. Hochrechnung aus der Stichprobe: 5,8 h Abruf, 2,8 GB, 12 min Extraktion.
- Auf Konrads Rechner liegen seit dem 2026-10-11 die ersten 200 PDFs nach Paper-ID unter `cache_root/pdf/`; `georep status` zeigt `pdfs` als „offen: Settings geändert", weil `--limit 200` im Stamp steht. Das ist richtig so.
- Labels, die sich nur durch ein Komma unterscheiden, fallen in der POI-Bereinigung zusammen (Verhalten der Arbeit, durch das Wörterbuch harmlos).
- Das Themenmodell ist je Rechner und je Thread-Zahl reproduzierbar, nicht darüber hinaus: zwischen 13 und 2 BLAS-Threads unterscheiden sich `themen.parquet` und `themen_anteile.parquet` in den letzten Stellen (gemessen 2026-10-12), Labels und Kennzahlen bleiben gleich. Die Golden-Master-Tests prüfen darum Invarianten, nicht Zahlen.
- Die Themen tragen Wörter, keine Deutung: die Nummern gelten nur für diesen Datenstand, ein Lauf über andere Dokumente vergibt sie neu. Thema 19 ist das breite Stadtthema („düsseldorf, innen, …"), der Stadtname steht bewusst nicht in der Stoppwortliste.
- Der Settings-Fingerprint ist global: ein neuer Schlüssel unter `[weights]` oder `[topics]` lässt alle Schritte einmal neu laufen (19 s). Hinnehmbar; ein Fingerprint je Schritt ist zurückgestellt (`docs/plans/00-synergien.md`, § 8).
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab (`docs/baseline-2026-10-10.md`).
- Der Stamp des Schritts `report` liegt als `site/index.html.stamp.json` im veröffentlichten Ordner; harmlos, aber mit dabei.
- Die Ergebnis-CSV der Ratswahl heißt im Open-Data-Portal inzwischen `…_Stimmbezirke_1.csv` (Datensatzseite am 2026-10-11); `defaults.toml` zeigt auf `…_0.csv`, woher die Referenz stammt. Vor einem `fetch opendata` nachsehen.

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
`index.html` 732 KB, `wahlbezirke_auswertung.parquet` byteidentisch. Der Plan der Berichtsseite ist mit Stufe G vollständig umgesetzt. Die Seite wird bei jedem Push auf `main` neu gebaut und veröffentlicht
(`.github/workflows/pages.yml`, Pages-Quelle „GitHub Actions" seit 2026-10-11); abgenommen am 2026-10-11: Workflow
grün, Seite erreichbar, Downloads laden, SHA-256 stimmen. Optional nach Bedarf: Stufe G des Plans (Dokumente je
Begriff: erledigt) und der Umzug auf Konrads VPS (`rsync` von `data/site`, Stufe F.4).

Außerdem offen, wenn jemand es will: ein voller `georep fetch` von Grund
auf (Stunden; zeigt, ob der OParl-Server `modified_since` beachtet); ein Ersatz für FlashText oder pypdf nur
nach neuer Messung (`docs/decisions.md`, Punkt 14); die beiden deal-Eigenheiten upstream melden; die Abweichung
in Tabelle 5 „ohne Ausreißer" mit Lukas klären, falls es je wieder darauf ankommt.
