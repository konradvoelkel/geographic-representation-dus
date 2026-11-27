# Rückstand

Stand 2026-11-26, `v0.32.0`. Hier stehen nur **offene** Aufgaben; was erledigt ist, fliegt raus, und
wichtige Änderungen stehen datiert in `CHANGELOG.md`. Jeder Punkt nennt, was offen ist und wo es
herkommt; Entscheidungen fallen mit einem Plan oder einem Punkt in `docs/decisions.md`.

Die Nummern bleiben, damit Verweise aus `docs/decisions.md`, `docs/architecture.md`, den
Messdokumenten und dem Code halten; freie Nummern bleiben frei. Die Punkte 1 bis 7 sind erledigt
(Themenmodell, Seitengröße, Skalierung, Methodik-Review, Literatur, Lizenz, Extraktor im
Methodenteil); ihr Verlauf steht in `CHANGELOG.md` (0.12.0 und 0.22.0) und in den Dokumenten, auf die
sie verweisen.

Was die Vorhaben der Vorverarbeitung 2026-11 noch brauchen — Stufe 3 aller gebauten Vorhaben, Stufe 2
von 16, 19, 27 und 28 —, steht in `docs/plans/README.md`, nicht hier.

## 8. Eine Probe mit `fetch papers --max-pages` verdirbt den folgenden vollen Abruf

Aufgenommen am 2026-11-23, gefunden vom Agenten des Fundaments F6 der Vorverarbeitung 2026-11
(`docs/plan-vorverarbeitung-2026-11.md`). Für die neuen Schritte `meetings`, `consultations` und
`persons` hat er es behoben und mit einem roten Test belegt; in `fetch papers` steckt derselbe
Fehler noch: eine Probe mit `--max-pages` auf einem leeren Store hinterlässt einen Stand, nach dem
der nächste Lauf mit `modified_since` nur noch Geändertes holt, statt die Liste zu Ende zu lesen.
Zu tun: denselben Weg wie in F6 (eine Probe ist der Anfang des Abrufs, der nächste Lauf setzt
fort) für `papers`, mit rotem Test.

## 9. Urheber: Mitantragsteller gehen verloren, das BSW fehlt

Aufgenommen am 2026-11-23 aus der Messung von Vorhaben 15 (`docs/plans/15-funktion.md`, Frage 9.5).
In `analysis/parties.py` gewinnt die erste Quelle (Dokumentart, Titel, Textkopf): bei 281 Dokumenten
gehen Mitantragsteller verloren (etwa „Antrag CDU/Grüne" mit vier Fraktionen im Titel), bei 49
zählt eine Partei mit, die nur im Gegenstand vorkommt, und das BSW fehlt in `[originators]` des
Profils, sodass 12 Anfragen als Person ohne Partei geführt werden. Zu tun: Quellen vereinigen statt
der ersten zu folgen, Parteien im Gegenstand ausschließen, das BSW ergänzen; Wirkung auf die
Parteikarten der Seite mit A/B-Bau messen, weil sich Zahlen ändern.
Die Kodierung von Vorhaben 15 (2026-11-23, `docs/plans/15-funktion.md` § 4.2) bestätigt das: `parteien`
nennt zweimal eine falsche Fraktion (AfD aus dem Gegenstand, SPD aus dem Briefkopf-Fenster); 19 Fraktionen
fehlen, davon 10 in Dokumenten der Urheberklasse „unbekannt", 7 in interfraktionellen Anträgen, deren
Fraktionen nur im Text stehen (Frage 9.15 dort).
Stand 2026-11-26: Vorhaben 15 vereinigt die Antragsteller aus drei Quellen im eigenen Schritt
`cosponsors` (`dokumente_antragsteller.parquet`, `docs/decisions.md`, Punkt 75); `analysis/parties.py`
selbst ist unverändert, und das BSW steht weiter nicht in `profiles/duesseldorf.toml`.

## 10. Textübernahme neu messen, wenn die Vorgänge gebaut sind

Aufgenommen am 2026-11-23 aus Vorhaben 23 (`docs/plans/23-textuebernahme.md`, § 4.1 und § 5), das
nach seiner vorab festgelegten Regel verworfen ist: Musteranträge gewichtet 0,889, Übernahmen über
Fraktionsgrenzen 0,296, Schwelle 0,9 je Art. Die Fehler sind vor allem Zitate im selben Verfahren
und Bausteine; beides könnten die Kanten aus Vorhaben 14 (Stufe 2) und die Abschnitte aus 11
abfangen. Eine neue Messung wäre ein eigenes Vorhaben mit neuer Regel, neuem Codebuch (die Vorschläge
des Schlichters stehen in § 9 dort) und frischer Stichprobe, nicht eine zweite Runde an diesen Labels.

## 11. Modellnaht: kleine Punkte aus dem Review von F5

Aufgenommen am 2026-11-23 aus der letzten Nachprüfung von F5 (Punkt 72), keiner verfälscht ein
Ergebnis. (a) Bei einem 5xx auf jede Anfrage fragt ein Lauf alle gemerkten Fehlschläge erneut, je mit
Wartezeiten, ohne anzuhalten, weil sie nicht mehr in die Serie zählen; das kostet nur Zeit.
(b) Weniger als zehn Abweisungen in Folge mit vorübergehender Ursache bleiben als abgewiesen gemerkt;
der Rückweg ist `--retry-rejected`. (c) Wer `embed_texts` oder `generate_texts` außerhalb von
`run_step` aufruft (etwa ein Skript der GPU-Warteschlange), muss `use.reset(retry_rejected=…)` selbst
setzen. Zu klären, wenn die Modellschritte von 19 und 20 gebaut werden.
(d) Eine Tempo-Probe vor dem ersten Stapel eines Modellschritts (oder in `georep ml status`): zweimal
rechnete ollama still auf der CPU, während `ollama ps` „100% GPU" sagte (2026-11-23, 22:42,
`ggml_cuda_init` im Log; Vorhaben 18, Frage 9.5). Bis dahin prüft jeder Lauf das Log und das Tempo von
Hand.
(e) Die Zahl der Korpus-IDs ohne Rohtext, für die `embeddings` keinen Vektor schreibt, steht nur in
der Laufzeile, nicht im Stamp und nicht in `status` (Review von Vorhaben 18, N9; braucht eine Stelle im
Stamp für Zählungen eines Schritts).

## 12. Vorgänge: Rückstand aus der Nachprüfung von Vorhaben 14

Aufgenommen am 2026-11-24 aus der Nachprüfung der Runde 2 (Punkt 76); keiner verfälscht ein Ergebnis.
(a) `references` braucht unter Last mehr als die angestrebten 20 s (21,3 s bei Last 16), rund 7 s davon
`flatten_with_offsets`. (b) Die Mini-Läufe lesen die echten Nachbarpakete relativ zum
Arbeitsverzeichnis. (c) Das README-Gerüst von `pack --attachments` ist das allgemeine. (d) Die
Stamp-Schlüssel von `compare` sind absolute Pfade unter `data_root`; relativ zu `data_root` liefe
`compare` nach einem Umzug nicht neu (0,1 s, Kür). (f) Die Maske nimmt
einmal ein Sachwort mit („Anfrage Dr. …" statt „… Hitzeschutz"); das README des Pakets sagt es.
(g) Aus der Stufe 3 (2026-11-27): der Dokumentdialog zeigt je Dokument nur die Kanten, die der
eigene Datensatz kennt; nennt eine Drucksache einer späteren Periode ein Dokument, fehlt das in
dessen Dialog (Hauptperiode: Kanten aus der laufenden Periode). Abhilfe wäre, dass `procedures` die
starken Kanten der Nachbarn, die es für den Wald ohnehin rechnet, als eigene Datei schreibt.

## 13. Zeit und Feeds: Rückstand aus dem Review von Vorhaben 17

Aufgenommen am 2026-11-26 aus dem Review der Stufe 2 (Punkt 78); keiner verfälscht ein Ergebnis heute.
(a) `jonckheere` (`analysis/cycles.py`) legt Anzahl × n × n float64 an: bei Gruppengrößen (6, 5, 4)
rund 1,1 GB, bei (6, 5, 5) rund 4,1 GB — das tritt ein, sobald das Paket 2025 bis August 2029 reicht,
und droht auf dem Pages-Runner als Speicherabbruch; in Blöcken zählen oder die exakte Verteilung
falten. (b) Die offene Periode endet am jüngsten Korpusdatum; ein falsch in die Zukunft datiertes
Dokument macht ein Wahljahr vorzeitig vollständig. (c) Fehlt nur `snapshots/2025`, verliert die Seite
den Periodenvergleich (Kopplung von Option 02 an 17). (d) Mönchengladbach hat in keinem Wahljahr einen
Haushaltsmonat; die Unterseite in Stufe 3 sagt das. (e) `cycle_tests` prüft die Schema-Version der
fremden Ordner nicht (wie `compare`).

## 14. Struktur der Dokumente: Kandidaten für `struktur-2`

Aufgenommen am 2026-11-24 beim Bau von Vorhaben 11 (`struktur-1` ist der validierte Entwurf
unverändert, Punkt 81); jede Änderung hier braucht eine frische Bestätigungsstichprobe. (a) Der
Beschlusssatz ohne Überschrift wird erst hinter dem **Ende des Abschnitts** `kopf_beratungsfolge`
gesucht, und der reicht bis zur nächsten Überschrift. Von den 278 Dokumenten der Hauptperiode, deren
Art einen Beschlussvorschlag erwarten lässt und in denen die Regel keinen findet, haben 70 Text ohne
Überschrift unter der Beratungsfolge (60 Beschlussvorlagen einer Bezirksvertretung, 58 davon BV 8),
und in 65 davon steht dort ein Beschlusssatz wie „Bezirksvertretung 8 beschließt …". Gesucht werden
müsste hinter dem letzten Kopffeld. Die Messung (§ 3.4) zählte diese 70 als „Rumpf leer"; leer sind
34. (b) Die zwölf Fehler am Ende des Beschlussvorschlags (Messdokument § 4.1). (c) Der Rumpf beginnt
in 2014 bis 2020 bei 4 095 Dokumenten mitten in der Kopfzeile, mit dem Namen hinter der
Amtsbezeichnung (Review von Vorhaben 11, N1, 2026-11-24; Begründung berichtigt in Runde 3): in
diesem Formular ist die Amtsbezeichnung das letzte Kopffeld -- 3 599 der 4 095 haben Zeilen der
Beratungsfolge, aber davor --, also endet der Kopf am Ende des Titels, und der Abschnitt
`kopf_dezernat` wird dort geteilt. Schneiden müsste er am Ende der Zeile des letzten Kopffelds. Nicht jetzt, weil Vorhaben 16 genau
diese Grenze vermessen hat; mit `struktur-2` und 16 zusammen.
(f) Der Kopf läuft in die nächste Zeile oder das nächste Feld: in der Hauptperiode trägt `amt_name`
viermal das Feld der Dezernentin oder des Dezernenten mit Namen („Kulturamt Dezernentin/Dezernent:
…"), in 2014 bis 2020 168-mal, dort dazu zwölf Zeilen der Beratungsfolge aus Textresten. Der
Download leert solche Werte (Stufe 3, `report.names`); schneiden müsste `struktur-2` die Amtszeile
am nächsten Feldlabel, auch ohne Doppelpunkt und mit anderer Schreibweise des Labels.


## 15. Beschlusslage: Rückstand aus dem Review von Vorhaben 26

Aufgenommen am 2026-11-26 aus dem Review der Stufe 2 (Punkt 79). (a) Die Folgevorlage ist je Profil
eine Untergrenze: die Kanten von 14 tragen nur Drucksachen des eigenen Korpus, 114 von 1 508 Anträgen
haben ihre Folgevorlage nur in der Nachbarperiode — soll 14 Kanten aus den Nachbarperioden
mitschreiben? (b) Ein Wortschatz für Mönchengladbach ist eine eigene Messung (48 Werte, darunter
„Siehe Niederschrift", „Ohne Abstimmung", „Die Bezirksvertretung wurde angehört"). (c) Das Messskript
von 26 bricht ab, sobald Dateien Mönchengladbachs im Datenordner liegen. (d) `rolle` bedeutet in
`beratungsverlauf`, `beschlusslage` und `dokumente_vorgang` dreierlei; vor Stufe 3 umbenennen oder in
`schema.json` sagen. (e) `[bodies.organizations]` braucht vor Stufe 3 die Kürzel `gr/400224` und `gr/65`
mit Beleg und A/B-Bau (Frage 9.17 dort).

## 16. Fingerprint je Schritt statt global

Aufgenommen am 2026-11-26 aus den Reviews von 12 und 22 (Punkte 80 und folgende); zurückgestellt war
es schon in `docs/plans/00-synergien.md`, § 8. Der Settings-Fingerprint
ist global: `duesseldorf-vergleich` rechnet auf Pages jeden Schritt neu, weil `compare.period` ihn ändert
(12: `identifiers` zweimal je rund 47 s), und die Periodenprofile rechnen ganz neu, wenn sich geerbte
Hypothesen von `need` ändern, obwohl `need` dort aus ist (22, `robust_without`). Ein Fingerprint je Schritt
aus den Schlüsseln, die er liest, behöbe beides; das ist eine Kernänderung mit eigenem A/B-Bau. Dazu für
Stufe 3 von 22: die Namensnennung auf der Seite braucht den Hinweis „verändert" (`NeedAttribution` hat
dafür noch kein Feld).

## 17. Kennungen: Rückstand aus dem Review von Vorhaben 12

Aufgenommen am 2026-11-26 aus dem Review der Stufe 2 (Punkt 82); keiner verfälscht ein Ergebnis.
(a) `identifiers` braucht für die Hauptperiode rund 27 s in einem Prozess, verteilt auf rund 25
Regex-Durchläufe über 55 Mio. Zeichen (am teuersten `month_year`, `plan`, `amount_after`); billige
Vorfilter je Muster oder ein Prozesspool über Textblöcke, je mit dem Vergleich gegen das Messskript.
(c) In 37 Dokumenten nimmt 12 bei dreistelliger Unternummer oder ohne Bindestrich den ganzen Wert als
Norm des Amts, 11 nur die Nummer (`tests/golden/test_identifiers_heads.py`); Nutzer des federführenden
Amts lesen es aus 11. (d) Der Eintrag in `MUTATION_SCOPE` ist ungemessen.

## 18. Ausschussklassifikator rechnerfest machen?

Aufgenommen am 2026-11-26 aus der Ursache des roten CI-Laufs von 0.29.0 (Punkt 80, Nachtrag). Die
logistische Regression des Ausschussklassifikators (Punkt 45) hält mit `tol` 1e-4 nach 46 Iterationen
an; dazwischen und einer engen Toleranz (1e-10, 132 Iterationen) liegen die Wahrscheinlichkeiten bis
0,011 auseinander, und 18 von 19 033 Dokumenten wechseln die Klasse. Eine engere Toleranz machte die
Klassen rechnerfest, verschöbe aber die Ausschusszuordnung auf der Seite und die Zahlen von H1 und H3 aus
22 (H1 ρ 0,3427 → 0,3470, Urteil gleich): eigene Entscheidung mit A/B-Bau aller Seiten.

## 19. Kurzfassungen: vor jedem Einschalten

Aufgenommen am 2026-11-26 mit dem Merge von Vorhaben 20 (Punkt 83). (a) Der Code von 20 hatte kein
unabhängiges Review wie die übrigen Bauten der Stufe 2; der Supervisor hat nur geprüft, dass keine
Kurzfassung ins Repo gelangt und der Schritt in allen Profilen aus ist. Vor dem ersten Einschalten ein
Review. (b) Weiter ginge es nur mit einem Codebuch Fassung 2 (Fragen 20.10, 20.11, 20.15 im Messdokument:
gestrichene Einschränkungen, Verallgemeinerungen, eine Möglichkeit als Pflicht, Kopfdaten gegen
Betreff, Adressat einer Anfrage) an einer frischen Stichprobe, als eigenes Vorhaben; erst danach ein
Stapellauf (5 bis 8 GPU-Stunden mit gemma4 für die Hauptperiode).

## 20. `cryptography` ins Lock?

Aufgenommen am 2026-11-26 aus `STATUS.md` (seit dem 2026-11-18 offen, Punkt 68). Ein PDF der
Hauptperiode, `00403713.pdf`, ist mit AES verschlüsselt; pypdf braucht dafür `cryptography`, das nicht
im Lock steht, meldet `CorruptPdfError: cryptography>=3.1 is required for AES algorithm`, und der Store
behält den Text der Arbeit. Jeder Lauf mit PDFs zählt es als fehlerhaft und versucht es erneut. Zu
entscheiden: `cryptography` aufnehmen (eine Abhängigkeit mehr, danach das Textpaket neu packen) oder
den einen Text der Arbeit so lassen.

## 21. Abhängigkeitsrunde: numpy und crosshair

Aufgenommen am 2026-11-26 aus `STATUS.md` (Abhängigkeitsrunde vom 2026-11-15, Punkt 66). numpy steht
im Lock auf 2.5.4; 2.5.5 erschien am 2026-11-15 abends und ist nicht gemessen (A/B-Bau aller Seiten
nach `CLAUDE.md`, „Commits"). `crosshair-tool` steht fest auf 0.0.111, weil 0.0.113 in einem von vier
vollen Läufen von `nox -s verify` selbst abstürzte; anheben, sobald eine Version das nicht mehr zeigt,
und `verify` von Hand fahren (der Push-CI sieht es nicht).

## 22. Monitor, VPS und Domain

Aufgenommen am 2026-11-26 aus `STATUS.md` und `docs/technik.md`, § 5. Der Timer, der die laufende
Periode fortschreibt (`deploy/README.md`: Installation, Trockenlauf und Erstabruf beschrieben, der
Trockenlauf ist am 2026-10-13 gelaufen), ist nirgends installiert; bis dahin zeigt `2025/` den
Schnappschuss vom 2026-10-13. VPS und Domain kommen später, ein R2-Bucket nicht (Antworten vom
2026-10-13 auf die Fragen 7.1 und 7.4 in `docs/plans/fragen.md`).

## 23. Aufräumen auf dem Rechner

Aufgenommen am 2026-11-26; ein Handgriff des Eigentümers, kein Agent löscht hier etwas.
(a) Die alte venv `/media/konrad/xtraspace/venvs/geographic-representation-dus` (Python 3.12,
pip-Pins der Arbeit) wird nicht mehr gebraucht (vorher in `FORK-NOTES.md`). (b) Die Datenwurzel
`…/xtraspace/georep/data-vollabruf/` des Vollabrufs der Metadaten vom 2026-10-14; seine Befunde stehen
in `docs/befunde-2026-10-14.md`. (c) Der lokale Branch `backup/04-vor-rebase` (2026-10-12) aus dem
Ausbau. (d) Logs und `anlegen.sh` unter `…/xtraspace/georep/worktrees/`; die Worktrees selbst sind
seit dem 2026-11-26 entfernt.

## 24. Titel der Arbeit und die Kölner Untersuchung

Aufgenommen am 2026-11-26 aus `STATUS.md` (Punkt 47, seit dem 2026-10-13 offen). In der
Literaturübersicht der Seite und im README stehen zwei Lücken sichtbar als „nachzutragen"
(`pending = true` in `[[report.literature]]` des Stadtprofils): Titel, Monat der Einreichung und
Betreuung der Arbeit, die ihr Repositorium nicht nennt, und die Kölner Untersuchung zu Parteien und
Ratsdokumenten, die die Arbeit zitiert und die am 2026-10-13 in OpenAlex, Crossref, arXiv,
Hochschulrepositorien und auf GitHub nicht auffindbar war. Beides ist nur beim Autor der Arbeit zu
erfragen.

## 25. Tabelle 5, Spalte „ohne Ausreißer", mit dem Autor der Arbeit klären

Aufgenommen am 2026-11-26 aus `STATUS.md`. Die Spalte der Arbeit weicht von der Neuberechnung ab
(`docs/baseline-2026-10-10.md`); die Tests frieren die Neuberechnung ein. Seit Punkt 61 heißt die
Spalte auf der Seite „explorativ". Zu klären bleiben die Abweichung und die Wahl der beiden Bezirke.

## 26. Die Grenze von 90 % im Runbook der Städte

Aufgenommen am 2026-11-26 aus `STATUS.md` (seit dem 2026-10-15 offen, Punkt 65). Mönchengladbachs
Straßen stimmen mit den Flächen des Wahltags zu 88,8 % je Wahlbezirk mit dem amtlichen Verzeichnis
überein; alle 300 Abweichungen sitzen an Bezirksgrenzen, weil das Verzeichnis über Adressen und
Overpass über Straßenzüge zuordnet. Zu entscheiden: ob die Grenze in `docs/runbook-stadt.md`, § 4,
für Städte mit einem solchen Verzeichnis bleibt, anders gerechnet wird oder fällt.

## 27. Die Eigenheiten von deal upstream melden

Aufgenommen am 2026-11-26 aus `STATUS.md`. deal 4.24.6: `deal.raises` vergleicht exakte Typen, keine
Unterklassen, und `deal.has()`/`deal.pure` sind nicht reentrant (der Patch bleibt nach einer Rekursion
stehen). Beides ist umschifft (`docs/architecture.md`, „Verträge"), gemeldet ist es nicht.

## 28. Mehrdeutige Beratungsfolgen über die Beratungen von F6 auflösen

Aufgenommen am 2026-11-26. 1 535 Dokumente der Periode 2014 bis 2020 und 1 275 Mönchengladbachs bleiben
„Gremium unbekannt", weil ihre Beratungsfolge mehrere Organisationen nennt und
`OparlPaper.consultation_organizations` die Liste sortiert und entdoppelt liest; welches Gremium
federführend war, steht darin nicht (Punkt 58; fünf Auswahlregeln gemessen, die beste trifft 59,9 %).
Der Netzlauf von F6 vom 2026-11-23/24 (`docs/runbook-sitzungen.md`, § 9) hat die Beratungen selbst mit
Sitzung und Tagesordnungspunkt geholt; damit wäre die Reihenfolge bestimmbar. Eine eigene Messung,
Wirkung auf die Gremientabellen mit A/B-Bau.

## 29. Overpass: der Wiederholungsweg über alle Stimmbezirke Düsseldorfs

Aufgenommen am 2026-11-26 aus `STATUS.md`. Seit Punkt 55 wiederholt `fetch_street_names` bei 504 und
429 selbst, je Stimmbezirk. Gelaufen ist das an Mönchengladbach (179 Stimmbezirke, 2026-10-15), über
die 306 Stimmbezirke Düsseldorfs nicht: gemessen ist die Ursache, nicht die Heilung. Beim nächsten
Abruf von `streets_osm` nichts am Cache-Schlüssel ändern (`docs/technik.md`, § 2).

## 30. Offene Auswertungen

Aufgenommen am 2026-11-26 aus `docs/statistik.md`, § 13 (dort steht jetzt ein Verweis hierher).
(a) Ein Ausschussklassifikator, der auf der Beratungsfolge statt auf der Drucksachennummer trainiert
und bewertet wird; er mäße die Zuordenbarkeit der BV- und Ratsdokumente an einem Label, das nicht im
Text steht (`docs/befunde-2026-10-14.md`, § 6, Punkt 1; `docs/statistik.md`, § 10). (b) Umlaute sind
Wortgrenzen im Matcher („Köölberg" trifft „ölberg"); die Seite sagt es nicht
(`docs/methodik-review-2026-10.md`, § 6). (c) Ein Konfidenzintervall oder ein Permutationstest neben
dem p-Wert von Tabelle 5; bei n = 41 billig. (d) Typfilterung der Wikidata-Orte (`P31` auf Straße,
Platz, Park, Gebäude, Gewässer) statt der Namensregel; braucht eine SPARQL-Änderung und einen neuen
Abruf, und die Typhierarchie ist für Kommunalobjekte lückenhaft.

## 31. `modified_since` bei den Beratungen prüfen

Aufgenommen am 2026-11-26 aus `docs/runbook-sitzungen.md`, § 8 (dort steht jetzt ein Verweis
hierher). Bei den Papern liefert der Server mit dem Filter Geändertes und Gelöschte (Option 07); für
die Liste `consultations` ist das plausibel, aber nicht belegt. Prüfung nach dem ersten vollen Lauf
(2026-11-24), frühestens einen Tag später:

```bash
raw=$(uv run georep paths | sed -n 's/^root=//p')/raw
uv run georep fetch consultations --force            # inkrementell: "seit <datum>"
cp "$raw/consultations.jsonl" /media/konrad/xtraspace/georep/consultations-inkrementell.jsonl
rm "$raw/consultations.jsonl"                        # ohne Bestand ist der nächste Lauf voll
uv run georep fetch consultations
diff <(sort /media/konrad/xtraspace/georep/consultations-inkrementell.jsonl) <(sort "$raw/consultations.jsonl") | head
```

Gleich: der Filter trägt, `council.incremental` bleibt. Fehlen im inkrementellen Bestand Zeilen oder
stehen Gelöschte darin: `incremental = []` im Stadtprofil, und `consultations` holt wie die anderen
beiden jedes Mal alles.

## 33. Lokale Datenwurzeln neu rechnen

Aufgenommen am 2026-11-26. Im Hauptklon meldet `georep status` fast jeden Schritt als offen
(„Settings geändert", „Ausgabe fehlt"), weil die Läufe der Vorverarbeitung in den Worktrees unter
eigenen Datenwurzeln liefen. Zu tun, ohne Netz: `georep bootstrap` und `georep run` je Profil, zuerst
`duesseldorf` (die Perioden lesen sein Wörterbuch), dann `duesseldorf-2014`, `duesseldorf-2025`,
`duesseldorf-vergleich` und `moenchengladbach`. Die Netzschritte Mönchengladbachs bleiben danach
„offen: Settings geändert", bis ein Abruf ohnehin ansteht.

## 34. Mutationstest der Berichtsseite

Aufgenommen am 2026-11-26 aus `STATUS.md` (Absicherung vom 2026-10-13, `docs/absicherung-2026-10.md`).
`report/model.py`, `report/charts.py` und `report/build.py` (rund 3 500 Zeilen) sind nie mit
`nox -s mutate` gemessen worden.

## 35. Größe der Downloads je Dokument

Aufgenommen am 2026-11-27 mit `akteure.html` (Punkt 88): die beiden Tabellen je Dokument von 15
(`dokumente_funktion`, `dokumente_antragsteller`) machen die veröffentlichte Seite um rund 10 MB größer,
fast nur CSV (rund 9,6 MB), davon rund 70 % die Spalte `id` (OParl-URL). Jede Tabelle im Register kommt
als Parquet und CSV; eine Verkleinerung (CSV nur für die Hauptperiode, gzip, kürzere Kennung) wäre eine
Regel für das ganze Register. Entscheiden, bevor weitere Tabellen je Dokument dazukommen (14, 26).
Mit Stufe 3 von 11 und 12 (2026-11-27) kamen in der Hauptperiode `dokumente_kopf.parquet` (204 KB,
ohne CSV), `kennungen.parquet` (1,25 MB) und `kennungen.csv` (4,6 MB, nur Bauleitplanung und Beträge,
30 180 Zeilen; davon 2,1 MB die Spalte `id`) dazu; als CSV nur Bauleitplanung wären es 0,33 MB.
Stand mit Stufe 3 von 14 (2026-11-27): `dokumente_vorgang` (je Dokument), `vorgang_kanten` und
`antwortzeiten` kommen in allen vier Datensätzen dazu; in der Hauptperiode als CSV 2,80, 1,27 und
0,42 MB (Parquet 0,08, 0,08, 0,03 MB), über alle vier Datensätze zusammen 10,9 MB, die
veröffentlichte Seite wuchs damit von 46,9 auf 58,4 MB. Seit dem Nachtrag zum Entscheidungseintrag
von 14 trägt `dokumente_vorgang.csv` nur die Dokumente in einem Vorgang (7,05 → 0,73 MB über die
vier Datensätze, `CsvPlan` aus Punkt 89 wie beim Vokabular von 17); offen bleibt die Regel für die
übrigen Tabellen je Dokument (15: `dokumente_funktion`, `dokumente_antragsteller`).

## 36. Spaltenschema nicht mehr auf der Hauptseite

Aufgenommen am 2026-11-27 nach `vorgaenge.html` (Punkt 91): die Hauptseite der Hauptperiode wiegt 966 522
Byte, rund 29 KB über dem Bau vor `v0.33.0` (Ziel der Phase höchstens 30 KB, hart 1 000 000). Den größten
Teil des Zuwachses tragen die Spaltenschemata der neuen Tabellen (`<details>` unter „Spaltenschema" je
Tabelle, bei 15, 11/12, 17 und 14 je rund 3 bis 6 KB). Vor der nächsten Unterseite (22) das Spaltenschema
nur noch in `schema.json` und auf einer kleinen eigenen Seite führen und auf der Hauptseite verlinken;
eine Regel für das ganze Register (Reviews der Stufen 3 von 15, 11/12, 17 und 14).

## 37. Allgemeine Wörter im Wörterbuch Mönchengladbachs

Aufgenommen am 2026-11-27 mit der Startseite (Punkt 93): der häufigste Ort auf der Karte Mönchengladbachs
ist „Stadt" im Wahlbezirk 30 (127 Dokumente). `combined_searchdict` führt dort `stadt`, im Wahlbezirk 2
`bau` und `baum`; das sind Wörter der Alltagssprache, die als Straßen- oder Ortsnamen ins Wörterbuch kamen
und jedes Dokument treffen, das sie enthält. Die Ausschlussliste des Profils Düsseldorf fängt solche
Wörter, die Mönchengladbachs offenbar nicht alle. Zu tun: die kurzen und allgemeinen Begriffe des
Wörterbuchs prüfen, die Ausschlussliste in `profiles/moenchengladbach.toml` ergänzen; die Zahlen
Mönchengladbachs ändern sich, also A/B-Bau.

## 38. Satz zur Wörterbuchgröße in der Methode nur bei starker Korrelation

Aufgenommen am 2026-11-27 aus dem Bau der Startseite (Punkt 93). Die Kurzfassung der Startseite nennt
die Verzerrung durch die Wörterbuchgröße erst ab r ≥ 0,5 (`BIAS_R`); der Absatz in `details.html`
(`60-methode.html.j2`) sagt dagegen auch bei r = 0,18 (Mönchengladbach), die Trefferzahl hänge „vor
allem" an der Größe des Wörterbuchs, sobald sich die Korrelation rechnen lässt. Dieselbe Grenze dort
anlegen, mit A/B-Bau.

