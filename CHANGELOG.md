# Changelog

Eine Zeile pro Änderung aus Sicht eines Nutzers, neueste oben. Versionen sind Git-Tags.

## 0.3.0 (2026-10-11), Phase 2

- Neue Kommandozeile `georep`: `bootstrap`, `run`, `steps`, `status`, `export`, `regress`; Schritte werden
  übersprungen, wenn Eingaben, Settings, Code und Schema unverändert sind, und sagen sonst, warum sie laufen.
- Konfiguration in TOML: `defaults.toml` im Paket mit Begründungen, `settings.toml` und `settings.local.toml`
  im Arbeitsverzeichnis, Umgebungsvariablen `GEOREP_*`. Daten und Cache liegen, wo man sie hinlegt.
- `data/` heißt `reference/` und wird nur gelesen; Läufe schreiben nach `data_root`.
- Die Offline-Kette rechnet in Polars und schreibt Parquet; die Ergebnisse sind identisch mit denen der Arbeit.
- OParl-Antworten werden gegen ein typisiertes Modell geprüft; eine echte Antwort liegt als Fixture bei.
- Notebook nutzt `georep.analysis.regression`; pandas und scikit-learn sind keine direkten Abhängigkeiten mehr.

## 0.2.0 (2026-10-11), Phase 1

- Kein Lauf zerstört mehr Daten: alle Schreibvorgänge atomar; Schritte verweigern leere Ergebnisse
  und fehlende Eingaben; `prep_papers` überschreibt den Korpus nicht mehr mit leeren oder weniger Texten.
- Netz: Timeout 180 s, Wiederholung mit Backoff, User-Agent. Der PDF-Download läuft bei Fehlern weiter
  und berichtet, wie viele Dateien geladen, übersprungen und fehlgeschlagen sind; Antworten ohne PDF-Kopf
  werden abgewiesen. Der Metadaten-Download speichert nach jeder Seite und bricht laut ab.
- Wahlergebnis-CSV wird byteweise gespeichert; Umlaute hängen nicht mehr von geratenem Encoding ab.
- Invertierter Index nach Begriff sortiert; zwei Läufe schreiben dieselben Dateien.
- Wikidata-Entität und Sprache kommen aus der Konfiguration; Log-Level über `GEOREP_LOG_LEVEL`
  (Standard INFO statt DEBUG).
- Neu: Paket `georep` (`io`, `http`, `errors`), 37 neue Tests.

## 0.1.0 (2026-10-11), Phase 0

- uv-Projekt auf Python 3.14 mit Lockfile; `requirements.txt` entfällt.
- Charakterisierungstests für die Offline-Kette und Tabelle 5; Mini-Fixture; vier PDF-Fixtures mit Herkunft.
- nox, pre-commit, GitHub Actions; Code mit Ruff modernisiert und formatiert, ohne Verhaltensänderung.
