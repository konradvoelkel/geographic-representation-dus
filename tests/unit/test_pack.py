"""``georep pack``: was in ein Datenpaket kommt, und was es verweigert (Punkt 56).

Die Gegenrichtung von ``bootstrap``, und darum ist die stärkste Zusicherung ein Rundgang: packen,
dann aus dem Paket bootstrappen, und die Eingaben müssen byteidentisch wieder da sein. Dazu die
zwei Abbrüche, an denen der Befehl überhaupt hängt -- eine Fremdzeile im Textstore und ein Text
ohne Paper sind genau die Fehler, die am 2026-10-13 von Hand gefunden wurden.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import polars as pl
import pytest

from georep.bootstrap import bootstrap
from georep.layout import Layout
from georep.pack import (
    README_NAME,
    RUN_SOURCES,
    PackError,
    check_text_store,
    pack,
    pack_consultations,
    package_files,
    paper_file_names,
)
from georep.settings import Settings
from georep.stores import TextMeta, TextStore


@pytest.fixture
def packed(tmp_path: Path, mini_run: Layout, default_settings: Settings) -> tuple[Path, Layout]:
    """Das Paket der Mini-Fixture, aus dem Lauf der Session gepackt."""
    target = tmp_path / "paket"
    report = pack(mini_run, default_settings, target, today=dt.date(2026, 10, 14))
    assert report.target == target and not report.skipped
    return target, mini_run


def test_pack_writes_exactly_the_inputs_bootstrap_reads(
    packed: tuple[Path, Layout], default_settings: Settings
) -> None:
    target, run = packed
    names = {str(path.relative_to(target)) for path in target.rglob("*") if path.is_file()}
    assert names == {
        README_NAME,
        "external/Stimmbezirk_Wahlergebnis.csv",
        "external/Stimmbezirke_2025.geojson",
        "raw/papers.jsonl",
        "raw/streets_per_district.json",
        "raw/wikipedia_dict.json",
        "cache/text/texts.parquet",
    }
    # Kein PDF, kein Stamp, kein Manifest, kein Abgeleitetes
    assert not any(
        path.suffix == ".pdf" or path.name.endswith(".stamp.json") for path in target.rglob("*")
    )
    assert not (target / "interim").exists() and not (target / "processed").exists()
    assert not (target / "site").exists() and not (target / "cache" / "pdf").exists()


def test_the_package_bootstraps_back_byte_identically(
    packed: tuple[Path, Layout], tmp_path: Path, default_settings: Settings
) -> None:
    """Der Rundgang: was gepackt wurde, liest ``bootstrap`` wieder als dieselben Bytes."""
    target, run = packed
    fresh = Layout(tmp_path / "neu", tmp_path / "neucache", target, default_settings.profile)
    report = bootstrap(fresh)
    assert report.missing == [] and (report.papers, report.texts) == (200, 200)
    for path in (fresh.results_csv, fresh.districts_geojson, fresh.streets, fresh.pois):
        original = run.root / path.relative_to(fresh.root)
        assert path.read_bytes() == original.read_bytes(), path.name
    assert fresh.papers.read_bytes() == run.papers.read_bytes()
    assert fresh.texts.read_bytes() == run.texts.read_bytes()


def test_the_readme_skeleton_carries_the_checksums(packed: tuple[Path, Layout]) -> None:
    target, _ = packed
    readme = (target / README_NAME).read_text(encoding="utf-8")
    assert "| Datei | Bytes | SHA-256 |" in readme
    assert "[nachzutragen]" in readme and "georep --profile" in readme
    # Jede Datei des Pakets steht in der Tabelle, mit ihrer Größe
    for path in sorted(p for p in target.rglob("*") if p.is_file() and p.name != README_NAME):
        name = str(path.relative_to(target))
        assert f"`{name}`" in readme
        assert f"{path.stat().st_size:,}".replace(",", " ") in readme


def test_pack_leaves_an_existing_readme_alone(
    packed: tuple[Path, Layout], default_settings: Settings
) -> None:
    """Die drei READMEs im Repo tragen mehr Prosa, als ein Gerüst haben kann."""
    target, run = packed
    (target / README_NAME).write_text("# Von Hand\n", encoding="utf-8")
    again = pack(run, default_settings, target, force=True)
    assert not again.readme_written and "README.md vorhanden" in again.line()
    assert (target / README_NAME).read_text(encoding="utf-8") == "# Von Hand\n"
    assert "| Datei | Bytes | SHA-256 |" in again.table()  # zum Einsetzen von Hand


def test_pack_skips_what_is_there_and_force_recopies(
    packed: tuple[Path, Layout], default_settings: Settings
) -> None:
    target, run = packed
    again = pack(run, default_settings, target)
    assert len(again.skipped) == len(again.files) and "nicht überschrieben" in again.line()
    forced = pack(run, default_settings, target, force=True)
    assert not forced.skipped


# --- Die zwei Abbrüche -------------------------------------------------------------------------


def test_pack_refuses_a_text_that_does_not_come_from_a_pdf(
    tmp_path: Path, mini_run: Layout, default_settings: Settings
) -> None:
    """Der Fehler vom 2026-10-13: fünf Zeilen aus einer Stichprobe lagen im Store der Stadt."""
    store = TextStore(mini_run.texts)
    saved = mini_run.texts.read_bytes()
    try:
        name = next(iter(store.rows))
        store.put(name, "aus einer Fixture", TextMeta(extractor="x", source="stichprobe"))
        store.save()
        with pytest.raises(PackError, match="kommen nicht aus einem Lauf"):
            pack(mini_run, default_settings, tmp_path / "paket")
        assert not (tmp_path / "paket").exists()  # nichts angefangen
    finally:
        mini_run.texts.write_bytes(saved)


def test_pack_refuses_a_text_without_a_paper(
    tmp_path: Path, mini_run: Layout, default_settings: Settings
) -> None:
    store = TextStore(mini_run.texts)
    saved = mini_run.texts.read_bytes()
    try:
        store.put("00000000.pdf", "ohne Paper", TextMeta(extractor="x", source="pdf"))
        store.save()
        with pytest.raises(PackError, match="haben kein Paper"):
            pack(mini_run, default_settings, tmp_path / "paket")
    finally:
        mini_run.texts.write_bytes(saved)


def test_pack_refuses_a_target_inside_the_data_root(
    mini_run: Layout, default_settings: Settings
) -> None:
    """Ein Paket über die Daten des Laufs zu legen, aus dem es entsteht, endet im Nichts."""
    for target in (mini_run.root / "paket", mini_run.data_root, mini_run.cache_root / "p"):
        with pytest.raises(PackError, match="ein Paket gehört daneben"):
            pack(mini_run, default_settings, target)


def test_pack_names_a_missing_input_instead_of_writing_half(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    empty = Layout(tmp_path / "leer", tmp_path / "cache", mini_root, default_settings.profile)
    with pytest.raises(PackError, match="Eingaben fehlen"):
        pack(empty, default_settings, tmp_path / "paket")


# --- Was das Paket je Profil enthält -----------------------------------------------------------


def test_a_period_with_the_base_dictionary_packs_no_streets_and_places(
    mini_run: Layout, default_settings: Settings
) -> None:
    """``period.dictionary = "base"``: Straßen und Orte gehören der Hauptperiode, nicht hierher."""
    period = default_settings.model_copy(
        update={"period": default_settings.period.model_copy(update={"dictionary": "base"})}
    )
    names = {name for _, name in package_files(mini_run, period)}
    assert "raw/streets_per_district.json" not in names and "raw/wikipedia_dict.json" not in names
    assert {"raw/papers.jsonl", "cache/text/texts.parquet"} <= names
    own = {name for _, name in package_files(mini_run, default_settings)}
    assert "raw/streets_per_district.json" in own


def test_paper_file_names_reads_the_jsonl(mini_run: Layout) -> None:
    names = paper_file_names(mini_run.papers)
    assert len(names) == 200 and all(name.endswith(".pdf") for name in names)
    first = json.loads(mini_run.papers.read_text(encoding="utf-8").splitlines()[0])
    assert first["file_name"] in names


def test_check_text_store_counts_the_rows_it_approves(mini_run: Layout) -> None:
    store = pl.read_parquet(mini_run.texts)
    assert check_text_store(mini_run) == store.height
    # Die Mini-Fixture ist aus der Referenz gebootstrappt, nicht abgerufen: auch das ist ein Lauf
    assert set(store.get_column("source")) == {"reference"} <= RUN_SOURCES


# --- Punkt 58: das Paket mit der Beratungsfolge je Dokument ------------------------------------


def _papers_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8"
    )


@pytest.fixture
def folge_run(tmp_path: Path, default_settings: Settings) -> Layout:
    """Ein Lauf, dessen ``raw/papers.jsonl`` eine Beratungsfolge trägt (wie der Vollabruf)."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref", "duesseldorf")
    organizations = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/organizations"
    _papers_jsonl(
        layout.papers,
        [
            {
                "id": "p2",
                "reference": "RAT/1/2021",
                "consultation_organizations": [f"{organizations}/gr/6"],
                "modified": "2026-03-01T10:00:00+01:00",
            },
            {
                "id": "p1",
                "reference": "BV1/1/2021",
                "consultation_organizations": [
                    f"{organizations}/gr/32",
                    f"{organizations}/gr/6",
                ],
                "modified": None,
            },
            {"id": "p3", "reference": "KUA/1/2021", "consultation_organizations": []},
        ],
    )
    return layout


def test_pack_consultations_writes_only_the_three_columns(
    folge_run: Layout, tmp_path: Path, default_settings: Settings
) -> None:
    target = tmp_path / "beratungsfolge"
    report = pack_consultations(folge_run, default_settings, target, today=dt.date(2026, 10, 14))
    assert {str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()} == {
        README_NAME,
        "raw/beratungsfolge.parquet",
    }
    frame = pl.read_parquet(target / "raw" / "beratungsfolge.parquet")
    assert frame.columns == ["id", "consultation_organizations", "modified"]
    assert frame.get_column("id").to_list() == ["p1", "p2", "p3"]  # sortiert
    assert frame.get_column("consultation_organizations").list.len().to_list() == [2, 1, 0]
    assert report.figures == (
        ("Dokumente", 3),
        ("mit Beratungsfolge", 2),
        ("verschiedene Organisationen", 2),
    )
    assert "3 Dokumente, 2 mit Beratungsfolge" in report.line()
    readme = (target / README_NAME).read_text(encoding="utf-8")
    assert "pack --consultations" in readme and "| Dokumente | 3 |" in readme
    assert "| `raw/beratungsfolge.parquet` |" in readme


def test_pack_consultations_keeps_what_is_there_without_force(
    folge_run: Layout, tmp_path: Path, default_settings: Settings
) -> None:
    target = tmp_path / "beratungsfolge"
    pack_consultations(folge_run, default_settings, target, today=dt.date(2026, 10, 14))
    again = pack_consultations(folge_run, default_settings, target, today=dt.date(2026, 10, 14))
    assert again.skipped == ("raw/beratungsfolge.parquet",) and not again.readme_written
    forced = pack_consultations(
        folge_run, default_settings, target, force=True, today=dt.date(2026, 10, 14)
    )
    assert not forced.skipped


def test_pack_consultations_says_when_the_metadata_are_missing(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "leer", tmp_path / "cache", tmp_path / "ref", "duesseldorf")
    with pytest.raises(PackError, match="fehlt; lief"):
        pack_consultations(layout, default_settings, tmp_path / "ziel")
    # Und ein Ziel in der Datenwurzel bleibt verboten, wie beim Paket der Eingaben
    _papers_jsonl(layout.papers, [{"id": "p1", "consultation_organizations": []}])
    with pytest.raises(PackError, match="gehört daneben"):
        pack_consultations(layout, default_settings, layout.root / "paket")
