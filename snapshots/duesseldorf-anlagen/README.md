# Paket Anlagen Düsseldorf (drei Wahlperioden, Netzläufe vom 2026-10-13 und 2026-10-14)

Die **Anlagen je Drucksache** mit Name und Datum, für Vorhaben 14 „Vorgänge"
(`docs/plans/14-vorgaenge.md`): eine Drucksache nennt eine andere im Namen einer Anlage („Anlage zu
RAT/111/2021"), und die Antwort der Verwaltung auf eine Anfrage kommt fast immer als Anlage an der
Anfrage selbst („Antwort der Verwaltung", Messdokument § 3.6). Weder der Korpus noch ein anderes
Paket trägt diese Angabe: `PaperRecord` behält von einem OParl-Paper nur die Hauptdatei, und der
Korpus der Hauptperiode kommt aus dem Altformat der Arbeit.

Erzeugt mit

```bash
georep --profile duesseldorf pack --attachments snapshots/duesseldorf-anlagen
```

aus den OParl-Seiten der Paper-Liste, die Konrads Netzläufe im HTTP-Cache hinterlassen haben
(`<cache_root>/http.sqlite`, nur lesend geöffnet; 469 Seiten von `…/bodies/0015/papers`). Gepackt
sind die Drucksachen aller drei Düsseldorfer Perioden: das Profil `duesseldorf` und seine
Nachbarperioden aus `[[procedures.related]]`. `profiles/duesseldorf.toml` nennt die Datei als
`procedures.attachments`, `bootstrap` kopiert sie nach `raw/anlagen.parquet`, und die Schritte
`references` und `procedures` lesen nur diese Kopie, je Profil für die eigenen Drucksachen. Der
Ordner wird **nur gelesen**; die pre-commit-Hooks lassen `snapshots/` aus.

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `raw/anlagen.parquet` | 303 455 | `88ca78c969f5f910098508506320365236a4a9ed6ed8795955ca6d0fc3b1b6dd` |

Zusammen 303 455 Bytes. `tests/unit/test_data_packages.py` hält diese Tabelle gegen die Datei im
Repo.

Drei Spalten, eine Zeile je Drucksache, sortiert nach `id`, zstd auf Stufe 19 wie das Rohtextpaket:
`id` (String, die OParl-URL der Drucksache), `abgerufen` (Date, der Tag, an dem die Seite mit ihrem
jüngsten Stand gespeichert wurde) und `anlagen` (List(Struct(`name` String, `datum` Date)), die
Anlagen in der Folge des Servers; `datum` ist das Datum der Datei, sonst der Tag ihrer Anlage).
Eine Drucksache mit leerer Liste hat keine Anlage; eine, die im Paket fehlt, kannte der Abruf
nicht. Steht eine Drucksache auf mehreren Seiten, gilt der Stand mit dem jüngsten `modified`.

## Zahlen des Abrufs

| Größe | Wert |
|---|---|
| Drucksachen | 45 418 (2014 bis 2020: 22 215, 2020 bis 2025: 19 108, seit 2025: 4 095) |
| davon mit Anlage | 25 440 (19 290, 5 176, 974) |
| Anlagen | 48 024, mit 15 423 verschiedenen Namen |
| nicht im Cache | 0 |
| Abrufdatum | 2026-10-13 (37 418 Drucksachen), 2026-10-14 (8 000) |
| Anlagen mit dem Datum 2019-07-03 | 26 542 (Umstellung des Ratsinformationssystems; kein Antwortdatum, `procedures.attachment_dates_invalid`) |

Gegengerechnet am 2026-11-23 mit dem Auszug, den das Messskript
(`docs/plans/14-vorgaenge-messung.py`) aus demselben Cache zieht: für jede der 45 418 Drucksachen
dieselben Namen, Daten und Abruftage, ohne Abweichung.

## Herkunft und Lizenz

| Angabe | Wert |
|---|---|
| Quelle | Ratsinformationssystem der Landeshauptstadt Düsseldorf (OParl 1.1), Body `0015` |
| Endpunkt | `https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers` |
| Betreiber | ITK Rheinland für die Landeshauptstadt Düsseldorf |
| Abrufdatum | 2026-10-13 und 2026-10-14 |
| Lizenz | auf den Seiten des Anbieters nicht angegeben (wie bei den übrigen Ratsdokumenten) |

Das Paket trägt keine Dateien und keine Texte, nur die Namen der Anlagen, wie das
Ratsinformationssystem sie öffentlich zeigt. Zwei Namen nennen eine Person, beide Mitglieder
eines Gremiums, deren Anfrage beantwortet wird.

## Was am Abruf auffiel

- **Das Datum einer Anlage ist erst ab Juli 2019 ein Antwortdatum.** 26 542 der 48 024 Anlagen
  tragen den 2019-07-03, den Tag der Umstellung; Drucksachen vor Juni 2019 haben bis auf eine nur
  Anlagen mit einem Datum aus 2019 (Messdokument § 3.6).
- **Der Stand ist der des Abrufs.** Eine Antwort, die nach dem 2026-10-14 als Anlage dazukam, fehlt;
  für die laufende Periode veraltet das Paket mit jedem Tag. Ein Netzschritt, der die Anlagen
  selbst behält, ist der Weg danach (Messdokument, Frage 9.1).
