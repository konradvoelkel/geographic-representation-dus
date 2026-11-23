# Validierung mit zwei KI-Kodierern (Fundament F4)

Stand 2026-11-23. Paket `georep.validation`, Befehl `georep validate sample|tasks|merge|score`.
Auftrag: [plan-vorverarbeitung-2026-11.md](plan-vorverarbeitung-2026-11.md), § 2.6 und § 7 (F4);
Gründe und verworfene Alternativen: [decisions.md](decisions.md), „Validierung mit zwei
KI-Kodierern". Diese Datei ist das Handbuch für den Supervisor und die Vorlage für die Aufträge an
die Agenten.

## 1. Was das Verfahren misst und was nicht

Konrad kodiert nicht selbst (2026-11-23). Jede Stichprobe eines Vorhabens kodieren darum **zwei
unabhängige Kodier-Agenten** nach einem Codebuch, ein **Schlicht-Agent** entscheidet nur ihre
Uneinigkeiten. Daraus entstehen zwei Zahlen:

- **Übereinstimmung der beiden Kodierer** (Krippendorffs α, dazu Cohens κ und der Anteil gleicher
  Labels mit Wilson-Intervall). Sie sagt, ob das Codebuch eindeutig genug ist, dass zwei
  Durchgänge dasselbe Urteil fällen. Stufe 3 eines Vorhabens verlangt **α ≥ 0,8**
  (`validation.min_alpha`); darunter ist das Codebuch zu unscharf, und das Vorhaben geht zurück in
  Stufe 1. Bei ordinaler Skala gilt das ordinale α, sonst das nominale.
- **Güte des geprüften Verfahrens gegen die geschlichteten Labels** (Präzision, Recall, F1 je
  Klasse, mikro und makro; nDCG@k für Rangfolgen; bei binärer Skala der Anteil positiver Urteile,
  also die Präzision, wenn die Einheiten die Treffer des Verfahrens sind).

**Was es nicht misst.** Es gibt **keinen menschlichen Goldstandard**. Die Labels sind das Urteil
eines stärkeren Modells, nicht das von Menschen; gemessen wird die Übereinstimmung des Verfahrens
mit diesem Modell. Zwei Kodierer desselben Modells teilen dessen Fehler und Vorlieben: ein hohes α
heißt „das Codebuch ist für dieses Modell eindeutig", nicht „die Labels stimmen". Es liegt
darum eher über dem, was zwei Menschen mit demselben Codebuch erreichten: ein niedriges α ist ein
deutlicher Befund (das Codebuch ist unscharf), ein hohes nur eine notwendige Bedingung und kein
Beleg der Richtigkeit. Die Seite sagt das wörtlich: **„geprüft
von zwei KI-Kodierern an *n* Dokumenten, nicht von Menschen"** (`satz` in `guete.json`).

Darum ist die KI-Kodierung der **vierte** Weg und nicht der erste (Plan, § 2.6): zuerst
deterministische Prüfungen (eine Drucksachennummer existiert oder nicht), dann Labels aus den Daten
selbst (Beratungsfolge, Dokumentart, Verweise), dann von Menschen kodierte Fremddaten, erst dann
die Kodier-Agenten.

**Was die Einheiten nicht können.** Eine Einheit ist ein Urteil über etwas Gegebenes: ein
Dokument, ein Paar, eine Spanne, eine Suchanfrage mit einem Dokument. Spannen *finden* lassen die
Kodierer nicht. Ein Recall über „vollständig annotierte Dokumente" (Vorhaben 12) braucht darum
eine Frage, die sich als Label beantworten lässt — etwa die Einheit `document` mit „Nennt der
Ausschnitt einen Betrag, den die hervorgehobenen Spannen nicht tragen? ja/nein" und den Spannen
des Verfahrens im Auftrag. Das ist dann ausdrücklich ein Urteil über die Ausgabe und gehört so ins
Codebuch.

## 2. Das Codebuch

Der Mess-Agent schreibt es in Stufe 1 (Messdokument, Abschnitt 4) nach
`validierung/<NN-name>/codebuch.toml`. Die Schlüssel sind englisch wie in allen TOML-Dateien des
Pakets, die Texte deutsch. pydantic prüft es (`georep.validation.codebook`); ein Fehler nennt das
Feld.

```toml
project = "11-struktur"          # der Ordnername
version = "1"                    # bei jeder Änderung hochzählen; steht in Aufträgen, README, guete.json
unit = "document"                # document | document_pair | span | query_document
question = "Steht im Ausschnitt ein Beschlussvorschlag, und wo beginnt er?"
scale = "nominal"                # nominal | ordinal (Optionen aufsteigend) | binary (genau zwei)
instructions = """
Lies den Titel und den Ausschnitt. Ein Beschlussvorschlag ist der Text, über den abgestimmt
werden soll ("Der Rat beschließt ..."). Eine Begründung ist keiner, auch wenn sie "beschließen"
enthält. Im Zweifel: keiner.
"""

[[options]]
value = "vorhanden"
definition = "Der Ausschnitt enthält einen Beschlussvorschlag."
example = "Beschlussvorschlag: Der Ausschuss beschließt die Planung ..."

[[options]]
value = "fehlt"
definition = "Kein Beschlussvorschlag im Ausschnitt."

[sample]
size = 200
seed = 20261123
stratum = "paper_type"           # Spalte der Grundgesamtheit; leer = ungeschichtet
allocation = "proportional"      # oder "equal": gleich viele je Schicht (etwa 100 Treffer je Art)
population = ""                  # Parquet relativ zum Profilordner; leer = interim/papers.parquet
strata = []                      # nur diese Schichten
require_text = true              # Einheiten ohne Text im Korpus fallen weg

[text]
source = "raw"                   # corpus (kleingeschrieben) oder raw (Rohtextstore von F1)
chars = 6000                     # Ausschnitt vom Anfang des Dokuments
window = 400                     # bei unit = "span": Zeichen vor und hinter der Spanne
title = true
spans = ""                       # Spannen nach F3 (id, start, end, kind) zum Hervorheben
span_kinds = []
context = []                     # weitere Spalten der Grundgesamtheit im Auftrag; nie die Ausgabe des Verfahrens

[score]
positive = ""                    # Pflicht bei scale = "binary": das Label, das als Treffer zählt
k = 10                           # nDCG@k bei unit = "query_document"
```

| Einheit | Grundgesamtheit (Parquet) | Schlüssel `id` | im Auftrag |
|---|---|---|---|
| `document` | `id` (Standard: der Korpus) | `<id>` | Titel, Ausschnitt vom Anfang, Spannen darin |
| `document_pair` | `id_a`, `id_b` | `<id_a>\|<id_b>` | beide Dokumente |
| `span` | `id`, `start`, `end` (F3) | `<id>\|<start>\|<end>` | Fenster um die Spanne, die Spanne zwischen ⟦ ⟧ im Feld `markiert` |
| `query_document` | `query`, `id` | `<query>\|<id>` | die Suchanfrage und das Dokument |

Gute Codebücher, aus der Literatur zur Inhaltsanalyse: die Optionen schließen einander aus und
decken alles ab; jede hat eine Definition und, wo es geht, ein Beispiel aus der Ratsarbeit; die
Anweisungen sagen, was zu lesen ist und wie Grenzfälle entschieden werden („im Zweifel …"). Eine
Option „unklar" senkt α und gehört nur hinein, wenn das Vorhaben sie auswerten will. Ändert sich
das Codebuch nach einer Kodierung, zählt `version` hoch, und die Kodierung beginnt mit einer neuen
Stichprobe (neuer Seed): wer das Codebuch an den Uneinigkeiten derselben Einheiten schärft und sie
dann neu kodieren lässt, misst seine eigene Anpassung.

Spannen beziehen sich auf den Text, in dem sie gefunden wurden: wer Spannen aus dem Rohtext
hervorhebt, setzt `text.source = "raw"`. Liegt eine Spanne außerhalb des Textes, bricht `tasks`
mit der Quelle in der Meldung ab.

## 3. Der Ablauf für den Supervisor

Auf Konrads Rechner liegen die Aufträge auf xtraspace; einmal in `settings.local.toml` (des
Hauptklons und jedes Worktrees, der validiert):

```toml
validation.coding_root = "/media/konrad/xtraspace/georep/messdaten/kodierung"
```

Ohne den Schlüssel liegen sie unter `<data_root>/kodierung/` (gitignored). Unter
`validation.root` (dem Ordner im Repo) verweigert das Paket sie.

```bash
V=11-struktur
uv run georep validate sample $V                     # 1. Stichprobe; stichprobe.csv und .json committen
uv run georep validate tasks $V --coder A            # 2. Aufträge, lokal
uv run georep validate tasks $V --coder B
#                                                      3. zwei Kodier-Agenten starten (§ 4.1), parallel
uv run georep validate merge $V --model claude-opus-5-5   # 4. Uneinigkeiten -> Auftrag der Schlichtung
#                                                      5. Schlicht-Agent starten (§ 4.2)
uv run georep validate merge $V --model claude-opus-5-5   # 6. labels.csv, README.md, guete.json; committen
uv run georep validate score $V --pred <ausgabe.parquet>  # 7. Güte des Verfahrens in guete.json; committen
```

1. **Stichprobe.** Einmal je Codebuch-Version; `--force` zieht neu und trennt die vorhandenen
   Antworten von ihren Einheiten. Die Grundgesamtheit ist der Korpus oder eine Datei des
   Messskripts (`sample.population` relativ zum Profilordner, oder `--population` für eine Datei
   unter `messdaten/`). Gezogen wird ohne Zufallsgenerator (Rang SHA-256 aus Seed und Schlüssel),
   also auf jedem Rechner dieselbe Stichprobe.
2. **Aufträge.** Je Kodierer ein Ordner mit `auftrag.jsonl`, `antworten.jsonl` (leer) und
   `codebuch.md`. Beide sehen dieselben Einheiten in verschiedener Folge. Mit `text.source = "raw"`
   liest `tasks` den Rohtextstore von F1; solange es ihn nicht gibt, nennt `--texts` die Messdatei
   `messdaten/rohtext/<profil>.parquet`. `--spans` nennt Spannen außerhalb des Profilordners.
3. **Kodieren.** Zwei **frische** Agenten (Agent-Werkzeug, `subagent_type` allgemein,
   `model: "opus"`), **kein Fork**: ein Fork erbte den Kontext des Supervisors, darin die Ausgabe
   des Verfahrens und womöglich den anderen Kodierer. Beide bekommen den Prompt aus § 4.1, jeder nur
   seinen Ordner. Über 200 Einheiten oder 6 000 Zeichen je Ausschnitt teilt der Supervisor einen
   Kodierer in Läufe nach Zeilen (erst 1 bis 100, dann ein frischer Agent mit 101 bis 200), statt
   einem Agenten alles zu geben; die Rolle bleibt dieselbe, die Unabhängigkeit auch.
4. **Zusammenführen.** `merge` prüft beide Antwortdateien (jede Einheit genau einmal, jedes Label
   aus dem Codebuch) und meldet sonst Zahl und Beispiel je Fehler; dann schickt der Supervisor den
   Agenten mit dieser Zeile zurück (SendMessage). Mit Uneinigkeiten entsteht
   `schlichtung/auftrag.jsonl`: nur die strittigen Einheiten, mit beiden Labels und Begründungen.
5. **Schlichten.** Ein dritter frischer Agent mit dem Prompt aus § 4.2.
6. **Labels.** Der zweite `merge` legt `labels.csv`, `README.md` und `guete.json` ab und sagt, ob α
   die Schwelle erreicht. Liegt es darunter: die Uneinigkeiten lesen (lokal), das Codebuch
   schärfen, `version` hochzählen, neue Stichprobe — zurück in Stufe 1.
7. **Güte.** Das Verfahren schreibt seine Ausgabe für die Einheiten der Stichprobe: `id` und
   `label` (Schlüssel wie in `labels.csv`), bei Rangfolgen `query`, `id`, `score`. Für Treffer eines
   Verfahrens (Spannen, Paare), die selbst die Einheiten sind, braucht es kein `--pred`: der
   Anteil positiver Labels ist seine Präzision.
8. **Auf die Seite.** Stufe 3 liest `validierung/<NN-name>/guete.json`: `satz` (wer geprüft hat,
   an wie vielen Einheiten), die Güte mit Intervall (`positiv.wilson95`,
   `verfahren.klassifikation.klassen[].praezision_wilson95`, `…ndcg_mittel`), `alpha_genuegt`.
   Ohne `alpha_genuegt = true` zeigt die Seite die Kennzahl nicht (Plan, § 2.6). Jede Kennzahl
   nennt ihre Validierung: Stichprobengröße, Güte mit Intervall, „zwei KI-Kodierer, nicht Menschen".

Was ins Repo kommt und was nicht:

| Datei | Ort | Inhalt |
|---|---|---|
| `codebuch.toml` | `validierung/<NN-name>/` | das Instrument |
| `stichprobe.csv`, `stichprobe.json` | ebenda | Schlüssel und Schicht; Profil, Prüfsumme der Grundgesamtheit, Seed, Aufteilung |
| `labels.csv`, `README.md` | ebenda | `id, kodierer_a, kodierer_b, schlichtung, label`; Codebuch-Version, Modell, Datum, Übereinstimmung |
| `guete.json` | ebenda | Übereinstimmung, Labels, Güte des Verfahrens, der Satz für die Seite |
| `A/`, `B/`, `schlichtung/` | `validation.coding_root/<NN-name>/`, **nie im Repo** | Aufträge mit Ausschnitten aus Ratsdokumenten, Antworten mit Begründungen |

## 4. Prompt-Vorlagen

Platzhalter in spitzen Klammern; `<ordner>` ist `<coding_root>/<NN-name>/<A|B|schlichtung>`.

### 4.1 Kodier-Agent

> Du bist Kodierer <A|B> für das Vorhaben <NN-name> im Projekt „Geografische Repräsentation in
> Ratsdokumenten". Deine Aufgabe ist eine Inhaltsanalyse nach einem Codebuch, sonst nichts.
>
> Lies `<ordner>/codebuch.md` ganz. Dann arbeite `<ordner>/auftrag.jsonl` ab, je Zeile eine
> Einheit (<zeilen: alle | Zeilen a bis b>), in Blöcken von 25 Zeilen. Jede Zeile trägt die
> `frage`, je Dokument `titel` und `ausschnitt` (bei Spannen `markiert`, die Spanne zwischen ⟦ und
> ⟧), hervorgehobene `spannen` und die `optionen` mit Definition und Beispiel. Urteile nur nach dem
> Codebuch und dem Ausschnitt; was nicht im Ausschnitt steht, gibt es für dich nicht.
>
> Schreibe nach jedem Block in `<ordner>/antworten.jsonl`: in der Zeile mit derselben `id` setzt
> du `label` auf genau einen `wert` aus den Optionen und `begruendung` auf einen kurzen Satz (ohne
> längere Zitate). Ändere keine `id`, lass keine Zeile weg, füge keine hinzu. Jedes Label ist dein
> eigenes Urteil über diese eine Einheit: setze keine Labels mit einem Skript, einer Suche nach
> Wörtern oder einer Regel über viele Zeilen.
>
> Lies keine anderen Dateien: nicht das Repository, nicht `docs/`, nicht die Ordner anderer
> Kodierer, keine Ausgabe des Verfahrens, nichts im Netz. Du weißt nicht, was das geprüfte
> Verfahren sagt, und sollst es nicht wissen.
>
> Melde am Ende: Zahl der kodierten Einheiten, Verteilung der Labels, und jede `id`, bei der das
> Codebuch nicht trägt, mit einem Satz warum. Rede nicht mit dem Nutzer.

### 4.2 Schlicht-Agent

> Du schlichtest für das Vorhaben <NN-name>. Lies `<coding_root>/<NN-name>/schlichtung/codebuch.md`
> ganz. In `schlichtung/auftrag.jsonl` steht je Zeile eine Einheit, bei der zwei Kodierer
> verschieden geurteilt haben: der Auftrag wie für die Kodierer, dazu `kodierung_1` und
> `kodierung_2` mit Label und Begründung. Entscheide jede Einheit nach dem Codebuch und dem
> Ausschnitt, nicht nach der Mehrheit, der Reihenfolge oder der Länge einer Begründung; jede
> Option ist erlaubt, auch eine, die keiner der beiden gewählt hat. Schreibe in
> `schlichtung/antworten.jsonl` je Zeile `label` und einen Satz `begruendung`. Lies keine anderen
> Dateien und nichts im Netz. Melde am Ende die Zahl der Entscheidungen, wie oft du Kodierung 1,
> Kodierung 2 oder etwas Drittes gewählt hast, und welche Unschärfen im Codebuch die
> Uneinigkeiten erklären. Rede nicht mit dem Nutzer.

## 5. Die Maße

Alle stehen in `georep.validation.measures`, rein und in reinem Python (ohne numpy und
scikit-learn, das im Paket nur in zwei Modulen von `analysis/` stehen darf).

| Maß | Rechnung | geprüft gegen |
|---|---|---|
| Wilson-Intervall 95 % | (p + z²/2n ± z·√(p(1−p)/n + z²/4n²)) / (1 + z²/n), z = 1,96 | Rechnung von Hand (8 von 10: 0,4902 bis 0,9433; 0 von 10: bis 0,2775) |
| Übereinstimmung | Anteil gleicher Labels, mit Wilson | – |
| Cohens κ | (n·a − s) / (n² − s), ganzzahlig; `None`, wenn beide immer dasselbe Label geben | `sklearn.metrics.cohen_kappa_score`, auch über hypothesis |
| Krippendorffs α | Koinzidenzmatrix, nominal, ordinal, intervall, fehlende Werte erlaubt; `None` ohne Streuung | Krippendorff (2011), *Computing Krippendorff's Alpha-Reliability*: 0,095 (binär), 0,692 (nominal), 0,743 / 0,815 / 0,849 (vier Beobachter mit Lücken) |
| Präzision, Recall, F1 | je Klasse mit Wilson für Präzision und Recall; mikro = Genauigkeit (einlabelig), makro ungewichtet, undefiniert zählt 0 | `precision_recall_fscore_support` (`zero_division=0`), `confusion_matrix` |
| nDCG@k | linearer Gewinn, Σ rel/log2(i+1); nicht geurteilte Dokumente zählen 0; `None` ohne relevantes Dokument | `sklearn.metrics.ndcg_score` |

F1 und die Makromittel sind keine Anteile und haben kein Wilson-Intervall. Wer eines braucht,
zieht es im Messskript per Bootstrap über die Einheiten.

## 6. Grenzen

- Beide Kodierer sind dasselbe Modell; ihre Fehler sind korreliert, α ist darum eine obere
  Schätzung der Schärfe des Codebuchs (§ 1).
- Die verschiedene Folge der Einheiten je Kodierer mildert Reihenfolgeeffekte, schließt sie nicht
  aus.
- Der Ausschnitt ist der Anfang des Textes (`text.chars`); was dahinter steht, sehen die Kodierer
  nicht. Für Fragen über das ganze Dokument muss `chars` reichen oder die Einheit eine Spanne sein.
- Eine HTML-Ansicht für Menschen gibt es nicht, solange niemand von Hand kodiert (Plan, § 7).
