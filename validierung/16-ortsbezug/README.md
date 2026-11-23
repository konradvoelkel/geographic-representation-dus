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
- **Runde 2 (Umbau, `docs/plans/16-ortsbezug.md`, § 5.3 und § 5.4)**: `codebuch-2.toml` (Fassung
  2026-11-23.2, Regeln (a) bis (e), Stadtbezirk und Stadtteile im Material), `stichprobe-2.csv`
  (100 Paare aus 100 Dokumenten, keines aus Runde 1, Seed `16-2`, Aufgaben `16-2-NNN`, nur IDs).
  `labels-2.csv`: Endlabels der Runde 2 (zwei Kodier-Agenten nach Fassung 2, Schlichtung einer
  Uneinigkeit, 2026-11-23), Spalten wie `labels.csv`; ausgewertet mit
  `uv run python docs/plans/16-ortsbezug-messung.py --auswertung-2`, Ergebnis im Messdokument § 4.4
  und § 5.5. Aufgaben (`aufgaben-2.jsonl`)
  und Ausgabe des Verfahrens (`regel-2.jsonl`, den Kodierern nicht zeigen) nur lokal.
