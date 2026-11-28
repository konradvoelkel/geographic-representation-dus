# Status

Stand und Bekanntes, je mit Datum. Der Verlauf steht in `CHANGELOG.md`, die Gründe in
`docs/decisions.md`, der Aufbau in `docs/architecture.md`, das Offene in `docs/todo.md`.

## Stand

Stand 2026-11-26, `main` auf `v0.32.0`.

- **Abgeschlossen**: der Umbau in sieben Phasen (`docs/development-plan-2026-10.md`), die
  Berichtsseite (`docs/plan-report-2026-10.md`, veröffentlicht unter
  <https://konradvoelkel.github.io/geographic-representation-dus/>) und der Ausbau in acht Optionen
  (`docs/plan-ausbau-2026-10.md`). `bartzsch-exakt` zeigt auf `v0.11.0`, den letzten Stand, der die
  Zahlen der Arbeit exakt reproduziert.
- **Vier Datensätze, ein Extraktor**: Hauptperiode 2020 bis 2025, Periode 2014 bis 2020, laufende
  Periode seit 2025 und Mönchengladbach, alle mit pypdf 7.1.0 gelesen (Punkte 67 und 68, bis auf
  16 Texte, siehe unten); die Hauptperiode aus dem Textpaket `snapshots/duesseldorf-texte/`.
- **Vorverarbeitung 2026-11** (`docs/plan-vorverarbeitung-2026-11.md`, Stand je Vorhaben in
  `docs/plans/README.md`): die Fundamente F1 bis F7 liegen auf `main` (`v0.17.0` bis `v0.23.0`,
  Punkte 69 bis 74). In Stufe 2 gebaut sind 15 (`v0.24.0`, Punkt 75), 14 (`v0.25.0`, 76), 18
  (`v0.26.0`, 77), 17 (`v0.27.0`, 78), 26 (`v0.28.0`, 79), 22 (`v0.29.0`, 80), 11 (`v0.30.0`, 81),
  12 (`v0.31.0`, 82) und 20 (`v0.32.0`, 83; gebaut und in allen Profilen aus, kein Stapellauf).
  Gemessen mit dem Urteil „bauen", aber noch nicht gebaut: 16, 19, 27, 28; verworfen: 13, 23; 24
  wartet auf eine Umbaurunde; 21, 25 und 29 sind nicht gemessen. Stufe 3 (zeigen) steht für alle
  aus: die Seite zeigt von den neuen Tabellen nichts. Weiter geht es nach
  `docs/plan-zeigen-2026-11.md` (Konrad, 2026-11-26: zuerst Stufe 3 der gebauten Vorhaben).
- **Die Zahlen der Seite** sind seit `v0.16.0` dieselben, bis auf eine Änderung in `v0.30.0`: sechs
  Ausschüsse tragen ihren Namen aus dem Kopf der Vorlagen, die Kürzel ohne gesicherten Namen sinken
  in der Hauptperiode von 11 auf 5, in den Perioden von 9 auf 3.
- **Erste Unterseite** (`v0.35.0`, Phase „Zeigen“, `docs/plan-zeigen-2026-11.md`): `akteure.html` aus
  Vorhaben 15 in allen fünf Profilen, verlinkt aus dem Abschnitt „weitere“ der Hauptseite (+4,6 KB);
  dazu die Downloads `dokumente_funktion` und `dokumente_antragsteller`.
- **Downloads von 11 und 12** (`v0.36.0`): `dokumente_kopf` und `kennungen`, nur in der Hauptperiode.
- **`zeit.html`** (`v0.37.0`): Rhythmus, die drei Hypothesen von 17, Bundesvokabular; in der laufenden
  Periode die Liste der Feeds mit ihrem Datenstand.
- **Startseite und `details.html`** (`v0.39.0` und `v0.40.0`, Punkte 92 und 93): die ganze Auswertung steht als
  `details.html` (Hauptperiode 968 010 Byte, Budget 1 000 000); `index.html` ist die Startseite mit
  Kurzfassung, Karte aus eigenen Vektordaten, Zeitregler und Filter „Gremium“ (86 742 bis 92 759 Byte je
  Profil, Budget 150 000), dazu `data/karte.json` (höchstens 448 872 Byte, Budget 500 000) und die Pakete
  `snapshots/*-strassenpunkte/`. Konrad hat die Seite noch nicht auf Pages gesehen (Haltepunkt ZS2).
- **`spalten.html`** (`v0.41.0`, Punkt 94): das Spaltenschema aller Tabellen steht je Profil auf einer eigenen
  Seite (Hauptperiode 77 302 Byte) und in `schema.json`, auf keiner anderen Seite; `details.html` der
  Hauptperiode wiegt damit 921 158 Byte, 16 KB unter dem Stand vor der Phase.
- **`bedarf.html`** (`v0.42.0`, Punkt 95): Bedarf und Aufmerksamkeit je Wahlbezirk in der Hauptperiode
  (242 267 Byte) und in Mönchengladbach ohne Klassen (133 866 Byte); H1 nach der vorab festgelegten Regel
  bestätigt, aber nur zwischen den Stadtbezirken. Die Klasse „Ordnung und Verkehr“ ist an Dokumenten ohne
  Ausschussberatung ohne verlässliches Maß geprüft (`docs/todo.md`, Punkt 40).
- **Ähnliche Dokumente** (`v0.43.0`, Punkt 96): der Dokumentdialog der Hauptperiode zeigt je Dokument fünf
  ähnliche aus `data/aehnlich.json` (911 KB, nachgeladen); nachgeladene Dateien der Hauptperiode zusammen
  rund 1,0 MB von 1,5 MB.
- **Ortsbezug** (`v0.44.0`, Punkt 97): der frühe Schritt `places` rechnet die Stelle je Treffer und die
  Hausnummern (92,3 % verortet); die Gewichtungen `ortsbezug` (Nebenregel C) und `stelle` (explorativ)
  stehen in der Hauptperiode in „Was ändert die Gewichtung?“. Mit ihnen sind es 28 Gewichtungen.
- **Abstimmungen** (`v0.45.0`, Punkt 98): Ergebnis und Mehrheitsform je Tagesordnungspunkt aus dem Eintrag der
  Sitzungsleitung (Ebene A), als Abschnitt auf `akteure.html`; H28.2 bestätigt (Anträge der Opposition im Rat
  zu 9,0 % angenommen, seit `v0.46.0`), H28.1 und H28.3 ohne Ebene B nicht entscheidbar.
- **Beschlusslage** (`v0.46.0`, Punkt 99): drei Abschnitte auf `vorgaenge.html` (Beschlusslage je Gremium, Erfolg je
  Fraktion explorativ, Anfragen in der Sitzung beantwortet) und je Antrag Klasse, Gremium und Tag der Entscheidung im
  Dokumentdialog (`beschluesse.json`); nachgeladene Dateien der Hauptperiode zusammen rund 1,14 MB von 1,5 MB.
- **`vorgaenge.html`** (`v0.38.0`): Antworten auf Anfragen, Kandidaten, Vorgänge; dazu der Dialog-Haken der
  Hauptseite, der Zeilen je Dokument beim Öffnen nachlädt. Die Hauptseite liegt damit bei 966 522 Byte,
  rund 29 KB über dem Stand vor der Phase (Ziel höchstens 30 KB, `docs/todo.md`, Punkt 36).
- Die Worktrees, Venvs und Branches der Vorverarbeitung sind am 2026-11-26 entfernt. Für die Phase
  „Zeigen“ arbeiten Bau-Agenten wieder auf eigenen Branches in Worktrees (Konrad, 2026-11-27; `CLAUDE.md`).

## Was wo läuft

- **GitHub Pages** (`.github/workflows/pages.yml`, bei jedem Push auf `main`): `bootstrap` und `run`
  je Profil aus den Datenpaketen im Repo, in der Folge `duesseldorf`, `duesseldorf-2014`,
  `duesseldorf-2025`, `duesseldorf-vergleich` (liest die beiden Perioden davor), `moenchengladbach`;
  dann `publish --strict-budget`. Kein Netz, keine Modelle: Netz- und Modellschritte werden
  übersprungen, ihre Ergebnisse kommen aus den Paketen. Den Rohtext gibt es dort nur für die
  Hauptperiode, darum bleiben `sections` und `identifiers` in den anderen Profilen leer; ähnliche
  Dokumente gibt es nur für die Hauptperiode (Paket `snapshots/duesseldorf-aehnlich/`).
- **Lokal** (Rechner mit xtraspace): die PDFs aller vier Datensätze (die der Hauptperiode seit dem
  2026-11-18, 19 092 Dateien, 2,7 GB), Rohtextstores, die Netzdaten von F6 (2026-11-23/24,
  `docs/runbook-sitzungen.md`, § 9), Einbettungen und Modellcache von ollama hinter
  `gpu-queue/gpu.lock`. Vektoren, Personendaten und Kurzfassungen kommen nie ins Repo.
- **Monitor** der laufenden Periode (`deploy/`): gebaut und im Trockenlauf geprüft, aber nirgends
  installiert (`docs/todo.md`, Punkt 22).

## Zahlen (2026-11-26)

- **Tests**: 2 631 schnelle grün (`nox -s test -- -n 3`, Commit `30bd52d`), 123 `slow`, 4 `network`,
  1 `models` (gesammelt mit `pytest --collect-only`). `nox -s verify` hat 62 Ziele.
- **Veröffentlichte Seiten** (abgerufen am 2026-11-26, gebaut aus `v0.32.0`): Hauptseite 937 528 Byte
  (Budget `report.page_budget_bytes` 1 000 000, 62 472 Byte oder 6,2 % Luft), `2014-2020/` 822 940,
  `2025/` 718 866, `moenchengladbach/` 806 210, `vergleich.html` 93 873.
- **Quelltext**: 116 Python-Dateien unter `src/`, rund 43 500 Zeilen; fünf Profile im Paket.
- **Mutation** (zuletzt 2026-10-13, `docs/mutation-2026-10-13.md`): 717 von 882 Mutanten getötet
  (81,3 %) über die dreizehn Module des Ausbaus.
- Schritte je Profil: `docs/architecture.md`, „Pipeline", oder `georep steps`; Datenpakete:
  `docs/technik.md`, § 3.

## Bekannt

Fakten über System, Daten und Werkzeuge, je mit Datum. Arbeitsregeln stehen in `CLAUDE.md`,
Entwurfsgrenzen in `docs/architecture.md`, Einwände gegen die Auswertungen in `docs/statistik.md`.

**Texte und Werkzeuge**

- **16 Texte sind nicht mit pypdf 7.1.0 gelesen** (2026-11-18): 15 der Periode 2014 bis 2020 tragen
  `pypdf-6.20.0`, weil pypdf seit 6.21 ihre PDFs an einer Schutzgrenze abweist (`Reached maximum
  number of tokens per stream`); einer der Hauptperiode (`00403713.pdf`, AES-verschlüsselt) trägt
  den Text der Arbeit, weil `cryptography` nicht im Lock steht (`docs/todo.md`, Punkt 20). Jeder
  Lauf mit PDFs zählt sie als fehlerhaft und versucht sie erneut. Wer die Periode 2014 bis 2020
  ohne ihren alten Store aus den PDFs extrahiert, bekommt die 15 nicht.
- **pypdf steht auf genau 7.1.0** (Punkt 66): es reproduziert 123 der 200 lokal vorhandenen Texte
  der Arbeit zeichengleich, 6.20.0 und 6.21.4 reproduzierten 197. Die Golden-Master-Tests rechnen
  darum gegen die Arbeit mit deren Texten (`as_in_the_thesis`).
- **Die Extraktion hängt an der Umgebung** (2026-11-15): mit installiertem fontTools (nur in der
  Gruppe `notebook`) ändern sich 12 der 27 062 Texte; extrahiert wird ohne sie.
- **crosshair-tool steht fest bei 0.0.111** (Punkt 66): 0.0.113 stürzte in einem von vier vollen
  Läufen von `nox -s verify` selbst ab (`docs/todo.md`, Punkt 21).
- **Eine Änderung am Python-Code der Berichtsseite macht den Stamp von `report` nicht ungültig**
  (2026-10-14): im Stamp stehen Vorlagen, `literatur.toml`, `[report]` und die Code-Version, nicht
  der Code. Ohne Versionssprung braucht die Seite danach `georep run report --force` je Profil.
- **Der Settings-Fingerprint ist global**: ein neuer Schlüssel lässt alle Schritte einmal neu laufen
  (`docs/todo.md`, Punkt 16).
- **Themenmodell und passender Ausschuss sind je Rechner reproduzierbar, nicht darüber hinaus**:
  zwischen 13 und 2 BLAS-Threads unterscheiden sich `themen.parquet` und `themen_anteile.parquet` in
  den letzten Stellen (2026-10-12); die logistische Regression hält bei `tol` 1e-4 an, und im CI-Lauf
  vom 2026-11-26 stand ein Wahlbezirk in H1 und H3 von Vorhaben 22 eine Rangstelle anders, die Urteile
  blieben (Punkt 80, Nachtrag; `docs/todo.md`, Punkt 18). Die Nummern der Themen gelten nur für
  diesen Datenstand.
- **Die lokale Datenwurzel des Hauptklons ist „offen"** (2026-11-26): `georep status` meldet fast
  jeden Schritt als „Settings geändert" oder „Ausgabe fehlt", weil die Läufe der Vorverarbeitung in
  den Worktrees liefen (`docs/todo.md`, Punkt 33).

**Quellen**

- **Ein voller `georep fetch` von Grund auf in einem Zug lief noch nie**; er dauert Stunden und ist
  wiederaufnehmbar. Gemessen sind seine Teile: der Vollabruf der Metadaten der Hauptperiode in 36 min
  (2026-10-14), ihre PDFs mit 17 892 Dateien in 5 h 35 min (2026-11-17/18, keine fehlgeschlagen). Die
  19 108 Dokumente der Hauptperiode haben 19 092 PDFs: 16 nennen keine Hauptdatei.
- **Der OParl-Server liefert für Düsseldorf keine Urheberfelder** (Vollabruf 2026-10-14: 0 von 19 109);
  der Urheber kommt aus Dokumentart, Titel und Textkopf (Deckung 98,3 %), und `georep fetch papers
  --max-pages 1` ist die billige Probe, ob sich das ändert. `modified` ist in der Hauptperiode
  brauchbar (1 200 tragen das Migrationsdatum 30.12.2024), in der Periode 2014 bis 2020 nicht, darum
  dort `incremental = false`. Ein Dokument mehr als die Referenz der Arbeit (`KUA/023/2026`,
  zurückdatiert) steht in `docs/befunde-2026-10-14.md`.
- **1 535 Dokumente der Periode 2014 bis 2020 und 1 275 Mönchengladbachs bleiben „Gremium
  unbekannt"** (2026-10-14, Punkt 58): ihre Beratungsfolge nennt mehrere Gremien, und welches
  federführend ist, steht nicht in `consultation_organizations` (`docs/todo.md`, Punkt 28).
- **Die Ergebnis-CSV der Ratswahl heißt im Open-Data-Portal inzwischen `…_Stimmbezirke_1.csv`**
  (Datensatzseite am 2026-10-11); `profiles/duesseldorf.toml` zeigt auf `…_0.csv`, woher die Referenz
  stammt. Vor einem `fetch opendata` nachsehen.
- **Overpass weist unter Last ein großes `[timeout:N]` ab** (2026-10-13, Punkt 54): mit 25 s antwortet
  die Abfrage, mit 90 s gab es von allen vier öffentlichen Instanzen `504`. Der Schlüssel des
  HTTP-Caches ist der POST-Body; wie man einen zähen Abruf zusammensammelt, steht in
  `docs/technik.md`, § 2.
- **Mönchengladbachs Ratsinformationssystem liefert nur 658 von 2 871 Hauptdateien aus** (voller Lauf
  2026-10-13): die übrigen antworten mit `404`, und warum, sagt der Server nicht. Jede absolute Zahl
  dieser Stadt ruht auf rund einem Viertel der Periode; die Seiten sagen es (Kernzahlen,
  Städtevergleich).
- **Mönchengladbachs Straßen stimmen zu 88,8 % je Wahlbezirk mit dem amtlichen Verzeichnis überein**
  (2026-10-15, Flächen des Wahltags, Punkt 65): alle 300 Abweichungen betreffen Namen, die Overpass in
  mehr als einem Wahlbezirk liefert, das Verzeichnis ordnet über Adressen zu (`docs/todo.md`,
  Punkt 26).
- Mönchengladbach: der Marker `betrifft` kommt in den Texten nicht vor, die Kette durchsucht dort den
  ganzen Text (2026-10-13, Frage 1.5); die votemanager-CSVs der ITK Rheinland tragen keine
  Lizenzangabe, die Seite schreibt „Lizenz laut Anbieter nicht angegeben" (Frage 1.4).
- **Der Schnappschuss `snapshots/2025/` veraltet mit jedem Tag**, und das ist in Ordnung: er ist der
  Erstabruf vom 2026-10-13 (4 095 Dokumente), Pages zeigt diesen Stand, und die Seite nennt ihr
  Abrufdatum. Neu gepackt wird er nur von Hand (`snapshots/2025/README.md`).

**Daten und Methode**

- **Tabelle 5 der Arbeit, Spalte „ohne Ausreißer", weicht von der Neuberechnung ab**
  (`docs/baseline-2026-10-10.md`); die Tests frieren die Neuberechnung ein, die Seite nennt die
  Spalte „explorativ" (Punkt 61; `docs/todo.md`, Punkt 25).
- **11 % der Urheber der Periode 2014 bis 2020 bleiben unbekannt** (2 356, 2026-10-14, Punkt 60):
  2 122 `Vorlage aus der Politik` ohne „fraktion" im Vorlagenkopf (Jugendrat, Einzelmandate, Listen
  des Integrationsrats), dazu 135 `Antrag`, 96 `Anfrage`, 3 `zAnfrage Piraten`. Piraten, REP, FWG und
  die Zentrumspartei haben keine Zeile in `[originators]`, weil jedes Wort eines Parteimusters zum
  Stoppwort des Themenmodells wird.
- **Sechs Personennamen überleben den Namensfilter des Themenmodells** („hans", „christian",
  „stephan", „cardeneo", „kühbacher", „tobias", `docs/themenmodell-2026-10.md`, § 2.2): sie stehen
  nie neben einer Amtsbezeichnung. Die Mitgliedschaften aus F6 (lokal seit 2026-11-24) könnten das
  schließen; angeschlossen sind sie nicht.
- **Wörterbuch und Matcher erben drei Eigenheiten der Arbeit**: Labels, die sich nur durch ein Komma
  unterscheiden, fallen in der POI-Bereinigung zusammen; die Abkürzungsregel ersetzt „straße" überall
  im Begriff („str.nbahn düsseldorf", trifft nichts); Umlaute sind Wortgrenzen („Köölberg" trifft
  „ölberg", `docs/todo.md`, Punkt 30). Regel 1 sieht nur Namen: „tonhalle" und „nrw-forum" bleiben als
  eigene Lemmata im Wörterbuch (`docs/methodik-review-2026-10.md`).
- Im Wahlbezirk 11 ist Die Linke nicht angetreten (0 Stimmen); der Abgleich Dokumentanteil gegen
  Stimmenanteil lässt solche Bezirke je Partei aus, Die Linke hat dort n = 40 statt 41.

Offenes: `docs/todo.md`.
