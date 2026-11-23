"""Spannen nach Fundament F3 (docs/plan-vorverarbeitung-2026-11.md, § 7)."""

from __future__ import annotations

import polars as pl
import pytest

from georep.errors import SchemaError
from georep.spans import SPAN_SCHEMA, check_spans, empty_spans, sort_spans

TEXTS = {"a": "Betreff: Radweg an der Benrather Straße", "b": "12.345,67 €"}


def _spans(rows: list[tuple[str, int, int, str]]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "id": i,
                "start": s,
                "end": e,
                "kind": k,
                "value": TEXTS[i][s:e] if i in TEXTS else "",
                "norm": "",
                "section": "",
                "extractor": "probe",
            }
            for i, s, e, k in rows
        ],
        schema=SPAN_SCHEMA,
    )


LENGTHS = {key: len(text) for key, text in TEXTS.items()}


def test_gueltige_spannen_bestehen() -> None:
    check_spans(sort_spans(_spans([("b", 0, 9, "betrag"), ("a", 9, 15, "abschnitt")])), LENGTHS)


def test_leere_tabelle_besteht() -> None:
    check_spans(empty_spans(), LENGTHS)


@pytest.mark.parametrize(
    ("row", "match"),
    [
        (("a", 5, 5, "abschnitt"), "erste Zeile 0"),  # leer
        (("a", -1, 3, "abschnitt"), "start=-1"),
        (("b", 0, 99, "betrag"), "Textlänge=11"),  # über das Ende
        (("x", 0, 1, "betrag"), "id='x'"),  # unbekanntes Dokument
        (("a", 0, 3, ""), "kind=''"),
    ],
)
def test_eine_spanne_ausserhalb_ihres_texts_wird_benannt(
    row: tuple[str, int, int, str], match: str
) -> None:
    with pytest.raises(SchemaError, match=match):
        check_spans(_spans([row]), LENGTHS)


def test_unsortierte_spannen_sind_ein_fehler() -> None:
    with pytest.raises(SchemaError, match="sortiert"):
        check_spans(_spans([("b", 0, 9, "betrag"), ("a", 9, 15, "abschnitt")]), LENGTHS)


def test_ein_falscher_typ_ist_ein_fehler() -> None:
    frame = sort_spans(_spans([("a", 0, 3, "abschnitt")])).with_columns(
        pl.col("start").cast(pl.Int32)
    )
    with pytest.raises(SchemaError, match="Schema"):
        check_spans(frame, LENGTHS)
