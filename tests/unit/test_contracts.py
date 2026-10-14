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


# --- Option 07: Prädikate der Monatsreihe ------------------------------------------------------


def test_next_month_wraps_the_year() -> None:
    from datetime import date

    from georep.contracts import next_month

    assert next_month(date(2025, 1, 1)) == date(2025, 2, 1)
    assert next_month(date(2025, 12, 1)) == date(2026, 1, 1)


def test_months_in_order_wants_gapless_firsts_with_the_empty_one_last() -> None:
    from datetime import date

    import polars as pl

    from georep.contracts import months_in_order

    def frame(months: list[date | None]) -> pl.DataFrame:
        return pl.DataFrame({"monat": months}, schema={"monat": pl.Date})

    assert months_in_order(frame([date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1)]), "monat")
    assert months_in_order(frame([date(2025, 11, 1), None]), "monat")
    assert months_in_order(frame([]), "monat") and months_in_order(frame([None]), "monat")
    assert not months_in_order(frame([date(2025, 11, 1), date(2026, 1, 1)]), "monat")  # Lücke
    assert not months_in_order(
        frame([date(2025, 12, 1), date(2025, 11, 1)]), "monat"
    )  # Reihenfolge
    assert not months_in_order(frame([None, date(2025, 11, 1)]), "monat")  # leerer nicht am Ende
    assert not months_in_order(frame([None, None]), "monat")  # höchstens einer
    assert not months_in_order(frame([date(2025, 11, 2)]), "monat")  # kein Monatserster


def test_keys_sorted_unique_puts_empty_values_last_in_their_own_column() -> None:
    from datetime import date

    import polars as pl

    from georep.contracts import keys_sorted_unique

    def frame(rows: list[tuple[int, date | None]]) -> pl.DataFrame:
        return pl.DataFrame(
            {"id": [r[0] for r in rows], "monat": [r[1] for r in rows]},
            schema={"id": pl.Int64, "monat": pl.Date},
        )

    good = [(1, date(2025, 1, 1)), (1, None), (2, date(2025, 1, 1)), (2, None)]
    assert keys_sorted_unique(frame(good), "id", "monat")
    assert not keys_sorted_unique(frame([(1, None), (1, date(2025, 1, 1))]), "id", "monat")
    assert not keys_sorted_unique(frame([(2, None), (1, None)]), "id", "monat")
    assert not keys_sorted_unique(frame([(1, None), (1, None)]), "id", "monat")  # Dublette


# --- Punkt 57: ein Prädikat für Validator und Laufzeit -----------------------------------------


@pytest.mark.parametrize(
    ("code", "district_body", "expected"),
    [
        ("BV1", "BV", True),
        ("BV10", "BV", True),
        ("BV0", "BV", False),  # einen Stadtbezirk 0 gibt es nicht
        ("BV", "BV", False),  # ohne Nummer keine Bezirksvertretung
        ("BVx", "BV", False),
        ("RAT", "BV", False),
        ("BV²", "BV", False),  # Punkt 40: isdigit() ist wahr, int() wirft
        ("BV١", "BV", False),  # arabisch-indische Ziffer: isascii() hält sie draußen
        ("7", "", False),  # ohne Kürzel ist keine Zahl eine Bezirksvertretung
        ("", "BV", False),
    ],
)
def test_is_district_code(code: str, district_body: str, expected: bool) -> None:
    from georep.contracts import is_district_code

    assert is_district_code(code, district_body) is expected


def test_the_validator_and_the_parser_share_the_predicate() -> None:
    """Ohne ``district_body`` hielt der Validator jede Zahl für eine Bezirksvertretung.

    Dass beide Seiten dieselbe Funktion rufen, hält die Regel zusammen: der Validator von
    ``settings.Bodies`` lässt ein Alias-Ziel nur durch, wenn es ein Kürzel aus einer Tabelle ist
    oder ``is_district_code`` wahr sagt -- und genau dann liest ``parse_reference`` es später als
    Bezirksvertretung.
    """
    from pathlib import Path

    from georep.contracts import is_district_code
    from georep.prep.bodies import DISTRICT_BODY, BodyRules, parse_reference
    from georep.settings import load_settings

    settings = load_settings(cwd=Path("/nonexistent"))
    rules = BodyRules.from_settings(settings.bodies)
    for head, code in rules.aliases.items():
        assert is_district_code(code, rules.district_body)
        assert parse_reference(f"{head}/ 1/2015", rules).kind == DISTRICT_BODY
