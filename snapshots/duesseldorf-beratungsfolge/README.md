# Paket Beratungsfolge Düsseldorf (Hauptperiode, Vollabruf vom 2026-10-14)

Die **zweite Quelle des Gremiums** je Ratsdokument der Wahlperiode 2020 bis 2025: welche Gremien
ein Dokument beraten haben, wie OParl es sagt (`consultation[].organization`). Nur diese eine
Angabe, nichts sonst.

Das Paket gibt es, weil der Korpus der Hauptperiode aus dem **Altformat der Arbeit** stammt
(`reference/interim/paper_with_text.json`, Januar 2026) und dieses Format die Beratungsfolge nicht
führt. Jede andere Periode trägt sie in ihrem eigenen `raw/papers.jsonl` und braucht das Paket
nicht: `snapshots/2014-2020` für 22 066 von 22 215 Dokumenten, `snapshots/2025` für 3 966 von
4 095, `reference/moenchengladbach` für alle 2 895.

Erzeugt mit

```bash
georep --profile duesseldorf --settings <data_root = …/data-vollabruf> \
    pack --consultations snapshots/duesseldorf-beratungsfolge
```

aus `raw/papers.jsonl` des Vollabrufs. `profiles/duesseldorf.toml` nennt die Datei als
`[bodies].consultations`, `bootstrap` kopiert sie nach `raw/`, und der Schritt `bodies` liest nur
diese Kopie. Der Ordner wird **nur gelesen**; die pre-commit-Hooks lassen `snapshots/` aus, und
`.gitattributes` hält die Bytes unverändert.

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `raw/beratungsfolge.parquet` | 90 455 | `ab1f206ec31a371193f6542b7c50e757ee2a237866a696082d01376e99e5dff9` |

Zusammen 90 455 Bytes. `tests/unit/test_data_packages.py` hält diese Tabelle gegen die Datei im
Repo.

**Parquet und nicht JSONL**, anders als `raw/papers.jsonl` der anderen Pakete: derselbe Inhalt
kostet als JSONL 4 467 207 Bytes, also fast fünfzigmal so viel (gemessen am 2026-10-14). Die drei
Spalten sind `id` (String, die OParl-URL des Dokuments und der Schlüssel in den Korpus),
`consultation_organizations` (List(String), die Organisations-URLs, sortiert und entdoppelt wie
`georep.oparl.OparlPaper` sie liest) und `modified` (String, der Zeitstempel des Servers). Sortiert
nach `id`, eine Zeile je Dokument, zstd wie jede Parquet-Datei dieses Programms.

## Zahlen des Abrufs

| Größe | Wert |
|---|---|
| Abruf | 2026-10-14, 01:40 bis 02:16 (2 142 s), 122 Seiten, 24 400 Paper gesehen |
| Dokumente im Zeitraum (14.09.2020 bis 13.09.2025) | 19 109 |
| davon mit `consultation_organizations` | **18 708 (97,9 %)** |
| davon mit genau einem Gremium | 17 047 (89,2 % aller Dokumente) |
| mit mehr als einem | 1 661; Maximum 27; zusammen 22 288 Paare |
| ohne Beratungsfolge | 401 (2,1 %) |
| verschiedene Organisationen | **36** |
| die fünf häufigsten | `gr/6` 2 881 (15,1 %), `gr/32` 1 606, `gr/40` 1 403, `gr/39` 1 342, `gr/33` 1 297 |
| `modified` gesetzt | 19 109 von 19 109; Spanne 30.12.2024 bis 25.09.2026 |
| `modified` im März 2026 | 16 155 (84,5 %); Migrationsdatum 30.12.2024: 1 200 (6,3 %) |
| `originatorPerson` / `originatorOrganization` / `underDirectionOf` | 0 / 0 / 0 |

Die Rechnung dazu steht in `docs/befunde-2026-10-14.md`, § 4, und läuft mit
`uv run python docs/befunde-2026-10-14-messung.py --vollabruf` nach.

## Herkunft und Lizenz

| Angabe | Wert |
|---|---|
| Quelle | Ratsinformationssystem der Landeshauptstadt Düsseldorf (OParl 1.1), Body `0015` |
| Endpunkt | `https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/papers` |
| Betreiber | ITK Rheinland für die Landeshauptstadt Düsseldorf |
| Abrufdatum | 2026-10-14 |
| Lizenz | auf den Seiten des Anbieters nicht angegeben (wie bei den übrigen Ratsdokumenten) |

Das Paket nennt **keine Personen**: eine Dokument-URL, Organisations-URLs und einen Zeitstempel.

## Was am Abruf auffiel

- **Ein Dokument mehr als die Referenz der Arbeit**: 19 109 gegen 19 108. Es ist `KUA/023/2026`,
  eine Vorlage mit dem Jahr 2026 in der Nummer und einem Datum im Jahr 2025; die Arbeit hatte sie
  nicht. Der Schritt `bodies` rechnet auf dem Korpus, also fällt sie dort heraus — der Korpus
  sagt, welche Dokumente es gibt, nicht das Paket.
- **401 Dokumente ohne Folge** bleiben ohne Gremium aus dieser Quelle. Die Drucksachennummer gibt
  ihnen trotzdem eines: in der Hauptperiode trifft ihr Muster jede Nummer.
- **Die Reihenfolge der Beratung ist nicht in den Daten.** `OparlPaper.consultation_organizations`
  liest die Liste sortiert und entdoppelt; welches Gremium zuerst beraten hat, lässt sich daraus
  nicht sagen. Darum entscheidet die Folge nur, wenn sie **genau ein** Gremium nennt
  (`docs/decisions.md`, Punkt 58).
- **Die Urheberfelder sind leer**, alle drei, in allen 19 109 Dokumenten. Die Urheberklassen der
  Seite kommen weiter aus Dokumentart, Titel und Textkopf (Option 04).
- **Der Stand ist der 2026-10-14.** `modified` liegt bei 84,5 % der Dokumente im März 2026: eine
  Systemmigration hat damals fast alles angefasst. Ein neuer Abruf kann andere Organisationen
  liefern; die Tabelle `[bodies.organizations]` im Profil ist darum datiert und mit
  `georep --profile duesseldorf learn-bodies` nachzurechnen.
