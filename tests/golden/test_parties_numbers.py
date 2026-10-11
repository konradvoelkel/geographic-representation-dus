"""Die Urheber-Zuordnung über die volle Referenz: Deckung, Klassen, Parteien, Vollständigkeit.

Diese Zahlen sind keine Werte der Arbeit (sie kennt die Urheber nicht), sondern die Deckung der
Muster aus ``defaults.toml`` über alle 19 108 Dokumente, am 2026-10-12 gemessen. Sie sind Schranken,
keine Gleichheiten: ein neuer ``paperType`` oder eine neue Schreibvariante soll auffallen, ohne dass
jede Verschiebung um ein Dokument den Test rot macht. Der Test, der wirklich eng ist, ist der
letzte: jeder ``paperType``-Wert des Korpus muss den Settings bekannt sein.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from georep.analysis.parties import (
    ART,
    PARTEIEN,
    QUELLE,
    Patterns,
    classify_originators,
    documents_per_party,
    originator_figures,
)
from georep.bootstrap import seed_stores_from_legacy
from georep.layout import Layout
from georep.prep.papers import build_corpus
from georep.settings import Settings, load_settings
from georep.stores import PaperStore, TextStore

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def settings() -> Settings:
    return load_settings(cwd=Path("/nonexistent"))


@pytest.fixture(scope="module")
def attribution(
    reference_root: Path, settings: Settings, tmp_path_factory: pytest.TempPathFactory
) -> pl.DataFrame:
    import json

    root = tmp_path_factory.mktemp("parties_reference")
    layout = Layout(root / "data", root / "cache", reference_root)
    layout.ensure_dirs()
    items = json.loads(
        (reference_root / "interim" / "paper_with_text.json").read_text(encoding="utf-8")
    )
    seed_stores_from_legacy(layout, items)
    corpus = build_corpus(PaperStore(layout.papers).load().values(), TextStore(layout.texts))
    assert corpus.height == 19_108
    return classify_originators(corpus, settings.originators)


def test_the_patterns_cover_almost_every_document(attribution: pl.DataFrame) -> None:
    figures = originator_figures(attribution)
    total = attribution.height
    assert sum(figures.values()) == total == 19_108  # die Partition deckt alles ab
    assert figures["unbekannt"] / total <= 0.05  # gemessen 3,2 % (616 Dokumente)
    assert figures["Fraktion"] / total >= 0.35  # gemessen 40,2 % (7 689)
    assert figures["Verwaltung"] / total >= 0.45  # gemessen 52,0 % (9 933)
    assert figures["Eingabe"] == 124  # die beiden Eingabe-paperTypes, 73 + 51
    assert 700 <= figures["Person"] <= 800  # gemessen 746


def test_the_sources_are_used_in_the_planned_proportions(attribution: pl.DataFrame) -> None:
    """Der Server liefert keine Urheberfelder, also ist ``oparl`` leer; der Rest verteilt sich auf
    Typ, Titel und Textkopf (Befund vom 2026-10-09, docs/plans/04-parteien.md § 3.1)."""
    found = dict(attribution.group_by(QUELLE).len().iter_rows())
    assert found.get("oparl", 0) == 0
    assert found["paper_type"] >= 13_000  # gemessen 13 432 (Verwaltung, Eingabe und Typ-Suffix)
    assert found["name"] >= 4_000  # gemessen 4 419
    assert found["text"] >= 500  # gemessen 641: Titel ohne Fraktion, Kopf mit
    assert found[""] <= 1_000  # gemessen 616, dieselben wie „unbekannt"


def test_every_party_has_documents_and_cooperations_are_visible(
    attribution: pl.DataFrame, settings: Settings
) -> None:
    per_party = documents_per_party(
        attribution, (*settings.originators.parties, *settings.originators.groups)
    )
    # Gemessen: GRUENE 2237, CDU 2089, SPD 2059, FDP 808, Die_Linke 791, AfD 182, T_FW 452,
    # PARTEI 281, VOLT 14. Jede Partei und Gruppe stellt Dokumente, die AfD am wenigsten.
    assert all(count > 0 for count in per_party.values())
    assert per_party["GRUENE"] >= per_party["CDU"] >= per_party["AfD"]
    assert 100 <= per_party["AfD"] <= 300
    multiple = attribution.filter(pl.col(PARTEIEN).list.len() >= 2)
    assert 1_000 <= multiple.height <= 1_300  # gemessen 1 119 Kooperationspapiere
    pairs = dict(multiple.group_by(pl.col(PARTEIEN).list.join("+")).len().iter_rows())
    assert pairs["CDU+GRUENE"] >= 700  # gemessen 826: die Kooperation der Periode


def test_every_paper_type_of_the_corpus_is_known_to_the_settings(
    attribution: pl.DataFrame, reference_root: Path, settings: Settings
) -> None:
    """Ein neuer ``paperType`` darf nicht stillschweigend in „unbekannt" verschwinden.

    Jeder Wert ist Verwaltung, Eingabe oder beginnt mit einem Antragspräfix; die Fehlermeldung
    nennt die Werte, damit ein Lauf nach einem Vollabruf sagt, was in die Settings gehört.
    """
    import json

    items = json.loads(
        (reference_root / "interim" / "paper_with_text.json").read_text(encoding="utf-8")
    )
    patterns = Patterns.from_settings(settings.originators)
    unknown = sorted(
        {
            typ
            for item in items
            if (typ := (item.get("paperType") or ""))
            and typ not in patterns.admin_types
            and typ not in patterns.citizen_types
            and not any(typ.lower().startswith(p) for p in patterns.motion_prefixes)
        }
    )
    assert unknown == [], f"paperType-Werte ohne Regel in [originators]: {unknown}"
    # Und: in der Klasse „unbekannt" steckt kein Verwaltungstyp mehr
    types = set(
        attribution.filter(pl.col(ART) == "unbekannt")
        .join(
            pl.DataFrame(
                {
                    "id": [i["id"] for i in items],
                    "paper_type": [i.get("paperType") or "" for i in items],
                }
            ),
            on="id",
        )
        .get_column("paper_type")
        .to_list()
    )
    assert types <= {"Antrag", "Anfrage", "zAnfrage REP"}, types
