"""Wahlergebnis zweier Quellformen in dieselben Spalten (Option 01, Stufe C).

Die Namen der Arbeit (``Wahlberechtigte_insgesamt``, ``Waehler``, ``<Partei>_Stimmen``) bleiben die
Ausgabe; die votemanager-Exporte der ITK Rheinland heißen ihre Spalten ``A``, ``B``, ``D1`` bis
``Dn`` und führen den Wahlbezirk nicht als Spalte, sondern in der Stimmbezirksnummer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from deal import ContractError
from pydantic import ValidationError

from georep.errors import SchemaError
from georep.prep.voters import (
    DISTRICT,
    ELIGIBLE_TOTAL,
    TURNOUT,
    VOTERS,
    aggregate_voters,
    canonical_names,
    read_results_csv,
)
from georep.settings import ResultsColumns, Settings, load_settings

# Mönchengladbach, AGS 05116000: Ratswahl 2025 je Stimmbezirk (docs/plans/01-staedte.md, § 3.2)
VOTEMANAGER = ResultsColumns(
    sep=";",
    encoding="utf-8",
    precinct="gebiet-nr",
    district_from_precinct=(1, 3),
    city_district="",  # votemanager führt keinen Stadtbezirk (Option 05 rechnet auf dem Ziel)
    eligible="A",
    voters="B",
    parties={"CDU": "D1", "SPD": "D2", "GRUENE": "D3"},
    party_names={"GRUENE": "GRÜNE"},
)
HEADER = "datum;wahl;ags;gebiet-nr;gebiet-name;A1;A;B;B2;C;D;D1;D2;D3"
ROWS = (
    # Wahlbezirk 04: zwei Urnenbezirke und ihr Briefwahlbezirk (dort ist A leer)
    "14.09.2025;Ratswahl;05116000;10401;Venn I;10;1000;500;0;5;495;200;180;115",
    "14.09.2025;Ratswahl;05116000;10402;Venn II;10;1200;600;0;6;594;250;200;144",
    "14.09.2025;Ratswahl;05116000;10497;Briefwahl Venn; ; ;300;300;3;297;150;100;47",
    # Wahlbezirk 22
    "14.09.2025;Ratswahl;05116000;32201;Wickrath I;10;800;400;0;4;396;100;200;96",
)


def _csv(tmp_path: Path, rows: tuple[str, ...] = ROWS, header: str = HEADER) -> Path:
    path = tmp_path / "Open-Data-05116000-Ratswahl-Stimmbezirk.csv"
    path.write_text("\n".join((header, *rows)) + "\n", encoding="utf-8")
    return path


def test_canonical_columns_are_the_names_of_the_thesis(default_settings: Settings) -> None:
    assert canonical_names(VOTEMANAGER) == {
        "A": ELIGIBLE_TOTAL,
        "B": VOTERS,
        "D1": "CDU_Stimmen",
        "D2": "SPD_Stimmen",
        "D3": "GRUENE_Stimmen",
    }
    # Für Düsseldorf ist die Umbenennung die Identität; der Golden Master merkt nichts davon
    duesseldorf = canonical_names(default_settings.columns.results)
    assert all(source == target for source, target in duesseldorf.items())


def test_votemanager_rows_aggregate_to_the_canonical_table(tmp_path: Path) -> None:
    frame = aggregate_voters(read_results_csv(_csv(tmp_path), VOTEMANAGER), VOTEMANAGER)
    assert frame.columns == [
        DISTRICT,
        ELIGIBLE_TOTAL,
        VOTERS,
        "CDU_Stimmen",
        "SPD_Stimmen",
        "GRUENE_Stimmen",
        TURNOUT,
        "CDU_anteil",
        "SPD_anteil",
        "GRUENE_anteil",
    ]
    rows = {row[DISTRICT]: row for row in frame.iter_rows(named=True)}
    assert sorted(rows) == [4, 22]
    assert rows[4][ELIGIBLE_TOTAL] == 2200  # die Briefwahlzeile trägt keine Wahlberechtigten
    assert rows[4][VOTERS] == 1400 and rows[4]["CDU_Stimmen"] == 600
    assert rows[4][TURNOUT] == pytest.approx(1400 / 2200)
    assert rows[22][ELIGIBLE_TOTAL] == 800 and rows[22]["GRUENE_Stimmen"] == 96


def test_a_results_csv_without_the_precinct_column_says_so(tmp_path: Path) -> None:
    path = _csv(tmp_path, header=HEADER.replace("gebiet-nr", "nummer"))
    with pytest.raises(SchemaError, match="gebiet-nr"):
        read_results_csv(path, VOTEMANAGER)


def test_a_byte_order_mark_does_not_become_part_of_the_first_column(tmp_path: Path) -> None:
    path = _csv(tmp_path)
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    frame = read_results_csv(path, VOTEMANAGER)
    assert frame.columns[0] == "datum"


def test_the_bom_goes_before_the_decoding_not_after(
    mini_root: Path, default_settings: Settings
) -> None:
    """Die Düsseldorfer CSV ist latin-1 mit UTF-8-BOM: dekodiert wird daraus „ï»¿", kein \ufeff.

    Nach der Dekodierung ist das Zeichen nicht mehr zu erkennen; der Name der ersten Spalte hieße
    dann „ï»¿datum" (Review 2026-10-12).
    """
    path = mini_root / "external" / "Stimmbezirk_Wahlergebnis.csv"
    assert path.read_bytes()[:3] == b"\xef\xbb\xbf"
    frame = read_results_csv(path, default_settings.columns.results)
    assert frame.columns[0] == "datum"


def test_canonical_columns_refuse_two_parties_on_one_source_column() -> None:
    """Zwei Parteien auf dieselbe Quellspalte ist ein Settings-Fehler, keine stille Zeile weniger."""
    columns = ResultsColumns(
        precinct="gebiet-nr",
        district_from_precinct=(1, 3),
        eligible="A",
        voters="B",
        parties={"CDU": "D1", "SPD": "D1"},
    )
    with pytest.raises(ContractError):
        canonical_names(columns)


def test_results_columns_demand_exactly_one_way_to_the_district() -> None:
    # Ohne beides ordnet der Crosswalk zu; das prüft Settings als Ganzes (Option 02), nicht hier
    with pytest.raises(ValidationError, match="district_from_precinct"):
        ResultsColumns(
            city_district="",
            district="Wahlbezirk",
            precinct="gebiet-nr",
            district_from_precinct=(1, 3),
            eligible="A",
            voters="B",
            parties={"CDU": "D1"},
        )
    with pytest.raises(ValidationError, match="precinct"):
        ResultsColumns(
            city_district="",
            district_from_precinct=(1, 3),
            eligible="A",
            voters="B",
            parties={"CDU": "D1"},
        )


def test_party_names_default_to_the_key_and_may_be_spelled_out(default_settings: Settings) -> None:
    assert VOTEMANAGER.display_name("GRUENE") == "GRÜNE"
    assert VOTEMANAGER.display_name("CDU") == "CDU"
    assert default_settings.columns.results.display_name("GRUENE") == "Bündnis 90/Die Grünen"


def test_the_default_profile_keeps_its_own_column_names(tmp_path: Path) -> None:
    columns = load_settings(cwd=tmp_path).columns.results
    assert columns.district == "Kommunalwahlbezirk" and columns.district_from_precinct is None
    assert columns.precinct == "gebietnr" and columns.encoding == "latin-1"
