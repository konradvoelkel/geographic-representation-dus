"""Fremddaten je Raumeinheit zu Kontrollvariablen je Wahlbezirk.

Drei Schritte, alle rein und Frame zu Frame: ``precinct_table`` verbindet Stimmbezirksflächen mit
den Wahlberechtigten der Wahlergebnis-CSV und ist die Eingabe des Crosswalks
(``georep.crosswalk``); ``read_context_table`` liest die Tabelle der Quelle (Dezimalkomma,
Vorzeichen, Fehlwertmarker, ordinale Stufen über eine Skala) und ``aggregate_context`` mittelt sie
mit den Gewichten des Crosswalks auf die Wahlbezirke.

Nichts hier kennt die Stadt: Spalten, Skalen, Variablen und Schwellen stehen in
``settings.context`` (docs/architecture.md, „Kontextdaten"; docs/plans/03-kontrollvariablen.md).
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from pathlib import Path

import deal
import polars as pl

from georep.contracts import has_columns, sorted_unique
from georep.crosswalk import DISTRICT, ELIGIBLE, PRECINCT, UNIT, UNIT_NAME, WEIGHT
from georep.errors import EmptyResultError, SchemaError
from georep.geo import Precinct
from georep.settings import ContextSettings, ContextTable, ContextVariable, ResultsColumns


def _one_row_per_precinct(result: pl.DataFrame) -> bool:
    return sorted_unique(result, PRECINCT) and bool((result.get_column(ELIGIBLE) > 0).all())


@deal.pre(
    lambda precincts, results, columns: (
        len(precincts) > 0
        and bool(columns.precinct)
        and has_columns(results, columns.precinct, columns.district, columns.eligible)
    ),
    message="Stimmbezirke, die CSV-Spalten des Wahlergebnisses und ein Spaltenname für den Stimmbezirk",
)
@deal.post(_one_row_per_precinct, message="eine Zeile je Stimmbezirk, Wahlberechtigte positiv")
@deal.ensure(
    lambda precincts, results, columns, result: result.height <= len(precincts),
    message="höchstens so viele Zeilen wie Stimmbezirke mit Fläche",
)
@deal.raises(SchemaError)
def precinct_table(
    precincts: Sequence[Precinct], results: pl.DataFrame, columns: ResultsColumns
) -> pl.DataFrame:
    """Eine Zeile je Stimmbezirk mit Fläche: ``stimmbezirk_id``, ``wahlkreis_id``, ``wahlberechtigte``.

    Der Wahlbezirk kommt aus dem GeoJSON (es trägt die Fläche, Frage 3.7), die Wahlberechtigten aus
    der CSV. Zeilen der CSV ohne Fläche fallen weg: Briefwahlbezirke sind keine Gebiete, ihre
    Stimmen gehören zu keinem Ort. Fehlt ein Stimmbezirk der Fläche in der CSV, ist das ein
    ``SchemaError`` -- dann passen die beiden Dateien nicht zusammen.
    """
    geometry = pl.DataFrame(
        {
            PRECINCT: [p.precinct_id for p in precincts],
            DISTRICT: [p.district_id for p in precincts],
        },
        schema={PRECINCT: pl.String, DISTRICT: pl.Int64},
    )
    counts = results.select(
        pl.col(columns.precinct).str.strip_chars().alias(PRECINCT),
        pl.col(columns.eligible)
        .str.strip_chars()
        .cast(pl.Int64, strict=False)
        .fill_null(0)
        .alias(ELIGIBLE),
    )
    joined = geometry.join(counts, on=PRECINCT, how="left")
    missing = joined.filter(pl.col(ELIGIBLE).is_null()).get_column(PRECINCT).to_list()
    if missing:
        raise SchemaError(
            f"Stimmbezirke mit Fläche, aber ohne Zeile im Wahlergebnis: {sorted(missing)}"
        )
    empty = joined.filter(pl.col(ELIGIBLE) <= 0).get_column(PRECINCT).to_list()
    if empty:
        raise SchemaError(f"Stimmbezirke ohne Wahlberechtigte: {sorted(empty)}")
    return joined.sort(PRECINCT)


MISSING_SUFFIX = "_fehlgewicht"  # Anteil des Gewichts eines Wahlbezirks auf Einheiten ohne Wert


@deal.pure
@deal.pre(lambda value, scale: len(scale) > 0, message="die Skala nennt mindestens eine Stufe")
@deal.ensure(
    lambda value, scale, result: result is None or result in scale.values(),
    message="das Ergebnis ist ein Wert der Skala oder None",
)
def ordinal_score(value: str, scale: Mapping[str, int]) -> int | None:
    """Die Stufe eines ordinalen Index als Zahl; ``None``, wenn der Text keine Stufe benennt.

    Rein und darum in ``noxfile.VERIFY_TARGETS``. Aufgerufen wird sie je *verschiedener* Stufe
    einer Spalte (eine Handvoll), nicht je Zelle: ``deal.pure`` patcht prozessweit und gehört in
    keine heiße Schleife (CLAUDE.md).
    """
    return scale.get(value.strip())


def _numeric(column: str, table: ContextTable) -> pl.Expr:
    """Text der Quelle zu Float64: Dezimalkomma, Vorzeichen ``+``, Fehlwertmarker zu null."""
    cleaned = pl.col(column).str.strip_chars()
    return (
        pl.when(cleaned.is_in(list(table.missing)) | (cleaned == ""))
        .then(None)
        .otherwise(cleaned.str.strip_prefix("+").str.replace(table.decimal, ".", literal=True))
        .cast(pl.Float64, strict=False)
        .alias(column)
    )


def _ordinal(column: str, levels: dict[str, int | None]) -> pl.Expr:
    return (
        pl.col(column)
        .str.strip_chars()
        .replace_strict(levels, default=None, return_dtype=pl.Float64)
    )


def _variable_expression(
    variable: ContextVariable, frame: pl.DataFrame, context: ContextSettings
) -> pl.Expr:
    table = context.table
    if variable.kind == "ordinal":
        assert variable.scale is not None  # der Settings-Validator verlangt sie
        scale = context.scales[variable.scale]
        column = variable.columns[0]
        seen = [v for v in frame.get_column(column).unique().to_list() if v is not None]
        levels: dict[str, int | None] = {v: ordinal_score(v, scale) for v in seen}
        unknown = sorted(
            v for v, score in levels.items() if score is None and v.strip() not in table.missing
        )
        if unknown:
            raise SchemaError(
                f"{column}: Stufen ohne Eintrag in context.scales.{variable.scale}: {unknown}; "
                f"bekannt sind {sorted(scale)}"
            )
        return (_ordinal(column, levels) * variable.factor).alias(variable.name)
    numbers = [_numeric(c, table) for c in variable.columns]
    # ignore_nulls=False: fehlt ein Summand, ist die Summe unbekannt und nicht der Rest.
    total = numbers[0] if len(numbers) == 1 else pl.sum_horizontal(*numbers, ignore_nulls=False)
    return (total * variable.factor).alias(variable.name)


def _one_row_per_unit(result: pl.DataFrame) -> bool:
    return sorted_unique(result, UNIT) and result.columns[:2] == [UNIT, UNIT_NAME]


@deal.post(_one_row_per_unit, message="eine Zeile je Raumeinheit, Schlüssel und Name zuerst")
@deal.raises(SchemaError)
def read_context_table(path: Path, context: ContextSettings) -> pl.DataFrame:
    """Die Tabelle der Quelle als eine Float64-Spalte je Variable, Schlüssel und Name als Text.

    Alles wird als Text gelesen und dann umgerechnet: Dezimalkomma, das ``+`` positiver Salden,
    die Fehlwertmarker der Quelle (anonymisierte Werte unter 3, leere Einheiten) und die Stufen
    der ordinalen Spalten über ``context.scales``. Eine fehlende Spalte oder eine unbekannte Stufe
    ist ein ``SchemaError``: die Settings und die Datei passen dann nicht zusammen.
    """
    table = context.table
    text = path.read_bytes().decode(table.encoding)
    frame = pl.read_csv(io.BytesIO(text.encode("utf-8")), separator=table.sep, infer_schema=False)
    wanted = [table.key, table.name, *(c for v in context.unit_variables() for c in v.columns)]
    missing = [c for c in dict.fromkeys(wanted) if c not in frame.columns]
    if missing:
        raise SchemaError(f"{path.name}: Spalten fehlen: {missing}")
    return frame.select(
        pl.col(table.key).str.strip_chars().alias(UNIT),
        pl.col(table.name).str.strip_chars().alias(UNIT_NAME),
        *(_variable_expression(v, frame, context) for v in context.unit_variables()),
    ).sort(UNIT)


def _weighted_mean(name: str) -> list[pl.Expr]:
    """Mittel über die Einheiten mit Wert und das Gewicht der Einheiten ohne.

    Liegt das ganze Gewicht auf Einheiten ohne Wert, ist das Mittel ``null`` und nicht ``NaN``:
    unbekannt ist kein Zahlenwert, und NaN stünde sonst in Parquet und auf der Seite.
    """
    present = pl.col(name).is_not_null()
    weight = pl.col(WEIGHT)
    known = weight.filter(present).sum()
    return [
        pl.when(known > 0)
        .then((pl.col(name) * weight).filter(present).sum() / known)
        .otherwise(None)
        .alias(name),
        weight.filter(~present).sum().alias(f"{name}{MISSING_SUFFIX}"),
    ]


def _scores_within_their_scale(
    weights: pl.DataFrame,
    values: pl.DataFrame,
    context: ContextSettings,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    for variable in context.unit_variables():
        if variable.scale is None:
            continue
        scale = context.scales[variable.scale]
        low, high = min(scale.values()) * variable.factor, max(scale.values()) * variable.factor
        column = result.get_column(variable.name).drop_nulls()
        if column.len() and not bool(((column >= low) & (column <= high)).all()):
            return False
    return True


@deal.pre(
    lambda weights, values, context: (
        has_columns(weights, DISTRICT, UNIT, WEIGHT)
        and has_columns(values, UNIT, *(v.name for v in context.unit_variables()))
    ),
    message="Gewichte je Wahlbezirk und Einheit, Werte je Einheit",
)
@deal.post(lambda result: sorted_unique(result, DISTRICT), message="eine Zeile je Wahlbezirk")
@deal.ensure(
    lambda weights, values, context, result: (
        set(result.get_column(DISTRICT)) == set(weights.get_column(DISTRICT))
    ),
    message="genau die Wahlbezirke der Gewichte",
)
@deal.ensure(_scores_within_their_scale, message="ordinale Mittel liegen in ihrer Skala")
@deal.raises(EmptyResultError)
def aggregate_context(
    weights: pl.DataFrame, values: pl.DataFrame, context: ContextSettings
) -> pl.DataFrame:
    """Gewichtetes Mittel je Wahlbezirk, plus je Variable den Anteil des Gewichts ohne Wert.

    Einheiten ohne Wert fallen aus dem Mittel heraus, und die übrigen Gewichte werden renormiert;
    stilles Auffüllen mit 0 verfälschte Anteile. Liegt mehr als ``context.max_missing_weight`` des
    Gewichts eines Wahlbezirks auf Einheiten ohne Wert, ist das Mittel nichts wert:
    ``EmptyResultError`` mit Variable und Wahlbezirk.
    """
    names = [v.name for v in context.unit_variables()]
    joined = weights.join(values.select(UNIT, *names), on=UNIT, how="left")
    frame = (
        joined.group_by(DISTRICT)
        .agg(*(expr for name in names for expr in _weighted_mean(name)))
        .sort(DISTRICT)
    )
    for name in names:
        too_much = frame.filter(pl.col(f"{name}{MISSING_SUFFIX}") > context.max_missing_weight)
        if not too_much.is_empty():
            worst = too_much.sort(f"{name}{MISSING_SUFFIX}", descending=True).row(0, named=True)
            raise EmptyResultError(
                f"Variable {name!r}: in Wahlbezirk {worst[DISTRICT]} liegen "
                f"{worst[f'{name}{MISSING_SUFFIX}']:.3f} des Gewichts auf Einheiten ohne Wert "
                f"(erlaubt {context.max_missing_weight}); context.max_missing_weight anheben "
                "oder die Variable streichen"
            )
    return frame.select(DISTRICT, *names, *(f"{n}{MISSING_SUFFIX}" for n in names))


@deal.pre(
    lambda voters, context: has_columns(voters, DISTRICT),
    message="die Wählertabelle mit dem Wahlbezirk",
)
@deal.post(lambda result: sorted_unique(result, DISTRICT))
@deal.raises(SchemaError)
def district_variables(voters: pl.DataFrame, context: ContextSettings) -> pl.DataFrame:
    """Variablen, die schon je Wahlbezirk vorliegen (Stimmenanteile), mit ihrem Faktor skaliert."""
    variables = context.district_variables()
    missing = [c for v in variables for c in v.columns if c not in voters.columns]
    if missing:
        raise SchemaError(f"Wählertabelle: Spalten der Kontrollvariablen fehlen: {missing}")
    return voters.select(
        pl.col(DISTRICT),
        *((pl.col(v.columns[0]) * v.factor).alias(v.name) for v in variables),
    ).sort(DISTRICT)
