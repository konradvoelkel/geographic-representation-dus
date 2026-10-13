# Seitengröße der Berichtsseite (2026-10-13)

`docs/todo.md`, Punkt 2: die Seite ist zu groß. `index.html` trägt 1 281 464 Byte bei einem Budget von
1,5 MB, fünfzehn Abschnitte und 43 Tabellen, und alles steht ausgeklappt da. Konrad wünscht eine
kompaktere Darstellung: Tabellen zu, nur zwei bis drei Zeilen sichtbar, der Rest auf Bedarf.

Dieses Dokument misst zuerst (§ 1), benennt dann, was groß ist (§ 2), und entscheidet daraus zwei
Änderungen (§ 3 und § 4). § 5 geht die übrigen Posten durch, je mit gemessenen Bytes und einer
Entscheidung, § 6 stellt vorher und nachher gegenüber, § 7 setzt das neue Budget, § 8 nennt die
Annahmen. Nachrechnen: `uv run python docs/seitengroesse-2026-10-messung.py`.

Ergebnis: `index.html` 958 527 Byte statt 1 281 464 (−25,2 %), elf Tabellen zeigen drei Zeilen und
klappen auf Bedarf auf, das Budget ist 1,0 MB statt 1,5 MB.

## 1. Messung vom 2026-10-13 (vorher)

`index.html` 1 281 464 Byte, gzip rund 218 KB (über HTTP liegt die Seite gezippt; das Budget gilt für
die Datei). Die gzip-Zahl steht nur gerundet da: sie schwankt mit dem Zeitstempel in
`generated_at`, also von Lauf zu Lauf. Die Zahlen stammen aus dem Lauf über die volle Referenz vom 2026-10-13, also nach den
Umschaltern (Punkt 46) und der Literaturübersicht (Punkt 47).

### 1.1 Je Abschnitt

| Abschnitt | Byte | davon |
|---|---:|---|
| `begriffe` | 347 050 | 333 750 die 41 Begriffslisten je Wahlbezirk, 7985 zwei Tabellen |
| `karte` | 242 584 | 238 245 das SVG (185 917 die 1196 Orte, 50 505 die 41 Flächen) |
| `parteien` | 193 826 | 98 485 Tabellen (94 463 die Bezirkstabelle), 89 873 die sechs Karten |
| `suche` | 139 615 | 138 565 der Vorschlagsindex als JSON |
| `kontrollvariablen` | 60 178 | 50 128 die vier Added-Variable-Plots, 7565 Tabelle 6 und 6b |
| `downloads` | 48 455 | 45 733 Tabellen (16 549 die Dateiliste, der Rest die Spaltendoku) |
| `gremien` | 41 935 | 37 132 drei Tabellen |
| `wahlbezirke` | 40 673 | 40 109 die Tabelle je Wahlbezirk |
| `gewichtung` | 34 396 | 31 139 zwei Tabellen |
| `monate` | 29 980 | 18 265 das Balkendiagramm, 11 071 die Monatstabelle |
| `zusammenhang` | 28 232 | 24 873 das Streudiagramm, 1391 Tabelle 5 |
| `literatur` | 12 428 | fünfzehn Einträge |
| `methode` | 6413 | |
| `abgeleitete-daten` | 5818 | |
| `kernzahlen` | 1127 | die Kacheln |
| Rahmen, Kopf, Fuß | 48 754 | 17 678 das CSS, 26 788 das Basis-JavaScript, Rest Kopf, Fuß, Dialog |

### 1.2 Je Elementart

| Art | Zahl | Byte |
|---|---:|---:|
| `<svg>` | 8 | 421 384 |
| `<table>` | 43 | 285 001 |
| `<script>` | 3 | 165 353 (138 565 der Suchindex, 26 788 das JavaScript) |
| `<style>` | 1 | 17 678 |

### 1.3 Die Tabellen über zehn Zeilen

| Abschnitt | Tabelle | Zeilen | Byte |
|---|---|---:|---:|
| `parteien` | `urheber-tabelle` | 41 | 94 463 |
| `wahlbezirke` | `districts` | 41 | 40 109 |
| `gewichtung` | `gewichtung-tabelle` | 27 | 24 381 |
| `gremien` | `gremien-bezirke` | 41 | 21 881 |
| `downloads` | `downloads-table` | 50 | 16 549 |
| `monate` | `monate-tabelle` | 61 | 11 071 |
| `gremien` | `gremien-liste` | 38 | 9680 |
| `gewichtung` | `themen-tabelle` | 20 | 6758 |
| `begriffe` | stadtweite Begriffe | 55 | 5781 |
| `gremien` | `ausschuss-tabelle` | 20 | 5571 |
| `abgeleitete-daten` | Spalten der Kontextdaten | 13 | 4391 |
| `downloads` | Spaltendoku, sechs Tabellen | 12 bis 23 | je 1816 bis 4176 |
| `begriffe` | trefferstärkste Begriffe | 20 | 2204 |
| `kontrollvariablen` | Tabelle 6b | 13 | 2935 |

## 2. Was groß ist, und warum

Drei Posten tragen zusammen 57 % der Seite, und sie sind von ganz verschiedener Art:

1. **Die Begriffslisten je Wahlbezirk** (333 750 Byte, 26 %): 3946 `<li>` mit einer Schaltfläche je
   Begriff, in 41 `<details>`. Sie sind schon heute *zu* — nur stehen sie trotzdem in der Datei.
   Das ist reine Datenmenge, und sie liegt an der falschen Stelle.
2. **Die 1196 Orte der Karte** (185 917 Byte, 15 %): je ein `<circle>` mit `data-name`,
   `data-district` und einem `<title>`, der dieselben beiden Angaben wiederholt.
3. **Der Vorschlagsindex der Suche** (138 565 Byte, 11 %): bewusst inline, damit die Suche ohne
   Webserver und ohne Netz läuft (`docs/plans/08-suche.md`, § 2; `docs/decisions.md`, Punkt 22).
   Der bleibt, wo er ist.

Dahinter kommen die Tabellen mit 41 Zeilen. Die teuerste ist die Parteitabelle mit 2281 Byte je
Zeile: sechs Parteien mal drei Varianten des Umschalters (Punkt 46). Die Zeile selbst ist also
nicht zu dick — es sind viele Zeilen, und sie stehen alle offen da. Genau das ist Konrads Punkt.

## 3. Entscheidung 1: lange Tabellen zeigen drei Zeilen

Jede lange Tabelle zeigt Kopf und die ersten `report.table_preview_rows` Zeilen (Vorgabe: 3); **vor**
der Tabelle steht eine Schaltfläche „▸ alle *n* Zeilen zeigen", die alle Zeilen aufklappt und wieder
einklappt. Das Muster ist ein Makro in `templates/macros.html.j2` und gilt für alle Abschnitte. Vor
und nicht hinter der Tabelle, weil das Aufklappmuster der WAI-ARIA Authoring Practices das
Bedienelement vor den Inhalt setzt — und weil die Schaltfläche hinter 41 Zeilen beim Aufklappen mit
dem Fokus aus dem Bild rutschte (Review 2026-10-13). Das Dreieck kommt aus `aria-expanded` über
`::before` und nicht aus JavaScript.

### 3.1 Warum ein `<button>` und kein `<details>`

`<details>` geht hier nicht: das Inhaltsmodell von `<tbody>` erlaubt nur `<tr>` und
skript-tragende Elemente. Ein `<details>` um die hinteren Zeilen würde vom HTML-Parser aus der
Tabelle herausgetragen (foster parenting) — die Zeilen landeten *vor* der Tabelle und wären keine
Tabellenzeilen mehr. Eine Tabelle in zwei Tabellen zu zerlegen (die Vorschau und der Rest in einem
`<details>`) bricht die Spaltenbreiten, die Sortierung und die Beziehung Kopf-zu-Zelle. Also ein
`<button type="button">` mit `aria-expanded` und `aria-controls` auf die Tabelle, wie die
WAI-ARIA Authoring Practices es für einen Aufklapper ohne eigene Semantik vorsehen. `<details>`
bleibt, wo es heute schon steht: um die Begriffslisten je Wahlbezirk und um die stadtweiten
Begriffe, denn das sind Blöcke, keine Tabellenzeilen.

### 3.2 Warum CSS und nicht `hidden` je Zeile

Die Vorschau entsteht aus einer Regel, nicht aus Attributen:

```css
table.preview tbody tr:nth-child(n+4) { display: none; }
table.preview.open tbody tr, table.preview tbody tr.selected { display: table-row; }
```

Das kostet 17 Byte je Tabelle (` class="preview"`), also rund 240 Byte über die Seite, statt rund
7 Byte je verborgener Zeile (` hidden` an 428 Zeilen, rund 3 KB) — aber der Grund ist nicht die
Größe, sondern dass drei Dinge dadurch ohne eine Zeile JavaScript richtig sind:

- **Sortieren.** Die Sortierung hängt Zeilen im `<tbody>` um. `nth-child` zählt die neue Folge, die
  Vorschau zeigt also nach dem Sortieren die ersten drei Zeilen *der neuen Ordnung*. Mit `hidden` je
  Zeile wären es die drei zufällig unverborgenen.
- **Markieren.** `window.georep.select(ids, scroll)` setzt die Klasse `selected` auf die Zeile; die
  zweite Regel zeigt genau sie. Eine eingeklappte Zeile klappt damit beim Auswählen auf — aus der
  Karte, aus dem Streudiagramm und aus der Suche —, und `scrollIntoView` findet sie. Beim nächsten
  `select` räumt dieselbe Mechanik wieder auf, weil `select` die Klasse überall entfernt.
- **Springen.** Dieselbe Regel nennt `tr:target`: `index.html#bezirk-17` aus einer geteilten
  Adresse zeigt die Zeile, auf die die Adresse zielt, und der Browser scrollt sie selbst ins Bild.
  Dafür liest niemand `location.hash`.
- **Drucken.** `@media print` setzt dieselbe Regel auf `table-row` und blendet die Schaltflächen aus;
  die Druckansicht ist vollständig, ohne dass jemand vorher klickt.

Ohne JavaScript steht alles offen: ein `<noscript><style>` im Kopf hebt die Vorschau auf und blendet
die Schaltfläche aus, die ohne Skript nichts tun könnte. Das ist die einzige Stelle, an der die Seite
überhaupt zwei Zustände hat, und sie kostet 131 Byte.

Die Umschalter der Normierung (Karte, Parteien) tauschen Attribute über `querySelectorAll` im ganzen
Dokument; eine verborgene Zeile ist im DOM und wird mitbedient. Das gilt unverändert weiter und
gehört zur Prüfung mit headless Chrome.

### 3.3 Welche Tabellen

Vorschau bekommen die zwölf Aufzählungen: `districts`, `urheber-tabelle`, `gremien-bezirke`,
`gremien-liste`, `ausschuss-tabelle`, `monate-tabelle`, `gewichtung-tabelle`, `themen-tabelle`,
`downloads-table`, `top-begriffe` (die trefferstärksten Begriffe), `kontext-variablen` (die Spalten
der Kontextdaten) und `perioden-tabelle` — die Tabelle je Wahlbezirk des Abschnitts „Zwei
Wahlperioden", die erst mit den Daten der zweiten Periode erscheint; auf der heutigen Seite sind es
also elf. `top-begriffe` und `kontext-variablen` bekommen dafür eine ID, denn `aria-controls`
braucht eine (die übrigen hatten schon eine). Die sechs Tabellen der Spaltendoku brauchen keine: sie
stehen schon je in einem `<details>`.

**Offen bleibt der Befund**, unabhängig von seiner Länge: die Kernzahlen, Tabelle 5
(`zusammenhang`), Tabelle 6 und 6b (`kontrollvariablen`, 13 Zeilen) und die Kacheln der Gremien. Wer
die Zahl sucht, um die es geht, soll sie sehen, ohne zu klicken. Das Kriterium ist also nicht die
Zeilenzahl, sondern die Rolle: eine Aufzählung klappt ein, ein Ergebnis nicht. Dass die Vorschau
ohnehin nur greift, wo mehr Zeilen als Vorschauzeilen stehen, erledigt die kurzen Tabellen von
selbst (Review 2026-10-13, Befund 10).

## 4. Entscheidung 2: die Begriffslisten werden nachgeladen

Die 41 Listen wandern in `data/begriffe.json` und werden beim ersten Aufklappen geholt, genau wie
`data/dokumente.json` beim ersten Klick auf einen Begriff. Inline bleiben die zwanzig
trefferstärksten Begriffe stadtweit, die stadtweiten Begriffe, die fünf häufigsten je Wahlbezirk in
der Bezirkstabelle und je Wahlbezirk die Zahl seiner Begriffe in der Zusammenfassung des `<details>`.

Das ist die eine große Datenmenge, die nicht in der Seite liegen muss. Die Suche muss es
(`docs/decisions.md`, Punkt 22: Vorschläge ohne Webserver, `fetch` ist unter `file://` verboten) —
eine Begriffsliste je Wahlbezirk muss es nicht: wer sie aufklappt, will stöbern, und wer aus
`file://` stöbert, bekommt denselben Hinweis, den der Dokumentdialog heute schon zeigt (ein Satz, der
sagt, dass es über einen Webserver oder unter der veröffentlichten Adresse funktioniert). Die Datei
steht im Register der veröffentlichten Dateien, also mit Zeilenzahl, Größe und SHA-256 im Abschnitt
„Downloads" wie jede andere.

**Verworfen:** die Listen in `dokumente.json` mitführen (2,3 MB für eine Begriffsliste nachladen);
die Begriffe eines Bezirks aus `combined_searchdict.parquet` im Browser lesen (Parquet im Browser
braucht eine Bibliothek); eine Unterseite je Wahlbezirk (41 Dateien, und die Reihenfolge der
Abschnitte soll bleiben, `docs/plans/00-synergien.md`, § 5.1).

## 5. Die übrigen Posten, gemessen

Die Prozente beziehen sich auf die Seite nach den Änderungen (886 328 Byte); das Dokument hat sie
nach dem Review vom 2026-10-13 nachgezogen, vorher standen dort die Anteile an der alten Seite.

| Posten | gemessen | Entscheidung |
|---|---:|---|
| Begriffslisten je Wahlbezirk | 333 750 B | **nachladen** (§ 4) |
| Lange Tabellen offen | — | **Vorschau** (§ 3); kostet rund 4 KB, spart keine Bytes |
| `<title>` in den 1196 Orts-Kreisen | 73 842 B (7,7 % der Seite davor) | **gemacht** (Review 2026-10-13, Befund 2). Die Ebene der Orte ist `aria-hidden="true"` und ohne JavaScript nie sichtbar — der `<title>` erreichte also keinen Screenreader und wiederholte nur, was der Tooltip aus `data-name` und `data-district` zeigt. Mit dem `<title>` fiel auch das schließende `</circle>` weg, darum 73 842 statt der geschätzten 64 274 B. Gezogen, weil das Budget sonst den Abschnitt „Zwei Wahlperioden" nicht mehr getragen hätte (§ 7) |
| Doppelte SVG-Pfade: die 41 Flächen stehen in der Karte und noch einmal in den `<defs>` der Parteikarten | 28 086 B (3,2 %) | **nicht gemacht.** Ein gemeinsames `<defs>` verlangt, dass auch die Hauptkarte ihre Flächen als `<use>` zeichnet. Dort hängen Klick, Hover, `tabindex="0"`, Tooltip und der Klassentausch des Umschalters; ob ein `<use>` in jedem Browser fokussierbar ist und ob Selektoren den geklonten Inhalt treffen, ist zwischen SVG 1.1 und SVG 2 verschieden und hier nur in Chrome prüfbar. 3,2 % sind das Risiko am Herzstück der Seite nicht wert, solange das Budget ohne sie hält. Der größte Posten der Reserve |
| `data-name` an den Orts-Kreisen, der Tooltip liest ihn aus einem anderen Attribut | rund 29 000 B | **nicht gemacht.** Ohne `data-name` braucht der Tooltip eine andere Quelle für den Namen; der `<title>` ist weg, und ein zweites Attribut spart nichts |
| `r="2"` an den 1196 Kreisen, stattdessen CSS | 10 764 B (1,2 %) | **nicht gemacht.** `r` als CSS-Eigenschaft ist erst ab Chrome 102, Firefox 72 und Safari 16 da; ältere Browser zeichneten die Orte dann mit Radius 0 |
| Koordinaten der Pfade mit einer Nachkommastelle statt zwei | 4034 B je Vorkommen, mit der Dopplung 8068 B (0,9 %) | **nicht gemacht.** Die `viewBox` ist 600 Einheiten breit, eine Einheit also rund 43 m: eine Stelle weniger kostet bis 2,2 m Genauigkeit, weniger als die 15 m der Vereinfachung. Trotzdem nur 0,9 % für eine Änderung an `to_svg_paths`, dessen zwei Stellen in Vertrag und Tests stehen |
| Sortierwerte in `data-value` runden | 3953 B (0,4 %) | **nicht gemacht.** 470 der 2887 Werte sind lang (`0.18908504561526973`); 0,4 % für eine Rundung, die in jeder Vorlage einzeln stehen müsste. Die Werte der Umschalter sind seit Punkt 46 schon auf sechs Stellen gerundet |
| Leerraum zwischen Tags (ein Minify-Schritt) | 4442 B in 4416 Stellen, **0,50 %** | **nicht gemacht.** Der Auftrag setzt die Grenze bei 5 %; 0,50 % lohnt keinen Schritt in der Kette. Der Grund für die kleine Zahl: die Vorlagen schreiben mit `trim_blocks` und `lstrip_blocks`, es steht also schon fast kein Leerraum in der Datei. (Vor dem Nachladen der Begriffslisten waren es 12 350 B in 12 335 Stellen — die 41 Listen trugen zwei Drittel aller Stellen) |
| Vorschlagsindex der Suche spaltenweise kodieren | rund 8000 B (0,9 %) | **nicht gemacht.** Stand schon in Punkt 22 als Reserve; vier Indexzugriffe je Eintrag im JavaScript für 0,9 % |

Reserve zusammen, mit bekannten Kosten: rund **40 KB** (doppelte Pfade 28 KB, Suchindex 8 KB,
Leerraum 4,4 KB).

## 6. Nachher: die Messung vom 2026-10-13

Dieselbe Messung nach allen Änderungen (einschließlich der Befunde des Reviews vom selben Tag), über
dieselbe Referenz, mit demselben Skript:

| Posten | vorher | nachher | Änderung |
|---|---:|---:|---:|
| **`index.html` gesamt** | **1 281 464** | **886 328** | **−395 136 (−30,8 %)** |
| davon gzip | rund 218 KB | rund 186 KB | rund −32 KB |
| Abschnitt `begriffe` | 347 050 | 16 506 | −330 544 |
| Abschnitt `karte` | 242 584 | 168 742 | −73 842 (die `<title>` der Orte) |
| Abschnitt `parteien` | 193 826 | 194 000 | +174 |
| Abschnitt `suche` | 139 615 | 139 615 | 0 |
| Abschnitt `kontrollvariablen` | 60 178 | 60 178 | 0 |
| Abschnitt `downloads` | 48 455 | 49 008 | +553 |
| Abschnitt `gremien` | 41 935 | 42 457 | +522 |
| Abschnitt `wahlbezirke` | 40 673 | 40 841 | +168 |
| Abschnitt `gewichtung` | 34 396 | 34 746 | +350 |
| Abschnitt `monate` | 29 980 | 30 153 | +173 |
| Abschnitt `abgeleitete-daten` | 5818 | 6017 | +199 |
| Rahmen (CSS, JavaScript, `<noscript>`) | 48 754 | 55 865 | +7111 |
| neu: `data/begriffe.json` | — | 96 413 | liegt daneben, nicht in der Seite |

Die Vorschau kostet 2139 Byte in den Abschnitten (zwölf Schaltflächen und zwölf Klassen) und steht
im Rahmen mit ihren Regeln, dem Druckblock, dem `<noscript>` (131 Byte) und der Logik der
Schaltfläche; dazu kommen dort das Skript des Abschnitts „Begriffe", der gemeinsame Lader
(`loadJson`, `forget`, `offlineNote` mit seinen zwei Sätzen) und die nachgerechneten Kontraste als
Kommentar — zusammen die 7111 Byte. Gespart haben die Begriffslisten 330 544 und die `<title>` der Orte 73 842. Die gzip-Größe
steht nur gerundet da: sie schwankt mit dem Zeitstempel in `generated_at`.

Geprüft am 2026-10-13 mit headless Chrome und über den lokalen Server auf Port 8777, hell und
dunkel, 375 px und 1200 px breit: kein waagerechtes Scrollen, Konsole leer, drei von 41 Zeilen
sichtbar, die Schaltfläche klappt auf (41) und wieder zu (3) und bleibt dabei an ihrem Platz (die
Tabelle wächst unter ihr), eine Auswahl über `georep.select(17)` klappt genau ihre Zeile auf und
`select(null)` wieder zu, `#bezirk-17` in der Adresse zeigt die Zeile über `:target` und scrollt sie
ins Bild, nach einem Klick auf „Treffer" zeigt die Vorschau die drei trefferstärksten Wahlbezirke
(1, 30, 10), der Umschalter der Karte tauscht die Zahl auch in einer verborgenen Zeile (Bezirk 23:
0,067 → 2,41 → 0,067), die Begriffsliste eines Wahlbezirks kommt beim Aufklappen (72 Einträge, oben
„grafenberger allee" mit 205 Dokumenten), ein Klick darauf öffnet den Dialog mit 205 Dokumenten, und
aus `file://` steht im Abschnitt „Begriffe" der Hinweis statt einer Liste.

## 7. Das neue Budget: 1 000 000 Byte

Die Zahl steht in den Settings (`report.page_budget_bytes`, 0 schaltet ab) und nicht als Literal in
vier Tests; die slow-Tests lesen sie über den Helfer `within_budget` (0 heißt dort wirklich „keine
Prüfung"), der Schritt `report` sagt es selbst, wenn die Seite darüber liegt („Seite über dem Budget
(1,05 von 1,00 MB)"), und `georep publish` nennt jede veröffentlichte Seite über dem Budget — erst
dort kommen die Zeile „Weitere Städte" und die Vergleichsseite dazu. Vorher waren es 1 500 000 bei
einer Seite von 1 281 464 Byte.

**Das Budget muss den Abschnitt „Zwei Wahlperioden" tragen**, der nach Konrads Lauf dazukommt
(Review 2026-10-13, Befund 2). Gemessen an der Mini-Periode: 6859 Byte fest und 551 Byte je
Wahlbezirk, auf 41 also rund 29 KB, dazu die 41 Punkte des Änderungsdiagramms statt dreier — rund
35 KB zusammen. „Laufende Wahlperiode" (rund 0,5 KB) und die Städtezeile aus `georep publish` (rund
0,2 KB) kommen obendrauf. 886 328 Byte lassen **113 672 Byte Luft (11,4 %)**; der Abschnitt passt
also mit rund 79 KB Rest. Die 40 KB Reserve aus § 5 bleiben unangetastet daneben liegen.

Die Luft ist bewusst nicht größer: die Seite ist zwischen dem 2026-10-11 und dem 2026-10-13 um
594 KB gewachsen (Suche 142 KB, Umschalter 110 KB, Parteikarten 63 KB, Gewichtung 33 KB, Monate
30 KB, Literatur 13 KB), ohne dass ein Test gezuckt hätte. Das Budget ist eine Verabredung, keine
Grenze der Technik; wer sie ändert, ändert eine Zahl in `defaults.toml`.

## 8. Annahmen, die Konrad umstoßen kann

1. **Drei Vorschauzeilen** (`report.table_preview_rows = 3`). Zwei wirken bei einer Tabelle mit
   Kopfzeile gedrängt, fünf zeigen schon eine halbe Seite. Die Zahl steht in `defaults.toml` und gilt
   für alle Tabellen gleich; eine Zahl je Tabelle wäre ein Argument am Makro, ist aber nicht gebaut.
2. **Die Vorschau ist der Ausgangszustand, nicht die Erinnerung.** Wer aufklappt und die Seite neu
   lädt, sieht wieder drei Zeilen; die Seite merkt sich nichts (kein `localStorage`, keine Adresse
   mit Zustand). Ein `#bezirk-17` in der Adresse springt trotzdem richtig — aber nicht über
   `select`, das niemand aufruft, sondern weil die Vorschauregel neben `tr.selected` auch
   `tr:target` zeigt. Ohne diese Regel scrollte der Browser für 38 der 41 Wahlbezirke ins Leere
   (gefunden im Review vom 2026-10-13, in Chrome nachgeprüft).
3. **Tabelle 5, Tabelle 6, 6b und die Kernzahlen bleiben offen** (§ 3.3). Wenn Konrad auch dort die
   Vorschau will, ist das je Tabelle ein Wort in der Vorlage.
4. **Die Begriffslisten brauchen jetzt einen Webserver.** Aus `file://` steht dort der Hinweis statt
   der Liste — dieselbe Einschränkung wie beim Dokumentdialog seit Stufe G. Die veröffentlichte Seite
   und jeder lokale Server (`python -m http.server` im Ordner `site/`) zeigen sie.
5. **`begriffe.json` ist eine veröffentlichte Datei**, also mit Zeilenzahl, Größe und Prüfsumme im
   Abschnitt „Downloads". Sie ist damit auch ein Download, den niemand bestellt hat; die Alternative
   wäre eine Datei neben den Downloads, die auf der Seite nicht steht, und das widerspräche der
   Regel, dass jede Datei unter `site/data/` auf der Seite genannt wird (ein Test hält das fest).
   Ins `schema.json` kommt sie nicht: das beschreibt Tabellenspalten, und die beiden JSON-Dateien
   tragen ihre Felder selbst (`fields`).
6. **Die Reserve bleibt liegen** (§ 5): rund 40 KB sind gemessen und nicht geholt, weil das Budget
   ohne sie hält. Wer sie will, bekommt sie zu den dort genannten Kosten.
7. **Das Budget ist 1 000 000 Byte** (§ 7): 113 672 Byte Luft tragen den Abschnitt „Zwei
   Wahlperioden" (rund 35 KB) und lassen danach rund 79 KB. Mehr Luft hieße, das nächste Wachstum
   erst zu merken, wenn es schon da ist; die Zahl steht in `defaults.toml` und lässt sich je Stadt
   ändern.
8. **Die Orte der Karte haben keinen `<title>` mehr** (§ 5): ihre Ebene ist `aria-hidden` und ohne
   JavaScript nie sichtbar, der Tooltip zeigt Name und Wahlbezirk aus den Datenattributen. Wer die
   Ebene für Screenreader öffnen will, braucht ohnehin mehr als 1196 Titel — eine Beschriftung an
   der Gruppe und eine Liste, die man lesen kann.
9. **Die Druckansicht öffnet Tabellen, aber keine `<details>`**: die Begriffslisten je Wahlbezirk
   werden nachgeladen, ein aufgeklapptes `<details>` im Druck wäre also leer. CSS kann ein
   geschlossenes `<details>` ohnehin nicht zuverlässig öffnen; was offen ist, wird gedruckt.
