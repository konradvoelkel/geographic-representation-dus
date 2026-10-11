"""Die Urheber-Zuordnung über die volle Referenz: Deckung, Klassen, Parteien, Vollständigkeit.

Diese Zahlen sind keine Werte der Arbeit (sie kennt die Urheber nicht), sondern die Deckung der
Muster aus ``defaults.toml`` über alle 19 108 Dokumente, am 2026-10-12 gemessen (nach der
Stichprobe von 50 Dokumenten, die drei Lücken in den Mustern gezeigt hat). Sie sind Schranken,
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
    KLASSEN_SPALTEN,
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
    assert figures["unbekannt"] / total <= 0.05  # gemessen 1,7 % (327 Dokumente)
    assert figures["Fraktion"] / total >= 0.35  # gemessen 41,1 % (7 859)
    assert figures["Verwaltung"] / total >= 0.45  # gemessen 52,0 % (9 933)
    assert figures["Eingabe"] == 124  # die beiden Eingabe-paperTypes, 73 + 51
    assert 800 <= figures["Person"] <= 950  # gemessen 865


def test_the_sources_are_used_in_the_planned_proportions(attribution: pl.DataFrame) -> None:
    """Der Server liefert keine Urheberfelder, also ist ``oparl`` leer; der Rest verteilt sich auf
    Typ, Titel und Textkopf (Befund vom 2026-10-09, docs/plans/04-parteien.md § 3.1)."""
    found = dict(attribution.group_by(QUELLE).len().iter_rows())
    assert found.get("oparl", 0) == 0
    assert found["paper_type"] >= 13_000  # gemessen 13 432 (Verwaltung, Eingabe und Typ-Suffix)
    assert found["name"] >= 4_000  # gemessen 4 617
    assert found["text"] >= 500  # gemessen 732: Titel ohne Fraktion, Kopf mit
    assert found[""] <= 1_000  # gemessen 327, dieselben wie „unbekannt"


def test_every_party_has_documents_and_cooperations_are_visible(
    attribution: pl.DataFrame, settings: Settings
) -> None:
    per_party = documents_per_party(
        attribution, (*settings.originators.parties, *settings.originators.groups)
    )
    # Gemessen: GRUENE 2307, CDU 2139, SPD 2106, FDP 879, Die_Linke 792, AfD 183, T_FW 452,
    # PARTEI 281, VOLT 14. Jede Partei und Gruppe stellt Dokumente, die AfD am wenigsten.
    assert all(count > 0 for count in per_party.values())
    assert per_party["GRUENE"] >= per_party["CDU"] >= per_party["AfD"]
    assert 100 <= per_party["AfD"] <= 300
    multiple = attribution.filter(pl.col(PARTEIEN).list.len() >= 2)
    assert 1_000 <= multiple.height <= 1_400  # gemessen 1 168 Kooperationspapiere
    pairs = dict(multiple.group_by(pl.col(PARTEIEN).list.join("+")).len().iter_rows())
    assert pairs["CDU+GRUENE"] >= 700  # gemessen 844: die Kooperation der Periode


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


def test_the_partition_holds_in_all_41_districts_and_the_party_sums_match(
    reference_root: Path, settings: Settings, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Die Kette auf der Referenz: in jedem der 41 Wahlbezirke summieren die fünf Urheberklassen
    zu ``anzahl_treffer``, und die Treffer je Partei stimmen mit der Messung vom 2026-10-12."""
    from georep.analysis.parties import originators_by_district, party_correlations
    from georep.bootstrap import bootstrap
    from georep.pipeline import build_steps, run_pipeline

    root = tmp_path_factory.mktemp("parties_chain")
    layout = Layout(root / "data", root / "cache", reference_root)
    bootstrap(layout)
    offline = [s.name for s in build_steps(settings, layout) if not s.network]
    outcomes = run_pipeline(build_steps(settings, layout), settings, offline)
    assert all(o.status == "ausgeführt" for o in outcomes)

    attribution = pl.read_parquet(layout.document_originators)
    results = pl.read_parquet(layout.results)
    by_district = pl.read_parquet(layout.district_originators)
    assert attribution.height == 19_108 and by_district.height == 41
    assert by_district.equals(originators_by_district(results, attribution))
    for row in by_district.iter_rows(named=True):
        assert sum(row[c] for c in KLASSEN_SPALTEN) == row["anzahl_treffer"], row["wahlkreis_id"]
    assert (
        by_district.get_column("anzahl_treffer").sum() == results.get_column("anzahl_treffer").sum()
    )

    table = pl.read_parquet(layout.party_results)
    assert table.height == 41 * len(settings.originators.parties)
    per_party = dict(table.group_by("partei").agg(pl.col("anzahl_treffer").sum()).iter_rows())
    # Gemessen am 2026-10-12: GRUENE 3408, CDU 2913, SPD 2278, FDP 973, Die_Linke 480, AfD 71
    assert per_party["GRUENE"] >= per_party["CDU"] >= per_party["SPD"] >= per_party["FDP"]
    assert per_party["FDP"] >= per_party["Die_Linke"] >= per_party["AfD"]
    assert 50 <= per_party["AfD"] <= 150

    # Wahlbezirk 11 hatte keinen Wahlvorschlag von Die Linke: n = 40 statt 41
    linke = table.filter(pl.col("partei") == "Die_Linke")
    assert linke.filter(~pl.col("angetreten")).get_column("wahlkreis_id").to_list() == [11]
    by_key = {c.key: c for c in party_correlations(table)}
    assert by_key["Die_Linke"].n == 40 and all(c.n in (40, 41) for c in by_key.values())
    # Unter Bonferroni (0,05/6 = 0,008) bleibt nur die FDP; gemessen r = +0,448, p = 0,0033
    significant = [k for k, c in by_key.items() if c.p is not None and c.p < 0.05 / 6]
    assert significant == ["FDP"], {k: (c.r, c.p) for k, c in by_key.items()}


def test_two_runs_write_the_same_party_tables(
    reference_root: Path, settings: Settings, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Byteidentisch: der Schritt hängt nur von Korpus, Auswertung, Wählern und Settings ab."""
    from georep.bootstrap import bootstrap
    from georep.pipeline import build_steps, run_pipeline

    roots = []
    for name in ("a", "b"):
        root = tmp_path_factory.mktemp(f"parties_twice_{name}")
        layout = Layout(root / "data", root / "cache", reference_root)
        bootstrap(layout)
        steps = build_steps(settings, layout)
        run_pipeline(steps, settings, [s.name for s in steps if not s.network])
        roots.append(layout)
    for attribute in ("document_originators", "district_originators", "party_results"):
        a, b = (getattr(layout, attribute) for layout in roots)
        assert a.read_bytes() == b.read_bytes(), attribute
