"""Die Leser und Aggregate von Vorhaben 22 in ``georep.prep.context`` an winzigen Archiven.

Bauplan ``docs/plans/22-bedarf.md``, § 6: die drei Namensformen der Unfallatlas-Jahrgänge (je drei
Zeilen, eine davon in der Zielgemeinde), BOM im Kopf, Dezimalkomma; Codepage 850 und „ohne" im
Sozialindex; die Zensus-Zelle auf der Grenze.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl
import pytest
from shapely.geometry import box

from georep.crosswalk import POINT, point_shares
from georep.errors import SchemaError
from georep.geo import Precinct
from georep.prep.context import (
    ACCIDENTS_SCHEMA,
    GRID_SCHEMA,
    NEED_TABLE_SCHEMA,
    SCHOOLS_SCHEMA,
    accidents_by_district,
    ags_parts,
    attention_by_district,
    grid_by_district,
    in_period,
    need_table,
    read_accidents,
    read_grid,
    read_schools,
    schools_by_district,
)
from tests.need_archives import (
    GRID_POPULATION_MEMBER,
    GRID_RENT_MEMBER,
    write_accident_archive,
    write_grid_archives,
    write_school_files,
)

AGS = "05111000"


def test_the_municipality_key_splits_into_its_four_parts() -> None:
    assert ags_parts(AGS) == (5, 1, 11, 0)
    assert ags_parts("05116000") == (5, 1, 16, 0)


@pytest.mark.parametrize("form", [0, 1, 2], ids=["2020-csv", "2021-txt-bom", "2025-basisdlm-bom"])
def test_each_form_of_the_accident_archives_reads_the_same(tmp_path: Path, form: int) -> None:
    rows = [
        {
            "ags": AGS,
            "month": 9,
            "category": 2,
            "bike": 1,
            "foot": 0,
            "x": 344000.5,
            "y": 5676000.25,
        },
        {
            "ags": AGS,
            "month": 1,
            "category": 3,
            "bike": 0,
            "foot": 1,
            "x": 345000.0,
            "y": 5677000.0,
            "leading_zero": False,
        },
    ]
    path = write_accident_archive(tmp_path / f"a{form}.zip", form, rows)
    frame = read_accidents(path, AGS)
    assert frame.schema == pl.Schema(ACCIDENTS_SCHEMA)
    assert frame.height == 2  # die dritte Zeile ist eine andere Gemeinde
    assert frame.select("monat", "kategorie", "rad", "fuss").rows() == [(1, 3, 0, 1), (9, 2, 1, 0)]
    assert frame.get_column("x").to_list() == [345000.0, 344000.5]  # Dezimalkomma gelesen
    assert frame.get_column("y").to_list() == [5677000.0, 5676000.25]


def test_an_archive_that_is_no_zip_is_a_schema_error(tmp_path: Path) -> None:
    path = tmp_path / "kaputt.zip"
    path.write_bytes(b"<html>Wartung</html>")
    with pytest.raises(SchemaError, match="kaputt.zip"):
        read_accidents(path, AGS)


def test_a_missing_column_is_named(tmp_path: Path) -> None:
    import zipfile

    path = tmp_path / "x.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("csv/x.csv", "ULAND;UJAHR\n05;2020\n")
    with pytest.raises(SchemaError, match="LINREFX"):
        read_accidents(path, AGS)


def test_the_grid_joins_people_and_rent_inside_the_box(tmp_path: Path) -> None:
    cells = [
        (4100050, 3100050, "12", "9,50", ""),
        (4100150, 3100050, "7", "11,25", "KLAMMERN"),
        (4100250, 3100050, "3", "", ""),  # ohne Miete
        (4100350, 3100050, "–", "8,00", ""),  # gesperrt
        (4900050, 3100050, "99", "5,00", ""),  # außerhalb des Rechtecks
    ]
    population, rent = write_grid_archives(tmp_path, cells)
    frame = read_grid(
        population,
        GRID_POPULATION_MEMBER,
        rent,
        GRID_RENT_MEMBER,
        (4100000, 3100000, 4100400, 3100100),
    )
    assert frame.schema == pl.Schema(GRID_SCHEMA)
    assert frame.rows() == [
        (4100050, 3100050, 12, 9.5, None),
        (4100150, 3100050, 7, 11.25, "KLAMMERN"),
        (4100250, 3100050, 3, None, None),
        (4100350, 3100050, None, 8.0, None),
    ]


def test_a_grid_member_that_is_missing_is_named(tmp_path: Path) -> None:
    population, rent = write_grid_archives(tmp_path, [(1, 1, "1", "1,0", "")])
    with pytest.raises(SchemaError, match="fehlt"):
        read_grid(population, "anders.csv", rent, GRID_RENT_MEMBER, (0, 0, 10, 10))


def test_schools_of_the_municipality_with_their_index_from_codepage_850(tmp_path: Path) -> None:
    schools, index = write_school_files(
        tmp_path,
        [
            ("100020", "02", AGS, 344000, 5676000, "7"),
            ("100010", "02", AGS, 345000, 5677000, "ohne"),
            ("100030", "20", AGS, 346000, 5678000, "4"),
            ("100040", "02", "05911000", 1, 2, "9"),  # andere Gemeinde
        ],
    )
    frame = read_schools(schools, index, AGS, crs="EPSG:25832")
    assert frame.schema == pl.Schema(SCHOOLS_SCHEMA)
    assert frame.rows() == [
        ("100010", "02", 345000.0, 5677000.0, None),
        ("100020", "02", 344000.0, 5676000.0, 7),
        ("100030", "20", 346000.0, 5678000.0, 4),
    ]


def test_a_school_in_another_crs_is_an_error_not_a_silent_conversion(tmp_path: Path) -> None:
    schools, index = write_school_files(tmp_path, [("100020", "02", AGS, 1, 2, "7")])
    with pytest.raises(SchemaError, match="EPSG:25832"):
        read_schools(schools, index, AGS, crs="EPSG:4326")


def test_the_period_counts_whole_months_at_both_ends() -> None:
    frame = pl.DataFrame(
        {"jahr": [2020, 2020, 2025, 2025], "monat": [8, 9, 9, 10]},
        schema={"jahr": pl.Int64, "monat": pl.Int64},
    )
    kept = in_period(frame, dt.date(2020, 9, 13), dt.date(2025, 9, 14))
    assert kept.rows() == [(2020, 9), (2025, 9)]
    assert in_period(frame, dt.date(2025, 9, 1), None).rows() == [(2025, 9), (2025, 10)]


# --- je Wahlbezirk: zwei Wahlbezirke nebeneinander ---------------------------------------------

AREAS = [
    Precinct("0101", 1, "Links", box(0, 0, 100, 100)),
    Precinct("0201", 2, "Rechts", box(100, 0, 200, 100)),
]


def _points(rows: list[tuple[float, float]], **columns: list[object]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            POINT: list(range(len(rows))),
            "x": [r[0] for r in rows],
            "y": [r[1] for r in rows],
            **columns,
        }
    ).with_columns(
        pl.col(POINT).cast(pl.Int64), pl.col("x").cast(pl.Float64), pl.col("y").cast(pl.Float64)
    )


def test_accidents_on_the_border_are_shared_and_counted_apart() -> None:
    points = _points(
        [(50, 50), (95, 50), (150, 50)],
        kategorie=[1, 3, 3],
        rad=[0, 1, 0],
        fuss=[0, 0, 1],
    )
    table = accidents_by_district(
        points, point_shares(points, AREAS, band_m=20.0), point_shares(points, AREAS)
    )
    assert table.rows() == [
        (1, 1.5, 1.0, 0.5, 2.0, 0.5),
        (2, 1.5, 0.0, 1.5, 1.0, 0.5),
    ]
    assert table.columns == [
        "wahlkreis_id",
        "unfaelle",
        "unfaelle_schwer",
        "unfaelle_rad_fuss",
        "unfaelle_scharf",
        "unfaelle_geteilt",
    ]


def test_a_census_cell_on_the_border_is_split_and_the_rent_weighs_people() -> None:
    cells = _points(
        [(50, 50), (100, 50), (150, 50), (160, 50)],
        einwohner=[10, 20, 30, -1],
        miete=[8.0, 12.0, None, 20.0],
    )
    table = grid_by_district(cells, point_shares(cells, AREAS))
    left, right = table.rows()
    assert left[:2] == (1, 20.0)  # 10 und die Hälfte von 20
    assert left[2] == pytest.approx((10 * 8.0 + 10 * 12.0) / 20)
    assert left[3] == pytest.approx(1.0)
    assert right[:2] == (2, 40.0)  # 30, die Hälfte von 20, die gesperrte Zelle zählt 0
    assert right[2] == pytest.approx(12.0)  # nur die halbe Zelle mit Miete hat Einwohner
    assert right[3] == pytest.approx(10 / 40)


def test_schools_count_only_their_forms_and_average_the_index() -> None:
    schools = _points(
        [(10, 10), (20, 20), (30, 30), (150, 50)],
        schulform=["02", "02", "20", "02"],
        sozialindex=[3, None, 9, 6],
    )
    table = schools_by_district(schools, point_shares(schools, AREAS), ["02"])
    assert table.rows() == [(1, 2.0, 1.0, 3.0), (2, 1.0, 1.0, 6.0)]


def test_attention_counts_documents_and_the_share_of_a_class() -> None:
    results = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2, 3],
            "suchbegriffe": [["a", "b"], ["c"], []],
            "paper_ids": [["p1", "p2", "p3", "p1"], ["p2"], []],
        }
    )
    committees = pl.DataFrame({"id": ["p1", "p2", "p3"], "ausschuss": ["OVA", "", "JHA"]})
    table = attention_by_district(results, committees, ["OVA"], ["JHA", "SCHUA"])
    assert table.select(
        "wahlkreis_id", "begriffe", "dok", "dok_mit_text", "dok_verkehr", "dok_jugend"
    ).rows() == [
        (1, 2, 3, 3, 1, 1),
        (2, 1, 1, 1, 0, 0),
        (3, 0, 0, None, None, None),
    ]
    assert table.get_column("anteil_verkehr").to_list() == pytest.approx([1 / 3, 0.0, None])
    without = attention_by_district(results, None, [], [])
    assert without.get_column("anteil_verkehr").null_count() == 3
    assert without.get_column("dok").to_list() == [3, 1, 0]


def test_the_need_table_has_one_row_per_district_and_no_nan() -> None:
    base = pl.DataFrame(
        {"wahlkreis_id": [1, 2], "flaeche_km2": [0.01, 0.01], "stadtbezirk": [1, 1]},
        schema={"wahlkreis_id": pl.Int64, "flaeche_km2": pl.Float64, "stadtbezirk": pl.Int64},
    )
    accidents = pl.DataFrame(
        {
            "wahlkreis_id": [1],
            "unfaelle": [2.0],
            "unfaelle_schwer": [1.0],
            "unfaelle_rad_fuss": [0.0],
            "unfaelle_scharf": [2.0],
            "unfaelle_geteilt": [0.0],
        }
    )
    grid = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2],
            "einwohner_zensus": [1000.0, 0.0],
            "miete_qm": [9.0, None],
            "miete_abdeckung": [1.0, None],
        }
    )
    schools = pl.DataFrame(
        {
            "wahlkreis_id": [2],
            "schulen": [1.0],
            "schulen_mit_index": [1.0],
            "sozialindex_schulen": [4.0],
        }
    )
    attention = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2],
            "begriffe": [3, 1],
            "dok": [10, 0],
            "dok_mit_text": [10, None],
            "dok_verkehr": [2, None],
            "dok_jugend": [1, None],
            "anteil_verkehr": [0.2, None],
            "anteil_jugend": [0.1, None],
        },
        schema_overrides={
            "begriffe": pl.Int64,
            "dok": pl.Int64,
            "dok_mit_text": pl.Int64,
            "dok_verkehr": pl.Int64,
            "dok_jugend": pl.Int64,
        },
    )
    table = need_table(base, accidents, grid, schools, attention)
    assert table.schema == pl.Schema(NEED_TABLE_SCHEMA)
    first, second = table.to_dicts()
    assert first["unfaelle_je_1000"] == pytest.approx(2.0)
    assert first["unfaelle_je_km2"] == pytest.approx(200.0)
    assert first["dok_je_1000_ew"] == pytest.approx(10.0)
    assert first["schulen"] == 0.0 and first["sozialindex_schulen"] is None
    # ohne Einwohner kein Verhältnis: null, nicht NaN und nicht unendlich
    assert second["unfaelle"] == 0.0 and second["unfaelle_je_1000"] is None
    assert second["dok_je_1000_ew"] is None
