"""Wo die Dateien eines Vorhabens liegen: im Repo, was keinen Text trägt, lokal der Rest (F4).

Im Repo, unter ``validation.root/<vorhaben>/``: das Codebuch, die Stichprobe (nur Schlüssel), die
Labels, das README und die Güte. Lokal, unter ``validation.coding_root/<vorhaben>/``, je Kodierer
ein Ordner mit Auftrag (Ausschnitte aus Ratsdokumenten), Codebuch als Text und Antworten (mit
Begründungen, die Text zitieren dürfen). Ein Kodier-Agent bekommt genau seinen Ordner; den des
anderen und die Ausgabe des Verfahrens sieht er nicht (docs/validierung.md, § 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from georep.errors import SchemaError
from georep.settings import Settings
from georep.validation.codebook import CODEBOOK_FILE, PROJECT_NAME

Coder = Literal["A", "B"]
Role = Literal["A", "B", "schlichtung"]
CODERS: tuple[Coder, ...] = ("A", "B")
ADJUDICATION: Role = "schlichtung"


@dataclass(frozen=True)
class ValidationPaths:
    project: str
    folder: Path  # validation.root/<vorhaben>, im Repo
    coding: Path  # validation.coding_root/<vorhaben>, lokal

    @property
    def codebook(self) -> Path:
        return self.folder / CODEBOOK_FILE

    @property
    def sample(self) -> Path:
        return self.folder / "stichprobe.csv"

    @property
    def sample_meta(self) -> Path:
        return self.folder / "stichprobe.json"

    @property
    def labels(self) -> Path:
        return self.folder / "labels.csv"

    @property
    def readme(self) -> Path:
        return self.folder / "README.md"

    @property
    def quality(self) -> Path:
        return self.folder / "guete.json"

    def role(self, who: Role) -> Path:
        return self.coding / who

    def tasks(self, who: Role) -> Path:
        return self.role(who) / "auftrag.jsonl"

    def answers(self, who: Role) -> Path:
        return self.role(who) / "antworten.jsonl"

    def brief(self, who: Role) -> Path:
        return self.role(who) / "codebuch.md"


def validation_paths(settings: Settings, project: str) -> ValidationPaths:
    """Die Pfade eines Vorhabens; die lokalen dürfen nicht unter dem Ordner im Repo liegen."""
    if not PROJECT_NAME.fullmatch(project):
        raise SchemaError(f"Vorhaben {project!r}: ein Ordnername wie 11-struktur")
    root = settings.validation.root
    coding_root = settings.validation.coding_root or settings.data_root / "kodierung"
    paths = ValidationPaths(project, root / project, coding_root / project)
    if paths.coding.resolve().is_relative_to(root.resolve()):
        raise SchemaError(
            f"validation.coding_root {coding_root} liegt unter validation.root {root}: die "
            "Aufträge tragen Text aus Ratsdokumenten und gehören nicht ins Repo"
        )
    return paths
