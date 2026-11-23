# Vorhaben 12: Kennungen und Beträge

Stand 2026-11-23, Stufe 1. Briefing: [plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md),
§ 11. Messskript: [12-kennungen-messung.py](12-kennungen-messung.py). Codebuch und Stichprobe:
`validierung/12-kennungen/`. **Urteil: vorläufig, Validierung ausstehend** (§ 5).

Alle Zahlen dieses Dokuments rechnet das Skript nach:

```bash
uv run python docs/plans/12-kennungen-messung.py --alle --stichprobe   # 54 s auf 4 Kernen, s. § 3.6
uv run python docs/plans/12-kennungen-messung.py --einzelprozess   # dazu die Zeit in einem Prozess
uv run python docs/plans/12-kennungen-messung.py --profil moenchengladbach   # Einzelheiten je Profil
uv run python docs/plans/12-kennungen-messung.py --beispiele betrag:sonstig   # 40 Beispiele mit Kontext
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

**Maße** (Codebuch, `[masse]`): Präzision streng (Art, Grenzen und Norm stimmen) und mild (nur die Art),
je Art gewichtet nach Schicht, mit Wilson-Intervall; Recall je Art über Überlappung, Tabellenbeträge
getrennt; Rolle als Übereinstimmung unter den streng richtigen Beträgen, mit κ; Funktion `frist` mit
Präzision und Recall; Krippendorffs α je Frage zwischen den Kodierern (unter 0,8 ist das Codebuch zu
unscharf). **Unsicherheit bei n = 100**: selbst 100 von 100 richtig ergibt ein 95-%-Wilson-Intervall
von 0,963 bis 1; 97 von 100 ergibt 0,915 bis 0,990. Das Kriterium wird am Punktschätzer gemessen, das
Intervall steht daneben. Für Art 1 und 2 enthalten die 50 Recall-Dokumente nur wenige Kennungen (die
Planungsschicht sorgt für Bebauungspläne, die Haushaltsschicht für Haushaltsnummern); ihr
Recall-Intervall wird breit (§ 9, Frage 9).

**Stand**: Kodierung ausstehend. Die Zahlen kommen nach der Kodierung in diesen Abschnitt.

## 5. Urteil gegen das Kriterium

**Kriterium** (Briefing, unverändert): Präzision ≥ 0,95 und Recall ≥ 0,85 je Art; die Rolle eines
Betrags mit ≥ 0,8, sonst kommt nur der Betrag. Urteil **vorläufig, Validierung ausstehend**; was hier
steht, ist die Erwartung aus dem Lesen, keine Messung.

| Art | Urteil (vorläufig) | Erwartung und Risiko |
|---|---|---|
| 1 Bauleitplanung | **bauen** | Präzision hoch (beim Lesen kein Fehltreffer); Recall hängt an Plantabellen ohne Schlüsselwort und Namen zwischen Wort und Nummer (Näherung: höchstens 16,5 % Verlust, davon viele keine Pläne) |
| 2 Haushalt | **bauen** | feste Formate, aber je Stadt eigene; Risiko bei gemischten Kontierungen (Produkt/Konto/Kostenstelle in einer Zeichenfolge) |
| 3 Betrag | **bauen** (Betrag) | Spanne und Normalisierung sind regelhaft; Recall-Risiko sind Tabellen mit Spalteneinheit (bis zu 5 450 Zahlen) |
| 3 Rolle | **offen**, Kernfrage | Heuristik nach Schlüsselwörtern; 13,1 % `sonstig`, Fehlerbilder (a) bis (c) in § 3.3. Erreicht sie 0,8 nicht, kommt nur der Betrag (Briefing), und 21 fasst Beträge ohne Rolle zusammen oder nimmt den Abschnitt „Finanzielle Auswirkungen“ aus 11 als Filter |
| 4 Termin | **bauen** (Zeitangabe) | Datumsformate sind eindeutig; die Funktion `frist` ist schwerer (Dauer gegen Frist) und hat im Briefing kein eigenes Kriterium (§ 9, Frage 6) |
| 5 Rechtsgrundlage | **bauen** | Gesetz und erster Paragraph sind verlässlich, die Grenzen langer Ketten weniger; streng gemessen ist das das Risiko |
| 6 Amt | **bauen** (Kopf und Text) | Kopffeld strukturiert; Namen aus dem selbst gebauten Verzeichnis |
| 6 Dezernat | **umbauen** | im Text fast nie (76 Dokumente); Dezernat über eine Tabelle Amt → Dezernat im Profil statt aus dem Text |

Wer nach der Kodierung eine Art unter dem Kriterium findet, baut sie nicht oder nur als Variante, die
die Seite nicht zeigt (Plan § 2.6: Stufe 3 zeigt nur Validiertes).

## 6. Bauplan Stufe 2

**Beitrag** `identifiers` (Register `georep.enrich.CONTRIBUTIONS`, Fundament F2), eine Zeile im Tupel,
hinter `sections` (11), wenn es da ist; sonst mit dem groben Abschnittsersatz aus § 3.1.

**Module** (neu, rund 600 Zeilen):

- `src/georep/enrich/identifiers/__init__.py`: `CONTRIBUTION = Contribution(name="12-kennungen", steps=…,
  tables=…)`, Schritt `identifiers`, `IDENTIFIERS_SCHEMA_VERSION = 1` (Schema-Version aus der Konstante,
  CLAUDE.md).
- `…/patterns.py`: kompiliert die Muster aus den Settings (stadtneutral aus `defaults.toml`,
  stadtspezifisch aus dem Profil), Amtsverzeichnis aus den Kopffeldern.
- `…/extract.py`: reine Funktionen je Art (`bauleitplanung`, `haushalt`, `betraege`, `termine`,
  `rechtsgrundlagen`, `verwaltung`) mit `(text, patterns) -> list[Span]`, dazu `betrag_norm`,
  `bplan_norm`, `gesetz_kanon`, `para_kanon`, `datum_iso`.
- `…/roles.py`: Rolle eines Betrags und Funktion eines Termins.

**Eingaben**: Rohtextstore aus F1 (`cache_root/<profil>/text/rohtexte.parquet`, Schritt `raw_texts`),
`interim/papers.parquet` für die Dokument-ID; Abschnitte aus 11, wenn vorhanden.

**Ausgabe** `processed/kennungen.parquet`, eine Zeile je Spanne, sortiert nach `id, start, end, kind`:

| Spalte | Typ | Inhalt |
|---|---|---|
| `id` | String | OParl-Paper-ID (je Datei die kleinste; nach dem Join sortieren) |
| `start`, `end` | Int64 | Zeichenoffsets in den Rohtext, `0 <= start < end <= len(text)` |
| `kind` | String (Enum) | `bplan, fnp, produkt, sachkonto, psp, investition, betrag, termin, recht, amt, dezernat` |
| `value` | String | Text der Spanne |
| `norm` | String | normalisiert (Betrag als Dezimalzahl in Euro, Termin ISO, Recht kanonisch, Amt Code) |
| `section` | String | Abschnitt (aus 11, sonst Ersatz) |
| `extractor` | String | `identifiers-v1` |
| `attr` | String, nullbar | Rolle (`kosten` … `sonstig`, Zusätze `;je`, `;spanne`, `;dok`), Funktion (`frist`, `sitzung`, `zeitraum`, `sonst`), Herkunft (`kopf`, `name`, `nummer`, `gesetz_nah` …) |

Die F3-Felder bleiben, wie F3 sie festlegt; `attr` ist eine Erweiterungsspalte (§ 9, Frage 1). Dazu
`processed/aemter.parquet` (Name, Code, Häufigkeit, erstes und letztes Datum) für 24.

**Verträge** an den Batch-Grenzen (`georep.contracts`): Spannen im Text, sortiert, keine Überlappung
innerhalb eines `kind`; `norm` eines Betrags ist eine Dezimalzahl; `norm` eines Termins passt zu ISO
oder `relativ:`. Kein `deal.pure` in der heißen Schleife (CLAUDE.md).

**Tests**:

- Beispiele aus dem Codebuch und § 3.3 als Unit-Tests (`tests/unit/test_identifiers.py`): jede
  Schreibweise eines Betrags, „5.000 bis 10.000 Euro“, „Bezirk 6 800 Euro“ (kein Betrag 6 800),
  „vom 10.07. bis zum 17.07.2022“ (`zeitraum`), „§§ 26, 27, 28 und 72 KWahlO“, „§ 5, 12 Mitglieder“
  (Kette endet bei § 5), „Vorlage APS/130/2020“ (keine Plannummer), „Produktsachkonto 52910000“ (Konto).
- hypothesis (`tests/property/`): für jeden Text liegen alle Spannen im Text und sind sortiert; ein
  Betrag, den eine Formatfunktion deutsch schreibt (Tausenderpunkt, Komma, Mio.), wird zur selben
  Dezimalzahl; jedes gültige Datum in jeder Schreibweise ergibt dasselbe ISO-Datum; ein Text ohne
  Ziffern ergibt keine Spanne der Arten 1 bis 5.
- grep-Test „kein Stadtwort“: die Kopffeldnamen („Fachbereich“, „Amt / Institut“) stehen nur im Profil.
- Golden Master unberührt (der Schritt ist neu und schreibt eine neue Datei).

**Settings** (Anhängeregel aus `00-synergien.md`, § 2): Modell `IdentifierSettings` vor
`class Settings`, Feld `identifiers` am Ende; in `defaults.toml` ein Block `# --- Vorhaben 12:
Kennungen und Beträge` mit `enabled = false`, Einheiten, Faktoren, Rollenwörtern, Fristwörtern, der
Liste der Gesetzeskurzformen (NRW-Landesrecht, je Land überschreibbar) und Gremienwörtern; in
`profiles/duesseldorf.toml` und `profiles/moenchengladbach.toml` je ein Block `[identifiers]` mit den
Einträgen aus `PROFILMUSTER` (die Periodenprofile erben über `base`). Jeder Eintrag mit Kommentar und
Beispiel.

**Berührte Dateien**: neu `src/georep/enrich/identifiers/`, eine Zeile in
`src/georep/enrich/__init__.py`, Modell und Feld in `src/georep/settings.py`, Block am Ende von
`src/georep/defaults.toml`, `src/georep/profiles/duesseldorf.toml`, `…/moenchengladbach.toml`;
`docs/architecture.md` (Abschnitt Vorverarbeitung), `docs/decisions.md` (Eintrag ohne Nummer).

**Laufzeit**: rund 41 s für die Hauptperiode in einem Prozess bei ruhigem Rechner, 109 s unter
Fremdlast (§ 3.6), offline; `nox -s bench` bekommt eine Stufe über 200 Dokumente. **Paket**: nicht
nötig, denn der Schritt rechnet aus dem Rohtextpaket (F1) in rund einer Minute; wer Pages den Schritt
ersparen will, packt `kennungen.parquet` (1,4 MB) mit `georep pack --identifiers`.

**Validierung in Stufe 2**: die Kodierung der Stichprobe (§ 4) läuft parallel; ihre Ergebnisse
entscheiden je Art, welche `kind`s veröffentlicht werden, und ob eine zweite Runde (Tabellenbeträge,
Rolle) nötig ist.

## 7. Bauplan Stufe 3

Keine eigene Unterseite (Briefing: Download). `kennungen.csv` und `kennungen.parquet` im
Tabellenregister (`report/tables.py` über das Register), mit `schema.json`-Eintrag; nur Arten, die das
Kriterium erreicht haben, und die Rolle nur, wenn sie 0,8 erreicht. Größe gemessen (§ 3.5): CSV mit
Terminen 11,3 MB, ohne 5,7 MB, Parquet 1,4 MB beziehungsweise 0,8 MB; die CSV ist für die Seite zu
groß, also nur Parquet, oder CSV ohne Termine aus dem Kopf (`section = kopf`). Text an der Tabelle: was jede Spalte heißt, Stichprobengröße, Güte
je Art und „geprüft von zwei KI-Kodierern an *n* Treffern, nicht von Menschen“ (Plan § 2.6). Keine
Personennamen in `value` (das Dezernentenfeld wird nicht extrahiert). Zulieferer für 21, 24 und 29, die
ihre Seiten selbst bauen.

## 8. Vorab festgelegte Hypothesen

Keine; Vorhaben 12 ist Extraktion, keine Analyse.

## 9. Risiken und offene Fragen

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 1 | Rolle und Funktion als Erweiterungsspalte `attr` neben den F3-Feldern, oder als Unterart im `kind` (`betrag.kosten`)? | F3 legt das gemeinsame Schema fest; 21 und 29 lesen es | `attr` als nullbare Erweiterungsspalte, F3-Felder unverändert |
| 2 | Das Kopffeld „Dezernentin / Dezernent“ nennt Beigeordnete mit Namen (5 669 Dokumente). Extrahieren? | Plan § 1: keine Personen aus freiem Text; 24 braucht aber das Dezernat | nicht extrahieren; Dezernat über eine Tabelle Amt → Dezernat mit Gültigkeitszeitraum im Profil, Quelle der öffentliche Dezernatsverteilungsplan (Fremddaten, Frage 8 des Plans) |
| 3 | Ist „5674/26“ derselbe Plan wie „5674/026“? | Normalisierung führt 103 Pläne mit mehreren Schreibweisen zusammen | ja; in 16 gegen das Bebauungsplanverzeichnis des Portals prüfen |
| 4 | Zählen die Düsseldorfer Verfahrensnummern im Planformat (Wettbewerb, Workshop, Vorkaufsrechtssatzung, „Plan Nr.“) zur Bauleitplanung? | sie teilen das Format und oft das Gebiet mit einem Bebauungsplan | nein, nur mit Planwort; „Plan Nr.“ bleibt draußen |
| 5 | Tabellenbeträge mit Spalteneinheit in Stufe 2 aufnehmen? | bis zu 5 450 Zahlen in 546 Dokumenten; Recall-Risiko von Art 3 | erst, wenn der Recall daran scheitert; dann ein eigener Extraktor `tabelle` mit eigener Präzision |
| 6 | Welches Kriterium gilt für die Funktion `frist`? | 29 (Wiedervorlage) braucht sie; das Briefing nennt keines | ≥ 0,8 wie die Rolle; der Supervisor entscheidet vor der Kodierung |
| 7 | Termine aus Kopf und Beratungsfolge (Briefdatum, Sitzungsdaten) in der Ausgabe behalten? | sie machen 99,5 % Abdeckung, aber wenig Inhalt | behalten, mit `section = kopf`; Nutzer filtern |
| 8 | Strenge Präzision bei Rechtsgrundlagen mit Grenzen langer Ketten? | Ketten sind auch für Menschen unscharf abzugrenzen | streng gilt für das Kriterium, mild steht daneben |
| 9 | Reichen 50 Recall-Dokumente für Art 1 und 2? | wenige Kennungen je Dokument, breite Intervalle | genügt für „vorläufig“; ist das Intervall breiter als ±0,15, eine zweite Runde mit 50 Dokumenten der Planungs- und Haushaltsschicht |
| 10 | Stimmen die Offsets der Messdatei mit dem Store aus F1 überein? | die Stichprobe zeigt auf Zeichenpositionen | ja, wenn F1 dasselbe pypdf 7.1.0 ohne weitere Normalisierung nutzt; Prüfung über `pdf_sha256` und Gleichheit des Texts, sonst die Spannen über den Text neu verorten |

**Risiken**: Die Rolle erreicht 0,8 nicht (dann nur der Betrag, 21 wird gröber); die Kodier-Agenten sind
sich bei der Rolle uneins (α < 0,8: Codebuch schärfen, Plan § 2.6); ältere Vorlagen (2014–2020) haben
andere Köpfe (Amtsanteil 39 %), Mönchengladbach nur 658 Dokumente, also kaum Bebauungspläne (15
Dokumente) zum Prüfen.

## 10. Änderungen durch die Synergie (füllt der Supervisor)
