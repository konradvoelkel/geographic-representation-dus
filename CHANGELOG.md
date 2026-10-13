# Changelog

Eine Zeile pro Änderung aus Sicht eines Nutzers, neueste oben. Versionen sind Git-Tags.

## Unreleased

- **Mutationstest über die dreizehn Module des Ausbaus** (`docs/mutation-2026-10-13.md`): 876
  Mutanten, 652 getötet (74,4 %); mit den Tests, die die echten Lücken schließen, 712 (81,3 %). Die
  Quote ist kein Gate, aber sie hat echte Löcher gezeigt: `analysis/scaling.dictionary_bias` hatte
  keinen Test, die Zahlen der Vergleichsseite waren nur auf Anwesenheit geprüft, und die Spalte
  `treffer` der Urheberzuordnung (mit der ein Mensch eine Zuordnung nachprüft) war nie verglichen.
  Die Session `nox -s mutate` trägt jetzt alle gemessenen Module und läuft mit drei Arbeitern.

- **`georep publish` fasst nur noch an, was ihm gehört** (Review zum Umzug, 2026-10-13): der
  Arbeitsordner der Kopie heißt nicht mehr `<ziel>.neu` (ein fremder Ordner dieses Namens wurde
  gelöscht), sondern trägt einen Namen von `mkdtemp`, den es noch nicht gibt. Die Stamps der
  Schritte (`*.stamp.json`) bleiben beim Kopieren in der Datenwurzel und liegen damit nicht mehr im
  veröffentlichten Ordner.

- **Düsseldorfs Hauptperiode liegt unter ihrem Slug** (`docs/decisions.md`, Punkt 52; Frage 1.7, Konrads
  Antwort vom 2026-10-13): `georep bootstrap` und `georep run` schreiben nach `data/duesseldorf/` und
  `data/cache/duesseldorf/`, nicht mehr flach nach `data/`; `data/site/` bleibt der veröffentlichte Ordner. Die veröffentlichte Adresse bleibt dieselbe,
  weil `georep publish` die erste Stadt an die Wurzel von `data/site/` legt — neu ist nur, dass auch sie
  kopiert wird. Die Seite der zweiten Periode baut der Pages-Workflow in den Ordner der Stadt, damit die
  Kopie sie mitnimmt; die Pfade kommen dort aus `georep paths`. Die Ergebnisse ändern sich nicht: 27 der 28
  Parquet-Dateien sind byteidentisch zum flachen Lauf (die 28. an drei Texten, die aus lokal extrahierten
  PDFs stammen), und `index.html` bleibt 886 328 Byte.
  **Wer schon Daten hat**, löscht die flachen Ordner `data/{external,raw,interim,processed}` und lässt
  `bootstrap`, `run` und `publish` neu laufen (23 s); wer den PDF-Cache behalten will, verschiebt
  `data/cache/{pdf,text}` statt dessen nach `data/cache/duesseldorf/`. Der Handgriff für Konrads Rechner
  steht in `STATUS.md` unter „Nächster Schritt" und wartet dort auf das Ende der Netzläufe.

## 0.12.0 (2026-10-13), Rueckstand nach dem Ausbau

- Die sechs Punkte aus `docs/todo.md` sind abgearbeitet, je mit Dokument unter `docs/`: Methodik-Review mit
  der Regel für Einrichtungen mit Stadtnamen und der Lockerung der exakten Reproduktion (Tag
  `bartzsch-exakt` auf `v0.11.0`), Themenmodell mit gesäten Themen je Ausschuss und der Zuordnung eines
  passenden Ausschusses je Dokument, Skalierung der Kennzahlen mit Umschaltern, Literaturübersicht, kompakte
  Seite mit eingeklappten Tabellen und nachgeladenen Begriffslisten, Quelltext unter GPL-3.0-or-later.
  Dabei behoben: Splitterflächen aus Fließkomma-Schnitten im Crosswalk, ein Fehler in `canonical_term`, ein
  Überlauf in `nice_ticks`, der verlorene Marker von `georep publish`. Einzelheiten in den Absätzen darunter.

- **Der Hinweis auf eine nicht geladene Datei nennt den richtigen Grund** (Review 2026-10-13,
  Befund 11): aus dem Dateisystem geöffnet verbietet der Browser das Nachladen, über einen Webserver
  fehlt die Datei oder ist unvollständig — vorher stand überall die Erklärung für `file://`.

- **Die 1196 Orte der Karte tragen keinen `<title>` mehr** (Review 2026-10-13, Befund 2;
  `docs/decisions.md` Punkt 50): ihre Ebene ist `aria-hidden` und ohne JavaScript nie sichtbar, der
  Titel erreichte also keinen Screenreader und wiederholte nur, was der Tooltip zeigt. Das sind
  73 842 Byte — `index.html` ist jetzt 886 328 Byte groß, und das Budget von 1,0 MB trägt damit auch
  den Abschnitt „Zwei Wahlperioden" (gemessen rund 35 KB), der nach dem Abruf der zweiten Periode
  dazukommt.
- **`georep publish` prüft das Budget jeder veröffentlichten Seite** und nennt sie in seiner Zeile;
  erst dort kommen die Zeile „Weitere Städte" und die Vergleichsseite dazu.

- **Der Aufklapper langer Tabellen steht jetzt vor der Tabelle** und zeigt mit ▸ und ▾, ob sie zu
  oder offen ist (Review 2026-10-13, Befunde 5 und 7); hinter 41 Zeilen rutschte er beim Aufklappen
  mit dem Fokus aus dem Bild. Dazu ist die Akzentfarbe in Hell abgedunkelt (`#1f68c0` statt
  `#2a78d6`): mit 14,4 px lag sie bei 4,19:1 unter den 4,5:1 von WCAG AA — das betraf jeden Link
  der Seite. Jetzt 5,24:1 auf dem Seitengrund und 5,38:1 auf den Flächen, nachgerechnet von einem
  Test.

- **`index.html#bezirk-17` springt wieder** (Review 2026-10-13, Befund 1): die Vorschau langer
  Tabellen verbarg die Zeile, auf die eine geteilte Adresse zielt — für 38 der 41 Wahlbezirke lief
  der Sprung ins Leere. Die Vorschauregel zeigt jetzt neben einer markierten auch die Zeile unter
  `:target`.

- **Die Gebietsumrechnung zählt keine Splitter mehr** (`docs/decisions.md` Punkt 51). Zwei Flächen,
  die nur eine Grenze teilen, schneiden sich in Fließkomma nicht in 0, sondern in etwa 4,44e-16;
  solche Scheinschnitte wurden zu eigenen Zeilen mit Gewichten wie 2,9e-17. Neu fällt ein
  Schnittstück unter `crosswalk.min_share` (Vorgabe 1e-9 der Quellfläche, 0 schaltet ab) vor der
  Normierung weg. `wahlbezirke_crosswalk` hat auf der Referenz 465 statt 485 Zeilen; jede gedruckte
  Zahl der Seite bleibt gleich (Tabelle 5, Tabelle 6, 6b und die Kennzahlen byteidentisch, größte
  Änderung an einem Koeffizienten 3,9e-08).

- **Das Budget der Seite ist 1,0 MB und steht in den Settings** (`report.page_budget_bytes`,
  `docs/decisions.md` Punkt 50). `georep run` sagt es jetzt selbst, wenn `index.html` darüber liegt;
  vorher stand die alte Grenze von 1,5 MB als Zahl in vier Tests und hat nie gezuckt, während die
  Seite in zwei Tagen um 594 KB wuchs. 958 527 Byte lassen 41 473 Byte Luft — knapp mit Absicht;
  vier gemessene Hebel über zusammen rund 112 KB stehen in `docs/seitengroesse-2026-10.md`, § 5.

- **Die Begriffe je Wahlbezirk stehen nicht mehr in der Seite**, sondern in `data/begriffe.json`
  (`docs/decisions.md` Punkt 49). Der Abschnitt „Begriffe" holt die Liste beim ersten Aufklappen
  eines Wahlbezirks nach, wie der Dialog die Dokumente beim ersten Klick auf einen Begriff holt;
  inline bleiben die trefferstärksten Begriffe stadtweit, die stadtweiten Begriffe, die fünf
  häufigsten je Wahlbezirk und je Wahlbezirk seine Zahl. Das war mit 334 KB der größte Posten der
  Seite: `index.html` schrumpft von 1,29 MB auf 0,96 MB.
  - Die Datei steht mit Zeilenzahl, Größe und SHA-256 unter „Downloads" wie `dokumente.json`.
    Aus dem Dateisystem geöffnet (`file://`) zeigt der Abschnitt denselben Hinweis wie der Dialog:
    der Browser erlaubt das Nachladen dort nicht, über einen Webserver geht es.

- **Lange Tabellen zeigen drei Zeilen, der Rest klappt auf Bedarf auf** (`docs/todo.md` Punkt 2,
  `docs/decisions.md` Punkt 48, Messung in `docs/seitengroesse-2026-10.md`). Elf Aufzählungen der
  Seite (Wahlbezirke, Urheber je Wahlbezirk, Gremien, Monate, Gewichtungen, Themen, Downloads,
  Begriffe, Kontextvariablen) haben darunter eine Schaltfläche „alle *n* Zeilen zeigen"; die Zahl
  der Vorschauzeilen steht in den Settings (`report.table_preview_rows = 3`, 0 klappt nichts ein).
  Offen bleiben die Kernzahlen und die Tabellen 5, 6 und 6b — das ist der Befund.
  - Welche Zeilen sichtbar sind, entscheidet eine CSS-Regel. Darum stimmt die Vorschau auch nach
    dem Sortieren einer Spalte, eine Zeile, die aus Karte, Streudiagramm oder Suche heraus markiert
    wird, klappt von allein auf, und die Druckansicht zeigt jede Zeile. Ohne JavaScript steht alles
    offen.

- **Die Seite hat einen Abschnitt „Literatur und verwandte Arbeiten"** (`docs/todo.md` Punkt 5,
  `docs/decisions.md` Punkt 47). Fünfzehn Einträge zwischen „Abgeleitete Daten" und „Downloads", je
  mit vollständiger Zitation (Autor, Titel, Jahr, Ort oder Institution, URL mit Abrufdatum oder DOI)
  und einem oder zwei Sätzen, was die Arbeit beiträgt und wie dieses Vorhaben sich dazu verhält.
  Dieselbe Liste steht im README unter „Literatur"; ein Test hält beide zusammen.
  - Darunter die methodisch nächste verwandte Forschung, die wir bis jetzt nicht genannt hatten:
    Harmening u. a. 2025 untersuchen 10 189 Anfragen aus zwölf deutschen Großstädten mit demselben
    Werkzeugkasten (Stadtteil-Wörterbuch aus Verwaltungsgrenzen, Wikipedia-Markern und
    OpenStreetMap-Straßen), Nyhuis u. a. 2025 prüfen genau die Wörterbuchfrage, Zittel u. a. 2019
    sind der Ursprung des Ansatzes für Deutschland, und Cherif 2026 ist ein offenes
    OParl-Volltextkorpus. Dazu OParl 1.1 mit seinen Trägern und seiner Verbreitung in
    Nordrhein-Westfalen, die Linie „Offenes Köln" → „Politik bei uns" → „Politik bei uns 2" samt dem
    Beitrag, der erklärt, warum sie einschlief, `meine-stadt-transparent` und der OParl-Validator.
  - **Zwei Lücken stehen sichtbar als „Angaben nachzutragen" da**, statt eine Zitation zu behaupten:
    der Titel der Arbeit, der nirgends steht — ihr Repositorium hat keine Beschreibung, sein README
    nennt nur den Zweck des Programms —, und die Kölner Untersuchung, die die Arbeit zitiert, die am
    2026-10-13 in OpenAlex, Crossref, arXiv, Hochschulrepositorien und auf GitHub nicht auffindbar
    war. Beim Titel steht „[Titel nachzutragen]" da, nicht eine eigene Formulierung.
  - Die Einträge sind **Daten, nicht Vorlage**: `src/georep/report/literatur.toml` im Paket
    (stadtneutral) und `[[report.literature]]` im Profil der Stadt, damit eine zweite Stadt die
    allgemeinen Einträge erbt und nur ihre eigene Arbeit dazulegt. Jeder Link war am 2026-10-13
    erreichbar, jeder DOI über Crossref aufgelöst; die URLs kommen über die Daten in die Allowlist
    der Seite. `index.html` wächst um 13 166 Bytes auf 1,28 MB (Budget 1,5 MB).

- **Jede Kennzahl mit Nenner hat jetzt einen Umschalter** (`docs/skalierung-2026-10.md`,
  `docs/decisions.md` Punkt 46). Konrads Frage war: nicht sehen, wo eine Partei viel über
  Wahlbezirke redet, sondern wie viel mehr oder weniger als der Durchschnitt aller Parteien.
  - Der Abschnitt „Urheber und Parteien" schaltet die sechs kleinen Karten, die Spalte „im Mittel"
    der Parteitabelle und die sechs Parteispalten der Bezirkstabelle zwischen **Anteil**,
    **Abweichung vom Mittel aller Parteien** (in Prozentpunkten) und **Verhältnis zum Mittel** um.
    Das Mittel ist das ungewichtete der Parteianteile im selben Wahlbezirk. Die Antwort in einer
    Zeile: die AfD nennt einen Wahlbezirk in weniger als einem Drittel so vielen ihrer Dokumente
    wie der Durchschnitt der sechs Parteien (Verhältnis 0,32), die GRÜNEN in rund der Hälfte mehr
    (1,59).
  - Die Karte der Wahlbezirke bietet neben der Trefferquote **Treffer absolut**, **Treffer je
    Begriff im Wörterbuch** und die **Abweichung vom Stadtmittel**; die Kennzahlspalte der Tabelle
    je Wahlbezirk zeigt dieselbe Einfärbung als Zahl, und die Kernzahlen nennen den Median der
    Treffer je Begriff (4,57, Spannweite 2,25 bis 9,55).
  - Neben Tabelle 5 steht **dieselbe Regression mit Treffer je Begriff im Wörterbuch** — die
    stärkste offene Empfehlung des Methodik-Reviews. Mit ihr bleibt vom Zusammenhang nichts, nicht
    einmal das Vorzeichen: r = −0,112 und p = 0,486 über alle 41 Wahlbezirke, ohne die Ausreißer 1
    und 10 r = −0,042 und p = 0,800 (Tabelle 5: 0,189 / 0,236 und 0,335 / 0,037). Die einzige
    Spalte, in der die Arbeit ein signifikantes p berichtet, hängt an der Größe der Wörterbücher.
  - Die Standardansicht ändert sich nicht, und Tabelle 5, die Treffer (29 010) und das Wörterbuch
    (5727) sind unberührt. Neue Download-Tabelle `wahlbezirke_kennzahlen` (neuer Schritt
    `metrics`); `wahlbezirke_parteien` hat drei Spalten mehr. `index.html` wächst von 1,10 auf
    1,27 MB (Budget 1,5 MB), die Seite auf 52 Dateien.
  - Divergierende Varianten haben feste, symmetrische Klassengrenzen statt Quantile
    (`[report.diverging]`): eine Abweichung vom Stadtmittel ist eine streng monotone Umrechnung der
    Quote, Quantile darüber wären genau deren Klassen in anderer Farbe. Weil die Grenzen unter
    `[report]` stehen, zählen sie nicht zum Settings-Fingerprint: nach einer Änderung braucht die
    Seite ein `georep run report --force`.
  - „Methode und Grenzen" nennt jetzt die Verzerrung, die dahinter steht: wie stark die Trefferzahl
    an der Größe des Wörterbuchs hängt, was die Normierung herausnimmt und dass sie dafür in die
    andere Richtung verzerrt. Die Zahlen sind gemessen, nicht geschrieben.

- **Die Themen tragen Namen statt Nummern** (`docs/themenmodell-2026-10.md`, `docs/decisions.md` Punkt 45).
  Drei Änderungen am Themenmodell, gemessen auf der Referenz:
  - Die Stoppwörter kommen jetzt aus dem Profil (`topics.stop_sources`): Namen, Kürzel und Muster der
    Parteien und Fraktionen aus `[originators]`, die Gremienkürzel aus `[bodies]`, und Personennamen aus dem
    Korpus — ein Wort, das fast nur hinter einer Unterschrift oder einer Amtsbezeichnung steht, ist ein
    Name (254 Wörter auf der Referenz). Vorher prägten „cdu", „linke", „sönke" oder „torsten" sieben der 20
    Themen; jetzt entstehen dort Schule, Aufsichtsratsbesetzungen und Verfügungsmittel der
    Bezirksvertretungen. Ausnahmen nennt das Profil (`topics.stop_keep`).
  - Jeder Ausschuss mit genug beratenen Dokumenten bekommt ein eigenes Thema, dessen Wörter aus seinen
    Dokumenten kommen (`topics.seed = "committees"`, auf der Referenz 17 von 20 Themen; drei bleiben frei).
    Die Themenzeilen der Sensitivitätstabelle heißen damit „Thema 0: Ordnungs- und Verkehrsausschuss", und
    die Themen-Tabelle hat eine Spalte „Gremium". `themen.parquet` hat die neue Spalte `gremium`.
  - Neu: **Dokumente je passendem Ausschuss** im Abschnitt „Gremien". Ein Klassifikator (TF-IDF und
    logistische Regression, Schritt `committees`) ordnet jedem Dokument den sachlich passenden Ausschuss zu,
    auch denen, die nur im Rat oder in einer Bezirksvertretung waren; unter `classify.min_probability`
    bleibt es in der Restklasse. Genauigkeit 0,941 und Makro-F1 0,878 in der Kreuzvalidierung, aber vier von
    fünf BV-Dokumenten und sieben von acht Ratsdokumenten bleiben in der Restklasse — querschnittliche
    Vorlagen haben kein Ausschussthema, und ein Teil der Güte hängt daran, dass eine Ausschussvorlage ihren
    Ausschuss im Text nennt (ohne diese Wörter 0,929 / 0,864). Neue Download-Tabelle `ausschuss_zuordnung`.

  Tabelle 5, die Treffer und das Wörterbuch ändern sich dadurch nicht; die `thema_NN`-Zeilen der
  Gewichtungstabelle tragen andere Zahlen, weil die Themen andere sind. Der volle Offline-Lauf dauert 23 s
  statt 17 s.

- Behoben: `nice_ticks` (Achsenticks der Diagramme) warf einen `OverflowError`, wenn beide Grenzen endlich
  waren, ihre Differenz aber nicht; die Vorbedingung verlangt jetzt eine endliche Spanne. Mit echten
  Achsen kam der Fall nicht vor; gefunden hat ihn crosshair.
- Behoben: `canonical_term` (die Rückübersetzung „münchener str." → „münchener straße", Option 08) ließ eine
  Abkürzung stehen, wenn die eingesetzte Langform mit dem nächsten Zeichen des Begriffs eine neue bildete.
  Ersetzt wird jetzt bis zum Festpunkt. Mit den ausgelieferten Paaren konnte der Fall nicht vorkommen; gefunden
  hat ihn crosshair (`nox -s verify`).

- **Stadtweite Begriffe stehen auf der Seite** (`search.citywide_quantile`, Vorgabe 0,99): Begriffe, deren
  Dokumentzahl über dem 99-%-Quantil liegt (auf der Referenz 55 von 5727 Begriffen über 64 Dokumenten, ohne
  Regel 1 sind es 58 von 5841; darunter „grafenberger allee" 205, „hofgarten" 172, „schulweg" 144), bekommen
  im Abschnitt „Begriffe" eine
  eigene Liste mit Dokumentzahl und Wahlbezirk: sie stehen in weit mehr Dokumenten, als ihr Wahlbezirk
  hergibt, und das soll sichtbar sein. **Gezählt werden sie weiter**: die Regel zeigt an und rechnet nicht,
  denn die Schwelle trifft auch echte Ortsnamen. Alternativ zum Quantil eine Schwelle als Vielfaches des
  Medians (`search.citywide_median_factor`); genau eine der beiden gilt. „Methode und Grenzen" nennt beide neuen
  Regeln in einem Absatz (`docs/decisions.md`, Punkt 44b).
- **Einrichtungen mit Stadtnamen sind keine Orte** (`search.city_facilities`, standardmäßig an): ein Ort aus
  Wikidata oder Wikipedia, dessen Label mit dem Stadtnamen des Profils endet („Stadtwerke Düsseldorf",
  „Messe Düsseldorf") oder das Städteadjektiv als eigenes Wort führt („Düsseldorfer Schauspielhaus"), fällt
  aus dem Wörterbuch und von der Karte: solche Dokumente handeln von der Einrichtung, nicht von ihrem
  Wahlbezirk. Orte, in deren Label ein Wort auf ein Gattungswort aus `search.place_words` endet (Bahnhof,
  Park, Wald, Gymnasium, Klinik …) oder die dem Stadtnamen noch ein Wort nachstellen („Bahnhof
  Düsseldorf-Rath"), bleiben Orte; Straßen sind nie betroffen. Auf der Referenz trifft die Regel 113 von 1309 Labels, die Treffer sinken um 1,9 %, der
  Wahlbezirk 10 verliert 14,9 % seiner Treffer und ist kein Ausreißer mehr. `search.city_facilities_keep` im
  Profil nimmt einzelne Labels wieder heraus. Mit `city_facilities = false` rechnet die Kette wie die Arbeit
  (`docs/decisions.md`, Punkt 44a, gemessen in `docs/methodik-review-2026-10.md`).
- Der Quelltext steht unter GPL-3.0-or-later (`LICENSE`); bis zum Tag `v0.11.0` war es CC0 1.0 wie das
  Original. Ergebnisse, Tabellen und die Berichtsseite bleiben CC0 1.0, die Daten behalten die Lizenz ihrer
  Quelle; der Fuß der Seite nennt beides.
- Der Tag `bartzsch-exakt` markiert `v0.11.0` als letzten Stand, der die Zahlen der Arbeit exakt reproduziert;
  ab jetzt genügt eine ungefähre Reproduktion (Konrad, 2026-10-12, `docs/decisions.md`, Punkt 43).

## 0.11.0 (2026-10-12), Ausbau in acht Optionen

- Sammelversion des Ausbaus nach `docs/plan-ausbau-2026-10.md`: acht Optionen auf eigenen Branches, je mit Plan
  und Abnahme unter `docs/plans/`, Review und Merge in der Reihenfolge 08, 05, 06, 03, 04, 02, 01, 07. Die
  Einzelheiten stehen in den Absätzen darunter, neueste zuerst. Was die Seite noch nicht zeigt, wartet auf
  einen Netzlauf: die zweite Wahlperiode, Mönchengladbach und die laufende Periode (STATUS.md, „Nächster
  Schritt"). Nebenbei behoben: ein zweiter `georep publish --out` in denselben Ordner scheiterte, weil die
  Kopie der ersten Stadt die Markerdatei löschte.
- **Weitere Städte** (Option 01): dieselbe Kette rechnet jede Kommune, deren Profil im Paket liegt. Ein
  Profil ist eine TOML-Datei (`src/georep/profiles/<slug>.toml`) mit allem Stadtspezifischen: Endpunkt,
  Quellen mit Dateinamen, Wikidata-Entität, Spalten und Parteien, Ausschlussliste, Marker, Quellen mit
  Lizenz für den Fuß der Seite, Ausreißer der zweiten Regression. Gewählt wird es mit `--profile`, sonst
  `GEOREP_PROFILE`, sonst `default_profile`; `georep profiles` listet die Profile, `georep status` nennt
  Profil und Stadt. Ein Profil kann mit `base = "<profil>"` auf einem anderen aufbauen: so sind die beiden
  Wahlperioden-Profile (Option 02) jetzt `duesseldorf-2014` und `duesseldorf-vergleich` im Paket und erben
  alles Düsseldorfer. `defaults.toml` ist damit stadtneutral, und im Code steht kein Stadtwort mehr.
- Mitgeliefert ist neben Düsseldorf das Profil **Mönchengladbach** (AGS 05116000, OParl-Body 0011): sein
  Wahlergebnis kommt aus dem votemanager der ITK Rheinland (Spalten `A`, `B`, `D1` bis `Dn`, Wahlbezirk in
  den Zeichen 1 und 2 der Stimmbezirksnummer), seine Flächen aus einem Shapefile-Zip. Der volle Abruf ist
  ein Handgriff mit Prüfpunkten: `docs/runbook-stadt.md`.
- Neuer Schritt `shapes`: aus GeoJSON oder Shapefile-Zip entsteht `interim/stimmbezirke.geojson` mit drei
  festen Eigenschaften und dem CRS der Quelle; alles dahinter kennt nur noch dieses Format. Neue
  Abhängigkeit `pyshp` (reines Python, MIT) statt GDAL.
- Die Berichtsseite liest die Stadt: Kopf, Fuß und „Methode und Grenzen“ nennen Name, Rat, Wahl, Marker und
  die Quellen mit Lizenz und Prüfdatum aus dem Profil; wo es ein amtliches Straßenverzeichnis gibt, steht
  die gemessene Übereinstimmung der Flächen mit dem Zuschnitt der Wahl dort.
- Neuer Download `data/summary.json` je Stadt: Kernzahlen, beide Regressionen und Datenstand, beschrieben in
  `schema.json`. Er ist die Schnittstelle des Städtevergleichs.
- Neuer Befehl `georep publish`: trägt die Stadtseiten nach `data/site/` zusammen (die erste Stadt an der
  Wurzel, jede weitere unter ihrem Slug) und baut `vergleich.html` — Tabelle, zwei kleine Karten mit
  gemeinsamen Klassengrenzen, ein Streudiagramm mit beiden Städten, Hinweise zur Vergleichbarkeit. Fehlt der
  Lauf einer Stadt, sagt der Befehl das und lässt den Vergleich weg.
- Eine Stadt bringt mit, was sie hat: ohne Kontextdatensatz fehlt der ganze Block `[context]` und mit ihm die
  Schritte `context_data`, `context` und `controls`; ohne Fraktionsnamen (`[originators]`) entfällt der Schritt
  `parties`; tragen die Drucksachennummern kein Kürzel des Gremiums, bleibt `bodies.reference_pattern` leer und
  jedes Dokument zählt als „unbekannt". Den Stadtbezirk je Stimmbezirk liest das Profil aus einer Spalte oder
  aus der Stimmbezirksnummer (`city_district_from_precinct`).
- Düsseldorf rechnet unverändert: der Golden Master, die Zahlen der Seite und ihre Adresse bleiben, wie sie
  waren (`profile = ""`, Daten weiter flach unter `data/`).

- **Zweite Wahlperiode (Option 02).** Eine Wahlperiode ist jetzt ein Profil:
  `--profile duesseldorf-2014` rechnet
  dieselbe Kette für 2014 bis 2020 in `data/2014-2020/`, mit dem Wörterbuch der Hauptperiode und dem
  Wahlergebnis der Ratswahl 2020, das über Flächenanteile der Stimmbezirke auf die Wahlbezirke von 2025
  umgerechnet wird (Zählgrößen anteilig und ganzzahlig summentreu, Briefwahl proportional zu den
  Wahlscheinen, Zuordnung als `stimmbezirke_zuordnung.parquet` zum Download).
  `--profile duesseldorf-vergleich` schaltet auf der Hauptperiode den Schritt `compare` und den Seitenabschnitt „Zwei Wahlperioden" ein:
  Streudiagramm der Änderungen, Regression der Differenzen, Tabelle je Wahlbezirk, Link auf die eigene
  Seite der alten Periode. Ohne die beiden Profile ist die Kette unverändert. Der Abruf der alten Periode
  ist vorbereitet und wiederaufnehmbar (`sources.oparl.first_page`, `raw/papers.progress.json`), aber noch
  nicht gelaufen; bis dahin fehlt der Abschnitt auf der veröffentlichten Seite. Der README beschreibt den
  Lauf unter „Zwei Wahlperioden".
- `wahlbezirke_waehler.parquet` trägt in jeder Periode dieselben Spaltennamen; Quellspalten werden beim
  Lesen umbenannt (für die Hauptperiode ein No-op, die Zahlen sind unverändert). Vier Stellen, die eine
  abgeleitete Tabelle lesen (Gremien, Gewichtung, Parteien, Kontrollvariablen), lasen bisher den
  Quellspaltennamen — richtig nur, solange beide gleich heißen; sie lesen jetzt die Konstante.

- Neuer Abschnitt „Urheber und Parteien" auf der Berichtsseite: je Ratsdokument der Urheber (Verwaltung,
  Fraktion, Person, Eingabe nach § 24 GO NRW oder unbekannt) und bei Fraktionen die Parteien, abgeleitet aus
  Dokumentart, Titel und Textkopf, weil der OParl-Server die Urheberfelder für Düsseldorf nicht füllt. Sechs
  kleine Karten zeigen je Partei, welcher Anteil ihrer Dokumente einen Wahlbezirk erwähnt; eine Tabelle je
  Partei stellt das dem Stimmenanteil gegenüber (Pearson *r* und *p*, Bonferroni-Hinweis bei sechs Tests), und
  die Tabelle je Wahlbezirk zeigt die Urheberklassen und die schattierten Parteispalten. Drei neue
  Download-Tabellen (`dokumente_urheber`, `wahlbezirke_urheber`, `wahlbezirke_parteien`), der Dokumentdialog
  nennt den Urheber. Neuer Offline-Schritt `parties` und der schnelle Netzschritt `organizations`;
  `georep fetch papers --max-pages N` liest nur die ersten Seiten und zählt, wie viele Paper ein Urheberfeld
  tragen. Alle Muster und Parteien stehen in `defaults.toml` unter `[originators]`.
- Kontrollvariablen (Option 03): die Berichtsseite stellt der Regression von Tabelle 5 drei Modelle mit
  Sozialdaten der Stadt gegenüber (Tabelle 6), zeigt je Term des Hauptmodells ein partielles Streudiagramm,
  nennt in Tabelle 6b den Koeffizienten der Trefferquote mit je einer Kontrollvariable und sagt unter
  „Abgeleitete Daten", woraus jede Variable entsteht, mit Quelle, Lizenz, Datenstand und Abrufdatum. Die
  Fremddaten (Quartiersatlas Düsseldorf 2024, dl-de/by-2-0) liegen unter `context/` im Repo und werden über
  die Stimmbezirksflächen und die Wahlberechtigten auf die Wahlbezirke umgerechnet. Neu sind die Schritte
  `context_data` (Netz), `context` und `controls`, drei Download-Tabellen und `georep regress --controls`;
  ohne Fremddaten (`context.root = ""`) bleibt alles wie bisher. Befund auf der Referenz: mit den
  Kontrollvariablen erklärt das Hauptmodell R² = 0,89 statt 0,03, und der Zusammenhang der Trefferquote mit
  der Wahlbeteiligung ist nicht mehr von Null zu unterscheiden.
- Gewichtete Trefferquoten (Option 06): die Berichtsseite hat einen Abschnitt „Was ändert die Gewichtung?" mit
  einer Sensitivitätstabelle — Tabelle 5 unter 26 Gewichtungen, dazu die Rangkorrelation zur ungewichteten
  Quote. Gewichtet wird je Begriff (in wie vielen Wahlbezirken er geführt wird, in wie vielen Dokumenten er
  steht), je Dokumentart (Regex-Regeln aus den Settings, zwei Regelsätze) und je Thema; ein Themenmodell
  (TF-IDF und NMF, scikit-learn, 20 Themen) verteilt jedes Dokument mit Text auf Themen. Mit Einheitsgewichten
  ist die Rechnung exakt die Trefferquote der Arbeit. Zwei neue Schritte (`topics`, `weights`, zusammen rund
  10 s), vier neue Tabellen zum Download, `georep regress --varianten` druckt dieselbe Tabelle im Terminal.
  Auf der Referenz erreicht der Zusammenhang über alle 41 Wahlbezirke unter 2 von 26 Gewichtungen das
  5-%-Niveau, ohne die Wahlbezirke 1 und 10 unter 8 von 26. `topics.k = 0` schaltet das Themenmodell ab.
- Gremien (`docs/plans/05-gremien.md`): jedes Ratsdokument bekommt aus seiner Drucksachennummer das Gremium
  (Rat, eine der zehn Bezirksvertretungen, Ausschuss, Beirat oder „unbekannt"); auf der Referenz trifft das
  Muster alle 19 108 Nummern, 0 bleiben unbekannt. Die Berichtsseite bekommt den Abschnitt „Gremien" mit einer
  Tabelle je Wahlbezirk und einer je Gremium, die Karte einen dritten Umschalter „Anteil eigene
  Bezirksvertretung", und es gibt drei neue Tabellen zum Download (`wahlbezirke_gremien`, `gremien`,
  `wahlbezirke_stadtbezirke`). Welche Bezirksvertretung für einen Wahlbezirk die eigene ist, folgt aus den
  Stadtbezirken seiner Stimmbezirke, gewichtet über die Wahlberechtigten; der Wahlbezirk 40 liegt in zwei und
  bekommt eine Fußnote. Zwei neue Offline-Schritte (`bodies`, `body_hits`), elf statt neun;
  `wahlbezirke_auswertung.parquet` bleibt byteidentisch. Alle Kürzel und Namen stehen in den Settings
  (`[bodies]`); die neuen Schlüssel lassen alle Schritte einmal neu laufen.
- Suchfeld „Straße oder Ort" auf der Berichtsseite: beim Tippen erscheinen Vorschläge aus dem Wörterbuch
  (4176 Einträge: Straßen aus OpenStreetMap, Orte aus Wikidata und Wikipedia, die 41 Wahlbezirksnamen). Die
  Auswahl nennt die Art, die Wahlbezirke mit Namen und die Zahl der Dokumente mit Treffer, zeigt sie auf
  Wunsch im Dialog, markiert die Bezirke in Karte, Tabelle und Streudiagramm und setzt bei einem Ort eine
  Marke auf die Karte. „Münchener Str.", „muenchener strasse" und „suedstr" finden dasselbe; eine Suche ist
  als Adresse teilbar (`index.html#suche=hofgarten`). Die Vorschläge stecken in der Seite und brauchen kein
  Netz, also auch keinen Webserver; nur die Dokumentliste wird wie bisher nachgeladen. `index.html` wächst
  dadurch von 687 KB auf 848 KB (gzip 141 KB), Budget 1,5 MB.

- Die laufende Wahlperiode seit der Kommunalwahl 14.09.2025 lässt sich fortschreiben: das Profil
  Paketprofil `duesseldorf-2025` legt Daten unter `data/2025/` und Cache unter `<cache_root>/2025/`, holt je Lauf nur
  Geändertes (`modified_since`), entfernt im Ratsinformationssystem gelöschte Paper aus dem Store und baut
  eine eigene Seite ohne Regression, dafür mit der Monatsreihe. Neuer Schritt `timeline` mit zwei Tabellen
  (`monatsreihe`, `wahlbezirke_monate`) und ein Abschnitt „Je Monat" auf beiden Seiten; die Hauptseite
  verweist auf die laufende Periode, sobald `report.monitoring_url` gesetzt ist. Für den Betrieb liegen ein
  idempotentes Lauf-Skript, zwei systemd-Einheiten und eine Anleitung unter `deploy/`.
- Fundament für den Ausbau in acht Optionen (`docs/plans/00-synergien.md`): die Berichtsseite entsteht aus einem
  Rahmen und Abschnittsdateien (`templates/sections/`), die veröffentlichten Tabellen stehen in einem Register,
  die Ausreißer von Tabelle 5 in den Settings (`analysis.exclude_districts`), ein `profile` legt Daten und
  Cache einer weiteren Stadt oder Periode in einen Unterordner, `period.end` darf offen bleiben (`election`
  nennt dann den Wahltag), und `georep.crosswalk` rechnet Gebietseinheiten auf Wahlbezirke um. Ergebnisse und
  Seite sind unverändert; die neuen Settings-Schlüssel lassen alle Schritte einmal neu laufen.

## 0.10.0 (2026-10-11), Berichtsseite: Dokumente, Orte, Leaflet

- Ein Klick auf einen Begriff zeigt die Dokumente, in denen er vorkommt: Datum, Drucksache, Titel, Art und
  Link auf das PDF im Ratsinformationssystem. Die Liste kommt aus `data/dokumente.json` (11 051 Dokumente ohne
  Texte, Begriffe als Indizes, 2,1 MB, gzip 0,5 MB) und wird beim ersten Klick nachgeladen; aus dem
  Dateisystem geöffnet sagt die Seite, warum das nicht geht.
- Die Orte auf der Karte tragen Namen und Wahlbezirk im Tooltip.
- `karte.html`: dieselben Flächen und Orte auf OpenStreetMap-Kacheln mit Leaflet 1.9.4 (per Subresource
  Integrity gepinnt), als einzige Seite mit Fremdressourcen; die Hauptseite bleibt ohne Netz nutzbar.

## 0.9.0 (2026-10-11), Berichtsseite

- Neuer Pipeline-Schritt `report` am Ende der Kette: `georep run` schreibt `data/site/index.html`, eine in sich
  geschlossene Seite mit Kernzahlen, Karte der 41 Wahlbezirke (Trefferquote oder Wahlbeteiligung, Tooltips,
  Klick-Markierung, Orte als Punkte), Streudiagramm mit beiden Regressionsgeraden und Tabelle 5, sortierbarer
  Tabelle je Wahlbezirk, Begriffen, Methode und Grenzen, Lizenzen; Deutsch mit englischer Kurzfassung, hell und
  dunkel, ohne externe Ressourcen.
- Downloads unter `data/site/data/`: die sechs Ergebnistabellen als Parquet und CSV, `wahlbezirke.geojson`
  (EPSG:4326) und `schema.json`; Größe und SHA-256 jeder Datei stehen auf der Seite, das Spaltenschema daneben.
- Die Mini-Fixture trägt die Stimmbezirke ihrer drei Wahlbezirke; `bootstrap` findet jetzt alle vier Eingaben.
- Jinja2 ist Laufzeitabhängigkeit, matplotlib nur noch in der Gruppe `notebook`.

## 0.8.0 (2026-10-11), Phase 7

- README aus Sicht eines frischen Klons: vier Befehle bis zu Tabelle 5, Herkunft der Daten mit Quellen und
  Lizenzen; geprüft aus einem frischen Klon.
- `docs/architecture.md` beschreibt den Aufbau, `docs/decisions.md` zwanzig Entscheidungen mit verworfenen
  Alternativen und Kosten; der Entwicklungsplan ist abgeschlossen und liegt unter
  `docs/development-plan-2026-10.md`. Kein Pull Request an das Original.

## 0.7.0 (2026-10-11), Phase 6

- Verträge mit deal auf Suche, Auswertung, Aufbereitung, Geometrie, Layout, Stores, HTTP, Settings und
  Quellen: Pflichtspalten, sortierte eindeutige Schlüssel und Listen, Begriffe kleingeschrieben und ohne
  Komma, Koordinaten in Grad, r in [-1, 1]; eine Verletzung ist ein Programmierfehler und läuft durch.
  `contracts = "off"` in den Settings schaltet ab; der Overhead liegt unter einem Prozent.
- Kaputte Quellantworten und Netzfehler sind Domänenfehler (`FetchError`, `NetworkError`): `georep fetch`
  meldet einen abgebrochenen Abruf als eine Zeile statt als Traceback. Ein leerer `text_split_marker` ist ein
  Settings-Fehler, eine Regression ohne Streuung ein `EmptyResultError`.
- `nox -s verify` sucht mit crosshair Gegenbeispiele zu den Verträgen der reinen Funktionen, `nox -s mutate`
  misst mit pytest-gremlins die Mutationsquote (79 %); `deal.cases` lässt hypothesis die Verträge angreifen.
- Behoben: `street_names` warf `TypeError` bei einer Overpass-Antwort ohne Liste; deals `has()`-Patch blieb
  nach rekursivem `deep_merge` stehen und hätte jeden späteren `print` und Netzzugriff blockiert.

## 0.6.0 (2026-10-11), Phase 5

- `georep profile [SCHRITT …]` führt echte Schritte unter cProfile aus und schreibt `.prof`-Dateien für snakeviz;
  `nox -s profile` ruft dasselbe, `nox -s bench` misst die heißen Pfade mit pytest-benchmark gegen den letzten
  gespeicherten Lauf (rot ab 20 % langsamer im Minimum; 10 % lagen unter dem gemessenen Rauschen).
- Die PDF-Bibliothek steht hinter dem Protokoll `PdfTextExtractor`; der Extraktorname ist der Cache-Schlüssel
  des Textstores, ein neuer Name macht alte Texte veraltet.
- Erste Messung in `docs/profiling/README.md`: Offline-Lauf 6,3 s, davon 4,1 s FlashText; Extraktion 38 ms je
  PDF über 200 PDFs; pypdf 6.20.0 reproduziert 197 von 200 Texten der Arbeit zeichengleich. Empfehlung: pypdf
  und FlashText bleiben, kein Rust-Port.
- `.gitignore` ignorierte `/data/` und `mutants/` nicht (Kommentar hinter dem Muster); behoben.

## 0.5.0 (2026-10-11), Phase 4

- Eigenschaftstests mit hypothesis für Suche, Aufbereitung, Treffer, Geometrie und Speicher; ein lesbares
  Orakel legt den Matcher-Vertrag fest (längster Treffer an Wortgrenzen, Umlaute sind Grenzen).
- Testsuite läuft parallel mit Abdeckung als Untergrenze; `georep steps` hat einen Snapshot.
- Mutationstests vertagt: mutmut 3 forkt, Polars blockiert im Kind (`docs/mutation-2026-10-11.md`).

## 0.4.0 (2026-10-11), Phase 3

- `georep fetch` holt alles aus dem Netz, wiederaufnehmbar: Metadaten seitenweise mit Abbruch unter dem
  Periodenbeginn und `modified_since` beim zweiten Mal, PDFs einzeln mit Manifest und Limit, Straßen per
  Overpass, Orte per Wikidata und Wikipedia; HTTP-Antworten liegen mit Lebensdauer je Quelle im Cache.
- Texte werden nur neu extrahiert, wenn PDF oder Extraktor sich geändert haben; alle Texte liegen in einer
  Parquet-Datei.
- Geometrie ohne geopandas: ein metrisches Arbeits-CRS, STRtree-Zuordnung; die Zuordnung der Arbeit wird
  für alle 1996 Orte reproduziert.
- Der Code der Arbeit ist vollständig ersetzt; pandas, geopandas, osmnx, scikit-learn und tqdm sind weg.

## 0.3.0 (2026-10-11), Phase 2

- Neue Kommandozeile `georep`: `bootstrap`, `run`, `steps`, `status`, `export`, `regress`; Schritte werden
  übersprungen, wenn Eingaben, Settings, Code und Schema unverändert sind, und sagen sonst, warum sie laufen.
- Konfiguration in TOML: `defaults.toml` im Paket mit Begründungen, `settings.toml` und `settings.local.toml`
  im Arbeitsverzeichnis, Umgebungsvariablen `GEOREP_*`. Daten und Cache liegen, wo man sie hinlegt.
- `data/` heißt `reference/` und wird nur gelesen; Läufe schreiben nach `data_root`.
- Die Offline-Kette rechnet in Polars und schreibt Parquet; die Ergebnisse sind identisch mit denen der Arbeit.
- OParl-Antworten werden gegen ein typisiertes Modell geprüft; eine echte Antwort liegt als Fixture bei.
- Notebook nutzt `georep.analysis.regression`; pandas und scikit-learn sind keine direkten Abhängigkeiten mehr.

## 0.2.0 (2026-10-11), Phase 1

- Kein Lauf zerstört mehr Daten: alle Schreibvorgänge atomar; Schritte verweigern leere Ergebnisse
  und fehlende Eingaben; `prep_papers` überschreibt den Korpus nicht mehr mit leeren oder weniger Texten.
- Netz: Timeout 180 s, Wiederholung mit Backoff, User-Agent. Der PDF-Download läuft bei Fehlern weiter
  und berichtet, wie viele Dateien geladen, übersprungen und fehlgeschlagen sind; Antworten ohne PDF-Kopf
  werden abgewiesen. Der Metadaten-Download speichert nach jeder Seite und bricht laut ab.
- Wahlergebnis-CSV wird byteweise gespeichert; Umlaute hängen nicht mehr von geratenem Encoding ab.
- Invertierter Index nach Begriff sortiert; zwei Läufe schreiben dieselben Dateien.
- Wikidata-Entität und Sprache kommen aus der Konfiguration; Log-Level über `GEOREP_LOG_LEVEL`
  (Standard INFO statt DEBUG).
- Neu: Paket `georep` (`io`, `http`, `errors`), 37 neue Tests.

## 0.1.0 (2026-10-11), Phase 0

- uv-Projekt auf Python 3.14 mit Lockfile; `requirements.txt` entfällt.
- Charakterisierungstests für die Offline-Kette und Tabelle 5; Mini-Fixture; vier PDF-Fixtures mit Herkunft.
- nox, pre-commit, GitHub Actions; Code mit Ruff modernisiert und formatiert, ohne Verhaltensänderung.
