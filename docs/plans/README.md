# Pläne

## Vorverarbeitung 2026-11

Meta-Plan: [../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md). Je Vorhaben ein
Messdokument `NN-name.md` mit Messskript `NN-name-messung.py` (Stufe 1, Vorlage § 12.1), geschrieben vom
Mess-Agenten auf seinem Branch; `00-synergien-2026-11.md` schreibt der Supervisor; `fragen-2026-11.md`
sammelt die Fragen an Konrad. Stufen: 1 Messen, 2 Bauen, 3 Zeigen (§ 8). Diese Tabelle ist der Stand;
der Supervisor führt sie bei jedem Start, Urteil und Merge nach.

| Nr. | Vorhaben | Branch | Stufe | Stand |
|---|---|---|---|---|
| F1 | Rohtext | `fund/F1-rohtext` | Fundament | gebaut (7 Commits: Schritt `raw_texts`, Paket der Hauptperiode 17,0 MB, Methodensatz zum Extraktor, `docs/todo.md` Punkt 7 erledigt); Plättung gleich bis auf 9 PDFs mit `\f` im Seitentext; Review läuft |
| F2 | Register | `main` | Fundament | auf `main` seit 2026-11-23 (`v0.17.0`, Punkt 69) |
| F3 | Spannen | `main` | Fundament | auf `main` seit 2026-11-23 (`v0.17.0`, Punkt 69) |
| F4 | Validierung | `fund/F4-validierung` | Fundament | gebaut (9 Commits), auf `main` rebast, Review läuft; danach Erweiterung um mehrere Fragen je Einheit und Paare mit Fundstelle, die Codebücher von 13 und 14 werden übertragen |
| F5 | Modellnaht | `fund/F5-modelle` | Fundament | gebaut (9 Commits, Paket `georep.ml`, Schalter `--models`, Cache in SQLite); Review ohne Blocker, aber drei Befunde, die falsche Ergebnisse im Cache festhielten (Fenster des Einbetters, abgeschnittene Antworten, Teillauf gilt als aktuell); zweite Runde läuft ohne Modellserver. ollama ist auf Konrads Wunsch seit 2026-11-23 angehalten: keine Modelläufe bis zu seinem Signal |
| F6 | OParl: Sitzungen, Tagesordnung, Personen | `fund/F6-oparl` | Fundament | gebaut (6 Commits, Netzschritte `meetings`, `consultations`, `persons`, Runbook `docs/runbook-sitzungen.md`); Review fand vier wichtige Fehler in der Fortsetzbarkeit (Probe ersetzt volle Ausgabe, Fortsetzung verliert Löschungen, Abbruchregel der Sitzungen, gleichzeitige Läufe); zweite Runde läuft, offline. Konrads Netzlauf erst nach dem Merge. Der Server füllt `agendaItem.result` (96,5 % der Punkte mit Beratung), nie `resolutionText` |
| 11 | Struktur der Dokumente | `feat/11-struktur` | 1 → 2 | Kodierung bestätigt (§ 4.1): Beschlussvorschlag 188/200 = 0,94 streng, Kopffelder 0,95 bis 1,0, α ≥ 0,99; **Urteil bauen**, Stufe 2 wartet auf Haltepunkt A |
| 12 | Kennungen und Beträge | `feat/12-kennungen` | 1 | Messdokument auf `main` (2026-11-23): vorläufig bauen je Art, Rolle eines Betrags offen, Dezernate über eine Tabelle im Profil; Kodierung der 650 Aufgaben läuft |
| 13 | Dubletten und Dokumentfamilien | `feat/13-dubletten` | 1 | Messdokument auf `main` (2026-11-23): vorläufig verwerfen (bei τ = 0,9 nur 0,5 % der Dokumente in Familien, höchstens 1,4 % Trefferverlust je Wahlbezirk, Tabelle 5 ändert sich in der dritten Stelle); Kodierung der 200 Paare zurückgestellt, sie läuft nur auf freien Plätzen, weil sie allein zwischen verwerfen und einer Variante mit höchstens rund 5 % Wirkung entscheidet; MinHash geht an 23, Fortschreibungen an 14 |
| 14 | Vorgänge | `feat/14-vorgaenge` | 1 → 2 | **Urteil bauen, mit der Rückfallregel** (2026-11-23): stark nur Kanten aus Titel, Anlage, Nachtragsnummer, Sammelbericht; 104/106 = 0,981 (Wilson 0,934–0,995); 3 563 starke Kanten, 2 169 Vorgänge, 39,6 % der Anfragen mit Antwort; Stufe 2 wartet auf F6 (Anlagen) und Haltepunkt A, mit einer eigenen Stichprobe von rund 50 Rückfall-Kanten daneben (Frage 9.18) |
| 15 | Dokumentfunktion und gemeinsame Anträge | `feat/15-funktion` | 1 → 2 | **Urteil bauen, Variante B** (2026-11-23): κ 0,905 (A 0,829, Untergrenze 0,748), Fehler nur bei Anträgen; Urheber-Präzision 119/119, Recall 0,86; Restklasse heißt auf der Seite „Funktion nicht erkannt"; Stufe 2 wartet auf Haltepunkt A |
| 16 | Ortsbezug verfeinern | `feat/16-ortsbezug` | – | wartet auf 11 |
| 17 | Zeit und Neuigkeiten | `feat/17-zeit` | – | offen |
| 18 | Einbettungen, Ähnlichkeit, Suche | `feat/18-einbettungen` | – | wartet auf F5 |
| 19 | Politikfelder (CAP) | `feat/19-politikfelder` | – | wartet auf F5 |
| 20 | Kurzfassungen (lokal) | `feat/20-kurzfassungen` | – | wartet auf F5 |
| 21 | Geld auf der Karte | `feat/21-geld` | – | wartet auf 11, 12, 16 |
| 22 | Bedarf und Aufmerksamkeit | `feat/22-bedarf` | – | offen |
| 23 | Textübernahme | `feat/23-textuebernahme` | – | wartet auf 13, 18 |
| 24 | Anfragen als Kontrolle | `feat/24-kontrolle` | – | wartet auf 11, 12 |
| 25 | Wahlprogramme und Versprechen | `feat/25-versprechen` | – | Sammlung der Programme offen |
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
