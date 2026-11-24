"""Vorhaben 14: Eigenschaften der Kanten und des Waldes, für alle Eingaben.

* Die Baumregel macht aus jedem Graphen einen Wald: jede Wurzel zeigt auf sich, kein Kreis, die
  Tiefe wächst um eins je Schritt, und die Größen der Vorgänge summieren sich zur Zahl der
  Drucksachen.
* Ein Vorgänger ist immer älter, oder am selben Tag eine kleinere ID.
* Die Kanten hängen nicht von der Zeilenfolge der Eingabe ab (CLAUDE.md: nach jedem Join
  sortieren), und jede verbindet zwei Drucksachen der Stadt, nie eine mit sich selbst.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from pathlib import Path

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.procedures import (
    EDGE_SCHEMA,
    assemble_edges,
    build_directory,
    document_roles,
    forest,
    parents,
    scan,
    supplement_pairs,
)
from georep.prep.references import TREE_TYPES, ReferenceRules
from georep.settings import load_settings
from tests.procedures_city import documents

RULES = ReferenceRules.from_settings(load_settings(cwd=Path("/nonexistent")).procedures)
DAY = dt.date(2021, 1, 1)


@st.composite
def graphs(draw: st.DrawFn) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Bis zu zwölf Drucksachen mit Daten aus wenigen Tagen und beliebigen Kanten dazwischen."""
    n = draw(st.integers(1, 12))
    ids = [f"d{i:02d}" for i in range(n)]
    days = [DAY + dt.timedelta(days=draw(st.integers(0, 3))) for _ in ids]
    roles = pl.DataFrame(
        {
            "id": ids,
            "periode": [""] * n,
            "date": days,
            "rolle": ["antrag"] * n,
            "sammelbericht": [False] * n,
        }
    )
    pairs = draw(
        st.lists(st.tuples(st.integers(0, n - 1), st.integers(0, n - 1)), max_size=30, unique=True)
    )
    rows = [
        (
            ids[a],
            ids[b],
            draw(st.sampled_from([*TREE_TYPES, "bezug", "kontrolle"])),
            ["titel"],
            draw(st.booleans()),
            "titel",
            (days[a] - days[b]).days,
            "",
        )
        for a, b in pairs
        if a != b
    ]
    edges = pl.DataFrame(rows, schema=EDGE_SCHEMA, orient="row").with_columns(
        pl.when(pl.col("stark")).then(pl.col("quelle")).otherwise(pl.lit("text")).alias("quelle")
    )
    return edges, roles


@given(graph=graphs())
def test_the_tree_rule_makes_a_forest(graph: tuple[pl.DataFrame, pl.DataFrame]) -> None:
    edges, roles = graph
    ids = roles.get_column("id").to_list()
    tree = parents(edges, roles)
    day = dict(roles.select("id", "date").iter_rows())
    for child, (parent, _kind) in tree.items():
        assert (day[parent], parent) < (day[child], child)
    found = forest(tree, ids, ids)
    rows = {row["id"]: row for row in found.iter_rows(named=True)}
    for item, row in rows.items():
        root = rows[row["vorgang"]]
        assert root["vorgang"] == root["id"] and root["tiefe"] == 0
        if item in tree:
            assert row["tiefe"] == rows[tree[item][0]]["tiefe"] + 1
            assert row["vorgang"] == rows[tree[item][0]]["vorgang"]
    sizes = Counter(row["vorgang"] for row in rows.values())
    assert all(rows[item]["groesse"] == sizes[rows[item]["vorgang"]] for item in rows)
    assert sum(rows[root]["groesse"] for root in sizes) == len(ids)


@given(order=st.permutations(range(16)))
def test_edges_do_not_depend_on_the_row_order(order: list[int]) -> None:
    docs = documents()
    shuffled = docs[order]
    expected = _edges(docs)
    assert _edges(shuffled).equals(expected)


def _edges(docs: pl.DataFrame) -> pl.DataFrame:
    directory = build_directory(docs, RULES)
    found = scan(docs, directory, RULES)
    return assemble_edges(
        found.occurrences, supplement_pairs(directory), document_roles(docs, RULES)
    )


@given(
    texts=st.lists(
        st.lists(
            st.sampled_from(
                [
                    "rat/1/2021",
                    "ova/2/2021",
                    "ova/2/2021/1",
                    "bv1/3/2021",
                    "rat/99/2019",
                    "kua/10/2020",
                    "61/ 12/2014",
                    "xyz/9/2020",
                    "zur vorlage",
                    " ",
                    "beschluss",
                ]
            ),
            max_size=6,
        ).map(" ".join),
        min_size=16,
        max_size=16,
    )
)
def test_every_edge_joins_two_papers_of_the_city(texts: list[str]) -> None:
    docs = documents().with_columns(pl.Series("text", texts))
    edges = _edges(docs)
    known = set(docs.get_column("id").to_list())
    assert set(edges.get_column("von")) <= known and set(edges.get_column("nach")) <= known
    assert (edges.get_column("von") != edges.get_column("nach")).all()
