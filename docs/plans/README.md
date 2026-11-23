# Pläne

## Vorverarbeitung 2026-11

Meta-Plan: [../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md). Je Vorhaben ein
Messdokument `NN-name.md` mit Messskript `NN-name-messung.py` (Stufe 1, Vorlage § 12.1), geschrieben vom
Mess-Agenten auf seinem Branch; `00-synergien-2026-11.md` schreibt der Supervisor; `fragen-2026-11.md`
sammelt die Fragen an Konrad. Stufen: 1 Messen, 2 Bauen, 3 Zeigen (§ 8). Diese Tabelle ist der Stand;
der Supervisor führt sie bei jedem Start, Urteil und Merge nach.

| Nr. | Vorhaben | Branch | Stufe | Stand |
|---|---|---|---|---|
| F1 | Rohtext | `main` | Fundament | auf `main` (`v0.22.0`, Punkt 73, 2026-11-23) nach drei Runden mit Review; Paket der Hauptperiode (14,2 MB) nur einmal in der Historie; die anderen Perioden lesen ihren Rohtext lokal (Frage 18) |
| F2 | Register | `main` | Fundament | auf `main` seit 2026-11-23 (`v0.17.0`, Punkt 69) |
| F3 | Spannen | `main` | Fundament | auf `main` seit 2026-11-23 (`v0.17.0`, Punkt 69) |
| F4 | Validierung | `main` | Fundament | auf `main` (`v0.19.0`, Punkt 71; vierte Runde `v0.20.0`, 2026-11-23); 11, 12, 14, 15, 17 im neuen Format (`-f4`); offen: Endlabels je Markierung und Recall gegen die Spannen eines Verfahrens (kommt mit dem Bau von 12), ein Maß für „Kategorie im Thema-Set" (17) |
| F5 | Modellnaht | `main` | Fundament | auf `main` (`v0.21.0`, Punkt 72, 2026-11-23) nach vier Runden mit Review; ollama war am 2026-11-23 einige Stunden angehalten, seit dem Abend ist die GPU wieder frei (Sperre `gpu-queue/gpu.lock`) |
| F6 | OParl: Sitzungen, Tagesordnung, Personen | `main` | Fundament | auf `main` seit 2026-11-23 (`v0.18.0`, Punkt 70), nach zwei Review-Runden; Konrads Netzlauf nach `docs/runbook-sitzungen.md` § 5 kann starten |
| F7 | Fundament-Nachzug | `fund/F7-nachzug` | Fundament | läuft seit 2026-11-23: früher Einhängepunkt vor `weights`, `http` an den Beiträgen, Zusatzspalten in F3, `flatten_with_offsets` (Synergien § 3.1) |
| 11 | Struktur der Dokumente | `feat/11-struktur` | 1 → 2 | Kodierung bestätigt (§ 4.1): Beschlussvorschlag 188/200 = 0,94 streng, Kopffelder 0,95 bis 1,0, α ≥ 0,99; **Urteil bauen**, Stufe 2 wartet auf Haltepunkt A |
| 12 | Kennungen und Beträge | `feat/12-kennungen` | 1 | Bestätigung ausgewertet (2026-11-23, frische Stichprobe, 410 Aufgaben): **bauen** Bauleitplanung (Fassung 1), Betrag (Fassung 1, ohne Rolle), Termin (Fassung 2, ohne Fristfunktion), Verwaltungseinheit (Fassung 2: Präzision 0,956, Recall 0,887); **fällt** Haushalt (Recall 0,716), Rechtsgrundlage (Präzision 0,861, Gesetz im Normwert 0,805), Rolle eines Betrags, Fristfunktion (Frage 20) |
| 13 | Dubletten und Dokumentfamilien | `feat/13-dubletten` | 1 | **verworfen** (2026-11-23, nach der Kodierung von 200 Paaren, α 0,941): keine Grenze erreicht die gewichtete Präzision 0,95 (bei τ = 0,9: 0,948), und selbst dort lägen nur 0,5 % der Dokumente in Familien, höchstens 1,4 % Verlust je Wahlbezirk; Befund „es gibt kaum Dubletten"; MinHash geht an 23, Fortschreibungen an 14 |
| 14 | Vorgänge | `feat/14-vorgaenge` | 1 → 2 | **Urteil bauen, mit der Rückfallregel** (2026-11-23): stark nur Kanten aus Titel, Anlage, Nachtragsnummer, Sammelbericht; 104/106 = 0,981 (Wilson 0,934–0,995); 3 563 starke Kanten, 2 169 Vorgänge, 39,6 % der Anfragen mit Antwort; Stufe 2 läuft seit 2026-11-23 (nach Haltepunkt A), mit einer eigenen Stichprobe von rund 50 Rückfall-Kanten daneben (Frage 9.18) |
| 15 | Dokumentfunktion und gemeinsame Anträge | `feat/15-funktion` | 1 → 2 | **Urteil bauen, Variante B** (2026-11-23): κ 0,905 (A 0,829, Untergrenze 0,748), Fehler nur bei Anträgen; Urheber-Präzision 119/119, Recall 0,86; Restklasse heißt auf der Seite „Funktion nicht erkannt"; Stufe 2 läuft seit 2026-11-23 (nach Haltepunkt A) |
| 16 | Ortsbezug verfeinern | `feat/16-ortsbezug` | 1 → 2 | **Urteil bauen** (2026-11-23): Stelle je Treffer (explorativ) und Hausnummern (92,3 % verortbar); Nebenregel C an einer frischen Stichprobe bestätigt (100 Paare: F1 0,828 mit Intervall 0,769–0,882, κ 0,249, Kodierer α 0,974) und wird die Gewichtsvariante `ortsbezug`, nicht die Standardzählung, weil die triviale Regel „alles handelt von" mit 0,878 darüber liegt; die Verzerrung durch die Wörterbuchgröße bleibt; Stufe 2 wartet auf F1, 11 und Haltepunkt A |
| 17 | Zeit und Neuigkeiten | `feat/17-zeit` | 1 | Kodierung ausgewertet (2026-11-23): **bauen**, Lexikon 2026-11-23.1 mit Präzision 94/100 (Wilson 0,875–0,972), α 0,957 / 0,928; H17.2 bestätigt, H17.1 und H17.3 nicht (gewichtet 55,5 % der Strukturtreffer nennen die Bundesebene, meist Umsetzung); Lexikon Version 2 nur Vorschlag |
| 18 | Einbettungen, Ähnlichkeit, Suche | `feat/18-einbettungen` | 1 | Messdokument auf `main` (2026-11-23, vorab festgelegt vor jedem Lauf): Hauptperiode eingebettet (47 407 Stücke, 12 min), BM25 und Einbettung finden verschiedene Dokumente (21 % gemeinsam unter den ersten zehn); Cluster tragen nicht (schlechter als NMF); Kodierung von 916 Such- und 383 Nachbarpaaren läuft |
| 19 | Politikfelder (CAP) | `feat/19-politikfelder` | 1 | Messung läuft (seit 2026-11-23, nach F5 und der Freigabe der GPU) |
| 20 | Kurzfassungen (lokal) | `feat/20-kurzfassungen` | 1 | Messdokument auf `main` (2026-11-23): beide Modelle verfehlen die Treue (0,516 / 0,689), weil die Prüfung deutsche Substantive für Namen hält (von Hand 0 und 2 von 200 falsch); **umbauen**: eine Runde mit der vorab festgelegten Klasse e Fassung 2 an frischen 200 (läuft); Durchsatz qwen 2,98 s, gemma 1,09 s je Dokument, Hauptperiode 6 bis 17 GPU-Stunden; Bewertung durch Maßstab und zwei Kodierer läuft; Kurzfassungen werden nie veröffentlicht |
| 21 | Geld auf der Karte | `feat/21-geld` | – | wartet auf 11, 12, 16 |
| 22 | Bedarf und Aufmerksamkeit | `feat/22-bedarf` | 1 → 2 | **Urteil bauen** (2026-11-23): vier offene Quellen plus Lärm; H1 (Unfälle → Verkehrsdokumente) bestätigt, aber nur zwischen Stadtbezirken; H2 zeigt in Richtung ungleicher Aufmerksamkeit ohne Nachweis; Stadtbezirk als Schicht in jede Rechnung; Stufe 2 wartet auf Haltepunkt A |
| 23 | Textübernahme | `feat/23-textuebernahme` | 1 | **verworfen** (2026-11-23, nach der Kodierung von 100 Paaren, α 0,950): keine politische Art erreicht Präzision 0,9 (Musteranträge 0,889, über Fraktionsgrenzen 0,296); gemeinsamen Text findet das Verfahren zuverlässig (92/92), die Verwechslung liegt bei Bausteinen und Zitaten im selben Verfahren; eine neue Messung mit den Kanten aus 14 und frischer Stichprobe wäre ein eigenes Vorhaben (`docs/todo.md`) |
| 24 | Anfragen als Kontrolle | `feat/24-kontrolle` | 1 | **umbauen** (2026-11-23, nach der Kodierung von 100 Zuordnungen, α 0,954): keine Schicht erreicht Präzision 0,9 (Fachausschuss 0,773, hochgerechnet 0,721); H1 vorab festgelegt und ungerechnet; die eine Umbau-Runde wartet auf eine bessere Quelle des antwortenden Amts (Antwortanlagen nach dem Netzlauf, 19 oder 26), mit neuer Stichprobe nach Codebuch .2; Dezernatstabelle lokal |
| 25 | Wahlprogramme und Versprechen | `feat/25-versprechen` | Quellen | Sammlung auf `main` (2026-11-23, `docs/plans/25-quellen.md`): 24 Programme und 3 Vereinbarungen, Hauptperiode 83/90 Sitze; Texte lokal; Stufe 1 wartet auf 18 (Einbettungen, misst seit dem 2026-11-23) und 26 (Beschlusslage, Netzlauf) |
| 26 | Beschlusslage und Antragserfolg | `feat/26-beschluesse` | – | wartet auf Netzlauf (F6) |
| 27 | Personen und Mandatstyp | `feat/27-personen` | – | wartet auf Netzlauf (F6) |
| 28 | Abstimmungen und Kooperation | `feat/28-abstimmungen` | – | wartet auf Netzlauf (F6) |
| 29 | Anwendungen für die Ratsarbeit | `feat/29-ratsarbeit` | – | wartet auf 14, 18, 20, 26 |

## Ausbau 2026-10 (abgeschlossen)

Meta-Plan: [../plan-ausbau-2026-10.md](../plan-ausbau-2026-10.md). Je Option ein Plan nach dessen § 8.3,
geschrieben vom jeweiligen Unteragenten auf seinem Branch; `00-synergien.md` schreibt der Supervisor;
`fragen.md` sammelt die Fragen an Konrad (§ 6).

| Nr. | Plan | Branch | Status |
|---|---|---|---|
| 00 | `00-synergien.md` | `main` | geschrieben 2026-10-12 |
| 01 | `01-staedte.md` | `feat/01-staedte` | gemerged 2026-10-12 |
| 02 | `02-zeitreihe.md` | `feat/02-zeitreihe` | gemerged 2026-10-12 |
| 03 | `03-kontrollvariablen.md` | `feat/03-kontrollvariablen` | gemerged 2026-10-12 |
| 04 | `04-parteien.md` | `feat/04-parteien` | gemerged 2026-10-12 |
| 05 | `05-gremien.md` | `feat/05-gremien` | gemerged 2026-10-12 |
| 06 | `06-gewichtung.md` | `feat/06-gewichtung` | gemerged 2026-10-12 |
| 07 | `07-monitoring.md` | `feat/07-monitoring` | gemerged 2026-10-12 |
| 08 | `08-suche.md` | `feat/08-suche` | gemerged 2026-10-12 |
