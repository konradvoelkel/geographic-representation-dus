"""Eigenschaften der Beschlusslage (``analysis.outcomes``), für jede Folge von Einträgen.

Die Regel (Messdokument ``docs/plans/26-beschluesse.md``, § 3.1) ist eine Funktion der **Menge**
der Tagesordnungspunkte eines Dokuments: die Zeilenfolge der Eingabe ändert nichts. Ein späterer
Punkt der Stufe ``sache`` bestimmt die Klasse, ein späterer der Stufe ``stand`` ändert eine Klasse
aus ``sache`` nie. Dazu das Orakel: die Regel, wie das Messskript sie rechnete
(``oracle_outcomes.py``). Die Praxiszellen hängen nur von Gremium, Jahr und Klasse der Anträge ab.
"""

from __future__ import annotations

import datetime as dt
import random
from pathlib import Path

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis import outcomes as oc
from georep.settings import OUTCOME_STAGES, load_settings
from tests.property.oracle_outcomes import Schritt, klasse

RESULTS = dict(load_settings(profile="duesseldorf", cwd=Path("/nonexistent")).outcomes.results)
SACHE = sorted(r for r, (stage, _) in RESULTS.items() if stage == "sache")
STAND = sorted(r for r, (stage, _) in RESULTS.items() if stage == "stand")
DOCS = ("a", "b", "c")
BODIES = ("gr/1", "gr/2", "gr/3")

# Wenige Sitzungen und Folgen, damit Gleichstände vorkommen: an ihnen entscheidet die Regel über
# die ID des Punkts, und genau dort würde eine Umsetzung, die die Eingabefolge liest, abweichen.
starts = st.one_of(
    st.none(),
    st.sampled_from([dt.datetime(2021, 3, day, hour) for day in (1, 2) for hour in (10, 17)]),
)
steps = st.lists(
    st.tuples(
        st.sampled_from(DOCS),
        starts,
        st.one_of(st.none(), st.integers(0, 3)),
        st.one_of(st.none(), st.sampled_from(SACHE + STAND)),
        st.sampled_from(("b1", "b2")),
        st.sampled_from(BODIES),
    ),
    max_size=14,
)

Row = tuple[str, dt.datetime | None, int | None, str | None, str, str]


def _agenda(found: list[Row]) -> pl.DataFrame:
    rows = [
        {
            "id": doc,
            "beratung": f"{doc}/{consultation}",
            "top": f"{doc}/t{index:02d}",
            "organisationen": [body],
            "rolle": None,
            "sitzung": start,
            "nummer": None,
            "ordnung": order,
            "result": result,
        }
        for index, (doc, start, order, result, consultation, body) in enumerate(found)
    ]
    return pl.DataFrame(rows, schema=oc.AGENDA_SCHEMA).sort(oc.PROGRESS_ORDER, nulls_last=False)


CORPUS = pl.DataFrame(
    {"id": list(DOCS), "date": [dt.date(2021, 1, 1)] * len(DOCS)},
    schema={"id": pl.String, "date": pl.Date},
)


def _classify(agenda: pl.DataFrame) -> pl.DataFrame:
    return oc.classify_outcomes(CORPUS, oc.progress(agenda, {}, RESULTS), RESULTS)


def _classes(agenda: pl.DataFrame) -> dict[str, tuple[str, str | None]]:
    frame = _classify(agenda)
    return {r["id"]: (r["klasse"], r["entscheidung_top"]) for r in frame.iter_rows(named=True)}


@given(steps)
def test_the_rule_is_the_rule_of_the_measurement(found: list[Row]) -> None:
    agenda = _agenda(found)
    expected: dict[str, tuple[str, str | None]] = {}
    for doc in DOCS:
        mine = [
            Schritt(r["top"], r["sitzung"], r["ordnung"] or 0, r["result"])
            for r in agenda.filter(pl.col("id") == doc).iter_rows(named=True)
        ]
        name, step = klasse(mine, RESULTS)
        expected[doc] = (name, step.top if step else None)
    assert _classes(agenda) == expected


@given(steps, st.randoms(use_true_random=False))
def test_the_row_order_does_not_matter(found: list[Row], rnd: random.Random) -> None:
    agenda = _agenda(found)
    shuffled = agenda.sample(fraction=1.0, shuffle=True, seed=rnd.randrange(2**32))
    assert _classify(shuffled).equals(_classify(agenda))


# Review 2026-11-24, N7: auch den Verlauf selbst mischen, nicht nur die Eingabe von ``progress``,
# die ihn ohnehin sortiert. Ein Punkt darf dabei von zwei Beratungen genannt werden (dieselbe
# Sitzung, dasselbe Ergebnis, aber das Gremium der Beratung): dort entscheidet sonst die Zeilenfolge.
shared = st.lists(
    st.tuples(
        st.sampled_from(DOCS),
        st.integers(0, 3),  # der Punkt
        starts,
        st.one_of(st.none(), st.integers(0, 3)),
        st.one_of(st.none(), st.sampled_from(SACHE + STAND)),
        st.lists(st.sampled_from(BODIES), min_size=1, max_size=2, unique=True),  # je Beratung
    ),
    max_size=10,
)


def _shared_progress(
    found: list[tuple[str, int, dt.datetime | None, int | None, str | None, list[str]]],
) -> pl.DataFrame:
    rows: dict[tuple[str, str, str], dict[str, object]] = {}
    for doc, point, start, order, result, bodies in found:
        for number, body in enumerate(bodies):
            key = (doc, f"{doc}/b{number}", f"{doc}/t{point}")
            rows.setdefault(
                key,
                {
                    "id": doc,
                    "beratung": key[1],
                    "top": key[2],
                    "organisationen": [body],
                    "rolle": None,
                    "sitzung": start,
                    "nummer": None,
                    "ordnung": order,
                    "result": result,
                },
            )
    # derselbe Punkt trägt in jeder Zeile dieselbe Sitzung, Folge und denselben Eintrag
    first: dict[tuple[object, object], dict[str, object]] = {}
    for row in rows.values():
        owner = first.setdefault((row["id"], row["top"]), row)
        row.update({k: owner[k] for k in ("sitzung", "ordnung", "result")})
    agenda = pl.DataFrame(list(rows.values()), schema=oc.AGENDA_SCHEMA)
    return oc.progress(agenda.sort(oc.PROGRESS_ORDER, nulls_last=False), {}, RESULTS)


@given(shared, st.randoms(use_true_random=False))
def test_the_order_of_the_progress_itself_does_not_matter(
    found: list[tuple[str, int, dt.datetime | None, int | None, str | None, list[str]]],
    rnd: random.Random,
) -> None:
    verlauf = _shared_progress(found)
    shuffled = verlauf.sample(fraction=1.0, shuffle=True, seed=rnd.randrange(2**32))
    assert oc.decisions(shuffled, RESULTS).equals(oc.decisions(verlauf, RESULTS))


LATE = dt.datetime(2030, 1, 1, 12)  # nach jeder Sitzung der Strategie


@given(steps, st.sampled_from(SACHE), st.sampled_from(DOCS))
def test_a_later_decision_in_the_matter_decides(found: list[Row], value: str, doc: str) -> None:
    agenda = _agenda([*found, (doc, LATE, 0, value, "b9", "gr/1")])
    name, top = _classes(agenda)[doc]
    assert name == RESULTS[value][1]
    assert top is not None and agenda.filter(pl.col("top") == top).row(0, named=True)[
        "sitzung"
    ] == (LATE)


@given(steps, st.sampled_from(STAND), st.sampled_from(DOCS))
def test_a_later_state_never_replaces_a_decision(found: list[Row], value: str, doc: str) -> None:
    before = _classes(_agenda(found))[doc]
    after = _classes(_agenda([*found, (doc, LATE, 0, value, "b9", "gr/1")]))[doc]
    if before[0] in OUTCOME_STAGES["sache"]:
        assert after == before
    elif before[0] in ("erledigt", "vertagt", "offen", "ohne_ergebnis"):
        assert after[0] == RESULTS[value][1]


@given(steps)
def test_entries_and_classes_go_together(found: list[Row]) -> None:
    frame = _classify(_agenda(found))
    without = frame.filter(pl.col("klasse") == "ohne_ergebnis")
    assert without.get_column("result").null_count() == without.height
    assert frame.filter(pl.col("klasse") != "ohne_ergebnis").get_column("result").null_count() == 0
    assert set(frame.get_column("grob").to_list()) <= set(oc.COARSE.values())


# --- Praxiszellen ---------------------------------------------------------------------------------

cells = st.lists(
    st.tuples(
        st.sampled_from(("RAT", "BV1", None)),
        st.sampled_from((2014, 2015)),
        st.sampled_from(oc.CLASSES),
        st.sampled_from(("antrag", "vorlage")),
    ),
    max_size=60,
)


def _outcomes(found: list[tuple[str | None, int, str, str]], prefix: str) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [f"{prefix}{i:03d}" for i in range(len(found))],
            "rolle": [role for *_, role in found],
            "klasse": [name for _, _, name, _ in found],
            "entscheidung_gremium": [body for body, *_ in found],
            "entscheidung_datum": [
                None if name == "ohne_ergebnis" else dt.date(year, 6, 1)
                for _, year, name, _ in found
            ],
        },
        schema={
            "id": pl.String,
            "rolle": pl.String,
            "klasse": pl.String,
            "entscheidung_gremium": pl.String,
            "entscheidung_datum": pl.Date,
        },
    )


@given(cells, st.randoms(use_true_random=False), st.integers(1, 5))
def test_practice_cells_depend_only_on_body_year_and_class(
    found: list[tuple[str | None, int, str, str]], rnd: random.Random, minimum: int
) -> None:
    """Andere IDs, andere Tage im Jahr und eine andere Zeilenfolge ändern keine Zelle."""
    first = oc.practice_cells(_outcomes(found, "x"), 0.4, minimum)
    other = list(found)
    rnd.shuffle(other)
    moved = _outcomes(other, "y").with_columns(
        pl.col("entscheidung_datum").dt.offset_by(f"{rnd.randrange(0, 150)}d")
    )
    assert oc.practice_cells(moved, 0.4, minimum).equals(first)
    for row in first.iter_rows(named=True):
        assert row["erledigt"] >= minimum and row["erledigt"] >= 0.4 * row["n"]


# --- Antragserfolg ------------------------------------------------------------------------------

motions = st.lists(
    st.tuples(
        st.sampled_from(("RAT", "AUS", "BV1")),
        st.sampled_from(("beschlossen", "geaendert", "abgelehnt", "erledigt", "vertagt")),
        st.lists(st.sampled_from(("A", "B", "C")), max_size=3),
    ),
    min_size=1,
    max_size=40,
)


@given(motions)
def test_success_spreads_the_observed_over_each_stratum(
    found: list[tuple[str, str, list[str]]],
) -> None:
    """Review 2026-11-24, N2: je Gremium (Schicht) Σ angenommen = Σ erwartet über die Fraktionen."""
    ids = [f"{i:03d}" for i in range(len(found))]
    kinds = {"RAT": "rat", "AUS": "ausschuss", "BV1": "bezirksvertretung"}
    outcomes = pl.DataFrame(
        {
            "id": ids,
            "rolle": ["antrag"] * len(ids),
            "klasse": [name for _, name, _ in found],
            "eintrag_tragfaehig": [True] * len(ids),
        }
    )
    cosponsors = pl.DataFrame(
        {"id": ids, "fraktionen": [fractions for *_, fractions in found]},
        schema={"id": pl.String, "fraktionen": pl.List(pl.String)},
    )
    for body, kind in kinds.items():
        keep = [i for i, (b, *_) in zip(ids, found, strict=True) if b == body]
        bodies = pl.DataFrame(
            {"id": keep, "gremium": [body] * len(keep), "gremium_art": [kind] * len(keep)},
            schema={"id": pl.String, "gremium": pl.String, "gremium_art": pl.String},
        )
        success = oc.motion_success(
            outcomes.filter(pl.col("id").is_in(keep)), cosponsors, bodies, "p"
        )
        expected = float(success.get_column("erwartet").sum())
        observed = int(success.get_column("angenommen").sum())
        assert abs(expected - observed) < 1e-9
