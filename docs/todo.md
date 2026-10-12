# Rückstand nach dem Ausbau

Stand 2026-10-12, Code auf `v0.11.0`. Konrads Beobachtungen vom 2026-10-12, aufgenommen nach dem Abschluss des
Ausbaus in acht Optionen und bewusst noch nicht bearbeitet. Jeder Punkt nennt den heutigen Stand und Wege, die
zu prüfen wären; Entscheidungen fallen erst mit einem Plan (`docs/decisions.md`, Punkt 20: Pläne werden durch
Beschreibungen ersetzt).

## 1. Themenmodell: die 20 Themen tragen nicht

Heute: TF-IDF und NMF mit 20 Themen (`analysis/topics.py`, Option 06), Wörter je Thema als Label. Konrads
Blick auf die Themen der Referenz: Thema 0 ist „Kosten/Geld", Thema 2 „Bauen", aber Thema 3 ist CDU vermischt
mit anderem, Thema 16 ein seltsamer Linke-Block; vermutlich prägen die Fraktionsnamen aus Kopf und Betreff der
Anträge die Themen. Zu prüfen, in dieser Reihenfolge, weil die Kosten steigen:

- Stoppwörter um Parteien, Fraktionen, Personen und Gremienkürzel erweitern (Option 04 kennt die Muster) und
  dasselbe Modell neu rechnen; billig, zeigt, wie viel davon Rauschen war.
- Gesäte Themen statt freier NMF: je Ausschuss ein Thema mit Startwörtern (Ordnung und Verkehr, Sport, Bauen,
  Schule, Kultur, Jugendhilfe), etwa anchored CorEx oder NMF mit initialisierter Wortmatrix; die Startwörter für
  Ausschüsse wie KUA oder JHA aus den Dokumenten gewinnen, die nachweislich dort beraten wurden (OParl
  `consultation`, Sitzungszuordnung).
- Überwachte Zuordnung statt Themenmodell: die Beratungsfolge aus OParl als Label, ein leichter Klassifikator
  (TF-IDF plus logistische Regression) ordnet dann jedes Dokument dem „passenden" Ausschuss zu, auch eines,
  das nur im Rat war. Konrads Frage, ob das für jedes Schriftstück geht: für die meisten ja; querschnittliche
  Vorlagen (Haushalt, Jahresabschlüsse, Personal) brauchen eine Restklasse. Voraussetzung ist der Vollabruf
  mit `consultation` (STATUS.md, „Nächster Schritt", Lauf 4).
- Einbettungen (Satz- oder Wortvektoren) mit Clustering: teuer auf 19 108 Dokumenten; nur, wenn die
  billigeren Wege nicht reichen, und dann einmal offline mit gespeicherten Vektoren.

## 2. Die Seite ist zu groß

Heute: `index.html` 1,17 MB bei einem Budget von 1,5 MB, 38 Tabellen und alle Abschnitte ausgeklappt. Konrad
wünscht eine kompaktere Darstellung: Tabellen zu, nur zwei bis drei Zeilen sichtbar, der Rest auf Bedarf.
Wege: `<details>` je Tabelle mit sichtbarem Kopf und Vorschauzeilen, lange Tabellen wie `dokumente.json`
nachladen (`data/` liegt ohnehin daneben), Abschnitte mit Zahlen als Unterseiten; danach das Budget neu
setzen. Die Reihenfolge der Abschnitte (`docs/plans/00-synergien.md`, § 5.1) bleibt.

## 3. Skalierung der Kennzahlen

Heute: Parteikarten und Tabellen zeigen je Partei den Anteil ihrer Dokumente mit Bezug auf einen Wahlbezirk,
andere Kennzahlen absolute Treffer oder Quoten je Wahlberechtigte (Bartzsch normiert auf Wahlberechtigte).
Konrad will nicht sehen, wo SPD oder AfD viel reden, sondern wie viel mehr oder weniger als der Durchschnitt
aller Parteien. Zu konzipieren: je Kennzahl eine Auswahl „absolut / je Wahlberechtigte / relativ zum
Durchschnitt aller Parteien" (Differenz in Prozentpunkten oder Log-Verhältnis), mit gemeinsamen Klassengrenzen
und Legende; der Kartenumschalter über `data-class-<metric>` ist der vorhandene Mechanismus dafür.

## 4. Bartzschs Methodik kritisch prüfen

**Erledigt am 2026-10-12, siehe `docs/methodik-review-2026-10.md`** (Regeln und Wirkung in
`docs/decisions.md`, Punkt 44; offene Empfehlungen in § 6 des Reviews, die stärkste: „Treffer je Begriff im
Wörterbuch" als zweite Kennzahl, siehe Punkt 3 hier). Der Auftrag stand so:

Heute reproduziert `v0.11.0` die Zahlen der Arbeit exakt (Tabelle 5 mit Einheitsgewichten, Golden Master
`tests/fixtures/mini/expected/`, slow-Test über die volle Referenz); pragmatische Regeln aus der Arbeit sind
übernommen, etwa `hide_in_display = ["schulweg"]` (zählt, wird nicht angezeigt). Konrad will die Vorgabe
lockern: ungefähre Reproduktion genügt. Vorgehen: vor der ersten bewussten Abweichung einen Tag setzen, der den
letzten exakt reproduzierenden Stand markiert (heute ist das `v0.11.0`), in `docs/decisions.md` und im README
dokumentieren, die Golden-Master-Tests danach gegen die eigene Referenz statt gegen die Arbeit messen. Zu
hinterfragen: die Behandlung der Stadtwerke (heute keine Sonderregel; gesucht ist eine programmatische Regel
für Einrichtungen, die den Stadtnamen tragen und überall treffen, übertragbar auf andere Städte), der
Schulweg-Fall (vielleicht ist die pragmatische Lösung richtig), die Ausschlussliste der Stadtteilnamen, die
Ausreißer 1 und 10.

## 5. Literaturübersicht auf der Seite

Heute nennt die Seite nur die Arbeit als Ursprung. Gewünscht ist ein kurzer Abschnitt mit sauberer Zitation:
Bartzsch (Bachelorarbeit, HHU Düsseldorf, Januar 2026); die Kölner Untersuchung zu Parteien in
Ratsdokumenten, die Bartzsch zitiert (im Literaturverzeichnis der Arbeit nachschlagen); OParl als Standard
und seine Werkzeuge; die Akteure um „Politik bei uns" und „Politik bei uns 2" samt dem Blogbeitrag, der
erklärt, warum das zweite Projekt eingeschlafen ist; weitere verwandte Arbeiten, soweit es sie gibt.

## 6. Lizenz des Codes

Heute CC0 1.0 wie das Original (README, „Lizenz"). Konrad möchte den Code nach einem Tag auf GPL-3.0-or-later
stellen (2026-10-12). CC0 des Ursprungs lässt das zu; Daten, Fremddaten und Fixtures behalten ihre eigenen
Lizenzen (DL-DE BY 2.0, ODbL, CC BY-SA), die Seite nennt sie weiter je Quelle.
