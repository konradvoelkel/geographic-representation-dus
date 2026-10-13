# Skalierung der Kennzahlen (2026-10-13)

Auftrag: `docs/todo.md`, Punkt 3. Konrad will auf den Parteikarten nicht sehen, *wo* SPD oder AfD viel über
Wahlbezirke reden, sondern *wie viel mehr oder weniger als der Durchschnitt aller Parteien*; dasselbe gilt
für die anderen Kennzahlen der Seite (Bartzsch normiert auf die Wahlberechtigten). Gewünscht ist je Kennzahl
eine Auswahl „absolut / je Wahlberechtigte / relativ zum Durchschnitt", und zuerst ein Konzept.

Dieses Dokument nimmt alle Kennzahlen der Berichtsseite auf (§ 1), nennt je Kennzahl die möglichen
Normierungen mit ihrer Lesart, ihrer Blindstelle, ihren Klassengrenzen und ihrer Farbskala (§ 2 bis § 4) und
entscheidet, welche Varianten gebaut werden und welche nicht (§ 5). Die Entscheidung steht als Punkt 46 in
`docs/decisions.md`; die Umsetzung beschreibt `docs/architecture.md`, „Berichtsseite".

Alle Zahlen sind am 2026-10-13 auf der Referenz gemessen (41 Wahlbezirke, 19 108 Dokumente, 5727 Begriffe,
29 010 Treffer; Regel 1 an, `docs/decisions.md`, Punkt 44a). Nachrechnen: die Spalten der beiden neuen
Tabellen `wahlbezirke_kennzahlen` und `wahlbezirke_parteien` stehen zum Download, und
`tests/golden/test_pipeline.py` friert die Kennzahlen des Referenzlaufs ein.

## 1. Inventar: jede Kennzahl der Seite mit Zähler und Nenner

Zähler und Nenner stehen so da, wie die Seite sie heute rechnet. „Bedeutung" ist der Satz, den ein Leser aus
der Zahl mitnimmt; „Nenner" leer heißt: es ist eine Zählung, keine Quote.

### 1.1 Kernzahlen (Abschnitt `10-kernzahlen`)

| Kennzahl | Zähler | Nenner | Bedeutung |
|---|---|---|---|
| Wahlbezirke (41) | Gebiete des Wahlergebnisses | — | Größe der Grundgesamtheit |
| Ratsdokumente (19 108) | Paper der Wahlperiode | — | Größe des Korpus |
| Suchbegriffe (5727) | Begriffe aller Wörterbücher, verschieden | — | Größe des Wörterbuchs, stadtweit |
| Dokumente mit Treffer (10 739) | Dokumente mit mindestens einem Treffer irgendwo | 19 108 Dokumente (als Anteil in der Unterzeile) | wie viel des Korpus die Methode überhaupt erreicht |
| Trefferquote, Median (0,0604) | Treffer des Bezirks | Wahlberechtigte des Bezirks | die Kennzahl der Arbeit, mittlerer Bezirk |
| Wahlbeteiligung, Median (54,0 %) | Wähler | Wahlberechtigte | die Zielgröße der Regression |

### 1.2 Karte (Abschnitt `20-karte`)

| Einfärbung | Zähler | Nenner | Bedeutung |
|---|---|---|---|
| Trefferquote (Standard) | Treffer | Wahlberechtigte | Dokumente je Person |
| Wahlbeteiligung | Wähler | Wahlberechtigte | Beteiligung |
| Anteil eigene Bezirksvertretung (Option 05) | Treffer aus der BV des eigenen Stadtbezirks | alle Treffer des Bezirks | wie lokal die Aufmerksamkeit erzeugt wird |

### 1.3 Tabelle je Wahlbezirk (Abschnitt `40-wahlbezirke`)

| Spalte | Zähler | Nenner | Bedeutung |
|---|---|---|---|
| Treffer | Dokumente mit mindestens einem Treffer im Bezirk | — | **Rohgröße, an der alles hängt** |
| Wahlberechtigte, Wähler | Personen | — | Größe des Bezirks |
| Wahlbeteiligung | Wähler | Wahlberechtigte | Beteiligung |
| Trefferquote | Treffer | Wahlberechtigte | Dokumente je Person |
| Begriffe | Begriffe im Wörterbuch des Bezirks | — | **die Größe, die die Treffer erklärt (r = 0,7595)** |
| häufigste Begriffe | Dokumente je Begriff | — | woher die Treffer kommen |

### 1.4 Parteien (Abschnitt `38-parteien`)

| Kennzahl | Zähler | Nenner | Bedeutung |
|---|---|---|---|
| sechs Karten, Zelle | Dokumente der Partei mit Treffer im Bezirk | alle Dokumente der Partei | wohin diese Partei blickt |
| je Partei: Dokumente, davon allein | Dokumente | — | Umfang der Partei |
| je Partei: Treffer | Summe über die Bezirke | — | Aufmerksamkeit, mehrfach gezählt |
| je Partei: r, p | Anteil je Bezirk gegen Stimmenanteil | — | Hochburg-Abgleich |
| je Bezirk: Urheberklassen | Treffer je Klasse | — | wer die Treffer erzeugt (Partition) |
| je Bezirk: Parteispalten | wie die Karten | wie die Karten | dieselbe Zahl exakt |

### 1.5 Gremien (Abschnitt `45-gremien`)

| Kennzahl | Zähler | Nenner | Bedeutung |
|---|---|---|---|
| Kacheln je Art | Dokumente der Art | 19 108 Dokumente (Unterzeile) | Mischung des Korpus |
| je Bezirk: eigene BV | Treffer aus der eigenen BV | alle Treffer des Bezirks (in Klammern) | **schon normiert** |
| je Bezirk: Quote | Treffer aus der eigenen BV | Wahlberechtigte | **schon normiert, zweiter Nenner** |
| je Gremium: Lokalität | Treffer in Bezirken des eigenen Stadtbezirks | alle Treffer des Gremiums | **schon normiert** |
| Ausschuss-Zuordnung | Dokumente je Ausschuss | alle Dokumente (Spalte „Anteil") | **schon normiert** |

### 1.6 Gewichtung (Abschnitt `34-gewichtung`)

| Kennzahl | Zähler | Nenner | Bedeutung |
|---|---|---|---|
| Summe | gewichtete Treffer über alle Bezirke | — | wie stark die Gewichtung dämpft |
| n, Steigung, Achsenabschnitt, r, R², p | Regression je Variante | — | hängt der Befund an der Kennzahl? |
| ρ | Rang der gewichteten gegen die ungewichtete Quote | — | **schon skalenfrei** |

### 1.7 Monate (Abschnitt `55-monate`)

| Kennzahl | Zähler | Nenner | Bedeutung |
|---|---|---|---|
| Dokumente, mit Text, mit Treffer je Monat | Dokumente | — | Rhythmus des Rates; der Anteil „mit Treffer" steht als zweiter Balken daneben |

### 1.8 Kontrollvariablen (Abschnitte `32-kontrollvariablen`, `65-abgeleitete-daten`)

| Kennzahl | Zähler | Nenner | Bedeutung |
|---|---|---|---|
| Koeffizient | Einheiten der Zielgröße je Einheit des Terms | — | Wirkung in Originaleinheiten |
| standardisiert (β) | Koeffizient × σ(x) | σ(y) | **die Normierung der Regression; schon da** |
| VIF, R², F-p | Modellgüte | — | Verlässlichkeit |
| Kontextvariablen | je Variable eigen (Anteile, Jahre, Punkte) | — | aus dem Quartiersatlas, schon Anteile |

### 1.9 Begriffe (Abschnitt `50-begriffe`)

| Kennzahl | Zähler | Nenner | Bedeutung |
|---|---|---|---|
| Dokumente je Begriff | Dokumente mit dem Begriff | — | Gewicht eines einzelnen Begriffs; die Schwelle der stadtweiten Begriffe ist die Offenlegung dazu (Punkt 44b) |

**Befund des Inventars.** Von den 35 Zeilen dieses Inventars tragen 16 schon einen Nenner, und sechs sind
Modell- oder Güteangaben, für die eine zweite Normierung nichts bedeutet. Offen sind genau zwei Stellen, und
beide sind die, über die Konrad gestolpert ist: **die Treffer je Wahlbezirk** (Karte, Tabelle, Kernzahlen) und
**die Parteianteile** (sechs Karten, zwei Tabellen).

## 2. Die vier Normierungen und was sie taugen

### 2.1 Absolut

Treffer, wie sie gezählt werden. **Lesart:** „In 1761 Dokumenten kommt ein Ort des Wahlbezirks 1 vor."
**Verdeckt:** dass ein Bezirk mehr Treffer hat, weil sein Wörterbuch größer ist. Gemessen am 2026-10-13:
Treffer gegen Begriffe r = **0,7595**, Treffer gegen Wahlberechtigte r = 0,1734 (das Review hatte 0,767 und
0,176 ohne Regel 1, `docs/methodik-review-2026-10.md`, § 1).
**Nicht dasselbe wie die Quote:** Pearson r(Treffer, Quote) = 0,9769 und Spearman ρ = 0,9353 sind hoch, aber
die Quantilklassen der beiden Varianten unterscheiden sich in **17 der 41 Bezirke** (3, 4, 7, 8, 9, 13, 15, 17,
18, 22, 23, 25, 31, 36, 37, 39, 40). Die Rohzählung ist also eine eigene Karte, keine Wiederholung.
**Klassen:** fünf Quantile, wie heute. **Skala:** sequenziell (die vorhandene Blau-Rampe `--q0` bis `--q4`).

### 2.2 Je 1000 Wahlberechtigte (Bartzsch)

Treffer geteilt durch Wahlberechtigte, mal 1000. **Lesart:** „Auf 1000 Wahlberechtigte des Bezirks kommen
60 Dokumente." **Verdeckt:** dasselbe wie „absolut" — die Trefferquote korreliert mit der Wörterbuchgröße mit
r = 0,7060. **Wichtig:** gegenüber der heutigen Trefferquote ist „je 1000" **nur ein Faktor**, kein
Perspektivwechsel: die Klassen, die Rangfolge und die Farbe jeder Fläche sind **identisch**, allein die Zahlen
der Legende werden mit 1000 multipliziert. Und gegenüber der rohen Zählung nimmt die Normierung wenig heraus,
weil die Wahlberechtigten nur um den Faktor 1,287 schwanken (10 168 bis 13 086): Pearson r(Treffer, Quote)
= 0,9769, Spearman ρ = 0,9353.
**Klassen:** fünf Quantile. **Skala:** sequenziell. Der Faktor 1000 ändert nur die Zahlen der Legende
(60,4 statt 0,0604), nicht die Karte.

### 2.3 Je Begriff im Wörterbuch (Empfehlung des Methodik-Reviews)

Treffer geteilt durch die Zahl der Begriffe im Wörterbuch des Bezirks. **Lesart:** „Ein Ort des Wahlbezirks
wird im Schnitt in 4,6 Dokumenten besprochen." Das ist die Kennzahl, die § 2.6 des Methodik-Reviews als
stärksten offenen Punkt nennt, weil die Wörterbuchgröße 58 % der Varianz der Treffer erklärt (r = 0,7595,
R² = 0,5768; das Review hatte 59 % ohne Regel 1).
**Was sie zeigt:** eine andere Stadt. Gemessen: Median 4,5656, Spannweite **2,2485** (Bezirk 24: 371 Treffer
auf 165 Begriffe) bis **9,5472** (Bezirk 10, Flingern: 1012 Treffer auf 106 Begriffe). Die Rangfolge kippt:
die fünf stärksten Bezirke sind nach Quote 1, 10, 2, 30, 28 und nach Treffer je Begriff **10, 15, 7, 3, 9**.
Bezirk 1, der Ausreißer der Arbeit, fällt von Platz 1 auf Platz 40; Bezirk 3, der kleinste Wörterbuchbezirk,
steigt von Platz 27 auf Platz 4.
**Verdeckt:** die Größe des Bezirks (kein Nenner aus Personen) und die Qualität des Wörterbuchs — ein Bezirk
mit 77 Begriffen, von denen einer eine Hauptverkehrsstraße ist, bekommt einen hohen Wert aus einem einzigen
Begriff. Die Kennzahl ist gegen die Wörterbuchgröße überkorrigiert: r(Treffer je Begriff, Begriffe) = **−0,5109**.
Sie ist also nicht die „richtige" Kennzahl, sondern die Gegenprobe zur Quote.
**Klassen:** fünf Quantile (2026-10-13: 3,34 / 4,29 / 4,88 / 6,23); sie weichen in **28 der 41 Bezirke** von
den Klassen der Trefferquote ab — die stärkste Umordnung aller Varianten. **Skala:** sequenziell.

### 2.4 Relativ zum Durchschnitt

Der Wert geteilt durch (oder minus) den Durchschnitt der Vergleichsgruppe. Zwei Vergleichsgruppen kommen vor:
bei Wahlbezirken **das Stadtmittel**, bei Parteien **das Mittel aller Parteien im selben Wahlbezirk**.

**Lesart:** „Dieser Bezirk liegt 45 % über dem Stadtmittel", „diese Partei nennt diesen Bezirk um 1,2
Prozentpunkte häufiger als der Durchschnitt aller sechs Parteien".
**Verdeckt:** das Niveau. Zwei Bezirke mit derselben Abweichung können 300 oder 1700 Treffer haben; die
Variante braucht die Spalte mit der Rohzahl daneben, und sie bekommt sie (die Tabellen zeigen immer beide).

**Mittel heißt ungewichtetes Mittel der Einheiten.** Diese Regel gilt in diesem Repo einheitlich: das
Stadtmittel ist das Mittel der 41 Bezirksquoten, das Parteimittel das Mittel der sechs Parteianteile.
Begründung je Fall in § 3.1 und § 4.1.

**Divergierend heißt auch: feste Grenzen, keine Quantile.** Eine Abweichung vom Mittel ist bei den
Wahlbezirken eine streng monotone Umrechnung der Quote — Quantilklassen darüber wären *dieselben* Klassen wie
die der Quote, nur anders gefärbt, und die Variante zeigte nichts Neues. Darum bekommen die divergierenden
Varianten **feste, um die Mitte symmetrische Grenzen**. Die mittlere Klasse ist die um das Mittel; ihre
Beschriftung nennt wie jede andere ihren Bereich („−10 % bis unter +10 %"), und der Begleitsatz der Legende
sagt dazu „etwa im Mittel" — eine Klasse, deren Label die Zahlen verschweigt, wäre schlechter lesbar.
**Skala:** divergierend, in beide Richtungen vom neutralen Mittelton weg (§ 6).

### 2.5 Was nicht geht

- **Log-Verhältnis** (`docs/todo.md` nennt es als Möglichkeit): fällt weg. 20 der 246 Parteizellen sind
  exakt 0 (vor allem die AfD, die 41 Bezirke mit 183 Dokumenten bedient), und der Logarithmus von 0 ist
  keine Zahl. Ein Ersatz (`log(x + ε)`) macht die Klassengrenzen von ε abhängig. Das Verhältnis selbst
  bleibt, mit log-symmetrischen Grenzen (0,5 / 0,8 / 1,25 / 2,0): das ist die Lesbarkeit des Logarithmus
  ohne seinen Definitionslücken.
- **Je Einwohner** (Alternative (c) in § 2.6 des Reviews): keine Daten. `wahlbezirke_kontext` trägt
  ausschließlich Anteile und Punktwerte (`anteil_65plus`, `mindestsicherung`, `hb_score` …), keine
  Bevölkerungszahl je Wahlbezirk. Eine Einwohnerzahl wäre ein neuer Abruf und machte die Hauptkarte von
  optionalen Fremddaten abhängig.
- **Je Fläche**: misst Dichte, nicht Repräsentation (Review, § 2.6 (b)).

## 3. Die Wahlbezirke

### 3.1 Welches Stadtmittel

| Kandidat | Wert (2026-10-13) | Entscheidung |
|---|---|---|
| ungewichtetes Mittel der 41 Bezirksquoten | 0,061808 | **gewählt** |
| gepoolt: Summe der Treffer / Summe der Wahlberechtigten | 0,061759 | verworfen |
| Median der 41 Quoten | 0,060404 | verworfen |

Die beiden Mittel unterscheiden sich um den Faktor **1,0008** — die Wahl ist für die Zahlen gleichgültig und
wird darum nach der Regel entschieden, nicht nach dem Ergebnis: ein Wahlbezirk ist eine Einheit, nicht eine
Menge Personen, und die Frage lautet „wie steht dieser Bezirk zu den anderen 40", nicht „zu allen
Wahlberechtigten der Stadt". Der Median wäre robuster, ist aber kein *Mittel*; der Ausreißer Bezirk 1 soll
in der Vergleichsgröße stehen, weil die Karte ihn zeigt.

### 3.2 Die Varianten der Karte und der Tabelle

| Variante | Formel | Klassengrenzen | Skala |
|---|---|---|---|
| Trefferquote (**Standard, unverändert**) | Treffer / Wahlberechtigte | fünf Quantile | sequenziell `--q0`…`--q4` |
| Treffer absolut | Treffer | fünf Quantile | sequenziell |
| Treffer je Begriff | Treffer / Begriffe | fünf Quantile | sequenziell |
| Abweichung vom Stadtmittel | (Quote / Stadtmittel − 1) in Prozent | fest: −25 %, −10 %, +10 %, +25 % | **divergierend** `--d0`…`--d4` |

Verteilung der Abweichung (41 Bezirke): Minimum **−57,8 %** (Bezirk 38), Median −2,3 %, Maximum **+144,8 %**
(Bezirk 1). Mit den festen Grenzen füllen sich die fünf Klassen mit **6, 12, 11, 8, 4** Bezirken; die mittlere
Klasse („±10 % um das Stadtmittel") trägt 11 Bezirke. Zwei weitere Grenzensätze sind gemessen und verworfen:
±20 % (9 / 26 / 6 über drei Klassen) und ±15 % (14 / 18 / 9) — beide drängen zu viel in die Randklassen.

Die Wahlbeteiligung und der Anteil der eigenen Bezirksvertretung bleiben, wie sie sind: die erste ist die
Zielgröße und schon ein Anteil, die zweite ist schon ein Anteil an den Treffern des Bezirks.

### 3.3 Der zweite Zusammenhang (Abschnitt `30-zusammenhang`)

Tabelle 5 bleibt unverändert. Daneben kommt dieselbe Regression mit x = Treffer je Begriff im Wörterbuch,
gerechnet mit `regression_pair(…, x=…)`:

| Regression | n | Steigung | Achsenabschnitt | r | R² | p |
|---|---|---|---|---|---|---|
| Trefferquote, alle (Tabelle 5) | 41 | 79,9539 | 48,1709 | 0,1891 | 0,0358 | 0,23641 |
| Trefferquote, ohne 1 und 10 | 39 | 216,2416 | 40,5715 | 0,3351 | 0,1123 | 0,03705 |
| **Treffer je Begriff, alle** | 41 | **−0,5570** | **55,7576** | **−0,1118** | **0,0125** | **0,48644** |
| **Treffer je Begriff, ohne 1 und 10** | 39 | **−0,2400** | **54,4333** | **−0,0419** | **0,0018** | **0,80000** |

**Deutung, die auf die Seite gehört:** mit der Kennzahl, die die größte Verzerrung der Methode herausnimmt,
bleibt vom Zusammenhang nichts — nicht einmal das Vorzeichen. p geht von 0,24 auf 0,49, und ohne die beiden
Ausreißer von 0,037 auf 0,80: **die einzige „signifikante" Spalte der Arbeit verschwindet, sobald die
Wörterbuchgröße herausgerechnet ist.** Das stützt den Befund der Arbeit (kein Zusammenhang) und entkräftet
gleichzeitig ihre zweite Spalte. Zusammen mit Tabelle 6 (Kontrollvariablen, R² 0,89 ohne Beitrag der Quote,
`docs/decisions.md`, Punkt 26) ist das die dritte unabhängige Prüfung mit demselben Ergebnis.

## 4. Die Parteien

### 4.1 Ungewichtetes oder gewichtetes Parteimittel

Das Mittel aller Parteien je Wahlbezirk kann der ungewichtete Durchschnitt der sechs Parteianteile sein oder
der nach Dokumentzahl gewichtete (Summe der Treffer aller Parteien / Summe ihrer Dokumente).

| Größe (2026-10-13, 246 Zellen) | Wert |
|---|---|
| Mittel der ungewichteten Bezirksmittel | 0,023878 |
| Mittel der gewichteten Bezirksmittel | 0,028906 |
| größter Abstand beider Mittel in einem Bezirk | 1,44 Prozentpunkte |
| Korrelation der Abweichungen (Pearson / Spearman) | 0,9696 / 0,9757 |
| Zellen, deren Abweichung das Vorzeichen wechselt | **29 von 246 (11,8 %)** |

**Entschieden: ungewichtet, und die Alternative wird verworfen, nicht als Schalter gebaut.** Drei Gründe:

1. **Die Frage ist ungewichtet gestellt.** „Mehr oder weniger als der Durchschnitt aller Parteien" heißt:
   jede Partei ist eine Stimme. Das gewichtete Mittel ist der Durchschnitt aller *Dokumente*, und das ist
   eine andere Frage.
2. **Das gewichtete Mittel messen die großen Fraktionen an sich selbst.** Es enthält die eigenen Dokumente
   jeder Partei mit deren Gewicht; die GRÜNEN (2308 Dokumente), die CDU (2140) und die SPD (2107) setzen es
   fast allein, die AfD (183) gar nicht. Folge: wer das Mittel setzt, weicht von ihm kaum ab, und das
   Vorzeichen der Abweichung kippt bei genau diesen Parteien — **18 der 29 Vorzeichenwechsel treffen SPD
   (10) und CDU (8)**, nur einer die AfD.
3. **Ein Schalter kostet mehr als er trägt.** Er wäre ein Settings-Schlüssel (und damit ein neuer
   Fingerprint für alle Schritte), eine zweite Spalte in `wahlbezirke_parteien`, eine zweite Legende und ein
   Satz Erklärung — für eine Größe, die mit ρ = 0,976 fast dasselbe ordnet und bei der die Abweichung vom
   gewichteten Mittel schwerer zu erklären ist. Wer sie trotzdem will, rechnet sie in einer Zeile aus der
   veröffentlichten Tabelle: `anzahl_treffer.sum() / dokumente_partei.sum()` je Bezirk.

### 4.2 Die drei Varianten

| Variante | Formel je Zelle (Bezirk × Partei) | Klassengrenzen | Skala |
|---|---|---|---|
| Anteil (**Standard, unverändert**) | Dokumente der Partei mit Treffer / alle Dokumente der Partei | fünf Quantile, **je Partei eigen** | sequenziell `--q0`…`--q4` |
| Abweichung vom Mittel | Anteil − Mittel der sechs Anteile im Bezirk, in Prozentpunkten | fest: −2, −0,5, +0,5, +2 pp, **gemeinsam für alle sechs Karten** | **divergierend** |
| Verhältnis zum Mittel | Anteil / Mittel der sechs Anteile im Bezirk | fest: 0,5, 0,8, 1,25, 2,0, **gemeinsam** | **divergierend** |

Die Standardvariante behält die Klassen je Partei: die größte Fraktion stellt 2308, die kleinste 183
Dokumente, und eine gemeinsame Skala der Anteile hätte die AfD überall in der untersten Klasse (so steht es
heute im Abschnitt). **Die beiden neuen Varianten brauchen das Gegenteil:** Abweichungen und Verhältnisse
sind in derselben Einheit gegen dieselbe Bezugsgröße gemessen, also über die sechs Karten vergleichbar — und
genau diese Vergleichbarkeit ist der Zweck. Gemeinsame Grenzen sind hier nicht nur erlaubt, sie sind die
Aussage.

Verteilungen (246 Zellen, 2026-10-13):

- **Abweichung in Prozentpunkten:** Minimum −4,75, Median +0,05, Maximum +4,78. Mit −2 / −0,5 / +0,5 / +2
  füllen sich die Klassen mit **23 / 67 / 64 / 72 / 20**. Verworfen: ±1,5 pp (41 / 49 / 64 / 56 / 36, zu viel
  an den Rändern), ±0,75 pp (96 in der Mitte, zu stumpf).
- **Verhältnis:** Minimum 0,000 (20 Zellen), Median 1,048, Maximum 2,354. Mit 0,5 / 0,8 / 1,25 / 2,0 füllen
  sich die Klassen mit **61 / 32 / 60 / 78 / 15**. Die Grenzen sind log-symmetrisch (1/2, 1/1,25, 1,25, 2),
  die Mitte („0,80× bis unter 1,25×") heißt im Begleitsatz der Legende „etwa im Mittel".
- **Vertrag:** die Abweichungen summieren sich je Wahlbezirk auf 0 (gemessen: größter Betrag der Summe
  2,8 · 10⁻¹⁵). Das ist die Prüfung, dass das Mittel wirklich das Mittel dieser sechs Zahlen ist.

### 4.3 Was die Varianten über die Parteien sagen

Die Tabelle je Partei bekommt eine Spalte, die mit der Variante wechselt: das Mittel der 41 Bezirkswerte.

| Partei | Dokumente | Anteil im Mittel | Abweichung im Mittel | Verhältnis im Mittel |
|---|---|---|---|---|
| GRÜNE | 2308 | 3,57 % | **+1,19 pp** | **1,59** |
| CDU | 2140 | 3,28 % | +0,90 pp | 1,33 |
| FDP | 879 | 2,65 % | +0,26 pp | 0,97 |
| SPD | 2107 | 2,61 % | +0,22 pp | 1,21 |
| Die Linke | 792 | 1,32 % | −1,07 pp | 0,57 |
| AfD | 183 | 0,89 % | **−1,49 pp** | **0,32** |

Das ist die Antwort auf Konrads Frage in einer Zeile: **die AfD nennt einen Wahlbezirk in weniger als einem
Drittel so vielen ihrer Dokumente wie der Durchschnitt der sechs Parteien, die GRÜNEN in rund der Hälfte
mehr.** Dass FDP und SPD beim Verhältnis die Plätze tauschen (0,97 gegen 1,21, bei fast gleichem Anteil),
ist kein Fehler: die FDP ist in den Bezirken stark, in denen das Parteimittel hoch ist, die SPD in solchen
mit niedrigem Mittel — genau das trennen die beiden Varianten, und darum stehen sie beide da.
Die Spalte „Anteil im Mittel" ist nicht der Anteil der Partei an allen ihren Dokumenten mit irgendeinem
Treffer; sie ist das Mittel über 41 Bezirke, und ein Dokument zählt in jedem Bezirk, den es nennt.

## 5. Entscheidung: was gebaut wird

**Gebaut** (Reihenfolge der Umsetzung):

1. **Zwei neue Datenspalten-Sätze.** `wahlbezirke_parteien` bekommt `mittel_anteil`, `abweichung_mittel`,
   `verhaeltnis_mittel`; eine neue veröffentlichte Tabelle `wahlbezirke_kennzahlen` (Schritt `metrics`)
   trägt `anzahl_treffer`, `begriffe`, `treffer_je_begriff`, `treffer_je_1000`, `stadtmittel`,
   `abweichung_stadtmittel`. Beide mit Spaltendoku im Register (`report/tables.py`) und Verträgen.
   `wahlbezirke_auswertung` bleibt unberührt — es ist Golden Master (`tests/fixtures/mini/expected/`).
2. **Ein Umschaltermuster** für die ganze Seite: ein `fieldset` mit Radios je Abschnitt (Makro
   `metric_switcher` in `templates/macros.html.j2`), die Varianten als Datenattribute an Flächen, Zellen und
   Zeilen, ein generisches Stück JavaScript im Rahmen, das je Radiogruppe **innerhalb ihres `<section>`**
   Klassen, Texte, Sortierwerte und Legenden tauscht. Der vorhandene Kartenumschalter wird darauf
   umgestellt, ohne sein Verhalten zu ändern. Ohne JavaScript zeigt die Seite die Standardvariante.
3. **Abschnitt `38-parteien`:** Umschalter „Anteil / Abweichung vom Mittel (pp) / Verhältnis zum Mittel" für
   die sechs Karten, die Spalte „im Mittel" der Parteitabelle und die sechs Parteispalten der Bezirkstabelle.
4. **Abschnitt `20-karte` und `40-wahlbezirke`:** drei neue Einfärbungen (Treffer absolut, Treffer je
   Begriff, Abweichung vom Stadtmittel) und eine Spalte in der Bezirkstabelle, die mit der Einfärbung
   wechselt; eine Kachel „Treffer je Begriff, Median" in den Kernzahlen.
5. **Abschnitt `30-zusammenhang`:** die zweite Regression aus § 3.3 mit r, p und dem Deutungssatz; Tabelle 5
   selbst unverändert.

**Nicht gebaut**, je mit Grund:

| Variante | Warum nicht |
|---|---|
| „je 1000 Wahlberechtigte" als eigenes Radio | Es **ist** der Standard, nur mit einem positiven Faktor: jede Fläche bekäme dieselbe Klasse und dieselbe Farbe, allein die Legende zeigte Zahlen mal 1000. Die Lesart steht stattdessen als Satz an der Legende und in der Fußnote der Tabelle. Die Rohzählung („Treffer absolut") ist dagegen eine eigene Variante, weil sich dort 17 von 41 Klassen ändern (§ 2.1) |
| Verhältnis zum Stadtmittel (Bezirke) | 1 + Abweichung, also dieselbe Information zweimal. Bei den Parteien sind beide nötig, weil dort jeder Bezirk ein anderes Mittel hat (§ 4.3) |
| Abweichung mit Quantilgrenzen | wäre dieselbe Klassenzuordnung wie die Quote, nur divergierend gefärbt (§ 2.4) |
| je Einwohner, je Fläche | keine Einwohnerzahl je Wahlbezirk in den Daten; Fläche misst Dichte (§ 2.5) |
| Log-Verhältnis | 20 Zellen mit Anteil 0 (§ 2.5) |
| gewichtetes Parteimittel als Settings-Schalter | § 4.1: ρ = 0,976, aber das Mittel wird von den beiden größten Fraktionen gesetzt; der Schalter kostet einen Fingerprint und eine Erklärung für nichts |
| Umschalter im Abschnitt Gremien | Seine vier Kennzahlen sind schon Anteile oder Quoten (§ 1.5): „eigene BV" trägt Zahl *und* Anteil *und* Quote je Wahlberechtigtem, „Lokalität" ist ein Anteil. Eine Abweichung vom Mittel beantwortet keine Frage des Abschnitts („wie lokal ist eine Bezirksvertretung" ist schon relativ gefragt) |
| Umschalter im Abschnitt Monate | Ein Monat ist keine Fläche und hat keine Wahlberechtigten. Die einzige sinnvolle Normierung, „Anteil der Dokumente mit Treffer", ist der Quotient zweier Balken, die nebeneinander stehen; eine Abweichung vom Monatsmittel zeigte den Sitzungskalender (Sommerpause) |
| Umschalter im Abschnitt Gewichtung | Der Abschnitt *ist* die Sensitivitätsanalyse: 26 Varianten derselben Kennzahl, jede mit ρ zur ungewichteten Quote. Drei Normierungen darüber verdreifachten eine Tabelle mit schon 14 Spalten |
| Umschalter bei den Kontrollvariablen | Die standardisierten Koeffizienten (β) sind die Normierung der Regression und stehen längst in der Tabelle |
| Umschalter im Abschnitt Begriffe | Ein Begriff hat keinen Nenner. Die Offenlegung dazu ist die Liste der stadtweiten Begriffe (Punkt 44b) |

## 6. Farben, Legenden, Bedienung

- **Sequenziell bleibt sequenziell.** Die drei Varianten ohne Vorzeichen nutzen die vorhandene Blau-Rampe
  `--q0` bis `--q4` (je Modus getrennt gewählt, mit dem Validator der Skill `dataviz` geprüft).
- **Divergierend ist eine neue Rampe `--d0` bis `--d4`**: von `--selected` (orange) über einen neutralen
  Mittelton zu `--q2` (blau), gemischt mit `color-mix(… , var(--surface))` in denselben Stufen wie die
  Tönung der Parteizellen (`--p0` bis `--p4`, `sections/38-parteien.css`). Weil beide Enden aus Variablen
  entstehen, die je Modus definiert sind, folgt die Rampe Hell und Dunkel ohne zweiten `@media`-Block. Die
  Kontraste der normalen Schriftfarbe auf allen fünf Stufen sind nachgerechnet und stehen als Kommentar an
  der Rampe; die Zellen der Tabellen tragen Zahlen und brauchen deshalb ≥ 4,5 in beiden Modi.
- **Orange heißt unter dem Mittel, blau darüber.** Dieselbe Richtung in Karten und Tabellenzellen. Orange ist
  auf dieser Seite schon die Markierungsfarbe (`--selected`); auf den Flächen der kleinen Karten liegt keine
  Markierung, auf der großen Karte bleibt die Markierung ein *Rand*, nicht eine Füllung, also kollidiert
  nichts.
- **Legende je Variante.** Ein `div.legend` mit `id="legend-<variante>"`, alle bis auf die Standardvariante
  `hidden`; der Umschalter zeigt genau eine. Die Legende nennt die festen Grenzen im Klartext („mehr als 2
  Prozentpunkte unter dem Mittel"), nicht die Quantilgrenzen.
- **Bedienung.** Ein `fieldset` mit `<legend>` ist die Beschriftung der Gruppe (Screenreader lesen sie vor
  jedem Radio); die Radios sind echte `<input type="radio">` mit `<label>`, also mit Pfeiltasten bedienbar
  und ohne JavaScript sichtbar. Der Umschalter ändert nur Farbe und Zahl, nie die Reihenfolge der Zeilen;
  eine sortierte Tabelle bleibt sortiert, und die Sortierwerte (`data-value`) wechseln mit, damit ein
  erneuter Klick auf den Spaltenkopf die neue Variante sortiert.
- **Die Standardansicht ändert sich nicht.** Ohne Klick zeigt die Seite genau das, was sie heute zeigt:
  Trefferquote auf der Karte, Anteil auf den Parteikarten, dieselben Zahlen in den Tabellen. Tabelle 5, die
  Treffer (29 010) und das Wörterbuch (5727) bleiben unberührt.

## 7. Kosten (gemessen nach dem Bau)

- **Seitengröße.** Vorher 1 158 408 Byte, nachher **1 268 298 Byte** (1,27 MB von 1,5 MB Budget), also
  **109 890 Byte für beide Umschalter zusammen**, rund 55 KB je Umschalter und damit unter der Grenze von
  rund 100 KB je Umschalter. Keine zweite Kopie der Karten-SVGs: die 41 Flächen stehen weiter einmal in
  `<defs>`, die Varianten sind Attribute an denselben `<use>`. Zwei Sparmaßnahmen nach dem Review:
  die Sortierwerte sind auf sechs Stellen gerundet, und **die Standardvariante trägt keine Attribute** —
  sie ist der Zustand, in dem die Seite ausgeliefert wird, und das JavaScript merkt sich beim Aufbau je
  Element Klasse, Text und Sortierwert und stellt sie wieder her (1080 Attribute weniger, 29 KB).
  Nicht gemacht: kürzere Attributnamen. `data-class-<variante>` ist die Schnittstelle aus Fundament F1
  (Punkt 21), dokumentiert und getestet, und die Variantennamen stehen auch in den Radios und in den
  Legenden-IDs.
- **Laufzeit.** Der neue Schritt `metrics` braucht auf der Referenz 0,1 s, der Schritt `parties` mit den
  drei Spalten weiter 0,5 s, der Schritt `report` 1,7 s statt 1,5 s. `nox -s bench` bleibt grün.
- **Kein neuer Fingerprint.** Die Klassengrenzen stehen unter `[report]` und sind damit aus dem
  Settings-Fingerprint ausgenommen (`docs/plans/00-synergien.md`, § 5.4): eine andere Grenze färbt die Karte
  um, sie rechnet keine Zahl neu. Neu laufen mussten nur `metrics` (neue Ausgabe), `parties`
  (Schema 1 → 2) und `report`.

## 8. Annahmen, die Konrad umstoßen kann

1. **Die Grenzen sind feste Zahlen, nicht Quantile** (±10 % und ±25 % vom Stadtmittel; ±0,5 und ±2
   Prozentpunkte; 0,5 / 0,8 / 1,25 / 2,0). Sie stehen in `defaults.toml` mit Kommentar und lassen sich je
   Stadt ändern. Wer Quantile will, bekommt bei den Bezirken dieselbe Karte wie bei der Quote (§ 2.4).
2. **Das Mittel ist ungewichtet**, bei Parteien und bei Bezirken (§ 3.1, § 4.1).
3. **Die Spalte „im Mittel" der Parteitabelle ist das Mittel der 41 Bezirkswerte**, nicht das Verhältnis der
   Mittelwerte. Beim Verhältnis unterscheidet sich das: AfD 0,32 (Mittel der Verhältnisse) gegen 0,37
   (Verhältnis der Mittel). Gewählt ist die erste Form, weil die Karte genau diese 41 Zahlen zeigt.
4. **„Treffer je Begriff" normiert auf das ganze Wörterbuch des Bezirks**, also auch auf die Begriffe mit
   null Treffern (Median 147 Begriffe, Spannweite 77 bis 751). Die Alternative „je Begriff *mit* Treffer"
   wäre eine andere Frage (sie misst, wie oft ein *gefundener* Ort besprochen wird) und ist nicht gebaut.
5. **Die Standardvariante bleibt überall die heutige.** Wenn Konrad die Abweichung als Standardansicht will,
   ist das ein Einzeiler je Abschnitt (`checked` am anderen Radio) — aber dann sieht ein Leser ohne
   JavaScript die divergierende Karte ohne Umschalter.

## 9. Nachtrag: was der Bau noch gezeigt hat (2026-10-13)

- **Eine CSS-Klasse muss auf jeder Fläche dasselbe bedeuten.** Die Parteizellen trugen `p<n>` aus
  `sections/38-parteien.css`, der Umschalter schrieb aber `q<n>`, und `.q0` bis `.q4` setzen nur `fill` —
  nach einem Klick auf „Anteil" war die Tönung weg. Gefunden hat das die Prüfung mit headless Chrome, kein
  Test. Seitdem gilt `q<n>` auf einer SVG-Fläche als `fill` mit der vollen Rampe und in einer Tabellenzelle
  als Tönung desselben Rangs (`td.q<n>` auf `--p0` bis `--p4`), beides im Rahmen definiert. So trägt ein
  Umschalter eine Skala und nicht zwei.
- **Der Umschalter kann nicht am Abschnitt hängen.** Die Karte steht in `#karte`, ihre Kennzahlspalte in
  `#wahlbezirke`; ein auf `closest("section")` beschränkter Umschalter hätte die Spalte nie erreicht. Darum
  sucht das JavaScript im ganzen Dokument, und die Gruppen trennen sich über eindeutige `value`-Namen (ein
  Test hält das fest).
- **„Treffer absolut" ist keine Wiederholung der Quote.** r = 0,977 und ρ = 0,935 klingen nach derselben
  Karte, aber 17 der 41 Quantilklassen sind andere. Nur „je 1000 Wahlberechtigte" ist wirklich dieselbe
  Karte — ein positiver Faktor ändert keine Klasse.

## 10. Nachtrag: die Befunde des Reviews (2026-10-13)

- **Eine Stadt ohne Treffer hat kein Stadtmittel.** `relative_to(...) − 1` war dort −1 je Bezirk, die
  Nachbedingung „die Abweichungen summieren sich auf 0" brach, und der Schritt `metrics` hätte die Kette
  abgebrochen — in jeder Stichprobe ohne extrahierte Texte. `deviation_from` hat dafür einen eigenen Zweig,
  und die Eigenschaften stehen jetzt als hypothesis-Tests in `tests/property/test_scaling_props.py`
  (dort wäre der Fall der erste Shrink gewesen), `classify_fixed` zusätzlich in `nox -s verify`.
- **Eine Legende fester Grenzen braucht keine Werte.** `legend_for` baut sie aus den Grenzen; vorher
  entstand sie aus `classify_fixed` über die 246 Parteizellen mit dem Wahlbezirk als Schlüssel, und die
  Klassen darin waren still falsch (aufgefallen wäre es erst beim nächsten Gebrauch).
- **Der Deutungssatz war zu stark.** Bei r = −0,11 und p = 0,49 ist das Vorzeichen nicht bestimmbar; die
  Seite sagt das jetzt, statt einen Richtungswechsel zu behaupten, und nennt „Treffer je Begriff" eine
  Gegenprobe und keine Erklärung. Die Zahlen des Methodenabsatzes rechnet
  `analysis.scaling.dictionary_bias`, damit eine zweite Stadt ihre eigenen bekommt.
- **Die mittlere Klasse muss das Mittel einschließen**, sonst divergiert nichts; der Settings-Validator
  prüft es seit dem Review.
