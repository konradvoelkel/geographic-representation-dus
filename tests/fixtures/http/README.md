# Aufgezeichnete Antworten (2026-10-11)

Einmalige echte Abrufe, klein geschnitten; die Offline-Tests der Quellen lesen sie. Die Antworten
auf Overpass, SPARQL und GeoSearch liegen neben ihrer Anfrage (`*.query.txt`, `*.params.json`),
denn die steckt im Rumpf oder in Parametern. Bei `identify_mg_mehrringig.json` ist die Anfrage die
**URL**, und die steht als `sources.opendata.districts_url` im Profil Mönchengladbachs; eine Datei
daneben wäre eine zweite Fassung derselben Angabe (Punkt 65).

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

### Die mehrringigen Flächen des Geoportals (2026-10-14, Punkt 65)

| Datei | Quelle | Anfrage | Inhalt |
|---|---|---|---|
| `identify_mg_mehrringig.json` | `geoportal.moenchengladbach.de/server/rest/…/MapServer` | die `identify`-URL aus dem Profil, Wort für Wort (ein GET am 2026-10-14: 1 043 618 Bytes, 179 Flächen, 25 187 Stützpunkte, SHA-256 `c2d3de4b862e615e6ddc998c6b7b4dd3f58bf35c4d4137a1b41b25ac4d093b94`) | die **zwei** mehrringigen Flächen 11001 und 11003, 13 401 Bytes |

Sie sind der Grund, dass die Umwandlung der Esri-Ringe nicht am Betrag der Fläche hängen darf,
sondern am Vorzeichen: 11003 trägt einen Ring **gegen** den Uhrzeigersinn (ein Loch von 1 641 m²),
11001 an derselben Stelle einen **im** Uhrzeigersinn (eine zweite Fläche von 1 639 m²). Sie liegen
hier und nicht in `tests/fixtures/mg/`, weil ihr Wahlbezirk (10) nicht zu den drei Bezirken der
Mini-Fixture gehört und die Kette dort keinen Namen für ihn fände. Die 17 Flächen dieser drei
Bezirke liegen als Paketeingabe unter `tests/fixtures/mg/external/`.

Overpass wiederholt die Session nicht von selbst: ihre Retry-Regel erlaubt GET und HEAD, die
Abfrage ist ein POST. Seit dem 2026-10-13 wiederholt darum `fetch_street_names` selbst, bis zu
`sources.osm.retries` mal je Stimmbezirk (`docs/decisions.md`, Punkt 55) -- genau das, was das
Aufzeichnungsskript damals von Hand tat.

## Der Abfragetext ist eine Aufzeichnung, kein Schlüssel (2026-10-13)

Die `*.query.txt` tragen das `[timeout:N]`, mit dem damals wirklich gesendet wurde: 60 bei den zwei
Düsseldorfer Abfragen vom 2026-10-11, 90 bei `overpass_0108` und den drei Mönchengladbacher. Seit
`docs/decisions.md`, Punkt 54, ist der Standard 25, und die Dateien werden **nicht** nachgezogen —
der Schlüssel der Fake-Session ist die URL (`tests/fakes.py`), nicht der Abfragetext, und eine
Aufzeichnung wird nicht rückdatiert. Verglichen wird darum nur, was wirklich dieselbe Aussage ist:
der Filter (`OSM_FILTER in recorded`). Die Antworten sind von der Zahl unberührt, sie hängen am
Polygon und am Filter.

## OParl: Sitzungen, Tagesordnung, Personen (2026-11-23, Fundament F6)

Die Netzstichprobe, die Konrad am 2026-11-23 für F6 freigegeben hat (rund fünf Minuten, je ein, zwei
Seiten der Listen, ein paar Einzelobjekte, kein PDF). Abgerufen von 18:11 bis 18:18 Uhr (MEZ) über die
Session aus `georep.sources.cached_session` (User-Agent und Timeout der Settings, eine Sekunde Pause);
keine der Antworten fiel unter eine Cache-Regel. Zusammen **41,3 s** reine Antwortzeit für elf Abrufe.
`tests/unit/test_oparl_council.py` liest die Dateien: jedes Modell muss jeden Schlüssel kennen, den der
Server schickt (bei Personen außer den Kontaktfeldern, siehe unten), und die Befunde zu dem, was der
Server füllt, stehen dort als Tests.

| Abruf (`…/Oparl/bodies/0015/…`) | HTTP | Zeit | Bytes | Datei hier | Auswahl |
|---|---|---|---|---|---|
| (ohne Pfad: das Body-Objekt) | 200 | 0,17 s | 3 655 | `oparl_body_0015.json` | unverändert; nennt die Listen `meetings`, `people`, `memberships`, `agendaitems`, `consultations`, `files` |
| `meetings` (Seite 1) | 200 | 14,97 s | 2 887 050 | — | nur ausgewertet: 200 Sitzungen, angelegt 2025-12-01 bis 2026-11-23, Beginn 2026-01-12 bis 2027-12-15 (also auch geplante) |
| `meetings?page=4` | 200 | 20,26 s | 4 029 429 | `oparl_meetings_0015.json` | 4 der 200 Sitzungen (angelegt 2023-09 bis 2023-12, Beginn 2022-08 bis 2024-12): Haupt- und Finanzausschuss 2024-12-02 (`26272`, mit Niederschrift und `resultsProtocol`), eine gemeinsame Sitzung zweier Gremien (`26143`), eine Sitzung ohne öffentliche Tagesordnung mit Niederschrift (`26193`), eine ohne alles (`25791`); die Tagesordnung der ersten auf 8 von 31, der zweiten auf 3 von 12 Punkten **gekürzt** (je ein Punkt je Kombination aus Ergebnis, Beratung und Anlage, in der Reihenfolge des Servers) |
| `people` (Seite 1) | 200 | 4,73 s | 409 244 | `oparl_people_0015.json` | 3 der 200 Personen (mit Titel und drei Mitgliedschaften, mit beendeter Mitgliedschaft, ohne Mitgliedschaft); **geschwärzt**: Namen ersetzt durch `VornameN NachnameN`, `phone` und `email` durch `["entfernt"]`, Anschriftfelder von `locationObject` geleert. Die Schlüssel bleiben, damit der Test sieht, dass der Server sie schickt und das Modell sie nicht liest |
| `memberships` (Seite 1) | 200 | 0,19 s | 90 195 | `oparl_memberships_0015.json` | 4 der 200 (je eine Kombination aus `votingRight` und `endDate`) |
| `agendaitems` (Seite 1) | 200 | 0,77 s | 106 774 | `oparl_agendaitems_0015.json` | 4 der 200 (je eine Kombination aus Beratung, Ergebnis und Anlage) |
| `consultations/141791` | 200 | 0,03 s | 588 | `oparl_consultation_141791.json` | unverändert; die Beratung des Papers `vo/114093` aus `tests/fixtures/oparl/papers_page.json` |
| `agendaitems/399178` | 200 | 0,03 s | 506 | `oparl_agendaitem_399178.json` | unverändert; der Punkt dieser Beratung |
| `files/581120` | 200 | 0,03 s | 578 | — | nur ausgewertet: die Datei hinter `resultsProtocol` einer Sitzung von Seite 1 („Haushaltsanträge der Liste B"), keine Niederschrift |
| `files/541049` | 200 | 0,09 s | 565 | `oparl_file_541049.json` | unverändert; die Niederschrift („Niederschrift Ö") der Sitzung `26272` |
| `HEAD downloadfiles/00541049.pdf` | 200 | 0,02 s | — | — | nur `Content-Length: 348439`, `application/pdf`; das PDF selbst wurde nicht geladen |

Kompakt wie vom Server geliefert; `pagination` und `links` sind die der echten Seite (Seite 4 trägt
auch `prev`, das `Links` seitdem kennt). SHA-256 der Dateien hier:

```
4a4e1ebcd0478e385b40f5a91a070552b8fdcd39071752fe314e62b9b935f454  oparl_meetings_0015.json
11a6efc3560953ad9c3c8eb96c699aed58540b0cb37a34f5d1c2e64a68003361  oparl_people_0015.json
7464928ab8cbbc863ff3da46d3b34d9ce098543fad14a9a3d671af1ca8223b81  oparl_memberships_0015.json
9c8e3bf04b38598316a1d55a48fdab21330f9a9e7b1dd7e060b4b7ae69b7ec45  oparl_agendaitems_0015.json
d907b12e30dde8f09db8ad7825bafe02577e735b2fe85bf1e24ceb1e54693f42  oparl_body_0015.json
ebe2495c9fbb1433a2840e3055e25d8bdd63e54dc2efbccb342d40aea51e5c34  oparl_consultation_141791.json
117804573d2bc51c94670ab6f9359e95a9efba6f285d65f7d3df64396b4887ba  oparl_agendaitem_399178.json
f349e31d120e50c2b179e21c956faed65d2855ed29c218287ab1fdb1bab37782  oparl_file_541049.json
```

Die vollen Antworten (rund 7,5 MB) lagen nur für die Auswertung auf xtraspace; die Personenseite trug
Kontaktdaten und ist danach gelöscht worden. Was die beiden Sitzungsseiten über die Füllgrade sagen,
steht in `docs/runbook-sitzungen.md`, § 2.

## Vorhaben 22: die Archive der Bedarfsquellen (2026-11-24)

Keine Datei hier: die Archive sind 0,3 bis 18,5 MB groß (Unfallatlas je Jahr, Zensus-Gitter,
Schuldaten, Sozialindex). Ihre **Form** ist aufgezeichnet, nicht ihr Inhalt: `tests/need_archives.py`
baut winzige Archive mit den Kopfzeilen, Mitgliedsnamen, BOMs, Zeilenenden und Kodierungen der echten
Dateien (abgelesen an den Archiven unter `fremddaten/opendata/`, deren Prüfsummen im README dort
stehen), und `tests/unit/test_need_steps.py` liefert sie über die Fake-Session aus. Die Zeilen sind
erfunden. Der echte Abruf je Quelle (eine Datei je Quelle, mit Pause) lief einmal am 2026-11-24 von
Hand und ergab dieselben SHA-256 wie die Messung.
