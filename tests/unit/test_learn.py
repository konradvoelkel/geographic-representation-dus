"""``georep learn-bodies``: die Abbildung Organisation -> Gremium aus den Daten lernen (Punkt 58).

Der Befehl behauptet nichts, er rechnet: aus den Dokumenten, deren Beratungsfolge **genau eine**
Organisation nennt und deren Drucksachennummer ein Kürzel trägt, folgt je Organisation ein Kürzel
mit einer messbaren Reinheit. Die Tests prüfen die drei Ausgaben (Katalog, TOML-Block, Gegenprobe)
und die zwei Fälle, die in den echten Daten vorkommen: eine Organisation, deren Dokumente
mehrheitlich für ein Kürzel stimmen (Düsseldorf: ``gr/6`` ist der Rat, 30 Dokumente nennen
trotzdem RPAU), und eine Stadt, deren Nummern kein Kürzel tragen (Mönchengladbach).
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from georep.errors import MissingInputError
from georep.io import write_parquet
from georep.layout import Layout
from georep.learn import learn_bodies
from georep.settings import Settings

ORG = "https://ris-oparl.itk-rheinland.de/Oparl/bodies/0015/organizations"


def _corpus(layout: Layout, rows: list[tuple[str, str, list[str]]]) -> None:
    frame = pl.DataFrame(
        {
            "id": [row[0] for row in rows],
            "reference": [row[1] for row in rows],
            "consultation_organizations": [[f"{ORG}/{key}" for key in row[2]] for row in rows],
        },
        schema={
            "id": pl.String,
            "reference": pl.String,
            "consultation_organizations": pl.List(pl.String),
        },
    )
    layout.interim.mkdir(parents=True, exist_ok=True)
    write_parquet(frame, layout.corpus, schema_version=3)


@pytest.fixture
def settings(default_settings: Settings) -> Settings:
    """Die Default-Settings ohne die gelernte Tabelle: so beginnt jede Stadt (Punkt 58)."""
    return default_settings.model_copy(
        update={"bodies": default_settings.bodies.model_copy(update={"organizations": {}})}
    )


@pytest.fixture
def run(tmp_path: Path, default_settings: Settings) -> Layout:
    """Ein kleiner Korpus mit Folge: zwei eindeutige Rats-, eine BV- und zwei andere Zeilen."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref", "duesseldorf")
    _corpus(
        layout,
        [
            ("p1", "RAT/1/2021", ["gr/6"]),
            ("p2", "RAT/2/2021", ["gr/6"]),
            ("p3", "RPAU/1/2021", ["gr/6"]),  # dieselbe Organisation, anderes Kürzel
            ("p4", "BV1/1/2021", ["gr/32"]),
            ("p5", "61/ 12/2014", ["gr/32"]),  # Amtsnummer: die Folge würde sie auflösen
            ("p6", "61/ 13/2014", ["gr/32", "gr/6"]),  # mehrdeutig
            ("p7", "61/ 14/2014", []),  # ohne Folge
            ("p8", "OVA/1/2021", ["gr/25", "gr/6"]),  # mehrdeutig, Nummer entscheidet
        ],
    )
    return layout


def test_the_majority_decides_and_the_purity_says_how_clear_it_was(
    run: Layout, settings: Settings
) -> None:
    report = learn_bodies(run, settings)
    assert (report.documents, report.with_consultation) == (8, 7)
    learned = {entry.key: entry for entry in report.learned}
    assert set(learned) == {"gr/6", "gr/32"}
    assert learned["gr/6"].code == "RAT" and learned["gr/6"].alone == 3
    assert learned["gr/6"].pure == 2 and learned["gr/6"].purity == pytest.approx(2 / 3)
    assert learned["gr/32"].code == "BV1" and learned["gr/32"].purity == 1.0
    # gr/25 steht nur in einer mehrdeutigen Folge: nichts zu lernen, aber im Katalog
    catalogue = {entry.key: entry for entry in report.organizations}
    assert catalogue["gr/25"].code == "" and catalogue["gr/25"].documents == 1
    assert report.purity == pytest.approx(3 / 4)  # 2 von 3 plus 1 von 1
    block = report.toml()
    assert block.startswith("[bodies.organizations]")
    assert '"gr/6" = "RAT"' in block and '"gr/32" = "BV1"' in block
    assert "3 Dokumente nennen nur sie, 2 davon als RAT" in block
    text = report.text()
    assert "Gelernt: 2 Organisationen aus 4 Dokumenten mit genau einer, Reinheit 75.0%" in text


def test_a_code_the_profile_does_not_know_comes_out_commented(
    tmp_path: Path, settings: Settings
) -> None:
    """Review 2026-10-14: eine Zeile, die das Profil ablehnen würde, ist keine gültige TOML-Zeile.

    ``POA`` stand bis zum Review in keiner Kürzeltabelle Düsseldorfs, und der Befehl druckte
    ``"gr/26" = "POA"`` zum Einsetzen -- wer es einsetzte, bekam einen Settings-Fehler. Jetzt kommt
    die Zeile auskommentiert heraus, mit dem Grund daneben.
    """
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref", "duesseldorf")
    _corpus(layout, [("p1", "XYZ/1/2021", ["gr/42"]), ("p2", "RAT/1/2021", ["gr/6"])])
    report = learn_bodies(layout, settings)
    learned = {entry.key: entry for entry in report.learned}
    assert learned["gr/42"].code == "XYZ" and not learned["gr/42"].known
    assert learned["gr/6"].code == "RAT" and learned["gr/6"].known
    block = report.toml()
    assert '# "gr/42" = "XYZ"' in block and "NICHT GÜLTIG" in block
    assert '"gr/6" = "RAT"' in block and '# "gr/6"' not in block
    assert "1 Zeile(n) sind auskommentiert" in report.text()
    # Und die auskommentierte Zeile ist genau die, die der Validator ablehnen würde
    with pytest.raises(ValueError, match="steht in keiner Tabelle"):
        settings.bodies.model_validate(
            settings.bodies.model_dump() | {"organizations": {"gr/42": "XYZ"}}
        )


def test_min_documents_keeps_a_single_vote_out_of_the_table(
    run: Layout, settings: Settings
) -> None:
    report = learn_bodies(run, settings, min_documents=4)
    assert [entry.key for entry in report.learned] == []  # keine schafft vier
    assert learn_bodies(run, settings, min_documents=3).learned[0].key == "gr/6"


def test_the_cross_check_measures_the_table_the_profile_carries(
    run: Layout, settings: Settings
) -> None:
    """Gezählt wird mit der Tabelle des Profils, nicht mit der gelernten (die wäre tautologisch).

    „Mehrdeutig" heißt seit dem Review vom 2026-10-14 „die Folge nennt mehrere Organisationen" --
    unabhängig davon, ob die Tabelle sie kennt. Darum zählt p6 (``gr/32`` und ``gr/6``) auch ohne
    Tabelle als mehrdeutig: eine Zeile mehr darin würde daran nichts ändern, und genau das soll
    die Gegenprobe sagen.
    """
    without = learn_bodies(run, settings)
    assert (without.confirmed, without.conflicting) == (0, 0)
    assert (without.unknown, without.resolvable, without.ambiguous, without.without) == (3, 0, 1, 2)
    assert without.differences() == ["  gr/32: nur gelernt (BV1)", "  gr/6: nur gelernt (RAT)"]

    with_table = settings.model_copy(
        update={
            "bodies": settings.bodies.model_copy(
                update={"organizations": {"gr/6": "RAT", "gr/32": "BV1", "gr/25": "OVA"}}
            )
        }
    )
    report = learn_bodies(run, with_table)
    assert (report.confirmed, report.conflicting) == (3, 1)  # p3 nennt RPAU, die Folge RAT
    assert (report.unknown, report.resolvable, report.ambiguous, report.without) == (3, 1, 1, 1)
    assert report.differences() == ["  gr/25: nur im Profil (OVA)"]
    assert "Unterschiede zur Tabelle im Profil" in report.text()


def test_the_catalogue_adds_the_names_from_the_organizations_file(
    run: Layout, settings: Settings
) -> None:
    """Mit ``raw/organizations.json`` tragen die Zeilen Kürzel, Klassifikation und Namen.

    Das ist der Weg für eine Stadt, deren Nummern kein Kürzel tragen: aus den Nummern ist dort
    nichts zu lernen, und die Tabelle entsteht aus diesen Namen.
    """
    run.raw.mkdir(parents=True, exist_ok=True)
    run.organizations.write_text(
        json.dumps(
            [
                {
                    "id": f"{ORG}/gr/6",
                    "shortName": "RAT",
                    "name": "Rat",
                    "classification": "Ausschuss",
                }
            ]
        ),
        encoding="utf-8",
    )
    report = learn_bodies(run, settings)
    entry = next(e for e in report.organizations if e.key == "gr/6")
    assert (entry.short_name, entry.classification, entry.name) == ("RAT", "Ausschuss", "Rat")
    assert "Ausschuss RAT Rat" in report.table()
    assert "(Rat)" in report.toml()


def test_without_a_corpus_the_command_says_which_step_is_missing(
    tmp_path: Path, settings: Settings
) -> None:
    layout = Layout(tmp_path / "leer", tmp_path / "cache", tmp_path / "ref", "duesseldorf")
    with pytest.raises(MissingInputError, match="papers.parquet fehlt"):
        learn_bodies(layout, settings)


def test_the_package_fills_the_consultation_of_a_period_without_one(
    tmp_path: Path, settings: Settings
) -> None:
    """Punkt 58: ``[bodies].consultations`` ist die Quelle, wenn der Korpus keine Folge trägt."""
    layout = Layout(tmp_path / "data", tmp_path / "cache", tmp_path / "ref", "duesseldorf")
    _corpus(layout, [("p1", "RAT/1/2021", []), ("p2", "61/ 12/2014", [])])
    package = tmp_path / "beratungsfolge.parquet"
    write_parquet(
        pl.DataFrame(
            {
                "id": ["p1", "p2"],
                "consultation_organizations": [[f"{ORG}/gr/6"], [f"{ORG}/gr/32"]],
            },
            schema={"id": pl.String, "consultation_organizations": pl.List(pl.String)},
        ),
        layout.consultations,
        schema_version=2,
    )
    assert layout.consultations.is_file() and not package.exists()
    declared = settings.model_copy(
        update={
            "bodies": settings.bodies.model_copy(update={"consultations": layout.consultations})
        }
    )
    report = learn_bodies(layout, declared)
    assert report.with_consultation == 2
    assert {entry.key: entry.code for entry in report.learned} == {"gr/6": "RAT"}
