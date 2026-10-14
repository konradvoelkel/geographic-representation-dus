"""Urheber je Dokument: ein Beispiel je Quelle und Klasse, mit den Mustern aus defaults.toml."""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest
from syrupy.assertion import SnapshotAssertion

from georep.analysis.parties import (
    ART,
    KLASSEN_SPALTEN,
    PARTEI,
    PARTEIEN,
    PARTY_COLUMNS,
    PARTY_DEVIATION,
    PARTY_MEAN,
    PARTY_RATIO,
    QUELLE,
    TREFFER,
    URHEBER_ARTEN,
    Patterns,
    classify_document,
    classify_originators,
    documents_per_party,
    originator_figures,
    originators_by_district,
    party_correlations,
    party_hits,
)
from georep.errors import SchemaError
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
    from georep.bootstrap import bootstrap_from_settings

    root = tmp_path_factory.mktemp("attribution")
    layout = Layout(root / "data", root / "cache", mini_root)
    bootstrap_from_settings(layout, default_settings)
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


# --- aus der Stichprobe von 50 Dokumenten (2026-10-12): sieben Fälle, die „unbekannt" hießen ------


def test_abbreviations_in_the_text_head_do_not_stop_the_marker(patterns: Patterns) -> None:
    """``(anfrage frau dr.dr.hagen, fdp-fraktion, …)``: die Punkte in Abkürzungen standen vorher
    zwischen Antragswort und Fraktion (BV5/031/2022, BV5/158/2024)."""
    assert _classify(
        patterns,
        paper_type="Anfrage",
        name="Hochwasserschaden Alte Landstraße",
        text="hochwasserschaden alte landstraße(anfrage frau dr.dr.hagen, fdp-fraktion, vom 8. februar 2022)",
    ) == ("Fraktion", ("FDP",), "text")


def test_an_interfractional_motion_in_the_text_head_counts(patterns: Patterns) -> None:
    """``(interfraktioneller antrag …)`` nennt die Fraktion vor dem Antragswort (BV5/109/2023)."""
    assert _classify(
        patterns,
        paper_type="Antrag",
        name="Dringlichkeitsantrag: Situation rund um den Anker verträglich gestalten",
        text="dringlichkeitsantrag: situation rund um den anker auch in zukunft verträglich gestalten "
        "- gemeinsamer austausch mit anliegern, verwaltung, schulen und politik (interfraktioneller "
        "antrag) die bezirksvertretung bittet",
    ) == ("Fraktion", (), "text")


def test_a_party_in_brackets_without_the_word_fraction(patterns: Patterns) -> None:
    """``(Antrag BÜNDNIS 90/DIE GRÜNEN)``: eine Partei ohne das Wort „Fraktion" (BV3/065/2021)."""
    assert _classify(
        patterns,
        paper_type="Antrag",
        name="Modellversuch Tempo 30 auf der Corneliusstraße (Antrag BÜNDNIS 90/DIE GRÜNEN)",
    ) == ("Fraktion", ("GRUENE",), "name")
    # Ohne Antragsklammer bleibt der Titel unbefragt: „CDU-nahe Stiftung" ist kein CDU-Antrag
    assert _classify(patterns, paper_type="Antrag", name="Spende an eine CDU-nahe Stiftung") == (
        "unbekannt",
        (),
        "",
    )


def test_a_single_representative_in_brackets_is_a_person(patterns: Patterns) -> None:
    """Person schlägt die Antragsklammer: „(Anfrage Herr Driesch - DIE LINKE)" ist eine Anfrage
    eines Bezirksvertreters, keine Fraktionsanfrage (BV3/141/2025, BV3/040/2024, BV8/243/2022).
    So bleibt es gleich, ob der Titel „Herrn Salinger; AfD" oder „(Antrag Herr X - Partei)" sagt."""
    for title in (
        "Sozialer Wohnungsbau im Bezirk 3 (Anfrage Herr Driesch - DIE LINKE)",
        "Begrünung Stadtteilzentrum Bilk (Antrag Herr Wolf - Bezirksbürgermeister)",
        "Beauftragte/r gegen Rechtsextremismus (Antrag Herr Lemmer-Freie Wähler)",
    ):
        assert _classify(patterns, paper_type="Antrag", name=title) == ("Person", (), "name")


def test_a_typo_in_the_source_still_names_the_fraction(patterns: Patterns) -> None:
    """„Antrag der CDU-Frakion" (BV7/018/2025) ist ein Tippfehler des Ratsinformationssystems;
    ``frak\\w{0,2}ion`` fängt ihn, ohne die Klasse zu raten."""
    assert _classify(
        patterns,
        paper_type="Antrag",
        name="Situation in Gerresheim an Silvester 2024/2025 - Antrag der CDU-Frakion -",
    ) == ("Fraktion", ("CDU",), "name")


# --- Kennzahlen je Wahlbezirk und Partei ----------------------------------------------------------


def _toy() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Drei Wahlbezirke, sieben Dokumente, zwei Parteien; von Hand nachgerechnet."""
    results = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2, 3],
            "paper_ids": [["a", "b", "c"], ["b", "d"], ["e", "f", "g"]],
            "anzahl_treffer": [3, 2, 3],
        },
        schema={
            "wahlkreis_id": pl.Int64,
            "paper_ids": pl.List(pl.String),
            "anzahl_treffer": pl.Int64,
        },
    )
    documents = pl.DataFrame(
        {
            "id": ["a", "b", "c", "d", "e", "f", "g"],
            ART: [
                "Fraktion",
                "Fraktion",
                "Verwaltung",
                "Person",
                "Fraktion",
                "Eingabe",
                "Fraktion",
            ],
            PARTEIEN: [["CDU"], ["CDU", "SPD"], [], [], ["SPD"], [], ["SPD"]],
        },
        schema={"id": pl.String, ART: pl.String, PARTEIEN: pl.List(pl.String)},
    )
    voters = pl.DataFrame(
        {
            "wahlkreis_id": [1, 2, 3],
            "Wahlberechtigte_insgesamt": [100, 200, 400],
            "CDU_Stimmen": [40, 0, 80],
            "SPD_Stimmen": [20, 60, 100],
            "CDU_anteil": [0.4, 0.0, 0.2],
            "SPD_anteil": [0.2, 0.3, 0.25],
        },
        schema={
            "wahlkreis_id": pl.Int64,
            "Wahlberechtigte_insgesamt": pl.Int64,
            "CDU_Stimmen": pl.Int64,
            "SPD_Stimmen": pl.Int64,
            "CDU_anteil": pl.Float64,
            "SPD_anteil": pl.Float64,
        },
    )
    return results, documents, voters


def test_the_classes_partition_the_hits_of_every_district() -> None:
    results, documents, _ = _toy()
    found = originators_by_district(results, documents)
    assert found.columns == ["wahlkreis_id", "anzahl_treffer", *KLASSEN_SPALTEN]
    rows = {r["wahlkreis_id"]: r for r in found.iter_rows(named=True)}
    # Bezirk 1: a, b Fraktion, c Verwaltung -> 2 + 1 = 3
    assert (rows[1]["fraktion"], rows[1]["verwaltung"], rows[1]["anzahl_treffer"]) == (2, 1, 3)
    # Bezirk 2: b Fraktion, d Person; Bezirk 3: e und g Fraktion, f Eingabe
    assert (rows[2]["fraktion"], rows[2]["person"]) == (1, 1)
    assert (rows[3]["fraktion"], rows[3]["eingabe"]) == (2, 1)
    for row in found.iter_rows(named=True):
        assert sum(row[c] for c in KLASSEN_SPALTEN) == row["anzahl_treffer"]


def test_a_document_missing_from_the_attribution_is_a_schema_error() -> None:
    results, documents, _ = _toy()
    with pytest.raises(SchemaError, match="fehlen in der Urheber-Tabelle"):
        originators_by_district(results, documents.filter(pl.col("id") != "d"))


def test_party_hits_counts_cooperations_for_both_and_marks_who_ran(
    default_settings: Settings,
) -> None:
    results, documents, voters = _toy()
    parties = [p for p in default_settings.originators.parties if p.key in ("CDU", "SPD")]
    found = party_hits(results, documents, voters, parties)
    assert found.height == 3 * 2 and found.columns == list(PARTY_COLUMNS)
    rows = {(r["partei"], r["wahlkreis_id"]): r for r in found.iter_rows(named=True)}
    # CDU: a (allein) und b (mit SPD) in Bezirk 1, b in Bezirk 2, nichts in Bezirk 3
    assert (rows[("CDU", 1)]["anzahl_treffer"], rows[("CDU", 1)]["treffer_allein"]) == (2, 1)
    assert (rows[("CDU", 2)]["anzahl_treffer"], rows[("CDU", 2)]["treffer_allein"]) == (1, 0)
    assert rows[("CDU", 3)]["anzahl_treffer"] == 0
    # dokumente_partei: CDU a und b, SPD b, e und g; je Partei konstant
    assert {rows[("CDU", d)]["dokumente_partei"] for d in (1, 2, 3)} == {2}
    assert {rows[("SPD", d)]["dokumente_partei"] for d in (1, 2, 3)} == {3}
    assert rows[("CDU", 1)]["anteil_dokumente"] == 1.0  # 2 von 2
    assert rows[("CDU", 1)]["trefferquote"] == pytest.approx(2 / 100)
    assert rows[("SPD", 3)]["anzahl_treffer"] == 2 and rows[("SPD", 3)]["treffer_allein"] == 2
    assert rows[("SPD", 3)]["anteil_dokumente"] == pytest.approx(2 / 3)
    # Bezirk 2 ohne CDU-Wahlvorschlag: angetreten falsch, der Anteil 0 bedeutet dort nichts
    assert rows[("CDU", 2)]["stimmen"] == 0 and rows[("CDU", 2)]["angetreten"] is False
    assert rows[("CDU", 1)]["angetreten"] is True and rows[("SPD", 2)]["angetreten"] is True


def test_the_party_mean_is_unweighted_and_the_deviations_cancel(
    default_settings: Settings,
) -> None:
    """Punkt 46: Mittel, Abweichung und Verhältnis je Wahlbezirk, von Hand nachgerechnet."""
    results, documents, voters = _toy()
    parties = [p for p in default_settings.originators.parties if p.key in ("CDU", "SPD")]
    found = party_hits(results, documents, voters, parties)
    rows = {(r[PARTEI], r["wahlkreis_id"]): r for r in found.iter_rows(named=True)}
    # Bezirk 1: CDU 2 von 2, SPD 1 von 3; das Mittel der beiden Anteile ist 2/3
    assert rows[("CDU", 1)][PARTY_MEAN] == pytest.approx(2 / 3)
    assert rows[("SPD", 1)][PARTY_MEAN] == pytest.approx(2 / 3)
    assert rows[("CDU", 1)][PARTY_DEVIATION] == pytest.approx(1 / 3)
    assert rows[("SPD", 1)][PARTY_DEVIATION] == pytest.approx(-1 / 3)
    assert rows[("CDU", 1)][PARTY_RATIO] == pytest.approx(1.5)
    assert rows[("SPD", 1)][PARTY_RATIO] == pytest.approx(0.5)
    # Bezirk 2: CDU 1 von 2, SPD 1 von 3; Mittel 5/12, die Verhältnisse 1,2 und 0,8
    assert rows[("CDU", 2)][PARTY_RATIO] == pytest.approx(1.2)
    assert rows[("SPD", 2)][PARTY_RATIO] == pytest.approx(0.8)
    # Bezirk 3: die CDU hat kein Dokument, das Verhältnis ist 0 und keine Division durch 0
    assert rows[("CDU", 3)][PARTY_RATIO] == 0.0
    assert rows[("CDU", 3)][PARTY_DEVIATION] == pytest.approx(-1 / 3)
    # Der Vertrag der Variante: je Wahlbezirk summieren sich die Abweichungen auf 0
    per_district = found.group_by("wahlkreis_id").agg(pl.col(PARTY_DEVIATION).sum())
    assert per_district.get_column(PARTY_DEVIATION).abs().max() == pytest.approx(0.0, abs=1e-12)


def test_party_correlations_skip_districts_where_the_party_did_not_run(
    default_settings: Settings,
) -> None:
    results, documents, voters = _toy()
    parties = [p for p in default_settings.originators.parties if p.key in ("CDU", "SPD")]
    table = party_hits(results, documents, voters, parties)
    by_key = {c.key: c for c in party_correlations(table)}
    assert set(by_key) == {"CDU", "SPD"}
    assert by_key["CDU"].n == 2 and by_key["SPD"].n == 3  # Bezirk 2 fehlt der CDU
    assert by_key["CDU"].documents == 2 and by_key["CDU"].hits == 3
    assert by_key["SPD"].documents == 3 and by_key["SPD"].hits == 4
    assert by_key["CDU"].districts_hit == 2 and by_key["SPD"].districts_hit == 3
    # Die CDU ist nur in zwei Bezirken angetreten, das ist unter min_n: kein r, kein p
    assert by_key["CDU"].r is None and by_key["CDU"].p is None
    assert by_key["SPD"].r is not None and -1.0 <= by_key["SPD"].r <= 1.0
    assert by_key["SPD"].p is not None and by_key["SPD"].rho is not None
    # Eine höhere Schranke nimmt auch der SPD das r, ohne dass die Funktion stolpert
    assert all(c.r is None and c.p is None for c in party_correlations(table, min_n=4))


def test_an_organization_key_outside_the_party_list_is_ignored(patterns: Patterns) -> None:
    """Von crosshair gefunden (2026-10-12): ``parties_for_urls`` sortierte mit ``keys.index`` und
    warf ValueError, wenn eine Organisation auf einen Schlüssel zeigte, den die Parteiliste nicht
    kennt. ``from_settings`` baut beides aus derselben Liste, aber ein Vertrag soll nicht an einer
    Sortierung zerschellen, sondern den unbekannten Schlüssel weglassen."""
    broken = replace(
        patterns, parties=(), org_suffixes=(("/organizations/gr/49", "FDP"),), org_exact={}
    )
    assert broken.parties_for_urls(["https://ris.invalid/organizations/gr/49"]) == ((), "")
    # Ein bekannter und ein unbekannter Schlüssel: der bekannte bleibt, in Settings-Reihenfolge
    mixed = replace(
        patterns,
        org_suffixes=(("/gr/49", "FDP"), ("/gr/99", "GIBTSNICHT"), ("/gr/44", "CDU")),
        org_exact={},
    )
    keys, hit = mixed.parties_for_urls(["https://x/gr/99", "https://x/gr/49", "https://x/gr/44"])
    assert keys == ("CDU", "FDP")  # Settings-Reihenfolge, nicht die der URLs
    assert "gr/49" in hit and "gr/44" in hit


def test_a_partyless_text_hit_still_lets_the_title_name_the_parties(patterns: Patterns) -> None:
    """BV3/134/2025 (Review-Befund 1, 2026-10-12): Der Textkopf trifft „beantragenden fraktionen",
    im Fenster steht keine Partei — vorher endete die Zuordnung dort mit Fraktion ohne Partei und
    das schwache Titel-Tor lief nicht mehr. Der Titel nennt alle drei Parteien in der Klammer."""
    title = "Lessingplatz – Gesamtkonzept (Antrag BÜNDNIS 90/DIE GRÜNEN, CDU, SPD)"
    head = (
        ": lessingplatz – gesamtkonzept (antrag bündnis 90/die grünen, cdu, spd) sehr geehrter "
        "herr bezirksbürgermeister, der lessingplatz mit seinen verschiedenen nutzungen bedarf "
        "aus der sicht der beantragenden fraktionen eine konzeptionellen überarbeitung"
    )
    assert _classify(patterns, paper_type="Antrag", name=title, text=head) == (
        "Fraktion",
        ("CDU", "GRUENE", "SPD"),
        "name",
    )


def test_beantragenden_is_not_an_antrag(patterns: Patterns) -> None:
    """Die Verbform zählt nicht: „der beantragenden fraktionen" ist kein „Antrag … Fraktion".
    Zusammensetzungen mit dem Antragswort bleiben erlaubt, auch die, in denen die
    PDF-Extraktion die Leerzeichen gefressen hat — eine Wortgrenze verlöre sechs Dokumente."""
    assert patterns.text is not None
    assert patterns.text.search("der beantragenden fraktionen eine überarbeitung") is None
    assert patterns.text.search("(haushaltsantrag der cdu-fraktion vom 1. mai 2024)") is not None
    assert patterns.text.search("(anfrage spd-fraktion vom 28. juli 2023)") is not None
    assert patterns.text.search("die antragsstellende liste und fraktion bitten sie") is not None
    assert patterns.text.search("(anfragefraktionbündnis90/diegrünenvom14.märz2022)") is not None


def test_an_interfractional_text_hit_without_a_title_bracket_stays_a_fraction(
    patterns: Patterns,
) -> None:
    """Ohne Parteien im Titel bleibt es bei Fraktion ohne Partei aus der Quelle text; die
    Personenmarker dürfen die Klasse nicht mehr umstoßen, nachdem der Kopf sie gesetzt hat."""
    assert _classify(
        patterns,
        paper_type="Antrag",
        name="Dringlichkeitsantrag: Situation rund um den Anker",
        text="dringlichkeitsantrag (interfraktioneller antrag) die bezirksvertretung bittet",
    ) == ("Fraktion", (), "text")


def test_a_structurally_wrong_organization_is_a_schema_error(tmp_path: Path) -> None:
    """Review-Befund 2: pydantic wirft ValidationError, der Rest der Kette kennt nur SchemaError.
    Ein kaputtes raw/organizations.json soll eine Zeile auf stderr geben, keinen Traceback."""
    from georep.analysis.parties import read_organizations

    path = tmp_path / "organizations.json"
    path.write_text('[{"name": "ohne id"}]', encoding="utf-8")
    with pytest.raises(SchemaError, match="organizations.json"):
        read_organizations(path)

    path.write_text("{ kaputt", encoding="utf-8")
    with pytest.raises(SchemaError, match="kein gültiges JSON"):
        read_organizations(path)
    path.write_text('{"data": []}', encoding="utf-8")
    with pytest.raises(SchemaError, match="Liste von Organisationen"):
        read_organizations(path)
    assert read_organizations(tmp_path / "fehlt.json") == ()


# --- Die Fundstelle: was in der Spalte ``treffer`` steht (Mutationslauf 2026-10-13) -------------
#
# ``_classify`` oben gibt die Fundstelle nicht zurück, und kein Test prüfte sie: in ``_excerpt``,
# in „der erste Treffer gewinnt" und in der Reihenfolge der Antragspräfixe überlebten darum
# Mutanten (docs/mutation-2026-10-13.md). Die Fundstelle ist die Spalte, mit der ein Mensch eine
# Zuordnung von Hand prüft -- sie ist kein Beiwerk.

SMALL = Originators(
    motion_prefixes=["antrag", "antrag der fraktion"],
    parties=[
        {"key": "CDU", "label": "CDU", "patterns": ["cdu"]},  # type: ignore[list-item]
        {"key": "SPD", "label": "SPD", "patterns": ["spd"]},  # type: ignore[list-item]
    ],
    fraction_markers=["fraktion"],
)


def test_the_longest_motion_prefix_is_stripped_first() -> None:
    """``antrag der fraktion`` muss vor ``antrag`` greifen, sonst bleibt die Hälfte stehen."""
    found = classify_document("Antrag der Fraktion CDU", "", "", Patterns.from_settings(SMALL))
    assert (found.art, found.parteien, found.quelle) == ("Fraktion", ("CDU",), "paper_type")
    assert found.treffer == "cdu"  # genau der Rest, nicht „der fraktion cdu"


def test_the_excerpt_shows_thirty_characters_around_the_first_match() -> None:
    """Der Auszug ist der Treffer mit 30 Zeichen links und rechts, an den Rändern beschnitten."""
    left, right = "x" * 40, "y" * 40
    title = f"{left} fraktion spd {right}"
    found = classify_document(None, title, "", Patterns.from_settings(SMALL))
    assert found.quelle == "name" and found.parteien == ("SPD",)
    # Das Fenster ist 30 Zeichen links und 30 rechts um „spd"; links fallen zehn „x" weg, weil
    # dort „ fraktion " steht, rechts endet der Titel nach 29 „y" -- gezeichnet:
    #   …xxxxxxxxxxxxxxxxxxxx fraktion spd yyyyyyyyy…
    #   |<-- 30 Zeichen links -->|      |<- 30 rechts, davon 29 vorhanden
    assert found.treffer == "x" * 20 + " fraktion spd " + "y" * 29


def test_the_first_party_in_the_text_wins_the_excerpt() -> None:
    """Zwei Parteien: der Auszug steht um den **frühesten** Treffer, nicht um den letzten.

    Die Reihenfolge in ``parteien`` bleibt die der Settings (CDU vor SPD); welche Stelle zitiert
    wird, entscheidet die Position im Text.
    """
    title = "fraktion spd " + "z" * 80 + " cdu"
    found = classify_document(None, title, "", Patterns.from_settings(SMALL))
    assert found.parteien == ("CDU", "SPD")  # Reihenfolge der Settings
    assert found.treffer.startswith("fraktion spd")  # Position im Titel
    assert "cdu" not in found.treffer


def test_a_document_without_a_head_or_an_organisation_still_classifies() -> None:
    """Im Korpus sind ``text`` und ``originator_organization`` nullbar; null heißt leer."""
    corpus = pl.DataFrame(
        {
            "id": ["b", "a"],
            "paper_type": ["Antrag CDU", None],
            "name": [None, "Fraktion SPD beantragt"],
            "text": [None, None],
            "originator_organization": [None, None],
        },
        schema={
            "id": pl.String,
            "paper_type": pl.String,
            "name": pl.String,
            "text": pl.String,
            "originator_organization": pl.List(pl.String),
        },
    )
    found = classify_originators(corpus, SMALL, ())
    assert found.get_column("id").to_list() == ["a", "b"]  # nach id sortiert
    assert found.get_column(ART).to_list() == ["Fraktion", "Fraktion"]
    assert found.get_column(PARTEIEN).to_list() == [["SPD"], ["CDU"]]
