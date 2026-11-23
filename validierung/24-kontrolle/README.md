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
- Noch nicht kodiert (Stand 2026-11-23). Danach: `labels.csv` (Aufgabe, Kodierer A, Kodierer B,
  Schlichtung, Endlabel) nach dem Muster von `validierung/15-funktion/`, Auswertung im Messdokument § 4.
  Kein menschlicher Goldstandard (`docs/plan-vorverarbeitung-2026-11.md`, § 2.6).
