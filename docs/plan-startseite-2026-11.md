# Plan: Startseite mit Karte, Zeitregler und Kurzfassung

Stand 2026-11-27. **Freigegeben von Konrad am 2026-11-27, seine Antworten auf § 10 sind die Empfehlungen dort; der Bau ist am selben Tag freigegeben** (nach `v0.38.0`). Weil § 10 beantwortet ist, entfallen der Prototyp P und der Haltepunkt ZS1 (§ 9); die Leistungsmessung mit CPU-Drossel und die Messskripte gehen in B. Gebaut wird U, dann B, je mit eigenem Merge; ZS2 bleibt. Auftrag von Konrad am selben Tag, sinngemäß: Die
heutige `index.html` ist zu lang und zu technisch; sie bleibt, wie sie ist, als Unterseite „Details".
Die neue Startseite zeigt nur Links zu den Unterseiten, eine Kurzfassung und eine Version von
„Politik bei uns": eine Karte, ein Schieberegler für den Zeitraum, die Dokumente als Punkte,
gegebenenfalls filterbar nach Ressort. Der Plan gehört zur Phase „Zeigen"
([plan-zeigen-2026-11.md](plan-zeigen-2026-11.md)); deren Regeln, Budgets (§ 6) und Fragenprotokoll
gelten. Gemessen ist am A-Bau `ab/17s-a` auf xtraspace (`v0.35.0`, alle fünf Profile wie auf Pages) und
an den Hauskoordinaten NRW unter `fremddaten/`; die Messskripte liegen beim Entwurf
(`messung.py`, `messung2.py`, `messung3.py`) und gehören als `docs/plans/startseite-messung.py` ins Repo.

## 1. Ziel und Nicht-Ziele

**Ziel.** Wer die Adresse öffnet, sieht in einer Bildschirmhöhe, worum es geht, was herauskommt und
wo in der Stadt im gewählten Zeitraum welche Dokumente Orte nennen; jeder Punkt führt zu den
Dokumenten im Ratsinformationssystem. Alles Bisherige bleibt unter `details.html` erreichbar.

**Nicht-Ziele.** Keine Zahl ändert sich (Phase „Zeigen", § 1). Keine Kartenkacheln von Dritten auf der
Startseite (Plan Berichtsseite, § 1). Kein Filter nach Partei oder Fraktion auf der Karte. Kein Punkt
feiner als „Straße im Wahlbezirk" (Datenschutz, [16-ortsbezug.md](plans/16-ortsbezug.md), § 3.4 und
Frage 9.7). Kein Server, kein Framework, kein Build mit npm.

## 2. Ausgangslage (gemessen am 2026-11-27, Hauptperiode, wenn nicht anders gesagt)

| Was | Zahl |
|---|---|
| `index.html` heute | 941 988 Byte (gzip 198 539), Budget 1 000 000; davon Kartenabschnitt 168 767 (Ortspunkte 112 114, Flächen rund 52 000), Stil 19 952, Skripte 31 494, Suchdaten 138 585 |
| Unterseiten, `karte.html` | `akteure.html` 105 563 (Stil 17 725, Skript 13 459); `karte.html` 237 882, in Mönchengladbach 356 513 |
| `data/dokumente.json` | 2 262 039 Byte, gzip 525 850; 10 789 Dokumente (10 799 mit Treffer, zehn nur in versteckten Begriffen) |
| Orte (Begriff × Wahlbezirk) mit Treffer | 3 146: 2 745 Straßen, 287 Orte aus Wikidata, 114 beides |
| Punkte (Dokument × Ort) | 50 951; je Dokument Median 3, höchstens 271; je Ort Median 7, P90 44, höchstens 206 Dokumente; 465 Orte mit einem Dokument |
| Sammeldokumente | 276 Dokumente mit mehr als 20 Orten tragen 11 437 Punkte (22 %); 52 mit mehr als 50 |
| Letzte 12 Monate (bis 2025-09-12) | 2 086 Dokumente, 10 295 Punkte an 2 140 Orten |
| Datum | `date` in allen Profilen, keines leer; Hauptperiode 2020-09-14 bis 2025-09-12 (61 Monate), 2014-05-26 bis 2020-09-11, laufend 2025-09-15 bis 2026-10-13, Mönchengladbach 2020-09-14 bis 2025-09-13; Dokumente mit Treffer je Monat Median 188 (45 bis 290) |
| Gremium der Dokumente mit Treffer | Bezirksvertretungen 7 889 (73,1 %), Ausschüsse 2 266 (21,0 %), Rat 550 (5,1 %), Beiräte 94 (0,9 %); 33 Gremien. „Gremium unbekannt": 0 %, 2014–2020 909 von 13 085 (6,9 %), Mönchengladbach 239 von 490 (48,8 %) |
| Amt aus dem Kopf (Vorhaben 11) | 3 486 von 10 799 (32,3 %), 3 430 der 6 150 Verwaltungsdokumente; nur Hauptperiode (Rohtext gibt es auf Pages nur dort) |
| Straßenpunkte aus den Hauskoordinaten NRW | 2 427 von 2 859 Straßenorten mit Treffer (84,9 %) haben Hausnummern im selben Wahlbezirk; Paket je (Straße, Wahlbezirk) 31 144 Byte (Parquet, zstd) |

## 3. Seitenstruktur

| Datei | heute | neu |
|---|---|---|
| `index.html` | die ganze Auswertung | **Startseite**: Kopf mit Datenstand, Kurzfassung (§ 8), Karte mit Regler und Gremium (§ 4 bis § 7), Linkblock, Fuß mit Lizenzen. Budget `report.start_budget_bytes = 150000` hart, Ziel 120 000 (geschätzt 90 bis 110 KB: Rahmen 33, Flächen und Stadtbezirke 50 bis 60, Rest 15) |
| `details.html` | – | der heutige Inhalt unverändert, Budget 1 MB; im Kopf „Zur Startseite"; Titel bleibt |
| `karte.html` | Leaflet und OSM-Kacheln | in U und B unverändert, „zurück" zeigt auf `details.html`; weiter nach Frage S.4 |
| `data/karte.json` | – | Daten der Startkarte (§ 4.5); eine Zeile unter „Downloads" auf `details.html`, wie jede Datei unter `data/` (Punkt 49) |
| Unterseiten (`akteure.html` usw.) | „Zur Hauptseite" auf `index.html` | „Zur Startseite"; der Fuß verweist für Quellen und Lizenzen auf `details.html` |

**Bau.** Der Schritt `report` schreibt `details.html` (bisher `index.html`), die Startseite, `karte.html`
und `data/karte.json`; ein eigener Schritt lohnt nicht, die Startseite liest dasselbe Modell.
`Layout.site_index` bleibt `index.html` (Stamp, Existenzprüfung in `publish`, Monitor, `georep paths`
ändern sich nicht), neu ist `Layout.site_details`. Neuer Code in `report/start.py` und
`templates/start.html.j2` mit `start/karte.js` und `.css`; Dialog und Fuß werden gemeinsame
Teilvorlagen des Rahmens (`frame/dialog.html.j2` mit `data-extras` aus V2, `frame/footer.html.j2`),
weil die Startseite beide braucht. Der Linkblock kommt aus `model.pages` wie `58-weitere`, dazu
Details, Downloads (`details.html#downloads`), die Perioden (`model.comparison.subpage`,
`monitoring_url`), die Nachbarstädte und `vergleich.html`.

**Alte Anker.** Verlinkt wird `index.html#…` heute aus `docs/inhalt.md` (6 Links mit Anker, 22 auf die
Seite), `docs/workflow-ratsmitglied.md` (13 und 21), aus der Seite selbst (`#suche=<begriff>` schreibt
`15-suche.js` als teilbare Adresse, `#bezirk-17` über `:target`) und von außen in unbekannter Zahl
(Pages führt keine Zugriffe). Statisch, ohne Server: ein Skript ganz oben auf der Startseite (unter
0,5 KB) ersetzt jede Adresse, deren Anker kein Schlüssel der Startseite ist, durch `details.html` mit
demselben Anker (`location.replace`). Die eigenen ids der Startseite beginnen darum mit `start-`, ihre
Schlüssel in der Adresse heißen `zeitraum` und `gremium`; ein Test verlangt, dass keiner davon eine id
auf `details.html` ist. Ohne
JavaScript nennt ein `<noscript>`-Satz den Weg zu den Details. Die Doku-Links ziehen in U nach.

**`publish` und Profile.** `write_neighbours` setzt die Zeile „Weitere Städte" in beide Seiten (die
Marke steht in beiden Rahmen). `_over_budget` prüft je Datei: `index.html` jeder Stadt und Periode gegen
`start_budget_bytes`, alles andere wie bisher. `vergleich.html`, `parent_url`, `monitoring_url` und
`36-perioden` verlinken Ordner und landen damit auf der Startseite der Periode oder Stadt; `pages.yml`
kopiert die Periodenordner ganz und braucht keine Änderung. Jede Periode und Mönchengladbach bekommen
ihre eigene Startseite mit eigenem Regler; die Wurzel baut wie heute das Profil `duesseldorf-vergleich`.

## 4. Die Karte

**4.1 Grundkarte: eigene Vektordaten als inline SVG** (Empfehlung). Wahlbezirke wie auf der
Hauptkarte (`report.geometry`, EPSG:25832, 15 m vereinfacht), darüber die Grenzen der Stadtbezirke
(Vereinigung über `wahlbezirke_stadtbezirke`) und die Namen der 50 Stadtteile als Beschriftung
(Portal der Stadt, dl-de/zero-2.0, liegt unter `fremddaten/duesseldorf-stadtteile/`; als Paket nur
Name und Punkt auf der Fläche, geschätzt 3 KB; wo ein Profil keine Stadtteile hat, die
Stadtbezirke). Gründe: offline und aus `file://` lesbar, keine IP-Adresse eines Lesers an Dritte,
dieselbe Palette hell und dunkel, testbar als Text, Größe in der Hand. Verworfen: OSM-Kacheln (jede
Ansicht schickt die IP an `tile.openstreetmap.org`, das wirft die Frage nach Einwilligung auf; die
Nutzungsregeln der OSMF erlauben nur geringe Last; Leaflet als Fremdskript), kommerzielle
Kacheldienste (Schlüssel, Bedingungen, Kosten), eigene Vektorkacheln (PMTiles mit MapLibre: rund
0,8 MB Skript und Kacheln im MB-Bereich, eine Build-Kette). Der Preis ist weniger Orientierung, weil
keine Straßen gezeichnet sind; Rhein, Autobahnen und Bahnlinien als vereinfachter OSM-Auszug (ODbL,
geschätzt 20 bis 40 KB) sind E4.

**4.2 Woher die Punkte kommen.** Ein Punkt ist ein **Ort = (Begriff, Wahlbezirk)**, die Einheit, in der
die Auswertung zählt; eine Straße über sieben Bezirke hat sieben Punkte entlang ihres Verlaufs, und ein
Dokument steht an allen, wie es in allen sieben Bezirken zählt.

| Art | Orte mit Treffer | Lage ohne Vorhaben 16 | mit Vorhaben 16 |
|---|---|---|---|
| Ort aus Wikidata | 401 | Koordinate aus `wikidata_vis` (zwei Labels mit zwei Koordinaten: die im Bezirk) | unverändert |
| Straße | 2 745 | Medoid der Hauskoordinaten dieser Straße im Wahlbezirk (GebRef NRW, dl-de/zero-2.0), auf 25 m gerundet: 84,9 %; sonst Punkt auf der Fläche der Stimmbezirke, die `streets_per_district` für die Straße nennt | dieselben Punkte. Neu: die Grenzstraße (ein Dokument mit verorteter Adresse steht nur am Ort des Bezirks der Adresse, nur als Variante, Frage 24) und die Stelle im Dialog (§ 7) |
| Wahlbezirk | – | nur als Flächenfarbe (§ 4.7) | – |

Hausnummern aus den Texten werden nie zu Punkten: ein Punkt an einer Adresse wäre die Tabelle
„Dokument × Adresse", die 16 ausschließt. Das Paket `snapshots/<stadt>-strassenpunkte/` trägt je
(Straße, Wahlbezirk) einen Punkt und die Zahl der Hausnummern, keine Hausnummer (31 144 Byte für
Düsseldorf), gebaut nach dem Muster von `--need` (Punkt 80) mit `georep pack --street-points`; der
Gemeindefilter kommt aus `city.ags`, Mönchengladbach liegt ebenfalls in GebRef. Ohne 16 geht also
alles; 16 nimmt geschätzt rund 2 000 der 50 951 Punkte weg (1 790 Paare Dokument × Wahlbezirk).

**4.3 Darstellung.** Ein Kreis je Ort, Fläche proportional zu den Dokumenten im Zeitraum (Wurzel,
Mindestradius), halbtransparent, eine Farbe (`--accent`; Kontrast ≥ 3 : 1 gegen die Flächen nach
WCAG 1.4.11, nachgerechnet im Rahmen wie Punkt 48). Keine Bündelung: 2 140 bis 3 146 Kreise sind für
SVG wenig (die Hauptkarte zeichnet 1 196 Ortspunkte). Sammeldokumente über
`report.start.max_places = 20` Orten stehen nicht als Punkt, sondern als Zeile unter der Karte („59
Dokumente im Zeitraum nennen mehr als 20 Orte: zeigen", gemessen für die letzten 12 Monate); die
Zählung der Auswertung bleibt unberührt. Zoom je Stadtbezirk (Auswahl oder Tippen auf den Bezirk, über die `viewBox`), dazu „ganze
Stadt"; kein freies Verschieben in B. Ein Umschalter „Punkte / Flächen" zeigt dieselben Dokumente als
Choroplethe je Wahlbezirk (fünf Quantilklassen wie die Hauptkarte). Canvas nur, wenn der Prototyp
mit vierfacher CPU-Drossel über 50 ms je Neuzeichnen braucht.

**4.4 Ein Satz unter der Karte** sagt, was ein Punkt ist: ein Name aus dem Wörterbuch des Bezirks
kommt im Dokument vor, nicht „das Dokument handelt davon" (16: 78 bis 82 % der Paare handeln davon,
geprüft von KI-Kodierern, nicht von Menschen); große Bezirke mit vielen Straßen haben mehr Punkte
(r = 0,77 zwischen Treffern und Wörterbuchgröße, Link auf `details.html#methode`).

**4.5 Daten und Nachladen.** `data/karte.json`, Format 1: `start` (erster Monat), `months`, `gremien`
(`[kürzel, name, art]`), `places` (`[x, y, wahlbezirk, art, name]`, auf die `viewBox` projiziert, ganze
Zahlen) und `docs` (`[monat, gremium, ort, …]` in der Folge von `dokumente.json`, dieselbe
`documents.document_order` wie V2). Gemessen ohne Ortsnamen: 385 079 Byte (gzip 107 585) mit Tag,
314 901 (gzip 87 912) mit Monat und ohne die Orte der Sammeldokumente; mit Namen geschätzt rund 365 KB
(gzip 110 KB). Geschätzt für die anderen Profile nach der Zahl der Punkte: 2014–2020 rund 440 KB,
laufende Periode 75 KB, Mönchengladbach 20 KB. Die Startseite lädt `karte.json` beim Aufbau;
`dokumente.json` kommt erst beim ersten Klick, wie heute. **Budget**: eine neue Zeile in § 6 der Phase,
`karte.json` höchstens 500 000 Byte roh je Profil, getrennt von den 1,5 MB der Dialogdateien.

**4.6 Handy.** Karte in voller Breite, Regler und Auswahl darunter, native `<select>`, Schieber mit
großem Griff. Ein Tippen sucht alle Orte im Umkreis von 24 Pixeln (eine Abstandssuche statt
Zuhörern an 3 146 Kreisen; Zielgröße nach WCAG 2.5.8) und öffnet bei mehreren zuerst ihre Liste.
Vergrößern über die Stadtbezirke und den Zoom des Browsers.

**4.7 Ohne JavaScript und aus `file://`.** Ohne Skript steht die Karte als Choroplethe „Dokumente mit
Treffer je Wahlbezirk in den letzten 12 Monaten", beim Bau gerechnet; Kurzfassung und Links sind
vollständig, ein `<noscript>` sagt, was fehlt. Aus `file://` lädt `karte.json` nicht: dieselbe
Choroplethe bleibt, darüber der Satz aus `georep.offlineNote`.

**4.8 Barriere.** Die Karte ist eine beschriftete Gruppe; eine `aria-live`-Zeile nennt nach jeder
Änderung „n Dokumente an m Orten, die meisten in …". „Als Liste" zeigt die 20 Orte mit den meisten
Dokumenten im Zeitraum als Tabelle (Vorschau drei Zeilen, Punkt 48), je mit Schaltfläche zum Dialog;
die Wahlbezirksflächen sind fokussierbar wie auf der Hauptkarte. Prüfung mit headless Chrome bei 390
und 1280 Pixeln, hell, dunkel und ohne Skripte, wie Punkt 88.

## 5. Zeitregler

- **Feld**: `date` der Drucksache (OParl), in allen Profilen gefüllt, dasselbe Feld wie `monatsreihe`
  und `dokumente.json`. Nicht das Sitzungsdatum: es gibt es nur in der Hauptperiode (Kopf aus 11) oder
  lokal (F6).
- **Raster und Spanne**: Monate, von Beginn bis Ende der Periode des Profils (61 Monate in der
  Hauptperiode, 77 für 2014–2020, 14 in der laufenden Periode).
- **Voreinstellung**: die letzten 12 Monate bis zum neuesten Dokument, auch in abgeschlossenen
  Perioden (Hauptperiode Oktober 2024 bis September 2025, 2 086 Dokumente). Die Beschriftung nennt das
  Ende („bis September 2025, Ende der Wahlperiode").
- **Bedienung**: zwei Schieber „von" und „bis" (`input type="range"`, `aria-valuetext` mit Monat und
  Jahr), Knöpfe „letzte 12 Monate", „ganze Periode" und je Jahr; darüber die Monatsbalken aus
  `monatsreihe` als schmale Leiste (61 Werte, rund 3 KB), damit man sieht, wo viel liegt.
- **Adresse**: `#zeitraum=2024-10..2025-09&gremium=OVA` ist teilbar, wie `#suche=` auf den Details.
- **Perioden**: je Profil ein Regler. Ein Regler über alle drei Düsseldorfer Perioden (gleiches
  Wörterbuch, gleiche Bezirke, zusammen rund 26 000 Dokumente) ist E5.

## 6. „Ressort"

| Bedeutung | Quelle | Güte | Verfügbar | Haken |
|---|---|---|---|---|
| **Gremium** (Rat, Ausschuss, Bezirksvertretung, Beirat) | Drucksachennummer (Punkt 23), Beratungsfolge (Punkt 58) | Regel, kein Modell; unbekannt 0 / 6,9 / 48,8 % (Hauptperiode, 2014–2020, Mönchengladbach) | alle Profile, auf Pages | 73 % der Dokumente stammen aus Bezirksvertretungen: dort ist der Filter ein Raumfilter („was hat meine BV beraten") |
| **Federführendes Amt** (99 Ämter), gruppiert nach der ersten Ziffer der Amtsnummer (Aufgabengruppen nach dem KGSt-Muster, gegen den Organisationsplan der Stadt nicht geprüft) | Kopf, Vorhaben 11 (Punkt 81) | Amt 125 von 125, zwei KI-Kodierer, nicht von Menschen | nur Hauptperiode, nur Verwaltungsvorlagen (32 % der Dokumente mit Treffer) | „Dezernat" steht nicht in den Daten (`dezernat_titel` ist nur „Beigeordnete", „Stadtdirektor"); dafür bräuchte es den Dezernatsverteilungsplan mit Datum |
| **Politikfeld** (21 Felder des CAP) | Vorhaben 19, Weg 3b | Makro-F1 0,70 (0,62–0,81) gegen KI-Kodierer, nicht von Menschen | nicht gebaut; nur Hauptperiode geprüft | CC BY-NC-SA 4.0 (Frage 37): nur in einer eigenen Datei mit Lizenzzeile, nie in `karte.json` |
| **Passender Ausschuss**, Thema des Themenmodells | Punkt 45b, 45c | 0,941 an Ausschussdokumenten, aber 62 % der Dokumente mit Treffer in der Restklasse | alle Profile mit Text | je Dokument bewusst unveröffentlicht (Punkt 45c); Themennummern gelten nur für einen Datenstand |

**Empfehlung.** In B heißt der Filter „Gremium", in zwei Stufen (Art, dann das Gremium; eine
Bezirksvertretung mit Stadtbezirk benannt, Namen aus `[bodies]`), und das Wort „Ressort" steht nicht
auf der Seite: es verspräche die Verwaltungssicht, die die Daten nur zum Teil tragen. E1 bringt
„Federführendes Amt" als zweite Auswahl in der Hauptperiode, mit einer datierten Tabelle der
Aufgabengruppen im Profil und dem Prüfsatz aus `11-struktur-f4`. E2 bringt das Politikfeld nach
Stufe 2 und 3 von 19 als eigene nachgeladene Datei.

## 7. Klick auf einen Punkt

- Der Dialog des Rahmens (`<dialog id="docs">`); neu ist `georep.showDocumentList(indizes, titel,
  satz)`, auf die `showDocuments` zurückgeht (rund 0,2 KB im Rahmen, also auf jeder Seite).
- **Überschrift**: Name des Orts und Wahlbezirk („Aachener Straße, Wahlbezirk 23 …"). **Satz**: Zahl
  der Dokumente im Zeitraum und unter dem Filter, neueste zuerst, und die Lage („Mitte der Hausnummern
  dieser Straße im Wahlbezirk", „ungefähr: Fläche der Stimmbezirke", „Koordinate aus Wikidata");
  bei einer Straße über mehrere Bezirke „liegt auch in …".
- **Je Dokument** wie heute: Datum, Titel mit Link auf das PDF im Ratsinformationssystem, Drucksache,
  Art, Urheber; darunter ohne weitere Verdrahtung die Zeilen der Beiträge aus V2 (Vorgang von 14,
  ähnliche Dokumente von 18, Beschlusslage von 26). Einen Link auf die Vorlagenseite des RIS gibt es
  nicht: die Daten tragen nur die Datei-URL.
- **Weiter**: „Alle Zahlen zu diesem Begriff" auf `details.html#suche=<begriff>`.
- **Mit 16 (E3)**: je Dokument, wo der Ort genannt ist (Titel, Betreff, Kern, Begleittext), mit dem
  Prüfsatz aus `16-ortsbezug-f4`; Dokumente mit Nennung im Betreff zuerst.

## 8. Kurzfassung

Vier bis fünf Sätze, zusammen höchstens rund 110 Wörter und 2 KB, jeder aus `ReportModel` gerechnet
und mit einem Link auf den Abschnitt von `details.html`, aus dem seine Zahl stammt.

| Nr. | Aussage | Zahl (Hauptperiode) | aus | Profile |
|---|---|---|---|---|
| K1 | Umfang | 19 108 Dokumente, 10 799 (57 %) nennen einen Ort eines der 41 Wahlbezirke | `figures` | alle; liegt der Anteil mit Text unter 90 %, ein Satz dazu (Mönchengladbach 650 von 2 895) |
| K2 | Spreizung mit Vorbehalt | Altstadt/Carlstadt/Hofgarten 0,153 je Wahlberechtigtem, Hassels/Paulsmühle 0,026: fast das Sechsfache; hängt an der Wörterbuchgröße (r = 0,77) | `districts`, `dictionary_bias` | alle mit Streuung |
| K3 | Leitfrage | kein Zusammenhang mit der Wahlbeteiligung belegt (p = 0,23, alle 41) | `regression.all`, Makro `verdict` | ohne Regression (laufende Periode): „zur laufenden Periode gibt es keine Wahlbeteiligung" |
| K4 | Wo beraten wird | 73 % Bezirksvertretungen, 21 % Ausschüsse, 5 % Rat | `gremien` | alle; mit „Gremium unbekannt", wo es das gibt |
| K5 | Empfindlichkeit (wahlweise) | „unter s von 26 Gewichtungen erreicht der Zusammenhang die 5-%-Schwelle" | `sensitivity` | wo gerechnet |

**Regeln.** Nur Aussagen aus dem Verfahren der Arbeit (Golden Master), aus Regeln (Gremium) und aus
dem Test über alle Bezirke; nichts „explorativ" Markiertes (die Spalte „ohne Ausreißer" nicht) und in
B nichts KI-Kodiertes. Kommt später eine kodierte Aussage dazu (15, 16, 19), trägt sie den Prüfsatz
aus `guete.json`. Keine Partei, keine Rangfolge von Fraktionen (Test wie `test_report_city.py`). Die
englische Kurzfassung (`<p lang="en">`) wird ein Makro und steht auf beiden Seiten. Tests: jede Zahl
der Sätze gegen das Modell an der Mini-Fixture; jeder Satz verlinkt eine id, die es auf
`details.html` gibt.

## 9. Einordnung in die Phase „Zeigen"

| Stufe | Inhalt | wann | Version | Läufe |
|---|---|---|---|---|
| P | **Prototyp**: statische Seite aus dem A-Bau (Hauptperiode) mit echten Orten und Straßenpunkten, Regler, Gremium, Dialog über `dokumente.json`; außerhalb des Repos unter xtraspace, über Port 8777; Bildschirmfotos bei 390 und 1280 Pixeln, hell, dunkel, ohne Skripte; Leistung mit CPU-Drossel; Messskript nach `docs/plans/` | sofort, neben den drei laufenden Branches (berührt `src/` nicht) | – | 2–3 |
| ZS1 | **Haltepunkt**: Konrad sieht den Prototyp und beantwortet § 10 | nach P | | |
| U | **Umzug** `index.html` → `details.html` als Refactoring: Rückverweise, `Layout.site_details`, Tests umziehen, Doku-Links; vorläufige Startseite nur mit Kopf, Linkblock und Weiterleitung. A/B-Bau: `details.html` gleich dem alten `index.html` bis auf die Kopfzeile und die Prüfsummen | nach `v0.38.0` (14, 11/12 und 17 gemerged) | `v0.39.0` | 2–3 |
| B | **Startseite**: Kurzfassung, Karte, Regler, Gremium, `karte.json`, Paket der Straßenpunkte, Budgets je Datei, Tests, A/B-Bau | nach U, vor 22 | `v0.40.0` | 5–6 |
| ZS2 | Konrad sieht die Seite auf Pages | nach B | | |
| E1–E5 | Amt (E1), Politikfeld (E2, nach 19), Stelle und Grenzstraße aus 16 (E3, nach dessen Stufe 2), Rhein und Autobahnen (E4), Regler über die Perioden (E5) | nach Antworten | je eigene | je 2–3 |

Die geplanten Versionen ab 22 (`bedarf.html`) rücken um zwei nach. **Warum diese Folge**: alle drei
laufenden Branches ändern `report/build.py`, 14 zusätzlich `report.html.j2` und `frame/script.js.j2`
(Dialog-Haken), 11/12 `tests/golden/test_published_page.py`, 17 `tests/golden/test_pipeline.py` und
`tests/unit/__snapshots__/test_cli.ambr`; ein Umzug davor erzeugte in jedem einen Konflikt. Der
Prototyp braucht nichts davon. B vor 22, damit `bedarf.html` gleich im neuen Linkblock erscheint.

**Aufwand, geschätzt.** P, U und B zusammen 9 bis 12 Agentenläufe (je Bau, zwei Reviews, eine
Nacharbeit), kein Netz, keine GPU. Konrad: zwei Haltepunkte.

| Risiko | Gegenmittel |
|---|---|
| Umzug halb angewandt: 21 Testdateien (19 `.py`, 2 `.ambr`) lesen `index.html` oder `site_index` | eigener Merge U, A/B-Bau, ein Test „`details.html` trägt alle Abschnitte des Profils" |
| Seiten- und Budgettests kennen ein Budget für alle Seiten | `_over_budget` je Datei; `tests/golden/test_published_page.py` prüft beide Budgets |
| Neue Datei unter `data/` ohne Zeile in den Downloads | `karte.json` bekommt ihre Zeile (rund 0,3 KB auf `details.html`) |
| Golden Master | unberührt (CSV unter `tests/fixtures/mini/expected/`) |
| Punkte werden als „handelt von" gelesen | Satz aus § 4.4, Straßen über mehrere Bezirke im Dialog |
| Leistung auf dem Handy | Messung im Prototyp; Canvas als Rückfall |
| Datenschutz | kein Punkt feiner als Straße je Wahlbezirk; das Paket trägt keine Hausnummern |
| Pages-Laufzeit und Pakete | `karte.json` entsteht in Sekunden aus Polars; Paket rund 0,03 MiB je Stadt (heute 168,6 von 180) |

## 10. Fragen an Konrad (beantwortet am 2026-11-27: es gelten die Empfehlungen)

| Nr. | Frage | warum sie zählt | Empfehlung, Annahme ohne Antwort |
|---|---|---|---|
| S.1 | Grundkarte aus eigenen Daten (Wahlbezirke, Stadtbezirke, Stadtteilnamen) statt Kacheln? | Orientierung gegen Datenschutz, Netz und Fremdskript | ja; Rhein und Autobahnen als OSM-Auszug später (E4) |
| S.2 | Heißt „Ressort" zunächst „Gremium" (überall, Regel), mit dem Amt als E1 und dem Politikfeld als E2? Oder meinst du Dezernate? | Dezernate stehen nicht in den Daten; 73 % der Dokumente sind BV-Dokumente | ja, „Gremium" in B; Dezernate nur mit einem datierten Verteilungsplan |
| S.3 | Kurzfassung aus K1 bis K4, K5 wahlweise, nur Verfahren der Arbeit, Regeln und vorab festgelegter Test? | Neutralität und Beleg; jede weitere Aussage braucht einen Prüfsatz | ja, ohne K5 |
| S.4 | `karte.html` nach ZS2 entfernen (einzige Datei mit Fremdressourcen) oder als „Stadtplan" mit den Punkten weiterführen? | Doppelte Karte, IP-Übertragung an den Kachelserver | entfernen, wenn die Startkarte reicht; bis dahin unverändert |
| S.5 | Reicht die Weiterleitung alter Anker per Skript? Hast du Links mit Anker geteilt? | Pages kann nicht umleiten | ja; dazu der `<noscript>`-Satz und die Doku-Links |
| S.6 | Voreinstellung „letzte 12 Monate bis zum neuesten Dokument", auch in abgeschlossenen Perioden? | Was man beim Öffnen sieht | ja |
| S.7 | Sammeldokumente (mehr als 20 Orte) als Zeile unter der Karte statt als Punkte? | 276 Dokumente tragen 22 % der Punkte | ja |
| S.8 | Straßenpunkte aus den Hauskoordinaten NRW als Paket ins Repo (31 KB, dl-de/zero-2.0, ohne Hausnummern)? | Ohne sie lägen 2 745 Straßen auf der Mitte von Stimmbezirken | ja |
| S.9 | Ein Regler über alle Düsseldorfer Perioden (E5) gewünscht? | 2014 bis heute auf einer Karte; doppelte Datenmenge | später, nach ZS2 |
| S.10 | Ein Filter nach Urheber auf der Karte (Verwaltung, Fraktionen, Bürgerinnen und Bürger)? | Für die Ratsarbeit naheliegend; die Antragsteller aus 15 sind geprüft (119 von 119), aber ein Parteifilter auf der Startseite verlangt besondere Neutralität | nicht in B; später als E6 mit den Antragstellern aus 15 und dem Prüfsatz, für alle Fraktionen gleich |
