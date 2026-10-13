"""Punkt 45: der passende Ausschuss je Dokument, überwacht gelernt.

Die Güte misst ein Skript (``docs/themenmodell-2026-10-messung.py``) mit Kreuzvalidierung; hier
stehen die Eigenschaften, die jeder Lauf halten muss: eine Zeile je Dokument mit Text, eine
Wahrscheinlichkeit oder nichts, eine Restklasse unter der Schwelle, und die Tabelle zerlegt die
Dokumente ohne Rest.
"""

from __future__ import annotations

from pathlib import Path

import deal
import polars as pl
import pytest
from polars.testing import assert_frame_equal

from georep.analysis.committees import assign_committees, summary
from georep.analysis.topics import TopicRules
from georep.settings import Classify, Topics, load_settings

FAMILIES = {
    "AAA": ("strasse", "verkehr", "parken", "radweg", "ampel"),
    "BBB": ("schule", "kita", "bildung", "unterricht", "lehrer"),
    "CCC": ("grundstueck", "bauvorhaben", "stellplatz", "bebauung", "baulinie"),
}
CROSS = "haushalt personal stellenplan jahresabschluss"


def _corpus(
    per_committee: int = 12, cross: int = 3, codes: tuple[str, ...] = ()
) -> tuple[pl.DataFrame, pl.DataFrame]:
    rows, refs = [], []
    families = {c: FAMILIES[c] for c in codes} if codes else FAMILIES
    for code, family in families.items():
        for i in range(per_committee):
            paper = f"{code}-{i:02d}"
            rows.append({"id": paper, "text": " ".join(family * 3) + f" wort{i}"})
            refs.append({"id": paper, "gremium": code, "gremium_art": "ausschuss"})
    for i in range(cross):
        paper = f"RAT-{i:02d}"
        rows.append({"id": paper, "text": f"{CROSS} wort{i}"})
        refs.append({"id": paper, "gremium": "RAT", "gremium_art": "rat"})
    corpus = pl.DataFrame(rows, schema={"id": pl.String, "text": pl.String})
    bodies = pl.DataFrame(
        refs, schema={"id": pl.String, "gremium": pl.String, "gremium_art": pl.String}
    )
    return corpus, bodies


def _topics(**overrides: object) -> Topics:
    base: dict[str, object] = {"k": 3, "min_df": 1, "max_df": 1.0, "max_features": 200}
    return Topics(**(base | overrides))  # type: ignore[arg-type]


def _classify(**overrides: object) -> Classify:
    base: dict[str, object] = {"min_documents": 5, "min_probability": 0.4}
    return Classify(**(base | overrides))  # type: ignore[arg-type]


def _rules() -> TopicRules:
    return TopicRules(committees=frozenset(FAMILIES))


def test_every_document_with_text_gets_one_row() -> None:
    corpus, bodies = _corpus()
    found = assign_committees(corpus, bodies, _topics(), _classify(), _rules())
    assert found.papers.columns == ["id", "ausschuss", "wahrscheinlichkeit"]
    assert found.papers.height == corpus.height
    assert found.papers.get_column("id").to_list() == sorted(corpus.get_column("id").to_list())


def test_a_document_of_a_committee_is_assigned_to_its_own_committee() -> None:
    corpus, bodies = _corpus()
    found = assign_committees(corpus, bodies, _topics(), _classify(), _rules())
    assigned = dict(found.papers.select("id", "ausschuss").iter_rows())
    for code in FAMILIES:
        own = [paper for paper in assigned if paper.startswith(code)]
        assert all(assigned[paper] == code for paper in own), (code, assigned)


def test_a_document_under_the_threshold_lands_in_the_rest_class() -> None:
    """Eine Schwelle von fast 1 lässt nichts durch: alles ist querschnittlich."""
    corpus, bodies = _corpus()
    found = assign_committees(corpus, bodies, _topics(), _classify(min_probability=0.999), _rules())
    assert set(found.papers.get_column("ausschuss").to_list()) == {""}
    assert found.table.height == 1 and found.table.get_column("ausschuss").to_list() == [""]


def test_fewer_than_two_classes_leave_everything_in_the_rest_class() -> None:
    """Eine Klasse ist keine Entscheidung; ein dünner Korpus ist kein Fehler."""
    corpus, bodies = _corpus(per_committee=3)
    found = assign_committees(corpus, bodies, _topics(), _classify(min_documents=5), _rules())
    assert set(found.papers.get_column("ausschuss").to_list()) == {""}
    assert found.papers.get_column("wahrscheinlichkeit").null_count() == found.papers.height


def test_the_table_decomposes_the_documents_without_a_rest() -> None:
    corpus, bodies = _corpus()
    found = assign_committees(corpus, bodies, _topics(), _classify(), _rules())
    assert found.table.columns == [
        "ausschuss",
        "dokumente",
        "anteil",
        "ohne_ausschussberatung",
        "wahrscheinlichkeit_median",
    ]
    assert int(found.table.get_column("dokumente").sum()) == found.papers.height
    assert float(found.table.get_column("anteil").sum()) == pytest.approx(1.0, abs=1e-9)
    assert (found.table.get_column("ohne_ausschussberatung") <= found.table["dokumente"]).all()
    # Die drei Ausschussdokumente des Rates sind die einzigen ohne Ausschussberatung.
    assert int(found.table.get_column("ohne_ausschussberatung").sum()) == 3


def test_two_runs_give_the_same_frames() -> None:
    corpus, bodies = _corpus()
    first = assign_committees(corpus, bodies, _topics(), _classify(), _rules())
    second = assign_committees(corpus, bodies, _topics(), _classify(), _rules())
    assert_frame_equal(first.papers, second.papers)
    assert_frame_equal(first.table, second.table)


def test_the_summary_names_the_classes_and_the_rest() -> None:
    corpus, bodies = _corpus()
    found = assign_committees(corpus, bodies, _topics(), _classify(), _rules())
    line = summary(found)
    assert "3 Ausschüsse" in line and "Restklasse" in line
    # Die Zahlen, nicht nur die Wörter: ohne sie überlebten die Mutanten in ``summary``
    # (``== REST`` zu ``!=``, ``-`` zu ``+``; docs/mutation-2026-10-13.md).
    rest = int(found.table.filter(pl.col("ausschuss") == "").get_column("dokumente").sum())
    assert line == (
        f"{found.papers.height} Dokumente: {found.papers.height - rest} einem von 3 Ausschüssen "
        f"zugeordnet, {rest} in der Restklasse"
    )
    assert f"{found.papers.height} Dokumente" in line and found.papers.height == 39


def test_exactly_two_classes_at_the_minimum_are_still_a_decision() -> None:
    """Die zwei Grenzen des Klassifikators: ``>= min_documents`` und ``len(classes) < 2``.

    Zwei Klassen mit **genau** ``min_documents`` Dokumenten müssen gelernt werden; mit einem
    Dokument weniger je Klasse bleibt alles in der Restklasse. Ohne diesen Fall überlebten die
    Mutanten ``>=`` zu ``>`` und ``< 2`` zu ``<= 2`` (docs/mutation-2026-10-13.md).
    """
    two = ("AAA", "BBB")
    corpus, bodies = _corpus(per_committee=5, cross=2, codes=two)
    found = assign_committees(corpus, bodies, _topics(k=2), _classify(min_documents=5), _rules())
    assert found.classes == two
    assigned = found.papers.filter(pl.col("ausschuss") != "")
    assert assigned.height > 0 and set(assigned.get_column("ausschuss").to_list()) <= set(two)

    corpus, bodies = _corpus(per_committee=4, cross=2, codes=two)
    thin = assign_committees(corpus, bodies, _topics(k=2), _classify(min_documents=5), _rules())
    assert thin.classes == () and set(thin.papers.get_column("ausschuss").to_list()) == {""}


def test_the_rest_class_counts_the_documents_without_a_committee() -> None:
    corpus, bodies = _corpus()
    found = assign_committees(corpus, bodies, _topics(), _classify(), _rules())
    rest = found.table.filter(pl.col("ausschuss") == "")
    assert rest.height <= 1  # ohne Restklasse fehlt die Zeile ganz
    assigned = found.papers.filter(pl.col("ausschuss") != "")
    assert (assigned.get_column("wahrscheinlichkeit") >= 0.4).all()


def test_the_profile_default_keeps_the_classifier_on() -> None:
    settings = load_settings(cwd=Path("/nonexistent"))
    assert settings.classify.enabled and settings.bodies.committees


# --- Die Zeilenfolge eines Joins ist nicht festgelegt (crosswalk.py, prep/context.py) ----------


def test_two_rows_for_one_document_are_a_contract_violation() -> None:
    """Ein zweites Gremium je Dokument würde den Join verlängern und alles verschieben.

    ``papers_gremien.parquet`` hat eine Zeile je Dokument (Vertrag in ``prep.bodies``); ein von
    Hand gebauter Frame muss das auch halten, sonst stünde die Wahrscheinlichkeit des einen
    Dokuments beim anderen.
    """
    corpus, bodies = _corpus()
    doubled = pl.concat([bodies, bodies.head(1)])
    with pytest.raises(deal.PreContractError):
        assign_committees(corpus, doubled, _topics(), _classify(), _rules())


def test_the_order_of_the_inputs_does_not_change_the_result() -> None:
    """Dieselben Daten in anderer Zeilenfolge: dieselbe Zuordnung, Zeile für Zeile."""
    corpus, bodies = _corpus()
    straight = assign_committees(corpus, bodies, _topics(), _classify(), _rules())
    shuffled = assign_committees(
        corpus.sample(fraction=1.0, shuffle=True, seed=7),
        bodies.sample(fraction=1.0, shuffle=True, seed=11),
        _topics(),
        _classify(),
        _rules(),
    )
    assert_frame_equal(straight.papers, shuffled.papers)
    assert_frame_equal(straight.table, shuffled.table)


def test_the_result_carries_exactly_the_documents_with_text_in_order() -> None:
    corpus, bodies = _corpus()
    corpus = pl.concat(
        [corpus, pl.DataFrame({"id": ["ZZZ-99"], "text": [""]}, schema=corpus.schema)]
    )
    found = assign_committees(corpus, bodies, _topics(), _classify(), _rules())
    expected = sorted(corpus.filter(pl.col("text") != "").get_column("id").to_list())
    assert found.papers.get_column("id").to_list() == expected


def test_a_document_without_a_gremium_counts_as_without_consultation() -> None:
    """Ein Dokument, das in ``bodies`` fehlt, ist „ohne Ausschussberatung" und kein Fehler."""
    corpus, bodies = _corpus()
    without = bodies.filter(pl.col("id") != "AAA-00")
    found = assign_committees(corpus, without, _topics(), _classify(), _rules())
    assert found.papers.height == corpus.height
    assert "AAA-00" in found.papers.get_column("id").to_list()
    # Die drei Ratsdokumente und das fehlende Ausschussdokument.
    assert int(found.table.get_column("ohne_ausschussberatung").sum()) == 4
