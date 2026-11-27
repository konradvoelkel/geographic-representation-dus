"""Die Unterseite ``vorgaenge.html`` und der Vorgang im Dialog (Vorhaben 14, Stufe 3).

Drei Gruppen, wie bei ``akteure.html`` (Punkt 88). Die Bausteine an einer kleinen, erfundenen
Stadt: Antwortzeiten, Gremien ab 30 Anfragen mit dem Hinweis auf die Sitzung, je Fraktion nur
beobachtet gegen erwartet, Kandidaten nur in Gremien mit Praxis, Vorgänge und Typen, die Einträge
im Dialog. Der Prüfsatz kommt aus den drei ``guete.json``: eine geänderte Datei ändert die Seite,
und ein Datensatz außerhalb der Prüfstichprobe heißt überall explorativ. Die echte Seite der
Mini-Fixture: im Register, mit Linkblock, den drei Downloads mit Spaltendoku, dem Haken auf der
Hauptseite, unter dem Budget, ohne Partei im veröffentlichten Text.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment

from georep.analysis.procedures import (
    ANSWER_SCHEMA,
    ATTACHMENT_SCHEMA,
    EDGE_SCHEMA,
    FOREST_SCHEMA,
)
from georep.enrich.procedures import DIALOG, PAGE, TABLES, procedure_files
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.prep.references import EDGE_TYPES
from georep.report.pages import PageSection, page_frame, render_page
from georep.report.procedures import (
    DIALOG_LABELS,
    MAX_RELATED,
    MIN_QUESTIONS,
    RULE_PROJECT,
    SESSION_GUEST,
    TYPE_LABELS,
    answer_times_of,
    build_procedures,
    dialog_entries,
    fraction_rows,
    page_data,
    procedure_summary,
    procedures_links,
    read_check,
    short_title,
)
from georep.report.render import environment
from georep.report.tables import published
from georep.settings import Settings, load_settings
from tests.conftest import REPO, mg_settings

NOW = dt.datetime(2026, 11, 27, 12, 0, tzinfo=dt.UTC)
PAGE_BUDGET = 500_000  # docs/plan-zeigen-2026-11.md, § 6
DIALOG_BUDGET = 100_000  # Messdokument § 7: vorgaenge.json unter 100 KB
SECTIONS = ("ueberblick", "antworten", "fraktionen", "kandidaten", "vorgaenge")
D = dt.date
NOWHERE = Path("/nonexistent")


def _check_settings(settings: Settings, root: Path = REPO / "validierung") -> Settings:
    return settings.model_copy(
        update={"validation": settings.validation.model_copy(update={"root": root})}
    )


# --- Eine kleine Stadt ------------------------------------------------------------------------------
def _id(n: int) -> str:
    return f"https://ris.example/papers/{n:05d}"


def _question(
    n: int, body: str, *, answered: bool, days: int | None, age: int, fractions: Sequence[str]
) -> dict[str, Any]:
    return {
        "id": _id(n),
        "quelle": "anlage" if answered else "keine",
        "antwort_datum": D(2021, 3, 1) if answered and days is not None else None,
        "tage": days if answered else None,
        "antwort_id": None,
        "alter_am_abruf": age,
        "gremium": body,
        "praxis_gremium": 0.0,  # unten je Gremium nachgerechnet
        "fraktionen": list(fractions),
    }


def _city(fractions: tuple[str, str] = ("CDU", "SPD")) -> dict[str, pl.DataFrame]:
    """40 Anfragen in einer Bezirksvertretung (36 mit Antwort), 35 im Rat (keine), 5 anderswo."""
    rows: list[dict[str, Any]] = []
    for n in range(40):
        rows.append(
            _question(
                n,
                "BV1",
                answered=n < 36,
                days=10 + n,
                age=400 if n >= 36 else 50,
                fractions=[fractions[0]],
            )
        )
    for n in range(40, 75):
        rows.append(
            _question(n, "RAT", answered=False, days=None, age=300, fractions=[fractions[1]])
        )
    for n in range(75, 80):
        rows.append(_question(n, "XA", answered=True, days=5, age=60, fractions=[]))
    frame = pl.DataFrame(rows)
    practice = frame.group_by("gremium").agg((pl.col("quelle") != "keine").mean().alias("p"))
    frame = frame.join(practice, on="gremium").with_columns(pl.col("p").alias("praxis_gremium"))
    answers = frame.select(list(ANSWER_SCHEMA)).cast(pl.Schema(ANSWER_SCHEMA)).sort("id")
    ids = [_id(n) for n in range(90)]
    corpus = pl.DataFrame(
        {
            "id": ids,
            "reference": [f"X/{n:03d}/2021" for n in range(90)],
            "date": [D(2021, 1, 1) + dt.timedelta(days=n) for n in range(90)],
            "download_url": [f"http://ris.example/downloadfiles/{n:05d}.pdf" for n in range(90)],
        }
    )
    questions = frame.select(
        "id", pl.lit("Fraktion").alias("urheber_art"), pl.col("fraktionen").cast(pl.List(pl.String))
    )
    attachments = pl.DataFrame(
        [
            (_id(n), D(2026, 11, 1), [{"name": "Antwort der Verwaltung", "datum": D(2021, 3, 1)}])
            for n in range(36)
        ],
        schema=ATTACHMENT_SCHEMA,
        orient="row",
    )
    bodies = pl.DataFrame(
        {
            "id": ids,
            "gremium": ["BV1"] * 40 + ["RAT"] * 35 + ["XA"] * 15,
            "gremium_art": ["bezirksvertretung"] * 40 + ["rat"] * 35 + ["ausschuss"] * 15,
            "stadtbezirk": [1] * 40 + [None] * 50,
        }
    )
    # Vorgänge: ein Paar (80 <- 81, Umsetzung), ein Dreier (82 <- 83 <- 84), der Rest allein
    edges = pl.DataFrame(
        [
            (_id(81), _id(80), "umsetzung", ["titel"], True, "titel", 3, ""),
            (_id(83), _id(82), "aenderung", ["titel"], True, "titel", 1, ""),
            (_id(84), _id(83), "nachtrag", ["nummer"], True, "nummer", 1, ""),
            (_id(85), _id(80), "bezug", ["text"], False, "text", 9, ""),
        ],
        schema=EDGE_SCHEMA,
        orient="row",
    )
    root = {81: 80, 83: 82, 84: 82}
    forest = pl.DataFrame(
        [
            (
                _id(n),
                _id(root.get(n, n)),
                {80: "wurzel", 82: "wurzel", 81: "umsetzung", 83: "aenderung", 84: "nachtrag"}.get(
                    n, "ohne"
                ),
                {81: 1, 83: 1, 84: 2}.get(n, 0),
                {80: 2, 81: 2, 82: 3, 83: 3, 84: 3}.get(n, 1),
            )
            for n in range(90)
        ],
        schema=FOREST_SCHEMA,
        orient="row",
    )
    return {
        "corpus": corpus,
        "forest": forest,
        "edges": edges,
        "answers": answers,
        "questions": questions,
        "attachments": attachments,
        "bodies": bodies,
    }


def _model(settings: Settings, city: dict[str, pl.DataFrame] | None = None) -> Any:
    c = _city() if city is None else city
    return build_procedures(
        c["corpus"],
        c["forest"],
        c["edges"],
        c["answers"],
        c["questions"],
        c["attachments"],
        c["bodies"],
        settings,
        read_check(settings),
        with_fractions=True,
    )


def _render(
    settings: Settings,
    city: dict[str, pl.DataFrame] | None = None,
    *,
    sections: Sequence[tuple[PageSection, dict[str, object]]] = (),
    env: Environment | None = None,
) -> str:
    model = _model(settings, city)
    urls = frozenset(f"https://ris.example/downloadfiles/{n:05d}.pdf" for n in range(90))
    allowed = urls | procedures_links(Layout(NOWHERE, NOWHERE, NOWHERE), settings)
    return render_page(
        page_frame(settings, now=NOW, commit=None),
        PAGE,
        page_data(model, settings),
        allowed,
        env=env,
        sections=sections,
    )


def _section(page: str, name: str) -> str:
    part = page[page.index(f'<section id="{name}">') :]
    return part[: part.index("</section>")]


# --- Bausteine ------------------------------------------------------------------------------------
def test_jeder_typ_hat_ein_wort_und_zwei_im_dialog() -> None:
    """Ein neuer Kantentyp in ``prep.references.EDGE_TYPES`` stünde sonst als Schlüssel da."""
    assert set(TYPE_LABELS) == set(EDGE_TYPES)
    assert {t for t, _ in DIALOG_LABELS} == set(EDGE_TYPES)
    assert len(DIALOG_LABELS) == 2 * len(EDGE_TYPES)


def test_antwortzeiten_nur_ueber_die_datierten() -> None:
    times = answer_times_of(pl.Series([10, 20, None, 30, 40], dtype=pl.Int32))
    assert (times.dated, times.median, times.q1, times.q3) == (4, 25.0, 20.0, 30.0)
    assert answer_times_of(pl.Series([None], dtype=pl.Int32)).median is None


def test_gremien_ab_dreissig_anfragen_und_der_hinweis_auf_die_sitzung(
    default_settings: Settings,
) -> None:
    model = _model(_check_settings(default_settings))
    answers = model.answers
    assert answers is not None
    rows = {b.code: b for b in answers.bodies}
    assert set(rows) == {"BV1", "RAT"} and (answers.small_bodies, answers.small_questions) == (1, 5)
    assert rows["BV1"].answered == 36 and not rows["BV1"].in_session
    assert rows["RAT"].answered == 0 and rows["RAT"].in_session
    assert answers.names == 1  # „Antwort der Verwaltung"
    page = _render(_check_settings(default_settings))
    section = _section(page, "antworten")
    assert "Ein fehlender Anhang ist keine fehlende Antwort" in section
    assert "Niederschrift" in section and "†" in section


def test_je_fraktion_nur_beobachtet_gegen_erwartet(default_settings: Settings) -> None:
    """Frage 14: keine rohe Quote je Fraktion; unter zehn erwarteten Antworten kein Verhältnis."""
    city = _city()
    joined = city["answers"].join(city["questions"], on="id")
    rows = {r.key: r for r in fraction_rows(joined, {})}
    assert rows["CDU"].questions == MIN_QUESTIONS + 10 and rows["CDU"].ratio == pytest.approx(1.0)
    assert rows["SPD"].ratio is None  # fragt nur im Rat, erwartet 0
    section = _section(_render(_check_settings(default_settings)), "fraktionen")
    assert "(explorativ)" in section and "%" not in section.split("<table")[1]
    assert '<th scope="col" class="num" data-sort="num">beob./erw.</th>' in section
    assert '<th scope="col" class="num">Median Tage</th>' in section  # roh, sortiert nicht


def test_kandidaten_nur_in_gremien_mit_praxis_und_alter_als_p90(default_settings: Settings) -> None:
    model = _model(_check_settings(default_settings))
    assert [k.reference for k in model.candidates] == [
        "X/036/2021",
        "X/037/2021",
        "X/038/2021",
        "X/039/2021",
    ]
    assert model.candidates[0].url == "https://ris.example/downloadfiles/00036.pdf"
    # der Rat antwortet nie als Anlage: keine Kandidaten dort, obwohl alt und ohne Antwort
    section = _section(_render(_check_settings(default_settings)), "kandidaten")
    assert "Kandidaten" in section and "X/040/2021" not in section


def test_vorgaenge_zaehlen_wurzeln_groessen_und_starke_kanten() -> None:
    city = _city()
    summary = procedure_summary(city["forest"], city["edges"], city["corpus"]["id"].to_list())
    assert (summary.procedures, summary.members, summary.sizes) == (2, 5, ((2, 1), (3, 1)))
    assert (summary.strong, summary.weak, summary.edges) == (3, 1, 4)
    # gleich viele: in der Folge von EDGE_TYPES
    assert [t for t, _, _ in summary.by_type] == ["umsetzung", "aenderung", "nachtrag"]
    assert [s for s, _, _ in summary.by_source] == ["titel", "nummer"]


def test_der_dialog_zeigt_starke_nachbarn_in_beiden_richtungen() -> None:
    """Keine Textverweise (Messdokument § 5.1), ``bezug`` höchstens fünf je Dokument (Frage 9.7)."""
    city = _city()
    dates = dict(zip(city["corpus"]["id"].to_list(), city["corpus"]["date"].to_list(), strict=True))
    labels, rows = dialog_entries(city["edges"], dates)
    words = {doc: [(labels[k], t) for k, t in entries] for doc, entries in rows.items()}
    assert words[_id(81)] == [("Umsetzung von", _id(80))]
    assert words[_id(80)] == [("umgesetzt in", _id(81))]  # die Textkante von 85 fehlt
    assert _id(85) not in words
    many = pl.DataFrame(
        [(_id(n), _id(0), "bezug", ["titel"], True, "titel", 1, "") for n in range(1, 9)],
        schema=EDGE_SCHEMA,
        orient="row",
    )
    labels, rows = dialog_entries(many, dates)
    assert len(rows[_id(0)]) == MAX_RELATED + 1
    assert labels[rows[_id(0)][-1][0]] == "und 3 weitere Nennungen" and rows[_id(0)][-1][1] is None


def test_ein_titel_im_dialog_ist_kurz() -> None:
    assert short_title("  a   b ") == "a b"
    assert len(short_title("x" * 300)) == 100 and short_title("x" * 300).endswith("…")


# --- Prüfung ----------------------------------------------------------------------------------------
def _quality(project: str) -> dict[str, Any]:
    path = REPO / "validierung" / project / "guete.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize(
    ("profile", "measured"),
    [
        ("duesseldorf", True),
        ("duesseldorf-2014", False),
        ("duesseldorf-2025", False),
        ("duesseldorf-vergleich", True),  # rechnet im Ordner der Hauptperiode
        ("moenchengladbach", False),
    ],
)
def test_der_pruefsatz_kommt_aus_guete_json(profile: str, measured: bool) -> None:
    """Gemessen ist die Rückfallregel nur an der Hauptperiode (Messdokument § 4.3)."""
    check = read_check(_check_settings(load_settings(profile=profile, cwd=NOWHERE)))
    rule = _quality(RULE_PROJECT)
    hits = rule["fragen"]["selbe_sache"]["treffer"]
    assert check.rule.sentence == rule["satz"]
    assert (check.rule.hits, check.rule.judged) == (hits["stichprobe"]["treffer"], 50)
    assert check.rule.population == hits["grundgesamtheit"]["n"] == 1710
    assert not check.rule.same_model and check.first.same_model  # Punkt 87: B ist Sonnet
    assert (check.first.hits, check.first.judged) == (139, 150)
    assert (check.second.hits, check.second.judged) == (85, 100)
    assert check.measured is measured


def test_eine_geaenderte_guete_json_aendert_die_seite(
    tmp_path: Path, default_settings: Settings
) -> None:
    for project in ("14-vorgaenge-f4", "14-vorgaenge-2-f4", RULE_PROJECT):
        shutil.copytree(REPO / "validierung" / project, tmp_path / project)
    quality = _quality(RULE_PROJECT) | {"satz": "geprüft von niemandem, nur zum Test"}
    (tmp_path / RULE_PROJECT / "guete.json").write_text(json.dumps(quality), encoding="utf-8")
    page = _render(_check_settings(default_settings, tmp_path))
    assert "geprüft von niemandem, nur zum Test" in _section(page, "ueberblick")


def test_ein_nicht_gemessener_datensatz_ist_ueberall_explorativ() -> None:
    page = _render(_check_settings(mg_settings()), _city(("F1", "F2")))
    for name in SECTIONS[1:]:
        assert "(explorativ)" in _section(page, name).split("</h2>")[0], name
    box = _section(page, "ueberblick")
    assert "Explorativ" in box and "Wahlperiode 2020 bis 2025" in box and "duesseldorf" not in box


def test_jeder_abschnitt_steht_einmal_und_die_hauptperiode_ist_gemessen(
    default_settings: Settings,
) -> None:
    page = _render(_check_settings(default_settings))
    for name in SECTIONS:
        assert page.count(f'<section id="{name}">') == 1
    assert "(explorativ)" in _section(page, "fraktionen")  # Frage 14, in jedem Datensatz
    assert "(explorativ)" not in _section(page, "vorgaenge")


def test_der_hinweis_auf_die_niederschrift_weicht_dem_gast(default_settings: Settings) -> None:
    """Vorhaben 26 hängt ``in-der-sitzung`` an (Punkt 86); dann verlinkt die Seite dorthin."""
    settings = _check_settings(default_settings)
    without = _render(settings)
    assert f'href="#{SESSION_GUEST}"' not in without and "Niederschrift, die dieser" in without
    env = environment()
    assert env.loader is not None
    env.loader = ChoiceLoader(
        [
            DictLoader(
                {f"pages/vorgaenge/{SESSION_GUEST}.html.j2": "{% if data.n %}<p>n</p>{% endif %}"}
            ),
            env.loader,
        ]
    )
    guest = PageSection(
        "vorgaenge", SESSION_GUEST, 10, inputs=lambda layout, s: (), data=lambda layout, s: {"n": 1}
    )
    with_guest = _render(settings, sections=((guest, {"n": 1}),), env=env)
    assert (
        f'href="#{SESSION_GUEST}"' in with_guest and "Niederschrift, die dieser" not in with_guest
    )
    assert "†" not in _section(with_guest, "antworten")


# --- Kein Parteiname, kein Stadtwort ----------------------------------------------------------------
def _party_names() -> set[str]:
    names: set[str] = set()
    for profile in ("duesseldorf", "moenchengladbach"):
        settings = load_settings(profile=profile, cwd=NOWHERE)
        for party in (*settings.originators.parties, *settings.originators.groups):
            names |= {n for n in (party.key, party.label, party.short) if n}
        names |= {f.key for f in settings.functions.fractions}
    return names


def _named(text: str) -> list[str]:
    return sorted(
        n for n in _party_names() if re.search(rf"(?<![\w+]){re.escape(n)}(?![\w+])", text)
    )


def test_kein_parteiname_in_vorlage_seite_und_spaltendoku() -> None:
    """Namen kommen nur aus den Daten: mit neutralen Fraktionen bleibt keiner übrig."""
    folder = REPO / "src" / "georep" / "report" / "templates" / "pages"
    assert _named("".join(p.read_text(encoding="utf-8") for p in folder.rglob("vorgaenge*"))) == []
    page = _render(_check_settings(mg_settings()), _city(("F1", "F2")))
    assert _named(page) == []
    docs = " ".join(doc[0] for table in TABLES for doc in table.columns.values())
    assert _named(docs + " ".join(t.description for t in TABLES) + DIALOG.description) == []


# --- Register, Linkblock, Downloads, Haken, Größe auf der Mini-Fixture ------------------------------
def test_die_seite_steht_im_register_und_auf_der_hauptseite(mini_run: Layout) -> None:
    page = (mini_run.site / "vorgaenge.html").read_text(encoding="utf-8")
    index = mini_run.site_index.read_text(encoding="utf-8")
    weitere = index[index.index('<section id="weitere">') :]
    assert '<a href="vorgaenge.html">Vorgänge: Anfragen, Antworten, Verbindungen</a>' in weitere
    assert len(page.encode("utf-8")) < PAGE_BUDGET
    for name in SECTIONS:
        assert page.count(f'<section id="{name}">') == 1


def test_die_drei_tabellen_stehen_als_download_mit_spaltendoku(
    mini_run: Layout, default_settings: Settings
) -> None:
    """``verweise.parquet`` nicht: seine Stellen hängen vom Rechner ab (todo 12 (e))."""
    names = {t.name for t in published(mini_run, default_settings)}
    assert {"vorgang_kanten", "dokumente_vorgang", "antwortzeiten"} <= names
    assert "verweise" not in names
    schema = json.loads((mini_run.site_data / "schema.json").read_text(encoding="utf-8"))
    for table in TABLES:
        assert (mini_run.site_data / f"{table.name}.csv").is_file()
        assert (mini_run.site_data / table.path(mini_run).name).is_file()
        columns = list(pl.read_parquet_schema(table.path(mini_run)))
        assert columns == list(table.columns)
        described = {c["column"]: c["description"] for c in schema["tables"][table.name]}
        assert described == {name: doc[0] for name, doc in table.columns.items()}


def test_der_dialog_der_hauptseite_laedt_die_vorgaenge(mini_run: Layout) -> None:
    index = mini_run.site_index.read_text(encoding="utf-8")
    assert '<dialog id="docs" aria-labelledby="docs-title" data-extras="vorgaenge">' in index
    listed = json.loads((mini_run.site_data / "dokumente.json").read_text(encoding="utf-8"))
    hook = mini_run.site_data / "vorgaenge.json"
    payload = json.loads(hook.read_text(encoding="utf-8"))
    assert payload["title"] == "Vorgang" and payload["base"] == listed["base"]
    assert all(0 <= int(k) < len(listed["documents"]) for k in payload["rows"])
    assert "nicht von Menschen" in payload["note"]
    assert hook.stat().st_size < DIALOG_BUDGET
    assert listed["fields"] == ["link", "datum", "drucksache", "titel", "art", "urheber"]
    assert '<a href="data/vorgaenge.json">vorgaenge.json</a>' in index


def test_der_bericht_liest_tabellen_und_dialog_mit(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    report = next(s for s in build_steps(default_settings, layout) if s.name == "report")
    files = procedure_files(layout)
    assert {files.edges, files.documents, files.answers} <= set(report.inputs)
    page = next(s for s in build_steps(default_settings, layout) if s.name == "page_vorgaenge")
    assert {files.edges, files.documents, files.answers, files.attachments} <= set(page.inputs)


def test_die_seite_darf_die_pdf_dateien_ihres_korpus_verlinken(
    mini_run: Layout, default_settings: Settings
) -> None:
    allowed = procedures_links(mini_run, default_settings)
    urls = pl.read_parquet(mini_run.corpus, columns=["download_url"]).get_column("download_url")
    first = next(u for u in urls.to_list() if u)
    assert first.replace("http://", "https://", 1) in allowed
    assert any(link.endswith("/docs/plans/14-vorgaenge.md") for link in allowed)
    assert any(link.endswith(f"/{RULE_PROJECT}/README.md") for link in allowed)


# --- Supervisor 2026-11-27: die CSV je Dokument nur mit Zeilen, die einen Vorgang tragen ----------
def test_die_csv_des_vorgangs_traegt_nur_dokumente_in_einem_vorgang(mini_run: Layout) -> None:
    """Wie das Vokabular von 17 (Punkt 90) über den ``CsvPlan`` aus Punkt 89: ein Dokument ohne
    Vorgang (``rolle = ohne``, in der Hauptperiode 84 %) trägt in der CSV nichts. Das Parquet bleibt
    vollständig, eine Zeile je Korpus-ID; Downloadzeile und Spaltendoku sagen es."""
    from georep.enrich.procedures import procedure_csv_rows

    table = next(t for t in TABLES if t.name == "dokumente_vorgang")
    assert table.csv is not None and table.csv.rows is procedure_csv_rows
    rows = procedure_csv_rows(_city()["forest"])
    assert rows.height == 5 and (rows.get_column("groesse") > 1).all()
    parquet = pl.read_parquet(mini_run.site_data / "dokumente_vorgang.parquet")
    assert parquet.height == pl.read_parquet(mini_run.corpus, columns=["id"]).height
    csv = pl.read_csv(mini_run.site_data / "dokumente_vorgang.csv", schema=parquet.schema)
    assert csv.equals(parquet.filter(pl.col("groesse") > 1))
    index = mini_run.site_index.read_text(encoding="utf-8")
    assert f"als CSV ({table.csv.note})" in index and "Vorgang" in table.csv.note
    assert "die CSV trägt nur" in table.columns["groesse"][0]
    # die beiden anderen CSV bleiben vollständig: eine schwache Kante und eine Anfrage ohne
    # gefundene Antwort sind selbst eine Aussage
    for name in ("vorgang_kanten", "antwortzeiten"):
        other = next(t for t in TABLES if t.name == name)
        assert other.csv is not None and other.csv.note == ""
