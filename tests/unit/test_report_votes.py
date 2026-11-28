"""Der Abschnitt „Abstimmungen" auf ``akteure.html`` (Vorhaben 28, Stufe 3; Messdokument § 7, § 10).

Drei Gruppen. Der Prüfsatz kommt aus ``validierung/28-abstimmungen/guete.json`` und, was die Datei
nicht trägt, aus ``RULE_CHECK``; eine andere Kodierung macht die Konstante ungültig, und nur Fragen
mit ``alpha_genuegt`` erscheinen. Der Abschnitt je Profilfall: alles (Hauptperiode), nur die
Nebenrechnung R2 (laufende Periode), keine Prüfung (2014 bis 2020), der Schritt aus (zweite Stadt).
Die echte Seite der Mini-Fixture: der Gast auf ``akteure.html`` mit Anker und Eintrag im
Verzeichnis, die drei Downloads (je Punkt nur Parquet) und ihre Spalten auf ``spalten.html``.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.analysis.votes import (
    LEVEL_A,
    LEVEL_B,
    MAIN,
    R2,
    HypothesisInputs,
    VoteRules,
    Window,
    body_summary,
    hypothesis_rows,
    votes_table,
)
from georep.enrich import CONTRIBUTIONS
from georep.enrich.votes import SECTIONS, TABLES, party_labels, vote_files, votes_enabled
from georep.errors import SchemaError
from georep.layout import Layout
from georep.prep.bodies import BodyRules
from georep.report.render import environment
from georep.report.votes import (
    RULE_CHECK,
    SECTION,
    VALIDATION_PROJECT,
    build_votes,
    read_check,
    votes_section_data,
    votes_section_inputs,
    votes_section_links,
)
from georep.settings import Settings, load_settings
from tests.conftest import REPO

NOWHERE = Path("/nonexistent")
PAGE_BUDGET = 500_000  # docs/plan-zeigen-2026-11.md, § 6
TEMPLATE = (
    REPO / "src" / "georep" / "report" / "templates" / "pages" / "akteure" / "abstimmungen.html.j2"
)


def _settings(profile: str = "duesseldorf", root: Path = REPO / "validierung") -> Settings:
    settings = load_settings(profile=profile, cwd=NOWHERE)
    return settings.model_copy(
        update={"validation": settings.validation.model_copy(update={"root": root})}
    )


def _quality() -> dict[str, Any]:
    path = REPO / "validierung" / VALIDATION_PROJECT / "guete.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


# --- Der Prüfsatz ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("profile", "measured"),
    [
        ("duesseldorf", True),
        ("duesseldorf-vergleich", True),  # rechnet im Ordner der Hauptperiode
        ("duesseldorf-2014", False),  # die Stichprobe ist aus der Hauptperiode gezogen
        ("duesseldorf-2025", False),
        ("moenchengladbach", False),
    ],
)
def test_der_pruefsatz_kommt_aus_guete_json(profile: str, measured: bool) -> None:
    check = read_check(_settings(profile))
    quality = _quality()
    assert check.sentence == quality["satz"]
    assert check.same_model
    assert check.measured is measured
    assert [(a.question, a.agreed, a.paired) for a in check.agreements] == [
        (q, quality["fragen"][q]["einig"], quality["fragen"][q]["beide"])
        for q in ("ergebnis", "form")
    ]
    assert check.agreements[0].alpha == pytest.approx(
        quality["fragen"]["ergebnis"]["krippendorff_alpha"]
    )


def _copied(tmp_path: Path, quality: dict[str, Any]) -> Path:
    folder = tmp_path / VALIDATION_PROJECT
    folder.mkdir()
    shutil.copy(REPO / "validierung" / VALIDATION_PROJECT / "stichprobe.json", folder)
    (folder / "guete.json").write_text(json.dumps(quality), encoding="utf-8")
    return tmp_path


def test_nur_fragen_mit_genuegendem_alpha_stehen_im_pruefsatz(tmp_path: Path) -> None:
    quality = _quality()
    quality["fragen"]["form"]["alpha_genuegt"] = False
    check = read_check(_settings(root=_copied(tmp_path, quality)))
    assert [a.question for a in check.agreements] == ["ergebnis"]


@pytest.mark.parametrize(
    ("key", "value"), [("codebuch_version", "2026-12-01.2"), ("einheiten", 151)]
)
def test_rule_check_gilt_nur_fuer_die_messung_aus_guete_json(
    tmp_path: Path, key: str, value: object
) -> None:
    root = _copied(tmp_path, _quality() | {key: value})
    with pytest.raises(SchemaError, match="RULE_CHECK"):
        read_check(_settings(root=root))
    assert RULE_CHECK.codebook_version == _quality()["codebuch_version"]
    assert RULE_CHECK.units == _quality()["einheiten"]


def test_rule_check_traegt_das_urteil_der_messung() -> None:
    """§ 5.1: A erfüllt das Kriterium (0,982, untere Grenze 0,928), B nicht (0,765)."""
    assert RULE_CHECK.level_a is LEVEL_A and RULE_CHECK.level_b is LEVEL_B
    assert LEVEL_A.met and not LEVEL_B.met
    assert LEVEL_A.interval[0] > RULE_CHECK.criterion > LEVEL_B.interval[1]
    assert RULE_CHECK.with_form / RULE_CHECK.decided == pytest.approx(LEVEL_A.coverage, abs=5e-4)


# --- Der Abschnitt je Profilfall ------------------------------------------------------------------
_PROGRESS_ROWS = [
    ("m1", "t1", "RAT", "mehrheitlich abgelehnt", dt.datetime(2022, 3, 1, 15)),
    ("m2", "t2", "RAT", "einstimmig beschlossen", dt.datetime(2022, 3, 1, 15)),
    ("m3", "t3", "BV6", "abweichend beschlossen", dt.datetime(2022, 3, 1, 15)),
    ("m3", "t4", "AWM", "Empfehlung mehrheitlich beschlossen", dt.datetime(2022, 2, 1, 15)),
]


def _tables(settings: Settings, windows: list[Window]) -> tuple[pl.DataFrame, pl.DataFrame]:
    from georep.analysis.outcomes import PROGRESS_SCHEMA

    progress = pl.DataFrame(
        [(p, f"b{t}", t, g, "-", s, "1", 1, r, None) for p, t, g, r, s in _PROGRESS_ROWS],
        schema=PROGRESS_SCHEMA,
        orient="row",
    )
    votes = votes_table(
        progress, BodyRules.from_settings(settings.bodies), VoteRules.from_settings(settings.votes)
    )
    corpus = pl.DataFrame({"id": ["m1", "m2"], "paper_type": ["Antrag SPD", "Antrag FDP"]})
    originators = pl.DataFrame(
        {"id": ["m1", "m2"], "urheber_art": ["Fraktion"] * 2, "parteien": [["SPD"], ["FDP"]]},
        schema={"id": pl.String, "urheber_art": pl.String, "parteien": pl.List(pl.String)},
    )
    tests = hypothesis_rows(
        HypothesisInputs(votes, corpus, originators),
        windows,
        settings.votes,
        party_labels(settings),
    )
    return body_summary(votes, "2020-2025"), tests


def _section(settings: Settings, windows: list[Window] | None, on: bool = True) -> str:
    bodies, tests = _tables(settings, windows or []) if on else (None, None)
    model = build_votes(settings, bodies, tests, read_check(settings))
    data = {
        "abstimmungen": model,
        "calculation_labels": {MAIN: "Haupttest", R2: "R2"},
        "urls": {"measurement": "m", "check": "c", "check_folder": "f", "commit": "k"},
    }
    return environment().get_template("pages/akteure/abstimmungen.html.j2").render(data=data)


MAJORITY = frozenset({"CDU", "GRUENE"})


def test_die_hauptperiode_zeigt_zaehlung_pruefsatz_und_haupttest() -> None:
    settings = _settings()
    html = _section(settings, [Window(MAIN, dt.date(2021, 1, 1), dt.date(2025, 9, 14), MAJORITY)])
    assert "<h2>Abstimmungen</h2>" in html  # gemessen: ohne „explorativ"
    assert 'id="abstimmungen-arten"' in html and 'id="abstimmungen-hypothesen"' in html
    assert _quality()["satz"] in html
    assert "<code>97ebb52</code>" in html and "am 24.11.2026" in html
    # zwei Anträge: H28.2 unter 30 Anträgen nicht entscheidbar, H28.1 und H28.3 ohne Ebene B
    assert html.count("<strong>nicht entscheidbar</strong>") == 3
    assert "zu wenige Anträge" in html
    assert "Nebenrechnungen von H28.2" in html
    assert "Bezirksvertretungen" in html and "Ausschüsse" in html


def test_ein_datensatz_ausserhalb_der_stichprobe_heisst_explorativ() -> None:
    html = _section(
        _settings("duesseldorf-2025"), [Window(R2, dt.date(2025, 12, 1), None, MAJORITY)]
    )
    assert "<h2>Abstimmungen (explorativ)</h2>" in html
    assert "<strong>Explorativ</strong>" in html
    assert "Nebenrechnung, entscheidet nicht" in html
    assert "hier steht nur die Nebenrechnung" in html
    assert "Nebenrechnungen von H28.2" not in html


def test_ohne_zeitraum_sagt_der_abschnitt_wo_die_pruefungen_rechnen() -> None:
    html = _section(_settings("duesseldorf-2014"), None)
    assert 'id="abstimmungen-arten"' in html
    assert 'id="abstimmungen-hypothesen"' not in html
    assert "keine dieser Prüfungen gerechnet" in html
    assert "keiner ihrer Zeiträume liegt in diesem Datensatz" in html
    assert "<code>abstimmungen_hypothesen</code>" not in html


def test_ohne_schritt_sagt_der_abschnitt_nur_was_fehlt() -> None:
    settings = _settings("moenchengladbach")
    assert not votes_enabled(settings)
    html = _section(settings, None, on=False)
    assert "<h2>Abstimmungen (explorativ)</h2>" in html
    assert (
        "der Wortschatz, mit dem die Sitzungsleitung hier Ergebnisse einträgt, ist nicht gemessen"
        in html
    )
    assert "<table" not in html and "abstimmungen-pruefung" not in html


def test_die_vorlage_beginnt_mit_if_data_und_nennt_keine_partei() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert text.startswith("{% if data.abstimmungen %}")
    names: set[str] = set()
    for profile in ("duesseldorf", "moenchengladbach"):
        settings = load_settings(profile=profile, cwd=NOWHERE)
        for party in (*settings.originators.parties, *settings.originators.groups):
            names |= {n for n in (party.key, party.label, party.short) if n}
    docs = " ".join(d for table in TABLES for d, _ in table.columns.values())
    docs += " ".join(table.description for table in TABLES)
    for source in (text, docs):
        assert sorted(n for n in names if re.search(rf"(?<!\w){re.escape(n)}(?!\w)", source)) == []


# --- Register und Eingaben ------------------------------------------------------------------------
def test_der_beitrag_steht_am_ende_mit_einem_gast_auf_akteure() -> None:
    assert CONTRIBUTIONS[-1].name == "28-abstimmungen"
    (section,) = SECTIONS
    assert (section.page, section.name) == ("akteure", SECTION)
    assert [t.name for t in TABLES] == [
        "abstimmungen",
        "abstimmungen_gremien",
        "abstimmungen_hypothesen",
    ]
    assert TABLES[0].csv is None  # je Punkt nur Parquet (Rückstand 35)


@pytest.mark.parametrize(
    ("profile", "with_tables"),
    [("duesseldorf", True), ("duesseldorf-2014", True), ("moenchengladbach", False)],
)
def test_der_gast_liest_die_tabellen_nur_wo_der_schritt_gebaut_wird(
    profile: str, with_tables: bool
) -> None:
    settings = _settings(profile)
    layout = Layout(NOWHERE / "data", NOWHERE / "cache", NOWHERE)
    inputs = votes_section_inputs(layout, settings)
    files = vote_files(layout)
    assert (files.bodies in inputs and files.hypotheses in inputs) is with_tables
    assert inputs[-2:] == (
        settings.validation.root / VALIDATION_PROJECT / "guete.json",
        settings.validation.root / VALIDATION_PROJECT / "stichprobe.json",
    )
    assert files.votes not in inputs  # die Tabelle je Punkt liest der Abschnitt nicht


def test_die_links_nach_aussen_sind_messdokument_pruefung_und_commit() -> None:
    links = votes_section_links(Layout(NOWHERE, NOWHERE, NOWHERE), _settings())
    assert {link.rsplit("/", 1)[-1] for link in links} == {
        "28-abstimmungen.md",
        "README.md",
        "97ebb52",
    }


# --- Die echte Seite der Mini-Fixture -------------------------------------------------------------
def test_der_gast_steht_auf_akteure_html_mit_anker_und_verzeichnis(mini_run: Layout) -> None:
    page = (mini_run.site / "akteure.html").read_text(encoding="utf-8")
    assert page.count('<section id="abstimmungen">') == 1
    assert page.count('<li><a href="#abstimmungen">Abstimmungen</a></li>') == 1
    assert 'Davon handelt der Abschnitt <a href="#abstimmungen">Abstimmungen</a> unten.' in page
    assert page.index('<section id="erklaerungen">') < page.index('<section id="abstimmungen">')
    assert len(page.encode("utf-8")) < PAGE_BUDGET
    start = page.index('<section id="abstimmungen">')
    section = page[start : page.index("</section>", start)]
    assert len(section.encode("utf-8")) < 15_000  # Plan § 7 nach § 5.1: rund 10 KB


def test_die_downloads_und_ihre_spalten(mini_run: Layout, default_settings: Settings) -> None:
    details = mini_run.site_details.read_text(encoding="utf-8")
    columns = (mini_run.site / "spalten.html").read_text(encoding="utf-8")
    for name in ("abstimmungen_gremien", "abstimmungen_hypothesen"):
        assert (mini_run.site_data / f"{name}.parquet").is_file()
        assert (mini_run.site_data / f"{name}.csv").is_file()
        assert f'<section id="{name}">' in columns
    assert (mini_run.site_data / "abstimmungen.parquet").is_file()
    assert not (mini_run.site_data / "abstimmungen.csv").is_file()
    assert '<section id="abstimmungen">' in columns
    assert 'href="spalten.html#abstimmungen"' in details
    settings = default_settings.model_copy(
        update={
            "validation": default_settings.validation.model_copy(
                update={"root": REPO / "validierung"}
            )
        }
    )
    data = votes_section_data(mini_run, settings)
    assert data["abstimmungen"].on  # type: ignore[attr-defined]
