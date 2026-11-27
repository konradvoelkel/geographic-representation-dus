# Vorhaben 14: Vorgänge

**Stand 2026-11-27: Urteil bauen mit der Rückfallregel (§ 5.1), Stufe 2 auf `main` (`v0.25.0`,
Punkt 76); Stufe 3 (`vorgaenge.html`, der Haken des Dokumentdialogs als Vorarbeit V2, die Downloads
`vorgang_kanten`, `dokumente_vorgang`, `antwortzeiten`) gebaut auf `feat/14-vorgaenge-seite`, wartet
auf Review und Merge (Entscheidungseintrag „Die Unterseite `vorgaenge.html` und der allgemeine
Dialog-Haken"). Die Seite trägt die Prüfstichprobe aus `guete.json` (50 von 50), nicht die 104/106;
gemessen heißt dort nur die Hauptperiode, `verweise.parquet` ist kein Download.** Der Branch ist gemerged und entfernt. Die Prüfstichprobe der Rückfallregel
(Frage 9.18) ist am 2026-11-27 vorab festgelegt und kodiert (§ 4.3): 50 von 50, Kriterium
erfüllt, zusammen mit § 5.1 154 von 156 (Wilson ab 0,954).

Stufe 1 (Messen) vom 2026-11-23 auf dem Branch `feat/14-vorgaenge`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „14 Vorgänge".
Messskript: [14-vorgaenge-messung.py](14-vorgaenge-messung.py) (`uv run python
docs/plans/14-vorgaenge-messung.py`, rechnet jede Zahl dieses Dokuments nach; `--stichprobe` schreibt
Stichprobe und Kodieraufgaben der Runde 1, `--stichprobe-2` die der Bestätigung). Codebuch und
Stichproben: `validierung/14-vorgaenge/`. **Endgültiges Urteil der Stufe 1 (§ 5): bauen, mit der
Rückfallregel** — stark sind nur Kanten aus Titel, Anlagenname, Nachtragsnummer und Sammelbericht;
an beiden kodierten Stichproben 104 von 106 richtig (0,981). Fassung .1 ergab 0,927 (§ 4.1), die
Regelfassung .2 an der Bestätigungsstichprobe 0,850 (§ 4.2); beide sind verworfen.

Die drei Zahlen, auf die es ankommt:

1. **14 870 Kanten** zwischen Drucksachen (Düsseldorf 14 483 über drei Perioden, Mönchengladbach 387),
   98,8 % davon zeigen auf ein älteres oder gleich altes Dokument, wie ein Verweis es soll; 2 599
   überqueren eine Periodengrenze.
2. **3 334 von 8 157 Anfragen (40,9 %)** haben eine Antwort im Ratsinformationssystem, die Hauptperiode
   33,2 % — fast alle als **Anlage „Antwort der Verwaltung" an der Anfrage selbst**, nicht als eigene
   Drucksache (nur 279). Das Kriterium „mindestens 30 %" ist erfüllt.
3. **Ob eine Antwort als Anlage kommt, ist Praxis des Gremiums, nicht Verhalten der Verwaltung gegenüber
   einer Fraktion**: in der Hauptperiode zwischen 0,2 % (Rat, 633 Anfragen) und 97 % (APS); gegen diese
   Praxis gerechnet liegen alle großen Fraktionen bei beobachtet/erwartet 0,93 bis 1,23. „Keine Antwort
   im Datensatz" heißt darum nicht „unbeantwortet". Antwortzeit, wo sie datiert ist: Median **20 Tage**
   (Q1 13, Q3 72, P90 133; n = 2 049).

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

**Frage.** Welche Drucksachen gehören zusammen (Anfrage und Antwort, Antrag und Umsetzung, Vorlage und
Änderungsantrag, Nachtrag, Bedarfs- und Ausführungsbeschluss)? Wie lange braucht eine Antwort, welche
Anfragen haben keine, was wurde aus einem Antrag?

**Ratsarbeit.** Wiedervorlage („ist die Anfrage vom März beantwortet?") und Recherche („gab es das
schon?", „was wurde aus dem Antrag?") sind die Wege, die `workflow-ratsmitglied.md`, § 4, heute ins
Ratsinformationssystem schickt: die Seite kennt keine Beratungsfolge je Dokument und keine Beschlusslage.
Ein Vorgang im Dokumentdialog verkürzt den Weg von einem Treffer zu seiner Vorgeschichte.

**Literatur.** Volden und Wiseman (2014)* messen „legislative effectiveness" als Weg eines Antrags durch
die Stufen; ein Vorgang ist die kommunale Entsprechung dieser Stufen, ohne Ergebnis (das bringt Vorhaben
26). Zu Anfragen als Kontrollinstrument Höhmann und Sieberer (2020); die Antwortzeit ist dort ein Maß der
Reaktion der Exekutive — hier zeigt § 3.7, dass die Daten das nur innerhalb eines Gremiums tragen.

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

Gerechnet auf den Läufen vom 2026-11-23 (`georep bootstrap && georep run` für alle vier Profile im
Worktree, 18:08 bis 18:16 Uhr). Pfade aus `georep --profile <p> paths`.

| Datensatz | Profil | Dokumente | mit Text | erstes – letztes Datum |
|---|---|---|---|---|
| 2014-2020 | `duesseldorf-2014` | 22 215 | 21 838 | 2014-05-26 – 2020-09-11 |
| 2020-2025 (Hauptperiode) | `duesseldorf` | 19 108 | 19 033 | 2020-09-14 – 2025-09-12 |
| 2025- (laufend) | `duesseldorf-2025` | 4 095 | 4 075 | 2025-09-15 – 2026-10-13 |
| Mönchengladbach | `moenchengladbach` | 2 895 | 650 | 2020-09-14 – 2025-09-13 |

Keine ID liegt in zwei Datensätzen. Gelesen werden je Profil:

- `interim/papers.parquet`: `id`, `name` (Titel), `reference` (Drucksachennummer), `date`, `paper_type`,
  `text` (kleingeschrieben, ohne Zeilenumbrüche).
- `processed/papers_gremien.parquet`: `id`, `gremium`, `gremium_art` (Punkte 23, 57, 58).
- `processed/dokumente_urheber.parquet`: `id`, `urheber_art`, `parteien` (Option 4, Punkte 59 bis 64).

**Neu für dieses Vorhaben: die OParl-Objekte im HTTP-Cache.** Konrads Netzläufe vom 2026-10-13 und
2026-10-14 haben 510 Seiten `…/papers` im requests-cache hinterlassen (`<cache_root>/http.sqlite`, 717
MB, nur lesend geöffnet): 51 200 Paper-Objekte, darunter **alle 48 313** Dokumente der vier Datensätze.
Diese Objekte tragen drei Angaben, die weder Korpus noch Paket haben:

- `auxiliaryFile[]` mit `name` und `date`: 19 290 Dokumente der Periode 2014-2020 haben Anlagen, 5 176 der
  Hauptperiode, 974 der laufenden, 1 929 in Mönchengladbach. Darin steht die **Antwort der Verwaltung**
  (§ 3.6).
- `consultation[]` mit `meeting`, `agendaItem`, `role`, `authoritative`: **jedes** Dokument aller vier
  Datensätze hat eine Beratung mit Sitzung (Sitzungsdatum und Ergebnis liegen in `meeting` und
  `agendaItem`, die erst F6 abruft).
- `subordinatedPaper`: 196 Paare, keins davon ein Nachtrag über die Nummer (§ 3.3; was sie bedeuten,
  ist offen, Frage 9.11).

Das Messskript zieht beim ersten Lauf einen Auszug nach
`/media/konrad/xtraspace/georep/messdaten/14-vorgaenge/oparl_papiere.parquet` (730 KB) und liest danach nur
ihn, damit ein Aufräumen des Caches die Messung nicht löscht. Als Paket gerechnet (`id`, Anlagenname,
Anlagendatum; zstd): **56 720 Anlagen in 519 KB**; Sitzungen und Rollen dazu 274 KB.

**Herkunft und Lizenz**: dieselben OParl-Metadaten des Ratsinformationssystems wie der Korpus. Ins Repo
und auf die Seite kommen nur IDs, Nummern, Kantentypen und abgeleitete Zahlen (Frage 6 des Meta-Plans);
die Texte der Antworten liegen nirgends lokal (die PDFs der Anlagen sind nicht abgerufen).

**Dokumentarten**, auf Rollen im Vorgang abgebildet (`art()` im Skript; Stufe 2: Tabelle im Profil):

| Rolle | 2014-2020 | 2020-2025 | 2025- | Mönchengladbach | Dokumentarten |
|---|---|---|---|---|---|
| `vorlage` | 9 583 | 5 507 | 1 192 | 1 260 | Beschlussvorlage, BV-Beschlussvorlage, Verwaltungsvorlage (alt), Beratungsvorlage, Änderungsvorlage (MG) |
| `antrag` | 3 203 | 5 101 | 932 | 617 | Antrag …, Haushaltsantrag …, zAntrag …, Fraktions-/Mitgliederantrag (MG); alt: „Vorlage aus der Politik" mit „antrag" im Titel |
| `anfrage` | 3 131 | 3 950 | 1 076 | 0 | Anfrage …, zAnfrage …; alt: „Vorlage aus der Politik" mit „anfrage" und ohne „antrag" im Titel (2 269) |
| `information` | 974 | 4 203 | 791 | 1 018 | (BV-)Informationsvorlage, Berichtsvorlage |
| `bedarf` / `af` | 19 / 46 | 78 / 145 | 9 / 32 | – | Bedarfsbeschluss / „A+F Beschluss" |
| `eingabe` | 20 | 124 | 63 | – | Eingabe nach § 24 GO |
| `politik` | 5 239 | – | – | – | „Vorlage aus der Politik" ohne „anfrage" und „antrag" im Titel |

**Korrektur einer Annahme des Briefings**: „A+F Beschluss" ist der **Ausführungs- und
Finanzierungsbeschluss** eines Bauvorhabens (Titel „… – Ausführungs- und Finanzierungsbeschluss –"), keine
Antwort auf eine Anfrage. Er folgt auf einen Bedarfsbeschluss und ist darum ein eigener Kantentyp (`bau`).
**Mönchengladbach hat keine Anfragen** im Datensatz (keine Dokumentart, ein einziger Titel mit „Anfrage");
Antwortzeiten gibt es dort nicht.

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

Alle Zahlen vom 2026-11-23, Lauf des Messskripts um 18:34 Uhr, **35,6 s** bei Lastmittel 41 → 28
(`uptime` davor und danach; frühere Läufe 52,6 s bei 70 → 39 und 73,1 s bei 38 → 40, die Zahlen gleich).
Einfädig bis auf Polars (vier Threads), `nice -n 10`.

### 3.1 Muster der Drucksachennummer je Stadt

| Stadt, Form | Muster der eigenen Nummer (`reference`) | trifft |
|---|---|---|
| Düsseldorf, heute | `^([A-ZÄÖÜ]+)(\d{1,2})?/(\d+)/(\d{4})(?:\s*[/-]+\s*(\d+))?$` | 19 108 / 19 108, 4 095 / 4 095, 4 197 / 22 215 |
| Düsseldorf, bis 2019 (Punkt 57) | `^(\d{2,3})/\s*(\d+)/(\d{4})(?:\s*[-/]\s*(\d+))?$` | die übrigen 18 018 / 22 215 |
| Mönchengladbach | `^(\d{3,4})(?:-(\d+))?/([IVX]+)(?:[-/](\d+))?$` (laufende Nummer / Wahlperiode römisch) | 2 895 / 2 895 |

Jede der 48 313 Nummern trifft genau ein Muster. Der **Schlüssel** ist die Nummer ohne führende Nullen und
Leerzeichen, der Nachtrag als `/k` (`OVA/117/2023/1`, `61/12/2014/1`, `0302/X/1`); 45 405 Schlüssel in
Düsseldorf, davon 13 mehrdeutig (zwei Dokumente, gleiche Normalform; Verweise darauf werden verworfen),
2 895 in Mönchengladbach, keiner mehrdeutig.

Im Text (kleingeschrieben) sucht das Skript dieselben Formen mit Spielraum für Leerzeichen um die
Schrägstriche. Drei Eigenheiten, gemessen an den bekannten Treffern:

- **Zusammengeklebte Wörter**: pypdf klebt Wörter aneinander („…zur vorlagebv6/002/2023"). Das Skript nimmt
  die ganze Buchstabenfolge vor der Zahl und kürzt sie auf das längste bekannte Kürzel am Ende (32 Kürzel,
  aus den Nummern gelernt). Das findet **169** Verweise im Text und 1 im Titel, die eine Wortgrenze
  verlöre. Ein Wort vor der alten Form („vorlage 61/ 12/2014") ist kein Kürzel: ohne diese Regel standen
  6 801 Scheintreffer „ORLAGE" unter den unbekannten.
- **Datumsform der alten Nummer**: „01/12/2014" könnte ein Datum sein. Unter den bekannten Treffern haben
  nur **10** diese Form (zwei Ziffern ≤ 31, zwei Ziffern ≤ 12, kein Leerzeichen); sie bleiben drin, der
  Kodierbogen fragt danach (`nummer_gemeint`).
- **Bebauungspläne in Mönchengladbach** heißen ähnlich („Nr. 437/V"). Kein bekannter Treffer steht in den
  50 Zeichen hinter „Bebauungsplan", „B-Plan" oder „Plan Nr."; die unbekannten mit anderer Periode (90)
  enthalten sie.

### 3.2 Verweise in Titel, Text und Anlagennamen

„Je Dokument" zählt jede Nummer einmal je Dokument und Feld; „bekannt" heißt: die Nummer gehört zu einer
Drucksache **irgendeiner** Periode derselben Stadt; „über Basis": nur die Grundnummer ohne Nachtrag ist
bekannt.

| Datensatz | Feld | je Dokument | selbst | bekannt | über Basis | unbekannt | Dokumente mit Verweis |
|---|---|---|---|---|---|---|---|
| 2014-2020 | Titel | 439 | 0 | 384 | 0 | 55 | 381 |
| | Text | 21 424 | 14 541 | 5 545 | 6 | 1 328 | 3 340 |
| | Anlage | 822 | 730 | 74 | 0 | 18 | 68 |
| 2020-2025 | Titel | 1 887 | 0 | 1 676 | 0 | 209 | 1 637 |
| | Text | 8 416 | 451 | 7 161 | 4 | 798 | 4 707 |
| | Anlage | 100 | 14 | 76 | 0 | 10 | 70 |
| 2025- | Titel | 332 | 0 | 294 | 0 | 38 | 281 |
| | Text | 1 632 | 53 | 1 440 | 2 | 137 | 934 |
| | Anlage | 27 | 6 | 17 | 0 | 4 | 12 |
| Mönchengladbach | Titel | 152 | 1 | 144 | 0 | 7 | 133 |
| | Text | 728 | 368 | 261 | 0 | 99 | 181 |
| | Anlage | 23 | 12 | 9 | 0 | 2 | 8 |

Gegen die Zahlen des Supervisors (Hauptperiode: 1 505 Titel mit 1 537 Verweisen, 3 630 Texte mit 5 144)
liegen diese höher, weil sie auch Nummern anderer Perioden, die alte Form und geklebte Kürzel als bekannt
zählen. In der Periode 2014-2020 nennt der Text die eigene Nummer oft im Kopf (14 541-mal); das ist kein
Verweis.

**Unbekannte Nummern** (gefunden, aber keine Drucksache des Datensatzes): 2014-2020: 716 vor 2014, 676 im
Zeitraum 2014 bis 2026, 9 unplausible Jahre; Hauptperiode 114 / 901 / 2; laufende 12 / 167 / 0;
Mönchengladbach 90 aus anderen Wahlperioden (IX: 71), 18 aus Periode X, die nicht im Datensatz liegen.
„Im Zeitraum, aber unbekannt" sind nicht öffentliche Drucksachen, Tippfehler oder Nummern, die anders
gemeint sind; Stufe 2 schreibt sie als Spannen ohne Ziel (F3), nicht als Kante.

### 3.3 Kanten

Eine Kante ist ein Paar (B nennt A), B ≠ A, einmal je Paar, mit den Feldern, in denen der Verweis steht.
Dazu kommen **337 Nachtragskanten über die Nummer** (`X/1` → `X`), auch wo B die Nummer von A nicht
nennt.

- **14 870 Kanten**: Düsseldorf 14 483, Mönchengladbach 387. Felder: nur Text 11 877, Text und Titel 2 338,
  nur Nummer (Nachtrag) 266, nur Titel 153, Anlage und Text 132, Nummer und Text 60, nur Anlage 26,
  übrige 18.
- **Richtung**: 182 Kanten (1,2 %) zeigen von einem älteren auf ein jüngeres Dokument, 131 liegen am selben
  Tag. Ein Verweis nach vorn ist möglich (Vorlage nennt die Nummer ihres angekündigten Nachtrags, Datum
  nachträglich geändert), aber selten; die Richtung ist ein deterministischer Plausibilitätstest.
- **Über Periodengrenzen**: 2020-2025 → 2014-2020: 1 675; 2025- → 2020-2025: 791; 2025- → 2014-2020: 133;
  zusammen **2 599** (17,9 % der Düsseldorfer Kanten). Innerhalb: 5 704, 5 635, 545. Ein Vorgang endet
  also nicht an der Wahl; Stufe 2 braucht die Nummern der Nachbarperioden (Frage 9.2).

### 3.4 Typisierte Paare

Typ aus den Rollen der beiden Dokumente (`kantentyp()` im Skript; B ist die nennende, spätere):

| Typ | Regel (B → A) | Düsseldorf | rückwärts | Median Tage | gleiches Gremium | Mönchengladbach |
|---|---|---|---|---|---|---|
| `antwort` | Information → Anfrage | 301 | 2 | 120 | 96,7 % | – |
| `nachfrage` | Anfrage → Anfrage | 373 | 2 | 266 | 75,3 % | – |
| `umsetzung` | Information oder Vorlage → Antrag | 3 308 | 22 | 144 | 81,5 % | 52 |
| `aenderung` | Antrag → Vorlage, Bedarf oder A+F | 758 | 7 | 70 | 42,3 % | 73 |
| `nachtrag` | gleiche Nummer mit Zusatz | 317 | 9 | 49 | 99,6 % | 20 |
| `bau` | A+F → Bedarfsbeschluss | 37 | 0 | 666 | 97,2 % | – |
| `bezug` | alles andere | 9 389 | 128 | 257 | 78,7 % | 242 |

„Gleiches Gremium" ist ein Etikett aus den Daten (Punkt 58), kein Prüfmaß: Änderungsanträge zu
Ausschussvorlagen laufen im Rat (`RAT/359/2026` zur Vorlage `AUS/008/2026`), darum die 42 %.

Wie oft ein Dokument einen Nachfolger dieses Typs hat (nur Kanten, die nicht rückwärts zeigen):

| | 2014-2020 | 2020-2025 | 2025- | Mönchengladbach |
|---|---|---|---|---|
| Anträge mit Vorlage oder Mitteilung, die sie nennt | 846 / 3 203 (26,4 %) | 1 490 / 5 101 (29,2 %) | 171 / 932 (18,3 %) | 41 / 617 (6,6 %) |
| Vorlagen mit Antrag, der sie nennt | 220 / 9 583 (2,3 %) | 209 / 5 507 (3,8 %) | 33 / 1 192 (2,8 %) | 55 / 1 260 (4,4 %) |
| Anfragen mit Informationsvorlage, die sie nennt | 43 / 3 131 (1,4 %) | 212 / 3 950 (5,4 %) | 24 / 1 076 (2,2 %) | – |
| Anfragen mit späterer Anfrage dazu | 90 (2,9 %) | 199 (5,0 %) | 32 (3,0 %) | – |
| Bedarfsbeschlüsse mit A+F-Beschluss | 8 / 19 | 22 / 78 | 0 / 9 | – |

Mönchengladbach hat nur 650 Texte; dort trägt fast alles der Titel („Zu Vorlage 0265/X", „Änderungsantrag
zu Beratungsvorlage 0688/X").

### 3.5 Verweisgraph, Komponenten, Vorgänge

| Definition (Düsseldorf, 45 418 Dokumente) | in einem Vorgang ≥ 2 | Vorgänge | größte drei |
|---|---|---|---|
| Zusammenhangskomponenten über **alle** Kanten | 15 923 (35,1 %) | 4 085 | 4 619, 54, 50 |
| … ohne Kanten in die 75 Dokumente mit > 10 Zitaten (1 309 Kanten) | — | — | 2 776 |
| Komponenten nur über **typisierte** Kanten (5 094) | 7 556 (16,6 %) | 2 720 | 701, 46, 44 |
| … ohne Kanten in Dokumente mit > 5 typisierten Zitaten (429) | — | — | 330, 43, 36 |
| **Baum**: jedes Dokument hängt am ältesten Dokument, das es typisiert nennt | **6 887 (15,2 %)** | **2 911** | **36, 32, 26** |

Größenverteilung des Baums: 2 Dokumente 2 407 Vorgänge, 3: 333, 4–5: 116, 6–10: 38, 11–50: 17, darüber
keiner. Mönchengladbach (2 895): alle Kanten 536 Dokumente (18,5 %) in 171 Komponenten, größte 36; als
Baum 236 Dokumente (8,2 %) in 102 Vorgängen, größter 5.

**Die Zusammenhangskomponente ist kein Vorgang.** Über alle Kanten hängen 29 % der verbundenen
Dokumente in einer einzigen Komponente von 4 619, weil Grundsatzbeschlüsse viele Folgen sammeln (meistzitiert:
`OVA/11/2020` 50-mal, `OVA/49/2020` 44, `RAT/111/2021` 41, `OVA/118/2021` 39, `RAT/367/2022` 37,
`61/8/2018` 32; Schlüssel in Normalform) und zwei Vorgänge verschmelzen, sobald ein drittes Dokument
beide nennt. Selbst über typisierte Kanten und ohne Knoten mit vielen Zitaten bleibt eine von 330. Der
**Baum** verschmilzt nichts: jede Antwort, Umsetzung, Änderung gehört zu genau einem Vorgänger. Beispiel
(typisierte Komponente mit fünf Dokumenten): Bedarfsbeschluss `KUA/151/2020` (2020-10-30) ← A+F-Beschlüsse
`KUA/47/2024` und `KUA/129/2024`; Bedarfsbeschluss `KUA/45/2025` ← A+F-Beschluss `KUA/63/2026`, der auch
`KUA/151/2020` nennt — als Baum zwei Vorgänge, als Komponente einer.

### 3.6 Anfragen und Antworten (Düsseldorf)

**Wo die Antwort steht.** Anfragen tragen in ihrem Text nur die Frage (Stichprobe von vier Texten, und
nur 19 von 3 950 Titeln von Anfragen der Hauptperiode nennen „Antwort" oder „Beantwortung", meist als
Nachfrage). Die Antwort kommt auf
zwei Wegen ins System:

1. **als Anlage an der Anfrage** (`auxiliaryFile`), erkannt am Namen mit dem Muster
   `(^|[^a-zäöü])(be)?antwort|verwaltungsantwort|anrwort|stellungnahme (der |des )?(verwaltung|dezernat|amt)`.
   Häufigste Namen an Anfragen: „Antwort der Verwaltung" 1 293, „Beantwortung" 156, „Antworten der
   Verwaltung zu NN/ NN/NNNN" 88, „Antwort" 80, „AGS NNN NNNN Antwort der Verwaltung" 78, „Beantwortung
   der Anfrage" 68, „Beantwortung zur Vorlage BVN_NNN_NNNN" 47, „Verwaltungsantwort" 31, „Antwort
   Dezernat" 24. Nicht als Antwort: „Vorlage" 2 277 (die Frage selbst, alte Periode), „Anlage N zur
   Drucksache …", „Fotos". „Stellungnahme" allein ist zu breit (IHK, ver.di, Abwägung nach BauGB: 663
   Anlagen über alle Dokumentarten), darum nur die der Verwaltung; das kostet unter den Anfragen 2
   Treffer. Fünf Zwischennachrichten zählen nicht als Antwort.
2. **als eigene Drucksache**, eine Informationsvorlage, die die Anfrage nennt (Typ `antwort`, § 3.4).

| Datensatz | Anfragen | Anlage | beide | nur eigene Drucksache | keine | mit Antwort |
|---|---|---|---|---|---|---|
| 2014-2020 | 3 131 | 1 715 | 33 | 10 | 1 373 | **1 758 (56,1 %)** |
| 2020-2025 | 3 950 | 1 101 | 119 | 93 | 2 637 | **1 313 (33,2 %)** |
| 2025- | 1 076 | 239 | 3 | 21 | 813 | **263 (24,4 %)** |
| zusammen | 8 157 | 3 055 | 155 | 124 | 4 823 | **3 334 (40,9 %)** |

Untergrenze für 2014-2020: von den 5 239 „Vorlagen aus der Politik" ohne „Anfrage" und „Antrag" im Titel
tragen 1 017 (19,4 %) eine Antwortanlage — vermutlich weitere Anfragen, die das Titelkriterium nicht als
solche erkennt (Frage 9.6).

**Das Datum der Anlage ist ab Juli 2019 ein Antwortdatum, davor nicht.** 28 451 Anlagen Düsseldorfer
Drucksachen im Cache tragen das Datum **2019-07-03**, darunter 26 542 der 48 024 Anlagen der drei
Datensätze (55,3 %, Drucksachen vom 2014-05-26 bis 2020-02-13); von den Anlagen der Drucksachen vor Juni
2019 tragen alle bis auf eine ein Datum aus 2019 — die Umstellung des Ratsinformationssystems. Antworten
mit diesem Datum zählen als vorhanden, aber ohne Antwortzeit; gültig datiert sind 2 049 der 3 334 (61,5 %).

### 3.7 Antwortzeiten

Tage von der Anfrage (`date`) bis zur frühesten datierten Antwort; eine Antwort lag vor ihrer Anfrage
(gezählt, nicht verwendet).

| | n | Median | Q1 | Q3 | P90 |
|---|---|---|---|---|---|
| alle gültig datierten | 2 049 | **20** | 13 | 72 | 133 (P95 215) |
| nur Anlage | 1 916 | 17 | 13 | 66 | 115 |
| nur eigene Drucksache | 279 | 119 | 63 | 210 | 391 |

Hauptperiode und laufende Periode zusammen (5 026 Anfragen), je Gremienart:

| Gremienart | Anfragen | mit Antwort | Anteil | Median Tage | Q3 |
|---|---|---|---|---|---|
| Bezirksvertretung | 2 745 | 1 304 | 47,5 % | 26,5 | 78 |
| Ausschuss | 1 289 | 213 | 16,5 % | 13 | 19 |
| Rat | 855 | 1 | 0,1 % | (240) | – |
| Beirat | 137 | 58 | 42,3 % | 19 | 41 |

Je Gremium (die 16 mit den meisten Anfragen): RAT 855 / 0,1 %; BV5 434 / 73,5 % / Median 62; BV10 339 /
11,8 % / 16; BV2 324 / 86,4 % / 18; BV8 304 / 43,1 % / 14; BV4 304 / 2,6 % / 24; BV1 246 / 34,6 % / 34; BV9
230 / 57,4 % / 17; BV7 218 / 92,7 % / 26,5; OVA 179 / 2,8 %; BV3 176 / 1,1 %; BV6 170 / 61,8 % / 56; AGS 143 /
54,5 % / 12; SCHUA 136 / 1,5 %; AWM 127 / 0 %; KUA 100 / 50 % / 16.

Je Urheber, Hauptperiode und laufende Periode (Partei aus `parteien`, sonst Urheberklasse; eine
gemeinsame Anfrage zählt je Partei), roh — Anfragen / Anteil mit Antwort / Median Tage:
SPD 1 167 / 25,3 % / Median 15; Grüne 989 / 39,6 % / 17,5; CDU 746 / 46,4 % / 14; Einzelpersonen 659 /
45,1 % / 22; Linke 453 / 17,7 % / 13; FDP 420 / 45,5 % / 41; Tierschutz/Freie Wähler 398 / 4,3 % / 27; AfD
292 / 7,5 % / 20; unbekannt 183 / 37,2 %; Volt 151 / 6,6 %; Die PARTEI 97 / 3,1 %.

Je Jahr der Anfrage (alle drei Perioden): 2014 1,0 %, 2015 32,3 %, 2016 61,3 %, 2017 70,1 %, 2018 80,2 %,
2019 63,3 %, 2020 51,6 %, 2021 39,5 %, 2022 33,3 %, 2023 33,7 %, 2024 27,6 %, 2025 29,5 %, 2026 23,3 %;
Median der Antwortzeit ab 2019: 26, 22, 34, 43, 18, 15, 15, 14 Tage.

### 3.8 „Keine Antwort im Datensatz" ist nicht „unbeantwortet"

Gemessen, wie man das trennt — und dass die Daten es nicht ganz können:

- **Die Sitzung trennt nicht.** 100 % der Anfragen ohne Antwort und 100 % der mit Antwort haben eine
  Beratung mit Sitzung; Rollen: „-" 7 069, Kenntnisnahme 3 841, Entscheidung 414, Vorberatung 10, Anhörung 4.
  Jede Anfrage stand also auf einer Tagesordnung. Ob sie dort mündlich beantwortet wurde, steht im
  Ergebnis des Tagesordnungspunkts oder in der Niederschrift — F6 und Vorhaben 26.
- **Die Praxis des Gremiums entscheidet.** Hauptperiode, 27 Gremien mit mindestens 30 Anfragen: Anteil mit
  Antwort von 0,0 (AWM 99, AÖE 69) über 0,002 (RAT 633), 0,009 (SCHUA), 0,015 (BV3), 0,027 (OVA), 0,032
  (BV4) bis 0,85 (BV2), 0,934 (BV7), 0,971 (APS); 15 Gremien unter 0,2, 7 über 0,7. Im Rat wird in der
  Sitzung geantwortet, in BV7 schriftlich als Anlage — das sagt nichts über die Verwaltung gegenüber den
  Fragenden.
- **Gegen diese Praxis gerechnet verschwinden die Unterschiede der Fraktionen** (Hauptperiode, indirekte
  Standardisierung: erwartet = Summe der Gremienanteile über die Anfragen einer Partei):

  | Urheber | Anfragen | roh | beobachtet / erwartet |
  |---|---|---|---|
  | SPD | 932 | 28,6 % | 0,93 |
  | Grüne | 816 | 40,1 % | 1,02 |
  | CDU | 641 | 44,5 % | 1,01 |
  | Einzelpersonen | 520 | 42,5 % | 1,01 |
  | FDP | 368 | 48,4 % | 1,06 |
  | Linke | 335 | 18,2 % | 1,08 |
  | Tierschutz/Freie Wähler | 306 | 5,2 % | 1,13 |
  | AfD | 129 | 2,3 % | 1,23 |
  | Die PARTEI | 97 | 3,1 % | 0,57 |

  Die AfD fragt zu 102 von 129 im Rat; ihre 2,3 % sind die 0,2 % des Rates, nicht eine Behandlung der
  Fraktion. Eine rohe Antwortquote je Fraktion auf der Seite wäre eine falsche Aussage.
- **Die Praxis wechselt mit der Periode.** Laufende Periode gegen Hauptperiode: AGS 0,0 (33 Anfragen) statt
  0,709, BV5 0,26 (50) statt 0,797, BV6 0,105 (38) statt 0,765; stabil BV2 0,889, BV7 0,889, BR 0,917.
  Wer „offen" anzeigt, muss die Praxis je Gremium **und** Periode kennen.
- **Zu jung**: 350 Anfragen ohne Antwort waren beim Abruf höchstens P90 = 133 Tage alt.
- **Kandidaten für „wirklich offen"**: ohne Antwort, älter als P90, in einem Gremium mit Praxis ≥ 0,7 in
  der Hauptperiode (AGS, APS, BR, BV2, BV5, BV6, BV7): Hauptperiode 188, laufende 72. Die ältesten der
  Hauptperiode: `AGS/072/2020` (2020-11-06, FDP), `BV2/181/2020` (FDP), `BV6/003/2021` (Einzelperson),
  `BV7/029/2021` (CDU), `BV2/016/2021` (Grüne), `BR/001/2021`, `BR/006/2021`, `BV2/056/2021`,
  `BV2/057/2021` (Grüne), `BV2/059/2021`, `BV2/074/2021`, `BV2/075/2021` (CDU); der laufenden:
  `BV5/143/2025` (2025-09-17, FDP, 391 Tage beim Abruf), `BV5/150/2025`, `BV5/153/2025`, `BV5/154/2025`,
  `BV5/155/2025`, `BV5/160/2025`, `BV5/161/2025`, `BV5/162/2025`, `BV5/164/2025`, `BV7/151/2025`. Die BV5-Liste
  ist zugleich der Praxiswechsel oben — „Kandidat" ist das ehrliche Wort, bis die Niederschriften (F6, 26)
  es entscheiden.

### 3.9 Umbau nach der Kodierung (Runde 2, 2026-11-23)

Die Kodierung (§ 4.1) ergab 139 / 150 = 0,927, das Kriterium verlangt 0,95: eine Runde Umbauen nach
§ 8 des Meta-Plans. Diese Runde erklärt die elf Fehler, schärft Regeln und Codebuch zur **Fassung .2**,
schätzt die neue Regel an den alten Labels — **als Entwurf, nicht als Messung**: die Regeln sind an
denselben 150 Kanten entworfen, an denen sie hier gut aussehen — und zieht eine frische
**Bestätigungsstichprobe** von 100 Kanten. Messskript, Abschnitte 11 und 12; letzter Lauf um
19:16 Uhr, 61,8 s bei Lastmittel 23 → 19 (`uptime`; ein Lauf um 19:12 Uhr brauchte 113 s bei 34 → 29,
mit denselben Zahlen).

**Die elf falschen Kanten.** Alle elf stehen nur im Text, keine im Titel; neun von elf hängen an einer
Stelle, an der B frühere Drucksachen *aufzählt* oder *belegt*, nicht behandelt.

| Kante | Schicht, Typ .1 | A (genannt) ← B (nennend) | Ursache | Regel .2, die sie verhindert |
|---|---|---|---|---|
| `181e4fc42bb2` | Umsetzung | KUA/171/2023 Antrag Aufwandsentschädigung Beiräte ← KUA/069/2024 Berufung neuer Beiratsmitglieder | Beschlusslage im Kopf einer Vorlage, nächste Nummer 90 Zeichen entfernt | R1 Aufzählung |
| `789e32e45dfd` | Umsetzung | RAT/039/2022 Antrag Wärmewende ← BAU/018/2023 Kolumbarium | Beschlusslage, Grundsatzbeschluss in einer Liste (115 Zeichen) | R1 Aufzählung |
| `c707f89125b1` | Umsetzung | RAT/367/2022 Masterplan Gasbeleuchtung ← BV4/098/2022 Bayerstraße | Rahmenzitat eines Grundsatzbeschlusses (37-mal zitiert) im Textbaustein; nächste Nummer 146 Zeichen | R1 Aufzählung (knapp unter 150); Codebuch .2, Grenzfall Rahmenbeschluss |
| `f6edd40eb21f` | Umsetzung | RAT/341/2023 LED-Umstellung ← OVA/034/2024 Abbiegeunfälle | Randnennung zweier Programme („RAT/341/2023 und OVA/179/2023") | R1 Aufzählung |
| `017519188ef7` | Mönchengladbach, Bezug | 0844/X Klassifizierte Straßen ← 1405/X Lärmaktionsplan | Vorgeschichte, Klammer mit zwei Vorlagen | R1 Aufzählung |
| `3ce35d466ae7` | Mönchengladbach, Bezug | 2487/X Sachstandsbericht Klimaschutz ← 3618/X Energiekonzept | Liste von sechs Vorlagen | R1 Aufzählung |
| `de552350d2a7` | Mönchengladbach, Umsetzung | 2163/X E-Scooter ← 3556/X E-Ladeinfrastruktur | Ausblick mit „vgl. Vorlage Nr." | R2 Verweiszeichen |
| `28b1b1a7c8e7` | Änderung | 001/ 40/2015 - 1 Stadtmarketing ← 01/ 283/2015 Änderungsantrag Tour de France | Typregel: ein Änderungsantrag zu *einer anderen* Vorlage nennt A nur mit „s." | R2 Verweiszeichen; Typ .2 verlangt das Änderungszeichen an der Fundstelle |
| `3c7dc42ebf60` | Nachfrage | OVA/126/2023 Verkehrszählungen Luegallee ← OVA/039/2024 KI im Verkehrswesen | Beleg in Fußnote und Quellenliste („[1.", „Quellen: (1)") | R2 Verweiszeichen |
| `11ed57a4aa2d` | Änderung | JHA/082/2022 Terminplan JHA ← RAT/527/2022 Haushaltsantrag | **Zitierfehler in B**: die Nummer existiert, B meint den Erinnerungsort Alter Schlachthof | keine; Codebuch .2 nennt den Fall (`nummer_gemeint = nein`) |
| `25b8500b0bd4` | Bezug, Text | BV3/147/2023 Unterhaltung, Haushalt 2023 ← BV3/160/2023 Fußgängerüberweg | A nur als **Finanzierungsquelle** | keine; Codebuch .2 nennt den Fall |

Das Nummernmuster ist an keinem Fehler schuld, auch in Mönchengladbach nicht (dort sind es zwei
Aufzählungen und ein „vgl."); die Muster je Stadt bleiben, wie § 3.1 sie beschreibt.

**Regelfassung .2** (Konstanten und `kantentyp2` im Messskript; Stufe 2: Profil und Defaults):

- **R1 Aufzählung.** Ein Textverweis in einer Verwaltungsvorlage (Rolle `vorlage` oder
  `information`) ist *schwach*, wenn die nächste Nummer mit anderer Grundnummer höchstens 150 Zeichen
  entfernt steht: Beschlusslage, Vorgeschichte, Klammer mit mehreren Vorlagen. Nicht in Anfragen und
  Anträgen — dort nennt eine Nachfrage die Anfrage und ihre Antwort nebeneinander, und die Regel auf
  allen Arten verwirft im Entwurf 15 statt 6 richtige Kanten (unten).
- **R2 Verweiszeichen.** Schwach ist auch ein Textverweis, wenn in den 30 Zeichen davor „vgl.",
  „siehe", „s.", „z. B.", eine Fußnote („[1.", „(1)") oder „Quelle(n):" steht.
- **R3 Sammelbericht.** Eine Verwaltungsvorlage mit „Beschlusskontrolle", „Veränderungsverzeichnis",
  „Ergebnis der Haushaltsberatungen", „Stand der Umsetzung", „Umsetzungsstand" oder „Erledigung" im
  Titel hält ihre Verweise trotz R1, als eigener Typ **`kontrolle`** (Codebuch .2: eine eigene Zeile mit
  Sachstand zu A ist `umsetzung`).
- **Stark** ist eine Kante, wenn eine ihrer Fundstellen stark ist: jede im Titel und in Anlagennamen,
  jeder Nachtrag über die Nummer, jede Textstelle ohne R1 und R2, und jede aus einem Sammelbericht.
  **Schwache Kanten bleiben in den Daten** (mit Grund `aufzaehlung` oder `verweiszeichen`), zählen aber
  nicht für Vorgänge, Antworten und Anzeige.
- **Typen .2**: `antwort` (Information → Anfrage, vor `kontrolle`); `kontrolle` (R3); `nachfrage` (jede
  Anfrage B, gleich was A ist — die Frage nach dem Stand eines Antrags ist eine Nachfrage, Codebuch .2);
  `umsetzung` (Information oder Vorlage → Antrag, alte Politik-Vorlage oder Eingabe); `aenderung` (Antrag →
  Vorlage, Bedarf, A+F oder Antrag, **nur mit Änderungszeichen**: „Änderungs-", „Ergänzungsantrag",
  „zur Vorlage", „zu TOP" im Titel von B, wenn A dort steht, oder bis 120 Zeichen vor der Fundstelle;
  sonst `bezug`); `fortsetzung` (Antrag → Anfrage oder Information, Information → Information);
  `bau`, `nachtrag` wie bisher; Rest `bezug`. Für die Art schlägt der Titel die Dokumentart, wo beide
  sich widersprechen („Antrag der Ratsfraktionen …" als „Anfrage Bündnis 90/Die Grünen": 8 Dokumente,
  umgekehrt 19).
- **Fortschreibungen (Befund aus Vorhaben 13)**: der Nachtrag über die Nummer bleibt immer stark. In der
  Hauptperiode sind es 130 Paare, 129 davon mit Text auf beiden Seiten; Vorhaben 13 zählt in seinem
  Textkorpus 128 mit Grundnummer — dieselbe Regel, und die Schicht `nachtrag` war 10 / 10 richtig.

**Wirkung auf alle 14 870 Kanten**: 12 744 stark, 1 707 schwach durch Aufzählung, 419 durch
Verweiszeichen (von 17 596 Textfundstellen stehen 2 796 in einer Aufzählung, 589 hinter einem
Verweiszeichen). Starke Kanten je Typ, Düsseldorf: `bezug` 4 570 von 5 773, `umsetzung` 3 724 von 4 297,
`nachfrage` 1 322 von 1 387, `fortsetzung` 851 von 1 043, `aenderung` 766, `kontrolle` 563, `nachtrag`
317, `antwort` 279 von 300, `bau` 37; Mönchengladbach 315 von 387. Typwechsel unter den starken: `bezug`
→ `umsetzung` 981, → `nachfrage` 971, → `fortsetzung` 900, → `kontrolle` 369, → `aenderung` 347;
`aenderung` → `bezug` 333 (kein Änderungszeichen); `umsetzung` → `kontrolle` 197.
**Vorgänge .2** (Baum über 7 296 starke typisierte Kanten, Düsseldorf): 4 015 Vorgänge mit 9 623
Dokumenten (21,2 %), größter 28 (statt 2 911, 6 887, 36). **Anfragen .2** (Art aus Titel und
Dokumentart): 8 168, mit Antwort 3 330 (40,8 %) — das Kriterium „30 %" bleibt erfüllt.

**Entwurfsschätzung an den alten 150 Labels — keine Messung.** Stark blieben 135 Kanten, davon 133
richtig: **0,985** (Wilson 0,948 bis 0,996); mit den starken Kanten je alter Schicht gewichtet
**0,956**. Verworfen wurden 9 der 11 falschen und **6 richtige** (`1fbaa119f89e` Mönchengladbach und
`c36914cb1844` periodenübergreifend durch „vgl.", `baeca9bead34`, `29a126522c2a`, `ae25bd7109bb`,
`21bb34390355` durch Aufzählung); sie bleiben als schwache Kanten in den Daten. Je alter Schicht stark /
davon richtig: Änderung 19 / 18, Antwort 25 / 25, Bau 5 / 5, Bezug Text 11 / 10, Bezug Titel 12 / 12,
Mönchengladbach 11 / 11, Nachfrage 14 / 14, Nachtrag 10 / 10, periodenübergreifend 7 / 7, Umsetzung
21 / 21. Rollen nach Typ .2 gegen die alten Rollenlabels (Codebuch .1, das die erweiterten Rollen nicht
kannte): Änderung 25 / 26, Antwort 23 / 25, Nachfrage 13 / 16 (die drei sind Anfragen nach dem Stand
eines Antrags, unter .1 als `bezug` kodiert), alle übrigen voll. Wer die Zahl 0,985 liest, liest eine
Obergrenze: der Entwurf kennt seine Fehler.

Verworfene Varianten, an denselben Labels:

| Variante | stark | richtig | falsch | richtige verworfen |
|---|---|---|---|---|
| **Fassung .2 (R1 in Verwaltungsvorlagen, R2, R3)** | **135** | **133** | **2** | **6** |
| R1 in allen Arten, R2, R3 | 126 | 124 | 2 | 15 |
| .2 und Titelabgleich ≥ 1 (Inhaltswort des Titels von A im Fenster ±300 oder im Titel von B) | 131 | 129 | 2 | 10 |
| .2 und Titelabgleich ≥ 2 | 125 | 124 | 1 | 15 |
| nur Titelabgleich ≥ 1 | 142 | 135 | 7 | 4 |

Der Titelabgleich ≥ 2 fände den Zitierfehler, kostet aber neun weitere richtige Kanten; ein Filter auf
Grundsatzbeschlüsse mit vielen Zitaten ist nicht nötig, weil der einzige unter den Fehlern
(`c707f89125b1`) schon unter R1 fällt. Für die Finanzierungsquelle gäbe es ein Zeichen
(„finanziert über", „Haushaltsposition") — aus einem Fall eine Regel zu machen, wäre an die Stichprobe
angepasst (Frage 9.14).

**Vorschläge der Kodierer und des Schlichters, je mit Entscheidung** (Rückmeldungen und
`schlichtung.jsonl` unter `messdaten/kodierung/14-vorgaenge/`; Codebuch `validierung/14-vorgaenge/codebuch.toml`,
Fassung 2026-11-23.2, `meta.aenderungen` nummeriert die Änderungen):

| Quelle | Vorschlag | Entscheidung |
|---|---|---|
| Schlichter `043e40c3a2c6` | Sammelantrag mit vielen Punkten; Typ aus Dokumentart oder Text? | übernommen: Rolle nach Inhalt, Titel schlägt Dokumentart (Codebuch 7, 8; `art2`) |
| Schlichter `0777b126e87f` | Anfrage zur Machbarkeit, dann Antrag auf die Maßnahme = Fortsetzung? | übernommen: `fortsetzung` (Codebuch 5), Typregel Antrag → Anfrage |
| Schlichter `39e9299db921`, `75503c0e17e9`; Kodierer A, Lücke 2; Kodierer B, Unscharf 1 | Beschlusskontrolle mit Sachstandszeile: ja/umsetzung oder Liste? | übernommen in der Fassung des Schlichters: eigene Zeile zu A = ja/umsetzung, bloße Aufzählung = nein (Codebuch 1; R3); Bs „nein" für die beiden Beschlusskontrollen verworfen, weil die Zeile einen Sachstand zu genau A führt |
| Schlichter `3b5c27d38a54`; Kodierer B | späterer Beschluss, der Mittel aus A umwidmet = Änderung? | übernommen (Codebuch 6); das Verfahren erkennt es nicht, die Kante bleibt `bezug` |
| Schlichter `65c7b673e01f`; Kodierer B | Reihenfolge-Regel, wenn B eine Rolle in der Begründung und eine im Beschlussteil erfüllt | verworfen: „die erste der Liste" bleibt und gilt ausdrücklich auch dann; eine Regel nach dem Teil von B verlangte, was der Ausschnitt meist nicht zeigt |
| Schlichter `ae25bd7109bb`; Kodierer A | abschließende Antwort nach Zwischennachricht = Änderung | übernommen (Codebuch 6) |
| Schlichter `c707f89125b1`; Kodierer A, Lücke 3; Kodierer B, Unscharf 3 | Körnung: Rahmenbeschluss gegen Einzelbeschluss desselben Programms | übernommen: ausgeführt = ja, nur als Rahmen zitiert = nein (Codebuch 2) |
| Kodierer A, Lücke 1; Kodierer B, Unscharf 2 | eigene Rolle „Rückfrage zur Umsetzung" für Anfragen zu einem Antrag | als Rolle verworfen, als Erweiterung von `nachfrage` übernommen (Codebuch 4): weniger Optionen halten α, die Art von A trennt die Fälle ohnehin |
| Kodierer A | „erste der Liste" gibt `umsetzung` vor `fortsetzung` | beibehalten: beide Kodierer wendeten die Regel gleich an |
| Kodierer A | Antworten auf Zusatzfragen = Antwort | übernommen (Definition `antwort`) |
| Vorhaben 13 | die Nummer findet alle 128 Fortschreibungen | übernommen: Nachtrag über die Nummer bleibt immer stark (130 Paare in der Hauptperiode) |
| Vorhaben 13 | Verteilervorlagen über gleichen Titel als Kantenart | zurückgestellt: hier nicht gemessen, und gleiche Titel sind oft Formeltitel („Stellungnahmen und Mitteilungen der Verwaltung"); Frage 9.13 |
| (eigener) | Zitierfehler in B | ins Codebuch (9): `nummer_gemeint = nein`, wenn B unter der Nummer erkennbar anderes beschreibt |

**Bestätigungsstichprobe** `validierung/14-vorgaenge/stichprobe-2.csv` (Spalten wie
`stichprobe.csv`, `typ` ist der Typ .2): 100 starke Kanten der Fassung .2, Seed `14-2`, **ohne die 150
alten**, Schichten in Vorrangfolge:

| Schicht | starke Kanten in der Schicht | gezogen |
|---|---|---|
| Mönchengladbach | 304 | 12 |
| periodenübergreifend | 2 086 | 8 |
| antwort | 227 | 8 |
| nachfrage | 948 | 10 |
| umsetzung | 3 371 | 18 |
| aenderung | 723 | 10 |
| kontrolle | 548 | 6 |
| fortsetzung (mit `bau`) | 702 | 6 |
| nachtrag | 291 | 3 |
| bezug, mit Titel | 148 | 5 |
| bezug, nur Text oder Anlage | 3 261 | 14 |

Mehr Gewicht als in Runde 1 auf die schwachen Schichten (Umsetzung, Mönchengladbach) und auf `bezug` im
Text, die größte Schicht. Kodieraufgaben nach Codebuch .2 (gleiches Format, ohne Kantentyp; die
Fundstelle ist die erste *starke* Fundstelle):
`/media/konrad/xtraspace/georep/messdaten/kodierung/14-vorgaenge/aufgaben-2.jsonl`, 100 Zeilen, 883 KB;
3 ohne Fundstelle (Nachtrag), 68 im Text, 29 im Titel.

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

Dieser Abschnitt beschreibt Runde 1 (Codebuch .1, `stichprobe.csv`); Codebuch .2 und die
Bestätigungsstichprobe stehen in § 3.9.

**Was schon deterministisch geprüft ist** (Stufe 1 der Prüfreihenfolge, § 2.6 des Meta-Plans): jede Kante
zeigt auf eine existierende Drucksache (Abgleich mit 48 300 Schlüsseln); 98,8 % zeigen in der Zeit
rückwärts; die Nummer der Antwortanlage ist ein Etikett der Verwaltung selbst. **Was es nicht prüft**: ob
ein Verweis die Sache meint oder nur am Rand nennt, und ob der Typ stimmt. Das prüfen die Kodier-Agenten.

**Codebuch** `validierung/14-vorgaenge/codebuch.toml` (Version 2026-11-23.1, vorläufiges Format, F4 baut
den Rahmen). Einheit: eine Kante (B nennt A). Drei Fragen:

1. `nummer_gemeint` (ja / nein / keine_fundstelle): meint die Fundstelle in B die Drucksache A, oder ist
   es ein Datum, ein Bebauungsplan, eine andere Akte?
2. `selbe_sache` (ja / nein / unklar): würde, wer die Akte von A führt, B darin erwarten?
3. `beziehung` (antwort, nachfrage, umsetzung, aenderung, fortsetzung, bezug, kein_bezug, unklar), mit
   Definitionen. Der Kantentyp des Verfahrens steht **nicht** in der Aufgabe (F4: ohne die Ausgabe des
   geprüften Verfahrens); die Zuordnung Typ → richtige Rollen steht unter `[auswertung.erwartet]`.

**Stichprobe** `validierung/14-vorgaenge/stichprobe.csv` (Spalten `kante`, `schicht`, `typ`, `von`, `nach`;
nur IDs), 150 Kanten, Seed 14, Schichten in Vorrangfolge (eine Kante gehört zur ersten passenden):

| Schicht | Kanten in der Schicht | gezogen |
|---|---|---|
| Mönchengladbach | 387 | 15 |
| periodenübergreifend (Düsseldorf) | 2 599 | 10 |
| antwort | 272 | 25 |
| nachfrage | 303 | 15 |
| umsetzung | 2 915 | 25 |
| aenderung | 657 | 20 |
| nachtrag | 301 | 10 |
| bau | 22 | 5 |
| bezug, mit Titel | 438 | 12 |
| bezug, nur Text oder Anlage | 6 976 | 13 |

**Kodieraufgaben** (nicht im Repo): `/media/konrad/xtraspace/georep/messdaten/kodierung/14-vorgaenge/aufgaben.jsonl`,
150 Zeilen, 1,07 MB. Je Zeile: `kante`, `codebuch`, `a` und `b` mit `drucksache`, `titel`, `dokumentart`,
`datum`, `gremium`, `anlagen` (Namen) und `textanfang` (höchstens 1 500 Zeichen), `fundstelle` (Feld,
Treffer, Ausschnitt mit 300 Zeichen links und rechts, Start und Ende im Ausschnitt) und `fragen` aus dem
Codebuch. 9 Aufgaben haben keine Fundstelle (Nachtrag über die Nummer), 19 Dokumente keinen Text
(Mönchengladbach). Fundstelle im Text 90, im Titel 51.

**Maße** (nach F4): Kantenpräzision = Anteil `selbe_sache = ja` unter ja und nein, ungewichtet an den 150
(das Kriterium) und mit den Schichtgrößen gewichtet (die Zahl über alle 14 870; die Schicht `bezug_text`
trägt 47 % der Kanten mit 13 Kodierungen und macht das gewichtete Intervall breit); Rollenpräzision je
Typ; Krippendorffs α je Frage zwischen den Kodierern. Wilson-95-%-Intervall: 147 / 150 → 0,943 bis 0,993,
150 / 150 → 0,975 bis 1. **Bei höchstens sieben Fehlern an 150 liegt der Punktwert bei mindestens
0,953**; die untere Intervallgrenze erreicht 0,95 erst bei höchstens zwei.

**Nicht in der Stichprobe: die Antwortanlage.** Sie ist keine Kante zwischen zwei Drucksachen, und ihr
Text liegt nicht lokal. Ihre Regel ist eine Namensregel über 2 419 verschiedene Anlagennamen (alle
Dokumentarten); geprüft werden kann sie an den Namen allein (Frage 9.5).

### 4.1 Ergebnis der Kodierung (2026-11-23, Supervisor)

Zwei Kodier-Agenten (Opus) haben die 150 Kanten unabhängig nach `codebuch.toml` (Fassung
2026-11-23.1) kodiert, ein Schlicht-Agent hat die 8 Uneinigkeiten entschieden (dreimal wie A,
fünfmal wie B). Kein menschlicher Goldstandard. Labels je Kante und Frage:
`validierung/14-vorgaenge/labels.csv`.

| Frage | gleich kodiert | Krippendorffs α (nominal) |
|---|---|---|
| `nummer_gemeint` | 150 / 150 | 1,000 |
| `selbe_sache` | 146 / 150 | 0,819 |
| `beziehung` | 142 / 150 | 0,935 |

**Kantenpräzision 139 / 150 = 0,927** (Wilson 95 %: 0,873 bis 0,959), mit den Schichtgrößen
gewichtet über alle 14 870 Kanten 0,922. **Das Kriterium (≥ 0,95) ist nicht erfüllt.** Je Schicht:
Antwort 25/25, Nachtrag 10/10, periodenübergreifend 10/10, Bau 5/5, Bezug mit Titel 12/12, Nachfrage
14/15, Bezug nur Text 12/13, Änderung 18/20, **Umsetzung 21/25**, **Mönchengladbach 12/15**. Die 11
falschen Kanten: `181e4fc42bb2`, `789e32e45dfd`, `c707f89125b1`, `f6edd40eb21f` (Umsetzung),
`017519188ef7`, `3ce35d466ae7`, `de552350d2a7` (Mönchengladbach), `11ed57a4aa2d`, `28b1b1a7c8e7`
(Änderung), `3c7dc42ebf60` (Nachfrage), `25b8500b0bd4` (Bezug nur Text).

Rollenpräzision unter den Kanten derselben Sache: Antwort 23/25, Nachfrage 13/14, Änderung 21/24,
Umsetzung 26/26, Nachtrag 10/10, Bau 5/5, Bezug 35/35.

Beide Kodierer und der Schlichter nennen dieselben Lücken des Codebuchs (Sammelvorlagen und
Beschlusskontrollen, Grundsatzbeschluss angewandt oder nur zitiert, Anfragen zum Umsetzungsstand,
Änderung über förmliche Änderungsdokumente hinaus); ihre Vorschläge liegen lokal unter
`messdaten/kodierung/14-vorgaenge/` (`rueckmeldung-A.md`, `rueckmeldung-B.md`, `schlichtung.jsonl`).

### 4.2 Ergebnis der Bestätigungsstichprobe (2026-11-23, Supervisor)

Stichprobe 2 (100 starke Kanten nach Regelfassung .2, Seed `14-2`, ohne Überschneidung mit den 150
alten), kodiert nach Codebuch .2 von zwei neuen Kodier-Agenten, sechs Uneinigkeiten geschlichtet von
einem dritten. Labels: `validierung/14-vorgaenge/labels-2.csv`. Übereinstimmung: `nummer_gemeint`
100/100 (α 1,000), `selbe_sache` 98/100 (α 0,922), `beziehung` 94/100 (α 0,923).

**Kantenpräzision der Fassung .2: 85 / 100 = 0,850** (Wilson 0,767–0,907), mit den Schichtgrößen
gewichtet **0,840**. Das vorab festgelegte Kriterium (≥ 0,95, ungewichtet und gewichtet) ist
**verfehlt**; die Entwurfsschätzung von 0,985 an den alten Labels hat die Präzision deutlich
überschätzt. Je Schicht: Umsetzung 18/18, Änderung 10/10, Kontrolle 6/6, Nachtrag 3/3, Bezug mit
Titel 4/5, Mönchengladbach 10/12, Nachfrage 8/10, Antwort 6/8, periodenübergreifend 6/8,
Fortsetzung 4/6, **Bezug nur Text 10/14**.

Nach § 5 (Frage 9.16) gilt damit **ohne weitere Runde die Rückfallregel**: stark sind nur Kanten aus
Titel, Anlage, Nachtragsnummer und Sammelbericht. Ihre Präzision an den Labels beider Stichproben
steht in § 5.

### 4.3 Prüfstichprobe der Rückfallregel (Frage 9.18; vorab festgelegt am 2026-11-27)

Festgelegt vor Stichprobe und Kodierung, im selben Commit wie Codebuch, Seed und Skript der
Grundgesamtheit (F4-Nachzug V3, [../plan-zeigen-2026-11.md](../plan-zeigen-2026-11.md), § 4). Sie
ist **keine Umbau-Runde**: sie ändert keine Regel, sie misst die gebaute (Frage 9.18).

**Frage.** Wie präzise ist die Rückfallregel an Kanten, die nur nach ihr gezogen sind? Die Zahl aus
§ 5.1 (104 von 106, 0,981, Wilson 0,934 bis 0,995) ruht auf zwei Ziehungen, die die Regel nicht
zum Ziel hatten, und auf zwei Fassungen des Codebuchs; die Seite zeigt sie darum nicht
(Synergie § 10, „Validierung auf der Seite nur aus `guete.json`").

**Grundgesamtheit** (`docs/plans/14-vorgaenge-pruefung.py`, nach `georep run` in der Hauptperiode,
`v0.32.1`): die starken Kanten von `processed/vorgang_kanten.parquet` innerhalb der Periode
(`nach_periode` leer; die Dokumente der Nachbarperiode liegen nicht im Korpus, aus dem
`validate tasks` die Ausschnitte liest), ohne die 53 Kanten, die schon in Stichprobe 1 oder 2
kodiert sind: 1 740 Kanten, als Einheit `pair_with_span` mit Schlüssel `kante` (SHA-1 über
„von|nach", wie in Abschnitt 10 des Messskripts). Vor dem Ziehen fallen 30 weg, bei denen A oder B
keinen Text hat (`sample.require_text`); es bleiben **1 710**. Nur die Kanten eines Sammelberichts
tragen eine Fundstelle im Text (`verweise.parquet`, im Rohtext wörtlich geprüft, 63 von 63); Titel,
Anlagenname und Nachtrag sieht der Kodierer im Titel und im Kontext. Das Skript schreibt
`<profil>/interim/vorgang_kanten_rueckfall.parquet` (`sample.population`), zweimal gelaufen und
bytegleich (SHA-256 `715c21d8…`); `stichprobe.json` hält die Prüfsumme fest.

| Schicht (`quelle`) | Kanten | mit Text | Stichprobe |
|---|---|---|---|
| Titel | 1 509 | 1 480 | 43 |
| Nachtrag über die Nummer (`nummer`) | 125 | 124 | 4 |
| Sammelbericht | 63 | 63 | 2 |
| Anlagenname | 43 | 43 | 1 |

**Stichprobe**: 50 Kanten, proportional nach der Fundstelle (`allocation = "proportional"`, jede
Schicht mindestens eine), Seed 20261127, gezogen von `georep validate sample 14-vorgaenge-3-f4`
(Rang SHA-256, ohne Zufallsgenerator). Proportional und nicht gleich je Schicht, weil Frage 9.18
das Intervall der ganzen Regel schließen soll: mit 13 Kanten je Schicht trüge der Titel 87 % des
Gewichts auf 13 Kanten, Kishs effektives n fiele auf 17, und schon 52 von 52 richtig ergäben
gewichtet nur 0,817 als untere Grenze; proportional bleibt es bei rund 50. Die Zahl je Fundstelle
(Anlage 1, Sammelbericht 2) ist darum nur eine Beschreibung, kein Befund.

**Codebuch**: [../../validierung/14-vorgaenge-3-f4/codebuch.toml](../../validierung/14-vorgaenge-3-f4/codebuch.toml),
Fassung 2026-11-27.1: die drei Fragen von Fassung .2 wörtlich, bis auf einen Satz zu
`keine_fundstelle` (der Nachtrag steht jetzt im Kontext); neu sind nur die Einheit und das Material
des Auftrags von F4 (Titel, Anfang des Rohtexts bis 1 500 Zeichen, bei einer Fundstelle im Text B
als Fenster von 300 Zeichen; Kontext: Nummer, Dokumentart und Datum beider, die Fundstelle).
Nicht im Auftrag: der Kantentyp des Verfahrens.

**Kodierer** nach der Regel aus Frage 19 ([../validierung.md](../validierung.md), § 3 und § 4):
Kodierer A und Schlichtung Opus, Kodierer B Sonnet; je ein frischer Agent, kein Fork. Aufträge
lokal unter `/media/konrad/xtraspace/georep/messdaten/kodierung/14-vorgaenge-3-f4/` (`A/`, `B/`).

**Maße** (nach F4, `georep validate score`): Kantenpräzision = Anteil `selbe_sache = ja` unter ja
und nein (`unklar` wird gezählt, nicht gewertet), in der Stichprobe (ungewichtet) und für die
1 710 Kanten (gewichtet mit N_h/n_h, Wilson bei Kishs effektivem n); je Fundstelle mit Wilson;
Krippendorffs α je Frage. Wilson 95 %: 50/50 → 0,929 bis 1; 49/50 → 0,895 bis 0,996; 48/50 →
0,865 bis 0,989; 47/50 → 0,838 bis 0,979. **Bei höchstens zwei Fehlern an 50 liegt der Punktwert bei
mindestens 0,960.** Rollenpräzision je Kantentyp (über `id_a`, `id_b` aus `vorgang_kanten.parquet`)
rechnet die Auswertung daneben, ohne Einfluss auf das Urteil.

**Kriterium** (wie § 5): Kantenpräzision ≥ 0,95 am Punktwert, ungewichtet und gewichtet, und α der
Frage `selbe_sache` ≥ 0,8 (`validation.min_alpha`, jetzt zwischen zwei Modellen).

**Nebenmaß, kein Kriterium**: zusammen mit den 104 von 106 aus § 5.1 die untere Wilson-Grenze über
alle Kanten der Rückfallregel. Das ist das Ziel der Frage 9.18: bei 50 von 50 sind es 154 von 156,
untere Grenze 0,954; bei einem Fehler 153 von 156, 0,945. Kein Kriterium, weil die drei Stichproben
verschieden gezogen sind (zwei über alle Kanten aller Datensätze, diese nur über die starken der
Hauptperiode) und nach drei Fassungen kodiert.

**Was folgt, vorab festgelegt.**

- **Erfüllt**: Stufe 3 von 14 zeigt die Präzision der Rückfallregel aus
  `validierung/14-vorgaenge-3-f4/guete.json` (gewichteter Punktwert mit Intervall und dem Satz zur
  Prüfung), für die Hauptperiode gemessen; die Nachbarperioden heißen dort „explorativ"
  (plan-zeigen-2026-11.md, § 8, Gültigkeitsregel).
- **Präzision unter 0,95**: das Urteil aus § 5.1 bleibt (die Regel stand vor beiden Kodierungen
  fest, und diese Prüfung ändert keine). Die Seite zeigt keine Präzision der Kanten; die Fehler
  gehen in Frage 9.17 (Fassung .3), mit Fundstelle und Typ.
- **α von `selbe_sache` unter 0,8**: das Codebuch ist für zwei Modelle zu unscharf
  (validierung.md, § 3); keine Kennzahl auf der Seite, die Uneinigkeiten gehen in Frage 9.17, und an
  diesen Kanten wird nicht nachkodiert.

#### Ergebnis (2026-11-27, nach der Kodierung)

Kodiert nach der Regel aus Frage 19: Kodierer A `claude-opus-5-5`, Kodierer B `claude-sonnet-5-5`,
Schlichtung `claude-opus-5-5`, je ein frischer Agent. Das ist die erste Messung mit Kodierer B auf
einem anderen Modell. Labels, README und `guete.json` stehen unter
[../../validierung/14-vorgaenge-3-f4/](../../validierung/14-vorgaenge-3-f4/); der Satz dort lautet
„geprüft von zwei KI-Kodierern (claude-opus-5-5 und claude-sonnet-5-5) an 50 Dokumentpaaren,
Schlichtung durch claude-opus-5-5, nicht von Menschen".

| Frage | gleich kodiert | Krippendorffs α | Labels |
|---|---|---|---|
| `nummer_gemeint` | 50 / 50 | 1,000 | ja 46, keine_fundstelle 4 |
| `selbe_sache` | 50 / 50 | nicht definiert | ja 50 |
| `beziehung` | 49 / 50 | 0,961 | umsetzung 33, aenderung 13, nachfrage 2, antwort 1, fortsetzung 1 |

Die eine Uneinigkeit (`a013463353a1`, ein Nachtrag zu einer Eingabe nach § 24 GO: A `umsetzung`,
B `aenderung`) entschied der Schlichter zu `umsetzung`. Die Unschärfe, die er nennt, steht als
Frage 9.19 für ein Codebuch Fassung .3 in § 9; angewandt ist sie nicht.

**Gegen das Kriterium.**

- **Kantenpräzision 50 von 50 = 1,000** (Wilson 0,929 bis 1,000); für die 1 710 Kanten gewichtet
  1,000 (Wilson bei Kishs n_eff 49,9: 0,928 bis 1,000). Erfüllt, ungewichtet und gewichtet.
- **α von `selbe_sache`** ist nicht rechenbar: beide Kodierer beurteilten jede Einheit gleich und
  mit demselben Wert (ja bei allen 50). Ohne Streuung gibt es keinen Zufallsabgleich, α und κ sind
  nicht definiert. **Entscheidung des Supervisors (2026-11-27): das zählt als erfüllt**, als
  vollständige Übereinstimmung, bei der kein Zufallsabgleich möglich ist. Die Grenze: das belegt
  nicht, dass das Codebuch Grenzfälle trennt, denn in diesen 50 Kanten kam keiner vor, an dem die
  Kodierer hätten auseinandergehen können. Die Regel steht seit dem 2026-11-27 in F4
  (validierung.md, § 3, Schritt 8): `guete.json` sagt für `selbe_sache` `alpha_genuegt = true` mit
  dem Vermerk „volle Einigkeit, α nicht definiert".
- **Urteil: erfüllt.** Nach „Was folgt" oben zeigt Stufe 3 von 14 die Präzision der Rückfallregel
  aus `guete.json`, für die Hauptperiode gemessen.

**Nebenmaß** (kein Kriterium): mit den 104 von 106 aus § 5.1 zusammen **154 von 156 = 0,987**,
Wilson 0,954 bis 0,996. Die untere Grenze liegt über 0,95; das Ziel der Frage 9.18 ist damit am
Nebenmaß erreicht.

**Ohne Einfluss auf das Urteil** (`docs/plans/14-vorgaenge-pruefung.py --auswertung`):
Kantenpräzision je Fundstelle Titel 43/43, Nachtrag 4/4, Sammelbericht 2/2, Anlage 1/1;
Rollenpräzision je Kantentyp 49 von 50 (umsetzung 27/27, aenderung 9/9, bezug 4/4, kontrolle 2/2,
nachfrage 2/2, antwort 1/1, fortsetzung 1/1, nachtrag 3/4: `a013463353a1` ist als `umsetzung`
geschlichtet, erwartet war `aenderung`).

**Grenzen.**

- 43 der 50 Kanten sind Titelkanten; die Anlage trägt eine, der Sammelbericht zwei, der Nachtrag
  vier. Die Präzision je Fundstelle ist damit **nicht geprüft** (Wilson je Schicht: Anlage 0,207
  bis 1, Sammelbericht 0,342 bis 1, Nachtrag 0,510 bis 1). Die beiden bekannten Fehler der
  Rückfallregel (§ 5.1) lagen in einer Anlage und einem Titel.
- Nur die Hauptperiode und nur Kanten innerhalb der Periode; die Nachbarperioden und
  Mönchengladbach heißen auf der Seite „explorativ".
- Kein menschlicher Goldstandard; zwei Modelle teilen weniger Fehler als eines, aber nicht keine.

## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

### 5.1 Endgültiges Urteil (Abschluss der Stufe 1, 2026-11-23): bauen, mit der Rückfallregel

Die Regelfassung .2 verfehlt an der Bestätigungsstichprobe das vorab festgelegte Kriterium (0,850,
§ 4.2). Darum gilt, wie vor beiden Kodierungen festgelegt (unten und Frage 9.16), **ohne weitere Runde
die Rückfallregel: stark ist eine Kante nur, wenn B die Nummer von A im Titel oder im Namen einer
Anlage nennt, wenn B ein Nachtrag zu A über die Nummer ist oder wenn B ein Sammelbericht ist**
(Beschlusskontrolle und die übrigen Titel aus R3). Jeder reine Textverweis ist schwach. Weil die Regel
vor beiden Kodierungen feststand, ist ihre Präzision an den Labels eine **Messung**, keine
Entwurfsschätzung (Messskript, Abschnitt 13; letzter Lauf um 19:37 Uhr, 39,0 s bei Lastmittel 35 → 27):

| Stichprobe | gezogen | davon nach der Rückfallregel stark | richtig | Präzision | Wilson 95 % | gewichtet |
|---|---|---|---|---|---|---|
| 1 (Codebuch .1, Seed 14) | 150 | 65 (Titel 51, Nummer 10, Sammelbericht 3, Anlage 1) | 65 | **1,000** | 0,944–1,000 | 1,000 |
| 2 (Codebuch .2, Seed 14-2) | 100 | 41 (Titel 29, Sammelbericht 7, Nummer 3, Anlage 2) | 39 | **0,951** | 0,839–0,987 | 0,968 |
| zusammen | 250 | 106 | 104 | **0,981** | 0,934–0,995 | 0,989 (nach Typ nachgeschichtet) |

„Gewichtet" heißt je Stichprobe: Präzision je Schicht, gewichtet mit der Zahl der Rückfall-Kanten in
der Schicht der Grundgesamtheit; zusammen nach Kantentyp .2 nachgeschichtet (die Typen der beiden
Stichproben decken alle 3 563 Rückfall-Kanten). Die zwei Fehler sind beide vom Typ `bezug`:
`e7a023ba6de0` (ein Bauantrag führt den Bauantrag des Nachbargrundstücks als Anlage, als Vergleichsfall)
und `883a584c6d63` (der Titel nennt den Mittelbeschluss `BV6/196/2022` nur als Finanzierungsquelle).
Nachträglich geteilt — **kein Kriterium, weil nach dem Blick auf die Labels**: die typisierten
Rückfall-Kanten sind 89 von 89 richtig (Wilson 0,959–1,000), die `bezug`-Kanten 15 von 17 (0,657–0,967).

**Reicht das?** Der Punktwert erfüllt das Kriterium in jeder Stichprobe und zusammen; die untere
Wilson-Grenze liegt zusammen bei 0,934, also unter 0,95. Das liegt an der Zahl: die Rückfallregel war
nicht das Ziel der Ziehung, sie bekommt aus Stichprobe 1 nur 65 und aus Stichprobe 2 nur 41 Kanten,
zusammen 106 statt der 150 des Briefings, und die beiden Stichproben sind nach verschiedenen
Codebuchfassungen kodiert (.2 ist die strengere: die beiden Fehler stammen aus ihr). Je Typ sind die
Zahlen klein (Antwort 5, Nachfrage 2, Fortsetzung 3). Für ein Urteil „bauen" genügt das, weil die
Regel vorab feststand und keine Stichprobe sie verfehlt; für eine Kennzahl auf der Seite nennt die Seite
104 / 106 mit Intervall und sagt, dass zwei KI-Kodierer geprüft haben. Eine eigene Stichprobe nur aus
Rückfall-Kanten (etwa 50, geschichtet nach Typ) würde das Intervall schließen; sie ist **keine weitere
Umbau-Runde**, weil sie keine Regel ändert, und kann mit Stufe 2 laufen (Frage 9.18).

**Was die Rückfallregel übrig lässt** (Abschnitt 13):

- **Kanten**: 3 563 von 14 870 stark (Düsseldorf 3 392, Mönchengladbach 171), 254 davon über eine
  Periodengrenze. Je Typ: `umsetzung` 1 500, `aenderung` 593, `kontrolle` 566, `nachtrag` 337, `bezug`
  322, `fortsetzung` 105, `nachfrage` 73, `antwort` 67. Die übrigen 11 307 Textkanten bleiben als
  schwache Kanten in den Daten.
- **Vorgänge** (Baum über starke typisierte Kanten): Düsseldorf 2 169 Vorgänge mit 4 643 Dokumenten
  (10,2 %), davon 1 937 aus zwei Dokumenten, größter 7; Mönchengladbach 99 mit 217 Dokumenten (7,5 %),
  größter 4. Ein Vorgang ist damit meist ein Paar: Vorlage und Änderungsantrag, Antrag und
  Umsetzungsvorlage, Original und Nachtrag — der Weg von einem Treffer zum unmittelbaren Nachbarn, keine
  lange Akte.
- **Anfragen mit Antwort**: 3 237 von 8 168 (39,6 %); 2014-2020 55,8 %, Hauptperiode 31,4 %, laufende
  23,0 %. **3 213 dieser Antworten hängen an der Anlage** und sind von der Rückfallregel unberührt, nur
  24 kommen über eine eigene Drucksache, deren Nummer im Titel steht (Fassung .2 hatte 117 solche über
  Textverweise). Das Kriterium „30 % der Anfragen" bleibt erfüllt, in der Hauptperiode knapp.
- **Antwortzeiten**: n = 1 948 gültig datiert, Median 18 Tage, Q1 13, Q3 69, P90 119 — praktisch die
  Zahlen der Anlagen (§ 3.7).

**Was das für die Seite heißt.** Die Antwortzeiten und die Praxis je Gremium (§ 3.7, § 3.8) tragen
unverändert, denn sie hängen an den Anlagen, nicht an Textverweisen. Der Dokumentdialog zeigt je
Dokument nur seine starken Nachbarn mit Rolle (in Beschlusskontrolle genannt, Änderungsantrag,
Umsetzung, Nachtrag, Antwort); Textverweise erscheinen nicht, auch nicht als „ungeprüft". Die
Vorgangsstatistik der Unterseite wird klein und ehrlich: rund 2 200 Vorgänge, fast alle Paare. Was
Textverweise wert sind, bleibt eine Frage für eine Fassung .3 mit eigener Messung (Frage 9.17).

**Antwortanteil**: erfüllt (39,6 %). **Kantenpräzision der gebauten Regel**: 0,981 an 106 Kanten, der
Punktwert erfüllt 0,95. **Urteil: bauen, mit der Rückfallregel**; die drei Änderungen am Briefing unten
gelten weiter (Vorgang als Baum, Antwort aus der Anlage, keine „unbeantworteten Anfragen" und keine rohe
Quote je Fraktion).

### 5.2 Verlauf

**Nachtrag 2026-11-23 (Supervisor): Urteil umbauen.** Die Kodierung (§ 4.1) ergibt eine
Kantenpräzision von 0,927, das Kriterium verlangt 0,95. Nach § 8 des Meta-Plans folgt eine Runde
Umbauen; was unten steht, ist der Stand vor der Kodierung.

**Nach dem Umbau (Runde 2, 2026-11-23, § 3.9): bauen, vorläufig — Bestätigung ausstehend.**

- Die Regelfassung .2 hält Textverweise in Aufzählungen und hinter Verweiszeichen als *schwache* Kanten
  fest, die nicht für Vorgang, Antwort und Anzeige zählen; die Entwurfsschätzung an den alten Labels ist
  0,985 (gewichtet 0,956), **eine Obergrenze, keine Messung**.
- **Vorab festgelegt, bevor die Stichprobe 2 kodiert ist:** Fassung .2 gilt als bestätigt, wenn unter
  den 100 Kanten mindestens 95 % der mit ja oder nein kodierten `selbe_sache = ja` haben (unklar wird
  berichtet, nicht gewertet) und die mit den Schichtgrößen gewichtete Präzision ebenfalls ≥ 0,95 ist.
  Sonst gilt die **Rückfallregel ohne weitere Runde**: stark sind nur noch Kanten aus Titel,
  Anlagennamen und Nachtragsnummer sowie aus Sammelberichten (Runde 1: keiner der elf Fehler steht im
  Titel, Bezug mit Titel 12 / 12, Nachtrag 10 / 10); alle reinen Textkanten werden schwach. Das kostet
  die meisten Kanten — stark blieben 3 392 von 14 483 Düsseldorfer Kanten, und die Vorgänge schrumpfen
  auf 2 169 mit 4 643 Dokumenten —, ist aber ohne neue Kodierung sicher.
- Die drei Änderungen am Briefing unten gelten weiter; die Zahlen der Vorgänge sind mit Fassung .2:
  4 015 Vorgänge mit 9 623 Dokumenten, größter 28. Der Antwortanteil bleibt bei 40,8 %.

*Stand vor der Kodierung (Runde 1):*

**Kriterium** (Briefing, unverändert): Präzision der Kanten ≥ 0,95 an 150; weiter, wenn mindestens 30 %
der Anfragen eine Antwort finden.

- **Antwortanteil: erfüllt.** 40,9 % über drei Perioden, 33,2 % in der Hauptperiode, 56,1 % in
  2014-2020; die laufende Periode liegt mit 24,4 % darunter, ist aber jung (350 Anfragen unter P90) und
  wechselt die Praxis in drei Gremien. Unsicherheit: der Anteil hängt an der Namensregel (eine Änderung
  der Regel um „Stellungnahme" bewegte ihn um 2 von 8 157) und vor allem an der Praxis der Gremien, nicht
  an der Methode; als Kennzahl je Fraktion taugt er nicht (§ 3.8).
- **Kantenpräzision: ausstehend.** Die deterministischen Vorzeichen sind gut (jede Kante trifft eine
  existierende Nummer, 98,8 % richtig gerichtet, 10 datumsförmige Treffer, kein Bebauungsplan), aber ob
  ein Verweis die *Sache* meint, misst erst die Kodierung.

**Urteil: bauen, vorläufig — Validierung ausstehend**, mit drei Änderungen am Briefing:

1. **Ein Vorgang ist ein Baum, keine Zusammenhangskomponente** (§ 3.5): 2 911 Vorgänge mit 6 887
   Dokumenten, größter 36, statt einer Komponente von 4 619.
2. **Die Antwort kommt aus den Anlagen**, nicht aus „A+F Beschluss" (das ist ein Bauschritt) und nur
   selten aus einer eigenen Drucksache (279 von 3 334). Das braucht eine neue Eingabe: Anlagenname und
   -datum je Drucksache (§ 6, Frage 9.1).
3. **Die Seite zeigt keine „unbeantworteten Anfragen" und keine rohe Antwortquote je Fraktion.** Sie
   zeigt „Antwort im Ratsinformationssystem gefunden / nicht gefunden" mit der Praxis des Gremiums daneben,
   Antwortzeiten nur gültig datiert (ab 2019-07-04), und eine Liste „ohne gefundene Antwort" nur für
   Gremien und Perioden, deren Praxis ≥ 0,7 ist, unter diesem Namen. Für den Rat und die Gremien mit
   Praxis unter 0,2 sagt die Seite: „Antworten stehen hier in der Niederschrift; Vorhaben 26".

Kippt die Kodierung (Präzision unter 0,95), ist die erste Stellschraube, `bezug`-Kanten nicht zu zeigen
(nur die typisierten, deren Präzision getrennt gemessen ist), die zweite, Textverweise außerhalb der ersten
1 500 Zeichen abzuwerten; dann eine Runde Umbauen nach § 8 des Meta-Plans.

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

**Eingabe Anlagen.** Zwei Wege, die sich nicht ausschließen (Frage 9.1):

- *jetzt*: `georep pack --attachments` schreibt aus dem Cache-Auszug ein Paket
  `snapshots/duesseldorf-anlagen/raw/anlagen.parquet` (`id`, `name`, `datum`; 56 720 Zeilen, 519 KB zstd,
  alle drei Düsseldorfer Perioden) mit README und Prüfsumme, wie Punkt 58 die Beratungsfolge;
  Mönchengladbach entsprechend unter `reference/moenchengladbach/raw/`. `bootstrap` kopiert es nach `raw/`.
- *danach*: der Netzschritt `papers` behält `auxiliaryFile[].name` und `.date` (und F6 die
  `consultation`-Objekte) in `raw/papers.jsonl`; dann liest der Schritt die Anlagen aus dem eigenen Abruf,
  und das Paket bleibt für die Hauptperiode, deren Korpus aus dem Altformat kommt. Berührt
  `georep/oparl.py` (`OparlPaper.auxiliary_file` liegt schon vor, nur `PaperRecord` verwirft es) und
  `georep/records.py` — mit F6 abzustimmen, das `OparlConsultation` baut.

**Beitrag `procedures`** nach F2 (`georep/enrich/procedures.py`), Schritte in dieser Reihenfolge, beide
offline, nach `bodies` und `parties` (liest deren Ausgaben):

1. `references`: Korpus (`id`, `name`, `reference`, `text`), Anlagen, das **Nummernverzeichnis** der
   Nachbarperioden (Frage 9.2). Schreibt `processed/verweise.parquet` als **Spannen nach F3** (`id`,
   `start`, `end`, `kind` = `drucksache`, `value` = Treffer, `norm` = Schlüssel, `section` = `titel` |
   `text` | `anlage`, `extractor`), auch die ohne Ziel, und `processed/vorgang_kanten.parquet`.
2. `procedures`: Kanten, Arten, Gremien, Urheber. Schreibt `processed/vorgaenge.parquet` und
   `processed/antwortzeiten.parquet`.

**Ausgaben** (Schema-Version aus der Modulkonstante `PROCEDURES_SCHEMA_VERSION = 1`):

| Datei | Spalten | Schlüssel, Ordnung |
|---|---|---|
| `vorgang_kanten.parquet` | `von` str, `nach` str, `typ` str (Typen .2: `antwort`, `kontrolle`, `nachfrage`, `umsetzung`, `aenderung`, `fortsetzung`, `nachtrag`, `bau`, `bezug`), `felder` list[str] (`titel`, `text`, `anlage`, `nummer`), `stark` bool, `quelle` str (`titel`, `anlage`, `nummer`, `sammelbericht`, `text`; die stärkste Fundstelle), `tage` i32, `nach_periode` str (Profil der Nachbarperiode oder leer) | eindeutig (`von`, `nach`), sortiert danach |
| `vorgaenge.parquet` | `id` str, `vorgang` str (ID der Wurzel), `rolle` str (`wurzel`, Kantentyp, `ohne`), `tiefe` i16, `groesse` i32 | eine Zeile je Korpus-ID, sortiert nach `id` |
| `antwortzeiten.parquet` | `id` str, `quelle` str (`anlage`, `drucksache`, `beide`, `keine`), `antwort_datum` date (null, wenn nur Umstellungsdatum), `tage` i32, `antwort_id` str, `alter_am_abruf` i32, `gremium` str, `praxis_gremium` f64 (Anteil mit Antwort im Gremium und in der Periode) | eine Zeile je Anfrage, sortiert nach `id` |

**Die Rückfallregel im Schritt** (§ 5.1): `stark` genau dann, wenn eine Fundstelle im Titel oder in
einem Anlagennamen liegt, die Kante ein Nachtrag über die Nummer ist oder B ein Sammelbericht
(`collective_titles`) ist. Reine Textkanten werden geschrieben, aber `stark = false`; `vorgaenge` und
`antwortzeiten` lesen nur starke Kanten. Die Merkmale der Fassung .2 (Aufzählung, Verweiszeichen) baut
Stufe 2 **nicht**: sie haben an der Bestätigung nicht getragen. Die Typen .2 (`kantentyp2`,
Änderungszeichen, Titel schlägt Dokumentart) bleiben: unter den Rückfall-Kanten waren die typisierten 89
von 89 dieselbe Sache, und ihre Rollen stimmten in Stichprobe 2 (Codebuch .2) 37 von 39-mal; die beiden
Abweichungen sind `fortsetzung`, die die Kodierer als `aenderung` lasen (Regel b in § 9.1).

**Verträge** (an den Batch-Grenzen, Prädikate in `georep.contracts`): `von != nach`; jede `nach` ist im
Nummernverzeichnis; `typ` aus der Aufzählung; genau eine Zeile je Korpus-ID in `vorgaenge`; `vorgang`
zeigt auf eine ID derselben Tabelle, eine Wurzel zeigt auf sich, `tiefe = 0` genau bei der Wurzel; kein
Kreis (die Baumregel nimmt den ältesten typisierten Vorgänger, ein Kreis bricht ab und ist ein Fehler);
`stark` genau bei `quelle` ≠ `text`; `typ = nachtrag` impliziert `stark`; `tage >= 0` oder null; `quelle = keine` genau dann, wenn `antwort_datum` und `antwort_id` null sind und
keine Anlage zählt; Summe der `groesse` über die Wurzeln = Zeilenzahl. Nach jedem Join sortieren.

**Settings** (Anhängeregel aus F2: Modell `Procedures` vor `class Settings`, Feld am Ende, Block am Ende
von `defaults.toml` mit `# --- Vorhaben 14: Vorgänge`, Schalter `procedures.enabled = false`):

```toml
[procedures]                    # Vorhaben 14; Muster und Tabellen stehen im Stadtprofil, kein Stadtwort im Code
enabled = false
related_profiles = []           # Nachbarperioden, deren Nummern als bekannt gelten (Düsseldorf: alle drei)
reference_patterns = []         # je Form ein Regex mit Gruppen code, number, serial, year oder period, suffix
text_patterns = []              # dieselben Formen im kleingeschriebenen Text
answer_attachment = ''          # Muster des Anlagennamens einer Antwort (kleingeschrieben)
interim_attachment = 'zwischen' # Zwischennachricht, keine Antwort
attachment_dates_invalid = []   # Düsseldorf: [2019-07-03], Umstellung des Ratsinformationssystems
[procedures.kinds]              # paper_type -> Rolle; was fehlt, ist "sonst"
[procedures.title_kinds]        # für Sammelarten wie "Vorlage aus der Politik": Titelwort -> Rolle
[procedures.edge_types]         # "rolle_von>rolle_nach" -> Kantentyp; Rest "bezug"
# Rückfallregel (§ 5.1): stark nur aus Titel, Anlage, Nachtragsnummer, Sammelbericht
text_edges_strong = false       # reine Textverweise sind schwach (Bestätigung der Fassung .2: 0,850)
amendment_markers = '…'         # Typ aenderung: Änderungs-, Ergänzungsantrag, zur Vorlage, zu TOP (Defaults)
collective_titles = '…'         # Stadtprofil: Beschlusskontrolle, Veränderungsverzeichnis, Ergebnis der Haushaltsberatungen, …
title_overrides_kind = true     # „Antrag …" als Anfrage eingestellt -> Antrag
```

Düsseldorf trägt die drei Formen aus § 3.1, Mönchengladbach die römische; die gelernten Kürzel zum
Kürzen geklebter Wörter kommen aus den Nummern selbst (oder aus `[bodies]`), nicht aus einer Liste.

**Tests.** Beispiele: je Form Nummer → Schlüssel (mit führenden Nullen, Leerzeichen, Nachtrag `/1`, ` - 1`,
`-1/X`), geklebte Kürzel (`vorlagebv6/002/2023`), alte Form hinter einem Wort, Datumsform, Bebauungsplan in
Mönchengladbach; die Umstellungsregel des Anlagendatums; die Rückfallregel (Titel, Anlage, Nummer,
Sammelbericht stark, Text schwach) und die beiden bekannten Fehler `e7a023ba6de0` und `883a584c6d63` als
dokumentierte Grenze. **hypothesis**: Schlüssel(Formatieren(x)) = x
für erzeugte Nummern jeder Form; die Baumregel erzeugt für jeden Zufallsgraphen einen Wald (jede Wurzel
zeigt auf sich, keine Kreise, Größen summieren sich); Kanten sind unabhängig von der Zeilenfolge der
Eingabe. Mini-Fixture: ein Dutzend Dokumente mit bekannten Kanten aller Typen. **slow**, Golden auf der
Hauptperiode: 14 483 Düsseldorfer Kanten über drei Perioden, davon 3 392 stark, 2 169 Vorgänge,
3 237 Anfragen mit Antwort (Rückfallregel, § 5.1). Kein Netz, kein Modell.

**Berührte Dateien.** Neu: `src/georep/enrich/procedures.py`, `src/georep/prep/references.py` (Muster,
Schlüssel, Spannen), `src/georep/analysis/procedures.py` (Typen, Baum, Antwortzeiten),
`tests/unit/test_references.py`, `tests/property/test_procedures.py`, `tests/golden/test_procedures.py`.
Geändert mit einer angehängten Zeile oder einem Block: `src/georep/enrich/__init__.py`,
`src/georep/settings.py`, `src/georep/defaults.toml`, `src/georep/profiles/duesseldorf.toml`,
`src/georep/profiles/moenchengladbach.toml`, `src/georep/pack.py` (`--attachments`),
`src/georep/bootstrap.py`, `docs/architecture.md` (Schrittabelle, Datenhaltung), `docs/decisions.md`
(Punkt ohne Nummer: „ein Vorgang ist ein Baum", „Antworten aus Anlagen", „keine Antwortquote je
Fraktion", „Textverweise sind schwach: Fassung .2 an der Bestätigung 0,850, Rückfallregel 104 / 106"). Mit F6: `src/georep/oparl.py`, `src/georep/records.py`.

**Laufzeit**: das ganze Messskript braucht für alle vier Datensätze samt Graph und Gruppierungen 36 bis
73 s unter Fremdlast; der Regexlauf über Titel und Texte der Hauptperiode allein kostete in der Erkundung
9 s (einfädig). Der Schritt sollte also unter 20 s je Profil bleiben; gemessen wird in Stufe 2.

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

**Unterseite `vorgaenge.html`** im Rahmen der Hauptseite (F2-Register), je Profil mit Anfragen:

1. *Antworten je Gremium*: Anfragen, „Antwort im Ratsinformationssystem gefunden" (Anteil), Median und
   Q3 der Antwortzeit (nur gültig datiert, n daneben); eine Zeile je Gremium mit mindestens 30 Anfragen.
   Darüber der Satz, dass ein fehlender Anhang keine fehlende Antwort ist, und für Gremien unter 0,2 der
   Hinweis auf die Niederschrift.
2. *Je Fraktion*: nur Antwortzeiten (Median, n ≥ 30) und beobachtet/erwartet gegen die Gremienpraxis,
   „explorativ" überschrieben — keine rohe Quote (Frage 9.4).
3. *Ohne gefundene Antwort*: Nummer, Datum, Gremium, Urheber, Tage — nur Gremien mit Praxis ≥ 0,7 in der
   Periode, älter als P90, als „Kandidaten" benannt, mit Link ins Ratsinformationssystem.
4. *Vorgänge*: Zahl und Größen nach der Rückfallregel (Düsseldorf rund 2 200, fast alle Paare), Typen
   der starken Kanten, ein Satz, dass Textverweise nicht zählen und warum (§ 5.1).

Größe geschätzt unter 50 KB (vier Tabellen, keine Grafik außer einer Größenverteilung). **Vorgang im
Dokumentdialog**: eine nachgeladene `vorgaenge.json` mit den starken Nachbarn je Dokument (Nummer, Rolle;
rund 3 400 Kanten in Düsseldorf, geschätzt unter 100 KB) statt einer Erweiterung von `dokumente.json`
(heute 2,26 MB); keine Textverweise, auch nicht als „ungeprüft". **Tabellen im Register**:
`vorgang_kanten` (mit `stark`), `vorgaenge`, `antwortzeiten` als Parquet und CSV. **Validierung auf der
Seite**: „Verbindungen aus Titel, Anlage, Nachtragsnummer und Sammelbericht: 104 von 106 von zwei
KI-Kodierern als dieselbe Sache bestätigt (Intervall 0,934–0,995), nicht von Menschen; Verweise im
Text sind nicht berücksichtigt, weil sie an 100 geprüften Kanten nur zu 85 % trugen"; „Antwortanlagen
erkannt am Namen der Anlage" mit der Zahl der Namen. **Vorhaben 26**
erweitert die Seite um das Ergebnis je Tagesordnungspunkt und um die Antworten aus den Niederschriften —
erst dann wird aus „Kandidat" eine Aussage, und für den Rat gibt es überhaupt erst eine Antwortquote.

## 8. Vorab festgelegte Hypothesen (nur Analysen: Hypothese, Maß, Test, Schwelle)

Keine; Vorhaben 14 ist beschreibend. Die Gegenüberstellung je Fraktion (§ 3.8) ist **explorativ** und
steht so auf der Seite. Wer daraus eine These macht (etwa: die Verwaltung antwortet der Opposition
langsamer), legt sie in Vorhaben 24 vorab fest, mit dem Gremium als Schicht und der Antwortzeit statt
der Antwortquote als Maß.

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 9.1 | Woher kommen die Anlagen in Stufe 2: Paket aus dem Cache-Auszug oder erweiterter Netzschritt? | ohne Anlagen keine Antworten | beides: Paket jetzt (`pack --attachments`, 519 KB), der Netzschritt behält die Felder ab F6 |
| 9.2 | Darf ein Profil die Nummern seiner Nachbarperioden lesen (`related_profiles`)? | 2 599 Kanten (17,9 %) überqueren eine Periodengrenze | ja, nur lesend aus den Paketen der Nachbarn, ihre Hashes im Stamp |
| 9.3 | Wie zeigt die Seite Gremien, die in der Sitzung antworten (Rat: 855 Anfragen, 1 mit Anlage)? | sonst stünde der Rat als „antwortet nicht" da | Hinweis auf die Niederschrift, keine Liste, bis Vorhaben 26 |
| 9.4 | Zeigt die Seite überhaupt etwas je Fraktion? | rohe Quoten wären parteipolitisch irreführend (AfD 2,3 % roh, 1,23 standardisiert) | nur Antwortzeiten und beobachtet/erwartet, „explorativ"; Konrad entscheidet |
| 9.5 | Wie wird die Namensregel der Antwortanlage geprüft, ohne die Antwort-PDFs? | sie trägt 3 210 der 3 334 gefundenen Antworten | ein kleiner Kodierauftrag nur über Namen (alle verschiedenen Namen an Anfragen); kein Abruf von PDFs ohne Freigabe |
| 9.6 | Sollen „Vorlagen aus der Politik" ohne Titelwort mit Antwortanlage als Anfrage zählen (1 017)? | 2014-2020 ist sonst eine Untergrenze | nein, die Regel wäre zirkulär; die Seite nennt die Untergrenze |
| 9.7 | Zeigt der Dokumentdialog auch `bezug`-Kanten (9 389)? | sie sind die meisten und am wenigsten geprüft | nur typisierte Kanten und höchstens fünf `bezug` als „nennt / genannt von", bis die Kodierung sie trägt |
| 9.8 | Ist der Praxiswechsel in AGS, BV5, BV6 echt oder Verzug? | er erzeugt Kandidaten (BV5-Liste) | beim nächsten Abruf neu messen; bis dahin Praxis je Periode |
| 9.9 | Ist das Anlagendatum das Antwortdatum? | es ist das Datum der Veröffentlichung im System, nicht des Schreibens | ja, im Sinn „seit wann öffentlich"; die Seite sagt das |
| 9.10 | Antwortzeiten auch für Mönchengladbach? | dort gibt es keine Anfragen im Datensatz | nein; der Abschnitt hängt an der Rolle `anfrage` im Profil |
| 9.11 | Was bedeutet `subordinatedPaper` (196 Paare, keins ein Nachtrag über die Nummer)? | könnte eine dritte Kantenquelle sein | in F6 messen, in Stufe 2 nicht verwenden |
| 9.12 | Ist ein Kürzel wie `AUS` im Text („aus/008/2026") ein Risiko? | gewöhnliche Wörter sind auch Kürzel | nein, solange die Nummer existieren muss; `nummer_gemeint` prüft es |
| 9.13 | Verteilervorlagen über gleichen Titel als Kantenart (Vorschlag aus Vorhaben 13)? | gleiche Vorlage an zehn Bezirksvertretungen ist ein Vorgang ohne Verweis | zurückgestellt; in Stufe 2 nur als eigener Typ `verteiler` nach einer eigenen kleinen Prüfung, wegen Formeltiteln |
| 9.14 | Ein Finanzierungszeichen („finanziert über", „Haushaltsposition") als vierte Regel? | ein Fehler der Runde 1 (`25b8500b0bd4`) | nein: aus einem Fall eine Regel wäre an die Stichprobe angepasst; die Stichprobe 2 zeigt, ob es häufiger ist |
| 9.15 | Zeigt der Dokumentdialog schwache Kanten? | 2 126 Kanten, darunter richtige (Entwurf: 6 von 15 verworfenen) | nein im Vorgang; höchstens als „genannt in einer Aufzählung" ohne Rolle |
| 9.16 | Was, wenn die Stichprobe 2 das Kriterium verfehlt? | § 8 des Meta-Plans erlaubt eine Runde | Rückfallregel aus § 5 (nur Titel, Anlage, Nummer, Sammelbericht), vorab festgelegt — **eingetreten** (0,850, § 4.2; Rückfallregel 104 / 106, § 5.1) |
| 9.17 | Eine spätere Fassung .3 für Textverweise, mit den Regeln des Schlichters der Bestätigung? | 11 307 Textkanten liegen schwach in den Daten; .2 trug zu 85 % | **Vorschlag, keine Runde jetzt** (§ 9.1 unten); nur mit neuer Ziehung und vorab festgelegtem Kriterium |
| 9.18 | Eine eigene Stichprobe nur aus Rückfall-Kanten (rund 50, nach Typ geschichtet), um das Intervall über 0,95 zu heben? | die Präzision 0,981 ruht auf 106 Kanten aus zwei Ziehungen, die untere Grenze ist 0,934 | ja, als Prüfung neben Stufe 2, keine Umbau-Runde (sie ändert keine Regel) — **erledigt** am 2026-11-27 (§ 4.3, `validierung/14-vorgaenge-3-f4/`): 50 von 50, zusammen mit § 5.1 154 von 156, untere Wilson-Grenze 0,954 |
| 9.19 | Meint „Nachtrag" in der Definition von `aenderung` das Etikett (dieselbe Nummer mit Zusatz) oder den Inhalt (B ändert, ergänzt oder ersetzt A)? | In der Prüfstichprobe (§ 4.3) legte ein Nachtrag (`a013463353a1`) dieselbe Eingabe nach § 24 GO mit einer Stellungnahme der Verwaltung nur erneut vor; A las `umsetzung`, B `aenderung`. Der Schlichter wählte `umsetzung`: `aenderung` passe über das Nachtragsformat auch, stehe aber später in der Liste, und B ändere A nicht. Die Rollenpräzision zählt beim Typ `nachtrag` nur `aenderung` | **Frage für ein Codebuch Fassung .3** (§ 9.1), nicht angewandt: dort entscheiden, ob „Nachtrag" den Inhalt meint (dann ist ein Nachtrag, der A nur mit Stellungnahme erneut vorlegt, `umsetzung`, und die Erwartung für den Typ `nachtrag` wird `aenderung` oder `umsetzung`) oder das Etikett (dann `aenderung`, vor der Reihenfolgeregel); die Labels von 14-vorgaenge-3-f4 bleiben, wie sie sind |

### 9.1 Vorschlag für eine Fassung .3 (nicht begonnen)

Aus der Schlichtung der Bestätigungsstichprobe (`messdaten/kodierung/14-vorgaenge/schlichtung-2.jsonl`)
und den Rückmeldungen beider Kodierer. Die Datei enthält die Regeln a, b, d, e, f und g; eine Regel c
steht nicht darin — an ihrer Stelle die Lücke, die beide Kodierer nennen (Finanzierungsquelle gegen
Sammelantrag), die auch einen der beiden Rückfall-Fehler erklärt.

| Regel | Inhalt | was sie für eine Fassung .3 hieße |
|---|---|---|
| a | Antwort der Verwaltung auf Fragen aus der Beratung einer Vorlage, die keine Anfrage ist: selbe Sache, `bezug`; `antwort` nur, wenn A eine Anfrage ist; `aenderung` nur, wenn B Beschlussvorschlag, Sachdarstellung oder Zahlen von A ändert | Codebuch; im Verfahren Information → Vorlage bleibt `bezug` |
| b | aktualisierte Fassung oder Fortschreibung desselben Dokuments, die A ablöst: `aenderung`; ein neuer Bericht neben A: `fortsetzung` | Typregel über Titelwörter („aktualisiert", „fortgeschrieben", „Neufassung") |
| c (Kodierer) | Finanzierungsquelle gegen Sammelantrag: nein, wenn B A nur als Mittelquelle nennt, auch im Titel (`883a584c6d63`, „Bauunterhaltungsmittel … Teil B"); ja, wenn B genau einen Punkt von A umsetzt | ein Finanzierungszeichen auch für Titelverweise; vorher messen, wie oft Mittelbeschlüsse im Titel stehen |
| d | Folgeanfrage auf eine Antwort: `nachfrage`, auch bei neuem Aspekt, wenn B an A oder die Antwort anknüpft; `bezug`, wenn B A nur als Vorgeschichte nennt | Codebuch; das Verfahren typisiert Anfrage → Anfrage schon als `nachfrage` |
| e | Stellenplan, Haushalt oder Sammelvorlage mit eigenem Abschnitt zu A: ja, `umsetzung`; nur Aufzählung oder Rahmen: nein | erweitert R3 um Stellenpläne; Abschnittserkennung erst mit F1 (Rohtext) und Vorhaben 11 |
| f | Querverweis auf eine parallele Drucksache zum selben Thema („ebenfalls", „siehe auch", „es wird verwiesen auf"): nein | ein drittes Verweiszeichen zu R2, an einer neuen Ziehung zu messen |
| g | Antrag, der ein mit A beschlossenes Vorgehen vorzieht oder abweichend festlegt: `aenderung`; der nächste Schritt im Rahmen von A: `fortsetzung` | Codebuch; im Verfahren nicht erkennbar |

Aus der Schlichtung der Prüfstichprobe (§ 4.3) kommt Frage 9.19 dazu: ob „Nachtrag" in `aenderung`
das Etikett oder den Inhalt meint. Dazu aus den Rückmeldungen: Mönchengladbacher Fraktionsanträge ohne Text sind nur aus dem Titel als
`aenderung` kodierbar (Kodierer A), und Anlagen, die einen Nachbarfall belegen (`e7a023ba6de0`), sind
keine selbe Sache. Eine Fassung .3 hieße: neue Regeln für **Textverweise**, neue Ziehung, neues
vorab festgelegtes Kriterium — ein eigenes Vorhaben nach Stufe 2, nicht eine weitere Runde dieser
Stufe 1.

## 10. Änderungen durch die Synergie (füllt der Supervisor)

Übertragen am 2026-11-24 aus [00-synergien-2026-11.md](00-synergien-2026-11.md) (§ 1, § 2.1,
§ 2.2 Konflikte 1, 10, 11, 12, § 3 und § 4 „14 Vorgänge"), als Auftrag an Stufe 2. Wo dieser
Abschnitt § 6 und § 7 widerspricht, gilt dieser Abschnitt.

**Stufe 2 (Bauen).**

- **Nur die Rückfallregel** (§ 5.1): stark nur aus Titel, Anlagenname, Nachtragsnummer und
  Sammelbericht; reine Textkanten bleiben schwach in den Daten. Merkmale der Fassung .2
  (Aufzählung, Verweiszeichen) werden nicht gebaut, die Typen .2 schon (§ 6).
- **Spannen nur für Stellen im Text** (Konflikt 1). `verweise.parquet` trägt keine Titel- und
  Anlagentreffer: die stehen nur in `vorgang_kanten` (`felder`, `quelle`), denn `check_spans` prüft
  gegen die Länge eines Texts je Dokument. Die Spannen liegen auf dem Rohtext über
  `flatten_with_offsets` (Fundament-Nachzug F7, `extractor` nennt den Rohtext, `section` aus 11);
  ist der Nachzug nicht rechtzeitig da, bleiben sie auf dem Textstore mit `section = ""`,
  F3-konform. Schema, Folge und Prüfung unverändert aus F3 (`sort_spans`, `check_spans`, Int64,
  Folge `id, start, end, kind`).
- **Dateiname** der Attribute je Dokument: `dokumente_vorgang.parquet` statt `vorgaenge.parquet`
  (Konvention `dokumente_<attribut>.parquet`, Vertrag `contracts.one_row_per_document`).
- **Fundstellen außerhalb des Texts** heißen wie bei den anderen Vorhaben: `titel`, `anlage`,
  `nummer` (dazu hier `sammelbericht` und `text` in `quelle`).
- **Anlagen nur als Paket** über `georep pack`: `snapshots/duesseldorf-anlagen/` (alle drei
  Düsseldorfer Perioden) und `snapshots/moenchengladbach-anlagen/`. **Nichts nach `reference/`
  oder `context/`** (Konflikt 11): `reference/moenchengladbach/` bleibt, wie es ist.
- **`PaperRecord` wird in Stufe 2 nicht erweitert** (§ 2.1, `oparl.py`, `records.py`): F6 hat die
  Felder 14 überlassen, aber es ist ein Schema-Sprung des Korpus mit Golden-Master-Risiko, und das
  Anlagenpaket genügt. „Mit F6 abzustimmen" in § 6 entfällt.
- **Paketbudget** (Konflikt 12): mit dem Rohtext der Hauptperiode liegen alle Pakete bei rund
  166,5 von 180 MiB (`TOTAL_LIMIT`); die Anlagen (rund 0,5 MB und Mönchengladbach) passen. Frage 26
  an Konrad: Annahme „die drei kleinen Pakete ja". Die Größe steht im Commit.
- **Gemeinsame Dateien nach der Anhängeregel** (§ 2.1): in `enrich/__init__.py` eine Importzeile
  und ein Eintrag am Ende von `CONTRIBUTIONS`, ein Beitrag `14-vorgaenge` mit allen Schritten;
  in `settings.py` ein Modell vor `class Settings` und ein Feld am Ende, in `defaults.toml` ein
  Block am Ende mit `# --- Vorhaben 14: Vorgänge`, Schalter aus; in den Stadtprofilen je ein Block
  am Ende, Listen im Stadtprofil (`deep_merge` ersetzt Listen); **keine neuen Properties in
  `layout.py`**, die Pfade gehören dem Modul; in `pack.py`, `cli.py` (`pack`), `bootstrap.py` und
  `tests/unit/test_data_packages.py` je eine Funktion, Option oder Zeile am Ende mit
  `# Vorhaben 14`; in `noxfile.py` Einträge am Ende; den Snapshot von `georep steps`
  (`tests/unit/__snapshots__/test_cli.ambr`) bewusst erneuern.
- **Dokumentart-Tabellen** (`procedures.kinds`) bleiben je Vorhaben, so sind sie validiert; ein
  gemeinsamer Test prüft später für jedes Profil jede vorkommende Dokumentart gegen jede Tabelle
  (abgebildet oder ausdrücklich „sonst").
- **Reihenfolge**: Welle 1 (14, 11, 12, 15, 22); Merge an Position 3, nach 11 und 12. 14 wartet
  auf nichts außer der Paketentscheidung; F1 nur, wenn die Spannen auf dem Rohtext liegen.

**Stufe 3 (Zeigen), zur Kenntnis.**

- **Fraktion aus 15** (`fraktionen`), nicht aus `parteien` (Konflikt 10); beobachtet/erwartet
  über die Funktion, die 15 in `analysis/` baut.
- **Dokumentdialog über einen eigenen Haken** in `templates/frame/script.js.j2` (Datei
  `data/<name>.json`, Zeilen je Dokument), an den sich 18 und 26 hängen; `dokumente.json` wächst
  nicht.
- **Validierung auf der Seite nur aus `guete.json`** (F4). Dort steht heute die Präzision der
  ganzen Regel (0,927 und 0,850), nicht die der Rückfallregel (104 / 106); bis zum F4-Nachzug (die
  Rückfallregel als Verfahren in `score` oder die Prüfstichprobe aus Frage 9.18 als
  `14-vorgaenge-3-f4`) kommt keine dieser Zahlen auf die Seite. Die Prüfstichprobe läuft parallel
  zu Stufe 2.
- `vorgaenge.html` füllt später auch Vorhaben 26; dafür braucht F2 Abschnitte aus fremden
  Beiträgen, für Stufe 3 von 14 nicht.
