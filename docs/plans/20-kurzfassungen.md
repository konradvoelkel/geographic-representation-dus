# Vorhaben 20: Kurzfassungen

Stand 2026-11-23, Stufe 1 (Messen), Branch `feat/20-kurzfassungen`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „20 Kurzfassungen".
Messskript: [20-kurzfassungen-messung.py](20-kurzfassungen-messung.py). Codebuch und Stichproben
(nur IDs): [../../validierung/20-kurzfassungen/](../../validierung/20-kurzfassungen/).

**Urteil (Stufe 1, 2026-11-23): nach der Festlegung nicht bestanden, weil das Instrument fehlerhaft ist —
umbauen, eine Runde, an der Treueprüfung, nicht am Prompt** (§ 5). Prompt, Modelle, Eingabe,
Prüfung, Kriterium und Regel der Hochrechnung standen vor der ersten Kurzfassung fest (§ 3.1,
Commit `6e7b966`); danach ist dort nur die Uhrzeit berichtigt. Die Bewertung durch zwei
Kodier-Agenten (Teil 2 des Kriteriums) ist vorbereitet, nicht gelaufen (§ 4).

Die drei Zahlen, auf die es ankommt:

1. **Nach der vorab festgelegten Prüfung besteht keines der Modelle**: ohne unbelegte Angabe sind
   geschichtet 51,6 % der Kurzfassungen von `qwen3.6:27b` und 68,9 % von `gemma4` (Kriterium 98 %).
   **Jede Beanstandung bis auf eine liegt in der Klasse „seltenes großgeschriebenes Wort"**, und die
   misst deutsche Substantive (Abstrakta, Zusammensetzungen), nicht Eigennamen: von 228
   Beanstandungen ist von Hand genau eine ein Eigenname, der nicht in der Eingabe steht.
2. **In den Klassen, die die Prüfung trägt, sind beide fast fehlerfrei**: 0 unbelegte Zahlen,
   Daten und Drucksachennummern bei qwen (519 geprüft), eine bei gemma (597 geprüft, eine selbst
   gerechnete, richtige Summe); nach der Durchsicht echte unbelegte Angaben bei **qwen 0 von 200, bei
   gemma 2 von 200**.
3. **Durchsatz auf der 4090**: qwen 2,98 s je Dokument (40 Token/s Ausgabe), gemma 1,09 s (131
   Token/s), nach der festgelegten Rechnung ohne Laden; die Hauptperiode kostet **15,8 GPU-Stunden
   mit qwen und 5,8 mit gemma** (mit der vollen Wanduhr je Aufruf 17,3 und 8,8), alle vier Perioden
   37,6 und 13,8 (41,2 und 21,0). Frage 13: nicht 50 bis 60. Mit gemma laufen nach der Regel alle
   vier Perioden, in beiden Rechnungen; mit qwen fiele die Hauptperiode heraus.

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
Treue, dann der Nutzen. **Literatur**: MeetingBank (Hu u. a. 2023)* ist ein Maßstab für
Zusammenfassungen von Stadtratssitzungen, gemessen an Referenzen; hier gibt es keine Referenz, der
Maßstab ist darum eine deterministische Prüfung jeder Zahl und jedes Namens und eine Bewertung
nach Codebuch (§ 4), nicht eine Ähnlichkeit zu einer Musterlösung.

## 2. Datenlage

| Datei | Inhalt |
|---|---|
| `messdaten/rohtext/duesseldorf.parquet` | Rohtext der Hauptperiode (pypdf 7.1.0, Groß- und Kleinschreibung, Zeilen, Seiten mit `\f`), 19 092 PDFs; Spalten `name`, `text`, `pages`, `chars` |
| `data/duesseldorf/interim/papers.parquet` | Korpus nach `georep run` im Worktree: `id`, `name` (Titel), `reference`, `date`, `paper_type`, `file_name` (Schlüssel zur Messdatei), `text` (kleingeschrieben, nur für die Wortverbreitung) |
| `data/duesseldorf/processed/combined_searchdict.parquet` | Ortsnamen der 41 Wahlbezirke (Straßen, Orte, Einrichtungen): 5 727 ab vier Zeichen |
| `docs/plans/11-struktur-messung.py` | Regelwerk der Abschnitte (Profilblöcke `duesseldorf`, `duesseldorf-2014`, `moenchengladbach`), als Modul geladen |
| `[bodies]` des Profils | 15 Gremienkürzel mit Namen; `BV n` ↔ „Bezirksvertretung n" |
| `messdaten/rohtext/{2025,2014-2020,moenchengladbach}.parquet` und die `papers.jsonl` der Pakete | nur für die Hochrechnung (Länge der Eingaben je Periode) |

Ausgaben **im Repo** (`validierung/20-kurzfassungen/`, nur IDs, Codes, Zahlen): `stichprobe200.csv`,
`stichprobe.csv` und `stichprobe.json` (die 50, Format F4), `codebuch.toml`, `treue.csv` (je Dokument
und Modell die Zahl der Angaben und der unbelegten je Klasse, `ok`), `durchsatz.csv` (je Aufruf
Zeichen, Token, Sekunden), `vorgaenge.csv` (IDs des Versuchs in § 3.6). **Lokal**, nie im Repo:
der Modellcache `cache_root/ml/<modell>.sqlite` (F5, mit allen Profilen und Vorhaben geteilt),
unter `messdaten/20-kurzfassungen/` der Auszug der Kurzfassungen je Modell, die Protokolle der
Läufe (`laeufe/`), die beanstandeten Angaben (`treue_unbelegt.jsonl`), die Zuordnung K1–K3
(`zuordnung.json`, entsteht mit den Aufträgen) und die Antworten des Versuchs; unter
`messdaten/kodierung/20-kurzfassungen/` die Aufträge an Maßstab und Kodierer. Quelle: öffentliche
Ratsdokumente; die Kurzfassungen sind daraus erzeugter Text und bleiben nach Frage 6 lokal.

## 3. Messung

### 3.1 Vorab festgelegt (2026-11-23, Commit `6e7b966` um 22:43, vor der ersten Kurzfassung)

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

### 3.2 Treue: Ergebnis nach der Festlegung und Durchsicht

Gerechnet am 2026-11-23 nach beiden Läufen (`uv run python docs/plans/20-kurzfassungen-messung.py`).
Beide Modelle lieferten 200 von 200 Kurzfassungen, keine leer, keine an `num_predict` abgeschnitten,
kein Aufruf gescheitert.

| | `qwen3.6:27b` | `gemma4` |
|---|---|---|
| **ohne unbelegte Angabe, nach § 3.1** (Kriterium ≥ 0,98) | 103 / 200 = 51,5 %; geschichtet **51,6 %** (44,8–58,8, n_eff 191) | 137 / 200 = 68,5 %; geschichtet **68,9 %** (62,2–75,2) |
| Angaben je Kurzfassung im Mittel | 10,2 | 11,0 |
| Zahlen: geprüft / unbelegt | 434 / **0** | 462 / **1** |
| Daten | 59 / **0** | 82 / **0** |
| Drucksachennummern | 26 / **0** | 53 / **0** |
| Eigennamen (a Kürzel, b Orte, d Personen, e seltene Wörter) | 1 530 / 158, alle in e | 1 611 / 70, alle in e |
| Kurzfassungen mit mindestens einer Beanstandung der Klasse e | 97 | 62 |
| ohne die Klasse e | **200 / 200** | **199 / 200** |
| Person nach Anrede genannt (gegen Regel 5 des Prompts) | 6 | 6 |
| höchstens drei Sätze und 80 Wörter | 186 / 200 (Wörter Median 50, höchstens 73) | 174 / 200 (Median 53, höchstens 78) |

**Nach der Festlegung besteht keines der beiden Modelle.** Jede Beanstandung von qwen und alle bis
auf eine von gemma liegen aber in **Klasse e** („seltenes großgeschriebenes Wort"), und die
Durchsicht zeigt, dass diese Klasse keine Eigennamen misst, sondern **deutsche Substantive**: das
Deutsche schreibt jedes Substantiv groß, und ein Abstraktum oder eine Zusammensetzung, die eine
Kurzfassung aus Wörtern der Eingabe bildet, ist im Korpus selten und steht nicht wörtlich in der
Eingabe. Die Gründe, maschinell zugeordnet (`kategorie` im Skript) und von Hand an allen
Beanstandungen nachgelesen:

| Beanstandung der Klasse e | qwen | gemma |
|---|---|---|
| Abstraktum auf -ung, -heit, -keit, -schaft, -ität, -ion, -nis, -tum, -ismus | 76 | 38 |
| Wort, das im Korpus in mindestens drei Dokumenten steht (Gattungswort) | 48 | 14 |
| Zusammensetzung aus Wörtern des Korpus | 27 | 14 |
| Bindestrichwort, dessen Name-Teil in der Eingabe steht | 5 | 2 |
| übrig | 2 | 2 |
| **davon von Hand als Eigenname erkannt, der nicht in der Eingabe steht** | **0** | **1** |

Die vier übrigen, von Hand gelesen: bei qwen ein Wort der Eingabe falsch gebeugt und eine
Umschreibung einer Klassenstufe (beides gedeckt), bei gemma ein Wort der Eingabe gebeugt (gedeckt)
und **ein Straßenname mit Schreibfehler** (ein Buchstabe doppelt, echt unbelegt nach Regel 3). Die
eine unbelegte Zahl von gemma ist **eine selbst gerechnete Summe** dreier Kredite der Eingabe
(arithmetisch richtig, aber so nicht im Text; nach Regel 3 unbelegt). Rundungen kamen nicht vor.

**Durchsicht, zusammengefasst** (nicht das Kriterium, sondern der Befund über das Instrument): an
echten unbelegten Angaben der vier Klassen stehen **bei qwen 0 von 200 Kurzfassungen, bei gemma 2
von 200** (99,0 %). Was die Prüfung damit nicht sagt: ob eine Kurzfassung einen Sachverhalt, eine
Rolle oder eine Wirkung erfindet; das misst die Bewertung (§ 4). Beim Lesen fiel eine solche Art
Fehler auf, im Versuch mit Vorgängen (§ 3.6): aus einem Beschlussvorschlag wird ein Beschluss.

**Nachträglich, explorativ** (`zeige_fassung2`): mit Klasse e in Fassung 2 (eine Beanstandung bleibt
nur, wenn das Wort kein Abstraktum, kein Wort und keine Zusammensetzung von Wörtern des Korpus ist;
Bindestrichwörter je Teil) stehen qwen bei 198 und gemma bei 197 von 200 ohne unbelegte Angabe. Diese
Regel ist an den Fehlalarmen dieser Stichprobe entstanden; sie gilt erst, wenn eine frische
Stichprobe sie bestätigt (§ 5.2).

Nach Dokumentart (nach § 3.1 nicht bestanden, qwen / gemma): Anfrage 31 / 23 von 41, Antrag 22 / 15
von 49, Beschlussvorlage 17 / 6 von 40, BV-Informationsvorlage 13 / 5 von 26. Anfragen trifft
Klasse e am stärksten, weil eine Kurzfassung ihre Fragen in Abstrakta auf -ung und -keit bündelt. Nach Länge: kurz 28 / 20 von 70, mittel 58 / 40 von 108, lang 11 / 3 von
22; gekürzte Eingaben (8) bestehen bei gemma alle, bei qwen die Hälfte.

### 3.3 Durchsatz auf der RTX 4090 und Hochrechnung

Je Aufruf die Wanduhr ohne das Laden des Modells (das Laden trug der erste Aufruf: qwen 9,95 s), unter
der Sperre der Warteschlange, je Modell ein Lauf; der Grafikspeicher und die Verteilung der Schichten
sind im Log von ollama geprüft (qwen 65 / 65 Schichten auf der GPU, 23,2 GB; gemma 43 / 43, 10,7 GB),
nicht mit `ollama ps` (Hinweis des Supervisors nach einem Rückfall auf die CPU in Vorhaben 18).

| Modell | Lauf, Lastmittel Anfang → Ende | je Dokument Mittel / Median / P90 | Eingabe | Ausgabe | Gerade |
|---|---|---|---|---|---|
| `qwen3.6:27b` | 22:46–22:57, 22,7 → 7,5 | 2,98 / 2,91 / 3,82 s | 903 Token im Mittel, 1 999 Token/s | 97 Token, **40,0 Token/s** | 2,56 s + 0,215 s je 1 000 Zeichen |
| `gemma4` | 23:14–23:20, 6,6 → 14,4 | 1,09 / 1,00 / 1,60 s | 911 Token, 13 228 Token/s | 108 Token, **130,5 Token/s** | 1,02 s + 0,034 s je 1 000 Zeichen |

**Nicht vorhergesehen**: ollama meldet auch bei geladenem Modell je Aufruf eine Ladezeit (Median
0,28 s bei qwen, 0,39 s bei gemma, bei gemma in 78 Aufrufen über 0,5 s); sie ist Wanduhr, die ein
Stapellauf ebenfalls zahlt. Festgelegt war „Wanduhr ohne Laden" (gemeint: ohne das Laden des
Modells); gerechnet ist danach je Aufruf Wanduhr minus gemeldete Ladezeit. Die volle Wanduhr der
warmen Aufrufe ist **qwen 3,27 s** (Gerade 2,86 s + 0,210 s je 1 000 Zeichen) und **gemma 1,67 s**
(1,65 s + 0,010 s); sie steht unten in Klammern und ist die ehrlichere Zahl für die Planung der
Nächte. Die Entscheidung der Regel ändert sie nicht.

Die Zeit ist fast ganz Ausgabe: qwen braucht für rund 100 Token Antwort 2,4 s, für rund 900 Token
Eingabe 0,45 s; lange Dokumente (Rohtext ab 5 000 Zeichen, Eingabe im Mittel 2 030 Token) kosten 3,85 s
statt 2,68 s bei kurzen. Rund 2,2 Zeichen je Eingabetoken. Die 13 Token/s des Rauchtests (Frage 13)
waren ein Ausreißer; F5 maß 33, hier sind es 40.

**Hochrechnung** (Gerade × Zeichen der Eingabe jedes Dokuments mit Text, nach demselben Regelwerk je
Periode; Regel aus § 3.1):

| Periode | Dokumente mit Text | qwen | gemma | Auswahl (Dokumente) | qwen | gemma |
|---|---|---|---|---|---|---|
| laufende Periode 2025– | 4 075 | 3,4 h (3,7) | 1,2 h (1,9) | 3 221 | 2,6 h (2,9) | 1,0 h (1,5) |
| Hauptperiode 2020–2025 | 19 032 | **15,8 h** (17,3) | **5,8 h** (8,8) | 14 708 | 12,1 h (13,3) | 4,4 h (6,8) |
| Mönchengladbach | 650 | 0,6 h (0,6) | 0,2 h (0,3) | 194 | 0,2 h (0,2) | 0,1 h (0,1) |
| 2014–2020 | 21 714 | 17,8 h (19,6) | 6,6 h (10,0) | 3 264 (Frage 20.5) | 2,7 h (2,9) | 1,0 h (1,5) |
| **alle** | 45 471 | **37,6 h** (41,2) | **13,8 h** (21,0) | | | |

Nach der Regel: **mit gemma laufen alle vier Perioden ganz (13,8 GPU-Stunden, mit voller Wanduhr
21,0, zwei bis drei Nächte)**; mit
qwen liefen 2025 und Mönchengladbach ganz und 2014–2020 nur als Auswahl, die **Hauptperiode gar
nicht** (15,8 h ganz, 12,1 h als Auswahl, knapp über der Grenze von 12 h je Periode). Frage 13 ist
damit beantwortet: eine Kurzfassung der Hauptperiode kostet nicht 50 bis 60, sondern **16 bis 17
GPU-Stunden mit qwen und 6 bis 9 mit gemma**; eine Auswahl braucht keines der beiden Modelle.

### 3.4 Eingaben

180 der 200 Eingaben kommen aus Abschnitten, 20 aus dem Rückfall auf den Rohtext (zehn
BV-Informationsvorlagen, deren Mitteilung als „Hierzu teilt das … Amt mit:" beginnt, sechs
Anfragen, je eine weitere Art); 8 sind gekürzt. Abschnitte in den Eingaben: Betreff 199,
Beschlussvorschlag 114, Sachdarstellung 83, Begründung 79, Fragen 33, Zitierter Beschluss 8,
Stellungnahme 7. Abschnittstext Median 1 335 Zeichen, Mittel 1 978. Zwei Mängel der Fassung 1 für
Stufe 2: Seitenkopf- und Seitenzahlzeilen („Seite 2") stehen noch im Abschnittstext, weil die Messung
`saeubern` statt `read_span` mit `page_noise` (11) nimmt, und die Einleitung „Hierzu teilt … mit"
fehlt im Regelwerk von 11 als Stellungnahme (dort nur „Hierzu teilt die Verwaltung mit"); beides
fällt mit Stufe 2 von 11 weg oder gehört als Label dorthin.

### 3.5 Laufzeiten

Skript ohne Hochrechnung rund 15 s, mit Hochrechnung (Regelwerk über vier Perioden, 45 471
Dokumente) rund 2 min, Lastmittel 7 bis 15. Erzeugen: qwen 11 min für 200, gemma 6 min, je
einschließlich des Ladens; Versuch § 3.6 beide Modelle zusammen 77 s.

### 3.6 Versuch: Kurzfassung je Vorgang und „was ist neu" (beschrieben, nicht validiert)

Acht Vorgänge nach den starken Kanten von 14, soweit ohne Anlagen prüfbar (Titel nennt eine
Drucksache, Nachtragsnummer): vier mit drei Dokumenten, vier Paare; dazu sechs Paare aus Vorlage und
Nachtrag (`/1`) für „was ist neu". IDs in `validierung/20-kurzfassungen/vorgaenge.csv`. Prompt
`20-vorgang-1`: die Eingaben der Dokumente nach Datum, je höchstens 2 500 Zeichen; `20-neu-1`: A und
B je höchstens 3 500 Zeichen (Wortlaut im Skript). Beide Modelle, dieselben Optionen.

- **Vorgang**: beide Modelle erzählen die Kette in der Folge der Daten (Antrag, Mitteilung der
  Verwaltung, Änderungsantrag) und nennen die Akteure; Median 52 (qwen) und 60 Wörter (gemma), 4,0 s
  und 1,3 s je Vorgang. Wo die Dokumente kein Ergebnis nennen, sagt qwen das einmal ausdrücklich.
  Der Fehler, den die Prüfung nicht sieht, kommt hier vor: qwen macht in einem Vorgang aus einem
  Beschlussvorschlag der Verwaltung einen Beschluss des Rates, gemma nennt die Vorlage der Verwaltung
  einmal einen Antrag. Rollen in Vorgängen sind die schwächste Stelle; Stufe 2 sollte die Rolle je
  Dokument aus 14 (`rolle`) und aus der Dokumentart in die Eingabe schreiben, statt sie das Modell
  erraten zu lassen.
- **Was ist neu**: in drei der sechs Paare ist B inhaltlich gleich A (zwei Eingaben nach § 24 GO,
  eine Vorlage); beide Modelle sagen dort „nichts Wesentliches neu". In den drei anderen nennen beide
  die eigentliche Änderung (geänderter Beschlussvorschlag, neue Maßnahmen und Budget, zusätzliche
  Genehmigungsteile); qwen genauer und mit dem neuen Betrag, gemma
  füllt mehrmals mit Kopfangaben (Drucksache und Datum von B) als „neu". Ob B neu ist, lässt sich
  billiger und sicherer **vorher deterministisch** sagen (zeilenweiser Vergleich der Eingaben); das
  Modell sollte nur den Unterschied sehen. Vorschlag für Stufe 2: `diff` der Abschnitte als Eingabe,
  kein Modellaufruf, wenn der Unterschied leer ist.

Die deterministische Prüfung beanstandet in beiden Versuchen fast nur Klasse e (wie § 3.2) und sagt
darum hier nichts Belastbares; die Versuche sind beschrieben, nicht gemessen.

## 4. Validierung

**Stand: vorbereitet, nicht kodiert.** Ablauf für den Supervisor (Rollen nach F4, `docs/validierung.md`):

1. **Maßstab-Agent** (Opus, frisch, kein Fork): Auftrag unter
   `messdaten/kodierung/20-kurzfassungen/massstab/` (`anleitung.md`, `auftrag.jsonl` mit den 50
   Eingaben, `antworten.jsonl` mit `kurzfassung: null`). Er sieht nur die Eingabe und dieselbe
   Anweisung wie die Modelle (Systemnachricht und Regeln wörtlich), keine Kurzfassung eines Modells.
2. **Aufträge der Kodierer**: `uv run python docs/plans/20-kurzfassungen-messung.py kodierung`
   (bricht ab, solange eine Maßstab-Kurzfassung fehlt). Es schreibt `A/` und `B/` im Format von F4
   (`auftrag.jsonl`, `antworten.jsonl`, `codebuch.md`; Folge der Einheiten je Kodierer verschieden)
   und die Zuordnung nach `messdaten/20-kurzfassungen/zuordnung.json`, außerhalb der Ordner der
   Kodierer. Jede Einheit trägt unter `dokumente` die Eingabe als `ausschnitt` und unter
   `kurzfassungen` K1 bis K3.
3. **Zwei Kodier-Agenten** mit dem Prompt aus `docs/validierung.md`, § 4.1, je Ordner; 50 Einheiten
   mit je zwölf Fragen (vier je Kurzfassung), Ausschnitte bis 8 200 Zeichen (Median 1 206 mit
   Kopfzeilen): ein Lauf je Kodierer reicht, bei Bedarf zwei zu 25.
4. `uv run georep validate merge 20-kurzfassungen --model claude-opus-5-5` (im Worktree mit
   `validation.coding_root = "/media/konrad/xtraspace/georep/messdaten/kodierung"`), Schlicht-Agent
   nach § 4.2, zweiter `merge`: `labels.csv`, `README.md`, `guete.json` mit α je Frage (ordinal für
   die drei Skalen, nominal für `unbelegt`).
5. `uv run python docs/plans/20-kurzfassungen-messung.py` rechnet danach je Quelle (qwen, gemma,
   Maßstab) Median und Verteilung je Dimension, den Anteil „ohne unbelegte Angabe" laut Kodierern
   mit Wilson-Intervall und die Vierfeldertafel deterministische Prüfung gegen Kodierer (Fassung 1
   wie festgelegt und Klasse e in Fassung 2).

**Codebuch** (`validierung/20-kurzfassungen/codebuch.toml`, Fassung 1, Einheit `document`): je
Kurzfassung K1 bis K3 vier Fragen in fester Folge: `kN_unbelegt` (binär: mindestens eine Angabe, die
der Ausschnitt nicht stützt, auch Sachverhalte und Rollen; eine erkennbare Rundung gilt als
gestützt), `kN_treue`, `kN_vollstaendigkeit`, `kN_verstaendlichkeit` (ordinal 1 bis 5, jede Stufe
definiert; Länge über drei Sätze oder 80 Wörter höchstens 4, Aufzählung höchstens 3). Die Kodierer
urteilen nur gegen den Ausschnitt, nicht gegeneinander und nicht nach Wissen von außen.

**Was die Bewertung leistet, was nicht.** Sie misst die Übereinstimmung zweier Opus-Agenten mit dem
Codebuch, keinen menschlichen Goldstandard (F4, § 1); der Maßstab stammt vom selben Modell wie die
Kodierer (Frage 20.2). Die Frage `unbelegt` ist die Gegenprobe der deterministischen Prüfung: sie
sieht Sachverhalte, Rollen und Wirkungen, die keine Zahl und keinen Namen tragen.

## 5. Urteil gegen das Kriterium

### 5.1 Nach der Festlegung: nicht bestanden, Instrument fehlerhaft → umbauen

| Teil des Kriteriums | qwen3.6:27b | gemma4 |
|---|---|---|
| 1. Treue ≥ 0,98 (geschichtet, Prüfung nach § 3.1) | 0,516 — **nicht bestanden** | 0,689 — **nicht bestanden** |
| 1′. dieselbe Prüfung ohne Klasse e (Zahlen, Daten, Drucksachen, Kürzel, Orte, Personen) | 200 / 200 | 199 / 200 |
| 1″. Durchsicht von Hand: echte unbelegte Angaben der vier Klassen | 0 / 200 | 2 / 200 |
| 2. Median der Bewertung ≥ 4 je Dimension (50, α ≥ 0,8) | ausstehend | ausstehend |
| GPU-Stunden aller vier Perioden (volle Wanduhr) | 37,6 (41,2) | 13,8 (21,0) |

Nach der vorab festgelegten Prüfung besteht kein Modell. Der Grund liegt nicht in den Kurzfassungen,
sondern im Instrument: Klasse e misst Substantive, nicht Eigennamen (§ 3.2); in den Klassen, die die
Prüfung trägt, sind beide Modelle nahezu fehlerfrei. Die Entscheidungsregel aus § 3.1 nennt für
„keines besteht" den Umbau, „wenn die unbelegten Angaben einer Klasse gehäuft sind, die ein Prompt
beheben kann"; gehäuft sind sie in einer Klasse, die nur ein neues Instrument behebt. **Urteil:
umbauen, eine Runde, nicht den Prompt, sondern Klasse e der Prüfung** (§ 5.2), an einer frischen
Stichprobe; die Bewertung durch die Kodierer (§ 4) läuft davon unabhängig an den vorhandenen 50 und
entscheidet Teil 2. Ob statt des Umbaus Teil 1 an 1′ gemessen wird und den Rest die Bewertung trägt,
entscheidet der Supervisor (Frage 20.1); das Kriterium selbst bleibt unverändert.

**Wenn beide Teile bestehen**, baut Stufe 2 nach der Regel aus § 3.1 mit **gemma4**: es ist 2,7-mal
so schnell, und qwen ist nach dem bisherigen Stand in Teil 1 nicht um 2 Prozentpunkte besser (1″:
100 % gegen 99 %, also 1 Punkt; die Medianregel kommt mit der Bewertung). Mit gemma laufen nach der
Hochrechnungsregel alle vier Perioden ganz.

### 5.2 Vorab festgelegt für die Umbaurunde (2026-11-23, vor jeder Kurzfassung der neuen Stichprobe)

Gilt, wenn der Supervisor „umbauen" entscheidet; nichts davon ist an einer neuen Kurzfassung geprüft.

- **Stichprobe**: 200 neue Dokumente nach derselben Schichtung, Seed 2026112330, ohne die 200 der
  ersten Runde (darunter die 50 der Bewertung).
- **Unverändert**: Eingabe Fassung 1, Prompt Fassung 1, beide Modelle, Optionen, Klassen 1 bis 3 und
  4a, 4b, 4d der Prüfung, das Kriterium (geschichtet ≥ 0,98, leere und abgeschnittene bestehen
  nie), die Regel der Modellwahl und der Hochrechnung.
- **Klasse 4e, Fassung 2** (`kategorie` und `bleibt_fassung2` im Skript, so wie sie in diesem Commit
  stehen): ein seltenes großgeschriebenes Wort, das nicht in der Eingabe steht, bleibt nur
  beanstandet, wenn es (je Teil eines Bindestrichworts ab vier Zeichen, wobei ein Teil aus der
  Eingabe den Teil deckt) **kein Abstraktum** ist (Endung -ung, -heit, -keit, -schaft, -ität, -ion,
  -nis, -tum, -ismus samt Beugung), **kein Wort des Korpus** (Kleinform in mindestens drei
  Korpusdokumenten) und **keine Zusammensetzung** aus Wörtern des Korpus (Teile ab drei Zeichen, mit
  Fugen -s-, -es-, -n-, -en-). Was das aufgibt: ein Name, der zugleich ein Wort oder eine
  Zusammensetzung des Korpus ist (ein Verkehrsbetrieb, ein Stadtteil außerhalb des Wörterbuchs), wird
  nicht mehr geprüft; ihn sucht die Bewertung (Frage `unbelegt`).
- **Auswertung**: wie § 3.2, dazu die Vierfeldertafel Prüfung gegen Kodierer an den 50 der ersten
  Runde (§ 4), weil nur sie zeigt, was Fassung 2 übersieht.

## 6. Bauplan Stufe 2

**Beitrag** `summaries` im Register `georep.enrich.CONTRIBUTIONS` (F2), ein Schritt `summaries` mit
`models=use` (F5): er läuft nur mit `georep run --models`, sonst wird er übersprungen wie ein
Netzschritt ohne `--online`. Reihenfolge im Tupel: nach `raw_texts` (F1) und `sections` (11). Er hängt
an F1, 11 und F5; ohne Stufe 2 von 11 und F1 auf `main` beginnt er nicht.

**Module** (neu):

- `src/georep/enrich/summaries.py`: der Beitrag; `SCHEMA_VERSION = 1`, `PROMPT_VERSION =
  "20-kurzfassung-1"`, `SYSTEM` und `RULES` als Konstanten (wortgleich mit § 3.1, damit der Cache
  dieser Messung trifft), die reine Funktion `summary_input(meta, raw_text, sections, budget) ->
  SummaryInput` (Kopfzeilen, Abschnitte in fester Folge, Budget, Rückfall), dann `generate_texts`
  mit `GenerationUse(generator_from_settings(settings.ml, client, model=settings.summaries.model),
  PROMPT_VERSION, generation_options(settings.ml))`. Die Abschnitte liest er aus
  `processed/dokumente_abschnitte.parquet` (11) und den Text mit `read_span(text, start, end,
  noise)` (`georep.spans`, mit 11), nicht mit einer eigenen Säuberung; die Seitenkopfzeilen fallen
  damit weg (an der Stichprobe stand „Seite 2" noch in Abschnitten, § 3.4). Weil `read_span` den
  Text anders säubert als `saeubern` hier, trifft der Bau den Cache dieser Messung nicht; das ist
  hingenommen (200 Dokumente).
- `src/georep/enrich/fidelity.py`: die Treueprüfung aus § 3.1 als reine Funktionen
  (`evidence(text) -> Evidence`, `claims(summary, evidence, lexicon) -> list[Claim]`), die Muster
  (Drucksachennummer, Datumsformen, Einheiten, Zahlwörter) als Profilwerte, wo sie stadtabhängig
  sind (Drucksachennummer aus `bodies.reference_pattern`, Kürzel aus `[bodies]`), das Lexikon aus
  dem Wörterbuch des Profils und der Wortverbreitung des Korpus.

**Ausgaben**, beide **unter `cache_root/<profil>/summaries/`, nie unter `data_root`**: so kann weder
`report` noch `publish` noch `pack` sie greifen (ein Test prüft, dass kein Pfad des Schritts unter
`data_root` liegt und `pack` die Art nicht kennt).

1. `kurzfassungen.parquet`: eine Zeile je Korpus-ID mit Text, sortiert nach `id`: `id`, `text`
   (null, wo der Stapellauf sie noch nicht gerechnet hat), `modell`, `digest`, `prompt`,
   `abgeschnitten` (Bool), `eingabe_quelle` (`abschnitte`, `rohtext`), `eingabe_gekuerzt` (Bool).
2. `kurzfassungen_treue.parquet`: eine Zeile je Kurzfassung: `id`, `angaben`, `unbelegt` je Klasse
   (Int), `ok` (Bool). Ohne Text; die beanstandeten Angaben selbst liegen nicht in einer Datei, die
   CLI rechnet sie bei Bedarf nach.

**Verträge**: `one_row_per_document` auf beiden; jede `id` im Korpus; `text` null genau dort, wo der
Bericht des Stapellaufs sie offen nennt; die Eingabe hat höchstens `budget` Zeichen Abschnittstext
plus Kürzungsmarke; Spannen aus 11 mit `check_spans` gegen die Länge des Rohtexts.

**Tests** (roter Test zuerst, Beleg im Commit-Body; nie ein Modell, immer `FakeGenerator`):

- Beispiele aus **synthetischen** Texten: Eingabe mit Abschnitten, Rückfall, Budget, Kürzung am
  Zeilenende, Ebene 2 im Beschlussvorschlag; der Schritt mit `FakeGenerator`, Teillauf mit `limit`,
  abgeschnittene Antwort, Abweisung.
- Die 14 Fälle des Selbsttests (§ 3.1) als Beispieltest der Treueprüfung, dazu die Fehlalarme der
  Klasse e aus § 3.2 als synthetische Fälle (Abstraktum, Zusammensetzung, Bindestrich).
- hypothesis in `tests/property/`: jede Angabe, die die Prüfung in einem Text findet, ist gegen
  denselben Text (mit beliebigem Text davor und dahinter) belegt; die Normalisierung ist idempotent;
  ein Betrag in den drei Schreibweisen (1.500.000 €, 1,5 Mio. €, 1 500 000 Euro) ist gegeneinander
  belegt.
- Kein Pfad des Schritts unter `data_root`, `site/` und `pack` kennen die Kurzfassungen nicht.

**Settings**: ein Block `# --- Vorhaben 20: Kurzfassungen` am Ende von `defaults.toml`:
`summaries.enabled = false`, `summaries.model = "<nach dem Urteil>"`, `summaries.budget_chars =
8000`, `summaries.rare_share = 0.01`. Das Modell steht hier und nicht in `[ml.generation]`, weil 19
dort ein anderes nennen darf. Nichts im Stadtprofil außer dem, was 11 und `[bodies]` schon tragen.

**Stapellauf**: je Profil ein Auftrag der GPU-Warteschlange
`/media/konrad/xtraspace/georep/gpu-queue/20-kurzfassungen-<profil>.sh`, der in Blöcken
`flock …/gpu.lock uv run georep --profile <p> run summaries --models --limit <n>` aufruft (n = 1 000 mit
gemma, 500 mit qwen: nach der vollen Wanduhr aus § 3.3 rund 28 Minuten je Block), bis `georep status` den Schritt aktuell nennt; der
Cache macht jeden Block fortsetzbar. Welche Perioden laufen, sagt § 3.3.

**CLI**, nur lokal: `georep kurzfassung <drucksache|id>` (Kurzfassung, Modell, Treue, die
beanstandeten Angaben) und `georep kurzfassungen --gremium <kürzel> --seit <datum>` (eine Liste für
den Vorlagenspiegel, als Text oder als HTML-Datei unter `cache_root/<profil>/summaries/`, nie unter
`site/`).

**Berührte Dateien**: neu `enrich/summaries.py`, `enrich/fidelity.py`, Tests; je eine angehängte
Zeile in `enrich/__init__.py` (Register), `settings.py` (Modell vor `class Settings`, Feld am Ende),
`defaults.toml` (Block am Ende), `cli.py` (zwei Befehle); `docs/architecture.md` (Abschnitt
„Modelle", Kurzfassungen als erster Generator-Schritt), `docs/decisions.md` (Eintrag ohne Nummer:
Kurzfassungen nur lokal, Treueprüfung deterministisch, Modellwahl).

**Paket**: keines (Frage 6). CI und Pages überspringen den Schritt; `bootstrap` kennt ihn nicht.

**Nicht in Stufe 2: Vorgang und „was ist neu"** (§ 3.6). Beides erst nach Stufe 2 von 14, als eigener
Schritt `procedure_summaries` mit einer eigenen Messung: die Eingabe nennt je Dokument seine Rolle
aus 14 (`rolle`) und die Dokumentart, damit das Modell sie nicht errät; „neu" nur, wenn der
zeilenweise Vergleich der Abschnitte von A und B nicht leer ist, und dann nur mit dem Unterschied
als Eingabe.

## 7. Bauplan Stufe 3

Keine Unterseite und keine Variante: Kurzfassungen werden nicht veröffentlicht (Frage 6). Sichtbar
werden sie nur lokal, über die CLI und in Vorhaben 29 (Vorlagenspiegel der laufenden Periode,
lokal). Was 29 veröffentlichen darf, ist höchstens die Zahl „Kurzfassungen vorhanden, Treue n %"
ohne Text; das entscheidet 29 mit Konrad.

## 8. Vorab festgelegte Hypothesen

Keine: Vorhaben 20 ist kein Analysevorhaben. Was vorab festgelegt war, ist das Kriterium (§ 3.1).

## 9. Risiken und offene Fragen

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 20.1 | Die Klasse e der Treueprüfung („seltenes großgeschriebenes Wort") misst keine Eigennamen, sondern deutsche Substantive (§ 3.2). Umbauen (Fassung 2 der Prüfung, vorab festgelegt in § 5.2, an einer frischen Stichprobe von 200), oder das Kriterium an den Klassen messen, die die Prüfung trägt, und den Rest der Bewertung überlassen? | Nach der Festlegung besteht kein Modell; der Grund liegt im Instrument, nicht in den Kurzfassungen | umbauen, eine Runde; bis dahin gilt das Urteil „nicht bestanden, Instrument fehlerhaft" |
| 20.2 | Die Maßstab-Kurzfassungen schreibt ein Opus-Agent, bewertet wird von zwei Opus-Agenten. Bevorzugen sie den Stil ihres eigenen Modells? | Die Obergrenze K wäre zu hoch, die lokalen Modelle zu niedrig | hingenommen und genannt; Frage 19 (Kodierer B ein anderes Modell) gilt hier besonders |
| 20.3 | Darf ein Vorlagenspiegel mit Kurzfassungen als lokale HTML-Datei entstehen (unter `cache_root`, nie unter `site/`)? | Vorhaben 29 braucht eine Sicht, Frage 6 verbietet die Veröffentlichung | ja, lokal; veröffentlicht wird nichts davon |
| 20.4 | Sind die Budgets der Hochrechnung (12 GPU-Stunden je Periode, 36 zusammen) richtig gewählt? | Sie entscheiden, welche Perioden laufen; mit `qwen3.6:27b` fiele die Hauptperiode knapp heraus | wie festgelegt; der Supervisor darf sie für Stufe 2 ändern, mit Grund |
| 20.5 | Die Auswahl der Periode 2014–2020 nennt die Arten der Hauptperiode; die alten Sammelarten „Vorlage aus der Politik" (9 375) und „Verwaltungsvorlage" (8 079) fallen heraus | Die Auswahl dort ist kleiner, als sie gemeint war | Stufe 2 bildet die alten Arten über das Regelwerk von 14 (`art`) ab; bis dahin gilt die Zahl hier als Untergrenze |
| 20.6 | 104 Dokumente der Hauptperiode haben nach dem Kopf keinen Text (Frage 31) | Ihre Kurzfassung kann nur den Betreff wiedergeben | keine OCR; Stufe 2 schreibt für sie keine Kurzfassung, sondern `text = null` mit Grund |

## 10. Änderungen durch die Synergie

(füllt der Supervisor)
