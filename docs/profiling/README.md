# Profiling und Benchmarks

Erst messen, dann optimieren, dann nachmessen (DEVELOPMENT_PLAN.md § 2). Hier stehen die Werkzeuge und
die datierten Zahlen; die Rohdaten (`.prof`-Dateien, `.benchmarks/`) bleiben lokal, weil sie
rechnerspezifisch sind. Alle Zahlen in dieser Datei stammen von Konrads Rechner (AMD Ryzen 7 5700X,
Python 3.14.6, Linux 6.8 lowlatency), sofern nichts anderes dabeisteht.

## Werkzeuge

| Befehl | Was er tut |
|---|---|
| `uv run georep profile [schritt …]` | führt die Schritte erzwungen unter cProfile aus, schreibt `docs/profiling/<datum>-<schritt>.prof` (gitignored) und druckt die pstats-Tabelle (`--top`, `--sort tottime`); ohne Namen alle Offline-Schritte, Netzschritte nur mit `--online` |
| `uv run nox -s profile -- <schritt>` | dasselbe als nox-Session |
| `uv run snakeviz docs/profiling/<datei>.prof` | Anzeige im Browser |
| `uv run nox -s bench` | pytest-benchmark über `tests/bench/`, speichert jeden Lauf unter `.benchmarks/` (gitignored) und vergleicht mit dem letzten; rot ab 10 % langsamer im Minimum. Der erste Lauf auf einem Rechner legt nur die Baseline an |

Das Minimum ist die Vergleichsstatistik, weil es am wenigsten rauscht; Mittelwert und Maximum tragen GC
und Scheduler mit. cProfile sieht nur Python-Frames: Zeit in Polars oder pypdf erscheint beim
aufrufenden Frame, dafür ist das Profil des echten Schritts die richtige Ebene.

## Benchmarks: Baseline vom 2026-10-11

Eingaben: die Mini-Fixture (`tests/fixtures/mini`: drei Wahlbezirke, 1054 Suchbegriffe, 200 Dokumente
mit zusammen 686 231 Zeichen) und die vier PDF-Fixtures. Zweiter Lauf des Tages, Minimum über alle Runden.

| Benchmark | Eingabe | Minimum |
|---|---|---|
| `aggregate_voters` | Wahlergebnis-CSV der drei Wahlbezirke | 0,63 ms |
| `build_dictionary` | Orte und Straßen von drei Wahlbezirken, 1054 Begriffe | 0,86 ms |
| `hits_and_voter_join` | Wörterbuch × Index × Wähler | 1,30 ms |
| `matcher_build` | 1054 Begriffe in den FlashText-Trie | 1,44 ms |
| `extract_pdf[00519825.pdf]` | 1 Seite, 106 kB | 10,7 ms |
| `extract_pdf[00552781.pdf]` | 1 Seite, 87 kB | 13,2 ms |
| `extract_pdf[00438685.pdf]` | 1 Seite, 59 kB | 20,8 ms |
| `extract_pdf[00439409.pdf]` | 2 Seiten, 44 kB | 41,5 ms |
| `matcher_extract_over_corpus` | 1054 Begriffe über 200 Texte | 46,6 ms |
| `index_step` | `build_index`: dasselbe plus Polars-Frame | 51,4 ms |

Was sich daraus ablesen lässt:

- Der Matcher kostet 0,23 ms je Dokument bei 3,4 kZeichen, also rund 15 Millionen Zeichen pro Sekunde;
  der Rest des Schritts `index` (Polars-Frame, Sortierung) sind 5 ms, ein Zehntel.
- Die Extraktion kostet 10 bis 40 ms je PDF, grob 20 ms je Seite. Hochgerechnet auf 19 108 PDFs sind das
  sechs bis sieben Minuten seriell, der Abruf aus dem Netz dagegen Stunden.
- Die Polars-Stufen liegen im Millisekundenbereich und sind kein Kandidat für Optimierung.

## Profile vom 2026-10-11: Offline-Lauf, Index, Extraktion

Datensatz: die Referenz der Arbeit nach `bootstrap` (19 108 Paper, 19 033 Texte, 5841 Suchbegriffe), dazu
die ersten 200 PDFs nach Paper-ID aus `georep fetch pdfs --limit 200`. Code auf dem Stand von Phase 5,
pypdf 6.20.0, FlashText 2.7, Polars 2.

### Voller Offline-Lauf: 6,3 s, davon 4,1 s Index

`georep run --force` ohne Profiler, Sekunden je Schritt aus der Ausgabe des Laufs; Spitzenwert 700 MB RSS.

| Schritt | Zeit | Was darin steckt (aus `georep profile`) |
|---|---|---|
| `texts` | 0,2 s | 19 092 Dateiprüfungen `PdfStore.has` (0,25 s unter cProfile), `PaperStore.load` mit 19 108 pydantic-Validierungen (0,13 s) |
| `voters`, `streets`, `pois`, `dictionary`, `results` | je unter 0,1 s | Polars; nichts zu holen |
| `corpus` | 0,7 s | `write_parquet` 0,29 s, Textstore laden 0,17 s, Frame aus 19 108 Zeilen 0,10 s |
| `index` | 4,1 s | FlashText `extract_keywords`: 3,78 s Eigenzeit für 19 033 Texte (88 % des Schritts); `str.lower` je Text 0,14 s (die Texte sind schon kleingeschrieben, FlashText tut es noch einmal); Polars 0,09 s; Trie-Aufbau 0,06 s |

Der Index ist der einzige heiße Pfad der Offline-Kette, und er ist reines Python: ein Zeichen-für-Zeichen-Lauf
durch 65 Millionen Zeichen. Alles andere liegt in Polars oder im Dateisystem und ist mit unter einer
Sekunde nicht der Mühe wert.

### Extraktion über 200 PDFs: 38 ms je PDF, 17 ms je Seite

| Messung | Wert |
|---|---|
| Abruf (`fetch pdfs --limit 200`, seriell, 1 s Pause) | 218 s für 200 PDFs, 29 MB, 0 Fehler; 1,09 s je PDF, davon 1,0 s Pause |
| `georep run texts --force` ohne Profiler | 8,3 s: 200 extrahiert, 445 Seiten, 697 438 Zeichen nach dem Marker |
| davon Extraktion (ohne Dateiprüfungen, Store laden und speichern) | rund 7,6 s, also 38 ms je PDF, 17 ms je Seite |
| dasselbe unter cProfile | 25,3 s und 75 Millionen Funktionsaufrufe: pypdf ist reines Python, der Profiler verdreifacht die Zeit |

Verteilung unter cProfile (23,7 s in `PageObject.extract_text`): Parsen der Content-Streams
(`_parse_content_stream`, `read_object`) 10,5 s = 44 %; Textoperatoren (`_handle_tj_operation`,
`get_text_operands`, `crlf_space_check`) 7,2 s = 30 %; Schriften laden (`from_font_resource`) 1,0 s = 4 %.
Der Rest verteilt sich auf Streamlesen und Objektauflösung.

Treue: 197 der 200 neuen Texte sind zeichengleich mit den Texten der Arbeit (pypdf vom Januar 2026); die drei
anderen unterscheiden sich um genau ein Leerzeichen bei einer Tiefstellung („co 2" statt „co2"). Der danach
neu gebaute Index ist byteidentisch mit dem vorherigen (31 024 Treffer, `results` blieb „aktuell").

### Hochrechnung auf den vollen Datensatz

| | 200 PDFs | 19 108 PDFs |
|---|---|---|
| Abruf mit 1 s Pause | 3,6 min | rund 5,8 h |
| Platz | 29 MB | rund 2,8 GB |
| Extraktion mit pypdf, seriell | 7,6 s | rund 12 min |
| Index (FlashText) | | 4,1 s je Lauf |

### Was daraus folgt (Stand 2026-10-11, zur Entscheidung)

- **Extraktion:** Der Abruf ist dreißigmal teurer als die Extraktion, und die Pause ist Rücksicht auf den Server,
  nicht unsere Rechenzeit. Ein schnellerer Extraktor (pypdfium2, pymupdf) spart im vollen Lauf höchstens elf
  Minuten einmalig und riskiert andere Texte als die der Arbeit; pypdf reproduziert 197 von 200 zeichengleich.
  Empfehlung: pypdf bleibt. Das Protokoll `PdfTextExtractor` steht, falls sich das ändert.
- **Matcher:** 4 s je Lauf sind gemessen und erklärt (reines Python). Ein C- oder Rust-Matcher brächte den
  Schritt vermutlich unter eine halbe Sekunde, muss aber FlashTexts Vertrag exakt treffen (längster Treffer
  an Wortgrenzen, Umlaute sind Grenzen, Terminator wird verbraucht; `tests/property/oracle_matcher.py`), und
  pyahocorasick liefert überlappende Treffer, die erst nachgefiltert werden müssten. Empfehlung: erst, wenn
  der Index öfter als einmal je Datenänderung läuft oder der Korpus um eine Größenordnung wächst. Billiger
  ist der doppelte `lower()` (3 %), lohnt aber auch nicht.
- **Rust:** kein gemessener Flaschenhals, den Python nicht in Sekunden erledigt. Kein Port.
