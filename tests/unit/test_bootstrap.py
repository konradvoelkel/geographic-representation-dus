from __future__ import annotations

from pathlib import Path

from georep.bootstrap import bootstrap
from georep.layout import Layout
from georep.settings import Settings


def _layout(tmp_path: Path, mini_root: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", mini_root)


def test_bootstrap_copies_inputs_and_converts_the_corpus(tmp_path: Path, mini_root: Path) -> None:
    layout = _layout(tmp_path, mini_root)
    report = bootstrap(layout)
    assert sorted(report.copied) == [
        "Stimmbezirk_Wahlergebnis.csv",
        "Stimmbezirke_2025.geojson",
        # Punkt 58: die Fixture bringt die Beratungsfolge ihrer 200 Dokumente selbst mit, und
        # dann gilt ihre Datei und nicht das Paket der Hauptperiode
        "beratungsfolge.parquet",
        "streets_per_district.json",
        "wikipedia_dict.json",
    ]
    assert report.missing == []
    assert (report.papers, report.texts) == (200, 200)
    assert (
        layout.results_csv.read_bytes()
        == (mini_root / "external" / "Stimmbezirk_Wahlergebnis.csv").read_bytes()
    )
    assert layout.papers.exists() and layout.texts.exists() and not layout.corpus.exists()
    assert (
        "5 Dateien kopiert, 0 übersprungen, 0 in Referenz oder Kontext nicht gefunden"
        in report.summary()
    )
    assert "200 Paper und 200 Texte" in report.summary()


def test_bootstrap_is_idempotent_and_force_recopies(tmp_path: Path, mini_root: Path) -> None:
    layout = _layout(tmp_path, mini_root)
    bootstrap(layout)
    second = bootstrap(layout)
    assert second.copied == [] and len(second.skipped) == 5 and second.papers is None
    forced = bootstrap(layout, force=True)
    assert len(forced.copied) == 5 and forced.papers == 200


def test_bootstrap_never_writes_into_the_reference(tmp_path: Path, mini_root: Path) -> None:
    before = sorted(p.relative_to(mini_root) for p in mini_root.rglob("*"))
    bootstrap(_layout(tmp_path, mini_root))
    after = sorted(p.relative_to(mini_root) for p in mini_root.rglob("*"))
    assert before == after


# --- Option 03: die Fremddaten kommen aus context_root ------------------------------------------


def test_bootstrap_copies_the_context_files_next_to_the_reference_inputs(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    names = default_settings.context.files.names()
    layout = Layout(
        tmp_path / "data", tmp_path / "cache", mini_root, context_root=mini_root / "context"
    )
    report = bootstrap(layout, context_files=names)
    assert len(report.copied) == 8 and report.missing == []
    assert "8 Dateien kopiert" in report.summary()
    for name in names:
        assert (layout.external / name).read_bytes() == layout.context_source(name).read_bytes()


def test_bootstrap_without_context_root_copies_only_the_reference(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    report = bootstrap(_layout(tmp_path, mini_root), context_files=("quartiersatlas_2024.csv",))
    assert len(report.copied) == 5 and report.missing == []


def test_bootstrap_reports_missing_context_files_without_failing(
    tmp_path: Path, mini_root: Path
) -> None:
    layout = Layout(
        tmp_path / "data", tmp_path / "cache", mini_root, context_root=tmp_path / "leer"
    )
    report = bootstrap(layout, context_files=("fehlt.csv",))
    assert report.missing == ["fehlt.csv"] and len(report.copied) == 5
    assert "1 in Referenz oder Kontext nicht gefunden" in report.summary()


# --- Option 07: Monitoring -------------------------------------------------------------------


def test_bootstrap_without_seed_copies_inputs_and_leaves_the_stores_alone(
    tmp_path: Path, mini_root: Path
) -> None:
    layout = _layout(tmp_path, mini_root).for_profile("2025")
    report = bootstrap(layout, seed_corpus=False)
    assert len(report.copied) == 5 and report.missing == []
    assert report.papers is None and report.texts is None
    assert not layout.papers.exists() and not layout.texts.exists()
    assert layout.pdf_manifest.is_file()  # der PDF-Store ist angelegt, die Eingabe von texts
    assert layout.external == tmp_path / "data" / "2025" / "external"
    assert "Stores nicht aus der Referenz gefüllt" in report.summary()
    # Ein zweiter Aufruf, auch mit force, fuellt die Stores weiterhin nicht
    forced = bootstrap(layout, force=True, seed_corpus=False)
    assert len(forced.copied) == 5 and forced.papers is None
    assert not layout.papers.exists() and not layout.texts.exists()
