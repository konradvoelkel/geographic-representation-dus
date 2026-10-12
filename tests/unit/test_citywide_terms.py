"""Regel 2 „stadtweite Begriffe": die Schwelle und wer über ihr liegt.

Begriffe mit auffällig hoher Dokumenthäufigkeit stehen in vielen Dokumenten, die nicht von ihrem
Wahlbezirk handeln („hofgarten" 172, „schulweg" 144 auf der Referenz). Die Regel benennt sie, statt
sie zu verstecken; ob sie zusätzlich aus der Zählung fallen, ist ein eigener Schalter
(``search.citywide_exclude``, standardmäßig aus). Siehe docs/decisions.md, Punkt 44.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from georep.analysis.hits import citywide_terms, without_terms
from georep.search.index import HITS, PAPER_IDS, TERM
from georep.settings import Search, Settings, load_settings


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


def _index(*pairs: tuple[str, int]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            TERM: [p[0] for p in pairs],
            PAPER_IDS: [[f"d{i}" for i in range(p[1])] for p in pairs],
            HITS: [p[1] for p in pairs],
        }
    )


def test_the_quantile_names_the_threshold_and_the_terms() -> None:
    index = _index(("a", 1), ("b", 1), ("c", 2), ("d", 3), ("e", 100))
    found = citywide_terms(index, quantile=0.75, median_factor=0.0)
    assert found.threshold == 3  # 75-%-Quantil der Häufigkeiten 1, 1, 2, 3, 100
    assert found.terms == ("e",)
    assert "75" in found.basis and "Quantil" in found.basis


def test_the_median_factor_names_the_threshold_and_the_terms() -> None:
    index = _index(("a", 1), ("b", 1), ("c", 2), ("d", 3), ("e", 100))
    found = citywide_terms(index, quantile=0.0, median_factor=10.0)
    assert found.threshold == 20  # Median 2, zehnfach
    assert found.terms == ("e",)
    assert "Median" in found.basis


def test_without_a_threshold_there_is_no_list() -> None:
    index = _index(("a", 1), ("e", 100))
    found = citywide_terms(index, quantile=0.0, median_factor=0.0)
    assert found.terms == () and found.threshold == 0 and found.basis == ""


def test_the_strongest_terms_come_first() -> None:
    index = _index(("a", 50), ("b", 80), ("c", 1), ("d", 80), ("e", 2), ("f", 3))
    found = citywide_terms(index, quantile=0.25, median_factor=0.0)
    assert found.threshold == 2  # 25-%-Quantil von 1, 2, 3, 50, 80, 80
    # absteigend nach Dokumenten, bei Gleichstand alphabetisch
    assert found.terms == ("b", "d", "a", "f")


def test_terms_can_be_taken_out_of_a_dictionary() -> None:
    dictionary = pl.DataFrame(
        {"wahlkreis_id": [1, 2], "suchbegriffe": [["a", "b"], ["b", "c"]]},
        schema={"wahlkreis_id": pl.Int64, "suchbegriffe": pl.List(pl.String)},
    )
    out = without_terms(dictionary, ("b",))
    assert out.get_column("suchbegriffe").to_list() == [["a"], ["c"]]
    assert without_terms(dictionary, ()).equals(dictionary)


def test_the_defaults_show_the_list_and_count_everything(settings: Settings) -> None:
    assert settings.search.citywide_quantile == 0.99  # 58 der 5841 Begriffe auf der Referenz
    assert settings.search.citywide_median_factor == 0.0
    assert settings.search.citywide_exclude is False  # nur Anzeige, keine Korrektur


@pytest.mark.parametrize(
    "overrides",
    [
        {"citywide_quantile": 0.99, "citywide_median_factor": 20.0},  # genau eines von beiden
        {"citywide_quantile": 1.0},
        {"citywide_quantile": -0.5},
        {"citywide_median_factor": -1.0},
        {"citywide_quantile": 0.0, "citywide_exclude": True},  # Ausschluss ohne Schwelle
    ],
)
def test_a_contradictory_threshold_is_an_error(overrides: dict[str, object]) -> None:
    fields: dict[str, object] = {"text_split_marker": "betrifft", **overrides}
    with pytest.raises(ValidationError):
        Search(**fields)  # type: ignore[arg-type]
