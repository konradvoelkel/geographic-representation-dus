"""Das Wiederholungsbudget der Overpass-Abfrage gilt für jede Folge von Antworten (Punkt 55).

Zwei Eigenschaften, die für alle Eingaben gelten und darum kein Beispieltest sind: die Zahl der
Abfragen übersteigt ``retries + 1`` nie, und gewartet wird genau einmal je verworfenem Versuch,
mit wachsender Pause. Die Folge der Antworten mischt Abweisungen (429, 504) und Erfolg; die
Fake-Session ist streng (ein Aufruf zu viel ist ein ``IndexError``), die obere Grenze steht also
schon im Aufbau und wird zusätzlich gezählt.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from georep.errors import NetworkError
from georep.sources.overpass import OVERPASS_RETRY_STATUSES, fetch_street_names
from tests.conftest import REPO
from tests.fakes import SequenceSession, response

ENDPOINT = "https://overpass.invalid/api/interpreter"


@pytest.fixture(scope="module")
def answer() -> object:
    return json.loads((REPO / "tests" / "fixtures" / "http" / "overpass_9802.json").read_text())


@hsettings(max_examples=200, deadline=None)
@given(
    statuses=st.lists(st.sampled_from([200, *OVERPASS_RETRY_STATUSES]), min_size=1, max_size=9),
    retries=st.integers(min_value=0, max_value=6),
)
def test_at_most_one_query_more_than_the_retry_budget(
    statuses: list[int], retries: int, answer: object
) -> None:
    answers = [
        response(ENDPOINT, status=s) if s != 200 else response(ENDPOINT, payload=answer)
        for s in statuses
    ]
    # Mehr Antworten, als das Budget je abholen kann: die Folge begrenzt den Test nicht.
    answers += [response(ENDPOINT, payload=answer)] * (retries + 2)
    session = SequenceSession(ENDPOINT, answers)
    slept: list[float] = []
    try:
        fetch_street_names(
            session, ENDPOINT, "51 6 51 7", retries=retries, delay_s=0.5, sleep=slept.append
        )
    except NetworkError:
        pass  # alle Versuche abgewiesen; die Zahlen unten gelten trotzdem
    assert 1 <= len(session.calls) <= retries + 1
    # Je verworfener Versuch genau eine Pause, und sie verdoppelt sich: 0,5 / 1 / 2 / …
    assert slept == [0.5 * 2**n for n in range(len(session.calls) - 1)]


@hsettings(max_examples=50, deadline=None)
@given(
    retries=st.integers(min_value=0, max_value=6),
    status=st.sampled_from(OVERPASS_RETRY_STATUSES),
)
def test_a_server_that_only_rejects_exhausts_the_budget_and_then_fails(
    retries: int, status: int
) -> None:
    session = SequenceSession(ENDPOINT, [response(ENDPOINT, status=status)] * (retries + 1))
    slept: list[float] = []
    with pytest.raises(NetworkError, match=str(status)):
        fetch_street_names(
            session, ENDPOINT, "51 6 51 7", retries=retries, delay_s=1.0, sleep=slept.append
        )
    assert len(session.calls) == retries + 1 and len(slept) == retries
