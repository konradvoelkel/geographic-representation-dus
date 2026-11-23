# Validierung Vorhaben 12 „Kennungen und Beträge"

- `codebuch.toml`: Fassung 2026-11-23.1, nach der `labels.csv` kodiert ist.
- `codebuch-2.toml`: Fassung 2026-11-23.2 nach der Kodierung (Regeln R1 bis R18 des Schlicht-Agenten,
  Wertformen der Kodierer, R19 und R20 aus den Labels, „Haushaltsstelle“ als PSP-Element wie in den
  Labels), mit Abschnitt `[runde2]` und festgelegtem Antwortformat `[antwortformat]`; gilt für die
  Bestätigungsstichprobe 2 (Messdokument `docs/plans/12-kennungen.md`, § 3.7, § 4.3, § 5).
- `stichprobe-2.csv`: Bestätigung der Fassung 2 des Extraktors (`kennungen-messung-v2`), 410 Aufgaben,
  Seed `12-2`, nur Dokumente, die in keiner Aufgabe der ersten Runde vorkommen: je 100 Treffer für
  Haushalt, Rechtsgrundlage und Verwaltungseinheit, je 30 für Betrag und Termin, 50 Recall-Dokumente
  (30 Haushalt, 20 Bezirksvertretung; nur Arten 2, 5, 6); nur IDs und Spannengrenzen. Aufgaben mit
  Ausschnitten lokal als `aufgaben-2.jsonl`, Antworten als `antworten-2-A.jsonl` und `antworten-2-B.jsonl`.
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
- `labels-2.csv`: Endlabels der Stichprobe 2 (Codebuch .2), gleiches Format wie `labels.csv`, ohne die
  Fragen `rolle` und `frist`; Schlichtung für 26 Aufgaben, ein Feld und zehn Normwerte gemeinsamer
  Recall-Spannen nach Codebuch .2 vom Auswerter. Kodierer und Schlichter waren dasselbe Modell (Frage 19
  an Konrad). Übereinstimmung: Art 360/360, Grenzen 354/357 (α 0,939), Norm 340/357 (α 0,952),
  Recall-Spannen F1 0,965. Ergebnis: Messdokument § 4.4 und § 5.
- Übereinstimmung der Kodierer: Art 600/600, Grenzen 597/597 (α 1,0), Norm 555/597 (α 0,93), Rolle
  90/98 (α 0,90), Funktion des Termins 89/100 (α 0,85); Recall-Spannen 502 gemeinsam, 14 nur bei
  einem (F1 0,986).
- Offsets sind Zeichenindizes in den Rohtext der Messdatei `messdaten/rohtext/duesseldorf.parquet`
  (pypdf-7.1.0 roh), gebunden an `pdf_sha256` der Aufgabe.
- Die Aufgaben mit Textausschnitten, die Antworten, die Schlichtung mit Begründungen, die
  Rückmeldungen der Kodierer und die Fehlerliste des Extraktors liegen nur lokal unter
  `/media/konrad/xtraspace/georep/messdaten/kodierung/12-kennungen/`.
- Nachrechnen: `uv run python docs/plans/12-kennungen-messung.py --auswertung` (schreibt
  `labels.csv` neu und druckt alle Maße); `--entwurf --stichprobe-2` für Fassung 2 und Stichprobe 2,
  `--fassung 2 --auswertung-2` für `labels-2.csv` und die Bestätigung.
- Ergebnis: `docs/plans/12-kennungen.md`, § 4.1.
