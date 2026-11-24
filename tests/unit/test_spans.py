"""Spannen nach Fundament F3 (docs/plan-vorverarbeitung-2026-11.md, § 7)."""

from __future__ import annotations

import polars as pl
import pytest

from georep.errors import SchemaError
from georep.spans import SPAN_SCHEMA, check_spans, empty_spans, read_span, section_of, sort_spans

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


# --- Nachzug F3: Zusatzspalten hinter den acht (Synergien 2026-11, Konflikt 3) ------------------


def test_eine_zusatzspalte_hinter_den_acht_besteht() -> None:
    """Vorhaben 12 trägt ``attr`` (die Form eines Betrags); F3 prüft die acht, nicht mehr."""
    spans = _spans([("b", 0, 9, "betrag"), ("a", 9, 15, "abschnitt")]).with_columns(
        attr=pl.Series(["dezimal", "kopf"])
    )
    checked = sort_spans(spans)
    check_spans(checked, LENGTHS)
    assert checked.columns == [*SPAN_SCHEMA, "attr"]
    assert checked.select("id", "attr").rows() == [("a", "kopf"), ("b", "dezimal")]


def test_sort_spans_stellt_zusatzspalten_hinter_die_acht() -> None:
    spans = _spans([("a", 0, 3, "abschnitt")]).with_columns(
        attr=pl.lit("x"), zeile=pl.lit(1, dtype=pl.UInt32)
    )
    front = ["attr", "extractor", "id", "zeile"]
    shuffled = spans.select(*front, *(name for name in SPAN_SCHEMA if name not in front))
    assert sort_spans(shuffled).columns == [*SPAN_SCHEMA, "attr", "zeile"]


def test_eine_zusatzspalte_darf_leer_sein() -> None:
    """Was eine Zusatzspalte bedeutet, weiß ihr Vorhaben; null ist dort kein Schemafehler."""
    spans = _spans([("a", 0, 3, "abschnitt")]).with_columns(attr=pl.lit(None, dtype=pl.String))
    checked = sort_spans(spans)
    check_spans(checked, LENGTHS)
    assert "attr" in checked.columns


def test_eine_zusatzspalte_darf_wie_eine_hilfsspalte_der_pruefung_heissen() -> None:
    """``check_spans`` nummeriert die Zeilen (``zeile``) und joint die Längen (``length``)."""
    spans = _spans([("a", 0, 3, "abschnitt")]).with_columns(
        zeile=pl.lit(7, dtype=pl.UInt32), length=pl.lit(-1)
    )
    checked = sort_spans(spans)
    check_spans(checked, LENGTHS)
    assert checked.columns[-2:] == ["zeile", "length"]


def test_eine_spalte_zwischen_den_acht_ist_ein_fehler() -> None:
    spans = _spans([("a", 0, 3, "abschnitt")]).with_columns(attr=pl.lit("x"))
    between = spans.select("id", "start", "attr", *list(SPAN_SCHEMA)[2:])
    with pytest.raises(SchemaError, match="Schema"):
        check_spans(between, LENGTHS)


def test_eine_fehlende_spalte_der_acht_ist_ein_fehler() -> None:
    spans = sort_spans(_spans([("a", 0, 3, "abschnitt")])).drop("norm")
    with pytest.raises(SchemaError, match="Schema"):
        check_spans(spans, LENGTHS)


def test_die_acht_in_anderer_folge_sind_ein_schemafehler() -> None:
    """Review F7, K1: die Folge der acht ist Teil des Schemas, nicht nur die Menge."""
    spans = sort_spans(_spans([("a", 0, 3, "abschnitt")]))
    swapped = spans.select("id", "end", "start", *list(SPAN_SCHEMA)[3:])
    with pytest.raises(SchemaError, match="Schema"):
        check_spans(swapped, LENGTHS)


@pytest.mark.parametrize("column", ["norm", "section", "value", "extractor"])
def test_ein_nullwert_in_den_acht_ist_ein_fehler(column: str) -> None:
    """Review F7, K2: ``norm`` und ``section`` sind leere Zeichenketten, nie null."""
    spans = sort_spans(_spans([("a", 0, 3, "abschnitt")])).with_columns(
        pl.lit(None, dtype=pl.String).alias(column)
    )
    with pytest.raises(SchemaError, match="leere Werte"):
        check_spans(spans, LENGTHS)


def test_eine_leere_tabelle_mit_zusatzspalten() -> None:
    """Review F7, N3: ein Vorhaben ohne Treffer schreibt dasselbe Schema wie eines mit."""
    empty = empty_spans({"attr": pl.String(), "zeile": pl.UInt32()})
    assert dict(empty.schema) == {**SPAN_SCHEMA, "attr": pl.String(), "zeile": pl.UInt32()}
    assert list(empty.columns) == [*SPAN_SCHEMA, "attr", "zeile"]
    check_spans(empty, LENGTHS)
    assert empty_spans().columns == list(SPAN_SCHEMA)


def test_eine_zusatzspalte_darf_keine_der_acht_ueberschreiben() -> None:
    with pytest.raises(SchemaError, match="norm"):
        empty_spans({"norm": pl.Int64()})


# --- Vorhaben 11: section_of und read_span (docs/plans/11-struktur.md, § 10, Punkt 3) -------------


def _section(doc: str, start: int, end: int, norm: str, section: str) -> dict[str, object]:
    return {
        "id": doc,
        "start": start,
        "end": end,
        "kind": "abschnitt",
        "value": "",
        "norm": norm,
        "section": section,
        "extractor": "struktur-1",
    }


def test_section_of_names_the_level_one_section_of_each_span() -> None:
    """Ebene 1 ist ``section == norm``; Finanzen (Ebene 2) im Beschlussvorschlag bestimmt nichts."""
    sections = sort_spans(
        pl.DataFrame(
            [
                _section("a", 0, 9, "betreff", "betreff"),
                _section("a", 10, 30, "beschlussvorschlag", "beschlussvorschlag"),
                _section("a", 20, 30, "finanzen", "beschlussvorschlag"),
                _section("b", 0, 5, "rumpf", "rumpf"),
            ],
            schema=SPAN_SCHEMA,
        )
    )
    spans = sort_spans(
        _spans([("a", 0, 3, "x"), ("a", 9, 10, "x"), ("a", 25, 27, "x"), ("b", 4, 6, "x")])
    )
    found = section_of(spans, sections)
    assert found["section"].to_list() == ["betreff", "", "beschlussvorschlag", "rumpf"]
    assert found.drop("section").equals(spans.drop("section"))


def test_section_of_keeps_extra_columns_and_an_id_without_sections() -> None:
    spans = sort_spans(_spans([("c", 0, 1, "x")])).with_columns(pl.lit("form").alias("attr"))
    empty = empty_spans()
    found = section_of(spans, empty)
    assert found.columns == [*SPAN_SCHEMA, "attr"]
    assert found["section"].to_list() == [""]


def test_read_span_skips_page_headers_but_keeps_the_offsets_raw() -> None:
    text = "Der Rat beschließt:\fSeite 2\n  Sitzung des APS am 01.02.2024  \n1. den Plan"
    noise = [r"Seite \d+", r"Sitzung des .{1,40} am \d{2}\.\d{2}\.\d{4}"]
    assert read_span(text, 0, len(text), noise) == "Der Rat beschließt:\n1. den Plan"
    assert read_span(text, 4, 7, noise) == "Rat"
