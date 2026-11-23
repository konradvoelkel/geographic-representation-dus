"""Das Codebuch eines Vorhabens: Einheit, Frage, Optionen, Skala, Anweisungen, Stichprobe (F4).

Eine TOML-Datei je Vorhaben, ``validierung/<NN-name>/codebuch.toml`` (docs/validierung.md, § 2).
Sie ist das Messinstrument: was die Kodierer gefragt werden, welche Antworten es gibt und was sie
bedeuten, wie die Stichprobe gezogen wird, welcher Text im Auftrag steht und welche Antwort als
Treffer zählt. Die Schlüssel sind englisch wie in jeder TOML-Datei des Pakets, die Texte deutsch.
pydantic prüft das Codebuch beim Lesen; jeder Fehler ist ein ``SchemaError`` mit dem Feld.

Die vier Einheiten und die Spalten, die ihre Grundgesamtheit tragen muss:

========================  ===============================  ===========================
Einheit                   Spalten der Grundgesamtheit      Schlüssel ``id``
========================  ===============================  ===========================
``document``              ``id``                           ``<id>``
``document_pair``         ``id_a``, ``id_b``               ``<id_a>|<id_b>``
``span``                  ``id``, ``start``, ``end`` (F3)  ``<id>|<start>|<end>``
``query_document``        ``query``, ``id``                ``<query>|<id>``
========================  ===============================  ===========================
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from georep.errors import MissingInputError, SchemaError

Unit = Literal["document", "document_pair", "span", "query_document"]
Scale = Literal["nominal", "ordinal", "binary"]
KEY_SEPARATOR = "|"
# Die Spalten der Grundgesamtheit je Einheit, in der Reihenfolge, in der sie den Schlüssel bilden.
KEY_COLUMNS: dict[Unit, tuple[str, ...]] = {
    "document": ("id",),
    "document_pair": ("id_a", "id_b"),
    "span": ("id", "start", "end"),
    "query_document": ("query", "id"),
}
# Die Spalten der Grundgesamtheit, die ein Dokument nennen: aus ihnen kommen die Ausschnitte.
DOCUMENT_COLUMNS: dict[Unit, tuple[str, ...]] = {
    "document": ("id",),
    "document_pair": ("id_a", "id_b"),
    "span": ("id",),
    "query_document": ("id",),
}
# Ein Vorhaben heißt wie sein Ordner unter validierung/ und unter docs/plans/: ``11-struktur``,
# ``F4-validierung``. Kein Pfad, kein Leerzeichen.
PROJECT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")
CODEBOOK_FILE = "codebuch.toml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Option(_Strict):
    """Eine Antwort: das Label, was es bedeutet, und ein Beispiel aus der Ratsarbeit."""

    value: str  # das Label, wie es in den Antworten und in labels.csv steht
    definition: str
    example: str = ""

    @field_validator("value")
    @classmethod
    def _plain_label(cls, value: str) -> str:
        if not value or value != value.strip() or "\n" in value or KEY_SEPARATOR in value:
            raise ValueError(
                f"option {value!r}: ein Label ist nicht leer, ohne Rand, ohne Zeilenumbruch und "
                f"ohne {KEY_SEPARATOR!r}"
            )
        return value


class SampleRules(_Strict):
    """Wie die Stichprobe gezogen wird (``georep validate sample``)."""

    size: int = Field(gt=0)  # Einheiten insgesamt
    seed: int  # fester Startwert: dieselbe Grundgesamtheit ergibt dieselbe Stichprobe
    stratum: str = ""  # Spalte der Grundgesamtheit, nach der geschichtet wird; leer = ungeschichtet
    # proportional: jede Schicht mindestens eine Einheit, der Rest nach ihrer Größe;
    # equal: jede Schicht gleich viele, kleine Schichten ganz (etwa „100 Treffer je Art")
    allocation: Literal["proportional", "equal"] = "proportional"
    # Parquet relativ zum Profilordner (data_root/<profil>/); leer = der Korpus
    # interim/papers.parquet, den nur die Einheit document ohne Weiteres trägt
    population: str = ""
    strata: list[str] = []  # nur diese Schichten; leer = alle
    require_text: bool = True  # Einheiten ohne Text im Korpus fallen vor dem Ziehen weg


class TextRules(_Strict):
    """Was im Kodierauftrag steht (``georep validate tasks``)."""

    # corpus: der Text aus interim/papers.parquet, kleingeschrieben und ohne Zeilenumbrüche;
    # raw: der Rohtextstore von F1 (Groß- und Kleinschreibung, Zeilen, Seitenwechsel)
    source: Literal["corpus", "raw"] = "corpus"
    chars: int = Field(default=4000, gt=0)  # Länge des Ausschnitts je Dokument, vom Anfang
    window: int = Field(
        default=400, ge=0
    )  # bei der Einheit span: Zeichen vor und hinter der Spanne
    title: bool = True  # den Titel des Dokuments aus dem Korpus zeigen
    spans: str = ""  # Spannen nach F3 als Parquet relativ zum Profilordner; leer = keine
    span_kinds: list[str] = []  # nur Spannen dieser Arten (kind); leer = alle
    # Spalten der Grundgesamtheit, die der Auftrag zeigt. Nie die Ausgabe des geprüften
    # Verfahrens: ein Kodierer, der sie sieht, misst Zustimmung, nicht Güte. Sie stehen auch in
    # stichprobe.csv im Repo, darum nur kurze Werte (ein Wahlbezirk), nie Text aus Dokumenten.
    context: list[str] = []


class ScoreRules(_Strict):
    """Wie ``georep validate score`` die Labels liest."""

    positive: str = ""  # binär: das Label, das als Treffer zählt (Pflicht bei scale = "binary")
    k: int = Field(default=10, gt=0)  # Rangtiefe von nDCG@k bei der Einheit query_document


class Codebook(_Strict):
    """Das ganze Codebuch; ``labels`` ist die Reihenfolge der Optionen (ordinal: aufsteigend)."""

    project: str  # der Ordnername, etwa "11-struktur"
    version: str  # steht in den Aufträgen, in labels.csv-README und in guete.json
    unit: Unit
    question: str
    scale: Scale
    instructions: str
    options: list[Option] = Field(min_length=2)
    sample: SampleRules
    text: TextRules = TextRules()
    score: ScoreRules = ScoreRules()

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(option.value for option in self.options)

    @property
    def key_columns(self) -> tuple[str, ...]:
        return KEY_COLUMNS[self.unit]

    @field_validator("project")
    @classmethod
    def _plain_project(cls, value: str) -> str:
        if not PROJECT_NAME.fullmatch(value):
            raise ValueError(f"project {value!r}: ein Ordnername wie 11-struktur")
        return value

    @model_validator(mode="after")
    def _options_fit_the_scale(self) -> Codebook:
        labels = self.labels
        if len(set(labels)) != len(labels):
            raise ValueError(f"options: jedes Label einmal, nicht {list(labels)}")
        if self.scale == "binary":
            if len(labels) != 2:
                raise ValueError(
                    f'scale = "binary" braucht genau zwei Optionen, nicht {len(labels)}'
                )
            if self.score.positive not in labels:
                raise ValueError(
                    f'scale = "binary" braucht score.positive aus {list(labels)}, '
                    f"nicht {self.score.positive!r}"
                )
        elif self.score.positive:
            raise ValueError('score.positive gilt nur bei scale = "binary"')
        clash = sorted(set(self.text.context) & {*self.key_columns, "schicht"})
        if clash:
            raise ValueError(f"text.context {clash}: Schlüsselspalten stehen ohnehin im Auftrag")
        return self


def codebook_problem(error: ValidationError) -> str:
    """Die erste Meldung von pydantic als eine Zeile: Feld und Grund."""
    first = error.errors()[0]
    where = ".".join(str(part) for part in first["loc"]) or "(Codebuch)"
    return f"{where}: {first['msg']}"


def load_codebook(path: Path, project: str) -> Codebook:
    """Das Codebuch lesen und prüfen; ``project`` muss der Ordnername sein."""
    if not path.is_file():
        raise MissingInputError(
            f"{path} fehlt: das Codebuch schreibt der Mess-Agent (docs/validierung.md, § 2)"
        )
    try:
        codebook = Codebook.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except tomllib.TOMLDecodeError as error:
        raise SchemaError(f"{path}: kein TOML ({error})") from error
    except ValidationError as error:
        raise SchemaError(f"{path}: {codebook_problem(error)}") from error
    if codebook.project != project:
        raise SchemaError(f"{path}: project = {codebook.project!r}, der Ordner heißt {project!r}")
    return codebook
