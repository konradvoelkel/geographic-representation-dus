# Validierung Vorhaben 17 „Zeit und Neuigkeiten"

- `codebuch.toml`: Fassung 2026-11-23.1, nach der `labels.csv` kodiert ist; Vorschläge für eine
  Fassung .2 (die Regeln des Schlichters, die Lücken der Kodierer) stehen im Messdokument, § 9.
- `stichprobe.csv`: 100 Treffer des Lexikons `docs/plans/17-zeit-lexikon.toml` (Version
  2026-11-23.1), zehn je Kategorie, Seed `17-<kategorie>`, Reihenfolge gemischt mit Seed 17
  (Messdokument § 4). Die Spalte `kategorie` ist die Kategorie des Lexikons; die Kodierer sahen sie nicht.
- `labels.csv`: je Aufgabe und Frage (`thema`, `ebene`) die Kodierung von Kodierer A und B (zwei
  unabhängige Opus-Agenten, 2026-11-23, **dasselbe Modell**: die Übereinstimmung misst die
  Festigkeit des Codebuchs für dieses Modell, nicht zwischen Menschen oder Modellen), die
  Schlichtung (ein dritter Opus-Agent, nur bei Uneinigkeit, acht Aufgaben) und das Endlabel. Werte als
  JSON (`thema` eine Liste in Lexikonfolge). Kein menschlicher Goldstandard
  (`docs/plan-vorverarbeitung-2026-11.md`, § 2.6). Geschrieben von
  `uv run python docs/plans/17-zeit-messung.py --labels`.
- Die Aufgaben mit Textausschnitten, die Antworten, die Begründungen und die Schlichtung liegen nur
  lokal unter `/media/konrad/xtraspace/georep/messdaten/kodierung/17-zeit/`.
- Ergebnis: `docs/plans/17-zeit.md`, § 4.1.
