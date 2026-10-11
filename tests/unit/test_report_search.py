"""Sucheinträge der Berichtsseite auf kleinen Frames von Hand und auf der Mini-Fixture."""

from __future__ import annotations

import deal
import polars as pl
import pytest

from georep.errors import SchemaError
from georep.layout import Layout
from georep.report.search import (
    KIND_LABELS,
    SearchEntry,
    canonical_term,
    fold,
    fold_ascii,
    search_entries,
    search_payload,
)
from georep.search.dictionary import STREET_ABBREVIATIONS

LIST_OF_STR = pl.List(pl.String)


def _lists(rows: dict[int, list[str]]) -> pl.DataFrame:
    return pl.DataFrame(
        {"wahlkreis_id": list(rows), "suchbegriffe": list(rows.values())},
        schema={"wahlkreis_id": pl.Int64, "suchbegriffe": LIST_OF_STR},
    )


def _index(rows: dict[str, list[str]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "suchbegriffe": list(rows),
            "paper_ids": list(rows.values()),
            "anzahl_treffer": [len(v) for v in rows.values()],
        },
        schema={"suchbegriffe": pl.String, "paper_ids": LIST_OF_STR, "anzahl_treffer": pl.Int64},
    )


def _pois(labels: list[str]) -> pl.DataFrame:
    return pl.DataFrame({"label": labels}, schema={"label": pl.String})


def _results(hits: dict[int, int]) -> pl.DataFrame:
    return pl.DataFrame(
        {"wahlkreis_id": list(hits), "anzahl_treffer": list(hits.values())},
        schema={"wahlkreis_id": pl.Int64, "anzahl_treffer": pl.Int64},
    )


DICTIONARY = _lists(
    {
        1: ["adlerstr.", "adlerstraße", "burgplatz", "schulweg"],
        2: ["adlerstr.", "adlerstraße", "hofgarten", "nordstr."],
    }
)
INDEX = _index(
    {
        "adlerstr.": ["p1", "p2"],
        "adlerstraße": ["p2", "p3", "p4"],
        "burgplatz": ["p1"],
        "hofgarten": [],
        "nordstr.": ["p9"],
        "schulweg": ["p1", "p5"],
    }
)
STREETS = _lists({1: ["Adlerstraße", "Burgplatz"], 2: ["Adlerstraße", "Nordstr."]})
POIS = _pois(["Burgplatz", "Hofgarten"])
RESULTS = _results({1: 4, 2: 5})
NAMES = {1: "Altstadt, Carlstadt", 2: "Flingern Süd"}


@pytest.fixture(scope="module")
def entries() -> tuple[SearchEntry, ...]:
    return search_entries(DICTIONARY, INDEX, STREETS, POIS, RESULTS, NAMES, hidden=("schulweg",))


def test_canonical_term_replaces_every_abbreviation() -> None:
    assert canonical_term("münchener str.") == "münchener straße"
    assert canonical_term("str. am str.") == "straße am straße"
    assert canonical_term("hofgarten") == "hofgarten"
    assert canonical_term("rue x", (("rue", "r."),)) == "rue x"
    assert canonical_term("r. x", (("rue", "r."),)) == "rue x"


def test_canonical_term_refuses_an_abbreviation_inside_its_long_form() -> None:
    with pytest.raises(deal.PreContractError):
        canonical_term("x", (("strasse", "str"),))
    with pytest.raises(deal.PreContractError):
        canonical_term("x", (("straße", ""),))


def test_variants_collapse_into_the_long_form_with_the_union_of_documents(
    entries: tuple[SearchEntry, ...],
) -> None:
    by_term = {e.term: e for e in entries}
    assert "adlerstr." not in by_term
    adler = by_term["adlerstraße"]
    assert adler.districts == (1, 2) and adler.kind == "s"
    assert adler.documents == 4  # p1..p4, p2 nur einmal: Vereinigung, nicht Summe (2 + 3)


def test_kinds_come_from_streets_and_places(entries: tuple[SearchEntry, ...]) -> None:
    by_term = {e.term: e for e in entries}
    assert by_term["burgplatz"].kind == "so" and by_term["burgplatz"].documents == 1
    assert by_term["hofgarten"].kind == "o" and by_term["hofgarten"].documents == 0
    assert by_term["hofgarten"].districts == (2,)


def test_an_abbreviated_term_without_long_twin_stays_its_own_entry(
    entries: tuple[SearchEntry, ...],
) -> None:
    by_term = {e.term: e for e in entries}
    assert "nordstraße" not in by_term
    assert by_term["nordstr."] == SearchEntry("nordstr.", (2,), 1, "s")


def test_hidden_terms_are_missing(entries: tuple[SearchEntry, ...]) -> None:
    assert "schulweg" not in {e.term for e in entries}


def test_district_names_are_entries_with_the_district_hits(
    entries: tuple[SearchEntry, ...],
) -> None:
    names = [e for e in entries if e.kind == "w"]
    assert names == [
        SearchEntry("Altstadt, Carlstadt", (1,), 4, "w"),
        SearchEntry("Flingern Süd", (2,), 5, "w"),
    ]


def test_entries_are_sorted_by_term_and_kind(entries: tuple[SearchEntry, ...]) -> None:
    keys = [(e.term, e.kind) for e in entries]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)
    assert all(e.districts == tuple(sorted(set(e.districts))) and e.districts for e in entries)
    assert len(entries) == 6  # adlerstraße, burgplatz, hofgarten, nordstr. und zwei Namen


def test_search_entries_require_the_columns() -> None:
    with pytest.raises(deal.PreContractError):
        search_entries(
            DICTIONARY.rename({"suchbegriffe": "t"}), INDEX, STREETS, POIS, RESULTS, NAMES, ()
        )
    with pytest.raises(deal.PreContractError):
        search_entries(DICTIONARY, INDEX.drop("paper_ids"), STREETS, POIS, RESULTS, NAMES, ())


def test_a_district_without_name_or_a_term_without_source_is_a_schema_error() -> None:
    with pytest.raises(SchemaError, match="ohne Namen"):
        search_entries(DICTIONARY, INDEX, STREETS, POIS, RESULTS, {1: "Eins"}, ())
    with pytest.raises(SchemaError, match="ohne Quelle"):
        search_entries(DICTIONARY, INDEX, _lists({1: []}), _pois([]), RESULTS, NAMES, ())


def test_payload_schema(entries: tuple[SearchEntry, ...]) -> None:
    payload = search_payload(entries, version="1.2.3")
    assert list(payload) == ["version", "abbreviations", "kinds", "entries"]
    assert payload["version"] == "1.2.3"
    assert payload["abbreviations"] == [list(pair) for pair in STREET_ABBREVIATIONS]
    assert payload["kinds"] == KIND_LABELS == {"s": "Straße", "o": "Ort", "w": "Wahlbezirk"}
    assert payload["entries"] == [[e.term, list(e.districts), e.documents, e.kind] for e in entries]
    assert payload["entries"][0] == ["Altstadt, Carlstadt", [1], 4, "w"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Münchener Str.", "munchener strasse"),
        ("münchener str", "munchener strasse"),
        ("südstr", "sudstrasse"),
        ("SÜDSTRASSE", "sudstrasse"),
        ("  auf'm   hennekamp ", "auf'm hennekamp"),
        ("café ōsaka", "cafe osaka"),
        ("straße", "strasse"),
        ("strandbad", "strandbad"),
    ],
)
def test_fold_mirrors_the_javascript(query: str, expected: str) -> None:
    assert fold(query) == expected


def test_fold_ascii_writes_umlauts_as_two_letters() -> None:
    assert fold_ascii("Münchener Str.") == "muenchener strasse"
    assert fold_ascii("Königsallee") == "koenigsallee"
    assert fold_ascii("südstr") == "suedstrasse"
    assert fold_ascii("hofgarten") == fold("hofgarten") == "hofgarten"


def test_mini_fixture_entries_cover_every_canonical_term(mini_run: Layout) -> None:
    from georep.geo import read_precincts
    from georep.report.model import district_names
    from georep.settings import load_settings

    settings = load_settings(cwd=mini_run.root)
    dictionary = pl.read_parquet(mini_run.dictionary)
    precincts = read_precincts(
        mini_run.districts_geojson, settings.columns, settings.geo.working_crs
    )
    entries = search_entries(
        dictionary,
        pl.read_parquet(mini_run.index),
        pl.read_parquet(mini_run.streets_by_district),
        pl.read_parquet(mini_run.pois_table),
        pl.read_parquet(mini_run.results),
        district_names(precincts),
        tuple(settings.search.hide_in_display),
    )
    terms = set(dictionary.get_column("suchbegriffe").explode().to_list()) - {"schulweg"}
    canonical = {t if canonical_term(t) not in terms else canonical_term(t) for t in terms}
    assert {e.term for e in entries if e.kind != "w"} == canonical
    assert [e.term for e in entries if e.kind == "w"] == [
        "Altstadt, Carlstadt, Hofgarten",
        "Flingern Süd",
        "Hassels, Paulsmühle",
    ]
    assert sum(1 for e in entries if "s" in e.kind) and sum(1 for e in entries if "o" in e.kind)
    folded = [(fold(e.term), e.kind) for e in entries]
    assert len(set(folded)) == len(folded)  # keine zwei Einträge derselben Art fallen zusammen
