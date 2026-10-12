"""Die normierten Kennzahlen auf der Seite (Punkt 46): Modell, Karte, Tabelle, Kernzahlen."""

from __future__ import annotations

import re
from dataclasses import replace

import deal
import polars as pl
import pytest

from georep.analysis.hits import DISTRICT, RATE
from georep.analysis.scaling import CITY_MEAN, DEVIATION, PER_1000, PER_TERM, TERM_COUNT
from georep.errors import SchemaError
from georep.report.model import DistrictMetrics, ReportModel, with_metrics
from georep.report.render import Visuals, render_report
from georep.search.index import HITS


def _frame(rows: list[tuple[int, float, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            DISTRICT: [r[0] for r in rows],
            HITS: [0 for _ in rows],
            TERM_COUNT: [0 for _ in rows],
            PER_TERM: [r[1] for r in rows],
            RATE: [0.0 for _ in rows],
            PER_1000: [0.0 for _ in rows],
            CITY_MEAN: [0.06 for _ in rows],
            DEVIATION: [r[2] for r in rows],
        }
    )


def test_every_row_gets_its_metrics(mini_model: ReportModel) -> None:
    for row in mini_model.districts:
        assert row.metrics is not None
        assert row.metrics.per_term == pytest.approx(row.hits / row.terms_total)
        assert row.metrics.per_1000 == pytest.approx(row.rate * 1000.0)
        assert row.metrics.deviation == pytest.approx(row.rate / row.metrics.city_mean - 1.0)


def test_a_district_missing_from_the_metrics_is_a_schema_error(mini_model: ReportModel) -> None:
    with pytest.raises(SchemaError, match="Kennzahlen"):
        with_metrics(mini_model.districts, _frame([(999, 1.0, 0.0)]))


def test_the_metrics_frame_needs_its_columns(mini_model: ReportModel) -> None:
    with pytest.raises(deal.PreContractError):
        with_metrics(mini_model.districts, pl.DataFrame({DISTRICT: [1]}))


def test_the_metrics_of_a_row_are_a_frozen_record() -> None:
    found = DistrictMetrics(per_term=2.0, per_1000=6.0, city_mean=0.006, deviation=0.5)
    with pytest.raises(Exception):  # noqa: B017 -- dataclasses.FrozenInstanceError
        found.per_term = 3.0  # type: ignore[misc]


def test_the_map_offers_the_three_new_normalisations(mini_page: str) -> None:
    for value, label in (
        ("treffer", "Treffer absolut"),
        ("jebegriff", "Treffer je Begriff"),
        ("abweichung", "Abweichung vom Stadtmittel"),
    ):
        assert f'value="{value}"' in mini_page
        assert label in mini_page
        assert f'id="legend-{value}"' in mini_page
    # Die divergierende Variante nennt ihre Rampe, die beiden sequenziellen nicht
    assert 'value="abweichung" data-scale="d"' in mini_page
    assert 'value="jebegriff" data-scale' not in mini_page


def test_every_district_shape_carries_the_new_classes(mini_page: str) -> None:
    for value in ("treffer", "jebegriff", "abweichung"):
        found = re.findall(rf'data-class-{value}="(\d)"', mini_page)
        assert len(found) == 3, value  # drei Wahlbezirke in der Mini-Fixture
        assert all(digit in "01234" for digit in found)


def test_the_district_table_mirrors_the_chosen_metric(mini_page: str) -> None:
    """Die Spalte der Trefferquote zeigt, wonach die Karte gerade eingefärbt ist."""
    table = mini_page.split('<table id="districts">', 1)[1].split("</table>", 1)[0]
    head = table.split("</thead>", 1)[0]
    assert 'data-text-jebegriff="Treffer je Begriff"' in head
    assert 'data-text-abweichung="vom Stadtmittel"' in head
    assert 'data-text-rate="Trefferquote"' in head
    for value in ("rate", "treffer", "jebegriff", "abweichung"):
        assert len(re.findall(rf"data-text-{value}=", table)) == 4  # Kopf und drei Zeilen
        assert len(re.findall(rf"data-value-{value}=", table)) == 3


def test_the_key_figures_name_the_hits_per_term(mini_page: str) -> None:
    kernzahlen = mini_page.split('<section id="kernzahlen">', 1)[1].split("</section>", 1)[0]
    assert "Treffer je Begriff" in kernzahlen
    assert "Spannweite" in kernzahlen


def test_the_legends_explain_the_fixed_boundaries(mini_page: str) -> None:
    block = mini_page.split('id="legend-abweichung"', 1)[1].split("</div>", 1)[0]
    assert "Stadtmittel" in block
    assert "%" in block


# --- Punkt 46: die zweite Regression neben Tabelle 5 ----------------------------------------------


def test_the_model_carries_a_second_regression(mini_model: ReportModel) -> None:
    """Dieselbe Rechnung mit x = Treffer je Begriff; Tabelle 5 selbst bleibt unberührt."""
    second = mini_model.per_term_regression
    assert second is not None and mini_model.regression is not None
    assert second.all.n == mini_model.regression.all.n
    assert -1.0 <= second.all.r <= 1.0 and 0.0 <= second.all.p <= 1.0
    # Die beiden sind verschiedene Rechnungen: dieselbe Zielgröße, eine andere Kennzahl
    assert second.all.slope != mini_model.regression.all.slope


def test_the_section_shows_both_regressions(mini_page: str) -> None:
    block = mini_page.split('<section id="zusammenhang">', 1)[1].split("</section>", 1)[0]
    assert "Tabelle 5 der Arbeit" in block  # unverändert
    assert "Treffer je Begriff" in block
    assert "Wörterbuch" in block
    assert block.count("<table") == 2  # Tabelle 5 und die zweite Regression daneben


def test_without_the_metrics_step_the_second_regression_is_absent(
    mini_model: ReportModel, mini_visuals: Visuals
) -> None:
    """Der Block hängt am Modellfeld; ohne den Schritt ``metrics`` steht er nicht da."""
    page = render_report(replace(mini_model, per_term_regression=None), mini_visuals)
    block = page.split('<section id="zusammenhang">', 1)[1].split("</section>", 1)[0]
    assert "Tabelle 5 der Arbeit" in block and block.count("<table") == 1
    assert "je Begriff im Wörterbuch" not in block
