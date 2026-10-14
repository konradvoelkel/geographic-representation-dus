# Schnappschuss Wahlperiode 2014 bis 2020 (voller Lauf vom 2026-10-13)

Die Eingaben eines echten Laufs der Wahlperiode 25.05.2014 bis 12.09.2020, eingefroren, damit
GitHub Pages ihre Unterseite und den Abschnitt „Zwei Wahlperioden" der Hauptseite **ohne Netz**
baut. `profiles/duesseldorf-2014.toml` zeigt mit `reference_root` hierher; `bootstrap` erkennt
dieses Format und kopiert nur (`src/georep/bootstrap.py`, `seed_stores_from_native`).
Vorgehen: README, „Zweite Periode abrufen"; Entscheidung: `docs/decisions.md`, Punkt 56
(Frage 2.1).

Der Ordner wird **nur gelesen**: `Layout.guard_writable` verweigert jeden Schreibvorgang darunter,
die pre-commit-Hooks lassen ihn aus. Ein Lauf schreibt nach `data_root/2014-2020/` und
`cache_root/2014-2020/`.

**Die PDFs liegen nicht im Paket**, nur ihre Texte — wie bei der Referenz der Arbeit. Die 22 116
PDFs sind 3,9 GB; sie bleiben im Cache des Rechners, der sie geholt hat.

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `external/Stimmbezirk_Wahlergebnis.csv` | 57 455 | `7ba0f0997c33d638c736770096eff9489656cf1cca843ed290abc390f85da33a` |
| `external/Stimmbezirke_2020.geojson` | 2 663 053 | `bad8a312786f68ac3e187fabc4300dc3b108facded76df1ec07723dd7af82e54` |
| `external/Kommunalwahlbezirke.geojson` | 576 574 | `4fff1d369bb280a8aa7469f84e2a2103e6f805e34ce70f765b6c875e04716225` |
| `external/Wahlbezirk_Wahlergebnis.csv` | 6 454 | `6edb43dd4278914c22ac0d88150a46092beea1dff46f01382c317d8219d92435` |
| `raw/papers.jsonl` | 14 834 478 | `3d3be11e729f67997761ff907f457ca6600e1f6f6c883ebe8ef6a8ad93a30f33` |
| `cache/text/texts.parquet` | 19 737 837 | `f6cae48388f1232e007fae55137f8aca11bfedf14424a61e227ec5134aac63af` |

Zusammen 37 875 851 Bytes (36,12 MiB). `tests/unit/test_data_packages.py` hält diese Tabelle gegen
die Dateien im Repo.

**Straßen und Orte fehlen hier mit Absicht**: `period.dictionary = "base"` liest das Wörterbuch
der Hauptperiode (Stand November 2025), damit sich die beiden Perioden nur in den Dokumenten
unterscheiden (Frage 2.2). `bootstrap` nennt sie darum nicht als fehlend, sondern als nicht
zuständig (`needs_dictionary = False`). Deshalb will dieses Profil die Hauptperiode zuerst
gebootstrappt haben.

## Zahlen des Laufs (2026-10-13)

| Größe | Wert |
|---|---|
| Ratsdokumente der Periode 26.05.2014 bis 11.09.2020 (Datum des ersten und letzten) | 22 215 |
| davon mit Hauptdatei (`mainFile`) | 22 142 |
| abgerufene PDFs | 22 116, **26 fehlgeschlagen** |
| Texte im Store | 22 116, davon 21 838 mit Inhalt |
| Zeichen im Store | 67 852 547 |
| Treffer über alle 41 Wahlbezirke | 36 324 (Hauptperiode: 29 010) |
| Monate in der Monatsreihe | 77 |
| Dokumentarten | 39, häufigste `Vorlage aus der Politik` (9 601) und `Verwaltungsvorlage` (8 337) |

**Die Drucksachennummern dieser Periode tragen bis 2019 kein Gremiumskürzel.** 18 018 der 22 215
Nummern haben die Form `<Amtsnummer>/ <Nummer>/<Jahr>` (`61/ 12/2014`), die 4 197 übrigen die
heutige Form (`BV7/108/2019`, `RAT/270/2020`); der Wechsel liegt im Jahr 2019. Vor dem 2026-10-14
standen damit 18 070 Dokumente auf „Gremium unbekannt" (81,3 %), gegen 0 von 19 108 in der
Hauptperiode. Seitdem übersetzt `[bodies.aliases]` im Stadtprofil die zehn Köpfe `170` bis `179` in
die Bezirksvertretungen 10 und 1 bis 9 (`docs/decisions.md`, Punkt 57; nachgewiesen an den
Dokumenttexten dieses Pakets: 9 999 von 10 008, 99,91 %). Danach sind es **7 365** (33,2 %):
Bezirksvertretung 2 539 → 13 244, unbekannt 18 070 → 7 365, die übrigen Klassen unverändert. Die
22 echten Amtsnummern (7 313 Dokumente) bleiben unbekannt — ein Amt ist kein Gremium.

**56 % der Urheber sind unbekannt** (Option 04): die Dokumentart heißt hier in 9 601 Fällen
`Vorlage aus der Politik` und nennt keine Fraktion, während die Hauptperiode `Antrag CDU`,
`Anfrage SPD/Volt` und so weiter führt. Die Muster in `[originators]` beschreiben die heutige
Benennung; für diese Periode wären eigene nötig (`docs/plans/04-parteien.md`). Die Seite dieser
Periode zeigt den Anteil offen an, statt ihn zu verschweigen.

## Herkunft und Lizenz

| Datei | Quelle, abgerufen am 2026-10-13 | Lizenz |
|---|---|---|
| `external/Stimmbezirk_Wahlergebnis.csv` (Ratswahl 13.09.2020, 454 Zeilen) | Open-Data-Portal der Landeshauptstadt Düsseldorf | Datenlizenz Deutschland Namensnennung 2.0 |
| `external/Wahlbezirk_Wahlergebnis.csv` (41 Zeilen, Briefwähler je Wahlbezirk) | ebenda | Datenlizenz Deutschland Namensnennung 2.0 |
| `external/Stimmbezirke_2020.geojson` (316 Flächen, EPSG:4647) | ebenda | Datenlizenz Deutschland – Zero – Version 2.0 |
| `external/Kommunalwahlbezirke.geojson` (41 Flächen, Stand 29.01.2020) | ebenda | Datenlizenz Deutschland – Zero – Version 2.0 |
| `raw/papers.jsonl` | Ratsinformationssystem Düsseldorf über OParl 1.1, `ris-oparl.itk-rheinland.de`, Body 0015, ab Seite 90 | kein Lizenzhinweis am Endpunkt |
| `cache/text/texts.parquet` | aus den 22 116 PDFs desselben Endpunkts mit pypdf 6.20.0 extrahiert | wie die Dokumente |

Namensnennung nach Lizenz: Landeshauptstadt Düsseldorf, Amt für Statistik und Wahlen
(Open-Data-Portal), dl-de/by-2-0 bzw. dl-de/zero-2-0.

## Was im Paket **nicht** liegt

- die PDFs (3,9 GB) und ihr `manifest.jsonl`,
- die Stamps (`*.stamp.json`) und `raw/papers.progress.json` (der Netz-Cursor eines Abrufs),
- der HTTP-Cache (`http.sqlite`),
- alles Abgeleitete (`interim/`, `processed/`, `site/`): das rechnet `georep run` neu.

Die synthetische Mini-Periode für die schnellen Tests liegt weiter unter
`tests/fixtures/mini-2014/`; dieses Paket ist die Eingabe der `slow`-Tests und von GitHub Pages.
Die 100 synthetischen Texte jener Fixture, die auf dem Rechner des Laufs im selben Store lagen,
sind beim Packen entfernt worden (22 216 → 22 116 Zeilen) — ein Schnappschuss trägt nur, was
abgerufen wurde.
