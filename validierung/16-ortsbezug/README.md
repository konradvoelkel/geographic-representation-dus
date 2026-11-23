# Validierung Vorhaben 16 „Ortsbezug verfeinern"

- `codebuch.toml` (Fassung 2026-11-23.1, vor der Kodierung), `stichprobe.csv` (200 Paare
  Dokument × Wahlbezirk aus 200 Dokumenten, Seed 20261123, geschichtet nach der besten Stelle des
  Treffers): Mess-Agent. Nur IDs: `aufgabe`, `paar` (die ersten zwölf Hexzeichen von
  SHA-1 über „ID|Wahlbezirk"), `id`, `wahlkreis_id`, `schicht`, `gewicht`.
- `labels.csv` fehlt noch: zwei unabhängige Kodier-Agenten und ein Schlicht-Agent nach dem Codebuch
  (`docs/plan-vorverarbeitung-2026-11.md`, § 2.6); Spalten wie bei 11 und 14. Kein menschlicher
  Goldstandard.
- Aufgaben mit Text und die Ausgabe der Regel (`regel.jsonl`, den Kodierern nicht zeigen) nur lokal
  unter `/media/konrad/xtraspace/georep/messdaten/kodierung/16-ortsbezug/`.
- Auswertung: `uv run python docs/plans/16-ortsbezug-messung.py` rechnet das Kriterium, sobald
  `labels.csv` da ist (§ 4.1 der Ausgabe); Messdokument `docs/plans/16-ortsbezug.md`, § 4.
