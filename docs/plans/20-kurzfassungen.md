# Vorhaben 20: Kurzfassungen

Stand 2026-11-23, Stufe 1 (Messen), Branch `feat/20-kurzfassungen`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „20 Kurzfassungen".
Messskript: [20-kurzfassungen-messung.py](20-kurzfassungen-messung.py). Codebuch und Stichproben
(nur IDs): [../../validierung/20-kurzfassungen/](../../validierung/20-kurzfassungen/).

**Dieser Stand ist die Festlegung vor der Messung** (§ 3.1): Prompt, Modelle, Eingabe,
Treueprüfung, Kriterium und Regel der Hochrechnung stehen fest, bevor die erste Kurzfassung
entsteht. Die Ergebnisse folgen in einem späteren Commit; was hier steht, wird danach nicht
geändert, nur ergänzt.

**Kurzfassungen kommen nicht ins Repo und nicht auf die Seite** (Konrad, 2026-11-23, Meta-Plan
§ 10, Frage 6). Sie liegen im Modellcache von F5 (`cache_root/ml/`) und als Auszug unter
`/media/konrad/xtraspace/georep/messdaten/20-kurzfassungen/`. Ins Repo kommen dieses Dokument, das
Skript, das Codebuch, die Stichproben (nur IDs), Labels (nur Codes und Zahlen) und Zählungen, kein
Satz aus einer Kurzfassung, auch nicht als Beispiel.

## 1. Frage und Nutzen

Zwei, drei Sätze je Dokument (und versuchsweise je Vorgang): wer will was, worum geht es, was ist
der Kern des Beschlussvorschlags, der Fragen oder der Mitteilung. **Ratsarbeit**: der
Vorlagenspiegel einer Fraktion liest heute je Sitzung Dutzende Vorlagen an; eine treue Kurzfassung
spart das erste Lesen, eine untreue kostet Vertrauen in alles andere. Darum zählt hier zuerst die
Treue, dann der Nutzen. **Literatur**: MeetingBank (Hu u. a. 2023)* zeigt, dass Zusammenfassungen
kommunaler Sitzungen mit kleinen Modellen messbar, aber oft untreu sind; der Maßstab dieses
Vorhabens ist darum eine deterministische Prüfung jeder Zahl und jedes Namens, nicht eine
Ähnlichkeit zu einer Referenz.

## 3. Messung

### 3.1 Vorab festgelegt (2026-11-23, 22:45, vor der ersten Kurzfassung)

**Stichprobe.** Grundgesamtheit: die Dokumente der Hauptperiode mit nicht leerem Rohtext (19 032;
Korpus `interim/papers.parquet` über `file_name` an die Messdatei `messdaten/rohtext/duesseldorf.parquet`).
Schichten: Dokumentart (zwölf Arten nach `Rules.art` aus Vorhaben 11) × Länge des Rohtexts (kurz
unter 1 500 Zeichen, mittel unter 5 000, lang ab 5 000): 33 belegte Schichten. **200 Dokumente**,
proportional mit größtem Rest und mindestens einem je Schicht (`allocate` aus F4), je Schicht die
kleinsten Ränge SHA-256 über Seed 2026112320 und ID (`rank` aus F4). Die Stichprobe ist nicht
selbstgewichtend; Anteile werden geschichtet geschätzt (Σ W_h·x_h/m_h, Wilson bei Kishs n_eff, wie
F4). Datei: `validierung/20-kurzfassungen/stichprobe200.csv` (id, art, laenge, schicht, schicht_n).
**Die 50 für die Bewertung**: aus den 200, proportional nach Dokumentart, Seed 2026112321
(`stichprobe.csv`, `stichprobe.json` im Format von F4).

**Eingabe, Fassung 1.** Was ein Modell als Dokument sieht (`eingabe` im Skript):

- vier Kopfzeilen: `Dokumentart:` (OParl `paperType`, wörtlich), `Drucksache:`, `Datum:` (TT.MM.JJJJ),
  `Titel:` (OParl `name`);
- die Abschnitte aus dem Regelwerk von Vorhaben 11 (`11-struktur-messung.py`, Profilblock
  `duesseldorf`, als Modul geladen) in dieser Folge, je mit Überschrift `## …`: Betreff,
  Beschlussvorschlag, Fragen, Sachdarstellung, Begründung, Stellungnahme der Verwaltung, Zitierter
  Beschluss, Finanzen, Klima, Alternative. Kopf, Beratungsfolge, Anlagen und „Nachrichtlich" bleiben
  draußen; ein Abschnitt der Ebene 2 im Text eines schon genommenen Abschnitts wird übersprungen;
- der Abschnittstext wird gesäubert (Seitenwechsel zu Zeilen, Silbentrennung am Zeilenende weg,
  Leerraum je Zeile zusammengezogen) und füllt in dieser Folge ein **Budget von 8 000 Zeichen**; der
  Abschnitt, der das Budget sprengt, endet am letzten Zeilen- oder Wortende davor mit „[…]", danach
  kommt nichts mehr (`gekuerzt`);
- **Rückfall**: findet das Regelwerk keinen Kernabschnitt (Beschlussvorschlag, Fragen,
  Sachdarstellung, Begründung, Stellungnahme), steht nach dem Betreff der Rohtext ab dem Ende des
  Kopfs unter `## Text`, im selben Budget. An der Stichprobe: 180 Eingaben aus Abschnitten, 20 aus
  dem Rückfall, 8 gekürzt, Abschnittstext im Median 1 335 Zeichen.

**Prompt, Fassung 1** (`PROMPT_VERSION = "20-kurzfassung-1"`), Systemnachricht:

> Du schreibst Kurzfassungen von Dokumenten aus dem Ratsinformationssystem einer deutschen Stadt für
> Ratsmitglieder. Du schreibst sachlich und neutral auf Deutsch und gibst nur wieder, was im Dokument
> steht.

Nachricht (danach folgt die Eingabe):

> Fasse das Dokument unten in zwei bis drei Sätzen zusammen, zusammen höchstens 80 Wörter.
>
> Regeln:
> 1. Der erste Satz sagt, wer was will oder mitteilt (wer beantragt, beschließen lassen will, fragt
>    oder berichtet) und worum es geht.
> 2. Danach das Wesentliche: der Kern des Beschlussvorschlags, der Fragen oder der Mitteilung, dazu
>    Ort, Betrag und Frist, wenn das Dokument sie nennt.
> 3. Zahlen, Beträge, Daten, Drucksachennummern und Namen nur, wenn sie im Dokument stehen, und genau
>    so geschrieben wie dort.
> 4. Füge nichts hinzu, was nicht im Dokument steht: kein Wissen von außen, keine Bewertung, keine
>    Vermutung.
> 5. Keine Personennamen; nenne Personen nach ihrer Rolle (etwa „die Verwaltung", „die Fraktion",
>    „die Bezirksvertretung").
> 6. Antworte nur mit der Kurzfassung als Fließtext, ohne Überschrift, ohne Aufzählung, ohne
>    Einleitung.
>
> Dokument:

**Modelle und Optionen.** Beide an denselben 200 Eingaben mit demselben Prompt, über die Naht von F5
(`GenerationUse`, `generate_texts`, Modellcache unter `cache_root/ml/`), Optionen aus
`[ml.generation]`: Temperatur 0, Seed 0, `num_ctx` 8192, `num_predict` 512, `think` aus.

| Modell | Digest (`/api/tags`, 2026-11-23) | Parameter, Quantisierung |
|---|---|---|
| `qwen3.6:27b` | `a50eda8ed977ab48a12431878896b27ffd5cef552c17af3317d9623b939a7f1e` | 27,8 B, Q4_K_M |
| `gemma4:latest` | `c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb` | 8,0 B, Q4_K_M |

Jeder GPU-Lauf unter der Sperre der Warteschlange (`flock …/gpu-queue/gpu.lock`), je Lauf höchstens
28 Minuten, fortsetzbar über den Cache; je Aufruf werden Eingabe- und Ausgabetoken, die Sekunden des
Servers, das Laden und die Wanduhr mitgeschrieben, je Lauf das Lastmittel (`os.getloadavg`) und der
Grafikspeicher am Anfang und am Ende.

**Treueprüfung** (deterministisch, `angaben` und `pruefe` im Skript; Selbsttest an 14 erfundenen
Fällen mit `selbsttest`). Geprüft wird jede **Angabe** der Kurzfassung gegen ihre **Eingabe** (die
Kopfzeilen und Abschnitte, die das Modell sah; nicht gegen das ganze Dokument, denn was das Modell
nicht sah, kann es nur erfunden haben). Vier Klassen, in dieser Folge erkannt (was eine Klasse
nimmt, ist für die folgenden verdeckt):

1. **Drucksachennummer**: `KÜRZEL[NR]/Nummer/Jahr[/Nachtrag]` (Kürzel in Großbuchstaben, Leerraum um
   die Schrägstriche erlaubt) und die alte Form `Amt/ Nummer/Jahr`. Normalisiert: ohne Leerraum,
   groß, Zahlen ohne führende Nullen. Belegt, wenn dieselbe Nummer in der Eingabe steht; dort zählt
   jede Endung einer Buchstabenfolge vor der Nummer als Kürzel (pypdf klebt „VorlageBV6/…").
2. **Datum**: `TT.MM.JJJJ`, `TT.MM.JJ`, `TT. Monat JJJJ` (auch abgekürzte Monate), `JJJJ-MM-TT`,
   `Monat JJJJ`, `TT.MM.` und `TT. Monat` ohne Jahr. Normalisiert zu (Tag, Monat, Jahr). Belegt, wenn
   die Eingabe dasselbe Datum in irgendeiner dieser Formen nennt; „Monat Jahr" gilt, wenn ein Datum
   oder eine Monatsangabe der Eingabe Monat und Jahr trägt; ein Datum ohne Jahr, wenn Tag und Monat
   vorkommen. Ein Jahr allein ist eine Zahl.
3. **Zahl**: jede in Ziffern geschriebene Zahl (Tausenderpunkt, schmales Leerzeichen oder Leerzeichen
   vor drei Ziffern, Dezimalkomma), mit Einheit „Tsd.", „Tausend", „T€", „TEUR", „Mio.", „Million(en)",
   „Mrd.", „Milliarde(n)"; Uhrzeiten (`17:30 Uhr`, `17.30 Uhr`, `17 Uhr`); die Zahlwörter zwei bis
   zwölf, zwanzig, dreißig, hundert. Normalisiert zum Wert (1.500.000,00 € = 1,5 Mio. €). Belegt, wenn
   der Wert oder der skalierte Wert unter den Werten der Eingabe ist; dort zählen alle Zahlen, auch
   die Teile von Daten und Nummern, mit und ohne Einheit, und die Zahlwörter. **Eine Rundung ist
   unbelegt** (Regel 3 des Prompts); wie viele unbelegte Zahlen ein Rundungswort tragen und höchstens
   5 % neben einer Zahl der Eingabe liegen, wird daneben berichtet, ändert das Urteil aber nicht.
4. **Eigenname**, fünf Erkennungen:
   a. **Kürzel**: ein Wort mit mindestens zwei Großbuchstaben (CDU, ÖPNV, KiTa) oder Großbuchstaben
      mit Ziffern (BV 6), ohne römische Zahlen und EUR/TEUR. Belegt, wenn es in der Eingabe steht
      (ab drei Buchstaben auch in einem längeren Wort, ein Plural-s abgestreift), oder wenn sein Name
      dasteht: „BV n" ↔ „Bezirksvertretung n", ein Ausschusskürzel ↔ sein Name aus `[bodies]` des
      Profils.
   b. **Ortsname** aus dem Wörterbuch der Pipeline (`combined_searchdict.parquet`, Straßen und Orte
      aller 41 Wahlbezirke, ab vier Zeichen), klein und an Wortgrenzen gesucht.
   c. (entfällt: Straßennamen mit Endung wie „-straße" sind entweder im Wörterbuch oder fallen unter e)
   d. **Person**: das Wort nach „Herr(n)", „Frau", „Dr.", „Prof.".
   e. **Seltenes Wort**: jedes übrige großgeschriebene Wort (auch am Satzanfang, auch mit Bindestrich),
      dessen Kleinform in **weniger als 1 %** der 19 033 Korpusdokumente mit Text vorkommt (Zählung
      über den kleingeschriebenen Korpustext; bei Bindestrichen muss jeder Teil selten sein oder das
      Ganze). Häufige Wörter (Verwaltung, Antrag, Bezirksvertretung, Düsseldorf) werden nicht
      geprüft.

   Belegt (b, d, e), wenn der Name in der Eingabe steht: klein, Leerraum zusammengezogen, auch ohne
   jeden Leerraum (pypdf trennt und klebt), „Str." gleich „Straße", „ß" gleich „ss"; bei d und e
   auch gebeugt oder als Teil eines längeren Wortes (Endungen -ern, -en, -er, -es, -e, -n, -s
   abgestreift, Stamm ab vier Zeichen).

Eine Kurzfassung ist **ohne unbelegte Angabe**, wenn keine ihrer Angaben unbelegt ist. Eine leere
oder an `num_predict` abgeschnittene Antwort besteht nie, ebenso ein Dokument, für das ein Modell
keine Antwort gab. Was die Prüfung nicht sieht: Sachverhalte ohne Zahl und Namen (eine falsche
Rolle, eine erfundene Wirkung), Zahlwörter über den genannten, häufige Namen. Das misst die
Bewertung (Frage `unbelegt` im Codebuch), und der Vergleich beider ist Teil der Messung (§ 4).

**Kriterium** (Briefing, unverändert), je Modell:

1. **Treue**: der geschichtete Anteil der 200 Kurzfassungen ohne unbelegte Angabe ist **≥ 0,98**
   (Punktschätzung; das Intervall steht daneben und entscheidet nicht, denn bei n = 200 läge die
   Untergrenze nur ohne jeden Fehler über 0,98).
2. **Bewertung**: an den 50 der Kodierung ist der **Median** des geschlichteten Labels **≥ 4** in
   jeder der drei Dimensionen Treue, Vollständigkeit, Verständlichkeit; gezählt nur, wenn Krippendorffs
   α (ordinal) zwischen den Kodierern ≥ 0,8 ist (F4), sonst geht das Codebuch zurück.

Ein Modell besteht, wenn beides gilt. **Bestehen beide**, baut Stufe 2 mit dem schnelleren
(`gemma4`), außer `qwen3.6:27b` ist in 1. um mindestens 2 Prozentpunkte oder in einem Median um
mindestens 0,5 besser. **Besteht eines**, dieses. **Besteht keines**: umbauen (eine Runde, Prompt
Fassung 2 an einer frischen Stichprobe), wenn die unbelegten Angaben einer Klasse gehäuft sind, die
ein Prompt beheben kann; sonst verwerfen. Solange die Kodierung aussteht, ist das Urteil über 1.
vorläufig.

**Hochrechnung und welche Perioden laufen.** Je Modell eine Gerade „Sekunden je Dokument (Wanduhr
ohne Laden) = a + b · Zeichen des Abschnittstexts" aus den 200 Aufrufen; für jede Periode die
Eingaben nach demselben Regelwerk (Profilblöcke `duesseldorf`, `duesseldorf-2014`,
`moenchengladbach` aus Vorhaben 11) und daraus die Summe in GPU-Stunden. Geprüft in der Folge
**laufende Periode 2025–** (der Vorlagenspiegel von Vorhaben 29 braucht sie zuerst), **Hauptperiode**,
**Mönchengladbach**, **2014–2020**: eine Periode läuft ganz, wenn sie höchstens **12 GPU-Stunden**
braucht und die Summe aller laufenden höchstens **36 GPU-Stunden** bleibt; sonst als **Auswahl**
(Arten mit Beschlussvorschlag oder Fragen: Beschlussvorlagen aller Formen, A+F- und Bedarfsbeschluss,
Anträge, Haushaltsanträge, Anfragen), wenn die Auswahl in beide Grenzen passt; sonst nicht. Gerechnet
wird mit dem Modell, das nach dem Kriterium gewählt ist.

**Bewertung (F4).** Die 50 werden von zwei Kodier-Agenten nach `codebuch.toml` (Fassung 1) bewertet:
je Dokument drei Kurzfassungen K1 bis K3 ohne Modellnamen, nämlich `qwen3.6:27b`, `gemma4` und eine
**Maßstab-Kurzfassung eines Opus-Agenten**, der nur die Eingabe und dieselbe Anweisung sieht. Die
Zuordnung von K1 bis K3 ist je Dokument zufällig (Seed 2026112322) und für beide Kodierer gleich,
damit die Übereinstimmung je Frage dieselbe Quelle vergleicht; sie liegt nur unter
`messdaten/20-kurzfassungen/zuordnung.json`. Der Maßstab ist so zugleich Obergrenze auf derselben
Skala und Gegenprobe der deterministischen Prüfung (wie oft beanstandet sie eine Kurzfassung des
stärkeren Modells).

**Daneben berichtet, nicht Kriterium**: Länge (Sätze, Wörter), Rundungen (oben), die Durchsicht der
beanstandeten Angaben durch den Mess-Agenten (echte unbelegte Angabe oder Fehlalarm der Prüfung) —
ändert sie das Urteil, entscheidet der Supervisor.
