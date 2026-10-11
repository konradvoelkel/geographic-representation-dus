"""Urheber je Dokument: ein Beispiel je Quelle und Klasse, mit den Mustern aus defaults.toml."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import polars as pl
import pytest
from syrupy.assertion import SnapshotAssertion

from georep.analysis.parties import (
    ART,
    PARTEIEN,
    QUELLE,
    TREFFER,
    URHEBER_ARTEN,
    Patterns,
    classify_document,
    classify_originators,
    documents_per_party,
    originator_figures,
)
from georep.layout import Layout
from georep.oparl import OparlOrganization
from georep.prep.papers import build_corpus
from georep.settings import Originators, Settings
from georep.stores import PaperStore, TextStore

ORG = "http://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/organizations"


@pytest.fixture(scope="module")
def originators(default_settings: Settings) -> Originators:
    return default_settings.originators


@pytest.fixture(scope="module")
def patterns(originators: Originators) -> Patterns:
    return Patterns.from_settings(originators)


def _classify(patterns: Patterns, **kwargs: object) -> tuple[str, tuple[str, ...], str]:
    found = classify_document(
        str(kwargs.get("paper_type", "") or ""),
        str(kwargs.get("name", "") or ""),
        str(kwargs.get("text", "") or ""),
        patterns,
        tuple(kwargs.get("urls", ()) or ()),  # type: ignore[arg-type]
    )
    return found.art, found.parteien, found.quelle


def test_administration_and_citizen_input_come_from_the_paper_type(patterns: Patterns) -> None:
    assert _classify(patterns, paper_type="Beschlussvorlage") == ("Verwaltung", (), "paper_type")
    assert (
        _classify(patterns, paper_type="Bezirksvertretung Informationsvorlage")[0] == "Verwaltung"
    )
    assert _classify(patterns, paper_type="Eingabe nach 24GO") == ("Eingabe", (), "paper_type")
    assert _classify(patterns, paper_type="Eingabe nach 24 GO")[0] == "Eingabe"
    # Eine Verwaltungsvorlage, die eine Fraktion zitiert, bleibt Verwaltung: paper_type gewinnt
    assert _classify(
        patterns,
        paper_type="Beschlussvorlage",
        name="Tempo 30 (die CDU-Fraktion beantragt)",
        text="(antrag cdu-fraktion vom 3. august 2023)",
    ) == ("Verwaltung", (), "paper_type")


def test_the_paper_type_names_the_fraction(patterns: Patterns) -> None:
    assert _classify(patterns, paper_type="Anfrage SPD") == ("Fraktion", ("SPD",), "paper_type")
    assert _classify(patterns, paper_type="Antrag CDU/Grüne") == (
        "Fraktion",
        ("CDU", "GRUENE"),
        "paper_type",
    )
    # Schreibvarianten des Servers: AFD, Die Partei-KlimaFraktion, SPD / Die Linke
    assert _classify(patterns, paper_type="Haushaltsantrag AFD") == (
        "Fraktion",
        ("AfD",),
        "paper_type",
    )
    assert _classify(patterns, paper_type="Haushaltsantrag Die Partei-KlimaFraktion") == (
        "Fraktion",
        ("PARTEI",),
        "paper_type",
    )
    assert _classify(patterns, paper_type="Antrag SPD / Die Linke") == (
        "Fraktion",
        ("SPD", "Die_Linke"),
        "paper_type",
    )
    assert _classify(patterns, paper_type="Anfrage Tierschutz/FREIE WÄHLER") == (
        "Fraktion",
        ("T_FW",),
        "paper_type",
    )
    assert _classify(patterns, paper_type="Anfrage Bündnis 90/Die Grünen")[1] == ("GRUENE",)
    # „zAnfrage REP" nennt eine Partei ohne Muster: die Klasse fällt auf die nächsten Quellen
    assert _classify(patterns, paper_type="zAnfrage REP") == ("unbekannt", (), "")


def test_the_title_names_the_fraction_only_behind_a_marker(patterns: Patterns) -> None:
    assert _classify(
        patterns, paper_type="Antrag", name="Glasfaser Hellerhof - Anfrage der SPD-Fraktion -"
    ) == ("Fraktion", ("SPD",), "name")
    assert _classify(
        patterns,
        paper_type="Anfrage",
        name="Tempo 30 (Antrag CDU-Fraktion und Fraktion Bündnis 90/Die Grünen)",
    ) == ("Fraktion", ("CDU", "GRUENE"), "name")
    # Ohne Fraktionsmarker wird der Titel nicht befragt: „CDU-nahe Stiftung" ist kein CDU-Antrag
    assert _classify(patterns, paper_type="Antrag", name="Spende an eine CDU-nahe Stiftung") == (
        "unbekannt",
        (),
        "",
    )


def test_interfractional_motions_are_a_fraction_without_a_party(patterns: Patterns) -> None:
    art, parteien, quelle = _classify(
        patterns, paper_type="Antrag", name="Interfraktioneller Antrag der Ratsfraktionen"
    )
    assert (art, parteien, quelle) == ("Fraktion", (), "name")
    # Nennt der interfraktionelle Antrag die Fraktionen, zählen sie alle
    assert _classify(
        patterns,
        paper_type="Antrag",
        name="Interfraktioneller Antrag der Ratsfraktionen von CDU, BÜNDNIS 90/DIE GRÜNEN, SPD, FDP",
    )[1] == ("CDU", "GRUENE", "SPD", "FDP")


def test_the_text_head_catches_what_the_title_hides(patterns: Patterns) -> None:
    assert _classify(
        patterns,
        paper_type="Anfrage",
        name="nichts neues vom kalkumer schloss?",
        text="sachverhalt (anfrage cdu-fraktion vom 28. juli 2023) die verwaltung antwortet",
    ) == ("Fraktion", ("CDU",), "text")
    assert _classify(
        patterns,
        paper_type="Anfrage",
        name="freiwillige feuerwehr",
        text="(anfrage frau irmer, spd-fraktion, vom 2. august 2023)",
    ) == ("Fraktion", ("SPD",), "text")
    # Jenseits des Kopfs zählt nichts mehr
    far = "x" * patterns.head_chars + " (antrag cdu-fraktion vom 1. mai 2024)"
    assert _classify(patterns, paper_type="Antrag", name="egal", text=far) == ("unbekannt", (), "")


def test_persons_and_the_unknown_rest(patterns: Patterns) -> None:
    assert _classify(
        patterns, paper_type="Anfrage", name="Anfrage der Bezirksvertreterin Claudia Drossel"
    ) == ("Person", (), "name")
    assert _classify(patterns, paper_type="Antrag", name="Antrag des Herrn Wozny (ZENTRUM)") == (
        "Person",
        (),
        "name",
    )
    assert _classify(patterns, paper_type="", name="", text="") == ("unbekannt", (), "")
    assert _classify(patterns, paper_type="Antrag", name="Freiwillige Feuerwehr") == (
        "unbekannt",
        (),
        "",
    )


def test_oparl_beats_every_pattern(patterns: Patterns) -> None:
    """Liefert der Server originatorOrganization, gewinnt es, auch gegen einen Verwaltungstyp."""
    found = classify_document(
        "Beschlussvorlage", "Antrag der SPD-Fraktion", "", patterns, (f"{ORG}/gr/49",)
    )
    assert (found.art, found.parteien, found.quelle) == ("Fraktion", ("FDP",), "oparl")
    assert found.treffer == f"{ORG}/gr/49"
    # Eine URL ohne Zuordnung (ein Amt) lässt die Muster weiterarbeiten
    other = classify_document("Anfrage SPD", "", "", patterns, (f"{ORG}/amt/66",))
    assert (other.art, other.parteien, other.quelle) == ("Fraktion", ("SPD",), "paper_type")


def test_organizations_from_the_server_map_urls_without_settings(patterns: Patterns) -> None:
    """CDU und GRÜNE stehen nicht in der Fixture; ihre Abbildung kommt aus synthetischen Objekten."""
    enriched = patterns.with_organizations(
        [
            OparlOrganization(id=f"{ORG}/gr/900", name="CDU-Ratsfraktion", shortName="CDU"),
            OparlOrganization(
                id=f"{ORG}/gr/901",
                name="Ratsfraktion BÜNDNIS 90/DIE GRÜNEN",
                shortName="BÜ 90/GRÜNE",
            ),
            OparlOrganization(
                id=f"{ORG}/gr/902", name="Ratsfraktion SPD/Volt", shortName="SPD/Volt"
            ),
            OparlOrganization(
                id=f"{ORG}/gr/903", name="Ordnungs- und Verkehrsausschuss", shortName="OVA"
            ),
            OparlOrganization(id=f"{ORG}/gr/904", name="FDP-Ratsfraktion", deleted=True),
        ]
    )
    assert enriched.parties_for_urls([f"{ORG}/gr/900"])[0] == ("CDU",)
    assert enriched.parties_for_urls([f"{ORG}/gr/901"])[0] == ("GRUENE",)
    assert enriched.parties_for_urls([f"{ORG}/gr/902"])[0] == ("SPD", "VOLT")
    assert enriched.parties_for_urls([f"{ORG}/gr/903"])[0] == ()  # ein Ausschuss ist keine Partei
    assert enriched.parties_for_urls([f"{ORG}/gr/904"])[0] == ()  # deleted bleibt draußen
    assert enriched.parties_for_urls([f"{ORG}/gr/49"])[0] == (
        "FDP",
    )  # Endungen der Settings gelten weiter


# --- über die Mini-Fixture -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def mini_attribution(
    mini_root: Path, default_settings: Settings, tmp_path_factory: pytest.TempPathFactory
) -> pl.DataFrame:
    from georep.bootstrap import bootstrap

    root = tmp_path_factory.mktemp("attribution")
    layout = Layout(root / "data", root / "cache", mini_root)
    bootstrap(layout)
    corpus = build_corpus(PaperStore(layout.papers).load().values(), TextStore(layout.texts))
    return classify_originators(corpus, default_settings.originators)


def test_attribution_on_the_mini_fixture(
    mini_attribution: pl.DataFrame, default_settings: Settings
) -> None:
    assert mini_attribution.columns == ["id", ART, PARTEIEN, QUELLE, TREFFER]
    assert mini_attribution.height == 200 and mini_attribution.get_column("id").is_sorted()
    figures = originator_figures(mini_attribution)
    assert set(figures) == set(URHEBER_ARTEN) and sum(figures.values()) == 200
    assert figures["Verwaltung"] > figures["Fraktion"] > 0  # Vorlagen sind die Mehrheit
    per_party = documents_per_party(mini_attribution, default_settings.originators.parties)
    assert set(per_party) == set(default_settings.columns.results.parties)
    # Fünf der sechs Parteien kommen vor; die AfD stellt in den 200 Dokumenten keines (Plan § 3.5)
    assert sum(1 for count in per_party.values() if count > 0) == 5
    assert per_party["AfD"] == 0


def test_attribution_counts_are_stable(
    mini_attribution: pl.DataFrame, default_settings: Settings, snapshot: SnapshotAssertion
) -> None:
    """Kleiner, stabiler Snapshot: Klassen und Parteien auf den 200 Dokumenten der Fixture."""
    assert {
        "klassen": originator_figures(mini_attribution),
        "parteien": documents_per_party(
            mini_attribution,
            (*default_settings.originators.parties, *default_settings.originators.groups),
        ),
        "quellen": dict(sorted(mini_attribution.group_by(QUELLE).len().iter_rows())),
    } == snapshot


def test_classification_is_idempotent(mini_attribution: pl.DataFrame) -> None:
    """Die Zuordnung hängt nur von den vier Feldern ab, nicht von vorherigen Läufen."""
    assert mini_attribution.equals(mini_attribution.sort("id"))


def test_corpus_without_the_originator_column_still_classifies(
    default_settings: Settings,
) -> None:
    """Der Schritt läuft auch auf einem Korpus aus Schema 2 (ohne die vier Listenspalten)."""
    corpus = pl.DataFrame(
        {
            "id": ["b", "a"],
            "paper_type": ["Anfrage SPD", "Beschlussvorlage"],
            "name": ["x", "y"],
            "text": ["", ""],
            "date": [dt.date(2024, 1, 1)] * 2,
        }
    )
    found = classify_originators(corpus, default_settings.originators)
    assert found.get_column("id").to_list() == ["a", "b"]
    assert found.get_column(ART).to_list() == ["Verwaltung", "Fraktion"]
