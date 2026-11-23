# Vorhaben 13: Dubletten und Dokumentfamilien

Stand 2026-11-23, Stufe 1, abgeschlossen mit der Kodierung der 200 Paare (§ 4.1). Briefing:
[plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11, Vorhaben 13.
Messskript: [13-dubletten-messung.py](13-dubletten-messung.py). Codebuch, Stichprobe und Labels:
[`validierung/13-dubletten/`](../../validierung/13-dubletten/).

**Urteil (nach der Kodierung): verwerfen. Befund: „es gibt kaum Dubletten".** Keine Grenze der
vorab festgelegten Schwellenregel erreicht die Präzision 0,95: am nächsten liegt τ = 0,9 mit
**0,948** [0,866; 0,964] (gewichtet, 58 kodierte Paare), darunter fällt sie auf 0,745 (ab 0,85), 0,538
(ab 0,8) und 0,411 (ab 0,7); ab 0,95 ist sie 0,812, weil drei wortgleiche Förderanträge
verschiedener Jahre dort liegen. Damit ist das Kriterium nach § 5 verfehlt, und es gibt keine
Variante. Das Urteil hinge auch nicht an der dritten Nachkommastelle: selbst bei τ = 0,9 lägen nur
**0,5 %** der Dokumente in Familien, und kein Wahlbezirk verlöre mehr als **1,4 %** seiner Treffer
(Schwellen des Kriteriums: 3 % und 5 %); Tabelle 5 rückt dort in der dritten Stelle (p ohne 1 und
10: 0,036 → 0,033; ρ = 0,9993). Die Kodierer waren sich einig (α = 0,941 über die vier Codes, 0,970
für „Familie ja oder nein").

Alle Zahlen sind am 2026-11-23 im Worktree `feat/13-dubletten` gemessen, Daten nach
`uv run georep bootstrap` und den Schritten bis `results` je Profil, mit `POLARS_MAX_THREADS=4`,
`OMP_NUM_THREADS=2`, `nice -n 10`, bei starker Fremdlast (Lastmittel 19 bis 95 statt höchstens 13;
Laufzeiten darum mit `uptime`). Nachrechnen:

```bash
uv run georep bootstrap && uv run georep run                    # Hauptperiode
uv run georep --profile duesseldorf-2014 bootstrap && uv run georep --profile duesseldorf-2014 run
uv run georep --profile duesseldorf-2025 bootstrap && uv run georep --profile duesseldorf-2025 run
uv run python docs/plans/13-dubletten-messung.py                # alle Zahlen hier, knapp zwei Minuten
uv run python docs/plans/13-dubletten-messung.py --kurven       # nur § 3.2 und § 3.3
uv run python docs/plans/13-dubletten-messung.py --stichprobe --schreiben   # § 4: Stichprobe und Kodieraufgaben neu
uv run python docs/plans/13-dubletten-messung.py --kodierung    # § 4.1 aus labels.csv; --labels-schreiben baut sie aus den lokalen Antworten
```

Für die Messung genügen die Schritte bis `results` (`georep run voters streets pois dictionary
corpus bodies index results`, für 2014 bis 2020 dazu `precincts`, für ab 2025 dazu `shapes`); der
volle Lauf prüft vorher die Hashes aller lokalen PDFs, was unter dieser Last über 20 Minuten dauerte
und für die Messung nichts ändert. Laufzeit des Messskripts: 1:52 min (Lastmittel 19,7 → 19,2) vor
der Kodierung, 1:26 min (Lastmittel 10,0 → 8,4) mit der Auswertung der Kodierung (§ 4.1, am Abend
des 2026-11-23 nach dem Rebase auf `v0.20.0`; die Treffer sind dieselben, 29 330).

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

**Frage.** Wie viele Ratsdokumente sind gleich oder fast gleich — dieselbe Mitteilung an mehrere
Bezirksvertretungen, Wiedervorlagen, Musteranträge —, und wie stark ändert das die Treffer je
Wahlbezirk, wenn jede Familie nur einmal zählt? Die Trefferquote der Arbeit zählt ein Dokument je
Wahlbezirk einmal ([methodik-review-2026-10.md](../methodik-review-2026-10.md), § 2.5); geht dieselbe
Vorlage an zehn Bezirksvertretungen, zählt sie zehnmal. Ob das die Kennzahl verzerrt, war ungemessen.

**Literatur.** Textübernahme als Spur politischer Ideen: Wilkerson, Smith und Stramp (2015)\*,
die in Gesetzentwürfen über lokale Ausrichtung übernommene Passagen suchen; das ist Vorhaben 23 und
braucht Kandidatenpaare, die dieses Vorhaben liefert. Das Verfahren selbst — Ähnlichkeit als
Jaccard-Maß über Shingles, geschätzt mit MinHash — geht auf Broder (1997)\* zurück; die Bänder des
Locality-Sensitive Hashing und die S-Kurve `1 − (1 − s^r)^b` stehen in Leskovec, Rajaraman und
Ullman, *Mining of Massive Datasets*, Kap. 3\*. Mit \* markiert: aus dem Gedächtnis, vor einem Zitat
auf der Seite nachzuschlagen (Regeln in `report/literatur.toml`).

**Ratsarbeit.** „Gab es das schon?" und „an wen ging das noch?" sind Alltagsfragen einer
Geschäftsstelle. Die gefundenen Familien beantworten sie für drei Fälle (§ 3.4): Fortschreibungen
(`X/1` neben `X`), Verteilervorlagen an mehrere Bezirksvertretungen und Anträge, die unverändert
wieder eingebracht werden. Die ersten beiden liest Vorhaben 14 schon aus Drucksachennummern und
Verweisen; das spricht dafür, den Nutzen dort zu heben statt in einem eigenen Schritt (§ 5, § 9).

## 2. Datenlage

| Datei | Spalten, die gelesen werden | Größe | Herkunft |
|---|---|---|---|
| `data_root/<profil>/interim/papers.parquet` (Korpus, Schritt `corpus`) | `id` (OParl-URL), `name` (Titel), `reference` (Drucksachennummer), `date`, `paper_type`, `text` (kleingeschrieben, ohne Zeilenumbrüche, nur die **Hauptdatei** eines Papers, pypdf 7.1.0) | Hauptperiode 19 108 Dokumente, 19 033 mit Text; 2014 bis 2020: 22 215 / 21 838; ab 2025: 4 095 / 4 075 | Textpakete im Repo (`snapshots/duesseldorf-texte`, `snapshots/2014-2020`, `snapshots/2025`), Metadaten aus Referenz und Paketen |
| `…/processed/papers_gremien.parquet` (Schritt `bodies`) | `id`, `gremium`, `gremium_art` | eine Zeile je Dokument | Drucksachennummer und Beratungsfolge (Punkt 58) |
| `…/processed/wahlbezirke_auswertung.parquet` (Schritt `results`) | `wahlkreis_id`, `paper_ids` (Vereinigung je Bezirk), `anzahl_treffer`, `Wahlberechtigte_insgesamt`, `trefferquote`, `wahlbeteiligung` | 41 Zeilen; 29 330 Treffer (Hauptperiode), 36 788 (2014 bis 2020) | Kette der Arbeit, Regeln von Punkt 44 |
| `messdaten/rohtext/<profil>.parquet` (Phase 0) | `name`, `text` (mit Groß- und Kleinschreibung und Umbrüchen), `pages` | 19 092 / 22 116 Texte | nur für die Ausschnitte der Kodieraufgaben, lokal |

Lizenz und Veröffentlichung: die Texte liegen schon als Pakete im Repo (Punkt 68); dieses Vorhaben
erzeugt nur Kennungen und Zahlen. Die Ausschnitte für die Kodierer bleiben lokal (Plan § 4).

Ein Dokument ohne Text (75 in der Hauptperiode, darunter Paper ohne Hauptdatei) oder mit weniger
als fünf Wörtern (2 in der Hauptperiode, 129 in der Periode 2014 bis 2020, § 3.6) hat keine Shingles
und bleibt ein Einzeldokument.

## 3. Messung

### 3.1 Vorgehen

1. Je Dokument die Menge der **Wort-Shingles** der Länge k = 5 über `\w+`-Token des Korpustexts;
   jedes Token als BLAKE2b-Hash (8 Byte), die fünf Hashes mit splitmix64 verkettet, davon die oberen
   32 Bit. Damit hängt nichts am Zufall des Interpreters (`PYTHONHASHSEED`) oder an der
   Korpusreihenfolge.
2. **MinHash** mit 128 Hashfunktionen `h_i(x) = (a_i·x + b_i) mod p`, p = 4 294 967 291 (größte
   Primzahl unter 2³²; `a·x + b` passt in uint64), a und b aus `numpy.random.default_rng(13)`.
3. **LSH** in 32 Bändern zu 4 Zeilen: ein Paar ist Kandidat, wenn es in einem Band dieselben vier
   Werte trägt. Für jeden Kandidaten die **exakte** Jaccard-Ähnlichkeit der Shingle-Mengen; die
   Schätzung aus der Signatur dient nur der Kandidatensuche.
4. **Familien** sind die Zusammenhangskomponenten des Graphen der Paare mit J ≥ τ
   (`scipy.sparse.csgraph.connected_components`).
5. **Gegenprobe**: dieselben Signaturen in 64 Bändern zu 2 Zeilen (Schwelle ≈ 0,12) finden fast
   jedes Paar ab J = 0,3; daran misst sich, was 32×4 verliert.
6. **Empfindlichkeit**: je Wahlbezirk die Zahl der Familien unter seinen Dokumenten mit Treffer statt
   der Zahl der Dokumente, geteilt durch die Wahlberechtigten, durch dieselbe `regression_pair` wie
   Tabelle 5 (Ausreißer aus `analysis.exclude_districts`), dazu Spearmans ρ zur heutigen Quote.

### 3.2 Exakte Dubletten

In der Hauptperiode tragen nur **2 Paare (4 Dokumente)** denselben Text: BV8/214/2024 und
BV8/032/2025 (ein SPD-Antrag zur Sanierung des Auguste-Leven-Wegs, wieder eingebracht) und
RAT/014/2022/1 und RAT/014/2022/2 (zwei Fassungen der Änderung der Zuständigkeitsordnung). Für die
Periode 2014 bis 2020 siehe § 3.6.

### 3.3 Parameter und Kurven

**Shingle-Länge k.** Die Texte sind kurz (Median **209** Shingles je Dokument, zusammen 6 300 495 in
der Hauptperiode). Kurze Shingles machen Texte aus demselben Formular ähnlich, lange machen jede
Änderung teuer: ein geändertes Wort nimmt bis zu k Shingles. Gemessen, je mit eigenem MinHash, als
Zahl der Kanten und als Jaccard der Kantenmengen zu k = 5:

| k | Kanten τ = 0,7 | τ = 0,8 | τ = 0,9 | Überlappung mit k = 5 bei 0,7 / 0,8 / 0,9 | Dokumente in Familien bei τ = 0,9 |
|---|---|---|---|---|---|
| 3 | 1 060 | 529 | 133 | 0,59 / 0,48 / 0,70 | 172 |
| 5 | 628 | 256 | 93 | 1 / 1 / 1 | 103 |
| 8 | 351 | 133 | 27 | 0,56 / 0,52 / 0,29 | 51 |

k = 3 nimmt bei τ = 0,9 vierzig Kanten mehr (133 statt 93), k = 8 verliert fast drei Viertel (27
statt 93): kurze Shingles lassen gemeinsamen Formulartext stärker zählen, lange bestrafen jedes
geänderte Wort. **k = 5** liegt dazwischen. Dass die Kantenmengen zwischen den k so verschieden
sind, sagt zugleich, dass Schwelle τ und Länge k zusammen gewählt werden müssen und dass jede Zahl
in diesem Dokument für k = 5 gilt.

**Permutationen und Bänder.** Die S-Kurve gibt die Wahrscheinlichkeit, dass ein Paar mit Jaccard s
Kandidat wird:

| b × r | Schwelle (1/b)^(1/r) | s = 0,3 | 0,4 | 0,5 | 0,6 | 0,7 | 0,8 | 0,9 |
|---|---|---|---|---|---|---|---|---|
| 16 × 8 | 0,71 | 0,001 | 0,010 | 0,061 | 0,237 | 0,613 | 0,947 | 1,000 |
| **32 × 4** | 0,42 | 0,229 | 0,564 | 0,873 | 0,988 | 1,000 | 1,000 | 1,000 |
| 64 × 2 | 0,12 | 0,998 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 |

32 × 4 findet jedes Paar ab 0,7 sicher und hält die Kandidaten klein (8 568 gegen 182 779 bei
64 × 2); 16 × 8 verlöre bei τ = 0,7 fast vier von zehn Paaren. Gemessen gegen die Gegenprobe,
je Band der exakten Jaccard:

| exakte Jaccard | gefunden von 32 × 4 |
|---|---|
| 0,3 bis 0,4 | 1 857 / 5 509 = 0,337 |
| 0,4 bis 0,5 | 1 192 / 1 602 = 0,744 |
| 0,5 bis 0,6 | 832 / 867 = 0,960 |
| 0,6 bis 0,7 | 533 / 533 = 1,000 |
| 0,7 bis 0,8 | 372 / 372 = 1,000 |
| ab 0,8 | 256 / 256 = 1,000 |

Die gemessenen Anteile passen zur Kurve, gemittelt über die Breite jedes Bandes; für jede Schwelle
ab 0,6 geht nichts verloren, und 32 × 4 findet kein Paar ab 0,3, das die Gegenprobe nicht auch
fände. 128 Permutationen geben der Schätzung einen Standardfehler von √(J(1−J)/128) = 0,035 bei
J = 0,8 und 0,027 bei 0,9 (64: 0,050 und 0,037; 256: 0,025 und 0,019); weil die Familien an der
exakten Jaccard hängen, entscheidet dieser Fehler nur über die Kandidaten, und die Tabelle zeigt,
dass 128 reichen.

**Schwelle τ** (k = 5, 32 × 4, exakte Jaccard, Anteil am ganzen Korpus von 19 108):

| τ | Kanten | Familien | Dokumente in Familien | größte Familie | Größen 2 / 3 / 4 / 5+ |
|---|---|---|---|---|---|
| 0,50 | 1 993 | 555 | 1 546 = 8,1 % | 36 | 399 / 72 / 37 / 47 |
| 0,60 | 1 161 | 405 | 1 070 = 5,6 % | 21 | 303 / 46 / 25 / 31 |
| 0,70 | 628 | 270 | 667 = 3,5 % | 15 | 211 / 29 / 13 / 17 |
| 0,80 | 256 | 143 | 326 = 1,7 % | 10 | 125 / 10 / 3 / 5 |
| 0,85 | 140 | 81 | 179 = 0,9 % | 10 | 73 / 5 / 2 / 1 |
| **0,90** | 93 | 47 | 103 = 0,5 % | 10 | 45 / 1 / 0 / 1 |
| 0,95 | 16 | 14 | 29 = 0,2 % | 3 | 13 / 1 / 0 / 0 |

**Was die Stufen enthalten, ohne Kodierung.** Labels aus den Metadaten (Plan § 2.6, Weg 2) sind
keine Validierung, aber sie zeigen, wie sich die Stufen unterscheiden. Gleicher Titel ist weder
nötig (eine Fortschreibung ändert ihn) noch hinreichend (ein wiederkehrender Bericht behält ihn);
dieselbe Grundnummer (`X` und `X/1`) ist ein fast sicheres Zeichen für dieselbe Sache:

| Stufe (exakte Jaccard) | Paare | Titel gleich | Grundnummer gleich | ≤ 31 Tage Abstand | beide mit Berichtswort im Titel |
|---|---|---|---|---|---|
| 0,95 bis 1 | 16 | 93,8 % | 31,2 % | 43,8 % | 0,0 % |
| 0,90 bis 0,95 | 77 | 92,2 % | 22,1 % | 77,9 % | 1,3 % |
| 0,85 bis 0,90 | 47 | 72,3 % | 19,1 % | 42,6 % | 23,4 % |
| 0,80 bis 0,85 | 116 | 49,1 % | 9,5 % | 35,3 % | 29,3 % |
| 0,70 bis 0,80 | 372 | 37,1 % | 5,6 % | 25,8 % | 38,4 % |
| 0,50 bis 0,70 | 1 400 | 26,6 % | 1,6 % | 26,4 % | 23,3 % |
| 0,30 bis 0,50 | 7 111 | 11,1 % | 0,3 % | 23,9 % | 4,9 % |

(„Berichtswort": Halbjahr, Quartal, Kalenderwoche, Jahresbericht, Controlling, Beschlusskontrolle.)
Ab 0,9 tragen über 90 % der Paare denselben Titel und kaum eines ein Berichtswort; unter 0,85 kippt
das: der Anteil gleicher Titel halbiert sich, und ein Drittel der Paare sind Berichte, die sich
wiederholen. Zwischen 0,85 und 0,9 liegt die Kante, an der „gleiche Form" die „gleiche Sache"
überholt.

### 3.4 Familien: welche Dokumente, welche Gremien

**Die Schwelle τ = 0,9 ist vorab gewählt** — nach dem Blick auf Beispielpaare je Stufe und auf die
Titel (oben), bevor die Typen der Familien und die Empfindlichkeit gerechnet waren. Die Kurve des
Familienanteils (Tabelle in § 3.3) kannte ich da schon; deshalb steht jede Zahl auch für 0,8 und 0,7
daneben, und die endgültige Schwelle setzt die Kodierung nach der Regel in § 5.

Die Typen unten sind eine **beschreibende Regel**, keine Validierung (`family_kind` im Skript): gleiche
Grundnummer → Fortschreibung; mehrere Gremien → Verteilervorlage (Verwaltung) oder gleicher Antrag in
mehreren Gremien (Antrag, Anfrage); ein Gremium und Abstand über 300 Tage oder ein Berichtswort im
Titel → wiederkehrend; sonst Wiedervorlage.

| Typ | τ = 0,9: Familien / Dokumente | τ = 0,8 | τ = 0,7 |
|---|---|---|---|
| Fortschreibung (`/1`, `/2` derselben Nummer) | 22 / 44 | 40 / 81 | 60 / 122 |
| Wiedervorlage im selben Gremium (≤ 300 Tage) | 12 / 25 | 30 / 63 | 61 / 138 |
| Verteilervorlage an mehrere Gremien | 9 / 26 | 18 / 54 | 28 / 89 |
| wiederkehrender Bericht oder Formular | 3 / 6 | 44 / 106 | 93 / 255 |
| gleicher Antrag oder gleiche Anfrage in mehreren Gremien | 1 / 2 | 11 / 22 | 28 / 63 |
| **zusammen** | **47 / 103** | **143 / 326** | **270 / 667** |

Von τ = 0,9 zu 0,7 wächst vor allem der wiederkehrende Bericht: von 6 auf 255 Dokumente. Beispiele bei
τ = 0,7: der Controllingbericht des Stadtentwässerungsbetriebs (15 Dokumente, darunter
SEBD/017/2021 und SEBD/031/2025), die „Beschlusskontrolle des Rates" (9, RAT/414/2020 bis
RAT/283/2025). Das sind nach dem Codebuch verschiedene Sachen (andere Berichtszeiträume), und sie
machen die Familien bei niedriger Schwelle groß.

Bei τ = 0,9 sind alle 47 Familien **Cliquen** (jedes Paar ≥ 0,9, kleinste Ähnlichkeit innerhalb
0,901): die Zusammenhangskomponenten verketten nichts. Bei 0,8 sind es 139 von 143 (kleinste 0,745),
bei 0,7 242 von 270 (kleinste 0,537).

**Die Fragen des Briefings:**

- **Verteilervorlagen** gibt es, aber wenige: 9 Familien mit 26 Dokumenten bei τ = 0,9. Die größte ist
  der „Sachstandsbericht zum Lärmaktionsplan IV" an alle zehn Bezirksvertretungen (BV1/226/2024,
  BV2/221/2024, BV3/181/2024, BV4/182/2024, BV5/136/2024, BV6/178/2024, BV7/160/2024, BV8/176/2024,
  BV9/172/2024, BV10/141/2024); bei 0,7 kommt „Umsetzung stationsbasierter Sharing-Angebote" an
  sieben Bezirksvertretungen dazu. Von 2 699 BV-Informationsvorlagen liegen bei τ = 0,9 nur 2 in
  einer Familie (die zehn Lärmaktionsplan-Vorlagen tragen die Art „Informationsvorlage").
- **Wiedervorlagen**: unverändert wieder eingebrachte Anträge (BV8/214/2024 → BV8/032/2025, ein
  Jugendfonds-Antrag JURAT/034/2024, JURAT/058/2024, JURAT/026/2025) und vor allem
  **Fortschreibungen derselben Nummer**, die größte Gruppe bei τ = 0,9 (22 von 47 Familien).
  Nach der Nummer allein gibt es 190 Dokumente mit Ergänzungszähler, 128 davon mit ihrer
  Grundnummer im Korpus; ihre Jaccard zur Grundnummer liegt im Median bei 0,621, nur 18 erreichen
  0,9, 57 erreichen 0,7, und 52 liegen unter 0,5. Eine Fortschreibung ist also meist deutlich
  geändert; der Text findet sie bei τ = 0,9 selten, die Nummer immer.
- **Musteranträge** zeigen sich in den Hauptdateien kaum: ein gleicher Antrag in mehreren Gremien ist
  bei τ = 0,9 einmal da (SENR/003/2023 und RAT/333/2023, Münstertherme), bei 0,7 28-mal; die
  Beispiele sind derselbe Antrag in mehreren Ausschüssen (SPD/Volt, Menstruationsartikel, in
  RAT/367/2021, AÖE/041/2021, SPOA/048/2021, JHA/102/2021, OVA/096/2021; eine Anfrage von CDU und
  Grünen in OVA/009/2024, SPOA/013/2024, INTR/005/2024), nicht eine Vorlage einer Partei für
  verschiedene Bezirke. Ein Musterantrag, der in jedem Bezirk den eigenen Ort nennt, läge vermutlich
  unter 0,9 und wäre nach Codebuch ohnehin „andere Sache"; ihn sucht Vorhaben 23.

**Dokumentarten** (τ = 0,9; in Klammern der Anteil an allen Dokumenten der Art): Beschlussvorlage 38
(1,0 %), Informationsvorlage 22 (1,7 %), Antrag 15 (0,5 %), Bedarfsbeschluss 8 (10,3 %), A+F Beschluss
6 (4,1 %), Antrag DIE PARTEI-Klima-Fraktion 6 (4,0 %), Anfrage 4 (0,2 %). Nach **Gremienart**:
Bezirksvertretung 44, Ausschuss 40, Rat 13, Beirat 6. Keine Art und kein Gremium sticht so heraus,
dass eine Zählung je Art oder Gremium (Option 05) sich merklich verschöbe.

### 3.5 Empfindlichkeit: Treffer je Wahlbezirk und Tabelle 5

Jede Familie zählt je Wahlbezirk einmal: ein Wahlbezirk, den k Dokumente einer Familie treffen,
bekommt für sie 1 statt k. Als Gewicht geschrieben (Form von `analysis/weights.py`) trägt jedes Paar
(Wahlbezirk, Dokument) 1/k; das Skript prüft, dass die Summe gleich der Zahl der Familien ist.

| | heute | τ = 0,9 | τ = 0,8 | τ = 0,7 |
|---|---|---|---|---|
| Treffer zusammen | 29 330 | 29 118 (−0,7 %) | 28 891 (−1,5 %) | 28 668 (−2,3 %) |
| Verlust je Wahlbezirk, Median | – | 0,7 % | 1,3 % | 2,1 % |
| größter Verlust | – | 1,4 % (WB 13, 555 → 547) | 3,2 % (WB 13, 555 → 537) | **5,05 %** (WB 13, 555 → 527) |
| Wahlbezirke mit ≥ 5 % Verlust | – | 0 | 0 | 1 |
| Steigung, alle 41 | 79,4275 | 81,9084 | 83,9331 | 86,3818 |
| r / p, alle 41 | 0,1901 / 0,23383 | 0,1943 / 0,22359 | 0,1970 / 0,21691 | 0,2012 / 0,20717 |
| Steigung, ohne 1 und 10 | 214,9840 | 220,2867 | 223,7635 | 228,0886 |
| r / p, ohne 1 und 10 | 0,3363 / 0,03635 | 0,3422 / 0,03299 | 0,3453 / 0,03134 | 0,3505 / 0,02868 |
| ρ zur heutigen Quote | 1 | 0,9993 | 0,9993 | 0,9977 |

Wahlbezirk 13 verliert bei jeder Schwelle am meisten; 2 und 14 stehen immer unter den ersten fünf
(τ = 0,9: 13, 2, 14, 12, 15; τ = 0,7: 13, 2, 3, 14, 17). Die Steigung wächst um 3 % (τ = 0,9) bis 9 %
(τ = 0,7), mehr als ein gleichmäßiger Abschlag allein erklärte (0,7 % beziehungsweise 2,3 % weniger
Treffer); die Bezirke verlieren also nicht genau gleich viel, aber der Rang bleibt fast gleich
(ρ ≥ 0,998), und p bewegt sich in der dritten Stelle. **Keine Schlussfolgerung der Seite hängt an den
Dubletten.**

### 3.6 Periode 2014 bis 2020 und über die Grenzen der Perioden

**Periode 2014 bis 2020** (22 215 Dokumente, 21 709 mit Shingles). Exakte Dubletten unter den Texten
mit mindestens fünf Wörtern: 10 Gruppen mit 24 Dokumenten; dazu 129 Texte mit weniger als fünf
Wörtern (beim Ansehen der Gruppen gleichen Texts: Scans, deren Text nur aus Leerzeichen besteht;
sie bleiben Einzeldokumente). Familien: τ = 0,7: 212 mit 522 Dokumenten (2,3 %); τ = 0,8: 118 mit
265 (1,2 %); **τ = 0,9: 49 mit 109 (0,5 %)**, davon 23 Fortschreibungen (47 Dokumente), 10
Verteilervorlagen (28), 10 Wiedervorlagen (20), 4 wiederkehrende (10), 2 gleiche Anträge in mehreren
Gremien (4); 48 der 49 sind Cliquen (kleinste Ähnlichkeit 0,873). Die größte Verteilervorlage ist der
„Sachstandsbericht zu Fahrradabstellanlagen für die Stadtbezirke 1-10" (sieben Dokumente, 2019).
Empfindlichkeit bei τ = 0,9: Treffer 36 788 → 36 546 (−0,7 %), größter Verlust 1,61 % (WB 38,
497 → 489), kein Wahlbezirk mit 5 %; Tabelle 5 über alle 41 Steigung 64,8653 → 65,5096, p 0,13605 →
0,13213; ohne 1 und 10 Steigung 81,7005 → 82,3821, p 0,08334 → 0,08052; ρ = 0,9998. Die Periode
zeigt dasselbe Bild wie die Hauptperiode, fast Zahl für Zahl.

**Laufende Periode ab 2025** (4 095 Dokumente, 4 075 mit Shingles): keine exakte Dublette; τ = 0,7:
29 Familien mit 60 Dokumenten (1,5 %), τ = 0,8: 13 mit 28 (0,7 %), τ = 0,9: 5 mit 10 (0,2 %). Eine
Regression gibt es für die laufende Periode nicht.

**Über die Grenzen der Perioden** (alle drei Korpora zusammen, 45 418 Dokumente, keine ID in zwei
Perioden; ein gemeinsames MinHash, gezählt nur Paare aus verschiedenen Perioden):

| τ | Paare über eine Grenze | Dokumente | 2014–2020 × 2020–2025 | 2020–2025 × ab 2025 |
|---|---|---|---|---|
| 0,7 | 84 | 126 | 46 | 38 |
| 0,8 | 29 | 45 | 18 | 11 |
| 0,9 | 3 | 6 | 0 | 3 |

Über die Wahl 2020 hinweg liegt **kein** Paar ab 0,9. Über die Wahl 2025 sind es drei
Paare mit gleichem Titel, zwei davon Fortschreibungen derselben Nummer, deren Fassungen auf beiden
Seiten des Periodenbeginns liegen: BV6/092/2025 und BV6/092/2025/1 (eine Anfrage, J = 1,000),
BAU/009/2025 und BAU/009/2025/1 (0,905), dazu BV7/037/2024 und BV7/148/2025 (Zulassung einer
Vertretung einer betroffenen Bevölkerungsgruppe, 0,916). Wiedervorlagen über die Wahl sind also kein
Thema für die Zählung; ob Anträge einer früheren Periode in neuer Fassung wiederkommen (18 Paare über
die Wahl 2020 ab 0,8, 46 ab 0,7), ist eine Frage für Vorhaben 23.

## 4. Validierung

**Einheit**: ein Dokumentpaar. **Codebuch**: [`validierung/13-dubletten/codebuch.toml`](../../validierung/13-dubletten/codebuch.toml),
vier Optionen mit Definition und Beispiel aus den Daten:

| Code | Bedeutung | für die Präzision |
|---|---|---|
| `gleich` | derselbe Text zur selben Sache; Unterschiede nur in Kopf und Rahmen (Nummer, Datum, adressiertes Gremium) | richtig |
| `fast_gleich` | weitgehend derselbe Text zur selben Sache mit inhaltlicher Änderung (Fassung `/1`, ergänzter Absatz, geänderter Beschlussvorschlag) | richtig |
| `aehnlich_andere_sache` | gleiche Vorlage oder viel Standardtext, aber andere Sache (anderer Berichtszeitraum, Ort, Zuschussempfänger, andere Person bei einer Ersatzwahl) | falsch |
| `verschieden` | nichts gemeinsam außer Floskeln | falsch |

Die strenge Lesart (nur `gleich` ist richtig) steht im Codebuch daneben.

**Stichprobe** ([`stichprobe.csv`](../../validierung/13-dubletten/stichprobe.csv), nur IDs, Stufe,
Größe der Stufe und Jaccard): 200 Paare, geschichtet nach der exakten Jaccard, Seed 13, aus der
Vereinigung der Kandidaten von 32 × 4 und 64 × 2. Dicht, wo die Schwelle liegen kann; die Stufe ab
0,95 ganz:

| Stufe (exakte Jaccard) | Paare in der Stufe | gezogen |
|---|---|---|
| 0,95 bis 1 | 16 | 16 (alle) |
| 0,90 bis 0,95 | 77 | 42 |
| 0,85 bis 0,90 | 47 | 38 |
| 0,80 bis 0,85 | 116 | 38 |
| 0,70 bis 0,80 | 372 | 34 |
| 0,50 bis 0,70 | 1 400 | 20 |
| 0,30 bis 0,50 | 7 111 | 12 |
| **zusammen** | 9 139 | **200** |

Die Reihenfolge ist gemischt, damit kein Kodierer die Stufe aus der Position liest; die Kodieraufgaben
tragen weder Jaccard noch Stufe.

**Kodieraufgaben**: `/media/konrad/xtraspace/georep/messdaten/kodierung/13-dubletten/aufgaben.jsonl`,
eine Zeile je Paar mit `paar`, den Optionen, dem Pfad des Codebuchs und je Dokument `id`, `drucksache`,
`titel`, `datum`, `art`, `gremium`, `seiten`, `zeichen` (volle Länge) und `ausschnitt` (Anfang des
Rohtexts aus der Messdatei von Phase 0, höchstens 1 500 Zeichen; wo die Messdatei fehlt, der
kleingeschriebene Text, `quelle` sagt welcher). Antwort je Paar: `{"paar", "code", "begruendung"}`.
Das Format ist vorläufig, bis F4 seinen Rahmen hat.

**Maße, die der Supervisor nach der Kodierung rechnet**: Krippendorffs α zwischen den beiden
Kodierern (nominal über die vier Codes, Plan § 2.6 verlangt für Stufe 3 α ≥ 0,8); Präzision je Stufe
mit Wilson-Intervall; Präzision ab τ als gewichtetes Mittel der Stufen ab τ mit dem Gewicht
Grundgesamtheit / gezogen. Zur Größenordnung (Rechenbeispiel des Skripts): von den 58 gezogenen
Paaren ab 0,9 wären bei 56 richtigen (96,6 %) die Grenzen des Wilson-Intervalls 0,883 und 0,990; die
Stichprobe zeigt ein klares Verfehlen sicher, ein knappes Erreichen nur mit Unsicherheit.

**Was sich ohne Kodierung sagen lässt.** Zwei Dinge tragen ohne Kodierung: (1) Familien aus
Fortschreibungen derselben Nummer sind fast sicher dieselbe Sache (22 von 47 Familien bei τ = 0,9);
(2) jede Familie bei τ = 0,9 ist eine Clique. Dagegen liegt das Hauptproblem — gleiche Form, andere
Sache — genau in den Stufen 0,7 bis 0,85 (siehe die Hinweistabelle in § 3.3 und die Typen in § 3.4).
Ein Beispiel aus der Stichprobe: RAT/554/2021 und RAT/555/2021, Ersatzwahl in den Aufsichtsrat der
Düsseldorf Tourismus GmbH und der Düsseldorf Marketing GmbH, wortgleich bis auf den Namen der
Gesellschaft.

### 4.1 Kodierung und Präzision (2026-11-23)

Zwei Kodier-Agenten (A, B) haben die 200 Paare unabhängig nach dem Codebuch kodiert, ohne Jaccard
und Stufe zu sehen; die 7 Uneinigkeiten hat ein Schlicht-Agent entschieden. Kodierer und Schlichter
sind dasselbe Modell (Frage 19 an Konrad, offen): das ist kein menschlicher Goldstandard, sondern
die Übereinstimmung mit einem stärkeren Modell (Plan § 2.6). Labels:
[`labels.csv`](../../validierung/13-dubletten/labels.csv) (Werte als JSON, ohne Ausschnitte und
Begründungen); Antworten, Uneinigkeiten und Schlichtung mit Begründung liegen lokal unter
`messdaten/kodierung/13-dubletten/`.

**Übereinstimmung.** Code: 193 von 200, Krippendorffs α = **0,941** (nominal, vier Codes); „Familie"
(`gleich` oder `fast_gleich`) ja oder nein: 197 von 200, α = **0,970**. Beides liegt über 0,8, der
Grenze aus Plan § 2.6; das Codebuch ist scharf genug. A vergab 108 × `aehnlich_andere_sache`,
63 × `gleich`, 29 × `fast_gleich`, B 105 / 65 / 30; `verschieden` vergab keiner (die Stichprobe
beginnt bei J = 0,3). Geschlichtet: p013, p048 und p052 zu `aehnlich_andere_sache` (ein an ein
Haushaltsjahr gebundener Antrag oder Zuschuss ist je Haushaltsjahr eine eigene Sache, Regel R-a),
p025, p041 und p157 zu `gleich`, p105 zu `fast_gleich`. Endlabels: 108 `aehnlich_andere_sache`,
64 `gleich`, 28 `fast_gleich`.

**Präzision je Stufe** (richtig: `gleich` oder `fast_gleich`; streng: nur `gleich`; Wilson 95 %):

| Stufe (exakte Jaccard) | Paare (N) | kodiert (n) | richtig | Präzision [Wilson] | streng | gleiche Sache, hochgerechnet |
|---|---|---|---|---|---|---|
| 0,95 bis 1 | 16 | 16 (alle) | 13 | 0,812 [0,570; 0,934] | 0,688 | 13 |
| 0,90 bis 0,95 | 77 | 42 | 41 | **0,976** [0,877; 0,996] | 0,857 | 75 |
| 0,85 bis 0,90 | 47 | 38 | 13 | 0,342 [0,212; 0,501] | 0,211 | 16 |
| 0,80 bis 0,85 | 116 | 38 | 11 | 0,289 [0,170; 0,448] | 0,132 | 34 |
| 0,70 bis 0,80 | 372 | 34 | 11 | 0,324 [0,191; 0,492] | 0,088 | 120 |
| 0,50 bis 0,70 | 1 400 | 20 | 2 | 0,100 [0,028; 0,301] | 0,050 | 140 |
| 0,30 bis 0,50 | 7 111 | 12 | 1 | 0,083 [0,015; 0,354] | 0 | 593 |

**Präzision ab τ** (Mittel der Stufen ab τ, gewichtet mit N; das Intervall überträgt die
Wilson-Grenzen der Stufen mit denselben Gewichten, eine ganz gezogene Stufe ohne Unsicherheit —
konservativ):

| τ | Präzision | Intervall | streng | ≥ 0,95? |
|---|---|---|---|---|
| 0,70 | 0,411 | [0,289; 0,554] | 0,215 | nein |
| 0,80 | 0,538 | [0,430; 0,645] | 0,399 | nein |
| 0,85 | 0,745 | [0,646; 0,809] | 0,621 | nein |
| 0,90 | **0,948** | [0,866; 0,964] | 0,828 | nein, knapp |
| 0,95 | 0,812 | (alle kodiert) | 0,688 | nein |

**Was die Labels zeigen.**

- **Eine scharfe Kante bei 0,9**, wie die Hinweistabelle in § 3.3 sie erwarten ließ: zwischen 0,90
  und 0,95 sind 41 von 42 Paaren dieselbe Sache, darunter ist es etwa eines von drei, unter 0,7
  eines von zehn.
- **Wortgleich ist nicht gleich.** Die Stufe ab 0,95 ist schlechter als die darunter: drei ihrer 16
  Paare sind die Jugendfonds-Anträge JURAT/034/2024, JURAT/058/2024 und JURAT/026/2025 (J = 1,000),
  deren Hauptdatei dasselbe Deckblatt ist; der Antrag selbst steht anderswo, und beide Kodierer
  sahen drei verschiedene Anträge. Das vierte falsche Paar ab 0,9 ist ein Jahresbericht
  (OVA/099/2020 und OVA/052/2021, „Qualitätsbericht der Rheinbahn", 0,901).
- **Was über die Metadaten trägt** (ab 0,7, ungewichtet, 168 Paare; ein Hinweis für eine Fassung
  2, keine Messung eines Verfahrens): gleiche Grundnummer 25 von 25 richtig; gleicher Titel 82 von
  115, verschiedener Titel 7 von 53; ein Berichtswort in beiden Titeln 1 von 30; Abstand bis 31 Tage
  55 von 85, darüber 34 von 83.

**Wirkung auf die Zählung je Wahlbezirk danach.** Eine validierte Schwelle gibt es nicht; die Zahlen
unten ordnen ein, wie groß der Unterschied wäre.

- **An der besten Grenze, τ = 0,9** (Präzision 0,948): Treffer 29 330 → 29 118 (−0,7 %), größter
  Verlust 1,4 % (WB 13, 555 → 547), kein Wahlbezirk mit 5 %, ρ = 0,9993, p ohne 1 und 10 0,033
  (§ 3.5). Etwa jede zwanzigste Kante dort ist falsch, die wahre Wirkung also etwas kleiner.
- **Obergrenze über alle Kanten ab 0,5**, vier von fünf davon falsch: −3,7 %, größter Verlust
  6,13 % (WB 24 und WB 13), 5 Wahlbezirke mit mindestens 5 %, p ohne 1 und 10 0,027, ρ = 0,9984. Die
  richtigen Kanten allein sind eine Teilmenge und wirken höchstens so stark.
- **Geschätzt, wenn nur die richtigen Kanten zählten**: jede Kante bleibt mit der Präzision ihrer
  Stufe stehen, 200 Ziehungen, Seed 13; das unterstellt, dass richtige und falsche Kanten sich nicht
  nach Wahlbezirk unterscheiden, und ist darum eine Größenordnung. Ab 0,5: 2,81 % der Dokumente in
  Familien [2,58; 3,04], Treffer −1,60 % [1,35; 1,88], größter Verlust 3,38 % [2,80; 4,19], ein
  Wahlbezirk mit 5 % nur in einzelnen Ziehungen (im Mittel 0,01). Ab 0,3: 5,99 % der Dokumente,
  Treffer −2,87 %
  [2,49; 3,26], größter Verlust 5,60 % [4,80; 6,67], im Mittel 1,7 Wahlbezirke mit 5 %; das hängt
  an einem richtigen von 12 kodierten Paaren der Stufe 0,3 bis 0,5 (Wilson 0,015 bis 0,354), die
  Intervalle in Klammern enthalten diese Unsicherheit nicht.

Dieselbe Sache gibt es also auch unter 0,9 — hochgerechnet rund 900 Paare zwischen 0,3 und 0,9,
mit großer Unsicherheit —, aber die Textähnlichkeit trennt sie dort nicht von Formularen und
wiederkehrenden Berichten (Präzision 0,29 bis 0,34 zwischen 0,7 und 0,9). Eine Familienvariante über
J ≥ τ kann sie nicht tragen; was sie mit der geforderten Präzision trägt (ab 0,9), ändert die
Zählung um weniger als anderthalb Prozent je Wahlbezirk.

## 5. Urteil gegen das Kriterium

**Kriterium (Briefing, unverändert):** Präzision ≥ 0,95; weiter, wenn mindestens 3 % der Dokumente in
Familien liegen oder ein Wahlbezirk mindestens 5 % seiner Treffer verliert; sonst ist „es gibt kaum
Dubletten" der Befund.

**Regel für die Schwelle, vorab festgelegt** (auch im Codebuch): τ* ist die kleinste der Grenzen
0,70; 0,80; 0,85; 0,90; 0,95, für die die gewichtete Präzision über alle Paare mit J ≥ τ* mindestens
0,95 ist. Erreicht keine Grenze 0,95, ist das Kriterium verfehlt. Das Kriterium wird dann bei τ*
geprüft:

| τ* | Präzision (§ 4.1) | Dokumente in Familien | größter Verlust eines Wahlbezirks | „weiter"? |
|---|---|---|---|---|
| 0,70 | 0,411 | 3,5 % | 5,05 % (WB 13) | ja, knapp beides |
| 0,80 | 0,538 | 1,7 % | 3,2 % | nein |
| 0,85 | 0,745 | 0,9 % | ≤ 3,2 % | nein |
| 0,90 | 0,948 | 0,5 % | 1,4 % | nein |
| 0,95 | 0,812 | 0,2 % | ≤ 1,4 % | nein |

**Urteil nach der Kodierung: verwerfen.** Keine der fünf Grenzen erreicht die Präzision 0,95; die
beste ist τ = 0,9 mit 0,948 [0,866; 0,964]. Nach der Regel ist das Kriterium damit verfehlt, ein
τ* gibt es nicht, und die Gewichtsvariante `familie` entsteht nicht. Das Urteil hängt nicht an der
knappen Zahl bei 0,9: läge die Präzision dort über 0,95, wäre τ* = 0,9, und dort liegen 0,5 % der
Dokumente in Familien und kein Wahlbezirk verliert mehr als 1,4 % — beide Schwellen für „weiter"
(3 % und 5 %) sind verfehlt. Nur τ* = 0,7 hätte zu „weiter" geführt, und dort ist die Präzision
0,411. Der Befund ist „es gibt kaum Dubletten": genauer, kaum Dubletten, die sich am Text mit der
geforderten Sicherheit erkennen lassen, und ihre Wirkung auf die Zählung liegt unter dem Wechsel des
Extraktors (Punkt 68, 29 010 → 29 330 Treffer). Die vorläufige Einschätzung vor der Kodierung
(verwerfen, weil ab 0,7 wiederkehrende Berichte die Familien füllen) hat die Kodierung bestätigt.

**Was bleibt:**

- der Befund für `decisions.md` (Zeile für ein verworfenes Vorhaben, Plan § 8): die Trefferquote
  zählt kaum Dubletten (0,5 % der Dokumente bei τ = 0,9, Präzision 0,948; in beiden Perioden
  gleich); geschätzt verschiebt auch die Dublette in der Sache die Treffer je Bezirk nur um einige
  Prozent (§ 4.1);
- der MinHash-Prototyp im Messskript als Ausgangspunkt für Vorhaben 23 (Textübernahme), das ihn mit
  niedrigerer Schwelle und lokaler Ausrichtung braucht; die Zahlen hier (Kandidaten 32 × 4 gegen
  64 × 2, k gegen τ) ersparen dort die Parametersuche;
- für Vorhaben 14: Fortschreibungen derselben Nummer sind die größte Familienart; die Nummer allein
  findet alle 128 mit Grundnummer im Korpus, der Text bei τ = 0,9 nur 18 davon (§ 3.4). Paare ab 0,9
  tragen zu über 90 % denselben Titel (Hinweistabelle in § 3.3), ein Merkmal, das 14 für
  Verteilervorlagen ohne Textvergleich lesen kann. Beides ist eine Synergie-Notiz für den Supervisor
  (§ 10).

## 6. Bauplan Stufe 2 (falls das Urteil nach der Kodierung „bauen" lautet)

Das Urteil lautet „verwerfen" (§ 5). Der Bauplan bleibt als Dokumentation stehen, für den Fall, dass
eine Fassung 2 (§ 9, 13.7) neu gemessen wird, und als Vorlage für den Kandidatenschritt von
Vorhaben 23.

**Beitrag `families`** nach F2 (`georep/enrich/families.py`), reine Funktionen in
`georep/analysis/families.py`: `Shingler` (Token-Hash BLAKE2b, splitmix64, 32 Bit), `signatures`,
`lsh_candidates`, `jaccard`, `family_labels`. Eigene typisierte Umsetzung mit numpy statt einer
Bibliothek: `datasketch` (2.0.0, MIT, numpy und scipy) trägt keinen Klassifikator „Typing :: Typed"
(PyPI, 2026-11-23) und bräuchte unter `mypy --strict` einen Stub oder eine Ausnahme wie `scipy`;
seine Hashfunktion und sein Speicherformat wären eine zweite Stelle, an der die Ergebnisse von einer
Version abhängen, und die Pinning-Regeln aus `CLAUDE.md` kämen für ein neues Paket dazu. Die eigene
Umsetzung ist im Messskript rund 100 Zeilen, besteht `mypy --strict` schon heute und braucht nur numpy
und scipy, die im Lockfile stehen.

**Settings** (Anhängeregel aus F2): ein Modell `FamiliesSettings` vor `class Settings`, ein Feld
`families` am Ende, ein Block am Ende von `defaults.toml`:

```toml
# --- Vorhaben 13: Dubletten und Dokumentfamilien
[families]
enabled = false        # Schalter, zunächst aus (Plan § 7, F2)
shingle = 5            # Wörter je Shingle; mit τ zusammen gewählt (13-dubletten.md, § 3.3)
permutations = 128
bands = 32             # 32 × 4: jedes Paar ab J = 0,6 wird Kandidat
rows = 4
threshold = 0.9        # τ*, aus der Kodierung (§ 5)
pairs_from = 0.5       # Paare ab hier in die Paardatei, für Vorhaben 23 und andere Schwellen
seed = 13
```

**Ausgaben** (Schema-Version `FAMILIES_SCHEMA_VERSION = 1` als Modulkonstante):

| Datei | Spalten | Zeilen |
|---|---|---|
| `processed/dokumentfamilien.parquet` | `id` String (eine Zeile je Korpus-ID, sortiert), `familie` String (kleinste ID der Familie, bei Einzeldokumenten die eigene), `groesse` Int64, `shingles` Int64 (0 ohne Text) | 19 108 |
| `processed/dokumentfamilien_paare.parquet` | `id_a` String, `id_b` String (`id_a < id_b`), `jaccard` Float64 | alle Kandidaten ab `pairs_from`, rund 2 000 |

Die Familie heißt nach ihrer kleinsten ID, nicht nach einer Komponentennummer: so ist das Etikett
unabhängig von der Reihenfolge und bleibt stehen, wenn ein neues Dokument hinzukommt, das nicht ihr
kleinstes ist.

**Verträge** an der Batch-Grenze: `id` sortiert und eindeutig und gleich den Korpus-IDs;
`familie ≤ id` und `familie` ist eine ID; `groesse` gleich der Zahl der Zeilen mit dieser Familie;
jedes Paar mit `jaccard ≥ threshold` liegt in einer Familie, und jede Familie ist über solche Paare
verbunden; `0 ≤ jaccard ≤ 1`; Signaturen haben `permutations` Spalten. Kein `deal.pure` und kein
`deal.has` auf `jaccard` oder den Hashfunktionen: sie laufen je Paar oder je Dokument, also in
heißen Schleifen (CLAUDE.md); Verträge nur an der Batch-Grenze. Kein crosshair-Ziel: die Funktionen
rechnen auf numpy-Arrays; ihre Eigenschaften prüft hypothesis.

**Gewichtsvariante `familie`** in `analysis/weights.py`: Konstante `BY_FAMILY = "familie"`,
`family_weights(pairs, families) -> [wahlkreis_id, id, gewicht]` mit `gewicht = 1 / k`, wobei k die
Zahl der Dokumente derselben Familie mit Treffer im selben Bezirk ist (die Kombination mit Begriffs-
oder Artgewichten bleibt aus Stufe 2 heraus; sie bräuchte ein Maximum je Familie statt einer Summe);
`variants(..., families: pl.DataFrame | None = None)` hängt die Zeile
an. Nachbedingungen: Summe je Bezirk gleich der Zahl der Familien mit Treffer; jedes Gewicht ≤ 1;
bei lauter Einzeldokumenten gleich `einheit`. `settings.FIXED_VARIANTS` bekommt `"familie"`; der Test,
der beide Listen gleich hält, gilt weiter.

**Berührte Dateien**: neu `src/georep/analysis/families.py`, `src/georep/enrich/families.py`,
`tests/unit/test_families.py`, `tests/property/test_families.py`; geändert
`src/georep/analysis/weights.py`, `src/georep/settings.py` (Modell, Feld, `FIXED_VARIANTS`),
`src/georep/defaults.toml` (Block am Ende), `src/georep/layout.py` (zwei Pfade),
`src/georep/pipeline.py` oder das Register aus F2 (`weights` liest die Familien, wenn der Schalter an
ist), `src/georep/report/model.py` (Beschriftung, Reihenfolge), `noxfile.py` (`MUTATION_SCOPE`),
`tests/unit/test_weights.py`, `docs/architecture.md`,
`docs/decisions.md` (Punkt beim Merge), `docs/statistik.md` § 6, `STATUS.md`.

**Tests.** Beispiele: zwei gleiche Texte sind eine Familie; ein geändertes Wort in einem Text von 300
Wörtern bleibt über 0,9; zwei Texte aus demselben Formular mit anderem Eigentext bleiben getrennt;
leerer und kurzer Text ergeben `shingles = 0` und eine Einzelfamilie; zwei Läufe und eine vertauschte
Eingabe ergeben dieselbe Datei. Eigenschaften (hypothesis): Jaccard ist symmetrisch, liegt in [0, 1],
J(a, a) = 1; die Familien zerlegen die IDs; jede Kante über τ liegt in einer Familie; die
Familiengewichte summieren je Bezirk zur Zahl der Familien und liegen nie über `einheit`. Keine
Erwartung auf die geschätzte Jaccard einer Signatur (sie hängt am Seed), außer als Schranke mit festem
Seed. Golden Master unberührt, weil die Variante eine Zeile in `wahlbezirke_gewichtet.parquet` ist.

**Paket und Laufzeit.** Kein neues Datenpaket: der Schritt liest nur den Textstore, den die Pakete
schon tragen, und läuft in GitHub Pages mit. Gemessen im letzten vollen Lauf des Messskripts
(2026-11-23, 18:35, Lastmittel 19,7 zu Beginn und 19,2 am Ende, `nice -n 10`): Shingles 6,8 s,
Signaturen 5,5 s, LSH 0,2 s, Jaccard 0,1 s für die Hauptperiode; das ganze Skript mit drei Profilen,
drei Shingle-Längen und der Gegenprobe 1:52 min, höchster Speicher 1,3 GB. Lauf für alle vier
Profile, auch Mönchengladbach (keine Kürzel in den Nummern; die Familien hängen nur am Text, die
Typen in § 3.4 sind Messwerkzeug und kommen nicht in den Schritt).

## 7. Bauplan Stufe 3

Eine Zeile in der Tabelle „Was ändert die Gewichtung?" auf `index.html` („jede Familie einmal",
Formel: „Dokumente mit fast gleichem Text, Jaccard ≥ τ über Fünf-Wort-Folgen, zählen je Wahlbezirk
zusammen einmal"), geschätzt 0,4 bis 0,6 KB wie die anderen Zeilen; darunter ein Satz zur Validierung
(„Präzision x an 200 Paaren, geprüft von zwei KI-Kodierern, nicht von Menschen"). Im Dokumentdialog
für Dokumente in einer Familie eine Zeile „gleicher Text auch in: BV2/221/2024, …" aus
`dokumente.json` (nachgeladen, nicht in `index.html`; rund 100 Dokumente bei τ = 0,9, geschätzt 3 KB).
Tabellen im Register: `dokumentfamilien.parquet` und die Paardatei als Download mit Spaltendoku. Keine
Unterseite.

## 8. Vorab festgelegte Hypothesen

Keine. Die Variante ist eine Robustheitsprüfung wie die 26 Gewichtungen von Option 06 und heißt auf
der Seite wie diese nicht „Test". Vorab festgelegt sind nur die Schwellenregel und das Kriterium
(§ 5).

## 9. Risiken und offene Fragen

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 13.1 | Zählt eine Fortschreibung (`X/1`) mit ihrem Original als eine Familie, oder ist eine neue Fassung neue Aufmerksamkeit für den Ort? | Sie ist die größte Gruppe bei τ = 0,9 | eine Familie (Codebuch: `fast_gleich` ist richtig) |
| 13.2 | Sind wiederkehrende Berichte verschiedener Zeiträume „andere Sache"? | Sie entscheiden, ob τ = 0,7 die Präzision hält, und damit das Urteil | ja, wie im Codebuch |
| 13.3 | Reicht die Hauptdatei, oder sollen Anlagen zählen? | Verteilervorlagen können sich nur in Anlagen unterscheiden; der Korpus trägt nur die Hauptdatei | Hauptdatei, wie die Trefferquote |
| 13.4 | Reichen 1 500 Zeichen Ausschnitt für die Kodierer? | Bei langen Dokumenten mit gleichem Anfang liegt der Unterschied später; die Präzision würde dann überschätzt | ja, zusammen mit Titel, Datum und `zeichen`; F4 kann den Ausschnitt erweitern |
| 13.5 | Soll die Familie im Dokumentdialog gezeigt werden, auch wenn die Variante verworfen wird? | Nutzen für die Ratsarbeit („an wen ging das noch?") | nein als eigener Schritt; Vorhaben 14 übernimmt Fortschreibungen und Verteiler über Nummern und Titel |
| 13.6 | Gelten Kodierer und Schlichter als unabhängig, obwohl sie dasselbe Modell sind? | α = 0,941 kann gemeinsame Vorlieben eines Modells messen statt Klarheit des Codebuchs | ja für Stufe 1, wie bei den anderen Vorhaben; Frage 19 an Konrad ist offen |
| 13.7 | Soll ein Codebuch in Fassung 2 die Regeln des Schlichters übernehmen? | Sie verschieben Paare zwischen `gleich`, `fast_gleich` und `aehnlich_andere_sache` und damit die Präzision | nur notiert, auf dieses Verfahren nicht angewandt (siehe unten) |

**Regeln des Schlichters für eine Fassung 2 des Codebuchs** (aus `schlichtung.jsonl`, 2026-11-23;
nicht auf die Messung angewandt, die Labels oben folgen nur Fassung 1 und den sieben Entscheiden).
Prüffrage: „Hätten beide Dokumente zusammen mehr bewirkt als eines?" (a) Ein an ein Haushaltsjahr
gebundener Antrag oder Zuschuss ist je Haushaltsjahr eine eigene Sache, auch wortgleich; dieselbe
Sache nur bei erneuter Einbringung zum selben Haushaltsjahr. (b) Die Endung `/1` ist ein Hinweis,
kein Kriterium; ein ungeklärter Längenrest bis rund 2 % gilt als `gleich`. (c) Dieselbe Vorlage an
mehrere Bezirksvertretungen ist ebenso `gleich`. (d) Eine Wahl mit getauschter Person zur selben
Besetzung ist `fast_gleich`. **Die Grenze von 2 % in (b) hat der Schlichter selbst gesetzt; sie war
nicht vorab festgelegt** und steht weder im Codebuch noch in diesem Dokument vor der Kodierung. Regel
(d) widerspräche dem Beispiel „andere Person bei einer Ersatzwahl" in Fassung 1 nur, wo dieselbe
Besetzung gemeint ist; RAT/554/2021 und RAT/555/2021 (zwei Gesellschaften) blieben „andere Sache".

**Risiken.** Ändert sich der Extraktor, ändern sich die Familien (der Stamp hängt am Textstore, das ist
gewollt). Die Typen in § 3.4 sind eine Regel über Metadaten und können einzelne Familien falsch
einordnen; sie tragen kein Urteil. Die Messung lief unter starker Fremdlast; die Zahlen hängen daran
nicht, nur die Laufzeiten.

## 10. Änderungen durch die Synergie (füllt der Supervisor)

Vorschlag des Mess-Agenten für die Synergie: Vorhaben 23 übernimmt den MinHash-Prototyp; Vorhaben 14
erhält die Fortschreibungen und Verteilervorlagen als Kantenarten.
