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


def test_pure_contracts_leave_patched_globals_restored() -> None:
    """deals has()-Patcher ist nicht reentrant: ein rekursiver pure-Aufruf ließ am 2026-10-11
    socket.socket und sys.stdout gepatcht zurück, jeder spätere print oder Netzzugriff im Prozess
    schlug fehl. Rekursive Funktionen bekommen darum deal.safe, nicht deal.pure."""
    import socket
    import sys

    from georep.settings import deep_merge

    before = (socket.socket, sys.stdout, sys.stderr)
    deep_merge({"a": {"b": {"c": 1}}}, {"a": {"b": {"d": 2}, "e": 3}})
    assert (socket.socket, sys.stdout, sys.stderr) == before
