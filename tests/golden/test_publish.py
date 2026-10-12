"""``georep publish``: die Stadtseiten zusammentragen und den Städtevergleich bauen (Stufe F).

Zwei Mini-Läufe in einem ``data_root``: Düsseldorf flach (wie heute) und Mönchengladbach unter
seinem Profil. ``publish`` kopiert die zweite Stadt in einen Unterordner, lässt die erste an der
Wurzel liegen und schreibt ``vergleich.html`` aus den veröffentlichten Dateien beider Städte.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import replace
from pathlib import Path

import pytest

from georep.bootstrap import bootstrap
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.report.publish import PublishSummary, publish_sites
from georep.settings import Settings, load_settings
from tests.conftest import MG, MINI, mg_settings

NOW = dt.datetime(2026, 10, 12, 12, 0, tzinfo=dt.UTC)


def _run(root: Path, settings: Settings, reference: Path) -> Layout:
    layout = replace(
        Layout.from_settings(settings),
        data_root=root / "data",
        cache_root=root / "cache",
        reference_root=reference,
        # Option 03: die Fremddaten liegen bei der Fixture; die zweite Stadt hat keine
        context_root=reference / "context" if settings.context.root is not None else None,
    )
    bootstrap(layout, context_files=settings.context.files.names())
    run_pipeline(build_steps(settings, layout), settings)
    return layout


@pytest.fixture(scope="module")
def both_cities(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Settings]:
    """Beide Städte in einem ``data_root``, wie nach zwei Läufen auf demselben Rechner."""
    root = tmp_path_factory.mktemp("publish")
    duesseldorf = load_settings(cwd=Path("/nonexistent"))
    moenchengladbach = mg_settings()
    _run(root, duesseldorf, MINI)
    _run(root, moenchengladbach, MG)
    return root, duesseldorf


def _publish(root: Path, settings: Settings) -> tuple[Path, PublishSummary]:
    layout = replace(
        Layout.from_settings(settings), data_root=root / "data", cache_root=root / "cache"
    )
    summary = publish_sites(settings, layout, now=NOW, commit="abc1234")
    return layout.data_root / "site", summary


def test_publish_keeps_the_first_city_at_the_root_and_nests_the_others(
    both_cities: tuple[Path, Settings],
) -> None:
    root, settings = both_cities
    site, summary = _publish(root, settings)
    assert (site / "index.html").is_file() and (site / "karte.html").is_file()
    assert (site / "data" / "summary.json").is_file()
    assert (site / "moenchengladbach" / "index.html").is_file()
    assert (site / "moenchengladbach" / "data" / "summary.json").is_file()
    assert summary.cities == ("duesseldorf", "moenchengladbach") and not summary.missing
    assert summary.comparison and "2 Städte" in summary.line()


def test_the_comparison_page_shows_both_cities(both_cities: tuple[Path, Settings]) -> None:
    root, settings = both_cities
    site, _ = _publish(root, settings)
    page = (site / "vergleich.html").read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>") and '<html lang="de">' in page
    assert "Düsseldorf" in page and "Mönchengladbach" in page
    assert page.count("<svg") >= 3  # zwei kleine Karten und ein Streudiagramm
    assert '<a href="./">' in page or '<a href="index.html">' in page
    assert '<a href="moenchengladbach/">' in page
    assert len(page.encode("utf-8")) < 400_000


def test_the_comparison_page_links_only_where_it_may(both_cities: tuple[Path, Settings]) -> None:
    from georep.report.publish import COMPARISON_LINKS
    from georep.report.render import external_links

    root, settings = both_cities
    site, _ = _publish(root, settings)
    page = (site / "vergleich.html").read_text(encoding="utf-8")
    assert set(external_links(page)) <= COMPARISON_LINKS
    assert "<script src=" not in page and "<link " not in page


def test_publishing_twice_changes_nothing_but_the_time(
    both_cities: tuple[Path, Settings],
) -> None:
    root, settings = both_cities
    site, _ = _publish(root, settings)
    first = (site / "vergleich.html").read_text(encoding="utf-8")
    site, _ = _publish(root, settings)
    second = (site / "vergleich.html").read_text(encoding="utf-8")
    assert first == second  # die Zeit ist Eingabe, also ist der Lauf wiederholbar


def test_a_city_without_a_run_is_named_and_leaves_no_comparison(tmp_path: Path) -> None:
    duesseldorf = load_settings(cwd=Path("/nonexistent"))
    _run(tmp_path, duesseldorf, MINI)
    site, summary = _publish(tmp_path, duesseldorf)
    assert summary.cities == ("duesseldorf",) and summary.missing == ("moenchengladbach",)
    assert not summary.comparison and not (site / "vergleich.html").exists()
    assert "kein Lauf" in summary.line() and "moenchengladbach" in summary.line()
    assert (site / "index.html").is_file()  # die vorhandene Stadt bleibt erreichbar


def test_the_comparison_names_the_numbers_of_both_cities(
    both_cities: tuple[Path, Settings],
) -> None:
    import json

    root, settings = both_cities
    site, _ = _publish(root, settings)
    page = (site / "vergleich.html").read_text(encoding="utf-8")
    for slug, folder in (("duesseldorf", site), ("moenchengladbach", site / "moenchengladbach")):
        summary = json.loads((folder / "data" / "summary.json").read_text(encoding="utf-8"))
        assert summary["city"]["slug"] == slug
        assert str(summary["figures"]["districts"]) in page
    # Hinweise zur Vergleichbarkeit stehen auf der Seite, nicht im Kopf des Lesers
    assert "Vergleichbarkeit" in page and "Wahlberechtigte je Wahlbezirk" in page


def test_the_comparison_is_a_table_with_one_row_per_city(
    both_cities: tuple[Path, Settings],
) -> None:
    root, settings = both_cities
    site, _ = _publish(root, settings)
    page = (site / "vergleich.html").read_text(encoding="utf-8")
    body = re.search(r"<tbody>(.*?)</tbody>", page, re.S)
    assert body is not None and body.group(1).count("<tr") == 2
