from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

import src.config as cfg
from src.dataset_opendata import get_stimmbezirk_shapefile, get_wahlergebnis
from tests.unit.test_dataset_oparl import FakeSession, _response


def test_wahlergebnis_is_stored_byte_for_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfg, "WAHLERGEBNIS_PATH", tmp_path / "ergebnis.csv")
    body = "﻿datum;gebietname\n14.09.2025;Düsseldorf Flingern-Süd\n".encode(
        "latin-1", errors="replace"
    )
    url = cfg.OPENDATA_ENDPOINT_WAHLERGEBNIS
    get_wahlergebnis(FakeSession({url: _response(url, content=body)}))
    assert (tmp_path / "ergebnis.csv").read_bytes() == body


def test_shapefile_is_stored_as_readable_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfg, "STIMMBEZIRK_SHAPEFILE_PATH", tmp_path / "bezirke.geojson")
    url = cfg.OPENDATA_ENDPOINT_STIMMBEZIRK
    payload = {"type": "FeatureCollection", "features": [{"name": "Düsseltal"}]}
    get_stimmbezirk_shapefile(FakeSession({url: _response(url, payload=payload)}))
    raw = (tmp_path / "bezirke.geojson").read_text(encoding="utf-8")
    assert "Düsseltal" in raw
    assert json.loads(raw) == payload


def test_network_errors_propagate_and_nothing_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfg, "WAHLERGEBNIS_PATH", tmp_path / "ergebnis.csv")
    url = cfg.OPENDATA_ENDPOINT_WAHLERGEBNIS
    with pytest.raises(requests.ConnectionError):
        get_wahlergebnis(FakeSession({url: requests.ConnectionError("Portal weg")}))
    assert not (tmp_path / "ergebnis.csv").exists()


def test_http_errors_propagate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "STIMMBEZIRK_SHAPEFILE_PATH", tmp_path / "bezirke.geojson")
    url = cfg.OPENDATA_ENDPOINT_STIMMBEZIRK
    with pytest.raises(requests.HTTPError):
        get_stimmbezirk_shapefile(FakeSession({url: _response(url, status=503)}))
    assert not (tmp_path / "bezirke.geojson").exists()
