# Validierung Vorhaben 12 „Kennungen und Beträge"

- `codebuch.toml`: Fassung 2026-11-23.1, nach der `labels.csv` kodiert ist.
- `codebuch-2.toml`: Fassung 2026-11-23.2, Vorschlag nach der Kodierung (Regeln R1 bis R18 des
  Schlicht-Agenten, Wertformen der Kodierer, R19 und R20 aus den Labels); gilt nur für eine
  Bestätigungsstichprobe nach einem Umbau (Messdokument `docs/plans/12-kennungen.md`, § 5).
- `stichprobe.csv`: 650 Aufgaben, Seed 20261123: 600 Treffer des Extraktors `kennungen-messung-v1`
  (100 je Art, geschichtet, `schicht_n` für die Gewichte) und 50 Recall-Dokumente in fünf Schichten;
  nur IDs und Spannengrenzen (Messdokument § 4).
- `labels.csv`: je Aufgabe und Frage die Kodierung von Kodierer A und B (zwei unabhängige
  Opus-Agenten, 2026-11-23), die Schlichtung (ein dritter Opus-Agent, nur bei Uneinigkeit, 67
  Aufgaben) und das Endlabel, alle Werte als JSON. Fragen der Präzisionsaufgaben: `art`, `grenzen`,
  `grenzen_korrigiert` (Offsets statt Text), `norm`, `rolle`, `frist`; Recall-Aufgaben: eine Zeile
  `spannen` mit den Spannen als Offsets in den Rohtext. Wo weder die Kodierer einig waren noch der
  Schlichter entschieden hat (vier Präzisionsfelder, zwölf Felder gemeinsamer Recall-Spannen, alle nur
  Schreibung oder durch R1, R3, R17, R18 gedeckt), steht in `schlichtung` `{"auswerter": …, "regel":
  …}`. Kein menschlicher Goldstandard (`docs/plan-vorverarbeitung-2026-11.md`, § 2.6).
- Übereinstimmung der Kodierer: Art 600/600, Grenzen 597/597 (α 1,0), Norm 555/597 (α 0,93), Rolle
  90/98 (α 0,90), Funktion des Termins 89/100 (α 0,85); Recall-Spannen 502 gemeinsam, 14 nur bei
  einem (F1 0,986).
- Offsets sind Zeichenindizes in den Rohtext der Messdatei `messdaten/rohtext/duesseldorf.parquet`
  (pypdf-7.1.0 roh), gebunden an `pdf_sha256` der Aufgabe.
- Die Aufgaben mit Textausschnitten, die Antworten, die Schlichtung mit Begründungen, die
  Rückmeldungen der Kodierer und die Fehlerliste des Extraktors liegen nur lokal unter
  `/media/konrad/xtraspace/georep/messdaten/kodierung/12-kennungen/`.
- Nachrechnen: `uv run python docs/plans/12-kennungen-messung.py --auswertung` (schreibt
  `labels.csv` neu und druckt alle Maße).
- Ergebnis: `docs/plans/12-kennungen.md`, § 4.1.
