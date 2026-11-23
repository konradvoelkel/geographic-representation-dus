# Paket Rohtexte Düsseldorf (Hauptperiode, gelesen mit pypdf 7.1.0 am 2026-11-23)

Der **Rohtext der Ratsdokumente** der Wahlperiode 2020 bis 2025: derselbe Extraktor wie im
Textpaket daneben (`snapshots/duesseldorf-texte`, pypdf 7.1.0), aber ungeglättet — Groß- und
Kleinschreibung, Zeilenumbrüche, der Vorlagenkopf vor „betrifft", und zwischen zwei Seiten ein
`\f`; die Spalte `form_feeds` nennt die Stellen, an denen eine Seite selbst ein `\f` trug. Nur der
Rohtextstore, nichts sonst (Fundament F1, `docs/plan-vorverarbeitung-2026-11.md`,
§ 7; `docs/decisions.md`, Eintrag „Der Rohtext bekommt einen zweiten Store").

Das Paket gibt es, weil GitHub Pages keine PDFs hat: ohne Paket hätte eine Kette dort keinen
Rohtext, und jedes spätere Vorhaben, das Abschnitte, Beträge, Kopfdaten oder Seiten liest, fehlte
auf der veröffentlichten Seite. Konrad hat Rohtextpakete im Repo am 2026-11-23 freigegeben
(`docs/plan-vorverarbeitung-2026-11.md`, § 10, Frage 6). Keine Zahl der Seite rechnet mit ihm, und
die Seite zeigt keinen Rohtext.

Erzeugt mit

```bash
georep bootstrap && georep run          # die 19 092 PDFs lokal unter cache_root/duesseldorf/pdf/
georep pack --raw-texts snapshots/duesseldorf-rohtexte
```

`profiles/duesseldorf.toml` nennt die Datei als `[bootstrap].raw_texts`. `bootstrap` legt sie als
Rohtextstore an (`cache/duesseldorf/text/rohtexte.parquet`), **wenn jeder ihrer Namen eine
Hauptdatei der Paper ist** (`georep.bootstrap.overlay_raw_texts`); die Periodenprofile nehmen den
Schlüssel zurück. Liegen die PDFs lokal, liest der Schritt `raw_texts` nur, was sich geändert hat
(PDF-Hash oder Extraktor). Der Ordner wird **nur gelesen**; die pre-commit-Hooks lassen
`snapshots/` aus, und `.gitattributes` hält die Bytes unverändert.

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `cache/text/rohtexte.parquet` | 14 183 802 | `56b8b79c95448a85af5086a7dcb3e468a4edd4716af60aed5d31218162671c8c` |

Zusammen 14 183 802 Bytes, Schema-Version 2, mit zstd auf Stufe 19 geschrieben (`georep pack
--raw-texts` schreibt den Store neu, statt ihn zu kopieren: 16,8 % kleiner als die Vorgabe von
Polars). `tests/unit/test_data_packages.py` hält diese Tabelle gegen die Datei im Repo
und, als `slow`-Test, jeden Rohtext gegen das Textpaket (unten, „Die Eigenschaft").

## Zahlen des Laufs

| Größe | Wert |
|---|---|
| Paper der Arbeit | 19 108, davon 16 ohne Hauptdatei |
| Hauptdateien | 19 092 |
| Rohtexte im Paket | **19 091**, einer je lesbarer Hauptdatei |
| Hauptdateien ohne Rohtext | 1 (`00403713.pdf`, siehe unten) |
| Seiten | 39 965 |
| Zeichen zusammen | 55 402 931 (das Textpaket: 51 152 796, ohne Kopf, Zeilenumbrüche und Seitenwechsel) |
| ohne Textschicht | 59 Rohtexte bestehen nur aus Seitenwechseln oder sind leer, dieselben 59 wie im Textpaket |
| mit Formfeeds im Seitentext | 1 (`00532917.pdf`, 41 Stellen in `form_feeds`) |
| Extraktor | `pypdf-7.1.0+roh` |
| Extraktion | 827,8 s für 19 092 PDFs (Schema-Version 2, 2026-11-23 abends, `nice -n 10`); der erste Lauf in Version 1 brauchte unter Fremdlast 1 178,1 s |

## Die Eigenschaft

Jeder Rohtext, geplättet (`\f` zu `\n`, die Formfeeds der Seiten aus `form_feeds` zurück, dann
kleingeschrieben und ohne Zeilenumbrüche, dann ab dem ersten „betrifft";
`georep.prep.raw_texts.flatten`), ist **genau der Text des Textpakets**. Über die
ganze Hauptperiode gilt das für **alle 19 091 Rohtexte**, ohne Ausnahme. Ein Fall braucht die
Spalte `form_feeds`: in `00532917.pdf` liefert eine defekte Schriftkodierung in einer Seite
Steuerzeichen statt Buchstaben, darunter 41 `\f`. Im Rohtext stehen sie als Leerzeichen, damit
`\f` nur den Seitenwechsel bedeutet; `flatten` setzt sie an den Stellen aus `form_feeds` zurück.

## Herkunft und Lizenz

| Angabe | Wert |
|---|---|
| Quelle | die Hauptdateien der Ratsdokumente, Ratsinformationssystem der Landeshauptstadt Düsseldorf (OParl 1.1), Body `0015` |
| Endpunkt | `https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/downloadfiles/` |
| Betreiber | ITK Rheinland für die Landeshauptstadt Düsseldorf |
| Abrufdatum der PDFs | 2026-11-17/18 (200 davon am 2026-10-11) |
| Lizenz | auf den Seiten des Anbieters nicht angegeben (wie bei den übrigen Ratsdokumenten) |

## Was im Paket **nicht** liegt

- die PDFs (2,7 GB) und ihr `manifest.jsonl`,
- die Paper: sie kommen aus `reference/`, die geglätteten Texte aus `snapshots/duesseldorf-texte`,
- die Stamps (`*.stamp.json`) und alles Abgeleitete.

## Was am Lauf auffiel

- **Ein PDF hat keinen Rohtext**: `00403713.pdf` ist mit AES verschlüsselt, und pypdf braucht dafür
  `cryptography`, das nicht im Lock steht (`docs/decisions.md`, Punkt 68). Der Textstore führt dafür
  den Text der Arbeit; einen Rohtext der Arbeit gibt es nicht.
- **Ein Seitentext trägt selbst Formfeeds**: `00532917.pdf`, siehe „Die Eigenschaft".
