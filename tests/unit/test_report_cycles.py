"""Die Unterseite ``zeit.html`` (Vorhaben 17, Stufe 3; ``docs/plans/17-zeit.md``, § 7).

Vier Gruppen. Die Bausteine an kleinen, erfundenen Tabellen (Monatsreihen, Wahljahre mit ihrer
Rolle, Haushaltsmonat oder keiner, Vokabular je Wahljahr, Ereignisse, Feeds). Der Prüfsatz kommt aus
``guete.json`` und den Labels von F4, nicht von Hand: eine geänderte Datei ändert die Seite, eine
neue Kodierung macht ``VALIDATED`` ungültig. Die Hypothesen mit Wort, Holm und Commit, und wo sie
stehen, wenn ein Profil sie nicht rechnet. Die echte Seite der Mini-Fixture: im Register, mit
Linkblock auf der Hauptseite, den Downloads, unter dem Budget, ohne Feed-Link auf ``index.html``.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.analysis.cycles import (
    BUDGET_SCHEMA,
    HYPOTHESES_EXTRA,
    MONTH_SCHEMA,
    PREREGISTERED,
)
from georep.analysis.hypotheses import CORE_SCHEMA, check_hypotheses, family, hypothesis_frame
from georep.analysis.lexicon import load_lexicon
from georep.analysis.parties import URHEBER_ARTEN
from georep.enrich.cycles import PAGE, TABLES, time_files
from georep.errors import SchemaError
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.report.cycles import (
    DOCUMENT_COLUMNS,
    FRACTION_GROUP,
    GROUPS,
    HYPOTHESES,
    PREREGISTRATION,
    VALIDATION_PROJECT,
    TimeInputs,
    build_time,
    effect_text,
    p_text,
    page_data,
    read_check,
    rhythm,
    time_links,
)
from georep.report.feeds import FEEDS_SCHEMA
from georep.report.pages import page_frame, render_page
from georep.report.tables import published
from georep.settings import Settings, load_settings
from tests.conftest import REPO, mg_settings

NOW = dt.datetime(2026, 11, 27, 12, 0, tzinfo=dt.UTC)
PAGE_BUDGET = 500_000  # docs/plan-zeigen-2026-11.md, § 6: jede Unterseite unter 500 KB
LEXICON = load_lexicon("bundespolitik")
NOWHERE = Path("/nonexistent")
SECTIONS = ("ueberblick", "rhythmus", "hypothesen", "vokabular", "ereignisse")


def _check_settings(settings: Settings, root: Path = REPO / "validierung") -> Settings:
    """Die Settings mit dem Ordner der Validierung im Repo, unabhängig vom Arbeitsverzeichnis."""
    return settings.model_copy(
        update={"validation": settings.validation.model_copy(update={"root": root})}
    )


def _profile(name: str) -> Settings:
    return _check_settings(load_settings(profile=name, cwd=NOWHERE))


def _with_feeds(settings: Settings, *, timer: bool = False) -> Settings:
    return settings.model_copy(
        update={"feeds": settings.feeds.model_copy(update={"enabled": True, "timer": timer})}
    )


# --- erfundene Tabellen -----------------------------------------------------------------------------
# Vier vollständige Wahljahre 2021/22 bis 2024/25 und ein angeschnittener Monat danach: 2024/25 ist
# das Vorwahljahr der Wahl vom 14.09.2025 (``cycles.elections`` im Stadtprofil), 2021/22 das Anlaufjahr.
YEARS = (2021, 2022, 2023, 2024)


def _months(*, budget: bool = True) -> pl.DataFrame:
    rows = []
    for year in YEARS:
        for i in range(12):
            month = (8 + i) % 12 + 1
            day = dt.date(year + (month < 9), month, 1)
            fraction = 10 + i + (year - 2021)  # jedes Jahr ein Dokument mehr je Monat
            motions = 6 if budget and month == 12 else 0
            for art, n in (("Verwaltung", 20), ("Fraktion", fraction), ("Person", 2)):
                rows.append(
                    {
                        "monat": day,
                        "wahljahr": year,
                        "gremium_art": "rat",
                        "urheber_art": art,
                        "instrument": "sonst",
                        "dokumente": n,
                        "mit_text": n,
                        "haushaltsantraege": motions if art == "Fraktion" else 0,
                    }
                )
    for art, n in (("Verwaltung", 3), ("Fraktion", 4), ("Person", 0)):
        rows.append(
            {
                "monat": dt.date(2025, 9, 1),
                "wahljahr": None,
                "gremium_art": "rat",
                "urheber_art": art,
                "instrument": "sonst",
                "dokumente": n,
                "mit_text": n,
                "haushaltsantraege": 0,
            }
        )
    return pl.DataFrame(rows, schema=MONTH_SCHEMA)


def _budget(*, found: bool = True) -> pl.DataFrame:
    rows = [
        {
            "wahljahr": year,
            "monat_kalender": 12 if found else None,
            "haushaltsantraege": 6 if found else 1,
            "im_monat": 6 if found else None,
        }
        for year in YEARS
    ]
    return pl.DataFrame(rows, schema=BUDGET_SCHEMA)


def _documents() -> pl.DataFrame:
    rows = []
    n = 0
    for year in YEARS:
        for k in range(40):
            n += 1
            day = dt.date(year, 10, 1) + dt.timedelta(days=7 * k)
            categories = []
            if k < 2 + (year - 2021):
                categories.append("migration_asyl")
            if year == 2022 and k < 5:
                categories.append("corona")
            rows.append(
                {
                    "id": f"https://ris.example/papers/{n:05d}",
                    "date": day,
                    "mit_text": k != 39,
                    "urheber_art": "Fraktion" if k % 2 else "Verwaltung",
                    "gremium": "RAT" if k % 3 else "BV1",
                    "gremium_art": "rat" if k % 3 else "bezirksvertretung",
                    "stadtbezirk": None if k % 3 else 1,
                    "kategorien": categories,
                }
            )
    return pl.DataFrame(
        rows,
        schema={
            "id": pl.String,
            "date": pl.Date,
            "mit_text": pl.Boolean,
            "urheber_art": pl.String,
            "gremium": pl.String,
            "gremium_art": pl.String,
            "stadtbezirk": pl.Int64,
            "kategorien": pl.List(pl.String),
        },
    )


def _hypotheses(*, fixed: str = PREREGISTERED) -> pl.DataFrame:
    """Eine Tabelle im Kern wie ``zeit_hypothesen``, mit den Zahlen des Messdokuments (§ 8.5)."""
    common = {"festgelegt": fixed, "lexikon": LEXICON.label, "daten_bis": dt.date(2026, 10, 13)}
    rows: list[dict[str, Any]] = [
        {
            "hypothese": "H17.1",
            "rolle": "Haupttest",
            "mass": "ln der Fraktionsdokumente je Wahljahr, ohne Anlaufjahr",
            "test": "OLS mit Konstante je Periode, t einseitig (δ > 0)",
            "effekt": -0.0489,
            "effekt_unten": -0.129,
            "effekt_oben": 0.038,
            "einheit": "relativ",
            "p": 0.8472,
            "p_randomisierung": 0.8,
            "zuordnungen": 20,
            "n": 9,
        },
        {
            "hypothese": "H17.1/S1.4",
            "rolle": "Sensitivität",
            "mass": "Anteil der Fraktionsdokumente an allen Dokumenten je Wahljahr",
            "test": "OLS",
            "effekt": -0.0283,
            "einheit": "anteil",
            "p": 0.9941,
            "n": 9,
        },
        {
            "hypothese": "H17.2",
            "rolle": "Haupttest",
            "mass": "ln(1 + Fraktionsdokumente) je Wahljahr und Kalendermonat",
            "test": "Zwei-Wege-Modell, Randomisierung über alle Zuordnungen der Haushaltsmonate, einseitig",
            "effekt": 0.831,
            "einheit": "relativ",
            "p": 1 / 27720,
            "zuordnungen": 27720,
            "n": 12,
        },
        {
            "hypothese": "H17.2/S2.1",
            "rolle": "Sensitivität",
            "mass": "dasselbe ohne die Haushaltsanträge",
            "test": "Zwei-Wege-Modell, Randomisierung über alle Zuordnungen der Haushaltsmonate, zweiseitig",
            "effekt": -0.129,
            "einheit": "relativ",
            "p": 0.2459,
            "zuordnungen": 27720,
            "n": 12,
        },
        {
            "hypothese": "H17.3",
            "rolle": "Haupttest",
            "mass": "Anteil der Dokumente mit Text und Treffer einer Strukturkategorie je Wahljahr",
            "test": "Jonckheere-Terpstra exakt, einseitig steigend",
            "effekt": 0.0347 - 0.0598,
            "einheit": "anteil",
            "anteile": [0.0598, 0.0316, 0.0347],
            "p": 0.98665,
            "zuordnungen": 5544,
            "n": 12,
        },
        {
            "hypothese": "H17.3/S3.3/corona",
            "rolle": "explorativ",
            "mass": "Anteil mit Treffer der Kategorie Corona-Pandemie",
            "test": "Jonckheere-Terpstra exakt, einseitig steigend",
            "effekt": 0.0055 - 0.0121,
            "einheit": "anteil",
            "anteile": [0.0121, 0.0733, 0.0055],
            "p": 0.0395,
            "zuordnungen": 5544,
            "n": 12,
        },
    ]
    main = {r["hypothese"]: r["p"] for r in rows if r["rolle"] == "Haupttest"}
    decided = family(main)
    for row in rows:
        row.update(common)
        if row["hypothese"] in decided:
            row["p_holm"], row["ergebnis"] = decided[row["hypothese"]]
    frame = hypothesis_frame(rows, HYPOTHESES_EXTRA)
    check_hypotheses(frame)
    return frame


def _feeds() -> pl.DataFrame:
    rows = [
        {
            "wahlkreis_id": d,
            "datei": f"feeds/wahlbezirk-{d:02d}.xml",
            "eintraege": 50 if d < 3 else 0,
            "dokumente": 120 - d if d < 3 else 0,
            "neu_30_tage": 7 if d < 3 else 0,
            "aktualisiert": "2026-10-05T09:10:24+02:00" if d < 3 else "2026-10-13T00:00:00+02:00",
            "bytes": 25000 if d < 3 else 900,
        }
        for d in (1, 2, 3)
    ]
    return pl.DataFrame(rows, schema=FEEDS_SCHEMA)


def _inputs(
    *, budget: bool = True, hypotheses: pl.DataFrame | None = None, feeds: bool = False
) -> TimeInputs:
    return TimeInputs(
        months=_months(budget=budget),
        budget=_budget(found=budget),
        documents=_documents(),
        hypotheses=hypotheses,
        feeds=_feeds() if feeds else None,
    )


def _render(settings: Settings, inputs: TimeInputs) -> str:
    check = read_check(settings, LEXICON)
    model = build_time(inputs, settings, LEXICON, check)
    return render_page(
        page_frame(settings, now=NOW, commit=None),
        PAGE,
        page_data(model, settings),
        time_links(Layout(NOWHERE, NOWHERE, NOWHERE), settings),
    )


def _section(page: str, name: str) -> str:
    start = page.index(f'<section id="{name}">')
    return page[start : page.index("</section>", start)]


# --- Bezeichnungen und Konstanten -------------------------------------------------------------------
def test_die_drei_reihen_decken_die_urheberklassen_genau_ab() -> None:
    arts = [a for _, _, group in GROUPS for a in group]
    assert sorted(arts) == sorted(URHEBER_ARTEN) and len(arts) == len(set(arts))
    assert GROUPS[FRACTION_GROUP][2] == ("Fraktion",)  # H17.1 und H17.2 zählen diese Reihe


def test_die_festlegung_ist_die_des_messdokuments() -> None:
    """§ 8: Commit 9c7b3d6, 2026-11-23 um 19:45; dieselbe Kennung wie in ``zeit_hypothesen``."""
    assert PREREGISTRATION.commit == PREREGISTERED == "9c7b3d6"
    assert PREREGISTRATION.when == dt.datetime(2026, 11, 23, 19, 45)
    assert set(HYPOTHESES) == {"H17.1", "H17.2", "H17.3"}


@pytest.mark.parametrize(
    ("p", "text"),
    [(0.8472, "0,847"), (1.0, "1,000"), (1 / 27720, "0,000036"), (3 / 27720, "0,00011")],
)
def test_ein_p_wert_in_deutscher_schreibweise(p: float, text: str) -> None:
    assert p_text(p) == text


def test_der_effekt_in_worten() -> None:
    relative = {
        "effekt": -0.0489,
        "effekt_unten": -0.129,
        "effekt_oben": 0.038,
        "einheit": "relativ",
    }
    assert effect_text(relative) == "-4,9 % (90 %: -12,9 bis +3,8 %)"
    assert effect_text({"effekt": 0.831, "einheit": "relativ"}) == "+83,1 %"
    assert effect_text({"effekt": -0.0283, "einheit": "anteil"}) == "-2,83 Prozentpunkte"
    shares = {"effekt": -0.0251, "einheit": "anteil", "anteile": [0.0598, 0.0316, 0.0347]}
    assert effect_text(shares, ("A", "B", "C")) == (
        "5,98 / 3,16 / 3,47 % je Periode (A, B, C); Differenz der letzten zur ersten "
        "-2,51 Prozentpunkte"
    )


# --- Die Prüfung aus guete.json und den Labels von F4 ----------------------------------------------
def _quality() -> dict[str, Any]:
    path = REPO / "validierung" / VALIDATION_PROJECT / "guete.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize(
    ("profile", "measured"),
    [
        ("duesseldorf", True),
        ("duesseldorf-2014", True),
        ("duesseldorf-2025", True),
        ("duesseldorf-vergleich", True),  # rechnet im Ordner der Hauptperiode
        ("moenchengladbach", False),
    ],
)
def test_der_pruefsatz_kommt_aus_guete_json(profile: str, measured: bool) -> None:
    check = read_check(_profile(profile), LEXICON)
    quality = _quality()
    assert check.sentence == quality["satz"]
    assert (check.topic.agreed, check.topic.units) == (96, 100)
    assert round(check.topic.alpha, 3) == 0.957 and round(check.level.alpha, 3) == 0.928
    assert (check.right, check.coded, check.validated) == (94, 100, True)
    assert check.same_model  # alle drei Rollen ein Modell (Punkt 87)
    assert check.measured is measured


def test_je_kategorie_richtig_und_bundesebene_wie_im_messdokument() -> None:
    """§ 4.1: „richtig k von 10" und „nennt die Bundesebene" unter den richtigen Treffern."""
    check = read_check(_profile("duesseldorf"), LEXICON)
    found = {c: (k.right, k.coded, k.federal) for c, k in check.categories.items()}
    assert found == {
        "migration_asyl": (10, 10, 4),
        "klima_energie": (9, 10, 8),
        "sozialstaat": (10, 10, 10),
        "gendern": (8, 10, 3),
        "bundesverkehr": (10, 10, 7),
        "wohnen_bund": (10, 10, 10),
        "cannabis": (10, 10, 2),
        "corona": (10, 10, 0),
        "ukraine_krieg": (8, 10, 1),
        "energiekrise": (9, 10, 3),
    }
    low, high = check.interval
    assert (round(low, 2), round(high, 2)) == (0.88, 0.97)  # Wilson wie § 1 des Messdokuments


def _copy_check(tmp_path: Path) -> Path:
    folder = tmp_path / VALIDATION_PROJECT
    shutil.copytree(REPO / "validierung" / VALIDATION_PROJECT, folder)
    return folder


def test_eine_geaenderte_guete_json_aendert_die_seite(tmp_path: Path) -> None:
    """Satz, Übereinstimmung und „schwacher Beleg" hängen an der Datei, nicht an der Vorlage."""
    settings = _profile("duesseldorf")
    original = _render(settings, _inputs())
    quality = _quality()
    assert quality["satz"] in original and "schwacher Beleg" in original
    folder = _copy_check(tmp_path)
    quality["satz"] = "geprüft von zwei KI-Kodierern (modell-a und modell-b) an 100 Dokumenten"
    quality["modelle"]["kodierer_b"] = "modell-b"
    quality["fragen"]["thema"]["einig"] = 91
    (folder / "guete.json").write_text(json.dumps(quality), encoding="utf-8")
    changed = _render(_check_settings(settings, tmp_path), _inputs())
    assert quality["satz"] in changed and _quality()["satz"] not in changed
    assert "beim Thema in 91 von 100 Treffern überein" in changed
    assert "schwacher Beleg" not in changed


def test_eine_neue_kodierung_macht_validated_ungueltig(tmp_path: Path) -> None:
    """Weichen die Labels von ``VALIDATED`` ab, ist das ein Fehler, keine stille neue Zahl."""
    folder = _copy_check(tmp_path)
    path = folder / "labels.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    first = next(r for r in rows if r["frage"] == "thema" and r["label"] == '["corona"]')
    first["label"] = '["anderes"]'
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(SchemaError, match="nachzurechnen"):
        read_check(_check_settings(_profile("duesseldorf"), tmp_path), LEXICON)


def test_eine_ungepruefte_lexikonversion_zeigt_keine_zahl_je_kategorie() -> None:
    settings = _profile("duesseldorf")
    other = replace(LEXICON, version="2099-01-01.9")
    check = read_check(settings, other)
    assert not check.validated and check.categories == {}
    model = build_time(_inputs(), settings, other, check)
    page = render_page(
        page_frame(settings, now=NOW, commit=None),
        PAGE,
        page_data(model, settings),
        time_links(Layout(NOWHERE, NOWHERE, NOWHERE), settings),
    )
    assert "nicht an Labels geprüft" in page and "nennt die Bundesebene" not in page


# --- Rhythmus, Wahljahre, Haushaltsmonat -----------------------------------------------------------
def test_die_reihen_summieren_und_die_wahljahre_tragen_ihre_rolle(
    default_settings: Settings,
) -> None:
    from georep.enrich.cycles import cycle_rules

    model = rhythm(_months(), _budget(), cycle_rules(default_settings))
    assert len(model.months) == 49  # vier Wahljahre und ein angeschnittener Monat
    assert sum(p.total for p in model.panels) == int(_months().get_column("dokumente").sum())
    assert [s.label for s in model.spans] == ["2021/22", "2022/23", "2023/24", "2024/25"]
    assert [m.month.month for m in model.months if m.budget] == [12] * 4
    assert model.budget_indexes == (3, 15, 27, 39)
    roles = [(y.label, y.role, y.election) for y in model.years]
    assert roles == [
        ("2021/22", "Anlaufjahr", None),
        ("2022/23", "mittleres Jahr", None),
        ("2023/24", "mittleres Jahr", None),
        ("2024/25", "Vorwahljahr", dt.date(2025, 9, 14)),
    ]
    (note,) = model.notes  # S1.6: das Vorwahljahr gegen das Mittel der mittleren Jahre
    fraction = {y.label: y.fraction for y in model.years}
    assert note.fraction == fraction["2024/25"]
    assert note.middle_mean == (fraction["2022/23"] + fraction["2023/24"]) / 2
    assert (note.rank, note.of) == (1, 3)
    assert len(model.calendar) == 12 and model.calendar[0].name == "Sep"
    assert model.months[-1].year is None and model.months[-1].label == ""


def test_ohne_haushaltsmonat_sagt_die_seite_das() -> None:
    """``docs/todo.md``, Punkt 13 (d): eine Stadt ohne Haushaltsmonat in keinem Wahljahr."""
    page = _render(_check_settings(mg_settings()), _inputs(budget=False))
    box = page[page.index('<div class="pruefung"') : page.index('<section id="rhythmus">')]
    assert "dieser Datensatz hat darum keinen Haushaltsmonat" in box
    assert "der Datensatz hat keinen Haushaltsmonat" in _section(page, "rhythmus")
    assert 'class="haushalt"' not in _section(page, "rhythmus")
    with_budget = _render(_profile("duesseldorf"), _inputs())
    assert "keinen Haushaltsmonat" not in with_budget
    assert with_budget.count('<rect class="haushalt"') == 4 * len(GROUPS)


# --- Die Hypothesen --------------------------------------------------------------------------------
def test_die_hypothesen_mit_wort_holm_und_commit() -> None:
    page = _render(_profile("duesseldorf-vergleich"), _inputs(hypotheses=_hypotheses()))
    section = _section(page, "hypothesen")
    # „nicht bestätigt" so groß wie „bestätigt": dasselbe Element, dieselbe Klasse
    words = re.findall(r'<span class="ergebnis">([^<]*)</span>', section)
    assert sorted(set(words)) == ["bestätigt", "nicht bestätigt"]
    assert words.count("nicht bestätigt") == 4 and words.count("bestätigt") == 2
    assert (
        f'href="https://github.com/konradvoelkel/geographic-representation-dus/commit/{PREREGISTERED}"'
        in page
    )
    assert "am 23.11.2026 um 19:45 Uhr in Commit" in section
    assert "Ohne die Haushaltsanträge selbst liegt der Haushaltsmonat 12,9 % unter" in section
    assert "Gewertet, weil das Lexikon" in section
    sensitivities = section[section.index('id="sensitivitaeten"') :]
    assert "H17.2/S2.1" in sensitivities and "0,246 zweiseitig" in sensitivities
    assert 'class="ergebnis"' not in sensitivities  # außerhalb der Familie kein Wort
    assert "explorativ" in sensitivities


def test_eine_fremde_festlegung_ist_ein_fehler() -> None:
    with pytest.raises(SchemaError, match="festgelegt"):
        _render(_profile("duesseldorf-vergleich"), _inputs(hypotheses=_hypotheses(fixed="abc1234")))


@pytest.mark.parametrize(
    ("profile", "sentence"),
    [
        ("duesseldorf-2014", "Sie stehen auf dieser Seite für die Wahlperiode 2020 bis 2025."),
        ("duesseldorf-2025", "Sie stehen auf dieser Seite für die Wahlperiode 2020 bis 2025."),
        ("duesseldorf", "erst im Lauf, der die Perioden vergleicht; in diesem Lauf fehlen sie."),
        ("moenchengladbach", "Für diesen Datensatz ist keine Hypothese vorab festgelegt."),
    ],
)
def test_ohne_tests_sagt_die_seite_wo_sie_stehen(profile: str, sentence: str) -> None:
    settings = (
        _check_settings(mg_settings()) if profile == "moenchengladbach" else _profile(profile)
    )
    section = _section(_render(settings, _inputs()), "hypothesen")
    assert sentence in section
    assert 'class="ergebnis"' not in section


# --- Vokabular, Ereignisse, explorativ -------------------------------------------------------------
def test_das_vokabular_je_wahljahr_und_kategorie() -> None:
    settings = _profile("duesseldorf")
    check = read_check(settings, LEXICON)
    model = build_time(_inputs(), settings, LEXICON, check)
    vocabulary = model.vocabulary
    assert vocabulary.years == ("2021/22", "2022/23", "2023/24", "2024/25")
    assert vocabulary.per_year == (39, 39, 39, 39)  # je Wahljahr 40 Dokumente, eines ohne Text
    rows = {r.key: r for r in vocabulary.rows}
    migration = rows["migration_asyl"]
    assert [c.hits for c in migration.cells] == [2, 3, 4, 5]
    assert migration.cells[-1].width == 1.0 and migration.pooled.hits == 14
    assert rows["struktur"].total and rows["struktur"].cells[0].hits == 2
    assert rows["alle"].cells[1].hits == 5  # 2022/23: die drei mit beidem zählen einmal
    assert rows["struktur"].check is not None and rows["struktur"].check.right == 67


def test_explorativ_wo_es_verlangt_ist() -> None:
    measured = _render(_profile("duesseldorf"), _inputs())
    elsewhere = _render(_check_settings(mg_settings()), _inputs())
    heading = re.compile(r"<h2>(.*?)</h2>")
    assert heading.search(_section(measured, "vokabular")).group(1) == "Bundespolitisches Vokabular"  # type: ignore[union-attr]
    assert heading.search(_section(elsewhere, "vokabular")).group(1).endswith("(explorativ)")  # type: ignore[union-attr]
    for page in (measured, elsewhere):
        assert heading.search(_section(page, "ereignisse")).group(1).endswith("(explorativ)")  # type: ignore[union-attr]
    assert "nicht an diesem Datensatz" in elsewhere and "nicht an diesem Datensatz" not in measured


def test_die_ereignisse_nennen_monat_und_gremien() -> None:
    """Ein Monat trägt einen Anteil erst ab 20 Dokumenten mit Text, ein Gremium ebenso."""
    settings = _profile("duesseldorf")
    dense = pl.DataFrame(
        [
            {
                "id": f"https://ris.example/papers/m{k:03d}",
                "date": dt.date(2023, 3, 1 + k % 28),
                "mit_text": True,
                "urheber_art": "Verwaltung",
                "gremium": "RAT",
                "gremium_art": "rat",
                "stadtbezirk": None,
                "kategorien": ["corona"] if k < 4 else [],
            }
            for k in range(25)
        ],
        schema=_documents().schema,
    )
    inputs = _inputs()
    inputs = replace(inputs, documents=pl.concat([inputs.documents, dense]))
    model = build_time(inputs, settings, LEXICON, read_check(settings, LEXICON))
    corona = next(e for e in model.events if e.key == "corona")
    assert corona.hits == 9 and corona.months == 49
    # die fünf Treffer von 2022 liegen in Monaten mit wenigen Dokumenten: keine Spitze dort
    assert (corona.peak_month, corona.peak_hits) == (dt.date(2023, 3, 1), 4)
    assert corona.peak_documents >= 25 and corona.thin == 48
    assert all(b.documents >= 20 for b in corona.bodies)
    assert [e.key for e in model.events] == list(LEXICON.of_kind("ereignis"))


# --- Neuigkeiten je Wahlbezirk ---------------------------------------------------------------------
def test_die_feeds_stehen_mit_datenstand_und_dem_satz_zum_schnappschuss() -> None:
    settings = _with_feeds(_profile("duesseldorf-2025"))
    page = _render(settings, _inputs(feeds=True))
    section = _section(page, "neuigkeiten")
    assert section.count('type="application/atom+xml"') == 3
    assert '<a href="feeds/wahlbezirk-01.xml"' in section  # relativ zur Seite der Periode
    last = _documents().get_column("date").max()
    assert isinstance(last, dt.date)
    assert f"Stand der Daten: {last:%d.%m.%Y}" in section
    assert "Ohne laufenden Abruf zeigen die Feeds diesen Stand" in section
    assert 'rel="self"' not in page  # Frage 28
    with_timer = _section(
        _render(_with_feeds(settings, timer=True), _inputs(feeds=True)), "neuigkeiten"
    )
    assert "Ohne laufenden Abruf" not in with_timer and "Stand der Daten" in with_timer


def test_ohne_feeds_gibt_es_den_abschnitt_nicht() -> None:
    page = _render(_profile("duesseldorf"), _inputs())
    assert 'id="neuigkeiten"' not in page and "feeds/" not in page


# --- Für alle gleich gebaut ------------------------------------------------------------------------
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
    folder = REPO / "src" / "georep" / "report" / "templates" / "pages"
    template = "".join(p.read_text(encoding="utf-8") for p in sorted(folder.glob("zeit*")))
    assert _named(template) == []
    page = _render(
        _with_feeds(_profile("duesseldorf-vergleich")),
        _inputs(hypotheses=_hypotheses(), feeds=True),
    )
    assert _named(page[page.index("<main>") : page.index("</main>")]) == []
    docs = " ".join(doc[0] for table in TABLES for doc in table.columns.values())
    assert _named(docs + " ".join(t.description for t in TABLES)) == []


def test_jede_spalte_der_seite_ist_da() -> None:
    settings = _profile("duesseldorf")
    inputs = _inputs()
    broken = replace(inputs, documents=inputs.documents.drop("kategorien"))
    with pytest.raises(SchemaError, match="kategorien"):
        build_time(broken, settings, LEXICON, read_check(settings, LEXICON))
    assert "kategorien" in DOCUMENT_COLUMNS


def test_die_seite_verlinkt_messdokument_pruefung_und_commit() -> None:
    links = time_links(Layout(NOWHERE, NOWHERE, NOWHERE), _profile("duesseldorf"))
    assert any(link.endswith("/docs/plans/17-zeit.md") for link in links)
    assert any(link.endswith(f"/validierung/{VALIDATION_PROJECT}/README.md") for link in links)
    assert any(link.endswith(f"/commit/{PREREGISTERED}") for link in links)


# --- Register, Linkblock, Downloads, Größe auf der Mini-Fixture -----------------------------------
def test_die_seite_steht_im_register_und_auf_der_hauptseite(mini_run: Layout) -> None:
    page = (mini_run.site / "zeit.html").read_text(encoding="utf-8")
    index = mini_run.site_index.read_text(encoding="utf-8")
    weitere = index[index.index('<section id="weitere">') :]
    weitere = weitere[: weitere.index("</section>")]
    assert '<a href="zeit.html">Zeit: Rhythmus der Ratsarbeit und Bundespolitik</a>' in weitere
    assert len(page.encode("utf-8")) < PAGE_BUDGET
    for name in SECTIONS:
        assert page.count(f'<section id="{name}">') == 1


def test_die_hauptseite_verlinkt_keinen_feed(mini_run: Layout) -> None:
    """Plan § 7 und Frage 9.11: kein Feed-Link auf ``index.html``, kein ``rel="self"``."""
    index = mini_run.site_index.read_text(encoding="utf-8")
    assert "feeds/" not in index and 'rel="self"' not in index


def test_die_tabellen_stehen_als_download_mit_spaltendoku(
    mini_run: Layout, default_settings: Settings
) -> None:
    names = {t.name for t in published(mini_run, default_settings)}
    assert {"zeit_monate", "haushaltsmonate", "dokumente_bundesvokabular"} <= names
    assert "zeit_hypothesen" not in names  # nur im Profil, das die Tests rechnet
    schema = json.loads((mini_run.site_data / "schema.json").read_text(encoding="utf-8"))
    for table in TABLES:
        if table.name not in names:
            continue
        assert (mini_run.site_data / f"{table.name}.csv").is_file()
        assert (mini_run.site_data / f"{table.name}.parquet").is_file()
        columns = list(pl.read_parquet_schema(table.path(mini_run)))
        assert columns == list(table.columns)
        described = {c["column"]: c["description"] for c in schema["tables"][table.name]}
        assert described == {name: doc[0] for name, doc in table.columns.items()}
    hypotheses = next(t for t in TABLES if t.name == "zeit_hypothesen")
    assert list(hypotheses.columns) == [*CORE_SCHEMA, *HYPOTHESES_EXTRA]


def test_der_bericht_liest_die_tabellen_von_17_mit(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Ändert sich eine Tabelle von 17, ist der Stamp von ``report`` nicht mehr aktuell."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    report = next(s for s in build_steps(default_settings, layout) if s.name == "report")
    files = time_files(layout)
    assert {files.months, files.budget, files.vocabulary} <= set(report.optional)


@pytest.mark.parametrize("profile", ["duesseldorf-vergleich", "duesseldorf-2025"])
def test_der_schritt_liest_tests_und_feeds_nur_wo_es_sie_gibt(tmp_path: Path, profile: str) -> None:
    settings = _profile(profile)
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference", settings.profile)
    step = next(s for s in build_steps(settings, layout) if s.name == "page_zeit")
    files = time_files(layout)
    assert (files.hypotheses in step.inputs) is bool(settings.cycles.periods)
    assert (files.feeds in step.inputs) is settings.feeds.enabled
