"""Vorab festgelegte Hypothesen: Holm über die Familie, die Wortwahl, der gemeinsame Spaltenkern.

Vier Vorhaben der Vorverarbeitung 2026-11 prüfen Thesen aus der Literatur (17 Wahlzyklus, 21
Verteilung, 24 Kontrolle in der Kooperation, 27 Mandatstyp; dazu 22 Bedarf). Ihre Hypothesen, Maße
und Tests stehen im Messdokument, **bevor** das Ergebnis gerechnet ist (Meta-Plan, § 2.11); jede
Tabelle, die sie auswertet, teilt darum denselben Kern (Synergien 2026-11, § 1), damit eine
Unterseite sie gleich zeigt und niemand das Ergebnis anders benennt:

* ``hypothese`` -- die Kennung, etwa ``H17.1`` oder ``H17.1/S1.2`` für eine Sensitivität;
* ``p`` -- der p-Wert des vorab festgelegten Tests, unkorrigiert;
* ``p_holm`` -- der nach Holm angepasste Wert, nur in der Familie der Haupttests, sonst leer;
* ``ergebnis`` -- ``bestätigt``, ``nicht bestätigt`` oder ``vorläufig``, nur in der Familie;
* ``n`` -- die Zahl der Einheiten des Tests;
* ``festgelegt`` -- der Commit, in dem die Hypothese festgelegt wurde; leer bei allem, was erst
  nach der Messung dazukam (das heißt auf der Seite „explorativ").

Was ein Vorhaben mehr braucht (Effekt, Intervall, Statistik), steht in Spalten **hinter** dem Kern.

**Holm** (1979) ist die Schwelle der Familie: nur die Haupttests eines Vorhabens bilden sie,
Sensitivitäten und explorative Zeilen bestätigen und widerlegen nichts. ``vorläufig`` heißt: Holm
hätte entschieden, aber das Maß ist noch nicht validiert (Vorhaben 17: das Lexikon vor seiner
Kodierung, Messdokument § 8.3). Rein, ohne Settings und ohne Polars-Logik außer dem Rahmen.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import deal
import polars as pl

from georep.errors import SchemaError

__all__ = [
    "ALPHA",
    "CONFIRMED",
    "CORE_SCHEMA",
    "NOT_CONFIRMED",
    "PROVISIONAL",
    "RESULTS",
    "Adjusted",
    "check_hypotheses",
    "family",
    "holm",
    "hypothesis_frame",
    "verdict",
]

CONFIRMED = "bestätigt"
NOT_CONFIRMED = "nicht bestätigt"
PROVISIONAL = "vorläufig"
RESULTS = (CONFIRMED, NOT_CONFIRMED, PROVISIONAL)
ALPHA = 0.05  # die Schwelle der Familie in allen Messdokumenten der Vorverarbeitung 2026-11

CORE_SCHEMA: dict[str, pl.DataType] = {
    "hypothese": pl.String(),
    "p": pl.Float64(),
    "p_holm": pl.Float64(),
    "ergebnis": pl.String(),
    "n": pl.Int64(),
    "festgelegt": pl.String(),
}
# Wie weit ein gespeicherter Holm-Wert von der Rechnung abweichen darf: nur Rundung
_TOLERANCE = 1e-12


@dataclass(frozen=True)
class Adjusted:
    """Ein angepasster p-Wert und ob die Hypothese in ihrer Familie fällt."""

    p_holm: float
    rejected: bool


def _p_values_and_alpha_valid(p: Mapping[str, float], alpha: float = ALPHA) -> bool:
    return bool(p) and all(0.0 <= v <= 1.0 for v in p.values()) and 0.0 < alpha < 1.0


def _holm_keeps_its_promises(
    p: Mapping[str, float], alpha: float = ALPHA, result: Mapping[str, Adjusted] | None = None
) -> bool:
    return (
        result is not None
        and list(result) == list(p)
        and all(
            p[k] <= a.p_holm <= 1.0 and (not a.rejected or p[k] <= alpha) for k, a in result.items()
        )
    )


# Benannte Validatoren vor dem Stapel: das deal-Plugin für mypy kennt keine Lambdas mit Vorgaben
# (CLAUDE.md, „Arbeitsweise", deal).
@deal.pre(
    _p_values_and_alpha_valid,
    message="p-Werte in [0, 1], mindestens einer, und 0 < alpha < 1",
)
@deal.ensure(
    _holm_keeps_its_promises,
    message="Holm: p <= p_holm <= 1, verwirft nur, was unkorrigiert fällt, Folge der Eingabe",
)
@deal.pure
def holm(p: Mapping[str, float], alpha: float = ALPHA) -> dict[str, Adjusted]:
    """Holm-Bonferroni über eine Familie: je Hypothese der angepasste Wert und ob sie fällt.

    Aufsteigend nach p (bei Gleichstand nach Kennung, damit die Folge der Eingabe nichts ändert)
    ist der angepasste Wert das laufende Maximum von ``(m - i) · p``, gekappt bei 1. Eine Hypothese
    fällt, wenn ihr angepasster Wert höchstens ``alpha`` ist; das ist gleichbedeutend mit Holms
    Schrittregel ``p_(j) <= alpha / (m - j + 1)`` für sie und alle vor ihr. Das Ergebnis steht in
    der Folge der Eingabe.
    """
    order = sorted(p, key=lambda key: (p[key], key))
    m = len(order)
    running = 0.0
    adjusted: dict[str, Adjusted] = {}
    for i, key in enumerate(order):
        running = max(running, min(1.0, (m - i) * p[key]))
        adjusted[key] = Adjusted(running, running <= alpha)
    return {key: adjusted[key] for key in p}


def verdict(adjusted: Adjusted, *, valid: bool = True) -> str:
    """Das Wort für eine Hypothese der Familie: ``vorläufig``, solange ihr Maß nicht gilt."""
    if not valid:
        return PROVISIONAL
    return CONFIRMED if adjusted.rejected else NOT_CONFIRMED


def family(
    p: Mapping[str, float], *, valid: Mapping[str, bool] | None = None, alpha: float = ALPHA
) -> dict[str, tuple[float, str]]:
    """Je Hypothese der Familie ``(p_holm, ergebnis)``; ``valid`` nennt, was noch nicht gilt.

    Holm rechnet über die ganze Familie, auch über vorläufige Hypothesen: die Familie ist vorab
    festgelegt, und eine noch nicht gültige Hypothese bleibt ihr Mitglied.
    """
    adjusted = holm(p, alpha)
    allowed = valid or {}
    return {
        key: (a.p_holm, verdict(a, valid=allowed.get(key, True))) for key, a in adjusted.items()
    }


def hypothesis_frame(
    rows: Sequence[Mapping[str, object]], extra: Mapping[str, pl.DataType] | None = None
) -> pl.DataFrame:
    """Die Zeilen als Tabelle: der Kern vorn in seiner Folge, ``extra`` dahinter."""
    schema = {**CORE_SCHEMA, **(extra or {})}
    clash = sorted(set(extra or {}) & set(CORE_SCHEMA))
    if clash:
        raise SchemaError(f"Hypothesen: Zusatzspalten tragen Namen des Kerns: {', '.join(clash)}")
    return pl.DataFrame([{name: row.get(name) for name in schema} for row in rows], schema=schema)


def _problems(frame: pl.DataFrame, alpha: float) -> list[str]:
    head = list(frame.schema.items())[: len(CORE_SCHEMA)]
    if head != list(CORE_SCHEMA.items()):
        return [f"Schema {dict(frame.schema)} beginnt nicht mit {CORE_SCHEMA}"]
    found: list[str] = []
    rows = frame.select(list(CORE_SCHEMA)).rows(named=True)
    names = [row["hypothese"] for row in rows]
    twice = sorted({name for name in names if names.count(name) > 1 and name is not None})
    if None in names or twice:
        found.append(f"Kennung leer oder doppelt: {', '.join(map(str, twice)) or 'leer'}")
    in_family: dict[str, float] = {}
    for row in rows:
        name, p, p_holm, word = row["hypothese"], row["p"], row["p_holm"], row["ergebnis"]
        if p is None or math.isnan(p) or not 0.0 <= p <= 1.0:
            found.append(f"{name}: p = {p} liegt nicht in [0, 1]")
            continue
        if row["n"] is None or row["n"] < 0 or row["festgelegt"] is None:
            found.append(f"{name}: n oder festgelegt fehlt")
        if (p_holm is None) != (word is None):
            found.append(f"{name}: p_holm und ergebnis nur zusammen, außerhalb der Familie keines")
            continue
        if p_holm is None:
            continue
        if word not in RESULTS:
            found.append(f"{name}: {word!r} ist kein Ergebnis ({', '.join(RESULTS)})")
        if not p - _TOLERANCE <= p_holm <= 1.0:
            found.append(f"{name}: p_holm = {p_holm} liegt nicht in [p, 1]")
        if word == CONFIRMED and p_holm > alpha:
            found.append(f"{name}: bestätigt, obwohl Holm nicht verwirft (p_holm = {p_holm})")
        if word == NOT_CONFIRMED and p_holm <= alpha:
            found.append(f"{name}: nicht bestätigt, obwohl Holm verwirft (p_holm = {p_holm})")
        in_family[name] = p
    if in_family and not found:
        expected = holm(in_family, alpha)
        stored = {row["hypothese"]: row["p_holm"] for row in rows if row["hypothese"] in in_family}
        off = [
            name
            for name, adjusted in expected.items()
            if abs(adjusted.p_holm - stored[name]) > _TOLERANCE
        ]
        if off:
            found.append(f"p_holm ist nicht Holm über die Familie: {', '.join(off)}")
    return found


def check_hypotheses(frame: pl.DataFrame, alpha: float = ALPHA) -> None:
    """``SchemaError``, wenn eine Hypothesentabelle den Kern verletzt; die Meldung nennt alles.

    Geprüft: der Kern vorn in Folge und Typ, Kennungen eindeutig, ``p`` in [0, 1], ``p_holm`` und
    ``ergebnis`` nur zusammen (die Familie), ``p <= p_holm <= 1``, das Wort passend zu Holm
    (``bestätigt`` genau dann, wenn Holm verwirft, außer ``vorläufig``), und ``p_holm`` ist Holm
    über die Familie, wie sie in der Tabelle steht.
    """
    found = _problems(frame, alpha)
    if found:
        raise SchemaError("Hypothesen: " + "; ".join(found))
