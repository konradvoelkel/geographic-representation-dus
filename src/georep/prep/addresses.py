"""Vorhaben 16: Hausnummer → Stimm- und Wahlbezirk aus den Gebäudereferenzen NRW (Adresspaket).

Eine Hausnummer hinter einem Straßenbegriff (``search.positions.house_number``) erzeugt keinen
Treffer; sie sagt, in welchem Wahlbezirk die Adresse liegt, und entscheidet so die Grenzstraße
(Messdokument ``docs/plans/16-ortsbezug.md``, § 3.4). Dafür braucht es je Straße, Nummer und Zusatz
den Bezirk. Die Koordinaten kommen aus demselben Archiv wie die Straßenpunkte der Startseite
(``prep.streetpoints``, Netzschritt ``street_points``, ``cache_root/startkarte/``): eine Quelle für
GebRef, keine zweite URL (§ 10, Punkt 3). Den Bezirk gibt ``crosswalk.point_shares`` mit Band 0
(Punkt in Fläche, Vorhaben 22): ein Punkt auf einer Grenze liegt in beiden Stimmbezirken und steht
mit beiden im Paket.

Das Paket (``georep pack --addresses`` nach ``snapshots/<stadt>-adressen/``) trägt keine
Koordinate, nur Straße, Nummer, Zusatz, Stimm- und Wahlbezirk; ``bootstrap`` kopiert es nach
``external/adressen/``, wo der Schritt ``places`` es liest. Welche Adresse ein Dokument nennt, steht
nur lokal (``adressen_wahlbezirke``, nie ein Download): unter ihnen sind Anschriften von
Privatpersonen (§ 3.4, Datenschutz).
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import deal
import polars as pl

from georep.contracts import has_columns
from georep.crosswalk import DISTRICT, POINT, PRECINCT, point_shares
from georep.geo import Precinct
from georep.layout import Layout
from georep.prep.streetpoints import GEBREF_MEMBER, ags_of, normalize_street

ADDRESS_DIR = "adressen"  # unter external/ und im Paket
ADDRESS_FILE = "adressen.parquet"
SOURCES_FILE = "quellen.json"  # Gemeinde und Archiv, aus dem das Paket entstand
ADDRESS_FILES = (ADDRESS_FILE, SOURCES_FILE)
ADDRESS_SCHEMA_VERSION = 1  # erhöhen, wenn sich Spalten oder Typen des Pakets ändern
STREET = "strasse"
NUMBER = "nr"
SUFFIX = "zusatz"
ADDRESS_SCHEMA: dict[str, pl.DataType] = {
    STREET: pl.String(),
    NUMBER: pl.UInt16(),
    SUFFIX: pl.String(),
    PRECINCT: pl.String(),
    DISTRICT: pl.Int64(),
}
# Felder einer Zeile von gebref.txt wie in ``prep.streetpoints``: Straßenname, Hausnummer, Zusatz,
# Ost- und Nordwert in EPSG:25832
_STREET, _NUMBER, _SUFFIX, _EAST, _NORTH = 14, 15, 16, 18, 19
_FIELDS = 21
# Wie das Messskript: verortet ist eine Adresse, deren Nummer mit Zusatz es gibt, oder deren
# Hauptnummer, wo der Text einen Zusatz nennt, den es nicht gibt (§ 3.4, „verortbar")
EXACT = "genau"
WITHOUT_SUFFIX = "ohne_zusatz"
OTHER_SUFFIX = "mit_zusatz"  # die Nummer gibt es nur mit einem anderen Zusatz: nicht verortet
NO_NUMBER = "nein"
UNKNOWN_STREET = "strasse_unbekannt"
STATUSES = (EXACT, WITHOUT_SUFFIX, OTHER_SUFFIX, NO_NUMBER, UNKNOWN_STREET)
LOCATED = frozenset({EXACT, WITHOUT_SUFFIX})


class AddressFiles(NamedTuple):
    table: Path
    sources: Path


def address_files(layout: Layout) -> AddressFiles:
    """Wo ``bootstrap`` das Adresspaket ablegt und ``places`` es liest: ``external/adressen/``."""
    folder = layout.external / ADDRESS_DIR
    return AddressFiles(folder / ADDRESS_FILE, folder / SOURCES_FILE)


def _lines(archive: Path) -> Iterator[str]:
    with zipfile.ZipFile(archive) as opened, opened.open(GEBREF_MEMBER) as raw:
        yield from io.TextIOWrapper(raw, encoding="utf-8")


def read_house_numbers(archive: Path, ags: str) -> pl.DataFrame:
    """Straße (normalisiert), Nummer, Zusatz (klein) und Koordinate je Hausnummer der Gemeinde.

    Wie das Messskript: eine Zeile ohne Ziffernfolge als Nummer oder ohne Koordinate fällt weg.
    Die Koordinaten sind EPSG:25832, wie GebRef sie trägt (``prep.streetpoints.GEBREF_CRS``).
    """
    rows: list[tuple[str, int, str, float, float]] = []
    for line in _lines(archive):
        parts = line.rstrip("\n").split(";")
        if len(parts) < _FIELDS or ags_of(parts) != ags or not parts[_NUMBER].isdecimal():
            continue
        try:
            x, y = float(parts[_EAST]), float(parts[_NORTH])
        except ValueError:
            continue
        rows.append(
            (
                normalize_street(parts[_STREET]),
                int(parts[_NUMBER]),
                parts[_SUFFIX].strip().lower(),
                x,
                y,
            )
        )
    return pl.DataFrame(
        rows,
        schema={
            STREET: pl.String,
            NUMBER: pl.Int64,
            SUFFIX: pl.String,
            "x": pl.Float64,
            "y": pl.Float64,
        },
        orient="row",
    )


def _schema_and_order(
    houses: pl.DataFrame, precincts: Sequence[Precinct], result: tuple[pl.DataFrame, int]
) -> bool:
    table, outside = result
    keys = list(table.select(STREET, NUMBER, SUFFIX, PRECINCT).iter_rows())
    return (
        table.schema == pl.Schema(ADDRESS_SCHEMA)
        and keys == sorted(set(keys))
        and 0 <= outside <= houses.height
    )


@deal.pre(lambda houses, precincts: has_columns(houses, STREET, NUMBER, SUFFIX, "x", "y"))
@deal.ensure(_schema_and_order, message="Schema des Pakets, je Adresse und Stimmbezirk eine Zeile")
def address_table(houses: pl.DataFrame, precincts: Sequence[Precinct]) -> tuple[pl.DataFrame, int]:
    """Je (Straße, Nummer, Zusatz) die Stimmbezirke ihrer Koordinaten und deren Wahlbezirk.

    ``houses`` und ``precincts`` im selben CRS. Über ``point_shares`` mit Band 0, je Stimmbezirk
    (``stimmbezirk_id``): eine Hausnummer auf der Grenze zweier Stimmbezirke steht mit beiden da,
    eine, die GebRef zweimal führt, mit jedem ihrer Stimmbezirke einmal. Eine Nummer mit mehr als
    vier Stellen hat keine Spalte (UInt16) und fiele auf; GebRef führt keine. Das zweite Ergebnis
    zählt die Hausnummern außerhalb aller Stimmbezirke, die wegfallen.
    """
    points = houses.with_row_index(POINT).with_columns(pl.col(POINT).cast(pl.Int64))
    shares = point_shares(points.select(POINT, "x", "y"), precincts, band_m=0.0, unit=PRECINCT)
    district_of = pl.DataFrame(
        {
            PRECINCT: [p.precinct_id for p in precincts],
            DISTRICT: [p.district_id for p in precincts],
        },
        schema={PRECINCT: pl.String, DISTRICT: pl.Int64},
    ).unique()
    located = points.join(shares.select(POINT, PRECINCT), on=POINT, how="inner")
    outside = houses.height - located.get_column(POINT).n_unique()
    table = (
        located.join(district_of, on=PRECINCT, how="left")
        .select(
            pl.col(STREET),
            pl.col(NUMBER).cast(pl.UInt16, strict=True),
            pl.col(SUFFIX),
            pl.col(PRECINCT),
            pl.col(DISTRICT),
        )
        .unique()
        .sort(STREET, NUMBER, SUFFIX, PRECINCT)
    )
    return table, outside


@dataclass(frozen=True)
class AddressBook:
    """Das Paket zum Nachschlagen: je Straße die Nummern mit ihren Wahlbezirken."""

    streets: Mapping[str, Mapping[tuple[int, str], frozenset[int]]]

    @classmethod
    def from_table(cls, table: pl.DataFrame) -> AddressBook:
        found: dict[str, dict[tuple[int, str], set[int]]] = {}
        for street, number, suffix, district in table.select(
            STREET, NUMBER, SUFFIX, DISTRICT
        ).iter_rows():
            found.setdefault(street, {}).setdefault((int(number), suffix), set()).add(int(district))
        return cls(
            {
                street: {key: frozenset(value) for key, value in numbers.items()}
                for street, numbers in found.items()
            }
        )

    def locate(self, term: str, number: int, suffix: str) -> tuple[str, frozenset[int]]:
        """(Status, Wahlbezirke) einer Adresse ``term`` ``number`` ``suffix`` wie im Messskript.

        ``genau``: Nummer und Zusatz gibt es; ``ohne_zusatz``: der Text nennt einen Zusatz, den
        es nicht gibt, die Hauptnummer schon; ``mit_zusatz``: die Nummer gibt es nur mit einem
        anderen Zusatz; ``nein``: die Nummer fehlt an der Straße; ``strasse_unbekannt``. Nur die
        ersten beiden sind verortet und tragen Wahlbezirke.
        """
        street = self.streets.get(normalize_street(term))
        if street is None:
            return UNKNOWN_STREET, frozenset()
        if (number, suffix) in street:
            return EXACT, street[(number, suffix)]
        if suffix and (number, "") in street:
            return WITHOUT_SUFFIX, street[(number, "")]
        if any(n == number for n, _ in street):
            return OTHER_SUFFIX, frozenset()
        return NO_NUMBER, frozenset()
