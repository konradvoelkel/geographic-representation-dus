"""Eigenschaften der Funktion, der Antragsteller und des Lagers (Vorhaben 15), für alle Eingaben.

Aus dem Bauplan (Messdokument ``docs/plans/15-funktion.md``, § 6): die Funktion ist total und
deterministisch; ein Text hinter einem Trenner des Titels ändert die Antragsteller nicht; die
Antragsteller hängen nicht an der Zeilenfolge; das Lager ist für jede Menge von Fraktionen und jede
Mehrheit eines der sieben und hängt nicht an der Reihenfolge.
"""

from __future__ import annotations

import random
from datetime import date
from pathlib import Path

import polars as pl
from hypothesis import given
from hypothesis import strategies as st

from georep.analysis.cosponsors import CAMPS, CosponsorRules, camp, classify_cosponsors, cosponsors
from georep.analysis.functions import FunctionRules, classify_function, is_consistent
from georep.settings import FUNCTION_INSTRUMENTS, load_settings

NOWHERE = Path("/nonexistent")
CITY = load_settings(cwd=NOWHERE)
RULES = {
    v: FunctionRules.from_settings(CITY.functions.model_copy(update={"variant": v})) for v in "AB"
}
COSPONSOR_RULES = CosponsorRules.from_settings(CITY)
SECOND = load_settings(profile="moenchengladbach", cwd=NOWHERE)
SECOND_RULES = FunctionRules.from_settings(SECOND.functions)

# Bausteine echter Titel und Texte: Instrumente, Erklärungen, Briefkopf, Parteien, Trenner, Rauschen.
WORDS = (
    "antrag",
    "anfrage",
    "nachfrage",
    "änderungsantrag",
    "haushaltsantrag",
    "prüfauftrag",
    "sachstand",
    "bericht",
    "resolution",
    "appell",
    "seebrücke",
    "bauvoranfrage",
    "mitteilung",
    "informationsvorlage",
    "beschlussdarstellung",
    "zur kenntnis",
    "teilt mit",
    "beschließt",
    "der rat verurteilt",
    "fordert die landesregierung auf",
    "wird gebeten zu berichten",
    "satzung",
    "bebauungsplan",
    "rsd vorlage x öffentlich nicht öffentlich",
    "der bezirksvertretung 3",
    "an den",
    "11.09.2014",
    "cdu",
    "spd",
    "volt",
    "grüne",
    "die linke",
    "afd",
    "fraktion",
    ":",
    ";",
    " zum ",
    " - ",
    "tempo 30",
    "spielplatz",
    "anlage 1",
)
TYPES = (
    *CITY.functions.types,
    *CITY.functions.collection_political,
    *CITY.functions.collection_admin,
    "Antrag",
    "Anfrage SPD",
    "Antrag CDU/Grüne",
    "Haushaltsantrag Die Linke",
    "zAnfrage REP",
    "Neue Art",
    "",
)
ORIGINATORS = ("Verwaltung", "Fraktion", "Person", "Eingabe", "unbekannt", None)
PARTIES = ("CDU", "GRUENE", "SPD", "FDP", "Die_Linke", "AfD", "T_FW", "PARTEI", "VOLT")
FRACTIONS = ("CDU", "GRUENE", "SPD+VOLT", "FDP", "Die_Linke", "AfD", "T_FW+PARTEI")

phrases = st.lists(st.one_of(st.sampled_from(WORDS), st.text(max_size=12)), max_size=12).map(
    " ".join
)


@given(
    st.sampled_from(TYPES),
    phrases,
    phrases,
    st.sampled_from(ORIGINATORS),
    st.sampled_from("AB"),
)
def test_the_function_is_total_and_deterministic(
    paper_type: str, name: str, text: str, origin: str | None, variant: str
) -> None:
    found = classify_function(paper_type, name, text, origin, RULES[variant])
    assert is_consistent(found)
    assert classify_function(paper_type, name, text, origin, RULES[variant]) == found


@given(st.sampled_from((*SECOND.functions.types, "Neue Art")), phrases, phrases)
def test_the_second_city_is_total_as_well(paper_type: str, name: str, text: str) -> None:
    assert is_consistent(classify_function(paper_type, name, text, "Fraktion", SECOND_RULES))


@given(
    st.sampled_from(("antrag der", "anfrage der", "änderungsantrag der", "resolution der")),
    st.lists(
        st.sampled_from(("cdu", "spd", "grüne", "fdp", "die linke", "volt")), min_size=1, max_size=3
    ),
    st.sampled_from((":", ";", " zum ", " zur ", " vom ", " - ", " – ", " hier: ", " wegen ")),
    phrases,
)
def test_a_subject_behind_a_separator_changes_no_cosponsor(
    instrument: str, parties: list[str], separator: str, subject: str
) -> None:
    author = f"{instrument} {' und '.join(parties)}-fraktion"
    alone = cosponsors("Antrag", author, "", "Fraktion", (), COSPONSOR_RULES)
    assert alone[0]  # der Autorenteil nennt eine Partei
    titled = cosponsors("Antrag", author + separator + subject, "", "Fraktion", (), COSPONSOR_RULES)
    assert titled == alone


documents = st.lists(
    st.tuples(
        st.sampled_from(("Antrag", "Antrag CDU/Grüne", "Anfrage SPD", "Vorlage aus der Politik")),
        phrases,
        st.sampled_from(("Fraktion", "Verwaltung", "unbekannt")),
        st.lists(st.sampled_from(PARTIES), unique=True, max_size=3),
        st.sampled_from(("rat", "ausschuss", "bezirksvertretung", None)),
        st.dates(min_value=date(2014, 1, 1), max_value=date(2027, 1, 1)),
    ),
    min_size=1,
    max_size=15,
)


@given(documents, st.randoms(use_true_random=False))
def test_the_cosponsors_do_not_depend_on_the_row_order(
    docs: list[tuple[str, str, str, list[str], str | None, date]], rnd: random.Random
) -> None:
    ids = [f"id{i:02d}" for i in range(len(docs))]
    corpus = pl.DataFrame(
        {
            "id": ids,
            "date": [d[5] for d in docs],
            "paper_type": [d[0] for d in docs],
            "name": [d[1] for d in docs],
            "text": [d[1] for d in docs],
        }
    )
    originators = pl.DataFrame(
        {"id": ids, "urheber_art": [d[2] for d in docs], "parteien": [d[3] for d in docs]},
        schema={"id": pl.String, "urheber_art": pl.String, "parteien": pl.List(pl.String)},
    )
    bodies = pl.DataFrame(
        {"id": ids, "gremium_art": [d[4] for d in docs]},
        schema={"id": pl.String, "gremium_art": pl.String},
    )
    order = list(range(len(docs)))
    rnd.shuffle(order)
    first = classify_cosponsors(corpus, originators, bodies, COSPONSOR_RULES)
    shuffled = classify_cosponsors(
        corpus[order], originators[order[::-1]], bodies[order], COSPONSOR_RULES
    )
    assert first.equals(shuffled)


@given(
    st.lists(st.sampled_from(FRACTIONS), max_size=5),
    st.one_of(st.none(), st.sets(st.sampled_from(FRACTIONS), min_size=1, max_size=3)),
    st.randoms(use_true_random=False),
)
def test_the_camp_is_one_of_seven_and_ignores_the_order(
    fractions: list[str], majority: set[str] | None, rnd: random.Random
) -> None:
    found = camp(fractions, majority)
    assert found in CAMPS
    assert (found == "ohne_lager") == (majority is None)
    other = list(fractions)
    rnd.shuffle(other)
    assert camp(other, majority) == found
    if majority is not None and len(set(fractions)) >= 2:
        assert found.startswith("gemeinsam") or found == "ueber_grenze"


pairs = st.sampled_from(
    [
        f"{f}/{i}"
        for f, instruments in FUNCTION_INSTRUMENTS.items()
        if f != "rest"
        for i in instruments
    ]
)


@given(
    st.dictionaries(
        st.sampled_from(("antrag", "anfrage", "vorlage", "beratungs")), pairs, max_size=4
    ),
    st.dictionaries(st.sampled_from(("Antrag", "Vorlage", "Beratungsvorlage")), pairs, max_size=3),
    st.sampled_from(("Antrag X", "Anfrage Y", "Vorlage Z", "Beratungsvorlage BV", "Vorlage")),
    phrases,
    st.sampled_from(ORIGINATORS),
    st.sampled_from("AB"),
)
def test_any_table_of_types_and_prefixes_keeps_the_contract(
    prefixes: dict[str, str],
    types: dict[str, str],
    paper_type: str,
    name: str,
    origin: str | None,
    variant: str,
) -> None:
    """Review 2026-11-24, K1: jede Tabelle, die die Settings zulassen, gibt ein gültiges Ergebnis."""
    functions = CITY.functions.model_copy(
        update={
            "type_prefixes": prefixes,
            "types": types,
            "collection_political": [],
            "collection_admin": [],
            "variant": variant,
        }
    )
    found = classify_function(paper_type, name, "", origin, FunctionRules.from_settings(functions))
    assert is_consistent(found)
