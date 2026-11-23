# Vorhaben 28: Abstimmungen und Kooperation

Stand 2026-11-24, Stufe 1 (Messen), Branch `feat/28-abstimmungen`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „28 Abstimmungen und
Kooperation". Messskript: [28-abstimmungen-messung.py](28-abstimmungen-messung.py).

*Dieser Stand ist der Vorab-Commit (§ 2.11 des Meta-Plans): nur § 8 ist geschrieben, bevor ein
Abstimmungsergebnis ausgezählt, ein Wert von `result` gezählt oder eine Niederschrift geladen ist. Die
übrigen Abschnitte folgen im nächsten Commit; § 8 ändert sich danach nicht mehr, Ergänzungen stehen
datiert darunter.*

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

folgt

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

folgt

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

folgt

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

folgt

## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

folgt

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

folgt

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

folgt

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

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

folgt

## 10. Änderungen durch die Synergie (füllt der Supervisor)

folgt
