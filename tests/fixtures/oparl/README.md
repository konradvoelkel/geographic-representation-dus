# Herkunft

`papers_page.json`: sechs Einträge der ersten Seite von
<https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers>, abgerufen am 2026-10-09, unverändert bis auf
die Auswahl: drei Papers mit `mainFile` ohne `auxiliaryFile`, eines ohne `mainFile` (aber mit `auxiliaryFile`), zwei mit beidem.
`pagination` und `links` sind die der echten Seite. Die Datei ist der Vertrag mit dem Server: `tests/unit/test_oparl.py`
prüft, dass das Modell jeden Schlüssel kennt, den der Server liefert.
