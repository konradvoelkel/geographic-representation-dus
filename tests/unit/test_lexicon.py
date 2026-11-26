"""Das Lexikon von Vorhaben 17 (``analysis.lexicon``): Laden, Kategorien je Dokument, Stellen im Text.

Je Kategorie ein Treffer und ein Nichttreffer; die Fehler, die die Kodierung und die zeitliche
Gegenprobe gefunden haben (Messdokument 17, § 3.4 und § 4.1), sind als bekannte Fehler von Version 1
festgeschrieben: „Energiesicherungsstelle" trifft die Energiekrise, „genderneutrale" Toiletten
treffen das Gendern, eine Webadresse die Energiewende. Version 2 würde das ändern und braucht eine
frische Stichprobe (Frage 9.16); bis dahin müssen diese Tests so bleiben.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import polars as pl
import pytest

from georep.analysis.lexicon import (
    EVENT,
    MIN_PRECISION,
    STRUCTURE,
    VOCABULARY_SCHEMA,
    document_categories,
    find_in_text,
    load_lexicon,
    parse_lexicon,
    validated_precision,
)
from georep.errors import SchemaError

REPO = Path(__file__).resolve().parents[2]
MEASURED = REPO / "docs" / "plans" / "17-zeit-lexikon.toml"
LEXICON = load_lexicon("bundespolitik")

# (Kategorie, Text mit Treffer, Text ohne Treffer), kleingeschrieben wie der Textstore
CASES = [
    ("migration_asyl", "unterbringung geflüchteter menschen", "das tierasyl am stadtrand"),
    ("klima_energie", "nach dem gebäudeenergiegesetz", "klimaschutz der stadt"),
    ("sozialstaat", "anträge auf wohngeld", "das sozialticket der stadt"),
    ("gendern", "das gendersternchen in briefen", "der gleichstellungsplan"),
    ("bundesverkehr", "das deutschlandticket ab mai", "die neue stadtbahnlinie"),
    ("wohnen_bund", "die mietpreisbremse gilt", "das wohnungsbauprogramm"),
    ("cannabis", "anbauvereinigungen für cannabis", "hanf als rohstoff"),
    ("corona", "in der corona-krise", "die krone der schöpfung"),
    ("ukraine_krieg", "geflüchtete aus der ukraine", "die partnerstadt in russland"),
    ("energiekrise", "die gasmangellage im winter", "die energieberatung der stadtwerke"),
]
# Bekannte Fehler von Version 1 (Messdokument 17, § 3.4 und § 4.1): sie treffen, gemeint ist
# etwas anderes.
KNOWN_ERRORS = [
    ("energiekrise", "die energiesicherungsstelle des amtes 50"),
    ("gendern", "genderneutrale toiletten im rathaus"),
    ("klima_energie", "www.mittelstand-energiewende.de"),
    ("ukraine_krieg", "ukrainische musik der sechziger jahre"),
]


def _corpus(*texts: tuple[str, str, str]) -> pl.DataFrame:
    return pl.DataFrame(texts, schema=["id", "name", "text"], orient="row")


def test_the_packaged_lexicon_is_the_measured_version_one_unchanged() -> None:
    assert LEXICON.version == "2026-11-23.1"
    assert LEXICON.digest == hashlib.sha256(MEASURED.read_bytes()).hexdigest()
    assert LEXICON.ids == (
        "migration_asyl",
        "klima_energie",
        "sozialstaat",
        "gendern",
        "bundesverkehr",
        "wohnen_bund",
        "cannabis",
        "corona",
        "ukraine_krieg",
        "energiekrise",
    )
    assert len(LEXICON.of_kind(STRUCTURE)) == 7 and len(LEXICON.of_kind(EVENT)) == 3
    assert sum(len(c.patterns) for c in LEXICON.categories) == 95  # Messdokument 17, § 3
    assert [c.id for c in LEXICON.local] == ["hochwasser"]  # geladen, nie gezählt
    assert LEXICON.label == "bundespolitik 2026-11-23.1"


def test_version_one_is_validated_above_the_criterion() -> None:
    assert validated_precision(LEXICON) == 0.94
    assert validated_precision(LEXICON) >= MIN_PRECISION  # type: ignore[operator]


def test_a_new_version_is_not_validated_until_it_is_coded() -> None:
    text = MEASURED.read_text(encoding="utf-8").replace('"2026-11-23.1"', '"2026-11-24.2"', 1)
    assert validated_precision(parse_lexicon("bundespolitik", text)) is None


@pytest.mark.parametrize(("category", "hit", "miss"), CASES)
def test_each_category_has_a_hit_and_a_miss(category: str, hit: str, miss: str) -> None:
    found = document_categories(_corpus(("a", "", hit), ("b", "", miss)), LEXICON)
    assert category in found.row(0, named=True)["kategorien"]
    assert found.row(1, named=True)["kategorien"] == []


@pytest.mark.parametrize(("category", "text"), KNOWN_ERRORS)
def test_the_known_errors_of_version_one_still_hit(category: str, text: str) -> None:
    found = document_categories(_corpus(("a", "", text)), LEXICON)
    assert category in found.row(0, named=True)["kategorien"]


def test_categories_stand_in_lexicon_order_and_the_head_reads_only_the_start() -> None:
    late = "x" * 2500 + " corona"
    corpus = _corpus(
        ("b", "Antrag zur Mietpreisbremse", "flüchtlinge und die energiekrise"),
        ("a", "", late),
        ("c", "Bericht", ""),
    )
    found = document_categories(corpus, LEXICON)
    assert found.schema == VOCABULARY_SCHEMA
    assert found.get_column("id").to_list() == ["a", "b", "c"]  # sortiert nach id
    rows = {r["id"]: r for r in found.iter_rows(named=True)}
    # der Titel zählt mit, kleingeschrieben; die Folge ist die des Lexikons
    assert rows["b"]["kategorien"] == ["migration_asyl", "wohnen_bund", "energiekrise"]
    assert rows["b"]["kopf"] == rows["b"]["kategorien"]
    # hinter 2 000 Zeichen nur in kategorien, nicht im Kopf (S3.1)
    assert rows["a"]["kategorien"] == ["corona"] and rows["a"]["kopf"] == []
    assert rows["c"]["kategorien"] == [] and rows["c"]["lexikon"] == LEXICON.label


def test_a_document_without_text_carries_what_its_title_carries() -> None:
    found = document_categories(_corpus(("a", "Anfrage zum Bürgergeld", "")), LEXICON)
    assert found.row(0, named=True)["kategorien"] == ["sozialstaat"]


def test_find_in_text_returns_the_places_of_each_category() -> None:
    text = "flüchtlinge aus der ukraine und flüchtlinge aus syrien"
    categories = [c for c in LEXICON.categories if c.id in ("migration_asyl", "ukraine_krieg")]
    found = find_in_text(text, categories)
    assert found == [
        (0, 10, "migration_asyl"),
        (20, 26, "ukraine_krieg"),
        (32, 42, "migration_asyl"),
    ]
    assert [text[s:e] for s, e, _ in found] == ["flüchtling", "ukrain", "flüchtling"]


def test_find_in_text_keeps_the_hits_of_every_category_in_order_of_place() -> None:
    both = [c for c in LEXICON.categories if c.id in ("energiekrise", "klima_energie")]
    found = find_in_text("energiewende und energiekrise", both)
    assert [k for _, _, k in found] == ["klima_energie", "energiekrise"]


HEAD = """
[meta]
name = "test"
version = "1"
"""


def test_a_lexicon_needs_meta_and_categories() -> None:
    with pytest.raises(SchemaError, match="name und version"):
        parse_lexicon("t", "[meta]\nname = 'x'\n")
    with pytest.raises(SchemaError, match="keine"):
        parse_lexicon("t", HEAD)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('id = "a"\nname = "A"\nart = "partei"\nmuster = ["x"]', "art"),
        ('id = "a"\nname = "A"\nart = "struktur"\nmuster = []', "muster"),
        ('id = "a"\nname = "A"\nart = "struktur"', "muster fehlt"),
        ('id = "a"\nname = "A"\nart = "struktur"\nmuster = ["("]', "übersetzt nicht"),
        # Python kann Lookbehind, Polars nicht: ein Muster muss in beiden gelten
        ('id = "a"\nname = "A"\nart = "struktur"\nmuster = ["(?<=a)b"]', "übersetzt nicht"),
    ],
)
def test_a_broken_category_fails_on_load(body: str, message: str) -> None:
    with pytest.raises(SchemaError, match=message):
        parse_lexicon("t", HEAD + "[[kategorie]]\n" + body + "\n")


def test_ids_are_unique_across_categories_and_local_events() -> None:
    body = '[[kategorie]]\nid = "a"\nname = "A"\nart = "struktur"\nmuster = ["x"]\n'
    local = '[[lokal]]\nid = "a"\nname = "A"\nmuster = ["y"]\n'
    with pytest.raises(SchemaError, match="doppelt"):
        parse_lexicon("t", HEAD + body + local)


def test_an_unknown_lexicon_names_the_file_it_looked_for() -> None:
    with pytest.raises(SchemaError, match="lexika/gibtsnicht.toml"):
        load_lexicon("gibtsnicht")
