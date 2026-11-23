"""Zwei Kodierungen zusammenführen, Uneinigkeiten schlichten lassen, Labels ablegen (F4).

``georep validate merge <vorhaben> --model <name>`` liest die Antworten von A und B. Sind beide
vollständig, gibt es zwei Ausgänge:

1. Es gibt Uneinigkeiten, und die Schlichtung ist noch nicht vollständig: der Auftrag des
   Schlicht-Agenten entsteht unter ``<coding_root>/<vorhaben>/schlichtung/`` (nur die strittigen
   Einheiten, mit beiden Labels und Begründungen) samt leerer Antwortdatei. Begonnene Antworten
   der Schlichtung bleiben stehen; der Befehl sagt, wie viele noch offen sind.
2. Es gibt keine Uneinigkeit, oder die Schlichtung ist vollständig: ``labels.csv`` (``id``,
   ``kodierer_a``, ``kodierer_b``, ``schlichtung``, ``label``), ``README.md`` (Codebuch-Version,
   Modell, Datum, Stichprobe, Übereinstimmung) und ``guete.json`` mit der Übereinstimmung
   entstehen im Ordner des Vorhabens im Repo. Begründungen bleiben lokal: sie dürfen Text zitieren.

Eine Antwortdatei ist nur brauchbar, wenn sie jede Einheit genau einmal mit einem Label aus dem
Codebuch trägt; sonst nennt ein ``CodingError`` Zahl und Beispiele.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from georep.errors import MissingInputError
from georep.io import atomic_path, write_json, write_text
from georep.layout import Layout
from georep.settings import Settings
from georep.validation import CodingError
from georep.validation.codebook import Codebook, load_codebook
from georep.validation.measures import agreement, cohen_kappa, krippendorff_alpha, wilson_interval
from georep.validation.paths import ADJUDICATION, ValidationPaths, validation_paths
from georep.validation.sample import ID, read_sample, sample_meta
from georep.validation.tasks import answers_started, write_assignment

LABEL_COLUMNS = ("id", "kodierer_a", "kodierer_b", "schlichtung", "label")
# Wie die Seite eine Einheit im Plural nennt: „geprüft von zwei KI-Kodierern an n …".
UNIT_PLURAL = {
    "document": "Dokumenten",
    "document_pair": "Dokumentpaaren",
    "span": "Textstellen",
    "query_document": "Paaren aus Suchanfrage und Dokument",
}


@dataclass(frozen=True)
class Answer:
    id: str
    label: str
    reason: str


def read_answers(path: Path, ids: Sequence[str], labels: Sequence[str]) -> dict[str, Answer]:
    """Eine vollständige Antwortdatei: jede Einheit genau einmal, jedes Label aus dem Codebuch."""
    if not path.is_file():
        raise MissingInputError(f"{path} fehlt; `georep validate tasks` schreibt sie")
    expected = set(ids)
    found: dict[str, Answer] = {}
    problems: dict[str, list[str]] = {}

    def note(kind: str, what: str) -> None:
        problems.setdefault(kind, []).append(what)

    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            note("kein JSON", f"Zeile {number}")
            continue
        unit = record.get("id") if isinstance(record, dict) else None
        if not isinstance(unit, str) or unit not in expected:
            note("unbekannte id", repr(unit))
            continue
        if unit in found:
            note("doppelt", unit)
            continue
        label = record.get("label")
        if label is None:
            note("ohne Label", unit)
            continue
        if label not in labels:
            note("Label nicht im Codebuch", f"{unit}: {label!r}")
            continue
        reason = record.get("begruendung")
        found[unit] = Answer(unit, label, reason if isinstance(reason, str) else "")
    missing = sorted(expected - set(found) - set(problems.get("ohne Label", ())))
    if missing:
        problems["fehlt"] = missing
    if problems:
        summary = "; ".join(
            f"{kind} {len(items)} (etwa {items[0]})" for kind, items in sorted(problems.items())
        )
        raise CodingError(f"{path}: nicht vollständig: {summary}")
    return found


@dataclass(frozen=True)
class Reliability:
    """Übereinstimmung der beiden Kodierer über die Stichprobe."""

    n: int
    agreed: int
    share: float
    interval: tuple[float, float]
    kappa: float | None
    alpha_nominal: float | None
    alpha_ordinal: float | None  # nur bei ordinaler Skala

    def alpha(self) -> float | None:
        """Das α, an dem Stufe 3 gemessen wird: ordinal bei ordinaler Skala, sonst nominal."""
        return self.alpha_ordinal if self.alpha_ordinal is not None else self.alpha_nominal

    def as_json(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "einig": self.agreed,
            "anteil": self.share,
            "anteil_wilson95": list(self.interval),
            "cohen_kappa": self.kappa,
            "krippendorff_alpha_nominal": self.alpha_nominal,
            "krippendorff_alpha_ordinal": self.alpha_ordinal,
        }


def reliability(first: Sequence[str], second: Sequence[str], codebook: Codebook) -> Reliability:
    units = list(zip(first, second, strict=True))
    share = agreement(first, second)
    assert share is not None  # Vorbedingung: mindestens eine Einheit (die Stichprobe ist nie leer)
    agreed = sum(1 for a, b in units if a == b)
    return Reliability(
        n=len(units),
        agreed=agreed,
        share=share,
        interval=wilson_interval(agreed, len(units)),
        kappa=cohen_kappa(first, second),
        alpha_nominal=krippendorff_alpha(units, "nominal", codebook.labels),
        alpha_ordinal=krippendorff_alpha(units, "ordinal", codebook.labels)
        if codebook.scale == "ordinal"
        else None,
    )


def format_number(value: float | None, digits: int = 3) -> str:
    return "nicht definiert" if value is None else f"{value:.{digits}f}".replace(".", ",")


def format_percent(value: float) -> str:
    return f"{100 * value:.1f}".replace(".", ",") + " %"


def readme(
    codebook: Codebook,
    meta: dict[str, Any],
    result: Reliability,
    disputed: int,
    model: str,
    today: dt.date,
    min_alpha: float,
) -> str:
    alpha = result.alpha()
    verdict = (
        "nicht definiert"
        if alpha is None
        else ("erfüllt" if alpha >= min_alpha else "nicht erfüllt: das Codebuch ist zu unscharf")
    )
    stratum = meta.get("schicht") or ""
    alpha_line = f"Krippendorffs α nominal {format_number(result.alpha_nominal)}"
    if result.alpha_ordinal is not None:
        alpha_line += f", ordinal {format_number(result.alpha_ordinal)}"
    return "\n".join(
        [
            f"# Validierung {codebook.project}",
            "",
            f"Erzeugt von `georep validate merge` am {today.isoformat()}; nicht von Hand ändern. "
            "Der Ablauf steht in [docs/validierung.md](../../docs/validierung.md).",
            "",
            f"- **Codebuch**: `codebuch.toml`, Version {codebook.version}; Einheit "
            f"`{codebook.unit}`, Skala `{codebook.scale}`, Optionen "
            + ", ".join(f"`{label}`" for label in codebook.labels)
            + ".",
            f"- **Stichprobe**: {result.n} Einheiten aus Profil `{meta.get('profil')}`, "
            + (f"geschichtet nach `{stratum}`, " if stratum else "ungeschichtet, ")
            + f"Seed {meta.get('seed')}, gezogen am {meta.get('gezogen')} "
            "(`stichprobe.csv`, `stichprobe.json`).",
            f"- **Kodierer**: zwei KI-Kodierer, Modell `{model}`, unabhängig voneinander und ohne "
            "die Ausgabe des geprüften Verfahrens; die "
            f"{disputed} Uneinigkeiten entschied ein dritter Agent (Schlichtung). **Kein "
            "menschlicher Goldstandard**: die Labels messen Übereinstimmung mit einem "
            "stärkeren Modell, nicht mit Menschen.",
            f"- **Datum**: {today.isoformat()}.",
            f"- **Übereinstimmung A–B**: {format_percent(result.share)} der Einheiten (Wilson 95 %: "
            f"{format_percent(result.interval[0])} bis {format_percent(result.interval[1])}), Cohens κ "
            f"{format_number(result.kappa)}, {alpha_line}. Stufe 3 verlangt α ≥ {format_number(min_alpha, 1)}: "
            f"{verdict}.",
            "",
            "## labels.csv",
            "",
            "| Spalte | Inhalt |",
            "|---|---|",
            "| `id` | Schlüssel der Einheit; bei `document` die Dokument-ID, sonst die Teile mit `|` "
            "verbunden (`stichprobe.csv` trägt sie einzeln) |",
            "| `kodierer_a` | Label von Kodierer A |",
            "| `kodierer_b` | Label von Kodierer B |",
            "| `schlichtung` | Label der Schlichtung; leer, wo A und B einig waren |",
            "| `label` | das Endlabel: das gemeinsame, sonst das der Schlichtung |",
            "",
        ]
    )


@dataclass(frozen=True)
class MergeReport:
    reliability: Reliability
    disputed: int
    open: int  # Einheiten, die die Schlichtung noch nicht entschieden hat
    labels: Path | None  # None, solange die Schlichtung offen ist
    adjudication: Path | None

    def lines(self) -> list[str]:
        r = self.reliability
        head = (
            f"{r.n} Einheiten, einig {r.agreed} ({format_percent(r.share)}), κ {format_number(r.kappa)}, "
            f"α nominal {format_number(r.alpha_nominal)}"
            + (f", ordinal {format_number(r.alpha_ordinal)}" if r.alpha_ordinal is not None else "")
            + f"; {self.disputed} Uneinigkeiten"
        )
        if self.labels is not None:
            return [head, f"Labels -> {self.labels}"]
        return [head, f"Schlichtung offen: {self.open} von {self.disputed} -> {self.adjudication}"]


def _adjudication_tasks(
    paths: ValidationPaths, disputed: Sequence[str], a: dict[str, Answer], b: dict[str, Answer]
) -> list[dict[str, Any]]:
    """Die strittigen Einheiten aus dem Auftrag von A, mit beiden Kodierungen."""
    tasks = {}
    for line in paths.tasks("A").read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            tasks[record["id"]] = record
    missing = [unit for unit in disputed if unit not in tasks]
    if missing:
        raise CodingError(
            f"{paths.tasks('A')} kennt {len(missing)} Einheiten nicht, etwa {missing[0]!r}"
        )
    return [
        tasks[unit]
        | {
            "kodierung_1": {"label": a[unit].label, "begruendung": a[unit].reason},
            "kodierung_2": {"label": b[unit].label, "begruendung": b[unit].reason},
            "antwort": None,
        }
        for unit in disputed
    ]


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
    a = read_answers(paths.answers("A"), ids, codebook.labels)
    b = read_answers(paths.answers("B"), ids, codebook.labels)
    result = reliability([a[u].label for u in ids], [b[u].label for u in ids], codebook)
    disputed = [unit for unit in ids if a[unit].label != b[unit].label]
    decided: dict[str, Answer] = {}
    if disputed:
        started = answers_started(paths.answers(ADJUDICATION))
        if (
            started >= len(disputed) or started < 0
        ):  # vollständig, oder kaputt: read_answers sagt was
            decided = read_answers(paths.answers(ADJUDICATION), disputed, codebook.labels)
        else:
            if started == 0:
                tasks = _adjudication_tasks(paths, disputed, a, b)
                write_assignment(paths, ADJUDICATION, tasks, codebook, force=False)
            return MergeReport(
                result,
                len(disputed),
                len(disputed) - max(started, 0),
                None,
                paths.role(ADJUDICATION),
            )
    if paths.labels.exists() and not force:
        raise CodingError(f"{paths.labels} gibt es schon; --force schreibt die Labels neu")
    frame = pl.DataFrame(
        {
            "id": ids,
            "kodierer_a": [a[u].label for u in ids],
            "kodierer_b": [b[u].label for u in ids],
            "schlichtung": [decided[u].label if u in decided else "" for u in ids],
            "label": [decided[u].label if u in decided else a[u].label for u in ids],
        }
    ).sort("id")
    with atomic_path(paths.labels) as tmp:
        frame.write_csv(tmp)
    meta = sample_meta(paths)
    min_alpha = settings.validation.min_alpha
    write_text(paths.readme, readme(codebook, meta, result, len(disputed), model, today, min_alpha))
    write_json(
        paths.quality,
        {
            "vorhaben": project,
            "codebuch_version": codebook.version,
            "einheit": codebook.unit,
            "skala": codebook.scale,
            "modell": model,
            "datum": today.isoformat(),
            "uneinig": len(disputed),
            "uebereinstimmung": result.as_json(),
            "alpha_mindestens": min_alpha,
            "alpha_genuegt": (result.alpha() or 0.0) >= min_alpha,
            "satz": f"geprüft von zwei KI-Kodierern an {result.n} "
            f"{UNIT_PLURAL[codebook.unit]}, nicht von Menschen",
        },
    )
    return MergeReport(result, len(disputed), 0, paths.labels, None)
