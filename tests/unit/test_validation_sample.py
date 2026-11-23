"""Codebuch und Stichprobe (F4): ``georep validate sample``, die Aufteilung von Hand nachgezählt."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from georep.cli import main
from georep.errors import EmptyResultError, MissingInputError, SchemaError
from georep.settings import load_settings
from georep.validation.codebook import Codebook, load_codebook
from georep.validation.paths import validation_paths
from georep.validation.sample import allocate, draw_sample, read_sample
from tests.validation_project import CODEBOOK, PROJECT, corpus_frame, make_project


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    make_project(tmp_path)
    monkeypatch.chdir(tmp_path / "repo")
    return tmp_path / "repo"


def _codebook(text: str = CODEBOOK) -> Codebook:
    import tomllib

    return Codebook.model_validate(tomllib.loads(text))


# --- Aufteilung auf die Schichten ------------------------------------------------------------------


def test_proportional_allocation_by_hand() -> None:
    # 10 aus 50/30/20: je eine, Rest 7 nach 49/29/19 (Summe 97): 343/97 = 3 Rest 52,
    # 203/97 = 2 Rest 9, 133/97 = 1 Rest 36; die fehlende eine geht an den größten Rest (a)
    assert allocate({"a": 50, "b": 30, "c": 20}, 10, "proportional") == {"a": 5, "b": 3, "c": 2}


def test_equal_allocation_fills_small_strata_completely() -> None:
    # 12 aus 2/10/10: a nimmt sich ganz (2), b und c teilen die 10
    assert allocate({"a": 2, "b": 10, "c": 10}, 12, "equal") == {"a": 2, "b": 5, "c": 5}


def test_proportional_allocation_is_self_weighting_where_it_can_be() -> None:
    """Review 2026-11-23: mit einer Mindesteinheit vorab kamen 8/2 statt 9/1 heraus."""
    assert allocate({"a": 900, "b": 100}, 10, "proportional") == {"a": 9, "b": 1}


def test_every_stratum_gets_one_even_if_tiny() -> None:
    assert allocate({"groß": 1000, "klein": 1}, 2, "proportional") == {"groß": 1, "klein": 1}


# --- Codebuch -----------------------------------------------------------------------------------


def test_the_codebook_reads_and_knows_its_labels(project: Path) -> None:
    paths = validation_paths(load_settings(cwd=project), PROJECT)
    codebook = load_codebook(paths.codebook, PROJECT)
    assert codebook.question("bv").labels == ("ja", "nein") and codebook.key_columns == ("id",)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (('positive = ["ja"]', "positive = []"), "genau ein Label in positive"),
        (('positive = ["ja"]', 'positive = ["vielleicht"]'), "keine Optionen"),
        (('id = "bv"', 'id = "id"'), "question id"),
        (
            (
                "[sample]",
                '[[questions]]\nid = "x"\nquestion = "?"\nscale = "open"\nonly_if = {question = "y", values = ["ja"]}\n\n[sample]',
            ),
            "keine frühere Frage",
        ),
        (('value = "nein"', 'value = "ja"'), "jedes Label einmal"),
        (('unit = "document"', 'unit = "absatz"'), "unit"),
        (("[text]\n", '[text]\ncontext = ["id"]\n'), "Schlüsselspalten"),
        (('project = "11-test"', 'project = "12-anders"'), "der Ordner heißt"),
        (('scale = "binary"', 'scale = "binär"'), "scale"),
    ],
)
def test_a_broken_codebook_names_the_field(
    project: Path, change: tuple[str, str], message: str
) -> None:
    paths = validation_paths(load_settings(cwd=project), PROJECT)
    paths.codebook.write_text(CODEBOOK.replace(*change), encoding="utf-8")
    with pytest.raises(SchemaError, match=message):
        load_codebook(paths.codebook, PROJECT)


def test_a_missing_codebook_is_a_missing_input(project: Path) -> None:
    paths = validation_paths(load_settings(cwd=project), "12-fehlt")
    with pytest.raises(MissingInputError, match="Mess-Agent"):
        load_codebook(paths.codebook, "12-fehlt")


@pytest.mark.parametrize(
    ("where", "message"),
    [
        ("{repo}/validierung/lokal", "Arbeitsbaum"),
        ("{repo}/lokal", "Arbeitsbaum"),
        ("lokal", "relativ"),
    ],
)
def test_the_coding_folder_may_not_lie_in_the_repository(
    project: Path, where: str, message: str
) -> None:
    (project / "settings.local.toml").write_text(
        f'validation.coding_root = "{where.format(repo=project)}"\n', encoding="utf-8"
    )
    with pytest.raises(SchemaError, match=message):
        validation_paths(load_settings(cwd=project), PROJECT)


# --- Stichprobe über die Befehlszeile ---------------------------------------------------------------


def test_sample_draws_by_stratum_and_writes_keys_only(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", "sample", PROJECT]) == 0
    out = capsys.readouterr().out
    assert "9 Einheiten aus 28, 2 ohne Text weggelassen, 3 Schichten; nicht selbstgewichtend" in out
    folder = project / "validierung" / PROJECT
    sample = pl.read_csv(folder / "stichprobe.csv")
    assert sample.columns == ["id", "schicht", "schicht_n"]
    assert sample.height == 9 and sample.get_column("id").n_unique() == 9
    assert sample.get_column("id").is_sorted()
    # 9 aus 15/10/3 (zwei Vorlagen ohne Text, N = 28): Quoten 4,82 / 3,21 / 0,96, abgerundet
    # 4/3/0, die zwei fehlenden an die größten Reste (Vorlage 0,96, Antrag 0,82)
    counts = dict(sample.group_by("schicht").len().iter_rows())
    assert counts == {"Antrag": 5, "Anfrage": 3, "Vorlage": 1}
    sizes = dict(sample.select("schicht", "schicht_n").unique().iter_rows())
    assert sizes == {"Antrag": 15, "Anfrage": 10, "Vorlage": 3}
    assert not set(sample.get_column("id")) & {"d28", "d29"}
    meta = json.loads((folder / "stichprobe.json").read_text(encoding="utf-8"))
    assert meta["einheiten"] == 28 and meta["ohne_text"] == 2 and meta["seed"] == 7
    assert meta["schichten"]["Vorlage"] == {"grundgesamtheit": 3, "stichprobe": 1}
    assert meta["selbstgewichtend"] is False
    assert meta["grundgesamtheit"] == "interim/papers.parquet"
    assert "text" not in (folder / "stichprobe.csv").read_text(encoding="utf-8")


def test_a_sample_is_drawn_once_unless_forced(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", "sample", PROJECT]) == 0
    first = (project / "validierung" / PROJECT / "stichprobe.csv").read_bytes()
    assert main(["validate", "sample", PROJECT]) == 1
    assert "gibt es schon" in capsys.readouterr().err
    assert main(["validate", "sample", PROJECT, "--force"]) == 0
    assert (project / "validierung" / PROJECT / "stichprobe.csv").read_bytes() == first


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("size = 9", "size = 29"), "größer als die Grundgesamtheit"),
        (("size = 9", "size = 2"), "kleiner als die Zahl der Schichten"),
        (('stratum = "paper_type"', 'stratum = "art"'), "ohne Spalten"),
        (
            ('stratum = "paper_type"', 'strata = ["Beschluss"]\nstratum = "paper_type"'),
            "gibt es nicht",
        ),
    ],
)
def test_impossible_samples_are_domain_errors(
    project: Path, capsys: pytest.CaptureFixture[str], change: tuple[str, str], message: str
) -> None:
    (project / "validierung" / PROJECT / "codebuch.toml").write_text(
        CODEBOOK.replace(*change), encoding="utf-8"
    )
    assert main(["validate", "sample", PROJECT]) == 1
    assert message in capsys.readouterr().err


def test_a_pair_population_from_the_command_line(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pairs = pl.DataFrame(
        {"id_a": ["d00", "d01", "d02", "d28"], "id_b": ["d03", "d04", "d05", "d06"]}
    )
    pairs.write_parquet(project / "paare.parquet")
    (project / "validierung" / PROJECT / "codebuch.toml").write_text(
        CODEBOOK.replace('unit = "document"', 'unit = "document_pair"')
        .replace("size = 9", "size = 2")
        .replace('stratum = "paper_type"', ""),
        encoding="utf-8",
    )
    assert (
        main(["validate", "sample", PROJECT, "--population", str(project / "paare.parquet")]) == 0
    )
    sample = pl.read_csv(project / "validierung" / PROJECT / "stichprobe.csv")
    assert sample.columns == ["id", "id_a", "id_b", "schicht", "schicht_n"]
    assert set(sample.get_column("id")) <= {"d00|d03", "d01|d04", "d02|d05"}  # d28 ohne Text


# --- Stichprobe als Funktion -------------------------------------------------------------------


def test_the_sample_does_not_depend_on_the_order_of_the_population() -> None:
    corpus = corpus_frame()
    codebook = _codebook()
    forward = draw_sample(corpus, codebook).frame
    backward = draw_sample(corpus.reverse(), codebook).frame
    assert forward.equals(backward)


def test_a_span_population_keeps_document_and_offsets() -> None:
    spans = pl.DataFrame(
        {"id": ["d00", "d00", "d01"], "start": [0, 5, 3], "end": [4, 9, 8], "kind": ["x"] * 3}
    )
    codebook = _codebook(
        CODEBOOK.replace('unit = "document"', 'unit = "span"')
        .replace("size = 9", "size = 3")
        .replace('stratum = "paper_type"', 'stratum = "kind"')
    )
    sample = draw_sample(spans, codebook).frame
    assert sample.columns == ["id", "dokument", "start", "end", "kind", "schicht", "schicht_n"]
    assert sample.get_column("id").to_list() == ["d00|0|4|x", "d00|5|9|x", "d01|3|8|x"]


def test_a_doubled_unit_is_a_schema_error() -> None:
    corpus = pl.concat([corpus_frame(), corpus_frame().head(1)])
    with pytest.raises(SchemaError, match="mehrfach"):
        draw_sample(corpus, _codebook())


def test_a_key_with_the_separator_is_a_schema_error() -> None:
    corpus = corpus_frame().with_columns(pl.col("id").str.replace("d01", "d|01"))
    with pytest.raises(SchemaError, match="'|'"):
        draw_sample(corpus, _codebook())


def test_without_any_text_there_is_nothing_to_draw() -> None:
    with pytest.raises(EmptyResultError, match="keine Einheit"):
        draw_sample(corpus_frame(), _codebook(), frozenset())


def test_the_stored_sample_reads_back(project: Path) -> None:
    assert main(["validate", "sample", PROJECT]) == 0
    paths = validation_paths(load_settings(cwd=project), PROJECT)
    frame = read_sample(paths, load_codebook(paths.codebook, PROJECT))
    assert frame.height == 9 and frame.schema["id"] == pl.String


def test_the_validation_settings_stay_out_of_the_fingerprint(project: Path) -> None:
    """Kein Schritt der Kette liest sie; ein anderer Ordner soll nichts neu rechnen lassen."""
    base = load_settings(cwd=project)
    (project / "settings.local.toml").write_text(
        'validation.coding_root = "/anderswo"\nvalidation.min_alpha = 0.7\n', encoding="utf-8"
    )
    moved = load_settings(cwd=project)
    assert moved.validation.min_alpha == 0.7 and moved.fingerprint() == base.fingerprint()


def test_the_stored_sample_keeps_leading_zeros(project: Path) -> None:
    """Review 2026-11-23, Befund 7: ohne Typvorgabe wurde die Kennung „010" zur Zahl 10."""
    pairs = pl.DataFrame({"id_a": ["010", "011"], "id_b": ["d03", "d04"]})
    pairs.write_parquet(project / "paare.parquet")
    (project / "validierung" / PROJECT / "codebuch.toml").write_text(
        CODEBOOK.replace('unit = "document"', 'unit = "document_pair"')
        .replace("size = 9", "size = 2")
        .replace('stratum = "paper_type"', "require_text = false"),
        encoding="utf-8",
    )
    assert (
        main(["validate", "sample", PROJECT, "--population", str(project / "paare.parquet")]) == 0
    )
    paths = validation_paths(load_settings(cwd=project), PROJECT)
    frame = read_sample(paths, load_codebook(paths.codebook, PROJECT))
    assert frame.get_column("id_a").to_list() == ["010", "011"]
    assert frame.schema["schicht_n"] == pl.Int64


def test_a_key_column_names_the_unit_and_keeps_the_document() -> None:
    population = corpus_frame().with_columns((pl.lit("aufgabe-") + pl.col("id")).alias("aufgabe"))
    codebook = _codebook(CODEBOOK.replace("[sample]\n", '[sample]\nkey = "aufgabe"\n'))
    sample = draw_sample(population, codebook).frame
    assert sample.columns == ["id", "dokument", "schicht", "schicht_n"]
    assert all(i == "aufgabe-" + d for i, d in sample.select("id", "dokument").iter_rows())


def test_a_long_context_value_is_refused() -> None:
    """Kontextspalten landen in stichprobe.csv im Repo: kein Ratstext (Befund 8)."""
    codebook = _codebook(CODEBOOK.replace("[text]\n", '[text]\ncontext = ["text"]\n'))
    with pytest.raises(SchemaError, match="context_chars"):
        draw_sample(corpus_frame(), codebook)
