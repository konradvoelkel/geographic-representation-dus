from __future__ import annotations

import deal
import pytest

from georep.contracts import configure


@deal.pre(lambda x: x > 0)
def _positive(x: int) -> int:
    return x


def test_configure_switches_contracts_process_wide() -> None:
    with pytest.raises(deal.PreContractError):
        _positive(-1)
    configure("off")
    assert _positive(-1) == -1
    configure("on")
    with pytest.raises(deal.PreContractError):
        _positive(-1)
