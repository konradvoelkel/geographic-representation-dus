"""Die Beschlusslage auf ``vorgaenge.html``, im Dokumentdialog und als Download (Vorhaben 26, Stufe 3).

Messdokument ``docs/plans/26-beschluesse.md``, § 7 und § 10, mit Rückfall 1 (§ 5). Vier Gruppen. Der
Prüfsatz kommt aus ``validierung/26-beschluesse/guete.json`` und, was die Datei nicht trägt, aus
``OUTCOMES_CHECK``; gemessen sind die drei Düsseldorfer Perioden der Stichprobe. Die drei Gäste an
erfundenen Tabellen: die Zählung je Gremium ohne die Praxiszellen, der Erfolg je Fraktion nach
Namen und ohne rohe Quote, die Antworten in der Sitzung nach dem Wortlaut. Der Haken: nur Anträge,
je einer ein Wort. Die echte Seite der Mini-Fixture und die Profile: drei Gäste mit Anker und
Verzeichnis, wo der Schritt läuft, sonst nur der Satz, was fehlt; die Downloads und ihre Spalten.
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

from georep.analysis.outcomes import OUTCOME_SCHEMA, PROGRESS_SCHEMA
from georep.enrich.outcomes import (
    CONTRIBUTION,
    DIALOG,
    SECTIONS,
    TABLES,
    outcome_files,
    outcomes_built,
)
from georep.enrich.procedures import TABLES as PROCEDURE_TABLES
from georep.errors import SchemaError
from georep.layout import Layout
from georep.report.dialog import dialog_names
from georep.report.outcomes import (
    CLASS_WORDS,
    DIALOG_NAME,
    MIN_MOTIONS,
    MIN_SESSION,
    MIN_SUCCESS,
    OUTCOMES_CHECK,
    PRACTICE_WORD,
    SECTION_OUTCOMES,
    SECTION_SESSION,
    SECTION_SUCCESS,
    VALIDATION_PROJECT,
    build_outcomes,
    build_session,
    build_success,
    check_sentence,
    code_names,
    counts_of,
    majority_fractions,
    outcome_label,
    read_check,
    sample_profiles,
)
from georep.report.procedures import SESSION_GUEST
from georep.report.render import environment
from georep.report.tables import published
from georep.settings import Settings, load_settings
from tests.conftest import REPO

NOWHERE = Path("/nonexistent")
TEMPLATES = REPO / "src" / "georep" / "report" / "templates" / "pages" / "vorgaenge"
DIALOG_BUDGET = 300_000  # Messdokument § 7, Plan § 6


def _settings(profile: str = "duesseldorf", root: Path = REPO / "validierung") -> Settings:
    settings = load_settings(profile=profile, cwd=NOWHERE)
    return settings.model_copy(
        update={"validation": settings.validation.model_copy(update={"root": root})}
    )


def _quality() -> dict[str, Any]:
    path = REPO / "validierung" / VALIDATION_PROJECT / "guete.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _copied(tmp_path: Path, quality: dict[str, Any]) -> Path:
    folder = tmp_path / VALIDATION_PROJECT
    folder.mkdir()
    shutil.copy(REPO / "validierung" / VALIDATION_PROJECT / "stichprobe.json", folder)
    (folder / "guete.json").write_text(json.dumps(quality), encoding="utf-8")
    return tmp_path


# --- Der Prüfsatz ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("profile", "measured"),
    [
        ("duesseldorf", True),
        ("duesseldorf-vergleich", True),  # rechnet im Ordner der Hauptperiode
        ("duesseldorf-2014", True),  # die Stichprobe zieht aus allen drei Perioden
        ("duesseldorf-2025", True),
        ("moenchengladbach", False),
    ],
)
def test_der_pruefsatz_kommt_aus_guete_json(profile: str, measured: bool) -> None:
    check = read_check(_settings(profile))
    quality = _quality()
    assert check.sentence == quality["satz"] and check.same_model
    assert check.measured is measured
    assert (check.agreed, check.paired) == (150, 150) and check.alpha == pytest.approx(1.0)
    sentence = check_sentence(check)
    assert quality["satz"] in sentence and "Niederschrift" in sentence
    assert "150 von 150 Anträgen" in sentence and "0,975–1,000" in sentence
    assert "Nur 17" not in sentence and "nur 17 davon" in sentence
    assert ("explorativ" in sentence) is not measured


def test_die_stichprobe_nennt_ihre_drei_perioden() -> None:
    sample = json.loads(
        (REPO / "validierung" / VALIDATION_PROJECT / "stichprobe.json").read_text(encoding="utf-8")
    )
    assert sample_profiles(sample) == ("duesseldorf-2014", "duesseldorf", "duesseldorf-2025")
    assert sample_profiles({"profil": "a, b"}) == ("a", "b")


def test_ohne_genuegendes_alpha_steht_keine_zahl(tmp_path: Path) -> None:
    quality = _quality()
    quality["fragen"]["ergebnis"]["alpha_genuegt"] = False
    check = read_check(_settings(root=_copied(tmp_path, quality)))
    sentence = check_sentence(check)
    assert check.agreed is None and "zu wenig überein" in sentence
    assert "150 von 150" not in sentence and "Niederschrift" in sentence


@pytest.mark.parametrize(("key", "value"), [("codebuch_version", "2"), ("einheiten", 151)])
def test_outcomes_check_gilt_nur_fuer_die_messung_aus_guete_json(
    tmp_path: Path, key: str, value: object
) -> None:
    with pytest.raises(SchemaError, match="OUTCOMES_CHECK"):
        read_check(_settings(root=_copied(tmp_path, _quality() | {key: value})))
    assert (OUTCOMES_CHECK.codebook_version, OUTCOMES_CHECK.units) == ("1", 150)


def test_die_kurze_fassung_passt_in_eine_downloadzeile() -> None:
    sentence = check_sentence(read_check(_settings()), short=True)
    assert len(sentence.encode("utf-8")) < 800 and "Niederschrift" in sentence
    assert "gewichtet" not in sentence and "150 von 150" in sentence


# --- Abschnitt 1 an einer erfundenen Beschlusslage ------------------------------------------------
Row = tuple[str, str, str, str | None, int, int | None, bool | None]


def _outcomes(rows: list[Row]) -> pl.DataFrame:
    """(id, rolle, klasse, gremium der Entscheidung, Beratungen, Tage, eintrag_tragfaehig)."""
    base = {name: [] for name in OUTCOME_SCHEMA}  # type: dict[str, list[object]]
    for doc, role, klasse, body, consultations, days, carries in rows:
        base["id"].append(doc)
        base["dokument_rolle"].append(role)
        base["klasse"].append(klasse)
        base["grob"].append(None)
        base["result"].append(None)
        base["entscheidung_top"].append(None if klasse == "ohne_ergebnis" else f"t-{doc}")
        base["entscheidung_gremium"].append(body)
        base["entscheidung_datum"].append(
            None if klasse == "ohne_ergebnis" else dt.date(2015, 3, 1)
        )
        base["tage"].append(days)
        base["beratungen"].append(consultations)
        base["pruefauftrag_beantragt"].append(None)
        base["folgevorlage"].append(None)
        base["eintrag_tragfaehig"].append(carries)
    return pl.DataFrame(base, schema=OUTCOME_SCHEMA)


def _bodies(ids: list[str], code: str = "BV1") -> pl.DataFrame:
    district = code.startswith("BV")
    return pl.DataFrame(
        {
            "id": ids,
            "gremium": [code] * len(ids),
            "gremium_art": ["bezirksvertretung" if district else "rat"] * len(ids),
            "stadtbezirk": [int(code[2:]) if district else None] * len(ids),
        },
        schema={
            "id": pl.String,
            "gremium": pl.String,
            "gremium_art": pl.String,
            "stadtbezirk": pl.Int64,
        },
    )


def _progress(rows: list[tuple[str, str | None, str, dt.datetime]]) -> pl.DataFrame:
    """(id, top, gremium, sitzung)."""
    return pl.DataFrame(
        [(d, f"b-{d}", t, g, "-", s, "1", 1, None, None) for d, t, g, s in rows],
        schema=PROGRESS_SCHEMA,
        orient="row",
    )


def test_die_praxiszellen_zaehlen_in_keinem_anteil() -> None:
    frame = _outcomes(
        [
            ("a", "antrag", "beschlossen", "BV1", 1, 10, True),
            ("b", "antrag", "geaendert", "BV1", 2, 40, True),
            ("c", "antrag", "abgelehnt", "BV1", 1, 5, True),
            ("d", "antrag", "erledigt", "BV1", 1, 7, False),  # Praxiszelle
            ("e", "antrag", "ohne_ergebnis", None, 1, None, None),
        ]
    )
    counts = counts_of(frame)
    assert (counts.motions, counts.practice, counts.counted) == (5, 1, 4)
    assert (counts.accepted, counts.changed, counts.done, counts.missing) == (2, 1, 0, 1)
    assert counts.share(counts.accepted) == 0.5


def test_beschlusslage_je_gremium_mit_der_groessten_sitzung_ohne_eintrag() -> None:
    settings = _settings()
    n = MIN_MOTIONS + MIN_SESSION
    ids = [f"m{i:03d}" for i in range(n)]
    rows: list[Row] = [
        (i, "antrag", "ohne_ergebnis", None, 1, None, None) for i in ids[:MIN_SESSION]
    ]
    rows += [(i, "antrag", "beschlossen", "RAT", 1, 12, True) for i in ids[MIN_SESSION:]]
    rows += [("v1", "vorlage", "beschlossen", "RAT", 1, 3, None)]  # keine Rolle Antrag
    meeting = dt.datetime(2021, 2, 5, 14)
    progress = _progress([(i, f"t-{i}", "RAT", meeting) for i in ids])
    model = build_outcomes(
        _outcomes(rows), progress, _bodies([*ids, "v1"], "RAT"), settings, read_check(settings)
    )
    assert model.on and model.total is not None and model.total.motions == n
    (row,) = model.rows
    assert row.name == "Rat" and row.counts.missing == MIN_SESSION
    assert model.session is not None
    assert (model.session.body, model.session.day, model.session.motions) == (
        "Rat",
        dt.date(2021, 2, 5),
        MIN_SESSION,
    )
    assert model.single.median == 12 and model.several.n == 0
    html = _render(SECTION_OUTCOMES, {"beschlusslage": model, "check_sentence": "Satz."})
    assert "<h2>Beschlusslage je Gremium</h2>" in html
    assert f"bei {MIN_SESSION} davon in einer einzigen Sitzung (Rat, 05.02.2021)" in html
    assert "Prüfauftrag" not in html.replace("nur eine Prüfung verlangt", "")


def test_ein_gremium_unter_der_grenze_steht_nur_in_der_summe() -> None:
    settings = _settings()
    ids = [f"m{i}" for i in range(3)]
    rows: list[Row] = [(i, "antrag", "abgelehnt", "BV1", 1, 4, True) for i in ids]
    model = build_outcomes(_outcomes(rows), _progress([]), _bodies(ids), settings, None)
    assert model.rows == () and (model.small_bodies, model.small_motions) == (1, 3)
    assert model.session is None


def test_ohne_schritt_sagt_der_erste_gast_was_fehlt() -> None:
    settings = _settings("moenchengladbach")
    assert not outcomes_built(settings)
    model = build_outcomes(None, None, None, settings, None)
    assert not model.on and model.missing
    html = _render(SECTION_OUTCOMES, {"beschlusslage": model, "check_sentence": ""})
    assert (
        "<li>Beschlusslage, Erfolg je Fraktion und Antworten in der Sitzung: der Wortschatz" in html
    )
    assert "<table" not in html


def test_namen_der_gremien_aus_dem_profil() -> None:
    names = code_names(_settings(), ["RAT", "BV3", "GLA+SPOA", "gr/27", None])
    assert names["RAT"] == "Rat" and names["BV3"] == "Bezirksvertretung 3"
    assert names["GLA+SPOA"].endswith(" und Sportausschuss")
    assert names["gr/27"] == "Gremium unbekannt"


# --- Abschnitt 2: Erfolg je Fraktion --------------------------------------------------------------
def _success(rows: list[tuple[str, str, int, int, float]]) -> pl.DataFrame:
    """(gremium_art, fraktion, n, angenommen, erwartet)."""
    from georep.analysis.outcomes import SUCCESS_SCHEMA

    return pl.DataFrame(
        [("2020-2025", k, f, n, a, e, a / e if e else None) for k, f, n, a, e in rows],
        schema=SUCCESS_SCHEMA,
        orient="row",
    )


def test_erfolg_nach_namen_ohne_rohe_quote_und_mit_der_mehrheit() -> None:
    settings = _settings()
    table = _success(
        [
            ("rat", "CDU", 60, 59, 30.0),
            ("ausschuss", "CDU", 40, 40, 30.0),
            ("rat", "AfD", 40, 0, 20.0),
            ("rat", "FDP", 20, 5, 10.0),  # unter MIN_SUCCESS
            ("bezirksvertretung", "CDU", 100, 95, 95.0),
            ("beirat", "CDU", 7, 7, 6.0),
        ]
    )
    model = build_success(table, settings, read_check(settings))
    council, districts = model.groups
    assert [r.label for r in council.rows] == ["AfD", "CDU", "FDP"]  # nach Namen
    cdu = next(r for r in council.rows if r.key == "CDU")
    assert (cdu.motions, cdu.observed) == (100, 99) and cdu.ratio == pytest.approx(99 / 60)
    assert cdu.majority and cdu.interval is not None and cdu.ratio is not None
    assert cdu.interval[0] < cdu.ratio < cdu.interval[1]
    assert next(r for r in council.rows if r.key == "FDP").ratio is None
    assert council.majority_ratio == pytest.approx(99 / 60)
    assert council.others_ratio == pytest.approx(5 / 30)  # auch Fraktionen ohne eigenes Verhältnis
    assert districts.rows[0].ratio == pytest.approx(1.0)
    assert model.majority == ("CDU", "Grüne") and model.elsewhere == (("Beiräten", 7),)
    html = _render(SECTION_SUCCESS, {"antragserfolg": model})
    assert "<h2>Erfolg der Anträge je Fraktion (explorativ)</h2>" in html
    assert "heißt Erfolg fast nur, zur Mehrheit zu gehören" in html
    assert f"unter {MIN_SUCCESS}" in html and "data-sort" not in html
    assert ">99<" not in html and ">59<" not in html  # keine beobachtete Zahl, keine rohe Quote


@pytest.mark.parametrize(
    ("profile", "parties"),
    [
        ("duesseldorf-2014", ("SPD", "GRUENE", "FDP")),
        ("duesseldorf", ("CDU", "GRUENE")),
        ("duesseldorf-2025", ("CDU", "GRUENE")),
    ],
)
def test_die_mehrheit_ist_die_der_laengsten_zeit(profile: str, parties: tuple[str, ...]) -> None:
    """Die alte Mehrheit gilt in der Hauptperiode noch bis 2020-10-31; sie bestimmt keine Zeile."""
    keys, since = majority_fractions(_settings(profile))
    assert sorted(keys) == sorted(parties) and since is not None


# --- Abschnitt 3: In der Sitzung beantwortet ------------------------------------------------------
def test_beantwortet_nach_dem_wortlaut_neben_den_antworten_von_14() -> None:
    settings = _settings()
    words = settings.outcomes.answered
    assert words == ["beantwortet", "schriftlich beantwortet"]
    n = 30
    ids = [f"q{i:02d}" for i in range(n)]
    answers = pl.DataFrame(
        {
            "id": ids,
            "gremium": ["RAT"] * n,
            "quelle": ["anlage"] * 5 + ["keine"] * 25,
        }
    )
    results = pl.DataFrame(
        {
            "id": ids,
            "result": ["schriftlich beantwortet"] * 10
            + ["beantwortet"] * 10
            + ["zur Kenntnis genommen"] * 9
            + [None],
        }
    )
    model = build_session(answers, results, _bodies(ids, "RAT"), settings)
    (row,) = model.rows
    assert (row.questions, row.attached, row.answered, row.written) == (30, 5, 20, 10)
    assert row.neither == 10  # die fünf mit Anlage tragen auch einen Eintrag
    html = _render(SECTION_SESSION, {"sitzung": model})
    assert "<h2>In der Sitzung beantwortet</h2>" in html
    assert "„beantwortet“ oder „schriftlich beantwortet“" in html
    assert "keine geprüfte Klasse" in html


def test_ohne_wortschatz_fuer_antworten_sagt_der_gast_was_fehlt() -> None:
    settings = _settings()
    settings = settings.model_copy(
        update={
            "outcomes": settings.outcomes.model_copy(
                update={"answered": [], "answered_written": []}
            )
        }
    )
    answers = pl.DataFrame({"id": ["q"], "gremium": ["RAT"], "quelle": ["keine"]})
    model = build_session(
        answers, pl.DataFrame({"id": ["q"], "result": [None]}), _bodies(["q"]), settings
    )
    assert not model.on and "outcomes.answered" in model.missing[0]


def test_der_wortschatz_der_antworten_steht_in_den_ergebnissen() -> None:
    from georep.settings import Outcomes

    with pytest.raises(ValueError, match="outcomes.answered"):
        Outcomes(results={"beantwortet": ("stand", "erledigt")}, answered=["gibt es nicht"])
    with pytest.raises(ValueError, match="answered_written"):
        Outcomes(
            results={"beantwortet": ("stand", "erledigt")},
            answered=["beantwortet"],
            answered_written=["anders"],
        )


# --- Der Haken im Dokumentdialog ------------------------------------------------------------------
def test_das_wort_eines_antrags() -> None:
    assert (
        outcome_label("beschlossen", "Rat", dt.date(2024, 3, 12)) == "angenommen (Rat, 12.03.2024)"
    )
    assert outcome_label("ohne_ergebnis", None, None) == CLASS_WORDS["ohne_ergebnis"]
    assert outcome_label("erledigt", "Bezirksvertretung 9", dt.date(2015, 1, 1), practice=True) == (
        f"{PRACTICE_WORD} (Bezirksvertretung 9, 01.01.2015)"
    )
    assert set(CLASS_WORDS) == {
        "beschlossen",
        "geaendert",
        "abgelehnt",
        "zurueckgezogen",
        "erledigt",
        "vertagt",
        "offen",
        "ohne_ergebnis",
    }


def test_der_haken_zeigt_nur_antraege(mini_run: Layout, default_settings: Settings) -> None:
    """Je Antrag eine Zeile mit einem Wort, kein anderes Dokument; 14 und 18 bleiben daneben."""
    assert DIALOG.name == DIALOG_NAME == "beschluesse"
    assert dialog_names(default_settings)[-1] == DIALOG_NAME
    listed = json.loads((mini_run.site_data / "dokumente.json").read_text(encoding="utf-8"))
    payload = json.loads((mini_run.site_data / "beschluesse.json").read_text(encoding="utf-8"))
    assert payload["title"] == "Beschlusslage" and payload["format"] == 3
    assert "nicht von Menschen" in payload["note"] and "Niederschrift" in payload["note"]
    lage = pl.read_parquet(outcome_files(mini_run).outcomes).join(
        pl.read_parquet(mini_run.corpus, columns=["id", "reference"]), on="id"
    )
    references = lage.get_column("reference").drop_nulls()
    assert references.n_unique() == references.len()  # die Drucksache trägt die Zuordnung
    motions = set(lage.filter(pl.col("dokument_rolle") == "antrag").get_column("reference"))
    keyed = {str(i): doc[2] for i, doc in enumerate(listed["documents"])}
    shown = {i for i, reference in keyed.items() if reference in motions}
    assert shown and set(payload["rows"]) == shown  # jeder Antrag des Dialogs, sonst keiner
    assert all(len(entries) == 1 and len(entries[0]) == 1 for entries in payload["rows"].values())
    # die Wörter je einmal, für jeden Antrag des Datensatzes, auch ohne Dokument im Dialog
    assert payload["documents"] == [] and len(payload["labels"]) <= len(motions)
    assert len(listed["documents"]) > len(payload["rows"])
    assert (mini_run.site_data / "beschluesse.json").stat().st_size < DIALOG_BUDGET


# --- Register, Seite und Downloads ----------------------------------------------------------------
def test_drei_gaeste_auf_vorgaenge_ein_haken_drei_tabellen() -> None:
    assert [(s.page, s.name) for s in SECTIONS] == [
        ("vorgaenge", SECTION_OUTCOMES),
        ("vorgaenge", SECTION_SUCCESS),
        ("vorgaenge", SECTION_SESSION),
    ]
    assert SECTION_SESSION == SESSION_GUEST  # der Name, den 14 erwartet
    assert [t.name for t in TABLES] == ["beschlusslage", "beratungsverlauf", "antragserfolg"]
    assert [t.csv is None for t in TABLES] == [True, True, False]  # Rückstand 35
    assert TABLES[0].check is not None and TABLES[2].check is None
    assert CONTRIBUTION.dialogs == (DIALOG,)
    for section in SECTIONS:
        text = (TEMPLATES / f"{section.name}.html.j2").read_text(encoding="utf-8")
        assert text.startswith("{% if data.")


def test_die_drei_rollen_stehen_in_schema_json_auseinander(
    mini_run: Layout, default_settings: Settings
) -> None:
    """Rückstand 15 (d): ``rolle`` von 14, ``beratung_rolle`` und ``dokument_rolle`` von 26."""
    schema = json.loads((mini_run.site_data / "schema.json").read_text(encoding="utf-8"))
    docs = {
        (table, c["column"]): c["description"]
        for table, columns in schema["tables"].items()
        for c in columns
    }
    roles = {
        ("dokumente_vorgang", "rolle"): ("Stellung im Vorgang", "dokument_rolle", "beratung_rolle"),
        ("beratungsverlauf", "beratung_rolle"): ("Rolle der Beratung", "dokument_rolle", "rolle"),
        ("beschlusslage", "dokument_rolle"): ("Rolle des Dokuments", "beratung_rolle", "rolle"),
    }
    for key, words in roles.items():
        assert all(word in docs[key] for word in words), key
    assert ("beschlusslage", "pruefauftrag_beantragt") not in docs  # Rückfall 1
    assert any("Stellung im Vorgang" in d for t in PROCEDURE_TABLES for d, _ in t.columns.values())


def test_die_downloads_und_ihre_spalten(mini_run: Layout, default_settings: Settings) -> None:
    names = {t.name for t in published(mini_run, default_settings)}
    assert {"beschlusslage", "beratungsverlauf", "antragserfolg"} <= names
    columns = (mini_run.site / "spalten.html").read_text(encoding="utf-8")
    details = mini_run.site_details.read_text(encoding="utf-8")
    for name in ("beschlusslage", "beratungsverlauf", "antragserfolg"):
        assert (mini_run.site_data / f"{name}.parquet").is_file()
        assert f'<section id="{name}">' in columns
        assert f'href="spalten.html#{name}"' in details
    assert (mini_run.site_data / "antragserfolg.csv").is_file()
    for name in ("beschlusslage", "beratungsverlauf"):
        assert not (mini_run.site_data / f"{name}.csv").is_file()
    published_lage = pl.read_parquet(mini_run.site_data / "beschlusslage.parquet")
    assert "pruefauftrag_beantragt" not in published_lage.columns
    assert '<p class="note"><code>beschlusslage</code>: Die Klasse folgt' in details


def test_die_drei_gaeste_stehen_auf_vorgaenge_html(mini_run: Layout) -> None:
    page = (mini_run.site / "vorgaenge.html").read_text(encoding="utf-8")
    for name, title in (
        (SECTION_OUTCOMES, "Beschlusslage je Gremium"),
        (SECTION_SUCCESS, "Erfolg der Anträge je Fraktion"),
        (SECTION_SESSION, "In der Sitzung beantwortet"),
    ):
        assert page.count(f'<section id="{name}">') == 1
        assert page.count(f'<li><a href="#{name}">{title}</a></li>') == 1
    assert page.index('<section id="vorgaenge">') < page.index(f'<section id="{SECTION_OUTCOMES}">')
    order = [
        page.index(f'<section id="{n}">')
        for n in (SECTION_OUTCOMES, SECTION_SUCCESS, SECTION_SESSION)
    ]
    assert order == sorted(order)
    assert "die dieser Datensatz nicht liest (†)" not in page  # 26 ersetzt den Hinweis von 14


def test_die_vorlagen_nennen_keine_partei() -> None:
    names: set[str] = set()
    for profile in ("duesseldorf", "moenchengladbach"):
        settings = load_settings(profile=profile, cwd=NOWHERE)
        for party in (*settings.originators.parties, *settings.originators.groups):
            names |= {n for n in (party.key, party.label, party.short) if n}
    text = "".join(p.read_text(encoding="utf-8") for p in sorted(TEMPLATES.glob("*.j2")))
    docs = " ".join(d for table in TABLES for d, _ in table.columns.values())
    docs += " ".join(table.description for table in TABLES) + DIALOG.description
    for source in (text, docs):
        assert sorted(n for n in names if re.search(rf"(?<!\w){re.escape(n)}(?!\w)", source)) == []


def _render(name: str, data: dict[str, object]) -> str:
    data = {"urls": {"measurement": "m", "check": "c", "check_folder": "f"}, **data}
    return environment().get_template(f"pages/vorgaenge/{name}.html.j2").render(data=data)


# --- Nach den Fotos (2026-11-28) ------------------------------------------------------------------
def test_die_koepfe_der_zehn_spalten_brechen_um(mini_run: Layout) -> None:
    """Bei 1280 Pixeln schob die Tabelle „ohne Ergebnis" und den Median aus dem Bild."""
    page = (mini_run.site / "vorgaenge.html").read_text(encoding="utf-8")
    assert "#beschlusslage-gremien th.num { white-space: normal;" in page


def test_die_praxiszellen_stehen_als_aufzaehlung_mit_und() -> None:
    settings = _settings()
    rows: list[Row] = []
    for body, prefix in (("BV1", "b"), ("RAT", "r")):
        rows += [(f"{prefix}{i:02d}", "antrag", "erledigt", body, 1, 3, False) for i in range(10)]
    ids = [row[0] for row in rows]
    model = build_outcomes(_outcomes(rows), _progress([]), _bodies(ids), settings, None)
    assert [(c.body, c.year, c.done) for c in model.cells] == [
        ("Bezirksvertretung 1", 2015, 10),
        ("Rat", 2015, 10),
    ]
    html = _render(SECTION_OUTCOMES, {"beschlusslage": model, "check_sentence": ""})
    assert "Bezirksvertretung 1 2015 (10 von 10) und Rat 2015 (10 von 10) sind" in html
    success = _render(
        SECTION_SUCCESS, {"antragserfolg": build_success(_success([]), settings, None)}
    )
    assert "(*, oben)" not in success
