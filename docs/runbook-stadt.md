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

Erwartet (gemessen am 2026-10-12): `30574 Bytes Wahlergebnis, 199548 Bytes Flächen
(shapefile-zip), Straßenverzeichnis, Wahlbezirksnamen` in 1,7 s, danach `180 Stimmbezirke in 33
Wahlbezirken, CRS EPSG:25832`. Weichen die Zahlen stark ab, hat die Stadt ihre Dateien ersetzt:
dann erst `docs/plans/01-staedte.md`, § 3.2 gegen die neue Datei halten.

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

Prüfpunkt Geometrie: die Zeile des Schritts `streets` nennt die Übereinstimmung mit dem
Straßenverzeichnis, etwa `Verzeichnis: 1 450 bekannte Straßennamen: 93,2 % im selben Stimmbezirk,
99,1 % im selben Wahlbezirk`. Unter 90 % je Wahlbezirk lohnt eine Anfrage an die Stadt nach den
Flächen von 2025 (Frage 1.3); die Seite nennt die Zahl ohnehin. Mönchengladbach liegt mit
**86,2 %** (2 651 bekannte Namen, 66,5 % im selben Stimmbezirk) darunter, weil seine Flächen vom
08.06.2022 sind — der Satz an `gdi@moenchengladbach.de` ist damit fällig und nicht mehr optional.

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

Vorhandene Dateien bleibt `pack` stehen; `--force` überschreibt sie. Die Prüfsummentabelle druckt
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
   `[bodies]` bleibt zunächst leer: die Gremien kommen in § 4b dazu, wenn der Korpus steht.
3. `publish.cities` in **allen** Profilen um den Slug erweitern (die Reihenfolge bestimmt, wer an
   der Wurzel liegt).
4. Dieses Runbook von § 1 an.

Was dabei auffällt, gehört in `docs/decisions.md`; was offen bleibt, in § 8 des Plans
`docs/plans/01-staedte.md`.
