# Arbeitsregeln für dieses Repo

Plan und Phasen: `DEVELOPMENT_PLAN.md`. Messlatte: `docs/baseline-2026-10-10.md`. Stand: `STATUS.md`
(im selben Commit nachziehen, wenn sich der Stand ändert). Maßstab für Stil und Vorgehen sind die
Kapitel Brownfield, Code-Qualität, Testing, Profiling und Design by Contract des eipy-Skripts.

## Befehle

```bash
uv sync                      # Umgebung aus uv.lock
uv run nox                   # lint, typecheck, deps, test
uv run pytest -m slow        # Kette über die volle Referenz, Vergleich mit der Arbeit
uv run georep bootstrap && uv run georep run && uv run georep status
uv run georep fetch opendata # der einzige schnelle Netzschritt; alles andere dauert Stunden
uv run ruff check . && uv run ruff format --check .
uv run mypy                  # strict für alles
```

Settings: `src/georep/defaults.toml` ist die Quelle; rechnerspezifisches (Pfade auf xtraspace) gehört in
`settings.local.toml`, nie in die Defaults. Neue Parameter bekommen dort einen Kommentar mit dem Warum.

Bei Konrad liegen Umgebung und Cache auf xtraspace: `UV_PROJECT_ENVIRONMENT` und `UV_CACHE_DIR`
setzen (siehe `FORK-NOTES.md`), sonst legt uv `.venv` im Repo an.

## Nie

- `georep fetch` ohne Not auf dem vollen Datensatz: Metadaten und 19108 PDFs dauern Stunden. `fetch opendata` ist der einzige schnelle Netzschritt.
- In `reference/` schreiben. `Layout.guard_writable` verweigert es; Tests arbeiten in `tmp_path` mit `Layout(tmp/data, tmp/cache, mini_root)`.
- `pre-commit run --all-files` über `reference/` oder `tests/fixtures/`.
- pandas, geopandas, osmnx: die nox-Session `deps` verbietet sie im Lockfile. Tabellen sind Polars, Dateien Parquet, Geometrie shapely und pyproj; alles ist typisiert und besteht `mypy --strict`.
- Netztests in CI. Der OParl-Server braucht 85 s pro Seite; Netztests tragen den Marker `network` und laufen nur von Hand. Netz in Unit-Tests kommt über das `Transport`-Protokoll aus `georep.http` und die Fake-Session in `tests/fakes.py` mit den aufgezeichneten Antworten in `tests/fixtures/http/`; OParl-JSON wird mit `georep.oparl` geparst, nie mit `.get()`-Ketten.
- Die Dateien unter `tests/fixtures/mini/expected/` neu erzeugen: sie sind der Golden Master aus dem Altcode (Tag `v0.2.0`), siehe `tests/fixtures/mini/README.md`.

## Commits

- Eine Refactoring-Sorte pro Commit. Formatierung und Modernisierung sind je ein eigener Commit und stehen in `.git-blame-ignore-revs`. Keine inhaltliche Änderung fährt mit.
- Betreff im Imperativ, rund 50 Zeichen, kein Punkt; der Body sagt, warum, mit Datum und Fehlertext, wenn es einen gab.
- Nach jedem Commit `uv run nox`. Wird der Golden Master rot, war es kein Refactoring: zurücknehmen und bewusst entscheiden.
- Verhaltensänderungen zuerst mit rotem Test, dann die Änderung, je ein Commit.
- Eine Eigenschaft, die für alle Eingaben gilt, wird ein hypothesis-Test in `tests/property/`, kein Beispieltest; wer den Matcher ersetzt, misst sich an `tests/property/oracle_matcher.py`. Snapshots (`syrupy`) nur für kleine, stabile Ausgaben und nie blind mit `--snapshot-update` erneuern.
- Phasen laufen auf `refactor/phase-<n>`. Am Phasenende: Push, grüne CI abwarten, Merge nach `main` (fast-forward), Tag `v0.<n+1>.0`, Push. So hat Konrad es am 2026-10-11 für Phase 0 angewiesen.
- Prüfschritte in Skripten nie hinter eine Pipe stellen (`uv run pytest | tail`): die Pipe frisst den Exit-Code, und am 2026-10-11 landeten so zwei rote Commits. Erst der Befehl allein, dann die Ausgabe ansehen.
