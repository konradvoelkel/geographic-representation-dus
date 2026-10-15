# Runbook: eine weitere Stadt abrufen und veröffentlichen

Stand 2026-10-12 (Option 01, Stufe G). Dieses Runbook führt den einen Schritt aus, den kein Agent
tun durfte: den vollen Abruf einer Stadt (Stunden Netz). Es ist für Mönchengladbach geschrieben,
gilt aber für jedes Profil unter `src/georep/profiles/`; was eine *neue* Stadt braucht, steht in
§ 6.

Alles davor ist fertig und getestet: Profil, Fetcher, kanonische Stimmbezirke, Wahlergebnis,
Seite, Städtevergleich. Ohne diesen Lauf baut `georep publish` die Seite nur für Düsseldorf und
sagt „kein Lauf: moenchengladbach".

## 1. Vorbereitung (eine Minute)

```bash
cd ~/files/work/__drafts/geographic-representation-dus   # oder der Worktree
export UV_PROJECT_ENVIRONMENT=/media/konrad/xtraspace/venvs/georep
export UV_CACHE_DIR=/media/konrad/xtraspace/uv-cache
uv sync
uv run georep profiles                      # zeigt duesseldorf und moenchengladbach
uv run georep --profile moenchengladbach status
```

`status` muss `Profil: moenchengladbach (Mönchengladbach)` zeigen und `Daten unter
…/data/moenchengladbach`. Die Daten der zweiten Stadt liegen durchweg unter diesem Unterordner,
die PDFs und Texte unter `cache_root/moenchengladbach/`; Düsseldorf liegt seit dem 2026-10-13
genauso unter seinem Slug (`data/duesseldorf/`, Punkt 52), es kann also nichts überschrieben
werden. Der HTTP-Cache (`cache_root/http.sqlite`) ist geteilt, sein Schlüssel ist die URL.

## 2. Die kleinen Quellen (Sekunden)

```bash
uv run georep --profile moenchengladbach fetch opendata
uv run georep --profile moenchengladbach run shapes
```

Erwartet: `30574 Bytes Wahlergebnis, 1043618 Bytes Flächen, Straßenverzeichnis,
Wahlbezirksnamen`, danach **`179 Stimmbezirke in 33 Wahlbezirken, CRS EPSG:25832`**. Die Zeile des
Schritts nennt die Quellform **nicht** — welche gilt, sagt `precincts.format` im Profil. Die
Flächenzahl ist am 2026-10-14 am Dienst nachgemessen (der Abruf der Flächen allein 5,2 s), die
Zahl der Wahlergebnis-CSV stammt vom 2026-10-12. Die Flächen sind seit dem 2026-10-14 die des
Wahltags und kommen aus der Operation `identify` des Geoportals (`docs/decisions.md`, Punkt 65);
die URL steht vollständig im Profil und ist ein GET. Zwei Prüfungen lohnen sich dabei:

- **179, nicht 180.** Das Shapefile von 2022 hatte 180 Polygone, von denen 175 zu Stimmbezirken der
  Wahl 2025 gehörten; der Dienst hat genau die 179 Urnen-Stimmbezirke der Wahl.
- **25 187 Stützpunkte, nicht 17 326.** Die URL im Profil trägt `maxAllowableOffset=0` und holt
  damit die volle Genauigkeit; derselbe Abruf mit `maxAllowableOffset=1` liefert eine auf zwei
  Nachkommastellen gerundete, vereinfachte Fassung (443 085 statt 1 043 618 Byte, je Fläche bis
  1 465 m² Unterschied). Beide runden auf 170,47 km², die Flächensumme verrät den Unterschied also
  **nicht** — die Stützpunktzahl verrät ihn:

  ```bash
  uv run python - <<'EOF'
  import json
  from georep.layout import Layout
  from georep.settings import load_settings
  roh = json.loads(Layout.from_settings(load_settings(profile="moenchengladbach")).districts_geojson.read_text(encoding="utf-8"))
  print(len(roh["results"]), "Flächen", sum(len(r) for e in roh["results"] for r in e["geometry"]["rings"]), "Stützpunkte")
  EOF
  ```
- **Die Flächensumme ist 170,47 km²**, die Stadtfläche — dieselbe Zahl wie beim Shapefile von 2022.
  Das ist der Prüfpunkt für die Umwandlung der Esri-Ringe (Löcher und zweite Flächen):

  ```bash
  uv run python - <<'EOF'
  import json
  from shapely.geometry import shape
  from georep.layout import Layout
  from georep.settings import load_settings
  settings = load_settings(profile="moenchengladbach")
  layout = Layout.from_settings(settings)
  flaechen = json.loads(layout.precincts_geojson.read_text(encoding="utf-8"))["features"]
  print(len(flaechen), "Flächen", round(sum(shape(f["geometry"]).area for f in flaechen) / 1e6, 2), "km²")
  EOF
  ```

Weichen die Zahlen stark ab, hat die Stadt ihren Dienst geändert: dann erst `docs/decisions.md`,
Punkt 65 und `docs/plans/01-staedte.md`, § 3.2 gegen die neue Antwort halten. Antwortet der Dienst
mit einem `error`-Objekt (ArcGIS tut das mit HTTP 200), bricht `fetch opendata` mit genau dieser
Meldung ab und schreibt nichts.

Prüfpunkt: das Wahlergebnis aggregiert zu denselben Summen wie die Wahlbezirks-CSV der Quelle.

```bash
uv run georep --profile moenchengladbach run voters
uv run python - <<'EOF'
import polars as pl
v = pl.read_parquet("data/moenchengladbach/processed/wahlbezirke_waehler.parquet")
print(v.height, "Wahlbezirke")
print(v.select(pl.col("Wahlberechtigte_insgesamt").sum(), pl.col("Waehler").sum()))
EOF
```

Erwartet: 33 Wahlbezirke, 204 219 Wahlberechtigte, 96 880 Wähler.

## 3. Die Probe am Ratsinformationssystem (zwei Minuten)

```bash
uv run georep --profile moenchengladbach fetch papers --max-pages 1
```

Prüfpunkte: Exit 0; die Paper tragen `body` `…/bodies/0011`; die Drucksachennummern haben die Form
`1031/XI`; der Server liefert 200 je Seite und `links.next`. Am 2026-10-12 antwortete er in rund
3 s (nicht 85 s wie Düsseldorfs Body); das schwankt.

Fällt die Probe anders aus (fremde Stadt, leere Liste), nennt
`https://ris-oparl.itk-rheinland.de/Oparl/bodies` den Katalog; der Body gehört dann in
`profiles/moenchengladbach.toml` korrigiert, sonst ändert sich nichts.

## 4. Der lange Teil (3 bis 5 Stunden, wiederaufnehmbar)

```bash
# Metadaten der Wahlperiode; bricht ab, sobald eine Seite nur noch Paper vor period.start trägt
time uv run georep --profile moenchengladbach fetch papers

# Stichprobe von 200 PDFs, dann die Extraktion, dann der Markeranteil (Frage 1.5)
time uv run georep --profile moenchengladbach fetch pdfs --limit 200
uv run georep --profile moenchengladbach run texts
uv run python - <<'EOF'
import polars as pl
texts = pl.read_parquet("/media/konrad/xtraspace/georep/cache/moenchengladbach/text/texts.parquet")
marker = "betrifft"
share = texts.select((pl.col("text").str.to_lowercase().str.contains(marker)).mean()).item()
print(f"{texts.height} Texte, Marker {marker!r} in {share:.1%}")
EOF
```

**Entscheidungspunkt.** Liegt der Anteil unter 90 %, trägt das Vorlagenformat dieser Stadt den
Marker nicht; dann entweder einen anderen Marker in `profiles/moenchengladbach.toml` eintragen
(`search.text_split_marker`, zum Beispiel `gegenstand` oder `betreff` — das Skript oben mit dem
anderen Wort wiederholen) oder ihn so lassen und hinnehmen, dass die Kette den ganzen Text
durchsucht (dann zählen Treffer in Briefköpfen mit; `after_marker` schneidet ohne Vorkommen
nichts ab). Die Stichprobe vom 2026-10-12 fand den Marker in **0 von 5** Dokumenten, aber das
waren Fraktionsanträge der laufenden Periode, nicht Verwaltungsvorlagen von 2020 bis 2025.
Der gewählte Wert gehört als Satz in die `notes` des Profils.

```bash
# Der Rest der PDFs (Stunden; jederzeit abbrechbar, der Lauf nimmt wieder auf)
time uv run georep --profile moenchengladbach fetch pdfs

# Straßen und Orte: 179 Overpass- und 179 GeoSearch-Abfragen, rund 15 Minuten
time uv run georep --profile moenchengladbach fetch streets_osm pois_wiki

# Alles Offline-Übrige bis zur Seite
time uv run georep --profile moenchengladbach run
uv run georep --profile moenchengladbach status
```

`status` soll am Ende jeden Schritt als `aktuell` zeigen.

**Erfahrungen aus dem vollen Lauf Mönchengladbachs (2026-10-13), nach denen man nicht sucht:**

- **Nicht jede Hauptdatei ist abrufbar.** Von 2 871 Dokumenten mit `mainFile` lieferte das
  Ratsinformationssystem 658 aus, die übrigen 2 213 antworteten mit `404`. Der Abruf isoliert
  jeden Fehler und läuft durch; die Kette rechnet dann mit einem Bruchteil der Dokumente, und das
  verschiebt jede absolute Zahl der Stadt. Darum **vor** dem langen Teil die Stichprobe ansehen:
  `fetch pdfs --limit 200` und die Zeile des Schritts vergleichen (200 geholt heißt gut, 40 geholt
  heißt, dass dieselbe Quote für den ganzen Korpus zu erwarten ist). Die Quote gehört ins README
  des Pakets und in die Kernzahlen der Seite („*n* mit Text, *m* ohne").
- **Overpass weist ein großes `[timeout:N]` unter Last ab, ein kleines nicht.** Am 2026-10-13
  gaben alle vier öffentlichen Instanzen auf die Stimmbezirksabfrage nach wenigen Sekunden
  `504 Gateway Timeout`, mit 25 s Budget antwortete dieselbe Abfrage in 2 s: der Server schätzt
  die Kosten vorab gegen sein Slot-Budget. Die Zahl steht als `sources.osm.query_timeout_s` in
  den Settings (Vorgabe 25, `docs/decisions.md`, Punkt 54); wer sie hochdreht, macht es
  schlechter. Je Versuch kamen rund 27 Abfragen durch, dann endete der Schritt (gemessen an
  Düsseldorfs 306 Stimmbezirken; Mönchengladbach hat 180) — seit dem
  2026-10-13 wiederholt `fetch_street_names` einen 504 oder 429 selbst, bis zu
  `sources.osm.retries` mal je Stimmbezirk mit wachsender Pause (Punkt 55); die Session tut es
  nicht, ihre Retry-Regel erlaubt GET und HEAD, und die Abfrage ist ein POST. Bleiben trotzdem
  Bezirke offen, holt ein zweiter Aufruf von `fetch streets_osm` sie nach: der HTTP-Cache hält die
  schon geholten. Wer `query_timeout_s` ändert, verliert die gecachten Antworten (der POST-Body
  ist der Schlüssel) und macht jeden Stamp ungültig.
- **Die Instanz kann auch tagelang weg sein.** Vom 2026-10-14 bis zum 2026-10-15 wies
  overpass-api.de Mönchengladbachs 179 Abfragen fast durchgehend ab -- `504` mit
  `Dispatcher_Client::request_read_and_idx::timeout`, zeitweise `502` und `Connection refused`, und
  zwar bei vier freien Slots und auch für eine Trivialabfrage. Das ist nicht zu beheben, nur
  auszusitzen: eine Schleife mit fünf Minuten Pause, bis ein Durchlauf durchkommt (hier der 130.,
  nach 14 Stunden). Dass das überhaupt aufsetzt, liegt allein am HTTP-Cache, und sein Schlüssel ist
  Host, Methode und Abfragetext — **wer währenddessen Endpunkt, `query_timeout_s` oder
  `sources.osm.simplify_m` anfasst, fängt das Sammeln von vorn an**. Ob die Instanz überhaupt
  antwortet, sagt `curl https://overpass-api.de/api/status` zusammen mit einer Trivialabfrage;
  antwortet die auch nicht, liegt es nicht an den eigenen Polygonen.

Prüfpunkt Geometrie: die Zeile des Schritts `streets` nennt die Übereinstimmung mit dem
Straßenverzeichnis, etwa `Verzeichnis: 1 450 bekannte Straßennamen: 93,2 % im selben Stimmbezirk,
99,1 % im selben Wahlbezirk`. Unter 90 % je Wahlbezirk lohnt eine Anfrage an die Stadt nach den
Flächen von 2025 (Frage 1.3); die Seite nennt die Zahl ohnehin. Mönchengladbach lag mit **86,2 %**
(2 651 bekannte Namen, 66,5 % im selben Stimmbezirk) darunter, solange seine Flächen vom 08.06.2022
waren. Mit den Flächen des Wahltags sind es **88,8 %** und 70,8 % auf 2 667 Zuordnungen (gemessen
am 2026-10-15, `docs/decisions.md`, Punkt 65) — besser, aber **weiter unter der Grenze**.

Gezählt werden **Zuordnungen**, also Paare (Stimmbezirk, Straßenname), und nicht Namen: derselbe
Name kommt in mehreren Bezirken vor und zählt dann mehrfach. Mönchengladbach hat 2 982 solche
Paare über 1 814 verschiedene Namen; davon kennt das Verzeichnis 2 667 Paare (1 563 Namen), die
übrigen 315 Paare (251 Namen) nicht.

Daran ist zu lernen, wofür diese Grenze taugt: sie zeigt nicht nur veraltete Flächen an. Ein
Verzeichnis ordnet eine Straße über **Adressen** genau einem Stimmbezirk zu, Overpass liefert sie
über die **Geometrie** des Straßenzugs; ein Zug über eine Bezirksgrenze zählt dann in beiden, und
das drückt die Quote unabhängig vom Stand der Flächen. Wer die Zahl einer neuen Stadt beurteilt,
vergleiche darum zuerst je Wahlbezirk (gröber, verzeiht die Grenzfälle) und sehe sich die Namen an,
die das Verzeichnis gar nicht kennt (hier 315: Fußwege, Plätze, neue Straßen). Frage 1.3 ist
beantwortet, und die Mail an `gdi@moenchengladbach.de` bleibt eine Bitte um eine Datei statt einer
Operation, kein Hindernis.

## 4b. Die Gremien der Stadt (zehn Minuten, ein kleiner Netzschritt)

Ohne diesen Schritt steht die Stadt mit „Gremium unbekannt" auf ihrer Seite, wenn ihre
Drucksachennummern kein Kürzel tragen (`docs/decisions.md`, Punkt 58). Zwei Quellen gibt es: die
Nummer (`[bodies] reference_pattern`) und die **Beratungsfolge** aus OParl, also die Gremien, die
ein Dokument beraten haben.

```bash
# Der Katalog: welche Organisationen stehen überhaupt in einer Beratungsfolge?
uv run georep --profile <slug> learn-bodies
```

Der Befehl liest den Korpus und druckt je Organisation die Dokumente, das aus den Nummern gelernte
Kürzel mit seiner Reinheit und, wenn `raw/organizations.json` vorliegt, `shortName`,
`classification` und Namen vom Server. Danach gilt eines von beidem:

- **Die Nummern tragen Kürzel** (Düsseldorf): der Befehl druckt den fertigen `[bodies.organizations]`-Block.
  Er geht so, wie er ist, ins Stadtprofil; die Kommentare je Zeile nennen die Zahlen. Eine Zeile,
  deren Kürzel in keiner Tabelle des Profils steht, kommt **auskommentiert** heraus und mit dem
  Hinweis „NICHT GÜLTIG" — der Validator würde sie ablehnen. Entweder gehört das Kürzel in
  `[bodies.committees]` (dann erst wird die Zeile erlaubt), oder sie bleibt draußen.
- **Die Nummern tragen keine** (Mönchengladbach): dann ist aus ihnen nichts zu lernen, und die
  Namen müssen aus dem Organisationskatalog kommen:
  `uv run georep --profile <slug> fetch organizations` (eine Seite, Sekunden). Danach denselben
  Befehl noch einmal, und die Tabelle aus den Namen schreiben: `classification` `Bezirk` sind die
  Bezirksvertretungen (`BV1`, `BV2`, … mit `[bodies.district_body_names]`, wenn sie Namen statt
  Nummern tragen), `Ausschuss` die Ausschüsse, der Rat gehört in `[bodies.council]`, Beiräte,
  Integrations- und Seniorenräte in `[bodies.advisory]`. Die Kürzel sind frei wählbar; die
  `shortName` des Servers ohne Leerzeichen sind die naheliegende Wahl.

Zwei Prüfungen danach:

1. `uv run georep --profile <slug> learn-bodies` ein letztes Mal: die Gegenprobe soll wenige
   Widersprüche nennen, und unter „Unterschiede zur Tabelle im Profil" darf keine Zeile
   „Profil X, gelernt Y" stehen.
2. **Welche Bezirksvertretung welche Nummer hat**, ist zu belegen und nicht zu raten, wenn die
   Namen keine Nummer tragen. Das Maß dafür steht als Matrix in `profiles/moenchengladbach.toml`
   über `[bodies.district_body_names]`: Zeile ist die Bezirksvertretung, die die Folge **allein**
   nennt, Spalte der Stadtbezirk des getroffenen Wahlbezirks, gezählt in Dokument-Bezirk-Paaren
   (dort 167 Dokumente, 683 Paare). Die Diagonale muss in jeder Zeile **und** jeder Spalte die
   größte Zelle sein (dort 52 bis 61 % der Zeile). Eine falsche Zuordnung verdreht die Kennzahl
   „eigene Bezirksvertretung" still.

Trägt der Korpus der Stadt die Beratungsfolge nicht (nur die Hauptperiode Düsseldorfs, deren Daten
aus dem Altformat der Arbeit kommen), holt ein eigener Metadatenabruf sie, und
`georep pack --consultations snapshots/<slug>-beratungsfolge` legt sie als Paket ins Repo;
`[bodies].consultations` im Profil zeigt darauf.

## 4c. Die Urheber der Stadt (zwanzig Minuten, kein Netzschritt)

Ohne `[originators]` im Profil fehlt der Schritt `parties`, und die Stadtseite hat den Abschnitt
„Urheber und Parteien" nicht (`docs/decisions.md`, Punkte 59 und 60). Gebraucht werden zwei Dinge:
**die Fraktionen** und **jede Dokumentart**.

```bash
# Welche Dokumentarten hat die Stadt, und wie viele Dokumente je Art?
uv run python - <<'PY'
import collections, json, pathlib
rows = [json.loads(l) for l in pathlib.Path("reference/<slug>/raw/papers.jsonl").read_text("utf-8").splitlines()]
for typ, n in collections.Counter(r.get("paper_type") or "" for r in rows).most_common():
    print(f"{n:6d}  {typ!r}")
PY
# Und die Fraktionen aus dem Katalog von Schritt 4b
uv run python -c "
import json, pathlib
for o in json.loads(pathlib.Path('reference/<slug>/raw/organizations.json').read_text('utf-8')):
    if o.get('classification') == 'Fraktion':
        print(o['id'].rsplit('/organizations/')[-1], repr(o.get('shortName')), repr(o.get('name')))
"
```

**Jede Dokumentart gehört in genau eine Liste** — und wo keine passt, bleibt die Art draußen und
ihre Dokumente stehen sichtbar als „Urheber unbekannt" auf der Seite. Vier Listen gibt es:

| Liste | Bedeutung | Beispiel |
|---|---|---|
| `admin_types` | Vorlage der Verwaltung | `1.1 - Beratungsvorlage`, `Verwaltungsvorlage` |
| `citizen_types` | Bürgerantrag (§ 24 GO NRW) | `Eingabe nach 24GO` |
| `fraction_types` | **Klasse** Fraktion, Partei woanders | `3 - Fraktionsantrag` |
| `person_types` | **Klasse** Person | `6.1 - Mitgliederantrag` |

Nennt die Art die Partei schon selbst („Anfrage SPD"), braucht sie keine Liste: `motion_prefixes`
schneidet das Präfix ab, und die Parteimuster finden den Rest. Nennt sie nur die Klasse, gehört sie
in eine der beiden unteren Listen; dann steht die Klasse fest, und die Partei wird im Titel und im
ganzen Textkopf gesucht. Nennt sie gar nichts (Düsseldorfs nacktes „Antrag"), entscheiden Titel und
Textkopf über beides, und dafür braucht es `fraction_markers`, `text_markers` und `person_markers`.

Die Fraktionen werden `[[originators.parties]]`, wenn ihr Schlüssel in `columns.results.parties`
steht (nur dann gibt es einen Stimmenanteil zum Abgleich), sonst `[[originators.groups]]`. Jede
braucht mindestens ein Muster; **ein Muster, das nichts trifft, ist eine Behauptung ohne Beleg** und
gehört stattdessen in einen Kommentar. Zwei Fallen:

1. **Jedes Wort eines Parteimusters wird Stoppwort des Themenmodells** (`topics.stop_sources`).
   Ein Muster wie `alternative für deutschland` nimmt „alternative" und „deutschland" aus dem
   Vokabular; ein Sachwort holt `topics.stop_keep` zurück (so „klima" und „tierschutz" bei
   Düsseldorf).
2. **Ein Personenmarker im Textkopf trifft oft die Anrede** und nicht den Urheber („an herrn
   bezirksvorsteher"): in der Düsseldorfer Periode 2014 bis 2020 in 776 von 1 503 Fällen. Darum
   suchen die `person_markers` im Titel.

Zwei Prüfungen danach:

```bash
uv run georep --profile <slug> run            # die Zeile von `parties` nennt die Klassenanteile
uv run python -c "
import polars as pl
from georep.layout import Layout
from georep.settings import load_settings
s = load_settings(profile='<slug>'); lay = Layout.from_settings(s)
c = pl.read_parquet(lay.corpus); a = pl.read_parquet(lay.document_originators)
j = c.select('id','paper_type').join(a, on='id')
print(j.group_by('urheber_art').len().sort('len', descending=True))
print(j.filter(pl.col('urheber_art')=='unbekannt').group_by('paper_type').len().sort('len', descending=True))
"
```

Die zweite Zeile ist die wichtige: steht dort eine Dokumentart mit vielen Dokumenten, fehlt sie in
einer Liste. „unbekannt" soll **offen angezeigt** werden und nicht verschwinden — eine Art, deren
Klasse die Daten nicht hergeben, bekommt keine geratene.

## 5. Veröffentlichen und das Paket ins Repo

```bash
uv run georep run            # Düsseldorf, falls nicht aktuell
uv run georep publish        # erwartet „2 Städte, 1 Vergleich, … Dateien, … MB"
python3 -m http.server 8777 --directory data/site   # ansehen: /, /moenchengladbach/, /vergleich.html
```

Damit CI dieselbe Seite ohne Netz baut, kommt das Ergebnis des Laufs als Paket ins Repo
(Frage 1.2, erledigt am 2026-10-14; `docs/decisions.md`, Punkt 56). Das macht **ein Befehl**, die
Gegenrichtung von `bootstrap`:

```bash
uv run georep --profile moenchengladbach pack reference/moenchengladbach
du -sb reference/moenchengladbach   # 2026-10-13: 3 980 958 Bytes
# pack selbst nennt die Summe seiner Dateien (2026-10-15: 9 Dateien, 5 224 917 Bytes); du zaehlt
# das README mit, dessen Groesse sich mit jeder Zeile aendert, die man hineinschreibt.
```

`pack` kopiert genau die Dateien, die `bootstrap` später sucht — `external/`, `raw/papers.jsonl`,
Straßen und Orte (wenn das Profil sein Wörterbuch selbst holt) und den Textstore nach
`cache/text/`, denn `Layout.reference_view` setzt `cache_root` auf `<reference_root>/cache`. Nichts
Abgeleitetes, keine Stamps, kein `manifest.jsonl`, kein `http.sqlite`, keine PDFs. Es **bricht ab**,
statt ein halbes Paket zu schreiben, wenn

- eine Eingabe fehlt (dann lief `georep run` für dieses Profil nicht),
- der Textstore Zeilen trägt, die nicht aus einem Lauf dieses Profils kommen (Spalte `source`
  weder `pdf` noch `reference`) — am 2026-10-13 lagen fünf Zeilen aus `tests/fixtures/mg/` im Store
  der Stadt, und nur ein Blick von Hand hat sie gefunden,
- ein Text kein Paper in `papers.jsonl` hat (er fällt im Schritt `corpus` ohnehin heraus).

Vorhandene Dateien bleibt `pack` stehen; `--force` überschreibt sie. **Beim zweiten Packen
derselben Stadt ist das die Falle**: ohne `--force` meldet es jede Datei als übersprungen und das
Paket bleibt der alte Stand. Und `pack` **räumt nicht auf** — es schreibt die Dateien, die das
Profil heute nennt, und lässt liegen, was es früher nannte. Wechselt eine Stadt die Quellform ihrer
Flächen (Punkt 65: vom Shapefile-Zip zur `identify`-Antwort), ist die alte Datei von Hand zu
löschen; `tests/unit/test_data_packages.py` merkt es, weil die Prüfsummentabelle des READMEs dann
nicht mehr zu den Dateien im Ordner passt. Die Prüfsummentabelle druckt
es immer, und ein **fehlendes** `README.md` schreibt es als Gerüst: Tabelle, Größen und Zahlen
fertig, die Prosa als `[nachzutragen]`. Dort gehören hinein, nach dem Muster von
`reference/moenchengladbach/README.md`: Datum des Laufs, Zahl der Paper, Texte, Orte und Straßen,
die Quellen mit Lizenz, der Satz, dass die PDFs selbst **nicht** im Paket liegen, und was am Lauf
auffiel. Was im Paket sein darf, prüft `tests/unit/test_data_packages.py`; es hält auch die Größen
und die Prüfsummen gegen das README.

Danach baut `pages.yml` die zweite Stadt von selbst mit (der Schritt prüft, ob
`reference/moenchengladbach/` existiert), und `tests/golden/test_second_city.py` kann seine
Erwartungen vom Mini-Paket auf das echte umstellen.

## 6. Eine neue Stadt (keine Mönchengladbacher)

1. `cp src/georep/profiles/moenchengladbach.toml src/georep/profiles/<slug>.toml` und darin
   ändern: `profile`, `[city]` (Slug gleich dem Dateinamen), `[sources.oparl] endpoint` (Body aus
   `https://ris-oparl.itk-rheinland.de/Oparl/bodies`), `[sources.opendata]` (vier URLs und
   Dateinamen), `[sources.wikidata] entity`, `[precincts]` (Format und Regeln der Quelle),
   `[columns.results]` (Spalten und Parteien), `[search] exclude`, `[report]`.
2. `uv run georep profiles` muss die Stadt zeigen, `uv run georep --profile <slug> status` laufen.
   `[bodies]` und `[originators]` bleiben zunächst leer: die Gremien kommen in § 4b dazu und die
   Urheber in § 4c, wenn der Korpus steht und seine Dokumentarten zu zählen sind.
3. `publish.cities` in **allen** Profilen um den Slug erweitern (die Reihenfolge bestimmt, wer an
   der Wurzel liegt).
4. Dieses Runbook von § 1 an.

Was dabei auffällt, gehört in `docs/decisions.md`; was offen bleibt, in § 8 des Plans
`docs/plans/01-staedte.md`.
