"""Ein kleines Projekt für die Tests der Validierung (F4): Settings, Korpus, Codebuch in ``tmp_path``.

Kein Lauf der Kette: der Korpus entsteht hier als Parquet mit genau den Spalten, die
``georep.validation`` liest, damit jede Zahl im Test von Hand nachzuzählen ist. Der Durchlauf über
die Mini-Fixture steht in ``tests/unit/test_validation_flow.py``.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from georep.layout import Layout
from georep.settings import load_settings

PROJECT = "11-test"

# 30 Dokumente: 15 Anträge, 10 Anfragen, 5 Vorlagen; d28 und d29 ohne Text.
TYPES = ["Antrag"] * 15 + ["Anfrage"] * 10 + ["Vorlage"] * 5


def corpus_frame() -> pl.DataFrame:
    ids = [f"d{i:02d}" for i in range(len(TYPES))]
    texts = [
        "" if i in (28, 29) else f"text von {doc}. " + "der rat beschliesst die sache. " * 20
        for i, doc in enumerate(ids)
    ]
    return pl.DataFrame(
        {
            "id": ids,
            "name": [f"Titel {doc}" for doc in ids],
            "paper_type": TYPES,
            "file_name": [f"{doc}.pdf" for doc in ids],
            "text": texts,
        }
    )


CODEBOOK = """\
project = "11-test"
version = "1"
unit = "document"
question = "Enthält das Dokument einen Beschlussvorschlag?"
scale = "binary"
instructions = "Lies den Ausschnitt. Antworte ja, wenn ein Beschlussvorschlag dasteht."

[[options]]
value = "ja"
definition = "Der Ausschnitt nennt einen Beschlussvorschlag."
example = "Der Rat beschließt ..."

[[options]]
value = "nein"
definition = "Kein Beschlussvorschlag im Ausschnitt."

[sample]
size = 9
seed = 7
stratum = "paper_type"

[text]
chars = 60

[score]
positive = "ja"
"""


def make_project(tmp_path: Path, codebook: str = CODEBOOK, project: str = PROJECT) -> Layout:
    """Settings, Korpus und Codebuch unter ``tmp_path``; Arbeitsverzeichnis setzt der Test."""
    (tmp_path / "settings.toml").write_text(
        f'data_root = "{tmp_path / "data"}"\n'
        f'validation.root = "{tmp_path / "validierung"}"\n'
        f'validation.coding_root = "{tmp_path / "lokal"}"\n',
        encoding="utf-8",
    )
    layout = Layout.from_settings(load_settings(cwd=tmp_path))
    layout.interim.mkdir(parents=True, exist_ok=True)
    corpus_frame().write_parquet(layout.corpus)
    folder = tmp_path / "validierung" / project
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "codebuch.toml").write_text(codebook, encoding="utf-8")
    return layout
