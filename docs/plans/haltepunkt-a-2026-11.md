# Haltepunkt A der Vorverarbeitung 2026-11

**Momentaufnahme vom 2026-11-23; nur noch historisch, gültig sind der Stand je Vorhaben in
[README.md](README.md) und die Fragen in [fragen-2026-11.md](fragen-2026-11.md).** Seither kam F7 dazu,
und 18, 19, 20, 26, 27, 28 sind gemessen.

Stand 2026-11-23, spät abends, `main` auf `v0.22.0`. Meta-Plan:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 9. Gemeinsame Bausteine,
Konflikte und Reihenfolge: [00-synergien-2026-11.md](00-synergien-2026-11.md). Stand je Vorhaben:
[README.md](README.md). Fragen mit Begründung und Annahme: [fragen-2026-11.md](fragen-2026-11.md).

Haltepunkt A ist erreicht: alle sechs Fundamente sind auf `main`, die Stufe 1 von 11 bis 17, 22, 23 und
24 ist gemessen und von zwei KI-Kodierern mit Schlichter geprüft. Keine Zahl der Seite hat sich bewegt.

## 1. Fundamente

| | was | Version, Punkt |
|---|---|---|
| F2, F3 | Register für Beiträge der Vorhaben (Schritte, Tabellen, Unterseiten), Schema für Spannen | `v0.17.0`, 69 |
| F6 | OParl-Sitzungen, Beratungen, Personen, hinter `council.enabled` | `v0.18.0`, 70 |
| F4 | `georep validate` (Stichprobe, Kodierauftrag, Schlichtung, Güte) | `v0.19.0`, `v0.20.0`, 71 |
| F5 | lokale Modelle über ollama, hinter `--models`, Cache in SQLite | `v0.21.0`, 72 |
| F1 | Rohtext je PDF neben dem Textstore, Paket der Hauptperiode | `v0.22.0`, 73 |

Jedes Fundament ging durch ein unabhängiges Review und zwei bis vier Runden Nacharbeit.

## 2. Urteile der Stufe 1

Gemessen nach vorab festgelegten Kriterien. Wo eine Regel an den Labels umgebaut wurde, entschied eine
frische Stichprobe (12, 14, 16), nie dieselben Labels.

| Vorhaben | Urteil | in einer Zeile |
|---|---|---|
| 11 Struktur | **bauen** | Beschlussvorschlag 188/200 streng, Kopffelder 0,95 bis 1,0 |
| 12 Kennungen | **bauen** in Teilen | Bauleitplanung, Betrag, Termin, Verwaltungseinheit; Haushalt, Rechtsgrundlage, Rolle eines Betrags und Fristen fallen |
| 13 Dubletten | **verworfen** | es gibt kaum Dubletten: 0,5 % der Dokumente, höchstens 1,4 % Verlust je Wahlbezirk |
| 14 Vorgänge | **bauen**, Rückfallregel | nur starke Kanten (Titel, Anlage, Nachtrag, Sammelbericht): 104/106 richtig, 2 169 Vorgänge |
| 15 Funktion | **bauen**, Variante B | κ 0,905; Urheber 119/119 richtig, Recall 0,86 |
| 16 Ortsbezug | **bauen** | Stelle je Treffer, Hausnummern (92 % verortbar), Variante `ortsbezug` an frischer Stichprobe bestätigt (F1 0,83) |
| 17 Zeit | **bauen** | Lexikon bundespolitischer Begriffe 94/100 richtig; die Hälfte des Bundesvokabulars ist örtliche Umsetzung |
| 22 Bedarf | **bauen** | vier offene Quellen; Unfälle ziehen Verkehrsdokumente nach sich, aber nur zwischen Stadtbezirken |
| 23 Textübernahme | **verworfen** | Musteranträge 0,889 knapp unter 0,9, Übernahmen über Fraktionsgrenzen 0,30; Neumessung nach 14 als Rückstand |
| 24 Kontrolle | **umbauen**, später | Zuordnung Anfrage → Dezernat nur 0,72; wartet auf die Antwortanlagen (Netzlauf), 19 oder 26 |
| 25 Programme | Quellen gesammelt | 24 Programme, 3 Vereinbarungen, lokal (Urheberrecht) |
| 18, 19, 20 | Messung läuft | seit dem Abend des 2026-11-23 auf der GPU, nacheinander |

**Zur Prüfung**: Kodierer, Schlichter und Messagenten sind dasselbe Modell (Opus). Die Kodierer stimmten
fast immer überein (α 0,92 bis 1,0); das belegt die Beständigkeit des Modells, weniger die
Zuverlässigkeit der Kodierung. Wo beide denselben Grenzfall gleich lasen (23), ist das ausgewiesen. Die
Seite wird sagen: „geprüft von zwei KI-Kodierern desselben Modells, nicht von Menschen" — bis Frage 19
anders entschieden ist.

## 3. Was als Nächstes kommt

1. **Fundament-Nachzug** (Supervisor, ein Refactoring mit A/B-Bau): ein zweiter Einhängepunkt für
   Beiträge vor `weights` (16 braucht ihn), `http` an den Beiträgen (22), Spannen auf dem Rohtext über
   die Offsets aus F1, Zusatzspalten in F3 hinter den acht.
2. **Stufe 2, erste Welle**, bis zu fünf Bau-Agenten: 14, 11, 12, 15, 22; dann 17 und 16. Merge in der
   Reihenfolge 11, 12, 14, 15, 17, 22, 16, je mit eigener Version. Keines davon braucht GPU oder Netzlauf.
3. **Nebenher**: 18, 19, 20 messen auf der GPU; danach ihre Kodierung.
4. **Nach deinem Netzlauf**: Stufe 1 von 26, 27, 28; dann 24 erneut und 25.

## 4. Was du tun kannst

**Nachtrag 2026-11-23, 23:30**: Konrad hat den Supervisor gebeten, den Netzlauf zu starten (läuft), und
entschieden, dass bei offenen Fragen die Annahme gilt. Ursprünglich stand hier: **Eine Handlung**: den Netzlauf für Sitzungen, Beratungen und Personen starten
([../runbook-sitzungen.md](../runbook-sitzungen.md), § 5). Er ist Voraussetzung für 26, 27, 28 und für die
zweite Runde von 24.

**Fragen, die die Stufe 2 berühren** (ohne Antwort gilt die Annahme in `fragen-2026-11.md`):

| Nr. | kurz | Annahme ohne Antwort |
|---|---|---|
| 19 | Kodierer B künftig ein anderes Modell (etwa Sonnet)? | beide Opus |
| 18, 26 | Paketgrenze 180 MiB: heben, auslagern, nur die Hauptperiode? Drei kleine Pakete der Stufe 2 (rund 1,7 MB) freigeben? | nur die Hauptperiode; die drei kleinen ja |
| 14 | Etwas je Fraktion zeigen (Antwortzeiten, Antwortquote)? | nur standardisiert und „explorativ" |
| 25 | Die Urheberzählung der Hauptseite um Mitantragsteller nachziehen (eine Zahl auf `index.html` ändert sich)? | nein, `akteure.html` nennt den Unterschied |
| 15 | Die Namen von sechs Ausschüssen ins Profil? | ja |
| 23, 24 | Stadtteilnamen als Begriffe zählen; Hausnummer vor Straßenname als Standard? | beides nein, nur Varianten |
| 27, 28 | Straßennamen als Kategorie in den Feeds; kanonische Adresse der Seite? | nein; kein `self` |
| 29 | Ein räumliches Modell für die Bedarfshypothesen? | Moran's I genügt |

**Fragen, die warten können**: 13 (Kurzfassungen: kleineres Modell oder Auswahl — 20 misst beide),
21 und 22 (Local Manifesto Project, fehlende Programme anfragen), 30 (Bebauungspläne bei der Stadt
anfragen), 31 (OCR für 104 Dokumente ohne Textebene), 33 und 34 (Parteien und Namen der Beigeordneten
für 24).

**Vom Supervisor entschieden, umstoßbar**: 16, 17, 20, 32 (siehe `fragen-2026-11.md`), dazu die
Entscheidungen in [00-synergien-2026-11.md](00-synergien-2026-11.md), § 3.1, Punkt 4.
