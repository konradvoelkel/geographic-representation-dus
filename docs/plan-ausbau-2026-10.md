# Meta-Plan: Ausbau in acht Optionen mit Supervisor und Unteragenten

Stand 2026-10-11, Auftrag von Konrad am selben Tag. Dieser Plan ist für einen frischen Supervisor-Agenten
geschrieben: er liest diese Datei und führt sie aus. Er beschreibt Ziel, Regeln, Rollen, Phasen mit
Abnahmekriterien, ein Briefing je Option, die Protokolle für Fragen und Merges, und die Prompts, mit denen der
Supervisor die Unteragenten startet. Alles Projektspezifische (Regeln, Umgebung, Lehren) steht in
[../CLAUDE.md](../CLAUDE.md), der Aufbau in [architecture.md](architecture.md), die Gründe in
[decisions.md](decisions.md), der Stand in [../STATUS.md](../STATUS.md). Vorbild für Form und Tiefe der
Einzelpläne ist [plan-report-2026-10.md](plan-report-2026-10.md), der abgeschlossene Plan der Berichtsseite.

## 1. Ziel und Rahmen

Acht Erweiterungen des Projekts, je eine auf einem eigenen Branch, je ein Unteragent; zuerst je ein
Implementierungsplan, dann eine Synergiephase des Supervisors über alle Pläne, dann die Implementierung, dann
Review und Merge nach `main`. Jede Erweiterung endet als Teil der veröffentlichten Berichtsseite oder der
Pipeline, dokumentiert, getestet, versioniert.

Die acht Optionen (Nummern bleiben über alle Dateien und Branches gleich):

| Nr. | Name | Branch | Kurzfassung | Netz nötig |
|---|---|---|---|---|
| 1 | Städte | `feat/01-staedte` | dieselbe Kette für weitere Kommunen am OParl-Server der ITK Rheinland, Städtevergleich | ja, Stunden |
| 2 | Zeitreihe | `feat/02-zeitreihe` | Wahlperiode 2014 bis 2020 mit den Wahlbezirken von 2020, Umrechnung auf 2025, Vergleich der Perioden | ja, Stunden |
| 3 | Kontrollvariablen | `feat/03-kontrollvariablen` | Quartiersatlas, Altersstruktur, Parteianteile; multiples Regressionsmodell; „Tabelle 6" | klein, einmalig |
| 4 | Parteien | `feat/04-parteien` | Urheber der Vorlagen (Fraktion, Person); wer erwähnt welchen Bezirk, Abgleich mit Hochburgen | ja, Stunden |
| 5 | Gremien | `feat/05-gremien` | Bezirksvertretungen gegen Rat aus den Drucksachennummern; Kennzahl und Karte je Gremium | nein |
| 6 | Gewichtung | `feat/06-gewichtung` | Spezifität je Begriff, Dokumentart, Themenmodell; gewichtete Trefferquote mit Sensitivitätstabelle | nein |
| 7 | Monitoring | `feat/07-monitoring` | laufende Wahlperiode 2025 bis 2030 inkrementell abrufen und auf der Seite zeigen | ja, laufend |
| 8 | Suche | `feat/08-suche` | Suchfeld „Straße oder Ort" auf der Seite, Vorschläge aus dem Wörterbuch, Bezirke, Dokumente, Karte | nein |

Zurückgestellt: Option 9 (Qualität der Operationalisierung, Annotation, Entity Linking). Fernziel: Option 10
(`georep` als konfigurierbares Paket, Methodennotiz, Lehrmaterial). Für 10 gilt ab jetzt in jedem Branch:
nichts Düsseldorf-Spezifisches im Code, alles in Settings; klare Modulgrenzen; Docstrings, die auf die
lebenden Beschreibungen verweisen; Verträge an Batch-Grenzen; jede Entscheidung mit verworfener Alternative in
`decisions.md`; keine neue Abhängigkeit ohne Begründung dort und ohne Prüfung durch `nox -s deps`.

## 2. Regeln, die über CLAUDE.md hinausgehen

- **Branches sind für dieses Vorhaben ausdrücklich gewünscht** (Konrad, 2026-10-11); die Regel „direkt auf
  `main`" in CLAUDE.md ist dafür ausgesetzt. `main` bleibt immer grün und trägt den letzten Tag. Branches
  heißen `feat/NN-name` wie in der Tabelle; Rebase auf `main` vor jedem Merge, kein Merge mit rotem `nox`.
- **Unteragenten reden nie mit Konrad.** Fragen kommen in den Abschnitt „Offene Fragen" ihres Plans; der
  Supervisor sammelt sie in [plans/fragen.md](plans/fragen.md) und gibt sie gebündelt weiter (§ 6). Ein Agent
  arbeitet weiter unter einer ausdrücklich notierten Annahme, wenn die Frage nicht blockiert.
- **Netzabrufe nur, wenn Konrad sie für die Option freigegeben hat** (§ 9, Frage 1). Bis dahin bereiten die
  Netz-Optionen alles vor (Settings, Fetcher, Tests mit aufgezeichneten Antworten in `tests/fixtures/http/`,
  Trockenlauf mit `--dry-run`) und markieren den Abruf als eigenen, von Hand zu startenden Schritt.
- **Nie unter `reference/` schreiben, nie `tests/fixtures/mini/expected/` neu erzeugen**; jede Option, die
  eine zweite Stadt oder Periode braucht, legt eine eigene kleine Fixture an (`tests/fixtures/<name>/`) mit
  README zur Herkunft.
- **Die Berichtsseite hat ein Budget**: `index.html` unter 1,5 MB, ohne Fremdressourcen (nur `karte.html`
  darf sie). Wächst die Seite durch mehrere Optionen darüber, entscheidet die Synergiephase über Unterseiten
  (ein Aufbau wie `karte.html`: eigene Vorlage, eigene Allowlist, Link von `index.html`).
- **Jede Zahl auf der Seite kommt aus den Daten**, nichts fest kodiert; Zeit und Commit sind Eingaben
  (`now`, `commit`), wie in `report/build.py`.
- **Die Arbeit von Lukas Bartzsch ist nicht öffentlich.** Nichts daraus zitieren oder ins Repo übernehmen;
  Verweise nur auf sein öffentliches Repository (`THESIS` in `report/render.py`).
- **Commit-Hygiene** wie in CLAUDE.md: eine Sorte pro Commit, Verhaltensänderung mit rotem Test zuerst,
  `uv run nox` nach jedem Commit, Prüfschritte nie hinter eine Pipe. Snapshots nie blind erneuern.

## 3. Rollen

**Supervisor** (ein frischer Agent, startet mit dem Prompt in § 10): richtet die Umgebung ein (Phase 0),
startet die Unteragenten, liest alle Pläne, schreibt die Synergien und das Fundament, bündelt Fragen,
reviewt, merged, versioniert, hält `STATUS.md` und diesen Plan nach. Er implementiert selbst nur das
Fundament (§ 5, Phase 2) und Korrekturen beim Merge.

**Unteragent NN** (je Option einer, Agent-Werkzeug mit `isolation: "worktree"` oder ein von Hand angelegter
Worktree, siehe Phase 0): schreibt zuerst den Plan `docs/plans/NN-name.md` auf seinem Branch, implementiert
später nach dem (gegebenenfalls umgeschriebenen) Plan, meldet Ergebnis und Fragen an den Supervisor. Er
kennt nur sein Briefing (§ 7), CLAUDE.md und die lebenden Dokumente.

**Konrad**: beantwortet die gebündelten Fragen, gibt Netzabrufe frei, entscheidet über Merge-Modus und
Versionierung (§ 9).

## 4. Umgebung für acht parallele Worktrees

Auf Konrads Rechner ist die Primärplatte voll (97 % am 2026-10-11); alles Schwere liegt auf
`/media/konrad/xtraspace`. Je Worktree:

```bash
# einmal je Option, aus dem Hauptklon heraus; NN und name wie in der Tabelle
git worktree add /media/konrad/xtraspace/georep/worktrees/NN-name -b feat/NN-name main
cd /media/konrad/xtraspace/georep/worktrees/NN-name
export UV_PROJECT_ENVIRONMENT=/media/konrad/xtraspace/venvs/georep-NN-name
export UV_CACHE_DIR=/media/konrad/xtraspace/uv-cache
cat > settings.local.toml <<EOT
data_root = "/media/konrad/xtraspace/georep/worktrees/NN-name/data"
cache_root = "/media/konrad/xtraspace/georep/cache"
EOT
uv sync && uv run nox && uv run georep bootstrap && uv run georep run
```

`settings.local.toml` ist gitignored und fehlt daher in jedem neuen Worktree; ohne sie landet `./data` auf
der vollen Primärplatte. Der Cache (`cache_root`) darf geteilt werden (PDFs, HTTP-Cache sind nach Inhalt
adressiert); `data_root` ist je Worktree eigen, weil Stamps und Ergebnisse sonst kollidieren. Jeder
Unteragent setzt die beiden `UV_*`-Variablen in jedem Shell-Aufruf (Shell-Zustand hält nicht über Aufrufe).

Rechnerlast: `nox -s test` nutzt alle Kerne (`-n auto`). Während der Implementierung laufen die
Unteragenten in Wellen (§ 5, Phase 3) und rufen im Alltag `uv run pytest -n 2 …`, das volle `nox` nur vor
jedem Commit. Der Supervisor prüft vor der ersten Welle mit `nproc` und `free -g`, wie viele Agenten
gleichzeitig tragbar sind (Faustregel: ein Agent je vier Kerne und je 4 GB frei).

Worktrees und Venvs räumt der Supervisor nach dem Merge der Option auf (`git worktree remove`, Venv löschen).

## 5. Phasen und Abnahmekriterien

### Phase 0: Einrichtung (Supervisor)

1. Einstieg nach CLAUDE.md: `main` aktuell, `uv run nox`, `uv run pytest -m slow` grün.
2. Lesen: CLAUDE.md, STATUS.md, architecture.md, decisions.md, plan-report-2026-10.md (als Vorbild), diesen
   Plan ganz, dann `src/georep/pipeline.py`, `settings.py`, `report/build.py`, `report/model.py`.
3. `docs/plans/` anlegen mit `fragen.md` (leer, Kopf nach § 6) und `README.md` (Index der Pläne und ihr
   Status: geplant, umgeschrieben, in Arbeit, im Review, gemerged).
4. CLAUDE.md ergänzen: Ausnahme von der Branch-Regel für dieses Vorhaben mit Datum und Verweis hierher;
   Hinweis, dass Unteragenten `settings.local.toml` im Worktree brauchen (§ 4). Commit auf `main`, Push.
5. Acht Worktrees nach § 4 anlegen; in einem davon `nox` grün sehen, dann die übrigen.
6. Abnahme: `git worktree list` zeigt acht Branches; jeder hat `settings.local.toml` und ein lauffähiges
   `georep run` (Seite unter `data/site/index.html`).

### Phase 1: Pläne (acht Unteragenten parallel, nur lesen und planen)

Jeder Unteragent bekommt den Prompt aus § 8.1 mit seinem Briefing aus § 7 und schreibt
`docs/plans/NN-name.md` nach der Vorlage in § 8.3, committet ihn auf seinem Branch, pusht nicht. Er
implementiert nichts; Erkundungsskripte laufen nur im Scratchpad. Netz nur für das Lesen öffentlicher Seiten
(Portale, Dokumentation), keine Abrufe gegen OParl außer einer einzelnen Seite zur Formatprüfung.

Abnahme je Plan: Vorlage vollständig, jeder Schritt hat ein Abnahmekriterium, die Berührungspunkte mit dem
bestehenden Code sind als Dateien benannt, offene Fragen stehen mit der Annahme, unter der es weiterginge.
Der Supervisor liest jeden Plan nach Eingang kurz und schickt ihn mit konkreten Lücken zurück, wenn die Vorlage
nicht erfüllt ist (höchstens eine Runde).

### Phase 2: Synergien und Fundament (Supervisor)

1. Alle acht Pläne mit vollem Kontext lesen. Daraus `docs/plans/00-synergien.md` schreiben:
   - gemeinsame Bausteine, die mehrere Optionen brauchen (Erwartung: Profile für Stadt und Periode in den
     Settings für 1, 2, 7; eine Umrechnung Stadtteil, Stadtbezirk, Stimmbezirk zu Wahlbezirk für 2, 3, 5;
     erweiterte `PaperRecord`-Metadaten wie Urheber und Gremium für 4, 5, 7; ein Abschnittsmechanismus für
     die Berichtsseite und das Seitenbudget für alle; eine Abstraktion „Kennzahlvariante" mit eigener
     Regression für 3 und 6; Wiederverwendung des Dokumentdialogs aus Stufe G für 8);
   - Konflikte (dieselben Dateien, dieselben Settings-Schlüssel, dieselben Seitenabschnitte) und ihre
     Auflösung;
   - die Merge-Reihenfolge (Vorschlag: zuerst die Offline-Optionen mit kleinem Fußabdruck 8, 5, 6, 3, dann
     4, 2, 1, 7; Begründung je Position);
   - welche Teile als Fundament vorab auf `main` kommen.
2. Das Fundament auf `main` implementieren: klein, getestet, mit Vertrag, mit Eintrag in `decisions.md`;
   `nox` grün, Push. Danach alle acht Branches auf `main` rebasen (`git rebase main` je Worktree).
3. Pläne umschreiben, wo die Synergien es verlangen: direkt in `docs/plans/NN-name.md` auf dem jeweiligen
   Branch, mit einem Abschnitt „Änderungen durch die Synergiephase" am Ende, damit der Unteragent sieht, was
   sich geändert hat.
4. Fragen bündeln (§ 6) und an Konrad geben. Blockierende Fragen (vor allem Netz, § 9) halten nur die
   betroffene Option an; alles andere läuft weiter.
5. Abnahme: `00-synergien.md` ist geschrieben, das Fundament ist gemerged und dokumentiert, jeder Plan trägt
   entweder „unverändert" oder den Änderungsabschnitt, `fragen.md` ist an Konrad gegangen.

### Phase 3: Implementierung (Unteragenten in Wellen)

Welle 1: die Offline-Optionen 8, 5, 6, 3. Welle 2: 4, 2, 1, 7, sobald die Fragen zum Netz beantwortet sind
(ohne Freigabe nur die Vorbereitung, § 2). Die Größe der Wellen passt der Supervisor an die Rechnerlast an.

Jeder Unteragent bekommt den Prompt aus § 8.2, arbeitet nach seinem Plan, committet in kleinen Schritten auf
seinem Branch, hält `nox` grün, schreibt Tests nach den Regeln in CLAUDE.md (hypothesis für Eigenschaften,
Golden Master für reproduzierte Zahlen, Snapshots nur klein und stabil), ergänzt `architecture.md`,
`decisions.md`, README und die Berichtsseite in seinem Branch, und trägt neue Fragen in seinen Plan ein. Am
Ende meldet er: was fertig ist, was nicht und warum, welche Fragen offen sind, welche Annahmen gelten, wie
lange `nox`, `pytest -m slow` und `georep run` brauchen.

Abnahme je Option: alle Abnahmekriterien des Plans erfüllt oder im Abschlussbericht ausdrücklich als offen
benannt; `nox`, `pytest -m slow`, `nox -s bench` grün im Worktree; die Seite baut und wurde mit headless Chrome
angesehen (siehe Memory-Notiz „site-preview-and-screenshots" beziehungsweise § 8.4); keine Düsseldorf-Konstante
im neuen Code (`grep -rn "Düsseldorf\|0015" src/` zeigt nur Settings und Doku).

### Phase 4: Review und Merge (Supervisor)

Je Option in der Reihenfolge aus `00-synergien.md`:

1. Branch auf `main` rebasen; Konflikte löst der Supervisor, bei inhaltlichen Konflikten mit Rückfrage an den
   Unteragenten (SendMessage, falls er noch läuft, sonst ein frischer Agent mit dem Plan).
2. Review mit der Skill `code-review` (Stufe high) und von Hand gegen die Abnahmekriterien; Befunde zurück an
   den Unteragenten oder selbst beheben, wenn klein.
3. `uv run nox`, `uv run pytest -m slow`, `uv run nox -s bench` im Worktree auf dem rebasten Stand.
4. Merge nach `main` als Merge-Commit mit `--no-ff` (die Branch-Historie bleibt lesbar; abweichend nur, wenn
   Konrad Pull Requests will, § 9 Frage 2), dann `nox` auf `main`, Push per SSH, CI über die Actions-REST-API
   prüfen (`gh run list` ist hier leer), Pages-Lauf grün, Seite live ansehen.
5. Version: je gemergter Option eine Minor-Version (0.11.0, 0.12.0, …) mit `CHANGELOG.md`, `STATUS.md`,
   `pyproject.toml`, `src/georep/__init__.py`, `uv lock`, Tag (falls Konrad nicht anders entscheidet, § 9 Frage 6).
6. `docs/plans/README.md` auf „gemerged" setzen, Worktree und Venv entfernen.

### Phase 5: Abschluss (Supervisor)

`STATUS.md` (Stand, Zahlen, Bekanntes, nächster Schritt), `architecture.md` (Module, Pipeline, Datenhaltung,
Berichtsseite), `decisions.md` (ein Punkt je Option, mit verworfenen Alternativen), README (Loslegen, Befehle,
Daten und Herkunft, Lizenzen). Dieser Plan bekommt oben die Zeile „abgeschlossen am <Datum>" mit dem Stand je
Option. Eine Übergabenachricht an Konrad: was live ist, was offen blieb, welche Fragen unbeantwortet waren und
welche Annahmen deshalb gelten.

## 6. Protokoll für Fragen

`docs/plans/fragen.md` führt der Supervisor; Unteragenten schreiben nur in ihren eigenen Plan. Jede Frage
hat: laufende Nummer, Option, Datum, Frage in einem Satz, warum sie zählt (was sich je nach Antwort ändert),
die Annahme, unter der ohne Antwort weitergearbeitet wird, Status (offen, beantwortet am, Antwort). Der
Supervisor gibt Fragen gebündelt weiter: einmal am Ende von Phase 2, danach nur, wenn eine Frage blockiert.
Antworten trägt er in `fragen.md` ein und in den betroffenen Plan.

## 7. Briefings je Option

Jedes Briefing nennt Ziel, Datenlage mit Pfaden, Berührungspunkte im Code, bekannte Hürden, Mindestumfang der
Abnahme und die ersten offenen Fragen. Die Pläne der Unteragenten vertiefen das; sie dürfen das Briefing in
Frage stellen, müssen die Abweichung aber begründen.

### 7.1 Option 1: Städte

- **Ziel**: Die Kette läuft für eine zweite Kommune am OParl-Server der ITK Rheinland (Bodies laut
  `defaults.toml`: 0009 Neuss, 0011 Mönchengladbach, 0013 Grevenbroich, 0019 Rhein-Kreis Neuss) bis zur
  Berichtsseite, und `main` baut Düsseldorf unverändert. Ein Städtevergleich (Tabelle, kleine Karten) kommt
  auf die Seite oder als Unterseite.
- **Datenlage**: je Stadt braucht es Wahlergebnis je Stimmbezirk (CSV) und Stimmbezirks-Geometrie (GeoJSON)
  mit Zuordnung zum Wahlbezirk; Spaltennamen und Kodierung werden abweichen (`settings.columns`). Welche der
  vier Kommunen das als Open Data hat, ist zu erkunden (Open-Data-Portale der Städte, GovData).
- **Code**: `settings.py` (Profile je Stadt: eigene TOML-Datei `settings.<stadt>.toml` oder eine
  `[city]`-Tabelle), `layout.py` (`data_root` je Stadt), `sources/opendata.py`, `prep/voters.py`,
  `geo.py` (CRS je Quelle), `report/` (Titel, Texte, Lizenzen je Stadt aus Settings), `cli.py` (`--settings`
  gibt es schon). Alles, was heute „Düsseldorf" oder „0015" im Code trägt, wandert in Settings.
- **Hürden**: Abruf dauert je Stadt Stunden (Metadaten 85 s je Seite, PDFs seriell); Overpass und Wikidata je
  Stimmbezirk ebenfalls. Lizenzen je Portal nachsehen und wörtlich auf die Seite. Wahltermine und Perioden je
  Stadt sind verschieden.
- **Abnahme mindestens**: Mini-Fixture der zweiten Stadt mit Golden Master aus einem einmaligen echten Lauf
  (klein, mit README); `georep --settings settings.<stadt>.toml run` offline grün; kein Düsseldorf-Literal
  mehr im Code; Seite der zweiten Stadt baut; Vergleichsabschnitt mit Zahlen aus beiden Läufen.
- **Offene Fragen**: Netzfreigabe (§ 9, Frage 1); welche Stadt zuerst (Vorschlag: die mit vollständigen Open
  Data, sonst Neuss als nächste Nachbarin).

### 7.2 Option 2: Zeitreihe

- **Ziel**: dieselben Kennzahlen für die Wahlperiode 2014 bis 2020 auf den Wahlbezirken von 2020,
  umgerechnet auf die Wahlbezirke von 2025 über Flächenanteile der Stimmbezirke, und ein Vergleich der
  Perioden (Änderung der Trefferquote gegen Änderung der Wahlbeteiligung).
- **Datenlage**: Open-Data-Portal: Datensätze „Ratswahl 2020 Düsseldorf" und „Wahlgebietseinteilung" (ältere
  Zuschnitte prüfen; die Arbeit zeigt den Neuzuschnitt 2020 zu 2025 in Abbildung 3). OParl liefert Vorlagen
  mindestens ab 2014 (zu prüfen mit einer Seite); PDFs rund 20 000 zusätzlich.
- **Code**: `settings.period` wird ein Profil je Periode; `layout` je Periode; `geo.py` bekommt die
  Umrechnung (Schnittflächen mit shapely, Gewichte als Flächenanteil oder, besser, als Anteil der
  Wahlberechtigten je Stimmbezirk); `analysis/` ein Modul für Differenzen; Seite: Abschnitt „Zwei Perioden".
- **Hürden**: Abruf Stunden; Stimmbezirke 2020 als Geometrie müssen vorhanden sein, sonst nur
  Wahlbezirksebene; Wörterbuch der alten Periode: Straßen und Orte von heute oder von damals (Entscheidung
  dokumentieren; Vorschlag: dasselbe Wörterbuch für beide, damit nur die Dokumente variieren).
- **Abnahme mindestens**: Umrechnung mit Vertrag (Gewichte je Zielbezirk summieren zu 1) und
  hypothesis-Test; Mini-Fixture mit synthetischer zweiter Periode; `georep --settings settings.2014.toml run`
  offline grün; Seite zeigt beide Perioden.
- **Offene Fragen**: Netzfreigabe; Zuschnitt 2020 als GeoJSON vorhanden?

### 7.3 Option 3: Kontrollvariablen

- **Ziel**: eine multiple Regression der Wahlbeteiligung auf Trefferquote plus Kontrollvariablen je
  Wahlbezirk; „Tabelle 6" auf der Seite mit Koeffizienten, Standardfehlern, p-Werten, R² und einem Satz zur
  Deutung; partielle Streudiagramme.
- **Datenlage**: Parteianteile sind da (`wahlbezirke_waehler.parquet`). Quartiersatlas der Stadt (sozialer
  Handlungsbedarf, Fluktuation; Quelle laut Arbeit `statistik.duesseldorf.de`, vermutlich PDF), Altersstruktur
  je Stadtteil aus dem Open-Data-Portal („Bevölkerung nach Alter"), repräsentative Wahlstatistik (Alter,
  Geschlecht, nur Stichprobe). Stadtteile zu Wahlbezirken: das Stimmbezirks-GeoJSON trägt `Stadtteil Nr.` je
  Stimmbezirk, Gewichtung über Wahlberechtigte je Stimmbezirk.
- **Code**: `analysis/regression.py` (OLS mit mehreren Prädiktoren; scipy hat `linregress` nur bivariat,
  also OLS mit numpy und t-Tests über `scipy.stats.t`, oder statsmodels als neue Abhängigkeit mit Eintrag in
  `decisions.md`); neue Quelle `sources/statistik.py` mit `Transport`; `prep/context.py`; Settings für die
  Variablenliste; Seite: Abschnitt und Tabelle.
- **Hürden**: Daten liegen womöglich nur als PDF-Tabellen vor (Parsen mit pypdf, Herkunft und Lizenz
  dokumentieren); kleine n (41) gegen mehrere Prädiktoren: Multikollinearität prüfen, Modell sparsam halten.
- **Abnahme mindestens**: OLS gegen bekannte Werte getestet (bivariat gleich `linregress`); Verträge (p in
  [0, 1], n > Prädiktoren + 1); Crosswalk Stadtteil zu Wahlbezirk mit Vertrag; Seite zeigt Tabelle 6 mit
  Daten aus Dateien, deren Herkunft und Lizenz im Fuß stehen.
- **Offene Fragen**: PDF-Tabellen scrapen erlaubt? (§ 9, Frage 5); statsmodels erlaubt oder numpy-OLS?

### 7.4 Option 4: Parteien

- **Ziel**: je Vorlage die Urheber (Fraktion, Verwaltung, Person) und daraus je Partei und Wahlbezirk die
  Erwähnungen; Abgleich mit dem Stimmenanteil der Partei im Bezirk (Hochburgen); Seite: Heatmap oder kleine
  Multiples je Partei, Tabelle.
- **Datenlage**: OParl-Paper tragen `originatorPerson`, `originatorOrganization`, `underDirectionOf`;
  Organisationen (Fraktionen) über den Endpunkt `organizations`. Prüfen, ob `PaperRecord` und
  `raw/papers.jsonl` der Referenz diese Felder haben (vermutlich nicht: die Referenz stammt aus
  `paper_with_text.json` der Arbeit); dann Metadaten neu abrufen (rund 95 Seiten mit `stop_when_older`,
  Stunden), PDFs nicht.
- **Code**: `oparl.py` (Felder im pydantic-Vertrag), `records.py`, `stores.py` (Upsert erhält neue Felder),
  `sources/oparl.py` (Organisationen), `analysis/parties.py`, Settings (Zuordnung Organisationsname zu
  Parteikürzel), Seite.
- **Hürden**: Netz; Namen der Organisationen variieren; Verwaltungsvorlagen ohne Fraktion sind die Mehrheit.
- **Abnahme mindestens**: OParl-Fixture mit Urheberfeldern (eine echte Seite aufzeichnen), Roundtrip-Test;
  Kennzahl je Partei und Bezirk mit Vertrag (Summen stimmen); Seite mit Abschnitt; ohne Netzfreigabe: alles
  bis auf den Abruf, der als `georep fetch papers --force` dokumentiert ist.
- **Offene Fragen**: Netzfreigabe; welche Parteien (die sechs aus `columns.results.parties`?).

### 7.5 Option 5: Gremien

- **Ziel**: aus Drucksachennummer (`BV6/108/2023`, Ratsvorlagen wie `11/3/2019`) und `paper_type` das Gremium
  je Dokument; Kennzahlen je Wahlbezirk: Treffer aus der eigenen Bezirksvertretung, aus anderen, aus dem Rat;
  Seite: Tabelle, Umschalter auf der Karte (dritte Klasse neben Trefferquote und Wahlbeteiligung).
- **Datenlage**: `interim/papers.parquet` hat `reference` und `paper_type`; Stadtbezirk je Stimmbezirk steht
  im GeoJSON (`Stadtbezirk Nr.`), daraus Stadtbezirk je Wahlbezirk (mehrheitlich oder gewichtet).
- **Code**: `prep/papers.py` oder neues `prep/bodies.py` (Parser mit Vertrag und hypothesis), `analysis/hits.py`
  erweitert oder neues Modul, `report/` (Modell, Karte: `data-class-*` je Kennzahl, Legende), Settings für
  die Muster der Drucksachennummern.
- **Hürden**: Muster der Nummern sind nicht dokumentiert; Fälle ohne erkennbares Gremium gehören in eine
  Klasse „unbekannt" mit Anteil auf der Seite.
- **Abnahme mindestens**: Parser-Vertrag mit hypothesis; Anteil „unbekannt" auf der Referenz unter 5 % oder
  begründet; Seite baut, Umschalter funktioniert (JS im Browser geprüft).
- **Offene Fragen**: keine blockierende.

### 7.6 Option 6: Gewichtung

- **Ziel**: Alternativen zur binären Trefferquote: Spezifität je Begriff (in wie vielen Bezirken geführt,
  Dokumenthäufigkeit stadtweit), Gewicht je Dokumentart (`paper_type`), Themen je Dokument; Sensitivitätstabelle
  auf der Seite: Tabelle 5 unter jeder Gewichtung.
- **Datenlage**: `inverted_index.parquet`, `combined_searchdict.parquet`, `interim/papers.parquet` (Texte,
  15 MB) liegen vor; alles offline.
- **Code**: `analysis/weights.py` (reine Funktionen auf Frames, Verträge: Gewichte in [0, 1], Summen);
  Themenmodell ohne scikit-learn (`nox -s deps` verbietet es): TF-IDF in Polars und numpy, NMF selbst
  implementiert oder gensim (neue Abhängigkeit, prüfen) (§ 9, Frage 3); Seite: Abschnitt „Was ändert die
  Gewichtung?".
- **Hürden**: Rechenzeit über 19 108 Texte (Profil vor jedem Nachbau, `georep profile`); Themen brauchen
  lesbare Labels (Top-Wörter je Thema), keine Interpretation versprechen.
- **Abnahme mindestens**: jede Gewichtung reproduziert bei Einheitsgewichten exakt Tabelle 5 (Golden Master);
  Verträge; Laufzeit des Schritts unter 60 s auf der Referenz oder als eigener, optionaler Schritt markiert.
- **Offene Fragen**: scikit-learn-Verbot lockern oder nicht.

### 7.7 Option 7: Monitoring

- **Ziel**: die laufende Wahlperiode (ab 15.09.2025) inkrementell abrufen und auf der Seite zeigen: Treffer je
  Wahlbezirk seit der Wahl, Neuzugänge je Monat, Datenstand; ein wiederkehrender Lauf.
- **Datenlage**: `georep fetch` mit `modified_since` existiert; der Textstore ist inkrementell; die Seite
  trägt Datenstand aus Stamps. Wahlbezirke 2025 bleiben; Wahlbeteiligung gibt es für die laufende Periode
  nicht (Kennzahl ohne Regression).
- **Code**: Settings-Profil `settings.2025.toml` (Periode offen: `end` optional), `pipeline.py` (Schritt
  `papers` mit offenem Ende), `report/` (Abschnitt mit Monatsreihe), ein Lauf-Skript oder nox-Target `monitor`
  (fetch, run, publish), Workflow oder systemd-Timer je nach Antwort (§ 9, Frage 4).
- **Hürden**: Wo läuft der Abruf, wohin gehen die Daten: Actions hat keinen dauerhaften Speicher und ein
  Zeitlimit von sechs Stunden; PDFs (Gigabyte) gehören nicht ins Repo. Vorschlag: Abruf auf Konrads Rechner
  oder VPS per Timer, Veröffentlichung der kleinen Ergebnisdateien (Parquet unter 1 MB) als Commit in einen
  Datenordner oder als Release-Artefakt, Seite baut daraus.
- **Abnahme mindestens**: Profil mit offener Periode, Tests mit Fake-Session (neue Seiten erscheinen, alte
  bleiben); Seite zeigt die Monatsreihe aus einem Testdatensatz; das Lauf-Skript ist dokumentiert und
  idempotent; ohne Freigabe kein echter Abruf.
- **Offene Fragen**: Ort und Speicher des Abrufs (§ 9, Frage 4); Netzfreigabe.

### 7.8 Option 8: Suche

- **Ziel**: ein Suchfeld auf der Seite: Eingabe einer Straße oder eines Orts mit Vorschlägen aus dem
  Wörterbuch; Ergebnis: Wahlbezirk(e), Treffer, Dokumente (Dialog aus Stufe G), Hervorhebung auf der Karte;
  ohne Server, ohne Fremdressourcen; auch aus dem Dateisystem nutzbar für die Vorschläge (Dokumente brauchen
  wie bisher einen Webserver).
- **Datenlage**: Begriffe stehen schon auf der Seite (Schaltflächen) und in `dokumente.json`; das
  Wörterbuch je Bezirk in `combined_searchdict.parquet` (5841 Begriffe, rund 150 KB als JSON).
- **Code**: `report/templates/report.html.j2` (Suchfeld, `<datalist>` oder eigene Vorschlagsliste, Tastatur
  bedienbar), `report/build.py` (Begriffe mit Bezirken als kompaktes JSON inline oder in `data/`), JS
  (Normalisierung wie das Wörterbuch: kleingeschrieben, `straße` und `str.`), CSS; Seitenbudget beachten.
- **Hürden**: Barrierefreiheit (ARIA für Combobox), Seitengröße, Tippfehler (einfacher Präfix- und
  Teilstring-Abgleich reicht; keine Fuzzy-Bibliothek).
- **Abnahme mindestens**: Tests auf das gerenderte HTML (Feld, Daten vorhanden, Escaping); JS im Browser
  geprüft (Eingabe, Auswahl, Markierung auf der Karte, Dialog); `index.html` bleibt unter 1,5 MB.
- **Offene Fragen**: keine blockierende.

## 8. Vorlagen

### 8.1 Prompt für einen Unteragenten in Phase 1 (Plan)

```
Du arbeitest im Worktree <PFAD> auf dem Branch feat/NN-name des Projekts georep. Setze in jedem
Shell-Aufruf UV_PROJECT_ENVIRONMENT=/media/konrad/xtraspace/venvs/georep-NN-name und
UV_CACHE_DIR=/media/konrad/xtraspace/uv-cache. Lies zuerst CLAUDE.md, STATUS.md, docs/architecture.md,
docs/decisions.md, dann docs/plan-ausbau-2026-10.md (§ 1, 2, 6, 7.NN, 8.3) und als Vorbild
docs/plan-report-2026-10.md. Deine Aufgabe: nur ein Implementierungsplan für Option NN, Datei
docs/plans/NN-name.md nach der Vorlage in § 8.3 des Meta-Plans. Erkunde Code und Daten (uv run georep
status, Parquet-Dateien unter data/, Fixtures), probiere im Scratchpad, implementiere nichts. Netz nur zum
Lesen öffentlicher Seiten; gegen OParl höchstens eine Seite zur Formatprüfung. Fragen an Konrad gehören in
den Abschnitt „Offene Fragen" mit der Annahme, unter der du ohne Antwort weiterarbeiten würdest; du selbst
sprichst nicht mit Konrad. Committe den Plan auf deinem Branch (kein Push) und melde am Ende in wenigen
Sätzen: Umfang, größte Risiken, offene Fragen.
```

### 8.2 Prompt für einen Unteragenten in Phase 3 (Implementierung)

```
Du arbeitest im Worktree <PFAD> auf dem Branch feat/NN-name des Projekts georep (UV_*-Variablen wie in
Phase 1). Lies CLAUDE.md, docs/plan-ausbau-2026-10.md (§ 2, 5 Phase 3, 6, 7.NN), docs/plans/00-synergien.md
und deinen Plan docs/plans/NN-name.md einschließlich „Änderungen durch die Synergiephase". Setze den Plan
Schritt für Schritt um: Verhaltensänderung zuerst mit rotem Test, dann die Änderung, eine Sorte pro Commit,
uv run nox nach jedem Commit (im Alltag uv run pytest -n 2 …), Verträge an Batch-Grenzen, Doku im selben
Branch (architecture.md, decisions.md, README, CHANGELOG-Eintrag unter „Unreleased"). Kein Netzabruf, es sei
denn, dein Plan trägt die Freigabe aus docs/plans/fragen.md. Sieh dir die gebaute Seite mit headless Chrome
an (§ 8.4). Neue Fragen trägst du in deinen Plan ein. Melde am Ende: erfüllte und offene
Abnahmekriterien, Annahmen, Laufzeiten von nox, pytest -m slow und georep run, und ob du mit dem Stand
mergen würdest.
```

### 8.3 Vorlage für `docs/plans/NN-name.md`

```
# Plan NN: <Name>

Stand <Datum>, Branch feat/NN-name. Status: geplant | umgeschrieben | in Arbeit | im Review | gemerged.

## 1. Ziel und Nicht-Ziel
## 2. Entscheidungen (mit verworfenen Alternativen und Kosten)
## 3. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)
## 4. Berührungspunkte im bestehenden Code (Datei, Funktion, was sich ändert)
## 5. Bauplan in Stufen (je Stufe: Schritte, Tests, Verträge, Abnahmekriterium, geschätzter Aufwand)
## 6. Auswirkung auf die Berichtsseite (Abschnitt, Größe in KB, Unterseite ja/nein)
## 7. Risiken und Fallstricke
## 8. Offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)
## 9. Vorbereitung für Option 10 (was wird konfigurierbar, welche Modulgrenze entsteht)
## 10. Änderungen durch die Synergiephase (füllt der Supervisor)
```

### 8.4 Seite ansehen ohne sichtbare Browser-Ansicht

```bash
S=<Scratchpad>; cp data/site/index.html $S/light.html
sed 's/@media (prefers-color-scheme: dark)/@media all/' $S/light.html > $S/dark.html
google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars --window-size=1280,11000 \
  --screenshot=$S/light.png file://$S/light.html   # danach mit PIL in Streifen schneiden und ansehen
```

JavaScript prüft man über einen lokalen Server (`python3 -m http.server 8777 --directory data/site`,
Port 8765 ist belegt) und `javascript_tool` in der eingebauten Browser-Ansicht; Screenshots dort sind leer,
wenn die Ansicht verborgen ist.

## 9. Offene Fragen an Konrad (vom Planer, 2026-10-11)

Die Antworten trägt der Supervisor in `docs/plans/fragen.md` ein. Ohne Antwort gelten die Annahmen.

1. **Netzabrufe**: Dürfen die Unteragenten stundenlange Abrufe gegen den OParl-Server und die Portale fahren
   (Option 1 je Stadt, Option 2 für 2014 bis 2020 mit rund 20 000 PDFs, Option 4 Metadaten neu, Option 7
   laufend)? Nur Metadaten oder auch PDFs? Auf deinem Rechner, oder bereiten sie nur vor und du startest?
   Annahme: nur vorbereiten, Abruf nach Freigabe je Option durch dich.
2. **Merge-Modus**: Merged der Supervisor nach grünem Review selbst nach `main` (Merge-Commit `--no-ff`),
   oder willst du Pull Requests mit deinem Review? Annahme: der Supervisor merged.
3. **scikit-learn** ist per `nox -s deps` verboten. Für das Themenmodell in Option 6: Verbot lockern, gensim
   erlauben, oder TF-IDF und NMF in numpy selbst bauen? Annahme: numpy, kein neues Paket.
4. **Monitoring (Option 7)**: Wo soll der wiederkehrende Abruf laufen (dein Rechner per Timer, dein VPS,
   Actions nur für Metadaten), und wohin gehen die Daten (Repo, xtraspace, Release-Artefakt)? Annahme:
   Skript plus systemd-Timer auf deinem Rechner, kleine Ergebnisdateien in einen Datenordner im Repo.
5. **Fremddaten (Option 3)**: Dürfen Tabellen aus PDFs der Stadt (Quartiersatlas) geparst und, mit Lizenz
   und Herkunft, auf der Seite verwendet werden? Annahme: ja, nur offene Daten, Lizenz wörtlich im Fuß.
6. **Versionen**: eine Minor-Version je gemergter Option mit Tag, oder eine Sammelversion am Ende? Annahme:
   je Option.
7. **Rechnerlast**: Der Rechner hat 16 Kerne und 62 GB RAM, davon am 2026-10-11 rund 24 GB verfügbar
   (`nproc`, `free -g`). Dürfen vier Agenten gleichzeitig `nox` laufen lassen? Annahme: Wellen zu vier,
   `pytest -n 2` im Alltag, volles `nox` nur vor Commits.

## 10. Start-Prompt für den Supervisor

```
Lies docs/plan-ausbau-2026-10.md im Repo /home/konrad/files/work/__drafts/geographic-representation-dus
vollständig und führe ihn aus, Phase 0 bis 5. Du bist der Supervisor: du planst nicht selbst die Optionen,
du startest je Option einen Unteragenten (Agent-Werkzeug, isolation worktree oder Worktree nach § 4), liest
deren Pläne, schreibst die Synergien und das Fundament, bündelst Fragen an Konrad in docs/plans/fragen.md,
reviewst, mergst, versionierst. Halte dich an CLAUDE.md und § 2 des Plans. Setze in jedem Shell-Aufruf
UV_PROJECT_ENVIRONMENT=/media/konrad/xtraspace/venvs/georep und
UV_CACHE_DIR=/media/konrad/xtraspace/uv-cache. Fragen an Konrad nur gebündelt (§ 6); sonst arbeite unter
den Annahmen in § 9 weiter. Beginne mit Phase 0 und melde nach jeder Phase in wenigen Sätzen den Stand.
```
