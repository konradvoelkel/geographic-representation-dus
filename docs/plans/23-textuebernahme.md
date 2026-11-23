# Vorhaben 23: Textübernahme über Perioden, Parteien und Städte

Stand 2026-11-23, Stufe 1 (Messen) mit Kodierung abgeschlossen, Branch `feat/23-textuebernahme`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „23 Textübernahme".
Messskript: [23-textuebernahme-messung.py](23-textuebernahme-messung.py). Codebuch und Stichprobe:
[`validierung/23-textuebernahme/`](../../validierung/23-textuebernahme/). Fremddaten:
`/media/konrad/xtraspace/georep/fremddaten/cherif/` (README dort).

**Urteil nach der Kodierung (2026-11-23): verwerfen** (§ 4.1, § 5). Gemeinsamen Text findet das
Verfahren sicher (alle 92 kodierten Paare über der Zufallsgrenze sind gemeinsamer Text, Recall der
Kandidatensuche 91,3 %), aber die **Art** trägt nicht: das Kriterium (Präzision ≥ 0,9 je politischer
Art) verfehlen die **Musteranträge knapp mit 0,889** (26 von 30 kodierten Paaren richtig, gewichtet;
Intervall 0,633 bis 0,972) und die **Übernahmen über Fraktionsgrenzen deutlich mit 0,296** (9 von
30). Familien über Partei- und Stadtgrenzen gibt es (9 bestätigte Paare über Fraktionsgrenzen, 3
über Stadtgrenzen), aber nach der vorab festgelegten Regel entscheidet die Präzision der
Musteranträge.

Nach der Regel des Verfahrens sind von 115 299 Dokumentpaaren mit gemeinsamer Stelle (mindestens 30
Wörter) nur 913 politische Übernahmen: 837 Musteranträge (gleicher Text derselben Partei in einem
anderen Gremium, 423, oder einer anderen Periode, 411; über Stadtgrenzen 3) und 76 Übernahmen über
Fraktionsgrenzen. Der Rest sind Bausteine und Formulare (68 125), eigene Wiederholungen (24 398),
Rechtszitate (14 352), Zitate im selben Verfahren (4 193) und andere Quellen (2 494). Zwischen
Düsseldorf und Mönchengladbach, Leipzig, Osnabrück, Dresden und Freiburg liegen 573 Paare, davon 424
Rechtszitate, 133 andere Quellen und 6 politische, von denen die Kodierung 3 bestätigt (ein
CDU-Antrag zur Ehrung von Knochenmarkspendern in Düsseldorf und Osnabrück, die
Nachtbürgermeister-Idee, eine TTIP-Resolution).

Alle Zahlen sind am 2026-11-23 im Worktree `feat/23-textuebernahme` gemessen, unter Fremdlast
(Lastmittel 10 bis 19 statt höchstens 13; Laufzeiten darum mit `uptime`), mit
`POLARS_MAX_THREADS=4`, `OMP_NUM_THREADS=2`, `nice -n 10`. Nachrechnen:

```bash
uv run georep bootstrap && uv run georep run                    # Hauptperiode zuerst
for p in duesseldorf-2014 duesseldorf-2025 moenchengladbach; do
  uv run georep --profile $p bootstrap && uv run georep --profile $p run
done
uv run python -I docs/plans/23-textuebernahme-messung.py --neu   # alle Zahlen, rund 19 Minuten
uv run python -I docs/plans/23-textuebernahme-messung.py         # aus der Zwischenablage, rund 3 Minuten
uv run python -I docs/plans/23-textuebernahme-messung.py --schreiben   # § 4: Stichprobe und Kodieraufgaben neu
uv run python -I docs/plans/23-textuebernahme-messung.py --labels      # § 4.1: Labels und Auswertung, Sekunden
```

Das Skript braucht das Cherif-Korpus unter `--cherif` (Vorgabe: der Pfad oben) und legt eine
Zwischenablage von 1,5 GB unter `messdaten/23-textuebernahme/cache/` an; ohne `--schreiben` prüft es,
ob die Stichprobe im Repo gleich der berechneten ist.

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

**Frage.** Wo steht in Düsseldorfer Ratsdokumenten Text, der auch anderswo steht — bei derselben
Partei in einer anderen Stadt, Periode oder einem anderen Gremium (Musterantrag), bei einer anderen
Fraktion (Übernahme über Fraktionsgrenzen), oder als Baustein, Gesetzeszitat oder Zitat im selben
Verfahren, die keine politische Übernahme sind und erkannt und ausgeschlossen werden müssen?

**Literatur.** Wilkerson, Smith und Stramp (2015, *American Journal of Political Science* 59 (4),
S. 943–956, DOI 10.1111/ajps.12175; gelesen in der Fassung auf der Seite von David A. Smith,
ccs.neu.edu) verfolgen Politikideen durch die Gesetzentwürfe des 111. US-Kongresses: Einheit ist der
Abschnitt eines Entwurfs (119 704 Abschnitte), Kandidaten aus einem Vorfilter über gehashte
Wortfolgen (Huston, Moffat und Croft 2011; 7,2 Milliarden Paare auf rund 1,6 Millionen), dann
Smith-Waterman auf Wörtern, ausgehend von einer gemeinsamen Folge von zehn Wörtern. Drei Kodierer
haben 3 400 Ausrichtungen in sechs Klassen eingeteilt; **die größte Klasse war Boilerplate**, geteilte
Politikideen machten rund 16 % aus. Nach einem Klassifikator gegen Boilerplate und einer Schwelle auf
dem Ausrichtungswert erreichen sie für geteilte Politikideen eine **Präzision von 65 %** (95 %:
55,1–74,3) bei einem Recall von 97,3 %. Das Kriterium dieses Vorhabens (Präzision ≥ 0,9) liegt also
deutlich über dem, was die Vorlage erreicht hat; und wie dort entscheidet die Behandlung der Bausteine
über die Präzision. Das Verfahren der Kandidatensuche (Jaccard über Shingles, MinHash, LSH) geht auf
Broder (1997)\* und Leskovec, Rajaraman und Ullman, *Mining of Massive Datasets*, Kap. 3\* zurück;
der Prototyp stammt aus Vorhaben 13 ([13-dubletten.md](13-dubletten.md), § 3.3 und § 6). Die
Seltenheitsgrenze für Shingles (häufige Wortfolgen zählen nicht als Beleg) ist das Vorgehen des
Werkzeugs *passim* von David A. Smith\*. Mit \* markiert: aus dem Gedächtnis, vor einem Zitat auf der
Seite nachzuschlagen (`report/literatur.toml`).

**Ratsarbeit.** Drei Fragen einer Fraktionsgeschäftsstelle: „Hat eine andere Fraktion das schon
beantragt, mit welchen Worten?", „Haben wir das in der letzten Periode schon einmal eingebracht?" und
„Ist dieser Antrag ein Musterantrag, und wo lief er noch?". Die ersten beiden beantwortet die Messung
für Düsseldorf; die dritte nur, soweit das Cherif-Korpus und Mönchengladbach reichen (§ 2). Für alle
Fraktionen gleich gebaut: jede Partei kann übernehmen und übernommen werden.

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

Gerechnet auf den Läufen vom 2026-11-23 (`georep bootstrap && georep run` für `duesseldorf`,
`duesseldorf-2014`, `duesseldorf-2025` und `moenchengladbach` im Worktree, 19:59 bis 20:01 Uhr; die
Periode 2014–2020 braucht die Hauptperiode zuerst, ein zweiter `run` lief durch). Pfade aus
`georep --profile <p> paths`, nur lesend:

- `interim/papers.parquet`: `id`, `name` (Titel), `reference`, `date`, `paper_type`, `file_name`,
  `text` (Hauptdatei, kleingeschrieben, ohne Zeilenumbrüche, pypdf 7.1.0);
- `processed/papers_gremien.parquet`: `id`, `gremium`;
- `processed/dokumente_urheber.parquet`: `id`, `urheber_art`, `parteien`, `quelle`;
- die Antragsteller aus dem Regelwerk von Vorhaben 15 (`antragsteller()` in
  `15-funktion-messung.py`, Präzision 119/119, Recall 0,86 an dessen Labels): Dokumentart, Autorenteil
  des Titels, Briefkopf der Periode 2014–2020; für Einzelmandate die Partei aus `parteien`; wo beides
  fehlt, die Parteimuster des Profils in den ersten 600 Zeichen;
- `messdaten/rohtext/<ordner>.parquet` (Phase 0): nur für den Kopf der Kodieraufgaben (Groß- und
  Kleinschreibung).

**Fremddaten: das Ratsvorlagen-Korpus von Khaled Cherif** (Zenodo, DOI 10.5281/zenodo.21767760,
veröffentlicht 2026-08-03, CC BY 4.0 für die Sammlung; Leipzig und Osnabrück CC BY 4.0, Dresden
DL-DE/Zero 2.0, Freiburg DL-DE/BY 2.0). Am 2026-11-23 um 19:59 Uhr direkt von Zenodo geladen nach
`/media/konrad/xtraspace/georep/fremddaten/cherif/`: zehn Dateien, **152 MB** komprimiert (vor dem
Laden aus der API geprüft, weit unter der Grenze von 10 GB), die vier JSONL-Dateien entpackt
939 MB; `sha256sum -c SHA256SUMS.txt` ohne Fehler; README daneben mit URL, DOI, Abrufdatum, Größe,
SHA-256 je Datei und der Lizenz im Wortlaut. Gelesen nur mit `python -I` aus dem Messskript (das
woanders liegt), über `compression.zstd` der Standardbibliothek; nichts wird ausgeführt. Felder:
`city_slug`, `oparl_id`, `name`, `reference`, `date`, `paper_type`, `text`, bei Dresden und Freiburg
`rolle` (Hauptdatei oder Anlage) und `datei_name`. Die Urheberklasse kommt aus der Dokumentart
(`CHERIF_POLITIK`, `CHERIF_EINGABE` im Skript; Freiburg hat nur Vorlagen der Verwaltung), die Partei
aus dem Kopf: in Leipzig der Block „Eingereicht von … Betreff", in Osnabrück die Zeile vor „Antrag
Vorlage-Nr", in Dresden die Dokumentart („Antrag SPD"); Ortschaftsräte bleiben ohne Partei.

| Korpus | Dokumente | mit Text | Wörter (bis 3 000 je Dokument) | politisch | davon mit Partei | Verwaltung | unbekannt | Eingabe |
|---|---|---|---|---|---|---|---|---|
| Düsseldorf 2014–2020 | 22 215 | 21 724 | 7 806 457 | 9 264 | 8 683 | 10 575 | 2 356 | 20 |
| Düsseldorf 2020–2025 | 19 108 | 19 033 | 6 312 337 | 8 724 | 8 220 | 9 933 | 327 | 124 |
| Düsseldorf ab 2025 | 4 095 | 4 075 | 1 238 988 | 1 924 | 1 705 | 2 024 | 84 | 63 |
| Mönchengladbach | 2 895 | 650 | 376 963 | 617 | 240 | 2 278 | 0 | 0 |
| Leipzig (Cherif) | 26 685 | 26 685 | 23 893 759 | 9 583 | 6 076 | 14 476 | 0 | 2 626 |
| Osnabrück (Cherif) | 10 334 | 10 334 | 11 023 640 | 2 966 | 2 593 | 7 368 | 0 | 0 |
| Dresden (Cherif) | 4 064 | 4 064 | 1 165 313 | 127 | 32 | 3 609 | 0 | 328 |
| Freiburg (Cherif) | 2 044 | 2 043 | 3 235 049 | 0 | 0 | 2 044 | 0 | 0 |

Zusammen 91 440 Dokumente, 55 052 506 Wörter, Vokabular 763 860, 54 698 130 Shingles.

**Grenzen der Daten**, die das Urteil berühren:

- Mönchengladbach hat Text nur für 650 von 2 895 Dokumenten, die politischen Dokumente fast nur als
  „Fraktionsantrag" ohne Partei in den Metadaten (240 von 617 mit Partei aus dem Text).
- Das Cherif-Korpus liegt **außerhalb von NRW** (Sachsen, Niedersachsen, Baden-Württemberg): andere
  Gemeindeordnungen, andere Landesvorgaben, andere kommunalpolitische Vereinigungen. Musteranträge
  einer NRW-Vereinigung können dort nicht auftauchen, die einer Bundespartei schon. Leipzig fehlen
  zudem in den Jahrgängen 2016 bis 2020 viele Dokumente (README des Korpus: Erfolgsquote 85,7 %, 2017
  nur 31 %); Dresden ist zu 41,9 % vollständig.
- Für alle Korpora gilt die Hauptdatei (Anlagen nur bei Dresden und Freiburg als eigene Dokumente);
  ein Musterantrag als Anlage einer Vorlage bleibt unsichtbar.
- Keine Texte und keine Ausschnitte gehen ins Repo; die Kodieraufgaben liegen lokal (Plan § 4).

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

### 3.1 Vorgehen

1. **Tokens.** Je Dokument die ersten CAP = 3 000 Wörter (`\w+`, kleingeschrieben) mit ihren
   Zeichenpositionen. Die Kappung trifft höchstens 1 % der Düsseldorfer Dokumente (99. Perzentil
   1 858 bis 3 085 Wörter je Periode) und vor allem lange Vorlagen und Anlagen der Fremdstädte (von 119,4 auf 39,3
   Millionen Wörter); Anträge und Anfragen sind kürzer.
2. **Shingles** aus K = 5 Wörtern, gehasht wie im Prototyp von 13 (BLAKE2b je Wort, splitmix64,
   obere 32 Bit): unabhängig von `PYTHONHASHSEED` und von der Korpusreihenfolge.
3. **Seltenheit.** Je Shingle die Zahl der Dokumente aller Korpora, in denen es steht. Ein Shingle
   in mehr als DF_MAX = 30 Dokumenten ist **Baustein** und zählt im MinHash nicht (wie die
   Höchstgrenze der Dokumenthäufigkeit in *passim*). Ohne diese Grenze fand der erste Lauf (noch mit 32 × 4 Bändern) 370 907
   Kandidatenpaare, 257 169 davon innerhalb der Periode 2014–2020 — Briefköpfe, Beratungsfolgen und
   Formulare, die in 30 und weniger Dokumenten je Eimer auftreten; mit ihr und denselben Bändern
   40 511.
4. **Fenster** statt ganzer Dokumente, weil Übernahme oft nur einen Absatz betrifft: Blöcke zu 25
   Shingles, ein Fenster sind zwei benachbarte Blöcke (50 Shingles, 54 Wörter), jedes Fenster um einen
   Block versetzt. Ein Fenster mit weniger als MIN_RARE = 15 seltenen Shingles sucht keine Partner.
   Die Signatur eines Fensters ist das Minimum der Signaturen seiner beiden Blöcke (MinHash der
   Vereinigung), so wird jeder Shingle je Permutation nur einmal gehasht.
5. **MinHash und LSH**: 128 Permutationen `(a·x + b) mod p`, Seed 23, **64 Bänder zu 2 Zeilen**
   (Schwelle (1/64)^(1/2) ≈ 0,125; ein Fensterpaar mit Jaccard 0,2 wird mit Wahrscheinlichkeit
   1 − (1 − 0,2²)⁶⁴ ≈ 0,93 Kandidat, mit 0,3 zu 0,998). Die Bänder von 13 (32 × 4, Schwelle 0,42)
   reichten für ganze Dokumente, für Fenster nicht: mit ihnen fand die Suche nur 441 von 993 (44 %)
   der Übernahmen außerhalb von Bausteinen, die die Gegenprobe (§ 3.4) kennt. Ein Eimer mit mehr als MAXDOC = 30 Dokumenten gibt keine
   Paare. Paare entstehen nur, wenn mindestens ein Fenster aus Düsseldorf stammt; Paare innerhalb
   einer Fremdstadt und zwischen Fremdstädten zählen nicht.
6. **Vorfilter**: ein Dokumentpaar geht nur in die Ausrichtung, wenn beide mindestens MIN_SHARED = 5
   verschiedene seltene Shingles teilen (exakt gezählt). Das ist dieselbe Bedingung, die die
   Gegenprobe an ihre Referenz stellt; sie senkt die Zahl der Ausrichtungen von 326 478 auf
   196 084.
7. **Ausrichtung** je Dokumentpaar: Smith-Waterman auf Wörtern (Treffer +1, Fehler −1, Lücke −1,
   linear) über den Bereich der Kandidatenfenster beider Seiten plus 40 Wörter Rand, höchstens 1 500
   Wörter je Seite (bei weiter verstreuten Fenstern die Diagonale mit den meisten Fensterpaaren). Die
   Zeile wird vektorisiert gerechnet, die waagrechten Lücken mit einem laufenden Maximum (exakt für
   lineare Kosten). Ergebnis je Paar: Wert, Spanne in beiden Dokumenten, Treffer und Spalten
   (Identität = Treffer / Spalten), Anteil an beiden Dokumenten.
8. **Zufallsgrenze** aus einer Nullverteilung: 2 000 zufällige Paare (ein Düsseldorfer Dokument,
   ein beliebiges anderes, beide mit mindestens 300 Wörtern, kein Kandidatenpaar), je ein zufälliger
   Ausschnitt von 300 Wörtern, Seed 24 (§ 3.3).
9. **Art** nach einer Regel über Merkmale des Paars (§ 3.5), dann **Familien** als
   Zusammenhangskomponenten über die beiden politischen Arten.

### 3.2 Kandidaten

| | Wert |
|---|---|
| Shingles zusammen / davon selten (in höchstens 30 Dokumenten) | 54 698 130 / 47 593 325 = 87,0 % |
| Fenster / mit mindestens 15 seltenen Shingles | 2 140 212 / 2 014 068 = 94,1 % |
| Fensterpaare aus LSH (64 × 2) / Dokumentpaare | 1 553 113 / 326 478 |
| nach dem Vorfilter (≥ 5 gemeinsame seltene Shingles): Fensterpaare / Dokumentpaare | 1 306 476 / **196 084** |

Ohne die Seltenheitsgrenze (erster Lauf, noch mit 32 × 4) waren es 370 907 Dokumentpaare, 257 169
davon innerhalb der Periode 2014–2020 (Briefkopf und Beratungsfolge des alten Vorlagenformats); mit
ihr 40 511. Die 196 084 Dokumentpaare nach Korpora:

| | 2014–2020 | 2020–2025 | ab 2025 | Mönchengladbach | Leipzig | Osnabrück | Dresden | Freiburg |
|---|---|---|---|---|---|---|---|---|
| Düsseldorf 2014–2020 | 85 939 | 23 963 | 2 972 | 111 | 641 | 665 | 3 | 92 |
| Düsseldorf 2020–2025 | | 59 896 | 11 120 | 168 | 639 | 432 | 8 | 88 |
| Düsseldorf ab 2025 | | | 8 854 | 28 | 270 | 155 | 1 | 39 |

### 3.3 Ausrichtung und Zufallsgrenze

**Nullverteilung** (2 000 Zufallspaare, je 300 Wörter, Seed 24): Median 2, 90 % 3, 99 % 6, 99,5 % 7,
99,9 % 22, Maximum 33. Nur drei Paare erreichen 20 und mehr, **alle drei sind Bausteine**, die die
Seltenheitsgrenze aus der Kandidatensuche nimmt, die Ausrichtung aber sieht: eine Sachdarstellung
zum Bauunterhalt an Schulen (33), zweimal die Fußnoten der alten Beratungsfolge („die Sitzung wurde
zum Zeitpunkt der Drucklegung dieser Vorlage noch nicht geplant", 29 und 22). Ohne Bausteine liegt
das Maximum bei 15 (eine Wendung aus § 34 BauGB). **Zufallsgrenze S\* = 20**, dazu mindestens 30
Wörter auf beiden Seiten: kein zufälliges Paar überschreitet beides, das nicht ohnehin ein Baustein
ist. Die Grenze trennt also gemeinsamen Text von Zufall, nicht Übernahme von Baustein; das tut die
Regel in § 3.5.

Über der Grenze liegen **115 299 der 196 084 Paare (58,8 %)**. Je Paar (10 %, 50 %, 90 %): Wert 26,
41, 105; Länge der kürzeren Seite 34, 59, 151 Wörter; Identität (Treffer je Spalte) 0,72 im unteren
Zehntel, Median 0,86.

### 3.4 Gegenprobe: was die Kandidatensuche verliert

Gegen eine **erschöpfende Suche**: ein invertierter Index aller seltenen Shingles, für jedes
Dokument der Auswahl jeder Partner mit mindestens fünf gemeinsamen seltenen Shingles, ausgerichtet
über den Bereich dieser Shingles, Art nach derselben Regel. Der Recall der Kandidatensuche ist der
Anteil dieser Paare über der Grenze, die auch die Kandidatensuche findet.

| Auswahl | Paare über der Grenze | ohne Bausteine | davon gefunden | politische Arten |
|---|---|---|---|---|
| 400 zufällige Düsseldorfer Dokumente (Seed 25), Partner überall | 2 523 | 943 | **861 = 91,3 %** | 17 / 17 |
| alle 19 912 politischen Düsseldorfer Dokumente, Partner in anderen Städten | 57 | 54 | **53 = 98,1 %** | 6 / 6 |

Ohne Bausteine je Länge der kürzeren Seite (erste Auswahl): 30–49 Wörter 0,892, 50–99 Wörter 0,878,
100–199 Wörter 0,969, ab 200 Wörtern 1,000. Bausteine findet die Suche zu 73,7 % (1 165 von 1 580) —
gewollt, die Seltenheitsgrenze nimmt sie heraus. Mit den Bändern von 13 (32 × 4) waren es ohne
Bausteine nur 441 von 993 (44,4 %, Regel der ersten Fassung), darum 64 × 2; Fenster aus 15 statt 25
Shingles brachten mit 32 × 4 nur 57 % und mit 64 × 2 nichts über 64 × 2 mit 25 hinaus (91,1 %). Die
politischen Paare über Stadtgrenzen sind damit vollständig: die erschöpfende Suche über alle
politischen Düsseldorfer Dokumente findet keines, das die Kandidatensuche nicht auch hat.

### 3.5 Was übernommen wird: die Art

**Regel** (erster Durchgang `classify`, in dieser Reihenfolge; der Vorrang folgt dem Codebuch):

1. **Verweis**: gleiche Stadt und dieselbe Grundnummer (`X` und `X/1`, `-ÄA-002`, `-NF-01`) oder die
   Nummer des einen steht in Titel oder Text des anderen → `verfahrenszitat`.
2. Mindestens drei Rechtsmarken (§, Abs., Gesetz, Verordnung, Richtlinie, GO NRW, BauGB, SGB …) je
   100 Wörter der Stelle → `rechtszitat`.
3. Die Stelle ist häufig (Median der Dokumenthäufigkeit ihrer Shingles ≥ 30) oder hat nach Abzug der
   **Floskeln** (Briefkopf, Anrede, Bitte um Tagesordnung, Gruß, Unterschrift, Beratungsfolge;
   `FLOSKEL` im Skript) weniger als 30 Wörter → `baustein`.
4. Beide politisch, Parteien bekannt und mit gemeinsamer Partei → `musterantrag`, wenn Stadt, Periode
   oder Gremium verschieden sind, sonst `eigene_wiederholung`.
5. Beide politisch, Parteien bekannt und verschieden → `fraktionsuebergreifend`.
6. Übrige Paare über Stadtgrenzen → `rechtszitat` mit einer Rechtsmarke in der Stelle oder den 20
   Wörtern davor, sonst `andere_quelle`.
7. Beide Verwaltung → `eigene_wiederholung` bei Titelnähe ≥ 0,3, sonst `baustein`.
8. Beide politisch oder unbekannt, eine Partei fehlt → `politisch_ohne_partei` (kein Code des
   Codebuchs, zählt nicht politisch).
9. Rest (Politik und Verwaltung, Eingaben) → `andere_quelle`.

**Zweiter Durchgang** (`refine`, nur für die drei politischen Arten), entstanden aus der Sichtung
unten: (a) zielen beide auf dieselbe dritte Drucksache (Nummer in Titel oder Textanfang) →
`verfahrenszitat`; (b) über Fraktionsgrenzen ist eines ein Änderungs-, Ergänzungs- oder
Begleitantrag und beide liegen höchstens 90 Tage auseinander → `verfahrenszitat`; (c) mehr als zwei
Dokumente tragen die Hälfte der Shingles der Stelle („Träger") und ihre Titel haben mit dem ersten im
Mittel eine Nähe unter 0,2 → `baustein`; (d) die Stelle beginnt in beiden Dokumenten in den ersten 40
Wörtern und die Titel sind verschieden (Nähe < 0,5) → `baustein` (Briefkopf). Der zweite Durchgang
nimmt aus den Übernahmen über Fraktionsgrenzen 253 → 76, aus den Musteranträgen 1 456 → 837, aus
`politisch_ohne_partei` 3 033 → 824.

**Sichtung durch den Mess-Agenten** (keine Validierung, nur Entwicklung der Regel, vor dem Ziehen der
Stichprobe; die gesichteten Paare können in der Stichprobe wieder vorkommen):

- Erste Fassung, 25 Übernahmen über Fraktionsgrenzen: 6 bis 7 echte Übernahmen; der Rest
  Briefköpfe und Formulare der Bezirksvertretungen der Periode 2014–2020 (rund 9), Zitate im selben
  Verfahren ohne gegenseitige Nummer (Änderungsanträge zweier Fraktionen zur selben Vorlage, rund 5),
  gemeinsame dritte Quellen (rund 3). Daraus (a) und (c).
- Nach (a) und (c), 20 Musteranträge: 18 plausibel (Haushaltsanträge der Ratsgruppe Tierschutz/Freie
  Wähler, die nach der Wahl wortgleich wiederkommen; Anfragen der Linken, die jedes Jahr dieselben
  Fragen stellen; Begründungen der Grünen zu sicheren Schulwegen in mehreren Bezirksvertretungen),
  2 Briefköpfe. 20 Übernahmen über Fraktionsgrenzen: rund 7 echte; daraus (b) und (d).
- Endgültige Regel, 16 Übernahmen über Fraktionsgrenzen: **9 klar** (die CDU übernimmt den Antrag
  der SPD zur Platzgestaltung in Lohausen, CDU und FDP die Sachdarstellung der Grünen zu den
  Ackerflächen am Schlosspark Kalkum, die Grünen die Begründung der SPD zum Stadtbaumkonzept in
  einer anderen Bezirksvertretung …), **3 unklar**, **4 falsch** (drei Zitate aus Satzungen und
  Gesetzen ohne Rechtsmarke, ein gemeinsamer Pressetext des Bundes).

**Ergebnis der Regel** (Paare über der Grenze, Grenze = was die beiden Dokumente trennt):

| Art | keine | Gremium | Periode | Stadt | zusammen |
|---|---|---|---|---|---|
| `musterantrag` | – | 423 | 411 | 3 | **837** |
| `fraktionsuebergreifend` | 32 | 24 | 17 | 3 | **76** |
| `eigene_wiederholung` | 14 919 | 3 339 | 6 140 | 0 | 24 398 |
| `verfahrenszitat` | 3 072 | 570 | 551 | 0 | 4 193 |
| `baustein` | 47 058 | 11 905 | 9 152 | 10 | 68 125 |
| `rechtszitat` | 7 244 | 1 762 | 4 922 | 424 | 14 352 |
| `andere_quelle` | 1 471 | 530 | 360 | 133 | 2 494 |
| `politisch_ohne_partei` | 551 | 181 | 92 | 0 | 824 |
| **zusammen** | 74 347 | 18 734 | 21 645 | 573 | **115 299** |

Über Stadtgrenzen je Städtepaar (Düsseldorfer Periode – Stadt): Rechtszitate vor allem mit Osnabrück
(107 + 98 + 2) und Leipzig (42 + 57 + 18), dann Mönchengladbach (45 + 48 + 1; Anerkennung freier
Träger nach § 75 SGB VIII, verkaufsoffene Sonntage, Tempo 30 vor sozialen Einrichtungen nach § 45
StVO, Erhaltungssatzungen nach § 172 BauGB, der Freistellungsbeschluss der EU zu Beihilfen); andere
Quellen vor allem mit Leipzig (30 + 54 + 3). Dresden steuert nichts bei (3 + 8 + 1 Kandidaten, keiner
über der Grenze), Freiburg 11 Paare.

**Die sechs politischen Paare über Stadtgrenzen**, alle echter gemeinsamer Text, aber nur zwei sind
Musteranträge im Sinn des Briefings:

| Düsseldorf | anderswo | Stelle | Art nach Regel | Einschätzung (Sichtung) |
|---|---|---|---|---|
| CDU, AGS 2015 „Ehrung Spender" | CDU Osnabrück 2015 | Begründung zur Ehrung von Blut- und Knochenmarkspendern | Musterantrag | Musterantrag derselben Partei |
| SPD/Volt, Rat 2021 „Nachtbürgermeister*in" | CDU, SPD, Grüne Osnabrück 2020 | Aufgabenbeschreibung | Musterantrag | Musterantrag oder gemeinsame Vorlage |
| CDU/Grüne, Rat 2021 | Grüne, SPD, Volt Osnabrück 2022 | Forderung der Städteinitiative Tempo 30 | Musterantrag | andere Quelle (Text der Initiative) |
| Grüne, ÄA Rat 2014 „TTIP verhindern" | Linke Leipzig 2014 | Resolutionstext | über Fraktionsgrenzen | andere Quelle (Kampagnentext) |
| SPD, OVA 2025 Gehwegparken | Grüne Leipzig 2023 | Verwaltungsvorschrift zur StVO | über Fraktionsgrenzen | Rechtszitat |
| Tierschutz/FW, Rat 2022 Wohngeld | Linke Leipzig 2022 | Zahlen zur Wohngeldreform | über Fraktionsgrenzen | andere Quelle (Bund) |

**Parteien.** Musteranträge (gemeinsame Partei): Die Linke 255, CDU 158, Grüne 109, Tierschutz/Freie
Wähler 107, SPD 72, FDP 32, CDU+Grüne 26, die Ampel der Periode 2014–2020 23. Über Fraktionsgrenzen
(frühere / spätere Seite) streuen die 76 Paare über alle Paarungen, keine mit mehr als fünf.

### 3.6 Länge und Anteil des übernommenen Texts

| Art | Paare | Wörter, Median | Wörter, 90 % | Anteil am späteren Dokument, Median | später zur Hälfte oder mehr übernommen | Identität, Median |
|---|---|---|---|---|---|---|
| `musterantrag` | 837 | 83 | 261 | 0,42 | 42,4 % | 0,86 |
| `fraktionsuebergreifend` | 76 | 49 | 102 | 0,20 | 10,5 % | 0,86 |
| `eigene_wiederholung` | 24 398 | 79 | 244 | 0,32 | 34,9 % | 0,82 |
| `verfahrenszitat` | 4 193 | 59 | 254 | 0,17 | 12,8 % | 0,92 |
| `baustein` | 68 125 | 50 | 112 | 0,19 | 13,1 % | 0,87 |
| `rechtszitat` | 14 352 | 66 | 156 | 0,24 | 21,7 % | 0,82 |
| `andere_quelle` | 2 494 | 47 | 120 | 0,17 | 5,5 % | 0,92 |

Ein Musterantrag übernimmt im Median 83 Wörter und gut zwei Fünftel des späteren Dokuments; eine
Übernahme über Fraktionsgrenzen ist kürzer (49 Wörter, ein Fünftel): eine Begründung oder eine
Forderung, nicht ein ganzer Antrag.

### 3.7 Familien

Zusammenhangskomponenten über die 913 politischen Paare: **433 Familien mit 1 158 Dokumenten**, 290
davon Paare, die größte 18 Dokumente (Ampel 2014–2020 und ihre Nachfolger über sechs Gremien und
zwei Perioden). **Über Parteigrenzen** (mit mindestens einer Kante `fraktionsuebergreifend`) **57**,
**über Stadtgrenzen 6**, über Periodengrenzen 191, über Gremiengrenzen 266. Fast jede Familie über
Stadtgrenzen ist ein einzelnes Paar.

### 3.8 Laufzeiten

Ganzer Lauf ohne Zwischenablage (`--neu`, 20:51 bis 21:10 Uhr, Lastmittel 13,4 zu Beginn, 10,2 am Ende): 18:51 min,
höchster Speicher 5,6 GB; davon Laden 24 s, Tokens, Shingles und Dokumenthäufigkeit 122 s, Fenster,
LSH und Vorfilter 379 s, Ausrichtung von 196 084 Paaren 471 s (2,4 ms je Paar). Aus der
Zwischenablage mit Gegenprobe und Stichprobe 2:50 min (21:17 bis 21:20 Uhr, Lastmittel 15,1 und 11,6).

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

**Einheit**: ein Textpaar mit der ausgerichteten Stelle. **Codebuch**:
[`validierung/23-textuebernahme/codebuch.toml`](../../validierung/23-textuebernahme/codebuch.toml),
zwei Fragen mit **festem Antwortformat**, eine JSON-Zeile je Paar:

```json
{"paar": "p001", "uebernahme": "ja", "art": "musterantrag", "begruendung": "<ein Satz>"}
```

- `uebernahme` ∈ {`ja`, `nein`}: dieselbe Stelle aus gemeinsamer Herkunft, oder Zufall;
- `art` ∈ {`musterantrag`, `fraktionsuebergreifend`, `eigene_wiederholung`, `verfahrenszitat`,
  `baustein`, `rechtszitat`, `andere_quelle`, `zufall`}, genau eine; `zufall` genau dann, wenn
  `uebernahme` = `nein`. Vorrang bei mehreren passenden Arten: `verfahrenszitat`, `rechtszitat`,
  `baustein`, `andere_quelle`, dann die politischen und die eigene Wiederholung. Jede Option hat im
  Codebuch eine Definition und ein Beispiel aus den Daten.

Zwei Arten kommen zu den fünf des Briefings (Musterantrag, Übernahme über Fraktionsgrenzen,
Verwaltungsbaustein, Rechtszitat, Zufall) hinzu, weil die Messung sie in großer Zahl zeigt und sie
sonst in einer politischen Art landeten: `verfahrenszitat` (ein Änderungsantrag zitiert den Antrag,
den er ändert — eine andere Fraktion, aber keine Übernahme) und `eigene_wiederholung` (dieselben
Urheber im selben Gremium und derselben Periode). `andere_quelle` fängt echte Übernahmen auf, die in
keine Art passen (Pressemitteilung, Verband, Bundesprogramm). „Verwaltungsbaustein" heißt hier
`baustein`, weil Fraktionen ebenso Formulare haben (Briefkopf, Bitte um Tagesordnung, Unterschriften)
und sie genauso ausgeschlossen werden müssen.

**Stichprobe** ([`stichprobe.csv`](../../validierung/23-textuebernahme/stichprobe.csv): IDs, Schicht,
Größe der Schicht, Wert und Länge; kein Text, keine Partei): 100 Paare, Seed 23, geschichtet nach der
Art des Verfahrens, dicht bei den beiden politischen Arten, an denen das Kriterium hängt. In den
politischen Schichten gehen zuerst alle Paare über Stadtgrenzen hinein (es sind wenige), der Rest
proportional nach Grenze (Gremium, Periode, keine). Die Reihenfolge ist gemischt; die Aufgaben tragen
weder Art noch Schicht, Partei, Wert oder Grenze des Verfahrens.

| Schicht (Art des Verfahrens, Grenze) | Grundgesamtheit | gezogen |
|---|---|---|
| `musterantrag`, Gremium | 423 | 14 |
| `musterantrag`, Periode | 411 | 13 |
| `musterantrag`, Stadt | 3 | 3 (alle) |
| `fraktionsuebergreifend`, keine | 32 | 12 |
| `fraktionsuebergreifend`, Gremium | 24 | 9 |
| `fraktionsuebergreifend`, Periode | 17 | 6 |
| `fraktionsuebergreifend`, Stadt | 3 | 3 (alle) |
| `eigene_wiederholung` | 24 398 | 6 |
| `verfahrenszitat` | 4 193 | 6 |
| `baustein` | 68 125 | 6 |
| `rechtszitat` | 14 352 | 6 |
| `andere_quelle` | 2 494 | 4 |
| `politisch_ohne_partei` | 824 | 4 |
| `unter_schwelle` (Wert 10 bis 19 oder kürzer als 30 Wörter) | 72 998 | 8 |
| **zusammen** | | **100**, davon 60 politische |

**Kodieraufgaben**: `/media/konrad/xtraspace/georep/messdaten/kodierung/23-textuebernahme/aufgaben.jsonl`
(lokal, nie im Repo), eine Zeile je Paar mit `paar`, den Fragen und Optionen, dem Pfad des Codebuchs
und je Seite `id`, `stadt`, `periode`, `drucksache`, `titel`, `datum`, `art` (Dokumentart),
`gremium`, `kopf` (die ersten 600 Zeichen, für Düsseldorf und Mönchengladbach aus dem Rohtext der
Messdaten mit Groß- und Kleinschreibung, `kopf_quelle` sagt welcher), `stelle` (die ausgerichtete
Stelle in ⟦…⟧ mit 40 Wörtern Kontext davor und danach, höchstens 2 500 Zeichen) und die Längen. Die
Partei steht nicht drin: die Kodierer lesen sie selbst aus Kopf und Titel, das prüft zugleich die
Zuordnung der Antragsteller.

**Maße, vorab festgelegt** (der Supervisor rechnet sie nach der Kodierung; Krippendorffs α zwischen
den beiden Kodierern über `art`, nominal; Stufe 3 verlangt α ≥ 0,8):

- **P1 je Art, das Kriterium** (§ 5): Anteil der Paare, die das Verfahren als `musterantrag`
  beziehungsweise als `fraktionsuebergreifend` meldet, deren Endlabel **genau diese Art** ist;
  gewichtet über die Schichten der Art (Gewicht Grundgesamtheit / gezogen), mit Wilson-Intervall.
  Streng, weil die Seite genau diese Paare unter genau diesem Namen zeigen würde.
- **P1 zusammen** und **P1 weit** (Nebenmaße): über beide Arten gewichtet; „weit" zählt jede der
  beiden politischen Arten als richtig.
- **P0** (Nebenmaß): Anteil aller Paare über der Zufallsgrenze mit `uebernahme` = `ja`, gewichtet
  über alle Schichten außer `unter_schwelle`.
- **Ausschluss**: je ausgeschlossener Art (`baustein`, `rechtszitat`, `verfahrenszitat`) der Anteil,
  den die Kodierung bestätigt; und wie viele Paare dieser Schichten die Kodierung politisch nennt
  (die Übernahmen, die die Regel verliert).
- **Schwelle**: in der Schicht `unter_schwelle` der Anteil `uebernahme` = `ja`; liegt er über 0,5,
  ist die Grenze S* zu hoch.

Rechenbeispiel (Skript): 60 politische Paare, davon 57 richtig (95 %), gäben ein Wilson-Intervall von
[0,863; 0,983]; 54 richtig (90 %) gäben [0,799; 0,953]. Je Art sind es 30 Paare: 28 von 30 (93 %)
gäben [0,787; 0,982]. Die Stichprobe zeigt ein deutliches Verfehlen
sicher, ein knappes Erreichen nur mit Unsicherheit — wie bei 13.

**Was sich ohne Kodierung sagen lässt.** Die Zufallsgrenze ist gemessen (§ 3.3); dass ein Paar über ihr
**gemeinsamen Text** hat, ist damit fast sicher. Unsicher ist allein die **Art**: ob eine Stelle
zwischen zwei Fraktionen eine Übernahme ist oder ein Formular, ein Zitat im Verfahren, das die
Verweisregel nicht erkennt, oder eine gemeinsame dritte Quelle. Die Sichtung in § 3.5 zeigt alle
drei Fehlerarten.

### 4.1 Ergebnis der Kodierung (2026-11-23)

Zwei Kodier-Agenten (dasselbe Modell, Opus) haben die 100 Paare unabhängig nach `codebuch.toml`
(Fassung 1) kodiert, ein Schlicht-Agent hat die 4 Uneinigkeiten entschieden (p055
`eigene_wiederholung`, p065 `andere_quelle`, p079 `verfahrenszitat`, p099 `baustein`). Kein
menschlicher Goldstandard; weil beide Kodierer dasselbe Modell sind, ist ihre Übereinstimmung ein
schwacher Beleg (Frage 19). Labels je Paar und Frage:
[`validierung/23-textuebernahme/labels.csv`](../../validierung/23-textuebernahme/labels.csv)
(`uv run python -I docs/plans/23-textuebernahme-messung.py --labels` bildet sie aus den lokalen
Antworten und rechnet alles hier nach, in wenigen Sekunden).

| Frage | gleich kodiert | Krippendorffs α (nominal) |
|---|---|---|
| `uebernahme` | 100 / 100 (alle „ja") | 1,000 (trivial) |
| `art` | 96 / 100 | 0,950 |
| politisch (Musterantrag / über Fraktionsgrenzen / sonst) | 99 / 100 | 0,981 |

**Präzision je politischer Art** (richtig = Endlabel ist genau die Art des Verfahrens; gewichtet mit
den Schichtgrößen, das Intervall überträgt die Wilson-Grenzen der Schichten mit denselben Gewichten,
eine ganz gezogene Schicht ohne Unsicherheit, wie in 13):

| Art | ungewichtet [Wilson 95 %] | **gewichtet** [übertragen] | je Schicht: richtig / gezogen von N [Wilson] |
|---|---|---|---|
| `musterantrag` | 26/30 = 0,867 [0,703; 0,947] | **0,889** [0,633; 0,972] | Gremium 12/14 von 423 [0,601; 0,960]; Periode 12/13 von 411 [0,667; 0,986]; Stadt 2/3 von 3 (ganz) |
| `fraktionsuebergreifend` | 9/30 = 0,300 [0,167; 0,479] | **0,296** [0,117; 0,595] | keine 3/12 von 32 [0,089; 0,532]; Gremium 4/9 von 24 [0,189; 0,733]; Periode 1/6 von 17 [0,030; 0,564]; Stadt 1/3 von 3 (ganz) |

Die falschen Musteranträge: p015 und p087 `baustein` (Anschreiben und Antragsformel der
CDU-Ratsfraktion zu verschiedenen Änderungen; Antragsformel und Erläuterung einer Förderrichtlinie
in wiederkehrenden Anträgen zu verschiedenen Themen), p095 `verfahrenszitat` (beide geben einen
Ratsbeschluss wieder), p044 `andere_quelle` (die Erklärung der Städteinitiative Tempo 30). Die 21
falschen Übernahmen über Fraktionsgrenzen: 6 `rechtszitat` (4 davon in der Schicht Gremium), 6
`andere_quelle`, 5 `verfahrenszitat`, 4 `baustein` — genau die Fehlerarten der Sichtung (§ 3.5), nur
häufiger, als sie erwarten ließ (9 bis 12 von 16 gegen 9 von 30).

**Empfindlichkeit der Musteranträge.** Beide Kodierer lasen denselben Grenzfall nach dem Wortlaut
des Codebuchs als `musterantrag`: dieselbe Fraktion, dieselbe Periode, ein anderes Gremium, oft im
selben Beratungsgang (Ausschuss, dann Rat; A nennt p001, p003, p011, p024, p038, p070, p100, B p001,
p024, p038, p100). Der Schlichter schlägt für eine Fassung 2 vor, das sei `eigene_wiederholung`.
Weil beide Kodierer dasselbe Modell sind, ist ihre Einigkeit hier kein unabhängiger Beleg. Über die
Metadaten (beide Dokumente in Rat oder Ausschuss derselben Periode, keines in einer
Bezirksvertretung) gehören 8 der 14 gezogenen Paare der Schicht Gremium zu diesem Fall: die sieben
von A und p015 (`baustein`).

| Lesart | ungewichtet | gewichtet [übertragen] |
|---|---|---|
| Hauptwert (Codebuch, Fassung 1) | 26/30 = 0,867 | **0,889** [0,633; 0,972] |
| ohne den Grenzfall (die Schicht Gremium schrumpft auf 6 von 14) | 19/22 = 0,864 | 0,894 [0,597; 0,980] |
| Grenzfall als falsch | 19/30 = 0,633 | 0,636 [0,412; 0,796] |

**Weitere Maße.** P0: alle 92 Paare über der Zufallsgrenze sind gemeinsamer Text (`uebernahme` =
„ja", Wilson-Untergrenze 0,960). Unter der Grenze sind es ebenfalls 8 von 8, nach der vorab
genannten Prüfung ist S\* also für „gemeinsamer Text" zu hoch — aber alle acht sind Bausteine (7)
oder eigene Wiederholung (1), keine politische Übernahme. Aus den ausgeschlossenen Schichten nennt
die Kodierung **kein** Paar politisch (0 von 28); von `politisch_ohne_partei` sind 2 von 4
Musteranträge. Die Ausschlussarten selbst stimmen nur teilweise (`baustein` 5/6, `verfahrenszitat`
2/6, `eigene_wiederholung` 2/6, `rechtszitat` 0/6 — die Regel über Rechtsmarken trifft Formulare,
die eine Norm nennen, etwa die Zulassung nach § 58 GO NRW —, `andere_quelle` 0/4, alle vier Zitate
im selben Verfahren); für die politischen Arten zählt nur, dass nichts Politisches darin liegt.
Bestätigt sind **9 Übernahmen über Fraktionsgrenzen** und **3 politische Paare über Stadtgrenzen**
(p002 Nachtbürgermeister, p090 Knochenmarkspender, beide Musterantrag; p066 TTIP, über
Fraktionsgrenzen, der Text stammt wahrscheinlich aus einem gemeinsamen Muster).

## 5. Urteil gegen das Kriterium

**Kriterium (Briefing, unverändert):** Präzision ≥ 0,9; weiter nur, wenn es Familien über Partei-
oder Stadtgrenzen gibt.

**Regel für das endgültige Urteil, vorab festgelegt** (vor der Kodierung):

1. Je politischer Art die gewichtete Präzision P1 (§ 4). Eine Art kommt auf die Seite, wenn **ihre
   eigene** Präzision mindestens 0,9 erreicht — eine gemeinsame Zahl über beide Arten verdeckte
   sonst, dass die kleinere Art (76 Paare) weit darunter liegen kann. Das Wilson-Intervall steht
   daneben.
2. „Familien über Partei- oder Stadtgrenzen gibt es", wenn die Kodierung mindestens drei Paare
   `fraktionsuebergreifend` oder mindestens ein Paar einer politischen Art über Stadtgrenzen bestätigt.
3. **bauen**: beide Arten ≥ 0,9 und Bedingung 2. **umbauen**: nur `musterantrag` ≥ 0,9; gebaut wird
   der ganze Schritt (er kostet wenig und liefert 14, 25 und 29 zu), gezeigt werden nur die
   Musteranträge, und die Übernahmen über Fraktionsgrenzen gehen in eine zweite Runde mit den Kanten
   aus 14 (Zitate im selben Verfahren) und den Abschnitten aus 11 (Briefkopf, Unterschrift).
   **verwerfen**: auch `musterantrag` < 0,9 oder Bedingung 2 nicht erfüllt.

**Endgültiges Urteil (nach der Kodierung, 2026-11-23): verwerfen.** Das Kriterium gilt je
politischer Art (Frage 32, vom Supervisor vor der Kodierung entschieden).

- **Regel 1, Präzision je Art:** `musterantrag` **0,889** (gewichtet; Intervall 0,633 bis 0,972),
  knapp unter 0,9; `fraktionsuebergreifend` **0,296** (0,117 bis 0,595), weit darunter. Keine Art
  erreicht 0,9.
- **Regel 2, Familien über Grenzen:** erfüllt — 9 bestätigte Übernahmen über Fraktionsgrenzen und 3
  bestätigte politische Paare über Stadtgrenzen.
- **Regel 3:** `musterantrag` < 0,9, also **verwerfen**. Für „umbauen" hätte `musterantrag` allein
  0,9 erreichen müssen.

Die Entscheidung ist knapp und unsicher: 0,889 liegt 0,011 unter der Schwelle, das Intervall reicht
von 0,63 bis 0,97, und die Empfindlichkeit zeigt, dass schon die Lesart eines einzigen Grenzfalls
den Wert zwischen 0,64 und 0,89 bewegt. Eine Runde „umbauen" (Plan § 8, höchstens eine) müsste
zugleich das Codebuch ändern (Fassung 2: dieselbe Fraktion im selben Beratungsgang ist eigene
Wiederholung) und die Regel (dieser Fall wird `eigene_wiederholung`, ein Baustein-Test für
Anschreiben und Antragsformel, Zitate eines Ratsbeschlusses als Verfahrenszitat); ohne den Grenzfall
liegt der gemessene Wert bei 0,894, auch das unter 0,9. Darauf ist keine Seite zu bauen; ob es die
Runde trotzdem gibt, entscheidet der Supervisor.

**Der Befund** für `decisions.md` und die Seite: Textübernahme zwischen Ratsdokumenten ist vor allem
Wiederholung derselben Urheber (24 398 Paare), Formular (68 125) und Zitat (Recht 14 352, Verfahren
4 193). Politische Übernahme im Sinn der Frage ist selten: Musteranträge derselben Partei über
Gremien und Perioden gibt es zu Hunderten (837 nach der Regel, rund 0,89 davon bestätigt), Übernahmen
über Fraktionsgrenzen nur wenige Dutzend (76 nach der Regel, rund 0,3 davon bestätigt, also in der
Größenordnung von 20 bis 25), und zwischen Düsseldorf und fünf anderen Städten drei bestätigte.

**Was bleibt:** der Smith-Waterman auf Wörtern und die Fensterkandidaten sind ein
Werkzeug für 25 (Versprechen der Wahlprogramme in Anträgen wiederfinden) und 29 („gab es das schon,
mit welchen Worten?"); die Art `verfahrenszitat` ist eine zweite Quelle für die Kanten von 14; die
Zahl der Bausteine (68 125 Paare) misst, wie viel Formulartext die Dokumente tragen, und ist für 11
eine Liste der Floskeln.

## 6. Bauplan Stufe 2 (nicht ausgeführt: das Urteil ist „verwerfen"; für eine Runde „umbauen" oder später)

**Beitrag `reuse`** nach F2 (Punkt 69): `src/georep/enrich/reuse.py` mit
`CONTRIBUTION = Contribution(name="23-textuebernahme", steps=reuse_steps, tables=(...))`, eine
Importzeile und ein Eintrag in `georep.enrich.CONTRIBUTIONS` **hinter** 15 (die Antragsteller
kommen aus dessen `processed/mitantraege.parquet` beziehungsweise der Spalte Antragsteller, nicht
aus einer Kopie des Regelwerks) und hinter 14 (Verweise zwischen Drucksachen ersetzen die
Verweisregel dieses Skripts, die nur Nummern im Text sucht). Reine Funktionen in
`src/georep/analysis/reuse.py`:

| Funktion | Ein- und Ausgabe | Herkunft im Messskript |
|---|---|---|
| `tokenize(texts, cap)` | Wort-IDs, Zeichenpositionen, Versätze | `tokenize` |
| `shingles`, `shingle_df` | Shingle-Hashes je Position, Dokumenthäufigkeit | `tokenize`, `shingle_df` (13: `Shingler`) |
| `windows`, `lsh_window_pairs` | Fensterpaare über die seltenen Shingles | `windows`, `lsh` |
| `smith_waterman(x, y)` | Wert, Spannen, Treffer, Spalten | `smith_waterman` |
| `align_pairs` | eine Ausrichtung je Dokumentpaar | `align_pairs` |
| `reuse_kind` | Art nach der Regel aus § 3.5 (beide Durchgänge) | `features`, `classify`, `refine`, `ShingleIndex` |
| `reuse_families` | Familien über die politischen Arten | `families` |

Eigene Umsetzung mit numpy und scipy (beide im Lockfile), wie Vorhaben 13 es begründet; keine neue
Abhängigkeit. Die Fensterlogik und Smith-Waterman sind zusammen rund 200 Zeilen.

**Woher die Partner kommen.** Ein Profil sieht in `run` nur sein eigenes Layout. Der Schritt liest
darum die Textstores der Partnerprofile über deren Settings, wie `report/publish.py` andere Profile
liest (`load_settings(profile=…)`), und das Fremdkorpus über einen Pfad aus `settings.local.toml`.
Fehlt ein Partner (CI, Pages, frischer Klon), läuft der Schritt mit dem, was da ist, und schreibt
in den Stamp, welche Partner er gesehen hat. Die veröffentlichte Fassung kommt deshalb, wie die
Texte seit Punkt 68, **aus einem Datenpaket**: `georep pack --reuse` packt
`textuebernahmen.parquet` (nur IDs, Spannen, Zahlen und Art; kein Text) nach
`snapshots/duesseldorf-textuebernahmen/` mit Größe und SHA-256 im README, und `bootstrap` legt es
nach `processed/`. Das Paket trägt alle Paare über der Grenze außer den Bausteinen (rund 47 000
Zeilen), geschätzt 1 bis 3 MB als Parquet.

**Settings** (Anhängeregel aus F2): Modell `ReuseSettings` vor `class Settings`, Feld `reuse` am
Ende, Block am Ende von `defaults.toml`:

```toml
# --- Vorhaben 23: Textübernahme über Perioden, Parteien und Städte
[reuse]
enabled = false        # Schalter, zunächst aus (Plan § 7, F2)
cap = 3000             # Wörter je Dokument (23-textuebernahme.md, § 3.1)
shingle = 5            # Wörter je Shingle, wie Vorhaben 13
block = 25             # Shingles je Block; ein Fenster sind zwei Blöcke
df_max = 30            # häufigere Shingles sind Baustein und zählen im MinHash nicht
min_rare = 15          # Fenster mit weniger seltenen Shingles suchen keine Partner
permutations = 128
bands = 64             # 32 × 4 fand nur 44 % (§ 3.4)
rows = 2
min_shared = 5         # Vorfilter vor der Ausrichtung
max_bucket_docs = 30
score_min = 20         # Zufallsgrenze aus der Nullverteilung (§ 3.3)
words_min = 30         # Mindestlänge einer Übernahme
partners = []          # Profile, gegen die verglichen wird, etwa ["duesseldorf-2014", "moenchengladbach"]
external = ""          # Pfad eines Fremdkorpus (settings.local.toml), leer = keins
seed = 23
```

Das Profil bekommt einen Block `[reuse.patterns]` mit den Floskeln (`FLOSKEL`), den Rechtsmarken
(`LEGAL`) und, für ein Fremdkorpus, den Kopfmustern der Antragsteller und der Zuordnung der
Dokumentarten (`CHERIF_POLITIK`, `CHERIF_EINGABE`, `LEIPZIG_KOPF`, `OSNABRUECK_KOPF`); kein Stadtwort
im Code (`tests/unit/test_report_city.py`).

**Ausgaben** (Schema-Version `REUSE_SCHEMA_VERSION = 1` als Modulkonstante, eine Zeile je Paar):

| Datei | Spalten |
|---|---|
| `processed/textuebernahmen.parquet` | `id_a`, `id_b` String (`id_a` das frühere Dokument, bei gleichem Datum die kleinere ID), `korpus_a`, `korpus_b` String, `wert` Int64, `a_von`, `a_bis`, `b_von`, `b_bis` Int64 (Wortpositionen), `treffer`, `spalten` Int64, `woerter` Int64 (kürzere Seite), `anteil_spaeteres` Float64, `art` String (Codes des Codebuchs plus `politisch_ohne_partei`), `grenze` String (`keine`, `Gremium`, `Periode`, `Stadt`) |
| `processed/textuebernahme_familien.parquet` | `id` String, `familie` String (kleinste ID der Familie), `groesse` Int64, `staedte`, `perioden`, `parteien` |

Spannen zusätzlich als F3-Spannen (`kind = "reuse"`, `value` = ID des Partners), damit der
Dokumentdialog die Stelle markieren kann.

**Verträge** an den Batch-Grenzen: `id_a != id_b`, Paare eindeutig und sortiert; `0 <= a_von <
a_bis <= Länge`; `treffer <= spalten`; `wert >= score_min` und `woerter >= words_min` für jede Zeile;
`art` aus der festen Liste; jede Kante einer Familie ist eine politische Zeile; die Familien
zerlegen ihre IDs. Kein `deal.pure` auf `smith_waterman` oder den Hashfunktionen (heiße Schleifen,
CLAUDE.md).

**Tests.** Beispiele: zwei gleiche Texte ergeben eine Ausrichtung über die volle Länge mit Wert =
Länge; ein eingefügtes Wort kostet genau eine Lücke; ein Text aus lauter häufigen Shingles gibt kein
Kandidatenfenster; ein Änderungsantrag mit der Drucksachennummer des Antrags wird
`verfahrenszitat`; zwei Läufe und eine vertauschte Eingabe ergeben dieselbe Datei. Eigenschaften
(hypothesis): Smith-Waterman ist symmetrisch im Wert, `0 <= wert <= min(len)`, `wert(x, x) =
len(x)`; der Wert ist gleich dem einer naiven O(n·m)-Umsetzung mit drei Fällen (Orakel in
`tests/property/`, wie der Matcher); jede Kante über der Grenze liegt in genau einer Familie.
Golden Master unberührt (neue Dateien, keine bestehende Zahl ändert sich).

**Berührte Dateien**: neu `src/georep/analysis/reuse.py`, `src/georep/enrich/reuse.py`,
`tests/unit/test_reuse.py`, `tests/property/test_reuse.py`, `snapshots/duesseldorf-textuebernahmen/`;
geändert `src/georep/enrich/__init__.py` (eine Zeile), `src/georep/settings.py` (Modell, Feld),
`src/georep/defaults.toml` (Block am Ende), `src/georep/profiles/duesseldorf*.toml` und
`moenchengladbach.toml` (`[reuse.patterns]`), `src/georep/layout.py` (zwei Pfade),
`src/georep/pack.py` (`--reuse`), `noxfile.py` (`MUTATION_SCOPE`), `docs/architecture.md`,
`docs/decisions.md` (Punkt beim Merge), `STATUS.md`.

**Laufzeit** (§ 3.8): der ganze Lauf mit dem Fremdkorpus 19 Minuten (unter Fremdlast), davon 8
Minuten Ausrichtung und 6 Minuten LSH mit Vorfilter; ohne Fremdkorpus geschätzt 10 bis 12 Minuten,
weil fast alle Paare innerhalb Düsseldorfs liegen. Für Pages ohne Bedeutung, weil das Paket gelesen
wird. Kein Netz, kein Modell.

### 6.1 Die Einbettungen aus Vorhaben 18 als zweite Kandidatenquelle

Ohne Modellserver (ollama ist seit 2026-11-23 angehalten) misst diese Stufe nur mit MinHash. Die
Einbettungen von Vorhaben 18 kommen später als **zweite Kandidatenquelle** dazu, nicht als Ersatz:

1. **Einheit.** Übernahme betrifft Teile eines Dokuments; eine Einbettung des ganzen Dokuments
   verwässert einen übernommenen Absatz in einem langen Antrag. Gebraucht werden Einbettungen je
   Fenster oder Absatz (Abschnitte aus Vorhaben 11, sonst die Fenster dieses Skripts, 50 Wörter
   versetzt um 25) — eine Frage an 18 (§ 9, 23.4).
2. **Kandidaten.** Je Fenster die k = 10 nächsten Fenster anderer Dokumente mit Kosinus ≥ θ (θ aus
   einer Stichprobe bekannter Übernahmen dieser Messung, so dass 95 % von ihnen darüber liegen); die
   Paare gehen in **dieselbe Ausrichtung** und **dieselbe Regel** wie die MinHash-Kandidaten. Die
   Vereinigung beider Quellen ist die Kandidatenmenge; der Stamp nennt beide.
3. **Was sie bringen sollen.** Umformulierte Musteranträge (ein Antrag, der in jeder Stadt den
   eigenen Ort, die eigenen Ämter und eigene Sätze einsetzt): ihre Fenster teilen wenige seltene
   Fünf-Wort-Folgen, ihre Bedeutung bleibt. Gemessen wird der Zugewinn als Zahl zusätzlicher
   Ausrichtungen über der Grenze, getrennt nach Art und Grenze, und die Präzision der zusätzlichen
   Paare an einer eigenen Schicht der Stichprobe.
4. **Was sie nicht dürfen.** Ein Paar mit hoher Kosinusähnlichkeit, aber ohne Ausrichtung über der
   Grenze, ist keine Textübernahme, sondern „gleiches Thema" oder „gleiche Idee in anderen Worten".
   Solche Paare bekommen eine eigene Art (`gleiche_idee`), gehen nicht in die Präzision P1 und nicht
   in die Familien; ob sie auf die Seite kommen, ist eine eigene Messung.

Die Mehrsprachigkeit des Modells (`nomic-embed-text-v2-moe`) spielt keine Rolle; alle Texte sind
deutsch.

## 7. Bauplan Stufe 3

Ein Abschnitt **„Wer übernimmt von wem"** auf `akteure.html` (Seite aus Vorhaben 15), nur mit dem,
was die Kodierung bestätigt:

- eine Tabelle Partei × Partei der Übernahmen über Fraktionsgrenzen je Periode (Zahl der Paare, mit
  Richtung: wer zuerst), und die Musteranträge je Partei über Gremien und Perioden;
- je Zeile ein Link auf zwei Beispielpaare im Dokumentdialog (IDs; der Dialog zeigt die markierte
  Stelle aus den F3-Spannen, keinen neuen Text auf der Seite);
- ein Satz zur Validierung („Präzision x an n Paaren, geprüft von zwei KI-Kodierern, nicht von
  Menschen") und einer zu den Grenzen (Hauptdatei bis 3 000 Wörter, keine Anlagen, Fremdkorpus mit
  vier Städten außerhalb von NRW);
- geschätzt 6 bis 12 KB (zwei kleine Tabellen, rund 40 Beispiel-IDs), weit unter dem Budget einer
  Unterseite (500 KB).

Tabellen im Register: `textuebernahmen.parquet` und die Familien als Download mit Spaltendoku.
Bausteine, Rechtszitate und Verfahrenszitate erscheinen nicht als Übernahme, nur als Zahl in der
Methodenzeile („so viele Stellen wurden als Baustein … ausgeschlossen").

## 8. Vorab festgelegte Hypothesen

Keine Hypothesentests. Das Vorhaben beschreibt (wer übernimmt von wem); jede Zahl auf der Seite
heißt „explorativ". Vorab festgelegt sind nur die Maße und Regeln der Validierung (§ 4) und die
Urteilsregel (§ 5).

## 9. Risiken und offene Fragen

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 23.1 | Zählt ein Antrag, den dieselbe Fraktion nach der Wahl oder in einer anderen Bezirksvertretung wieder einbringt, als „Musterantrag"? | Das Briefing definiert Musterantrag über Partei und Stadt oder Periode; im Datensatz sind fast alle Musteranträge solche Wiederholungen derselben Partei in Düsseldorf, nicht Vorlagen einer Vereinigung | ja, wie das Briefing; die Seite sagt „gleicher Text derselben Partei in einem anderen Gremium oder einer anderen Periode" und nennt Vereinigungen nicht, solange keine Quelle es belegt |
| 23.2 | Sollen Musteranträge der kommunalpolitischen Vereinigungen (GAR NRW, SGK NRW, KPV NRW u. a.) selbst als Korpus geladen werden? | Erst damit ließe sich „Musterantrag" von „Wiedervorlage" trennen und der Ursprung benennen; das Cherif-Korpus liegt außerhalb von NRW und zeigt nur sechs politische Paare (§ 3.5) | nein in Stufe 1; als Fremddaten für eine spätere Runde vorgeschlagen (Abruf nur von den Seiten der Vereinigungen, Lizenz klären) |
| 23.3 | Reicht der Verweis über die Drucksachennummer, um Zitate im selben Verfahren zu erkennen? | Ein Änderungsantrag ohne Nummer im Text landet sonst als „über Fraktionsgrenzen"; das ist die wahrscheinlichste Fehlerquelle von P1 | in Stufe 2 die Kanten von Vorhaben 14 (Titel, Anlage, Nachtragsnummer) statt der Nummernsuche dieses Skripts |
| 23.4 | Liefert Vorhaben 18 Einbettungen je Fenster oder Abschnitt, nicht nur je Dokument? | Ohne sie findet die zweite Kandidatenquelle übernommene Absätze in langen Dokumenten nicht (§ 6.1) | ja, Fenster von 50 Wörtern wie hier; sonst die Abschnitte aus Vorhaben 11 |
| 23.5 | Darf die Seite Paare aus dem Cherif-Korpus (Leipzig, Osnabrück, Dresden, Freiburg) mit ID und Link nennen? | CC BY 4.0 verlangt die Nennung der Städte; Dresden DL-DE/Zero, Freiburg DL-DE/BY | ja mit Quellenangabe je Stadt, nur IDs und Links auf das jeweilige Ratsinformationssystem, kein Text |
| 23.6 | Gilt die Kappung bei 3 000 Wörtern je Dokument auch in Stufe 2? | Sie schneidet 1 % der Düsseldorfer Dokumente und viele lange Vorlagen der Fremdstädte ab; Anträge sind kürzer | ja; ein Schalter erlaubt mehr, wenn Anlagen (F6) dazukommen |
| 23.7 | Ist der Antragsteller einer Fraktion „unbekannt" (Partei fehlt), soll das Paar dennoch politisch zählen? | 824 Paare `politisch_ohne_partei` (§ 3.5), vor allem Einzelmandate und die Sammelart der Periode 2014–2020 | nein; die Seite zählt nur Paare mit Partei auf beiden Seiten |
| 23.8 | Darf das Kriterium (Präzision ≥ 0,9) je politischer Art gelesen werden statt über beide zusammen? | Über beide zusammen könnten 837 gute Musteranträge 76 schwache Übernahmen über Fraktionsgrenzen tragen; die Seite zeigte dann eine Art, die die Schwelle nicht hält | **entschieden** vom Supervisor vor der Kodierung (Frage 32 in `fragen-2026-11.md`): je Art (§ 5, Regel 1) |
| 23.9 | Wann kommen die Einbettungen aus 18 dazu? | ollama ist angehalten; ohne sie fehlen umformulierte Übernahmen | nach Konrads Signal und dem Merge von 18, als zweite Kandidatenquelle (§ 6.1) mit eigener Schicht in einer zweiten Stichprobe |

**Vorschläge des Schlichters für eine Fassung 2 des Codebuchs** (2026-11-23, notiert, nicht
angewandt; lokal unter `messdaten/kodierung/23-textuebernahme/schlichtung.jsonl`):

- (a) `musterantrag` nur zwischen Gliederungen derselben Partei (Ratsfraktion und Bezirksfraktion,
  zwei Bezirksfraktionen, Städte); dieselbe Fraktion in Ausschuss und Rat derselben Periode ist
  `eigene_wiederholung` — der Urheber entscheidet, nicht das Gremium (§ 4.1, Empfindlichkeit).
- (b) Baustein-Test: „Könnte der Absatz unverändert in eine Vorlage derselben Reihe zu einer anderen
  Sache?" — dann `baustein`.
- (c) Dritte Quelle: geben beide Dokumente denselben dritten Text wieder, wird das Paar so kodiert,
  wie jedes Dokument mit dieser Quelle kodiert würde (ein ausdrücklich wiedergegebener Beschluss der
  Stadt macht `verfahrenszitat`); städtische Geschäftsanweisungen sind `rechtszitat`, Projektaufrufe
  `andere_quelle`; `rechtszitat` nur bei einer benannten Norm.
- (d) Gleiche Forderung zum gleichen Haushaltsgegenstand: nur bei geteiltem Wortlaut jenseits von
  Formular, Haushaltsformel und Bezeichnung des Postens `fraktionsuebergreifend`, sonst `baustein`.

**Risiken.** Die Art hängt an Regeln über Metadaten (Urheber, Parteien, Gremium, Verweis) und an
einer Floskelliste, die aus Düsseldorfer Formularen stammt; in Mönchengladbach und den Fremdstädten
greift sie weniger. Die Antragsteller kommen aus dem Regelwerk von 15 (Präzision 119/119, Recall
0,86); ein übersehener Mitantragsteller macht aus einem Musterantrag eine Übernahme über
Fraktionsgrenzen oder umgekehrt. Die Messung lief unter Fremdlast; die Zahlen hängen daran nicht,
nur die Laufzeiten. Die Zwischenablage unter `messdaten/23-textuebernahme/cache/` (1,5 GB) gilt nur
für die Parameter im Stamp; `--neu` rechnet alles neu.

## 10. Änderungen durch die Synergie (füllt der Supervisor)

Vorschläge des Mess-Agenten: 14 liefert die Kanten zwischen Drucksachen (Titel, Anlage,
Nachtragsnummer), die hier die Nummernsuche im Text ersetzen; 11 liefert Briefkopf, Beschlussvorschlag
und Unterschrift als Abschnitte, mit denen Bausteine ohne Floskelliste erkannt werden; 15 liefert die
Antragsteller als Datei statt als importiertes Regelwerk; 25 kann die Ausrichtung dieses Vorhabens
für „Versprechen im Antrag" übernehmen; 13 bekommt mit der Seltenheitsgrenze und den Fenstern eine
Antwort auf seine Musterantrags-Frage (§ 3.4 dort): wortgleiche Anträge in mehreren
Bezirksvertretungen sind hier `musterantrag` mit Grenze Gremium.
