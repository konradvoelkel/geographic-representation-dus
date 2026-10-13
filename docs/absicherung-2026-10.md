# Absicherung statt Ausbau (2026-10-13)

Konrads Auftrag für diesen Tag: keine neuen Funktionen, sondern das Vorhandene härten, messen und
die Lehren an den Ort bringen, an dem sie wirken. Nach `v0.11.0` (Ausbau in acht Optionen) und den
Punkten 44 bis 52 standen rund 3 700 Zeilen Code da, die noch kein Mutationslauf gesehen hatte, und
`STATUS.md` unter „Bekannt" war zu einer Liste aus 34 Punkten gewachsen, in der Fakten und
Arbeitsregeln durcheinanderlagen.

Diese Seite ist die Übersicht: was gemessen wurde, was sich geändert hat, was bleibt. Die
Entscheidungen stehen als Punkt 53 in [decisions.md](decisions.md), die Zahlen des Mutationslaufs in
[mutation-2026-10-13.md](mutation-2026-10-13.md).

## 1 Mutationstest über die dreizehn Module des Ausbaus

| | vorher (`v0.12.0`) | nachher (HEAD) |
|---|---|---|
| Mutanten | 876 | 882 |
| getötet | 652 (74,4 %) | **717 (81,3 %)** |
| überlebt | 224 | 165 |

Je Modul eine **eigene Sitzung** mit genau den Testdateien, die es benutzen, und **drei Arbeitern**
(mit sechs wurde die Sitzung am 2026-10-12 unter Last abgeschossen). Zusammen 1 191 s, also rund
20 Minuten für alle dreizehn Module — gemessen, während Konrads Netzläufe liefen. Die sechs
Mutanten Unterschied in der Gesamtzahl stehen in `report/terms.py`, dessen Vorbedingung aus dem
crosshair-Befund sechs Zeilen Prädikat dazugelegt hat; seine Zeile ist darum kein
Vorher-Nachher-Paar. Die Tabelle je Modul, die Deutung der 165 Überlebenden in drei Sorten und die
offenen Posten stehen in [mutation-2026-10-13.md](mutation-2026-10-13.md).

Die größten Löcher, alle mit Tests geschlossen und ohne eine Zeile Produktionscode:

- **`analysis/scaling.dictionary_bias` hatte keinen einzigen Test** (30 → 44 getötet). Die drei
  Korrelationen des Methodenabsatzes der Seite („die Trefferzahl korreliert mit der Größe des
  Wörterbuchs mit r = 0,767") hingen allein am slow-Test.
- **Die Vergleichsseite war nur auf Anwesenheit geprüft** (17 → 31, von 46 % auf 84 %). Dass sie
  entsteht und nur erlaubte Links trägt, prüfte `tests/golden/test_publish.py`; was auf ihr *steht*
  — Mittel oder Summe der Wahlberechtigten, die Koordinaten der Punkte, die Markenform je Stadt, der
  Rückfall des Links auf `./` — prüfte nichts.
- **Die Zahlen des OLS-Modells standen nur im slow-Test** (88 → 98). Besonders hübsch: die
  Indexverschiebung `i + 1` zu `i - 1` fällt bei **einem** Term nicht auf, denn dann ist
  `matrix[:, -1]` dieselbe Spalte; es brauchte ein Modell mit zwei Termen und eine geschlossene Form
  als Orakel.
- **Die Spalte `treffer` der Urheberzuordnung war nie verglichen** (133 → 142). Sie ist der Auszug,
  mit dem ein Mensch eine Zuordnung von Hand nachprüft.
- **Die Richtung des letzten Sortierschlüssels in `crosswalk.py`** (95 → 98): in jedem Beispiel
  waren die Gewichte schon verschieden, der Stichentscheid also unbelegt. Dieselbe Sorte Befund wie
  der `maintain_order`-Mutant vom 2026-10-12 — eine Zusicherung, die nur zufällig gilt.

Nebenbefund, der die Zahlen erklärt: die abdeckungsgeführte Testauswahl von pytest-gremlins
**liefert hier keine Daten** („Coverage collection returned no data", mit `--gremlin-explain`
bestätigt: „Covering set (0 tests)"). Die Ursache ist nicht belegt — nachgemessen ist, dass dem
Vorlauf die **benannten Kontexte je Test** fehlen, nicht die Zeilendaten
([mutation-2026-10-13.md](mutation-2026-10-13.md)). Für die Quote ist das gut (kein Mutant überlebt,
weil ein Test fehlte), für die Laufzeit teuer — und es ist der Grund, warum der Zuschnitt je Modul
keine Bequemlichkeit ist, sondern die Voraussetzung dafür, dass eine Sitzung in Minuten durchläuft.

## 2 Verträge und crosshair

`VERIFY_TARGETS` wuchs von 22 auf **31 Ziele**; neun Kandidaten aus den Modulen des Ausbaus kamen
dazu, je einzeln mit 20 s pro Bedingung geprüft. **Vier fanden ein Gegenbeispiel, und alle vier
waren echt** — jedes dieselbe Sorte Fehler: eine Annahme über die Eingabe, die nur in der
Nachbedingung stand, so dass eine gültige Eingabe die Nachbedingung brach und die Meldung auf die
falsche Stelle zeigte.

| Funktion | Gegenbeispiel | jetzt |
|---|---|---|
| `report.terms.terms_payload` | ein Begriff ohne Treffer; eine Liste in der Folge `[1, 2]` | Vorbedingung: Treffer positiv, Liste absteigend |
| `report.geometry.fit` | `fit((-1.0, 0.0, inf, 1.0), 1.0)` → Skala und Höhe 0 | Vorbedingung: endliche Grenzen |
| `report.model.body_figures` | eine fremde Gremienklasse (`KeyError` ohne Text); `documents = -1` → Anteil 2,0 | Vorbedingung: bekannte Klasse, `0 <= with_hits <= documents` |
| `report.charts.bars` | `width = nan` → `ValueError` aus `nice_ticks` | Vorbedingung: endliche positive Maße |

Dieselbe Lehre wie bei `nice_ticks` am 2026-10-12, dreimal am selben Tag: **eine Vorbedingung über
Zahlen muss sagen, dass sie endlich sind**, und eine Zusage über die Eingabe gehört nicht in die
Nachbedingung.

`uv run nox -s verify` am Ende: **Exit 0**, 31 Ziele, 27 „Not confirmed", kein Gegenbeispiel.
Ausgenommen bleiben zwei Ziele mit gemessenem Grund: `prep.bodies.parse_reference` (crosshair baut
für `re.Pattern | None` einen symbolischen Regex und bricht ab, 2026-10-12) und
`report.charts.bars` — sein letztes Gegenbeispiel ist eine Dokumentzahl mit 300 Stellen neben einer
denormalen Leinwand, und die Vorbedingung, die das abfinge, wäre eine Aussage über crosshair und
nicht über dieses Programm.

## 3 Die bekannten Schwächen

### a) Vorlagen und Anzeige stehen im Stamp des Berichts

Zwei Einträge aus „Bekannt", beide dieselbe Schwäche: der Stamp des Schritts `report` wusste nicht,
woraus die Seite entsteht. Ein Wechsel an einer Vorlage (`templates/sections/*.j2`, ihr CSS, ihr
JavaScript) oder an `literatur.toml` machte ihn nicht ungültig — er trug nur die Code-Version des
Pakets. Und `[report]` ist aus dem Settings-Fingerprint ausgenommen, weil der Block nur die Anzeige
betrifft: für die Parquet-Dateien richtig, für `index.html` falsch, so dass `georep status` den
Schritt nach einer geänderten Klassengrenze als „aktuell" meldete.

`Step` hat dafür ein Feld `extra`, einen kurzen Hash. `report` füllt ihn mit
`report.build.report_fingerprint` über `templates/**`, `literatur.toml`, `settings.report` **und die
vier Anzeigewerte, die der globale Fingerprint auslässt** und die trotzdem auf der Seite stehen:
`bodies.names_as_of` (Stand der Gremiennamen), `period.label` (Überschrift der Periode),
`context.dataset` (Namensnennung der Fremddaten) und die `label` der Gewichtungsregeln (Zeilenköpfe
von Tabelle 5b). Der Review hat diese Lücke gefunden — die erste Fassung schloss nur die Hälfte
(Befund 8).

Einen zweiten Zusatz bekam `topics`: die Stoppwortliste `analysis/stopwords_de.txt` entscheidet,
welche Wörter das Modell überhaupt sieht, und prägt damit `themen.parquet` — im Fingerprint stand
aber nur ihr **Name** (`topics.stop_words = "de"`). Eine gestrichene Zeile änderte das Modell und
liess den Stamp gültig. `schema.stop_words_digest` hasht die Datei, und der Hash sitzt importfrei in
`georep.schema`, weil `build_steps` ihn bei jedem `georep status` braucht.

Was bewusst **mitzählt**, obwohl es nicht zum Schritt gehört: `templates/vergleich.html.j2`. Es
gehört zu `georep publish`; der Preis ist ein Seitenbau von 1,7 s, wenn jemand nur diese Vorlage
anfasst, und das ist billiger, als die Regel „alles unter `templates/`" zu durchlöchern und die
nächste Vorlage zu vergessen (im Docstring begründet).

`stamp_mismatch` liest `extra` mit Vorgabe: ein Stamp von vor diesem Feld bleibt für jeden Schritt
ohne Zusatz gültig, der globale Fingerprint ist unberührt, und die Datenschritte laufen nicht mit
neu. `georep status` sagt jetzt „Paketdateien oder Anzeige geändert".

### b) Das Register gegen die Schema-Konstanten

Der Test zu Punkt 45 kannte eine Liste von sechs Namen und hätte ein siebtes Modell nicht bemerkt.
Statt der Liste jetzt zwei Tests: die Version im Stamp ist die der Datei, neben der er liegt (für
jeden Offline-Schritt der Mini-Kette, 18 Schritte), und jede Schema-Konstante des Pakets gehört zu
einem Schritt — reflexiv gesammelt aus `pipeline`, `schema`, `prep.bodies` und `prep.papers`. Keine
Codeänderung: das Register war an jeder geprüften Stelle schon richtig.

### c) Die Zeilenfolge nach einem Join

Gesucht mit einem Skript über alle 141 Join- und `group_by`-Stellen in `src/`, geprüft von Hand.
Fünf Stellen lasen positionell aus einem Join oder bildeten eine Fließkommasumme darüber:

- `analysis/scaling.dictionary_bias` — drei Spalten positionell, drei Korrelationen; ohne Sortierung
  gaben dieselben Zeilen in anderer Folge **0,5372474566602047 statt …46**.
- `analysis/bodies.regression_frame` — speist `regression_pair`; jetzt mit Nachbedingung
  `sorted_unique`, nicht nur mit einer Sortierung.
- `report/model._variant_frame` und `_per_term_regression` — dieselbe Sorte.
- `pipeline.context_step` — schrieb **zwei veröffentlichte Parquet-Dateien** aus unsortierten Joins,
  gegen die Zusage „zwei Läufe auf denselben Eingaben schreiben byteidentische Parquet-Dateien".

Für die veröffentlichte Tabelle wurde der Join eine eigene Funktion mit Vertrag
(`prep.context.named_weights`): so steht die Zusage, wo sie gilt, und nicht in einem Kommentar im
Register. Gedruckt ändert sich nichts — `uv run pytest -m slow` über die volle Referenz bleibt grün.

Die Sortierung ändert aber die **Zeilenfolge zweier veröffentlichter Dateien**, und ein alter Lauf
liegt unsortiert da. Nach der eigenen Regel bekommt der Schritt darum eine neue Schema-Version
(`prep.context.CONTEXT_SCHEMA_VERSION = 2`, im schreibenden Modul): `georep status` meldet `context`
seitdem als „Schema geändert" und rechnet die beiden Dateien einmal neu. Der Byteidentitäts-Test
(`test_two_runs_write_identical_parquet`) kannte sie beide nicht — er lief ohne Fremddaten und damit
ohne die drei Kontextschritte; jetzt stehen `context_table`, `crosswalk` und `controls` in seiner
Liste (Review-Befunde 4 und 5).

### d) Reihenfolgeunabhängigkeit der Tests

Neue Session `nox -s alone`: jede Testdatei unter `tests/unit`, `tests/golden` und `tests/property`
einmal allein (drei parallel), dann die ganze schnelle Suite rückwärts. `-p no:randomly` gibt es
hier nicht; die Reihenfolge kommt aus `--co` und wird umgedreht, und `xargs -d '\n'` statt
Wort-Trennung, weil ein parametrierter Testname ein Leerzeichen enthält (`-auf'm`).

Gemessen am 2026-10-13: **97 Testdateien, 94 allein grün, drei ohne schnelle Tests**
(`test_bodies_reference.py`, `test_network_period.py`, `test_parties_numbers.py` — jeder Test darin
trägt `slow` oder `network`, Exit 5 = nichts gesammelt); rückwärts **1065 Tests**, die Session
zusammen **228 s, Exit 0**. **Keine Abhängigkeit gefunden** — das ist der Befund, nicht eine
fehlende Prüfung. Gegenprobe: mit einer absichtlich roten Datei bricht die Session mit Exit 1 ab
und nennt sie; die erste Fassung hatte den Exit-Code hinter einem `|| echo` verloren (Review-Befund
7). Die Lehre stand seit dem 2026-10-12 in STATUS; jetzt kann man sie nachrechnen.

### e) Die Gegenbeispiele als `@example`

Drei Lagen der Gebietsumrechnung stehen als `@example` in `tests/property/test_crosswalk_props.py`,
dazu der Faktor 1,4603 aus dem Befund vom 2026-10-13 und zwei gleich große Gewichte für die
Gewichts-Eigenschaften. Der Grund: hypothesis hat die Lagen lokal gefunden, und die
Beispiel-Datenbank liegt lokal — CI zieht sie nur, wenn der Zufall sie trifft. Neu ist
`test_the_weights_do_not_depend_on_the_order_of_the_rows`: die Lehre aus § 3c als Eigenschaft, Zeile
für Zeile mit `assert_frame_equal` und nicht ungefähr.

## 4 Die Lehren an ihrem Ort

`STATUS.md` „Bekannt" trug zwei Sorten: Fakten über das System und die Daten neben Arbeitsregeln
daraus. Die Regeln standen damit an der Stelle, die man liest, um den **Stand** zu erfahren — nicht
an der, die man liest, bevor man etwas **anfasst**.

Elf Regeln sind nach `CLAUDE.md` „Arbeitsweise" umgezogen, je als ein Satz mit Datum: ein Join legt
die Zeilenfolge nicht fest; jeder `Step` holt seine Schema-Version aus der Konstante seines Moduls;
ein Test prüft die Stelle, die er meint; eine Abschnittsvorlage beginnt mit `{% if model.… %}`; eine
Umschalter-Klasse bedeutet auf jeder Fläche dasselbe; einen neuen Test einmal allein starten; nach
einem Rebase die `def`-Zahlen vergleichen; Mutanten in Vertrags-Lambdas werden nicht nachgezogen und
„äquivalent" will nachgerechnet werden; Mutationsziele je Modul messen; Golden-Master-Tests über das
Themenmodell prüfen Invarianten, nicht Zahlen; eine Zahl in einem Test rundet wie die Seite (U+202F
als Tausendertrenner). In STATUS bleiben die Fakten und Zahlen, und ein Satz am Kopf von „Bekannt"
sagt, wo die Regeln jetzt stehen. **Keine Information verloren, nur den Ort gewechselt** (31 Zeilen
weg, 8 dazu).

## 5 Der wiederkehrende Qualitätslauf

`.github/workflows/quality.yml`, montags um 04:17 UTC und von Hand: `nox -s verify` und die
gezielte Mutationssitzung mit zwei Arbeitern über die acht Module, die lokal unter 90 s brauchen.
Kein Netz, kein Pages-Schritt, kein Gate für einen Push — rot wird der Lauf nur bei einem echten
Befund (crosshair findet ein Gegenbeispiel, oder eine Sitzung bricht ab); überlebende Mutanten sind
keiner (decisions.md, Punkt 12).

Gemessen und geschätzt: verify **580 s lokal** mit 31 Zielen, auf dem Runner rund 12 min (crosshair
begrenzt jede Bedingung auf 20 s Rechenzeit, die Zahl der Kerne ändert daran wenig); mutate rund
14 min (403 s lokal mit drei Arbeitern, auf zwei Kernen etwa das Doppelte); zusammen mit Checkout
und `uv sync` **unter 30 Minuten**. `timeout-minutes: 45` ist die Grenze aus dem Auftrag. Die fünf teuren Module stehen mit
Zahl im Kommentar und bleiben dem Lauf von Hand.

## 6 Zahlen am Ende des Tages

| Prüfung | Ergebnis |
|---|---|
| `uv run nox` | Exit 0; 1065 schnelle Tests in 56 s, Abdeckung 98,35 % |
| `uv run pytest -m slow` | Exit 0; 20 Tests über die volle Referenz, 190 s |
| `uv run nox -s bench` | Exit 0; 17 Messungen gegen die gespeicherte Baseline |
| `uv run nox -s verify` | Exit 0; 31 Ziele, 27 „Not confirmed", 581 s |
| `uv run nox -s alone` | Exit 0; 228 s, 97 Dateien allein, Suite rückwärts 1065 Tests |
| `uv run nox -s mutate` | Exit 0; 882 Mutanten, 717 getötet (81,3 %); `-- fast --gremlin-workers=2` in 539 s |

Die schnelle Suite ist von 1021 auf 1065 Tests gewachsen (44 neue), vier Vorbedingungen sind
strenger, fünf Stellen sortieren nach einem Join, zwei Schritte tragen einen Zusatz im Stamp, und
`nox` hat eine Session mehr (`alone`) sowie ein `mutate`, das je Modul läuft.

## 7 Was bleibt

- **Die 165 überlebenden Mutanten.** 100 liegen in Vertragsgrenzen und bleiben dort bewusst liegen
  (decisions.md, Punkt 12), 27 sind nachgerechnet äquivalent. Die 38 anderen sind Grenzen, die nur
  ein genauer Wert unterscheidet, zwei im Standardfall tote Zweige in `report/publish.py` und eine
  unerreichbare Notbremse in `canonical_term`; je mit Grund in
  [mutation-2026-10-13.md](mutation-2026-10-13.md).
- **`report/model.py`, `report/charts.py` und `report/build.py` sind ungemessen.** Zusammen rund
  3 500 Zeilen; ein Mutationslauf darüber ist noch nicht gelaufen, und deshalb behauptet der
  `noxfile`-Kommentar auch nichts über sie. Das ist der nächste offene Posten dieser Art.
- **Die Testauswahl von gremlins bleibt aus**, und warum, ist nicht belegt: nachgemessen fehlen dem
  Vorlauf die benannten Kontexte je Test. Solange das so ist, läuft jeder Mutant gegen alle
  übergebenen Tests, und der Zuschnitt je Modul ist Pflicht. Ein Versuch mit einem anderen
  coverage-Kern (`COVERAGE_CORE=ctrace`) wäre der nächste Schritt; gemessen ist er nicht.
- **`analysis/topics.py`** bleibt aus der Sitzung draußen, weil jeder Mutant NMF rechnet
  (unverändert seit 2026-10-12).
- **Der Qualitätslauf ist nicht erprobt.** Die Laufzeit auf einem Zwei-Kern-Runner ist geschätzt,
  nicht gemessen; der erste geplante Lauf zeigt es. Bleibt er über 30 Minuten, fällt die
  Mutationssitzung weg und nur `verify` bleibt (so steht es im Auftrag).
