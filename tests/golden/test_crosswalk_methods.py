"""Der geometrische Crosswalk gegen den Attribut-Crosswalk der Stadt.

Die Stadt ordnet jeden Stimmbezirk ganz einem Stadtteil zu; ``area_shares`` teilt ihn nach
Fläche. Beide Wege müssen fast dasselbe liefern -- tun sie es nicht, stimmt an den Flächen oder
an den Gewichten etwas nicht. Die Stadtteile entstehen hier aus den Raumeinheiten selbst (die
ersten drei Stellen ihres Schlüssels sind die Stadtteilnummer), damit der Vergleich nur die
Methode prüft und nicht zwei Portaldateien verschiedener Jahrgänge.

Gemessen am 2026-10-12 (Zahlen in docs/decisions.md): auf der Referenz weichen 227 Paare im
Mittel um 0,001 ab, höchstens um 0,067 (Wahlbezirk 22, Stadtteile 053 und 054); der dominante
Stadtteil stimmt in 40 von 41 Wahlbezirken.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from georep.crosswalk import area_shares, district_weights, unit_weights
from georep.geo import Area, read_areas, read_precincts
from georep.prep.context import precinct_table
from georep.prep.voters import read_results_csv
from georep.settings import Settings, load_settings

BOROUGH = "Stadtteil Nr."  # Eigenschaft des Stimmbezirks-GeoJSON; nur dieser Vergleich liest sie


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


def _compare(root: Path, context: Path, settings: Settings) -> tuple[pl.DataFrame, int, int]:
    """(Vergleichstabelle, Wahlbezirke mit gleichem dominanten Stadtteil, Wahlbezirke)."""
    working = settings.geo.working_crs
    geojson = root / "external" / "Stimmbezirke_2025.geojson"
    precincts = read_precincts(geojson, settings.columns, working)
    results = read_results_csv(
        root / "external" / "Stimmbezirk_Wahlergebnis.csv", settings.columns.results
    )
    table = precinct_table(precincts, results, settings.columns.results)
    units = read_areas(
        context / settings.context.files.units.file, settings.context.units.key, working
    )
    merged: dict[str, list[BaseGeometry]] = {}
    for unit in units:
        merged.setdefault(unit.key[:3], []).append(unit.geometry)
    boroughs = [Area(key, unary_union(parts)) for key, parts in sorted(merged.items())]
    geometric = district_weights(
        table,
        area_shares([Area.of(p) for p in precincts], boroughs, min_coverage=0.9),
    )
    by_precinct = {
        str(f["properties"][settings.columns.precinct_id]): f"{int(f['properties'][BOROUGH]):03d}"
        for f in json.loads(geojson.read_text(encoding="utf-8"))["features"]
    }
    attributes = unit_weights(
        table.with_columns(pl.col("stimmbezirk_id").replace_strict(by_precinct).alias("einheit")),
        "einheit",
        "wahlberechtigte",
    )
    both = geometric.join(
        attributes.select("wahlkreis_id", "einheit", "gewicht"),
        on=["wahlkreis_id", "einheit"],
        how="full",
        suffix="_attribut",
        coalesce=True,
    ).fill_null(0.0)
    both = both.with_columns(
        (pl.col("gewicht") - pl.col("gewicht_attribut")).abs().alias("abweichung")
    )

    def dominant(frame: pl.DataFrame, column: str = "gewicht") -> dict[int, str]:
        best = (
            frame.sort(["wahlkreis_id", column], descending=[False, True])
            .group_by("wahlkreis_id")
            .agg(pl.col("einheit").first())
        )
        return dict(best.iter_rows())

    a, b = dominant(geometric), dominant(attributes)
    agree = sum(1 for key, value in a.items() if b.get(key) == value)
    return both, agree, len(a)


def test_both_crosswalks_agree_on_the_mini_fixture(mini_root: Path, settings: Settings) -> None:
    both, agree, districts = _compare(mini_root, mini_root / "context", settings)
    assert districts == 3 and agree == 3
    assert bool((both.get_column("abweichung") < 0.01).all())  # gemessen 0,0026 (2026-10-12)


@pytest.mark.slow
def test_both_crosswalks_agree_on_the_reference(
    reference_root: Path, context_root: Path, settings: Settings
) -> None:
    both, agree, districts = _compare(reference_root, context_root, settings)
    assert districts == 41 and agree >= 40
    deviations: list[float] = both.get_column("abweichung").to_list()
    worst, average = max(deviations), sum(deviations) / len(deviations)
    # Höchstens ein Zehntel des Gewichts eines Wahlbezirks, im Mittel ein Promille: der Rest ist
    # der Unterschied der Methoden (ganzer Stimmbezirk gegen Fläche), kein Fehler.
    assert worst < 0.10 and average < 0.01
    assert both.height > 200
