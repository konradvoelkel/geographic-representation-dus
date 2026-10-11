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
