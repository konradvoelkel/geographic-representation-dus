# Profiling und Benchmarks

Erst messen, dann optimieren, dann nachmessen (decisions.md, Punkt 13 und 14). Hier stehen die Werkzeuge und
die datierten Zahlen; die Rohdaten (`.prof`-Dateien, `.benchmarks/`) bleiben lokal, weil sie
rechnerspezifisch sind. Alle Zahlen in dieser Datei stammen von Konrads Rechner (AMD Ryzen 7 5700X,
Python 3.14.6, Linux 6.8 lowlatency), sofern nichts anderes dabeisteht.

## Werkzeuge

| Befehl | Was er tut |
|---|---|
| `uv run georep profile [schritt …]` | führt die Schritte erzwungen unter cProfile aus, schreibt `docs/profiling/<datum>-<schritt>.prof` (gitignored) und druckt die pstats-Tabelle (`--top`, `--sort tottime`); ohne Namen alle Offline-Schritte, Netzschritte nur mit `--online` |
| `uv run nox -s profile -- <schritt>` | dasselbe als nox-Session |
| `uv run snakeviz docs/profiling/<datei>.prof` | Anzeige im Browser |
| `uv run nox -s bench` | pytest-benchmark über `tests/bench/`, speichert jeden Lauf unter `.benchmarks/` (gitignored) und vergleicht mit dem letzten; rot ab 20 % langsamer im Minimum. Der erste Lauf auf einem Rechner legt nur die Baseline an |

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

### Rauschen und Schwelle (2026-10-11)

Sechs Läufe gleichen Codes am selben Nachmittag, Spanne = größtes durch kleinstes Minimum je Benchmark:

| Benchmark | Spanne des Minimums | Spanne des Medians |
|---|---|---|
| `aggregate_voters` (0,6 ms) | 3,9 % | 40,9 % |
| `build_dictionary` (0,9 ms) | 12,5 % | 12,6 % |
| `hits_and_voter_join` (1,3 ms) | 12,7 % | 17,9 % |
| `matcher_build` (1,4 ms) | 8,0 % | 11,0 % |
| `extract_pdf[…]` (10 bis 42 ms) | 1,9 bis 3,7 % | 2,7 bis 3,8 % |
| `matcher_extract_over_corpus` (46 ms) | 9,0 % | 7,9 % |
| `index_step` (51 ms) | 5,8 % | 5,6 % |

Die 10 % des Plans schlugen beim vierten Lauf ohne Codeänderung an (`build_dictionary`, 12,5 %). Die
Schwelle steht darum auf 20 % im Minimum: über allem gemessenen Rauschen, aber jede Verdopplung einer
Polars-Stufe und jede Verschlechterung von Matcher oder Extraktion um ein Fünftel bleibt rot. Der Median
rauscht bei den kurzen Stufen stärker als das Minimum, er bleibt Anzeige, nicht Gate.

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

## Schritt `report` mit der Suche (2026-10-12, Option 08)

`georep run report --force` auf der Referenz, Ausgabe des Laufs, zweimal gemessen.

| Messung | Wert |
|---|---|
| Schritt `report` vor der Suche | 1,1 s |
| Schritt `report` mit Sucheinträgen und Abschnitt | 1,3 s |
| `search_entries` allein, 4176 Einträge, Verträge an | 65 ms |
| dasselbe mit `contracts = "off"` | 45 ms |
| `index.html` | 687 418 → 848 144 Byte (gzip 100 → 141 KB), Budget 1 500 000 |

Die Verträge kosten hier 20 ms, fast alles im `ensure`, das die Zuordnung Begriff → Eintrag ein zweites Mal
von Hand rechnet. Der erste Entwurf dieses Prädikats suchte die Mitglieder je Eintrag linear (4176 × 5841
Vergleiche) und machte den Aufruf mit 605 ms zehnmal teurer; die Gruppierung in einem Durchlauf behebt das.
Die Lehre ist die alte: ein Vertrag an einer Batch-Grenze darf die Batch nicht quadratisch machen.

## Overhead der Verträge (2026-10-11, Phase 6)

Alle Verträge aus Phase 6 aktiv (`contracts = "on"`, Standard) gegen `GEOREP_CONTRACTS=off`, voller
Datensatz, derselbe Rechner wie oben.

| Messung | Verträge an | Verträge aus |
|---|---|---|
| `georep run --force`, gesamt, drei Läufe | 6,7 / 6,7 / 6,4 s | 6,7 / 6,6 / 6,7 s |
| Schritt `index` in diesen Läufen | 4,3 / 4,3 / 4,1 s | 4,3 / 4,2 / 4,3 s |
| `build_index` direkt, Minimum von drei Aufrufen | 4,04 s | 4,09 s |
| `hits_by_district` + `join_voters` direkt, Minimum von zehn | 16 ms | 9 ms |

Der Overhead liegt unter dem Rauschen des Laufs, also unter einem Prozent. Absolut kosten die Verträge
rund zehn Millisekunden je Lauf, fast alles in den Mengenvergleichen der Nachbedingungen von
`hits_by_district` und `join_voters` (Wahlbezirke Teilmenge der Eingaben, Listen sortiert und eindeutig).
Die Verträge stehen an Batch-Grenzen, nicht in der heißen Schleife des Matchers; darum bleibt `index`
unverändert. `contracts = "off"` ist eine Option für Messungen, kein Bedürfnis im Betrieb.

### Kosten der Verträge in den Benchmarks (2026-10-11)

Nach Phase 6 war `nox -s bench` einmal rot, wie vorgesehen: `build_dictionary` 0,96 zu 1,46 ms (+51 %),
`hits_and_voter_join` 1,43 zu 1,91 ms (+33 %), `index_step` 51 zu 54 ms (+5 %); alle anderen unverändert.
Das sind die Nachbedingungen (Listen sortiert und eindeutig, Mengenvergleiche der Wahlbezirke) auf
Millisekunden-Stufen, absolut eine halbe Millisekunde je Schritt. Angenommen; der gespeicherte Lauf ist die
neue Baseline. So soll der Gate arbeiten: rot bei einer Änderung, die man erklären und entweder zurücknehmen
oder hier aufschreiben muss.

## Die Schritte `bodies` und `body_hits` (2026-10-12, Option 05)

`uv run georep profile bodies body_hits` auf der Referenz (19 108 Dokumente, 41 Wahlbezirke), derselbe
Rechner wie oben, unter cProfile:

| Schritt | unter cProfile | im Lauf (`georep run`) | was die Zeit kostet |
|---|---|---|---|
| `bodies` | 0,33 s | 0,1 s | 19 108 Aufrufe von `parse_reference` (0,09 s), Parquet schreiben |
| `body_hits` | 0,10 s | 0,1 s | 44 Polars-`collect` (0,05 s) über 29 573 Dokument-Bezirk-Paare |

Zusammen rund 0,2 s im Lauf; der volle Offline-Lauf steigt damit von rund 7 s auf rund 9 s (die zwei
Schritte und das größere `report`). Das Budget aus dem Plan (unter 1 s für beide) ist eingehalten.

**`deal.pure` in der Schleife, gemessen.** Das erste Profil zeigte `deal._has_patcher.patch` mit 19 108
Aufrufen und 0,078 s von 0,242 s in `classify_papers`: `deal.pure` ist `deal.has()` plus `deal.safe`, und
`has()` patcht je Aufruf prozessweit `socket` und `sys.stdout`. Ohne cProfile gemessen (Minimum von drei
Läufen auf der Referenz): 0,076 s mit `deal.pure`, 0,053 s mit `deal.safe`, also rund 30 %. Der Parser
trägt seitdem `deal.safe`; seine Reinheit prüfen `deal.cases` und crosshair (`nox -s verify`). Das ist die
Regel aus CLAUDE.md („`deal.pure` nicht in heiße Schleifen") mit einer Zahl dahinter.

**Benchmarks.** Zwei neue Einträge in `tests/bench/`: `classify_papers` über die 200 Dokumente der
Mini-Fixture (Minimum 1,00 ms) und `hits_by_body` über die drei Wahlbezirke der Mini-Fixture (Minimum
3,19 ms). Der erste `nox -s bench` legte ihre Baseline an, der zweite lief grün dagegen.
## Profile vom 2026-10-12: Gewichtung und Themenmodell (Option 06)

Gemessen auf Konrads Rechner, während sieben weitere Agenten darauf arbeiteten; darum liefen alle Messungen
dieses Abschnitts mit gedrosselten Threads: `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
POLARS_MAX_THREADS=4`. Ohne diese Grenzen ist der Schritt `topics` rund 25 % schneller (9,2 s gegen 9,8 s im
Median, einmal gemessen). Die Zahlen sind damit eine Obergrenze, keine Bestleistung.

### Schritt `topics`: 9 bis 12 s, davon zwei Drittel NMF

`georep run topics --force`, drei Läufe ohne Profiler: 9,8 / 9,1 / 12,4 s. Unter cProfile 8,4 s (der
Profiler sieht nur Python-Frames; TF-IDF und NMF rechnen in C und erscheinen beim aufrufenden Frame, darum
verteuert er hier fast nichts).

| Stufe | Zeit unter cProfile | Was passiert |
|---|---|---|
| `TfidfVectorizer.fit_transform` | 2,6 s | 19 033 Texte, 51 Millionen Zeichen, Vokabular auf 20 000 Wörter beschnitten (`min_df 5`, `max_df 0,5`), 1 970 953 Einträge |
| `NMF.fit_transform` | 5,3 s | 20 Themen, Koordinatenabstieg, 120 Iterationen bis `tol = 1e-3`; davon 4,8 s in `_update_coordinate_descent` |
| Parquet schreiben | 0,4 s | `themen.parquet` (3,3 kB), `themen_dokumente.parquet` (97 kB), `interim/themen_anteile.parquet` (1,37 MB) |

Mit `tol = 1e-4` läuft NMF in die Obergrenze von 200 Iterationen (6,9 s, ConvergenceWarning) und konvergiert
erst nach 412 Iterationen in 13,4 s, für 0,03 % weniger Rekonstruktionsfehler. LDA (online, 10 Iterationen)
brauchte 47 s und lieferte Themen aus Funktionswörtern. Beides steht in `decisions.md`.

### Schritt `weights`: 0,7 s für 26 Varianten

`georep run weights --force`, drei Läufe: 0,6 / 0,8 / 0,7 s; unter cProfile 0,74 s, davon 0,55 s in
`PyLazyFrame.collect` (631 Aufrufe: Polars rechnet je Variante ein halbes Dutzend kleiner Stufen). Die 26
Varianten teilen sich dieselben Paare (51 887 Tripel) und Begriffsgewichte, `document_weights` kostet
zusammen 0,28 s. Die Verträge (62 Aufrufe von `deal`) liegen im Rauschen.

### Voller Offline-Lauf mit beiden Schritten: 18,9 s

`georep run` nach einer Änderung des Settings-Fingerprints (alle Schritte neu), ungedrosselt gemessen:
`texts` 0,5 s, `corpus` 0,7 s, **`topics` 9,2 s**, `index` 4,4 s, `results` 0,1 s, **`weights` 1,1 s**,
`report` 1,6 s. Das Themenmodell ist damit der teuerste Schritt der Kette, bleibt aber weit unter der
Schwelle von 60 s, ab der ein Schritt gesondert behandelt würde (Plan 06, Stufe C). `topics.k = 0` nimmt ihn
ganz heraus.

### Zwei Benchmarks mehr

`weights_step` (alle Varianten ohne Themenmodell auf der Mini-Fixture) und `document_weights_over_the_pairs`
stehen in `tests/bench/test_bench_hot_paths.py`. Das Themenmodell selbst ist kein Benchmark: NMF schwankt mit
der BLAS-Bibliothek und der Zahl der Threads, dafür ist `georep profile topics` da.

| Benchmark | Eingabe | Minimum (2026-10-12, gedrosselt) |
|---|---|---|
| `document_weights_over_the_pairs` | Gewichte je Paar plus Summen, drei Wahlbezirke | 0,96 ms |
| `weights_step` | alle neun Varianten der Mini-Fixture ohne Themen | 12,2 ms |

Beide liegen über den Polars-Stufen der Arbeit (0,6 bis 1,3 ms), weil `variants` je Variante ein halbes
Dutzend kleiner Frames baut; auf der Referenz sind es 0,7 s für 26 Varianten. Der zweite Lauf gegen die
frische Baseline blieb grün (12,0 gegen 12,2 ms).

### Determinismus hat eine Grenze: die Threads

Zwei Läufe im selben Prozess und mit derselben Thread-Zahl schreiben byteidentische Dateien (Golden-Master-Test).
Zwischen 13 und 2 BLAS-Threads unterscheiden sich `themen.parquet` und `themen_anteile.parquet` dagegen in den
Bytes (gemessen 2026-10-12): die Reduktionsreihenfolge in NMF ändert die letzten Stellen. Labels, dominierte
Dokumente und alle Kennzahlen der Seite blieben dabei gleich. Darum prüfen die Golden-Master-Tests auf der
Referenz nur Invarianten (20 Themen, Zerlegung der Zählung, Labels ohne Stoppwörter), keine einzelnen Zahlen.
