# Plan 06: Gewichtung

Stand 2026-10-11, Branch `feat/06-gewichtung`. Status: umgeschrieben.

Briefing: [../plan-ausbau-2026-10.md](../plan-ausbau-2026-10.md), § 7.6; Regeln in [../../CLAUDE.md](../../CLAUDE.md)
und § 2 des Meta-Plans; Aufbau in [../architecture.md](../architecture.md). Alle Zahlen hier sind am 2026-10-11 auf
der Referenz im Worktree gemessen (`uv run georep run`, Polars, ein Scratchpad-Venv mit scikit-learn 1.9.1), nicht
geschätzt, wo nicht ausdrücklich „geschätzt" steht.

## 1. Ziel und Nicht-Ziel

Die Trefferquote der Arbeit ist binär: ein Dokument zählt für einen Wahlbezirk, sobald ein einziger Begriff seines
Wörterbuchs darin vorkommt, und „Hofgarten" zählt so viel wie „Am Kleinforst". Option 6 stellt dieser Kennzahl
gewichtete Varianten zur Seite und zeigt auf der Berichtsseite, ob die Schlussfolgerung (p = 0,31 über alle 41
Wahlbezirke, p = 0,035 ohne 1 und 10) davon abhängt:

1. **Spezifität je Begriff**: ein Begriff, den mehrere Wahlbezirke führen, zählt für jeden nur anteilig
   (1/n Bezirke); ein Begriff, der stadtweit in sehr vielen Dokumenten steht, zählt weniger (normierte inverse
   Dokumenthäufigkeit, IDF).
2. **Gewicht je Dokumentart** (`paper_type`): Verwaltungsvorlagen gegen Anträge, Anfragen und Eingaben, zwei
   Regelsätze (halbes Gewicht, Gewicht null), Regeln in den Settings.
3. **Themen je Dokument**: ein Themenmodell (TF-IDF und NMF, scikit-learn, 20 Themen) verteilt jedes Dokument auf
   Themen; je Thema entsteht eine Variante, die nur den Anteil des Dokuments an diesem Thema zählt. Die Themen
   bekommen Labels aus ihren zehn stärksten Wörtern; eine Deutung wird nicht versprochen.
4. **Sensitivitätstabelle** auf der Seite: Tabelle 5 (n, Steigung, Achsenabschnitt, r, R², p; alle Wahlbezirke und
   ohne 1 und 10) unter jeder Gewichtung, dazu die Rangkorrelation (Spearman) der gewichteten zur ungewichteten
   Quote. Abschnitt „Was ändert die Gewichtung?".

Invariante über allem: **Einheitsgewichte reproduzieren Tabelle 5 exakt**, nicht nur ungefähr; der Golden Master
der Arbeit bleibt unberührt, die bisherigen Tabellen ändern sich nicht um ein Byte.

Nicht Ziel: die Karte oder die Tabelle je Wahlbezirk auf gewichtete Quoten umschalten (die Karte bekommt mit
Option 5 schon eine dritte Klasse; die Gewichtung bleibt ein eigener Abschnitt); Themen interpretieren oder von
Hand benennen; eine „beste" Gewichtung küren; den Index oder das Wörterbuch ändern (alle Gewichte wirken nach dem
Matcher, auf den vorhandenen Dateien); Themen je Dokument im Dokumentdialog zeigen (Option 8 oder später); LDA
(gemessen: 47 s, Themen aus Funktionswörtern, siehe § 2); Fremddaten.

## 2. Entscheidungen (mit verworfenen Alternativen und Kosten)

| Frage | Entscheidung | Warum, und was verworfen wurde |
|---|---|---|
| Formel | Für Wahlbezirk d und Dokument p mit mindestens einem Treffer aus dem Wörterbuch von d: `g(d, p) = max über die getroffenen Begriffe t von w_begriff(t) · w_art(p) · w_thema(p)`; gewichtete Treffer `Σ_p g(d, p)`; gewichtete Quote geteilt durch Wahlberechtigte. Jedes Gewicht in [0, 1], also `g ≤ 1` | Ein Dokument zählt je Bezirk höchstens einmal, wie die Vereinigung der Arbeit; bei Einheitsgewichten ist `g = 1` und die Summe gleich `anzahl_treffer` (auf der Referenz nachgerechnet: exakt, 29 573 Paare). Verworfen: Summe über Begriffe (zählt Dokumente mit vielen Begriffen mehrfach, bricht die Schranke 1); Noisy-Or `1 − Π(1 − w)` (dieselbe Schranke, schwerer zu erklären); Summe mit Kappung bei 1 (nicht linear in den Gewichten) |
| Spezifität nach Bezirken | `w = 1 / n_bezirke(t)` | Die Anteile eines Begriffs über die Bezirke summieren zu 1: ein Dokument, das nur „Münchener Straße" (7 Bezirke) nennt, verteilt ein Gewicht 1 auf sieben Bezirke. 4918 der 5841 Begriffe gehören genau einem Bezirk (§ 3), die Variante wirkt also nur auf 923 Begriffe, darunter die trefferstärksten |
| Spezifität nach Dokumenthäufigkeit | `w = (ln N − ln df) / ln N` mit df = Dokumente mit dem Begriff (`anzahl_treffer` des Index), N = Dokumente mit Text (19 033); df = 0 ergibt 1 (ohne Wirkung, keine Treffer) | Liegt in [0, 1], Begriff in einem Dokument = 1, in allen = 0; ohne freien Parameter. Verworfen: `1 / (1 + ln df)` (erreicht nie 0, willkürliche Skala); BM25-Sättigung (ein Parameter mehr, nichts gewonnen) |
| Dokumentart | Geordnete Regex-Regeln in den Settings, erste passende gewinnt, sonst `default`; je Regelsatz eine Variante. Standard: `^z?(antrag\|anfrage\|haushaltsantrag\|eingabe)` (ohne Groß/Klein) mit Gewicht 0,5 (`antraege_halb`) und 0 (`nur_vorlagen`) | 39 Dokumentarten (§ 3), davon 30 Fraktionsvarianten von Antrag und Anfrage; ein Präfix-Muster deckt sie, „zAnfrage REP" ist ein Tippfehler der Quelle. Verworfen: Gewicht je einzelner Art in den Settings (39 Zeilen, Düsseldorf-spezifisch, bricht bei jeder neuen Stadt); feste Klassen im Code (Option 10 verlangt Settings) |
| Themenmodell | TF-IDF (`TfidfVectorizer`, Token `[a-zäöüß]{3,}`, `min_df 5`, `max_df 0,5`, 20 000 Merkmale, sublineares tf, float32) und NMF (`init="nndsvda"`, `solver="cd"`, `max_iter 200`, `tol 1e-4`), K = 20; Zeilen von W L1-normiert sind die Themenanteile; Label = zehn stärkste Wörter der Zeile von H | Gemessen auf 19 033 Texten: TF-IDF 2,2 s, NMF 3,8 s (113 Iterationen), zweiter Lauf byteidentisch, keine Zeile ohne Masse. LDA (online, 10 Iterationen) 47 s und Themen aus Funktionswörtern. nndsvda ist deterministisch, `random_state` steht trotzdem in den Settings. Verworfen: LDA; gensim (Konrad, Frage 3); TF-IDF von Hand (dito); K aus Kohärenzmaßen wählen (Rechenzeit mal zehn, ohne Testbarkeit) |
| Stopwörter | eine gepackte deutsche Liste `src/georep/analysis/stopwords_de.txt` (rund 200 Funktionswörter, aus eigener Hand, keine Abhängigkeit), Settings `topics.stop_words = "de"` oder `""` | Die Messung zeigt ein Thema aus „auch, oder, sich, nicht, dass" mit 4144 dominierten Dokumenten; `max_df` allein fängt das nicht. Verworfen: NLTK oder spaCy (neue Abhängigkeit für eine Liste); sklearn-Liste (nur Englisch) |
| Themen als Gewicht | je Thema k eine Variante `thema_NN` mit `w_thema(p) = anteil_k(p)` (weich) | Die Anteile summieren je Dokument zu 1, also zerlegen die K Varianten die Einheitszählung: `Σ_k treffer(thema_k) = anzahl_treffer` je Bezirk (auf der Referenz: 29 573,0 = 29 573). Das ist ein prüfbarer Vertrag und braucht keine Deutung. Verworfen: hartes Zuordnen zum dominanten Thema (verliert die Zerlegung bei Mischdokumenten); ein Themengewicht aus den Settings (verlangt Interpretation, die Themen sind nicht stabil über Städte) |
| Kombination | eine Variante `kombiniert` als Produkt der Faktoren aus `weights.combined`, Standard `["idf", "antraege_halb"]` | Zeigt, ob zwei milde Gewichte zusammen etwas ändern; die Faktoren stehen in den Settings, damit die Wahl nicht im Code steckt. Verworfen: alle Paare (Tabelle wird unlesbar) |
| Ausreißer | die Spalte „ohne" nutzt für jede Variante dieselben Wahlbezirke wie Tabelle 5; die Konstante `OUTLIERS = (1, 10)` in `report/model.py` wandert nach `[analysis] exclude_districts` in den Settings | Vergleichbarkeit der Zeilen; ein Düsseldorf-Wert im Code verstößt gegen § 1 des Meta-Plans. Verworfen: je Variante die zwei höchsten Quoten neu bestimmen (dann vergleicht die Tabelle verschiedene Stichproben) |
| Ausgabeform | lange Tabelle `processed/wahlbezirke_gewichtet.parquet` (eine Zeile je Wahlbezirk und Variante) statt neuer Spalten in `wahlbezirke_auswertung.parquet` | Die Auswertung der Arbeit bleibt byteidentisch (Golden Master, Tabelle 5); Varianten sind Zeilen, nicht Spalten, also kommt eine neue Variante ohne Schemaänderung hinzu; Option 3 kann dieselbe Form nutzen |
| Veröffentlichung der Themen | `themen.parquet` (K Zeilen) und `themen_dokumente.parquet` (dominantes Thema und Anteil je Dokument, 0,10 MB) werden veröffentlicht; die volle Anteilsmatrix bleibt in `interim/themen_anteile.parquet` (0,93 MB) als Eingabe des Schritts `weights` | Die Matrix als CSV wären rund 4 MB (19 033 Zeilen × 20 Zahlen plus 70 Zeichen URL); `interim/` ist für Zwischenstände da, wie `papers.parquet`. Verworfen: Matrix auf vier Stellen gerundet veröffentlichen (0,58 MB Parquet, CSV trotzdem 3,6 MB) |
| Schritte | zwei neue Offline-Schritte: `topics` (nach `corpus`) und `weights` (nach `results`); `report` liest beide; `topics.k = 0` nimmt `topics` aus dem Register, dann gibt es keine `thema_*`-Varianten | Beide unter 10 s auf der Referenz, also normale Schritte mit Stamp, `--force`, `--dry-run`; die Abnahmeschwelle von 60 s ist mit Abstand erfüllt. Verworfen: ein Schalter `--with-optional` (neuer CLI-Begriff für etwas, das Sekunden dauert) |
| scikit-learn | Laufzeitabhängigkeit `scikit-learn>=1.9`, aus `FORBIDDEN` in `noxfile.py` gestrichen; importiert nur in `analysis/topics.py` (ein Test prüft das per Quelltextsuche); `pipeline.py` importiert das Modul erst im Schritt | Konrad, 2026-10-11 (Frage 3). scikit-learn 1.9.1 zieht nur joblib, threadpoolctl, scipy und numpy, kein pandas; der Import kostet rund 0,4 s und soll `georep status` nicht verteuern. Eintrag in `decisions.md`, Punkt 21 |
| Regression je Variante | `regression_pair` wandert aus `report/model.py` nach `analysis/regression.py` und bekommt `x` (Spaltenname) und `exclude` als Parameter; eine Variante ohne Streuung liefert `None` statt eines Fehlers | Dieselbe Funktion braucht Option 3 (Kennzahlvarianten mit eigener Regression, § 5 Phase 2 des Meta-Plans); auf der Mini-Fixture kann `nur_vorlagen` drei gleiche Quoten liefern |

## 3. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

Alles liegt nach `georep run` unter `data_root` (`/media/konrad/xtraspace/georep/worktrees/06-gewichtung/data`,
Stand 2026-10-11, Größen mit `ls -l`, Zeilen und Spalten mit Polars). Herkunft und Lizenzen wie auf der Seite:
Dokumente aus dem Ratsinformationssystem (nur Kennungen werden veröffentlicht), Straßen ODbL, Orte CC0, Wahl DL-DE-BY.

Eingaben der Option (vorhanden):

- `processed/inverted_index.parquet`, 5841 Zeilen, 152 045 Bytes: `suchbegriffe` String, `paper_ids`
  List(String), `anzahl_treffer` Int64. 2801 Begriffe ohne Treffer; Summe der Treffer 31 024 (Begriff-Dokument-Paare);
  Median 1, 90 %-Quantil 15, Maximum 205 („grafenberger allee"), dann „stadtwerke düsseldorf" 190, „vennhauser
  allee" 176, „hofgarten" 172, „königsallee" 146, „schulweg" 144 (versteckt, zählt).
- `processed/combined_searchdict.parquet`, 41 Zeilen, 44 255 Bytes: `wahlkreis_id` Int64, `suchbegriffe`
  List(String). 6991 Bezirk-Begriff-Paare über 5841 Begriffe: 4918 Begriffe in einem Bezirk, 756 in zwei, 123 in
  drei, 32 in vier, 10 in fünf, 2 in sieben („münchener straße", „grafenberger allee" in fünf). Begriffe je Bezirk
  81 bis 812, Median 147.
- `interim/papers.parquet`, 19 108 Zeilen, 15 677 746 Bytes: `id`, `name`, `reference` String, `date` Date,
  `paper_type`, `main_file`, `file_name`, `download_url`, `text` String. 19 033 mit Text, zusammen 51,2 Millionen
  Zeichen, Median 1660, Mittel 2680, Maximum 320 886; Texte kleingeschrieben und ab „betrifft" geschnitten. 39
  Dokumentarten; die größten: Beschlussvorlage 4001, Antrag 3321, Bezirksvertretung Informationsvorlage 2699,
  Anfrage 2353, Bezirksvertretung Beschlussvorlage 1474, Informationsvorlage 1327; dann 30 Fraktionsvarianten
  (Anfrage SPD 360 … Haushaltsantrag AFD 2), Berichtsvorlage 177, A+F Beschluss 145, Bedarfsbeschluss 78, Eingabe
  nach 24GO 73 und „24 GO" 51, Beschlussvorlage RPA 32, zAnfrage REP 2. Das Muster aus § 2 trifft 9175 Dokumente,
  9933 bleiben bei Gewicht 1.
- `processed/wahlbezirke_auswertung.parquet`, 41 Zeilen, 135 841 Bytes: `wahlkreis_id` Int64, `suchbegriffe`
  List(String), `paper_ids` List(String), `anzahl_treffer` Int64, `Wahlberechtigte_insgesamt`, `Waehler`, sechs
  `<Partei>_Stimmen` Int64, `wahlbeteiligung` Float64, sechs `<Partei>_anteil` Float64, `trefferquote` Float64.
- `processed/wahlbezirke_waehler.parquet`, 41 Zeilen, 9519 Bytes: dieselben Wählerspalten ohne Treffer.

Abgeleitete Zahlen (Polars, 2026-10-11): 11 051 Dokumente mit mindestens einem Treffer; 29 573 Paare (Wahlbezirk,
Dokument); 51 887 Tripel (Wahlbezirk, Begriff, Dokument); je Dokument im Mittel 2,8 verschiedene Begriffe, 401
Dokumente mit zehn oder mehr.

Messungen im Scratchpad (Dateien dort: `topics_bench.log`, `weights_preview.log`):

| Was | Ergebnis |
|---|---|
| alle Gewichtsvarianten außer Themen, Polars | 0,05 s; Einheitsgewichte gleich `anzahl_treffer` in allen 41 Bezirken |
| TF-IDF über 19 033 Texte | 2,2 s, Matrix 19 033 × 20 000, 2 431 542 Einträge |
| NMF, K = 20 | 3,8 s (cd, 113 Iterationen), 3,2 s (mu); zweiter Lauf byteidentisch |
| LDA online, 10 Iterationen | 47 s, verworfen |
| `themen_anteile.parquet` (Float64) | 0,93 MB; dominantes Thema je Dokument 0,10 MB |

Vorschau der Sensitivität auf der Referenz (nicht Teil der Abnahme, nur Orientierung): über alle 41 Wahlbezirke
liegt p je nach Gewichtung zwischen 0,27 (Bezirke) und 0,75 (nur Vorlagen); ohne 1 und 10 zwischen 0,024 (Bezirke)
und 0,36 (nur Vorlagen); Spearman zur ungewichteten Quote 0,79 (Bezirke) bis 0,99. Von den 20 Themen ist eines
(Grundstück, Bauvorhaben, Stellplätze) über alle 41 Bezirke mit p = 0,021 signifikant. Die Tabelle wird also etwas
zeigen; was, entscheidet der Lauf.

Neue Ausgaben (Spalten festgelegt, Größen geschätzt, soweit nicht gemessen):

| Datei | Zeilen | Spalten | Größe |
|---|---|---|---|
| `processed/themen.parquet` (trägt den Stamp von `topics`) | K = 20 | `thema` Int64 (0 … K−1), `woerter` List(String) (zehn, absteigend), `dokumente` Int64 (dominant), `gewicht_summe` Float64 (Summe der Anteile) | unter 10 KB |
| `processed/themen_dokumente.parquet` | 19 033 | `id` String, `thema` Int64, `anteil` Float64 (des dominanten Themas, vier Stellen) | 0,10 MB gemessen; CSV rund 1,5 MB (die IDs) |
| `interim/themen_anteile.parquet` (nicht veröffentlicht) | 19 033 | `id` String, `anteile` List(Float64) der Länge K, Summe 1 | 0,93 MB gemessen |
| `processed/gewichte_begriffe.parquet` | 5841 | `suchbegriffe` String, `n_bezirke` Int64, `anzahl_treffer` Int64, `gewicht_bezirke` Float64, `gewicht_idf` Float64 | rund 80 KB, CSV rund 250 KB |
| `processed/wahlbezirke_gewichtet.parquet` (trägt den Stamp von `weights`) | 41 × (6 + K) = 1066 | `wahlkreis_id` Int64, `variante` String, `anzahl_treffer_gewichtet` Float64, `trefferquote_gewichtet` Float64; sortiert nach `variante`, `wahlkreis_id` | rund 20 KB, CSV rund 50 KB |

Varianten (Reihenfolge auf der Seite): `einheit`, `bezirke`, `idf`, `antraege_halb`, `nur_vorlagen`, `kombiniert`,
`thema_00` … `thema_19`. Die Mini-Fixture (200 Dokumente, drei Wahlbezirke, 22 Dokumentarten, davon 72 Dokumente
Anträge, Anfragen oder Eingaben) deckt alle Varianten; `expected/` bleibt unberührt, die neuen Dateien haben dort
keine Erwartung.

## 4. Berührungspunkte im bestehenden Code (Datei, Funktion, was sich ändert)

| Datei | Funktion / Stelle | Änderung |
|---|---|---|
| `noxfile.py` | `FORBIDDEN` | `"scikit-learn"` entfernen, Kommentar mit Datum und Verweis auf `decisions.md` Punkt 21; `VERIFY_TARGETS` um `georep.analysis.weights.idf_weight` und `district_weight` ergänzen |
| `pyproject.toml` | `dependencies`, `[[tool.mypy.overrides]]` | `scikit-learn>=1.9`; `sklearn.*` zu `ignore_missing_imports` (keine Stubs, Stand 2026-10-11); `uv lock` |
| `src/georep/defaults.toml` | neu `[analysis]`, `[weights]`, `[[weights.paper_type]]`, `[topics]` | Schlüssel aus § 2 mit Begründung je Zeile |
| `src/georep/settings.py` | neue Modelle `Analysis`, `PaperTypeRule`, `PaperTypeVariant`, `Weights`, `Topics`; `Settings` | Validatoren: Gewichte in [0, 1], Muster kompilierbar, Variantennamen eindeutig und nicht aus der festen Menge, `k ≥ 0`, `0 < max_df ≤ 1`, `combined` nur bekannte Faktoren. Alles zählt zum `fingerprint()` |
| `src/georep/layout.py` | neue Properties `topics`, `topic_documents`, `topic_shares`, `term_weights`, `weighted` | Pfade aus § 3 |
| `src/georep/analysis/regression.py` | `regress`, neu `RegressionPair`, `regression_pair(frame, exclude, *, x, y)` | Umzug aus `report/model.py`; beide Teile optional (`None` ohne Streuung); `spearman(frame, x, reference)` daneben |
| `src/georep/analysis/weights.py` (neu) | `term_weights`, `idf_weight`, `district_weight`, `paper_type_weights`, `compile_rules`, `document_pairs`, `document_weights`, `weighted_hits`, `variants` | reine Funktionen Frame zu Frame mit deal-Verträgen (§ 5, Stufe B) |
| `src/georep/analysis/topics.py` (neu) | `TopicModel`, `fit_topics`, `topic_labels`, `load_stop_words` | der einzige Ort mit `sklearn`-Import |
| `src/georep/analysis/stopwords_de.txt` (neu) | Paketdatei | über `importlib.resources` wie `defaults.toml` |
| `src/georep/pipeline.py` | `build_steps` | Schritte `topics` (lazy Import) und `weights`; `report` bekommt vier Eingaben mehr; Reihenfolge `corpus, topics, index, results, weights, report` |
| `src/georep/export.py` | `csv_plan` | vier Einträge: `themen` (`woerter` mit „; "), `themen_dokumente`, `gewichte_begriffe`, `wahlbezirke_gewichtet` |
| `src/georep/report/model.py` | `OUTLIERS` weg (Settings), `RegressionPair`/`regression_pair` importiert statt definiert; neu `SensitivityRow`, `TopicRow`, `sensitivity_rows`, `topic_rows`; `ReportModel.sensitivity`, `.topics`; `COLUMN_DOCS` vier Tabellen; `published_tables` vier Einträge; `build_report_model` | die Zahlen des Abschnitts |
| `src/georep/report/build.py` | `DESCRIPTIONS`, `build_site` | vier Beschreibungen; Zählung in `SiteSummary` stimmt automatisch |
| `src/georep/report/templates/report.html.j2` | neuer `<section id="gewichtung">` nach `#zusammenhang`; `<p lang="en">` um einen Halbsatz aus den Daten | § 6 |
| `src/georep/cli.py` | `_cmd_regress` | `--varianten` druckt die Sensitivitätstabelle aus `wahlbezirke_gewichtet.parquet` (klein, optional) |
| `tests/unit/__snapshots__/test_cli.ambr` | `georep steps` | bewusst erneuert, Diff im Commit |
| `tests/unit/test_cli.py` | Zählungen „9 geplant", „9 ausgeführt", `function calls == 9` | 11 |
| `tests/golden/test_pipeline.py` | `offline` 9 → 11; `third` um `topics: übersprungen`, `weights: ausgeführt`; `test_two_runs_write_identical_parquet` um `weighted`, `topics`, `topic_shares`; slow-Test: 15 → 23 Dateien, Einheitsvariante gleich `anzahl_treffer`, Regression gleich Tabelle 5 | Golden Master der Option |
| `tests/unit/test_report_build.py` | `test_site_has_index_map_and_fifteen_download_files` | 23 Dateien, umbenennen |
| `tests/bench/test_bench_hot_paths.py` | neu `test_weights_step` | `document_weights` plus `weighted_hits` auf der Mini-Fixture |
| `tests/property/test_contract_cases.py` | `deal.cases` für `idf_weight`, `district_weight` | |
| `docs/architecture.md`, `docs/decisions.md`, `docs/profiling/README.md`, `README.md`, `CHANGELOG.md`, `STATUS.md` | | Stufe F |

Unverändert bleiben `search/`, `prep/`, `analysis/hits.py`, `geo.py`, `stores.py`, die Fixtures unter
`tests/fixtures/mini/expected/`, die Golden-Master-Vergleiche von `results` und `index`.

## 5. Bauplan in Stufen

Jede Stufe ein bis drei Commits, eine Sorte pro Commit, Verhaltensänderung zuerst mit rotem Test; nach jedem Commit
`uv run nox` (im Alltag `uv run pytest -n 2`), Tests in `tmp_path` mit `Layout(tmp/data, tmp/cache, mini_root)`.
Aufwand in Agentenstunden, geschätzt.

### Stufe A: Settings, Abhängigkeit, Layout (2 h, 3 Commits)

1. `defaults.toml` und `settings.py`: `[analysis] exclude_districts = [1, 10]`, `[weights]`, `[[weights.paper_type]]`
   (zwei Regelsätze), `[topics]` (Werte aus § 2) mit Validatoren; `report/model.py` liest `OUTLIERS` aus den Settings.
   Tests in `tests/unit/test_settings.py`: Gewicht 1,5 ist ein Fehler, ungültiges Muster ist ein Fehler, doppelter
   Variantenname ist ein Fehler, `k = 0` erlaubt; der Fingerprint ändert sich mit `topics.k`.
2. `pyproject.toml`: `scikit-learn>=1.9`, mypy-Override, `uv lock`; `noxfile.py`: `FORBIDDEN` ohne scikit-learn;
   `decisions.md` Punkt 21 (Konrads Freigabe, Messung LDA gegen NMF, Begrenzung auf ein Modul, verworfene
   Alternativen). Test `tests/unit/test_dependency_boundary.py`: `grep` über `src/georep` findet `sklearn` nur in
   `analysis/topics.py`.
3. `layout.py`: die fünf Pfade; `runtime_dirs` bleibt (keine neuen Verzeichnisse).
4. Abnahme: `uv run nox` grün, `nox -s deps` meldet scikit-learn nicht mehr; `georep status` zeigt alle Schritte
   „offen: Settings geändert" (der Fingerprint trägt die neuen Schlüssel; das ist richtig, CLAUDE.md).

### Stufe B: `analysis/weights.py` mit Verträgen und Eigenschaften (4 h, 3 Commits)

1. Reine Funktionen, alle Polars, Frame zu Frame:
   - `district_weight(n: int) -> float` und `idf_weight(df: int, n: int) -> float`: `deal.pure`, pre `n ≥ 1`,
     `0 ≤ df ≤ n`, post in [0, 1]; crosshair-fähig.
   - `term_weights(dictionary, index, n_documents) -> gewichte_begriffe`: post Spalten wie § 3, `sorted_unique`
     auf `suchbegriffe`, `gewicht_bezirke` in (0, 1], `gewicht_idf` in [0, 1], `n_bezirke ≥ 1`; ensure: die Begriffe
     sind genau die des Index.
   - `compile_rules(variant) -> list[tuple[Pattern, float]]` und `paper_type_weights(corpus, rules, default) ->
     DataFrame[id, gewicht]`: pre Gewichte in [0, 1]; post eine Zeile je Dokument, Gewicht in [0, 1].
   - `document_pairs(dictionary, index) -> DataFrame[wahlkreis_id, id, suchbegriffe]`: die 51 887 Tripel; ensure:
     die Paarmenge (Bezirk, Dokument) ist dieselbe wie in `hits_by_district` (Vereinigung der `paper_ids`).
   - `document_weights(pairs, term_weights, type_weights | None, topic_weights | None) -> DataFrame[wahlkreis_id,
     id, gewicht]`: max über Begriffe mal Dokumentart mal Thema; post Gewicht in [0, 1], eine Zeile je Paar,
     sortiert; fehlende Faktoren gelten als 1.
   - `weighted_hits(weights, voters, eligible) -> DataFrame[wahlkreis_id, anzahl_treffer_gewichtet,
     trefferquote_gewichtet]`: post `≥ 0`, `anzahl_treffer_gewichtet ≤` Zahl der Paare je Bezirk, `sorted_unique`.
   - `variants(dictionary, index, corpus_types, voters, topic_shares | None, settings) -> wahlbezirke_gewichtet`:
     baut alle Varianten, lange Tabelle; post Spalten, sortiert nach (`variante`, `wahlkreis_id`), jede Variante 
     hat genau die Wahlbezirke der Auswertung; ensure: Variante `einheit` gleich der Zählung aus `hits_by_district`
     (exakt, als Float64 gleich dem Int64).
2. `tests/unit/test_weights.py`: Handbeispiele (Begriff in zwei Bezirken → 0,5; df = N → 0; Regel trifft
   „Antrag SPD", nicht „Beschlussvorlage"; max statt Summe bei zwei Begriffen in einem Dokument); je Vertrag ein
   Gegenbeispiel in `test_contract_violations.py`.
3. `tests/property/test_weights_props.py` (hypothesis, Strategien aus `test_hits_props.py`): Einheitsgewichte
   reproduzieren `hits_by_district` für jedes Wörterbuch und jeden Index; alle Gewichte in [0, 1]; Monotonie (ein
   kleineres Begriffsgewicht senkt keine Bezirkssumme nie und erhöht keine); Bezirksanteile je Begriff summieren zu
   1; IDF fällt monoton in df; Themenzerlegung: für zufällige Anteile mit Zeilensumme 1 ist die Summe der
   `thema_*`-Treffer gleich `einheit` (Toleranz 1e-9 relativ); Spearman in [−1, 1] und 1 für die Einheitsvariante.
   `deal.cases` auf `idf_weight` und `district_weight`.
4. Abnahme: `uv run nox` grün; `nox -s verify` findet kein Gegenbeispiel für die beiden reinen Funktionen;
   `nox -s mutate` über `analysis/` mindestens 75 % getötet (Zahl in `docs/mutation-….md` nachtragen, kein Gate).

### Stufe C: `analysis/topics.py` und Schritt `topics` (4 h, 3 Commits)

1. `load_stop_words(name) -> frozenset[str]` (Paketdatei, Vertrag: alle kleingeschrieben, keine leer);
   `fit_topics(corpus, settings.topics) -> TopicModel(shares: DataFrame[id, anteile], topics: DataFrame[thema,
   woerter, dokumente, gewicht_summe])`: TfidfVectorizer und NMF wie § 2; Zeilen ohne Masse (gemessen keine)
   bekommen gleichverteilte Anteile, damit die Zerlegung hält; `EmptyResultError`, wenn weniger Dokumente mit
   Text als `k` vorliegen oder das Vokabular leer ist. Verträge: post Zeilensummen 1 ± 1e-9, genau `k` Themen,
   `woerter` Länge `top_words` und eindeutig, `dokumente` summiert zur Dokumentzahl; pre `k ≥ 1`. Der Import
   von `sklearn` steht oben im Modul, sonst nirgends.
2. Schritt `topics` in `build_steps`: Eingabe `corpus`; Ausgaben `themen.parquet` (Stamp), `themen_dokumente.parquet`,
   `interim/themen_anteile.parquet`; Rückgabe „20 Themen, 19 033 Dokumente, 20 000 Wörter"; mit `topics.k = 0` fehlt
   der Schritt im Register und `weights` nennt die Anteile nicht als Eingabe. Das Modul wird im Schritt importiert
   (Kommentar: 0,4 s Importzeit, nur wer rechnet, zahlt).
3. `tests/unit/test_topics.py`: zwölf synthetische Dokumente aus drei Wortfamilien, `k = 3`: jede Familie dominiert
   ein Thema, Labels enthalten ihre Wörter, zwei Aufrufe liefern gleiche Frames (`assert_frame_equal`), zu wenige
   Dokumente sind ein Domänenfehler, ein leeres Vokabular ebenso. Golden-Master-Test auf der Mini-Fixture: `k`
   Zeilen, Zerlegung hält, Datei byteidentisch über zwei Läufe (Erweiterung von `test_two_runs_write_identical_parquet`).
4. `georep profile topics` auf der Referenz, Zahlen nach `docs/profiling/README.md` (Erwartung aus der Messung:
   rund 7 s, davon 2 s TF-IDF, 4 s NMF, Rest Parquet).
5. Abnahme: Schritt läuft auf der Referenz unter 60 s (gemessen rund 7 s) und ist damit ein normaler Schritt;
   `nox` grün; die schnelle Suite wird um höchstens zwei Sekunden langsamer (sklearn-Import plus NMF auf 200
   Dokumenten in der Sitzungs-Fixture `mini_run` und in den Pipeline-Tests); Themenlabels auf der Referenz ohne
   Wörter aus der Stopwortliste.

### Stufe D: Schritt `weights`, Pipeline, Golden Master (3 h, 2 Commits)

1. `build_steps`: Schritt `weights` mit Eingaben `dictionary`, `index`, `corpus` (nur `id`, `paper_type` gelesen),
   `voters`, `topic_shares` (wenn `k > 0`); Ausgaben `wahlbezirke_gewichtet.parquet` (Stamp) und
   `gewichte_begriffe.parquet`; Rückgabe „26 Varianten, 41 Wahlbezirke, Einheit = 29 573 Treffer".
   `csv_plan` um die vier Dateien; `regression_pair` nach `analysis/regression.py` (reine Verschiebung, ein Commit).
2. Tests: `test_pipeline.py` (11 Offline-Schritte, Reihenfolge, `third`-Erwartung: `topics` übersprungen, weil nur
   der Korpus zählt und der ist unverändert; `weights` ausgeführt, weil `index` lief), Snapshot von `georep steps`
   bewusst erneuert, CLI-Zählungen; `test_regression_numbers.py` bekommt einen Test, der aus
   `wahlbezirke_gewichtet.parquet` der Referenz die Variante `einheit` zieht und über `regress(…, x="trefferquote_gewichtet")`
   die Werte aus Tabelle 5 auf dieselben Stellen trifft (Steigung 62,1337, r 0,16125, p 0,31385; ohne 1 und 10
   215,3341 / 0,338461 / 0,035069). Bench `test_weights_step`.
3. Abnahme: `uv run pytest -m slow` grün mit den Tabelle-5-Werten über die Einheitsvariante; `results` und
   `index` bleiben byteidentisch zum Stand vor der Option (Vergleich der Parquet-Dateien aus einem Lauf auf
   `main`, im Scratchpad); voller Offline-Lauf auf der Referenz unter 20 s (bisher 7 s, plus rund 7 s `topics`,
   unter 1 s `weights`).

### Stufe E: Berichtsseite (5 h, 3 Commits)

1. `report/model.py`: `SensitivityRow(name, label, description, total, pair: RegressionPair | None, spearman:
   float | None)`, `TopicRow(index, words, documents, hits_share)`; `sensitivity_rows(weighted, voters, columns,
   exclude)` rechnet je Variante beide Regressionen und Spearman gegen `einheit`; `topic_rows(topics, weighted)`;
   Labels der festen Varianten in Deutsch im Modul, Beschreibung mit der Formel in einem Satz; Themen als
   „Thema 3: grundstück, bauvorhaben, …". `COLUMN_DOCS` und `published_tables` um die vier Tabellen, `DESCRIPTIONS`
   in `build.py`. Verträge: eine Zeile je Variante der Datei, `einheit` zuerst mit Spearman 1, Themen in
   Nummernreihenfolge.
2. Vorlage: Abschnitt „Was ändert die Gewichtung?" (§ 6); `<p lang="en">` um einen Halbsatz aus den Daten („under
   k of n alternative weightings the relationship across all districts becomes significant", Zahlen aus dem
   Modell, nichts fest kodiert).
3. Tests: `test_report_model.py` (Zahlen gegen Polars nachgerechnet, Einheitszeile gleich `model.regression`),
   `test_report_render.py` (Abschnitt vorhanden, Zeilen gleich Varianten, keine neuen externen Links, „—" bei
   `None`), `test_report_build.py` (23 Dateien, Prüfsummen, Schema deckt die vier Tabellen), Snapshot nur für die
   Themenzeile der Mini-Fixture, falls stabil, sonst keiner.
4. Seite mit headless Chrome ansehen (§ 8.4 des Meta-Plans), hell und dunkel; Größe von `index.html` messen.
5. Abnahme: `georep run` erzeugt die Seite mit dem Abschnitt; `index.html` unter 1,5 MB (Erwartung rund 710 KB);
   `nox`, `pytest -m slow`, `nox -s bench` grün; `grep -rn "Düsseldorf\|0015" src/` zeigt nur Settings und Doku, und
   `OUTLIERS` ist aus dem Code verschwunden.

### Stufe F: Dokumentation, Profil, Abschluss (2 h, 1 bis 2 Commits)

1. `architecture.md`: Modultabelle (`analysis/weights`, `analysis/topics`), Pipeline-Tabelle (16 Schritte),
   Datenhaltung (`interim/themen_anteile.parquet`, vier Dateien unter `processed/`), Berichtsseite (Abschnitt,
   Größen), Verträge (die neuen), Tests (neue Dateien). `decisions.md` Punkt 21 (falls nicht schon in Stufe A
   vollständig). `docs/profiling/README.md`: Profil von `topics` und `weights` datiert. README: ein Satz zum
   Abschnitt und zu `georep regress --varianten`. `CHANGELOG.md` unter „Unreleased". `STATUS.md`: Zahlen, Laufzeit,
   Bekanntes (Themen sind Labels, keine Deutung; Fingerprint global).
2. Abschlussbericht an den Supervisor: erfüllte und offene Abnahmekriterien, Laufzeiten, Merge-Empfehlung.
3. Abnahme: alle Kriterien aus A bis E, Doku beschreibt den neuen Stand, dieser Plan trägt oben „Status: im Review".

Gesamt: rund 20 Agentenstunden, 15 bis 17 Commits.

## 6. Auswirkung auf die Berichtsseite (Abschnitt, Größe in KB, Unterseite ja/nein)

Ein neuer Abschnitt `<section id="gewichtung">` „Was ändert die Gewichtung?" direkt nach „Trefferquote und
Wahlbeteiligung", keine Unterseite:

1. Zwei Absätze: warum gewichten (Beispiel „Hofgarten" in 172 Dokumenten, „Münchener Straße" in sieben Wörterbüchern,
   aus den Daten), und wie (die Formel in einem Satz, Einheitsgewichte sind Tabelle 5).
2. **Sensitivitätstabelle**, sortierbar wie die Bezirkstabelle: je Variante eine Zeile mit Name, Gewichtsumme
   (Σ über Bezirke), dann n, Steigung, Achsenabschnitt, r, R², p für „alle" und für „ohne 1 und 10", zuletzt
   Spearman-ρ zur ungewichteten Quote; `None` als „—"; die Einheitszeile ist hervorgehoben und trägt dieselben
   Zahlen wie Tabelle 5 darüber (ein Test prüft das). 26 Zeilen × rund 450 Bytes ≈ 12 KB. Die Themenzeilen stehen
   unter einer Zwischenzeile „je Thema (Anteil des Dokuments am Thema)".
3. **Themen**: Tabelle mit Nr., den zehn Wörtern, Zahl der dominierten Dokumente, Anteil an den gewichteten
   Treffern; eine Fußnote, dass die Wörter das Thema beschreiben, nicht benennen, und dass die Nummern nur für
   diesen Datenstand gelten. 20 Zeilen ≈ 5 KB.
4. Ein Satz aus den Daten, unter wie vielen Varianten der Zusammenhang über alle Wahlbezirke das 5-%-Niveau
   erreicht, und unter wie vielen ohne die Ausreißer; keine Wertung.

Größe: rund 20 KB mehr in `index.html` (686 KB heute, erwartet rund 710 KB, Budget 1,5 MB). Downloads: vier Tabellen
als Parquet und CSV, zusammen rund 2 MB, davon 1,5 MB die CSV der Dokument-Themen (die IDs); `schema.json`
wächst um vier Tabellen. Die Download-Tabelle auf der Seite wird 23 statt 15 Zeilen lang. Das
Streudiagramm bleibt, wie es ist; keine zweite Karte.

## 7. Risiken und Fallstricke

- **Der Settings-Fingerprint ist global**: `topics.k` oder eine Regel ändern, und alle Schritte sind „Settings
  geändert", auch `index` (4 s). Hinnehmbar (Sekunden); ein Fingerprint je Schritt über den Settings-Teilbaum, den
  der Schritt liest, wäre ein Fundament für alle Optionen (§ 9).
- **Determinismus des Themenmodells**: auf einem Rechner byteidentisch (gemessen); zwischen Rechnern (andere
  BLAS-Bibliothek, CI unter Ubuntu) können Anteile in der zwölften Stelle abweichen. Darum prüfen die Golden-Master-
  Tests auf der Referenz nur Invarianten (K Themen, Zerlegung, Labels ohne Stopwörter), nicht einzelne Zahlen; der
  Byteidentitätstest läuft zweimal im selben Prozess. Vier Stellen Rundung in `themen_dokumente.parquet`.
- **Ein Thema aus Funktionswörtern** (gemessen ohne Stopwörter: „auch, düsseldorf, oder, innen, als" mit 4144
  Dokumenten). Die Stopwortliste nimmt die Funktionswörter; der Stadtname bleibt (er ist in allen Städten der
  häufigste Eigenname und gehört nach Option 10 nicht in eine deutsche Liste). Prüfen nach dem ersten Lauf, ob das
  Thema verschwindet; wenn nicht, `max_df` auf 0,3 senken und in `decisions.md` begründen.
- **Varianten ohne Streuung** (Mini-Fixture: `nur_vorlagen` kann drei gleiche Quoten liefern, `thema_NN` kann in
  allen drei Bezirken null sein): `regress` wirft `EmptyResultError`, die Zeile zeigt „—". Nie `pytest.approx` auf
  Nullen sparen: `0.0 == 0.0` ist hier exakt gemeint.
- **`column_docs` wirft `SchemaError`**, sobald eine veröffentlichte Spalte ohne Beschreibung ist: die vier Tabellen
  zuerst in `COLUMN_DOCS` eintragen (roter Test), dann veröffentlichen.
- **`max` über Begriffe mit Polars**: `group_by(wahlkreis_id, id).agg(pl.col("gewicht").max())` ist richtig; ein
  `sum` an dieser Stelle verletzt den Vertrag `g ≤ 1` sofort, und der hypothesis-Test mit zwei Begriffen in einem
  Dokument fängt es.
- **Regex auf `paper_type`**: `None` bekommt `default` (auf der Referenz hat jedes der 19 108 Dokumente eine Art,
  `PaperRecord` erlaubt aber `None`); das Muster
  wird einmal kompiliert (`compile_rules`), nicht je Zeile; `str.contains` in Polars mit `(?i)`-Präfix statt
  `map_elements` (die Vorschau im Scratchpad nahm `map_elements`, das ist im Paket der falsche Weg).
- **Importzeit von scikit-learn** (rund 0,4 s): nur im Schritt importieren; ein Test misst nicht die Zeit, aber
  `tests/unit/test_dependency_boundary.py` findet den Import nur in `analysis/topics.py`.
- **Lockfile und CI**: `uv sync --locked` in CI zieht scikit-learn (rund 15 MB Wheel); die CI-Laufzeit steigt um
  wenige Sekunden. Python 3.14-Wheels gibt es (1.9.1 installiert sich).
- **Seitenbudget und Downloads**: `index.html` bleibt weit unter 1,5 MB; die Download-Größe wächst um rund 2 MB,
  vor allem durch IDs in CSV. Wenn die Synergiephase das zu viel findet, fällt die CSV der Dokument-Themen weg
  (ein Eintrag weniger in `csv_plan`, dann aber eine Ausnahme von „jede Tabelle auch als CSV").
- **Hypothesis-Laufzeit**: die Varianten-Eigenschaften bauen mehrere Frames je Beispiel; mit `max_examples=100`
  (`dev`) bleibt das unter zwei Sekunden, sonst Strategien verkleinern, nicht `deadline` anheben.
- **Ausreißerspalte**: `exclude_districts` fest für alle Varianten (§ 2); eine Variante, in der 1 und 10 nicht die
  höchsten Quoten haben, zeigt trotzdem „ohne 1 und 10". Das steht als Satz unter der Tabelle.
- **Nie unter `reference/` schreiben**, `expected/` nicht anfassen: die neuen Dateien haben dort keine Erwartung;
  die Erwartung ist die Identität mit `anzahl_treffer` und Tabelle 5.

## 8. Offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | Warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 6.1 | Reichen die sechs festen Varianten (Einheit, Bezirke, IDF, Anträge halb, nur Vorlagen, kombiniert) plus die 20 Themen, oder soll es weniger (Tabelle kürzer) oder mehr (etwa Themen hart zugeordnet) geben? | bestimmt die Länge der Tabelle und die Zahl der Settings-Schlüssel | genau diese; Themen weich (Anteile) |
| 6.2 | Gilt die Regel „Antrag, Anfrage, Haushaltsantrag, Eingabe sind nicht Verwaltung" (alles andere ist Vorlage) als Klassengrenze für die Dokumentart? | die beiden Regelsätze hängen daran; „A+F Beschluss" und „Bedarfsbeschluss" zählen so als Vorlage | ja; Muster in `defaults.toml`, änderbar ohne Code |
| 6.3 | K = 20 Themen und nur das dominante Thema je Dokument veröffentlichen (volle Anteile bleiben in `interim/`)? | Lesbarkeit der Tabelle gegen Auflösung; Download-Größe | ja; K in den Settings |
| 6.4 | Die Spalte „ohne Ausreißer" für alle Varianten mit denselben Wahlbezirken (1 und 10, aus `analysis.exclude_districts`)? | Vergleichbarkeit gegen Treue zur Definition „die zwei höchsten Quoten" | ja, fest; ein Satz unter der Tabelle |
| 6.5 | Sollen gewichtete Quoten auch auf Karte und Bezirkstabelle umschaltbar sein? | Konflikt mit Option 5 (dritte Kartenklasse) und dem Seitenbudget | nein, nur der Abschnitt; die lange Tabelle macht einen späteren Umschalter möglich |
| 6.6 | `kombiniert` = IDF × Anträge halb? | eine Zeile der Tabelle, Faktoren in `weights.combined` | ja |
| 6.7 | Darf `OUTLIERS = (1, 10)` aus `report/model.py` nach `[analysis] exclude_districts` in die Settings, obwohl das Option 3 ebenso betrifft? | nimmt einen Düsseldorf-Wert aus dem Code; zwei Branches würden dieselbe Zeile ändern | ja, in Stufe A, als Angebot ans Fundament der Synergiephase |

Keine Frage blockiert; scikit-learn ist freigegeben (Konrad, 2026-10-11, `fragen.md` Nr. 3).

## 9. Vorbereitung für Option 10 (was wird konfigurierbar, welche Modulgrenze entsteht)

Konfigurierbar, alles in `defaults.toml` mit Begründung je Zeile und im Fingerprint: `analysis.exclude_districts`
(statt der Konstante im Berichtsmodell), `weights.paper_type` (Regelsätze mit Regex, Gewicht, Standard; je Stadt
andere Dokumentarten), `weights.combined` (Faktoren der Kombination), `topics.k`, `min_df`, `max_df`,
`max_features`, `top_words`, `stop_words` (Sprachkürzel der Paketdatei oder leer), `random_state`. Keine Stadt, kein
Begriff, kein Wahlbezirk im Code; `k = 0` schaltet das Themenmodell ab, ohne dass etwas fehlt.

Modulgrenzen: `analysis/weights.py` ist reines Polars mit Verträgen, kennt weder Dateien noch Settings-Objekte
(bekommt Regeln und Zahlen als Argumente) und ist von außen mit jedem Frame nutzbar; `analysis/topics.py` ist der
einzige Ort, der scikit-learn importiert, mit einer kleinen Schnittstelle (`fit_topics(corpus, settings) ->
TopicModel`), hinter der ein anderes Modell (LDA, ein Transformer) stehen könnte, ohne dass `weights` oder `report`
es merken; `analysis/regression.py` trägt die Kennzahlvariante (`regression_pair(frame, exclude, x=…)`), die Option 3
mit Kontrollvariablen und Option 2 mit einer zweiten Periode wiederverwenden; die lange Tabelle
`wahlbezirke_gewichtet.parquet` (Wahlbezirk, Variante, Wert) ist die Form, in der weitere Kennzahlen (Gremium aus
Option 5, Periode aus Option 2) ohne Schemaänderung dazukommen. Für die Methodennotiz liefert der Abschnitt die
Sensitivitätstabelle als Beleg, dass die Kennzahl der Arbeit eine von mehreren vertretbaren ist.

Gemeinsame Bausteine, die der Supervisor erwägen sollte: ein Fingerprint je Schritt (Settings-Teilbaum je Schritt);
ein Register der veröffentlichten Tabellen (`published_tables`, `COLUMN_DOCS`, `DESCRIPTIONS`, `csv_plan` wachsen
mit jeder Option an vier Stellen, ein `report/tables.py` würde die Konflikte bündeln); ein Abschnittsmechanismus
der Vorlage (Reihenfolge der `<section>`-Blöcke, jede Option ein Block); die Klassifikation der Dokumentart per
Regex (Option 5 parst `reference` und `paper_type` zum Gremium; dieselben Muster könnten dort stehen und hier eine
Variante `gremium` liefern).

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

Für Option 6 im Besonderen:

- **Stufe A ist kleiner**: `[analysis] exclude_districts = [1, 10]` und `regression_pair(frame, exclude, *, x,
  y, y_scale)` in `analysis/regression.py` liegen im Fundament F3 (`OUTLIERS` ist weg, `RegressionPair` wohnt
  dort); 06 ergänzt nur `[weights]`, `[[weights.paper_type]]`, `[topics]`, die Abhängigkeit scikit-learn und die
  Layout-Pfade. `spearman` kommt wie geplant zu `analysis/regression.py`.
- **Sensitivitätstabelle**: jede Variante rechnet `regression_pair(frame, settings.analysis.exclude_districts,
  x="trefferquote_gewichtet")` auf der langen Tabelle, gefiltert je `variante`.
- **Tabellen**: `themen`, `themen_dokumente`, `gewichte_begriffe`, `wahlbezirke_gewichtet` als Einträge in
  `TABLES` (`themen` und `themen_dokumente` mit `optional=True`, weil `topics.k = 0` den Schritt abschaltet).
  Für `themen_dokumente` (eine Zeile je Dokument mit Text) das Prädikat `one_row_per_document` von 04 nutzen,
  sobald gemerged; bis dahin dieselbe Bedingung inline.
- **Abschnitt**: `sections/34-gewichtung.html.j2`, sortierbare Tabelle über die vorhandenen `data-sort`-Köpfe.
- **Dokumentart**: die Regex-Regeln auf `paper_type` bleiben bei 06 (Gewichte, keine Klassen); Option 5 parst
  die Drucksachennummer, Option 4 den Urheber. Keine gemeinsame Datei.
- **Reihenfolge**: 06 merged als Dritte (nach 08, 05), damit das Lockfile mit scikit-learn früh auf `main` ist.
- **Fragen**: alle sieben vorentschieden (fragen.md); 6.7 ist durch das Fundament erledigt.
