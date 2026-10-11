# Plan 05: Gremien

Stand 2026-10-12, Branch `feat/05-gremien`. Status: im Review (umgesetzt am 2026-10-12).

Briefing: [../plan-ausbau-2026-10.md](../plan-ausbau-2026-10.md), § 7.5; Regeln § 2; Vorlage § 8.3. Dieser
Plan ist so geschrieben, dass ein frischer Agent ihn nach der Synergiephase ohne Rückfragen umsetzen kann:
Datenlage mit nachgemessenen Zahlen, Entscheidungen mit verworfenen Alternativen, Berührungspunkte als Dateien
und Funktionen, Stufen mit Abnahmekriterien und Aufwand. Arbeitsregeln (Commits, nox, Verträge, nie unter
`reference/` schreiben) stehen in [../../CLAUDE.md](../../CLAUDE.md), der Aufbau in
[../architecture.md](../architecture.md). Die Erkundung lief im Scratchpad auf der Referenz und auf der
Mini-Fixture (`georep --settings <datei> bootstrap && run` in einen Scratchpad-`data_root`); nichts davon
liegt im Worktree.

## 1. Ziel und Nicht-Ziel

**Ziel.** Jedes der 19 108 Ratsdokumente bekommt aus seiner Drucksachennummer (`reference`, zum Beispiel
`BV6/108/2023`, `RAT/270/2023`, `OVA/117/2023/1`) ein Gremium: den Rat, eine der zehn Bezirksvertretungen (mit
der Nummer des Stadtbezirks), einen Ausschuss, einen Beirat oder „unbekannt". Daraus entstehen je Wahlbezirk
die Kennzahlen „Treffer aus der eigenen Bezirksvertretung", „aus anderen Bezirksvertretungen", „aus dem Rat",
„aus Ausschüssen", „aus Beiräten", „unbekannt", als absolute Zahl und als Anteil an allen Treffern des Bezirks,
dazu die Quote „Treffer der eigenen Bezirksvertretung je Wahlberechtigtem". Die Zuordnung Wahlbezirk zu
Stadtbezirk kommt aus dem Wahlergebnis je Stimmbezirk, gewichtet über die Wahlberechtigten, mit Vertrag. Die
Berichtsseite bekommt einen Abschnitt „Gremien" (Tabelle je Wahlbezirk, Tabelle je Gremium, Methode), und die
Karte einen dritten Umschalter „Anteil eigene Bezirksvertretung" neben Trefferquote und Wahlbeteiligung. Drei
neue Tabellen stehen zum Download. Alle Muster und Namen der Gremien stehen in den Settings, nichts davon im
Code.

Als Nebenprodukt, weil es dieselbe Datei und dieselben Regeln sind: eine Spalte `herkunft` je Dokument aus
`paper_type` (Verwaltung, Fraktion, Bürger, unbekannt). Sie bekommt keine eigene Kennzahl und keine Karte;
Option 4 (Parteien) und Option 6 (Gewicht je Dokumentart) können sie nutzen.

**Nicht Ziel.** Kein Netzabruf: die Gremien kommen aus der Drucksachennummer, nicht aus OParl-`consultation`
(§ 2, Entscheidung 1). Keine Änderung an `wahlbezirke_auswertung.parquet` (Golden Master der Arbeit bleibt
byteidentisch). Keine Personen oder Fraktionen als Urheber (Option 4). Kein Umschalter in `karte.html`
(Leaflet; bleibt bei der Trefferquote). Keine Veröffentlichung der Zuordnung je Dokument als CSV (2,3 MB für
eine Spalte, die aus `drucksache` in `dokumente.json` und der dokumentierten Regel folgt). Keine
Zeitreihe je Gremium (Option 2 und 7).

## 2. Entscheidungen (mit verworfenen Alternativen und Kosten)

| Frage | Entscheidung | Warum, und was verworfen wurde |
|---|---|---|
| 1. Quelle des Gremiums | die Drucksachennummer (`reference`), geparst nach einem Muster aus den Settings; `paper_type` nur für die Herkunft | Alle 19 108 Nummern der Referenz folgen `KÜRZEL[NR]/lfd. Nr./Jahr[/Nachtrag]`, 0 fallen heraus (§ 3). Verworfen: `paper_type` als Gremium (nur 4 173 Dokumente tragen „Bezirksvertretung" im Typ, 6 847 BV-Dokumente heißen „Antrag", „Anfrage", „Beschlussvorlage"; 21 ABA-Dokumente heißen fälschlich „Bezirksvertretung Informationsvorlage"). Verworfen für jetzt: OParl-`consultation[].organization` (genau, auch mehrere Gremien je Vorlage; `tests/fixtures/oparl/papers_page.json` zeigt es, die Referenz der Arbeit hat es nicht; braucht einen neuen Metadaten-Abruf von Stunden, den Option 4 vorbereitet). Der Parser bleibt der Offline-Weg und der Fallback. |
| 2. Klassen | `rat`, `bezirksvertretung` (mit `stadtbezirk`), `ausschuss`, `beirat`, `unbekannt`; Kürzel explizit in Settings-Tabellen, alles andere ist `unbekannt` | Ein Kürzel, das in keiner Tabelle steht, soll auf der Seite als „unbekannt" mit Anteil erscheinen, statt stillschweigend Ausschuss zu heißen (neue Gremien in Option 7, andere Städte in Option 1, ältere Perioden in Option 2). Verworfen: „alles, was nicht Rat und nicht BV ist, ist Ausschuss" (0 % unbekannt auf jeder Eingabe, also keine Aussage). Beiräte (Jugendrat, Integrationsrat, Seniorenrat, Behindertenrat, 448 Dokumente) sind keine Ausschüsse des Rates; sie bleiben eine eigene Klasse in der Tabelle, nicht auf der Karte. |
| 3. „Verwaltung" | keine Gremium-Klasse, sondern die Herkunft aus `paper_type`: `verwaltung` (…vorlage, …beschluss), `fraktion` (Antrag, Anfrage, Haushaltsantrag), `buerger` (Eingabe nach § 24 GO), `unbekannt` | Das Briefing nennt Verwaltung neben Rat und Bezirksvertretung; in den Daten ist sie aber eine zweite, unabhängige Dimension (eine Beschlussvorlage der Verwaltung geht an eine BV, einen Ausschuss oder den Rat; Kreuztabelle in § 3). Regeln als Teilstrings in Settings-Reihenfolge, erste Übereinstimmung gewinnt; 0 unbekannt auf der Referenz. Verworfen: die Herkunft an Option 4 oder 6 abzugeben (sie brauchen sie beide; hier kostet sie eine Spalte und drei Settings-Zeilen). |
| 4. Zuordnung Wahlbezirk zu Stadtbezirk | aus der Wahlergebnis-CSV je Stimmbezirk (`Kommunalwahlbezirk`, `Stadtbezirk`, `Wahlberechtigte_insgesamt`), Gewicht = Anteil der Wahlberechtigten; alle Stadtbezirke mit Gewicht > 0 sind „eigene" | Die CSV hat, anders als das GeoJSON, die Wahlberechtigten und stimmt im Feld Stadtbezirk mit `Stadtbezirk Nr.` des GeoJSON für alle 306 Stimmbezirke überein (nachgesehen 2026-10-11); `read_results_csv` liest sie schon. 40 von 41 Wahlbezirken liegen in genau einem Stadtbezirk; Wahlbezirk 40 (Urdenbach, Garath Kämpenviertel) zu 64,7 % in 9 und 35,3 % in 10. Verworfen: nur der Hauptstadtbezirk zählt (mehrheitlich): dann gelten die 293 BV10-Treffer von Wahlbezirk 40 als „fremd" und nur 152 BV9-Treffer als „eigen", Anteil 0,26 statt 0,77, und die BV 10 bekäme in der Lokalitätstabelle 44 % statt rund 75 %. Verworfen: gewichtete Bruchzahlen je Dokument (schwer erklärbar, betrifft einen Bezirk). Verworfen: Zählen der Stimmbezirke im GeoJSON (gleiche Entscheidung für Wahlbezirk 40: 5 zu 3, aber ohne Wahlberechtigte). Die Gewichte werden veröffentlicht; Wahlbezirk 40 bekommt auf der Seite eine Fußnote. |
| 5. Kennzahl auf der Karte | `anteil_eigene_bv` = Treffer aus der eigenen Bezirksvertretung geteilt durch alle Treffer des Bezirks, fünf Quantilklassen wie die anderen beiden, dieselbe Blau-Rampe | Dimensionslos, 41 verschiedene Werte (0,227 bis 0,743), erzählt „wie lokal ist die Aufmerksamkeit". Verworfen als Kartenkennzahl: `quote_eigene_bv` je Wahlberechtigtem (korreliert mit der Trefferquote, erzählt dasselbe wie die erste Karte) und `anteil_rat` (Median 0,038, Spannweite bis 0,158 fast nur durch Bezirk 1). Beide stehen in der Tabelle. |
| 6. Regression | ein Satz auf der Seite: `regress(…, x="quote_eigene_bv")` über die bestehende Funktion, p im Text, keine Tabelle | Auf der Referenz r = 0,20, p = 0,22 (`anteil_eigene_bv`: r = −0,02, p = 0,90). Die Abstraktion „Kennzahlvariante mit eigener Regression" gehört Option 3 und 6 (Synergiephase); hier nur der vorhandene `x`-Parameter. |
| 7. Schritte und Dateien | zwei neue Offline-Schritte `bodies` (Korpus zu `processed/papers_gremien.parquet`) und `body_hits` (Auswertung plus Zuordnung zu `processed/wahlbezirke_gremien.parquet` und `processed/gremien.parquet`); der Schritt `voters` schreibt zusätzlich `processed/wahlbezirke_stadtbezirke.parquet` | Dieselbe Körnung wie `corpus`, `index`, `results`: der Parser ist für sich profilierbar (`georep profile bodies`), die Aggregation hängt an `results`. Die Zuordnung gehört zu `voters`, weil dort die CSV schon gelesen wird; Option 3 bekommt daneben die Stadtteile. Verworfen: ein einziger Schritt mit drei Ausgaben (geht, verwischt aber die Abhängigkeit); Spalten an `wahlbezirke_auswertung.parquet` anhängen (ändert den Golden Master und die veröffentlichte Tabelle); alles im Schritt `report` rechnen (nicht als Parquet nachnutzbar). |
| 8. Veröffentlichung | drei neue Tabellen in `site/data/` als Parquet und CSV: `wahlbezirke_gremien`, `gremien`, `wahlbezirke_stadtbezirke`; `papers_gremien` bleibt unter `processed/` (nicht veröffentlicht) | Die drei sind klein (zusammen unter 20 KB) und tragen das Ergebnis. `papers_gremien` ist je Dokument aus `drucksache` und der Regel ableitbar; als CSV 2,3 MB (§ 3). Verworfen: Parquet ohne CSV für diese eine Tabelle (bricht die Regel „jede Tabelle in beiden Formaten"). |
| 9. Namen der Gremien | Kürzel zu Name in Settings-Tabellen mit Quelle je Zeile; Kürzel ohne gesicherten Namen stehen ohne Namen, die Seite zeigt dann das Kürzel | Am 2026-10-11 hat eine Seite von `…/bodies/0015/organizations` (die eine erlaubte Formatprüfung) gezeigt: `shortName` ist genau das Drucksachen-Kürzel (BV8, GLA, ADIG, AUS, AÖE, AWIR, AWIZ, SENR, INTR), `classification` ist `Bezirk`, `Ausschuss`, `Gremium` oder `Fraktion`, und Namen ändern sich innerhalb der Periode (ADIG am 2024-09-19 umbenannt, AWIZ nur bis 2021-03-18, dann AWIR). Verworfen für jetzt: die Namen aus `organizations` zu laden (Netz; Option 4 holt die Organisationen ohnehin, dann ersetzt der Abruf die Tabelle, Kürzel bleiben der Schlüssel). |
| 10. Form des Parsers | reine Funktion `parse_reference(reference, rules) -> BodyRef` auf einem vorkompilierten `BodyRules`-Objekt aus den Settings; Frame-Funktion darüber | Reine Funktionen bekommen `deal.pure`, `deal.cases` und hypothesis; die Frame-Funktion die Batch-Verträge. Verworfen: Polars-`str.extract` als zweite Implementierung des Musters (zwei Wahrheiten). 19 108 Aufrufe kosten nach Prototyp unter 0,1 s. |
| 11. Settings-Fingerprint | die neuen Schlüssel zählen zum Fingerprint; alle Stamps werden beim ersten Lauf ungültig („Settings geändert"), der volle Offline-Lauf dauert 7 s | Richtig so: die Muster beeinflussen Ergebnisse. Keine Ausnahme im `exclude` von `fingerprint()`. |

## 3. Datenlage (Stand 2026-10-11, nachgesehen mit Polars und `ls -l`)

### 3.1 Korpus `interim/papers.parquet`

19 108 Zeilen, 15 677 746 Bytes (Referenz nach `georep run`). Spalten: `id` String (OParl-URL), `name`
String, `reference` String, `date` Date, `paper_type` String, `main_file` String, `file_name` String,
`download_url` String, `text` String. `reference` und `paper_type` sind nie null und nie leer; `reference`
ist eindeutig (19 108 verschiedene Werte).

**Form der Drucksachennummern** (Buchstaben zu A, Ziffern zu 9 verdichtet):

| Form | Anzahl | Beispiele | Bedeutung |
|---|---|---|---|
| `A9/9/9` | 10 955 | `BV6/108/2023`, `BV10/107/2023` | Bezirksvertretung mit Stadtbezirksnummer, laufende Nummer, Jahr |
| `A/9/9` | 7 962 | `RAT/270/2023`, `KUA/015/2024`, `AÖE/050/2023` | Rat, Ausschuss oder Beirat |
| `A/9/9/9` | 147 | `OVA/117/2023/1`, `RAT/293/2023/1` | Nachtrag `/1`, `/2` (175 mal `/1`, 13 mal `/2` über beide Formen) |
| `A9/9/9/9` | 41 | `BV7/233/2022/1` | Nachtrag bei einer Bezirksvertretung |
| `A9/9/9-9` | 2 | `BV10/104/2020-2`, `BV9/163/2022-1` | Nachtrag mit Bindestrich |
| `A9/9/9/-9` | 1 | `BV10/149/2022/-1` | Nachtrag mit Schrägstrich und Minus |

18 919 Nummern haben drei Segmente, 189 vier. Kein Präfix ist rein numerisch; das Beispiel `11/3/2019` aus
dem Briefing kommt im Korpus nicht vor (es wäre „unbekannt"). Das Jahressegment ist 2020 bis 2025 und einmal
2026 (`KUA/022/2026`, Dokument vom 2023-12-11, offenbar ein Tippfehler der Quelle; der Parser liest das Jahr
nicht aus, es stört nicht). Das Muster
`^(?P<code>[A-ZÄÖÜ]+?)(?P<number>\d{1,2})?/\d+/\d{4}(?:[/-].*)?$` trifft alle 19 108; `code` ist das Kürzel,
`number` die Stadtbezirksnummer der Bezirksvertretungen; `bv1/1/2020`, `BV/1/2020` und `11/3/2019` treffen
nicht oder landen ohne Tabelle in „unbekannt".

**Kürzel** (38, mit Dokumenten und davon mit mindestens einem Treffer in irgendeinem Wahlbezirk):

| Klasse | Kürzel: Dokumente / mit Treffer | Summe |
|---|---|---|
| `bezirksvertretung` | BV1 1 383/1 027, BV2 1 194/789, BV3 794/640, BV4 939/684, BV5 965/731, BV6 1 098/796, BV7 1 148/914, BV8 1 250/991, BV9 1 276/828, BV10 952/514 | 10 999 (57,6 %) / 7 914 |
| `rat` | RAT 2 301/658 | 2 301 (12,0 %) / 658 |
| `ausschuss` | OVA 752/476, KUA 617/326, APS 569/455, JHA 511/250, SCHUA 439/181, AGS 318/44, SPOA 311/146, AUS 296/81, AÖE 275/91, AWM 196/42, SEBD 189/94, ADIG 170/12, HFA 155/22, GLA 149/20, ABA 138/58, AWIR 114/32, BAU 94/45, RPAU 31/1, WALTW 21/0, AWIZ 10/2, WABTW 3/0, AWTL 1/0, WPA 1/0 | 5 360 (28,1 %) / 2 378 |
| `beirat` | JURAT 190/56, INTR 165/20, BR 66/18, SENR 27/7 | 448 (2,3 %) / 101 |
| `unbekannt` | keines | 0 (0,0 %) |

Namen, mit Quelle: aus der OParl-`organizations`-Seite vom 2026-10-11: BV1 bis BV10 „Bezirksvertretung n",
GLA „Ausschuss für Gleichstellung und Antidiskriminierung", ADIG „Ausschuss für Digitalisierung und
allgemeine Verwaltungsorganisation" (bis 2024-09-19, danach „…, Personal und Organisation"), AUS „Ausschuss
für Umwelt-, Klima- und Verbraucherschutz", AÖE „Ausschuss für öffentliche Einrichtungen, Stadtökologie,
Abfallmanagement und Bevölkerungsschutz", AWIR „Ausschuss für Wirtschaftsförderung, internationale und
regionale Zusammenarbeit", AWIZ „Ausschuss für Wirtschaftsförderung und internationale Zusammenarbeit"
(2020-11-01 bis 2021-03-18), SENR „Seniorenrat", INTR „Integrationsrat". Aus Dokumenttiteln
(„Sitzungstermine des …"): OVA „Ordnungs- und Verkehrsausschuss", APS „Ausschuss für Planung und
Stadtentwicklung", BAU „Bauausschuss", SPOA „Sportausschuss", ABA „Anregungs- und Beschwerdeausschuss",
RPAU „Rechnungsprüfungsausschuss", JURAT „Jugendrat", BR „Behindertenrat". Ohne gesicherten Namen (nur
plausibel, bleiben in den Settings ohne Namen, bis Frage 2 beantwortet ist): KUA, JHA, SCHUA, AGS, AWM, SEBD,
HFA, WALTW, WABTW, WPA, AWTL. RAT heißt „Rat".

**`paper_type`**: 39 Werte. Die häufigsten: Beschlussvorlage 4 001, Antrag 3 321, Bezirksvertretung
Informationsvorlage 2 699, Anfrage 2 353, Bezirksvertretung Beschlussvorlage 1 474, Informationsvorlage 1 327,
dann Anfragen und Anträge mit Fraktionsnamen (Anfrage SPD 360 bis zAnfrage REP 2), Berichtsvorlage 177, A+F
Beschluss 145, Haushaltsantrag … (CDU/Grüne 118, Die Linke 87, SPD 64, FDP 55, Die Partei-KlimaFraktion 13,
AFD 2), Bedarfsbeschluss 78, Eingabe nach 24GO 73 und Eingabe nach 24 GO 51, Beschlussvorlage RPA 32.
Herkunft nach den Regeln aus § 5 Stufe A: `verwaltung` 9 933 (52,0 %), `fraktion` 9 051 (47,4 %), `buerger`
124 (0,6 %), `unbekannt` 0. Kreuztabelle Herkunft gegen Klasse: Verwaltung 5 697 BV, 3 489 Ausschuss, 601
Rat, 146 Beirat; Fraktion 5 291, 1 758, 1 700, 302; Bürger 11, 113, 0, 0.

### 3.2 Zuordnung Wahlbezirk zu Stadtbezirk

- `external/Stimmbezirke_2025.geojson`: 7 927 291 Bytes (so in `reference/external/`, mit Einzug), 306
  Features, `crs` `urn:ogc:def:crs:EPSG::4647`. Eigenschaften je Feature: `Stimm-/ Wahlbezirk` (String, z. B.
  `1302`), `Kommunalwahlbezirk Nr.` (Int), `Kommunalwahlbezirk Name`, `Stadtteil Nr.` (Int), `Stadtteil Name`,
  `Stadtbezirk Nr.` (Int, 1 bis 10), `Bundestagswahlkreis Nr.` und `Name`, `Landtagswahlkreis Nr.` und `Name`,
  `BezirksZuordnungen — Zuordnung_Briefwahlbezirk`. 40 von 41 Wahlbezirken liegen in genau einem
  Stadtbezirk; Wahlbezirk 40 hat 5 Stimmbezirke in Stadtbezirk 9 und 3 in Stadtbezirk 10. Stadtbezirk zu
  Wahlbezirke: 1: 1 bis 6; 2: 7 bis 10; 3: 11 bis 18; 4: 19 bis 21; 5: 22, 23; 6: 24 bis 27; 7: 28 bis 30;
  8: 31 bis 34; 9: 35 bis 40; 10: 40, 41.
- `external/Stimmbezirk_Wahlergebnis.csv`: 65 982 Bytes, latin-1, `;`, 467 Datenzeilen = 306 Stimmbezirke
  plus 161 Briefwahlbezirke mit 0 Wahlberechtigten (`gebietnr` vierstellig). Spalten unter anderem
  `gebietnr`, `Kommunalwahlbezirk`, `Stadtbezirk`, `Stadtteil`, `Wahlberechtigte_insgesamt`, `Waehler`; alle
  als Text gelesen (`read_results_csv`). `Stadtbezirk` stimmt für alle 306 Stimmbezirke mit
  `Stadtbezirk Nr.` des GeoJSON überein; `Kommunalwahlbezirk` ebenso mit `Kommunalwahlbezirk Nr.`. Gewichte
  für Wahlbezirk 40: Stadtbezirk 9 mit 8 136 von 12 566 Wahlberechtigten (0,647), Stadtbezirk 10 mit 4 430
  (0,353); alle anderen Wahlbezirke Gewicht 1,0. Die Summe je Wahlbezirk ist 1 (geprüft).
- Mini-Fixture (`tests/fixtures/mini/external/`): 34 Datenzeilen, Wahlbezirk 1 → Stadtbezirk 1, 10 → 2, 38 →
  9, also kein Mehrfachfall; 22 Stimmbezirke im GeoJSON.

### 3.3 Auswertung und Prototyp der Kennzahlen

- `processed/wahlbezirke_auswertung.parquet`: 41 Zeilen, 135 841 Bytes; `wahlkreis_id` Int64, `suchbegriffe`
  List(String), `paper_ids` List(String), `anzahl_treffer` Int64, `Wahlberechtigte_insgesamt`, `Waehler`,
  sechs `<Partei>_Stimmen` Int64, `wahlbeteiligung` Float64, sechs `<Partei>_anteil` Float64, `trefferquote`
  Float64. Die `paper_ids` ergeben 29 573 Dokument-Bezirk-Paare über 11 051 Dokumente.
- Prototyp (Scratchpad, Regeln wie § 5 Stufe A, „eigene" nach Entscheidung 4): die Summe der sechs Klassen
  ist in allen 41 Bezirken gleich `anzahl_treffer`. `anteil_eigene_bv` liegt zwischen 0,227 (Bezirk 17) und
  0,743 (Bezirk 41), Median 0,485, 41 verschiedene Werte (mit Mehrheitszuordnung hätte Bezirk 40 den Wert
  0,263, mit Entscheidung 4 rund 0,77). `anteil_rat` zwischen 0,013 und 0,158 (Bezirk 1), Median 0,038.
  Beispiele: Bezirk 1: 1 894 Treffer, 599 eigene BV, 261 andere BV, 300 Rat; Bezirk 38: 316, 193, 15, 12.
  Lokalität je Bezirksvertretung (Anteil ihrer Treffer in Wahlbezirken des eigenen Stadtbezirks, bei
  Mehrheitszuordnung): 61,8 % (BV6) bis 84,1 % (BV3); BV10 43,6 % nur wegen Wahlbezirk 40.
- Mini-Fixture (200 Dokumente): BV 93, Ausschuss 86, Rat 16, Beirat 5, unbekannt 0; Herkunft 128/63/9/0.
  Je Wahlbezirk (Treffer, eigene BV, andere BV, Rat): 1: 96, 26, 14, 11; 10: 63, 22, 11, 5; 38: 14, 9, 0, 0.
  Der Bezirk 38 hat also 0 Rats-Treffer, und keine Klasse ist in allen drei Bezirken leer; drei verschiedene
  Anteile ergeben drei Klassen.
- Größen der neuen Dateien (Prototyp, zstd wie `georep.io.write_parquet`): `papers_gremien.parquet` 125 979
  Bytes (CSV 2 302 319), `wahlbezirke_gremien.parquet` 5 931 (11 Spalten), `gremien.parquet` 2 025 (CSV 850);
  `wahlbezirke_stadtbezirke.parquet` unter 3 KB (42 Zeilen).

### 3.4 OParl als Vergleich

`tests/fixtures/oparl/papers_page.json` (sechs echte Paper vom 2026-10-09): jedes hat
`consultation[].organization` als Liste von URLs (`…/organizations/gr/35`), je ein Gremium pro Beratung, und
`reference` plus `paperType` wie im Korpus; `originatorOrganization`, `underDirectionOf`, `originatorPerson`
sind dort null. Die Seite `…/bodies/0015/organizations` (2026-10-11, einmal gelesen) liefert je Organisation
`shortName`, `name`, `classification` (`Bezirk`, `Ausschuss`, `Gremium`, `Fraktion`), `startDate`, `endDate`.
Herkunft und Lizenz: Ratsinformationssystem der Landeshauptstadt Düsseldorf; die Seite nennt wie bisher nur
Kennungen, Kürzel und Namen von Gremien (keine Personen).

## 4. Berührungspunkte im bestehenden Code (Datei, Funktion, was sich ändert)

| Datei | Funktion oder Stelle | Änderung |
|---|---|---|
| `src/georep/defaults.toml` | neue Tabelle `[bodies]` mit `reference_pattern`, `district_body`, `[bodies.council]`, `[bodies.committees]`, `[bodies.advisory]` (Kürzel → Name, Kommentar mit Quelle je Zeile), `[[bodies.origin]]` (Herkunftsregeln in Reihenfolge); `[columns.results]` bekommt `city_district = "Stadtbezirk"` | alles Düsseldorf-Spezifische dieser Option steht hier |
| `src/georep/settings.py` | neue Modelle `Bodies`, `OriginRule`; `Settings.bodies`; `ResultsColumns.city_district`; Validatoren: Muster kompiliert und hat die Gruppen `code` und `number`, Kürzel in den drei Tabellen disjunkt, `district_body` in keiner Tabelle, Herkunftsnamen eindeutig | `fingerprint()` sieht die neuen Felder automatisch |
| `src/georep/prep/bodies.py` (neu) | `BodyRef`, `BodyRules.from_settings`, `parse_reference`, `origin_of`, `classify_papers`, `BODIES_COLUMNS`, `BODIES_SCHEMA_VERSION`, `KINDS`, `ORIGINS` | Parser als reine Funktion, Frame-Funktion mit Verträgen |
| `src/georep/prep/crosswalk.py` (neu) | `unit_weights(results, columns, unit_column, name)` | Gewichte je (Wahlbezirk, Einheit) aus den Wahlberechtigten; generisch für Stadtbezirk (hier) und Stadtteil (Option 3) |
| `src/georep/analysis/bodies.py` (neu) | `hits_by_body`, `documents_by_body`, Spaltennamen als Konstanten | Kennzahlen je Wahlbezirk und je Gremium |
| `src/georep/contracts.py` | neue Prädikate `shares_in_unit_interval(frame, *columns)`, `parts_sum_to(frame, parts, total)` | dieselbe Eigenschaft heißt überall gleich |
| `src/georep/layout.py` | Properties `papers_bodies` (`processed/papers_gremien.parquet`), `district_bodies` (`processed/wahlbezirke_gremien.parquet`), `bodies_table` (`processed/gremien.parquet`), `district_units` (`processed/wahlbezirke_stadtbezirke.parquet`) | |
| `src/georep/pipeline.py` | `build_steps`: `voters()` schreibt zusätzlich `district_units` (zweite Ausgabe des Schritts); neue Schritte `bodies` (Eingabe `corpus`, Ausgabe `papers_bodies`, Schema-Version aus `prep.bodies`) und `body_hits` (Eingaben `results`, `papers_bodies`, `district_units`; Ausgaben `district_bodies`, `bodies_table`); Schritt `report` bekommt `district_bodies`, `bodies_table`, `district_units` als Eingaben | Offline-Schritte 9 → 11, Schritte insgesamt 14 → 16 |
| `src/georep/export.py` | `csv_plan`: vier Einträge dazu (`district_units`, `papers_bodies`, `district_bodies` mit `stadtbezirke` als `; `-Liste, `bodies_table`) | `georep export` schreibt 11 statt 7 CSV-Dateien |
| `src/georep/report/model.py` | `DistrictRow.bodies: DistrictBodies \| None = None` (neues Feld mit Default am Ende, Tests bauen `DistrictRow` positional); neue dataclasses `DistrictBodies`, `BodyRow`, `BodyFigures`; `ReportModel.bodies`, `.body_figures`, `.body_regression`; `published_tables` + 3; `COLUMN_DOCS` + 3 Tabellen; `build_report_model` liest die drei Parquet-Dateien; `district_rows` bekommt den Frame `district_bodies` | der Test „jede Spalte hat eine Beschreibung" greift automatisch |
| `src/georep/report/charts.py` | `choropleth(…, bodies: Classification \| None = None)` schreibt `data-class-bodies`; `district_attributes` ergänzt `data-own` („599 (31,6 %)"); `own_share_label` | der Umschalter tauscht wie bisher nur Klassen |
| `src/georep/report/render.py` | `Visuals.bodies_legend` | |
| `src/georep/report/build.py` | `DESCRIPTIONS` + 3; `build_site`: dritte `classify`, Legende, `Visuals`; `write_tables` unverändert (läuft über `published_tables`) | |
| `src/georep/report/templates/report.html.j2` | drittes Radio `value="bodies"`, `#legend-bodies`, Tooltip-Zeile aus `data-own`, Abschnitt `#gremien` (Einleitung mit Anteilen je Klasse und Anteil „unbekannt", Tabelle je Wahlbezirk, Tabelle je Gremium, Fußnote Wahlbezirk 40, Methode), Umschalter-JS liest `getAttribute("data-class-" + metric)` statt zweier Zweige | `index.html` um rund 18 KB |
| `noxfile.py` | `VERIFY_TARGETS` + `georep.prep.bodies.origin_of` (und `parse_reference`, falls crosshair mit `re` zurechtkommt, sonst mit Begründung nicht) | |
| `tests/unit/test_cli.py` | „5 übersprungen, 9 geplant" → „11 geplant", „9 ausgeführt" → „11 ausgeführt", `out.count("function calls") == 9` → 11, „7 CSV-Dateien" → „11 CSV-Dateien" | bewusst, mit Diff |
| `tests/unit/__snapshots__/test_cli.ambr` | `georep steps` mit den zwei neuen Schritten und den neuen Eingaben von `report` | Snapshot bewusst erneuern, Diff lesen |
| `tests/golden/test_pipeline.py` | 9 → 11 Offline-Schritte, Nachfolger-Kette (`pois` geändert zieht `body_hits` und `report` nach, `bodies` nicht), `site/data` 15 → 21 Dateien; slow-Test prüft zusätzlich die Zahlen aus § 3.3 (BV 10 999, RAT 2 301, unbekannt 0, Summen je Bezirk, Gewichte von Wahlbezirk 40) und 306/306 Übereinstimmung CSV gegen GeoJSON | Golden Master der neuen Schritte, eingefroren aus dem Prototyp |
| `tests/unit/test_report_build.py` | 15 → 21 Dateien | |
| `tests/unit/test_report_charts.py`, `test_report_render.py`, `test_report_model.py` | dritter Umschalter, `data-class-bodies`, Legende, Abschnitt, Escaping eines Gremiennamens mit `<`, Modellzahlen gegen Polars | |
| `tests/bench/` | zwei Benchmarks: `classify_papers` (200 Dokumente), `hits_by_body` (Mini) | der erste Lauf legt nur ihre Baseline an |
| neu: `tests/unit/test_bodies.py`, `tests/unit/test_crosswalk.py`, `tests/unit/test_analysis_bodies.py`, `tests/property/test_bodies_props.py`; `tests/property/test_contract_cases.py` + `parse_reference`, `origin_of` | |
| Doku | `docs/architecture.md` (Modultabelle, Pipeline-Tabelle, Datenhaltung, Berichtsseite), `docs/decisions.md` (Punkt 21: Gremien aus der Drucksachennummer, mit § 2), `README.md` („neun Offline-Schritte" → elf, Daten und Herkunft), `CHANGELOG.md` unter „Unreleased", `STATUS.md`, `docs/profiling/README.md` (Zeit der zwei Schritte) | |

Nicht berührt: `wahlbezirke_auswertung.parquet` und seine Erzeuger (`analysis/hits.py`, `search/`),
`records.py`, `oparl.py`, `stores.py`, `sources/`, `karte.html` (`map.html.j2`, `render_map`),
`report/documents.py`, `tests/fixtures/mini/expected/`.

## 5. Bauplan in Stufen

Jede Stufe sind ein bis drei Commits, nach jedem `uv run nox` grün (im Alltag `uv run pytest -n 2`),
Verhaltensänderung zuerst mit rotem Test. Tests arbeiten in `tmp_path` mit `Layout(tmp/data, tmp/cache,
mini_root)` oder mit der Sitzungs-Fixture `mini_run`. Aufwand ist Agentenzeit einschließlich Tests und nox.

### Stufe A: Settings, Parser, Herkunft, Zuordnung (rund 4 h, 3 Commits)

1. **Settings.** `defaults.toml` bekommt `[bodies]` (Muster mit Kommentar „trifft alle 19 108 Nummern der
   Referenz, 2026-10-11", `district_body = "BV"` mit dem Hinweis, dass die Nummer dahinter der Stadtbezirk ist,
   `[bodies.council]` mit `RAT = "Rat"`, `[bodies.committees]` und `[bodies.advisory]` mit den Namen aus § 3.1
   und einem Kommentar mit Quelle, Kürzel ohne gesicherten Namen mit `""`, `[[bodies.origin]]` als Liste:
   `buerger` mit `["eingabe"]`, `fraktion` mit `["antrag", "anfrage"]`, `verwaltung` mit `["vorlage",
   "beschluss"]`, Teilstring ohne Groß/Klein, erste Regel gewinnt) und `columns.results.city_district =
   "Stadtbezirk"`. `settings.py`: Modelle und Validatoren aus § 4. Tests in `tests/unit/test_settings.py`:
   Default lädt, doppeltes Kürzel in zwei Tabellen ist ein Fehler, Muster ohne Gruppe `code` ist ein Fehler,
   der Fingerprint ändert sich mit einem Kürzel.
2. **Parser `prep/bodies.py`.** `BodyRules` (frozen dataclass: kompiliertes Muster, `district_body`,
   drei `frozenset`, Namen als `Mapping`, Herkunftsregeln als Tuple) aus den Settings;
   `parse_reference(reference: str | None, rules) -> BodyRef(kind, code, district)`: kein Treffer des Musters
   → `("unbekannt", None, None)`; Kürzel gleich `district_body` mit Nummer → `("bezirksvertretung", "BV6", 6)`;
   Kürzel in `council` → `rat`; in `committees` → `ausschuss`; in `advisory` → `beirat`; sonst `("unbekannt",
   code, None)`; ein Kürzel aus den Tabellen mit Nummer oder `district_body` ohne Nummer ist `unbekannt`.
   `origin_of(paper_type, rules) -> str`. Verträge: `deal.pure`; post `kind in KINDS`, `district is not None`
   genau dann, wenn `kind == "bezirksvertretung"`, `district >= 1`, `code is None` nur bei `unbekannt`;
   `origin_of` liefert ein Element aus `ORIGINS`. Beispieltests: die sechs Formen aus § 3.1, `11/3/2019`,
   `BV/1/2020`, `bv1/1/2020`, leer, None; alle 39 `paper_type`-Werte der Referenz als Liste im Test mit
   erwarteter Herkunft. `classify_papers(corpus, rules) -> DataFrame` mit Spalten `id`, `reference`, `gremium`
   (Kürzel, null bei keinem Treffer), `gremium_art`, `stadtbezirk` (Int64, null außer BV), `herkunft`;
   Verträge: pre `has_columns(corpus, "id", "reference", "paper_type")`; post Spalten exakt,
   `sorted_unique(result, "id")`, `len == corpus.height`, `gremium_art` ⊆ `KINDS`, `stadtbezirk` null genau
   bei Nicht-BV. Test auf der Mini-Fixture: 93/86/16/5/0 und Herkunft 128/63/9/0.
3. **Zuordnung `prep/crosswalk.py`.** `unit_weights(results, columns, unit_column, name)`: aus dem rohen
   CSV-Frame (`read_results_csv`) je (Wahlbezirk, Einheit) die Summe der Wahlberechtigten und das Gewicht
   (Anteil an den Wahlberechtigten des Wahlbezirks); Zeilen mit 0 Wahlberechtigten (Briefwahl) fallen weg.
   Ausgabe `wahlkreis_id` Int64, `<name>` Int64, `wahlberechtigte` Int64, `gewicht` Float64, sortiert nach
   Wahlbezirk und Gewicht absteigend. Verträge: pre Pflichtspalten; post eine Zeile je Paar, `gewicht` in
   (0, 1], Summe je Wahlbezirk 1 ± 1e-9, jeder Wahlbezirk mit Wahlberechtigten > 0 kommt vor. Tests: Mini
   (drei Zeilen, Gewicht 1,0), synthetischer Zweifachfall wie Wahlbezirk 40 (0,647 und 0,353, Reihenfolge),
   hypothesis in `tests/property/test_bodies_props.py` (zufällige Stimmbezirkszeilen mit Text-Zellen wie in
   `test_prep_props.py`: Summen 1, Bezirke ohne Wahlberechtigte fehlen). Ein Test prüft auf der Mini-Fixture,
   dass `Stadtbezirk` der CSV mit `Stadtbezirk Nr.` des GeoJSON je Stimmbezirk übereinstimmt (22 von 22); der
   slow-Test dasselbe auf der Referenz (306 von 306).
4. **Property-Tests für den Parser.** hypothesis-Strategie, die Nummern aus der Grammatik baut (Kürzel aus den
   Tabellen oder ein fremdes, optionale Nummer 1 bis 99, laufende Nummer, Jahr, optionaler Nachtrag `/n`,
   `-n`, `/-n`): das Ergebnis ist die erzeugte Klasse, `code` das erzeugte Kürzel samt Nummer, `district` die
   Nummer; für beliebigen Text: keine Ausnahme, Invarianten der Nachbedingung. `deal.cases` für
   `parse_reference` und `origin_of` in `test_contract_cases.py` (kwargs: `reference` aus `st.text()`,
   `rules` als fester Wert aus den Default-Settings). `nox -s verify` mit `origin_of`; `parse_reference` nur,
   wenn crosshair das kompilierte Muster verfolgt (einmal probieren, Ergebnis im Commit-Body).
5. **Abnahme:** `uv run nox` grün; `classify_papers` auf der Referenz im Scratchpad: 0 unbekannt (Grenze aus
   dem Briefing: unter 5 %, sonst begründen); Herkunft 0 unbekannt; `unit_weights` auf der Referenz liefert
   42 Zeilen mit den Gewichten aus § 3.2; `grep -rn "Düsseldorf\|BV\b\|RAT" src/georep/prep/bodies.py` zeigt
   nichts außer Docstrings.

### Stufe B: Kennzahlen, Schritte, Golden Master (rund 4 h, 3 Commits)

1. **`analysis/bodies.py`.** `hits_by_body(results, papers, units, eligible_column) -> DataFrame`: `results`
   (`wahlkreis_id`, `paper_ids`, `anzahl_treffer`, Wahlberechtigte) explodieren, mit `papers` (`id`,
   `gremium_art`, `stadtbezirk`) verbinden, „eigene" ist eine BV, deren `stadtbezirk` in der Menge der
   Stadtbezirke des Wahlbezirks aus `units` liegt; Summen über explizite Bedingungen (`(quelle ==
   "eigene_bv").sum()`), kein `pivot`, damit leere Klassen 0 statt fehlender Spalten ergeben. Ausgabe
   `wahlkreis_id`, `stadtbezirke` List(Int64) (absteigend nach Gewicht), `anzahl_treffer`,
   `treffer_eigene_bv`, `treffer_andere_bv`, `treffer_rat`, `treffer_ausschuss`, `treffer_beirat`,
   `treffer_unbekannt`, `anteil_eigene_bv`, `anteil_rat`, `quote_eigene_bv` (je Wahlberechtigtem). Verträge:
   pre Pflichtspalten und jede `paper_id` der Auswertung kommt in `papers` vor (sonst `SchemaError`); post
   `sorted_unique`, `parts_sum_to` (sechs Klassen gleich `anzahl_treffer`), `shares_in_unit_interval`,
   Bezirke gleich denen der Auswertung. `documents_by_body(papers, results) -> DataFrame`: je `gremium`
   (null wird `""`) `gremium_art`, `stadtbezirk`, `name` kommt erst im Report dazu, `dokumente`,
   `mit_treffer`, `anteil_eigener_stadtbezirk` (nur BV: Anteil der Treffer in Wahlbezirken des eigenen
   Stadtbezirks, sonst null); Verträge: eine Zeile je Kürzel, `dokumente >= mit_treffer >= 0`, Summe
   `dokumente` gleich `papers.height`. Tests auf der Mini-Fixture gegen die Zahlen aus § 3.3 (auch der Bezirk
   38 mit 0 Rats-Treffern), ein synthetischer Fall mit zwei Stadtbezirken (beide BV zählen als eigene),
   hypothesis: zufällige Zuordnung Dokument → Klasse und zufällige `paper_ids` → Summen stimmen, eigene ⊆ BV,
   Anteile in [0, 1].
2. **Pipeline.** `layout.py`-Properties; `pipeline.py`: `voters()` schreibt `district_units` als zweite
   Ausgabe; Schritte `bodies` und `body_hits` nach § 4; `report` mit drei weiteren Eingaben; `export.py`:
   `csv_plan` + 4. Dann die Tests anpassen, die Zahlen zählen (§ 4: `test_cli.py`, Snapshot, Golden
   `test_pipeline.py` mit der Nachfolger-Kette). Rückgabezeilen der Schritte: „19 108 Dokumente: 10 999 BV,
   2 301 Rat, 5 360 Ausschuss, 448 Beirat, 0 unbekannt" und „41 Wahlbezirke, 38 Gremien".
3. **Golden Master.** Der slow-Test prüft auf der Referenz die eingefrorenen Zahlen aus § 3.3 und § 3.2; der
   Mini-Test die Mini-Zahlen; `test_two_runs_write_identical_parquet` nimmt `papers_bodies`, `district_bodies`,
   `bodies_table`, `district_units` dazu. `expected/` der Mini-Fixture bleibt unangetastet (`git status`).
4. **Abnahme:** `uv run nox`, `uv run pytest -m slow` grün; `uv run georep run` auf der Referenz läuft mit „11
   ausgeführt" durch (alle Stamps neu wegen des Fingerprints), ein zweiter Lauf überspringt alles mit
   „aktuell"; `uv run georep profile bodies body_hits` liefert zusammen unter 1 s (Zahlen nach
   `docs/profiling/README.md`); `uv run nox -s bench` grün oder mit angelegter Baseline für die zwei neuen
   Benchmarks; `wahlbezirke_auswertung.parquet` ist byteidentisch mit dem Stand vor der Option (Hash vorher
   notieren, nach dem Lauf vergleichen).

### Stufe C: Berichtsseite (rund 5 h, 2 bis 3 Commits)

1. **Modell.** `DistrictBodies` (own, other, council, committee, advisory, unknown, own_share, own_rate,
   city_districts: tuple[int, ...]), `BodyRow` (code, name, kind, district, documents, with_hits,
   local_share), `BodyFigures` (Dokumente und Dokumente mit Treffer je Klasse, Anteil unbekannt, Stand der
   Namen), `body_regression: RegressionResult | None` aus `regress(frame, x="quote_eigene_bv")` auf dem Join
   `district_bodies` mit `voters` (None, wenn `EmptyResultError`). `DistrictRow.bodies` wird aus
   `district_bodies` gefüllt; Vertrag: `bodies` für jede Zeile gesetzt, Anteile in [0, 1], `own + other +
   council + committee + advisory + unknown == hits`. Namen aus `settings.bodies` (Kürzel ohne Namen zeigen
   das Kürzel); `COLUMN_DOCS` für `wahlbezirke_gremien`, `gremien`, `wahlbezirke_stadtbezirke` auf Deutsch mit
   Einheit. Tests: Zahlen gegen Polars, Escaping eines Namens `"<b>" & Co` im Modell, Regression auf drei
   Bezirken ist vorhanden (n = 3).
2. **Karte und Legende.** `classify({d.id: d.bodies.own_share})`, `choropleth(…, bodies=…)`, `data-own` im
   Tooltip, `Visuals.bodies_legend` mit `own_share_label` (`percent_de(v, 0)`), drittes Radio „Anteil eigene
   Bezirksvertretung", `#legend-bodies` mit Zeile „Anteil der Treffer aus der Bezirksvertretung des eigenen
   Stadtbezirks". JS: ein Zweig für alle drei Kennzahlen (`"data-class-" + metric`), Legenden über
   `hidden`. Tests: jede `<path>` trägt `data-class-bodies` in `{0, 1, 2}` auf der Mini-Fixture, das SVG parst,
   die Legende hat so viele Einträge wie Klassen.
3. **Abschnitt `#gremien`** nach „Je Wahlbezirk": ein Absatz, was eine Drucksachennummer ist und wie die
   Regel liest (mit Beispielen aus den Daten), Kacheln oder ein Satz mit den Anteilen je Klasse und dem
   Anteil „unbekannt" (auf der Referenz 0,0 %), die sortierbare Tabelle je Wahlbezirk (Nr., Name,
   Stadtbezirk(e), Treffer, eigene BV mit Anteil, andere BV, Rat, Ausschüsse, Beiräte, unbekannt, Quote eigene
   BV), die Tabelle je Gremium (Kürzel, Name, Art, Dokumente, mit Treffer, für BV der Anteil im eigenen
   Stadtbezirk), eine Fußnote zu Wahlbezirk 40 mit beiden Gewichten, der Regressionssatz, ein Satz zum Stand
   der Namen (Settings, Datum) und der Hinweis, dass ein Dokument je Wahlbezirk einmal zählt. Spaltenschema
   und Downloads kommen automatisch über `published_tables` und `COLUMN_DOCS`. Tests: Abschnitt vorhanden, 3
   Zeilen, jeder Gremienname der Mini-Fixture auf der Seite, `index.html` der Mini-Fixture parst, keine neuen
   externen Links (`ALLOWED_LINKS` unverändert).
4. **Im Browser prüfen** (Abnahme aus dem Briefing): `python3 -m http.server 8777 --directory data/site`
   (Port 8765 ist belegt, Memory-Notiz „site-preview-and-screenshots"), dann mit `javascript_tool` in der
   eingebauten Browser-Ansicht: alle drei Radios nacheinander wählen und prüfen, dass jede `.district` die
   Klasse `q<data-class-…>` der gewählten Kennzahl trägt, genau eine Legende sichtbar ist, Tooltip die Zeile
   „eigene BV" zeigt, Klick-Markierung und Tabellensortierung der neuen Tabelle funktionieren; dann headless
   Chrome (§ 8.4 des Meta-Plans) in Hell und Dunkel, Streifen ansehen. Befund im Commit-Body.
5. **Abnahme:** `uv run nox` grün; Seite baut aus der Referenz; `index.html` unter 1,5 MB (erwartet rund 705
   KB); `site/data` hat 21 Dateien, SHA-256 auf der Seite stimmen; Umschalter im Browser geprüft; Hell und
   Dunkel angesehen.

### Stufe D: Dokumentation, Messungen, Abschluss (rund 2 h, 1 bis 2 Commits)

1. `docs/architecture.md`: Modultabelle (`prep/bodies`, `prep/crosswalk`, `analysis/bodies`),
   Pipeline-Tabelle (16 Schritte), Datenhaltung (`processed/` mit vier neuen Dateien), Berichtsseite (dritter
   Umschalter, Abschnitt Gremien, 21 Dateien). `docs/decisions.md` Punkt 21 mit den Entscheidungen 1, 2, 4, 5,
   9 aus § 2 und ihren verworfenen Alternativen. README: „neun Offline-Schritte" → elf, Daten und Herkunft
   (Gremiennamen aus Settings, OParl-Organisationen als Quelle), Befehle unverändert. `CHANGELOG.md` unter
   „Unreleased" (Sammelversion am Ende, Konrad 2026-10-11). `STATUS.md`: Zahlen (Tests, Schritte, Laufzeit).
2. `docs/profiling/README.md`: Laufzeit der Schritte `bodies` und `body_hits` auf der Referenz und die zwei
   Benchmark-Minima, datiert.
3. `uv run nox -s mutate` einmal über `analysis/` (die Session deckt `analysis/bodies.py` ab); Überlebende
   deuten, nicht nachjagen; Befund in `docs/mutation-2026-10-11.md` als neuer Absatz mit Datum. `nox -s
   verify` einmal.
4. **Abnahme:** `uv run nox`, `uv run pytest -m slow`, `uv run nox -s bench` grün im Worktree; `grep -rn
   "Düsseldorf\|0015" src/` zeigt nur `defaults.toml`, Vorlagen und Docstrings; Abschlussmeldung an den
   Supervisor nach § 5 Phase 3 des Meta-Plans (erfüllte und offene Abnahmekriterien, Annahmen, Laufzeiten).

Summe: rund 15 h, 9 bis 11 Commits.

## 6. Auswirkung auf die Berichtsseite

- **Karte** (`#karte`): drittes Radio „Anteil eigene Bezirksvertretung", dritte Legende, eine Tooltip-Zeile.
  Keine neue Geometrie; je `<path>` ein Attribut mehr (41 × rund 25 Bytes).
- **Neuer Abschnitt** `#gremien` zwischen „Je Wahlbezirk" und „Begriffe": Einleitung (rund 1 KB), Tabelle je
  Wahlbezirk (41 Zeilen × rund 230 Bytes ≈ 9,5 KB), Tabelle je Gremium (38 Zeilen × rund 150 Bytes ≈ 5,7 KB),
  Fußnote, Regressionssatz, Methode (rund 1 KB).
- **Downloads und Schema**: drei Tabellen mehr (je Parquet und CSV: `wahlbezirke_gremien` ≈ 6 KB und 4 KB,
  `gremien` ≈ 2 KB und 1 KB, `wahlbezirke_stadtbezirke` ≈ 2 KB und 1 KB), drei Blöcke im Spaltenschema
  (rund 2 KB), `schema.json` um rund 2 KB.
- **Größe**: `index.html` von 686 KB auf rund 705 KB (Budget 1,5 MB); `site/data` von 15 auf 21 Dateien,
  rund 20 KB mehr. Keine Unterseite nötig. `karte.html` unverändert.
- **Kernzahlen**: keine neue Kachel; der Anteil der BV-Dokumente steht im Abschnitt.

## 7. Risiken und Fallstricke

- **Semantik „eigene Bezirksvertretung" für Wahlbezirk 40** (Entscheidung 4): die Zahl ändert sich je nach
  Lesart von 0,26 auf 0,77. Festgelegt auf „alle Stadtbezirke mit Wahlberechtigten des Wahlbezirks", mit
  Fußnote und veröffentlichten Gewichten; die Alternative ist eine Zeile in `hits_by_body` (Frage 1).
- **Namen der Gremien** sind nur teils gesichert und wechseln innerhalb der Periode (ADIG 2024, AWIZ/AWIR
  2021). Die Seite nennt den Stand der Namen; Kürzel bleiben der Schlüssel; Option 4 kann die Tabelle aus
  `organizations` ersetzen (Frage 2).
- **Kürzel sind kein Vertrag mit dem Server**: eine neue Periode oder eine andere Stadt bringt neue Kürzel
  (dann „unbekannt" mit Anteil auf der Seite, keine stille Fehlklasse) oder ein anderes Muster (dann
  `reference_pattern` im Städteprofil). Die Klasse „unbekannt" ist absichtlich sichtbar.
- **Fingerprint**: die neuen Settings machen alle Stamps ungültig; der erste `georep run` nach dem Merge
  rechnet alles neu (7 s), auch im Pages-Workflow. Kein Fehler, aber im CHANGELOG nennen.
- **Polars-Aggregation mit leeren Klassen**: `pivot` lässt Spalten weg, wenn eine Klasse in keinem Bezirk
  vorkommt (Mini-Fixture: „unbekannt" nie, Bezirk 38 ohne Rat). Darum Summen über Bedingungen, Spalten immer
  vorhanden, Tests mit Nullen.
- **`DistrictRow` wird in Tests positional gebaut** (`test_report_charts.py`): das neue Feld muss mit Default
  am Ende stehen, sonst brechen fremde Tests.
- **Zählende Tests** (9 Schritte, 15 Dateien, 7 CSV-Dateien, `function calls == 9`) brechen bewusst; jede Zahl
  mit Diff anpassen, Snapshots nie blind erneuern.
- **Konflikte mit anderen Branches** (für die Synergiephase): `defaults.toml` und `settings.py` (Optionen 1,
  2, 3, 6, 7 fügen Tabellen hinzu), `pipeline.py` `build_steps` (jede Option mit Schritt), `report/model.py`
  und `report.html.j2` (jede Option mit Abschnitt; der Umschalter-JS-Zweig wird hier generisch, Option 8 baut
  daneben die Suche), `COLUMN_DOCS` und `published_tables` (3, 6), `prep/crosswalk.py` (Option 3 erweitert um
  Stadtteil, Option 2 um Flächenanteile), die Herkunft (Option 4 und 6 lesen sie, nicht neu bauen).
- **`deal.pure` mit einem kompilierten Muster als Argument** ist in Ordnung (kein I/O), aber crosshair kann
  `re` womöglich nicht symbolisch verfolgen; dann bleibt `parse_reference` aus `VERIFY_TARGETS`, `origin_of`
  bleibt drin.
- **Browser-Prüfung** ohne sichtbare Ansicht: Screenshots der eingebauten Ansicht sind leer, `javascript_tool`
  und `read_page` funktionieren; die Pixel kommen aus headless Chrome (Memory-Notiz).
- **`regress` auf `quote_eigene_bv`**: in der Mini-Fixture drei Bezirke, Vertrag `n >= 3` hält gerade; ohne
  Streuung `EmptyResultError` → `None` im Modell, die Vorlage lässt den Satz dann weg.
- **Mini-Fixture ohne Zweifachfall**: der Wahlbezirk 40 ist nur im slow-Test und in synthetischen Unit-Tests
  abgedeckt; die Fixture wird nicht erweitert (`expected/` bleibt der Golden Master).

## 8. Offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

1. **Eigene Bezirksvertretung bei Wahlbezirk 40.** Zählen BV9 und BV10 beide als „eigene" (alle Stadtbezirke
   mit Wahlberechtigten des Wahlbezirks) oder nur BV9 (Hauptstadtbezirk, 64,7 %)? Zählt, weil sich die
   Kennzahl dieses Bezirks von 0,77 auf 0,26 ändert und die Lokalität der BV10 von rund 75 % auf 44 %.
   Annahme: beide, Gewichte in der Tabelle, Fußnote auf der Seite.
2. **Namen der Gremien.** Reichen die Namen aus Settings (teils aus Titeln abgeleitet, elf Kürzel ohne
   gesicherten Namen), oder soll ein einmaliger Abruf der `organizations`-Liste (eine Seite, unter einer
   Minute) die Tabelle füllen und als Fixture liegen? Zählt für die Lesbarkeit der Gremientabelle und für
   Option 4. Annahme: Settings mit Quelle je Zeile; ungesicherte Kürzel ohne Namen; der Abruf wird Option 4
   als Baustein vorgeschlagen.
3. **Kennzahl auf der Karte.** Anteil der eigenen BV an den Treffern (dimensionslos) oder Quote der eigenen BV
   je Wahlberechtigtem? Zählt für die Lesart der dritten Karte. Annahme: Anteil; die Quote steht in der
   Tabelle und im Regressionssatz.
4. **Beiräte als eigene Klasse.** Jugendrat, Integrationsrat, Seniorenrat, Behindertenrat (448 Dokumente,
   2,3 %) als „beirat" oder zu den Ausschüssen? Zählt für die Tabelle und die Settings-Form. Annahme: eigene
   Klasse, in der Tabelle, nicht auf der Karte.
5. **Herkunft hier oder in Option 4/6.** Soll die Spalte `herkunft` (Verwaltung, Fraktion, Bürger) in dieser
   Option entstehen? Zählt für die Grenze zu Option 4 (Urheber) und 6 (Gewicht je Dokumentart). Annahme: hier
   als eine Spalte mit drei Settings-Regeln und ohne Kennzahl; die Synergiephase ordnet sie zu.
6. **Zuordnung je Dokument veröffentlichen.** `papers_gremien` als Download (Parquet 126 KB, CSV 2,3 MB) oder
   nicht? Zählt für das Seitenbudget und die Regel „beide Formate". Annahme: nicht veröffentlicht; die Regel
   steht auf der Seite, `dokumente.json` trägt die Drucksachennummer.
7. **Regressionssatz.** Ein Satz mit p für die Quote der eigenen BV, oder gar keine Regression in dieser
   Option (Kennzahlvarianten gehören Option 3 und 6)? Annahme: ein Satz über die vorhandene Funktion, keine
   Tabelle.

Neu bei der Umsetzung (2026-10-12):

8. ~~`main` war rot.~~ **Irrtum, zurückgenommen.** `except OSError, subprocess.TimeoutExpired:` ohne
   Klammern ist seit Python 3.14 gültige Syntax (PEP 758), `ruff format` schreibt sie absichtlich so, und
   mit dem Projekt-Python 3.14.6 importiert das Modul einwandfrei. Der Befund kam davon, dass die Datei mit
   dem System-`python3` (3.12) geparst wurde; Prüfungen laufen nur über `uv run`. Der Commit `ad4cd44` ist
   damit gegenstandslos und seine Änderung an `src/georep/report/build.py` ist zurückgenommen (die Datei
   unterscheidet sich von `main` nur noch um die dritte Kartenkennzahl aus Stufe C). Keine Frage an Konrad.
9. **`deal.pure` auf dem Parser.** Der Plan (§ 2, Entscheidung 10) forderte `deal.pure`; CLAUDE.md verbietet
   `deal.pure`/`deal.has()` in heißen Schleifen, und `classify_papers` ruft den Parser 19 108 mal (gemessen
   0,076 s gegen 0,053 s, rund 30 %, `docs/profiling/README.md`). Umgesetzt mit `deal.safe`; die Reinheit
   prüfen `deal.cases` und crosshair. Annahme: so richtig, CLAUDE.md schlägt den Plan.
10. **Die Tabelle je Wahlbezirk hat elf statt zwölf Spalten.** Mit zwölf lief sie bei 1280 px aus dem
   Container (die letzte Spalte war abgeschnitten); Zahl und Anteil der eigenen BV stehen jetzt in einer
   Zelle, die letzte Spalte heißt nur „Quote". Annahme: so richtig; wer alle Spalten einzeln will, lädt
   `wahlbezirke_gremien.csv`.
11. **Zahlen, die vom Prototyp des Plans abweichen.** Mit Entscheidung 4 (beide Bezirksvertretungen des
   Wahlbezirks 40 zählen als eigene) ist der Höchstwert von `anteil_eigene_bv` 0,771 (Bezirk 40) statt
   0,743 (Bezirk 41), der Median 0,497 statt 0,485, und die Regression auf `quote_eigene_bv` ergibt
   r = 0,24 und p = 0,12 statt r = 0,20 und p = 0,22. Der Prototyp in § 3.3 hatte für Bezirk 40 teils noch
   die Mehrheitszuordnung gerechnet. Annahme: die Zahlen hier sind die richtigen; § 3.3 bleibt als Stand
   der Erkundung stehen.

## 9. Vorbereitung für Option 10 (was wird konfigurierbar, welche Modulgrenze entsteht)

- **Konfigurierbar** in `[bodies]`: das Muster der Drucksachennummer mit benannten Gruppen `code` und
  `number`, das Kürzel der Bezirksvertretungen (`district_body`), die drei Kürzel-Tabellen (Rat, Ausschüsse,
  Beiräte) mit Namen, die Herkunftsregeln als geordnete Liste von Teilstrings; in `[columns.results]` die
  Spalte des Stadtbezirks. Eine Stadt mit anderem Nummernschema (andere Kürzel, Jahr vorn, Ziffernpräfix)
  braucht nur ein anderes Muster und andere Tabellen; was nicht passt, ist sichtbar „unbekannt". Die Annahme
  „Bezirksvertretung n gehört zu Stadtbezirk n" ist die Struktur der GO NRW (eine Bezirksvertretung je
  Stadtbezirk) und steht als Kommentar an `district_body`; eine Stadt mit anderer Zählung bekäme eine Tabelle
  Kürzel → Stadtbezirk (vermerkt als mögliche Erweiterung, nicht gebaut).
- **Modulgrenzen**: `prep/bodies.py` ist ein reiner Parser über ein `BodyRules`-Objekt, ohne Polars in der
  Kernfunktion, ohne Settings-Import in der Signatur (`BodyRules.from_settings` ist die einzige Brücke);
  `prep/crosswalk.py` ist generisch über die Einheit (Stadtbezirk, Stadtteil) und kennt keine Gremien;
  `analysis/bodies.py` arbeitet nur auf Frames mit benannten Spalten; der Report liest Parquet und Settings.
  Kein Düsseldorf-Literal im Code; die Kürzel kommen nirgends im Python vor (`grep` in Stufe A und D).
- **Spätere Quelle**: `organizations` liefert `shortName` = Kürzel und `classification`; eine Methodennotiz
  kann die Settings-Tabelle als „Schnappschuss der Organisationen, Stand Datum" beschreiben. Der Schritt
  `bodies` bliebe gleich, nur die Tabelle käme aus einer Datei statt aus `defaults.toml`.
- **Lehrmaterial**: der Parser mit seinem hypothesis-Test aus der Grammatik ist ein kleines, abgeschlossenes
  Beispiel für Design by Contract über einer Textregel.

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

Für Option 5 im Besonderen:

- **`herkunft` entfällt** (fragen.md 5.5): Option 4 besitzt die Urheberklassifikation (`urheber_art` mit
  fünf Klassen); 05 baut keine Herkunftsregeln, `classify_papers` liefert `id`, `reference`, `gremium`,
  `gremium_art`, `stadtbezirk`. Die `[[bodies.origin]]`-Regeln aus § 5 Stufe A fallen weg.
- **Crosswalk**: statt `prep/crosswalk.py` nutzt 05 `georep.crosswalk.unit_weights(frame, "stadtbezirk",
  "wahlberechtigte")` aus dem Fundament F5 (Ausgabe `wahlkreis_id`, `<unit>`, `<weight>` (Summe), `gewicht`;
  Verträge inklusive `sums_to_one`); 05 liest die CSV mit `read_results_csv`, typisiert die Spalten
  (`columns.results.city_district`) und schreibt das Ergebnis als `wahlbezirke_stadtbezirke.parquet`.
- **Umschalter**: generisch im Fundament F1; 05 ergänzt nur das Radio `value="bodies"` und die Legende
  `#legend-bodies` in `sections/20-karte.html.j2`, das Attribut über `choropleth(..., extra_classes={"bodies":
  classification})` und die Tooltip-Zeile (`data-own`) im Basis-JavaScript des Rahmens (eine Zeile).
- **Regressionssatz** über `regression_pair(frame, settings.analysis.exclude_districts, x="quote_eigene_bv")`
  aus dem Fundament F3.
- **Tabellen**: `wahlbezirke_gremien`, `gremien`, `wahlbezirke_stadtbezirke` als Einträge in `TABLES`.
- **Abschnitt**: `sections/45-gremien.html.j2`; Absatz in `sections/60-methode.html.j2` am Ende.
- **Gremiennamen** aus den Settings wie geplant; nach dem Merge von 04 liegt `raw/organizations.json` vor und
  darf die Namen ersetzen (eigener Commit nach dem Rebase, falls Zeit bleibt).
- **Reihenfolge**: 05 merged als Zweite (nach 08); keine Abhängigkeit von anderen Optionen.
- **Fragen**: alle sieben vorentschieden (fragen.md); 5.5 anders als angenommen (siehe oben).
