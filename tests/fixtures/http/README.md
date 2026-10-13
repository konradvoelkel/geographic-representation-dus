# Aufgezeichnete Antworten (2026-10-11)

Einmalige echte Abrufe, klein geschnitten; die Offline-Tests der Quellen lesen sie. Jede Antwort
liegt neben ihrer Anfrage (`*.query.txt`, `*.params.json`).

| Datei | Quelle | Anfrage | Inhalt |
|---|---|---|---|
| `overpass_1302.json` | overpass-api.de | `way[highway][name]…(poly:…)` des ersten Stimmbezirks (1302, Altstadt) | 72 Ways, 11 Namen |
| `overpass_9802.json` | overpass-api.de | kleinster Stimmbezirk (9802) | 29 Ways, 7 Namen |
| `overpass_0108.json` | overpass-api.de | mittlerer Stimmbezirk (0108) | 14 Namen |
| `wikidata_sparql.json` | query.wikidata.org | die SPARQL-Query der Arbeit (Q1718, de) | erste 25 von 995 Bindings |
| `wikipedia_geosearch_1302.json` | de.wikipedia.org | GeoSearch in der Bounding Box von 1302 | 8 Treffer |

Die Ways tragen nur die Tags `highway`, `name`, `service`, `area`; der Overpass-Filter bildet den
`network_type="all"` von osmnx nach (ohne `area=yes`, ohne `abandoned|construction|planned|platform|proposed|raceway|razed`,
ohne `service=private`), weil die Referenz damit entstand.

## Treue gegen die Referenz der Arbeit (November 2025)

| Quelle | Vergleich | Ergebnis |
|---|---|---|
| Overpass | Straßennamen je Stimmbezirk gegen `reference/raw/streets_per_district.json` | 1302: 11 von 11 identisch; 9802: 7 von 7; 0108: 11 von 12 (fehlt: Julius-Raschdorff-Straße; neu: Eisvogelweg, Josef-Kleesattel-Straße, Stümpeweg) |
| SPARQL | Labels gegen die 950 SPARQL-Orte in `reference/raw/wikipedia_dict.json` | 949 gemeinsam, 1 nur in der Referenz, 11 neu |
| GeoSearch | die 2 der Referenz dem Bezirk 1302 zugeordneten Orte | beide in der heutigen Antwort |

Abweichungen sind OSM- und Wikidata-Pflege seit November 2025, keine Fehler der Abfrage.

## Mönchengladbach (2026-10-12, Option 01)

Dieselben drei Quellen für die zweite Stadt, je ein Stimmbezirk der drei Wahlbezirke der
Mini-Fixture (`tests/fixtures/mg/`). Die Antworten liegen wieder neben ihrer Anfrage. Gelesen
werden sie von `tests/golden/test_second_city.py` (Netzschritte gegen die Fake-Session) und von
`tests/fixtures/make_mini_mg.py`.

| Datei | Quelle | Anfrage | Inhalt |
|---|---|---|---|
| `overpass_mg_10404.json` | overpass-api.de | Stimmbezirk 10404 (Wahlbezirk 04, Hardt) | 53 Ways, 12 Namen |
| `overpass_mg_10906.json` | overpass-api.de | Stimmbezirk 10906 (Wahlbezirk 09, Hermges/Dahl/Ohler) | 27 Ways, 10 Namen |
| `overpass_mg_32301.json` | overpass-api.de | Stimmbezirk 32301 (Wahlbezirk 23, Dorfbroich/Hövel) | 69 Ways, 17 Namen |
| `wikidata_sparql_mg.json` | query.wikidata.org | dieselbe Query mit Q2758 | erste 25 von 1 190 Bindings |
| `wikipedia_geosearch_mg_10404.json` | de.wikipedia.org | GeoSearch in der Bounding Box von 10404 | 0 Treffer (ein Fall ohne Treffer, auch der gehört geprüft) |
| `wikipedia_geosearch_mg_10906.json` | de.wikipedia.org | ebenso für 10906 | 23 Treffer |
| `wikipedia_geosearch_mg_32301.json` | de.wikipedia.org | ebenso für 32301 | 39 Treffer |

Aufgezeichnet wurde in zwei Runden: am 2026-10-12 gegen 01:45 Uhr zuerst für die Stimmbezirke
11001, 32201 und 40201 (Wahlbezirke 10, 22, 02), rund eine Minute; diese Antworten sind gelöscht,
weil in jenen Bezirken kein Straßenname der PDF-Stichprobe vorkommt und die Kette dort keinen
Treffer fände. Die zweite Runde gegen 02:05 Uhr holte die drei Bezirke oben (knapp zwei Minuten,
Overpass antwortete dreimal mit 504, das Aufzeichnungsskript wiederholt nach 15 s). Die SPARQL-
Antwort stammt aus der ersten Runde und ist stadtweit, also unverändert gültig.

Overpass wiederholt die Session nicht von selbst: ihre Retry-Regel erlaubt GET und HEAD, die
Abfrage ist ein POST.

## Der Abfragetext ist eine Aufzeichnung, kein Schlüssel (2026-10-13)

Die `*.query.txt` tragen das `[timeout:N]`, mit dem damals wirklich gesendet wurde: 60 bei den zwei
Düsseldorfer Abfragen vom 2026-10-11, 90 bei `overpass_0108` und den drei Mönchengladbacher. Seit
`docs/decisions.md`, Punkt 54, ist der Standard 25, und die Dateien werden **nicht** nachgezogen —
der Schlüssel der Fake-Session ist die URL (`tests/fakes.py`), nicht der Abfragetext, und eine
Aufzeichnung wird nicht rückdatiert. Verglichen wird darum nur, was wirklich dieselbe Aussage ist:
der Filter (`OSM_FILTER in recorded`). Die Antworten sind von der Zahl unberührt, sie hängen am
Polygon und am Filter.
