# Validierung Vorhaben 16 „Ortsbezug verfeinern"

- `codebuch.toml` (Fassung 2026-11-23.1, vor der Kodierung), `stichprobe.csv` (200 Paare
  Dokument × Wahlbezirk aus 200 Dokumenten, Seed 20261123, geschichtet nach der besten Stelle des
  Treffers): Mess-Agent. Nur IDs: `aufgabe`, `paar` (die ersten zwölf Hexzeichen von
  SHA-1 über „ID|Wahlbezirk"), `id`, `wahlkreis_id`, `schicht`, `gewicht`.
- `labels.csv`: je Aufgabe und Feld (`bezug`, `begriffe_kein_bezug`, `beleg_zeile`, `unsicher`)
  Kodierer A, Kodierer B (zwei unabhängige Kodier-Agenten, 2026-11-23), Schlichtung (ein Schlicht-Agent,
  nur bei `bezug` und nur bei Uneinigkeit, 5 Aufgaben) und Endlabel; Werte als JSON, ohne Ausschnitte,
  Begründungen und Anschriften. `beleg_zeile` und `unsicher` bleiben ohne Label, wo die Kodierer
  abweichen (26 und 20 Aufgaben). Kodierer und Schlichter sind dasselbe Modell; kein menschlicher
  Goldstandard (`docs/plan-vorverarbeitung-2026-11.md`, § 2.6).
- Aufgaben mit Text und die Ausgabe der Regel (`regel.jsonl`, den Kodierern nicht zeigen) nur lokal
  unter `/media/konrad/xtraspace/georep/messdaten/kodierung/16-ortsbezug/`.
- Auswertung: `uv run python docs/plans/16-ortsbezug-messung.py` rechnet das Kriterium aus
  `labels.csv` (Abschnitt „§ 4.1 Kodierung" der Ausgabe); Ergebnis und Urteil im Messdokument
  `docs/plans/16-ortsbezug.md`, § 4.1 und § 5.
