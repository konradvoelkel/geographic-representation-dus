# Vorhaben 27: Personen und Mandatstyp

Stand 2026-11-24, Stufe 1 (Messen), Branch `feat/27-personen`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „27 Personen und
Mandatstyp". Messskript: [27-personen-messung.py](27-personen-messung.py).

**Dieser Stand ist die Vorab-Festlegung** (§ 2.11 des Meta-Plans): § 8 steht, bevor eine Anfrage einer
Person oder ein Ratsmitglied einem Mandatstyp zugeordnet ist. Die übrigen Abschnitte folgen in eigenen
Commits; § 8 wird danach nicht mehr geändert, eine neue Quelle wird datiert unter § 8.6 nachgetragen.

Personen kommen nur als Mandatsträger in öffentlicher Rolle vor (Plan § 1). Namen bleiben lokal; in
diesem Dokument, im Messskript und unter `validierung/27-personen/` stehen nur OParl-Kennungen,
Wahlbezirksnummern, Rollen, Codes und Zählungen.

## 1. Frage und Nutzen (Literatur, Ratsarbeit)

*folgt nach der Messung*

## 2. Datenlage (Dateien, Spalten exakt, Größen, Herkunft, Lizenz)

*folgt nach der Messung*

## 3. Messung (Vorgehen, Stichprobe mit Seed, Zahlen mit Datum)

*folgt nach der Messung*

## 4. Validierung (Codebuch, Kodierer, Maße mit Intervall)

*folgt nach der Messung*

## 5. Urteil gegen das Kriterium: bauen / umbauen / verwerfen

*folgt nach der Messung*

## 6. Bauplan Stufe 2 (Beiträge, Ausgaben mit Schema, Verträge, Tests, berührte Dateien, Settings, Paket)

*folgt nach der Messung*

## 7. Bauplan Stufe 3 (Unterseite oder Variante, Größe in KB, Tabellen im Register, Texte)

*folgt nach der Messung*

## 8. Vorab festgelegte Hypothesen (nur Analysen: Hypothese, Maß, Test, Schwelle)

Festgelegt am 2026-11-24 um 00:40 Uhr (Commit `Hypothesen von Vorhaben 27 vorab festlegen`), bevor eine Anfrage einer Person, ein Ratsmitglied einem
Mandatstyp oder ein Ratsmitglied einem Wahlbezirk zugeordnet war, und bevor Wahlergebnisse mit Namen
geladen waren. **Bekannt war zu diesem Zeitpunkt nur**: die Zahl der Personen (632) und
Mitgliedschaften (4 615) im Netzlauf aus F6 und deren Rollen; wie viele Mitgliedschaften im Rat
(`gr/6`) zu einigen Stichtagen laufen (rund 31 bis 35 vor 2020, 54 bis 63 zwischen 2021 und 2025, 89
seit Ende 2025: der Server nennt ausgeschiedene Mitglieder offenbar nicht mehr); die Verteilung der
Urheberklassen aus Vorhaben 15 nach Gremium; Anfang und Ende von neun Anfragen, gelesen nur, um das
Format von Absender und Unterschrift zu sehen (nicht gezählt); `originatorPerson` ist in keinem
Dokument der Hauptperiode gefüllt. Weder Ortsbezüge je Person noch je Mandatstyp waren gerechnet.
In Stufe 1 wird **keine** Probe der Hypothese gerechnet, auch keine vorläufige: das Messskript bildet
das Maß *Y* (§ 8.2) nicht, auch nicht gepoolt (dieselbe Regel wie 24, § 8, nach Punkt 61).

**Bezug.** Zittel, Nyhuis und Baumann (2019) zählen Ortsbezüge in den schriftlichen Fragen des
Bundestags als Maß geografischer Repräsentation und finden sie trotz starker Fraktionsdisziplin, mehr
bei lokal verwurzelten Abgeordneten und in Wahlkreisen mit wechselhaften Ergebnissen; den Volltext
konnte der Mess-Agent nicht lesen (Bezahlschranke), die Angabe stammt aus dem Abstract. Harmening u. a.
(2025) zeigen an 10 189 Anfragen aus zwölf deutschen Großstädten, dass **Parteien** ihre Hochburgen
öfter nennen, verstärkt bei räumlich konzentrierter Wählerschaft und in Städten mit Wahlbezirken; der
Mandatstyp einzelner Ratsmitglieder ist dort nicht untersucht (Einheit ist die Partei je Stadtteil).
In Nordrhein-Westfalen hat jede Wählerin eine Stimme, die zugleich für die Bewerberin im Wahlbezirk und
für die Reserveliste ihrer Partei zählt; im Wahlbezirk gewinnt die relative Mehrheit, die übrigen Sitze
kommen über die Reservelisten. Wer über die Liste einzieht, hat fast immer selbst in einem Wahlbezirk
kandidiert und verloren. Das macht den Vergleich möglich, den das Briefing fragt: dieselbe Art
„eigener" Wahlbezirk, einmal gewonnen, einmal nicht.

### 8.1 H1 (die Hauptthese, sie allein entscheidet)

> Ratsmitglieder, die ihren Wahlbezirk direkt gewonnen haben, nennen in den Anfragen, die sie stellen,
> ihren eigenen Wahlbezirk häufiger als Ratsmitglieder, die über die Reserveliste in den Rat gekommen
> sind, ihren eigenen Wahlbezirk (den, in dem sie kandidiert haben).

### 8.2 Einheit, Maß, Grundgesamtheit

- **Dokumente**: Anfragen (Rolle `anfrage` nach Vorhaben 14, `art()`; Dokumentart mit „Anfrage") in
  **Rat oder Ausschuss** (`gremium_art` `rat` oder `ausschuss`, Schritt `bodies`), aus den Profilen
  `duesseldorf` (2020–2025), `duesseldorf-2014` (2014–2020) und `duesseldorf-2025` (seit 2025).
  Bezirksvertretungen gehören nicht zur Hauptprüfung: ihre Mitglieder werden nur über Listen gewählt.
- **Einheit**: ein Paar (Anfrage *d*, Person *p*), wenn das in Stufe 1 validierte und danach
  eingefrorene Verfahren (§ 3) *p* als Fragestellerin oder Unterzeichnerin von *d* nennt und *p* am
  Datum von *d* Ratsmitglied der Periode ist. Eine Anfrage mit drei Unterzeichnern gibt drei Paare.
  Zeichnende „f. d. R.", Empfänger (Vorsitzende) und Personen, über die gefragt wird, sind keine
  Fragesteller (Codebuch, § 4).
- **Mandatstyp** *D*(*p*) ∈ {direkt, Liste}: direkt, wenn *p* bei der Wahl, die die Periode eröffnet
  (2014-05-25, 2020-09-13, 2025-09-14), einen Wahlbezirk gewonnen hat; Liste, wenn *p* über die
  Reserveliste gewählt wurde oder später aus ihr nachgerückt ist. Quelle ist das amtliche
  Wahlergebnis (Stadt, Wahlleiter), nicht OParl; OParl liefert die Kennung und die Mitgliedschaft.
- **Eigener Wahlbezirk** *w*(*p*): bei direkt Gewählten der gewonnene, bei Listenmitgliedern der, in
  dem sie bei derselben Wahl kandidiert haben, nach den amtlichen Wahlvorschlägen oder dem Ergebnis je
  Wahlbezirk. Wer über die Liste kam und in keinem Wahlbezirk kandidiert hat, fällt aus der
  Hauptprüfung (kein eigener Wahlbezirk); die Zahl wird berichtet.
- **Zuschnitt**: der der Wahl, die die Periode eröffnet. Ortsbezüge werden mit dem Wörterbuch-Verfahren
  der Kette (Schritte `dictionary`, `index`, die Settings des Commits, mit dem geprüft wird) auf die
  Wahlbezirke **dieses** Zuschnitts bezogen. Eine Periode, für deren Zuschnitt Stufe 2 kein Wörterbuch
  bauen kann (fehlende Flächen), fällt aus der Hauptprüfung; sie wird nicht über einen anderen
  Zuschnitt genähert (das ist nur Nebenrechnung R7).
- **Maß**: *Y*(*d*, *p*) = 1, wenn *d* mindestens einen Treffer des Wörterbuchs im Wahlbezirk *w*(*p*)
  hat, sonst 0.
- **Kovariaten**: (a) die **Basisrate** *b*(*w*, *t*, −*p*): der Anteil der Anfragen in Rat und
  Ausschüssen der Periode *t*, die *w* treffen, ohne die von *p* gestellten, geglättet als
  (1 + Treffer) / (2 + Anfragen); sie nimmt, wie oft ein Wahlbezirk ohnehin genannt wird (Altstadt
  gegen Stadtrand, Größe des Wörterbuchs je Wahlbezirk). (b) *k*(*d*) = log(1 + Zahl der Wahlbezirke,
  die *d* trifft): eine Anfrage, die die halbe Stadt aufzählt, trifft jeden Wahlbezirk.
  (c) Feste Effekte **Fraktion × Periode** (Fraktion von *p* am Datum von *d* aus den
  Mitgliedschaften, sonst die Partei des Wahlvorschlags): direkt gewinnen fast nur große Fraktionen,
  und Fraktionen fragen verschieden viel nach Orten.

### 8.3 Modell, Test, Schwelle, Entscheidung

- **Modell**: logistische Regression über alle Paare der geprüften Perioden zusammen,
  logit P(*Y* = 1) = α(Fraktion × Periode) + β · [*D* = direkt] + γ₁ · logit *b*(*w*, *t*, −*p*) +
  γ₂ · *k*(*d*), geschätzt nach Maximum-Likelihood (IRLS, numpy; pandas und statsmodels sind im Paket
  verboten). Standardfehler **geclustert nach Person** (Sandwich, Faktor G/(G−1) · (N−1)/(N−K)).
- **Test**: einseitig, H1: β > 0, z-Test, **α = 0,05**. Berichtet wird OR = exp(β) mit
  95-%-Intervall.
- **Vorab genannter Effekt**: **OR = 1,5**. Die Literatur nennt für den Mandatstyp auf kommunaler
  Ebene keine Größe; 1,5 ist dieselbe Größenordnung wie die kleinste Wirkung, die 24 sehen will, und
  heißt bei einer Basisrate von 10 % rund 14 % statt 10 %.
- **Entscheidung**:
  - **bestätigt**, wenn p < 0,05 (einseitig);
  - **widerlegt** (der vorab genannte Effekt ist ausgeschlossen), wenn p ≥ 0,05 und die obere Grenze des
    einseitigen 95-%-Intervalls für OR unter 1,5 liegt;
  - **nicht entscheidbar** sonst, und **immer**, wenn eine der drei Voraussetzungen fehlt: die
    Zuordnung Dokument → Person erreicht an 150 Dokumenten die Präzision 0,95 nicht (§ 4), der
    Mandatstyp ist für weniger als 90 % der Ratsmitglieder einer geprüften Periode bekannt, oder die
    Teststärke nach § 8.4 liegt unter 0,8. „Nicht entscheidbar" steht auf der Seite als solches, nicht
    als „kein Unterschied".

### 8.4 Teststärke-Regel

Simuliert mit der **beobachteten Struktur** (alle Paare mit *D*, Fraktion × Periode, *b* und *k*,
nach dem eingefrorenen Verfahren), aber mit **künstlichem** *Y*: *Y* ~ Bernoulli(expit(logit *b* +
*a* + β · *D* + *u*(*p*))), mit *a* = 0 (Listenmitglieder nennen ihren Wahlbezirk so oft wie die
Basisrate), β = log 1,5, *u*(*p*) ~ N(0; 0,5²) für die Eigenart einer Person, 1 000 Läufe, je Lauf das
Modell aus § 8.3. Teststärke = Anteil der Läufe mit p < 0,05 einseitig. **Entscheidend: ≥ 0,8 bei
OR 1,5.** Daneben, nicht entscheidend: OR 1,25 und 2,0, *a* = log 2, Streuung 1,0, und der Fehler
erster Art (β = 0). Stufe 1 rechnet sie mit der Struktur, die sie messen kann (Zuordnung vor der
Kodierung, Ortsbezüge im Zuschnitt 2025, eigener Wahlbezirk über die größte Flächenüberlappung
genähert); Stufe 2 rechnet sie vor der Prüfung neu mit dem eingefrorenen Verfahren, und nur diese
zweite Zahl entscheidet.

### 8.5 Nebenrechnungen und Nebenthese (berichtet, entscheiden nicht)

- **H2 (Wettbewerb, nach Zittel u. a. 2019)**: Unter den direkt Gewählten nennen die mit knappem
  Vorsprung (unter 5 Prozentpunkten vor der Zweiten im Wahlbezirk) ihren Wahlbezirk häufiger als die mit
  sicherem. Modell wie H1 nur über die Paare direkt Gewählter, Regressor [Vorsprung < 5 Punkte];
  einseitig, α = 0,05; ohne eigene Teststärke ≥ 0,8 heißt das Ergebnis „explorativ".
- **R1** nur Anfragen mit genau einer Unterzeichnerin; **R2** dazu Anträge (Rolle `antrag`, Funktion
  `initiative` nach 15); **R3** je Periode einzeln; **R4** feste Effekte je Wahlbezirk × Periode statt
  der Basisrate; **R5** mit dem Stimmenanteil der eigenen Partei im eigenen Wahlbezirk als Kovariate
  (Hochburg nach Harmening u. a. 2025; trennt Mandatstyp und Stärke der Partei, mit geringerer
  Teststärke); **R6** *Y* als Zahl der Treffer im eigenen Wahlbezirk, Poisson mit denselben festen
  Effekten und Clustern; **R7** Ortsbezüge im Zuschnitt 2025, eigener Wahlbezirk über die größte
  Flächenüberlappung (die Näherung der Stufe 1); **R8** dazu Anfragen in Bezirksvertretungen, die ein
  Ratsmitglied zeichnet.
- **Ausdrücklich explorativ** und auf der Seite so genannt: Unterschiede je Fraktion, je Gremium,
  Ortsbezüge auf Wahlbezirke, in denen jemand nicht kandidiert hat (Wohnort, Nachbarbezirk), und alles,
  was erst nach der Zuordnung auffällt.

### 8.6 Nachträge

*keine*

## 9. Risiken und offene Fragen (Nummer, Frage, warum sie zählt, Annahme ohne Antwort)

*folgt nach der Messung*

## 10. Änderungen durch die Synergie (füllt der Supervisor)
