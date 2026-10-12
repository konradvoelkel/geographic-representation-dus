# Arbeitsregeln für dieses Repo

Aufbau: `docs/architecture.md`. Gründe und verworfene Alternativen: `docs/decisions.md`. Stand und Bekanntes:
`STATUS.md` (im selben Commit nachziehen, wenn sich der Stand ändert). Offenes Vorhaben: der Ausbau in acht
Optionen, `docs/plan-ausbau-2026-10.md` (Supervisor und Unteragenten). Die Berichtsseite ist gebaut und über
GitHub Pages veröffentlicht (`docs/plan-report-2026-10.md`, abgeschlossen am 2026-10-11). Der Umbau 2026-10 ist
abgeschlossen; sein
Plan liegt historisch unter `docs/development-plan-2026-10.md`, der Befund davor in `docs/baseline-2026-10-10.md`.
Maßstab für Stil und Vorgehen sind die Kapitel Brownfield, Code-Qualität, Testing, Profiling und Design by
Contract des eipy-Skripts.

## Einstieg in eine neue Sitzung

1. `git switch main && git pull`. Gearbeitet wird direkt auf `main`, keine Branches (Konrad, 2026-10-11);
   `main` trägt den letzten Tag (`v0.10.0` am 2026-10-11). Ausnahme, von Konrad am 2026-10-11 gewünscht: die acht
   Ausbau-Optionen aus `docs/plan-ausbau-2026-10.md` laufen auf Branches `feat/NN-name` in eigenen Worktrees auf
   xtraspace (dort fehlt `settings.local.toml`, siehe § 4 des Plans); `main` bleibt grün.
2. Auf Konrads Rechner vor allem anderen, weil die Primärplatte voll ist:
   `export UV_PROJECT_ENVIRONMENT=/media/konrad/xtraspace/venvs/georep UV_CACHE_DIR=/media/konrad/xtraspace/uv-cache`;
   `settings.local.toml` (gitignored, vorhanden) zeigt `data_root` und `cache_root` auf `/media/konrad/xtraspace/georep/`.
3. `uv sync && uv run nox && uv run pytest -m slow`: alles grün ist der Ausgangspunkt, sonst zuerst das klären.
4. Lesen: `STATUS.md` (Stand, Bekanntes), `docs/architecture.md` für den betroffenen Teil, `docs/decisions.md`,
   bevor eine Entscheidung dort umgestoßen wird. Für die Berichtsseite: `docs/plan-report-2026-10.md`, § 8 nennt
   die Reihenfolge. Die Lehren aus dem Umbau stehen unten unter „Commits" und „Arbeitsweise".
5. Push geht per SSH; in nicht-interaktiven Sitzungen hält der Keyring-Agent den Schlüssel:
   `SSH_AUTH_SOCK=/run/user/1000/gcr/ssh git push`. Das gh-Token hat keinen `workflow`-Scope.

## Befehle

```bash
uv sync                      # Umgebung aus uv.lock
uv run nox                   # lint, typecheck, deps, test
uv run pytest -m slow        # Kette über die volle Referenz, Vergleich mit der Arbeit
uv run georep bootstrap && uv run georep run && uv run georep status   # run endet mit der Berichtsseite data/site/index.html
uv run georep fetch opendata # der einzige schnelle Netzschritt; alles andere dauert Stunden
uv run ruff check . && uv run ruff format --check .
uv run mypy                  # strict für alles
uv run nox -s bench          # heiße Pfade gegen die gespeicherte Baseline; der erste Lauf legt sie nur an
uv run georep profile index  # echter Schritt unter cProfile; .prof nach docs/profiling/, Zahlen ins README dort
uv run nox -s verify         # crosshair über die reinen Funktionen mit Verträgen, rund drei Minuten
uv run nox -s mutate         # pytest-gremlins über search/ und analysis/, einmal pro Phase, kein Gate
```

Settings: `src/georep/defaults.toml` ist die Quelle; rechnerspezifisches (Pfade auf xtraspace) gehört in
`settings.local.toml`, nie in die Defaults. Neue Parameter bekommen dort einen Kommentar mit dem Warum.

Bei Konrad liegen Umgebung und Cache auf xtraspace: `UV_PROJECT_ENVIRONMENT` und `UV_CACHE_DIR`
setzen (siehe `FORK-NOTES.md`), sonst legt uv `.venv` im Repo an.

## Nie

- `georep fetch` ohne Not auf dem vollen Datensatz: Metadaten und 19108 PDFs dauern Stunden. `fetch opendata` ist der einzige schnelle Netzschritt.
- In `reference/` schreiben. `Layout.guard_writable` verweigert es; Tests arbeiten in `tmp_path` mit `Layout(tmp/data, tmp/cache, mini_root)`.
- In `context/` schreiben oder die Dateien formatieren: Portaldateien, unverändert gespeichert, mit SHA-256 im README. `Layout.guard_writable` verweigert das Schreiben, die pre-commit-Hooks lassen den Ordner aus.
- `pre-commit run --all-files` über `reference/` oder `tests/fixtures/`.
- pandas, geopandas, osmnx: die nox-Session `deps` verbietet sie im Lockfile. Tabellen sind Polars, Dateien Parquet, Geometrie shapely und pyproj; alles ist typisiert und besteht `mypy --strict`.
- Netztests in CI. Der OParl-Server braucht 85 s pro Seite; Netztests tragen den Marker `network` und laufen nur von Hand. Netz in Unit-Tests kommt über das `Transport`-Protokoll aus `georep.http` und die Fake-Session in `tests/fakes.py` mit den aufgezeichneten Antworten in `tests/fixtures/http/`; OParl-JSON wird mit `georep.oparl` geparst, nie mit `.get()`-Ketten.
- Die Dateien unter `tests/fixtures/mini/expected/` neu erzeugen: sie sind der Golden Master aus dem Altcode (Tag `v0.2.0`), siehe `tests/fixtures/mini/README.md`.
- `deal.pure` oder `deal.has()` auf rekursive Funktionen oder in heiße Schleifen: der Patcher ist nicht reentrant und patcht prozessweit. `deal.inv` auf Stores, deren Methoden je Dokument laufen.

## Commits

- Eine Refactoring-Sorte pro Commit. Formatierung und Modernisierung sind je ein eigener Commit und stehen in `.git-blame-ignore-revs`. Keine inhaltliche Änderung fährt mit.
- Betreff im Imperativ, rund 50 Zeichen, kein Punkt; der Body sagt, warum, mit Datum und Fehlertext, wenn es einen gab.
- Nach jedem Commit `uv run nox`. Wird der Golden Master rot, war es kein Refactoring: zurücknehmen und bewusst entscheiden.
- Verhaltensänderungen zuerst mit rotem Test, dann die Änderung, je ein Commit.
- Eine Eigenschaft, die für alle Eingaben gilt, wird ein hypothesis-Test in `tests/property/`, kein Beispieltest; wer den Matcher ersetzt, misst sich an `tests/property/oracle_matcher.py`. Snapshots (`syrupy`) nur für kleine, stabile Ausgaben und nie blind mit `--snapshot-update` erneuern.
- Direkt auf `main`: nach jedem Commit `uv run nox`, dann Push; CI über die Actions-REST-API prüfen (`gh run list` liefert für dieses Repo leer). Tag bei Versionssprung; Versionen stehen in `pyproject.toml`, `src/georep/__init__.py` und `uv.lock` (`uv lock`), jede mit einer Zeile im `CHANGELOG.md`. So hat Konrad es am 2026-10-11 angewiesen.
- Prüfschritte in Skripten nie hinter eine Pipe stellen (`uv run pytest | tail`): die Pipe frisst den Exit-Code, und am 2026-10-11 landeten so zwei rote Commits. Erst der Befehl allein, dann die Ausgabe ansehen.

## Arbeitsweise, gelernt im Umbau 2026-10

- `set -e` greift in der zsh dieser Umgebung nicht zuverlässig; jede Prüfung bekommt eine eigene Exit-Code-Abfrage (`cmd || exit 1`).
- Textersetzungen im Code auf den Wortlaut aufsetzen, den Ruff zuletzt formatiert hat (vorher `grep -n`), sonst scheitern Anker, und eine halb angewandte Änderung bleibt liegen. Nach `ruff format` ändern sich Umbrüche.
- `ruff format` muss auch `noxfile.py` und andere Python-Dateien außerhalb von `src` und `tests` einschließen (`ruff format .`).
- Ein Golden-Master-Vergleich über Labels oder Namen muss die Eindeutigkeit prüfen (Wikidata: „Itter" ist Stadtteil und Bach, ein Objekt kann zwei Koordinaten haben); über URL oder ID vergleichen.
- Wenn die Laufzeit einer Suite sich plötzlich vervielfacht, ist meist ein neuer I/O-Pfad schuld (19108 Dateien mit fsync kosteten 143 s); erst messen, dann die Struktur ändern.
- mutmut 3 forkt und blockiert mit Polars (`docs/mutation-2026-10-11.md`); Polars-Threads nicht nur für ein Werkzeug drosseln.
- `.gitignore` kennt keine Kommentare hinter dem Muster; git liest sie als Teil des Musters, und die Zeile ignoriert nichts (so lagen `/data/` und `mutants/` bis 2026-10-11 offen). Kommentare auf eigene Zeilen, danach `git check-ignore -v`.
- Ein Test darf nicht von der Laufzeit abhängen: ob ein Funktionsname in einer Top-N-Profiltabelle steht, wechselt unter xdist von Lauf zu Lauf (rot am 2026-10-11). Den äußersten Frame oder die Sortierzeile prüfen.
- pytest-benchmark: `--benchmark-compare-fail` ohne gespeicherten Lauf ist ein Bedienfehler (Exit 4); die nox-Session `bench` prüft `.benchmarks/` vorher. Die CPU-Taktfrequenz schwankt zwischen Läufen, darum ist die `machine_info`-Warnung gefiltert. Eine Schwelle erst nach gemessenem Rauschen setzen: 10 % im Minimum schlugen bei 1-ms-Polars-Stufen ohne Codeänderung an (12,7 %), 20 % liegen über allem Gemessenen.
- Messungen stehen datiert in `docs/profiling/README.md`, `.prof`-Dateien und `.benchmarks/` bleiben lokal. Ein Profil des echten Schritts (`georep profile`) vor jedem Nachbau; cProfile verdreifacht die Zeit reiner Python-Bibliotheken (pypdf), die Verteilung stimmt trotzdem.
- `georep fetch pdfs --limit N` schreibt `pdf_limit` in den Settings-Fingerprint des Stamps; `status` zeigt `pdfs` danach als „offen: Settings geändert". Das ist richtig, nicht kaputt.
- deal (Phase 6): `deal.raises` vergleicht exakte Typen, keine Unterklassen (`requests.RequestException` deckt `HTTPError` nicht ab); darum wandeln Fetcher Netzfehler in `NetworkError`. `deal.has()`/`deal.pure` patchen `socket.socket` und `sys.stdout` prozessweit und sind nicht reentrant: rekursive Funktionen bekommen `deal.safe`, sonst bleibt der Patch stehen (2026-10-11, `deep_merge`). Das mypy-Plugin `deal.mypy` modelliert `result` in `ensure` als positionalen Parameter; Validatoren mit optionalen Argumenten werden benannte Funktionen und stehen vor dem ganzen Decorator-Stapel, nie dazwischen. Prädikate für Verträge liegen in `georep.contracts`.
- `deal.cases` läuft ohne Beispiel-Datenbank: ein Gegenbeispiel kann im nächsten Lauf fehlen, hypothesis druckt den Reproduktions-Blob. `check_types=False`, weil typeguard nicht installiert ist. `nox -s verify` (crosshair) braucht rund drei Minuten; „Not confirmed" ist kein Befund.
- `except OSError, TimeoutExpired:` ohne Klammern ist seit Python 3.14 gültig (PEP 758), und `ruff format` schreibt
  es so; das System-`python3` ist 3.12 und meldet dafür einen Syntaxfehler. Prüfungen laufen nur über `uv run`
  (am 2026-10-12 hielt ein Agent die Form für kaputt und „reparierte" sie).
- Commit-Messages in der zsh nicht mit deutschen Anführungszeichen „…" schreiben: das schließende Zeichen ist ein ASCII-`"` und beendet den String (2026-10-11, nichts wurde ausgeführt).
