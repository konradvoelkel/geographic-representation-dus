# Vorhaben 11: Struktur der Dokumente

Stand 2026-11-23, Stufe 1. Briefing: [plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md),
§ 11. Messskript: [11-struktur-messung.py](11-struktur-messung.py). Branch `feat/11-struktur`.

**Urteil, vorläufig: bauen.** Validierung ausstehend: die 200 Dokumente der Stichprobe sind gezogen, das
Codebuch steht, die Kodieraufgaben liegen lokal; kodiert haben die Kodier-Agenten noch nicht (§ 4, § 5).

Alle Zahlen sind am 2026-11-23 gemessen, an der Rohtext-Messdatei (pypdf 7.1.0, Groß- und
Kleinschreibung, Zeilen, Seitenwechsel als `\f`, Vorlagenkopf nicht abgeschnitten) und am Korpus nach
`georep run` im Worktree. Nachrechnen, mit den Lastregeln des Supervisors vom selben Tag:

```bash
export POLARS_MAX_THREADS=4 OMP_NUM_THREADS=2
nice -n 10 uv run python docs/plans/11-struktur-messung.py              # alle Zahlen, rund eine Minute
nice -n 10 uv run python docs/plans/11-struktur-messung.py --aufgaben   # dazu Stichprobe und Kodieraufgaben
```

Laufzeit des Skripts: 54 s Wanduhr, 1,35 GB Spitzenspeicher, ein Prozess, unter Fremdlast (`uptime`:
7,5 / 12,5 / 26,4 beim Start, 9,9 am Ende; ein Lauf bei 15,7 / 23,7 / 37,0 brauchte 60 s); das
Regelwerk allein braucht 15 bis 24 s für die 19 092 Dokumente der Hauptperiode, je nach Last (rund 1 ms
je Dokument, reines Python mit `re`). Die Stichprobe und die Kodieraufgaben sind bytegleich über Läufe
(SHA-256 von `aufgaben.jsonl` vor und nach dem letzten Lauf gleich).

## 1. Frage und Nutzen

Welche Teile hat ein Ratsdokument, und lassen sie sich zuverlässig als Spannen nach F3 auszeichnen:
Kopf (Amt oder Institut, Beratungsfolge mit Gremium, Sitzungsdatum und Beratungsqualität,
Amtsbezeichnung der Dezernentin oder des Dezernenten), Betreff, Beschlussvorschlag, Sachdarstellung,
Begründung, Fragen einer Anfrage, Finanzen, Klima?

**Ratsarbeit.** Ein Vorlagenspiegel liest zuerst den Beschlussvorschlag und die Finanzen; wer eine Vorlage
in der Fraktion vorbereitet, will wissen, welche Gremien sie wann und mit welcher Qualität berät
(Vorberatung, Anhörung der Bezirksvertretung, Entscheidung). Beides steht in jedem Dokument der
Verwaltung, aber nur als Text.

**Zulieferer.** 16 braucht die Stelle eines Treffers (Titel, Betreff, Beschlussvorschlag, Rest), 20 die
Abschnitte als Eingabe einer Kurzfassung, 21 den Abschnitt Finanzen und den Beschlussvorschlag (ein
Betrag im Beschluss ist eine Entscheidung, einer in der Sachdarstellung oft nur Hintergrund), 24 das
adressierte Amt. Mit der Beratungsfolge im Kopf bekommt 14 zu jedem Dokument die geplante Folge der
Sitzungen, ohne den Netzlauf aus F6.

**Literatur.** Die Strukturerkennung selbst ist Handwerk; der Maßstab ist Grimmer und Stewart (2013):
eine Regel, die nicht gegen eine kodierte Stichprobe geprüft ist, ist eine Behauptung (§ 4).

## 2. Datenlage

| Datei | Inhalt | Größe |
|---|---|---|
| `messdaten/rohtext/duesseldorf.parquet` | Hauptperiode 2020–2025: 19 092 PDFs, 55 402 931 Zeichen, 39 965 Seiten, 12 570 Dokumente mit Seitenwechsel; 60 mit leerem Text | 17,0 MB |
| `messdaten/rohtext/2014-2020.parquet` | 22 116 PDFs, 73 397 634 Zeichen, 50 861 Seiten | 21,8 MB |
| `messdaten/rohtext/2025.parquet` | laufende Periode: 4 088 PDFs, 10 907 491 Zeichen, 8 265 Seiten | 3,3 MB |
| `messdaten/rohtext/moenchengladbach.parquet` | 658 PDFs (nur ein Teil der Dokumente liegt lokal), 3 571 264 Zeichen, 2 485 Seiten | 1,1 MB |
| `data/duesseldorf/interim/papers.parquet` | Korpus: `id`, `reference`, `date`, `paper_type`, `file_name` (Schlüssel zur Messdatei über `name`) | |
| `data/duesseldorf/raw/beratungsfolge.parquet` | OParl-Beratungsfolge der Hauptperiode (`id`, `consultation_organizations`), Paket aus Punkt 58 | |
| `snapshots/2014-2020/raw/papers.jsonl`, `snapshots/2025/raw/papers.jsonl`, `reference/moenchengladbach/raw/papers.jsonl` | Metadaten der anderen Profile, nur gelesen | |

Spalten der Messdatei: `name` (PDF-Dateiname), `text`, `pages`, `chars`, `extractor`
(`pypdf-7.1.0 roh`), `pdf_sha256`, `error`. Die Dokumente sind öffentliche Ratsdokumente aus dem
Ratsinformationssystem; ins Repo kommen aus diesem Vorhaben nur IDs, Labels und Muster, keine Texte.

Die Dokumentarten (`paper_type`) fasst das Skript wie `weights.paper_type` zusammen: jede Fraktionsvariante
von „Antrag …", „Anfrage …", „Haushaltsantrag …" ist eine Art, die Eingaben nach § 24 GO sind eine. So
entstehen in der Hauptperiode zwölf Arten (Tabelle in § 3.1).

## 3. Messung

### 3.1 Katalog der Überschriften je Dokumentart

Gezählt sind Zeilen der Form „Label:" (Großbuchstabe am Anfang, höchstens 60 Zeichen, Doppelpunkt), je
Dokument einmal, als Anteil der Dokumente der Art. Gezeigt ist, was in mindestens 2 % der Dokumente
steht, ohne die Zeilen, die ersichtlich Satzanfänge sind.

| Art (Dokumente) | Überschriften, Anteil in % |
|---|---|
| Antrag (4 760) | Betrifft 99, Begründung 94, **Antrag 73**, Anlagen 2 |
| Beschlussvorlage (3 996) | Betrifft 100, Fachbereich 99, Beratungsfolge 99, Dezernentin / Dezernent 99, Sachdarstellung 94, **Beschlussdarstellung 91**, Anlagen 54, Begründung 20, Nachrichtlich 18, **Beschlussentwurf 7**, Beschlusslage 4, Finanzierungsart 3, Auswirkungen auf die Jugendhilfeplanung 3 |
| Anfrage (3 945) | Betrifft 98, Begründung 38, Anfrage 17, Sachdarstellung 8, Anlagen 6, Fragen 3, Sachlage 2; dazu Einleitungssätze wie „Die Verwaltung wird gebeten, folgende Fragen zu beantworten" 5 |
| Bezirksvertretung Informationsvorlage (2 699) | Betrifft 100, Beratungsfolge 100, Amt / Institut 100, Sachdarstellung 45, Stellungnahme der Verwaltung 26, Beschluss 25 (der zitierte Beschluss der Bezirksvertretung), Hierzu teilt die Verwaltung mit 11, Anlagen 7 |
| Bezirksvertretung Beschlussvorlage (1 473) | Betrifft 100, Beratungsfolge 100, Amt / Institut 100, **Beschlussdarstellung 95**, Sachdarstellung 60, Anlagen 7, Ansatz 6, Beschlusssumme 5 |
| Informationsvorlage (1 324) | Betrifft 100, Fachbereich 100, Beratungsfolge 100, Dezernentin / Dezernent 100, Sachdarstellung 96, Anlagen 47, Finanzierung 3 |
| Haushaltsantrag (339) | Betrifft 99, Begründung 97, **Antrag 55**, Produkt 7; Einleitung „… folgenden Haushaltsantrag" 15 |
| Berichtsvorlage (177) | Betrifft, Fachbereich, Dezernentin / Dezernent, Beratungsfolge, Sachdarstellung je 100, Berichtszeitraum 11 |
| A+F Beschluss (145) | Betrifft, Fachbereich, Beratungsfolge, **Beschlussdarstellung** je 99, Anlagen 98, Sachdarstellung 97, Beschlusslage 40, „Erfüllung der Voraussetzungen des § 13 KomHVO" in drei Schreibweisen 37, 17 und 8, Terminplan 12, Finanzierung 11 |
| Eingabe (124) | Betrifft, Fachbereich, Beratungsfolge je 100, Anlagen 93, Kurzdarstellung 58, Sachdarstellung 40, **Beschlussvorschlag 10**, **Beschlussdarstellung 6** |
| Bedarfsbeschluss (78) | Betrifft, Fachbereich, Dezernentin / Dezernent, Beratungsfolge, **Beschlussdarstellung**, Sachdarstellung je 100, Anlagen 96, Beschlusslage 18 |
| Beschlussvorlage RPA (32) | Betrifft, Fachbereich, Amtsleitung, Beratungsfolge, **Beschlussdarstellung**, Sachdarstellung je 100 |

Was das heißt:

- **Die Stadt nennt den Beschlussvorschlag „Beschlussdarstellung"**, in der Bauleitplanung
  „Beschlussentwurf", in Eingaben „Beschlussvorschlag"; Fraktionen schreiben „Antrag:" oder leiten mit
  einem Satz ein (§ 3.4).
- **Der Kopf ist ein Formular.** Vorlagen der Verwaltung tragen in fester Folge
  `X öffentlich / nicht öffentlich`, den Formulartitel („Beschlussvorlage", „Informationsvorlage",
  „Bericht"), `Betrifft:`, `Fachbereich:` (Vorlagen der Bezirksverwaltung: `Amt / Institut:`),
  `Dezernentin / Dezernent:` und `Beratungsfolge:` mit der Tabelle `Gremium Sitzungsdatum
  Beratungsqualität`. Anträge und Anfragen sind Briefe: Absender, `<Ort>, <Datum>`, Adressat,
  „Antrag zur Sitzung der Bezirksvertretung 5 am 24. Juni 2025", `Betrifft:`, Anrede, Text,
  Grußformel, Unterschrift.
- **„Finanzielle Auswirkungen" ist kein Formularfeld** in dieser Stadt: als Überschrift in 120 Dokumenten
  (0,6 %), „Finanzierung:" in 157 (0,8 %). **„Klimarelevanz" gibt es gar nicht**: „Klimarelevanz:" und
  „Klimaschutz:" in 0 Dokumenten, „Klimaanpassung:" in 3. Mönchengladbach hat Finanzen und
  Klimaauswirkungen als Formularfelder (§ 3.6).
- **„A+F Beschluss" heißt „Ausführungs- und Finanzierungsbeschluss"**: 144 der 145 Texte sagen es
  wörtlich, keiner nennt „Anregungen und Beschwerden". Der Kommentar in `profiles/duesseldorf.toml`
  (`admin_types`, „Ausschuss für Anregungen und Beschwerden") ist falsch, und das Briefing von 14
  rechnet „Anfrage → A+F Beschluss" als Antwortpaar (Frage 9.1).

### 3.2 Das Regelwerk

Das Skript enthält den Entwurf der Profilblöcke als TOML (`ENTWURF`), so wie sie in Stufe 2 ins Profil
kommen; der Code kennt kein Stadtwort (der Ort der Datumszeile kommt als `{city}` aus dem Block). Je
Dokument:

1. **Zeilen** mit Zeichenpositionen; Zeilenumbruch und Seitenwechsel trennen.
2. **Überschriften**: eine Zeile `Label: Rest`, deren Label in `labels` steht, öffnet einen Abschnitt der
   dort genannten Art. Der Text beginnt hinter dem Doppelpunkt oder, wenn dort nichts steht, in der
   nächsten Zeile. Wo eine Stadt den Doppelpunkt weglässt, nennt `heading_nocolon` die Labels
   (Mönchengladbach: `Fachbereich  FB 50 …`, `Beratungsfolge`).
3. **Zwei Ebenen.** Ein Abschnitt der Ebene 1 endet an der nächsten Überschrift der Ebene 1. Finanzen und
   Klima sind in Düsseldorf Ebene 2: sie öffnen eine eigene Spanne, schließen aber den umgebenden
   Abschnitt nicht, weil die Kosten eines Ausführungsbeschlusses („Kosten: … Gesamtkosten: …") im
   Beschlussvorschlag stehen.
4. **Einleitungssätze** (`leads`): eine Zeile, die mit Doppelpunkt endet und (mit den zwei Zeilen davor)
   etwa „… beschließen zu lassen:", „… zur Abstimmung zu bringen:", „… folgenden Haushaltsantrag:"
   enthält, öffnet den Beschlussvorschlag ab der nächsten Zeile; „… folgende Fragen zu beantworten:"
   öffnet die Fragen. Ein Einleitungssatz in einem schon offenen Abschnitt derselben Art und in einem
   zitierten Beschluss (`lead_blocked_in`) zählt nicht.
5. **Beschlusssatz** (`fallback`): hat ein Dokument einer Art mit erwartetem Beschlussvorschlag keinen,
   wird in den zwölf Zeilen nach dem Kopf ein Satz wie „Die Bezirksvertretung 5 bittet die Verwaltung …"
   oder „Der Rat beschließt …" gesucht; er gehört selbst zum Abschnitt. Derselbe Satz beendet einen
   Betreff, der sonst in den Antragstext liefe.
6. **Endmarken**: Grußformel, „gez.", „Sehr geehrte" schließen jeden offenen Abschnitt.
7. **Betreff**: endet an der ersten Leerzeile nach Text oder nach vier Zeilen.
8. **Kopf**: aus den Abschnitten `kopf_*` und den ersten 30 Zeilen: Amt (Nummer und Name), Amtsbezeichnung
   im Feld „Dezernentin / Dezernent" (**die Spanne deckt nur die Bezeichnung**, der Name dahinter wird
   nie gelesen), je Zeile der Beratungsfolge Gremium, Datum und Qualität, in Briefen die Sitzung
   („zur Sitzung der … am …") und das Briefdatum, der Formulartitel, im Unterschriftsblock eine
   Amtsbezeichnung aus einer Liste (`signer_roles`), nie ein Name.

Ausgabe sind Spannen nach F3: `id, start, end, kind, value, norm, section, extractor`, für Abschnitte
`kind = "abschnitt"`, `value` das Label wie geschrieben, `norm` und `section` die Abschnittsart; für
Kopffelder `kind` = `amt`, `dezernat`, `beratung`, `sitzung`, `datum`, `formular`, `unterzeichner`,
`section = "kopf"`. Auf der Hauptperiode sind es **137 443 Spannen**; der Vertrag
`0 <= start < end <= len(text)` hält für alle Spannen aller vier Profile (das Skript prüft ihn).

### 3.3 Abdeckung je Art

Anteil der Dokumente mit mindestens einer Spanne der Art, Hauptperiode, alle 19 092 Dokumente (die 60 ohne
Text eingeschlossen).

| Art | n | Betreff | Beschluss­vorschlag | Sach­darstellung | Begrün­dung | Fragen | Amt | Dezer­nat | Beratung | Sitzung | Brief­datum |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Antrag | 4 760 | 98,5 | 96,9 | 0,3 | 94,1 | 0,3 | 0 | 0 | 0 | 65,1 | 98,8 |
| Beschlussvorlage | 3 996 | 99,6 | 97,6 | 93,7 | 20,5 | 0,1 | 98,7 | 98,7 | 98,6 | 0 | 0 |
| Anfrage | 3 945 | 97,6 | 0,4 | 10,0 | 35,2 | 78,6 | 0 | 0 | 0 | 68,2 | 98,4 |
| BV-Informationsvorlage | 2 699 | 99,8 | 0,5 | 44,8 | 0,1 | 0,3 | 100,0 | 0 | 99,8 | 3,7 | 0 |
| BV-Beschlussvorlage | 1 473 | 100,0 | 95,5 | 62,2 | 0,8 | 0 | 100,0 | 0,1 | 99,9 | 0 | 0,1 |
| Informationsvorlage | 1 324 | 99,8 | 0,1 | 95,9 | 0,1 | 0,2 | 99,8 | 99,8 | 99,7 | 0,5 | 0 |
| Haushaltsantrag | 339 | 99,1 | 98,5 | 0 | 97,3 | 0 | 0 | 0 | 0 | 61,1 | 99,4 |
| Berichtsvorlage | 177 | 100,0 | 1,1 | 100,0 | 0,6 | 0 | 100,0 | 100,0 | 100,0 | 0 | 0 |
| A+F Beschluss | 145 | 99,3 | 98,6 | 84,8 | 0 | 0 | 99,3 | 97,9 | 99,3 | 0 | 0 |
| Eingabe | 124 | 99,2 | 18,5 | 98,4 | 0,8 | 0 | 100,0 | 0 | 96,8 | 0 | 0 |
| Bedarfsbeschluss | 78 | 100,0 | 100,0 | 100,0 | 0 | 0 | 100,0 | 100,0 | 100,0 | 0 | 0 |
| Beschlussvorlage RPA | 32 | 100,0 | 100,0 | 100,0 | 0 | 0 | 100,0 | 0 | 100,0 | 0 | 0 |
| **alle** | 19 092 | 99,0 | 55,3 | 42,3 | 36,9 | 16,4 | 52,3 | 29,7 | 52,3 | 32,0 | 46,8 |

Weitere Spalten des Skripts: Stellungnahme der Verwaltung 37,5 % der BV-Informationsvorlagen, zitierter
Beschluss (`beschlusslage`) 25,4 % ebenda und 52,4 % der A+F Beschlüsse, Anlagen 20,4 % aller Dokumente,
Finanzen 2,0 %, Klima 0,0 %, Formulartitel 62,8 %. Die Bezirksvertretungen haben kein Dezernentenfeld,
darum fehlt das Dezernat dort (kein Fehler der Regel).

### 3.4 Beschlussvorschlag

Arten **mit erwartetem Beschlussvorschlag**: Beschlussvorlage, BV-Beschlussvorlage, A+F Beschluss,
Bedarfsbeschluss, Beschlussvorlage RPA, Antrag, Haushaltsantrag. **Ohne**: Informationsvorlage,
BV-Informationsvorlage, Anfrage, Berichtsvorlage. Eingaben stehen in keiner Liste: nur ein Teil trägt
einen Beschlussvorschlag (§ 3.1); gefunden in 23 von 124.

| | Dokumente mit Text | mit Beschlussvorschlag | Anteil, 95 %-Intervall (Wilson) |
|---|---|---|---|
| erwartet | 10 784 | 10 506 | 97,4 % (97,1–97,7) |
| davon Antrag | 4 725 | 4 611 | 97,6 % |
| davon Beschlussvorlage | 3 993 | 3 901 | 97,7 % |
| davon BV-Beschlussvorlage | 1 473 | 1 407 | 95,5 % |
| davon Haushaltsantrag / A+F / Bedarfsbeschluss / RPA | 338 / 145 / 78 / 32 | 334 / 143 / 78 / 32 | 98,8 / 98,6 / 100 / 100 % |
| nicht erwartet | 8 124 | 30 | 0,4 % (0,3–0,5) |

- **Woher**: Überschrift 9 236 (87,9 %), Einleitungssatz 927 (8,8 %), Beschlusssatz 343 (3,3 %).
- **Länge**: Median 302 Zeichen, 10 % unter 128, 10 % über 1 019; 73 Spannen (0,7 %) über 4 000 Zeichen
  (Verdacht auf ein fehlendes Ende); 49 Dokumente (0,5 %) mit mehr als einer Spanne (Beschlussdarstellung
  vorn, Beschlussentwurf auf Seite 3).
- **Die 278 ohne Fund**: in 104 steht nach dem Kopf weniger als 80 Zeichen Text — der Rumpf ist nicht in
  der Textebene des PDFs (gehäuft Anträge einer Bezirksvertretung, deren Brief nach dem Betreff nur
  „Seite 2", „Seite 3" ergibt, etwa BV8/198/2024, BV8/241/2022). Das ist ein Befund über die PDFs, nicht
  über die Regel; ohne sie findet die Regel 10 506 von 10 680 (98,4 %).
- **Wo die Regel scheitert** (174 Dokumente; Beispiele aus der Durchsicht, mit den endgültigen Regeln
  nachgeprüft; das Skript druckt zwölf weitere mit Seed 20261123; Personennamen weggelassen):
  - Bitte ohne Doppelpunkt, Antrag in Prosa: „wir bitten Sie, nachfolgenden Antrag auf die Tagesordnung …
    zu nehmen und prüfen zu lassen." (BV8/109/2024); „… zu nehmen:" und dann erst die Begründung, der
    Beschlusssatz („Daher bittet die Bezirksvertretung die Verwaltung …") steht mitten im Text
    (BV8/118/2022, BV8/117/2022).
  - Überschriften ohne Doppelpunkt in einer eigenen Zeile: „Beschlussvorlage" und „Begründung" in einem
    Antrag (BV3/062/2021).
  - Vorlagen ohne Beschlusstext im PDF: Plankommentare zum Haushalt („Plankommentare zu den Produkten des
    Dezernats 01", ADIG/024/2023, AWIR/086/2023), eine Richtlinie als Anlage (BV10/185/2020).
  - Beschlusssatz ohne Gremium am Satzanfang („Damit … beauftragt die Bezirksvertretung 5 die Verwaltung
    … mit folgenden Maßnahmen:", BV5/093/2021).
- **Die 30 Funde in Arten ohne erwartetem Vorschlag** sind zum Teil richtig: der Server führt manche
  Anträge als „Anfrage" (KUA/045/2021 „Anfrage CDU/Grüne" mit „Antrag: Die Kulturverwaltung wird
  beauftragt …", OVA/055/2023). Falsch sind Fragen, die der Brief „zur Abstimmung" stellt (GLA/031/2021),
  und die zitierte „Beschlussempfehlung" einer Kommission in einem Bericht (RAT/084/2024). Zwei Fälle
  der Art „fasste folgenden Beschluss: … zu beschließen:" (BV7/007/2025, BV7/008/2025) fängt
  `lead_blocked_in` ab.

### 3.5 Kopf

- **Beratungsfolge**: 13 536 Zeilen in 9 976 Dokumenten; je Dokument 1 Zeile 8 380-mal, 2 Zeilen 753-mal,
  bis zu 28. Beratungsqualität: Entscheidung 5 705, Kenntnisnahme 4 882, Vorberatung 1 899, Anhörung 939,
  ohne Angabe („-", Eingaben) 111. Die Qualität ist ein geschlossener Katalog von vier Werten.
- **Sitzungsdatum plausibel** (14 Tage vor bis 400 Tage nach dem Dokumentdatum): 13 478 von 13 536
  (99,6 %, 99,4–99,7).
- **Amt**: 98,7 bis 100 % der Vorlagen der Verwaltung; Form „52 - Sportamt", „01/17 - Büro für …",
  „Bezirksverwaltungsstelle 10". Anträge und Anfragen haben kein Amtsfeld.
- **Dezernat**: Amtsbezeichnung in 5 665 Dokumenten, keine ohne erkannte Bezeichnung: Beigeordnete 2 203,
  Beigeordneter 1 417, Stadtdirektor 1 185, Stadtkämmerin 541, Oberbürgermeister 319. Die Bezeichnung
  allein nennt das Dezernat nicht (es gibt mehrere Beigeordnete); das Amt mit seiner Nummer tut es, und
  24 braucht beides.
- **Unterzeichner**: 6 802 Dokumente haben Grußformel oder „gez.", aber nur 332 (4,9 %) eine
  Amtsbezeichnung im Unterschriftsblock (Fraktionsvorsitzender 212, Ratsherr 74, Ratsfrau 29, …). In den
  Vorlagen der Verwaltung findet die Regel keine (0,0 %), sie tragen keine Unterschrift. Das Feld ist also fast leer; wer eine Person zum
  Dokument braucht (27), nimmt OParl, nicht den Text.
- **Briefe**: Briefdatum 98,8 % der Anträge, 98,4 % der Anfragen; Sitzung („zur Sitzung der … am …")
  65,1 % und 68,2 %.
- **Formulartitel**: in 62,8 % aller Dokumente, in den Vorlagen der Verwaltung zu 98,7 bis 100 %.

### 3.6 Übertrag auf die anderen Profile

Dasselbe Skript, dieselben Regeln, ohne neue Muster; nur für 2014–2020 und Mönchengladbach je ein
zweiter Block (unten). Beschlussvorschlag „erwartet" hier über alle Dokumente einschließlich derer ohne
Text, darum etwas unter § 3.4.

| Profil | Regeln | n | Betreff | Beschluss­vorschlag (erwartet) | … (nicht erwartet) | Amt | Beratung | Qualität | Finanzen | Klima |
|---|---|---|---|---|---|---|---|---|---|---|
| Hauptperiode | duesseldorf | 19 092 | 99,0 | 97,1 von 10 823 | 0,4 von 8 145 | 52,3 | 52,3 | 51,7 | 2,0 | 0 |
| 2014–2020 | duesseldorf | 22 116 | 46,4 | 96,1 von 2 410 | 0,6 von 1 834 | 34,4 | 43,3 | 10,6 | 1,2 | 0 |
| 2014–2020 | duesseldorf-2014 | 22 116 | 78,9 | 96,1 von 2 410 | 0,6 von 1 834 | 34,4 | 60,0 | 10,7 | 1,2 | 0 |
| laufende Periode | duesseldorf | 4 088 | 99,5 | 97,5 von 2 163 | 1,1 von 1 862 | 50,7 | 50,6 | 49,4 | 1,3 | 0 |
| Mönchengladbach | duesseldorf | 658 | 0 | – | – | 0 | 0 | 0 | 0,5 | 0 |
| Mönchengladbach | moenchengladbach | 658 | 85,4 | 85,4 von 465 | 0,5 von 193 | 51,8 | 74,2 | – | 49,1 | 2,6 |

- **Laufende Periode**: trägt ohne Änderung (dasselbe Formular).
- **2014–2020**: 81 % der Dokumente mit Text heißen „Vorlage aus der Politik" (9 538) oder
  „Verwaltungsvorlage" (8 309) und sagen nicht, ob Beschluss oder Information; die Prozentzahlen
  „erwartet" beziehen sich darum nur auf die 2 410 Dokumente mit heutigen Artnamen. **Der Formulartitel im Kopf löst das**:
  Verwaltungsvorlagen sind zu 46,9 % „Beschlussvorlage", zu 37,3 % „Informationsvorlage", 14,7 % ohne
  Titel; Vorlagen aus der Politik zu 34,6 % „Antrag", 28,3 % „Anfrage", 36,4 % ohne Titel. Das Formular
  von damals hat die Beratungsfolge am Ende der ersten Seite mit der Spalte **„Ergebnis"** statt
  „Beratungsqualität" (11 678 Dokumente gegen 2 288; in 62,3 % davon steht „-/-" hinter dem
  Sitzungsdatum, weil das Ergebnis bei Drucklegung fehlte), und die Vorlagen aus der Politik
  tragen den Betreff ohne „Betrifft:" unter dem Formulartitel. Der Block `duesseldorf-2014` erbt alles
  und ändert genau das: Betreff 46,4 → 78,9 %, Beratungszeilen 43,3 → 60,0 %. In den 2 404 Dokumenten
  mit heutigen Artnamen und Text findet die Regel den Beschlussvorschlag in 2 316 (96,3 %, 95,5–97,0;
  ohne leeren Rumpf 98,1 %).
- **Mönchengladbach**: mit den Düsseldorfer Regeln nichts — anderes Formular: `TOP:` oder
  `Beratungsgegenstand:` statt „Betrifft", `Beschlussentwurf:`, `Finanzwirksamkeit:` (98 % der
  Beratungsvorlagen), `Auswirkung auf die Kinder- und Familienfreundlichkeit:` (98 %),
  `Auswirkungen auf Klima und Umwelt:` (Klima in 2,6 % der Dokumente), `Zur Kenntnisnahme:` in
  Berichtsvorlagen (89,6 %), `Fachbereich  FB 50 …` ohne Doppelpunkt, eine Beratungsfolge ohne Qualität. Mit eigenem Block:
  Beratungsvorlagen 98,5 % Beschlussvorschlag; Fraktionsanträge nur 71,1 %, weil
  viele nur ein Deckblatt sind und der Antrag als Anlage kommt („Anlage/n: Fraktionsantrag …", 36 der 60
  ohne Fund haben nach dem Kopf keinen Text). Das ist der Prüfstein für Stadtneutralität (§ 2.13): das
  Verfahren trägt, die Muster sind je Stadt neu zu schreiben, aus einem Katalog wie in § 3.1 (der Block
  für Mönchengladbach hat 19 Labels und zwei Muster).

### 3.7 Nebenbefunde

- **Namen der Ausschüsse ohne Eintrag im Profil** (`bodies.committees` = ""). Wo ein Dokument genau eine
  Kopfzeile und genau ein OParl-Gremium hat, stehen Name und Kürzel ohne Ausnahme zusammen:
  JHA „Jugendhilfeausschuss" (310 von 310), KUA „Kulturausschuss" (298), SCHUA „Schulausschuss" (137),
  AGS „Ausschuss für Gesundheit und Soziales" (96), HFA „Haupt- und Finanzausschuss" (69), AWM „Ausschuss
  für Wohnungswesen und Modernisierung" (36). SEBD steht 142-mal mit „Bauausschuss", das das Profil schon
  BAU nennt (dieselbe Organisation gr/17, Kommentar im Profil). Frage 9.2.
- **Größe der Ausgaben**: alle Spannen der Hauptperiode als Parquet (zstd) 0,9 MB; die Kopfspannen
  (56 543) als CSV ohne Offsets 7,7 MB — als Download zu groß, als Parquet klein (§ 7).

## 4. Validierung

### 4.1 Was ohne Kodierer schon prüfbar ist (deterministisch und aus den Daten)

- **Gremium der Beratungsfolge gegen OParl** (Labels aus den Daten selbst, § 2.6 (2)): 9 894 Dokumente
  haben Kopfzeilen und eine OParl-Beratungsfolge, zusammen 13 454 Kopfzeilen. 10 867 davon (80,8 %)
  tragen einen Gremiumsnamen, den das Profil einem Kürzel zuordnet (Rat, Bezirksvertretung *n*, die
  benannten Ausschüsse und Beiräte). **10 404 dieser 10 867 (95,7 %, 95,3–96,1) stehen in der
  OParl-Beratungsfolge desselben Dokuments.** Das ist eine untere Schranke der Präzision: OParl hält die
  tatsächliche Beratung, der Kopf die geplante, und eine vertagte oder umgeleitete Vorlage weicht ab,
  ohne dass die Regel falsch liest. Umgekehrt stehen 10 364 von 10 567 benannten OParl-Gremien (98,1 %)
  im Kopf.
- **Sitzungsdatum plausibel**: 99,6 % (§ 3.5).
- **Vertrag der Spannen**: hält für alle 137 443 Spannen der Hauptperiode und alle Spannen der anderen
  Profile.
- **Kein Personenname**: Dezernat ist zu 100 % einer von fünf Titeln; Unterzeichner einer aus der Liste.

### 4.2 Stichprobe, Codebuch, Kodieraufgaben (vorbereitet, nicht kodiert)

**Stichprobe**: 200 Dokumente der Hauptperiode mit Text, geschichtet nach den zwölf Arten,
proportional mit mindestens 8 je Schicht, Rest nach größtem Bruchteil, Seed 20261123
([../../validierung/11-struktur/stichprobe.csv](../../validierung/11-struktur/stichprobe.csv): `id`,
`schicht`, `gewicht` = Dokumente der Schicht durch Stichprobe der Schicht).

| Schicht | Dokumente mit Text | Stichprobe | Gewicht |
|---|---|---|---|
| Antrag | 4 725 | 34 | 138,97 |
| Beschlussvorlage | 3 993 | 30 | 133,10 |
| Anfrage | 3 924 | 29 | 135,31 |
| BV-Informationsvorlage | 2 699 | 23 | 117,35 |
| BV-Beschlussvorlage | 1 473 | 16 | 92,06 |
| Informationsvorlage | 1 324 | 15 | 88,27 |
| Haushaltsantrag | 338 | 10 | 33,80 |
| Berichtsvorlage | 177 | 9 | 19,67 |
| A+F Beschluss | 145 | 9 | 16,11 |
| Eingabe | 124 | 9 | 13,78 |
| Bedarfsbeschluss | 78 | 8 | 9,75 |
| Beschlussvorlage RPA | 32 | 8 | 4,00 |

115 der 200 gehören zu Arten mit erwartetem Beschlussvorschlag; 76 zu Arten ohne (sie prüfen, dass die
Regel dort keinen erfindet), 9 sind Eingaben. Die 60 Dokumente ohne Text sind nicht in der Stichprobe (ihr Ausfall ist in § 3.4
gezählt), die mit leerem Rumpf nach dem Kopf schon.

**Codebuch**: [../../validierung/11-struktur/codebuch.toml](../../validierung/11-struktur/codebuch.toml).
Einheit Dokument; Fragen: Beschlussvorschlag vorhanden, erste und letzte Zeile, mehrteilig; Amt wie
geschrieben; Amtsbezeichnung im Dezernentenfeld (Auswahl, nie ein Name); die Zeilen der Beratungsfolge
(Gremium, Datum, Qualität); Sitzung und Briefdatum in Briefen; unsicher mit Bemerkung. Die Grenzen des
Beschlussvorschlags sind festgelegt: ohne Überschrift und ohne die Bitt- oder Einleitungsformel des
Antragstellers, mit dem Beschlusssatz selbst; Ende vor der nächsten Überschrift, Grußformel oder
Unterschrift; Kostenaufstellungen im Beschluss gehören dazu; leere Zeilen und Seitenkopfzeilen sind nie
erste oder letzte Zeile.

**Kodieraufgaben**: `/media/konrad/xtraspace/georep/messdaten/kodierung/11-struktur/aufgaben.jsonl`
(200 Zeilen, 785 KB, lokal, nicht im Repo): je Aufgabe ID, Drucksache, Dokumentart, der Rohtext als Liste
von Zeilen (höchstens 600; 4 Dokumente sind gekürzt), die Zeilen mit Seitenanfang. Die Reihenfolge ist
gemischt (Seed 20261124), damit kein Kodierer Schicht für Schicht arbeitet. Daneben `regel.jsonl` mit der
Ausgabe der Regeln in denselben Zeilennummern — **den Kodierern nicht zeigen** (blind, § 5 des Plans) —
und ein README. Antworten kommen als `antworten-<kodierer>.jsonl` daneben; das Format steht im
Codebuch. F4 baut den Rahmen parallel; das Format hier ist vorläufig und so gewählt, dass F4 es aus
`stichprobe.csv` neu erzeugen oder übernehmen kann.

**Maße** (Codebuch, `[mass]`): Beschlussvorschlag richtig, wenn „vorhanden" stimmt und bei ja erste und
letzte Zeile gleich sind (streng; mild mit einer Zeile Toleranz daneben); Anteil über die Stichprobe mit
Wilson-Intervall, dazu mit den Schichtgewichten hochgerechnet. Kopf: Präzision je Feld (Amt, Dezernat,
Beratungszeile als Tripel, Sitzung, Briefdatum), Recall daneben. Krippendorffs α zwischen den
Kodierern je Frage.

**Was die Stichprobe auflösen kann**: das Kriterium sagt „in mindestens 90 % der Stichprobe", also
mindestens 180 von 200 richtig. Bei 180 reicht das Wilson-Intervall von 85,1 bis 93,4 %, bei 190 von
91,0 bis 97,3 %. Wer die Aussage „mindestens 90 % im Korpus" will, braucht rund 190 richtige.

### 4.1 Ergebnis der Kodierung (2026-11-23, Supervisor)

Zwei Kodier-Agenten (Opus) haben die 200 Dokumente unabhängig nach `codebuch.toml` kodiert, ein
Schlicht-Agent hat die eine Uneinigkeit entschieden (Aufgabe 128, Feld `sitzung`: Gremium
ausgeschrieben, wie Kodierer B). Kein menschlicher Goldstandard. Labels je Aufgabe und Feld:
`validierung/11-struktur/labels.csv` (Werte als JSON; drei Zeilen des Meta-Felds `unsicher` bleiben
ohne Label).

**Übereinstimmung**: in `bv_vorhanden`, `bv_erste_zeile`, `bv_letzte_zeile` (114 Dokumente mit
Vorschlag, zeilengenau), `amt`, `dezernat_titel`, `beratungsfolge` und `briefdatum` 200 von 200
(α = 1,0), in `sitzung` 199 von 200 (α = 0,99). So hohe Übereinstimmung spricht für eindeutige
Formulare; sie misst Zuverlässigkeit, nicht Wahrheit — beide Kodierer sind dasselbe Modell.

**Regelentwurf `struktur-entwurf-1` gegen die Labels:**

| Maß | Ergebnis | Wilson 95 % | Kriterium |
|---|---|---|---|
| Beschlussvorschlag richtig, streng (Zeile genau) | 188 / 200 = 0,940 | 0,898–0,965 | ≥ 0,90: **erfüllt** |
| dasselbe, mild (± 1 Zeile) | 190 / 200 = 0,950 | | |
| Kopf: Amt | 125 / 125 = 1,000 | 0,970–1,000 | ≥ 0,95: erfüllt |
| Kopf: Dezernat (Amtsbezeichnung) | 69 / 69 = 1,000 | 0,947–1,000 | erfüllt |
| Kopf: Beratungsfolge (Gremium, Datum, Qualität) | 160 / 168 = 0,952 | 0,909–0,976 | erfüllt, knapp |
| Kopf: Briefdatum | 73 / 73 = 1,000 | 0,950–1,000 | — |
| Kopf: Sitzung, Datum | 48 / 48 = 1,000 | 0,926–1,000 | — |
| Kopf: Sitzung, Gremium und Datum wörtlich | 27 / 48 | | — (Gremium im Genitiv oder abgekürzt) |

Die 12 Fehler beim Beschlussvorschlag liegen fast alle am **Ende** (die Regel nimmt Zeilen nach dem
Vorschlag mit: Haushaltsanträge, Anträge, lange Beschlussvorlagen); keiner in Anfragen,
Informations-, Berichts- und BV-Beschlussvorlagen. Der Gremienname der Sitzung muss in Stufe 2 über
die Gremien des Profils normalisiert werden (Nominativ, Kürzel ausgeschrieben), wie es die
Kodierer und der Schlichter als Lücke des Codebuchs gemeldet haben.

## 5. Urteil gegen das Kriterium: **bauen** (vorläufig, Validierung ausstehend)

**Nachtrag 2026-11-23 (Supervisor): Urteil bauen.** Die Kodierung (§ 4.1) bestätigt das Kriterium;
Stufe 2 schärft das Ende des Beschlussvorschlags und normalisiert die Gremiennamen.

Kriterium (unverändert): richtiger Beschlussvorschlag in mindestens 90 % der Stichprobe, Kopffelder mit
Präzision ≥ 0,95.

- **Beschlussvorschlag.** Was ohne Kodierer messbar ist, liegt über der Schwelle: in den Arten mit
  Vorschlag findet die Regel einen in 97,4 % (98,4 % ohne leeren Rumpf), in den Arten ohne Vorschlag
  erfindet sie einen in 0,4 %, und einige davon sind richtig. Offen ist, ob **die Grenzen** stimmen. Die
  Überschriften (87,9 % der Funde) und die Endmarken sind scharf; unsicher sind die 8,8 % aus
  Einleitungssätzen (wo beginnt der Vorschlag nach „… beschließen zu lassen:"?), die 3,3 % aus
  Beschlusssätzen, die 0,7 % mit mehr als 4 000 Zeichen und die Seitenkopfzeilen mitten im Vorschlag.
  Grob gerechnet: wenn die Grenzen in 95 % der Funde stimmen, sind in der Stichprobe 115 · 0,974 · 0,95
  + 85 · 0,996 ≈ 191 von 200 richtig. Unter 180 fiele sie erst, wenn mehr als 15 % der Grenzen falsch
  wären. Das ist eine Schätzung, kein Ergebnis.
- **Kopf.** Die Felder sind Formularfelder mit festem Label und kurzem Wert; Amt und Dezernat sind
  Zeilen hinter einem Label, die Qualität ein geschlossener Katalog. Für das Gremium liegt die untere
  Schranke aus OParl bei 95,7 % (95,3–96,1), knapp über 0,95; der Rest sind zum guten Teil echte
  Abweichungen zwischen Plan und Beratung. Das Kriterium misst die Kodierung, nicht OParl.
- **Was das Urteil umwirft**: streng unter 180, mild darüber → **umbauen** (Grenzregeln, eine Runde);
  beides unter 180 → umbauen mit Fehlerklassen aus der Schlichtung; Kopf unter 0,95 in einem Feld → das
  Feld fällt aus der Kopftabelle, die anderen bleiben. Stufe 3 (Download) wartet auf die Validierung
  und auf α ≥ 0,8 zwischen den Kodierern.

## 6. Bauplan Stufe 2

**Beitrag** `sections` im Register `georep.enrich.CONTRIBUTIONS` (F2), ein Schritt `sections`, offline,
nach `raw_texts` (F1) und dem Korpus; Ebene 0, keine Abhängigkeit von anderen Vorhaben. Reihenfolge im
Tupel: nach F1, vor 16, 20, 21, 24.

**Module** (neu): `src/georep/prep/structure.py` mit den reinen Funktionen (Zeilen, Überschriften,
Einleitungen, Beschlusssatz, Kopf; dieselben Schritte wie `analyse` im Messskript, typisiert, mit
Verträgen an den Grenzen), `src/georep/enrich/sections.py` mit dem Beitrag (Lesen, Schreiben,
`SCHEMA_VERSION = 1` als Modulkonstante für den `Step`).

**Ausgaben**:

1. `processed/dokumente_abschnitte.parquet`: Spannen nach F3, eine Zeile je Spanne, sortiert nach
   `id, start`. `id` (String, Korpus-ID), `start`, `end` (UInt32, Zeichen im Rohtext von F1), `kind`
   (`abschnitt` oder ein Kopffeld), `value` (Label wie geschrieben; bei Kopffeldern der Wert, beim
   Dezernat nur die Amtsbezeichnung), `norm` (Abschnittsart oder normalisierter Wert), `section`,
   `extractor` (Regelname und Version, etwa `struktur-1`, plus der Extraktor des Rohtexts). Gemessen
   0,9 MB für die Hauptperiode.
2. `processed/dokumente_kopf.parquet`: eine Zeile je Korpus-ID (auch ohne Text, dann leer), sortiert nach
   `id`: `formular`, `amt_nr`, `amt_name`, `dezernat_titel`, `beratungsfolge`
   (List(Struct{`gremium`, `gremium_kuerzel` aus `[bodies]`, `datum` Date, `qualitaet`})),
   `sitzung_gremium`, `sitzung_datum`, `briefdatum`, `unterzeichner_rolle`, `beschlussvorschlag`
   (Bool), `beschlussvorschlag_quelle` (`ueberschrift`, `einleitung`, `beschlusssatz`), `rumpf_leer`
   (Bool: weniger als 80 Zeichen nach dem Kopf), `extractor`. Kein Feld trägt einen Namen.

**Verträge**: F3 (`0 <= start < end <= len(text)`, sortiert); Spannen der Ebene 1 überlappen sich nicht;
`dezernat_titel` und `unterzeichner_rolle` stammen aus den Listen des Profils (Nachbedingung, so kann kein
Name durchrutschen); `dokumente_kopf` hat genau die IDs des Korpus, eindeutig; jedes `datum` ist ein
gültiges Datum; die Spanne des Dezernats endet vor dem Namen.

**Tests** (roter Test zuerst, CLAUDE.md):

- Beispiele aus **synthetischen** Texten nach dem Katalog in § 3.1 (Formularkopf, Brief mit „Antrag:",
  Brief mit Einleitungssatz, Brief mit Beschlusssatz, Informationsvorlage mit zitiertem Beschluss,
  A+F mit Kosten im Beschluss, Mönchengladbacher Formular), keine echten Dokumente mit Namen in
  `tests/fixtures/`.
- hypothesis in `tests/property/`: für beliebigen Text hält der Vertrag; Einfügen einer Überschrift der
  Ebene 2 teilt keinen Abschnitt der Ebene 1; die Ausgabe hängt nicht von `\n` gegen `\f` als Trenner ab
  (bis auf die Seitenzahl); Idempotenz über zwei Läufe.
- Golden Master unberührt (der Schritt ändert keine bestehende Datei); `test_report_city.py` bleibt grün,
  weil der Ort nur als `{city}` aus dem Profil kommt.
- `pytest -m slow`: Abdeckung der Hauptperiode gegen die Zahlen hier, als Untergrenzen (erwartet ≥ 97 %,
  nicht erwartet ≤ 1 %).

**Settings** (Anhängeregel aus `00-synergien.md`, § 2): Modell `StructureSettings` vor `class Settings`,
Feld `structure` am Ende; Block `# --- Vorhaben 11: Struktur der Dokumente` am Ende von `defaults.toml`
mit `enabled = false` und leeren Listen (stadtneutral, der Schritt ist aus); die Muster aus `ENTWURF`
in `profiles/duesseldorf.toml`, der Unterschied in `profiles/duesseldorf-2014.toml`,
`profiles/moenchengladbach.toml` eigen; `duesseldorf-2025` erbt ohne Änderung. Jeder Schlüssel mit
Kommentar und Zahl aus diesem Dokument.

**Berührte Dateien**: neu `src/georep/prep/structure.py`, `src/georep/enrich/sections.py`, Tests; je eine
angehängte Zeile oder ein Block in `src/georep/enrich/__init__.py`, `src/georep/settings.py`,
`src/georep/defaults.toml`, den drei Profilen; `docs/architecture.md` (Abschnitt Beiträge),
`docs/decisions.md` (Eintrag ohne Nummer: Regeln statt Modell; Spannen auf dem Rohtext statt auf dem
kleingeschriebenen Store; Kopf ohne Namen).

**Paket**: keins eigenes. Die Ausgaben sind in rund 20 s aus dem Rohtextpaket von F1 gerechnet und
laufen auf Pages mit; ein eigenes Paket wäre doppelt.

**Nebenarbeit, getrennt committet und nur mit Zustimmung des Supervisors**: Kommentar zu „A+F Beschluss"
im Profil berichtigen (Frage 9.1); Namen der Ausschüsse (Frage 9.2).

## 7. Bauplan Stufe 3

Keine Unterseite (Briefing). Die Kopftabelle als **Download** über das Tabellenregister von F2
(`report/tables.py`): `dokumente_kopf` mit Spaltenbeschreibung in `schema.json`. Als CSV wären es
geschätzt 5 bis 8 MB (die Kopfspannen allein 7,7 MB), darum Parquet als Download und CSV nur, wenn das
Register es verlangt; `index.html` bekommt nur die Zeile im Downloadblock (unter 1 KB). Die Seite nennt
neben der Tabelle die Validierung: „geprüft von zwei KI-Kodierern an 200 Dokumenten, nicht von Menschen",
Anteil richtiger Beschlussvorschläge und Präzision je Kopffeld mit Intervall. Die Abschnitte selbst
werden nicht veröffentlicht, nur ihre Grenzen als Zahlen (sie sind Rohtext; Frage 6 erlaubt das
Rohtextpaket, der Download braucht ihn nicht).

## 8. Vorab festgelegte Hypothesen

Keine: Vorhaben 11 ist eine Vorverarbeitung, keine Analyse.

## 9. Risiken und offene Fragen

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 9.1 | „A+F Beschluss" ist in 144 von 145 Texten ein **Ausführungs- und Finanzierungsbeschluss**, nicht der Ausschuss für Anregungen und Beschwerden; der Kommentar in `profiles/duesseldorf.toml` sagt das Gegenteil. Darf der Supervisor ihn berichtigen? | 14 rechnet „Anfrage → A+F Beschluss" als Antwortpaar; das wäre falsch | ja, eigener Commit; 14 bekommt den Befund über die Synergie |
| 9.2 | Sollen die sechs unbenannten Kürzel ihre Namen aus der Beratungsfolge bekommen (JHA, KUA, SCHUA, AGS, HFA, AWM; § 3.7)? | `fragen.md` 5.2 ist seit 2026-10 offen; die Seite zeigt bisher Kürzel | Vorschlag an Konrad, nicht in diesem Vorhaben; SEBD bleibt, wie es ist |
| 9.3 | Darf eine Spanne nach F3 eine Zusatzspalte tragen (`quelle` für ueberschrift, einleitung, beschlusssatz)? | die Validierung soll die Fehler nach Quelle trennen | nein; die Quelle steht in `dokumente_kopf` |
| 9.4 | Zählt die strenge Grenze (Zeile genau) oder die milde (± 1 Zeile) für das Kriterium? | entscheidet zwischen „bauen" und „umbauen" | streng ist das Kriterium, mild steht daneben |
| 9.5 | Gehören Eingaben zum Kriterium? Nur 18,5 % tragen einen Beschlussvorschlag. | 9 Dokumente der Stichprobe | ja, wie jede Art: richtig ist „vorhanden" wie im Text |
| 9.6 | Seitenkopfzeilen („Seite 2", „Sitzung des APS am … Vorlage Nr. …") stehen mitten in Spannen. Reicht es, sie beim Lesen eines Ausschnitts zu überspringen? | 20 und 16 lesen den Text einer Spanne | ja: Stufe 2 bringt eine Liste `page_noise` im Profil und eine Lesefunktion, die Spannen behalten die rohen Offsets |
| 9.7 | 104 Dokumente der Hauptperiode haben nach dem Kopf keinen Text in der Textebene (gehäuft BV 8). OCR? | 16 und 20 sehen dort nichts | nein, außerhalb des Vorhabens; `rumpf_leer` macht sie sichtbar |
| 9.8 | „Klimarelevanz" und „Finanzielle Auswirkungen" sind in Düsseldorf keine Formularfelder (§ 3.1). | 21 hatte mit einem Finanzabschnitt gerechnet | 21 nimmt Beträge aus Beschlussvorschlag und Sachdarstellung (über 12) und den Abschnitt `finanzen` nur, wo es ihn gibt |
| 9.9 | Der Unterzeichner als Amtsbezeichnung ist fast immer leer (4,9 % der Unterschriftsblöcke). | Briefing nennt ihn | gebaut, weil billig; keine Aussage darauf stützen |
| 9.10 | F4 ist noch nicht gemerged; Format der Aufgaben vorläufig. | Kodier-Agenten brauchen ein festes Format | F4 übernimmt `stichprobe.csv` und erzeugt die Aufgaben neu oder liest `aufgaben.jsonl` |

## 10. Änderungen durch die Synergie (füllt der Supervisor)

Übertragen am 2026-11-24 aus [00-synergien-2026-11.md](00-synergien-2026-11.md) (§ 1, § 2.1, § 2.2
Konflikte 2, 4, 5, 8 und 14, § 3 und § 4 „11 Struktur"), bevor die Stufe 2 beginnt. Wo das § 6 und
§ 7 ändert, gilt dieser Abschnitt.

1. **`struktur-1` ist `struktur-entwurf-1`, unverändert** (Konflikt 8, Entscheidung des Supervisors
   vom 2026-11-23). Die 12 Fehler beim Beschlussvorschlag sind an den 200 Labels gefunden; eine
   Nachschärfung daran wäre eine Entwurfsschätzung, und 16 hat Stelle und Stichprobe auf dem Entwurf
   gerechnet. Der Nachtrag in § 5 („Stufe 2 schärft das Ende des Beschlussvorschlags") entfällt
   damit. Eine geschärfte Fassung kommt nur als `struktur-2` mit frischer Bestätigungsstichprobe, wie
   12 Runde 2. Die Normalisierung der Gremiennamen ist davon unberührt: das Feld `sitzung` ist nicht im
   Kriterium.
2. **Spannen nach F3, wie sie auf `main` liegen** (Konflikt 2): `start`, `end` als **Int64**, nicht
   UInt32, Folge `id, start, end, kind` über `sort_spans`, geprüft mit `check_spans`. Die Quelle
   eines Beschlussvorschlags bleibt in `dokumente_kopf` (Frage 9.3); die Zusatzspalten hinter den
   acht (Punkt 74) braucht 11 nicht.
3. **Zeilen, Abschnitte, Lesen** (§ 1, § 2.1): `split_lines` wandert aus dem Messskript nach
   `prep/raw_texts.py` neben `flatten` (textneutral; 16 und 20 importieren von dort). Mit 11 kommen
   nach `georep.spans` **`section_of(spans, sections)`** (Intervall-Join: der Abschnitt der Ebene 1 je
   Spanne; 12, 16 und 17 rufen sie statt eigener Joins) und **`read_span(text, start, end, noise)`**,
   das einen Ausschnitt ohne Seitenkopfzeilen liest (`page_noise` im Profil, Frage 9.6); die Spannen
   behalten die rohen Offsets. Je in `VERIFY_TARGETS`, wenn rein.
4. **Abschnittsart `rumpf`** (§ 4 „11"): Text nach dem Kopf ohne Überschrift — 55 % der
   BV-Informationsvorlagen setzen ihren Text ohne „Sachdarstellung:" unter die Beratungsfolge, Anfragen
   haben zwischen Betreff und Fragen eine Einleitung ohne Überschrift. 16 hat die Lücke im Messskript
   selbst geschlossen ([16-ortsbezug.md](16-ortsbezug.md), § 3.0); mit `rumpf` kommt sie aus 11. Sie
   berührt keine validierte Frage.
5. **Eine Zeile je Korpus-ID, auch bei geteilter Datei** (§ 1, „Dokument je PDF-Datei"; Konflikt 4):
   mehrere Korpus-IDs teilen eine PDF-Datei (19 108 Paper, 19 093 Dateien in der Hauptperiode); **jede**
   ID bekommt die Spannen und die Zeile in `dokumente_kopf`, sonst fehlen IDs in jedem Join auf `id`.
6. **Gremiennamen normalisieren** (§ 1): über die vorhandenen `prep/bodies` (`BodyRules`,
   `organization_key`, `resolve_organizations`, Punkt 58) und `[bodies]`, keine zweite Normalisierung.
   Frage 9.2 ist Frage 15 an Konrad; ihre Annahme („ja, als eigener Commit, mit Quelle") gilt.
7. **Ämter und Dezernate** (§ 1): das **Ämterverzeichnis** (Nummer → Name) entsteht je Lauf aus
   `dokumente_kopf`, keine Liste im Profil. Die Dezernatsverteilung (Amt → Dezernat, Beigeordnete mit
   Partei) sammelt 24, nicht 11.
8. **Doppelt geplant: Amt im Kopf und Termine der Beratungsfolge** (Konflikt 5): 11 und 12 bauen beide,
   wie validiert; **Quelle für das federführende Amt und die Beratungsfolge ist 11**, 12 für Nennungen
   im Text. Ein slow-Test vergleicht das Kopf-Amt beider, sobald 12 gemerged ist; eine Abweichung ist
   ein Befund, kein Umbau.
9. **Einhängepunkt** (Konflikt 6, Punkt 74): ein Beitrag `11-struktur` mit dem Schritt `sections` als
   **früher Schritt** (`early_steps`, vor `weights`), weil 16 seine Abschnitte vor `weights` braucht.
   Die Fabrik bekommt `(settings, layout, http)`; der Schritt ist offline.
10. **Profile ohne Rohtext** (Konflikt 14): auf Pages liegt ein Rohtextpaket nur für die Hauptperiode.
    Ohne Rohtext läuft der Schritt trotzdem und schreibt leere Spannen und je Korpus-ID eine leere Zeile;
    der Lauf scheitert nicht.
11. **Reihenfolge** (§ 3): Welle 1, Merge an Position 1 (Zulieferer für 12, 16, 20, 21, 24). Stufe 3
    zeigt nur eine Downloadzeile und darf eine Version mit 12 teilen.
