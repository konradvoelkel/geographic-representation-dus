"""Schema-Versionen der Ausgaben, die ein Modell schreibt -- importfrei (Punkt 45, 2026-10-13).

Jede abgeleitete Datei trägt ihre Schema-Version in den Parquet-Metadaten **und** im Stamp ihres
Schritts; nur über den Stamp kann ``pipeline.stamp_mismatch`` je „Schema geändert" melden
(docs/architecture.md, „Pipeline"). ``build_steps`` braucht die Zahl darum beim Bauen des
Registers, also bei jedem ``georep status``.

Die Versionen der übrigen Schritte stehen im Modul, das die Datei schreibt
(``prep.bodies.BODIES_SCHEMA_VERSION``, ``prep.papers.CORPUS_SCHEMA_VERSION``). Die zwei hier
können das nicht: ``analysis.topics`` und ``analysis.committees`` importieren scikit-learn, und
``pipeline.py`` lädt sie bewusst erst im Schritt (rund 0,4 s Importzeit,
``tests/unit/test_dependency_boundary.py``). Eine Zahl soll diesen Import nicht auslösen, darum
liegt sie hier und wird von beiden Modellen importiert statt dort definiert.
"""

from __future__ import annotations

import hashlib
from importlib import resources
from importlib.resources.abc import Traversable

# Erhöhen, wenn sich Spalten oder Typen von ``themen.parquet`` ändern.
# 2: Punkt 45 hat die Spalte ``gremium`` hinzugefügt (gesätes Thema je Ausschuss).
TOPICS_SCHEMA_VERSION = 2

# Erhöhen, wenn sich Spalten oder Typen von ``papers_ausschuss.parquet`` ändern.
ASSIGNMENT_SCHEMA_VERSION = 1


def stop_words_digest(name: str, folder: Traversable | None = None) -> str:
    """Kurzer Hash der Paket-Stoppwortliste ``stopwords_<name>.txt``; leer, wenn es keine gibt.

    Der Zusatz im Stamp des Schritts ``topics`` (Punkt 53, Review-Befund 8 vom 2026-10-13). Die
    Liste prägt ``themen.parquet`` -- sie entscheidet, welche Wörter das Modell überhaupt sieht --,
    stand aber in keinem Eingabe-Hash und in keinem Settings-Fingerprint: dort steht nur ihr
    **Name** (``topics.stop_words = "de"``). Eine gestrichene Zeile in der Datei änderte das Modell
    und liess den Stamp gültig.

    Hier und nicht in ``analysis.topics``, aus demselben Grund wie die beiden Versionen oben:
    ``build_steps`` braucht die Zahl bei jedem ``georep status``, und ``analysis.topics`` zieht
    scikit-learn mit.
    """
    if not name:
        return ""
    if folder is None:
        folder = resources.files("georep.analysis")
    source = folder / f"stopwords_{name}.txt"
    if not source.is_file():
        return ""
    return hashlib.sha256(source.read_bytes()).hexdigest()[:16]
