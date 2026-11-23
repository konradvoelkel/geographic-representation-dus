# Validierung Vorhaben 24 „Anfragen als Kontrolle in der Kooperation"

- `codebuch.toml`: Fassung 2026-11-23.1, eine Frage (`dezernat`: welches Dezernat ist adressiert) mit
  festem Antwortformat (JSON-Zeile je Aufgabe).
- `stichprobe.csv`: 100 Anfragen der drei Düsseldorfer Perioden aus der Grundgesamtheit der Prüfung
  (Fraktionen, Rat und Ausschüsse, im Zeitraum der Kooperation), Seed 24, sieben Schichten nach dem Weg
  der Zuordnung (Messdokument § 4). Nur IDs und Schicht.
- Die Aufgaben mit Textanfang und der Liste der Dezernate zum Datum liegen nur lokal unter
  `/media/konrad/xtraspace/georep/messdaten/kodierung/24-kontrolle/aufgaben.jsonl`, dazu leere
  `antworten-A.jsonl` und `antworten-B.jsonl`. Die Aufgaben enthalten weder das Dezernat des Verfahrens
  noch den Weg noch die Schicht; ihre Reihenfolge ist gemischt (Seed 25).
- `labels.csv`: je Aufgabe (OParl-ID) und Frage (`dezernat`, `weitere`, `amt`) die Werte von Kodierer A
  und B (zwei unabhängige Opus-Agenten, 2026-11-23), die Schlichtung (ein dritter Opus-Agent, nur bei
  Uneinigkeit: 4 Aufgaben) und das Endlabel, alle als JSON. Gebildet mit
  `docs/plans/24-kontrolle-messung.py --labels`. Übereinstimmung beim Dezernat 96 von 100, Krippendorffs α
  0,954. Kein menschlicher Goldstandard (`docs/plan-vorverarbeitung-2026-11.md`, § 2.6), und alle drei sind
  dasselbe Modell (`docs/plans/fragen-2026-11.md`, Frage 19).
- Ergebnis: `docs/plans/24-kontrolle.md`, § 4.1 (keine Schicht erreicht die Präzision 0,9; hochgerechnet
  0,721) und § 5.1 (Urteil umbauen). Die Vorschläge für ein Codebuch .2 stehen dort in § 9 (Frage 9.13).
  Die Antworten mit Begründungen, die Uneinigkeiten und die Schlichtung liegen nur lokal unter
  `/media/konrad/xtraspace/georep/messdaten/kodierung/24-kontrolle/`.
