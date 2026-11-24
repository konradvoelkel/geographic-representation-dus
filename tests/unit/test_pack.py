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

from georep.analysis.procedures import ATTACHMENT_SCHEMA
from georep.bootstrap import bootstrap
from georep.layout import Layout
from georep.pack import (
    ATTACHMENTS_NAME,
    README_NAME,
    RUN_SOURCES,
    PackError,
    attachment_rows,
    cached_pages,
    check_text_store,
    pack,
    pack_attachments,
    pack_consultations,
    pack_raw_texts,
    pack_texts,
    package_files,
    paper_file_names,
)
from georep.prep.references import ReferenceRules
from georep.settings import Settings, load_settings
from georep.stores import RAW_TEXT_SCHEMA_VERSION, RawTextStore, TextMeta, TextStore


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


def test_pack_texts_writes_only_the_text_store(tmp_path: Path, default_settings: Settings) -> None:
    """Punkt 68: die Paper bleiben die der Referenz, nur die Texte kommen aus dem Paket."""
    layout = _text_run(tmp_path)
    target = tmp_path / "texte"
    report = pack_texts(layout, default_settings, target, today=dt.date(2026, 11, 18))
    assert {str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()} == {
        README_NAME,
        "cache/text/texts.parquet",
    }
    assert (target / "cache" / "text" / "texts.parquet").read_bytes() == layout.texts.read_bytes()
    assert report.figures == (("Texte", 2), ("aus PDFs", 1), ("übernommen", 1))
    assert "2 Texte, 1 aus PDFs, 1 übernommen" in report.line()
    assert "pack --texts" in (target / README_NAME).read_text(encoding="utf-8")


def test_pack_texts_keeps_what_is_there_without_force(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _text_run(tmp_path)
    target = tmp_path / "texte"
    pack_texts(layout, default_settings, target, today=dt.date(2026, 11, 18))
    again = pack_texts(layout, default_settings, target, today=dt.date(2026, 11, 18))
    assert again.skipped == ("cache/text/texts.parquet",) and not again.readme_written
    assert not pack_texts(layout, default_settings, target, force=True).skipped


def test_pack_texts_refuses_a_store_without_a_single_extraction(
    tmp_path: Path, mini_run: Layout, default_settings: Settings
) -> None:
    """Nur übernommene Texte wären der Textstore der Referenz ein zweites Mal, kein Paket."""
    with pytest.raises(PackError, match="keiner der 200 Texte"):
        pack_texts(mini_run, default_settings, tmp_path / "texte")
    assert not (tmp_path / "texte").exists()


def test_pack_texts_checks_the_store_like_pack(tmp_path: Path, default_settings: Settings) -> None:
    layout = _text_run(tmp_path)
    store = TextStore(layout.texts)
    store.put("c.pdf", "ohne Paper", TextMeta(extractor="pypdf-7.1.0", source="pdf"))
    store.save()
    with pytest.raises(PackError, match="haben kein Paper"):
        pack_texts(layout, default_settings, tmp_path / "texte")
    with pytest.raises(PackError, match="gehört daneben"):
        pack_texts(layout, default_settings, layout.root / "texte")


def test_pack_texts_says_when_the_store_is_missing(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "leer", tmp_path / "cache", tmp_path / "ref", "duesseldorf")
    with pytest.raises(PackError, match="fehlen; lief"):
        pack_texts(layout, default_settings, tmp_path / "texte")


def _text_run(tmp_path: Path) -> Layout:
    """Ein Lauf mit zwei Papern und zwei Texten: einer neu extrahiert, einer übernommen."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref", "duesseldorf")
    _papers_jsonl(
        layout.papers,
        [{"id": "p1", "file_name": "a.pdf"}, {"id": "p2", "file_name": "b.pdf"}, {"id": "p3"}],
    )
    layout.texts.parent.mkdir(parents=True, exist_ok=True)
    store = TextStore(layout.texts)
    store.put("a.pdf", "neu gelesen", TextMeta(extractor="pypdf-7.1.0", source="pdf"))
    store.put("b.pdf", "aus der Arbeit", TextMeta(extractor="Arbeit", source="reference"))
    store.save()
    return layout


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


# --- Fundament F1: ein Paket, das nur den Rohtextstore trägt -------------------------------------


def _raw_run(tmp_path: Path) -> Layout:
    """Ein Lauf mit zwei Hauptdateien, von denen eine einen Rohtext hat (die andere war defekt)."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref", "duesseldorf")
    _papers_jsonl(
        layout.papers,
        [{"id": "p1", "file_name": "a.pdf"}, {"id": "p2", "file_name": "b.pdf"}, {"id": "p3"}],
    )
    layout.raw_texts.parent.mkdir(parents=True, exist_ok=True)
    store = RawTextStore(layout.raw_texts)
    store.put("a.pdf", "Kopf\nBetrifft: A\fSeite 2", pages=2, extractor="x+roh", pdf_sha256="0")
    store.save()
    # Der Textstore desselben Laufs: dieselbe Datei, derselbe PDF-Hash, der Extraktor ohne Zusatz;
    # b.pdf hat dort den Text der Arbeit (ohne Hash), wie 00403713.pdf in der Hauptperiode
    texts = TextStore(layout.texts)
    texts.put("a.pdf", ": a", TextMeta(extractor="x", pdf_sha256="0", source="pdf"))
    texts.put("b.pdf", "arbeit", TextMeta(extractor="Arbeit", source="reference"))
    texts.save()
    return layout


def test_pack_raw_texts_writes_only_the_raw_store(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _raw_run(tmp_path)
    target = tmp_path / "rohtexte"
    report = pack_raw_texts(layout, default_settings, target, today=dt.date(2026, 11, 23))
    assert {str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()} == {
        README_NAME,
        "cache/text/rohtexte.parquet",
    }
    packed = target / "cache" / "text" / "rohtexte.parquet"
    assert packed.read_bytes() == layout.raw_texts.read_bytes()
    assert report.figures == (("Rohtexte", 1), ("Seiten", 2), ("Hauptdateien ohne Rohtext", 1))
    assert "1 Rohtexte, 2 Seiten, 1 Hauptdateien ohne Rohtext" in report.line()
    assert "pack --raw-texts" in (target / README_NAME).read_text(encoding="utf-8")


def test_pack_raw_texts_keeps_what_is_there_without_force(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _raw_run(tmp_path)
    target = tmp_path / "rohtexte"
    pack_raw_texts(layout, default_settings, target, today=dt.date(2026, 11, 23))
    again = pack_raw_texts(layout, default_settings, target, today=dt.date(2026, 11, 23))
    assert again.skipped == ("cache/text/rohtexte.parquet",) and not again.readme_written
    assert not pack_raw_texts(layout, default_settings, target, force=True).skipped


def test_pack_raw_texts_refuses_an_empty_store(
    tmp_path: Path, mini_run: Layout, default_settings: Settings
) -> None:
    """Ohne PDFs schreibt der Schritt einen leeren Store; als Paket hieße er „so sah der Lauf aus"."""
    with pytest.raises(PackError, match="kein einziger Rohtext"):
        pack_raw_texts(mini_run, default_settings, tmp_path / "rohtexte")
    assert not (tmp_path / "rohtexte").exists()


def test_pack_raw_texts_refuses_a_text_without_a_paper_and_a_target_inside(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = _raw_run(tmp_path)
    store = RawTextStore(layout.raw_texts)
    store.put("c.pdf", "ohne Paper", pages=1, extractor="x+roh", pdf_sha256="1")
    store.save()
    with pytest.raises(PackError, match="haben kein Paper"):
        pack_raw_texts(layout, default_settings, tmp_path / "rohtexte")
    with pytest.raises(PackError, match="gehört daneben"):
        pack_raw_texts(layout, default_settings, layout.root / "rohtexte")


def test_pack_raw_texts_says_when_the_store_is_missing(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout = Layout(tmp_path / "leer", tmp_path / "cache", tmp_path / "ref", "duesseldorf")
    with pytest.raises(PackError, match="fehlen; lief"):
        pack_raw_texts(layout, default_settings, tmp_path / "rohtexte")


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        (
            TextMeta(extractor="x", pdf_sha256="1", source="pdf"),
            "1 haben im Textstore einen anderen PDF-Hash",
        ),
        (
            TextMeta(extractor="y", pdf_sha256="0", source="pdf"),
            "1 haben im Textstore einen anderen Extraktor",
        ),
        (None, "1 haben im Textstore keinen Text"),
    ],
)
def test_pack_raw_texts_checks_the_bridge_to_the_text_store(
    tmp_path: Path, default_settings: Settings, meta: TextMeta | None, expected: str
) -> None:
    """Review F1, N2: ein Rohtext gehört zu dem Text, den die Suche liest.

    Gleicher PDF-Hash je Name, und der Extraktor ist der des Textstores mit ``+roh``; sonst
    plättet der Rohtext nicht zum Text, und das Paket behauptete eine Brücke, die es nicht gibt.
    """
    layout = _raw_run(tmp_path)
    texts = TextStore(layout.texts)
    texts.rows.pop("a.pdf")
    if meta is not None:
        texts.put("a.pdf", ": a", meta)
    texts.save()
    with pytest.raises(PackError, match=expected):
        pack_raw_texts(layout, default_settings, tmp_path / "rohtexte")
    assert not (tmp_path / "rohtexte").exists()


def test_pack_raw_texts_writes_the_same_rows_with_a_stronger_compression(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Review F1, M4: das Paket liegt im Repo, also zählt jedes Byte; der Inhalt bleibt derselbe.

    ``pack_raw_texts`` schreibt den Store neu, mit zstd auf Stufe ``level`` (Vorgabe 19) statt der
    Stufe des Caches, und mit derselben Schema-Version in den Metadaten.
    """
    layout = _raw_run(tmp_path)
    store = RawTextStore(layout.raw_texts)
    for i in range(40):  # genug Text, dass die Stufe einen Unterschied macht
        name = f"z{i:02d}.pdf"
        store.put(
            name,
            "Beschlussvorlage Betrifft: " * 50 + str(i),
            pages=1,
            extractor="x+roh",
            pdf_sha256=str(i),
        )
    store.save()
    _papers_jsonl(
        layout.papers, [{"id": f"p{i}", "file_name": name} for i, name in enumerate(store.rows)]
    )
    texts = TextStore(layout.texts)
    for name, row in store.rows.items():
        texts.put(
            name, "t", TextMeta(extractor="x", pdf_sha256=str(row["pdf_sha256"]), source="pdf")
        )
    texts.save()
    sizes = {}
    for level in (1, 19):
        target = tmp_path / f"stufe-{level}"
        pack_raw_texts(layout, default_settings, target, level=level, today=dt.date(2026, 11, 23))
        packed = target / "cache" / "text" / "rohtexte.parquet"
        assert pl.read_parquet(packed).equals(pl.read_parquet(layout.raw_texts))
        assert pl.read_parquet_metadata(packed)["georep.schema_version"] == str(
            RAW_TEXT_SCHEMA_VERSION
        )
        sizes[level] = packed.stat().st_size
    assert sizes[19] < sizes[1]
    default = tmp_path / "vorgabe"
    pack_raw_texts(layout, default_settings, default, today=dt.date(2026, 11, 23))
    assert (default / "cache/text/rohtexte.parquet").read_bytes() == (
        tmp_path / "stufe-19" / "cache/text/rohtexte.parquet"
    ).read_bytes()


def test_pack_raw_texts_names_an_old_schema_version(
    tmp_path: Path, default_settings: Settings
) -> None:
    """Review F1, dritte Runde: ein Store in Version 1 hieß bisher „lief ohne PDFs"."""
    from georep.io import write_parquet

    layout = _raw_run(tmp_path)
    write_parquet(
        pl.read_parquet(layout.raw_texts).drop("form_feeds"), layout.raw_texts, schema_version=1
    )
    with pytest.raises(PackError, match="Schema-Version 1") as refused:
        pack_raw_texts(layout, default_settings, tmp_path / "rohtexte")
    assert "ohne PDFs" not in str(refused.value)


# --- Vorhaben 14: das Anlagenpaket aus dem HTTP-Cache -------------------------------------------

ENDPOINT = "https://ris.test/Oparl/bodies/0015/papers"
MASK = ReferenceRules.from_settings(load_settings(cwd=Path("/nonexistent")).procedures)


def _file(name: str, day: str | None, created: str | None = None) -> dict[str, object]:
    found: dict[str, object] = {"id": f"https://ris.test/files/{name}", "name": name}
    if day is not None:
        found["date"] = day
    if created is not None:
        found["created"] = created
    return found


def _paper(paper_id: str, modified: str, *files: dict[str, object]) -> dict[str, object]:
    return {"id": paper_id, "modified": modified, "auxiliaryFile": list(files)}


def _cache(path: Path, pages: list[tuple[str, dt.datetime, list[dict[str, object]]]]) -> Path:
    """Ein HTTP-Cache im Format von requests-cache: Tabelle ``responses``, gepickelte Antworten."""
    import sqlite3
    from contextlib import closing

    from requests_cache.models.response import CachedResponse
    from requests_cache.serializers import SERIALIZERS

    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("create table responses (key PRIMARY KEY, value)")
        for number, (url, created, papers) in enumerate(pages):
            response = CachedResponse(
                url=url,
                status_code=200,
                content=json.dumps({"data": papers}).encode(),
                created_at=created,
            )
            connection.execute(
                "insert into responses values (?, ?)",
                (f"k{number}", SERIALIZERS["pickle"].dumps(response)),
            )
    return path


FIRST = dt.datetime(2026, 10, 13, 12, tzinfo=dt.UTC)
SECOND = dt.datetime(2026, 10, 14, 1, tzinfo=dt.UTC)


def test_cached_pages_reads_only_the_paper_list_of_the_endpoint(tmp_path: Path) -> None:
    cache = _cache(
        tmp_path / "http.sqlite",
        [
            (f"{ENDPOINT}?page=2", FIRST, []),
            ("https://ris.test/Oparl/bodies/0011/papers", FIRST, []),
            (f"{ENDPOINT}/vo/1", FIRST, []),
        ],
    )
    assert cached_pages(cache, ENDPOINT) == [(FIRST.date(), b'{"data": []}')]


def test_attachment_rows_keep_the_newest_object_in_the_server_order(tmp_path: Path) -> None:
    old = _paper("p1", "2026-03-01T10:00:00+01:00", _file("Vorlage", "2019-07-03"))
    new = _paper(
        "p1",
        "2026-03-02T10:00:00+01:00",
        _file("Antwort der Verwaltung", None, "2026-02-01T09:00:00+01:00"),
        _file("Schreiben von Herrn Seeler", "2026-02-02"),  # Review K1: der Name bleibt draußen
    )
    pages = [
        (
            FIRST.date(),
            json.dumps({"data": [old, _paper("p2", "2026-01-01T00:00:00+01:00")]}).encode(),
        ),
        (
            SECOND.date(),
            json.dumps({"data": [new, _paper("p9", "2026-01-01T00:00:00+01:00")]}).encode(),
        ),
        (SECOND.date(), json.dumps({"data": [old]}).encode()),  # älter: bleibt draußen
    ]
    rows = attachment_rows(pages, {"p1", "p2"}, MASK)
    assert rows.schema == pl.Schema(ATTACHMENT_SCHEMA)
    assert rows.rows() == [
        (
            "p1",
            SECOND.date(),
            [
                {"name": "Antwort der Verwaltung", "datum": dt.date(2026, 2, 1)},
                {"name": "Schreiben von Herrn …", "datum": dt.date(2026, 2, 2)},
            ],
        ),
        ("p2", FIRST.date(), []),
    ]


def _attachment_run(tmp_path: Path, settings: Settings) -> tuple[Layout, Settings]:
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref")
    layout.ensure_dirs()
    pl.DataFrame({"id": ["p1", "p2", "p3"]}).write_parquet(layout.corpus)
    _cache(
        layout.http_cache,
        [
            (
                f"{ENDPOINT}?page=1",
                FIRST,
                [
                    _paper("p1", "2026-01-01T00:00:00+01:00", _file("Antwort", "2026-02-01")),
                    _paper("p2", "2026-01-01T00:00:00+01:00"),
                    _paper("x9", "2026-01-01T00:00:00+01:00"),
                ],
            )
        ],
    )
    oparl = settings.sources.oparl.model_copy(update={"endpoint": ENDPOINT})
    procedures = settings.procedures.model_copy(update={"related": []})
    return layout, settings.model_copy(
        update={
            "sources": settings.sources.model_copy(update={"oparl": oparl}),
            "procedures": procedures,
        }
    )


def test_pack_attachments_writes_one_row_per_paper_the_cache_knows(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout, settings = _attachment_run(tmp_path, default_settings)
    target = tmp_path / "paket"
    report = pack_attachments(layout, settings, target, today=dt.date(2026, 11, 24))
    frame = pl.read_parquet(target / ATTACHMENTS_NAME)
    assert frame.get_column("id").to_list() == [
        "p1",
        "p2",
    ]  # p3 kennt der Cache nicht, x9 ist fremd
    assert dict(report.figures) == {
        "Drucksachen": 2,
        "mit Anlage": 1,
        "Anlagen": 1,
        "nicht im Cache": 1,
        "Anlagennamen mit maskiertem Personennamen": 0,
    }
    assert report.readme_written and "pack --attachments" in (target / README_NAME).read_text(
        encoding="utf-8"
    )
    again = pack_attachments(layout, settings, target)
    assert again.skipped == (ATTACHMENTS_NAME,)


def test_pack_attachments_refuses_without_cache_or_without_a_known_paper(
    tmp_path: Path, default_settings: Settings
) -> None:
    layout, settings = _attachment_run(tmp_path, default_settings)
    elsewhere = settings.sources.oparl.model_copy(update={"endpoint": f"{ENDPOINT}/anders"})
    other = settings.model_copy(
        update={"sources": settings.sources.model_copy(update={"oparl": elsewhere})}
    )
    with pytest.raises(PackError, match="das Paket wäre leer"):
        pack_attachments(layout, other, tmp_path / "paket")
    layout.http_cache.unlink()
    with pytest.raises(PackError, match="HTTP-Cache"):
        pack_attachments(layout, settings, tmp_path / "paket")
