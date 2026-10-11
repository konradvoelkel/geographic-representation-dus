from __future__ import annotations

from pathlib import Path

import pytest
import shapely
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from georep.geo import Precinct, PrecinctIndex, read_precincts, transformer
from georep.settings import Settings, load_settings


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


@pytest.fixture(scope="module")
def index(reference_root: Path, settings: Settings) -> PrecinctIndex:
    precincts = read_precincts(
        reference_root / "external" / "Stimmbezirke_2025.geojson",
        settings.columns,
        settings.geo.working_crs,
    )
    return PrecinctIndex(precincts, settings.geo.working_crs)


@hsettings(max_examples=300, deadline=None)
@given(lon=st.floats(6.5, 7.1), lat=st.floats(51.0, 51.5))
def test_every_point_lies_in_at_most_one_precinct_and_that_one_contains_it(
    lon: float, lat: float, index: PrecinctIndex, settings: Settings
) -> None:
    hit = index.locate(lon, lat)
    x, y = transformer("EPSG:4326", settings.geo.working_crs).transform(lon, lat)
    point = shapely.Point(x, y)
    containing = [p for p in index.precincts if p.geometry.contains(point)]
    assert len(containing) <= 1
    if hit is None:
        assert containing == []
    else:
        assert isinstance(hit, Precinct) and containing == [hit]
