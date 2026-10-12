# Changelog

Eine Zeile pro Änderung aus Sicht eines Nutzers, neueste oben. Versionen sind Git-Tags.

## Unreleased

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
