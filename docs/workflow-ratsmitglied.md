# Arbeitsablauf: neu im Rat, ein Gebiet oder ein Thema einarbeiten

Stand 2026-10-14, `v0.13.0`; die veröffentlichte Seite ist aus Commit `813827e` gebaut. Diese Sicht
ist ein **Beispiel**, kein Versprechen: sie zeigt Schritt für
Schritt, wie jemand, der neu im Rat der Stadt Düsseldorf ist, mit der veröffentlichten Seite und den
Schnittstellen schneller findet, was zu seinem Gebiet oder seinem Thema gehört — und § 4 sagt
ehrlich, was die Seite dafür **nicht** kann. Jede Behauptung unten ist am 2026-10-14 an der
veröffentlichten Seite oder an den Seitenvorlagen geprüft.

Die drei anderen Sichten: [technik.md](technik.md), [inhalt.md](inhalt.md),
[statistik.md](statistik.md). Als durchgehendes Beispiel dient **Wahlbezirk 39, Benrath,
Stadtbezirk 9** und das Thema **Verkehr**; jeder Schritt funktioniert mit jeder anderen Nummer und
jedem anderen Thema genauso.

Alle Adressen unten sind relativ zu
<https://konradvoelkel.github.io/geographic-representation-dus/>.

## 1. Der Weg über die Seite

### Schritt 1: die Größenordnungen (eine Minute)

Die [Kernzahlen](https://konradvoelkel.github.io/geographic-representation-dus/#kernzahlen) ganz oben
sagen, worüber geredet wird: 41 Wahlbezirke aus 306 Stimmbezirken, **19 108 Ratsdokumente** der
Wahlperiode 2020 bis 2025, davon 19 033 mit Text, 5 727 Suchbegriffe, 10 739 Dokumente mit Treffer.
Das ist der Rahmen: ein einzelner Wahlbezirk liegt zwischen 316 und 1 761 Treffern.

### Schritt 2: das eigene Gebiet markieren

Ins Suchfeld unter
[`#suche`](https://konradvoelkel.github.io/geographic-representation-dus/#suche) „Benrath" tippen
oder die Adresse gleich teilbar aufrufen:

**[`index.html#suche=Benrath`](https://konradvoelkel.github.io/geographic-representation-dus/#suche=Benrath)**

Die Vorschlagsliste führt den Wahlbezirk („Benrath", Wahlbezirk 39, 811 Dokumente) **und** die
Straßen, die seinen Namen tragen („benrather schloßallee" 29 Dokumente, „benrather marktplatz" 13).
Die Auswahl des Wahlbezirks markiert ihn gleichzeitig in der Karte, in der Tabelle „Je Wahlbezirk" und
im Streudiagramm, und die markierte Tabellenzeile klappt aus der Vorschau von selbst auf. Die Adresse
in der Leiste ist teilbar — ein Link an die Fraktion zeigt dort dieselbe Markierung.

Die Zeile des Bezirks 39 in der Tabelle
[`#wahlbezirke`](https://konradvoelkel.github.io/geographic-representation-dus/#wahlbezirke) sagt
dann: 811 Treffer, 11 318 Wahlberechtigte, 6 650 Wähler, 58,8 % Wahlbeteiligung, Trefferquote 0,072,
**189 Begriffe**, und als häufigste Begriffe „münchener straße (135), koblenzer straße (109), frankfurter
straße (96), benrodestraße (67), bonner straße (62)". Die Spaltenköpfe sind Sortierschalter.

### Schritt 3: woran die Sichtbarkeit des Gebiets hängt

Der Abschnitt
[`#begriffe`](https://konradvoelkel.github.io/geographic-representation-dus/#begriffe) hat je
Wahlbezirk eine aufklappbare Liste **aller** seiner Begriffe mit Dokumentzahl (sie wird beim ersten
Aufklappen aus `data/begriffe.json` nachgeladen). Zwei Dinge sind dort gleich mitzulesen:

- Die **20 trefferstärksten Begriffe stadtweit** — „grafenberger allee" (205), „vennhauser allee"
  (176), „hofgarten" (172) — zeigen, wie viel ein einzelner großer Straßenname trägt.
- Die **55 stadtweiten Begriffe** über dem 99-%-Quantil (64 Dokumente) sind benannt, weil viele ihrer
  Dokumente **nicht** von dem Bezirk handeln, dessen Wörterbuch sie führt. Für Benrath betrifft das
  „münchener straße" (135 Dokumente, geteilt mit sechs anderen Bezirken) und „koblenzer straße" (109,
  geteilt mit 40 und 41). Wer die Zahl 811 liest, sollte diese Liste gesehen haben.

### Schritt 4: die Dokumente wirklich öffnen

**Jeder Begriff auf der Seite ist eine Schaltfläche.** Ein Klick auf „benrodestraße" öffnet einen
Dialog mit den 67 Dokumenten, neueste zuerst, je Zeile Datum, Titel, Drucksachennummer, Dokumentart,
Urheber — und einen Link auf das PDF im Ratsinformationssystem, also auf
`https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/downloadfiles/<datei>.pdf`. Von dort ist es ein
Schritt in das Ratsinformationssystem selbst, wo Beratungsfolge, Sitzung und Beschluss stehen, die
diese Seite nicht hat.

Der Dialog arbeitet mit `data/dokumente.json` (2,2 MB, beim ersten Klick nachgeladen) und braucht
darum einen Webserver; aus dem Dateisystem geöffnet sagt die Seite das.

### Schritt 5: wo über das Gebiet beraten wurde

Die Tabelle „Je Wahlbezirk" im Abschnitt
[`#gremien`](https://konradvoelkel.github.io/geographic-representation-dus/#gremien) zerlegt die 811
Treffer nach dem Gremium, das das Dokument eingebracht hat:

| Bezirk | Stadtbezirk | Treffer | eigene BV | andere BV | Rat | Ausschüsse | Beiräte | unbekannt |
|---|---|---|---|---|---|---|---|---|
| 39 Benrath | 9 | 811 | **403 (49,7 %)** | 170 | 29 | 204 | 5 | 0 |

Also: die Hälfte dessen, was über Benrath geschrieben wird, kommt aus der **Bezirksvertretung 9** —
dem Gremium, in dem es zuerst zu lesen ist. Ein Viertel kommt aus den Ausschüssen des Rates.

**Das Gremium wird nicht geschätzt, und der Abschnitt sagt, woher es kommt.** Erste Quelle ist das
Kürzel der Drucksachennummer (`BV9/…`, `RAT/…`, `OVA/…`); in der Hauptperiode trägt jede der 19 108
Nummern eines, also kommt dort jedes Gremium von dort. Zweite Quelle ist seit Punkt 58 die
**Beratungsfolge** des Ratsinformationssystems — die Gremien, die ein Dokument beraten haben. Sie
entscheidet nur, wo die Nummer kein bekanntes Gremium nennt, und auch dann nur, wenn sie genau eine
Organisation nennt; der Abschnitt nennt beide Anteile mit Zahlen. Für Düsseldorf steht dort, dass
Nummer und Folge in 16 902 Fällen übereinstimmen und sich in 145 widersprechen (0,9 % der
Vergleiche) — **wo beide etwas sagen, bleibt die Nummer**, denn die Folge ist ein Weg und die Nummer
eine Akte. Auf den anderen Seiten trägt die Folge mehr: in `2014-2020/` kommen 5 659 Gremien aus ihr
und 1 535 Dokumente bleiben offen, weil ihre Folge mehrere Gremien nennt, und in
`moenchengladbach/`, wo keine Nummer ein Kürzel trägt, kommen **alle** 1 620 erkannten Gremien aus
der Folge.

Wer wissen will, welche Bezirke stark und welche schwach an ihrer eigenen Bezirksvertretung hängen,
schaltet die Karte unter
[`#karte`](https://konradvoelkel.github.io/geographic-representation-dus/#karte) auf **„Anteil eigene
Bezirksvertretung"** (die Klassen reichen von unter 37 % bis ab 62 %) — dieselbe Einfärbung erscheint
dann als Zahl in der Kennzahlspalte der Bezirkstabelle.

### Schritt 6: ein Thema statt eines Gebiets — Beispiel Verkehr

Für ein Thema gibt es zwei Zugänge, und beide sind Schätzungen, keine Volltextsuche.

**Der Ausschuss.** Die zweite Tabelle unter
[`#gremien`](https://konradvoelkel.github.io/geographic-representation-dus/#gremien), „Dokumente je
passendem Ausschuss", ordnet jedem Dokument mit Text den Ausschuss zu, der sachlich zu ihm passt —
auch einem, das nie in einem Ausschuss war:

| Ausschuss | Dokumente | Anteil | davon ohne Ausschussberatung | Wahrscheinlichkeit (Median) |
|---|---|---|---|---|
| **Ordnungs- und Verkehrsausschuss (OVA)** | 1 825 | 9,6 % | **1 082** | 60 % |
| Ausschuss für Planung und Stadtentwicklung (APS) | 1 250 | 6,6 % | 710 | 62 % |
| keine Zuordnung (Restklasse) | 11 869 | 62,4 % | 11 284 | — |

Die Spalte „davon ohne Ausschussberatung" ist die interessante: rund 1 082 der 1 825
Verkehrsdokumente tragen **kein** OVA-Kürzel in ihrer Drucksachennummer, ihre Zuordnung ist also
eine echte Schätzung und keine Wiederholung dessen, was ohnehin in der Nummer steht. (Die Zahlen
sind die der veröffentlichten Seite; ein Lauf auf einem anderen Rechner landet um einzelne Dokumente
daneben, weil die Thread-Zahl den Klassifikator in der letzten Stelle bewegt.) Und 62,4 % aller
Dokumente bleiben in der Restklasse — bei den Dokumenten der Bezirksvertretungen sind es vier von
fünf. **Das ist eine Vorsortierung, keine Auskunft.**

**Das Thema.** Die Themen-Tabelle unter
[`#gewichtung`](https://konradvoelkel.github.io/geographic-representation-dus/#gewichtung) nennt die
stärksten Wörter je Thema; Thema 0 heißt „Ordnungs- und Verkehrsausschuss (OVA)" und trägt „ordnungs,
verkehrsausschuss, straße, verkehrsmanagement, rheinbahn, öpnv, radverkehr, verkehr, straßen, platz"
über 2 425 Dokumente (13,9 % der Treffer). Die Zahlen daneben sind eine **Sensitivitätsrechnung** —
sie sagen, wie Tabelle 5 aussähe, wenn jedes Dokument nur mit seinem Anteil an diesem Thema zählte —
und keine Themensuche. Die Themennummern gelten nur für diesen Datenstand.

### Schritt 7: wer schreibt, und wohin die eigene Partei blickt

Der Abschnitt
[`#parteien`](https://konradvoelkel.github.io/geographic-representation-dus/#parteien) hat sechs
kleine Karten, je eine Partei: welcher Anteil **ihrer eigenen** Dokumente einen Wahlbezirk erwähnt.
Die Klassen sind je Partei gerechnet, die Karten sagen also „wohin eine Partei blickt", nicht „wie
viel sie schreibt". Der Umschalter darüber rechnet jede Zelle zusätzlich als **Abweichung vom Mittel
aller Parteien** in Prozentpunkten und als **Verhältnis** dazu — die Frage „redet meine Fraktion über
diesen Bezirk mehr oder weniger als der Durchschnitt" ist damit eine Radiotaste weit.

Die Tabelle „Je Partei" daneben nennt je Fraktion die Dokumentzahl (GRÜNE 2 308, CDU 2 140, SPD 2 107,
FDP 879, Die Linke 792, AfD 183) und die Korrelation zum Stimmenanteil samt der Bonferroni-Grenze
0,008 — das ist die auf sechs gleichzeitige Tests heruntergeteilte 5-%-Schwelle (0,05 / 6), denn bei
sechs Parteien wäre ein „signifikanter" Wert allein durch Zufall zu erwarten. Zwei Dinge gehören dazugelesen: der Urheber ist **abgeleitet** (der OParl-Server füllt seine
Urheberfelder nicht; 0 von 19 109), und 865 Dokumente einzelner Mandatsträger bleiben ohne Partei.
Jede Zuordnung steht mit ihrer Quelle in `dokumente_urheber` zum Download.

### Schritt 8: was gerade läuft

Für die **laufende** Wahlperiode seit dem 14.09.2025 gibt es eine eigene Seite:
**[`2025/`](https://konradvoelkel.github.io/geographic-representation-dus/2025/)** — 4 095 Dokumente,
4 075 mit Text, 2 173 mit Treffer, Karte, Begriffe, Gremien, Urheber und die **Monatsreihe** unter
[`2025/#monate`](https://konradvoelkel.github.io/geographic-representation-dus/2025/#monate) mit zwei
Balken je Monat (alle Dokumente, die mit Treffer) über 14 Monate. Dort gibt es keine Regression und
kein Streudiagramm, weil zu einer laufenden Periode keine Wahlbeteiligung gehört; Kopf und Kurzfassung
sagen das. **Der Stand ist der Erstabruf vom 13.10.2026**, und die Seite nennt ihr Abrufdatum selbst —
der Timer, der die Periode fortschreibt, läuft noch nicht.

Für den langen Blick zurück:
[`2014-2020/`](https://konradvoelkel.github.io/geographic-representation-dus/2014-2020/) rechnet
dieselbe Auswertung über 22 215 Dokumente der vorigen Periode, und der Abschnitt
[`#perioden`](https://konradvoelkel.github.io/geographic-representation-dus/#perioden) der Hauptseite
stellt beide nebeneinander. Benrath ist dort einer der Bezirke mit dem stärksten Rückgang: Quote
0,1283 → 0,0717.

### Schritt 9: eigene Zahlen, ohne Programm

[`#downloads`](https://konradvoelkel.github.io/geographic-representation-dus/#downloads) listet 53
Dateien mit Format, Zeilenzahl, Größe, Beschreibung und SHA-256. Für eine Tabellenkalkulation sind
diese vier der kürzeste Weg:

| Datei | gut für |
|---|---|
| [`data/wahlbezirke_auswertung.csv`](https://konradvoelkel.github.io/geographic-representation-dus/data/wahlbezirke_auswertung.csv) | 41 Zeilen: Treffer, Begriffe, Dokument-IDs, Wahlberechtigte, Wähler, Stimmen je Partei, Wahlbeteiligung, Trefferquote |
| [`data/wahlbezirke_gremien.csv`](https://konradvoelkel.github.io/geographic-representation-dus/data/wahlbezirke_gremien.csv) | Treffer je Bezirk nach Gremium, mit den Stadtbezirken des Bezirks |
| [`data/inverted_index.csv`](https://konradvoelkel.github.io/geographic-representation-dus/data/inverted_index.csv) | 5 727 Zeilen: je Begriff die Dokumente (mit „;" verbunden) |
| [`data/summary.json`](https://konradvoelkel.github.io/geographic-representation-dus/data/summary.json) | die Kernzahlen und beide Spalten von Tabelle 5 in einer Datei, 1,2 KB — das ist die Schnittstelle, aus der auch der Städtevergleich liest. Die zweite Spalte lässt die Wahlbezirke 1 und 10 aus; auf der Seite heißt ihr Kopf seit Punkt 61 „explorativ", weil sie nach dem Ansehen der Daten entstanden ist ([statistik.md](statistik.md), § 1) |

Die Spalten sind in
[`data/schema.json`](https://konradvoelkel.github.io/geographic-representation-dus/data/schema.json)
maschinenlesbar beschrieben (je Spalte `column`, `dtype`, `description`, `unit`), und auf der Seite
steht dieselbe Beschreibung als Tabelle. Prüfsummen sind SHA-256; Listen sind in CSV mit „; "
verbunden, bei `paper_ids` mit „;".

## 2. Der Weg über die Kommandozeile

Wer mehr als 41 Zeilen braucht — etwa die Dokumente eines Bezirks nach Gremium, Datum und Titel —
nimmt die Parquet-Dateien (ein spaltenweises Tabellenformat, das Typen und Listen mitbringt und das
Polars, DuckDB, R und pandas direkt lesen). Zwei Tabellen sind **nicht** veröffentlicht und nur nach einem eigenen Lauf
da: `papers_gremien` (Gremium je Dokument) und der Korpus `interim/papers.parquet` mit den
Metadaten. Ein Lauf braucht kein Netz, nur die Datenpakete aus dem Repo:

```bash
git clone git@github.com:konradvoelkel/geographic-representation-dus.git   # das Repository holen
cd geographic-representation-dus
uv sync --locked            # Python und alle Pakete genau in den Versionen aus uv.lock
uv run georep bootstrap     # den Datensatz aus reference/ übernehmen
uv run georep run           # 27 Offline-Schritte, rund 23 s
uv run georep export        # die Parquet-Ergebnisse zusätzlich als CSV
```

Danach liegen die Tabellen unter `data/duesseldorf/processed/` und der Korpus unter
`data/duesseldorf/interim/papers.parquet`. Welcher Schritt was schreibt, zeigt `uv run georep steps`;
`uv run georep status` sagt je Schritt, ob er aktuell ist und warum.

**Die Dokumente eines Bezirks, die aus einem bestimmten Ausschuss kommen** (geprüft am 2026-10-14,
Polars 1.x):

```python
import polars as pl

B, BEZIRK, GREMIUM = "data/duesseldorf", 39, "OVA"
treffer = pl.read_parquet(f"{B}/processed/wahlbezirke_auswertung.parquet").filter(
    pl.col("wahlkreis_id") == BEZIRK
)
meine = pl.LazyFrame({"id": list(treffer.get_column("paper_ids").item())})
print(
    pl.scan_parquet(f"{B}/interim/papers.parquet")
    .select("id", "date", "reference", "name")
    .join(meine, on="id", how="semi")
    .join(pl.scan_parquet(f"{B}/processed/papers_gremien.parquet").select("id", "gremium"), on="id")
    .filter(pl.col("gremium") == GREMIUM)
    .sort("date", descending=True)
    .collect()
)
```

Ergebnis am 2026-10-14: 811 Treffer im Bezirk 39, davon **59 aus dem Ordnungs- und
Verkehrsausschuss**, der jüngste `OVA/096/2025` vom 03.06.2025 („Maßnahmen zur Optimierung des …").
`select("text")` statt `select("name")` gibt den extrahierten Volltext dazu — der liegt lokal, auf der
veröffentlichten Seite nicht. `papers_gremien.parquet` trägt seit Punkt 58 außerdem `quelle`
(`nummer`, `alias`, `beratungsfolge`, `unbekannt`), `folge_gremium` und `folge_anzahl`: wer wissen
will, welche Zuordnung aus der Nummer kommt und welche aus der Beratungsfolge, nimmt
`select("id", "gremium", "quelle")` und gruppiert danach.

**Welche Begriffe das eigene Gebiet tragen, nach Dokumentzahl:**

```python
import polars as pl

B, BEZIRK = "data/duesseldorf", 39
zeile = pl.read_parquet(f"{B}/processed/wahlbezirke_auswertung.parquet").filter(
    pl.col("wahlkreis_id") == BEZIRK
)
meine = pl.DataFrame({"suchbegriffe": list(zeile.get_column("suchbegriffe").item())})
print(
    pl.read_parquet(f"{B}/processed/inverted_index.parquet")
    .join(meine, on="suchbegriffe", how="semi")
    .sort("anzahl_treffer", descending=True)
    .head(10)
)
```

**Ohne Klon** geht derselbe Blick auf die 41 Zeilen direkt aus der veröffentlichten CSV:

```python
import polars as pl

df = pl.read_csv("wahlbezirke_auswertung.csv")  # vorher von …/data/ geladen
spalten = ["wahlkreis_id", "anzahl_treffer", "wahlbeteiligung", "trefferquote"]
print(df.select(spalten).sort("trefferquote", descending=True))
```

Zwei weitere Befehle, die sich lohnen: `uv run georep regress --exclude 1 10` druckt Tabelle 5, und
`uv run georep regress --controls` Tabelle 6 mit den Kontrollvariablen. Wer die **aktuellen**
Dokumente der laufenden Periode will und bereit ist, dafür Netz zu benutzen, hat einen schnellen und
einen langsamen Schritt:

```bash
uv run georep --profile duesseldorf-2025 bootstrap               # Stand 13.10.2026 aus snapshots/2025/
uv run georep --profile duesseldorf-2025 fetch papers --force    # eine OParl-Seite, 45 bis 85 s
uv run georep --profile duesseldorf-2025 fetch pdfs texts        # nur die neuen PDFs, je 1 s Pause
uv run georep --profile duesseldorf-2025 run                     # Kette und Seite
```

`georep fetch` auf einem leeren Datenverzeichnis dauert dagegen **Stunden** (Hochrechnung: 5,8 h für
19 108 PDFs, 2,8 GB) — das ist nichts, was man nebenbei startet.

## 3. Der Datenstand, den man mitlesen muss

| Was | Stand |
|---|---|
| Ratsdokumente 2020 bis 2025 | Datensatz der Arbeit, November 2025 |
| Straßen und Orte (das Wörterbuch) | November 2025 — gilt auch für die beiden anderen Düsseldorfer Perioden |
| Wahlergebnis und Zuschnitt | Kommunalwahl 14.09.2025 |
| Laufende Periode (`2025/`) | Erstabruf 13.10.2026; der Timer läuft noch nicht |
| Sozialdaten der Kontrollvariablen | 31.12.2021 |
| Namen der Gremien | 14.10.2026 (die Seite nennt den Stand selbst) |

Der Kopf jeder Seite nennt ihr Abrufdatum, das neueste Dokument und die Zahl der Dokumente ohne Text
— alles aus dem Modell, nichts fest kodiert.

## 4. Was die Seite nicht kann

Diese Liste ist der Grund, warum der Weg oben mit „finden, dann im Ratsinformationssystem lesen"
endet und nicht dort bleibt.

- **Keine Volltextsuche.** Die Texte der PDFs liegen auf keiner veröffentlichten Seite — aus Lizenz-
  und Datenschutzgründen werden nur abgeleitete Tabellen und Kennungen veröffentlicht. Die Suche
  findet **Namen von Straßen, Orten und Wahlbezirken**, keine Wörter im Dokument. Wer „Radverkehr"
  sucht, findet hier nichts; wer „Benrodestraße" sucht, findet 67 Dokumente. Volltext gibt es nach
  einem lokalen Lauf (`interim/papers.parquet`, Spalte `text`) oder im Ratsinformationssystem selbst.
- **Keine Themensuche.** Der passende Ausschuss und die 20 Themen sind Vorsortierungen mit
  ausgewiesener Unsicherheit: 62,4 % der Dokumente bleiben in der Restklasse, bei den Dokumenten der
  Bezirksvertretungen vier von fünf. Ein Dokument, das kein Thema trifft, ist deswegen nicht
  themenlos.
- **Keine Benachrichtigung.** Es gibt kein Abonnement, keinen Alarm und keinen RSS-Feed. Die
  laufende Periode wird fortgeschrieben, aber man muss nachsehen. Wer eine Benachrichtigung braucht,
  baut sie selbst auf `2025/data/summary.json` oder auf dem Abrufdatum im Kopf der Seite — oder
  benutzt die Abo-Funktion des Ratsinformationssystems, wenn es eine hat.
- **Keine Beschlusslage, keine Sitzungstermine, keine Beratungsfolge je Dokument.** Die Seite sagt,
  welches Gremium ein Dokument eingebracht hat, nicht was beschlossen wurde oder wann die nächste
  Sitzung ist. Die Beratungsfolge (`consultation`, bei 18 708 von 19 109 Dokumenten der
  Hauptperiode) wird seit Punkt 58 **gelesen**, aber nur als zweite Quelle des Gremiums und nur als
  Zahl: wie viele Dokumente ihr Gremium von ihr haben, wie oft sie der Nummer zustimmt oder
  widerspricht. Welche Stationen ein einzelnes Dokument durchlaufen hat, steht **nicht** auf der
  Seite und in keiner veröffentlichten Datei — dafür ist das Ratsinformationssystem da. Mit
  Reihenfolge gibt es sie dort auch nur über die `consultation`-Objekte selbst (je Dokument eines mit
  `meeting` und `order`), und die sind nicht abgerufen.
- **Keine Mandatsträger.** Wer in welchem Gremium sitzt, steht nicht auf der Seite; das OParl-Feld
  `memberships` ist nicht abgerufen. Der Urheber eines Dokuments ist eine Fraktion oder eine Klasse,
  keine Person — 865 Dokumente einzelner Mandatsträger bleiben ohne Partei.
- **Keine Suche über mehrere Perioden oder Städte zugleich.** Jede Periode und jede Stadt ist eine
  eigene Seite mit eigener Suche; nur `vergleich.html` und der Abschnitt „Zwei Wahlperioden" stellen
  Zahlen nebeneinander.
- **Die Zahl 811 ist nicht „811 Dokumente über Benrath".** Sie ist „811 Dokumente, in denen ein Name
  aus dem Wörterbuch dieses Bezirks vorkommt". Ein Dokument über die Münchener Straße zählt für sieben
  Bezirke; ein Dokument, das Benrath beim Namen nennt, aber keine Straße darin, zählt **gar nicht** —
  „Benrath" steht in `search.exclude` des Profils, wie alle Stadtteilnamen, weil ein Stadtteil zu grob
  für einen Wahlbezirk ist und oft in mehreren liegt (der Name allein stünde in 411 Dokumenten, die
  63 Namen der Liste zusammen in 19 644). Wie weit die Zahl 811 dadurch trägt, steht in
  [statistik.md](statistik.md), § 3 und § 12.
- **Kein Suchfeld auf `vergleich.html`** und keine Downloads dort: die Vergleichsseite liest nur die
  `summary.json` der Stadtseiten und rechnet selbst nichts.
- **`karte.html` braucht Netz.** Die Hauptkarte ist inline-SVG und funktioniert offline; die
  Leaflet-Karte mit OpenStreetMap-Kacheln daneben ist die einzige Datei mit Fremdressourcen.
- **Aus dem Dateisystem geöffnet** (`file://`) bleiben der Dokumentdialog und die Begriffslisten je
  Wahlbezirk leer — der Browser erlaubt das Nachladen dort nicht, und die Seite sagt es. Alles andere,
  Suche eingeschlossen, funktioniert offline.
