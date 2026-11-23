# Runbook: Sitzungen, Tagesordnung, Beratungen und Personen abrufen

Stand 2026-11-23 (Fundament F6, `docs/plan-vorverarbeitung-2026-11.md`, § 7). Dieses Runbook führt
den Lauf aus, den kein Agent tun durfte: den vollen Abruf der Listen `meetings`, `consultations` und
`people` vom OParl-Server, je Profil. Alles davor ist gebaut und gegen aufgezeichnete Antworten
getestet: die Modelle in `georep.oparl`, der Listenabruf `fetch_objects`, die drei Netzschritte in
`georep.council`. Grundlage der Zahlen ist eine Netzstichprobe vom 2026-11-23 (41 s Antwortzeit,
`tests/fixtures/http/README.md`) und der Paper-Abruf vom 2026-10-13/14, dessen 510 Seiten noch im
HTTP-Cache liegen (nur lesend ausgewertet).

**Kurz:** Hauptperiode zuerst, je Schritt erst eine Seite als Probe, dann der Rest. Geschätzt rund
4 min für `meetings`, rund 2 min für `persons`; `consultations` ist nicht gemessen (wenige Minuten, wenn
die Liste so schnell ist wie die anderen flachen Listen, Stunden, wenn sie so langsam ist wie die
Paper-Liste) — die Probe entscheidet.

## 1. Was die drei Schritte tun

| Schritt | Liste (Profil `[council]`) | behält | schreibt unter `data_root/<profil>/raw/` |
|---|---|---|---|
| `meetings` | `…/meetings` mit eingebetteter Tagesordnung | Sitzungen ab `period.start`, **ohne** Obergrenze (eine Vorlage vom Periodenende wird oft erst danach beraten); Abbruch nach der ersten Seite, die ganz vor dem Beginn liegt | `meetings.jsonl` (ohne Tagesordnung), `agenda_items.jsonl` |
| `consultations` | `…/consultations` | alle Beratungen des Bodys | `consultations.jsonl` |
| `persons` | `…/people` mit eingebetteten Mitgliedschaften | alle Personen des Bodys, **ohne** Telefon, E-Mail, Anschrift (das Modell kennt sie nicht) | `persons.jsonl`, `memberships.jsonl` |

Eine Zeile je Objekt, sortiert nach ID, mit den Schlüsseln von OParl (`agendaItem`, `votingRight` …).
Die Liste `…/memberships` wird nicht gebraucht: die eingebetteten Mitgliedschaften sind dieselben
Objekte (80 von 80 gleich in der Stichprobe). Die Listen sind je Body, nicht je Periode: die drei
Düsseldorfer Profile lesen dieselben Personen und Beratungen, nur die Sitzungen schneidet jedes Profil
an seinem Beginn.

Jede Seite geht sofort in eine Teildatei (`*.jsonl.partial`), der Fortschritt nach
`<schritt>.progress.json`. Erst ein vollständiger Abruf ersetzt die Ausgabe, atomar; bis dahin bleibt
die alte Datei, wie sie war. `modified_since` (jüngstes `modified` minus ein Tag) nutzt nur
`consultations` (`council.incremental`): bei Sitzungen und Personen folgt `modified` den eingebetteten
Objekten nicht (§ 2), ein Lauf mit Filter verpasste nachgetragene Ergebnisse. Beide holen darum jedes
Mal alles; das kostet wenige Minuten.

## 2. Was der Server füllt

Gemessen am 2026-11-23. Sitzungen: zwei Seiten der Liste (Seite 1: 200 Sitzungen, angelegt
2025-12 bis 2026-11, Beginn 2026-01 bis 2027-12, also auch geplante; Seite 4: 200 Sitzungen, Beginn
2022-08 bis 2024-12). Beratungen: die 25 675 eingebetteten Beratungen der Paper der Hauptperiode im
HTTP-Cache (Paper-Abruf 2026-10-14). Personen: die erste Seite (200 Personen, 630 Mitgliedschaften).

| Objekt, Feld | gefüllt | Bemerkung |
|---|---|---|
| Sitzung `agendaItem` | 62,0 % (S. 1), 95,0 % (S. 4) | auf S. 1 fehlt sie den geplanten; von den 114 vergangenen Sitzungen auf S. 1 haben 112 eine |
| Sitzung `resultsProtocol` | 36,0 % / 70,0 % | **immer dieselbe Datei wie `invitation` und `verbatimProtocol`** (72 von 72, 140 von 140), und die ist ein Nachtrag zur Tagesordnung („NachtragsTO", „1. Nachlieferung", „Sitzungspaket Ö"), **keine Niederschrift** |
| Sitzung `auxiliaryFile` „Niederschrift …" | 93 % (186 von 200, S. 4); 60 der 114 vergangenen auf S. 1 | die eigentliche Niederschrift, Name „Niederschrift Ö"; `size` setzt der Server nicht |
| Sitzung `cancelled`, `meetingState` | 0 von 400 | abgesagte Sitzungen sind nicht erkennbar |
| Sitzung `participant` | 51,5 % / 95,0 % | URLs auf Personen |
| Sitzung `organization` | 100 % | 395 von 400 mit genau einem Gremium |
| Tagesordnungspunkt `result` | **70,7 % / 80,2 %**; mit Beratung **84,4 % / 96,5 %** (vergangene Sitzungen auf S. 1: 95,4 %) | ein fester Wortschatz: „einstimmig beschlossen", „zur Kenntnis genommen", „mehrheitlich abgelehnt", „vertagt", „abweichend beschlossen", „zurückgezogen", „beantwortet", „Empfehlung … beschlossen", „passieren lassen" … (rund 20 Werte) |
| Tagesordnungspunkt `consultation` | 73,2 % / 70,3 % | Punkte ohne Beratung sind Verfahren (Beschlussfähigkeit, Tagesordnung, Mitteilungen) |
| Tagesordnungspunkt `resolutionText`, `resolutionFile` | **0 von 9 495** | der Beschlusstext steht nur in der Vorlage oder der Niederschrift |
| Tagesordnungspunkt `public`, `start`, `end` | immer wahr, nie, nie | die Liste enthält nur öffentliche Punkte |
| Beratung `meeting`, `agendaItem` | **98,9 %** | über alle vier Datensätze im Cache 68 799 von 69 844 (98,5 %) |
| Beratung `role` | 100 % | aber „-" bei 13,0 % der Hauptperiode und 80,4 % der Periode 2014 bis 2020 |
| Beratung `authoritative` | 91,4 % | sonst fehlt es; `false` kommt nicht vor |
| Beratung `organization` | 98,3 % | das beratende Gremium (Punkt 58) |
| Person `name`, `familyName`, `givenName` | 100 % | dazu `formOfAddress` 97 %, `gender` 88 %, `title` 3 %, `affix`, `status`, `life` nie |
| Mitgliedschaft `role` | **100 %** | freier Text: „ordentliches Mitglied", „stellvertretendes Mitglied", „Fraktion Mitarbeiter/in", „sachkundige Einwohnerin (beratend)" … |
| Mitgliedschaft `startDate`, `endDate` | 100 %, 7,3 % | die erste Seite ist die jüngste, beendete stehen weiter hinten |
| Mitgliedschaft `votingRight` | 63,8 % | sonst fehlt es |
| Mitgliedschaft `onBehalfOf` | 0 % | |

Zwei Befunde mit Folgen für die Schritte: Bei 69 von 314 Sitzungen mit Tagesordnung ist ein Punkt
jünger als die Sitzung (bis 245 Tage), bei 91 von 198 Personen eine Mitgliedschaft jünger als die
Person — darum kein `modified_since` für beide (§ 1). Und die Personenliste nennt alle Personen des
Bodys, auch Fraktionsmitarbeiter, Verwaltung und sachkundige Einwohner; wer Mandatsträger ist, sagt die
Rolle der Mitgliedschaft (Vorhaben 27).

## 3. Der billigste Weg vom Paper zum Ergebnis

**Die Paper-Liste trägt die Verbindung schon.** Jede in ein Paper eingebettete Beratung nennt
`meeting` und `agendaItem` (98,9 %), und jeder Tagesordnungspunkt nennt seine Beratung
(`consultation`). Für das Ergebnis fehlt nur die Tagesordnung, also der Schritt `meetings`; die
19 108 Paper müssen **nicht** neu abgerufen werden:

```
Paper ── consultation[] (id, agendaItem, meeting, role, authoritative)   aus der Paper-Liste
              │ id
              ▼
         agendaItem.consultation ── agendaItem (number, name, result) ── meeting (start, organization)
```

Verbunden wird über `agendaItem.consultation == consultation.id`, nicht über
`consultation.agendaItem == agendaItem.id`: eine vertagte Vorlage steht auf zwei Tagesordnungen, beide
Punkte nennen dieselbe Beratung, die Beratung aber nur den späteren. Auf Seite 4 der Sitzungsliste
finden sich 3 880 der 3 888 Beratungs-IDs der Punkte (99,8 %) in den Paper-Seiten im Cache; bei 340
davon zeigt die Beratung auf einen anderen, späteren Punkt — genau diese Fälle. Für die 3 017 Paper,
die in den 200 Sitzungen dieser Seite beraten wurden, steht dort ein Ergebnis bei 96,4 % der Anträge,
95,2 % der Anfragen und 99,6 % der übrigen. Als Rückfall taugt der Titel: `agendaItem.name` ist bei
3 778 von 3 880 Punkten (97,4 %) wortgleich mit dem Titel des Papers.

**Woher die Beratungen kommen**, drei Wege:

1. *Aus dem HTTP-Cache, ohne Netz.* `cache_root/http.sqlite` hält die 510 Paper-Seiten des Abrufs
   vom 2026-10-13/14 (alle 48 313 Dokumente der vier Datensätze, 69 844 Beratungen). Ein einmaliger
   Auszug **nur lesend** (wie der von Vorhaben 14) mit `id`, `paper`, `meeting`, `agendaItem`, `role`,
   `authoritative`, `organization` je Beratung, als Paket wie die Beratungsfolge (Punkt 58), reicht
   für alle Paper bis zum 2026-10-14. **Der Auszug von Vorhaben 14**
   (`messdaten/14-vorgaenge/oparl_papiere.parquet`) **reicht dafür nicht**: er hält `sitzungen` und
   `rollen`, aber weder `agendaItem` noch die ID der Beratung; mit ihm fände ein Paper seine Sitzung,
   den Punkt aber nur über den Titel. Er müsste um diese zwei Spalten wachsen.
2. *Der Schritt `consultations`* holt dieselben Objekte aus der Liste — dauerhaft, unabhängig vom
   Cache und auch für Paper nach dem 2026-10-14; die Dauer ist offen (§ 4).
3. *Künftig der Schritt `papers`.* `PaperRecord` verwirft heute alles außer
   `consultation_organizations`. Empfehlung: der Abruf behält die Beratungen **ganz**
   (`OparlPaper.consultations` liefert sie schon typisiert), nicht nur `meeting` und `role` — der
   Schlüssel zum Ergebnis ist `agendaItem` beziehungsweise die ID. Ebenso `auxiliaryFile` (Name,
   Datum, ID; Vorhaben 14 braucht die Anlagen) und `subordinatedPaper`/`superordinatedPaper`. Am
   einfachsten nicht als Felder von `PaperRecord` (der Record ist der Korpus, und jedes neue Feld
   ändert dessen Schema), sondern als eigene Dateien, die der Schritt `papers` neben
   `raw/papers.jsonl` schreibt. Das berührt `oparl.py`, `records.py` und `pipeline.py` und gehört in
   die Stufe 2 von Vorhaben 14 oder 26.

**Was `subordinatedPaper` bedeutet** (Frage 9.11 aus `docs/plans/14-vorgaenge.md`, gemessen im
Cache): 196 Paare, 195 in Düsseldorf, symmetrisch (jedes untergeordnete Paper nennt das andere als
`superordinatedPaper`). In 177 Paaren ist die Nummer des übergeordneten die des untergeordneten plus
`/N` (`OVA/136/2021/1` über `OVA/136/2021`), 182 tragen denselben Titel, und das übergeordnete ist nie
älter. Es ist also die **Neufassung oder Fortschreibung einer Vorlage über ihrer ersten Fassung**,
meist bei Beschlussvorlagen (126). Nur 49 Paare teilen eine Sitzung.

**Reicht die Stichprobe für das Ergebnis?** Nein: sie hat 400 der rund 3 700 Sitzungen (in den
Beratungen im Cache kommen 3 675 verschiedene Sitzungen vor, 2 928 in Düsseldorf, 747 in
Mönchengladbach). Für die Ergebnisse aller Paper braucht es den Schritt `meetings`; die Beratungen
kann Weg 1 oder 2 liefern.

## 4. Hochrechnung

Sekunden je Seite aus der Stichprobe (Antwortzeit bis zum letzten Byte, 200 Objekte je Seite), dazu
eine Sekunde Pause je Seite. Der Rechner lief dabei unter fremder Last (Lastmittel um 18:30 Uhr 87,
im 15-Minuten-Mittel 60); die Zeiten sind überwiegend die des Servers, aber eher obere Grenzen. Am
2026-10-09 brauchte die Paper-Liste 85 s je Seite, am 2026-10-14 im Mittel 18 s (122 Seiten in 36
Minuten): der Server schwankt um das Vierfache, darum steht daneben der schlechte Fall.

| Liste | gemessen | Größe je Seite | Objekte (geschätzt) | Seiten |
|---|---|---|---|---|
| `meetings` (0015) | 15,0 s und 20,3 s | 2,9 und 4,0 MB | rund 3 300 bis 3 600 Sitzungen seit 2013: 2 928 in Beratungen genannt, 93 % der Sitzungen von S. 4 werden genannt, dazu geplante | 17 bis 18 |
| `people` (0015) | 4,7 s | 0,4 MB | unbekannt; höchstens rund 5 000 (Mitgliedschafts-IDs bis 28 073, 3,15 je Person) | bis rund 25 |
| `consultations` (0015) | **nicht gemessen** | — | 61 350 Beratungen in den Paper-Seiten seit 2013 | rund 310 |
| `agendaitems`, `memberships` | 0,77 s, 0,19 s | 0,1 MB | (nicht gebraucht; zeigt, wie schnell eine flache Liste ist) | — |

Je Profil:

| Profil | `meetings` | `persons` | `consultations` |
|---|---|---|---|
| `duesseldorf` (Beginn 2020-09-13) | rund 1 700 Sitzungen ab Beginn, 9 bis 10 Seiten: **rund 3 min**, schlechter Fall 14 min | bis 25 Seiten: **rund 2,5 min** | 310 Seiten: rund 10 min wie eine flache Liste (1 s + 1 s Pause), schlechter Fall wie die Paper-Liste 1,5 bis 7 h |
| `duesseldorf-2025` (Beginn 2025-09-15) | 2 bis 3 Seiten: rund 1 min | wie oben (dieselbe Liste) | wie oben; danach nur Geändertes |
| `duesseldorf-2014` (Beginn 2014-05-25) | fast die ganze Liste, 17 bis 18 Seiten: rund 6 min, schlechter Fall 26 min | wie oben | wie oben |
| `moenchengladbach` (Body 0011) | rund 800 Sitzungen, 4 bis 5 Seiten: rund 1,5 min (Liste nicht gemessen) | nicht gemessen | 8 494 Beratungen, 43 Seiten: rund 1,5 min oder bis 1 h |

**Platz**: `meetings` überträgt rund 70 MB (Düsseldorf, ganze Liste) und schreibt geschätzt 10 MB
Sitzungen und 40 MB Tagesordnung (rund 90 000 Punkte); `consultations.jsonl` rund 35 MB,
`persons.jsonl` und `memberships.jsonl` zusammen wenige MB. Unter 100 MB je Profil, während eines
Laufs doppelt (Teildateien). Die Seiten der drei Listen fallen unter keine Cache-Regel, `http.sqlite`
wächst also nicht.

## 5. Der Lauf

### 5.1 Vorbereitung

```bash
cd ~/files/work/__drafts/geographic-representation-dus
git switch main && git pull
export UV_PROJECT_ENVIRONMENT=/media/konrad/xtraspace/venvs/georep UV_CACHE_DIR=/media/konrad/xtraspace/uv-cache
uv sync
df -h /media/konrad/xtraspace          # unter 1 GB für alle vier Profile
uv run georep fetch --dry-run meetings consultations persons
```

Erwartet: drei Zeilen `geplant` mit „Ausgabe fehlt", danach `3 geplant`. Steht ein Schritt nicht da,
fehlt sein Endpunkt im Profil (`[council]`).

### 5.2 Hauptperiode: erst je eine Seite, dann der Rest

```bash
uv run georep fetch meetings --max-pages 1        # ~20 s: "1 Seite(n), 200 gesehen, 200 behalten; weiter bei …"
uv run georep fetch persons --max-pages 1         # ~5 s
uv run georep fetch consultations --max-pages 1   # die eine unbekannte Zahl: Sekunden oder eine Minute?
```

Die Zeile nennt die Dauer in Klammern. Eine Probe ist der **Anfang** des Abrufs: ihre Seite liegt in
der Ausgabe und in der Teildatei, der Fortschritt zeigt auf Seite 2, und der nächste Lauf ohne
`--max-pages` setzt dort fort. Dauert die Probe von `consultations` mehr als 30 s, lohnt Weg 1 aus § 3
statt des vollen Abrufs; dann `consultations` nicht weiter abrufen und die Frage an den Supervisor
geben.

```bash
uv run georep fetch meetings persons consultations
uv run georep status | grep -E "meetings|persons|consultations"   # dreimal "aktuell"
```

Erwartete Zeilen (Zahlen gerundet): `meetings … vollständig (fortgesetzt): 9 Seite(n) …; Rest älter als
der Periodenbeginn; ~1 700 Sitzungen, ~45 000 Tagesordnungspunkte, ~80% mit Ergebnis, ~70% mit
Beratung`; `persons … N Personen, M Mitgliedschaften, ~60% mit Stimmrecht` (N und M sind nicht geschätzt, nur ihre Obergrenze, § 4); `consultations
… ~61 000 Beratungen, ~98% mit Sitzung und Tagesordnungspunkt`. Weicht der Anteil mit Ergebnis oder mit
Sitzung um mehr als zehn Punkte ab, hat sich der Server geändert: § 2 und die Tests in
`tests/unit/test_oparl_council.py` sagen, was vorher galt.

### 5.3 Die anderen Profile

```bash
uv run georep --profile duesseldorf-2025 fetch meetings persons consultations
uv run georep --profile duesseldorf-2014 fetch meetings persons consultations
uv run georep --profile moenchengladbach fetch meetings --max-pages 1   # die Endpunkte von Body 0011 sind nicht abgerufen
uv run georep --profile moenchengladbach fetch meetings persons consultations
```

`persons` und `consultations` sind je Body dieselben Listen; wer Zeit sparen will, kopiert die beiden
Dateien der Hauptperiode in die beiden anderen Düsseldorfer Profile, statt sie dreimal zu holen
(`raw/persons.jsonl`, `raw/memberships.jsonl`, `raw/consultations.jsonl`), und läuft dort nur
`meetings`. Ihr Stamp fehlt dann; `georep status` zeigt sie als „offen", und ein späteres `fetch` holt
sie trotzdem.

### 5.4 Abbrechen und fortsetzen

- **Abbrechen** mit Strg-C, jederzeit. Die Ausgabe bleibt die des letzten vollständigen Laufs; die
  geholten Seiten liegen in `raw/<datei>.jsonl.partial`, die nächste URL in
  `raw/<schritt>.progress.json`.
- **Fortsetzen**: derselbe Befehl. Die Zeile sagt „(fortgesetzt)". Ein Netzfehler (`NetworkError`, eine
  Zeile auf stderr, Exit 1) ist dasselbe wie ein Abbruch.
- **Neu beginnen**: `raw/<schritt>.progress.json` und die `.partial`-Dateien löschen. `--force` tut
  das **nicht**: es umgeht den Stamp, nicht den Fortschritt (wie bei `papers`).
- **Später nachholen**: `fetch meetings persons consultations --force`. `consultations` fragt dann
  nur nach Geändertem; `meetings` und `persons` holen alles neu (§ 1).

## 6. Was danach offline läuft

Heute nichts: kein Schritt der Kette liest die fünf Dateien, die Seite ändert sich nicht. Sie sind
die Eingaben der Vorhaben 26 (Beschlusslage), 27 (Personen und Mandatstyp) und 28 (Abstimmungen), die
sie über `georep.council.council_files(layout)` finden und mit den Modellen aus `georep.oparl` lesen
(`JsonlStore(path, OparlAgendaItem).load()`). Eine Prüfung von Hand, wie viel der Server gefüllt hat:

```bash
uv run python - <<'EOF'
from georep.council import JsonlStore, council_files
from georep.layout import Layout
from georep.oparl import OparlAgendaItem, OparlMeeting
from georep.settings import load_settings
files = council_files(Layout.from_settings(load_settings()))
items = JsonlStore(files.agenda_items, OparlAgendaItem).load().values()
meetings = JsonlStore(files.meetings, OparlMeeting).load().values()
print(len(meetings), "Sitzungen,", sum(1 for m in meetings if any((f.name or "").startswith("Niederschrift") for f in m.auxiliary_file)), "mit Niederschrift")
print(len(items), "Punkte,", sum(1 for i in items if i.result), "mit Ergebnis,", sum(1 for i in items if i.consultation), "mit Beratung")
EOF
```

Ins Repo kommt davon nichts, bevor ein Vorhaben sagt, welche abgeleitete Tabelle es braucht; die
Personendaten bleiben lokal (Namen sind öffentlich, aber nur Mandatsträger in ihrer Rolle gehören auf
die Seite, `docs/plan-vorverarbeitung-2026-11.md`, § 1).

## 7. Niederschriften (PDF): holen oder nicht?

**Was es gibt.** Die Niederschrift einer Sitzung ist eine Anlage (`auxiliaryFile`) mit dem Namen
„Niederschrift Ö" (öffentlicher Teil), nicht `resultsProtocol` (§ 2). 93 % der Sitzungen auf Seite 4
haben eine, auf Seite 1 die Hälfte der vergangenen (die jüngsten sind noch nicht geschrieben). Für die
Hauptperiode sind das geschätzt **1 400 bis 1 600 PDFs**, für alle Düsseldorfer Perioden rund 3 000,
für Mönchengladbach rund 700.

**Größe.** Der Server nennt keine; ein `HEAD` auf die Niederschrift des Haupt- und Finanzausschusses
vom 2024-12-02 (31 Punkte) gab 348 439 Bytes. Mit 0,2 bis 1 MB je Stück sind es für die Hauptperiode
0,3 bis 1,5 GB, für alle Perioden bis 3 GB.

**Dauer.** Die Paper-PDFs kamen am 2026-11-17/18 mit 1,1 s je Datei (17 892 in 5 h 35 min, eine
Sekunde Pause inklusive): die Hauptperiode in rund 30 min, alle Perioden in rund einer Stunde.

**Empfehlung: jetzt nicht.** Vorhaben 26 (Beschlusslage) braucht sie nicht, `result` trägt das
Ergebnis je Punkt mit 96,5 %; „einstimmig" und „mehrheitlich" stehen schon dort. Erst wer wissen will,
**wer** wie gestimmt hat (Vorhaben 28, „mit den Stimmen der …", die WZB-Schwelle), braucht den Text.
Dafür zuerst eine Stichprobe von 50 Niederschriften lesen (Stufe 1 von 28), dann entscheiden. Gebaut
ist der Abruf nicht; ein Schritt `minutes` läse die Anlagen aus `raw/meetings.jsonl` (Name beginnt mit
einem Präfix aus dem Profil, „Niederschrift"), lüde sie wie `pdfs` in `cache_root/<profil>/minutes/`
und extrahierte den Text wie `texts`.

## 8. Offen

- Die Liste `consultations` ist nicht gemessen (die Freigabe galt für Einzelobjekte). Die Probe in
  § 5.2 ist die Messung.
- Die Zahl der Personen und die Dauer von `people` über mehr als eine Seite sind geschätzt.
- Die Endpunkte von Mönchengladbach (Body 0011) stehen nach dem Muster von Body 0015 im Profil; ihr
  Body-Objekt ist nicht abgerufen.
- `fetch papers --max-pages 1` auf einem leeren Store, danach `fetch papers`: der zweite Lauf holt
  inkrementell nur, was sich seit dem jüngsten `modified` der Probe geändert hat. Die drei neuen
  Schritte setzen nach einer Probe fort (`georep.council`), `papers` nicht.
