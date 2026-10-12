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

`papers_page_0011.json` (2026-10-12, Option 01): sechs Einträge der ersten Seite von
<https://ris-oparl.itk-rheinland.de/Oparl/bodies/0011/papers> (Mönchengladbach), unverändert bis
auf die Auswahl: die fünf Paper, deren PDF unter `tests/fixtures/pdf/mg/` liegt, und eines ohne
`mainFile`. `pagination` und `links` sind die der echten Seite. `tests/unit/test_oparl.py` prüft
auch an dieser Datei, dass das Modell jeden Schlüssel kennt; sie ist zugleich die Quelle der
Metadaten in `tests/fixtures/mg/raw/papers.jsonl`.

`papers_modified_since.json`: sechs Einträge der einen Seite von
<https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers?modified_since=2026-10-01T00:00:00+00:00>,
abgerufen am 2026-10-11, 22:43 UTC (HTTP 200 nach 28,6 s, 266 355 Bytes, 141 Paper, davon fünf mit
`deleted: true`; derselbe Inhalt wie bei der Prüfung am 2026-10-11, 21:42 UTC in `docs/plans/07-monitoring.md`,
§ 3). Auswahl: zwei Gelöschte (`vo/114106`, `vo/114088`; ohne `date`, `modified` ist der Löschzeitpunkt), das
neueste Paper (`vo/114057`, 2026-10-08), eines mit `mainFile` und `auxiliaryFile` (`vo/112413`), eines ohne
`mainFile` (`vo/114038`, sechs `auxiliaryFile`), das älteste (`vo/112372`, 2026-05-15). Die Reihenfolge ist die
der Seite; sie ist weder streng nach `date` noch nach `modified` sortiert, und die Gelöschten stehen zwischen
den datierten Papern. Der Abruf verlässt sich darum nicht auf die Sortierung: `stop_when_older` vergleicht das
größte Datum einer ganzen Seite mit dem Periodenbeginn (`georep.sources.oparl`). `pagination` und `links` sind
die der echten Seite: kein `next` (eine Seite), `first` und `self` tragen den Parameter. Die Datei ist die
Fixture für den inkrementellen Abruf (Option 7): `test_oparl.py` prüft, dass das Modell jeden Schlüssel kennt
und `deleted` liest.
