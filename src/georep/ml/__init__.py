"""Lokale Modelle als Naht (Fundament F5): Einbettungen und Textgenerierung über einen ollama-Server.

``base`` hält die Protokolle ``Embedder`` und ``Generator``, die Optionen und die Kennung für den
Stamp; ``ollama`` das Backend über HTTP auf localhost; ``cache`` den inhaltsadressierten Cache unter
``cache_root/ml/``; ``batch`` den fortsetzbaren Stapellauf; ``commands`` die Befehle
``georep ml status`` und ``georep ml bench``. Ein Schritt mit Modell trägt ``models`` (die Kennung)
und läuft nur mit ``--models`` (docs/architecture.md, „Modelle"; die Gründe in docs/decisions.md).
Tests rufen nie ein Modell: ``tests/fakes.py`` hat Einbetter, Generator und einen Server als Tabelle.
"""
