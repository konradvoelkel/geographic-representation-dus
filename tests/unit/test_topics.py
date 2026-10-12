"""Das Themenmodell auf synthetischen Texten: drei Wortfamilien, drei Themen.

Einzelne Zahlen des Modells prüft kein Test: zwischen Rechnern (andere BLAS-Bibliothek) weichen
sie in den letzten Stellen ab. Geprüft werden die Eigenschaften, auf denen die Gewichtung aufbaut:
genau ``k`` Themen, Anteile mit Zeilensumme 1, Labels aus den Wörtern der Familie, zwei Aufrufe im
selben Prozess gleich.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from georep.analysis.topics import (
    TopicRules,
    dominant_topics,
    fit_topics,
    load_stop_words,
    name_stop_words,
    profile_stop_words,
)
from georep.errors import EmptyResultError
from georep.settings import Topics, load_settings

FAMILIES = (
    ("strasse", "verkehr", "parken", "radweg"),
    ("schule", "kita", "bildung", "unterricht"),
    ("grundstueck", "bauvorhaben", "stellplatz", "bebauung"),
)


def _corpus(documents: int = 12, filler: str = "") -> pl.DataFrame:
    rows = [
        {
            "id": f"p{i:02d}",
            "text": " ".join(FAMILIES[i % len(FAMILIES)] * 2) + f" wort{i} {filler}",
        }
        for i in range(documents)
    ]
    return pl.DataFrame(rows, schema={"id": pl.String, "text": pl.String})


def _settings(**overrides: object) -> Topics:
    base: dict[str, object] = {
        "k": 3,
        "min_df": 1,
        "max_df": 1.0,
        "max_features": 100,
        "top_words": 4,
        "stop_words": "de",
        "random_state": 0,
    }
    return Topics(**(base | overrides))  # type: ignore[arg-type]


def test_stop_words_are_lowercase_and_cover_the_function_words() -> None:
    words = load_stop_words("de")
    assert len(words) > 150
    assert {"und", "oder", "sich", "nicht", "dass", "auch"} <= words
    assert all(word == word.strip().lower() and word for word in words)
    assert "düsseldorf" not in words and "beschluss" not in words  # Eigennamen, Sachwörter
    assert load_stop_words("") == frozenset()


def test_an_unknown_language_is_a_domain_error() -> None:
    with pytest.raises(EmptyResultError, match="Stoppwortliste"):
        load_stop_words("xx")


def test_each_word_family_dominates_one_topic_and_appears_in_its_label() -> None:
    model = fit_topics(_corpus(), _settings())
    assert model.topics.height == 3
    labels = [set(words) for words in model.topics.get_column("woerter").to_list()]
    for family in FAMILIES:
        assert any(set(family) <= label for label in labels), (family, labels)
    assert model.topics.get_column("dokumente").to_list() == [4, 4, 4]
    assert model.topics.get_column("thema").to_list() == [0, 1, 2]


def test_the_shares_of_a_document_sum_to_one() -> None:
    model = fit_topics(_corpus(), _settings())
    sums = model.shares.get_column("anteile").list.sum().to_list()
    assert all(value == pytest.approx(1.0, abs=1e-9) for value in sums)
    assert model.shares.get_column("id").to_list() == sorted(_corpus().get_column("id").to_list())


def test_two_runs_give_the_same_frames() -> None:
    first = fit_topics(_corpus(), _settings())
    second = fit_topics(_corpus(), _settings())
    assert_frame_equal(first.shares, second.shares)
    assert_frame_equal(first.topics, second.topics)


def test_documents_without_text_are_left_out() -> None:
    corpus = pl.concat(
        [
            _corpus(),
            pl.DataFrame(
                {"id": ["p99"], "text": [""]}, schema={"id": pl.String, "text": pl.String}
            ),
        ]
    )
    model = fit_topics(corpus, _settings())
    assert "p99" not in model.shares.get_column("id").to_list()
    assert int(model.topics.get_column("dokumente").sum()) == 12


def test_fewer_documents_than_topics_is_a_domain_error() -> None:
    with pytest.raises(EmptyResultError, match="Dokumente mit Text"):
        fit_topics(_corpus(2), _settings())


def test_an_empty_vocabulary_is_a_domain_error() -> None:
    """Nur Stoppwörter und Zahlen: nach dem Beschneiden bleibt kein Wort übrig."""
    corpus = pl.DataFrame(
        {"id": [f"p{i}" for i in range(5)], "text": ["und oder 2025"] * 5},
        schema={"id": pl.String, "text": pl.String},
    )
    with pytest.raises(EmptyResultError, match="Kein Wort"):
        fit_topics(corpus, _settings(min_df=1))


def test_dominant_topic_breaks_a_tie_for_the_smaller_number() -> None:
    shares = pl.DataFrame(
        {"id": ["p2", "p1"], "anteile": [[0.5, 0.5], [0.25, 0.75]]},
        schema={"id": pl.String, "anteile": pl.List(pl.Float64)},
    )
    found = dominant_topics(shares)
    assert found.get_column("id").to_list() == ["p1", "p2"]  # sortiert
    assert dict(found.select("id", "thema").iter_rows()) == {"p1": 1, "p2": 0}
    assert dict(found.select("id", "anteil").iter_rows()) == {"p1": 0.75, "p2": 0.5}


def test_dominant_topic_rounds_the_share() -> None:
    shares = pl.DataFrame(
        {"id": ["p1"], "anteile": [[0.123456789, 0.876543211]]},
        schema={"id": pl.String, "anteile": pl.List(pl.Float64)},
    )
    assert dominant_topics(shares).get_column("anteil").to_list() == [0.8765]


# --- Punkt 45: Stoppwörter aus dem Profil und aus dem Korpus -----------------------------------


def test_the_profile_supplies_the_stop_words_of_parties_and_bodies() -> None:
    """Die Namen stehen schon im Profil (Option 04 und 05); eine zweite Liste gibt es nicht."""
    settings = load_settings(cwd=Path("/nonexistent"))
    words = profile_stop_words(settings.originators, settings.bodies, ("fraktionen", "gremien"))
    assert {"cdu", "spd", "fdp", "afd", "linke", "grüne", "gruene"} <= words
    assert {"fraktionen", "interfraktionell", "ratsherr", "bezirksvertreter"} <= words
    assert {"ova", "kua", "rat", "jurat"} <= words
    assert "verkehrsausschuss" not in words  # nur Kürzel, keine Namen: die sind Themenwörter
    assert "bv" not in words  # zwei Buchstaben bilden kein Token, also auch kein Stoppwort
    assert profile_stop_words(settings.originators, settings.bodies, ()) == frozenset()
    only_bodies = profile_stop_words(settings.originators, settings.bodies, ("gremien",))
    assert "ova" in only_bodies and "cdu" not in only_bodies


def test_a_word_that_stands_almost_only_behind_a_name_marker_is_a_name() -> None:
    rules = TopicRules(
        name_markers=("gez.",),
        name_window=40,
        name_min_documents=3,
        name_share=0.8,
        with_names=True,
    )
    texts = [f"beschluss über die strasse {i} gez. mustermann strasse" for i in range(10)]
    texts += [f"strasse und verkehr in bezirk {i}" for i in range(10)]
    words = name_stop_words(texts, rules)
    assert "mustermann" in words
    assert "strasse" not in words and "verkehr" not in words


def test_the_person_markers_alone_find_names_without_any_signature_marker() -> None:
    """``name_markers = []`` darf die Marker aus ``[originators]`` nicht mit abschalten.

    Die beiden Quellen von Namensfenstern sind unabhängig: die Amtsbezeichnungen stehen
    stadtneutral in ``defaults.toml``, die Personenmarker im Profil (Option 04). Eine Stadt, die
    die deutsche Liste leert, soll die eigenen Marker behalten.
    """
    rules = TopicRules(
        name_markers=(),
        person_patterns=("ratsherr ",),
        name_window=40,
        name_min_documents=3,
        with_names=True,
    )
    texts = [f"antrag des ratsherr mustermann meier zur strasse {i}" for i in range(6)]
    texts += [f"die strasse und der verkehr in bezirk {i}" for i in range(6)]
    assert "mustermann" in name_stop_words(texts, rules)
    assert "strasse" not in name_stop_words(texts, rules)


def test_a_window_fragment_never_pushes_the_share_above_one() -> None:
    """Ein Marker kann mitten in einem Wort treffen; dann beginnt das Fenster mit einem Rest.

    „stadtkämmer" trifft in „stadtkämmerin", das Fenster fängt mit „in …" an. Ein längerer Rest
    wäre ein Token, das im ganzen Text nicht vorkommt -- der Quotient läge über 1 und der Anteil
    wäre kein Anteil mehr.
    """
    rules = TopicRules(
        name_markers=("vorsitzende",),
        name_window=40,
        name_min_documents=2,
        name_share=1.0,
        with_names=True,
    )
    texts = [f"beschluss vorsitzenderausschuss tagte heute {i}" for i in range(4)]
    assert all(word.isalpha() for word in name_stop_words(texts, rules))


def test_without_the_source_namen_no_name_is_derived() -> None:
    rules = TopicRules(name_markers=("gez.",), with_names=False)
    assert name_stop_words(["gez. mustermann x"] * 10, rules) == frozenset()


def test_a_kept_word_survives_a_derived_stop_word() -> None:
    """Sachwörter, die zufällig in einem Gruppen- oder Gremiennamen stehen, nennt das Profil.

    Nicht nur Parteinamen können ein Sachwort mitnehmen: ein **Gremienkürzel** kann mit einem
    Wort zusammenfallen. „BAU" (Bauausschuss) ist als Wort „bau" und steht auf der Referenz in
    1101 von 19 033 Dokumenten (5,8 %); es gehört in die Themen. ``topics.stop_keep`` holt es
    zurück.
    """
    settings = load_settings(cwd=Path("/nonexistent"))
    rules = TopicRules.from_settings(settings)
    assert not {"klima", "tierschutz", "bau"} & rules.stop_words  # vom Profil zurückgeholt
    assert {"cdu", "ova", "kua"} <= rules.stop_words
    assert settings.topics.stop_keep  # das Profil nennt die Ausnahmen


def test_the_derived_words_do_not_reach_the_labels() -> None:
    """Ein Korpus voller Fraktionsnamen: ohne sie prägen die Sachwörter die Themen."""
    rows = [
        {
            "id": f"p{i:02d}",
            # Der Namensmarker steht hinten, wie in den echten Dokumenten: alles hinter ihm ist
            # Unterschrift, alles davor Sache.
            "text": " ".join(FAMILIES[i % len(FAMILIES)] * 2)
            + " antrag der cdu fraktion gez. mustermann fraktionssprecher",
        }
        for i in range(12)
    ]
    corpus = pl.DataFrame(rows, schema={"id": pl.String, "text": pl.String})
    rules = TopicRules(
        stop_words=frozenset({"cdu", "fraktion", "antrag"}),
        name_markers=("gez.",),
        name_min_documents=3,
        with_names=True,
    )
    model = fit_topics(corpus, _settings(), rules)
    labels = {word for words in model.topics.get_column("woerter").to_list() for word in words}
    assert not labels & {"cdu", "fraktion", "antrag", "mustermann"}
    assert labels & set(FAMILIES[0])


# --- Punkt 45: gesäte Themen je Ausschuss ------------------------------------------------------

CODES = ("AAA", "BBB", "CCC")


def _seed_corpus(per_committee: tuple[int, ...] = (6, 5, 4)) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Je Ausschuss eine Wortfamilie, dazu ein Dokument ohne Gremium.

    Die Füllwörter sind kein Zierrat: ohne sie hat die TF-IDF-Matrix genau den Rang 4, und mit
    ``k = 4`` findet NMF eine exakte Zerlegung. Dann wird das Residuum in sklearns eigener
    Fehlerformel minimal negativ, ``np.sqrt`` davon ist ``nan`` und die Abbruchprüfung von ``tol``
    fällt still aus (``_nmf.py:125``, dieselbe Stelle, die der Kommentar in ``analysis/topics.py``
    zu Float32 nennt). Mit den Füllwörtern ist der Rang 6, und die Suite läuft ohne Warnung
    (gemessen 2026-10-13: Rang 4 → eine Warnung, Rang 6 → keine).
    """
    rows, refs = [], []
    for family, (code, count) in enumerate(zip(CODES, per_committee, strict=True)):
        for i in range(count):
            paper = f"{code}-{i:02d}"
            text = (
                " ".join(FAMILIES[family] * 3)
                + f" wort{family}{i}"
                + " anlage" * (i % 3)
                + " beschluss" * ((i + 1) % 2)
            )
            rows.append({"id": paper, "text": text})
            refs.append({"id": paper, "gremium": code, "gremium_art": "ausschuss"})
    rows.append({"id": "RAT-01", "text": "haushalt personal stellenplan haushalt personal"})
    refs.append({"id": "RAT-01", "gremium": "RAT", "gremium_art": "rat"})
    corpus = pl.DataFrame(rows, schema={"id": pl.String, "text": pl.String})
    bodies = pl.DataFrame(
        refs, schema={"id": pl.String, "gremium": pl.String, "gremium_art": pl.String}
    )
    return corpus, bodies


def _seed_rules(**overrides: object) -> TopicRules:
    base: dict[str, object] = {
        "seed": "committees",
        "free": 1,
        "seed_words": 6,
        "seed_min_documents": 4,
        "committees": frozenset(CODES),
    }
    return TopicRules(**(base | overrides))  # type: ignore[arg-type]


def test_each_committee_with_enough_documents_gets_its_own_topic() -> None:
    corpus, bodies = _seed_corpus()
    model = fit_topics(corpus, _settings(k=4), _seed_rules(), bodies)
    assert model.topics.get_column("gremium").to_list() == [*CODES, None]
    labels = dict(model.topics.select("gremium", "woerter").iter_rows())
    for family, code in enumerate(CODES):
        assert set(labels[code]) & set(FAMILIES[family]), (code, labels[code])
    # Das freie Thema rechnet auf dem Rest und trägt darum Wörter, aber kein Gremium.
    assert labels[None]


def test_a_committee_below_the_threshold_gets_no_topic() -> None:
    corpus, bodies = _seed_corpus((6, 5, 4))
    model = fit_topics(corpus, _settings(k=4), _seed_rules(seed_min_documents=5), bodies)
    assert model.topics.get_column("gremium").to_list() == ["AAA", "BBB", None, None]


def test_a_seed_word_occurs_in_the_documents_of_its_committee() -> None:
    """Sonst sät das Modell ein Wort, das der Ausschuss nie benutzt.

    Die Log-Odds vergleichen einen Ausschuss mit den anderen Ausschüssen. Ein Wort, das in
    **keinem** Ausschuss steht (hier „haushalt" und „personal", nur im Ratsdokument), hat in
    beiden Gruppen die Zahl 0 — und bekommt trotzdem ein positives z, weil der kleinere Ausschuss
    im Nenner weniger Token hat. Sein Zentroid ist dann 0, und die Saat trug dafür ersatzweise
    das Gewicht 1: das stärkste Wort des Themas wäre eines, das sein Ausschuss nicht kennt.
    """
    corpus, bodies = _seed_corpus()
    model = fit_topics(corpus, _settings(k=4), _seed_rules(), bodies)
    texts = dict(corpus.select("id", "text").iter_rows())
    for row in model.topics.iter_rows(named=True):
        if not row["gremium"]:
            continue
        own = " ".join(texts[p] for p in texts if p.startswith(row["gremium"]))
        assert all(word in own for word in row["woerter"]), (row["gremium"], row["woerter"])


def test_the_seeded_topics_are_the_strongest_for_their_own_documents() -> None:
    corpus, bodies = _seed_corpus()
    model = fit_topics(corpus, _settings(k=4), _seed_rules(), bodies)
    dominant = dict(dominant_topics(model.shares).select("id", "thema").iter_rows())
    for topic, code in enumerate(CODES):
        own = [p for p in dominant if p.startswith(code)]
        assert all(dominant[paper] == topic for paper in own), (code, dominant)


def test_without_a_free_topic_every_topic_is_seeded() -> None:
    """``free = 0``: so viele Themen wie gesäte Ausschüsse, kein Rest wird gerechnet."""
    corpus, bodies = _seed_corpus()
    model = fit_topics(corpus, _settings(k=3), _seed_rules(free=0), bodies)
    assert model.topics.get_column("gremium").to_list() == list(CODES)
    sums = model.shares.get_column("anteile").list.sum().to_list()
    assert all(value == pytest.approx(1.0, abs=1e-9) for value in sums)


def test_the_shares_of_a_seeded_model_also_sum_to_one() -> None:
    corpus, bodies = _seed_corpus()
    model = fit_topics(corpus, _settings(k=4), _seed_rules(), bodies)
    sums = model.shares.get_column("anteile").list.sum().to_list()
    assert all(value == pytest.approx(1.0, abs=1e-9) for value in sums)
    assert model.shares.height == corpus.height


def test_two_seeded_runs_give_the_same_frames() -> None:
    corpus, bodies = _seed_corpus()
    first = fit_topics(corpus, _settings(k=4), _seed_rules(), bodies)
    second = fit_topics(corpus, _settings(k=4), _seed_rules(), bodies)
    assert_frame_equal(first.shares, second.shares)
    assert_frame_equal(first.topics, second.topics)


def test_without_a_seed_or_without_gremien_no_topic_carries_a_name() -> None:
    """Vier Themen auf 19 synthetischen Texten zerlegen fast exakt; sklearns eigene Fehlerformel
    zieht dann die Wurzel aus einer negativen Zahl und warnt (dieselbe Stelle, die der Kommentar
    in ``analysis/topics.py`` zu Float32 nennt). Harmlos: ``max_iter`` begrenzt den Lauf."""
    corpus, bodies = _seed_corpus()
    for rules, frame in (
        (_seed_rules(seed="none"), bodies),
        (_seed_rules(), None),
        (_seed_rules(committees=frozenset()), bodies),
        (_seed_rules(free=4), bodies),  # kein Platz für ein gesätes Thema
    ):
        model = fit_topics(corpus, _settings(k=4), rules, frame)
        assert model.topics.get_column("gremium").to_list() == [None] * 4


def test_only_committees_are_seeded_not_the_council() -> None:
    corpus, bodies = _seed_corpus()
    rules = _seed_rules(committees=frozenset({*CODES, "RAT"}), seed_min_documents=1)
    model = fit_topics(corpus, _settings(k=4), rules, bodies)
    assert "RAT" not in model.topics.get_column("gremium").to_list()


def test_a_vocabulary_smaller_than_k_is_a_domain_error() -> None:
    """nndsvda verlangt ``k <= min(Dokumente, Wörter)``; zu wenige Wörter sind kein Programmfehler."""
    corpus = pl.DataFrame(
        {"id": [f"p{i}" for i in range(5)], "text": ["strasse verkehr"] * 5},
        schema={"id": pl.String, "text": pl.String},
    )
    with pytest.raises(EmptyResultError, match="Wörter"):
        fit_topics(corpus, _settings(k=4, min_df=1))
