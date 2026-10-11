"""Profil eines echten Schritts: cProfile um ``run_step``, Datei für snakeviz, Tabelle für die Konsole.

Profiliert wird der Schritt aus ``build_steps``, erzwungen, kein Nachbau (docs/decisions.md,
Punkt 13). Die ``.prof``-Datei landet datiert unter ``docs/profiling/`` und ist gitignored, weil sie
rechnerspezifisch ist; die Zahlen, die bleiben sollen, stehen datiert in ``docs/profiling/README.md``.
cProfile sieht nur Python-Frames: Zeit in Polars oder pypdf erscheint beim aufrufenden Frame.
"""

from __future__ import annotations

import cProfile
import datetime as dt
import io
import pstats
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from georep.io import atomic_path
from georep.pipeline import Outcome, Step, run_step
from georep.settings import Settings

SortKey = Literal["cumulative", "tottime"]


@dataclass(frozen=True)
class ProfileResult:
    outcome: Outcome
    path: Path | None  # None: der Schritt lief nicht (Netzschritt ohne ``online``)
    table: str  # pstats-Tabelle; leer, wenn der Schritt nicht lief


def profile_step(
    step: Step,
    settings: Settings,
    out_dir: Path,
    *,
    online: bool = False,
    top: int = 25,
    sort: SortKey = "cumulative",
    today: dt.date | None = None,
) -> ProfileResult:
    """Führt ``step`` erzwungen unter cProfile aus und schreibt ``<out_dir>/<datum>-<schritt>.prof``.

    ``today`` ist die Testnaht für das Datum im Dateinamen.
    """
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        outcome = run_step(step, settings, force=True, online=online)
    finally:
        profiler.disable()
    if outcome.status != "ausgeführt":
        return ProfileResult(outcome, None, "")
    day = dt.date.today() if today is None else today
    target = out_dir / f"{day.isoformat()}-{step.name}.prof"
    with atomic_path(target) as tmp:
        profiler.dump_stats(tmp)
    buffer = io.StringIO()
    pstats.Stats(profiler, stream=buffer).strip_dirs().sort_stats(sort).print_stats(top)
    return ProfileResult(outcome, target, buffer.getvalue())
