# Architektur

Stand 2026-11-23, `v0.17.0`. Diese Datei beschreibt, was das Programm ist und wie es gebaut ist. Warum es so
gebaut ist, steht mit den verworfenen Alternativen in [decisions.md](decisions.md); was sich aus Nutzersicht
geändert hat, in [../CHANGELOG.md](../CHANGELOG.md); der Befund vor dem Umbau in
[baseline-2026-10-10.md](baseline-2026-10-10.md); Messwerte datiert in [profiling/README.md](profiling/README.md).
Der Entwicklungsplan, der zu diesem Stand geführt hat, liegt abgeschlossen unter
[development-plan-2026-10.md](development-plan-2026-10.md).

## Aufgabe

Düsseldorf hat 41 Kommunalwahlbezirke aus 306 Stimmbezirken. Für jeden Wahlbezirk entsteht ein Wörterbuch aus
Straßennamen (OpenStreetMap) und Orten (Wikidata, Wikipedia); die 19 108 Ratsdokumente der Wahlperiode
2020 bis 2025 aus dem Ratsinformationssystem (OParl) werden danach durchsucht; je Bezirk zählt die Menge der
Dokumente mit mindestens einem Treffer, geteilt durch die Wahlberechtigten, als Trefferquote; eine lineare
Regression setzt sie zur Wahlbeteiligung der Kommunalwahl 2025 in Beziehung. Die Ergebnisse der
Bachelorarbeit (Tabelle 5) werden auf alle Stellen reproduziert; der Datensatz der Arbeit liegt eingefroren
unter `reference/`.

## Paket `georep`

Ein Paket, `src/georep/`, vollständig typisiert (`mypy --strict` mit deal-Plugin), Polars für Tabellen,
shapely und pyproj für Geometrie, Parquet für alles Abgeleitete.

| Modul | Aufgabe |
|---|---|
| `settings` | `defaults.toml` (stadtneutral) im Paket, darüber das Profil `profiles/<slug>.toml` (gewählt mit `--profile`, `GEOREP_PROFILE` oder `default_profile`, mit `base` auf einem anderen Profil aufbauend), darüber `settings.toml`, `settings.local.toml`, `--settings`, Umgebung `GEOREP_*`; pydantic-settings, unbekannte Schlüssel sind ein Fehler; `fingerprint()` der ergebnisrelevanten Parameter; `profile` (Ordnername je Stadt oder Periode, nicht im Fingerprint), `period.end` optional mit `election` als Wahltag, `analysis.exclude_districts` (Ausreißer von Tabelle 5), `originators` (Muster und Parteien für den Urheber, Option 04; `admin_types`, `citizen_types` und, seit Punkt 59, `fraction_types` und `person_types` sind die Dokumentarten, die die Klasse allein entscheiden; `letterhead_markers` steht seit Punkt 62 vor ihnen allen), `context` (Fremddaten: Quelle, Lizenz, Dateien, Spaltenform, Ordinalskalen, Variablen, Modelle, Schwellen; der ganze Block fehlt, wo eine Stadt keine hat; `context.need`, Vorhaben 22: Schalter, Paket, die bundes- und landesweiten Archive der Bedarfsquellen mit Namensnennung in `defaults.toml`, Band, Klassen und die vorab festgelegten Hypothesen mit Commit im Stadtprofil), `bodies` (Kürzel und Namen der Gremien; ohne `reference_pattern` tragen die Drucksachennummern keines, `aliases` übersetzt den Kopf einer älteren Nummernform derselben Stadt in ein Kürzel (Punkt 57), und `organizations`, `consultations` und `district_body_names` sind die zweite Quelle: Abbildung OParl-Organisation → Kürzel, das Paket mit der Beratungsfolge je Dokument und die Namen von Bezirksvertretungen ohne Nummer, Punkt 58), `topics` (Themenmodell samt Stoppwortquellen `stop_sources`, Namensfenstern und Saat je Ausschuss, Punkt 45), `classify` (der passende Ausschuss: Mindestzahl je Klasse, Schwelle der Restklasse), `functions` (Vorhaben 15: die Wörter der Ratssprache in `defaults.toml`, im Stadtprofil die Dokumentarten als „funktion/instrument“, die Sammelarten einer alten Vorlagenform mit Textregeln und Briefkopf und die Fraktionen aus mehreren Parteien mit Zeitraum; geprüft gegen `FUNCTION_INSTRUMENTS`), `majorities` (die Ratsmehrheiten der Stadt, stadtweit und nicht unter `functions`: je Zeile Wahlperiode, Parteien, Gültigkeit, Vereinbarung mit Datum und Belege im Korpus; `on(tag)` gibt die Zeile des Tages, `body_kinds` die Gremienarten, in denen sie gilt; 15 legt den Block an, 24 und 28 lesen ihn); je Stadt `[city]`, `[precincts]` (Regeln der Quellgeometrie; `format` ist `geojson`, `shapefile-zip` oder `esri-identify`, und `min_areas` ist die Zahl der Flächen, unter der eine Antwort als abgeschnitten gilt), `[columns.results]` (Spalten und Parteien), `[report]` (Quellen mit Lizenz, Notizen), `[publish]` (welche Städte veröffentlicht werden) |
| `layout` | wo was liegt: `data_root`, `cache_root`, `reference_root`, `profile` (Unterordner `data_root/<profil>/` und `cache_root/<profil>/` für PDFs und Texte, HTTP-Cache geteilt; jedes Profil setzt ihn, `Settings.base_profile` nennt den der Hauptperiode einer Stadt), `context_root` (Fremddaten im Repo, Default `None`), die Dateinamen der Quellen aus dem Profil (`districts_file`, `results_file`, `streets_file`, `district_names_file`; leer = diese Stadt veröffentlicht die Datei nicht); `for_profile` wechselt; `guard_writable` verweigert jeden Pfad unter den beiden nur lesbaren Wurzeln |
| `schema` | die Schema-Versionen der zwei Modellausgaben (Themen, passender Ausschuss) -- importfrei, damit `build_steps` sie ohne scikit-learn kennt (Punkt 45) |
| `io` | atomare Schreibvorgänge (Temporärdatei, fsync, `os.replace`), JSON, Parquet mit `schema_version` in den Metadaten, SHA-256 (`digest`) |
| `http` | Session mit Timeout, Retry mit Backoff, User-Agent, requests-cache je Quelle; `Transport`-Protokoll als Testnaht; `DeferredTransport` holt die Session erst beim ersten Aufruf (für die Beiträge, Fundament F2); `network_errors` wandelt requests-Fehler in `NetworkError`; `is_loopback_url` sagt, ob eine Adresse auf diesen Rechner zeigt (der Modellserver, Fundament F5) |
| `errors` | Domänenfehler: `MissingInputError`, `EmptyResultError`, `SchemaError`, `CorruptPdfError`, `FetchError`, `NetworkError`, `ModelError` (Fundament F5: Modell fehlt, Antwort unbrauchbar oder nicht in `ml.timeout_s`) mit den Unterklassen `ModelRejectedError` (der Server wies diese Eingabe ab) und `ModelUnreachableError` (der Server nahm die Verbindung nicht an oder verweigerte den Zugriff) |
| `oparl` | OParl 1.1 als pydantic-Vertrag (`OparlPaper` mit den drei Urheberfeldern und `consultation_organizations`, `OparlFile`, `OparlOrganization`, `PaperPage`, `OrganizationPage`), echte Antworten als Fixtures; Fundament F6: `OparlMeeting` mit Tagesordnung, `OparlAgendaItem`, `OparlConsultation`, `OparlPerson` (ohne Kontaktdaten, `PERSON_PRIVATE_KEYS`), `OparlMembership`, gemeinsame Basis `OparlObject` und der Umschlag `ListPage` für jede Liste; `OparlPaper.consultations` liest die eingebetteten Beratungen typisiert |
| `council` | Fundament F6: die Netzschritte `meetings`, `consultations`, `persons` (`run_*`), ihre Dateien (`council_files`), ein `JsonlStore` je Objektart (letzte Zeile gewinnt, sortiert und atomar gespeichert) und die Fortsetzung über Teildateien und Fortschritt; Runbook `docs/runbook-sitzungen.md` |
| `records` | `PaperRecord`: die Zeile in `raw/papers.jsonl`, aus OParl oder dem Altformat der Arbeit; die vier URL-Listen sind Tupel, weil der Record `frozen` und damit hashbar ist |
| `stores` | `PaperStore` (JSONL, Upsert nach `modified`), `TextStore` (eine Parquet-Datei, Schlüssel Dateiname, Frische über Extraktorname und PDF-Hash), `RawTextStore` (dasselbe für den Rohtext, mit Seitenzahl und den Offsets der Formfeeds im Seitentext, `form_feeds`; `save` prüft einmal je Lauf jede Zeile: Länge, `pages - 1` Seitenwechsel, jeder Offset auf einem Ersatzzeichen; eine Datei mit anderer Schema-Version liest der Store als leer, Fundament F1) |
| `sources/` | reine Fetch-Funktionen über `Transport`: `opendata` (`fetch_csv`, `fetch_districts_file` für GeoJSON, Shapefile-Zip oder die Esri-JSON-Antwort einer ArcGIS-Operation; die URL darf einen Query-String tragen, und eine abgeschnittene Antwort ist ein `FetchError` -- `exceededTransferLimit` des Dienstes oder weniger Flächen als `precincts.min_areas`, Punkt 65), `oparl` (Paper-Seiten; `fetch_objects` für jede andere Liste, F6), `pdfs` (`PdfStore` mit Manifest), `overpass` (Straßen je Polygon), `wiki` (SPARQL, GeoSearch); `opendata.fetch_zip` prüft ein Archiv der Bedarfsquellen (ein Zip mit einer Datei, Vorhaben 22) |
| `geo` | GeoJSON lesen, nach EPSG:25832 projizieren, `make_valid`, `PrecinctIndex` (STRtree), eine Rückprojektion nach lon/lat; `read_canonical_precincts` für den kanonischen Stand (drei feste Eigenschaften), `read_precincts` für eine Quellgeometrie mit Wahlbezirksattributen, `read_areas` für Flächen, die nur eine Kennung tragen |
| `prep/` | `extract` (PDF-Text hinter `PdfTextExtractor`), `raw_texts` (der Rohtext hinter `PdfPageExtractor`: `raw_from_pages` verbindet die Seiten mit `\f` und nennt die Offsets der `\f` in einer Seite, `restore_form_feeds` setzt sie zurück, `flatten` macht daraus genau den Text des Textstores, `extract_raw_missing` ist die Batch-Grenze; Fundament F1. `flatten_with_offsets` liefert denselben Text und je Zeichen seine Stelle im Rohtext, aufsteigend: die Brücke, über die Spannen aus dem kleingeschriebenen Text auf den Rohtext kommen), `papers` (Korpus), `precincts` (jede Quellgeometrie zu `interim/stimmbezirke.geojson`, GeoJSON, Shapefile-Zip über pyshp oder Esri-JSON der ArcGIS-Operation `identify`; dort wandeln `ring_signed_area`, `point_in_ring` und `geometry_from_esri_rings` die Ringe nach GeoJSON -- rein, mit Verträgen und, zusammen mit dem Prädikat `is_ring`, alle vier in `VERIFY_TARGETS`, Punkt 65. Die Nachbedingung vergleicht die Trapezformel über die Quellringe mit der über die Ergebnisringe: sie hält damit fest, dass jeder Ring genau einmal und mit dem richtigen Vorzeichen im Ergebnis steht, nicht dass die Geometrie im Übrigen stimmt), `voters` (auch `district_units`: Wahlbezirk zu Stadtbezirk über den Crosswalk), `streets` (dazu die Übereinstimmung mit dem Straßenverzeichnis der Wahl), `pois`, `bodies` (Gremium je Dokument: `parse_reference` als reine Funktion über `BodyRules`, `classify_papers` als Batch-Grenze; trifft das Muster nicht, übersetzt `bodies.aliases` den Kopf der Nummer, und `_from_code` wendet dieselben zwei Regeln an. Punkt 58: die zweite Quelle ist die Beratungsfolge -- `organization_key` und `resolve_organizations` sind rein und total, `merge_consultations` füllt die Folge des Korpus aus einem Paket auf, und `source_counts` zählt Quelle, Zustimmung, Widerspruch und Mehrdeutigkeit aus der Ausgabe), `context` (Fremddaten je Raumeinheit: Stimmbezirkstabelle, Tabelle der Quelle lesen, gewichtetes Mittel je Wahlbezirk; seit Vorhaben 22 auch die Bedarfsquellen aus Punkten und Gitterzellen: `read_accidents` liest einen Jahrgang des Unfallatlas in jeder seiner drei Formen, `read_grid` das Zensus-Gitter, `read_schools` die Schuldaten mit Sozialindex, `in_period` zählt ganze Monate, und `accidents_by_district`, `grid_by_district`, `schools_by_district`, `attention_by_district` und `need_table` rechnen aus den Anteilen von `crosswalk.point_shares` eine Zeile je Wahlbezirk): Polars-Funktionen Frame zu Frame. `voters` benennt die Zählspalten beim Lesen auf die kanonischen Namen um (`Wahlberechtigte_insgesamt`, `Waehler`, `<Partei>_Stimmen`), damit jede Wahl dasselbe Schema liefert, liest Wahlbezirk und Stadtbezirk aus einer Spalte oder aus der Stimmbezirksnummer und kennt für einen älteren Zuschnitt zusätzlich `precinct_counts`, `district_results` und `spread_postal` (Briefwahl ohne Geometrie); `references` (Vorhaben 14: Drucksachennummern in Normalform nach den Formen des Profils, `find_hits` mit geklebten Kürzeln, Rollen aus der Dokumentart, die Typregel .2 `edge_type`) |
| `search/` | `dictionary` (Wörterbuch je Wahlbezirk), `matcher` (`KeywordMatcher`-Protokoll, FlashText), `index` (invertierter Index) |
| `analysis/` | `topics` (Themenmodell: TF-IDF und NMF; `TopicRules` trägt die Stoppwörter aus dem Profil und die Saat je Ausschuss, `vectorize` ist die eine Textdarstellung), `committees` (passender Ausschuss je Dokument: logistische Regression mit Restklasse), `hits` (Treffer je Wahlbezirk, Join mit Wählern), `regression` (`scipy.stats.linregress`; `regression_pair` rechnet beide Spalten von Tabelle 5 für jede Kennzahlspalte, Ausreißer aus den Settings; ohne Streuung in x oder y gibt es kein Ergebnis, sondern einen `EmptyResultError`), `periods` (zwei Perioden je Wahlbezirk nebeneinander und die Regression ihrer Änderungen), `timeline` (Dokumente je Monat, stadtweit und je Wahlbezirk; die Nachbedingung prüft gegen `hits_by_district`, Option 07), `functions` (Vorhaben 15: Funktion je Dokument aus Dokumentart, Sammelart, Titel und Textkopf, `FunctionRules` aus `[functions]`, Variante A oder B), `cosponsors` (Vorhaben 15: Antragsteller aus Art, Autorenteil des Titels und Briefkopf, Fraktionen mit Zeitraum, Lager gegen die Ratsmehrheit aus `[majorities]`; `camp` ist rein und steht in `VERIFY_TARGETS`), `practice` (beobachtet gegen erwartet: eine Einheit gegen die Praxis ihrer Schichten, indirekte Standardisierung; ohne Settings, 15 und 14 rechnen damit), `need` (Vorhaben 22: Spearman mit Permutationstest und Perzentil-Bootstrap, Holm, die Robustheit, explorativ die Rechnung innerhalb der Stadtbezirke und Moran's I; die Zufallszahlen in der Folge des Messskripts, darum gleiche Zahlen wie die Messung; `holm` und `verdict` sind eine Übergangslösung bis `analysis/hypotheses.py` von Vorhaben 17); `procedures` (Vorhaben 14: Nummernverzeichnis, Fundstellen und Spannen, Kanten nach der Rückfallregel, Vorgänge als Wald, Antworten auf Anfragen) |
| `crosswalk` | Umrechnung von Gebietseinheiten auf Wahlbezirke: `unit_weights` wiegt je Wahlbezirk die Einheiten (Stadtbezirk, Stadtteil) mit einer Zählgröße je Stimmbezirk; der Flächen-Crosswalk auf einen anderen Zuschnitt kommt mit `assign_by_point` (Zuordnung innerhalb eines Zuschnitts über den repräsentativen Punkt), `area_shares` (Flächenanteile, auf die Schnittsumme normiert, mit Abdeckung `min_coverage` als Wächter und `min_share` gegen Splitter: ein Schnittstück unter diesem Anteil der Quellfläche stammt aus der Fließkomma-Arithmetik einer geteilten Grenze und fällt vor der Normierung weg, Punkt 51), `target_weights` und `transfer_counts` (additive Zählgrößen übertragen, `largest_remainder` macht sie ganzzahlig ohne die Summe zu ändern); `point_shares` (Vorhaben 22) gibt Punkte zu gleichen Teilen an jede Einheit (Wahlbezirk oder Stimmbezirk), deren Fläche näher als `band_m` liegt -- Band 0 ist Punkt in Fläche, ein Punkt auf einer Grenze wird geteilt; 16 und 21 rufen dieselbe Funktion. Verträge: Anteile je Quelle und Gewichte je Ziel summieren zu 1, Spaltensummen bleiben exakt erhalten, die Anteile eines Punkts summieren zu 1 |
| `pipeline` | Schrittregister: Name, Eingaben, Ausgaben, `run()`, Schema-Version, optionaler Zusatz im Stamp (`extra`: `report` und die Unterseiten), optional die Kennung der Modelle (`models`, Fundament F5: der Schritt läuft nur mit `--models`), optionale Eingaben (`optional`: ihr Hash steht im Stamp, eine fehlende als `fehlt`, ihr Fehlen bricht nichts ab; heute der Rohtextstore für `report`, Fundament F1); Stamps; `run_step`, `run_pipeline`, `build_steps` |
| `enrich` | das Register der Beiträge der Vorverarbeitung 2026-11 (Punkt 69): `CONTRIBUTIONS` ist ein Tupel von `Contribution`-Objekten mit Schritten, veröffentlichten Tabellen und Unterseiten; `build_steps` setzt die Schritte (`steps`) vor `report`, die frühen (`early_steps`, für Ausgaben, die `weights` liest: 11 `sections`, 16 `places`) unmittelbar vor `weights`, und prüft Namen über alle Schritte auf Dubletten (`DuplicateStepError`); `check_step_order` bricht ab, wenn ein Schritt eine Ausgabe liest (auch optional), die erst ein späterer schreibt (`StepOrderError`), oder wenn zwei Schritte dieselbe Datei schreiben (`DuplicateOutputError`) -- der Kern erfüllt beides in jedem Paketprofil. Ein Vorhaben mit frühen und späten Schritten bleibt ein Beitrag. Die Fabrik der Schritte bekommt `(settings, layout, http)`: `http` ist der `Transport` aus `build_steps` -- in Tests die Fake-Session, sonst ein `DeferredTransport`, der die gecachte Session erst beim ersten Aufruf baut. Ein Vorhaben ändert hier eine Importzeile und einen Eintrag, nicht den Kern. Der erste Beitrag ist `enrich.functions` (Vorhaben 15, Schritte `functions` und `cosponsors`; die Pfade nennt `functions_files`); Vorhaben 14 trägt `14-vorgaenge` bei (`enrich/procedures`: die Schritte `references` und `procedures` hinter `procedures.enabled`, ihre Pfade in `procedure_files`, die Nachbarperioden aus ihren Paketen); der dritte ist `enrich.need` (Vorhaben 22, der Netzschritt `need_data` und `need`; die Pfade nennt `need_files`) |
| `spans` | das gemeinsame Schema für Stellen im Text (Punkt 69): `id`, `start`, `end`, `kind`, `value`, `norm`, `section`, `extractor`; ein Vorhaben darf weitere Spalten **dahinter** tragen (12: `attr`), `sort_spans` behält sie dort, `empty_spans(extra)` legt sie leer an; `check_spans` prüft die acht in Folge und Typ, Grenzen und Zeilenfolge (`id, start, end, kind`, bei Gleichstand die übrigen vier, damit die Folge nicht an der Eingabe hängt) und lässt die weiteren frei, `excerpt` schneidet eine Spanne mit Kontext aus |
| `bootstrap` | kopiert die Referenz nach `data_root` und baut daraus `papers.jsonl` und den Textstore; `bootstrap_from_settings` ist die eine Stelle, an der die Nähte aus den Settings folgen (Kontextdateien, Wörterbuch, leerer Store, Beratungsfolge, Textpaket); `overlay_texts` legt ein Textpaket über den Store der Referenz, wenn es genau ihre Dateien trägt (Punkt 68); `overlay_raw_texts` legt ein Rohtextpaket als Rohtextstore an, wenn es die aktuelle Schema-Version trägt und jeder seiner Namen eine Datei des Datensatzes ist; ein leerer Store oder einer in alter Version am Ziel zählt wie ein fehlender, ein halber wird um die fehlenden Namen ergänzt, wo die Brücke zum Textstore hält (Fundament F1); das Anlagenpaket aus `procedures.attachments` nach `raw/anlagen.parquet`, nur mit eingeschalteten Schritten (Vorhaben 14); mit `context.need.enabled` kopiert er die Stadtauszüge der Bedarfsquellen aus `[context.need].package` nach `external/bedarf/`, die eigenen des Datensatzes zuerst (Vorhaben 22) |
| `pack` | die Gegenrichtung (`georep pack ZIEL`, Punkt 56): schreibt aus einem gelaufenen Profil genau die Eingaben, die `bootstrap` liest, in ein Datenpaket -- mit Prüfsummentabelle und README-Gerüst, und mit zwei Abbrüchen über den Textstore (jede Zeile aus einem Lauf, jeder Name ein Paper). `--consultations` packt stattdessen nur die Beratungsfolge je Dokument als Parquet (Punkt 58), `--texts` nur den Textstore (Punkt 68), `--raw-texts` nur den Rohtextstore (Fundament F1; verweigert einen leeren Store, Namen ohne Paper und jeden Rohtext ohne Brücke zum Textstore -- gleicher PDF-Hash, Extraktor mit `+roh` --, und schreibt ihn mit zstd auf Stufe 19 neu, `RAW_TEXTS_ZSTD_LEVEL`); `--attachments` die Anlagen je Drucksache aus dem HTTP-Cache, nur lesend, für das Profil und seine Nachbarperioden (Vorhaben 14); `--need` packt nur die Stadtauszüge der Bedarfsquellen (Vorhaben 22; verweigert ein Profil ohne `context.need.enabled`, fehlende oder leere Auszüge und Auszüge aus anderen Archiven oder einer anderen Gemeinde, als `quellen.json` und die Settings nennen) |
| `learn` | `georep learn-bodies` (Punkt 58): lernt die Abbildung OParl-Organisation → Gremiumskürzel aus den Dokumenten mit eindeutiger Beratungsfolge und bekanntem Kürzel, druckt Katalog, TOML-Block und die Gegenprobe mit der Tabelle des Profils; schreibt nichts |
| `validation/` | Fundament F4 ([validierung.md](validierung.md)): Prüfung einer Messung durch zwei unabhängige KI-Kodierer und einen Schlicht-Agenten. `codebook` (das Codebuch je Vorhaben als TOML unter `validation.root/<vorhaben>/`, geprüft von pydantic: Einheit `document`, `document_pair`, `pair_with_span`, `span`, `query_document` oder `marking`, eine oder mehrere Fragen mit Skala, Optionen, Bedingung `only_if`, `positive`/`ignore` für Treffer, `adjudicate`; dazu Regeln für Stichprobe, Auftrag, Auswertung und die Übernahme vorläufiger Antworten), `sample` (geschichtete Stichprobe ohne Zufallsgenerator: Rang SHA-256 aus Seed und Schlüssel, je Schicht die kleinsten; `allocate` teilt ganzzahlig auf; jede Zeile trägt `schicht_n`), `tasks` (Kodierauftrag je Kodierer mit Ausschnitten und Spannen nach F3, geprüft mit `georep.spans`, unter `validation.coding_root`, nie im Repo), `importer` (vorläufige Antwortdateien ins Format von F4), `merge` (zwei Kodierungen je Frage, Auftrag der Schlichtung, dann `labels.csv` mit `id, frage, …`, README und `guete.json`), `measures` (Wilson, Cohens κ, Krippendorffs α, Präzision, Recall, F1, Konfusionsmatrix, nDCG@k mit Gleichständen, geschichteter Anteil mit Wilson bei Kishs n_eff; rein und in reinem Python, gegen scikit-learn und Krippendorff 2011 geprüft), `score` (Übereinstimmung, Treffer je Schicht, in der Stichprobe und für die Grundgesamtheit, Güte eines Verfahrens), `paths`, `command` (der Unterbefehl `validate`, den `cli` mit drei Zeilen einhängt) |
| `contracts` | `configure()` für `settings.contracts` und die Prädikate der deal-Verträge |
| `profiling` | `profile_step`: ein echter Schritt unter cProfile, `.prof` datiert nach `docs/profiling/` |
| `cli` | `georep run, fetch, steps, status, profiles, publish, paths, bootstrap, pack, learn-bodies, export, regress, profile, validate, ml`; global `--profile`; `run --models [--limit N]` und `profile --models` für Schritte mit Modell; `main(argv) -> int`; Exit 0, 1 (Domänenfehler), 2 (Bedienung) |
| `ml/` | Fundament F5, lokale Modelle (Abschnitt „Modelle"): `base` (Protokolle `Embedder` und `Generator`, `EmbeddingOptions`, `GenerationOptions`, `Reply`, `ModelUse` für `Step.models` und den Cache-Schlüssel), `ollama` (Backend über HTTP, Fabriken aus `[ml]`), `cache` (inhaltsadressiert, eine SQLite-Datei je Modell unter `cache_root/ml/`), `batch` (fortsetzbarer Stapellauf, `embed_texts`, `generate_texts`), `commands` (`georep ml status`, `georep ml bench`) |
| `export` | Parquet-Ergebnisse als CSV neben die Dateien; `csv_plan` und `write_csv` nutzt auch der Schritt `report` |
| `report/` | die Berichtsseite: `model` (frozen dataclasses aus den Parquet-Ergebnissen, `format_de`, Spaltendoku; mit Fremddaten `controls` und `derived` für die beiden neuen Abschnitte), `geometry` (Wahlbezirke vereinigen und vereinfachen, SVG-Pfade, GeoJSON), `charts` (Quantilklassen, Legende, `nice_ticks`, `Axes`, Choroplethe, Streudiagramm und Added-Variable-Plots als SVG), `documents` (Dokumente mit Treffer ohne Texte, Begriffe als Indizes, für `dokumente.json`), `terms` (Begriffe mit Treffer je Wahlbezirk, für `begriffe.json`, Punkt 49), `render` (Jinja2 mit Autoescape, Allowlist der Links; `sections` liest die Abschnitte aus `templates/sections/`; `render_map` für die Leaflet-Datei), `search` (Sucheinträge je kanonischem Begriff mit Wahlbezirken, Dokumenten und Art, dazu die Faltung als Spiegel des Abschnitts-Skripts), `literature` (die Einträge der Literaturübersicht: stadtneutral aus `literatur.toml` im Paket, stadtspezifisch aus dem Profil), `tables` (Register der veröffentlichten Tabellen: Datei, Beschreibung, Spaltendoku, CSV-Regeln; `all_tables` hängt die Tabellen der Beiträge an, Punkt 69), `pages` (Unterseiten der Beiträge im Rahmen der Hauptseite, je ein Schritt `page_<name>`, Punkt 69), `build` (der Schritt `report`: Downloads, Schema, `summary.json`, Seiten), `comparison` und `publish` (`georep publish`: die Stadtseiten zusammentragen und `vergleich.html` bauen) |
| `deploy/` (kein Modul) | außerhalb des Pakets: `bin/georep-monitor.sh` und die systemd-Einheiten des wiederkehrenden Laufs; sie sprechen mit `georep` nur über CLI, Settings und Umgebung (Abschnitt Betrieb, Option 07) |

## Pipeline

Neununddreißig Schritte stehen im Register (die drei der Sitzungen, Beratungen und Personen,
`meetings`, `consultations` und `persons`, nur mit `council.enabled`, Fundament F6; je zwei der
Beiträge von Vorhaben 15, 14 und 22), jeder mit
Eingaben, Ausgaben und einer
Schema-Version; welche ein Lauf hat, entscheiden die Settings, und `georep steps` zeigt es
(nachgezählt am 2026-11-24 mit `georep steps`: vierunddreißig für Düsseldorf, fünfunddreißig mit
Vergleich, siebenundzwanzig im Periodenprofil 2014 bis 2020, sechsundzwanzig in der laufenden
Periode, dreißig für Mönchengladbach). Netzschritte laufen nur mit `--online` oder über
`georep fetch`, Schritte mit lokalem Modell (`Step.models`, Fundament F5) nur mit `--models`; `georep fetch` führt `shapes`, `texts` und `raw_texts` mit, weil die Netzschritte die Flächen
brauchen und die Texte sonst im Cache liegen blieben. Mit
`topics.k = 0` fehlt der Schritt `topics`, und `weights` rechnet ohne Themenvarianten; `bodies` steht
vor `topics`, weil die Saat der Themen die Gremien je Dokument liest (Punkt 45). Den Schritt
`committees` gibt es nur mit `classify.enabled` und Ausschüssen im Profil. Die drei
Schritte der Kontrollvariablen (`context_data`, `context`, `controls`) gibt es nur mit Fremddaten,
also wenn `context.root` gesetzt ist; `parties` nur, wenn das Profil Fraktionsnamen mitbringt
(`[originators]`). Option 02 bringt zwei weitere Profilschritte: `precincts`
mit `crosswalk.enabled` und `compare` mit `compare.period`; mit `period.dictionary = "base"`
entfallen dafür `streets_osm` und `pois_wiki`. Option 01 bringt `shapes`: er entfällt, wo eine
Periode den Zuschnitt einer anderen rechnet (`precincts.enabled = false`). Fundament F6 bringt drei
Netzschritte nach `organizations`, nur mit dem Schalter `council.enabled` (Vorgabe aus) und je einen,
wo das Profil unter `[council]` einen Endpunkt nennt (Düsseldorf und Mönchengladbach: alle drei);
kein Offline-Schritt liest ihre Ausgaben bisher. Vorhaben 15 bringt als erster Beitrag (`georep.enrich`)
zwei Offline-Schritte vor `report`, `functions` und `cosponsors`, nur mit `functions.enabled` und
Urhebern im Profil (beide Stadtprofile schalten sie ein); Vorhaben 14 dahinter `references` und
`procedures`, nur mit `procedures.enabled` (beide Stadtprofile, alle drei Düsseldorfer Perioden).
Vorhaben 22 bringt zwei weitere dahinter, den Netzschritt `need_data` und `need`, nur mit
`context.need.enabled` (beide Stadtprofile; die Periodenprofile schalten ihn aus, Frage 22.5).

| Schritt | Netz | liest | schreibt |
|---|---|---|---|
| `opendata` | ja | die Quellen des Profils (Wahlergebnis, Flächen, optional Straßenverzeichnis und Wahlbezirksnamen) | `external/` mit den Dateinamen der Quelle |
| `shapes` | nein | die Quellgeometrie (GeoJSON, Shapefile-Zip oder Esri-JSON) und die Regeln aus `[precincts]` (`format` entscheidet, und der Validator prüft, welche Schlüssel zu der Form gehören) | `interim/stimmbezirke.geojson` (drei Eigenschaften, CRS der Quelle) |
| `context_data` | ja | Open-Data-Portal: Tabelle je Raumeinheit, ihre Flächen, die Erläuterung der Indikatoren | `external/` unter den Namen aus `context.files` |
| `papers` | ja | OParl-Liste, neueste zuerst, Abbruch unter dem Periodenbeginn; beim zweiten Mal `modified_since`, `--max-pages` als Probe | `raw/papers.jsonl` |
| `organizations` | ja | OParl-Endpunkt `organizations`: Fraktionen, Ausschüsse, Bezirksvertretungen (Düsseldorf: eine Seite, 58 Objekte, 0,47 s) | `raw/organizations.json` |
| `meetings` | ja | OParl-Liste `meetings` mit eingebetteter Tagesordnung, neueste zuerst; behält Sitzungen ab `period.start` ohne Obergrenze, Abbruch nach der ersten Seite, die mehr als `council.created_margin_days` vor dem Beginn angelegt wurde; immer vollständig (F6) | `raw/meetings.jsonl`, `raw/agenda_items.jsonl` |
| `consultations` | ja | OParl-Liste `consultations`: Paper, Sitzung, Tagesordnungspunkt, Rolle je Beratung; beim zweiten Mal `modified_since` (F6) | `raw/consultations.jsonl` |
| `persons` | ja | OParl-Liste `people` mit eingebetteten Mitgliedschaften, ohne Kontaktdaten; immer vollständig (F6) | `raw/persons.jsonl`, `raw/memberships.jsonl` |
| `pdfs` | ja | Download-URLs der Paper, seriell mit Pause, `--limit` | `cache_root/<profil>/pdf/*.pdf`, `…/pdf/manifest.jsonl` |
| `streets_osm` | ja | Overpass je Stimmbezirkspolygon (aus `interim/stimmbezirke.geojson`) | `raw/streets_per_district.json` |
| `pois_wiki` | ja | Wikidata-SPARQL, Wikipedia-GeoSearch je Stimmbezirk (ebenda) | `raw/wikipedia_dict.json` |
| `texts` | nein | PDFs ohne aktuellen Text | `cache_root/<profil>/text/texts.parquet` |
| `raw_texts` | nein | PDFs ohne aktuellen Rohtext (Fundament F1); ohne PDFs bleibt der Store aus dem Paket oder entsteht leer | `cache_root/<profil>/text/rohtexte.parquet` |
| `precincts` | nein | nur mit `crosswalk.enabled`: eigenes Stimmbezirks-GeoJSON, eigene Wahlbezirksflächen, Stimmbezirke der Hauptperiode als Zielzuschnitt | `processed/stimmbezirke_zuordnung.parquet` |
| `voters` | nein | Wahlergebnis-CSV; mit `crosswalk.enabled` zusätzlich die Wahlbezirks-CSV, die Zuordnung und die Stadtbezirke der Hauptperiode | `processed/wahlbezirke_waehler.parquet`, `processed/wahlbezirke_stadtbezirke.parquet` |
| `context` | nein | Stimmbezirke (Fläche und Wahlberechtigte), Raumeinheiten, Tabelle der Quelle, Wähler | `processed/wahlbezirke_kontext.parquet`, `processed/wahlbezirke_crosswalk.parquet` |
| `streets` | nein | Straßen je Stimmbezirk | `processed/wahlbezirke_strassen.parquet` |
| `pois` | nein | Orte; mit `search.city_facilities` fallen Einrichtungen mit Stadtnamen aus beiden Ausgaben (decisions.md, Punkt 44a) | `processed/wikidata_vis.parquet`, `processed/wikidata_agg.parquet` |
| `dictionary` | nein | Orte und Straßen je Wahlbezirk | `processed/combined_searchdict.parquet` |
| `corpus` | nein | Metadaten und Texte | `interim/papers.parquet` |
| `bodies` | nein | Korpus (`id`, `reference`, `consultation_organizations`), dazu `raw/beratungsfolge.parquet`, wo das Profil eines nennt (Punkt 58) | `processed/papers_gremien.parquet` |
| `topics` | nein | Korpus (Texte), mit Saat auch die Gremien je Dokument | `processed/themen.parquet`, `processed/themen_dokumente.parquet`, `interim/themen_anteile.parquet` |
| `committees` | nein | Korpus (Texte), Gremien je Dokument | `processed/papers_ausschuss.parquet`, `processed/ausschuss_zuordnung.parquet` |
| `index` | nein | Wörterbuch, Korpus | `processed/inverted_index.parquet` |
| `timeline` | nein | Korpus, Index, Wörterbuch | `processed/monatsreihe.parquet`, `processed/wahlbezirke_monate.parquet` |
| `results` | nein | Wörterbuch, Index, Wähler | `processed/wahlbezirke_auswertung.parquet` |
| `metrics` | nein | Auswertung, Wörterbuch | `processed/wahlbezirke_kennzahlen.parquet` |
| `body_hits` | nein | Auswertung, Gremien je Dokument, Stadtbezirke | `processed/wahlbezirke_gremien.parquet`, `processed/gremien.parquet` |
| `weights` | nein | Wörterbuch, Index, Korpus (`id`, `paper_type`), Wähler, Themenanteile | `processed/wahlbezirke_gewichtet.parquet`, `processed/gewichte_begriffe.parquet` |
| `controls` | nein | Auswertung, Kontrollvariablen | `processed/regression_kontrollen.parquet` |
| `parties` | nein | Korpus, Auswertung, Wähler, dazu `raw/organizations.json`, wenn vorhanden | `processed/dokumente_urheber.parquet`, `processed/wahlbezirke_urheber.parquet`, `processed/wahlbezirke_parteien.parquet` |
| `compare` | nein | nur mit `compare.period`: die Auswertung und das Wörterbuch beider Perioden | `processed/wahlbezirke_vergleich.parquet` |
| `functions` | nein | Vorhaben 15: Korpus (`id`, `paper_type`, `name`, `text`), Urheberklasse aus `dokumente_urheber` | `processed/dokumente_funktion.parquet` (`id`, `funktion`, `instrument`, `quelle`, `variante`; eine Zeile je Korpus-ID) |
| `cosponsors` | nein | Vorhaben 15: Korpus (mit `date`), Urheber und `parteien`, Gremienart aus `papers_gremien`; die Fraktionen und Mehrheiten aus den Settings | `processed/dokumente_antragsteller.parquet` (`id`, `antragsteller`, `fraktionen`, `quelle`, `gemeinsam`, `lager`; eine Zeile je Korpus-ID) |
| `references` | nein | nur mit `procedures.enabled` (Vorhaben 14): Korpus, Textstore (Extraktor der Spannen), als optionale Eingabe der Rohtextstore (die Spannen liegen über `flatten_with_offsets` auf dem Rohtext, wo es ihn gibt, sonst auf dem Textstore), `raw/anlagen.parquet`, die Paper der Nachbarperioden aus ihren Paketen (`procedures.related`) | `processed/verweise.parquet` (Spannen nach F3: jede Nummer im Text, auch ohne Ziel), `processed/vorgang_kanten.parquet` (je Paar eine Kante, nennende Drucksache im eigenen Korpus, schwache eingeschlossen) |
| `procedures` | nein | nur mit `procedures.enabled`: Korpus, Gremien je Dokument, die eigenen Kanten, `raw/anlagen.parquet`, Paper und Textstore der Nachbarperioden (Texte nur der Drucksachen, die eine starke Kante haben können) | `processed/dokumente_vorgang.parquet` (Vorgang, Rolle, Tiefe, Größe je Korpus-ID), `processed/antwortzeiten.parquet` (je Anfrage Quelle, Datum und Tage der Antwort, Alter beim Abruf, Praxis des Gremiums) |
| `need_data` | ja | Vorhaben 22: die Archive aus `[context.need]` (Unfallatlas je Jahr, Zensus-Gitter, Schuldaten, Sozialindex) nach `cache_root/bedarf/`, eines jünger als `cache.opendata_s` nicht noch einmal; die Stimmbezirke | `external/bedarf/` mit `unfaelle.parquet`, `zensus2022.parquet`, `schulen.parquet` (die Gemeinde aus `city.ags`, Zellen mit Mittelpunkt in einem Stimmbezirk) und `quellen.json` (URL, Bytes, SHA-256, Abrufdatum je Archiv) |
| `need` | nein | Vorhaben 22: die Auszüge, Stimmbezirke, Auswertung, Stadtbezirke; mit Klassen im Profil und `classify.enabled` den passenden Ausschuss, mit Fremddaten und Hypothesen die Kontextvariablen | `processed/wahlbezirke_bedarf.parquet` (eine Zeile je Wahlbezirk: Einwohner, Unfälle mit Band von 20 m, scharf und geteilt, Miete, Schulen und Index, Dokumente und Anteile der Klassen) und, mit Hypothesen oder Paaren im Profil, `processed/bedarf_hypothesen.parquet` (Kern `hypothese`, `p`, `p_holm`, `ergebnis`, `n`, `festgelegt`, dann `deutung` mit den Wörtern aus § 8 des Messdokuments, Rechnung, Maß, Wert, Intervall) |
| `report` | nein | die Ergebnistabellen, Korpus, die kanonischen Stimmbezirke des gerechneten Zuschnitts (mit Vergleich auch dessen Tabelle), mit Fremddaten auch die drei Tabellen der Kontrollvariablen und die Erläuterung der Indikatoren, mit Straßenverzeichnis auch dieses; der Textstore (Extraktor je Text) und, als optionale Eingabe, der Rohtextstore für die Sätze über Extraktor und Rohtext in „Methode und Grenzen“; der zweite steht nur da, wenn der Store vollständig ist (`complete_raw_texts`) | `site/index.html`, `site/karte.html`, `site/data/` (Parquet, CSV, `wahlbezirke.geojson`, `schema.json`, `summary.json`, `dokumente.json`) |

Die Tabelle steht in der Reihenfolge des Registers, also in der Reihenfolge, in der `georep run`
die Schritte plant (`georep steps` zeigt sie für ein Profil). Neben der ersten Ausgabe jedes
Schritts liegt `<datei>.stamp.json` mit den SHA-256-Hashes der Eingaben, dem
Settings-Fingerprint, der Code-Version, der Schema-Version und einem Zusatz, den nur der Schritt
`report` füllt (Punkt 53: ein Hash über die Vorlagendateien des Pakets, `literatur.toml` und
`settings.report` — beides steht in keinem Eingabe-Hash und nicht im globalen Fingerprint). Stimmt alles, ist der Schritt aktuell und wird
übersprungen; sonst läuft er und sagt, warum („Eingabe geändert: texts.parquet", „Code-Version 0.6.0 ->
0.7.0"). `--force` erzwingt, `--dry-run` plant nur. Jeder Lauf druckt je Schritt eine Zeile mit der Anzahl,
auf die er gewirkt hat, und die Sekunden. Der volle Offline-Lauf auf der Referenz dauert rund 23 s, davon
7,4 s das Themenmodell, 6,5 s der passende Ausschuss, 4,2 s der Index, je unter 1 s die Gewichtung, die
Kontrollvariablen (`context` 0,4 s, `controls` unter 0,1 s) und 1,5 s die Berichtsseite (2026-10-12, nach
Punkt 45; ohne Themenmodell und Klassifikator rund 9 s).

## Datenhaltung

```
reference/                 der Datensatz der Arbeit; wird nur gelesen (guard_writable)
  moenchengladbach/        das Paket der zweiten Stadt: external/, raw/, cache/text/texts.parquet (Punkt 56)
snapshots/<periode>/       dieselbe Form je weiterer Wahlperiode: 2014-2020 und 2025 (Punkt 56)
snapshots/duesseldorf-beratungsfolge/   nur raw/beratungsfolge.parquet: die Beratungsfolge je Dokument
                           der Hauptperiode, deren Korpus sie nicht trägt (Punkt 58)
snapshots/duesseldorf-rohtexte/   nur cache/text/rohtexte.parquet: der Rohtext der Hauptperiode, damit
                           eine Kette ohne PDFs ihn hat (Fundament F1)
snapshots/<stadt>-anlagen/ nur raw/anlagen.parquet: die Anlagen je Drucksache (Name, Datum) aus dem
                           HTTP-Cache, Düsseldorf mit allen drei Perioden (Vorhaben 14)
snapshots/<stadt>-bedarf/  nur external/bedarf/: die Stadtauszüge der Bedarfsquellen (Unfälle, Zensus-Gitter,
                           Schulen, quellen.json) für Düsseldorf und Mönchengladbach (Vorhaben 22)
context/                   Fremddaten je Raumeinheit mit README (Quelle, Lizenz, Stand, SHA-256); wird nur gelesen
validierung/<vorhaben>/    Fundament F4, je Vorhaben und Runde: codebuch.toml, stichprobe.csv und .json, labels.csv, README.md,
                           guete.json -- Schlüssel, Labels und Zahlen, kein Ratstext (docs/validierung.md)
data_root/                 Standard ./data, gitignored
  <profil>/                ein Ordner je Lauf: jede Stadt unter ihrem Slug, jede Periode unter ihrem
                           Namen (Punkt 52); Standard ohne --profile ist der Slug der Stadt der Arbeit
    external/              Eingaben der Quellen, Dateinamen und Formate der Quelle (CSV, GeoJSON, Shapefile-Zip, Esri-JSON)
    external/bedarf/       Vorhaben 22: die Stadtauszüge aus need_data oder dem Paket (Parquet und quellen.json)
    raw/                   papers.jsonl, organizations.json, beratungsfolge.parquet (Punkt 58),
                           anlagen.parquet (Vorhaben 14),
                           streets_per_district.json, wikipedia_dict.json; F6: meetings.jsonl,
                           agenda_items.jsonl, consultations.jsonl, persons.jsonl, memberships.jsonl
    interim/               papers.parquet (Korpus: Metadaten plus Text), stimmbezirke.geojson (kanonisch),
                           themen_anteile.parquet (Themenanteile je Dokument, nicht veröffentlicht)
    processed/             die Ergebnistabellen als Parquet (zstd), je mit Stamp; mit Fremddaten drei mehr; dazu stimmbezirke_zuordnung (Profil mit Crosswalk)
                           (nicht veröffentlicht: papers_gremien, papers_ausschuss und wikidata_agg);
                           Vorhaben 14: verweise, vorgang_kanten, dokumente_vorgang, antwortzeiten
    site/                  die Berichtsseite: index.html (mit Stamp), karte.html (Leaflet) und data/ mit den Download-Dateien
    site/<periode>/        eine Unterseite, wenn eine zweite Wahlperiode gerechnet ist: der Pages-Workflow
                           legt sie hierher, weil der Abschnitt „Zwei Wahlperioden" sie relativ verlinkt
  kodierung/<vorhaben>/    Standard von validation.coding_root (bei Konrad messdaten/kodierung/ auf
                           xtraspace): A/, B/, schlichtung/ mit Auftrag, Codebuch und Antworten; nie im Repo
  site/                    was veröffentlicht wird und was GitHub Pages hochlädt: `georep publish` kopiert
                           die erste Stadt aus publish.cities hierher, jede weitere nach site/<slug>/, und
                           legt vergleich.html daneben
cache_root/                Standard data_root/cache
  <profil>/pdf/            <dateiname>.pdf, manifest.jsonl (URL, SHA-256, Größe, Zeit)
  <profil>/text/texts.parquet   alle Texte mit Extraktorname, PDF-Hash, Herkunft, Zeichenzahl
  <profil>/text/rohtexte.parquet   der Rohtext derselben PDFs (Fundament F1, Schema-Version 2): Groß- und
                           Kleinschreibung, Zeilen, Vorlagenkopf, \f zwischen den Seiten; Seitenzahl,
                           Zeichenzahl, Extraktorname mit Zusatz +roh, PDF-Hash, form_feeds (die
                           Offsets der \f, die eine Seite selbst trug; fast immer leer)
  http.sqlite              requests-cache, von allen Profilen geteilt (der Schlüssel ist die URL);
                           Lebensdauer je Quelle, PDFs nie
  ml/<modell>.sqlite       Modellcache (Fundament F5), eine Datei je Modell, von allen Profilen
                           geteilt; Schlüssel Digest, Prompt-Version, SHA-256 der Eingabe
  bedarf/                  Vorhaben 22: die Archive der Bedarfsquellen, unverändert, von allen Profilen
                           geteilt (bundesweit: dieselbe Datei für jede Stadt); need_data lädt eines erst
                           wieder, wenn es älter ist als cache.opendata_s
```

**Ein Datenpaket ist ein `reference_root`**: `Layout.reference_view()` liest es als Datenwurzel mit
`cache_root = <reference_root>/cache`, darum liegt der Textstore eines Pakets unter `cache/text/`. Fünf
Pakete gibt es (Punkt 56): `reference/` (81,8 MiB, der Datensatz der Arbeit, Altformat
`interim/paper_with_text.json`), `reference/moenchengladbach/` (3,8 MiB), `snapshots/2014-2020/` (36,1 MiB)
und `snapshots/2025/` (13,2 MiB) im eigenen Format (`raw/papers.jsonl`, `cache/text/texts.parquet`), dazu
`context/` (2,1 MiB) für die Fremddaten — zusammen 137,11 MiB, gezählt ohne die READMEs. Jedes trägt ein README mit Herkunft, Lizenz, Abrufdatum, den Zahlen
des Laufs und der SHA-256 jeder Datei; `tests/unit/test_data_packages.py` hält beides zusammen und lässt
keine PDFs, Stamps, Manifeste und Caches hinein. Die PDFs liegen in keinem Paket. Drei weitere
Pakete tragen je nur eine Datei der Hauptperiode, die ihr Altformat nicht hat:
`snapshots/duesseldorf-beratungsfolge/` (Punkt 58), `snapshots/duesseldorf-texte/` (Punkt 68) und
`snapshots/duesseldorf-rohtexte/` (13,5 MiB, Fundament F1); `bootstrap` übernimmt sie, wo das
Profil sie unter `[bodies]` oder `[bootstrap]` nennt, die beiden Textpakete nur, wenn ihre Namen zu
den Dateien der Referenz passen. Zwei Anlagenpakete tragen je Stadt die Anlagen je Drucksache, die
weder ein Korpus noch ein anderes Paket hat (Vorhaben 14): `snapshots/duesseldorf-anlagen/`
(303 400 Bytes, alle drei Perioden) und `snapshots/moenchengladbach-anlagen/` (63 910 Bytes). Die
Schritte von Vorhaben 14 lesen außerdem die Pakete der Nachbarperioden (`raw/papers.jsonl` und
Textstore, für die Hauptperiode `reference/raw/paper_objects.json`) nur lesend, ihr Hash steht im
Stamp. Vorhaben 22 bringt zwei kleine Pakete aus abgeleiteten Auszügen,
`snapshots/duesseldorf-bedarf/` (198 018 Bytes) und `snapshots/moenchengladbach-bedarf/` (91 866
Bytes), geschrieben von `georep pack --need` und gelesen über `[context.need].package`. Alle Pakete
zusammen 167,12 MiB am 2026-11-24.

Eingaben behalten die Formate der Quellen, weil sie Rohdaten sind; alles Abgeleitete ist Parquet und trägt
`georep.schema_version` in den Metadaten. Append-artige Metadaten (`papers.jsonl`, `manifest.jsonl`) bleiben
JSONL. CSV entsteht nur für Menschen (`georep export`). Zwei Läufe auf denselben Eingaben schreiben
byteidentische Parquet-Dateien: alle Ausgaben sind sortiert, Mengen werden zu sortierten Listen.

## Sicherheit: was „nichts geht kaputt" heißt

1. Unter `reference/` und unter dem `reference_root` eines Profils (`snapshots/<periode>/`) schreibt nichts; `Layout.guard_writable` verweigert jeden Pfad darunter, auch über Symlinks.
2. Jeder Schreibvorgang ist atomar: Temporärdatei im Zielverzeichnis, `fsync`, `os.replace`. Ein Abbruch hinterlässt die alte Datei oder die neue, nie eine halbe.
3. Fehlende Eingaben sind `MissingInputError` vor dem Lauf, leere Ergebnisse `EmptyResultError` vor dem Schreiben, falsche Spalten `SchemaError`.
4. Wiederholung ohne Änderung ist ein No-op und sagt das; `--dry-run` zeigt den Plan.
5. Netz: 180 s Timeout je Aufruf, fünf Wiederholungen mit Backoff bei 429 und 5xx, eine Sekunde Pause zwischen Seiten und Dateien; der PDF-Download isoliert Fehler je Datei und berichtet Zähler; Antworten ohne `%PDF` werden abgewiesen.
6. Domänenfehler (`GeorepError`) werden an genau einer Stelle gefangen, am Rand in `cli.main`, mit einer Zeile auf stderr und Exit 1. Vertragsverletzungen (deal) sind Programmierfehler und laufen durch.
7. Caches sehen, was sie sehen müssen: Stamps tragen Eingabe-Hashes, Settings-Fingerprint, Code- und Schema-Version; der Textstore kennt Extraktorname und PDF-Hash; Parquet-Dateien kennen ihr Schema.

## Netz

Alle Quellen sprechen über das `Transport`-Protokoll (`get`, `post`); `requests.Session` erfüllt es, die
Fake-Session in `tests/fakes.py` auch. `make_session` baut Timeout, Retry, User-Agent und requests-cache
(SQLite) mit Lebensdauer je URL-Muster (`cache_pattern`); PDFs werden nie gecacht, sie gehören in den
PDF-Store. Jeder Fetcher wirft nur `FetchError` (Antwort nicht brauchbar) oder `NetworkError` (nicht
erreichbar, Fehlerstatus nach allen Wiederholungen), gesichert durch `deal.raises`.

Ein Netzschritt eines Beitrags (`Contribution.steps` oder `early_steps`, etwa `need_data` von
Vorhaben 22) bekommt dieselbe Session wie der Kern, über `http` (Fundament F2). Ihre Cache-Regeln
kennen aber nur die Quellen des Kerns (`sources.cached_session`), und eine URL ohne Regel cacht
requests-cache nicht (`expire_after=DO_NOT_CACHE`): ohne eigene Regel holt der Schritt seine
Antworten in jedem Lauf neu. Wer das nicht will, trägt die Regel mit seinem Vorhaben ein oder legt
die Antwort selbst unter `raw/` ab, wie `opendata` (Review F7, N7). `need_data` von Vorhaben 22 tut das Zweite: es legt
seine zehn Archive (rund 105 MB, bundesweit) unverändert unter `cache_root/bedarf/` ab, von allen
Profilen geteilt, und lädt eines erst wieder, wenn es älter ist als `cache.opendata_s` (30 Tage),
eine Datei nach der anderen mit `context.need.delay_s` Pause. Ein Zip prüft
`sources.opendata.fetch_zip`, eine CSV `fetch_csv`; `quellen.json` neben den Auszügen nennt je
Archiv URL, Bytes, SHA-256 und Abrufdatum. Gemessen am 2026-11-24: vier Archive (je Quelle eines)
frisch geladen, gleiche Prüfsummen wie die der Messung; der Schritt schneidet eine Stadt in 3,0
bis 3,6 s aus den Archiven (9,8 s unter Fremdlast), der Schritt `need` rechnet in rund 1 s.

- OParl: Paper-Seiten neueste zuerst, Abbruch, sobald eine Seite nur noch Paper vor dem Periodenbeginn trägt
  (spart 270 von 365 Seiten); beim zweiten Lauf `modified_since` (letztes `modified` minus ein Tag). Nur mit
  diesem Filter liefert der Server gelöschte Paper (`deleted: true`, ohne Datum); sie kommen als
  `FetchReport.deleted_ids` zurück, und `PaperStore.upsert(deleted=…)` nimmt sie aus dem Store
  (Option 07). Jede Seite wird gegen das pydantic-Modell geprüft. Der Server brauchte am 2026-10-09 85 s je Seite.
  `--max-pages N` liest nur die ersten Seiten; der Abrufbericht zählt, wie viele der gesehenen Paper ein
  Urheberfeld tragen, und ist damit die Probe, ob sich am Befund unten etwas geändert hat.
- OParl `organizations`: die Fraktionen, Ausschüsse und Bezirksvertretungen, eine Seite mit 58 Objekten in
  0,47 s (2026-10-11). Der Server der ITK Rheinland setzt `classification` („Fraktion“, „Ausschuss“,
  „Bezirk“, „Gremium“ oder nichts), nie `organizationType`. Der Schritt `parties` bildet daraus
  Organisations-URLs auf Parteien ab; ohne die Datei greifen nur die URL-Endungen aus den Settings.
- OParl `meetings`, `consultations`, `people` (Fundament F6, `docs/runbook-sitzungen.md`): dieselbe
  Mechanik wie die Paper-Seiten in `fetch_objects`, für jede Objektart über ihr Modell; die Listen sind
  nach ID absteigend, 200 Objekte je Seite. Gemessen am 2026-11-23: Sitzungen 15 bis 20 s und 3 bis 4 MB
  je Seite (die Tagesordnung ist eingebettet), Personen 4,7 s, die flachen Listen `agendaitems` und
  `memberships` unter einer Sekunde. Jede Seite geht mit `fsync` in eine Teildatei, danach der
  Fortschritt nach `raw/<schritt>.progress.json` (nächste URL, Zeilen je Teildatei, Löschungen,
  Beginn, Schlüssel aus Endpunkt, `period.start` und Hash von `[council]`); erst ein vollständiger
  Abruf schreibt die Ausgabe, eine Probe mit `--max-pages` ist der Anfang des Abrufs, und
  `freshness` meldet einen Netzschritt mit offenem Fortschritt als „Abruf unvollständig" (das gilt
  auch für `papers`). Eine Fortsetzung kürzt die Teildateien auf die Zeilen des Fortschritts und
  verwirft ihn, wenn er älter als ein Tag ist, eine Teildatei fehlt oder der Schlüssel abweicht.
  Eine Sperre (`fcntl.flock` auf `raw/<schritt>.lock`) lässt jeden Schritt je Ordner `raw/` nur
  einmal laufen. Die Sitzungsliste ist nach Anlage sortiert (`start − created` von −418 bis +447
  Tagen); ihr Abruf endet erst nach einer Seite, die mehr als 500 Tage vor dem Beginn angelegt wurde.
  Eine volle Seite ohne `links.next` ist ein `FetchError`. `[council]` steht nicht im Fingerprint;
  die drei Schritte tragen seinen Hash als `extra`. `modified_since` nur für
  `consultations`: bei Sitzungen und Personen folgt `modified` den eingebetteten Objekten nicht. Der
  Server füllt `result` je Tagesordnungspunkt (96,5 % mit Beratung), nie `resolutionText`,
  `resolutionFile`, `cancelled`; `resultsProtocol` ist ein Nachtrag zur Tagesordnung, die
  Niederschrift eine Anlage. Keine der drei Listen fällt unter eine Cache-Regel.
- Overpass: je Stimmbezirk der Außenring des größten Polygons, um 2 m vereinfacht, als `(poly:"…")`; der
  Filter bildet `network_type="all"` von osmnx nach, mit dem die Daten der Arbeit entstanden. Treue gegen
  die Referenz: `tests/fixtures/http/README.md`. Das Rechenbudget im Kopf der Abfrage (`[timeout:N]`)
  steht als `sources.osm.query_timeout_s` in den Settings und ist 25 s: mit 90 s wiesen am 2026-10-13
  alle vier öffentlichen Instanzen dieselbe Abfrage unter Last mit `504` ab, mit 25 s antwortete sie in
  2 s (Punkt 54). Es ist nicht der Netz-Timeout, der bleibt bei 180 s. Bei `504` und `429` fragt
  `fetch_street_names` bis zu `sources.osm.retries` mal nach (Standard 3, Pause `delay_s`, dann 2×, 4×,
  `sleep` injizierbar), **je Stimmbezirk**: die Retry-Regel der Session erlaubt nur GET und HEAD, die
  Abfrage ist ein POST, und ein einzelner 504 soll nicht die 278 Bezirke danach kosten (Punkt 55).
  Jeder andere Status kommt sofort heraus.
- Wikidata: ein SPARQL für alle Objekte mit Koordinate in der Verwaltungseinheit (P131*) und Artikel in der
  Sprache; Wikipedia-GeoSearch je Stimmbezirks-Bounding-Box, ein Treffer zählt nur für den Bezirk, dessen
  Box abgefragt wurde und der den Punkt enthält (Verhalten der Arbeit).

Ein voller Abruf von Grund auf dauert Stunden (Hochrechnung 2026-10-11: 5,8 h für 19 108 PDFs, 2,8 GB) und
ist an jeder Stelle wiederaufnehmbar.

## Geometrie

Die Stimmbezirke kommen als GeoJSON in EPSG:4647 und werden einmal ins metrische EPSG:25832 projiziert
(`always_xy=True`); ungültige Polygone repariert `make_valid`, Linien ohne Fläche fallen weg, nie
`buffer(0)`. `PrecinctIndex` hält einen STRtree über die 306 Flächen und ordnet Punkte (lon, lat) zu; die
Vorbedingung prüft den Gradbereich, denn vertauschte Koordinaten sind der klassische Fehler. Zurück nach
lon/lat geht es an genau einer Stelle (`to_lonlat`), für Overpass-Polygone und GeoSearch-Boxen. Die Zuordnung
der Arbeit wird für alle 1996 Orte reproduziert.

## Nähte: Matcher und Extraktor

- `search.matcher.KeywordMatcher` (`add_terms`, `extract(text) -> set[str]`), Implementierung
  `FlashTextMatcher` (reines Python, FlashText 2.7). Der Vertrag steht lesbar in
  `tests/property/oracle_matcher.py`: Treffer an Wortgrenzen (ASCII-Buchstaben, Ziffern, Unterstrich;
  Umlaute sind Grenzen), längster Begriff gewinnt, keine Überlappung, das beendende Grenzzeichen ist
  verbraucht, Groß/Klein zählt nicht. Jeder Ersatz muss `tests/property/test_matcher_contract.py` bestehen;
  der Vertrag ist Mengengleichheit, keine Toleranz.
- `prep.extract.PdfTextExtractor` (`name` als Cache-Schlüssel, `extract(path) -> str`), Implementierung
  `PypdfExtractor`. Normalisierung (Zeilenumbrüche weg, kleingeschrieben) und der Schnitt am Marker
  `betrifft` liegen außerhalb. Ein Ersatz muss den Golden Master der vier Fixture-PDFs bestehen oder seine
  Abweichung dokumentieren; pypdf 6.20.0 und 6.21.4 reproduzieren 197 von 200 Texten der Arbeit
  zeichengleich, 7.1.0 nur 123 (`decisions.md`, Punkt 66). Seit dem 2026-11-16 ist 7.1.0 trotzdem der
  Extraktor, auf genau diese Version festgelegt; die Abweichung und ihr Preis stehen in Punkt 67.
- `prep.raw_texts.PdfPageExtractor` (`name`, `pages(path) -> list[str]`), dieselbe Implementierung
  `PypdfExtractor`, deren `extract` die Liste mit `\n` verbindet (Fundament F1). Der Rohtextstore
  hängt am Textstore über eine Eigenschaft für jedes Dokument, ohne Ausnahme: `flatten`
  (Seitenwechsel zu Zeilenumbruch, die `\f` aus dem Text einer Seite an den Offsets in
  `form_feeds` zurück, dann `normalise_text`, dann `after_marker`) ergibt den Text des
  Textstores. Ein Ersatz des Extraktors muss sie für beide Stores zugleich erfüllen
  (`decisions.md`, Punkt 73). `flatten_with_offsets` gibt zum selben Text je Zeichen den Index im
  Rohtext (gleich lang, aufsteigend; zwei gleiche nur, wo ein Zeichen klein zu mehreren wird, wie
  „İ"); eine Spanne `[i, j)` im Textstore ist im Rohtext `[offsets[i], offsets[j - 1] + 1)`. Über
  die Hauptperiode gilt beides ohne Ausnahme (`test_data_packages.py`, slow).

Gemessen (2026-10-11): der Matcher kostet 4,1 s für 5841 Begriffe über 19 108 Dokumente, 3,8 s davon reines
Python in FlashText; die Extraktion 38 ms je PDF, 17 ms je Seite. Kein Flaschenhals rechtfertigt derzeit
einen Ersatz; die Kandidaten stehen in decisions.md.

## Modelle

Fundament F5 (`docs/plan-vorverarbeitung-2026-11.md`, § 7; Gründe in decisions.md, „Lokale Modelle
über ollama"). Drei Vorhaben brauchen ein Modell: Einbettungen (18), Politikfelder (19) und
Kurzfassungen (20). Sie sprechen nicht mit einem Modell, sondern mit einer Naht:

- **Protokolle** in `ml.base`, wie Matcher und Extraktor: `Embedder` (`embed(texts)` liefert eine
  float32-Zeile je Text, dazu `name`, `digest`, `dimension` und `options`, das Fenster `num_ctx` und
  `truncate`) und `Generator` (`generate(prompt, *, system, options)` liefert eine `Reply` mit
  `text` und `truncated`: die Antwort stieß an `num_predict`; dazu `name`, `digest`).
  `GenerationOptions` sind die Optionen, die eine Antwort bestimmen; der Standard ist
  deterministisch (Temperatur 0, fester Seed, `num_ctx`, `num_predict`, `think` aus).
  Deterministisch heißt: je Rechner, Modell und Stapelgröße; über Rechner hinweg rechnet die GPU
  anders.
- **Ein Modell in einem Schritt** ist eine `ModelUse` (`EmbeddingUse(embedder, prompt)`,
  `GenerationUse(generator, prompt, options)`): die eine Quelle für die Kennung im Stamp (Modell,
  Digest, Prompt-Version, Schlüssel der Optionen, bei Einbettungen der des Fensters), für die
  Prompt-Version im Cache-Schlüssel (`prompt_key`) und für das Ergebnis des letzten Laufs (`limit`,
  `open`, `failed`). Der Schritt reicht dieselbe an `Step.models` und an `embed_texts` oder
  `generate_texts`; so laufen Kennung und Schlüssel nicht auseinander.
- **Backend** `ml.ollama`: ein ollama-Server **auf diesem Rechner**, über das `Transport`-Protokoll
  wie jede Quelle. `ml.base_url` muss `localhost` oder eine Loopback-Adresse sein, sonst ist es ein
  Fehler der Settings und des Clients, außer mit `ml.allow_remote = true`; die Session liest keine
  Proxys aus der Umgebung (`trust_env = False`). `/api/tags` liefert den Digest (den SHA-256 des
  Modellmanifests), `/api/show` die Fähigkeiten; `think` geht nur an Modelle mit `thinking`. Vor der
  ersten Arbeit fragt der Client einmal `/api/version`, ohne Wiederholung; fehlt der Server, ist
  jeder weitere Aufruf sofort ein `ModelUnreachableError`, und `client_from_settings` gibt allen
  Schritten eines Prozesses denselben Client, also eine Probe. Einmal erreicht, wird eine abgelehnte
  Verbindung mit Backoff wiederholt (`ml.retries`), ebenso 408, 409, 425, 429 und 5xx (danach ein
  `ModelError`). Nicht wiederholt werden ein Lese-Timeout nach `ml.timeout_s` (ein `ModelError`
  dieses Texts: der Server lief ja), ein 404 (ein fehlendes Modell), 400, 413 und 422 (der Server
  wies die Eingabe ab, `ModelRejectedError`) und 401 und 403 (Zugriff verweigert, eine Frage der
  Konfiguration: `ModelUnreachableError`, der Lauf bricht ab). Der Konstruktor spricht nicht mit dem
  Server: `build_steps` darf Modelle bauen, ohne dass einer läuft.
- **Settings und Stamp**: `[ml]` steht **nicht** im Settings-Fingerprint; eine Änderung dort lässt
  keinen anderen Schritt neu laufen. Was ein Ergebnis bestimmt, steht als Kennung im Stamp des
  Modellschritts, lesbar unter `"models"` samt `limit`, `open`, `failed` und `rejected`; `run_step`
  setzt sie vor jedem Lauf zurück, und die Stapelläufe des Schritts summieren hinein. `run_step`
  fragt die Kennung erst, wenn der Schritt laufen darf, also mit `--models`; eine andere meldet
  `stamp_mismatch` als „Modell oder Prompt geändert", ein Teillauf als „offen: n Eingaben" (davon
  m gescheitert), und der nächste Lauf rechnet weiter. **Abgewiesene Eingaben sind erledigt, nicht
  offen**: der Schritt ist aktuell und sagt es („aktuell, n Eingaben abgewiesen", so auch in
  `georep status`); mit `ml.retry_rejected` (`georep run --models --retry-rejected`) gilt er wieder
  als offen und fragt sie erneut. Ohne `--models` wird der Schritt übersprungen
  wie ein Netzschritt ohne `--online`, und sein Ergebnis kommt aus einem Paket (`georep pack`,
  `bootstrap`): CI und GitHub Pages haben weder GPU noch Modellserver. Fehlt der Server, ist der
  Schritt „fehlgeschlagen", nicht der Lauf: `georep run` druckt jede Zeile, sobald ein Schritt fertig
  ist, und endet mit Exit 1; `--dry-run` plant ihn mit „Frische unbekannt"; `georep status` nennt ihn
  „unbekannt" mit dem Grund. `georep profile --models` profiliert Modellschritte.
- **Cache** `ml.cache` unter `cache_root/ml/`: eine SQLite-Datei je Modell, von allen Profilen
  geteilt. Schlüssel ist (Digest, Prompt-Version samt Schlüssel der Optionen, SHA-256 der Eingabe),
  und die Eingabe ist, was das Modell sieht: bei Einbettungen der Text samt Präfix, bei Generatoren
  System und Prompt zusammen. Ein Stapel ist eine Transaktion (WAL); eine abgeschnittene Antwort
  liegt markiert darin (`truncated`). Die Tabelle `failures` (Schema 3) merkt sich je Eingabe,
  die scheiterte, Art und Grund: `abgewiesen` (vom Modell, erledigt) oder `gescheitert` (Zeit, 5xx,
  offen); ein Wert für dieselbe Eingabe löscht den Eintrag. Öffnen mehrere Läufe dieselbe neue Datei
  zugleich, wiederholt `with_busy_retry` die Vorbereitung, solange SQLite „besetzt" meldet.
  `cache_stats` liest nur (`mode=ro`), überspringt Dateien, die nicht zum Cache gehören, und nennt je
  Zeile die Datei (`CacheStat.path`), deren Name nicht zum Modell passen muss. Einbettungen liegen als
  float32 little endian.
- **Stapellauf** `ml.batch`: `run_batch` rechnet nur, was unter dem Schlüssel fehlt, jede verschiedene
  Eingabe einmal, in Stapeln zu `ml.batch_size`; `limit` (`georep run --models --limit N`) begrenzt
  die neuen Eingaben **je Stapellauf**, also je Aufruf von `embed_texts` oder `generate_texts`, und ein
  Abbruch verliert höchstens den laufenden Stapel. Scheitert ein Stapel, wird er in Einzeltexte
  zerlegt; was dann noch scheitert, steht mit Index und Grund im Bericht, und der Lauf geht weiter:
  eine Abweisung in `BatchReport.rejected` (gemerkt, spätere Läufe überspringen sie, außer mit
  `retry_rejected`, den `run_step` aus `ml.retry_rejected` in die `ModelUse` setzt), jeder andere
  Fehlschlag in `BatchReport.failures` (gemerkt, offen, im nächsten Lauf hinter allem Neuen, damit
  er nicht zuerst `limit` verbraucht). Ein fehlender Server bricht ab. Zehn Eingaben in Folge, die
  in diesem Lauf zum ersten Mal scheitern, halten den Stapellauf an, ohne Ausnahme: der Stapel, in
  dem es geschah, ist gespeichert, der Rest bleibt offen, der Grund steht in `BatchReport.stopped`.
  Der Schritt schreibt, was er hat, sein Stamp nennt den Rest offen, und `run_step` meldet ihn als
  „fehlgeschlagen". Die Abweisungen dieser Serie gelten dann als „gescheitert", nicht als abgewiesen:
  zehn in Folge sagen eher etwas über die Anfrage als über die Texte. Schon bekannte Fehlschläge
  zählen nicht in die Serie. Nach jedem Stapel ein Fortschritt mit Restzeit; `progress_log` schreibt höchstens alle 30 s
  eine Zeile. `embed_texts` und `generate_texts` lesen danach alles aus dem Cache zurück, markieren,
  was fehlt (`present`, `None`) und was abgeschnitten ist (`Generated.truncated`), und tragen das
  Ergebnis in die `ModelUse` ein.
- **Befehle**: `georep ml status` (Server, Modelle aus `[ml]` mit Digest, Grafikspeicher, Cache je
  Modell; Exit 1, wenn etwas fehlt) und `georep ml bench MODELL --n 20` (Sekunden je Dokument, Token
  je Sekunde, Hochrechnung; Zahlen in `docs/profiling/README.md`).
- **Tests** rufen nie ein Modell: `tests/fakes.py` hat `FakeEmbedder` und `FakeGenerator`
  (deterministisch aus dem SHA-256 der Eingabe, mit Abweisung und Abschneiden) und `FakeOllama`,
  einen Server als Tabelle unter `FAKE_URL`, einer Loopback-Adresse ohne Dienst. Ein Rauchtest
  gegen den echten Server trägt den Marker `models` und läuft nur von Hand (`uv run pytest -m models`).

Ein Schritt mit Modell, als Gerüst für die Vorhaben (Namen der Ausgabe und Konstanten sind deren
Sache; `Path`-Eingaben und Schema-Version wie bei jedem Schritt):

```python
client = client_from_settings(settings.ml)  # spricht noch nicht mit dem Server
use = EmbeddingUse(embedder_from_settings(settings.ml, client), PROMPT_VERSION)


def embeddings() -> str:
    texts = ...  # was das Modell sieht, samt Präfix
    with ModelCache(layout.ml_cache, use.name) as cache:
        found = embed_texts(
            use,
            cache,
            texts,
            batch_size=settings.ml.batch_size,
            limit=settings.ml.limit,
            progress=progress_log(),
        )
    ...  # Parquet schreiben, nur Zeilen mit found.present
    return found.report.line()


Step(
    "embeddings",
    (layout.corpus,),
    (out,),
    embeddings,
    EMBEDDINGS_SCHEMA_VERSION,
    models=use,
)
```

Ein Generator geht genauso mit `GenerationUse(generator_from_settings(...), PROMPT_VERSION,
options)` und `generate_texts(use, cache, prompts, system=...)`.

Grenzen, gemessen am 2026-11-23: `nomic-embed-text-v2-moe` liest höchstens 512 Token, ein längerer
Text wird hinten abgeschnitten (Vorhaben 18 zerteilt vorher); `qwen3.6:27b` belegt mit
`num_ctx = 8192` 22,9 GB Grafikspeicher, und ollama hat das Einbettungsmodell daneben verdrängt:
beide passen **nicht** zusammen in 24 GB (`gemma4` belegt 10,8 GB). Durchsatz und Hochrechnung je
Modell stehen in [profiling/README.md](profiling/README.md), „Lokale Modelle auf der RTX 4090".

## Berichtsseite

**Unterseiten** (Punkt 69): ein Beitrag in `georep.enrich.CONTRIBUTIONS` darf Seiten neben
`index.html` tragen (`report.pages.Page`: Name, Titel, ein Satz, Eingaben, Daten, Schalter, erlaubte
Links). Jede entsteht in einem eigenen Schritt `page_<name>` hinter `report` aus
`templates/pages/<name>.html.j2` (optional mit `<name>.css` und `<name>.js` daneben) im Rahmen
`templates/page.html.j2`, der dieselben Teilvorlagen einbindet wie die Hauptseite
(`templates/frame/style.css.j2` und `templates/frame/script.js.j2`); die Vorlage sieht den Rahmen
als `model` und ihre Daten als `data`. Die Hauptseite nennt die Seiten im Abschnitt `58-weitere`,
der ohne Unterseiten fehlt. So bleibt `index.html` im Budget, und kein Vorhaben ändert
`report/model.py`.

Der letzte Schritt `report` (`georep.report.build.build_site`) macht aus den Parquet-Ergebnissen eine einzige
`site/index.html` ohne externe Ressourcen: CSS, JavaScript und beide SVGs inline, nur relative Pfade, Deutsch
mit einer englischen Kurzfassung, hell und dunkel über `prefers-color-scheme`. Die Vorlage
`templates/report.html.j2` ist der Rahmen (Kopf, Fuß, Dialog, Tooltip, Basis-JavaScript); die Abschnitte liegen
als `templates/sections/NN-name.html.j2` in Nummernfolge, je mit optionalem `NN-name.css` und `NN-name.js`, die
der Rahmen in den Stil- und einen eigenen Skriptblock einfügt (`render.sections`; ein `.css` oder `.js` ohne
Vorlage ist ein Fehler). Das Basis-JavaScript bietet `window.georep` (`select(ids, scroll)`,
`showDocuments(terms, title)`, `rows`) für die Skripte der Abschnitte. **Lange Tabellen zeigen eine
Vorschau** (Punkt 48): eine Tabelle mit `class="preview"` zeigt Kopf und die ersten
`report.table_preview_rows` Zeilen, und das Makro `more(id, rows, preview)` aus
`templates/macros.html.j2` setzt darunter die Schaltfläche „alle *n* Zeilen zeigen"
(`aria-expanded`, `aria-controls`), die der Tabelle die Klasse `open` gibt. Welche Zeilen sichtbar
sind, entscheidet eine CSS-Regel im Rahmen (`tbody tr:nth-child(n+N)`, dazu `.open` und
`tr.selected`): darum zählt die Vorschau nach dem Sortieren die neue Folge, eine markierte Zeile
klappt von allein auf (`select` setzt `selected`), `@media print` zeigt alles, und ein
`<noscript><style>` im Kopf hebt die Vorschau ohne JavaScript auf. Die Umschalter bedienen
verborgene Zeilen weiter, weil sie im ganzen Dokument suchen. **Umschalter einer Kennzahl** sind ein
gemeinsames Muster (Punkt 46): das Makro `switcher(group, label, variants)` aus `templates/macros.html.j2`
baut ein `fieldset.switcher` mit einem Radio je Variante (das erste ist die Standardansicht und steht auch
ohne JavaScript da), und das Basis-JavaScript tauscht alles, was eine Variante kennt —
`data-class-<variante>` (Stufe der Farbskala, `choropleth(extra_classes=...)` setzt sie je Fläche),
`data-text-<variante>` (angezeigte Zahl oder Spaltenkopf), `data-value-<variante>` (Sortierwert) und die
Legende `#legend-<variante>`. Die **Standardvariante trägt keine Attribute**: sie ist der Zustand, in dem
die Seite ausgeliefert wird, und das JavaScript merkt sich beim Aufbau je beteiligtem Element Klasse, Text
und Sortierwert und stellt sie wieder her. Gesucht wird im ganzen Dokument, nicht im Abschnitt, denn der Umschalter der
Karte färbt auch die Kennzahlspalte der Tabelle je Wahlbezirk; getrennt halten sich die Gruppen dadurch, dass
kein `value` zweimal vorkommt (ein Test hält das fest). Die Skala steht als `data-scale` am Radio: ohne
Angabe die sequenzielle Blau-Rampe `q`, `d` ist die divergierende um das Mittel (orange darunter, neutrales
Grau in der Mitte, blau darüber; aus `color-mix` von `--selected`, `--muted` und `--q2` in `--surface`, also
ohne zweiten Dunkel-Block, mit nachgerechneten Kontrasten im Rahmen). Dieselbe Klasse bedeutet auf beiden
Flächen dasselbe: auf einer SVG-Fläche färbt `q<n>` den `fill` mit der vollen Rampe, in einer Tabellenzelle
denselben Rang als Tönung (`td.q<n>` auf `--p0` bis `--p4`) — die Zellen tragen Zahlen, und die volle Rampe
erreicht in der Mitte keinen Kontrast 4,5; ein Test verlangt darum je Rampe und Stufe beide Regeln.
Die Legenden stehen in einer `aria-live`-Region, und die Legende fester Grenzen entsteht aus den Grenzen
allein (`charts.legend_for`), nicht aus den Daten. Die Karte bietet damit neben der Trefferquote auch Treffer
absolut, Treffer je Begriff im Wörterbuch und die Abweichung vom Stadtmittel (feste Grenzen aus
`[report.diverging]`, keine Quantile: die Abweichung ist eine streng monotone Umrechnung der Quote, und
Quantile ergäben genau deren Klassen); der Abschnitt „Urheber und Parteien" schaltet seine sechs Karten und
seine Parteispalten zwischen Anteil, Abweichung vom Mittel aller Parteien und Verhältnis zum Mittel um. Woher
die Zahlen kommen, steht in `docs/skalierung-2026-10.md`; die Entscheidungen in `docs/decisions.md`,
Punkt 46. „Methode und Grenzen" schließt mit dem Absatz zur Wörterbuchgröße, dessen Korrelationen
`analysis.scaling.dictionary_bias` messen — ohne Streuung entfällt er. Neben Tabelle 5 steht dieselbe Regression mit `x = Treffer je Begriff` (`model.per_term_regression`),
und ihre Deutungssätze entstehen aus den Zahlen, nicht aus festem Text. Die Spalte „ohne
Ausreißer" von Tabelle 5 trägt im Kopf das Wort „explorativ", und unter der Tabelle steht, warum
(Punkt 61): sie ist nach dem Ansehen der Daten entstanden, und dieselbe Spalte der anderen
Wahlperiode steht daneben, sobald das Vergleichsprofil sie kennt (`model.comparison.previous_pair`,
dieselbe Rechnung über deren `results`). Das Urteil dazu hat vier Zweige aus den beiden p-Werten;
der Abschnitt „Zwei Wahlperioden" sagt dasselbe als Satz je Periode über beide Spalten (ein
Jinja-Makro `verdict` mit fünf Zweigen). Die veröffentlichten Tabellen stehen im Register
`report/tables.py` (Datei, Beschreibung, Spaltendoku, CSV-Regeln, `optional` für profilabhängige Tabellen);
daraus entstehen Downloads, `schema.json`, CSV-Dateien und die Spaltentabelle. Die Seite bleibt unter 1,5 MB
(slow-Test); mit allen Abschnitten sind es 1,27 MB. Die beiden Abschnitte der Kontrollvariablen
(`32-kontrollvariablen`, `65-abgeleitete-daten`) stehen in `{% if model.controls %}` beziehungsweise
`{% if model.derived %}` und fehlen ohne sie ganz; ihre Zahlen kommen aus
`processed/regression_kontrollen.parquet`, der Satz zur Deutung entsteht aus p, Vorzeichen, R²-Zuwachs und dem
größten standardisierten Koeffizienten, nicht aus festem Text. Der Abschnitt
`67-literatur` („Literatur und verwandte Arbeiten", zwischen „Abgeleitete Daten" und „Downloads") ist eine
geordnete Liste aus Daten: `report/literature.py` liest die stadtneutralen Einträge aus
`report/literatur.toml` im Paket und stellt die stadtspezifischen aus `[[report.literature]]` des Profils
davor (die Arbeit, auf der die Stadtseite aufsetzt, ist ihr Ursprung und steht oben); jeder Eintrag ist ein
`LiteratureEntry` aus `georep.settings` (Autor, Titel, Jahr, Ort oder Institution, URL mit Abrufdatum oder
DOI, ein Satz zum Beitrag, `pending` für Angaben, die nachzutragen sind). Die URLs kommen über die Daten in
die Allowlist (`render.model_links`), damit keine Zitation eine Konstante mit einem Ortsnamen in den Code
zwingt; `tests/unit/test_report_literature.py` hält die Liste mit dem Abschnitt „Literatur" des README
zusammen, `tests/property/test_literature_props.py` die Rendering-Invariante (jeder Eintrag genau einmal, in
der Reihenfolge der Datei). Reihenfolge: erst die Dateien
unter `site/data/` (die veröffentlichten Tabellen als Parquet kopiert und als CSV mit den Regeln von `georep export`,
`wahlbezirke.geojson` in EPSG:4326, `summary.json`, `schema.json`), dann das Modell (`report.model`: frozen dataclasses, Polars
bis zum Schluss, Zeit und Commit sind Eingaben) mit Größe und SHA-256 jeder Datei, dann die Karte
(`report.geometry`: `unary_union` je Wahlbezirk, um 15 m vereinfacht, Flächensumme bis auf 1 % erhalten, formtreu
aus EPSG:25832 auf eine `viewBox` abgebildet) und das Streudiagramm (`report.charts`), zuletzt die Seite
(`report.render`, Jinja2 mit Autoescape; Nachbedingung: jeder Link nach außen steht in `ALLOWED_LINKS` oder
kommt aus den Settings der Fremddaten, `render.model_links`). Die
Choroplethe hat fünf Quantilklassen (weniger, wenn es weniger verschiedene Werte gibt) in einer Blau-Rampe, die
je Modus getrennt gewählt und mit dem Validator der Skill `dataviz` geprüft ist; der Umschalter auf die
Wahlbeteiligung oder auf den Anteil der eigenen Bezirksvertretung tauscht nur CSS-Klassen über
`data-`-Attribute. Begriffe sind Schaltflächen: ein Klick lädt
`data/dokumente.json` nach (`report.documents`: die Dokumente mit Treffer ohne Texte, neueste zuerst, je Begriff
Indizes; der PDF-Link entsteht aus einem gemeinsamen Präfix) und zeigt die Dokumente in einem `<dialog>` mit
Datum, Titel, Drucksache, Art und Urheber; die Orte der Karte tragen Namen und Wahlbezirk als Datenattribute für den Tooltip und keinen `<title>` — ihre Ebene ist `aria-hidden` und ohne JavaScript nie sichtbar, der Titel erreichte also niemanden (Punkt 50, 73 842 Byte). **Die
Begriffslisten je Wahlbezirk kommen genauso nach** (Punkt 49): sie stehen in
`data/begriffe.json` (`report.terms`, je Wahlbezirk `[Begriff, Dokumente]` absteigend), und
`sections/50-begriffe.js` holt sie beim ersten Aufklappen eines `<details data-terms>`; inline
bleiben die trefferstärksten Begriffe stadtweit, die stadtweiten Begriffe, die fünf häufigsten je
Wahlbezirk und je Wahlbezirk seine Zahl. Beides geht über `georep.loadJson(pfad)`, das je Pfad ein
Versprechen hält (`forget(pfad)` erlaubt einen zweiten Versuch), und scheitert es — aus `file://`
verbietet der Browser `fetch` —, formuliert `georep.offlineNote(was, pfad)` denselben Satz für
beide. Der Klick auf einen Begriff hängt als ein Zuhörer am Dokument, damit auch nachgeladene
Schaltflächen wirken. Der Abschnitt
„Urheber und Parteien“ (`sections/38-parteien`) bringt sechs kleine Karten in einem SVG: die 41 Flächen
stehen einmal in `<defs>`, jedes Panel ist ein `<g transform>` mit 41 `<use>` (`charts.party_maps`), und die
Quantilklassen sind je Partei gerechnet. Seine Tabelle je Wahlbezirk schattiert die Parteispalten nicht mit
der Rampe der Karten, sondern mit fünf Tönungen einer Farbe (`--q2` in `--surface`): die Zellen tragen
Zahlen, und die volle Rampe erreicht in der Mitte in keiner Schriftfarbe den Kontrast 4,5 (nachgerechnet im
Rahmen, wo die Tönung seit Punkt 46 steht). Der Abschnitt `15-suche` ist ein Suchfeld nach dem
Combobox-Muster der WAI-ARIA Authoring Practices: `report/search.py` baut je kanonischem Begriff einen Eintrag
(Abkürzung und Langform zusammengezogen, Dokumente beider Schreibweisen vereinigt) und je Wahlbezirksname
einen weiteren, `render_report` legt sie als `<script id="suche-daten" type="application/json">` in die Seite
(rund 144 KB), und `sections/15-suche.js` gleicht Teilstrings auf zwei gefalteten Schlüsseln ab (einmal ohne
Akzente, einmal mit `ä` als `ae`). Die Vorschläge brauchen kein Netz und funktionieren aus `file://`; die
Auswahl markiert über `georep.select` und zeigt die Dokumente über `georep.showDocuments`. Die
Abkürzungsregel steht einmal als `STREET_ABBREVIATIONS` in `search/dictionary.py`, aus der das Wörterbuch und
der Payload lesen; `tests/unit/test_report_js_fold.py` prüft mit `node`, dass JavaScript und Python gleich
falten. `karte.html` ist die zweite Datei und die einzige mit
Fremdressourcen: Leaflet 1.9.4 per Subresource Integrity gepinnt, OpenStreetMap-Kacheln mit Namensnennung,
Flächen und Orte inline als JSON (`</` escaped), eigene Allowlist in `render_map`. Entscheidungen und verworfene
Alternativen stehen in [plan-report-2026-10.md](plan-report-2026-10.md), § 2. Der Abschnitt
`34-gewichtung` („Was ändert die Gewichtung?", Option 06) steht direkt hinter der Regression: eine
Sensitivitätstabelle mit beiden Spalten von Tabelle 5 je Gewichtungsvariante und der Rangkorrelation zur
ungewichteten Quote, darunter die Themen mit ihren stärksten Wörtern. Die Einheitszeile trägt dieselben
Zahlen wie Tabelle 5 (ein Test vergleicht sie); eine Variante ohne Streuung zeigt „—", und fehlt der ganzen
Tabelle die zweite Regression, entfällt die Spaltengruppe. Mit gesäten Themen (Punkt 45) trägt eine
Themenzeile den Namen ihres Ausschusses aus dem Profil, und die Themen-Tabelle eine Spalte „Gremium"; der
Abschnitt „Gremien" bekommt daneben die Tabelle „Dokumente je passendem Ausschuss" mit der Spalte „davon
ohne Ausschussberatung". Auf der Referenz: 41 Wahlbezirke, 53 Dateien
(mit `summary.json`, Option 01, `ausschuss_zuordnung`, Punkt 45, `wahlbezirke_kennzahlen`, Punkt 46,
und `begriffe.json`, Punkt 49),
13,1 MB, davon `index.html` 0,89 MB (135 KB Suchdaten, 110 KB die beiden Umschalter, 63 KB die
Parteikarten, 33 KB die Gewichtung, 30 KB die Monatsreihe), `karte.html` 232 KB, `dokumente.json` 2,3 MB,
`begriffe.json` 96 KB; 1,6 s (2026-10-13, nach Punkt 50). Die Zerlegung der Seite in ihre Posten steht
in `docs/seitengroesse-2026-10.md`.

Die Stadtseite kennt ihre Nachbarn nicht: wo die Zeile „Weitere Städte" steht, hinterlässt der Rahmen nur die
Marke `<!--georep:weitere-staedte-->`. Erst `georep publish` (`report.publish`) weiß, welche Stadtseiten es
wirklich gibt, trägt sie zusammen (die erste Stadt aus `publish.cities` bleibt an der Wurzel, jede weitere
kommt unter ihren Slug), setzt die Zeile in jede kopierte Seite und baut `vergleich.html` (`report.comparison`:
Tabelle, zwei kleine Choroplethen mit gemeinsamen Quantilklassen, ein Streudiagramm mit einer Farbe und einer
Markenform je Stadt, eigene Allowlist). Gelesen wird je Stadt nur ihr veröffentlichter Ordner
(`summary.json`, `wahlbezirke.geojson`, `wahlbezirke_auswertung.parquet`). Weil `publish` beim Kopieren löscht,
nimmt es nur seinen eigenen Zielordner an: die Standardwurzel, ein leeres Verzeichnis oder eines mit seiner
Markerdatei `.georep-publish`.

Teile der Seite hängen am Profil. Ohne Wahlbeteiligung zur Periode (`report.regression = false`) ist
`model.regression` leer: Streudiagramm, Tabelle 5 und der Umschalter der Karte entfallen, und Kopf wie
englische Kurzfassung sagen, warum. Der Abschnitt „Je Monat" (`sections/55-monate`) zeichnet aus der
Monatsreihe zwei Balken je Monat über dieselbe `Axes`-Klasse wie das Streudiagramm; der Abschnitt
„Laufende Wahlperiode" (`sections/75-laufend`) erscheint nur, wenn `report.monitoring_url` gesetzt ist, und
verweist relativ auf die Unterseite. Der Datenstand im Kopf nennt die Abrufdaten aus den Stamps von
`papers.jsonl` und `manifest.jsonl`, das neueste Dokument und die Zahl der Dokumente ohne Text — alles aus
dem Modell, nichts fest kodiert.

## Betrieb

Die Hauptperiode entsteht in GitHub Actions aus der Referenz und, seit Punkt 68, ihrem Textpaket (`bootstrap`, `run`, `publish`; der Workflow
liest die Pfade mit `georep paths`, damit kein Ordnername zweimal dasteht). Die laufende Wahlperiode
(Paketprofil `duesseldorf-2025`, Datenordner `2025`) braucht dagegen einen Rechner mit Speicher: sie ruft je Lauf nur Geändertes ab
(`modified_since`), lädt neue PDFs, extrahiert deren Texte und baut ihre eigene Seite unter
`<data_root>/2025/site/`. Das Skript `deploy/bin/georep-monitor.sh` führt einen solchen Lauf, die beiden
systemd-Einheiten daneben machen daraus einen Timer; beide tragen keinen Pfad, alles kommt aus
`%E/georep/monitor.env`. Dieselben Dateien laufen als Nutzereinheit auf kookaburra und als Systemeinheit auf
dem VPS; die Hauptseite kommt aus dem Ordner der Stadt (`<data_root>/<slug>/site/`, Punkt 52), beide Pfade
aus `georep paths`. PDFs und Textstore gehen optional in ein privates R2-Bucket (`cache/2025/…`), die fertigen Seiten
und Tabellen per `rsync` auf den VPS; ohne die Variablen passiert nichts von beidem. Eine `flock`-Sperre
lässt nur einen Lauf zu, ein Fehler bricht mit Exit 1 ab und nennt den Schritt. Installation, Trockenlauf,
Erstabruf und die Handgriffe für R2 und VPS stehen in [../deploy/README.md](../deploy/README.md), die
Entscheidungen in [decisions.md](decisions.md).

## Verträge

deal-Verträge stehen an den Batch-Grenzen, nicht in heißen Schleifen: Vorbedingungen (Pflichtspalten,
Begriffe kleingeschrieben und ohne Komma, Koordinaten in Grad, Wahlberechtigte positiv), Nachbedingungen
(eine Zeile je Schlüssel, Listen sortiert und eindeutig, `anzahl_treffer` gleich Mächtigkeit, Wahlbezirke
nur aus den Eingaben, r in [-1, 1], eine Zerlegung ohne Rest über `parts_sum_to`), `raises` an den
Fetchern, `pure` auf kleinen totalen Funktionen (nicht aber auf solchen, die eine Batch-Funktion je
Zeile ruft: `deal.has()` patcht je Aufruf prozessweit, darum trägt `prep.bodies.parse_reference` nur
`deal.safe` und wird über `deal.cases` und crosshair auf Reinheit geprüft). Die
nur aus den Eingaben, r in [-1, 1]), `raises` an den Fetchern, `pure` auf kleinen totalen Funktionen. Die
Gewichtung hat die ihren: jeder Faktor und jedes Dokumentgewicht in [0, 1] (`in_unit_interval`), eine Zeile
je Paar (Wahlbezirk, Dokument), dieselbe Paarmenge wie die Vereinigung in `hits_by_district`, und als
stärkste Zusage, dass die Variante `einheit` genau `anzahl_treffer` reproduziert und die Themenvarianten
diese Zählung zerlegen; beim Themenmodell: genau `k` Themen, Zeilensummen 1 ± 1e-9, jedes Dokument mit Text
einmal, jedes Gremienkürzel höchstens einmal und die gesäten Themen zuerst; beim passenden Ausschuss: eine
Zeile je Dokument mit Text, nur gelernte Kürzel oder die Restklasse, jede Wahrscheinlichkeit über der
Schwelle, und die Tabelle zerlegt die Dokumente ohne Rest. Die
Prädikate liegen in `georep.contracts`, damit dieselbe Eigenschaft überall gleich heißt. `settings.contracts
= "off"` ruft `deal.disable` beim Start; der Overhead liegt unter einem Prozent (2026-10-11). Pydantic
validiert an der Systemgrenze (OParl, Records, Settings), Verträge sichern das Innere; `icontract` wird
nicht gemischt.

Grenzen von deal 4.24.6, umschifft: `deal.raises` vergleicht exakte Typen (darum `NetworkError` statt der
requests-Unterklassen), und der `has()`-Patcher ist nicht reentrant (darum `deal.safe`, nicht `deal.pure`,
auf dem rekursiven `deep_merge`).

## Tests und Prüfungen

| Schicht | Inhalt |
|---|---|
| `tests/unit/` | eine Funktion, ein Verhalten; Vertragsverletzungen je mit Gegenbeispiel |
| `tests/property/` | hypothesis-Invarianten (darunter: Einheitsgewichte reproduzieren die Zählung exakt, Gewichte in [0, 1], Monotonie, Themenzerlegung, die Stoppwörter aus dem Profil sind Token des Modells), das Matcher-Orakel (400 Zufallsfälle), `deal.cases` auf achtzehn reinen Funktionen |
| Messskripte unter `docs/` | was kein Test tragen kann, weil es am Rechner hängt: die Methodikkennzahlen (`methodik-review-2026-10-messung.py`) und die Kohärenz, Saattreue und Kreuzvalidierung des Themenmodells (`themenmodell-2026-10-messung.py`) |
| `tests/golden/` | Mini-Fixture (3 Wahlbezirke, 200 Dokumente, Erwartung aus dem Altcode `v0.2.0`) und die volle Referenz (`slow`) gegen die Ergebnisse der Arbeit; beide mit `as_in_the_thesis(...)`, also mit abgeschalteten eigenen Regeln (decisions.md, Punkte 43 und 44), und beide unter dem Profil der Settings, nicht flach (Punkt 52) |
| `tests/bench/` | pytest-benchmark, nur in `nox -s bench` |
| Marker `models` | ruft den lokalen Modellserver (Fundament F5), nur von Hand: `uv run pytest -m models`; jede nox-Session schließt ihn aus |
| `tests/fixtures/` | Mini-Datensatz (drei Wahlbezirke mit ihren 22 Stimmbezirken), vier PDFs mit Herkunft, eine OParl-Seite, aufgezeichnete Antworten von Overpass, Wikidata, Wikipedia |

Netz kommt in Tests nie von echten Endpunkten; Zeit (`today`), Zufall (hypothesis-Profile) und Netz
(`Transport`, `sleep`) sind Eingaben.

| nox-Session | Was | wo |
|---|---|---|
| `lint`, `typecheck`, `deps`, `test` | Ruff, mypy strict, Lockfile ohne pandas/geopandas/osmnx, schnelle Suite parallel mit Abdeckung als Untergrenze (90 %) | lokal (`uv run nox`) und CI |
| `golden` | die volle Referenz | CI, lokal `uv run pytest -m slow` |
| `bench` | heiße Pfade gegen den letzten gespeicherten Lauf, rot ab 20 % langsamer im Minimum | lokal |
| `profile -- SCHRITT` | ein echter Schritt unter cProfile | lokal |
| `verify` | crosshair über die reinen Funktionen mit Verträgen (37 Ziele), rund zehn Minuten (580 s am 2026-10-13); zwei Ziele sind mit Begründung ausgenommen (`parse_reference`: crosshair baut für `re.Pattern \| None` einen symbolischen Regex und bricht ab; `bars`: sein Gegenbeispiel ist eine Zahl mit 300 Stellen) | lokal, und wöchentlich in Actions (`quality.yml`) |
| `alone` | Reihenfolgeunabhängigkeit: jede Testdatei einmal allein (drei parallel), dann die ganze schnelle Suite rückwärts | lokal |
| `mutate` | pytest-gremlins, **eine Sitzung je Modul** mit genau seinen Testdateien (`MUTATION_SCOPE` im `noxfile.py`), drei Arbeiter, einmal pro größerer Änderung; `analysis/topics.py` ist ausgenommen (jeder Mutant rechnet NMF). Der Zuschnitt ist Pflicht, nicht Bequemlichkeit: ohne Abdeckungsdaten läuft jeder Mutant gegen alle übergebenen Tests | lokal, und wöchentlich in Actions (`quality.yml`) mit `-- fast` |

Stand 2026-11-18: 1299 schnelle Tests in rund 55 s, Abdeckung 98,5 %; Mutationsquote 81 % über die
dreizehn Module des Ausbaus ([mutation-2026-10-13.md](mutation-2026-10-13.md): 882 Mutanten, 717
getötet, 165 Überlebende, davon 100 in Vertragsgrenzen), 79 % über `search/` und `analysis/`
([mutation-2026-10-11.md](mutation-2026-10-11.md)), 83 % über `analysis/weights.py`
([mutation-2026-10-12.md](mutation-2026-10-12.md)).

## Bekannte Grenzen

- Ein voller `georep fetch` von Grund auf lief noch nie; ob der OParl-Server `modified_since` beachtet, zeigt erst er.
- Labels, die sich nur durch ein Komma unterscheiden, fallen in der POI-Bereinigung zusammen (Verhalten der Arbeit, durch das Wörterbuch harmlos).
- Die Regel „Einrichtung mit Stadtnamen" urteilt über den Namen, nicht über die Sache: sie trifft auch, was
  eine Stadt im Namen trägt und kein Ort ist (eine Zeitung, eine Ausstellung), und sie trifft nicht, was ohne
  Stadtnamen stadtweit vorkommt („Hofgarten", „Schulweg") — dafür steht die Liste der stadtweiten Begriffe,
  und die urteilt umgekehrt nur über die Häufigkeit, nicht über die Sache. Die Gattungswortliste ist
  deutschsprachig; eine Stadt in einem anderen Sprachraum ersetzt sie im Profil.
- Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab; die Tests frieren die Neuberechnung ein (baseline-2026-10-10.md).
- crosshair prüft nur rein-pythonische Funktionen; Polars-Funktionen haben Laufzeitverträge und hypothesis.
- Der passende Ausschuss ist eine Schätzung aus Wörtern, keine Aussage darüber, wo ein Dokument hätte
  beraten werden müssen; vier von fünf Dokumenten der Bezirksvertretungen bleiben in der Restklasse
  (decisions.md, Punkt 45c). Sechs Personennamen überleben den Namensfilter, weil sie nie neben einer
  Amtsbezeichnung stehen (ebenda, 45a).
- Der OParl-Server liefert für Düsseldorf keine Urheberfelder (`originatorPerson`, `originatorOrganization`,
  `underDirectionOf`): 0 von 19 108 Rohobjekten und keines der sechs Paper der Seite vom 2026-10-09, auch
  der „Antrag FDP“ nicht. Der Urheber ist deshalb aus `paperType`, Titel und Textkopf abgeleitet und deckt
  98,3 % der Dokumente ab; die Quelle `oparl` greift ohne Codeänderung, sobald der Server die Felder füllt.
  Einzelne Mandatsträger (865 Dokumente) bleiben ohne Partei, auch wenn der Titel eine nennt; nennt erst der
  Textkopf den Mandatsträger, zählt das Dokument als unbekannt (die Anreden der Vorlagen würden sonst halbe
  Anträge zu Personen machen).
- Eine Periode derselben Stadt kann eine andere Taxonomie und eine andere Vorlagenform haben
  (Punkt 60): `Verwaltungsvorlage` steht in `admin_types` und kommt nur in der Wahlperiode 2014 bis
  2020 vor (8 337 Dokumente), und `letterhead_markers` trägt den Briefkopf jener Form, der den
  Urheber zwischen der Formularzeile und dem Gremium nennt. Ein Briefkopfmarker gilt **vor** jeder
  Dokumentart-Liste (Punkt 62): die Art sagt, wie das System die Vorlage geführt hat, der Briefkopf,
  wer sie geschrieben hat, und 47 Dokumente jener Periode widersprechen sich darin. Er darf nur
  dort stehen, wo ein Zitat ihn nicht trägt — für diese Formularzeile ist das gemessen. „Urheber unbekannt" liegt damit in
  jener Periode bei 10,6 % statt 55,9 %; die beiden anderen Perioden sind byteidentisch unberührt,
  weil ihr Korpus den Text hinter `search.text_split_marker` abschneidet und die Formularzeile
  davor liegt.
- Eine Stadt kann die Urheberklasse in der **Dokumentart** führen, ohne den Urheber zu nennen
  (Punkt 59): `originators.fraction_types` und `person_types` nennen solche Arten, die Klasse steht
  dann fest, und die Partei wird im Titel und im ganzen Textkopf gesucht statt in einem Fenster.
  Mönchengladbachs 16 Dokumentarten sind so vollständig zugeordnet (`Urheber unbekannt` 0,0 %); offen
  bleibt dort die Partei — 239 der 581 Fraktionsanträge (41,1 %) nennen eine, die übrigen 342 sind
  eine Fraktion ohne Namen (314 ohne Text, 28 mit Briefkopf ohne Namen). Vom Titel zählt dabei nur,
  was hinter seinem letzten Bezugsmarker steht (`title_split_markers`, Punkt 63).
- Im Wahlbezirk 11 ist Die Linke nicht angetreten (0 Stimmen). Der Abgleich mit dem Stimmenanteil lässt
  solche Bezirke je Partei aus (`angetreten`), sonst läse sich „kein Wahlvorschlag“ wie „keine Zustimmung“.
