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
