"""Vorhaben 12 gegen den Kopf aus Vorhaben 11 (Synergien 2026-11, Konflikt 5).

Beide lesen das federführende Amt aus dem Kopffeld der Vorlage: 11 als `dokumente_kopf`
(`amt_nr`, `amt_name`), 12 als Spanne `amt` mit der Form `kopf`, und 12 baut daraus je Lauf sein
Ämterverzeichnis (Name -> Nummer). Beide bauen, wie validiert; Quelle des federführenden Amts für
jeden Nutzer ist 11, 12 liefert die Nennungen im Text. Eine Abweichung ist ein Befund, kein Umbau:
die Tests halten fest, wie groß sie ist, damit eine Änderung an einer Seite auffällt.

Die Hauptperiode entsteht wie in `georep run` aus den Datenpaketen im Repo: `bootstrap`, dann die
Schritte `corpus`, `sections` (11) und `identifiers` (12).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest

from georep.bootstrap import bootstrap_from_settings
from georep.enrich.identifiers import identifiers_files, raw_text_frame
from georep.enrich.sections import sections_files
from georep.layout import Layout
from georep.pipeline import build_steps, run_pipeline
from georep.prep.identifiers import IdentifierRules, office_directory
from georep.settings import Settings, load_settings

pytestmark = pytest.mark.slow

NOWHERE = Path("/nonexistent")


@dataclass(frozen=True)
class MainPeriod:
    settings: Settings
    layout: Layout


@pytest.fixture(scope="module")
def main_period(tmp_path_factory: pytest.TempPathFactory) -> MainPeriod:
    root = tmp_path_factory.mktemp("kopf")
    settings = load_settings(cwd=NOWHERE).model_copy(
        update={"data_root": root / "data", "cache_root": root / "cache"}
    )
    layout = Layout.from_settings(settings)
    bootstrap_from_settings(layout, settings)
    names = ["corpus", "sections", "identifiers"]
    outcomes = run_pipeline(build_steps(settings, layout), settings, names)
    assert [o.status for o in outcomes] == ["ausgeführt"] * 3, [o.line() for o in outcomes]
    return MainPeriod(settings, layout)


def _directory_of_11(head: pl.DataFrame, settings: Settings) -> dict[str, str]:
    """Das Verzeichnis, das 12 aus `dokumente_kopf` bauen würde: dieselben Schwellen wie
    `office_directory` (Häufigkeit, Länge oder Amtswort, kein Gremium), Name -> häufigste Nummer."""
    offices = settings.identifiers.offices
    committees = re.compile(offices.committee_words)
    by_name: dict[str, Counter[str]] = {}
    for number, name in head.select("amt_nr", "amt_name").drop_nulls().iter_rows():
        by_name.setdefault(name, Counter())[number] += 1
    return {
        name: codes.most_common(1)[0][0]
        for name, codes in by_name.items()
        if sum(codes.values()) >= offices.directory_min_count
        and (len(name) >= offices.directory_min_chars or offices.directory_word in name.lower())
        and not committees.search(name)
    }


def test_das_aemterverzeichnis_von_12_steht_ganz_in_dem_aus_dem_kopf_von_11(
    main_period: MainPeriod,
) -> None:
    """Gemessen am 2026-11-26: 12 hat 55 Namen, alle mit derselben Nummer auch bei 11; 11 hätte
    sieben mehr, und keiner davon ist ein Amt, das 12 im Text suchen sollte: Kopffelder mit zwei
    Ämtern in einer Zeile, ein Verein hinter dem Amt, eine Person statt eines Amts. 12 bleibt darum
    bei seinem validierten Verzeichnis aus den eigenen Kopffeldern."""
    settings, layout = main_period.settings, main_period.layout
    corpus = pl.read_parquet(layout.corpus, columns=["file_name"]).drop_nulls().unique()
    texts, _ = raw_text_frame(layout.raw_texts)
    heads = texts.join(corpus, left_on="name", right_on="file_name", how="semi").sort("name")
    rules = IdentifierRules.from_settings(settings.identifiers)
    ours = office_directory(heads.get_column("text"), rules)
    theirs = _directory_of_11(pl.read_parquet(sections_files(layout).head), settings)
    assert len(ours) == 55
    assert {name: theirs.get(name) for name in ours} == ours
    assert sorted(set(theirs) - set(ours)) == [
        "Amt für Gebäudemanagement 67 - Stadtentwässerungsbetrieb",
        "Amt für Statistik und Wahlen 50 – Amt für Soziales",
        "Amt für Umwelt- und Verbraucherschutz 68 – Garten-, Friedhofs- und Forstamt",
        "Amt für Umwelt- und Verbraucherschutz 68- Garten-, Friedhofs- und Forstamt",
        "Sportamt Stadtsportbund Düsseldorf e. V.",
        "Sportamt Stadtsportbund Düsseldorf e.V.",
        "Stadtkämmerin",
    ]
    assert identifiers_files(layout).spans.exists()


def test_das_kopf_amt_von_12_gegen_das_von_11(main_period: MainPeriod) -> None:
    """Gemessen am 2026-11-26: in 9 994 Dokumenten nennen beide ein federführendes Amt, in 9 957 das
    gleiche (die Nummer, ohne Nummer der Name). Die 37 übrigen sind Kopffelder mit dreistelliger
    Unternummer oder ohne Bindestrich („40/603 - VHS", „02/0 Stadtkämmerin"): 11 liest die Nummer,
    die Kopfform von 12 (zwei Ziffern, eine oder zwei dahinter, Bindestrich) trifft sie nicht, und
    12 nimmt nach Fassung 2 den ganzen Wert als Norm. Ein Dokument hat nur bei 12 ein Kopf-Amt.
    Nutzer des federführenden Amts lesen es aus 11 (Konflikt 5); 12 behält die validierte Regel."""
    layout = main_period.layout
    spans = pl.read_parquet(identifiers_files(layout).spans)
    ours = (
        spans.filter((pl.col("kind") == "amt") & (pl.col("attr") == "kopf"))
        .sort("id", "start")
        .group_by("id", maintain_order=True)
        .agg(pl.col("norm").first().alias("amt_12"))
    )
    theirs = pl.read_parquet(sections_files(layout).head, columns=["id", "amt_nr", "amt_name"])
    joined = theirs.join(ours, on="id", how="full", coalesce=True)
    has_11 = pl.col("amt_nr").is_not_null() | pl.col("amt_name").is_not_null()
    has_12 = pl.col("amt_12").is_not_null()
    same = (pl.col("amt_12") == pl.col("amt_nr")) | (
        pl.col("amt_nr").is_null() & (pl.col("amt_12") == pl.col("amt_name"))
    )
    both = joined.filter(has_11 & has_12)
    differ = both.filter(~same.fill_null(False))
    assert (
        both.height,
        both.height - differ.height,
        joined.filter(has_11 & ~has_12).height,
        joined.filter(~has_11 & has_12).height,
    ) == (9994, 9957, 0, 1)
    assert dict(differ.group_by("amt_nr").len().iter_rows()) == {
        "02/0": 17,
        "40/603": 17,
        "41/202": 2,
        "41/203": 1,
    }
    assert all(
        amt_12.startswith(amt_nr)
        for amt_nr, amt_12 in differ.select("amt_nr", "amt_12").iter_rows()
    )
