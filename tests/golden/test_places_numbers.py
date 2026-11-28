"""Vorhaben 16 über die Hauptperiode, gegen die Messung und gegen die Ausgabe des Verfahrens.

Zwei Arten von Zahlen. **Das Verfahren als Regressionstest**: an den 300 kodierten Paaren beider
Runden (``validierung/16-ortsbezug/verfahren.csv``, die Ausgabe von ``ortsbezug-entwurf-2`` aus dem
Messskript, nur IDs und Wahrheitswerte) muss ``handelt_von`` des Schritts ``places`` Paar für Paar
dasselbe sagen; an diesen Paaren ist Nebenregel C bestätigt (Messdokument
``docs/plans/16-ortsbezug.md``, § 4.4, F1 0,828). **Die Messung**: die Treffer mit Stelle sind genau
die des Index, keines zusätzlich (§ 3.0), mit den Verteilungen aus § 3.1, Nebenregel C an 21 951
Paaren (§ 3.2) und 92,3 % verortbaren Adressen (§ 3.4, Untergrenze 0,90).

Der Korpus entsteht wie in ``georep run``: ``bootstrap`` aus den Datenpaketen im Repo (darunter das
Rohtextpaket der Hauptperiode, Fundament F1, und das Adresspaket), dann die Schritte bis ``places``.
"""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest

from georep.bootstrap import bootstrap_from_settings
from georep.enrich.places import places_files
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.addresses import LOCATED
from georep.settings import load_settings

pytestmark = pytest.mark.slow

REPO = Path(__file__).resolve().parents[2]
VERFAHREN = REPO / "validierung" / "16-ortsbezug" / "verfahren.csv"
NOWHERE = Path("/nonexistent")
STEPS = [
    "shapes",
    "voters",
    "streets",
    "pois",
    "dictionary",
    "corpus",
    "index",
    "results",
    "sections",
    "places",
]
# Gemessen am 2026-11-23 (Messdokument § 3.0 bis § 3.4), nachgerechnet am 2026-11-28 aus den Paketen
MENTIONS = 66_004
TERM_PAIRS = 30_695  # (Dokument, Begriff) mit Stelle; der Index hat 30 859
PAIRS = 29_330  # (Dokument, Wahlbezirk) = Summe der Treffer aller Bezirke
LOCATED_PAIRS = 29_289  # die 41 übrigen aus einem Dokument ohne Rohtext (Frage 9.9)
RULE_C = 21_951  # 74,9 % der Paare mit Stelle (§ 3.2)
BEST = {"titel": 11_903, "betreff": 194, "kern": 5_060, "begleittext": 12_050, "rest": 82}
FINE = {
    "sachdarstellung": 25_431,
    "beschlussvorschlag": 9_977,
    "betreff": 8_293,
    "rumpf": 7_512,
    "begruendung": 7_327,
    "beschlusslage": 2_480,
    "stellungnahme": 2_298,
    "fragen": 1_641,
    "anlagen": 910,
    # „hinter dem Schluss, Nachrichtlich, Kopf" (§ 3.1: zusammen 135)
    "": 94,
    "nachrichtlich": 39,
    "kopf_amt": 2,
}
ADDRESSES = 10_944  # Erwähnungen einer Straße mit Hausnummer dahinter
LOCATED_ADDRESSES = 10_097  # genau 9 879, Hauptnummer 218: 92,3 % (91,7–92,7)


@dataclass(frozen=True)
class Run:
    layout: Layout
    spans: pl.DataFrame
    pairs: pl.DataFrame
    addresses: pl.DataFrame


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> Run:
    root = tmp_path_factory.mktemp("places")
    settings = load_settings(profile="duesseldorf", cwd=NOWHERE).model_copy(
        update={"data_root": root / "data", "cache_root": root / "cache"}
    )
    layout = Layout.from_settings(settings)
    bootstrap_from_settings(layout, settings)
    outcomes = run_pipeline(build_steps(settings, layout), settings, STEPS)
    assert all(o.status == "ausgeführt" for o in outcomes), [o.line() for o in outcomes]
    files = places_files(layout)
    return Run(
        layout,
        pl.read_parquet(files.spans),
        pl.read_parquet(files.pairs),
        pl.read_parquet(files.addresses),
    )


def _key(doc: str, district: int) -> str:
    """Der Schlüssel eines Paars wie im Messskript (``pair_key``): SHA-1 über „ID|Wahlbezirk"."""
    return hashlib.sha1(f"{doc}|{district}".encode()).hexdigest()[:12]


def test_the_procedure_says_the_same_at_the_300_coded_pairs(run: Run) -> None:
    with VERFAHREN.open(encoding="utf-8") as handle:
        expected = {row["paar"]: row["ortsbezug"] == "true" for row in csv.DictReader(handle)}
    assert len(expected) == 300
    found = {
        _key(doc, int(district)): about
        for doc, district, about in run.pairs.select(
            "id", "wahlkreis_id", "handelt_von"
        ).iter_rows()
    }
    assert {key: found.get(key) for key in expected} == expected


def test_the_hits_with_position_are_exactly_those_of_the_index(run: Run) -> None:
    assert run.spans.height == MENTIONS
    with_position = set(run.spans.select("id", "norm").unique().iter_rows())
    index = set(
        pl.read_parquet(run.layout.index)
        .select("suchbegriffe", "paper_ids")
        .explode("paper_ids")
        .drop_nulls()
        .select("paper_ids", "suchbegriffe")
        .iter_rows()
    )
    assert len(with_position) == TERM_PAIRS and with_position <= index
    documents = {doc for doc, _ in with_position}
    assert {pair for pair in index if pair[0] in documents} == with_position
    # die übrigen Paare des Index stammen aus Dokumenten ohne Rohtext, keines aus einem mit
    assert len({doc for doc, _ in index - with_position}) == 1


def test_the_positions_have_the_distributions_of_the_measurement(run: Run) -> None:
    assert dict(Counter(run.spans.get_column("section").to_list())) == FINE
    assert run.pairs.height == PAIRS
    located = run.pairs.filter(pl.col("stelle").is_not_null())
    assert located.height == LOCATED_PAIRS
    assert dict(Counter(located.get_column("stelle").to_list())) == BEST
    assert int(located.get_column("handelt_von").sum()) == RULE_C


def test_house_numbers_are_located_like_the_measurement(run: Run) -> None:
    mentions = run.addresses.unique(["id", "start"])
    located = mentions.filter(pl.col("status").is_in(list(LOCATED)))
    assert mentions.height == ADDRESSES and located.height == LOCATED_ADDRESSES
    assert located.height / mentions.height >= 0.90
    assert run.pairs.get_column("wahlkreis_adresse").null_count() == PAIRS - LOCATED_PAIRS
