"""Die Downloads von Vorhaben 11 und 12 (Stufe 3; Messdokumente ``11-struktur.md``, ``12-kennungen.md``, § 7).

Vier Gruppen. **Kein Personenname**: die Sichten leeren einen Freitext oder lassen eine Spanne
weg, in der hinter einem Titel ein Name beginnt, und ``dokumente_kopf`` trägt keinen Unterzeichner;
ein Lauf mit erfundenen Rohtexten, in deren Kopf Namen stehen, veröffentlicht keinen davon.
**Spaltendoku**: jede veröffentlichte Spalte beschrieben, keine Beschreibung zu viel, in der Folge
der Datei, auch in ``schema.json``. **Wo und wie groß**: nur in einem gemessenen Datensatz mit
Rohtext, die CSV von ``kennungen`` nur mit Bauleitplanung und Beträgen, keine von
``dokumente_kopf``; ohne Rohtext (die Mini-Fixture) bleibt die Seite ohne Zeile und Absatz. **Der
Prüfsatz** kommt aus ``guete.json``: eine geänderte Datei ändert ihn, eine andere Kodierung bricht ab.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from georep.enrich.identifiers import (
    CSV_KINDS,
    IDENTIFIER_CHECKS,
    identifiers_files,
    spans_sentence,
    spans_view,
)
from georep.enrich.identifiers import TABLES as IDENTIFIER_TABLES
from georep.enrich.sections import HEAD_CHECK, WITHHELD, head_sentence, head_view, sections_files
from georep.enrich.sections import TABLES as HEAD_TABLES
from georep.errors import MissingInputError, SchemaError
from georep.export import export_csv
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.identifiers import EXTRA
from georep.prep.structure import HEAD_SCHEMA
from georep.report.downloads import Measure, has_extracted_rows, measured, named, names_in
from georep.report.tables import csv_plan, published
from georep.settings import Settings, UnknownProfileError, load_settings
from georep.spans import SPAN_SCHEMA
from georep.stores import RawTextStore
from tests.conftest import REPO

[HEAD] = HEAD_TABLES
[SPANS] = IDENTIFIER_TABLES
NOWHERE = Path("/nonexistent")
NAMES = ("Henrike", "Vogelsang", "Bruno", "Quasthoff", "Fraktionsvorsitzender")
SPAN_COLUMNS = {**SPAN_SCHEMA, **EXTRA}  # kennungen.parquet: F3 und attr dahinter
LINE_BUDGET = 1_000  # docs/plan-zeigen-2026-11.md, § 5: je Zeile unter 1 KB auf index.html

# Ein Vorlagenkopf, in dem das Feld der Dezernentin in die Amtszeile läuft (wie viermal in der
# Hauptperiode), und ein Antrag mit Unterschrift; erfunden, keine echten Namen
VORLAGE = """Betrifft: Neubau eines Radwegs

Fachbereich: 66 - Amt für Verkehrsmanagement Dezernentin/Dezernent: Beigeordnete Henrike Vogelsang
Beratungsfolge:
Gremium Sitzungsdatum Beratungsqualität
Rat 09.11.2023 Entscheidung
Beschlussdarstellung:
Der Rat beschließt den Neubau nach dem Bebauungsplan Nr. 5674/026 für 250.000 Euro.
Sachdarstellung:
Der Radweg schließt eine Lücke. Baubeginn ist am 30.08.2024, zuständig ist das Amt 66.
"""
ANTRAG = """Antrag zur Sitzung des Rates am 09.11.2023

Betrifft: Mehr Bänke im Park

Antrag:
Der Rat beschließt, zehn Bänke für 12.000 Euro aufzustellen.

Mit freundlichen Grüßen
Bruno Quasthoff
Fraktionsvorsitzender
"""


def _settings(settings: Settings, root: Path = REPO / "validierung") -> Settings:
    """Die Settings mit dem Ordner der Validierung im Repo, unabhängig vom Arbeitsverzeichnis."""
    return settings.model_copy(
        update={"validation": settings.validation.model_copy(update={"root": root})}
    )


@pytest.fixture(scope="module")
def raw_run(
    mini_run: Layout, default_settings: Settings, tmp_path_factory: pytest.TempPathFactory
) -> Layout:
    """Die Mini-Kette mit zwei erfundenen Rohtexten: ``sections``, ``identifiers``, ``report``.

    Die Mini-Fixture hat keinen Rohtext; eine Kopie ihres Laufs bekommt ihn für zwei Dokumente,
    und nur die drei Schritte, die ihn lesen oder zeigen, laufen neu.
    """
    root = tmp_path_factory.mktemp("rohtext_lauf")
    shutil.copytree(mini_run.data_root, root / "data")
    shutil.copytree(mini_run.cache_root, root / "cache")
    layout = Layout(
        root / "data",
        root / "cache",
        mini_run.reference_root,
        default_settings.profile,
        context_root=mini_run.context_root,
    )
    names = pl.read_parquet(layout.corpus, columns=["file_name"]).get_column("file_name")
    first, second = [n for n in names.to_list() if n][:2]
    store = RawTextStore(layout.raw_texts)
    store.put(first, VORLAGE, pages=1, extractor="pypdf-7.1.0+roh", pdf_sha256="0" * 64)
    store.put(second, ANTRAG, pages=1, extractor="pypdf-7.1.0+roh", pdf_sha256="1" * 64)
    store.save()
    settings = _settings(default_settings)
    outcomes = run_pipeline(
        build_steps(settings, layout), settings, ["sections", "identifiers", "report"]
    )
    assert [o.status for o in outcomes] == ["ausgeführt"] * 3, [o.line() for o in outcomes]
    return layout


# --- Kein Personenname ----------------------------------------------------------------------------
def _downloads_section(page: str) -> str:
    """Der Abschnitt „Downloads" mit Zeilen, Prüfsätzen und Spaltenschema, nicht die ganze Seite."""
    start = page.index('<section id="downloads">')
    return page[start : page.index("</section>", start)]


def _published_text(layout: Layout) -> str:
    """Alles, was der Lauf zu den beiden Tabellen veröffentlicht, als ein Text."""
    data = layout.site_data
    parts = [
        pl.read_parquet(data / "dokumente_kopf.parquet").write_json(),
        pl.read_parquet(data / "kennungen.parquet").write_json(),
        (data / "kennungen.csv").read_text(encoding="utf-8"),
        (data / "schema.json").read_text(encoding="utf-8"),
        _downloads_section(layout.site_details.read_text(encoding="utf-8")),
    ]
    return "\n".join(parts)


def test_kein_name_aus_den_rohtexten_steht_in_einem_download(raw_run: Layout) -> None:
    head = pl.read_parquet(sections_files(raw_run).head)
    # im Kopf der Kette stehen die Namen noch: der Kopf läuft in das Feld der Dezernentin, und
    # der Unterschriftsblock nennt die Rolle des Unterzeichners
    assert head.filter(pl.col("amt_name").str.contains("Vogelsang")).height == 1
    assert "Fraktionsvorsitzender" in head.get_column("unterzeichner_rolle").to_list()
    # und das Kopffeld des Amts von 12 nimmt die ganze Zeile
    spans = pl.read_parquet(identifiers_files(raw_run).spans)
    assert spans.filter(pl.col("value").str.contains("Vogelsang")).height == 1
    published_text = _published_text(raw_run)
    assert [name for name in NAMES if name in published_text] == []
    columns = pl.read_parquet_schema(raw_run.site_data / "dokumente_kopf.parquet")
    assert not set(WITHHELD) & set(columns)


def test_die_sicht_des_kopfs_leert_werte_mit_namen_und_laesst_die_amtsbezeichnung(
    default_settings: Settings,
) -> None:
    rows = [
        {"id": "1", "amt_name": "Kulturamt Dezernentin/Dezernent: Beigeordneter Hans Muster"},
        {
            "id": "2",
            "amt_name": "AmtfürGebäudemanagement Dezernentin/Dezernent: StadtkämmerinEvaMuster",
        },
        {"id": "3", "amt_name": "Rechnungsprüfungsamt Amtsleiterin: Frau Muster"},
        {"id": "4", "amt_name": "Bauaufsichtsamt Dezernentin: Muster"},
        {"id": "5", "amt_name": "Büro Oberbürgermeister", "dezernat_titel": "Stadtkämmerin"},
        {
            "id": "6",
            "amt_name": "Stadtdirektor und Dezernat für Jugend, Schule, Soziales und Sport",
        },
        {
            "id": "7",
            "sitzung_gremium": "Herrn Muster",
            "beratungsfolge": [{"gremium": "Rat"}, {"gremium": "Frau Muster BV 3"}],
            "unterzeichner_rolle": "Ratsherr",
        },
    ]
    frame = pl.DataFrame(rows, schema=HEAD_SCHEMA)
    view = head_view(frame, default_settings)
    assert view.columns == [c for c in HEAD_SCHEMA if c not in WITHHELD]
    assert view.get_column("amt_name").to_list() == [
        None,
        None,
        None,
        None,
        "Büro Oberbürgermeister",
        "Stadtdirektor und Dezernat für Jugend, Schule, Soziales und Sport",
        None,
    ]
    assert view.get_column("dezernat_titel").to_list()[4] == "Stadtkämmerin"
    last = view.row(6, named=True)
    assert last["sitzung_gremium"] is None
    assert [r["gremium"] for r in last["beratungsfolge"]] == ["Rat", None]
    assert names_in(view, named(default_settings)) == []


def test_die_sicht_der_kennungen_laesst_spannen_mit_namen_weg(default_settings: Settings) -> None:
    """In 2014 bis 2020 nennen 13 Spannen der Ämter eine Person („Beigeordnete …")."""
    rows = [
        ("1", 0, 6, "amt", "Amt 66", "66", "", "kennungen-1/x", "nummer"),
        (
            "1",
            10,
            30,
            "amt",
            "Beigeordnete Muster",
            "Beigeordnete Muster",
            "",
            "kennungen-1/x",
            "kopf",
        ),
        ("1", 40, 60, "amt", "Büro Oberbürgermeister", "01", "", "kennungen-1/x", "name"),
        ("1", 70, 80, "betrag", "5.000 Euro", "5000.00", "", "kennungen-1/x", None),
    ]
    frame = pl.DataFrame(rows, schema=SPAN_COLUMNS, orient="row")
    view = spans_view(frame, default_settings)
    assert view.get_column("value").to_list() == ["Amt 66", "Büro Oberbürgermeister", "5.000 Euro"]
    assert view.schema == frame.schema


# --- Spaltendoku ------------------------------------------------------------------------------------
def test_jede_veroeffentlichte_spalte_ist_beschrieben(default_settings: Settings) -> None:
    """Beide Richtungen und die Folge, an der Sicht einer leeren Tabelle (ohne Rohtext)."""
    for table, schema in ((HEAD, HEAD_SCHEMA), (SPANS, SPAN_COLUMNS)):
        view = table.published_frame(pl.DataFrame(schema=schema), default_settings)
        docs = table.column_docs(default_settings)
        assert list(docs) == view.columns, table.name
        assert all(text for text, _ in docs.values()), table.name


def test_schema_json_beschreibt_die_sichten(raw_run: Layout, default_settings: Settings) -> None:
    schema = json.loads((raw_run.site_data / "schema.json").read_text(encoding="utf-8"))
    for table in (HEAD, SPANS):
        written = pl.read_parquet_schema(raw_run.site_data / table.path(raw_run).name)
        described = {c["column"]: c["description"] for c in schema["tables"][table.name]}
        docs = table.column_docs(default_settings)
        assert list(described) == list(written) == list(docs)
        assert described == {name: doc[0] for name, doc in docs.items()}
    # docs/todo.md, Punkt 14 (e): sitzung_gremium mischt Profilnamen und die Form wie im Text
    gremium = HEAD.column_docs(default_settings)["sitzung_gremium"][0]
    assert "aus dem Profil" in gremium and "wie im Text" in gremium


# --- Wo, welche Dateien, wie groß ------------------------------------------------------------------
@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("duesseldorf", True),
        ("duesseldorf-vergleich", True),  # rechnet im Ordner der Hauptperiode
        ("duesseldorf-2014", False),
        ("duesseldorf-2025", False),
        ("moenchengladbach", False),
    ],
)
def test_nur_ein_gemessener_datensatz_bekommt_die_downloads(profile: str, expected: bool) -> None:
    settings = _settings(load_settings(profile=profile, cwd=NOWHERE))
    projects = [HEAD_CHECK.project, *(c.project for c in IDENTIFIER_CHECKS)]
    assert [measured(settings, p) for p in projects] == [expected] * 3


def test_ohne_rohtext_keine_zeile_und_kein_absatz(
    mini_run: Layout, default_settings: Settings
) -> None:
    """Die Mini-Fixture hat keinen Rohtext: die Tabellen sind leer und stehen nicht auf der Seite."""
    for table in (HEAD, SPANS):
        assert table.path(mini_run).is_file()
        assert not has_extracted_rows(table.path(mini_run))
        assert not (mini_run.site_data / table.path(mini_run).name).exists()
    names = {t.name for t in published(mini_run, _settings(default_settings))}
    assert not {"dokumente_kopf", "kennungen"} & names
    page = mini_run.site_details.read_text(encoding="utf-8")
    assert "dokumente_kopf" not in page and "kennungen" not in page


def test_mit_rohtext_parquet_und_die_csv_der_plaene_und_betraege(raw_run: Layout) -> None:
    data = raw_run.site_data
    assert (data / "dokumente_kopf.parquet").is_file() and not (
        data / "dokumente_kopf.csv"
    ).exists()
    spans = pl.read_parquet(identifiers_files(raw_run).spans)
    csv = pl.read_csv(data / "kennungen.csv", infer_schema=False)
    assert sorted(set(csv.get_column("kind"))) == sorted(
        set(spans.get_column("kind")) & set(CSV_KINDS)
    )
    assert {"termin", "amt"} <= set(spans.get_column("kind")) - set(csv.get_column("kind"))
    assert csv.columns == pl.read_parquet(data / "kennungen.parquet").columns
    page = raw_run.site_details.read_text(encoding="utf-8")
    rows = [line for line in page.splitlines() if '<a href="data/dokumente_kopf' in line]
    rows += [line for line in page.splitlines() if '<a href="data/kennungen' in line]
    assert len(rows) == 3
    assert all(len(row.encode("utf-8")) < LINE_BUDGET for row in rows)
    assert "(nur Bebauungspläne, FNP-Änderungen und Beträge)" in rows[2]


def test_export_laesst_den_kopf_ohne_csv_aus(raw_run: Layout, tmp_path: Path) -> None:
    """Eine Liste von Strukturen hat keine CSV-Form; ``georep export`` bricht nicht an ihr ab."""
    assert HEAD.path(raw_run) not in {parquet for parquet, _, _ in csv_plan(raw_run)}
    copy = tmp_path / "data"
    shutil.copytree(raw_run.root, copy / raw_run.root.name)
    layout = Layout(copy, tmp_path / "cache", raw_run.reference_root, raw_run.profile)
    written = export_csv(layout)
    assert identifiers_files(layout).spans.with_suffix(".csv") in written
    assert not sections_files(layout).head.with_suffix(".csv").exists()


def test_der_bericht_liest_die_pruefung_mit(tmp_path: Path, default_settings: Settings) -> None:
    """guete.json und stichprobe.json beider Vorhaben stehen im Stamp von ``report``."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "reference")
    settings = _settings(default_settings)
    report = next(s for s in build_steps(settings, layout) if s.name == "report")
    root = settings.validation.root
    for project in ("11-struktur-f4", "12-kennungen-f4", "12-kennungen-2-f4"):
        assert {root / project / "guete.json", root / project / "stichprobe.json"} <= set(
            report.inputs
        )
    assert {HEAD.path(layout), SPANS.path(layout)} <= set(report.optional)


# --- Der Prüfsatz ---------------------------------------------------------------------------------
def _quality(project: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (REPO / "validierung" / project / "guete.json").read_text(encoding="utf-8")
    )
    return data


def test_der_pruefsatz_steht_unter_den_downloads(raw_run: Layout) -> None:
    page = raw_run.site_details.read_text(encoding="utf-8")
    downloads = page[page.index('<section id="downloads">') : page.index("<h3>Spaltenschema</h3>")]
    satz = _quality("11-struktur-f4")["satz"]
    assert f"<code>dokumente_kopf</code>: {satz[0].upper()}{satz[1:]}" in downloads
    for project in ("12-kennungen-f4", "12-kennungen-2-f4"):
        assert _quality(project)["satz"] in downloads
    notes = [line for line in downloads.splitlines() if line.startswith('<p class="note"><code>')]
    assert len(notes) == 2 and all(len(n.encode("utf-8")) < LINE_BUDGET for n in notes)


def test_der_pruefsatz_des_kopfs_nennt_die_zahlen_der_messung(default_settings: Settings) -> None:
    """Messdokument 11, § 4.1: 188 von 200 zeilengenau (0,898–0,965), die Kopffelder mit Intervall."""
    sentence = head_sentence(_settings(default_settings))
    assert sentence.startswith("Geprüft von zwei KI-Kodierern desselben Modells (claude-opus-5-5)")
    assert "nicht von Menschen, geschlichtet von demselben Modell." in sentence
    for part in (
        "Beschlussvorschlag zeilengenau 188 von 200 (0,898–0,965)",
        "Amt 125 von 125 (0,970–1,000)",
        "Amtsbezeichnung 69 von 69 (0,947–1,000)",
        "Zeilen der Beratungsfolge 160 von 168 (0,909–0,976)",
        "Briefdatum 73 von 73 (0,950–1,000)",
        "Datum der Sitzung 48 von 48 (0,926–1,000)",
    ):
        assert part in sentence


def test_der_pruefsatz_der_kennungen_nennt_nur_die_praezision(default_settings: Settings) -> None:
    """Messdokument 12, § 4.1 und § 4.4; der Recall gehört nicht zu dieser Phase."""
    sentence = spans_sentence(_settings(default_settings))
    for part in (
        "Bauleitplanung 1,000 (0,957–1,000; n 100)",
        "Betrag 0,962 (0,885–0,988; n 100)",
        "Termin 1,000 (0,726–1,000; n 30)",
        "Verwaltungseinheit 0,956 (0,851–0,988; n 100)",
        "an 600 Textstellen, nicht von Menschen",
        "an 360 Textstellen, nicht von Menschen",
        "Beträge tragen keine Rolle",
        "Termine keine Frist",
    ):
        assert part in sentence
    assert "Recall" not in sentence and "Vollständigkeit" not in sentence


def test_eine_geaenderte_guete_json_aendert_den_pruefsatz(
    tmp_path: Path, default_settings: Settings
) -> None:
    for project in ("11-struktur-f4", "12-kennungen-f4", "12-kennungen-2-f4"):
        shutil.copytree(REPO / "validierung" / project, tmp_path / project)
    quality = _quality("11-struktur-f4")
    quality["satz"] = (
        "geprüft von zwei KI-Kodierern (modell-a und modell-b) an 200 Dokumenten, nicht von Menschen"
    )
    quality["modelle"]["kodierer_b"] = "modell-b"
    (tmp_path / "11-struktur-f4" / "guete.json").write_text(json.dumps(quality), encoding="utf-8")
    sentence = head_sentence(_settings(default_settings, tmp_path))
    assert sentence.startswith("Geprüft von zwei KI-Kodierern (modell-a und modell-b) an 200")
    assert "geschlichtet von demselben Modell" not in sentence


def test_eine_andere_kodierung_bricht_den_pruefsatz_ab(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Wie ``RULE_CHECK`` von 15: neue Labels machen die Zahlen ungültig, bis sie nachgerechnet sind."""
    for project in ("12-kennungen-f4", "12-kennungen-2-f4"):
        shutil.copytree(REPO / "validierung" / project, tmp_path / project)
    quality = _quality("12-kennungen-2-f4")
    quality["einheiten"] = 361
    (tmp_path / "12-kennungen-2-f4" / "guete.json").write_text(
        json.dumps(quality), encoding="utf-8"
    )
    with pytest.raises(SchemaError, match="nachzurechnen"):
        spans_sentence(_settings(default_settings, tmp_path))


def test_fehlende_oder_unvollstaendige_pruefdateien_sind_fehler(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Ohne ``stichprobe.json`` oder ``guete.json`` gibt es keinen Download, sondern eine Meldung."""
    settings = _settings(default_settings, tmp_path)
    with pytest.raises(MissingInputError, match="stichprobe.json"):
        measured(settings, HEAD_CHECK.project)
    with pytest.raises(MissingInputError, match="guete.json"):
        head_sentence(settings)
    folder = tmp_path / HEAD_CHECK.project
    folder.mkdir()
    (folder / "stichprobe.json").write_text("{}", encoding="utf-8")
    (folder / "guete.json").write_text('{"satz": "geprüft"}', encoding="utf-8")
    with pytest.raises(SchemaError, match="profil"):
        measured(settings, HEAD_CHECK.project)
    with pytest.raises(SchemaError, match="Feld fehlt"):
        head_sentence(settings)
    # ein Profil, das es nicht gibt, ist ein Tippfehler und kein stilles „nicht gemessen"
    (folder / "stichprobe.json").write_text('{"profil": "gibt-es-nicht"}', encoding="utf-8")
    with pytest.raises(UnknownProfileError):
        measured(settings, HEAD_CHECK.project)


def test_ein_gewichtetes_mass_braucht_anteil_und_intervall() -> None:
    with pytest.raises(SchemaError, match="Anteil und Intervall"):
        Measure("Betrag", 100).text()
    assert Measure("Betrag", 100, share=0.962, interval=(0.885, 0.988)).text() == (
        "Betrag 0,962 (0,885–0,988; n 100)"
    )
