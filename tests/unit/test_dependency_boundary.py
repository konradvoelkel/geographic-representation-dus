"""scikit-learn ist erlaubt (Konrad, 2026-10-11), aber nur in ``analysis/topics.py`` (decisions.md, Option 06).

Der Import kostet rund 0,4 s; ``georep status`` und jeder Schritt außer ``topics`` sollen ihn nicht
zahlen. Eine Quelltextsuche über das Paket hält die Grenze, kein Laufzeittrick.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "georep"
ALLOWED = SRC / "analysis" / "topics.py"
IMPORT = re.compile(r"^\s*(?:from\s+sklearn\b|import\s+sklearn\b)", re.MULTILINE)


def test_sklearn_is_installed() -> None:
    assert importlib.util.find_spec("sklearn") is not None


def test_sklearn_is_imported_only_in_the_topics_module() -> None:
    importing = sorted(
        p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if IMPORT.search(p.read_text(encoding="utf-8"))
    )
    assert set(importing) <= {"analysis/topics.py"}, importing
