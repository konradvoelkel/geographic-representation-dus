# Vorhaben 24: Anfragen als Kontrolle in der Kooperation

**Stand 2026-11-26: Urteil umbauen (§ 5.1), gemessen, nicht gebaut.** Die eine Umbaurunde steht aus:
Zulieferer 26 liegt vor, 19 nicht; die Antwortanlagen brauchen einen eigenen Stichprobenabruf ihrer
PDFs. Umbauen oder verwerfen ist Frage 41 in `fragen-2026-11.md`. **§ 10 vor dem Bau durch den
Supervisor.**

Stufe 1 (Messen) vom 2026-11-23 auf dem Branch `feat/24-kontrolle` (gemerged, entfernt). Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „24 Anfragen als Kontrolle
in der Kooperation". Messskript: [24-kontrolle-messung.py](24-kontrolle-messung.py).

Die Hypothesen (§ 8) sind im Commit `a0cc89e` festgelegt, **bevor** eine Anfrage einem Dezernat
zugeordnet oder eine Zelle gezählt war (§ 2.11 des Meta-Plans); sie sind danach nicht geändert. Codebuch
und Stichprobe: `validierung/24-kontrolle/`.

**Urteil nach der Kodierung (Abschluss der Stufe 1, 2026-11-23): umbauen.** Die Zuordnung Anfrage →
Dezernat wird in dieser Form **nicht** gebaut; H1 bleibt ungerechnet (§ 5.1). Die drei Zahlen:

1. **Keine Schicht erreicht die Präzision 0,9** (§ 4.1): Antwort 7/8 und Amt im Text 14/16 (je 0,875),
   Klassifikator hoch 12/14 (0,857), mittel 11/14 (0,786), **Fachausschuss 17/22 (0,773, Wilson
   0,566–0,899)**, Klassifikator niedrig 5/14 (0,357). Hochgerechnet auf die 2 757 zugeordneten Anfragen
   **0,721** (0,596–0,847). Nach der vorab festgelegten Regel (§ 4) bleibt kein Weg im Verfahren.
2. **Die Frage selbst ist kodierbar**: zwei Kodierer einig bei 96 von 100 (Krippendorffs α 0,954), nur 4
   Schlichtungen. Es scheitert das Verfahren, nicht das Konstrukt: der Fachausschuss ist bei fast jeder
   vierten Anfrage nicht das adressierte Dezernat, und der Klassifikator schiebt Rat-Anfragen dem
   Oberbürgermeister zu.
3. **Die Fallzahl hätte getragen** (Teststärke 0,99 bis 1,00 bei IRR 1,5, § 3.5): ein neuer Weg, der 0,9
   erreicht und rund die Hälfte der Anfragen zuordnet, reicht für die Prüfung.

*Vorläufiges Urteil vor der Kodierung (Stand des Commits `2cddab5`): „bauen, wenn die Kodierung die
Präzision bestätigt", mit 79,3 % Abdeckung und der Erwartung, Fachausschuss und sicherer Klassifikator
trügen. Die Erwartung war falsch; § 4.1 sagt, warum.*

Die Tabelle der Dezernate, ihrer Ämter und der vorschlagenden Fraktionen 2014–2026 steht mit Quellen in
§ 2.2; die Köpfe der Vorlagen bestätigen sie zu 97,9 % (§ 3.2).

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

**Frage.** Fragen die Fraktionen der Ratsmehrheit gezielt die Dezernate, die ihr Kooperationspartner
führt? Anfragen sind das Kontrollinstrument der Kommunalpolitik (3 950 in der Hauptperiode, 8 157
in den drei Düsseldorfer Perioden, § 3.1); ob sie auch *innerhalb* der Mehrheit kontrollieren, ist eine Frage der
Koalitionsforschung, die bisher für den Bundestag und für einen Querschnitt deutscher Großstädte
beantwortet ist, nicht für die Abfolge zweier Mehrheiten in einer Stadt.

**Literatur.** Höhmann und Sieberer (2020) für den Bundestag; Höhmann und Krauss (2022, Parliamentary
Affairs 75 (2), S. 420–448, DOI 10.1093/pa/gsab002) zum Detailgrad der Koalitionsverträge (je
detaillierter, desto mehr Fragen: Verträge und Fragen ergänzen sich); Block (2024, DOI
10.1017/S1755773923000322) und Block (2025, DOI 10.1017/gov.2024.19, frei lesbar unter CC BY-NC-ND) für
deutsche Großstädte. Block ordnet Anfragen über CAP-Themen den Zuständigkeiten der Dezernate zu, weil
„PQs at the local level are not addressed directly to a portfolio" — dieselbe Lage wie hier (12, § 3.3:
eine Anfrage nennt ihr Ziel nicht). Er zählt je Partei, Dezernat und Wahlperiode; dieses Vorhaben zählt
je Halbjahr, weil Dezernate in Düsseldorf mitten in der Periode neu geschnitten werden (2021-07,
2022-08, 2023-08, 2024-09, 2026-01, § 2.2).

**Ratsarbeit.** Für Fraktionsgeschäftsstellen aller Parteien: „Welches Dezernat befragen wir wie oft,
und wie oft die anderen?" — eine Übersicht je Fraktion und Dezernat, gleich für alle gebaut. Für die
Seite: ein Abschnitt auf `akteure.html`, der das Kontrollverhalten in der Kooperation zeigt, mit dem
Vorbehalt, dass eine Zuordnung zu Dezernaten eine Messung ist.

**Zulieferer.** 11 (Kopffelder: Amt der Vorlagen), 12 (Amtsverzeichnis), 14 (Antwort als eigene
Drucksache, Praxis der Gremien), 15 (Mehrheiten, gemeinsame Anfragen, Urheber). Später: 19
(Politikfeld je Dokument, ein fünfter Weg der Zuordnung), 25 (Positionen und Vereinbarungen, für H2 und
H3), 27 (Fragesteller als Person, Mehrheiten der Bezirke).

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

Gerechnet auf den Läufen vom 2026-11-23 (`georep bootstrap && georep run` für `duesseldorf`,
`duesseldorf-2014`, `duesseldorf-2025` im Worktree, 19:46 bis 19:49 Uhr, alle Exit 0). Mönchengladbach
hat keine Anfragen (14, § 2) und fehlt darum.

### 2.1 Korpus

Je Profil, nur lesend (Pfade aus `georep --profile <p> paths`):

- `interim/papers.parquet`: `id`, `reference`, `date`, `paper_type`, `name` (Titel), `file_name`, `text`
  (kleingeschrieben).
- `processed/papers_gremien.parquet`: `id`, `gremium`, `gremium_art` (`rat`, `ausschuss`,
  `bezirksvertretung`, `beirat`, `unbekannt`; Punkte 23, 57, 58).
- `processed/dokumente_urheber.parquet`: `id`, `urheber_art`, `parteien` (Schlüssel `CDU`, `GRUENE`,
  `SPD`, `FDP`, `Die_Linke`, `AfD`, `T_FW`, `PARTEI`, `VOLT`).
- `messdaten/rohtext/<ordner>.parquet` (Phase 0): `name`, `text` mit Groß- und Kleinschreibung und Zeilen —
  er trägt die Kopffelder der Vorlagen (`Fachbereich:`, `Amt / Institut:`), die der kleingeschriebene
  Store nur geplättet hat.

`processed/papers_ausschuss.parquet` (der Ausschussklassifikator, Punkt 45) nennt das Briefing als Weg
„über den Gegenstand". Er sagt, welcher *Ausschuss* passt, nicht welches Dezernat; der Mess-Agent hat
ihn durch einen Klassifikator Text → Amt ersetzt, der an den Vorlagen mit Amt im Kopf lernt (§ 3.3), weil
Ämter die Einheit sind, die der Dezernatsverteilungsplan verteilt.

### 2.2 Fremddaten: Dezernate und wer sie führt

Abgerufen am 2026-11-23 durch einen Unteragenten, nur öffentliche Quellen, abgelegt unter
`/media/konrad/xtraspace/georep/fremddaten/dezernate/` (README mit URL, Abrufdatum, Größe, SHA-256 und
Lizenz je Datei, 73 Dateien; `beigeordnete.tsv` mit 42 Zeilen). Ins Repo kommt nur diese Tabelle. Erhoben
sind nur Name, Funktion, Dezernat, Zeitraum und vorschlagende Fraktion oder Parteizugehörigkeit.

**Zuerst im Datensatz selbst geprüft** (Briefing): die Wahlvorlagen stehen im Korpus — `RAT/323/2021`
und `RAT/326/2021` (Wahl von Rauterkus für das „neue Dezernat für Wirtschaft, Digitalisierung, Personal
und Organisation" und Kral für das „neue Dezernat für Mobilität", Amtsantritt 2021-07-01),
`RAT/116/2022` und `RAT/119/2022` (Koch, „Kultur und Integration"; Zur, „Sport und Bürgerservice"),
`RAT/295/2023` (Wagner, „Personal, Organisation und Digitalisierung"), `RAT/014/2023`, `RAT/085/2024`,
`RAT/386/2024` (Wiederwahlen Schneider, Zuschke, Zaum, mit dem Datum der ersten Wahl) und
`RAT/368/2021`, `RAT/279/2023` (Reihenfolge der Vertretung: wer zu dem Datum Beigeordnete war). **Keine
dieser Vorlagen nennt eine Partei oder eine vorschlagende Fraktion**; die Wahl ist geheim (§ 50 Abs. 2
GO NRW, so in den Vorlagen). Die Partei kommt darum aus der Presse, den Kooperationsvereinbarungen und
Wikipedia; Personen und Daten sind am Korpus gegengeprüft (§ 3.2).

| Dez. | Inhaber/in (Funktion) | von – bis | Ämter (Auswahl, mit Wechseln) | führt (Regel § 8) | Beleg der Partei bzw. des Vorschlags |
|---|---|---|---|---|---|
| 01 | Elbers (OB) | – 2014-08 | 01, 13, 80 | CDU (Partei des OB) | de.wikipedia.org/wiki/Dirk_Elbers |
| 01 | Geisel (OB) | 2014-09 – 2020-10 | 01, 13, 80 | SPD (Partei des OB) | Stadtchronik 2014 (duesseldorf.de/stadtarchiv/stadtgeschichte/chronik/2014); Wikipedia |
| 01 | Keller (OB) | 2020-11 – | 01, 13; 80 bis 2021-06 | CDU (Partei des OB) | de.wikipedia.org/wiki/Stephan_Keller_(Politiker) |
| 02 | Abrahams (Stadtdirektor, Kämmerer) | – 2015-09 | 20, 21, 22, 67 | CDU (Mitgliedschaft, nur Presseüberschrift) | WZ „Abrahams, Bonin, Keller: Der Abgang der CDU-Dezernenten" (aid-27905049) |
| 02 | Schneider (Kämmerin) | 2015-11 – | 20, 21, 22, 67; 23 ab 2016-05; 69 2026-01 bis 2026-09 | SPD (Vorschlag) | WZ „Rat wählt Schneider zur Kämmerin" (aid-28966181); ddorf-aktuell 2015-08-15 |
| 03 | Bonin | – 2015-11 | 23, 60–63, 65 | CDU (Mitgliedschaft, nur Presseüberschrift) | WZ aid-27905049 |
| 03 | Zuschke | 2016-09 – | 61–63, 65; 66 2017-06 bis 2021-06 und 2026-01 bis 2026-09; 64 ab 2021-07 | **keine** (Vorschlag des OB 2016, Fraktion nicht belegt; die Wiederwahl 2024 war ohne Ausschreibung, `RAT/085/2024`, also keine „Neuwahl", für die die Kooperation 2021 der CDU das Vorschlagsrecht gibt — die andere Lesart rechnet R4) | Pressedienst 2016 „Stadtrat wählt Cornelia Zuschke"; gruene-duesseldorf.de/koop-kooperation-dezernate |
| 04 | Meyer-Falcke | – 2020-08 | 10, 11, 16, 53; 33 ab 2017-06 | FDP (Vorschlag) | de.wikipedia.org/wiki/Andreas_Meyer-Falcke; WZ aid-48610269 |
| 04 | Rauterkus | 2021-07 – 2023-03 | 10, 16, 80; 33 bis 2022-07 | CDU (Vorschlagsrecht Kooperation 2021) | gruene-duesseldorf.de/koop-kooperation-dezernate; `RAT/323/2021` |
| 04 | Wagner | 2023-10 – | 10, 16; 33 ab 2024-09 | CDU (Vorschlagsrecht Kooperation 2021 für Dezernat 04; die Wahl 2023 war eine Neuwahl nach Ausschreibung, `RAT/295/2023`; wer vorschlug, ist nicht belegt) | Pressedienst 2023-09-07; `RAT/295/2023` |
| 05 | Kral | 2021-07 – | 66, 69; 19, 68 ab 2022-06; ab 2026-01 nur 19, 68 | Grüne (Vorschlagsrecht Kooperation 2021) | gruene-duesseldorf.de/news/verkehrsdezernent-kral; `RAT/326/2021` |
| 06 | Hintzsche (Stadtdirektor ab 2015-10) | – | 40, 50, 51; 52 bis 2022-07 und ab 2024-09; 54 bis 2022-04; 64 bis 2017-05; 37 ab 2024-09 | SPD (Mitgliedschaft) | WZ aid-27905049 |
| 07 | Keller (Beigeordneter) | – 2016-12 | 12, 30, 32, 33, 66 | CDU (Mitgliedschaft) | Wikipedia |
| 07 | Zaum | 2017-06 – | 12, 30; 32 außer 2023-08 bis 2024-08; 64 bis 2021-06; 37, 53 2021-07 bis 2024-08 (53 bis 2025-12); 80 ab 2023-08 | CDU (Vorschlag) | WZ „Christian Zaum ist neuer Ordnungsdezernent" (aid-27133969); ddorf-aktuell 2017-04-06 |
| 08 | Stulgies | – 2022-05 | 19, 39, 68; 37 bis 2021-06 | Grüne (Vorschlag) | WZ aid-29241319 |
| 08 | Zur | 2022-08 – 2024-06 | 33, 52; 32 ab 2023-08 | FDP (Vorschlagsrecht Kooperation 2021; parteilos) | de.wikipedia.org/wiki/Britta_Zur; Pressedienst 2022-03 |
| 09 | Lohe | – 2022-04 | 41; VHS, Musikschule ab 2017-06 | CDU (Mitgliedschaft) | ddorf-aktuell 2018-04-27 |
| 09 | Koch | 2022-05 – | 41, VHS, Musikschule, 54; 53 ab 2026-01 | Grüne (Vorschlagsrecht Kooperation 2021) | ddorf-aktuell 2022-04-07; `RAT/116/2022` |
| IN | Beyer (Infrastruktur) | 2026-10 – | 23, 66, 67, 69 | **keine** (gemeinsamer Vorschlag laut Koalitionsvertrag 2025, S. 57; parteilos) | Pressedienst 2026-09; Koalitionsvertrag CDU/Grüne 2025–2030 |

Lücken mit Vertretung (Dezernat ohne Inhaber, „führt keine"): 02 im Oktober 2015, 03 von 2015-12 bis
2016-08, 07 von 2017-01 bis 2017-05, 04 von 2020-09 bis 2021-06 und von 2023-04 bis 2023-09, 08 2024-07
und 2024-08. Die Ämter je Zeitscheibe stehen vollständig in `DEZERNATE` im Messskript, aus den
Dezernatsverteilungsplänen der Stadt (Stand 01.02.2018, 01.07.2021, 01.08.2022, 01.10.2023,
01.09.2024, 01.01.2026; die älteren aus dem Internet Archive) und für 2014 bis 2016 aus den archivierten
Vorstandsseiten (dort ohne Amtsnummern; die Nummern sind über gleichnamige Ämter erschlossen).

**Kooperationsvereinbarungen**: 2014 (Ampel) verteilt keine Dezernate; die Vorschlagsrechte jener Jahre
stehen nur in der Presse. 2021 (CDU/Grüne, vorgestellt 2021-01-08) nennt sie ausdrücklich: CDU für das
neue Dezernat Wirtschaft, Digitalisierung, Personal und Organisation, Grüne für Mobilität (später
Umwelt), FDP für Sport und Bürgerservice, Grüne für Kultur und Integration, CDU für Planen und Bauen
„bei einer Neuwahl". Der Koalitionsvertrag 2025–2030 (S. 57) schafft 2026 ein Dezernat Infrastruktur,
dessen Besetzung beide gemeinsam verabreden.

**Unsicher oder unbelegt** (aus dem README der Fremddaten): die Parteien von Abrahams, Bonin und
Rauterkus stehen nur in Überschriften oder Suchauszügen (die WZ liegt hinter einer Bezahlschranke), die
von Hintzsche, Schneider, Stulgies und Zaum in WZ-Artikeln, die nur als Auszug lesbar waren; Zuschkes,
Krals und Wagners Mitgliedschaft ist nicht belegt (für Kral und Wagner trägt Regel 2, das
Vorschlagsrecht). Der Plan vom 01.01.2026 und die Vorstandsseite vom Januar 2026 widersprechen sich bei
66, 69 und dem Schienen-ÖPNV (Kral oder Zuschke und Kämmerin); die Tabelle folgt dem Plan, die Köpfe der
Vorlagen bestätigen ihn (§ 3.2).

**Lizenz**: die Tabelle ist eine eigene Zusammenstellung öffentlicher Tatsachen mit Quellenangabe; die
gespeicherten Pressetexte und Vereinbarungen sind urheberrechtlich geschützt und bleiben lokal.

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

Alle Zahlen vom 2026-11-23, Lauf des Messskripts um 20:57 Uhr (`nice -n 10 uv run python
docs/plans/24-kontrolle-messung.py --sim 400`, Polars auf vier Threads, Lastmittel um 20 durch andere
Agenten), **229 s**, fast alles Laden, Training und Kreuzprüfung des Klassifikators; die Simulation der
Teststärke braucht zusammen rund zehn Sekunden. Zwei
Läufe ohne Änderung der Zuordnung ergeben dieselben Zahlen und dieselbe Stichprobe (SHA-256 von
`stichprobe.csv` vor und nach dem letzten Lauf gleich).

### 3.1 Anfragen und die Grundgesamtheit der Prüfung

Anfragen nach der Rolle aus 14 (`art()`); „Stadtebene" heißt Rat oder Ausschuss, in 2014–2020 auch die
Drucksachen mit einer Amtsnummer als Kopf ohne erkanntes Gremium; „im Fenster" heißt ab dem Halbjahr der
Kooperation (§ 8).

| Periode | Anfragen | Rat/Ausschuss | Bezirksvertretung | Beirat | von Fraktionen, Stadtebene, im Fenster | davon gemeinsam |
|---|---|---|---|---|---|---|
| 2014-2020 | 3 131 | 1 832 | 1 058 | 241 | 1 409 | 29 |
| 2020-2025 | 3 950 | 1 634 | 2 201 | 115 | 1 582 | 129 |
| 2025- | 1 076 | 510 | 544 | 22 | 485 | 21 |
| zusammen | 8 157 | 3 976 | 3 803 | 378 | **3 476** | 179 |

Die 3 476 sind die Grundgesamtheit der Zuordnung und der Stichprobe. Davon stellen die
Mehrheitsfraktionen den kleineren Teil (§ 3.4): die Opposition fragt mehr (15, § 3.7).

### 3.2 Gegenprobe der Dezernatstabelle an den Köpfen der Vorlagen

Für jede Vorlage mit Amt im Kopf (8 288 in drei Perioden) sucht das Skript das Dezernat des Amtes zum
Datum in `DEZERNATE` und vergleicht die Person mit dem Feld „Dezernentin / Dezernent" desselben Kopfes
(der Name wird nur verglichen, nicht gespeichert). **7 791 von 7 958 vergleichbaren Köpfen (97,9 %)
stimmen.** Die Abweichungen sind fast alle neu erzeugte PDFs: Amt 66 mit Kral auf Vorlagen von 2019 bis
2021-06 (39; Kral trat 2021-07 an), Amt 01 mit Keller als OB auf Vorlagen von 2019 und 2020 (26; Keller
wurde 2020-11 OB). Der Kopf zeigt die Person zur Zeit der PDF-Erzeugung, nicht zum Datum der Drucksache
(Frage 9.9). Umgekehrt bestätigen die Köpfe den Plan vom 01.01.2026 gegen die Vorstandsseite: Amt 66 trägt
von 2026-01 bis 2026-09 in 76 Köpfen Zuschke, in keinem Kral (und in 3 Beyer, Vorlagen vom Juli und August
2026, vor seinem Amtsantritt im Oktober — wieder neu erzeugte PDFs).

### 3.3 Zuordnung Anfrage → Dezernat: vier Wege

Eine Anfrage nennt ihr Ziel nicht (12, § 3.3). Das Skript prüft vier Wege, in dieser Rangfolge:

1. **Antwort** als eigene Drucksache: eine spätere Informationsvorlage mit Amt im Kopf, deren Titel oder
   Textanfang die Nummer der Anfrage nennt (Typ `antwort` aus 14) → Amt → Dezernat zum Datum der Anfrage.
2. **Fachausschuss**: die Anfrage ist in einem Ausschuss gestellt, und mindestens 80 % der Vorlagen dieses
   Ausschusses in der Periode kommen aus Ämtern eines Dezernats (zum Datum der Anfrage); in 2014–2020
   zusätzlich die Amtsnummer vor dem ersten Schrägstrich der alten Drucksachennummer (Punkt 57; das ist
   das Amt mit der Geschäftsführung des Ausschusses, außer `01`, dem Ratsbüro).
3. **Amt im Text**: Titel oder Text nennen Ämter beim Namen oder als „Amt 66", und alle genannten Ämter
   liegen in einem Dezernat (`AMT_MUSTER` im Skript, aus dem Amtsverzeichnis der Köpfe).
4. **Klassifikator** Text → Amt: TF-IDF über Wörter und Wortpaare und logistische Regression, trainiert an
   den 7 734 Vorlagen mit Amt im Kopf **ohne den Kopf** (der Text beginnt bei Beschluss- oder
   Sachdarstellung); die Wahrscheinlichkeiten der Ämter werden je Dezernat zum Datum der Anfrage
   summiert. Kreuzprüfung über die Perioden (je eine Periode Test): auf Ebene Dezernat richtig bei
   **0,918** (2014–2020, n = 1 212), **0,877** (2020–2025, n = 5 478), **0,943** (2025-, n = 1 044) —
   an Vorlagen; an Anfragen misst es erst die Kodierung. Schichten nach der Wahrscheinlichkeit p des
   besten Dezernats: hoch (p ≥ 0,7), mittel (0,5 ≤ p < 0,7), niedrig (0,3 ≤ p < 0,5); darunter keine
   Zuordnung.

Der Ausschussklassifikator aus Punkt 45 (`papers_ausschuss.parquet`) ist nicht verwendet: er sagt den
passenden Ausschuss, und gemischte Ausschüsse (OVA, AGS, HFA) haben kein eindeutiges Dezernat.

**Abdeckung in der Grundgesamtheit** (3 476 Anfragen; Rangfolge wie oben, jede Anfrage einmal):

| Periode | n | Antwort | Fachausschuss | Amt im Text | Klass. hoch | Klass. mittel | Klass. niedrig | keine | zugeordnet |
|---|---|---|---|---|---|---|---|---|---|
| 2014-2020 | 1 409 | 4 | 1 002 | 63 | 3 | 59 | 168 | 110 | 92,2 % |
| 2020-2025 | 1 582 | 3 | 669 | 165 | 23 | 77 | 206 | 439 | 72,3 % |
| 2025- | 485 | 1 | 202 | 48 | 4 | 13 | 47 | 170 | 64,9 % |
| zusammen | 3 476 | **8** | **1 873** | **276** | **30** | **149** | **421** | **719** | **79,3 %** |

Jeder Weg für sich (ohne Rangfolge): Antwort 8 (0,2 %), Fachausschuss 1 879 (54,1 %), Amt im Text 629
(18,1 %; 45 davon mit Ämtern mehrerer Dezernate, nicht zugeordnet), Klassifikator p ≥ 0,7 169 (4,9 %),
p ≥ 0,5 750 (21,6 %), p ≥ 0,3 2 055 (59,1 %). Ohne die niedrige Schicht sind 67,2 % zugeordnet, mit
Antwort, Fachausschuss und Klassifikator ab 0,7 allein 55,0 %, nur mit Antwort und Fachausschuss 54,1 %.

Was das heißt:

- **Die Antwort trägt auf der Stadtebene fast nichts**: Rat-Anfragen werden in der Sitzung beantwortet
  (14, § 3.8: 0,2 % mit Antwort im Rat), Ausschussanfragen, wo überhaupt schriftlich, als Anlage (16,5 %
  der Ausschussanfragen, 14, § 3.7), deren PDF nicht lokal ist;
  eine eigene Drucksache als Antwort gibt es für 8 der 3 476. Der Weg, den das Briefing zuerst nennt,
  fällt für die Prüfung aus (Frage 9.3).
- **Der Fachausschuss ist der Hauptweg** (54 %). Eindeutig (Anteil ≥ 0,8) sind in der Hauptperiode APS,
  JHA, KUA, SPOA, SEBD (je ≥ 0,99), AUS 0,98, BAU 0,98, AWM 0,95, SCHUA 0,94, ABA 0,92, AÖE und GLA 0,89,
  ADIG 0,87; **nicht** eindeutig sind OVA 0,78 (Ordnung und Verkehr in zwei Dezernaten), HFA 0,62, AWIR
  0,62, AGS 0,56 (Soziales und Gesundheit). In 2014–2020 trägt die Amtsnummer der alten
  Drucksachennummer 1 002 Anfragen.
- **Amt im Text ist der unsicherste Weg**: genannt werden vor allem Ordnungsamt und OSD (65),
  Wirtschaftsförderung (49), Gesundheitsamt (35), Jugendamt (17), Kämmerei (16), Verkehrsmanagement (15) —
  oft als Gegenstand oder Beteiligte, nicht als Adressat. Er stimmt mit dem Fachausschuss nur bei 197 von
  353 (55,8 %, Wilson 0,506–0,609) und mit dem Klassifikator bei 307 von 633 (48,5 %) überein.
- **Der Klassifikator ist an Anfragen vorsichtig**, aber wo er sicher ist, stimmt er mit den Daten:
  gegen Antwort oder Fachausschuss ab p 0,5 bei 507 von 549 (92,3 %), ab 0,6 283 von 304 (93,1 %), ab
  0,7 129 von 133 (97,0 %), ab 0,8 45 von 45. Über alle Anfragen mit Fachausschuss stimmt sein bestes
  Dezernat zu 70,3 % (1 324 von 1 884).
- **Rat-Anfragen bleiben am häufigsten ohne Zuordnung**: kein Fachausschuss, oft mehrere Gegenstände; dort
  setzen 19 (Politikfeld) und 26 (Ergebnis im Rat, Niederschrift) an.

Bezirksvertretungen (Nebenrechnung R2, 2 581 Anfragen von Fraktionen im Fenster): ohne Fachausschuss und
fast ohne eigene Antwortdrucksache sind 33,6 % zugeordnet, davon 588 nur mit niedriger Wahrscheinlichkeit
des Klassifikators. R2 ist damit schwach (Frage 9.7).

### 3.4 Fallzahl je Fraktion × Dezernat × Halbjahr

Zellen der Mehrheitsfraktionen mit allen Dezernatseinheiten des Halbjahrs, Nullen eingeschlossen; eine
gemeinsame Anfrage zählt je Fraktion. **Nicht** gezählt ist, wie viele Anfragen auf Zellen mit Status
`partner` und `eigen` fallen (§ 8): das wäre die Prüfung.

| Periode | Zellen | Anfragen der Mehrheit in Zellen | Mittel je Zelle | Halbjahre | Dezernatseinheiten | Zellen partner oder eigen |
|---|---|---|---|---|---|---|
| 2014-2020 (SPD, Grüne, FDP) | 336 | 552 | 1,64 | 13 | 17 | 189 |
| 2020-2025 (CDU, Grüne) | 180 | 303 | 1,68 | 10 | 14 | 104 |
| 2025- (CDU, Grüne) | 50 | 32 | 0,64 | 3 | 9 | 30 |
| zusammen | 566 | **887** | 1,57 | 26 | | 323 |

42,8 % der Zellen sind null. Je Fraktion: 2014–2020 Grüne 269, SPD 146, FDP 137; 2020–2025 Grüne 175, CDU
128; 2025- Grüne 17, CDU 15. Die meisten Anfragen gehen an Jugend, Schule und Soziales (2014–2020: 159,
2020–2025: 79), dann Umwelt beziehungsweise Mobilität und Umwelt (86; 65), Kultur (64; 45), Planen und
Bauen (86; 44), den Oberbürgermeister (81; 11). Ohne die niedrige Schicht des Klassifikators sind es 803
Anfragen in Zellen, mit Antwort, Fachausschuss und Klassifikator ab 0,7 718, nur mit Antwort und
Fachausschuss 713.

### 3.5 Teststärke

Simulation unter dem vorab festgelegten Modell (§ 8): das Nullmodell (nur die festen Effekte Fraktion ×
Halbjahr und Dezernatseinheit × Halbjahr) an die beobachteten Zellen angepasst, daraus je Wiederholung
neue Zahlen mit dem Effekt exp(β) auf den Zellen `partner`, Überdispersion als Negativbinomial mit θ
aus den Momenten des Nullmodells, dann das Modell mit dem quasi-Poisson-Test, einseitig bei α = 0,05.
Gemessen ist φ = 1,00 im Nullmodell (keine Überdispersion über Poisson hinaus, θ unbeschränkt). Seed 24,
400 Wiederholungen je Effektgröße. Der Schätzer (`ppml`, abwechselnde Projektionen) stimmt an einem
simulierten Satz mit der Poisson-Regression über ausgeschriebene Dummies in β und Standardfehler auf
sechs Stellen überein.

| Variante der Zuordnung | Zellen | Anfragen | IRR 1,2 | 1,25 | 1,3 | 1,4 | **1,5** | 2,0 | kleinster IRR mit ≥ 0,8 |
|---|---|---|---|---|---|---|---|---|---|
| alle Wege | 406 | 887 | 0,57 | 0,70 | 0,86 | 0,97 | **1,00** | 1,00 | 1,3 |
| ohne Klassifikator unter 0,5 | 393 | 803 | 0,50 | 0,68 | 0,81 | 0,94 | **0,99** | 1,00 | 1,3 |
| Antwort, Fachausschuss, Klassifikator ab 0,7 | 346 | 718 | 0,45 | 0,67 | 0,76 | 0,92 | **0,99** | 1,00 | 1,4 |
| nur Antwort und Fachausschuss | 343 | 713 | 0,47 | 0,61 | 0,73 | 0,90 | **0,99** | 1,00 | 1,4 |

Zellen nach Entfernen der Gruppen ohne Anfrage (davon mit Status `partner` 143, 139, 114, 112). Je Periode
allein (Nebenrechnung R3, alle Wege, IRR 1,5): 2014–2020 **0,94** (264 Zellen, 552 Anfragen), 2020–2025
**0,81** (120, 303), 2025- **0,16** (22, 32). Die vorab genannte Effektgröße ist also in jeder Variante
sichtbar; IRR 1,25 (+25 %) wäre es nicht (0,61 bis 0,70).

Größe des Tests (Anteil der Ablehnungen bei IRR 1,0): 0,06, 0,04, 0,05 und 0,03 in den vier Varianten,
nahe dem Nennwert 0,05.

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

**Codebuch** `validierung/24-kontrolle/codebuch.toml` (Fassung 2026-11-23.1): Einheit Anfrage; eine Frage
`dezernat` — „Welches Dezernat ist adressiert?", das Dezernat, in dessen Zuständigkeit nach dem
Dezernatsverteilungsplan am Datum die Beantwortung fällt, nicht der angeredete Oberbürgermeister und
nicht das Gremium. **Festes Antwortformat**: eine JSON-Zeile je Aufgabe mit `dezernat` (Code aus der
mitgelieferten Liste, `mehrere`, `keins` oder `unklar`), `weitere` (Codes bei `mehrere`), `amt`
(Amtsnummer, für die Schlichtung), `sicherheit` und `begruendung`. Die Aufgabe zeigt Nummer, Titel,
Datum, Gremium, Textanfang (3 000 Zeichen Rohtext) und die Liste der Dezernate zum Datum mit ihren Ämtern
— ohne Personen, ohne Parteien, ohne das Ergebnis des Verfahrens, den Weg und die Schicht; die
Reihenfolge der Aufgaben ist gemischt.

**Stichprobe** `validierung/24-kontrolle/stichprobe.csv`, 100 Anfragen aus den 3 476, Seed 24, geschichtet
nach dem Weg (Grundgesamtheit je Schicht in Klammern): Antwort 8 (8, alle), Fachausschuss 22 (1 873),
Amt im Text 16 (276), Klassifikator hoch 14 (30), mittel 14 (149), niedrig 14 (421), keine Zuordnung 12
(719). Die kleinen Wege sind übergewichtet, damit jeder eine eigene Präzision bekommt; die Schicht ohne
Zuordnung zeigt, was dem Verfahren entgeht.

**Aufgaben**: `/media/konrad/xtraspace/georep/messdaten/kodierung/24-kontrolle/aufgaben.jsonl` (100 Zeilen,
lokal, nie ins Repo), dazu leere `antworten-A.jsonl` und `antworten-B.jsonl`.

**Maße** (vorab, im Codebuch): Präzision je Schicht mit Wilson-Intervall, streng (ein Endlabel `mehrere`,
`keins` oder `unklar` zählt als falsch) und mild daneben (`mehrere` ist richtig, wenn das Dezernat des
Verfahrens unter den genannten ist), hochgerechnet mit den Schichtgewichten auf die zugeordneten
Anfragen; Krippendorffs α zwischen A und B. **Regel für das eingefrorene Verfahren**, vor der
Kodierung festgelegt: ein Weg oder eine Schicht des Klassifikators bleibt im Verfahren, wenn ihre
Präzision (Punktschätzer) ≥ 0,9 ist; das Kriterium gilt für die hochgerechnete Präzision der
verbleibenden Wege. Die Teststärke wird danach mit den verbleibenden Wegen neu gerechnet (§ 3.5 zeigt sie
schon für vier Varianten).

**Stand**: kodiert am 2026-11-23, Ergebnis in § 4.1.

**Was die Daten selbst schon sagen** (Labels aus den Daten, Plan § 2.6 (2); kein Ersatz für die
Kodierung): Fachausschuss und Klassifikator ab p 0,7 stimmen zu 97,0 % überein (129 von 133, zwei
unabhängige Wege); Amt im Text stimmt mit keinem anderen Weg zu mehr als 56 %. Die Erwartung ist darum:
Fachausschuss und Klassifikator hoch erreichen 0,9, Amt im Text und Klassifikator niedrig nicht.

### 4.1 Ergebnis der Kodierung (2026-11-23)

Kodiert von zwei Kodier-Agenten unabhängig nach Codebuch 2026-11-23.1, Uneinigkeiten von einem
Schlicht-Agenten entschieden; alle drei sind dasselbe Modell (Frage 19 von `fragen-2026-11.md`): die
Übereinstimmung ist ein schwacher Beleg, kein menschlicher Goldstandard. Endlabels in
`validierung/24-kontrolle/labels.csv` (Aufgabe, Frage `dezernat`, `weitere`, `amt`; Kodierer A, B,
Schlichtung, Endlabel als JSON; Einigkeit gibt das Label, sonst die Schlichtung, ohne Schlichtung bei
Uneinigkeit `null`). `amt` ist bei 6 Aufgaben `null`: dreimal von beiden Kodierern leer gelassen, zweimal
entschied die Schlichtung ohne Amt, einmal blieben die Kodierer uneins ohne Schlichtung (das Dezernat war
gleich). Gebildet und ausgewertet mit
`docs/plans/24-kontrolle-messung.py --labels` (Abschnitt 8 der Ausgabe; der Lauf bestätigt, dass die
Zuordnung die gespeicherte Stichprobe unverändert reproduziert).

**Übereinstimmung**: Dezernat 96 von 100, **Krippendorffs α (nominal) 0,954**; Amt 95 von 100. Die vier
Schlichtungen: `RAT/186/2024` → `mehrere` (07, 02; Unwetter: Feuerwehr und Stadtentwässerung),
`OVA/020/2025` → 05 (Amt 66), `RAT/165/2025` → `unklar` (öffentliche Toiletten: zuständiges Amt weder im
Text noch in der Liste), `RAT/096/2023` → 09 (Amt 54). Endlabels: 05 20, 06 18, 03 15, 04 10, 09 9, 01 7,
07 6, 08 6, 02 4, `mehrere` 4, `unklar` 1.

**`unklar` und `mehrere`** zählen, wie das Codebuch es vorab regelt (`[mass]`): streng falsch, wenn das
Verfahren ein Dezernat vergibt; `mehrere` mild richtig, wenn das Dezernat des Verfahrens unter den
genannten ist. Das einzige `unklar` (`RAT/165/2025`) liegt in der Schicht ohne Zuordnung und geht darum
in keine Präzision ein; von den vier `mehrere` liegen drei in zugeordneten Schichten (zwei Klassifikator
hoch, eines niedrig).

**Präzision je Schicht** (streng; Kriterium), mild daneben, Wilson-Intervall 95 %:

| Schicht (Weg) | Grundgesamtheit | Stichprobe | richtig streng | Präzision | Wilson 95 % | mild |
|---|---|---|---|---|---|---|
| Antwort als eigene Drucksache | 8 | 8 | 7 | 0,875 | 0,529–0,978 | 7 |
| Fachausschuss | 1 873 | 22 | 17 | **0,773** | 0,566–0,899 | 17 |
| Amt im Text | 276 | 16 | 14 | 0,875 | 0,640–0,965 | 14 |
| Klassifikator hoch (p ≥ 0,7) | 30 | 14 | 12 | 0,857 | 0,601–0,960 | 13 |
| Klassifikator mittel (0,5–0,7) | 149 | 14 | 11 | 0,786 | 0,524–0,924 | 11 |
| Klassifikator niedrig (0,3–0,5) | 421 | 14 | 5 | 0,357 | 0,163–0,612 | 5 |
| **hochgerechnet (Schichtgewichte)** | 2 757 | 88 | | **0,721** | 0,596–0,847 (normal) | |
| ohne Zuordnung | 719 | 12 | — | — | — | — |

**Je Periode** (alle zugeordneten Schichten, ungewichtet): 2014–2020 22/32 = 0,688 (Wilson 0,514–0,820),
2020–2025 35/44 = 0,795 (0,655–0,888), 2025- 9/12 = 0,750 (0,468–0,911). Keine Periode erreicht 0,9.

**Die vorab festgelegte Regel** (§ 4: eine Schicht bleibt, wenn ihr Punktschätzer ≥ 0,9 ist) **behält
keine Schicht.** Damit gibt es kein Verfahren, dessen Präzision hochzurechnen wäre, und keine Teststärke
„mit den verbleibenden Wegen". Nachträglich und ohne Wirkung auf das Urteil: auch keine Kombination der
Schichten erreicht 0,9, die besten einzelnen Schichten (Antwort, Amt im Text) liegen bei 0,875 und
decken zusammen 8 % der Grundgesamtheit.

**Fehlerbilder** (22 Fehler in den zugeordneten Schichten; die Liste mit Drucksachennummern druckt das
Skript):

- **Fachausschuss ≠ adressiertes Dezernat** (5 von 22): im Umweltausschuss nach Planung und Bau gefragt
  (`AUS/011/2020`, `AUS/007/2024` → 03), im Sportausschuss nach dem Bau einer Sportstätte
  (`SPOA/031/2021` → 03), im Personal- und Organisationsausschuss nach einer Sache des OB
  (`POA/008/2020` → 01), im Ordnungs- und Verkehrsausschuss 2018 mit Amt 66 als Geschäftsführung, aber
  einer Ordnungsfrage (`66/ 34/2018` → 07). Ein Ausschuss mit eindeutigem Dezernat seiner **Vorlagen**
  (Anteil ≥ 0,8) hat damit noch kein eindeutiges Dezernat seiner **Anfragen**: Fraktionen fragen im
  Fachausschuss quer.
- **Der Klassifikator schiebt Rat-Anfragen dem OB zu** (4 der 9 Fehler der niedrigen Schicht:
  `01/ 23/2015`, `01/ 268/2016`, `01/ 125/2019`, `001/ 26/2015` → 03, 04, 08, 02; dazu `01/ 131/2015` in
  der mittleren Schicht): Vorlagen des Amtes 01 (Ratsbüro) teilen das Vokabular des Rates, nicht den
  Gegenstand.
- **Das Gesundheitsamt wandert** (4 Fehler im Ausschuss für Gesundheit und Soziales): vakantes Dezernat 04
  bis 2021-06, Dezernat 07 bis 2025, Dezernat 09 ab 2026; der Klassifikator wählt Soziales (06), weil AGS-
  Vorlagen meist aus dem Sozialamt kommen (`AGS/029/2021`, `AGS/033/2021` → 04, `AGS/005/2023` → 07,
  `AGS/040/2026` → 09).
- **`mehrere`** (3): Querschnittsfragen (`AGS/012/2024`, `OVA/009/2024`, `RAT/186/2024`), die das Verfahren
  mit genau einem Dezernat nicht treffen kann.
- **Warum die Erwartung aus den Daten falsch war**: Fachausschuss und sicherer Klassifikator stimmten zu
  97 % überein (§ 4, „Was die Daten selbst schon sagen"), aber beide folgen dem Vokabular des Gremiums und
  der Vorlagen, nicht dem Gegenstand der Fragen; zwei Wege mit demselben Fehler bestätigen einander. Die
  Lehre gilt für jedes Vorhaben, das Labels aus den Daten als Gegenprobe nimmt (Plan § 2.6 (2)): nur
  Wege mit **verschiedener** Fehlerquelle prüfen einander.

**Die Schicht ohne Zuordnung** (12 Anfragen, fast alle im Rat): die Kodierer geben 10 davon ein einziges
Dezernat, das beste Dezernat des Klassifikators (p < 0,3) trifft keines. Dort fehlt dem Verfahren der
Gegenstand, nicht dem Material.

**Anträge in der Grundgesamtheit**: der Supervisor meldet drei der 100 Aufgaben, die keine Anfragen sind,
obwohl der Server sie als „Anfrage" führt; die Kodierer begründen es bei `OVA/152/2021` (Antrag) und
`OVA/196/2023` (Änderungsantrag). Die Regel des Skripts (Titel oder Briefkopf nennt einen Antrag) findet in
der Stichprobe drei: diese beiden und `01/ 61/2015` (Titel „Anfrage", Briefkopf „Antrag der
CDU-Ratsfraktion"). In der ganzen
Grundgesamtheit nennen 16 Titel einen Antrag, 20 Briefköpfe beginnen mit „Antrag" oder
„Änderungsantrag", zusammen **26 von 3 476 (0,7 %)**, davon 13 über den Fachausschuss zugeordnet. Für
die Zuordnung ist das ohne Gewicht; für H1 würde Stufe 2 sie über die Funktion aus Vorhaben 15
(`initiative`) ausschließen.

## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

### 5.1 Urteil nach der Kodierung (Abschluss der Stufe 1, 2026-11-23): umbauen

Maßgeblich ist der Wortlaut des Absatzes „Was entscheidet" unten (§ 5.2, vor der Kodierung geschrieben):

- „erreicht die hochgerechnete Präzision der verbleibenden Wege 0,9 … ist das Urteil bauen": **nicht
  erfüllt**, es bleibt kein Weg (§ 4.1).
- „Erreicht auch der Fachausschuss allein 0,9 nicht, heißt es **umbauen**": **erfüllt** (0,773, obere
  Wilson-Grenze 0,899).
- „**Verwerfen** nur, wenn kein Weg 0,9 erreicht": die Bedingung ist **ebenfalls erfüllt**; der Satz nennt
  eine notwendige Bedingung für Verwerfen, keine hinreichende.

Die beiden letzten Sätze überschneiden sich genau in diesem Fall, und das Dokument hat die Überschneidung
nicht geregelt. Der Mess-Agent liest den bestimmenden Satz („heißt es umbauen") vor dem einschränkenden
(„nur, wenn") und urteilt **umbauen**; ob stattdessen verworfen wird, entscheiden Supervisor und Konrad
(Frage 9.17). Für umbauen spricht in der Sache: die Frage ist kodierbar (α 0,954), die Fallzahl trägt,
und die Fehler haben benennbare Ursachen, für die es Zulieferer gibt.

**Was das heißt**:

- **Kein Stufe-2-Bau** der Zuordnung, kein Beitrag `oversight` (§ 6 und § 7 ruhen). **H1 bleibt
  ungerechnet**; sie bleibt wie vorab festgelegt (§ 8) und wird erst geprüft, wenn ein neues Verfahren das
  Kriterium erfüllt. Gerechnet mit dem heutigen Verfahren wäre sie nach § 8 „nicht entscheidbar".
- **Die Umbau-Runde** (höchstens eine, Meta-Plan § 8) misst neu, sobald mindestens einer der Zulieferer da
  ist, mit einer neuen Stichprobe von 100 Anfragen nach einem Codebuch .2 (Frage 9.13):
  1. **Antwortendes Amt aus den Antwortanlagen** (Frage 9.3; braucht Konrads Netzlauf): die einzige
     Quelle, deren Fehler nicht am Vokabular hängt; heute 7/8 richtig an den eigenen Drucksachen.
  2. **Politikfeld je Dokument (Vorhaben 19)** und daraus das Dezernat über die Zuständigkeiten, wie Block
     (2024) es über CAP-Themen tut — an den **Fragen** gemessen, nicht am Gremium.
  3. **Ergebnis im Rat und Niederschrift (Vorhaben 26)**: wer antwortet mündlich (die Schicht ohne
     Zuordnung ist fast nur Rat).
  4. Ein Klassifikator, der an **Anfragen** lernt (Labels der beiden Kodierungen) statt an Vorlagen, ohne die
     Klasse Ratsbüro; der Fachausschuss nur noch als Merkmal, nicht als Regel.
- **Was bleibt verwendbar**: die Dezernatstabelle 2014–2026 mit Quellen (§ 2.2, an den Köpfen zu 97,9 %
  bestätigt), das Codebuch, die 100 Labels (als Trainings- oder Prüfmaterial der Umbau-Runde, nicht als
  ihre Stichprobe) und der Schätzer mit Teststärke (§ 3.5).

### 5.2 Vorläufiges Urteil vor der Kodierung (unverändert, Stand `2cddab5`)

**Vorläufig: bauen, sobald die Kodierung die Präzision bestätigt.** Das Kriterium hat zwei Teile.

1. **Fallzahl: erfüllt.** Die Teststärke für den vorab genannten Effekt IRR 1,5 liegt bei 1,00 mit allen
   Wegen und bleibt bei 0,99, wenn nur Antwort und Fachausschuss bleiben; 0,8 erreicht das Modell ab IRR
   1,3 (mit allen Wegen) beziehungsweise 1,4 (nur Antwort und Fachausschuss). Je Periode allein
   (Nebenrechnung R3) tragen es nur 2014–2020 (0,94) und knapp die Hauptperiode (0,81), die laufende
   Periode nicht (0,16).
2. **Präzision ≥ 0,9: offen.** Die Kodierung steht aus. Die Daten deuten darauf, dass der Hauptweg
   (Fachausschuss, 54 % der Grundgesamtheit, 1 873 Anfragen) und der sichere Klassifikator tragen, Amt im
   Text und der unsichere Klassifikator nicht (§ 4). Selbst wenn nur Antwort und Fachausschuss
   bleiben (713 Anfragen der Mehrheit in Zellen), liegt die Teststärke bei IRR 1,5 bei 0,99 (§ 3.5).

**Was entscheidet**: erreicht die hochgerechnete Präzision der verbleibenden Wege 0,9 und die Teststärke
mit ihnen 0,8 bei IRR 1,5, ist das Urteil **bauen** (Stufe 2 nach § 6, dann die Prüfung nach § 8).
Erreicht auch der Fachausschuss allein 0,9 nicht, heißt es **umbauen**: auf 19 (Politikfeld) und 26
(Ergebnis im Rat) warten und mit ihnen neu messen. **Verwerfen** nur, wenn kein Weg 0,9 erreicht.

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

Gilt nur, wenn die Kodierung das Kriterium bestätigt (§ 5); die Wege, deren Schicht unter 0,9 bleibt,
fallen vorher heraus.

**Beitrag `oversight`** in `src/georep/enrich/oversight.py`, eingetragen in `CONTRIBUTIONS`
(`georep/enrich/__init__.py`, Punkt 69) **hinter** den Beiträgen von 11 (`sections`), 14 (`procedures`) und
15 (`functions`), deren Ausgaben er liest. Drei Schritte, alle offline:

1. `oversight_assign` liest `interim/papers.parquet`, `processed/papers_gremien.parquet`,
   `processed/dokumente_urheber.parquet`, `processed/dokumente_kopf.parquet` (11: Amt im Kopf; das
   eigene Muster des Messskripts entfällt) und `processed/vorgang_kanten.parquet` (14: Kanten vom Typ
   `antwort`). Schreibt **`processed/anfragen_dezernat.parquet`**: `id` str, `anfrage` bool, `dezernat` str
   (Code der Profiltabelle, null ohne Zuordnung), `einheit` str (Dezernat und Inhaber-Schlüssel der
   Profiltabelle), `weg` str (`antwort`, `ausschuss`, `amt_im_text`, `klassifikator`, `keins`,
   `keine_anfrage`), `wahrscheinlichkeit` f64 (nur Klassifikator), `amt` str (das Amt, über das zugeordnet
   wurde). Eine Zeile je Korpus-ID, sortiert nach `id`.
2. `oversight_cells` schreibt **`processed/kontrolle_zellen.parquet`**: `periode`, `fraktion`, `halbjahr`,
   `einheit`, `dezernat`, `fuehrt` (Fraktion oder null), `status` (`partner`, `eigen`, `andere`;
   `opposition` für Fraktionen außerhalb der Mehrheit), `anfragen` int; das volle Gitter aller Fraktionen
   der Periode × aller Einheiten im Halbjahr, Nullen eingeschlossen, sortiert nach den ersten vier
   Spalten.
3. `oversight_test` (nur mit `oversight.test = true`, das erst nach der bestandenen Validierung gesetzt
   wird) schreibt **`processed/kontrolle_test.parquet`**: je Rechnung (H1, R1 bis R5) eine Zeile mit
   `n_zellen`, `n_anfragen`, `beta`, `se`, `irr`, `irr_unten`, `irr_oben`, `p_einseitig`, `phi`,
   `entscheidung` (`bestätigt`, `widerlegt`, `nicht entscheidbar`) nach der Regel in § 8.

**Profil** (kein Stadtwort im Code): ein Block `[oversight]` in `profiles/duesseldorf.toml` mit
`[[oversight.units]]` (Dezernat, Inhaber-Schlüssel, `von`, `bis`, Ämter), `[[oversight.holders]]`
(Schlüssel, Anzeigename, Funktion, `fuehrt`, `regel`, `quelle`, `abgerufen`), `amt_patterns` (die Namen
der Ämter, wie Anfragen sie schreiben), `committee_share = 0.8`, die Schwellen des Klassifikators; die
Mehrheiten und Zeitfenster kommen aus `[[functions.majorities]]` von 15 (um `ab_halbjahr` ergänzt), die
Fraktionen aus mehreren Parteien aus 15, Frage 9.3. Settings nach der Anhängeregel: ein Modell
`OversightSettings` vor `class Settings`, ein Feld am Ende, ein Block am Ende von `defaults.toml` mit
`# --- Vorhaben 24: Anfragen als Kontrolle in der Kooperation`, `oversight.enabled = false` und
`oversight.test = false`. Der Validator des Profils prüft, dass kein Amt zugleich in zwei Einheiten
liegt, dass jeder Inhaber-Schlüssel einen Eintrag hat und dass `fuehrt` eine Partei des Profils ist (die
Prüfung `pruefe_tabelle()` des Messskripts).

**Verträge**: eine Zeile je Korpus-ID; `dezernat` ist zum Datum der Anfrage eine Einheit der
Profiltabelle; das Gitter der Zellen ist vollständig, und die Summe der Zellen ist die Zahl der
zugeordneten Anfragen mal die Zahl ihrer Fraktionen; nach jedem Join sortiert. Der Schätzer (`ppml`
des Messskripts, abwechselnde Projektionen statt Dummies) wird eine reine Funktion in
`georep.analysis` mit Vertrag (`φ ≥ 1`, `se > 0`, keine Gruppe ohne Anfrage).

**Tests**: Beispiele für `dezernat_am` an den Grenzen der Zeitscheiben, für die Regel „wer führt" in
ihrer Reihenfolge, für jeden Weg; **hypothesis** für zwei Eigenschaften, die für alle Eingaben gelten:
`ppml` stimmt mit der Poisson-Regression über ausgeschriebene Dummies in β und Standardfehler überein
(das Messskript prüft es an einem simulierten Satz, § 3.5), und nach `ohne_leere_gruppen` hat keine
Gruppe die Summe null; der Klassifikator mit einem Fake-Korpus aus drei Ämtern. Kein Netz, kein Modell.

**Berührte Dateien**: `src/georep/enrich/oversight.py` (neu), `src/georep/analysis/count_models.py`
(neu, `ppml`), `src/georep/enrich/__init__.py` (eine Zeile), `src/georep/settings.py` (Modell und
Feld), `src/georep/defaults.toml` (Block am Ende), `src/georep/profiles/duesseldorf.toml` (Tabellen),
`tests/unit/test_oversight.py`, `tests/property/test_count_models.py`, `docs/architecture.md`,
`docs/decisions.md` (Eintrag ohne Nummer), `STATUS.md`.

**Paket**: keins nötig. Alle Eingaben liegen schon in den Paketen (Korpus, Gremien, Urheber, Kopf aus
11 über den Textstore), der Klassifikator ist eine logistische Regression wie `committees` und läuft in
CI und auf Pages. Laufzeit im Messskript: rund dreieinhalb Minuten bis zur Simulation bei Lastmittel um
20, fast alles Laden, Training (7 734 Vorlagen) und Kreuzprüfung (vier Anpassungen); der Schritt
trainiert einmal ohne Kreuzprüfung. Mönchengladbach hat keine Anfragen und keinen Block
`[oversight]`: der Beitrag liefert dort keine Schritte.

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

**Abschnitt auf `akteure.html`** (die Unterseite legt 15 an): „Anfragen an die Dezernate".

- Eine Tabelle je Periode: Fraktionen (Zeilen) × Dezernate (Spalten), Zahl der zugeordneten Anfragen in
  Rat und Ausschüssen und ihr Anteil an den Anfragen der Fraktion; über jeder Spalte das Dezernat mit
  Zeitraum und „vorgeschlagen von …" (oder „parteilos, gemeinsam vorgeschlagen"), Quelle als Link. Für
  alle Fraktionen gleich gebaut, keine Rangfolge.
- Ein Satz zu H1, wie es vorab festgelegt ist: das Ergebnis (bestätigt, widerlegt, nicht entscheidbar)
  mit IRR und 95-%-Intervall; solange die Prüfung nicht gerechnet ist: „Die Hypothese ist vorab
  festgelegt und noch nicht geprüft." Alles andere heißt „explorativ".
- Validierung wörtlich: „Zuordnung zu Dezernaten geprüft von zwei KI-Kodierern an 100 Anfragen, nicht von
  Menschen; Präzision … (Intervall)". Dazu: Anfragen ohne Zuordnung (Anteil) und dass Bezirksvertretungen
  fehlen.
- **Größe**: drei Tabellen von höchstens 10 × 10 Zellen und die Dezernatsliste, geschätzt 12 bis 18 KB im
  HTML; die Unterseite bleibt unter 500 KB.
- **Tabellen im Register** (`report.tables`, über `Contribution.tables`): `kontrolle_zellen` (CSV und
  Parquet, mit `schema.json`) und `anfragen_dezernat` (nur `id`, `dezernat`, `weg`).
- **Texte**: Erklärung „Eine Anfrage nennt das Dezernat nicht; es ist über den Fachausschuss, ein Amt im
  Text, die Antwort oder einen Klassifikator erschlossen" und der Hinweis auf die Personen in öffentlicher
  Rolle (nur Funktion und vorschlagende Fraktion). `workflow-ratsmitglied.md` bekommt einen Schritt
  „Anfragen meiner Fraktion je Dezernat".

## 8. Vorab festgelegte Hypothesen (nur Analysen: Hypothese, Maß, Test, Schwelle)

Festgelegt am 2026-11-23, bevor eine Anfrage einem Dezernat zugeordnet oder eine Zelle Fraktion ×
Dezernat × Halbjahr gezählt war. Bekannt waren zu diesem Zeitpunkt nur Zahlen anderer Vorhaben, die
nicht nach Dezernat trennen: Anfragen je Fraktion und Gremium (14, § 3.7 und § 3.8) und der
Kontrollanteil je Fraktion (15, § 3.7). Die Zuordnung Anfrage → Dezernat wird in Stufe 1 gemessen und
validiert; die Hypothesen werden erst gerechnet, wenn sie das Kriterium (Präzision ≥ 0,9) erfüllt.
In Stufe 1 wird **keine** Probe der Hypothese gerechnet, auch keine vorläufige: die Daten, an denen sie
später geprüft wird, sind dieselben, und eine Probe würde aus der Prüfung eine Bestätigung des schon
Gesehenen machen (die Lektion aus Punkt 61 und aus 15, § 8).

**Bezug.** Höhmann und Sieberer (2020) zeigen für den Bundestag 1980–2017, dass Regierungsparteien mehr
Fragen an die Ministerien des Koalitionspartners richten, vor allem bei salienten und strittigen Themen,
und dass der Effekt für Fragen an eigene Ministerien und für Oppositionsparteien nicht auftritt; Höhmann
und Krauss (2022) finden mehr Fragen, je detaillierter der Koalitionsvertrag ein Thema regelt. Für
deutsche Großstädte hat Block (2024, European Political Science Review 16 (2), S. 298–314) dasselbe
Muster mit schriftlichen Anfragen in 21 Räten 2011–2020 gezeigt (Zuordnung Anfrage → Dezernat über
CAP-Themen, Mehrebenen-Negativbinomialmodell; Inzidenzratenverhältnis rund 1,5 bis 1,66 je Einheit
ideologischer Distanz), Block (2025, Government and Opposition 60, S. 517–538) für parteilose
Dezernentinnen und Dezernenten (IRR 1,15). Den Volltext von Höhmann und Sieberer konnte der Mess-Agent
nicht lesen (Bezahlschranke); die Angaben stammen aus dem Abstract und den Zusammenfassungen bei Block.

**Übertragung.** Ein Ministerium ist hier ein **Dezernat**, der Minister die Beigeordnete oder der
Beigeordnete, die Koalition die Ratsmehrheit (Kooperation 2014–2020 SPD, Grüne, FDP; 2020–2025 und ab
2025 CDU und Grüne, Belege in 15, § 3.9). Anders als im Bundestag gibt es Dezernate, die eine Person
führt, die eine **Oppositionsfraktion** vorgeschlagen hat (Beigeordnete werden für acht Jahre gewählt
und überdauern die Mehrheit) oder die parteilos ist.

### H1 (die Hauptthese, sie allein entscheidet)

> Fraktionen der Ratsmehrheit richten mehr Anfragen an Dezernate, die eine vom Kooperationspartner
> vorgeschlagene Person führt, als an Dezernate, die eine von ihnen selbst vorgeschlagene Person führt.

- **Einheit**: eine Anfrage (Rolle `anfrage` nach Vorhaben 14, `art()`), gestellt von einer Fraktion
  (`urheber_art = Fraktion`, Partei aus `parteien`; SPD und Volt sind ab 2020 eine Fraktion), in **Rat oder
  Ausschuss** (`gremium_art` `rat` oder `ausschuss`; in 2014–2020 zählen Drucksachen mit einer
  Amtsnummer als Kopf, Punkt 57, zur Stadtebene). Bezirksvertretungen und Beiräte gehören nicht zur
  Hauptprüfung: in den Bezirken gelten andere Mehrheiten (15, § 3.9). Eine gemeinsame Anfrage zählt für
  jede beteiligte Fraktion (wie Block 2024).
- **Dezernatseinheit** *d*: ein Dezernat unter einer Inhaberin oder einem Inhaber, mit dem Zuschnitt zur
  Zeit der Anfrage (Tabelle in § 2, aus dem Dezernatsverteilungsplan der Stadt). Das Dezernat des
  Oberbürgermeisters ist eine Einheit wie die anderen und zählt zur Partei des Oberbürgermeisters.
- **Wer ein Dezernat „führt"**, in dieser Reihenfolge: (1) die belegt vorschlagende Fraktion; (2) sonst
  die Fraktion, der die Kooperationsvereinbarung das Vorschlagsrecht für dieses Dezernat gibt; (3) sonst
  die belegte Parteimitgliedschaft der Person; (4) sonst „keine" (parteilos ohne belegten Vorschlag,
  gemeinsam vorgeschlagen). Die Zuordnung steht als Tabelle mit Quelle und Abrufdatum in § 2 und wird
  vor der Prüfung nicht mehr geändert; eine neue Quelle wird datiert unter § 8 nachgetragen und die
  Prüfung mit beiden Fassungen gerechnet.
- **Status** eines Paars (Fraktion *f*, Dezernatseinheit *d*): `partner`, wenn *d* von einer anderen
  Mehrheitsfraktion geführt wird; `eigen`, wenn von *f*; sonst `andere`.
- **Zeitraum**: ab dem Kalenderhalbjahr, in dem die Kooperation vereinbart ist (2014-2, 2021-1, 2025-2), bis
  zum Ende des Datensatzes (2026-10-13); Anfragen davor zählen nicht.
- **Maß**: *Y* = Zahl der Anfragen von *f*, die das validierte Verfahren (§ 3, eingefroren nach der
  Kodierung) *d* zuordnet, im Kalenderhalbjahr *h*. Anfragen, denen das Verfahren kein oder mehr als ein
  Dezernat gibt, zählen nicht.
- **Stichprobe der Prüfung**: alle Zellen (*f*, *d*, *h*) mit *f* in der Mehrheit, auch die Nullen; Zellen
  einer Gruppe *f* × *h* oder *d* × *h* ohne jede Anfrage fallen heraus (sie tragen zur Schätzung nichts bei).
- **Modell**: Poisson-Regression (Pseudo-Maximum-Likelihood) mit festen Effekten Fraktion × Halbjahr und
  Dezernatseinheit × Halbjahr, log E[*Y*] = α(*f*, *h*) + γ(*d*, *h*) + β · partner(*f*, *d*). α nimmt den
  Fleiß einer Fraktion je Halbjahr, γ die Aufmerksamkeit für ein Dezernat je Halbjahr (Ereignisse, Größe,
  Amtszeit innerhalb des Halbjahrs). β ist identifiziert nur aus Dezernaten, die eine Mehrheitsfraktion
  führt, als Vergleich der Mehrheitsfraktionen untereinander; Dezernate der Kategorie `andere` stützen nur
  die Schätzung von α. Gerechnet über alle drei Perioden zusammen.
- **Test**: einseitig, H1: β > 0, z-Test mit quasi-Poisson-Standardfehler (Überdispersion φ aus der
  Pearson-Statistik, φ ≥ 1), **α = 0,05**. Berichtet wird IRR = exp(β) mit 95-%-Intervall.
- **Vorab genannter Effekt**: **IRR = 1,5** (Partner-Dezernate bekommen anderthalbmal so viele Anfragen wie
  eigene), die Größenordnung der kommunalen Befunde bei Block (2024). Mit ihm rechnet das
  Fallzahlkriterium (§ 3): Teststärke ≥ 0,8 bei α = 0,05 einseitig, simuliert unter Überdispersion wie in
  den Daten. Daneben, nicht entscheidend, die Teststärke für IRR 1,25.
- **Entscheidung**:
  - **bestätigt**, wenn p < 0,05 (einseitig);
  - **widerlegt** (der vorab genannte Effekt ist ausgeschlossen), wenn p ≥ 0,05 und die obere Grenze des
    einseitigen 95-%-Intervalls für IRR unter 1,5 liegt;
  - **nicht entscheidbar** sonst, und immer dann, wenn die Zuordnung die Präzision 0,9 nicht erreicht hat
    oder die Teststärke für IRR 1,5 unter 0,8 liegt. Ein Ergebnis „nicht entscheidbar" steht auf der Seite
    als solches, nicht als „kein Effekt".
- **Vorab festgelegte Nebenrechnungen** (berichtet, entscheiden nicht): (R1) nur Anfragen einer einzigen
  Fraktion; (R2) mit den Bezirksvertretungen (Mehrheit der Bezirke als die des Rates genähert, wie 15);
  (R3) je Periode einzeln; (R4) Dezernat 03 ab der Wiederwahl 2024-09 als von der CDU geführt (die
  Kooperationsvereinbarung 2021 gibt ihr das Vorschlagsrecht „bei einer Neuwahl", die Ausübung ist nicht
  belegt); (R5) Negativbinomialmodell mit denselben festen Effekten statt quasi-Poisson.

### H2 (Nebenthese: strittige Themen)

> Der Partnereffekt ist größer in Dezernaten, deren Feld zwischen den Partnern strittig ist.

- **Maß der Strittigkeit**, vorab gewählt, Hauptmaß: Abstand der Partner auf der Politikdimension des
  Dezernats nach ihren Wahlprogrammen (Vorhaben 25; wie Block 2024 mit Gross und Jankowski 2020). Bis 25
  diese Positionen liefert, ist H2 **nicht entscheidbar**.
- **Ersatzmaß**, schon jetzt messbar und hiermit festgelegt: der Anteil der Anträge (Funktion
  `initiative` nach Vorhaben 15) der Mehrheitsfraktionen im Feld des Dezernats und in der Periode, die eine
  Mehrheitsfraktion **ohne** ihren Partner stellt („Alleingangsquote", Zuordnung zum Dezernat mit
  demselben Verfahren wie die Anfragen), innerhalb der Periode standardisiert.
- **Modell und Test**: H1-Modell plus Wechselwirkung partner × Strittigkeit; einseitig, Koeffizient der
  Wechselwirkung > 0, α = 0,05, quasi-Poisson. Bestätigt, widerlegt und nicht entscheidbar wie bei H1, mit
  dem Ersatzmaß nur als „Ersatzmaß bestätigt" oder „nicht bestätigt" berichtet.

### H3 (Nebenthese: Detailgrad der Vereinbarung, nach Höhmann und Krauss 2022)

> Der Partnereffekt ist größer in Dezernaten, deren Feld die Kooperationsvereinbarung ausführlicher regelt.

- **Maß**: Zahl der Wörter der Vereinbarung im Feld des Dezernats (Zuordnung der Abschnitte durch
  Vorhaben 25), je Periode standardisiert. Bis 25 die Vereinbarungen zerlegt, **nicht entscheidbar**.
- **Modell und Test** wie H2.

### Was ausdrücklich explorativ bleibt

Ob die Opposition Dezernate „ihrer" Beigeordneten schont oder stärker befragt, ob parteilose
Dezernentinnen mehr Anfragen bekommen (Block 2025), Antwortzeiten je Dezernat (14, § 8: mit dem Gremium
als Schicht und der Antwortzeit statt der Antwortquote) und alles, was erst nach der Zuordnung auffällt,
steht auf der Seite als „explorativ".

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 9.1 | Kann Konrad die unbelegten Parteien bestätigen oder korrigieren (Zuschke, Wagner, dazu Abrahams, Bonin, Rauterkus nur aus Überschriften)? | „wer führt" ist die erklärende Variable von H1; Zuschkes Dezernat 03 ist groß (§ 3.4) | Regel aus § 8; Zuschke „keine", Wagner CDU über das Vorschlagsrecht; Nebenrechnung R4 für Zuschke ab 2024-09 |
| 9.2 | Namen der Beigeordneten im Profil? Plan § 1 lässt Personen nur als Mandatsträger über OParl zu, das Briefing von 24 erlaubt Name, Amt, Zeitraum und vorschlagende Fraktion | Datenschutzlinie des Projekts | Namen im Profil und im Messdokument (öffentliche Rolle, Briefing); auf der Seite nur Dezernat, Zeitraum und „vorgeschlagen von", kein Name |
| 9.3 | Die Antwort als Anlage (14: 33 bis 56 % der Anfragen in Bezirken und manchen Ausschüssen, fast nie im Rat) liegt nur als Name vor; die PDFs sind nicht lokal. Abrufen? | Das antwortende Amt wäre die beste Zuordnung, für die Hauptprüfung aber nur bei rund jeder sechsten Ausschussanfrage | nicht in Stufe 2; eine Stichprobe von rund 50 Antwortanlagen mit Konrads Netzlauf (F6) würde zeigen, ob ihr Kopf das Amt nennt, dann als Weg `antwort_anlage` |
| 9.4 | Rat-Anfragen bleiben am häufigsten ohne Zuordnung (§ 3.3). Verzerrt das H1? | Fällt die Zuordnung je nach Status anders aus, wäre der Ausschluss nicht neutral | neutral angenommen; geprüft wird, ob der Anteil ohne Zuordnung je Fraktion der Mehrheit gleich ist (eine Zahl je Fraktion, keine nach Status) |
| 9.5 | Das Dezernat des Oberbürgermeisters zählt zur Partei des OB. Block (2024) findet, dass Dezernate der Partei des direkt gewählten Bürgermeisters mehr Fragen der anderen Kooperationspartner bekommen — das vermischt H1 mit einem Bürgermeistereffekt | 2014–2020 SPD (Geisel), ab 2020 CDU (Keller) | § 8 bleibt; eine Rechnung ohne Dezernat 01 wird als **explorativ, nachträglich** berichtet, nicht als Nebenrechnung |
| 9.6 | Die laufende Periode trägt nur rund 30 Anfragen in den Zellen der Mehrheit | R3 je Periode ist für 2025- nicht entscheidbar | gepoolt wie festgelegt; die laufende Periode prospektiv bis zum Periodenende nachrechnen |
| 9.7 | Bezirksvertretungen: Mehrheiten unbekannt, Zuordnung schwach (rund 11 %) | R2 ist kaum aussagekräftig | R2 bleibt Nebenrechnung; mit Vorhaben 27 (Mitgliedschaften) die Mehrheiten je Bezirk, dann neu |
| 9.8 | Das Ersatzmaß von H2 braucht die Zuordnung von **Anträgen** zu Dezernaten, die nicht validiert ist | H2 wäre sonst auf ungeprüfter Grundlage | vor H2 eine eigene Stichprobe von 50 Anträgen mit demselben Codebuch; ohne sie heißt H2 „nicht entscheidbar" |
| 9.9 | Köpfe neu erzeugter PDFs nennen den Dezernenten zur Zeit der Erzeugung, nicht des Dokuments (Kral auf Vorlagen von 2019, Keller als OB auf Vorlagen von 2019 und 2020) | Wer Zeiträume aus den Köpfen abläse, läge falsch | Stufe 2 liest aus dem Kopf nur das Amt, nie die Person; Zeiträume nur aus der Profiltabelle (§ 3.2) |
| 9.10 | Quasi-Poisson oder Standardfehler geclustert nach Fraktion × Dezernat? | Wenige Cluster (rund 30 Paare der Mehrheit) machen geclusterte Fehler unzuverlässig | wie festgelegt quasi-Poisson; φ ist in den Daten nahe 1 (§ 3.5) |
| 9.11 | Prüfen an den vorhandenen Daten oder nur prospektiv (wie 15, § 8, für H15.1 vorschlägt)? | 15 hat seine Zahlen schon gesehen; hier ist keine Zelle nach Status gezählt | an den vorhandenen Daten nach der Validierung, weil der Vergleich Partner gegen eigen noch von niemandem gerechnet ist; dazu prospektiv bis zum Periodenende |
| 9.12 | Gemeinsame Anfragen von CDU und Grünen (129 in der Hauptperiode) zählen für beide, einmal als Partner, einmal als eigen | Das verdünnt den Kontrast, verzerrt ihn aber nicht | wie festgelegt; R1 rechnet ohne sie |
| 9.13 | Codebuch .2 nach den Lücken der Kodierung (Vorschläge des Schlicht-Agenten, **nicht** auf das gemessene Verfahren angewandt): (a) Querschnittsfragen an das koordinierende Amt, `mehrere` nur bei getrennten Fachsachen; (b) Amt nicht im Material: Amtsbezeichnung, Weltwissen nur bei einheitlicher Zuständigkeit, sonst dasselbe Dezernat aller Kandidaten, sonst `unklar` — dazu den Aufgabengliederungsplan der Stadt ins Material; (c) Beteiligungen an die Beteiligungsverwaltung (02); (d) ÖPNV nach Bus, Schiene und Bau trennen; (e) Präfixe der Drucksachennummer und zitierte Pressemitteilungen zählen nicht; (f) Schadensereignisse: Einsatz und Schadensbild an 37, Ursachen an einer Einrichtung an deren Amt; dazu den **Fragenblock** zeigen statt der ersten 3 000 Zeichen | Die Umbau-Runde braucht ein schärferes Codebuch; (e) zeigt, dass das alte Präfix (Punkt 57) selbst die Kodierer verleiten kann | Fassung .2 mit (a) bis (f) und Fragenblock (Abschnitt `fragen` aus 11) für die Umbau-Runde |
| 9.14 | Kodierer und Schlichter sind dasselbe Modell (Frage 19) | α 0,954 kann geteilte Fehler verdecken | die Umbau-Runde mit einem zweiten Modell, wenn Frage 19 so beantwortet wird |
| 9.15 | „Anfragen", die Anträge sind (26 von 3 476, 0,7 %; 3 in der Stichprobe) | in H1 zählt nur Kontrolle | Stufe 2 schließt sie über die Funktion aus 15 aus (`kontrolle`), nicht über die Dokumentart |
| 9.16 | Labels aus den Daten als Gegenprobe: Fachausschuss und Klassifikator stimmten zu 97 % überein und lagen beide bei rund 0,77 bis 0,86 Präzision | Zwei Wege mit derselben Fehlerquelle bestätigen einander (§ 4.1) | Befund für `00-synergien-2026-11.md` und Plan § 2.6 (2): eine Gegenprobe aus den Daten zählt nur zwischen Wegen mit verschiedener Fehlerquelle |
| 9.17 | Umbauen oder verwerfen? § 5 regelt den Fall „kein Weg erreicht 0,9" doppelt (§ 5.1) | Das Urteil hängt an der Lesart | umbauen (der bestimmende Satz vor dem einschränkenden); Supervisor und Konrad können verwerfen |

**Was Vorhaben 27 ergänzt**: die Fragestellerin oder den Fragesteller als Person (Mitgliedschaften aus
F6), damit (a) die Mehrheiten der Bezirksvertretungen und damit R2, (b) die Frage, ob Mitglieder des
Fachausschusses ihr Dezernat befragen oder fachfremde (Arbeitsteilung in der Fraktion), (c) ob
Fraktionsvorsitzende häufiger den Partner befragen als Fachpolitiker. Vorhaben 26 (`agendaItem.result`,
Niederschriften) bringt die mündlichen Antworten im Rat und damit einen Weg für die Rat-Anfragen, die
heute am häufigsten ohne Zuordnung bleiben; Vorhaben 19 (Politikfeld) einen fünften Weg der Zuordnung
und das Feld für H2 und H3.

**Risiken**: Die Kodier-Agenten sind sich bei „welches Dezernat" uneins, wo Ämter wandern (Ordnungsamt
2023-08 bis 2024-08 bei Dezernat 08, Feuerwehr dreimal umgehängt) — das Codebuch gibt darum die Liste
der Dezernate zum Datum mit. Parteipolitische Schlagseite: die Seite zeigt alle Fraktionen gleich und
nennt Personen nicht. Ein Effekt kann auch umgekehrt laufen (Mehrheitsfraktionen schonen den Partner
öffentlich und klären intern, Block 2025 für parteilose Dezernate); der Test ist einseitig, ein negatives
β heißt „nicht bestätigt", nicht „umgekehrt bestätigt".

## 10. Änderungen durch die Synergie (füllt der Supervisor)

—
