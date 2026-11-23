# Vorhaben 17: Zeit und Neuigkeiten

Stand 2026-11-23, Stufe 1 (Messen), Branch `feat/17-zeit`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „17 Zeit und Neuigkeiten".
Messskript: [17-zeit-messung.py](17-zeit-messung.py) (`uv run python docs/plans/17-zeit-messung.py
--feeds <ordner>`, rechnet jede Zahl dieses Dokuments nach und schreibt den Feed-Prototyp;
`--stichprobe` schreibt Stichprobe und Kodieraufgaben). Lexikon: [17-zeit-lexikon.toml](17-zeit-lexikon.toml),
Version 2026-11-23.1. Codebuch und Stichprobe: `validierung/17-zeit/`. **Hypothesen (§ 8) und Lexikon
sind vor der Messung festgelegt und allein committet** (`4b9bf14`, 19:45 Uhr; das Messskript lief zum
ersten Mal um 19:51 Uhr).

**Urteil: bauen, vorläufig — die Feeds erfüllen ihren Teil des Kriteriums, die Präzision des Lexikons
ist noch nicht gemessen** (§ 5), mit vier Änderungen am Briefing.

Die drei Zahlen, auf die es ankommt:

1. **Kein Wahlzyklus, aber ein Haushaltsrhythmus — und der besteht aus den Haushaltsanträgen.** Im
   Wahljahr vor den Wahlen 2020 und 2025 reichten die Fraktionen **4,9 % weniger** Dokumente ein als in
   den mittleren Jahren ihrer Periode (90 %: −12,9 bis +3,8 %; p = 0,85; H17.1 nicht bestätigt). Der
   Monat der Haushaltsberatung liegt **83 % über** demselben Kalendermonat in Jahren, in denen der
   Haushalt in einem anderen Monat beraten wurde (p = 1/27 720, Holm 0,0001; H17.2 bestätigt); ohne die
   Haushaltsanträge selbst liegt er 13 % darunter (p zweiseitig 0,25).
2. **Das bundespolitische Vokabular wächst nicht; es folgt der Bundesagenda.** Die Strukturkategorien
   des Lexikons stehen in **5,98 %** der Dokumente 2014-2020, **3,16 %** 2020-2025 und **3,47 %** seit 2025
   (p = 0,99; H17.3 nicht bestätigt). Der Anteil hängt an Flucht und Asyl (4,65 % der Dokumente
   2014-2020, 1,25 % seit 2025; alle Strukturkategorien zusammen 9,4 % im Wahljahr 2015/16); ohne diese
   Kategorie ist er flach (1,57 / 1,58 / 2,30 %, nachträglich und explorativ). Klima- und
   Energiepolitik und Wohnungs- und Bodenrecht des Bundes steigen (explorativ, je p = 0,008 ohne
   Korrektur): das sind Bundesgesetze, die die Stadt umsetzen muss.
3. **41 von 41 Atom-Feeds sind gültig**, nach dem RELAX-NG-Schema aus RFC 4287 und nach den normativen
   Regeln, die das Schema nicht ausdrückt; ein absichtlich kaputter Feed fällt bei beiden durch, zwei
   Bauten sind bytegleich. Je Feed die 50 neuesten Dokumente (18 bis 27 KB, zusammen 982 KB); sie
   reichen im Median 140 Tage zurück, ein Wahlbezirk bekommt im Median 2,3 neue Dokumente je Woche.

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

**Frage.** Hat die Ratsarbeit einen Takt — mehr Anfragen und Anträge vor der Wahl, Spitzen in der
Haushaltsberatung, sichtbare Spuren von Ereignissen? Wie viel bundespolitisches Vokabular steht in den
Dokumenten, und wächst es? Und: kann die Seite Neuigkeiten je Wahlbezirk liefern, statt dass man
nachsehen muss?

**Literatur.** Barari und Simko (2025: The Promise of Text, Audio, and Video Data for the Study of US
Local Politics and Federalism. Publius 55 (2), 223–252, doi:10.1093/publius/pjae046) zeigen an LocalView
(Barari und Simko 2023, Scientific Data), dass national markante, parteipolitisch gefärbte Wendungen in
kommunalen Sitzungen der USA häufig sind, in großen Städten häufiger, je Begriff sehr verschieden, und
dass ihre Färbung mit den örtlichen Parteipräferenzen zusammenhängt. Das ist der Bezug für H17.3; dieses
Vorhaben misst an Ratsdokumenten statt an Wortprotokollen und mit einem deutschen Lexikon, das
Gegenstände der Bundespolitik (Gesetze, Leistungen, Debatten) statt parteipolitischer Schlagworte zählt
(§ 3.3, Lesart). Für den Wahlzyklus (mehr Sichtbarkeit vor der Wahl) und den Haushaltsrhythmus nennt der
Meta-Plan keine Studie; die Hypothesen sind hier aus der Frage des Briefings formuliert, und ein Zitat
auf der Seite braucht eine nachgeschlagene Quelle (`report/literatur.toml`).

**Ratsarbeit.** [../workflow-ratsmitglied.md](../workflow-ratsmitglied.md), § 4: „Keine
Benachrichtigung … man muss nachsehen." Ein Feed je Wahlbezirk beantwortet „was ist neu in meinem
Bezirk?" in jedem Feedreader und in Mailprogrammen mit Feedfunktion, ohne Konto und ohne dass die Seite
etwas über den Leser erfährt. Der Rhythmus beantwortet „wann ist Hochsaison?" (Haushaltsmonat,
Sommerpause), die Ereignisspuren „welche Gremien hat das Hochwasser 2021 beschäftigt?".

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

Gerechnet auf den Läufen vom 2026-11-23 (`georep bootstrap && georep run` für `duesseldorf`,
`duesseldorf-2014` und `duesseldorf-2025` im Worktree, 19:31 bis 19:34 Uhr, `nice -n 10`). Pfade aus
`georep --profile <p> paths`.

| Datensatz | Profil | Dokumente | mit Text | erstes – letztes Datum | in Wahljahren | Fraktion | politisch | Haushaltsanträge | Text, Mio. Zeichen (Mittel je Dokument) |
|---|---|---|---|---|---|---|---|---|---|
| 2014-2020 | `duesseldorf-2014` | 22 215 | 21 838 | 2014-05-26 – 2020-09-11 | 21 496 | 8 815 | 11 620 | 139 | 67,7 (3 100) |
| 2020-2025 | `duesseldorf` | 19 108 | 19 033 | 2020-09-14 – 2025-09-12 | 18 977 | 7 859 | 9 051 | 678 | 51,2 (2 688) |
| 2025- | `duesseldorf-2025` | 4 095 | 4 075 | 2025-09-15 – 2026-10-13 | 3 623 | 1 732 | 2 008 | 171 | 10,0 (2 444) |

„In Wahljahren" sind die Dokumente in vollständigen Wahljahren (§ 8.0); „politisch" heißt Urheberklasse
Fraktion, Person oder unbekannt. Gelesen werden je Profil, nur lesend:

- `interim/papers.parquet`: `id`, `name` (Titel), `reference`, `date`, `paper_type`, `file_name`,
  `download_url`, `text` (kleingeschrieben, ohne Zeilenumbrüche).
- `processed/papers_gremien.parquet`: `id`, `gremium`, `gremium_art`.
- `processed/dokumente_urheber.parquet`: `id`, `urheber_art` (Option 4).
- Nur für die Feeds (`duesseldorf-2025`): `raw/papers.jsonl` (Feld `modified`, bei 4 095 von 4 095
  gesetzt, mit Zeitzone), `processed/combined_searchdict.parquet` (`wahlkreis_id`, `suchbegriffe`; 41
  Wahlbezirke) und `processed/inverted_index.parquet` (`suchbegriffe`, `paper_ids`, `anzahl_treffer`).
  Dokument und Wahlbezirk verbindet dieselbe Funktion wie die Seite (`analysis.hits.hits_by_district`).
- `messdaten/rohtext/<ordner>.parquet` (Phase 0): `name`, `text` mit Groß- und Kleinschreibung, nur für
  die Ausschnitte der Kodieraufgaben.

Zwei Eigenschaften der Daten tragen die Lesart:

- **Die Dokumentarten wechseln 2019.** Bis Mitte 2019 führt das Ratsinformationssystem Sammelarten
  (`Vorlage aus der Politik` bis 2019-06-28, `Verwaltungsvorlage` bis 2020-02-13), ab dem 2019-02-11 die
  Arten der späteren Perioden (Anfrage, Antrag, Beschlussvorlage …; 4 277 Dokumente der Periode
  2014-2020). Wer in 2014-2020 nach Dokumentart zählt, zählt über einen Bruch (§ 3.1, S1.5). Die
  Urheberklasse aus Option 4 überbrückt ihn mit Titel und Briefkopf, aber nicht ohne Rest (2 356
  „unbekannt" in 2014-2020).
- **Das Datum ist das Vorlagendatum**: Haushaltsanträge liegen im Monat ihrer Einreichung, nicht im Monat
  des Beschlusses; eine Monatsreihe zeigt Einreichungen, nicht Sitzungen.

**Herkunft und Lizenz**: OParl-Metadaten und PDF-Texte des Ratsinformationssystems wie der Korpus; das
Profil nennt am Endpunkt keinen Lizenzhinweis (`license = ""`), die Seite veröffentlicht darum nur
Kennungen und abgeleitete Tabellen. Die Feeds tragen nur, was `site/data/dokumente.json` schon
veröffentlicht (Kennung, Drucksache, Titel, Datum, Link aufs PDF), keine Texte.

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

Alle Zahlen vom 2026-11-23, Läufe des Messskripts zwischen 19:51 und 20:04 Uhr. Zwei Läufe ohne
Codeänderung ergeben bis auf die Laufzeit gleiche Ausgaben (geprüft mit `cmp`), die Feeds sind
bytegleich, und ohne `--stichprobe` meldet das Skript „gespeicherte Stichprobe ist dieselbe". Laufzeit
**18 bis 46 s** bei Lastmittel 7 bis 27 (`uptime` davor und danach, `nice -n 10`, Polars auf vier
Threads, Fremdlast); davon Laden und Markieren mit den 95 Mustern 11 bis 27 s, die drei exakten Tests
zusammen wenige Sekunden.

### 3.1 H17.1 Wahlzyklus: kein Anstieg vor der Wahl

| Wahljahr | Rolle im Test | Fraktionsdokumente | alle Dokumente | Anteil |
|---|---|---|---|---|
| 2014/15 | Anlauf (ausgenommen) | 1 582 | 3 643 | 43,4 % |
| 2015/16 | Vergleich | 1 486 | 3 608 | 41,2 % |
| 2016/17 | Vergleich | 1 351 | 3 370 | 40,1 % |
| 2017/18 | Vergleich | 1 358 | 3 441 | 39,5 % |
| 2018/19 | Vergleich | 1 401 | 3 683 | 38,0 % |
| 2019/20 | **vor der Wahl 2020** | 1 380 | 3 751 | 36,8 % |
| 2020/21 | Anlauf (ausgenommen) | 1 653 | 4 079 | 40,5 % |
| 2021/22 | Vergleich | 1 634 | 3 843 | 42,5 % |
| 2022/23 | Vergleich | 1 644 | 3 911 | 42,0 % |
| 2023/24 | Vergleich | 1 442 | 3 487 | 41,4 % |
| 2024/25 | **vor der Wahl 2025** | 1 434 | 3 657 | 39,2 % |
| 2025/26 | laufend (nicht im Test) | 1 499 | 3 623 | 41,4 % |

**Haupttest**: δ̂ = −0,051 (SE 0,045, t = −1,12, df = 6), also **−4,9 %** (90 %: −12,9 bis +3,8 %),
p einseitig **0,847**; die Randomisierungsprobe gibt p = 0,80 (16 von 20 Zuordnungen mindestens so
groß). Je Wahl (S1.6): 2020 1 380 gegen 1 399,0 im Mittel der mittleren Jahre (×0,986, Rang 3 von 5),
2025 1 434 gegen 1 573,3 (×0,911, Rang 4 von 4 — das schwächste Jahr der Periode).

| Sensitivität | Effekt | 90 % | p einseitig | Randomisierung |
|---|---|---|---|---|
| S1.1 politische Dokumente | −6,8 % | −14,6 bis +1,6 | 0,918 | 0,95 |
| S1.2 ohne März bis Juni | −6,2 % | −20,3 bis +10,4 | 0,762 | 0,75 |
| S1.3 Anlaufjahre im Vergleich (df = 8) | −6,8 % | −15,0 bis +2,3 | 0,901 | 0,87 (30 Zuordnungen) |
| S1.4 Anteil an allen Dokumenten | −2,83 Prozentpunkte (SE 0,79) | | 0,994 | 1,00 |
| S1.5 nur Anfragen / nur Anträge | +34,9 % / +53,8 % | +3,1 bis +76,5 / −5,5 bis +150,2 | 0,037 / 0,068 | 0,10 / 0,20 |

**S1.5 ist nicht deutbar.** Die vorab festgelegte Regel (Dokumentart, in 2014-2020 das Titelwort) lässt
in 2014-2020 **4 270 Fraktionsdokumente** ohne Instrument (je Wahljahr 1 025, 905, 779, 749, 684 und **0**
im Vorwahljahr 2019/20): mit dem Wechsel der Dokumentarten 2019 zählt sie die Anfragen und Anträge des
Vorwahljahrs vollständig (541 und 839), die der Jahre davor nur zum kleineren Teil (249 bis 368 und 283
bis 349). Der „Anstieg" ist der Bruch in den Daten (§ 2). Sauber ist die Teilung nur in der Hauptperiode:
**Anfragen** 601, 637, 699, 663, **674** (×1,01 gegen 666,3 in den mittleren Jahren), **Anträge** 1 052,
997, 945, 779, **760** (×0,84 gegen 907,0). Vor der Wahl 2025 gab es also gleich viele Anfragen und weniger
Anträge.

**Lesart.** Die Fraktionsdokumente fallen in beiden Perioden vom ersten zum letzten Wahljahr (2014-2020:
1 582 → 1 380; 2020-2025: 1 653 → 1 434), ihr Anteil an allen Dokumenten in 2014-2020 stetig
(43,4 → 36,8 %), in 2020-2025 von 42,5 % (2021/22) auf 39,2 %. Das erste Wahljahr liegt **über** den mittleren (×1,131 und ×1,051; begleitend und
explorativ), die laufende Periode in ihrem ersten Jahr bei 1 499 (×0,953 gegen die mittleren Jahre der
Hauptperiode, ein Vergleich über zwei Räte). Das Muster ist eher ein Anfangsschwung neuer Räte als ein
Endspurt vor der Wahl. Die Pandemie erklärt das Fehlen nicht: ohne März bis Juni (S1.2) bleibt der Effekt
negativ, und das Vorwahljahr 2024/25 ohne Pandemie ist das schwächste der Hauptperiode. Ob der Rückgang
über eine Periode die Regel ist, kann nur neues Material prüfen (§ 8.5, Vorschlag H17.4).

### 3.2 H17.2 Haushaltsrhythmus: Spitze durch die Haushaltsanträge selbst

Die Exposition (Regel in § 8.2, im Skript `haushaltsmonate`):

| Wahljahr | Haushaltsmonat | Haushaltsanträge im Wahljahr | davon im Monat |
|---|---|---|---|
| 2014/15 bis 2019/20 | November | 13, 16, 16, 16, 36, 42 | 13, 13, 12, 9, 27, 32 |
| 2020/21 | Februar (Haushalt 2021 nach der Wahl) | 171 | 136 |
| 2021/22 bis 2024/25 | Dezember | 118, 158, 126, 105 | 82, 108, 65, 63 |
| 2025/26 | März (Haushalt 2026 nach der Wahl) | 166 | 145 |

In 2014-2020 zählt die Regel nur Dokumente, deren Art oder Titel „Haushaltsantrag" sagt (139 in der
ganzen Periode gegen 678 und 171): ältere Haushaltsanträge standen als `Vorlage aus der Politik` mit
Titeln wie „Antrag … zum Haushalt". Der Monat ist trotzdem eindeutig (jedes Jahr November); die Stärke
der Exposition ist zwischen den Perioden nicht vergleichbar.

Fraktionsdokumente je Wahljahr und Kalendermonat (September bis August; * = Haushaltsmonat). Die
Septemberzellen von 2020/21 und 2025/26 sind um 12 und 14 Tage gekürzt (§ 8.0); die Jahreskonstante
nimmt das mit.

| Wahljahr | Sep | Okt | Nov | Dez | Jan | Feb | Mär | Apr | Mai | Jun | Jul | Aug |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2014/15 | 146 | 183 | 170* | 28 | 152 | 201 | 142 | 164 | 105 | 132 | 5 | 154 |
| 2015/16 | 158 | 150 | 119* | 57 | 148 | 135 | 117 | 176 | 115 | 166 | 16 | 129 |
| 2016/17 | 146 | 102 | 140* | 31 | 135 | 100 | 175 | 111 | 108 | 175 | 24 | 104 |
| 2017/18 | 132 | 107 | 149* | 31 | 134 | 136 | 83 | 154 | 167 | 154 | 27 | 84 |
| 2018/19 | 143 | 104 | 151* | 28 | 176 | 135 | 150 | 90 | 167 | 135 | 6 | 116 |
| 2019/20 | 132 | 86 | 233* | 17 | 147 | 144 | 140 | 50 | 127 | 148 | 10 | 146 |
| 2020/21 | 22 | 44 | 103 | 33 | 188 | 291* | 181 | 194 | 170 | 251 | 14 | 162 |
| 2021/22 | 125 | 90 | 180 | 106* | 147 | 147 | 209 | 101 | 213 | 122 | 11 | 183 |
| 2022/23 | 126 | 99 | 187 | 135* | 164 | 142 | 146 | 173 | 166 | 97 | 20 | 189 |
| 2023/24 | 128 | 144 | 154 | 79* | 120 | 168 | 86 | 184 | 110 | 152 | 10 | 107 |
| 2024/25 | 155 | 97 | 156 | 80* | 134 | 122 | 159 | 116 | 169 | 205 | 30 | 11 |
| 2025/26 | 32 | 46 | 91 | 32 | 155 | 152 | 246* | 190 | 167 | 235 | 65 | 88 |

**Haupttest**: δ̂ = 0,605, also **+83,1 %**; die beobachtete Zuordnung ist die extremste aller 27 720,
p einseitig = 1/27 720 ≈ 0,00004, Holm-angepasst 0,0001: **bestätigt**.

| Sensitivität | Effekt | p |
|---|---|---|
| S2.1 Fraktionsdokumente ohne Haushaltsanträge | −12,9 % | zweiseitig 0,246 |
| S2.2 alle Dokumente | +31,9 % | einseitig 1/27 720 |
| S2.3 Hauptperiode, beschreibend | Februar 2021: 291 gegen 144,8 (Februar 2022 bis 2025); Dezember 2021 bis 2024: 100,0 gegen 33 (Dezember 2020) | — |

Je Wahljahr, Haushaltsmonat gegen das Mittel desselben Kalendermonats in den Jahren ohne Haushalt in
diesem Monat (beschreibend):

| Wahljahr, Monat | Fraktionsdokumente | ohne Haushaltsanträge | Rang im Wahljahr |
|---|---|---|---|
| 2014/15 Nov | 170 gegen 145,2 (×1,17) | ×1,13 | 3 |
| 2015/16 Nov | 119 (×0,82) | ×0,79 | 8 |
| 2016/17 Nov | 140 (×0,96) | ×0,95 | 4 |
| 2017/18 Nov | 149 (×1,03) | ×1,05 | 4 |
| 2018/19 Nov | 151 (×1,04) | ×0,91 | 3 |
| 2019/20 Nov | 233 (×1,61) | ×1,45 | **1** |
| 2020/21 Feb | 291 gegen 143,8 (×2,02) | ×1,09 | **1** |
| 2021/22 Dez | 106 gegen 32,1 (×3,30) | ×0,77 | 9 |
| 2022/23 Dez | 135 (×4,20) | ×0,87 | 8 |
| 2023/24 Dez | 79 (×2,46) | ×0,45 | 11 |
| 2024/25 Dez | 80 (×2,49) | ×0,55 | 10 |
| 2025/26 Mär | 246 gegen 144,4 (×1,70) | ×0,71 | **1** |

**Lesart.** Der Haushalt macht seinen Monat sichtbar: in den 2020er Jahren verdrei- bis vervierfacht er
den Dezember, im Februar 2021 und im März 2026 ist der Haushaltsmonat der stärkste des Wahljahrs. Er
zieht aber keine anderen Initiativen nach sich: ohne die Haushaltsanträge liegt der Haushaltsmonat 13 %
**unter** seinem Kalendermonat (nicht signifikant), im Dezember der Hauptperiode deutlich (×0,45 bis
×0,87) — eher Verdrängung als Sog. In 2014-2020 ist der Haushalt kaum zu sehen (November ×0,82 bis ×1,61,
zweimal unter dem Mittel), dort zählte die Regel nur 9 bis 32 Haushaltsanträge im Monat. Und
„Spitzenmonat" heißt im vorab festgelegten Sinn „über seinem Kalendermonat", nicht „stärkster Monat des
Jahres": der Dezember bleibt mit Haushalt einer der schwächsten Monate (Rang 8 bis 11), stärkster Monat
war der Haushaltsmonat dreimal (November 2019, Februar 2021, März 2026). Die Bestätigung ist damit
richtig und fast mechanisch; auf die Seite gehört sie mit dem Satz zu S2.1.

### 3.3 H17.3 Bundespolitisches Vokabular: kein Anstieg

Anteil der Dokumente mit Text und Treffer in einer Strukturkategorie, je Wahljahr (in Prozent):

| | 14/15 | 15/16 | 16/17 | 17/18 | 18/19 | 19/20 | 20/21 | 21/22 | 22/23 | 23/24 | 24/25 | 25/26 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Strukturkategorien (Haupttest) | 7,30 | 9,37 | 6,76 | 5,35 | 4,37 | 2,97 | 2,79 | 3,35 | 3,97 | 3,49 | 2,22 | 3,47 |
| S3.1 nur Titel und 2 000 Zeichen | 5,92 | 7,62 | 5,16 | 3,85 | 3,37 | 2,19 | 2,07 | 2,51 | 2,92 | 2,33 | 1,73 | 2,50 |
| S3.2 alle zehn Kategorien | 7,33 | 9,45 | 6,76 | 5,38 | 4,37 | 9,18 | 18,09 | 13,57 | 9,86 | 5,93 | 4,06 | 4,16 |
| S3.5 ohne Migration (nachträglich) | 1,38 | 1,07 | 1,84 | 1,89 | 1,99 | 1,26 | 1,16 | 1,20 | 2,51 | 1,84 | 1,18 | 2,30 |

**Haupttest**: 5,98 / 3,16 / 3,47 % je Periode, Differenz der laufenden zur ersten −2,51 Prozentpunkte,
JT = 7,0, p einseitig **0,987**: **nicht bestätigt**. Sensitivitäten: S3.1 4,66 / 2,32 / 2,50 % (p =
0,987); S3.2 mit den Ereignissen 7,10 / 10,54 / 4,16 % (JT = 21, p = 0,50); S3.4 politische Dokumente
6,29 / 3,83 / 4,35 % (p = 0,955), Verwaltung 5,66 / 2,58 / 2,71 % (p = 0,995). Nachträglich und
explorativ, nicht vorab festgelegt: S3.5 ohne Migration 1,57 / 1,58 / 2,30 % (JT = 23, p = 0,38).

Je Kategorie (S3.3, explorativ, ohne Korrektur; Anteil an den Dokumenten in Wahljahren, Dokumente an allen
mit Text der Periode, die häufigsten Muster über alle drei Perioden):

| Kategorie | Anteil je Periode, % | Dokumente je Periode | p (JT, steigend) | häufigste Muster (Dokumente) |
|---|---|---|---|---|
| Migration und Asyl | 4,65 / 1,68 / 1,25 | 989 / 317 / 54 | 0,999 | flüchtling 1 027, asyl 447, geflüchtete 318, abschiebung 59 |
| Klima- und Energiepolitik des Bundes | 0,18 / 0,43 / 0,36 | 38 / 81 / 14 | **0,008** | energiewende 70, gebäudeenergiegesetz 30, EEG 11, wärmeplanungsgesetz 8 |
| Bürgergeld und Sozialstaat | 0,75 / 0,52 / 0,50 | 163 / 100 / 21 | 0,94 | wohngeld 98, hartz iv 69, Bildungs- und Teilhabe 55, mindestlohn 30 |
| Gendern | 0,03 / 0,04 / 0,06 | 7 / 8 / 2 | 0,40 | geschlechtergerechte Sprache 8, gendern 5 |
| Verkehrspolitik des Bundes | 0,46 / 0,40 / 0,61 | 99 / 77 / 23 | 0,33 | bundesverkehrsminist 42, dieselfahrverbot 40, deutschlandticket 36, stvo-novelle 20 |
| Wohnungs- und Bodenpolitik des Bundes | 0,04 / 0,14 / 0,75 | 9 / 28 / 32 | **0,008** | mietpreisbremse 27, bau-turbo 26, baulandmobilisierungsgesetz 18 |
| Cannabispolitik | 0,13 / 0,09 / 0,08 | 28 / 17 / 4 | 0,89 | cannabis 49, kiffen 4 |
| Corona (Ereignis) | 1,21 / 7,33 / 0,55 | 266 / 1 388 / 24 | 0,040 | corona 1 276, pandemie 989, covid 228 |
| Krieg gegen die Ukraine (Ereignis) | 0,02 / 1,09 / 0,33 | 5 / 207 / 14 | 0,044 | ukrain 221, angriffskrieg 44, putin 13 |
| Energiekrise 2022 (Ereignis) | 0,01 / 0,27 / 0,06 | 3 / 51 / 2 | 0,027 | energiekrise 29, gasmangel 11 |

**Lesart.** Der Anteil hängt an einem Thema: die Aufnahme Geflüchteter 2015/16 war eine örtliche Aufgabe
mit bundespolitischer Ursache, und „flüchtling" allein steht in 1 027 Dokumenten. Ohne sie ist der Anteil
flach. Was steigt, sind **Bundesgesetze, die die Stadt umsetzen muss** — Gebäudeenergiegesetz,
Wärmeplanungsgesetz, Baulandmobilisierungsgesetz, „Bau-Turbo" —, nicht die parteipolitisch gefärbten
Schlagworte, die Barari und Simko zählen: Gendern steht in 17 Dokumenten in elf Jahren, Cannabis in 49.
Mit einer Bonferroni-Korrektur über zehn Kategorien hielte keiner der beiden Anstiege (0,008 · 10 =
0,08). Ob ein Treffer die Bundesebene nennt oder nur die örtliche Umsetzung, beschreibt die Frage
`ebene` der Kodierung (§ 4). Die Lesart „Nationalisierung" im Sinne von Barari und Simko stützen die Zahlen
nicht; sie zeigen die **Bundesagenda** in den Dokumenten, mit ihren Wellen (2015/16 Flucht, 2020/21
Corona, 2022 Krieg und Energiepreise).

### 3.4 Zeitliche Gegenprobe des Lexikons (deterministisch)

Treffer vor dem Ereignis können die Kategorie nicht meinen; das ist eine Untergrenze für Fehler einzelner
Muster, keine Präzision.

- **corona** (Muster corona, covid, sars-cov, lockdown): 1 von 1 435 Dokumenten liegt vor dem 2020-01-01,
  `AGS/003/2020` mit Datum 2019-12-11 und dem Satz „die corona-krise mit ihren noch nicht gänzlich
  abschätzbaren …" — ein Dokument von 2020 (Nummer) mit früherem Datum, ein Datumsfehler, kein Fehler des
  Lexikons. Das Muster „pandemie" trifft vor 2020 ein Dokument.
- **energiekrise**: 3 von 56 Dokumenten liegen vor dem 2021-09-01, alle drei mit „Energiesicherungsstelle"
  (Amt 50, 2015/16: eine Stelle gegen Strom- und Gassperren armer Haushalte). Das Muster
  `energiesicherungs` meint dort etwas anderes; es trifft insgesamt 3, 1 und 0 Dokumente der drei
  Perioden.
- **bundesverkehr** (Ticketmuster): 0 von 50 Dokumenten vor dem 2022-03-01.
- **ukraine_krieg** vor dem 24.02.2022: 5 Dokumente. Eines trifft die Definition (`50/ 47/2014`, der
  „Ukraine-Konflikt" und Russlands Importverbot), vier nicht: eine Liste von Sprachen („ukrainisch",
  2016) und dreimal „Angriffskrieg" für andere Kriege (2016 der deutsche im Zweiten Weltkrieg, 2018 und
  2019 der türkische in Syrien). `angriffskrieg` (44 Dokumente) ist der schwache Teil der Kategorie.

### 3.5 Ereignisspuren je Gremium (explorativ)

Anteil der Dokumente mit Text und Treffer im Fenster des Ereignisses gegen dieselben Kalendermonate ein
Jahr davor; je Gremium mit mindestens 20 Dokumenten im Fenster, die acht mit den meisten Treffern.
Hochwasser steht nicht im bundespolitischen Lexikon, sondern unter `[[lokal]]` (sieben Muster) und ist
**nicht** kodiert.

| Ereignis | Fenster gegen Vorjahr | Spitzenmonat | Gremien (Treffer/Dokumente, Anteil gegen Vorjahr) |
|---|---|---|---|
| Hochwasser Juli 2021 | Jul–Dez 2021: 97/1 740 (5,6 %) gegen 14/1 541 (0,9 %) | 2021-08: 48/424 (11,3 %) | BV7 17/119 (14 % gegen 0 %), BV5 14/100 (14 % gegen 5 %), BV8 11/120 (9 % gegen 1 %), RAT 8/185 (4 % gegen 0 %), AUS 7/26 (27 % gegen 0 %), APS 5/59 (8 % gegen 6 %), AÖE 5/34 (15 % gegen 0 %), BV10 4/67 (6 % gegen 0 %) |
| Pandemie ab März 2020 | Mär 2020–Feb 2021: 554/3 653 (15,2 %) gegen 3/3 773 (0,1 %) | 2021-07: 33/119 (27,7 %); zuvor 2020-05: 27 % | RAT 131/486 (27 %), KUA 62/143 (43 %), BV1 34/277 (12 %), AGS 33/68 (49 %), BV10 32/172 (19 %), OVA 27/126 (21 %), BV7 25/359 (7 %), BV5 23/151 (15 %); im Vorjahr überall 0 bis 1 % |
| Vollinvasion Februar 2022 | Mär 2022–Feb 2023: 117/3 928 (3,0 %) gegen 0/4 073 | 2022-03: 24/413 (5,8 %) | RAT 47/470 (10 %), KUA 13/116 (11 %), SCHUA 8/88 (9 %), AGS 5/70 (7 %), AWIR 5/27 (19 %), BV4, BV7, OVA je 4 (2 bis 3 %) |
| Energiekrise 2022 | Jul 2022–Jun 2023: 37/3 890 (1,0 %) gegen 3/3 792 (0,1 %) | 2022-10: 6/304 (2,0 %) | RAT 12/453 (3 %), AUS 6/71 (8 %), OVA 3/162, HFA 2/36 (6 % gegen 3 %), BV1 2/317, BV4 2/190 |

Lesbar ist: das **Hochwasser** beschäftigte vor allem die Bezirksvertretungen 7, 5 und 8 und den
Umweltausschuss (AUS, Ausschuss für Umwelt-, Klima- und Verbraucherschutz) und bleibt bis Mitte 2022 bei
1 bis 5 % der Dokumente; die **Pandemie** stand ein Jahr lang in einem Siebtel aller Dokumente, in KUA und
AGS in fast der Hälfte; der **Krieg** setzt im März 2022 schlagartig ein und liegt Anfang 2024 bei 0 bis
1 %; die **Energiekrise** ist mit 1 % schwach und am deutlichsten im Rat und im Umweltausschuss.
Alles explorativ: keine Tests, Fenster nach dem Ereignis gewählt, die Muster von Corona, Ukraine und
Energiekrise noch ungeprüft.

### 3.6 Atom-Feeds je Wahlbezirk (Prototyp im Scratchpad)

**Inhalt.** Je Wahlbezirk der laufenden Periode ein Feed `feeds/wahlbezirk-NN.xml` mit den 50 neuesten
Dokumenten, in denen ein Name aus dem Wörterbuch des Bezirks vorkommt (dieselbe Zuordnung wie die Zahl
auf der Seite). Kopf und erster Eintrag des Feeds für Wahlbezirk 1:

```xml
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="de">
  <id>urn:uuid:b1ee82b3-9830-51ec-b109-887099fa8178</id>
  <title>Ratsdokumente im Wahlbezirk 1 (Düsseldorf, Wahlperiode seit der Kommunalwahl 2025)</title>
  <subtitle>Neue Dokumente, in denen ein Straßen- oder Ortsname des Wahlbezirks vorkommt: …</subtitle>
  <updated>2026-10-05T09:10:24+02:00</updated>
  <author><name>georep, aus dem Ratsinformationssystem (OParl)</name></author>
  <generator version="0.17.0">georep</generator>
  <link rel="alternate" type="text/html" href="../index.html"/>
  <entry>
    <id>http://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers/vo/114055</id>
    <title>BAU/026/2026: Stopp der weiteren Planung und Machbarkeitsprüfung einer Photovoltaikanlage …</title>
    <published>2026-10-05T00:00:00+02:00</published>
    <updated>2026-10-05T09:10:24+02:00</updated>
    <link rel="alternate" type="application/pdf" href="https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/downloadfiles/00599402.pdf"/>
  </entry>
```

Was ein Feed enthalten darf, und warum:

| Element | Wert | Grund |
|---|---|---|
| `feed/id` | `urn:uuid:` (UUID v5 aus `georep:<stadt>/<ordner>/feeds/wahlbezirk-NN`) | absolut und dauerhaft, ohne dass die Seite ihre eigene Adresse kennen muss (Pages oder VPS) |
| `feed/title`, `subtitle` | Wahlbezirk, Stadt, Periode; was drin ist | ein eigener Satz, kein Dokumenttext |
| `feed/updated` | das jüngste `updated` der Einträge, **nicht** die Laufzeit | gleiche Daten, gleiche Bytes: ein Lauf ohne neues Dokument ändert keinen Feed |
| `feed/author`, `generator` | „georep, aus dem Ratsinformationssystem (OParl)", Version | RFC 4287 verlangt einen Autor im Feed oder in jedem Eintrag |
| `feed/link` alternate | `../index.html` (relativ, die Seite der Periode) | ein `rel="self"` bräuchte die absolute Adresse (§ 9, Frage 9.4) |
| `entry/id` | die OParl-URL des Dokuments | dauerhaft; dasselbe Dokument trägt in mehreren Bezirksfeeds dieselbe id, wie RFC 4287 es für denselben Eintrag vorsieht |
| `entry/title` | „Drucksache: Titel" | wie im Dokumentdialog der Seite |
| `entry/published` | Vorlagendatum, 00:00 Europe/Berlin | das Datum der Seite |
| `entry/updated` | OParl `modified`, nie vor `published` | ein geändertes Dokument erscheint im Reader neu |
| `entry/link` alternate | das PDF im Ratsinformationssystem (https), `type="application/pdf"` | der Link der Seite; OParl liefert für Düsseldorf kein `web` |
| **nicht** | `content`, `summary`, `category`, Personen | keine Texte (Briefing, Meta-Plan § 1); keine Personen |

**Prüfung.** (1) Das RELAX-NG-Schema aus RFC 4287, Anhang B, von Hand aus der Compact-Syntax ins
XML-Format übertragen (im Skript, `ATOM_RNG`), geprüft mit lxml 5.2.1 des System-Pythons 3.12
(`python3 -I`; das Paket hat lxml nicht): **41 von 41 gültig**. (2) Die normativen Regeln, die das
Schema nicht ausdrückt (Autor im Feed oder in jedem Eintrag; genau ein `id`, `title`, `updated`; Datum
nach RFC 3339 mit großem `T` und Zeitzone; `id` absolut; ein Eintrag ohne `content` hat einen
alternate-Link; nie zwei alternate-Links mit gleichem `type` und `hreflang`) und die Projektregeln
(Einträge nur mit `id`, `title`, `updated`, `published`, `link`; `id` je Feed eindeutig; `feed/updated`
= jüngstes `updated`): **41 von 41 ohne Fehler**. (3) Gegenprobe: ein Feed mit kaputtem Datum und
falschem Elementnamen — die Regeln melden drei Fehler, RELAX NG verwirft ihn. (4) Zwei Bauten sind
bytegleich.

**Umfang.** 41 Feeds zu je höchstens 50 Einträgen, **18 162 bis 26 718 Byte** (Median 24 473), zusammen
**981,8 KB**, rund 490 Byte je Eintrag (die Titel sind lang). Die 50 neuesten Einträge reichen **54 bis
379 Tage** zurück (Median 140); je Wahlbezirk und Woche kommen **0,6 bis 6,3** neue Dokumente (Median
2,3), in den letzten 30 Tagen vor dem 2026-10-13 waren es 2 bis 24 (Median 11). Kein Eintrag ohne Link.
Wer wöchentlich liest, verpasst also nichts; wer monatlich liest, in den dichtesten Bezirken auch nicht.

**Entstehung bei jedem Lauf des Monitors** (`deploy/bin/georep-monitor.sh`): Schritt 5 (`georep --profile
$MONITOR_PROFILE run`) ruft den Schritt `feeds` des Beitrags (Stufe 2), der `site/feeds/wahlbezirk-NN.xml`
schreibt; Schritt 7 spiegelt `$PROFILE_SITE/` mit `rsync -a --delete` nach `out/2025/` (ausgenommen nur
`snapshots/`, `stand.json` und Stamps), die Feeds liegen also unter `out/2025/feeds/`; Schritt 9 schiebt
sie mit derselben rsync-Zeile auf den VPS, `--itemize-changes` zeigt nur die geänderten Feeds. Weil
`updated` aus den Daten kommt, ändert ein Lauf ohne neues Dokument keinen Feed. Der Monatsschnappschuss
(`out/2025/snapshots/<JJJJ-MM>/`) kopiert nur `data/`; die Feeds sind abgeleitet und gehören nicht hinein.
GitHub Pages bekommt sie über `georep publish` (`_copy_tree` kopiert den ganzen Ordner der Seite). Die
Feeds sind keine HTML-Seiten, das Budget aus Punkt 50 gilt für sie nicht (`_over_budget` prüft nur
HTML); die Seite der laufenden Periode wächst um rund 1 MB.

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

**Was schon deterministisch geprüft ist** (§ 3.4): die zeitliche Gegenprobe für Corona, Energiekrise,
die Ticketmuster und die Ukraine vor der Vollinvasion. Sie findet zwei schwache Muster
(`energiesicherungs`, `angriffskrieg`) und sonst nichts, sagt aber nichts über Treffer nach dem
Stichtag und nichts über die Strukturkategorien. Die Feeds sind vollständig geprüft (§ 3.6); sie brauchen
keine Kodierung.

**Codebuch** `validierung/17-zeit/codebuch.toml` (Version 2026-11-23.1, vorläufiges Format wie Vorhaben
15, F4 baut den Rahmen). Einheit: ein Treffer, also eine Fundstelle eines Lexikonbegriffs, im Ausschnitt
mit ⟦ ⟧ markiert. Ein Grundsatz („maßgeblich ist, was das markierte Wort an dieser Stelle bedeutet") und
zwei Fragen:

1. `thema` (Mehrfachauswahl aus den zehn Kategorien, dazu `anderes` und `unklar`, die allein stehen),
   mit den Definitionen des Lexikons, geschärft um die Grenzfälle aus § 3.4 (Pandemieplan vor 2020,
   Energiesperren, die Ukraine ohne Krieg) und um Überschneidungen (Geflüchtete aus der Ukraine:
   `migration_asyl` und `ukraine_krieg`).
2. `ebene` (`bund`, `land_eu`, `lokal`, `unklar`): nennt die Fundstelle die Bundesebene, oder bleibt sie
   bei der örtlichen Umsetzung? Beschreibt die Lesart „Nationalisierung" (§ 3.3), wird nicht als
   Präzision gewertet.

**Antwortformat im Codebuch** (`[antwortformat]`): `antworten-<kodierer>.jsonl` neben den Aufgaben, eine
Zeile je Aufgabe in deren Reihenfolge, mit `aufgabe`, `thema` (Liste), `ebene`, `unsicher` (true oder
false), `begruendung` (ein Satz, höchstens 200 Zeichen, ohne Personennamen), dazu ein Beispiel und
`rueckmeldung-<kodierer>.md` für Lücken. Das ist die Lehre aus Vorhaben 15, wo ein Kodierer sein Format
selbst wählen musste, weil das Codebuch keines nannte.

**Stichprobe** `validierung/17-zeit/stichprobe.csv` (`aufgabe`, `id`, `kategorie`, `periode`, `stelle`,
`treffer`; nur Kennungen und das Fundwort): **100 Treffer, zehn je Kategorie**, je Kategorie zehn
Dokumente mit Seed `17-<kategorie>`, je Dokument eine zufällige Fundstelle, die Reihenfolge gemischt
(Seed 17). Perioden in der Stichprobe 30 / 58 / 12; Fundstelle im Text 97, im Titel 3. Population je
Kategorie (Dokumente mit Text und Treffer, drei Perioden): Migration 1 360, Klima und Energie 133,
Sozialstaat 284, Gendern 17, Bundesverkehr 199, Wohnen 69, Cannabis 49, Corona 1 678, Ukraine 226,
Energiekrise 56. Die Stichprobe hängt am Lexikon; wer ein Muster ändert, macht eine neue Version und
zieht neu, und das Skript meldet ohne `--stichprobe`, ob die gespeicherte noch dieselbe ist.

**Kodieraufgaben** (nicht im Repo): `/media/konrad/xtraspace/georep/messdaten/kodierung/17-zeit/aufgaben.jsonl`,
100 Zeilen, 113 979 Byte, dazu ein README. Je Zeile: `vorhaben`, `aufgabe`, `codebuch`, `id`,
`drucksache`, `titel`, `dokumentart`, `datum`, `gremium`, `fundwort`, `textquelle` (97 `rohtext`, 3
`titel`), `ausschnitt` (rund 350 Zeichen links und rechts, aus dem Rohtext von Phase 0 mit Groß- und
Kleinschreibung). Das markierte Wort gleicht in 100 von 100 Aufgaben dem Fundwort (Leerraum
normalisiert). **Nicht in den Aufgaben**: die Kategorie des Lexikons und die Schichtung.

**Maße** (nach F4): **Präzision** = Anteil der Aufgaben, deren Lexikonkategorie im Endlabel `thema`
steht; `unklar` wird gezählt, nicht gewertet. Kriterium ≥ 0,9 an den 100 (Punktschätzung, wie in den
anderen Vorhaben), berichtet mit Wilson-95-%-Intervall — bei genau 90 von 100 sind das 0,83 bis 0,94;
dazu mit der Population gewichtet (Corona und Migration tragen dann 75 % des Gewichts) und je Kategorie
mit Wilson-Intervall (n = 10, nur zur Orientierung). `ebene`: Anteile je Kategorie und Periode. Zwischen
den Kodierern Krippendorffs α, für `thema` als MASI-Distanz und binär (Lexikonkategorie im Thema ja oder
nein), für `ebene` nominal; Stufe 3 verlangt α ≥ 0,8.

**Was ≥ 0,9 hier verlangt**: höchstens zehn falsche von 100 gewerteten. Bekannte Risiken je Kategorie,
ohne dass ich die Stichprobe angesehen hätte: Energiekrise (3 von 56 Dokumenten sind sicher falsch, eine
Aufgabe von zehn wäre im Erwartungswert 0,5), Ukraine (`angriffskrieg` für andere Kriege, Sprachlisten),
Corona (`pandemie` ohne Covid). Wohngeld und das Bildungs- und Teilhabepaket sind Bundesleistungen, die
die Stadt auszahlt; sie zählen als `sozialstaat`, und `ebene` zeigt, wie oft die Stelle die Bundesebene
nennt.

## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

**Kriterium** (Briefing, unverändert): das Lexikon erreicht eine Präzision ≥ 0,9 an 100 Treffern; die
Feeds sind gültig.

- **Feeds: erfüllt.** 41 von 41 nach RELAX NG und nach den normativen Regeln, die Gegenprobe greift, zwei
  Bauten bytegleich. Unsicherheit: das Schema ist von Hand übertragen; es verwirft den kaputten Feed, aber
  ein Übertragungsfehler, der es zu nachsichtig macht, ist nicht ausgeschlossen — darum prüfen die Regeln
  unabhängig davon.
- **Lexikon: ausstehend.** Die Gegenprobe kennt sieben sicher falsche Dokumente (drei mit
  `energiesicherungs`, vier Ukraine-Treffer vor 2022) unter 4 071 Dokument-Kategorie-Paaren; das
  spricht für die großen Kategorien, aber die Stichprobe gibt den kleinen dasselbe Gewicht.

**Urteil: bauen, vorläufig — Präzision ausstehend**, mit vier Änderungen am Briefing:

1. **Die Feeds werden unabhängig vom Lexikon gebaut**; sie brauchen es nicht, und sie sind der Teil mit
   dem klarsten Nutzen für die Ratsarbeit (§ 1).
2. **Die Hypothesen sind entschieden und kommen so auf die Seite**: H17.1 nicht bestätigt, H17.2
   bestätigt mit dem Satz zu S2.1 (die Spitze sind die Haushaltsanträge selbst), H17.3 nicht bestätigt.
   Die Tests werden in Stufe 2 ein Schritt, damit die Seite sie aus den Daten nachrechnet und H17.3 mit
   jedem Monat der laufenden Periode neu rechnet — mit Lexikon Version 1, an die H17.3 gebunden ist.
3. **Das Lexikon erscheint auf der Seite erst nach der Kodierung** (Präzision ≥ 0,9, α ≥ 0,8). Fällt es
   durch, folgt Version 2 mit einer neuen Kodierrunde (höchstens eine Runde Umbauen, Meta-Plan § 8);
   Kandidaten sind `energiesicherungs` streichen und `angriffskrieg` nur mit Ukraine oder Russland im
   Muster. Die Zahlen von H17.3 bleiben die von Version 1.
4. **Ereignisspuren nur für geprüfte Kategorien.** Corona, Ukraine und Energiekrise prüft die Kodierung
   mit; Hochwasser steht nicht im Lexikon und ist nicht geprüft — auf die Seite nur mit eigener
   Stichprobe (Frage 9.12), sonst bleibt es im Messdokument.

Kippt die Präzision, betrifft das § 3.3 bis § 3.5, nicht die Feeds und nicht H17.1 und H17.2.

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

Zwei Beiträge nach F2 im Register `georep.enrich.CONTRIBUTIONS` (Punkt 69), beide offline, beide hinter
`parties` und `bodies` (lesen deren Ausgaben), `feeds` zusätzlich hinter `index` und dem Wörterbuch:

**Beitrag `cycles`** (`src/georep/enrich/cycles.py`), drei Schritte:

1. `cycles`: Korpus (`id`, `date`, `name`, `paper_type`, `text`), `dokumente_urheber`, `papers_gremien`.
   Schreibt `processed/zeit_monate.parquet` und `processed/haushaltsmonate.parquet`.
2. `vocabulary`: Korpus und Lexikon. Schreibt `processed/bundesvokabular.parquet` und, für die
   Kodierbögen von F4, die Treffer im Text als Spannen nach F3.
3. `cycle_tests`: nur in einem Profil mit `cycles.periods` (die Profile der Stadt in zeitlicher Folge);
   liest deren `zeit_monate` und `bundesvokabular` über `layout.for_profile`, wie `compare` (Option 02).
   Schreibt `processed/zeit_hypothesen.parquet`.

| Datei | Spalten | Schlüssel, Ordnung |
|---|---|---|
| `zeit_monate.parquet` | `monat` Date (Monatserster), `wahljahr` Int32 (leer außerhalb vollständiger Wahljahre), `gremium_art` str, `urheber_art` str, `dokumente` Int64, `mit_text` Int64, `haushaltsantraege` Int64 | (`monat`, `gremium_art`, `urheber_art`), lückenlos vom ersten bis zum letzten Monat, sortiert |
| `haushaltsmonate.parquet` | `wahljahr` Int32, `monat_kalender` Int8 (1 bis 12, leer ohne Haushaltsmonat), `haushaltsantraege` Int64, `im_monat` Int64 | `wahljahr`, sortiert |
| `bundesvokabular.parquet` | `id` str, `kategorien` list[str] (in Lexikonfolge, leer ohne Treffer), `kopf` list[str] (dasselbe nur in Titel und 2 000 Zeichen), `lexikon` str (Version) | eine Zeile je Korpus-ID, sortiert nach `id` |
| `bundesvokabular_spannen.parquet` | F3-Schema; `kind = "bundesvokabular"`, `value` das Fundwort, `norm` die Kategorie, `extractor` Textstore und Lexikonversion | nach `id`, `start`, `end`, `kind` |
| `zeit_hypothesen.parquet` | `hypothese` str, `mass` str, `test` str, `statistik` f64, `effekt` f64, `p` f64, `p_holm` f64, `ergebnis` str (`bestätigt`, `nicht bestätigt`, `vorläufig`), `n` Int64, `lexikon` str, `daten_bis` Date | eine Zeile je Haupttest und Sensitivität, Folge wie § 8 |

Schema-Versionen aus den Modulkonstanten (`CYCLES_SCHEMA_VERSION`, `VOCABULARY_SCHEMA_VERSION`,
`CYCLE_TESTS_SCHEMA_VERSION`, je 1).

**Beitrag `feeds`** (`src/georep/enrich/feeds.py`, die XML-Erzeugung rein in `src/georep/report/feeds.py`),
ein Schritt `feeds` nur in Profilen mit `feeds.enabled` (Düsseldorf: die laufende Periode): Korpus-Metadaten
(`id`, `name`, `reference`, `date`, `download_url`), `modified` aus `raw/papers.jsonl` (fehlt es, gilt das
Vorlagendatum), Wörterbuch und Index. Schreibt `site/feeds/wahlbezirk-NN.xml` je Wahlbezirk des
Wörterbuchs und entfernt Feeds von Wahlbezirken, die es nicht mehr gibt.

**Verträge** (an den Batch-Grenzen, Prädikate in `georep.contracts`): `zeit_monate` summiert zur Zahl
der Korpusdokumente, und je Monat zu `monatsreihe.parquet` aus `timeline` (dieselbe Zählung);
`wahljahr` leer genau außerhalb der vollständigen Wahljahre; `haushaltsantraege ≤ dokumente`;
`bundesvokabular` hat genau eine Zeile je Korpus-ID, `kategorien` ⊆ Kategorien des Lexikons, sortiert,
eindeutig, `kopf` ⊆ `kategorien`; Spannen nach F3 (`0 ≤ start < end ≤ len(text)`, `text[start:end] ==
value`); `zeit_hypothesen`: `p` und `p_holm` in [0, 1], `p_holm ≥ p`, `ergebnis = bestätigt` genau dann,
wenn Holm verwirft. Je Feed: die Regeln aus `atom_regeln` des Messskripts (normativ und Projekt), höchstens
`feeds.entries` Einträge, absteigend nach Datum, `id` eindeutig, `feed/updated` = jüngstes `updated`,
`updated ≥ published`, Titel ohne Steuerzeichen, die XML 1.0 verbietet (Titel aus OParl werden
bereinigt). Nach jedem Join sortieren.

**Settings** (Anhängeregel aus F2: Modelle `Cycles` und `Feeds` vor `class Settings`, Felder am Ende,
Block am Ende von `defaults.toml` mit `# --- Vorhaben 17: Zeit und Neuigkeiten`, Schalter aus):

```toml
[cycles]                        # Vorhaben 17; stadtneutral, die Wahltage stehen im Stadtprofil
enabled = false
year_start_month = 9            # Wahljahr ab September: die Kommunalwahlen in NRW lagen 2020 und 2025 im September
elections = []                  # Wahltage der Kommunalwahlen, im Stadtprofil mit Quelle
budget_pattern = "haushalts(begleit)?-?antrag"   # auf Dokumentart und Titel, kleingeschrieben (Messdokument § 8.2)
budget_minimum = 5              # so viele Haushaltsanträge braucht ein Wahljahr für einen Haushaltsmonat
lexicon = "bundespolitik"       # Paketdatei georep/lexika/<name>.toml; die Version steht in der Datei
periods = []                    # Profile der Stadt für die Tests über Perioden, in zeitlicher Folge; leer = keine Tests

[feeds]                         # Vorhaben 17; nur für eine laufende Periode sinnvoll
enabled = false
entries = 50                    # neueste Dokumente je Feed; 50 reichen im Median 140 Tage zurück (Messdokument § 3.6)
```

Düsseldorf trägt im **Stadtprofil** `elections = [2014-05-25, 2020-09-13, 2025-09-14]` (Quelle:
Landeswahlleiterin NRW) und `cycles.enabled = true`; das Hauptprofil `duesseldorf` trägt `periods =
["duesseldorf-2014", "duesseldorf", "duesseldorf-2025"]`; nur `duesseldorf-2025.toml` setzt
`feeds.enabled = true`. Das **Lexikon** ist deutschsprachig, aber nicht städtisch: es zieht als
Paketdatei `src/georep/lexika/bundespolitik.toml` ins Paket (Inhalt wie
`docs/plans/17-zeit-lexikon.toml`, Version im Kopf, Version im Stamp und in jeder Ausgabe). Mönchengladbach
bekommt `cycles` (Rhythmus, Vokabular, sofern Text) ohne Tests und ohne Feeds.

**Tests.** Beispiele: Wahljahr an den Grenzen (31.08., 01.09., Wahltag, angeschnittene Monate je
Periode); Haushaltsmonat mit Gleichstand, unter dem Minimum, ohne Haushaltsanträge; je Kategorie ein
Treffer und ein Nichttreffer aus § 3.4 (`energiesicherungsstelle` trifft in Version 1, `tierasyl` nicht);
ein Feed aus einem Mini-Korpus als syrupy-Snapshot (klein und stabil); ein Feed ohne Einträge; ein Titel
mit `&`, `<`, Anführungszeichen und einem Steuerzeichen. **hypothesis**: `zeit_monate` summiert für jeden
Zufallskorpus zur Dokumentzahl; jeder Feed ist für zufällige Titel, Daten und Links wohlgeformt, besteht
`atom_regeln` und gibt die Titel unverändert zurück; derselbe Korpus gibt dieselben Bytes, in jeder
Zeilenfolge; der Randomisierungstest von H17.2 und der Jonckheere-Terpstra-Test geben für jede Tabelle
p in (0, 1] und p ≥ 1/Zahl der Zuordnungen; Holm verwirft nie, was der ungekorrigierte Test
nicht verwirft. Die
exakten Tests gegen Rechnungen von Hand an Tabellen von 3 × 3 und 2 + 2 + 1. **slow**, Golden auf den drei
Perioden: die Tabellen aus § 3.1 bis § 3.3 und die Ergebnisse von § 8 (gerundet), bis eine neue
Lexikonversion sie bewusst neu einfriert. **RELAX NG**: eine Prüfung aller Feeds gegen das Schema braucht
lxml (Frage 9.8). Kein Netz, kein Modell.

**Berührte Dateien.** Neu: `src/georep/enrich/cycles.py`, `src/georep/enrich/feeds.py`,
`src/georep/analysis/cycles.py` (Wahljahr, Haushaltsmonat, Tests, rein), `src/georep/analysis/lexicon.py`
(Laden, Muster, Treffer, rein), `src/georep/report/feeds.py`, `src/georep/lexika/bundespolitik.toml`,
`tests/unit/test_cycles.py`, `tests/unit/test_lexicon.py`, `tests/unit/test_feeds.py`,
`tests/property/test_cycles.py`, `tests/property/test_feeds.py`, `tests/golden/test_cycles.py`.
Geändert mit einer Zeile oder einem Block: `src/georep/enrich/__init__.py`, `src/georep/settings.py`,
`src/georep/defaults.toml`, `src/georep/profiles/duesseldorf.toml`,
`src/georep/profiles/duesseldorf-2025.toml`, `pyproject.toml` (Paketdaten `lexika/*.toml`),
`docs/architecture.md` (Schritttabelle), `docs/decisions.md` (Punkt ohne Nummer: „Wahljahr ab
September, Tests über ganze Jahre", „Feeds mit urn:uuid und updated aus den Daten"),
`docs/workflow-ratsmitglied.md` § 4 (die Zeile „Keine Benachrichtigung" ändert sich mit Stufe 3).
`deploy/bin/georep-monitor.sh` bleibt unverändert (§ 3.6). **Kein Paket**: alle Schritte rechnen offline
aus Texten und Metadaten, die die Pakete schon tragen, in rund 20 s für drei Perioden.

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

**Unterseite `zeit.html`** (`report.pages.Page` im Beitrag `cycles`, je Profil mit `cycles.enabled`),
im Rahmen der Hauptseite, für alle Fraktionen gleich gebaut:

1. *Rhythmus der Ratsarbeit*: Monatsbalken (SVG) der Dokumente je Urheberklasse über die Periode,
   Haushaltsmonate und Sommerpausen markiert; darunter der Median je Kalendermonat.
2. *Vorab festgelegte Hypothesen* (nur im Profil mit `cycles.periods`): eine Zeile je Hypothese mit Maß,
   Test, Effekt, p, Holm, Ergebnis und dem Satz, wann und in welchem Commit sie festgelegt wurde;
   H17.2 mit dem Satz zu S2.1; „nicht bestätigt" so groß wie „bestätigt".
3. *Bundespolitisches Vokabular*: Anteil je Wahljahr und Kategorie (Tabelle mit kleinen Balken), mit
   „geprüft von zwei KI-Kodierern an 100 Treffern, nicht von Menschen", Präzision mit Intervall und α —
   nur, wenn die Kodierung trägt.
4. *Ereignisspuren* (explorativ überschrieben): Corona, Krieg gegen die Ukraine, Energiekrise je Monat
   und die Gremien mit den höchsten Anteilen; Hochwasser nur mit eigener Prüfung.
5. *Neuigkeiten je Wahlbezirk* (nur mit `feeds.enabled`): die 41 Feeds als Liste mit Link und Zahl der
   neuen Dokumente der letzten 30 Tage, zwei Sätze, was ein Feed enthält und was nicht, und wie oft er
   sich ändert.

Größe geschätzt **40 bis 80 KB** (drei Balkenreihen über 14 bis 77 Monate, eine Tabelle 12 × 10, vier
kleine Ereignisreihen, eine Liste von 41 Links). **Tabellen im Register**: `zeit_monate`,
`haushaltsmonate`, `bundesvokabular` (nur Kennungen und Kategorien), `zeit_hypothesen` (Parquet und
CSV). **Feed-Links auf der Seite der laufenden Periode**: der Abschnitt 5 auf `zeit.html` des Profils
`duesseldorf-2025`, das die Hauptseite im Linkblock „Weitere Auswertungen" erreicht; `index.html` bleibt
unverändert (Meta-Plan § 4). Ein Link je Wahlbezirk im Dialog des Bezirks auf `index.html` wäre der
kürzeste Weg, berührt aber die Hauptseite (Frage 9.11). `workflow-ratsmitglied.md`, § 4: „Keine
Benachrichtigung" wird zu „Neuigkeiten je Wahlbezirk als Feed, keine Benachrichtigung per Mail".

## 8. Vorab festgelegte Hypothesen (nur Analysen: Hypothese, Maß, Test, Schwelle)

Festgelegt am 2026-11-23 um 19:45 Uhr (Commit `4b9bf14`; dort stand „gegen 19:50", Korrektur 1),
**bevor** eine Ergebnisgröße gerechnet war; der Commit, der
diesen Abschnitt anlegt, trägt nur ihn und das Lexikon, sein Zeitstempel ist der Beleg (Meta-Plan,
§ 2.11). **Vorher angesehen** waren: die Schemas der Dateien; die Monatsreihe aller Dokumente in
[../statistik.md](../statistik.md), § 11 (Dezember und Juli schwach, Juni stark); die Anteile je
Urheberklasse und Fraktion aus [15-funktion.md](15-funktion.md), §§ 3.6 und 3.7 (Periodensummen, keine
Jahres- oder Monatswerte); und, weil H17.2 sie als Exposition braucht, **die Monate der Haushaltsanträge
und die Titel der Haushaltsvorlagen** — nicht die Zahl der übrigen Dokumente je Monat.

### 8.0 Gemeinsame Festlegungen

- **Wahljahr**: 1. September bis 31. August. Kommunalwahlen in NRW: 25.05.2014, 13.09.2020, 14.09.2025
  (stehen in Stufe 2 mit Quelle im Stadtprofil). Vollständige Wahljahre: 2014/15 bis 2019/20 (Periode
  2014-2020, sechs), 2020/21 bis 2024/25 (Hauptperiode, fünf), 2025/26 (laufende Periode, eines).
  Angeschnittene Monate (Juni bis August 2014, 1. bis 12. September 2020, 1. bis 14. September 2025,
  ab September 2026) gehören zu keinem Wahljahr.
- **Datum** ist das Vorlagendatum (`date`), wie in der Monatsreihe der Seite.
- **Fraktionsdokumente**: `urheber_art == "Fraktion"` aus `processed/dokumente_urheber.parquet` (Option
  4, auf der Seite); fast nur Anfragen, Anträge und Resolutionen ([15-funktion.md](15-funktion.md),
  § 3.6). **Politische Dokumente**: `urheber_art` in Fraktion, Person, unbekannt.
- **Familie**: die drei Haupttests H17.1, H17.2, H17.3, mit **Holm bei α = 0,05** über die drei
  einseitigen p-Werte. Alles andere — Sensitivitäten, Teilmaße, Anlaufjahr, Ereignisspuren, je
  Kategorie — ist beschreibend und heißt auf der Seite „Sensitivität" oder „explorativ"; es bestätigt
  und widerlegt keine Hypothese.
- **Warum Wahljahre als Einheit**: Monatsreihen sind autokorreliert (ein aktives Jahr hebt alle seine
  Monate) und haben Sommerpausen und Sitzungskalender. Ein Test über Monate als unabhängige
  Beobachtungen wäre zu liberal. Alle drei Tests vergleichen darum ganze Wahljahre oder denselben
  Kalendermonat über Jahre; jedes Wahljahr enthält jeden Kalendermonat genau einmal.

### 8.1 H17.1 Wahlzyklus

- **Hypothese**: Im letzten Wahljahr vor einer Kommunalwahl reichen die Fraktionen mehr Dokumente ein
  als in den mittleren Wahljahren derselben Periode.
- **Maß**: y = ln(Summe der Fraktionsdokumente im Wahljahr).
- **Einheiten**: behandelt sind 2019/20 (Wahl 2020) und 2024/25 (Wahl 2025); Vergleich sind die
  mittleren Wahljahre 2015/16 bis 2018/19 und 2021/22 bis 2023/24. Das erste Wahljahr jeder Periode
  ist ausgenommen (Konstituierung, Besetzung der Ausschüsse: ein eigener Effekt, der den Vergleich zu
  Gunsten der These verschöbe). Die Wahl 2014 hat kein Vorwahljahr im Datensatz (er beginnt am
  Wahltag), die laufende Periode noch keines.
- **Test**: OLS y = μ_Periode + δ · Vorwahljahr über neun Wahljahre, einseitiger t-Test auf δ > 0
  (df = 6). Die exakte Randomisierungsprobe (welches Nicht-Anlaufjahr jeder Periode „Vorwahljahr" ist,
  5 · 4 = 20 Zuordnungen) wird berichtet, entscheidet aber nicht: sie kann 1/20 nicht unterschreiten.
- **Effekt**: exp(δ̂) − 1 mit 90-%-Intervall (einseitig 95 %).
- **Schwelle**: Holm über die Familie.
- **Sensitivität** (berichtet, nicht entscheidend): S1.1 politische Dokumente statt Fraktionsdokumente;
  S1.2 ohne die Kalendermonate März bis Juni in allen Wahljahren (Pandemie im Vorwahljahr 2019/20);
  S1.3 die Anlaufjahre als Vergleich eingeschlossen (df = 8); S1.4 Anteil der Fraktionsdokumente an
  allen Dokumenten statt Summe; S1.5 Anfragen und Anträge getrennt (Dokumentart, in 2014-2020 das
  Titelwort); S1.6 je Wahl das Verhältnis Vorwahljahr zu mittleren Jahren.
- **Begleitend, explorativ**: das **Anlaufjahr** (erstes Wahljahr) gegen die mittleren Jahre derselben
  Periode, für die Perioden 2014-2020 und 2020-2025; für 2025/26 nur gegen die mittleren Jahre der
  Hauptperiode (ein Vergleich über zwei Räte).

### 8.2 H17.2 Haushaltsrhythmus

- **Hypothese**: Der Monat der Haushaltsberatung ist für die Fraktionen ein Spitzenmonat: in ihm liegen
  mehr Fraktionsdokumente, als derselbe Kalendermonat in Wahljahren erwarten lässt, in denen der
  Haushalt in einem anderen Monat beraten wurde.
- **Exposition** (aus den Daten; vor dem Festlegen angesehen): Haushaltsmonat eines Wahljahrs ist der
  Kalendermonat mit den meisten **Haushaltsanträgen** (Dokumentart oder Titel enthält
  `haushalts(begleit)?-?antrag`, kleingeschrieben); bei Gleichstand der frühere Monat; unter fünf
  Haushaltsanträgen im Wahljahr gibt es keinen. Angesehen: November in 2014/15 bis 2019/20, Februar in
  2020/21 (Haushalt 2021 nach der Wahl), Dezember in 2021/22 bis 2024/25, März in 2025/26 (Haushalt
  2026 nach der Wahl).
- **Identifikation**: der Haushaltsmonat wandert (November, Februar, Dezember, März). Derselbe
  Kalendermonat lässt sich darum mit und ohne Haushaltsberatung vergleichen, ohne dass die Saison der
  Ratsarbeit als Haushaltseffekt gelesen wird.
- **Maß**: y(w, m) = ln(1 + Fraktionsdokumente im Kalendermonat m des Wahljahrs w), zwölf Wahljahre mal
  zwölf Monate.
- **Test**: Zwei-Wege-Modell y = α_w + β_m + δ · [m ist Haushaltsmonat von w] + ε; δ̂ aus der doppelt
  zentrierten Tabelle. **Randomisierungstest** über alle Zuordnungen der beobachteten Haushaltsmonate
  (sechsmal November, viermal Dezember, je einmal Februar und März) zu den zwölf Wahljahren,
  12!/(6! · 4! · 1! · 1!) = 27 720 (dort stand 13 860, ein Rechenfehler in der Zahl, nicht im Test;
  Korrektur 2), einseitig: p = Anteil der Zuordnungen mit δ̂* ≥ δ̂. Ganze Wahljahre werden
  vertauscht, die Abhängigkeit der Monate eines Jahres bleibt also erhalten; die Monatskonstanten
  nehmen Sommerpause und Sitzungskalender, die Jahreskonstanten das Niveau des Rates.
- **Effekt**: exp(δ̂) − 1.
- **Schwelle**: Holm über die Familie.
- **Sensitivität**: S2.1 Fraktionsdokumente **ohne** Haushaltsanträge, zweiseitig (zieht der Haushalt
  andere Initiativen mit, oder verdrängt er sie?); S2.2 alle Dokumente; S2.3 nur die Hauptperiode
  (Februar 2021 gegen Dezember 2021 bis 2024, beschreibend).

### 8.3 H17.3 Bundespolitisches Vokabular

- **Hypothese**: Der Anteil der Dokumente, die einen Begriff der **Strukturkategorien** des Lexikons
  (Version 2026-11-23.1: Migration und Asyl, Klima- und Energiepolitik des Bundes, Bürgergeld und
  Sozialstaat, Gendern, Verkehrspolitik des Bundes, Wohnungs- und Bodenpolitik des Bundes,
  Cannabispolitik) tragen, steigt von Periode zu Periode: 2014-2020 < 2020-2025 < 2025-.
- **Maß**: Anteil je Wahljahr: Dokumente mit Text und Treffer in Titel oder Text / Dokumente mit Text.
- **Test**: **Jonckheere-Terpstra** für geordnete Alternativen über die zwölf Wahljahre in drei Gruppen
  (6, 5, 1), exakt über alle 12!/(6! · 5! · 1!) = 5 544 Zuordnungen, einseitig steigend. Rangtest ohne
  Normalitätsannahme; die geordnete Alternative ist die These. Bekannte Schwäche: Autokorrelation
  zwischen benachbarten Jahren macht ihn etwas zu liberal; dagegen stehen Holm und die Sensitivitäten.
- **Effekt**: Anteil je Periode (über die Dokumente gepoolt) und Differenz der laufenden zur ersten
  Periode in Prozentpunkten.
- **Schwelle**: Holm über die Familie. **Gültigkeit**: gewertet wird erst, wenn das Lexikon die
  Präzision ≥ 0,9 erreicht (Kriterium des Briefings, § 4); bis dahin heißt das Ergebnis „vorläufig".
- **Warum die Ereigniskategorien nicht zählen**: Corona, der Krieg gegen die Ukraine und die
  Energiekrise gab es vor 2020 nicht; mit ihnen stiege der Anteil mechanisch. Die Strukturkategorien
  sind Gegenstände, die es in allen drei Perioden gab — ihre Begriffe aber teilweise nicht (Bürgergeld
  ab 2023, Deutschlandticket ab 2023; umgekehrt Hartz IV und Pkw-Maut früher). Das Lexikon misst
  darum die **Präsenz der Bundesagenda** in den Dokumenten, nicht ihre Ursache; „Nationalisierung" im
  Sinne von Barari und Simko (2025) ist eine Lesart, kein Befund dieses Tests.
- **Sensitivität**: S3.1 nur Titel und die ersten 2 000 Zeichen des Texts (gegen längere Dokumente);
  S3.2 alle zehn Kategorien einschließlich der Ereignisse; S3.3 je Kategorie (explorativ, ohne
  Korrektur); S3.4 politische Dokumente und Verwaltung getrennt.

### 8.4 Nicht vorab festgelegt

Die Ereignisspuren (Hochwasser Juli 2021, Pandemie 2020/21, Energiekrise 2022) in den Monatsreihen je
Gremium sind **explorativ** und stehen so im Dokument und auf der Seite.

### 8.5 Ergebnis und Vorschlag (nach der Messung angefügt)

Die Festlegung oben ist bis auf zwei gekennzeichnete Korrekturen der Text von Commit `4b9bf14`: die Uhrzeit
(19:45, nicht „gegen 19:50") und die Zahl der Zuordnungen von H17.2 (27 720, nicht 13 860 — ein
Rechenfehler in der Zahl, der Test ist derselbe). Ergebnisse in § 3:

| Hypothese | Effekt | p einseitig | Holm | Ergebnis |
|---|---|---|---|---|
| H17.1 Wahlzyklus | −4,9 % (90 %: −12,9 bis +3,8) | 0,847 | 1,0 | nicht bestätigt |
| H17.2 Haushaltsrhythmus | +83,1 % | 1/27 720 ≈ 0,00004 | 0,0001 | bestätigt (ohne Haushaltsanträge −12,9 %, p zweiseitig 0,25) |
| H17.3 Bundespolitisches Vokabular | 5,98 / 3,16 / 3,47 % | 0,987 | 1,0 | nicht bestätigt, und vorläufig, bis das Lexikon die Präzision erreicht |

**Vorschlag für eine prospektive Hypothese** (für den Supervisor; prüfbar nur an neuem Material, weil
das Muster jetzt bekannt ist): **H17.4 Anfangsschwung** — in der Periode ab 2025 liegen die
Fraktionsdokumente im ersten Wahljahr (2025/26: 1 499) über dem Mittel der Wahljahre 2026/27 bis
2028/29; Maß und Test wie H17.1 (Jahressummen, ein Rang unter vier Jahren, also p ≥ 1/4: allein
nicht entscheidbar, nur zusammen mit 2014/15 und 2020/21 als dritte Periode in einem Modell wie § 8.1).
Prüfbar im September 2029.

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 9.1 | Gilt das Wahljahr ab September auch für eine Periode, die im Mai begann (2014)? | 2014/15 beginnt drei Monate nach der Wahl | ja; Juni bis August 2014 bleiben draußen (§ 8.0), das Anlaufjahr ist ohnehin nicht im Test |
| 9.2 | Der Wechsel der Dokumentarten 2019 (§ 2) verschiebt die Urheberklassen innerhalb der Periode 2014-2020 | H17.1 und jede Reihe nach Instrument | S1.1 (politische Dokumente) ist dagegen robust und zeigt dasselbe; Reihen nach Instrument nur ab Februar 2019 |
| 9.3 | 50 Einträge je Feed (rund 1 MB für 41 Feeds) oder weniger? | Größe der Seite, Last beim Abruf | 50; mit 30 wären es geschätzt rund 600 KB (nicht gemessen) |
| 9.4 | Ein `rel="self"` braucht die absolute Adresse der Seite (Pages oder VPS) | Feedreader finden Umzüge über `self` | kein `self`, bis ein Schlüssel `report.site_url` die kanonische Adresse nennt; die ids (`urn:uuid`) hängen nicht an der Adresse |
| 9.5 | Link ins RIS: PDF oder HTML-Seite der Vorlage? | ein PDF öffnet sich in manchen Readern schlecht | PDF wie im Dokumentdialog; OParl liefert für Düsseldorf kein `web` |
| 9.6 | Dürfen die getroffenen Straßennamen als `category` in den Eintrag („warum steht das hier")? | sehr nützlich, aber mehr als Kennung, Titel, Datum, Link (Briefing) | nein, bis Konrad es freigibt; die Namen sind Wörterbuch, kein Dokumenttext |
| 9.7 | `updated` aus OParl `modified` oder nur aus dem Datum? | ein vom RIS berührtes Dokument erscheint im Reader neu | `modified`, wo vorhanden; sonst das Datum |
| 9.8 | lxml als Abhängigkeit der Entwicklungsgruppe, damit ein Test jeden Feed gegen das RELAX-NG-Schema prüft? | ohne lxml prüfen die Tests nur die normativen Regeln | ja, nur in der Entwicklungsgruppe; sonst Regeln allein und das Schema im Messskript |
| 9.9 | Wo laufen die Tests über drei Perioden, und in welcher Reihenfolge laufen die Profile auf Pages und im Monitor? | `cycle_tests` liest die Ausgaben der anderen Profile | im Hauptprofil `duesseldorf`, nach den beiden Periodenprofilen (im Monitor läuft die Hauptseite schon zuletzt); fehlt eine Eingabe, bricht der Schritt mit Namen ab wie `compare` |
| 9.10 | Lexikon als Paketdatei statt im Stadtprofil? | ein Lexikon für alle deutschen Städte | Paketdatei mit Version; ein Stadtprofil darf eine eigene Datei nennen |
| 9.11 | Feed-Link im Dialog des Wahlbezirks auf `index.html`? | kürzester Weg für Ratsmitglieder, berührt aber die Hauptseite | nein; nur `zeit.html` der laufenden Periode, bis der Supervisor eine Zeile im Dialog freigibt |
| 9.12 | Hochwasser auf die Seite? | nicht im Lexikon, nicht kodiert (Meta-Plan § 2.6) | nein, bis zehn Treffer mitkodiert sind |
| 9.13 | Präzision mit Mehrfachauswahl: zählt ein Treffer, wenn die Lexikonkategorie eine von zwei gewählten ist? | Geflüchtete aus der Ukraine sind beides | ja; `unklar` wird gezählt, nicht gewertet |
| 9.14 | H17.2 ist fast mechanisch (die Spitze sind die Haushaltsanträge). Zeigt die Seite sie als „bestätigt"? | die Leser könnten mehr hineinlesen | ja, wie vorab festgelegt, mit dem Satz zu S2.1 in derselben Zeile |
| 9.15 | H17.3 rechnet mit jedem Monat der laufenden Periode neu; ab wann ist eine neue Rechnung ein neuer Befund? | wiederholtes Testen derselben Hypothese | die Seite zeigt den Stand mit Datum; als Befund zählt nur der Stand am Ende der Periode (Herbst 2030) |

## 10. Änderungen durch die Synergie (füllt der Supervisor)

—
