from __future__ import annotations

from pathlib import Path

from georep.bootstrap import bootstrap
from georep.layout import Layout


def _layout(tmp_path: Path, mini_root: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", mini_root)


def test_bootstrap_copies_inputs_and_converts_the_corpus(tmp_path: Path, mini_root: Path) -> None:
    layout = _layout(tmp_path, mini_root)
    report = bootstrap(layout)
    assert sorted(report.copied) == [
        "Stimmbezirk_Wahlergebnis.csv",
        "paper_with_text.json",
        "streets_per_district.json",
        "wikipedia_dict.json",
    ]
    assert sorted(report.missing) == [
        "Stimmbezirke_2025.geojson",
        "paper_objects.json",
        "paper_urls.json",
    ]
    assert (
        layout.results_csv.read_bytes()
        == (mini_root / "external" / "Stimmbezirk_Wahlergebnis.csv").read_bytes()
    )
    assert layout.corpus_legacy.exists() and not layout.corpus.exists()
    assert "4 Dateien kopiert" in report.summary()


def test_bootstrap_is_idempotent_and_force_recopies(tmp_path: Path, mini_root: Path) -> None:
    layout = _layout(tmp_path, mini_root)
    bootstrap(layout)
    second = bootstrap(layout)
    assert second.copied == [] and len(second.skipped) == 4
    forced = bootstrap(layout, force=True)
    assert len(forced.copied) == 4


def test_bootstrap_never_writes_into_the_reference(tmp_path: Path, mini_root: Path) -> None:
    before = sorted(p.relative_to(mini_root) for p in mini_root.rglob("*"))
    bootstrap(_layout(tmp_path, mini_root))
    after = sorted(p.relative_to(mini_root) for p in mini_root.rglob("*"))
    assert before == after
