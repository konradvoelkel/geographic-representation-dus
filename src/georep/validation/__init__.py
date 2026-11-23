"""Validierung mit zwei KI-Kodierern (Fundament F4, docs/validierung.md).

Konrad kodiert nicht selbst (plan-vorverarbeitung-2026-11.md, § 2.6): jede Stichprobe kodieren
zwei unabhängige Kodier-Agenten nach einem Codebuch, ein Schlicht-Agent entscheidet nur ihre
Uneinigkeiten. Das Paket trägt den Ablauf von der Stichprobe bis zur Zahl:

- ``codebook``: das Codebuch je Vorhaben als TOML, geprüft von pydantic;
- ``sample``: die geschichtete Stichprobe mit festem Seed (``georep validate sample``);
- ``tasks``: der Kodierauftrag je Kodierer, lokal und nie im Repo (``georep validate tasks``);
- ``merge``: zwei Kodierungen, die Liste der Uneinigkeiten, nach der Schlichtung ``labels.csv``
  (``georep validate merge``);
- ``measures``: Übereinstimmung (κ, α) und Güte (Präzision, Recall, F1, nDCG@k), rein;
- ``score``: die Maße gegen die Labels und die Ausgabe eines Verfahrens (``georep validate score``).
"""

from __future__ import annotations

from georep.errors import GeorepError


class CodingError(GeorepError):
    """Ein Kodierschritt kann nicht weiter: Antworten fehlen, passen nicht oder würden überschrieben."""
