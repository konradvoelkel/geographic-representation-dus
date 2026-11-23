# Vorhaben 16: Ortsbezug verfeinern

Stand 2026-11-23, Stufe 1 (Messen), Branch `feat/16-ortsbezug`. Briefing:
[../plan-vorverarbeitung-2026-11.md](../plan-vorverarbeitung-2026-11.md), § 11 „16 Ortsbezug
verfeinern". Messskript: [16-ortsbezug-messung.py](16-ortsbezug-messung.py). Codebuch und Stichprobe:
[../../validierung/16-ortsbezug/](../../validierung/16-ortsbezug/).

**Urteil, vorläufig: bauen in zwei Teilen, die Regel „handelt von" wartet auf die Kodierung.**
Die Stelle jedes Treffers (Titel, Betreff, Kern, Begleittext, Rest) ist exakt messbar und deckt den
Index der Arbeit ohne Rest; die Hausnummern erfüllen ihr Kriterium (92,3 % verortbar, Schwelle 80 %).
Ob die Regel „handelt von" das Kriterium F1 ≥ 0,8 erreicht, entscheidet die Kodierung der 200 Paare;
eine Durchsicht außerhalb der Stichprobe lässt erwarten, dass sie am Recall scheitert (§ 5).
Unabhängig davon ändert keine Variante die stärkste Verzerrung: die Trefferzahl hängt an der Größe
des Wörterbuchs mit r = 0,765, nur mit „handelt von" mit r = 0,770.

Die drei Zahlen, auf die es ankommt:

1. **41,3 % der Paare (Dokument, Wahlbezirk) haben ihren besten Treffer in Titel oder Betreff, 17,3 %
   im Kern (Beschlussvorschlag, Fragen), 41,1 % nur im Begleittext**, 0,3 % nur im Rest
   (Anlagenliste, Kopf, hinter der Grußformel). Die Regel „Titel, Betreff oder Kern" nennt damit
   17 157 von 29 289 Paaren „handelt von" (58,6 %); in Informationsvorlagen nur 9,0 %, in Anträgen
   81,0 %.
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
die Kodierung; das Codebuch zählt solche Listenpunkte als „handelt von" (§ 4).

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

### 4.1 Was ohne Kodierer schon prüfbar ist

- **Treffer und Stelle sind deterministisch und vollständig**: 30 695 der 30 695 Paare (Dokument,
  Begriff) mit Rohtext sind genau die des Index, keines mehr, keines weniger (§ 3.0). Die Stelle
  hängt an den Abschnitten von 11, deren Beschlussvorschlag an 200 kodierten Dokumenten streng zu
  0,940 (0,898–0,965) richtig ist ([11-struktur.md](11-struktur.md), § 4.1).
- **Hausnummern gegen die Hauskoordinaten** (Labels aus Fremddaten, § 2.6 (2) des Plans): 92,3 %
  verortbar; von den verorteten liegen 10 143 von 10 146 (99,97 %) im Bezirk, dem das Wörterbuch die
  Straße zuordnet — eine Gegenprobe des Wörterbuchs selbst.

### 4.2 Stichprobe, Codebuch, Kodieraufgaben (vorbereitet, nicht kodiert)

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
± 0,05 bis 0,07).

## 5. Urteil gegen das Kriterium

Kriterium (unverändert): F1 der Regel ≥ 0,8; Hausnummern nur, wenn ≥ 80 % verortbar sind.

- **Hausnummern: bauen.** 92,3 % (91,7–92,7) verortbar, die untere Grenze liegt 11,7 Punkte über
  der Schwelle. Fehlerkennungen des Musters (in der Durchsicht 3 von 40, seither ausgeschlossen)
  senken die Verortbarkeit eher, als dass sie sie erhöhen; dass zufällige Zahlen an einer Straße
  als Hausnummer existieren, ist der eine Weg, auf dem die Zahl zu hoch sein könnte, und er ist
  durch die Durchsicht klein.
- **Stelle je Treffer: bauen.** Exakt, deterministisch, deckungsgleich mit dem Index, rund 40 s für
  die Hauptperiode; Zulieferer für Suche und Seitenstruktur, für 21 (ein Betrag gehört zum Ort des
  Kerns) und für die Regel, wie immer sie nach der Kodierung aussieht.
- **Regel „handelt von": offen, erwartet umbauen.** Eine Durchsicht von 40 Paaren mit bestem Treffer
  im Begleittext außerhalb der Stichprobe (Mess-Agent, nach dem Codebuch gelesen, **keine Kodierung**)
  fand rund 28 „handelt von" (Listen von Maßnahmen, Kommissionsberichte, Standorte von Stationen,
  Förderlisten), rund 8 „erwähnt" (Anschrift einer Dienststelle, Beispiel in einer Anfrage, Richtung,
  frühere Testphase anderswo) und 4 Grenzfälle. Grob gerechnet: wenn die Regel in den beiden
  vorderen Schichten zu 90 % richtig liegt und im Begleittext zwei Drittel „handelt von" stehen, ist
  der Recall 0,9 · 17 157 / (0,9 · 17 157 + 0,67 · 12 132) ≈ 0,65 und **F1 ≈ 0,75 — unter der
  Schwelle**; die triviale Regel „alles handelt von" käme auf F1 ≈ 0,90. **Das ist eine Schätzung,
  kein Ergebnis**, und sie benennt die Schwäche des Kriteriums (§ 9.2).
- **Flächen: Stadtteile messbar, aber ein anderes Maß** (+23 % Paare, Gebiete statt Orte) — nur als
  Schalter, der aus ist, und nur nach Konrads Entscheidung; Punktquellen (Schulen, Museen, Bahnhöfe,
  Kitas, Kirchen, Sportstätten) +2,4 %, ohne Präzision; **Bebauungspläne verworfen** (der
  Landesdatensatz deckt 19,7 % der genannten Plannummern).
- **Wirkung**: keine Variante ändert die stärkste Verzerrung (r ≥ 0,76 in allen); die Regel ist eine
  weitere Gewichtungsvariante neben den 26 der Seite, keine Korrektur.

**Was das Urteil umwirft.** F1 der Regel ≥ 0,8 an der Kodierung und κ-Intervall über 0 (§ 9.2) →
die Regel wird Gewichtsvariante `ortsbezug` wie in § 6. F1 < 0,8, aber eine Nebenregel (A oder C) ≥ 0,8 und besser als die triviale
Regel im κ → umbauen auf diese Nebenregel, mit einer neuen Stichprobe zur Bestätigung (sie ist an
derselben Kodierung ausgesucht, also explorativ; Vorbild 14, § 4.2). Alle unter 0,8 oder keine
besser als die triviale Regel → die Regel wird verworfen, die Stelle bleibt als Spalte und als
Gewicht nach Stelle (Sensitivität, nicht validiert, auf der Seite „explorativ"). α < 0,8 zwischen
den Kodierern → das Codebuch ist zu unscharf, zurück in Stufe 1 (eine Runde).

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
bleibt ≤ 1. Zwei feste Varianten, Namen in `settings.FIXED_VARIANTS`: `ortsbezug` (nur „handelt
von": Gewichte 1 / 1 / 1 / 0 / 0) — **nur, wenn die Kodierung das Kriterium bestätigt** — und
`stelle` (1 / 1 / 1 / 0,5 / 0,25, explorativ). Verträge: jedes Gewicht in [0, 1]; mit allen
Stellengewichten 1 reproduziert die Variante `einheit` exakt (`_unit_and_topics_reproduce_the_count`
erweitern); Paare ohne Stelle zählen 1.

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

**Variante im Kartenumschalter**, wenn die Kodierung die Regel trägt: ein Radio „nur ‚handelt von‘"
neben „Treffer absolut", „je Begriff" und „Abweichung" (Makro `switcher`, `data-value-<variante>` an
41 Flächen und Zellen, eine Legende). Geschätzt 3 bis 5 KB auf `index.html` (41 Werte je Fläche und
Tabellenzelle plus Legende; die beiden Umschalter von Punkt 46 kosten zusammen 110 KB, aber vor
allem über die sechs Parteikarten, eine Bezirksvariante nur einen Bruchteil); die Luft von rund 64 KB
reicht. Gemessen wird das erst in Stufe 3. Dazu die
Gewichtszeilen `ortsbezug` und `stelle` in der Tabelle „Was ändert die Gewichtung?" (zwei Zeilen,
unter 1 KB), mit „explorativ" bei `stelle`. Ohne bestätigte Regel nur die Zeile `stelle`.

**Unterseite `orte.html`** (unter 500 KB, Register von F2), wenn mehr gezeigt werden soll: je
Wahlbezirk der Anteil der Treffer nach Stelle (die Tabelle aus § 3.1), die Adressen je Bezirk als
Zahl, die 57 stadtweiten Begriffe mit ihrem Anteil vorn. Keine Adressen, keine Textstellen.

**Validierung auf der Seite**: „geprüft von zwei KI-Kodierern an 200 Paaren, nicht von Menschen",
F1 mit Intervall, α; die Verortbarkeit der Hausnummern mit Intervall und Quelle (GebRef NRW,
dl-de/zero-2.0).

**Tabellen im Register**: `dokumente_wahlbezirke_stelle` als Download (Parquet; als CSV rund 3 MB
geschätzt, darum Parquet), mit Spaltenbeschreibung in `schema.json`. Die Spannen und die Adressen
nicht.

## 8. Vorab festgelegte Hypothesen

Keine Analyse mit Hypothese: Vorhaben 16 ist eine Vorverarbeitung. Festgelegt vor der Kodierung sind
die Regel, die Nebenregeln, die Gewichte nach Stelle, das Hauptmaß und die Nebenmaße (§ 3.2, § 4.2,
Codebuch `[mass]`). Die Sensitivität in § 3.3 ist explorativ: fünf Varianten × zwei Spalten von
Tabelle 5 sind zehn weitere Tests derselben Frage.

## 9. Risiken und offene Fragen

| Nr. | Frage | warum sie zählt | Annahme ohne Antwort |
|---|---|---|---|
| 9.1 | Ist „handelt von" weit gemeint (auch ein Punkt einer Liste von Maßnahmen) oder eng (der Ort ist Hauptgegenstand)? | Entscheidet, ob die Regel das Kriterium erreichen kann: weit trifft den Recall, eng machte die Kodierung zum Spiegel der Regel | weit, wie im Codebuch; eine Maßnahme an einem Ort ist Aufmerksamkeit für ihn |
| 9.2 | F1 der Klasse „handelt von" ist bei hoher Prävalenz schwach: die triviale Regel „alles handelt von" käme geschätzt auf 0,90. Soll das Kriterium zusätzlich verlangen, dass die Regel die triviale schlägt (κ > 0 mit Intervall, oder F1 der Gegenklasse ≥ 0,5)? | Sonst besteht eine Regel, die nichts trennt | Kriterium unverändert; das Skript berichtet die triviale Regel und κ mit Intervall daneben, und § 5 wertet eine Regel nur als bestanden, wenn zusätzlich das κ-Intervall über 0 liegt |
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

## 10. Änderungen durch die Synergie (füllt der Supervisor)
