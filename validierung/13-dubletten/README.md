# Validierung Vorhaben 13 „Dubletten und Dokumentfamilien"

- `codebuch.toml` (Fassung 1, 2026-11-23, vor der Kodierung) und `stichprobe.csv` (200 Dokumentpaare,
  Seed 13, geschichtet nach der exakten Jaccard-Ähnlichkeit über Fünf-Wort-Shingles): Mess-Agent.
  Nur IDs: `paar`, `id_a`, `id_b`, `stufe`, `grundgesamtheit` (Paare der Stufe, für die Gewichte),
  `jaccard`.
- `labels.csv`: je Paar (`aufgabe` = `paar`, `frage` = `code`) Kodierer A, Kodierer B (zwei
  unabhängige Kodier-Agenten, 2026-11-23), Schlichtung (ein Schlicht-Agent, nur bei Uneinigkeit,
  7 Paare) und Endlabel; Werte als JSON, ohne Ausschnitte und Begründungen. Kodierer und Schlichter
  sind dasselbe Modell (Frage 19 an Konrad, offen); kein menschlicher Goldstandard
  (`docs/plan-vorverarbeitung-2026-11.md`, § 2.6).
- Aufgaben mit Textausschnitten, Antworten mit Begründungen, `uneinig.jsonl` und
  `schlichtung.jsonl` nur lokal unter
  `/media/konrad/xtraspace/georep/messdaten/kodierung/13-dubletten/`.
- Erzeugt und ausgewertet mit `uv run python docs/plans/13-dubletten-messung.py --kodierung`
  (`--labels-schreiben` baut `labels.csv` neu aus den lokalen Antworten); Ergebnis und Urteil in
  `docs/plans/13-dubletten.md`, § 4.1 und § 5.
