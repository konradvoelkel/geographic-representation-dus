# Paket Beschlüsse Düsseldorf (drei Wahlperioden, Netzlauf vom 2026-11-23)

Die Tabelle **„Paper × Tagesordnungspunkt"** je Wahlperiode, für Vorhaben 26 „Beschlusslage und
Antragserfolg" (`docs/plans/26-beschluesse.md`, § 6 und § 10): je Beratung einer Drucksache jeder
Tagesordnungspunkt, der sie behandelt, mit Sitzung, Gremium und dem Eintrag, den die
Sitzungsleitung in OParl `result` gesetzt hat („einstimmig beschlossen", „vertagt" …). Daraus
rechnet der Schritt `council_results` den Beratungsverlauf und `outcomes` die Beschlusslage. GitHub
Pages hat kein Netz und damit nicht den Netzlauf von Fundament F6 (`raw/meetings.jsonl`,
`agenda_items.jsonl`, `consultations.jsonl`, zusammen rund 90 MB je Periode); von ihm braucht die
Beschlusslage nur diese Tabelle.

Erzeugt mit

```bash
georep --profile duesseldorf pack --outcomes snapshots/duesseldorf-beschluesse
georep --profile duesseldorf-2014 pack --outcomes snapshots/duesseldorf-beschluesse
georep --profile duesseldorf-2025 pack --outcomes snapshots/duesseldorf-beschluesse
```

aus dem Netzlauf je Profil und den Korpus-IDs seines Laufs (`interim/papers.parquet`). Jedes Profil
nennt seine Datei als `outcomes.package`; `bootstrap` kopiert sie nach
`raw/tagesordnungspunkte.parquet`, und `council_results` liest diese Kopie nur, wo kein Netzlauf in
`raw/` liegt. Aus denselben Dateien gerechnet geben beide Wege denselben Beratungsverlauf
(`tests/unit/test_outcomes_steps.py`). Der Ordner wird **nur gelesen**; die pre-commit-Hooks lassen
`snapshots/` aus.

## Inhalt mit Prüfsummen (SHA-256)

| Datei | Bytes | SHA-256 |
|---|---|---|
| `raw/tagesordnungspunkte-2014-2020.parquet` | 275 397 | `73d5379febab899e3e0a4db0fd70d008050f668f807233360e179d178da18e03` |
| `raw/tagesordnungspunkte-2025.parquet` | 54 644 | `c8873022fb538c47bea9aff96b451501157afe18fb6499a4259af94661989298` |
| `raw/tagesordnungspunkte-duesseldorf.parquet` | 301 903 | `e99a1f25de817ab3d9de46370fa04927eaeaa66867d9e44531d40c589125f629` |

Zusammen 631 944 Bytes. `tests/unit/test_data_packages.py` hält diese Tabelle gegen die Dateien im
Repo.

Neun Spalten (`analysis.outcomes.AGENDA_SCHEMA`, Schema-Version 1 in den Metadaten), sortiert nach
`id`, Sitzung (ohne Beginn zuerst), Folge, Punkt und Beratung, zstd auf Stufe 19 wie das
Rohtextpaket: `id` (die OParl-URL der Drucksache), `beratung`, `top` (null: eine Beratung, deren
Tagesordnungspunkt nicht in der Sitzungsliste der Periode steht; so zählt jede Beratung),
`organisationen` (Liste der Schlüssel `gr/NN` der Sitzung, sonst der Beratung; das Kürzel setzt erst
das Profil, damit eine neue Zeile in `[bodies.organizations]` kein neues Paket braucht), `rolle` (der
Beratung, etwa „Entscheidung" oder „-"), `sitzung` (Beginn in Ortszeit, ohne Zone), `nummer`,
`ordnung` und `result` (wörtlich; null = kein Eintrag). Welche Klasse ein Eintrag trägt, sagt
`[outcomes.results]` im Stadtprofil; ein Wert, den es nicht kennt, bricht den Schritt ab.

## Zahlen des Laufs

| Größe | 2014 bis 2020 | 2020 bis 2025 | seit 2025 |
|---|---|---|---|
| Dokumente mit Beratung | 22 215 | 19 108 | 4 094 (von 4 095) |
| Zeilen | 28 820 | 25 715 | 5 010 |
| Tagesordnungspunkte | 28 092 | 25 439 | 4 979 |
| davon mit Eintrag | 26 032 | 23 580 | 4 792 |
| Beratungen ohne Punkt in der Sitzungsliste | 728 | 276 | 31 |
| Abrufdatum (Sitzungen; Beratungen) | 2026-11-24 00:59; 2026-11-24 00:42 | 2026-11-23 23:40; 23:57 | 2026-11-23 23:58; 2026-11-24 00:15 |

Die Beratungen sind je Body dieselbe Liste; für 2014 bis 2020 ist es der eigene Abruf, nicht die Kopie
der Hauptperiode, mit der das Messdokument rechnete (Frage 9.10). Die Anträge haben dieselben Klassen
wie dort (§ 3.4: Hauptperiode 5 099 Anträge, 4 810 mit Ergebnis; 2014 bis 2020 3 198 und 2 990; seit
2025 928 und 915).

## Herkunft und Lizenz

| Angabe | Wert |
|---|---|
| Quelle | Ratsinformationssystem der Landeshauptstadt Düsseldorf (OParl 1.1), Body `0015` |
| Endpunkte | `…/bodies/0015/meetings` (mit eingebetteter Tagesordnung), `…/bodies/0015/consultations` |
| Betreiber | ITK Rheinland für die Landeshauptstadt Düsseldorf |
| Abrufdatum | 2026-11-23 und 2026-11-24 (Netzlauf nach `docs/runbook-sitzungen.md`, § 9) |
| Lizenz | auf den Seiten des Anbieters nicht angegeben (wie bei den übrigen Ratsdokumenten) |

Das Paket trägt **keine Namen von Personen**: nur IDs, Schlüssel der Organisationen, die Rolle der
Beratung, Beginn, Nummer und Folge des Punkts und den Eintrag aus einem festen Wortschatz von 21
Werten. Die Bezeichnung eines Tagesordnungspunkts (der Titel der Drucksache, in dem ein Name stehen
kann) und die Anlagen der Sitzungen sind nicht darin. `persons.jsonl` und `memberships.jsonl` liest
dieses Vorhaben nicht.

## Was am Lauf auffiel

- **Ein Tagesordnungspunkt ohne Eintrag ist kein Ergebnis.** In der Haushaltssitzung des Rates am
  2021-02-05 trägt kein Haushaltsantrag einen Eintrag (155 Anträge der Hauptperiode); das Ergebnis
  steht nur in der Niederschrift (Messdokument § 3.3).
- **Der Eintrag ist der der Sitzungsleitung.** In der Bezirksvertretung 9 tragen 2014 und 2015 alle
  Anträge „zur Kenntnis genommen"; der Schritt `outcomes` markiert solche Gremium-Jahre
  (`eintrag_tragfaehig`, Messdokument § 5).
- **Der Stand ist der des Abrufs.** Ein Ergebnis, das nach dem 2026-11-24 eingetragen wurde, fehlt;
  für die laufende Periode veraltet das Paket mit jeder Sitzung. Ein neuer Netzlauf und ein neues
  `pack --outcomes --force` ziehen es nach.
