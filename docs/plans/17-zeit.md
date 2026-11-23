# Vorhaben 17: Zeit und Neuigkeiten

Stand 2026-11-23, Stufe 1 (Messen), Branch `feat/17-zeit`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „17 Zeit und Neuigkeiten".
Messskript: [17-zeit-messung.py](17-zeit-messung.py). Lexikon: [17-zeit-lexikon.toml](17-zeit-lexikon.toml).

**Dieser Stand enthält nur die vorab festgelegten Hypothesen (§ 8) und das Lexikon**, festgelegt, bevor
das Messskript gelaufen ist. Die Abschnitte 1 bis 7 und 9 folgen mit der Messung im nächsten Commit.

## 8. Vorab festgelegte Hypothesen (nur Analysen: Hypothese, Maß, Test, Schwelle)

Festgelegt am 2026-11-23 gegen 19:50 Uhr, **bevor** eine Ergebnisgröße gerechnet war; der Commit, der
diesen Abschnitt anlegt, trägt nur ihn und das Lexikon, sein Zeitstempel ist der Beleg (Meta-Plan,
§ 2.11). **Vorher angesehen** waren: die Schemas der Dateien; die Monatsreihe aller Dokumente in
[../statistik.md](../statistik.md), § 11 (Dezember und Juli schwach, Juni stark); die Anteile je
Urheberklasse und Fraktion aus [15-funktion.md](15-funktion.md), §§ 3.6 und 3.7 (Periodensummen, keine
Jahres- oder Monatswerte); und, weil H17.2 sie als Exposition braucht, **die Monate der Haushaltsanträge
und die Titel der Haushaltsvorlagen** — nicht die Zahl der übrigen Dokumente je Monat.

### 8.0 Gemeinsame Festlegungen

- **Wahljahr**: 1. September bis 31. August. Kommunalwahlen in NRW: 25.05.2014, 13.09.2020, 14.09.2025
  (stehen in Stufe 2 mit Quelle im Stadtprofil). Vollständige Wahljahre: 2014/15 bis 2019/20 (Periode
  2014-2020, sechs), 2020/21 bis 2024/25 (Hauptperiode, fünf), 2025/26 (laufende Periode, eines).
  Angeschnittene Monate (Juni bis August 2014, 1. bis 12. September 2020, 1. bis 14. September 2025,
  ab September 2026) gehören zu keinem Wahljahr.
- **Datum** ist das Vorlagendatum (`date`), wie in der Monatsreihe der Seite.
- **Fraktionsdokumente**: `urheber_art == "Fraktion"` aus `processed/dokumente_urheber.parquet` (Option
  4, auf der Seite); fast nur Anfragen, Anträge und Resolutionen ([15-funktion.md](15-funktion.md),
  § 3.6). **Politische Dokumente**: `urheber_art` in Fraktion, Person, unbekannt.
- **Familie**: die drei Haupttests H17.1, H17.2, H17.3, mit **Holm bei α = 0,05** über die drei
  einseitigen p-Werte. Alles andere — Sensitivitäten, Teilmaße, Anlaufjahr, Ereignisspuren, je
  Kategorie — ist beschreibend und heißt auf der Seite „Sensitivität" oder „explorativ"; es bestätigt
  und widerlegt keine Hypothese.
- **Warum Wahljahre als Einheit**: Monatsreihen sind autokorreliert (ein aktives Jahr hebt alle seine
  Monate) und haben Sommerpausen und Sitzungskalender. Ein Test über Monate als unabhängige
  Beobachtungen wäre zu liberal. Alle drei Tests vergleichen darum ganze Wahljahre oder denselben
  Kalendermonat über Jahre; jedes Wahljahr enthält jeden Kalendermonat genau einmal.

### 8.1 H17.1 Wahlzyklus

- **Hypothese**: Im letzten Wahljahr vor einer Kommunalwahl reichen die Fraktionen mehr Dokumente ein
  als in den mittleren Wahljahren derselben Periode.
- **Maß**: y = ln(Summe der Fraktionsdokumente im Wahljahr).
- **Einheiten**: behandelt sind 2019/20 (Wahl 2020) und 2024/25 (Wahl 2025); Vergleich sind die
  mittleren Wahljahre 2015/16 bis 2018/19 und 2021/22 bis 2023/24. Das erste Wahljahr jeder Periode
  ist ausgenommen (Konstituierung, Besetzung der Ausschüsse: ein eigener Effekt, der den Vergleich zu
  Gunsten der These verschöbe). Die Wahl 2014 hat kein Vorwahljahr im Datensatz (er beginnt am
  Wahltag), die laufende Periode noch keines.
- **Test**: OLS y = μ_Periode + δ · Vorwahljahr über neun Wahljahre, einseitiger t-Test auf δ > 0
  (df = 6). Die exakte Randomisierungsprobe (welches Nicht-Anlaufjahr jeder Periode „Vorwahljahr" ist,
  5 · 4 = 20 Zuordnungen) wird berichtet, entscheidet aber nicht: sie kann 1/20 nicht unterschreiten.
- **Effekt**: exp(δ̂) − 1 mit 90-%-Intervall (einseitig 95 %).
- **Schwelle**: Holm über die Familie.
- **Sensitivität** (berichtet, nicht entscheidend): S1.1 politische Dokumente statt Fraktionsdokumente;
  S1.2 ohne die Kalendermonate März bis Juni in allen Wahljahren (Pandemie im Vorwahljahr 2019/20);
  S1.3 die Anlaufjahre als Vergleich eingeschlossen (df = 8); S1.4 Anteil der Fraktionsdokumente an
  allen Dokumenten statt Summe; S1.5 Anfragen und Anträge getrennt (Dokumentart, in 2014-2020 das
  Titelwort); S1.6 je Wahl das Verhältnis Vorwahljahr zu mittleren Jahren.
- **Begleitend, explorativ**: das **Anlaufjahr** (erstes Wahljahr) gegen die mittleren Jahre derselben
  Periode, für die Perioden 2014-2020 und 2020-2025; für 2025/26 nur gegen die mittleren Jahre der
  Hauptperiode (ein Vergleich über zwei Räte).

### 8.2 H17.2 Haushaltsrhythmus

- **Hypothese**: Der Monat der Haushaltsberatung ist für die Fraktionen ein Spitzenmonat: in ihm liegen
  mehr Fraktionsdokumente, als derselbe Kalendermonat in Wahljahren erwarten lässt, in denen der
  Haushalt in einem anderen Monat beraten wurde.
- **Exposition** (aus den Daten; vor dem Festlegen angesehen): Haushaltsmonat eines Wahljahrs ist der
  Kalendermonat mit den meisten **Haushaltsanträgen** (Dokumentart oder Titel enthält
  `haushalts(begleit)?-?antrag`, kleingeschrieben); bei Gleichstand der frühere Monat; unter fünf
  Haushaltsanträgen im Wahljahr gibt es keinen. Angesehen: November in 2014/15 bis 2019/20, Februar in
  2020/21 (Haushalt 2021 nach der Wahl), Dezember in 2021/22 bis 2024/25, März in 2025/26 (Haushalt
  2026 nach der Wahl).
- **Identifikation**: der Haushaltsmonat wandert (November, Februar, Dezember, März). Derselbe
  Kalendermonat lässt sich darum mit und ohne Haushaltsberatung vergleichen, ohne dass die Saison der
  Ratsarbeit als Haushaltseffekt gelesen wird.
- **Maß**: y(w, m) = ln(1 + Fraktionsdokumente im Kalendermonat m des Wahljahrs w), zwölf Wahljahre mal
  zwölf Monate.
- **Test**: Zwei-Wege-Modell y = α_w + β_m + δ · [m ist Haushaltsmonat von w] + ε; δ̂ aus der doppelt
  zentrierten Tabelle. **Randomisierungstest** über alle Zuordnungen der beobachteten Haushaltsmonate
  (sechsmal November, viermal Dezember, je einmal Februar und März) zu den zwölf Wahljahren,
  12!/(6! · 4!) = 13 860, einseitig: p = Anteil der Zuordnungen mit δ̂* ≥ δ̂. Ganze Wahljahre werden
  vertauscht, die Abhängigkeit der Monate eines Jahres bleibt also erhalten; die Monatskonstanten
  nehmen Sommerpause und Sitzungskalender, die Jahreskonstanten das Niveau des Rates.
- **Effekt**: exp(δ̂) − 1.
- **Schwelle**: Holm über die Familie.
- **Sensitivität**: S2.1 Fraktionsdokumente **ohne** Haushaltsanträge, zweiseitig (zieht der Haushalt
  andere Initiativen mit, oder verdrängt er sie?); S2.2 alle Dokumente; S2.3 nur die Hauptperiode
  (Februar 2021 gegen Dezember 2021 bis 2024, beschreibend).

### 8.3 H17.3 Bundespolitisches Vokabular

- **Hypothese**: Der Anteil der Dokumente, die einen Begriff der **Strukturkategorien** des Lexikons
  (Version 2026-11-23.1: Migration und Asyl, Klima- und Energiepolitik des Bundes, Bürgergeld und
  Sozialstaat, Gendern, Verkehrspolitik des Bundes, Wohnungs- und Bodenpolitik des Bundes,
  Cannabispolitik) tragen, steigt von Periode zu Periode: 2014-2020 < 2020-2025 < 2025-.
- **Maß**: Anteil je Wahljahr: Dokumente mit Text und Treffer in Titel oder Text / Dokumente mit Text.
- **Test**: **Jonckheere-Terpstra** für geordnete Alternativen über die zwölf Wahljahre in drei Gruppen
  (6, 5, 1), exakt über alle 12!/(6! · 5! · 1!) = 5 544 Zuordnungen, einseitig steigend. Rangtest ohne
  Normalitätsannahme; die geordnete Alternative ist die These. Bekannte Schwäche: Autokorrelation
  zwischen benachbarten Jahren macht ihn etwas zu liberal; dagegen stehen Holm und die Sensitivitäten.
- **Effekt**: Anteil je Periode (über die Dokumente gepoolt) und Differenz der laufenden zur ersten
  Periode in Prozentpunkten.
- **Schwelle**: Holm über die Familie. **Gültigkeit**: gewertet wird erst, wenn das Lexikon die
  Präzision ≥ 0,9 erreicht (Kriterium des Briefings, § 4); bis dahin heißt das Ergebnis „vorläufig".
- **Warum die Ereigniskategorien nicht zählen**: Corona, der Krieg gegen die Ukraine und die
  Energiekrise gab es vor 2020 nicht; mit ihnen stiege der Anteil mechanisch. Die Strukturkategorien
  sind Gegenstände, die es in allen drei Perioden gab — ihre Begriffe aber teilweise nicht (Bürgergeld
  ab 2023, Deutschlandticket ab 2023; umgekehrt Hartz IV und Pkw-Maut früher). Das Lexikon misst
  darum die **Präsenz der Bundesagenda** in den Dokumenten, nicht ihre Ursache; „Nationalisierung" im
  Sinne von Barari und Simko (2025) ist eine Lesart, kein Befund dieses Tests.
- **Sensitivität**: S3.1 nur Titel und die ersten 2 000 Zeichen des Texts (gegen längere Dokumente);
  S3.2 alle zehn Kategorien einschließlich der Ereignisse; S3.3 je Kategorie (explorativ, ohne
  Korrektur); S3.4 politische Dokumente und Verwaltung getrennt.

### 8.4 Nicht vorab festgelegt

Die Ereignisspuren (Hochwasser Juli 2021, Pandemie 2020/21, Energiekrise 2022) in den Monatsreihen je
Gremium sind **explorativ** und stehen so im Dokument und auf der Seite.
