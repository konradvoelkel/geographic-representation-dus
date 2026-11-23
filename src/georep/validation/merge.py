"""Zwei Kodierungen zusammenführen, Uneinigkeiten schlichten lassen, Labels ablegen (F4).

``georep validate merge <vorhaben> --model <name>`` liest die Antworten von A und B, je Einheit und
Frage. Sind beide vollständig, gibt es zwei Ausgänge:

1. Es gibt Uneinigkeiten, und die Schlichtung ist nicht vollständig: der Auftrag des
   Schlicht-Agenten entsteht unter ``<coding_root>/<vorhaben>/schlichtung/`` (je Einheit mit
   Uneinigkeit eine Zeile: die strittigen Fragen und beide Kodierungen mit Begründung, in einer
   je Einheit festen, aber nicht immer gleichen Folge) samt leerer Antwortdatei. Begonnene
   Antworten bleiben stehen; passt der Auftrag nicht mehr zu den Uneinigkeiten (A oder B haben
   neu kodiert), bricht der Befehl ab, bis ``--force`` die Schlichtung zurücksetzt.
2. Es gibt keine Uneinigkeit, oder die Schlichtung ist vollständig: ``labels.csv`` (``id``,
   ``frage``, ``kodierer_a``, ``kodierer_b``, ``schlichtung``, ``label``), ``README.md`` und
   ``guete.json`` mit der Übereinstimmung je Frage entstehen im Ordner des Vorhabens im Repo.
   Begründungen bleiben lokal: sie dürfen Text zitieren.

Eine Antwortdatei ist nur brauchbar, wenn sie jede Einheit genau einmal trägt, mit der
``codebuch_version`` des Codebuchs und je gestellter Frage einer gültigen Antwort; eine Frage,
deren Bedingung nicht erfüllt ist, bleibt ``null``. Sonst nennt ein ``CodingError`` Zahl und
Beispiel je Fehlerart.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from georep.errors import MissingInputError
from georep.io import atomic_path, write_json, write_text
from georep.layout import Layout
from georep.settings import Settings
from georep.validation import CodingError
from georep.validation.codebook import OPTION_SCALES, Codebook, Question, applies, load_codebook
from georep.validation.measures import agreement, cohen_kappa, krippendorff_alpha, wilson_interval
from georep.validation.paths import ADJUDICATION, ValidationPaths, validation_paths
from georep.validation.sample import ID, rank, read_sample, sample_meta
from georep.validation.tasks import answers_started, write_assignment

LABEL_COLUMNS = ("id", "frage", "kodierer_a", "kodierer_b", "schlichtung", "label")
META_KEYS = ("id", "codebuch_version", "begruendung", "kodierer")
# Wie die Seite eine Einheit im Plural nennt: „geprüft von zwei KI-Kodierern an n …".
UNIT_PLURAL = {
    "document": "Dokumenten",
    "document_pair": "Dokumentpaaren",
    "pair_with_span": "Dokumentpaaren",
    "span": "Textstellen",
    "query_document": "Paaren aus Suchanfrage und Dokument",
    "marking": "Dokumenten",
}
Values = dict[str, str | None]


@dataclass(frozen=True)
class Coding:
    """Die Antworten eines Agenten zu einer Einheit, kanonisch; ``None``: nicht gestellt."""

    id: str
    values: Values
    reason: str


class _Problems:
    def __init__(self) -> None:
        self.items: dict[str, list[str]] = {}

    def note(self, kind: str, what: str) -> None:
        self.items.setdefault(kind, []).append(what)

    def raise_if_any(self, path: Path) -> None:
        if self.items:
            summary = "; ".join(
                f"{kind} {len(found)} (etwa {found[0]})"
                for kind, found in sorted(self.items.items())
            )
            raise CodingError(f"{path}: nicht vollständig: {summary}")


def _records(path: Path, problems: _Problems) -> list[dict[str, Any]]:
    if not path.is_file():
        raise MissingInputError(f"{path} fehlt; `georep validate tasks` schreibt sie")
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            problems.note("kein JSON", f"Zeile {number}")
            continue
        if not isinstance(record, dict):
            problems.note("kein JSON-Objekt", f"Zeile {number}")
            continue
        records.append(record)
    return records


def _fill(
    codebook: Codebook,
    record: Mapping[str, Any],
    asked: Sequence[str],
    given: Values,
    problems: _Problems,
    unit: str,
) -> Values:
    """Die Antworten auf ``asked`` aus ``record``; die übrigen aus ``given``, Bedingungen in Folge."""
    values: Values = {}
    for question in codebook.questions:
        if question.id not in asked:
            value = given.get(question.id)
            values[question.id] = value if applies(question, values) else None
            continue
        raw = record.get(question.id)
        if not applies(question, values):
            if raw is not None:
                problems.note("beantwortet, obwohl nicht gestellt", f"{unit}: {question.id}")
            values[question.id] = None
            continue
        try:
            value = question.canonical(raw)
        except ValueError as error:
            problems.note("ungültige Antwort", f"{unit}: {error}")
            values[question.id] = None
            continue
        if value is None:
            problems.note("ohne Antwort", f"{unit}: {question.id}")
        values[question.id] = value
    return values


def read_answers(path: Path, ids: Sequence[str], codebook: Codebook) -> dict[str, Coding]:
    """Eine vollständige Antwortdatei: jede Einheit genau einmal, jede gestellte Frage beantwortet."""
    problems = _Problems()
    expected, seen = set(ids), set()
    found: dict[str, Coding] = {}
    for record in _records(path, problems):
        unit = record.get("id")
        if not isinstance(unit, str) or not unit:
            problems.note("leere id", repr(unit))
            continue
        if unit not in expected:
            problems.note("unbekannte id", repr(unit))
            continue
        if unit in seen:
            problems.note("doppelt", unit)
            continue
        seen.add(unit)
        if record.get("codebuch_version") != codebook.version:
            problems.note(
                "andere codebuch_version",
                f"{unit}: {record.get('codebuch_version')!r} statt {codebook.version!r}",
            )
            continue
        values = _fill(codebook, record, codebook.question_ids, {}, problems, unit)
        reason = record.get("begruendung")
        found[unit] = Coding(unit, values, reason if isinstance(reason, str) else "")
    for unit in sorted(expected - seen):
        problems.note("fehlt", unit)
    problems.raise_if_any(path)
    return found


@dataclass(frozen=True)
class Reliability:
    """Übereinstimmung der beiden Kodierer bei einer Frage über die Einheiten, wo sie gestellt war."""

    question: str
    scale: str
    n: int  # Einheiten, bei denen mindestens ein Kodierer die Frage beantwortet hat
    both: int  # Einheiten, bei denen beide geantwortet haben
    agreed: int
    share: float | None
    interval: tuple[float, float] | None
    kappa: float | None
    alpha_nominal: float | None
    alpha_scale: float | None  # ordinal bei ordinaler, intervall bei Intervallskala, sonst None

    def alpha(self) -> float | None:
        """Das α, an dem Stufe 3 gemessen wird: das der Skala, sonst das nominale."""
        return self.alpha_scale if self.scale in ("ordinal", "interval") else self.alpha_nominal

    def as_json(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "beide": self.both,
            "einig": self.agreed,
            "anteil": self.share,
            "anteil_wilson95": list(self.interval) if self.interval else None,
            "cohen_kappa": self.kappa,
            "krippendorff_alpha_nominal": self.alpha_nominal,
            "krippendorff_alpha_skala": self.alpha_scale,
            "krippendorff_alpha": self.alpha(),
        }


def reliability(
    question: Question, first: Sequence[str | None], second: Sequence[str | None]
) -> Reliability:
    """κ, α und der Anteil gleicher Antworten für eine Frage; ``None`` heißt „nicht gestellt"."""
    units = [(a, b) for a, b in zip(first, second, strict=True) if a is not None or b is not None]
    both = [(a, b) for a, b in units if a is not None and b is not None]
    firsts = [a for a, _ in both if a is not None]
    seconds = [b for _, b in both if b is not None]
    agreed = sum(1 for a, b in both if a == b)
    observed = sorted({v for pair in units for v in pair if v is not None})
    categories = list(question.labels) if question.scale in OPTION_SCALES else observed
    alpha_scale = None
    if question.scale == "ordinal":
        alpha_scale = krippendorff_alpha(units, "ordinal", categories)
    elif question.scale == "interval":
        numbers = [v for v in observed if v != "null"]
        numeric = [tuple(v if v != "null" else None for v in pair) for pair in units]
        alpha_scale = krippendorff_alpha(numeric, "interval", numbers) if numbers else None
    return Reliability(
        question=question.id,
        scale=question.scale,
        n=len(units),
        both=len(both),
        agreed=agreed,
        share=agreement(firsts, seconds),
        interval=wilson_interval(agreed, len(both)) if both else None,
        kappa=cohen_kappa(firsts, seconds) if both else None,
        alpha_nominal=krippendorff_alpha(units, "nominal", categories) if units else None,
        alpha_scale=alpha_scale,
    )


def format_number(value: float | None, digits: int = 3) -> str:
    return "nicht definiert" if value is None else f"{value:.{digits}f}".replace(".", ",")


def format_percent(value: float | None) -> str:
    return "nicht definiert" if value is None else f"{100 * value:.1f}".replace(".", ",") + " %"


def _cell(text: str) -> str:
    """Ein Wert in einer Markdown-Tabelle: ``|`` darf die Zelle nicht teilen."""
    return text.replace("|", "\\|")


def alpha_suffices(result: Reliability, min_alpha: float) -> bool:
    """Stufe 3: α definiert und mindestens ``min_alpha``; ein undefiniertes α genügt nie."""
    alpha = result.alpha()
    return alpha is not None and alpha >= min_alpha


def _adjudicated(disputed: int) -> str:
    """Der Halbsatz zur Schlichtung, für keine, eine und mehrere Uneinigkeiten."""
    if disputed == 0:
        return "Uneinigkeiten gab es keine, eine Schlichtung war nicht nötig"
    if disputed == 1:
        return "die eine Uneinigkeit entschied ein dritter Agent (Schlichtung)"
    return f"die {disputed} Uneinigkeiten entschied ein dritter Agent (Schlichtung)"


def readme(
    codebook: Codebook,
    meta: Mapping[str, Any],
    results: Sequence[Reliability],
    units: int,
    disputed: int,
    model: str,
    today: dt.date,
    min_alpha: float,
) -> str:
    stratum = meta.get("schicht") or ""
    rows = [
        f"| `{_cell(r.question)}` | {r.scale} | {r.n} | {r.agreed} von {r.both} "
        f"({format_percent(r.share)}) | {format_number(r.kappa)} | {format_number(r.alpha())} | "
        f"{'ja' if alpha_suffices(r, min_alpha) else 'nein'} |"
        for r in results
    ]
    return "\n".join(
        [
            f"# Validierung {codebook.project}",
            "",
            f"Erzeugt von `georep validate merge` am {today.isoformat()}; nicht von Hand ändern. "
            "Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).",
            "",
            f"- **Codebuch**: `codebuch.toml`, Version {codebook.version}; Einheit "
            f"`{codebook.unit}`, {len(codebook.questions)} "
            f"Frage{'n' if len(codebook.questions) != 1 else ''}.",
            f"- **Stichprobe**: {units} Einheiten aus Profil `{meta.get('profil')}`, "
            + (f"geschichtet nach `{stratum}`, " if stratum else "ungeschichtet, ")
            + ("selbstgewichtend" if meta.get("selbstgewichtend") else "gewichtet mit N_h/n_h")
            + " (`stichprobe.csv`, `stichprobe.json`).",
            f"- **Kodierer**: zwei KI-Kodierer, Modell `{_cell(model)}`, unabhängig voneinander und "
            f"ohne die Ausgabe des geprüften Verfahrens; {_adjudicated(disputed)}. **Kein "
            "menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem "
            "stärkeren Modell, nicht mit Menschen.",
            f"- **Datum**: {today.isoformat()}.",
            "",
            f"Übereinstimmung A–B je Frage; Stufe 3 verlangt α ≥ {format_number(min_alpha, 2)} "
            "(ordinal bei ordinaler, intervall bei Intervallskala, sonst nominal):",
            "",
            "| Frage | Skala | gestellt | gleich | Cohens κ | Krippendorffs α | genügt |",
            "|---|---|---|---|---|---|---|",
            *rows,
            "",
            "## labels.csv",
            "",
            "| Spalte | Inhalt |",
            "|---|---|",
            "| `id` | Schlüssel der Einheit (`stichprobe.csv` trägt seine Teile einzeln) |",
            "| `frage` | die Frage aus dem Codebuch |",
            "| `kodierer_a`, `kodierer_b` | die Antworten von A und B; leer, wo die Frage nicht "
            "gestellt war |",
            "| `schlichtung` | die Antwort der Schlichtung; leer, wo A und B einig waren |",
            "| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |",
            "",
        ]
    )


@dataclass(frozen=True)
class MergeReport:
    results: tuple[Reliability, ...]
    disputed: int  # strittige Paare aus Einheit und Frage
    open: int  # Einheiten, die die Schlichtung noch nicht entschieden hat
    labels: Path | None  # None, solange die Schlichtung offen ist
    adjudication: Path | None

    def lines(self) -> list[str]:
        out = [
            f"{r.question}: {r.n} Einheiten, einig {r.agreed} von {r.both} "
            f"({format_percent(r.share)}), κ {format_number(r.kappa)}, α {format_number(r.alpha())}"
            for r in self.results
        ]
        out.append(f"{self.disputed} Uneinigkeiten")
        if self.labels is not None:
            return [*out, f"Labels -> {self.labels}"]
        return [*out, f"Schlichtung offen: {self.open} Einheiten -> {self.adjudication}"]


def _first_is_a(seed: int, unit: str) -> bool:
    """Welche Kodierung die Schlichtung als erste sieht: je Einheit fest, im Mittel halb A."""
    return int(rank(seed, f"schlichtung|{unit}"), 16) % 2 == 0


def _tasks_of(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    return {
        record["id"]: record
        for record in (
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }


def _adjudication_tasks(
    paths: ValidationPaths,
    codebook: Codebook,
    disputes: Mapping[str, list[str]],
    a: Mapping[str, Coding],
    b: Mapping[str, Coding],
) -> list[dict[str, Any]]:
    """Je Einheit mit Uneinigkeit: der Auftrag von A (wo es ihn gibt) und beide Kodierungen."""
    tasks = _tasks_of(paths.tasks("A"))
    records = []
    for unit, strittig in disputes.items():
        first, second = (
            (a[unit], b[unit]) if _first_is_a(codebook.sample.seed, unit) else (b[unit], a[unit])
        )
        records.append(
            tasks.get(
                unit,
                {"id": unit, "vorhaben": codebook.project, "codebuch_version": codebook.version},
            )
            | {
                "strittig": strittig,
                "kodierung_1": {**first.values, "begruendung": first.reason},
                "kodierung_2": {**second.values, "begruendung": second.reason},
                "antwort": None,
            }
        )
    return records


def reset_adjudication(paths: ValidationPaths) -> None:
    """``merge --force``: Auftrag, Antworten und Codebuch der Schlichtung entfernen."""
    for path in (paths.tasks(ADJUDICATION), paths.answers(ADJUDICATION), paths.brief(ADJUDICATION)):
        path.unlink(missing_ok=True)


def read_adjudication(
    path: Path,
    codebook: Codebook,
    disputes: Mapping[str, list[str]],
    agreed: Mapping[str, Values],
) -> dict[str, Values]:
    """Die Endantworten der strittigen Einheiten: Einigkeit plus Schlichtung, Bedingungen in Folge."""
    problems = _Problems()
    seen: set[str] = set()
    final: dict[str, Values] = {}
    for record in _records(path, problems):
        unit = record.get("id")
        if not isinstance(unit, str) or unit not in disputes:
            problems.note("unbekannte id", repr(unit))
            continue
        if unit in seen:
            problems.note("doppelt", unit)
            continue
        seen.add(unit)
        if record.get("codebuch_version") != codebook.version:
            problems.note(
                "andere codebuch_version",
                f"{unit}: {record.get('codebuch_version')!r} statt {codebook.version!r}",
            )
            continue
        final[unit] = _fill(codebook, record, disputes[unit], agreed[unit], problems, unit)
    for unit in sorted(set(disputes) - seen):
        problems.note("fehlt", unit)
    problems.raise_if_any(path)
    return final


def merge_project(
    settings: Settings,
    layout: Layout,
    project: str,
    *,
    model: str,
    today: dt.date,
    force: bool = False,
) -> MergeReport:
    """``georep validate merge``: zusammenführen, schlichten lassen, Labels ablegen."""
    paths = validation_paths(settings, project)
    codebook = load_codebook(paths.codebook, project)
    ids = read_sample(paths, codebook).get_column(ID).to_list()
    a = read_answers(paths.answers("A"), ids, codebook)
    b = read_answers(paths.answers("B"), ids, codebook)
    results = tuple(
        reliability(q, [a[u].values[q.id] for u in ids], [b[u].values[q.id] for u in ids])
        for q in codebook.questions
    )
    adjudicable = [q.id for q in codebook.questions if q.adjudicate]
    disputes = {
        unit: [q for q in adjudicable if a[unit].values[q] != b[unit].values[q]] for unit in ids
    }
    disputes = {unit: qs for unit, qs in disputes.items() if qs}
    count = sum(len(qs) for qs in disputes.values())
    if force:
        reset_adjudication(paths)
    # Fragen ohne Schlichtung: das gemeinsame Label, bei Uneinigkeit keines
    final: dict[str, Values] = {
        unit: {
            q: value if q in adjudicable or value == b[unit].values[q] else None
            for q, value in a[unit].values.items()
        }
        for unit in ids
    }
    if disputes:
        asked = {u: t.get("strittig") for u, t in _tasks_of(paths.tasks(ADJUDICATION)).items()}
        started = answers_started(paths.answers(ADJUDICATION))
        if asked and asked != disputes:
            if started:
                raise CodingError(
                    f"{paths.tasks(ADJUDICATION)} passt nicht mehr zu den Uneinigkeiten (A oder B "
                    "haben neu kodiert); `merge --force` setzt die Schlichtung zurück"
                )
            asked = {}
        if not asked and started == 0:
            tasks = _adjudication_tasks(paths, codebook, disputes, a, b)
            write_assignment(paths, ADJUDICATION, tasks, codebook, force=False)
            return MergeReport(results, count, len(disputes), None, paths.role(ADJUDICATION))
        if 0 <= started < len(disputes):
            return MergeReport(
                results, count, len(disputes) - started, None, paths.role(ADJUDICATION)
            )
        agreed = {u: {q: v for q, v in final[u].items() if q not in disputes[u]} for u in disputes}
        final |= read_adjudication(paths.answers(ADJUDICATION), codebook, disputes, agreed)
    write_labels(paths, codebook, ids, a, b, disputes, final)
    meta = sample_meta(paths)
    min_alpha = settings.validation.min_alpha
    write_text(
        paths.readme, readme(codebook, meta, results, len(ids), count, model, today, min_alpha)
    )
    write_json(
        paths.quality,
        {
            "vorhaben": project,
            "codebuch_version": codebook.version,
            "einheit": codebook.unit,
            "modell": model,
            "datum": today.isoformat(),
            "einheiten": len(ids),
            "uneinig": count,
            "alpha_mindestens": min_alpha,
            "fragen": {
                r.question: r.as_json() | {"alpha_genuegt": alpha_suffices(r, min_alpha)}
                for r in results
            },
            "satz": f"geprüft von zwei KI-Kodierern an {len(ids)} "
            f"{UNIT_PLURAL[codebook.unit]}, nicht von Menschen",
        },
    )
    return MergeReport(results, count, 0, paths.labels, None)


def write_labels(
    paths: ValidationPaths,
    codebook: Codebook,
    ids: Sequence[str],
    a: Mapping[str, Coding],
    b: Mapping[str, Coding],
    disputes: Mapping[str, list[str]],
    final: Mapping[str, Values],
) -> None:
    """``labels.csv``: je Einheit und gestellter Frage eine Zeile, nach id und Fragefolge."""
    rows = []
    for unit in sorted(ids):
        for question in codebook.question_ids:
            first, second, label = (
                a[unit].values[question],
                b[unit].values[question],
                final[unit][question],
            )
            if first is None and second is None and label is None:
                continue
            adjudicated = label if question in disputes.get(unit, ()) else None
            rows.append((unit, question, first or "", second or "", adjudicated or "", label or ""))
    frame = pl.DataFrame(rows, schema=list(LABEL_COLUMNS), orient="row")
    with atomic_path(paths.labels) as tmp:
        frame.write_csv(tmp)
