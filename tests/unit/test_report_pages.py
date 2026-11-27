"""Unterseiten der Vorhaben (Fundament F2, docs/plan-vorverarbeitung-2026-11.md, § 2.4 und § 7).

Eine Unterseite steht im Rahmen der Hauptseite (Teilvorlagen unter ``templates/frame/``), hat einen
eigenen Schritt hinter ``report`` und einen Eintrag im Abschnitt „Weitere Auswertungen". Ohne
Beiträge gibt es den Abschnitt nicht, und ``index.html`` bleibt bytegleich.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from pathlib import Path

import pytest
from jinja2 import ChoiceLoader, DictLoader

import georep.enrich
import georep.report.pages
from georep.enrich import Contribution
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.report.model import PageLink, ReportModel
from georep.report.pages import Page, page_frame, page_links, render_page
from georep.report.render import Visuals, environment, render_report
from georep.settings import Settings

NOW = dt.datetime(2026, 11, 23, 12, 0, tzinfo=dt.UTC)


def _probe(**changes: object) -> Page:
    page = Page(
        "probe",
        "Probe",
        "Eine Seite, die nur der Test kennt.",
        inputs=lambda layout, settings: (layout.corpus,),
        data=lambda layout, settings: {"n": 3},
    )
    return replace(page, **changes)  # type: ignore[arg-type]


def _env() -> object:
    env = environment()
    assert env.loader is not None
    env.loader = ChoiceLoader(
        [DictLoader({"pages/probe.html.j2": '<p id="probe">{{ data.n }}</p>'}), env.loader]
    )
    return env


def test_die_unterseite_steht_im_rahmen_der_hauptseite(default_settings: Settings) -> None:
    html = render_page(
        page_frame(default_settings, now=NOW, commit="abc1234"),
        _probe(),
        {"n": 3},
        env=_env(),  # type: ignore[arg-type]
    )
    assert "<h1>Probe</h1>" in html
    assert '<p id="probe">3</p>' in html
    assert 'href="index.html">Zur Startseite: ' in html  # plan-startseite, § 3
    # Quellen und Lizenzen stehen seit dem Umzug auf details.html (plan-startseite, § 3)
    assert 'nennen die <a href="details.html">Details</a>' in html
    assert "Hauptseite</a>" not in html
    assert "--accent:" in html  # Farbtokens aus frame/style.css.j2
    assert "showDocuments: showDocuments" in html  # Basis-JavaScript aus frame/script.js.j2
    assert "Commit abc1234" in html


@pytest.mark.parametrize(
    "name", ["Probe", "1probe", "index", "details", "karte", "vergleich", "a_b"]
)
def test_ein_seitenname_ist_ein_einfacher_dateiname(name: str) -> None:
    with pytest.raises(ValueError, match="Seitenname"):
        _probe(name=name)


def test_der_schritt_der_unterseite_steht_hinter_dem_bericht(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(georep.enrich, "CONTRIBUTIONS", (Contribution("probe", pages=(_probe(),)),))
    # die Vorlagen des Pakets gehören zu Seiten, die dieses Register nicht kennt (check_page_files)
    monkeypatch.setattr(georep.report.pages, "pages_folder", lambda: Path("/nonexistent/pages"))
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    steps = build_steps(default_settings, layout)
    names = [s.name for s in steps]
    assert names.index("page_probe") == names.index("report") + 1
    page_step = steps[names.index("page_probe")]
    assert page_step.outputs == (layout.site / "probe.html",)
    assert page_step.extra == steps[names.index("report")].extra  # Vorlagen zählen wie beim Bericht


def test_eine_abgeschaltete_unterseite_fehlt_ganz(
    default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    off = _probe(enabled=lambda settings: False)
    monkeypatch.setattr(georep.enrich, "CONTRIBUTIONS", (Contribution("probe", pages=(off,)),))
    assert page_links(default_settings) == ()


def test_die_hauptseite_nennt_die_unterseite(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    mini_model: ReportModel,
    mini_visuals: Visuals,
) -> None:
    monkeypatch.setattr(georep.enrich, "CONTRIBUTIONS", (Contribution("probe", pages=(_probe(),)),))
    links = page_links(default_settings)
    assert links == (PageLink("probe.html", "Probe", "Eine Seite, die nur der Test kennt."),)
    page = render_report(replace(mini_model, pages=links), mini_visuals)
    assert '<section id="weitere">' in page
    assert '<a href="probe.html">Probe</a>' in page


def test_ohne_unterseiten_gibt_es_den_abschnitt_nicht(
    mini_model: ReportModel, mini_visuals: Visuals
) -> None:
    """Seit Vorhaben 15 hat das Standardprofil eine Unterseite; ohne sie fehlt der Abschnitt."""
    assert 'id="weitere"' not in render_report(replace(mini_model, pages=()), mini_visuals)
