# Bartzschs Methodik, kritisch geprüft (2026-10-12)

Der Rückstand nennt den Auftrag (`docs/todo.md`, Punkt 4): die Entscheidungen der Bachelorarbeit durchgehen,
so wie `georep` sie heute umsetzt, jede mit ihrer Wirkung auf die Zahlen, ihren Alternativen und einer
Empfehlung. Grundlage ist `v0.11.0`, der Stand, der die Arbeit exakt reproduziert (Tag `bartzsch-exakt`,
`docs/decisions.md`, Punkt 43). Alle Zahlen sind am 2026-10-12 auf der Referenz unter `reference/` gemessen,
41 Wahlbezirke, 306 Stimmbezirke, 19 108 Dokumente, 5841 Begriffe. Die Kennzahlen aus § 1 und die Wirkung
aus § 4 rechnet `docs/methodik-review-2026-10-messung.py` nach (`uv run python
docs/methodik-review-2026-10-messung.py`, rund 20 s auf der Referenz); Tabelle 5 und die Wirkung der Regeln
frieren zusätzlich die slow-Tests in `tests/golden/test_pipeline.py` ein.

Dies ist ein Review, keine Neubewertung der Arbeit. Die Arbeit hat aus einem Datensatz, den vorher niemand
zusammengetragen hatte, eine prüfbare Zahl gemacht; die Kritik unten gilt dem Verfahren, nicht dem Befund.
Ihr Befund — die Trefferquote erklärt die Wahlbeteiligung nicht — hält allen Prüfungen stand, die dieses
Repository seither gerechnet hat, und wird von den Kontrollvariablen (Option 03) bestätigt.

## 1. Maßzahlen des heutigen Stands

| Größe | Wert (2026-10-12, Referenz) |
|---|---|
| Begriffe im Wörterbuch | 5841: 2897 Straßennamen aus OSM, 1307 Ortslabels aus Wikidata/Wikipedia (68 kommen in beiden vor), dazu 1705 `str.`-Varianten |
| Begriffe je Wahlbezirk | Median 147, Minimum 81 (Bezirk 3), Maximum 812 (Bezirk 1) |
| Dokumenthäufigkeit je Begriff | Median 1, Mittel 5,3, 75-%-Quantil 4, 90-%-Quantil 15, 95-%-Quantil 27, 99-%-Quantil 64, Maximum 205 |
| Summe der Treffer | 29 573 Dokument-Bezirk-Paare, aus 31 024 Begriff-Dokument-Paaren und 51 887 Bezirk-Begriff-Dokument-Tripeln |
| Tabelle 5, alle 41 | Steigung 62,1337, Achsenabschnitt 49,1993, r = 0,1612, R² = 0,0260, p = 0,31385 |
| Tabelle 5, ohne 1 und 10 | Steigung 215,3341, Achsenabschnitt 40,5046, r = 0,3385, R² = 0,1146, p = 0,03507, n = 39 |

Zwei Zahlen rahmen alles Weitere ein:

- **Die Trefferzahl eines Wahlbezirks hängt an der Größe seines Wörterbuchs, nicht an seiner
  Einwohnerzahl.** Korrelation Treffer gegen Zahl der Begriffe: **r = 0,767**; Treffer gegen Wahlberechtigte:
  r = 0,176; Trefferquote gegen Zahl der Begriffe: r = 0,724. Wer mehr Straßen und Orte im Wörterbuch hat,
  wird häufiger getroffen. Das ist die wichtigste Grenze der Methode, und sie steht heute nicht auf der
  Seite.
- **Die Wahlberechtigten schwanken kaum**: 10 168 bis 13 086, Verhältnis 1,287. Die Normierung auf
  Wahlberechtigte ändert die Rangfolge der Bezirke deshalb fast nicht; sie ist richtig, aber sie ist nicht
  die Normierung, die fehlt (siehe § 2.7).

## 2. Die Entscheidungen der Arbeit

### 2.1 Das Wörterbuch: OSM-Straßen je Stimmbezirk, Wikidata/Wikipedia-Orte mit Koordinate

**Was die Arbeit tut.** Je Stimmbezirkspolygon fragt sie Overpass nach den Straßennamen darin (`streets_osm`)
und Wikidata-SPARQL plus die Wikipedia-GeoSearch nach allem, was in diesem Gebiet eine Koordinate hat
(`pois_wiki`). Beides wird je Wahlbezirk vereinigt, kleingeschrieben, um die `str.`-Variante ergänzt und ist
dann das Wörterbuch dieses Bezirks (`search/dictionary.py`, Kapitel 4.2 der Arbeit).

**Was es mit den Zahlen macht.** Der Ortsteil der Abfrage filtert nach *Koordinate*, nicht nach *Typ*: in
die 1309 Ortszeilen (1307 verschiedene Labels) geraten neben Plätzen und Parks auch Gerichte, Theater,
Behörden, Vereine, Zeitungen, Ausstellungen und Ereignisse („Amoklauf von Düsseldorf am 9. und 10. März
2017", „Skilanglauf-Weltcup in Düsseldorf", „Von hier aus – Zwei Monate neue deutsche Kunst in
Düsseldorf"). 460 der 1309 Rohlabels tragen
den Stadtnamen. Das Gefälle der Wörterbuchgrößen (81 bis 812) folgt daraus: die Innenstadt hat nicht
zehnmal so viele Straßen wie der Bezirk 3, aber zehnmal so viele Wikipedia-Artikel mit Koordinate.
Außerdem tragen 315 Labels eine Klammer, und in 277 davon steht der Stadtname darin („Neue Synagoge
(Düsseldorf)"); als Suchbegriff sind diese 277 tot, weil die Klammer im Dokumenttext nicht vorkommt —
**alle 277 haben Dokumenthäufigkeit 0.** Von den übrigen 38 Klammerlabels trifft genau eines, nämlich
„Kom(m)ödchen" mit 2 Dokumenten; dort gehört die Klammer zum Namen.

**Alternativen.** (a) Nach Wikidata-Typ filtern (`P31` auf Straße, Platz, Park, Gebäude, Gewässer …): genauer,
kostet eine SPARQL-Änderung und einen neuen Abruf, und die Typhierarchie ist für Kommunalobjekte lückenhaft.
(b) Den Klammerzusatz abschneiden statt die Labels zu behalten: macht aus 277 toten Begriffen 277 lebende und
hebt die Treffer, aber „Neue Synagoge" trifft dann auch den Satz über eine andere Synagoge. (c) Nur Straßen,
keine Orte: verliert die Plätze und Parks, die in Ratsdokumenten viel vorkommen. (d) Die Regel aus § 3.1
dieses Reviews, die Einrichtungen mit Stadtnamen erkennt, ohne den Typ zu brauchen.

**Empfehlung.** Keine Typfilterung (sie erfordert einen neuen Netzabruf von Stunden und wäre je Stadt neu zu
prüfen), aber die Regel aus § 3.1, und den Klammerzusatz weiter *nicht* abschneiden: 277 Begriffe mit
Häufigkeit 0 kosten nichts und das Abschneiden erzeugt falsche Treffer. Dass die Wörterbuchgröße die
Trefferzahl bestimmt, gehört in einem Satz auf die Seite (§ 4).

### 2.2 Die Ausschlussliste der Stadtteil- und Stadtbezirksnamen (`search.exclude`)

**Was die Arbeit tut.** 63 Namen — der Stadtname, die Düssel, zehn „Stadtbezirk N" und die Stadtteilnamen —
fallen nach der Bereinigung aus den Orten (`prep/pois.py`, Reihenfolge der Arbeit). Begründung im Profil:
„zu grob für einen Wahlbezirk".

**Was es mit den Zahlen macht.** Gemessen, indem die 63 Namen einmal als eigenes Wörterbuch über den Korpus
gelaufen sind: sie würden zusammen **19 644** Begriff-Dokument-Paare erzeugen, mehr als es Dokumente gibt
(19 108). Allein „düsseldorf" steht in **8385** Dokumenten (43,9 % des Korpus), „eller" in 569, „garath" in
496, „gerresheim" in 477, „benrath" in 411, „stadtbezirk 10" in 330. Ohne die Liste wäre die Trefferzahl
jedes Bezirks von seinen Stadtteilnamen dominiert, und ein Stadtteil liegt oft in mehreren Wahlbezirken.

**Alternativen.** (a) Stadtteilnamen behalten und dem Stadtteil statt dem Wahlbezirk zurechnen: eine andere
Auswertungsebene, interessant, aber nicht diese Frage. (b) Sie mit einem Gewicht unter 1 mitzählen (Option 06
hat dafür den Mechanismus): verschiebt das Problem auf die Wahl des Gewichts. (c) Die Liste programmatisch
aus den Gebietsnamen der Quelle erzeugen statt sie von Hand zu pflegen: `precincts.name_property` und die
Stadtbezirksspalte liefern die Namen schon, der Stadtteilname steht in Düsseldorf aber in keiner der
abgerufenen Dateien.

**Empfehlung.** Liste bleibt, Entscheidung der Arbeit ist richtig und mit 19 644 gegen 29 573 Treffern
deutlich belegt. Die Pflege von Hand bleibt der Preis; das Runbook für eine neue Stadt
(`docs/runbook-stadt.md`) nennt sie schon als Schritt. Die Liste wächst nicht mit — sie ist einmal je Stadt zu
schreiben.

### 2.3 `hide_in_display = ["schulweg"]`: zählt, wird nicht angezeigt

**Was die Arbeit tut.** `analyse.py` entfernt „schulweg" aus der angezeigten Begriffsliste, nicht aus der
Trefferzählung (Kapitel 4.3.5; der Befund steht als Risiko 9 in `docs/baseline-2026-10-10.md`). `georep`
übernimmt das als Settings-Schlüssel, `analysis/hits.py` filtert nur die Anzeigeliste.

**Was es mit den Zahlen macht.** „Schulweg" ist ein echter Straßenname in Düsseldorf-Kalkum und steht in
**144** Dokumenten — die sechsthöchste Dokumenthäufigkeit aller 5841 Begriffe. Er gehört zum Wörterbuch des
Wahlbezirks 22. Dessen 262 Begriffe treffen zusammen 869 Dokumente; ohne „schulweg" bleiben **742**, also
**127 Dokumente (14,6 %) hängen allein an diesem Begriff**. Die Trefferquote des Bezirks 22 fiele von 0,0688
auf 0,0587 und damit von Platz 7 unter den Median (0,0613). Der Grund ist offensichtlich: „Schulweg" steht in
Ratsdokumenten fast immer als Gattungswort („Sicherheit auf dem Schulweg"), nicht als Adresse.

**Alternativen.** (a) So lassen: die Arbeit hat den Fall gesehen und pragmatisch gelöst, aber die Lösung
versteckt ihn — die Zahl bleibt falsch, nur unsichtbar. (b) Den Begriff auch aus der Zählung nehmen: ehrlich,
aber dann wird in Kalkum ein echter Straßenname nicht gefunden. (c) Gewicht 0,5 wie bei den Anträgen
(Option 06): willkürlich. (d) Verallgemeinern: ein Begriff, der ein Gattungswort der Verwaltungssprache ist,
zählt nicht — das wäre eine Stoppwortliste je Sprache, nicht je Stadt, und müsste „marktplatz", „rathaus",
„friedhof" mitnehmen und damit viele echte Orte treffen. (e) Die Begriffe mit auffällig hoher
Dokumenthäufigkeit benennen und dem Leser zeigen (Regel 2, § 3.2): „schulweg" steht mit 144 Dokumenten
sicher über jeder sinnvollen Schwelle.

**Empfehlung.** **Die pragmatische Lösung der Arbeit ist nicht richtig, aber die Richtung ihrer Korrektur ist
offen, und darum bleibt sie** — mit zwei Ergänzungen: der Begriff erscheint in der Liste der stadtweiten
Begriffe (Regel 2) mit seinen 144 Dokumenten und seinem Wahlbezirk, und die Fußnote der Seite sagt weiter,
dass er mitgezählt wird. Einen Schalter, der ihn und die 54 weiteren Begriffe über der Schwelle aus der
Zählung nimmt, gibt es bewusst nicht (`docs/decisions.md`, Punkt 44b): die Schwelle trifft auch echte
Ortsnamen. Eine Einzelregel für ein Wort ist in keiner Richtung übertragbar, eine Schwelle ist es — als
Offenlegung, nicht als Korrektur.

### 2.4 Die Matching-Regeln

**Was die Arbeit tut.** FlashText (Aho-Corasick in reinem Python) über den kleingeschriebenen Text ab dem
ersten Vorkommen des Markers „betrifft". Der Vertrag steht lesbar in `tests/property/oracle_matcher.py`:
Treffer an Wortgrenzen (ASCII-Buchstaben, Ziffern, Unterstrich sind Wortzeichen, **Umlaute sind Grenzen**),
der längste Begriff gewinnt, keine Überlappung, das beendende Grenzzeichen ist verbraucht, Groß- und
Kleinschreibung zählt nicht. Zu jedem Begriff mit „straße" kommt die Variante mit „str." ins Wörterbuch.

**Was es mit den Zahlen macht.** Drei Eigenheiten sind messbar:

1. **Umlaute als Grenzen.** „Köölberg" trifft „ölberg" — hypothesis hat den Fall gefunden, er steht als Test
   fest (`docs/decisions.md`, Punkt 11). In der Praxis selten, aber die Regel ist nicht die, die man meint.
2. **Die Abkürzungsvariante ist einseitig und ersetzt Teilstrings.** „Gumbertstraße" bringt „gumbertstr."
   mit, aber ein Dokument, das „Gumbertstr" ohne Punkt schreibt, trifft nicht, und andere Abkürzungen
   (Pl., Weg, „A.-Str.") gibt es nicht. Ersetzt wird außerdem jedes Vorkommen von „straße", nicht nur das
   am Wortende: aus „Straßenbahn Düsseldorf" wurde im Wörterbuch der Arbeit der Begriff „str.nbahn
   düsseldorf" (am 2026-10-12 aufgefallen, als die Regel aus § 3.1 das Label entfernte und 114 statt 113
   Begriffe verschwanden). Der Begriff trifft nichts und ist harmlos, aber er zeigt die Art der Regel. Die
   Berichtsseite liest dieselben Paare (`report/search.py`), die Regel steht also nur an einer Stelle.
3. **Straßen über Bezirksgrenzen zählen für jeden Bezirk.** „Grafenberger Allee" (205 Dokumente, die höchste
   Häufigkeit überhaupt) steht in den Wörterbüchern von 7, 8, 9, 10 und 28; „Münchener Straße" (135) in
   sieben Bezirken. Jedes dieser Dokumente zählt für jeden dieser Bezirke einmal. Von den 51 887
   Bezirk-Begriff-Dokument-Tripeln bleiben nach der Vereinigung je Bezirk 29 573 — der Rest sind
   Mehrfachzählungen
   innerhalb eines Bezirks; die Mehrfachzählung *zwischen* Bezirken bleibt vollständig erhalten und ist
   gewollt (eine Straße liegt wirklich in beiden).

**Alternativen.** (a) Treffer dem Bezirk zuschlagen, in dem der *längste Teil* der Straße liegt: macht aus
einer Mengenfrage eine Längenfrage, verliert aber die Information, dass ein Dokument beide Bezirke betrifft.
(b) Den Treffer zwischen den Bezirken aufteilen (je 1/5 für die Grafenberger Allee): Option 06 kann das als
Gewicht `bezirke`, und die Sensitivitätstabelle zeigt, dass es die Rangfolge kaum ändert. (c) Mehr
Abkürzungen und eine Normalisierung ohne Punkt: billig, aber jede neue Variante ändert den Golden Master.
(d) Ein Matcher mit echten Unicode-Wortgrenzen (Regex, `pyahocorasick`): sauberer, bricht die exakte
Reproduktion (`docs/decisions.md`, Punkt 14 hält die Nähte dafür offen).

**Empfehlung.** Matcher bleibt, Gewicht `bezirke` steht als Variante schon auf der Seite. Die Grenze
„Umlaute sind Wortgrenzen" gehört in einem Halbsatz in „Methode und Grenzen", weil sie niemand erwartet.

### 2.5 Die Zählung je Dokument statt je Erwähnung

**Was die Arbeit tut.** Ein Dokument zählt je Wahlbezirk einmal, auch wenn mehrere Begriffe des Bezirks
darin vorkommen und auch wenn ein Begriff zehnmal vorkommt: `hits_by_district` vereinigt die Dokument-IDs
über die Begriffe des Bezirks (`analysis/hits.py`). Mehrfachnennungen innerhalb eines Dokuments sind im Index
gar nicht gespeichert, der Matcher liefert eine Menge.

**Was es mit den Zahlen macht.** 51 887 Bezirk-Begriff-Dokument-Tripel werden zu 29 573 Treffern, Faktor
1,75 im
Mittel. Der Faktor ist nicht gleichverteilt: Bezirk 1 2,10, Bezirk 33 2,05, Bezirk 20 1,98 gegen Bezirk 3
1,48, Bezirk 27 1,49, Bezirk 10 1,53. Die Vereinigung dämpft also gerade die Bezirke mit großem Wörterbuch —
sie wirkt gegen den Effekt aus § 1 und ist damit die vorsichtigere Wahl.

**Alternativen.** (a) Erwähnungen zählen: ein Dokument, das eine Straße fünfzehnmal nennt, handelt
wahrscheinlich von ihr — aber ein Bebauungsplan nennt jede Anliegerstraße einmal pro Absatz, und der Matcher
müsste Zähler statt Mengen liefern (Vertrag und Index ändern sich, der Golden Master bricht).
(b) Die Tripel zählen (die 51 887): belohnt große Wörterbücher doppelt. (c) Nach Dokumentlänge
normieren: möglich, Option 06 hätte den Platz, misst dann aber eher Textsorten.

**Empfehlung.** Bleibt. Die Entscheidung der Arbeit ist hier die beste der drei, und sie ist mit den
gemessenen Faktoren begründbar: sie dämpft die Verzerrung, statt sie zu verstärken.

### 2.6 Die Trefferquote je Wahlberechtigte (Bartzschs Normierung)

**Was die Arbeit tut.** Trefferquote = Treffer / Wahlberechtigte des Wahlbezirks (`join_voters`), also
Dokumente pro Person; die Werte liegen zwischen 0,026 und 0,163. Die Regression setzt sie zur
Wahlbeteiligung in Prozent in Beziehung.

**Was es mit den Zahlen macht.** Fast nichts: die Wahlberechtigten schwanken nur um den Faktor 1,287 (10 168
bis 13 086). Die Korrelation Treffer gegen Wahlberechtigte ist 0,176 — die Normierung nimmt also wenig
Verzerrung heraus. Dagegen korreliert die Trefferquote mit der **Wörterbuchgröße** mit 0,724. Die Normierung
ist damit auf die Größe normiert, die nicht stört, und nicht auf die, die stört.

**Alternativen.** (a) **Je Begriff im Wörterbuch** (Treffer / Begriffe): nimmt genau die Verzerrung aus § 1
heraus und misst „wie oft wird ein Ort dieses Bezirks im Schnitt besprochen". Ändert die Rangfolge stark und
ist die inhaltlich interessantere Größe. (b) Je Fläche: misst Dichte, nicht Repräsentation. (c) Je Einwohner
statt je Wahlberechtigte: ehrlicher gegenüber Bezirken mit vielen Nichtwahlberechtigten, braucht die
Bevölkerungszahl je Wahlbezirk (die Kontextdaten aus Option 03 hätten sie). (d) Absolute Treffer ohne
Normierung: bei 1,287-facher Spannweite der Nenner kaum anders als heute. (e) Gewichtete Quoten (Option 06,
26 Varianten): schon gebaut, keine ändert das Vorzeichen des Befunds.

**Empfehlung.** Die Normierung der Arbeit bleibt die Hauptkennzahl (sie ist die der Fragestellung: Dokumente
je Wahlberechtigtem), aber **„Treffer je Begriff im Wörterbuch" gehört als zweite Kennzahl auf die Seite** —
sie ist mit `regression_pair(…, x=…)` eine Zeile Arbeit, braucht keinen neuen Abruf und beantwortet die
Frage, die § 1 aufwirft. Das ist der stärkste offene Punkt dieses Reviews und zugleich die Verbindung zu
`docs/todo.md`, Punkt 3 (Skalierung der Kennzahlen).

### 2.7 Die Ausreißer 1 und 10 (`analysis.exclude_districts`)

**Was die Arbeit tut.** Tabelle 5 hat zwei Spalten: alle 41 Wahlbezirke und dieselbe Regression ohne die
Bezirke 1 und 10, die beiden mit der höchsten Trefferquote. Die Arbeit nennt sie Ausreißer; `georep` hat die
Nummern im Profil, nicht im Code (`analysis.exclude_districts`, Fundament F3).

**Was es mit den Zahlen macht.** Robust gemessen (Median 0,0613, MAD 0,0097) liegt Bezirk 1 bei z = 10,43 und
Bezirk 10 bei z = 4,04; der dritthöchste Bezirk 2 bei 2,38. Die beiden sind also wirklich abgesetzt, und das
Weglassen ist nicht willkürlich. **Warum** sie abgesetzt sind, ist bei beiden verschieden:

- **Bezirk 1** (Altstadt/Carlstadt/Stadtmitte) hat 812 Begriffe im Wörterbuch, das Fünffache des Medians,
  weil in der Innenstadt jedes zweite Gebäude einen Wikipedia-Artikel hat. Seine 1894 Treffer verteilen sich
  breit: der stärkste Begriff ist „hofgarten" mit 172 Dokumenten.
- **Bezirk 10** (Flingern) hat nur 107 Begriffe, aber 1189 Treffer, und davon hängen **177 (14,9 %) allein am
  Ort „Stadtwerke Düsseldorf"** — der zweithäufigste Begriff des ganzen Datensatzes (190 Dokumente). Dazu
  kommt die Grafenberger Allee (205 Dokumente, geteilt mit vier anderen Bezirken). Der Bezirk ist Ausreißer,
  weil der Stadtkonzern dort seinen Sitz hat.

**Alternativen.** (a) Ausreißer über eine Regel bestimmen statt über zwei Nummern (robuster z, Cook-Distanz):
übertragbar, und das Profil bräuchte keine Liste. (b) Robuste Regression (Huber, Theil-Sen) statt
Weglassen: nutzt alle 41 Punkte. (c) Die Ursache beheben statt den Punkt zu entfernen — genau das tut Regel 1
(§ 3.1).

**Empfehlung.** Die Nummern bleiben, weil Tabelle 5 der Arbeit sie nennt und die Seite beide Spalten zeigt;
die Ursache von Bezirk 10 wird aber behoben (§ 3.1), und nach der Behebung fällt Bezirk 10 von z = 4,04 auf
z = 2,69 und ist kein Ausreißer mehr (Bezirk 2 liegt bei 2,58, Bezirk 30 bei 2,54). Bezirk 1 bleibt bei
z = 9,71: **er ist kein Artefakt der Benennung, sondern eines der Wörterbuchgröße** — und damit wieder § 1.
Eine automatische Ausreißerregel ist ein eigener Vorschlag und hier nicht umgesetzt: sie würde die Spalte
„ohne Ausreißer" der Arbeit von Lauf zu Lauf anders füllen.

### 2.8 Die Regression von Tabelle 5

**Was die Arbeit tut.** `scipy.stats.linregress` auf 41 Punkten, x = Trefferquote, y = Wahlbeteiligung in
Prozent; dieselbe Rechnung ohne die zwei Ausreißer. Ergebnis: r = 0,1612, p = 0,31385 über alle, r = 0,3385,
p = 0,03507 ohne die beiden.

**Was es mit den Zahlen macht.** Drei Dinge sind zu sagen, und die Arbeit sagt sie nicht alle:

1. **n = 41.** Das ist eine kleine Stichprobe, und sie ist die ganze Grundgesamtheit — es gibt nicht mehr
   Wahlbezirke. Ein p-Wert beantwortet hier die Frage „wie wahrscheinlich wäre dieses Muster, wenn die
   Trefferquote zufällig verteilt wäre", nicht „gilt das auch für andere Städte".
2. **Die zweite Spalte ist nach Ansehen der Daten entstanden.** Wer die zwei höchsten Punkte entfernt und
   dann p = 0,035 berichtet, hat zwei Tests gerechnet und einen berichtet; das ist die klassische Form des
   zu optimistischen p-Werts. Die Arbeit berichtet beide Spalten, das ist redlich, aber die Deutung der
   zweiten als „signifikant" steht ohne Korrektur da.
3. **Mit Kontrollvariablen bleibt nichts übrig.** Option 03 (`docs/decisions.md`, Punkt 26) rechnet Tabelle 6
   mit dem Quartiersatlas: R² steigt von 0,03 auf 0,89, und die Trefferquote erklärt für sich nichts mehr.
   Das relativiert Tabelle 5 nicht nur, es ersetzt sie als Antwort. In `STATUS.md` steht die Zahl, auf der
   Seite steht der Abschnitt „Kontrollvariablen" direkt unter „Zusammenhang".

**Alternativen.** (a) Konfidenzintervall statt p-Wert: zeigt die Unsicherheit statt eines Schwellenurteils
und ist bei n = 41 die ehrlichere Darstellung. (b) Permutationstest: bei n = 41 billig und ohne
Normalverteilungsannahme. (c) Bonferroni oder Benjamini-Hochberg über die 26 Gewichtungsvarianten: die
Gewichtungstabelle zählt heute, wie viele Varianten p < 0,05 erreichen, und nennt den Bonferroni-Hinweis
schon (Option 06).

**Empfehlung.** Tabelle 5 bleibt, wie sie ist — sie ist die Zahl der Arbeit und die Seite reproduziert sie.
Ergänzt gehört ein Satz, der sagt, dass die zweite Spalte nach Ansehen der Daten entstanden ist, und der
Verweis auf Tabelle 6 steht schon da. Ein Konfidenzintervall statt oder neben p ist der nächste billige
Schritt.

### 2.9 Einrichtungen, die den Stadtnamen tragen

**Was die Arbeit tut.** Nichts. „Stadtwerke Düsseldorf" ist für sie ein Ort wie jeder andere, weil Wikidata
eine Koordinate dazu hat und die Koordinate im Wahlbezirk 10 liegt.

**Was es mit den Zahlen macht.** Gemessen am 2026-10-12: „stadtwerke düsseldorf" steht in **190** Dokumenten
und ist damit die **zweithöchste Dokumenthäufigkeit aller 5841 Begriffe** (Median 1, 90-%-Quantil 15,
99-%-Quantil 64, Maximum 205 für „grafenberger allee"). Weiter: „flughafen düsseldorf" 80, „hochschule
düsseldorf" 80, „messe düsseldorf" 61, „stadtsparkasse düsseldorf" 45, „feuerwehr düsseldorf" 43,
„heinrich-heine-universität düsseldorf" 17. Diese Dokumente handeln vom Stadtkonzern, vom Flughafen, von der
Hochschule — nicht von Flingern, Lohausen oder Derendorf. Ein Dokument über die Strompreise der Stadtwerke
zählt heute als Beleg dafür, dass der Rat über Flingern spricht.

**Alternativen.** (a) Einzelne Labels je Stadt in die Ausschlussliste schreiben: löst den Fall, ist aber
Handarbeit und nicht übertragbar — genau was `docs/todo.md`, Punkt 4 ausdrücklich nicht will.
(b) Nach Wikidata-Typ filtern (Organisation statt Ort): bräuchte einen neuen Abruf (§ 2.1).
(c) Über die Dokumenthäufigkeit gehen (Regel 2): trifft auch „hofgarten" und „schulweg", also mehr als die
Benennung, und ist eine andere Frage. (d) Eine Regel über den Namen: eine Einrichtung mit stadtweiter
Bedeutung trägt den Stadtnamen im Namen, ein Ort trägt ihn höchstens als Klammerzusatz des
Wikipedia-Lemmas. Das ist Regel 1.

**Empfehlung.** Regel 1 (§ 3.1), standardmäßig an, weil sie für jede Stadt gilt und keinen Abruf braucht;
ihre Grenze (ein Kurzname ohne Stadtnamen bleibt) steht in § 4.

## 3. Die beiden Regeln (umgesetzt am 2026-10-12)

### 3.1 Regel 1: „Einrichtung mit Stadtnamen" (`search.city_facilities`, Standard an)

Ein Ort aus Wikidata/Wikipedia ist eine **Einrichtung** und fällt aus dem Wörterbuch, wenn beides gilt:

1. **Benennung.** Nach dem Entfernen aller Klammerzusätze steht im Label der Stadtname am Ende — die
   letzten Wörter, so viele wie der Stadtname hat, damit „Stadtwerke Frankfurt am Main" auch greift
   („Stadtwerke Düsseldorf", „Messe Düsseldorf") — oder das Städteadjektiv irgendwo („Düsseldorfer
   Schauspielhaus"). Beides sind die deutschen Formen, einer Einrichtung den Namen ihrer Stadt zu geben. Ein
   Ort *innerhalb* der Stadt trägt den Stadtnamen dagegen vorangestellt, mit dem Ortsteil dahinter („Bahnhof
   Düsseldorf-Rath", „Düsseldorf Hauptbahnhof", „Düsseldorf Arcaden") — dort folgt dem Stadtnamen noch ein
   Wort, und das Label bleibt ein Ort.
2. **Kein Gattungswort.** Kein Wort des Labels endet auf ein Gattungswort aus `search.place_words`
   (stadtneutral in `defaults.toml`: bahnhof, haltepunkt, park, friedhof, wald, garten, see, gymnasium,
   krankenhaus, klinik, stadion …). Ein „Düsseldorfer Stadtwald" ist ein Ort, auch wenn er das Adjektiv
   trägt.

Beide Bedingungen gelten nur für Orte; **Straßen sind nie betroffen**, weil die Regel im Schritt `pois`
greift und das Straßenverzeichnis aus OSM nie durch sie läuft (ein Test hält das fest). Der Stadtname kommt
aus `city.name` und `city.adjective` des Profils, nie aus dem Code. `search.city_facilities_keep` im Profil
nimmt einzelne Labels wieder heraus.

Warum zwei Bedingungen und nicht eine, steht in `docs/decisions.md`, Punkt 44a, mit den gemessenen Zahlen
der drei geprüften Varianten (183, 140, 131 und 114 Labels). Die Kurzfassung: die Benennungsregel allein
erklärt 19 Labels mit Treffern zu Einrichtungen, die Orte sind (neun Bahnhöfe und Haltepunkte, die
Düsseldorf Arcaden, der Stadtwald, zwei Gymnasien, das Universitätsklinikum); die Gattungswortregel allein
lässt
„Stadtsparkasse Düsseldorf" (45 Dokumente) stehen, weil „park" in „Sparkasse" steckt — daher der Vergleich
auf das *Wortende*, nicht auf das Vorkommen. „halle" und „schule" stehen bewusst nicht in der Liste, sonst
blieben Tonhalle, Kunsthalle und Hochschule Orte.

### 3.2 Regel 2: „stadtweite Begriffe" (`search.citywide_quantile`, nur Anzeige)

Begriffe, deren Dokumenthäufigkeit über dem 99-%-Quantil liegt (auf der Referenz: über 64 Dokumenten, das
sind 55 der 5727 Begriffe mit Regel 1 und 58 der 5841 ohne sie), stehen im Abschnitt „Begriffe" der Seite
als eigene, aufklappbare Tabelle mit Dokumentzahl und Wahlbezirk. Die Schwelle ist ein Quantil oder ein
Vielfaches des Medians (`search.citywide_median_factor`), genau eines von beiden, und immer mindestens 1:
sonst gilt in einem dünnen Index jeder Begriff mit einem einzigen Dokument als stadtweit. Ob diese Begriffe
zusätzlich aus der Zählung fallen, ist ein eigener Schalter
(`search.citywide_exclude`), **standardmäßig aus**: die Liste ist eine Offenlegung, keine Korrektur. Sie
beginnt auf der Referenz mit „grafenberger allee" (205), „vennhauser allee" (176), „hofgarten" (172),
„königsallee" (146) und „schulweg" (144) — also genau mit den Fällen, die § 2.3 und § 2.7 beschreiben und
die keine Namensregel findet.

## 4. Wirkung auf die Zahlen (2026-10-12, Referenz)

Alle Zahlen aus einem Lauf `uv run georep run` über die volle Referenz am 2026-10-12; der slow-Test
`test_the_rules_change_the_reference_as_measured` friert sie ein.

Regel 1 trifft **113 der 1309 Ortslabels**, davon 40 mit Dokumenthäufigkeit über 0. Die stärksten:
Stadtwerke Düsseldorf (190), Hochschule Düsseldorf (80), Flughafen Düsseldorf (80), Messe Düsseldorf (61),
Stadtsparkasse Düsseldorf (45), Feuerwehr Düsseldorf (43), Kunstakademie Düsseldorf (28), Tonhalle
Düsseldorf (25), Düsseldorfer Schauspielhaus (22), Handwerkskammer Düsseldorf (19), Regierungsbezirk
Düsseldorf (17), Heinrich-Heine-Universität Düsseldorf (17), Kunsthalle Düsseldorf (17), Mahn- und
Gedenkstätte Düsseldorf (15), Polizeipräsidium Düsseldorf (14).

**Ort geblieben** sind 70 Labels, die den Stadtnamen tragen: 26 Bahnhöfe und Haltepunkte, 11 Schulen, 10
Parks, Gärten, Wälder und Friedhöfe, 7 Kliniken und Krankenhäuser, dazu die Fälle, die dem Stadtnamen ein
Wort nachstellen. 19 von ihnen haben Treffer: Düsseldorf Arcaden (18), Düsseldorfer Stadtwald (13),
Universitätsklinikum Düsseldorf (13), Düsseldorf Hauptbahnhof (6), Düsseldorf-Hellerhof (4), Bahnhof
Düsseldorf Flughafen (2), Düsseldorf-Hafen (2), Autobahndreieck Düsseldorf-Süd (2), zwei Gymnasien und sechs
weitere Bahnhöfe und Haltepunkte mit je einem Dokument. Im Profil steht genau eine Ausnahme: `Castello
Düsseldorf` (6 Dokumente), eine Veranstaltungshalle an einer Adresse in Reisholz, die die Benennungsregel
sonst für eine stadtweite Einrichtung hielte.

| Größe | Regeln aus (wie die Arbeit) | Regel 1 an |
|---|---|---|
| Orte im Wörterbuch | 1309 | 1196 |
| Begriffe | 5841 | 5727 |
| Begriff-Dokument-Paare | 31 024 | 30 272 |
| Summe der Treffer | 29 573 | 29 010 (−1,9 %) |
| Wahlbezirke mit geänderter Trefferzahl | — | 12 von 41, alle nach unten |
| Bezirk 10 (Flingern) | 1189 Treffer, Quote 0,100592 | 1012, Quote 0,085618 (−14,9 %) |
| Bezirk 1 (Altstadt) | 1894, Quote 0,162757 | 1761, Quote 0,151328 (−7,0 %) |
| Bezirk 23 (Lohausen, Flughafen und Messe) | 964, Quote 0,073667 | 873, Quote 0,066713 (−9,4 %) |
| Bezirk 6 (Derendorf, Hochschule) | 727 | 663 (−8,8 %) |
| Bezirk 13 (Feuerwehr) | 590 | 548 (−7,1 %) |
| Tabelle 5, alle 41 | 62,1337 · x + 49,1993; r 0,1612; R² 0,0260; p 0,31385 | 79,9539 · x + 48,1709; r 0,1891; R² 0,0358; p 0,23641 |
| Tabelle 5, ohne 1 und 10 | 215,3341 · x + 40,5046; r 0,3385; R² 0,1146; p 0,03507 | 216,2416 · x + 40,5715; r 0,3351; R² 0,1123; p 0,03705 |
| Bezirk 10 als Ausreißer | robuster z = 4,04 (dritthöchster: 2,38) | z = 2,69 (zweithöchster: 2,58) — kein Ausreißer mehr |
| Bezirk 1 als Ausreißer | z = 10,43 | z = 9,71 — unverändert Ausreißer |
| Begriffe über dem 99-%-Quantil (Regel 2) | 58 über 64 Dokumenten | 55 über 64 Dokumenten |

Der Befund der Arbeit bleibt: über alle 41 Bezirke ist der Zusammenhang weiter nicht signifikant (p geht von
0,31 auf 0,24), und die Spalte ohne die Ausreißer ändert sich in der dritten Stelle. **Was sich ändert, ist
die Deutung der Ausreißer**: Bezirk 10 war ein Artefakt der Benennung, Bezirk 1 ist es nicht — seine Quote
kommt von der Größe seines Wörterbuchs (§ 1).

**Zwei Nebenwirkungen, beide gemessen.** Erstens gibt der Matcher Treffer zurück, wenn ein längerer Begriff
verschwindet: „tonhalle" trifft jetzt 72 statt 67 Dokumente und „nrw-forum" 11 statt 10, weil „tonhalle
düsseldorf" und „nrw-forum düsseldorf" den Treffer vorher verbraucht haben (längster Begriff gewinnt,
§ 2.4). Darum verliert Bezirk 1 nur 133 Treffer, nicht 138. Zweitens ist das zugleich die **Grenze der
Regel**: 2 der 113 entfernten Labels haben einen Kurznamen, der als eigenes Wikipedia-Lemma im Wörterbuch
steht und bleibt — die Tonhalle zählt also weiter, nur unter „tonhalle". Eine Regel über Namen kann das
nicht sehen; dafür steht der Begriff mit 72 Dokumenten in der Liste der stadtweiten Begriffe (Regel 2) und
ist dem Leser benannt.

Die Zahlen stehen auch in `STATUS.md` unter „Zahlen" und in `docs/decisions.md`, Punkt 44.

## 5. Golden-Master-Politik (decisions.md, Punkt 43)

- Die Mini-Fixture enthält Einrichtungen mit Stadtnamen — die Regel trifft 62 ihrer 493 Labels, der
  Wahlbezirk 1 ist die Altstadt —, **aber ihre Erwartungsdateien unter `tests/fixtures/mini/expected/`
  ändern sich nicht**: der Golden-Master-Test rechnet mit `as_in_the_thesis(...)` (`tests/conftest.py`),
  also mit abgeschalteten Regeln, und vergleicht weiter Zeile für Zeile gegen die Ausgaben des Altcodes.
  Nur so bleibt sichtbar, wo die Arbeit endet und das Programm beginnt. Mit den Regeln an rechnet dieselbe
  Fixture 431 Orte, 991 statt 1054 Begriffe und 162 statt 173 Treffer; das steht in
  `tests/fixtures/mini/README.md`.
- Geändert haben sich nur zwei eigene Zahlen dieses Repos: die eingefrorenen Gremienzahlen der Mini-Fixture
  (Option 05) sinken von (96, 63, 14) auf (89, 59, 14) Treffern.
- Der slow-Test über die volle Referenz hat zwei Fälle: `test_pipeline_reproduces_the_thesis_results` mit
  abgeschalteten Regeln gegen die Zahlen der Arbeit und `test_the_rules_change_the_reference_as_measured`
  mit den Vorgaben gegen die oben gemessenen Erwartungswerte vom 2026-10-12.
- Jede weitere bewusste Abweichung bekommt denselben Dreisatz: eine Regel in `defaults.toml` mit Schalter,
  eine Messung in diesem Dokument und ein Punkt in `docs/decisions.md`.

## 6. Empfehlungen in der Reihenfolge, in der sie etwas bringen

1. **Umgesetzt:** Regel 1 (Einrichtung mit Stadtnamen) und Regel 2 (stadtweite Begriffe anzeigen).
2. **Offen, größter Nutzen:** „Treffer je Begriff im Wörterbuch" als zweite Kennzahl mit eigener Regression
   (§ 2.6). Die Verzerrung aus § 1 ist die größte der Methode und die einzige, die der Befund der Arbeit
   nicht aushält. Gehört zu `docs/todo.md`, Punkt 3.
3. **Offen, billig:** drei Sätze in „Methode und Grenzen" — Wörterbuchgröße bestimmt die Trefferzahl
   (r = 0,767), Umlaute sind Wortgrenzen, die zweite Spalte von Tabelle 5 ist nach Ansehen der Daten
   entstanden.
4. **Offen:** Konfidenzintervall oder Permutationstest neben dem p-Wert von Tabelle 5 (§ 2.8).
5. **Offen, nur mit neuem Abruf:** Typfilterung der Wikidata-Orte (§ 2.1).
6. **Bewusst nicht gemacht:** „schulweg" aus der Zählung nehmen (§ 2.3), die Ausreißer automatisch bestimmen
   (§ 2.7), Erwähnungen statt Dokumente zählen (§ 2.5), die Ausschlussliste programmatisch erzeugen (§ 2.2).
