"""Der Beitrag von Vorhaben 16 im Register: ein früher Schritt ``places``, drei Dateien.

``places`` steht hinter ``sections`` (Vorhaben 11) und vor ``weights`` (Punkt 74), weil die Stelle
eines Treffers aus den Abschnitten kommt und ``weights`` sie liest (Messdokument
``docs/plans/16-ortsbezug.md``, § 10, Punkt 4). Ohne Rohtext (die Mini-Fixture, auf Pages jedes
Profil außer der Hauptperiode) schreibt er keine Spanne, aber je Paar der Suche eine Zeile ohne
Stelle. Mit Rohtext liegt jede Spanne auf dem Rohtext, in F3, mit wörtlichem ``value`` und dem Begriff
in ``norm``; jede Korpus-ID einer geteilten Datei bekommt ihre Zeilen. Synthetische Texte, keine
echten Adressen.
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl
import pytest

from georep.enrich.places import (
    ADDRESS_COLUMNS,
    EXTRACTOR,
    PAIR_SCHEMA,
    PLACES_SCHEMA_VERSION,
    SPAN_EXTRA,
    pair_table,
    place_tables,
    places_files,
    places_steps,
)
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.prep.addresses import EXACT, NO_NUMBER, AddressBook, address_files
from georep.prep.raw_texts import flatten
from georep.search.positions import BODY, CORE, SUBJECT, PlaceRules
from georep.settings import Settings
from georep.spans import SPAN_SCHEMA, check_spans
from georep.stores import stored_schema_version
from tests.fakes import FakeSession

HTTP = FakeSession({})  # der Schritt ist offline und fragt nie
MARKER = "betrifft"
RAW = (
    "Kopf Kürtenstraße 9\nBetrifft: Poller Kürtenstraße 12\nSachdarstellung:\n7 Am Wehrhahn.\n"
    "Die Verwaltung berichtet, dass die Kürtenstraße bis zum Ende des Jahres gesperrt bleibt."
)
RAW_EXTRACTOR = "pypdf-7.1.0+roh"


def _layout(tmp_path: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")


def test_the_step_stands_after_sections_and_before_weights(
    tmp_path: Path, default_settings: Settings
) -> None:
    names = [s.name for s in build_steps(default_settings, _layout(tmp_path))]
    assert names.index("sections") < names.index("places") < names.index("weights")


def test_the_switch_decides_whether_the_step_exists(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _layout(tmp_path)
    places = default_settings.places
    off = default_settings.model_copy(
        update={"places": places.model_copy(update={"enabled": False})}
    )
    assert places_steps(off, layout, HTTP) == []
    [step] = places_steps(default_settings, layout, HTTP)
    files = places_files(layout)
    assert step.outputs == (files.spans, files.pairs, files.addresses)
    assert files.spans == layout.processed / "treffer_stellen.parquet"
    assert files.pairs == layout.processed / "dokumente_wahlbezirke_stelle.parquet"
    assert files.addresses == layout.processed / "adressen_wahlbezirke.parquet"
    assert step.schema_version == PLACES_SCHEMA_VERSION
    assert address_files(layout).table in step.inputs
    without = default_settings.model_copy(
        update={"places": places.model_copy(update={"house_numbers": False})}
    )
    [plain] = places_steps(without, layout, HTTP)
    assert address_files(layout).table not in plain.inputs
    assert {layout.corpus, layout.raw_texts, layout.dictionary, layout.index} <= set(plain.inputs)


def _documents() -> pl.DataFrame:
    """Zwei Korpus-IDs teilen eine Datei (d1, d2), eine hat keinen Rohtext (d3)."""
    store = flatten(RAW, MARKER, ())
    return pl.DataFrame(
        {
            "id": ["d1", "d2", "d3"],
            "name": ["Poller in der Kürtenstraße", "Sachstand", "Ohne Text"],
            "text": [store, store, "kürtenstraße"],
            "raw": [RAW, RAW, None],
            "form_feeds": [[], [], None],
            "extractor": [RAW_EXTRACTOR, RAW_EXTRACTOR, None],
        },
        schema={
            "id": pl.String,
            "name": pl.String,
            "text": pl.String,
            "raw": pl.String,
            "form_feeds": pl.List(pl.Int64),
            "extractor": pl.String,
        },
    )


def _sections() -> pl.DataFrame:
    """Abschnitte wie aus Vorhaben 11: Betreff in Zeile 2, Sachdarstellung ab Zeile 3."""
    betreff = RAW.index("Betrifft")
    sach = RAW.index("Sachdarstellung")
    rows = [
        (doc, betreff, sach - 1, "abschnitt", "", "betreff", "betreff", "struktur-1/x")
        for doc in ("d1", "d2")
    ] + [
        (doc, sach, len(RAW), "abschnitt", "", "sachdarstellung", "sachdarstellung", "struktur-1/x")
        for doc in ("d1", "d2")
    ]
    return pl.DataFrame(rows, schema=SPAN_SCHEMA, orient="row").sort("id", "start")


def _book() -> AddressBook:
    table = pl.DataFrame(
        {
            "strasse": ["kürtenstraße", "kürtenstraße"],
            "nr": [12, 12],
            "zusatz": ["", ""],
            "stimmbezirk_id": ["0101", "0201"],
            "wahlkreis_id": [1, 2],
        },
        schema={
            "strasse": pl.String,
            "nr": pl.UInt16,
            "zusatz": pl.String,
            "stimmbezirk_id": pl.String,
            "wahlkreis_id": pl.Int64,
        },
    )
    return AddressBook.from_table(table)


RULES = PlaceRules(60, 12, re.compile(r"\s{0,3}(?P<nr>\d{1,3})(?:(?P<zusatz>[a-z]))?(?!\d)"))
TERMS = ("am wehrhahn", "kürtenstraße")
STREETS = frozenset({"kürtenstraße"})


def test_spans_lie_on_the_raw_text_with_their_position() -> None:
    result = place_tables(_documents(), _sections(), TERMS, STREETS, _book(), RULES, MARKER)
    spans = result.spans
    assert list(spans.columns) == [*SPAN_SCHEMA, *SPAN_EXTRA]
    check_spans(spans, {"d1": len(RAW), "d2": len(RAW)}, texts={"d1": RAW, "d2": RAW})
    assert result.bridged == 2 and result.without_bridge == 0
    mine = spans.filter(pl.col("id") == "d1")
    # „Kopf Kürtenstraße 9" steht vor dem Marker: nicht im Textstore, kein Treffer
    assert mine.select("value", "norm", "section", "stelle").rows() == [
        ("Kürtenstraße", "kürtenstraße", "betreff", SUBJECT),
        ("Am Wehrhahn", "am wehrhahn", "sachdarstellung", BODY),
        ("Kürtenstraße", "kürtenstraße", "sachdarstellung", BODY),
    ]
    assert mine.get_column("im_titel").to_list() == [True, False, True]
    assert mine.get_column("listenzeile").to_list() == [False, True, False]
    assert mine.get_column("hausnummer").to_list() == [True, False, False]
    assert set(spans.get_column("extractor").to_list()) == {f"{EXTRACTOR}/{RAW_EXTRACTOR}"}
    # die zweite ID derselben Datei: dieselben Stellen, ihr eigener Titel
    theirs = spans.filter(pl.col("id") == "d2")
    assert theirs.drop("id", "im_titel").equals(mine.drop("id", "im_titel"))
    assert not any(theirs.get_column("im_titel").to_list())


def test_an_address_is_kept_locally_with_its_districts() -> None:
    result = place_tables(_documents(), _sections(), TERMS, STREETS, _book(), RULES, MARKER)
    addresses = result.addresses
    assert list(addresses.columns) == list(ADDRESS_COLUMNS)
    assert addresses.filter(pl.col("id") == "d1").select(
        "begriff", "nr", "zusatz", "status", "wahlkreis_id"
    ).rows() == [("kürtenstraße", 12, "", EXACT, 1), ("kürtenstraße", 12, "", EXACT, 2)]
    unknown = AddressBook({"kürtenstraße": {}})
    found = place_tables(_documents(), _sections(), TERMS, STREETS, unknown, RULES, MARKER)
    assert found.addresses.filter(pl.col("id") == "d1").select("status", "wahlkreis_id").rows() == [
        (NO_NUMBER, None)
    ]


def test_without_a_bridge_a_document_has_no_spans() -> None:
    documents = _documents().with_columns(
        pl.when(pl.col("id") == "d2").then(pl.lit("anders")).otherwise(pl.col("text")).alias("text")
    )
    result = place_tables(documents, _sections(), TERMS, STREETS, None, RULES, MARKER)
    assert set(result.spans.get_column("id").to_list()) == {"d1"}
    assert result.bridged == 1 and result.without_bridge == 1
    assert result.addresses.height == 0  # ohne Adressbuch keine Adressen


def test_the_pair_table_has_every_pair_of_the_search() -> None:
    result = place_tables(_documents(), _sections(), TERMS, STREETS, _book(), RULES, MARKER)
    triples = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2, 2, 1],
            "id": ["d1", "d1", "d2", "d3"],
            "suchbegriffe": ["kürtenstraße", "am wehrhahn", "am wehrhahn", "kürtenstraße"],
        },
        schema={"wahlkreis_id": pl.Int64, "id": pl.String, "suchbegriffe": pl.String},
    )
    pairs = pair_table(result.spans, result.addresses, triples, house_numbers=True)
    assert pairs.schema == pl.Schema(PAIR_SCHEMA)
    rows = {(r["id"], r["wahlkreis_id"]): r for r in pairs.iter_rows(named=True)}
    assert set(rows) == {("d1", 1), ("d1", 2), ("d2", 2), ("d3", 1)}
    assert rows[("d1", 1)]["stelle"] == "titel" and rows[("d1", 1)]["handelt_von"]
    assert rows[("d1", 1)]["wahlkreis_adresse"] is True  # Kürtenstraße 12 liegt in 1 (und 2)
    # Am Wehrhahn in einer Listenzeile: Nebenregel C, aber keine Adresse; die Kürtenstraße 12
    # liegt auch in 2, doch dort führt das Wörterbuch sie nicht
    assert rows[("d1", 2)]["stelle"] == BODY and rows[("d1", 2)]["handelt_von"]
    assert rows[("d1", 2)]["wahlkreis_adresse"] is False
    assert rows[("d3", 1)]["stelle"] is None and rows[("d3", 1)]["handelt_von"] is None
    assert rows[("d3", 1)]["wahlkreis_adresse"] is None and rows[("d3", 1)]["extractor"] is None
    assert rows[("d1", 1)]["extractor"] == f"{EXTRACTOR}/{RAW_EXTRACTOR}"
    plain = pair_table(result.spans, result.addresses, triples, house_numbers=False)
    assert plain.get_column("wahlkreis_adresse").null_count() == plain.height


@pytest.mark.parametrize("name", ["spans", "pairs", "addresses"])
def test_without_raw_text_the_step_writes_its_files_without_position(
    mini_run: Layout, name: str
) -> None:
    files = places_files(mini_run)
    path = getattr(files, name)
    assert stored_schema_version(path) == str(PLACES_SCHEMA_VERSION)
    frame = pl.read_parquet(path)
    if name == "pairs":
        assert frame.schema == pl.Schema(PAIR_SCHEMA)
        assert frame.height > 0 and frame.get_column("stelle").null_count() == frame.height
        # je Paar (Dokument, Wahlbezirk) der Suche eine Zeile: so viele, wie die Arbeit zählt
        counted = pl.read_parquet(mini_run.results).get_column("anzahl_treffer").sum()
        assert frame.height == counted
    else:
        assert frame.height == 0


def test_core_positions_count_for_rule_c() -> None:
    """Ein Begriff im Kern handelt von seinem Ort, auch ohne Liste (Nebenregel C)."""
    raw = "Betrifft: Antrag\nBeschlussvorschlag:\nDer Poller auf der Kürtenstraße wird gebaut."
    store = flatten(raw, MARKER, ())
    documents = pl.DataFrame(
        {
            "id": ["d9"],
            "name": [""],
            "text": [store],
            "raw": [raw],
            "form_feeds": [[]],
            "extractor": [RAW_EXTRACTOR],
        },
        schema={
            "id": pl.String,
            "name": pl.String,
            "text": pl.String,
            "raw": pl.String,
            "form_feeds": pl.List(pl.Int64),
            "extractor": pl.String,
        },
    )
    start = raw.index("Beschlussvorschlag")
    sections = pl.DataFrame(
        [("d9", start, len(raw), "abschnitt", "", "beschlussvorschlag", "beschlussvorschlag", "s")],
        schema=SPAN_SCHEMA,
        orient="row",
    )
    result = place_tables(documents, sections, TERMS, STREETS, None, RULES, MARKER)
    assert result.spans.get_column("stelle").to_list() == [CORE]
