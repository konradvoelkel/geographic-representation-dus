# Vorhaben 18: Einbettungen, Ähnlichkeit, semantische Suche

Stand 2026-11-24, Stufe 1 (Messen) abgeschlossen, Stufe 2 (Bauen) gebaut auf `feat/18-einbettungen`
(was vom Bauplan abweicht, steht im Entscheidungspunkt „Einbettungen über Stücke" in
[../decisions.md](../decisions.md)). Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „18 Einbettungen,
Ähnlichkeit, semantische Suche". Messskript: [18-einbettungen-messung.py](18-einbettungen-messung.py).
Suchfragen: [18-einbettungen-anfragen.toml](18-einbettungen-anfragen.toml). Codebücher, Stichproben
und Labels: [../../validierung/18-einbettungen/](../../validierung/18-einbettungen/) (Suche) und
[../../validierung/18-einbettungen-nachbarn/](../../validierung/18-einbettungen-nachbarn/) (ähnliche
Dokumente).

**Urteil (2026-11-24, nach der vorab festgelegten Regel aus § 3.1, Commit `a38e149`, ohne Anpassung
an die Labels): bauen** — `embeddings`, `neighbors` und `georep suche` mit der Einbettung (§ 5.1).
Beide Teile des Kriteriums sind erfüllt, die Rückfallregel greift nicht. Die Labels kommen von zwei
KI-Kodierern und einem Schlicht-Agenten, alle drei dasselbe Modell (`claude-opus-5-5`, Frage 19 an
Konrad: es gilt die Annahme), nicht von Menschen; α ordinal 0,975 (Suche) und 0,943 (Nachbarn).
Schon vor den Labels entschieden: die GPU trägt es, Vektoren gehören nicht ins Repo, Cluster über
Einbettungen werden nicht gebaut (§ 5).

Die drei Zahlen, auf die es ankommt:

1. **Suche**: nDCG@10 über 50 Suchfragen **Einbettung 0,883 (0,842–0,919), Mischung 0,846
   (0,792–0,899), BM25 0,709 (0,622–0,785)**; die Einbettung schlägt BM25 um **+0,175** (95 %
   +0,106 bis +0,255), die Mischung um +0,137, Schwelle 0,05. Der Vorsprung hängt an der Form der
   Frage: bei Stichwörtern im Amtswortlaut +0,032 (Intervall schließt 0 ein; die Mischung +0,046),
   bei umschriebenen +0,181, bei ganzen Fragesätzen +0,350 (§ 4.4).
2. **Ähnliche Dokumente**: Präzision@5 der Einbettung **0,832** (208 von 250, Wilson 0,781–0,873),
   Schwelle 0,70; TF-IDF 0,652 (0,591–0,708) erreicht die Schwelle nicht, der billigere Weg fällt.
   Dieselbe Sache (nicht nur dasselbe Thema) sind 34 % der Vorschläge der Einbettung.
3. **Aufwand**: die Hauptperiode in 693 s Wanduhr (47 407 Stücke, rund 16 ms GPU und 27 ms Wanduhr
   je Dokument ohne Fremdlast), alle vier Datensätze rund 17 GPU-Minuten; ins Repo nur die
   Nachbartabelle (0,88 MiB), „ähnliche Dokumente" im Dialog 29 Bytes je Dokument (§ 3.3, § 3.4).

Alle Zahlen sind am 2026-11-23 gemessen (die Auswertung der Labels am 2026-11-24), an der
Rohtext-Messdatei der Hauptperiode und am Korpus nach
`georep bootstrap && georep run` im Worktree, ollama 0.24.0 auf der RTX 4090. Nachrechnen, mit den
Lastregeln des Supervisors vom selben Tag:

```bash
export POLARS_MAX_THREADS=4 OMP_NUM_THREADS=2
flock /media/konrad/xtraspace/georep/gpu-queue/gpu.lock \
  nice -n 10 uv run python docs/plans/18-einbettungen-messung.py --einbetten   # GPU, fehlende Stücke
nice -n 10 uv run python docs/plans/18-einbettungen-messung.py --hochrechnung  # § 3.3, ohne GPU
nice -n 10 uv run python docs/plans/18-einbettungen-messung.py --pools         # § 3.6, Pools für F4
nice -n 10 uv run python docs/plans/18-einbettungen-messung.py --groessen --cluster   # § 3.4, § 3.5
nice -n 10 uv run python docs/plans/18-einbettungen-messung.py --auswertung    # § 5, nach den Labels
```

Ohne `--einbetten` fragt das Skript ollama nur nach dem Digest und liest die Vektoren aus dem
Modellcache (`cache_root/ml/`, 204 MB für dieses Vorhaben). Laufzeit des Skripts mit `--pools`: 21 s
bei einem Lastmittel von 7, 85 s bei 27; 1,0 GB Spitzenspeicher; mit `--groessen --cluster` 187 s
und 2,0 GB. Rangfolgen und Nachbarn sind über drei Läufe bytegleich, die Pools über zwei (SHA-256
`rangfolgen.parquet` `7d806b9870a3…`, `nachbarn.parquet` `78e206e3c49b…`, `pool_suche.parquet`
`ba5c904f3246…`, `pool_nachbarn.parquet` `568e8085d6b4…`).

## 1. Frage und Nutzen

**Frage.** Findet eine Suche nach Bedeutung, was die Wortsuche nicht findet? Welche Dokumente ähneln
einander? Tragen Cluster über Einbettungen besser als das NMF-Modell? Die Seite hat heute keine
Volltextsuche: ihre Suche kennt nur Namen von Straßen, Orten und Wahlbezirken, und „wer
‚Radverkehr‘ sucht, findet hier nichts" ([../workflow-ratsmitglied.md](../workflow-ratsmitglied.md),
§ 4). Die Messung vergleicht darum nicht mit der heutigen Seite, sondern mit dem, was eine
ordentliche Wortsuche leisten würde: BM25 mit deutschem Stemmer über denselben Text.

**Ratsarbeit.** „Gab es das schon?" ist eine der vier Sichten, die Vorhaben 29 für
Fraktionsgeschäftsstellen bauen soll („Recherche"): ein Antrag zum Zebrastreifen vor der
Grundschule, eine Anfrage zur Kältehilfe, die Vorlage zum Ganztag. Eine Wortsuche findet nur, wer
das Wort der Verwaltung trifft („Radfahrstreifen", „Querungshilfe", „Notschlafstelle"). „Ähnliche Dokumente" im Dokumentdialog der Seite wäre der zweite Weg: von einem gefundenen
Dokument zu den verwandten, ohne ein Suchwort zu kennen.

**Literatur** (mit * aus dem Gedächtnis, vor einem Zitat nachzuschlagen). BM25 ist in Vergleichen
über viele Sammlungen eine schwer zu schlagende Grundlinie für Einbettungsmodelle ohne Training auf
der Zielsammlung, und eine Mischung aus beiden ist meist besser als jede allein (Thakur u. a. 2021,
BEIR*). Reciprocal Rank Fusion ist die Mischung ohne gelernte Gewichte (Cormack, Clarke, Büttcher
2009*). Das Modell ist `nomic-embed-text-v2-moe`, ein mehrsprachiges Einbettungsmodell mit
Mixture-of-Experts, 475 M Parameter, Fenster 512 Token, Präfixe `search_query:` und
`search_document:` (Nussbaum, Duderstadt 2025*). Maßstab der Prüfung bleibt Grimmer und Stewart
(2013*): eine Suche ohne geurteilte Treffer ist eine Behauptung.

**Was sich seit Oktober geändert hat.** Einbettungen waren im Oktober verworfen
([../themenmodell-2026-10.md](../themenmodell-2026-10.md), § 5; [../decisions.md](../decisions.md),
Punkt 45c): ein bis drei CPU-Stunden je Durchgang, rund 800 MB Abhängigkeiten (torch), keine
nachlesbaren Wörter, und für das Themenmodell reichten die billigen Wege. Zwei der drei Gründe sind
weg: F5 (Punkt 72) spricht ollama über HTTP ohne neue Abhängigkeit, und die GPU rechnet die
Hauptperiode in Minuten (§ 3.3). Der dritte bleibt und gilt hier wie dort: ein Treffer der
Einbettung hat kein Wort, das ihn erklärt. Die Frage von damals („wenn, dann für die Suche") ist
genau die dieses Vorhabens.

## 2. Datenlage

| Datei | Inhalt | Herkunft, Lizenz |
|---|---|---|
| `data/duesseldorf/interim/papers.parquet` | Korpus der Hauptperiode, 19 108 Dokumente: `id`, `name` (OParl-Titel), `reference`, `paper_type`, `date`, `file_name`, `text` (kleingeschrieben, nur für das Themenmodell und die Cluster) | Paket `reference/` und `snapshots/duesseldorf-texte/` (Punkt 68), `georep bootstrap && georep run` |
| `messdaten/rohtext/duesseldorf.parquet` | Rohtext pypdf 7.1.0 je PDF: `name` (Dateiname), `text` (Seiten mit `\f`, Groß- und Kleinschreibung, Kopf erhalten), `pages`, `chars`; 19 092 Dateien, 55,4 Mio. Zeichen | Messdatei aus Phase 0 (wie F1) |
| `messdaten/rohtext/{2014-2020,2025,moenchengladbach}.parquet` | dieselben Spalten für die übrigen Datensätze; nur für die Hochrechnung (§ 3.3) | ebenda |
| `processed/papers_gremien.parquet`, `themen_dokumente.parquet`, `themen.parquet` | Gremium je Dokument (Drucksachennummer), Themen der Seite; nur für die Cluster (§ 3.5) | `georep run` |
| `site/data/dokumente.json` | die 10 789 Dokumente des Dialogs der Seite; nur für die Größe von „ähnliche Dokumente" (§ 3.4) | `georep run` |
| `cache_root/ml/nomic-embed-text-v2-moe_latest.sqlite` | Modellcache von F5: je Stück und Frage ein Vektor float32, Schlüssel Digest, Prompt-Version samt Fensterschlüssel (`18-stuecke-1+1868f0241d5a`, `18-anfrage-1+1868f0241d5a`) und SHA-256 der Eingabe | `--einbetten`, lokal |

**Modell**: `nomic-embed-text-v2-moe:latest`, Digest `ff9c2f10ef5e3722…`, F16, 958 MB, ollama 0.24.0.
`ollama show --license` nennt keine Lizenz; die Modellseite nennt nach Erinnerung Apache 2.0
(nicht geprüft, Frage 9.6). Ins Repo kämen ohnehin nur Ausgaben (IDs, gegebenenfalls Vektoren), nie
das Modell.

**Einheit.** Die Messung rechnet je PDF-Datei (§ 3.1). Von den 19 108 Korpus-IDs haben 19 032 einen
nicht leeren Rohtext, jede in ihrer eigenen Datei (die Dateien, die sich mehrere IDs teilen, haben
keinen Rohtext); 76 IDs fehlen darum in jeder Rangfolge (kein PDF, ein leeres oder ein Scan ohne
Text). Stufe 2 gibt trotzdem jeder ID einer Datei dieselbe Zeile (Synergie, § 1, „Dokument je
PDF-Datei"), damit der Join auf `id` nichts verliert.

Ins Repo kommen aus diesem Vorhaben nur Suchfragen, Codebücher, Stichproben mit IDs und Messskript;
Rangfolgen, Vektoren und Kodieraufgaben bleiben lokal.

## 3. Messung

### 3.1 Vorab festgelegt (2026-11-23, 22:37, bevor ein Verfahren lief)

Vorher gemessen und für die Festlegung benutzt wurde nur, was keine Suchfrage berührt: die Länge der
Rohtexte (Messdatei, 19 092 Dateien, 55,4 Mio. Zeichen, Median 1 903) und das Verhältnis von Zeichen zu
Token des Einbettungsmodells an 288 Anfängen von 120 Rohtexten (Einzelaufrufe, `prompt_eval_count`:
im Mittel 4,3 Zeichen je Token, 1-%-Quantil 3,8, Minimum 3,47). Gelesen wurden 80 zufällige Titel des
Korpus (Seed 7) als Eindruck der Themen. Keine Suchfrage ist an einem Treffer geprüft.

**Einheit der Suche.** Je PDF-Datei der Hauptperiode eine Einheit: die Dokumente des Korpus
(`interim/papers.parquet`, 19 108) über `file_name` verbunden mit der Rohtext-Messdatei
(`messdaten/rohtext/duesseldorf.parquet`, Spalte `name`), nur Dateien, deren Rohtext ohne Leerraum
nicht leer ist. Teilen sich mehrere Korpus-IDs eine Datei, steht die Einheit unter der kleinsten ID
(Zeichenfolge); sonst stünde derselbe Text zweimal in einer Trefferliste. Titel = OParl `name` dieser
ID, Leerraum zusammengezogen, höchstens 200 Zeichen. Text einer Einheit T(d) = Titel, Leerzeile,
Rohtext (Seitenwechsel `\f` als Zeilenwechsel). Beide Verfahren sehen denselben Text.

**Verfahren 1, BM25** (Fassung `18-bm25-1`, die Wortsuche als Vergleich): Token `\w+` aus T(d) in
Kleinschreibung, je Token der Snowball-Stemmer für Deutsch (Algorithmus nach snowballstem.org, im
Messskript ohne neue Abhängigkeit umgesetzt: ß → ss, R1 und R2, Schritte 1 bis 3, zuletzt Umlaute
ohne Punkte), keine Stoppwortliste. Okapi BM25 mit k1 = 1,2, b = 0,75, IDF = ln(1 + (N − n + 0,5) /
(n + 0,5)) wie Lucene, mittlere Länge über alle Einheiten. Die Suchfrage geht durch dieselbe
Zerlegung; jedes verschiedene Token zählt einmal. Einheiten ohne ein Token der Frage stehen nicht in
der Rangfolge (BM25 darf weniger als zehn liefern).

**Verfahren 2, Einbettung** (Fassung `18-stuecke-1`, `18-anfrage-1`): `nomic-embed-text-v2-moe:latest`
(Digest `ff9c2f10ef5e…`, 768 Dimensionen, Fenster 512 Token, `truncate` an) über die Naht von F5
(`georep.ml`: `EmbeddingUse`, `embed_texts`, Modellcache), Stapel zu 32. Zerteilung: die Zeilen des
Rohtexts (ohne Zeilen aus Leerraum) werden der Reihe nach zu Stücken gepackt, deren Rumpf höchstens
B = 1 600 − (Länge des Titels) − 2 Zeichen hat; eine Zeile über B wird an der letzten Leerstelle vor B
geteilt (ohne Leerstelle hart). Das nächste Stück beginnt mit den letzten Zeilen des vorigen, die
zusammen höchstens 200 Zeichen haben (Überlappung), und nimmt mindestens eine neue Zeile auf. Jedes
Stück ist `search_document: ` + Titel + Leerzeile + Rumpf; mit 1 600 Zeichen bleibt es auch beim
kleinsten gemessenen Verhältnis (3,47 Zeichen je Token: 461 Token) unter 512. Die Suchfrage ist
`search_query: ` + Frage. Vektoren auf Länge 1 normiert, Ähnlichkeit ist das Skalarprodukt; die
Punktzahl einer Einheit ist das Maximum über ihre Stücke.

**Verfahren 3, Mischung** (Fassung `18-rrf-1`, feste Gewichtung): Reciprocal Rank Fusion (Cormack,
Clarke, Büttcher 2009) über die ersten 100 von BM25 und Einbettung, beide mit Gewicht 1:
s(d) = Σ 1 / (60 + Rang). Eine Einheit außerhalb der ersten 100 einer Liste bekommt von ihr nichts.
Gleichstände in allen drei Verfahren nach ID aufsteigend.

**Suchfragen.** Die 50 Fragen in [18-einbettungen-anfragen.toml](18-einbettungen-anfragen.toml):
18 Stichwörter im Wortlaut der Verwaltung (`wort`), 18 umschriebene (`umschrieben`: Umgangssprache,
Synonym, Oberbegriff wie „Radverkehr"), 14 ganze Fragesätze (`frage`); 34 Themen, 9 Orte, 7 Vorhaben.
Jede trägt einen Satz `bedarf`, den nur die Kodierer sehen.

**Relevanzurteile (F4).** Je Frage die ersten 10 jedes der drei Verfahren, vereinigt; jedes Paar
(Frage, Einheit) ist eine Einheit `query_document` im Codebuch `validierung/18-einbettungen/`. Die
Kodierer sehen Frage, Bedarf, Titel und die ersten 6 000 Zeichen des Rohtexts, **nicht**, welches
Verfahren das Dokument fand oder auf welchem Rang. Relevanz ordinal: `0` nicht relevant, `1`
teilweise (berührt das Gesuchte als Nebenpunkt, in einer Liste, oder nur das Oberthema), `2` relevant
(handelt zu einem wesentlichen Teil vom Gesuchten). Zwei Kodier-Agenten, ein Schlicht-Agent für die
Uneinigkeiten, Endlabel nach F4.

**Maß der Suche.** nDCG@10 je Frage mit `georep.validation.measures.ndcg_at_k` (linearer Gewinn 0,
1, 2, Ideal über alle geurteilten Einheiten der Frage); weil jede der drei Listen bis Rang 10
geurteilt ist, ist das für sie das gewöhnliche nDCG@10 gegen den Pool. Gemittelt über die Fragen mit
mindestens einer Einheit der Relevanz ≥ 1; eine Frage ohne fällt für alle Verfahren heraus, ihre
Zahl wird genannt.

**Ähnliche Dokumente.** 50 Anker aus den Einheiten mit mindestens 300 Zeichen Rohtext, gezogen wie
in F4 ohne Zufallsgenerator (Rang SHA-256 über Seed 20261123 und ID, `georep.validation.sample.rank`),
geschichtet nach Dokumentart (die acht häufigsten `paper_type`, der Rest als „sonst"), proportional
(`georep.validation.sample.allocate`). Dokumentvektor (Fassung `18-dokvektor-1`) = Mittel der
normierten Vektoren der ersten drei Stücke, normiert. Nachbarn = die fünf Einheiten mit dem größten
Skalarprodukt, ohne den Anker. Zum Vergleich, nicht im Kriterium: TF-IDF (Fassung `18-tfidf-1`,
scikit-learn `TfidfVectorizer` auf T(d), Kleinschreibung, Token `(?u)\b\w\w+\b`, `min_df` 2,
`max_df` 0,5, `sublinear_tf`, L2), Kosinus, dieselben fünf und dieselben Ausschlüsse. Beide
Nachbarlisten vereinigt sind die Einheiten `document_pair` (A = Anker, B = Nachbar) im Codebuch
`validierung/18-einbettungen-nachbarn/`; die Kodierer sehen beide Titel und je die ersten 3 000
Zeichen, nicht das Verfahren. Label ordinal: `verschieden` < `gleiches_thema` (dasselbe konkrete
Sachthema, unter dem ein Ratsmitglied suchen würde, aber eine andere Sache) < `gleiche_sache`
(derselbe Vorgang, dasselbe Vorhaben oder derselbe Gegenstand am selben Ort).

**Kriterium** (aus dem Briefing, unverändert):

1. **Suche**: max(nDCG@10 Einbettung, nDCG@10 Mischung) − nDCG@10 BM25 ≥ **0,05**, je als Mittel über
   die Fragen.
2. **Nachbarn**: Präzision@5 der Einbettung ≥ **0,70**, das heißt unter den 250 Paaren (Anker,
   Nachbar der Einbettung) der Anteil mit `gleiches_thema` oder `gleiche_sache`.

Unsicherheit, berichtet und nicht Teil des Kriteriums: für jede Differenz ein gepaarter Bootstrap
über die Fragen (2 000 Ziehungen, `numpy.random.default_rng(20261123)`, Perzentil-Intervall 95 %)
und ein zweiseitiger Vorzeichen-Permutationstest (10 000 Permutationen, gleicher Seed); für die
Präzision@5 Wilson über die 250 Paare und ein Bootstrap über die Anker (2 000 Ziehungen). Zwei
Vergleiche (Einbettung, Mischung) gegen BM25: die Seite nennt beide.

**Urteil und Rückfallregel.**

- Beide Teile erfüllt: **bauen**: `embeddings` (Stücke und Dokumentvektoren), `neighbors`
  (`processed/aehnliche_dokumente.parquet`) und `georep suche` mit dem Verfahren, das im Mittel
  höher liegt (Einbettung oder Mischung).
- Nur die Suche erfüllt: `embeddings` und `georep suche` lokal; keine ähnlichen Dokumente im Dialog.
- Nur die Nachbarn erfüllt: `embeddings` und `neighbors`; `georep suche` nicht mit Einbettung.
- Keiner erfüllt: **verwerfen**, mit einer Zeile in `decisions.md` und diesem Dokument als Befund.
- Der billigere Weg bei den Nachbarn: erreicht TF-IDF selbst 0,70 **und** liegt höchstens 0,05
  unter der Einbettung, empfiehlt das Dokument die TF-IDF-Nachbarn für den Dialog (keine GPU, kein
  Vektorpaket, erklärbar), und die Einbettung trägt nur die Suche, wenn Teil 1 erfüllt ist.
- Liegt Krippendorffs α (ordinal) zwischen den Kodierern unter 0,8, gilt das Urteil gegen das
  Kriterium trotzdem; Stufe 3 darf dann nichts zeigen (Plan, § 2.6), und das Codebuch geht in eine
  neue Runde.

**Explorativ, nicht im Kriterium** (an denselben Labels; ein nicht geurteiltes Dokument zählt nicht,
condensed list, darum mit judged@10): BM25 ohne Stemmer; Einbettung nur mit dem ersten Stück je
Einheit; Einbettung mit den ersten 256 Komponenten (Matryoshka), neu normiert; Mischung als konvexe
Kombination 0,5 / 0,5 der auf [0, 1] skalierten Punktzahlen der ersten 100; alle Zahlen auch je
`form` und `art`; bei den Nachbarn die strenge Präzision (nur `gleiche_sache`) und der Anteil der
Paare im selben Vorgang nach Vorhaben 14, wo er sich ohne Kodierung bestimmen lässt.

**Cluster (Nebensache, explorativ)**: k-Means mit k = 20 über die Dokumentvektoren, Seeds 0 bis 4,
gegen die freie NMF des Themenmodells (k = 20, dieselben Seeds): Stabilität als mittlerer
paarweiser adjustierter Rand-Index, Nähe zum Ausschuss als NMI gegen die Zuordnung aus
`papers_ausschuss.parquet`, Kohärenz als NPMI der zehn Topwörter (`coherence` aus
`docs/themenmodell-2026-10-messung.py`, Topwörter eines Clusters nach c-TF-IDF).

**Laufzeit**: je Stück und je Einheit aus der Rechenzeit des Servers (`total_duration` ohne
`load_duration`) und der Wanduhr je Stapel, mit `uptime` daneben; Hochrechnung je Periode aus den
Zeichen ihrer Rohtexte.

### 3.2 Zerteilung (gemessen 2026-11-23)

`18-stuecke-1` nach § 3.1 über die 19 032 Einheiten: **47 407 Stücke**, davon 47 312 verschiedene
Texte (95 Stücke wiederholen sich wörtlich samt Titel, etwa Formulare, und werden einmal gerechnet).
Je Einheit im Mittel 2,49 Stücke, Median 2, 90-%-Quantil 4, 99-%-Quantil 16, höchstens 247; keine
Einheit ohne Stück. Ein Stück hat samt Präfix und Titel im Mittel 1 337
Zeichen, höchstens 1 617; der Titel im Mittel 91 Zeichen. Gezählt hat der Server im Mittel **316
Token je Stück** (14,9 Mio. Token für 47 312 Stücke); beim kleinsten an 288 Textanfängen gemessenen
Verhältnis (3,47 Zeichen je Token) hätte das längste Stück 466 Token, also stößt keines an die 512
des Fensters. Nach Abschnitten aus Vorhaben 11 zu zerteilen, war nicht nötig: die Fenster brauchen
keine Abschnittsgrenzen, und ein Abschnitt über 512 Token müsste ohnehin wieder geteilt werden.

### 3.3 Laufzeit und Hochrechnung

Gerechnet am 2026-11-23 von 22:57 bis 23:09 unter der GPU-Sperre, in 25 Blöcken (eine Probe zu 64
Stücken, 23 zu 2 048, ein Rest), Stapel zu 32, ein Lauf: **693 s Wanduhr für alle 47 312 Stücke**
und die 50 Fragen. Das Lastmittel (eine Minute) lag zwischen 3,9 und 32,5, die Fremdlast kam und
ging; der Durchsatz hängt an der CPU, nicht an der GPU (sie war zu 2 bis 15 % ausgelastet, der
Server lief zeitweise mit einem Kern bei 100 %).

| | GPU (Rechenzeit des Servers) | Wanduhr |
|---|---|---|
| je Stück, ohne Fremdlast (11 Blöcke, Lastmittel vor und nach unter 8) | 6,3 bis 6,8 ms, Median 6,6 | 10,2 bis 11,1 ms, Median 10,9 |
| je Stück, unter Fremdlast (Last bis 32) | bis 21,1 ms | bis 39,7 ms |
| je Stück, Mittel aller Blöcke | 8,5 ms | 14,5 ms |
| je Dokument (2,49 Stücke), ohne Fremdlast | rund 16 ms | rund 27 ms |
| je Suchfrage (50 in einem Aufruf, 698 Token) | 12 ms | – |
| Laden des Modells | 6,9 s beim ersten Aufruf | |

**Hochrechnung je Periode** (`--hochrechnung`): Stücke aus den Rohtexten mit einem Platzhaltertitel
der mittleren Länge, Token und Zeit aus dem Mittel aller Blöcke der Hauptperiode (also mit Fremdlast
gerechnet, eher zu hoch):

| Datensatz | Dateien | Zeichen | Stücke | Token | GPU | Wanduhr | float16 roh |
|---|---|---|---|---|---|---|---|
| Hauptperiode 2020–2025 | 19 032 | 55,4 Mio. | 47 359 | 15,0 Mio. | 6,7 min | 11,4 min | 69 MiB |
| Wahlperiode 2014–2020 | 21 714 | 73,4 Mio. | 61 182 | 19,3 Mio. | 8,7 min | 14,8 min | 90 MiB |
| laufende Periode ab 2025 | 4 075 | 10,9 Mio. | 9 560 | 3,0 Mio. | 1,4 min | 2,3 min | 14 MiB |
| Mönchengladbach | 650 | 3,6 Mio. | 2 943 | 0,9 Mio. | 0,4 min | 0,7 min | 4 MiB |
| zusammen | 45 471 | 143,3 Mio. | 121 044 | 38,2 Mio. | **17 min** | **29 min** | 177 MiB |

Die Hochrechnung der Hauptperiode (47 359) liegt 48 Stücke unter der echten Zahl (47 407), weil der
Platzhaltertitel die Längen nicht trifft. **Alle vier Datensätze passen in einen gesperrten Block
von rund 30 Minuten**; ein Auftrag für die GPU-Warteschlange ist nicht nötig. Zum Vergleich die
Kostenrechnung vom Oktober (Punkt 45c): ein bis drei CPU-Stunden je Durchgang und 800 MB
Abhängigkeiten; jetzt 12 Minuten und keine Abhängigkeit.

**Ein Befund nebenbei** (Frage 9.5): Um 22:42 scheiterte beim Laden des Modells die
CUDA-Initialisierung (`ggml_cuda_init: failed to initialize CUDA: initialization error` im Log des
Servers), ollama rechnete still auf der CPU weiter (370 Vektoren in rund
225 s, 650 % CPU), und `ollama ps` zeigte trotzdem „100% GPU". Der Lauf ist abgebrochen, die 370 auf der CPU gerechneten Vektoren dieses
Vorhabens sind aus dem Cache gelöscht und um 22:57 auf der GPU neu gerechnet (das Log zeigt
„offloaded 13/13 layers to GPU"). Seitdem prüft das Skript vor jedem Lauf das Tempo an 64 Stücken
und bricht über 50 ms je Stück ab.

### 3.4 Größen und Anzeige

Gemessen mit `--groessen` an der Hauptperiode, Parquet mit zstd 19:

| Ausgabe | Zeilen | Größe |
|---|---|---|
| Dokumentvektoren, float16, 768 Komponenten | 19 032 | 25,7 MiB |
| Dokumentvektoren, float16, erste 256 Komponenten (Matrjoschka) | 19 032 | 8,6 MiB |
| Dokumentvektoren, int8, 768 Komponenten | 19 032 | 7,5 MiB |
| Stückvektoren, float16, 768 Komponenten (was die Suche braucht) | 47 407 | 64,0 MiB |
| `aehnliche_dokumente`: zehn Nachbarn je Einheit (`id`, `rang`, `nachbar`, `aehnlichkeit`) | 190 320 | **0,88 MiB** |
| Modellcache, float32, alle Stücke und Fragen dieses Vorhabens | 47 362 | 204 MB |

Die zehn Nachbarn aller 19 032 Einheiten rechnen in 7,8 s (Blöcke zu 2 048, float32, CPU).

**Paketfrage** (Frage 18/26 an Konrad; alle Pakete liegen bei rund 166 von 180 MiB): Vektoren passen
nicht, die Nachbartabelle passt. Die Seite braucht nur die Nachbarn (IDs); die Vektoren braucht nur
`georep suche`, und das läuft dort, wo auch der Modellcache liegt. **Annahme: nur die Nachbartabelle
ins Repo** (Frage 9.1). Für alle vier Datensätze wären es rund 2,1 MiB Nachbarn (hochgerechnet über
die Einheiten), gegen 177 MiB Stückvektoren roh.

**Ähnliche Dokumente im Dokumentdialog** (der Haken von Vorhaben 14, Synergie § 1): `dokumente.json`
trägt 10 789 Dokumente, 10 788 davon sind Einheiten mit Rohtext. Fünf Nachbarn je Dokument als
Indizes: **307 KB, gzip 128 KB, im Mittel 29 Bytes je Dokument**. 3 726 der Nachbarn stehen nicht in
`dokumente.json` (sie haben keinen Treffer eines Orts); ihre Zeilen (Datei, Datum, Drucksache,
Titel) kosten 513 KB, gzip 134 KB. Zusammen eine nachgeladene Datei von 820 KB (gzip 262 KB),
einmal beim ersten Öffnen eines Dialogs; `index.html` wächst nur um den Haken. Wer nur Nachbarn aus
`dokumente.json` zeigt, spart die 513 KB, verliert aber jeden Vorschlag ohne Ortstreffer.

**Eine freie semantische Suche auf der statischen Seite** (beziffert, nicht gebaut):

- **Index**: die Suche sucht über Stücke (§ 3.1); das sind 64 MiB float16 oder, geschätzt, rund
  12 MB mit 256 Komponenten als int8 (47 407 × 256 Bytes; ob die Güte hält, misst nur die
  explorative Variante `einbettung_256`, in float32). Ein Index nur über Dokumentvektoren wäre 7,5
  bis 26 MiB, ist aber ein anderes Verfahren als das gemessene.
- **Modell im Browser**: dieselbe Frage muss mit demselben Modell eingebettet werden.
  `nomic-embed-text-v2-moe` hat 475 M Parameter, 958 MB als F16; als int8 wären es geschätzt rund
  0,5 GB (Parameter × 1 Byte), dazu eine WASM- oder WebGPU-Laufzeit. Das Budget der Seite ist 1 MB,
  eine Unterseite 500 KB, ohne Fremdressourcen. Ein kleineres Modell (um 120 M Parameter, int8 rund
  120 MB) bräuchte eigene Vektoren und eine eigene Messung.
- **Server**: die Frage einzubetten kostet auf der GPU 12 ms, auf der CPU (gemessen beim
  CUDA-Ausfall: rund 0,6 s für ein Stück von 316 Token) für eine Frage von 15 Token deutlich weniger als
  eine Sekunde; der Index passt in den Speicher (64 MiB). Aber die Seite ist statisch (GitHub
  Pages); ein Server hieße Betrieb, Kosten und Suchanfragen von Lesern, die den Browser verlassen.
- **Für die Mischung** käme ein BM25-Index dazu: 3,47 Mio. Einträge (Dokument, Wortstamm) über
  119 681 Stämme, grob 15,6 MB roh.

Keines davon passt in eine Stufe 3 (Frage 9.3).

### 3.5 Cluster (Nebensache, explorativ)

`--cluster`, an den Einheiten mit Korpustext, k = 20, Seeds 0 bis 4; Topwörter für alle
Verfahren über dasselbe TF-IDF wie das Themenmodell der Seite (`topics.vectorize` mit den
Stoppwörtern aus dem Profil), NPMI mit `coherence` aus
[../themenmodell-2026-10-messung.py](../themenmodell-2026-10-messung.py); Nähe zum Ausschuss als NMI
gegen das Gremium der Drucksache, nur für die Dokumente der Ausschüsse.

| Verfahren | NPMI (Topwörter) | UMass | ARI über Seeds | NMI zum Ausschuss | größter / kleinster Cluster |
|---|---|---|---|---|---|
| k-Means über Dokumentvektoren | +0,291 | −1,311 | 0,689 | 0,451 | 2 056 / 328 |
| NMF frei (wie `topics.seed = "none"`) | **+0,405** | −1,237 | **0,899** | 0,311 | 3 474 / 156 |
| k-Means über TF-IDF (zwei Seeds) | +0,355 | −1,117 | 0,705 | 0,235 | 2 594 / 96 |
| NMF gesät, das Modell der Seite (dominantes Thema) | +0,333 | −1,579 | – | **0,737** | – |

**Cluster über Einbettungen tragen nicht besser als NMF.** Ihre Topwörter sind am wenigsten
kohärent, sie sind über Seeds weniger stabil als die freie NMF, und dem Ausschuss kommen sie zwar
näher als die freie NMF, aber weit weniger nah als das gesäte Modell der Seite. Der Grund steht in
den Topwörtern: die Einbettung sortiert nach **Form** — „antrag, gez, begründung, bezirksvertretung,
gebeten" (2 056 Dokumente), „beschlusskontrolle, sitzungstermine, kenntnisnahme", „bauvorhaben,
erteilung, befreiungen", „haushaltsantrag, produkt, zeile" — und nur bei einem Teil nach Sache
(Schulen, Kultur, Bäume, Wohnen, Rheinbahn). Das passt zum Befund von Oktober (die Fehler des
Themenmodells sind Mehrdeutigkeiten der Sache, keine Darstellungsfehler) und ändert nichts an
Punkt 45: **nicht bauen**.

### 3.6 Rangfolgen vor der Kodierung

Ohne Labels lässt sich nur sagen, wie verschieden die Verfahren sind (`--pools`):

| Form | Fragen | Jaccard der ersten 10, BM25 und Einbettung | BM25 mit weniger als 10 Treffern | Pool je Frage |
|---|---|---|---|---|
| wort | 18 | 0,272 | 2 („Waffenverbotszone" 4, „Stadttauben" 6) | 16,1 |
| umschrieben | 18 | 0,148 | 1 („Hundewiesen" 8) | 20,3 |
| frage | 14 | 0,196 | 0 | 18,6 |
| alle | 50 | 0,206 | 3 | 18,3 |

BM25 findet bei Fragesätzen fast jedes Dokument (jedes Wort zählt, auch „die" und „was"; IDF macht
sie nur leicht), aber die ersten zehn bestimmen die seltenen Wörter. Der Stemmer verschmilzt
einzelne Wörter, die nichts gemein haben („sicherer" und „Sicherheit" werden zu „sich", wie das
Pronomen): ein bekannter Mangel des Snowball-Stemmers, der hier zwei Fragen trifft (a20, a45).
Im Pool stehen 488 Paare aus den ersten zehn von BM25 und 500 aus denen der Einbettung, 149 davon
in beiden; die Mischung bringt 77 eigene dazu (meist Dokumente, die in beiden Listen knapp hinter Rang
10 stehen).

Bei den Nachbarn teilen Einbettung und TF-IDF 117 der 250 Paare (47 %); vereinigt sind es 383. Ein
Zeichen für denselben Vorgang ohne Kodierung — dieselbe Drucksachennummer, oder der eine Text nennt
die Nummer des anderen — tragen 28 der 250 Paare der Einbettung und 27 der 250 von TF-IDF (11 %);
die Verfahren unterscheiden sich darin nicht.

## 4. Validierung

### 4.1 Codebücher und Kodierer

Zwei Codebücher im Format von F4, je mit einer ordinalen Frage, geschrieben nach § 3.1 und vor dem
Ziehen der Pools; ihre Fassung ist `2026-11-23.1`:

- [../../validierung/18-einbettungen/codebuch.toml](../../validierung/18-einbettungen/codebuch.toml),
  Einheit `query_document`, Frage `relevanz` mit `0` (nicht relevant), `1` (teilweise), `2`
  (relevant), je mit Definition und Beispiel; der Bedarf der Frage als Kontext (`bedarf`, vom
  Mess-Agenten geschrieben, nie von einem Verfahren gesehen); Titel und die ersten 6 000 Zeichen
  Rohtext; nDCG@10 über `relevanz` (`[score]`).
- [../../validierung/18-einbettungen-nachbarn/codebuch.toml](../../validierung/18-einbettungen-nachbarn/codebuch.toml),
  Einheit `document_pair` (A Anker, B Nachbar), Frage `aehnlich` mit `verschieden`,
  `gleiches_thema`, `gleiche_sache`; `positive` = die beiden oberen (Präzision@5); Titel und je die
  ersten 3 000 Zeichen.

Die Stichproben sind die ganzen Pools (`sample.size` gleich der Zahl der Einheiten, ungeschichtet,
ohne `require_text`, weil die Verfahren den Rohtext lesen). Die Kodierer sehen weder Verfahren noch
Rang noch Punktzahl; die Folge der Einheiten ist je Kodierer eine andere (F4). Kodiert wird nach
[../validierung.md](../validierung.md), § 3 und § 4: zwei frische Kodier-Agenten, ein Schlicht-Agent
für die Uneinigkeiten. Maße: Krippendorffs α ordinal zwischen den Kodierern (Stufe 3 verlangt
≥ 0,8), dann die Maße des Kriteriums an den Endlabels (§ 3.1).

**Grenzen des Instruments.** Der Ausschnitt ist der Anfang des Dokuments (6 000 bzw. 3 000
Zeichen); 92,3 % der Einheiten passen ganz hinein, 74,2 % in 3 000. Ein Dokument, das ein Verfahren
über eine Stelle hinter dem Ausschnitt fand, kann darum als `0` gelten, obwohl es dort vom
Gesuchten handelt; beide Verfahren lesen das ganze Dokument, es trifft also beide, und vor allem
lange Dokumente. Die
Suchfragen und der Bedarf sind vom Mess-Agenten geschrieben, die Kodierer sind Modelle derselben
Familie: eine gemeinsame Vorliebe für „semantische" Treffer ist nicht ausgeschlossen (Frage 9.9).

### 4.2 Stichproben und Kodieraufgaben (2026-11-23, nach § 3.1)

Gezogen und geschrieben nach dem Festlegungscommit `a38e149`, mit

```bash
nice -n 10 uv run python docs/plans/18-einbettungen-messung.py --pools
uv run georep validate sample 18-einbettungen
uv run georep validate sample 18-einbettungen-nachbarn
for p in 18-einbettungen 18-einbettungen-nachbarn; do for c in A B; do
  uv run georep validate tasks $p --coder $c --texts /media/konrad/xtraspace/georep/messdaten/rohtext/duesseldorf.parquet
done; done
```

(`validation.coding_root` steht in der `settings.local.toml` des Worktrees auf
`/media/konrad/xtraspace/georep/messdaten/kodierung`.)

| Codebuch | Einheiten | Grundgesamtheit (SHA-256) | Stichprobe im Repo | Auftrag je Kodierer (lokal) |
|---|---|---|---|---|
| `18-einbettungen` | **916** Paare (Suchfrage, Dokument) aus 50 Fragen, 10 bis 27 je Frage (Median 18) | `data/duesseldorf/messung18/pool_suche.parquet` (`ba5c904f3246…`) | `stichprobe.csv` (`id`, `anfrage`, `dokument`, `bedarf`; `15491717…`), `stichprobe.json` | `kodierung/18-einbettungen/{A,B}/auftrag.jsonl`, 5,6 MB, 2,7 Mio. Zeichen Ausschnitt |
| `18-einbettungen-nachbarn` | **383** Paare (Anker, Nachbar) aus 50 Ankern, 5 bis 10 je Anker | `data/duesseldorf/messung18/pool_nachbarn.parquet` (`568e8085d6b4…`) | `stichprobe.csv` (`id`, `id_a`, `id_b`; `17ce222b…`), `stichprobe.json` | `kodierung/18-einbettungen-nachbarn/{A,B}/auftrag.jsonl`, 2,4 MB, 1,4 Mio. Zeichen Ausschnitt |

Die Aufträge tragen nichts, was ein Verfahren nennt: kein Verfahren, kein Rang, keine Punktzahl,
keine Ähnlichkeit (geprüft mit `grep` über beide Aufträge; die Wörter „Einbettung" und „Mischung"
stehen nur im Feld `vorhaben` und in sechs Ratstexten). A und B sehen dieselben Einheiten in
verschiedener Folge. 92,3 % der Einheiten passen ganz in 6 000 Zeichen, 74,2 % in 3 000.
Rangfolgen und Nachbarlisten liegen nur unter `messdaten/18-einbettungen/`, nicht bei den
Kodierern.

**Für den Supervisor**: je Kodierer fünf Läufe zu höchstens 200 Zeilen für die Suche (916) und zwei
für die Nachbarn (383), nach [../validierung.md](../validierung.md), § 3 und § 4.1; danach `georep
validate merge` je Codebuch, Schlichtung, zweites `merge`, und `--auswertung` (§ 4.3).

### 4.3 Auswertung (vorbereitet vor der Kodierung)

`--auswertung` liest `labels.csv` beider Ordner und rechnet nach § 3.1: nDCG@10 je Frage und
Verfahren (`georep.validation.measures.ndcg_at_k`), das Mittel über die Fragen mit mindestens einem
relevanten Dokument, die Differenzen zu BM25 mit Bootstrap-Intervall und Permutationstest, das
Kriterium der Suche, Präzision@5 je Verfahren mit Wilson-Intervall und Bootstrap über die Anker, das
Kriterium der Nachbarn und das Urteil samt Rückfallregel; dazu explorativ die vier Varianten mit
judged@10, die Präzision streng (nur `gleiche_sache`) und alle Zahlen je `form` und `art`. Die
Werte je Frage gehen nach `messdaten/18-einbettungen/ndcg_je_anfrage.csv`.

Geprüft am 2026-11-23 mit erfundenen Labels in beide Richtungen
(`V18_SUCHE`/`V18_NACHBARN` zeigen auf einen Ordner mit Kopie der Stichprobe und erfundener
`labels.csv`): (a) relevant sind die ersten fünf der Einbettung, alle Nachbarn der Einbettung sind
`gleiches_thema` — nDCG@10 Einbettung 1,000, BM25 0,362, Mischung 0,698, Präzision@5 1,000 und
0,468, „URTEIL: bauen"; (b) relevant sind die ersten fünf von BM25, alle Nachbarn `verschieden` —
BM25 1,000, Einbettung 0,338, „URTEIL: verwerfen". Die Intervalle und der Permutationstest liefen
in beiden Fällen durch.

Die Güte nach F4 (`georep validate score 18-einbettungen --pred <ausgabe.parquet>`) geht ebenso: je
Verfahren eine Datei mit `query`, `id`, `score` aus `rangfolgen.parquet`; sie rechnet dasselbe
nDCG@10 und schreibt es nach `guete.json`, das Stufe 3 liest.

### 4.4 Ergebnis der Kodierung (2026-11-24)

Kodiert hat der Supervisor nach [../validierung.md](../validierung.md), § 3: zwei Kodier-Agenten,
ein Schlicht-Agent für die Uneinigkeiten, **alle drei dasselbe Modell** (`claude-opus-5-5`; Frage 19
an Konrad ist offen, es gilt die Annahme). Kein menschlicher Goldstandard; α misst die Schärfe des
Codebuchs für dieses Modell, nicht die Richtigkeit der Labels (§ 4.1). Zusammengeführt mit `georep
validate merge`; `labels.csv`, `README.md` und `guete.json` liegen in beiden Ordnern.

| Codebuch | Einheiten | einig | Cohens κ | Krippendorffs α (ordinal) | geschlichtet |
|---|---|---|---|---|---|
| `18-einbettungen` (Suche) | 916 | 881 (96,2 %, Wilson 94,7–97,2) | 0,933 | **0,975** | 35 |
| `18-einbettungen-nachbarn` | 383 | 360 (94,0 %, Wilson 91,2–96,0) | 0,906 | **0,943** | 23 |

Beide α liegen über 0,8; Stufe 3 darf zeigen (Plan, § 2.6). Endlabels der Suche: 529 Paare
relevant (`2`), 144 teilweise (`1`), 243 nicht relevant (`0`); jede der 50 Fragen hat mindestens ein
relevantes Dokument, keine fällt heraus.

**Suche, nDCG@10** (`--auswertung`, 2026-11-24; Intervalle Bootstrap über die Fragen, 2 000
Ziehungen, Seed 20261123; p zweiseitig aus 10 000 Vorzeichen-Permutationen, 0,0001 ist der kleinste
mögliche Wert). Die Zeile „alle" mit den Differenzen ist die vorab festgelegte Rechnung; die
Intervalle der Mittel und alles je `form` sind nach der Kodierung auf Bitte des Supervisors
nachgetragen (Frage 9.9) und explorativ, mit eigenem Zufallsstrom, damit die festgelegten Zahlen
gleich bleiben.

| Form | Fragen | BM25 | Einbettung | Mischung | Einbettung − BM25 | Mischung − BM25 |
|---|---|---|---|---|---|---|
| alle | 50 | 0,709 (0,622–0,785) | **0,883** (0,842–0,919) | 0,846 (0,792–0,899) | **+0,175** (+0,106 bis +0,255), p 0,0001 | **+0,137** (+0,094 bis +0,185), p 0,0001 |
| wort | 18 | 0,933 (0,893–0,967) | 0,965 (0,934–0,991) | 0,979 (0,961–0,994) | +0,032 (−0,004 bis +0,064), p 0,108 | +0,046 (+0,021 bis +0,076), p 0,002 |
| umschrieben | 18 | 0,623 (0,488–0,755) | 0,804 (0,722–0,876) | 0,771 (0,670–0,867) | +0,181 (+0,043 bis +0,330), p 0,022 | +0,148 (+0,072 bis +0,240), p 0,0002 |
| frage | 14 | 0,529 (0,357–0,684) | 0,880 (0,817–0,933) | 0,770 (0,676–0,858) | +0,350 (+0,207 bis +0,488), p 0,0004 | +0,241 (+0,152 bis +0,329), p 0,0008 |

Je Frage ist die Einbettung bei 35 der 50 Fragen besser als BM25 und bei 10 schlechter, die Mischung
bei 39 besser und bei 5 schlechter. Nach `art`: Orte (9) BM25 0,610 gegen Einbettung 0,877, Themen
(34) 0,730 gegen 0,887, Vorhaben (7) 0,730 gegen 0,876. Am deutlichsten verliert die Einbettung bei
a25 „Busse und Bahnen pünktlicher machen" (0,310 gegen 0,605) und a07 „Photovoltaik auf städtischen
Dächern" (0,756 gegen 0,931); in beiden Fällen liegt die Mischung nahe bei BM25 oder darüber.

**Zu Frage 9.9** (liegt der Vorsprung nur bei umschriebenen Fragen?): Nein, aber er hängt an der
Form. Am größten ist er bei ganzen Fragesätzen (+0,350), wo BM25 ohne Stoppwortliste (so vorab
festgelegt) Funktionswörter mitzählt; bei Stichwörtern im Amtswortlaut ist er klein und nicht gegen
null gesichert (+0,032), dort ist die **Mischung am besten** (0,979). Ohne die 14 Fragesätze, also an
den 36 Stichwörtern, liegt die Einbettung explorativ um +0,107 (+0,032 bis +0,182) vorn, die Mischung
um +0,097 (+0,055 bis +0,152): auch ohne den Vorteil bei Fragesätzen über der Schwelle, mit
breiterem Intervall.

**Explorative Varianten** (dieselben Labels; nicht geurteilte Dokumente zählen nicht, darum mit
judged@10, und je kleiner judged@10, desto eher zu gut): BM25 ohne Stemmer 0,749 (judged@10 0,736),
Einbettung nur mit dem ersten Stück 0,874 (0,642), Einbettung mit 256 Komponenten 0,874 (0,726),
konvexe Mischung 0,845 (0,992). Die konvexe Mischung ist fast ganz geurteilt und liegt gleichauf mit
RRF. Dass BM25 ohne Stemmer höher liegt als mit, ist bei einem Viertel ungeurteilter Treffer nicht
gesichert; ein Kandidat ist die Verschmelzung „sicherer"/„Sicherheit" → „sich" (§ 3.6).

**Ähnliche Dokumente** (Präzision@5; Intervalle Wilson über die 250 Paare und Bootstrap über die 50
Anker):

| | Einbettung | TF-IDF |
|---|---|---|
| `gleiche_sache` | 85 | 66 |
| `gleiches_thema` | 123 | 97 |
| `verschieden` | 42 | 87 |
| **Präzision@5** | **0,832** (Wilson 0,781–0,873; Anker 0,760–0,892) | 0,652 (Wilson 0,591–0,708; Anker 0,560–0,744) |
| streng (nur `gleiche_sache`) | 0,340 | 0,264 |
| Präzision auf Rang 1 / 2 / 3 / 4 / 5 | 0,94 / 0,84 / 0,76 / 0,86 / 0,76 | 0,88 / 0,72 / 0,70 / 0,54 / 0,42 |

Die Einbettung hält ihre Präzision bis Rang 5, TF-IDF fällt nach Rang 1 ab. Ein Zeichen für
denselben Vorgang ohne Kodierung (Drucksachennummer, § 3.6) tragen bei beiden 11 % der Paare;
kodiert sind 34 % der Vorschläge der Einbettung dieselbe Sache.

Ein Fehler des Skripts, vor diesem Ergebnis behoben: der Bootstrap über die Anker zog nach Platz,
und die Folge der Anker kam aus Polars `unique()` ohne feste Ordnung, so dass das Anker-Intervall
von Lauf zu Lauf um ein Hundertstel schwankte (0,764 bis 0,768 als untere Grenze). Seit die Anker
sortiert sind, geben zwei Läufe dieselben Zahlen; Punktschätzungen und Wilson-Intervalle waren nie
betroffen.

## 5. Urteil gegen das Kriterium

### 5.1 Urteil (2026-11-24): bauen

Nach der Regel aus § 3.1 (Commit `a38e149`), ohne Anpassung an die Labels:

- **Suche: erfüllt.** max(Einbettung − BM25, Mischung − BM25) = max(+0,175, +0,137) = +0,175 ≥ 0,05.
  Auch die untere Grenze des Intervalls (+0,106) liegt über der Schwelle.
- **Nachbarn: erfüllt.** Präzision@5 der Einbettung 0,832 ≥ 0,70 (Wilson 0,781–0,873, Bootstrap über
  die Anker 0,760–0,892; beide unteren Grenzen über 0,70).
- **Daraus: bauen** — `embeddings`, `neighbors` und `georep suche` mit dem Verfahren, das im Mittel
  höher liegt: **die Einbettung** (0,883 gegen 0,846 der Mischung).
- **Rückfallregel, TF-IDF-Nachbarn**: greift nicht; TF-IDF erreicht 0,652 < 0,70 (und liegt 0,180
  unter der Einbettung).
- **Validierung für Stufe 3**: α 0,975 und 0,943, beide ≥ 0,8. Die Seite sagt wörtlich, was
  `guete.json` sagt („geprüft von zwei KI-Kodierern an 383 Dokumentpaaren, nicht von Menschen"), und
  dazu, dass Kodierer und Schlichter dasselbe Modell sind.

Was das Urteil nicht entscheidet, aber Stufe 2 wissen sollte: Bei Stichwörtern im Amtswortlaut war
die Mischung das beste Verfahren (0,979 gegen 0,965) und nie weit hinter der Einbettung; die
Einbettung verliert dort, wo das Wort der Verwaltung genau getroffen ist (a07, a25). `georep suche`
nimmt die Einbettung als Vorgabe, wie die Regel es sagt; `--verfahren mischung` steht im Bauplan
(§ 6) und kostet nur die Wortmatrix. Ob die Mischung Vorgabe werden soll, wäre eine neue Messung mit
neuen Fragen (Frage 9.12), keine Auslegung dieser.

### 5.2 Vor den Labels entschieden

- **Rechenaufwand: tragbar.** Die Hauptperiode ist ganz eingebettet (11,5 Minuten in einem
  gesperrten Block), alle vier Datensätze kosten rund 17 GPU-Minuten (§ 3.3). Die Stichprobengrenze
  von 500 Dokumenten des Plans ist hier nach der Freigabe des Supervisors überschritten, weil die
  Hochrechnung unter zwei GPU-Stunden lag; ein Auftrag für die Warteschlange war nicht nötig.
- **Paket: nur Nachbarn, keine Vektoren** (§ 3.4, Frage 9.1).
- **Cluster: nicht bauen** (§ 3.5): die Einbettung ordnet nach Dokumentform, ihre Topwörter sind
  weniger kohärent (NPMI 0,291 gegen 0,405 der freien NMF) und weniger stabil (ARI 0,689 gegen
  0,899); dem Ausschuss kommt das gesäte Modell der Seite näher (NMI 0,737 gegen 0,451).
- **Freie semantische Suche auf der Seite: nicht in Stufe 3** (§ 3.4, Frage 9.3).

### 5.3 Wie die Zahlen zu lesen sind

Die Differenzen sind Mittel über 50 Fragen (je Form 14 bis 18); die Intervalle sind darum breit,
insgesamt rund ±0,07, je Form bis ±0,14. Das Kriterium ist die Punktschätzung, wie das Briefing es
setzt; hier liegt auch die untere Grenze darüber. Gemessen ist die Übereinstimmung mit einem Modell
(drei Agenten desselben Modells), an Fragen, die ein Agent geschrieben hat, und an der Hauptperiode;
für Menschen, echte Suchprotokolle und andere Perioden ist nichts gemessen (Fragen 9.9, 9.10).

## 6. Bauplan Stufe 2

Geschrieben für den Fall „bauen"; welche Teile kommen, entscheidet § 5 nach den Labels (Suche,
Nachbarn, oder beides). Alles unten ist so geschnitten, dass jeder Teil allein gebaut werden kann.

**Beitrag** `18-einbettungen` im Register `georep.enrich.CONTRIBUTIONS` (F2, Punkt 69), am Ende
des Tupels, mit zwei Schritten:

1. `embeddings` (`models=EmbeddingUse(..., "18-stuecke-1")`, läuft nur mit `georep run --models`,
   F5): liest den Rohtextstore von F1 (`rohtexte.parquet`, nach Dateiname geschlüsselt) und den
   Korpus, zerteilt nach `18-stuecke-1` (§ 3.1, die Funktion `zerteile` des Messskripts unverändert
   nach `src/georep/prep/chunks.py`, rein, mit Verträgen), bettet über `embed_texts` ein und
   schreibt **nur lokal** `processed/einbettungen_stuecke.parquet` (`datei`, `stueck`, `start`,
   `end` im Rohtext, `vektor` als `Array(Float32, 768)`) und `processed/einbettungen_dokumente.parquet`
   (`id`, `vektor`; Mittel der ersten drei Stücke, `18-dokvektor-1`). Eine Zeile je Korpus-ID; IDs
   ohne Rohtext fehlen, und der Stamp sagt, wie viele. Schema-Version aus der Modulkonstante.
2. `neighbors` (offline, ohne Modell): liest `einbettungen_dokumente.parquet` und schreibt `processed/aehnliche_dokumente.parquet`: `id`, `rang` (1 bis 10),
   `nachbar`, `aehnlichkeit` (Float32, vier Stellen), sortiert nach `id, rang`. Nachbarn ohne die
   eigene Datei; Gleichstände nach ID. Vertrag: zehn Zeilen je ID mit Dokumentvektor, `rang`
   lückenlos, `nachbar != id`, `aehnlichkeit` fallend. Ohne Dokumentvektoren (Pages, CI) kommt die
   Tabelle aus dem Paket. Gemessen 2026-11-23: 7,8 s für zehn Nachbarn je Einheit über die 19 032 Einheiten der Hauptperiode (Blöcke zu 2 048, float32, CPU).

**Paket.** Auf Pages gibt es weder GPU noch Modell. Ins Repo kommt darum **nur die Nachbartabelle**
(0,88 MiB zstd, § 3.4) als `snapshots/duesseldorf-aehnlich/` über `georep pack
--neighbors` (Anhängeregel, Synergie § 2.1), mit README (Modell, Digest, Prompt-Versionen, Datum,
SHA-256). **Die Vektoren kommen nicht ins Repo**: Dokumentvektoren 25,7 MiB (float16), 8,6 MiB (256 Komponenten) oder 7,5 MiB (int8), die Stückvektoren, die die Suche braucht, 64,0 MiB, je für die Hauptperiode allein (Frage 9.1). `georep suche`
braucht sie nur lokal, wo auch der Modellcache liegt. Damit schrumpft Frage 18/26 für dieses
Vorhaben auf die Nachbartabelle.

**CLI** `georep suche "<frage>" [--verfahren einbettung|mischung|bm25] [--n 10] [--profil …]`:
lokal, liest `einbettungen_stuecke.parquet` und, für BM25 und die Mischung, eine Wortmatrix, die
der Befehl beim ersten Aufruf aus dem Rohtextstore baut (5,8 bis 8,9 s für die Hauptperiode) und neben die Vektoren legt;
die Frage wird über F5 eingebettet (ein Aufruf; 50 Fragen kosteten zusammen 0,6 s Rechenzeit auf der GPU, auf der CPU
wäre es für eine Frage unter einer Sekunde). Ausgabe: Rang, Punktzahl, Drucksache, Datum, Titel, Link. Ohne ollama: nur `--verfahren
bm25`, mit einer Zeile dazu.

**Stemmer.** BM25 braucht den Snowball-Stemmer; das Messskript setzt ihn in rund 70 Zeilen ohne
Abhängigkeit um und prüft ihn an zehn Wörtern der Beispielliste von snowballstem.org. Für Stufe 2:
dieselbe Umsetzung als `src/georep/search/stem.py` mit der vollständigen Beispielliste von snowballstem.org (Vokabular und
Ausgabe, als Test-Fixture mit Quelle und Lizenz, BSD) statt einer neuen Abhängigkeit
(`snowballstemmer` wäre eine reine Python-Bibliothek, BSD; Frage 9.4).

**Settings** (Anhängeregel): Modell `EmbeddingsSettings` vor `class Settings`, Feld `embeddings` am
Ende, Block `# --- Vorhaben 18: Einbettungen` am Ende von `defaults.toml`: `enabled = false`,
`chunk_chars = 1600`, `title_chars = 200`, `overlap_chars = 200`, `document_chunks = 3`,
`neighbors = 10`, `bm25 = {k1 = 1.2, b = 0.75}`, `rrf_k = 60`, `fusion_depth = 100`; Präfixe
`search_document: ` und `search_query: ` gehören zum Modell und stehen darum in `[ml.embedding]`
(`document_prefix`, `query_prefix`), nicht im Code. Was das Ergebnis bestimmt, steht zusätzlich in
der Prompt-Version (`18-stuecke-1`), damit eine Änderung den Cache nicht trifft. Im Profil
`duesseldorf.toml`: `enabled = true`.

**Tests** (roter Test zuerst, CLAUDE.md; nie ein Modell, `FakeEmbedder` aus `tests/fakes.py`):

- Beispiele: `zerteile` mit leeren Zeilen, einer Zeile über dem Budget ohne Leerstelle, langem
  Titel; BM25 gegen eine Rechnung von Hand an drei Dokumenten; RRF an zwei Listen; Stemmer an der
  Beispielliste.
- hypothesis in `tests/property/`: jedes Stück hat höchstens `chunk_chars` Zeichen ohne Präfix; jede
  Zeile des Rohtexts (ohne Leerraum) steht in mindestens einem Stück; die Überlappung zweier
  benachbarter Stücke ist höchstens `overlap_chars`; die Nachbartabelle hat zehn Zeilen je ID und
  nie die eigene Datei; RRF ist symmetrisch in den Listen.
- `pytest -m slow`: die Zahl der Stücke der Hauptperiode (47 407) und die Rangfolgen der 50
  Fragen für BM25 gegen eine gespeicherte Liste (nur IDs); für die Einbettung nur Invarianten, weil
  die GPU je Rechner anders rundet (wie die Themen, CLAUDE.md).
- Golden Master unberührt: kein bestehender Schritt liest die neuen Dateien.

**Berührte Dateien**: neu `src/georep/prep/chunks.py`, `src/georep/search/bm25.py`,
`src/georep/search/stem.py`, `src/georep/enrich/embeddings.py`, `src/georep/suche.py` (CLI), Tests,
`snapshots/duesseldorf-aehnlich/`; je eine angehängte Zeile oder ein Block in
`src/georep/enrich/__init__.py`, `settings.py`, `defaults.toml`, `profiles/duesseldorf.toml`,
`cli.py` (`suche`, `pack --neighbors`), `pack.py`, `bootstrap.py`,
`tests/unit/test_data_packages.py`; `docs/architecture.md` („Modelle", Beiträge),
`docs/decisions.md` (Eintrag ohne Nummer: Suche über Stücke mit Maximum, Mischung mit RRF,
Nachbarn als Paket statt Vektoren).

**Profile.** Stufe 2 läuft lokal für jedes Profil mit Rohtext (§ 3.3: zusammen rund 17 GPU-Minuten),
auf Pages nur mit dem Nachbarpaket der Hauptperiode (Synergie, Konflikt 14). Mönchengladbach ist der
Prüfstein für Stadtneutralität: nichts im Code kennt eine Stadt, die Präfixe kommen aus `[ml]`.

## 7. Bauplan Stufe 3

**Ähnliche Dokumente im Dokumentdialog** (kein eigener Abschnitt, keine Unterseite): der Haken von
Vorhaben 14 in `templates/frame/script.js.j2` (Synergie § 1, „Dokumentdialog, nachgeladen") lädt
`data/aehnlich.json` beim ersten Öffnen eines Dialogs nach; je Dokument fünf Nachbarn als Indizes in
eine Tabelle. Größe (§ 3.4): fünf Nachbarn als Indizes 307 KB (gzip 128 KB) für die 10 788 Dokumente des Dialogs, dazu Datei, Datum, Drucksache und Titel der 3 726 Nachbarn, die nicht in `dokumente.json` stehen, 513 KB (gzip 134 KB); zusammen 820 KB, gzip 262 KB, einmal geladen. `index.html` wächst nur um die Zeilen des Hakens
(unter 1 KB). Jeder Vorschlag mit Drucksache, Datum, Titel und Link wie die Trefferliste; darunter
der Satz zur Validierung aus `guete.json` („geprüft von zwei KI-Kodierern an 383 Dokumentpaaren,
nicht von Menschen"), Präzision@5 0,83 mit Intervall und der Hinweis, dass Kodierer und Schlichter
dasselbe Modell sind.

**Keine freie semantische Suche auf der statischen Seite in Stufe 3.** Was sie bräuchte, beziffert
§ 3.4; beides ist größer als das, was eine Stufe 3 tragen soll (Frage 9.3).

**Tabellen im Register**: `aehnliche_dokumente` als Download (Parquet, zehn je Dokument), mit
Spaltenbeschreibung in `schema.json` und dem Satz zur Validierung.

## 8. Vorab festgelegte Hypothesen

Keine: Vorhaben 18 prüft ein Verfahren gegen ein Kriterium, keine These über die Ratsarbeit. Was
vorab festgelegt ist (Verfahren, Kriterium, Rückfall, explorative Zusätze), steht in § 3.1.

## 9. Risiken und offene Fragen

| Nr. | Frage | Warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 9.1 | Kommen Vektoren ins Repo (Frage 18/26)? | Dokumentvektoren 7,5 bis 25,7 MiB, Stückvektoren 64 MiB, je für die Hauptperiode allein; das Paketbudget hat rund 11 bis 14 MiB Luft | **Nein.** Ins Repo nur die Nachbartabelle (0,88 MiB); Vektoren bleiben im Modellcache, `georep suche` ist lokal. Damit ist Frage 26 für 18 beantwortet, Frage 18 nicht berührt |
| 9.2 | Wer kodiert 916 + 383 Einheiten, und in wie vielen Läufen? | Der Pool der Top-10 je Verfahren ist groß (Plan § 11 verlangt ihn); je Kodierer rund 2,7 + 1,4 Mio. Zeichen Ausschnitt | Erledigt am 2026-11-24 durch den Supervisor (§ 4.4): alle 916 und 383 Einheiten kodiert, 35 und 23 geschlichtet |
| 9.3 | Soll es eine freie semantische Suche auf der Seite geben? | Modell im Browser oder Server, § 3.4: rund 0,5 GB Modell oder ein eigener Dienst, dazu 12 bis 64 MB Index | Nicht in Stufe 3; „ähnliche Dokumente" und `georep suche` lokal decken die Ratsarbeit, eine Suche auf der Seite wäre ein eigenes Vorhaben mit eigener Messung (kleineres Modell, andere Vektoren) |
| 9.4 | Snowball-Stemmer als eigene Umsetzung oder als Abhängigkeit `snowballstemmer`? | eine Bibliothek für rund 70 Zeilen gegen den Prüfaufwand einer eigenen | Eigene Umsetzung mit der vollständigen Beispielliste als Test (wie `krippendorff` in F4, Punkt 71) |
| 9.5 | Wie erkennt ein Modellschritt, dass ollama still auf der CPU rechnet? | Am 2026-11-23 um 22:42 scheiterte die CUDA-Initialisierung (`ggml_cuda_init: failed to initialize CUDA: initialization error` im Log), `ollama ps` sagte trotzdem „100% GPU"; rund 1,6 Stücke/s statt rund 90 je Sekunde auf der GPU | Die Messung prüft das Tempo an einer Probe von 64 Stücken (`GPU_GRENZE_S`); 370 auf der CPU gerechnete Vektoren dieses Vorhabens sind aus dem Cache gelöscht und auf der GPU neu gerechnet. Für F5: eine Tempo-Probe in `georep ml status` oder vor dem ersten Stapel, Entscheidung des Supervisors |
| 9.6 | Unter welcher Lizenz stehen die Gewichte von `nomic-embed-text-v2-moe`? | Die Seite nennt das Modell neben den Nachbarn | `ollama show --license` ist leer; nach Erinnerung Apache 2.0. Vor Stufe 3 auf der Modellseite nachsehen |
| 9.7 | Verraten veröffentlichte Vektoren Text? | Aus Einbettungen lässt sich Text teilweise zurückgewinnen (Morris u. a. 2023, „vec2text"*), bei kurzen Texten weitgehend; die Seite veröffentlicht bewusst keine Volltexte (`workflow-ratsmitglied.md`, § 4) | Keine Vektoren auf der Seite und im Repo (9.1); die Nachbartabelle trägt nur IDs und Ähnlichkeiten |
| 9.8 | Kommt `georep suche` mit BM25, auch wenn Teil 1 des Kriteriums verfehlt wird? | BM25 ist billig und ohne Modell; die Messung liefert seine Güte mit | Entfällt: Teil 1 ist erfüllt (§ 5.1). BM25 bleibt als `--verfahren bm25` für Läufe ohne ollama (nDCG@10 0,709) |
| 9.9 | Sind die Labels voreingenommen? | Suchfragen, Bedarf und Kodierung kommen aus derselben Modellfamilie; der Bedarf beschreibt Synonyme, die BM25 nicht sieht, aber die Einbettung vielleicht | Beantwortet, soweit es die Daten können (§ 4.4): der Vorsprung liegt nicht nur bei umschriebenen Fragen, am größten ist er bei Fragesätzen, bei Stichwörtern im Amtswortlaut ist er klein (+0,032, Intervall über 0); ohne Fragesätze +0,107. Dass Fragen, Bedarf und Labels aus derselben Modellfamilie kommen, bleibt als Grenze (Frage 19 an Konrad) |
| 9.10 | Gilt das Ergebnis für die anderen Perioden und für Mönchengladbach? | Gemessen ist nur die Hauptperiode (Plan § 2.13) | Ja für Zerteilung, Laufzeit und Größen (§ 3.3); die Güte wird für andere Profile nicht nachgemessen, die Seite nennt die Hauptperiode als Ort der Prüfung |
| 9.11 | Wie wird das Codebuch für eine nächste Fassung schärfer? | Die Schlichter haben an den 35 und 23 Uneinigkeiten Regeln vorgeschlagen; angewandt auf dieselben Einheiten würden sie die eigene Anpassung messen (F4, § 2) | **Nicht angewandt.** Für eine Fassung 2 mit neuer Stichprobe, Suche: (a) der Bedarf vor dem Doppelpunkt ist das Gesuchte, die Liste danach sind Beispiele; (b) fragt die Suchfrage nach einem Aspekt, ist er Pflicht; (c) die Reichweite eines Orts folgt dem Bedarf, Ortsarten zählen wie Orte; (d) der Betreff zählt wie ein Titel; (e) Sammelvorlagen: ein großer Abschnitt ist `1`, `2` erst, wenn Titel, Betreff oder Beschluss es nennen; (f) Gremienbesetzungen sind `0`. Nachbarn: ein Sachthema ist eine Art Maßnahme; derselbe Ort allein stiftet kein Thema; Teilvorlagen derselben Runde sind dieselbe Sache; Einzelbeschlüsse gegen denselben Topf bilden keine Liste; mehrjährige Programme sind Thema, derselbe Vorgang ist Sache |
| 9.12 | Soll `georep suche` die Mischung statt der Einbettung als Vorgabe nehmen? | Bei Stichwörtern im Amtswortlaut war die Mischung am besten (0,979), insgesamt die Einbettung (0,883 gegen 0,846) | Vorgabe nach der Regel: Einbettung; `--verfahren mischung` als Option. Eine andere Vorgabe nur nach einer neuen Messung mit neuen Fragen |

## 10. Änderungen durch die Synergie (füllt der Supervisor)

Geschrieben am 2026-11-24 nach dem Urteil (§ 5.1), vor dem Start der Stufe 2. Die Synergie
([00-synergien-2026-11.md](00-synergien-2026-11.md)) entstand vor dieser Messung und hat für 18 keinen
Eintrag in § 4; was sie trotzdem festlegt, steht hier.

1. **Fundamente seit dem Bauplan.** F7 (Punkt 74) gibt jeder Fabrik `http`; 18 braucht es nicht. Der
   Beitrag hängt in `CONTRIBUTIONS`, nicht in `early_steps`: kein Schritt vor `weights` liest Nachbarn.
   Der Rohtext kommt aus F1 (Punkt 73) nach Dateiname; geteilte Dateien bekommen eine Zeile je
   Korpus-ID (Synergie § 1).
2. **Befehl und Namen.** Die Befehle der CLI sind englisch (`run`, `pack`, `regress`, `validate`):
   der Suchbefehl heißt **`georep search "<frage>" [--method embedding|hybrid|bm25] [--n 10]`**, das
   Profil kommt über das globale `--profile`. Die Logik liegt in `src/georep/search/` (`bm25.py`,
   `stem.py`, `query.py`), `cli.py` hängt nur den Befehl an; kein `src/georep/suche.py`. Dateinamen
   der Daten bleiben deutsch (`einbettungen_*.parquet`, `aehnliche_dokumente.parquet`), wie im Bauplan.
3. **Paket.** Nur die Nachbartabelle der Hauptperiode (`snapshots/duesseldorf-aehnlich/`, rund
   0,9 MiB) über `georep pack --neighbors`, unter `TOTAL_LIMIT` in `tests/unit/test_data_packages.py`
   (Annahme zu Frage 26: kleine Pakete ja, Vektoren nein). Anhängeregel aus Synergie § 2.1 für
   `pack.py`, `bootstrap.py`, `cli.py`, `test_data_packages.py`; 14 und 22 bauen dort parallel.
4. **Stemmer-Prüfliste.** Die Beispielliste von snowballstem.org (Vokabular und Ausgabe, BSD) darf
   einmal abgerufen werden (Fremddaten, Konrads Antwort 8). Ins Repo kommt eine feste Teilmenge
   (jedes n-te Wort, rund 2 000 Paare) mit Quelle, Datum, Lizenz und SHA-256 der vollen Dateien in
   einem README daneben; die volle Liste bleibt lokal unter `/media/konrad/xtraspace/georep/fremddaten/`.
5. **GPU.** `georep run --models` nur unter `flock /media/konrad/xtraspace/georep/gpu-queue/gpu.lock`,
   höchstens 30 Minuten je gesperrtem Lauf (Meta-Plan § 5); vorher und nachher im ollama-Log
   „offloaded n/n layers" und das Tempo prüfen (Frage 9.5). Die Vektoren der Messung liegen im
   Modellcache; ein Lauf mit derselben Prompt-Version `18-stuecke-1` trifft ihn.
6. **Tempo-Probe (Frage 9.5).** Entschieden vom Supervisor: keine eigene Probe in 18. Eine Probe vor
   dem ersten Stapel gehört nach F5 und geht als Rückstand nach `docs/todo.md`; 18 prüft im Bau von
   Hand wie oben.
7. **Merge.** 18 hängt an keinem Vorhaben der Welle 1 und wird gemerged, sobald es fertig ist (Synergie
   § 3.4: ein fertiger Branch wartet nicht auf einen langsameren, von dem er nicht abhängt); es rebast
   auf den Stand, den `main` dann hat. Stufe 3 (ähnliche Dokumente im Dialog) wartet auf den Haken von 14.
