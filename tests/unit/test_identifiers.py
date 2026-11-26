"""Kennungen und Beträge (Vorhaben 12), Regel für Regel an Beispielen aus dem Messdokument.

Die Regeln sind die der Stadtprofile, wie ``georep run`` sie liest. Jedes Beispiel steht im
Messdokument ``docs/plans/12-kennungen.md`` (§ 3.3, § 3.7, § 4.2, § 4.4) oder im Codebuch .2; die
erwarteten Spannen sind die, die das Messskript in der validierten Fassung liefert (Bauleitplanung
und Betrag Fassung 1, Termin und Verwaltungseinheit Fassung 2) — auch dort, wo die Kodierer etwas
anderes wollten: ein bekannter Fehler einer bestandenen Fassung bleibt, bis eine neue Fassung an
frischen Labels besteht.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from georep.prep.identifiers import (
    ATTR,
    EXTRA,
    METHOD,
    Hit,
    IdentifierRules,
    _spans_hold,
    amount_norm,
    find_identifiers,
    identifier_figures,
    identifier_spans,
    iso_date,
    office_directory,
    overlaps_are_allowed,
    plan_norm,
)
from georep.settings import IdentifierOffices, Identifiers, PlanNorm, Settings, load_settings
from georep.spans import SPAN_SCHEMA, empty_spans, sort_spans

NOWHERE = Path("/nonexistent")
DIRECTORY = {
    "Umweltamt": "19",
    "Amt für Wohnungswesen": "64",
    "Amt für Verkehrsmanagement": "66",
}


@pytest.fixture(scope="module")
def city() -> Settings:
    return load_settings(cwd=NOWHERE)


@pytest.fixture(scope="module")
def rules(city: Settings) -> IdentifierRules:
    return IdentifierRules.from_settings(city.identifiers).with_directory(DIRECTORY)


@pytest.fixture(scope="module")
def other_city() -> IdentifierRules:
    settings = load_settings(profile="moenchengladbach", cwd=NOWHERE)
    return IdentifierRules.from_settings(settings.identifiers)


def _found(text: str, rules: IdentifierRules, kind: str) -> list[tuple[str, str, str | None]]:
    """(Text der Spanne, Normwert, Form) je Kennung einer Art."""
    return [
        (text[h.start : h.end], h.norm, h.attr)
        for h in find_identifiers(text, rules)
        if h.kind == kind
    ]


# --- Art 1: Bauleitplanung (Fassung 1) ---------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Bebauungsplan Nr. 5674/26", [("5674/26", "5674/026", None)]),
        ("Bebauungsplan 5872 011", [("5872 011", "5872/011", None)]),
        ("Bebauungsplan 5374-027", [("5374-027", "5374/027", None)]),
        ("B-Plan 06-018", [("06-018", "06/018", None)]),
        # eine Liste hinter dem Schlüsselwort: je Nummer eine Spanne
        (
            "Bebauungspläne 03/017 und 03/018",
            [("03/017", "03/017", None), ("03/018", "03/018", None)],
        ),
        # das Nummernformat ohne Schlüsselwort ist keine Plannummer (§ 3.3)
        ("Vorlage APS/130/2020", []),
        ("Qualifizierungsverfahren Nr. 01/021", []),
    ],
)
def test_bebauungsplaene(
    text: str, expected: list[tuple[str, str, None]], rules: IdentifierRules
) -> None:
    assert _found(text, rules, "bplan") == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Flächennutzungsplanänderung Nr. 178", [("178", "FNP-Änderung 178", None)]),
        ("FNP-Änderung 138", [("138", "FNP-Änderung 138", None)]),
        ("die 190. Änderung des Flächennutzungsplans", [("190", "FNP-Änderung 190", None)]),
        # über den Zeilenwechsel verpasst die Ordinalform die Nummer (§ 4.2, in Fassung 2 nicht
        # umgebaut; bleibt offen)
        ("die 188.\nÄnderung des Flächennutzungsplans", []),
    ],
)
def test_fnp_aenderungen(
    text: str, expected: list[tuple[str, str, None]], rules: IdentifierRules
) -> None:
    assert _found(text, rules, "fnp") == expected


def test_die_plannummer_einer_anderen_stadt(other_city: IdentifierRules) -> None:
    """Mönchengladbach schreibt Nummer/Stadtbezirk und Nummer/römische Ziffer (§ 3.4)."""
    text = "Bebauungsplan Nr. 809/N und 517/III"
    assert _found(text, other_city, "bplan") == [
        ("809/N", "809/N", None),
        ("517/III", "517/III", None),
    ]


def test_plannummer_ohne_regel_ohne_leerraum_und_gross(other_city: IdentifierRules) -> None:
    assert plan_norm("809 / n", other_city) == "809/N"


# --- Art 3: Betrag (Fassung 1, ohne Rolle) -----------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Kosten 5.000 Euro", [("5.000 Euro", "5000.00", None)]),
        ("rund 2,5 Mio. €", [("2,5 Mio. €", "2500000.00", None)]),
        ("EUR 2.700", [("EUR 2.700", "2700.00", None)]),
        ("300 T€", [("300 T€", "300000.00", None)]),
        ("3 Mrd. Euro", [("3 Mrd. Euro", "3000000000.00", None)]),
        ("40 Tsd. €", [("40 Tsd. €", "40000.00", None)]),
        ("-1.234,- €", [("-1.234,- €", "-1234.00", None)]),
        # ein Preis je Einheit trägt die Form je
        ("12,50 €/m²", [("12,50 €", "12.50", "je")]),
        # die erste Zahl einer Spanne erbt Einheit und Faktor
        (
            "5.000 bis 10.000 Euro",
            [("5.000", "5000.00", "spanne"), ("10.000 Euro", "10000.00", None)],
        ),
        # „Bezirk 6 800 Euro": die 6 gehört zum Bezirk, nicht zum Betrag (§ 6)
        ("Bezirk 6 800 Euro", [("800 Euro", "800.00", None)]),
        # Fassung 1 nimmt das Pluszeichen nicht in die Spanne (Fassung 2 bestand nicht, § 5)
        ("+536.000EUR", [("536.000EUR", "536000.00", None)]),
        # bekannter Fehler der Fassung 1 (§ 4.2, zwei Fälle in Runde 1): eine Jahreszahl im
        # Tabellenkopf mit Faktor und Einheit ist ein Betrag
        ("2021 Mio. EUR", [("2021 Mio. EUR", "2021000000.00", None)]),
        # bekannte Lücke der Fassung 1: „Euro" vorn kennt sie nicht (§ 4.2)
        ("Euro 172.000", []),
        ("Kapitel 3 und Seite 12", []),
    ],
)
def test_betraege(
    text: str, expected: list[tuple[str, str, str | None]], rules: IdentifierRules
) -> None:
    assert _found(text, rules, "betrag") == expected


def test_betrag_norm_mit_faktor_und_tausend(rules: IdentifierRules) -> None:
    assert amount_norm("1.500,75", None, None, "€", rules) == Decimal("1500.75")
    assert amount_norm("2,5", None, "Millionen", "Euro", rules) == Decimal("2500000.00")
    assert amount_norm("300", None, None, "T EUR", rules) == Decimal("300000.00")
    assert amount_norm("12", "−", None, "€", rules) == Decimal("-12.00")
    # mehr Stellen, als eine Dezimalzahl hält: kein Betrag, kein Absturz
    assert amount_norm("9" * 40, None, "Mrd.", "€", rules) is None


# --- Art 4: Termin (Fassung 2, ohne Funktion) ---------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("bis zum 31.03.2024", [("31.03.2024", "2024-03-31", "tag")]),
        ("am 01.02.24", [("01.02.24", "2024-02-01", "tag")]),
        # zweistellige Jahre nur mit zweistelligem Tag und Monat: „3.2.10" ist eine Gliederung
        ("Punkt 3.2.10", []),
        ("Datei 2020-10-05", [("2020-10-05", "2020-10-05", "tag")]),
        ("23. Februar\n2022", [("23. Februar\n2022", "2022-02-23", "tag")]),
        # R10: die erste Angabe einer Spanne ist eine eigene Spanne
        (
            "am 10. und 11. Juni 2023",
            [("10.", "2023-06-10", "tag"), ("11. Juni 2023", "2023-06-11", "tag")],
        ),
        (
            "10.07. bis zum 17.07.2022",
            [("10.07.", "2022-07-10", "tag"), ("17.07.2022", "2022-07-17", "tag")],
        ),
        (
            "März bis Dezember 2021",
            [("März", "2021-03", "monat"), ("Dezember 2021", "2021-12", "monat")],
        ),
        ("Ende Februar 2021", [("Ende Februar 2021", "2021-02~ende", "monat")]),
        ("3. Quartal 2024", [("3. Quartal 2024", "2024-Q3", "quartal")]),
        ("III. Quartal 2023", [("III. Quartal 2023", "2023-Q3", "quartal")]),
        ("1. Halbjahr 2025", [("1. Halbjahr 2025", "2025-H1", "quartal")]),
        ("3. Halbjahr 2025", []),
        ("Ende des Jahres 2023", [("Ende des Jahres 2023", "2023~ende", "jahr")]),
        ("Frühjahr 2023", [("Frühjahr 2023", "2023~fruehjahr", "jahr")]),
        ("Jahresende 2022", [("Jahresende 2022", "2022~ende", "jahr")]),
        (
            "in der nächsten Sitzung",
            [("in der nächsten Sitzung", "relativ:naechste_sitzung", "relativ")],
        ),
        # „bis zur" gehört nicht zur Spanne (so die Labels)
        ("bis zur nächsten Sitzung", [("nächsten Sitzung", "relativ:naechste_sitzung", "relativ")]),
        (
            "nach der Sommerpause 2022",
            [("nach der Sommerpause 2022", "relativ:nach_sommerpause", "relativ")],
        ),
        (
            "innerhalb von drei Monaten",
            [("innerhalb von drei Monaten", "relativ:frist", "relativ")],
        ),
        ("am 31.02.2024", []),
    ],
)
def test_termine(text: str, expected: list[tuple[str, str, str]], rules: IdentifierRules) -> None:
    assert _found(text, rules, "termin") == expected


@pytest.mark.parametrize(
    ("day", "month", "year", "expected"),
    [
        (29, 2, 2024, "2024-02-29"),
        (29, 2, 2023, None),
        (31, 4, 2024, None),
        (1, 13, 2024, None),
        (1, 1, 1949, None),
        (31, 12, 2040, "2040-12-31"),
    ],
)
def test_iso_datum(day: int, month: int, year: int, expected: str | None) -> None:
    assert iso_date(day, month, year) == expected


# --- Art 6: Verwaltungseinheit (Fassung 2) -----------------------------------------------------
HEAD = (
    "Vorlage\nFachbereich: 66 - Amt für Verkehrsmanagement\n19 - Umweltamt\nBetreff: Test\n"
    "Das Umweltamts (Amt 19) und das Umweltamt nehmen Stellung. Amt 66 und Amt 01/17.\n"
    "Der Ausschuss für Umweltamt tagt. Das Gartenamt, das Finanzamt, das Bundesamt, Gesamt.\n"
    "Bezirksverwaltungsstelle 10 und die Bezirksverwaltungsstellen. Siehe 64 - Amt für Wohnungswesen.\n"
)


def test_aemter_aus_kopf_und_text(rules: IdentifierRules) -> None:
    assert _found(HEAD, rules, "amt") == [
        ("66 - Amt für Verkehrsmanagement", "66", "kopf"),
        # die Folgezeile des Kopffelds trifft zuerst der Name aus dem Verzeichnis
        ("19 - Umweltamt", "19", "name"),
        ("Umweltamts (Amt 19)", "19", "name"),
        ("Umweltamt", "19", "name"),
        ("Amt 66", "66", "nummer"),
        ("Amt 01/17", "01/17", "nummer"),
        # „Ausschuss für" verhindert den Namen, nicht das Wort auf -amt
        ("Umweltamt", "19", "wort"),
        ("Gartenamt", "Gartenamt", "wort"),
        ("Bezirksverwaltungsstelle 10", "Bezirksverwaltungsstelle 10", "text"),
        ("Bezirksverwaltungsstellen", "Bezirksverwaltungsstelle", "text"),
        ("64 - Amt für Wohnungswesen", "64", "name"),
    ]


def test_die_nummer_vor_einem_namen_ueber_den_zeilenwechsel(rules: IdentifierRules) -> None:
    """Review K1 (2026-11-24): „Amt 19 - ⏎Amt für …" beginnt bei „19", nicht mitten in der Nummer.

    ``$`` trifft auch vor dem Zeilenwechsel am Ende des Fensters; die Spanne beginnt darum an der
    Fundstelle, nicht um die Länge des Treffers vor dem Namen.
    """
    text = "Das Amt 19 - \nAmt für Wohnungswesen nimmt Stellung."
    names = [h for h in find_identifiers(text, rules) if h.attr == "name"]
    assert [(text[h.start : h.end], h.norm) for h in names] == [
        ("19 - \nAmt für Wohnungswesen", "19")
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "im Dezernat 06 und Dezernat 3",
            [("Dezernat 06", "06", "nummer"), ("Dezernat 3", "03", "nummer")],
        ),
        # „Dezernat 6." am Satzende: die Fassung kennt es nicht (validiert, keine Nachschärfung)
        ("an Dezernat 6.", []),
    ],
)
def test_dezernate_nur_aus_dem_text(
    text: str, expected: list[tuple[str, str, str]], rules: IdentifierRules
) -> None:
    assert _found(text, rules, "dezernat") == expected


def test_aemter_einer_anderen_stadt(other_city: IdentifierRules) -> None:
    text = "Fachbereich FB 64 Umwelt\nFB 64 und Fachbereich 20.1; Amt 61"
    assert _found(text, other_city, "amt") == [
        ("FB 64 Umwelt", "64", "kopf"),
        ("FB 64", "64", "nummer"),
        ("Fachbereich 20.1", "20.1", "nummer"),
        ("Amt 61", "61", "nummer"),
    ]


def test_das_verzeichnis_entsteht_aus_den_kopffeldern(city: Settings) -> None:
    rules = IdentifierRules.from_settings(city.identifiers)
    heads = [
        *["Fachbereich: 52 - Sportamt\n"] * 3,
        *["Fachbereich: 66 - Amt für Verkehrsmanagement\n"] * 2,
        "Fachbereich: 66 - Amt für Verkehrsmanagement\n",
        "Fachbereich: 67 - Amt für Verkehrsmanagement\n",
        # zu selten
        *["Fachbereich: 68 - Amt für Brücken\n"] * 2,
        # ein Gremium kommt nicht ins Verzeichnis
        *["Amt / Institut: 01 - Jugendhilfeausschuss\n"] * 4,
        # kurz und ohne „amt": zu allgemein
        *["Fachbereich: 19 - Umwelt\n"] * 4,
        # ohne Nummer: nur der Name, kein Eintrag
        *["Fachbereich: Bezirksverwaltungsstelle\n"] * 4,
    ]
    assert office_directory(heads, rules) == {
        "Sportamt": "52",
        "Amt für Verkehrsmanagement": "66",
    }


def test_ohne_verzeichnis_nur_nummern_und_woerter(city: Settings) -> None:
    rules = IdentifierRules.from_settings(city.identifiers)
    assert _found("Das Umweltamt (Amt 19).", rules, "amt") == [
        ("Umweltamt", "Umweltamt", "wort"),
        ("Amt 19", "19", "nummer"),
    ]


# --- Arten, Settings, Korpus -------------------------------------------------------------------
def test_nur_die_gewaehlten_arten(city: Settings) -> None:
    only = city.identifiers.model_copy(update={"kinds": ["betrag"]})
    rules = IdentifierRules.from_settings(only)
    hits = find_identifiers("Am 31.03.2024 kostet Bebauungsplan 03/017 genau 5.000 Euro.", rules)
    assert {h.kind for h in hits} == {"betrag"}


def test_ohne_muster_keine_treffer() -> None:
    """Die Vorgaben des Modells sind leer; ohne Muster aus den Settings trifft nur, was kein Wort
    braucht: ein Datum in Ziffern."""
    rules = IdentifierRules.from_settings(Identifiers())
    text = "Bebauungsplan 03/017, 5.000 Euro, 31.03.2024, Amt 66, Dezernat 06, Sportamt"
    assert find_identifiers(text, rules) == [Hit(34, 44, "termin", "2024-03-31", "tag")]


def test_settings_pruefen_gruppen_und_vorlagen() -> None:
    with pytest.raises(ValidationError, match="braucht die Gruppen"):
        IdentifierOffices(head=r"Fachbereich: (?P<wert>.*)")
    with pytest.raises(ValidationError, match="text_norm"):
        IdentifierOffices(text=r"Bezirksamt(?: (?P<n>\d+))?")
    with pytest.raises(ValidationError, match="passt nicht"):
        PlanNorm(pattern=r"(\d{4})", replace=r"\2")
    with pytest.raises(ValidationError, match="doppelt"):
        Identifiers(kinds=["betrag", "betrag"])


def _texts(*pairs: tuple[str, str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "name": [p[0] for p in pairs],
            "text": [p[1] for p in pairs],
            "extractor": ["pypdf-7.1.0+roh"] * len(pairs),
        }
    )


def test_jede_korpus_id_der_datei_bekommt_die_spannen(rules: IdentifierRules) -> None:
    """Zwei Paper tragen dieselbe Datei: beide bekommen die Spannen (Synergien 2026-11, § 1)."""
    texts = _texts(
        ("a.pdf", "Kosten 5.000 Euro"), ("b.pdf", "Bebauungsplan 03/017"), ("c.pdf", "x")
    )
    documents = pl.DataFrame(
        {"id": ["p2", "p1", "p3", "p4"], "file_name": ["a.pdf", "a.pdf", "b.pdf", None]}
    )
    spans = identifier_spans(texts, documents, rules)
    assert spans.columns == [*SPAN_SCHEMA, ATTR]
    assert spans.select("id", "start", "end", "kind", "value", "norm", "section").rows() == [
        ("p1", 7, 17, "betrag", "5.000 Euro", "5000.00", ""),
        ("p2", 7, 17, "betrag", "5.000 Euro", "5000.00", ""),
        ("p3", 14, 20, "bplan", "03/017", "03/017", ""),
    ]
    assert set(spans.get_column("extractor")) == {f"{METHOD}/pypdf-7.1.0+roh"}
    assert identifier_figures(spans) == {
        "bplan": 1,
        "fnp": 0,
        "betrag": 2,
        "termin": 0,
        "amt": 0,
        "dezernat": 0,
        "dokumente": 3,
    }


def test_ohne_treffer_dasselbe_schema(rules: IdentifierRules) -> None:
    spans = identifier_spans(
        _texts(("a.pdf", "nichts")), pl.DataFrame({"id": ["p"], "file_name": ["a.pdf"]}), rules
    )
    assert spans.schema == empty_spans(EXTRA).schema
    assert spans.height == 0


def test_eine_datei_ohne_korpus_id_faellt_weg(rules: IdentifierRules) -> None:
    spans = identifier_spans(
        _texts(("fremd.pdf", "5.000 Euro")),
        pl.DataFrame({"id": ["p"], "file_name": ["a.pdf"]}),
        rules,
    )
    assert spans.height == 0


def _amt_spans(*rows: tuple[int, int, str, str]) -> pl.DataFrame:
    """Spannen der Art amt in einem Dokument: (start, end, value, attr)."""
    frame = pl.DataFrame(
        {
            "id": ["p"] * len(rows),
            "start": [r[0] for r in rows],
            "end": [r[1] for r in rows],
            "kind": ["amt"] * len(rows),
            "value": [r[2] for r in rows],
            "norm": ["10"] * len(rows),
            "section": [""] * len(rows),
            "extractor": [f"{METHOD}/x"] * len(rows),
            ATTR: [r[3] for r in rows],
        },
        schema={**SPAN_SCHEMA, **EXTRA},
    )
    return sort_spans(frame)


def test_nur_die_nummer_und_der_nach_vorn_verlaengerte_name_ueberlappen() -> None:
    """Review N1 (2026-11-24): der Vertrag erlaubt das eine Paar aus Fassung 2, nicht die ganze Art.

    „Amt 10 – Hauptamt": die Nummer „Amt 10" und der Name „10 – Hauptamt", der sie nach vorn in
    seine Spanne nimmt. Zwei Namen, ein Wort statt des Namens, ein Name, der nicht mit der Nummer
    beginnt, oder eine Nummer hinter dem Namen sind ein Fehler.
    """
    assert overlaps_are_allowed(
        _amt_spans((0, 6, "Amt 10", "nummer"), (4, 17, "10 – Hauptamt", "name"))
    )
    for rows in (
        ((0, 6, "Amt 10", "name"), (4, 17, "10 – Hauptamt", "name")),
        ((0, 6, "Amt 10", "nummer"), (4, 17, "10 – Hauptamt", "wort")),
        ((0, 6, "Amt 10", "nummer"), (5, 17, "0 – Hauptamt", "name")),
        ((0, 17, "Amt 10 – Hauptamt", "nummer"), (4, 6, "10", "name")),
    ):
        assert not overlaps_are_allowed(_amt_spans(*rows)), rows


def test_value_ist_woertlich_der_text_der_spanne(rules: IdentifierRules) -> None:
    """Review N2 (2026-11-24): der Vertrag verspricht es, also prüft er es, seit Vorhaben 11 mit
    ``check_spans(..., texts=...)`` aus F3 (auch hinter einem Zeichen außerhalb der Basisebene).
    12 kennt keine Positionsspanne: ein leeres ``value`` ist ein Fehler."""
    texts = _texts(("a.pdf", "𝔘 Amt 10 – Hauptamt"))
    documents = pl.DataFrame({"id": ["p", "q"], "file_name": ["a.pdf", "a.pdf"]})
    right = _amt_spans((2, 8, "Amt 10", "nummer"))
    assert _spans_hold(texts, documents, rules, result=right)
    for wrong in (
        _amt_spans((2, 8, "Amt 11", "nummer")),
        _amt_spans((2, 8, "", "nummer")),
        right.with_columns(pl.lit("r").alias("id")),
    ):
        assert not _spans_hold(texts, documents, rules, result=wrong)


def _sections(*rows: tuple[str, int, int, str]) -> pl.DataFrame:
    """Abschnitte der Ebene 1 aus Vorhaben 11: (id, start, end, Abschnitt)."""
    frame = pl.DataFrame(
        {
            "id": [r[0] for r in rows],
            "start": [r[1] for r in rows],
            "end": [r[2] for r in rows],
            "kind": ["abschnitt"] * len(rows),
            "value": [""] * len(rows),
            "norm": [r[3] for r in rows],
            "section": [r[3] for r in rows],
            "extractor": ["struktur-1/pypdf-7.1.0+roh"] * len(rows),
        },
        schema=SPAN_SCHEMA,
    )
    return sort_spans(frame)


def test_section_kommt_aus_den_abschnitten_von_11(rules: IdentifierRules) -> None:
    """Je Spanne der Abschnitt der Ebene 1, in dem ihr Anfang liegt (``section_of``, Vorhaben 11);
    außerhalb jedes Abschnitts bleibt ``section`` leer."""
    text = "Betreff: Turnhalle\nBeschlussvorschlag: 5.000 Euro bis zum 31.03.2024\nAnlage 7 Euro"
    texts = _texts(("a.pdf", text))
    documents = pl.DataFrame({"id": ["p"], "file_name": ["a.pdf"]})
    sections = _sections(("p", 0, 19, "betreff"), ("p", 19, 69, "beschlussvorschlag"))
    spans = identifier_spans(texts, documents, rules, sections)
    assert spans.select("value", "section").rows() == [
        ("5.000 Euro", "beschlussvorschlag"),
        ("31.03.2024", "beschlussvorschlag"),
        ("7 Euro", ""),
    ]
    assert identifier_spans(texts, documents, rules).get_column("section").to_list() == [""] * 3
