from __future__ import annotations

from pathlib import Path

from georep.bootstrap import REFERENCE_EXTRACTOR, bootstrap, bootstrap_from_settings
from georep.layout import Layout
from georep.settings import Bootstrap, Settings
from georep.stores import PaperStore, RawTextStore, TextMeta, TextStore


def _layout(tmp_path: Path, mini_root: Path) -> Layout:
    return Layout(tmp_path / "data", tmp_path / "cache", mini_root)


def test_bootstrap_copies_inputs_and_converts_the_corpus(tmp_path: Path, mini_root: Path) -> None:
    layout = _layout(tmp_path, mini_root)
    report = bootstrap(layout)
    # Punkt 58: ohne ``consultations`` kopiert bootstrap die Beratungsfolge **nicht**, auch wenn
    # die Fixture eine mitbringt -- der Schritt ``bodies`` liest sie dann nicht (Review 2026-10-14;
    # der Fall mit Deklaration steht unten in test_the_consultation_is_copied_only_when_…).
    assert sorted(report.copied) == [
        "Stimmbezirk_Wahlergebnis.csv",
        "Stimmbezirke_2025.geojson",
        "streets_per_district.json",
        "wikipedia_dict.json",
    ]
    assert report.missing == []
    assert (report.papers, report.texts) == (200, 200)
    assert (
        layout.results_csv.read_bytes()
        == (mini_root / "external" / "Stimmbezirk_Wahlergebnis.csv").read_bytes()
    )
    assert layout.papers.exists() and layout.texts.exists() and not layout.corpus.exists()
    assert (
        "4 Dateien kopiert, 0 übersprungen, 0 in Referenz oder Kontext nicht gefunden"
        in report.summary()
    )
    assert "200 Paper und 200 Texte" in report.summary()


def test_bootstrap_is_idempotent_and_force_recopies(tmp_path: Path, mini_root: Path) -> None:
    layout = _layout(tmp_path, mini_root)
    bootstrap(layout)
    second = bootstrap(layout)
    assert second.copied == [] and len(second.skipped) == 4 and second.papers is None
    forced = bootstrap(layout, force=True)
    assert len(forced.copied) == 4 and forced.papers == 200


def test_bootstrap_never_writes_into_the_reference(tmp_path: Path, mini_root: Path) -> None:
    before = sorted(p.relative_to(mini_root) for p in mini_root.rglob("*"))
    bootstrap(_layout(tmp_path, mini_root))
    after = sorted(p.relative_to(mini_root) for p in mini_root.rglob("*"))
    assert before == after


# --- Option 03: die Fremddaten kommen aus context_root ------------------------------------------


def test_bootstrap_copies_the_context_files_next_to_the_reference_inputs(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    names = default_settings.context.files.names()
    layout = Layout(
        tmp_path / "data", tmp_path / "cache", mini_root, context_root=mini_root / "context"
    )
    report = bootstrap(layout, context_files=names)
    assert len(report.copied) == 7 and report.missing == []
    assert "7 Dateien kopiert" in report.summary()
    for name in names:
        assert (layout.external / name).read_bytes() == layout.context_source(name).read_bytes()


def test_bootstrap_without_context_root_copies_only_the_reference(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    report = bootstrap(_layout(tmp_path, mini_root), context_files=("quartiersatlas_2024.csv",))
    assert len(report.copied) == 4 and report.missing == []


def test_bootstrap_reports_missing_context_files_without_failing(
    tmp_path: Path, mini_root: Path
) -> None:
    layout = Layout(
        tmp_path / "data", tmp_path / "cache", mini_root, context_root=tmp_path / "leer"
    )
    report = bootstrap(layout, context_files=("fehlt.csv",))
    assert report.missing == ["fehlt.csv"] and len(report.copied) == 4
    assert "1 in Referenz oder Kontext nicht gefunden" in report.summary()


# --- Option 07: Monitoring -------------------------------------------------------------------


def test_bootstrap_without_seed_copies_inputs_and_leaves_the_stores_alone(
    tmp_path: Path, mini_root: Path
) -> None:
    layout = _layout(tmp_path, mini_root).for_profile("2025")
    report = bootstrap(layout, seed_corpus=False)
    assert len(report.copied) == 4 and report.missing == []
    assert report.papers is None and report.texts is None
    assert not layout.papers.exists() and not layout.texts.exists()
    assert layout.pdf_manifest.is_file()  # der PDF-Store ist angelegt, die Eingabe von texts
    assert layout.external == tmp_path / "data" / "2025" / "external"
    assert "Stores nicht aus der Referenz gefüllt" in report.summary()
    # Ein zweiter Aufruf, auch mit force, fuellt die Stores weiterhin nicht
    forced = bootstrap(layout, force=True, seed_corpus=False)
    assert len(forced.copied) == 4 and forced.papers is None
    assert not layout.papers.exists() and not layout.texts.exists()


# --- Punkt 58: die Beratungsfolge wird nur kopiert, wenn das Profil sie deklariert -------------


def test_the_consultation_is_copied_only_when_the_profile_declares_one(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    """Review 2026-10-14: eine Kopie ohne Leser wäre eine Angabe ohne Stamp.

    Die Mini-Fixture bringt eine ``raw/beratungsfolge.parquet`` mit. Ein Profil mit
    ``[bodies].consultations`` bekommt sie (und zwar die der Fixture, nicht das Paket aus dem
    Profil); ein Profil ohne -- jede Periode mit eigener Folge im ``papers.jsonl`` -- bekommt sie
    nicht, denn der Schritt ``bodies`` nennt sie dann nicht als Eingabe.
    """
    declared = _layout(tmp_path / "mit", mini_root)
    report = bootstrap(declared, consultations=tmp_path / "gibt-es-nicht.parquet")
    assert declared.consultations.is_file()
    assert (
        declared.consultations.read_bytes()
        == (mini_root / "raw" / "beratungsfolge.parquet").read_bytes()
    )
    assert report.missing == []  # die Fixture gewinnt, der Pfad des Profils wird nicht gesucht

    plain = _layout(tmp_path / "ohne", mini_root)
    assert bootstrap(plain, consultations=None).missing == []
    assert not plain.consultations.exists()
    # Genau so entscheidet die Kette: ohne Deklaration ist die Datei keine Eingabe des Schritts
    from georep.pipeline import build_steps

    period = default_settings.model_copy(
        update={"bodies": default_settings.bodies.model_copy(update={"consultations": None})}
    )
    inputs = {
        path for step in build_steps(period, plain) if step.name == "bodies" for path in step.inputs
    }
    assert plain.consultations not in inputs


# --- Punkt 68: ein Textpaket legt neu gelesene Texte über die der Referenz ----------------------


def _text_package(tmp_path: Path, names: list[str]) -> Path:
    """Ein Textstore wie aus ``pack --texts``: je Name ein neu gelesener Text."""
    package = tmp_path / "texte" / "cache" / "text" / "texts.parquet"
    package.parent.mkdir(parents=True)
    store = TextStore(package)
    for name in names:
        store.put(name, f"neu gelesen: {name}", TextMeta(extractor="pypdf-7.1.0", source="pdf"))
    store.save()
    return package


def _file_names(layout: Layout) -> list[str]:
    return sorted(r.file_name for r in PaperStore(layout.papers).load().values() if r.file_name)


def test_a_text_package_replaces_the_texts_of_its_own_dataset(
    tmp_path: Path, mini_root: Path
) -> None:
    """Die Paper bleiben die der Referenz, die Texte kommen aus dem Paket, Byte für Byte."""
    probe = _layout(tmp_path / "probe", mini_root)
    bootstrap(probe)
    package = _text_package(tmp_path, _file_names(probe))
    layout = _layout(tmp_path / "neu", mini_root)
    report = bootstrap(layout, texts=package)
    assert report.missing == [] and (report.papers, report.texts) == (200, 200)
    assert layout.texts.read_bytes() == package.read_bytes()
    assert layout.papers.read_bytes() == probe.papers.read_bytes()
    assert f"200 Paper aus der Referenz und 200 Texte aus {package}" in report.summary()
    # Ohne force bleiben vorhandene Stores stehen, wie ohne Paket
    assert bootstrap(layout, texts=package).texts is None


def test_a_text_package_of_other_documents_leaves_the_reference_texts(
    tmp_path: Path, mini_root: Path
) -> None:
    """Die Mini-Fixture bootstrappt mit den Settings der Hauptperiode, deren Paket nicht ihres ist.

    Ein Textpaket gehört zu genau den Dateien seines Datensatzes; eine Datei zu viel oder zu
    wenig heißt, es ist das Paket eines anderen, und dann bleiben die Texte der Referenz.
    """
    probe = _layout(tmp_path / "probe", mini_root)
    bootstrap(probe)
    names = _file_names(probe)
    for other in (names[:-1], [*names, "99999999.pdf"]):
        package = _text_package(tmp_path / str(len(other)), other)
        layout = _layout(tmp_path / f"neu-{len(other)}", mini_root)
        report = bootstrap(layout, texts=package)
        assert layout.texts.read_bytes() == probe.texts.read_bytes()
        assert report.missing == [] and report.texts == 200
        assert f"Textpaket {package} nicht übernommen: {len(other)} Texte" in report.summary()


def test_a_missing_text_package_is_named_and_the_reference_texts_stay(
    tmp_path: Path, mini_root: Path
) -> None:
    layout = _layout(tmp_path, mini_root)
    report = bootstrap(layout, texts=tmp_path / "gibt-es-nicht.parquet")
    assert report.missing == ["gibt-es-nicht.parquet"] and report.texts == 200
    extractors = {str(row["extractor"]) for row in TextStore(layout.texts).rows.values()}
    assert extractors == {REFERENCE_EXTRACTOR}


def test_a_period_without_seeded_stores_takes_no_text_package(
    tmp_path: Path, mini_root: Path
) -> None:
    layout = _layout(tmp_path, mini_root).for_profile("2025")
    report = bootstrap(layout, seed_corpus=False, texts=tmp_path / "gibt-es-nicht.parquet")
    assert report.missing == [] and not layout.texts.exists()


def test_the_settings_wire_the_text_package_into_bootstrap(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    """``[bootstrap].texts``: leer heißt kein Paket, ein Pfad geht an ``bootstrap``."""
    assert Bootstrap(texts="").texts is None  # type: ignore[arg-type]
    probe = _layout(tmp_path / "probe", mini_root)
    bootstrap(probe)
    package = _text_package(tmp_path, _file_names(probe))
    settings = default_settings.model_copy(
        update={"bootstrap": default_settings.bootstrap.model_copy(update={"texts": package})}
    )
    layout = _layout(tmp_path / "neu", mini_root)
    assert bootstrap_from_settings(layout, settings).texts == 200
    assert layout.texts.read_bytes() == package.read_bytes()


# --- Fundament F1: ein Rohtextpaket legt den Rohtextstore an -------------------------------------


def _raw_package(tmp_path: Path, names: list[str]) -> Path:
    """Ein Rohtextstore wie aus ``pack --raw-texts``: je Name ein Text mit zwei Seiten."""
    package = tmp_path / "rohtexte" / "cache" / "text" / "rohtexte.parquet"
    package.parent.mkdir(parents=True)
    store = RawTextStore(package)
    for name in names:
        store.put(name, f"Kopf {name}\fSeite 2", pages=2, extractor="x+roh", pdf_sha256="0")
    store.save()
    return package


def test_a_raw_text_package_of_this_dataset_becomes_the_raw_store(
    tmp_path: Path, mini_root: Path
) -> None:
    """Ein Rohtext je lesbarer Hauptdatei: weniger als alle Dateien ist richtig, keine fremde."""
    probe = _layout(tmp_path / "probe", mini_root)
    bootstrap(probe)
    package = _raw_package(tmp_path, _file_names(probe)[:5])
    layout = _layout(tmp_path / "neu", mini_root)
    report = bootstrap(layout, raw_texts=package)
    assert report.missing == [] and report.raw_texts == 5
    assert layout.raw_texts.read_bytes() == package.read_bytes()
    assert f"5 Rohtexte aus {package}" in report.summary()
    # Ohne force bleibt ein vorhandener Rohtextstore stehen, mit force kommt das Paket wieder
    RawTextStore(layout.raw_texts).save()  # derselbe Inhalt, neu geschrieben
    again = bootstrap(layout, raw_texts=package)
    assert again.raw_texts is None and "rohtexte.parquet" in again.skipped
    assert bootstrap(layout, raw_texts=package, force=True).raw_texts == 5


def test_a_raw_text_package_with_a_foreign_name_is_refused(tmp_path: Path, mini_root: Path) -> None:
    """Das Paket der Hauptperiode gehört nicht zur Mini-Fixture, die mit ihren Settings bootstrappt."""
    probe = _layout(tmp_path / "probe", mini_root)
    bootstrap(probe)
    package = _raw_package(tmp_path, [*_file_names(probe)[:3], "99999999.pdf"])
    layout = _layout(tmp_path / "neu", mini_root)
    report = bootstrap(layout, raw_texts=package)
    assert report.raw_texts is None and not layout.raw_texts.exists()
    assert f"Rohtextpaket {package} nicht übernommen: 4 Rohtexte, 1 davon" in report.summary()


def test_a_missing_raw_text_package_is_named(tmp_path: Path, mini_root: Path) -> None:
    layout = _layout(tmp_path, mini_root)
    report = bootstrap(layout, raw_texts=tmp_path / "gibt-es-nicht.parquet")
    assert report.missing == ["gibt-es-nicht.parquet"] and not layout.raw_texts.exists()


def test_a_period_without_seeded_stores_takes_no_raw_text_package(
    tmp_path: Path, mini_root: Path
) -> None:
    layout = _layout(tmp_path, mini_root).for_profile("2025")
    report = bootstrap(layout, seed_corpus=False, raw_texts=tmp_path / "gibt-es-nicht.parquet")
    assert report.missing == [] and not layout.raw_texts.exists()


def test_the_settings_wire_the_raw_text_package_into_bootstrap(
    tmp_path: Path, mini_root: Path, default_settings: Settings
) -> None:
    """``[bootstrap].raw_texts``: leer heißt kein Paket, ein Pfad geht an ``bootstrap``."""
    assert Bootstrap(raw_texts="").raw_texts is None  # type: ignore[arg-type]
    probe = _layout(tmp_path / "probe", mini_root)
    bootstrap(probe)
    package = _raw_package(tmp_path, _file_names(probe))
    settings = default_settings.model_copy(
        update={"bootstrap": default_settings.bootstrap.model_copy(update={"raw_texts": package})}
    )
    layout = _layout(tmp_path / "neu", mini_root)
    assert bootstrap_from_settings(layout, settings).raw_texts == 200
    assert layout.raw_texts.read_bytes() == package.read_bytes()
