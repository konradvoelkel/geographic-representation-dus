# Paket Texte Düsseldorf (Hauptperiode, neu gelesen mit pypdf 7.1.0 am 2026-11-18)

Die **Texte der Ratsdokumente** der Wahlperiode 2020 bis 2025, aus den PDFs neu gelesen mit dem
Extraktor des Programms, pypdf 7.1.0. Nur der Textstore, nichts sonst (`docs/decisions.md`,
Punkt 68).

Das Paket gibt es, weil die Paper der Hauptperiode aus dem **Altformat der Arbeit** kommen
(`reference/interim/paper_with_text.json`, Januar 2026) und dieses Format die Texte so trägt, wie
die Arbeit sie gelesen hat. Konrad hat am 2026-11-18 entschieden, die Hauptperiode mit demselben
Extraktor zu lesen wie die drei anderen Datensätze (`snapshots/2014-2020`, `snapshots/2025`,
`reference/moenchengladbach`, seit Punkt 67). `reference/` bleibt dabei unverändert der Stand der
Arbeit; der Tag `bartzsch-exakt` ist der Anker für ihre Zahlen.

Erzeugt mit

```bash
georep fetch pdfs                       # 19 092 PDFs, 2026-11-17 22:40 bis 2026-11-18 04:34
georep bootstrap && georep run          # in einer eigenen Datenwurzel, die PDFs als Kopie daneben
georep pack --texts snapshots/duesseldorf-texte
```

`profiles/duesseldorf.toml` nennt die Datei als `[bootstrap].texts`. `bootstrap` füllt die Stores
aus der Referenz und legt danach diesen Store über den Textstore, **wenn er genau die Hauptdateien
ihrer Paper trägt** (`georep.bootstrap.overlay_texts`); sonst bleiben die Texte der Referenz. Die
Golden-Master-Tests gegen die Arbeit nehmen das Paket mit `as_in_the_thesis` zurück. Der Ordner
wird **nur gelesen**; die pre-commit-Hooks lassen `snapshots/` aus, und `.gitattributes` hält die
Bytes unverändert.

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `cache/text/texts.parquet` | 15 563 293 | `a68ea314a262052fa062a94eb61ddacde641aa4f751aca18f53391e7abb17a8f` |

Zusammen 15 563 293 Bytes. `tests/unit/test_data_packages.py` hält diese Tabelle gegen die Datei
im Repo und, als `slow`-Test, die Zahlen unten gegen den Store.

## Zahlen des Laufs

| Größe | Wert |
|---|---|
| Paper der Arbeit | 19 108, davon 16 ohne Hauptdatei |
| Texte im Paket | **19 092**, einer je Hauptdatei |
| davon aus pypdf 7.1.0 | 19 091 |
| davon der Text der Arbeit | 1 (`00403713.pdf`, siehe unten) |
| mit Inhalt | 19 033, wie in der Arbeit |
| ohne Inhalt | 59 PDFs ohne Textschicht; die Arbeit führte für sie keinen Text |
| zeichengleich mit der Arbeit | 11 002; verschieden 8 031 (42 %) |
| Zeichen zusammen | 51 152 796 (die Arbeit: 51 204 305) |
| Extraktion | 628,5 s für 19 092 PDFs |

Was die neuen Texte an den Zahlen der Seite ändern, steht in `docs/decisions.md`, Punkt 68.

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
- die Paper: sie kommen aus `reference/`,
- die Stamps (`*.stamp.json`) und alles Abgeleitete.

## Was am Lauf auffiel

- **Ein PDF ist mit AES verschlüsselt**: `00403713.pdf` (6,5 MB). pypdf braucht zum Entschlüsseln
  das Paket `cryptography`, das nicht im Lock steht, und meldet `CorruptPdfError: cryptography>=3.1
  is required for AES algorithm`. `extract_missing` behält dann den alten Text, hier den der Arbeit
  (187 472 Zeichen). Mit `cryptography` würde auch dieses PDF neu gelesen; ob es ins Lock kommt,
  ist offen (`STATUS.md`, „Bekannt").
- **Der Server fiel vor dem Abruf einen Tag lang aus**: am 2026-11-16 von 01:48 bis mindestens
  17:40 antwortete jede Adresse mit `503`. Der Abruf selbst lief ohne einen Fehlschlag.
