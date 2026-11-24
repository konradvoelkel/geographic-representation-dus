"""Vorab festgelegte Hypothesen: Holm über die Familie, die Wortwahl, der gemeinsame Spaltenkern.

Vier Vorhaben der Vorverarbeitung 2026-11 prüfen Thesen aus der Literatur (17 Wahlzyklus, 21
Verteilung, 24 Kontrolle in der Kooperation, 27 Mandatstyp; dazu 22 Bedarf). Ihre Hypothesen, Maße
und Tests stehen im Messdokument, **bevor** das Ergebnis gerechnet ist (Meta-Plan, § 2.11); jede
Tabelle, die sie auswertet, teilt darum denselben Kern (Synergien 2026-11, § 1), damit eine
Unterseite sie gleich zeigt und niemand das Ergebnis anders benennt:

* ``hypothese`` -- die Kennung, etwa ``H17.1`` oder ``H17.1/S1.2`` für eine Sensitivität;
* ``p`` -- der p-Wert des Tests, unkorrigiert;
* ``p_holm`` -- der nach Holm angepasste Wert, nur in der Familie, sonst leer;
* ``ergebnis`` -- ``bestätigt``, ``nicht bestätigt`` oder ``vorläufig``, nur in der Familie;
* ``n`` -- die Zahl der Einheiten des Tests;
* ``festgelegt`` -- der Commit, in dem die Hypothese festgelegt wurde.

**Die Familie sind die Zeilen mit ``p_holm``** (Review K2, 2026-11-24): die vorab festgelegten
Haupttests eines Vorhabens. Für sie sind Kennung, ``p`` in [0, 1], ``n``, ``festgelegt`` und
``ergebnis`` Pflicht, die Kennungen sind in der Familie eindeutig, und ``p_holm`` und ``ergebnis``
müssen Holm über die Familie sein, wie sie in der Tabelle steht. Außerhalb der Familie --
Sensitivität, Robustheit, explorativ, beschreibend -- bestätigt und widerlegt eine Zeile nichts:
``p_holm`` und ``ergebnis`` sind leer, ``p``, ``n``, ``festgelegt`` und sogar die Kennung dürfen es
sein (ein ``p``, das dasteht, liegt in [0, 1]). Eindeutig ist eine Zeile über einen Schlüssel, den
der Aufrufer nennt (Vorgabe: die Kennung allein; 22 trägt je Hypothese mehrere Rechnungen).

Was ein Vorhaben mehr braucht (Effekt, Intervall, Statistik, Rolle), steht in Spalten **hinter**
dem Kern.

**Holm** (1979) ist die Schwelle der Familie, bei ``alpha``; ob ``p_holm`` gleich ``alpha`` noch
verwirft, legt jede Festlegung selbst fest (17: ``<=``, Vorgabe; 22: ``<``, ``strict=True``).
``vorläufig`` heißt: Holm hätte entschieden, aber das Maß ist noch nicht validiert (Vorhaben 17: das
Lexikon vor seiner Kodierung, Messdokument § 8.3). Rein, ohne Settings und ohne Polars-Logik außer
dem Rahmen.
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


def _p_values_and_alpha_valid(
    p: Mapping[str, float], alpha: float = ALPHA, *, strict: bool = False
) -> bool:
    return bool(p) and all(0.0 <= v <= 1.0 for v in p.values()) and 0.0 < alpha < 1.0


def _holm_keeps_its_promises(
    p: Mapping[str, float],
    alpha: float = ALPHA,
    *,
    strict: bool = False,
    result: Mapping[str, Adjusted] | None = None,
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
def holm(
    p: Mapping[str, float], alpha: float = ALPHA, *, strict: bool = False
) -> dict[str, Adjusted]:
    """Holm-Bonferroni über eine Familie: je Hypothese der angepasste Wert und ob sie fällt.

    Aufsteigend nach p (bei Gleichstand nach Kennung, damit die Folge der Eingabe nichts ändert)
    ist der angepasste Wert das laufende Maximum von ``(m - i) · p``, gekappt bei 1. Eine Hypothese
    fällt, wenn ihr angepasster Wert höchstens ``alpha`` ist (mit ``strict`` kleiner als
    ``alpha``); das ist gleichbedeutend mit Holms Schrittregel ``p_(j) <= alpha / (m - j + 1)`` für
    sie und alle vor ihr. Das Ergebnis steht in der Folge der Eingabe.
    """
    order = sorted(p, key=lambda key: (p[key], key))
    m = len(order)
    running = 0.0
    adjusted: dict[str, Adjusted] = {}
    for i, key in enumerate(order):
        running = max(running, min(1.0, (m - i) * p[key]))
        adjusted[key] = Adjusted(running, running < alpha if strict else running <= alpha)
    return {key: adjusted[key] for key in p}


def verdict(adjusted: Adjusted, *, valid: bool = True) -> str:
    """Das Wort für eine Hypothese der Familie: ``vorläufig``, solange ihr Maß nicht gilt."""
    if not valid:
        return PROVISIONAL
    return CONFIRMED if adjusted.rejected else NOT_CONFIRMED


def family(
    p: Mapping[str, float],
    *,
    valid: Mapping[str, bool] | None = None,
    alpha: float = ALPHA,
    strict: bool = False,
) -> dict[str, tuple[float, str]]:
    """Je Hypothese der Familie ``(p_holm, ergebnis)``; ``valid`` nennt, was noch nicht gilt.

    Holm rechnet über die ganze Familie, auch über vorläufige Hypothesen: die Familie ist vorab
    festgelegt, und eine noch nicht gültige Hypothese bleibt ihr Mitglied.
    """
    adjusted = holm(p, alpha, strict=strict)
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


def _problems(frame: pl.DataFrame, alpha: float, key: Sequence[str], strict: bool) -> list[str]:
    head = list(frame.schema.items())[: len(CORE_SCHEMA)]
    if head != list(CORE_SCHEMA.items()):
        return [f"Schema {dict(frame.schema)} beginnt nicht mit {CORE_SCHEMA}"]
    unknown = [name for name in key if name not in frame.columns]
    if not key or unknown:
        return [f"Schlüssel {list(key)} nennt keine oder fremde Spalten: {unknown}"]
    found: list[str] = []
    twice = frame.filter(pl.struct(list(key)).is_duplicated()).select(list(key)).unique()
    if twice.height:
        found.append(f"Schlüssel {list(key)} doppelt: {twice.rows()[:3]}")
    rows = frame.select(list(CORE_SCHEMA)).rows(named=True)
    in_family: dict[str, float] = {}
    stored: dict[str, tuple[float, str]] = {}
    for row in rows:
        name, p, p_holm, word = row["hypothese"], row["p"], row["p_holm"], row["ergebnis"]
        if p is not None and (math.isnan(p) or not 0.0 <= p <= 1.0):
            found.append(f"{name}: p = {p} liegt nicht in [0, 1]")
            continue
        if row["n"] is not None and row["n"] < 0:
            found.append(f"{name}: n = {row['n']} ist negativ")
        if (p_holm is None) != (word is None):
            found.append(f"{name}: p_holm und ergebnis nur zusammen, außerhalb der Familie keines")
            continue
        if p_holm is None:
            continue
        # die Familie: Kennung, p, n, festgelegt und ein Wort sind Pflicht
        if name is None or p is None:
            found.append(f"{name}: in der Familie ohne Kennung, oder p fehlt")
            continue
        if row["n"] is None or row["festgelegt"] is None:
            found.append(f"{name}: in der Familie fehlt n oder festgelegt")
        if name in in_family:
            found.append(f"{name}: zweimal in der Familie")
        if word not in RESULTS:
            found.append(f"{name}: {word!r} ist kein Ergebnis ({', '.join(RESULTS)})")
        if not p - _TOLERANCE <= p_holm <= 1.0:
            found.append(f"{name}: p_holm = {p_holm} liegt nicht in [p, 1]")
        in_family[name] = p
        stored[name] = (p_holm, word)
    if in_family and not found:
        for name, adjusted in holm(in_family, alpha, strict=strict).items():
            p_holm, word = stored[name]
            if abs(adjusted.p_holm - p_holm) > _TOLERANCE:
                found.append(f"{name}: p_holm = {p_holm} ist nicht Holm über die Familie")
            if word == CONFIRMED and not adjusted.rejected:
                found.append(f"{name}: bestätigt, obwohl Holm nicht verwirft (p_holm = {p_holm})")
            if word == NOT_CONFIRMED and adjusted.rejected:
                found.append(f"{name}: nicht bestätigt, obwohl Holm verwirft (p_holm = {p_holm})")
    return found


def check_hypotheses(
    frame: pl.DataFrame,
    alpha: float = ALPHA,
    *,
    key: Sequence[str] = ("hypothese",),
    strict: bool = False,
) -> None:
    """``SchemaError``, wenn eine Hypothesentabelle den Kern verletzt; die Meldung nennt alles.

    Geprüft: der Kern vorn in Folge und Typ; jede Zeile eindeutig über ``key``; ein ``p``, das
    dasteht, in [0, 1]; ``p_holm`` und ``ergebnis`` nur zusammen. Die Zeilen mit ``p_holm`` sind
    die Familie: dort sind Kennung, ``p``, ``n`` und ``festgelegt`` Pflicht, jede Kennung kommt
    einmal vor, ``p <= p_holm <= 1``, ``p_holm`` ist Holm über die Familie, wie sie in der Tabelle
    steht, und das Wort passt zu Holm bei ``alpha`` (``bestätigt`` genau dann, wenn Holm verwirft,
    außer ``vorläufig``; ``strict`` verlangt ``p_holm < alpha`` statt ``<=``).
    """
    found = _problems(frame, alpha, key, strict)
    if found:
        raise SchemaError("Hypothesen: " + "; ".join(found))
