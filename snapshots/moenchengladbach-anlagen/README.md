# Paket Anlagen Mönchengladbach (Wahlperiode 2020 bis 2025, Netzlauf vom 2026-10-13)

Die **Anlagen je Drucksache** mit Name und Datum, für Vorhaben 14 „Vorgänge"
(`docs/plans/14-vorgaenge.md`): eine Drucksache nennt eine andere im Namen einer Anlage. Antworten
auf Anfragen gibt es hier nicht, denn der Datensatz hat keine Anfragen (Messdokument § 2); die
Anlagen tragen nur Kanten. Das Paket liegt neben `reference/moenchengladbach/` und nicht darin:
abgeleitete Auszüge kommen nur über `georep pack` nach `snapshots/` (Synergie 2026-11, Konflikt 11).

Erzeugt mit

```bash
georep --profile moenchengladbach pack --attachments snapshots/moenchengladbach-anlagen
```

aus den OParl-Seiten der Paper-Liste im HTTP-Cache (`<cache_root>/http.sqlite`, nur lesend; 41
Seiten von `…/bodies/0011/papers`). `profiles/moenchengladbach.toml` nennt die Datei als
`procedures.attachments`, `bootstrap` kopiert sie nach `raw/anlagen.parquet`. Der Ordner wird
**nur gelesen**.

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `raw/anlagen.parquet` | 63 909 | `ec4e8b2aa44e7c24641b9802506abbb67346b49204128bc5e43cb0fea29a2b5e` |

Zusammen 63 909 Bytes. `tests/unit/test_data_packages.py` hält diese Tabelle gegen die Datei im
Repo. Spalten wie im Düsseldorfer Paket (`snapshots/duesseldorf-anlagen/README.md`): `id`,
`abgerufen`, `anlagen` (Name und Datum je Anlage, in der Folge des Servers).

## Zahlen des Abrufs

| Größe | Wert |
|---|---|
| Drucksachen | 2 895 |
| davon mit Anlage | 1 929 |
| Anlagen | 4 710, mit 3 595 verschiedenen Namen |
| nicht im Cache | 0 |
| Abrufdatum | 2026-10-13 |

Gegengerechnet am 2026-11-23 mit dem Auszug des Messskripts aus demselben Cache: keine Abweichung.

## Herkunft und Lizenz

| Angabe | Wert |
|---|---|
| Quelle | Ratsinformationssystem der Stadt Mönchengladbach (OParl 1.1), Body `0011` |
| Endpunkt | `https://ris-oparl.itk-rheinland.de/Oparl/bodies/0011/papers` |
| Betreiber | ITK Rheinland |
| Abrufdatum | 2026-10-13 |
| Lizenz | auf den Seiten des Anbieters nicht angegeben (wie bei den übrigen Ratsdokumenten) |

Das Paket trägt keine Dateien und keine Texte, nur die Namen der Anlagen, wie das
Ratsinformationssystem sie öffentlich zeigt; ein Name nennt eine Person, ein Mitglied eines
Gremiums, deren Anfrage in einer Sitzung beantwortet wurde.
