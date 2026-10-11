from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from georep.io import atomic_path, write_bytes, write_json, write_text


def _leftovers(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir() if p.name.endswith(".tmp"))


def test_write_text_creates_parent_and_content(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "out.txt"
    write_text(target, "hallo ü")
    assert target.read_text(encoding="utf-8") == "hallo ü"
    assert _leftovers(target.parent) == []


def test_failing_block_keeps_old_file_and_leaves_no_tmp(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("alt")
    with pytest.raises(RuntimeError), atomic_path(target) as tmp:
        tmp.write_text("neu, aber unvollständig")
        raise RuntimeError("Abbruch mitten im Schreiben")
    assert target.read_text() == "alt"
    assert _leftovers(tmp_path) == []


def test_block_that_writes_nothing_is_an_error(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    with pytest.raises(FileNotFoundError), atomic_path(target):
        pass
    assert not target.exists()
    assert _leftovers(tmp_path) == []


def test_write_json_keeps_umlauts_readable(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    write_json(target, {"name": "Düsseldorf", "n": [1, 2]})
    raw = target.read_text(encoding="utf-8")
    assert "Düsseldorf" in raw
    assert json.loads(raw) == {"name": "Düsseldorf", "n": [1, 2]}


@given(st.binary())
def test_write_bytes_roundtrip(tmp_path_factory: pytest.TempPathFactory, data: bytes) -> None:
    target = tmp_path_factory.mktemp("bytes") / "blob.bin"
    write_bytes(target, data)
    assert target.read_bytes() == data
    assert _leftovers(target.parent) == []
