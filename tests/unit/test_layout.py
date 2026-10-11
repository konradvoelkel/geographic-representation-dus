from __future__ import annotations

from pathlib import Path

import pytest

from georep.layout import Layout, ReferenceWriteError
from georep.settings import load_settings


def test_layout_from_settings_uses_cache_dir_default(tmp_path: Path) -> None:
    layout = Layout.from_settings(load_settings(cwd=tmp_path))
    assert layout.cache_root == Path("data") / "cache"
    assert layout.pdf_dir == Path("data") / "cache" / "pdf"
    assert layout.corpus == Path("data") / "interim" / "papers.parquet"
    assert layout.reference_root == Path("reference")


def test_reference_view_reads_the_same_names_under_reference_root(tmp_path: Path) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    reference = layout.reference_view()
    assert reference.paper_objects == tmp_path / "reference" / "raw" / "paper_objects.json"
    assert reference.corpus_legacy == tmp_path / "reference" / "interim" / "paper_with_text.json"


def test_guard_refuses_paths_under_reference_root(tmp_path: Path) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    assert layout.guard_writable(layout.corpus) == layout.corpus
    with pytest.raises(ReferenceWriteError):
        layout.guard_writable(tmp_path / "reference" / "processed" / "x.parquet")
    with pytest.raises(ReferenceWriteError):
        layout.guard_writable(tmp_path / "reference")


def test_ensure_dirs_creates_runtime_dirs_only(tmp_path: Path) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    layout.ensure_dirs()
    assert all(d.is_dir() for d in layout.runtime_dirs())
    assert not (tmp_path / "reference").exists()


def test_data_root_inside_reference_is_refused(tmp_path: Path) -> None:
    layout = Layout(tmp_path / "reference" / "data", tmp_path / "cache", tmp_path / "reference")
    with pytest.raises(ReferenceWriteError):
        layout.ensure_dirs()
