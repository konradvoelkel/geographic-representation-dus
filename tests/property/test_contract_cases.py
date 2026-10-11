"""deal.cases: hypothesis greift die Verträge direkt an.

Für jede reine Funktion mit Verträgen erzeugt deal.cases Eingaben aus den Typannotationen oder den
angegebenen Strategien, ruft die Funktion und prüft pre, post, ensure, raises und pure; eine in
deal.raises genannte Ausnahme gilt als erlaubt, Eingaben gegen eine Vorbedingung werden verworfen.
Polars-Funktionen bleiben außen vor, hypothesis baut keine DataFrames aus Typen; sie haben ihre
Invarianten in den anderen Modulen hier. check_types bleibt aus: typeguard ist nicht installiert,
und ``deal test`` ist mit typeguard 4 kaputt (docs/decisions.md, Punkt 15).
"""

from __future__ import annotations

import deal
from hypothesis import strategies as st

from georep.http import cache_pattern
from georep.prep.extract import after_marker, normalise_text
from georep.report.charts import nice_ticks
from georep.report.model import format_de
from georep.settings import deep_merge
from georep.sources.overpass import overpass_query, street_names
from georep.sources.wiki import geosearch_params, parse_point, sparql_query
from tests.property.oracle_matcher import oracle_extract

COUNT = 200
scalars = st.one_of(st.integers(), st.text(max_size=5), st.booleans(), st.none())
json_dicts = st.recursive(
    st.dictionaries(st.text(alphabet="abc", min_size=1, max_size=2), scalars, max_size=3),
    lambda children: st.dictionaries(
        st.text(alphabet="abc", min_size=1, max_size=2), children, max_size=3
    ),
    max_leaves=12,
)
points = st.one_of(
    st.text(max_size=20),
    st.builds("Point({} {})".format, st.floats(-200, 200), st.floats(-100, 100)),
    st.builds("Point({} {} {})".format, st.floats(), st.floats(), st.floats()),
)
words = st.text(alphabet="abcäöß -.,(0", min_size=0, max_size=8)


@deal.cases(after_marker, count=COUNT, check_types=False)
def test_after_marker(case: deal.TestCase) -> None:
    case()


@deal.cases(normalise_text, count=COUNT, check_types=False)
def test_normalise_text(case: deal.TestCase) -> None:
    case()


@deal.cases(
    deep_merge, count=COUNT, check_types=False, kwargs={"base": json_dicts, "override": json_dicts}
)
def test_deep_merge(case: deal.TestCase) -> None:
    case()


@deal.cases(cache_pattern, count=COUNT, check_types=False)
def test_cache_pattern(case: deal.TestCase) -> None:
    case()


@deal.cases(parse_point, count=COUNT, check_types=False, kwargs={"value": points})
def test_parse_point(case: deal.TestCase) -> None:
    case()


@deal.cases(overpass_query, count=50, check_types=False)
def test_overpass_query(case: deal.TestCase) -> None:
    case()


@deal.cases(geosearch_params, count=50, check_types=False)
def test_geosearch_params(case: deal.TestCase) -> None:
    case()


@deal.cases(sparql_query, count=50, check_types=False)
def test_sparql_query(case: deal.TestCase) -> None:
    case()


@deal.cases(
    street_names,
    count=COUNT,
    check_types=False,
    kwargs={
        "data": st.fixed_dictionaries(
            {
                "elements": st.lists(
                    st.fixed_dictionaries(
                        {"tags": st.fixed_dictionaries({"name": words}, optional={"x": words})}
                    ),
                    max_size=5,
                )
            }
        )
    },
)
def test_street_names(case: deal.TestCase) -> None:
    case()


@deal.cases(
    oracle_extract,
    count=COUNT,
    check_types=False,
    kwargs={"text": words, "terms": st.lists(words, max_size=5)},
)
def test_oracle_extract(case: deal.TestCase) -> None:
    case()


@deal.cases(
    format_de,
    count=COUNT,
    check_types=False,
    kwargs={
        "value": st.floats(allow_nan=False, allow_infinity=False),
        "decimals": st.integers(0, 8),
    },
)
def test_format_de(case: deal.TestCase) -> None:
    case()


@deal.cases(
    nice_ticks,
    count=COUNT,
    check_types=False,
    kwargs={
        "lo": st.floats(-1e9, 1e9, allow_nan=False),
        "hi": st.floats(-1e9, 1e9, allow_nan=False),
        "n": st.integers(1, 25),
    },
)
def test_nice_ticks(case: deal.TestCase) -> None:
    case()
