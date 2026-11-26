# Statistik: die Auswertungen, ihre Zahlen und ihre Einwände

Stand 2026-10-14, `v0.13.0`. Die veröffentlichte Seite ist aus Commit `813827e` gebaut und zeigt
alles bis **Punkt 58**; die **Punkte 59 bis 61** liegen seit dem 2026-10-14 auf `main` und sind in
der veröffentlichten Seite noch nicht zu sehen — wo eine Zahl unten davon betroffen ist, steht es
dabei. Die Zahlen der Hauptperiode in den §§ 1 bis 9 und 11 bis 13 und ihre Treffer in § 10 sind die
seit dem 2026-11-18, als ihre Texte mit pypdf 7.1.0 neu gelesen wurden ([decisions.md](decisions.md),
Punkt 68), nachgerechnet am Bau aller Seiten aus diesen Texten; nicht nachgerechnet sind in § 10 das
Themenmodell (NPMI, Saattreue, Reinheit) und der Klassifikator, die den Stand ihres Datums
(2026-10-14, Texte der Arbeit) zeigen. Diese Sicht beantwortet: **welche Frage rechnet welche
Auswertung, mit welcher Formel, mit welchem Ergebnis — und was spricht dagegen.** Sie entscheidet
nichts: wo etwas offen ist, steht das als offen. Die drei anderen Sichten: [technik.md](technik.md),
[inhalt.md](inhalt.md), [workflow-ratsmitglied.md](workflow-ratsmitglied.md). Gründe und verworfene
Alternativen: [decisions.md](decisions.md); Aufbau: [architecture.md](architecture.md).

Die Zahlen unten stammen aus drei Orten, und das ist je Abschnitt angegeben: der veröffentlichten
Seite samt ihrer `summary.json` (am 2026-10-14 nachgesehen), dem Methodik-Review
[methodik-review-2026-10.md](methodik-review-2026-10.md) (gemessen am 2026-10-12 auf der Referenz)
und dem Befundbericht [befunde-2026-10-14.md](befunde-2026-10-14.md) (nachrechenbar mit
`uv run python docs/befunde-2026-10-14-messung.py`). Wo die Referenzmessung mit **abgeschalteten**
eigenen Regeln rechnet (Stand der Arbeit, Tag `bartzsch-exakt`), ist es gesagt.

## 1. Tabelle 5: Trefferquote gegen Wahlbeteiligung

**Die Frage.** Hängt die Wahlbeteiligung eines Kommunalwahlbezirks damit zusammen, wie oft er in den
Ratsdokumenten vorkommt? Das ist die Frage der Bachelorarbeit, und die Seite reproduziert ihre
Tabelle 5.

**Die Rechnung.** Trefferquote = Dokumente mit mindestens einem Treffer im Wörterbuch des Bezirks,
geteilt durch seine Wahlberechtigten. `scipy.stats.linregress` mit x = Trefferquote, y =
Wahlbeteiligung **in Prozent**, über alle 41 Bezirke und ein zweites Mal ohne die Bezirke 1 und 10
(`analysis.exclude_districts` im Profil, nicht im Code). Code: `analysis/regression.py`,
`regression_pair`; ohne Streuung in x oder y gibt es kein Ergebnis, sondern einen `EmptyResultError`.

**Die Zahlen heute** (`summary.json` der Hauptperiode):

| | alle Wahlbezirke | ohne 1 und 10 |
|---|---|---|
| n | 41 | 39 |
| Steigung | 79,4275 | 214,9840 |
| Achsenabschnitt | 48,1482 | 40,5023 |
| r | 0,1901 | 0,3363 |
| R² | 0,0361 | 0,1131 |
| p | 0,23383 | **0,03635** |
| Standardfehler der Steigung | 65,681 | 98,988 |

Mit den Texten der Arbeit (bis zum 2026-11-18) standen dort Steigung 79,9539 und 216,2416, r = 0,1891
und 0,3351, p = 0,23641 und 0,03705.

**Der Interpretationsspielraum.** Über alle 41 Bezirke belegt p = 0,23 keinen Zusammenhang. Die
zweite Spalte ist die einzige Stelle im ganzen Vorhaben, an der ein p unter 0,05 steht — und sie
erklärt R² = 0,11 der Streuung, also neun Zehntel nicht. Das Vorzeichen ist in allen Varianten
positiv (mehr Sichtbarkeit, mehr Beteiligung) außer in einer Themenzeile ohne Aussage (§ 6), aber
kein Standardfehler ist kleiner als der Koeffizient geteilt durch 2,2.

**Die Einwände, in der Reihenfolge ihrer Schwere.**

1. **n = 41 ist die ganze Grundgesamtheit.** Es gibt nicht mehr Wahlbezirke. Ein p-Wert beantwortet
   hier „wie wahrscheinlich wäre dieses Muster, wenn die Trefferquote zufällig verteilt wäre", nicht
   „gilt das auch für andere Städte".
2. **Die zweite Spalte ist nach Ansehen der Daten entstanden.** Wer die zwei höchsten Punkte
   entfernt (seit dem 2026-11-18 genau genommen den höchsten und den dritthöchsten, § 2) und dann
   p = 0,036 berichtet, hat zwei Tests gerechnet und einen berichtet. Die Arbeit
   berichtet beide Spalten, das ist redlich; die Deutung der zweiten als „signifikant" stand bis zum
   2026-10-14 ohne Korrektur da. **Punkt 61 beantwortet das**: der Spaltenkopf trägt auf `main` das
   Wort „explorativ", und darunter stehen zwei Sätze — der erste nennt den Grund (ausgeschlossen sind
   die beiden Bezirke mit den höchsten Quoten, eine Entscheidung über diesen Datensatz), der zweite
   beide p-Werte samt dem Urteil, und keine der Zahlen steht hart im Text. Die veröffentlichte Seite
   zeigt das noch nicht.
3. **Mit Kontrollvariablen bleibt nichts übrig** (§ 5): R² steigt von 0,036 auf 0,886, und der
   Koeffizient der Trefferquote fällt auf p = 0,163.
4. **In der vorigen Wahlperiode verschwindet der Befund** (§ 6): dieselbe Methode, dieselbe Stadt,
   anderer Zeitraum, p = 0,08334 ohne 1 und 10. Das ist der stärkste Einwand, der aus den Daten
   selbst kommt.
5. **Die Verzerrung der Wörterbuchgröße** (§ 3) steckt in x.
6. **Die Normierung** teilt durch eine Größe, die kaum schwankt (§ 3).

## 2. Die Ausreißer 1 und 10

**Die Frage.** Sind die beiden Bezirke mit der höchsten Trefferquote wirklich abgesetzt, und warum?

**Die Rechnung.** Robuster z-Wert über Median und MAD der Trefferquote.

**Die Zahlen** (linke Spalte: Methodik-Review § 2.7 und § 4, Referenz 2026-10-12; rechte Spalte:
Hauptperiode mit den Texten aus pypdf 7.1.0, seit dem 2026-11-18):

| | Regeln aus (wie die Arbeit) | Regel 1 an (heute) |
|---|---|---|
| Median / MAD der Quote | 0,0613 / 0,0097 | 0,0612 / 0,0090 |
| Bezirk 1 (Altstadt, Carlstadt, Hofgarten) | z = 10,43 | z = 10,21 |
| Bezirk 10 (Flingern Süd) | z = 4,04 | **z = 2,74** |
| dritt- bzw. zweithöchster | 2,38 (Bezirk 2) | 2,79 (Bezirk 2) |

Mit den Texten der Arbeit stand die rechte Spalte bei 0,0604 / 0,0094, z = 9,71 und z = 2,69, und
Bezirk 2 lag mit 2,58 hinter Bezirk 10 (so im Methodik-Review, § 4).

**Der Interpretationsspielraum.** Die beiden sind aus verschiedenen Gründen abgesetzt. Bezirk 1 hat
751 Begriffe im Wörterbuch (Median 147 auf der Referenz der Arbeit), weil in der Innenstadt fast
jedes zweite Gebäude einen Wikipedia-Artikel hat — ein Artefakt der **Wörterbuchgröße**, kein
Artefakt der Benennung. Bezirk 10 hing mit 177 von 1 189 Treffern (14,9 %) allein am Ort „Stadtwerke
Düsseldorf"; seit Regel 1 („Einrichtung mit Stadtnamen") ist er **kein Ausreißer mehr**, wird aber
weiter aus der zweiten Spalte genommen, weil Tabelle 5 der Arbeit ihn nennt. Mit den neu gelesenen
Texten hat er nicht einmal mehr die zweithöchste Quote: Bezirk 2 liegt mit 0,0864 knapp vor ihm
(0,0860). Die Seite nannte die ausgeschlossenen Bezirke bis dahin immer „die beiden höchsten
Trefferquoten", auch auf der Seite der Periode 2014 bis 2020, wo sie auf Platz 2 und 9 stehen; seit
dem 2026-11-18 sagt sie das nur noch, wenn es stimmt, und nennt sonst die Plätze (hier 1 und 3).

**Die Einwände.** Die Liste `[1, 10]` ist eine Entscheidung von Hand; eine automatische Regel
(robuster z, Cook-Distanz) wäre übertragbar, würde aber die Spalte „ohne Ausreißer" von Lauf zu Lauf
anders füllen und ist bewusst nicht gebaut. Eine robuste Regression (Huber, Theil-Sen) über alle 41
Punkte ist die andere Alternative und ebenfalls nicht gebaut.

## 3. Die Verzerrung durch die Wörterbuchgröße

**Die Frage.** Wovon hängt die Trefferzahl eines Bezirks eigentlich ab?

**Die Rechnung.** Pearson-Korrelationen über die 41 Bezirke in `analysis.scaling.dictionary_bias`;
die Deutungssätze auf der Seite entstehen aus diesen Zahlen, nicht aus festem Text.

**Die Zahlen** (Abschnitt „Methode und Grenzen" der Seite; mit den Texten der Arbeit stand die
zweite Zeile bei 0,17, die beiden anderen gleich):

| Paar | r |
|---|---|
| Treffer gegen Zahl der Begriffe | **0,76** (erklärt 58 % der Streuung) |
| Treffer gegen Wahlberechtigte | 0,16 |
| Treffer je Begriff gegen Zahl der Begriffe | **−0,51** |

Wörterbücher reichen von 77 bis 751 Begriffen (Faktor 9,8), Wahlberechtigte von 10 168 bis 13 086
(Faktor 1,3). Auf der Referenz der Arbeit (Regeln aus, 2026-10-12) waren es r = 0,767 beziehungsweise
0,176, und die Trefferquote korrelierte mit der Wörterbuchgröße mit r = 0,724.

**Der Interpretationsspielraum.** „Wie oft kommt ein Bezirk vor" misst zu gut der Hälfte, wie viele
benannte Orte in ihm liegen und wie viele davon einen Wikipedia-Artikel haben. Das ist die größte
Grenze der Methode. Die Normierung der Arbeit (je Wahlberechtigtem) nimmt davon fast nichts heraus,
weil ihr Nenner kaum schwankt.

**Die Einwände gegen die Gegenprobe.** „Treffer je Begriff" nimmt diese Verzerrung heraus, ist dafür
in die andere Richtung verzerrt (r = −0,51): ein Bezirk mit wenigen Begriffen braucht nur einen stark
besprochenen Ort für einen hohen Wert. **Keine der beiden ist die richtige Kennzahl**; sie sind
Gegenproben, und darum stehen beide auf der Seite.

## 4. Die zweite Regression: Treffer je Begriff

**Die Frage.** Was wird aus Tabelle 5, wenn die Verzerrung aus § 3 aus der Kennzahl genommen ist? Das
war die stärkste offene Empfehlung des Methodik-Reviews (§ 2.6).

**Die Rechnung.** Dieselbe Funktion, derselbe y-Wert, x = Treffer je Begriff im Wörterbuch des
Bezirks (`model.per_term_regression`).

**Die Zahlen** (Seite, Abschnitt „Trefferquote und Wahlbeteiligung"):

| | alle Wahlbezirke | ohne 1 und 10 |
|---|---|---|
| n | 41 | 39 |
| Steigung | −0,56 | −0,25 |
| r | −0,113 | −0,043 |
| R² | 0,013 | 0,002 |
| p | 0,484 | 0,793 |

Mit den Texten der Arbeit: Steigung −0,56 und −0,24, p = 0,486 und 0,800.

**Der Interpretationsspielraum.** Es bleibt **nicht einmal das Vorzeichen**. Die einzige Spalte, in
der die Arbeit ein signifikantes p berichtet, hängt damit an der Größe der Wörterbücher. Median der
Kennzahl 4,5984, Spannweite 2,2727 bis 9,5849; 29 der 41 Quantilklassen liegen anders als bei der
Quote (mit den Texten der Arbeit 4,5656, 2,2485 bis 9,5472 und 28).

**Die Einwände.** Siehe § 3: die Kennzahl ist gegenläufig verzerrt. Die Rechnung widerlegt Tabelle 5
nicht, sie zeigt, dass das Ergebnis an der Wahl der Kennzahl hängt.

## 5. Tabelle 6 und 6b: Kontrollvariablen

**Die Frage.** Hängt die Wahlbeteiligung an der Trefferquote, oder an dem, was beide erklärt?

**Die Rechnung.** Gewöhnliche kleinste Quadrate in `analysis/ols.py` (gegen statsmodels geprüft),
y = Wahlbeteiligung in Prozent, n = 41. Die Kontrollvariablen sind Sozialdaten des Quartiersatlas
2024 (Stand **31.12.2021**), die für 171 Sozialräume vorliegen und über die Flächenanteile der
Stimmbezirke, gewichtet mit deren Wahlberechtigten, auf die Wahlbezirke umgerechnet werden; eine
Einheit ohne Wert fällt heraus, solange sie unter `context.max_missing_weight` = 0,1 des Gewichts
eines Bezirks liegt. Die Tabelle nennt je Term Koeffizient, Standardfehler, p, standardisierten
Koeffizienten und VIF.

**Die Zahlen** (Seite, Abschnitt „Kontrollvariablen"):

| Modell | Terme neben der Konstante | Koeffizient der Trefferquote | p | R² | korrigiert |
|---|---|---|---|---|---|
| A | 1 (nur Trefferquote) | 79,428 (± 65,681) | 0,234 | 0,036 | 0,011 |
| **B (Hauptmodell)** | 4 | 41,602 (± 29,197) | **0,163** | **0,886** | 0,874 |
| C | 6 | 39,355 (± 24,139) | 0,112 | 0,928 | 0,915 |

Mit den Texten der Arbeit standen in der Spalte der Trefferquote 79,954 (p = 0,236), 43,531
(p = 0,145, R² = 0,887) und 40,426 (p = 0,104); in keinem Modell und keiner Stichprobe kreuzt ein p
der Trefferquote durch die neuen Texte die Grenze von 0,05.

Im Modell B tragen den Befund: sozialer Handlungsbedarf (Koeffizient −9,877, standardisiert **−0,96**,
p < 0,001, VIF 1,46), Fluktuationsrate (−0,312, p = 0,037) und Anteil 65 Jahre und älter (−0,459,
p = 0,108). Modell C fügt die Stimmenanteile von CDU (−0,259, p = 0,005) und AfD (−0,436, p = 0,034)
hinzu. Tabelle 6b rechnet dieselbe Regression mit **genau einer** Kontrollvariable neben der
Trefferquote; die Spanne des korrigierten R² reicht dort von −0,013 (Anteil unter 18 Jahren) bis
0,866 (Anteil mit Migrationshintergrund; sozialer Handlungsbedarf 0,864).

**Der Interpretationsspielraum.** Das ist nicht eine Relativierung von Tabelle 5, es ist ihre
Ersetzung als Antwort: ein einziger Index der Stadtstatistik erklärt die Wahlbeteiligung fast
vollständig, und die Trefferquote erklärt daneben nichts mehr. Dass ihr Koeffizient positiv bleibt
und von 79 auf 42 fällt, lässt sich als „ein kleiner eigener Beitrag, nicht signifikant" lesen oder
als „Rauschen" — beides ist mit p = 0,163 bei n = 41 vereinbar.

**Die Einwände.**

1. **Der Datenstand passt nicht zur Wahl**: Sozialdaten vom 31.12.2021, Wahl am 14.09.2025. Die Seite
   sagt es.
2. **Zirkularität bei den Stimmenanteilen** (Modell C): Parteianteile und Wahlbeteiligung sind beides
   Größen derselben Wahl; der Koeffizient der CDU erklärt die Beteiligung nicht, er beschreibt sie
   mit. Siehe § 9.
3. **Multikollinearität**: in Modell C steht der soziale Handlungsbedarf bei VIF 6,66, der Anteil 65+
   fällt von p = 0,108 auf p = 0,950. Das Hauptmodell ist darum B, nicht C.
4. **Die Umrechnung** von 171 Sozialräumen auf 41 Wahlbezirke über Flächenanteile setzt voraus, dass
   sich die Wahlberechtigten innerhalb eines Stimmbezirks gleichmäßig verteilen; ein
   Bevölkerungsraster wäre genauer und ist nicht Teil der Auswertung. Die Abdeckung liegt bei 0,9999.
5. **Modellwahl nach Ansehen**: dass B das Hauptmodell ist, ist eine Entscheidung; 6b zeigt, wie
   empfindlich der Koeffizient der Trefferquote auf die Wahl der einen Kontrollvariable reagiert:
   von −27,24 (Mindestsicherungsquote) über 5,72 (sozialer Handlungsbedarf) bis 150,77
   (Fluktuationsrate). Bis zum 2026-11-18 stand hier „7,60 bis 149,75", also nur der Wert neben dem
   sozialen Handlungsbedarf und der größte; die kleinsten Werte (−26,05 neben der
   Mindestsicherungsquote, −7,80 neben der AfD) fehlten schon damals.

## 6. Die 26 Gewichtungsvarianten

**Die Frage.** Hängt die Schlussfolgerung an der binären Zählung? Heute zählt ein Dokument für einen
Bezirk, sobald **ein** Begriff seines Wörterbuchs darin vorkommt — „grafenberger allee" (206
Dokumente) zählt so viel wie ein Begriff mit einem einzigen Treffer.

**Die Rechnung.** Ein Dokument bekommt je Wahlbezirk das Gewicht `max` über seine getroffenen
Begriffe von (Gewicht des Begriffs × Gewicht der Dokumentart × Anteil des Themas); jeder Faktor liegt
in [0, 1], ein Dokument zählt je Bezirk also höchstens einmal wie bisher. Verträge sichern zu, dass
die Variante `einheit` genau `anzahl_treffer` reproduziert und die Themenvarianten diese Zählung
zerlegen. Je Variante steht Tabelle 5 in beiden Spalten, dazu ρ, die Rangkorrelation der gewichteten
zur ungewichteten Quote.

**Die Zahlen** (Seite, Abschnitt „Was ändert die Gewichtung?"; Auszug der sechs Nicht-Themen-Zeilen):

| Variante | Summe | p (alle) | p (ohne 1, 10) | ρ |
|---|---|---|---|---|
| ohne Gewichtung (= Tabelle 5) | 29 330,0 | 0,234 | **0,036** | 1,000 |
| Spezifität nach Wahlbezirken (ein Begriff in n Wörterbüchern zählt 1/n) | 18 031,0 | 0,182 | **0,026** | 0,777 |
| Spezifität nach Dokumenthäufigkeit ((ln N − ln df) / ln N) | 19 760,6 | 0,219 | **0,033** | 0,978 |
| Anträge, Anfragen, Eingaben halb | 23 829,5 | 0,348 | 0,091 | 0,986 |
| nur Verwaltungsvorlagen | 18 329,0 | 0,627 | 0,358 | 0,887 |
| kombiniert (Dokumenthäufigkeit × Anträge halb) | 16 132,7 | 0,330 | 0,083 | 0,974 |

Dazu 20 Themenzeilen, die je Dokument nur seinen Anteil an einem Thema zählen (ρ von 0,529 bis
0,957). Über alle 26 Varianten erreichen **2 ein p unter 0,05 in der Spalte über alle 41 Bezirke**
(Thema 6 Sportausschuss 0,043, Thema 19 0,016) und **8 in der Spalte ohne 1 und 10** (die drei oben
plus Thema 0 0,011, Thema 6 0,004, Thema 11 0,028, Thema 17 0,015, Thema 19 0,004). Mit den Texten
der Arbeit lagen genau dieselben Zeilen unter 0,05 (Summe der ersten Zeile 29 010,0, p = 0,236 und
0,037; Themen-ρ 0,530 bis 0,953); das Themenmodell ist für die neuen Texte auf demselben Rechner neu
gerechnet, und seine Themen tragen dieselben Kürzel.

**Der Interpretationsspielraum.** Die Kernaussage ist stabil: die drei Varianten, die nur die
Spezifität der Begriffe ändern, lassen Vorzeichen und Größenordnung stehen, und die Varianten, die
Anträge abwerten, machen den Zusammenhang schwächer. Keine der sechs Varianten ohne Thema dreht das
Vorzeichen; unter den Themenzeilen ist die Steigung über alle 41 Bezirke einmal negativ (Thema 18,
p = 0,998, also ohne Aussage), ohne 1 und 10 nie. Mit den Texten der Arbeit waren es zwei solche
Zeilen (Thema 5 und Thema 18, beide mit p über 0,97).

**Die Einwände.** Bei 26 Varianten × 2 Spalten sind 52 Tests gerechnet; unter der Nullhypothese
wären rund 2,6 Werte unter 0,05 zu erwarten, und gefunden sind 10 — mehr als Zufall, aber die acht
„signifikanten" Themenzeilen sind **keine unabhängigen** Tests, sondern Zerlegungen derselben
Zählung. Die Themennummern gelten nur für diesen Datenstand (§ 10). Die Seite nennt für die
Gewichtungstabelle keine Mehrfachtest-Korrektur; der Bonferroni-Hinweis steht nur im Abschnitt
„Urheber und Parteien" (§ 9).

## 7. Zwei Wahlperioden

**Die Frage.** Bewegt sich die Wahlbeteiligung eines Bezirks mit seiner Sichtbarkeit, wenn man
dieselbe Rechnung über zwei Wahlperioden legt?

**Die Rechnung.** Schritt `compare` (`analysis/periods.py`) stellt beide Perioden je Wahlbezirk
nebeneinander und regressiert die **Änderungen** (Δ Trefferquote gegen Δ Wahlbeteiligung in
Prozentpunkten, beides neu minus alt). Beide Perioden benutzen **dasselbe** Wörterbuch; die
Wahlzahlen von 2020 liegen auf 316 Stimmbezirken eines anderen Zuschnitts und werden im Schritt
`precincts` über Flächenanteile summentreu auf die 41 Wahlbezirke von 2025 übertragen
(`largest_remainder` rundet ganzzahlig, ohne die Stadtsumme zu ändern).

**Die Zahlen** (Befundbericht § 1, Seite Abschnitt „Zwei Wahlperioden"):

| Periode | n | Steigung | r | R² | p |
|---|---|---|---|---|---|
| 2014 bis 2020, alle | 41 | 64,8653 | 0,2368 | 0,0561 | 0,13605 |
| 2014 bis 2020, ohne 1 und 10 | 39 | 81,7005 | 0,2808 | 0,0789 | **0,08334** |
| 2020 bis 2025, alle | 41 | 79,4275 | 0,1901 | 0,0361 | 0,23383 |
| 2020 bis 2025, ohne 1 und 10 | 39 | 214,9840 | 0,3363 | 0,1131 | **0,03635** |
| **Regression der Differenzen** | 41 | 7,3455 | 0,0982 | 0,0096 | **0,54136** |

Die Rangfolge hält: Spearman der Trefferquoten zwischen den Perioden **0,8230**, der
Wahlbeteiligungen 0,9826. Δ Trefferquote hat den Median −0,0102 (−0,0865 bis +0,0070); 8 der 41
Bezirke gewinnen an Quote, 24 an Beteiligung.

**Stand der Zahlen.** Seit dem 2026-11-18 sind die Texte beider Perioden mit pypdf 7.1.0
extrahiert: die der alten Periode seit dem 2026-11-16 ([decisions.md](decisions.md), Punkt 67), die
der Hauptperiode seit dem 2026-11-18 ([decisions.md](decisions.md), Punkt 68); bis dahin waren es in
der Hauptperiode die Texte der Arbeit. Der neue Extraktor allein hebt die Treffer der alten Periode
um 1,3 % (36 324 → 36 788) und die der Hauptperiode um 1,1 % (29 010 → 29 330); mit den Texten aus
pypdf 6.20.0 (und den Texten der Arbeit in der Hauptperiode) standen in der Tabelle für die alte
Periode r = 0,2384 und p = 0,13330, ohne 1 und 10 p = 0,08211, für die Differenzen p = 0,53045 und
als Spearman 0,8106. Mit den Texten der Arbeit in der Hauptperiode und 7.1.0 in der alten (vom
2026-11-16 bis zum 2026-11-18) standen in den Zeilen der Hauptperiode r = 0,1891 und p = 0,23641,
ohne 1 und 10 p = 0,03705, für die Differenzen p = 0,51365 (Steigung 7,8493, r = 0,1050) und als
Spearman 0,8127; Δ Trefferquote hatte den Median −0,0115 (−0,0870 bis +0,0059). Die Zeilen der
alten Periode ändert Punkt 68 nicht. Dieselbe Umstellung gilt für den Städtevergleich in § 8
(Mönchengladbach liest seit Punkt 67 mit 7.1.0).

**Der Interpretationsspielraum.** Die alte Periode ist eineinhalb Jahre länger und trägt 3 107
Dokumente mehr; die Quoten sind fast überall niedriger, der Median um 15 % (mit den Texten der
Arbeit 16 %). Was sich **nicht** mitbewegt, ist die Wahlbeteiligung: ein Bezirk mit gestiegener
Sichtbarkeit hat keine gestiegene Beteiligung (p = 0,54). Und: die eine signifikante Spalte der
Arbeit ist in der alten Periode nicht signifikant.

**Die Einwände.**

1. **Dasselbe Wörterbuch für beide Perioden**: eine Straße, die 2016 anders hieß, wird in den
   Dokumenten von 2016 mit dem Namen von heute gesucht.
2. **Der Längenunterschied ist nicht herausgerechnet** (77 gegen 61 Monate).
3. **Die Umrechnung der Wahlzahlen ist ein Modell**: 269 der 316 Stimmbezirke (85,1 %) fallen auf
   mehr als einen Zielbezirk, und die 44,6 % Briefwähler von 2020 haben keine Geometrie — sie sind
   proportional zu den Wahlberechtigten mit Wahlschein verteilt. Nachrechenbar in
   `stimmbezirke_zuordnung.parquet` (liegt unter `2014-2020/data/`).
4. **Zwei Zeitpunkte und 41 Bezirke tragen keine kausale Aussage.** Die Seite sagt diesen Satz.
5. Die alte Periode hat außerdem **33,2 % unbekannte Gremien und 55,9 % unbekannte Urheber**; ihre
   Gremien- und Parteiauswertung ist darum viel schwächer belegt als die der Hauptperiode.

## 8. Zwei Städte

**Die Frage.** Sieht die Rechnung in einer zweiten Kommune anders aus?

**Die Rechnung.** Dieselbe Kette unter einem zweiten Profil; `georep publish` baut `vergleich.html`
aus den `summary.json` der Stadtseiten und rechnet selbst nichts.

**Die Zahlen** (`vergleich.html`, Befundbericht § 2):

| | Düsseldorf | Mönchengladbach |
|---|---|---|
| Wahlbezirke / Stimmbezirke | 41 / 306 | 33 / 179 |
| Wahlberechtigte je Bezirk | 11 457 im Mittel | 6 188 im Mittel |
| Dokumente / davon mit Text | 19 108 / 19 033 (99,6 %) | 2 895 / **650 (22,5 %)** |
| Trefferquote: Median | 0,061 | 0,006 |
| Trefferquote: max/min | 5,84 | **28,93** |
| Tabelle 5, alle | r = 0,1901, p = 0,23383 | r = 0,1294, p = 0,47310 |

**Stand der Zahlen.** Die Spalte Düsseldorf trägt seit dem 2026-11-18 die Texte aus pypdf 7.1.0
([decisions.md](decisions.md), Punkt 68), wie Mönchengladbach schon seit Punkt 67; mit den Texten der
Arbeit standen dort 0,060, 5,80 und r = 0,1891, p = 0,23641. Die Spalte Mönchengladbach ändert sich
nicht.

**Der Interpretationsspielraum.** Was beide Städte teilen, ist der Nicht-Befund: in keiner erklärt
die Trefferquote die Wahlbeteiligung. Die Verteilungen sind verschieden **geformt**, nicht nur
verschoben.

**Die Einwände.** Die absoluten Zahlen sind nicht vergleichbar: Mönchengladbachs Zahlen ruhen auf
rund einem Viertel der Periode (2 213 von 2 871 Hauptdateien antworten mit `404`), und die 650
Dokumente mit Text sind **keine Zufallsstichprobe** der 2 895 — welche Datei das
Ratsinformationssystem ausliefert, entscheidet es selbst, und warum, sagt es nicht. Dazu: die
Wahlbezirke sind fast doppelt so groß zugeschnitten, und die Quote teilt durch die Wahlberechtigten;
die Stimmbezirksflächen stammen vom 08.06.2022 und stimmen nur zu 86,2 % je Wahlbezirk mit dem
amtlichen Straßenverzeichnis überein (Grenze des Runbooks: 90 %). Der Abschnitt „Vergleichbarkeit"
der Vergleichsseite sagt alles davon.

## 9. Parteien gegen Stimmenanteil

**Die Frage.** Bedient eine Partei in ihren Dokumenten ihre Hochburgen?

**Die Rechnung.** Je Partei und Wahlbezirk: Anteil der Dokumente dieser Partei, die diesen Bezirk
erwähnen. Dagegen der Stimmenanteil derselben Partei in diesem Bezirk, Pearson-Korrelation über die
n Bezirke, **in denen die Partei angetreten ist** (`angetreten`). Der Urheber je Dokument ist aus
Dokumentart, Titel und Textkopf abgeleitet, weil der OParl-Server die drei Urheberfelder nicht füllt
(0 von 19 109 über die ganze Periode gemessen); die Ableitung deckt 98,3 % ab und steht mit Quelle
und getroffener Zeichenkette in `dokumente_urheber` zum Download.

**Die Zahlen** (Seite, Abschnitt „Urheber und Parteien"):

| Partei | Dokumente | davon allein | Anteil im Mittel | n | r | p |
|---|---|---|---|---|---|---|
| CDU | 2 140 | 1 602 | 3,33 % | 41 | 0,046 | 0,773 |
| Bündnis 90/Die Grünen | 2 308 | 1 999 | 3,63 % | 41 | 0,076 | 0,637 |
| SPD | 2 107 | 1 767 | 2,65 % | 41 | 0,035 | 0,830 |
| FDP | 879 | 694 | 2,68 % | 41 | **0,459** | **0,003** |
| Die Linke | 792 | 356 | 1,32 % | 40 | 0,141 | 0,385 |
| AfD | 183 | 67 | 0,89 % | 41 | **−0,363** | 0,020 |

Die Dokumente und die Urheberzuordnung ändern die neu gelesenen Texte nicht, nur die Treffer: mit den
Texten der Arbeit standen in der Spalte „davon allein" 1 584, 1 969, 1 747 und 686, im Mittel
3,28 %, 3,57 %, 2,61 % und 2,65 %, und r = 0,052, 0,077, 0,022 und 0,450 (FDP p = 0,003); Die Linke
und AfD sind unverändert.

Die Bonferroni-Grenze bei 6 Tests ist 0,05/6 = 0,008; **nur die FDP liegt darunter**. Der Umschalter
rechnet jede Zelle zusätzlich als Abweichung vom Mittel aller Parteien in Prozentpunkten und als
Verhältnis dazu (AfD 0,32, Die Linke 0,56, FDP 0,98, SPD 1,21, CDU 1,33, GRÜNE **1,60**; mit den
Texten der Arbeit Die Linke 0,57, FDP 0,97, GRÜNE 1,59); das Mittel
ist ungewichtet, das gewichtete ist gemessen und verworfen, weil GRÜNE, CDU und SPD es fast allein
setzen.

**Die Einwände.**

1. **Endogenität.** Stimmenanteil und Dokumentanteil sind keine unabhängigen Größen: wo eine Partei
   stark ist, hat sie mehr Mandatsträger in der Bezirksvertretung, und Anträge der
   Bezirksvertretungen machen 57,6 % der Dokumente aus. Die Korrelation kann die Ursache in beide
   Richtungen haben, und die Rechnung unterscheidet sie nicht.
2. **Sechs Tests, einer unter der Grenze.** Die Seite nennt die Bonferroni-Grenze, sagt aber nicht,
   dass die FDP-Korrelation damit ein einzelner Befund aus sechs ist und als solcher nicht geprüft.
3. **Mehrfachurheberschaft**: 1 169 Dokumente haben zwei oder mehr Urheber und zählen für jede
   Partei voll; „Treffer" summiert über die Bezirke, ein Dokument mit drei Bezirken zählt dreimal.
4. **Die Ableitung ist keine Messung, und ihre Deckung hängt an der Konfiguration.** 865 Dokumente
   einzelner Mandatsträger bleiben ohne Partei, auch wenn der Titel eine nennt; 327 bleiben
   unbekannt. Die Periode 2014 bis 2020 stand bei 44,1 % Deckung, bis Punkt 60 ihre beiden
   häufigsten Dokumentarten und den Briefkopf ihrer Vorlagenform las — jetzt sind es 89,4 %
   („unbekannt" 12 418 → 2 356). **Mönchengladbach** hat seit Punkt 59 überhaupt Urheber: seine 16
   Dokumentarten sind eindeutig und entscheiden die Klasse, also 0,0 % unbekannt, aber nur 242 der
   581 Fraktionsanträge (41,7 %) nennen auch eine **Partei**. Beides liegt auf `main` und ist in der
   veröffentlichten Seite noch nicht zu sehen. Dass eine Zahl so stark an einer Profilzeile hängt,
   ist selbst der Einwand: „unbekannt" misst die Konfiguration mit, nicht nur die Quelle.
5. **Wahlbezirk 11**: Die Linke ist dort nicht angetreten (0 Stimmen), darum n = 40 — sonst läse sich
   „kein Wahlvorschlag" wie „keine Zustimmung".
6. **In den anderen Datensätzen findet derselbe Abgleich nichts**, und das ist der nüchternste
   Kommentar zur FDP-Korrelation der Hauptperiode: in Mönchengladbach liegt kein r über 0,2 und kein
   p unter 0,27 (AfD: 5 Dokumente in 3 Bezirken, eine Zahl ohne Aussage), und in der Periode 2014
   bis 2020 kommt mit FDP +0,395 (p = 0,0106) und AfD −0,378 (0,0149) **keine** Partei unter die
   Bonferroni-Grenze von 0,008. Beide Zahlenreihen liegen auf `main` (Punkte 59 und 60).

## 10. Gremien, Themen und der passende Ausschuss

**Die Frage.** Von welchem Gremium kommt ein Dokument, und welcher Ausschuss passt sachlich zu ihm?

**Die Rechnungen.**

- **Gremium je Dokument, erste Quelle**: das Kürzel vor dem ersten Schrägstrich der
  Drucksachennummer (`reference_pattern` im Profil), in einer Tabelle nachgesehen; trifft das Muster
  nicht, übersetzt `[bodies.aliases]` den Kopf einer älteren Nummernform.
- **Zweite Quelle, seit Punkt 58**: die **Beratungsfolge** aus OParl
  (`consultation[].organization`), also die Gremien, die ein Dokument beraten haben. Sie entscheidet
  nur, wo die Nummer kein bekanntes Gremium nennt, **und nur, wenn sie genau eine Organisation
  nennt**; die Abbildung Organisation → Kürzel steht als `[bodies.organizations]` im Stadtprofil und
  ist mit `georep learn-bodies` aus den Daten gelernt. Was übrig bleibt, bleibt sichtbar „ohne
  erkanntes Gremium".
- **Themenmodell**: TF-IDF und NMF (scikit-learn), k = 20, davon 17 je Ausschuss gesät (Saatwörter
  nach Log-Odds mit Dirichlet-Prior, feste Wortmatrix), 3 frei. Stoppwörter kommen aus dem Profil und
  aus dem Korpus (627 statt 313 Wörter).
- **Passender Ausschuss**: logistische Regression auf TF-IDF, gelernt auf den Dokumenten, deren
  Drucksachennummer ein Ausschusskürzel trägt; unter `classify.min_probability` = 0,4 landet ein
  Dokument in der Restklasse.

**Die Zahlen.**

| Größe | Wert |
|---|---|
| Gremium je Dokument, Hauptperiode | 38 Klassen, **0 unbekannt**; BV 10 999 (57,6 %), Rat 2 301 (12,0 %), Ausschuss 5 360 (28,1 %), Beirat 448 (2,3 %) |
| Treffer aus der eigenen Bezirksvertretung | 14 486 der 29 330 Dokument-Bezirk-Paare (mit den Texten der Arbeit 14 377 der 29 010) |
| Anteil eigene BV je Wahlberechtigtem gegen Wahlbeteiligung | r = 0,25, p = 0,12 über alle 41; ohne 1 und 10 p = 0,08 (mit den Texten der Arbeit r = 0,24, p = 0,12 und 0,09) |
| Themenmodell, NPMI der Topwörter | +0,4164 → +0,4208 mit den Stoppwörtern aus dem Profil; **+0,3349 mit Saat** |
| Saattreue / Reinheit | 0,72 bis 1,00 (Median 0,83) / 0,15 bis 0,57 |
| Klassifikator, Kreuzvalidierung | **0,941** Genauigkeit, **0,878** Makro-F1 über 20 Klassen |
| Restklasse | **11 869** von 19 108 (62,4 %), davon 11 284 ohne Ausschusskürzel in der Nummer |
| unter der Schwelle: Ausschussdokumente / BV / Rat | 10,9 % / 81,2 % / 87,4 % |

Die Zahlen des Klassifikators sind die der **veröffentlichten Seite**; über Rechner hinweg sind sie
nicht exakt reproduzierbar (die logistische Regression hat einen festen Startwert, die
BLAS-Thread-Zahl aber nicht, und ein lokaler Lauf landet um einzelne Dokumente daneben). Als
Größenordnung sind sie stabil, auf die letzte Stelle nicht. Sie und die drei Zeilen des
Themenmodells sind der Stand vom 2026-10-14, also mit den Texten der Arbeit, und für die Texte aus
pypdf 7.1.0 (Punkt 68) nicht nachgerechnet; die Zeilen der Gremien hängen nicht an den Texten und
sind gleich geblieben.

**Was die zweite Quelle gebracht hat** (Punkt 58, Läufe vom 2026-10-14; „ergänzt" sind die
Dokumente, deren Gremium aus der Folge kommt, „mehrdeutig" die, deren Folge mehrere nennt):

| Profil | Dokumente | unbekannt vorher | nachher | ergänzt | mehrdeutig | bestätigt | Widerspruch |
|---|---|---|---|---|---|---|---|
| `duesseldorf` | 19 108 | 0 (0,0 %) | 0 (0,0 %) | 0 | 0 | 16 902 | 145 |
| `duesseldorf-2014` | 22 215 | 7 314 (32,9 %) | **1 655 (7,4 %)** | 5 659 | 1 535 | 14 464 | 30 |
| `duesseldorf-2025` | 4 095 | 55 (1,3 %) | **0 (0,0 %)** | 0 | 0 | 3 665 | 26 |
| `moenchengladbach` | 2 895 | 2 895 (100,0 %) | **1 275 (44,0 %)** | 1 620 | 1 275 | 0 | 0 |

Diese Zahlen sind der Stand **nach** dem Review vom 2026-10-14, das `POA` und `ACI` in
`[bodies.committees]` nachgetragen hat; wer in [befunde-2026-10-14.md](befunde-2026-10-14.md), § 6
oder weiter oben in [decisions.md](decisions.md), Punkt 58, auf 8,5 %, 1 896 und 1 541 stößt, liest
den Stand davor — die beiden Kürzel lösen 51 Nummern der alten Periode selbst auf und 190 über ihre
Organisation, und in der laufenden Periode alle 55.

**Der Interpretationsspielraum.** Das Gremium aus der Drucksachennummer ist eine **Ablesung**, keine
Schätzung, und die Beratungsfolge bestätigt sie: wo der Server eine liefert (18 707 Dokumente),
steht das Gremium der Nummer in 98,9 % der Fälle darin, bei allen zehn Bezirksvertretungen zu
100,0 %; über die Dokumente mit eindeutiger Folge sind es 16 902 von 17 047 (**99,1 %**). Die
gelernte Abbildung ist damit so gut wie die Quelle, aus der sie kommt — dieselbe Rechnung auf der
alten Periode (30 Organisationen, 99,8 %) und der laufenden (32, 99,3 %) widerspricht in keiner der
29 beziehungsweise 30 gemeinsamen Zeilen. Der passende Ausschuss dagegen ist eine Schätzung aus
Wörtern und sagt nichts darüber, wo ein Dokument hätte beraten werden müssen.

**Warum die Folge nicht entscheidet, wenn sie mehrere nennt.** Der Server liefert die Liste
**sortiert und entdoppelt**, die Reihenfolge der Beratung ist also nicht in den Daten; damit fällt
die naheliegende Regel „die erste Station" weg. Fünf Regeln, die ohne Reihenfolge auskommen, sind
gegen die Nummer gemessen — die beste („die seltenste Organisation") trifft 993 von 1 658 Fällen
(**59,9 %**) in der Hauptperiode und 214 von 371 (57,7 %) in der alten, gegen 99,1 % bei eindeutiger
Folge. Eine Regel, die in zwei von fünf Fällen ein erfundenes Gremium in genau die Spalte schreibt,
die die Seite zeigt, ist keine Quelle; der ehrliche Anteil „unbekannt" ist das bessere Ergebnis.
Darum bleiben 1 535 Dokumente der alten Periode und 1 275 Mönchengladbachs „ohne erkanntes Gremium",
obwohl ihre Folge Gremien nennt.

**Die Einwände.**

1. **Leckage beim Klassifikator.** Ein Teil der Güte hängt daran, dass der Volltext die
   Beratungsfolge und darin den Namen des Ausschusses nennt (ABA 100 %, OVA 91,7 %) — und der
   Zielwert kommt aus derselben Drucksachennummer, deren Kürzel der Text ebenfalls trägt. Ohne die 44
   Wörter mit „ausschuss" sind es 0,929 / 0,864; **die Zahlen sind eine Untergrenze, kein Befund über
   die Zuordenbarkeit**. Die Beratungsfolge **ist** inzwischen gebaut (Punkt 58), aber nur als Quelle
   des beratenden Gremiums — der Klassifikator lernt und wird weiter an der Nummer gemessen. Dass die
   Folge auch das Label geben könnte, das *nicht* im Text steht, ist der offene Teil des Vorschlags
   aus dem Befundbericht ([todo.md](todo.md), Punkt 30 a).
2. **Die 145 Widersprüche der Hauptperiode sind keine Parserfehler**, und sie zerfallen in zwei
   Klassen, die beide für die Nummer sprechen (gemessen 2026-10-14, eingefroren in
   `tests/golden/test_bodies_reference.py`): bei **88** Dokumenten hat das Kürzel der Nummer *keine
   eigene Organisation* und teilt sie mit einem anderen Gremium (BAU → SEBD 57, RPAU → RAT 30,
   WPA → RAT 1) — die Folge *kann* `BAU` nicht nennen; bei **57** haben beide eine, und die Folge
   nennt eine andere Beratungsstation (RAT → HFA 14, OVA → RAT 9, KUA → RAT 8, …). Die zweite Klasse
   ist der Grund für die Reihenfolge der Quellen: **die Folge ist ein Weg, die Nummer ist eine
   Akte.** Wer die Folge vorzieht, verschiebt Dokumente auf das Gremium, das sie zuletzt angefasst
   hat.
3. **Die Abbildung Organisation → Kürzel ist aus diesem Datenstand gelernt und nicht amtlich.** Sie
   ruht auf den 17 047 eindeutigen Dokumenten der Hauptperiode, hat 145 Gegenstimmen (0,9 %) und ist
   **nicht umkehrbar**: mehrere Kürzel zeigen auf dieselbe Organisation. Ein neuer Abruf kann andere
   Organisationen liefern; die Tabelle im Profil ist darum datiert und mit `georep learn-bodies`
   nachzurechnen. `gr/27` bleibt offen (1 Dokument der Hauptperiode, 21 der alten, keines mit
   eindeutiger Folge) — welches Gremium das ist, sagen die Daten nicht.
4. **Vier von fünf BV-Dokumenten bleiben in der Restklasse.** Konrads Frage, ob sich jedem
   Schriftstück ein Ausschuss zuordnen lässt, ist damit mit Nein beantwortet.
5. **Die Themennummern gelten nur für diesen Datenstand**; ein Lauf über andere Dokumente vergibt sie
   neu. Nur das Kürzel eines gesäten Themas ist stabil. Sechs Personennamen überleben den
   Namensfilter, weil sie nie neben einer Amtsbezeichnung stehen; eine Mandatsträgerliste aus OParl
   `memberships` würde das schließen und ist nicht abgerufen.
6. **Die Saat kostet Kohärenz**: NPMI fällt von +0,4208 auf +0,3349 — bezahlt für Namen statt
   Nummern. In **Mönchengladbach** ist die Saat seit Punkt 58 ganz aus (`topics.seed = "none"`): acht
   Ausschüsse bekamen dort ein Thema aus 11 bis 21 Texten, und ihre Namen standen danach in der
   Sensitivitätstabelle — eine Zuordnung, die 650 Texte aus 2 895 Dokumenten nicht tragen.
7. **Mönchengladbach hat sein Gremium nur aus der Beratungsfolge**, also aus der schwächeren der
   beiden Quellen, und 44,0 % bleiben offen; der Ausschuss-Klassifikator ist dort aus demselben Grund
   abgeschaltet wie die Saat. In der Periode 2014 bis 2020 sind 7,4 % offen, und ihre 30 Widersprüche
   stehen gegen nur 14 464 Bestätigungen.

## 11. Die Monatsreihe

**Die Frage.** Wie verteilen sich die Dokumente und die Treffer über die Zeit — und wie weit ist eine
laufende Periode gekommen?

**Die Rechnung.** `analysis/timeline.py` zählt je Monat des Vorlagendatums die Dokumente, die mit
Text und die mit mindestens einem Treffer (`monatsreihe.parquet`, stadtweit) und zusätzlich die
Treffer je Monat und Wahlbezirk (`wahlbezirke_monate.parquet`). Es ist eine Zählung, keine Schätzung;
die Nachbedingung hält sie gegen `hits_by_district`, die Summe über die Monate muss also die Treffer
der Auswertung ergeben.

**Die Zahlen** (Seiten, Abschnitt `#monate`; die Zeile `duesseldorf` mit den Texten aus pypdf 7.1.0,
seit dem 2026-11-18 — mit den Texten der Arbeit hatte ihr erster Monat 81 Dokumente mit Treffer):

| Datensatz | Monate | erster | letzter |
|---|---|---|---|
| `duesseldorf` | 61 | September 2020: 135 Dokumente, 133 mit Text, 82 mit Treffer | September 2025: 131 / 131 / 76 |
| `duesseldorf-2014` | 77 | Mai 2014: 9 / 9 / 7 | September 2020: 103 / 103 / 65 |
| `duesseldorf-2025` | 14 | September 2025: 106 / 105 / 66 | Oktober 2026: 52 / 51 / 27 |
| `moenchengladbach` | 61 | September 2020: 19 / **0** / 0 | September 2025: 12 / **0** / 0 |

Die laufende Periode gegen dieselben dreizehn Monate der Hauptperiode (Befundbericht § 3, die Seite
der Hauptperiode seit dem 2026-11-18 nachgerechnet): 4 043 gegen 4 365 Dokumente, 2 146 (53,1 %)
gegen 2 400 (55,0 %) mit Treffer, Median je Monat 332 gegen 379. Die Rangfolge der Bezirke nach
Treffern gleicht der Hauptperiode mit **Spearman 0,8431**. Mit den Texten der Arbeit in der
Hauptperiode waren es 2 390 (54,8 %) und 0,8261.

**Der Interpretationsspielraum.** Der Rhythmus ist der der Ratsarbeit und keine Eigenschaft der
Methode: Dezember 131 und Juli 176 gegen Juni 488 sind Sitzungs- und Ferienpausen. Dass dreizehn
Monate laufende Periode wie dreizehn Monate Hauptperiode aussehen, ist die stärkste Aussage dieses
Abschnitts — sie stützt, dass der Abruf der laufenden Periode denselben Korpus sieht wie damals, und
nicht mehr.

**Die Einwände.**

1. **Der letzte Monat ist angeschnitten.** `2025/` endet mit Oktober 2026 (52 Dokumente am
   Abrufdatum 13.10.2026); er bleibt im Dreizehnmonatsvergleich darum draußen. Jede Reihe einer
   offenen Periode hat diesen Rand.
2. **Das Datum ist das der Vorlage, nicht der Beratung.** Ein Dokument erscheint in dem Monat, in dem
   es angelegt wurde; wann es beraten oder beschlossen wurde, steht nicht in dieser Reihe (und
   überhaupt nicht auf der Seite, § 10).
3. **Die Reihe erbt die Textlücke ihrer Stadt.** Mönchengladbachs erster und letzter Monat haben 19
   beziehungsweise 12 Dokumente und **null** mit Text; die Spalte „mit Treffer" ist dort über ganze
   Monate hinweg 0, ohne dass in diesen Monaten weniger passiert wäre. Wer die Reihe dieser Stadt
   liest, liest die Ausspielpolitik ihres Ratsinformationssystems mit (§ 8).
4. **Verschiedene Periodenlängen sind nicht normiert.** 77 Monate gegen 61 gegen 14: absolute Summen
   über eine Reihe sind zwischen den Datensätzen nicht vergleichbar, Mediane je Monat schon.
5. **Kein Trendtest.** Die Seite zeichnet die Balken und nennt die Zahlen; eine Regression über die
   Zeit, eine Saisonbereinigung oder ein Test auf einen Bruch ist nicht gerechnet.

## 12. Die Einwände, gesammelt

| Einwand | wo er wirkt | sagt die Seite es? |
|---|---|---|
| Wörterbuchgröße treibt die Trefferzahl (r = 0,76) | jede Kennzahl mit Treffern im Zähler | **ja**, Absatz in „Methode und Grenzen", plus Karteneinfärbung „Treffer je Begriff" |
| Ausreißer 1 und 10 sind von Hand gewählt | Tabelle 5, zweite Spalte | seit Punkt 61 **ja**: der Absatz nennt sie als Entscheidung über diesen Datensatz, und seit dem 2026-11-18 mit ihren Plätzen, wenn sie nicht die höchsten Quoten haben (Hauptperiode 1 und 3, Periode 2014 bis 2020 2 und 9; § 2) |
| Zweite Spalte nach Ansehen der Daten entstanden | Tabelle 5 | **ja, seit Punkt 61**: der Spaltenkopf sagt „explorativ", darunter zwei Sätze mit beiden p-Werten (auf `main`, noch nicht veröffentlicht) |
| n = 41 ist die Grundgesamtheit, kein p-Wert-Fall | alle Regressionen | nein |
| Kein Konfidenzintervall neben dem p-Wert | alle Regressionen | nein — offene Empfehlung, § 6 Punkt 4 |
| Umlaute sind Wortgrenzen im Matcher („Köölberg" trifft „ölberg") | jede Trefferzählung | **nein**, nur als Kommentar im Quelltext |
| Normierung auf Wahlberechtigte nimmt die falsche Verzerrung heraus | Trefferquote | ja, im Absatz zur Wörterbuchgröße |
| „schulweg" zählt mit, wird nicht angezeigt: 143 Dokumente, und 127 der 876 Treffer des Bezirks 22 (14,5 %) hängen allein an ihm (mit den Texten der Arbeit 144 und 127 der 869, 14,6 %) | Trefferquote Bezirk 22 | ja, in der Liste der stadtweiten Begriffe und als Fußnote |
| Endogenität der Parteianteile | § 9, Modell C in § 5 | nein |
| „Unbekannt" bei Urheber und Gremium misst die Konfiguration mit, nicht nur die Quelle | § 9, § 10 | teilweise: jede Seite zeigt ihren Anteil offen und nennt seit Punkt 59 die Zähler je Quelle (Dokumentart / Titel / Textkopf) |
| Mehrfachtests ohne Korrektur (52 in der Gewichtungstabelle) | § 6 | nein; Bonferroni nur bei den Parteien |
| Themenmodell-Leckage über die Beratungsfolge im Text | § 10 | teilweise: die Seite nennt „davon ohne Ausschussberatung" je Zeile |
| Die Beratungsfolge entscheidet nur bei genau einem Gremium; der Rest bleibt offen | § 10 | **ja**, seit Punkt 58 nennt der Abschnitt „Gremien" beide Quellen, die Übereinstimmungen, die Widersprüche und die mehrdeutigen Fälle in einem Satz |
| Die Abbildung Organisation → Kürzel ist gelernt, nicht amtlich (Reinheit 99,1 %) | § 10 | nein — sie steht datiert im Profil und ist mit `georep learn-bodies` nachzurechnen |
| Perioden nicht gleich lang, gleiches Wörterbuch, umgerechnete Wahlzahlen | § 7 | **ja**, eigener Absatz „Wie belastbar ist das?" |
| Städte nicht der Höhe nach vergleichbar (Textlücke, Bezirksgröße, Geometriestand) | § 8 | **ja**, Abschnitt „Vergleichbarkeit" |
| Kontextdaten vom 31.12.2021, Wahl 2025 | § 5 | ja |
| Straßen über Bezirksgrenzen zählen für jeden Bezirk | jede Trefferzählung | ja, in „Methode und Grenzen" |
| Labels, die sich nur durch ein Komma unterscheiden, fallen zusammen | Wörterbuch | ja |

## 13. Was als nächste Auswertung offen ist

Die offenen Auswertungen stehen als Aufgaben in [todo.md](todo.md), Punkt 30: ein
Ausschussklassifikator auf der Beratungsfolge statt auf der Drucksachennummer, ein Satz dazu, dass
Umlaute im Matcher Wortgrenzen sind, ein Konfidenzintervall oder Permutationstest neben dem p-Wert von
Tabelle 5 und eine Typfilterung der Wikidata-Orte. Die vier Vorschläge des Befundberichts
([befunde-2026-10-14.md](befunde-2026-10-14.md), § 6, Punkte 1 bis 4) sind am 2026-10-14 umgesetzt
(Punkte 58 bis 61), sein fünfter, die Flächen Mönchengladbachs zum Stand der Wahl, am 2026-10-15
(Punkt 65); was davon an Zahlen offen bleibt, steht in den §§ 8 bis 10 oben.

**Bewusst nicht gemacht**, je mit Grund im Review: „schulweg" aus der Zählung nehmen (§ 2.3), die
Ausreißer automatisch bestimmen (§ 2.7), Erwähnungen statt Dokumente zählen (§ 2.5), die
Ausschlussliste programmatisch erzeugen (§ 2.2), Einbettungen für das Themenmodell
([themenmodell-2026-10.md](themenmodell-2026-10.md), § 5), ein Umschalter „je 1000 Wahlberechtigte"
als eigenes Radio und fünf weitere Normierungen
([skalierung-2026-10.md](skalierung-2026-10.md), § 5).
