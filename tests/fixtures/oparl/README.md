# Herkunft

`papers_page.json`: sechs Einträge der ersten Seite von
<https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers>, abgerufen am 2026-10-09, unverändert bis auf
die Auswahl: drei Papers mit `mainFile` ohne `auxiliaryFile`, eines ohne `mainFile` (aber mit `auxiliaryFile`), zwei mit beidem.
`pagination` und `links` sind die der echten Seite. Die Datei ist der Vertrag mit dem Server: `tests/unit/test_oparl.py`
prüft, dass das Modell jeden Schlüssel kennt, den der Server liefert.

`organizations_page.json`: zwölf der 58 Objekte der einzigen Seite von
<https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/organizations>, abgerufen am 2026-10-11 21:42 UTC (HTTP 200
in 0,47 s, 216 955 Bytes, kein `next`), unverändert bis auf die Auswahl, kompakt wie vom Server geliefert;
`pagination` und `links` sind die der echten Seite. Auswahl: die Fraktionen und Gruppen der Periode 2020 bis 2025
mit Stimmenspalte, soweit sie unter die 40-KB-Grenze passen (AfD `gr/400198`, Die Linke `gr/66`, FDP `gr/49`,
SPD/Volt `gr/400204`; CDU `gr/44` mit 20 KB und BÜNDNIS 90/DIE GRÜNEN `gr/42` mit 14 KB bleiben draußen, ihre
Abbildung prüft ein Test mit synthetischen Objekten), die Gruppen Tierschutz/FREIE WÄHLER `gr/400202` (bis
2025-10-31) und Ratsgruppe Freie Wähler Tierschutz PARTEI `gr/400238`, Die PARTEI `gr/400205` (ohne
`classification`), ein älteres Einzelmandat (AfD `gr/162`, bis 2020-10-31), eine Fraktion nach der Periode (BSW
`gr/400239`, ab 2025-11-01) und je ein Objekt der übrigen `classification`-Werte: Integrationsrat `gr/144`
(Gremium), Bezirksvertretung 1 `gr/32` (Bezirk), Ordnungs- und Verkehrsausschuss `gr/25` (Ausschuss). Der Server
kennt kein `organizationType`, nur `classification` (Ausschuss, Fraktion, Bezirk, Gremium oder keine).
