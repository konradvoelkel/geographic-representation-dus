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
    assert layout.site_data.is_dir()
    assert not (tmp_path / "reference").exists()


def test_site_lies_under_data_root(tmp_path: Path) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    assert layout.site == tmp_path / "data" / "site"
    assert layout.site_index == tmp_path / "data" / "site" / "index.html"
    assert layout.site_data == tmp_path / "data" / "site" / "data"
    assert layout.site in layout.runtime_dirs() and layout.site_data in layout.runtime_dirs()


def test_data_root_inside_reference_is_refused(tmp_path: Path) -> None:
    layout = Layout(tmp_path / "reference" / "data", tmp_path / "cache", tmp_path / "reference")
    with pytest.raises(ReferenceWriteError):
        layout.ensure_dirs()


def test_profile_puts_data_and_cache_in_a_subfolder_but_shares_the_http_cache(
    tmp_path: Path,
) -> None:
    flat = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    period = flat.for_profile("2014-2020")
    assert (
        flat.profile == "" and flat.root == tmp_path / "data" and flat.cache == tmp_path / "cache"
    )
    assert period.root == tmp_path / "data" / "2014-2020"
    assert period.processed == tmp_path / "data" / "2014-2020" / "processed"
    assert period.site_index == tmp_path / "data" / "2014-2020" / "site" / "index.html"
    assert period.pdf_dir == tmp_path / "cache" / "2014-2020" / "pdf"
    assert period.texts == tmp_path / "cache" / "2014-2020" / "text" / "texts.parquet"
    assert period.http_cache == flat.http_cache == tmp_path / "cache" / "http.sqlite"
    assert period.for_profile("") == flat
    assert period.reference_view() == flat.reference_view()
    shared = set(flat.runtime_dirs()) & set(period.runtime_dirs())
    assert not shared


def test_layout_from_settings_takes_the_profile(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text('profile = "2025"\n', encoding="utf-8")
    layout = Layout.from_settings(load_settings(cwd=tmp_path))
    assert layout.profile == "2025" and layout.corpus == Path("data/2025/interim/papers.parquet")


# --- Option 06: Gewichtung --------------------------------------------------------------------


def test_weights_and_topics_files_lie_next_to_their_kind(tmp_path: Path) -> None:
    """Veröffentlichtes unter processed/, die Anteilsmatrix als Zwischenstand unter interim/."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    processed = tmp_path / "data" / "processed"
    assert layout.topics == processed / "themen.parquet"
    assert layout.topic_documents == processed / "themen_dokumente.parquet"
    assert layout.term_weights == processed / "gewichte_begriffe.parquet"
    assert layout.weighted == processed / "wahlbezirke_gewichtet.parquet"
    assert layout.topic_shares == tmp_path / "data" / "interim" / "themen_anteile.parquet"
    assert layout.topics.parent in layout.runtime_dirs()
    assert layout.topic_shares.parent in layout.runtime_dirs()


# --- Option 03: Fremddaten unter context_root ----------------------------------------------------


def test_context_root_is_read_only_and_names_the_new_tables(tmp_path: Path) -> None:
    layout = Layout(
        tmp_path / "data", tmp_path / "cache", tmp_path / "reference", context_root=tmp_path / "ctx"
    )
    assert layout.context_source("a.csv") == tmp_path / "ctx" / "a.csv"
    assert layout.context_table == tmp_path / "data" / "processed" / "wahlbezirke_kontext.parquet"
    assert layout.crosswalk.name == "wahlbezirke_crosswalk.parquet"
    assert layout.controls.name == "regression_kontrollen.parquet"
    with pytest.raises(ReferenceWriteError, match="context_root"):
        layout.guard_writable(layout.context_source("a.csv"))
    with pytest.raises(ReferenceWriteError, match="context_root"):
        layout.guard_writable(tmp_path / "ctx")
    assert layout.guard_writable(layout.context_table) == layout.context_table
    assert tmp_path / "ctx" not in layout.runtime_dirs()


def test_context_root_is_optional_and_survives_views(tmp_path: Path) -> None:
    flat = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    assert flat.context_root is None
    # Ohne Kontextdaten bleibt der Wächter beim reference_root, und drei Argumente genügen weiter.
    assert flat.guard_writable(tmp_path / "ctx" / "a.csv") == tmp_path / "ctx" / "a.csv"
    with_context = Layout(
        tmp_path / "data", tmp_path / "cache", tmp_path / "reference", "", tmp_path / "ctx"
    )
    assert with_context.for_profile("2025").context_root == tmp_path / "ctx"
    assert with_context.reference_view().context_root == tmp_path / "ctx"


def test_layout_from_settings_takes_the_context_root(tmp_path: Path) -> None:
    assert Layout.from_settings(load_settings(cwd=tmp_path)).context_root == Path("context")
    (tmp_path / "settings.toml").write_text('[context]\nroot = ""\n', encoding="utf-8")
    assert Layout.from_settings(load_settings(cwd=tmp_path)).context_root is None


# --- Option 02: Periode als Profil -----------------------------------------------------------


def test_option02_paths_hang_on_the_profile_root(tmp_path: Path) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference", "2014-2020")
    root = tmp_path / "data" / "2014-2020"
    assert layout.district_shapes_geojson == root / "external" / "Kommunalwahlbezirke.geojson"
    assert layout.district_results_csv == root / "external" / "Wahlbezirk_Wahlergebnis.csv"
    assert layout.precinct_assignment == root / "processed" / "stimmbezirke_zuordnung.parquet"
    assert layout.comparison == root / "processed" / "wahlbezirke_vergleich.parquet"
    assert layout.papers_progress == root / "raw" / "papers.progress.json"


def test_districts_file_names_the_precinct_geojson_per_profile(tmp_path: Path) -> None:
    flat = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    assert flat.districts_file == "Stimmbezirke_2025.geojson"
    old = Layout(
        tmp_path / "data",
        tmp_path / "cache",
        tmp_path / "reference",
        "2014-2020",
        districts_file="Stimmbezirke_2020.geojson",
    )
    name_2020 = "Stimmbezirke_2020.geojson"
    assert old.districts_geojson == tmp_path / "data" / "2014-2020" / "external" / name_2020
    assert old.reference_view().districts_geojson == tmp_path / "reference" / "external" / name_2020
    assert old.for_profile("").districts_file == name_2020
    target = old.for_profile("", districts_file="Stimmbezirke_2025.geojson")
    assert target == flat and target.districts_geojson == flat.districts_geojson
    (tmp_path / "settings.toml").write_text(
        f'[sources.opendata]\ndistricts_file = "{name_2020}"\n', encoding="utf-8"
    )
    assert Layout.from_settings(load_settings(cwd=tmp_path)).districts_file == name_2020
