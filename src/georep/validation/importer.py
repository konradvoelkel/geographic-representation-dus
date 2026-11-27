"""Vorläufige Antworten übernehmen (``georep validate import <vorhaben> --from <ordner>``, F4).

Die Vorhaben 11 bis 14 haben kodieren lassen, bevor F4 stand: je Kodierer eine Datei
``antworten-A.jsonl`` und ``antworten-B.jsonl``, dazu ``schlichtung.jsonl``, flach je Einheit mit
einem eigenen Schlüsselfeld (``kante``, ``aufgabe``, ``paar``) und den Antworten unter den Namen
der Fragen. ``[provisional]`` im Codebuch sagt, wie sie zu lesen sind (Schlüsselfeld, Felder, die
anders heißen als ihre Frage, Werte, die ein Label werden, etwa ``true`` -> ``ja``). Der Import
schreibt daraus ``antworten.jsonl`` im Format von F4 nach ``<coding_root>/<vorhaben>/<A|B|
schlichtung>/``; danach rechnen ``merge`` und ``score`` wie bei jeder Kodierung. Die Quelldateien
liest er nur. Zeilen, deren Schlüssel nicht in der Stichprobe steht, zählt er und lässt sie weg
(bei Vorhaben 12 stehen Präzision und Recall in einer Datei).

Vorhaben 12 (Runde 2) und 16 legten statt der Antwortdateien ihre Labels im Repo ab, in langer
Form wie ``labels.csv`` von F4 (Schlüssel, ``frage``, ``kodierer_a``, ``kodierer_b``,
``schlichtung``, ``label``), die Werte als JSON. Mit ``[provisional] labels`` liest der Import
diese Datei: A und B aus ihren Spalten, und für jede Einheit mit einem Eintrag unter
``schlichtung`` eine Schlichtungszeile aus ``label``. Steht dort ein Objekt mit ``auswerter``,
entschied der Auswerter nach dem Codebuch; die Zeile trägt dann ``labels_auditor`` als
``herkunft``, die README und guete.json zählen.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from georep.errors import MissingInputError, SchemaError
from georep.io import write_text
from georep.layout import Layout
from georep.settings import Settings
from georep.validation import CodingError
from georep.validation.codebook import Codebook, ProvisionalRules, load_codebook
from georep.validation.paths import Role, validation_paths
from georep.validation.sample import ID, read_sample
from georep.validation.tasks import answers_started, jsonl


def convert(
    record: Mapping[str, Any], codebook: Codebook, rules: ProvisionalRules
) -> dict[str, Any]:
    """Eine vorläufige Antwortzeile im Format von F4; Werte erst abgebildet, geprüft wird in merge."""
    renamed = {rules.fields.get(field, field): value for field, value in record.items()}
    converted: dict[str, Any] = {"id": str(record[rules.key]), "codebuch_version": codebook.version}
    for question in codebook.questions:
        value = renamed.get(question.id)
        mapping = rules.values.get(question.id, {})
        key = json.dumps(value, ensure_ascii=False)
        converted[question.id] = mapping.get(key, value) if mapping else value
    reasons = [str(renamed[f]) for f in rules.reason if renamed.get(f)]
    converted["begruendung"] = " / ".join(reasons)
    if record.get("herkunft"):
        converted["herkunft"] = str(record["herkunft"])  # wer entschied, wo nicht der Schlichter
    return converted


LABEL_FILE_COLUMNS = ("frage", "kodierer_a", "kodierer_b", "schlichtung", "label")


def _value(cell: str, where: str) -> object:
    """Ein Wert der Labeldatei: JSON; eine leere Zelle heißt „nicht gestellt"."""
    if not cell:
        return None
    try:
        return json.loads(cell)
    except json.JSONDecodeError as error:
        raise SchemaError(f"{where}: kein JSON ({cell[:40]!r})") from error


def from_labels(
    path: Path, codebook: Codebook, rules: ProvisionalRules, units: set[str]
) -> tuple[dict[Role, list[dict[str, Any]]], dict[Role, int]]:
    """Die Antwortzeilen von A, B und der Schlichtung aus einer Labeldatei in langer Form.

    Dazu je Rolle die Zahl der Zeilen, deren Einheit nicht in der Stichprobe steht. Eine Frage, die
    weder im Codebuch noch unter ``fields`` steht, ist bei einer Einheit der Stichprobe ein Fehler:
    sie fiele sonst still weg.
    """
    if not path.is_file():
        raise MissingInputError(f"{path} fehlt")
    frame = pl.read_csv(path, infer_schema=False).with_columns(pl.all().fill_null(""))
    missing = [c for c in (rules.key, *LABEL_FILE_COLUMNS) if c not in frame.columns]
    if missing:
        raise SchemaError(f"{path}: Spalten {missing} fehlen")
    cells: dict[str, dict[str, dict[str, str]]] = {}
    for row in frame.iter_rows(named=True):
        cells.setdefault(row[rules.key], {})[row["frage"]] = row
    known = set(codebook.question_ids) | set(rules.fields)
    records: dict[Role, list[dict[str, Any]]] = {"A": [], "B": [], "schlichtung": []}
    skipped: dict[Role, int] = dict.fromkeys(records, 0)
    for unit, questions in sorted(cells.items()):
        decided = {q: row for q, row in questions.items() if row["schlichtung"]}
        if unit not in units:
            skipped["A"] += len(questions)
            skipped["B"] += len(questions)
            skipped["schlichtung"] += len(decided)
            continue
        unknown = sorted(set(questions) - known)
        if unknown:
            raise SchemaError(f"{path}: {unit} trägt Fragen außerhalb des Codebuchs {unknown}")
        coders: tuple[tuple[Role, str], ...] = (("A", "kodierer_a"), ("B", "kodierer_b"))
        for role, column in coders:
            records[role].append(
                {rules.key: unit}
                | {
                    q: _value(row[column], f"{path.name}: {unit} {q}")
                    for q, row in questions.items()
                }
            )
        if not decided:
            continue
        adjudicated = {rules.key: unit} | {
            q: _value(row["label"], f"{path.name}: {unit} {q}") for q, row in questions.items()
        }
        notes = [
            _value(row["schlichtung"], f"{path.name}: {unit} {q}") for q, row in decided.items()
        ]
        if rules.labels_auditor and any(isinstance(n, dict) and "auswerter" in n for n in notes):
            adjudicated["herkunft"] = rules.labels_auditor
        records["schlichtung"].append(adjudicated)
    return records, skipped


def pivot(records: list[dict[str, Any]], rules: ProvisionalRules) -> list[dict[str, Any]]:
    """Eine Schlichtung in langer Form (eine Zeile je Einheit und Frage) als eine Zeile je Einheit."""
    units: dict[str, dict[str, Any]] = {}
    for record in records:
        unit = units.setdefault(str(record[rules.key]), {rules.key: record[rules.key]})
        unit[str(record[rules.adjudication_question])] = record.get(rules.adjudication_value)
        reasons = [str(record[f]) for f in rules.reason if record.get(f)]
        if reasons:
            previous = unit.get(rules.reason[0])
            unit[rules.reason[0]] = " / ".join([*([previous] if previous else []), *reasons])
    return list(units.values())


@dataclass(frozen=True)
class ImportReport:
    written: dict[str, int]  # Rolle -> übernommene Einheiten
    skipped: dict[str, int]  # Rolle -> Zeilen ohne Einheit in der Stichprobe

    def lines(self) -> list[str]:
        return [
            f"{role}: {count} Einheiten übernommen"
            + (
                f", {self.skipped[role]} Zeilen nicht in der Stichprobe"
                if self.skipped[role]
                else ""
            )
            for role, count in self.written.items()
        ]


def import_project(
    settings: Settings, layout: Layout, project: str, source: Path, *, force: bool = False
) -> ImportReport:
    """``georep validate import``: vorläufige Antwortdateien in das Format von F4 übernehmen."""
    paths = validation_paths(settings, project)
    codebook = load_codebook(paths.codebook, project)
    rules = codebook.provisional
    if rules is None:
        raise SchemaError(f"{paths.codebook}: ohne [provisional] gibt es nichts zu übernehmen")
    units = set(read_sample(paths, codebook).get_column(ID).to_list())
    written: dict[str, int] = {}
    skipped: dict[str, int] = {}
    if rules.labels:
        by_role, outside = from_labels(source / rules.labels, codebook, rules, units)
        for role, found in by_role.items():
            if role == "schlichtung" and not found:
                continue
            if answers_started(paths.answers(role)) and not force:
                raise CodingError(
                    f"{paths.answers(role)} trägt schon Antworten; --force übernimmt neu"
                )
            write_text(paths.answers(role), jsonl([convert(r, codebook, rules) for r in found]))
            written[role] = len(found)
            skipped[role] = outside[role]
        return ImportReport(written, skipped)
    roles: dict[Role, str] = {
        "A": rules.coder_a,
        "B": rules.coder_b,
        "schlichtung": rules.adjudication,
    }
    for role, name in roles.items():
        path = source / name
        if not path.is_file():
            if role != "schlichtung":
                raise MissingInputError(f"{path} fehlt")
            continue
        if answers_started(paths.answers(role)) and not force:
            raise CodingError(f"{paths.answers(role)} trägt schon Antworten; --force übernimmt neu")
        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        missing = [r for r in records if rules.key not in r]
        if missing:
            raise SchemaError(f"{path}: {len(missing)} Zeilen ohne Schlüsselfeld {rules.key!r}")
        if role == "schlichtung" and rules.adjudication_question:
            records = pivot(records, rules)
        if role == "schlichtung" and rules.adjudication_nested:
            records = [r | dict(r.get(rules.adjudication_nested) or {}) for r in records]
        kept = [convert(r, codebook, rules) for r in records if str(r[rules.key]) in units]
        write_text(paths.answers(role), jsonl(kept))
        written[role] = len(kept)
        skipped[role] = len(records) - len(kept)
    return ImportReport(written, skipped)
