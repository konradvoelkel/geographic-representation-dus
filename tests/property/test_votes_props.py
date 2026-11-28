"""Eigenschaften der Abstimmungen (``analysis.votes``), für jeden Eintrag und jede Folge von Zeilen.

Bauplan ``docs/plans/28-abstimmungen.md``, § 6 (Ebene A): die Wortregel gibt jedem Text genau eine
Klasse, eine Form genau bei einem entschiedenen Beschluss; die Tabelle je Punkt und die Zählung je
Gremienart hängen nur von der Menge der Zeilen ab, nicht von ihrer Folge; der letzte Beschluss
eines Antrags ist der späteste im Zeitraum; die Grenzen nach Clopper-Pearson umschließen den Anteil.
"""

from __future__ import annotations

import datetime as dt
import random
from pathlib import Path

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.outcomes import PROGRESS_SCHEMA
from georep.analysis.votes import (
    CLASSES,
    FORMS,
    VoteRules,
    binomial_less,
    body_summary,
    form_of,
    last_decisions,
    result_class,
    votes_table,
)
from georep.prep.bodies import BodyRules
from georep.settings import VOTE_DECIDED, load_settings

SETTINGS = load_settings(cwd=Path("/nonexistent"))
RULES = VoteRules.from_settings(SETTINGS.votes)
BODIES = BodyRules.from_settings(SETTINGS.bodies)
VALUES = sorted(SETTINGS.outcomes.results)
WORDS = sorted({word for _, words in RULES.results for word in words})

texts = st.one_of(
    st.none(),
    st.text(max_size=40),
    st.sampled_from(VALUES),
    st.lists(
        st.sampled_from([*WORDS, "einstimmig", "mehrheitlich", " ", "Empfehlung"]), max_size=4
    ).map(" ".join),
)


@given(texts)
def test_jeder_text_bekommt_genau_eine_klasse_und_eine_form_nur_bei_entscheidung(
    text: str | None,
) -> None:
    klasse = result_class(text, RULES)
    form = form_of(text, RULES)
    assert klasse in CLASSES
    assert (form is not None) == (klasse in VOTE_DECIDED)
    assert form is None or form in FORMS


rows = st.lists(
    st.tuples(
        st.sampled_from(("p1", "p2", "p3")),
        st.one_of(st.none(), st.sampled_from(("RAT", "BV6", "AWM", "INTR", "gr/1", "AWM+RAT"))),
        st.one_of(st.none(), st.sampled_from(VALUES)),
        st.sampled_from([dt.datetime(2021, 1, day, 15) for day in (1, 2, 3)]),
    ),
    max_size=12,
)


def _progress(found: list[tuple[str, str | None, str | None, dt.datetime]]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            (paper, f"b{i}", f"t{i:02d}", body, "-", start, "1", 1, result, None)
            for i, (paper, body, result, start) in enumerate(found)
        ],
        schema=PROGRESS_SCHEMA,
        orient="row",
    )


@given(rows, st.randoms(use_true_random=False))
def test_tabelle_und_zaehlung_haengen_nicht_an_der_folge(
    found: list[tuple[str, str | None, str | None, dt.datetime]], rng: random.Random
) -> None:
    progress = _progress(found)
    shuffled = progress.sample(fraction=1.0, shuffle=True, seed=rng.randrange(2**32))
    votes = votes_table(progress, BODIES, RULES)
    assert votes.equals(votes_table(shuffled, BODIES, RULES))
    bodies = body_summary(votes, "2020-2025")
    assert bodies.equals(body_summary(votes.reverse(), "2020-2025"))
    assert bodies.get_column("punkte").sum() == len(found)


decisions = st.lists(
    st.tuples(
        st.sampled_from(("m1", "m2", "m3")),
        st.sampled_from(("rat", "ausschuss")),
        st.sampled_from(("angenommen", "abgelehnt", "vertagt")),
        st.dates(dt.date(2020, 6, 1), dt.date(2026, 6, 1)),
    ),
    max_size=15,
)


@given(decisions)
def test_der_letzte_beschluss_ist_der_spaeteste_im_zeitraum(
    found: list[tuple[str, str, str, dt.date]],
) -> None:
    progress = _progress(
        [
            (
                paper,
                "RAT" if kind == "rat" else "AWM",
                "mehrheitlich abgelehnt"
                if klasse == "abgelehnt"
                else "mehrheitlich beschlossen"
                if klasse == "angenommen"
                else "vertagt",
                dt.datetime.combine(day, dt.time(15)),
            )
            for paper, kind, klasse, day in found
        ]
    )
    votes = votes_table(progress, BODIES, RULES)
    motions = pl.DataFrame(
        {"id": ["m1", "m2", "m3"], "parteien": [["C"]] * 3},
        schema={"id": pl.String, "parteien": pl.List(pl.String)},
    )
    start, end = dt.date(2021, 1, 1), dt.date(2025, 9, 14)
    last = last_decisions(votes, motions, ("rat",), VOTE_DECIDED, start, end)
    for row in last.iter_rows(named=True):
        later = votes.filter(
            (pl.col("paper") == row["id"])
            & (pl.col("gremium_art") == "rat")
            & pl.col("ergebnis").is_in(list(VOTE_DECIDED))
            & pl.col("datum").is_between(start, end)
            & (
                (pl.col("datum") > row["datum"])
                | ((pl.col("datum") == row["datum"]) & (pl.col("top") > row["top"]))
            )
        )
        assert later.is_empty()
        assert start <= row["datum"] <= end
    decided = votes.filter(
        (pl.col("gremium_art") == "rat")
        & pl.col("ergebnis").is_in(list(VOTE_DECIDED))
        & pl.col("datum").is_between(start, end)
    )
    assert last.height == decided.get_column("paper").n_unique()


@given(st.integers(1, 400).flatmap(lambda n: st.tuples(st.integers(0, n), st.just(n))))
def test_die_grenzen_umschliessen_den_anteil(pair: tuple[int, int]) -> None:
    k, n = pair
    test = binomial_less(k, n, 0.25)
    assert 0.0 <= test.lower <= k / n <= test.upper <= 1.0
    assert 0.0 <= test.p <= 1.0
    if k < n:
        assert binomial_less(k + 1, n, 0.25).p >= test.p
