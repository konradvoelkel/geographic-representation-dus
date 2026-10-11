from __future__ import annotations

import polars as pl
import pytest

from georep.analysis.regression import regress
from georep.errors import EmptyResultError


def test_regression_without_spread_in_x_is_a_domain_error() -> None:
    frame = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2, 3],
            "trefferquote": [0.2, 0.2, 0.2],
            "wahlbeteiligung": [0.5, 0.6, 0.7],
        }
    )
    with pytest.raises(EmptyResultError, match="Streuung"):
        regress(frame)
