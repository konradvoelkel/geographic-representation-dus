# Vorhaben 19: Politikfelder nach dem Comparative Agendas Project

Stand 2026-11-23, Stufe 1 (Messen), Branch `feat/19-politikfelder`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „19 Politikfelder nach
dem Comparative Agendas Project", dazu § 10, Frage 5 (Babel Machine nicht benutzen, aber nachbauen).
Messskript: [19-politikfelder-messung.py](19-politikfelder-messung.py); Trainingsskript (eigenes Venv
außerhalb des Pakets): [19-politikfelder-training.py](19-politikfelder-training.py). Codebuch,
Stichprobe und später die Labels: `validierung/19-politikfelder/`.

**Dieser Stand ist die Vorab-Festlegung** (§ 8): Kodierschema, Testmenge, die drei Wege, Maß,
Kriterium, Entscheidungs- und Rückfallregel, geschrieben und committet, bevor ein Verfahren auf einem
Ratsdokument gelaufen ist und bevor kodiert wird. Die Abschnitte 1 bis 7 und 9 folgen mit der Messung.

## 8. Vorab festgelegt (2026-11-23, vor jedem Lauf eines Verfahrens und vor der Kodierung)

### 8.1 Kodierschema

- **Die 21 Hauptthemen des CAP-Master-Codebuchs** (Version 1.1 vom 2022-08-09) mit ihren Nummern: 1
  Makroökonomie, 2 Bürgerrechte, 3 Gesundheit, 4 Landwirtschaft, 5 Arbeit, 6 Bildung, 7 Umwelt, 8
  Energie, 9 Migration, 10 Verkehr, 12 Recht und Kriminalität, 13 Soziales, 14 Wohnen und
  Stadtentwicklung, 15 Binnenwirtschaft, 16 Verteidigung, 17 Technik, 18 Außenhandel, 19
  Internationales, 20 Staat und Verwaltung, 21 Öffentliche Flächen und Wasser, 23 Kultur. Dazu **99
  „kein Politikfeld erkennbar"** als 22. Option. Unterthemen (vierstellig) kodiert niemand; ein
  Verfahren darf sie ausgeben, gemessen wird das Hauptthema.
- **Ein Thema je Dokument**, das vorherrschende (Grundregel 1 des deutschen CAP-Codebuchs v2.5: die
  Sache, nicht die Zielgruppe, nicht das Instrument). Geld folgt der Sache; der Ort entscheidet nichts.
- **Abbildung auf kommunale Themen**: je Option eine Definition mit dem, was in einer Stadt dazugehört,
  und den Grenzfällen, in `validierung/19-politikfelder/codebuch.toml` (Fassung 2026-11-23.1). Wo das
  deutsche Codebuch eine Sache ausdrücklich verortet, folgt die Abbildung ihm, weil die menschlich
  kodierten deutschen Daten von Weg 3 danach kodiert sind: Kitas und Kinder- und Jugendhilfe 13
  (1308), Vereine und Amateursport 13 (1305), Spielplätze und Kleingärten 14 (1401), öffentliche
  Bibliotheken 6 (607), Denkmalschutz und Parks 21 (2101), Tierschutz bei Haustieren 4,
  Barrierefreiheit als Zugang 2 (205). Was keines der Codebücher regelt, legt diese Fassung fest:
  Feuerwehr und Katastrophenschutz 15 (1523), Zivilschutz 16 (1615), Rettungsdienst 3 (322),
  Friedhöfe 21, Straßenbenennungen und Ehrungen 20, Verfügungsmittel nach ihrem Zweck.
- **Verwaltungsinterna sind ein Politikfeld, nicht „keins"**: Sitzungstermine, Geschäftsordnung, Wahl
  und Besetzung von Gremien, Beschlusskontrollen ohne vorherrschendes Thema, Personal und Organisation
  der Verwaltung, Wahlen, Sammlungen ohne vorherrschendes Feld sind 20 (Staat und Verwaltung), wie im
  CAP (2002, 2004, 2005, 2011, 2012). **99** nur, wenn der Ausschnitt keinen Gegenstand erkennen
  lässt (leer, unlesbar, nur Deckblatt); im Zweifel das Feld. 99 zählt im Maß als eigene Klasse.
- Zweite Frage `unsicher` (ja/nein, ohne Schlichtung) für die Auswertung der Grenzfälle.

### 8.2 Testmenge (F4) und Entwicklungsmengen

- **Testmenge**: 300 Dokumente der Hauptperiode (`duesseldorf`, 2020 bis 2025) mit Text, geschichtet
  nach Gremiumsart (Bezirksvertretung, Ausschuss, Rat, Beirat; `papers_gremien.parquet`) × Gruppe der
  Dokumentart (Beschlussvorlage, Informationsvorlage, Antrag, Anfrage, Eingabe), proportional,
  Seed 20261123, gezogen mit `georep validate sample` (F4) aus der Grundgesamtheit, die das Messskript
  schreibt. **Die 300 sind Testdaten**: kein Training, keine Silberlabels, kein Prompt- und kein
  Parameter-Tuning an ihnen. Jedes Verfahren läuft auf ihnen genau einmal, in der vorher eingefrorenen
  Fassung; ein zweiter Lauf nur nach einem technischen Fehler (Abbruch, Parserfehler), mit
  unveränderter Fassung und Vermerk.
- **Entwicklungsmenge Ratsdokumente**: 200 Dokumente derselben Grundgesamtheit ohne die 300, gleiche
  Schichtung, Seed 20261124, nur IDs im Repo (`validierung/19-politikfelder/entwicklung.csv`). An ihr
  darf das Prompt-Format (Antwortform, Parser, Länge) eingestellt werden; ihre Antworten sind
  Silberlabels für Weg 3b. Gold gibt es dort nicht, also kein Tuning auf eine Zahl.
- **Zweite Prüfung an menschlichen CAP-Daten** (§ 2.6, Stufe 3): 200 Titel der deutschen
  CAP-Anfragen 1976 bis 2005 (Seed 20261125, geschichtet nach Hauptthema, proportional), nicht im
  Training von Weg 3; dazu die zurückgehaltenen 10 % der deutschen CAP-Daten für Weg 3. Andere
  Textsorte, darum nur berichtet, nicht im Kriterium.

### 8.3 Die drei Wege

| Weg | Verfahren | Eingabe | eingefroren vor dem Testlauf |
|---|---|---|---|
| **1** LLM mit Codebuch | `qwen3.6:27b` über die Naht von F5 (`GenerationUse`, `generate_texts`, Modellcache), Temperatur 0, Seed 0, `num_ctx` 8192, `think` aus, `num_predict` 64. Systemprompt = das Codebuch (Grundregeln, alle 22 Optionen mit Definition und Beispiel), wörtlich aus `codebuch.toml` erzeugt; Antwortform `THEMA: <Nummer>` | Dokumentart, Titel, die ersten 4 000 Zeichen des Rohtexts: dasselbe Material wie die Kodierer | Prompt-Version und SHA-256 des Systemprompts in einem Commit vor dem Testlauf. Nebenlauf (nicht fürs Urteil, nur für die Kosten): `gemma4` mit demselben Prompt |
| **2** Ausschuss → CAP | die bestehende Ausschusszuordnung (Punkt 45, `committees`) und eine feste Tabelle Ausschuss → Hauptthema (§ 8.4). **2A**: `papers_ausschuss.parquet` wie die Kette sie schreibt, Restklasse → 99. **2B**: dasselbe Modell ohne Schwelle (`min_probability = 0`), jedes Dokument bekommt seinen wahrscheinlichsten Ausschuss | Korpustext, wie die Kette | Tabelle § 8.4. Vergleichsmaß ist **die bessere von 2A und 2B** auf der Testmenge |
| **3** Klassifikator (Nachbau der Babel Machine) | `xlm-roberta-large` (MIT-Lizenz, Gewichte als safetensors, kein Fremdcode), feinjustiert in einem eigenen Venv außerhalb des Pakets, unter der GPU-Sperre in Blöcken. **3a**: nur menschlich kodierte deutsche CAP-Daten (Anfragentitel und Wahlprogrammsätze, § 2). **3b**: dazu Silberlabels von Weg 1 auf Ratsdokumenten außerhalb der Testmenge (mindestens die 200 der Entwicklungsmenge; ein Auftrag an die GPU-Warteschlange für 4 000 weitere) | Titel und Textanfang, auf 256 Token gekürzt | Hyperparameter fest: Länge 256, Lernrate 1e-5, Stapel 16, zwei Epochen, 10 % Aufwärmen, Seed 0, Auswahl des Prüfpunkts nach Makro-F1 auf den zurückgehaltenen 10 % der CAP-Daten (nie auf Ratsdokumenten). Ins Urteil geht 3b, wenn zum Zeitpunkt der Auswertung Silberlabels für mindestens 2 000 Ratsdokumente vorliegen, sonst 3a |

Nebenverfahren ohne Einfluss auf das Urteil: TF-IDF mit logistischer Regression auf denselben
CAP-Daten (CPU), als Maß, wie weit die Textsorte trägt. Die Babel Machine selbst (Dienst oder
Gewichte) wird nicht benutzt (Konrad, 2026-11-23, Frage 5).

### 8.4 Tabelle Ausschuss → Hauptthema (Weg 2)

Je Ausschuss das Feld, das Name und Zuschnitt am stärksten tragen, festgelegt nach den Namen in
`profiles/duesseldorf.toml` und sechs Titeln je Ausschuss, ohne Blick auf ein Ergebnis eines
Verfahrens. Wortgleich als `AUSSCHUSS_CAP` im Messskript.

| Kürzel | Ausschuss | CAP |
|---|---|---|
| ABA | Anregungs- und Beschwerdeausschuss | 20 |
| ADIG | Digitalisierung und allgemeine Verwaltungsorganisation | 20 |
| AGS | Gesundheit und Soziales | 13 |
| APS | Planung und Stadtentwicklung | 14 |
| AUS | Umwelt-, Klima- und Verbraucherschutz | 7 |
| AWIR, AWIZ | Wirtschaftsförderung, internationale (und regionale) Zusammenarbeit | 15 |
| AWM | Wohnungswesen und Modernisierung | 14 |
| AÖE | öffentliche Einrichtungen, Stadtökologie, Abfallmanagement, Bevölkerungsschutz | 7 |
| BAU | Bauausschuss (städtische Hochbauten) | 20 |
| GLA | Gleichstellung und Antidiskriminierung | 2 |
| HFA | Haupt- und Finanzausschuss | 1 |
| JHA | Jugendhilfeausschuss | 13 |
| KUA | Kulturausschuss | 23 |
| OVA | Ordnungs- und Verkehrsausschuss | 10 |
| RPAU | Rechnungsprüfungsausschuss | 20 |
| SCHUA | Schulausschuss | 6 |
| SEBD | Betriebsausschuss Stadtentwässerung | 7 |
| SPOA | Sportausschuss | 13 |
| WALTW, WABTW, WPA, AWTL, POA | Wahl-, Wahlprüfungs-, Personal- und Organisationsausschüsse | 20 |
| ACI | Chancengerechtigkeit und Integration | 9 |
| Restklasse (nur 2A) | – | 99 |

### 8.5 Maß, Kriterium, Entscheidung

- **Gold**: das geschlichtete Label der Frage `politikfeld` (zwei Kodier-Agenten, Schlichtung, F4).
- **Hauptmaß**: Makro-F1 wie `georep validate score` (F4): ungewichtetes Mittel der F1 über die
  Klassen mit Gold oder Vorhersage, 99 als eigene Klasse, auf den 300 ohne Schichtgewichte (Güte je
  Klasse, keine Prävalenz). Intervall: Bootstrap über die Dokumente, 2 000 Ziehungen, Seed 20261123,
  Perzentile 2,5 und 97,5.
- **Kriterium** (Briefing, unverändert): **Makro-F1 ≥ 0,70 und besser als die Ausschussabbildung.**
  Festgelegt wird hier, was das heißt: der Punktwert ≥ 0,70 (das Intervall wird berichtet), und
  „besser" heißt, dass im gepaarten Bootstrap (dieselben 2 000 Ziehungen) die Differenz Weg minus
  bessere Ausschussvariante im 2,5-%-Perzentil über 0 liegt. Ein Weg, der nur im Punktwert vorn
  liegt, schlägt die kostenlose Ausschusszuordnung nicht nachweislich.
- **Entscheidung**: Erfüllen mehrere Wege das Kriterium, wird der mit dem höchsten Makro-F1 gebaut;
  ist dessen gepaarter Vorsprung vor dem nächsten nicht über 0 (2,5-%-Perzentil), der billigere
  (Weg 3 vor Weg 1, gemessen in GPU-Stunden für alle Perioden).
- **Übereinstimmung der Kodierer**: Krippendorffs α (nominal) für `politikfeld`. Unter 0,67 gibt es
  kein Urteil über die Wege: das Codebuch ist zu unscharf, Fassung 2 mit neuer Stichprobe in einem
  eigenen Ordner (F4). Zwischen 0,67 und 0,8 ist das Urteil vorläufig und Stufe 3 gesperrt (§ 2.6).
- **Nebenmaße** ohne Einfluss: Genauigkeit, Cohens κ gegen Gold, F1 je Klasse mit Zahl der
  Gold-Dokumente, Makro-F1 nur über Klassen mit mindestens fünf Gold-Dokumenten, gewichtetes
  Makro-F1, Verwechslungsmatrix, Übereinstimmung der Wege untereinander, Anteil `unsicher` und Güte
  ohne die unsicheren Dokumente, Güte je Schicht.

### 8.6 Rückfallregel

Erfüllt kein Weg das Kriterium, gilt die **Einigkeitsregel**: ein Politikfeld bekommt nur, wo Weg 1
und Weg 3 dasselbe Hauptthema sagen, sonst „nicht bestimmt" (wie der Konfidenzfilter von ParlaCAP,
dort „Mix"). Gebaut wird sie, wenn auf den Dokumenten mit Einigkeit **Makro-F1 ≥ 0,70**, im
gepaarten Bootstrap **besser als die Ausschussabbildung auf denselben Dokumenten**, und die
**Abdeckung**, mit den Schichtgewichten hochgerechnet, **mindestens 70 %** ist. Sonst: verwerfen;
die Seite behält die Ausschusszuordnung (Punkt 45), Vorhaben 22 seine Klassen `OVA`, `JHA`, `SCHUA`.

### 8.7 Zweite Prüfung an menschlich kodierten Daten

Weg 1 auf den 200 CAP-Anfragentiteln (§ 8.2), Weg 3 auf den zurückgehaltenen 10 % der deutschen
CAP-Daten, beide gegen die menschlichen Codes: Makro-F1 mit Bootstrap-Intervall. Berichtet, nicht im
Kriterium (Bundestag 1976 bis 2005, Titel statt Ratsdokument). Sie ist die einzige Zahl dieses
Vorhabens, hinter der Menschen stehen.

### 8.8 Eingefroren vor dem ersten Testlauf (2026-11-23, 23:10 Uhr)

- **Weg 1**: Prompt-Version `19-cap-1` unverändert seit der Vorab-Festlegung; Systemprompt aus
  `codebuch.toml` (Fassung 2026-11-23.1) mit `systemprompt()` des Messskripts, **18 307 Zeichen,
  SHA-256 `b19eaa091e801db97bda50f6824666675a3f92ebf66116349b04a820caf7efa4`**; Nutzerprompt
  `nutzerprompt()`, Parser `ANTWORT` (erste Nummer hinter `THEMA:`), `num_predict` 64. Geprüft an 20
  Dokumenten der Entwicklungsmenge (alle 20 in der Antwortform, keine Änderung nötig).
- **Weg 3**: Trainingsskript `19-politikfelder-training.py` mit den Werten aus § 8.3, Gewichten von
  `FacebookAI/xlm-roberta-large` im Stand `c23d21b0620b635a76227c604d44e43a9f0ee389` (MIT,
  safetensors); Eingabe je Ratsdokument: Titel und die ersten 1 500 Zeichen des Rohtexts, Leerraum
  zusammengezogen (`schreibe_eingabe()`). Für 3b werden die Silberlabels so oft wiederholt, dass sie
  rund ein Viertel der Beispiele stellen, höchstens 20-fach; nur Antworten von `qwen3.6:27b` mit
  gültiger Nummer, nie von Dokumenten der Testmenge.
- **Silbermenge**: 4 000 Ratsdokumente außerhalb von Test- und Entwicklungsmenge, gleiche Schichtung,
  Seed 20261126 (`schreibe_silber()`; IDs unter `$GEOREP_MESSDATEN/19-politikfelder/silber.csv`).
