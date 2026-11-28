# Datenpaket moenchengladbach-politikfelder (Politikfelder, Mönchengladbach, Wahlperiode 2020 bis 2025, gepackt am 2026-11-28)

Ein Politikfeld nach dem **Comparative Agendas Project** (CAP) je Ratsdokument des Profils
`moenchengladbach`: eines der 21 Hauptthemen des CAP-Master-Codebuchs oder 99 („kein Politikfeld
erkennbar"), leer ohne Rohtext. Vorhaben 19, Weg 3b (`docs/plans/19-politikfelder.md`, § 5, § 6 und
§ 10). Erzeugt mit `georep --profile moenchengladbach pack --policy-areas --from politikfelder.parquet
snapshots/moenchengladbach-politikfelder`; `[policy_areas].package` des Profils zeigt hierher, `bootstrap` kopiert die Datei
nach `raw/politikfelder_paket.parquet`, und der Schritt `policy_areas` prüft sie gegen den Korpus.
Der Ordner wird **nur gelesen** (`Layout.guard_writable`).

## Lizenz

Anders als der Rest des Repositorys und der Seite (CC0 und GPL) steht diese Datei unter
**CC BY-NC-SA 4.0** (https://creativecommons.org/licenses/by-nc-sa/4.0/): die Codes sind die des CAP, und der Klassifikator ist auf
den menschlich kodierten Daten des German Policy Agendas Project trainiert (Frage 37, Konrad,
2026-11-26: „unter NC-SA zeigen"). Zitat: Comparative Agendas Project, www.comparativeagendas.net; German Policy Agendas Project: Christian Breunig, Benjamin Guinaudeau und Tinette Schnatterer (2021), Policy agendas in Germany – database and descriptive insights, The Journal of Legislative Studies, doi 10.1080/13572334.2021.2010395.

## Modell

- Klassifikator `xlm-roberta-large` (FacebookAI, Revision `c23d21b0`, MIT-Lizenz), feinjustiert auf
  den deutschen CAP-Daten (Anfragentitel des Bundestags 1976–2005, Sätze aus Wahlprogrammen) und auf
  Silberlabels des lokalen Sprachmodells `qwen3.6:27b` für 4 200 Ratsdokumente der Hauptperiode
  (`docs/plans/19-politikfelder-training.py`, Variante 3b).
- Gewichte `training-3b/beste/model.safetensors`, SHA-256 `80ca2a823bd191c26f6f8c4be0f425ed90c1507c657e78468391ea57f9cab309`; die Gewichte
  (2,24 GB) liegen **nicht** im Repo. Jede Zeile trägt die Kennung `xlm-roberta-large@80ca2a82`.
- Eingabe: Titel und die ersten 1 500 Zeichen des Rohtexts (Fundament F1),
  Leerraum zusammengezogen (`georep policy-areas export`), im Modell auf 256 Token gekürzt;
  `abgeschnitten` sagt, ob der Klassifikator weniger als den ganzen Text sah.
- Die Wahrscheinlichkeit (Softmax des gewählten Themas) steht auf 3 Stellen gerundet da.

## Güte

Geprüft nur am Datensatz der Stichprobe (Profil `duesseldorf`, `validierung/19-politikfelder/`): von
zwei KI-Kodierern desselben Modells an 300 Dokumenten, nicht von Menschen (`guete.json`), Makro-F1
0,704 (Bootstrap 0,620–0,807), Genauigkeit 83,7 %; an 200 von Menschen kodierten Bundestagsanfragen
Makro-F1 0,688. Für dieses Profil ist die Datei nicht geprüft (Fragen 46 und 9.10).

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `processed/politikfelder.parquet` | 10 584 | `8c125ea54c624455cad108cac9b3e809272b539220a3d14b39c2362479ea27dd` |

Zusammen 10 584 Bytes. `tests/unit/test_data_packages.py` hält diese
Tabelle gegen die Dateien im Repo.

## Zahlen

| Größe | Wert |
|---|---|
| Dokumente | 2 895 |
| mit Politikfeld | 650 |
| ohne Rohtext | 2 245 |
| abgeschnitten | 514 |

## Spalten

| Spalte | Typ | Inhalt |
|---|---|---|
| `id` | str | OParl-URL des Dokuments, eine Zeile je Korpus-ID, sortiert |
| `politikfeld` | str | Hauptthema des CAP (1–10, 12–21, 23) oder 99; leer ohne Rohtext |
| `quelle` | str | `klassifikator`; leer ohne Rohtext |
| `modell` | str | `xlm-roberta-large@80ca2a82`; leer ohne Rohtext |
| `prompt` | str | leer (kein Sprachmodell) |
| `wahrscheinlichkeit` | float | Softmax des gewählten Themas, 0 bis 1; leer ohne Rohtext |
| `abgeschnitten` | bool | Rohtext über 1 500 Zeichen oder Eingabe über 256 Token; leer ohne Rohtext |
