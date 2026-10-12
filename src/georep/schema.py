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

# Erhöhen, wenn sich Spalten oder Typen von ``themen.parquet`` ändern.
# 2: Punkt 45 hat die Spalte ``gremium`` hinzugefügt (gesätes Thema je Ausschuss).
TOPICS_SCHEMA_VERSION = 2

# Erhöhen, wenn sich Spalten oder Typen von ``papers_ausschuss.parquet`` ändern.
ASSIGNMENT_SCHEMA_VERSION = 1
