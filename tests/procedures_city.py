"""Eine kleine Stadt mit bekannten Kanten aller Typen, für die Tests von Vorhaben 14.

Vierzehn eigene Drucksachen und zwei einer Nachbarperiode, Nummern in Düsseldorfer Form. Was
jede Drucksache nennt und welche Kante daraus wird, steht an ihr; ``EDGES``, ``FOREST`` und
``ANSWERS`` sind die erwarteten Ergebnisse. Die Rollen kommen aus dem Stadtprofil
(``procedures.kinds``), die Muster ebenso.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

from georep.analysis.procedures import ATTACHMENT_SCHEMA, DOCUMENT_SCHEMA

D = dt.date
NEIGHBOUR = "duesseldorf-2014"
# id, periode, Nummer, Dokumentart, Titel, Datum, Text, Anlagen (Name, Datum)
DOCUMENTS: list[tuple[str, str, str, str, str, dt.date, str, list[tuple[str, dt.date | None]]]] = [
    ("p01", "", "RAT/1/2021", "Antrag SPD", "Radweg an der Hauptstraße", D(2021, 1, 10), "", []),
    # Titel nennt den Antrag: Umsetzung, stark über den Titel
    (
        "p02",
        "",
        "OVA/2/2021",
        "Beschlussvorlage",
        "Umsetzung des Antrags RAT/1/2021",
        D(2021, 3, 1),
        "die verwaltung schlägt vor",
        [("Lageplan", D(2021, 3, 1))],
    ),
    # Nachtrag über die Nummer, ohne Fundstelle
    ("p03", "", "OVA/2/2021/1", "Beschlussvorlage", "Nachtrag Radweg", D(2021, 3, 20), "", []),
    # Änderungsantrag: Änderungszeichen im Titel
    (
        "p04",
        "",
        "RAT/9/2021",
        "Antrag CDU",
        "Änderungsantrag zur Vorlage OVA/2/2021",
        D(2021, 3, 15),
        "",
        [],
    ),
    # nur im Text: schwach (Rückfallregel), Vorlage nennt Vorlage: bezug
    (
        "p05",
        "",
        "RAT/8/2021",
        "Beschlussvorlage",
        "Haushalt",
        D(2021, 4, 1),
        "wie in ova/2/2021 beschlossen",
        [],
    ),
    # Sammelbericht: seine Textverweise sind stark, Typ kontrolle
    (
        "p06",
        "",
        "RAT/7/2021",
        "Informationsvorlage",
        "Beschlusskontrolle 2021",
        D(2021, 6, 1),
        "zu rat/1/2021: umgesetzt.",
        [],
    ),
    (
        "p07",
        "",
        "BV1/3/2021",
        "Anfrage SPD",
        "Spielplatz",
        D(2021, 1, 15),
        "",
        [("Antwort der Verwaltung", D(2021, 2, 1))],
    ),
    # eigene Drucksache als Antwort, im Titel
    (
        "p08",
        "",
        "BV1/4/2021",
        "Bezirksvertretung Informationsvorlage",
        "Beantwortung der Anfrage BV1/3/2021",
        D(2021, 3, 1),
        "",
        [],
    ),
    ("p09", "", "BV1/5/2021", "Anfrage CDU", "Bank", D(2021, 2, 1), "", []),
    # Antwortanlage vom Umstellungstag: Antwort ohne Datum
    (
        "p10",
        "",
        "BV1/6/2021",
        "Anfrage FDP",
        "Licht",
        D(2021, 2, 2),
        "",
        [("Antwort", D(2019, 7, 3))],
    ),
    ("p11", "", "KUA/10/2020", "Bedarfsbeschluss", "Schule Neubau", D(2020, 11, 1), "", []),
    (
        "p12",
        "",
        "KUA/11/2021",
        "A+F Beschluss",
        "Schule Neubau – Ausführungs- und Finanzierungsbeschluss zu KUA/10/2020",
        D(2021, 5, 1),
        "",
        [],
    ),
    # über den Namen einer Anlage in die Nachbarperiode
    (
        "p13",
        "",
        "OVA/12/2021",
        "Beschlussvorlage",
        "Umsetzung",
        D(2021, 2, 1),
        "",
        [("Antrag RAT/99/2019", None)],
    ),
    # eine unbekannte Nummer und die eigene: keine Kante
    (
        "p14",
        "",
        "RAT/13/2021",
        "Antrag Die Linke",
        "Zu Vorlage OVA/404/2021",
        D(2021, 7, 1),
        "antrag rat/13/2021",
        [],
    ),
    ("n01", NEIGHBOUR, "RAT/99/2019", "Antrag", "Radweg alt", D(2019, 5, 1), "", []),
    (
        "n02",
        NEIGHBOUR,
        "OVA/98/2019",
        "Beschlussvorlage",
        "Umsetzung RAT/99/2019",
        D(2019, 8, 1),
        "",
        [],
    ),
]
OWN_IDS = [row[0] for row in DOCUMENTS if not row[1]]
FETCHED = D(2021, 12, 31)

# von, nach, typ, felder, stark, quelle, tage, nach_periode
EDGES = [
    ("n02", "n01", "umsetzung", ["titel"], True, "titel", 92, NEIGHBOUR),
    ("p02", "p01", "umsetzung", ["titel"], True, "titel", 50, ""),
    ("p03", "p02", "nachtrag", ["nummer"], True, "nummer", 19, ""),
    ("p04", "p02", "aenderung", ["titel"], True, "titel", 14, ""),
    ("p05", "p02", "bezug", ["text"], False, "text", 31, ""),
    ("p06", "p01", "kontrolle", ["text"], True, "sammelbericht", 142, ""),
    ("p08", "p07", "antwort", ["titel"], True, "titel", 45, ""),
    ("p12", "p11", "bau", ["titel"], True, "titel", 181, ""),
    ("p13", "n01", "umsetzung", ["anlage"], True, "anlage", 642, NEIGHBOUR),
]
# id, vorgang, rolle, tiefe, groesse (über die ganze Stadt)
FOREST = [
    ("p01", "p01", "wurzel", 0, 4),
    ("p02", "p01", "umsetzung", 1, 4),
    ("p03", "p01", "nachtrag", 2, 4),
    ("p04", "p01", "aenderung", 2, 4),
    ("p05", "p05", "ohne", 0, 1),
    ("p06", "p06", "ohne", 0, 1),
    ("p07", "p07", "wurzel", 0, 2),
    ("p08", "p07", "antwort", 1, 2),
    ("p09", "p09", "ohne", 0, 1),
    ("p10", "p10", "ohne", 0, 1),
    ("p11", "p11", "wurzel", 0, 2),
    ("p12", "p11", "bau", 1, 2),
    ("p13", "n01", "umsetzung", 1, 3),
    ("p14", "p14", "ohne", 0, 1),
]
# id, quelle, antwort_datum, tage, antwort_id, alter_am_abruf, gremium, praxis_gremium
ANSWERS = [
    ("p07", "beide", D(2021, 2, 1), 17, "p08", 350, "BV1", 2 / 3),
    ("p09", "keine", None, None, None, None, "BV1", 2 / 3),
    ("p10", "anlage", None, None, None, 332, "BV1", 2 / 3),
]


def documents() -> pl.DataFrame:
    return pl.DataFrame(
        [(i, p, r, n, t, d, x, [name for name, _ in a]) for i, p, r, t, n, d, x, a in DOCUMENTS],
        schema=DOCUMENT_SCHEMA,
        orient="row",
    )


def attachments() -> pl.DataFrame:
    return pl.DataFrame(
        [
            (i, FETCHED, [{"name": name, "datum": day} for name, day in a])
            for i, _p, _r, _t, _n, _d, _x, a in DOCUMENTS
            if a
        ],
        schema=ATTACHMENT_SCHEMA,
        orient="row",
    )
