"""Das Codebuch eines Vorhabens: Einheit, Fragen mit Optionen und Skala, Anweisungen, Stichprobe (F4).

Eine TOML-Datei je Vorhaben, ``validierung/<NN-name>/codebuch.toml`` (docs/validierung.md, § 2).
Sie ist das Messinstrument: welche Einheit beurteilt wird, welche Fragen die Kodierer zu ihr
beantworten, welche Antworten es gibt und was sie bedeuten, wie die Stichprobe gezogen wird,
welcher Text im Auftrag steht und welche Antworten als Treffer zählen. Die Schlüssel sind englisch
wie in jeder TOML-Datei des Pakets, die Texte deutsch. pydantic prüft das Codebuch beim Lesen; jeder
Fehler ist ein ``SchemaError`` mit dem Feld.

Ein Codebuch hat eine oder mehrere Fragen (``[[questions]]``), jede mit eigener Skala; eine Frage
kann bedingt sein (``only_if``: nur, wenn eine frühere Frage eine der genannten Antworten hat).
Übereinstimmung, Schlichtung und Labels gibt es je Frage.

Die Einheiten und die Spalten, die ihre Grundgesamtheit tragen muss (mit ``sample.key`` trägt sie
den Schlüssel selbst, etwa ``kante`` bei Vorhaben 14):

- ``document``: ``id``; Schlüssel ``<id>``.
- ``document_pair``: ``id_a``, ``id_b``; Schlüssel ``<id_a>|<id_b>``.
- ``pair_with_span``: ``id_a``, ``id_b``, dazu ``start`` und ``end`` der Fundstelle in ``id_b``
  (leer, wo es keine im Text gibt); Schlüssel ``<id_a>|<id_b>``.
- ``span``: ``id``, ``start``, ``end``, ``kind`` (F3, ``georep.spans``); Schlüssel
  ``<id>|<start>|<end>|<kind>``.
- ``query_document``: ``query``, ``id``; Schlüssel ``<query>|<id>``.
- ``marking``: ``id``; die Kodierer markieren alle Stellen einer Art im Dokument (Recall).
"""

from __future__ import annotations

import json
import math
import re
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from georep.errors import MissingInputError, SchemaError

Unit = Literal["document", "document_pair", "pair_with_span", "span", "query_document", "marking"]
Scale = Literal["nominal", "ordinal", "binary", "interval", "open", "spans"]
OPTION_SCALES = ("nominal", "ordinal", "binary")
KEY_SEPARATOR = "|"
# Die Spalten der Grundgesamtheit je Einheit, in der Reihenfolge, in der sie den Schlüssel bilden.
KEY_COLUMNS: dict[Unit, tuple[str, ...]] = {
    "document": ("id",),
    "document_pair": ("id_a", "id_b"),
    "pair_with_span": ("id_a", "id_b"),
    "span": ("id", "start", "end", "kind"),
    "query_document": ("query", "id"),
    "marking": ("id",),
}
# Spalten, die eine Einheit außer dem Schlüssel braucht; bei pair_with_span dürfen sie leer sein.
EXTRA_COLUMNS: dict[Unit, tuple[str, ...]] = {"pair_with_span": ("start", "end")}
# Die Spalten der Grundgesamtheit, die ein Dokument nennen: aus ihnen kommen die Ausschnitte.
DOCUMENT_COLUMNS: dict[Unit, tuple[str, ...]] = {
    "document": ("id",),
    "document_pair": ("id_a", "id_b"),
    "pair_with_span": ("id_a", "id_b"),
    "span": ("id",),
    "query_document": ("id",),
    "marking": ("id",),
}
# Ein Vorhaben heißt wie sein Ordner unter validierung/ und unter docs/plans/: ``11-struktur``,
# ``F4-validierung``. Kein Pfad, kein Leerzeichen.
PROJECT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")
QUESTION_ID = re.compile(r"[a-z][a-z0-9_]*")
RESERVED = frozenset({"id", "codebuch_version", "begruendung", "kodierer"})
CODEBOOK_FILE = "codebuch.toml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Option(_Strict):
    """Eine Antwort: das Label, was es bedeutet, und ein Beispiel aus der Ratsarbeit."""

    value: str  # das Label, wie es in den Antworten und in labels.csv steht
    name: str = ""  # Anzeigename, wo das Label ein Kürzel ist („fast_gleich" -> „fast gleich, gleiche Sache")
    definition: str = ""
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


class Condition(_Strict):
    """Eine Frage gilt nur, wenn eine frühere Frage eine dieser Antworten hat."""

    question: str
    values: list[str] = Field(min_length=1)


class Question(_Strict):
    """Eine Frage an die Kodierer. Skalen mit Optionen: nominal, ordinal (aufsteigend), binär.

    ``interval``: eine Zahl (etwa eine Zeilennummer); ``open``: ein freier JSON-Wert (Text, Liste,
    Objekt), verglichen in kanonischer Form; ``spans``: die Markierungen der Einheit ``marking``.
    Bei ``interval`` und ``open`` ist ``null`` eine Antwort („nichts da").
    """

    id: str
    question: str
    scale: Scale
    instructions: str = ""
    options: list[Option] = []
    only_if: Condition | None = None
    # Was als Treffer zählt (Präzision, Anteil positiver Urteile); ``ignore`` fällt aus dem Nenner
    # (etwa „unklar"). Binär: genau ein Label in ``positive``.
    positive: list[str] = []
    ignore: list[str] = []
    # false: eine Uneinigkeit geht nicht an die Schlichtung, das Label bleibt dort leer (für
    # Meta-Fragen wie „unsicher" bei Vorhaben 11, die nichts messen)
    adjudicate: bool = True
    # Wie offene Antworten verglichen werden: squeeze zieht Leerraum zu einem Leerzeichen zusammen,
    # ignore entfernt ihn ganz (pypdf setzt ihn verschieden: „66 - Amt" und „66-Amt", Vorhaben 11
    # und 12). Gespeichert wird die Antwort selbst; nur der Vergleich sieht den Schlüssel.
    whitespace: Literal["squeeze", "ignore"] = "squeeze"
    # Eine Liste als Menge: die Einträge sortiert, die Folge zählt nicht (Mehrfachauswahl, Vorhaben 15)
    unordered: bool = False

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(option.value for option in self.options)

    @field_validator("id")
    @classmethod
    def _plain_id(cls, value: str) -> str:
        if not QUESTION_ID.fullmatch(value) or value in RESERVED:
            raise ValueError(
                f"question id {value!r}: Kleinbuchstaben, Ziffern, Unterstrich, nicht {sorted(RESERVED)}"
            )
        return value

    @model_validator(mode="after")
    def _options_fit_the_scale(self) -> Question:
        labels = self.labels
        if len(set(labels)) != len(labels):
            raise ValueError(f"{self.id}: jedes Label einmal, nicht {list(labels)}")
        if self.scale in OPTION_SCALES:
            if len(labels) < 2:
                raise ValueError(
                    f"{self.id}: scale = {self.scale!r} braucht mindestens zwei Optionen"
                )
        elif labels:
            raise ValueError(f"{self.id}: scale = {self.scale!r} hat keine Optionen")
        if self.scale == "binary":
            if len(labels) != 2:
                raise ValueError(f'{self.id}: scale = "binary" braucht genau zwei Optionen')
            if len(self.positive) != 1:
                raise ValueError(f'{self.id}: scale = "binary" braucht genau ein Label in positive')
        unknown = sorted(set(self.positive + self.ignore) - set(labels))
        if unknown:
            raise ValueError(f"{self.id}: positive und ignore {unknown} sind keine Optionen")
        if self.whitespace == "ignore" and self.scale != "open":
            raise ValueError(f'{self.id}: whitespace = "ignore" gilt nur für scale = "open"')
        if set(self.positive) & set(self.ignore):
            raise ValueError(f"{self.id}: ein Label ist positive oder ignore, nicht beides")
        return self

    def canonical(self, value: object) -> str | None:
        """Die Antwort als Text für Vergleich und labels.csv; ``None`` heißt „nicht beantwortet".

        Optionen: das Label selbst; ``interval``: die Zahl ohne überflüssige Nachkommastellen;
        ``open`` und ``spans``: JSON mit sortierten Schlüsseln und Leerraum in Texten zu einem
        Leerzeichen zusammengezogen, ``null`` als „null". ``ValueError`` bei einer Antwort, die die
        Skala nicht kennt.
        """
        if self.scale in OPTION_SCALES:
            if value is None:
                return None
            if not isinstance(value, str) or value not in self.labels:
                raise ValueError(
                    f"{self.id}: {value!r} ist keine Option ({', '.join(self.labels)})"
                )
            return value
        if self.scale == "interval":
            if value is None:
                return "null"
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError(f"{self.id}: {value!r} ist keine Zahl")
            if not math.isfinite(value):
                raise ValueError(f"{self.id}: {value!r} ist keine endliche Zahl")
            return str(int(value)) if float(value).is_integer() else repr(float(value))
        if blank(value):
            return (
                "null"  # ein leerer Text ist „nichts da", wie null (Vorhaben 12: „leer bei keine")
            )
        if self.unordered and isinstance(value, list):
            value = sorted(_squeeze(value), key=lambda item: json.dumps(item, sort_keys=True))
        return json.dumps(_squeeze(value), ensure_ascii=False, sort_keys=True)


def blank(value: object) -> bool:
    """Keine Antwort: ``null`` oder ein Text aus Leerraum."""
    return value is None or (isinstance(value, str) and not value.strip())


def compare_key(question: Question, value: str | None) -> str | None:
    """Was beim Vergleich zweier Antworten zählt: die kanonische Antwort, ohne Leerraum bei ``ignore``."""
    if value is None or question.whitespace != "ignore":
        return value
    return "".join(value.split())


def _squeeze(value: Any) -> Any:
    """Leerraum in Texten zusammenziehen, rekursiv: „Ordnungs-  und\\nVerkehrsausschuss" gleich."""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, list):
        return [_squeeze(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _squeeze(v) for k, v in value.items()}
    return value


class SampleRules(_Strict):
    """Wie die Stichprobe gezogen wird (``georep validate sample``)."""

    size: int = Field(gt=0)  # Einheiten insgesamt
    seed: int  # fester Startwert: dieselbe Grundgesamtheit ergibt dieselbe Stichprobe
    stratum: str = ""  # Spalte der Grundgesamtheit, nach der geschichtet wird; leer = ungeschichtet
    # proportional: Anteile nach der Schichtgröße, größter Rest; eine Schicht, die dabei leer
    # bliebe, bekommt eine Einheit (dann ist die Stichprobe nicht mehr selbstgewichtend).
    # equal: jede Schicht gleich viele, kleine Schichten ganz (etwa „100 Treffer je Art")
    allocation: Literal["proportional", "equal"] = "proportional"
    # Parquet relativ zum Profilordner (data_root/<profil>/); leer = der Korpus
    # interim/papers.parquet, den nur die Einheiten document und marking ohne Weiteres tragen
    population: str = ""
    key: str = (
        ""  # Spalte der Grundgesamtheit, die selbst der Schlüssel ist; leer = aus der Einheit
    )
    strata: list[str] = []  # nur diese Schichten; leer = alle
    require_text: bool = True  # Einheiten ohne Text im Korpus fallen vor dem Ziehen weg


class TextRules(_Strict):
    """Was im Kodierauftrag steht (``georep validate tasks``)."""

    # corpus: der Text aus interim/papers.parquet, kleingeschrieben und ohne Zeilenumbrüche;
    # raw: der Rohtextstore von F1 (Groß- und Kleinschreibung, Zeilen, Seitenwechsel)
    source: Literal["corpus", "raw"] = "corpus"
    chars: int = Field(default=4000, gt=0)  # Länge des Ausschnitts je Dokument, vom Anfang
    window: int = Field(default=400, ge=0)  # bei einer Spanne: Zeichen vor und hinter ihr
    title: bool = True  # den Titel des Dokuments aus dem Korpus zeigen
    spans: str = ""  # Spannen nach F3 als Parquet relativ zum Profilordner; leer = keine
    span_kinds: list[str] = []  # nur Spannen dieser Arten (kind); leer = alle
    # Die Art (kind) der hervorgehobenen Spannen zeigen. Bei Spannen des geprüften Verfahrens ist
    # sie seine Ausgabe; ``tasks`` weist das ab, wenn die Spannen die Einheiten selbst sind.
    show_kind: bool = False
    # Spalten der Grundgesamtheit, die der Auftrag zeigt. Nie die Ausgabe des geprüften
    # Verfahrens: ein Kodierer, der sie sieht, misst Zustimmung, nicht Güte. Sie stehen auch in
    # stichprobe.csv im Repo, darum nur kurze Werte (ein Wahlbezirk), nie Text aus Dokumenten;
    # ``sample`` weist Werte über ``context_chars`` Zeichen ab.
    context: list[str] = []
    context_chars: int = Field(default=80, gt=0)


class ScoreRules(_Strict):
    """Wie ``georep validate score`` die Labels liest."""

    k: int = Field(default=10, gt=0)  # Rangtiefe von nDCG@k bei der Einheit query_document
    relevance: str = ""  # die Frage mit den Relevanzstufen für nDCG; leer = die erste mit Optionen


class ProvisionalRules(_Strict):
    """Wie vorläufige Antwortdateien zu lesen sind (``georep validate import``, ``importer``)."""

    key: str  # Feld der Antwortzeilen mit dem Schlüssel der Einheit (kante, aufgabe, paar)
    coder_a: str = "antworten-A.jsonl"
    coder_b: str = "antworten-B.jsonl"
    adjudication: str = "schlichtung.jsonl"
    fields: dict[str, str] = {}  # Feld der Antworten -> Frage, wo sie anders heißen
    # Frage -> {Wert als JSON-Text -> Label}, etwa {"true" = "ja", "false" = "nein"}
    values: dict[str, dict[str, str]] = {}
    reason: list[str] = ["begruendung"]  # Felder der Begründung, nicht leere mit „ / " verbunden
    # Eine Schlichtungsdatei in langer Form, eine Zeile je strittiger Frage (Vorhaben 11): das Feld
    # mit der Frage und das mit der Antwort. Leer: eine Zeile je Einheit wie bei den Kodierern.
    adjudication_question: str = ""
    adjudication_value: str = ""
    adjudication_nested: str = (
        ""  # ein Feld der Schlichtung mit {Frage: Antwort} (Vorhaben 12: entscheid)
    )
    # Statt der drei Antwortdateien eine Labeldatei der Messung in langer Form (Vorhaben 12 Runde
    # 2, Vorhaben 16): je Zeile Schlüssel (key), frage, kodierer_a, kodierer_b, schlichtung, label,
    # die Werte als JSON, leer wo nicht gestellt. A und B kommen aus kodierer_a und kodierer_b; eine
    # Einheit mit einem Eintrag unter schlichtung bekommt eine Schlichtungszeile mit ihren Labels.
    labels: str = ""
    # herkunft dieser Schlichtungszeile, wo unter schlichtung ein Objekt mit "auswerter" steht: dort
    # entschied der Auswerter nach dem Codebuch, nicht der Schlichter (Vorhaben 12, Runde 2)
    labels_auditor: str = ""


class Codebook(_Strict):
    """Das ganze Codebuch; die Fragen stehen in der Folge, in der die Kodierer sie beantworten."""

    project: str  # der Ordnername, etwa "11-struktur"
    version: str  # steht in Aufträgen, Antworten, im README der Labels und in guete.json
    unit: Unit
    instructions: str
    questions: list[Question] = Field(min_length=1)
    sample: SampleRules
    text: TextRules = TextRules()
    score: ScoreRules = ScoreRules()
    provisional: ProvisionalRules | None = (
        None  # vorläufige Antworten übernehmen (Vorhaben 11 bis 14)
    )

    @property
    def key_columns(self) -> tuple[str, ...]:
        return (self.sample.key,) if self.sample.key else KEY_COLUMNS[self.unit]

    @property
    def question_ids(self) -> tuple[str, ...]:
        return tuple(q.id for q in self.questions)

    def question(self, question_id: str) -> Question:
        return next(q for q in self.questions if q.id == question_id)

    @field_validator("project")
    @classmethod
    def _plain_project(cls, value: str) -> str:
        if not PROJECT_NAME.fullmatch(value):
            raise ValueError(f"project {value!r}: ein Ordnername wie 11-struktur")
        return value

    @model_validator(mode="after")
    def _questions_fit_together(self) -> Codebook:
        ids = [q.id for q in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError(f"questions: jede id einmal, nicht {ids}")
        for position, question in enumerate(self.questions):
            condition = question.only_if
            if condition is None:
                continue
            earlier = {q.id: q for q in self.questions[:position]}
            if condition.question not in earlier:
                raise ValueError(
                    f"{question.id}: only_if nennt {condition.question!r}, keine frühere Frage"
                )
            gate = earlier[condition.question]
            unknown = sorted(set(condition.values) - set(gate.labels))
            if unknown or gate.scale not in OPTION_SCALES:
                raise ValueError(f"{question.id}: only_if-Werte {unknown} sind keine Optionen")
        spans = [q.id for q in self.questions if q.scale == "spans"]
        if (self.unit == "marking") != bool(spans):
            raise ValueError('scale = "spans" gehört zur Einheit marking und nur zu ihr')
        clash = sorted(set(self.text.context) & {*self.key_columns, "schicht", "schicht_n"})
        if clash:
            raise ValueError(f"text.context {clash}: Schlüsselspalten stehen ohnehin im Auftrag")
        rules = self.provisional
        if rules is not None:
            unknown = sorted((set(rules.fields.values()) | set(rules.values)) - set(ids))
            if unknown:
                raise ValueError(f"provisional: {unknown} sind keine Fragen")
        if self.score.relevance and self.score.relevance not in ids:
            raise ValueError(f"score.relevance {self.score.relevance!r} ist keine Frage")
        return self


def applies(question: Question, answers: dict[str, str | None]) -> bool:
    """Ob die Frage gestellt ist: ohne ``only_if`` immer, sonst nach der Antwort auf die frühere."""
    condition = question.only_if
    return condition is None or answers.get(condition.question) in condition.values


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
