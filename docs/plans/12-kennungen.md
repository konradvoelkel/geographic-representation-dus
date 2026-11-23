# Vorhaben 12: Kennungen und Beträge

Stand 2026-11-23, Stufe 1 mit Kodierung. Briefing: [plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md),
§ 11. Messskript: [12-kennungen-messung.py](12-kennungen-messung.py). Codebuch, Stichprobe und Labels:
`validierung/12-kennungen/`. **Urteil nach der Kodierung** (§ 4.1, § 5): Bauleitplanung, Betrag und
Termin **bauen**; Haushalt, Rechtsgrundlage und Amt **umbauen** (eine Runde mit frischer
Bestätigungsstichprobe); die Rolle eines Betrags und die Funktion eines Termins **fallen**.

Alle Zahlen dieses Dokuments rechnet das Skript nach:

```bash
uv run python docs/plans/12-kennungen-messung.py --alle --stichprobe   # 54 s auf 4 Kernen, s. § 3.6
uv run python docs/plans/12-kennungen-messung.py --einzelprozess   # dazu die Zeit in einem Prozess
uv run python docs/plans/12-kennungen-messung.py --profil moenchengladbach   # Einzelheiten je Profil
uv run python docs/plans/12-kennungen-messung.py --beispiele betrag:sonstig   # 40 Beispiele mit Kontext
uv run python docs/plans/12-kennungen-messung.py --auswertung   # Labels bilden, Extraktor messen (§ 4.1), rund 20 s
```

## 1. Frage und Nutzen

**Frage** (Briefing): Welche Kennungen stehen in den Ratsdokumenten, und lassen sie sich mit Regeln
verlässlich herausziehen — Bebauungsplan-Nummern und Änderungen des Flächennutzungsplans,
Haushaltsnummern (Produkt, Sachkonto, PSP-Element, Investitionsmaßnahme), Euro-Beträge **mit ihrer
Rolle** (Kosten, Zuschuss, Ertrag, Verfügungsmittel, Förderung, Einsparung), Fristen und Termine,
Rechtsgrundlagen, Ämter und Dezernate? Drucksachennummern gehören Vorhaben 14.

**Nutzen für die Ratsarbeit.** Ein Vorlagenspiegel liest zuerst Beschlussvorschlag und Finanzen; eine
Bebauungsplan-Nummer ist der Schlüssel, unter dem Verwaltung, Bezirksvertretung und Bürgerschaft
einen Vorgang über Jahre wiederfinden („was gab es schon zu 03/017?“); eine Frist („bis zum
31.03.2023 vorzulegen“, „in der nächsten Sitzung zu berichten“) ist die Wiedervorlage, die heute
niemand automatisch sieht (`workflow-ratsmitglied.md`, § 4); das federführende Amt sagt, wer
antwortet. Die Kennungen sind Zulieferer: **21** (Geld auf der Karte) braucht Beträge mit Rolle und
über die Bebauungspläne einen Ortsbezug, **24** (Anfragen als Kontrolle) das Amt und Dezernat, **29**
(Ratsarbeit) Fristen und Plannummern, **16** (Ortsbezug) die Plannummern als Schlüssel zu den
Geltungsbereichen des Portals.

**Literatur.** Regelbasierte Extraktion ist bei festen Formaten (Nummern, Paragraphen, Datumsangaben)
der übliche, gut prüfbare Weg; für die Rolle eines Betrags ist sie eine Heuristik, deren Güte nur eine
kodierte Stichprobe zeigt („validate, validate, validate“, Grimmer und Stewart 2013, im Plan § 2.6).
Die Messung trennt darum die Spanne (Betrag richtig gefunden und normalisiert) von der Rolle (Betrag
richtig eingeordnet), wie das Kriterium es tut.

## 2. Datenlage

**Rohtext** (Messdatei aus Phase 0, vom Supervisor am 2026-11-23 mit pypdf 7.1.0 extrahiert, nur lesbar
unter `/media/konrad/xtraspace/georep/messdaten/rohtext/<profil>.parquet`). Spalten: `name`
(PDF-Dateiname, String), `text` (Groß- und Kleinschreibung, Zeilenumbrüche, Seitenwechsel als `\f`),
`pages` (Int64), `chars` (Int64), `extractor` (`pypdf-7.1.0 roh`), `pdf_sha256`, `error`.

| Datensatz | Zeilen | mit Text | Zeichen | Seiten | Fehler | leer | Datei |
|---|---:|---:|---:|---:|---:|---:|---:|
| `duesseldorf` (Hauptperiode) | 19 092 | 19 091 | 55 402 931 | 39 965 | 1 | 16 | 17,0 MB |
| `2014-2020` | 22 116 | 22 101 | 73 397 634 | 50 861 | 15 | 182 | 21,8 MB |
| `2025` | 4 088 | 4 088 | 10 907 491 | 8 265 | 0 | 3 | 3,3 MB |
| `moenchengladbach` | 658 | 658 | 3 571 264 | 2 485 | 0 | 6 | 1,1 MB |

**Metadaten** je Profil aus `raw/papers.jsonl` (Pfad über `Layout.papers`): `file_name`, `id`
(OParl-Paper), `paper_type`, `name` (Titel), `date`. In der Hauptperiode tragen 19 108 Paper 19 093
verschiedene Dateien; das Skript nimmt je Datei die kleinste ID (sortiert, dann `group_by` mit
`maintain_order`). Alle 19 092 Texte finden ihr Paper.

**Herkunft und Lizenz**: Ratsinformationssysteme der Städte über OParl, wie im Profil unter
`[[report.sources]]` genannt (Lizenz dort leer). Die Messdatei und die Kodieraufgaben bleiben lokal;
ins Repo kommen nur die Stichprobe (IDs und Spannengrenzen) und das Codebuch (Plan § 4).

## 3. Messung

### 3.1 Vorgehen

Je Art eine Funktion aus regulären Ausdrücken (Messfassung `kennungen-messung-v1`), Ausgabe als Spannen
nach F3 (`id, start, end, kind, value, norm, section, extractor`), dazu `attr` (Rolle eines Betrags,
Funktion eines Termins, Herkunft eines Gesetzes oder Amts) und `cue` (das auslösende Wort). Offsets
sind Zeichenindizes in den Rohtext. Elf `kind`s in sechs Arten:

| Art | kinds | Auslöser |
|---|---|---|
| 1 Bauleitplanung | `bplan`, `fnp` | Schlüsselwort (Bebauungsplan, B-Plan, Fluchtlinien-, Durchführungsplan; Flächennutzungsplanänderung) und Nummernformat der Stadt; die Spanne ist nur die Nummer |
| 2 Haushalt | `produkt`, `sachkonto`, `psp`, `investition` | Schlüsselwort (Produkt, Profitcenter, Konto, Kostenart, PSP-Element, Maßnahme, LDI) und Format der Stadt |
| 3 Betrag | `betrag` | Zahl mit Einheit (€, EUR, Euro, T€, TEUR), Faktor (Mio., Mrd., Tsd.), Einheit vorn, Spannen („5.000 bis 10.000 Euro“) |
| 4 Termin | `termin` | Datum (Zahl und Text), Monat und Jahr, Quartal und Halbjahr, „Ende 2024“, relative Fristen („in der nächsten Sitzung“, „innerhalb von drei Monaten“) |
| 5 Rechtsgrundlage | `recht` | Kette aus § oder Art. mit Absatz, Satz, Nummer, Verbindern („i. V. m.“), dazu das Gesetz dahinter, in der Nähe danach oder direkt davor |
| 6 Verwaltungseinheit | `amt`, `dezernat` | Kopffeld der Vorlage, Amtsnummer („Amt 66“), Name aus einem Amtsverzeichnis, das das Skript **aus den Kopffeldern des Korpus selbst** baut, „Dezernat 06“ |

Was stadtspezifisch ist (Kopffelder wie „Fachbereich:“ und „Amt / Institut:“, Nummernformate der Pläne
und des Haushalts), steht im Skript in `PROFILMUSTER` je Stadt und zieht in Stufe 2 ins Profil; alles
andere ist stadtneutral (Plan § 4: kein Stadtwort im Code). Die Rolle eines Betrags kommt aus
Schlüsselwörtern im selben Satz: ein Wort in derselben Zeile davor gewinnt (Tabellenzeile „Baukosten
82.000 EUR“), Verfügungsmittel im Satz gehen vor, eine Einsparung in 60 Zeichen auch, sonst das
nächste Wort; findet der Satz keines, gilt ein Wort aus Kopf und Betreff (Markierung `;dok`), sonst
`sonstig`. Die Funktion eines Termins kommt aus dem Wort davor („bis zum“, „spätestens“ → `frist`;
„vom … bis“ → `zeitraum`; „Sitzung am“ → `sitzung`). `section` ist hier ein grober Ersatz (letzte
Überschrift wie „Beschlussvorschlag“, „Sachdarstellung“, „Finanzielle Auswirkungen“, „Anlagen“, davor
`kopf`); Stufe 2 nimmt die Abschnitte aus Vorhaben 11.

Entwickelt wurden die Muster an Beispielen mit Kontext (`--beispiele`); die Fehlerbilder in § 3.3
stammen aus diesem Lesen und sind **keine** Kodierung. Die Güte misst erst die Stichprobe (§ 4).

### 3.2 Zahlen der Hauptperiode (2026-11-23)

| kind | Treffer | Dokumente | Anteil | verschieden | häufigste `norm` |
|---|---:|---:|---:|---:|---|
| `bplan` | 2 061 | 944 | 4,9 % | 518 | 01/009 (42), 5576/078 (40), 05/016 (39) |
| `fnp` | 265 | 57 | 0,3 % | 30 | FNP-Änderung 138 (22), 188 (21), 178 (17) |
| `produkt` | 1 277 | 874 | 4,6 % | 115 | 2528101 (181), 4242404 (108), 3135102 (94) |
| `sachkonto` | 1 574 | 1 114 | 5,8 % | 142 | 53180000 (162), 53170000 (127), 52910000 (122) |
| `psp` | 156 | 132 | 0,7 % | 13 | 1.10.36.365.01 (124) |
| `investition` | 348 | 272 | 1,4 % | 98 | 7.90000278 (106), 7.01320011 (31), 7.90000537 (31) |
| `betrag` | 27 854 | 5 101 | 26,7 % | 8 864 | 0.00 (801), 5000.00 (448), 20000.00 (418) |
| `termin` | 63 127 | 18 989 | 99,5 % | 3 324 | 2021-12-16 (302), relativ:naechste_sitzung (297) |
| `recht` | 8 358 | 3 560 | 18,6 % | 1 979 | BauGB § 34 (260), Bezirkssatzung § 3 Abs. 10 Nr. 3 (245) |
| `amt` | 17 135 | 10 696 | 56,0 % | 79 | 66 (1 497), 51 (1 195), 63 (1 010) |
| `dezernat` | 979 | 76 | 0,4 % | 10 | 06 (250), 03 (192), 02 (140) |

Zusammen 123 134 Spannen. Anteil der Dokumente mit mindestens einem Treffer je Art, nach Dokumentart:

| Dokumentart | n | 1 Plan | 2 Haushalt | 3 Betrag | 4 Termin | 5 Recht | 6 Amt |
|---|---:|---:|---:|---:|---:|---:|---:|
| Beschlussvorlage | 3 995 | 20 % | 20 % | 39 % | 99 % | 53 % | 100 % |
| Antrag | 3 321 | 1 % | 1 % | 12 % | 100 % | 2 % | 5 % |
| Bezirksvertretung Informationsvorlage | 2 699 | 2 % | 0 % | 13 % | 100 % | 6 % | 100 % |
| Anfrage | 2 351 | 1 % | 0 % | 3 % | 100 % | 3 % | 6 % |
| Bezirksvertretung Beschlussvorlage | 1 473 | 1 % | 23 % | 81 % | 100 % | 21 % | 100 % |
| Informationsvorlage | 1 324 | 1 % | 5 % | 34 % | 100 % | 19 % | 100 % |

### 3.3 Je Art: Abdeckung und typische Fehler

**Art 1, Bauleitplanung.** 518 verschiedene Pläne; 103 davon stehen in mehr als einer Schreibweise
(5580/07 und 5580-007, 5287/01 und 5287/001), die Normalisierung führt sie zusammen (dreistellig hinten,
Schrägstrich; Annahme in § 9, Frage 3). 18 Nummern kommen aus Listen („Nr. 5481/006 … und Nr. 5481/…“).
**Recall-Näherung**: in den Dokumenten mit Planwort stehen 2 423 Zeichenfolgen im Nummernformat; 400
(16,5 %) trifft keine Spanne. Das ist eine Obergrenze der Verluste, denn das Format teilen
Hausnummernbereiche („Str. 95-105“), Telefonnummern, Schuljahre und — eine Düsseldorfer Eigenheit —
die Verfahrensnummern von Wettbewerben, Workshops und Vorkaufsrechtssatzungen („Qualifizierungsverfahren
Nr. 01/021“, „Plan Nr. 09/031“). Echte Verluste beim Lesen: ein Name zwischen Schlüsselwort und Nummer
(„Bebauungsplans „Ehemaliger Güterbahnhof Oberkassel II“ (04/001)“), Plantabellen ohne Schlüsselwort
(„05/009 Nördlich Einbrunger Straße“), Dateinamen in Anlagenlisten („BPlan 06-018“, inzwischen erfasst).
Fehltreffer sah ich keine. FNP: 30 Änderungen, nur Nummern mit Schlüsselwort; die Kurzform „FNP 194“ in
Anlagenlisten wird erfasst, Tabellenköpfe („Flächennutzungsplanänderung Öffentlichkeitsbeteiligung ⏎
Nr. 178“) nicht.

**Art 2, Haushalt.** Selten (5,8 % der Dokumente), aber in festen Formaten; Schwerpunkt sind
Beschlussvorlagen der Bezirksvertretungen (23 %, Verfügungsmittel) und der Fachämter (20 %). Die 1 076
siebenstelligen Produkte fallen in 16 Produktbereiche. Fehlerbilder: „Produktsachkonto 52910000“ nennt
ein Konto, kein Produkt (acht Ziffern gelten darum als Konto); „Produktsachkonto 42 424 040 1000
53170000“ und „Sachkonto 1111114 / 1000 / 1000/ 549940400“ mischen Produkt, Kostenstelle und Konto;
„7.90000521.E0“ ist eine Investitionsmaßnahme, die acht Ziffern darin kein Konto; neunstellige
Altformen („025 281 010“) bleiben neunstellig. Mönchengladbach schreibt Investitionen als „LDI-1301“
(129 Treffer in 61 von 658 Dokumenten) und Produkte als „06 030 10“.

**Art 3, Beträge.** 27 854 Beträge in 5 101 Dokumenten. Schreibweisen: 2 244 mit Mio./Mrd., 71 mit
Tsd./T€, 275 mit der Einheit vorn („EUR 2.700“), 112 erste Zahlen einer Spanne, 388 Preise je Einheit
(„12,50 €/m²“, `;je`), 801 Nullbeträge (Tabellen). Median 50 000 €, 90-%-Quantil 5,4 Mio. €.

| Rolle (Extraktor) | Treffer | Anteil |
|---|---:|---:|
| kosten | 10 981 | 39,4 % |
| zuschuss | 5 234 | 18,8 % |
| ansatz | 4 820 | 17,3 % |
| sonstig | 3 650 | 13,1 % |
| foerderung | 1 129 | 4,1 % |
| ertrag | 1 111 | 4,0 % |
| verfuegungsmittel | 794 | 2,9 % |
| einsparung | 135 | 0,5 % |

Die Rolle ist die Kernfrage, und beim Lesen zeigen sich drei Fehlerbilder: (a) **Tabellen ohne
Schlüsselwort in der Zeile** übernehmen das Wort der Zeile davor („abzüglich U3-städt. Anteil“ wird
`foerderung`, weil die Zeile davor „Landesmittel“ sagt); (b) **Förderung in beide Richtungen**: „Förderung
BMVI (60 %)“ ist Geld des Bundes, „Regelförderung“ eines Vereins Geld der Stadt; das Wort allein trennt
das nicht; (c) **Listen ohne Satz** (Verfügungsmittel- und Kunstförderlisten) haben nur im Betreff
ein Schlüsselwort, daher der Rückgriff `;dok`. Ein neuntes Merkmal ergab sich beim Lesen: `ansatz`
(Haushaltsansatz, bereitgestellte Mittel ohne Maßnahme und Empfänger) ist häufig und weder Kosten noch
Zuschuss; das Codebuch führt es mit Vorrangregel.

**Tabellen mit Spalteneinheit** („Beträge in EUR“, „(Euro)“) sind die größte Recall-Lücke: in 546
Dokumenten mit einem solchen Kopf stehen 10 177 Zahlen mit Tausenderpunkt, davon 5 450 ohne eigene
Einheit und also ohne Spanne. Wie viele davon Beträge sind (statt Einwohnerzahlen, Flächen,
Stundenzahlen), zeigen die Recall-Dokumente (Kodierer markieren sie mit `tabelle = true`).

**Art 4, Termine.** 63 127 Zeitangaben in 99,5 % der Dokumente — fast jede Vorlage trägt ein Briefdatum
und eine Beratungsfolge mit Sitzungsdaten im Kopf. Funktion nach dem Extraktor:

| Form | frist | sitzung | zeitraum | sonst |
|---|---:|---:|---:|---:|
| Tag (31.03.2024, 19. Januar 2024) | 527 | 11 966 | 652 | 41 626 |
| Monat und Jahr | 170 | 226 | 207 | 3 790 |
| Quartal, Halbjahr | 27 | 42 | 15 | 1 228 |
| Jahr mit Zusatz („Ende 2024“) | 300 | 2 | 39 | 1 776 |
| relativ („in der nächsten Sitzung“) | 261 | 197 | – | 76 |

1 285 Fristen, davon 261 relativ. Fehlerbilder: „bis“ beendet oft eine Dauer statt eine Frist zu setzen
(„bis zum 30.11.2020 untersagt“); „vom 10.07. bis zum 17.07.2022“ fängt die Regel `zeitraum` ab (913
Fälle). „Stichtag“ ist meist Bezugsdatum einer Statistik und zählt darum nicht als Frist. Die Daten der
Beratungsfolge im Kopf stehen in einer Tabelle ohne „Sitzung am“ und laufen als `sonst` (Abschnitt
`kopf`). Zweistellige Jahre zählen nur mit zweistelligem Tag und Monat („01.02.24“), weil „3.2.10“
meist eine Gliederungsnummer ist.

**Art 5, Rechtsgrundlagen.** 8 358 Zitate in 3 560 Dokumenten (53 % der Beschlussvorlagen). Häufigste
Gesetze: BauGB 2 006, GO NRW 1 370, Bezirkssatzung 564, SGB VIII 391, Zuständigkeitsordnung 323,
KomHVO NRW 194, GewO 156, StVO 143, KAG NRW 133, BauNVO 117, KiBiz 113, SchulG NRW 109. Ohne
erkanntes Gesetz bleiben 702 (8,4 %); 382 finden es in den 60 Zeichen danach, 24 direkt davor („In
der StVO § 5“). Fehlerbilder: Aufzählungen nach einem einzelnen § enden früh („§ 45 Abs. 1 S. 1,
Abs. 9 S. 1, 3 StVO“ wird bei „Abs. 9“ abgeschnitten, das Gesetz trotzdem gefunden); getrennte Wörter
(„Gemeinde ⏎Ordnung“); 149 Zitate nennen nur „der Satzung“ oder „des Gesetzes“; Inhaltsverzeichnisse
von Satzungen („§ 11 Vorsitz im Verwaltungsrat“) sind Zitate ohne Gesetz.

**Art 6, Verwaltungseinheiten.** Das Kopffeld „Fachbereich:“ oder „Amt / Institut:“ steht in 9 995
Dokumenten (52,4 %): in 98,8 bis 100 % der Vorlagen, in **keinem** Antrag und keiner Anfrage.
Daneben 6 543 Nennungen mit Namen (Amtsverzeichnis aus den Kopffeldern: 55 Namen, drei mit mehr als
einem Code, weil Ämter umnummeriert oder umbenannt wurden) und 591 mit Nummer („Amt 66“). Gremien im
Kopffeld („Jugendhilfeausschuss“, „Behindertenrat“) und zu allgemeine Namen („Umwelt“, „BV Ost“ in
Mönchengladbach) kommen nicht ins Verzeichnis, sonst wären sie Fehltreffer. „Dezernat 06“ steht nur in
76 Dokumenten (Haushaltstabellen). Das Feld „Dezernentin / Dezernent“ in 5 669 Dokumenten nennt die
Beigeordneten mit Namen; das Skript zählt es und extrahiert es nicht (§ 9, Frage 2). **Folge für 24**:
eine Anfrage nennt ihr Ziel nicht; das antwortende Amt steht im Kopf der Antwort (Vorgang aus Vorhaben
14) und im Satz „Das Amt für Verkehrsmanagement (Amt 66) nimmt wie folgt Stellung“; das Dezernat
kommt aus einer Tabelle Amt → Dezernat mit Gültigkeitszeitraum im Profil, nicht aus dem Text.

### 3.4 Übertragbarkeit auf die anderen Datensätze

| kind | 2014–2020 | 2025 | Mönchengladbach |
|---|---|---|---|
| `bplan` | 2 351 (4,9 %) | 363 (4,5 %) | 50 (2,3 %), Format 809/N, 517/III |
| `fnp` | 336 (0,5 %) | 48 (0,2 %) | 9 (0,3 %) |
| `produkt` | 1 615 (2,9 %) | 188 (3,2 %) | 49 (6,5 %), Format 06 030 10 |
| `sachkonto` | 1 916 (3,9 %) | 223 (4,2 %) | 38 (4,9 %), Format 5238 0000 |
| `psp` | 141 (0,5 %) | 14 (0,3 %) | 2 (0,3 %) |
| `investition` | 578 (0,7 %) | 51 (1,0 %) | 129 (9,3 %), LDI-Nummern |
| `betrag` | 43 891 (22,2 %) | 5 523 (23,5 %) | 2 221 (36,2 %) |
| `termin` | 80 147 (94,7 %) | 12 315 (99,4 %) | 3 888 (98,5 %) |
| `recht` | 12 753 (17,0 %) | 2 255 (21,9 %) | 958 (33,9 %), Hauptsatzung § 10 Abs. 2 (39) |
| `amt` | 16 749 (39,0 %) | 3 143 (53,5 %) | 1 103 (70,2 %), Kopf „Fachbereich FB 64 Umwelt“ |
| `dezernat` | 481 (0,4 %) | 21 (0,3 %) | 0 |

In Klammern der Anteil der Dokumente mit Text. Die Düsseldorfer Muster tragen über alle drei Perioden;
der niedrigere Amtsanteil 2014–2020 (39 %) folgt aus dem Kopf älterer Vorlagen. Mönchengladbach
braucht eigene Muster für Plannummer, Produkt, Sachkonto, Investition und Kopffeld (alle in
`PROFILMUSTER`), die stadtneutralen Muster (Betrag, Termin, Recht) laufen ohne Änderung; das
Kopffeld steht dort in 444 Dokumenten (67,5 %, `--profil moenchengladbach`).

### 3.5 Größe der Ausgabe

Die 123 134 Spannen der Hauptperiode (Spalten wie in § 6, ohne die Messspalte `cue`) sind als Parquet
(zstd) 1 381 197 Bytes groß, als CSV 11 347 376 Bytes; ohne Termine (60 007 Zeilen) 777 799 Bytes
Parquet und 5 652 118 Bytes CSV.

### 3.6 Laufzeit

Unter Fremdlast gemessen (Supervisor, 2026-11-23: Lastmittel zeitweise 144), mit `nice -n 10`,
`POLARS_MAX_THREADS=4`, `OMP_NUM_THREADS=2` und vier Prozessen:

| Lauf | Wanduhr | `uptime` davor / danach (Lastmittel 1 min) |
|---|---:|---|
| `--alle --stichprobe` (vier Datensätze und Stichprobe) | 53,7 s, 755 MB RSS | 18:46:13 11,71 / 18:47:07 15,03 |
| Extraktion je Datensatz in diesem Lauf (Hauptperiode, 2014–2020, 2025, Mönchengladbach) | 17,2 / 27,9 / 4,1 / 2,0 s | wie oben |
| Hauptperiode in **einem** Prozess (wie ein Pipeline-Schritt), Hilfsskript mit denselben Funktionen | 41,2 s | 18:49:29 9,43 / 18:50:28 9,04 |
| `--alle --stichprobe --einzelprozess` unter starker Fremdlast | 264,0 s, 739 MB RSS | 18:53:31 15,01 / 18:58:05 35,76 (zwischendurch 40,49) |
| darin Extraktion je Datensatz | 98,8 / 29,6 / 16,6 / 2,7 s | wie oben |
| darin Hauptperiode in einem Prozess | 108,5 s | wie oben |
| `--auswertung` (Hauptperiode, Labels, alle Maße) | 23,2 s, 672 MB RSS / 16,5 s | 19:45:02 27,22 / 19:45:25 25,53; 19:49:10 17,16 / 19:49:27 15,34 |

Die Zeiten hängen an der Fremdlast um den Faktor zwei bis sechs; die ruhigen Läufe sind der
Maßstab. Stichprobe und alle Zählungen waren in beiden Läufen gleich (SHA-256 der Stichprobe
identisch).

## 4. Validierung

**Codebuch**: `validierung/12-kennungen/codebuch.toml` (Arten mit Spannen- und Normregeln, Fragen,
Rollen mit Vorrang, Funktion eines Termins, Antwortformat, Maße). **Kodierer**: zwei Kodier-Agenten
(Opus) unabhängig, ein Schlicht-Agent für die Uneinigkeiten (F4); sie sehen die markierte Stelle, aber
nicht Art, Norm und Rolle des Extraktors. Das ist kein menschlicher Goldstandard (Plan § 2.6).

**Stichprobe** (Seed 20261123, `--stichprobe`, deterministisch; SHA-256 von `stichprobe.csv`:
`07279bc3…f6ac823`), 650 Aufgaben:

- **Präzision**: 100 Treffer je Art aus der Hauptperiode, geschichtet mit Mindestzahl je Schicht, der
  Rest proportional; `schicht_n` in der CSV ist die Größe der Schicht für die Gewichtung.
  Art 1: `bplan` 70, `fnp` 30. Art 2: `produkt` 30, `sachkonto` 34, `psp` 17, `investition` 19.
  Art 3: je Rolle 10 bis 18 (damit jede Rolle eine eigene Zahl bekommt). Art 4: `frist` 30, Tag 21,
  Monat 13, Quartal 12, Jahr 12, relativ 12. Art 5: Gesetz direkt 37, nah 21, davor 20, ohne 22.
  Art 6: Kopf 37, Name 30, Nummer 16, Dezernat 17.
- **Recall**: 50 Dokumente mit 300 bis 12 000 Zeichen (zusammen 141 927), in fünf Schichten zu je zehn,
  gewählt nach Metadaten und Titel, **nicht** nach dem Extraktor: Planung (Titel nennt Bebauungs- oder
  Flächennutzungsplan, Pool 209), Haushalt (Dokumentart oder Titel mit Haushalt, Zuschuss, Förderung,
  Pool 3 148), Bezirksvertretung (Pool 4 131), Antrag und Anfrage (Pool 8 628), Zufall (Pool 18 479).
  Die Kodierer markieren dort jede Kennung jeder Art.
- **Ablage**: `validierung/12-kennungen/stichprobe.csv` (Spalten `aufgabe, typ, art, schicht,
  schicht_n, dok_id, datei, start, end`), Ausschnitte als
  `/media/konrad/xtraspace/georep/messdaten/kodierung/12-kennungen/aufgaben.jsonl` (650 Zeilen,
  929 834 Bytes; je Präzisionsaufgabe 400 Zeichen links und rechts der Markierung ⟦…⟧, je Recall-Aufgabe der
  ganze Text) und eine leere `antworten-leer.jsonl`. Das Format ist vorläufig, F4 baut den Rahmen.

**Maße, wie vor der Kodierung geplant** (Codebuch .1, `[masse]`; gemessen wurde nach den Maßen des
Supervisors in § 4.1, dort zählt der Normwert getrennt): Präzision streng (Art, Grenzen und Norm stimmen) und mild (nur die Art),
je Art gewichtet nach Schicht, mit Wilson-Intervall; Recall je Art über Überlappung, Tabellenbeträge
getrennt; Rolle als Übereinstimmung unter den streng richtigen Beträgen, mit κ; Funktion `frist` mit
Präzision und Recall; Krippendorffs α je Frage zwischen den Kodierern (unter 0,8 ist das Codebuch zu
unscharf). **Unsicherheit bei n = 100**: selbst 100 von 100 richtig ergibt ein 95-%-Wilson-Intervall
von 0,963 bis 1; 97 von 100 ergibt 0,915 bis 0,990. Das Kriterium wird am Punktschätzer gemessen, das
Intervall steht daneben. Für Art 1 und 2 enthalten die 50 Recall-Dokumente nur wenige Kennungen (die
Planungsschicht sorgt für Bebauungspläne, die Haushaltsschicht für Haushaltsnummern); ihr
Recall-Intervall wird breit (§ 9, Frage 9).

### 4.1 Ergebnis der Kodierung (2026-11-23)

**Kodierung.** Zwei Kodier-Agenten (A, B) haben alle 650 Aufgaben nach Codebuch .1 kodiert, ein
Schlicht-Agent hat 67 Uneinigkeiten entschieden (Regeln R1 bis R18 in seiner Begründung, übernommen in
`codebuch-2.toml`). Übereinstimmung der beiden vor der Schlichtung:

| Frage | gleich | α (nominal) |
|---|---:|---:|
| Art | 600 / 600 | 1,000 |
| Grenzen | 597 / 597 | 1,000 |
| Normwert | 555 / 597 | 0,929 |
| Rolle (Beträge) | 90 / 98 | 0,901 |
| Funktion (Termine) | 89 / 100 | 0,850 |
| Recall-Spannen | 502 gemeinsam, 14 nur bei einem | F1 0,986 |

Alle α liegen bei mindestens 0,8; das Codebuch ist scharf genug (Plan § 2.6). Die Endlabels: einig,
sonst Schlichtung, sonst — bei vier Präzisionsfeldern und zwölf Feldern gemeinsamer Recall-Spannen,
die dem Schlichter nicht vorlagen — der Auswerter nach den Regeln des Schlichters (R1, R3, R17, R18;
alle nur Schreibung oder durch eine Regel gedeckt). Die drei Besonderheiten des Supervisors sind
übernommen: 12-0101 („in der nächsten Sitzung“ → `frist`), 12-0012 („10.“ als eigene Spanne nach R10),
Rechtsketten mit demselben Gesetz als eine Spanne (R8; 12-0023, 12-0431, 12-0502). Alle 516
Recall-Spannen fanden ihre Stelle im Text. `labels.csv` (3 650 Zeilen, Werte als JSON, Offsets statt
Textausschnitten) und README liegen in `validierung/12-kennungen/`.

**Maße** (Supervisor, 2026-11-23): Präzision = Art und Grenzen richtig, daneben mild = nur die Art;
Normwert getrennt unter den streng richtigen Treffern; Recall an den 50 Dokumenten mit strenger
(gleiche Grenzen) und milder Grenze (Überlappung), Tabellenbeträge getrennt; Rolle und Funktion als
Übereinstimmung mit dem Endlabel, Kriterium je ≥ 0,8. Präzision, Rolle und Funktion sind mit
`schicht_n` / Quote gewichtet, das Wilson-Intervall nutzt das effektive n nach Kish. Den Recall
bewerte ich **ungewichtet**: die fünf Recall-Schichten sind nacheinander aus überlappenden Pools
gezogen, Pool/10 ist also kein Kehrwert einer Auswahlwahrscheinlichkeit; die gewichtete Zahl steht als
Gegenprobe daneben und ist bei kleinem effektivem n (Art 1 und 5: 8) nicht belastbar.

**Präzision, Recall und Normwert je Art** (Hauptperiode; in Klammern 95-%-Wilson):

| Art | Präzision streng | mild | Recall streng | Recall mild | Normwert gleich | Norm äquivalent |
|---|---|---|---|---|---|---|
| 1 Bauleitplanung | **1,000** [0,957; 1] n 100 | 1,000 | **0,901** [0,810; 0,951] 64/71 | 0,901 | 1,000 | 1,000 |
| 2 Haushalt | **1,000** [0,956; 1] n 100 | 1,000 | **0,524** [0,324; 0,717] 11/21 | 0,524 | 0,978 [0,920; 0,994] | 1,000 |
| 3 Betrag | **0,962** [0,885; 0,988] n 100 | 0,983 | **0,955** [0,889; 0,982] 84/88 | 0,966 | 1,000 | 1,000 |
| 4 Termin | **0,992** [0,867; 1] n 100 | 1,000 | **0,960** [0,923; 0,980] 192/200 | 0,960 | 0,994 | 0,994 |
| 5 Rechtsgrundlage | **0,883** [0,763; 0,947] n 100 | 1,000 | **0,932** [0,851; 0,971] 69/74 | 0,986 | 0,822 [0,677; 0,910] | 0,853 |
| 6 Verwaltungseinheit | **0,964** [0,896; 0,988] n 100 | 0,988 | **0,808** [0,681; 0,892] 42/52 | 0,846 | 0,713 [0,602; 0,803] | 1,000 |

Gewichteter Recall (Gegenprobe, streng): Art 1 0,959 (n_eff 8), Art 2 0,631 (12), Art 3 0,862 (50),
Art 4 0,967 (92), Art 5 0,559 (8; eine einzige verpasste Spanne in einem Zufallsdokument trägt das
Gewicht), Art 6 0,761 (24). „Norm äquivalent“ ist eine Diagnose, kein Maß: gleich bis auf Schreibung,
die Codebuch .1 offen ließ (Satz/S., „(3)“/„Abs. 3“, Suffix .A0) und, bei Ämtern, nach Abbildung des
Namens über das Amtsverzeichnis aus den Kopffeldern auf die Nummer (R1 lässt die Kodierer den Namen
schreiben, wo die Nummer nicht im Ausschnitt steht; der Extraktor schreibt die Nummer).

Recall je Schicht (streng, gefunden/alle): Bauleitplanung Planung 61/68; Haushalt Haushalt 4/11,
Bezirk 1/2, Fraktion 2/2, Zufall 4/6; Betrag Haushalt 50/50, Bezirk 17/17, Fraktion 8/8, Zufall 9/13;
Termin 192/200 über alle Schichten; Rechtsgrundlage Planung 65/66, übrige 4/8; Amt Planung 10/11,
Haushalt 10/13, Bezirk 16/20, Fraktion 1/1, Zufall 5/7. Drei Tabellenbeträge ohne eigene Einheit
(`tabelle = true`) fand der Extraktor nicht (wie angelegt).

**Rolle der Beträge**: Übereinstimmung **0,508** [0,389; 0,626] (n 98, n_eff 65). Je Rolle des
Extraktors richtig: verfuegungsmittel 10/10, kosten 13/18, einsparung 5/10, ertrag 5/10, zuschuss
5/13, foerderung 4/11, ansatz 4/13, sonstig 3/13. Häufigste Verwechslungen (Extraktor → Label):
sonstig → kosten 7, ansatz → verfuegungsmittel 5, foerderung → zuschuss 4, kosten →
verfuegungsmittel 3. Von 23 Beträgen mit Label `verfuegungsmittel` erkennt der Extraktor 10.

**Funktion der Termine**: Übereinstimmung **0,613** [0,430; 0,769] (n 100, n_eff 28). Die Klasse
`frist` hat Präzision 15/30 und im Recall-Teil Recall 2/6. Häufigste Verwechslungen: sonst → frist 14
(Termine eines Terminplans: Baubeginn, Fertigstellung, Quartale), sonst → sitzung 11 (Daten der
Beratungsfolge im Kopf, die ohne „Sitzung am“ in einer Tabelle stehen), frist → zeitraum 9 („bis“
beendet eine Dauer: „bis zum 30.11.2020 untersagt“, „gültig bis“), sonst → zeitraum 6, frist →
sonst 6 (vergangene Daten: „bis zum 30.06.2020 ausgegeben“).

### 4.2 Ursachen der Verfehlungen

Aus der Fehlerliste (`messdaten/kodierung/12-kennungen/fehler-extraktor.jsonl`, lokal, mit Kontext):

| Art, Maß | Fehler | Ursache | Abhilfe | lohnt? |
|---|---|---|---|---|
| 5 Präzision streng 0,883 | 30 von 100 `zu_kurz`; je Schicht: Gesetz direkt 2/37, Gesetz in der Nähe 18/21, Gesetz davor 2/20, ohne Gesetz 8/22 | Kette endet vor dem Gesetz an Spezifizierern, die die Grammatik nicht kennt: „Abs. (4)“, „Nr. 1.2“, „Abs. 1 bis 3“, „Nr. 5, 8 und 9“, „Absatz 1 und 2“, „Abs. 1 b“, „ff.“; Gesetzesnamen mit Zusatz („Straßen- und Wegegesetz des Landes Nordrhein-Westfalen“, „‚Zuständigkeitsordnung der …‘“, „Allgemeinen Eisenbahngesetzes“, „Straßenverkehrs Ordnung“) | Kettengrammatik um diese Spezifizierer, Gesetzesname mit Adjektiv, Genitivzusatz und Anführungszeichen; R8 (gleiches Gesetz über „i. V. m.“ = eine Spanne) | ja: 26 der 30 Fehler sind dieselbe Lücke |
| 5 Normwert 0,822 | 26 von 70 | Schreibung (S./Satz, „(3)“, „in Verbindung mit“), Kurzformen gegen R4 (ZO, KomHVO ohne NRW, WbK), Gesetz aus dem Satz davor (R6), Gremium „AG § 78“ als Gesetz | R3/R4/R6 in `gesetz_kanon` und `para_kanon` | ja, mit derselben Runde |
| 2 Recall 0,524 | 10 von 21 | Kontierungen ohne Schlüsselwort je Glied: „1111114/1000/5490200/2“, „Konto 1111114 5/74990600“ (Produkt nach „Konto“), „Profitcenter/Konto/Maßnahme 42 424 04 /78170100/ 7.90000278“ (Fenster endet am Wort „Maßnahme“), Tabellenzeile „1111115 13 52910000“, „Haushaltsstelle:⏎Liste B) … 11.111.05.001 52415900“, „Produktes 2528101“ | ein Zerleger für Kontierungsketten (Produkt / Kostenstelle / Konto / Maßnahme nach Stellenzahl), Beugung „Produktes“ | ja, aber nur mit einer Bestätigung an mehr Haushaltsdokumenten: 21 Spannen sind wenig |
| 6 Recall 0,808 / 0,846 | 10 von 52 (8 ganz verpasst) | Beugung („Umweltamts“, „Sportamts“, „Stadtplanungsamtes“), „Bezirksverwaltungsstelle“ im Text (mit und ohne Nummer; das Verzeichnis nimmt nur Namen mit Code auf), Kurzname „Gartenamt“, Kopffeld mit mehreren Ämtern (je Zeile eine Spanne) | Genitiv-s, Muster für Bezirksverwaltungsstelle, mehrzeiliges Kopffeld, Kurznamen aus dem Profil | ja, klein |
| 6 Normwert 0,713 | 23 von 80 | Konvention: R1 schreibt den Namen, wo die Nummer nicht im Ausschnitt steht; der Extraktor nimmt die Nummer aus dem Verzeichnis | keine im Extraktor; Codebuch .2 vergleicht über das Verzeichnis | — |
| 3 Rolle 0,508 | 49 von 98 | die Regeln R11 bis R15 brauchen Wissen über Dokument und Tabelle: Bauunterhaltungsmittel der Bezirksvertretung als Verfügungsmittel (R11), eigene benannte Maßnahme gegen Etat (R12), fremdes Vorhaben (R14), Spaltenkopf (R15); Schlüsselwörter im Satz tragen das nicht | eine Regelrunde (R11 als Dokumentmerkmal) brächte grob 12 der 49 Fehler, also rund 0,63 — nicht 0,8 | nein: die Rolle fällt; nur der Betrag (Briefing) |
| 4 Funktion 0,613 | 51 von 100 (ungewichtet; die Tagesschicht mit 8 Fehlern von 21 trägt das Gewicht) | Kopftabelle der Beratungsfolge (R20) und „Sitzung … am“ über einen Zeilenwechsel sind strukturelle Lücken (die 8 Fehler der Tagesschicht); Terminplan (R19), Dauer gegen Frist (R16, R18) und vergangene Daten (R17) brauchen Satzverständnis (die übrigen 43) | R20 allein höbe die gewichtete Übereinstimmung auf geschätzt 0,94, weil die Tagesschicht das Gewicht trägt; die Klasse `frist` bliebe bei rund 0,5 Präzision — für die Wiedervorlage (29) unbrauchbar | nein: die Funktion `frist` fällt; die Zeitangabe bleibt (§ 9, Frage 12) |

Kleinere Fehler der Arten, die das Kriterium erreichen: Betrag — „2021 Mio. EUR“ und „2023 €“ in
Tabellenköpfen als Betrag (2 × `keine`), Vorzeichen „+“ nicht in der Spanne (3 × `zu_kurz`), im Recall
„Euro 172.000“, „€⏎40.000“ (Einheit vorn als Wort oder über den Zeilenwechsel); Termin — „Ende Februar
2021“, „Mitte Juli 2021“ ohne Zusatz, „bis zur nächsten Sitzung“ mit „bis zur“, im Recall
Datumsangaben über einen Zeilenwechsel („23. Februar⏎2022“, „Ende des⏎Jahres 2023“), unvollständige
Daten einer Spanne („22. April bis …“, R10), ISO-Daten in Dateinamen; Bauleitplanung — FNP-Nummern in
Tabellenköpfen („Flächennutzungsplanänderung Stellungnahmen⏎Nr. 188“) und als Ordinalzahl über den
Zeilenwechsel (5 von 30), „Plan Nr. 5776/014“ (2). Die Investitionsnummer trägt das Suffix .A0 im
Normwert (4 von 19, R7).

## 5. Urteil gegen das Kriterium

**Kriterium** (Briefing, unverändert): Präzision ≥ 0,95 und Recall ≥ 0,85 je Art; die Rolle eines
Betrags mit ≥ 0,8, sonst kommt nur der Betrag; die Funktion eines Termins mit ≥ 0,8 (Supervisor, vor
der Messung festgelegt, § 9, Frage 6). Gemessen am Punktschätzer, das Intervall daneben (§ 4).

| Art | Präzision | Recall | Normwert | Urteil |
|---|---|---|---|---|
| 1 Bauleitplanung | 1,000 ✓ | 0,901 ✓ | 1,000 | **bauen** (untere Grenze des Recall-Intervalls 0,81) |
| 2 Haushalt | 1,000 ✓ | 0,524 ✗ | 0,978 | **umbauen**: Kontierungszerleger, Bestätigung an einer eigenen Haushaltsschicht |
| 3 Betrag | 0,962 ✓ | 0,955 ✓ | 1,000 | **bauen** (nur der Betrag) |
| 3 Rolle | 0,508 ✗ (≥ 0,8) | – | – | **fällt** (Briefing: dann kommt nur der Betrag) |
| 4 Termin | 0,992 ✓ | 0,960 ✓ | 0,994 | **bauen** (nur die Zeitangabe) |
| 4 Funktion | 0,613 ✗ (≥ 0,8) | `frist` 2/6 | – | **fällt** |
| 5 Rechtsgrundlage | 0,883 ✗ | 0,932 ✓ | 0,822 | **umbauen**: Kettengrammatik und Gesetzesnamen, R3 bis R8 |
| 6 Amt | 0,964 ✓ | 0,808 ✗ (mild 0,846) | 0,713 (äquivalent 1,000) | **umbauen**: Beugung, Bezirksverwaltungsstelle, mehrzeiliger Kopf |
| 6 Dezernat | 17/17 | – (keine Spanne in den Recall-Dokumenten) | 17/17 | **umbauen wie zuvor**: Dezernat über eine Tabelle Amt → Dezernat im Profil, nicht aus dem Text |

**Umbauen** heißt wie in Vorhaben 14: eine Runde, gemessen an einer **frischen Bestätigungsstichprobe**
nach Codebuch .2, nie an denselben Labels. Vorschlag: Seed `12-2`, ohne die 650 Aufgaben, je
umgebauter Art 100 Treffer des neuen Extraktors (Art 2 und 6 mit eigener Schicht für die neuen Muster,
Art 5 mit den Schichten „Kette mit Spezifizierern“ und „Gesetzesname mit Zusatz“) und 30 Recall-
Dokumente aus Haushaltsdokumenten (Art 2 hat im ersten Durchgang nur 21 Spannen) sowie 20 aus
Bezirksvertretungen (Ämter). Verfehlt eine Art dort wieder, fällt sie. Die kleinen Korrekturen an
Betrag und Termin (Vorzeichen „+“, Jahreszahl im Tabellenkopf, „Euro 172.000“, Datum über den
Zeilenwechsel, „Ende Februar 2021“) baut Stufe 2 mit Tests und prüft sie in derselben
Bestätigungsrunde mit je 30 Treffern mit.

**Zwei Wege, die ich nicht vorschlage**: eine Regelrunde für die Rolle (bestenfalls rund 0,63, § 4.2)
und eine für die Funktion `frist`. Wer sie für 21 oder 29 braucht, misst neu mit einem Modell über F5
an frischen Labels; ein binärer Merker „aus bezirklichen Mitteln“ (Verfügungs- und
Bauunterhaltungsmittel der Bezirksvertretungen) wäre der aussichtsreichste Teil (Extraktor heute 10/10
richtig, aber nur 10 von 23 gefunden) und eine Frage an den Supervisor (§ 9, Frage 11).

## 6. Bauplan Stufe 2

Stufe 2 baut die Arten mit Urteil „bauen“ (§ 5): **Bauleitplanung** (`bplan`, `fnp`), **Betrag**
(`betrag`, ohne Rolle) und **Termin** (`termin`, ohne Funktion). Haushalt (`produkt`, `sachkonto`,
`psp`, `investition`), Rechtsgrundlage (`recht`) und Amt (`amt`) kommen erst dazu, wenn ihr Umbau die
Bestätigungsstichprobe besteht (§ 5); der Code ist so geschnitten, dass sie je `kind` hinter einem
Schalter dazukommen, ohne den Schritt umzubauen. Das Dezernat kommt aus einer Tabelle im Profil.

**Beitrag** `identifiers` (Register `georep.enrich.CONTRIBUTIONS`, Fundament F2), eine Zeile im Tupel,
hinter `sections` (11), wenn es da ist; sonst mit dem groben Abschnittsersatz aus § 3.1.

**Module** (neu, rund 500 Zeilen für die drei Arten):

- `src/georep/enrich/identifiers/__init__.py`: `CONTRIBUTION = Contribution(name="12-kennungen", steps=…,
  tables=…)`, Schritt `identifiers`, `IDENTIFIERS_SCHEMA_VERSION = 1` (Schema-Version aus der Konstante,
  CLAUDE.md).
- `…/patterns.py`: kompiliert die Muster aus den Settings (stadtneutral aus `defaults.toml`,
  stadtspezifisch aus dem Profil).
- `…/extract.py`: reine Funktionen je Art (`bauleitplanung`, `betraege`, `termine`; später `haushalt`,
  `rechtsgrundlagen`, `verwaltung`) mit `(text, patterns) -> list[Span]`, dazu `betrag_norm`,
  `bplan_norm`, `datum_iso`. Übernommen aus `kennungen-messung-v1` mit den kleinen Korrekturen aus
  § 4.2: Vorzeichen „+“ in der Spanne, keine Jahreszahl mit Einheit im Tabellenkopf als Betrag,
  Einheit vorn auch als Wort („Euro 172.000“) und über den Zeilenwechsel, Datum und „Ende des Jahres“
  über einen Zeilenwechsel, Monat mit Zusatz („Ende Februar 2021“ → `2021-02~ende`), Jahreszeiten in
  der Normform `2022~herbst`, `relativ:vor_sommerpause`, „bis zur nächsten Sitzung“ ohne „bis zur“, FNP
  im Tabellenkopf und als Ordinalzahl über den Zeilenwechsel. Jede Korrektur bekommt ihren Test aus
  § 4.2 und eine Schicht in der Bestätigungsrunde (§ 5).
- Keine Rolle, keine Funktion (beide fallen, § 5); kein `roles.py`.

**Eingaben**: Rohtextstore aus F1 (`cache_root/<profil>/text/rohtexte.parquet`, Schritt `raw_texts`),
`interim/papers.parquet` für die Dokument-ID; Abschnitte aus 11, wenn vorhanden.

**Ausgabe** `processed/kennungen.parquet`, eine Zeile je Spanne, sortiert nach `id, start, end, kind`:

| Spalte | Typ | Inhalt |
|---|---|---|
| `id` | String | OParl-Paper-ID (je Datei die kleinste; nach dem Join sortieren) |
| `start`, `end` | Int64 | Zeichenoffsets in den Rohtext, `0 <= start < end <= len(text)` |
| `kind` | String (Enum) | `bplan, fnp, betrag, termin` (später `produkt, sachkonto, psp, investition, recht, amt`) |
| `value` | String | Text der Spanne |
| `norm` | String | Plannummer, `FNP-Änderung n`, Betrag als Dezimalzahl in Euro, Termin nach Codebuch .2 |
| `section` | String | Abschnitt (aus 11, sonst Ersatz) |
| `extractor` | String | `identifiers-v1` |
| `attr` | String, nullbar | nur die Form, keine Deutung: Betrag `je`, `spanne`; Termin `tag`, `monat`, `quartal`, `jahr`, `relativ` |

Die F3-Felder bleiben, wie F3 sie festlegt; `attr` ist eine Erweiterungsspalte (§ 9, Frage 1).

**Verträge** an den Batch-Grenzen (`georep.contracts`): Spannen im Text, sortiert, keine Überlappung
innerhalb eines `kind`; `norm` eines Betrags ist eine Dezimalzahl; `norm` eines Termins passt zu den
Normformen des Codebuchs .2. Kein `deal.pure` in der heißen Schleife (CLAUDE.md).

**Tests**:

- Beispiele aus dem Codebuch .2 und § 4.2 als Unit-Tests (`tests/unit/test_identifiers.py`): jede
  Schreibweise eines Betrags, „5.000 bis 10.000 Euro“, „Bezirk 6 800 Euro“ (kein Betrag 6 800),
  „+536.000EUR“, „2021 Mio. EUR“ im Tabellenkopf (kein Betrag), „Euro 172.000“, „10. und 11. Juni 2023“
  (zwei Termine, R10), „23. Februar⏎2022“, „Ende Februar 2021“, „Vorlage APS/130/2020“ (keine
  Plannummer), „die 188.⏎Änderung des Flächennutzungsplans“.
- hypothesis (`tests/property/`): für jeden Text liegen alle Spannen im Text und sind sortiert; ein
  Betrag, den eine Formatfunktion deutsch schreibt (Tausenderpunkt, Komma, Mio.), wird zur selben
  Dezimalzahl; jedes gültige Datum in jeder Schreibweise ergibt dasselbe ISO-Datum; ein Text ohne
  Ziffern ergibt keine Spanne.
- grep-Test „kein Stadtwort“: Nummernformate und Kopffeldnamen stehen nur im Profil.
- Golden Master unberührt (der Schritt ist neu und schreibt eine neue Datei).

**Settings** (Anhängeregel aus `00-synergien.md`, § 2): Modell `IdentifierSettings` vor
`class Settings`, Feld `identifiers` am Ende; in `defaults.toml` ein Block `# --- Vorhaben 12:
Kennungen und Beträge` mit `enabled = false`, `kinds = ["bplan", "fnp", "betrag", "termin"]`,
Einheiten, Faktoren, Monatsnamen, Wörtern relativer Termine; in `profiles/duesseldorf.toml` und
`profiles/moenchengladbach.toml` je ein Block `[identifiers]` mit den Plannummernformaten aus
`PROFILMUSTER` (die Periodenprofile erben über `base`). Jeder Eintrag mit Kommentar und Beispiel.

**Berührte Dateien**: neu `src/georep/enrich/identifiers/`, eine Zeile in
`src/georep/enrich/__init__.py`, Modell und Feld in `src/georep/settings.py`, Block am Ende von
`src/georep/defaults.toml`, `src/georep/profiles/duesseldorf.toml`, `…/moenchengladbach.toml`;
`docs/architecture.md` (Abschnitt Vorverarbeitung), `docs/decisions.md` (Eintrag ohne Nummer: Rolle und
Funktion gemessen und verworfen, mit den Zahlen aus § 4.1).

**Laufzeit**: rund 41 s für alle Arten der Hauptperiode in einem Prozess bei ruhigem Rechner, 109 s
unter Fremdlast (§ 3.6), offline; für drei Arten weniger. `nox -s bench` bekommt eine Stufe über 200
Dokumente. **Paket**: nicht nötig, der Schritt rechnet aus dem Rohtextpaket (F1) in unter einer
Minute; wer Pages den Schritt ersparen will, packt `kennungen.parquet` mit `georep pack --identifiers`.

**Umbau (parallel, eigener Branch-Abschnitt)**: Kontierungszerleger (Art 2), Kettengrammatik und
Gesetzesnamen mit R3 bis R8 (Art 5), Beugung, Bezirksverwaltungsstelle und mehrzeiliger Kopf (Art 6),
dann die Bestätigungsstichprobe nach § 5 mit `codebuch-2.toml`; das Messskript bekommt dafür
`--stichprobe-2` und `--auswertung-2` nach dem Muster von Vorhaben 14. Erst nach bestandener Runde
kommen die `kind`s in `kinds`.

## 7. Bauplan Stufe 3

Keine eigene Unterseite (Briefing: Download). `kennungen.parquet` im Tabellenregister
(`report/tables.py` über das Register), mit `schema.json`-Eintrag; nur die `kind`s, die das Kriterium
erreicht haben (heute `bplan`, `fnp`, `betrag`, `termin`). Größe gemessen (§ 3.5): alle Arten als
Parquet 1,4 MB, als CSV 11,3 MB; die CSV ist für die Seite zu groß, also Parquet, und als CSV nur
Bauleitplanung und Beträge. Text an der Tabelle: was jede Spalte heißt, Stichprobengröße, Güte je Art
(§ 4.1) und „geprüft von zwei KI-Kodierern an 100 Treffern und 50 Dokumenten je Art, nicht von
Menschen“ (Plan § 2.6); ausdrücklich, dass Beträge **keine Rolle** tragen (Kosten, Zuschuss und
Einnahme sind nicht unterschieden) und Termine **keine Frist** markieren. Keine Personennamen in
`value`. Zulieferer für 21 (Beträge ohne Rolle; der Abschnitt „Finanzielle Auswirkungen“ aus 11 als
Filter), 24 (Amt erst nach dem Umbau) und 29 (Plannummern; Fristen nicht).

## 8. Vorab festgelegte Hypothesen

Keine; Vorhaben 12 ist Extraktion, keine Analyse.

## 9. Risiken und offene Fragen

Stand nach der Kodierung; beantwortete Fragen mit der Antwort, neue ab Nummer 11.

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 1 | `attr` als Erweiterungsspalte neben den F3-Feldern? | F3 legt das gemeinsame Schema fest | ja, aber nur für die Form (`je`, `spanne`, `tag` …); Rolle und Funktion entfallen (§ 5) |
| 2 | Das Kopffeld „Dezernentin / Dezernent“ nennt Beigeordnete mit Namen (5 669 Dokumente). Extrahieren? | Plan § 1: keine Personen aus freiem Text; 24 braucht das Dezernat | nicht extrahieren; Dezernat über eine Tabelle Amt → Dezernat mit Gültigkeitszeitraum im Profil, Quelle der öffentliche Dezernatsverteilungsplan |
| 3 | Ist „5674/26“ derselbe Plan wie „5674/026“? | Normalisierung führt 103 Pläne zusammen | ja; die Kodierer haben in 100 Fällen jede Norm so geschrieben (Normwert 1,000); in 16 gegen das Bebauungsplanverzeichnis prüfen |
| 4 | Zählt „Plan Nr.“? | dasselbe Format wie Wettbewerbe und Satzungen | **beantwortet durch die Labels**: ja, wenn der Text dieselbe Nummer als Bebauungsplan behandelt (Codebuch .2); Wettbewerbe und Satzungen nicht |
| 5 | Tabellenbeträge mit Spalteneinheit aufnehmen? | bis zu 5 450 Zahlen | nein: der Recall erreicht 0,955 ohne sie; in den 50 Dokumenten markierten die Kodierer nur 3 |
| 6 | Kriterium der Funktion `frist`? | 29 braucht sie | **beantwortet** (Supervisor, vor der Messung): ≥ 0,8; siehe Frage 12 |
| 7 | Termine aus Kopf und Beratungsfolge behalten? | 99,5 % Abdeckung, wenig Inhalt | behalten, mit `section = kopf` |
| 8 | Strenge Präzision bei langen Rechtsketten? | Grenzen sind unscharf | streng gilt (Supervisor); die Kodierer waren sich bei den Grenzen in 597 von 597 Fällen einig, die Grenzen sind also nicht unscharf, sondern der Extraktor zu kurz |
| 9 | Reichen 50 Recall-Dokumente für Art 1 und 2? | wenige Kennungen | für Art 1 ja (71 Spannen); für Art 2 nein (21 Spannen): die Bestätigungsrunde nimmt 30 Haushaltsdokumente |
| 10 | Offsets der Messdatei gegen den Store aus F1? | Labels zeigen auf Zeichenpositionen | ja, wenn F1 denselben Text liefert; Prüfung über `pdf_sha256` und Textgleichheit |
| 11 | Soll ein binärer Merker „aus bezirklichen Mitteln“ (Verfügungs- und Bauunterhaltungsmittel der Bezirksvertretungen, R11) für 21 gemessen werden? | 21 fragt nach den Verfügungsmitteln; die volle Rolle fällt | nein, nicht in dieser Runde; 21 entscheidet in seiner Stufe 1, ob es den Merker braucht, und misst ihn dann an frischen Labels |
| 12 | Meint das Kriterium der Funktion die Übereinstimmung über vier Klassen oder die Klasse `frist`? | die Kopfregel R20 höbe die Übereinstimmung auf geschätzt 0,94, die Klasse `frist` bliebe bei rund 0,5 | die Klasse `frist`, weil nur sie der Wiedervorlage (29) dient; darum fällt die Funktion auch nach einem Umbau |
| 13 | Normwert des Amts: Nummer aus dem Verzeichnis (Extraktor) oder Name (R1 der Kodierer)? | Normwert 0,713 gleich, 1,000 nach Abbildung | der Extraktor bleibt bei der Nummer (24 braucht sie); das Codebuch .2 lässt die Kodierer den Namen schreiben, der Vergleich bildet ihn über das Verzeichnis ab |

**Risiken**: Die Bestätigungsrunde für Haushalt, Recht und Amt braucht wieder zwei Kodier-Agenten und
einen Schlicht-Agenten (rund 400 Aufgaben); das Recall-Intervall der Bauleitplanung reicht bis 0,81
(64 von 71); ältere Vorlagen (2014–2020) und Mönchengladbach sind nicht kodiert — die Güte gilt für die
Hauptperiode, die Übertragbarkeit nur nach den Zählungen in § 3.4.

## 10. Änderungen durch die Synergie (füllt der Supervisor)
