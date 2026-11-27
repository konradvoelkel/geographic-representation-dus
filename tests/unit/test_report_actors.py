"""Die Unterseite ``akteure.html`` (Vorhaben 15, Stufe 3; ``docs/plans/15-funktion.md``, § 7).

Drei Gruppen. Die Bausteine an kleinen, erfundenen Tabellen (Leisten, Fraktionen gegen die Praxis
der Gremien, Matrix mit Lager, K3, die zwei Zählungen der Parteien). Der Prüfsatz kommt aus
``guete.json`` und nicht von Hand: eine geänderte Datei ändert die Seite. Die echte Seite der
Mini-Fixture: im Register, mit Linkblock auf der Hauptseite, den beiden Downloads, unter dem
Budget, und für jede Stadt und jede Fraktion gleich gebaut.
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

from georep.enrich.functions import PAGE, TABLES, functions_files
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.report.actors import (
    DOCUMENT_COLUMNS,
    FUNCTION_LABELS,
    INSTRUMENT_LABELS,
    MIN_DOCUMENTS,
    RULE_CHECK,
    VALIDATION_PROJECT,
    MajorityContext,
    actors_links,
    build_actors,
    concordance,
    cosponsor_matrix,
    counting_difference,
    fraction_rows,
    function_bars,
    labels_of,
    page_data,
    read_check,
)
from georep.report.pages import PageSection, page_frame, render_page
from georep.report.render import environment
from georep.report.tables import published
from georep.settings import FUNCTION_CLASSES, FUNCTION_INSTRUMENTS, Settings, load_settings
from tests.conftest import REPO, mg_settings

NOW = dt.datetime(2026, 11, 27, 12, 0, tzinfo=dt.UTC)
PAGE_BUDGET = 500_000  # docs/plan-zeigen-2026-11.md, § 6: jede Unterseite unter 500 KB
SCHEMA: dict[str, Any] = {
    "id": pl.String,
    "name": pl.String,
    "reference": pl.String,
    "date": pl.Date,
    "download_url": pl.String,
    "funktion": pl.String,
    "instrument": pl.String,
    "antragsteller": pl.List(pl.String),
    "fraktionen": pl.List(pl.String),
    "gemeinsam": pl.Boolean,
    "lager": pl.String,
    "urheber_art": pl.String,
    "parteien": pl.List(pl.String),
    "gremium": pl.String,
    "gremium_art": pl.String,
    "stadtbezirk": pl.Int64,
}
INSTRUMENT_OF = {"kontrolle": "anfrage", "initiative": "antrag", "erklaerung": "resolution"}


def _doc(
    n: int,
    *,
    funktion: str = "initiative",
    fraktionen: Sequence[str] = (),
    urheber: str = "Fraktion",
    gremium: str = "RAT",
    art: str = "rat",
    day: dt.date = dt.date(2021, 3, 1),
    lager: str = "ohne_lager",
    parteien: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": f"https://ris.example/papers/{n:05d}",
        "name": f"Antrag {n}",
        "reference": f"X/{n:03d}/2021",
        "date": day,
        "download_url": f"http://ris.example/downloadfiles/{n:05d}.pdf",
        "funktion": funktion,
        "instrument": INSTRUMENT_OF.get(funktion, "beschlussvorlage"),
        "antragsteller": list(fraktionen),
        "fraktionen": list(fraktionen),
        "gemeinsam": len(fraktionen) >= 2,
        "lager": lager,
        "urheber_art": urheber,
        "parteien": list(fraktionen if parteien is None else parteien),
        "gremium": gremium,
        "gremium_art": art,
        "stadtbezirk": None,
    }


def _frame(rows: Sequence[dict[str, Any]]) -> pl.DataFrame:
    return pl.DataFrame(list(rows), schema=SCHEMA)


def _check_settings(settings: Settings, root: Path = REPO / "validierung") -> Settings:
    """Die Settings mit dem Ordner der Validierung im Repo, unabhängig vom Arbeitsverzeichnis."""
    return settings.model_copy(
        update={"validation": settings.validation.model_copy(update={"root": root})}
    )


def _context(settings: Settings) -> MajorityContext:
    from georep.analysis.parties import Patterns

    order = {k: i for i, (k, _) in enumerate(Patterns.from_settings(settings.originators).parties)}
    return MajorityContext(settings.majorities, tuple(settings.functions.fractions), order)


# --- Bezeichnungen ---------------------------------------------------------------------------------
def test_jede_funktion_und_jedes_instrument_hat_eine_bezeichnung() -> None:
    """Ein neues Instrument in ``settings.FUNCTION_INSTRUMENTS`` stünde sonst als Schlüssel da."""
    assert tuple(FUNCTION_LABELS) == FUNCTION_CLASSES
    assert set(INSTRUMENT_LABELS) == {i for group in FUNCTION_INSTRUMENTS.values() for i in group}


# --- Abschnitt 1: Leisten ---------------------------------------------------------------------------
def test_eine_leiste_je_urheberklasse_summiert_zu_ihren_dokumenten() -> None:
    rows = [
        _doc(1, funktion="vollzug", urheber="Verwaltung"),
        _doc(2, funktion="information", urheber="Verwaltung"),
        _doc(3, funktion="information", urheber="Verwaltung"),
        _doc(4, funktion="kontrolle", fraktionen=["CDU"]),
        _doc(5, funktion="rest", urheber="unbekannt"),
    ]
    bars = function_bars(_frame(rows))
    assert [b.originator for b in bars] == ["Verwaltung", "Fraktion", "unbekannt"]
    administration = bars[0]
    assert [(s.function, s.count) for s in administration.segments] == [
        ("information", 2),
        ("vollzug", 1),
    ]
    assert administration.segments[1].x == pytest.approx(2 / 3)
    assert sum(s.width for s in administration.segments) == pytest.approx(1.0)


# --- Abschnitt 2: Fraktionen gegen die Praxis der Gremien -------------------------------------------
def test_kontrolle_je_fraktion_gegen_die_praxis_des_gremiums() -> None:
    """A fragt im Rat in der Hälfte seiner Dokumente, alle dort zusammen in 20 von 65.

    Erwartet sind für A also 30 · 20/65, beobachtet 15; B fragt dort nie (0,0). C hat weniger als
    ``MIN_DOCUMENTS`` Dokumente und kein Verhältnis; der gemeinsame Antrag im Ausschuss zählt für
    A und B, in einer Schicht ohne Kontrolle.
    """
    rows = [
        _doc(i, funktion="kontrolle" if i < 15 else "initiative", fraktionen=["A"])
        for i in range(30)
    ]
    rows += [_doc(100 + i, fraktionen=["B"]) for i in range(30)]
    rows += [_doc(200 + i, funktion="kontrolle", fraktionen=["C"]) for i in range(5)]
    rows += [
        _doc(300, funktion="initiative", fraktionen=["A", "B"], gremium="AUS", art="ausschuss")
    ]
    found = {r.key: r for r in fraction_rows(_frame(rows), {"A": "Fraktion A"})}
    assert [r.key for r in fraction_rows(_frame(rows), {})] == ["A", "B", "C"]
    a, b, c = found["A"], found["B"], found["C"]
    assert (a.label, a.documents, a.joint, a.control, a.initiative) == ("Fraktion A", 31, 1, 15, 16)
    assert a.ratio == pytest.approx(15 / (30 * 20 / 65 + 0.0))
    assert b.ratio == 0.0 and b.joint == 1
    assert c.documents < MIN_DOCUMENTS and c.ratio is None


def test_die_zwei_zaehlungen_der_parteien_stehen_mit_zahl_da() -> None:
    """Frage 25: die Hauptseite zählt ``parteien``, diese Seite die Antragsteller."""
    rows = [
        _doc(1, fraktionen=["CDU", "GRUENE"], parteien=["CDU"]),  # Mitantragsteller gefunden
        _doc(2, fraktionen=["SPD"], parteien=["SPD", "GRUENE"]),  # Gegenstand im Titel
        _doc(3, fraktionen=["FDP"], parteien=["CDU"]),
        _doc(4, fraktionen=["FDP"]),
        _doc(5, funktion="vollzug", urheber="Verwaltung"),
    ]
    found = counting_difference(_frame(rows))
    assert (found.documents, found.different, found.more, found.fewer, found.other) == (
        4,
        3,
        1,
        1,
        1,
    )


# --- Abschnitt 3: Matrix -------------------------------------------------------------------------
def test_die_matrix_ist_symmetrisch_und_traegt_das_lager_am_datum(
    default_settings: Settings,
) -> None:
    """Grüne und FDP: im Oktober 2020 beide in der Mehrheit, ab November über die Grenze.

    Die Zelle trägt das häufigere Lager, ``mixed`` nennt beide. Ein Dokument von vier Fraktionen
    über die Grenze ist für das Paar CDU und Grüne „beide in der Mehrheit".
    """
    rows = [
        _doc(1, fraktionen=["GRUENE", "FDP"], day=dt.date(2020, 10, 1)),
        _doc(2, fraktionen=["GRUENE", "FDP"]),
        _doc(3, fraktionen=["GRUENE", "FDP"]),
        _doc(4, fraktionen=["CDU", "GRUENE", "FDP", "Die_Linke"]),
        _doc(5, fraktionen=["CDU", "GRUENE"], gremium="BV1", art="bezirksvertretung"),
    ]
    frame = _frame(rows)
    axis = (("CDU", "CDU"), ("GRUENE", "Grüne"), ("FDP", "FDP"), ("Die_Linke", "Linke"))
    city = cosponsor_matrix(
        frame, axis, key="stadt", kinds=("rat", "ausschuss"), context=_context(default_settings)
    )
    cells = {
        (a, b): city.cells[i][j] for i, (a, _) in enumerate(axis) for j, (b, _) in enumerate(axis)
    }
    green_liberal = cells[("GRUENE", "FDP")]
    assert green_liberal is not None and green_liberal.count == 4
    assert green_liberal.camp == "ueber_grenze"
    assert dict(green_liberal.camps) == {"ueber_grenze": 3, "gemeinsam_mehrheit": 1}
    majority = cells[("CDU", "GRUENE")]
    assert majority is not None and (majority.count, majority.camp) == (1, "gemeinsam_mehrheit")
    assert city.joint == (1, 4, 4, 1) and city.documents == 4 and city.with_camps
    assert [(a, b) for a, b, _ in city.mixed] == [("GRUENE", "FDP")]
    assert (city.label, city.label_dative) == ("Rat und Ausschüsse", "Rat und Ausschüssen")
    districts = cosponsor_matrix(
        frame, axis, key="bezirke", kinds=("bezirksvertretung",), context=None
    )
    assert districts.documents == 1 and not districts.with_camps
    assert all(c is None or c.camp is None for row in districts.cells for c in row)


# --- Abschnitt 4: K3 -----------------------------------------------------------------------------
def test_k3_zaehlt_initiativen_ueber_die_grenze_unter_denen_mit_opposition(
    default_settings: Settings,
) -> None:
    rows = [
        _doc(1, fraktionen=["CDU", "SPD"], lager="ueber_grenze"),
        _doc(2, fraktionen=["SPD"], lager="allein_opposition"),
        _doc(3, fraktionen=["FDP"], lager="allein_opposition"),
        _doc(4, fraktionen=["SPD", "FDP"], lager="gemeinsam_opposition"),
        _doc(5, fraktionen=["CDU"], lager="allein_mehrheit"),
        _doc(6, funktion="kontrolle", fraktionen=["FDP"], lager="allein_opposition"),
        _doc(7, fraktionen=["SPD"], gremium="BV1", art="bezirksvertretung"),
    ]
    labels, parties = labels_of(default_settings)
    found = concordance(
        _frame(rows),
        default_settings,
        labels,
        parties,
        ("Rat und Ausschüsse", "Rat und Ausschüssen"),
    )
    assert found is not None
    assert (found.initiatives.hits, found.initiatives.n) == (1, 4)
    assert (found.all_functions.hits, found.all_functions.n) == (1, 5)
    low, high = found.initiatives.interval
    assert low < 0.25 < high
    assert [d.reference for d in found.across] == ["X/001/2021"]
    assert found.across[0].url == "https://ris.example/downloadfiles/00001.pdf"
    assert [t.period for t in found.majorities] == ["2020-2025"]  # nur die, die im Datensatz gilt


def test_ohne_mehrheit_im_profil_gibt_es_keine_konkordanz() -> None:
    """Mönchengladbach: kein Dokument trägt ein Lager, der Abschnitt sagt, was fehlt."""
    settings = _check_settings(mg_settings())
    rows = [
        _doc(1, fraktionen=["CDU", "SPD"]),
        _doc(2, funktion="vollzug", urheber="Verwaltung", lager="ohne_partei"),
    ]
    model = build_actors(_frame(rows), settings, read_check(settings))
    assert model.concordance is None
    assert any(line.startswith("Ratsmehrheit") for line in model.missing)
    assert not model.matrices[0].with_camps


# --- Die Prüfung aus guete.json --------------------------------------------------------------------
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
    settings = _check_settings(load_settings(profile=profile, cwd=Path("/nonexistent")))
    check = read_check(settings)
    function = _quality()["fragen"]["funktion"]
    assert check.sentence == _quality()["satz"]
    assert (check.agreed, check.units) == (function["einig"], function["n"])
    assert check.same_model  # alle drei Rollen ein Modell (Punkt 87)
    assert check.measured is measured
    assert (check.variant, check.chosen) == ("B", RULE_CHECK.variants["B"])


def _render(
    settings: Settings,
    rows: Sequence[dict[str, Any]],
    *,
    sections: Sequence[tuple[PageSection, dict[str, object]]] = (),
    env: Environment | None = None,
) -> str:
    model = build_actors(_frame(rows), settings, read_check(settings))
    urls = frozenset(f"https://ris.example/downloadfiles/{n:05d}.pdf" for n in range(400))
    nowhere = Path("/nonexistent")
    allowed = urls | actors_links(Layout(nowhere, nowhere, nowhere), settings)
    return render_page(
        page_frame(settings, now=NOW, commit=None),
        PAGE,
        page_data(model, settings),
        allowed,
        env=env,
        sections=sections,
    )


ROWS = [
    _doc(1, funktion="vollzug", urheber="Verwaltung", lager="ohne_partei"),
    _doc(2, funktion="kontrolle", fraktionen=["SPD"], lager="allein_opposition"),
    _doc(3, fraktionen=["CDU", "GRUENE"], lager="gemeinsam_mehrheit"),
    _doc(4, fraktionen=["CDU", "SPD"], lager="ueber_grenze"),
    _doc(5, funktion="erklaerung", fraktionen=["GRUENE"], lager="allein_mehrheit"),
]


def test_eine_geaenderte_guete_json_aendert_die_seite(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Satz, Übereinstimmung und „schwacher Beleg" hängen an der Datei, nicht an der Vorlage."""
    folder = tmp_path / VALIDATION_PROJECT
    folder.mkdir()
    source = REPO / "validierung" / VALIDATION_PROJECT
    shutil.copy(source / "stichprobe.json", folder / "stichprobe.json")
    shutil.copy(source / "codebuch.toml", folder / "codebuch.toml")
    quality = _quality()
    original = _render(_check_settings(default_settings), ROWS)
    assert quality["satz"] in original and "schwacher Beleg" in original
    assert "in 149 von 150 überein" in original
    quality["satz"] = (
        "geprüft von zwei KI-Kodierern (modell-a und modell-b) an 150 Dokumenten, nicht von Menschen"
    )
    quality["modelle"]["kodierer_b"] = "modell-b"
    quality["fragen"]["funktion"]["einig"] = 141
    (folder / "guete.json").write_text(json.dumps(quality), encoding="utf-8")
    changed = _render(_check_settings(default_settings, tmp_path), ROWS)
    assert quality["satz"] in changed and _quality()["satz"] not in changed
    assert "in 141 von 150 überein" in changed
    assert "schwacher Beleg" not in changed


def test_der_pruefsatz_nennt_die_zahlen_der_messung(default_settings: Settings) -> None:
    """Messdokument § 7: κ mit Intervall, die nicht gewählte Variante, 119/119, 119/138."""
    page = _render(_check_settings(default_settings), ROWS)
    box = page[
        page.index('<div class="pruefung"') : page.index(
            "</div>", page.index('<div class="pruefung"')
        )
    ]
    assert "in 125 mit ihnen überein, κ = 0,91 (95-%-Intervall 0,84–0,96; Variante B)" in box
    assert "Variante A, κ = 0,83 (0,75–0,90)" in box
    assert "119 von 119 genannten Fraktionen bestätigt, 119 von 138 gefunden" in box


# --- Die Seite: Abschnitte, explorativ, Gäste -----------------------------------------------------
SECTIONS = ("ueberblick", "funktionen", "fraktionen", "wer-mit-wem", "konkordanz", "erklaerungen")


def _headings(page: str) -> dict[str, str]:
    found = {}
    for name in SECTIONS[1:]:
        start = page.index(f'<section id="{name}">')
        heading = re.search(r"<h2>(.*?)</h2>", page[start:])
        assert heading is not None
        found[name] = heading.group(1)
    return found


def test_jeder_abschnitt_steht_einmal_und_explorativ_wo_es_verlangt_ist(
    default_settings: Settings,
) -> None:
    page = _render(_check_settings(default_settings), ROWS)
    for name in SECTIONS:
        assert page.count(f'<section id="{name}">') == 1
    headings = _headings(page)
    assert headings["fraktionen"].endswith("(explorativ)")
    assert headings["konkordanz"].endswith("(explorativ)")
    assert not headings["funktionen"].endswith("(explorativ)")  # gemessen
    assert "beob./erw." in page and "unter 30" in page


def test_ein_nicht_gemessener_datensatz_ist_ueberall_explorativ() -> None:
    settings = _check_settings(mg_settings())
    page = _render(
        settings,
        [_doc(1, fraktionen=["CDU", "SPD"]), _doc(2, funktion="vollzug", urheber="Verwaltung")],
    )
    assert all(h.endswith("(explorativ)") or h == "Konkordanz" for h in _headings(page).values())
    assert "nicht an diesem Datensatz" in page
    assert "Dieses Profil nennt keine Ratsmehrheit" in page


def test_der_link_auf_die_abstimmungen_steht_nur_mit_dem_gast(default_settings: Settings) -> None:
    """Vorhaben 28 hängt ``abstimmungen`` an (Punkt 86); bis dahin sagt die Seite, dass es fehlt."""
    settings = _check_settings(default_settings)
    without = _render(settings, ROWS)
    assert 'href="#abstimmungen"' not in without and "noch nicht auf dieser Seite" in without
    env = environment()
    assert env.loader is not None
    env.loader = ChoiceLoader(
        [
            DictLoader(
                {"pages/akteure/abstimmungen.html.j2": "{% if data.n %}<p>n</p>{% endif %}"}
            ),
            env.loader,
        ]
    )
    guest = PageSection(
        "akteure", "abstimmungen", 10, inputs=lambda layout, s: (), data=lambda layout, s: {"n": 1}
    )
    with_guest = _render(settings, ROWS, sections=((guest, {"n": 1}),), env=env)
    assert 'href="#abstimmungen"' in with_guest and '<section id="abstimmungen">' in with_guest


def test_die_vorlage_nennt_keine_partei() -> None:
    """Für alle Fraktionen gleich gebaut: jeder Name kommt aus dem Profil, keiner aus der Vorlage."""
    names = set()
    for profile in ("duesseldorf", "moenchengladbach"):
        settings = load_settings(profile=profile, cwd=Path("/nonexistent"))
        for party in (*settings.originators.parties, *settings.originators.groups):
            names |= {party.key, party.label, party.short}
    folder = REPO / "src" / "georep" / "report" / "templates" / "pages"
    text = "".join(p.read_text(encoding="utf-8") for p in sorted(folder.rglob("akteure*")))
    found = sorted(n for n in names if n and re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text))
    assert found == []


# --- Register, Linkblock, Downloads, Größe auf der Mini-Fixture ----------------------------------
def test_die_seite_steht_im_register_und_auf_der_hauptseite(mini_run: Layout) -> None:
    page = (mini_run.site / "akteure.html").read_text(encoding="utf-8")
    index = mini_run.site_index.read_text(encoding="utf-8")
    weitere = index[index.index('<section id="weitere">') :]
    assert '<a href="akteure.html">Akteure: Funktionen und gemeinsame Anträge</a>' in weitere
    assert len(page.encode("utf-8")) < PAGE_BUDGET
    for name in SECTIONS:
        assert page.count(f'<section id="{name}">') == 1


def test_die_beiden_tabellen_stehen_als_download_mit_spaltendoku(
    mini_run: Layout, default_settings: Settings
) -> None:
    names = {t.name for t in published(mini_run, default_settings)}
    assert {"dokumente_funktion", "dokumente_antragsteller"} <= names
    schema = json.loads((mini_run.site_data / "schema.json").read_text(encoding="utf-8"))
    for table in TABLES:
        assert (mini_run.site_data / f"{table.name}.csv").is_file()
        assert (mini_run.site_data / f"{table.name}.parquet").is_file()
        # jede Spalte beschrieben, keine Beschreibung zu viel, in der Folge der Datei
        columns = list(pl.read_parquet_schema(table.path(mini_run)))
        assert columns == list(table.columns)
        described = {c["column"]: c["description"] for c in schema["tables"][table.name]}
        assert described == {name: doc[0] for name, doc in table.columns.items()}


def test_der_bericht_liest_die_tabellen_der_beitraege_mit(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Ändert sich eine Tabelle von 15, ist der Stamp von ``report`` nicht mehr aktuell."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    report = next(s for s in build_steps(default_settings, layout) if s.name == "report")
    files = functions_files(layout)
    assert {files.functions, files.cosponsors} <= set(report.optional)


def test_die_seite_darf_die_pdf_dateien_ihres_korpus_verlinken(
    mini_run: Layout, default_settings: Settings
) -> None:

    allowed = actors_links(mini_run, default_settings)
    urls = pl.read_parquet(mini_run.corpus, columns=["download_url"]).get_column("download_url")
    first = next(u for u in urls.to_list() if u)
    assert first.replace("http://", "https://", 1) in allowed
    assert any(link.endswith("/docs/plans/15-funktion.md") for link in allowed)


def test_jede_spalte_der_seite_ist_da(default_settings: Settings) -> None:
    """``build_actors`` verlangt seine Spalten und sagt, welche fehlen."""
    from georep.errors import SchemaError

    frame = _frame(ROWS).drop("lager")
    with pytest.raises(SchemaError, match="lager"):
        build_actors(frame, default_settings, read_check(_check_settings(default_settings)))
    assert "lager" in DOCUMENT_COLUMNS


# --- Konrad, 2026-11-27: „Erklärung oder Appell", nicht „Symbolpolitik" -------------------------
WORD = re.compile("symbol", re.IGNORECASE)


def test_kein_leser_sieht_das_wort_symbol(mini_run: Layout) -> None:
    """Die Klasse heißt auf der Seite „Erklärung oder Appell", in den Daten ``erklaerung``.

    Geprüft werden die gebaute Unterseite, die Hauptseite (Downloads und Spaltenschema),
    ``schema.json`` und die beiden Tabellen als CSV.
    """
    files = [
        mini_run.site / "akteure.html",
        mini_run.site_index,
        mini_run.site_data / "schema.json",
        *(mini_run.site_data / f"{table.name}.csv" for table in TABLES),
    ]
    found = {path.name: WORD.findall(path.read_text(encoding="utf-8")) for path in files}
    assert {name: hits for name, hits in found.items() if hits} == {}


def test_die_vorlagen_nennen_das_wort_symbol_nicht() -> None:
    folder = REPO / "src" / "georep" / "report" / "templates" / "pages"
    found = sorted(
        p.name for p in folder.rglob("akteure*") if WORD.search(p.read_text(encoding="utf-8"))
    )
    assert found == []


def test_die_seite_nennt_die_definition_aus_dem_codebuch(default_settings: Settings) -> None:
    """Die Definition steht wörtlich da; im Codebuch heißt die Klasse noch ``symbol``."""
    from georep.validation.codebook import load_codebook

    folder = REPO / "validierung" / VALIDATION_PROJECT
    codebook = load_codebook(folder / "codebuch.toml", VALIDATION_PROJECT)
    option = next(o for o in codebook.question("funktion").options if o.value == "symbol")
    page = _render(_check_settings(default_settings), ROWS)
    assert option.definition.strip() in page.replace("&#34;", '"').replace("&#39;", "'")
    assert "Erklärung oder Appell" in page and "Erklärung/Appell" in page


# --- Review Runde 2 (2026-11-27) -------------------------------------------------------------------
def test_ohne_javascript_ist_der_umschalter_nicht_zu_sehen(default_settings: Settings) -> None:
    """K1: ``fieldset { display: inline-flex }`` im Rahmen schlägt ``[hidden]``; die Seite hebt es auf."""
    page = _render(_check_settings(default_settings), ROWS)
    assert '<fieldset class="matrix-ebene" id="matrix-ebene" hidden>' in page
    assert "fieldset.matrix-ebene[hidden] { display: none; }" in page


def test_jede_gefaerbte_zelle_traegt_ein_sichtbares_kuerzel(default_settings: Settings) -> None:
    """K2: die Tönungen sind unter Rot-Grün-Schwäche nicht sicher zu trennen; das Kürzel trägt."""
    page = _render(_check_settings(default_settings), ROWS)
    cells = re.findall(r'<td class="num lager-([a-z_]+)"[^>]*>(.*?)</td>', page)
    assert cells  # CDU und Grüne beide in der Mehrheit, CDU und SPD über die Grenze
    short = {"gemeinsam_mehrheit": "M", "ueber_grenze": "Ü", "gemeinsam_opposition": "O"}
    for camp, inner in cells:
        assert f'<span class="lager-kuerzel" aria-hidden="true">{short[camp]}</span>' in inner
    legend = page[page.index('<ul class="fn-legend lager-legende">') :]
    legend = legend[: legend.index("</ul>")]
    for camp, letter in short.items():
        assert f'<span class="lager-kuerzel">{letter}</span>' in legend and camp in legend


def test_in_einer_laufenden_periode_ist_ein_kleines_k3_noch_kein_befund(
    default_settings: Settings,
) -> None:
    """K3 (Plan 15, § 9.11): die Seite nennt n und „laufend"."""
    closed = _render(_check_settings(default_settings), ROWS)
    assert "läuft noch" not in closed
    period = default_settings.period.model_copy(
        update={"end": None, "election": default_settings.period.election_day}
    )
    running = _render(_check_settings(default_settings.model_copy(update={"period": period})), ROWS)
    konkordanz = running[running.index('<section id="konkordanz">') :]
    assert "Die Periode läuft noch" in konkordanz[: konkordanz.index("</section>")]


def _party_names() -> set[str]:
    names: set[str] = set()
    for profile in ("duesseldorf", "moenchengladbach"):
        settings = load_settings(profile=profile, cwd=Path("/nonexistent"))
        for party in (*settings.originators.parties, *settings.originators.groups):
            names |= {n for n in (party.key, party.label, party.short) if n}
        names |= {f.key for f in settings.functions.fractions}
    return names


def _named(text: str) -> list[str]:
    return sorted(
        n for n in _party_names() if re.search(rf"(?<![\w+]){re.escape(n)}(?![\w+])", text)
    )


def test_kein_parteiname_im_text_der_seite_und_des_schemas() -> None:
    """K4: Namen kommen nur aus den Daten. Gerendert mit neutralen Fraktionen und ohne Mehrheit
    bleibt keiner übrig; die Spaltendoku der beiden Tabellen nennt auch keinen."""
    settings = _check_settings(mg_settings())
    rows = [
        _doc(1, fraktionen=["F1", "F2"], parteien=[]),
        _doc(2, funktion="kontrolle", fraktionen=["F1"], parteien=[]),
        _doc(3, funktion="erklaerung", fraktionen=["F2"], parteien=[]),
        _doc(4, funktion="vollzug", urheber="Verwaltung", lager="ohne_partei"),
    ]
    assert _named(_render(settings, rows)) == []
    docs = " ".join(doc[0] for table in TABLES for doc in table.columns.values())
    assert _named(docs + " ".join(t.description for t in TABLES)) == []


@pytest.mark.parametrize(
    ("key", "value"), [("codebuch_version", "2026-12-01.2"), ("einheiten", 151)]
)
def test_rule_check_gilt_nur_fuer_die_messung_aus_guete_json(
    tmp_path: Path, default_settings: Settings, key: str, value: object
) -> None:
    """N1: eine neue Kodierung (anderes Codebuch, andere Stichprobe) macht ``RULE_CHECK`` ungültig."""
    from georep.errors import SchemaError

    folder = tmp_path / VALIDATION_PROJECT
    folder.mkdir()
    source = REPO / "validierung" / VALIDATION_PROJECT
    for name in ("stichprobe.json", "codebuch.toml"):
        shutil.copy(source / name, folder / name)
    quality = _quality() | {key: value}
    (folder / "guete.json").write_text(json.dumps(quality), encoding="utf-8")
    with pytest.raises(SchemaError, match="RULE_CHECK"):
        read_check(_check_settings(default_settings, tmp_path))
    assert RULE_CHECK.codebook_version == _quality()["codebuch_version"]
    assert RULE_CHECK.units == _quality()["einheiten"]


def test_eine_partei_neben_ihrer_spaeteren_fraktion_ist_erklaert(
    default_settings: Settings,
) -> None:
    """N2: „SPD" neben „SPD/Volt" sind die Fraktion des alten Rates und die ab ``valid_from``."""
    rows = [
        _doc(10, funktion="kontrolle", fraktionen=["SPD"], day=dt.date(2020, 10, 1)),
        _doc(11, funktion="kontrolle", fraktionen=["SPD+VOLT"]),
        _doc(12, fraktionen=["CDU", "GRUENE"], lager="gemeinsam_mehrheit"),
    ]
    page = _render(_check_settings(default_settings), rows)
    section = page[page.index('<section id="fraktionen">') :]
    section = section[: section.index("</section>")]
    assert "SPD und SPD/Volt stehen in zwei Zeilen" in section
    assert "ab 01.11.2020" in section


def test_der_rohe_kontrollanteil_ist_keine_rangfolge(default_settings: Settings) -> None:
    """N3 (Frage 14: je Fraktion nur standardisiert): „Kontrolle roh" steht daneben, sortiert nicht."""
    page = _render(_check_settings(default_settings), ROWS)
    assert '<th scope="col" class="num">Kontrolle roh</th>' in page
    assert '<th scope="col" class="num" data-sort="num">beob./erw.</th>' in page


def test_listen_nennen_gremien_beim_namen_und_keine_profilnamen() -> None:
    """N5: Gremium mit Namen aus ``[bodies]``, „Fraktion nicht erkannt" statt „Fraktionen", und der
    Prüfsatz nennt Stadt und Periode der Stichprobe, keine Profilnamen."""
    settings = _check_settings(mg_settings())
    council, name = next(iter(settings.bodies.council.items()))
    rows = [
        _doc(1, funktion="erklaerung", fraktionen=["CDU"], gremium=council),
        _doc(2, funktion="erklaerung", fraktionen=[], parteien=[], gremium="XYZ", art="unbekannt"),
        _doc(3, funktion="vollzug", urheber="Verwaltung", lager="ohne_partei"),
    ]
    page = _render(settings, rows)
    listing = page[page.index('<table id="erklaerungen-liste"') :]
    listing = listing[: listing.index("</table>")]
    assert f"<td>{name}</td>" in listing and "<td>XYZ</td>" in listing
    assert "<td>Fraktion nicht erkannt</td>" in listing and "<td>Fraktionen</td>" not in listing
    box = page[page.index('<div class="pruefung"') :]
    box = box[: box.index("</div>")]
    assert "duesseldorf" not in box and "Wahlperiode 2014 bis 2020" in box
