"""Regel 2 „stadtweite Begriffe": die Schwelle und wer über ihr liegt.

Begriffe mit auffällig hoher Dokumenthäufigkeit stehen in vielen Dokumenten, die nicht von ihrem
Wahlbezirk handeln („hofgarten" 172, „schulweg" 144 auf der Referenz). Die Regel benennt sie und
ändert keine Zahl: ein Schalter, der sie aus der Zählung nimmt, gibt es nicht
(docs/decisions.md, Punkt 44b).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from georep.analysis.hits import citywide_terms
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


def test_the_defaults_show_the_list_and_count_everything(settings: Settings) -> None:
    assert settings.search.citywide_quantile == 0.99  # 55 von 5727 Begriffen auf der Referenz
    assert settings.search.citywide_median_factor == 0.0


def test_there_is_no_switch_that_takes_the_terms_out_of_the_count(settings: Settings) -> None:
    """Regel 2 ist Anzeige, nichts weiter (decisions.md, Punkt 44b).

    Ein Schalter, der die stadtweiten Begriffe aus der Zählung nimmt, hat es am 2026-10-12 kurz
    gegeben; er wirkte nur im Schritt ``results``, während ``timeline``, ``weights`` und die
    Berichtsseite weiter das ganze Wörterbuch lasen. Statt ihn an fünf Stellen durchzuziehen, ist
    er weg: die Schwelle trifft auch echte Ortsnamen, und niemand könnte ihren Ausschluss
    begründen.
    """
    assert not hasattr(settings.search, "citywide_exclude")
    with pytest.raises(ValidationError):
        Search(text_split_marker="betrifft", citywide_exclude=True)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "overrides",
    [
        {"citywide_quantile": 0.99, "citywide_median_factor": 20.0},  # genau eines von beiden
        {"citywide_quantile": 1.0},
        {"citywide_quantile": -0.5},
        {"citywide_median_factor": -1.0},
    ],
)
def test_a_contradictory_threshold_is_an_error(overrides: dict[str, object]) -> None:
    fields: dict[str, object] = {"text_split_marker": "betrifft", **overrides}
    with pytest.raises(ValidationError):
        Search(**fields)  # type: ignore[arg-type]
