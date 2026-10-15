# Inhalt: welche Daten es gibt und was die Seite kann

Stand 2026-10-14, `v0.13.0`. Diese Sicht beantwortet: **was steckt drin, und was kann man
damit auf der Seite tun.** Jede Angabe unten ist an der veröffentlichten Seite
<https://konradvoelkel.github.io/geographic-representation-dus/> nachgesehen; sie ist aus Commit
`813827e` gebaut und zeigt alles bis **Punkt 58**. Die **Punkte 59 bis 61** liegen seit dem
2026-10-14 auf `main` und sind in der veröffentlichten Seite noch nicht zu sehen — die Stellen, an
denen das etwas ändert, sagen es.
Die drei anderen Sichten:
[technik.md](technik.md) (Schnittstellen, Kette, Veröffentlichung), [statistik.md](statistik.md) (die
Auswertungen), [workflow-ratsmitglied.md](workflow-ratsmitglied.md) (ein Arbeitsablauf). Aufbau des
Codes: [architecture.md](architecture.md); Gründe: [decisions.md](decisions.md).

## 1. Die vier Datensätze

Jeder ist ein Profil mit eigener Datenwurzel, eigener Seite und eigenen Downloads. Alle vier Läufe
sind Konrads; ihre Eingaben liegen als Pakete im Repo, damit GitHub Pages ohne Netz baut.

| | `duesseldorf` | `duesseldorf-2014` | `duesseldorf-2025` | `moenchengladbach` |
|---|---|---|---|---|
| Stadt | Düsseldorf | Düsseldorf | Düsseldorf | Mönchengladbach |
| Periode | 13.09.2020 – 14.09.2025 | 25.05.2014 – 12.09.2020 | ab 15.09.2025, **offen** | 13.09.2020 – 14.09.2025 |
| Wahl, die den Nenner liefert | Ratswahl 14.09.2025 | Ratswahl 13.09.2020 | Ratswahl 14.09.2025 | Ratswahl 14.09.2025 |
| Wahlbezirke | 41 | 41 (Zuschnitt 2025) | 41 | 33 |
| Stimmbezirke | 306 | 316 (Zuschnitt 2020) | 306 | 179 |
| Dokumente | 19 108 | 22 215 | 4 095 | 2 895 |
| davon mit Text | 19 033 (99,6 %) | 21 838 (98,3 %) | 4 075 (99,5 %) | **650 (22,5 %)** |
| davon mit Treffer | 10 739 | 12 977 | 2 173 | 489 |
| Treffer (Dokument-Bezirk-Paare) | 29 010 | 36 324 | 5 448 | 1 682 |
| Begriffe im Wörterbuch | 5 727 | 5 727 (geborgt) | 5 727 (geborgt) | 6 005 |
| Monate in der Reihe | 61 | 77 | 14 | 61 |
| Stand der Dokumente | Datensatz der Arbeit, November 2025 | Abruf 13.10.2026 | Erstabruf 13.10.2026 | Abruf 13.10.2026 |
| Stand der Geometrie | Stimmbezirke 2025 | Stimmbezirke 2020, umgerechnet | Stimmbezirke 2025 | **Stimmbezirke der Kommunalwahl 2025** (Punkt 65; bis zum 2026-10-14 Flächen vom 08.06.2022) |
| Seite | [Wurzel](https://konradvoelkel.github.io/geographic-representation-dus/) | [`2014-2020/`](https://konradvoelkel.github.io/geographic-representation-dus/2014-2020/) | [`2025/`](https://konradvoelkel.github.io/geographic-representation-dus/2025/) | [`moenchengladbach/`](https://konradvoelkel.github.io/geographic-representation-dus/moenchengladbach/) |

**Das Wörterbuch** entsteht je Wahlbezirk aus Straßennamen (OpenStreetMap über Overpass) und Orten
mit Koordinate (Wikidata per SPARQL, Wikipedia-GeoSearch), kleingeschrieben, je Begriff mit „straße"
zusätzlich die Variante mit „str.". Düsseldorf: 5 727 Begriffe, 1 196 Orte, Wörterbücher von 77 bis
751 Begriffen je Bezirk. Beide Düsseldorfer Nebenperioden benutzen **dasselbe** Wörterbuch wie die
Hauptperiode (`period.dictionary = "base"`, Stand November 2025), damit sich nur die Dokumente
unterscheiden.

### Die Lücken, je Datensatz benannt

Das Gremium je Dokument hat seit Punkt 58 **zwei** Quellen: die Drucksachennummer entscheidet, und wo
sie kein bekanntes Gremium nennt, entscheidet die Beratungsfolge aus OParl — aber nur, wenn die genau
eine Organisation nennt.

| Datensatz | ohne Text | woran es liegt | Gremium unbekannt | Urheber unbekannt |
|---|---|---|---|---|
| `duesseldorf` | 75 (0,4 %) | 16 ohne Hauptdatei, 59 PDFs ohne extrahierbaren Text | 0 (0,0 %) | 327 (1,7 %) |
| `duesseldorf-2014` | 377 (1,7 %) | 73 ohne Hauptdatei, 26 gescheiterte Abrufe, 278 leer extrahiert | **1 655 (7,4 %)** | 2 356 (10,6 %) |
| `duesseldorf-2025` | 20 (0,5 %) | 7 ohne Hauptdatei, 13 leer extrahiert | 0 (0,0 %) | 84 (2,1 %) |
| `moenchengladbach` | **2 245 (77,5 %)** | 24 ohne Hauptdatei, **2 213 antworten mit `404`**, 8 leer extrahiert | **1 275 (44,0 %)** | 0 (0,0 %) |

Was aus welcher Quelle kommt, steht je Dokument in `papers_gremien.parquet` (Spalten `quelle`,
`folge_gremium`, `folge_anzahl`), und der Abschnitt „Gremien" nennt die Anteile in einem Satz. Wie
viel die zweite Quelle je Profil beigetragen hat — ergänzt, mehrdeutig, bestätigt, Widerspruch —
steht als eine Tabelle in [statistik.md](statistik.md), § 10, und nur dort. Die Zeile der
Gremientabelle, die früher „ohne Drucksachennummer" hieß, heißt auf den Seiten, die sie brauchen
(`2014-2020/` und `moenchengladbach/`), jetzt **„ohne erkanntes Gremium"** — in Mönchengladbach hat
jedes Dokument eine Nummer, sie sagt nur nichts.

Vier Lücken sind groß genug, um jede Deutung zu tragen:

- **Mönchengladbachs 404.** Von 2 871 Dokumenten mit Hauptdatei liefert das Ratsinformationssystem
  658 aus; die übrigen 2 213 antworten mit `404`, und warum, sagt der Server nicht. Die Seiten sagen
  es selbst: der Städtevergleich führt die Spalte „davon mit Text", und die Kachel „Dokumente mit
  Treffer" jeder Stadtseite nennt den Anteil an allen Dokumenten **und** den an denen mit Text
  (Mönchengladbach 489 von 650 = 75,2 %, nicht nur 16,9 % aller 2 895). Was die Lücke für die
  Auswertung bedeutet, steht in [statistik.md](statistik.md), § 8.
- **Mönchengladbachs Gremien.** Die Drucksachennummern tragen kein Kürzel (`0682/XI`), über alle
  2 895 bestätigt. Seit Punkt 58 kommen sie aus der Beratungsfolge: alle 2 895 tragen eine, sie nennt
  27 Organisationen, und 1 620 (56,0 %) nennen genau eine — „unbekannt" fällt von 100 % auf 1 275
  (44,0 %), und die 1 275 sind genau die, deren Folge mehrere Gremien nennt. Die Namen kommen aus
  einem Abruf von `…/bodies/0011/organizations`, der als `raw/organizations.json` im Paket der Stadt
  liegt; welche der vier nach der Himmelsrichtung benannten Bezirksvertretungen zu welchem
  Stadtbezirk gehört, ist an 167 Dokumenten belegt und nicht geraten (die Matrix steht im Profil).
- **Die Urheber der Periode 2014 bis 2020** waren bis zum 2026-10-14 zu 55,9 % unbekannt, weil ihre
  beiden häufigsten Dokumentarten (`Vorlage aus der Politik` 9 601, `Verwaltungsvorlage` 8 337,
  zusammen 80,7 %) in keiner Liste des Profils standen. Punkt 60 liest sie: `Verwaltungsvorlage` ist
  die Verwaltung, und der Briefkopf der damaligen Vorlagenform nennt die Fraktion. **„Unbekannt"
  liegt seitdem bei 2 356 (10,6 %)** — offen bleiben 2 122 Vorlagen aus der Politik ohne das Wort
  „fraktion" im Kopf (Jugendrat, Einzelmandate, Listen des Integrationsrats), 135 `Antrag`, 96
  `Anfrage` und 3 `zAnfrage Piraten`. **Die veröffentlichte Seite zeigt noch die 55,9 %.**
- **Die Urheberfelder von OParl.** Der Server füllt `originatorPerson`, `originatorOrganization` und
  `underDirectionOf` nicht — über die ganze Hauptperiode gemessen: 0 von 19 109. Der Urheber ist
  darum aus Dokumentart, Titel und Textkopf abgeleitet und deckt 98,3 % ab.

- **Mönchengladbachs Urheber** fehlten ganz, weil `[originators]` im Profil leer war und der Schritt
  `parties` darum nicht lief. Punkt 59 füllt ihn: die 16 Dokumentarten der Periode sind eindeutig
  (14 Arten mit 2 278 Dokumenten sind Verwaltung, `3 - Fraktionsantrag` mit 581 die Fraktion,
  `6.1 - Mitgliederantrag` mit 36 die Person), **„Urheber unbekannt" ist 0,0 %** — die offene Zahl
  liegt eine Ebene tiefer: nur **242 der 581 Fraktionsanträge (41,7 %) nennen ihre Partei**, weil 390
  von ihnen keinen Text tragen. Die Stadtseite wächst dadurch um 169 567 auf **819 288 Byte** — der
  Abschnitt mit sechs Parteikarten über 33 Flächen ist der größte Posten, den diese Seite je bekommen
  hat (lokal gemessen, `STATUS.md`).
  **Die veröffentlichte Seite hat den Abschnitt „Urheber und Parteien" noch nicht.**

„Unbekannt" heißt auf diesen Seiten überall **„von dieser Konfiguration nicht erkannt"**, nie „im
Dokument nicht vorhanden".

## 2. Was die Seite kann

Die Stadtseite ist **eine Datei** ohne externe Ressourcen (`index.html`, veröffentlicht 932 839 Byte
bei einem Budget von 1 000 000, also 6,7 % Luft): CSS, JavaScript und alle SVGs
inline, nur relative
Pfade, Deutsch mit englischer Kurzfassung, hell und dunkel über `prefers-color-scheme`. Daneben liegt
`karte.html` mit Leaflet und OpenStreetMap-Kacheln — die einzige Datei mit Fremdressourcen und die
einzige, die Netz braucht.

### Suche „Straße oder Ort"

Der Abschnitt [`#suche`](https://konradvoelkel.github.io/geographic-representation-dus/#suche)
durchsucht **4 063 Einträge** nach dem Combobox-Muster der WAI-ARIA Authoring Practices: Straßen
(`s`), Orte (`o`) und Wahlbezirksnamen (`w`), je mit seinen Wahlbezirken und seiner Dokumentzahl; ein
Name, der beides ist, trägt beide Marken (`benrather straße` steht als `so` da). Die
Vorschlagsliste steckt in der Seite und braucht kein Netz; abgeglichen werden Teilstrings auf zwei
gefalteten Schlüsseln (einmal ohne Akzente, einmal mit `ä` als `ae`), und die Abkürzungsregel
(`straße`/`str.`) kommt aus den Daten, nicht aus einer Sprachregel im Skript. Eine Auswahl nennt Art,
Wahlbezirke und Dokumente, markiert sie in Karte, Bezirkstabelle und Streudiagramm und schreibt die
Adresse mit:

| Adresse | zeigt |
|---|---|
| [`#suche=hofgarten`](https://konradvoelkel.github.io/geographic-representation-dus/#suche=hofgarten) | den Ort, 172 Dokumente, Wahlbezirk 1 |
| [`#suche=grafenberger%20allee`](https://konradvoelkel.github.io/geographic-representation-dus/#suche=grafenberger%20allee) | die Straße mit der höchsten Dokumentzahl (205) in den Bezirken 7, 8, 9, 10, 28 |
| [`#suche=Benrath`](https://konradvoelkel.github.io/geographic-representation-dus/#suche=Benrath) | den Wahlbezirk 39 mit seinen 811 Treffern |
| [`#suche=luegallee`](https://konradvoelkel.github.io/geographic-representation-dus/#suche=luegallee) | eine Straße in zwei Bezirken (19, 20), 97 Dokumente |

Die Adresse ist teilbar: beim Laden zeigt die Seite das Ergebnis schon.

### Dokumentdialog

Jeder Begriff auf der Seite ist eine Schaltfläche. Ein Klick lädt beim ersten Mal
`data/dokumente.json` nach und zeigt die Dokumente in einem `<dialog>` — neueste zuerst, je Zeile
Datum, Titel, Drucksache, Dokumentart, Urheber und ein Link auf das PDF im Ratsinformationssystem
(`https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/downloadfiles/<datei>.pdf`; die Datei nennt
nur das gemeinsame Präfix und je Dokument den Rest). Die Datei trägt 10 729 Dokumente und 2 999
Begriffe — also nur Begriffe mit Treffer, und nur Dokumente, die über einen **angezeigten** Begriff
getroffen werden; die zehn Dokumente, die allein an „schulweg" hängen (der zählt, wird aber nicht
angezeigt), fehlen darin. Aus `file://` geöffnet sagt die Seite, dass der Browser das Nachladen dort
nicht erlaubt.

### Karten und ihre Umschalter

Der Abschnitt [`#karte`](https://konradvoelkel.github.io/geographic-representation-dus/#karte) zeigt
die 41 Wahlbezirke als inline-SVG mit Tooltips und Klick-Markierung; die 1 196 Orte lassen sich als
Punkte dazuschalten. **Sechs Einfärbungen** stehen zur Wahl, und dieselbe Klasse färbt die
Kennzahlspalte der Bezirkstabelle mit:

| Einfärbung | Kennzahl | Skala |
|---|---|---|
| Trefferquote | Dokumente mit Treffer je Wahlberechtigtem | 5 Quantilklassen, Blau |
| Treffer absolut | Dokumente mit Treffer, ohne Nenner | 5 Quantilklassen |
| Treffer je Begriff | Dokumente je Begriff im Wörterbuch des Bezirks (Median 4,57) | 5 Quantilklassen |
| Abweichung vom Stadtmittel | Trefferquote gegen das ungewichtete Mittel aller 41 | **feste Grenzen** ±10 %, ±25 %, divergierend |
| Wahlbeteiligung | je Wahlbezirk, Kommunalwahl 14.09.2025 | 5 Quantilklassen |
| Anteil eigene Bezirksvertretung | Treffer aus der BV des eigenen Stadtbezirks, an allen Treffern | 5 Quantilklassen |

Der Abschnitt „Urheber und Parteien" hat seinen eigenen Umschalter über sechs kleine Parteikarten und
die Parteispalten der Bezirkstabelle: **Anteil** (Standard) / **Abweichung vom Mittel aller Parteien**
in Prozentpunkten / **Verhältnis zum Mittel**. Ohne JavaScript steht überall die Standardvariante da.
Die Legenden liegen in einer `aria-live`-Region.

### Die siebzehn Abschnitte in Reihenfolge

| # | Anker | Was dort steht |
|---|---|---|
| 1 | `#kernzahlen` | sieben Kacheln: Wahlbezirke, Dokumente, Suchbegriffe, Dokumente mit Treffer, Trefferquote, Treffer je Begriff, Wahlbeteiligung. Jede trägt eine zweite Zeile, und bei drei von ihnen ist das die Spannweite (Trefferquote, Treffer je Begriff, Wahlbeteiligung); die anderen nennen dort die Teilmenge (19 033 mit Text, 75 ohne) oder den Bezug. |
| 2 | `#suche` | das Suchfeld über Straßen, Orte und Wahlbezirke (oben). |
| 3 | `#karte` | die Karte der Wahlbezirke mit sechs Einfärbungen, Ortspunkten und Legende je Variante. |
| 4 | `#zusammenhang` | Streudiagramm mit beiden Regressionsgeraden, Tabelle 5 der Arbeit und dieselbe Rechnung je Begriff im Wörterbuch. Seit Punkt 61 (auf `main`, noch nicht veröffentlicht) trägt die Spalte „ohne Ausreißer" im Kopf das Wort **„explorativ"**, und darunter steht in zwei Sätzen, dass sie nach dem Ansehen der Daten entstanden ist und in der Periode 2014 bis 2020 nicht signifikant ist. |
| 5 | `#kontrollvariablen` | Tabelle 6 in drei Modellen, partielle Streudiagramme je Term und Tabelle 6b mit je einer Kontrollvariable. |
| 6 | `#gewichtung` | 26 Gewichtungsvarianten, je mit beiden Spalten von Tabelle 5 und der Rangkorrelation zur ungewichteten Quote, darunter die Themen mit ihren stärksten Wörtern. |
| 7 | `#perioden` | die Wahlperiode 2014 bis 2020 daneben: Regression der Änderungen, Regression jener Periode, und wie belastbar die Umrechnung der alten Wahlzahlen ist. |
| 8 | `#parteien` | sechs kleine Karten je Partei mit Umschalter, Tabelle je Partei mit dem Abgleich zum Stimmenanteil samt Bonferroni-Grenze, Tabelle je Wahlbezirk mit den Urheberklassen. |
| 9 | `#wahlbezirke` | die sortierbare Tabelle aller 41 Bezirke: Name, Begriffe, Treffer, Kennzahl, Wahlberechtigte, Wahlbeteiligung. |
| 10 | `#gremien` | Treffer nach Gremium (Bezirksvertretung, Rat, Ausschuss, Beirat, ohne erkanntes Gremium), je Wahlbezirk aufgeschlüsselt, dazu „Dokumente je passendem Ausschuss" aus dem Klassifikator. Seit Punkt 58 nennt der Abschnitt **beide Quellen** des Gremiums mit Zahlen: wie viele Dokumente ihr Gremium aus der Drucksachennummer haben, wie viele aus der Beratungsfolge, wie oft die beiden übereinstimmen oder sich widersprechen, und wie viele mehrdeutig bleiben. |
| 11 | `#begriffe` | die 20 trefferstärksten Begriffe stadtweit, die 55 stadtweiten Begriffe über dem 99-%-Quantil, und je Wahlbezirk seine Begriffsliste (nachgeladen). |
| 12 | `#monate` | zwei Balken je Monat (alle Dokumente, die mit Treffer) über 61 Monate, mit Tabelle. |
| 13 | `#methode` | Verfahren in Prosa, die beiden eigenen Methodikregeln, die Grenzen, und der Absatz zur Größe des Wörterbuchs mit seinen Korrelationen. |
| 14 | `#abgeleitete-daten` | je Kontrollvariable, aus welchem Indikator des Quartiersatlas sie entsteht und wie sie umgerechnet wird. |
| 15 | `#literatur` | fünfzehn Einträge mit vollständiger Zitation und einem Satz zum Beitrag; zwei Lücken stehen sichtbar als „nachzutragen". |
| 16 | `#downloads` | 53 Zeilen mit Format, Zeilenzahl, Größe, Beschreibung und SHA-256. |
| 17 | `#laufend` | ein Verweis auf die Unterseite der laufenden Wahlperiode. |

Lange Tabellen zeigen Kopf und drei Zeilen (`report.table_preview_rows`) und klappen über „alle *n*
Zeilen zeigen" auf; im Druck und ohne JavaScript steht alles offen, und eine Zeile, die aus Karte,
Streudiagramm oder Suche markiert wird, klappt von allein auf. Offen bleiben die Kernzahlen und die
Tabellen 5, 6 und 6b — sie sind der Befund.

### Downloads

Unter `data/` liegen neben jeder Seite **24 Ergebnistabellen als Parquet und als CSV** plus fünf
weitere Dateien, zusammen 53 Zeilen in der Download-Tabelle; Parquet trägt Typen und Listen und ist
das primäre Format, CSV verbindet Listen mit „; ", GeoJSON ist EPSG:4326. Größe und SHA-256 jeder
Datei stehen auf der Seite.

| Datei | Was |
|---|---|
| [`data/schema.json`](https://konradvoelkel.github.io/geographic-representation-dus/data/schema.json) | je Tabelle eine Liste von Spalten mit `column`, `dtype`, `description`, `unit` — das maschinenlesbare Spaltenschema, 25 Einträge (24 Tabellen plus `wahlbezirke`). |
| [`data/summary.json`](https://konradvoelkel.github.io/geographic-representation-dus/data/summary.json) | die Schnittstelle der Stadtseite: `city`, `stand`, `figures` (Bezirke, Stimmbezirke, Dokumente, mit Text, mit Treffer, Begriffe, Quote als Median/Min/Max, Wahlbeteiligung als Median), `regression` mit beiden Spalten von Tabelle 5, `version`, `generated_at`. Daraus baut `georep publish` den Städtevergleich. |
| [`data/begriffe.json`](https://konradvoelkel.github.io/geographic-representation-dus/data/begriffe.json) | je Wahlbezirk `[Begriff, Dokumente]` absteigend, 41 Einträge; wird beim Aufklappen einer Begriffsliste nachgeladen. |
| [`data/dokumente.json`](https://konradvoelkel.github.io/geographic-representation-dus/data/dokumente.json) | 10 729 Dokumente als Feldlisten (`link, datum, drucksache, titel, art, urheber`) plus je Begriff die Indizes darauf; wird beim ersten Klick auf einen Begriff nachgeladen. |
| [`data/wahlbezirke.geojson`](https://konradvoelkel.github.io/geographic-representation-dus/data/wahlbezirke.geojson) | die 41 Wahlbezirksflächen in EPSG:4326. |

Die 24 Tabellen, nach Thema: **Auswertung** (`wahlbezirke_auswertung`, `wahlbezirke_kennzahlen`),
**Wörterbuch und Index** (`combined_searchdict`, `inverted_index`, `wahlbezirke_strassen`,
`wikidata_vis`), **Wahl** (`wahlbezirke_waehler`, `wahlbezirke_stadtbezirke`), **Gremien**
(`wahlbezirke_gremien`, `gremien`, `ausschuss_zuordnung`), **Gewichtung und Themen**
(`wahlbezirke_gewichtet`, `gewichte_begriffe`, `themen`, `themen_dokumente`), **Kontrollvariablen**
(`wahlbezirke_kontext`, `wahlbezirke_crosswalk`, `regression_kontrollen`), **Urheber**
(`dokumente_urheber`, `wahlbezirke_urheber`, `wahlbezirke_parteien`), **Zeit und Vergleich**
(`monatsreihe`, `wahlbezirke_monate`, `wahlbezirke_vergleich`).

Welche Tabelle eine Seite hat, hängt daran, welche Schritte ihr Profil hat — die Schritte je Profil
stehen in [technik.md](technik.md), § 4. Praktisch heißt das: Mönchengladbach hat keine
Kontrollvariablen, die laufende Periode keine Regression, und `stimmbezirke_zuordnung` (die
Umrechnung der Wahlzahlen von 2020) liegt nur unter
[`2014-2020/data/`](https://konradvoelkel.github.io/geographic-representation-dus/2014-2020/data/stimmbezirke_zuordnung.parquet),
nicht an der Wurzel.

## 3. Die Unterseiten

| Seite | Abschnitte | was fehlt und warum |
|---|---|---|
| [Wurzel](https://konradvoelkel.github.io/geographic-representation-dus/) (Düsseldorf 2020–2025) | alle siebzehn | — |
| [`2014-2020/`](https://konradvoelkel.github.io/geographic-representation-dus/2014-2020/) | 13: kernzahlen, suche, karte, zusammenhang, gewichtung, parteien, wahlbezirke, gremien, begriffe, monate, methode, literatur, downloads | kein `kontrollvariablen` und `abgeleitete-daten` (die Fremddaten liegen auf dem Zuschnitt 2021 der Hauptperiode), kein `perioden` (eine Periode verglicht sich nicht mit sich selbst), kein `laufend` |
| [`2025/`](https://konradvoelkel.github.io/geographic-representation-dus/2025/) | 11: kernzahlen, suche, karte, parteien, wahlbezirke, gremien, begriffe, monate, methode, literatur, downloads | **kein `zusammenhang`**: zu einer laufenden Periode gibt es keine Wahlbeteiligung, also keine Regression, kein Streudiagramm, keinen Umschalter darauf — Kopf und Kurzfassung sagen, warum; auch keine Gewichtungstabelle |
| [`moenchengladbach/`](https://konradvoelkel.github.io/geographic-representation-dus/moenchengladbach/) | 12, seit Punkt 59 auf `main` 13: kernzahlen, suche, karte, zusammenhang, gewichtung, (parteien), wahlbezirke, gremien, begriffe, monate, methode, literatur, downloads | keine Kontrollvariablen (die Stadt hat keine Fremddaten im Profil), **keine „Dokumente je passendem Ausschuss"** (`classify.enabled = false`: nur 650 von 2 895 Dokumenten tragen Text). `parteien` fehlt der **veröffentlichten** Seite noch und kommt mit Punkt 59 |
| [`vergleich.html`](https://konradvoelkel.github.io/geographic-representation-dus/vergleich.html) | vier: Die Städte nebeneinander, Trefferquote je Wahlbezirk, Trefferquote und Wahlbeteiligung, Vergleichbarkeit | eine eigene Seite, 89 597 Byte; sie rechnet nichts selbst, sondern liest die `summary.json` der Stadtseiten; kein Suchfeld und keine Downloads |

Größen der **veröffentlichten** Dateien (am 2026-10-14 abgerufen, Commit `813827e`): Hauptseite
932 839, `2014-2020/` 820 071, `2025/` 718 207, `moenchengladbach/` 649 612, `vergleich.html`
89 597 Byte. (`STATUS.md` nennt für dieselben Seiten Zahlen, die um wenige Byte abweichen: dort sind
sie lokal vor dem Hochladen gemessen, und Commit und Zeitstempel im Fuß unterscheiden sich.)
Mönchengladbach wuchs mit Punkt 58 um 8 056 Byte, weil seine Gremientabelle jetzt 27 Zeilen hat
statt einer, und schrumpfte wieder um 1 294, als seine Themen ihre Ausschussnamen verloren.

**Mönchengladbach sät seit Punkt 58 keine Themen** (`topics.seed = "none"`): mit der Saat bekamen acht
Ausschüsse ein eigenes Thema, gesät aus 11 bis 21 Dokumenten mit Text, und ihre Namen standen danach
als Zeilen in der Sensitivitätstabelle. Das sah nach einer Zuordnung aus, die 650 Texte aus 2 895
Dokumenten nicht tragen; die Themen dieser Stadt heißen darum wieder nach ihren Wörtern, nicht nach
einem Ausschuss. Die Themen Düsseldorfs sind unberührt.

Die Hauptseite verlinkt `2025/` im Abschnitt „Laufende Wahlperiode", `2014-2020/` im Abschnitt „Zwei
Wahlperioden" und die weiteren Städte in der Zeile „Weitere Städte", die erst `georep publish` in die
kopierte Seite setzt.

**Der Städtevergleich sagt seine eigenen Grenzen.** Die beiden kleinen Karten teilen die
Klassengrenzen (dieselbe Farbe heißt in jeder Stadt dieselbe Quote), sind aber nicht maßstabsgleich.
Der Abschnitt „Vergleichbarkeit" nennt je Stadt die Wahlberechtigten je Bezirk, die Spalte „davon
mit Text" und den Satz, dass die Absolutwerte einer Stadt mit großer Textlücke nicht mit denen der
anderen zu vergleichen sind; die Zahlen dazu und was sie tragen, stehen in
[statistik.md](statistik.md), § 8.

## 4. Lizenzen

| Was | Lizenz |
|---|---|
| Quelltext | GPL-3.0-or-later (seit `v0.11.0`, 2026-10-12; davor CC0 1.0 wie das Original) |
| Ergebnisse, Tabellen, Berichtsseite | CC0 1.0 |
| Wahlergebnisse (Düsseldorf) | dl-de/by-2-0 |
| Stimmbezirksgeometrie (Düsseldorf, Mönchengladbach) | dl-de/zero-2-0 |
| Quartiersatlas 2024 | dl-de/by-2-0, Namensnennung: Landeshauptstadt Düsseldorf, Amt für Statistik und Wahlen |
| Straßennamen | ODbL, © OpenStreetMap-Mitwirkende |
| Orte | Wikidata CC0, Artikeltitel der deutschsprachigen Wikipedia |
| votemanager-CSVs (Mönchengladbach) | **laut Anbieter nicht angegeben**; die Seite nennt Quelle und Herausgeber |
| Ratsdokumente über OParl | kein Lizenzhinweis am Endpunkt; **veröffentlicht werden keine Texte**, nur abgeleitete Tabellen und Kennungen |
