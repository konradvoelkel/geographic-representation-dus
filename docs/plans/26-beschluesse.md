# Vorhaben 26: Beschlusslage und Antragserfolg

Stand 2026-11-24, Stufe 1 (Messen), Branch `feat/26-beschluesse`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „26 Beschlusslage und
Antragserfolg". Messskript: [26-beschluesse-messung.py](26-beschluesse-messung.py) (`uv run python
docs/plans/26-beschluesse-messung.py`, rechnet jede Zahl dieses Dokuments nach; `--stichprobe` schreibt
Stichprobe und Kodieraufträge, `--auswertung` wertet die Regel gegen die Labels aus). Codebuch und
Stichprobe, Labels und Güte: `validierung/26-beschluesse/`. Vorab festgelegt in Commit `c94ae31`
(Autordatum 2026-11-24, 00:41:48), Regel und Codebuch in `94da91f` (00:54), Stichprobe in `f797535`
(00:56) — die Namen nach dem Rebase auf `main` 0.23.0 um 01:14; vorher hießen sie `d68962e`, `e2b3545`,
`e9e9bcb`, und so nennt das Codebuch im Kopfkommentar den ersten. § 3.1 steht wörtlich, wie er vorab
committet wurde; gesehen war bis dahin nur Beschreibendes (die 22 Werte von `result` und ihre
Häufigkeit je Dokumentart, die Abdeckung der Beratungen, rund 70 Beratungsfolgen als Beispiele).

**Urteil der Stufe 1 (§ 5): bauen, mit Rückfall 1 — die Beschlusslage ohne den Prüfauftrag.** Nach der
vorab festgelegten Regel, ohne Anpassung an die Labels: die volle Klasse verfehlt das Kriterium
(142 / 150 = 0,947, gewichtet 0,894), weil die Regel für den Prüfauftrag 8 von 65 angenommenen Anträgen
anders liest als die Kodierer; `ergebnis` allein trifft 150 / 150 (Wilson 0,975–1,000, gewichtet
1,000), und 94,3 % der Anträge der Hauptperiode haben ein Ergebnis. **Der Beleg ist schwach**: beide
Kodierer sind dasselbe Modell (Frage 19), sie waren sich in allen 215 Antworten einig (α 1,0), und
69 der 150 Fälle sind die Abbildung eines einzigen Eintrags aus einem festen Wortschatz; nur 17 Fälle
verlangten eine Entscheidung über mehrere Einträge (17 / 17 richtig, Wilson 0,816–1,000; § 4.1).

Die drei Zahlen, auf die es ankommt:

1. **Ergebnis für 94,3 % der Anträge der Hauptperiode** (4 810 von 5 099; abschließend entschieden
   93,5 %), 93,5 % in 2014-2020, 98,6 % in der laufenden Periode. Der Weg ist billig und fast verlustfrei:
   jeder Antrag hat eine Beratung in der Liste `consultations` und einen Tagesordnungspunkt, und die
   289 Anträge der Hauptperiode ohne Ergebnis stehen alle auf einem Tagesordnungspunkt, dem die
   Sitzungsleitung kein Ergebnis eingetragen hat — 155 davon in **einer** Sitzung, der Haushaltssitzung
   des Rates am 2021-02-05. `resolutionText` und `resolutionFile` füllt der Server nie (in keinem der
   drei Abrufe); das Ergebnis ist ein fester Wortschatz von 22 Werten.
2. **Konkurrenz im Rat, Konsens in den Bezirken, gemessen am Ergebnis.** Hauptperiode, Anträge mit
   Sachentscheidung: Anträge der Ratsmehrheit (CDU, Grüne) werden im Rat zu **98,3 %** angenommen (n 417),
   die der übrigen Fraktionen zu **18,7 %** (n 611); in den Bezirksvertretungen 93,4 % gegen 93,9 %.
   Standardisiert nach Gremium und Periode liegen CDU und Grüne bei beobachtet/erwartet 1,23, SPD/Volt
   bei 1,00, FDP 0,97, Linke 0,45; Anträge der AfD und der Ratsgruppe Tierschutz/Freie Wähler wurden in
   dieser Periode keiner angenommen (46 und 71 mit Sachentscheidung). Explorativ (§ 3.10).
3. **Der Server sagt, was das Gremium eingetragen hat, nicht immer, was geschah.** Zwei Gegenproben aus
   den Daten selbst zeigen die Grenze, die keine Kodierung der Einträge sehen kann (§ 3.8): in der
   Bezirksvertretung 9 tragen 2014 und 2015 **alle** 179 Anträge „zur Kenntnis genommen" (2016 noch die
   Hälfte), und ein angenommener Änderungs- oder Ergänzungsantrag führt nur in 29 von 81 Fällen
   (Hauptperiode) dazu, dass die geänderte Vorlage „abweichend beschlossen" heißt. Umgekehrt trägt die Klasse, wo es zählt: unter
   1 784 abgelehnten Anträgen hat genau einer eine Folgevorlage der Verwaltung, unter den angenommenen
   ein Viertel (§ 3.7).

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

**Frage.** Was wurde aus einem Antrag — angenommen wie gestellt, geändert, abgelehnt, zurückgezogen,
vertagt, verwiesen, ohne Abstimmung erledigt? Ist ein angenommener Antrag nur ein Prüfauftrag, und kam
danach eine Vorlage der Verwaltung? Wie lange dauert es bis zur Entscheidung, und wie erfolgreich sind
die Fraktionen, gemessen an dem, was in ihrem Gremium üblich ist?

**Ratsarbeit.** „Was wurde aus dem Antrag?" ist der Weg, den `workflow-ratsmitglied.md`, § 4, heute ins
Ratsinformationssystem schickt; Vorhaben 14 gibt den Vorgang (Antrag und Umsetzungsvorlage), dieses
Vorhaben das Ergebnis jeder Station. Für die Wiedervorlage zählen die beschlossenen Prüfaufträge ohne
Folgevorlage. Und für Vorhaben 14 klärt es, was dort offen blieb: **Anfragen im Rat werden in der Sitzung
beantwortet** — 97,3 % tragen „beantwortet" oder „schriftlich beantwortet" (§ 3.9), wo 14 nur 0,1 % mit
Antwortanlage fand.

**Literatur.** Volden und Wiseman (2014)* messen „legislative effectiveness" als Weg eines Antrags durch
die Stufen bis zur Annahme; die Beschlusslage ist die kommunale Entsprechung der letzten Stufe. Holtkamp
(2008)* unterscheidet Konkordanz- von Konkurrenzdemokratie; § 3.10 zeigt beides in einer Stadt, getrennt
nach Gremienart, wie Vorhaben 15 es für gemeinsame Anträge fand. Die WZB-Studien zur AfD in
Kommunalparlamenten (Schroeder, Ziblatt, Bochert) zählen Zustimmung zu Anträgen; das Ergebnis allein
sagt nicht, wer zugestimmt hat (Vorhaben 28). Mit * markierte Angaben stehen im Meta-Plan aus dem
Gedächtnis und sind vor einem Zitat auf der Seite nachzuschlagen (`report/literatur.toml`).

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

Gerechnet auf den Läufen vom 2026-11-24 (`georep bootstrap && georep run` für `duesseldorf`,
`duesseldorf-2014`, `duesseldorf-2025` und `moenchengladbach` im Worktree, zwischen 00:30 und 00:46 Uhr).

**Netzlauf aus F6** (Konrads Lauf über den Supervisor, 2026-11-23 23:29 bis 2026-11-24 00:32; Stamps
`code` 0.22.0), aus der Datenwurzel des Hauptklons in die des Worktrees kopiert, dort gelesen mit
`georep.council.council_files(layout)` und den Modellen aus `georep.oparl`:

| Datensatz | `meetings.jsonl` | `agenda_items.jsonl` | `consultations.jsonl` | Sitzungen | Tagesordnungspunkte |
|---|---|---|---|---|---|
| 2014-2020 (`duesseldorf-2014`) | 10,1 MB | 46,9 MB | Kopie aus der Hauptperiode | 3 172 | 81 139 |
| 2020-2025 (`duesseldorf`) | 6,3 MB | 27,2 MB | 56,3 MB, 97 112 Beratungen | 1 672 | 44 231 |
| 2025- (`duesseldorf-2025`) | 1,3 MB | 5,5 MB | 56,3 MB (eigener Abruf, 00:15 Uhr) | 390 | 8 719 |
| Mönchengladbach | — | — | — | Netzlauf lief noch | — |

Die Beratungen sind eine Liste des Bodys; für 2014-2020 lief ihr Abruf beim Kopieren noch (Teildatei),
darum liest das Profil die vollständige Datei der Hauptperiode, wie das Runbook (§ 5.3) es vorsieht.
Die Sitzungen jedes Profils beginnen am Periodenbeginn und haben **keine** Obergrenze (Punkt 70); die
Liste der Hauptperiode enthält also auch die Sitzungen der laufenden Periode. `persons.jsonl` und
`memberships.jsonl` liest dieses Vorhaben nicht (Vorhaben 27).

Gelesene Felder: `OparlAgendaItem`: `id`, `meeting`, `number`, `order`, `name`, `consultation`,
`result` (dazu gezählt: `resolutionText`, `resolutionFile`); `OparlMeeting`: `id`, `start`,
`organization`, `auxiliaryFile[].name`; `OparlConsultation`: `id`, `paper`, `meeting`, `agendaItem`,
`organization`, `role`, `authoritative`. Gremienkürzel aus `[bodies.organizations]` des Profils.

**Korpus je Profil**, nur lesend: `interim/papers.parquet` (`id`, `name`, `reference`, `date`,
`paper_type`, `file_name`, `text` kleingeschrieben), `processed/papers_gremien.parquet` (`id`,
`gremium`, `gremium_art`), `processed/dokumente_urheber.parquet` (`id`, `urheber_art`, `parteien`,
`quelle`). 2014-2020: 22 215 Dokumente, Hauptperiode 19 108, laufende Periode 4 095, Mönchengladbach
2 895.

**Aus anderen Vorhaben**, nur lesend: die Rolle (`art2`) aus dem Messskript von 14; Antragsteller,
Fraktionseinheiten (SPD/Volt, Tierschutz/FW/PARTEI) und Ratsmehrheit je Periode aus dem Messskript von
15 (`antragsteller`, `FRAKTION_EINHEIT`, `MEHRHEIT`); die Kanten aus der Stufe 2 von 14
(`processed/vorgang_kanten.parquet` im Worktree `14-vorgaenge`, Commit `0a15e88`, Rückfallregel: 3 563
starke Kanten), beim ersten Lauf nach
`/media/konrad/xtraspace/georep/messdaten/26-beschluesse/vorgang_kanten-<ordner>.parquet` kopiert; für
die Kodieraufträge der Rohtext aus Phase 0 (`messdaten/rohtext/<ordner>.parquet`).

**Herkunft und Lizenz**: dieselben OParl-Metadaten des Ratsinformationssystems wie der Korpus. Ins Repo
und auf die Seite kämen nur IDs, Gremienkürzel, Daten, der Wortlaut von `result` (ein fester Wortschatz)
und abgeleitete Klassen und Zahlen (Frage 6 des Meta-Plans). Als Paket gerechnet: die Tabelle „Paper ×
Tagesordnungspunkt" (`id`, Beratung, Punkt, Gremium, Rolle, Sitzungsdatum, Nummer, `result`) hat für die
drei Düsseldorfer Perioden **58 510 Zeilen in 649 KB** (zstd).

## 3. Messung

Alle Zahlen vom 2026-11-24, letzter Lauf des Messskripts um 01:06 Uhr, **18,2 s** bei Lastmittel 12,0 →
11,7 (`uptime` davor und danach; frühere Läufe 13,9 bis 17,3 s bei Lastmittel 7 bis 26, die Zahlen
gleich), `nice -n 10`, Polars auf vier Threads. Laden und Zusammenführen der drei Netzläufe 8 bis 10 s,
die Klassen über alle 48 313 Dokumente rund 6 s.

### 3.1 Vorab festgelegt (2026-11-24, 00:41 Uhr, vor jeder Klassenvergabe)

**Einheit.** Ein Antrag: eine Drucksache mit der Rolle `antrag` nach `art2` aus Vorhaben 14
(Dokumentart „Antrag …", „Haushaltsantrag …", „zAntrag …", Fraktions- und Mitgliederantrag; bis 2019
„Vorlage aus der Politik" mit „Antrag" im Titel; der Titel schlägt die Dokumentart, wo beide sich
widersprechen). Grundgesamtheit: die Anträge der drei Düsseldorfer Perioden; Mönchengladbach nur
beschreibend, sobald sein Netzlauf fertig ist. Beschlussvorlagen der Verwaltung und Anfragen werden mit
derselben Abbildung beschrieben, aber nicht validiert.

**Klassen der Beschlusslage** (Frage `ergebnis`, genau eine je Antrag). Maßgeblich ist die **letzte
Entscheidung in der Sache** über alle Beratungen des Antrags, nach Sitzungsdatum: beschlossen, geändert
beschlossen, abgelehnt, zurückgezogen, auch als Empfehlung eines vorberatenden Gremiums. Eine spätere
Entscheidung in der Sache ersetzt eine frühere; Kenntnisnahme, Vertagung und Verweisung ersetzen keine.
Nur wenn es keine Entscheidung in der Sache gibt, zählt der letzte andere Stand.

| Klasse | Bedeutung | Werte von `result`, die sie tragen |
|---|---|---|
| `beschlossen` | angenommen, wie gestellt | einstimmig beschlossen, mehrheitlich beschlossen, beschlossen; Empfehlung einstimmig/mehrheitlich beschlossen |
| `geaendert` | angenommen mit Änderungen | abweichend beschlossen; Empfehlung abweichend beschlossen |
| `abgelehnt` | nicht angenommen, auch förmlich zurückgewiesen | einstimmig abgelehnt, mehrheitlich abgelehnt, abgelehnt aufgrund Stimmengleichheit, zurückgewiesen; Empfehlung … abgelehnt |
| `zurueckgezogen` | vom Antragsteller zurückgenommen | zurückgezogen |
| `erledigt` | behandelt, ohne über ihn abzustimmen | zur Kenntnis genommen, passieren lassen, beantwortet, schriftlich beantwortet |
| `vertagt` | zuletzt vertagt oder zurückgestellt, danach nichts im Datensatz | vertagt, zurückgestellt |
| `offen` | an ein anderes Gremium verwiesen, dort nichts im Datensatz | verwiesen |
| `ohne_ergebnis` | keine Beratung mit einem Ergebnis im Datensatz | (Tagesordnungspunkt ohne `result`, Beratung ohne Tagesordnungspunkt, keine Beratung) |

**Prüfauftrag** (Frage `auftrag`, nur bei `beschlossen` und `geaendert`): `pruefauftrag`, wenn der
Antrag von der Verwaltung **nur** verlangt, etwas zu prüfen, zu berichten, darzustellen oder ein Konzept,
eine Stellungnahme oder einen Vorschlag vorzulegen; `sachbeschluss`, wenn er mindestens eine Sache selbst
festlegt oder eine Maßnahme in Auftrag gibt (auch mit Bericht), Mittel vergibt, etwas erklärt oder Dritte
auffordert. Beurteilt wird der Antrag, wie er gestellt ist; den geänderten Wortlaut kennt der Datensatz
nicht.

**Kriterium** (Briefing, unverändert): **Präzision ≥ 0,95 an 150, Ergebnis für mindestens 80 % der
Anträge**, ausgelegt so:

1. *Präzision*: Anteil der Anträge der Stichprobe, deren Klasse der Regel dem Endlabel (zwei
   Kodier-Agenten, Schlichtung der Uneinigkeiten, F4) gleicht. Eine Einheit ist **richtig**, wenn
   `ergebnis` gleich ist und, wo `ergebnis` `beschlossen` oder `geaendert` ist, auch `auftrag`. Labels
   `unklar` fallen aus Zähler und Nenner und werden berichtet; sind es mehr als 15, ist das Codebuch zu
   unscharf, und das ist der Befund. Erfüllt ist das Kriterium nur, wenn **beide** Zahlen ≥ 0,95 sind:
   die ungewichtete an der Stichprobe und die mit den Schichtgrößen gewichtete (F4, Σ W_h·p_h).
2. *Ergebnis*: Anteil der Anträge der **Hauptperiode** mit einer Klasse außer `ohne_ergebnis`.
   Berichtet wird daneben der Anteil mit **abschließendem** Ergebnis (`beschlossen`, `geaendert`,
   `abgelehnt`, `zurueckgezogen`, `erledigt`) und beides für die beiden anderen Perioden.

**Rückfallregel**, in dieser Reihenfolge, ohne neue Kodierung (dieselben Labels):

- **Rückfall 1, ohne Prüfauftrag**: verfehlt die volle Klasse das Kriterium, erreicht es aber, wenn nur
  `ergebnis` verglichen wird, dann gilt `ergebnis` ohne `auftrag`. Der Prüfauftrag kommt nicht als
  Klasse auf die Seite, „offene Prüfaufträge" entfallen; der beantragte Prüfauftrag bleibt eine
  beschreibende Spalte ohne Anzeige.
- **Rückfall 2, grobe Klassen**: verfehlt auch `ergebnis` das Kriterium, gilt es für die groben Klassen
  `angenommen` (beschlossen, geaendert), `abgelehnt`, `ohne_sachbeschluss` (zurueckgezogen, erledigt),
  `offen` (vertagt, offen) und `ohne_ergebnis`; richtig ist eine Einheit, wenn die grobe Klasse gleich ist.
- Verfehlen auch die groben Klassen das Kriterium: Urteil **umbauen** (eine Runde mit neuer Stichprobe,
  Plan § 8) oder **verwerfen**.

Zusätzlich, für jede Stufe: eine Klasse mit mindestens 10 Einheiten in der Stichprobe und einer
Präzision unter 0,80 kommt nicht als eigene Klasse auf die Seite, sondern nur in ihrer groben Klasse.

**Stichprobe**: 150 Anträge, Seed 26, gezogen mit dem Rang von F4 (SHA-256 aus Seed und Schlüssel, je
Schicht die kleinsten Ränge). Schichten = Klasse der Regel, `pruefauftrag` als eigene Schicht
(angenommen mit Prüfauftrag), feste Aufteilung: beschlossen 25, geaendert 20, pruefauftrag 20,
abgelehnt 20, zurueckgezogen 15, erledigt 15, vertagt 15, offen 10, ohne_ergebnis 10. Hat eine Schicht
weniger Anträge, kommen alle, und der Rest geht an `beschlossen`. Die Regel wird vor dem Ziehen
committet; ändert sie sich danach, gilt eine neue Stichprobe.

**Kodierung**: zwei Kodier-Agenten und ein Schlicht-Agent nach F4. Sie sehen je Antrag Titel,
Drucksache, Datum, Dokumentart, den Textanfang und die Beratungsfolge, wie der Server sie füllt (je
Beratung Gremium, Rolle, Sitzungsdatum, Nummer und Bezeichnung des Tagesordnungspunkts, Wortlaut von
`result`); nicht die Klasse der Regel, nicht die Schicht.

**Erfolg je Fraktion**: nur standardisiert und „explorativ" (Frage 14, Annahme). Erfolg = Anteil
`angenommen` unter den Anträgen mit `angenommen` oder `abgelehnt`; erwartet = Summe der Erfolgsquoten
von Gremium und Periode über die Anträge der Fraktion (indirekte Standardisierung wie 14 § 3.8); ein
gemeinsamer Antrag zählt für jede beteiligte Fraktion. Keine Hypothese, kein Test.

### 3.2 Was der Server füllt

| Feld | 2014-2020 | 2020-2025 | 2025- |
|---|---|---|---|
| Sitzungen (davon bis zum Abruf am 2026-11-23) | 3 172 (3 078) | 1 672 (1 578) | 390 (296) |
| Tagesordnungspunkt `result`, alle | 81,7 % | 77,5 % | 73,7 % |
| … in vergangenen Sitzungen | 82,3 % | 78,6 % | 79,1 % |
| … mit Beratung, in vergangenen Sitzungen | **93,0 %** (54 832 / 58 939) | **93,4 %** (29 063 / 31 133) | **96,6 %** (5 506 / 5 702) |
| Tagesordnungspunkt `consultation` | 73,2 % | 71,4 % | 70,7 % |
| `resolutionText`, `resolutionFile` | 0 | 0 | 0 |
| verschiedene Werte von `result` | 21 | 21 | 20 |
| Sitzung mit Anlage „Niederschrift …" (vergangen) | 44,2 % | 71,8 % | 56,4 % |

Die Punkte ohne Beratung sind Verfahren (Beschlussfähigkeit, Tagesordnung, Mitteilungen), wie das
Runbook (§ 2) sie beschreibt; sie tragen das Ergebnis seltener und zählen hier nicht.

**Der Wortschatz** von `result`, alle drei Abrufe zusammen 22 Werte: einstimmig beschlossen, zur
Kenntnis genommen, vertagt, mehrheitlich beschlossen, beantwortet, schriftlich beantwortet, Empfehlung
einstimmig beschlossen, abweichend beschlossen, mehrheitlich abgelehnt, zurückgezogen, passieren lassen,
Empfehlung mehrheitlich beschlossen, Empfehlung abweichend beschlossen, beschlossen, verwiesen,
zurückgestellt, einstimmig abgelehnt, Empfehlung mehrheitlich abgelehnt, zurückgewiesen, Empfehlung
einstimmig abgelehnt, abgelehnt aufgrund Stimmengleichheit — und leer. Jeder Wert hat in § 3.1 eine
Klasse; ein neuer Wert bricht die Messung (und in Stufe 2 den Schritt) mit seinem Wortlaut ab.

**Beratungen** (Liste des Bodys, 97 112): `meeting` und `agendaItem` bei 93,7 %; `role` „-" 66 873
(68,9 %), Entscheidung 16 260, Kenntnisnahme 9 817, Vorberatung 2 771, Anhörung 1 391; `authoritative`
wahr bei 84 366, sonst leer — `false` kommt nicht vor. Die Rolle trägt also wenig, und die Regel braucht
sie nicht (§ 3.1: die letzte Entscheidung in der Sache, gleich in welcher Rolle).

**Verbindung**: Punkte je Beratung über `agendaItem.consultation` (Hauptperiode): eine 26 475, zwei
1 456, drei und mehr 511 — die vertagten Vorlagen, die auf mehreren Tagesordnungen stehen (Runbook § 3).
Wo `consultation.agendaItem` einen Punkt der Liste des Profils nennt, nennt dieser Punkt die Beratung
zurück (28 442 von 28 442); die übrigen nennen Punkte aus Sitzungen, die nicht zum Profil gehören.

**Je Gremium** (Punkte mit Beratung in vergangenen Sitzungen, Hauptperiode): fast überall 88 bis 100 %;
darunter nur JURAT 77,0 %, SCHUA 80,2 %, BV5 81,8 %. Der Rat 89,2 %.

### 3.3 Vom Antrag zum Ergebnis

Der billigste Weg ist der, den das Runbook (§ 3) und Punkt 70 beschreiben, ohne die Paper neu
abzurufen: Antrag → Beratungen aus `consultations.jsonl` (über `paper`) → Tagesordnungspunkte, die die
Beratung nennen (`agendaItem.consultation == consultation.id`, dazu der Punkt aus
`consultation.agendaItem`, falls er die Beratung nicht nennt) → Sitzung (Datum, Gremium) und `result`.
Die Folge wird nach Sitzungsbeginn, dann `order` sortiert; maßgeblich ist der Punkt nach § 3.1.

| Datensatz | Rolle | n | mit Beratung | mit Tagesordnungspunkt | mit Ergebnis |
|---|---|---|---|---|---|
| 2014-2020 | Antrag | 3 198 | 100,0 % | 100,0 % | 93,5 % |
| 2020-2025 | Antrag | 5 099 | 100,0 % | 100,0 % | **94,3 %** |
| 2025- | Antrag | 928 | 100,0 % | 100,0 % | 98,6 % |
| 2020-2025 | Vorlage | 5 507 | 100,0 % | 100,0 % | 98,9 % |
| 2020-2025 | Anfrage | 3 952 | 100,0 % | 100,0 % | 96,6 % |
| 2020-2025 | Information | 4 203 | 100,0 % | 100,0 % | 99,6 % |
| Mönchengladbach | alle | 2 895 | — | — | Netzlauf fehlte |

Ein Antrag der Hauptperiode hat fast immer **eine** Beratung (4 943 von 5 099; zwei 144, drei und
mehr 12) und einen Tagesordnungspunkt (4 724; zwei 317, drei und mehr 58).

**Anträge ohne Ergebnis und warum.** Alle haben einen Tagesordnungspunkt, dem kein Ergebnis eingetragen
ist; keiner scheitert an der Verbindung.

| Datensatz | ohne Ergebnis | davon Haushaltsanträge | Gremium der Drucksache |
|---|---|---|---|
| 2014-2020 | 208 | 10 | BV9 96, RAT 29, SCHUA 21, AWM 17, BV6 11, INTR 10 |
| 2020-2025 | 289 | 156 | RAT 225, JURAT 33, BV7 9, BV5 5 |
| 2025- | 13 | 0 | RAT 9, BV10 3, BV8 1 |

In der Hauptperiode liegen **155 der 289 in einer einzigen Sitzung**: der Haushaltssitzung des Rates am
2021-02-05, in der kein Haushaltsantrag ein Ergebnis trägt. Die übrigen verteilen sich auf einzelne
Sitzungen (Rat 2025-07-10: 10, Jugendrat 2025-09-18: 8, Rat 2021-09-16: 8 …). Das Ergebnis dieser
Sitzungen steht nur in der Niederschrift.

### 3.4 Klassen der Beschlusslage

Anträge, nach der Regel aus § 3.1 (Commit `94da91f`, vor dem Rebase `e2b3545`):

| Klasse | 2014-2020 | 2020-2025 | 2025- |
|---|---|---|---|
| `beschlossen` | 1 696 (53,0 %) | 2 585 (50,7 %) | 420 (45,3 %) |
| `geaendert` | 226 (7,1 %) | 660 (12,9 %) | 96 (10,3 %) |
| `abgelehnt` | 421 (13,2 %) | 1 028 (20,2 %) | 335 (36,1 %) |
| `zurueckgezogen` | 252 (7,9 %) | 406 (8,0 %) | 57 (6,1 %) |
| `erledigt` | 354 (11,1 %) | 88 (1,7 %) | 2 (0,2 %) |
| `vertagt` | 29 (0,9 %) | 31 (0,6 %) | 5 (0,5 %) |
| `offen` | 12 (0,4 %) | 12 (0,2 %) | 0 |
| `ohne_ergebnis` | 208 (6,5 %) | 289 (5,7 %) | 13 (1,4 %) |
| **mit Ergebnis** | **93,5 %** | **94,3 %** | **98,6 %** |
| abschließend | 92,2 % | 93,5 % | 98,1 % |
| ohne Haushaltsanträge: mit Ergebnis | 93,3 % (n 2 953) | 96,8 % (n 4 141) | 98,2 % (n 738) |

Der maßgebliche Wert in der Hauptperiode: einstimmig beschlossen 1 936, mehrheitlich abgelehnt 1 010,
abweichend beschlossen 655, mehrheitlich beschlossen 627, zurückgezogen 406, passieren lassen 86,
zurückgestellt 18, beschlossen 15, vertagt 13, verwiesen 12, einstimmig abgelehnt 8, Empfehlungen 19,
abgelehnt aufgrund Stimmengleichheit 3, zur Kenntnis genommen 2. Die Empfehlung eines vorberatenden
Gremiums ist in 19 von 5 099 Fällen die letzte Entscheidung — der Sonderfall, an dem die Regel am
meisten entscheidet, ist selten.

**Prüfaufträge** unter den angenommenen Anträgen (nach der Kodierung **nicht tragfähig**, § 4.1: die
Regel übersieht rund ein Viertel der Prüfaufträge, die Zahlen sind Untergrenzen): 390 von 1 922
(20,3 %), 739 von 3 245 (22,8 %), 125 von 516 (24,2 %). Die Regel (`pruefauftrag()` im Skript, vor der Stichprobe committet) liest den
Beschlusstext im kleingeschriebenen Korpus vom letzten Marker („antrag:", „folgendes zu beschließen:",
„beschlussvorschlag" …) bis zur Begründung und zerlegt ihn in Sätze. Ein Satz mit Prüfwort (prüf…,
untersuch…, Bericht, Konzept, vorlegen, vorstellen, darstellen …) ist eine Prüfung; er trägt zusätzlich
eine Maßnahme, wenn vor dem Prüfwort eine steht oder danach eine folgt, die nicht in einer Frage
(„prüfen, ob …") oder unter Vorbehalt („wenn die Prüfung positiv …") steht. Ein Satz ohne Prüfwort und
ohne Fragezeichen ist eine Maßnahme, wenn er eine Handlung festlegt (trennbares „zu"-Infinitiv,
„beschließt" ohne „dass die Verwaltung", Mittel bereitstellen, Passiv wie „wird eingerichtet",
„soll … werden", Subjekt mit Handlungsverb). Prüfauftrag heißt: mindestens eine Prüfung, keine
Maßnahme. Den Beschlusstext findet die Regel hinter einem Marker bei 4 609 Anträgen der
Hauptperiode, ohne Marker liest sie den Textanfang (452), ohne Text den Titel (38).

**Haushaltsanträge** (Dokumentart oder Titel mit „Haushalt"): Hauptperiode 958, davon 487 im Rat —
beschlossen 114, geändert 3, abgelehnt 212, zurückgezogen 3, **ohne Ergebnis 155** (die Sitzung vom
2021-02-05). In den Ausschüssen tragen sie oft „passieren lassen" (an den Rat weitergegeben, 63 als
`erledigt`). Laufende Periode: 190, davon 125 im Rat, alle mit Ergebnis (6 beschlossen, 119 abgelehnt).

**Wo „erledigt" eine Praxis der Sitzungsleitung ist, nicht ein Ergebnis.** Anträge mit maßgeblichem
Ergebnis „zur Kenntnis genommen", nach Gremium und Jahr der Sitzung (mindestens 10):

| Gremium, Jahr | `erledigt` | Anteil |
|---|---|---|
| BV9 2015 | 98 von 98 | 100 % |
| BV9 2014 | 81 von 81 | 100 % |
| BV9 2016 | 34 von 70 | 48,6 % |
| RAT 2016 | 27 von 58 | 46,6 % |
| BV6 2016 | 10 von 61 | 16,4 % |

Sonst nirgends; ab 2017 sind es 2 bis 3 % je Jahr, in der Hauptperiode 1,7 % (fast alle „passieren
lassen" bei Haushaltsanträgen). Dass eine Bezirksvertretung zwei Jahre lang **jeden** Antrag nur zur
Kenntnis nimmt, ist kein Verhalten, sondern ein Eintrag; dieselbe Spur zeigen die Verwaltungsvorlagen
2014 bis 2019 (38,0 % `erledigt`, 2014 bis 2016 die Hälfte). Die Kodierer können das nicht sehen — sie
sehen denselben Eintrag (§ 4). Stufe 2 markiert solche Zellen (§ 6, Frage 9.2).

**Vorlagen der Verwaltung und Anfragen**, dieselbe Abbildung, beschreibend (nicht validiert):

| | 2014-2020 | 2020-2025 | 2025- |
|---|---|---|---|
| Vorlagen | beschlossen 54,1 %, erledigt 38,0 %, geändert 1,5 %, ohne Ergebnis 3,8 % | beschlossen 89,1 %, geändert 5,6 %, abgelehnt 1,2 %, ohne Ergebnis 1,1 % | beschlossen 91,6 %, geändert 4,8 %, abgelehnt 1,5 % |
| Anfragen | erledigt 88,1 %, ohne Ergebnis 5,6 % | erledigt 94,1 %, ohne Ergebnis 3,4 % | erledigt 90,6 %, ohne Ergebnis 3,5 % |

### 3.5 Abdeckung je Gremium und je Fraktion

Anträge mit Ergebnis (Klasse außer `ohne_ergebnis`) und abschließend, je Gremienart der Drucksache:

| Gremienart | 2014-2020 | 2020-2025 | 2025- |
|---|---|---|---|
| Bezirksvertretung | 93,8 / 93,4 % (n 1 914) | 99,4 / 99,1 % (n 3 090) | 99,3 / 98,5 % (n 543) |
| Ausschuss | 93,2 / 90,3 % (n 691) | 98,4 / 96,3 % (n 755) | 100 / 100 % (n 111) |
| Rat | 92,1 / 89,6 % (n 366) | **78,9 / 77,6 %** (n 1 067) | 96,4 / 96,0 % (n 253) |
| Beirat | 93,9 / 93,3 % (n 164) | 81,8 / 80,7 % (n 187) | 100 / 100 % (n 21) |

Der Rat der Hauptperiode liegt unter 80 % allein wegen der Haushaltssitzung von 2021 (§ 3.3); ohne sie
läge er bei 92,3 % (842 von 912). Gremien mit dem niedrigsten Anteil (Hauptperiode, mindestens 50
Anträge): JURAT 74,2 % (128), RAT 78,9 % (1 067), KUA 96,2 %, BV7 97,7 %; BV2, BV4, BV6, BV10 und AWM
100 %.

Je Fraktion (Antragsteller nach Vorhaben 15; ein gemeinsamer Antrag zählt für jede; Hauptperiode),
mit Ergebnis: CDU 96,2 % (1 514), Grüne 95,6 % (1 492), SPD/Volt 97,0 % (1 192), FDP 95,0 % (519),
Linke 93,1 % (466), PARTEI 87,7 % (195), **Tierschutz/Freie Wähler 51,0 % (145)**, AfD 92,6 % (54). Die
Ratsgruppe Tierschutz/FW hat fast die Hälfte ihrer Anträge (70 von 145) als Haushaltsanträge in der
Sitzung vom 2021-02-05 gestellt; ihre Quote ohne Ergebnis ist ein Loch im Eintrag, kein Verhalten. In
derselben Sitzung fehlen auch 45 Anträge der CDU, 45 der Grünen, 13 der Linken und 11 von SPD/Volt. Für den Erfolg
je Fraktion (§ 3.10) heißt das: Anträge ohne Ergebnis fallen heraus, und bei Tierschutz/FW ist das die
Hälfte.

### 3.6 Dauer bis zur Entscheidung

Tage vom Datum des Antrags bis zur Sitzung des maßgeblichen Tagesordnungspunkts, alle drei Perioden
(140 Anträge mit einer Sitzung vor dem Datum der Drucksache gezählt, nicht verwendet):

| | n | Median | Q1 | Q3 | P90 |
|---|---|---|---|---|---|
| alle mit maßgeblichem Punkt | 8 575 | **14** | 9 | 15 | 35 |
| beschlossen | 4 643 | 14 | 11 | 15 | 24 |
| geändert | 973 | 14 | 13 | 15 | 35 |
| abgelehnt | 1 739 | 10 | 5 | 14 | 42 |
| zurückgezogen | 708 | 14 | 13 | 18 | 62 |
| abschließend, Bezirksvertretung | 5 347 | 14 | 13 | 15 | 24 |
| abschließend, Ausschuss | 1 389 | 10 | 1 | 14 | 24 |
| abschließend, Rat | 1 377 | 9 | 6 | 20 | 78 |
| mehr als eine Beratung | 258 | 45,5 | 13 | 79 | 100 |

Ein Antrag wird meist in der nächsten Sitzung entschieden; die Dauer trennt kaum etwas außer der Zahl
der Beratungen. Längste: `BV6/125/2021`, `BV6/136/2021`, `BV6/138/2021` mit 266 Tagen. Als Kennzahl
für die Seite taugt sie nur für Anträge mit mehr als einer Beratung (verwiesen, vertagt, vorberaten).

### 3.7 Prüfaufträge und Folgevorlagen (mit Vorhaben 14)

*Nach der Kodierung gilt Rückfall 1 (§ 4.1, § 5): die Zahlen zum Prüfauftrag in diesem Abschnitt sind
beschreibend und kommen nicht auf die Seite; die Folgevorlagen je Klasse gelten weiter.*

Eine Folgevorlage ist eine Drucksache der Verwaltung (Vorlage, Information, Bedarfs- oder A+F-Beschluss),
die den Antrag über eine **starke** Kante von 14 nennt (Titel, Anlage, Nachtrag, Sammelbericht; 3 563
Kanten). Das ist eine Untergrenze: Antworten in der Sitzung oder in einer Mitteilung ohne Nummer im Titel
sieht sie nicht.

| Klasse | mit Folgevorlage |
|---|---|
| beschlossen | 1 135 von 4 701 (24,1 %) |
| geändert | 290 von 982 (29,5 %) |
| **abgelehnt** | **1 von 1 784 (0,1 %)** |
| zurückgezogen | 3 von 715 (0,4 %) |
| erledigt | 55 von 444 (12,4 %) |
| vertagt, offen | 1 von 89 |
| ohne Ergebnis | 23 von 510 (4,5 %) |

Das ist eine Gegenprobe der Klassen aus den Daten selbst (Prüfreihenfolge 2, Plan § 2.6): eine
Verwaltung setzt keine abgelehnten Anträge um, und die Daten zeigen es. Die 55 `erledigt` mit
Folgevorlage hängen alle an einer Kante `kontrolle` (Sammelbericht): 41 tragen „passieren lassen", 33
sind Haushaltsanträge, die ein Ausschuss an den Rat weitergab und die danach in einer Sammelvorlage zu
den Haushaltsberatungen stehen. Für Haushaltsanträge ist „passieren lassen" also kein Ergebnis, sondern
der Weg in die Haushaltssitzung, deren Entscheidung je Antrag nicht eingetragen ist (§ 3.3).

**Prüfaufträge**: angenommen mit Prüfauftrag 1 254, mit Folgevorlage 428 (34,1 %; über irgendeine Kante,
auch schwache Textverweise, 47,8 %); Sachbeschlüsse 22,5 % (38,2 %). Tage vom Beschluss bis zur ersten
Folgevorlage: n 428, Median 88, Q1 44, Q3 173, P90 317. Je Gremienart (alle Perioden): Bezirksvertretung
24,0 % der angenommenen sind Prüfaufträge, davon 38,3 % mit Folgevorlage; Ausschuss 22,6 % / 13,4 %;
Rat 7,9 % / **0 %**; Beirat 10,5 % / 25,0 %. Ob ein Prüfauftrag mit einer Vorlage beantwortet wird,
ist also wie bei den Anfragen (14 § 3.8) eine Praxis des Gremiums.

**Ohne Folgevorlage und älter als P90 (315 Tage)**: 292 (2014-2020), 444 (Hauptperiode), 17 (laufende
Periode). Das sind **Kandidaten**, nicht offene Prüfaufträge: die Folgevorlage ist eine Untergrenze, und
im Rat gibt es sie nie. Älteste der Hauptperiode: `APS/119/2020`, `BV5/136/2020`, `BV2/177/2020`,
`BV1/291/2020`, `BV7/382/2020`, `BV4/096/2020`.

### 3.8 Gegenproben aus den Daten selbst

**1. Folgevorlagen** (§ 3.7): abgelehnt 0,1 %, angenommen 25,1 %.

**2. Änderungsantrag und geänderte Vorlage.** Starke Kante `aenderung` (Antrag → Vorlage) und beide in
derselben Sitzung desselben Gremiums mit Ergebnis (alle drei Perioden):

| Antrag | Vorlage | n |
|---|---|---|
| abgelehnt | unverändert beschlossen | 109 |
| angenommen | unverändert beschlossen | 86 |
| angenommen | abweichend beschlossen | 38 |
| zurückgezogen | unverändert / abweichend beschlossen | 14 / 4 |
| abgelehnt | abweichend beschlossen | 13 |
| übrige | | 7 |

Ein abgelehnter Änderungsantrag lässt die Vorlage zu 88,6 % unverändert — das passt. Ein angenommener
macht sie aber nur zu 29,9 % „abweichend beschlossen" (2014-2020: 6 von 33, Hauptperiode 29 von 81,
laufende 3 von 10; Ergänzungs-, Begleit- und Zusatzanträge nicht deutlich anders als Änderungsanträge,
in der Hauptperiode 12 von 38 gegen 17 von 43). Die
Sitzungsleitung trägt die Annahme der Änderung beim Antrag ein und die Vorlage oft als „beschlossen" in
der geänderten Fassung. Für die **Vorlagen** heißt „beschlossen" darum nicht „unverändert"; für die
**Anträge** selbst ist „abweichend beschlossen" der eigene Eintrag des Antrags. Die Seite sollte
`beschlossen` und `geaendert` als `angenommen` zusammen zeigen und „davon mit Änderungen" nur als
Unterzahl (§ 7, Frage 9.4).

**3. Praxiszellen** (§ 3.4): BV9 2014 und 2015, je 100 % `erledigt`.

### 3.9 Anfragen: was der Tagesordnungspunkt sagt (für Vorhaben 14)

Hauptperiode und laufende Periode, maßgeblicher Wert je Gremienart der Anfrage:

| Gremienart | n | beantwortet | schriftlich beantwortet | zur Kenntnis genommen | kein Ergebnis | übrige |
|---|---|---|---|---|---|---|
| Rat | 857 | 26,5 % | **70,8 %** | – | 0,1 % | zurückgewiesen 2,2 %, zurückgezogen 0,4 % |
| Ausschuss | 1 292 | 30,3 % | 27,1 % | 31,0 % | 10,3 % | 1,3 % |
| Bezirksvertretung | 2 746 | 42,6 % | 24,1 % | 30,0 % | 0,5 % | vertagt 2,1 % |
| Beirat | 137 | 8,0 % | 32,8 % | 5,8 % | 16,1 % | beschlossen 35,7 % |

**Im Rat wird jede Anfrage in der Sitzung beantwortet** (834 von 857 „beantwortet" oder „schriftlich
beantwortet"); 14 fand dort 0,1 % mit Antwortanlage. Damit wird für 14 § 3.8 aus „Kandidat" eine
Aussage: eine Anfrage ohne Antwortanlage, deren Tagesordnungspunkt „beantwortet" trägt, ist beantwortet
(in der Sitzung oder schriftlich zur Niederschrift). Das Datum der Antwort ist dann das Sitzungsdatum.

### 3.10 Erfolg je Fraktion, standardisiert (explorativ)

Nur Anträge mit Sachentscheidung (`angenommen` oder `abgelehnt`), 7 467 in Düsseldorf, angenommen
76,1 %. Erwartet = Summe der Annahmequoten von Gremium der Drucksache und Periode über die Anträge der
Fraktion (§ 3.1). „M" = Ratsmehrheit nach Vorhaben 15 (§ 3.9 dort); in den Bezirksvertretungen ist das
Lager der Ratsmehrheit nur eine Näherung, ihre Mehrheiten stehen nicht im Datensatz.

| Fraktion | 2014-2020: n, roh, beob/erw | 2020-2025 | 2025- |
|---|---|---|---|
| CDU | 793, 74,8 %, 0,94 | 1 373, 96,4 %, **1,23** M | 222, 97,7 %, 1,20 M |
| Grüne | 572, 96,5 %, 1,30 M | 1 338, 93,6 %, **1,23** M | 191, 95,3 %, 1,22 M |
| SPD (ab 2020 SPD/Volt) | 591, 99,5 %, 1,28 M | 1 012, 77,8 %, 1,00 | 181, 73,5 %, 1,03 |
| FDP | 476, 98,3 %, 1,33 M | 436, 68,3 %, 0,97 | 75, 48,0 %, 0,95 |
| Linke | 144, 43,8 %, 0,71 | 360, 20,6 %, 0,45 | 86, 25,6 %, 0,76 |
| PARTEI | – | 127, 22,8 %, 0,59 | (mit T/FW) |
| Tierschutz/FW (ab 2025 mit PARTEI) | – | 71, 0 %, 0,00 | 77, 0 %, 0,00 |
| AfD | – | 46, 0 %, 0,00 | 88, 0 %, 0,00 |

Je Gremienart, Mehrheitsfraktionen gegen übrige Fraktionen:

| Periode | Rat | Ausschuss | Bezirksvertretung |
|---|---|---|---|
| 2014-2020 | 95,6 % (206) / 31,7 % (123) | 99,5 % (568) / 41,2 % (279) | 97,6 % (797) / 92,8 % (525) |
| 2020-2025 | **98,3 % (417) / 18,7 % (611)** | 99,2 % (384) / 27,1 % (413) | **93,4 % (1 885) / 93,9 % (1 014)** |
| 2025- | 100 % (37) / 0,5 % (208) | 100 % (36) / 9,9 % (81) | 95,9 % (338) / 83,4 % (217) |

Was das zeigt und was nicht: Die Standardisierung nach Gremium nimmt den Unterschied zwischen Rat und
Bezirksvertretung heraus, nicht den zwischen Mehrheit und Opposition — der ist im Rat das Ergebnis selbst.
Dass eine Fraktion „erfolgreich" ist, heißt im Rat fast nur, dass sie zur Mehrheit gehört; in den
Bezirksvertretungen werden die Anträge aller Fraktionen gleich oft angenommen. Die Nullen der AfD und von
Tierschutz/FW sind Zählungen (46 und 71 Anträge, fast alle im Rat), keine Schätzung; ob andere ihnen
zugestimmt haben, sagt das Ergebnis nicht (Vorhaben 28). Bei Tierschutz/FW fehlt zudem die Hälfte der
Anträge (§ 3.5). Ausweis auf der Seite nur so: standardisiert, nach Gremienart getrennt, mit n,
„explorativ" überschrieben, ohne Rangfolge (Frage 9.5).

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

**Was schon deterministisch geprüft ist** (Prüfreihenfolge 1 und 2, Plan § 2.6): jeder Wert von
`result` hat eine Klasse, ein unbekannter bricht ab; jede Beratung eines Antrags findet ihren
Tagesordnungspunkt (100 %); die Folgevorlagen trennen angenommen und abgelehnt (25,1 % gegen 0,1 %,
§ 3.7); die Änderungsanträge passen zu ihren Vorlagen, wo abgelehnt (88,6 %). **Was es nicht prüft**: ob
die Regel aus einer Folge mit mehreren Beratungen die richtige Station wählt, ob ein
Tagesordnungspunkt wirklich diesen Antrag behandelt, und ob ein angenommener Antrag nur ein Prüfauftrag
ist. Das prüfen die Kodier-Agenten. **Was niemand hier prüft**: ob der Eintrag der Sitzungsleitung
stimmt. Das zeigte nur die Niederschrift; die Praxiszellen (§ 3.4) und die Vorlagen (§ 3.8) sind die
bekannten Fälle, in denen er es nicht tut (Frage 9.1).

**Codebuch** `validierung/26-beschluesse/codebuch.toml` (Fassung 1, F4-Format, geprüft mit
`load_codebook`). Einheit: ein Antrag. Zwei Fragen:

1. `ergebnis` (nominal): die acht Klassen aus § 3.1 und `unklar` (nur bei widersprüchlicher Folge; fällt
   aus dem Nenner). Der Grundsatz „letzte Entscheidung in der Sache" steht im Codebuch mit Bedeutung
   jedes Werts; dazu die Anweisung, Zeilen wegzulassen, deren Tagesordnungspunkt erkennbar eine andere
   Sache behandelt.
2. `auftrag` (nominal, nur wenn `ergebnis` `beschlossen` oder `geaendert`): `pruefauftrag`,
   `sachbeschluss`, `unklar`; mit den Grenzfällen (Maßnahme unter Vorbehalt der Prüfung = Prüfauftrag;
   Maßnahme mit Bericht = Sachbeschluss; Mittel für eine Untersuchung = Sachbeschluss; Bericht Dritter auf
   Einladung = Prüfauftrag).

**Stichprobe** `validierung/26-beschluesse/stichprobe.csv` (`id`, `schicht`, `schicht_n`) und
`stichprobe.json` (Prüfsumme der Grundgesamtheit
`messdaten/26-beschluesse/grundgesamtheit.parquet`): 150 Anträge, Seed 26, Aufteilung aus § 3.1 (alle
Schichten groß genug). Aus der Hauptperiode 91, aus 2014-2020 42, aus der laufenden Periode 17.

| Schicht | Anträge in der Schicht (drei Perioden) | gezogen |
|---|---|---|
| beschlossen (Sachbeschluss) | 3 668 | 25 |
| geaendert (Sachbeschluss) | 761 | 20 |
| pruefauftrag (angenommen) | 1 254 | 20 |
| abgelehnt | 1 784 | 20 |
| zurueckgezogen | 715 | 15 |
| erledigt | 444 | 15 |
| vertagt | 65 | 15 |
| offen | 24 | 10 |
| ohne_ergebnis | 510 | 10 |

**Kodieraufträge** (nicht im Repo), im Format von F4, je Kodierer ein Ordner mit `auftrag.jsonl`,
`antworten.jsonl` (leer) und `codebuch.md`:
`/media/konrad/xtraspace/georep/messdaten/kodierung/26-beschluesse/A/` und `…/B/`, je 150 Zeilen, 1,04
MB, in verschiedener Folge. Je Zeile `dokumente` (Titel, Drucksache, Datum, Dokumentart, `ausschnitt`
= höchstens 2 500 Zeichen Rohtext; einer aus dem kleingeschriebenen Korpus, `textquelle` = "klein") und
`beratungsfolge` (je Tagesordnungspunkt Gremium, Rolle, Sitzung, Nummer, Bezeichnung, Ergebnis; Beratungen
ohne Punkt mit `hinweis`). **Nicht** im Auftrag: Klasse, Schicht, Prüfauftrag der Regel. Ein Probelauf
mit erfundenen Antworten in einem Ordner im Scratchpad bestätigt, dass `georep validate merge` die
Ordner liest, die Schlichtung baut und `labels.csv` schreibt, und dass `--auswertung` daraus die drei
Stufen rechnet.

**Ablauf für den Supervisor** (`settings.local.toml` des Worktrees nennt
`validation.coding_root = "/media/konrad/xtraspace/georep/messdaten/kodierung"`):

```bash
# 1. zwei Kodier-Agenten nach docs/validierung.md § 4.1, Ordner …/26-beschluesse/A und …/B, alle 150 Zeilen
uv run georep validate merge 26-beschluesse --model claude-opus-5-5   # 2. Schlichtungsauftrag
# 3. Schlicht-Agent nach § 4.2, Ordner …/26-beschluesse/schlichtung
uv run georep validate merge 26-beschluesse --model claude-opus-5-5   # 4. labels.csv, README.md, guete.json
uv run python docs/plans/26-beschluesse-messung.py --auswertung       # 5. Präzision in drei Stufen, Urteil
```

**Maße** (§ 3.1): richtig, wenn `ergebnis` gleich und, bei angenommen, `auftrag` gleich; ungewichtet an
den gewerteten Einheiten mit Wilson-95-%-Intervall und gewichtet mit den Schichtgrößen (Σ W_h·p_h,
Wilson bei Kishs n_eff, wie F4); in drei Stufen (voll, Rückfall 1, Rückfall 2); je Schicht; α je Frage
aus `georep validate merge`. Bei 150 gewerteten Einheiten liegt der Punktwert bei höchstens sieben
Fehlern bei mindestens 0,953. Erwartung, ausdrücklich keine Messung: `ergebnis` ist eine Abbildung eines
festen Wortschatzes und sollte fast fehlerfrei sein; `auftrag` ist eine Heuristik über den Beschlusstext
(beim Entwickeln gesehene Fehler: Passiv ohne Liste, gemischte Sätze, Mittel für eine Untersuchung) und
das Risiko. Verfehlt sie, greift Rückfall 1, wie vorab festgelegt. (So geschrieben vor der Kodierung.)

### 4.1 Ergebnis der Kodierung (2026-11-24)

Zwei Kodier-Agenten (Opus, `claude-opus-5-5`) haben die 150 Anträge unabhängig nach Codebuch 1 kodiert;
`georep validate merge` fand keine Uneinigkeit, eine Schlichtung war nicht nötig. Labels:
`validierung/26-beschluesse/labels.csv`, Übereinstimmung und Satz für die Seite: `README.md`,
`guete.json`. Ausgewertet mit `26-beschluesse-messung.py --auswertung` um 01:16 Uhr (20,5 s, Lastmittel
20 → 17), nach der Regel aus § 3.1, ohne sie an die Labels anzupassen.

| Frage | gestellt | gleich | κ | α |
|---|---|---|---|---|
| `ergebnis` | 150 | 150 (100 %) | 1,000 | 1,000 |
| `auftrag` | 65 | 65 (100 %) | 1,000 | 1,000 |

Kein Label `unklar` (Grenze 15).

| Stufe (§ 3.1) | ungewichtet | Wilson 95 % | gewichtet | Intervall (n_eff 96,9) | Kriterium |
|---|---|---|---|---|---|
| voll (`ergebnis` und `auftrag`) | 142 / 150 = 0,947 | 0,898–0,973 | 0,894 | 0,817–0,941 | **verfehlt** |
| Rückfall 1 (`ergebnis`) | 150 / 150 = 1,000 | 0,975–1,000 | 1,000 | 0,962–1,000 | **erfüllt** |
| Rückfall 2 (grobe Klassen) | 150 / 150 = 1,000 | 0,975–1,000 | 1,000 | 0,962–1,000 | erfüllt |

Je Schicht, volle Klasse: beschlossen 19 / 25, geaendert 19 / 20, pruefauftrag 19 / 20, alle übrigen voll.
Nach Rückfall 1 ist jede Klasse voll richtig (beschlossen 42 / 42, geaendert 23 / 23, abgelehnt 20 / 20,
zurueckgezogen, erledigt, vertagt je 15 / 15, offen und ohne_ergebnis je 10 / 10); die Zusatzregel
(Klasse unter 0,80) trifft keine. Gewichtet liegt die volle Klasse unter der ungewichteten, weil die
große Schicht `beschlossen` (3 668 Anträge) sechs der acht Fehler trägt.

**Die acht Fehler liegen alle beim Prüfauftrag.** Regel gegen Label:

| | Label Prüfauftrag | Label Sachbeschluss |
|---|---|---|
| Regel Prüfauftrag | 19 | 1 (`BV1/009/2022`) |
| Regel Sachbeschluss | 7 | 38 |

57 / 65 richtig (0,877, Wilson 0,775–0,936). Was die Regel Prüfauftrag nennt, stimmt zu 19 / 20
(0,95); sie findet aber nur 19 der 26 Prüfaufträge (Recall 0,731, Wilson 0,539–0,863): `BV5/053/2024`,
`JURAT/032/2024`, `BV5/077/2025`, `BV1/111/2025`, `176/ 85/2016`, `BV8/190/2022`, `BV1/188/2022`. Die
Anteile der Prüfaufträge in § 3.4 und § 3.7 sind darum Untergrenzen.

**Was die Fälle verlangten** (ein Fall kann mehrere Merkmale tragen):

| Merkmal | Fälle | `ergebnis` richtig |
|---|---|---|
| mechanisch: ein einziger Eintrag oder keiner, nach der Tabelle in § 3.1 | 69 | 69 |
| Prüfauftrag zu beurteilen (angenommen) | 65 | 65 (`auftrag` 57) |
| Folge mit Entscheidung über mehrere Einträge | **17** | 17 |
| … darin Verweisung | 13 | 13 |
| … mehrere Beratungen | 9 | 9 |
| … mindestens zwei Einträge mit Ergebnis | 7 | 7 |
| … Vertagung mit späterem Eintrag | 3 | 3 |
| … maßgeblich ist nicht der letzte Eintrag | 1 | 1 |
| … Empfehlung eines vorberatenden Gremiums | 1 | 1 |

81 Fälle verlangten mehr als das Nachschlagen eines Eintrags: 65 den Prüfauftrag, 17 eine Folge (einer
beides). Für die Frage, die über den Wortschatz hinausgeht, stehen damit 17 / 17 (Wilson 0,816–1,000),
nicht 150 / 150.

**Wie viel das belegt.** Wenig über die Schärfe der Klassen hinaus. Die Klassen folgen fast mechanisch
aus `result`; zwei Kodierer desselben Modells, die dieselbe Tabelle im Codebuch lesen, müssen sich dort
einig sein, und ihre Einigkeit zeigt vor allem, dass Codebuch und Regel dieselbe Abbildung beschreiben
(Frage 19 des Supervisors: Kodierer B ein anderes Modell). Was die Kodierung tatsächlich prüft: dass die
Verbindung Antrag → Beratung → Tagesordnungspunkt in keinem der 150 Fälle einen fremden Punkt
erwischt, dass der Grundsatz „letzte Entscheidung in der Sache" an 17 Folgen so gelesen wird wie
verabredet, und dass der Prüfauftrag eine echte Lesefrage ist, an der die Regel scheitert. Was sie nicht
prüft: ob der Eintrag der Sitzungsleitung stimmt (§ 3.4 Praxiszellen, § 3.8, Frage 9.1).

**Lücken, die die Kodierer nennen** (Rückmeldung an den Supervisor; nicht angewandt, Codebuch 1 bleibt):
Planung mit Bürgerdialog für eine festgelegte Maßnahme; Machbarkeitsstudie als Mittelvergabe;
Verfahrensbeteiligung als Maßnahme; „Vorarbeiten durchführen"; mehrstufige Beratung mit „passieren
lassen"; Gremienkürzel `gr/400224` und `gr/65` ohne Namen; Verweisung ohne Zeile des Zielgremiums
(Fragen 9.12 bis 9.18).

## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

**Kriterium** (Briefing, unverändert; Auslegung vorab in § 3.1): Präzision ≥ 0,95 an 150, Ergebnis für
mindestens 80 % der Anträge.

- **Ergebnis für mindestens 80 % der Anträge: erfüllt.** Hauptperiode 94,3 % (4 810 von 5 099),
  abschließend 93,5 %; 2014-2020 93,5 %, laufende Periode 98,6 %. Unsicherheit: keine aus Stichproben
  (Vollerhebung), aber eine aus dem Eintrag: im Rat der Hauptperiode sind es 78,9 % wegen einer
  einzigen Sitzung, und in den Praxiszellen (BV9 2014 bis 2016, Rat 2016) ist bei 240 Anträgen ein
  Ergebnis eingetragen, das keines ist. Zählt man diese als ohne Ergebnis, bleibt 2014-2020 bei 86,0 %
  (2 750 von 3 198).
- **Präzision an 150: erfüllt in Rückfall 1, verfehlt in der vollen Klasse** (§ 4.1). Volle Klasse
  142 / 150 = 0,947 (Wilson 0,898–0,973), gewichtet 0,894 (0,817–0,941): beide unter 0,95. `ergebnis`
  allein 150 / 150 = 1,000 (Wilson 0,975–1,000), gewichtet 1,000 (0,962–1,000): beide ≥ 0,95. Keine
  Klasse unter 0,80. α 1,0 bei beiden Fragen (Stufe 3 verlangt 0,8).

**Urteil (2026-11-24, nach der Kodierung): bauen, mit Rückfall 1** — so, wie § 3.1 es vor der Kodierung
festlegt: die acht Klassen von `ergebnis` gelten; der Prüfauftrag kommt nicht als Klasse auf die Seite,
„offene Prüfaufträge" entfallen, der beantragte Prüfauftrag bleibt eine beschreibende Spalte ohne
Anzeige. Unsicherheit: der Punktwert 1,000 ruht für den Teil, der über den Wortschatz hinausgeht, auf 17
Fällen (untere Grenze 0,816), und die Kodierer sind dasselbe Modell wie der Agent, der die Regel schrieb (§ 4.1). Eine
Fassung .2 des Prüfauftrags wäre ein eigenes Vorhaben mit neuer Stichprobe (Frage 9.8), keine Runde
dieser Stufe 1. Dazu drei Änderungen am Briefing, die nicht an der Kodierung hängen:

1. **Angenommen statt beschlossen/geändert auf der Seite.** Die Unterscheidung ist ein Eintrag der
   Sitzungsleitung, der bei Vorlagen nachweislich uneinheitlich ist (§ 3.8); sie bleibt in den Daten,
   die Seite zeigt sie als Unterzahl.
2. **Praxiszellen werden markiert.** In einem Gremium-Jahr, in dem mindestens 40 % der Anträge mit
   Ergebnis `erledigt` sind (BV9 2014 und 2015 je 100 %, BV9 2016 48,6 %, Rat 2016 46,6 %; die nächste
   Zelle, BV6 2016, hat 16,4 %, alle übrigen ab 2017 höchstens 3 %), gilt `erledigt` als
   `eintrag_tragfaehig = false` (240 Anträge); diese zählen weder im Erfolg noch in den Klassenanteilen,
   und die Seite sagt warum (Frage 9.2; als Regel neu und nach dem Blick auf die Daten gesetzt, also eine
   Variante, die die Kodierung nicht misst).
3. **Erfolg je Fraktion nur standardisiert, getrennt nach Gremienart, explorativ** (§ 3.10, Frage 14
   des Supervisors). Keine rohe Quote, keine Rangfolge.

(Die vierte Änderung der vorläufigen Fassung, „offene Prüfaufträge nur als Kandidaten", entfällt mit
Rückfall 1.)

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

**Eingaben.** Die drei Dateien des Netzlaufs je Profil über `council_files(layout)` (Modelle aus
`georep.oparl`, nie `.get()`-Ketten); Korpus, `papers_gremien`, `dokumente_urheber`; aus Vorhaben 15 die
Antragsteller (`processed/dokumente_funktion.parquet`, sobald gemerged; bis dahin die Regel aus seinem
Messskript); aus Vorhaben 14 `processed/vorgang_kanten.parquet` (nur starke Kanten). Für Pages, das kein
Netz hat: ein **Paket** der Tabelle „Paper × Tagesordnungspunkt" (unten, 649 KB für drei Perioden;
Frage 9.7), gepackt mit `georep pack --outcomes` nach `snapshots/duesseldorf-beschluesse/raw/` mit README
und Prüfsumme wie Punkt 58; `bootstrap` kopiert es nach `raw/`.

**Beitrag `outcomes`** nach F2 (`georep/enrich/outcomes.py`), offline, nach `procedures` (14) und
`functions` (15), zwei Schritte:

1. `council_results`: aus den Netzlauf-Dateien (oder dem Paket) die Folge je Drucksache →
   `processed/beratungsfolge.parquet`.
2. `outcomes`: Klasse, Dauer, Folgevorlage, Praxiszellen, dazu der beantragte Prüfauftrag als Spalte
   ohne Anzeige (Rückfall 1) → `processed/beschlusslage.parquet` und `processed/antragserfolg.parquet`.

**Ausgaben** (Schema-Version aus der Modulkonstante `OUTCOMES_SCHEMA_VERSION = 1`):

| Datei | Spalten | Schlüssel, Ordnung |
|---|---|---|
| `beratungsfolge.parquet` | `id` str, `beratung` str, `top` str, `gremium` str, `rolle` str, `sitzung` date, `nummer` str, `ordnung` i32, `result` str (null erlaubt), `stufe` str (`sache`, `stand`, null) | eindeutig (`id`, `top`), sortiert nach `id`, `sitzung`, `ordnung`, `top` |
| `beschlusslage.parquet` | `id` str, `rolle` str (14), `klasse` str (acht Klassen), `grob` str, `result` str, `entscheidung_top` str, `entscheidung_gremium` str, `entscheidung_datum` date, `tage` i32, `beratungen` i16, `pruefauftrag_beantragt` bool (nur Anträge, sonst null; Rückfall 1: beschreibend, nicht auf der Seite, Recall 0,73), `folgevorlage` str (erste starke, sonst null), `eintrag_tragfaehig` bool | eine Zeile je Korpus-ID, sortiert nach `id` |
| `antragserfolg.parquet` | `periode` str, `gremium_art` str, `fraktion` str, `n` i32, `angenommen` i32, `erwartet` f64, `beob_erw` f64 | eindeutig (`periode`, `gremium_art`, `fraktion`), sortiert danach |

**Die Regel** (Messskript, Commit `94da91f`, vor dem Rebase `e2b3545`, unverändert übernehmen; § 3.1):
letzte Entscheidung in der Sache, sonst letzter Stand, sonst `ohne_ergebnis`; der Prüfauftrag wie
`pruefauftrag()` im Skript, nach Rückfall 1 nur als Spalte ohne Anzeige. `klasse` ist eine **Funktion der Folge**, unabhängig von der
Zeilenfolge der Eingabe.

**Verträge** (Batch-Grenzen, Prädikate in `georep.contracts`): `klasse` aus der Aufzählung; genau eine
Zeile je Korpus-ID; `entscheidung_top` null genau bei `ohne_ergebnis`; jeder `entscheidung_top` ist ein
`top` derselben `id` in `beratungsfolge`; `tage >= 0` oder null; `pruefauftrag_beantragt` null außer bei Rolle
`antrag` und Klasse `beschlossen`/`geaendert`; jeder `result` im Wortschatz des Profils, sonst
`SchemaError` mit dem Wert; nach jedem Join sortieren; `n >= angenommen >= 0` in `antragserfolg`.

**Settings** (Anhängeregel aus F2: Modell `Outcomes` vor `class Settings`, Feld am Ende, Block am Ende von
`defaults.toml` mit `# --- Vorhaben 26: Beschlusslage`, Schalter aus):

```toml
[outcomes]                       # Vorhaben 26; der Wortschatz steht im Stadtprofil, kein Stadtwort im Code
enabled = false
practice_share = 0.4             # Gremium-Jahr mit mindestens diesem Anteil "erledigt" unter den Anträgen: dort ist "erledigt" kein Ergebnis (§ 3.4, § 5)
practice_min = 10                # und mindestens so viele "erledigt" (sonst träfe es AGS 2024 mit fünf Anträgen)
followup_roles = ["vorlage", "information", "bedarf", "af"]   # Rollen (14), die als Folgevorlage zählen
# Prüfauftrag: Muster der deutschen Sprache, keine Stadt (Marker, Prüfwörter, Maßnahmen, Vorbehalt; § 3.1)
[outcomes.results]               # Stadtprofil: Wert von result -> [stufe, klasse]; ein fehlender Wert ist ein Fehler
```

Düsseldorf trägt die 21 Werte aus § 3.1 (`"einstimmig beschlossen" = ["sache", "beschlossen"]` …).
Mönchengladbach liegt auf demselben Server (Body 0011); ob es denselben Wortschatz hat, zeigt sein
Netzlauf, und ein fremder Wert bricht ab, statt still `ohne_ergebnis` zu werden.

**Tests.** Beispiele für die Regel: vertagt, dann beschlossen → beschlossen; verwiesen, dann
zurückgezogen → zurueckgezogen; Empfehlung beschlossen, dann im Ausschuss abgelehnt → abgelehnt;
beschlossen, danach zur Kenntnis genommen in einem anderen Gremium → beschlossen; nur vertagt → vertagt;
nur Punkte ohne Ergebnis → ohne_ergebnis; gleiche Sitzung, verschiedene `order`. Der Prüfauftrag an den
Beispielen des Codebuchs und den acht Fehlern aus der Kodierung (§ 4.1) als dokumentierte Grenze. **hypothesis**: die
Klasse ist unabhängig von der Reihenfolge der Eingabe; ein angehängter späterer Schritt der Stufe `sache`
bestimmt die Klasse; ein angehängter späterer Schritt der Stufe `stand` ändert eine Klasse aus `sache`
nie; die Praxiszellen hängen nur von Gremium, Jahr und Klasse ab. Mini-Fixture: ein Dutzend Paper mit
Sitzungen, Punkten und Beratungen als JSONL unter `tests/fixtures/council/` (geschwärzt wie F6).
**slow**, Golden auf der Hauptperiode: 5 099 Anträge, 4 810 mit Ergebnis, die Klassenzahlen aus § 3.4,
155 ohne Ergebnis in der Sitzung vom 2021-02-05. Kein Netz, kein Modell.

**Berührte Dateien.** Neu: `src/georep/enrich/outcomes.py`, `src/georep/analysis/outcomes.py` (Regel,
Prüfauftrag, Erfolg), `tests/unit/test_outcomes.py`, `tests/property/test_outcomes.py`,
`tests/golden/test_outcomes.py`, `tests/fixtures/council/`. Geändert mit einer angehängten Zeile oder einem
Block: `src/georep/enrich/__init__.py`, `src/georep/settings.py`, `src/georep/defaults.toml`,
`src/georep/profiles/duesseldorf.toml` (Wortschatz), `src/georep/pack.py` (`--outcomes`),
`src/georep/bootstrap.py`, `docs/architecture.md`, `docs/decisions.md` (Punkt ohne Nummer: „die letzte
Entscheidung in der Sache", „Prüfauftrag nach der Kodierung nicht auf der Seite (Rückfall 1, Recall
0,73)", „Praxiszellen", „angenommen statt beschlossen/geändert auf der Seite"). Die Kürzel `gr/400224`
und `gr/65` (Frage 9.17) gehören vor Stufe 3 in `[bodies.organizations]`, mit Beleg.

**Laufzeit**: das Messskript braucht für drei Perioden 15 s, davon 8 s Laden der JSONL-Dateien über
pydantic; der Schritt sollte unter 10 s je Profil bleiben.

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

**Erweitert `vorgaenge.html`** (14) um drei Abschnitte, je Profil mit Netzlauf; dafür braucht F2
Abschnitte aus fremden Beiträgen (Synergie § 3.1, „später"):

1. *Beschlusslage je Gremium*: Anträge, Anteil angenommen (davon mit Änderungen), abgelehnt,
   zurückgezogen, ohne Abstimmung erledigt, offen, ohne Ergebnis; Median der Dauer bei mehr als einer
   Beratung. Darüber ein Satz, was „ohne Ergebnis" heißt (Sitzung ohne Eintrag, Beispiel Haushaltssitzung
   2021), und die Praxiszellen als Fußnote.
2. *Erfolg je Fraktion, explorativ*: beobachtet/erwartet und n, getrennt nach Rat und Ausschüssen und
   nach Bezirksvertretungen, ohne Rangfolge; der Satz, dass im Rat Erfolg fast nur Mehrheit heißt.
3. *Anfragen*: „in der Sitzung beantwortet" je Gremium neben 14s Antwortanlagen; für den Rat ersetzt
   das den Hinweis „Antworten stehen in der Niederschrift".

Kein Abschnitt zu Prüfaufträgen (Rückfall 1). Größe geschätzt unter 30 KB (drei Tabellen). **Im Dokumentdialog** an 14s Haken: je Antrag Klasse,
Gremium und Datum der Entscheidung, nachgeladen in `beschluesse.json` (rund 9 200 Anträge × rund 30 Bytes,
unter 300 KB) statt einer Erweiterung von `dokumente.json`. **Tabellen im Register**: `beschlusslage`,
`antragserfolg`, `beratungsfolge` als Parquet und CSV. **Validierung auf der Seite**: „Beschlusslage aus
dem Eintrag der Sitzungsleitung im Ratsinformationssystem; die Zuordnung zu Klassen an 150 Anträgen von
zwei KI-Kodierern desselben Modells geprüft, nicht von Menschen (150 von 150 gleich; nur 17 Fälle
verlangten mehr als das Nachschlagen eines Eintrags); ob der Eintrag stimmt, zeigt nur die
Niederschrift".

## 8. Vorab festgelegte Hypothesen (nur Analysen: Hypothese, Maß, Test, Schwelle)

Keine. Vorhaben 26 ist beschreibend; der Erfolg je Fraktion ist **explorativ** (§ 3.1, § 3.10). Wer
daraus eine These macht (etwa: die Opposition hat in Bezirksvertretungen dieselbe Chance wie die
Mehrheit, im Rat keine), legt sie in Vorhaben 28 vorab fest, mit den Abstimmungen statt des Ergebnisses
als Maß, und dort mit der Schwelle der WZB-Studien für die AfD.

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 9.1 | Stimmt der Eintrag `result` mit der Niederschrift überein? | die Kodierung prüft die Abbildung, nicht den Eintrag; Praxiszellen und Vorlagen (§ 3.4, § 3.8) zeigen, dass er nicht immer trägt | Vorhaben 28 liest ohnehin 50 Niederschriften (Runbook § 7); es vergleicht dabei je Tagesordnungspunkt Niederschrift und `result`. Kein eigener Abruf für 26 |
| 9.2 | Praxiszellen (BV9 2014 bis 2016, Rat 2016) als „Eintrag nicht tragfähig" markieren? | 240 Anträge sind dort `erledigt`; dass eine Bezirksvertretung zwei Jahre jeden Antrag nur zur Kenntnis nimmt, ist ein Eintrag, kein Verhalten | ja, in Stufe 2 mit `practice_share = 0.4`, als Spalte neben der Klasse, nicht an ihrer Stelle; die Schwelle ist nach dem Blick auf die Daten gesetzt (Lücke zwischen 16 % und 47 %) |
| 9.3 | Die Haushaltssitzung 2021-02-05 (155 Anträge ohne Ergebnis) aus der Niederschrift nachtragen? | sie macht den Rat der Hauptperiode unter 80 % und halbiert die Anträge von Tierschutz/FW | nein; die Seite nennt die Sitzung. Ein Nachtrag wäre Text aus einer Niederschrift, also Vorhaben 28 |
| 9.4 | `beschlossen` und `geaendert` auf der Seite getrennt? | Vorlagen tragen „abweichend" nur in 30 % der Fälle mit angenommener Änderung | nein: „angenommen", davon „mit Änderungen" als Unterzahl |
| 9.5 | Erfolg je Fraktion auf der Seite, und wie? | AfD und Tierschutz/FW 0 von 46 und 71; rohe Quoten wären parteipolitisch irreführend | nur beobachtet/erwartet mit n, nach Gremienart getrennt, „explorativ", keine Rangfolge (Annahme zu Frage 14) |
| 9.6 | Gilt der Wortschatz für Mönchengladbach? | derselbe Server (Body 0011), aber andere Sitzungsleitung | Messung nach seinem Netzlauf; ein fremder Wert bricht ab |
| 9.7 | Darf das Paket der Beratungsfolge (649 KB, drei Perioden) ins Repo? | ohne es baut Pages die Abschnitte nicht | ja, unter Frage 18/26 des Supervisors (kleine Pakete ja) |
| 9.8 | Was, wenn der Prüfauftrag die 0,95 verfehlt? | die Regel ist eine Heuristik | **eingetreten** (57 / 65, Recall 0,73, § 4.1): Rückfall 1 wie vorab festgelegt; eine Fassung .2 nur als eigenes Vorhaben mit neuer Stichprobe und anderem Modell für Kodierer B |
| 9.9 | Beschlusslage auch für Vorlagen und Anfragen auf der Seite? | sie ist gerechnet (§ 3.4), aber nicht kodiert | nein, nur Anträge (validiert) und für Anfragen die Zahl „in der Sitzung beantwortet" je Gremium (Wortlaut, keine Klasse) |
| 9.10 | Die Beratungen für 2014-2020 aus der eigenen Datei des Profils statt der Kopie? | sein Abruf lief beim Messen noch | ja in Stufe 2; die Liste ist je Body dieselbe, die Zahlen ändern sich höchstens um Nachträge |
| 9.11 | Die Rolle der Beratung („Entscheidung") für die Regel nutzen? | sie ist zu 69 % „-" | nein; die Regel braucht sie nicht, das Codebuch nennt sie nur |
| 9.12 | Planung mit Bürgerdialog für eine festgelegte Maßnahme: Sachbeschluss oder Prüfauftrag? | Lücke im Codebuch, von den Kodierern genannt | nicht angewandt; nach Rückfall 1 ohne Folge für die Seite; in einer Fassung .2 Sachbeschluss, wenn die Maßnahme selbst festgelegt ist |
| 9.13 | Machbarkeitsstudie als Mittelvergabe? | Grenzfall zwischen „Mittel vergeben" und „untersuchen" | nicht angewandt; Codebuch 1 sagt Sachbeschluss, wenn Haushaltsmittel zugesagt werden |
| 9.14 | Verfahrensbeteiligung (Anhörung, Beteiligung eines Gremiums) als Maßnahme? | Lücke im Codebuch | nicht angewandt; für eine Fassung .2 |
| 9.15 | „Vorarbeiten durchführen": Maßnahme oder Prüfung? | Lücke im Codebuch, auch in der Regel (`durchzuführen` ist neutral) | nicht angewandt; für eine Fassung .2 |
| 9.16 | Mehrstufige Beratung mit „passieren lassen" (Haushaltsanträge) | „passieren lassen" ist dort der Weg in die Haushaltssitzung, kein Ergebnis (§ 3.7) | nicht angewandt; Stufe 2 zeigt solche Anträge als `erledigt` mit Fußnote; eine eigene Klasse „weitergegeben" nur mit neuer Messung |
| 9.17 | Die Kürzel `gr/400224` und `gr/65` fehlen in `[bodies.organizations]` | die Kodierer sahen Rohkürzel; die Seite zeigte sie | vor Stufe 3 mit Beleg ins Profil (`gr/400224`: 260 Punkte in 2020-2025, alle mit Ergebnis; `gr/65`: 346 Punkte in 2014-2020) |
| 9.18 | Verweisung ohne Zeile des Zielgremiums | die Klasse `offen` sagt dann nicht, wohin | nicht angewandt; Stufe 2 nennt das Zielgremium nur, wo eine Beratung es nennt |

## 10. Änderungen durch die Synergie (füllt der Supervisor)

Geschrieben am 2026-11-24 nach dem Urteil (§ 5), vor dem Start der Stufe 2. Die Synergie
([00-synergien-2026-11.md](00-synergien-2026-11.md)) entstand vor dieser Messung; was sie trotzdem
festlegt und was seither auf `main` kam, steht hier und geht dem Bauplan (§ 6) vor.

1. **Name des Beitrags.** `Contribution.name` ist `26-beschluesse` (Synergie § 2.1, Docstring von
   `Contribution`), nicht `outcomes`; Modul und Schrittnamen bleiben englisch (`enrich/outcomes.py`,
   `council_results`, `outcomes`).
2. **Dateiname.** `raw/beratungsfolge.parquet` gibt es schon (Punkt 58: Dokument → beratende Gremien,
   Paket `snapshots/duesseldorf-beratungsfolge/`, gelesen vom Schritt `bodies`). Die Tabelle aus § 6
   heißt darum **`processed/beratungsverlauf.parquet`**; Punkt 58, sein Paket und `pack
   --consultations` bleiben unverändert.
3. **Abhängigkeit von 14.** `rolle` und `folgevorlage` kommen aus Vorhaben 14 (Rollen,
   `vorgang_kanten.parquet`, nur starke Kanten), das in Runde 2 der Stufe 2 steht und vor 26 gemerged
   wird (Synergie § 3.4: 14 ist Zulieferer für 26). Bis dahin baut 26 alles, was nicht an 14 hängt
   (Beratungsverlauf, Regel, Praxiszellen, Paket, Settings, Tests mit einer Rollen-Fixture), und zieht
   die Verdrahtung nach dem Merge von 14 nach; der Supervisor meldet den Merge. Kein Nachbau der Rollen
   aus 14 in 26.
4. **Antragsteller aus 15.** Vorhaben 15 ist gemerged (`v0.24.0`, Punkt 75): Antragsteller aus
   `functions_files(layout)` (`processed/dokumente_antragsteller.parquet`), nicht aus dem Messskript.
5. **Eingaben des Netzlaufs.** Lokal liegen sie unter `data_root/<profil>/raw/` (`council_files`,
   Netzlauf vom 2026-11-23, `docs/runbook-sitzungen.md` § 9); auf Pages und in CI kommt die Tabelle
   „Paper × Tagesordnungspunkt" aus dem Paket `snapshots/duesseldorf-beschluesse/` über `georep pack
   --outcomes`. Das Paket ist klein (rund 0,65 MB für drei Perioden) und fällt unter die Annahme zu
   Frage 26 (kleine Pakete ja); `TOTAL_LIMIT` in `tests/unit/test_data_packages.py` bleibt die Grenze.
   18 und 22 bauen parallel eigene kleine Pakete; Anhängeregel aus Synergie § 2.1 für `pack.py`,
   `bootstrap.py`, `cli.py`, `test_data_packages.py`.
6. **Mönchengladbach.** Der Netzlauf hat es geholt (967 Sitzungen, 25 619 Beratungen). Der Schritt
   läuft dort mit; fehlt ein Wert von `result` im Wortschatz, kommt er mit Zählung und Beleg in
   `profiles/moenchengladbach.toml` (Daten, kein Code). Ist ein Wert nicht eindeutig einer Klasse
   zuzuordnen, bleibt `outcomes.enabled` dort aus, und der Bericht nennt die Werte.
7. **Kürzel aus Frage 9.17** (`gr/400224`, `gr/65`): erst vor Stufe 3, in einem eigenen Commit mit
   A/B-Bau, weil sie die Gremienzuordnung und damit Zahlen der Seite berühren können.
8. **Merge.** Nach 14; Stufe 3 (Abschnitte auf `vorgaenge.html`, Dialog) wartet auf den F2-Nachzug für
   Abschnitte aus fremden Beiträgen und auf den Haken von 14 (Synergie § 1).
