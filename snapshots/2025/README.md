# Schnappschuss laufende Wahlperiode seit 2025 (Erstabruf vom 2026-10-13)

Die Eingaben des Erstabrufs der laufenden Wahlperiode (ab 15.09.2025, offenes Ende), eingefroren,
damit GitHub Pages die Unterseite `2025/` und den Abschnitt „Laufende Wahlperiode" der Hauptseite
**ohne Netz** baut. `profiles/duesseldorf-2025.toml` zeigt mit `reference_root` hierher;
`bootstrap` erkennt dieses Format und kopiert nur. Vorgehen: README, „Laufende Wahlperiode" und
`deploy/README.md`; Entscheidung: `docs/decisions.md`, Punkt 56 — dazu Konrads Antwort auf Frage
7.4 vom 2026-10-13 („kein Bucket, kaum Traffic und kleine Dateien"), die den Weg über R2
ausschließt. Frage 3.3 betrifft den Quartiersatlas unter `context/`, nicht diese Periode.

**Dieser Schnappschuss veraltet mit jedem Lauf des Monitors — das ist Absicht.** Die laufende
Periode wird fortgeschrieben (`deploy/bin/georep-monitor.sh` hinter einem systemd-Timer); der
Stand im Repo ist der des Erstabrufs und wird nur dann neu gepackt, wenn jemand ihn neu packt.
Wer die aktuelle Seite will, nimmt die des Monitors; Pages zeigt den Stand des Pakets, und die
Seite nennt ihr Abrufdatum selbst.

## Warum dieses Format und nicht das aus `deploy/README.md`

`deploy/` kennt ein zweites Ding, das auch „Schnappschuss" heißt: `out/2025/snapshots/<JJJJ-MM>/`
mit `SHA256SUMS`, monatlich vom Monitor geschrieben, dazu `out/2025/stand.json`. Das ist ein
**Ergebnis**: eine Kopie der Download-Dateien der fertigen Seite für die Besucher, mit
Aufbewahrung über `MONITOR_SNAPSHOT_KEEP`. Dieser Ordner hier ist eine **Eingabe**: er trägt
`raw/papers.jsonl`, den Textstore und die beiden Wahl-Eingaben, aus denen `georep run` die ganze
Kette rechnet.

Aus den veröffentlichten Tabellen ließe sich die Seite nicht bauen: `bootstrap` kennt sie nicht,
der Schritt `corpus` bräuchte Dokumente, und `dokumente.json` bräuchte die Texte. Darum hat dieser
Ordner genau die Form von `snapshots/2014-2020/` und von `reference/moenchengladbach/` — dieselbe
Codezeile liest alle drei (`seed_stores_from_native`) — und die Prüfsummen stehen wie bei
`context/` in diesem README, nicht in einer eigenen `SHA256SUMS`. Ein Eingabepaket im Repo, eine
Form; `stand.json` bleibt beim Betrieb, wo es entsteht.

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `external/Stimmbezirk_Wahlergebnis.csv` | 65 982 | `ac45b7ae5d2e60deef155dd50acbfe9df0f207d7c1b4daacd797d292e3b4fc33` |
| `external/Stimmbezirke_2025.geojson` | 7 927 291 | `358d8c5498489feec0d70f2833a1dd753ce89790bd9f3bbdc9780bfc141b69b6` |
| `raw/papers.jsonl` | 2 863 955 | `a010228dad59f6fcc166110b08130b58e4529f53fcf9a433c98f9803d71bac20` |
| `cache/text/texts.parquet` | 3 037 026 | `fd8370744ba757011379089ebf6bbf44ef4248d22680208b76105729697bea07` |

Zusammen 13 894 254 Bytes (13,25 MiB). `tests/unit/test_data_packages.py` hält diese Tabelle gegen
die Dateien im Repo.

Die beiden Dateien unter `external/` sind **byteidentisch** zu `reference/external/`: die laufende
Periode rechnet mit dem Ergebnis derselben Wahl (14.09.2025) auf demselben Zuschnitt wie die
Hauptperiode, darum überschreibt ihr Profil `[sources.opendata]` nicht. Sie liegen hier trotzdem
noch einmal, damit das Paket für sich steht (`tar` darüber genügt, `bootstrap` braucht keine
zweite Wurzel und keinen Symlink); git speichert dieselben Bytes nur einmal, weil ein Blob über
seinen Inhalt adressiert wird. Im Arbeitsbaum kosten sie 7,9 MiB.

Straßen und Orte fehlen mit Absicht: `period.dictionary = "base"` liest das Wörterbuch der
Hauptperiode (Stand November 2025), damit sich nur die Dokumente unterscheiden (Frage 7.8).
Deshalb will dieses Profil die Hauptperiode zuerst gebootstrappt haben.

## Zahlen des Erstabrufs (2026-10-13)

| Größe | Wert |
|---|---|
| Ratsdokumente ab 15.09.2025 (letztes Datum 13.10.2026) | 4 095 |
| davon mit Hauptdatei (`mainFile`) | 4 088 |
| abgerufene PDFs | 4 088, keiner fehlgeschlagen |
| Texte im Store | 4 088, davon 4 075 mit Inhalt |
| Zeichen im Store | 9 961 880 |
| Treffer über alle 41 Wahlbezirke | 5 448 |
| Monate in der Monatsreihe | 14 |
| Gremium aus der Drucksachennummer | 4 040 von 4 095 erkannt, 55 unbekannt (1,3 %) |
| Dokumentarten | 39, häufigste `Beschlussvorlage` (808), `Anfrage` (585), `Antrag` (580) |

Der Abruf lief in einer Seite OParl mit `modified_since` und `stop_when_older`; die Zahlen sind
die Grundlage, auf die der Monitor fortschreibt (`deploy/README.md`, „Erstabruf").

## Herkunft und Lizenz

| Datei | Quelle, abgerufen am 2026-10-13 | Lizenz |
|---|---|---|
| `external/Stimmbezirk_Wahlergebnis.csv` (Kommunalwahl 14.09.2025) | Open-Data-Portal der Landeshauptstadt Düsseldorf | Datenlizenz Deutschland Namensnennung 2.0 |
| `external/Stimmbezirke_2025.geojson` (306 Flächen, EPSG:4647) | ebenda | Datenlizenz Deutschland – Zero – Version 2.0 |
| `raw/papers.jsonl` | Ratsinformationssystem Düsseldorf über OParl 1.1, `ris-oparl.itk-rheinland.de`, Body 0015 | kein Lizenzhinweis am Endpunkt |
| `cache/text/texts.parquet` | aus den 4 088 PDFs desselben Endpunkts mit pypdf 6.20.0 extrahiert | wie die Dokumente |

Namensnennung nach Lizenz: Landeshauptstadt Düsseldorf, Amt für Statistik und Wahlen
(Open-Data-Portal), dl-de/by-2-0 bzw. dl-de/zero-2-0.

## Was im Paket **nicht** liegt

- die PDFs (585 MB) und ihr `manifest.jsonl`; sie sind urheberrechtlich nicht geklärt und bleiben
  im Cache des Rechners, der sie geholt hat (Frage 7.3),
- die Stamps (`*.stamp.json`): der Monitor entscheidet an seinen eigenen, was zu laufen hat,
- der HTTP-Cache (`http.sqlite`),
- alles Abgeleitete (`interim/`, `processed/`, `site/`).

## Wie der Monitor damit umgeht

`bootstrap` füllt die Stores nur, wenn sie fehlen (`force` überschreibt). Auf einem Rechner, der
die Periode schon fortschreibt, bleibt der eigene Stand also stehen; auf einem frischen Rechner —
dem Runner von GitHub Pages, einem neuen VPS — beginnt der Lauf mit diesem Paket, statt 4 088 PDFs
noch einmal zu holen (`deploy/README.md`, „Umzug von kookaburra auf den VPS"). Ein
`georep --profile duesseldorf-2025 bootstrap --force` würde den laufenden Stand auf den des Pakets
zurücksetzen: der eine Befehl, den man hier nicht aus Gewohnheit tippt.
