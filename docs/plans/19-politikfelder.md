# Vorhaben 19: Politikfelder nach dem Comparative Agendas Project

**Stand 2026-11-28: Urteil bauen mit Weg 3b (§ 5), gemessen; § 10 geschrieben, Stufe 2 und 3 im Bau.** Stufe 2 braucht die
GPU unter 15 Minuten (Gewichte lokal unter `messdaten/19-politikfelder/training-3b/`); Paket und Seite
erst nach Frage 37 (Lizenz der CAP-Codes, `fragen-2026-11.md`). **§ 10 vor dem Bau durch den
Supervisor.**

Stufe 1 (Messen) vom 2026-11-24 (Messung 2026-11-23, 22:26 Uhr, bis 2026-11-24, 00:11 Uhr) auf dem
Branch `feat/19-politikfelder` (gemerged, entfernt). Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „19 Politikfelder nach
dem Comparative Agendas Project", dazu § 10, Frage 5 (Babel Machine nicht benutzen, aber nachbauen).
Messskript: [19-politikfelder-messung.py](19-politikfelder-messung.py) (`uv run python
docs/plans/19-politikfelder-messung.py` rechnet jede Zahl dieses Dokuments aus den gespeicherten
Ausgaben nach, ohne Modell; die Teile `llm`, `ausschuss`, `cap`, `tfidf` erzeugen sie). Trainingsskript
für Weg 3, in einem eigenen Venv außerhalb des Pakets: [19-politikfelder-training.py](19-politikfelder-training.py).
Codebuch, Stichprobe, Entwicklungsmenge und später die Labels: `validierung/19-politikfelder/`.

**Urteil (endgültig, 2026-11-24, 02:20 Uhr): bauen mit Weg 3b**, dem Nachbau der Babel Machine:
`xlm-roberta-large`, feinjustiert auf den menschlich kodierten deutschen CAP-Daten und auf
Silberlabels von Weg 1 für 4 200 Ratsdokumente (§ 5). Gegen die Labels von zwei KI-Kodierern und einem
Schlichter desselben Modells (Opus, α 0,943, nicht von Menschen) erfüllen **zwei Wege das Kriterium**:
Weg 1 (`qwen3.6:27b` mit dem Codebuch im Systemprompt) mit **Makro-F1 0,753** (Bootstrap 0,658–0,822)
und Weg 3b mit **0,704** (0,620–0,807), beide im gepaarten Bootstrap sicher besser als die
Ausschussabbildung (2B: 0,242). Weg 1 liegt vor 3b, aber nicht sicher (2,5-%-Perzentil der Differenz
−0,047); nach der vorab festgelegten Regel wird dann der billigere Weg gebaut, und das ist 3b
(Vorhersage aller Perioden in Minuten statt 13,8 GPU-Stunden). Das vorläufige Urteil „bauen mit
Weg 1" (00:50 Uhr, mit 3a statt 3b) ist damit überholt. Vorab festgelegt in `b813d43` (22:43 Uhr, § 8),
Prompt, Training und Gewichtung der Silberlabels eingefroren in `c194e08` (23:10 Uhr, § 8.8), beides
vor dem ersten Lauf auf der Testmenge; an den Labels ist nichts nachgestellt.

Die Zahlen vor der Kodierung, auf die es ankam (die Abschnitte 3 und 3.5 sind so stehen geblieben, wie
sie vor den Labels geschrieben wurden):

1. **Weg 1 ist billig**: `qwen3.6:27b` mit dem ganzen Codebuch im Systemprompt braucht **0,86 s je
   Dokument** (300 der Testmenge in 258 s, alle in der Antwortform), weil die Antwort fünf Token hat und
   ollama den Systemprompt zwischenspeichert. Alle vier Datensätze (45 483 Dokumente mit Text) kosten
   **11,0 GPU-Stunden**, die Hauptperiode 4,6.
2. **Gegen menschliche CAP-Kodierung** (200 Anfragentitel des Bundestags 1976–2005, German Policy
   Agendas Project) erreicht Weg 1 **Makro-F1 0,579** (Bootstrap 0,487–0,642), Genauigkeit 0,65; gemma4
   nur 0,388. Das ist die einzige Zahl mit menschlichem Gold, an einer anderen Textsorte.
3. **Die Ausschussabbildung ist ein schwacher Vergleich**: 2A lässt 174 der 300 Testdokumente in der
   Restklasse (99), 2B legt 46 % des Korpus auf Verkehr und kann zehn der 21 Felder nie ausgeben;
   Weg 1 stimmt mit 2B in 175 von 300 überein. Das Kriterium „besser als die Ausschussabbildung"
   sollte Weg 1 bestehen; offen ist Makro-F1 ≥ 0,70, das bei 300 Dokumenten an acht fast leeren
   Klassen hängt (Frage 9.1).
4. **Weg 3a**, der Nachbau der Babel Machine (xlm-roberta-large, nur auf den deutschen CAP-Daten,
   24 GPU-Minuten Training), erreicht auf zurückgehaltenen menschlichen Codes **Makro-F1 0,710** und auf
   denselben 200 Titeln 0,706 (0,622–0,793), mehr als Weg 1 dort; auf Ratsdokumenten stimmt er mit
   Weg 1 in 197 von 300 überein. Die Einigkeitsregel deckt damit 0,660 (gewichtet) ab, unter 0,70.
5. **Fremddaten**: offen lizenzierte, von Menschen CAP-kodierte deutsche Texte gibt es nur vom German
   Policy Agendas Project (10 033 Anfragentitel, 73 878 Programmsätze; CC BY-NC-SA 4.0 für die Codes,
   die Programmtexte urheberrechtlich geschützt, darum nur lokal). Keine Landtage, keine Kommunen.

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

**Frage.** Welches der 21 Hauptthemen des Comparative Agendas Project (CAP) trägt ein Ratsdokument?
Mit einem Politikfeld je Dokument wird die Aufmerksamkeit des Rates und der Bezirksvertretungen
zählbar und vergleichbar: zwischen Perioden, Gremien, Fraktionen und Wahlbezirken, und über die
Ebenen hinweg mit Bundestag, Landtagen und anderen Städten, die nach demselben Codebuch kodiert sind.

**Literatur.** Das CAP geht auf das Policy Agendas Project von Baumgartner und Jones zurück; das
Master-Codebuch (Version 1.1, 2022) vereinheitlicht die Länderprojekte mit 21 Hauptthemen und rund 220
Unterthemen. Für Deutschland kodiert das German Policy Agendas Project Anfragen, Gesetze,
Regierungserklärungen und Wahlprogramme (Breunig, Guinaudeau, Schnatterer 2021, Journal of
Legislative Studies). Die Babel Machine (Sebők u. a. 2024, Social Science Computer Review) ist ein
mehrsprachiger CAP-Klassifikator aus feinjustierten XLM-RoBERTa-Modellen; ParlaCAP (Kuzman
Pungeršek, Ljubešić 2026, arXiv 2602.16516) zeigt, dass ein von GPT-4o gelabelter Trainingssatz
einen Schüler-Klassifikator mit Makro-F1 0,64 bis 0,72 gegen menschliche Kodierung trägt, und dass
GPT-4o selbst dort 0,63 bis 0,74 erreicht. Auf kommunaler Ebene gibt es nach dieser Suche keinen
offen lizenzierten, von Menschen CAP-kodierten Datensatz; Mortensen, Loftis und Seeberg (2022,
*Explaining Local Policy Agendas*) arbeiten mit dänischen Gemeinden, ohne offenen Datensatz.

**Ratsarbeit.** „Wie viel Aufmerksamkeit bekommt Verkehr in der Bezirksvertretung 3 im Vergleich
zum Rat?", „Welche Fraktion bringt welche Politikfelder ein?", „Welche Themen fehlen in einem
Wahlbezirk, gemessen an seinem Bedarf?" (Vorhaben 22). Heute beantwortet das nur die
Ausschusszuordnung (Punkt 45), und die lässt 62 % der Dokumente in der Restklasse.

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

**Ratsdokumente.** Gerechnet auf den Läufen vom 2026-11-23 (`georep bootstrap && georep run` für alle
vier Profile im Worktree, 22:26 bis 23:03 Uhr). Gelesen, nur lesend:

- `interim/papers.parquet`: `id`, `name` (Titel), `paper_type`, `file_name`, `text`.
- `processed/papers_gremien.parquet`: `id`, `gremium`, `gremium_art` (Schichtung; Eingabe von Weg 2).
- `processed/papers_ausschuss.parquet`: `id`, `ausschuss`, `wahrscheinlichkeit` (Weg 2A; 2B rechnet das
  Messskript mit `assign_committees` ohne Schwelle nach).
- `messdaten/rohtext/duesseldorf.parquet` (Phase 0): `name`, `text` mit Groß- und Kleinschreibung und
  Zeilen; Ausschnitt für Kodierer, Weg 1 und Weg 3. Mit F1 tritt `rohtexte.parquet` an seine Stelle.

| Profil | Dokumente | mit Text |
|---|---|---|
| `duesseldorf-2014` | 22 215 | 21 725 |
| `duesseldorf` (Hauptperiode) | 19 108 | 19 033 (19 032 auch mit Rohtext: die Grundgesamtheit) |
| `duesseldorf-2025` | 4 095 | 4 075 |
| `moenchengladbach` | 2 895 | 650 |

Die Grundgesamtheit der Testmenge hat 18 Schichten (Gremiumsart × Gruppe der Dokumentart), die
größten Bezirksvertretung|Antrag (3 090), |Beschluss (2 893), |Information (2 803), Ausschuss|Beschluss
(2 327), Bezirksvertretung|Anfrage (2 200). Die Texte der Testmenge haben im Median 1 854 Zeichen;
59 der 300 sind länger als der Ausschnitt von 4 000 Zeichen.

**Fremddaten** (geladen am 2026-11-23 direkt von der Quelle, je Quelle ein Ordner unter
`/media/konrad/xtraspace/georep/fremddaten/cap/` mit README: URL, Abrufzeit, Bytes, SHA-256,
Lizenz wörtlich; nichts ausgeführt, CSV mit Polars, PDF-Text mit pypdf aus einem Skript außerhalb):

| Datensatz | von Menschen kodiert | Bestand | Lizenz (wörtlich gesichert) | Nutzung |
|---|---|---|---|---|
| German Policy Agendas: **Anfragen** 1976–2005 (`anfrage_…_2.5.csv`, 1,06 MB) | ja | 10 033 Titel (ASCII-Umschrift „Laender"), Haupt- und Unterthema | CAP-Seite „Copyright and Legal": Codes und Variablen „Creative Commons Attribution-NonCommercial-ShareAlike 4.0"; „the original copyright of primary source material also applies" | **Training 3a**, zweite Prüfung (200 Titel) |
| German Policy Agendas: **Wahlprogramme** 1949–2013 (`manifesto_…_2.5_2_3.csv`, 12,0 MB) | ja | 75 190 Sätze, davon 73 878 ohne „junk" mit gültigem Code; 5 778 mit 99 | wie oben; die Sätze sind Texte der Parteien (urheberrechtlich geschützt) | **Training 3a**, nur lokal |
| German Policy Agendas: Gesetzentwürfe, Gesetze, Regierungserklärungen, MIP | ja | nur Codes, kein Text | wie oben | nicht nutzbar |
| Deutsches CAP-Codebuch v2.5 (April 2019, PDF, zweisprachig) | – | 70 Seiten, alle Unterthemen deutsch | wie oben | Grundlage der kommunalen Abbildung |
| CAP Master Topics Codebook 1.1 (2022, Webseite) | – | 21 Hauptthemen, Unterthemen | wie oben | Kodierschema |
| Swiss Agendas: NZZ-Titelseite 1995–2003 (0,86 MB) | ja | deutsche Schlagzeilen, Umlaute verloren | wie oben; Texte der NZZ | geladen, **nicht** im Training (Zeitung, Außenpolitik) |
| FrameASt (Klamm, Rehbein, Ponzetto 2022, GitHub) | teils (Testausschnitt Bundestagsreden) | klein | **keine Lizenzangabe** | nur genannt |
| ParlaCAP-train (CLARIN.SI 11356/2093) | **nein**, GPT-4o | 35 579 Reden aus 29 Parlamenten, darunter deutschsprachige (Österreich) | CC BY 4.0 | nur genannt (Silberlabels anderer Herkunft) |
| Erweiterte deutsche CAP-Daten 1978–2017, deutsches Codebuch mit Querverweis | ja | Bundestag, mehr Arten | nur auf Anfrage | nur genannt |
| Babel Machine (Dienst, Gewichte `poltextlab/…`, Hugging Face, zugangsbeschränkt) | – | – | – | **nicht benutzt** (Konrad, 2026-11-23) |

Deutsche Landtage oder Kommunen mit offen lizenzierten CAP-Codes gibt es nach dieser Suche nicht.
Die Codes in den CSV-Dateien sind bereits die des Master-Codebuchs (9 Migration und 23 Kultur kommen
vor, 24 und 25 des deutschen Codebuchs nicht). Lizenzfolge: die CAP-Codes und alles, was sie
bearbeitet, stehen unter CC BY-NC-SA 4.0. Das betrifft das Codebuch dieses Vorhabens (eine
Bearbeitung beider CAP-Codebücher; `codebuch.toml` sagt es im Kopf) und, je nach Lesart, die Ausgabe
eines Klassifikators, der auf CAP-Daten trainiert ist (Weg 3); Frage 9.4.

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

Alle Zahlen vom 2026-11-23, Läufe zwischen 22:43 Uhr und 00:11 Uhr am 24.11.; das Messskript ohne
Teil rechnet sie aus den gespeicherten Ausgaben nach (20 bis 45 s je nach Last, ruft kein Modell). Der Rechner stand unter Fremdlast
(Lastmittel 4 bis 22) und teilte die GPU mit den Vorhaben 18 und 20; jeder Modellauf lief unter der
Sperre `gpu-queue/gpu.lock`, mit `uptime` davor und danach in `laufzeiten.jsonl`. Nach jedem Laden
stand im ollama-Log „offloaded 65/65 layers to GPU" (qwen) beziehungsweise „43/43" (gemma4), und
`nvidia-smi` zeigte 23,2 GB beziehungsweise 10,7 GB belegt: keine Zahl hier stammt von der CPU.

### 3.1 Reihenfolge

1. 22:43 Vorab-Festlegung `b813d43` (§ 8), danach Grundgesamtheit, Testmenge (F4), Kodieraufträge,
   Entwicklungsmenge, CAP-Daten, Weg 2, Nebenverfahren TF-IDF (CPU).
2. 23:09 bis 23:14 Weg 1 auf der Entwicklungsmenge (zuerst 20 Dokumente zur Prüfung der Antwortform,
   dann die übrigen 180) und auf den 200 CAP-Anfragentiteln.
3. 23:10 Einfrieren `c194e08` (§ 8.8): Prompt unverändert, SHA-256 des Systemprompts im Commit.
4. 23:21 bis 23:30 Weg 1 auf der Testmenge, einmal (`qwen3.6:27b`, Nebenlauf `gemma4`), und gemma4
   auf den CAP-Titeln.
5. 23:46 bis 00:11 Weg 3a: ein Trainingsblock von 24 Minuten unter der Sperre (9 438 Schritte),
   danach die Vorhersage. Ein erster Versuch um 23:30 brach beim Laden ab, ohne zu rechnen: das
   torch-Rad von PyPI (2.15.0, CUDA 13.2) verlangt einen neueren Treiber als den installierten
   (575.57, CUDA 12.9); das Trainings-Venv wurde mit `torch 2.13.0+cu129` vom PyTorch-Index
   neu angelegt.
6. 2026-11-24, 00:18 bis 02:11 Uhr, Auftrag `gpu-queue/19-silber.sh` (vom Supervisor gestartet):
   Silberlabels von Weg 1 für 4 000 Ratsdokumente in zwei Blöcken (00:18 bis 00:55, 00:55 bis 01:32),
   dann Training 3b in zwei Blöcken (01:32 bis 01:58, Prüfpunkt bei Schritt 8 856, und bis 02:11).
7. 00:44 bis 00:50 und 02:11 bis 02:20 Auswertung gegen die Labels (§ 4.2), vorläufig ohne, endgültig
   mit 3b.

Kein Lauf auf der Testmenge wurde wiederholt; an keinem Prompt, Parameter oder Schwellenwert wurde
nach einem Blick auf Testergebnisse etwas geändert (es gibt dort ohnehin noch kein Gold).

### 3.2 Weg 2: Ausschuss → CAP

Die Kette ordnet 7 172 der 19 033 Dokumente mit Text einem von 19 Ausschüssen zu, 11 861 (62,3 %)
bleiben in der Restklasse. **2A** gibt der Restklasse 99; in der Testmenge sind das **174 von 300**.
**2B** nimmt den wahrscheinlichsten Ausschuss ohne Schwelle und gibt jedem Dokument ein Feld, aber
schief: **8 838 der 19 033 Dokumente (46 %) werden Verkehr (10)**, weil der Ordnungs- und
Verkehrsausschuss die Bezirksvertretungsdokumente an sich zieht; in der Testmenge 142 von 300. Die
Abbildung kennt nur die 11 Felder, für die es einen Ausschuss gibt (1, 2, 6, 7, 9, 10, 13, 14, 15, 20,
23, dazu 99): 3, 4, 5, 8, 12, 16, 17, 18, 19 und 21 kann sie nie ausgeben.

### 3.3 Weg 1: qwen3.6:27b mit dem Codebuch

| Menge | Dokumente | gültige Antworten | Sekunden je Dokument (ohne Laden) | Last vorher → nachher |
|---|---|---|---|---|
| Entwicklung, erste 20 | 20 | 20 | 1,36 (mit 10,8 s Laden im ersten) | 5,7 → 7,9 |
| Entwicklung, übrige | 180 | 180 | **0,84** | 7,9 → 7,2 |
| CAP-Anfragentitel | 200 | 200 | 0,59 | 7,2 → 6,6 |
| **Test** | 300 | **300** | **0,86** | 11,7 → 3,4 |
| Test, gemma4 (Nebenlauf) | 300 | 300 | 0,52 | 3,4 → 4,5 |
| CAP-Titel, gemma4 | 200 | 200 | 0,41 | 4,4 → 5,4 |

Keine Antwort verfehlte die Form `THEMA: <Nummer>`, keine stieß an `num_predict`. Das Modell ist viel
schneller als bei den Kurzfassungen (3,9 s je Dokument, F5): die Antwort hat fünf Token statt rund 90.
Der Systemprompt hat 18 307 Zeichen; ihn bei 1 261 Token/s (F5) jedes Mal neu zu lesen, kostete allein
mehrere Sekunden. Die gemessenen 0,86 s gehen nur, weil ollama den gemeinsamen Anfang aller Prompts
wiederverwendet und je Dokument nur den Ausschnitt liest; ein Lauf, der zwischen zwei Prompts
wechselt, verliert das.

Verteilung auf der Testmenge (qwen): 10 Verkehr 83, 20 Staat und Verwaltung 37, 13 Soziales 35, 14
Wohnen und Stadtentwicklung 30, 7 Umwelt 25, 23 Kultur 19, 6 Bildung 17, 21 Flächen 15, 8 Energie 7,
15 Wirtschaft 7, 2 Bürgerrechte 6, 3 Gesundheit 5, 1 Haushalt 4, 17 Technik 4, 12 Ordnung 3, 19, 9, 4
je 1; nie 5, 16, 18, 99. Auf der Entwicklungsmenge dasselbe Bild (10: 53, 14: 28, 13: 21, 20: 18).

### 3.4 Weg 3: Klassifikator nach dem Muster der Babel Machine

**Daten.** 75 502 Trainingsbeispiele (9 021 Anfragentitel, 66 481 Programmsätze), 8 409 zurückgehalten
(1 012 Titel, 7 397 Sätze; je Quelle und Hauptthema die 10 % mit dem kleinsten Rang aus Seed 20261125).
Median 25 Token je Beispiel, keines über 256. Die Verteilung ist schief (19 Internationales 6 737,
1 Wirtschaft 6 719, aber 21 Flächen 236, 23 Kultur 1 095): Bundestag und Wahlprogramme reden über
andere Dinge als ein Rat.

**Nebenverfahren TF-IDF** (CPU, 2 min 44 s mit Weg 2): Makro-F1 auf den zurückgehaltenen
Anfragentiteln **0,509** (Genauigkeit 0,579), auf den Programmsätzen 0,531. Auf den Ratsdokumenten
der Testmenge sagt es 66-mal 20 und 38-mal 1 und stimmt nur in 93 von 300 mit Weg 1 überein: die
Textsorte trägt mit Wörtern allein nicht.

**3a** (Training 2026-11-23, 23:46 bis 00:11): `xlm-roberta-large` (Revision `c23d21b0`, 2,24 GB safetensors),
Venv `/media/konrad/xtraspace/venvs/cap-train` (7,1 GB; `torch 2.13.0+cu129`, `transformers 5.22.2`,
`polars 2.1.0`, nichts davon im Paket). Zwei Epochen in **1 438 s** auf der RTX 4090 (13,4 GB belegt,
Lastmittel 5,9 bis 8,2), ein Block. Makro-F1 auf den zurückgehaltenen 10 % nach Epoche 1 0,676, nach
Epoche 2 **0,710** (gewählt); je Quelle: Anfragentitel **0,693** (Genauigkeit 0,753), Programmsätze 0,709
(0,704), im Bereich, den ParlaCAP für seinen Schüler-Klassifikator gegen menschliche Kodierung nennt
(0,64 bis 0,72). Auf den
Ratsdokumenten der Testmenge: 20 Staat und Verwaltung 75, 10 Verkehr 68, 7 Umwelt 30, 13 Soziales 23,
14 Wohnen 21, 23 Kultur 20, 6 Bildung 15, 2 Bürgerrechte 9, 3 Gesundheit 7, 8 Energie 6, 4, 12, 15 je 5,
1, 17, 21 je 3, 5 und 9 je 1. Er legt mehr auf 20 und weniger auf 10 als Weg 1 und kennt die
kommunalen Regeln des Codebuchs nicht (Parks 21 gibt er dreimal, Weg 1 15-mal).

**3b** (2026-11-24): Silberlabels von Weg 1 für 4 000 Dokumente der Silbermenge, alle 4 000 in der
Antwortform (10 Verkehr 1 053, 14 Wohnen 501, 20 Staat und Verwaltung 414, 13 Soziales 395, …, 99
zweimal), dazu die 200 der Entwicklungsmenge: 4 200 Ratsdokumente, je sechsmal wiederholt (rund ein
Viertel der Beispiele, § 8.8), zusammen 100 702 Beispiele und 12 588 Schritte. Training in **2 268,5 s**
(zwei Blöcke), Makro-F1 auf den zurückgehaltenen CAP-Daten nach Epoche 1 0,686, nach Epoche 2
**0,705** (gewählt); je Quelle Anfragentitel 0,681, Programmsätze 0,705, also fast wie 3a: die
Ratsdokumente kosten auf der alten Textsorte nichts. Gewichte unter
`$GEOREP_MESSDATEN/19-politikfelder/training-3b/beste/` (`model.safetensors`, 2,24 GB, SHA-256
`80ca2a82…09`), nicht im Repo. Auf der Testmenge: 10 Verkehr 81, 20 Staat und Verwaltung 34, 13
Soziales 32, 14 Wohnen 30, 7 Umwelt 29, 23 Kultur 23, 6 Bildung 18, 21 Flächen 12, 15 Wirtschaft 10, 3
Gesundheit 8, 8 Energie 7, 2 Bürgerrechte 5, 1, 12, 17 je 3, 4 und 9 je 1; mit Weg 1 einig in
**270 von 300**, mit 3a in 201.

**Babel Machine**: weder Dienst noch Gewichte benutzt; die Modellseiten von poltextlab auf Hugging Face
sind zugangsbeschränkt und wurden nicht geöffnet.

### 3.5 Übereinstimmung ohne Gold (Entwurf, kein Urteil)

Auf der Testmenge, je Paar gleiche Hauptthemen von 300:

| | qwen | gemma4 | 2A | 2B | TF-IDF | 3a |
|---|---|---|---|---|---|---|
| qwen | – | 232 | 95 | 175 | 93 | 197 |
| gemma4 | | – | 98 | 182 | 99 | 187 |
| 2A | | | – | 126 | 60 | 90 |
| 2B | | | | – | 88 | 152 |

In der Entwicklungsmenge gibt qwen 40 der 56 Dokumente aus Ausschüssen das Feld, das die Tabelle
§ 8.4 ihrem eigenen Ausschuss gibt: für Ausschussdokumente ist die Tabelle ein brauchbarer Anker, für
die übrigen (in der Testmenge 215 von 300: Rat, Bezirksvertretungen, Beiräte) nicht, und dort muss
2A oder 2B raten.

**Einigkeitsregel** (§ 8.6, für den Rückfall): Weg 1 und Weg 3a sagen in 197 von 300 dasselbe, mit den
Schichtgewichten hochgerechnet **0,660**, unter der Abdeckung 0,70, die die Regel verlangt. Mit 3b kann
sich das ändern; ohne bessere Einigkeit trägt der Rückfall nicht.

**Was das für das Urteil heißt (Entwurf).** Weg 2 wird gegen das Gold schwach sein: 2A lässt 58 % der
Testmenge in 99, 2B legt fast die Hälfte auf Verkehr, und zehn Felder kann die Tabelle gar nicht
ausgeben. Den Vergleich mit der Ausschussabbildung sollte Weg 1 darum bestehen. Offen ist die Schwelle
0,70: das Makro-F1 mittelt über alle Klassen mit Gold oder Vorhersage, und bei 300 Dokumenten haben
nach der Verteilung von Weg 1 acht der 22 Klassen höchstens drei Dokumente (Frage 9.1). Gegen
menschliche Kodierung auf Bundestagstiteln erreicht qwen 0,58 (§ 3.6), etwas weniger als GPT-4o bei
ParlaCAP gegen menschliche Kodierung von Reden (0,63 bis 0,74).

### 3.6 Zweite Prüfung an menschlich kodierten Daten

| Verfahren | Menge | n | Makro-F1 (Bootstrap 95 %) | Genauigkeit | κ |
|---|---|---|---|---|---|
| Weg 1, qwen3.6:27b | 200 CAP-Anfragentitel | 200 | **0,579** (0,487–0,642) | 0,650 | 0,624 |
| Weg 1, gemma4 | dieselben | 200 | 0,388 (0,297–0,447) | 0,440 | 0,393 |
| TF-IDF (auf CAP trainiert) | dieselben 200 Titel | 200 | 0,549 (0,464–0,622) | 0,620 | 0,589 |
| TF-IDF | zurückgehaltene Anfragentitel | 1 012 | 0,509 | 0,579 | 0,545 |
| TF-IDF | zurückgehaltene Programmsätze | 7 397 | 0,531 | 0,557 | 0,527 |
| **Weg 3a**, xlm-roberta-large | dieselben 200 Titel | 200 | **0,706** (0,622–0,793) | 0,765 | 0,747 |
| Weg 3a | zurückgehaltene Anfragentitel | 1 012 | 0,693 | 0,753 | 0,734 |
| Weg 3a | zurückgehaltene Programmsätze | 7 397 | 0,709 | 0,704 | 0,685 |
| Weg 3b (mit Silberlabels) | dieselben 200 Titel | 200 | 0,688 (0,596–0,758) | 0,750 | 0,730 |
| Weg 3b | zurückgehaltene Anfragentitel | 1 012 | 0,681 | 0,742 | 0,722 |
| Weg 3b | zurückgehaltene Programmsätze | 7 397 | 0,705 | 0,700 | 0,681 |

Das Codebuch ist auf Städte zugeschnitten (Verwaltungsinterna 20, Sport 13, Parks 21); auf
Bundestagstiteln von 1976 bis 2005 (Deutschlandpolitik, Bundeswehr, Außenwirtschaft) ist es nicht
gemacht, und die Titel sind kurz und in ASCII-Umschrift. Die Zahl ist darum eine untere Marke für die
Treue zum CAP-Schema, keine Schätzung der Güte auf Ratsdokumenten. gemma4 fällt deutlich ab und kommt
für das Urteil nicht in Frage; es bleibt nur als Kostenvergleich. Weg 3a ist auf genau dieser
Textsorte trainiert; dass er dort vorn liegt, sagt nichts darüber, wie er auf Ratsdokumente
überträgt (Bundestag und Wahlprogramme kennen keine Bebauungspläne, Spielplätze und Ampeln).

### 3.7 Hochrechnung auf alle Perioden

Sekunden je Dokument aus den Läufen mit neuen Eingaben auf Ratsdokumenten, ohne Laden:

| Modell | s je Dokument | 2014–2020 (21 725) | 2020–2025 (19 033) | ab 2025 (4 075) | Mönchengladbach (650) | alle (45 483) |
|---|---|---|---|---|---|---|
| qwen3.6:27b | 0,87 | 5,3 h | 4,6 h | 1,0 h | 0,2 h | **11,0 h** |
| gemma4 | 0,52 | 3,2 h | 2,8 h | 0,6 h | 0,1 h | 6,6 h |

Dazu je Profil einmal Laden (rund 11 s). **Weg 3** ist in der Vorhersage billig: nach dem Training
brauchten Laden des besten Prüfpunkts und Vorhersage von 500 Ratsdokumenten und 8 409 Sätzen zusammen
10 s; alle Perioden geschätzt unter 15 GPU-Minuten. Das Training kostet einmal 24 Minuten (3a).
**Silberlabels für 3b**: 4 000 Dokumente × 0,84 s, rund 56 Minuten in zwei Blöcken; das Training 3b hat
mit 4 200 Silberdokumenten (sechsfach wiederholt, rund ein Viertel) rund 100 700 Beispiele und 12 600
Schritte, mit den längeren Ratsdokumenten geschätzt 35 bis 45 Minuten, also zwei Blöcke. Beides steht
als Auftrag in `/media/konrad/xtraspace/georep/gpu-queue/19-silber.sh` (fortsetzbar, Log
`georep/logs/19-silber.log`), den der Supervisor startet.

**Nachtrag mit den Silberläufen** (2026-11-24, Lastmittel 7 bis 18): die zwei Blöcke zu je 2 000
Dokumenten brauchten 2 235 und 2 239 s, **1,12 s je Dokument**. Über alle 4 500 Ratsdokumente mit
neuen Eingaben sind es im Mittel 1,09 s, und die Hochrechnung für Weg 1 steigt unter dieser Last auf
**13,8 GPU-Stunden** für alle Perioden (2014–2020 6,6 h, Hauptperiode 5,8 h, ab 2025 1,2 h,
Mönchengladbach 0,2 h); die 0,87 s oben gelten für einen ruhigeren Rechner.

**GPU-Zeit dieser Stufe 1** (Wanduhr unter der Sperre, ohne Warten): qwen 9,2 Minuten (Entwicklung,
CAP-Titel, Test) und 74,6 Minuten Silberlabels, gemma4 4,0 Minuten, Training 3a 24,0 Minuten, Training
3b 37,8 Minuten, dazu Laden; zusammen rund 2,5 Stunden.

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

**Codebuch** `validierung/19-politikfelder/codebuch.toml`, Format F4, Fassung 2026-11-23.1: Einheit
`document`, Frage `politikfeld` (nominal, 22 Optionen: die 21 Hauptthemen mit Nummer und 99) mit
Grundregeln, je Option Definition, kommunaler Abbildung, Grenzfällen und Beispiel; dazu `unsicher`
(ja/nein, ohne Schlichtung). Lizenz der Datei: CC BY-NC-SA 4.0 (Bearbeitung der CAP-Codebücher, im
Kopf der Datei vermerkt). Dasselbe Codebuch ist der Systemprompt von Weg 1.

**Stichprobe** (im Repo, nur IDs): `stichprobe.csv` und `stichprobe.json` (300 von 19 032, 18 Schichten,
proportional, nicht selbstgewichtend, weil kleine Schichten aufgerundet wurden; Prüfsumme der
Grundgesamtheit `2afe0a65…`), `entwicklung.csv` (200, ohne die 300).

**Aufträge** (lokal, nie im Repo): `/media/konrad/xtraspace/georep/messdaten/kodierung/19-politikfelder/A/`
und `…/B/`, je `auftrag.jsonl` (300 Einheiten mit Titel, Dokumentart und den ersten 4 000 Zeichen des
Rohtexts, rund 6 MB), `antworten.jsonl` (leer), `codebuch.md`. Erzeugt mit
`georep validate tasks 19-politikfelder --coder A|B --texts /media/konrad/xtraspace/georep/messdaten/rohtext/duesseldorf.parquet`
(`validation.coding_root` in `settings.local.toml` des Worktrees). Keine Ausgabe eines Verfahrens, auch
nicht das Gremium; die Ausschnitte nennen es aber oft selbst (Frage 9.2).

**Kodierer**: zwei frische Opus-Agenten nach `docs/validierung.md` § 4.1, der Supervisor teilt jeden in
zwei Läufe zu 150 Zeilen (über 200 Einheiten); Schlichtung nach § 4.2. Danach:

```bash
uv run georep validate merge 19-politikfelder --model claude-opus-5-5   # zweimal, mit Schlichtung dazwischen
uv run python docs/plans/19-politikfelder-messung.py                      # Urteil nach § 8.5/8.6
uv run georep validate score 19-politikfelder --pred <id,label der gewählten Fassung>
```

Das Messskript liest `labels.csv` (Spalten `id, frage, kodierer_a, kodierer_b, schlichtung, label`) und
rechnet α, Makro-F1 je Weg mit gepaartem Bootstrap, die Entscheidung und die Rückfallregel; die
Vorhersagen liegen unter `$GEOREP_MESSDATEN/19-politikfelder/` (`weg1_test_qwen3.6-27b.parquet`,
`weg2.parquet`, `weg3a_test.parquet`, später `weg3b_test.parquet`). Die Logik ist mit erfundenen Labels
durchgespielt (alle Zweige: α-Stufen, Kriterium, Rückfall).

**Maße**: § 8.5. Die zweite Prüfung (§ 3.6) ist die einzige Zahl mit menschlichem Gold.

### 4.1 Ergebnis der Kodierung (2026-11-24)

Zwei Kodier-Agenten und ein Schlicht-Agent, **alle drei dasselbe Modell** (`claude-opus-5-5`; Frage 19
aus F4, die Annahme „Opus für beide" gilt), ohne die Ausgabe eines Verfahrens; zusammengeführt mit
`georep validate merge` (`validierung/19-politikfelder/labels.csv`, `README.md`, `guete.json`).

| Frage | einig | Cohens κ | Krippendorffs α | genügt (α ≥ 0,8) |
|---|---|---|---|---|
| `politikfeld` | 285 von 300 (95,0 %) | 0,943 | **0,943** | ja |
| `unsicher` | 286 von 300 (95,3 %) | 0,890 | 0,890 | ja |

Die 15 Uneinigkeiten entschied die Schlichtung: viermal wie Kodierung 1, zehnmal wie Kodierung 2,
einmal etwas Drittes. α liegt über beiden Schwellen (0,67 für ein Urteil, 0,8 für Stufe 3): das Urteil
gilt nach § 8.5, und Stufe 3 ist nicht gesperrt. Weil alle drei dasselbe Modell sind, ist α eine obere
Schätzung der Schärfe des Codebuchs, kein Beleg der Richtigkeit (`docs/validierung.md`, § 1).

**Gold-Verteilung** (300): 10 Verkehr 78, 20 Staat und Verwaltung 33, 13 Soziales 32, 14 Wohnen 31, 7
Umwelt 29, 23 Kultur 27, 6 Bildung 12, 21 Flächen 9, 8 Energie 8, 12 Ordnung 8, 15 Wirtschaft 8, 2
Bürgerrechte 7, 3 Gesundheit 7, 17 Technik 4, 1 Haushalt 3, 4, 5, 9, 19 je 1; nie 16, 18, 99. Damit hat
das Hauptmaß 19 Klassen mit Gold, davon 13 mit mindestens fünf. `unsicher` sagte mindestens einer der
beiden bei 98 Dokumenten, beide bei 84.

### 4.2 Güte der Wege gegen die Labels

Messskript, 2026-11-24, 00:44 bis 00:50 Uhr (Lastmittel 20 bis 28, ein Lauf 65 s), Bootstrap über die
Dokumente mit 2 000 Ziehungen, Seed 20261123, gepaart über alle Wege:

| Weg | Makro-F1 (Hauptmaß) | 95 % | Makro-F1, Klassen ≥ 5 Gold | Genauigkeit | κ | gewichtetes Makro-F1 |
|---|---|---|---|---|---|---|
| **1 qwen3.6:27b** | **0,753** | 0,658–0,822 | **0,769** | **0,843** | 0,820 | 0,840 |
| 1, gemma4 (Nebenlauf) | 0,612 | 0,519–0,702 | 0,670 | 0,757 | 0,719 | 0,747 |
| **3b xlm-roberta-large mit Silberlabels** | **0,704** | 0,620–0,807 | **0,780** | **0,837** | 0,813 | 0,832 |
| 3a xlm-roberta-large | 0,509 | 0,422–0,583 | 0,597 | 0,637 | 0,586 | 0,650 |
| 2B Ausschuss ohne Schwelle | 0,242 | 0,222–0,310 | 0,354 | 0,587 | 0,502 | 0,512 |
| 2A Ausschuss der Kette | 0,191 | 0,175–0,242 | 0,294 | 0,320 | 0,279 | 0,416 |
| TF-IDF (Nebenverfahren) | 0,260 | 0,183–0,306 | 0,298 | 0,320 | 0,258 | 0,346 |

`georep validate score 19-politikfelder --pred <Weg 1>` bestätigt 0,753 und Genauigkeit 84,3 % in der
Stichprobe wie für die Grundgesamtheit (mit Schichtgewichten); das steht in `guete.json`.

Kriterium nach § 8.5 (bessere Ausschussvariante ist 2B):

| Weg | Makro-F1 ≥ 0,70 | Differenz zu 2B | 2,5-%-Perzentil der Differenz | Kriterium |
|---|---|---|---|---|
| 1 qwen3.6:27b | ja (0,753) | +0,511 | **+0,379** | **erfüllt** |
| 3b | ja (0,704) | +0,462 | **+0,355** | **erfüllt** |
| 3a | nein (0,509) | +0,267 | +0,147 | nicht erfüllt (geht nach § 8.3 nicht ins Urteil, weil 3b mit 4 200 Silberdokumenten vorliegt) |

Zwei Wege erfüllen das Kriterium. Weg 1 liegt vor 3b um 0,049 im Makro-F1, im gepaarten Bootstrap mit
2,5-%-Perzentil **−0,047**: kein sicherer Vorsprung. Im Nebenmaß über die 13 Klassen mit mindestens
fünf Gold-Dokumenten liegt 3b vorn (0,780 gegen 0,769), in der Genauigkeit gleichauf (0,837 gegen
0,843). `georep validate score` bestätigt für 3b 0,704 und Genauigkeit 83,7 % (Grundgesamtheit 83,6 %);
`guete.json` trägt jetzt diese Zahlen, die der gebauten Fassung.

### 4.3 Teilmengen (Frage 9.2) und Unsicherheit

Genauigkeit und Makro-F1 getrennt nach Dokumenten, deren Ausschnitt mit einem Ausschusskürzel in der
Drucksachennummer beginnt (84), und den übrigen (216):

| Weg | mit Kürzel: Genauigkeit | Makro-F1 | ohne Kürzel: Genauigkeit | Makro-F1 |
|---|---|---|---|---|
| 1 qwen3.6:27b | 0,833 | 0,662 | **0,847** | 0,748 |
| 3b | 0,857 | 0,707 | 0,829 | 0,723 |
| 3a | 0,643 | 0,431 | 0,634 | 0,542 |
| 2B | 0,714 | 0,360 | 0,537 | 0,207 |
| 2A | 0,655 | 0,326 | 0,190 | 0,127 |

Der Hinweis auf den Ausschuss hilft der Ausschussabbildung (2B: 0,714 gegen 0,537), nicht Weg 1, der
ohne Kürzel nicht schlechter ist. Die Labels bevorzugen Weg 2 also höchstens auf den 84
Ausschussdokumenten, und dort liegt Weg 1 trotzdem vorn; die Makro-Werte der Teilmengen haben wenige
Dokumente je Klasse und sind nur grob.

Ohne die 98 Dokumente, die mindestens ein Kodierer unsicher nannte: Weg 1 Genauigkeit 0,980, Makro-F1
0,946 (202 Dokumente); 3b 0,960 und 0,879; 3a 0,767 und 0,652; 2B 0,678 und 0,268. Die Fehler von Weg 1 liegen fast alle
dort, wo auch die Kodierer zwischen zwei Feldern schwankten.

### 4.4 Fehlerbild von Weg 1

F1 je Klasse (Gold/vorhergesagt): Verkehr 0,96 (78/83), Wohnen 0,95 (31/30), Soziales 0,84 (32/35),
Staat und Verwaltung 0,83 (33/37), Bildung 0,83 (12/17), Umwelt 0,81 (29/25), Wirtschaft 0,80 (8/7),
Energie 0,80 (8/7), Kultur 0,78 (27/19), Bürgerrechte 0,77 (7/6), Technik 0,75 (4/4), Flächen 0,58
(9/15), Haushalt 0,57 (3/4), Ordnung 0,55 (8/3), Gesundheit 0,50 (7/5); 4, 9, 19 je 1/1 richtig, 5
(1/0) falsch. Häufigste Verwechslungen (Gold → Weg 1): Kultur → Soziales 5, Kultur → Bildung 3,
Umwelt → Flächen 3, Umwelt → Staat und Verwaltung 2, Flächen → Verkehr 2 (47 Fehler insgesamt).
Kultur wird unterschätzt: Zuschüsse an Schützen- und Heimatvereine gibt das Modell an 13, die
Programme „Kultur und Schule" und kulturelle Bildung an 6. Flächen wird überschätzt: Wasserspender
auf Plätzen, eine Baumscheibe, Mahd am Deich sind nach den Labels Umwelt, eine Platzsanierung Wohnen,
eine Rattenplage auf einem Platz Gesundheit. Das sind genau die Stellen, für die der Schlichter Regeln
einer Fassung 2 des Codebuchs vorschlägt (Frage 9.16).

**Weg 3b** hat 49 Fehler und ein ausgeglicheneres Bild: Flächen 0,76 (9/12) statt 0,58, Umwelt 0,86,
Wohnen 0,89, Kultur 0,80 (27/23), dafür Gesundheit 0,53 (7/8) und Ordnung 0,55 (8/3) wie bei Weg 1;
Verkehr 0,96. Häufigste Verwechslungen: Kultur → Soziales 3, Kultur → Bildung 2, Kultur → Staat und
Verwaltung 2, Verkehr → Umwelt 2, Wohnen → Soziales 2.

## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

**Endgültiges Urteil (2026-11-24, 02:20 Uhr): bauen mit Weg 3b**, `xlm-roberta-large` feinjustiert auf
den menschlich kodierten deutschen CAP-Daten und den Silberlabels von Weg 1 (Gewichte `80ca2a82…`).
Nach der vorab festgelegten Regel (`b813d43`, § 8.3, § 8.5, § 8.6), ohne Anpassung an die Labels:

- **α 0,943** zwischen den Kodierern: das Urteil gilt, Stufe 3 ist erlaubt. Kodierer und Schlichter
  sind dasselbe Modell (`claude-opus-5-5`, Frage 19, Annahme gilt): die Labels sind das Urteil eines
  Modells, nicht von Menschen, und α ist eine obere Schätzung der Schärfe des Codebuchs.
- **3b statt 3a**: Silberlabels liegen für 4 200 Ratsdokumente vor, mehr als die 2 000 aus § 8.3; 3a
  (0,509) geht nicht ins Urteil.
- **Zwei Wege erfüllen das Kriterium** (Makro-F1 ≥ 0,70 und im gepaarten Bootstrap besser als die
  bessere Ausschussvariante 2B):
  - Weg 1, `qwen3.6:27b` mit dem Codebuch im Systemprompt: **0,753** (0,658–0,822), gegen 2B +0,511
    (2,5-%-Perzentil +0,379);
  - Weg 3b: **0,704** (0,620–0,807), gegen 2B +0,462 (2,5-%-Perzentil +0,355).
- **Auswahl nach § 8.5**: der Vorsprung von Weg 1 vor 3b ist im gepaarten Bootstrap nicht über 0
  (2,5-%-Perzentil −0,047). Dann wird der billigere gebaut, Weg 3 vor Weg 1, gemessen in GPU-Stunden
  für alle Perioden: 3b sagt alle 45 483 Dokumente in geschätzt unter 15 GPU-Minuten vorher, Weg 1
  bräuchte 11,0 bis 13,8 GPU-Stunden.
- **Die Rückfallregel greift nicht**, weil Wege das Kriterium erfüllen. Zur Information: Weg 1 und 3b
  sind sich bei 270 von 300 einig (gewichtet 0,900), dort Makro-F1 0,775 und Genauigkeit 0,881.
- **Was das Urteil nicht sagt.** 3b liegt mit 0,704 knapp über der Schwelle, sein Intervall reicht bis
  0,620; die Regel verlangt den Punktwert. 3b ist zum großen Teil eine Destillation von Weg 1 (sein
  Lehrer liefert die Ratsdokumente, und beide sind sich in 90 % einig): wer den Prompt oder das Modell
  von Weg 1 ändert, muss 3b neu trainieren. Auf menschlich kodierten Bundestagstiteln liegt 3b mit
  0,688 über Weg 1 (0,579), weil er diese Textsorte im Training gesehen hat.
- **Weg 2** ist mit 0,242 (2B) und 0,191 (2A) kein brauchbares Politikfeld; er bleibt, was er ist, die
  Zuordnung zu einem Ausschuss.

Das vorläufige Urteil von 00:50 Uhr (bauen mit Weg 1, gerechnet mit 3a statt 3b, Commit `3603a21`)
hatte diesen Ausgang vorab benannt; es ist überholt.

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

**Das Urteil ist Weg 3b.** Der Klassifikator braucht torch, das nie ins Paket darf (Plan § 2.8,
`uv.lock`); darum zwei Teile:

1. **Vorhersage außerhalb des Pakets** (Trainings-Venv `/media/konrad/xtraspace/venvs/cap-train`):
   `docs/plans/19-politikfelder-training.py` bekommt `--vorhersage <profil>`; es liest die Eingabe je
   Dokument (Titel und die ersten 1 500 Zeichen des Rohtexts, Leerraum zusammengezogen, wie
   `schreibe_eingabe()`), die das Paket mit einem kleinen Befehl `georep policy-areas export
   <profil>` als Parquet schreibt, sagt mit den Gewichten `training-3b/beste` (SHA-256 `80ca2a82…`)
   vorher und schreibt `politikfelder.parquet` mit Wahrscheinlichkeit. Unter der GPU-Sperre, alle
   Profile zusammen geschätzt unter 15 Minuten. Die Gewichte (2,24 GB) bleiben auf xtraspace, ihr
   SHA-256 steht im README des Pakets.
2. **Im Paket nur das Ergebnis**: `georep pack --policy-areas --from <datei>` friert die Datei je
   Profil ein (`snapshots/<profil>-politikfelder/`), `bootstrap` kopiert sie, und der Beitrag
   `policy_areas` (offline, ohne Modell) prüft sie gegen den Korpus (eine Zeile je Korpus-ID,
   Codes aus der Menge) und reicht sie an Seite und Tabellen weiter.

Der Plan für Weg 1 unten bleibt der Rückweg, wenn ein späterer Lauf zeigt, dass 3b auf einer anderen
Periode nicht trägt (Frage 9.17): dieselbe Ausgabe, nur mit `quelle = llm`. Die Teile „Ausgabe",
„Verträge", „Paket" und „Für Vorhaben 22" gelten für beide.

**Rückweg Weg 1** (nicht gewählt):

**Beitrag `policy_areas`** nach F2 (`src/georep/enrich/policy_areas.py`), ein Schritt mit Modell:

- `policy_areas` (`models=GenerationUse(...)`, läuft nur mit `--models`, F5): liest Korpus (`id`, `name`,
  `paper_type`, `file_name`) und den Rohtextstore von F1 (`rohtexte.parquet`; ohne ihn den
  Korpustext, dann mit eigener Prompt-Version, weil der Ausschnitt anders aussieht), baut je Dokument
  den Nutzerprompt (Dokumentart, Titel, die ersten `chars` Zeichen) und den Systemprompt aus dem
  Codebuch, ruft `generate_texts` (Cache unter `cache_root/ml/`, fortsetzbar), parst die Antwort.
  Schreibt `processed/politikfelder.parquet`.
- Ohne `--models` kommt die Datei aus dem Paket (`bootstrap`), wie jedes Modellergebnis (Plan § 2.8).

**Ausgabe** (Schema-Version aus `POLICY_AREAS_SCHEMA_VERSION = 1`):

| Datei | Spalten | Schlüssel, Ordnung |
|---|---|---|
| `politikfelder.parquet` | `id` str, `politikfeld` str (Code aus `CODES` oder leer, wo kein Text oder keine gültige Antwort), `quelle` str (`llm`; bei Weg 3 `klassifikator`, bei der Rückfallregel `einigkeit`), `modell` str (Name und Digest), `prompt` str (Version), `abgeschnitten` bool | eine Zeile je Korpus-ID, sortiert nach `id` |

Dazu eine Tabelle der Namen (`politikfeld` → deutscher Name, Kurzname für die Seite) als Konstante im
Modul, nicht im Profil: die Hauptthemen sind stadtneutral.

**Verträge** (Prädikate in `georep.contracts`): eine Zeile je Korpus-ID (`one_row_per_document`),
`politikfeld` ∈ `CODES` ∪ {""}, leer genau dort, wo der Text leer ist oder die Antwort ungültig;
sortiert nach `id`. Der Parser ist rein (`parse(antwort) -> str`) mit `deal.ensure` auf die Menge.

**Tests** (nie ein Modell, Fakes aus `tests/fakes.py`): Beispiele mit `FakeGenerator`, der `THEMA: 10`
und Unsinn liefert; Parser als hypothesis-Eigenschaft in `tests/property/` (beliebiger Text → Code oder
leer, nie eine Ausnahme; jede gültige Form wird erkannt); Systemprompt bytegleich zum eingefrorenen
SHA-256 (`b19eaa09…`), solange die Prompt-Version `19-cap-1` heißt; Stamp nennt Modell, Digest, Prompt;
Schritt ohne `--models` übersprungen; Paket bootstrapbar.

**Codebuch im Paket.** Der Systemprompt braucht das Codebuch zur Laufzeit. Es enthält Düsseldorfer
Beispiele („Rheinbahn", „Tonhalle", „Volksgarten", „Rheinufer"), und `tests/unit/test_report_city.py`
lässt im Paket nur `literatur.toml` als TOML neben `defaults.toml` zu. Darum: die stadtneutralen Teile
(Grundregeln, Definitionen) nach `src/georep/enrich/policy_codebook.toml` mit einer Ausnahme im
Stadtwort-Test, die Beispiele mit Ortsnamen als `[policy_areas.examples]` ins Profil; der Prompt
setzt beides zusammen. Für `duesseldorf` muss das Ergebnis bytegleich zum eingefrorenen Prompt sein
(Test); für andere Städte ist es ein anderer Prompt mit eigener Version und ohne Validierung
(„explorativ", Frage 9.10).

**Settings** (Block `# --- Vorhaben 19: Politikfelder` am Ende von `defaults.toml`, Modell vor `class
Settings`): `[policy_areas]` `enabled = false`, `model = "qwen3.6:27b"` (sonst `[ml.generation]`),
`prompt_version = "19-cap-1"`, `chars = 4000`, `num_predict = 64`. Nicht im Fingerprint, was im Stamp
des Modellschritts steht (F5).

**Paket** `georep pack --policy-areas` → `snapshots/<profil>-politikfelder/processed/politikfelder.parquet`
mit README (Modell, Digest, Prompt, SHA-256, Lizenz CC BY-NC-SA 4.0 für die Codes, Frage 9.4).
Größe rund 40 KB je Hauptperiode (eine Probe gleicher Form mit 19 108 Zeilen, zstd 19: 36 KB), unter
100 KB für alle vier Profile.

**Lauf**: über die GPU-Warteschlange, je Profil ein Auftrag in Blöcken zu 2 000 Dokumenten (rund
30 Minuten): 2014–2020 5,3 h, Hauptperiode 4,6 h, ab 2025 1,0 h, Mönchengladbach 0,2 h.

**Berührte Dateien**: `src/georep/enrich/policy_areas.py` (neu), `src/georep/enrich/__init__.py` (eine
Zeile), `src/georep/enrich/policy_codebook.toml` (neu), `src/georep/settings.py` und `defaults.toml`
(Anhängeregel), `src/georep/profiles/duesseldorf.toml` (Beispiele), `src/georep/pack.py` und
`bootstrap.py` (Paketregister), `tests/unit/test_policy_areas.py`, `tests/property/test_policy_parse.py`,
`tests/unit/test_report_city.py` (Ausnahme), `docs/architecture.md`, `docs/decisions.md` (Punkt beim
Merge).

**Ausgabe für Weg 3b**: wie oben, `quelle = klassifikator`, `modell` = `xlm-roberta-large@80ca2a82`,
`prompt` leer, dazu `wahrscheinlichkeit` float (die Softmax des gewählten Themas); ohne Text eine
leere Zeile. Die Einigkeitsregel bleibt ungenutzt (sie greift nicht), kann aber als Variante gezeigt
werden, wenn Weg 1 für eine Periode doch läuft (`quelle = einigkeit`, leer bei Uneinigkeit).

**Berührte Dateien für Weg 3b**: `src/georep/enrich/policy_areas.py` (neu, ohne Modell und ohne torch:
Export der Eingabe, Prüfung und Weitergabe des Pakets), `src/georep/enrich/__init__.py` (eine Zeile),
`src/georep/cli.py` (`policy-areas export`), `src/georep/pack.py` und `bootstrap.py` (Paket mit
`--from`), `settings.py` und `defaults.toml` (Anhängeregel: `[policy_areas]` `enabled = false`,
`chars = 1500`, `weights_sha256`), `docs/plans/19-politikfelder-training.py` (`--vorhersage`),
`tests/unit/test_policy_areas.py` (Export bytegleich zu `schreibe_eingabe()`, Prüfung des Pakets:
fehlende und doppelte IDs, fremde Codes), `docs/architecture.md`, `docs/decisions.md` (Punkt beim
Merge). Kein Codebuch im Paket nötig (Frage 9.10 entfällt für 3b); die Gewichte nennen nur ihre
Prüfsumme.

**Für Vorhaben 22**: Verkehr = Hauptthema 10 (statt Klasse `OVA`), Schule = 6 (statt `SCHUA`); Jugend
steckt in 13 zusammen mit Sozialem und Sport (Frage 9.6).

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

**Unterseite `themen.html`** im Rahmen der Hauptseite (`report.pages.Page`, F2), je Profil mit
`politikfelder.parquet`:

1. *Politikfelder je Periode*: gestapelte Leiste je Periode (21 Felder plus „nicht bestimmt"), Anteil
   und Zahl, für Rat und Ausschüsse sowie Bezirksvertretungen getrennt.
2. *Je Fraktion*: Anteile der Felder an den Fraktionsdokumenten (Urheber aus
   `dokumente_urheber.parquet`, gemeinsame Anträge nach Vorhaben 15 jeder Fraktion), Fraktionen unter
   30 Dokumenten ohne Anteile; für alle Fraktionen gleich gebaut.
3. *Je Wahlbezirk*: Anteile der Felder an den Dokumenten mit Treffer im Wahlbezirk (Index der Arbeit),
   als Tabelle und als Karte für ein gewähltes Feld (wie `karte.html`), mit dem Hinweis auf den
   ökologischen Fehlschluss (wie 22).
4. *Vergleich mit dem Bundestag*: Anteile der Felder an den Anfragen des Bundestags 1976–2005 (CAP
   Deutschland, abgeleitete Anteile mit Quellenangabe und Lizenz), nur als Einordnung („andere Ebene,
   andere Zeit").
5. *Wie die Felder entstehen*: Codebuch als Link, Modell, Prompt-Version, und die Validierung im
   Wortlaut aus `guete.json`: „geprüft von zwei KI-Kodierern desselben Modells an 300 Dokumenten,
   nicht von Menschen", Makro-F1 mit Intervall, dazu die zweite Prüfung an menschlich kodierten
   Bundestagstiteln mit ihrer Zahl. Mit den Werten dieser Messung: „Politikfeld je Dokument von einem
   Klassifikator (XLM-RoBERTa), trainiert auf von Menschen nach dem CAP kodierten Bundestagsanfragen
   und Wahlprogrammen und auf Labels eines lokalen Sprachmodells für Ratsdokumente; geprüft von zwei
   KI-Kodierern desselben Modells an 300 Dokumenten der Periode 2020–2025, nicht von Menschen:
   Genauigkeit 84 %, Makro-F1 0,70 (0,62–0,81); an 200 von Menschen kodierten Bundestagsanfragen
   Makro-F1 0,69."

Größe geschätzt **60 bis 90 KB** ohne Karte (vier Leisten, eine Tabelle Fraktion × Feld von höchstens
10 × 22, eine Tabelle Wahlbezirk × Feld von 41 × 22); die Karte bringt die Geometrie der 41 Wahlbezirke
mit (`karte.html` wiegt heute 238 KB), zusammen bis rund 300 KB, unter dem Budget von 500 KB. **Tabellen
im Register**: `politikfelder` (Parquet und CSV, Lizenzzeile). Stufe 3 nur mit `alpha_genuegt = true`
(α ≥ 0,8).

## 8. Vorab festgelegt (2026-11-23, vor jedem Lauf eines Verfahrens und vor der Kodierung)

### 8.1 Kodierschema

- **Die 21 Hauptthemen des CAP-Master-Codebuchs** (Version 1.1 vom 2022-08-09) mit ihren Nummern: 1
  Makroökonomie, 2 Bürgerrechte, 3 Gesundheit, 4 Landwirtschaft, 5 Arbeit, 6 Bildung, 7 Umwelt, 8
  Energie, 9 Migration, 10 Verkehr, 12 Recht und Kriminalität, 13 Soziales, 14 Wohnen und
  Stadtentwicklung, 15 Binnenwirtschaft, 16 Verteidigung, 17 Technik, 18 Außenhandel, 19
  Internationales, 20 Staat und Verwaltung, 21 Öffentliche Flächen und Wasser, 23 Kultur. Dazu **99
  „kein Politikfeld erkennbar"** als 22. Option. Unterthemen (vierstellig) kodiert niemand; ein
  Verfahren darf sie ausgeben, gemessen wird das Hauptthema.
- **Ein Thema je Dokument**, das vorherrschende (Grundregel 1 des deutschen CAP-Codebuchs v2.5: die
  Sache, nicht die Zielgruppe, nicht das Instrument). Geld folgt der Sache; der Ort entscheidet nichts.
- **Abbildung auf kommunale Themen**: je Option eine Definition mit dem, was in einer Stadt dazugehört,
  und den Grenzfällen, in `validierung/19-politikfelder/codebuch.toml` (Fassung 2026-11-23.1). Wo das
  deutsche Codebuch eine Sache ausdrücklich verortet, folgt die Abbildung ihm, weil die menschlich
  kodierten deutschen Daten von Weg 3 danach kodiert sind: Kitas und Kinder- und Jugendhilfe 13
  (1308), Vereine und Amateursport 13 (1305), Spielplätze und Kleingärten 14 (1401), öffentliche
  Bibliotheken 6 (607), Denkmalschutz und Parks 21 (2101), Tierschutz bei Haustieren 4,
  Barrierefreiheit als Zugang 2 (205). Was keines der Codebücher regelt, legt diese Fassung fest:
  Feuerwehr und Katastrophenschutz 15 (1523), Zivilschutz 16 (1615), Rettungsdienst 3 (322),
  Friedhöfe 21, Straßenbenennungen und Ehrungen 20, Verfügungsmittel nach ihrem Zweck.
- **Verwaltungsinterna sind ein Politikfeld, nicht „keins"**: Sitzungstermine, Geschäftsordnung, Wahl
  und Besetzung von Gremien, Beschlusskontrollen ohne vorherrschendes Thema, Personal und Organisation
  der Verwaltung, Wahlen, Sammlungen ohne vorherrschendes Feld sind 20 (Staat und Verwaltung), wie im
  CAP (2002, 2004, 2005, 2011, 2012). **99** nur, wenn der Ausschnitt keinen Gegenstand erkennen
  lässt (leer, unlesbar, nur Deckblatt); im Zweifel das Feld. 99 zählt im Maß als eigene Klasse.
- Zweite Frage `unsicher` (ja/nein, ohne Schlichtung) für die Auswertung der Grenzfälle.

### 8.2 Testmenge (F4) und Entwicklungsmengen

- **Testmenge**: 300 Dokumente der Hauptperiode (`duesseldorf`, 2020 bis 2025) mit Text, geschichtet
  nach Gremiumsart (Bezirksvertretung, Ausschuss, Rat, Beirat; `papers_gremien.parquet`) × Gruppe der
  Dokumentart (Beschlussvorlage, Informationsvorlage, Antrag, Anfrage, Eingabe), proportional,
  Seed 20261123, gezogen mit `georep validate sample` (F4) aus der Grundgesamtheit, die das Messskript
  schreibt. **Die 300 sind Testdaten**: kein Training, keine Silberlabels, kein Prompt- und kein
  Parameter-Tuning an ihnen. Jedes Verfahren läuft auf ihnen genau einmal, in der vorher eingefrorenen
  Fassung; ein zweiter Lauf nur nach einem technischen Fehler (Abbruch, Parserfehler), mit
  unveränderter Fassung und Vermerk.
- **Entwicklungsmenge Ratsdokumente**: 200 Dokumente derselben Grundgesamtheit ohne die 300, gleiche
  Schichtung, Seed 20261124, nur IDs im Repo (`validierung/19-politikfelder/entwicklung.csv`). An ihr
  darf das Prompt-Format (Antwortform, Parser, Länge) eingestellt werden; ihre Antworten sind
  Silberlabels für Weg 3b. Gold gibt es dort nicht, also kein Tuning auf eine Zahl.
- **Zweite Prüfung an menschlichen CAP-Daten** (§ 2.6, Stufe 3): 200 Titel der deutschen
  CAP-Anfragen 1976 bis 2005 (Seed 20261125, geschichtet nach Hauptthema, proportional), nicht im
  Training von Weg 3; dazu die zurückgehaltenen 10 % der deutschen CAP-Daten für Weg 3. Andere
  Textsorte, darum nur berichtet, nicht im Kriterium.

### 8.3 Die drei Wege

| Weg | Verfahren | Eingabe | eingefroren vor dem Testlauf |
|---|---|---|---|
| **1** LLM mit Codebuch | `qwen3.6:27b` über die Naht von F5 (`GenerationUse`, `generate_texts`, Modellcache), Temperatur 0, Seed 0, `num_ctx` 8192, `think` aus, `num_predict` 64. Systemprompt = das Codebuch (Grundregeln, alle 22 Optionen mit Definition und Beispiel), wörtlich aus `codebuch.toml` erzeugt; Antwortform `THEMA: <Nummer>` | Dokumentart, Titel, die ersten 4 000 Zeichen des Rohtexts: dasselbe Material wie die Kodierer | Prompt-Version und SHA-256 des Systemprompts in einem Commit vor dem Testlauf. Nebenlauf (nicht fürs Urteil, nur für die Kosten): `gemma4` mit demselben Prompt |
| **2** Ausschuss → CAP | die bestehende Ausschusszuordnung (Punkt 45, `committees`) und eine feste Tabelle Ausschuss → Hauptthema (§ 8.4). **2A**: `papers_ausschuss.parquet` wie die Kette sie schreibt, Restklasse → 99. **2B**: dasselbe Modell ohne Schwelle (`min_probability = 0`), jedes Dokument bekommt seinen wahrscheinlichsten Ausschuss | Korpustext, wie die Kette | Tabelle § 8.4. Vergleichsmaß ist **die bessere von 2A und 2B** auf der Testmenge |
| **3** Klassifikator (Nachbau der Babel Machine) | `xlm-roberta-large` (MIT-Lizenz, Gewichte als safetensors, kein Fremdcode), feinjustiert in einem eigenen Venv außerhalb des Pakets, unter der GPU-Sperre in Blöcken. **3a**: nur menschlich kodierte deutsche CAP-Daten (Anfragentitel und Wahlprogrammsätze, § 2). **3b**: dazu Silberlabels von Weg 1 auf Ratsdokumenten außerhalb der Testmenge (mindestens die 200 der Entwicklungsmenge; ein Auftrag an die GPU-Warteschlange für 4 000 weitere) | Titel und Textanfang, auf 256 Token gekürzt | Hyperparameter fest: Länge 256, Lernrate 1e-5, Stapel 16, zwei Epochen, 10 % Aufwärmen, Seed 0, Auswahl des Prüfpunkts nach Makro-F1 auf den zurückgehaltenen 10 % der CAP-Daten (nie auf Ratsdokumenten). Ins Urteil geht 3b, wenn zum Zeitpunkt der Auswertung Silberlabels für mindestens 2 000 Ratsdokumente vorliegen, sonst 3a |

Nebenverfahren ohne Einfluss auf das Urteil: TF-IDF mit logistischer Regression auf denselben
CAP-Daten (CPU), als Maß, wie weit die Textsorte trägt. Die Babel Machine selbst (Dienst oder
Gewichte) wird nicht benutzt (Konrad, 2026-11-23, Frage 5).

### 8.4 Tabelle Ausschuss → Hauptthema (Weg 2)

Je Ausschuss das Feld, das Name und Zuschnitt am stärksten tragen, festgelegt nach den Namen in
`profiles/duesseldorf.toml` und sechs Titeln je Ausschuss, ohne Blick auf ein Ergebnis eines
Verfahrens. Wortgleich als `AUSSCHUSS_CAP` im Messskript.

| Kürzel | Ausschuss | CAP |
|---|---|---|
| ABA | Anregungs- und Beschwerdeausschuss | 20 |
| ADIG | Digitalisierung und allgemeine Verwaltungsorganisation | 20 |
| AGS | Gesundheit und Soziales | 13 |
| APS | Planung und Stadtentwicklung | 14 |
| AUS | Umwelt-, Klima- und Verbraucherschutz | 7 |
| AWIR, AWIZ | Wirtschaftsförderung, internationale (und regionale) Zusammenarbeit | 15 |
| AWM | Wohnungswesen und Modernisierung | 14 |
| AÖE | öffentliche Einrichtungen, Stadtökologie, Abfallmanagement, Bevölkerungsschutz | 7 |
| BAU | Bauausschuss (städtische Hochbauten) | 20 |
| GLA | Gleichstellung und Antidiskriminierung | 2 |
| HFA | Haupt- und Finanzausschuss | 1 |
| JHA | Jugendhilfeausschuss | 13 |
| KUA | Kulturausschuss | 23 |
| OVA | Ordnungs- und Verkehrsausschuss | 10 |
| RPAU | Rechnungsprüfungsausschuss | 20 |
| SCHUA | Schulausschuss | 6 |
| SEBD | Betriebsausschuss Stadtentwässerung | 7 |
| SPOA | Sportausschuss | 13 |
| WALTW, WABTW, WPA, AWTL, POA | Wahl-, Wahlprüfungs-, Personal- und Organisationsausschüsse | 20 |
| ACI | Chancengerechtigkeit und Integration | 9 |
| Restklasse (nur 2A) | – | 99 |

### 8.5 Maß, Kriterium, Entscheidung

- **Gold**: das geschlichtete Label der Frage `politikfeld` (zwei Kodier-Agenten, Schlichtung, F4).
- **Hauptmaß**: Makro-F1 wie `georep validate score` (F4): ungewichtetes Mittel der F1 über die
  Klassen mit Gold oder Vorhersage, 99 als eigene Klasse, auf den 300 ohne Schichtgewichte (Güte je
  Klasse, keine Prävalenz). Intervall: Bootstrap über die Dokumente, 2 000 Ziehungen, Seed 20261123,
  Perzentile 2,5 und 97,5.
- **Kriterium** (Briefing, unverändert): **Makro-F1 ≥ 0,70 und besser als die Ausschussabbildung.**
  Festgelegt wird hier, was das heißt: der Punktwert ≥ 0,70 (das Intervall wird berichtet), und
  „besser" heißt, dass im gepaarten Bootstrap (dieselben 2 000 Ziehungen) die Differenz Weg minus
  bessere Ausschussvariante im 2,5-%-Perzentil über 0 liegt. Ein Weg, der nur im Punktwert vorn
  liegt, schlägt die kostenlose Ausschusszuordnung nicht nachweislich.
- **Entscheidung**: Erfüllen mehrere Wege das Kriterium, wird der mit dem höchsten Makro-F1 gebaut;
  ist dessen gepaarter Vorsprung vor dem nächsten nicht über 0 (2,5-%-Perzentil), der billigere
  (Weg 3 vor Weg 1, gemessen in GPU-Stunden für alle Perioden).
- **Übereinstimmung der Kodierer**: Krippendorffs α (nominal) für `politikfeld`. Unter 0,67 gibt es
  kein Urteil über die Wege: das Codebuch ist zu unscharf, Fassung 2 mit neuer Stichprobe in einem
  eigenen Ordner (F4). Zwischen 0,67 und 0,8 ist das Urteil vorläufig und Stufe 3 gesperrt (§ 2.6).
- **Nebenmaße** ohne Einfluss: Genauigkeit, Cohens κ gegen Gold, F1 je Klasse mit Zahl der
  Gold-Dokumente, Makro-F1 nur über Klassen mit mindestens fünf Gold-Dokumenten, gewichtetes
  Makro-F1, Verwechslungsmatrix, Übereinstimmung der Wege untereinander, Anteil `unsicher` und Güte
  ohne die unsicheren Dokumente, Güte je Schicht.

### 8.6 Rückfallregel

Erfüllt kein Weg das Kriterium, gilt die **Einigkeitsregel**: ein Politikfeld bekommt nur, wo Weg 1
und Weg 3 dasselbe Hauptthema sagen, sonst „nicht bestimmt" (wie der Konfidenzfilter von ParlaCAP,
dort „Mix"). Gebaut wird sie, wenn auf den Dokumenten mit Einigkeit **Makro-F1 ≥ 0,70**, im
gepaarten Bootstrap **besser als die Ausschussabbildung auf denselben Dokumenten**, und die
**Abdeckung**, mit den Schichtgewichten hochgerechnet, **mindestens 70 %** ist. Sonst: verwerfen;
die Seite behält die Ausschusszuordnung (Punkt 45), Vorhaben 22 seine Klassen `OVA`, `JHA`, `SCHUA`.

### 8.7 Zweite Prüfung an menschlich kodierten Daten

Weg 1 auf den 200 CAP-Anfragentiteln (§ 8.2), Weg 3 auf den zurückgehaltenen 10 % der deutschen
CAP-Daten, beide gegen die menschlichen Codes: Makro-F1 mit Bootstrap-Intervall. Berichtet, nicht im
Kriterium (Bundestag 1976 bis 2005, Titel statt Ratsdokument). Sie ist die einzige Zahl dieses
Vorhabens, hinter der Menschen stehen.

### 8.8 Eingefroren vor dem ersten Testlauf (2026-11-23, 23:10 Uhr)

- **Weg 1**: Prompt-Version `19-cap-1` unverändert seit der Vorab-Festlegung; Systemprompt aus
  `codebuch.toml` (Fassung 2026-11-23.1) mit `systemprompt()` des Messskripts, **18 307 Zeichen,
  SHA-256 `b19eaa091e801db97bda50f6824666675a3f92ebf66116349b04a820caf7efa4`**; Nutzerprompt
  `nutzerprompt()`, Parser `ANTWORT` (erste Nummer hinter `THEMA:`), `num_predict` 64. Geprüft an 20
  Dokumenten der Entwicklungsmenge (alle 20 in der Antwortform, keine Änderung nötig).
- **Weg 3**: Trainingsskript `19-politikfelder-training.py` mit den Werten aus § 8.3, Gewichten von
  `FacebookAI/xlm-roberta-large` im Stand `c23d21b0620b635a76227c604d44e43a9f0ee389` (MIT,
  safetensors); Eingabe je Ratsdokument: Titel und die ersten 1 500 Zeichen des Rohtexts, Leerraum
  zusammengezogen (`schreibe_eingabe()`). Für 3b werden die Silberlabels so oft wiederholt, dass sie
  rund ein Viertel der Beispiele stellen, höchstens 20-fach; nur Antworten von `qwen3.6:27b` mit
  gültiger Nummer, nie von Dokumenten der Testmenge.
- **Silbermenge**: 4 000 Ratsdokumente außerhalb von Test- und Entwicklungsmenge, gleiche Schichtung,
  Seed 20261126 (`schreibe_silber()`; IDs unter `$GEOREP_MESSDATEN/19-politikfelder/silber.csv`).

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 9.1 | Soll das Hauptmaß das Makro-F1 über **Klassen mit mindestens fünf Gold-Dokumenten** sein statt über alle Klassen mit Gold oder Vorhersage? | Bei 300 Dokumenten und 22 Klassen haben nach der Verteilung von Weg 1 acht Klassen höchstens drei Dokumente (5, 16, 18, 99 keines; 4, 9, 19 eines; 12 drei). Eine Klasse mit einem Gold-Dokument und einem Fehler zählt mit F1 0 so viel wie Verkehr mit 83; eine einzige falsche Vorhersage in eine leere Klasse ebenso. Das Kriterium misst dann vor allem die seltenen Klassen. Nur der Supervisor darf das vor der Kodierung ändern (Plan § 4) | **entschieden vor der Auswertung (Frage 36 des Supervisors): Hauptmaß wie festgelegt**, das Makro über Klassen mit ≥ 5 Gold-Dokumenten als Nebenmaß. Ergebnis: 19 Klassen mit Gold, 13 mit ≥ 5; Weg 1 0,753 (Hauptmaß) und 0,769 (Nebenmaß) |
| 9.2 | Die Ausschnitte nennen oft den Ausschuss (84 der 300 beginnen mit einem Ausschusskürzel in der Drucksachennummer, 69 nennen einen Ausschussnamen, meist in der Beratungsfolge). Bevorzugt das Gold damit Weg 2? | Kodierer und Weg 1 sehen den Hinweis, Weg 2 ist aus ihm gebaut; Grundregel 2 sagt „Hinweis, nicht Kriterium" | hingenommen; **gemessen (§ 4.3)**: der Hinweis hilft 2B (Genauigkeit 0,714 mit, 0,537 ohne Kürzel), nicht Weg 1 (0,833 mit, 0,847 ohne) |
| 9.3 | Kodierer B ein anderes Modell (Frage 19 aus F4)? | Die Kodierer sind Opus, Weg 1 ist qwen: das Urteil misst qwen gegen Opus, nicht gegen Menschen. Die zweite Prüfung (0,58 gegen Menschen auf Bundestagstiteln) ist die einzige menschliche Zahl | Opus für beide **und für den Schlichter** (Annahme gilt, Supervisor 2026-11-24); das Urteil nennt es, die Seite sagt „desselben Modells" |
| 9.4 | Lizenz: die CAP-Codes und alles, was sie bearbeitet, sind CC BY-NC-SA 4.0. Darf `codebuch.toml` so im GPL-Repo liegen, und steht `politikfelder.parquet` unter derselben Lizenz? | ShareAlike verlangt dieselbe Lizenz für Bearbeitungen; NonCommercial verbietet kommerzielle Nutzung. Weg 1 nutzt nur das Codebuch, Weg 3 trainiert auf CAP-Daten | Codebuch mit Lizenzvermerk im Kopf (erledigt); Paket und Tabelle der Seite tragen „Codes nach dem CAP, CC BY-NC-SA 4.0" mit Zitat; die Seite ist nicht kommerziell. Vor Stufe 2 bestätigen lassen |
| 9.5 | ParlaCAP-train (CC BY 4.0, GPT-4o-Labels, darunter österreichische Nationalratsreden auf Deutsch) als zusätzliche Silberdaten für 3b? | mehr deutschsprachige, parlamentarische Beispiele; aber nicht von Menschen und fremde Lizenz neben CC BY-NC-SA | nein, nicht in dieser Runde |
| 9.6 | Vorhaben 22 braucht „Jugend" getrennt; CAP legt Kitas, Jugendhilfe, Sport und Sozialhilfe zusammen in 13 | H3 von 22 misst Jugend und Schule | 22 nimmt 6 (Schule) aus 19 und behält `JHA` aus der Ausschusszuordnung; ein Unterthema (1308) bräuchte eine eigene Frage im Codebuch (Fassung 2) |
| 9.7 | Sport in 13 (deutsches Codebuch, 1305 Amateursport) statt 15 (Master-Codebuch, 1526) | Vergleich mit anderen Ländern; Sport ist in Städten häufig | deutsches Codebuch, weil die deutschen Trainingsdaten danach kodiert sind; die Seite nennt die Regel |
| 9.8 | Weg 3 braucht torch zur Vorhersage, das nie ins Paket darf | **gilt jetzt**: 3b ist gewählt | § 6: Vorhersage im Trainings-Venv, im Paket nur das Ergebnis mit der Prüfsumme der Gewichte |
| 9.9 | gemma4 als billigere Fassung von Weg 1 (6,6 statt 11,0 GPU-Stunden)? | an menschlichen Bundestagstiteln 0,39 statt 0,58 | nein; qwen, die Hochrechnung trägt es |
| 9.10 | Andere Städte (Mönchengladbach): nicht validiert | 3b ist auf Düsseldorfer Silberlabels trainiert; Weg 1 hätte einen Prompt mit Düsseldorfer Beispielen | 3b für alle Profile, Mönchengladbach auf der Seite „explorativ" bis zu einer eigenen Stichprobe |
| 9.11 | 99 kommt in Weg 1 nie vor, Verwaltungsinterna sind 20 | wenn die Kodierer 99 öfter vergeben, kostet es Weg 1 eine Klasse | Codebuch wie festgelegt; Uneinigkeiten 20/99 werden in der Auswertung gezählt |
| 9.12 | Die Ausschnitte sind die ersten 4 000 Zeichen; 59 der 300 Texte sind länger | der Gegenstand steht in Ratsdokumenten fast immer im Titel und Betreff | hingenommen, für Kodierer und Weg 1 gleich |
| 9.13 | Silberlabels und Training 3b vor der Auswertung laufen lassen? | sonst ginge 3a ins Urteil (§ 8.3) | **erledigt**: `gpu-queue/19-silber.sh` lief 2026-11-24 von 00:18 bis 02:11 Uhr (Silberlabels 74,6 min, Training 37,8 min); 4 000 von 4 000 gültig. Die Silberblöcke zu 2 000 Dokumenten dauerten unter Last je 37 Minuten, länger als die geplanten 30 |
| 9.14 | Rückfallregel | greift nur, wenn kein Weg das Kriterium erfüllt | **greift nicht** (zwei Wege erfüllen es); zur Information mit 3b: 270 von 300 einig, Abdeckung 0,900, dort Makro-F1 0,775 |
| 9.15 | Das Trainings-Venv braucht `torch 2.13.0+cu129` vom PyTorch-Index (`download.pytorch.org/whl/cu129`), weil der Treiber 575.57 nur CUDA 12.9 kann; PyPI liefert heute CUDA 13.2 | eine zweite Paketquelle neben PyPI; ein Treiber-Update würde es ändern | hingenommen für ein Venv außerhalb des Pakets; Versionen in § 3.4 |
| 9.16 | Fassung 2 des Codebuchs mit den Regeln, die der Schlichter an den 15 Uneinigkeiten formuliert hat: **Zweck gegen Mittel** (das Ziel einer Maßnahme entscheidet, nicht der Ort oder das Instrument, etwa Infektionsschutz in Schulen 3, Prävention gegen Übergriffe 12); **ein Bauantrag ist 14**; **Vereinszuschuss nach Vereinszweck** (Schützen- und Heimatverein, Straßenfest 23 wie Brauchtum, Sportverein 13); **kulturelle Bildung** eindeutig verorten (heute uneinig zwischen 6 und 23); **Sammelvorlagen nach Posten**; **Plätze, Toiletten, Schädlinge** (Pflege und Instandsetzung von Plätzen 21, Toiletten und Rattenbekämpfung nach Zweck); **die Haushaltsstelle ist nie das Feld**; **Eigenbetriebe nach Aufgabe**; **Ernennungen und Wahlen einzelner Personen 20** | Kultur (F1 0,78) und Flächen (0,58) verlieren bei Weg 1 genau an diesen Stellen (§ 4.4) | nicht in dieser Runde: Fassung 2 hieße eine neue Stichprobe in einem eigenen Ordner (F4), und zwei Wege erfüllen das Kriterium mit Fassung 1; für Stufe 2 bleiben der eingefrorene Prompt `19-cap-1` (Lehrer) und die Gewichte von 3b. Vorschlag für eine spätere Runde |
| 9.17 | Trägt 3b auf den anderen Perioden (2014–2020, ab 2025)? Er ist auf Silberlabels der Hauptperiode trainiert und nur dort geprüft | die Seite zeigt Politikfelder je Periode | Annahme: ja, gleiche Stadt, gleiche Dokumentarten; die Seite nennt die Prüfung nur für 2020–2025. Eine kleine Stichprobe je Periode (je 100, Weg 1 als Vergleich, rund 2 GPU-Minuten) vor Stufe 3 wäre billig |
| 9.18 | 3b ist eine Destillation von Weg 1 (einig in 270 von 300) und liegt mit 0,704 knapp über der Schwelle, Intervall bis 0,620 | ein neuer Prompt oder ein neues Modell für Weg 1 heißt neues Training von 3b; die Güte ist nicht sicher über 0,70 | hingenommen nach der vorab festgelegten Regel (Punktwert, billigerer Weg); die Seite nennt das Intervall |

## 10. Änderungen durch die Synergie (füllt der Supervisor)

Geschrieben am 2026-11-28 vom Supervisor der Phase „Zeigen“ vor dem Start der Stufe 2, nach Konrads
„Yes, start 19“ (2026-11-28). Die Synergie ([00-synergien-2026-11.md](00-synergien-2026-11.md)) hat für
19 keinen Abschnitt in § 4; was seither feststeht und auf `main` liegt, geht dem Bauplan (§ 6, § 7) vor.

1. **Weg 3b, wie in § 6.** Die Vorhersage läuft außerhalb des Pakets im Venv
   `/media/konrad/xtraspace/venvs/cap-train` mit den Gewichten `training-3b/beste` (SHA-256 `80ca2a82…`,
   vor dem Lauf nachrechnen), **nur unter `flock /media/konrad/xtraspace/georep/gpu-queue/gpu.lock`**,
   höchstens 30 Minuten je gesperrtem Lauf, alle Profile zusammen geschätzt unter 15 Minuten. Vor und
   nach dem Lauf `nvidia-smi` und das Tempo prüfen (läuft torch wirklich auf der GPU); ein Lauf auf der
   CPU wird abgebrochen, nicht abgewartet. torch kommt nie ins Lock des Pakets.
2. **Lizenz (Frage 37, Konrad 2026-11-26: „unter NC-SA zeigen“).** `politikfelder.parquet` und jede
   Tabelle, die die Codes trägt, stehen unter **CC BY-NC-SA 4.0** mit Zitat des CAP (Comparative
   Agendas Project; deutsches Codebuch), getrennt vom Rest der Seite, der CC0 bleibt: das Paket
   `snapshots/<profil>-politikfelder/` mit Lizenz im README, die Downloads mit eigener Lizenzzeile,
   `themen.html` mit dem Vermerk oben und im Fuß. Frage 9.4 ist damit beantwortet.
3. **Bausteine von `main`.** Beitrag `19-politikfelder` am Ende von `CONTRIBUTIONS` (offline, prüft
   das Paket gegen den Korpus und reicht es weiter), Fabrik mit `http` (F7, Punkt 74), Pfade im Modul,
   Settings nach der Anhängeregel (`enabled = false` in `defaults.toml`, an in den Profilen mit Paket).
   Die Eingabe je Dokument (Titel und 1 500 Zeichen Rohtext) kommt aus F1 (Punkt 73) nach Dateiname,
   eine Zeile je Korpus-ID; der Export ist bytegleich zu `schreibe_eingabe()` (Test). Befehl
   `georep policy-areas export <profil>` (englische Befehle, wie `search`). Die Fraktionen kommen aus
   den Antragstellern von 15 (`processed/dokumente_antragsteller.parquet`, Punkt 75), für alle gleich,
   ab 30 Dokumenten.
4. **Profile.** Alle vier Datensätze bekommen eine Vorhersage. Geprüft ist nur die Hauptperiode;
   2014–2020 und ab 2025 nennen das (Frage 46, Annahme gilt, keine eigene Stichprobe in dieser Runde),
   Mönchengladbach heißt „explorativ“ (Frage 9.10).
5. **Stufe 2 und Stufe 3 in einem Bau** (Ressourcen): `themen.html` nach § 7, aber **ohne Karte** je
   Wahlbezirk (nur die Tabelle), damit die Unterseiten der Hauptperiode zusammen unter 1 MB bleiben
   (Plan der Phase § 6; heute rund 640 KB ohne `themen.html`). Abschnitt 4 (Vergleich mit dem Bundestag)
   nur mit abgeleiteten Anteilen und Quelle, unter derselben Lizenz. Downloads `politikfelder` je Dokument
   nur als Parquet (Rückstand 35) und eine kleine Tabelle der Anteile je Periode und Gremiumsart als
   Parquet und CSV, beide CC BY-NC-SA 4.0; Spalten auf `spalten.html` (Punkt 94).
6. **Validierung auf der Seite.** Der Satz aus `validierung/19-politikfelder/guete.json` (zwei
   KI-Kodierer desselben Modells, nicht von Menschen); Makro-F1 von 3b mit Intervall (0,704,
   0,620–0,807) und die zweite Prüfung an menschlich kodierten Bundestagstiteln (0,688) als geprüfte
   Konstanten, die ein Test aus den Dateien der Messung nachrechnet, soweit sie im Repo liegen; sonst mit
   Verweis auf dieses Dokument. Dazu der Satz aus § 5, dass 3b eine Destillation von Weg 1 ist.
7. **Nicht in dieser Runde:** Weg 1 (der Rückweg), das Codebuch Fassung 2 (Frage 9.16), die Klasse 10
   als Maß für H1 von 22 (H1 bleibt vorab festgelegt an `OVA`), Unterthemen.

