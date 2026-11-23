# Validierung Vorhaben 15 „Dokumentfunktion und gemeinsame Anträge"

- `codebuch.toml`: Fassung 2026-11-23.1, nach der `labels.csv` kodiert ist. Die Lücken, die Kodierer
  und Schlichtung gefunden haben, stehen als Vorschlag für eine Fassung .2 im Messdokument (§ 4.3); sie
  gilt erst für eine nächste Kodierung.
- `stichprobe.csv`: 150 Dokumente der drei Düsseldorfer Perioden, Seed 15, neun Schichten nach der
  Funktion des Regelwerks und den schwierigen Fällen (Messdokument § 4).
- `labels.csv`: je Dokument (`aufgabe` = OParl-ID) und Frage (`funktion`, `urheber`, `adressat`) die
  Kodierung von Kodierer A und B (zwei unabhängige Opus-Agenten, 2026-11-23), die Schlichtung (ein
  dritter Opus-Agent, nur bei Uneinigkeit: zwei Dokumente, drei Felder) und das Endlabel; alle Werte als
  JSON (`urheber` ist eine sortierte Liste). Gebildet mit `docs/plans/15-funktion-messung.py --labels`.
  Kein menschlicher Goldstandard (`docs/plan-vorverarbeitung-2026-11.md`, § 2.6), und beide Kodierer
  sind dasselbe Modell: ihre Übereinstimmung ist ein schwacher Beleg (`docs/plans/fragen-2026-11.md`,
  Frage 19).
- Die Aufgaben mit Textanfängen, die Antworten (mit Begründung und dem Feld `unsicher`), die
  Uneinigkeiten und die Rückmeldungen der Kodierer liegen nur lokal unter
  `/media/konrad/xtraspace/georep/messdaten/kodierung/15-funktion/`.
- Ergebnis: `docs/plans/15-funktion.md`, § 4.1 bis § 4.3 (κ der Funktion 0,905 für Variante B, 0,829
  für A; Antragsteller Präzision 119/119, Recall 119/138).
