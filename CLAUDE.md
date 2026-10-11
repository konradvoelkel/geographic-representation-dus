# Arbeitsregeln für dieses Repo

Plan und Phasen: `DEVELOPMENT_PLAN.md`. Messlatte: `docs/baseline-2026-10-10.md`. Stand: `STATUS.md`
(im selben Commit nachziehen, wenn sich der Stand ändert). Maßstab für Stil und Vorgehen sind die
Kapitel Brownfield, Code-Qualität, Testing, Profiling und Design by Contract des eipy-Skripts.

## Einstieg in eine neue Sitzung

1. `git switch refactor/phase-<n>` (der offene Branch steht in `STATUS.md` unter „Nächster Schritt"; existiert er
   noch nicht, von `main` abzweigen). `main` trägt den letzten Phasen-Tag.
2. Auf Konrads Rechner vor allem anderen, weil die Primärplatte voll ist:
   `export UV_PROJECT_ENVIRONMENT=/media/konrad/xtraspace/venvs/georep UV_CACHE_DIR=/media/konrad/xtraspace/uv-cache`;
   `settings.local.toml` (gitignored, vorhanden) zeigt `data_root` und `cache_root` auf `/media/konrad/xtraspace/georep/`.
3. `uv sync && uv run nox && uv run pytest -m slow`: alles grün ist der Ausgangspunkt, sonst zuerst das klären.
4. Lesen: `STATUS.md` (Stand, Bekanntes, nächster Schritt), dann im Plan den Abschnitt der Phase, dann § 2 (Leitplanken)
   und § 4a (Lehren aus bubatzblick). Die Lehren aus den bisherigen Phasen stehen unten unter „Commits" und „Arbeitsweise".
5. Push geht per SSH; in nicht-interaktiven Sitzungen hält der Keyring-Agent den Schlüssel:
   `SSH_AUTH_SOCK=/run/user/1000/gcr/ssh git push`. Das gh-Token hat keinen `workflow`-Scope.

## Befehle

```bash
uv sync                      # Umgebung aus uv.lock
uv run nox                   # lint, typecheck, deps, test
uv run pytest -m slow        # Kette über die volle Referenz, Vergleich mit der Arbeit
uv run georep bootstrap && uv run georep run && uv run georep status
uv run georep fetch opendata # der einzige schnelle Netzschritt; alles andere dauert Stunden
uv run ruff check . && uv run ruff format --check .
uv run mypy                  # strict für alles
uv run nox -s bench          # heiße Pfade gegen die gespeicherte Baseline; der erste Lauf legt sie nur an
uv run georep profile index  # echter Schritt unter cProfile; .prof nach docs/profiling/, Zahlen ins README dort
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

## Arbeitsweise, aus den Phasen 0 bis 4 gelernt

- `set -e` greift in der zsh dieser Umgebung nicht zuverlässig; jede Prüfung bekommt eine eigene Exit-Code-Abfrage (`cmd || exit 1`).
- Textersetzungen im Code auf den Wortlaut aufsetzen, den Ruff zuletzt formatiert hat (vorher `grep -n`), sonst scheitern Anker, und eine halb angewandte Änderung bleibt liegen. Nach `ruff format` ändern sich Umbrüche.
- `ruff format` muss auch `noxfile.py` und `run.py`-artige Dateien einschließen (`ruff format .`), nicht nur `src tests`.
- Ein Golden-Master-Vergleich über Labels oder Namen muss die Eindeutigkeit prüfen (Wikidata: „Itter" ist Stadtteil und Bach, ein Objekt kann zwei Koordinaten haben); über URL oder ID vergleichen.
- Wenn die Laufzeit einer Suite sich plötzlich vervielfacht, ist meist ein neuer I/O-Pfad schuld (19108 Dateien mit fsync kosteten 143 s); erst messen, dann die Struktur ändern.
- mutmut 3 forkt und blockiert mit Polars (`docs/mutation-2026-10-11.md`); Polars-Threads nicht nur für ein Werkzeug drosseln.
- `.gitignore` kennt keine Kommentare hinter dem Muster; git liest sie als Teil des Musters, und die Zeile ignoriert nichts (so lagen `/data/` und `mutants/` bis 2026-10-11 offen). Kommentare auf eigene Zeilen, danach `git check-ignore -v`.
- Ein Test darf nicht von der Laufzeit abhängen: ob ein Funktionsname in einer Top-N-Profiltabelle steht, wechselt unter xdist von Lauf zu Lauf (rot am 2026-10-11). Den äußersten Frame oder die Sortierzeile prüfen.
- pytest-benchmark: `--benchmark-compare-fail` ohne gespeicherten Lauf ist ein Bedienfehler (Exit 4); die nox-Session `bench` prüft `.benchmarks/` vorher. Die CPU-Taktfrequenz schwankt zwischen Läufen, darum ist die `machine_info`-Warnung gefiltert. Eine Schwelle erst nach gemessenem Rauschen setzen: 10 % im Minimum schlugen bei 1-ms-Polars-Stufen ohne Codeänderung an (12,7 %), 20 % liegen über allem Gemessenen.
- Messungen stehen datiert in `docs/profiling/README.md`, `.prof`-Dateien und `.benchmarks/` bleiben lokal. Ein Profil des echten Schritts (`georep profile`) vor jedem Nachbau; cProfile verdreifacht die Zeit reiner Python-Bibliotheken (pypdf), die Verteilung stimmt trotzdem.
- `georep fetch pdfs --limit N` schreibt `pdf_limit` in den Settings-Fingerprint des Stamps; `status` zeigt `pdfs` danach als „offen: Settings geändert". Das ist richtig, nicht kaputt.
