# Plan 04: Parteien

Stand 2026-10-11, Branch `feat/04-parteien`. Status: umgeschrieben.

Briefing: [../plan-ausbau-2026-10.md](../plan-ausbau-2026-10.md), § 7.4; Vorlage § 8.3; Regeln § 2.
Dieser Plan ist so geschrieben, dass ein frischer Agent ihn in Phase 3 ohne Rückfragen umsetzen kann. Alle
Zahlen in § 3 sind am 2026-10-11 im Worktree nachgesehen (Polars, `ls -l`, eine einzelne OParl-Anfrage);
die Erkundungsskripte und die aufgezeichnete Antwort liegen im Scratchpad des Planers (`04-parteien/`:
`prototype_parties.py`, `organizations_page1.json`), nichts davon ist im Worktree.

Der Befund, der den Plan prägt: **Der OParl-Server der ITK Rheinland liefert für Düsseldorf keine
Urheberfelder** (`originatorPerson`, `originatorOrganization`, `underDirectionOf` fehlen auf der echten
Seite vom 2026-10-09, auch bei einem „Antrag FDP" und einem „Haushaltsbegleitantrag der Fraktion DIE LINKE"),
und die Rohobjekte der Arbeit haben sie ebenfalls nie getragen (0 von 19 108). Der Urheber steht stattdessen
in drei vorhandenen Feldern: im `paperType` („Anfrage SPD", „Antrag CDU/Grüne": 3 375 Dokumente), im Titel
(„Antrag der SPD-Fraktion": 3 673 Dokumente plus 746 mit Person) und im Textkopf nach „betrifft" („(anfrage
cdu-fraktion vom 28. juli 2023)": 641 Dokumente). Ein Prototyp ordnet damit 96,8 % der Dokumente einer Klasse
zu (Verwaltung 52,6 %, Fraktion 40,2 %, Person 3,9 %, unbekannt 3,2 %). Der volle Metadaten-Abruf (rund 95
Seiten, 2 bis 3 h) wird deshalb vorbereitet und dokumentiert, aber nicht gebraucht; sein Ertrag wären
`modified`-Zeitstempel (Option 7) und `consultation` (Option 5), nicht die Urheber.

## 1. Ziel und Nicht-Ziel

Ziel:

1. Je Ratsdokument der Urheber als Klasse (Verwaltung, Fraktion, Person, Eingabe, unbekannt), bei Fraktionen
   die Menge der Parteien (Kürzel wie in `columns.results.parties`), dazu die Quelle der Zuordnung
   (`paper_type`, `name`, `text`, `oparl`) und die getroffene Zeichenkette, damit jede Zuordnung prüfbar ist.
2. Je Partei und Wahlbezirk: wie viele Dokumente der Partei den Bezirk erwähnen (Schnitt mit `paper_ids` der
   Auswertung), als Zahl, als Anteil an allen Dokumenten der Partei und als Quote je Wahlberechtigtem; daneben
   der Stimmenanteil der Partei im Bezirk aus `wahlbezirke_waehler.parquet` und je Partei der Zusammenhang
   beider Größen über die 41 Bezirke (Pearson r, p). Je Wahlbezirk die Verteilung der Treffer auf die
   Urheberklassen, deren Summe die `anzahl_treffer` der Auswertung ergibt (Vertrag).
3. Die Berichtsseite bekommt den Abschnitt „Urheber und Parteien": sechs kleine Karten (eine je Partei), eine
   Tabelle je Partei (Dokumente, Treffer, r, p), eine sortierbare Tabelle je Wahlbezirk mit Urheberklassen und
   schattierten Parteispalten (die Heatmap des Briefings in Tabellenform), drei neue Download-Tabellen mit
   Schema, und der Dokumentdialog nennt den Urheber.
4. Der OParl-Vertrag kennt die Urheberfelder und das Objekt `Organization`; `PaperRecord`, Store und Korpus
   tragen die Felder mit; ein schneller Netzschritt `organizations` holt die Organisationen (eine Seite,
   0,5 s); `georep fetch papers --max-pages 1` ist die Probe, ob der Server inzwischen Urheber liefert; der
   volle Abruf ist als Lauf für Konrad dokumentiert. Liefert der Server die Felder eines Tages, hat die Quelle
   `oparl` Vorrang vor den Mustern, ohne Codeänderung.

Nicht Ziel: Personen über `memberships` und `persons` einer Fraktion zuordnen (Hunderte Anfragen; § 8, Frage
3); Gremien aus Drucksachennummern (Option 5); ein Regressionsmodell der Wahlbeteiligung mit Parteianteilen
(Option 3); Themen der Anträge; eine Deutung im Sinne von „Partei X kümmert sich um ihre Hochburgen" (die Seite
zeigt Zahlen und sagt, was sie nicht belegen); Fraktionen ohne Spalte im Wahlergebnis (Tierschutz/Freie Wähler,
Die PARTEI, Volt) bekommen keine Hochburg-Kennzahl, zählen aber als Klasse „Fraktion".

## 2. Entscheidungen

| Frage | Entscheidung | Warum, und was verworfen wurde |
|---|---|---|
| Quelle der Urheber | aus `paper_type`, `name` und den ersten 600 Zeichen des Texts nach „betrifft", in dieser Reihenfolge; `originatorOrganization` aus OParl hat Vorrang, sobald es gefüllt ist | der Server liefert die OParl-Felder nicht (§ 3.1), die Muster sind explizit und decken 96,8 % (§ 3.5). Verworfen: auf den Vollabruf warten (Stunden, Ertrag für Urheber null); ein Klassifikator (nichts zu lernen, die Muster stehen im Text); den ganzen Text durchsuchen (Verwaltungsvorlagen zitieren Fraktionen: „die cdu-fraktion beantragt", falsche Treffer) |
| Reihenfolge der Quellen | `paper_type` schlägt `name` schlägt `text`; die erste Quelle mit Parteitreffer gewinnt, die anderen werden nicht mehr befragt | die genaueste Quelle zuerst; der Titel trägt bei BV-Anträgen die Fraktion, der Textkopf fängt die 641 Fälle, in denen der Titel sie verschweigt. Verworfen: Vereinigung aller Quellen (ein Antrag „zur Vorlage der CDU-Fraktion" im Titel ergäbe falsche Mehrfachurheber) |
| Mehrfache Urheber | ein Dokument trägt eine Menge von Parteien (`CDU/Grüne` ergibt beide); es zählt für jede Partei voll; zusätzlich `treffer_allein` für Dokumente mit genau einem Urheber | Summen bleiben ganzzahlig und anschaulich; 1 117 Dokumente haben zwei oder mehr Parteien, 825 davon CDU+GRUENE (Kooperationspapiere). Verworfen: Bruchteile 1/k je Partei (halbe Dokumente, schwer zu prüfen); nur den ersten Urheber (verfälscht die Kooperation) |
| Klassen und Parteien | `urheber_art` ist eine Partition (genau eine Klasse je Dokument: Verwaltung, Fraktion, Person, Eingabe, unbekannt); `parteien` ist eine sortierte Menge, bei Nicht-Fraktionen leer | die Partition trägt den Vertrag „Summen stimmen" gegen `anzahl_treffer`; Parteisummen sind keine Partition und bekommen Schranken statt Gleichheit. Eingaben nach § 24 GO (124 Dokumente) sind Bürgeranträge, weder Verwaltung noch Fraktion |
| Welche Parteien | die sechs Schlüssel aus `columns.results.parties` (CDU, GRUENE, SPD, FDP, Die_Linke, AfD) mit Stimmenanteil; dazu `groups` ohne Stimmenanteil (Tierschutz/Freie Wähler, Die PARTEI, Volt; „interfraktionell" als Marker) | nur dafür gibt es `<Partei>_anteil`; die Gruppen stellen 747 Dokumente und gehören in die Klasse Fraktion, sonst fiele ihr Anteil der Klasse „unbekannt" zu (§ 8, Frage 1) |
| Kennzahl je Partei und Bezirk | `anzahl_treffer` = Dokumente der Partei mit Treffer im Bezirk; `anteil_dokumente` = davon geteilt durch alle Dokumente der Partei; `trefferquote` = geteilt durch Wahlberechtigte; `stimmenanteil` daneben; `angetreten` = Stimmen > 0 | `anteil_dokumente` macht Parteien mit 182 und 2 237 Dokumenten vergleichbar; `trefferquote` ist die Kennzahl der Arbeit je Partei. Verworfen: Lokationsquotient (Anteil der Partei im Bezirk geteilt durch Anteil aller Fraktionen; elegant, aber bei 70 AfD-Treffern über 41 Bezirke instabil, bleibt für Option 6 notierbar) |
| Abgleich mit Hochburgen | je Partei Pearson r und p zwischen `anteil_dokumente` und `stimmenanteil` über die Bezirke mit `angetreten`, mit dem Hinweis, dass bei sechs Tests und n = 41 ein oder zwei „signifikante" Werte unter der Nullhypothese zu erwarten sind (Bonferroni 0,05/6 = 0,008) | reicht für „gibt es einen Zusammenhang?"; ein Modell gehört zu Option 3. Verworfen: Spearman allein (weniger lesbar; wird als Zahl mitgeführt, nicht gezeigt); ein Hochburg-Rang (verliert Information) |
| Konfiguration | alles Düsseldorf-Spezifische in `defaults.toml` unter `[originators]`: Verwaltungs- und Eingabe-`paper_type`s, Antragspräfixe, Fraktions-, Gemeinschafts- und Personenmarker, Länge des Textkopfs, je Partei Schlüssel, Label, Muster und die OParl-Organisationsnamen | Vorgabe für Option 10 (§ 1 des Meta-Plans); eine zweite Stadt bringt andere `paperType`-Werte. Verworfen: Muster im Code (Düsseldorf-Konstanten) |
| Wo gerechnet wird | neues Modul `analysis/parties.py`, neuer Offline-Schritt `parties` nach `results` mit drei Parquet-Ausgaben | `results` und sein Golden Master bleiben unberührt; der Schritt hat eigene Eingaben (Korpus, Auswertung, Wähler) und Stamps. Verworfen: in `results` einbauen (Schema-Version und Golden Master der Arbeit anfassen) |
| Organisationen | pydantic-Modell `OparlOrganization`, Netzschritt `organizations` (eine Seite, 0,47 s), Ausgabe `raw/organizations.json`, Fixture aus der echten Antwort; der Schritt `parties` liest die Datei, wenn sie da ist, um `originatorOrganization`-URLs auf Namen und Parteien abzubilden | billig, legt die Abbildung URL zu Partei an und ist die Grundlage für Option 5 (Gremien per `classification`). Der Server kennt kein `organizationType`, nur `classification` („Fraktion", „Ausschuss", „Bezirk", „Gremium"). Ohne die Datei läuft `parties` nur mit Mustern, also auch aus der Referenz |
| Vollabruf | nicht in diesem Branch; vorbereitet durch `--max-pages N` (Probe) und einen Zähler „mit Urheberfeld" im Abrufbericht; dokumentiert als `georep fetch papers --force` für Konrad | Netz nur stichprobenartig (Meta-Plan § 2); der Abruf bringt für die Urheber nichts, für Option 7 (`modified`) und 5 (`consultation`) etwas, darum als gemeinsamer Lauf vorschlagen (§ 8, Frage 4) |
| Darstellung | sechs kleine Karten in einem SVG (3 × 2, Flächen einmal in `<defs>`, je Karte 41 `<use>`), Quantilklassen je Partei; eine Tabelle je Partei; eine sortierbare Tabelle je Wahlbezirk mit Urheberklassen und sechs schattierten Parteispalten | die Karte ist das Vokabular der Seite; Klassen je Partei zeigen, wohin eine Partei blickt, nicht wie viel sie schreibt (AfD: 70 Treffer, GRUENE: 3 237); die schattierte Tabelle ist die Heatmap mit exakten Zahlen. Verworfen: eine Matrix-Heatmap ohne Geografie; sechs eigenständige SVGs (sechsmal 28 KB Pfade); eine gemeinsame Farbskala (AfD läge überall in der untersten Klasse) |
| Dokumentdialog | `dokumente.json` bekommt je Dokument ein sechstes Feld `urheber` (Label oder Klasse) | rund 130 KB mehr für eine sichtbare Verbesserung; keine neue Abfrage |
| Record-Felder | `tuple[str, ...]` statt `list[str]` für die drei URL-Listen | `PaperRecord` ist `frozen`; Tupel bleiben hashbar und gleichheitsfähig, pydantic validiert JSON-Arrays hinein |
| Verträge | an den Batch-Grenzen von `analysis/parties.py`: Partition je Dokument, Klassen aus der festen Menge, Parteien sortiert und aus den Settings, Summen je Bezirk gleich `anzahl_treffer`, Schranken je Partei; `deal.pure` nur auf der Musterfunktion je Dokument | wie `hits_by_district`; keine Verträge je Dokument in der Schleife (19 108 Aufrufe) |

## 3. Datenlage (Stand 2026-10-11, Spalten exakt)

### 3.1 Was der OParl-Server liefert

- `tests/fixtures/oparl/papers_page.json` (18 903 Bytes, sechs Paper der ersten Seite vom 2026-10-09):
  Schlüssel je Paper `id`, `type`, `body`, `name`, `reference`, `date`, `paperType`, `consultation`, `created`,
  `modified` (alle 6), `mainFile` (5), `auxiliaryFile` (3). **Kein** `originatorPerson`, `originatorOrganization`,
  `underDirectionOf`, `location`, `relatedPaper`, auch nicht bei `vo/114086` („Antrag FDP", OVA/119/2026,
  „Ergänzungsantrag der FDP-Ratsfraktion zur Vorlage OVA/102/2026") und `vo/114087` („Antrag", BV2/292/2026,
  „… Haushaltsbegleitantrag der Fraktion DIE LINKE"). `consultation[]` trägt `organization` (Liste von
  Organisations-URLs, z. B. `organizations/gr/25` = Ordnungs- und Verkehrsausschuss), `role`, `authoritative`,
  `meeting`, `agendaItem`: das Gremium, nicht der Urheber.
- OParl 1.1 (schema.oparl.org, nachgelesen am 2026-10-11): `Paper.originatorPerson` Array von Person-URLs,
  `Paper.originatorOrganization` Array von Organisations-URLs („Urheber, falls der Urheber eine Gruppierung
  ist"), `Paper.underDirectionOf` Array von Organisations-URLs (Federführung, Amt oder Abteilung).
  `Organization`: `name`, `shortName`, `organizationType` (grob: Gremium, Partei, Fraktion), `classification`
  (genauer: Parlament, Ausschuss, Beirat), `membership` (URLs), `subOrganizationOf`, `startDate`, `endDate`,
  `location`, `meeting`, `externalBody`, `web`, `deleted`. `Membership`: `person`, `organization`, `role`,
  `votingRight`, `startDate`, `endDate`, `onBehalfOf`.
- Die eine erlaubte Anfrage: `GET https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/organizations`,
  2026-10-11 21:42 UTC, HTTP 200 in 0,47 s (die Paper-Seiten brauchten am 2026-10-09 85 s), 216 955 Bytes,
  eine Seite ohne `next`, 58 Objekte, im Scratchpad als `organizations_page1.json`. Schlüssel: `id`, `type`,
  `body`, `name`, `shortName`, `created`, `modified` (58), `meeting` (56), `classification` (55), `membership`
  (52), `location` (42), `startDate` (25), `endDate` (16); **kein** `organizationType`. `classification`:
  Ausschuss 24, Fraktion 16, Bezirk 10, Gremium 5, ohne 3. Die Fraktionen und Gruppen der Periode 2020 bis
  2025 (Kürzel ist `shortName`, Nummer der Rest der `id`):

  | Organisation (`name`) | `shortName` | `id` | `startDate`, `endDate` | Partei in den Settings |
  |---|---|---|---|---|
  | CDU-Ratsfraktion | CDU | gr/44 | 1999-01-01, offen | CDU |
  | Ratsfraktion BÜNDNIS 90/DIE GRÜNEN | BÜ 90/GRÜNE | gr/42 | offen | GRUENE |
  | Ratsfraktion SPD/Volt | SPD/Volt | gr/400204 | 2020-11-01, offen | SPD (und Gruppe Volt) |
  | FDP-Ratsfraktion | FDP | gr/49 | 1998-01-01, offen | FDP |
  | Ratsfraktion Die Linke | Die Linke | gr/66 | 2009-10-26, offen | Die_Linke |
  | AfD-Ratsfraktion | AfD | gr/400198 | 2020-11-01, offen | AfD |
  | Tierschutz/FREIE WÄHLER (Gruppe) | T/FW | gr/400202 | 2020-11-01 bis 2025-10-31 | Gruppe T_FW |
  | Ratsgruppe Freie Wähler Tierschutz PARTEI | FrTiPA | gr/400238 | 2020-11-01, offen | Gruppe T_FW |
  | Die PARTEI (ohne `classification`) | Die PARTEI | gr/400205 | 2020-11-01 bis 2025-10-31 | Gruppe PARTEI |
  | Bündnis Sahra Wagenknecht | BSW | gr/400239 | ab 2025-11-01 | außerhalb der Periode |

  Dazu ältere Einzelmandate (AfD gr/162, REP gr/63, PIRATEN gr/146, bis 2020-10-31), zwei Objekte mit
  `id`-Präfix `at/` ohne `classification` („Einzelmandat BSW", „Freie Wähler Tierschutz PARTEI", ab 2025-11),
  Rat (gr/6), Bezirksvertretungen 1 bis 10 (gr/32 bis gr/41, `shortName` BV1 bis BV10), 24 Ausschüsse mit den
  Kürzeln der Drucksachennummern (OVA, KUA, APS, JHA, SCHUA, AGS, …). Größen: das CDU-Objekt 20 535 Bytes (272
  `membership`-URLs), GRÜNE 14 034, Rat 10 916, FDP 6 331; die sechs Partei-Fraktionen zusammen 54 534 Bytes.
  Fixture-Kandidat (unverändert bis auf die Auswahl, unter der 40-KB-Grenze von `test_oparl.py`): die zehn
  Objekte AfD (gr/400198 und gr/162), Die Linke, FDP, T/FW, Die PARTEI, BSW, Rat, BV1, OVA mit `pagination` und
  `links` der echten Seite, 39 142 Bytes; passt SPD/Volt noch hinein, dazunehmen. CDU und GRÜNE bleiben wegen
  der Größe draußen; ihre Abbildung prüft ein Test mit synthetischen Organisationsobjekten.

### 3.2 Was Record, Store und Korpus heute tragen

- `src/georep/oparl.py`: `OparlPaper` mit `id`, `type`, `body`, `name`, `reference`, `date`, `paper_type`,
  `main_file`, `auxiliary_file`, `consultation` (als `list[dict]`), `web`, `created`, `modified`, `deleted`;
  `extra="ignore"`, Urheberfelder werden heute verworfen. Kein Organisationsmodell.
- `src/georep/records.py`: `PaperRecord` mit `id`, `name`, `reference`, `date`, `paper_type`, `main_file`,
  `file_name`, `download_url`, `modified`; `extra="forbid"`, `frozen`.
- `data/raw/papers.jsonl`: 19 108 Zeilen, 9 245 584 Bytes, genau diese neun Felder; `modified` ist in allen
  19 108 Zeilen `null` (aus `from_legacy`). Folge: `georep fetch papers` rechnet `since = None` und holt
  vollständig mit `stop_when_older`; der Upsert ersetzt jede Zeile, deren Gegenstück ein `modified` trägt.
- `reference/raw/paper_objects.json`: 9 723 446 Bytes, 19 108 Objekte, Schlüssel `id`, `name`, `reference`,
  `date`, `paperType`, `mainFile`, `download_url`, `paper_text`; keines der drei Urheberfelder kommt vor.
- `data/interim/papers.parquet` (Schritt `corpus`, Schema-Version 2): 19 108 Zeilen, 15 677 746 Bytes; Spalten
  `id` String, `name` String, `reference` String, `date` Date, `paper_type` String, `main_file` String,
  `file_name` String, `download_url` String, `text` String (kleingeschrieben, ohne Zeilenumbrüche, nach dem
  ersten „betrifft"). 75 Dokumente ohne Text, 16 ohne `download_url`.

### 3.3 Was aus `paper_type`, `reference`, `name` und Text ableitbar ist

`paper_type` hat 39 Werte. Die Verwaltung schreibt ohne Zusatz, Fraktionen des Rats und der Ausschüsse
stehen im Typ, die der Bezirksvertretungen nicht:

| `paper_type` | Dokumente | Klasse |
|---|---|---|
| Beschlussvorlage 4 001, Bezirksvertretung Informationsvorlage 2 699, Bezirksvertretung Beschlussvorlage 1 474, Informationsvorlage 1 327, Berichtsvorlage 177, A+F Beschluss 145, Bedarfsbeschluss 78, Beschlussvorlage RPA 32 | 9 933 | Verwaltung |
| Eingabe nach 24GO 73, Eingabe nach 24 GO 51 | 124 | Eingabe (§ 24 GO NRW) |
| Antrag 3 321, Anfrage 2 353 | 5 674 | Fraktion, Person oder unbekannt: Urheber aus Titel oder Text |
| Anfrage SPD 360, Anfrage Die Linke 325, Antrag Die Linke 310, Anfrage Tierschutz/FREIE WÄHLER 303, Antrag SPD 287, Antrag CDU/Grüne 276, Anfrage FDP 163, Antrag DIE PARTEI-Klima-Fraktion 155, Antrag Tierschutz/FREIE WÄHLER 146, Antrag FDP 134, Anfrage AfD 128, Anfrage CDU/Grüne 126, Haushaltsantrag CDU/Grüne 118, Anfrage DIE PARTEI-Klima-Fraktion 95, Haushaltsantrag Die Linke 87, Anfrage Bündnis 90/Die Grünen 77, Antrag Bündnis 90/Die Grünen 67, Haushaltsantrag SPD 64, Haushaltsantrag FDP 55, Antrag AfD 51, Anfrage CDU 18, Haushaltsantrag Die Partei-KlimaFraktion 13, Antrag CDU 7, Antrag SPD/FDP 5, Antrag SPD / Die Linke 3, zAnfrage REP 2, Haushaltsantrag AFD 2 | 3 377 | Fraktion, Partei aus dem Suffix (Schreibvarianten: „AFD", „Die Partei-KlimaFraktion", „SPD / Die Linke") |

`reference` hat 38 Präfixe (RAT 2 301, BV1 bis BV10 zwischen 794 und 1 383, OVA 752, KUA 617, APS 569, JHA 511,
SCHUA 439, AGS 318, …). Von den 5 674 Dokumenten mit nacktem „Antrag" oder „Anfrage" stammen 5 288 aus BV1 bis
BV10, 181 aus JURAT, 62 aus INTR, 38 aus BR, 24 aus RAT; 4 488 tragen im `name` eine Fraktion oder Partei
(„Tempo 30 … (Antrag CDU-Fraktion und Fraktion Bündnis 90/Die Grünen)", „Glasfaserkabelanschluss Hellerhof -
Anfrage der SPD-Fraktion -", „Interfraktioneller Antrag der Ratsfraktionen von CDU, BÜNDNIS 90/DIE GRÜNEN, SPD,
FDP, PARTEI-Klima: …"), weitere nennen eine Person („Anfrage der Bezirksvertreterin Claudia Drossel", „Antrag
des Herrn Wozny (ZENTRUM)"). Bei 5 667 davon gibt es Text; der Kopf der ersten 600 Zeichen nennt in 2 936
Fällen ein Muster „antrag/anfrage … fraktion" („(anfrage spd-fraktion vom 28. juli 2023)", „(antrag
cdu-fraktion vom 3. august 2023)", „(anfrage frau irmer, spd-fraktion, vom 2. august 2023)").

### 3.4 Wählertabelle

`data/processed/wahlbezirke_waehler.parquet` (41 Zeilen, 9 519 Bytes, Schema-Version 1): `wahlkreis_id` Int64,
`Wahlberechtigte_insgesamt` Int64, `Waehler` Int64, `CDU_Stimmen`, `GRUENE_Stimmen`, `SPD_Stimmen`,
`FDP_Stimmen`, `Die_Linke_Stimmen`, `AfD_Stimmen` Int64, `wahlbeteiligung` Float64, `CDU_anteil`,
`GRUENE_anteil`, `SPD_anteil`, `FDP_anteil`, `Die_Linke_anteil`, `AfD_anteil` Float64 (Anteil an den Wählern).
Mittelwerte: CDU 0,325, GRUENE 0,218, SPD 0,151, FDP 0,047, Die_Linke 0,067, AfD 0,108. **Wahlbezirk 11 hat
`Die_Linke_Stimmen` = 0** (kein Wahlvorschlag; die Stimmbezirks-CSV führt dort die 0, in anderen Bezirken
Dutzende): ein Anteil 0 heißt „nicht angetreten", nicht „keine Zustimmung"; der Abgleich lässt solche Bezirke
je Partei aus (`angetreten = false`). `data/processed/wahlbezirke_auswertung.parquet` (41 Zeilen, 135 841
Bytes) trägt dieselben Spalten plus `suchbegriffe` List(String), `paper_ids` List(String), `anzahl_treffer`
Int64, `trefferquote` Float64; `paper_ids` ist der Schlüssel zum Korpus. `inverted_index.parquet` (5 841 Zeilen,
152 045 Bytes) wird nicht gebraucht.

### 3.5 Prototyp (Scratchpad, 2026-10-11)

Mit den Regeln aus § 2 (Eingaben noch unter Verwaltung) über alle 19 108 Dokumente:

- Klassen: Verwaltung 10 057 (52,6 %), Fraktion 7 689 (40,2 %; aus `paper_type` 3 375, aus `name` 3 673, aus
  Text 641), Person 746 (3,9 %), unbekannt 616 (3,2 %; Titel wie „Nichts Neues vom Kalkumer Schloss?",
  „Freiwillige Feuerwehr", ohne Fraktion im Kopf).
- Parteien (Dokumente je Partei, Mehrfachnennung): GRUENE 2 237, CDU 2 087, SPD 2 059, FDP 807, Die_Linke 791,
  AfD 182; Gruppen: Tierschutz/Freie Wähler 452, Die PARTEI 281, Volt 14; „interfraktionell" ohne Namen 220.
  1 117 Dokumente mit zwei oder mehr Parteien: CDU+GRUENE 825, GRUENE+SPD 50, alle fünf 47, CDU+FDP 40,
  CDU+GRUENE+SPD 37.
- Partition je Wahlbezirk (Verwaltung, Fraktion, unbekannt, Person): Bezirk 1: 1 172 + 637 + 69 + 16 = 1 894 =
  `anzahl_treffer`; Bezirk 24: 233 + 113 + 4 + 21 = 371; Bezirk 38: 248 + 36 + 2 + 30 = 316. Auffällig: in den
  Wahlbezirken 35, 36, 37 und 39 stellen Personen 95 bis 131 Treffer (Anfragen einzelner Bezirksvertreter),
  in 11 bis 18 „unbekannt" 24 bis 59.
- Treffer je Partei über alle Bezirke (Summe `anzahl_treffer`): GRUENE 3 237, CDU 2 816, SPD 2 180, FDP 903,
  Die_Linke 480, AfD 70.
- Pearson r zwischen `anteil_dokumente` und `stimmenanteil`, n = 41: CDU +0,045 (p = 0,78), GRUENE −0,015
  (0,93), SPD +0,072 (0,65), FDP +0,439 (0,004), Die_Linke +0,170 (0,29), AfD −0,365 (0,019). Unter Bonferroni
  (0,008) bleibt nur die FDP; die Seite sagt das so.
- Mini-Fixture (200 Dokumente): Verwaltung 137, Fraktion 52, Person 8, unbekannt 3; Parteien CDU 14, GRUENE 12,
  SPD 10, FDP 10, Die_Linke 9, Gruppen 6: genug für Tests mit Zahlen ungleich null.
- Größen der Prototyp-Tabellen: Urheber je Dokument (19 108 Zeilen, vier Spalten) 49 639 Bytes Parquet; Partei
  × Bezirk (246 Zeilen) 8 811 Bytes.

### 3.6 Seite und Herkunft

`data/site/index.html` 686 088 Bytes, `karte.html` 255 263, `dokumente.json` 2 148 551, Downloads 15 Dateien,
Seite gesamt rund 8,4 MB. Das Karten-SVG misst 252 393 Bytes, davon 28 086 Bytes die 41 Flächenpfade und der
Rest die 1 309 Orte; das Streudiagramm 23 909 Bytes. Herkunft und Lizenz: Metadaten und Organisationsnamen aus
dem Ratsinformationssystem Düsseldorf über OParl (Fuß der Seite nennt es; die Urheberklasse ist aus Titel und
Typ abgeleitet, also aus Metadaten, die `dokumente.json` schon veröffentlicht); Stimmenanteile aus dem
Wahlergebnis des Open-Data-Portals (Datenlizenz Deutschland Namensnennung 2.0, steht schon im Fuß). Nichts aus
der nicht öffentlichen Arbeit.

## 4. Berührungspunkte im bestehenden Code

| Datei | Funktion, Objekt | Was sich ändert |
|---|---|---|
| `src/georep/oparl.py` | `OparlPaper` | drei Felder `originator_person`, `originator_organization`, `under_direction_of` als `tuple[str, ...]` mit Aliasen `originatorPerson`, `originatorOrganization`, `underDirectionOf`, Standard leer; `has_originator` Property |
| | neu `OparlOrganization`, `OrganizationPage` | `id`, `type`, `body`, `name`, `short_name` (`shortName`), `classification`, `organization_type` (`organizationType`, beim Server nie gesetzt), `start_date`, `end_date`, `membership: tuple[str, ...]`, `sub_organization_of`, `created`, `modified`, `deleted`; Seite wie `PaperPage` |
| `src/georep/records.py` | `PaperRecord`, `from_oparl`, `from_legacy` | dieselben drei Tupel, `from_oparl` kopiert, `from_legacy` lässt sie leer; alte JSONL-Zeilen ohne die Schlüssel laden weiter (Standardwerte) |
| `src/georep/stores.py` | `PaperStore.upsert` | keine Logikänderung; Test, dass ein Legacy-Record (ohne `modified`) durch den Server-Record mit Urheberfeldern ersetzt wird und dass Gleichheit die neuen Felder sieht |
| `src/georep/prep/papers.py` | `CORPUS_COLUMNS`, `CORPUS_SCHEMA`, `CORPUS_SCHEMA_VERSION`, `build_corpus` | drei Spalten `originator_person`, `originator_organization`, `under_direction_of` List(String); Version 2 -> 3 (der Stamp von `corpus` meldet „Schema geändert", die Kette läuft ab `corpus` neu, 7 s) |
| `src/georep/settings.py` | `OparlSource` | `organizations_endpoint: str`, `max_pages: int = 0` (0 = alle; zählt wie `pdf_limit` zum Fingerprint) |
| | neu `Party`, `Originators`, `Settings.originators` | `Party(key, label, patterns: list[str], organizations: list[str])`; `Originators(admin_types, citizen_types, motion_prefixes, fraction_markers, joint_markers, person_markers, text_head_chars=600, parties: list[Party], groups: list[Party])`; Validatoren: Schlüssel eindeutig, `parties[].key` ⊆ `columns.results.parties` (Model-Validator auf `Settings`), jedes Muster kompiliert, `text_head_chars > 0` |
| `src/georep/defaults.toml` | `[sources.oparl]`, neu `[originators]`, `[[originators.parties]]` × 6, `[[originators.groups]]` × 3 | Werte aus § 3.3 und § 3.1 mit Warum-Kommentar je Zeile |
| `src/georep/sources/__init__.py` | `cached_session` | Cache-Regel für `organizations_endpoint` mit `cache.oparl_pages_s` |
| `src/georep/sources/oparl.py` | `FetchReport`, `fetch_papers` | Feld `originators: int` (gesehene Paper mit mindestens einem Urheberfeld), `summary()` sagt „…, davon N mit Urheberfeld"; `max_pages` kommt aus den Settings |
| | neu `fetch_organizations(http, endpoint, *, delay_s, sleep) -> tuple[list[OparlOrganization], int]` | folgt `links.next`, lässt `deleted` aus, `deal.raises(FetchError, NetworkError)`, Nachbedingung: IDs eindeutig |
| `src/georep/layout.py` | neu `organizations`, `document_originators`, `district_originators`, `party_results` | `raw/organizations.json`, `processed/dokumente_urheber.parquet`, `processed/wahlbezirke_urheber.parquet`, `processed/wahlbezirke_parteien.parquet` |
| `src/georep/analysis/parties.py` (neu) | `URHEBER_ARTEN`, `classify_document(...)` (rein, `deal.pure`), `classify_originators(corpus, originators, organizations=None)`, `originators_by_district(results, documents)`, `party_hits(results, documents, voters, parties)`, `party_correlations(party_results) -> tuple[PartyCorrelation, ...]` | das ganze Rechnen; Verträge in § 5 Stufe B und C |
| `src/georep/pipeline.py` | `build_steps` | Netzschritt `organizations` (nach `papers`, Ausgabe `raw/organizations.json`); Offline-Schritt `parties` nach `results` (Eingaben `corpus`, `results`, `voters`, dazu `organizations.json`, wenn vorhanden; Ausgaben die drei Parquet-Dateien, Schema-Version 1); `report` bekommt die drei als Eingaben |
| `src/georep/cli.py` | `build_parser`, `_cmd_run`, `_with_pdf_limit` | `fetch --max-pages N` als Settings-Override wie `--limit`; Hilfetext nennt die Probe |
| `src/georep/export.py` | `csv_plan` | drei Einträge: `dokumente_urheber` (`parteien` mit „; ", Trenner „,"), `wahlbezirke_urheber`, `wahlbezirke_parteien` |
| `src/georep/report/model.py` | neu `PartyRow`, `PartyCell`, `OriginatorRow`, `OriginatorFigures`; `ReportModel`; `COLUMN_DOCS`; `published_tables`; `build_report_model` | Modell des Abschnitts, Spaltendoku der drei Tabellen (Pflicht: der Test gegen `schema.json` prüft beide Richtungen), neun statt sechs veröffentlichte Tabellen |
| `src/georep/report/charts.py` | neu `party_maps(cells, shapes, projection, parties) -> str`; `classify`, `legend` wiederverwendet | ein SVG, `<defs>` mit 41 Pfaden, 3 × 2 Panels aus `<g transform>` mit `<use href="#d-N" class="qK">` und `<title>` |
| `src/georep/report/render.py`, `templates/report.html.j2` | `render_report`, Vorlage | Abschnitt `#parteien` nach `#zusammenhang`; CSS für schattierte Zellen; Absatz in „Methode und Grenzen"; `ALLOWED_LINKS` unverändert |
| `src/georep/report/documents.py` | `FIELDS`, `documents_payload(corpus, index, hidden, originators, ...)` | sechstes Feld `urheber`; JavaScript im Dialog hängt es an die `.ref`-Zeile |
| `src/georep/report/build.py` | `DESCRIPTIONS`, `write_tables`, `write_documents`, `build_site` | drei Beschreibungen; Karten-SVG der Parteien in `Visuals` (`party_maps_svg`, `party_legends`) |
| `src/georep/bootstrap.py` | unverändert | die Referenz hat keine Organisationen; `parties` läuft ohne die Datei |
| `tests/unit/test_oparl.py` | `test_model_knows_every_key_the_server_sends`, neu | zweite Fixture `tests/fixtures/oparl/organizations_page.json` (§ 3.1) mit README-Zeile; Roundtrip eines synthetischen Papers mit allen drei Urheberfeldern; Größe beider Fixtures unter 40 KB |
| `tests/unit/test_sources_oparl.py` | neu | `originators` im Bericht; `fetch_organizations` über zwei Fake-Seiten, `deleted` ausgelassen, Formatfehler -> `FetchError` |
| `tests/unit/test_stores.py`, `tests/property/test_models_props.py` | Strategien | Tupel von URLs in `papers` und `PaperRecord`; alte Zeile ohne Schlüssel lädt |
| `tests/unit/test_papers.py` | `test_corpus_from_stores_matches_the_legacy_file` | zwölf Spalten, Schema-Version „3" |
| `tests/unit/test_settings.py` | neu | Parteischlüssel müssen in `columns.results.parties` stehen; doppelte Schlüssel, ungültige Muster abgewiesen; Fingerprint ändert sich mit einem Muster |
| `tests/unit/test_parties.py`, `tests/property/test_parties_props.py` (neu) | | Beispiele je Quelle und Klasse, Vorrang `oparl`, Gruppen, interfraktionell, Person, unbekannt; hypothesis-Invarianten (§ 5) |
| `tests/golden/test_pipeline.py` | `test_pipeline_runs_skips_and_reruns`, `test_two_runs_write_identical_parquet`, `slow` | 10 Offline-Schritte statt 9 (`parties` in der Frische-Tabelle nach `results`), die drei neuen Dateien byteidentisch, auf der Referenz 21 Download-Dateien, Partition in allen 41 Bezirken, `unbekannt` unter 5 % |
| `tests/golden/test_network_steps.py` | `test_online_run_fetches_everything_then_skips` | Route für `organizations_endpoint` mit der Fixture; danach ordnet `parties` ein Paper mit `originatorOrganization` = gr/49 der FDP mit Quelle `oparl` zu |
| `tests/unit/test_cli.py`, `tests/unit/__snapshots__/test_cli.ambr` | Zähltexte, Snapshot | „10 ausgeführt, 6 übersprungen", `--dry-run` „6 übersprungen, 10 geplant", „10 CSV-Dateien"; `georep steps` bewusst neu aufgenommen, Diff gelesen |
| `tests/unit/test_report_build.py`, `test_report_model.py`, `test_report_render.py`, `test_report_documents.py` | Dateizahl, Modell, Abschnitt, Dialogfeld | 21 Dateien; Zahlen gegen Polars; Abschnitt und sechs Panels; `fields` hat sechs Einträge |
| `docs/architecture.md`, `docs/decisions.md`, `README.md`, `CHANGELOG.md`, `STATUS.md` | | Modultabelle, Pipeline-Tabelle (+2 Zeilen), Datenhaltung, Berichtsseite, Netz; ein Entscheidungspunkt; README: Berichtsseite, Befehle (`--max-pages`), Daten (Organisationen), der dokumentierte Lauf; „Unreleased"; „Bekannt": der Server liefert keine Urheberfelder, Wahlbezirk 11 ohne Linke-Vorschlag |

## 5. Bauplan in Stufen

Jede Stufe ein bis drei Commits, nach jedem `uv run nox` grün, Verhaltensänderung mit rotem Test zuerst,
Tests in `tmp_path` mit `Layout(tmp/data, tmp/cache, mini_root)`. Aufwand in Agentenstunden, gemessen am
Berichtsseiten-Plan (Stufen A bis F an einem Tag).

### Stufe A: OParl-Vertrag, Record, Korpus (rund 1,5 h, 3 Commits)

1. `oparl.py`: die drei Urheberfelder auf `OparlPaper`, `OparlOrganization`, `OrganizationPage`; die Fixture
   `tests/fixtures/oparl/organizations_page.json` aus der aufgezeichneten Antwort (Auswahl nach § 3.1, README
   mit Abrufzeit, Auswahlregel, Größe); `test_model_knows_every_key_the_server_sends` auch für Organisationen;
   Roundtrip-Test mit allen drei Feldern (hypothesis-Strategie in `test_models_props.py` erweitert).
2. `records.py`, `stores.py`: Tupelfelder; Tests: Legacy-Zeile lädt, Upsert ersetzt Legacy durch Server-Record,
   Gleichheit unterscheidet Urheberfelder.
3. `prep/papers.py`: drei Listenspalten, `CORPUS_SCHEMA_VERSION = 3`; `test_papers.py` angepasst.
   Abnahme: `nox` grün; `uv run georep run` im Worktree führt `corpus` bis `report` neu aus (Grund „Schema
   geändert"), `papers.parquet` hat zwölf Spalten, `uv run pytest -m slow` grün (der Golden Master kennt den
   Korpus nicht).

### Stufe B: Settings und Zuordnung je Dokument (rund 2,5 h, 3 Commits)

1. `settings.py`, `defaults.toml`: `[originators]` wie in § 4 mit den Werten aus § 3; Validatoren mit
   Gegenbeispiel-Tests; `organizations_endpoint`, `max_pages`; Cache-Regel.
2. `analysis/parties.py`, Teil 1: `classify_document(paper_type, name, text_head, originators, organizations)
   -> Classification(art, parteien, quelle, treffer)` als reine Funktion, und `classify_originators(corpus,
   originators, organizations=None) -> pl.DataFrame` mit Spalten `id` String, `urheber_art` String, `parteien`
   List(String), `quelle` String, `treffer` String (die Zeichenkette, die zur Zuordnung führte). Reihenfolge:
   `oparl` (URLs in `originator_organization` über die Organisationsnamen), `paper_type` (Verwaltung,
   Eingabe, Suffix nach Antragspräfix), `name` (nur bei Fraktionsmarker), `text` (Fenster um
   „antrag|anfrage … fraktion" im Kopf), Personenmarker, sonst `unbekannt`.
   Verträge: pre `has_columns(corpus, "id", "paper_type", "name", "text")`, `text_head_chars > 0`; post eine
   Zeile je Korpus-ID in Korpus-Reihenfolge, `urheber_art` ∈ `URHEBER_ARTEN`, `parteien` sortiert, eindeutig,
   Teilmenge der Settings-Schlüssel, leer außerhalb der Klasse Fraktion, `quelle` ∈ {oparl, paper_type, name,
   text, ""}.
   Tests: ein Beispiel je Pfad (Stufe `oparl` schlägt `paper_type`, „Anfrage CDU/Grüne" ergibt CDU und GRUENE,
   „Haushaltsantrag AFD" ergibt AfD, „Interfraktioneller Antrag …" ohne Namen ergibt Fraktion ohne Partei,
   „Anfrage der Bezirksvertreterin …" ergibt Person, „Eingabe nach 24GO" ergibt Eingabe, leerer Text und
   unbekannter Typ ergeben unbekannt); hypothesis: Groß/Klein und Text jenseits des Kopfs ändern nichts,
   Partition und Teilmengen gelten für zufällige Dokumente, Idempotenz (die Klassifikation des Ergebnisses ist
   das Ergebnis).
3. Golden-Zahlen: Snapshot (syrupy, klein) der Klassen- und Parteizähler auf der Mini-Fixture; auf der
   Referenz (`slow`): `unbekannt` ≤ 5 %, Fraktion ≥ 35 %, jeder `paper_type`-Wert des Korpus ist Verwaltung,
   Eingabe oder beginnt mit einem Antragspräfix (sonst Fehlerliste mit den Werten, damit ein neuer Typ
   auffällt).
   Abnahme: `nox` grün; der Lauf auf der Referenz liefert die Zahlen aus § 3.5 bis auf die Verschiebung der 124
   Eingaben (dokumentiert im Commit-Body); eine geschichtete Stichprobe von 50 Dokumenten (10 je Quelle und
   Klasse unbekannt) ist von Hand gegen Titel und Textkopf geprüft und als Tabelle im Abschlussbericht notiert
   (Fehlerquote unter 5 % oder Muster nachgezogen).

### Stufe C: Kennzahlen und Schritt `parties` (rund 2 h, 3 Commits)

1. `analysis/parties.py`, Teil 2:
   - `originators_by_district(results, documents) -> pl.DataFrame`: `wahlkreis_id`, `anzahl_treffer`,
     `verwaltung`, `fraktion`, `person`, `eingabe`, `unbekannt` (Int64). Vertrag: `sorted_unique` auf
     `wahlkreis_id`; **Summe der fünf Klassen gleich `anzahl_treffer` in jeder Zeile**; nur Bezirke der
     Auswertung; jede `paper_id` der Auswertung hat eine Zeile in `documents` (sonst `SchemaError`).
   - `party_hits(results, documents, voters, parties) -> pl.DataFrame`, lang: `wahlkreis_id` Int64, `partei`
     String, `anzahl_treffer` Int64, `treffer_allein` Int64, `dokumente_partei` Int64, `anteil_dokumente`
     Float64, `trefferquote` Float64, `stimmen` Int64, `stimmenanteil` Float64, `angetreten` Boolean.
     Vertrag: genau |Bezirke| × |Parteien| Zeilen, sortiert nach (`partei`, `wahlkreis_id`); `0 ≤
     treffer_allein ≤ anzahl_treffer ≤ min(dokumente_partei, anzahl_treffer des Bezirks)`;
     `anteil_dokumente` und `stimmenanteil` in [0, 1]; `angetreten == (stimmen > 0)`; `dokumente_partei` je
     Partei konstant und gleich der Zahl ihrer Dokumente in `documents`.
   - `party_correlations(party_results, min_n=3) -> tuple[PartyCorrelation, ...]`: je Partei `n`
     (Bezirke mit `angetreten`), `documents`, `hits`, `districts_hit`, `r`, `p`, `rho` (Spearman, mitgeführt),
     über `scipy.stats.pearsonr`/`spearmanr`; Vertrag: r in [−1, 1], p in [0, 1], `None` unter `min_n`.
   - Tests: Beispiel mit drei Bezirken und zwei Parteien nachgerechnet; hypothesis: für zufällige
     Dokumentmengen je Bezirk und zufällige Zuordnungen gilt die Partition, die Schranken und die Konstanz
     von `dokumente_partei`.
2. `layout.py`, `pipeline.py`, `export.py`: Schritt `parties` (Zeile „19 108 Dokumente: 52 % Verwaltung, 40 %
   Fraktion, 4 % Person, 1 % Eingabe, 3 % unbekannt; 41 × 6 Kennzahlen"); `csv_plan` ergänzt; CLI-Texte und
   Snapshot `georep steps` bewusst erneuert, Diff im Commit-Body; `test_pipeline.py` auf zehn Offline-Schritte,
   `test_two_runs_write_identical_parquet` um die drei Dateien.
3. Abnahme: `nox` grün; `uv run georep run` schreibt die drei Dateien unter `processed/` (246, 41 und 19 108
   Zeilen); der `slow`-Test prüft die Partition in allen 41 Bezirken und die Summen aus § 3.5 (Treffer je
   Partei bis auf die Verschiebung der Eingaben); zwei Läufe byteidentisch; `uv run nox -s bench` grün (der
   Schritt kostet Sekunden: ein Durchlauf über 19 108 Zeilen mit kompilierten Mustern, zu messen mit
   `georep profile parties`, Ziel unter 5 s).

### Stufe D: Fetcher, Netzschritt `organizations`, Probe, Doku des Vollabrufs (rund 1,5 h, 2 Commits)

1. `sources/oparl.py`: `originators` im `FetchReport` und in `summary()`; `fetch_organizations`; Tests mit
   `FakeSession` (zwei Seiten, `deleted`, Formatfehler, Netzfehler). `pipeline.py`: Schritt `organizations`
   schreibt `raw/organizations.json` (Liste der Objekte per `model_dump(by_alias=True)`, kompakt) und meldet
   „58 Organisationen, 16 Fraktionen"; `parties` nimmt die Datei als Eingabe auf, wenn sie beim Aufbau der
   Schritte existiert (dann wandert ihr Hash in den Stamp). `cli.py`: `fetch --max-pages N`.
   `test_network_steps.py`: Route für den Organisationsendpunkt mit der Fixture, ein synthetisches Paper mit
   `originatorOrganization` = `…/organizations/gr/49` landet als FDP mit Quelle `oparl`; `fetch --max-pages 1`
   in `test_cli.py` mit Fake-Session (`build_steps` bekommt `http`), Bericht nennt „0 mit Urheberfeld".
2. README und dieser Plan: der dokumentierte Lauf für Konrad, kein Netz in Tests:

   ```bash
   uv run georep fetch organizations            # eine Seite, Sekunden; raw/organizations.json
   uv run georep fetch papers --max-pages 1     # Probe, rund 90 s: "... 200 Paper gesehen, 0 im Zeitraum, davon N mit Urheberfeld"
   uv run georep fetch papers --force           # nur wenn N > 0 oder für Option 5/7 gewünscht: rund 95 Seiten mit
                                                # stop_when_older, je 85 s plus 1 s Pause, 2 bis 3 h; nicht seitenweise
                                                # wiederaufnehmbar (ein Abbruch beginnt von vorn, der HTTP-Cache hält
                                                # Seiten eine Stunde); danach uv run georep run (corpus bis report, 7 s)
   uv run georep status                         # pdfs zeigt "Settings geändert", solange max_pages im Stamp steht; richtig so
   ```

   Abnahme: `nox` grün; `uv run georep run --dry-run --online organizations` plant den Schritt; keine Anfrage
   in Tests (der Marker `network` bleibt unbenutzt); die drei Befehle stehen in README und Plan.

### Stufe E: Berichtsseite (rund 4 h, 4 Commits; vorher die Skill `dataviz` laden)

1. `report/model.py`: `PartyRow(key, label, documents, hits, districts_hit, n, r, p)`,
   `PartyCell(district, party, hits, share, vote_share, klass)`, `OriginatorRow(district, hits, verwaltung,
   fraktion, person, eingabe, unbekannt)`, `OriginatorFigures(documents, verwaltung, fraktion, person, eingabe,
   unbekannt, with_two_parties)`; `ReportModel.parties`, `.party_cells`, `.originators`, `.originator_figures`;
   `COLUMN_DOCS` für `dokumente_urheber`, `wahlbezirke_urheber`, `wahlbezirke_parteien`; `published_tables`
   mit neun Einträgen. Tests auf der Mini-Fixture gegen Polars.
2. `report/charts.py`: `party_maps`; je Partei `classify(anteil_dokumente)` (bei vielen Nullen weniger
   Klassen, das trägt `classify` schon); Legende je Panel als `<title>` und als Liste unter dem SVG; Tests:
   sechs Panels, 41 `<use>` je Panel, parst mit `ElementTree`, Snapshot der Klassengrenzen auf der
   Mini-Fixture (klein).
3. Vorlage: Abschnitt `#parteien` nach `#zusammenhang`: zwei Absätze (woher der Urheber kommt, mit den
   Deckungszahlen aus `originator_figures`; was die Karten zeigen), das SVG mit Legenden, Tabelle je Partei
   (Partei, Dokumente, mit Treffer, Treffer, n, r, p, mit Fußnote zu sechs Tests und Bonferroni), Tabelle je
   Wahlbezirk (Nr., Name, Treffer, Verwaltung, Fraktion, Person, Eingabe, unbekannt, dann je Partei
   `anteil_dokumente` als Zelle mit Klasse `q0` bis `q4`; sortierbar über die vorhandenen `data-sort`- und
   `data-value`-Attribute); Absatz in „Methode und Grenzen" (Muster, 3 % unbekannt, Personen ohne Partei,
   Kooperationspapiere zählen doppelt, Bezirk ohne Wahlvorschlag); `dokumente.json` mit `urheber`, der Dialog
   zeigt es hinter der Drucksache; `DESCRIPTIONS`; CSS für Zellen (Hintergrund aus `--q0` bis `--q4`,
   Textfarbe mit genügend Kontrast in Hell und Dunkel, Werte prüft die Skill). Tests: Abschnitt und Tabellen
   vorhanden, Zahl der Zellen 41 × 6, externe Links unverändert, `fields` sechs Einträge, Größe unter 1,5 MB
   auf der Referenz (`slow`).
4. Ansehen mit headless Chrome in Hell und Dunkel (Meta-Plan § 8.4), JavaScript über den lokalen Server:
   Sortierung der neuen Tabelle, Dialog mit Urheber; Befund mit Screenshot-Streifen im Abschlussbericht.
   Abnahme: Seite baut auf Mini-Fixture und Referenz; 21 Download-Dateien mit SHA-256 auf der Seite;
   `schema.json` kennt die drei Tabellen; `index.html` unter 1,5 MB; keine Düsseldorf-Konstante im neuen Code
   (`grep -rn "Düsseldorf\|0015" src/` zeigt nur `defaults.toml` und Doku).

### Stufe F: Dokumentation und Abschluss (rund 1 h, 2 Commits)

`docs/architecture.md` (Module, Pipeline mit 16 Schritten, Datenhaltung, Berichtsseite, Netz: Organisationen
und die Urheberfelder), `docs/decisions.md` (Punkt 21: Urheber aus Metadaten und Textkopf, OParl-Felder
vorbereitet, Alternativen und Kosten), `README.md` (Berichtsseite, Befehle, Daten und Herkunft, der Lauf aus
Stufe D), `CHANGELOG.md` unter „Unreleased", `STATUS.md` „Bekannt" (Server ohne Urheberfelder, Wahlbezirk 11),
dieser Plan auf „in Arbeit" beziehungsweise „im Review". Abnahme: `uv run nox`, `uv run pytest -m slow`,
`uv run nox -s bench` grün; Abschlussbericht an den Supervisor mit Laufzeiten, erfüllten und offenen Kriterien,
Stichprobentabelle aus Stufe B und Annahmen.

### Stufe G (optional, nur nach Freigabe in `fragen.md`): der Vollabruf auf Konrads Rechner

Die Befehle aus Stufe D in dieser Reihenfolge; danach `uv run georep run`, Vergleich von
`dokumente_urheber.parquet` vorher und nachher (Zahl der Zeilen mit `quelle == "oparl"`), Ergebnis in
`STATUS.md` und `docs/architecture.md` („Bekannte Grenzen"). Erwartung nach § 3.1: null Zeilen mit `oparl`;
Gewinn sind die `modified`-Zeitstempel für `incremental` (Option 7) und die `consultation`-Listen (Option 5),
die der Korpus dann tragen kann.

Gesamt: rund 12,5 Agentenstunden in etwa 17 Commits, dazu 2 bis 3 h Wartezeit für Stufe G.

## 6. Auswirkung auf die Berichtsseite

- Abschnitt „Urheber und Parteien" zwischen „Trefferquote und Wahlbeteiligung" und „Je Wahlbezirk"; keine
  Unterseite nötig.
- Größe: das Parteien-SVG rund 50 KB (28 KB Pfade einmal in `<defs>`, sechs Panels mit je 41 `<use>` und
  `<title>` rund 17 KB, Beschriftung), Tabelle je Wahlbezirk 41 Zeilen × 14 Zellen rund 20 KB, Tabelle je
  Partei und Texte unter 5 KB, CSS und JavaScript rund 2 KB: `index.html` von 686 KB auf rund 760 bis 780 KB,
  unter dem Budget von 1,5 MB.
- Downloads von 15 auf 21 Dateien: `dokumente_urheber.parquet` rund 50 KB, als CSV rund 1,7 MB (19 108
  OParl-URLs; wie `wahlbezirke_auswertung.csv` mit 2,1 MB hinnehmbar, § 8 Frage 9); `wahlbezirke_urheber`
  rund 3 KB und 2 KB; `wahlbezirke_parteien` rund 9 KB und 20 KB; `dokumente.json` rund 130 KB mehr (auf rund
  2,3 MB); `schema.json` rund 3 KB mehr. Seite gesamt von 8,4 auf rund 10,3 MB, `karte.html` unverändert.
- `karte.html` bekommt nichts; der Dokumentdialog eine Angabe mehr.

## 7. Risiken und Fallstricke

- **Falsche Zuordnungen durch Muster.** Ein Titel „Antrag zur Vorlage der CDU-Fraktion" ist kein CDU-Antrag;
  `\bcdu\b` trifft auch „CDU-nahe Stiftung". Gegenmittel: Vorrang der genaueren Quelle, Fenster im Textkopf statt
  Volltext, Spalte `treffer` mit der getroffenen Zeichenkette, die Stichprobe aus Stufe B, Klasse „unbekannt" statt
  Raten. Die Deckung bleibt eine Zahl auf der Seite, keine Behauptung.
- **Sechs Tests bei n = 41.** FDP p = 0,004 und AfD p = 0,019 im Prototyp; die Seite nennt die Bonferroni-Grenze
  und sagt, dass Kooperationspapiere (CDU+GRUENE 825) beide Karten einander ähnlich machen; `treffer_allein` ist
  die Gegenprobe.
- **BV-Fraktion ist nicht Ratsfraktion.** „CDU-Fraktion" in der Bezirksvertretung 5 ist eine andere Organisation
  als die CDU-Ratsfraktion; die Kennzahl fasst beide unter der Partei zusammen, der Methodentext sagt es; Option 5
  kann nach Gremium trennen (`reference`-Präfix liegt vor).
- **Wahlbezirk 11 ohne Linke-Vorschlag** (0 Stimmen): `angetreten = false`, n = 40 für Die_Linke. Weitere Nullen
  gibt es nicht (Minimum der anderen Anteile über 0,018).
- **Schreibvarianten der Organisationen** („AFD", „Die Partei-KlimaFraktion", „BÜNDNINS 90" im Text, „SPD/Volt"
  ab 2020-11, „Tierschutz/FREIE WÄHLER (Gruppe)" bis 2025-10, dann „Ratsgruppe Freie Wähler Tierschutz
  PARTEI"): alles in den Settings-Mustern, Tests je Variante; neue Varianten fallen über den Snapshot der
  unzugeordneten `paper_type`-Werte und die Quote „unbekannt" auf.
- **Der Stamp von `parties` mit optionaler Eingabe.** `raw/organizations.json` ist beim Aufbau der Schritte da
  oder nicht; `build_steps` entscheidet je Aufruf. Ein Test deckt beide Fälle (ohne Datei: Lauf aus der Referenz;
  mit Datei: Hash im Stamp, Änderung löst den Schritt aus).
- **Der Vollabruf ersetzt alle 19 108 Zeilen** (sie bekommen `modified`); `corpus` bis `report` laufen neu (7 s).
  Ändert der Server inzwischen `name` oder `paperType` eines Papers, verschiebt sich die Zuordnung; Dateinamen
  (`file_name`) sind der Schlüssel des Textstores und sollten gleich bleiben. Der `slow`-Test läuft auf der
  Referenz, nicht auf `data/`, und bleibt grün. Nicht seitenweise wiederaufnehmbar: ein Abbruch nach 60 Seiten
  beginnt von vorn (HTTP-Cache hält Seiten nur eine Stunde); wer das braucht, erhöht `cache.oparl_pages_s` für
  den Lauf.
- **`test_oparl.py` verlangt Fixtures unter 40 KB**; die Auswahl aus § 3.1 misst 39 142 Bytes, der Platz ist eng.
  Memberships nicht kürzen (Fixtures bleiben unverändert); lieber ein Objekt weniger.
- **Kontrast der schattierten Zellen**: `--q3` und `--q4` brauchen helle Schrift im Hellmodus, `--q0` dunkle
  im Dunkelmodus; die Skill `dataviz` liefert den Validator, die headless-Chrome-Streifen den Beweis.
- **pydantic `frozen` und Listen**: Tupel statt Listen (§ 2), sonst wirft `hash()` auf Records.
- **`deal.pure` nur auf `classify_document`**, nicht auf Funktionen mit Polars oder Settings-Objekten; keine
  Verträge in der Schleife über 19 108 Dokumente.
- Wie immer: nie unter `reference/` schreiben, `expected/` der Mini-Fixture nicht anfassen (der neue Schritt
  bekommt keinen Eintrag dort, seine Golden-Zahlen sind ein kleiner Snapshot), Prüfschritte nicht hinter eine
  Pipe, Commit-Messages ohne deutsche Anführungszeichen.

## 8. Offene Fragen

| Nr. | Frage | Warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 1 | Welche Parteien bekommen die Hochburg-Kennzahl: nur die sechs aus `columns.results.parties`, oder sollen Tierschutz/Freie Wähler (452 Dokumente) und Die PARTEI (281) Stimmenspalten aus der Wahlergebnis-CSV bekommen, falls sie dort stehen? | bestimmt `defaults.toml` (`columns.results.parties` wächst), die Zahl der Karten (acht statt sechs) und das Seitenbudget | die sechs; die Gruppen zählen als Fraktion und stehen als Zeile „weitere Fraktionen und Gruppen" in der Parteitabelle ohne r und p |
| 2 | Kooperationspapiere (CDU+GRUENE 825): für jede Partei voll zählen und `treffer_allein` daneben, oder nur Alleinurheber werten? | verändert Karten und Korrelationen von CDU und GRUENE spürbar | voll zählen, `treffer_allein` als Spalte und Fußnote; die Karten zeigen `anteil_dokumente` auf Basis aller Dokumente |
| 3 | Personen (746 Dokumente, 3,9 %): über `memberships` und `persons` den Fraktionen zuordnen? Das sind rund 60 Organisationen mit zusammen über 1 500 Mitgliedschafts-URLs, also Hunderte Anfragen, oder eine Liste der Personen je Fraktion von Hand in den Settings | ohne Antwort bleiben BV-Anfragen einzelner Bezirksvertreter (Wahlbezirke 35, 36, 37, 39: 95 bis 131 Treffer je Wahlbezirk) ohne Partei | Klasse „Person" ohne Partei; die Seite nennt den Anteil; eine spätere Stufe kann `persons` holen, wenn Konrad es freigibt |
| 4 | Soll Konrad den Vollabruf (`georep fetch papers --force`, 2 bis 3 h) starten, obwohl er nach § 3.1 keine Urheberfelder bringt? Gemeinsamer Lauf für die Optionen 4, 5 (`consultation`) und 7 (`modified`)? | entscheidet, ob Stufe G läuft und ob der Korpus `consultation` tragen soll | nur vorbereitet und dokumentiert; der Supervisor bündelt die Frage mit 5 und 7 |
| 5 | Darf der Netzschritt `organizations` (eine Seite, 0,5 s) bei jedem `georep fetch` mitlaufen? | er steht sonst außerhalb der Standardliste, und `raw/organizations.json` fehlt | ja, mit Cache-Lebensdauer `cache.oparl_pages_s` |
| 6 | Darstellung: sechs kleine Karten und die schattierte Tabelle, oder eine Matrix-Heatmap Partei × Bezirk? | Seitenbudget (rund 75 KB), Lesbarkeit | Karten plus Tabelle (§ 2); der Supervisor darf den Abschnitt auf eine Unterseite verlegen, wenn andere Optionen das Budget sprengen |
| 7 | Soll `dokumente.json` den Urheber je Dokument tragen (rund 130 KB mehr)? | Größe der Datei, die beim ersten Klick geladen wird (2,1 MB heute) | ja |
| 8 | Reicht je Partei Pearson r mit p und der Bonferroni-Hinweis, oder soll ein Modell her (Option 3)? | Umfang der Statistik auf der Seite, Abgrenzung zu Option 3 | r, p, rho je Partei; das Modell bleibt bei Option 3 |
| 9 | `dokumente_urheber.csv` wird rund 1,7 MB (19 108 URLs). Als Download anbieten oder nur Parquet? | Seitengröße 8,4 -> 10,3 MB | anbieten, wie `wahlbezirke_auswertung.csv` (2,1 MB) |
| 10 | Eingaben nach § 24 GO als eigene Klasse „Eingabe" (124 Dokumente) oder unter „Person"? | fünf statt vier Klassen in Tabelle und Vertrag | eigene Klasse; Bürgeranträge sind weder Verwaltung noch Mandatsträger |

## 9. Vorbereitung für Option 10

Konfigurierbar wird: `[originators]` vollständig (welche `paperType`-Werte Verwaltung oder Eingabe sind, wie
Anträge heißen, welche Marker Fraktion, Gemeinschaft und Person anzeigen, wie lang der Textkopf ist, je Partei
Schlüssel, Label, Muster und OParl-Organisationsnamen), `sources.oparl.organizations_endpoint` und `max_pages`.
Eine zweite Kommune (Option 1) braucht nur ihre `[[originators.parties]]` und `admin_types`; `columns.results.parties`
bindet die Parteischlüssel an die Stimmenspalten, der Validator sagt, wenn beides nicht zusammenpasst.

Modulgrenzen: `analysis/parties.py` kennt nur Frames und das Settings-Objekt `Originators`, keine Pfade und
kein Netz; `sources/oparl.py` kennt die Endpunkte, `oparl.py` den Vertrag, `report/` liest die drei
Parquet-Dateien. `classify_document` ist eine reine Funktion und damit ein Kandidat für `nox -s verify`
(crosshair) und `deal.cases`; die Polars-Funktionen behalten Laufzeitverträge und hypothesis.

Gemeinsame Bausteine mit anderen Optionen, die der Supervisor in `00-synergien.md` bündeln kann:

- `PaperRecord` und Korpus mit Urheberfeldern (4) und `consultation` (5, 7): eine Erweiterung, ein
  Schema-Sprung des Korpus (2 -> 3), nicht zwei.
- `raw/organizations.json` und `OparlOrganization`: Option 5 bekommt daraus die Gremien mit `classification`
  „Ausschuss", „Bezirk", „Gremium" und die Kürzel der Drucksachennummern (OVA, KUA, …) direkt vom Server.
- `fetch --max-pages`, der Zähler „mit Urheberfeld" und der dokumentierte Vollabruf: Option 7 (inkrementell,
  `modified`) und 2 (ältere Periode) nutzen dieselben Schalter.
- Eine Tabelle „Attribute je Dokument" (`dokumente_urheber.parquet` hier; Gremium in 5; Gewichte in 6): dieselbe
  Form (eine Zeile je Korpus-ID, Schlüssel `id`), vielleicht eine gemeinsame Datei `dokumente_attribute.parquet`
  mit Spalten aus mehreren Optionen und einem gemeinsamen Vertrag „eine Zeile je Korpus-ID".
- Der Abschnittsmechanismus der Seite, `classify` und `legend` für neue Kennzahlen (5: Gremium, 6: Gewichtung),
  kleine Karten per `<defs>` und `<use>` für jede Option, die mehrere Karten braucht (1: Städtevergleich).
- Das sechste Feld in `dokumente.json` ist ein Muster für weitere Attribute im Dialog (5: Gremium).

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

Für Option 4 im Besonderen:

- **Ein Schema-Sprung für alle**: `PaperRecord` und Korpus (2 auf 3) bekommen in Stufe A zusätzlich
  `consultation_organizations: tuple[str, ...]` (die Organisations-URLs aus `consultation[].organization`,
  sortiert, eindeutig), damit Option 5 später die Gremien direkt aus OParl lesen kann, ohne den Korpus erneut
  zu ändern. `from_legacy` lässt das Feld leer.
- **Dialog**: `showDocuments(terms, title)` aus dem Fundament F1 nimmt mehrere Begriffe; 04 hängt an
  `documents.FIELDS` das Feld `urheber` an und zeigt es im Basis-JavaScript des Rahmens hinter der Drucksache
  (eine Zeile im Rahmen, Kommentar `/* Option 04 */`).
- **Abschnitt**: `sections/38-parteien.html.j2` mit eigenem `38-parteien.css` für die schattierten Zellen;
  Absatz in `sections/60-methode.html.j2` am Ende.
- **Tabellen**: `dokumente_urheber`, `wahlbezirke_urheber`, `wahlbezirke_parteien` als Einträge in `TABLES`.
  Für Tabellen mit einer Zeile je Korpus-ID legt 04 das Prädikat `one_row_per_document(frame, corpus_ids)` in
  `contracts.py` an (00-synergien.md § 5.6); 05 und 06 nutzen es nach dem Rebase.
- **Urheber ist 04s Besitz**: Option 5 streicht ihre Spalte `herkunft`; 06 behält Regex-Gewichte auf
  `paper_type`. Die Klassen Verwaltung, Fraktion, Person, Eingabe, unbekannt bleiben wie geplant.
- **`max_pages`** und der Zähler „mit Urheberfeld" bleiben bei 04; 01, 02 und 07 nutzen den Schalter.
- **Reihenfolge**: 04 merged als Fünfte (nach 08, 05, 06, 03), vor 02 und 07, die den Record erweitern.
- **Fragen**: 4.4 offen (gebündelt mit dem Erstabruf von 07); 4.1, 4.2, 4.3, 4.5 bis 4.10 wie angenommen.
