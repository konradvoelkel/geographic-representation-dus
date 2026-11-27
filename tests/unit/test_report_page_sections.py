"""Abschnitte aus fremden Beiträgen auf einer Unterseite (Vorarbeit V1, F2-Nachzug).

``docs/plan-zeigen-2026-11.md``, § 4: ein Beitrag hängt einen Abschnitt an die Unterseite eines
anderen (26 an ``vorgaenge.html`` von 14, 28 an ``akteure.html`` von 15). Heute registriert kein
Beitrag eine Seite; geprüft wird darum mit einer Seite und Abschnitten, die nur diese Tests kennen,
ihre Vorlagen in einem ``DictLoader``.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import replace
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

import deal
import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment
from loguru import logger

import georep.enrich
import georep.report.pages
from georep.enrich import CONTRIBUTIONS, Contribution
from georep.errors import SchemaError
from georep.layout import Layout
from georep.pipeline import Step, build_steps
from georep.report.pages import (
    Page,
    PageSection,
    SectionError,
    build_page,
    check_page_files,
    page_frame,
    render_page,
    section_problems,
    sections_for,
)
from georep.report.render import environment
from georep.settings import Settings, available_profiles, load_settings

NOW = dt.datetime(2026, 11, 27, 12, 0, tzinfo=dt.UTC)
OWN = '<p id="eigen">{{ data.n }}</p>\n'
# Eine Vorlage, die am Modell hängt, beginnt mit ``{% if … %}`` (CLAUDE.md); ohne Zeilen zeigt sie
# nichts. Das ``<section id="…">`` setzt der Rahmen (Review K1).
GUEST = (
    "{% if data.rows %}\n"
    "<h2>{{ data.id }}</h2>{% for row in data.rows %}<p>{{ row }}</p>{% endfor %}\n"
    "{% endif %}\n"
)
# Der Gastgeber weiß von seinen Gästen: ein Link auf den Abschnitt, wenn es ihn gibt, sonst der
# Hinweis, den der Gast ersetzt (15 verlinkt auf 28, 26 ersetzt einen Hinweis von 14).
HOST_WITH_HINT = (
    '<p id="gaeste">{{ guests|sort|join(",") }}</p>\n'
    '{% if "gast" in guests %}<p><a href="#gast">Antworten unten</a></p>'
    '{% else %}<p id="hinweis">Antworten stehen in der Niederschrift.</p>{% endif %}\n'
)
TEMPLATES = {
    "pages/probe.html.j2": OWN,
    "pages/probe/gast.html.j2": GUEST,
    "pages/probe/zweiter.html.j2": GUEST,
    "pages/probe/dritter.html.j2": GUEST,
    "pages/probe/gast.css": ".gast { color: var(--accent); }\n",
    "pages/probe/gast.js": "void 'gast';",
}


def _env(extra: Mapping[str, str] | None = None) -> Environment:
    env = environment()
    assert env.loader is not None
    env.loader = ChoiceLoader([DictLoader({**TEMPLATES, **(extra or {})}), env.loader])
    return env


def _page(**changes: object) -> Page:
    page = Page(
        "probe",
        "Probe",
        "Eine Seite, die nur der Test kennt.",
        inputs=lambda layout, settings: (layout.corpus,),
        data=lambda layout, settings: {"n": 3},
    )
    return replace(page, **changes)  # type: ignore[arg-type]


def _section(name: str = "gast", rank: int = 10, **changes: object) -> PageSection:
    section = PageSection(
        page="probe",
        name=name,
        rank=rank,
        inputs=lambda layout, settings: (layout.processed / f"{name}.parquet",),
        data=lambda layout, settings: {"id": name, "rows": [f"Zeile von {name}"]},
    )
    return replace(section, **changes)  # type: ignore[arg-type]


def _register(monkeypatch: pytest.MonkeyPatch, *contributions: Contribution) -> None:
    monkeypatch.setattr(georep.enrich, "CONTRIBUTIONS", contributions)


def _host(page: Page | None = None) -> Contribution:
    return Contribution("14-gastgeber", pages=(page or _page(),))


@pytest.fixture
def log() -> Iterator[list[str]]:
    lines: list[str] = []
    sink = logger.add(lines.append, level="INFO", format="{message}")
    try:
        yield lines
    finally:
        logger.remove(sink)


def _render(
    settings: Settings,
    sections: tuple[PageSection, ...],
    env: Environment | None = None,
    allowed: frozenset[str] = frozenset(),
) -> str:
    return render_page(
        page_frame(settings, now=NOW, commit=None),
        _page(),
        {"n": 3},
        allowed,
        env or _env(),
        tuple((s, s.data(Layout(Path("d"), Path("c"), Path("r")), settings)) for s in sections),
    )


# --- Register und Profil ------------------------------------------------------------------------


def test_ein_abschnitt_haengt_an_der_seite_eines_anderen_beitrags(
    default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    guest = _section()
    _register(monkeypatch, _host(), Contribution("26-gast", sections=(guest,)))
    assert sections_for(default_settings) == {"probe": (guest,)}


def test_die_abschnitte_stehen_nach_rang_nicht_nach_register(
    default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    late, early, middle = _section("gast", 30), _section("zweiter", 10), _section("dritter", 20)
    _register(
        monkeypatch,
        Contribution("28-gast", sections=(late,)),
        _host(),
        Contribution("26-gast", sections=(early, middle)),
    )
    assert sections_for(default_settings) == {"probe": (early, middle, late)}


def test_fehlt_die_zielseite_im_profil_entfaellt_der_abschnitt_mit_einer_zeile_im_log(
    default_settings: Settings, monkeypatch: pytest.MonkeyPatch, log: list[str]
) -> None:
    off = _page(enabled=lambda settings: False)
    _register(monkeypatch, _host(off), Contribution("26-gast", sections=(_section(),)))
    assert sections_for(default_settings) == {}
    assert len(log) == 1
    assert "gast" in log[0] and "26-gast" in log[0] and "probe.html" in log[0]


def test_ein_abgeschalteter_abschnitt_fehlt_ohne_zeile_im_log(
    default_settings: Settings, monkeypatch: pytest.MonkeyPatch, log: list[str]
) -> None:
    off = _section(enabled=lambda settings: False)
    _register(monkeypatch, _host(), Contribution("26-gast", sections=(off,)))
    assert sections_for(default_settings) == {}
    assert log == []


def test_ein_ziel_ohne_registrierte_seite_ist_ein_fehler(
    default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    typo = _section(page="prob")
    _register(monkeypatch, _host(), Contribution("26-gast", sections=(typo,)))
    with pytest.raises(SectionError, match=r"26-gast.*gast.*prob\.html"):
        sections_for(default_settings)


@pytest.mark.parametrize(
    ("first", "second", "what"),
    [
        (_section("gast", 10), _section("zweiter", 10), "Rang 10"),
        (_section("gast", 10), _section("gast", 20), "Name gast"),
    ],
)
def test_rang_und_name_sind_je_seite_eindeutig(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    first: PageSection,
    second: PageSection,
    what: str,
) -> None:
    _register(
        monkeypatch,
        _host(),
        Contribution("26-gast", sections=(first,)),
        Contribution("28-gast", sections=(second,)),
    )
    with pytest.raises(SectionError, match=rf"probe\.html: {what} doppelt.*26-gast.*28-gast"):
        sections_for(default_settings)


def test_gleicher_rang_auf_zwei_seiten_ist_kein_fehler() -> None:
    entries = [("26-gast", _section("gast", 10)), ("28-gast", _section("gast", 10, page="zweite"))]
    assert section_problems({"probe", "zweite"}, entries) == []


@pytest.mark.parametrize("target", ["Probe", "index", "karte", "vergleich", "a_b"])
def test_das_ziel_ist_ein_seitenname(target: str) -> None:
    with pytest.raises(ValueError, match="Zielseite"):
        _section(page=target)


@pytest.mark.parametrize("name", ["Gast", "1gast", "a_b", ""])
def test_der_name_des_abschnitts_ist_ein_einfacher_dateiname(name: str) -> None:
    with pytest.raises(ValueError, match="Abschnittsname"):
        _section(name=name)


def test_jedes_ziel_im_register_ist_eine_registrierte_seite() -> None:
    """Über das echte Register: kein Ziel ohne Seite, kein Rang und kein Name doppelt je Seite."""
    pages = {page.name for contribution in CONTRIBUTIONS for page in contribution.pages}
    entries = [(c.name, s) for c in CONTRIBUTIONS for s in c.sections]
    assert section_problems(pages, entries) == []


def _templates_without_data_guard(
    folder: Traversable, entries: Sequence[tuple[str, PageSection]]
) -> list[str]:
    """Abschnitte, deren Vorlage fehlt oder nicht mit ``{% if data.`` beginnt (Review N5).

    ``{% if model.`` oder ``{% if rows %}`` hinge nicht an den eigenen Daten: ``model`` ist der
    Rahmen der Seite, und ein freier Name ist unter ``StrictUndefined`` ein Fehler.
    """
    found: list[str] = []
    for contribution, section in entries:
        path = folder.joinpath(*section.template.split("/"))
        if not path.is_file():
            found.append(f"{contribution} {section.name}: Vorlage fehlt")
        elif not path.read_text(encoding="utf-8").lstrip().startswith("{% if data."):
            found.append(f"{contribution} {section.name}: beginnt nicht mit {{% if data.")
    return found


def test_jede_abschnittsvorlage_im_register_liegt_im_paket_und_beginnt_mit_if_data() -> None:
    folder = resources.files("georep.report") / "templates"
    entries = [(c.name, s) for c in CONTRIBUTIONS for s in c.sections]
    assert _templates_without_data_guard(folder, entries) == []


def test_die_pruefung_der_vorlagen_verlangt_if_data(tmp_path: Path) -> None:
    for name, source in (
        ("gast", "{% if data.rows %}x{% endif %}\n"),
        ("zweiter", "{% if model.city %}x{% endif %}\n"),
        ("dritter", "{% if rows %}x{% endif %}\n"),
    ):
        (tmp_path / "pages" / "probe").mkdir(parents=True, exist_ok=True)
        (tmp_path / "pages" / "probe" / f"{name}.html.j2").write_text(source, encoding="utf-8")
    entries = [("26-gast", _section(name)) for name in ("gast", "zweiter", "dritter", "vierter")]
    assert _templates_without_data_guard(tmp_path, entries) == [
        "26-gast zweiter: beginnt nicht mit {% if data.",
        "26-gast dritter: beginnt nicht mit {% if data.",
        "26-gast vierter: Vorlage fehlt",
    ]


# --- Dateien unter templates/pages/ (Review N4) ------------------------------------------------


def _files(root: Path, *names: str) -> Path:
    for name in names:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("{% if data.rows %}{% endif %}\n", encoding="utf-8")
    return root


GUESTS = [("26-gast", _section())]


def test_dateien_mit_gegenstueck_im_register_sind_in_ordnung(tmp_path: Path) -> None:
    names = ("probe.html.j2", "probe.css", "probe/gast.html.j2", "probe/gast.css", "probe/gast.js")
    check_page_files({"probe"}, GUESTS, _files(tmp_path, *names))
    check_page_files({"probe"}, GUESTS, tmp_path / "fehlt")  # kein Ordner, nichts zu prüfen


@pytest.mark.parametrize(
    ("name", "why"),
    [
        ("probe/alt.css", "probe/alt.css: keine Vorlage alt.html.j2"),
        ("probe/gast.js.bak.js", "keine Vorlage gast.js.bak.html.j2"),
        ("probe/alt.html.j2", "probe/alt.html.j2: kein Eintrag im Register"),
        ("fremd/gast.html.j2", "fremd/: keine Seite im Register"),
        ("fremd.html.j2", "fremd.html.j2: kein Eintrag im Register"),
        ("fremd.js", "fremd.js: keine Vorlage fremd.html.j2"),
    ],
)
def test_eine_verwaiste_datei_ist_ein_schemafehler(tmp_path: Path, name: str, why: str) -> None:
    folder = _files(tmp_path, "probe.html.j2", "probe/gast.html.j2", name)
    with pytest.raises(SchemaError, match=why):
        check_page_files({"probe"}, GUESTS, folder)


def test_das_register_prueft_die_dateien_des_pakets(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``sections_for`` prüft beim Aufbau der Schritte, wie ``render.sections`` beim Bericht."""
    folder = _files(tmp_path, "probe/gast.html.j2", "probe/vergessen.css")
    monkeypatch.setattr(georep.report.pages, "pages_folder", lambda: folder)
    _register(monkeypatch, _host(), Contribution("26-gast", sections=(_section(),)))
    with pytest.raises(SchemaError, match="vergessen.css"):
        sections_for(default_settings)


# --- Schritt ------------------------------------------------------------------------------------


def test_der_schritt_der_seite_liest_auch_die_eingaben_ihrer_abschnitte(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    same = _section("zweiter", 20, inputs=lambda layout, settings: (layout.corpus,))
    _register(monkeypatch, _host(), Contribution("26-gast", sections=(_section(), same)))
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    steps = {step.name: step for step in build_steps(default_settings, layout)}
    # die Eingabe der Seite zuerst, dann die des Abschnitts; ``corpus`` liest auch ``zweiter``,
    # steht aber nur einmal im Stamp
    assert steps["page_probe"].inputs == (layout.corpus, layout.processed / "gast.parquet")


def _unproduced_page_inputs(steps: Sequence[Step]) -> list[str]:
    """Eingaben eines ``page_*``, die im Lauf niemand bereitstellt (Review N1).

    Bereit ist, was ein früherer Schritt schreibt, außer einem Modellschritt (er läuft nur mit
    ``--models``, auf Pages nie), und was schon ein früherer Schritt liest, ohne dass einer davor
    es schreibt: das bringt ``bootstrap`` aus der Referenz oder einem Paket, sonst bräche schon
    jener Schritt ab (``check_step_order`` schließt aus, dass ein späterer es schreibt). Eine
    Datei, die erst die Seite liest und niemand schreibt, fehlt im Lauf, und ``page_*`` bricht ab.
    """
    written: set[Path] = set()
    brought: set[Path] = set()
    missing: list[str] = []
    for step in steps:
        if step.name.startswith("page_"):
            missing.extend(
                f"{step.name}: {path}"
                for path in step.inputs
                if path not in written and path not in brought
            )
            continue
        brought.update(path for path in step.inputs if path not in written)
        if step.models is None:
            written.update(step.outputs)
    return missing


@pytest.mark.parametrize("profile", available_profiles())
def test_jede_eingabe_jeder_unterseite_entsteht_im_lauf(tmp_path: Path, profile: str) -> None:
    """Über das echte Register in jedem Paketprofil; heute ohne Seiten, er greift ab dem ersten Gast."""
    settings = load_settings(profile=profile, cwd=Path("/nonexistent")).model_copy(
        update={"data_root": tmp_path / "data", "cache_root": tmp_path / "cache"}
    )
    assert _unproduced_page_inputs(build_steps(settings, Layout.from_settings(settings))) == []


def test_die_pruefung_der_eingaben_findet_einen_gast_ohne_schreiber(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``gast`` liest eine Datei, die kein Schritt schreibt; ``zweiter`` den Index des Kerns."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    index = layout.processed / "inverted_index.parquet"
    fine = _section("zweiter", 20, inputs=lambda layout, settings: (index,))
    _register(monkeypatch, _host(), Contribution("26-gast", sections=(_section(), fine)))
    steps = build_steps(default_settings, layout)
    assert index in {path for step in steps if step.name == "index" for path in step.outputs}
    assert _unproduced_page_inputs(steps) == [f"page_probe: {layout.processed / 'gast.parquet'}"]


def test_der_schritt_schreibt_die_seite_mit_ihren_abschnitten(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _env()
    monkeypatch.setattr(georep.report.pages, "environment", lambda: env)
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    line = build_page(layout, default_settings, _page(), (_section(),), now=NOW, commit=None)
    html = (layout.site / "probe.html").read_text(encoding="utf-8")
    assert line.startswith("probe.html, ")
    assert '<section id="gast">\n<h2>gast</h2><p>Zeile von gast</p></section>' in html


# --- Darstellung --------------------------------------------------------------------------------


def test_die_fremden_abschnitte_stehen_nach_dem_eigenen_inhalt_in_main(
    default_settings: Settings,
) -> None:
    html = _render(default_settings, (_section("gast", 10), _section("zweiter", 20)))
    main = html[html.index("<main>") : html.index("</main>")]
    assert main.index('<p id="eigen">3</p>') < main.index('id="gast"') < main.index('id="zweiter"')


def test_jeder_abschnitt_sieht_nur_seine_eigenen_daten(default_settings: Settings) -> None:
    probe = _env({"pages/probe/gast.html.j2": "{% if data %}<i>{{ data|length }}</i>{% endif %}\n"})
    html = _render(default_settings, (_section(),), env=probe)
    assert "<i>2</i>" in html  # ``id`` und ``rows``, nicht das ``n`` der Seite


def test_ohne_zeilen_bleibt_vom_abschnitt_nur_sein_anker(default_settings: Settings) -> None:
    """Der Anker steht, sobald der Gast in ``guests`` steht; ein Link des Gastgebers bleibt gültig."""
    empty = _section(data=lambda layout, settings: {"id": "gast", "rows": []})
    assert '<section id="gast">\n</section>' in _render(default_settings, (empty,))


@pytest.mark.parametrize("with_guest", [True, False])
def test_die_seite_kennt_ihre_gaeste_und_ersetzt_damit_einen_hinweis(
    tmp_path: Path,
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    with_guest: bool,
) -> None:
    """Review K1: ``guests`` sind die Namen der Gäste in diesem Profil, jeder mit Anker."""
    env = _env({"pages/probe.html.j2": HOST_WITH_HINT})
    monkeypatch.setattr(georep.report.pages, "environment", lambda: env)
    guest = _section(enabled=lambda settings: with_guest)
    off = _section("zweiter", 20, enabled=lambda settings: False)
    _register(monkeypatch, _host(), Contribution("26-gast", sections=(guest, off)))
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    attached = sections_for(default_settings).get("probe", ())
    build_page(layout, default_settings, _page(), attached, now=NOW, commit=None)
    html = (layout.site / "probe.html").read_text(encoding="utf-8")
    if with_guest:
        assert '<p id="gaeste">gast</p>' in html  # ``zweiter`` ist aus und fehlt
        assert '<a href="#gast">' in html and '<section id="gast">' in html
        assert 'id="hinweis"' not in html
    else:
        assert '<p id="gaeste"></p>' in html
        assert '<p id="hinweis">' in html and 'href="#gast"' not in html
        assert 'id="gast"' not in html


@pytest.mark.parametrize(
    ("templates", "name"),
    [
        ({"pages/probe.html.j2": '<p id="gast">eigen</p>\n'}, "gast"),  # ID der Seite
        ({"pages/probe/gast.html.j2": '{% if data.id %}<p id="gast">x</p>{% endif %}\n'}, "gast"),
        ({"pages/probe/docs.html.j2": GUEST}, "docs"),  # der Dokumentdialog des Rahmens
    ],
)
def test_der_anker_eines_gasts_kollidiert_mit_keiner_id_der_seite(
    default_settings: Settings, templates: dict[str, str], name: str
) -> None:
    with pytest.raises(deal.PostContractError):
        _render(default_settings, (_section(name),), env=_env(templates))


def test_ohne_abschnitte_bleibt_der_rahmen_wie_vorher(default_settings: Settings) -> None:
    """Der Inhalt der Seite endet direkt vor ``</main>``, wie vor V1 (bytegleich)."""
    assert '<main>\n<p id="eigen">3</p></main>\n<footer>' in _render(default_settings, ())


def test_css_und_javascript_der_abschnitte_stehen_auf_der_seite(
    default_settings: Settings,
) -> None:
    html = _render(default_settings, (_section(), _section("zweiter", 20)))
    assert ".gast { color: var(--accent); }\n</style>" in html
    assert "<script>\nvoid 'gast';\n</script>" in html


def test_css_und_javascript_der_seite_stehen_vor_denen_der_gaeste(
    default_settings: Settings,
) -> None:
    """Review N8: erst die Seite, dann die Gäste in der Folge der Seite (``sections_for``); ein
    Gast kann so eine Regel der Seite überschreiben, nicht umgekehrt."""
    env = _env(
        {
            "pages/probe.css": ".seite {}\n",
            "pages/probe/zweiter.css": ".zweiter {}\n",
            "pages/probe.js": "void 'seite';",
            "pages/probe/zweiter.js": "void 'zweiter';",
        }
    )
    html = _render(default_settings, (_section("gast", 10), _section("zweiter", 20)), env=env)
    style = html[html.index("<style>") : html.index("</style>")]
    assert style.index(".seite {}") < style.index(".gast {") < style.index(".zweiter {}")
    assert html.index("void 'seite'") < html.index("void 'gast'") < html.index("void 'zweiter'")
    assert html.index("</style>") < html.index("<main>") < html.index("void 'seite'")


def test_jede_javascript_datei_bekommt_ein_eigenes_skript(default_settings: Settings) -> None:
    """Review N2: ein Fehler im Skript eines Gasts legt das der Seite und der anderen nicht still."""
    env = _env({"pages/probe.js": "void 'seite';", "pages/probe/zweiter.js": "void 'zweiter';"})
    html = _render(default_settings, (_section(), _section("zweiter", 20)), env=env)
    blocks = "<script>\nvoid 'seite';\n</script>\n<script>\nvoid 'gast';\n</script>\n"
    assert blocks + "<script>\nvoid 'zweiter';\n</script>\n</body>" in html


def test_css_und_javascript_mit_crlf_stehen_mit_lf_auf_der_seite(
    default_settings: Settings,
) -> None:
    """Review N3: wie ``read_text`` vor V1; eine Datei aus einem Windows-Editor ändert die Seite nicht."""
    env = _env(
        {"pages/probe/gast.css": ".gast {}\r\n.b {}\r", "pages/probe/gast.js": "void 1;\r\n"}
    )
    html = _render(default_settings, (_section(),), env=env)
    assert "\r" not in html
    assert ".gast {}\n.b {}\n</style>" in html and "<script>\nvoid 1;\n\n</script>" in html


def test_ein_abschnitt_bringt_seine_links_nach_aussen_mit(
    tmp_path: Path, default_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.org/ratsinfo"
    env = _env({"pages/probe/gast.html.j2": f'{{% if data %}}<a href="{url}">R</a>{{% endif %}}\n'})
    monkeypatch.setattr(georep.report.pages, "environment", lambda: env)
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    with pytest.raises(deal.PostContractError):
        build_page(layout, default_settings, _page(), (_section(),), now=NOW, commit=None)
    allowed: Callable[[Settings], frozenset[str]] = lambda settings: frozenset({url})  # noqa: E731
    build_page(layout, default_settings, _page(), (_section(links=allowed),), now=NOW, commit=None)
    assert f'<a href="{url}">R</a>' in (layout.site / "probe.html").read_text(encoding="utf-8")
