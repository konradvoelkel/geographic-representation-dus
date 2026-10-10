# Geographic Representation DUS

Wie sichtbar sind die 41 Kommunalwahlbezirke Düsseldorfs in den Dokumenten des Stadtrats, und hängt
das mit der Wahlbeteiligung zusammen? Für jeden Wahlbezirk wird ein Wörterbuch aus Straßennamen
(OpenStreetMap) und Orten (Wikidata, Wikipedia) gebaut, die Ratsdokumente der Wahlperiode 2020–2025
(OParl-Schnittstelle des Ratsinformationssystems) werden danach durchsucht, und die Trefferquote je
Bezirk wird mit der Wahlbeteiligung der Kommunalwahl 2025 in Beziehung gesetzt.

Ursprung: Bachelorarbeit von Lukas Bartzsch, Heinrich-Heine-Universität Düsseldorf, Januar 2026
(<https://github.com/lubar102/geographic-representation-dus>). Dieser Fork baut den Code schrittweise um;
Ziel und Phasen stehen in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md), der aktuelle Stand in [STATUS.md](STATUS.md).

## Loslegen

```bash
git clone git@github.com:konradvoelkel/geographic-representation-dus.git
cd geographic-representation-dus
uv sync                  # installiert Python 3.14 und alle Pakete aus uv.lock
uv run nox               # lint, typecheck, baseline, test (Sekunden)
uv run pytest -m slow    # Offline-Kette über das volle Referenzkorpus, etwa 5 s
```

Systemabhängigkeiten: keine. Die Geo-Bibliotheken bringen ihre Binärteile als Wheels mit.
Wer die Umgebung woanders ablegen will (volle Platte), setzt vor `uv sync` die Variablen
`UV_PROJECT_ENVIRONMENT` und `UV_CACHE_DIR`.

## Pipeline ausführen

Der Code der Arbeit liegt unverändert in `src/` und `run.py` und läuft mit `uv run python run.py`.
Das lädt alle PDFs neu und dauert Stunden; was davon offline geht und was man nicht ohne PDFs
starten darf, steht in [FORK-NOTES.md](FORK-NOTES.md). Die Ergebnisse der Arbeit lassen sich ohne
Netz und ohne Schreiben ins Repo reproduzieren: `uv run pytest -m slow`.

## Daten

`data/` ist der eingefrorene Datensatz der Arbeit: Rohdaten (Wahlergebnis, Stimmbezirke, Straßen,
Orte), die Metadaten und extrahierten Texte von 19108 Ratsdokumenten (die PDFs selbst nicht) und
die Ergebnistabellen. Die Tests lesen daraus und schreiben nie hinein. Ab Phase 2 heißt das
Verzeichnis `reference/`, und Läufe schreiben in ein konfigurierbares Datenverzeichnis.

## Entwicklung

- Prüfungen: `uv run nox` lokal und in CI (`.github/workflows/ci.yml`) rufen dieselben Sessions.
- Vor dem Commit: `uvx pre-commit install` einmalig; die Hooks formatieren und linten mit Ruff.
- Regeln für Commits und für Agenten: [CLAUDE.md](CLAUDE.md).
- Befund vor dem Umbau mit allen Messwerten: [docs/baseline-2026-10-10.md](docs/baseline-2026-10-10.md).

## Lizenz

CC0 1.0, wie das Original.
