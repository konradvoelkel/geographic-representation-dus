# Vorhaben 15: Dokumentfunktion und gemeinsame Anträge

Stand 2026-11-23, Stufe 1 (Messen), Branch `feat/15-funktion`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „15 Dokumentfunktion und gemeinsame
Anträge". Messskript: [15-funktion-messung.py](15-funktion-messung.py) (`uv run python
docs/plans/15-funktion-messung.py`, rechnet jede Zahl dieses Dokuments nach; `--stichprobe` schreibt
Stichprobe und Kodieraufgaben, `--labels` bildet die Endlabels der Kodierung). Codebuch, Stichprobe
und Labels: `validierung/15-funktion/`.
**Urteil: bauen, mit Variante B** (§ 5). Das Kriterium ist erfüllt: κ = **0,905** (Bootstrap-95-%
0,840–0,960) für Variante B und 0,829 (0,748–0,900) für Variante A an den 135 Dokumenten, denen das
Regelwerk eine Funktion gibt; Restklasse 5,5 % / 0 % / 0 %. Geprüft von zwei Kodier-Agenten desselben
Modells (Opus), nicht von Menschen — ihre Übereinstimmung (α 0,99 bei `funktion`) ist darum ein
schwacher Beleg (Frage 19), und B ist an denselben Labels gewählt, an denen es gemessen ist (§ 4.1).

Die drei Zahlen, auf die es ankommt:

1. **Das Regelwerk gibt 44 187 von 45 418 Düsseldorfer Dokumenten (97,3 %) eine Funktion**; die
   Restklasse ist 5,5 % in der Periode 2014-2020 und 0 % in den beiden anderen (Kriterium ≤ 10 %). Gegen
   die Kodierung trifft Variante B **125 von 135** (κ 0,905); Verwaltungsvorlagen und Anfragen
   fehlerfrei, die zehn Fehler liegen alle bei Anträgen (Berichtsantrag, Symbolpolitik ohne Marker).
   Drei Gegenproben aus den Daten selbst stützen es: die Beratungsrolle der OParl-Objekte passt in
   **98,7 %**, die Textregel der Sammelart „Verwaltungsvorlage" trifft die Dokumentart der späteren
   Perioden in **95,9 %**, das Instrumentwort im Textkopf trifft das im Titel in **99,5 %**.
2. **Gemeinsame Dokumente**: 1 397 (2014-2020), 1 202 (2020-2025), 204 (ab 2025), 15,8 %, 15,3 % und
   11,8 % der Fraktionsdokumente. Die Urheberspalte `parteien` reicht dafür nicht: sie nimmt die erste
   Quelle mit Treffer und **übersieht bei 281 Dokumenten Mitantragsteller** („Antrag CDU/Grüne" mit vier
   Fraktionen im Titel), bei 49 nennt sie mehr Parteien als Art, Titel und Briefkopf, meist aus dem
   Gegenstand. An den Labels: die Antragsteller des Regelwerks haben **Präzision 119/119** und Recall
   119/138 (0,86), und von 30 gemeinsamen Dokumenten erkennt es 26 mit genau denselben Fraktionen
   (`parteien`: 23, dazu ein falsches). Die AfD stellt in keiner Periode ein Dokument gemeinsam mit einer
   anderen Fraktion (0 von 10, 183 und 265).
3. **Konkurrenz im Rat, Zusammenarbeit in den Bezirken.** In Rat und Ausschüssen trägt eine Fraktion der
   Ratsmehrheit **7,4 %** der Initiativen mit, an denen die Opposition beteiligt ist (2014-2020, Ampel),
   **3,2 %** (2020-2025, CDU und Grüne) und **0 von 314** (ab 2025; nach Variante B 7,5 %, 3,2 %, 0 von
   312); und von den wenigen Dokumenten über
   die Grenze sind 42 von 50 und 27 von 43 Allparteienanträge (mindestens vier Fraktionen). In den
   Bezirksvertretungen, gezählt mit dem Lager der Ratsmehrheit, sind es 32,1 %, 23,6 % und 46,8 % — dort
   gelten andere Mehrheiten.

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

**Frage.** Welche Funktion hat ein Ratsdokument — Kontrolle (Anfrage), Information (Mitteilung,
Bericht), Initiative (Antrag, Prüfauftrag), Symbolpolitik (Resolution, Appell), Vollzug (Beschlussvorlage
der Verwaltung, Satzung, Haushalt)? Welche Fraktion nutzt welches Instrument? Wer stellt mit wem
gemeinsam Anträge, innerhalb der Ratsmehrheit und über die Grenze zur Opposition?

**Literatur.** Holtkamp (2008)* unterscheidet kommunale Konkordanz- von Konkurrenzdemokratie: in der einen
entscheiden breite Mehrheiten über Lagergrenzen, in der anderen stehen Mehrheit und Opposition
gegeneinander, und NRW-Großstädte gelten als Fall der zweiten. Gemeinsame Anträge über die Grenze sind
ein beobachtbarer Teil davon, die Abstimmungen der andere (Vorhaben 28). Zu Anfragen als
Kontrollinstrument Höhmann und Sieberer (2020); dort kontrollieren auch Koalitionspartner einander, was
Vorhaben 24 für die Kommune prüft. Mit * markierte Angaben stehen im Meta-Plan aus dem Gedächtnis und
sind vor einem Zitat auf der Seite nachzuschlagen (`report/literatur.toml`).

**Ratsarbeit.** Drei Fragen, die die Seite heute nicht beantwortet: „Mit wem hat unsere Fraktion
in dieser Periode Anträge gestellt, und in welchem Gremium?", „Welche Resolutionen hat der Rat
beschlossen oder beraten?" (eine Liste von 39 Dokumenten, § 3.4), „Wie oft stellen Fraktionen aus
Mehrheit und Opposition gemeinsam?" (im Rat fast nie außer bei Allparteienanträgen, in den
Bezirksvertretungen bei einem Viertel bis knapp der Hälfte der Initiativen mit Oppositionsbeteiligung,
§ 3.11).

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

Gerechnet auf den Läufen vom 2026-11-23 (`georep bootstrap && georep run` für `duesseldorf`,
`duesseldorf-2014`, `duesseldorf-2025` und `moenchengladbach` im Worktree, 18:42 bis 18:48 Uhr). Pfade
aus `georep --profile <p> paths`.

| Datensatz | Profil | Dokumente | mit Text | erstes – letztes Datum |
|---|---|---|---|---|
| 2014-2020 | `duesseldorf-2014` | 22 215 | 21 838 | 2014-05-26 – 2020-09-11 |
| 2020-2025 (Hauptperiode) | `duesseldorf` | 19 108 | 19 033 | 2020-09-14 – 2025-09-12 |
| 2025- (laufend) | `duesseldorf-2025` | 4 095 | 4 075 | 2025-09-15 – 2026-10-13 |
| Mönchengladbach | `moenchengladbach` | 2 895 | 650 | 2020-09-14 – 2025-09-13 |

Gelesen werden je Profil, nur lesend:

- `interim/papers.parquet` (19,4 / 15,6 / 3,1 / 1,1 MB): `id`, `name` (Titel), `reference`, `date`,
  `paper_type`, `file_name`, `text` (kleingeschrieben, ohne Zeilenumbrüche).
- `processed/papers_gremien.parquet`: `id`, `gremium`, `gremium_art` (Punkte 23, 57, 58).
- `processed/dokumente_urheber.parquet`: `id`, `urheber_art`, `parteien`, `quelle` (Option 4, Punkte 59
  bis 64).
- Die Parteimuster und Fraktionsmarker aus `[originators]` des Profils (`georep.settings.load_settings`).

Dazu zwei gemeinsame Messdateien, beide nur lesend:

- `messdaten/14-vorgaenge/oparl_papiere.parquet` (730 KB, der Auszug von Vorhaben 14 aus dem
  HTTP-Cache): `id`, `rollen` — die Beratungsrolle jeder `consultation` („Kenntnisnahme",
  „Entscheidung", „Vorberatung" …). Sie ist **nicht** Teil des Regelwerks, nur seine Gegenprobe (§ 3.5);
  in Stufe 2 bringt sie F6.
- `messdaten/rohtext/<ordner>.parquet` (Phase 0, 1,1 bis 21,8 MB): `name` (PDF-Datei), `text` mit Groß-
  und Kleinschreibung, nur für die Kodieraufgaben (§ 4).

**Herkunft und Lizenz**: dieselben OParl-Metadaten und PDF-Texte des Ratsinformationssystems wie der
Korpus. Ins Repo und auf die Seite kommen nur IDs, Klassen und abgeleitete Zahlen (Frage 6 des
Meta-Plans); die Textanfänge der Kodieraufgaben bleiben lokal.

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

Alle Zahlen vom 2026-11-23, Läufe des Messskripts zwischen 19:03 und 19:22 Uhr; zwei Läufe ohne
Codeänderung ergeben byteidentische Ausgaben. Laufzeit **16,4 bis 104,3 s** bei Lastmittel 3 bis 37
(`uptime` davor und danach, `nice -n 10`, Polars auf vier Threads; der Rechner stand unter Fremdlast).
Das Regelwerk selbst braucht für beide Varianten über alle 48 313 Dokumente **1,9 bis 2,0 s**
(einfädig, Läufe um 19:20 und 19:21 bei Lastmittel 3 bis 4); der Rest ist Laden und Gruppieren.

### 3.1 Das Regelwerk

Die Funktion entsteht in dieser Reihenfolge (`funktion()` im Skript; alle Tabellen und Muster stehen im
Block „Profil" des Skripts, Stufe 2 legt sie ins Stadtprofil):

1. **Dokumentart als ganzer Wert** (`ART`): die Vorlagen der Verwaltung, die Eingaben nach § 24 GO NRW und
   alle 16 Arten Mönchengladbachs. Beschlussvorlage, Bedarfs- und A+F-Beschluss, Beschlussvorlage RPA →
   Vollzug; (Bezirksvertretung) Informationsvorlage, Berichtsvorlage → Information; Eingabe → Initiative.
2. **Präfix der Dokumentart** (`PRAEFIX`): `Anfrage …`, `zAnfrage …` → Kontrolle; `Antrag …`,
   `zAntrag …`, `Haushaltsantrag …` → Initiative.
3. **Die beiden Sammelarten der Periode 2014-2020**, deren Art die Funktion nicht nennt:
   - `Vorlage aus der Politik` (9 601) und `Verwaltungsvorlage` mit Fraktionsbriefkopf: zuerst das
     Titelwort (Anfrage ohne Antrag → Kontrolle, Antrag → Initiative, Resolution → Symbol), dann das
     **erste Instrumentwort im Textkopf** (700 Zeichen) hinter dem Briefkopf („… an den bezirksvorsteher
     … 11.09.2014  antrag quartier rund um den bilker bahnhof"); Bauantrag und Bauvoranfrage zählen
     nicht.
   - `Verwaltungsvorlage` (8 337): der politische Briefkopf, auch ohne das Wort „fraktion" (dann wie oben);
     sonst **das erste Merkmal im Textkopf**, Kenntnisnahme („zur kenntnis", „informationsvorlage",
     „teilt mit") gegen Entscheidung („beschließt", „empfiehlt", „genehmigt", „beschlussdarstellung");
     sonst Titelwörter (Bericht, Mitteilung, MdV, Beschlusskontrolle → Information; Satzung,
     Bebauungsplan, Vergabe, Beschluss → Vollzug); sonst die ersten 3 000 Zeichen.
4. **Symbolpolitik aus dem Titel**, nur für Initiativen aus der Politik (Urheberklasse Fraktion, Person
   oder unbekannt): Resolution, Appell, Solidarität mit, Verurteilung, „bekennt sich", „gegen Hass",
   Sichere Häfen, Seebrücke, Mayors for Peace, Städtebündnis, Städte-Koalition. Eine Anfrage zu einer
   Resolution bleibt Kontrolle, eine Informationsvorlage „Resolution zur Stärkung der Kommunalfinanzen"
   (RAT/374/2021, die Verwaltung berichtet über einen Antrag) bleibt Information.
5. **Variante B** liest zusätzlich den Beschlusstext eines Antrags (1 200 Zeichen): „der rat … verurteilt
   / appelliert / bekräftigt / erklärt seine solidarität / fordert die landesregierung auf" → Symbol;
   und ein **Berichtsantrag** (Titel „Sachstand", „Bericht"; Text „wird gebeten … zu berichten") →
   Kontrolle. Variante A zählt beides als Initiative. Welche gilt, entscheidet die Kodierung (Frage 9.1).

Dazu ein **Instrument** je Dokument (Unterart, nicht Teil des Kriteriums): Anfrage, Nachfrage;
Informations-, Berichtsvorlage; Antrag, Änderungsantrag, Haushaltsantrag, Prüfauftrag, Berichtsantrag,
Eingabe; Resolution; Beschlussvorlage, Satzung, Haushalt, Bauleitplanung, Besetzung, Dringlichkeit, Bau,
Rechnungsprüfung.

### 3.2 Abdeckung je Periode

| Datensatz | Kontrolle | Information | Initiative | Symbol | Vollzug | **Rest** | n |
|---|---|---|---|---|---|---|---|
| 2014-2020 | 5 318 (23,9 %) | 3 790 (17,1 %) | 6 158 (27,7 %) | 23 (0,1 %) | 5 695 (25,6 %) | **1 231 (5,5 %)** | 22 215 |
| 2020-2025 | 3 950 (20,7 %) | 4 203 (22,0 %) | 5 210 (27,3 %) | 15 (0,1 %) | 5 730 (30,0 %) | **0** | 19 108 |
| 2025- | 1 076 (26,3 %) | 791 (19,3 %) | 994 (24,3 %) | 1 (0,0 %) | 1 233 (30,1 %) | **0** | 4 095 |
| Mönchengladbach | 0 | 1 018 (35,2 %) | 612 (21,1 %) | 5 (0,2 %) | 1 260 (43,5 %) | 0 | 2 895 |

Düsseldorf zusammen: Rest 1 231 von 45 418 (2,7 %). Variante B verschiebt 257 Düsseldorfer Dokumente,
alle aus der Initiative: 186 Berichtsanträge in die Kontrolle (77, 89, 20) und 71 Anträge mit
Beschlusstext einer Erklärung ins Symbol (32, 37, 2); in Mönchengladbach 27 Berichtsanträge. Symbol wird
dadurch 55, 52 und 3.

**Woher die Funktion kommt** (Variante A): in den beiden jüngeren Perioden zu 99,9 % aus der
Dokumentart (19 093 und 4 094; der Rest aus dem Titel, Symbolpolitik). In 2014-2020 nur 4 272 aus der Art,
5 259 aus dem Titel und **11 453 aus dem Textkopf** — die Periode hängt am Text, und die Restklasse liegt
ganz in ihr.

**Die Null in der Restklasse ist kein Gütebeweis.** In 2020-2025 und ab 2025 hat jede Dokumentart eine
Zeile in der Tabelle; Rest kann dort gar nicht entstehen. Ob die Zeilen stimmen (ein „Antrag", der nur
einen Bericht verlangt; eine „Informationsvorlage", die eine Entscheidung enthält), misst nur die
Kodierung (§ 4).

### 3.3 Je Dokumentart und Instrument

62 Dokumentarten in Düsseldorf; **53 bekommen immer dieselbe Funktion** (21 324 Dokumente). Gemischt sind
die beiden Sammelarten und die Antragsarten, aus denen der Titel ein Symbol macht (`Antrag` 4 749:
4 742 Initiative, 7 Symbol; `Antrag Die Linke` 385: 378 und 7). Die Sammelarten:

| Art (2014-2020) | Kontrolle | Information | Initiative | Symbol | Vollzug | Rest | n |
|---|---|---|---|---|---|---|---|
| Vorlage aus der Politik | 4 408 | 27 | 4 983 | 18 | 22 | 143 | 9 601 |
| Verwaltungsvorlage | 48 | 2 789 | 50 | 0 | 4 362 | 1 088 | 8 337 |

Instrumente (Variante A), 2014-2020 / 2020-2025 / 2025-:

| Funktion | Instrument | 2014-2020 | 2020-2025 | 2025- |
|---|---|---|---|---|
| Kontrolle | Anfrage / Nachfrage | 5 311 / 7 | 3 935 / 15 | 1 068 / 8 |
| Information | Informations- / Berichtsvorlage | 3 766 / 24 | 4 026 / 177 | 772 / 19 |
| Initiative | Antrag | 5 490 | 3 894 | 658 |
| | Änderungsantrag | 381 | 427 | 62 |
| | Haushaltsantrag | 165 | 673 | 171 |
| | Prüfauftrag / Berichtsantrag | 71 / 31 | 35 / 57 | 22 / 18 |
| | Eingabe § 24 GO | 20 | 124 | 63 |
| Symbol | Resolution | 23 | 15 | 1 |
| Vollzug | Beschlussvorlage | 4 826 | 4 535 | 935 |
| | Besetzung / Bauleitplanung | 300 / 176 | 375 / 170 | 165 / 27 |
| | Haushalt / Satzung | 131 / 108 | 205 / 118 | 35 / 26 |
| | Bau (Bedarf, A+F) / Dringlichkeit | 65 / 88 | 223 / 102 | 41 / 4 |

Mönchengladbach (Prüfstein der Stadtneutralität): alle 16 Arten gehen über die Tabelle, keine Restklasse,
**keine Kontrolle** — die Stadt hat keine Anfragen im Datensatz (Vorhaben 14, § 2). Die Muster des Titels
(Symbol, Änderungs-, Prüfantrag) greifen dort ohne Änderung (5 Symbol, darunter „Resolution: Gegen jeden
Antisemitismus"); die Dokumentarten nicht — sie heißen `1.1 - Beratungsvorlage` und `3 - Fraktionsantrag`
und gehören ins Profil.

### 3.4 Restklasse und Symbolpolitik, mit Beispielen

**Restklasse** (nur 2014-2020): 1 088 Verwaltungsvorlagen und 143 Vorlagen aus der Politik (142 mit
Urheber unbekannt). Davon haben **269 keinen Text**, bei 145 beginnt der Text mit einer Anlage
(„anlage 1 zur vorlage …", Tabellen, Satzungssynopsen), 817 haben Text ohne Merkmal — meist
Sachdarstellungen ohne Beschluss- oder Kenntnisformel. Zehn Beispiele (Seed 15): „Zuschüsse für
Baumaßnahmen 2014 - 1. Halbjahr" (`52/ 43/2014`, eine Tabelle), „Jülicher Straße von Roßstraße bis Euler
Straße" (`171/ 125/2014`, Sachdarstellung), „Öffentliche Beleuchtung Parkstraße" (`171/ 184/2014`, kein
Text), „Benrather Fußgängerzone" (`12/ 27/2014`, eine Bürgeranfrage aus einem Webformular),
„Bezirksvertretung ‚Op Jöck' - Anregungen der Bürgerinnen und Bürger" (`171/ 170/2015`), „Barrierefreier
Neubau der Bushaltestellen …" (`173/ 138/2015`, Text „anlage 3.1"), „Kulturrucksack NRW in Düsseldorf"
(`41/ 62/2016`, eine Liste), „Hundekotbeutelspender im Stadtbezirk 5 - Patenschaften" (`175/ 104/2016`,
Vorlage aus der Politik ohne Text), „Wiederherstellung der Grünanlage Mahnmalachse" (`175/ 163/2017`, eine
Finanzierungsanlage zuerst), „Pilotversuch Rechtsabbiegen bei Rot für Radfahrende" (`66/ 9/2019`, Anlage
zuerst).
Mit dem Rohtext (F1) und den Abschnitten (Vorhaben 11) ließe sich ein Teil heben; das Kriterium braucht
es nicht.

**Symbolpolitik ist selten**: 39 Düsseldorfer Dokumente über drei Perioden in Variante A, 110 in Variante
B, also 0,1 % bis 0,2 % des Korpus; bezogen auf die 18 406 Fraktionsdokumente 0,2 % bis 0,6 %. Die Titel
tragen sie deutlich: „Resolution gegen Fremdenfeindlichkeit" (`01/ 17/2015`, CDU, SPD, Grüne, FDP, Linke), „Palermo
Appell" (`01/215/2019`, Ampel; dazu ein Änderungsantrag der CDU), „Resolution zum russischen Angriff auf
die Ukraine" (`RAT/092/2022`, sechs Fraktionen), „Resolution für besseren Nahverkehr" (`RAT/039/2024`, Die
Linke, an Bund und Land), „Städtebündnis Sichere Häfen" (`RAT/178/2024`) und der Antrag der AfD, die
Mitgliedschaft bei „Seebrücke" zu beenden (`RAT/102/2024`, `RAT/407/2025`). Von den 14 Fraktionsdokumenten
der Hauptperiode tragen die Linke 8 mit, CDU und Grüne je 6, SPD/Volt und FDP je 5 (gemeinsame zählen je
Fraktion). Variante B findet dazu Anträge wie „CETA verhindern" (`01/ 235/2016`), „Keine Panzer für die
Türkei" (`01/ 229/2017`), „Keine Nachtabschiebungen in Düsseldorf" (`01/ 163/2015`), aber auch „Lärmschutz
beim RRX" (`01/ 49/2017`, eine Forderung an Bund und Bahn mit örtlichem Gegenstand) — genau die Grenze,
die das Codebuch mit der Frage `adressat` ausmisst.

### 3.5 Gegenproben aus den Daten selbst

Die Stufen (1) und (2) der Prüfreihenfolge (Meta-Plan, § 2.6): deterministische Proben und Labels, die
die Daten schon tragen.

- **Beratungsrolle** (`consultation.role` der OParl-Objekte aus dem Auszug von Vorhaben 14): Information
  und Kontrolle sollten zur Kenntnis genommen, Vollzug, Initiative und Symbol entschieden werden. Unter
  den Dokumenten mit eindeutiger Rolle passt das in **23 631 von 23 953 (98,7 %)**: 2014-2020 98,5 %
  (3 706 / 3 764), 2020-2025 98,6 % (16 520 / 16 759), ab 2025 99,3 % (3 405 / 3 430). Abweichungen vor
  allem 168 Anfragen der Hauptperiode mit „Entscheidung" und 30 Informationsvorlagen mit „Entscheidung".
  **Grenze**: die beiden Sammelarten haben keine Rolle (9 600 und 8 336 mal „keine"); die Probe prüft die
  Tabelle der Dokumentarten, nicht die Textregeln. Anfragen haben oft keine Rolle (2 071 von 3 950 in der
  Hauptperiode).
- **Die Textregel der Verwaltungsvorlage**, angewandt auf die 11 657 Beschluss-, Informations- und
  Berichtsvorlagen der beiden jüngeren Perioden, deren Art die Funktion nennt: **95,9 %** richtig (96,6 %
  ohne die 92, bei denen die Regel nichts findet). Der häufigste Fehler: 313 Beschlussvorlagen, deren
  Text zuerst „zur Kenntnis" sagt. Für 2014-2020 ist das eine Schätzung der Güte, keine Messung — die
  Vorlagenform war eine andere (Punkt 60).
- **Das Instrumentwort im Textkopf** einer Vorlage aus der Politik gegen das im Titel, wo beide da sind:
  **3 974 von 3 995 (99,5 %)** gleich; 10 Titel sagen Antrag und der Text Anfrage, 6 umgekehrt.

### 3.6 Funktion je Urheberklasse

| Datensatz | Urheberklasse | Kontrolle | Information | Initiative | Symbol | Vollzug | Rest |
|---|---|---|---|---|---|---|---|
| 2014-2020 | Verwaltung | 33 | 3 763 | 18 | 0 | 5 673 | 1 088 |
| | Fraktion | 3 840 | 0 | 4 962 | 11 | 1 | 1 |
| | Person | 351 | 0 | 98 | 0 | 0 | 0 |
| | Eingabe | 0 | 0 | 20 | 0 | 0 | 0 |
| | unbekannt | 1 094 | 27 | 1 060 | 12 | 21 | 142 |
| 2020-2025 | Verwaltung | 0 | 4 203 | 0 | 0 | 5 730 | 0 |
| | Fraktion | 3 301 | 0 | 4 544 | 14 | 0 | 0 |
| | Person | 520 | 0 | 345 | 0 | 0 | 0 |
| | Eingabe | 0 | 0 | 124 | 0 | 0 | 0 |
| | unbekannt | 129 | 0 | 197 | 1 | 0 | 0 |
| 2025- | Verwaltung | 0 | 791 | 0 | 0 | 1 233 | 0 |
| | Fraktion | 883 | 0 | 848 | 1 | 0 | 0 |
| | Person | 139 | 0 | 53 | 0 | 0 | 0 |
| | Eingabe | 0 | 0 | 63 | 0 | 0 | 0 |
| | unbekannt | 54 | 0 | 30 | 0 | 0 | 0 |

Die Partition ist sauber: Verwaltung informiert und vollzieht, die Politik kontrolliert und initiiert.
Einzelmandate fragen mehr, als sie beantragen (60 % bis 78 % Kontrolle), Fraktionen halten beides in etwa
die Waage. Die 51 Dokumente der Verwaltung mit Kontrolle oder Initiative in 2014-2020 sind Anfragen und
Anträge, die unter `Verwaltungsvorlage` liegen, ohne den Briefkopf, den Punkt 62 erkennt.

### 3.7 Funktion je Fraktion: roh und gegen die Praxis der Gremien

Fraktionsdokumente der Funktionen Kontrolle, Initiative und Symbol; ein gemeinsames Dokument zählt für
jede beteiligte Fraktion; SPD und Volt sind ab 2020 **eine** Fraktion, Freie Wähler, Tierschutz und
Die PARTEI ab 2025 eine Gruppe (§ 3.8). „Erwartet" ist die Summe der Kontrollanteile des Gremiums über
die Dokumente der Fraktion (indirekte Standardisierung wie in Vorhaben 14, § 3.8).

| Datensatz | Fraktion | Dokumente | davon gemeinsam | Kontrolle | Initiative | Symbol | Anteil Kontrolle | beob./erw. |
|---|---|---|---|---|---|---|---|---|
| 2014-2020 | CDU | 3 646 | 758 | 1 605 | 2 034 | 7 | 44,0 % | 0,99 |
| | SPD | 2 722 | 834 | 922 | 1 792 | 8 | 33,9 % | 0,79 |
| | Grüne | 2 417 | 1 216 | 897 | 1 512 | 8 | 37,1 % | 0,83 |
| | FDP | 1 361 | 870 | 365 | 988 | 8 | 26,8 % | 0,61 |
| | Die Linke | 555 | 137 | 252 | 301 | 2 | 45,4 % | 0,89 |
| | Tierschutz/FW | 175 | 9 | 126 | 49 | 0 | 72,0 % | 1,53 |
| | AfD | 10 | 0 | 10 | 0 | 0 | 100 % | (2,31) |
| 2020-2025 | Grüne | 2 307 | 1 110 | 813 | 1 488 | 6 | 35,2 % | 0,86 |
| | CDU | 2 165 | 1 070 | 650 | 1 509 | 6 | 30,0 % | 0,74 |
| | SPD/Volt | 2 125 | 303 | 932 | 1 188 | 5 | 43,9 % | 1,02 |
| | FDP | 886 | 187 | 368 | 513 | 5 | 41,5 % | 0,97 |
| | Die Linke | 801 | 81 | 335 | 458 | 8 | 41,8 % | 0,87 |
| | Tierschutz/FW | 453 | 1 | 307 | 146 | 0 | 67,8 % | 1,67 |
| | Die PARTEI-Klima | 292 | 35 | 97 | 193 | 2 | 33,2 % | 0,76 |
| | AfD | 183 | 0 | 129 | 53 | 1 | 70,5 % | 1,75 |
| 2025- | SPD/Volt | 430 | 90 | 236 | 194 | 0 | 54,9 % | 1,02 |
| | Grüne | 377 | 144 | 173 | 204 | 0 | 45,9 % | 0,95 |
| | CDU | 336 | 192 | 106 | 230 | 0 | 31,5 % | 0,66 |
| | AfD | 265 | 0 | 163 | 101 | 1 | 61,5 % | 1,20 |
| | Die Linke | 211 | 8 | 118 | 93 | 0 | 55,9 % | 0,99 |
| | FW/Tierschutz/PARTEI | 174 | 0 | 92 | 82 | 0 | 52,9 % | 1,06 |
| | FDP | 136 | 45 | 52 | 84 | 0 | 38,2 % | 0,67 |

**Der Kontrollanteil ist Praxis des Gremiums.** Unter den Fraktionsdokumenten eines Gremiums (mindestens
100) liegt er 2014-2020 zwischen 0,11 (BV9) und 0,73 (POA), 2020-2025 zwischen 0,19 (BV2) und 0,64; je
Gremienart 2020-2025: Ausschuss 0,57, Bezirksvertretung 0,38, Rat 0,37, Beirat 0,41 — in den
Ausschüssen wird mehr gefragt als im Rat und in den Bezirken. Die Standardisierung verschiebt die rohen
Unterschiede deutlich (die SPD 2014-2020 von 33,9 % auf 0,79, die Linke 2020-2025 von 41,8 % auf 0,87),
aber ein Muster bleibt: **Tierschutz/Freie Wähler (1,53 und 1,67) und die AfD (1,75; ab 2025 1,20)
fragen mehr**, die **Fraktionen der Ratsmehrheit weniger**
(alle unter 1: CDU 0,74 und 0,66, Grüne 0,86 und 0,95 seit 2020; 2014-2020 die Ampel mit 0,79, 0,83 und
0,61). Das ist explorativ (§ 8).

### 3.8 Gemeinsame Dokumente: wer stellt mit wem

**`parteien` reicht nicht.** Die Urheberspalte nimmt die erste Quelle mit Treffer (Punkt 59 ff.): bei
„Haushaltsantrag CDU/Grüne" die Dokumentart, auch wenn der Titel „der Ratsfraktionen von CDU, BÜNDNIS
90/DIE GRÜNEN und SPD" sagt (`RAT/510/2023`), bei einer Antragsart einer Fraktion nur diese, auch wenn der
Titel zwei nennt („Antrag DIE PARTEI-Klima-Fraktion" für „Antrag der Ratsfraktionen Die PARTEI-Klima-Fraktion
und DIE LINKE", `RAT/158/2024`), und bei einem Titel den ganzen Titel, auch den Gegenstand („Grüner Pfeil für
Radfahrende, Antrag der SPD-Fraktion" wird SPD und Grüne, `BV4/080/2025`). Das Skript bildet darum eine
eigene Spalte **Antragsteller** als Vereinigung aus drei Teilen (`antragsteller()`):

1. die Parteien der Dokumentart hinter dem Antragspräfix;
2. der **Autorenteil des Titels**: vom ersten Instrumentwort (Antrag, Anfrage, Resolution, ÄA) bis zum
   ersten Trenner (Doppelpunkt, Semikolon, „zum", „zur", „hier", „vom", Gedankenstrich). So stellt
   „Änderungsantrag der SPD-Ratsfraktion zum Antrag der Ratsfraktionen von CDU und BÜNDNIS 90/DIE GRÜNEN"
   nur die SPD und „Antrag Die Linke: AfD keine Plattform geben" nur die Linke;
3. der **Verfasserblock des Briefkopfs** der Periode 2014-2020, zwischen „nicht öffentlich" und dem
   Gremium oder der Anrede („… nicht öffentlich  spd - fraktion  cdu - fraktion  der bezirksvertretung 8
   an den bezirksbürgermeister …").

Nennt keiner der drei eine Partei, bleibt `parteien`. Danach werden Parteien zu **Fraktionen**
zusammengefasst: die Ratsfraktion SPD/Volt ab 2020-11-01, die Ratsgruppe Freie Wähler Tierschutz PARTEI
ab 2025-11 (Kommentare an `organizations` im Profil). Ohne diesen Schritt wäre „SPD – Volt" mit 216
Dokumenten die stärkste Kante der laufenden Periode, und sie ist keine Zusammenarbeit zweier Fraktionen.

Von 18 406 Fraktionsdokumenten weicht die Spalte Antragsteller bei **330** von `parteien` ab: 281 haben
mehr Parteien (206, bei denen `parteien` aus der Dokumentart kam, 75 aus dem Textkopf), 49 weniger (meist
ein Gegenstand im Titel oder im Fenster um den Briefkopf; ob einige davon Mitzeichner sind, die nur der
Briefkopf nennt, ist offen). Die Kodierung prüft beide (Frage `urheber`, Schicht `gemeinsam`).

| Datensatz | allein | gemeinsam | ohne Partei | gemeinsam: Initiative / Kontrolle / Symbol |
|---|---|---|---|---|
| 2014-2020 | 7 063 | **1 397 (15,8 %)** | 355 | 1 108 / 281 / 8 |
| 2020-2025 | 6 425 | **1 202 (15,3 %)** | 232 | 889 / 307 / 6 |
| 2025- | 1 450 | **204 (11,8 %)** | 78 | 146 / 58 / 0 |

„Ohne Partei" sind Fraktionsdokumente, die keine Partei nennen, fast alle in Bezirksvertretungen (347,
225, 78), meist „interfraktioneller Antrag". Anteil gemeinsamer Dokumente je Gremienart, 2020-2025: Rat
16,6 %, Ausschuss 19,3 %, Bezirksvertretung 12,9 %, Beirat 39,7 % (23 von 58); ab 2025: Rat 5,9 %,
Ausschuss 9,2 %, Bezirksvertretung 15,9 %. Zahl der Fraktionen je gemeinsamem Dokument: 2014-2020 zwei
628, drei 601, vier 83, fünf 77, sechs 8 — die Ampel stellt zu dritt; 2020-2025 zwei 980, drei 124, vier
39, fünf 55, sechs 4.

**Gemeinsame Dokumentarten.** Das Ratsinformationssystem führt die Kooperation als eigene Art: „Antrag
CDU/Grüne" 276, „Anfrage CDU/Grüne" 126, „Haushaltsantrag CDU/Grüne" 118 (2020-2025; ab 2025 25, 20, 11);
dazu selten „Antrag SPD/FDP" (5), „Antrag SPD / Die Linke" (3 und 2). Für die Ampel 2014-2020 gab es keine
solche Art; ihre Anträge stehen unter „Vorlage aus der Politik" und „Antrag Bündnis 90/Die Grünen" mit drei
Fraktionen im Titel.

### 3.9 Mehrheiten, mit Quelle

Die Ratsmehrheit je Periode ist eine **Annahme mit Beleg im Korpus**, nicht aus den gemeinsamen Anträgen
abgeleitet (das wäre zirkulär). Das Skript sucht je Periode die Formel der eigenen Mehrheit im Text
(„Ampelmehrheit", „Ampel-Kooperationsvertrag"; „Ratsmehrheit aus CDU und Grünen", „schwarz-grüne
Ratsmehrheit", „Kooperation von CDU und Grünen") und druckt die ersten und letzten Fundstellen; ein
Rückblick in der Folgeperiode („gemäß ampel-kooperationsvertrag 2014-2020" in `RAT/061/2021`) zählt nicht.

| Periode | Annahme | Belege (Dokumente) | Beispiele |
|---|---|---|---|
| 2014-2020 | SPD, Grüne, FDP („Ampel") | 48 | `174/ 112/2014` (2014-10-20): „… aus der ampel-kooperationsvereinbarung …"; `01/ 2/2015`: „… in den ampel-kooperationsvertrag …"; `BV7/263/2020` (2020-08-17): „… mit ampelmehrheit zugestimmt …" |
| 2020-2025 | CDU, Grüne | 18, dazu 520 Dokumente der Art „… CDU/Grüne" | `RAT/241/2021` (2021-03-09): „… die schwarz-grüne ratsmehrheit …"; `AWM/046/2021`: „… die aktuelle kooperation von cdu und grünen …"; `RAT/324/2023`: „… der ratsmehrheit aus cdu und grünen" |
| 2025- | CDU, Grüne | 4, dazu 56 der Art „… CDU/Grüne" | `RAT/073/2026` (2026-02-11): „nun beantragt die ratsmehrheit aus cdu und grünen …"; `RAT/120/2026` (2026-03-10): „… der schwarz-grünen ratsmehrheit …" |

„Ampel" heißt SPD, Grüne und FDP; dass es genau diese drei sind, bestätigt das Netz (§ 3.10: die drei
stärksten Kanten in Rat und Ausschüssen), ist aber nicht daraus geschlossen. **Annahmen**: die Mehrheit
gilt für Rat und Ausschüsse über die ganze Periode (ein Wechsel innerhalb einer Periode ist nicht
geprüft); die **Bezirksvertretungen haben eigene Mehrheiten**, die im Datensatz nicht stehen (Vorhaben 27,
`membership`; `BV7/261/2020` spricht von „ampelmehrheiten in aps und bezirksvertretung", in BV7 war es also
dieselbe, für die anderen Bezirke gibt es keinen Beleg), und werden darum nur mit dem Lager der
Ratsmehrheit als Näherung gezählt.

### 3.10 Das Netz der Mitantragsteller

Kanten zwischen Fraktionen, Gewicht = gemeinsame Dokumente (alle Gremien, in Klammern Rat und
Ausschüsse); „Anteil" = Anteil an allen Fraktionsdokumenten der Fraktion.

**2014-2020** (15 Kanten, 1 397 Dokumente; Mehrheit SPD, Grüne, FDP):

| Kante | Gewicht (Rat/Ausschüsse) | Lager | Anteil an A / B |
|---|---|---|---|
| Grüne – SPD | 772 (405) | Mehrheit | 31,9 % / 28,4 % |
| FDP – Grüne | 738 (398) | Mehrheit | 54,2 % / 30,5 % |
| FDP – SPD | 593 (383) | Mehrheit | 43,6 % / 21,8 % |
| CDU – Grüne | 591 (46) | über die Grenze | 16,2 % / 24,5 % |
| CDU – FDP | 417 (45) | über die Grenze | 11,4 % / 30,6 % |
| CDU – SPD | 212 (43) | über die Grenze | 5,8 % / 7,8 % |
| Linke – SPD / Grüne / FDP | 136 / 129 / 99 (9 / 10 / 9) | über die Grenze | 24,5 % / 23,2 % / 17,8 % der Linken |
| CDU – Linke | 91 (7) | Opposition | 2,5 % / 16,4 % |

**2020-2025** (16 Kanten, 1 202 Dokumente; Mehrheit CDU, Grüne):

| Kante | Gewicht (Rat/Ausschüsse) | Lager | Anteil an A / B |
|---|---|---|---|
| CDU – Grüne | 1 019 (577) | Mehrheit | 47,1 % / 44,2 % |
| Grüne – SPD/Volt | 262 (41) | über die Grenze | 11,4 % / 12,3 % |
| CDU – SPD/Volt | 184 (36) | über die Grenze | 8,5 % / 8,7 % |
| CDU – FDP | 142 (23) | über die Grenze | 6,6 % / 16,0 % |
| FDP – SPD/Volt | 137 (34) | Opposition | 15,5 % / 6,4 % |
| FDP – Grüne | 127 (27) | über die Grenze | 14,3 % / 5,5 % |
| Linke – SPD/Volt | 70 (18) | Opposition | 8,7 % / 3,3 % |
| PARTEI – SPD/Volt, Linke – PARTEI | 23 (23), 23 (23) | Opposition | |

**2025-** (10 Kanten, 204 Dokumente; Mehrheit CDU, Grüne): CDU – Grüne 137 (57), CDU – SPD/Volt 78 (1),
CDU – FDP 44 (0), FDP – Grüne 42 (0), Grüne – SPD/Volt 31 (1); in Rat und Ausschüssen außer CDU – Grüne
nur Linke – SPD/Volt 4 und drei einzelne.

**Die AfD stellt kein gemeinsames Dokument**, in keiner Periode (0 von 10, 183, 265 Dokumenten). Die zwei
Treffer, die `parteien` in 2014-2020 lieferte (`01/ 29/2016` „AfD keine Plattform geben", `01/ 30/2016`
„Veranstaltung der AfD im Congress Center"), sind der Gegenstand, nicht der Mitantragsteller. Ob die
übrigen Fraktionen Anträgen der AfD zustimmen, sagen erst die Abstimmungen (§ 3.12).

### 3.11 Ein Maß für Konkordanz gegen Konkurrenz

Je Fraktionsdokument ein **Lager**: allein Mehrheit, allein Opposition, gemeinsam innerhalb der Mehrheit,
gemeinsam innerhalb der Opposition, **über die Grenze** (mindestens eine Fraktion jeder Seite), ohne
Partei. Drei Anteile:

- **K1** = über die Grenze / alle gemeinsamen. Hängt daran, wie oft die Mehrheit ihre eigenen Anträge
  bündelt (die Art „Antrag CDU/Grüne" hebt den Nenner).
- **K2** = über die Grenze / alle Fraktionsdokumente mit Partei.
- **K3** = über die Grenze / alle Dokumente mit Beteiligung der Opposition: **wie oft trägt eine Fraktion
  der Mehrheit ein Dokument der Opposition mit.** Das ist das Hauptmaß: es hängt weder an der Bündelung
  der Mehrheit noch an der Zahl ihrer Anfragen, und es fragt, was Holtkamp* mit Konkordanz meint, aus der
  Sicht der Opposition. Gerechnet auf Initiative und Symbol (Anfragen werden selten gemeinsam gestellt).

| Ebene | Periode | Fraktionsdokumente (Kontrolle, Initiative, Symbol) | K1 Initiative | K2 Initiative | **K3 Initiative** (Wilson-95-%) | K3 alle Funktionen |
|---|---|---|---|---|---|---|
| Rat und Ausschüsse | 2014-2020 | 2 569 | 49 / 397 (12,3 %) | 4,5 % | **49 / 665 (7,4 %; 5,6–9,6)** | 50 / 1 565 (3,2 %) |
| | 2020-2025 | 3 418 | 43 / 476 (9,0 %) | 2,4 % | **43 / 1 351 (3,2 %; 2,4–4,3)** | 43 / 2 735 (1,6 %) |
| | 2025- | 837 | 0 / 40 (0,0 %) | 0,0 % | **0 / 314 (0,0 %; 0–1,2)** | 1 / 778 (0,1 %) |
| Bezirksvertretungen (Näherung) | 2014-2020 | 5 998 | 506 / 676 (74,9 %) | 14,7 % | 506 / 1 578 (32,1 %; 29,8–34,4) | 28,8 % |
| | 2020-2025 | 4 383 | 231 / 401 (57,6 %) | 9,3 % | 231 / 979 (23,6 %; 21,0–26,4) | 16,0 % |
| | 2025- | 889 | 103 / 105 (98,1 %) | 24,0 % | 103 / 220 (46,8 %; 40,3–53,4) | 28,1 % |

**Was über die Grenze geht, ist meist ein Allparteienantrag.** Von den Dokumenten über die Grenze in Rat
und Ausschüssen haben 42 von 50 (2014-2020) und 27 von 43 (2020-2025) mindestens vier Fraktionen:
„Resolution gegen Fremdenfeindlichkeit" (`01/ 17/2015`), „Resolution gegen Antisemitismus"
(`RAT/389/2021`), „Aufnahme Geflüchteter aus Afghanistan" (`RAT/525/2021`), „Konzept und Projektgruppe
für die Umbenennung von Düsseldorfer Straßen" (`RAT/461/2021`). Zweiseitige Zusammenarbeit zwischen einer
Mehrheits- und einer Oppositionsfraktion ist in der Stadtpolitik fast nicht zu sehen.

**Arbeitsteilung in der Mehrheit** (Rat und Ausschüsse): die Ampel stellte ihre Initiativen zu 82,8 %
gemeinsam, ihre Anfragen nur zu 4,7 %; CDU und Grüne 87,0 % und 62,4 % (2020-2025), ab 2025 94,7 % und
95,2 %. Kontrollanteil je Lager, alle Dokumente: 2014-2020 Mehrheit 57,9 %, Opposition 59,3 %; 2020-2025
32,4 % gegen 51,4 %; ab 2025 35,6 % gegen 59,6 %.

**Lesart.** In Rat und Ausschüssen ist Düsseldorf in allen drei Perioden eine Konkurrenzdemokratie im
Sinne Holtkamps*: die Mehrheit beantragt gemeinsam, die Opposition allein, und was beide Seiten zusammen
stellen, sind meist Erklärungen und Grundsatzfragen von vier bis sechs Fraktionen, nie mit der AfD. Der
Anteil sinkt von Periode zu Periode (7,4 → 3,2 → 0,0 %; nach Variante B 7,5 %, 3,2 % und 0 von 312); die
laufende Periode ist 13 Monate alt. Die
Bezirksvertretungen sind anders: dort trägt in einem Viertel bis fast der Hälfte der Initiativen mit
Oppositionsbeteiligung eine Fraktion der Ratsmehrheit mit. Weil die Mehrheiten der Bezirke nicht im
Datensatz stehen, ist das dort **kein** Konkordanzmaß, sondern nur die Aussage, dass die Lager des Rates in
den Bezirken nicht gelten.

### 3.12 Was erst die Abstimmungen zeigen (Vorhaben 28)

Gemeinsame Anträge messen **Kooperation beim Antragstellen**, nicht beim Entscheiden. Nicht messbar ohne
Beschlüsse und Stimmen:

- ob Initiativen der Opposition **angenommen** werden — auch einstimmig, ohne dass jemand mitzeichnet;
- **Ersetzungsanträge**: die Mehrheit lehnt einen Oppositionsantrag ab und beschließt einen eigenen zum
  selben Gegenstand (über die Kanten von Vorhaben 14 sichtbar, ihr Ergebnis erst mit Vorhaben 26);
- **Einstimmigkeit** und „mehrheitlich gegen die Stimmen der …": die zweite Hälfte der Konkordanz;
- der **Umgang mit Anträgen der AfD** (WZB-Schwelle: Zustimmung aus den übrigen Fraktionen);
- in den Bezirksvertretungen überhaupt erst, wer Mehrheit ist (Vorhaben 27, Mitgliedschaften).

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

**Was schon deterministisch geprüft ist** (§ 3.5): die Tabelle der Dokumentarten gegen die Beratungsrolle
(98,7 %), die Textregel der Verwaltungsvorlage an Dokumenten bekannter Art (95,9 %), das Textwort gegen
das Titelwort (99,5 %). **Was es nicht prüft**: ob ein Antrag, der nur einen Bericht verlangt, Kontrolle
ist; ob eine Forderung an das Land Symbolpolitik ist; ob die Textregeln in der alten Vorlagenform so gut
sind wie in der neuen; ob die Antragsteller stimmen. Das prüfen die Kodier-Agenten.

**Codebuch** `validierung/15-funktion/codebuch.toml` (Version 2026-11-23.1, vorläufiges Format wie
Vorhaben 14, F4 baut den Rahmen). Einheit: ein Dokument. Ein Grundsatz („maßgeblich ist, was das Gremium
mit dem Dokument tun soll, nicht das Thema und nicht die Dokumentart") und drei Fragen:

1. `funktion` (kontrolle, information, initiative, symbol, vollzug, rest, unklar) mit Definitionen und
   Beispielen; bei zwei passenden entscheidet der Beschlusstext, bei mehreren Punkten der erste.
2. `urheber` (Mehrfachauswahl aus den Fraktionen der Periode, dazu Verwaltung, Einzelmitglied, Beirat,
   Bürger, interfraktionell ohne Namen, andere, unklar): nur die Verfasser, nicht der Gegenstand, nicht die
   Verfasser eines Antrags, auf den sich das Dokument bezieht.
3. `adressat` (stadt, dritte, beide, keiner, unklar): trennt Initiative von Symbolpolitik und entscheidet
   zwischen Variante A und B; wird nicht selbst gewertet.

Die Funktion und die Antragsteller des Regelwerks stehen **nicht** in der Aufgabe, auch die Schicht nicht
(sie verrät die Funktion).

**Stichprobe** `validierung/15-funktion/stichprobe.csv` (Spalten `id`, `schicht`; nur IDs), 150 Dokumente,
Seed 15, Schichten in Vorrangfolge (ein Dokument gehört zur ersten passenden):

| Schicht | Population | gezogen |
|---|---|---|
| `abweichung_ab` (Variante A und B verschieden) | 257 | 10 |
| `rest` | 1 231 | 15 |
| `symbol` (Variante A) | 39 | 15 |
| `gemeinsam` (mindestens zwei Fraktionen) | 2 734 | 20 |
| `sammelart` (Vorlage aus der Politik, Verwaltungsvorlage) | 15 404 | 15 |
| `kontrolle` | 5 490 | 20 |
| `information` | 5 968 | 15 |
| `initiative` | 6 021 | 20 |
| `vollzug` | 8 274 | 20 |

Perioden in der Stichprobe: 59 / 80 / 11. Klassen der Variante A darin: Information 19, Initiative 51,
Kontrolle 27, Rest 15, Symbol 15, Vollzug 23. Die Stichprobe hängt am Regelwerk (die Schichten); wer eine
Regel ändert, zieht sie mit demselben Seed neu, und das Skript meldet ohne `--stichprobe`, ob die
gespeicherte noch dieselbe ist.

**Kodieraufgaben** (nicht im Repo): `/media/konrad/xtraspace/georep/messdaten/kodierung/15-funktion/aufgaben.jsonl`,
150 Zeilen, rund 1,1 MB. Je Zeile: `id`, `codebuch`, `periode`, `drucksache`, `titel`, `dokumentart`,
`datum`, `gremium`, `textquelle` (alle 150 `rohtext`), `textanfang` (höchstens 1 500 Zeichen, mit Groß-
und Kleinschreibung und Zeilenumbrüchen aus dem Rohtext von Phase 0), `grundsatz`,
`fraktionen_der_periode` und `fragen` aus dem Codebuch.

**Maße** (nach F4): **Cohens κ zwischen Regelwerk und Endlabel** `funktion`, ungewichtet an den 150 (das
Kriterium), je Variante A und B; dazu mit den Schichtgrößen gewichtet (die Zahl über den Korpus; die
großen Schichten `sammelart` und `vollzug` tragen dann viel Gewicht mit wenigen Kodierungen). Präzision
und Recall je Funktion mit Wilson-Intervall; `unklar` gezählt, nicht gewertet. Für `urheber`: Anteil exakt
gleicher Mengen und für die Schicht `gemeinsam` die Präzision von „mindestens zwei Fraktionen"; α je Frage
zwischen den Kodierern (Stufe 3 verlangt ≥ 0,8).

**Was κ ≥ 0,7 hier verlangt.** Bei der Klassenverteilung der Stichprobe ist die Zufallsübereinstimmung
p_e = 0,208 (unter gleichen Randverteilungen), κ = 0,7 also eine Trefferquote von mindestens 0,762:
**höchstens 35 Abweichungen an 150**. Die Schichten sind bewusst schwer (55 der 150 sind Abweichung,
Rest, Symbol oder Sammelart); auf dem Korpus gewichtet wird die Trefferquote höher liegen als an der
Stichprobe. **Supervisor-Entscheidung vor der Kodierung (Frage 17 in `fragen-2026-11.md`)**: die Schicht
`rest` zählt nicht zum κ-Kriterium; κ wird an den Dokumenten gemessen, denen das Regelwerk eine Funktion
gibt, und was die Kodierer in der Restklasse sehen, steht daneben (§ 4.2).

### 4.1 Ergebnis der Kodierung (2026-11-23)

Zwei Kodier-Agenten (Opus) haben die 150 Dokumente unabhängig nach `codebuch.toml` (Fassung
2026-11-23.1) kodiert; ein Schlicht-Agent hat die zwei uneinigen Aufgaben entschieden (drei Felder:
`40/ 1/2017 - 1` `funktion` = vollzug und `adressat` = stadt, wie Kodierer A; `RAT/412/2023` `adressat`
= keiner). Kein menschlicher Goldstandard. Endlabel = gleiche Antwort, sonst Schlichtung:
`validierung/15-funktion/labels.csv` (je Aufgabe und Frage, Werte als JSON). Ausgewertet vom
Messskript (Abschnitt „4.1 Auswertung der Kodierung"), Läufe um 19:37 bis 19:45 Uhr, 21,0 bis 94,4 s
bei Lastmittel 22 bis 37; die Auswertung braucht nur `labels.csv`, nicht die lokalen Antworten.

| Frage | gleich kodiert | Krippendorffs α (nominal) | geschlichtet |
|---|---|---|---|
| `funktion` | 149 / 150 | 0,992 | 1 |
| `urheber` | 150 / 150 | 1,000 | 0 |
| `adressat` | 148 / 150 | 0,970 | 2 |

**Die Übereinstimmung ist ein schwacher Beleg.** Beide Kodierer sind dasselbe Modell mit fast gleichem
Auftrag; sie teilen ihre Lesarten und damit ihre Fehler, und α misst eher die Beständigkeit des Modells
als die Zuverlässigkeit der Kodierung (Frage 19 in `fragen-2026-11.md`: Kodierer B künftig ein anderes
Modell). Die Bedingung der Stufe 3 (α ≥ 0,8) ist formal erfüllt; die Seite nennt Modell und Verfahren.
Beide Kodierer markieren rund 30 Aufgaben als unsicher, vor allem die alten Vorlagen, deren Textanfang
nur eine Anlage ist.

Labels `funktion`: Kontrolle 39, Initiative 37, Vollzug 29, Information 24, Symbol 19, unklar 2 (beide
in der Schicht `rest`), Restklasse 0.

**Funktion: Regelwerk gegen Label.** Basis nach Frage 17: die 135 Dokumente außerhalb der Restklasse (die
beiden `unklar` liegen in ihr). Intervall für κ: Perzentil-Bootstrap über die Dokumente (2 000
Ziehungen, Seed 15); für die Trefferquote Wilson. „Gewichtet" heißt mit den Schichtgrößen aus
`stichprobe.csv` hochgerechnet auf den Korpus.

| | κ (95 %) | Treffer (Wilson 95 %) | gewichtet: κ / Treffer |
|---|---|---|---|
| **Variante B** | **0,905** (0,840–0,960) | 125 / 135 = 0,926 (0,869–0,959) | 0,877 / 0,907 |
| Variante A | 0,829 (0,748–0,900) | 117 / 135 = 0,867 (0,799–0,914) | 0,871 / 0,902 |
| zum Vergleich mit der Restklasse (148, ohne die 2 `unklar`): B / A | 0,806 (0,729–0,873) / 0,739 (0,655–0,813) | 125 / 148, 117 / 148 | |

Konfusion der Variante B (Zeile Regelwerk, Spalte Label):

| | Kontrolle | Information | Initiative | Symbol | Vollzug | Präzision |
|---|---|---|---|---|---|---|
| Kontrolle | **34** | 0 | 1 | 0 | 0 | 34 / 35 |
| Information | 0 | **19** | 0 | 0 | 0 | 19 / 19 |
| Initiative | 5 | 0 | **33** | 3 | 0 | 33 / 41 |
| Symbol | 0 | 0 | 1 | **16** | 0 | 16 / 17 |
| Vollzug | 0 | 0 | 0 | 0 | **23** | 23 / 23 |
| Recall | 34 / 39 | 19 / 19 | 33 / 35 | 16 / 19 | 23 / 23 | |

Je Schicht (B / A): Abweichung A–B 9/10 / 1/10, gemeinsam 17/20, Information 15/15, Initiative 18/20,
Kontrolle 20/20, Sammelart 12/15, Symbol 14/15, Vollzug 20/20 (außer der ersten Schicht in A und B
gleich). **Alles, was die Verwaltung vorlegt, und jede Anfrage ist richtig**; die Fehler liegen bei
Anträgen und Vorlagen aus der Politik:

- **Antrag, der nur Auskunft verlangt, ohne die Wörter der Berichtsregel** (5, Kontrolle-Recall 34/39):
  `AUS/057/2021` (Antrag CDU/Grüne), `BV3/047/2020`, `BV7/020/2024`, `170/ 43/2016`, `170/ 65/2015`.
- **Symbolpolitik ohne Titel- oder Textmarker** (3): `RAT/526/2021` (Antrag CDU/Grüne), `BV10/027/2026`
  („Konsequenzen aus der Veranstaltung der AfD im Kulturhaus Süd"), `170/ 21/2016`.
- **Berichtsantrag, der eine Initiative ist** (1): `RAT/464/2024` (Haushaltsantrag CDU/Grüne).
- **Symbol nach Titel, das die Kodierer als Initiative lesen** (1): `01/ 251/2019` (Änderungsantrag der CDU
  zum „Palermo-Appell", dessen erster Punkt eine Sachentscheidung ist).

**Variante A gegen B — ein Entwurfsvergleich, keine Messung der gewählten Variante.** Die Schicht
`abweichung_ab` entscheidet: A trifft 1 von 10, B 9 von 10 (sieben Berichtsanträge, die die Kodierer als
Kontrolle lesen, zwei Erklärungen aus dem Beschlusstext als Symbol, ein Haushaltsantrag falsch). Weil B
an denselben Labels gewählt wird, an denen es gemessen ist, ist κ_B = 0,905 eine optimistische Zahl.
Unabhängig von der Wahl gilt: **beide vorab festgelegten Varianten erfüllen das Kriterium**, auch mit
der Restklasse, und die konservative Zahl ist die untere Grenze von A (0,748). Auf dem Korpus gewichtet
liegen die Varianten nah beieinander (κ 0,877 gegen 0,871), weil nur 257 Dokumente verschieden sind. Die
Fehlermuster oben sind **keine** Regeländerung dieser Runde: wer die Berichtsregel nach ihnen erweitert,
misst an einer neuen Stichprobe (Lehre aus Vorhaben 14, § 4.2: die Entwurfsschätzung an alten Labels lag
dort 0,135 zu hoch).

**Urheber: Regelwerk gegen Label.** Verglichen werden die Optionen des Codebuchs; das Regelwerk liefert
für Fraktionsdokumente die Fraktionen (§ 3.8), sonst Verwaltung, Einzelmitglied (Urheberklasse Person),
Bürger (Eingabe) oder unklar (unbekannt). Gegenprobe ist `parteien` aus `dokumente_urheber`, auf
Fraktionen abgebildet.

| | exakt gleiche Urheber | Fraktionen: Präzision | Fraktionen: Recall | gemeinsame des Labels (30): erkannt / exakt / falsch gemeinsam |
|---|---|---|---|---|
| **Regelwerk** (Art, Autorenteil, Briefkopf) | **130 / 150** | **119 / 119 = 1,000** | 119 / 138 = 0,862 | 26 / **26** / 0 |
| `parteien` (erste Quelle gewinnt) | 126 / 150 | 115 / 117 = 0,983 | 115 / 138 = 0,833 | 25 / 23 / 1 |

Recall je Fraktion (Regelwerk): CDU 35/38, Grüne 28/33, SPD/Volt 15/18, Linke 14/20, FDP 13/15, SPD
(2014-2020) 6/6, Tierschutz/FW 4/4, PARTEI 2/2, AfD 1/1, FW/Tierschutz/PARTEI 1/1. Die zwei Parteien,
die `parteien` zu viel nennt, sind der Befund aus § 3.8: `BV10/027/2026` (die AfD aus dem Gegenstand)
und `01/ 43/2016` (SPD aus dem Fenster um den Briefkopf). **Damit bestätigt die Kodierung den Rückstand
in `docs/todo.md`, Punkt 9**: vereinigte Quellen statt der ersten und kein Gegenstand im Titel —
gemeinsame Dokumente exakt 26 statt 23 von 30, keine falsche Fraktion statt zwei.

Die 19 fehlenden Fraktionen liegen nicht im Antragsteller-Schritt, sondern **eine Ebene davor, in der
Urheberklasse**: 8 Dokumente mit Urheber „unbekannt", die die Kodierer einer Fraktion geben (10 der 19;
Vorlagen aus der Politik 2014-2020 ohne Fraktionswort im Briefkopf: `01/ 153/2016`, `01/ 175/2014`,
`01/ 175/2016`, `170/ 65/2015`, alle Linke; dazu `BV3/047/2020`, `BV8/028/2019`, `BV9/025/2020`,
`AGS/006/2024`), 2 Einzelmitglieder, deren Partei die Kodierer als Fraktion kodieren (`BV10/066/2021`,
`BV9/191/2023`; eine Lücke des Codebuchs, § 4.3), und 2 interfraktionelle Anträge, deren Fraktionen nur
im Text stehen (7 der 19; `BV1/224/2022`, `BV5/074/2024`). Dazu zwei Eingaben nach § 24 GO, die 2014-2020 als
Verwaltungsvorlage geführt sind (`12/ 12/2017`, `173/ 89/2016`: Label Bürger, Regelwerk Verwaltung).
Hochgerechnet ist die Klasse „unbekannt" (2 356 Dokumente 2014-2020, 327 und 84 danach) die größte
Lücke; sie gehört zu Punkt 9 des Rückstands, nicht zu diesem Vorhaben.

**Adressat**: das Regelwerk vergibt keinen; die Frage diente der Kodierung als Hilfe. Label `funktion` ×
`adressat`: Kontrolle 38 Stadt, 1 beide; Information 24 keiner; Initiative 37 Stadt; Vollzug 29 Stadt;
**Symbol uneinheitlich**: 5 Dritte, 3 beide, 5 keiner, 5 Stadt, 1 unklar. Ein Merkmal „richtet sich an
Dritte" träfe also weniger als die Hälfte der Symbolpolitik (ein Bündnisbeitritt richtet sich an die
Stadt, eine Erklärung an niemanden); die Textmarker der Variante B treffen 16 von 17.

### 4.2 Was die Kodierer in der Restklasse sehen

Die 15 Dokumente der Schicht `rest` (alle Verwaltungsvorlagen 2014-2020) bekommen von den Kodierern
**Vollzug 6, Information 5, Initiative 2, unklar 2**, also 13 von 15 eine Funktion. Die zwei Initiativen
sind Eingaben nach § 24 GO, die unter `Verwaltungsvorlage` liegen (`12/ 12/2017`, `173/ 89/2016`); die
zwei `unklar` sind `61/ 23/2017` und `66/ 134/2018`. Kodierer A markiert 9 der 15 als unsicher,
Kodierer B 12 (nur in den lokalen Antworten, nicht in `labels.csv`): sie haben die Funktion meist aus
Titel und Anlage erschlossen. **Die Restklasse heißt also nicht „Dokument ohne Funktion", sondern
„Funktion aus Art, Titel und Textanfang nicht erkannt"** — fast immer, weil der Text fehlt oder mit einer
Anlage beginnt (§ 3.4). Für die 1 231 Dokumente ist das eine Verteilung aus 15 und kein Grund, die Regel
zu ändern; die Seite nennt die Klasse „Funktion nicht erkannt".

### 4.3 Lücken des Codebuchs: Vorschlag für Fassung .2

Aus beiden Rückmeldungen (`rueckmeldung-A.md`, `rueckmeldung-B.md`) und der Schlichtung, lokal unter
`messdaten/kodierung/15-funktion/`. Das Codebuch im Repo bleibt Fassung .1, nach der kodiert ist; .2 gilt
für die nächste Kodierung (eine Bestätigung mit zweitem Modell nach Frage 19 oder die Erweiterungen von
`akteure.html` durch 24, 27, 28).

1. **Einzelmitglied mit Partei** (beide Kodierer; sieben Fälle bei A): ein Rats- oder
   Bezirksvertretungsmitglied ohne Fraktion, das seine Partei nennt, oder ein Mitglied, das allein für
   eine Gruppe zeichnet. Heute kodierten beide die Partei als Fraktion. Vorschlag: `einzelmitglied`
   bleibt die Option, die Partei kommt in ein eigenes Feld `partei_des_mitglieds`; zeichnet ein Mitglied
   ausdrücklich „für die Fraktion/Gruppe", ist es die Fraktion. Das hält die Urheberklasse Person von der
   Fraktion getrennt, wie `parties.py` es tut.
2. **Sondergremien**: ein Mitglied des Jugendrats oder Integrationsrats ist `beirat_oder_sondergremium`,
   eine Liste des Integrationsrats (etwa „Grüne internationale offene Liste") `andere` mit Namen; ein
   Verein, der eine Eingabe nach § 24 GO stellt, ist `buerger`.
3. **Symbol gegen Initiative, wenn die Stadt bei Dritten etwas anstoßen soll** (beide; „DB-Bitte"):
   Symbolpolitik nur, wenn das Gremium eine Haltung erklärt (Resolution, Appell, Verurteilung,
   Solidarität, Bündnisbeitritt) oder Dritte zu Politik in deren Zuständigkeit auffordert; eine sachliche
   Bitte um eine bestimmte Maßnahme eines Dritten für die Stadt (die Bahn soll einen Aufzug bauen, die
   Verwaltung soll das bei ihr erwirken) ist `initiative` mit `adressat` dritte oder beide.
4. **Erster Punkt und abgeschnittener Beschlusstext** (Schlichtung): `funktion` und `adressat` werden am
   selben Punkt kodiert, dem ersten, soweit sichtbar; `adressat` = unklar nur, wenn gar kein Beschlusstext
   im Textanfang steht; eine Erklärung des Gremiums ohne genannten Handelnden ist `keiner`.
5. **Nur eine Anlage im Textanfang** (beide, Schlichtung): kodiert wird der Zweck, den Art, Titel und
   Anlage zusammen erkennen lassen (Entwurfspläne eines städtischen Bauvorhabens in einer
   Verwaltungsvorlage: Vollzug; Tabellen eines Berichts: Information); `unklar` nur ohne erkennbaren
   Zweck; `rest` bleibt Dokumenten, die selbst keine der fünf Funktionen haben.
6. **Mischtexte** (A): Fragen und Antrag in einem Dokument — der Beschlusstext entscheidet; stehen nur
   Fragen da, ist es Kontrolle, auch wenn der Titel „Antrag" sagt (so haben beide schon kodiert; das
   Codebuch sollte es sagen).

## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

**Kriterium** (Briefing, unverändert): κ ≥ 0,7 gegen 150 kodierte Dokumente, Restklasse ≤ 10 %; nach der
Supervisor-Entscheidung vor der Kodierung (Frage 17) wird κ an den Dokumenten gemessen, denen das
Regelwerk eine Funktion gibt.

- **κ: erfüllt.** Variante B 0,905 (Bootstrap-95-% 0,840–0,960), Variante A 0,829 (0,748–0,900), an 135
  Dokumenten; gewichtet 0,877 und 0,871. Auch mit der Restklasse, wie vor Frage 17 vorgesehen, liegen
  beide darüber (0,806 und 0,739). Die untere Intervallgrenze von A, der Variante, die nicht an diesen
  Labels gewählt ist, liegt über 0,7.
- **Restklasse: erfüllt.** 5,5 % in der Periode 2014-2020, 0 % in den beiden anderen, 2,7 % über alle
  Düsseldorfer Dokumente; Mönchengladbach 0 %. Die Kodierer geben 13 der 15 Dokumente der Restklasse eine
  Funktion (§ 4.2): die Klasse misst, was das Regelwerk nicht sehen kann, nicht Dokumente ohne Funktion.
- **Grenze des Belegs**: zwei Kodierer desselben Modells, kein Mensch (Frage 19); die Übereinstimmung von
  149 aus 150 sagt, dass das Modell sich treu ist, nicht, dass es recht hat. Die Fehler des Regelwerks
  liegen genau dort, wo auch ein Mensch zögern würde (Antrag oder Berichtswunsch, Initiative oder
  Erklärung); Vollzug und Information, die beiden großen Klassen der Verwaltung, sind an den Labels
  fehlerfrei.

**Urteil: bauen, mit Variante B.** Die Wahl folgt der Regel, die vor der Kodierung in Frage 9.1 stand
(B, wenn κ_B ≥ κ_A und die Präzision von Symbol in B ≥ 0,8; gemessen 0,905 ≥ 0,829 und 16/17 = 0,94).
Weil B an denselben Labels gewählt und gemessen ist, nennt die Seite für die Funktion das Intervall von B
und dazu die Zahl von A als vorsichtige Untergrenze. Eine zweite Runde ist für das Kriterium nicht nötig;
eine Bestätigung mit einem zweiten Modell als Kodierer gehört zu Frage 19.

Änderungen am Briefing, bestätigt durch die Kodierung:

1. **Die Mitantragsteller kommen nicht aus `parteien`**, sondern aus einer eigenen Spalte Antragsteller
   (Dokumentart, Autorenteil des Titels, Verfasserblock des Briefkopfs; § 3.8), zu **Fraktionen**
   zusammengefasst (SPD/Volt). An den Labels: Präzision 119/119, gemeinsame Dokumente 26 von 30 exakt
   (`parteien` 23 und ein falsches). `analysis/parties.py` bleibt unverändert; der Rückstand dazu steht
   in `docs/todo.md`, Punkt 9, und die Kodierung erweitert ihn um die Urheberklasse „unbekannt" (Frage
   9.15).
2. **Konkordanz nur in Rat und Ausschüssen.** In den Bezirksvertretungen gibt es keine Lager im Datensatz;
   dort zeigt die Seite das Netz, nicht K3.
3. **Symbolpolitik ist eine kleine Klasse** (110 Dokumente in elf Jahren nach Variante B). Die Seite zeigt
   sie als Liste mit Drucksachen, nicht als Anteil je Fraktion.
4. **Instrumente je Fraktion nur gegen die Praxis der Gremien** (beobachtet/erwartet), die rohen Anteile
   nur daneben, wie in Vorhaben 14.
5. **Die Restklasse heißt auf der Seite „Funktion nicht erkannt"** (§ 4.2).

Nicht in dieser Runde geändert, obwohl die Labels es nahelegen: eine breitere Berichtsregel (fünf
Anträge, die nur Auskunft verlangen, liest das Regelwerk als Initiative) und Marker für Symbolpolitik ohne
die Wörter der Titelregel (drei). Beides wäre an denselben Labels nachgebaut und bräuchte eine neue
Stichprobe; an den Labels betrifft es 8 der 41 Dokumente, die das Regelwerk als Initiative führt
(Präzision der Initiative 33/41).

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

**Beitrag `functions`** nach F2 (`src/georep/enrich/functions.py`), zwei Schritte, beide offline, hinter
`bodies` und `parties` (liest deren Ausgaben), im Register vor den Beiträgen, die `akteure.html`
erweitern (24, 27, 28):

1. `functions`: Korpus (`id`, `name`, `paper_type`, `text`), `dokumente_urheber`. Schreibt
   `processed/dokumente_funktion.parquet`.
2. `cosponsors`: Korpus, `dokumente_urheber`, `papers_gremien`, Settings. Schreibt
   `processed/mitantraege.parquet`.

**Ausgaben** (Schema-Version aus der Modulkonstante `FUNCTIONS_SCHEMA_VERSION = 1`):

| Datei | Spalten | Schlüssel, Ordnung |
|---|---|---|
| `dokumente_funktion.parquet` | `id` str, `funktion` str (`kontrolle`, `information`, `initiative`, `symbol`, `vollzug`, `rest`), `instrument` str, `quelle` str (`art`, `titel`, `text`, leer bei `rest`), `variante` str (`A` oder `B`, aus den Settings) | eine Zeile je Korpus-ID, sortiert nach `id` |
| `mitantraege.parquet` | `id` str, `antragsteller` list[str] (Parteischlüssel), `fraktionen` list[str] (Fraktionen), `quelle` str (`art`, `titel`, `briefkopf`, `parteien`, mehrere mit `+`), `gemeinsam` bool, `lager` str (`allein_mehrheit`, `allein_opposition`, `gemeinsam_mehrheit`, `gemeinsam_opposition`, `ueber_grenze`, `ohne_partei`, `ohne_lager`) | eine Zeile je Korpus-ID (leere Listen, wo die Urheberklasse nicht Fraktion ist), sortiert nach `id` |

Die Kanten des Netzes und K1 bis K3 entstehen auf der Seite aus `mitantraege` (`report.pages.Page.data`),
nicht als dritte Datei: sie sind eine Gruppierung, und eine Kantentabelle müsste ihre eigenen Filter
(Gremienart, Funktion) mitschreiben.

**Verträge** (an den Batch-Grenzen, Prädikate in `georep.contracts`): genau eine Zeile je Korpus-ID in
beiden Dateien (`one_row_per_document`); `funktion` aus der Aufzählung; `quelle` leer genau bei `rest`;
`instrument` gehört zu seiner Funktion (Tabelle im Modul); `antragsteller` ⊆ Schlüssel der Settings,
sortiert in Settings-Folge, eindeutig; `fraktionen` = Bild von `antragsteller` unter der Fraktionstabelle;
`gemeinsam` ⇔ `len(fraktionen) >= 2`; `antragsteller` leer, wo `urheber_art != "Fraktion"`; `lager =
ohne_lager` genau dort, wo das Gremium nicht auf der Stadtebene liegt oder das Profil keine Mehrheit für
das Datum kennt. Nach jedem Join sortieren.

**Settings** (Anhängeregel aus F2: Modell `Functions` vor `class Settings`, Feld am Ende, Block am Ende
von `defaults.toml` mit `# --- Vorhaben 15: Dokumentfunktion und gemeinsame Anträge`, Schalter aus):

```toml
[functions]                     # Vorhaben 15; alle Muster und Tabellen im Stadtprofil, kein Stadtwort im Code
enabled = false
variant = "B"                   # gewählt nach der Kodierung (Messdokument Vorhaben 15, § 5; A bleibt als Schalter)
head_chars = 700                # Textkopf der Sammelarten
wide_chars = 3000               # zweiter Blick der Verwaltungs-Sammelart
types = {}                      # paper_type -> "funktion/instrument", ganzer Wert
type_prefixes = {}              # Präfix (klein) -> "funktion/instrument", längste zuerst
collection_political = []       # Sammelarten der Politik (Titel, dann erstes Instrumentwort im Text)
collection_admin = []           # Sammelarten der Verwaltung (Kenntnis gegen Beschluss)
symbol_title = []               # Muster, die eine Initiative aus der Politik zur Symbolpolitik machen
symbol_text = []                # Variante B
report_request = []             # Berichtsantrag (Titel und Text)
not_instruments = []            # Bauantrag, Bauvoranfrage, ...
letterhead_authors = ""         # Verfasserblock des Briefkopfs (Düsseldorf 2014-2020), Ende als Regex
title_author_stop = []          # Trenner des Autorenteils
[[functions.fractions]]         # Fraktion aus mehreren Parteischlüsseln, mit Zeitraum
[[functions.majorities]]        # Ratsmehrheit: von, bis, Parteien, Quelle (Drucksache und Zitat)
```

Düsseldorf trägt die Dokumentarten aller drei Perioden, die Sammelarten von 2014-2020, die beiden
Fraktionen aus mehreren Parteien und drei Mehrheiten mit Datum und Drucksache (§ 3.9) **im Stadtprofil**,
nicht im Periodenprofil, aus demselben Grund wie Punkt 57 und 60: die Vorlagenform und die Mehrheiten
gehören der Stadt, und `deep_merge` ersetzt Listen. Mönchengladbach trägt seine 16 Arten und keine
Mehrheit (der Abschnitt Konkordanz entfällt dort). Die Fraktionstabelle wird überflüssig, sobald F6
`raw/organizations.json` für Düsseldorf abruft: `Patterns.with_organizations` bildet schon heute
„Ratsfraktion SPD/Volt" auf SPD und VOLT ab (Frage 9.3).

**Tests.** Beispiele: je Regel ein Dokument (die Fälle aus § 3.1 und § 3.8, darunter „Anfrage zu einer
Resolution" → Kontrolle, „Informationsvorlage: Resolution …" → Information, Bauvoranfrage keine Anfrage,
„Änderungsantrag der SPD zum Antrag von CDU und Grünen" → nur SPD, „Antrag Die Linke: AfD keine
Plattform" → nur Linke, „Haushaltsantrag CDU/Grüne" mit drei Fraktionen im Titel → drei, Briefkopf 2014
mit zwei Fraktionen, SPD und Volt → eine Fraktion, alle 16 Arten Mönchengladbachs). **hypothesis**: die
Funktion ist total und deterministisch (jede Eingabe bekommt genau eine der sechs, dieselbe bei
gleicher Eingabe); ein Text hinter einem Trenner des Titels ändert die Antragsteller nicht (zufälliger
Gegenstand mit Parteinamen nach „: "); die Antragsteller sind unabhängig von der Zeilenfolge; `lager`
ist für jede Zufallsmenge von Fraktionen und jede Mehrheit eine der sieben Klassen und symmetrisch in der
Reihenfolge. Mini-Fixture: ein Dutzend Dokumente mit bekannten Funktionen und Antragstellern. **slow**,
Golden auf allen drei Perioden: die Abdeckungstabelle der Variante B (§ 3.2), die gemeinsamen Dokumente
(§ 3.8), K3 (§ 3.11), und **die Validierung als Regressionstest**: an `validierung/15-funktion/labels.csv`
muss κ der Funktion ≥ 0,7 bleiben (heute 0,905) und die Präzision der Fraktionen 1,0 (119/119); ein Umbau
der Regeln, der eine dieser Zahlen senkt, ist kein Refactoring. Kein Netz, kein Modell.

**Berührte Dateien.** Neu: `src/georep/enrich/functions.py`, `src/georep/analysis/functions.py` (Regeln,
rein), `src/georep/analysis/cosponsors.py` (Antragsteller, Fraktionen, Lager),
`tests/unit/test_functions.py`, `tests/unit/test_cosponsors.py`, `tests/property/test_functions.py`,
`tests/golden/test_functions.py`. Geändert mit einer Zeile oder einem Block: `src/georep/enrich/__init__.py`,
`src/georep/settings.py`, `src/georep/defaults.toml`, `src/georep/profiles/duesseldorf.toml`,
`src/georep/profiles/moenchengladbach.toml`, `docs/architecture.md` (Schrittabelle), `docs/decisions.md`
(Punkt ohne Nummer: „Antragsteller aus Art, Autorenteil und Briefkopf, nicht aus `parteien`",
„Konkordanz nur auf der Stadtebene"). Gelesen, nicht geändert: `src/georep/analysis/parties.py`
(`Patterns.from_settings` für die Parteimuster). Kein Paket: beide Schritte rechnen offline aus dem, was die
Pakete schon tragen; das Regelwerk braucht für alle vier Datensätze zusammen rund 2 s (§ 3).

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

**Unterseite `akteure.html`** im Rahmen der Hauptseite (`report.pages.Page`, F2), je Profil mit
Fraktionsdokumenten; 24, 27 und 28 hängen später je einen Abschnitt an (Kontrolle in der Kooperation,
Personen, Abstimmungen). Die Seite ist **für alle Fraktionen gleich gebaut** (Meta-Plan, § 13, Risiko
Schlagseite).

1. *Funktionen der Dokumente*: je Periode eine gestapelte Leiste (SVG, sechs Klassen) für Verwaltung und
   Politik getrennt, darunter die Instrumente als Tabelle.
2. *Instrumente je Fraktion*: Dokumente, davon gemeinsam, Kontrolle, Initiative, Symbol, **beobachtet/
   erwartet gegen die Praxis der Gremien**, roh daneben, „explorativ" überschrieben; Fraktionen unter 30
   Dokumenten ohne Verhältnis.
3. *Wer mit wem*: das Netz als Matrix (Fraktion × Fraktion, Zellen = gemeinsame Dokumente, Farbe nach
   Lager), je Periode, umschaltbar Rat und Ausschüsse / Bezirksvertretungen; kein Graph-Layout, keine
   Bibliothek.
4. *Konkordanz*: K3 je Periode mit Wilson-Intervall und n, die Mehrheit mit Drucksache als Quelle, die
   Allparteienanträge als Liste, und der Satz, was erst die Abstimmungen zeigen (§ 3.12) — mit Link auf den
   Abschnitt, den 28 anhängt.
5. *Resolutionen und Appelle*: die Liste der Symbolpolitik mit Datum, Drucksache, Antragstellern und Link
   ins Ratsinformationssystem.

Größe geschätzt **40 bis 70 KB** (drei Matrizen von höchstens 9 × 9, fünf Tabellen, eine Liste von rund
40 Zeilen, drei Leisten). **Tabellen im Register**: `dokumente_funktion`, `mitantraege` (Parquet und CSV).
**Validierung auf der Seite**, im Wortlaut der Messung: „Funktion geprüft von zwei KI-Kodierern
desselben Modells (Claude Opus) an 150 Dokumenten, nicht von Menschen: das Regelwerk stimmt an 135
Dokumenten in 125 mit ihnen überein, κ = 0,91 (0,84–0,96; die nicht gewählte Variante 0,83). Die
Kodierer stimmten untereinander in 149 von 150 überein; bei zwei Kodierern desselben Modells ist das ein
schwacher Beleg." Dazu: „Antragsteller: 119 von 119 genannten Fraktionen bestätigt, 119 von 138
gefunden"; „Mehrheiten: Annahme mit Beleg im Korpus"; „Funktion nicht erkannt: 1 231 Vorlagen 2014-2020
ohne lesbaren Text". Stufe 3 zeigt nur, was validiert ist (Meta-Plan, § 2.6): `funktion` und `urheber`
tragen beide (κ ≥ 0,7, α ≥ 0,8), also alle fünf Abschnitte; ändert eine zweite Kodierung mit anderem
Modell (Frage 19) das Bild, zeigt die Seite ihre Zahlen.

## 8. Vorab festgelegte Hypothesen (nur Analysen: Hypothese, Maß, Test, Schwelle)

Keine; Vorhaben 15 ist beschreibend, und alles in § 3.7 und § 3.11 ist **explorativ** und steht so auf
der Seite. Weil die Zahlen jetzt bekannt sind, kann nur **neues Material** eine Hypothese prüfen. Zwei
Vorschläge an die Vorhaben, die sie vorab festlegen, beide prospektiv auf Dokumenten mit Datum nach dem
2026-10-13 (dem letzten Datum des heutigen Abrufs) bis zum Ende der laufenden Periode:

| Nr. | Hypothese | Maß | Test, Schwelle | für |
|---|---|---|---|---|
| H15.1 | Die Opposition nutzt die Kontrolle häufiger als die Mehrheit | Anteil Kontrolle an den Fraktionsdokumenten in Rat und Ausschüssen, Opposition minus Mehrheit, mit dem Gremium als Schicht | Cochran-Mantel-Haenszel über die Gremien, einseitig, α = 0,05 | 24 |
| H15.2 | Die Stadtebene bleibt Konkurrenz | K3 (Initiative, Rat und Ausschüsse) | exakter Binomialtest gegen p = 0,10, einseitig, α = 0,05 | 28 |

Explorativ gemessen, nicht geprüft: H15.1 hätte 2014-2020 nicht gegolten (57,9 % gegen 59,3 %), 2020-2025
schon (32,4 % gegen 51,4 %); H15.2 galt in allen drei Perioden. Wer eine These über die AfD formuliert
(keine Mitanträge in drei Perioden), braucht die Abstimmungen, nicht die Anträge.

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 9.1 | Variante A oder B: Berichtsantrag als Kontrolle, Symbol aus dem Beschlusstext? | 257 Dokumente; B verdreifacht die Symbolpolitik | **beantwortet durch die Kodierung: B** (κ_B 0,905 ≥ κ_A 0,829, Präzision Symbol 16/17), nach der vorab notierten Regel; an denselben Labels gewählt und gemessen (§ 4.1) |
| 9.2 | Reichen Korpusbelege für die Ratsmehrheit, oder braucht die Seite die Kooperationsvereinbarung als Quelle? | K3 hängt ganz an der Mehrheit | Korpusbelege mit Drucksache im Profil; Vorhaben 25 sammelt die Vereinbarungen und ersetzt die Quelle |
| 9.3 | Fraktionen aus mehreren Parteien: Profiltabelle oder `raw/organizations.json`? | ohne sie ist „SPD – Volt" die stärkste Kante ab 2025 | Profiltabelle mit Zeitraum bis F6 die Organisationen Düsseldorfs abruft, dann aus OParl |
| 9.4 | Zeigt die Seite K3 für Bezirksvertretungen? | dort gelten andere Mehrheiten | nein, nur das Netz, bis Vorhaben 27 die Mehrheiten der Bezirke kennt |
| 9.5 | `parteien` verliert Mitantragsteller (erste Quelle gewinnt, 281) und nennt bei 49 mehr Parteien als Art, Titel und Briefkopf, meist Gegenstände; 12 Anfragen des BSW sind Person ohne Partei. Nachziehen in Option 4? | die Seite zeigt Dokumente je Partei aus `parteien` | `parties.py` bleibt (Briefing); Vorhaben 15 rechnet eigene Antragsteller; Befund an den Supervisor für `docs/todo.md`, BSW als Gruppe im Profil der laufenden Periode |
| 9.6 | Ist die Eingabe nach § 24 GO eine Initiative? | 207 Dokumente | ja; die Urheberklasse Eingabe trennt sie von der Politik |
| 9.7 | Soll die Restklasse von 2014-2020 (1 231) weiter schrumpfen? | 5,5 %, unter dem Kriterium | nein; mit Rohtext (F1) und Abschnitten (11) später, nicht für dieses Kriterium |
| 9.8 | Zeigt die Seite Symbolpolitik je Fraktion? | kleine Zahlen, politisch heikel | nur die Liste der Dokumente, keine Rangfolge |
| 9.9 | Gilt die Mehrheit die ganze Periode? | ein Wechsel würde K3 verschieben | ja, bis ein Beleg anderes sagt; das Profil trägt Datumsgrenzen |
| 9.10 | Mönchengladbach: keine Mehrheit, keine Anfragen | der Abschnitt Konkordanz hätte keine Grundlage | Abschnitt entfällt ohne `[[functions.majorities]]`; Funktionen und Netz bleiben (73 Fraktionsanträge mit mindestens zwei Parteien) |
| 9.11 | Die laufende Periode ist 13 Monate alt: ist K3 = 0 ein Befund? | die Seite könnte eine junge Periode als Bruch lesen | die Seite nennt n und „laufend"; H15.2 prüft prospektiv |
| 9.12 | Schließt das Kriterium die Schicht `rest` ein? | 15 Dokumente, die das Regelwerk absichtlich offen lässt, kosten fast die Hälfte der erlaubten Abweichungen | **entschieden vor der Kodierung (Frage 17): nein**; mit der Restklasse wäre κ 0,806 (B) und 0,739 (A), auch das über 0,7 |
| 9.13 | Braucht es eine zweite Kodierrunde? | κ_B ist an denselben Labels gewählt und gemessen | nein für das Kriterium (beide Varianten tragen); eine Bestätigung mit einem zweiten Modell, wenn Frage 19 so beantwortet wird, dann nach Codebuch .2 (§ 4.3) |
| 9.14 | Einzelmitglied mit Partei: Person oder Fraktion? | die Kodierer gaben die Partei als Fraktion (2 Fälle in der Stichprobe), `parties.py` führt sie als Person ohne Partei | Person; die Partei als eigenes Feld (Codebuch .2, Punkt 1), auf der Seite erst mit Vorhaben 27 |
| 9.15 | Urheberklasse „unbekannt": 8 der 150 Dokumente geben die Kodierer einer Fraktion | 10 der 19 fehlenden Fraktionen; 2 356, 327 und 84 Dokumente sind „unbekannt" | Rückstand in `docs/todo.md`, Punkt 9 (Urheber), erweitern; nicht in Vorhaben 15, das `parties.py` nur liest |

## 10. Änderungen durch die Synergie (füllt der Supervisor)

Übertragen am 2026-11-23 aus [00-synergien-2026-11.md](00-synergien-2026-11.md) (§ 1, § 2.1, § 2.2
Konflikt 10, § 3 und § 4 „15 Funktion"), bevor die Stufe 2 beginnt. Wo das § 6 und § 7 ändert, gilt
dieser Abschnitt.

1. **Dateiname** (§ 1, „Attribute je Dokument"): `mitantraege.parquet` heißt
   **`dokumente_antragsteller.parquet`**, nach der Konvention `dokumente_<attribut>.parquet`; Spalten wie
   in § 6. Beide Ausgaben haben den Schlüssel `id`, eine Zeile je Korpus-ID (auch wo mehrere IDs eine
   PDF-Datei teilen) und den Vertrag `one_row_per_document`.
2. **Ein stadtweiter Mehrheitenblock** (§ 1, „Ratsmehrheit, Kooperation, Sitze je Periode"; § 3.1,
   Punkt 4): kein `[[functions.majorities]]`, sondern ein Block im **Stadtprofil**, weder unter
   `[functions]` noch unter `[council]` (das ist der Abrufblock von F6 und steht außerhalb des
   Fingerprints, Punkt 70). 15 legt ihn an; je Zeile Periode, Fraktionen, Gültigkeit und Quelle: die
   Vereinbarung aus Vorhaben 25 mit Datum ([25-quellen.md](25-quellen.md), § 2), dazu der Korpusbeleg
   aus § 3.9. 24 (Kooperation) und 28 (Fraktionsstärken) lesen ihn. Frage 9.2 ist damit beantwortet.
3. **Beobachtet/erwartet** (§ 1): die indirekte Standardisierung aus § 3.7 wird **eine reine Funktion
   in `src/georep/analysis/`** (Schicht Gremium und Periode) mit Eigenschaftstests. 15 baut sie, weil
   es vor 14 fertig wird; 14 nutzt sie in Stufe 3 für die Antworten je Fraktion (§ 4 „14").
4. **Gemeinsame Dateien** (§ 2.1): **ein** Beitrag `15-funktion` mit beiden Schritten (`functions`,
   `cosponsors`), eine Importzeile und ein Eintrag am Ende von `CONTRIBUTIONS`; Settings nach der
   Anhängeregel (Modell vor `class Settings`, Feld am Ende, Block am Ende von `defaults.toml` mit
   Kopfzeile, Schalter aus); Listen im Stadtprofil, weil `deep_merge` Listen ersetzt; der Snapshot von
   `georep steps` wird bewusst erneuert; die Punktnummer in `decisions.md` vergibt der Merge. Der
   F2-Nachzug (`steps(settings, layout, http)`, ein früher Einhängepunkt) läuft parallel; wird er vorher
   gemerged, zieht 15 nach.
5. **Zwei Zählungen der Parteien** (§ 2.2, Konflikt 10): Option 04 besitzt Urheberklasse und
   `parteien`, `analysis/parties.py` bleibt unverändert; ob es nachzieht und damit „Dokumente je Partei"
   auf `index.html` ändert, ist Frage 25 an Konrad (Annahme: nein). 14 nimmt die Fraktion aus 15
   (`fraktionen`), nicht aus `parteien`; `akteure.html` nennt den Unterschied mit Zahl.
6. **Fraktionstabelle** (§ 4 „15"): `[[functions.fractions]]` bleibt, bis Konrads Netzlauf
   `raw/organizations.json` für Düsseldorf bringt (Frage 9.3).
7. **Dokumentart-Tabellen** (§ 1): `functions.types` und `functions.type_prefixes` bleiben bei 15, so
   wie sie validiert sind. Neu ist ein Test, der je Profil jede vorkommende Dokumentart gegen die
   Tabellen prüft, damit eine neue Art sofort auffällt. Das Abschneiden der Fraktionsnamen hinter dem
   Antragspräfix nimmt `originators.motion_prefixes`.
8. **Seite** (§ 5): `akteure.html` zeigt Funktionen, Instrumente je Fraktion beobachtet/erwartet
   („explorativ"), die Matrix wer mit wem, K3 nur in Rat und Ausschüssen mit der Quelle der Mehrheit,
   die Liste der Resolutionen und „Funktion nicht erkannt"; nicht: eine Rangfolge der Symbolpolitik je
   Fraktion, K3 für Bezirksvertretungen, H15.1 und H15.2 als Test (nur prospektiv). Die Zahlen der
   Validierung kommen aus `validierung/15-funktion-f4/guete.json` mit dem Satz „desselben Modells"; die
   an den Labels gewählte Variante B nennt A als Untergrenze.
9. **Reihenfolge** (§ 3): Welle 1, Merge an Position 4 nach 11, 12 und 14; 15 braucht weder F1 noch
   den Netzlauf noch ein Modell.
