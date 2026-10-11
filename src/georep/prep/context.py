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

from collections.abc import Sequence

import deal
import polars as pl

from georep.contracts import has_columns, sorted_unique
from georep.crosswalk import DISTRICT, ELIGIBLE, PRECINCT
from georep.errors import SchemaError
from georep.geo import Precinct
from georep.settings import ResultsColumns


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
