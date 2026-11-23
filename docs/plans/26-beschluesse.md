# Vorhaben 26: Beschlusslage und Antragserfolg

Stand 2026-11-24, Stufe 1 (Messen), Branch `feat/26-beschluesse`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „26 Beschlusslage und
Antragserfolg". Messskript: [26-beschluesse-messung.py](26-beschluesse-messung.py).

**Dieser Stand ist nur die Vorab-Festlegung (§ 3.1).** Sie ist committet, bevor die Regel einem
einzigen Antrag eine Klasse gegeben hat. Gesehen war bis dahin nur Beschreibendes: die 22 Werte von
`agendaItem.result` und ihre Häufigkeit je Dokumentart in der Hauptperiode, der Anteil der Anträge mit
Beratung, Tagesordnungspunkt und Ergebnis, und rund 70 Beratungsfolgen als Beispiele.

## 3. Messung

### 3.1 Vorab festgelegt (2026-11-24, 00:41 Uhr, vor jeder Klassenvergabe)

**Einheit.** Ein Antrag: eine Drucksache mit der Rolle `antrag` nach `art2` aus Vorhaben 14
(Dokumentart „Antrag …", „Haushaltsantrag …", „zAntrag …", Fraktions- und Mitgliederantrag; bis 2019
„Vorlage aus der Politik" mit „Antrag" im Titel; der Titel schlägt die Dokumentart, wo beide sich
widersprechen). Grundgesamtheit: die Anträge der drei Düsseldorfer Perioden; Mönchengladbach nur
beschreibend, sobald sein Netzlauf fertig ist. Beschlussvorlagen der Verwaltung und Anfragen werden mit
derselben Abbildung beschrieben, aber nicht validiert.

**Klassen der Beschlusslage** (Frage `ergebnis`, genau eine je Antrag). Maßgeblich ist die **letzte
Entscheidung in der Sache** über alle Beratungen des Antrags, nach Sitzungsdatum: beschlossen, geändert
beschlossen, abgelehnt, zurückgezogen, auch als Empfehlung eines vorberatenden Gremiums. Eine spätere
Entscheidung in der Sache ersetzt eine frühere; Kenntnisnahme, Vertagung und Verweisung ersetzen keine.
Nur wenn es keine Entscheidung in der Sache gibt, zählt der letzte andere Stand.

| Klasse | Bedeutung | Werte von `result`, die sie tragen |
|---|---|---|
| `beschlossen` | angenommen, wie gestellt | einstimmig beschlossen, mehrheitlich beschlossen, beschlossen; Empfehlung einstimmig/mehrheitlich beschlossen |
| `geaendert` | angenommen mit Änderungen | abweichend beschlossen; Empfehlung abweichend beschlossen |
| `abgelehnt` | nicht angenommen, auch förmlich zurückgewiesen | einstimmig abgelehnt, mehrheitlich abgelehnt, abgelehnt aufgrund Stimmengleichheit, zurückgewiesen; Empfehlung … abgelehnt |
| `zurueckgezogen` | vom Antragsteller zurückgenommen | zurückgezogen |
| `erledigt` | behandelt, ohne über ihn abzustimmen | zur Kenntnis genommen, passieren lassen, beantwortet, schriftlich beantwortet |
| `vertagt` | zuletzt vertagt oder zurückgestellt, danach nichts im Datensatz | vertagt, zurückgestellt |
| `offen` | an ein anderes Gremium verwiesen, dort nichts im Datensatz | verwiesen |
| `ohne_ergebnis` | keine Beratung mit einem Ergebnis im Datensatz | (Tagesordnungspunkt ohne `result`, Beratung ohne Tagesordnungspunkt, keine Beratung) |

**Prüfauftrag** (Frage `auftrag`, nur bei `beschlossen` und `geaendert`): `pruefauftrag`, wenn der
Antrag von der Verwaltung **nur** verlangt, etwas zu prüfen, zu berichten, darzustellen oder ein Konzept,
eine Stellungnahme oder einen Vorschlag vorzulegen; `sachbeschluss`, wenn er mindestens eine Sache selbst
festlegt oder eine Maßnahme in Auftrag gibt (auch mit Bericht), Mittel vergibt, etwas erklärt oder Dritte
auffordert. Beurteilt wird der Antrag, wie er gestellt ist; den geänderten Wortlaut kennt der Datensatz
nicht.

**Kriterium** (Briefing, unverändert): **Präzision ≥ 0,95 an 150, Ergebnis für mindestens 80 % der
Anträge**, ausgelegt so:

1. *Präzision*: Anteil der Anträge der Stichprobe, deren Klasse der Regel dem Endlabel (zwei
   Kodier-Agenten, Schlichtung der Uneinigkeiten, F4) gleicht. Eine Einheit ist **richtig**, wenn
   `ergebnis` gleich ist und, wo `ergebnis` `beschlossen` oder `geaendert` ist, auch `auftrag`. Labels
   `unklar` fallen aus Zähler und Nenner und werden berichtet; sind es mehr als 15, ist das Codebuch zu
   unscharf, und das ist der Befund. Erfüllt ist das Kriterium nur, wenn **beide** Zahlen ≥ 0,95 sind:
   die ungewichtete an der Stichprobe und die mit den Schichtgrößen gewichtete (F4, Σ W_h·p_h).
2. *Ergebnis*: Anteil der Anträge der **Hauptperiode** mit einer Klasse außer `ohne_ergebnis`.
   Berichtet wird daneben der Anteil mit **abschließendem** Ergebnis (`beschlossen`, `geaendert`,
   `abgelehnt`, `zurueckgezogen`, `erledigt`) und beides für die beiden anderen Perioden.

**Rückfallregel**, in dieser Reihenfolge, ohne neue Kodierung (dieselben Labels):

- **Rückfall 1, ohne Prüfauftrag**: verfehlt die volle Klasse das Kriterium, erreicht es aber, wenn nur
  `ergebnis` verglichen wird, dann gilt `ergebnis` ohne `auftrag`. Der Prüfauftrag kommt nicht als
  Klasse auf die Seite, „offene Prüfaufträge" entfallen; der beantragte Prüfauftrag bleibt eine
  beschreibende Spalte ohne Anzeige.
- **Rückfall 2, grobe Klassen**: verfehlt auch `ergebnis` das Kriterium, gilt es für die groben Klassen
  `angenommen` (beschlossen, geaendert), `abgelehnt`, `ohne_sachbeschluss` (zurueckgezogen, erledigt),
  `offen` (vertagt, offen) und `ohne_ergebnis`; richtig ist eine Einheit, wenn die grobe Klasse gleich ist.
- Verfehlen auch die groben Klassen das Kriterium: Urteil **umbauen** (eine Runde mit neuer Stichprobe,
  Plan § 8) oder **verwerfen**.

Zusätzlich, für jede Stufe: eine Klasse mit mindestens 10 Einheiten in der Stichprobe und einer
Präzision unter 0,80 kommt nicht als eigene Klasse auf die Seite, sondern nur in ihrer groben Klasse.

**Stichprobe**: 150 Anträge, Seed 26, gezogen mit dem Rang von F4 (SHA-256 aus Seed und Schlüssel, je
Schicht die kleinsten Ränge). Schichten = Klasse der Regel, `pruefauftrag` als eigene Schicht
(angenommen mit Prüfauftrag), feste Aufteilung: beschlossen 25, geaendert 20, pruefauftrag 20,
abgelehnt 20, zurueckgezogen 15, erledigt 15, vertagt 15, offen 10, ohne_ergebnis 10. Hat eine Schicht
weniger Anträge, kommen alle, und der Rest geht an `beschlossen`. Die Regel wird vor dem Ziehen
committet; ändert sie sich danach, gilt eine neue Stichprobe.

**Kodierung**: zwei Kodier-Agenten und ein Schlicht-Agent nach F4. Sie sehen je Antrag Titel,
Drucksache, Datum, Dokumentart, den Textanfang und die Beratungsfolge, wie der Server sie füllt (je
Beratung Gremium, Rolle, Sitzungsdatum, Nummer und Bezeichnung des Tagesordnungspunkts, Wortlaut von
`result`); nicht die Klasse der Regel, nicht die Schicht.

**Erfolg je Fraktion**: nur standardisiert und „explorativ" (Frage 14, Annahme). Erfolg = Anteil
`angenommen` unter den Anträgen mit `angenommen` oder `abgelehnt`; erwartet = Summe der Erfolgsquoten
von Gremium und Periode über die Anträge der Fraktion (indirekte Standardisierung wie 14 § 3.8); ein
gemeinsamer Antrag zählt für jede beteiligte Fraktion. Keine Hypothese, kein Test.
