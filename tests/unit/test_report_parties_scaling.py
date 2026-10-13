"""Der Umschalter des Parteiabschnitts (Punkt 46): Anteil, Abweichung, Verhältnis."""

from __future__ import annotations

import re

import polars as pl
import pytest

from georep.analysis.hits import DISTRICT
from georep.analysis.parties import PARTEI, PARTY_DEVIATION, PARTY_RATIO, SHARE
from georep.layout import Layout
from georep.report.model import ReportModel


def test_every_cell_carries_all_three_variants(mini_model: ReportModel, mini_run: Layout) -> None:
    table = pl.read_parquet(mini_run.party_results)
    found = {(r[DISTRICT], r[PARTEI]): r for r in table.iter_rows(named=True)}
    assert mini_model.party_cells
    for cell in mini_model.party_cells:
        row = found[(cell.district, cell.party)]
        assert cell.share == pytest.approx(row[SHARE])
        assert cell.deviation == pytest.approx(row[PARTY_DEVIATION])
        assert cell.ratio == pytest.approx(row[PARTY_RATIO])
        assert 0 <= cell.klass_deviation <= 4
        assert 0 <= cell.klass_ratio <= 4


def test_the_diverging_classes_are_shared_across_the_parties(mini_model: ReportModel) -> None:
    """Die Standardvariante klassiert je Partei, die beiden neuen gemeinsam.

    Der Anteil einer Fraktion mit 2308 Dokumenten ist mit dem einer mit 183 nicht vergleichbar;
    Abweichung und Verhältnis sind in derselben Einheit gegen dieselbe Bezugsgröße gemessen, und
    genau diese Vergleichbarkeit ist der Zweck der Variante.
    """
    cells = mini_model.party_cells
    # Gemeinsame Grenzen heißt: wer mehr abweicht, liegt nie in einer niedrigeren Klasse
    for one in cells:
        for other in cells:
            if one.deviation < other.deviation:
                assert one.klass_deviation <= other.klass_deviation
            if one.ratio < other.ratio:
                assert one.klass_ratio <= other.klass_ratio


def test_each_party_row_carries_its_three_means(mini_model: ReportModel) -> None:
    for party in mini_model.parties:
        mine = [c for c in mini_model.party_cells if c.party == party.key]
        assert party.mean_share == pytest.approx(sum(c.share for c in mine) / len(mine))
        assert party.mean_deviation == pytest.approx(sum(c.deviation for c in mine) / len(mine))
        assert party.mean_ratio == pytest.approx(sum(c.ratio for c in mine) / len(mine))


def test_the_section_offers_the_switcher(mini_page: str) -> None:
    block = mini_page.split('<section id="parteien">', 1)[1].split("</section>", 1)[0]
    assert 'name="parteiwert"' in block
    for value, label in (
        ("anteil", "Anteil"),
        ("abwpartei", "Abweichung vom Mittel"),
        ("verhpartei", "Verhältnis zum Mittel"),
    ):
        assert f'value="{value}"' in block and label in block
        assert f'id="legend-{value}"' in block
    assert 'value="abwpartei" data-scale="d"' in block
    assert 'value="verhpartei" data-scale="d"' in block


def test_the_small_maps_carry_the_variants_as_attributes(
    mini_page: str, mini_model: ReportModel
) -> None:
    """Keine zweite Kopie der SVG-Karten: die Varianten sind Attribute an denselben <use>."""
    cells = len(mini_model.party_cells)
    assert mini_page.count('<path id="pm-') == len(mini_model.districts)
    for value in ("abwpartei", "verhpartei"):
        assert len(re.findall(rf'data-class-{value}="\d"', mini_page)) >= cells
    # Die Standardvariante steht in der Klasse der Flaeche und traegt kein Attribut
    assert "data-class-anteil=" not in mini_page
    assert len(re.findall(r'<use href="#pm-\d+" class="district q\d"', mini_page)) == cells


def test_the_party_table_column_follows_the_switcher(mini_page: str) -> None:
    table = mini_page.split('<table id="parteien-tabelle"', 1)[1].split("</table>", 1)[0]
    assert ">Anteil im Mittel</th>" in table  # die Standardvariante steht als Text da
    assert 'data-text-abwpartei="Abweichung"' in table
    assert 'data-text-verhpartei="Verhältnis"' in table
    rows = table.split("<tbody>", 1)[1].count("<tr>")
    for value in ("abwpartei", "verhpartei"):
        assert len(re.findall(rf"data-value-{value}=", table)) == rows
    assert "data-value-anteil=" not in table and "data-text-anteil=" not in table


def test_the_district_cells_follow_the_switcher(mini_page: str, mini_model: ReportModel) -> None:
    table = mini_page.split('<table id="urheber-tabelle"', 1)[1].split("</table>", 1)[0]
    cells = len(mini_model.party_cells)
    for value in ("abwpartei", "verhpartei"):
        assert len(re.findall(rf'data-class-{value}="\d"', table)) == cells
        assert len(re.findall(rf"data-text-{value}=", table)) == cells
    # Die Standardvariante steht in Klasse, Text und Sortierwert der Zelle selbst
    assert len(re.findall(r'class="num q\d" data-value=', table)) == cells
    assert "pp" in table and "×" in table  # Prozentpunkte und Malzeichen


def test_the_legends_explain_the_fixed_boundaries(mini_page: str) -> None:
    for value in ("abwpartei", "verhpartei"):
        block = mini_page.split(f'id="legend-{value}"', 1)[1].split("</div>", 1)[0]
        assert "swatch d" in block  # die divergierende Rampe
        assert "Mittel" in block
