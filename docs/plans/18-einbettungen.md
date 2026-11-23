# Vorhaben 18: Einbettungen, Ähnlichkeit, semantische Suche

Stand 2026-11-23, Stufe 1 (Messen), Branch `feat/18-einbettungen`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „18 Einbettungen,
Ähnlichkeit, semantische Suche". Messskript: [18-einbettungen-messung.py](18-einbettungen-messung.py).
Suchfragen: [18-einbettungen-anfragen.toml](18-einbettungen-anfragen.toml).

Dieser Stand enthält nur die **vorab festgelegte Messung** (§ 3.1). Sie ist geschrieben und
committet, bevor ein Verfahren auf eine Suchfrage oder einen Anker lief; sie wird danach nicht mehr
geändert, Ergebnisse kommen in eigene Abschnitte.

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
