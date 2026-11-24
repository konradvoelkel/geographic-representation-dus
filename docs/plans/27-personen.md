# Vorhaben 27: Personen und Mandatstyp

Stand 2026-11-24, Stufe 1 (Messen), Branch `feat/27-personen`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „27 Personen und
Mandatstyp". Messskript: [27-personen-messung.py](27-personen-messung.py). Codebuch und Stichprobe:
`validierung/27-personen/`.

Die Hypothesen (§ 8) sind im Commit `038699e` (2026-11-24, 00:40 Uhr) festgelegt, **bevor** eine Anfrage
einer Person, ein Ratsmitglied einem Mandatstyp oder einem Wahlbezirk zugeordnet und bevor ein
Wahlergebnis mit Namen geladen war (§ 2.11 des Meta-Plans); § 8 ist danach nicht geändert. Das Maß *Y*
der Hypothese ist nirgends gebildet, auch nicht gepoolt.

Personen kommen nur als Mandatsträger in öffentlicher Rolle vor (Plan § 1). Namen bleiben lokal; in
diesem Dokument, im Messskript und unter `validierung/27-personen/` stehen nur OParl-Kennungen,
Wahlbezirksnummern, Rollen, Codes und Zählungen. Die Endlabels der Kodierer sind Nachnamen und darum
gitignored (`validierung/27-personen/.gitignore`); ins Repo geht `labels-kennungen.csv` (§ 4).

**Vorläufiges Urteil (vor der Kodierung): umbauen.** Die Zuordnung Dokument → Person und der Mandatstyp
taugen als Daten für 24, 26 und 28 und für Rollen und Zählungen auf `akteure.html`; die Hypothese H1
ist mit diesen Daten **nicht entscheidbar**, gleich wie die Kodierung ausgeht (§ 5). Die drei Zahlen:

1. **Mandatstyp**: in der laufenden Periode für **92 von 93** Ratsmitgliedern bekannt (0,989), in der
   Hauptperiode nur für **62 von 94** Sitzen (0,660): der OParl-Server nennt Ratsmitglieder, die 2025
   ausgeschieden sind, nicht mehr (§ 3.2). Das Kriterium (≥ 90 %) hält also nur die laufende Periode.
2. **Zuordnung Dokument → Person**: 90,1 % der Anfragen in Rat und Ausschüssen der laufenden Periode
   und 62,1 % der Hauptperiode bekommen mindestens ein Ratsmitglied; die Präzision misst die Kodierung
   an 150 Dokumenten (vorbereitet, § 4).
3. **Fallzahl**: Mandatstyp und Partei sind fast deckungsgleich (die CDU gewann 2020 alle 30 und 2025
   alle 31 Sitze direkt, die SPD je einen von 16 und 14; vergleichen lässt sich nur innerhalb der
   Grünen). Das vorab festgelegte Modell erreicht in der Simulation nur eine **Teststärke von 0,466**
   bei OR 1,5 und verwirft unter H0 in **38,5 %** statt 5 % der Läufe (§ 3.6): H1 ist nach § 8.3 und
   § 8.4 nicht entscheidbar.

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

**Frage** (Briefing): Fragen direkt gewählte Ratsmitglieder öfter nach ihrem eigenen Wahlbezirk als über
die Liste gewählte? Dafür braucht es drei Dinge, die die Kette heute nicht hat: wer ein Dokument
einbringt (als Person, nicht als Fraktion), welchen Mandatstyp ein Ratsmitglied hat, und welcher
Wahlbezirk „seiner" ist.

**Literatur.** Zittel, Nyhuis und Baumann (2019) zählen Ortsbezüge in schriftlichen Fragen des
Bundestags und lesen sie als geografische Repräsentation (Abstract: mehr bei lokal verwurzelten
Abgeordneten und in wechselhaften Wahlkreisen; Volltext hinter Bezahlschranke). Harmening u. a. (2025)
zeigen mit demselben Werkzeug wie dieses Projekt an 10 189 Anfragen aus zwölf Großstädten, dass
**Parteien** ihre Hochburgen öfter nennen; 6 948 dieser Anfragen stellte ein einzelnes Ratsmitglied,
aber den Mandatstyp untersucht die Arbeit nicht (Einheit ist die Partei je Stadtteil; gelesen auf der
Verlagsseite, 2026-11-24). Die Frage ist also auf kommunaler Ebene offen. Diese Messung zeigt, warum
sie in Düsseldorf kaum zu beantworten ist: der Mandatstyp variiert fast nur zwischen Parteien, nicht
in ihnen (§ 3.1).

**Nutzen für die Ratsarbeit, unabhängig von H1.** Wer ein Dokument einbringt, ist die Grundlage für
24 (Fragesteller als Person), 26 (Antragserfolg je Antragsteller) und 28 (Abstimmungen), und für
Fragen wie „wie viele Anträge zeichnen mehrere Fraktionen gemeinsam, wie viele eine einzelne Person"
(15). Auf die Seite kommen davon nur Rollen und Zählungen, nie eine Person (§ 7).

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

### 2.1 OParl (Netzlauf aus F6, 2026-11-23/24)

Kopiert aus `/media/konrad/xtraspace/georep/data/<profil>/raw/` in die Datenwurzel des Worktrees
(nur gelesen): `persons.jsonl` (268 868 Bytes, 632 Personen), `memberships.jsonl` (2 163 277 Bytes,
4 615 Mitgliedschaften), `meetings.jsonl`, `agenda_items.jsonl`, `consultations.jsonl`; die Dateien von
`duesseldorf` und `2025` sind bei Personen und Mitgliedschaften bytegleich (eine Liste je Body). Gelesen
mit `georep.council.JsonlStore` und den Modellen `OparlPerson` (`family_name`, `given_name`;
Kontaktdaten kennt das Modell nicht), `OparlMembership` (`person`, `organization`, `role`,
`start_date`, `end_date`), `OparlMeeting` (`organization`, `start`, `participant`).

- **Wer ist Mandatsträger.** Rat: Mitgliedschaft in `gr/6` mit Rolle „Mitglied" oder eine Rolle mit
  „Ratsmitglied" (ohne „beratendes Ratsmitglied", das in den Bezirksvertretungen steht und immer eine
  Ratsmitgliedschaft daneben hat: 163 von 163). Bezirksvertretung: „Mitglied" in `gr/32` bis `gr/41`
  oder eine Rolle mit „Bezirksvertretungsmitglied", „BV-Mitglied" oder „Bezirksbürgermeister".
  Nicht: Fraktionsmitarbeiter, Geschäftsführung, Verwaltung, Personalrat, sachkundige Bürgerinnen und
  Einwohner (nicht gewählt). So bleiben **288** der 632 Personen.
- **`originatorPerson`**: in keinem Dokument gefüllt (0 von 19 108, `interim/papers.parquet`), wie die
  übrigen Urheberfelder (Runbook F6, § 2).
- **Lücke**: der Server nennt ausgeschiedene Personen nicht mehr. Ratsmitgliedschaften laufen am
  2021-06-01 für 57 Personen, am 2025-12-01 für 92; die Ratssitzungen der Hauptperiode nennen 65
  verschiedene Teilnehmer (die von 29 der 42 Sitzungen mit Liste), die der laufenden 94. Für 2014 bis
  2020 laufen höchstens 35 (§ 3.2).

### 2.2 Wahlergebnisse (Fremddaten, lokal)

`/media/konrad/xtraspace/georep/fremddaten/wahlen/votemanager-duesseldorf/` (README mit Quelle,
Abrufdatum, Größe, SHA-256 und Lizenzangabe; 94 Dateien, 1 335 085 Bytes): die amtliche
Wahlergebnispräsentation der Stadt (votemanager auf `wep.itk-rheinland.de`, von duesseldorf.de
verlinkt), Ratswahl 2020 (ID 61) und 2025 (ID 89). Je Wahlbezirk `ergebnis_ebene_5_id_<n>_0.json`:
`seitentitel` (Nummer des Wahlbezirks), `Komponente.tabelle.zeilen[].label.labelKurz` („Vorname Name,
PARTEI"), `.zahl`, `.prozent`, `Komponente.gewaehlte_kandidaten.items[].label` (der Gewinner); die
Stadt: `Komponente.sitze.tortenDiagramm.entries[]` (`label`, `sitze`). **Lizenz**: keine Datenlizenz
angegeben (README). Ins Repo kommt davon nichts; abgeleitet werden nur Wahlbezirk, Partei, gewonnen,
Vorsprung und OParl-Kennungen.

Nicht gefunden: eine Präsentation der Ratswahl 2014, die Bekanntmachung der 2020 über die
Reservelisten Gewählten (Amtsblatt-Archiv der ULB: 403) und die Flächen der Wahlbezirke 2014. Die
Periode 2014 bis 2020 ist darum nicht gemessen (§ 9, Frage 27.2). Geladen und nicht benutzt: zwei PDF
von IT.NRW ohne Namen (`fremddaten/wahlen/itnrw/`).

### 2.3 Aus der Kette und aus anderen Vorhaben

- Je Profil (`georep run` im Worktree, 2026-11-24): `interim/papers.parquet` (`id`, `reference`,
  `paper_type`, `name`, `date`, `file_name`), `processed/papers_gremien.parquet` (`gremium_art`,
  `stadtbezirk`), `processed/dokumente_urheber.parquet` (`urheber_art`: nur `Fraktion` und `Person`
  zählen als politisch), `processed/inverted_index.parquet` und `combined_searchdict.parquet` (Treffer
  je Wahlbezirk, Zuschnitt 2025), `processed/wahlbezirke_stadtbezirke.parquet`,
  `external/Stimmbezirke_2025.geojson`.
- Rohtext als Messdatei: `messdaten/rohtext/<profil>.parquet` (`name`, `text`); er ist bis auf ein
  Dokument gleich dem Store von F1 (`cache_root/duesseldorf/text/rohtexte.parquet`, 19 090 von 19 091),
  aus dem die Kodieraufträge lesen.
- Zuschnitt 2020: `snapshots/2014-2020/external/Kommunalwahlbezirke.geojson` (41 Flächen, EPSG:4647).
- Rolle `anfrage`/`antrag`: `art()` aus `14-vorgaenge-messung.py`, wörtlich übernommen. Fraktionen:
  `[originators]` des Profils (Volt zur SPD, Klimaliste zur PARTEI).
- Aus 11: der Unterzeichner als Amtsbezeichnung steht in 4,9 % der Unterschriftsblöcke; 11 empfiehlt
  OParl statt Text. Hier zählt der **Name** im Unterschriftsblock, nicht die Amtsbezeichnung, und nur,
  wenn er einem Mandatsträger aus OParl gehört.

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

Alle Zahlen vom 2026-11-24, `uv run python docs/plans/27-personen-messung.py --sim 1000 --stichprobe`
(rund zwei Minuten; ohne `--sim` 30 Sekunden). Seed der Simulation 20261124.

### 3.1 Kandidaturen und Sitze

| | 2020 | 2025 |
|---|---|---|
| Wahlbezirke, Kandidaturen | 41, 552 | 41, 489 |
| Sitze (aufgestockt von 82) | 90 | 92 |
| direkt gewonnen: CDU / Grüne / SPD | 30 / 10 / 1 | 31 / 9 / 1 |
| Sitze CDU / Grüne / SPD | 30 / 22 / 16 | 31 / 20 / 14 |
| Listensitze aller übrigen Parteien | 22 | 27 |
| Gewinner mit Vorsprung unter 5 Punkten | 7 | 3 |

**Mandatstyp und Partei sind fast deckungsgleich.** Die CDU hat in beiden Perioden keinen einzigen
Listensitz (Überhang), FDP, Linke, AfD und die kleinen Parteien keinen Direktsitz. Innerhalb einer
Partei gibt es beide Typen nur bei den Grünen (10 zu 12, 9 zu 11) und mit je einem Direktsitz bei der
SPD; dazu kommen Nachrücker, die über die Liste in eine Fraktion mit Direktmandaten kommen.

### 3.2 Mandatstyp je Ratsmitglied

**Ratsmitglied einer Periode** (Ratsperiode ab dem 1. November nach der Wahl): eine
Ratsmitgliedschaft überlappt die Periode, und die Person steht in der Teilnehmerliste einer
Ratssitzung der Periode oder ihre Mitgliedschaft beginnt in ihr. Ohne die Teilnahme zählten Mitglieder
des alten Rats mit, deren Mitgliedschaft kein Ende trägt (`endDate` zu 7 % gefüllt): 71 statt 64 in der
Hauptperiode, 103 statt 93 in der laufenden.

**Zuordnung zur Kandidatur**: Vor- und Nachname (normiert: klein, ohne Titel und Akzente, ß als ss),
sonst Nachname mit gleichem Anfangsbuchstaben des Vornamens. Gewonnen → direkt; verloren → Liste mit
eigenem Wahlbezirk; keine Kandidatur → Liste ohne eigenen Wahlbezirk, **außer** ein nicht
zugeordneter Gewinner könnte dieselbe Person sein (Nachname mit denselben vier Anfangsbuchstaben oder
gleicher Vorname) → unbekannt. **Bekannt** heißt: OParl-Kennung und Mandatstyp; Nenner sind die Sitze
der Wahl plus die Nachrücker, die OParl kennt (Sitz ab dem 61. Tag der Periode).

| | Hauptperiode 2020–2025 | laufende Periode seit 2025 |
|---|---|---|
| Ratsmitglieder in OParl | 64 | 93 |
| direkt / Liste / unbekannt | 30 / 32 / 2 | 40 / 52 / 1 |
| davon über den vollen Namen zugeordnet / ohne Kandidatur | 53 / 11 | 82 / 11 |
| Gewinner der 41 Wahlbezirke mit OParl-Kennung | 30 | 40 |
| **Mandatstyp bekannt, je Sitz** | **62 / 94 = 0,660** (0,559–0,747) | **92 / 93 = 0,989** (0,942–0,998) |
| dazu eigener Wahlbezirk bekannt, je Sitz | 53 / 94 = 0,564 | 82 / 93 = 0,882 |
| bekannt unter den OParl-Ratsmitgliedern | 62 / 64 = 0,969 | 92 / 93 = 0,989 |

Die Hauptperiode verfehlt 90 % nicht an der Zuordnung, sondern an der Quelle: elf Gewinner und rund
zwanzig Listenmitglieder von 2020 kennt der Server nicht mehr. Die elf Ratsmitglieder je Periode ohne
Kandidatur sind über die Liste gewählt, ohne in einem Wahlbezirk anzutreten, oder heißen auf dem
Stimmzettel anders als in OParl (nicht geprüft, Namen bleiben lokal).

### 3.3 Zuordnung Dokument → Person: die Regel

Nur politische Dokumente (Urheberklasse Fraktion oder Person nach Option 4). Kandidaten sind die
Mandatsträger aus OParl, deren Rats- oder BV-Mitgliedschaft das Datum des Dokuments umfasst (14 Tage
Toleranz). Drei Wege, jeder Name nur aus dieser geschlossenen Liste, nie aus freiem Text erkannt:

1. **Titel**: hinter einer Rollenbezeichnung (Ratsherr, Ratsfrau, Herr, Frau, Bezirksvertreterin …)
   der Nachname eines Mandatsträgers im Gremium des Dokuments („Anfrage des Ratsherrn X", „Antrag von
   Frau Y (SPD-Fraktion)"); bei gleichem Nachnamen entscheidet der Vorname, sonst nichts.
2. **Briefkopf**: der volle Name (Vorname, bis zu zwei weitere Worte, Nachname) in den ersten 400
   Zeichen **vor** der Anrede („An", „Herrn", Bezirksbürgermeister, Oberbürgermeister, Vorsitz,
   „Betrifft", „Sehr geehrte"); so fällt der Empfänger heraus.
3. **Unterschrift**: der volle Name in 400 Zeichen nach dem ersten Gruß hinter dem Kopf („Mit
   freundlichen Grüßen", „gez."), abgeschnitten vor „f. d. R.", „für die Richtigkeit", „Anlage",
   „Seite n", „Beratungsfolge", „Quelle". Fehlen im Text die Leerzeichen, wird ohne sie verglichen.

Zwei Mandatsträger mit demselben Vor- und Nachnamen am selben Datum: keine Zuordnung („mehrdeutig").

### 3.4 Abdeckung

| Hauptperiode (ab 2020-11-01) | Dokumente | mit Person |
|---|---|---|
| politische Dokumente (Anträge, Anfragen) | 8 645 | |
| Rat | 1 685 | 0,762 |
| Ausschuss | 1 736 | 0,609 |
| Bezirksvertretung | 5 166 | 0,551 |
| Anfragen / Anträge | 3 785 / 4 860 | 0,583 / 0,622 |
| **Anfragen in Rat und Ausschüssen** | 1 615 | 0,669; mit **Ratsmitglied 0,621** (0,597–0,644) |

| laufende Periode (ab 2025-11-01) | Dokumente | mit Person |
|---|---|---|
| politische Dokumente | 1 838 | |
| Rat / Ausschuss / Bezirksvertretung | 455 / 382 / 996 | 0,714 / 0,906 / 0,756 |
| **Anfragen in Rat und Ausschüssen** | 484 | 0,905; mit **Ratsmitglied 0,901** (0,871–0,924) |

Wege je Paar Dokument–Person: Hauptperiode Unterschrift 6 143, Titel 831, Briefkopf 233 (mehrdeutig
verworfen bei 213 Dokumenten); laufende Periode 1 701, 365, 141 (38). Personen je zugeordnetem
Dokument: eine bei 3 618, zwei bei 1 334, drei und mehr bei 276 (Hauptperiode). Der Unterschied der
Perioden ist die Lücke aus § 3.2: wer 2025 ausschied, kann nicht zugeordnet werden. Unterschriften
ohne Namen („AfD-Ratsfraktion") und sachkundige Bürger fehlen in beiden.

### 3.5 Die Grundgesamtheit der Prüfung (ohne *Y*)

| | Hauptperiode | laufende Periode |
|---|---|---|
| Paare Anfrage × Ratsmitglied | 1 207 | 515 |
| nutzbar (Mandatstyp und eigener Wahlbezirk bekannt) | 984 aus 828 Anfragen, 42 Personen | 429 aus 383 Anfragen, 52 Personen |
| davon Paare direkt / Liste | 237 / 747 | 43 / 386 |
| Fraktionen mit beiden Typen: Paare direkt / Liste (Personen) | CDU 130 / 1 (15 / 1), Grüne 107 / 23 (7 / 3) | SPD 2 / 137 (1 / 12), Grüne 14 / 7 (5 / 4) |

Über beide Perioden: 1 413 Paare von 73 Personen, 280 davon direkt; 16 Gruppen Fraktion × Periode,
in 4 davon kommen beide Typen vor (421 Paare, 45 Personen). Nur diese tragen zur Schätzung von β bei
(§ 8.3: feste Effekte Fraktion × Periode). Die **Basisrate** (Anteil der übrigen Anfragen, die den
eigenen Wahlbezirk treffen) liegt im Median bei 0,014; 23,6 % der Anfragen der Hauptperiode und 24,9 %
der laufenden treffen überhaupt einen Wahlbezirk. Unter H0 sind über alle Paare rund 25 Treffer zu
erwarten.

**Zuschnitt.** Die Wahlbezirke 2020 und 2025 haben dieselbe Zahl, aber nicht dieselben Grenzen: die
größte Überlappung eines Wahlbezirks 2020 mit einem von 2025 liegt im Median bei 0,697 seiner Fläche
(Minimum 0,346), bei 24 von 41 unter 0,8, und nur 12 tragen dieselbe Nummer. Die Näherung der Stufe 1
(eigener Wahlbezirk 2020 → der von 2025 mit der größten Fläche, R7) ist also grob; § 8.2 verlangt
für die Prüfung ein Wörterbuch im Zuschnitt 2020, das Stufe 2 aus den Flächen im Snapshot bauen kann.

### 3.6 Teststärke (§ 8.4), mit der Struktur aus § 3.5

1 000 Läufe je Szenario, *Y* künstlich aus der Basisrate, das Modell aus § 8.3 (logistisch, feste
Effekte Fraktion × Periode, Basisrate und *k* als Kovariaten, Standardfehler nach Person geclustert).
Umsetzung: Gruppen, in denen *Y* in einem Lauf nicht streut, fallen vor der Schätzung heraus, wie in
fixest (ihr fester Effekt hätte keinen endlichen Schätzer und trägt zu β nichts bei); „Trennung" ist
der Anteil der Läufe mit |β| > 5.

| Szenario | Anteil p < 0,05 | Treffer je Lauf (Median) | Trennung |
|---|---|---|---|
| **OR 1,5, *a* = 0, Streuung 0,5 (entscheidend)** | **0,466** | 30 | 0,106 |
| **OR 1,0 (Fehler erster Art)** | **0,385** | 28 | 0,112 |
| OR 1,25 | 0,443 | 29 | 0,108 |
| OR 2,0 | 0,516 | 32 | 0,105 |
| OR 1,5, *a* = log 2 | 0,394 | 57 | 0,016 |
| OR 1,5, Streuung 1,0 | 0,426 | 39 | 0,069 |
| *Vorschlag, nicht vorab festgelegt*: Stadtbezirk statt Wahlbezirk, OR 1,0 | 0,207 | 83 | 0,001 |
| *ebenso*, OR 1,5 | 0,259 | 89 | 0,002 |

**Das Modell hält sein Niveau nicht.** Unter H0 verwirft es in 38,5 % der Läufe statt in 5 %, und die
Teststärke bei OR 1,5 liegt mit 0,466 kaum darüber: die Rejektionsrate misst hier vor allem den Fehler
des Tests, nicht den Effekt. Ursachen, beide aus der Struktur und nicht aus *Y*: (1) seltene Ereignisse
(rund 30 Treffer je Lauf; die vier gemischten Gruppen tragen 421 der 1 413 Paare, also nur einen Teil davon) machen den logistischen Schätzer in
den vier gemischten Gruppen verzerrt, in jedem zehnten Lauf trennt er; (2) der Kontrast hängt an sehr
wenigen Personen der Minderheit je Gruppe (eine CDU-Listenperson mit einem Paar, drei und vier
Grünen-Listenpersonen, eine SPD-Direktperson mit zwei Paaren), und geclusterte Standardfehler mit so
wenigen „behandelten" Clustern sind bekanntlich viel zu klein. Auch der gröbere Stadtbezirk, der die
Ereignisse verdreifacht, bringt den Fehler erster Art nur auf 0,207. Nach § 8.4 entscheidet die
Teststärke der Stufe 2; sie kann mit denselben Fraktionen nicht wesentlich besser werden, denn mehr
Zuordnungen ändern nichts daran, dass es kaum Listenmitglieder bei der CDU und kaum Direktmitglieder bei
der SPD gibt.

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

**Codebuch** `validierung/27-personen/codebuch.toml`, Fassung 2026-11-24.1, Einheit `document`, Format
F4. Frage `fragesteller`: offene Liste der Nachnamen aller Personen, die das Dokument einbringen (im
Titel als Fragesteller oder Antragstellerin, als Absender im Briefkopf, in der Unterschrift), klein, ohne
Titel und Vornamen, als Menge (`unordered`), Leerraum egal (`whitespace = "ignore"`); nicht: Empfänger
und Anrede, „f. d. R.", Personen im Gegenstand, die Verwaltung. Meta-Frage `unsicher` ohne Schlichtung.
Die Kodierer sehen Titel und 6 000 Zeichen Rohtext, **nicht** die Personen des Verfahrens.

**Stichprobe** (`georep validate sample 27-personen`, 2026-11-24): Grundgesamtheit
`<data_root>/duesseldorf/messung/27-personen-grundgesamtheit.parquet` aus dem Messskript
(`--stichprobe`): Anträge und Anfragen der Hauptperiode ab 2020-11-01 mit Rohtext, Schicht
`rat_ausschuss` (Rat, Ausschuss, Beirat; 2 343 mit Zuordnung), `bezirksvertretung` (2 835),
`ohne_zuordnung` (3 401, nicht gezogen). Zugeordnete, deren Beleg hinter 6 000 Zeichen liegt, fallen
vorher heraus (48), weil die Kodierer ihn nicht sähen. Gezogen: **150**, je 75 aus den beiden
zugeordneten Schichten (`allocation = "equal"`, Seed 20261124, nicht selbstgewichtend;
`stichprobe.csv`, `stichprobe.json` mit SHA-256 der Grundgesamtheit).

**Aufträge** (lokal, nie im Repo): `/media/konrad/xtraspace/georep/messdaten/kodierung/27-personen/A/`
und `…/B/` (je `auftrag.jsonl`, `antworten.jsonl`, `codebuch.md`; `validation.coding_root` steht in der
`settings.local.toml` des Worktrees). Die Vorhersage des Verfahrens liegt getrennt unter
`messdaten/27-personen/vorhersage.parquet`. Die Kodierer startet der Supervisor (Prompt
`docs/validierung.md`, § 4.1), danach `georep validate merge 27-personen`.

**Maße** (`--labels`, vorab festgelegt): **Präzision je Paar** Dokument–Person = Anteil der Personen des
Verfahrens, deren normierter Nachname im Endlabel steht, je Schicht mit Wilson-Intervall und mit den
Schichtgewichten der Grundgesamtheit (Kish, wie F4); **Kriterium ≥ 0,95 gewichtet**. Daneben: Anteil
der Dokumente, deren Personen alle bestätigt sind (streng), und der Recall innerhalb der zugeordneten
Dokumente (Personen des Labels, die das Verfahren nicht nennt: sachkundige Bürger, ausgeschiedene
Mitglieder, Namen ohne OParl-Eintrag). Übereinstimmung der Kodierer: α aus `merge` (Stufe 3 verlangt
≥ 0,8).

**Personendaten in den Labels.** `labels.csv` trägt Nachnamen und ist gitignored. Das Messskript
schreibt `labels-kennungen.csv` (`id`, `schicht`, Kennungen des Verfahrens, Kennungen der gelabelten
Personen, soweit am Datum eindeutig, Zahl der Labels ohne Kennung, bestätigte Paare); diese Datei,
`README.md` und `guete.json` aus `merge` dürfen ins Repo.

## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

Kriterium (Briefing): Zuordnung Dokument → Person mit Präzision ≥ 0,95 an 150 **und** Mandatstyp für
≥ 90 % der Ratsmitglieder, dazu eine vorab festgelegte Hypothese mit Fallzahl.

| Teil | Stand | erfüllt? |
|---|---|---|
| Präzision der Zuordnung | Kodierung vorbereitet, 150 Dokumente | offen |
| Mandatstyp ≥ 90 % | laufende Periode 0,989; Hauptperiode 0,660 | nur laufende Periode |
| Hypothese vorab festgelegt | Commit `038699e` | ja |
| Fallzahl | Teststärke 0,466, Fehler erster Art 0,385 | nein |

**Vorläufiges Urteil: umbauen.** Die Hypothese H1 ist **nicht entscheidbar** (§ 8.3: Teststärke unter
0,8; in der Hauptperiode zudem Mandatstyp unter 90 %); das steht so auf der Seite, wenn überhaupt, und
nicht als „kein Unterschied". Daran ändert die Kodierung nichts. Gebaut wird, **wenn die Kodierung die
Präzision 0,95 bestätigt**, der Beitrag `persons` als Datengrundlage: Mandatsträger mit Zeiträumen und
Fraktion, Dokument → Person, Mandatstyp und eigener Wahlbezirk je Ratsmitglied, und auf `akteure.html`
nur Rollen und Zählungen (§ 6, § 7). Verfehlt die Kodierung 0,95, geht die Regel in die eine
Umbau-Runde (Kandidaten: Titelweg ohne „Herr/Frau", Unterschrift nur bis zur ersten Leerzeile).
Verwerfen wäre falsch: 24 wartet auf den Fragesteller als Person, 26 und 28 auf Antragsteller und
Mandatsträger.

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

**Beitrag `persons`** (`src/georep/enrich/persons.py`, angehängt im Tupel von F2 vor
`report`; er liest nur Korpus, Urheber und den Rohtext von F1), drei Schritte, alle offline:

1. **`mandates`** liest `raw/persons.jsonl`, `memberships.jsonl`, `meetings.jsonl` (`council_files`)
   und schreibt `processed/mandate.parquet`: `person` (OParl-URL), `gremium` (`RAT`, `BV1` … `BV10`,
   `BV` ohne Nummer), `beginn`, `ende` (Date, offen = null), `fraktion` (Schlüssel aus
   `[originators]`), `ratssitz_periode` (bool, Regel § 3.2). **Keine Namen.** Schema-Version aus der
   Modulkonstante, sortiert nach `person, gremium, beginn`.
2. **`signers`** liest Korpus, `dokumente_urheber`, den Rohtextstore (F1) und Namen aus
   `persons.jsonl` **nur im Speicher**; schreibt `processed/dokumente_personen.parquet`: `id`, `person`,
   `weg` (`titel`, `kopf`, `unterschrift`), `start`, `end` (Spanne des Belegs nach F3, `kind = person`,
   `value` leer: der Name steht nicht in der Datei), eine Zeile je Paar, dazu `processed/
   dokumente_personen_status.parquet` (`id`, `n_personen`, `mehrdeutig`).
3. **`mandate_types`** liest ein Paket mit den Kandidaturen (`snapshots/<profil>-wahl/`:
   `kandidaturen.parquet` mit `jahr`, `wahlbezirk`, `partei`, `stimmen`, `anteil`, `gewonnen`,
   `vorsprung`, `person` (OParl-Kennung oder leer), **ohne Namen**) und schreibt
   `processed/mandatstyp.parquet`: `person`, `periode`, `typ` (`direkt`, `liste`, `unbekannt`),
   `wahlbezirk`, `nachruecker`. Das Paket entsteht lokal mit `georep pack --elections` aus den
   Fremddaten (die Namen braucht nur der Abgleich, der in `pack` läuft; Lizenzangabe: amtliches
   Wahlergebnis ohne Datenlizenz, Frage 27.3).

**Verträge**: Ausgaben sortiert und eindeutig (`id, person`); `0 <= start < end <= len(text)`;
Nachbedingung „keine Spalte enthält einen Namen" als Eigenschaft (unten). **Tests**: Fake-Personen und
-Mitgliedschaften in `tests/fixtures/` (erfundene Namen), Beispiele je Weg (Titel, Kopf mit Empfänger
danach, Unterschrift mit „f. d. R.", geklebter Text ohne Leerzeichen, gleicher Name zweier Personen);
hypothesis: für beliebige Namen und Texte enthält keine Ausgabedatei einen Vor- oder Nachnamen;
Zuordnung ist invariant gegen die Reihenfolge der Personen; ein Empfänger hinter „An" wird nie
zugeordnet. **Settings**: Block `# --- Vorhaben 27: Personen und Mandatstyp` am Ende von
`defaults.toml` (`persons.enabled = false`, Rollenmuster für Mandat und Stab, Grußformeln,
Kopfende, Fenster 400 Zeichen, Toleranz 14 Tage), im Stadtprofil die Organisationen von Rat und
Bezirksvertretungen (heute `[bodies.organizations]`, `gr/6`, `gr/32` bis `gr/41`) und die Wahlen
(`[persons.elections]`: Jahr, Quelle, Ratsperiode). **Berührte Dateien**: `enrich/__init__.py` (eine
Zeile), `settings.py` (ein Modell vor `Settings`, ein Feld am Ende), `defaults.toml`,
`profiles/duesseldorf*.toml`, `pack.py` (`--elections`, oder Paketregister F7), `architecture.md`,
Entscheidungspunkt ohne Nummer. **Profile**: laufende Periode voll; Hauptperiode mit der Lücke aus
§ 3.2 (Seite nennt sie); 2014–2020 und Mönchengladbach ohne Wahlpaket (der Schritt `mandate_types`
fehlt dort, `signers` läuft).

**Was Stufe 2 nicht baut**: die Prüfung von H1 (nicht entscheidbar, § 5) und das Wörterbuch im
Zuschnitt 2020 (nur für H1 nötig).

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

Ein **Abschnitt auf `akteure.html`** (15; F2 braucht dafür Abschnitte aus fremden Beiträgen,
Synergien § 1), rund 10 bis 15 KB, **nur Rollen und Zählungen**, nie eine Person und nie eine Zeile je
Person:

- „Wer zeichnet": Anteil der Anträge und Anfragen mit namentlicher Unterschrift je Gremienart und
  Periode; Zahl der Unterschriften je Dokument (eine, zwei, drei und mehr); Anteil, den Ratsmitglieder
  gegenüber Bezirksvertretern zeichnen.
- „Direkt und über die Liste": Sitze je Partei und Mandatstyp aus dem amtlichen Ergebnis (öffentlich,
  ohne Namen) und der Satz, warum der Vergleich hier nicht trägt (§ 3.1, § 3.6): „nicht entscheidbar",
  mit der Festlegung (Commit `038699e`).
- **Zellenregel**: keine Zahl für eine Zelle mit weniger als fünf Personen (eine Fraktion mit einem
  Listenmitglied machte die Person kenntlich).
- Validierung im Satz aus `guete.json` („geprüft von zwei KI-Kodierern an 150 Dokumenten, nicht von
  Menschen"), mit Präzision und Intervall.

Tabellen im Register (F2): `mandate` (ohne Namen, Downloads als CSV) und `dokumente_personen` nur als
Zählung je Dokument (`n_personen`), nicht als Paar mit Kennung — die Kennung macht über die OParl-API
die Person sichtbar (Frage 27.4).

## 8. Vorab festgelegte Hypothesen (nur Analysen: Hypothese, Maß, Test, Schwelle)

Festgelegt am 2026-11-24 um 00:40 Uhr (Commit `Hypothesen von Vorhaben 27 vorab festlegen`), bevor eine Anfrage einer Person, ein Ratsmitglied einem
Mandatstyp oder ein Ratsmitglied einem Wahlbezirk zugeordnet war, und bevor Wahlergebnisse mit Namen
geladen waren. **Bekannt war zu diesem Zeitpunkt nur**: die Zahl der Personen (632) und
Mitgliedschaften (4 615) im Netzlauf aus F6 und deren Rollen; wie viele Mitgliedschaften im Rat
(`gr/6`) zu einigen Stichtagen laufen (rund 31 bis 35 vor 2020, 54 bis 63 zwischen 2021 und 2025, 89
seit Ende 2025: der Server nennt ausgeschiedene Mitglieder offenbar nicht mehr); die Verteilung der
Urheberklassen aus Vorhaben 15 nach Gremium; Anfang und Ende von neun Anfragen, gelesen nur, um das
Format von Absender und Unterschrift zu sehen (nicht gezählt); `originatorPerson` ist in keinem
Dokument der Hauptperiode gefüllt. Weder Ortsbezüge je Person noch je Mandatstyp waren gerechnet.
In Stufe 1 wird **keine** Probe der Hypothese gerechnet, auch keine vorläufige: das Messskript bildet
das Maß *Y* (§ 8.2) nicht, auch nicht gepoolt (dieselbe Regel wie 24, § 8, nach Punkt 61).

**Bezug.** Zittel, Nyhuis und Baumann (2019) zählen Ortsbezüge in den schriftlichen Fragen des
Bundestags als Maß geografischer Repräsentation und finden sie trotz starker Fraktionsdisziplin, mehr
bei lokal verwurzelten Abgeordneten und in Wahlkreisen mit wechselhaften Ergebnissen; den Volltext
konnte der Mess-Agent nicht lesen (Bezahlschranke), die Angabe stammt aus dem Abstract. Harmening u. a.
(2025) zeigen an 10 189 Anfragen aus zwölf deutschen Großstädten, dass **Parteien** ihre Hochburgen
öfter nennen, verstärkt bei räumlich konzentrierter Wählerschaft und in Städten mit Wahlbezirken; der
Mandatstyp einzelner Ratsmitglieder ist dort nicht untersucht (Einheit ist die Partei je Stadtteil).
In Nordrhein-Westfalen hat jede Wählerin eine Stimme, die zugleich für die Bewerberin im Wahlbezirk und
für die Reserveliste ihrer Partei zählt; im Wahlbezirk gewinnt die relative Mehrheit, die übrigen Sitze
kommen über die Reservelisten. Wer über die Liste einzieht, hat fast immer selbst in einem Wahlbezirk
kandidiert und verloren. Das macht den Vergleich möglich, den das Briefing fragt: dieselbe Art
„eigener" Wahlbezirk, einmal gewonnen, einmal nicht.

### 8.1 H1 (die Hauptthese, sie allein entscheidet)

> Ratsmitglieder, die ihren Wahlbezirk direkt gewonnen haben, nennen in den Anfragen, die sie stellen,
> ihren eigenen Wahlbezirk häufiger als Ratsmitglieder, die über die Reserveliste in den Rat gekommen
> sind, ihren eigenen Wahlbezirk (den, in dem sie kandidiert haben).

### 8.2 Einheit, Maß, Grundgesamtheit

- **Dokumente**: Anfragen (Rolle `anfrage` nach Vorhaben 14, `art()`; Dokumentart mit „Anfrage") in
  **Rat oder Ausschuss** (`gremium_art` `rat` oder `ausschuss`, Schritt `bodies`), aus den Profilen
  `duesseldorf` (2020–2025), `duesseldorf-2014` (2014–2020) und `duesseldorf-2025` (seit 2025).
  Bezirksvertretungen gehören nicht zur Hauptprüfung: ihre Mitglieder werden nur über Listen gewählt.
- **Einheit**: ein Paar (Anfrage *d*, Person *p*), wenn das in Stufe 1 validierte und danach
  eingefrorene Verfahren (§ 3) *p* als Fragestellerin oder Unterzeichnerin von *d* nennt und *p* am
  Datum von *d* Ratsmitglied der Periode ist. Eine Anfrage mit drei Unterzeichnern gibt drei Paare.
  Zeichnende „f. d. R.", Empfänger (Vorsitzende) und Personen, über die gefragt wird, sind keine
  Fragesteller (Codebuch, § 4).
- **Mandatstyp** *D*(*p*) ∈ {direkt, Liste}: direkt, wenn *p* bei der Wahl, die die Periode eröffnet
  (2014-05-25, 2020-09-13, 2025-09-14), einen Wahlbezirk gewonnen hat; Liste, wenn *p* über die
  Reserveliste gewählt wurde oder später aus ihr nachgerückt ist. Quelle ist das amtliche
  Wahlergebnis (Stadt, Wahlleiter), nicht OParl; OParl liefert die Kennung und die Mitgliedschaft.
- **Eigener Wahlbezirk** *w*(*p*): bei direkt Gewählten der gewonnene, bei Listenmitgliedern der, in
  dem sie bei derselben Wahl kandidiert haben, nach den amtlichen Wahlvorschlägen oder dem Ergebnis je
  Wahlbezirk. Wer über die Liste kam und in keinem Wahlbezirk kandidiert hat, fällt aus der
  Hauptprüfung (kein eigener Wahlbezirk); die Zahl wird berichtet.
- **Zuschnitt**: der der Wahl, die die Periode eröffnet. Ortsbezüge werden mit dem Wörterbuch-Verfahren
  der Kette (Schritte `dictionary`, `index`, die Settings des Commits, mit dem geprüft wird) auf die
  Wahlbezirke **dieses** Zuschnitts bezogen. Eine Periode, für deren Zuschnitt Stufe 2 kein Wörterbuch
  bauen kann (fehlende Flächen), fällt aus der Hauptprüfung; sie wird nicht über einen anderen
  Zuschnitt genähert (das ist nur Nebenrechnung R7).
- **Maß**: *Y*(*d*, *p*) = 1, wenn *d* mindestens einen Treffer des Wörterbuchs im Wahlbezirk *w*(*p*)
  hat, sonst 0.
- **Kovariaten**: (a) die **Basisrate** *b*(*w*, *t*, −*p*): der Anteil der Anfragen in Rat und
  Ausschüssen der Periode *t*, die *w* treffen, ohne die von *p* gestellten, geglättet als
  (1 + Treffer) / (2 + Anfragen); sie nimmt, wie oft ein Wahlbezirk ohnehin genannt wird (Altstadt
  gegen Stadtrand, Größe des Wörterbuchs je Wahlbezirk). (b) *k*(*d*) = log(1 + Zahl der Wahlbezirke,
  die *d* trifft): eine Anfrage, die die halbe Stadt aufzählt, trifft jeden Wahlbezirk.
  (c) Feste Effekte **Fraktion × Periode** (Fraktion von *p* am Datum von *d* aus den
  Mitgliedschaften, sonst die Partei des Wahlvorschlags): direkt gewinnen fast nur große Fraktionen,
  und Fraktionen fragen verschieden viel nach Orten.

### 8.3 Modell, Test, Schwelle, Entscheidung

- **Modell**: logistische Regression über alle Paare der geprüften Perioden zusammen,
  logit P(*Y* = 1) = α(Fraktion × Periode) + β · [*D* = direkt] + γ₁ · logit *b*(*w*, *t*, −*p*) +
  γ₂ · *k*(*d*), geschätzt nach Maximum-Likelihood (IRLS, numpy; pandas und statsmodels sind im Paket
  verboten). Standardfehler **geclustert nach Person** (Sandwich, Faktor G/(G−1) · (N−1)/(N−K)).
- **Test**: einseitig, H1: β > 0, z-Test, **α = 0,05**. Berichtet wird OR = exp(β) mit
  95-%-Intervall.
- **Vorab genannter Effekt**: **OR = 1,5**. Die Literatur nennt für den Mandatstyp auf kommunaler
  Ebene keine Größe; 1,5 ist dieselbe Größenordnung wie die kleinste Wirkung, die 24 sehen will, und
  heißt bei einer Basisrate von 10 % rund 14 % statt 10 %.
- **Entscheidung**:
  - **bestätigt**, wenn p < 0,05 (einseitig);
  - **widerlegt** (der vorab genannte Effekt ist ausgeschlossen), wenn p ≥ 0,05 und die obere Grenze des
    einseitigen 95-%-Intervalls für OR unter 1,5 liegt;
  - **nicht entscheidbar** sonst, und **immer**, wenn eine der drei Voraussetzungen fehlt: die
    Zuordnung Dokument → Person erreicht an 150 Dokumenten die Präzision 0,95 nicht (§ 4), der
    Mandatstyp ist für weniger als 90 % der Ratsmitglieder einer geprüften Periode bekannt, oder die
    Teststärke nach § 8.4 liegt unter 0,8. „Nicht entscheidbar" steht auf der Seite als solches, nicht
    als „kein Unterschied".

### 8.4 Teststärke-Regel

Simuliert mit der **beobachteten Struktur** (alle Paare mit *D*, Fraktion × Periode, *b* und *k*,
nach dem eingefrorenen Verfahren), aber mit **künstlichem** *Y*: *Y* ~ Bernoulli(expit(logit *b* +
*a* + β · *D* + *u*(*p*))), mit *a* = 0 (Listenmitglieder nennen ihren Wahlbezirk so oft wie die
Basisrate), β = log 1,5, *u*(*p*) ~ N(0; 0,5²) für die Eigenart einer Person, 1 000 Läufe, je Lauf das
Modell aus § 8.3. Teststärke = Anteil der Läufe mit p < 0,05 einseitig. **Entscheidend: ≥ 0,8 bei
OR 1,5.** Daneben, nicht entscheidend: OR 1,25 und 2,0, *a* = log 2, Streuung 1,0, und der Fehler
erster Art (β = 0). Stufe 1 rechnet sie mit der Struktur, die sie messen kann (Zuordnung vor der
Kodierung, Ortsbezüge im Zuschnitt 2025, eigener Wahlbezirk über die größte Flächenüberlappung
genähert); Stufe 2 rechnet sie vor der Prüfung neu mit dem eingefrorenen Verfahren, und nur diese
zweite Zahl entscheidet.

### 8.5 Nebenrechnungen und Nebenthese (berichtet, entscheiden nicht)

- **H2 (Wettbewerb, nach Zittel u. a. 2019)**: Unter den direkt Gewählten nennen die mit knappem
  Vorsprung (unter 5 Prozentpunkten vor der Zweiten im Wahlbezirk) ihren Wahlbezirk häufiger als die mit
  sicherem. Modell wie H1 nur über die Paare direkt Gewählter, Regressor [Vorsprung < 5 Punkte];
  einseitig, α = 0,05; ohne eigene Teststärke ≥ 0,8 heißt das Ergebnis „explorativ".
- **R1** nur Anfragen mit genau einer Unterzeichnerin; **R2** dazu Anträge (Rolle `antrag`, Funktion
  `initiative` nach 15); **R3** je Periode einzeln; **R4** feste Effekte je Wahlbezirk × Periode statt
  der Basisrate; **R5** mit dem Stimmenanteil der eigenen Partei im eigenen Wahlbezirk als Kovariate
  (Hochburg nach Harmening u. a. 2025; trennt Mandatstyp und Stärke der Partei, mit geringerer
  Teststärke); **R6** *Y* als Zahl der Treffer im eigenen Wahlbezirk, Poisson mit denselben festen
  Effekten und Clustern; **R7** Ortsbezüge im Zuschnitt 2025, eigener Wahlbezirk über die größte
  Flächenüberlappung (die Näherung der Stufe 1); **R8** dazu Anfragen in Bezirksvertretungen, die ein
  Ratsmitglied zeichnet.
- **Ausdrücklich explorativ** und auf der Seite so genannt: Unterschiede je Fraktion, je Gremium,
  Ortsbezüge auf Wahlbezirke, in denen jemand nicht kandidiert hat (Wohnort, Nachbarbezirk), und alles,
  was erst nach der Zuordnung auffällt.

### 8.6 Nachträge

*keine*

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | Warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 27.1 | Soll die Lücke der Hauptperiode geschlossen werden (die 2020 über die Reservelisten Gewählten und die Nachrücker, etwa aus der Bekanntmachung im Amtsblatt, deren Archiv bei der ULB gesperrt ist; oder eine ältere Fassung der OParl-Personenliste, falls Konrad eine hat)? | Ohne sie bleibt der Mandatstyp der Hauptperiode bei 0,660 (Kriterium 0,9), und 38 % der Anfragen in Rat und Ausschüssen bleiben ohne Ratsmitglied | nein; die Hauptperiode wird mit Lücke gebaut, die Seite nennt sie |
| 27.2 | Die Periode 2014–2020: kein Ergebnis mit Namen online, keine Flächen der Wahlbezirke 2014 gefunden (2009 liegen auf dem Portal), OParl kennt höchstens 35 Ratsmitglieder | Ohne Quelle keine Messung | nicht gemessen, nicht gebaut |
| 27.3 | Dürfen die Wahlergebnisse ohne Datenlizenz (votemanager der Stadt) als abgeleitetes Paket ohne Namen ins Repo (Wahlbezirk, Partei, Stimmen, gewonnen, OParl-Kennung)? | Pages baut aus Paketen; ohne Paket fehlt der Mandatstyp auf Pages | ja für Stimmen je Wahlbezirk und Partei (dieselben Zahlen stehen unter dl-de/zero im Open-Data-Portal), Kennungen erst nach 27.4 |
| 27.4 | Dürfen OParl-Kennungen von Personen je Dokument ins Repo und auf die Seite? Die Kennung ist kein Name, aber die öffentliche OParl-API löst sie in einen Namen auf | Die Regel „nur IDs" erlaubt es; die Absicht von Plan § 1 (nur Rollen) eher nicht. Schon `validierung/27-personen/labels-kennungen.csv` trägt sie | Kennungen nur in lokalen Dateien und in `labels-kennungen.csv`; auf der Seite nur Zählungen |
| 27.5 | Soll H1 in einer neuen Runde mit einem gültigen Test vorab festgelegt werden (Permutation des Mandatstyps innerhalb Fraktion × Periode, oder gepoolt mit den Städten von Harmening u. a.)? | Das vorab festgelegte Modell hält sein Niveau nicht (0,385); ein gültiger Test hätte bei dieser Struktur noch weniger Teststärke | nein; H1 bleibt „nicht entscheidbar" |
| 27.6 | Ratsmitglied einer Periode über die Teilnahme an Ratssitzungen (§ 3.2) | Ohne die Regel zählten zehn Mitglieder des alten Rats in der laufenden Periode mit | so |
| 27.7 | Sachkundige Bürgerinnen und Einwohner zählen nicht als Mandatsträger (nicht gewählt), auch wenn sie unterschreiben | Recall in Ausschüssen; Plan § 1 nennt „Mandatsträger" | so; die Kodierung zeigt, wie oft sie unterschreiben (Recall) |
| 27.8 | Fraktion am Datum aus OParl, sonst die Partei der Kandidatur (Volt zur SPD, Klimaliste zur PARTEI) | feste Effekte in § 8.3 | so |
| 27.9 | `labels.csv` dieses Vorhabens trägt Nachnamen und ist gitignored; der Supervisor committet nach `merge` nur `README.md`, `guete.json` und, nach `--labels`, `labels-kennungen.csv` | Personendaten bleiben lokal | so |
| 27.10 | Der Worktree teilt `cache_root` mit dem Hauptklon (`settings.local.toml`): `bootstrap` hat am 2026-11-24 `texts.parquet` der Hauptperiode und der laufenden Periode neu geschrieben (bytegleich mit den Snapshots, nur die Stamps sind neu) | Seiteneffekt außerhalb des Worktrees | harmlos; gemeldet |

## 10. Änderungen durch die Synergie (füllt der Supervisor)
