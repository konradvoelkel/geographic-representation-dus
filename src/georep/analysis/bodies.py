"""Kennzahlen je Wahlbezirk und je Gremium (Option 5).

Die Auswertung der Arbeit sagt, welche Dokumente in einem Wahlbezirk Treffer haben
(``paper_ids``); ``prep.bodies`` sagt, aus welchem Gremium ein Dokument kommt; der Crosswalk sagt,
in welchen Stadtbezirken ein Wahlbezirk liegt. Daraus entstehen hier die sechs Trefferklassen je
Wahlbezirk („eigene Bezirksvertretung", „andere", Rat, Ausschüsse, Beiräte, unbekannt) und die
Lokalität je Gremium. „Eigen" ist eine Bezirksvertretung, deren Stadtbezirk Wahlberechtigte des
Wahlbezirks enthält; 40 der 41 Wahlbezirke liegen in genau einem Stadtbezirk, einer in zwei
(docs/plans/05-gremien.md, Entscheidung 4, und die Fußnote auf der Seite).

Die Klassen werden über explizite Bedingungen summiert, nicht mit ``pivot``: eine Klasse, die in
keinem Bezirk vorkommt, muss eine Spalte mit Nullen ergeben und keine fehlende Spalte. Die
Verträge an der Batch-Grenze sichern zu, dass die sechs Klassen zusammen die Treffer des Bezirks
ergeben und jeder Anteil in [0, 1] liegt.
"""

from __future__ import annotations

import deal
import polars as pl

from georep.analysis.hits import DISTRICT
from georep.contracts import has_columns, parts_sum_to, shares_in_unit_interval, sorted_unique
from georep.crosswalk import WEIGHT
from georep.errors import SchemaError
from georep.prep.bodies import (
    ADVISORY,
    BODY,
    CITY_DISTRICT,
    COMMITTEE,
    COUNCIL,
    DISTRICT_BODY,
    ID,
    KIND,
    UNKNOWN,
)
from georep.prep.voters import TURNOUT, UNIT
from georep.search.index import HITS, PAPER_IDS

# ``prep.bodies.CITY_DISTRICT`` und ``prep.voters.UNIT`` sind dieselbe Spalte „stadtbezirk": der
# Stadtbezirk eines Gremiums und der eines Wahlbezirks: darum trägt der Join unten beide Namen.
assert UNIT == CITY_DISTRICT
UNITS = "stadtbezirke"  # alle Stadtbezirke des Wahlbezirks, nach Gewicht absteigend
OWN = "treffer_eigene_bv"
OTHER = "treffer_andere_bv"
COUNCIL_HITS = "treffer_rat"
COMMITTEE_HITS = "treffer_ausschuss"
ADVISORY_HITS = "treffer_beirat"
UNKNOWN_HITS = "treffer_unbekannt"
PARTS = (OWN, OTHER, COUNCIL_HITS, COMMITTEE_HITS, ADVISORY_HITS, UNKNOWN_HITS)
OWN_SHARE = "anteil_eigene_bv"
COUNCIL_SHARE = "anteil_rat"
OWN_RATE = "quote_eigene_bv"
DISTRICT_BODY_COLUMNS = [DISTRICT, UNITS, HITS, *PARTS, OWN_SHARE, COUNCIL_SHARE, OWN_RATE]

DOCUMENTS = "dokumente"
WITH_HITS = "mit_treffer"
LOCAL_SHARE = "anteil_eigener_stadtbezirk"
BODY_COLUMNS = [BODY, KIND, UNIT, DOCUMENTS, WITH_HITS, LOCAL_SHARE]
NO_BODY = ""  # Kürzel eines Dokuments, dessen Nummer kein Muster trifft; null wäre kein Schlüssel

_OWN = "_eigen"  # Hilfsspalte: dieses Dokument-Bezirk-Paar kommt aus der eigenen Bezirksvertretung


def _exploded_hits(
    results: pl.DataFrame, papers: pl.DataFrame, units: pl.DataFrame
) -> pl.DataFrame:
    """Ein Dokument-Bezirk-Paar je Zeile, mit Gremium, Klasse und der Marke „eigen"."""
    pairs = (
        # Der Cast ist nötig, wenn kein Wahlbezirk Treffer hat: eine Spalte aus nur leeren Listen
        # ist List(Null), und der Join auf die Dokument-IDs scheitert dann an den Typen.
        results.select(DISTRICT, pl.col(PAPER_IDS).cast(pl.List(pl.String)))
        .explode(PAPER_IDS)
        .drop_nulls(PAPER_IDS)
        .join(
            papers.select(pl.col(ID).alias(PAPER_IDS), BODY, KIND, UNIT),
            on=PAPER_IDS,
            how="left",
        )
    )
    unmatched = pairs.filter(pl.col(KIND).is_null())
    if unmatched.height:
        missing = sorted(set(unmatched.get_column(PAPER_IDS)))[:3]
        raise SchemaError(
            f"{unmatched.height} Treffer verweisen auf Dokumente ohne Gremium, etwa {missing}; "
            "der Schritt bodies muss zum Korpus der Auswertung passen."
        )
    own = units.select(DISTRICT, UNIT).with_columns(pl.lit(True).alias(_OWN))
    return pairs.join(own, on=[DISTRICT, UNIT], how="left").with_columns(
        pl.col(_OWN).fill_null(False)
    )


def _same_districts(
    results: pl.DataFrame,
    papers: pl.DataFrame,
    units: pl.DataFrame,
    eligible_column: str,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return set(result.get_column(DISTRICT)) == set(results.get_column(DISTRICT))


@deal.pre(
    lambda results, papers, units, eligible_column: (
        has_columns(results, DISTRICT, PAPER_IDS, HITS, eligible_column)
        and has_columns(papers, ID, BODY, KIND, UNIT)
        and has_columns(units, DISTRICT, UNIT, WEIGHT)
    ),
    message="Auswertung, Gremien je Dokument und Gewichte je Wahlbezirk",
)
@deal.pre(
    lambda results, papers, units, eligible_column: bool(
        (results.get_column(eligible_column) > 0).all()
    ),
    message="Wahlberechtigte je Wahlbezirk positiv, sonst ist die Quote undefiniert",
)
@deal.post(lambda result: result.columns == DISTRICT_BODY_COLUMNS)
@deal.post(lambda result: sorted_unique(result, DISTRICT))
@deal.post(
    lambda result: parts_sum_to(result, PARTS, HITS),
    message="die sechs Klassen ergeben die Treffer des Bezirks",
)
@deal.post(
    lambda result: shares_in_unit_interval(result, OWN_SHARE, COUNCIL_SHARE),
    message="Anteile in [0, 1]",
)
@deal.ensure(_same_districts, message="genau die Wahlbezirke der Auswertung")
@deal.raises(SchemaError)
def hits_by_body(
    results: pl.DataFrame, papers: pl.DataFrame, units: pl.DataFrame, eligible_column: str
) -> pl.DataFrame:
    """Je Wahlbezirk die Treffer nach Gremium, die zwei Anteile und die Quote der eigenen BV."""
    pairs = _exploded_hits(results, papers, units)
    counted = pairs.group_by(DISTRICT).agg(
        pl.col(_OWN).sum().cast(pl.Int64).alias(OWN),
        ((pl.col(KIND) == DISTRICT_BODY) & ~pl.col(_OWN)).sum().cast(pl.Int64).alias(OTHER),
        (pl.col(KIND) == COUNCIL).sum().cast(pl.Int64).alias(COUNCIL_HITS),
        (pl.col(KIND) == COMMITTEE).sum().cast(pl.Int64).alias(COMMITTEE_HITS),
        (pl.col(KIND) == ADVISORY).sum().cast(pl.Int64).alias(ADVISORY_HITS),
        (pl.col(KIND) == UNKNOWN).sum().cast(pl.Int64).alias(UNKNOWN_HITS),
    )
    # Der Hauptstadtbezirk steht vorn: nach Gewicht absteigend, bei Gleichstand nach Nummer. Die
    # Reihenfolge steht hier explizit, nicht als Verlass auf die Sortierung der Eingabe.
    listed = units.group_by(DISTRICT).agg(
        pl.col(UNIT).sort_by([pl.col(WEIGHT), pl.col(UNIT)], descending=[True, False]).alias(UNITS)
    )
    share = pl.when(pl.col(HITS) > 0).then(pl.col(OWN) / pl.col(HITS)).otherwise(0.0)
    council_share = (
        pl.when(pl.col(HITS) > 0).then(pl.col(COUNCIL_HITS) / pl.col(HITS)).otherwise(0.0)
    )
    return (
        results.select(DISTRICT, HITS, pl.col(eligible_column))
        .join(listed, on=DISTRICT, how="left")
        .join(counted, on=DISTRICT, how="left")
        .with_columns(
            pl.col(UNITS).fill_null(pl.lit([], dtype=pl.List(pl.Int64))),
            *[pl.col(part).fill_null(0) for part in PARTS],
        )
        .with_columns(
            share.alias(OWN_SHARE),
            council_share.alias(COUNCIL_SHARE),
            (pl.col(OWN) / pl.col(eligible_column)).alias(OWN_RATE),
        )
        .select(DISTRICT_BODY_COLUMNS)
        .sort(DISTRICT)
    )


def _documents_add_up(
    papers: pl.DataFrame,
    results: pl.DataFrame,
    units: pl.DataFrame,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    return int(result.get_column(DOCUMENTS).sum()) == papers.height


@deal.pre(
    lambda papers, results, units: (
        has_columns(papers, ID, BODY, KIND, UNIT)
        and has_columns(results, DISTRICT, PAPER_IDS)
        and has_columns(units, DISTRICT, UNIT, WEIGHT)
    ),
    message="Gremien je Dokument, Auswertung und Gewichte je Wahlbezirk",
)
@deal.post(lambda result: result.columns == BODY_COLUMNS)
@deal.post(lambda result: sorted_unique(result, BODY), message="eine Zeile je Kürzel, sortiert")
@deal.post(
    lambda result: bool(
        (result.get_column(DOCUMENTS) >= result.get_column(WITH_HITS)).all()
        and (result.get_column(WITH_HITS) >= 0).all()
    ),
    message="Dokumente mit Treffer sind eine Teilmenge der Dokumente",
)
@deal.post(
    lambda result: shares_in_unit_interval(result.drop_nulls(LOCAL_SHARE), LOCAL_SHARE),
    message="die Lokalität ist ein Anteil",
)
@deal.ensure(_documents_add_up, message="jedes Dokument zählt bei genau einem Gremium")
@deal.raises(SchemaError)
def documents_by_body(
    papers: pl.DataFrame, results: pl.DataFrame, units: pl.DataFrame
) -> pl.DataFrame:
    """Je Gremium: Dokumente, Dokumente mit Treffer und (nur Bezirksvertretungen) die Lokalität.

    Die Lokalität ist der Anteil der Treffer einer Bezirksvertretung, der in Wahlbezirken ihres
    eigenen Stadtbezirks liegt; für alle anderen Gremien gibt es keinen eigenen Stadtbezirk und
    damit keinen Wert. Ein Gremium ohne Treffer bekommt ebenfalls keinen (Division durch 0).
    """
    keyed = papers.with_columns(pl.col(BODY).fill_null(NO_BODY))
    pairs = _exploded_hits(results, keyed, units)
    per_body = keyed.group_by(BODY).agg(
        pl.col(KIND).first(), pl.col(UNIT).first(), pl.len().alias(DOCUMENTS)
    )
    with_hits = pairs.group_by(BODY).agg(
        pl.col(PAPER_IDS).n_unique().alias(WITH_HITS),
        pl.col(_OWN).sum().alias("_own_pairs"),
        pl.len().alias("_pairs"),
    )
    local = (
        pl.when((pl.col(KIND) == DISTRICT_BODY) & (pl.col("_pairs") > 0))
        .then(pl.col("_own_pairs") / pl.col("_pairs"))
        .otherwise(None)
    )
    return (
        per_body.join(with_hits, on=BODY, how="left")
        .with_columns(
            pl.col(WITH_HITS).fill_null(0).cast(pl.Int64),
            pl.col("_own_pairs").fill_null(0),
            pl.col("_pairs").fill_null(0),
        )
        .with_columns(local.alias(LOCAL_SHARE))
        .select(BODY_COLUMNS)
        .sort(BODY)
    )


def summary(districts: pl.DataFrame, bodies: pl.DataFrame) -> str:
    """Die Rückgabezeile des Schritts ``body_hits``."""
    own = int(districts.get_column(OWN).sum())
    total = int(districts.get_column(HITS).sum())
    return (
        f"{districts.height} Wahlbezirke, {bodies.height} Gremien, "
        f"{own} von {total} Treffern aus der eigenen Bezirksvertretung"
    )


@deal.pre(
    lambda districts, results: (
        has_columns(districts, DISTRICT, OWN_SHARE, OWN_RATE)
        and has_columns(results, DISTRICT, TURNOUT)
    )
)
@deal.post(lambda result: result.columns == [DISTRICT, OWN_SHARE, OWN_RATE, TURNOUT])
@deal.post(
    lambda result: sorted_unique(result, DISTRICT), message="eine Zeile je Wahlbezirk, sortiert"
)
def regression_frame(districts: pl.DataFrame, results: pl.DataFrame) -> pl.DataFrame:
    """Der Join für den Regressionssatz: die Kennzahlen der Gremien neben der Wahlbeteiligung.

    ``regression_pair(frame, exclude, x=OWN_RATE)`` rechnet daraus beide Spalten von Tabelle 5.

    Sortiert, und die Nachbedingung sagt es: ein Join legt die Zeilenfolge nicht fest, und
    ``linregress`` summiert über die Spalten -- in anderer Folge stehen in den gedruckten Zahlen
    andere letzte Bits. Zwei Läufe sollen dieselbe Seite schreiben (2026-10-13).
    """
    return (
        districts.select(DISTRICT, OWN_SHARE, OWN_RATE)
        .join(results.select(DISTRICT, TURNOUT), on=DISTRICT, how="inner")
        .sort(DISTRICT)
    )
