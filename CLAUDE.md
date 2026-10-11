# Arbeitsregeln für dieses Repo

Plan und Phasen: `DEVELOPMENT_PLAN.md`. Messlatte: `docs/baseline-2026-10-10.md`. Stand: `STATUS.md`
(im selben Commit nachziehen, wenn sich der Stand ändert). Maßstab für Stil und Vorgehen sind die
Kapitel Brownfield, Code-Qualität, Testing, Profiling und Design by Contract des eipy-Skripts.

## Befehle

```bash
uv sync                      # Umgebung aus uv.lock
uv run nox                   # lint, typecheck, baseline, test
uv run pytest -m slow        # Offline-Kette über das volle Referenzkorpus
uv run ruff check . && uv run ruff format --check .
uv run mypy                  # strict für tests/ (ab Phase 2 auch src/georep/)
```

Bei Konrad liegen Umgebung und Cache auf xtraspace: `UV_PROJECT_ENVIRONMENT` und `UV_CACHE_DIR`
setzen (siehe `FORK-NOTES.md`), sonst legt uv `.venv` im Repo an.

## Nie

- `uv run python run.py` oder `src.prep_papers` ohne PDFs unter `data/raw/oparl_paper_pdf/`: überschreibt den Korpus mit leeren Texten.
- In `data/` schreiben lassen. Tests führen den Altcode über `tests/legacy_runner.py` mit umgebogenen Pfaden aus.
- `pre-commit run --all-files` über `data/` oder `tests/fixtures/`.
- pandas in neuem Code. Neuer Code nutzt Polars und schreibt Parquet; er ist vollständig typisiert und besteht `mypy --strict`.
- Netztests in CI. Der OParl-Server braucht 85 s pro Seite; Netztests tragen den Marker `network` und laufen nur von Hand. Netz in Unit-Tests kommt über das `Transport`-Protokoll aus `georep.http` und die Fake-Session in `tests/unit/test_dataset_oparl.py`.

## Commits

- Eine Refactoring-Sorte pro Commit. Formatierung und Modernisierung sind je ein eigener Commit und stehen in `.git-blame-ignore-revs`. Keine inhaltliche Änderung fährt mit.
- Betreff im Imperativ, rund 50 Zeichen, kein Punkt; der Body sagt, warum, mit Datum und Fehlertext, wenn es einen gab.
- Nach jedem Commit `uv run nox`. Wird der Golden Master rot, war es kein Refactoring: zurücknehmen und bewusst entscheiden.
- Verhaltensänderungen zuerst mit rotem Test, dann die Änderung, je ein Commit.
- Phasen laufen auf `refactor/phase-<n>`. Am Phasenende: Push, grüne CI abwarten, Merge nach `main` (fast-forward), Tag `v0.<n+1>.0`, Push. So hat Konrad es am 2026-10-11 für Phase 0 angewiesen.
- Prüfschritte in Skripten nie hinter eine Pipe stellen (`uv run pytest | tail`): die Pipe frisst den Exit-Code, und am 2026-10-11 landeten so zwei rote Commits. Erst der Befehl allein, dann die Ausgabe ansehen.
