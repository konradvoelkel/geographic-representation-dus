"""Points of Interest (Wikidata, Wikipedia) bereinigen und je Wahlbezirk sammeln.

Entspricht ``src/prep_wiki.py`` einschließlich seiner Reihenfolge, die den Golden Master prägt:
erst Duplikate nach Label entfernen (erstes Vorkommen bleibt), dann Einträge ohne Wahlbezirk
verwerfen, dann Kommas aus den Labels tilgen, dann die Ausschlussliste anwenden.

Danach, und nur wenn ``search.city_facilities`` an ist, greift die Regel „Einrichtung mit
Stadtnamen" (``docs/decisions.md``, Punkt 44): sie ist eine Abweichung von der Arbeit und darum
ein eigener Schritt nach ``clean_pois``, damit der Golden Master mit abgeschalteter Regel weiter
Zeile für Zeile stimmt.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path

import deal
import polars as pl

from georep.contracts import has_columns, lists_sorted_unique, sorted_unique

DISTRICT = "wahlkreis_id"
TERMS = "suchbegriffe"
POI_COLUMNS = ["label", DISTRICT, "lon", "lat"]
# Wikipedia-Lemmata unterscheiden Gleichnamige mit einem Klammerzusatz („Elbsee (Düsseldorf)"):
# der Zusatz gehört nicht zum Namen und zählt für die Regel nicht mit.
PARENTHESIS = re.compile(r"\([^)]*\)")
# Ein Wort im Sinne der Regel; dieselbe Zeichenklasse, die auch der Matcher als Wortzeichen
# nimmt, plus die Umlaute (hier geht es um Namen, nicht um Treffer).
WORD = re.compile(r"[0-9A-Za-zÄÖÜäöüß]+")


def read_pois_json(path: Path) -> pl.DataFrame:
    """Zwei Schlüsselsätze in einer Datei (SPARQL mit url, GeoSearch mit pageid und dist):
    das Schema muss über alle Zeilen abgeleitet werden."""
    return pl.read_json(path, infer_schema_length=None)


@deal.pre(lambda pois, exclude: has_columns(pois, *POI_COLUMNS))
@deal.post(lambda result: result.columns == POI_COLUMNS)
@deal.post(
    lambda result: (
        result.get_column(DISTRICT).null_count() == 0
        and not result.get_column("label").str.contains(",", literal=True).any()
    ),
    message="jeder Ort hat einen Wahlbezirk, kein Label trägt ein Komma",
)
@deal.ensure(lambda pois, exclude, result: result.height <= pois.height)
def clean_pois(pois: pl.DataFrame, exclude: Iterable[str]) -> pl.DataFrame:
    """Tabelle label, wahlkreis_id, lon, lat; Reihenfolge der Quelle bleibt."""
    excluded = list(exclude)
    return (
        pois.unique(subset=["label"], keep="first", maintain_order=True)
        .drop_nulls(DISTRICT)
        .with_columns(
            pl.col("label").str.replace_all(",", "", literal=True),
            pl.col(DISTRICT).cast(pl.Int64),
        )
        .filter(~pl.col("label").is_in(excluded))
        .select(POI_COLUMNS)
    )


@deal.pure
@deal.post(lambda result: result in (True, False))
def is_city_facility(
    label: str, city_name: str, city_adjectives: Sequence[str], place_words: Sequence[str]
) -> bool:
    """Trägt das Label den Stadtnamen so, wie Einrichtungen ihn tragen?

    Drei Prüfungen in dieser Reihenfolge (``docs/decisions.md``, Punkt 44):

    1. Kein Gattungswort: endet ein Wort des Labels auf ein Wort aus ``place_words``, ist es ein
       Ort, gleich wie es den Stadtnamen trägt („Düsseldorfer Stadtwald", „Luisen-Gymnasium
       Düsseldorf"). Das **Wortende** statt des Vorkommens, weil „park" sonst in
       „Stadtsparkasse" steckt; deutsche Zusammensetzungen tragen ihren Kopf hinten
       („Stadtwald", „Nordpark", „Hauptbahnhof").
    2. Das Städteadjektiv: steht es im Label, ist es eine Einrichtung („Düsseldorfer
       Schauspielhaus"). Ein Ort heißt nicht nach dem Adjektiv seiner Stadt.
    3. Der Stadtname: er macht das Label nur dann zur Einrichtung, wenn er das **letzte** Wort ist
       („Stadtwerke Düsseldorf", „Messe Düsseldorf"). Ein Ort innerhalb der Stadt trägt ihn
       vorangestellt, mit dem Ortsteil dahinter („Bahnhof Düsseldorf-Rath", „Düsseldorf
       Arcaden"), und bleibt ein Ort.

    Klammerzusätze fallen vorher weg: „Elbsee (Düsseldorf)" ist ein Wikipedia-Lemma, kein Name.
    Stadtname und Adjektiv kommen aus ``city`` des Profils; ohne beide gibt es keine Regel.
    """
    plain = PARENTHESIS.sub(" ", label)
    tokens = [word.lower() for word in WORD.findall(plain)]
    if not tokens:
        return False
    if any(token.endswith(place.lower()) for token in tokens for place in place_words if place):
        return False
    if any(adjective.lower() in tokens for adjective in city_adjectives if adjective):
        return True
    return bool(city_name) and tokens[-1] == city_name.lower()


@deal.pre(lambda pois, city_name, city_adjectives, place_words, keep: has_columns(pois, "label"))
@deal.post(lambda result: result.columns == POI_COLUMNS)
@deal.ensure(
    lambda pois, city_name, city_adjectives, place_words, keep, result: result.height <= pois.height
)
def drop_city_facilities(
    pois: pl.DataFrame,
    city_name: str,
    city_adjectives: Sequence[str],
    place_words: Sequence[str],
    keep: Iterable[str],
) -> pl.DataFrame:
    """Die Orte ohne die Einrichtungen mit Stadtnamen; Reihenfolge und Spalten bleiben.

    ``keep`` sind die Labels, die das Profil ausdrücklich als Ort behält
    (``search.city_facilities_keep``); verglichen wird wie im Wörterbuch, also getrimmt und
    kleingeschrieben.
    """
    kept = {label.strip().lower() for label in keep}
    facility = [
        str(label).strip().lower() not in kept
        and is_city_facility(str(label), city_name, city_adjectives, place_words)
        for label in pois.get_column("label").to_list()
    ]
    return pois.filter(~pl.Series(facility, dtype=pl.Boolean)).select(POI_COLUMNS)


@deal.pre(lambda clean: has_columns(clean, DISTRICT, "label"))
@deal.post(lambda result: result.columns == [DISTRICT, TERMS])
@deal.post(lambda result: sorted_unique(result, DISTRICT) and lists_sorted_unique(result, TERMS))
def pois_by_district(clean: pl.DataFrame) -> pl.DataFrame:
    return clean.group_by(DISTRICT).agg(pl.col("label").unique().sort().alias(TERMS)).sort(DISTRICT)
