# Rückstand nach dem Ausbau

Stand 2026-10-12, Code auf `v0.11.0`. Konrads Beobachtungen vom 2026-10-12, aufgenommen nach dem Abschluss des
Ausbaus in acht Optionen und bewusst noch nicht bearbeitet. Jeder Punkt nennt den heutigen Stand und Wege, die
zu prüfen wären; Entscheidungen fallen erst mit einem Plan (`docs/decisions.md`, Punkt 20: Pläne werden durch
Beschreibungen ersetzt).

## 1. Themenmodell: die 20 Themen tragen nicht

**Erledigt am 2026-10-12, siehe `docs/themenmodell-2026-10.md`** (Entscheidungen in
`docs/decisions.md`, Punkt 45; Messskript `docs/themenmodell-2026-10-messung.py`). Alle vier Wege
sind abgearbeitet und gemessen: die Stoppwörter kommen aus dem Profil und aus dem Korpus, jeder
größere Ausschuss hat ein gesätes Thema mit Namen, ein Klassifikator ordnet jedem Dokument einen
passenden Ausschuss zu (Genauigkeit 0,941, Makro-F1 0,878; vier von fünf BV-Dokumenten bleiben
aber in der Restklasse), und Einbettungen sind mit Zahlen begründet **nicht** gebaut. Offene
Annahmen stehen in § 7 des Dokuments. Der Auftrag stand so:

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

**Erledigt am 2026-10-13, siehe `docs/seitengroesse-2026-10.md`** (Messskript daneben,
Entscheidungen in `docs/decisions.md`, Punkte 48, 49 und 50; offene Annahmen in § 8 des
Dokuments). Gemessen wurde zuerst je Abschnitt, je Tabelle, je SVG und je Skript; daraus zwei
Änderungen und acht Posten, die mit gemessenen Bytes liegen bleiben. Elf lange Tabellen zeigen
Kopf und drei Zeilen und klappen über „alle *n* Zeilen zeigen" auf (die Kernzahlen und die
Tabellen 5, 6 und 6b bleiben offen, sie sind der Befund); die 41 Begriffslisten je Wahlbezirk
stehen als `data/begriffe.json` daneben und kommen beim Aufklappen. `index.html` 1 281 464 →
958 527 Byte (−25,2 %), Budget jetzt 1,0 MB in den Settings. Der Auftrag stand so:

Heute: `index.html` 1,17 MB bei einem Budget von 1,5 MB, 38 Tabellen und alle Abschnitte ausgeklappt. Konrad
wünscht eine kompaktere Darstellung: Tabellen zu, nur zwei bis drei Zeilen sichtbar, der Rest auf Bedarf.
Wege: `<details>` je Tabelle mit sichtbarem Kopf und Vorschauzeilen, lange Tabellen wie `dokumente.json`
nachladen (`data/` liegt ohnehin daneben), Abschnitte mit Zahlen als Unterseiten; danach das Budget neu
setzen. Die Reihenfolge der Abschnitte (`docs/plans/00-synergien.md`, § 5.1) bleibt.

## 3. Skalierung der Kennzahlen

**Erledigt am 2026-10-13, siehe `docs/skalierung-2026-10.md`** (Entscheidungen in
`docs/decisions.md`, Punkt 46; offene Annahmen in § 8 des Konzepts). Das Konzept nimmt alle 35
Kennzahlen der Seite mit Zähler und Nenner auf und entscheidet je Kennzahl, welche Normierung
etwas ändert: gebaut sind der Umschalter der Parteikarten (Anteil / Abweichung vom Mittel aller
Parteien / Verhältnis zum Mittel), drei neue Einfärbungen der Karte (Treffer absolut, Treffer je
Begriff im Wörterbuch, Abweichung vom Stadtmittel) mit der Kennzahlspalte der Bezirkstabelle, und
die zweite Regression neben Tabelle 5; Gremien, Monate, Gewichtung, Kontrollvariablen und Begriffe
bekommen keinen, je mit Grund. Der Auftrag stand so:

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

**Erledigt am 2026-10-13, siehe Abschnitt Literatur** auf der Berichtsseite („Literatur und verwandte
Arbeiten", `#literatur`) und im README; die Einträge stehen als Daten in
`src/georep/report/literatur.toml` (stadtneutral) und als `[[report.literature]]` im Profil der Stadt
(Entscheidungen in `docs/decisions.md`, Punkt 47). Der Auftrag stand so:

Heute nennt die Seite nur die Arbeit als Ursprung. Gewünscht ist ein kurzer Abschnitt mit sauberer Zitation:
Bartzsch (Bachelorarbeit, HHU Düsseldorf, Januar 2026); die Kölner Untersuchung zu Parteien in
Ratsdokumenten, die Bartzsch zitiert (im Literaturverzeichnis der Arbeit nachschlagen); OParl als Standard
und seine Werkzeuge; die Akteure um „Politik bei uns" und „Politik bei uns 2" samt dem Blogbeitrag, der
erklärt, warum das zweite Projekt eingeschlafen ist; weitere verwandte Arbeiten, soweit es sie gibt.

## 6. Lizenz des Codes

**Erledigt am 2026-10-12, siehe `docs/decisions.md`, Punkt 42** (Commit 079725e). Der Quelltext steht seit
dem Tag `v0.11.0` unter GPL-3.0-or-later: `LICENSE` trägt den GPL-Text, `pyproject.toml` das Feld
`license = "GPL-3.0-or-later"`, der README-Abschnitt „Lizenz" nennt beides mit Datum, und der Fuß der
Berichtsseite trennt Quelltext (GPL) von Ergebnissen (CC0). Verworfen sind MIT, Apache-2.0 und AGPL, je mit
Grund in Punkt 42. Daten, Fremddaten und Fixtures behalten die Lizenz ihrer Quelle (DL-DE BY 2.0,
DL-DE Zero 2.0, ODbL, CC BY-SA, CC BY 4.0); die Seite nennt sie je Quelle. Der Auftrag stand so:

Heute CC0 1.0 wie das Original (README, „Lizenz"). Konrad möchte den Code nach einem Tag auf GPL-3.0-or-later
stellen (2026-10-12). CC0 des Ursprungs lässt das zu; Daten, Fremddaten und Fixtures behalten ihre eigenen
Lizenzen (DL-DE BY 2.0, ODbL, CC BY-SA), die Seite nennt sie weiter je Quelle.

## 8. Eine Probe mit `fetch papers --max-pages` verdirbt den folgenden vollen Abruf

Aufgenommen am 2026-11-23, gefunden vom Agenten des Fundaments F6 der Vorverarbeitung 2026-11
(`docs/plan-vorverarbeitung-2026-11.md`). Für die neuen Schritte `meetings`, `consultations` und
`persons` hat er es behoben und mit einem roten Test belegt; in `fetch papers` steckt derselbe
Fehler noch: eine Probe mit `--max-pages` auf einem leeren Store hinterlässt einen Stand, nach dem
der nächste Lauf mit `modified_since` nur noch Geändertes holt, statt die Liste zu Ende zu lesen.
Zu tun: denselben Weg wie in F6 (eine Probe ist der Anfang des Abrufs, der nächste Lauf setzt
fort) für `papers`, mit rotem Test.

## 9. Urheber: Mitantragsteller gehen verloren, das BSW fehlt

Aufgenommen am 2026-11-23 aus der Messung von Vorhaben 15 (`docs/plans/15-funktion.md`, Frage 9.5).
In `analysis/parties.py` gewinnt die erste Quelle (Dokumentart, Titel, Textkopf): bei 281 Dokumenten
gehen Mitantragsteller verloren (etwa „Antrag CDU/Grüne" mit vier Fraktionen im Titel), bei 49
zählt eine Partei mit, die nur im Gegenstand vorkommt, und das BSW fehlt in `[originators]` des
Profils, sodass 12 Anfragen als Person ohne Partei geführt werden. Zu tun: Quellen vereinigen statt
der ersten zu folgen, Parteien im Gegenstand ausschließen, das BSW ergänzen; Wirkung auf die
Parteikarten der Seite mit A/B-Bau messen, weil sich Zahlen ändern.
Die Kodierung von Vorhaben 15 (2026-11-23, `docs/plans/15-funktion.md` § 4.2) bestätigt das: `parteien`
nennt zweimal eine falsche Fraktion (AfD aus dem Gegenstand, SPD aus dem Briefkopf-Fenster); 19 Fraktionen
fehlen, davon 10 in Dokumenten der Urheberklasse „unbekannt", 7 in interfraktionellen Anträgen, deren
Fraktionen nur im Text stehen (Frage 9.15 dort).

## 10. Textübernahme neu messen, wenn die Vorgänge gebaut sind

Aufgenommen am 2026-11-23 aus Vorhaben 23 (`docs/plans/23-textuebernahme.md`, § 4.1 und § 5), das
nach seiner vorab festgelegten Regel verworfen ist: Musteranträge gewichtet 0,889, Übernahmen über
Fraktionsgrenzen 0,296, Schwelle 0,9 je Art. Die Fehler sind vor allem Zitate im selben Verfahren
und Bausteine; beides könnten die Kanten aus Vorhaben 14 (Stufe 2) und die Abschnitte aus 11
abfangen. Eine neue Messung wäre ein eigenes Vorhaben mit neuer Regel, neuem Codebuch (die Vorschläge
des Schlichters stehen in § 9 dort) und frischer Stichprobe, nicht eine zweite Runde an diesen Labels.

## 11. Modellnaht: kleine Punkte aus dem Review von F5

Aufgenommen am 2026-11-23 aus der letzten Nachprüfung von F5 (Punkt 72), keiner verfälscht ein
Ergebnis. (a) Bei einem 5xx auf jede Anfrage fragt ein Lauf alle gemerkten Fehlschläge erneut, je mit
Wartezeiten, ohne anzuhalten, weil sie nicht mehr in die Serie zählen; das kostet nur Zeit.
(b) Weniger als zehn Abweisungen in Folge mit vorübergehender Ursache bleiben als abgewiesen gemerkt;
der Rückweg ist `--retry-rejected`. (c) Wer `embed_texts` oder `generate_texts` außerhalb von
`run_step` aufruft (etwa ein Skript der GPU-Warteschlange), muss `use.reset(retry_rejected=…)` selbst
setzen. Zu klären, wenn die Modellschritte von 19 und 20 gebaut werden.
(d) Eine Tempo-Probe vor dem ersten Stapel eines Modellschritts (oder in `georep ml status`): zweimal
rechnete ollama still auf der CPU, während `ollama ps` „100% GPU" sagte (2026-11-23, 22:42,
`ggml_cuda_init` im Log; Vorhaben 18, Frage 9.5). Bis dahin prüft jeder Lauf das Log und das Tempo von
Hand.
(e) Die Zahl der Korpus-IDs ohne Rohtext, für die `embeddings` keinen Vektor schreibt, steht nur in
der Laufzeile, nicht im Stamp und nicht in `status` (Review von Vorhaben 18, N9; braucht eine Stelle im
Stamp für Zählungen eines Schritts).

## 12. Vorgänge: Rückstand aus der Nachprüfung von Vorhaben 14

Aufgenommen am 2026-11-24 aus der Nachprüfung der Runde 2 (Punkt 76); keiner verfälscht ein Ergebnis.
(a) `references` braucht unter Last mehr als die angestrebten 20 s (21,3 s bei Last 16), rund 7 s davon
`flatten_with_offsets`. (b) Die Mini-Läufe lesen die echten Nachbarpakete relativ zum
Arbeitsverzeichnis. (c) Das README-Gerüst von `pack --attachments` ist das allgemeine. (d) Die
Stamp-Schlüssel von `compare` sind absolute Pfade unter `data_root`; relativ zu `data_root` liefe
`compare` nach einem Umzug nicht neu (0,1 s, Kür). (e) `verweise.parquet` hängt vom Rechner ab: lokal
liegen die Spannen aller Profile auf dem Rohtext, auf Pages nur die der Hauptperiode (die Spalte
`extractor` sagt es); vor Stufe 3 klären, ob die Tabelle so veröffentlicht wird. (f) Die Maske nimmt
einmal ein Sachwort mit („Anfrage Dr. …" statt „… Hitzeschutz"); das README des Pakets sagt es.

## 13. Zeit und Feeds: Rückstand aus dem Review von Vorhaben 17

Aufgenommen am 2026-11-26 aus dem Review der Stufe 2 (Punkt 78); keiner verfälscht ein Ergebnis heute.
(a) `jonckheere` (`analysis/cycles.py`) legt Anzahl × n × n float64 an: bei Gruppengrößen (6, 5, 4)
rund 1,1 GB, bei (6, 5, 5) rund 4,1 GB — das tritt ein, sobald das Paket 2025 bis August 2029 reicht,
und droht auf dem Pages-Runner als Speicherabbruch; in Blöcken zählen oder die exakte Verteilung
falten. (b) Die offene Periode endet am jüngsten Korpusdatum; ein falsch in die Zukunft datiertes
Dokument macht ein Wahljahr vorzeitig vollständig. (c) Fehlt nur `snapshots/2025`, verliert die Seite
den Periodenvergleich (Kopplung von Option 02 an 17). (d) Mönchengladbach hat in keinem Wahljahr einen
Haushaltsmonat; die Unterseite in Stufe 3 sagt das. (e) `cycle_tests` prüft die Schema-Version der
fremden Ordner nicht (wie `compare`).

## 15. Beschlusslage: Rückstand aus dem Review von Vorhaben 26

Aufgenommen am 2026-11-26 aus dem Review der Stufe 2 (Punkt 79). (a) Die Folgevorlage ist je Profil
eine Untergrenze: die Kanten von 14 tragen nur Drucksachen des eigenen Korpus, 114 von 1 508 Anträgen
haben ihre Folgevorlage nur in der Nachbarperiode — soll 14 Kanten aus den Nachbarperioden
mitschreiben? (b) Ein Wortschatz für Mönchengladbach ist eine eigene Messung (48 Werte, darunter
„Siehe Niederschrift", „Ohne Abstimmung", „Die Bezirksvertretung wurde angehört"). (c) Das Messskript
von 26 bricht ab, sobald Dateien Mönchengladbachs im Datenordner liegen. (d) `rolle` bedeutet in
`beratungsverlauf`, `beschlusslage` und `dokumente_vorgang` dreierlei; vor Stufe 3 umbenennen oder in
`schema.json` sagen. (e) `[bodies.organizations]` braucht vor Stufe 3 die Kürzel `gr/400224` und `gr/65`
mit Beleg und A/B-Bau (Frage 9.17 dort).

