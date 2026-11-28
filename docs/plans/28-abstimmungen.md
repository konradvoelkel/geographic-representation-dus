# Vorhaben 28: Abstimmungen und Kooperation

**Stand 2026-11-28: Ebene A mit Stufe 2 und 3 auf `main` (`v0.45.0`, Punkt 98), nach § 10; Ebene B verworfen (§ 5.1).**
Ebene A braucht kein Netz; Ebene B nur mit Frage 40. Mönchengladbach ist seit dem Netzlauf vom
2026-11-23/24 abgerufen (anders als in Frage 9.9 notiert), seine Niederschriften sind nicht gemessen.
**§ 10 vor dem Bau durch den Supervisor.**

Stufe 1 (Messen) vom 2026-11-24 auf dem Branch `feat/28-abstimmungen` (gemerged, entfernt). Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „28 Abstimmungen und
Kooperation". Messskript: [28-abstimmungen-messung.py](28-abstimmungen-messung.py). Codebuch und
Stichprobe: `validierung/28-abstimmungen/`.

Klassen, Kriterium, Rückfallregel und drei Hypothesen (§ 8) sind im Commit `97ebb52` (2026-11-24
00:41) festgelegt, **bevor** ein Wert von `result` gezählt oder eine Niederschrift geladen war; sie
sind danach nicht geändert. Das Verfahren für die Niederschriften ist danach entstanden und vor der
Kodierung eingefroren (§ 4: Ausgabe mit SHA-256).

**Urteil nach der Kodierung (Abschluss der Stufe 1, 2026-11-24), nach der vorab festgelegten Regel
(§ 8.2, Commit `97ebb52`), ohne Anpassung an die Labels:**

- **Ebene A (Ergebnis und Mehrheitsform aus OParl `result`): bauen.** Präzision **0,982** (Wilson
  0,928–0,995, roh 90/92), Abdeckung **86,4 %** der Beschlüsse der Hauptperiode (10 856 von 12 570).
  Braucht kein Netz.
- **Ebene B (Positionen aller Parteien aus den Niederschriften): verwerfen in dieser Form.** Präzision
  **0,765** (Wilson 0,671–0,838, roh 88/118) unter dem Kriterium 0,9, obwohl die Abdeckung reichte
  (82,3 % in den Niederschriften, hochgerechnet 70,1 %). Die Fehler liegen fast nur in den Positionen
  (26 von 30): übersehene Enthaltungen, geteilte Fraktionen, einzeln genannte Mitglieder (§ 4.1). Eine
  Umbau-Runde (Meta-Plan § 8, höchstens eine) bräuchte Codebuch Fassung 2 und eine frische Stichprobe;
  das entscheidet der Supervisor.
- **Hypothesen**: ungerechnet. Nach § 8.6 sind H28.1 und H28.3 ohne Ebene B `nicht entscheidbar`; H28.2
  braucht nur Ebene A und kann in Stufe 2 gerechnet werden.
- **Geprüft von KI-Kodierern**: zwei Kodierer und ein Schlichter, alle **dasselbe Modell**
  (`claude-opus-5-5`, Frage 19), kein menschlicher Goldstandard; α je Frage 0,885 bis 1,000.

Die drei wichtigsten Zahlen der Messung:

1. **`result` nennt die Mehrheitsform bei 86,4 % der Beschlüsse** der Hauptperiode (Rat 93,3 %,
   Ausschüsse 82,7 %, Bezirksvertretungen 86,5 %), und sie stimmt mit der Niederschrift überein
   (0,982). `resolutionText` ist bei keinem der 44 231 Tagesordnungspunkte gefüllt. Wer wie gestimmt
   hat, steht nur in den Niederschriften.
2. **Die Niederschriften nennen die Stimmen je Fraktion**, das Verfahren liest sie bei 82,3 % der
   Beschlüsse vollständig (778 von 945), aber nur zu 0,765 richtig. Die Mehrheitsform aus der
   Niederschrift (A2) ist dagegen genau (0,979).
3. **Die WZB-Schwelle wäre prüfbar**: 76 Anträge der AfD mit einem Ratsbeschluss (39 in 2020–2025, 37
   ab 2025), alle 13 der Stichprobe mit vollständigen Positionen; mit verworfener Ebene B bleibt H28.3
   aber nicht entscheidbar.

Netzstichprobe: 50 Niederschriften, 60 147 372 Bytes, 75 s. *Vorläufiges Urteil vor der Kodierung
(Stand `bf207d1`): „bauen, in zwei Ebenen, wenn die Kodierung die Präzision bestätigt"; für Ebene B
hat sie es nicht.*

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

**Frage.** Wie oft entscheiden die Gremien einstimmig, mit welchen Mehrheiten, und wer stimmt Anträgen
anderer zu? Daraus zwei Prüfungen: Konkordanz gegen Konkurrenz im Sinne Holtkamps, und der Umgang der
übrigen Fraktionen mit Anträgen der AfD nach der Schwelle der WZB-Studien.

**Literatur.** Holtkamp (2008, *Kommunale Konkordanz- und Konkurrenzdemokratie*, VS Verlag) unterscheidet
Räte mit Sachentscheidungen und wechselnden, breiten Mehrheiten von Räten mit fester Mehrheit,
Fraktionsdisziplin und einer Opposition, deren Initiativen scheitern; die großen Städte Nordrhein-Westfalens
gelten als Konkurrenzdemokratien. Vorhaben 15 hat das beim **Antragstellen** gezeigt (gemeinsame Anträge
über die Lagergrenze in Rat und Ausschüssen 3,2 % in der Hauptperiode, [15-funktion.md](15-funktion.md),
§ 3.11) und das **Entscheiden** an dieses Vorhaben übergeben (§ 3.12 dort). Die WZB-Studie (Discussion
Paper SP V 2025-501, März 2025) hat bundesweit 4 968 Anträge der AfD in Kreistagen und Räten kreisfreier
Städte 2019 bis 2024 ausgewertet; 934 (18,8 %) fanden Zustimmung, wenn man als Zustimmung zählt, dass
mindestens ein Zehntel der übrigen Mitglieder dafür stimmte. Eine frühere Studie desselben Hauses für
Ostdeutschland kam auf rund 20 %; für kreisfreie Städte allein nennt die Pressemitteilung rund 16 %
(nicht am Papier geprüft).

**Ratsarbeit.** Für Fraktionsgeschäftsstellen aller Parteien: Wer hat unseren Anträgen zugestimmt, wer
hat dagegen gestimmt, wie stimmen die anderen zu ihren eigenen? Für die Seite: ein Abschnitt auf
`akteure.html`, gleich für alle Fraktionen, mit den vorab festgelegten Prüfungen und ihrer Validierung.

**Zulieferer.** F6 (Sitzungen, Tagesordnung, Beratungen), 15 (Ratsmehrheit, Urheber der Anträge über
Option 04), 25 (Sitze), 26 (Ergebnisklassen, Erfolg je Fraktion), 27 (Personen → Partei, Besetzung der
Ausschüsse und Bezirksvertretungen).

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

**F6, Konrads Netzlauf vom 2026-11-23** (Stamps 22:40 bis 22:57 UTC), kopiert aus der Datenwurzel des
Hauptklons nach `data_root/<profil>/raw/` des Worktrees, gelesen mit `georep.council.council_files` und
den Modellen aus `georep.oparl`:

| Datei | Hauptperiode (`duesseldorf`) | 2014–2020 | ab 2025 |
|---|---|---|---|
| `meetings.jsonl` | 1 672 Sitzungen, 6,3 MB | 3 172, 10,1 MB | 390, 1,3 MB |
| `agenda_items.jsonl` | 44 231 Punkte, 27,2 MB | 81 139, 46,9 MB | 8 719, 5,5 MB |
| `consultations.jsonl` | 97 112 Beratungen, 56,3 MB (je Body, für alle drei) | lief noch | wie Hauptperiode |
| `persons.jsonl`, `memberships.jsonl` | 632 Personen, 4 615 Mitgliedschaften (nicht gelesen) | – | – |

Mönchengladbach hatte zum Messzeitpunkt noch keine Sitzungen; es ist nicht gemessen.

Gelesene Felder: `OparlAgendaItem.result`, `.consultation`, `.number`, `.name`, `.meeting`;
`OparlMeeting.start`, `.organization` (Gremium über `[bodies.organizations]`), `.auxiliaryFile`
(`name`, `downloadUrl`); `OparlConsultation.paper`. **`resolutionText` und `resolutionFile` sind bei 0
von 44 231 Punkten gefüllt** (wie das Runbook, § 2, an einer Seite sah). Aus dem Lauf der Kette:
`interim/papers.parquet` (`id`, `reference`, `paper_type`), `processed/dokumente_urheber.parquet`
(`urheber_art`, `parteien`, Option 04); für ab 2025 der Lauf des Profils `duesseldorf-2025` im Worktree.

**Niederschriften.** 50 Anlagen „Niederschrift Ö" (und Varianten wie „Niederschrift Rat … - öffentlich")
der Hauptperiode, geladen am 2026-11-24 (§ 3.3), lokal unter
`/media/konrad/xtraspace/georep/messdaten/28-abstimmungen/` mit `niederschriften/liste.csv` (Sitzung,
Datum, Art, Gremium, Datei, Name, URL, Abrufzeit, Bytes, SHA-256) und README. Text mit pypdf 7.1.0 wie F1
(`pypdf-7.1.0+roh`), `niederschriften_text.parquet`. Öffentliche Dokumente des Ratsinformationssystems
ohne Lizenzangabe; sie enthalten Namen von Mandatsträgern, Verwaltung und Gästen und bleiben darum
lokal. Ins Repo kommen nur IDs (Tagesordnungspunkte) und Zählungen.

**Sitze.** [25-quellen.md](25-quellen.md), § 1 (IT.NRW, Wikipedia), Fraktionsbildung wie dort; die
Tabelle steht in § 8.5.

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

Alle Zahlen vom 2026-11-24, gerechnet mit `uv run python docs/plans/28-abstimmungen-messung.py messen`
(24 s, 1 GB). Grundgesamtheit wie in § 8.2: Tagesordnungspunkte mit Beratung in Sitzungen der Periode,
die vor dem 2026-11-23 stattfanden.

### 3.1 Was `result` hergibt

Der Wortschatz an den 25 431 Punkten mit Beratung der Hauptperiode, mit der vorab festgelegten Wortregel
(§ 8.1); keine Zeile fällt in eine falsche Klasse, nur „zurückgewiesen" (5) und leer (1 874) sind
`sonstiges`:

| Anzahl | `result` | Ergebnis | Form |
|---|---|---|---|
| 6 385 | einstimmig beschlossen | angenommen | einstimmig |
| 5 914 | zur Kenntnis genommen | kenntnis | – |
| 1 874 | (leer) | sonstiges | – |
| 1 662 | vertagt | vertagt | – |
| 1 558 | mehrheitlich beschlossen | angenommen | mehrheitlich |
| 1 446 | Empfehlung einstimmig beschlossen | angenommen | einstimmig |
| 1 411 | beantwortet | kenntnis | – |
| 1 330 | schriftlich beantwortet | kenntnis | – |
| 1 053 | mehrheitlich abgelehnt | abgelehnt | mehrheitlich |
| 1 004 | abweichend beschlossen | angenommen (geändert) | ohne_angabe |
| 521 | zurückgezogen | zurueckgezogen | – |
| 457 | passieren lassen | angenommen | ohne_angabe |
| 337 | Empfehlung mehrheitlich beschlossen | angenommen | mehrheitlich |
| 146 | Empfehlung abweichend beschlossen | angenommen (geändert) | ohne_angabe |
| 105 | beschlossen | angenommen | ohne_angabe |
| 74 | verwiesen | verwiesen | – |
| 70 | zurückgestellt | vertagt | – |
| 38 | einstimmig abgelehnt | abgelehnt | einstimmig |
| 30 | Empfehlung mehrheitlich abgelehnt | abgelehnt | mehrheitlich |
| 9 | Empfehlung einstimmig abgelehnt | abgelehnt | einstimmig |
| 5 | zurückgewiesen | sonstiges | – |
| 2 | abgelehnt aufgrund Stimmengleichheit | abgelehnt | ohne_angabe |

Zwei Befunde: Eine geänderte Annahme („abweichend beschlossen", 1 150) trägt nie eine Form, und
„abgelehnt aufgrund Stimmengleichheit" ist nach der Definition `mehrheitlich`, die Wortregel gibt
`ohne_angabe` (2 Fälle, bleibt so, weil § 8 festliegt; Stufe 2 kann es als Ergänzung datiert nachtragen).

### 3.2 Ebene A je Periode und Gremiumsart

| Periode | Art | Beschlüsse | Form aus `result` (A1) | davon einstimmig | Sitzung mit Niederschrift |
|---|---|---|---|---|---|
| 2014–2020 | alle | 12 546 | 92,1 % | 76,5 % | 22,7 % |
| | Rat | 1 455 | 98,4 % | 61,6 % | 25,6 % |
| **2020–2025** | **alle** | **12 570** | **86,4 %** | **72,6 %** | **86,5 %** |
| | Rat | 1 633 | 93,3 % | 41,0 % | 88,4 % |
| | Ausschüsse | 3 975 | 82,7 % | 74,3 % | 90,0 % |
| | Bezirksvertretungen | 6 483 | 86,5 % | 81,0 % | 87,9 % |
| | Beiräte | 286 | 90,2 % | 83,3 % | 35,3 % |
| ab 2025 | alle | 2 848 | 89,4 % | 63,3 % | 59,8 % |
| | Rat | 396 | 98,2 % | 37,8 % | 79,5 % |

Die Spalte „einstimmig" ist beschreibend (explorativ, § 8.6). In 2014–2020 hat OParl nur an 294 von
1 500 Sitzungen überhaupt Anlagen; die Niederschriften dieser Periode sind über die Schnittstelle meist
nicht zu haben. Ab 2025 fehlen die jüngsten Niederschriften noch (Runbook § 7).

### 3.3 Netzstichprobe der Niederschriften

**Ziehung** (`sitzungen_der_stichprobe`): vergangene Sitzungen der Hauptperiode mit Niederschrift,
geschichtet nach Gremiumsart mit Rat 12, Ausschüsse 22, Bezirksvertretungen 16 (der Rat mehr als sein
Anteil, weil H28.1 und H28.3 im Rat gelten; Beiräte und Gremien ohne Zuordnung nicht), je Art reihum
über die Gremien, Rang SHA-256 aus Seed 20261124 und ID wie F4. Ergebnis: 12 Ratssitzungen, 17
Ausschüsse (22 Sitzungen), alle zehn Bezirksvertretungen (16 Sitzungen), 2020-09-15 bis 2025-07-10.

**Abruf** am 2026-11-24 00:42 bis 00:44 (UTC 23:42:52 bis 23:44:06) über `georep.http.make_session`
ohne Cache, eigener User-Agent ohne persönliche Angaben, 1,2 s Pause je Datei: **50 Dateien,
60 147 372 Bytes, 75 s**. Mittel je Art: Rat 1,02 MB, Ausschuss 0,64 MB, Bezirksvertretung 2,12 MB
(manche mit eingescannten Anlagen). Text mit pypdf 7.1.0 rund 4 min auf einem Kern.

**Vier Formen und Scans.** Wie eine Niederschrift die Abstimmung nennt, hängt am Gremium (je Dokument
die überwiegende Form, `stile`):

| Form | Niederschriften | Beispiel (Namen ersetzt) |
|---|---|---|
| Wortprotokoll mit Fragen | 12 (alle Ratssitzungen) | „Gegenstimmen? – AfD, Tierschutz/Freie Wähler und Die Linke. Enthaltungen? – Dann ist das im Übrigen mit Mehrheit so beschlossen." / „Wer ist für diesen Antrag? – Das ist die AfD. … Wer ist dagegen? – Das ist der gesamte Rest des Rates." |
| Stimmenzahlen mit Fraktionen | 16 (BV 11, Ausschuss 5) | „Ja: 11 (5 Bü 90/Grüne, 3 SPD, 2 FDP, Frau NN) Nein: 6 (6 CDU) Enthaltung: 1 (Herr NN)"; „6 JA (SPD, DIE LINKE, Die PARTEI/Klima) 15 NEIN 0 ENTHALTUNG" |
| Block nur mit der Form | 8 (Ausschuss 4, BV 4) | „Abstimmungsergebnis: einstimmig" |
| Fließtext | 10 (Ausschuss 9, BV 1) | „… empfiehlt dem Rat mehrheitlich bei einer Gegenstimme von Ratsfrau NN (Die Linke) …" |
| ohne Textebene (Scan) | 4 (Ausschüsse, 2020/21) | – |

### 3.4 Das Verfahren (eingefroren vor der Kodierung)

1. **Seitenköpfe** heraus (`ohne_kopf`): sie stehen mitten in den Sätzen.
2. **Schnitt je Tagesordnungspunkt** (`schnitt`): eine Zeile mit nur der Nummer des Punktes, der binnen
   acht Zeilen die Drucksachennummer oder der Anfang des Namens folgt; Rückfall: die Drucksachennummer
   allein auf einer Zeile (der Rat nummeriert in der Niederschrift manchmal anders als OParl). **Jeder
   Aufruf** zählt: der Rat ruft Punkte im Schnelldurchgang auf und zur Debatte noch einmal; ohne das
   lasen wir 70,9 % statt 86,0 % der Ratsabstimmungen.
3. **Die maßgebliche Abstimmung** (`stimmen`): der letzte Schluss („Damit ist der Antrag … abgelehnt",
   „Dann … beschlossen"); bei einem Änderungsantrag der letzte Schluss, vor dem der Änderungsantrag genannt
   ist; ohne Schluss (Blockform) der letzte Anker. Im Fenster davor werden Fächer gelesen (ja: „Wer ist
   für", „Ja:", „n JA"; nein: „Gegenstimmen", „Wer ist dagegen", „gegen die Stimmen der"; Enthaltung) und
   in jedem Fach die Parteien nach festen Mustern; Personen über ihre Partei in der Anwesenheitsliste oder
   in „Ratsherr NN (Partei)" derselben Niederschrift (die Namen verlassen das Skript nicht).
4. **Form**: das letzte „einstimmig/mehrheitlich/mit Mehrheit" im Fenster, sonst aus den Fächern; nach
   der Definition aus § 8.1 ist „mit Mehrheit" ohne genannte Gegenstimme einstimmig.
5. **Ergänzungsregel** (§ 8.1): ein Fach, das „den Rest" nennt, oder ein Fach mit Zahl ohne Namen bekommt
   die nicht genannten Parteien; sonst die Seite des Ergebnisses, wenn die Formel nur Abweichende nennt.
   Fraktionen aus mehreren Parteien geben allen dieselbe Position (in Rat und Ausschüssen ab
   2020-11-01). **Parteien des Gremiums**: im Rat die Sitzverteilung, sonst die Parteien, die die
   Niederschrift in Anwesenheitsliste und Abstimmungen nennt.
6. Ergebnis aus `result` (Rückfallregel 1), Form aus der Niederschrift, sonst aus `result` (Regel 2).

### 3.5 Ergebnis in der Stichprobe

1 774 Punkte mit Beratung in den 50 Niederschriften, davon 945 Beschlüsse (Ergebnis `angenommen` oder
`abgelehnt` nach `result`), 937 in Niederschriften mit Text.

| Art | Beschlüsse | Abschnitt gefunden | Abstimmung gelesen | Form (A2, mit Rückfall) | **B vollständig** | Form `result` ≠ Niederschrift | mit Personen ohne Partei |
|---|---|---|---|---|---|---|---|
| Rat | 515 | 99,6 % | 86,0 % | 98,3 % | **81,9 %** | 17 von 428 | 8 |
| Ausschüsse | 148 | 93,6 % (der Rest Scans) | 76,4 % | 87,8 % | **73,0 %** | 2 von 106 | 10 |
| Bezirksvertretungen | 282 | 100 % | 96,1 % | 98,9 % | **87,9 %** | 6 von 228 | 39 |
| **alle** | **945** | 98,8 % | 87,5 % | 96,8 % | **82,3 %** | 25 von 762 (3,3 %) | 57 |

„B vollständig" heißt: jede Partei des Gremiums hat eine Position (ja, nein, Enthaltung, geteilt). Ob
die Positionen stimmen, misst erst die Kodierung (§ 4). Die 25 Widersprüche zwischen `result` und
Niederschrift sind eine erste, schwache Probe der Ebene A: in 96,7 % stimmen beide überein.

### 3.6 Abdeckung B für die Hauptperiode

B in den Niederschriften je Art × Anteil der Beschlüsse, deren Sitzung eine Niederschrift hat (§ 3.2) ×
Beschlüsse je Art; Beiräte und Gremien ohne Zuordnung (479 Beschlüsse) zählen mit 0:

| Art | B | mit Niederschrift | Beschlüsse |
|---|---|---|---|
| Rat | 0,819 | 0,884 | 1 633 |
| Ausschüsse | 0,730 | 0,900 | 3 975 |
| Bezirksvertretungen | 0,879 | 0,879 | 6 483 |
| **gesamt** | | | **8 807 / 12 570 = 0,701** |

Die Zahl setzt den vollen Abruf voraus (§ 5). Sie überschätzt, wenn die Stichprobe der Ausschüsse
günstig lag (17 Ausschüsse mit je ein bis zwei Sitzungen), und unterschätzt, weil Scans und
Beiräte mit 0 zählen.

### 3.7 Prüfbarkeit der Hypothesen (nur n, nicht ihr Ausgang)

| Hypothese | Einheiten | davon prüfbar |
|---|---|---|
| H28.1 geschlossene Mehrheit | 882 strittige Ratsbeschlüsse (Form `mehrheitlich` aus `result`, 2021-01-01 bis 2025-09-14), 711 mit Niederschrift | in der Stichprobe CDU und GRÜNE beide bekannt bei 208 von 276 (75,4 %); erwartet rund 530 ≥ 30 |
| H28.2 Opposition selten angenommen | 389 Anträge allein von Oppositionsfraktionen ohne AfD mit letztem entschiedenen Ratsbeschluss im Zeitraum | alle über Ebene A; ≥ 30 |
| H28.3 WZB-Schwelle | 76 Anträge der AfD mit Ratsbeschluss: 39 (2020–2025, alle mit Niederschrift) und 37 (ab 2025, 19 mit Niederschrift bis heute) | in der Stichprobe 13 von 13 mit vollständigen Positionen; ≥ 20 |

Die WZB-Schwelle ist damit prüfbar: die Ratsniederschriften nennen bei Anträgen der AfD die Parteien
je Fach („Wer ist für diesen Antrag? – Das ist die AfD. … Wer ist dagegen? – Das ist der gesamte Rest
des Rates"), und die Sitzverteilung macht daraus Stimmen. Der Ausgang ist nicht gerechnet (§ 8).

### 3.8 Laufzeiten

`messen` 24 s; Abruf 75 s für 50 Dateien; Text 4 min für 50 Dateien auf einem Kern; Aufträge unter einer Minute.

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

**Codebuch** `validierung/28-abstimmungen/codebuch.toml`, Version 2026-11-24.1, Format F4. Einheit: ein
Tagesordnungspunkt (Schlüssel: Nummer des OParl-AgendaItem). Fünf Fragen: `abschnitt` (behandelt der
Ausschnitt den Punkt; binär), `ergebnis` (die acht Klassen aus § 8.1 und `nicht_erkennbar`),
`form` (`einstimmig`, `mehrheitlich`, `ohne_angabe`), `stimmen` (JSON-Objekt Partei → Position, nur
genannte Parteien), `uebrige` (`mit_mehrheit`, `unbekannt`). Die Kodierer sehen Titel (Nummer, Name,
Gremium, Datum) und den Abschnitt der Niederschrift, bei über 9 000 Zeichen die ersten 1 500 und die
letzten 7 500, davor gekürzt die Anwesenheitsliste; nicht `result`, nicht die Schicht, nicht was das
Verfahren liest.

**Stichprobe** (`georep validate sample 28-abstimmungen`): Grundgesamtheit die 926 Beschlüsse mit
gefundenem Abschnitt (`data_root/duesseldorf/validierung-28/population.parquet`, SHA-256
`2030e3d7a8766ec62128e8ae0785ba6d2e503a47c7e355655266b1666a563641`), geschichtet nach der Form aus
`result`, gleiche Aufteilung, Seed 20261124: einstimmig 50 von 486, mehrheitlich 50 von 361,
ohne_angabe 50 von 79. Nicht selbstgewichtend; `stichprobe.csv` trägt `schicht_n`.

**Aufträge** (`28-abstimmungen-messung.py auftraege`): die Niederschriften stehen nicht im Korpus, darum
baut das Skript die Aufträge mit den Bausteinen von F4 (`build_task`, `write_assignment`), je Kodierer in
eigener Folge, unter `/media/konrad/xtraspace/georep/messdaten/kodierung/28-abstimmungen/{A,B}/`
(`auftrag.jsonl`, `antworten.jsonl`, `codebuch.md`). Ausschnitt: Median 2 818 Zeichen, höchstens 11 404;
nach dem Handbuch (§ 3, Schritt 3) teilt der Supervisor die Kodierer in Läufe (etwa drei zu 50 Zeilen).
`georep validate merge` und die Schlichtung laufen wie gewohnt; **`georep validate tasks` nicht aufrufen**: es läse den Text der Drucksache statt der Niederschrift und schriebe die Aufträge damit neu.

**Eingefroren**: die Ausgabe des Verfahrens für alle 1 774 Punkte,
`messdaten/28-abstimmungen/vorhersage.parquet`, SHA-256
`e4fc0a16c8ef3753dc388918684455e5aef997b0c418f838603b03f3456209e9`, erzeugt vor dem Start der
Kodierer; das Skript erzeugt sie bitgleich neu (geprüft). In der Stichprobe beansprucht das Verfahren
A1 bei 100, A2 bei 122 und B bei 118 Einheiten.

**Maße** (`28-abstimmungen-messung.py guete`, nach `merge`): Präzision A1, A2 und B wie in § 8.2, je
Teilmenge als gewichteter Anteil Σ w·richtig / Σ w mit w = N_h/n_h und Wilson-Intervall bei Kishs
n_eff (wie F4, `docs/validierung.md` § 5). B ist richtig, wenn Ergebnis und Form stimmen und der Vektor
der Positionen aller Parteien des Gremiums gleich dem ist, was aus `stimmen` und `uebrige` nach der
Ergänzungsregel folgt. Ein Ausschnitt, der nach dem Label nicht zum Punkt gehört, ist für A2 und B ein
Fehler, für A1 ein Ausfall. Übereinstimmung der Kodierer je Frage aus `georep validate merge`
(Krippendorffs α, Stufe 3 verlangt ≥ 0,8). Eine Probe mit Labels aus der eigenen Ausgabe ergibt für A2
und B je 1,000 und für A1 0,966, wie erwartet: die Rechnung läuft. Bei einer Präzision um 0,95 und
n_eff rund 100 ist das Intervall etwa ±0,05 breit.

### 4.1 Ergebnis der Kodierung (2026-11-24)

Zwei Kodier-Agenten (je drei Läufe zu 50 Einheiten), ein Schlicht-Agent für 7 Einheiten mit 13
strittigen Fragen (6-mal Kodierung 1, 7-mal Kodierung 2), zusammengeführt mit `georep validate merge`
(`validierung/28-abstimmungen/labels.csv`, `README.md`, `guete.json`). **Alle drei sind dasselbe Modell
(`claude-opus-5-5`)**; α ist darum eine obere Schätzung der Schärfe des Codebuchs, nicht der
Richtigkeit (Frage 19, `docs/validierung.md` § 1).

| Frage | gestellt | gleich | Krippendorffs α |
|---|---|---|---|
| `abschnitt` | 150 | 150 | 1,000 |
| `ergebnis` | 132 | 129 | 0,908 |
| `form` | 131 | 128 von 129 | 0,985 |
| `stimmen` | 124 | 119 von 123 | 0,961 |
| `uebrige` | 124 | 122 von 123 | 0,885 |

Alle Fragen erreichen α ≥ 0,8. `stimmen` steht in `labels.csv` bei allen 124 Einheiten als JSON-Objekt;
`guete` liest einen JSON-String ebenso (Hinweis des Schlichters).

**Präzision** (`28-abstimmungen-messung.py guete`, Ausgabe des Verfahrens vom Stand vor der Kodierung,
SHA-256 oben; gewichtet mit N_h/n_h, Wilson bei Kishs n_eff):

| Ebene | Präzision | Wilson 95 % | n_eff | roh | Kriterium 0,9 |
|---|---|---|---|---|---|
| A1, Ergebnis und Form aus `result` | **0,982** | 0,928–0,995 | 90,1 | 90/92 | erfüllt |
| A2, Form aus der Niederschrift mit Rückfall | 0,979 | 0,928–0,994 | 99,5 | 118/122 | erfüllt |
| B, Positionen aller Parteien | **0,765** | 0,671–0,838 | 96,3 | 88/118 | **verfehlt** |

**Wo es scheitert** (Fehleranalyse, ändert nichts am Urteil):

- 18 der 150 Ausschnitte gehören nach den Kodierern nicht zum Punkt (Rat 13, Ausschüsse 4, BV 1;
  meist Punkte, die der Rat gemeinsam mit anderen behandelt oder nur aufruft). Keiner davon ist eine
  Einheit, für die das Verfahren B beansprucht; für A1 fallen 8 als Ausfall heraus.
- A1: 2 Fehler, beide im Rat: `result` sagt „mehrheitlich beschlossen", die Niederschrift nennt keine
  Gegenstimme (nach der Definition einstimmig).
- B: 30 Fehler bei 118 Einheiten, 26 davon in den Positionen (Ergebnis 2, Form 2); je Art richtig: Rat
  38/51, Ausschüsse 12/17, Bezirksvertretungen 38/50. Häufigste Muster: eine Enthaltung, die das
  Verfahren der Mehrheit zuschlägt (LINKE 3, AFD 2), geteilte Fraktionen, die es als geschlossen liest
  (CDU 2, GRÜNE 2) oder umgekehrt (FDP, SPD, LINKE je 2), Parteien, deren Stimmen die Labels offen
  lassen (`uebrige` unbekannt, 4). Die Ergänzungsregel trägt also, aber das Lesen der Fächer, der
  Personen und der Zahlen je Partei nicht genau genug.


## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

### 5.1 Urteil nach der Kodierung (2026-11-24)

Nach der Regel aus § 8.2, unverändert angewendet:

| Ebene | Abdeckung (≥ 50 %) | Präzision (≥ 0,9) | Urteil |
|---|---|---|---|
| A (A1 aus `result`) | 86,4 % der Beschlüsse | 0,982 (0,928–0,995) | **bauen** |
| A2 (Form aus der Niederschrift, Rückfall `result`) | 96,8 % in den Niederschriften | 0,979 (0,928–0,994) | erfüllt; hebt die Abdeckung von A nur mit dem Abruf und ist für Stufe 2 nicht nötig |
| B (Positionen aller Parteien) | 70,1 % hochgerechnet | 0,765 (0,671–0,838) | **verwerfen in dieser Form** |

Unsicherheit: die obere Grenze von B (0,838) liegt unter 0,9; auch eine günstigere Gewichtung brächte
B nicht ans Kriterium. Für A liegt die untere Grenze (0,928) über 0,9.

**Folgen.** Stufe 2 baut nur Ebene A (Beitrag `votes` ohne Niederschriften, § 6, Reihenfolge erster
Schritt). H28.2 ist mit Ebene A prüfbar; H28.1 und H28.3 bleiben nach § 8.6 `nicht entscheidbar`, bis
eine Ebene B das Kriterium erfüllt. Die Seite (§ 7) zeigt Einstimmigkeit je Gremium und H28.2, nicht
die Positionen je Fraktion.

**Empfehlung zum vollen Abruf der Niederschriften: jetzt nicht.** Ebene A braucht ihn nicht. Er lohnt
sich erst, wenn der Supervisor eine Umbau-Runde für B freigibt; dann zuerst nur die Ratsniederschriften
(47 Dateien, rund 50 MB, ein bis zwei Minuten), weil H28.1 und H28.3 im Rat gelten und das Wortprotokoll
des Rates die gleichmäßigste Form hat, danach die Hauptperiode (966 Dateien, rund 1,2 GB, rund 24 min
Abruf und rund 74 min Text auf einem Kern) und alle Düsseldorfer Perioden (1 359, rund 1,7 GB, rund
34 min). Eine Umbau-Runde misst an einer frischen Stichprobe mit Codebuch Fassung 2 (Regeln in § 9).

### 5.2 Vorläufiges Urteil vor der Kodierung (unverändert, Stand `bf207d1`)

**Vorläufig, vor der Kodierung**:

| Ebene | Abdeckung (Kriterium 50 %) | Präzision (Kriterium 0,9) | vorläufiges Urteil |
|---|---|---|---|
| A1, Form aus `result` | 86,4 % der Beschlüsse | offen (erste Probe: 96,7 % Übereinstimmung mit der Niederschrift, § 3.5) | **bauen**, wenn A1 ≥ 0,9 |
| A2, Form aus Niederschrift mit Rückfall | 96,8 % in den Niederschriften | offen | Teil von B |
| B, Positionen aller Parteien | 82,3 % in den Niederschriften, **70,1 % hochgerechnet** | offen | **bauen mit vollem Abruf**, wenn B ≥ 0,9; sonst umbauen |

Unsicherheit: die Abdeckung von B beruht auf 50 Niederschriften (Ausschüsse mit 22 Sitzungen am
dünnsten); selbst eine um zehn Punkte niedrigere Abdeckung in den Ausschüssen hielte B gesamt über 60 %.

**Empfehlung zum vollen Abruf der Niederschriften** (an Konrad, Runbook § 7, nur bei „bauen" für B):

| Periode | Niederschriften | Größe (Mittel je Art) | Abruf (1,5 s je Datei) | Text (pypdf, ein Kern) |
|---|---|---|---|---|
| 2020–2025 | 966 (Rat 39, Ausschüsse 481, BV 353, Beiräte 45, sonst 48) | rund 1,2 GB | rund 24 min | rund 74 min |
| ab 2025 | 167 | rund 0,2 GB | rund 4 min | rund 13 min |
| 2014–2020 | 226 (OParl hat nur für ein Fünftel der Sitzungen Anlagen) | rund 0,3 GB | rund 6 min | rund 17 min |
| **alle drei** | **1 359** | **rund 1,7 GB** | **rund 34 min** | **rund 1¾ h, parallel unter 15 min** |

Für H28.1 und H28.3 im Rat reichen 47 Ratsniederschriften (rund 50 MB, ein bis zwei Minuten). Die
Hypothesen H28.2 (Ebene A) und die Einstimmigkeit je Gremium brauchen keinen Abruf.

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

**Beitrag `votes`** (`src/georep/enrich/votes.py`, eine Zeile in `src/georep/enrich/__init__.py` hinter
26), drei Schritte, jeder hinter einem Schalter, der zunächst aus ist:

1. `minutes` (Netz, nur mit `--online` und `votes.minutes = true`): liest die Anlagen aus
   `raw/meetings.jsonl` (Name beginnt mit `votes.minutes_prefix`, „nicht" im Namen ausgeschlossen, Vorrang
   „Niederschrift Ö"), lädt sie wie `pdfs` nach `cache_root/<profil>/minutes/` mit Manifest (Datei, URL,
   Abrufzeit, Bytes, SHA-256), fortsetzbar, 1 s Pause.
2. `minutes_text` (offline): Rohtext mit demselben Extraktor wie F1 nach
   `cache_root/<profil>/minutes/texts.parquet` (`datei`, `sitzung`, `seiten`, `text`, `extractor`).
3. `votes` (offline): je Tagesordnungspunkt mit Beratung eine Zeile nach `processed/abstimmungen.parquet`.

**Schema `abstimmungen.parquet`** (Schema-Version aus `VOTES_SCHEMA_VERSION`): `top` (String,
AgendaItem-ID, Schlüssel), `sitzung`, `datum` (Date), `gremium`, `gremium_art`, `paper` (Korpus-ID oder
null), `ergebnis` (Enum aus § 8.1, aus `result`; mit 26 abgestimmt, Frage 9.2), `geaendert` (Bool),
`form` (Enum oder null), `form_quelle` (`niederschrift`, `result`), `positionen` (List[Struct{partei,
position}], sortiert), `vollstaendig` (Bool), `niederschrift` (Datei-ID oder null). Eine Zeile je `top`,
sortiert nach `top`; dazu für die Seite eine Ableitung je Antrag (letzter Ratsbeschluss) in `report/`.
Die Stelle der Abstimmung als Spanne nach F3 (`kind = "abstimmung"`) liegt nur lokal neben dem Text der
Niederschrift (`id` = Datei-ID): `value` wäre Ratstext mit Namen.

**Verträge**: eine Zeile je `top`; `positionen` nur mit Schlüsseln aus `votes.parties`; `vollstaendig`
⇒ jede Partei des Gremiums hat eine Position; `form = einstimmig` ⇒ keine Position `nein`;
`ergebnis ∉ {angenommen, abgelehnt}` ⇒ `form` null; Folge nach `top`.

**Settings** (Anhängeregel, Block `# --- Vorhaben 28` am Ende von `defaults.toml`, Modell vor
`class Settings`, Feld am Ende): `votes.enabled`, `votes.minutes`, `votes.minutes_prefix`, die Muster
der Fächer und Schlüsse (sprachlich, aber stadtneutral genug für `defaults.toml`; Mönchengladbach prüft
das), `[[votes.parties]]` (Muster → Parteischlüssel) und die Fraktionen aus mehreren Parteien mit
Zeitraum **im Stadtprofil**. Mehrheiten und Sitze kommen aus dem stadtweiten Block, den 15 anlegt
(Synergien § 1); fehlt er, fehlen H28.1 bis H28.3.

**Tests**: Beispiele je Form aus synthetischen Niederschriften ohne echte Namen (Wortprotokoll mit
„der gesamte Rest", Stimmenzahlen mit Fraktionen und `geteilt`, Block „einstimmig", Fließtext,
Änderungsantrag vor der Schlussabstimmung, Punkt zweimal aufgerufen, Seitenkopf mitten im Satz);
hypothesis: die Wortregel gibt jedem Text genau eine Klasse; die Ergänzungsregel überschreibt nie eine
genannte Partei; eine Fraktion aus mehreren Parteien gibt allen dieselbe Position; `vollstaendig` hängt
nicht an der Folge der Fächer. Netztest für `minutes` nur mit Marker `network`, sonst Fake-Session mit
einer aufgezeichneten, gekürzten Antwort.

**Paket**: `georep pack --votes` nach `snapshots/duesseldorf-abstimmungen/` mit `abstimmungen.parquet`
ohne Text (geschätzt 1 bis 2 MB für rund 25 000 Punkte), damit Pages ohne Netz baut. Die PDFs und Texte
der Niederschriften nicht ins Repo.

**Berührte Dateien**: `src/georep/enrich/votes.py` (neu), `src/georep/enrich/__init__.py`,
`src/georep/settings.py`, `src/georep/defaults.toml`, `src/georep/profiles/duesseldorf.toml`,
`src/georep/pack.py`, `tests/unit/test_votes.py`, `tests/property/test_votes.py`,
`docs/architecture.md`, `docs/decisions.md` (Nummer beim Merge), `docs/runbook-sitzungen.md` § 7.

**Reihenfolge**: zuerst nur Ebene A (`votes` ohne Niederschriften, sofort baubar), dann `minutes` und
Ebene B nach Konrads Abruf. **Nach der Kodierung (§ 5.1) baut Stufe 2 nur Ebene A**: Schritt `votes`
mit `ergebnis`, `geaendert`, `form`, `form_quelle = result`; `positionen` und `vollstaendig` und die
Schritte `minutes` und `minutes_text` entfallen, bis eine Umbau-Runde B bestätigt. Personen ohne Partei über die Mitgliedschaften von 27 statt der
Anwesenheitsliste, sobald 27 gebaut ist.

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

Ein Abschnitt „Abstimmungen" auf `akteure.html` (braucht den F2-Nachzug für Abschnitte aus fremden
Beiträgen, Synergien § 1). Inhalt, für alle Fraktionen gleich:

1. Einstimmig, mehrheitlich, geändert je Gremiumsart und Periode (Ebene A), mit dem Satz aus
   `guete.json`.
2. Die drei Prüfungen H28.1 bis H28.3 als Tabelle mit `hypothese`, `n`, `p`, `p_holm`, `ergebnis`,
   `festgelegt` (Commit `97ebb52`), „nicht entscheidbar" als solches.
3. Anträge der AfD im Rat: Zahl, Anteil mit Zustimmung nach der WZB-Schwelle, Vergleichswert der Studie.
4. Explorativ: die Matrix „Partei × Urheberpartei → Anteil ja" für Rat und Ausschüsse.

Größe: vier kleine Tabellen, rund 15 bis 25 KB. Tabellen im Register: `abstimmungen_gremien`,
`abstimmungen_hypothesen`, `abstimmungen_matrix` (CSV und Parquet). Keine Personennamen, keine
Ausschnitte aus Niederschriften.

**Nach der Kodierung (§ 5.1)**: ohne Ebene B entfallen Punkt 3 (Zustimmung nach der WZB-Schwelle)
und Punkt 4 (Matrix); Punkt 2 zeigt H28.2 mit Ergebnis und H28.1, H28.3 als „nicht entscheidbar".
Es bleiben Punkt 1 und 2, rund 10 KB.

## 8. Vorab festgelegte Hypothesen (nur Analysen: Hypothese, Maß, Test, Schwelle)

Festgelegt am 2026-11-24 gegen 00:45, bevor ein Abstimmungsergebnis ausgezählt war. Bekannt waren zu
diesem Zeitpunkt nur: die Füllgrade der F6-Felder aus [../runbook-sitzungen.md](../runbook-sitzungen.md),
§ 2 (darin der dort genannte Wortschatz von `result` als Beispiel, ohne Häufigkeiten), die Zahl der
Sitzungen mit einer Anlage „Niederschrift …" je Gremiumsart (Rat 47, Ausschüsse 577, Bezirksvertretungen
407 vergangene Sitzungen ab 2020-09-14; nicht nach Ergebnis getrennt), die Sitzverteilung aus
[25-quellen.md](25-quellen.md), § 1, und die Mitantragsteller aus [15-funktion.md](15-funktion.md),
§ 3.9 bis 3.12 (sie sagen nichts über Abstimmungen). Keine Niederschrift war geladen, kein Wert von
`result` gezählt.

Wie in [24-kontrolle.md](24-kontrolle.md) wird in Stufe 1 **keine Probe der Hypothesen gerechnet**, auch
keine vorläufige an der Stichprobe der Niederschriften: gemessen wird nur, ob und an wie vielen Fällen
sie prüfbar sind (Fallzahl, Anteil der bestimmbaren Fälle), nicht ihr Ausgang. Gerechnet werden sie in
Stufe 2, und nur, wenn das Kriterium für die Ebene, die sie brauchen, erfüllt ist (§ 8.2).

### 8.1 Einheit und Klassen

**Einheit** ist ein **Beschluss**: ein Tagesordnungspunkt (`OparlAgendaItem`) einer vergangenen Sitzung,
der eine Beratung (`consultation`) und damit eine Drucksache hat. Punkte ohne Beratung sind Verfahren
(Beschlussfähigkeit, Tagesordnung, Mitteilungen) und zählen nicht. Steht dieselbe Drucksache in einer
Sitzung zweimal auf der Tagesordnung, sind es zwei Einheiten.

**Ebene A, Ergebnis und Mehrheitsform.** Aus `result` (F6) und, wo geladen, aus der Niederschrift.
Das **Ergebnis** folgt aus `result`, kleingeschrieben, nach der ersten zutreffenden Regel in dieser Folge
(eine Regel über Wörter, keine Tabelle der Werte, damit ein neuer Wert nicht still herausfällt):

| Folge | `result` enthält | Ergebnis |
|---|---|---|
| 1 | „zurückgezogen" | `zurueckgezogen` |
| 2 | „vertagt", „zurückgestellt", „abgesetzt" | `vertagt` |
| 3 | „verwiesen" | `verwiesen` |
| 4 | „abgelehnt" | `abgelehnt` |
| 5 | „beschlossen", „zugestimmt", „angenommen", „passieren lassen" | `angenommen` |
| 6 | „kenntnis", „beantwortet" | `kenntnis` |
| 7 | „erledigt" | `erledigt` |
| 8 | sonst, auch leer | `sonstiges` |

Dazu ein Merker `geaendert`, wenn `result` „abweichend" oder „geändert" enthält (für Vorhaben 26).
**Entschieden** heißt ein Beschluss mit Ergebnis `angenommen` oder `abgelehnt`; nur bei ihnen gibt es eine
**Mehrheitsform**:

- `einstimmig`: keine Gegenstimme. Enthaltungen sind erlaubt („einstimmig bei Enthaltung der …"), sie
  stehen dann bei den Stimmen (Ebene B).
- `mehrheitlich`: mindestens eine Gegenstimme.
- `ohne_angabe`: entschieden, aber die Form ist nicht genannt („beschlossen").

Aus `result`: „einstimmig" → `einstimmig`, „mehrheitlich" → `mehrheitlich`, sonst `ohne_angabe`.

**Ebene B, Stimmen der Fraktionen.** Nur aus der Niederschrift. Je **Partei** eine Position zum
Gegenstand der Abstimmung (dem Antrag oder der Vorlage, nicht dem Ergebnis): `ja`, `nein`,
`enthaltung`, `geteilt` (Mitglieder derselben Partei stimmten verschieden). Eine Fraktion aus mehreren
Parteien gibt jeder ihrer Parteien dieselbe Position (SPD/Volt → `SPD`, `VOLT`; PARTEI-Klima-Fraktion →
`PARTEI`, `KLIMA`; Gruppe Tierschutz/Freie Wähler → `TIERSCHUTZ`, `FW`). Ein einzeln genanntes Mitglied mit
Partei gibt die Position seiner Partei, wenn der Text nichts über andere Mitglieder dieser Partei sagt.
Die Niederschrift nennt meist nur die Abweichenden („mehrheitlich beschlossen gegen die Stimmen der
AfD-Fraktion bei Enthaltung der Fraktion Die Linke"); die **Ergänzungsregel**: sagt die Formel, dass die
übrigen mit der Mehrheit stimmten (die Formen „gegen die Stimmen der …", „bei Enthaltung der …",
„einstimmig"), dann haben alle nicht genannten Parteien des Gremiums die Position der Mehrheit (`ja` bei
`angenommen`, `nein` bei `abgelehnt`). Nennt die Formel nur die Unterstützer („mit den Stimmen der CDU und
der Grünen"), bleiben die übrigen `unbekannt`. **Vollständig** heißt ein Beschluss, wenn jede Partei des
Gremiums eine Position hat; welche Parteien im Gremium sitzen, sagt die Sitzverteilung (Rat, § 8.5) oder,
wo sie fehlt, die Menge der Parteien, die die Niederschrift dieser Sitzung irgendwo nennt.

Nicht Teil der Einheit: Abstimmungen über Änderungsanträge vor der Schlussabstimmung. Gezählt wird die
**letzte Abstimmung** über den Gegenstand des Punktes. Der Oberbürgermeister und die Bezirksbürgermeister
haben keine Partei im Sinne der Ebene B (sie stimmen mit, werden aber nicht als Fraktion gezählt).

### 8.2 Das Kriterium, wie es gezählt wird

Kriterium des Briefings: **Präzision ≥ 0,9 an 150 und Abdeckung ≥ 50 % der Beschlüsse**. Es gilt je
Ebene getrennt; jede Ebene bekommt ihr eigenes Urteil.

- **Grundgesamtheit** („Beschlüsse"): die entschiedenen Beschlüsse (Ergebnis `angenommen` oder `abgelehnt`
  nach der Regel in § 8.1) in Sitzungen der Hauptperiode (Beginn 2020-09-13 bis 2025-09-14), die vor dem
  2026-11-23 stattfanden. Zum Vergleich berichtet, entscheidet nicht: alle Punkte mit Beratung.
- **Abdeckung A**: Anteil der Beschlüsse mit Mehrheitsform `einstimmig` oder `mehrheitlich` aus `result`
  (A1) beziehungsweise aus Niederschrift und `result` nach der Rückfallregel (A2).
- **Abdeckung B**: Anteil der Beschlüsse, die nach Ebene B **vollständig** sind. Gemessen an den
  Beschlüssen der Stichprobe der Niederschriften; für die ganze Hauptperiode hochgerechnet mit dem Anteil
  der Beschlüsse, deren Sitzung eine Niederschrift hat (B gesamt = B in den Niederschriften × dieser
  Anteil). Das Urteil über B nennt beide Zahlen; das Kriterium gilt für **B gesamt**, unter der Annahme,
  dass alle vorhandenen Niederschriften geladen werden.
- **Präzision** an 150 Tagesordnungspunkten aus den geladenen Niederschriften, kodiert nach F4 (zwei
  Kodier-Agenten, Schlichtung), die Labels aus dem Ausschnitt der Niederschrift zu diesem Punkt:
  - **A1** (`result`): richtig, wenn Ergebnis und Mehrheitsform aus `result` gleich den Labels sind;
    Nenner die Punkte, denen `result` eine Mehrheitsform gibt. Punkte, deren Ausschnitt nach dem Label
    nicht zum Punkt gehört, fallen aus dem Nenner (es gibt für sie kein Label) und werden gezählt.
  - **A2** und **B** (Niederschrift): richtig, wenn Ergebnis und Form (A2) beziehungsweise der volle
    Vektor der Positionen aller Parteien des Gremiums (B) gleich dem sind, was aus den Labels nach
    derselben Ergänzungsregel folgt. Gehört der Ausschnitt nach dem Label nicht zum Punkt, ist das ein
    Fehler des Verfahrens (es hat die Stelle falsch geschnitten), kein Ausfall.
  - Die Stichprobe ist geschichtet (nach der Mehrheitsform aus `result`, gleiche Aufteilung); die
    Präzision ist die auf die Grundgesamtheit der Punkte in den geladenen Niederschriften gewichtete
    Schätzung nach F4 (Σ W_h·p_h, Wilson bei Kishs n_eff). Entscheidend ist der Punktwert gegen 0,9; das
    Intervall wird berichtet.
- **Urteil je Ebene**: beide Bedingungen erfüllt → bauen; Präzision erfüllt, Abdeckung nicht → umbauen
  (bei B: der volle Abruf der Niederschriften oder ein besserer Schnitt hebt sie, § 6); Präzision nicht
  erfüllt → verwerfen in dieser Form. Ebene A kann ohne Ebene B gebaut werden; B setzt den Abruf der
  Niederschriften voraus und wird bei „bauen" eine Empfehlung an Konrad (Runbook § 7) mit Dauer und
  Größe, kein Netzlauf eines Agenten.

### 8.3 Rückfallregel

1. Ergebnis aus `result`. Fehlt `result` oder ist es `sonstiges`, aber die Niederschrift nennt ein
   Ergebnis, gilt das der Niederschrift.
2. Mehrheitsform aus der Niederschrift, wenn sie für den Punkt eine Formel trägt; **sonst** aus `result`;
   sonst `ohne_angabe`. Widersprechen sich beide, gilt die Niederschrift (sie ist das Protokoll, `result`
   ein Kurzeintrag), und der Widerspruch wird gezählt.
3. Positionen (Ebene B) nur aus der Niederschrift; ohne Niederschrift oder ohne gefundene Stelle bleiben
   alle `unbekannt` (der Beschluss ist dann nicht vollständig, auch wenn `result` „einstimmig" sagt —
   außer bei `einstimmig` ohne genannte Enthaltung im Rückfall aus `result`: dort sind alle `ja`
   beziehungsweise `nein`, und das wird als eigene Quelle `result_einstimmig` gezählt und gesondert
   validiert).
4. Ein Beschluss, dessen Stelle in der Niederschrift nicht gefunden wird, bekommt nur Ebene A aus `result`.

### 8.4 Mehrheiten, Opposition und Zeiträume

Ratsmehrheit nach [15-funktion.md](15-funktion.md), § 3.9, mit den Vereinbarungen aus
[25-quellen.md](25-quellen.md), § 2: **2020–2025 CDU und GRÜNE** (Kooperationsvereinbarung, Januar 2021),
**ab 2025 CDU und GRÜNE** (Koalitionsvertrag, Dezember 2025). Die Hypothesen H28.1 und H28.2 gelten ab
dem Monat der Vereinbarung: Sitzungen **2021-01-01 bis 2025-09-14** (Hauptrechnung) und ab
**2025-12-01** (Nebenrechnung); Sitzungen davor zählen nicht, weil es keine feste Mehrheit gab.
Opposition sind alle anderen Parteien im Rat. Die Bezirksvertretungen haben eigene Mehrheiten, die der
Datensatz nicht kennt (15, § 3.9); sie gehören zu keiner Hauptrechnung.

### 8.5 Sitze und Mitglieder (für H28.3)

Sitze nach der Wahl (25, § 1), Fraktionsbildung nach 25 und Profil; Wechsel während der Periode sind
nicht berücksichtigt (Annahme, § 9). Mitglieder des Rates = Sitze + Oberbürgermeister (stimmberechtigt).

| Partei (Fraktion) | 2020–2025 | ab 2025 |
|---|---|---|
| CDU | 30 | 31 |
| GRÜNE | 22 | 20 |
| SPD (Fraktion SPD/Volt) | 16 | 14 |
| VOLT (Fraktion SPD/Volt) | 2 | 2 |
| FDP | 8 | 5 |
| LINKE | 4 | 6 |
| AFD | 3 | 10 |
| PARTEI (2020–2025 PARTEI-Klima-Fraktion, ab 2025 Ratsgruppe) | 2 | 1 |
| KLIMA (PARTEI-Klima-Fraktion) | 1 | – |
| TIERSCHUTZ (2020–2025 Gruppe mit FW, ab 2025 Ratsgruppe) | 1 | 1 |
| FW | 1 | 1 |
| BSW | – | 1 |
| **Sitze** | **90** | **92** |
| **Mitglieder mit Oberbürgermeister** | **91** | **93** |

### 8.6 Die Hypothesen

Drei Hypothesen, je eine Entscheidung; die p-Werte werden über alle drei nach **Holm** korrigiert
(gemeinsamer Kern aus [00-synergien-2026-11.md](00-synergien-2026-11.md), § 1: `hypothese`, `p`,
`p_holm`, `ergebnis`, `n`, `festgelegt`). Ergebnisse: `bestätigt`, `widerlegt`, `nicht entscheidbar`; ein
„nicht entscheidbar" steht auf der Seite als solches, nie als „kein Effekt".

**Bezug.** Holtkamp (2008, *Kommunale Konkordanz- und Konkurrenzdemokratie*, VS Verlag) unterscheidet
Räte, in denen nach der Sache und mit breiten, wechselnden Mehrheiten entschieden wird (Konkordanz), von
Räten mit fester Mehrheit, Fraktionsdisziplin und einer Opposition, deren Initiativen scheitern
(Konkurrenz), und ordnet die nordrhein-westfälischen Großstädte eher der Konkurrenz zu. Vorhaben 15 hat
das beim Antragstellen gezeigt (K3 3,2 % in der Hauptperiode, § 3.11 dort); offen ist das Entscheiden
(15, § 3.12). Für den Umgang mit Anträgen der AfD: WZB-Studie (Discussion Paper SP V 2025-501, März
2025), bundesweit 4 968 Anträge der AfD in Kreistagen und Räten kreisfreier Städte 2019 bis 2024, davon
934 (18,8 %) mit „Zustimmung", wenn mindestens ein Zehntel der übrigen Mitglieder zustimmte; eine
frühere Studie desselben Hauses für Ostdeutschland kam auf rund 20 %.

#### H28.1 Die Mehrheit stimmt geschlossen (Konkurrenz, Hauptthese 1)

> In strittigen Abstimmungen des Rates stimmen die Fraktionen der Ratsmehrheit gleich.

- **Einheit**: ein Beschluss im Rat (Gremium `RAT`) mit Mehrheitsform `mehrheitlich`, Sitzung im Zeitraum
  der Hauptrechnung (§ 8.4), bei dem die Positionen von CDU und GRÜNE nach Ebene B bekannt sind (nicht
  `unbekannt`, nicht `geteilt`).
- **Maß**: Anteil der Einheiten, in denen CDU und GRÜNE dieselbe Position haben.
- **Test**: einseitiger exakter Binomialtest, H0: p ≤ 0,9 gegen H1: p > 0,9, α = 0,05 nach Holm.
- **Schwelle 0,9**, vorab gesetzt: eine Kooperation mit Fraktionsdisziplin stimmt fast immer gemeinsam;
  0,9 lässt Raum für freigegebene Abstimmungen und Gewissensfragen. Unter Konkordanz gibt es keine feste
  Mehrheit, und die beiden größten Fraktionen stimmten in strittigen Fragen deutlich öfter verschieden.
- **Entscheidung**: `bestätigt`, wenn p_holm < 0,05; `widerlegt`, wenn die obere Grenze des einseitigen
  95-%-Intervalls nach Clopper-Pearson unter 0,9 liegt; sonst `nicht entscheidbar`, und immer dann, wenn
  Ebene B das Kriterium (§ 8.2) nicht erfüllt oder n < 30.
- **Nebenrechnungen** (berichtet, entscheiden nicht): R1 Ausschüsse des Rates (Besetzung nach
  Ratsproporz); R2 ab 2025-12-01; R3 `geteilt` als „verschieden" gezählt statt ausgeschlossen; R4 nur
  Beschlüsse über Anträge von Fraktionen (Option 04, `urheber_art` = Fraktion).

#### H28.2 Die Opposition setzt sich selten durch (Konkurrenz, Hauptthese 2)

> Anträge, die nur Oppositionsfraktionen stellen, nimmt der Rat in weniger als einem Viertel der Fälle an.

- **Einheit**: eine Drucksache der Funktion Antrag (Dokumentart mit „Antrag", ohne „Anfrage"), deren
  Urheber nach Option 04 (`dokumente_urheber`, `urheber_art` = Fraktion) nur Oppositionsparteien sind,
  **ohne** AfD-Beteiligung (sie ist H28.3), mit einem entschiedenen Beschluss im Rat im Zeitraum der
  Hauptrechnung. Maßgeblich ist der **letzte** entschiedene Beschluss des Rates über diese Drucksache.
- **Maß**: Anteil der Einheiten mit Ergebnis `angenommen` (auch `geaendert`), nach Ebene A (aus `result`
  mit Rückfallregel). Braucht keine Niederschrift.
- **Test**: einseitiger exakter Binomialtest, H0: p ≥ 0,25 gegen H1: p < 0,25, α = 0,05 nach Holm.
- **Schwelle 0,25**, vorab gesetzt: unter einem Viertel scheitert eine Initiative der Opposition in der
  Regel; die Schwelle liegt bewusst über dem Anteil, den die WZB-Studie für Anträge der ausgegrenzten
  AfD fand, damit „Konkurrenz" nicht erst bei Ausgrenzung beginnt.
- **Entscheidung**: `bestätigt`, wenn p_holm < 0,05; `widerlegt`, wenn die untere Grenze des einseitigen
  95-%-Intervalls nach Clopper-Pearson über 0,25 liegt; sonst `nicht entscheidbar`, und immer dann, wenn
  Ebene A das Kriterium nicht erfüllt oder n < 30.
- **Nebenrechnungen**: R1 Ausschüsse; R2 ab 2025-12-01; R3 Anträge mit letztem Ergebnis `vertagt`,
  `verwiesen`, `erledigt`, `zurueckgezogen` als „nicht angenommen" im Nenner; R4 je Oppositionsfraktion.
  Die Abgrenzung zu Vorhaben 26 (Antragserfolg je Fraktion): 26 misst den Erfolg, diese Hypothese prüft
  eine Schwelle; dieselben Ergebnisklassen, wenn 26 sie baut.

#### H28.3 Die WZB-Schwelle (Umgang mit Anträgen der AfD)

> Im Rat findet ein kleinerer Anteil der Anträge der AfD Zustimmung nach der WZB-Schwelle als in der
> WZB-Studie (934 von 4 968 = 0,188).

- **Einheit**: eine Drucksache der Funktion Antrag mit AfD unter den Urhebern (Option 04, `parteien`
  enthält `AfD`), mit einem entschiedenen Beschluss im Rat, Sitzungen ab 2020-09-13 bis zum Ende des
  Datensatzes (beide Perioden gepoolt, wie die WZB-Studie einen Zeitraum von fünf Jahren poolt).
  Maßgeblich ist der letzte entschiedene Beschluss des Rates.
- **Zustimmung**, wie die WZB-Studie: die Ja-Stimmen der übrigen Mitglieder erreichen mindestens ein
  Zehntel der übrigen Mitglieder. Ja-Stimmen = Summe der Sitze (§ 8.5) der Parteien außer AfD mit
  Position `ja`, dazu einzeln genannte Mitglieder. Schwelle 2020–2025: 0,1 × (91 − 3) = 8,8, also 9;
  ab 2025: 0,1 × (93 − 10) = 8,3, also 9. Bei `geteilt` oder `unbekannt` zählen eine untere (0) und
  eine obere Schranke (alle Sitze); liegt die Schwelle dazwischen, ist die Einheit **unbestimmt**.
  Aus Ebene A allein bestimmt: `angenommen` → Zustimmung; `einstimmig` `abgelehnt` → keine Zustimmung.
- **Maß**: Anteil der bestimmten Einheiten mit Zustimmung.
- **Test**: einseitiger exakter Binomialtest, H0: p ≥ 0,188 gegen H1: p < 0,188, α = 0,05 nach Holm.
- **Entscheidung**: `bestätigt`, wenn p_holm < 0,05; `widerlegt`, wenn die untere Grenze des einseitigen
  95-%-Intervalls über 0,188 liegt; sonst `nicht entscheidbar`, und immer dann, wenn n < 20, wenn mehr als
  10 % der Einheiten unbestimmt sind, oder wenn Ebene B das Kriterium nicht erfüllt (Ebene A allein
  entscheidet nur `angenommen` und `einstimmig abgelehnt`; bei „mehrheitlich abgelehnt" braucht es B).
- **Nebenrechnungen**: R1 nur 2020–2025, R2 nur ab 2025; R3 Vergleichswert der kreisfreien Städte aus
  derselben Studie (rund 0,16, aus der Pressemitteilung, nicht aus dem Papier geprüft); R4 Ausschüsse und
  Bezirksvertretungen, wo ihre Besetzung bekannt ist (Vorhaben 27, Mitgliedschaften); R5 jede
  Zustimmung einer anderen Partei (auch unter der Schwelle) als Anteil.

#### Was ausdrücklich explorativ bleibt

Wie oft einstimmig je Gremiumsart und Periode; die Matrix „Partei × Urheberpartei → Anteil `ja`"
(wer stimmt Anträgen anderer zu); Enthaltungen je Partei; Querabstimmungen (eine Mehrheitsfraktion mit
der Opposition gegen den Partner); Bezirksvertretungen. Auf der Seite heißen sie „explorativ".


**Ergänzung 2026-11-24 (nach dem Vorab-Commit, ändert nichts oben).** Der Commit `97ebb52` trägt die
Zeit 00:41, nicht „gegen 00:45". Nach ihm entstanden: die Zählung von `result` (§ 3.1), die
Stichprobe der Niederschriften und das Verfahren (§ 3.3 bis 3.5) und die Fallzahlen (§ 3.7, nur n).
Keine Hypothese ist gerechnet, auch keine Probe davon.

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | Warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 9.1 | Lädt Konrad die Niederschriften ganz (Hauptperiode 966 Dateien, rund 1,2 GB, rund 24 min; alle Düsseldorfer Perioden 1 359, rund 1,7 GB, rund 34 min; für den Rat allein 47, rund 50 MB)? | Ebene B und H28.1, H28.3 hängen daran | erst nach dem Urteil der Kodierung; bei „bauen" zuerst die Ratsniederschriften |
| 9.2 | Wer besitzt die Ergebnisklassen je Tagesordnungspunkt, 26 oder 28? | dieselbe Wortregel zweimal gebaut liefe auseinander | 26 baut `ergebnis` je Punkt mit der Regel aus § 8.1; 28 ergänzt Form und Positionen |
| 9.3 | Fraktionswechsel und Austritte während der Periode | die Sitzzahlen der WZB-Schwelle und die Parteien des Rates gelten ab der Wahl | Sitze nach der Wahl (§ 8.5); später je Datum aus den Mitgliedschaften (27) |
| 9.4 | Personen ohne Partei im Abstimmungstext (57 von 945 Beschlüssen, meist Bezirksvertretungen, im Rat fraktionslose Mitglieder) | ohne Partei fehlt ihre Position, und bei kleinen Fraktionen kippt „vollständig" | Anwesenheitsliste der Niederschrift; mit 27 über `membership` |
| 9.5 | Gescannte Niederschriften ohne Textebene (4 von 22 Ausschusssitzungen der Stichprobe, 2020/21) | sie fallen auf Ebene A zurück | keine Texterkennung; sie zählen in B mit 0 |
| 9.6 | „Einstimmig" ohne genannte Enthaltung (Blockform) kann Enthaltungen verschweigen | B setzt dann alle auf ja | nach der Definition (keine Gegenstimme) und dem Codebuch gilt das; auf der Seite als „einstimmig" ohne Aussage über Enthaltungen |
| 9.7 | Darf die Seite das Stimmverhalten je Fraktion zeigen? | es ist öffentlich protokolliert, aber neu zusammengestellt | ja, je Fraktion, nie je Person |
| 9.8 | 2014–2020: OParl hat nur an 294 von 1 500 Sitzungen Anlagen (22,7 % der Beschlüsse mit Niederschrift) | Ebene B ist dort nicht möglich | dort nur Ebene A |
| 9.9 | Mönchengladbach | Stadtneutralität der Muster | nicht gemessen (Sitzungen noch nicht abgerufen); die Schritte bleiben dort aus, bis eine Stichprobe die Form der Niederschriften zeigt |
| 9.10 | Besetzung von Ausschüssen und Bezirksvertretungen für die Ergänzungsregel | nur Parteien, die die Niederschrift nennt, bekommen eine Position; eine nie genannte fehlt still | Näherung aus Anwesenheitsliste und Abstimmungen; mit 27 die wirkliche Besetzung |
| 9.11 | Vergleichswert der WZB-Schwelle: 18,8 % gepoolt oder rund 16 % für kreisfreie Städte? | die Entscheidung von H28.3 hängt an der Schwelle | 18,8 % wie vorab festgelegt; 16 % als Nebenrechnung R3 |
| 9.12 | Abstimmungen über verbundene Punkte (der Rat berät zwei Anträge gemeinsam und stimmt am Ende des zweiten über beide ab) | die Abstimmung des ersten steht im Abschnitt des zweiten | nicht gelöst; der erste fällt auf Ebene A zurück (ein Teil der 14 % ungelesenen Ratsabstimmungen) |
| 9.13 | Wird Ebene B in einer Umbau-Runde neu gemessen? | B verfehlt 0,9 (0,765); H28.1 und H28.3 hängen daran | nein, bis der Supervisor sie freigibt; dann Codebuch Fassung 2 (unten), frische Stichprobe, zuerst nur Ratsniederschriften |

**Regeln des Schlichters für eine Fassung 2 des Codebuchs** (2026-11-24; nur notiert, in Fassung 1
nicht angewendet, die Labels oben gelten unverändert):

1. Teilabstimmungen: es zählt die Gesamtabstimmung; gibt es nur Abstimmungen über Teile, folgt das
   Ergebnis dem Beschlusstext.
2. „geteilt" wird über die Anwesenheitsliste bestimmt (Mitglieder einer Partei in verschiedenen Fächern).
3. Tierschutz/Freie Wähler ausdrücklich als Gruppe aus zwei Parteien.
4. Offene Wahlen sind `angenommen` oder `abgelehnt`.
5. „Empfehlung abweichend beschlossen" nach dem Inhalt der Empfehlung.
6. Steht nur eine Ja-Zeile da, gilt sie wie ein vollständiges Fach.
7. „mehrheitlich" ohne Namen: Form `mehrheitlich`, `uebrige` unbekannt.
8. „SPD" allein gilt nur dann als SPD und Volt, wenn die Niederschrift die Fraktion SPD/Volt sichtbar
   nennt; der Zeitraum der gemeinsamen Fraktion gehört ins Codebuch.

## 10. Änderungen durch die Synergie (füllt der Supervisor)

Geschrieben am 2026-11-28 vom Supervisor der Phase „Zeigen“ vor dem Start der Stufe 2 (nur Ebene A,
§ 5.1), nach Konrads „weiter“ zu 16 und 28 (2026-11-27). Die Synergie
([00-synergien-2026-11.md](00-synergien-2026-11.md)) hat für 28 keinen Abschnitt in § 4; was seither
auf `main` liegt, geht dem Bauplan (§ 6, § 7) vor.

1. **Eingabe aus 26, kein eigenes Paket.** Die Tabelle „Paper × Tagesordnungspunkt“ von 26
   (`analysis.outcomes.AGENDA_SCHEMA`, unter `raw/tagesordnungspunkte.parquet`, auf Pages aus
   `snapshots/duesseldorf-beschluesse/`) trägt je Beratung jeden Tagesordnungspunkt mit `result`
   wörtlich. Die Einheit aus § 8.1 (ein Punkt mit Beratung) ist eine Zeile dort mit `top` nicht null;
   steht dieselbe Drucksache zweimal in einer Sitzung, sind es zwei Zeilen. `georep pack --votes`
   entfällt; deckt das Paket von 26 eine Periode nicht, fehlt 28 dort, mit Namen im Log.
2. **Frage 9.2, entschieden: die Wortregel aus § 8.1 bleibt das Verfahren von 28.** Gemessen und
   bestätigt ist genau sie (Präzision 0,982, 0,928–0,995); der Wortschatz von 26
   (`[outcomes.results]`) ist eine andere Regel für eine andere Einheit (die Beschlusslage je
   Dokument). Ein Test vergleicht beide je Punkt (`angenommen` ⇔ Stufe `sache` mit `beschlossen` oder
   `geaendert`, `abgelehnt` ⇔ `abgelehnt`, `zurueckgezogen` ⇔ `zurueckgezogen`); jede Abweichung wird
   gezählt und im Entscheidungseintrag mit Beispielen genannt, nicht still angeglichen.
3. **Nur Ebene A** (§ 5.1): `ergebnis`, `geaendert`, `form`, `form_quelle = "result"`. Ohne
   `positionen`, `vollstaendig`, `niederschrift` und ohne die Schritte `minutes` und `minutes_text`;
   kein Netz. H28.2 wird gerechnet, H28.1 und H28.3 stehen als `nicht entscheidbar` in der
   Hypothesentabelle.
4. **Bausteine von `main`.** Gremium und Gremiumsart über `prep.bodies.organization_key` und
   `[bodies.organizations]` wie bei 26; Mehrheiten und Sitze aus `[[majorities.terms]]` des
   Stadtprofils (15, Punkt 75); die Hypothesentabelle mit dem Spaltenkern und `family` aus
   `analysis.hypotheses` (17, Punkt 78), wie 22. Beitrag `28-abstimmungen` am Ende von
   `CONTRIBUTIONS` (hinter 26), Fabrik mit `http` (F7), Pfade im Modul, Settings nach der
   Anhängeregel, Schalter in `defaults.toml` aus, an in den Düsseldorfer Profilen, deren Paket von 26
   die Punkte trägt; Mönchengladbach aus (Frage 9.9).
5. **Stufe 2 und Stufe 3 in einem Bau** (Ressourcen; Plan der Phase § 5): der Abschnitt
   „Abstimmungen“ auf `akteure.html` über `Contribution.sections` (V1, Punkt 86), nur die Punkte 1 und 2
   aus § 7 nach der Kodierung: Einstimmig, mehrheitlich, geändert je Gremiumsart und Periode mit dem
   Satz aus `validierung/28-abstimmungen/guete.json`, und die Hypothesentabelle (H28.2 mit Ergebnis,
   H28.1 und H28.3 `nicht entscheidbar`, festgelegt mit Commit `97ebb52`). Rund 10 KB. Downloads
   `abstimmungen_gremien` und `abstimmungen_hypothesen` (Parquet und CSV, je klein), Spalten auf
   `spalten.html` (Punkt 94). `abstimmungen.parquet` je Punkt nur als Parquet (Rückstand 35). Keine
   Personen, keine Positionen je Fraktion.
6. **Validierung.** `guete.json` stammt von zwei KI-Kodierern desselben Modells (Labels vor dem
   2026-11-26, F4-Nachzug V3); die Seite nennt nur die Kennzahlen mit `alpha_genuegt = true`, für
   Ebene A die Fragen `ergebnis` und `form`.

