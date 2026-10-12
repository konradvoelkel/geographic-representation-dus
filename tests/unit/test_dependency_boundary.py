"""scikit-learn ist erlaubt (Konrad, 2026-10-11), aber nur in zwei Modulen von ``analysis/``.

``analysis/topics.py`` (Option 06) rechnet das Themenmodell, ``analysis/committees.py`` (Punkt 45)
den passenden Ausschuss. Der Import kostet rund 0,4 s; ``georep status`` und jeder andere Schritt
sollen ihn nicht zahlen. Eine Quelltextsuche über das Paket hält die Grenze, kein Laufzeittrick.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "georep"
ALLOWED = {"analysis/topics.py", "analysis/committees.py"}
IMPORT = re.compile(r"^\s*(?:from\s+sklearn\b|import\s+sklearn\b)", re.MULTILINE)


def test_sklearn_is_installed() -> None:
    assert importlib.util.find_spec("sklearn") is not None


def test_sklearn_is_imported_only_in_the_two_model_modules() -> None:
    importing = sorted(
        p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if IMPORT.search(p.read_text(encoding="utf-8"))
    )
    assert set(importing) <= ALLOWED, importing
