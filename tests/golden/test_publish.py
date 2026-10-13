"""``georep publish``: die Stadtseiten zusammentragen und den Städtevergleich bauen (Stufe F).

Zwei Mini-Läufe in einem ``data_root``, jede Stadt unter ihrem Slug (Punkt 52). ``publish``
kopiert die erste Stadt an die Wurzel von ``data_root/site/``, jede weitere nach
``site/<slug>/``, und schreibt ``vergleich.html`` aus den veröffentlichten Dateien beider Städte.
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
# Option 02: so heißt der Ordner, in den der Pages-Workflow die Seite der zweiten Periode legt
# -- in den der Stadt, nicht nach data/site/ (Punkt 52).
SUBPAGE = "2014-2020"


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
    # Die Unterseite der zweiten Periode, wie `cp -r` im Pages-Workflow sie ablegt: publish muss
    # sie mitnehmen, sonst zeigte der Link des Abschnitts „Zwei Wahlperioden" ins Leere.
    subpage = _layout_of(root, duesseldorf).site / SUBPAGE
    subpage.mkdir(parents=True, exist_ok=True)
    # Gut 1 KB, damit ein kleines Budget im Test wirklich ueberschritten wird
    (subpage / "index.html").write_text(
        "<!doctype html><title>Alte Periode</title>\n<p>" + "Zeile. " * 160 + "</p>\n",
        encoding="utf-8",
    )
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
    # Punkt 52: auch die erste Stadt wird kopiert, denn sie liegt unter ihrem Slug. Ihre
    # Quellseite bleibt dabei ohne die Zeile „Weitere Städte" -- die gehört in die Kopie.
    layout = _layout_of(root, settings)
    source = layout.site
    assert source != site and source == layout.data_root / settings.city.slug / "site"
    assert "Weitere Städte" not in (source / "index.html").read_text(encoding="utf-8")
    # Punkt 50, Review 2026-10-13: publish prüft jede kopierte Seite gegen das Budget. Hier
    # passen beide, also sagt die Zeile nichts darüber.
    assert summary.over_budget == () and "Budget" not in summary.line()


def test_the_subpage_of_a_period_comes_along_and_counts_against_the_budget(
    both_cities: tuple[Path, Settings],
) -> None:
    """Punkt 52: die Periodenseite liegt im Ordner der Stadt, also traegt die Kopie sie mit.

    Und sie ist eine veroeffentlichte Seite wie jede andere: ueber dem Budget nennt publish sie
    (Punkt 50). Beides hielt bis zum Review vom 2026-10-13 kein Test.
    """
    root, settings = both_cities
    site, summary = _publish(root, settings)
    page = site / SUBPAGE / "index.html"
    assert page.is_file() and "Alte Periode" in page.read_text(encoding="utf-8")
    assert summary.over_budget == ()
    # Ein zweiter Lauf ersetzt den ganzen Zielordner; die Unterseite muss wieder da sein
    site, _ = _publish(root, settings)
    assert (site / SUBPAGE / "index.html").is_file()
    tight = settings.model_copy(
        update={"report": settings.report.model_copy(update={"page_budget_bytes": 1000})}
    )
    narrow = publish_sites(tight, _layout_of(root, tight), now=NOW, commit=None)
    assert f"{SUBPAGE}/index.html" in narrow.over_budget and "über dem Budget" in narrow.line()


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
    """Die Zeile steht in der Kopie; publish muss sie bei jedem Lauf wieder setzen können."""
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
    # Die Quelle darf keinen Marker tragen, sonst brächte die Kopie ihn mit; so blieb bis
    # 2026-10-12 verborgen, dass die Kopie den Marker im Ziel löscht. Seit Punkt 52 liegt die
    # Quelle unter dem Slug der Stadt, der Standardordner von publish daneben.
    (_layout_of(root, settings).site / MARKER_NAME).unlink(missing_ok=True)
    (root / "data" / "site" / MARKER_NAME).unlink(missing_ok=True)
    publish_sites(settings, _layout_of(root, settings), now=NOW, commit=None, out=out)
    assert (out / "moenchengladbach" / "index.html").is_file()
    assert (out / MARKER_NAME).is_file(), (
        "publish muss sein Ziel nach dem Kopieren wieder markieren"
    )
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


def test_publish_never_touches_what_lies_next_to_its_target(
    both_cities: tuple[Path, Settings], tmp_path: Path
) -> None:
    """Ersetzt wird der Zielordner; der Nachbar gehoert publish nicht (Review 2026-10-13).

    Der Arbeitsordner hiess ``<ziel>.neu`` und wurde vor dem Kopieren weggeraeumt. Seit die erste
    Stadt kopiert wird, ist das Ziel der beanspruchte Ordner selbst -- und sein Nachbar damit ein
    fremder Ordner, den niemand geprueft hat.
    """
    root, settings = both_cities
    out = tmp_path / "out"
    neighbour = tmp_path / "out.neu"
    (neighbour / "fremd").mkdir(parents=True)
    (neighbour / "fremd" / "datei.txt").write_text("bitte nicht loeschen", encoding="utf-8")
    publish_sites(settings, _layout_of(root, settings), now=NOW, commit=None, out=out)
    assert (neighbour / "fremd" / "datei.txt").read_text(encoding="utf-8") == "bitte nicht loeschen"
    # Und danach liegt kein Arbeitsordner mehr daneben, auch kein neu benannter
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out", "out.neu"]
    assert (out / "index.html").is_file()


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
