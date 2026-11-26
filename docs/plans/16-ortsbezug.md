# Vorhaben 16: Ortsbezug verfeinern

**Stand 2026-11-26: Urteil bauen (§ 5.5), gemessen, nicht gebaut. § 10 vor dem Bau durch den
Supervisor**: § 6 ist durch die Synergie überholt (`flatten_with_offsets` aus F1 statt `store_view`,
Spannen nach F3 mit Int64, Rumpf aus 11, Adressen über `point_shares` aus 22;
[00-synergien-2026-11.md](00-synergien-2026-11.md), § 4 „16 Ortsbezug"). Alle Voraussetzungen liegen auf
`main`.

Stufe 1 (Messen) mit einer Runde Umbau, abgeschlossen am 2026-11-23 auf dem Branch `feat/16-ortsbezug`
(gemerged, entfernt). Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „16 Ortsbezug
verfeinern". Messskript: [16-ortsbezug-messung.py](16-ortsbezug-messung.py). Codebuch, Stichprobe und
Labels: [../../validierung/16-ortsbezug/](../../validierung/16-ortsbezug/).

**Urteil (Abschluss der Stufe 1 nach einer Runde Umbau, 2026-11-23): bauen.** Die vorab festgelegte
Regel „handelt von" (Titel, Betreff oder Kern) verfehlte in Runde 1 das Kriterium (F1 0,772 an 200
Paaren). Nach der vorab festgelegten Entscheidungsregel ging es mit **Nebenregel C** weiter (dazu
Listenzeilen und Adressen im Begleittext); sie **besteht an 100 frischen Paaren** nach Codebuch
Fassung 2: **F1 0,828 (0,769–0,882), κ 0,249 (0,023–0,466)**, α zwischen den Kodierern 0,974 (§ 4.4,
§ 5.5). C wird die Gewichtsvariante `ortsbezug`, nicht die Standardzählung: die triviale Regel „alles
handelt von" liegt in beiden Runden darüber (F1 0,902 und 0,878), **78 bis 82 % der Paare handeln
von einem Ort im Bezirk**. **Gebaut werden außerdem die Stelle je Treffer und die Hausnummern**
(92,3 % verortbar, Schwelle 80 %). Keine Variante ändert die stärkste Verzerrung: die Trefferzahl
hängt an der Größe des Wörterbuchs mit r = 0,765, nur mit „handelt von" mit r = 0,770.

Die drei Zahlen, auf die es ankommt:

1. **Die Stelle allein reicht nicht, mit Listen und Adressen knapp**: 41,3 % der Paare (Dokument,
   Wahlbezirk) haben ihren besten Treffer in Titel oder Betreff, 17,3 % im Kern, 41,1 % nur im
   Begleittext; kodiert handeln aber **zwei Drittel der Paare im Begleittext** von dem Ort (67,1 %
   in Runde 1, 64,7 % in Runde 2) — Listen, Berichte, Sachstände. Die ursprüngliche Regel kommt auf
   F1 0,772, **Nebenregel C an frischen Paaren auf 0,828** (κ 0,249); die triviale Regel auf 0,902
   und 0,878.
2. **Die Regel lässt die Verzerrung durch die Wörterbuchgröße stehen** (r 0,765 → 0,770) und
   bewegt Tabelle 5 wenig: p über alle 41 Bezirke 0,234 → 0,167, ohne 1 und 10 0,036 → 0,025;
   Rangkorrelation der Quote zur heutigen 0,932.
3. **Hausnummern**: 18,0 % der Erwähnungen von Straßen tragen eine Hausnummer, 27,0 % der Paare
   enthalten eine solche Adresse; **92,3 % (91,7–92,7) der Adressen sind in den Hauskoordinaten NRW
   verortbar**, 10 143 von 10 146 verorteten liegen im Wahlbezirk des Begriffs, und jede Adresse an
   einer Straße über mehrere Bezirke (4 998) legt den Bezirk fest.

Alle Zahlen sind am 2026-11-23 gemessen, an der Rohtext-Messdatei der Hauptperiode (pypdf 7.1.0,
Groß- und Kleinschreibung, Zeilen, Seitenwechsel als `\f`) und am Korpus nach `georep bootstrap &&
georep run` im Worktree. Nachrechnen, mit den Lastregeln des Supervisors vom selben Tag:

```bash
export POLARS_MAX_THREADS=4 OMP_NUM_THREADS=2
nice -n 10 uv run python docs/plans/16-ortsbezug-messung.py              # alle Zahlen, rund eine Minute
nice -n 10 uv run python docs/plans/16-ortsbezug-messung.py --aufgaben   # dazu Stichprobe und Kodieraufgaben
```

Laufzeit des Skripts: 43 s Wanduhr, 0,77 GB Spitzenspeicher, ein Prozess, bei `uptime` 4,2 / 11,7 /
17,7 (unter Fremdlast von 27 bis 72 waren es 59 bis 70 s). Davon 26 bis 51 s für den Nachbau des
Textstores, das Regelwerk von 11 und die Suche mit Stelle über 19 075 Dokumente. Stichprobe,
Kodieraufgaben und Regelausgabe sind bytegleich über Läufe (SHA-256 von `aufgaben.jsonl` in sechs
Läufen gleich, `20b9f85b…`; `stichprobe.csv` `92285610…`).

## 1. Frage und Nutzen

**Frage.** Handelt ein Dokument von einem Ort im Wahlbezirk, oder erwähnt es ihn nur? Lassen sich
Hausnummern und Flächen (Geltungsbereiche von Bebauungsplänen, Schulen, Kitas, Haltestellen)
verorten?

**Warum.** Die Trefferquote der Arbeit ist binär: ein Dokument zählt für einen Bezirk, sobald ein
Begriff seines Wörterbuchs irgendwo im Text steht — im Betreff eines Antrags zum Zebrastreifen auf
der Kürtenstraße ebenso wie in der Anschrift „Katasteramt, Brinckmannstraße 5" einer Auslegung. Die
Seite misst seit dem Methodik-Review, dass die Trefferzahl zu gut der Hälfte an der Größe des
Wörterbuchs hängt (`STATUS.md`, „Methodikregeln"; [../statistik.md](../statistik.md), § 3). Wenn
beiläufige Erwähnungen in großen Wörterbüchern häufiger wären, müsste eine Zählung nur dessen, wovon
ein Dokument handelt, diese Verzerrung kleiner machen. Das prüft § 3.3.

**Literatur.** Harmening u. a. (2025) und Nyhuis u. a. (2025) zählen Ortsbezüge in Anfragen über
dasselbe Werkzeug wie diese Seite: ein Wörterbuch aus Verwaltungsgrenzen, geolokalisierten
Wikipedia-Einträgen und Straßennamen (Einträge in `report/literatur.toml`). Die Unterscheidung
„handelt von / erwähnt" ist hier eine eigene Verfeinerung, nicht aus diesen Arbeiten übernommen; die
Seite belegt sie darum nicht mit ihnen. Ob sie Stadtteilnamen ins Wörterbuch nehmen (§ 3.5), ist vor
einem Zitat nachzulesen. Maßstab der Prüfung bleibt Grimmer und Stewart (2013): eine Regel ohne
kodierte Stichprobe ist eine Behauptung.

**Ratsarbeit.** Wer für einen Wahlbezirk sucht, will zuerst die Dokumente, die von einem Ort dort
handeln, nicht jede Vorlage, die eine Dienststelle an der Straße als Anschrift nennt; die Stelle des
Treffers ordnet die Trefferliste. Die Hausnummer legt fest, auf welcher Seite einer Grenzstraße eine
Maßnahme liegt — für Bezirksvertretungen eine Frage der Zuständigkeit. Vorhaben 21 (Geld auf der Karte) braucht beides: einen Betrag ordnet es dem Ort zu,
von dem das Dokument handelt, und die Adresse dem Bezirk.

## 2. Datenlage

| Datei | Inhalt | Herkunft, Lizenz |
|---|---|---|
| `data/duesseldorf/interim/papers.parquet` | Korpus der Hauptperiode, 19 108 Dokumente: `id`, `reference`, `name` (OParl-Titel), `paper_type`, `date`, `file_name`, `text` (Textstore: kleingeschrieben, ohne Zeilenumbrüche, ab dem ersten „betrifft") | Paket `reference/` und `snapshots/duesseldorf-texte/` (Punkt 68) |
| `messdaten/rohtext/duesseldorf.parquet` | Rohtext pypdf 7.1.0 je PDF (`name`, `text` mit `\f` zwischen Seiten); 19 076 Dokumente des Korpus haben eine Zeile, 32 nicht | Messdatei aus Phase 0 |
| `data/duesseldorf/processed/inverted_index.parquet` | `suchbegriffe`, `paper_ids`, `anzahl_treffer`: 5 727 Begriffe, 30 859 Paare (Dokument, Begriff) | `georep run` |
| `processed/combined_searchdict.parquet` | Wörterbuch je Wahlbezirk (`wahlkreis_id`, `suchbegriffe`) | `georep run` |
| `processed/wahlbezirke_strassen.parquet`, `processed/wikidata_agg.parquet` | Straßen und Orte je Bezirk, daraus die Begriffsart: 4 373 Straßen, 1 258 Orte, 96 beides | `georep run` |
| `processed/wahlbezirke_auswertung.parquet` | Treffer, Wahlberechtigte, Wahlbeteiligung je Bezirk (Tabelle 5) | `georep run` |
| `interim/stimmbezirke.geojson` | 306 Stimmbezirke mit `wahlbezirk` (EPSG:4647) | Open-Data-Portal, Punkt 52 |
| `docs/plans/11-struktur-messung.py` | Regelwerk `struktur-entwurf-1` (Abschnitte, Kopf), unverändert importiert | Vorhaben 11, bestätigt (Beschlussvorschlag streng 0,94) |

**Fremddaten** (Konrad, 2026-11-23: ausdrücklich gewünscht). Je Quelle ein Ordner unter
`/media/konrad/xtraspace/georep/fremddaten/opendata/` mit README (URL, Abrufdatum, Größe, SHA-256,
Lizenz wörtlich); das Messskript prüft die Prüfsumme vor dem Lesen und liest nur mit seinem eigenen
Code (`csv`, `json`, `zipfile`), nichts wird ausgeführt. Messung 22 hatte drei der gebrauchten
Dateien schon geladen; sie sind nicht doppelt geladen.

| Ordner | Datei | Bytes | Lizenz (wörtlich, Quelle) | geladen von |
|---|---|---|---|---|
| `nrw-gebaeudereferenzen/` | `gebref_EPSG25832_ASCII.zip` (Hauskoordinaten NRW, 84 193 im Stadtgebiet) | 90 258 596 | „Datenlizenz Deutschland – Zero – Version 2.0" (open.nrw) | 22 |
| `nrw-schuldaten/` | `schuldaten.csv` (185 Schulen im Stadtgebiet) | 1 790 359 | „Datenlizenz Deutschland Namensnennung 2.0" (open.nrw) | 22 |
| `duesseldorf-kitas/` | `Tageseinrichtungen_fuer_Kinder.csv` (369) | 57 590 | „Datenlizenz Deutschland – Zero – Version 2.0" (Portal) | 22 |
| `duesseldorf-stadtteile/` | `Stadtteile_2025_WGS84_EPSG4326_1.geojson` (50 Flächen) | 1 335 152 | `license_title` „https://www.govdata.de/dl-de/zero-2-0" (Portal-API) | 16 |
| `duesseldorf-wohnquartiere/` | `Wohnquartiere_WGS84_4326.geojson` (365 Flächen, ohne Namen; nicht verwendet) | 2 337 931 | wie oben | 16 |
| `duesseldorf-sportstaetten/` | `Sportstaetten_Duesseldorf.geojson` (116) | 54 703 | wie oben | 16 |
| `duesseldorf-kleingaerten/` | `Kleingaerten_Duesseldorf.csv` (96, ohne Koordinate) | 7 802 | wie oben | 16 |
| `duesseldorf-bahnhoefe/` | S-Bahnhöfe (25) und Fernbahnhöfe (3), GeoJSON | 6 747 + 871 | wie oben | 16 |
| `duesseldorf-kirchen/` | `Kirchen_in_Duesseldorf.geojson` (137) | 62 693 | `license_title` „https://www.govdata.de/dl-de/by-2-0" | 16 |
| `duesseldorf-museen/` | `Duesseldorfer_Museen_erweiterte_Info_WGS84_4326.geojson` (39) | 38 118 | dl-de/zero-2-0 | 16 |
| `duesseldorf-wohnbauflaechen/` | `potenzial_wohnen_2026.geojson` (64 Flächen mit Namen und B-Plan-Nummer) | 111 988 | dl-de/zero-2-0 | 16 |
| `nrw-bauleitplanung/` | `bplan_duesseldorf_gkz05111000.geojson` (104 Pläne der Stadt aus der OGC API „Räumliche Pläne nach BauGB", `gkz=05111000`); `bplanlinks_CSV.zip` (Kommunenliste) | 613 949 + 19 697 | „Datenlizenz Deutschland - Namensnennung - Version 2.0" (`rel=license` der API); die Liste ohne eigene Angabe | 16 |

Was es **nicht** gibt: Das Portal der Stadt (383 Datensätze, `package_list` am 2026-11-23) hat
**keine Geltungsbereiche von Bebauungsplänen und keine Haltestellen**; der WFS
`maps.duesseldorf.de/services/poi/wfs`, auf den der Datensatz „Standorte von Grundschulen" verweist,
antwortet mit 404. Die Bebauungspläne kommen darum aus dem Landesdatensatz, der nach eigener Angabe
„im Aufbau und … unvollständig" ist (§ 3.5). Haltestellen des Nahverkehrs sind eine Lücke; das Portal
hat nur Bahnhöfe, Park-and-ride, Taxistände.

Ins Repo kommen aus diesem Vorhaben nur Paar-IDs, Codebuch und Messskript; Texte, Anschriften und
die Kodieraufgaben bleiben lokal.

## 3. Messung

### 3.0 Wie die Stelle entsteht (und warum sie exakt ist)

Der Index sucht im Textstore, der aus dem Rohtext durch Entfernen aller Zeilenumbrüche,
Kleinschreiben und Abschneiden vor dem ersten „betrifft" entsteht (`prep/extract.py`). Das Skript
baut denselben Text aus der Messdatei, merkt sich je Zeichen die Stelle im Rohtext und sucht mit
demselben Matcher (flashtext, Wortgrenzen wie im Index). Ergebnis:

- **19 075 von 19 076 Dokumenten** mit Rohtext ergeben genau den Textstore; eines (ADIG/039/2024)
  weicht um 41 Zeichen ab und hat keinen Treffer.
- **30 695 der 30 859 Paare (Dokument, Begriff) des Index** sind mit Stelle wiedergefunden, **keines
  zusätzlich**. Die 164 übrigen stammen alle aus einem Dokument, BR/007/2021: es hat 187 472 Zeichen
  im Textstore, aber keine Zeile in der Messdatei (mutmaßlich der Text, der nach Punkt 68 der der
  Arbeit blieb). Die anderen 31 Dokumente ohne Rohtext haben auch keinen Textstore. Auf Ebene
  (Dokument, Wahlbezirk) sind es 29 289 von 29 330 Paaren (= Summe der Treffer aller Bezirke); die 41
  des einen Dokuments bleiben ohne Stelle und zählen in jeder Variante wie heute.
- Die Abschnitte sind die von Vorhaben 11 (Ebene 1). Zwei Lücken des Regelwerks schließt das Skript,
  weil 11 Abschnitte nur an Überschriften öffnet: in 55 % der BV-Informationsvorlagen folgt der Text
  der Beratungsfolge ohne „Sachdarstellung:" (für 11 noch Kopf), und in Anfragen steht zwischen Betreff
  und Fragen eine Einleitung ohne Überschrift. Beides heißt hier **Rumpf** und zählt zum Begleittext;
  was hinter Grußformel oder „gez." steht, zählt zum Rest.

**Grobe Stelle** (fünf Klassen): **Titel** (der Begriff steht auch im OParl-Titel; der Titel selbst
ist nicht im Index, gezählt wird er nur bei einem Treffer im Text), **Betreff**, **Kern**
(Beschlussvorschlag, Fragen einer Anfrage — worüber abgestimmt oder wonach gefragt wird),
**Begleittext** (Sachdarstellung, Begründung, Stellungnahme, zitierter Beschluss, Alternative,
Rumpf), **Rest** (Anlagenliste, „Nachrichtlich", Kopf, hinter dem Schluss). Die beste Stelle eines
Paares ist die vorderste in dieser Reihenfolge.

### 3.1 Wo steht ein Treffer?

**Erwähnungen** (jedes Vorkommen eines Begriffs, 66 004):

| feine Stelle | Erwähnungen | Anteil | grob |
|---|---|---|---|
| Sachdarstellung | 25 431 | 38,5 % | Begleittext |
| Beschlussvorschlag | 9 977 | 15,1 % | Kern |
| Betreff | 8 293 | 12,6 % | Betreff |
| Rumpf ohne Überschrift | 7 512 | 11,4 % | Begleittext |
| Begründung | 7 327 | 11,1 % | Begleittext |
| zitierter Beschluss | 2 480 | 3,8 % | Begleittext |
| Stellungnahme der Verwaltung | 2 298 | 3,5 % | Begleittext |
| Fragen | 1 641 | 2,5 % | Kern |
| Anlagenliste | 910 | 1,4 % | Rest |
| hinter dem Schluss, „Nachrichtlich", Kopf | 135 | 0,2 % | Rest |

**Beste Stelle** je Paar:

| Stelle | Erwähnungen | (Dokument, Begriff) | (Dokument, Wahlbezirk) |
|---|---|---|---|
| Titel | – | 8 080 (26,3 %) | 11 903 (40,6 %) |
| Betreff (nicht im Titel) | 8 293 (12,6 %) | 176 (0,6 %) | 194 (0,7 %) |
| Kern | 11 618 (17,6 %) | 5 604 (18,3 %) | 5 060 (17,3 %) |
| Begleittext | 45 048 (68,3 %) | 16 702 (54,4 %) | 12 050 (41,1 %) |
| Rest | 1 045 (1,6 %) | 133 (0,4 %) | 82 (0,3 %) |
| zusammen | 66 004 | 30 695 | 29 289 |

- **Titel und Betreff sind fast dasselbe**: 8 080 Paare tragen den Begriff im Titel, nur 176 im
  Betreff allein. Für eine Regel sind sie eine Klasse.
- **Anlage und Rest sind fast leer** (0,3 % der Paare): die Anlagen sind in OParl eigene Dateien
  (`auxiliaryFile`) und nicht im Text des Hauptdokuments; was im Briefing „Anlage/Rest" heißt, ist
  hier die Anlagenliste.
- **Erwähnungen je Paar**: Median 2, Mittel 3,92; ein einziges Vorkommen bei 31,2 % der Paare, drei
  und mehr bei 46,7 %, zehn und mehr bei 7,8 %.

**Nach Begriffsart** (beste Stelle je Dokument und Begriff):

| Begriffsart | (Dok., Begriff) | Titel | Betreff | Kern | Begleittext | Rest | Titel/Betreff/Kern |
|---|---|---|---|---|---|---|---|
| Straße | 25 548 | 27,0 % | 0,6 % | 18,6 % | 53,4 % | 0,4 % | 46,2 % |
| Ort (Wikidata) | 2 577 | 21,7 % | 0,4 % | 15,2 % | 62,1 % | 0,5 % | 37,3 % |
| Straße und Ort | 2 570 | 24,1 % | 0,3 % | 18,1 % | 57,2 % | 0,3 % | 42,5 % |
| 57 stadtweite Begriffe | 5 447 | 27,5 % | 0,5 % | 19,2 % | 52,4 % | 0,3 % | 47,2 % |
| übrige | 25 248 | 26,1 % | 0,6 % | 18,1 % | 54,8 % | 0,5 % | 44,7 % |

Orte aus Wikidata stehen seltener vorn als Straßen (37 gegen 46 %): ein Gebäude oder Park wird öfter
im Begleittext genannt. **Die stadtweiten Begriffe** (57 über dem 99-%-Quantil der
Dokumenthäufigkeit, 64 Dokumente; mit den Texten der Arbeit waren es 55) **stehen nicht seltener
vorn als die übrigen** (47 gegen 45 %): sie sind große Straßen, über die oft entschieden wird, keine
Füllwörter. Am wenigsten vorn stehen „südring" (22 %), „prinz-georg-straße" (25 %), „schulweg"
(27 %), „vennhausen" (29 %), „hofgarten" (30 %), „schadowstraße" (31 %); am meisten
„benderstraße" (64 %), „worringer platz" (62 %), „hansaallee" (61 %). Keiner liegt unter 10 %. Die
Liste mit Dokumentzahl je Begriff druckt das Skript.

**Je Wahlbezirk** (Paare mit Stelle; Anteile an ihnen; „nur stadtweit": alle getroffenen Begriffe
des Paares sind stadtweite):

| Bezirk | Begriffe | Treffer | Titel/Betreff | Kern | Begleittext | Rest | handelt von (Regel) | nur stadtweit |
|---|---|---|---|---|---|---|---|---|
| 1 | 751 | 1 786 | 43,1 | 16,0 | 40,6 | 0,3 | 59,2 | 25,1 |
| 2 | 134 | 908 | 37,6 | 18,0 | 44,1 | 0,3 | 55,6 | 28,8 |
| 3 | 77 | 564 | 37,3 | 18,8 | 43,5 | 0,4 | 56,1 | 42,5 |
| 4 | 109 | 718 | 42,3 | 17,0 | 40,3 | 0,4 | 59,3 | 35,0 |
| 5 | 198 | 682 | 36,6 | 19,2 | 43,3 | 0,9 | 55,8 | 23,6 |
| 6 | 136 | 668 | 40,9 | 17,7 | 40,9 | 0,4 | 58,6 | 33,1 |
| 7 | 105 | 821 | 38,5 | 19,1 | 41,6 | 0,7 | 57,7 | 48,2 |
| 8 | 139 | 810 | 45,4 | 16,8 | 37,5 | 0,4 | 62,2 | 24,5 |
| 9 | 113 | 797 | 45,9 | 16,6 | 37,6 | 0,0 | 62,4 | 21,9 |
| 10 | 106 | 1 016 | 40,6 | 16,7 | 42,5 | 0,3 | 57,2 | 35,6 |
| 11 | 199 | 674 | 31,9 | 19,6 | 48,3 | 0,1 | 51,6 | 10,5 |
| 12 | 114 | 725 | 32,7 | 19,8 | 47,2 | 0,3 | 52,5 | 20,4 |
| 13 | 105 | 555 | 27,1 | 17,1 | 55,6 | 0,2 | 44,2 | 10,3 |
| 14 | 92 | 574 | 30,0 | 17,8 | 51,7 | 0,5 | 47,8 | 9,4 |
| 15 | 80 | 638 | 35,3 | 19,9 | 44,4 | 0,3 | 55,3 | 26,8 |
| 16 | 122 | 561 | 40,0 | 16,1 | 43,9 | 0,0 | 56,1 | 20,5 |
| 17 | 130 | 588 | 31,7 | 15,8 | 52,5 | 0,0 | 47,5 | 13,6 |
| 18 | 171 | 789 | 35,4 | 17,1 | 47,1 | 0,4 | 52,5 | 18,9 |
| 19 | 154 | 584 | 41,3 | 20,2 | 38,4 | 0,0 | 61,6 | 28,5 |
| 20 | 147 | 752 | 45,3 | 16,8 | 37,9 | 0,0 | 62,1 | 14,4 |
| 21 | 195 | 693 | 42,8 | 17,3 | 39,9 | 0,0 | 60,1 | 8,2 |
| 22 | 262 | 876 | 41,6 | 15,1 | 43,1 | 0,2 | 56,7 | 31,7 |
| 23 | 362 | 893 | 45,4 | 19,1 | 35,2 | 0,3 | 64,5 | 16,9 |
| 24 | 165 | 375 | 47,3 | 14,7 | 37,4 | 0,5 | 62,0 | 11,5 |
| 25 | 162 | 644 | 54,6 | 12,9 | 32,0 | 0,5 | 67,5 | 3,7 |
| 26 | 147 | 663 | 45,3 | 17,2 | 36,7 | 0,8 | 62,5 | 16,2 |
| 27 | 155 | 517 | 41,5 | 14,3 | 43,6 | 0,6 | 55,8 | 18,2 |
| 28 | 233 | 946 | 42,6 | 18,0 | 39,2 | 0,2 | 60,6 | 29,4 |
| 29 | 163 | 817 | 45,8 | 18,1 | 35,9 | 0,1 | 64,0 | 27,8 |
| 30 | 216 | 1 019 | 47,3 | 16,6 | 36,0 | 0,1 | 63,9 | 19,9 |
| 31 | 107 | 530 | 39,9 | 16,6 | 43,1 | 0,4 | 56,5 | 12,7 |
| 32 | 164 | 826 | 42,4 | 11,8 | 45,6 | 0,2 | 54,2 | 29,3 |
| 33 | 137 | 758 | 44,3 | 12,8 | 42,4 | 0,5 | 57,1 | 22,5 |
| 34 | 109 | 610 | 40,2 | 17,7 | 41,7 | 0,3 | 58,0 | 13,0 |
| 35 | 123 | 471 | 35,3 | 20,4 | 44,3 | 0,0 | 55,7 | 33,4 |
| 36 | 128 | 572 | 46,8 | 17,5 | 35,6 | 0,2 | 64,3 | 25,2 |
| 37 | 193 | 649 | 44,6 | 18,7 | 36,7 | 0,0 | 63,3 | 17,3 |
| 38 | 132 | 318 | 38,5 | 19,6 | 42,0 | 0,0 | 58,0 | 0,0 |
| 39 | 189 | 812 | 45,6 | 19,2 | 34,9 | 0,2 | 64,9 | 29,5 |
| 40 | 195 | 581 | 44,7 | 18,3 | 37,1 | 0,0 | 62,9 | 17,9 |
| 41 | 158 | 550 | 44,1 | 20,6 | 35,2 | 0,2 | 64,7 | 20,6 |

Der Anteil „handelt von" schwankt zwischen 44,2 % (Bezirk 13) und 67,5 % (Bezirk 25), Median 58,0 %.
**Mit der Größe des Wörterbuchs hängt er kaum zusammen** (Pearson r = 0,208, p = 0,19; Spearman
ρ = 0,389): Bezirk 1 mit 751 Begriffen liegt mit 59,2 % in der Mitte. Große Wörterbücher erzeugen
also nicht mehr beiläufige Erwähnungen je Treffer — der Grund, warum § 3.3 die Verzerrung nicht
kleiner findet.

### 3.2 Die Regel „handelt von"

**Vorab festgelegt** (2026-11-23, im Skript `REGEL_HANDELT_VON`, vor jeder Kodierung): ein Paar
(Dokument, Wahlbezirk) handelt von einem Ort des Bezirks, wenn mindestens ein Begriff seines
Wörterbuchs im Titel, im Betreff oder im Kern steht; sonst erwähnt es ihn. Daneben, an derselben
Kodierung gemessen und **explorativ**:

| Regel | „handelt von" | Anteil der 29 289 Paare |
|---|---|---|
| **Regel: Titel, Betreff oder Kern** | **17 157** | **58,6 %** |
| A: Regel oder ≥ 3 Erwähnungen im Begleittext | 20 544 | 70,1 % |
| B: nur Titel oder Betreff | 12 097 | 41,3 % |
| C: Regel oder ein Begriff im Begleittext in einer Listenzeile (Zeile ≤ 60 Zeichen, Begriff in den ersten 12) oder mit Hausnummer | 21 951 | 74,9 % |

**Nach Dokumentart** (Arten wie in 11):

| Art | Paare | handelt von | Titel | Kern | Begleittext |
|---|---|---|---|---|---|
| Beschlussvorlage | 7 135 | 63,7 % | 42,3 % | 21,0 % | 35,9 % |
| Antrag | 6 708 | 81,0 % | 49,0 % | 31,2 % | 18,8 % |
| BV-Informationsvorlage | 5 761 | 45,1 % | 44,5 % | 0,5 % | 54,6 % |
| Anfrage | 4 036 | 69,8 % | 49,3 % | 18,2 % | 29,8 % |
| Informationsvorlage | 2 814 | **9,0 %** | 8,7 % | 0,1 % | 90,9 % |
| BV-Beschlussvorlage | 1 216 | 78,3 % | 28,9 % | 49,2 % | 21,6 % |
| Berichtsvorlage | 728 | **5,1 %** | 5,1 % | 0,0 % | 94,9 % |
| A+F Beschluss | 401 | 53,1 % | 51,4 % | 1,2 % | 46,9 % |
| Bedarfsbeschluss | 233 | 47,2 % | 37,3 % | 9,0 % | 52,8 % |
| Eingabe | 145 | 80,7 % | 69,7 % | 10,3 % | 19,3 % |
| Haushaltsantrag | 112 | 68,8 % | 17,0 % | 51,8 % | 30,4 % |

Die Regel ist **an die Form gebunden**: Dokumente ohne Kern (Informations- und Berichtsvorlagen)
handeln für sie nur dann von einem Ort, wenn er im Titel steht. Ein Bericht der Kleinen Kommission
Radverkehr über Maßnahmen an vielen Straßen „erwähnt" für sie jede davon. Ob das falsch ist, sagt erst
die Kodierung; das Codebuch zählt solche Listenpunkte als „handelt von", und kodiert handeln zwei Drittel der Paare im Begleittext von dem Ort (§ 4.1).

**Dokumente**: 10 798 Dokumente haben Treffer mit Stelle; in 8 253 (76,4 %) handelt mindestens ein
Paar von einem Bezirk. **1 542 Dokumente treffen fünf oder mehr Bezirke** und tragen 11 857 der
29 289 Paare (40,5 %) — Sammelvorlagen, Listen, Berichte. Sie sind der Kern der Frage.

### 3.3 Wirkung als Sensitivität

Je Variante die Treffer je Wahlbezirk (Summe der Gewichte der Paare; Paare ohne Stelle zählen 1),
Tabelle 5 mit derselben Funktion wie die Seite (`analysis.regression.regression_pair`, Ausreißer aus
dem Profil), die drei Korrelationen des Methodenabsatzes und die Rangkorrelation der Quote zur
heutigen:

| Variante | Summe | r(Treffer, Begriffe) | r(Treffer, Wahlberecht.) | r(je Begriff, Begriffe) | ρ zur Quote | Tabelle 5, alle 41: Steigung / r / p | ohne 1 und 10: Steigung / r / p |
|---|---|---|---|---|---|---|---|
| alle Treffer (heute) | 29 330 | **0,765** | 0,165 | −0,512 | 1,000 | 79,43 / 0,190 / 0,234 | 214,98 / 0,336 / 0,036 |
| nur „handelt von" (Regel) | 17 198 | **0,770** | 0,268 | −0,478 | 0,932 | 149,16 / 0,220 / 0,167 | 355,35 / 0,360 / 0,025 |
| nur Titel oder Betreff (B) | 12 138 | 0,760 | 0,298 | −0,440 | 0,876 | 187,76 / 0,211 / 0,186 | 426,01 / 0,336 / 0,037 |
| nach Stelle gewichtet (1 / 1 / 1 / 0,5 / 0,25) | 23 243,5 | 0,772 | 0,206 | −0,504 | 0,983 | 105,87 / 0,203 / 0,203 | 277,43 / 0,351 / 0,028 |
| Hausnummer vor Straßenname (§ 3.4) | 27 540 | 0,801 | 0,205 | −0,512 | 0,984 | 90,51 / 0,207 / 0,194 | 242,39 / 0,358 / 0,025 |

- **Die stärkste Verzerrung bleibt**: keine Variante senkt r(Treffer, Begriffe) unter 0,76. Die Zahl
  der Begriffe treibt die Zahl der Dokumente, die von einem Ort im Bezirk handeln, genauso wie die
  Zahl der Dokumente, die einen erwähnen. Ein großes Wörterbuch heißt: viele benannte Orte, über die
  auch entschieden wird. Die Verfeinerung ist darum **keine Antwort auf Methodik-Review § 2.6**; die
  Gegenprobe „Treffer je Begriff" bleibt nötig.
- **Tabelle 5 bewegt sich in die Richtung der Arbeit**, aber innerhalb dessen, was schon die
  Gewichtungsvarianten zeigen ([../statistik.md](../statistik.md), § 6): Steigung und r steigen, das
  p über alle 41 Bezirke bleibt über 0,05 (0,167), ohne 1 und 10 sinkt es von 0,036 auf 0,025. Das
  ist ein weiterer Test derselben Frage, kein unabhängiger (§ 12 dort: Mehrfachtests).
- **Bewegung der Quote**: 12 Bezirke wandern mit der Regel um fünf und mehr Plätze, am weitesten 18
  (7 → 17), 25 (34 → 23), 14 (27 → 35), 32 (8 → 15), 13 (32 → 39). Die ausgeschlossenen Bezirke
  bleiben auf Platz 1 und 3. Bezirk 13 hat mit 44,3 % den kleinsten Anteil „handelt von" an allen
  seinen Treffern (44,2 % an denen mit Stelle, § 3.1), 25 mit 67,5 % den größten.
- **Hausnummer vor Straßenname** (eine Straße zählt nur noch für die Bezirke ihrer verorteten
  Adressen, wo das Dokument sie nur mit Hausnummer nennt) nimmt 1 790 Paare weg (6,1 %) und **erhöht**
  r(Treffer, Begriffe) auf 0,801 — vermutlich, weil die Doppelzählung über Grenzstraßen Treffer auch
  Bezirken mit kleinem Wörterbuch zuschlägt; ohne sie hängen die Treffer noch stärker an der
  Wörterbuchgröße (nicht weiter zerlegt).

### 3.4 Hausnummern

| Größe | Wert |
|---|---|
| Hauskoordinaten im Stadtgebiet (GebRef NRW, Stand 2026-10-01) | 84 193 Hausnummern an 2 652 Straßennamen; jede liegt in einem Stimmbezirk |
| Straßenbegriffe des Wörterbuchs (ohne „str."-Varianten) in GebRef | 2 608 von 2 897 (90,0 %); 565 Straßen liegen in mehr als einem Wahlbezirk |
| Erwähnungen von Straßen mit Hausnummer dahinter | **10 944 von 60 749 (18,0 %)** |
| (Dokument, Straße) mit mindestens einer Hausnummer | 6 114 von 28 118 (21,7 %) |
| Dokumente mit „Straße + Hausnummer" | 3 335; Paare (Dokument, Bezirk) mit einer solchen Adresse: 7 916 von 29 289 (27,0 %) |
| Stelle der Adressen | Betreff 15,5 %, Kern 16,6 %, Begleittext 66,3 %, Rest 1,6 % |
| Straßenname der Adresse in GebRef | 10 882 von 10 944 (99,4 %) |
| **verortbar** (Nummer mit Zusatz genau, oder Hauptnummer, wo der Text einen Zusatz nennt, den es nicht gibt) | **10 097 von 10 944 = 92,3 % (91,7–92,7)**: genau 9 879, Hauptnummer 218 |
| verortbar, großzügig (dazu Nummer, die es nur mit anderem Zusatz gibt) | 92,7 % (92,2–93,2) |
| nicht verortbar | Nummer fehlt an der Straße 736, Straße unbekannt 62 |
| verortet im Wahlbezirk des Begriffs | 10 143; in einem anderen 3; außerhalb 0 |
| Adressen an Straßen über mehrere Bezirke | 4 998, jede einem der Bezirke der Straße zugeordnet |
| (Dokument, Straße), deren Erwähnungen alle verortete Adressen sind | 4 050; damit fielen 1 790 Paare (Dokument, Bezirk) weg (6,1 %) |
| Adresse → Wahlbezirk als Paket (Straße, Nummer, Zusatz, Bezirk; zstd) | 92 827 Bytes |

**Erkennung.** Eine Hausnummer ist eine Zahl mit bis zu drei Ziffern direkt hinter einem
Straßenbegriff, mit Zusatzbuchstabe, Bereich („50–54", „12/14") oder „Nr." davor; keine Hausnummer
sind Dezimalzahlen, vierstellige Zahlen und Zahlen mit Einheit (m, %, €, Uhr, Plätze, Standorte …).
Eine Durchsicht von 40 zufälligen Treffern des Musters außerhalb der Stichprobe (Mess-Agent, keine
Kodierung) fand 37 Adressen und dreimal eine Zählung („Münsterstraße 2 Standorte"); „Standort" ist
seitdem ausgeschlossen. Die Präzision des Musters ist damit nicht validiert, nur grob geprüft; eine
falsch erkannte Zahl fällt meist beim Nachschlagen durch und senkt dann die Verortbarkeit, statt sie
zu erhöhen.

**Was Hausnummern bringen — und was nicht.** Sie erzeugen keine Treffer (jede Adresse hängt an einer
Straße, die schon im Wörterbuch steht), sie **entscheiden die Grenzstraße**: wo ein Dokument eine
Straße über mehrere Bezirke nur mit Hausnummer nennt, zählt es nur für den Bezirk der Adresse. Das
betrifft 6,1 % der Paare und die Zuständigkeitsfrage der Bezirksvertretungen. Anschriften stehen zu
zwei Dritteln im Begleittext; sie sind kein Zeichen für „handelt von" (Anschriften von Dienststellen
und Personen sind „erwähnt", Listen von Baumaßnahmen „handelt von").

**Datenschutz.** Unter den Adressen sind Anschriften von Privatpersonen (Eingaben, Wahl von
Schiedspersonen, Bauanträge). Eine Tabelle „Dokument × Adresse" wird darum nie veröffentlicht; die
Seite bekommt höchstens die Zuordnung zum Bezirk.

### 3.5 Flächen und benannte Objekte

Was das Portal (und das Land) an Flächen und Orten mit Namen hat und wie viele Begriffe und Treffer
sie **zusätzlich** brächten, wenn ein Schalter sie in die Zählung nähme (heute zählt nichts davon).
Begriffe: Name kleingeschrieben, Anführungszeichen und „e. V." entfernt, mindestens fünf Zeichen;
Schulen über ihren Eigennamen („marie-curie-gymnasium", „aloys-odenthal-schule"; Grundschulen, die
nach ihrer Straße heißen, bringen keinen neuen Begriff); Bahnhöfe als „s-bahnhof …", „bahnhof …";
Kleingärten als „kleingartenanlage …", „kgv …". Bezirk: Punkt im Stimmbezirk, Fläche in jedem
Wahlbezirk mit mindestens 5 % ihrer Fläche. Gesucht im Textstore mit demselben Matcher.

| Quelle | Objekte | verortet | Begriffe | schon im Wörterbuch | neu | neu mit Treffer | Dokumente | Paare | davon neu | Begriffe in mehreren Bezirken |
|---|---|---|---|---|---|---|---|---|---|---|
| Stadtteile (Flächen) | 50 | 50 | 47 | 1 | 46 | 46 | **4 714** | 12 015 | **6 827** | 21 |
| Schulen (NRW) | 185 | 185 | 211 | 8 | 203 | 39 | 343 | 580 | 267 | 4 |
| Bahnhöfe | 28 | 28 | 73 | 0 | 73 | 39 | 257 | 279 | 140 | 0 |
| Kitas | 369 | 367 | 350 | 85 | 265 | 65 | 200 | 235 | 117 | 7 |
| Museen | 39 | 39 | 39 | 7 | 32 | 11 | 122 | 123 | 74 | 0 |
| Kirchen | 137 | 137 | 123 | 56 | 67 | 14 | 74 | 82 | 59 | 4 |
| Sportstätten | 116 | 116 | 116 | 3 | 113 | 34 | 90 | 101 | 30 | 0 |
| Wohnbauflächen (Flächen) | 64 | 64 | 64 | 15 | 49 | 19 | 94 | 94 | 8 | 1 |
| Kleingärten | 96 | 0 | 279 | 0 | 279 | 18 | 28 | 0 | 0 | 0 |

- **Zusammen 7 443 neue Paare (25,4 % der heutigen 29 330), davon 6 827 aus den Stadtteilen.** Ohne
  Stadtteile sind es 694 (2,4 %).
- **Stadtteile sind ein anderes Maß.** „Eller" (562 Dokumente), „Garath" (492), „Gerresheim" (472),
  „Benrath" (403) nennen Gebiete, die im Mittel 1,7 Wahlbezirke überdecken (21 von 46 liegen in
  mehreren); „altstadt" (260) ist zudem ein Gattungswort. Bis auf einen stehen sie nicht im
  Wörterbuch (es besteht aus Straßen und verorteten Einzelorten; warum die Wikidata-Einträge der
  Stadtteile fehlen, ist hier nicht geprüft). In die Zählung genommen, würden sie ein Viertel der Treffer
  hinzufügen und die Bezirke nach der Prominenz ihres Stadtteilnamens gewichten. **Nur hinter einem
  Schalter, der aus ist, und nur mit Konrads Entscheidung** (§ 9).
- **Die Punktquellen sind klein und unsicher.** Kitas und Kirchen tragen Namen wie „St. Paulus", die
  auch eine Kirche, eine Schule und eine Gemeinde meinen; Schulen und Museen sind die
  verlässlichsten. Ohne Kodierung keine Präzision; zusammen +2,4 % der Paare.
- **Bebauungspläne: verworfen.** Der Landesdatensatz hat 104 Pläne der Stadt (76 Bebauungspläne,
  28 FNP-Änderungen; 34 ohne Datum, die übrigen meist von 2018 bis 2026) mit 83 Plannummern. Im
  Text stehen **320 verschiedene Plannummern in 605 Dokumenten** (Muster `NN/NNN` oder `NNNN/NNN` mit „Bebauungsplan" o. ä. in den
  120 Zeichen davor); **nur 63 davon (19,7 %) sind im Landesdatensatz**, in 245 Dokumenten, und sie
  brächten 23 neue Paare. Das Portal der Stadt hat keine Geltungsbereiche.
- **Haltestellen: Lücke** (§ 2). Viele Haltestellen heißen nach Straßen und Plätzen, die schon im
  Wörterbuch stehen (nicht gezählt); die Bahnhöfe des Portals bringen 39 neue Begriffe mit Treffern.

## 4. Validierung

### 4.1 Ergebnis der Kodierung (2026-11-23)

Zwei Kodier-Agenten haben die 200 Paare unabhängig nach `codebuch.toml` (Fassung 2026-11-23.1)
kodiert, ein Schlicht-Agent hat die fünf Uneinigkeiten entschieden. **Kodierer und Schlichter sind
dasselbe Modell** (Frage 19 an Konrad, offen): die Übereinstimmung misst Zuverlässigkeit des Codebuchs,
nicht Wahrheit, und kein Mensch hat geprüft. Labels je Aufgabe und Feld:
[../../validierung/16-ortsbezug/labels.csv](../../validierung/16-ortsbezug/labels.csv) (`bezug`,
`begriffe_kein_bezug`, `beleg_zeile`, `unsicher`; Werte als JSON, ohne Ausschnitte, Begründungen und
Anschriften; Belegzeile und `unsicher` ohne Label, wo die Kodierer abweichen). Gerechnet mit
`uv run python docs/plans/16-ortsbezug-messung.py` (Abschnitt „§ 4.1 Kodierung" der Ausgabe).

**Übereinstimmung**: `bezug` 195 von 200, **Krippendorffs α 0,917** (drei Klassen), 0,915 für
„handelt von" ja/nein; `begriffe_kein_bezug` 200 von 200. Die fünf Uneinigkeiten (A → B): dreimal
erwähnt → handelt von, zweimal handelt von → erwähnt; geschlichtet zweimal zu „handelt von", dreimal
zu „erwähnt". Unsicher nannten sich A in 22, B in 28, beide in 15 Aufgaben. α ≥ 0,8, wie Stufe 3
verlangt.

**Labels**: 164 „handelt von", 31 „erwähnt", 5 „kein Bezug" (82,0 %, 15,5 %, 2,5 %); mit den
Schichtgewichten hochgerechnet auf alle Paare **82,1 % handelt von, 15,4 % erwähnt, 2,5 % kein
Bezug**. „Kein Bezug" (der Begriff meint keinen Ort im Bezirk) ist die Fehltrefferquote des
Wörterbuchs auf Paarebene: 5 von 200 (Wilson 1,1–5,7 %); die sechs Begriffe ohne Bezug sind
„marktplatz" (ein früherer Name), „schulweg" (Gattungswort), „flughafenstr." (in „Alte
Flughafenstr."), „düsseldorfer straße" (gleichnamig anderswo), „franz jürgens" und „st. cäcilia"
(Namen, die anderes meinen).

**Je Schicht** (Wilson, ungewichtet):

| Schicht | Paare | Label „handelt von" | Regel richtig | Regel sagt |
|---|---|---|---|---|
| Titel oder Betreff | 75 | 97,3 % (90,8–99,3) | 97,3 % (90,8–99,3) = Präzision | handelt von |
| Kern | 49 | 81,6 % (68,6–90,0) | 81,6 % (68,6–90,0) = Präzision | handelt von |
| Begleittext und Rest | 76 | **67,1 % (55,9–76,6)** | 32,9 % (23,4–44,1) | erwähnt |

**Die Regel gegen die Labels** (Hauptmaß hochgerechnet, Intervalle aus dem geschichteten Bootstrap;
ungewichtet mit Wilson):

| Regel | TP / FP / FN | Präzision hochgerechnet | Recall hochgerechnet | **F1 hochgerechnet** | F1 ungewichtet | F1 Gegenklasse | κ (95 %) |
|---|---|---|---|---|---|---|---|
| **Regel: Titel, Betreff oder Kern** | 113 / 11 / 51 | 0,927 (0,884–0,964) | 0,661 (0,628–0,700) | **0,772 (0,740–0,804)** | 0,785 (P 91,1 %, 84,8–95,0; R 68,9 %, 61,5–75,5) | 0,459 | **0,279 (0,161–0,399)** |
| A: Regel oder ≥ 3 Erwähnungen im Begleittext | 126 / 11 / 38 | 0,935 (0,896–0,968) | 0,748 (0,698–0,798) | 0,831 (0,793–0,867) | 0,837 | 0,522 | 0,374 (0,241–0,510) |
| B: nur Titel oder Betreff | 73 / 2 / 91 | 0,973 (0,933–1,000) | 0,490 (0,462–0,521) | 0,652 (0,622–0,681) | 0,611 | 0,439 | 0,226 (0,149–0,305) |
| C: Regel oder Listenzeile oder Adresse im Begleittext | 138 / 15 / 26 | 0,913 (0,869–0,952) | 0,827 (0,778–0,879) | 0,868 (0,833–0,901) | 0,871 | 0,526 | 0,399 (0,239–0,548) |
| trivial: alles handelt von | 164 / 36 / 0 | 0,821 (0,771–0,868) | 1,000 | **0,902 (0,871–0,929)** | 0,901 | – | 0 |

- **Das Kriterium ist nicht erfüllt**: F1 0,772, das Intervall reicht bis 0,804 und schließt die
  Schwelle gerade noch ein, der Punktwert liegt darunter. Gegen jeden Kodierer allein: 0,766 (A),
  0,763 (B); ohne die 15 Aufgaben, die beide unsicher nannten: 0,793. Keine Lesart der Kodierung
  hebt die Regel über 0,8.
- **Die Regel schlägt die triviale Regel nur im κ** (Intervall 0,161–0,399, über 0; Annahme 9.2),
  **nicht im F1**: „alles handelt von" kommt auf 0,902. Bei 82 % Prävalenz entfernt jede der
  gemessenen Regeln mehr Paare, die von einem Ort handeln, als solche, die ihn nur erwähnen. κ von
  0,28 bis 0,40 heißt: die Stelle trägt Information über den Ortsbezug, aber wenig.
- **Die Regel scheitert am Recall, wie erwartet** (§ 5 der ersten Fassung schätzte F1 ≈ 0,75): zwei
  Drittel der Paare mit bestem Treffer im Begleittext handeln von dem Ort. Die Präzision ist hoch
  (92,7 %), im Titel fast vollständig (97,3 %), im Kern geringer (81,6 %).

**Fehler der Regel nach Ursache** (62: 51 falsch „erwähnt", 11 falsch „handelt von"; Zuordnung des
Mess-Agenten nach Titel, Belegzeile und Bemerkungen der Kodierer, Aufgaben-IDs im Skript):

| Ursache | Fehler | Beispiele (Art des Dokuments) |
|---|---|---|
| **Falsch „erwähnt" (51, alle mit bestem Treffer im Begleittext)** | | |
| Liste, Tabelle oder Bericht mit ortsbezogenen Punkten: Kommissionsberichte (Radverkehr, Spielplätze, Kö-Bogen, Opernhaus), Maßnahmen- und Standortlisten (Haltestellen, Lichtsignalanlagen, Winterdienst, Baumpflanzungen, Altkleidercontainer), Controlling-, Sachstands- und Förderberichte, Messstationen der Luftqualität, Veränderungsverzeichnis, Mitteilungen der Verwaltung | 28 | Informations-, BV-Informations-, Berichtsvorlagen |
| Gegenstand im Begleittext, Titel und Kern nennen ihn mit einem anderen Namen (Stadtteil, Gebäude, Linie, Projekt), der Ort verortet, begrenzt oder bedient ihn: Tunnel unter einer Straße, Gelände zwischen Straßen, Poller vor einer Schule, P+R-Platz einer Stadtbahnlinie, Ersatzspielfeld, Fällungen an einem Weg | 17 | BV-Informationsvorlagen, Beschluss- und Bedarfsvorlagen, Anträge |
| Anfrage oder Antrag: der Ort steht in Einleitung oder Begründung, die Frage oder der Antrag richtet sich auf ihn, ohne ihn zu nennen (oder 11 erkennt die Fragen nicht als Abschnitt) | 6 | Anfragen, Anträge |
| **Falsch „handelt von" (11; 9 mit bestem Treffer im Kern, 2 im Titel)** | | |
| kein Bezug: Gattungswort („Schulweg"), früherer Name („ehem. Marktplatz"), Teil eines längeren Straßennamens („Alte Flughafenstr.") | 3 | Anträge |
| Beispiel in einer Anfrage oder einem Antrag zu Bezirk oder Stadt („z. B. …straße"), ohne dass sich eine Frage oder Maßnahme auf den Ort richtet | 3 | Anfrage, Anträge |
| Umstand oder Begründung für eine andere Sache (Brückenneubau als Grund einer Priorität, Badneubau als zu berücksichtigender Umstand) | 2 | Anträge |
| früherer Vorgang (Titel einer unbeantworteten Anfrage), Name einer Organisation (Kirchengemeinde als Zuschussempfänger), Herkunft oder Richtung („jenseits der …") | 3 | Anfrage, BV-Beschlussvorlage |

25 der 51 falsch „erwähnt" haben eine Listenzeile oder Adresse im Begleittext; Nebenregel C fängt
sie, bezahlt mit 4 zusätzlichen falsch „handelt von". Vier der falsch „erwähnt" (Gelände,
Parkgebiet, Bauabschnitt, Planungskonzept einer Nachbarstraße) liegen nach den Bemerkungen der
Kodierer in einem Nachbarstadtteil; nach dem Vorschlag (a) für Fassung 2 des Codebuchs (§ 9.13) wären
sie „kein Bezug" und die Regel dort richtig. Auch dann bliebe sie unter der Schwelle (hochgerechnet
F1 0,784; Nebenregel C 0,880) — nachgerechnet von Hand, nicht im Skript, weil Fassung 2 nicht
kodiert ist.

### 4.2 Was ohne Kodierer schon prüfbar ist

- **Treffer und Stelle sind deterministisch und vollständig**: 30 695 der 30 695 Paare (Dokument,
  Begriff) mit Rohtext sind genau die des Index, keines mehr, keines weniger (§ 3.0). Die Stelle
  hängt an den Abschnitten von 11, deren Beschlussvorschlag an 200 kodierten Dokumenten streng zu
  0,940 (0,898–0,965) richtig ist ([11-struktur.md](11-struktur.md), § 4.1).
- **Hausnummern gegen die Hauskoordinaten** (Labels aus Fremddaten, § 2.6 (2) des Plans): 92,3 %
  verortbar; von den verorteten liegen 10 143 von 10 146 (99,97 %) im Bezirk, dem das Wörterbuch die
  Straße zuordnet — eine Gegenprobe des Wörterbuchs selbst.

### 4.3 Stichprobe, Codebuch, Kodieraufgaben

**Stichprobe**: 200 Paare (Dokument, Wahlbezirk) mit Stelle, aus 200 verschiedenen Dokumenten,
geschichtet nach der besten Stelle, proportional mit mindestens 30 je Schicht (Rest nach größtem
Bruchteil, `allocate` aus 11), je Schicht gemischt mit Seed 20261123; ein Paar, dessen Dokument schon
gezogen ist, wird übersprungen
([../../validierung/16-ortsbezug/stichprobe.csv](../../validierung/16-ortsbezug/stichprobe.csv):
`aufgabe`, `paar`, `id`, `wahlkreis_id`, `schicht`, `gewicht`).

| Schicht | Paare mit Stelle | Stichprobe | Gewicht | Regel sagt |
|---|---|---|---|---|
| Titel oder Betreff | 12 097 | 75 | 161,29 | handelt von |
| Kern | 5 060 | 49 | 103,27 | handelt von |
| Begleittext und Rest | 12 132 | 76 | 159,63 | erwähnt |

**Codebuch**: [../../validierung/16-ortsbezug/codebuch.toml](../../validierung/16-ortsbezug/codebuch.toml),
Fassung 2026-11-23.1, mit **festgelegtem Antwortformat** (eine JSON-Zeile je Aufgabe: `aufgabe`,
`bezug` ∈ {`handelt_von`, `erwaehnt`, `kein_bezug`}, `begriffe_kein_bezug`, `beleg_zeile`,
`unsicher`, `bemerkung`). Die Frage: **handelt das Dokument von einem Ort in diesem Wahlbezirk, oder
erwähnt es ihn nur?** „Handelt von" heißt: das Dokument sagt etwas Eigenes über den Ort oder über
etwas dort — beantragt, beschließt, fragt, berichtet, plant —, **auch als ein Punkt einer Liste**
(Bauunterhaltung, Förderliste, Fällliste, Radverkehrskommission), auch wenn der Ort den Gegenstand
verortet („Höhe …straße") oder ein Plangebiet begrenzt. „Erwähnt": Anschrift, Sitzungsort, Richtung,
Beispiel, Vergleich, früherer Vorgang, Name ohne Bezug zum Ort, Adressliste. „Kein Bezug": der
Begriff meint keinen Ort im Bezirk (Gattungswort wie „Schulweg", Name, andere Stadt). Die Begriffe
gehören zum Bezirk, weil das Wörterbuch es sagt; welcher Abschnitt einer Grenzstraße gemeint ist,
wird nicht kodiert. Namen und Anschriften kommen in keine Antwort.

Die Definition ist **bewusst weit**: eine Maßnahme an einem Ort ist Aufmerksamkeit für ihn, auch in
einer Liste. Eine enge Definition („der Ort ist der Hauptgegenstand") hätte die Regel nur
nachgesprochen — Hauptgegenstand ist, was im Titel steht — und Listen im Beschlussvorschlag (eine
Reihe von Straßen für Tempo 30) gegen sie gezählt (§ 9.1).

**Kodieraufgaben**: `/media/konrad/xtraspace/georep/messdaten/kodierung/16-ortsbezug/aufgaben.jsonl`
(200 Zeilen, 1 118 KB, lokal, nicht im Repo, mit README): je Aufgabe ID, Drucksache, Dokumentart,
Datum, Titel, Wahlbezirk mit Name, die Begriffe des Bezirks im Dokument mit Art, Zeilen und „im
Titel", der Rohtext als Zeilen (höchstens 600; 3 Dokumente gekürzt, ihre Zeilen mit Begriffen hinter
Zeile 600 kommen mit sechs Zeilen Rand als `auszug`), die Zeilen mit Seitenanfang. Reihenfolge
gemischt (Seed 20261124). Daneben `regel.jsonl` mit Stelle, Regel, Nebenregeln A bis C und
Erwähnungen — **den Kodierern nicht zeigen**. Antworten kommen als `antworten-<kodierer>.jsonl`
daneben, die Endlabels nach Schlichtung als `validierung/16-ortsbezug/labels.csv` (Spalten wie 11
und 14; das Skript liest die Zeilen mit `frage = bezug`). Format vorläufig, bis F4 gemerged ist.

**Maße** (Codebuch `[mass]`, vorab festgelegt; das Skript rechnet sie, sobald `labels.csv` da ist):
**Hauptmaß F1 der Klasse „handelt von" für die Regel, mit den Schichtgewichten hochgerechnet**,
Intervall aus einem geschichteten Bootstrap (2 000 Ziehungen, Seed 20261123); „erwähnt" und „kein
Bezug" sind beide „nicht handelt von". Daneben ohne Einfluss auf das Kriterium: ungewichtet, F1 der
Gegenklasse, Cohens κ zwischen Regel und Label mit Bootstrap-Intervall (liegt es über 0, schlägt die
Regel die triviale „alles handelt von"; § 9.2), dieselben Maße für die Nebenregeln A bis C und für die
triviale Regel „alles handelt von", der Anteil „handelt von" je Schicht mit Wilson-Intervall, der
hochgerechnete Anteil „kein Bezug" (Fehltreffer des Wörterbuchs) und Krippendorffs α zwischen den
Kodierern (nominal, drei Klassen; Stufe 3 verlangt α ≥ 0,8).

**Was die Stichprobe auflösen kann.** Mit 124 Paaren in den beiden Schichten, für die die Regel
„handelt von" sagt, ist die Präzision auf rund ± 5 Punkte bestimmt; der Recall hängt an den 76 Paaren
der dritten Schicht, die für 12 132 Paare stehen — das Intervall um F1 wird darum breit (geschätzt
± 0,05 bis 0,07; gemessen 0,740–0,804, also rund ± 0,03).

### 4.4 Bestätigung: Runde 2 gegen ortsbezug-entwurf-2 (2026-11-23)

Gerechnet mit `uv run python docs/plans/16-ortsbezug-messung.py --auswertung-2`, unverändert nach
§ 5.3 (Commit `1902bd4`, gepusht vor der Kodierung); keine Anpassung an diese Labels. 100 Paare der
Stichprobe 2 (§ 5.4), zwei Kodier-Agenten nach Codebuch Fassung 2, ein Schlicht-Agent für die eine
Uneinigkeit. **Kodierer und Schlichter sind dasselbe Modell** (Frage 19, offen). Labels:
[../../validierung/16-ortsbezug/labels-2.csv](../../validierung/16-ortsbezug/labels-2.csv) (Spalten
wie `labels.csv`; Belegzeile ohne Label in 16, `unsicher` in 7 Aufgaben, wo die Kodierer abweichen).

**Übereinstimmung**: `bezug` 99 von 100, **α 0,974** (drei Klassen), 0,972 für „handelt von"
ja/nein; `begriffe_kein_bezug` 100 von 100. Die eine Uneinigkeit (16-2-002, A handelt von, B erwähnt)
ist zu „handelt von" geschlichtet. Unsicher: A 11, B 8, beide 6.

**Labels**: 77 „handelt von", 13 „erwähnt", 10 „kein Bezug"; hochgerechnet **78,3 % / 13,6 % /
8,0 %**. „Kein Bezug" ist mit Regel (a) der Fassung 2 viermal so häufig wie in Runde 1 (10 von 100,
Wilson 5,5–17,4 %, gegen 5 von 200): sechs der zehn sind Gegenstände in einem anderen Stadtteil oder
Stadtbezirk, die über eine durchlaufende Straße (Grafenberger Allee, Münchener Straße, Mettmanner
Straße …) ins Wörterbuch des Bezirks fallen, eines eine gleichnamige Straße in einer Nachbarstadt.

**Je Schicht** (Wilson, ungewichtet):

| Schicht | Paare | Label „handelt von" | Verfahren richtig | C sagt |
|---|---|---|---|---|
| Titel oder Betreff | 34 | 94,1 % (80,9–98,4) | 94,1 % (80,9–98,4) = Präzision | handelt von |
| Kern | 32 | 71,9 % (54,6–84,4) | 71,9 % (54,6–84,4) = Präzision | handelt von |
| Begleittext und Rest | 34 | 64,7 % (47,9–78,5) | 52,9 % (36,7–68,5) | 14 handelt von, 20 erwähnt |

**Verfahren und Vergleiche** (hochgerechnet, Intervalle aus dem geschichteten Bootstrap; ungewichtet
mit Wilson):

| Verfahren | TP / FP / FN | Präzision | Recall | **F1 hochgerechnet** | F1 ungewichtet | F1 Gegenklasse | κ (95 %) |
|---|---|---|---|---|---|---|---|
| **C = `ortsbezug-entwurf-2`** | 65 / 15 / 12 | 0,841 (0,763–0,914) | 0,816 (0,741–0,893) | **0,828 (0,769–0,882)** | 0,828 (P 81,2 %, 71,3–88,3; R 84,4 %, 74,7–90,9) | 0,420 | **0,249 (0,023–0,466)** |
| ursprüngliche Regel (Titel, Betreff, Kern) | 55 / 11 / 22 | 0,877 (0,799–0,943) | 0,663 (0,611–0,728) | 0,755 (0,698–0,808) | 0,769 | 0,461 | 0,248 (0,070–0,438) |
| A: Regel oder ≥ 3 Erwähnungen im Begleittext | 59 / 12 / 18 | 0,870 (0,790–0,938) | 0,724 (0,654–0,801) | 0,790 (0,730–0,846) | 0,797 | 0,467 | 0,273 (0,068–0,476) |
| B: nur Titel oder Betreff | 32 / 2 / 45 | 0,941 (0,853–1,000) | 0,506 (0,458–0,562) | 0,658 (0,603–0,711) | 0,577 | 0,483 | 0,244 (0,115–0,382) |
| trivial: alles handelt von | 77 / 23 / 0 | 0,783 (0,701–0,857) | 1,000 | **0,878 (0,824–0,923)** | 0,870 | – | 0 |

- **Das Kriterium aus § 5.3 ist erfüllt**: F1 0,828 ≥ 0,8, und das κ-Intervall liegt über 0
  (untere Grenze 0,023). Gegen jeden Kodierer allein 0,828 (A) und 0,835 (B), ohne die 6 Aufgaben,
  die beide unsicher nannten, 0,833.
- **Knapp und ohne Spielraum**: das F1-Intervall reicht bis 0,769, die untere κ-Grenze liegt nahe 0.
  Wie in Runde 1 schlägt **keine Regel die triviale im F1** (0,878): bei 78 % Prävalenz nimmt auch
  C etwas mehr Paare zu viel heraus, als sie richtig ausscheidet, κ 0,25 heißt „schwache Trennung".
- **Die Rangfolge der Regeln wiederholt sich** an frischen Paaren und mit dem neuen Codebuch: C vor
  A vor der ursprünglichen Regel vor B, wie in Runde 1 (0,868, 0,831, 0,772, 0,652). C, A und die
  ursprüngliche Regel liegen 0,02 bis 0,04 tiefer, B gleich; vermutlich auch, weil Regel (a) „kein
  Bezug" vermehrt und diese Fälle meist vorn stehen (7 der 10 im Kern oder Titel).

**Fehler des Verfahrens nach Ursache** (27: 12 falsch „erwähnt", 15 falsch „handelt von";
Zuordnung des Mess-Agenten nach Titel, Belegzeile und Bemerkungen der Kodierer, die meist die Regel
nennen):

| Ursache | Fehler |
|---|---|
| **Falsch „erwähnt" (12, alle im Begleittext, keine Listenzeile, keine Hausnummer)** | |
| Gegenstand im Begleittext verortet oder benannt, der Titel nennt ihn anders (Park, Friedhof, Stadion, Block, Abschnitt, Ersatzstandort) | 8 |
| Anfrage oder Beschluss richtet sich auf Beispielstraßen (Regel (c)) | 2 |
| Listenpunkt mit längerem Vorlauf („Priorität 2 – …straße", 14 Zeichen vor dem Begriff) | 1 |
| Messwerte je Station als Antwort auf eine Anfrage (geschlichtet) | 1 |
| **Falsch „handelt von" (15)** | |
| Regel (a): Gegenstand in einem anderen Stadtteil oder Stadtbezirk, eine andere Bezirksvertretung berät | 6 |
| gleichnamige Straße in einer Nachbarstadt | 1 |
| Anschrift in einer Liste oder als Beleg (Schiedsperson, Dienstsitz, Projektraum, Einrichtung) — die Erweiterung von C | 4 |
| Beispiel oder Vergleich (Regel (c)) | 2 |
| Zuschuss an Organisation oder Fest, die Aussage hängt nicht am Ort (Regeln (d), (e)) | 2 |

C bezahlt ihre Erweiterung um Listen und Adressen mit 4 falsch „handelt von" (Anschriften im
Begleittext) und fängt dafür 10 Paare, die die ursprüngliche Regel verliert. Sieben der 15 falsch
„handelt von" sind „kein Bezug", sechs davon nach Regel (a): die Stelle kann nicht sehen, in welchem Stadtteil
eine durchlaufende Straße gemeint ist — das kann nur die Hausnummer (§ 3.4) oder ein Stadtteilname
im Text.

## 5. Urteil gegen das Kriterium

**Ergebnis (2026-11-23, nach der Bestätigung): bauen — `ortsbezug-entwurf-2` (Nebenregel C) besteht
an frischen 100 Paaren (F1 0,828 ≥ 0,8, κ 0,249 mit Intervall 0,023–0,466 über 0) und wird die
Gewichtsvariante `ortsbezug`, nicht die Standardzählung; Stelle und Hausnummern werden gebaut (§ 5.5).**

Kriterium (unverändert): F1 der Regel ≥ 0,8; Hausnummern nur, wenn ≥ 80 % verortbar sind.
Entscheidungsregel, vorab festgelegt (erste Fassung dieses Abschnitts, vor der Kodierung):
F1 ≥ 0,8 und κ-Intervall über 0 → die Regel wird Gewichtsvariante `ortsbezug`; F1 < 0,8, aber eine
Nebenregel (A oder C) ≥ 0,8 und besser als die triviale Regel im κ → umbauen auf diese Nebenregel,
mit einer neuen Stichprobe zur Bestätigung (sie ist an derselben Kodierung ausgesucht, also
explorativ; Vorbild 14, § 4.2); alle unter 0,8 oder keine besser als die triviale Regel → die Regel
wird verworfen, die Stelle bleibt als Spalte und als Gewicht nach Stelle (explorativ); α < 0,8 →
zurück in Stufe 1.

### 5.1 Urteil (Abschluss der Stufe 1, 2026-11-23): umbauen — Regel nicht bestätigt, Nebenregel C zur Bestätigung; Stelle und Hausnummern bauen

- **Regel „handelt von" (Titel, Betreff oder Kern): Kriterium nicht erfüllt.** F1 hochgerechnet
  **0,772 (0,740–0,804)**, Präzision 0,927, Recall 0,661; κ 0,279 (0,161–0,399). α zwischen den
  Kodierern 0,917, das Codebuch ist also scharf genug; die Regel ist zu schmal.
- **Nach der vorab festgelegten Regel: umbauen auf Nebenregel C** (Regel oder ein Begriff im
  Begleittext in einer Listenzeile oder mit Hausnummer): F1 **0,868 (0,833–0,901)**, κ 0,399
  (0,239–0,548), beides über den Schwellen. Nebenregel A (≥ 3 Erwähnungen) erfüllt sie auch (0,831;
  κ 0,374), schwächer. C ist **an derselben Kodierung ausgesucht und darum explorativ**; Stufe 2 baut
  sie erst als Variante, wenn eine **neue Stichprobe** sie bestätigt (Vorschlag: 100 Paare, gleiche
  Schichtung, Seed neu, ohne die 200 Dokumente, Codebuch Fassung 2 aus § 9.13; Kriterium wie hier).
- **Was der Vergleich mit der trivialen Regel sagt**: keine Regel schlägt „alles handelt von" im F1
  (0,902). Hochgerechnet handeln **82,1 % aller Paare** von einem Ort im Bezirk, 15,4 % erwähnen ihn,
  2,5 % haben keinen Bezug. Die binäre Zählung der Arbeit zählt also überwiegend Dokumente, die von
  einem Ort im Bezirk handeln, und ein Filter nach der Stelle nähme mehr richtige als falsche Paare
  heraus. Die Regel gehört darum **nicht** in die Standardzählung, auch nicht in der Fassung C;
  bestätigt wird sie eine Gewichtsvariante neben den 26 der Seite, nicht mehr. Für die Seite ist
  die Kodierung selbst der Befund: „82 % der Treffer handeln von einem Ort im Bezirk, 2,5 % sind
  Fehltreffer des Wörterbuchs — geprüft von zwei KI-Kodierern an 200 Paaren, nicht von Menschen".
- **Stelle je Treffer: bauen.** Exakt, deterministisch, deckungsgleich mit dem Index, rund 40 s für
  die Hauptperiode; im Titel steht ein Ort zu 97,3 % (90,8–99,3) als Gegenstand — die Stelle taugt
  zum Ordnen einer Trefferliste, auch ohne Regel. Zulieferer für Suche, für 21 und für Nebenregel C.
- **Hausnummern: bauen.** 92,3 % (91,7–92,7) verortbar, die untere Grenze liegt 11,7 Punkte über
  der Schwelle; Fehlerkennungen des Musters (in der Durchsicht 3 von 40, seither ausgeschlossen)
  senken die Verortbarkeit eher, als dass sie sie erhöhen. Sie tragen auch C: Adressen im
  Begleittext sind dort ein Zeichen für „handelt von".
- **Flächen: Stadtteile messbar, aber ein anderes Maß** (+23 % Paare, Gebiete statt Orte) — nur als
  Schalter, der aus ist, und nur nach Konrads Entscheidung; Punktquellen +2,4 %, ohne Präzision;
  **Bebauungspläne verworfen** (der Landesdatensatz deckt 19,7 % der genannten Plannummern).
- **Wirkung**: keine Variante ändert die stärkste Verzerrung (r ≥ 0,76 in allen); wer die
  Wörterbuchgröße herausnehmen will, braucht weiter „Treffer je Begriff", nicht den Ortsbezug.

**Vorbehalt.** Kodierer und Schlichter sind dasselbe Modell (Frage 19); α 0,917 misst, wie
eindeutig das Codebuch für dieses Modell ist. Die Grenze von „handelt von" bei Listen und Beispielen
ist eine Definitionsfrage (§ 9.1, § 9.13); mit einer engeren Definition (Listenpunkte als „erwähnt") stiege
der Recall der Regel und fiele die Präzision der trivialen; ob die Regel dann besteht, ist nicht
gemessen. Das Urteil hängt also an § 9.1, und Fassung 2 des Codebuchs muss es an der
Bestätigungsstichprobe neu prüfen.

### 5.2 Verlauf

Die erste Fassung dieses Abschnitts (Commit `67d038f`, vor der Kodierung) schätzte nach einer
Durchsicht von 40 Paaren außerhalb der Stichprobe F1 ≈ 0,75 für die Regel und ≈ 0,90 für die
triviale; gemessen sind 0,772 und 0,902.

### 5.3 Umbau, Runde 2: vorab festgelegt (2026-11-23, 20:56, vor Stichprobe, Codebuch und Kodierung)

Eine Runde Umbauen nach § 8 des Meta-Plans, wie bei 12 und 14. Dieser Abschnitt ist geschrieben und
committet, bevor die Stichprobe der Runde 2 gezogen, das Codebuch Fassung 2 geschrieben und ein Paar
kodiert ist; er wird danach nicht mehr geändert, Ergebnisse kommen in einen eigenen Abschnitt.

**Verfahren, das bestätigt werden soll: `ortsbezug-entwurf-2` = Nebenregel C, genau so, wie sie in
§ 4.1 gemessen ist**, ohne weitere Anpassung an die Labels der Runde 1. Ein Paar (Dokument,
Wahlbezirk) handelt von einem Ort des Bezirks, wenn mindestens ein Begriff seines Wörterbuchs
(a) im Titel, im Betreff oder im Kern (Beschlussvorschlag, Fragen) steht, oder (b) im Begleittext in
einer Listenzeile steht (die Zeile ohne Leerraum am Rand hat höchstens 60 Zeichen, vor dem Begriff
stehen in ihr höchstens 12) oder eine Hausnummer trägt (Muster `HAUSNR` des Messskripts mit dem
Ausschluss „Standort"). Code: `rule_columns`, Spalte `neben_c`, Konstanten `LISTE_MAX_ZEILE = 60`,
`LISTE_MAX_VORLAUF = 12` im Messskript, unverändert seit Commit `7102908`; im Skript heißt die
Fassung `FASSUNG_2 = "neben_c"`.

**Kriterium** (gemessen wie in § 4.1): F1 der Klasse „handelt von", mit den Schichtgewichten der
Stichprobe 2 hochgerechnet, **≥ 0,8**, **und** das 95-%-Intervall von Cohens κ zwischen Verfahren
und Label (geschichteter Bootstrap, 2 000 Ziehungen, Seed 20261123) **liegt über 0**. „Erwähnt" und
„kein Bezug" sind beide „nicht handelt von". Labels: zwei Kodier-Agenten nach Codebuch Fassung 2
(`validierung/16-ortsbezug/codebuch-2.toml`: die Vorschläge (a) bis (e) aus § 9.13 als Regeln, der
Stadtbezirk und die Stadtteile des Wahlbezirks im Material), ein Schlicht-Agent für die
Uneinigkeiten.

**Stichprobe**: 100 Paare mit Stelle, Seed `"16-2"`, ohne die 200 Dokumente der Runde 1, ein Paar
je Dokument, geschichtet wie in § 4.3 (Titel/Betreff, Kern, Begleittext und Rest; proportional mit
mindestens 30 je Schicht, `allocate` aus 11). Aufgaben-IDs `16-2-NNN`.

**Rückfallregel, falls C scheitert** (F1 < 0,8 oder κ-Intervall nicht über 0): **keine Regel „handelt
von" wird gebaut**, weder C noch A noch die ursprüngliche. Gebaut werden nur die Stelle je Treffer
(Spalte und Gewichtsvariante `stelle`, explorativ) und die Hausnummern; die Seite nennt die
Kodierung als Befund (Anteil „handelt von", Fehltreffer). Nebenregel A wird **nicht** als Ersatz
geprüft: zwei Regeln an einer Bestätigungsstichprobe wären zwei Tests, und A war in Runde 1
schwächer (0,831 gegen 0,868). A, B, die ursprüngliche Regel und die triviale „alles handelt von"
werden an der Stichprobe 2 nur berichtet, explorativ. Liegt α zwischen den Kodierern unter 0,8, ist
Fassung 2 zu unscharf; eine dritte Runde gibt es nicht (§ 8 des Meta-Plans), es gilt die
Rückfallregel.

**Was ein Bestehen bedeutet**: C wird die Gewichtsvariante `ortsbezug` (§ 6) neben `stelle`, nicht
die Standardzählung; die triviale Regel wird weiter daneben berichtet (§ 9.2).

### 5.4 Runde 2: Stichprobe und Aufgaben (2026-11-23, nach § 5.3)

Gezogen und geschrieben nach dem Commit von § 5.3 (`1902bd4`), mit

```bash
nice -n 10 uv run python docs/plans/16-ortsbezug-messung.py --fassung 2 --aufgaben-2
nice -n 10 uv run python docs/plans/16-ortsbezug-messung.py --auswertung-2   # sobald labels-2.csv da ist
```

**Stichprobe** ([../../validierung/16-ortsbezug/stichprobe-2.csv](../../validierung/16-ortsbezug/stichprobe-2.csv),
nur IDs, Spalten wie Runde 1): 100 Paare aus 100 Dokumenten, keines aus Runde 1; Grundgesamtheit ohne
die 200 Dokumente der Runde 1.

| Schicht | Paare mit Stelle | Stichprobe | Gewicht | C sagt |
|---|---|---|---|---|
| Titel oder Betreff | 11 857 | 34 | 348,74 | handelt von (34) |
| Kern | 4 826 | 32 | 150,81 | handelt von (32) |
| Begleittext und Rest | 11 491 | 34 | 337,97 | handelt von 14, erwähnt 20 |

**Codebuch**: [../../validierung/16-ortsbezug/codebuch-2.toml](../../validierung/16-ortsbezug/codebuch-2.toml),
Fassung 2026-11-23.2: die Regeln (a) bis (e) aus § 9.13 je mit Beispiel, die Anweisung über
Begriffe und Bezirk nach (a), Frage, Klassen und Antwortformat wie Fassung 1 (Aufgaben-IDs
`16-2-NNN`), Maße und Kriterium aus § 5.3.

**Kodieraufgaben**: `/media/konrad/xtraspace/georep/messdaten/kodierung/16-ortsbezug/aufgaben-2.jsonl`
(100 Zeilen, 521 KB, lokal; ein Dokument über 600 Zeilen gekürzt, seine Zeilen mit Begriffen als
`auszug`), Reihenfolge gemischt (Seed `"16-2-reihenfolge"`). Neu im Material: `stadtbezirk` und
`stadtteile_im_wahlbezirk` (jeder Stadtteil der Stadtteilgrenzen 2025, der mindestens 5 % der
Fläche des Wahlbezirks deckt, mit Anteil; im Mittel 2,0 je Wahlbezirk). Daneben `regel-2.jsonl`
mit `verfahren` (= C), den anderen Regeln und der Stelle — **den Kodierern nicht zeigen**. Beide
Dateien und die Stichprobe sind über zwei Läufe bytegleich (SHA-256 `aufgaben-2.jsonl` `998b19a9…`,
`regel-2.jsonl` `ab29d8c1…`, `stichprobe-2.csv` `f91527e1…`), die Aufgaben der Runde 1 unverändert
(`20b9f85b…`).

**Auswertung** (`--auswertung-2`, mit erfundenen Labels geprüft, je einmal bestanden und nicht
bestanden): Hauptmaß und Urteil nach § 5.3, daneben die ursprüngliche Regel, A, B und die triviale
Regel explorativ, Übereinstimmung, Fehler nach Stelle und Dokumentart. Die Ergebnisse kommen in
einen eigenen Abschnitt; § 5.3 bleibt, wie er ist.

### 5.5 Urteil nach der Bestätigung (2026-11-23): bauen, mit Nebenregel C als Gewichtsvariante

Nach der Entscheidungsregel in § 5.3, ohne Anpassung an die Labels der Runde 2:

- **`ortsbezug-entwurf-2` (Nebenregel C) besteht**: F1 hochgerechnet **0,828 (0,769–0,882)**,
  Präzision 0,841, Recall 0,816, **κ 0,249 (0,023–0,466)**; α zwischen den Kodierern 0,974 (§ 4.4).
  Damit wird C die Gewichtsvariante `ortsbezug` neben `stelle` (§ 6), wie § 5.3 es für ein Bestehen
  festlegt. Die Rückfallregel greift nicht.
- **Nicht mehr als eine Variante.** Die triviale Regel „alles handelt von" liegt wieder darüber
  (F1 0,878), κ ist schwach, und die Intervalle reichen an beide Schwellen heran. Die Standardzählung
  der Arbeit bleibt, und die Seite nennt bei `ortsbezug` beides: dass sie bestätigt ist und dass sie
  nicht besser trennt als „alles zählt". An der stärksten Verzerrung ändert sie nichts (§ 3.3:
  r(Treffer, Begriffe) 0,770 mit der ursprünglichen Regel; für C in Stufe 2 nachzurechnen).
- **Was die Kodierung beider Runden als Befund trägt**: 78 bis 82 % der Paare (Dokument,
  Wahlbezirk) handeln von einem Ort im Bezirk; Fehltreffer des Wörterbuchs liegen bei 2,5 % nach
  Fassung 1 und bei 8,0 % nach Fassung 2, die Gegenstände in einem anderen Stadtteil mitzählt.
- **Stelle je Treffer und Hausnummern: bauen** wie in § 5.1. Die Hausnummer ist das Mittel gegen
  die häufigste Fehlerart von C in Runde 2 (durchlaufende Straßen, Gegenstand in einem anderen
  Stadtteil); ob „Hausnummer vor Straßenname" Standard wird, bleibt Konrads Entscheidung (§ 9.8).
- **Flächen**: unverändert (Stadtteile nur hinter einem Schalter, der aus ist; Bebauungspläne
  verworfen).

## 6. Bauplan Stufe 2

**Beitrag** `places` im Register `georep.enrich.CONTRIBUTIONS` (F2, Punkt 69), ein Schritt `places`,
offline, nach dem Rohtext (F1) und `sections` (11); Reihenfolge im Tupel: hinter 11, vor 21.

**Module** (neu):

- `src/georep/search/positions.py`, reine Funktionen: `store_view(raw, marker) -> (text, offsets)`
  (der Nachbau des Textstores mit Rohtextstelle je Zeichen; derselbe Vertrag wie
  `prep/extract.normalise_text` plus `after_marker`), `find_positions(text, offsets, matcher)` (die
  Treffer mit Spanne), `fine_position` und `coarse_position` (Abschnitt von 11 → Stelle, mit Rumpf
  und Schluss wie § 3.0), `house_number(raw, end) -> HouseNumber | None`. Das Muster der Hausnummer
  ist sprachabhängig und gehört ins Profil (Einheiten-Ausschlussliste).
- `src/georep/enrich/places.py`, der Beitrag: liest Rohtext, Abschnitte, Index, Wörterbuch, das
  Adresspaket; schreibt die Ausgaben; `SCHEMA_VERSION = 1` als Modulkonstante für den `Step`.

**Ausgaben**:

1. `processed/treffer_stellen.parquet`, Spannen nach F3: eine Zeile je Erwähnung, sortiert nach
   `id, start`: `id`, `start`, `end` (UInt32, Rohtext von F1), `kind = "ort"`, `value` (der Begriff
   des Wörterbuchs), `norm` (grobe Stelle), `section` (feine Stelle), `extractor` (`ortsbezug-1` plus
   Extraktor des Rohtexts). Hauptperiode: 66 004 Zeilen.
2. `processed/dokumente_wahlbezirke_stelle.parquet`: eine Zeile je Paar, Schlüssel
   (`id`, `wahlkreis_id`) — wie `analysis.weights.document_pairs`, nicht „eine Zeile je Korpus-ID",
   weil die Stelle am Paar hängt: `stelle` (beste grobe Stelle, null ohne Rohtext), `erwaehnungen`,
   `n_begleit`, `n_liste`, `handelt_von` (Bool, null ohne Rohtext), `wahlkreis_adresse` (Bool: das
   Paar ist durch eine verortete Adresse belegt), `extractor`. Hauptperiode: 29 330 Zeilen.
3. `processed/adressen_wahlbezirke.parquet` (nur lokal und als Zahl auf der Seite, nie als Download,
   § 3.4 Datenschutz): `id`, `start`, `end`, `begriff`, `nr`, `zusatz`, `status`
   (`genau`, `ohne_zusatz`, `mit_zusatz`, `nein`, `strasse_unbekannt`), `wahlkreis_id`.

**Paket**: `snapshots/duesseldorf-adressen/adressen.parquet` (Straße normalisiert, Nummer, Zusatz,
Wahlbezirk; 84 193 Zeilen, 92 827 Bytes), abgeleitet aus GebRef NRW (dl-de/zero-2.0) und den
Stimmbezirken des Profils, mit README nach dem Muster von `snapshots/` (Größe, SHA-256, Quelle,
Lizenz); Pages braucht so weder das 90-MB-Archiv noch Netz. `georep pack --addresses` als neue
Option (Muster `--texts`, Punkt 68). Die Ausgaben 1 und 2 laufen auf Pages aus dem Rohtextpaket von
F1 mit (rund 40 s), kein eigenes Paket.

**Gewichtsvariante `ortsbezug`** in `src/georep/analysis/weights.py`: `document_weights` bekommt
einen vierten, optionalen Faktor `position_weights` mit (`id`, `suchbegriffe`, `gewicht`), der
**vor** dem Maximum je Paar mit dem Begriffsgewicht multipliziert wird (er hängt an Dokument und
Begriff, nicht an einem allein); `g = max_t w_begriff(t) · w_stelle(d, t) · w_art(d) · w_thema(d)`
bleibt ≤ 1. Zwei feste Varianten, Namen in `settings.FIXED_VARIANTS`:

- `ortsbezug` — **bestätigt** (§ 4.4, § 5.5): Gewicht 1, wenn der Begriff im Dokument
  `ortsbezug-entwurf-2` erfüllt (im Titel, im Betreff, im Kern, oder im Begleittext in einer
  Listenzeile oder mit Hausnummer), sonst 0; das Maximum über die Begriffe ist dann genau Nebenregel
  C je Paar. Konstanten wie im Messskript (`LISTE_MAX_ZEILE = 60`, `LISTE_MAX_VORLAUF = 12`, Muster
  der Hausnummer mit Einheiten-Ausschluss), im Profil statt im Code, **ohne Änderung**: jede
  Änderung ist ein neues Verfahren und braucht eine neue Stichprobe.
- `stelle` (1 / 1 / 1 / 0,5 / 0,25 nach der besten Stelle des Begriffs, explorativ).

Die ursprüngliche Regel (ohne Listen und Adressen) wird nicht gebaut: F1 0,772 und 0,755. Verträge:
jedes Gewicht in [0, 1]; mit allen Gewichten 1 reproduziert die Variante `einheit` exakt
(`_unit_and_topics_reproduce_the_count` erweitern); Paare ohne Stelle zählen 1. Die Ausgabe des
Verfahrens für die 300 kodierten Paare kommt als `validierung/16-ortsbezug/verfahren.csv` (`paar`,
`ortsbezug`, aus `regel.jsonl` und `regel-2.jsonl`, nur IDs und Wahrheitswerte) ins Repo; ein
`slow`-Test hält den Schritt daran fest.

**Settings** (Anhängeregel aus `00-synergien.md`): Modell `PlacesSettings` vor `class Settings`, Feld
`places` am Ende; Block `# --- Vorhaben 16: Ortsbezug` am Ende von `defaults.toml`: `enabled = false`,
`position_weights = {titel = 1.0, betreff = 1.0, kern = 1.0, begleittext = 0.5, rest = 0.25}`,
`house_numbers = false`, `area_sources = []` (**aus**; ein Eintrag nähme eine Quelle aus § 3.5 in die
Zählung und änderte die Treffer, wie `city_facilities`), `house_number_units = [...]`. Im Profil
`duesseldorf.toml`: `enabled = true`, `house_numbers = true`, Paketname des Adresspakets; die
Periodenprofile erben, Mönchengladbach bleibt aus (kein GebRef-Auszug, eigene Abschnittsregeln aus
11). Jeder Schlüssel mit Kommentar und der Zahl aus diesem Dokument.

**Tests** (roter Test zuerst, CLAUDE.md):

- Beispiele aus **synthetischen** Texten: Brief mit Betreff und Antrag, Vorlage mit Beschlussdarstellung,
  BV-Informationsvorlage ohne „Sachdarstellung:" (Rumpf), Anfrage mit Einleitung, Text hinter „Mit
  freundlichen Grüßen" (Rest), Straße mit „12a", „50–54", „2 Standorte", „150 m", „2023".
- hypothesis in `tests/property/`: für jeden Rohtext ist `store_view` gleich
  `after_marker(normalise_text(raw.replace("\f", "\n")), marker)`, und jedes Zeichen des Ergebnisses
  ist die Kleinschreibung des Rohtextzeichens an seiner Stelle; die Menge der Begriffe aus
  `find_positions` ist gleich der von `build_index` auf demselben Text (Vertrag gegen das Orakel in
  `tests/property/oracle_matcher.py`); jede Erwähnung hat genau eine Stelle; die Variante mit
  Gewichten 1 ist `einheit`.
- `pytest -m slow`: auf der Hauptperiode 30 695 Paare wie hier, keines zusätzlich; Anteil verortbarer
  Adressen ≥ 0,90 als Untergrenze.
- Golden Master unberührt (der Schritt ändert keine bestehende Datei; die Varianten kommen neben die
  26); `test_report_city.py` grün (kein Stadtwort; „betrifft" kommt aus dem Profil).

**Berührte Dateien**: neu `src/georep/search/positions.py`, `src/georep/enrich/places.py`, Tests,
`snapshots/duesseldorf-adressen/`; je eine angehängte Zeile oder ein Block in
`src/georep/enrich/__init__.py`, `src/georep/settings.py`, `src/georep/defaults.toml`,
`src/georep/profiles/duesseldorf.toml`, `src/georep/analysis/weights.py` (ein Faktor, zwei Namen),
`src/georep/cli.py` und `src/georep/pack.py` (`pack --addresses`); `docs/architecture.md` (Beiträge), `docs/decisions.md`
(Eintrag ohne Nummer: Stelle aus den Abschnitten von 11 statt eigener Regeln; Hausnummer entscheidet
die Grenzstraße, erzeugt keine Treffer; Flächen hinter Schalter; Bebauungspläne verworfen mit Zahl).

## 7. Bauplan Stufe 3

**Variante im Kartenumschalter**: die Bestätigung trägt C (§ 5.5), das Budget auch; empfohlen ist
trotzdem **zuerst nur die Gewichtungszeile** (§ 9.16), weil eine Karte die Variante als bessere Zahl
lesen lässt, obwohl sie nicht besser trennt als „alles zählt". Wenn ein Radio „nur ‚handelt von‘"
neben „Treffer absolut", „je Begriff" und „Abweichung" (Makro `switcher`, `data-value-<variante>` an
41 Flächen und Zellen, eine Legende). Geschätzt 3 bis 5 KB auf `index.html` (41 Werte je Fläche und
Tabellenzelle plus Legende; die beiden Umschalter von Punkt 46 kosten zusammen 110 KB, aber vor
allem über die sechs Parteikarten, eine Bezirksvariante nur einen Bruchteil); die Luft von rund 64 KB
reicht; gemessen wird das erst in Stufe 3. In jedem Fall: die Gewichtszeilen `ortsbezug` und
`stelle` in der Tabelle „Was ändert die Gewichtung?" (zwei Zeilen, unter 1 KB), mit „explorativ" bei
`stelle` und bei `ortsbezug` dem Satz „bestätigt an 100 Paaren (F1 0,83), trennt aber nicht besser
als alle Treffer (F1 0,88)". Und der Befund der Kodierung in „Methode und Grenzen" (ein Satz, unter
0,5 KB): 78 bis 82 % der Treffer handeln von einem Ort im Bezirk, 2,5 bis 8 % sind Fehltreffer des
Wörterbuchs, geprüft von zwei KI-Kodierern an 300 Paaren in zwei Runden, nicht von Menschen
(α 0,917 und 0,974).

**Unterseite `orte.html`** (unter 500 KB, Register von F2), wenn mehr gezeigt werden soll: je
Wahlbezirk der Anteil der Treffer nach Stelle (die Tabelle aus § 3.1), die Adressen je Bezirk als
Zahl, die 57 stadtweiten Begriffe mit ihrem Anteil vorn. Keine Adressen, keine Textstellen.

**Validierung auf der Seite**: „geprüft von zwei KI-Kodierern an 100 Paaren (Bestätigung), nicht von
Menschen", F1 0,828 (0,769–0,882), κ 0,249, α 0,974, die triviale Regel daneben; die Verortbarkeit der Hausnummern mit Intervall und Quelle (GebRef NRW,
dl-de/zero-2.0).

**Tabellen im Register**: `dokumente_wahlbezirke_stelle` als Download (Parquet; als CSV rund 3 MB
geschätzt, darum Parquet), mit Spaltenbeschreibung in `schema.json`. Die Spannen und die Adressen
nicht.

## 8. Vorab festgelegte Hypothesen

Keine Analyse mit Hypothese: Vorhaben 16 ist eine Vorverarbeitung. Festgelegt vor der Kodierung sind
die Regel, die Nebenregeln, die Gewichte nach Stelle, das Hauptmaß und die Nebenmaße (§ 3.2, § 4.3,
Codebuch `[mass]`). Die Sensitivität in § 3.3 ist explorativ: fünf Varianten × zwei Spalten von
Tabelle 5 sind zehn weitere Tests derselben Frage.

## 9. Risiken und offene Fragen

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 9.1 | Ist „handelt von" weit gemeint (auch ein Punkt einer Liste von Maßnahmen) oder eng (der Ort ist Hauptgegenstand)? | Entscheidet, ob die Regel das Kriterium erreichen kann: weit trifft den Recall, eng machte die Kodierung zum Spiegel der Regel | weit, wie im Codebuch; eine Maßnahme an einem Ort ist Aufmerksamkeit für ihn |
| 9.2 | F1 der Klasse „handelt von" ist bei hoher Prävalenz schwach: gemessen kommt die triviale Regel „alles handelt von" auf 0,902, über jeder gemessenen Regel. Soll das Kriterium zusätzlich verlangen, dass die Regel die triviale schlägt (κ > 0 mit Intervall, oder F1 der Gegenklasse ≥ 0,5)? | Sonst besteht eine Regel, die nichts trennt | Kriterium unverändert; das Skript berichtet die triviale Regel und κ mit Intervall daneben, und § 5 wertet eine Regel nur als bestanden, wenn zusätzlich das κ-Intervall über 0 liegt (alle Regeln tun das: κ 0,23 bis 0,40; die F1 der Gegenklasse liegen bei 0,44 bis 0,53) |
| 9.3 | Darf ein aus GebRef NRW abgeleitetes Paket (Straße, Nummer, Zusatz, Wahlbezirk; 92 827 Bytes, dl-de/zero-2.0) ins Repo? | Pages braucht es für die Hausnummern ohne Netz | ja, unter `snapshots/duesseldorf-adressen/` mit README und Prüfsumme |
| 9.4 | Sollen Stadtteilnamen (46 neue Begriffe, +6 827 Paare, +23 %) je zählen? | Sie ändern das Maß von Orten zu Gebieten und alle Zahlen der Seite | nein; Schalter `area_sources` bleibt leer, die Zahl steht hier |
| 9.5 | Bebauungspläne: die Stadt veröffentlicht ihre Geltungsbereiche nicht im Portal, der Landesdatensatz deckt 19,7 % der genannten Nummern. Anfrage an die Stadt? | Plannummern sind eindeutige Ortsbezüge in 605 Dokumenten | nein, außerhalb des Vorhabens; Konrads Handgriff, wenn gewünscht |
| 9.6 | Haltestellen: nicht im Portal; VRR- und Rheinbahn-Daten (GTFS) und OpenStreetMap (ODbL) nicht geprüft | Briefing nennt sie | Lücke; die meisten heißen nach Straßen und Plätzen des Wörterbuchs |
| 9.7 | Adressen von Privatpersonen (Eingaben, Schiedspersonen, Bauanträge) stehen in den Dokumenten | Datenschutz | die Adresstabelle bleibt lokal; veröffentlicht wird nur die Zuordnung Paar → Bezirk |
| 9.8 | Hausnummer vor Straßenname nimmt 1 790 Paare (6,1 %) weg und erhöht r(Treffer, Begriffe) auf 0,801. Als Standard oder als Variante? | Ändert Tabelle 5 (p 0,234 → 0,194 und 0,036 → 0,025) | Variante; ob sie Standard wird, entscheidet Konrad (Nicht-Ziel des Plans: keine Zahl ändert sich still) |
| 9.9 | Die 41 Paare ohne Stelle (alle aus BR/007/2021: Text im Store, keine Zeile in der Messdatei) | Klein, aber jede Variante muss sie behandeln; F1 (Rohtextpaket) muss das Dokument tragen | zählen wie heute (Gewicht 1) |
| 9.10 | Titel: der OParl-Titel ist nicht im Index. Zählt ein Begriff, der nur im Titel steht, als Treffer? | Würde den Index ändern | nein; „Titel" ist nur die Stelle eines Treffers, der auch im Text steht |
| 9.11 | F4 ist nicht gemerged; Format der Aufgaben vorläufig | Kodier-Agenten brauchen ein festes Format | F4 übernimmt `stichprobe.csv` und liest `aufgaben.jsonl` oder erzeugt sie neu; das Antwortformat steht im Codebuch fest |
| 9.12 | Mönchengladbach und die anderen Perioden | Stufe 2 läuft für jedes Profil mit Eingaben | die Stelle geht überall, wo 11 Regeln hat; Hausnummern nur mit GebRef der Stadt (Mönchengladbach liegt in NRW, Auszug wie hier) |
| 9.13 | **Codebuch Fassung 2** (Lücken beider Kodierer, Vorschläge des Schlichters; nicht auf die gemessene Regel angewandt; umgesetzt in `codebuch-2.toml` für Runde 2, § 5.4): (a) liegt der Gegenstand in einem Stadtteil außerhalb des Bezirks, auch einem benachbarten, ist dieser Begriff `kein_bezug`; nur aus Weltwissen erschlossen → nach dem Wörterbuch und `unsicher`; der Stadtbezirk des Wahlbezirks kommt ins Material; (b) lineare Maßnahmen: Anfang, Ende und bedienter Ort → `handelt_von`, Herkunft und Richtung → `erwaehnt`; (c) Beispiele in Anfragen nur `handelt_von`, wenn sich eine Frage auf den Ort richtet; Rückblicke in Sachstandslisten → `erwaehnt`; (d) Ortsname in einem Organisationsnamen: nach Sitz und Gegenstand; (e) Veranstaltungen: „bliebe die Aussage gleich, wenn sie anderswo stattfände?" → dann `erwaehnt`, sonst `handelt_von` | Vier der 51 falsch „erwähnt" würden mit (a) zu „kein Bezug" (§ 4.1; F1 der Regel dann 0,784, C 0,880), (c) und (d) beschreiben vier der 11 falsch „handelt von" (Beispiel in einer Anfrage, Rückblick, Kirchengemeinde als Empfänger), die die Kodierer schon so lasen, aber unsicher; die Bestätigungsstichprobe braucht ein Codebuch ohne diese Lücken | Fassung 2 mit (a) bis (e) für die Bestätigungsstichprobe von Nebenregel C; die 200 Labels hier bleiben nach Fassung 1 |
| 9.14 | Kodierer und Schlichter sind dasselbe Modell (Frage 19 an Konrad, offen) | α 0,917 misst die Eindeutigkeit des Codebuchs für ein Modell, nicht Wahrheit | wie bei 11 und 14: die Seite sagt „geprüft von zwei KI-Kodierern, nicht von Menschen"; ein zweites Modell als Kodierer B, wenn Frage 19 es freigibt |
| 9.15 | Der Matcher trifft „flughafenstr." in „Alte Flughafenstr.", weil die längere Straße im Wörterbuch dieses Bezirks fehlt | Ein Fehltreffer an der Wortgrenze, den die Stelle nicht sieht (1 von 5 „kein Bezug") | außerhalb des Vorhabens; gehört zu den Wörterbuchregeln (Methodik-Review), nicht zur Stelle |
| 9.16 | Soll `ortsbezug` auf der Karte als Radio erscheinen oder nur als Zeile der Gewichtungstabelle? | Bestätigt (F1 0,828), aber κ 0,249 und unter der trivialen Regel (0,878); eine Karte lädt ein, die Variante für die bessere Zahl zu halten | nur die Gewichtungszeile und der Satz in „Methode und Grenzen"; ein Radio nur auf Konrads Wunsch |
| 9.17 | **Lücken der Fassung 2**, von beiden Kodierern in Runde 2 gemeldet (nicht angewandt, für eine Fassung 3): Straßen, die die „maßgebliche Umgebung" eines Bauvorhabens nach § 34 BauGB begrenzen (16-2-068, 16-2-079); Regel (a) bei Quartiers- oder Eigennamen, die einen fremden Stadtteil enthalten (013, 044, 014), und wenn nur der Betreff einen fremden Raum nennt (086); Regel (c) bei stadtweiten Schritten, die den Ort ausdrücklich einschließen (040, 067); Zuschüsse für Räume oder Feste, die nach dem Ort heißen (072, 084, 099) | Fünf der 15 falsch „handelt von" (040, 067, 072, 084, 086) und einer der 12 falsch „erwähnt" (068) der Runde 2 liegen in diesen Lücken | keine dritte Runde (§ 8 des Meta-Plans); die Lücken stehen hier für eine spätere Fassung, das Urteil gilt für Fassung 2 |
| 9.18 | Fassung 2 zählt Gegenstände in einem anderen Stadtteil als „kein Bezug" (Regel (a)); der Anteil „kein Bezug" steigt dadurch von 2,5 auf 8,0 % | Die Fehltrefferquote ist eine Definitionsfrage: Fassung 1 misst Fehltreffer des Wortes, Fassung 2 auch die der Lage | die Seite nennt beide mit ihrer Fassung; durchlaufende Straßen sind der Fall, den die Hausnummer (§ 3.4) entscheidet |

## 10. Änderungen durch die Synergie (füllt der Supervisor)
