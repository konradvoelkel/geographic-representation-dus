# Validierung mit zwei KI-Kodierern (Fundament F4)

Stand 2026-11-23 (zweite Runde nach dem Review). Paket `georep.validation`, Befehl
`georep validate sample|tasks|import|merge|score`.
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

**Was die Einheiten können.** Eine Einheit ist ein Urteil über etwas Gegebenes: ein Dokument, ein
Paar, ein Paar mit Fundstelle, eine Spanne, eine Suchanfrage mit einem Dokument. Die Einheit
`marking` lässt die Kodierer dagegen alle Stellen einer Art in einem Dokument markieren (Recall,
Vorhaben 12); ihre Auswertung gegen die Spannen eines Verfahrens ist noch offen (§ 6).

## 2. Das Codebuch

Der Mess-Agent schreibt es in Stufe 1 (Messdokument, Abschnitt 4) nach
`validierung/<NN-name>/codebuch.toml`. Die Schlüssel sind englisch wie in allen TOML-Dateien des
Pakets, die Texte deutsch. pydantic prüft es (`georep.validation.codebook`); ein Fehler nennt das
Feld. Ein Codebuch hat eine oder mehrere Fragen; Übereinstimmung, Schlichtung und Labels gibt es je
Frage.

```toml
project = "11-struktur"          # der Ordnername; eine zweite Runde ist ein eigener Ordner (14-vorgaenge-2-f4)
version = "1"                    # bei jeder Änderung hochzählen; steht in Aufträgen, Antworten, README, guete.json
unit = "document"                # document | document_pair | pair_with_span | span | query_document | marking
instructions = """
Lies den Titel und den Ausschnitt. ...
"""

[[questions]]
id = "bv_vorhanden"
question = "Enthält das Dokument einen Beschlussvorschlag?"
scale = "binary"                 # nominal | ordinal (aufsteigend) | binary (genau zwei) | interval | open | spans
positive = ["ja"]                # was als Treffer zählt (Präzision, Anteil); binär genau eines
ignore = []                      # Labels, die aus dem Nenner fallen (etwa "unklar")
instructions = "Ein Text, über den abgestimmt werden soll ..."

[[questions.options]]
value = "ja"
name = ""                        # Anzeigename, wo das Label ein Kürzel ist
definition = "..."
example = "..."

[[questions.options]]
value = "nein"
definition = "..."

[[questions]]
id = "bv_erste_zeile"
question = "Erste Zeile des Beschlussvorschlags."
scale = "interval"               # eine Zahl; null heißt „nichts da"
only_if = { question = "bv_vorhanden", values = ["ja"] }   # sonst bleibt die Antwort null

[[questions]]
id = "unsicher"
question = "Ist eine der Antworten unsicher?"
scale = "binary"
positive = ["ja"]
adjudicate = false               # Meta-Frage: eine Uneinigkeit geht nicht an die Schlichtung

[sample]
size = 200
seed = 20261123
stratum = "paper_type"           # Spalte der Grundgesamtheit; leer = ungeschichtet
allocation = "proportional"      # größter Rest nach N_h; oder "equal": gleich viele je Schicht
population = ""                  # Parquet relativ zum Profilordner; leer = interim/papers.parquet
key = ""                         # Spalte, die selbst der Schlüssel ist (kante, aufgabe, paar)
strata = []
require_text = true

[text]
source = "raw"                   # corpus (kleingeschrieben) oder raw (Rohtextstore von F1)
chars = 6000                     # Ausschnitt vom Anfang des Dokuments
window = 400                     # bei einer Spanne oder Fundstelle: Zeichen vor und hinter ihr
title = true
spans = ""                       # Spannen nach F3 (georep.spans) zum Hervorheben
span_kinds = []
show_kind = false                # die Art der Spannen zeigen; nie, wenn sie die Einheiten selbst sind
context = []                     # weitere kurze Spalten im Auftrag (und in stichprobe.csv): nie Ratstext,
context_chars = 80               # nie die Ausgabe des Verfahrens; länger weist sample ab

[score]
k = 10                           # nDCG@k bei unit = "query_document"
relevance = ""                   # die Frage mit den Relevanzstufen; leer = die erste ordinale oder binäre

[provisional]                    # nur für vorläufige Antworten von vor F4 (georep validate import)
key = "aufgabe"
values = { bv_vorhanden = { "true" = "ja", "false" = "nein" } }
reason = ["begruendung", "bemerkung"]
```

| Einheit | Grundgesamtheit (Parquet) | Schlüssel `id` | im Auftrag |
|---|---|---|---|
| `document` | `id` (Standard: der Korpus) | `<id>` | Titel, Ausschnitt vom Anfang, Spannen darin |
| `document_pair` | `id_a`, `id_b` | `<id_a>\|<id_b>` | beide Dokumente |
| `pair_with_span` | `id_a`, `id_b`, `start`, `end` (dürfen leer sein) | `<id_a>\|<id_b>` | A vom Anfang, B als Fenster um die Fundstelle (⟦ ⟧ in `markiert`), ohne Fundstelle vom Anfang |
| `span` | `id`, `start`, `end`, `kind` (F3) | `<id>\|<start>\|<end>\|<kind>` | Fenster um die Spanne, die Spanne in `markiert`, nicht noch einmal unter `spannen` |
| `query_document` | `query`, `id` | `<query>\|<id>` | die Suchanfrage und das Dokument |
| `marking` | `id` | `<id>` | das Dokument; die Kodierer markieren |

Mit `sample.key` ist der Schlüssel eine Spalte der Grundgesamtheit; `stichprobe.csv` trägt dann
das Dokument als `dokument`. Bei `unit = "span"` liest `tasks` `value` und `extractor` aus der
Grundgesamtheit (sie stehen nicht in `stichprobe.csv`, `value` ist Ratstext), prüft ihre Prüfsumme
gegen `stichprobe.json`, alle Spannen mit `georep.spans.check_spans` gegen die Längen der gewählten
Textquelle und `value` gegen den Text an der Stelle: Spannen aus dem Rohtext in einem Auftrag aus
dem kleingeschriebenen Korpus säßen sonst still an der falschen Stelle.

Gute Codebücher, aus der Literatur zur Inhaltsanalyse: die Optionen schließen einander aus und
decken alles ab; jede hat eine Definition und, wo es geht, ein Beispiel aus der Ratsarbeit; die
Anweisungen sagen, was zu lesen ist und wie Grenzfälle entschieden werden („im Zweifel …"). Eine
Option „unklar" senkt α und gehört nur hinein, wenn das Vorhaben sie auswerten will (dann als
`ignore`). Ändert sich das Codebuch nach einer Kodierung, zählt `version` hoch, und die Kodierung
beginnt mit einer neuen Stichprobe in einem eigenen Ordner (Vorhaben 14: `14-vorgaenge-2-f4`): wer
das Codebuch an den Uneinigkeiten derselben Einheiten schärft und sie dann neu kodieren lässt,
misst seine eigene Anpassung.

Antworten werden kanonisch verglichen: Optionen als Label, Zahlen ohne überflüssige
Nachkommastellen, offene Werte als JSON mit sortierten Schlüsseln und zu einem Leerzeichen
zusammengezogenem Leerraum; ein leerer Text gilt wie `null`. „66 - Amt" und „66-Amt" sind damit
verschieden (§ 6).

## 3. Der Ablauf für den Supervisor

Auf Konrads Rechner liegen die Aufträge auf xtraspace; einmal in `settings.local.toml` (des
Hauptklons und jedes Worktrees, der validiert):

```toml
validation.coding_root = "/media/konrad/xtraspace/georep/messdaten/kodierung"
```

Ein gesetztes `coding_root` muss absolut sein und außerhalb des Arbeitsbaums liegen; ohne Eintrag
liegen die Aufträge unter `<data_root>/kodierung/` (gitignored).

```bash
V=11-struktur
uv run georep validate sample $V                     # 1. Stichprobe; stichprobe.csv und .json committen
uv run georep validate tasks $V --coder A            # 2. Aufträge, lokal
uv run georep validate tasks $V --coder B
#                                                      3. zwei Kodier-Agenten starten (§ 4.1), parallel
uv run georep validate merge $V --model claude-opus-5-5   # 4. Uneinigkeiten -> Auftrag der Schlichtung
#                                                      5. Schlicht-Agent starten (§ 4.2)
uv run georep validate merge $V --model claude-opus-5-5   # 6. labels.csv, README.md, guete.json; committen
uv run georep validate score $V [--pred <ausgabe.parquet>]  # 7. Treffer und Güte in guete.json; committen
```

1. **Stichprobe.** Einmal je Codebuch-Version; `--force` zieht neu und trennt die vorhandenen
   Antworten von ihren Einheiten. Gezogen wird ohne Zufallsgenerator (Rang SHA-256 aus Seed und
   Schlüssel), also auf jedem Rechner dieselbe Stichprobe. Jede Zeile trägt die Größe ihrer
   Schicht (`schicht_n`); `stichprobe.json` sagt, ob die Stichprobe selbstgewichtend ist.
2. **Aufträge.** Je Kodierer ein Ordner mit `auftrag.jsonl` (je Einheit die Fragen, Dokumente,
   Spannen), `antworten.jsonl` (je Einheit `id`, `codebuch_version`, je Frage `null`,
   `begruendung`) und `codebuch.md`. Beide sehen dieselben Einheiten in verschiedener Folge.
3. **Kodieren.** Zwei **frische** Agenten (Agent-Werkzeug, `model: "opus"`), **kein Fork**: ein
   Fork erbte den Kontext des Supervisors, darin die Ausgabe des Verfahrens. Über 200 Einheiten
   oder 6 000 Zeichen je Ausschnitt teilt der Supervisor einen Kodierer in Läufe nach Zeilen.
4. **Zusammenführen.** `merge` prüft beide Antwortdateien (jede Einheit genau einmal, dieselbe
   `codebuch_version`, jede gestellte Frage beantwortet, keine nicht gestellte) und meldet sonst
   Zahl und Beispiel je Fehler. Mit Uneinigkeiten entsteht `schlichtung/auftrag.jsonl`: je Einheit
   die strittigen Fragen (`strittig`) und beide Kodierungen in einer je Einheit festen, aber
   wechselnden Folge. Haben A oder B danach neu kodiert, passt die Schlichtung nicht mehr; `merge`
   bricht dann ab, `merge --force` setzt `schlichtung/` zurück.
5. **Schlichten.** Ein dritter frischer Agent mit dem Prompt aus § 4.2.
6. **Labels.** Der zweite `merge` legt `labels.csv` (`id, frage, kodierer_a, kodierer_b,
   schlichtung, label`), `README.md` und `guete.json` ab und sagt je Frage, ob α die Schwelle
   erreicht. Liegt es darunter: das Codebuch schärfen, `version` hochzählen, neue Stichprobe.
7. **Güte.** Ohne `--pred` je Frage mit `positive` der Anteil der Treffer: je Schicht, in der
   Stichprobe und für die Grundgesamtheit (§ 5). Mit `--pred` die Ausgabe eines Verfahrens: `id`,
   `frage`, `label` (bei einem Codebuch mit einer Frage darf `frage` fehlen), bei Rangfolgen
   `query`, `id`, `score`.
8. **Auf die Seite.** Stufe 3 liest `validierung/<NN-name>/guete.json`: `satz` (wer geprüft hat,
   an wie vielen Einheiten), je Frage `alpha_genuegt` und die Güte mit Intervall
   (`fragen.<frage>.treffer.grundgesamtheit`, `…verfahren`). Ohne `alpha_genuegt = true` zeigt die
   Seite die Kennzahl nicht (Plan, § 2.6); eine gewichtete Schätzung heißt auf der Seite so.

**Vorläufige Antworten** (Vorhaben 11 bis 14 kodierten vor F4): `[provisional]` im Codebuch sagt,
wie ihre Dateien zu lesen sind (Schlüsselfeld; Felder, die anders heißen; Werte, die ein Label
werden; Schlichtung je Feld in langer Form oder verschachtelt). `georep validate import <V> --from
<ordner>` schreibt daraus die Antworten im Format von F4, ohne die Quelldateien zu ändern; danach
geht es mit `merge` weiter. Für Vorhaben 14 rechnet das die Zahlen des Messdokuments nach
(`tests/unit/test_validation_projects.py`).

**Wo die übertragenen Vorhaben liegen.** Die Messskripte der Vorhaben 11 bis 14
(`docs/plans/*-messung.py`) lesen die vorläufigen Dateien unter `validierung/<NN-name>/` und
prüfen, dass die gespeicherten Stichproben unverändert sind. Das Format von F4 liegt darum daneben,
in `validierung/<NN-name>-f4/` (Runde 2 von 14: `14-vorgaenge-2-f4`, die Recall-Aufgaben von 12:
`12-kennungen-recall-f4`); die alten Ordner bleiben, wie die Messung sie geschrieben hat. Ein neues
Vorhaben legt sein Codebuch gleich im Format von F4 an und braucht kein `-f4`.

Was ins Repo kommt und was nicht:

| Datei | Ort | Inhalt |
|---|---|---|
| `codebuch.toml` | `validierung/<NN-name>/` | das Instrument |
| `stichprobe.csv`, `stichprobe.json` | ebenda | Schlüssel, Schicht, `schicht_n`; Profil, Prüfsumme der Grundgesamtheit, Seed, Aufteilung |
| `labels.csv`, `README.md` | ebenda | `id, frage, kodierer_a, kodierer_b, schlichtung, label`; Codebuch-Version, Modell, Datum, Übereinstimmung je Frage |
| `guete.json` | ebenda | Übereinstimmung, Labels, Treffer, Güte des Verfahrens je Frage, der Satz für die Seite |
| `A/`, `B/`, `schlichtung/` | `validation.coding_root/<NN-name>/`, **nie im Repo** | Aufträge mit Ausschnitten aus Ratsdokumenten, Antworten mit Begründungen |

## 4. Prompt-Vorlagen

Platzhalter in spitzen Klammern; `<ordner>` ist `<coding_root>/<NN-name>/<A|B|schlichtung>`.

### 4.1 Kodier-Agent

> Du bist Kodierer <A|B> für das Vorhaben <NN-name> im Projekt „Geografische Repräsentation in
> Ratsdokumenten". Deine Aufgabe ist eine Inhaltsanalyse nach einem Codebuch, sonst nichts.
>
> Lies `<ordner>/codebuch.md` ganz. Dann arbeite `<ordner>/auftrag.jsonl` ab, je Zeile eine
> Einheit (<zeilen: alle | Zeilen a bis b>), in Blöcken von 25 Zeilen. Jede Zeile trägt die
> `fragen` (mit Skala, Anleitung, Optionen und, wo es eine gibt, der Bedingung `nur_wenn`), je
> Dokument `titel` und `ausschnitt` (bei einer Spanne oder Fundstelle `markiert`, die Stelle
> zwischen ⟦ und ⟧) und hervorgehobene `spannen`. Urteile nur nach dem Codebuch und dem
> Ausschnitt; was nicht im Ausschnitt steht, gibt es für dich nicht.
>
> Schreibe nach jedem Block in `<ordner>/antworten.jsonl`: in der Zeile mit derselben `id` setzt
> du je Frage den Wert (bei Optionen genau einen `wert`; eine Frage, deren Bedingung nicht erfüllt
> ist, bleibt `null`) und `begruendung` auf einen kurzen Satz (ohne längere Zitate). Ändere keine
> `id` und keine `codebuch_version`, lass keine Zeile weg, füge keine hinzu. Jede Antwort ist dein
> eigenes Urteil über diese eine Einheit: setze keine Werte mit einem Skript, einer Suche nach
> Wörtern oder einer Regel über viele Zeilen.
>
> Lies keine anderen Dateien: nicht das Repository, nicht `docs/`, nicht die Ordner anderer
> Kodierer, keine Ausgabe des Verfahrens, nichts im Netz. Du weißt nicht, was das geprüfte
> Verfahren sagt, und sollst es nicht wissen.
>
> Melde am Ende: Zahl der kodierten Einheiten, Verteilung der Antworten je Frage, und jede `id`,
> bei der das Codebuch nicht trägt, mit einem Satz warum. Rede nicht mit dem Nutzer.

### 4.2 Schlicht-Agent

> Du schlichtest für das Vorhaben <NN-name>. Lies `<coding_root>/<NN-name>/schlichtung/codebuch.md`
> ganz. In `schlichtung/auftrag.jsonl` steht je Zeile eine Einheit, bei der zwei Kodierer bei
> mindestens einer Frage verschieden geurteilt haben: der Auftrag wie für die Kodierer, dazu
> `strittig` (die Fragen) und `kodierung_1`, `kodierung_2` mit allen Antworten und der Begründung.
> Beantworte jede strittige Frage nach dem Codebuch und dem Ausschnitt, nicht nach der Mehrheit,
> der Reihenfolge oder der Länge einer Begründung; jede Option ist erlaubt, auch eine, die keiner
> der beiden gewählt hat, und eine Frage, deren Bedingung nach deiner Antwort nicht mehr erfüllt
> ist, bleibt `null`. Schreibe in `schlichtung/antworten.jsonl` je Zeile die Werte der strittigen
> Fragen (die übrigen bleiben `null`) und einen Satz `begruendung`. Lies keine anderen Dateien und
> nichts im Netz. Melde am Ende die Zahl der Entscheidungen, wie oft du Kodierung 1, Kodierung 2
> oder etwas Drittes gewählt hast, und welche Unschärfen im Codebuch die Uneinigkeiten erklären.
> Rede nicht mit dem Nutzer.

## 5. Die Maße

Alle stehen in `georep.validation.measures`, rein und in reinem Python (ohne numpy und
scikit-learn, das im Paket nur in zwei Modulen von `analysis/` stehen darf).

| Maß | Rechnung | geprüft gegen |
|---|---|---|
| Wilson-Intervall 95 % | (p + z²/2n ± z·√(p(1−p)/n + z²/4n²)) / (1 + z²/n), z = 1,96 | Rechnung von Hand (8 von 10: 0,4902 bis 0,9433; 0 von 10: bis 0,2775) |
| Übereinstimmung | Anteil gleicher Antworten unter den Einheiten, wo beide geantwortet haben, mit Wilson | – |
| Cohens κ | (n·a − s) / (n² − s), ganzzahlig; `None`, wenn beide immer dasselbe Label geben | `sklearn.metrics.cohen_kappa_score`, auch über hypothesis |
| Krippendorffs α | Koinzidenzmatrix, nominal, ordinal, intervall, fehlende Werte erlaubt (eine nicht gestellte Frage fehlt); `None` ohne Streuung; Stufe 3 misst ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal | Krippendorff (2011): 0,095 (binär), 0,692 (nominal), 0,743 / 0,815 / 0,849 (vier Beobachter mit Lücken) |
| Präzision, Recall, F1 | je Klasse mit Wilson für Präzision und Recall; mikro = Genauigkeit (einlabelig); makro ungewichtet über die Klassen mit Gold oder Vorhersage | `precision_recall_fscore_support`, `confusion_matrix` |
| Treffer, geschichtet | Σ_h W_h·x_h/m_h mit W_h = N_h/N; Intervall nach Wilson bei Kishs n_eff = N² / Σ_h N_h²/m_h | Vorhaben 14: 0,922 (Runde 1), 0,840 (Runde 2) wie im Messdokument; selbstgewichtend gleich dem einfachen Anteil (hypothesis) |
| nDCG@k | über die geurteilten Dokumente (condensed list, Sakai 2007), Gleichstände gemittelt, linearer Gewinn; `None` ohne relevantes Dokument; dazu judged@k | `sklearn.metrics.ndcg_score`, auch mit Gleichständen |

**Warum Wilson mit Kishs effektivem n für die geschichtete Schätzung** (Review 2026-11-23,
Befund 1). Drei Wege lagen nahe. Ein geschichteter Bootstrap (Ziehen mit Zurücklegen je Schicht)
gibt für eine Schicht, in der alle Einheiten Treffer sind, keine Streuung, und genau solche
Schichten sind bei Präzisionen um 0,95 die Regel; das Intervall würde zu schmal, und es hinge am
Zufall. Die Normalnäherung mit der geschichteten Varianz Σ W_h² p_h(1−p_h)/m_h hat dasselbe
Problem und reicht nahe 1 über 1 hinaus. Wilson bei n_eff = (Σ w)²/Σ w² (Kish 1965) bleibt in
[0, 1], ist geschlossen und ohne Zufall, verliert nicht seine Breite, wenn Schichten rein sind,
und fällt bei einer selbstgewichtenden Stichprobe genau auf das einfache Wilson-Intervall zurück.
Es nimmt an, dass die Streuung in allen Schichten ähnlich ist; ungleiche Gewichte kosten effektive
Stichprobengröße (Vorhaben 14, Runde 1: 150 Kanten, n_eff 45,8, weil eine Schicht mit 47 % der
Kanten nur 13 trägt).

F1 und die Makromittel sind keine Anteile und haben kein Wilson-Intervall. Wer eines braucht,
zieht es im Messskript per Bootstrap über die Einheiten.

## 6. Grenzen und Offenes

- Beide Kodierer sind dasselbe Modell; ihre Fehler sind korreliert, α ist darum eine obere
  Schätzung der Schärfe des Codebuchs (§ 1).
- Die verschiedene Folge der Einheiten je Kodierer mildert Reihenfolgeeffekte, schließt sie nicht
  aus.
- Offene Antworten werden bis auf zusammengezogenen Leerraum genau verglichen. Die vorläufigen
  Auswertungen der Vorhaben 11 und 12 entfernten Leerraum ganz und zählten „66 - Amt" und
  „66-Amt" als gleich; nach F4 sind das zwei Uneinigkeiten für die Schlichtung (11: zwei bei
  `amt`; 12: vier bei `norm` und `text_korrigiert`).
- Die Einheit `marking` (Recall, Vorhaben 12) hat Codebuch, Stichprobe und Antworten, aber noch
  keine Auswertung: die Markierungen beider Kodierer abgleichen und gegen die Spannen des
  Verfahrens mit strenger (gleiche Grenzen und Art) und milder Grenze (Überlappung und Art)
  zählen.
- Die Vorhaben 15 und 17 kamen nach der zweiten Runde von F4 und sind noch im vorläufigen Format.
- Der Ausschnitt ist der Anfang des Textes (`text.chars`); was dahinter steht, sehen die Kodierer
  nicht.
- Eine HTML-Ansicht für Menschen gibt es nicht, solange niemand von Hand kodiert (Plan, § 7).
