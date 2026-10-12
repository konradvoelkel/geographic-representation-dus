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
from georep.layout import Layout, ReferenceWriteError
from georep.pipeline import build_steps, run_pipeline
from georep.report.publish import (
    MARKER_NAME,
    NEIGHBOURS_MARKER,
    PublishSummary,
    PublishTargetError,
    publish_sites,
)
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


def _layout_of(root: Path, settings: Settings) -> Layout:
    return replace(
        Layout.from_settings(settings), data_root=root / "data", cache_root=root / "cache"
    )


def _publish(root: Path, settings: Settings) -> tuple[Path, PublishSummary]:
    layout = _layout_of(root, settings)
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


def test_publish_writes_the_neighbour_line_into_both_pages(
    both_cities: tuple[Path, Settings],
) -> None:
    root, settings = both_cities
    site, _ = _publish(root, settings)
    first = (site / "index.html").read_text(encoding="utf-8")
    second = (site / "moenchengladbach" / "index.html").read_text(encoding="utf-8")
    assert 'Weitere Städte: <a href="moenchengladbach/">Mönchengladbach</a>' in first
    assert '<a href="vergleich.html">Städtevergleich</a>' in first
    assert 'Weitere Städte: <a href="../">Düsseldorf</a>' in second
    assert '<a href="../vergleich.html">Städtevergleich</a>' in second
    # Die Marke bleibt als Kommentar stehen: die Seite der ersten Stadt wird nicht neu kopiert,
    # und der nächste publish-Lauf muss die Zeile wieder ersetzen können.
    assert first.count(NEIGHBOURS_MARKER) == 1 and second.count(NEIGHBOURS_MARKER) == 1
    assert first.count("Weitere Städte") == 1 and second.count("Weitere Städte") == 1


def test_without_a_second_city_no_page_links_anywhere(tmp_path: Path) -> None:
    """Die tote Zeile ist schlimmer als keine: ohne Lauf der zweiten Stadt gibt es keine Links."""
    duesseldorf = load_settings(cwd=Path("/nonexistent"))
    _run(tmp_path, duesseldorf, MINI)
    site, summary = _publish(tmp_path, duesseldorf)
    page = (site / "index.html").read_text(encoding="utf-8")
    assert not summary.comparison
    assert "Weitere Städte" not in page and "vergleich.html" not in page
    assert "moenchengladbach/" not in page and page.count(NEIGHBOURS_MARKER) == 1


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


def test_the_neighbour_line_survives_a_second_publish(both_cities: tuple[Path, Settings]) -> None:
    """Die Seite der ersten Stadt wird nicht kopiert; ihre Zeile muss publish neu setzen können."""
    root, settings = both_cities
    site, _ = _publish(root, settings)
    once = (site / "index.html").read_text(encoding="utf-8")
    site, _ = _publish(root, settings)
    twice = (site / "index.html").read_text(encoding="utf-8")
    assert once == twice
    assert twice.count("Weitere Städte") == 1
    assert 'Weitere Städte: <a href="moenchengladbach/">Mönchengladbach</a>' in twice


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


def test_a_city_that_lost_its_run_leaves_the_published_folder(
    both_cities: tuple[Path, Settings], tmp_path: Path
) -> None:
    """Ein Stadtordner ohne Lauf und ohne Link wäre tote Last; publish räumt ihn weg."""
    root, settings = both_cities
    out = tmp_path / "zwei-dann-eine"
    publish_sites(settings, _layout_of(root, settings), now=NOW, commit=None, out=out)
    assert (out / "moenchengladbach" / "index.html").is_file()
    moved = tmp_path / "beiseite"
    (root / "data" / "moenchengladbach" / "site").rename(moved)
    try:
        summary = publish_sites(settings, _layout_of(root, settings), now=NOW, commit=None, out=out)
    finally:
        moved.rename(root / "data" / "moenchengladbach" / "site")
    assert summary.missing == ("moenchengladbach",)
    assert not (out / "moenchengladbach").exists()
    assert not (out / "vergleich.html").exists()
    assert (out / "index.html").is_file()


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


# --- Das Ziel von --out ------------------------------------------------------------------------


def test_publish_refuses_a_target_it_did_not_make(
    both_cities: tuple[Path, Settings], tmp_path: Path
) -> None:
    """``--out`` zeigt leicht auf den falschen Ordner; gelöscht wird nur, was publish gehört."""
    root, settings = both_cities
    layout = replace(
        Layout.from_settings(settings), data_root=root / "data", cache_root=root / "cache"
    )
    foreign = tmp_path / "wichtig"
    foreign.mkdir()
    (foreign / "diplomarbeit.txt").write_text("bitte nicht löschen", encoding="utf-8")
    with pytest.raises(PublishTargetError, match="nicht von georep publish"):
        publish_sites(settings, layout, now=NOW, commit=None, out=foreign)
    assert (foreign / "diplomarbeit.txt").read_text(encoding="utf-8") == "bitte nicht löschen"
    assert list(foreign.iterdir()) == [foreign / "diplomarbeit.txt"]


def test_publish_takes_an_empty_target_and_its_own_from_then_on(
    both_cities: tuple[Path, Settings], tmp_path: Path
) -> None:
    root, settings = both_cities
    layout = replace(
        Layout.from_settings(settings), data_root=root / "data", cache_root=root / "cache"
    )
    out = tmp_path / "veroeffentlicht"
    first = publish_sites(settings, layout, now=NOW, commit=None, out=out)
    assert first.comparison and (out / "index.html").is_file()
    assert (out / MARKER_NAME).is_file()  # daran erkennt der nächste Lauf seinen eigenen Ordner
    second = publish_sites(settings, layout, now=NOW, commit=None, out=out)
    assert second.cities == first.cities
    assert (out / "vergleich.html").read_text(encoding="utf-8")


def test_publish_refuses_a_target_under_the_reference(
    both_cities: tuple[Path, Settings],
) -> None:
    root, settings = both_cities
    layout = replace(
        Layout.from_settings(settings),
        data_root=root / "data",
        cache_root=root / "cache",
        reference_root=root / "reference",
    )
    with pytest.raises(ReferenceWriteError):
        publish_sites(settings, layout, now=NOW, commit=None, out=root / "reference" / "site")
