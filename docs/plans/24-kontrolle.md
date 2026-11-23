# Vorhaben 24: Anfragen als Kontrolle in der Kooperation

Stand 2026-11-23, Stufe 1 (Messen), Branch `feat/24-kontrolle`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „24 Anfragen als Kontrolle
in der Kooperation". Messskript: [24-kontrolle-messung.py](24-kontrolle-messung.py).

*Dieser Stand ist der Vorab-Commit (§ 2.11 des Meta-Plans): nur § 8 ist geschrieben, bevor eine Anfrage
einem Dezernat zugeordnet oder je Fraktion und Dezernat gezählt ist. Die übrigen Abschnitte folgen im
nächsten Commit; § 8 ändert sich danach nicht mehr, Ergänzungen stehen datiert darunter.*

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

folgt

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

folgt

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

folgt

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

folgt

## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

folgt

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

folgt

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

folgt

## 8. Vorab festgelegte Hypothesen (nur Analysen: Hypothese, Maß, Test, Schwelle)

Festgelegt am 2026-11-23, bevor eine Anfrage einem Dezernat zugeordnet oder eine Zelle Fraktion ×
Dezernat × Halbjahr gezählt war. Bekannt waren zu diesem Zeitpunkt nur Zahlen anderer Vorhaben, die
nicht nach Dezernat trennen: Anfragen je Fraktion und Gremium (14, § 3.7 und § 3.8) und der
Kontrollanteil je Fraktion (15, § 3.7). Die Zuordnung Anfrage → Dezernat wird in Stufe 1 gemessen und
validiert; die Hypothesen werden erst gerechnet, wenn sie das Kriterium (Präzision ≥ 0,9) erfüllt.
In Stufe 1 wird **keine** Probe der Hypothese gerechnet, auch keine vorläufige: die Daten, an denen sie
später geprüft wird, sind dieselben, und eine Probe würde aus der Prüfung eine Bestätigung des schon
Gesehenen machen (die Lektion aus Punkt 61 und aus 15, § 8).

**Bezug.** Höhmann und Sieberer (2020) zeigen für den Bundestag 1980–2017, dass Regierungsparteien mehr
Fragen an die Ministerien des Koalitionspartners richten, vor allem bei salienten und strittigen Themen,
und dass der Effekt für Fragen an eigene Ministerien und für Oppositionsparteien nicht auftritt; Höhmann
und Krauss (2022) finden mehr Fragen, je detaillierter der Koalitionsvertrag ein Thema regelt. Für
deutsche Großstädte hat Block (2024, European Political Science Review 16 (2), S. 298–314) dasselbe
Muster mit schriftlichen Anfragen in 21 Räten 2011–2020 gezeigt (Zuordnung Anfrage → Dezernat über
CAP-Themen, Mehrebenen-Negativbinomialmodell; Inzidenzratenverhältnis rund 1,5 bis 1,66 je Einheit
ideologischer Distanz), Block (2025, Government and Opposition 60, S. 517–538) für parteilose
Dezernentinnen und Dezernenten (IRR 1,15). Den Volltext von Höhmann und Sieberer konnte der Mess-Agent
nicht lesen (Bezahlschranke); die Angaben stammen aus dem Abstract und den Zusammenfassungen bei Block.

**Übertragung.** Ein Ministerium ist hier ein **Dezernat**, der Minister die Beigeordnete oder der
Beigeordnete, die Koalition die Ratsmehrheit (Kooperation 2014–2020 SPD, Grüne, FDP; 2020–2025 und ab
2025 CDU und Grüne, Belege in 15, § 3.9). Anders als im Bundestag gibt es Dezernate, die eine Person
führt, die eine **Oppositionsfraktion** vorgeschlagen hat (Beigeordnete werden für acht Jahre gewählt
und überdauern die Mehrheit) oder die parteilos ist.

### H1 (die Hauptthese, sie allein entscheidet)

> Fraktionen der Ratsmehrheit richten mehr Anfragen an Dezernate, die eine vom Kooperationspartner
> vorgeschlagene Person führt, als an Dezernate, die eine von ihnen selbst vorgeschlagene Person führt.

- **Einheit**: eine Anfrage (Rolle `anfrage` nach Vorhaben 14, `art()`), gestellt von einer Fraktion
  (`urheber_art = Fraktion`, Partei aus `parteien`; SPD und Volt sind ab 2020 eine Fraktion), in **Rat oder
  Ausschuss** (`gremium_art` `rat` oder `ausschuss`; in 2014–2020 zählen Drucksachen mit einer
  Amtsnummer als Kopf, Punkt 57, zur Stadtebene). Bezirksvertretungen und Beiräte gehören nicht zur
  Hauptprüfung: in den Bezirken gelten andere Mehrheiten (15, § 3.9). Eine gemeinsame Anfrage zählt für
  jede beteiligte Fraktion (wie Block 2024).
- **Dezernatseinheit** *d*: ein Dezernat unter einer Inhaberin oder einem Inhaber, mit dem Zuschnitt zur
  Zeit der Anfrage (Tabelle in § 2, aus dem Dezernatsverteilungsplan der Stadt). Das Dezernat des
  Oberbürgermeisters ist eine Einheit wie die anderen und zählt zur Partei des Oberbürgermeisters.
- **Wer ein Dezernat „führt"**, in dieser Reihenfolge: (1) die belegt vorschlagende Fraktion; (2) sonst
  die Fraktion, der die Kooperationsvereinbarung das Vorschlagsrecht für dieses Dezernat gibt; (3) sonst
  die belegte Parteimitgliedschaft der Person; (4) sonst „keine" (parteilos ohne belegten Vorschlag,
  gemeinsam vorgeschlagen). Die Zuordnung steht als Tabelle mit Quelle und Abrufdatum in § 2 und wird
  vor der Prüfung nicht mehr geändert; eine neue Quelle wird datiert unter § 8 nachgetragen und die
  Prüfung mit beiden Fassungen gerechnet.
- **Status** eines Paars (Fraktion *f*, Dezernatseinheit *d*): `partner`, wenn *d* von einer anderen
  Mehrheitsfraktion geführt wird; `eigen`, wenn von *f*; sonst `andere`.
- **Zeitraum**: ab dem Kalenderhalbjahr, in dem die Kooperation vereinbart ist (2014-2, 2021-1, 2025-2), bis
  zum Ende des Datensatzes (2026-10-13); Anfragen davor zählen nicht.
- **Maß**: *Y* = Zahl der Anfragen von *f*, die das validierte Verfahren (§ 3, eingefroren nach der
  Kodierung) *d* zuordnet, im Kalenderhalbjahr *h*. Anfragen, denen das Verfahren kein oder mehr als ein
  Dezernat gibt, zählen nicht.
- **Stichprobe der Prüfung**: alle Zellen (*f*, *d*, *h*) mit *f* in der Mehrheit, auch die Nullen; Zellen
  einer Gruppe *f* × *h* oder *d* × *h* ohne jede Anfrage fallen heraus (sie tragen zur Schätzung nichts bei).
- **Modell**: Poisson-Regression (Pseudo-Maximum-Likelihood) mit festen Effekten Fraktion × Halbjahr und
  Dezernatseinheit × Halbjahr, log E[*Y*] = α(*f*, *h*) + γ(*d*, *h*) + β · partner(*f*, *d*). α nimmt den
  Fleiß einer Fraktion je Halbjahr, γ die Aufmerksamkeit für ein Dezernat je Halbjahr (Ereignisse, Größe,
  Amtszeit innerhalb des Halbjahrs). β ist identifiziert nur aus Dezernaten, die eine Mehrheitsfraktion
  führt, als Vergleich der Mehrheitsfraktionen untereinander; Dezernate der Kategorie `andere` stützen nur
  die Schätzung von α. Gerechnet über alle drei Perioden zusammen.
- **Test**: einseitig, H1: β > 0, z-Test mit quasi-Poisson-Standardfehler (Überdispersion φ aus der
  Pearson-Statistik, φ ≥ 1), **α = 0,05**. Berichtet wird IRR = exp(β) mit 95-%-Intervall.
- **Vorab genannter Effekt**: **IRR = 1,5** (Partner-Dezernate bekommen anderthalbmal so viele Anfragen wie
  eigene), die Größenordnung der kommunalen Befunde bei Block (2024). Mit ihm rechnet das
  Fallzahlkriterium (§ 3): Teststärke ≥ 0,8 bei α = 0,05 einseitig, simuliert unter Überdispersion wie in
  den Daten. Daneben, nicht entscheidend, die Teststärke für IRR 1,25.
- **Entscheidung**:
  - **bestätigt**, wenn p < 0,05 (einseitig);
  - **widerlegt** (der vorab genannte Effekt ist ausgeschlossen), wenn p ≥ 0,05 und die obere Grenze des
    einseitigen 95-%-Intervalls für IRR unter 1,5 liegt;
  - **nicht entscheidbar** sonst, und immer dann, wenn die Zuordnung die Präzision 0,9 nicht erreicht hat
    oder die Teststärke für IRR 1,5 unter 0,8 liegt. Ein Ergebnis „nicht entscheidbar" steht auf der Seite
    als solches, nicht als „kein Effekt".
- **Vorab festgelegte Nebenrechnungen** (berichtet, entscheiden nicht): (R1) nur Anfragen einer einzigen
  Fraktion; (R2) mit den Bezirksvertretungen (Mehrheit der Bezirke als die des Rates genähert, wie 15);
  (R3) je Periode einzeln; (R4) Dezernat 03 ab der Wiederwahl 2024-09 als von der CDU geführt (die
  Kooperationsvereinbarung 2021 gibt ihr das Vorschlagsrecht „bei einer Neuwahl", die Ausübung ist nicht
  belegt); (R5) Negativbinomialmodell mit denselben festen Effekten statt quasi-Poisson.

### H2 (Nebenthese: strittige Themen)

> Der Partnereffekt ist größer in Dezernaten, deren Feld zwischen den Partnern strittig ist.

- **Maß der Strittigkeit**, vorab gewählt, Hauptmaß: Abstand der Partner auf der Politikdimension des
  Dezernats nach ihren Wahlprogrammen (Vorhaben 25; wie Block 2024 mit Gross und Jankowski 2020). Bis 25
  diese Positionen liefert, ist H2 **nicht entscheidbar**.
- **Ersatzmaß**, schon jetzt messbar und hiermit festgelegt: der Anteil der Anträge (Funktion
  `initiative` nach Vorhaben 15) der Mehrheitsfraktionen im Feld des Dezernats und in der Periode, die eine
  Mehrheitsfraktion **ohne** ihren Partner stellt („Alleingangsquote", Zuordnung zum Dezernat mit
  demselben Verfahren wie die Anfragen), innerhalb der Periode standardisiert.
- **Modell und Test**: H1-Modell plus Wechselwirkung partner × Strittigkeit; einseitig, Koeffizient der
  Wechselwirkung > 0, α = 0,05, quasi-Poisson. Bestätigt, widerlegt und nicht entscheidbar wie bei H1, mit
  dem Ersatzmaß nur als „Ersatzmaß bestätigt" oder „nicht bestätigt" berichtet.

### H3 (Nebenthese: Detailgrad der Vereinbarung, nach Höhmann und Krauss 2022)

> Der Partnereffekt ist größer in Dezernaten, deren Feld die Kooperationsvereinbarung ausführlicher regelt.

- **Maß**: Zahl der Wörter der Vereinbarung im Feld des Dezernats (Zuordnung der Abschnitte durch
  Vorhaben 25), je Periode standardisiert. Bis 25 die Vereinbarungen zerlegt, **nicht entscheidbar**.
- **Modell und Test** wie H2.

### Was ausdrücklich explorativ bleibt

Ob die Opposition Dezernate „ihrer" Beigeordneten schont oder stärker befragt, ob parteilose
Dezernentinnen mehr Anfragen bekommen (Block 2025), Antwortzeiten je Dezernat (14, § 8: mit dem Gremium
als Schicht und der Antwortzeit statt der Antwortquote) und alles, was erst nach der Zuordnung auffällt,
steht auf der Seite als „explorativ".

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

folgt

## 10. Änderungen durch die Synergie (füllt der Supervisor)

—
