# Skripte

Werkzeuge neben dem Paket, kein Teil von `georep`. Pfade kommen als Argumente; nichts
Rechnerspezifisches steht in den Skripten. Die Shell-Skripte laufen ohne `set -e` (es greift in
dieser Umgebung nicht zuverlässig, `CLAUDE.md`) und prüfen jeden Exit-Code selbst.

| Skript | wozu |
|---|---|
| `ab_bau.sh` | alle Seiten wie `pages.yml` aus den Datenpaketen bauen, in eigener Datenwurzel |
| `ab_vergleich.py` | zwei solche Bauten vergleichen, Parquet als Frame, Zeitstempel herausgerechnet |
| `worktree_anlegen.sh` | Worktree für ein Vorhaben auf eigenem Branch, mit eigener `settings.local.toml` |

## A/B-Bau: `ab_bau.sh` und `ab_vergleich.py`

**Wozu.** Eine Abhängigkeit, die Zahlen der Seite rechnet (polars, numpy, scipy, scikit-learn,
shapely, pyproj), und eine Kernänderung, die keine Zahl bewegen soll, bekommen einen A/B-Bau aller
Seiten gegen den alten Stand, nicht nur die Tests (`CLAUDE.md`, „Commits"). Das Verfahren steht in
`docs/decisions.md`, Punkt 66: alle Seiten wie in `pages.yml`, einmal am alten und einmal am neuen
Stand, je in eigener Datenwurzel über `GEOREP_SETTINGS`. Zwei Bauten am selben Lock waren dort in
allen 606 Dateien gleich; das Rauschen ist null, jede Abweichung ist ein Befund. Die
Einträge ab Punkt 69 zitieren die beiden Skripte noch als `ab/ab_bau.sh` und `ab/ab_vergleich.py`
auf xtraspace; das sind die Vorgänger dieser Dateien, die Reihenfolge der Profile gilt seit `v0.27.0`.

**Vorgehen.**

1. Zwei Stände ohne eigene Datenwurzel bereitstellen, etwa
   `git worktree add --detach <klon-a> <alter-commit>` oder
   `mkdir <klon-a> && git archive <alter-commit> | tar -x -C <klon-a>`; ebenso B.
2. Je Stand ein eigenes, noch leeres Venv-Verzeichnis wählen. `uv run` richtet es beim ersten Aufruf
   nach dem Lock des Klons ein; mit einem geteilten Venv bauten beide Seiten am selben Lock.
3. Beide Seiten bauen, **mit denselben Umgebungsvariablen**. Die Einträge seit Punkt 77 nehmen
   `POLARS_MAX_THREADS=4 OMP_NUM_THREADS=2`; `UV_CACHE_DIR` zeigt, wo uv seinen Cache hat:

   ```bash
   export POLARS_MAX_THREADS=4 OMP_NUM_THREADS=2
   scripts/ab_bau.sh <ab>/x-a <klon-a> <venv-a> \
     --periode duesseldorf-2014 --periode duesseldorf-2025 \
     --vergleich duesseldorf-vergleich --stadt moenchengladbach || exit 1
   scripts/ab_bau.sh <ab>/x-b <klon-b> <venv-b> \
     --periode duesseldorf-2014 --periode duesseldorf-2025 \
     --vergleich duesseldorf-vergleich --stadt moenchengladbach || exit 1
   ```

   `scripts/ab_bau.sh` kommt aus dem Hauptklon; gebaut wird der Stand in `<klon-a>` beziehungsweise
   `<klon-b>`. Das Skript schreibt `<wurzel>/settings.toml`, `<wurzel>/bau.log` und die Datenwurzel
   `<wurzel>/data` samt Cache.
4. Vergleichen, mit dem Venv des Hauptklons (das Skript braucht nur Polars):

   ```bash
   uv run python -I scripts/ab_vergleich.py <ab>/x-a/data/site <ab>/x-b/data/site
   uv run python -I scripts/ab_vergleich.py <ab>/x-a/data <ab>/x-b/data
   ```

   Exit 0 heißt gleich, 1 heißt Abweichungen, je eine Zeile `nur in A: …`, `nur in B: …` oder
   `anders: …`. Im Vergleich der Datenwurzeln weicht jeder `.stamp.json` ab, weil er seine
   Schreibzeit trägt; zählen tun die übrigen Zeilen. Die Zahlen gehören in den Entscheidungseintrag,
   mit beiden Commits und den Umgebungsvariablen.

**Reihenfolge der Profile.** Sie ist die von `.github/workflows/pages.yml`, und der Aufruf oben
bildet sie nach: das Standardprofil (bootstrap, run); die Perioden je mit bootstrap und run, ihre
Seite als Unterordner `<profil>/` im Ordner der Stadtseite, weil der Abschnitt „Zwei Wahlperioden"
sie relativ verlinkt; das Vergleichsprofil nur mit run und **nach** den Perioden, weil `compare` und
`cycle_tests` deren Ausgaben lesen (Vorhaben 17); die zweite Stadt mit bootstrap und run; zuletzt
`georep publish --strict-budget`. Wer die Blöcke in `pages.yml` ändert, ändert den Aufruf hier mit.

## Worktree für ein Vorhaben: `worktree_anlegen.sh`

```bash
scripts/worktree_anlegen.sh <wurzel> feat/NN-name NN-name [<cache_root>]
```

Legt `<wurzel>/NN-name` auf dem neuen Branch `feat/NN-name` ab `main` an und schreibt dort eine
`settings.local.toml` mit `data_root = "<wurzel>/NN-name/data"` und, wenn angegeben, dem geteilten
`cache_root` (§ 6 von `docs/plan-vorverarbeitung-2026-11.md`). Venv, `uv sync`, bootstrap und run
macht der Agent danach selbst, in jedem Aufruf mit dem eigenen `UV_PROJECT_ENVIRONMENT`: ein
`uv run` mit dem Venv des Hauptklons richtet dieses auf den Worktree um.
