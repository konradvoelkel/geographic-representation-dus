# Plan 08: Suche

Stand 2026-10-11, Branch `feat/08-suche`. Status: in Arbeit (seit 2026-10-12).

Briefing: [../plan-ausbau-2026-10.md](../plan-ausbau-2026-10.md), § 7.8; Regeln § 2; Vorlage § 8.3; Seite ansehen
§ 8.4. Der Plan ist so geschrieben, dass ein frischer Agent ihn ohne Rückfragen umsetzt. Alle Zahlen sind am
2026-10-11 im Worktree nachgemessen (Polars, `ls -l`, ein Node-Prototyp der JavaScript-Normalisierung auf den
echten 4135 Einträgen im Scratchpad); nichts ist geschätzt, wo es messbar war.

## 1. Ziel und Nicht-Ziel

**Ziel.** Ein Suchfeld „Straße oder Ort" auf `index.html`. Beim Tippen erscheinen Vorschläge aus dem Wörterbuch
(Straßennamen aus OpenStreetMap, Orte aus Wikidata und Wikipedia, dazu die Namen der Wahlbezirke). Die Auswahl
eines Vorschlags zeigt: die Art (Straße, Ort, Wahlbezirk), den oder die Wahlbezirke, deren Wörterbuch den Begriff
führt (mit Namen, anklickbar), die Zahl der Dokumente mit Treffer, eine Schaltfläche „Dokumente zeigen" (der Dialog
aus Stufe G), und die Markierung auf der Karte (Wahlbezirke hervorgehoben, ein Ort als Marker). Die Vorschläge
funktionieren ohne Server, also auch aus dem Dateisystem (`file://`), weil die Daten inline in der Seite liegen;
die Dokumentliste braucht wie bisher einen Webserver (`data/dokumente.json`, 2,1 MB, nachgeladen). Tastatur und
Screenreader bedienen das Feld nach dem Combobox-Muster der WAI-ARIA Authoring Practices. Eine Suche ist als
Adresse teilbar (`index.html#suche=münchener%20straße`).

**Nicht-Ziel.** Keine Volltextsuche in den Dokumenten (die Texte sind nicht veröffentlicht); keine
Fuzzy-Suche mit Editierdistanz und keine Bibliothek dafür (Präfix und Teilstring nach Normalisierung reichen,
§ 2); kein Geocoding, keine Hausnummern, keine Koordinatensuche; keine neue Download-Datei unter `data/` (das
Wörterbuch liegt dort schon als `combined_searchdict.parquet`); keine Fremdressourcen, kein Build mit npm, kein
Framework; keine Änderung an Wörterbuch, Index oder Ergebnissen (der Golden Master bleibt byteidentisch).

## 2. Entscheidungen (mit verworfenen Alternativen und Kosten)

| Frage | Entscheidung | Warum, und was verworfen wurde |
|---|---|---|
| Wo liegen die Suchdaten | inline in `index.html` als `<script id="suche-daten" type="application/json">`, über `_json_for_script` aus `render.py` (`</` wird `<\/`), mit `\|safe` eingefügt | Vorschläge müssen aus `file://` funktionieren, und `fetch` ist dort verboten (die Seite sagt das heute schon beim Dialog). Gemessen (§ 3): 141 835 Byte, gzip 35 885. Verworfen: `data/suche.json` nachladen (kein `file://`); `<datalist>` mit 5841 `<option>` (ähnlich groß, ohne Bezirke, ohne Normalisierung; Gründe in der Zeile „Bedienelement") |
| Form der Einträge | ein Eintrag je *kanonischem* Begriff: die `str.`-Variante wird in die `straße`-Form zusammengezogen; je Eintrag `[begriff, [wahlbezirke], dokumente, art]`; `dokumente` ist die *Vereinigung* der `paper_ids` beider Schreibweisen; `art` ist eine Buchstabenmenge aus `s` (Straße, aus `wahlbezirke_strassen.parquet`), `o` (Ort, aus `wikidata_vis.parquet`), `w` (Wahlbezirksname) | 1705 Paare `x straße` / `x str.` würden sonst als zwei Vorschläge erscheinen; die Vereinigung zählt ein Dokument einmal, auch wenn es beide Schreibweisen enthält (gemessen: in 256 von 1705 Paaren weicht die Vereinigung von der Summe ab, 30 404 gegen 30 880 über alle). Kosten: die Zahl im Suchergebnis kann von den Zahlen hinter den Begriffs-Schaltflächen abweichen; das Ergebnis sagt „beide Schreibweisen". Verworfen: alle 5840 Begriffe einzeln (170 829 Byte, doppelte Vorschläge); nur Begriffe mit Treffer (spart 1618 Einträge, aber „Alzeyer Weg: Wahlbezirk 17, keine Dokumente" ist eine richtige und nützliche Antwort) |
| Wahlbezirksnamen als Einträge | die 41 Namen aus dem GeoJSON (`DistrictRow.name`, z. B. „Urdenbach, Garath Kämpenviertel") als Einträge der Art `w`, Originalschreibweise, `dokumente` = `anzahl_treffer` des Bezirks, keine Dialog-Schaltfläche | „Benrath" steht in der Ausschlussliste und darum nicht im Wörterbuch; die Suche danach soll trotzdem zu Wahlbezirk 39 führen. Teilstring-Abgleich auf dem ganzen Namen liefert „Garath" sowohl für 40 als auch für 41, ohne die Namen zu zerlegen. Kosten: rund 2 KB. Stadtteile aus `Stadtteil Name` je Stimmbezirk (50, davon 23 über mehrere Wahlbezirke) kommen erst, wenn die Synergiephase den Crosswalk Stadtteil zu Wahlbezirk als Fundament liefert (§ 8, Frage 4) |
| Normalisierung in JavaScript | eine Funktion `fold`: kleinschreiben; Abkürzungen aus dem Payload (`[["straße","str."]]`) zurück auf die Langform, überall im Begriff wie `normalise_terms` (`südstr.` → `südstraße`), dazu ohne Punkt am Wortende (`münchener str` → `münchener straße`); Unicode NFD und Kombinationszeichen weg (`ü` → `u`); `ß` → `ss`; Whitespace bündeln. Zweiter Schlüssel je Eintrag mit `ä` → `ae`, `ö` → `oe`, `ü` → `ue` für Tastaturen ohne Umlaute. Beide Schlüssel einmal beim Laden berechnet (4135 Einträge) | spiegelt das Wörterbuch (`search/dictionary.py`: kleingeschrieben, getrimmt, `straße`/`str.`), ohne die Regel ein zweites Mal hart zu kodieren: sie kommt aus einer Konstante in `dictionary.py` und steht im Payload. Geprüft im Prototyp: „südstr", „suedstr", „Münchener Str.", „muenchener", „Koenigsallee" finden ihren Begriff; keine zwei Einträge fallen nach `fold` zusammen. Verworfen: Levenshtein oder Trigramme (Bibliothek oder 100 Zeilen eigener Code für Tippfehler, die der Teilstring meist schon abfängt) |
| Abgleich und Reihenfolge | Teilstring auf den normalisierten Schlüsseln; Rang 1 Präfix, Rang 2 Wortanfang (nach Leerzeichen, Bindestrich, Klammer), Rang 3 Teilstring; innerhalb eines Rangs alphabetisch (die Einträge sind sortiert); höchstens 8 Vorschläge, eine Statuszeile „n Treffer, die ersten 8" | ein Durchlauf über 4135 Einträge kostet unter 0,6 ms (Node, Prototyp), also kein Debounce und kein Index. Verworfen: Sortierung nach Dokumentzahl (versteckt die Straße, die man meint, hinter trefferstarken Orten) |
| Bedienelement | eigene Vorschlagsliste nach dem APG-Muster „Editable Combobox with List Autocomplete": `<input role="combobox" aria-autocomplete="list" aria-expanded aria-controls="suche-liste" aria-activedescendant>`, `<ul id="suche-liste" role="listbox">` mit `<li role="option" aria-selected>`; Pfeil ab/auf, Enter, Escape, Alt+Pfeil ab, Pointer; Fokus bleibt im Feld; Statuszeile `aria-live="polite"`; ein `<form>` drumherum, damit Enter ohne Liste die erste Übereinstimmung nimmt | `<datalist>` verworfen: der Abgleich ist Browsersache (Chrome Teilstring, Safari Präfix, Firefox anders), keine Normalisierung (`str.` gegen `straße`), kaum gestaltbar, mit 5841 Optionen in der Seite nicht kleiner, und für das Ergebnis bräuchte es ohnehin das JSON mit den Bezirken. Kosten: rund 70 Zeilen JavaScript für Liste und Tastatur |
| Ergebnisdarstellung | ein `<section id="suche">` zwischen „Kernzahlen" und „Karte": Feld, Liste, darunter ein Ergebnisblock (`aria-live="polite"`): Begriff, Art, Wahlbezirke als Schaltflächen (Klick markiert genau diesen Bezirk in Karte, Tabelle und Streudiagramm, wie heute ein Klick auf die Karte), „n Dokumente mit Treffer" mit Schaltfläche „Dokumente zeigen", Hinweis „auf der Karte markiert" mit Sprunglink `#karte`. Der Block markiert sofort alle Bezirke des Begriffs; bei einem Ort setzt er einen Marker-Kreis an die Koordinaten des Orts | die Bezirksnamen kommen aus der Tabelle (`#districts tr[data-id]`), die Koordinaten der Orte aus den vorhandenen `<circle data-name data-district>` der Karte; die Seite braucht dafür kein weiteres Byte an Daten. Verworfen: Ergebnis in der Karten-Legende (zu eng), Ergebnis im Dialog (versteckt die Karte) |
| Mehrfachmarkierung | `select` im Basis-JavaScript nimmt künftig eine Zahl *oder* ein Array und ein Flag `scroll` (die Suche scrollt nicht zur Tabellenzeile); der Ort-Marker ist ein `<circle class="suchmarke">` in einer per JavaScript erzeugten Gruppe `<g class="suchmarken">` am Ende des SVG | die Ebene `.pois` ist standardmäßig `display: none`, ein Kind kann das nicht überstimmen; eine eigene Gruppe ist immer sichtbar und kommt mit `--selected` als Farbe aus. Bestehende Klick-Handler ändern sich nicht |
| Schreibweise der Anzeige | kleingeschrieben, wie alle Begriffe auf der Seite (Schaltflächen, Tabellen); Wahlbezirksnamen in Originalschreibweise | die Originalschreibweise der Straßen (`wahlbezirke_strassen.parquet`, z. B. „Adlerstraße") und Orte (`wikidata_vis.parquet`) würde rund 90 KB mehr kosten und zwei Schreibweisen auf einer Seite mischen. § 8, Frage 1 |
| Dialog mit beiden Schreibweisen | `showDocuments` nimmt künftig eine Liste von Begriffen und einen Titel; die Indizes aus `dokumente.json` werden vereinigt und aufsteigend sortiert (die Dokumentliste ist neueste zuerst, also bleibt die Reihenfolge) | die Varianten erzeugt das JavaScript nach derselben Regel aus dem Payload; fehlt eine Variante in `dokumente.json`, wird sie übergangen. Bestehende Schaltflächen rufen weiter `showDocuments([begriff], begriff)` |
| Teilbare Adresse | `#suche=<begriff>` (URL-kodiert) setzt beim Laden das Feld und führt die Suche aus; eine Auswahl schreibt den Hash mit `history.replaceState`; Escape leert Feld und Hash. Ungültige Kodierung wird abgefangen (`decodeURIComponent` wirft) | kostet zehn Zeilen und macht die Browser-Prüfung aus `file://` per Screenshot möglich (§ 5, Stufe D), weil der Ergebnisblock ohne Tippen entsteht. Verworfen: `?q=` (Query-Strings laden die Seite neu und stören den Pages-Cache nicht, aber `#` reicht und bleibt lokal) |
| Python-Seite | neues Modul `report/search.py`: reine Funktionen von Frames zu `SearchEntry` (frozen dataclass) mit deal-Verträgen an der Batch-Grenze; `ReportModel.search` trägt die Einträge, `render_report` macht daraus das JSON. Die Abkürzungsregel wird zur Konstante `STREET_ABBREVIATIONS` in `search/dictionary.py`, aus der `normalise_terms` *und* der Payload lesen | ein Ort für die Regel; `mypy --strict`, Verträge, hypothesis wie der Rest des Pakets; die Signatur von `render_report(model, visuals)` bleibt, Tests brauchen keine neuen Argumente. Verworfen: Einträge erst in `build.py` zusammensetzen (dann wüsste das Modell nichts davon und die Render-Tests müssten alles nachbauen) |
| Vorlage | die Vorlage wird in Abschnitte zerlegt (Vorschlag für das Fundament der Synergiephase, § 6 unten); fällt das Fundament anders aus, kommen drei markierte Einfügestellen in die heutige Vorlage | fünf Optionen (2, 3, 5, 6, 7, 8) erweitern dieselbe Datei; Konflikte sollen Einzeiler bleiben |
| Abhängigkeiten | keine neue | reines JavaScript ohne Bibliothek, Python mit Polars und deal wie bisher; `nox -s deps` bleibt unberührt |

## 3. Datenlage (Stand 2026-10-11, Worktree `08-suche`, Spalten exakt)

Alles liegt nach `georep run` unter `data/processed/`, `data/external/` und `data/site/`; die Mini-Fixture
(`tests/fixtures/mini/`) hat dieselben Spalten mit 3 Wahlbezirken.

| Datei | Zeilen | Spalten | Größe | Für die Suche |
|---|---|---|---|---|
| `processed/combined_searchdict.parquet` | 41 | `wahlkreis_id` Int64, `suchbegriffe` List(String) | 44 255 B | 6991 Paare (Bezirk, Begriff), 5841 verschiedene Begriffe; 923 Begriffe in mehr als einem Bezirk, höchstens 7 (`münchener straße`: 15, 16, 18, 35, 36, 37, 39); 1705 Paare `straße`/`str.`; Zeichen: Kleinbuchstaben, Ziffern, `ßäöüéóō`, `-./()'&"„“’–`, Leerzeichen; Länge 4 bis 89 Zeichen, im Mittel 16,3; `schulweg` (`hide_in_display`) ist dabei |
| `processed/inverted_index.parquet` | 5841 | `suchbegriffe` String, `paper_ids` List(String), `anzahl_treffer` Int64 | 152 045 B | 3040 Begriffe mit Treffer; `paper_ids` für die Vereinigung der Schreibweisen |
| `processed/wahlbezirke_strassen.parquet` | 41 | `wahlkreis_id` Int64, `suchbegriffe` List(String) | 25 413 B | 3589 Namen in Originalschreibweise („Adlerstraße"), 2897 verschiedene kleingeschrieben; alle im Wörterbuch; Quelle der Art `s` |
| `processed/wikidata_vis.parquet` | 1309 | `label` String, `wahlkreis_id` Int64, `lon` Float64, `lat` Float64 | 30 819 B | 1307 verschiedene Labels kleingeschrieben, alle im Wörterbuch; Quelle der Art `o`; 68 Begriffe sind Straße *und* Ort („aachener straße", „burgplatz") |
| `processed/wahlbezirke_auswertung.parquet` | 41 | `wahlkreis_id`, `anzahl_treffer` Int64 und die Wählerspalten (§ 3 des Berichtsplans) | 135 841 B | `anzahl_treffer` je Bezirk für die Einträge der Art `w` |
| `external/Stimmbezirke_2025.geojson` | 306 Features | `Kommunalwahlbezirk Nr.`, `Kommunalwahlbezirk Name`, `Stadtteil Name`, … | 7 927 291 B | 41 Wahlbezirksnamen (über `read_precincts` und `district_names`, schon im Modell); 50 Stadtteile, 23 davon in mehreren Wahlbezirken, höchstens 4 (Pempelfort: 1, 2, 3, 4) — noch nicht gelesen, § 8 Frage 4 |
| `site/index.html` | | | 686 088 B, gzip 98 346 B | Zusammensetzung: Karten-SVG 252 393 B (davon die 1309 Orte als `<circle>` mit `<title>` 205 004 B, die 41 Flächen 45 650 B), Abschnitt „Begriffe" 344 522 B (4211 Begriffs-Schaltflächen), Tabelle je Wahlbezirk 28 836 B, Streudiagramm 23 909 B, Downloads 13 694 B, CSS 6953 B, JavaScript 7024 B |
| `site/data/dokumente.json` | 11 041 Dokumente, 3039 Begriffe | `version`, `generated_at`, `fields` (`link, datum, drucksache, titel, art`), `base`, `documents` (Listen), `terms` (Begriff → Indizes) | 2 148 551 B | unverändert; der Dialog vereinigt künftig die Indizes mehrerer Begriffe |

Die Suchdaten, aus den ersten vier Tabellen gerechnet (ohne `schulweg`): **4135 Einträge** (2828 Straßen, 1239
Orte, 68 beides), 1618 davon ohne Dokument; dazu 41 Wahlbezirksnamen. Kodierungen, gemessen als kompaktes JSON
(`ensure_ascii=False`, ohne Leerzeichen):

| Variante | Byte | gzip | Bemerkung |
|---|---|---|---|
| A: alle 5840 Begriffe einzeln `[begriff, bezirke, treffer]` | 170 829 | 42 866 | doppelte Vorschläge je Straße |
| **B: zusammengezogen `[begriff, bezirke, dokumente, art]`** | **141 835** | **35 885** | gewählt; lesbar, ein Eintrag je Zeile |
| C: spaltenweise (`t`, `d`, `h`, `k` als parallele Listen) | 133 589 | 33 412 | 8 KB weniger, aber je Eintrag vier Indexzugriffe; Reserve, falls das Budget knapp wird |
| D: Text, eine Zeile je Eintrag mit Tabulator | 108 747 | 34 210 | gzip gleich, eigener Parser; verworfen |

Mit B und rund 9 KB für Abschnitt, CSS und JavaScript liegt `index.html` bei rund 837 KB (gzip rund 135 KB),
660 KB unter dem Budget von 1,5 MB (§ 2 des Meta-Plans). Der Payload enthält heute kein `</`; `_json_for_script`
schützt trotzdem. Herkunft und Lizenz der Daten ändern sich nicht (OSM ODbL, Wikidata CC0, Open-Data-Portal
DL-DE); die Seite nennt sie schon im Fuß.

Mini-Fixture: 3 Wahlbezirke (1, 10, 38), 1054 Begriffe, 172 mit Treffer, 493 Orte; Wahlbezirksnamen
„Altstadt, Carlstadt, Hofgarten", „Flingern Süd", „Hassels, Paulsmühle".

## 4. Berührungspunkte im bestehenden Code

| Datei | Funktion oder Stelle | Was sich ändert |
|---|---|---|
| `src/georep/search/dictionary.py` | `normalise_terms` | das Literal `"straße"`/`"str."` wird zur Modulkonstante `STREET_ABBREVIATIONS: tuple[tuple[str, str], ...] = (("straße", "str."),)`; `normalise_terms` liest daraus (Schleife über die Paare, heute ein Paar). Reines Refactoring, eigener Commit, Golden Master unverändert |
| `src/georep/report/search.py` (neu) | `SearchEntry(term, districts, documents, kind)`; `KIND_LABELS = {"s": "Straße", "o": "Ort", "w": "Wahlbezirk"}`; `canonical_term(term, abbreviations) -> str` (`deal.pure`: ersetzt jede Abkürzung durch die Langform, idempotent); `search_entries(dictionary, index, streets, pois, results, names, hidden, abbreviations) -> tuple[SearchEntry, ...]`; `search_payload(entries, abbreviations, version) -> dict[str, object]` | der ganze neue Python-Code; Verträge: pre `has_columns` auf allen vier Frames; post Einträge nach `(term, kind)` sortiert und eindeutig, `districts` sortiert, nicht leer, nur aus dem Wörterbuch beziehungsweise `names`, `documents >= 0`, `kind` nur aus `s`, `o`, `w` in dieser Reihenfolge; ensure: jeder nicht versteckte Begriff des Wörterbuchs liegt unter genau einem Eintrag (sein kanonischer), und `documents` eines Eintrags ist höchstens die Summe und mindestens das Maximum der `anzahl_treffer` seiner Schreibweisen |
| `src/georep/report/model.py` | `ReportModel` bekommt `search: tuple[SearchEntry, ...]`; `build_report_model` liest zusätzlich `layout.streets_by_district` und `layout.pois_table` (beide schon Eingaben des Schritts `report`) und ruft `search_entries` | ein Feld, ein Aufruf; `district_names(precincts)` und `hidden` liegen dort schon vor |
| `src/georep/report/render.py` | `render_report` | übergibt `search_json=_json_for_script(search_payload(...))` an die Vorlage (die Funktion steht heute unter `render_report`, sie wandert davor); die Nachbedingungen (Doctype, `lang="de"`, `ALLOWED_LINKS`) bleiben, denn die Suche setzt keinen Link nach außen |
| `src/georep/report/templates/report.html.j2` | Abschnitt, CSS, JavaScript, JSON-Block | neuer `<section id="suche">` nach `#kernzahlen`; rund 25 Zeilen CSS (Liste, Option, aktive Option, Ergebnisblock, Marker) und rund 150 Zeilen JavaScript (Normalisierung, Abgleich, Combobox, Ergebnis, Markierung, Hash). Im Basis-JavaScript: `select(ids, scroll)` statt `select(id)`, `showDocuments(terms, title)` statt `showDocuments(term)`, und ein Objekt `georep` (`select`, `showDocuments`, `rows`) als Schnittstelle für Abschnitts-Skripte. Mit dem Abschnittsmechanismus aus § 6 liegt das Neue in `templates/sections/15-suche.html.j2`, `15-suche.css`, `15-suche.js` |
| `src/georep/report/build.py` | `build_site` | nichts Zwingendes; die Einträge entstehen im Modell. `SiteSummary.line()` bleibt |
| `tests/unit/test_report_search.py` (neu) | | kleine Frames von Hand: Zusammenziehen der Varianten, Vereinigung der `paper_ids`, Arten `s`/`o`/`so`/`w`, versteckter Begriff fehlt, ein `str.`-Begriff ohne `straße`-Zwilling bleibt eigener Eintrag, Bezirke sortiert, Vertragsverletzung mit Gegenbeispiel (Begriff mit Komma, fehlender Bezirk in `names`) |
| `tests/property/test_search_props.py` (neu) | | hypothesis: `canonical_term` idempotent, kleingeschrieben bleibt kleingeschrieben, enthält keine Abkürzung mehr; für zufällige Wörterbücher (Strategie aus `test_dictionary_props.py`) deckt `search_entries` jeden Begriff genau einmal ab und die Summe der Dokumente liegt zwischen Maximum und Summe; `deal.cases` auf `canonical_term` |
| `tests/unit/test_report_render.py` | `page`-Fixture, neue Tests | das JSON lässt sich aus `<script id="suche-daten">` zurücklesen (`json.loads` nach `<\/` → `</`) und entspricht `search_payload(model.search)`; ein Begriff `x</script><b>` im Modell steht als `<\/script>` in der Seite; `role="combobox"`, `aria-controls` zeigt auf eine vorhandene `id`, `role="listbox"`, `<label for>`; `tags["svg"] == 2` bleibt (keine Icons) |
| `tests/unit/test_report_model.py` | | auf der Mini-Fixture: 3 Einträge der Art `w`, Zahl der Einträge gleich Zahl der kanonischen Begriffe, ein `münchener straße`-artiges Paar zusammengezogen (im Mini: `adlerstraße`) |
| `tests/unit/test_report_js_fold.py` (neu, `skipif` ohne `node`) | | zieht `function fold` und `foldAscii` aus der Vorlage, lässt sie in Node über alle Begriffe der Mini-Fixture laufen und vergleicht mit dem Python-Spiegel `georep.report.search.fold` (nur für diesen Test und die Kollisionsprüfung); `node` ist auf Konrads Rechner (v22) und auf `ubuntu-latest` vorhanden |
| `tests/golden/test_pipeline.py` | `test_pipeline_reproduces_the_thesis_results` | `site_index.stat().st_size < 1_500_000` statt `3_000_000` (das Budget aus § 2 des Meta-Plans; geteilte Zeile, § 8 Frage 8) und `"suche-daten" in page` |
| `tests/unit/__snapshots__/` | | keine neuen Snapshots; der Download-Tabellen-Snapshot bleibt gleich, weil keine Datei dazukommt |
| `docs/architecture.md` | Modultabelle `report/`, Absatz „Berichtsseite" | `search` in der Tabelle; ein Satz zur Suche und zum Abschnittsmechanismus |
| `docs/decisions.md` | neuer Punkt | „Suche inline, kanonische Begriffe, eigene Combobox" mit den verworfenen Alternativen aus § 2 |
| `README.md`, `CHANGELOG.md` (Unreleased), `STATUS.md` | Abschnitt „Berichtsseite" | je ein Satz; Zahlen (Seite rund 840 KB, 4135 Einträge) |
| `.claude/launch.json` (gitignored, im Worktree neu anlegen) | Konfiguration `site` | `python3 -m http.server 8777 --directory <Worktree>/data/site`; Vorlage im Hauptklon, Pfad anpassen |

Nicht berührt: `pipeline.py` (Eingaben und Ausgaben des Schritts `report` bleiben; der Stamp wechselt über die
Code-Version), `charts.py` (die Marker-Gruppe erzeugt das JavaScript), `documents.py`, `geometry.py`,
`settings.py` (§ 9 nennt den späteren Schlüssel), `map.html.j2`.

## 5. Bauplan in Stufen

Jede Stufe ein bis drei Commits, nach jedem `uv run nox` (im Alltag `uv run pytest -n 2 tests/unit tests/property`),
Verhaltensänderung zuerst mit rotem Test. Tests arbeiten in `tmp_path` über die Fixture `mini_run`. Geschätzter
Aufwand insgesamt: 9 bis 12 Stunden Agentenzeit, 8 bis 9 Commits.

### Stufe A: Sucheinträge in Python (2 bis 3 h, 3 Commits)

1. Refactoring-Commit: `STREET_ABBREVIATIONS` in `search/dictionary.py`, `normalise_terms` liest daraus.
   Abnahme: `uv run nox` grün, `uv run pytest -m slow` grün, `test_two_runs_write_identical_parquet` grün (das
   Wörterbuch ist byteidentisch).
2. Roter Test, dann `report/search.py`: `canonical_term`, `search_entries`, `search_payload`, `fold`
   (Python-Spiegel), Verträge wie in § 4, Prädikate nach `georep.contracts`, wo sie allgemein sind
   (`sorted_unique` auf dem Frame der Einträge vor dem Umbau in dataclasses). Payload-Schema, dokumentiert im
   Modul-Docstring:
   ```json
   {"version": "0.10.0", "abbreviations": [["straße", "str."]],
    "kinds": {"s": "Straße", "o": "Ort", "w": "Wahlbezirk"},
    "entries": [["aachener straße", [14, 15, 16, 18], 61, "so"], ["Altstadt, Carlstadt, Hofgarten", [1], 1894, "w"]]}
   ```
   Abnahme: `tests/unit/test_report_search.py` und `tests/property/test_search_props.py` grün; auf der Mini-Fixture
   liefert `search_entries` genau so viele Einträge der Art `s`/`o` wie kanonische Begriffe ohne `schulweg` plus
   3 der Art `w`; `mypy --strict` ohne Befund; `nox -s verify` nimmt `georep.report.search.canonical_term` in
   `VERIFY_TARGETS` auf.
3. `ReportModel.search`, `build_report_model` ruft `search_entries`; Test in `test_report_model.py`.
   Abnahme: `georep run report --force` auf der Referenz zählt 4176 Einträge (4135 plus 41; Zahl im Test der
   Stufe D), Laufzeit des Schritts `report` bleibt unter 1,5 s (`georep profile report` vorher und nachher, Zahlen
   nach `docs/profiling/README.md`).

### Stufe B: Abschnitt und Daten in der Vorlage (1,5 bis 2 h, 2 Commits)

1. Roter Test in `test_report_render.py` (JSON-Block vorhanden und rücklesbar, Escaping von `</script>`,
   Combobox-Attribute), dann `render_report` mit `search_json` und der Abschnitt in der Vorlage: `<h2>Straße oder
   Ort suchen</h2>`, `<form role="search">`, `<label for="suche-feld">`, das Feld mit allen ARIA-Attributen,
   `<ul id="suche-liste" role="listbox" hidden>`, `<p id="suche-status" aria-live="polite">`, `<div id="suche-ergebnis"
   aria-live="polite" hidden>`, der `<script id="suche-daten" type="application/json">`-Block, dazu eine Zeile
   „Durchsucht {{ model.search|length|num }} Straßen, Orte und Wahlbezirke; Vorschläge ohne Netz, die Dokumentliste
   braucht einen Webserver." CSS für Liste, aktive Option (`aria-selected="true"`: Hintergrund `color-mix` mit
   `--accent`), Ergebnisblock (`.tile`-Optik), Marker (`fill: none; stroke: var(--selected); stroke-width: 3px`).
   Abnahme: Tests grün; `page.count("<script") == 2` (JSON und Basis-Skript) beziehungsweise plus Abschnitts-Skripte
   mit dem Mechanismus aus § 6; `tags["svg"] == 2`; hell und dunkel per headless Chrome (§ 8.4) angesehen, der
   Abschnitt ist ohne JavaScript ein leeres, beschriftetes Feld.
2. Falls das Fundament aus § 6 auf `main` liegt: die drei Dateien unter `templates/sections/`; sonst die drei
   markierten Einfügestellen in `report.html.j2`. Abnahme: `uv run nox` grün, `git diff --stat` zeigt für die
   Vorlage nur die Einfügestellen.

### Stufe C: JavaScript (4 bis 5 h, 2 bis 3 Commits)

1. Basis-Skript: `select(ids, scroll)` (Zahl oder Array; `scroll` Standard `true` für die alten Aufrufer),
   `showDocuments(terms, title)` mit Vereinigung, Objekt `georep` als Schnittstelle. Abnahme: im Browser (§ 8.4,
   Port 8777) verhalten sich Karte, Tabelle, Streudiagramm und Dialog wie vor der Änderung (Klick, Enter,
   Umschalter, Sortierung, Dialog mit „Lade …", Schließen).
2. Suche: `fold`, `foldAscii`, Schlüssel beim Laden, `search(query, limit)` mit drei Rängen; Combobox
   (`input` → Liste neu bauen, `aria-expanded`, `aria-activedescendant` auf `suche-opt-<i>`; Tasten: Pfeil ab/auf
   mit Umlauf, Enter wählt, Escape schließt und beim zweiten Mal leert, Alt+Pfeil ab öffnet, Tab schließt;
   `pointerdown` auf eine Option wählt, ohne den Fokus zu verlieren); Statuszeile „8 von 113 Vorschlägen" oder
   „keine Vorschläge"; Ergebnisblock aus Daten per `textContent` und `createElement`, nie `innerHTML`;
   Markierung: `georep.select(bezirke, false)`; bei Art `o` Marker aus den `<circle>`-Koordinaten des ersten
   passenden `data-name` (kleingeschrieben verglichen), ohne `.pois`-Gruppe kein Marker und kein Fehler; bei
   Art `w` kein Dialog-Knopf, Hinweis auf „Begriffe je Wahlbezirk"; Hash lesen beim Laden und schreiben bei Auswahl.
   Abnahme in der Browser-Ansicht mit `javascript_tool` (Skriptfolge im Scratchpad ablegen, damit der Supervisor sie
   wiederholen kann): Eingabe „münch" liefert zwei Optionen, Pfeil ab und Enter wählt „münchener straße", sieben
   `path.district.selected` und sieben `tr.selected`, Ergebnisblock nennt 7 Bezirke mit Namen und „141 Dokumente";
   „Dokumente zeigen" öffnet den Dialog mit 141 Einträgen (Vereinigung beider Schreibweisen); „Hofgarten" markiert
   Bezirk 1 und setzt einen Marker; „Benrath" liefert den Wahlbezirk 39 als Option der Art Wahlbezirk; „suedstr"
   findet „südstraße"; Escape schließt die Liste, erneut Escape leert Feld, Ergebnis, Markierung und Hash;
   `index.html#suche=hofgarten` zeigt das Ergebnis beim Laden; keine Konsolenfehler (`read_console_messages`).
3. `tests/unit/test_report_js_fold.py` (Node, sonst `skip`). Abnahme: für alle Begriffe der Mini-Fixture stimmen
   JavaScript und Python überein; keine zwei kanonischen Begriffe derselben Art fallen nach `fold` zusammen (auf
   der Referenz als `slow`-Variante).

### Stufe D: Budget, Prüfung, Dokumentation (1,5 bis 2 h, 1 bis 2 Commits)

1. `test_pipeline.py`: Budget `< 1_500_000` und `"suche-daten" in page`; eine Zahl im Test, die den Umfang
   festhält (`page.count('role="option"') == 0` vor Eingabe, Einträge im JSON `== 4176`). Abnahme:
   `uv run pytest -m slow` grün, `ls -l data/site/index.html` unter 900 000 Byte.
2. Headless Chrome (§ 8.4): `light.png` und `dark.png` der Seite mit `#suche=m%C3%BCnchener%20stra%C3%9Fe` aus
   `file://` (das beweist den `file://`-Pfad ohne Tippen), Streifen ansehen; Fokusring und Kontrast der aktiven
   Option in beiden Modi prüfen (WCAG AA, Verhältnis mit dem Validator der Skill `dataviz` oder von Hand).
3. Doku: `architecture.md`, `decisions.md`, README, CHANGELOG „Unreleased", STATUS (Zahlen vom Lauf), dieser Plan
   bekommt den Status „im Review". Abnahme: `uv run nox`, `uv run pytest -m slow`, `uv run nox -s bench` grün;
   `grep -rn "Düsseldorf\|0015" src/georep/report/search.py` leer; `georep run` zweimal hintereinander, der
   zweite Lauf überspringt `report` („aktuell").

## 6. Auswirkung auf die Berichtsseite

- **Abschnitt**: neu `<section id="suche">` zwischen „Kernzahlen" und „Karte"; das Suchfeld ist das erste
  Bedienelement der Seite. Die Karte erhält beim Suchen Markierungen (bestehende Klasse `selected`, neue Gruppe
  `suchmarken`), sonst ändert sich kein Abschnitt. Der Dialog bleibt, kann aber mehrere Begriffe vereinigen.
- **Größe**: plus 141 835 B Daten und rund 9 000 B Markup, CSS, JavaScript: `index.html` rund 837 KB
  (gzip rund 135 KB) statt 686 KB; Budget 1,5 MB, Rest rund 660 KB für die anderen Optionen. `karte.html`,
  `data/` unverändert; keine neue Download-Datei. Hebel, falls die Synergiephase sparen muss: Variante C
  (−8 KB), `<title>` in den 1309 Orts-Kreisen (der Tooltip trägt dieselbe Information; rund −60 KB; betrifft
  `charts.py`, nicht diese Option).
- **Unterseite**: nein.
- **Abschnittsmechanismus (Vorschlag für das Fundament der Synergiephase)**: `report.html.j2` wird Rahmen
  (`<head>`, Kopf, Fuß, Dialog, Tooltip, Basis-JavaScript mit `georep`-Objekt) und zieht die Abschnitte aus
  `templates/sections/NN-name.html.j2` in Nummernfolge ein, je mit optionalen Geschwistern `NN-name.css` und
  `NN-name.js`, die in den `<style>`- beziehungsweise einen eigenen `<script>`-Block laufen; `render.py` listet
  das Verzeichnis über `importlib.resources` (`uv_build` packt Nicht-Python-Dateien unter `src/georep/` mit).
  Die heutigen Abschnitte werden `10-kernzahlen`, `20-karte`, `30-zusammenhang`, `40-wahlbezirke`, `50-begriffe`,
  `60-methode`, `70-downloads`; die Suche wird `15-suche`. Eine neue Option legt dann nur neue Dateien an, und
  die Nummer bestimmt die Position; Konflikte entstehen nur noch, wenn zwei Optionen denselben Abschnitt ändern
  (5 ändert `20-karte`; 3 und 6 kommen als `35-…`, 2 und 7 als eigene Nummern). Jinja-`{% include %}` arbeitet mit
  Autoescape wie die Hauptvorlage; `{{ }}` in `.js`-Teilen nur über `|safe` nach `_json_for_script`. Fallback ohne
  Fundament: drei Kommentar-Marken `{# abschnitt:suche #}`, `{# css:suche #}`, `{# js:suche #}` in der heutigen
  Vorlage; der Konflikt bleibt ein Einzeiler je Stelle.

## 7. Risiken und Fallstricke

- **Drift zwischen JavaScript und Wörterbuch.** Die Regel `straße`/`str.` darf nur an einer Stelle stehen
  (`STREET_ABBREVIATIONS`), das JavaScript liest sie aus dem Payload; der Node-Test (Stufe C.3) vergleicht `fold`
  mit dem Python-Spiegel. Ohne `node` läuft der Test nicht; dann bleibt die Browser-Prüfung.
- **Autoescape und JSON.** Das JSON muss durch `_json_for_script` (`</` → `<\/`) und mit `|safe` in die Vorlage;
  ein `{{ search_json }}` ohne `|safe` würde Anführungszeichen entwerten und das Skript stumm brechen. Test mit
  einem Begriff `x</script><b>` wie bei `karte.html`.
- **`select` ändert Signatur.** Alte Aufrufer übergeben eine Zahl; das neue `select` muss beides nehmen und
  weiter scrollen, sonst bricht die Klick-Markierung von Karte und Tabelle. Vor dem Umbau die Browser-Prüfung der
  heutigen Funktionen durchführen (Stufe C.1).
- **`aria-activedescendant`** wird von Screenreadern unterschiedlich gelesen; das APG-Muster ist die Referenz,
  mehr lässt sich hier nicht prüfen. Der Fokus bleibt immer im Feld; die Optionen sind nicht fokussierbar.
- **Orte ohne Kreis.** Die `.pois`-Gruppe fehlt, wenn `visuals.pois == 0` (Render-Tests); mehrere Kreise mit
  gleichem Namen sind möglich („Itter": Stadtteil und Bach). Das JavaScript nimmt alle passenden Kreise, keinen
  oder mehrere, ohne Fehler.
- **`str.`-Begriffe ohne `straße`-Zwilling** gibt es auf der Referenz nicht (geprüft), in anderen Städten
  vielleicht (ein OSM-Name mit „Str." im Original). `search_entries` lässt solche Begriffe als eigene Einträge
  stehen; das JavaScript übergeht Varianten, die in `dokumente.json` fehlen.
- **Die Zahl im Ergebnis** ist die Vereinigung beider Schreibweisen und weicht in 256 Fällen von den Zahlen der
  Begriffs-Schaltflächen ab; der Ergebnisblock sagt „beide Schreibweisen", und `decisions.md` erklärt es.
- **Acht Worktrees, ein Port.** § 8.4 nennt 8777 für die Vorschau; laufen mehrere Agenten gleichzeitig, kollidiert
  der Port. Vorschlag für die Synergiephase: `8700 + NN` je Option (hier 8708); bis dahin 8777 und bei
  „Address already in use" 8708.
- **Vorlage als Konfliktherd.** Ohne Fundament ändern sechs Optionen dieselbe Datei; die Einfügestellen aus § 6
  halten den Konflikt klein, der Rebase vor dem Merge bleibt trotzdem Handarbeit des Supervisors.
- **Hash und `file://`.** `history.replaceState` funktioniert auch unter `file://`; `decodeURIComponent` wirft bei
  kaputter Kodierung, darum `try`/`catch` und leeres Feld.
- **Stamp und Fingerprint.** Keine Settings ändern sich, der Schritt `report` läuft wegen der Code-Version neu;
  das Wörterbuch bleibt byteidentisch (Stufe A.1 prüft es), sonst wäre A.1 kein Refactoring.
- **Laufzeit.** `search_entries` ist Polars über 6991 Paare, erwartet unter 50 ms; `georep profile report`
  vorher und nachher, Zahl ins Profiling-README. Im Browser: 4135 Einträge, zwei Schlüssel, unter 1 ms je Tastendruck.
- **Begriffe mit Sonderzeichen** (`auf'm hennekamp`, `„…“`, `&`): alle Ausgaben per `textContent`, keine
  `data-`-Attribute mit Begriffen im neuen Code, keine `innerHTML`.

## 8. Offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | Warum sie zählt | Annahme |
|---|---|---|---|
| 1 | Sollen Straßen und Orte in der Suche in Originalschreibweise erscheinen („Adlerstraße") statt kleingeschrieben wie überall sonst auf der Seite? | rund 90 KB mehr, zwei Schreibweisen auf einer Seite; umgekehrt liest sich Originalschreibweise besser | kleingeschrieben, Wahlbezirksnamen in Originalschreibweise |
| 2 | Ein Vorschlag je Straße mit Vereinigung der Dokumente beider Schreibweisen, oder beide Schreibweisen getrennt wie die Schaltflächen? | Zahlen im Ergebnis weichen in 256 Fällen von den Schaltflächen ab | zusammengezogen, mit dem Hinweis „beide Schreibweisen" |
| 3 | Platz der Suche: eigener Abschnitt vor der Karte, oder im Kopf über den Kernzahlen? | erstes Bedienelement der Seite; der Kopf ist heute Text | eigener Abschnitt zwischen Kernzahlen und Karte |
| 4 | Sollen auch die 50 Stadtteile (`Stadtteil Name` je Stimmbezirk, 23 über mehrere Wahlbezirke) Einträge werden? | braucht die Zuordnung Stadtteil zu Wahlbezirk, die auch Optionen 2, 3 und 5 brauchen (Fundament); allein gebaut gäbe es drei Versionen davon | zunächst nur die 41 Wahlbezirksnamen; Stadtteile, sobald der Crosswalk auf `main` liegt, als Art `t` in einem späteren Commit |
| 5 | Teilbare Adresse `#suche=…` erwünscht? | zehn Zeilen; verändert den Hash beim Suchen | ja |
| 6 | Kommt der Abschnittsmechanismus (§ 6) als Fundament der Synergiephase? | entscheidet, ob die Suche drei neue Dateien oder drei Einfügestellen in der Vorlage ist | ja; sonst der Fallback |
| 7 | Port der Vorschau je Worktree | acht Agenten, ein Port 8777 | 8777; bei Kollision 8708 |
| 8 | Wer setzt das Budget `< 1_500_000` in `test_pipeline.py`? | geteilte Zeile in einem Test, den jede Option berührt | diese Option setzt sie; der Supervisor löst den Konflikt zugunsten derselben Zahl |

Keine Frage blockiert; alle Annahmen tragen bis zum Merge.

## 9. Vorbereitung für Option 10

- **Konfigurierbar wird** die Abkürzungsregel: heute Konstante `STREET_ABBREVIATIONS` in `search/dictionary.py`,
  aus der Wörterbuch und Payload lesen; später ein Settings-Schlüssel `[search] abbreviations = [["straße", "str."]]`
  (Default gleich der Konstante, damit der Fingerprint und der Golden Master sich nicht ändern; andere Sprachen
  tragen andere Paare, etwa `[["rue", "r."]]`). Das JavaScript ist schon jetzt datengetrieben: es kennt keine
  deutsche Regel, nur die Paare aus dem Payload. Die Umlaut-Faltung (`ä` → `ae`) ist sprachspezifisch und bleibt
  im JavaScript als zweiter Schlüssel; sie schadet keiner anderen Sprache.
- **Modulgrenze**: `report/search.py` ist eine reine Funktion von vier Frames und einer Namenstabelle zu
  `SearchEntry`, ohne HTML, ohne Dateizugriff, ohne Stadtwissen; `render.py` kennt nur das Payload-Schema;
  das JavaScript nur das JSON und die DOM-Verträge der Seite (`#districts tr[data-id]`, `.pois circle[data-name]`,
  `georep.select`, `georep.showDocuments`). Diese vier Verträge stehen als Kommentar am Kopf des Abschnitts-Skripts,
  damit ein Umbau der Karte sie findet. Die Arten `s`/`o`/`w` kommen aus den Quelltabellen, ihre Beschriftungen
  (`KIND_LABELS`) sind die einzigen deutschen Strings im Python-Teil und wandern mit Option 10 in die Vorlage.
- **Kein Düsseldorf-Literal** im neuen Code (`grep` in Stufe D); die Wahlbezirksnamen kommen aus dem GeoJSON über
  `settings.columns.district_name`.
- **Payload trägt `version`**, damit eine spätere Änderung des Schemas (etwa Stadtteile als Art `t`, Variante C)
  erkennbar bleibt.

## 10. Änderungen durch die Synergiephase

Stand 2026-10-12, geschrieben vom Supervisor nach [00-synergien.md](00-synergien.md). Das Fundament liegt auf
`main` (Commits `d7df0ed` bis `b8e44b1`, Branch rebased); was unten steht, gilt vor den Stufen in § 5. Für alle
Optionen (00-synergien.md, § 2 und § 5):

- **Vorlage**: `report.html.j2` ist Rahmen; ein neuer Abschnitt ist eine neue Datei
  `src/georep/report/templates/sections/NN-name.html.j2` (Nummern in 00-synergien.md § 5.1), optional mit
  `NN-name.css` und `NN-name.js` daneben; `render.sections()` bindet sie in Nummernfolge ein. Das Makro
  `term` kommt aus `templates/macros.html.j2` (`{% from "macros.html.j2" import term %}`). Ein Abschnitt, der
  nur mit einem Modellteil existiert, steht in `{% if model.<teil> %} … {% endif %}`, das Feld in `ReportModel`
  hat Default `None` und steht am Ende der Klasse.
- **JavaScript**: Abschnitts-Skripte sprechen mit `window.georep` (`select(ids, scroll)` für Zahl, Array
  oder `null`; `showDocuments(terms, title)` mit mehreren Begriffen; `rows`). Der Kartenumschalter ist
  generisch: Radio `input[name="metric"]` mit `value`, Attribut `data-class-<value>` je Fläche
  (`charts.choropleth(..., extra_classes={"<value>": classification})`), Legende `.legend#legend-<value>`.
- **Tabellen**: jede neue veröffentlichte Tabelle ist ein `PublishedTable`-Eintrag am Ende von `TABLES` in
  `src/georep/report/tables.py` (Name, Pfad-Lambda, Beschreibung, Spaltendoku, CSV-Regeln, `optional`);
  `published_tables`, `COLUMN_DOCS`, `DESCRIPTIONS` und `export.csv_plan` gibt es nicht mehr.
- **Regression**: `analysis.regression.regression_pair(frame, exclude, *, x, y, y_scale)` rechnet beide
  Spalten von Tabelle 5 für jede Kennzahlspalte; die Ausreißer kommen aus `settings.analysis.exclude_districts`
  (`defaults.toml`, `[analysis]`), `OUTLIERS` gibt es nicht mehr.
- **Settings**: neue Tabellen am Ende von `defaults.toml` in einem Block `# --- Option NN`, neue Modelle vor
  `class Settings`, neue Felder am Ende von `Settings`; Pfade und reine Anzeigewerte aus `fingerprint()`
  ausschließen (Kommentar dort). Neue Layout-Properties am Ende der Klasse vor `runtime_dirs`.
- **Pipeline**: neue Schritte mit Kommentar `# --- Option NN` an der Stelle ihrer Abhängigkeit; neue Eingaben
  von `report` am Ende seines Tupels.
- **Tests**: `test_cli.py`, `test_pipeline.py`, `test_report_build.py` zählen Schritte und Dateien aus
  `build_steps` und dem Register; eigene Erwartungen in eigene Tests. Den Snapshot `test_cli.ambr`
  (`georep steps`) bewusst erneuern, Diff im Commit.
- **Doku**: `decisions.md` neuer Punkt ohne feste Nummer („## Punkt: <Titel> (Option NN, Datum)"; Punkt 21
  ist das Fundament, der Supervisor nummeriert beim Merge); CHANGELOG unter „Unreleased" als eigener Absatz.
- **Vorschau**: lokaler Server auf Port `8700 + NN`; `.claude/launch.json` je Worktree anlegen. Browser-Prüfung
  nach § 8.4 des Meta-Plans.
- **Cache**: `cache_root` ist geteilt; nichts außer `bootstrap` schreibt den Textstore der Hauptperiode.
- **Fragen**: die Antworten und Vorentscheidungen stehen in [fragen.md](fragen.md); neue Fragen in § 8 dieses
  Plans eintragen, der Supervisor sammelt sie.

Für Option 8 im Besonderen:

- **Fundament F1 deckt die Stufen B.2, C.1 und D.1**: der Abschnittsmechanismus, `window.georep` mit
  `select(ids, scroll)` und `showDocuments(terms, title)` sowie das Budget 1,5 MB im slow-Test liegen auf
  `main`. Die Suche ist `sections/15-suche.html.j2`, `15-suche.css`, `15-suche.js`; der JSON-Block
  `<script id="suche-daten">` steht im Abschnitt, das JSON kommt über `render_report` (Variable `search_json`,
  mit `_json_for_script`, das dafür vor `render_report` wandert).
- **Verträge der Seite**, die das Skript nutzt: `#districts tr[data-id]`, `.pois circle[data-name]`,
  `georep.select`, `georep.showDocuments`; als Kommentar am Kopf von `15-suche.js`.
- **Stadtteile als Einträge** (Frage 8.4): `georep.crosswalk.unit_weights` liegt im Fundament; nach dem Merge
  von 05 (`wahlbezirke_stadtbezirke.parquet`) beziehungsweise 03 (Stadtteile) als eigener Commit, wenn Zeit
  bleibt; sonst bleibt es bei den Wahlbezirksnamen.
- **Port** 8708 (00-synergien.md § 5.2).
- **Reihenfolge**: 08 merged als Erste; keine Abhängigkeit von anderen Optionen.
- **Fragen**: alle acht vorentschieden (fragen.md); 8.6, 8.7, 8.8 durch das Fundament erledigt.
