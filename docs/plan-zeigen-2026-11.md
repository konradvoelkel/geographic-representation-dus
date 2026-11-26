# Plan: Zeigen, was gebaut ist (Stufe 3 der Vorverarbeitung 2026-11)

Stand 2026-11-27. Grundlage ist Konrads Entscheidung vom 2026-11-26 für **Variante a, erst zeigen**:
die gebauten Vorhaben kommen auf die Seite, bevor der Rest gebaut wird. Am selben Tag hat er die
Fragen 19 und 37 beantwortet (§ 3). Dieser Plan setzt den Meta-Plan
[plan-vorverarbeitung-2026-11.md](plan-vorverarbeitung-2026-11.md) fort. Dessen Rollen, Regeln (§ 4),
die Abnahme der Stufe 3 (§ 8), Versionen (§ 2.12) und das Fragenprotokoll gelten unverändert. Neu sind
hier die Reihenfolge, die Vorarbeiten, die Budgets und die Regeln für den Abschluss. Stand je
Vorhaben: [plans/README.md](plans/README.md). Fragen: [plans/fragen-2026-11.md](plans/fragen-2026-11.md).

## 1. Ziel und Nicht-Ziele

**Ziel.** Die neun in Stufe 2 gebauten Vorhaben (11, 12, 14, 15, 17, 18, 20, 22, 26) werden
sichtbar, ohne die Hauptseite über ihr Budget zu treiben.

- Acht davon bekommen ihre Stufe 3 nach § 7 ihres Messdokuments: eine Unterseite, einen Abschnitt,
  eine Downloadzeile oder einen Eintrag im Dokumentdialog.
- Vorhaben 20 bleibt, was es ist: gebaut, aus und nie veröffentlicht (Meta-Plan § 10, Frage 6). Es
  geht nur durch die Rückbauregel (§ 8).
- Parallel und nur auf der CPU bauen 16 und 28 (Ebene A) ihre Stufe 2. 19 baut seine Stufe 2 als
  eigenen Schritt nach den Vorarbeiten. Am Ende der Phase folgen ihre Stufen 3.

**Nicht-Ziele.**

- Keine Zahl der Hauptseite ändert sich still (Meta-Plan § 1).
- Keine neue Messung außer den Prüfstichproben, die eine Stufe 3 trägt (§ 4, § 5).
- Kein Netzlauf und keine Kurzfassung.
- Was ausdrücklich wartet, steht in § 10.

## 2. Ausgangslage (2026-11-26)

| Was | Stand |
|---|---|
| Stufe 3 | keine begonnen. Kein Beitrag registriert `tables` oder `pages`; der Dokumentdialog lädt nur `dokumente.json` und `begriffe.json` (`report/templates/frame/script.js.j2`) |
| `index.html` | 937 528 Byte veröffentlicht (Pages, `v0.32.0`, abgerufen am 2026-11-26; `STATUS.md`, „Zahlen“), Budget 1 000 000 (`report.page_budget_bytes`, Punkt 50; `publish --strict-budget`), also rund 62 KB Luft |
| Pakete | 168,6 von 180 MiB (`TOTAL_LIMIT`, `tests/unit/test_data_packages.py`) |
| Pages | Bau bei jedem Push auf `main`, unabhängig von `ci.yml`. Fünf grüne Läufe am 2026-11-26 dauerten 4 bis 6 Minuten vom Start bis zum Deploy |
| Validierung | Die Labels aller Vorhaben stammen von zwei Kodierern und einem Schlichter desselben Modells (`claude-opus-5-5`). Der `satz` in `guete.json` lautet nur „geprüft von zwei KI-Kodierern an *n* …, nicht von Menschen" (`validation/merge.py`) |

## 3. Entscheidungen, die gelten (Konrad, 2026-11-26)

1. **Variante a**: zuerst Stufe 3 der gebauten Vorhaben, der Rest danach (§ 10).
2. **Frage 19**:
   - Für **neue** Messungen ist Kodierer B ein anderes Modell als Kodierer A und der Schlichter.
   - Die bisherigen Labels bleiben, wie sie sind.
   - Jede Seite nennt je Vorhaben, wie geprüft wurde: welche Modelle kodiert und geschlichtet haben,
     an wie vielen Einheiten, nicht von Menschen.
   - Die Regel steht in [validierung.md](validierung.md), § 3 und § 4; den Code bringt V3.
3. **Frage 37**: Die Politikfeld-Tabelle von 19 erscheint getrennt unter CC BY-NC-SA 4.0, mit
   Namensnennung des Comparative Agendas Project. Alles andere bleibt CC0. Tabelle, Paket, Download
   und Seitenfuß nennen die Ausnahme.

## 4. Vorarbeiten

**V1 F2-Nachzug: Abschnitte aus fremden Beiträgen.** Erledigt der Supervisor direkt auf `main`, als
Refactoring mit A/B-Bau aller Seiten, bytegleich.

- Ein Beitrag kann einen Abschnitt auf der Unterseite eines anderen Beitrags anhängen, etwa über
  `Contribution.sections` mit Zielseite, Name, Rang, Vorlage und Daten.
- Die Seite rendert ihre fremden Abschnitte in fester Folge.
- Fehlt die Zielseite in einem Profil, entfällt der Abschnitt mit Namen im Log, ohne Fehler.
- Ein Test prüft, dass jedes Ziel eine registrierte Seite ist.
- Nötig für 26 auf `vorgaenge.html` und für 28 (und später 24, 27) auf `akteure.html`.

**V2 Der allgemeine Dialog-Haken** kommt mit Stufe 3 von 14, nicht vorher.

- Ein Beitrag legt `data/<name>.json` mit Zeilen je Dokument ab.
- `frame/script.js.j2` lädt die Datei beim ersten Öffnen eines Dialogs nach.
- `dokumente.json` wächst nicht.
- 18 (`aehnlich.json`) und 26 (`beschluesse.json`) hängen sich nur mit Daten an.

**V3 F4-Nachzug.** Code und Daten, Supervisor oder ein Agent mit Review.

- `merge` nimmt das Modell je Rolle: Kodierer A, Kodierer B, Schlichtung. README und `guete.json`
  nennen alle drei. Der `satz` nennt sie ebenfalls, bei gleichem Modell „zwei KI-Kodierer desselben
  Modells (…)".
- Die vorhandenen `guete.json` bekommen den neuen Satz über einen Lauf, der nur den Satz neu
  schreibt. Ein Test hält Labels und Zahlen bytegleich.
- Aus vorhandenen Labels werden über `validate import`:
  - `12-kennungen-2-f4` aus `validierung/12-kennungen/labels-2.csv`, für die Verwaltungseinheit und
    die Termine in Fassung 2;
  - `16-ortsbezug-f4` aus beiden Runden.
- Neu kodiert wird **die Prüfstichprobe von 14**: rund 50 Kanten der Rückfallregel, geschichtet nach
  Typ, als `14-vorgaenge-3-f4` (Frage 9.18 in `docs/plans/14-vorgaenge.md`). Das sind drei
  Agentenläufe nach der neuen Regel: A und Schlichter Opus, B ein anderes Modell.
- Der Recall von 12 (`12-kennungen-recall-f4`, Auswertung der Markierungen, `validierung.md` § 6) ist
  nicht Teil dieser Phase. Die Downloadzeile von 12 nennt dann nur die Präzision.

**V4 Die Regel aus Frage 19** in [validierung.md](validierung.md), § 3 und § 4: erledigt am
2026-11-26.

**V5 Kleine Punkte, die eine bestimmte Stufe 3 braucht.** Sie kommen je im Commit der Stufe 3 mit:

| Vorhaben | Punkt | Quelle |
|---|---|---|
| 11 | `sitzung_gremium` in `schema.json` erklären | `docs/todo.md`, Punkt 14 (e) |
| 14 | entscheiden, ob `verweise.parquet` so veröffentlicht wird | Punkt 12 (e) |
| 26 | die Kürzel `gr/400224` und `gr/65` mit Beleg ins Profil, A/B-Bau | Punkt 15 (e) |
| 26 | `rolle` umbenennen oder in `schema.json` erklären | Punkt 15 (d) |
| 22 | das Feld „verändert" in `NeedAttribution` | Punkt 16 |
| 17 | die Seite sagt, dass Mönchengladbach keinen Haushaltsmonat hat | Punkt 13 (d) |
| 18 | die Lizenz der Modellgewichte nachsehen | Frage 47 |

## 5. Reihenfolge und Versionen

Eine Spur für die Seiten, nacheinander. Daneben zwei Spuren für Stufe 2, die nur die CPU brauchen,
und eine für 19. Jeder Merge, der Code ändert, bekommt eine eigene Minor-Version (Meta-Plan § 2.12;
zwei kurz nacheinander dürfen eine teilen). Die Nummern sind die geplante Folge und rücken nach,
wenn sich ein Merge schiebt.

| Version | Spur | Inhalt | Größe auf der Seite |
|---|---|---|---|
| `v0.33.0` | Seiten | V1, F2-Nachzug | bytegleich |
| `v0.34.0` | Seiten | V3, F4-Nachzug (Prüfsatz mit Modellen; `12-kennungen-2-f4`, `16-ortsbezug-f4`; Prüfstichprobe von 14) | keine Änderung der Seite |
| `v0.35.0` | Seiten | 15 `akteure.html` | 40–70 KB, Linkblock auf `index.html` |
| `v0.36.0` | Seiten | 14 `vorgaenge.html` und der Dialog-Haken (V2) | unter 50 KB; `vorgaenge.json` unter 100 KB; Haken unter 1 KB auf `index.html` |
| `v0.37.0` | Seiten | 11 und 12 als Downloadzeilen (eine Version) | je unter 1 KB auf `index.html` |
| `v0.38.0` | Seiten | 17 `zeit.html` mit Feed-Liste (§ 7) | 40–80 KB |
| `v0.39.0` | Seiten | 22 `bedarf.html`; vorher die OVA-Kodierung an 100 Dokumenten der Bezirksvertretungen, weil H1 auf der Seite steht (Frage 22.3 in `docs/plans/22-bedarf.md`; drei Läufe nach der neuen Regel) | 150–250 KB |
| `v0.40.0` | CPU | 16 Stufe 2 (Stelle, Hausnummern, Variante `ortsbezug`, Adresspaket 93 KB); vorher § 10 durch den Supervisor | Gewichtungstabelle unverändert, bis Stufe 3 |
| `v0.41.0` | CPU | 28 Stufe 2, nur Ebene A (Paket 1–2 MB); vorher § 10 | – |
| `v0.42.0` | Seiten | 18 „ähnliche Dokumente" im Dialog | `aehnlich.json` 820 KB (gzip 262 KB), nachgeladen |
| `v0.43.0` | Seiten | 26 auf `vorgaenge.html` (drei Abschnitte) und im Dialog | unter 30 KB; `beschluesse.json` unter 300 KB |
| eigene | 19 | 19 Stufe 2 mit Weg 3b: GPU unter 15 Minuten unter der Sperre, Paket `snapshots/duesseldorf-politikfelder/` mit Lizenz CC BY-NC-SA 4.0 im README; frühestens nach `v0.34.0`, vorher § 10 | keine Seite |
| `v0.44.0` bis `v0.46.0` | Seiten | Stufe 3 von 16 (zwei Gewichtungszeilen, ein Satz; ein Radio nur auf Wunsch, Frage 45), 28 (Abschnitt auf `akteure.html`) und 19 (`themen.html`; davor auf Wunsch die Stichprobe je Periode aus Frage 46) | unter 1 KB; rund 10 KB; 60–300 KB |

**Warum diese Folge.**

- 15 legt `akteure.html` an, und 14 den Haken, an dem 18 und 26 hängen.
- 11 und 12 brauchen V3.
- 17 und 22 haben keine Vorbedingung außer V5.
- 16 und 28 werden erst nach den Merges gemerged, die `index.html` berühren (15, 14, 11/12, 17,
  22). So bleibt jede Änderung der Hauptseite einem Merge zuzuordnen.
- 19 berührt keine Seite, bis seine Stufe 3 kommt.

**Haltepunkte.**

- **Z1** nach `v0.35.0`: Konrad sieht die erste Unterseite an (Rahmen, Prüfsatz, Linkblock), bevor
  die übrigen nach ihrem Muster folgen.
- **Z2** am Ende der Phase: der Bericht nach dem Abschlusskriterium (§ 8).

## 6. Budgets

| Was | Grenze | Messung |
|---|---|---|
| `index.html` | hart 1 000 000 Byte (bestehender Test). Ziel für die Phase: höchstens 30 KB über dem Bau vor `v0.33.0`, für Linkblock, Downloadzeilen, Dialog-Haken und die Zeilen von 16 | Bytes vor und nach im Commit-Body jedes Merges |
| jede Unterseite | unter 500 KB (Meta-Plan § 4) | `publish --strict-budget`, headless Chrome |
| Unterseiten je Profil | zusammen höchstens 1 MB; geplant sind in der Hauptperiode rund 500 KB, mit `themen.html` rund 800 KB | `publish` je Profil |
| nachgeladene Dateien je Profil (neu) | zusammen höchstens 1,5 MB; geplant rund 1,2 MB (`aehnlich.json`, `beschluesse.json`, `vorgaenge.json`) | Bytes im Commit-Body |
| Pages-Laufzeit | höchstens 8 Minuten (heute 4 bis 6). Darüber kommt vor jedem neuen Schritt der Fingerprint je Schritt (`docs/todo.md`, Punkt 16) | Actions-REST-API nach jedem Push |
| Pakete | am Ende der Phase höchstens rund 171 MiB (heute 168,6; dazu 16 mit 0,1, 28 mit 1–2, 19 mit unter 0,1). Die harte Grenze bleibt 180 | `tests/unit/test_data_packages.py` |

**Welche Seite in welchem Profil.** Eine Unterseite erscheint in jedem Profil, dessen Schalter des
Beitrags an ist und das die Eingaben hat. Jede Seite sagt, was in diesem Profil fehlt. Nach den
Bauplänen heißt das auf Pages:

- Hauptperiode: alles.
- 2014–2020 und laufende Periode: `akteure`, `vorgaenge` und `zeit`. Die Feeds stehen nur in der
  laufenden Periode.
- Mönchengladbach: `akteure` ohne Konkordanz und `bedarf` ohne Klassen; keine Anfragen, kein
  Wortschatz für 26.
- Rohtext und Nachbarn gibt es nur in der Hauptperiode (Frage 18). Die Downloads von 11 und 12 und
  die ähnlichen Dokumente erscheinen darum nur dort.

## 7. Die Feeds

17 schreibt die Feeds schon in Stufe 2: `feeds.enabled` steht im Profil `duesseldorf-2025`.
`pages.yml` kopiert den Seitenordner der laufenden Periode ganz, also mit `feeds/`. Die Dateien
liegen damit öffentlich, aber ohne Link. Solange kein Timer die laufende Periode fortschreibt
(`docs/todo.md`, Punkt 22), zeigen sie den Stand des Schnappschusses vom 2026-10-13.

**Regel für Stufe 3 von 17**:

- `zeit.html` listet die Feeds mit dem Datum dieses Stands neben der Liste.
- Ein Satz sagt, dass sie sich erst mit einem neuen Schnappschuss oder mit dem Timer ändern.
- Kein Feed-Link auf `index.html` (Frage 9.11 in `docs/plans/17-zeit.md`), kein `rel="self"`
  (Frage 28).
- Läuft der Timer, fällt der Satz weg.

## 8. Abschluss, Rückbau, Gültigkeit

**Abschlusskriterium der Vorverarbeitung 2026-11.** Sie ist abgeschlossen, wenn jedes der Vorhaben
11 bis 29 genau einen Endzustand hat:

1. **verworfen**: Messdokument und Entscheidungspunkt (13 und 23: Punkte 84 und 85);
2. **gebaut und gezeigt**: Stufe 3 gemerged, mit dem Prüfsatz aus `guete.json`;
3. **gebaut und bewusst nicht gezeigt**: mit Grund in `docs/decisions.md` (20);
4. **übergeben**: an einen eigenen Plan oder einen Punkt in `docs/todo.md`, mit Ort (21, 24, 25, 27,
   29, 28 Ebene B).

Dazu kommen die Aufgaben aus Meta-Plan § 9, Phase 5. Dann bekommt der Meta-Plan oben „Abgeschlossen
am …" und dieser Plan ebenso.

**Rückbauregel.**

- Wann: Ein Schritt ist in allen Profilen aus, oder seine Ausgaben liest weder eine Seite noch eine
  Tabelle noch ein anderer Schritt, und kein Plan sieht seine Stufe 3 vor. Dann entscheidet der
  Supervisor spätestens am Ende der nächsten Phase oder drei Monate nach dem Bau, was früher kommt.
- Was: entweder **ausbauen** (Code, Tests, Settings-Block, Paket) oder **behalten** mit datiertem
  Grund und Frist in `docs/decisions.md`.
- Messdokument und Entscheidungspunkt bleiben in jedem Fall.
- Bis dahin läuft ein solcher Schritt auf Pages nicht (Schalter im Profil aus), damit er keine
  Laufzeit kostet.
- Anwendung in dieser Phase: Vorhaben 20 wird bei Z2 entschieden. Es bleibt nur, wenn
  `docs/todo.md`, Punkt 19 (Codebuch Fassung 2) einen Termin hat; vor einem Einschalten braucht es
  das ausstehende Review.

**Gültigkeitsregel.**

- Ein Urteil der Stufe 1 gilt für die Daten, den Extraktor, das Modell mit Digest und Prompt und das
  Codebuch, an denen es gemessen ist. Das Messdokument nennt sie, der Stamp führt sie.
- Ändert sich eines davon, misst das Vorhaben vor seiner nächsten Stufe 3 oder vor der Nutzung durch
  ein anderes Vorhaben neu: frische Stichprobe, dasselbe vorab festgelegte Kriterium. Beispiele: ein
  neues pypdf; ein neues Modell oder ein neuer Prompt für Weg 1 von 19, der 3b neu trainieren
  ließe; eine neue Fassung des Codebuchs.
- Neue Dokumente derselben Periode machen ein Urteil nicht ungültig, solange keine neue Dokumentart
  dazukommt; das prüft der Test über die Dokumentart-Tabellen (Synergie § 1).
- Eine Periode oder Stadt, an der nicht gemessen ist, heißt auf der Seite „explorativ".
- Die bisherigen Labels gelten weiter (Frage 19). Die Seite nennt ihre Modelle.

## 9. Rollen, Plätze, Aufwand

**Rollen und Plätze.**

- Rollen wie Meta-Plan § 5. Je Stufe 3 ein Bau-Agent; derselbe Agent darf es sein, wenn er Stufe 2
  gebaut hat (Meta-Plan § 2.9).
- Je Merge ein Review am Diff.
- Kodier-Agenten nach [validierung.md](validierung.md) § 4.
- Höchstens drei Bau-Agenten zugleich: einer auf der Spur der Seiten (die Seiten teilen Rahmen,
  Register und `index.html`), je einer für 16 und 28, und 19 nach V3.

**Aufwand, geschätzt.**

- Rund 35 bis 45 Agentenläufe: 8 Stufen 3, 3 Stufen 2 und 3 späte Stufen 3, je mit Bau, zwei
  Reviews und einer Nacharbeit; dazu V1 und V3 und drei Kodierungen zu je drei Läufen (14, OVA für
  22, auf Wunsch 19).
- GPU: unter 15 Minuten für 19, auf Wunsch rund 2 Minuten für Frage 46.
- Netz: keines.
- Konrad: zwei Haltepunkte; die Fragen in § 11 gelten mit ihrer Annahme.

## 10. Nicht in dieser Phase

| Was | Wo es wartet |
|---|---|
| 21 Geld, Stufe 1 (nach Stufe 2 von 16) | [plans/README.md](plans/README.md); Briefing überholt, Meta-Plan § 11 „21" |
| 25 Versprechen, Stufe 1 | [plans/25-quellen.md](plans/25-quellen.md); Meta-Plan § 11 „25" |
| 29 Ratsarbeit, Stufe 1 (zuletzt, ohne Kurzfassungen) | plans/README.md; Meta-Plan § 11 „29" |
| 24 Umbaurunde (oder verwerfen) | Frage 41; [plans/24-kontrolle.md](plans/24-kontrolle.md), § 5.1 |
| 27 Stufe 2 und 3 (Zulieferer für 24) | plans/README.md; Fragen 43 und 44 |
| 28 Ebene B (voller Abruf der Niederschriften) | Frage 40 |
| 20 Codebuch Fassung 2 und ein Stapellauf | `docs/todo.md`, Punkt 19; [plans/20-kurzfassungen.md](plans/20-kurzfassungen.md), Fragen 20.10, 20.11, 20.15 |
| `struktur-2`, Codebücher Fassung 2 und 3 der übrigen Vorhaben, Textübernahme neu | `docs/todo.md`, Punkte 14 und 10; § 9 der Messdokumente |
| Abhängigkeitsrunde (numpy, crosshair), `cryptography` | `docs/todo.md`, Punkte 21 und 20 |
| Fingerprint je Schritt | `docs/todo.md`, Punkt 16; wird vorgezogen, wenn das Laufzeitbudget aus § 6 reißt |
| Monitor, VPS und Domain (Timer, kanonische Adresse) | `docs/todo.md`, Punkt 22; Fragen 28 und 7.2 |

## 11. Fragen an Konrad

Ohne Antwort gilt die Annahme, wie seit dem 2026-11-23.

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| Z.1 | Soll Pages auf eine grüne CI desselben Commits warten (`workflow_run` statt `push`)? | Ab Stufe 3 zeigt Pages neue Seiten; heute deployt auch ein Commit, dessen Tests rot sind | nein, Pages bleibt Staging und baut jeden Push. Der Supervisor prüft nach jedem Push CI und Pages über die REST-API und nimmt einen roten Stand sofort zurück |
| Z.2 | Gilt die Branch-Ausnahme von 2026-11-23 für diese Phase weiter (`feat/NN-name` in Worktrees auf xtraspace, Merge nur durch den Supervisor)? | Seit dem 2026-11-26 wird nur auf `main` gearbeitet; die drei Spuren und das Review vor dem Merge brauchen Branches | ja, als Fortsetzung der Vorverarbeitung, mit denselben Regeln (Meta-Plan § 4, § 6) |
| Z.3 | Die Feeds der laufenden Periode auf `zeit.html` listen, obwohl sie ohne Timer den Stand vom 2026-10-13 zeigen? | Ein Feed, der sich nicht ändert, ist keine Neuigkeit | ja, mit dem Datum des Stands und dem Satz aus § 7 |
