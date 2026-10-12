"""Straßennamen je Stimmbezirk (OSM) zu Suchbegriffen je Wahlbezirk.

Entspricht ``src/prep_streets.py``: je Wahlbezirk die sortierte Menge der Straßennamen aller
seiner Stimmbezirke. Listen statt ``"; "``-Strings.

Dazu (Option 01) die Übereinstimmung mit dem amtlichen Straßenverzeichnis der Wahl, wo die Stadt
eines veröffentlicht: sie misst, wie gut die Flächen, aus denen die Straßennamen kommen, zum
Zuschnitt der Wahl passen. Mönchengladbachs Flächen sind von 2022, die Wahl ist von 2025.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import deal
import polars as pl

from georep.contracts import has_columns, lists_sorted_unique, sorted_unique
from georep.errors import SchemaError
from georep.io import read_text_without_bom
from georep.prep.precincts import district_from_id
from georep.settings import Precincts, ResultsColumns

DISTRICT = "wahlkreis_id"
TERMS = "suchbegriffe"
# Option 01: Spalten des amtlichen Straßenverzeichnisses der Wahl (votemanager)
DIRECTORY_STREET = "Strassen-Name"
DIRECTORY_PRECINCT = "Bezirk-Nr"


def read_streets_json(path: Path) -> pl.DataFrame:
    """``streets_per_district.json``: eine Zeile je Stimmbezirk mit der Liste ``straßen``."""
    return pl.read_json(path)


@deal.pre(lambda streets: has_columns(streets, "wahlbezirk_id", "straßen"))
@deal.post(lambda result: result.columns == [DISTRICT, TERMS])
@deal.post(lambda result: sorted_unique(result, DISTRICT) and lists_sorted_unique(result, TERMS))
def streets_by_district(streets: pl.DataFrame) -> pl.DataFrame:
    return (
        streets.select(pl.col("wahlbezirk_id").cast(pl.Int64).alias(DISTRICT), pl.col("straßen"))
        .explode("straßen")
        .drop_nulls("straßen")
        .group_by(DISTRICT)
        .agg(pl.col("straßen").unique().sort().alias(TERMS))
        .sort(DISTRICT)
    )


# --- Option 01: Übereinstimmung mit dem Straßenverzeichnis der Wahl -----------------------------


@dataclass(frozen=True)
class Agreement:
    """Wie viele der OSM-Straßennamen das Verzeichnis demselben Gebiet zuordnet."""

    streets: int  # Paare (Stimmbezirk, Straßenname) aus OpenStreetMap, die das Verzeichnis kennt
    matched: int  # davon im selben Stimmbezirk
    matched_district: int  # davon im selben Wahlbezirk (gröber, kann nur mehr sein)
    unknown: int  # Namen, die das Verzeichnis gar nicht führt (Fußwege, Plätze, neue Straßen)

    @property
    def precinct_share(self) -> float:
        return self.matched / self.streets if self.streets else 0.0

    @property
    def district_share(self) -> float:
        return self.matched_district / self.streets if self.streets else 0.0

    def line(self) -> str:
        return (
            f"{self.streets} bekannte Straßennamen: {self.precinct_share:.1%} im selben "
            f"Stimmbezirk, {self.district_share:.1%} im selben Wahlbezirk; "
            f"{self.unknown} nicht im Verzeichnis"
        )


def read_directory(path: Path, columns: ResultsColumns) -> pl.DataFrame:
    """Das Straßenverzeichnis der Wahl: Straßenname und Stimmbezirk, alles als Text."""
    text = read_text_without_bom(path, columns.encoding)
    frame = pl.read_csv(io.BytesIO(text.encode("utf-8")), separator=columns.sep, infer_schema=False)
    missing = [c for c in (DIRECTORY_STREET, DIRECTORY_PRECINCT) if c not in frame.columns]
    if missing:
        raise SchemaError(f"{path.name}: Spalten fehlen: {missing}")
    return frame.select(
        pl.col(DIRECTORY_STREET).str.strip_chars().alias("name"),
        pl.col(DIRECTORY_PRECINCT).str.strip_chars().alias("stimmbezirk"),
    ).filter(pl.col("name") != "")


def _plausible(result: Agreement) -> bool:
    return (
        0 <= result.matched <= result.matched_district <= result.streets
        and 0.0 <= result.precinct_share <= result.district_share <= 1.0
        and result.unknown >= 0
    )


@deal.post(_plausible, message="Treffer ≤ grober Treffer ≤ Namen, Anteile in [0, 1]")
@deal.raises(SchemaError)
def directory_agreement(
    streets_json: Path, directory_csv: Path, columns: ResultsColumns, rules: Precincts
) -> Agreement:
    """Vergleicht die OSM-Straßen je Stimmbezirk mit dem Straßenverzeichnis der Wahl.

    Gezählt werden Paare (Stimmbezirk, Straßenname), deren Name im Verzeichnis vorkommt: einmal
    danach, ob das Verzeichnis denselben Stimmbezirk nennt, und einmal gröber, ob es denselben
    Wahlbezirk nennt. Namen, die das Verzeichnis nicht kennt (Fußwege, Plätze, neue Straßen),
    zählen getrennt und nicht gegen die Quote.
    """
    directory = read_directory(directory_csv, columns)
    known = directory.group_by("name").agg(pl.col("stimmbezirk").unique().alias("stimmbezirke"))
    by_name = {row["name"]: set(row["stimmbezirke"]) for row in known.iter_rows(named=True)}
    streets = read_streets_json(streets_json)
    missing = [c for c in ("stimmbezirks_id", "straßen") if c not in streets.columns]
    if missing:
        raise SchemaError(f"{streets_json.name}: Spalten fehlen: {missing}")
    total = matched = matched_district = unknown = 0
    for row in streets.iter_rows(named=True):
        precinct = str(row["stimmbezirks_id"]).strip()
        district = _district_of(precinct, rules)
        for name in row["straßen"]:
            places = by_name.get(name)
            if places is None:
                unknown += 1
                continue
            total += 1
            if precinct in places:
                matched += 1
                matched_district += 1
            elif district is not None and district in {_district_of(p, rules) for p in places}:
                matched_district += 1
    return Agreement(total, matched, matched_district, unknown)


def _district_of(precinct: str, rules: Precincts) -> int | None:
    """Der Wahlbezirk einer Stimmbezirksnummer, wenn das Profil ihn aus ihr liest."""
    if rules.district_from_id is None:
        return None
    try:
        return district_from_id(precinct, *rules.district_from_id)
    except SchemaError:
        return None
