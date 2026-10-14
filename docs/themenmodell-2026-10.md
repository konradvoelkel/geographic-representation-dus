# Das Themenmodell tragfähig machen

Stand 2026-10-13 (die Zahlen des ersten Durchgangs vom 2026-10-12 sind nach dem Review neu
gemessen; was sich geändert hat, steht in § 8). Punkt 1 aus [todo.md](todo.md): Konrads Blick auf die 20 Themen der Referenz —
Thema 0 „Kosten/Geld" und Thema 2 „Bauen" brauchbar, Thema 3 „CDU vermischt mit anderem", Thema 16
„ein seltsamer Linke-Block"; Vermutung: die Fraktionsnamen aus Kopf und Betreff prägen die Themen.
Die Vermutung trifft zu, und sie trifft auch auf Personennamen zu. Dieses Dokument geht die vier
Wege des TODO in seiner Reihenfolge durch, misst jeden und nennt, was offen bleibt.

Alle Zahlen sind am 2026-10-12 auf der Referenz gemessen (19 108 Dokumente, 19 033 mit Text), mit
`UV_PROJECT_ENVIRONMENT` und Daten auf xtraspace, `POLARS_MAX_THREADS=4`, `OMP_NUM_THREADS=2`.
Nachrechnen:

```bash
uv run georep run                                             # die Kette, 17 s
uv run python docs/themenmodell-2026-10-messung.py            # die Zahlen hier, rund zwei Minuten
uv run python docs/themenmodell-2026-10-messung.py --stages   # nur § 2
```

Entscheidungen und verworfene Alternativen stehen in [decisions.md](decisions.md), Punkt 45; der
Aufbau in [architecture.md](architecture.md). Die Zahlen von Tabelle 5 und die Treffer sind
unberührt: das Themenmodell speist nur die Gewichtungsvarianten der Option 06 (5727 Begriffe,
29 010 Treffer, Einheitsvariante gleich `anzahl_treffer` — vor und nach dieser Arbeit).

## 1. Die Kennzahl: NPMI und UMass über die Topwörter

Eine Kohärenzkennzahl ersetzt kein Hinsehen, aber sie macht die vier Wege vergleichbar. Gerechnet
wird auf demselben Korpus, ohne neue Abhängigkeit (`docs/themenmodell-2026-10-messung.py`,
Funktion `coherence`):

- **NPMI**: je Paar der zehn Topwörter eines Themas
  `ln(P(w_i, w_j) / (P(w_i)·P(w_j))) / −ln P(w_i, w_j)`, gemittelt über die 45 Paare und dann über
  die 20 Themen. Dokumenthäufigkeiten, nicht Fenster. +1 heißt „kommen nur zusammen vor", 0
  „unabhängig". Das ist die Zahl, auf die es hier ankommt.
- **UMass**: `ln((D(w_i, w_j) + 1) / D(w_i))` mit dem stärkeren Wort als Bedingung, sonst gleich
  gemittelt. Sie steht daneben, weil sie die gängige zweite Zahl ist, **belohnt aber häufige
  Wörter**: nimmt man die Formelwörter der Vorlagen aus den Labels, fällt UMass, obwohl die Themen
  lesbarer werden. Genau das passiert unten; wer nur auf UMass sieht, zieht den falschen Schluss.

Beide Zahlen hängen am Korpus und am Rechner (BLAS-Threads) und taugen darum nicht als
Erwartungswert eines Tests. Die Tests prüfen Eigenschaften — `k` Themen, Zeilensummen 1, Saat aus
den Settings, Determinismus je Rechner (`tests/unit/test_topics.py`,
`tests/golden/test_pipeline.py`).

## 2. Weg 1: Stoppwörter aus dem Profil, Namen aus dem Korpus

### 2.1 Woher sie kommen

Keine zweite Liste: die Namen und Muster stehen schon im Profil, weil Option 04 und 05 sie pflegen.
`topics.stop_sources` wählt die Quellen (`defaults.toml`), `analysis/topics.py` leitet ab:

| Quelle | liest | ergibt (Referenz) |
|---|---|---|
| `fraktionen` | `[originators]`: `key`, `label`, `short` und `patterns` jeder Partei und Gruppe, dazu `fraction_markers`, `joint_markers`, `person_markers` | 35 Wörter: `cdu`, `spd`, `fdp`, `afd`, `linke`, `grüne`, `gruene`, `grünen`, `bündnis`, `volt`, `partei`, `tierschutz`, `freie`, `wähler`, `fraktion`, `fraktionen`, `interfraktionell`, `ratsherr`, `ratsfrau`, `bezirksvertreter`, `bürgermitglied`, `herrn`, `frau` … |
| `gremien` | `[bodies]`: `district_body` und die Kürzel aus `council`, `committees`, `advisory` — **nur die Kürzel, nicht die Namen** | 26 Wörter: `rat`, `ova`, `kua`, `aps`, `jha`, `schua`, `jurat`, `intr` … |
| `namen` | den Korpus: Wörter, die fast nur in einem Namensfenster stehen | 254 Wörter |

„Verkehrsausschuss" bleibt also ein Themenwort; „OVA" ist keines. `BV` fällt heraus, weil zwei
Buchstaben nach `topics`-Tokenmuster (`[a-zäöüß]{3,}`) gar kein Token bilden. Aus einem Regex
kommen Bruchstücke mit (`frak` und `ion` aus `frak\w{0,2}ion`); sie sind harmlos, weil ein
Bruchstück allein nie ein Token ist.

**Ein Kürzel kann mit einem Sachwort zusammenfallen.** Das ist der Preis dafür, die Kürzel
mechanisch aus dem Profil zu nehmen, und er ist messbar: `BAU` (Bauausschuss) ist als Wort „bau"
und steht in 1101 von 19 033 Dokumenten (5,8 %), wo es das Bauen meint. Ohne Ausnahme fiel die
Kohärenz der Stufe `gremien` deswegen von +0,4386 auf +0,4282; mit `bau` in `topics.stop_keep`
liegt sie bei **+0,4364** (gemessen 2026-10-13). Zwei weitere Kürzel sind Wörter, bleiben aber
Stoppwörter, weil sie wirklich das Gremium nennen: „rat" (`RAT`, 3751 Dokumente, 19,7 %) und
„aus" (`AUS`, Umweltausschuss, 9320 Dokumente -- das Wort steht ohnehin in der deutschen
Paketliste). Beide Entscheidungen stehen mit ihrer Zahl im Profil.

**Das Profil nennt die Ausnahmen.** Die Quelle `fraktionen` nähme „klima" (aus
„Die PARTEI-Klima-Fraktion") und „tierschutz" (aus „Tierschutz/Freie Wähler") mit; beide sind
Sachwörter dieser Stadt. `profiles/duesseldorf.toml` holt sie mit `topics.stop_keep` zurück — eine
Ausnahmeliste von zwei Wörtern, kein zweiter Katalog. Dass „klima" wieder zählt, sieht man am
gesäten Thema des Umweltausschusses unten.

### 2.2 Personennamen: der Textkopf allein trägt nicht

Die Frage des TODO war, ob der Textkopf (Option 04 kennt ihn: 600 Zeichen hinter „betrifft")
Namen liefert, die als Stoppwörter taugen, oder ob ein einfacher Filter genügt. Gemessen:

- Der Textkopf **allein** reicht nicht. Die Personenmarker aus `[originators]`
  („bezirksvertreter", „ratsherr", „herrn ", „frau " …) treffen im Kopf 8 430 Dokumente, aber die
  Namen der Verwaltung stehen nicht dort, sondern unter der Vorlage.
- **Der einfache Filter trägt.** Ein Wort ist ein Name, wenn es fast nur in einem
  *Namensfenster* steht: 60 Zeichen hinter einem Marker aus `topics.name_markers`
  („gez.", „mit freundlichen grüßen", „oberbürgermeister", „beigeordnete", „stadtdirektor",
  „stadtkämmer", „dezernent", „amtsleiter", „vorsitzende") oder hinter einem Personenmarker im
  Textkopf. Zwei Durchgänge zählen die Dokumente je Wort — einmal nur in den Fenstern, einmal
  überall; liegt der Anteil über `name_share` (0,8) und steht das Wort in mindestens
  `name_min_documents` (5) Fenstern, ist es ein Name. Ergebnis: **254 Wörter** in 1,8 s, darunter
  „czerwinski", „hebeler", „fraktionssprecherin", „bezirksbürgermeisterin", „markus", „brigitte".
- Die **Amtsbezeichnungen** sind der Unterschied: ohne sie findet derselbe Filter nur 196 Wörter,
  und die Namen der Dezernenten („jochen", „kral", „doroth", „schneider", „keller", „stulgies",
  „zaum") bleiben in den Themen stehen. Die Liste ist deutschsprachig und stadtneutral, wie
  `search.place_words`; eine Stadt in einem anderen Sprachraum ersetzt sie im Profil.
- **Grenze**, benannt: Namen, die nie neben einem Amt oder einer Unterschrift stehen, bleiben
  („cardeneo", „kühbacher", „tobias", „stephan", „hans", „christian"), und Wörter, die zugleich
  Name und Sachwort sind, hält der Anteil draußen („klein", „graf", „born"). Ein Namenslexikon
  oder die Mandatsträgerliste aus OParl-`memberships` würde das schließen; beides ist ein neuer
  Abruf und steht nicht in diesem Punkt.

### 2.3 Gemessen: vorher und nachher

Vier Stufen, jede mit derselben freien NMF (k = 20, `tol = 1e-3`):

| Stufe | Stoppwörter | NPMI | UMass | Laufzeit |
|---|---|---|---|---|
| heute (nur die Paketliste `stopwords_de.txt`) | 313 | **+0,4164** | −1,045 | 8,9 s |
| + `fraktionen` | 348 | **+0,4386** | −1,162 | 8,9 s |
| + `gremien` | 373 | **+0,4364** | −1,182 | 10,0 s |
| + `namen` (die Vorgabe) | 627 | **+0,4208** | −1,159 | 10,4 s |

NPMI steigt gegenüber heute um 1,1 % (Stufe 4) bis 5,3 % (Stufe 2) und ist nicht monoton: jede
Stufe nimmt Wörter weg, die in *irgendeinem* Thema zusammen auftraten, und ersetzt sie durch
seltenere. UMass fällt durchweg — das ist die erwartete Richtung (§ 1) und kein Gegenbefund. Die
Zahl, die zählt, steht in den Wortlisten:

**Vorher (heute, nur die Paketliste).** Sieben der 20 Themen sind Partei-, Anreden- oder
Personenblöcke:

```
 3 [ 2969] antrag, gez, fraktion, begründung, cdu, straße, grünen, bündnis, gebeten, bittet
 4 [  849] tagesordnung, freundlichen, ratsfraktion, geehrter, grüßen, herr, antrag, bitten, ratsfraktionen, spd
 9 [  516] bezirksbürgermeisterin, geehrte, frau, eller, hiermit, nächste, beschließen, nehmen, sitzung, fraktion
10 [  216] festsetzung, uhr, sonntag, gewerbeordnung, ordnungsamt, ablehnungsgründe, beantragt, marktes, zaum, christian
11 [ 2612] anfrage, beantworten, fragen, wann, beantwortung, fraktion, spd, bitte, frage, herr
16 [  911] linke, ratsfraktion, düsseldorf, stellt, sönke, voigt, stadt, innen, freundlichen, julia
18 [  411] wähler, tierschutz, ratsgruppe, freie, lemmer, torsten, setzen, haushaltsplan, düsseldorf, oberbürgermeister
```

**Nachher (Stufe 4, noch frei).** Keine Partei, kein Personenname; dafür entstehen Themen, die es
vorher nicht gab — Schule (18), Aufsichtsratsbesetzungen (16), Verfügungsmittel der
Bezirksvertretungen (1 und 8), Gemeindeordnung und Dringlichkeitsentscheidungen (10):

```
 0 [ 1454] düsseldorf, innen, stadt, düsseldorfer, menschen, landeshauptstadt, entwicklung, rahmen, ziel, jahr
 1 [  641] verfügungsmittel, bezirksvertretung, zuschuss, bezirksverwaltungsstelle, vergabe, zuschusses, höhe, beschließt, institut, beschlussdarstellung
 2 [  983] grundstück, bauvorhaben, erteilung, stellplätze, vorhaben, geltungsbereich, nachrichtlich, befreiungen, gebäude, erforderlichen
 3 [ 2514] bezirksvertretung, beschluss, amt, bezirksverwaltungsstelle, institut, kenntnisnahme, teilt, beratungsfolge, straße, beratungsqualität
 4 [ 3184] ratsfraktion, anfrage, freundlichen, geehrter, herr, tagesordnung, grüßen, sitzung, bitten, düsseldorf
 5 [  272] träger, jugendhilfeplanung, abzüglich, euro, kinder, jugendhilfeausschuss, plätze, tageseinrichtungen, landesmittel, städt
 6 [  175] anregungs, beschwerdeausschuss, ratsangelegenheiten, stadtverfassung, eingabe, einsender, regt, kurzdarstellung, stellungnahme, fachbereich
 7 [  424] liste, eur, restmittel, beschlusssumme, unterhaltung, grundstücken, stadtbezirk, ansatz, maßnahme, instandhaltung
 8 [  340] festbetrag, bezirklichen, gewährt, verfügungsmitteln, zweckgebunden, zuschuss, euro, bezirksvertretung, durchführung, höhe
 9 [  436] stadtentwicklung, vorlagegemäße, ausschuss, planung, baugb, gem, empfiehlt, abs, bebauungsplan, entwurf
10 [  509] satz, abs, nrw, gemeindeordnung, dringlichkeitsentscheidung, entscheidung, schriftführung, beschlussdarstellung, verbindung, bestellt
11 [  457] uhr, festsetzung, sitzungstermine, sonntag, halbjahr, gewerbeordnung, donnerstag, ordnungsamt, ablehnungsgründe, beantragt
12 [ 3413] gez, antrag, begründung, straße, gebeten, bittet, bezirksvertretung, stadtbezirk, prüfen, fraktionssprecherin
13 [  219] bäume, nachpflanzungen, abgestorben, baumart, fällung, stadtbezirk, absterbend, gefällt, baumfällungen, kalenderwoche
14 [  159] beschlusskontrolle, beschlüsse, bearbeitung, abgeschlossen, anlage, tabellarische, beschlüssen, sachstandsbericht, anliegende, aufgeteilt
15 [ 1356] kosten, brutto, eur, maßnahme, finanzierung, gesamtkosten, anlage, planung, höhe, sanierung
16 [  330] aufsichtsrat, abberufung, mitglieder, aufsichtsrates, wahlperiode, landeshauptstadt, gmbh, abs, düsseldorf, entsendung
17 [  370] eur, verein, weiblich, männlich, zuschuss, zuschüsse, gewährung, sportausschuss, gesamtkosten, mitgliederstatistik
18 [  975] schule, schulen, schüler, ggs, bildung, kgs, grundschule, budget, kinder, gymnasium
19 [  822] anlage, vvz, veränderungsverzeichnis, ausschuss, beigefügt, entwurf, beratungsunterlagen, haushaltsplan, teil, dezernentin
```

**Befund zu Weg 1:** Konrads Vermutung war richtig, und der billige Weg wirkt. Was bleibt, sind die
Formelwörter des Verfahrens: die Themen 3, 4, 12 und 19 beschreiben Dokumentarten
(Bezirksvertretungsvorlage, Anfrage, Antrag, Veränderungsverzeichnis), nicht Sachgebiete. Dagegen
hilft keine Stoppwortliste — ein Formelwort ist in seinem Thema sehr wohl kohärent. Dafür ist
Weg 2 da.

## 3. Weg 2: Gesäte Themen je Ausschuss

### 3.1 Wie gesät wird

Jedes Dokument trägt sein Gremium aus der Drucksachennummer (Option 05, auf der Referenz 0 von
19 108 unbekannt); die Ausschüsse stehen im Profil unter `[bodies.committees]`. Daraus:

1. **Unterscheidende Wörter je Ausschuss**: Log-Odds-Verhältnis mit informativem Dirichlet-Prior
   (Monroe u. a. 2008), verglichen wird ein Ausschuss **gegen die anderen Ausschüsse** — gesucht
   ist, was *diesen* Ausschuss trennt, nicht was eine Ausschussvorlage von einem Antrag trennt.
   Der Prior kommt aus den Wortzahlen des ganzen Korpus, auf `seed_prior` (1000) Pseudo-Token
   gebracht; er dämpft Wörter, die nur ein paar Mal vorkommen. Die 30 Wörter mit dem größten
   z-Wert sind die Saat — aber nur solche, die der Ausschuss auch benutzt: ein Wort, das in
   **keinem** Ausschuss steht, hat in beiden Gruppen die Zahl 0 und bekommt trotzdem ein
   positives z, weil der kleinere Ausschuss weniger Token im Nenner hat (aufgedeckt am
   2026-10-13 an der synthetischen Fixture; auf der Referenz war kein solches Wort unter den
   ersten 30, der Fehler war latent).
2. **Feste Wortmatrix**: die Zeile eines gesäten Themas trägt genau diese 30 Wörter mit dem
   TF-IDF-Mittelwert ihres Ausschusses, auf Länge 1 gebracht, und wird **nicht mehr verändert**
   (`non_negative_factorization(..., update_H=False)`). Gelernt werden nur die Anteile der
   Dokumente.
3. **Freie Themen auf dem Rest**: `max(X − W·H, 0)`, exakt und sparse auf dem Träger von X
   gerechnet, geht in eine gewöhnliche NMF mit `topics.free` (3) Komponenten.

Welche Ausschüsse: die mit mindestens `seed_min_documents` (10) beratenen Dokumenten, nach Zahl
absteigend, höchstens `k − free` (17) viele. Auf der Referenz sind das 17 von 23 Ausschüssen; die
sechs übrigen (RPAU 31 bis WPA 1) bleiben ohne eigenes Thema, weil die 17 größeren die Plätze
füllen.

**Verworfen: H nur initialisieren.** Mit `init="custom"` und freiem H wanderte NMF binnen 58
Iterationen von der Saat weg: nur 0 bis 23 % der Dokumente eines Ausschusses hatten danach noch
sein Thema als stärkstes (OVA 1 %, KUA 0 %), und Thema 0 „OVA" war in Wirklichkeit der
Formelblock der Bezirksvertretungen. Das Festhalten von H ist der ganze Unterschied.

**Verworfen: binäre Saatgewichte.** Jedes Saatwort mit Gewicht 1 statt des Zentroids: NPMI
+0,2170 gegen +0,3640 bei sonst gleicher Rechnung, und die Labels fallen alphabetisch aus, weil
alle 30 Wörter gleich stark sind (gemessen am 2026-10-12, Stoppwortliste noch ohne die
Amtsmarker).

### 3.2 Gemessen: die Themen haben Namen

Die Vorgabe (`seed = "committees"`, `free = 3`, `seed_words = 30`): NPMI **+0,3349**,
UMass −1,577, 8,7 s. Die Kohärenz liegt **unter** der freien NMF (+0,4208) — erwartbar, denn die
Topwörter eines gesäten Themas sind nicht die, die am häufigsten zusammen stehen, sondern die, die
diesen Ausschuss von den anderen trennen. Was man dafür bekommt, steht in der Spalte „Gremium":

| Nr. | Gremium | Dokumente | stärkste Wörter |
|---|---|---|---|
| 0 | OVA | 2426 | ordnungs, verkehrsausschuss, straße, verkehrsmanagement, rheinbahn, öpnv, radverkehr, verkehr, straßen, platz |
| 1 | KUA | 880 | kulturausschuss, kulturamt, kunst, eur, landeshauptstadt, künstler, innen, halbjahr, mittel, hans |
| 2 | APS | 1498 | stadtentwicklung, planung, ausschuss, bebauungsplan, baugb, empfiehlt, vorlage, abs, beschlussfassung, gem |
| 3 | JHA | 1088 | jugendhilfeausschuss, träger, kinder, jugendhilfe, abzüglich, euro, jugendamt, jugend, kita, sgb |
| 4 | SCHUA | 1184 | schule, schulen, schulausschuss, schüler, bildung, schuljahr, grundschulen, schülerinnen, berufskolleg, gymnasium |
| 5 | AGS | 618 | soziales, gesundheit, ausschusses, menschen, geehrter, gesundheitsamt, christian, plus, corona, pandemie |
| 6 | SPOA | 691 | sportausschuss, verein, sportamt, eur, weiblich, männlich, zuschuss, gewährung, sport, zuschüsse |
| 7 | AUS | 671 | umwelt, verbraucherschutz, klima, umweltschutz, www, förderprogramm, klimaschutz, klimafreundliches, emissionen, richtlinie |
| 8 | AÖE | 756 | stadtökologie, abfallmanagement, bevölkerungsschutz, öffentliche, einrichtungen, umwelt, friedhofs, garten, verbraucherschutz, forstamt |
| 9 | AWM | 1320 | wohnungswesen, modernisierung, ratsfraktion, wohnungen, wohnraum, geehrte, ausschusses, wohnungsmarkt, anfrage, freundlichen |
| 10 | SEBD | 957 | stadtentwässerungsbetrieb, gesamtkosten, euro, bauausschuss, brutto, höhe, kosten, maßnahme, netto, circa |
| 11 | ADIG | 309 | digitalisierung, verwaltungsorganisation, allgemeine, finanzplan, personal, produkt, organisation, vvz, leistungen, begründung |
| 12 | HFA | 296 | haupt, finanzausschuss, controllingbericht, kämmerei, landeshauptstadt, haushalts, dienstreise, absatz, jahresabschluss, stellenplan |
| 13 | GLA | 370 | gleichstellung, frauen, antidiskriminierung, gewalt, stephan, geehrte, ratsfraktion, ausschusses, sitzung, anfrage |
| 14 | ABA | 483 | anregungs, beschwerdeausschuss, ratsangelegenheiten, eingabe, stadtverfassung, regt, kurzdarstellung, stellungnahme, anlagen, fachbereich |
| 15 | AWIR | 376 | wirtschaftsförderung, regionale, internationale, zusammenarbeit, cardeneo, düsseldorf, unternehmen, wirtschaftsförderungsamt, kühbacher, tobias |
| 16 | BAU | 317 | gebäudemanagement, bauausschuss, bauausschusses, eur, dienstag, hochbaumaßnahmen, controllingbericht, brutto, amt, ausführungs |
| 17 | (frei) | 2477 | düsseldorf, antrag, anfrage, begründung, sitzung, stadt, gez, herr, innen, straße |
| 18 | (frei) | 1530 | bezirksvertretung, bezirksverwaltungsstelle, institut, amt, zuschuss, beratungsfolge, beratungsqualität, beschlussdarstellung, entscheidung, höhe |
| 19 | (frei) | 786 | grundstück, bauvorhaben, erteilung, stellplätze, vorhaben, erforderlichen, gebäude, geltungsbereich, lageplan, nachrichtlich |

Die drei freien Themen nehmen genau das auf, was Weg 1 nicht wegbekam: den Antrags- und
Anfrageblock (17), den Formelblock der Bezirksvertretungen (18) und die Baugenehmigungen (19).
Sechs Namen haben die Saat überlebt („hans", „christian", „stephan", „cardeneo", „kühbacher",
„tobias") — sie stehen in den Dokumenten ihres Ausschusses so oft, dass der Log-Odds-Wert sie
nach vorn trägt, und keiner von ihnen steht regelmäßig neben einem Amt (§ 2.2).

**Treue und Reinheit** (Treue: Anteil der Dokumente eines Ausschusses, deren stärkstes Thema
seines ist; Reinheit: Anteil der Dokumente dieses Ausschusses an allen mit diesem Thema):

| Gremium | Treue | Reinheit | | Gremium | Treue | Reinheit |
|---|---|---|---|---|---|---|
| ABA | 1,00 | 0,29 | | AÖE | 0,83 | 0,30 |
| AWM | 0,98 | 0,15 | | SCHUA | 0,83 | 0,31 |
| AGS | 0,93 | 0,48 | | KUA | 0,81 | 0,57 |
| GLA | 0,91 | 0,36 | | SEBD | 0,81 | 0,16 |
| APS | 0,87 | 0,33 | | SPOA | 0,80 | 0,36 |
| AWIR | 0,87 | 0,26 | | AUS | 0,80 | 0,35 |
| ADIG | 0,86 | 0,48 | | OVA | 0,77 | 0,24 |
| JHA | 0,84 | 0,40 | | BAU | 0,73 | 0,19 |
| | | | | HFA | 0,72 | 0,38 |

Die Treue ist durchweg hoch (0,72 bis 1,00, Median 0,83): ein gesätes Thema ist tatsächlich das
Thema seines Ausschusses. Die Reinheit ist niedrig (0,15 bis 0,57) — und das ist der Punkt der
ganzen Übung: ein Thema zieht viel mehr Dokumente an, als in diesem Ausschuss beraten wurden. Dem
Thema des Wohnungsausschusses (AWM, 196 beratene Dokumente) fallen 1320 Dokumente zu; es ist
also eine Sachkategorie geworden, kein Abbild der Beratungsfolge.

**Befund zu Weg 2:** Die Themen tragen jetzt lesbare Namen statt Nummern, und die Zuordnung ist
treu. Die Kohärenz nach NPMI fällt dabei um ein Fünftel; wer die Themen nur nach NPMI wählt, nimmt
die freie NMF. Für Konrads Zweck — Themen, die etwas sagen — ist die Saat die richtige Wahl, und
sie ist die Vorgabe. `topics.seed = "none"` rechnet weiter freie NMF, ohne Codeänderung.

## 4. Weg 3: Überwachte Zuordnung zum passenden Ausschuss

### 4.1 Aufbau

Ein Klassifikator (TF-IDF aus `[topics]`, logistische Regression, `C = 1`, `random_state = 0`)
lernt auf den Dokumenten, deren Drucksachennummer ein Ausschusskürzel trägt, und ordnet jedem
Dokument mit Text einen Ausschuss zu — auch denen, die nur im Rat oder in einer
Bezirksvertretung waren. Klassen sind die Ausschüsse mit mindestens `classify.min_documents` (10)
beratenen Dokumenten: 20 Klassen, 5347 Trainingsdokumente. Liegt die Wahrscheinlichkeit der
stärksten Klasse unter `classify.min_probability` (0,4), zählt das Dokument als querschnittlich
und landet in der **Restklasse**. Neuer Offline-Schritt `committees`
(`processed/papers_ausschuss.parquet` je Dokument, `processed/ausschuss_zuordnung.parquet` je
Ausschuss, beide mit Stamp und Schema-Version); die Kette trainiert einmal, kreuzvalidiert wird im
Messskript.

### 4.2 Güte (Kreuzvalidierung, fünf Faltungen, stratifiziert)

**Genauigkeit 0,941, Makro-F1 0,878** (8,7 s). Je Klasse:

| Klasse | n | richtig | | Klasse | n | richtig |
|---|---|---|---|---|---|---|
| OVA | 751 | 1,00 | | AGS | 318 | 0,96 |
| KUA | 616 | 0,99 | | SPOA | 310 | 0,96 |
| SCHUA | 439 | 0,98 | | AWM | 196 | 0,95 |
| APS | 568 | 0,97 | | SEBD | 189 | 0,94 |
| JHA | 510 | 0,97 | | AUS | 295 | 0,93 |
| ABA | 138 | 0,97 | | AÖE | 275 | 0,92 |
| RPAU | 31 | 0,97 | | ADIG | 170 | 0,89 |
| WALTW | 21 | 0,90 | | GLA | 149 | 0,87 |
| HFA | 154 | 0,71 | | AWIR | 113 | 0,70 |
| BAU | 94 | 0,56 | | AWIZ | 10 | 0,00 |

Häufigste Verwechslungen: BAU → OVA 21, HFA → OVA 18, AUS → OVA 15, AÖE → OVA 10,
JHA → SCHUA 9, AÖE → AUS 8, AWIR → APS 8, AGS → JHA 8, ADIG → OVA 8, GLA → OVA 7. Sie sind
sachlich plausibel: der Bauausschuss und der Ordnungs- und Verkehrsausschuss verhandeln dieselben
Straßen, der Umweltausschuss und der Ausschuss für öffentliche Einrichtungen dieselben Bäume,
Jugendhilfe und Schule dieselben Kinder. AWIZ (10 Dokumente, 2020-11 bis 2021-03, danach AWIR)
wird nie erkannt und zieht Makro-F1 um rund vier Punkte: die Klasse ist der Vorläufer ihres
Nachfolgers, mit denselben Wörtern.

### 4.3 Woran die Güte hängt: der Text nennt sein Gremium selbst

Die 0,941 sind zu einem Teil geschenkt. Eine Ausschussvorlage trägt im Volltext die
Beratungsfolge, und darin steht der Name des Ausschusses — gemessen am 2026-10-13 auf der
Referenz:

| Ausschuss | das Wort im Text | Anteil seiner Dokumente |
|---|---|---|
| ABA | „beschwerdeausschuss" | 138/138 = 100 % |
| RPAU | „rechnungsprüfungsausschuss" | 31/31 = 100 % |
| SPOA | „sportausschuss" | 300/310 = 96,8 % |
| JHA | „jugendhilfeausschuss" | 489/510 = 95,9 % |
| KUA | „kulturausschuss" | 579/616 = 94,0 % |
| SCHUA | „schulausschuss" | 409/439 = 93,2 % |
| OVA | „verkehrsausschuss" | 689/751 = 91,7 % |
| BAU | „bauausschuss" | 84/94 = 89,4 % |

Das **Kürzel** ist dabei unschädlich, aber nur, weil § 2.1 es zum Stoppwort macht (`gremien`);
diese Kopplung ist hier ausgesprochen, nicht stillschweigend: wer `topics.stop_sources` ohne
`gremien` setzt, lernt dem Klassifikator die Drucksachennummer bei. Der **Name** steht weiter im
Vokabular. Was er wert ist, zeigt der Gegenversuch: sperrt man alle 44 Vokabularwörter, die
„ausschuss" enthalten, fällt die Kreuzvalidierung auf **0,929 Genauigkeit und 0,864 Makro-F1**,
und die Zuordnung wird breiter statt enger — die Restklasse geht bei den
Bezirksvertretungen von 81,2 % auf 79,1 % zurück, beim Rat von 87,4 % auf 86,9 %, bei den
Ausschüssen dagegen von 10,9 % auf 12,8 % hoch, und von den Ausschussdokumenten treffen 4654
statt 4756 ihr eigenes Gremium.

Das ist der eigentliche Einwand gegen § 4.4, und er ist berechtigt: **die Restklasse ist zum Teil
ein Artefakt der Beratungsfolge.** Ein Dokument, das seinen Ausschuss nennt, bekommt eine hohe
Wahrscheinlichkeit, und eines ohne diese Zeile — jedes BV- und Ratsdokument — eine niedrigere,
unabhängig davon, wie klar sein Thema ist. Die Antwort darauf ist nicht, die Wörter zu sperren:
der Gegenversuch verschiebt die Restklasse um zwei Punkte und kostet eineinhalb Punkte Güte,
ändert also an der Aussage nichts. Sie lautet: die Zahlen in § 4.4 sind eine **Untergrenze** für
die Zuordenbarkeit der BV- und Ratsdokumente, keine Schätzung. Wer die Frage genauer stellen
will, trainiert auf dem Text **ohne** Beratungsfolge (der Marker `betrifft` schneidet den Kopf
ab, nicht den Fuß) — das ist ein eigener Punkt und braucht einen Blick in die PDFs, nicht nur
eine Stoppwortliste.

**Nachtrag 2026-10-14:** das Label, das dieser Absatz vermisst, liegt seit Punkt 58 vor. Die
Beratungsfolge steht jetzt als Angabe **neben** dem Text in `papers_gremien.parquet`
(`folge_gremium`, `folge_anzahl`), nicht nur in ihm: für 17 047 Dokumente der Hauptperiode nennt
sie genau ein Gremium, und die Tabelle sagt je Dokument, ob das Gremium aus der Nummer oder aus
der Folge kommt. Ein Klassifikator, der darauf trainiert und bewertet wird, misst die
Zuordenbarkeit an einem Ziel, das nicht aus dem Volltext stammt — die Untergrenze von § 4.4
könnte damit eine Schätzung werden. Umgebaut ist hier nichts; der Zielwert des Schritts
`committees` bleibt das Kürzel der Drucksachennummer.

Zwei Zahlen dieses Dokuments haben sich dabei verschoben, und zwar nicht durch das Modell: mit
`POA` und `ACI` in `[bodies.committees]` (Punkt 58) kommen zwei Kürzel mehr in die Stoppwortliste
aus `topics.stop_sources = ["gremien", …]`, und die Kette ordnet seitdem **7 174** statt 7 180
Dokumente zu (37,7 %), davon treffen **4 750** statt 4 756 das Gremium der Nummer (66,2 %).

### 4.4 Konrads Frage: lässt sich jedes Schriftstück einem Ausschuss zuordnen?

**Nein — für ein knappes Drittel sicher, für den Rest nicht.** Mit der Vorgabe (Schwelle 0,4)
ordnet die Kette 7180 von 19 033 Dokumenten zu (37,7 %), 11 853 bleiben in der Restklasse
(62,3 %). Nach Herkunft:

| Gremienart | Dokumente | Restklasse | Anteil |
|---|---|---|---|
| Ausschuss | 5351 | 582 | 10,9 % |
| Bezirksvertretung | 10 997 | 8929 | 81,2 % |
| Rat | 2243 | 1961 | 87,4 % |
| Beirat | 442 | 381 | 86,2 % |

Von den 5351 Ausschussdokumenten treffen 4756 (88,9 %) ihr eigenes Gremium — die Zuordnung ist
also dort verlässlich, wo sie prüfbar ist. Für die Dokumente, um die es Konrad geht (Rat,
Bezirksvertretung), ist sie es nicht: vier von fünf BV-Dokumenten und sieben von acht
Ratsdokumenten erreichen keine Wahrscheinlichkeit von 0,4. Der Grund ist nicht
Modellschwäche, sondern Inhalt: ein BV-Antrag über einen Zebrastreifen *und* einen Spielplatz
*und* einen Baum ist kein Ausschussthema, und eine Haushaltsvorlage ist alle Themen zugleich. Die
Zahlen sind bewusst nicht wegkalibriert — mit 20 Klassen liegt der Zufall bei 0,05, und 0,4 ist
das Achtfache davon; wer die Schwelle auf 0,3 senkt, bekommt mehr Zuordnungen und weniger
Verlass. `classify.min_probability` steht in den Settings, damit diese Wahl sichtbar bleibt.

Die Tabelle „Dokumente je passendem Ausschuss" steht im Abschnitt „Gremien" der Berichtsseite,
mit der Spalte „davon ohne Ausschussberatung": für OVA sind das 1092 von 1835, für APS 710 von
1250. Genau diese Dokumente sind der Gewinn der Übung — bei ihnen sagt die Zuordnung etwas, das
nicht schon in der Drucksachennummer steht.

### 4.5 Laufzeit

Der Schritt `committees` braucht **6,5 s** auf der Referenz (TF-IDF 4,1 s, Training 1,4 s,
Vorhersage unter 0,1 s), die Abnahmegrenze waren rund 30 s. Der volle Offline-Lauf (`georep run
--force`, 19 Schritte) dauert damit **23,4 s** gegen 17 s vorher: `topics` kostet 7,4 s statt
7,0 s (die Namensfenster 1,8 s und die Saat kommen dazu, dafür konvergiert die freie NMF auf drei
Komponenten schneller), `committees` 6,5 s, `index` unverändert 4,2 s, die Berichtsseite 1,5 s.
Die Kreuzvalidierung (8,7 s) läuft nur im Messskript.

## 5. Weg 4: Einbettungen — nicht gebaut, und warum sie nicht nötig sind

Die drei billigen Wege reichen. Was Einbettungen leisten würden, leisten sie hier schon: die
Themen sind lesbar (§ 3.2, Treue 0,70 bis 1,00), die Begriffe der Dokumente sind durch TF-IDF über
20 000 Wörter hinreichend fein getrennt (Kreuzvalidierung 0,941 bei 20 Klassen, § 4.2; ohne die Gremiennamen 0,929, § 4.3), und die
Fehler, die bleiben, sind keine Darstellungsfehler, sondern Mehrdeutigkeiten der Sache: ein
BV-Antrag über drei Gegenstände hat kein Thema, und eine Haushaltsvorlage hat alle. Ein
Satzvektor würde daran nichts ändern — er würde dasselbe Dokument in denselben Mischbereich legen,
nur ohne nachlesbare Wörter. Dazu die Kosten: 19 108 Dokumente mit zusammen 51,2 Millionen Zeichen
sind rund 13 Millionen Token; ein deutsches Satzmodell (etwa `paraphrase-multilingual-MiniLM`,
384 Dimensionen) bräuchte auf dieser CPU nach Erfahrung 1 bis 3 Stunden für einen Durchgang,
dazu eine Abhängigkeit von `sentence-transformers` und `torch` (rund 800 MB im Lockfile, gegen die
15 MB von scikit-learn), ein Modellgewicht im Cache oder im Netz, und eine Reproduzierbarkeit, die
an der Modellversion hängt statt an `random_state`. Die gespeicherten Vektoren wären 19 033 × 384
Float32, also 29 MB — tragbar, aber nur der kleinste Teil der Rechnung. Der Preis ist die
Erklärbarkeit: die Berichtsseite kann heute neben jedem Thema die Wörter nennen, aus denen es
besteht. **Empfehlung: nicht bauen.** Wenn, dann erst, wenn eine konkrete Frage es verlangt
(etwa Ähnlichkeit zwischen Dokumenten für die Suche), und dann einmal offline mit gespeicherten
Vektoren, wie das TODO es schon vorsah. Die eine Frage, für die Einbettungen etwas brächten,
ist die aus § 4.3: ob ein BV-Antrag ohne Beratungsfolge sachlich zu einem Ausschuss passt. Auch
dort wäre der erste Schritt aber nicht ein Satzmodell, sondern derselbe Klassifikator auf dem
Text ohne Fuß — billiger, erklärbar und mit der vorhandenen Messung vergleichbar.

## 6. Was sich auf der Seite und in den Daten geändert hat

- **`themen.parquet`** hat die Spalte `gremium` (Kürzel des gesäten Ausschusses, leer bei einem
  freien Thema), Schema-Version 2. `themen_dokumente.parquet` und `themen_anteile.parquet` sind
  unverändert in Form.
- **Abschnitt „Was ändert die Gewichtung?" (34-gewichtung)**: die Themenzeilen der
  Sensitivitätstabelle heißen „Thema 0: Ordnungs- und Verkehrsausschuss" statt „Thema 0" (ein Kürzel ohne gesicherten Namen im Profil steht als Kürzel, etwa „Thema 4: SCHUA"), und die
  Themen-Tabelle hat eine Spalte „Gremium" (Name und Kürzel aus dem Profil, „frei" bei den drei
  freien). Ein Absatz erklärt, was „gesät" heißt.
- **Abschnitt „Gremien" (45-gremien)**: neue Tabelle „Dokumente je passendem Ausschuss" mit Zahl,
  Anteil, davon ohne Ausschussberatung und dem Median der Wahrscheinlichkeit, dazu zwei Absätze
  zur Methode und zur Restklasse. Kein Download extra: `ausschuss_zuordnung` ist eine
  veröffentlichte Tabelle (Parquet und CSV), die Zuordnung je Dokument bleibt unter `processed/`
  (19 033 Zeilen wären als CSV 1,5 MB, und sie folgt nicht aus der dokumentierten Regel).
- **Größen**: `index.html` 1 158 408 Bytes (1,10 MB) bei einem Budget von 1,5 MB, 50 Dateien
  zusammen 13,3 MB. Voller Offline-Lauf 23,4 s.
- **Unberührt**: `wahlbezirke_auswertung.parquet`, Tabelle 5, der invertierte Index, das
  Wörterbuch. Die `thema_NN`-Zeilen der Gewichtungstabelle ändern ihre Zahlen, weil die Themen
  andere sind; die Zerlegung (`Σ_k thema_k = einheit`) hält weiter, ein Vertrag prüft sie.

## 7. Annahmen und offene Fragen

| Nr. | Annahme | Was Konrad umstoßen könnte |
|---|---|---|
| 1 | Gesäte Themen sind die Vorgabe, obwohl ihre NPMI-Kohärenz um ein Fünftel unter der freien NMF liegt: Namen wiegen mehr als Kohärenz. | `topics.seed = "none"` in `settings.local.toml` oder im Profil rechnet freie NMF, ohne Codeänderung. |
| 2 | `k` bleibt 20 und `free` ist 3, also bekommen die 17 größten Ausschüsse ein Thema und sechs kleine keines. `k = 26` mit `free = 3` gäbe allen 23 ein Thema. | Die Zahl der Zeilen in der Sensitivitätstabelle hängt daran (26 Varianten heute). |
| 3 | Die Schwelle der Restklasse ist 0,4, also das Achtfache des Zufalls bei 20 Klassen; 62 % der Dokumente bleiben darunter. | 0,3 ordnet mehr zu, 0,5 weniger; die Tabelle auf der Seite nennt die Schwelle. |
| 4 | `classify.min_documents = 10` lässt AWIZ (10 Dokumente) als Klasse zu, die nie erkannt wird und Makro-F1 um vier Punkte drückt. 25 wäre die ehrlichere Grenze für die Güte, 10 die freundlichere für die Mini-Fixture (zwei Klassen). | Eine Grenze von 25 nähme der Mini-Fixture alle Klassen und damit den Golden-Master-Tests den echten Pfad. |
| 5 | Die Ausnahmeliste `topics.stop_keep` im Profil hat zwei Wörter („klima", „tierschutz"). Weitere Sachwörter in Gruppennamen würden dort nachgetragen. | Wer sie leert, verliert „klima" aus dem Thema des Umweltausschusses. |
| 6 | Personennamen, die nie neben einem Amt stehen, bleiben Themenwörter (sechs in den 20 Labels). Eine Mandatsträgerliste aus OParl `memberships` würde das schließen. | Das wäre ein neuer Netzabruf und ein eigener Punkt. |
| 7 | Die Güte des Klassifikators hängt zum Teil daran, dass der Volltext die Beratungsfolge und damit den Ausschussnamen trägt (§ 4.3); die Zahlen in § 4.4 sind darum eine Untergrenze für die Zuordenbarkeit der BV- und Ratsdokumente. | Ein Lauf auf dem Text ohne Fuß wäre die genauere Antwort und ein eigener Punkt. |
| 8 | Die Kürzel der Gremien werden mechanisch Stoppwörter; „bau" ist die eine Ausnahme im Profil, „rat" und „aus" sind bewusst keine (§ 2.1). | Eine Stadt mit anderen Kürzeln braucht ihre eigene Ausnahmeliste; der Code kann die Mehrdeutigkeit nicht sehen. |
| 9 | Die Namen der Ausschüsse kommen weiter aus `[bodies.committees]`; elf Kürzel haben dort keinen gesicherten Namen (KUA, JHA, SCHUA, AGS, AWM, SEBD, HFA, WALTW, WABTW, WPA, AWTL) und stehen als Kürzel auf der Seite. | `fragen.md` 5.2: nach einem Abruf von `organizations` ließen sie sich füllen. |

## 8. Was das Review geändert hat (2026-10-13)

Der erste Durchgang stand am 2026-10-12; das Review danach hat drei Dinge an den Zahlen und zwei
am Code geändert. Festgehalten, damit niemand die alten Zahlen gegen die neuen hält:

- **`bau` ist eine Ausnahme geworden** (§ 2.1). Dadurch steigt die Kohärenz der Stufe `gremien`
  von +0,4282 auf +0,4364; die Vorgabe (Stufe 4) liegt bei +0,4208 statt +0,4224, das gesäte
  Modell bei +0,3349 statt +0,3351. Beide Unterschiede liegen im Rauschen eines anderen
  Vokabulars, der Befund der Stufe `gremien` nicht.
- **Die Saat nimmt nur Wörter, die ihr Ausschuss benutzt** (§ 3.1). Auf der Referenz ändert das
  keine Beschriftung; der Fehler war latent und wurde an einer synthetischen Fixture sichtbar.
- **Die Leckage ist gemessen und benannt** (§ 4.3, neu). Die Kreuzvalidierung bleibt bei 0,941,
  ohne die Gremiennamen sind es 0,929.
- Am Code: die Zuordnung rechnet an einem Frame statt an zwei (ein Join legt die Zeilenfolge
  nicht fest), und die Schritte `topics` und `committees` tragen ihre Schema-Version. Beides
  ändert keine Zahl, beides war ein stiller Versagensmodus.

Erledigt damit: `todo.md`, Punkt 1. Offen bleiben Punkt 2 (Seitengröße), Punkt 3 (Skalierung der
Kennzahlen), Punkt 5 (Literatur) und Punkt 6 (Lizenz).
