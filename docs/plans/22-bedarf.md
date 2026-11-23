# Vorhaben 22: Bedarf und Aufmerksamkeit

Stand 2026-11-23, Stufe 1 (Messen), Branch `feat/22-bedarf`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „22 Bedarf und
Aufmerksamkeit". Messskript: [22-bedarf-messung.py](22-bedarf-messung.py) (`uv run python -I
docs/plans/22-bedarf-messung.py [--teil …]`, rechnet jede Zahl dieses Dokuments nach). Die Fremddaten
liegen nicht im Repo, sondern unter `/media/konrad/xtraspace/georep/fremddaten/opendata/` mit README
(Quelle, Abrufdatum, Bytes, SHA-256, Lizenz wörtlich); das Skript prüft die Prüfsummen, bevor es liest.
**Urteil: bauen** (§ 5). Die Hypothesen in § 8 stehen in diesem Commit fest, **bevor** der Teil
`hypothesen` des Skripts zum ersten Mal lief; ihr Ergebnis kommt im nächsten Commit (§ 3.4).

Die drei Zahlen, auf die es ankommt:

1. **Vier Bedarfsquellen mit freier Lizenz und passender Raumeinheit** für Düsseldorf: Quartiersatlas
   2024 (171 Sozialräume, dl-de/by-2-0, schon im Repo), Unfallatlas (Punkte, dl-de/by-2-0), Zensus 2022
   (100-m-Gitter mit Einwohnern und Nettokaltmiete, dl-de/by-2-0), Schulsozialindex NRW (Grundschulen
   als Punkte, dl-de/by-2-0); dazu Straßenverkehrslärm 2018 je Gebäude (dl-de/zero-2-0, über die
   Hauskoordinaten NRW zu 96,3 % verortet). Das Kriterium verlangt zwei. Drei der vier sind
   bundes- oder landesweit und tragen auch Mönchengladbach.
2. **11 501 Unfälle mit Personenschaden** in der Hauptperiode (2020-09 bis 2025-09), 4 außerhalb aller
   Stimmbezirke; **28,4 %** liegen näher als 20 m an einer Wahlbezirksgrenze, weil Grenzen auf
   Straßenmitten laufen. Die Messung teilt sie darum zu gleichen Teilen auf die Wahlbezirke im Band;
   die Rangfolge der Wahlbezirke ändert das kaum (Spearman 0,980 gegen die scharfe Zuordnung).
3. **Die Umrechnung trägt**: Einwohner je Wahlbezirk aus dem Zensus-Gitter (Punkt in Fläche) und aus
   dem Quartiersatlas über den vorhandenen Crosswalk korrelieren mit r = 0,947, Median der Abweichung
   5,3 %, größte 11,4 % (Wahlbezirk 4); die Summen unterscheiden sich um 5,1 % (Melderegister 2021
   gegen Zensus 2022).

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

**Frage.** Folgt die Aufmerksamkeit der Ratsdokumente dem Bedarf in den Wahlbezirken? Werden
Wahlbezirke mit vielen Verkehrsunfällen öfter in Verkehrsdokumenten genannt, Wahlbezirke mit vielen
Kindern öfter in Dokumenten der Jugendhilfe und der Schule, und Wahlbezirke mit hohem sozialem
Handlungsbedarf überhaupt öfter — oder seltener?

**Literatur.** Elsässer, Hense und Schäfer (2021)* finden für Deutschland, dass politische
Entscheidungen den Präferenzen der Wohlhabenden eher folgen als denen der Ärmeren („ungleiche
Responsivität"). Dieses Vorhaben misst nicht Präferenzen und Entscheidungen, sondern **Bedarf und
Nennung**: eine schwächere, aber beobachtbare Größe auf der Ebene, die die Seite schon hat. Der Befund
von Option 03 macht die Frage dringend: der soziale Handlungsbedarf erklärt die Wahlbeteiligung fast
vollständig (Modell B, R² 0,886, standardisierter Koeffizient −0,96; [../statistik.md](../statistik.md),
§ 5). Wenn Wahlbezirke mit hohem Bedarf weniger wählen *und* weniger genannt würden, wäre das die
kommunale Form der ungleichen Responsivität; wenn sie mehr genannt werden, spräche das dagegen. Zur
Deutung jeder Zahl hier gehört der ökologische Fehlschluss (Robinson 1950*): ein Zusammenhang über 41
Wahlbezirke sagt nichts über die Menschen in ihnen.

**Ratsarbeit.** Ein Ratsmitglied fragt „Wo ist viel Bedarf und wenig Aufmerksamkeit?" — heute ohne
Antwort auf der Seite. Eine Unterseite `bedarf.html` kann je Wahlbezirk Bedarf und Nennung
nebeneinander stellen, mit Quelle, Stand und Unsicherheit; sie ersetzt keine Bedarfsplanung der
Verwaltung, sie zeigt, wo die Dokumentlage und die amtlichen Zahlen auseinanderlaufen.

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

Gerechnet auf dem Lauf vom 2026-11-23 (`georep bootstrap && georep run` im Worktree, Profil
`duesseldorf`, 20 Schritte, Exit 0). Fremddaten geladen am 2026-11-23 von der Quelle, je Quelle ein
Unterordner unter `fremddaten/opendata/` (README dort; 16 Dateien, 201 MB).

### 2.1 Bestand für Düsseldorf

Gesucht im Open-Data-Portal der Stadt (DKAN-API `package_list`: 383 Datensätze, davon 187 mit einem
Bedarfswort im Namen; `package_show` für 38 Kandidaten), bei open.nrw (CKAN-API), bei Destatis und dem
Schulministerium NRW. „Frei" heißt hier: Datenlizenz Deutschland (Zero oder Namensnennung) oder
CC BY; „passend" heißt: Punkt, Gitter, Gebäude oder eine Gliederung feiner als die 41 Wahlbezirke mit
Geometrie.

| Quelle | Inhalt | Raumeinheit | Lizenz | Stand | Zeitreihe | geladen | passt |
|---|---|---|---|---|---|---|---|
| **Quartiersatlas 2024** (Stadt, Amt für Statistik und Wahlen) | sozialer Handlungsbedarf (Index), SGB II, Arbeitslose, Mindestsicherung, Alter, Fluktuation, Wohnen; 54 Spalten | 171 Sozialräume (Zuschnitt 2021), GeoJSON | dl-de/by-2-0 | 31.12.2021 | nein (eine Ausgabe) | schon in `context/` | **ja** |
| **Unfallatlas** (Statistische Ämter des Bundes und der Länder) | Unfälle mit Personenschaden: Jahr, Monat, Stunde, Kategorie (getötet, schwer, leicht), Art, Typ, Beteiligung Rad, Fuß, Pkw, Krad, Güter | Punkt auf der Straßenachse (EPSG:25832) | dl-de/by-2-0 | 2025 (veröffentlicht 2026-07) | jährlich, NRW ab 2019 | 2020–2025, 6 × 12,6 MB | **ja** |
| **Zensus 2022, Gitter** (Destatis) | Einwohner; durchschnittliche Nettokaltmiete je m² | 100-m-Gitter (EPSG:3035) | dl-de/by-2-0 | 15.05.2022 | nein (2011 mit anderen Merkmalen) | 18,5 + 9,4 MB | **ja** |
| **Schulsozialindex NRW** (MSB) mit den **amtlichen Schuldaten** | Sozialindexstufe 1–9 je Schule | Schule, Punkt über die Schulnummer | dl-de/by-2-0 | Schuljahr 2025/26 | jährlich seit 2021 | 0,3 + 1,8 MB | **ja** (88 Grundschulen, 87 mit Stufe) |
| **Straßenverkehrslärm** (Stadt) | Pegel Tag und Nacht je Gebäude, Wohngebäude ja/nein | Gebäude (Adresse, **ohne** Koordinate) | dl-de/zero-2-0 | 2018 | nein (EU-Kartierung alle 5 Jahre, Runde 2022 nicht im Portal) | 3,4 MB | ja, mit den Hauskoordinaten |
| **Gebäudereferenzen NRW** (Geobasis NRW) | Hauskoordinaten je Straßenschlüssel und Hausnummer | Punkt | dl-de/zero-2-0 | 2026-10-01 | aktuell, historisch ab 2016 | 90 MB | Hilfsdatei (Adresse → Punkt) |
| Kitas (Stadt) | Name, Träger, Adresse, Koordinate; **keine Platzzahl** | Punkt | dl-de/zero-2-0 | 2024-07 | nein | 58 KB | Angebot, kein Bedarf |
| Schulstandorte, Grundschulen (Stadt) | Standorte | Punkt | dl-de/zero-2-0 | 2020/2024 | nein | – | Angebot, kein Bedarf |
| Sozialraum-Datensätze 2016 (Arbeitslose, SGB II, SGB XII, Schuleingangsuntersuchung, Wohnen, Haushalte) | je Thema eine CSV | Sozialräume, Zuschnitt 2017 (Grenzen 30.06.2017 als GeoJSON vorhanden) | am 2026-11-23 dl-de/zero-2-0 (Option 03 las am 2026-10-11 „Andere geschlossene Lizenz") | 2016 | nein | – | veraltet; die Schuleingangsuntersuchung wäre die einzige Gesundheitsangabe |
| Bevölkerung in den Stadtteilen | Einwohner | 50 Stadtteile | dl-de/zero-2-0 | 2012–2025 | **jährlich** | – | als Nenner einer Zeitreihe |
| Bevölkerungswanderung in den Sozialräumen 2024 | Zu- und Fortzüge | Sozialräume | dl-de/by-2-0 | 2024 | nein | – | Fluktuation neuer als im Quartiersatlas |
| Belastungskarten Hitze | Bioklima Tag/Nacht, Referenz und Zukunft (Modell) | Raster als Polygone, 64 MB je GeoJSON | dl-de/by-2-0 | Modell 2018 | nein | – | möglich, groß; nicht gemessen |
| Verkehrszähldaten 2024 | DTV Kfz, Lkw, Rad, Bus je Zählstelle | Punkt (WFS) | dl-de/zero-2-0 | 2024 | jährlich (2019, 2024 im Portal) | – | Belastung, kein Bedarf |
| Polizeiliche Kriminalstatistik 2020 | Delikte | 3 Polizeiinspektionen | dl-de/zero-2-0 | 2020 | nein | – | **nein**, zu grob |
| Wohnungsmarkt, Wohnungsangebot | Angebotsmieten | Stadt | dl-de/zero-2-0 | 2025 | jährlich | – | **nein**, keine Raumeinheit |
| Mietspiegel | – | – | – | – | – | – | **gibt es nicht** als Datensatz im Portal; ersetzt durch die Zensus-Miete |
| Mängelmelder | – | – | – | – | – | – | **gibt es nicht** offen für Düsseldorf (keiner der 383 Datensätze; offen sind etwa Bonn, Münster, Dormagen) |
| Statistikportal `statistik.duesseldorf.de` | Quartiersatlas interaktiv | – | – | – | – | – | **nein**, kein Export (Option 03, § 3.6) |

**Mönchengladbach, kurz.** Das Portal `opendata.moenchengladbach.de` (Opendatasoft, 27 Datensätze)
hat kein Sozialmonitoring: Stadtteildemografie 2020–2025 (44 Stadtteile, Einwohner und
Ausländeranteil, CC BY-SA 4.0) und Bevölkerung nach Alter je Stadtteil (**CC BY-NC 4.0**, also nicht
frei im Sinn dieses Plans). open.nrw kennt für Mönchengladbach nur Kreiszahlen der Landesdatenbank und
eine polizeiliche Verkehrsunfallstatistik 2023 für die ganze Stadt. Es tragen aber die drei
überregionalen Quellen: Unfallatlas (812, 792, 838, 920, 901 und 1 038 Unfälle mit Personenschaden
2020 bis 2025, Gemeinde 05 1 16 000), Zensus-Gitter und Schulsozialindex. Für Mönchengladbach erfüllt
das Kriterium also dieselbe Kombination ohne den Quartiersatlas. Die Klassen „Verkehr" und „Jugend und
Schule" gibt es dort nicht: der Ausschussklassifikator läuft nur, wo Drucksachennummern ein
Ausschusskürzel tragen (§ 9, Frage 22.6).

### 2.2 Eigene Eingaben aus dem Lauf

- `interim/stimmbezirke.geojson`: 306 Stimmbezirke in 41 Wahlbezirken, 217,4 km², EPSG:4647
  (gelesen mit `georep.geo.read_canonical_precincts` in EPSG:25832).
- `processed/wahlbezirke_auswertung.parquet`: `wahlkreis_id`, `suchbegriffe`, `paper_ids`,
  `anzahl_treffer`, `Wahlberechtigte_insgesamt`, `wahlbeteiligung`, `trefferquote`.
- `processed/papers_ausschuss.parquet`: `id`, `ausschuss`, `wahrscheinlichkeit`; 19 033 Dokumente mit
  Text, davon `OVA` (Ordnungs- und Verkehrsausschuss) 1 827, `JHA` oder `SCHUA` (Jugendhilfe-,
  Schulausschuss) 1 162, Restklasse (leer, unter `classify.min_probability` = 0,4) 11 861.
- `processed/wahlbezirke_kontext.parquet`: `hb_score`, `anteil_u18`, `anteil_65plus`,
  `mindestsicherung`, `fluktuation` je Wahlbezirk (Option 03, Crosswalk über Flächenanteile und
  Wahlberechtigte); `processed/wahlbezirke_crosswalk.parquet` (465 Paare Wahlbezirk–Sozialraum);
  `external/quartiersatlas_2024.csv` für `Bevoelkerung_abs` und `u6_abs`.

### 2.3 Ablage der Auszüge

Das Skript legt beim ersten Lauf die Düsseldorfer Auszüge unter
`/media/konrad/xtraspace/georep/messdaten/22-bedarf/` ab und liest danach nur sie:
`unfaelle_duesseldorf.parquet` (13 507 Unfälle 2020–2025, 97 KB zstd, als CSV 435 KB),
`zensus2022_duesseldorf.parquet` (14 400 Zellen im Rechteck um die Stadt, 70 KB), `gebref_duesseldorf.parquet`
(84 193 Hausnummern, 821 KB), `unfaelle_moenchengladbach.parquet`. Das sind die Größenordnungen, mit
denen Stufe 2 ein Paket unter `context/` rechnen muss (§ 6).

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

Alle Zahlen vom 2026-11-23. Keine Stichprobe: jede Quelle wird ganz gerechnet. Seed 22 nur für
Permutationen und Bootstrap in § 3.4. Laufzeit des Teils `bedarf` 5,9 s mit vorhandenen Auszügen,
rund 60 s beim ersten Lauf (die bundesweiten Archive), `nice -n 10`, Polars auf vier Threads.

### 3.1 Umrechnung je Quelle auf die 41 Wahlbezirke

| Quelle | Weg | Abdeckung | Unsicherheit |
|---|---|---|---|
| Quartiersatlas | vorhandener Crosswalk (`georep.crosswalk.area_shares` + `district_weights`), gewichtetes Mittel je Wahlbezirk | 0,9999 der Stimmbezirksfläche (Option 03) | Gleichverteilung der Wahlberechtigten im Stimmbezirk angenommen; Gegenprobe Einwohner: r = 0,947 gegen den Zensus, Median 5,3 %, größte Abweichung 11,4 % (Wahlbezirk 4). Stand 2021 gegen Wahl 2025 |
| Unfallatlas | Punkt in Fläche (Stimmbezirk → Wahlbezirk), **unscharf**: jeder Unfall zu gleichen Teilen an alle Wahlbezirke, deren Stimmbezirke näher als 20 m liegen | 11 499 von 11 501 im Band, 4 außerhalb aller Stimmbezirke (scharf) | 3 268 Unfälle (28,4 %) näher als 20 m an einer Grenze, 3 170 geteilt; je Wahlbezirk Median 28,6 %, höchstens 64,9 % am Rand. Scharf gegen unscharf: Spearman 0,980 |
| Zensus 2022 | Mittelpunkt der 100-m-Zelle in Fläche | 7 658 Zellen mit Mittelpunkt in einem Stimmbezirk, 611 134 Einwohner (gegen die amtliche Gemeindezahl des Zensus nicht geprüft; Zellen über die Stadtgrenze fallen der Seite ihres Mittelpunkts zu) | Zellen auf einer Grenze fallen ganz einer Seite zu (100 m gegen Wahlbezirke von 12 039 bis 18 317 Einwohnern); keine negativen Werte (Geheimhaltung) in der Stadt |
| Zensus-Miete | Mittel der Zellen mit Wert, gewogen mit deren Einwohnern | 6 220 Zellen mit Wert; je Wahlbezirk 80,8 % bis 100 % der Einwohner in Zellen mit Wert (Median 96,5 %) | 11 Zellen mit Zeichen `KLAMMERN` (Wert unsicher), mitgerechnet; Gewicht Einwohner statt Wohnungen (die Wohnungszahl liegt in einer weiteren Datei) |
| Lärm 2018 | Straßenschlüssel und Hausnummer mit Zusatz → Gebäudereferenz NRW → Punkt in Fläche; Anteil der Wohngebäude über 65 dB(A) Tag bzw. 55 dB(A) Nacht | 75 930 von 78 832 Gebäuden (96,3 %), Wohngebäude 98,8 %; keins außerhalb | Gebäude statt Einwohner (ein Hochhaus zählt wie ein Einfamilienhaus); Stand 2018; die Pegelart (L_DEN oder L_Day) nennt die Datei nicht, Wertebereich Tag 34–78, Nacht 26–73 |
| Schulsozialindex | Schulnummer → Koordinate der amtlichen Schuldaten → Punkt in Fläche; Mittel der Grundschulen je Wahlbezirk | 88 Grundschulen, 87 mit Stufe, jeder Wahlbezirk hat 1 bis 4 | eine Schule ist kein Gebiet: das Einzugsgebiet reicht über Wahlbezirksgrenzen; bei einer Schule je Wahlbezirk ist das Mittel eine Einzelzahl |
| Kitas | Punkt in Fläche | 368 mit Koordinate (1 unlesbar: „512.209.216.102.838"), 1 außerhalb | keine Platzzahl; Angebot, nicht Bedarf |

Das Band von 20 m ist eine Entscheidung dieser Messung: der Unfallatlas legt Unfälle auf die
Straßenachse (Spalten `LINREFX`, `LINREFY`), und Wahlbezirksgrenzen laufen oft auf Straßenmitten.
Halbe Straßenbreite plus Digitalisierungsabstand der Stimmbezirke liegen bei Hauptstraßen um 10 bis
20 m; ein breiteres Band verschmiert, ein schmaleres teilt zufällig.

### 3.2 Bedarf je Wahlbezirk (Spannweiten, n = 41)

| Größe | min | Median | max |
|---|---|---|---|
| Einwohner (Zensus 2022) | 12 039 | 14 664 | 18 317 |
| Unfälle mit Personenschaden 2020-09 bis 2025-09 (unscharf) | 143,2 | 259,0 | 935,3 |
| je 1 000 Einwohner | 8,9 | 17,8 | 58,4 |
| je km² | 7,3 | 66,6 | 414,2 |
| davon mit Rad- oder Fußbeteiligung | 57,5 | 124,8 | 510,0 |
| Anteil Wohngebäude ≥ 65 dB(A) Tag / ≥ 55 dB(A) Nacht | 0,021 / 0,043 | 0,164 / 0,231 | 0,469 / 0,551 |
| Nettokaltmiete je m² (Zensus 2022) | 7,49 € | 9,21 € | 11,36 € |
| Sozialer Handlungsbedarf (Score 1–5) | 1,34 | 2,98 | 4,46 |
| Anteil unter 18 Jahren (%) | 10,8 | 16,2 | 21,4 |
| Mindestsicherungsquote (%) | 1,8 | 9,0 | 21,6 |
| Schulsozialindex der Grundschulen (Mittel, 1–9) | 1,0 | 4,5 | 9,0 |
| Kitas / je 1 000 Kinder unter 6 | 2 / 2,7 | 9 / 9,9 | 17 / 21,9 |

In der ganzen Stadt: 51 Unfälle mit Getöteten, 1 527 mit Schwerverletzten, 9 923 mit Leichtverletzten
im Zeitraum; je ganzem Jahr 2 224 (2020), 2 019, 2 087, 2 427, 2 343 und 2 407 (2025).

### 3.3 Aufmerksamkeit je Wahlbezirk

Ein Dokument „nennt" einen Wahlbezirk, wenn es mindestens einen Treffer in dessen Wörterbuch hat
(`paper_ids`, wie die Trefferquote der Seite). Die Klasse kommt aus dem vorhandenen
Ausschussklassifikator (Option 05; Genauigkeit 0,941, Makro-F1 0,878 in der Kreuzvalidierung **auf
Ausschussdokumenten**, [../statistik.md](../statistik.md), § 10).

| Größe | min | Median | max |
|---|---|---|---|
| Dokumente mit Treffer | 318 | 674 | 1 786 |
| Begriffe im Wörterbuch | 77 | 147 | 751 |
| davon Klasse Verkehr (`OVA`) | 45 | 152 | 358 |
| Anteil Verkehr | 0,118 | 0,207 | 0,303 |
| davon Klasse Jugend und Schule (`JHA`, `SCHUA`) | 21 | 45 | 87 |
| Anteil Jugend und Schule | 0,026 | 0,060 | 0,134 |

Jedes Dokument mit Treffer hat Text, also eine Klasse oder die Restklasse; der Nenner der Anteile
ist darum die Zahl der Dokumente mit Treffer.

### 3.4 Ergebnis der vorab festgelegten Hypothesen

Noch nicht gerechnet. Der Teil `hypothesen` des Skripts läuft erst nach dem Commit, der § 8 festlegt.

### 3.5 Explorativ

Noch nicht gerechnet (nach § 3.4).

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

Eine Kodierung braucht das Vorhaben nicht: die Bedarfsdaten sind amtlich, die Umrechnung ist
deterministisch. Geprüft wird nach § 2.6 des Meta-Plans in der Reihenfolge deterministischer
Prüfungen:

- **Prüfsummen**: jede Fremddatei gegen Größe und SHA-256 aus dem Ladeprotokoll (Teil `bestand`).
- **Summentreue**: Zensus-Einwohner der Stadt 611 134 in 7 658 Zellen; Unfälle 11 501 im Zeitraum, 2
  ohne Wahlbezirk im Band.
- **Zwei Wege zur selben Größe**: Einwohner je Wahlbezirk aus Gitter und aus Crosswalk (r = 0,947);
  Unfälle scharf und unscharf (Spearman 0,980). Der Vergleich des städtischen Handlungsbedarfs mit dem
  Schulsozialindex des Landes (zwei unabhängige Bedarfsmaße) steht in § 3.5.
- **Verortung**: Lärm 96,3 % der Gebäude über Straßenschlüssel und Hausnummer.

Nicht validiert ist die **Klasse der Dokumente außerhalb der Ausschüsse**: 1 084 der 1 827
Verkehrsdokumente haben keine Ausschussberatung (vor allem Bezirksvertretungen), und auf ihnen ist der
Klassifikator nie geprüft worden. Für Stufe 3 ist das eine Lücke, die die Seite nennen muss; eine
Kodierung von 100 Bezirksvertretungsdokumenten der Klasse `OVA` würde sie schließen (§ 9, Frage 22.3).

## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

**Kriterium** (Briefing, unverändert): mindestens zwei Quellen mit passender Raumeinheit und freier
Lizenz.

**Erfüllt, mit vier Quellen** (§ 2.1): Quartiersatlas (Sozialräume, dl-de/by-2-0), Unfallatlas
(Punkte, dl-de/by-2-0), Zensus 2022 (100-m-Gitter, dl-de/by-2-0), Schulsozialindex (Schulen als
Punkte, dl-de/by-2-0); als fünfte mit einer Hilfsdatei der Lärm (Gebäude, dl-de/zero-2-0). Ohne den
Quartiersatlas, der nur Düsseldorf trägt, sind es für beide Städte drei. Unsicher ist nicht die
Lizenz und nicht die Raumeinheit, sondern **der Stand**: Lärm 2018, Quartiersatlas 2021, Zensus 2022
gegen Dokumente von 2020 bis 2025; nur die Unfälle liegen genau im Zeitraum. Und die Zuordnung an
Grenzen: 28,4 % der Unfälle liegen in einem Band, in dem die Seite der Straße Zufall ist.

**Urteil: bauen**, mit drei Einschränkungen am Briefing:

1. **Die Erweiterung von `prep/context.py` braucht einen zweiten Weg in den Crosswalk**: Punkte (und
   Gitterzellen als Punkte) statt Flächen, mit dem unscharfen Band. Er gehört nach
   `georep.crosswalk` (§ 6), weil Vorhaben 16 und 21 dieselbe Zuordnung brauchen.
2. **Mieten nur aus dem Zensus 2022**, Mängelmeldungen gar nicht: es gibt sie nicht offen.
3. **Mönchengladbach bekommt Bedarf ohne Klassen**: Unfälle, Einwohner, Miete und Schulsozialindex ja,
   die Anteile „Verkehr" und „Jugend und Schule" nicht, solange es dort keinen
   Ausschussklassifikator gibt.

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

**Beitrag** `22-bedarf` in `georep.enrich.CONTRIBUTIONS` (Punkt 69) mit zwei Schritten und zwei
Tabellen; Ebene 0, einziger Eigentümer von `prep/context.py`.

**Code.**

- `georep/crosswalk.py`: neu `point_shares(points, precincts, *, band_m) -> pl.DataFrame` (Spalten
  `punkt`, `wahlkreis_id`, `anteil`; je Punkt summieren die Anteile zu 1, Punkte ohne Wahlbezirk im
  Band fehlen) und `cells_to_districts(cells, precincts)` (Mittelpunkt in Fläche, scharf). Verträge an
  der Batch-Grenze: Anteile in (0, 1], Summe je Punkt 1, sortiert nach `punkt, wahlkreis_id`;
  Bandbreite ≥ 0 (0 = scharf). Nicht `PrecinctIndex.locate` je Punkt: `STRtree.query` mit
  `predicate="dwithin"` über das ganze Feld (13 507 Punkte in Millisekunden).
- `georep/prep/context.py`: neu `read_accidents(paths, ags) -> pl.DataFrame` (die Jahrgänge heißen
  verschieden: `csv/…_LinRef.csv`, `…/Unfallorte_2021_LinRef.txt`, `…_LR_BasisDLM.csv`; Spalten mit
  BOM; Dezimalkomma), `read_grid(path, bbox)` (Zensus, EPSG:3035), `read_school_index(schools,
  index, ags, schulform)` (Codepage 850, „ohne" als null), `need_table(...)` (je Wahlbezirk eine
  Zeile). Schema-Version `NEED_SCHEMA_VERSION = 1` als Modulkonstante.
- `georep/enrich/need.py` (neu): `CONTRIBUTION = Contribution("22-bedarf", steps=…, tables=…)`;
  Schritte `need_data` (Netz: lädt die Archive in den Cache und schreibt die Stadtauszüge nach
  `data_root/external/bedarf/`) und `need` (offline: `processed/wahlbezirke_bedarf.parquet`,
  `processed/bedarf_hypothesen.parquet`).

**Ausgaben.**

- `wahlbezirke_bedarf.parquet`, eine Zeile je `wahlkreis_id` (Int64), sortiert: `einwohner_zensus`
  (Int64), `unfaelle`, `unfaelle_schwer`, `unfaelle_rad_fuss`, `unfaelle_scharf`, `unfaelle_am_rand`,
  `unfaelle_je_1000`, `miete_qm`, `miete_abdeckung`, `sozialindex_gs`, `grundschulen`,
  `anteil_laerm_tag`, `anteil_laerm_nacht` (nur mit Lärmpaket), `dok`, `dok_verkehr`, `dok_jugend`,
  `anteil_verkehr`, `anteil_jugend`, `dok_je_1000_ew` (Float64).
- `bedarf_hypothesen.parquet`: eine Zeile je Hypothese aus § 8 (`name`, `bedarf`, `aufmerksamkeit`,
  `rho`, `ci_lo`, `ci_hi`, `p`, `p_holm`, `urteil`, `n`, `seed`); dazu die explorativen Paare in einer
  zweiten Tabelle mit `explorativ = true`. Die Permutationen mit festem Seed machen die Datei
  byteidentisch über Läufe.

**Settings** (Anhängeregel, `docs/plans/00-synergien.md`, § 2): neuer Block `[context.need]` in
`defaults.toml` mit `band_m = 20.0` (Kommentar: Straßenachse, § 3.1), `period_months` aus der Periode des
Profils, `permutations = 10000`, `bootstrap = 2000`, `seed = 22`, `[context.need.classes]` mit
`traffic = []`, `youth = []`; im Profil `duesseldorf`: `ags = "05111000"`, `traffic = ["OVA"]`,
`youth = ["JHA", "SCHUA"]`, die Quell-URLs mit Lizenz wie `[context.files]`. Mönchengladbach: `ags =
"05116000"`, Klassen leer (die Anteile fehlen dann, der Rest rechnet).

**Paket.** Nach dem Muster von `context/` (Punkt 26): `context/bedarf/` mit
`unfaelle_<stadt>_2020_2025.csv` (rund 435 KB für Düsseldorf, 7 Spalten), `zensus2022_<stadt>.csv`
(nur Zellen mit Mittelpunkt in der Stadt, rund 430 KB), `schulen_<stadt>.csv` (Schulnummer, Schulform,
Koordinate, Stufe; rund 10 KB), README mit Quelle, Lizenz, Namensnennung, SHA-256. Die Gebäudereferenzen
(90 MB) und der Lärm kommen **nicht** ins Repo; der Lärm kommt höchstens als Aggregat je Stimmbezirk
(306 Zeilen), erzeugt mit `georep pack --need` (Frage 22.2). `bootstrap` kopiert `context/bedarf/` nach
`external/bedarf/`; `need_data` holt frisch.

**Tests** (roter Test zuerst, Beleg im Commit-Body):

- `tests/unit/test_crosswalk_points.py`: zwei Quadrate mit gemeinsamer Kante, ein Punkt auf der Kante
  → 0,5/0,5; ein Punkt innen → 1,0; ein Punkt außen → fehlt. hypothesis in `tests/property/`: für
  beliebige Punkte summieren die Anteile je Punkt zu 1, und die Summe über alle Wahlbezirke ist die
  Zahl der Punkte im Band; Band 0 ist die scharfe Zuordnung.
- `tests/unit/test_context_need.py`: die drei Namensformen der Unfallatlas-Archive als winzige
  Fixture-Zips (je drei Zeilen, eine davon in der Zielgemeinde), BOM im Kopf, Dezimalkomma;
  Codepage 850 und „ohne" im Sozialindex; die Zensus-Zelle auf der Grenze.
- `tests/unit/test_need_hypotheses.py`: Permutationstest gegen `scipy.stats.spearmanr` bei großem n
  (p stimmen auf zwei Stellen), Holm gegen eine Handrechnung, gleicher Seed → gleiche Datei.
- Mini-Fixture: drei Wahlbezirke mit zehn erfundenen Unfällen und zwölf Zellen unter
  `tests/fixtures/mini/context/bedarf/`; `expected/` bleibt unberührt.
- Kein Netz in Tests; `need_data` ist ein Netzschritt wie `context_data`.

**Berührte Dateien**: `crosswalk.py`, `prep/context.py`, `enrich/need.py` (neu), `enrich/__init__.py`
(eine Zeile), `defaults.toml`, `profiles/duesseldorf.toml`, `profiles/moenchengladbach.toml`,
`settings.py` (Modell `NeedSettings` am Ende von `ContextSettings`), `layout.py` (zwei Pfade),
`bootstrap.py` (Kopierliste), `context/bedarf/` (neu), `docs/architecture.md`, ein Entscheidungspunkt
ohne Nummer. Nicht berührt: `report/model.py`, `pipeline.build_steps` (Register).

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

**Unterseite `bedarf.html`** (`report.pages.Page`, Name `bedarf`), je Profil mit Bedarfsdaten:

1. *Quellen und Stand*: eine Tabelle wie „Abgeleitete Daten" (Quelle, Lizenz, Namensnennung, Stand,
   Raumeinheit, Umrechnung, Abdeckung). Namensnennungen: „Statistische Ämter des Bundes und der Länder,
   Unfallatlas, dl-de/by-2-0", „Statistisches Bundesamt (Destatis), Zensus 2022, dl-de/by-2-0",
   „Ministerium für Schule und Bildung NRW, Schulsozialindex, dl-de/by-2-0", Quartiersatlas wie bisher.
2. *Bedarf je Wahlbezirk*: drei kleine Karten (Unfälle je 1 000 Einwohner, sozialer Handlungsbedarf,
   Anteil unter 18), daneben dieselbe Tabelle sortierbar; der Satz zum Randband.
3. *Bedarf und Nennung*: die drei vorab festgelegten Tests als Tabelle (ρ mit Intervall, p, Holm, Urteil,
   „vorab festgelegt am 2026-11-23, Commit …") und je ein Streudiagramm; darunter die explorativen
   Paare unter dieser Überschrift.
4. *Was das nicht sagt*: ökologischer Fehlschluss, n = 41 (nur |ρ| ≳ 0,4 ist mit 80 % Power
   erkennbar), Stand der Daten, Klassifikator auf Bezirksvertretungsdokumenten ungeprüft, keine
   Kausalität, keine Rangliste „vernachlässigter" Bezirke.

**Was die Seite nicht zeigt**: eine Rangfolge der Wahlbezirke nach „Bedarf minus Aufmerksamkeit" als
Urteil (zwei Größen mit verschiedenen Einheiten, deren Differenz eine Gewichtung ist, die niemand
festgelegt hat); Aussagen über Personen oder Gruppen; eine Zeitreihe (die Bedarfsdaten sind Momente,
nur die Unfälle hätten Monate); etwas je Partei.

**Größe** geschätzt 150 bis 250 KB: drei Karten aus den vereinfachten Wahlbezirksflächen der Hauptseite
(je rund 40 KB), drei Streudiagramme (je rund 10 KB), Tabellen. **Tabellen im Register**:
`wahlbezirke_bedarf`, `bedarf_hypothesen` als Parquet und CSV (je unter 20 KB). **Validierung auf der
Seite**: die Gegenproben aus § 4 mit Zahl, und für die Klassen: „Klassifikator geprüft an
Ausschussdokumenten (Genauigkeit 0,941), nicht an Dokumenten der Bezirksvertretungen".

## 8. Vorab festgelegte Hypothesen (nur Analysen: Hypothese, Maß, Test, Schwelle)

Festgelegt am 2026-11-23 in diesem Commit, **bevor** irgendeine Größe der Bedarfsseite gegen eine der
Aufmerksamkeitsseite gerechnet wurde. Angesehen waren davor nur die Randverteilungen beider Seiten
(§ 3.2, § 3.3). Alles, was nicht hier steht, heißt „explorativ".

Für alle drei: Einheit ist der Wahlbezirk, n = 41, **alle 41** (keine Ausreißer ausgenommen). Maß
des Zusammenhangs ist **Spearmans ρ** (Ränge, weil die Verteilungen schief sind und n klein ist). p aus
einem **Permutationstest** mit 10 000 Permutationen, Seed 22, in der Reihenfolge H1, H2, H3 aus
einem Generator gezogen; dazu ein 95-%-Perzentil-Bootstrap-Intervall für ρ (2 000 Ziehungen, derselbe
Generator). **Schwelle**: α = 0,05 nach **Holm** über die drei Tests. Bei n = 41 erkennt ein
einseitiger Test mit 80 % Power nur |ρ| ≥ rund 0,39 (im ersten Holm-Schritt, α/3, rund 0,46);
kleinere Zusammenhänge kann diese Messung nicht ausschließen, und „nicht bestätigt" heißt darum
„nicht nachgewiesen", nicht „widerlegt".

| Nr. | Hypothese | Bedarf (x) | Aufmerksamkeit (y) | Test |
|---|---|---|---|---|
| H1 | Wo mehr Verkehrsunfälle mit Personenschaden je Einwohner geschehen, ist ein größerer Teil der Dokumente, die den Wahlbezirk nennen, ein Verkehrsdokument. | Unfälle mit Personenschaden (Kategorie 1–3) des Unfallatlas, Unfallmonat 2020-09 bis 2025-09, unscharf zugeordnet (Band 20 m, § 3.1), je 1 000 Einwohner des Zensus 2022 (`unfaelle_je_1000`) | Anteil der Dokumente der Klasse `OVA` an den Dokumenten mit Treffer im Wahlbezirk (`anteil_verkehr`) | einseitig, ρ > 0 |
| H2 | Wahlbezirke mit höherem sozialem Handlungsbedarf werden je Einwohner **häufiger** genannt (Responsivität) — oder **seltener** (ungleiche Responsivität). | `hb_score` des Quartiersatlas (wie Tabelle 6 der Seite) | Dokumente mit Treffer je 1 000 Einwohner des Zensus 2022 (`dok_je_1000_ew`) | **zweiseitig**; Deutung vorab: ρ > 0 und p_Holm < 0,05 → „Aufmerksamkeit folgt dem Bedarf"; ρ < 0 und p_Holm < 0,05 → „ungleiche Aufmerksamkeit"; sonst „kein Zusammenhang nachweisbar" |
| H3 | Wo der Anteil der unter 18-Jährigen höher ist, ist ein größerer Teil der Dokumente des Wahlbezirks ein Dokument der Jugendhilfe oder der Schule. | `anteil_u18` des Quartiersatlas | Anteil der Klassen `JHA` oder `SCHUA` an den Dokumenten mit Treffer (`anteil_jugend`) | einseitig, ρ > 0 |

**Warum Einwohner, nicht Wahlberechtigte** (H1, H2): Bedarf betrifft alle Einwohner. Die
Trefferquote der Seite teilt durch Wahlberechtigte; wo viele Einwohner ohne deutsche
Staatsangehörigkeit leben — und das sind oft Gebiete mit hohem Handlungsbedarf —, wäre die Quote
dadurch höher, ohne dass ein Dokument mehr den Bezirk nennt. Der Zensus 2022 liegt in der Mitte der
Periode.

**Warum Anteile** (H1, H3): die Zahl der Dokumente mit Treffer hängt an der Größe des Wörterbuchs
(r = 0,76, [../statistik.md](../statistik.md), § 3). Ein Anteil innerhalb des Wahlbezirks kürzt diese
Verzerrung heraus und fragt nur, *worüber* gesprochen wird, wenn der Bezirk vorkommt. H2 fragt
dagegen nach dem *Wie oft* und trägt die Verzerrung; darum die Robustheitsrechnung mit der Zahl der
Begriffe.

**Robustheit, vorab genannt, entscheidet nicht**: alle drei ohne die Wahlbezirke 1 und 10; H1 mit
scharfer Zuordnung (Punkt in Fläche), mit absoluten Unfällen und mit Unfällen je km²; H2 als partielle
Rangkorrelation bei festem log(Zahl der Begriffe) und mit der Trefferquote der Seite (je
Wahlberechtigtem). Weichen sie vom Haupttest ab, sagt die Seite das; das Urteil bleibt das des
Haupttests.

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 22.1 | Dürfen Auszüge aus Unfallatlas, Zensus-Gitter und Schuldaten unter `context/bedarf/` ins Repo (zusammen rund 0,9 MB, dl-de/by-2-0)? | Pages baut ohne Netz nur, was im Repo liegt | ja, nach dem Muster des Quartiersatlas (Punkt 26), mit Namensnennung auf der Seite |
| 22.2 | Kommt der Lärm 2018 in Stufe 2 mit (braucht die 90-MB-Gebäudereferenzen zum Verorten)? | eine zweite Verkehrsgröße, aber Stand 2018 und Gebäude statt Einwohner | nein in Stufe 2; nur explorativ hier; wenn ja, dann als Aggregat je Stimmbezirk aus `georep pack --need` |
| 22.3 | Soll die Klasse `OVA` an 100 Dokumenten der Bezirksvertretungen kodiert werden (F4, zwei Kodier-Agenten)? | H1 hängt an 1 084 Verkehrsdokumenten ohne Ausschussberatung, auf denen der Klassifikator ungeprüft ist | nein für Stufe 2; für Stufe 3 ja, wenn H1 auf die Seite soll |
| 22.4 | Gilt das Band von 20 m auch für andere Punkte (Kitas, Schulen, Orte aus Vorhaben 16)? | eine Schule an einer Grenzstraße liegt auch auf beiden Seiten | nein: das Band ist für Punkte auf Straßenachsen; Gebäude und Einrichtungen werden scharf zugeordnet |
| 22.5 | Soll die Seite die Hypothesen auch für die Periode 2014–2020 rechnen? | Unfallatlas NRW erst ab 2019, Quartiersatlas 2021, Zensus 2022 | nein: die Bedarfsdaten passen nur zur Hauptperiode und zur laufenden |
| 22.6 | Mönchengladbach ohne Klassen: reicht „Bedarf je Wahlbezirk" ohne die Anteile? | Stadtneutralität; dort gibt es keinen Ausschussklassifikator | ja; die Anteile fehlen sichtbar, mit Grund |
| 22.7 | Zensus-Miete gewogen mit Einwohnern statt Wohnungen? | das Gitter hat die Wohnungen in einer eigenen Datei | Einwohner reichen für eine Beschreibung; die Wohnungsdatei erst, wenn die Miete in einen Test geht |
| 22.8 | Räumliche Autokorrelation: benachbarte Wahlbezirke sind sich ähnlich, der Permutationstest nimmt Austauschbarkeit an | p-Werte zu klein | die Seite nennt es; Moran's I der Residuen als Prüfung in Stufe 2, kein anderes Verfahren |
| 22.9 | Die Fremddaten unter `fremddaten/opendata/` sind älter als die Auszüge im Repo, wenn eine Quelle neu veröffentlicht (Unfallatlas jährlich im Juli) | Stand der Seite | `need_data` holt neu, der Stamp trägt die SHA-256 der Archive |

## 10. Änderungen durch die Synergie (füllt der Supervisor)

—

---

Literatur, aus dem Gedächtnis (*), vor einem Zitat auf der Seite nachzuschlagen: Elsässer, Hense,
Schäfer (2021): Not just money: unequal responsiveness in egalitarian democracies. Journal of European
Public Policy. Robinson (1950): Ecological correlations and the behavior of individuals. American
Sociological Review 15 (3).
