# Validierung Vorhaben 14 „Vorgänge"

- `codebuch.toml`: Fassung 2026-11-23.2 nach der Kodierung (Messdokument § 3.9); Fassung .1, nach der
  `labels.csv` kodiert ist, liegt in Commit 8941650.
- `stichprobe.csv`: 150 Kanten, Seed 14, zehn Schichten (Messdokument § 4).
- `stichprobe-2.csv`: Bestätigung der Regelfassung .2, 100 starke Kanten, Seed `14-2`, elf Schichten,
  ohne die 150 alten (Messdokument § 3.9); Aufgaben nach Codebuch .2 lokal als `aufgaben-2.jsonl`.
- `labels.csv`: je Kante und Frage die Kodierung von Kodierer A und B (zwei unabhängige Opus-Agenten,
  2026-11-23), die Schlichtung (ein dritter Opus-Agent, nur bei Uneinigkeit) und das Endlabel. Kein
  menschlicher Goldstandard (`docs/plan-vorverarbeitung-2026-11.md`, § 2.6).
- Die Aufgaben mit Textausschnitten, die Antworten und die Rückmeldungen der Kodierer liegen nur lokal
  unter `/media/konrad/xtraspace/georep/messdaten/kodierung/14-vorgaenge/`.
- Ergebnis: `docs/plans/14-vorgaenge.md`, § 4.1.
