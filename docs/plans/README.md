# Pläne

## Vorverarbeitung 2026-11

Stand 2026-11-26, `main` auf `v0.32.0`. Meta-Plan:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md). **Fortsetzung:
[../plan-zeigen-2026-11.md](../plan-zeigen-2026-11.md)** (Konrad, 2026-11-26: zuerst Stufe 3 der
gebauten Vorhaben, dazu 16 und 28 Ebene A parallel und 19 Stufe 2). Je Vorhaben ein Messdokument
`NN-name.md` mit Messskript `NN-name-messung.py` (Stufe 1, Vorlage § 12.1); die Änderungen der Synergie
stehen in § 10 des jeweiligen Messdokuments ([00-synergien-2026-11.md](00-synergien-2026-11.md) ist der
Stand von Haltepunkt A und historisch); [fragen-2026-11.md](fragen-2026-11.md) sammelt die Fragen an
Konrad. Stufen: 1 Messen, 2 Bauen, 3 Zeigen (Meta-Plan § 8). Alle Branches `feat/NN-name` und
`fund/FN-name` sind gemerged, Worktrees und Branches am 2026-11-26 entfernt. Diese Tabelle ist der
Stand; der Supervisor führt sie bei jedem Urteil und Merge nach.

**Fundamente, alle auf `main`**: F2 Register und F3 Spannen (`v0.17.0`, Punkt 69); F6 OParl-Sitzungen,
Tagesordnung, Personen (`v0.18.0`, Punkt 70; Netzlauf für alle vier Profile am 2026-11-23/24,
[../runbook-sitzungen.md](../runbook-sitzungen.md) § 9: Hauptperiode 1 672 Sitzungen, 44 231
Tagesordnungspunkte, 97 112 Beratungen, 632 Personen); F4 Validierung (`v0.19.0`, `v0.20.0`, Punkt 71);
F5 Modellnaht (`v0.21.0`, Punkt 72; jeder Modelllauf unter `gpu-queue/gpu.lock`); F1 Rohtext
(`v0.22.0`, Punkt 73; Paket nur für die Hauptperiode, Frage 18); F7 Fundament-Nachzug (`v0.23.0`,
Punkt 74: `early_steps`, `http` an den Beiträgen, Zusatzspalten an Spannen, `flatten_with_offsets`,
Prüfung der Schrittfolge).

**Nachzug vor Stufe 3**: Abschnitte aus fremden Beiträgen auf einer Unterseite sind seit `v0.33.0` da
(Vorarbeit V1, Punkt 86); seit `v0.34.0` nennt der Prüfsatz in `guete.json` das Modell je Rolle, und
`12-kennungen-2-f4`, `16-ortsbezug-f4`, `16-ortsbezug-2-f4` und die Prüfstichprobe `14-vorgaenge-3-f4`
(50 von 50 Kanten richtig, Kodierer B auf Sonnet) liegen im Format von F4 (Vorarbeit V3, Punkt 87).
Offen in F4 bleiben `12-kennungen-recall-f4` und ein Maß für „Kategorie im Thema-Set" (17); beide sind
nicht Teil der Phase „Zeigen". Die erste Stufe 3 ist `akteure.html` (`v0.35.0`).

| Nr. | Vorhaben | Urteil (Stufe 1) | Stufe 2 | Stufe 3 | Endzustand oder wartet auf |
|---|---|---|---|---|---|
| 11 | Struktur der Dokumente | **bauen** (2026-11-23): Beschlussvorschlag 188/200 streng, Kopffelder 0,95 bis 1,0, α ≥ 0,99 | `main`, `v0.30.0`, Punkt 81 (`struktur-1` unverändert, früher Schritt vor `weights`) | offen: Downloadzeile `dokumente_kopf` | Stufe 3, mit 12 in einer Version |
| 12 | Kennungen und Beträge | **bauen** in vier Arten (2026-11-23, Bestätigung an frischer Stichprobe): Bauleitplanung (Fassung 1), Betrag (Fassung 1, ohne Rolle), Termin (Fassung 2, ohne Fristfunktion), Verwaltungseinheit (Fassung 2: Präzision 0,956, Recall 0,887); fallen: Haushalt, Rechtsgrundlage, Rolle eines Betrags, Fristfunktion (Frage 20) | `main`, `v0.31.0`, Punkt 82 | offen: Download `kennungen.parquet` | Stufe 3, nach dem F4-Nachzug `12-kennungen-2-f4` |
| 13 | Dubletten und Dokumentfamilien | **verworfen** (2026-11-23, 200 Paare, α 0,941): keine Grenze erreicht die gewichtete Präzision 0,95 (τ = 0,9: 0,948); dort lägen 0,5 % der Dokumente in Familien, höchstens 1,4 % Verlust je Wahlbezirk | – | – | **Endzustand verworfen**; MinHash an 23, Fortschreibungen an 14 |
| 14 | Vorgänge | **bauen, mit der Rückfallregel** (2026-11-23): stark nur Kanten aus Titel, Anlage, Nachtragsnummer, Sammelbericht; 104/106 = 0,981 (Wilson 0,934–0,995); 3 563 starke Kanten, 2 169 Vorgänge | `main`, `v0.25.0`, Punkt 76 | offen: `vorgaenge.html` und der allgemeine Haken des Dokumentdialogs, an den sich 18 und 26 hängen | Stufe 3, nach dem F4-Nachzug (104/106 steht nicht in `guete.json`) |
| 15 | Dokumentfunktion und gemeinsame Anträge | **bauen, Variante B** (2026-11-23): κ 0,905; Antragsteller 119/119, Recall 0,86 | `main`, `v0.24.0`, Punkt 75 | **`akteure.html` auf `main`** (`v0.35.0`, Punkt 88), Grundseite für 24, 27, 28 | gezeigt |
| 16 | Ortsbezug verfeinern | **bauen** (2026-11-23): Stelle je Treffer (explorativ), Hausnummern (92,3 % verortbar), Nebenregel C als Gewichtsvariante `ortsbezug` (frische 100 Paare: F1 0,828, κ 0,249), nicht als Standardzählung | **nicht gebaut**; seine Voraussetzungen (F1, F7, 11, `point_shares` aus 22) liegen auf `main` | Gewichtungszeilen auf `index.html`; Radio auf der Karte nur auf Konrads Wunsch (Frage 45) | Stufe 2; vorher § 10 durch den Supervisor (§ 6 ist durch die Synergie überholt) |
| 17 | Zeit und Neuigkeiten | **bauen** (2026-11-23): Lexikon 2026-11-23.1 mit Präzision 94/100, 41 von 41 Feeds gültig; H17.2 bestätigt, H17.1 und H17.3 nicht | `main`, `v0.27.0`, Punkt 78 | offen: `zeit.html`, Feed-Liste der laufenden Periode | Stufe 3 |
| 18 | Einbettungen, Ähnlichkeit, Suche | **bauen** (2026-11-24): nDCG@10 Einbettung 0,883 gegen BM25 0,709; ähnliche Dokumente Präzision@5 0,832; keine Cluster; Vektoren nicht ins Repo (Frage 26) | `main`, `v0.26.0`, Punkt 77 (`georep search`, Nachbartabelle als Paket) | offen: „ähnliche Dokumente" im Dokumentdialog | Stufe 3, nach dem Dialog-Haken von 14; Lizenz der Modellgewichte (Frage 47) |
| 19 | Politikfelder (CAP) | **bauen mit Weg 3b** (2026-11-24): Nachbau der Babel Machine, Makro-F1 0,704 (0,620–0,807), unter 15 GPU-Minuten für alle Perioden; Gewichte nur lokal | **nicht gebaut** | `themen.html` | Stufe 2 (GPU unter 15 min), Paket und Tabelle getrennt unter CC BY-NC-SA 4.0 (Frage 37, beantwortet 2026-11-26); vorher § 10 durch den Supervisor |
| 20 | Kurzfassungen (lokal) | **bauen mit gemma4** (2026-11-24, zwei Vorbehalte); die vorab festgelegte Nachmessung an 50 frischen Dokumenten (2026-11-26) verwarf gemma4 (4/50) und qwen3.6:27b (5/50, Grenze 2) | `main`, `v0.32.0`, Punkt 83: gebaut, in allen Profilen aus, kein Stapellauf (Frage 38) | keine: Kurzfassungen werden nie veröffentlicht | **Endzustand gebaut und aus**; weiter nur mit einem Codebuch Fassung 2 als eigenes Vorhaben |
| 21 | Geld auf der Karte | nicht gemessen | – | – | Stufe 1, nach Stufe 2 von 16 (11 und 12 liegen vor); Briefing überholt (Meta-Plan § 11) |
| 22 | Bedarf und Aufmerksamkeit | **bauen** (2026-11-23): vier offene Quellen plus Lärm; H1 bestätigt, aber nur zwischen Stadtbezirken; H2, H3 nicht | `main`, `v0.29.0`, Punkt 80 | offen: `bedarf.html` | Stufe 3 |
| 23 | Textübernahme | **verworfen** (2026-11-23, 100 Paare, α 0,950): keine politische Art erreicht Präzision 0,9 (Musteranträge 0,889, über Fraktionsgrenzen 0,296); gemeinsamen Text findet das Verfahren zuverlässig | – | – | **Endzustand verworfen**; eine Neumessung mit den Kanten aus 14 wäre ein eigenes Vorhaben (`docs/todo.md`) |
| 24 | Anfragen als Kontrolle | **umbauen** (2026-11-23, 100 Zuordnungen, α 0,954): keine Schicht erreicht 0,9 (Fachausschuss 0,773, hochgerechnet 0,721); H1 ungerechnet | – | – | eine Umbaurunde (neue Stichprobe, Codebuch .2): Zulieferer 26 liegt vor, 19 nicht; die Antwortanlagen brauchen einen eigenen Stichprobenabruf ihrer PDFs (der Netzlauf von F6 brachte keine PDFs); umbauen oder verwerfen ist Frage 41 |
| 25 | Wahlprogramme und Versprechen | nicht gemessen; Quellen gesammelt (2026-11-23, [25-quellen.md](25-quellen.md)): 24 Programme und 3 Vereinbarungen, Hauptperiode 83/90 Sitze; Texte lokal | – | – | Stufe 1; die Eingaben 14, 18 und 26 liegen vor; Briefing teils überholt (Meta-Plan § 11) |
| 26 | Beschlusslage und Antragserfolg | **bauen mit Rückfall 1** (2026-11-24): acht Klassen der Beschlusslage, Ergebnis für 94,3 % der Anträge; 150/150 (schwacher Beleg: dasselbe Modell, 69 Fälle mechanisch); der Prüfauftrag fällt | `main`, `v0.28.0`, Punkt 79 | offen: Abschnitte auf `vorgaenge.html`, Beschluss im Dokumentdialog | Stufe 3, nach dem F2-Nachzug, dem Dialog-Haken von 14 und den Kürzeln `gr/400224`, `gr/65` mit A/B-Bau |
| 27 | Personen und Mandatstyp | **bauen, eingeschränkt** (2026-11-24): Dokument → Person 194/194 (schwacher Beleg), Recall 0,69; Mandatstyp nur in der laufenden Periode bekannt (92/93; Hauptperiode 62/94); H1 nicht entscheidbar | **nicht gebaut** | Abschnitt auf `akteure.html`, nur Rollen und Zählungen ab fünf Personen | Stufe 2 (Fragen 43 und 44: Wahlpaket, Kennungen); vorher § 10 durch den Supervisor |
| 28 | Abstimmungen und Kooperation | **Ebene A bauen, Ebene B verwerfen** (2026-11-24): Ergebnis und Mehrheitsform aus `result` 0,982 bei 86,4 % Abdeckung; Positionen je Fraktion aus Niederschriften 0,765 | **nicht gebaut** (Ebene A braucht kein Netz) | Abschnitt auf `akteure.html` | Stufe 2 Ebene A; Ebene B nur mit Frage 40; vorher § 10 durch den Supervisor |
| 29 | Anwendungen für die Ratsarbeit | nicht gemessen | – | – | Stufe 1, zuletzt; 14, 18 und 26 liegen vor, 20 ist aus (kein Vorlagenspiegel mit Kurzfassungen); Briefing überholt (Meta-Plan § 11) |

## Ausbau 2026-10 (abgeschlossen am 2026-10-12, historisch)

Meta-Plan: [../plan-ausbau-2026-10.md](../plan-ausbau-2026-10.md). Je Option ein Plan nach dessen § 8.3,
geschrieben vom jeweiligen Unteragenten auf seinem Branch; `00-synergien.md` schrieb der Supervisor;
`fragen.md` sammelte die Fragen an Konrad (§ 6). Alle Pläne sind historisch; gültig sind
[../architecture.md](../architecture.md) und [../decisions.md](../decisions.md).

| Nr. | Plan | Branch | Status |
|---|---|---|---|
| 00 | `00-synergien.md` | `main` | geschrieben 2026-10-12, historisch |
| 01 | `01-staedte.md` | `feat/01-staedte` | gemerged 2026-10-12 |
| 02 | `02-zeitreihe.md` | `feat/02-zeitreihe` | gemerged 2026-10-12 |
| 03 | `03-kontrollvariablen.md` | `feat/03-kontrollvariablen` | gemerged 2026-10-12 |
| 04 | `04-parteien.md` | `feat/04-parteien` | gemerged 2026-10-12 |
| 05 | `05-gremien.md` | `feat/05-gremien` | gemerged 2026-10-12 |
| 06 | `06-gewichtung.md` | `feat/06-gewichtung` | gemerged 2026-10-12 |
| 07 | `07-monitoring.md` | `feat/07-monitoring` | gemerged 2026-10-12 |
| 08 | `08-suche.md` | `feat/08-suche` | gemerged 2026-10-12 |
