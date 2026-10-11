"""Der Flächen-Crosswalk auf den echten Stimmbezirken: derselbe Zuschnitt muss die Identität sein.

Die Probe, die jeden Vorzeichen- und CRS-Fehler findet: rechnet man die Stimmbezirke eines
Zuschnitts auf die aus ihnen vereinigten Wahlbezirke um, muss jeder Stimmbezirk genau ein Paar
mit Anteil 1 bekommen, und zwar mit seinem eigenen Wahlbezirk aus dem GeoJSON. Auf der
Mini-Fixture (22 Stimmbezirke, drei Wahlbezirke) schnell, auf der Referenz (306 auf 41) als
``slow``-Test.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from georep.crosswalk import area_shares, assign_by_point
from georep.geo import Area, read_precincts
from georep.report.geometry import district_shapes
from georep.settings import Settings


def _check_identity(root: Path, settings: Settings, precincts_expected: int) -> None:
    layout_external = root / "external"
    precincts = read_precincts(
        layout_external / settings.sources.opendata.districts_file,
        settings.columns,
        settings.geo.working_crs,
    )
    assert len(precincts) == precincts_expected
    sources = [Area(p.precinct_id, p.geometry) for p in precincts]
    targets = [Area(str(d), g) for d, g in district_shapes(precincts, tolerance_m=0.0).items()]
    shares = area_shares(sources, targets)
    assert shares.get_column("source_id").n_unique() == len(precincts)
    assert shares.get_column("coverage").to_list() == pytest.approx([1.0] * shares.height, abs=1e-6)
    # Je Stimmbezirk ein Anteil nahe 1 und sein eigener Wahlbezirk; die übrigen Paare sind
    # Splitter an gemeinsamen Grenzen (Fließkomma, unter 10^-6) und keine echte Teilung.
    best = (
        shares.sort("share", descending=True)
        .group_by("source_id")
        .agg(pl.col("target_id").first(), pl.col("share").max())
    )
    assert best.get_column("share").to_list() == pytest.approx([1.0] * best.height, abs=1e-6)
    expected = {p.precinct_id: str(p.district_id) for p in precincts}
    assert (
        dict(zip(*(best.get_column(c).to_list() for c in ("source_id", "target_id")), strict=True))
        == expected
    )
    assert assign_by_point(sources, targets) == expected


def test_identity_on_the_mini_cut(mini_root: Path, default_settings: Settings) -> None:
    _check_identity(mini_root, default_settings, 22)


@pytest.mark.slow
def test_identity_on_the_full_cut(reference_root: Path, default_settings: Settings) -> None:
    _check_identity(reference_root, default_settings, 306)


def test_shares_are_a_partition_even_where_districts_are_not_contiguous(
    mini_root: Path, default_settings: Settings
) -> None:
    """Wahlbezirk 10 der Mini-Fixture ist mehrteilig; die Zerlegung gilt trotzdem je Stimmbezirk."""
    precincts = read_precincts(
        mini_root / "external" / default_settings.sources.opendata.districts_file,
        default_settings.columns,
        default_settings.geo.working_crs,
    )
    shares = area_shares(
        [Area(p.precinct_id, p.geometry) for p in precincts],
        [Area(str(d), g) for d, g in district_shapes(precincts, tolerance_m=0.0).items()],
    )
    sums = shares.group_by("source_id").agg(pl.col("share").sum())
    assert sums.get_column("share").to_list() == pytest.approx([1.0] * sums.height, abs=1e-9)
