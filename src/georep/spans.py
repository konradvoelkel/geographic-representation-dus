"""Spannen: eine Stelle im Text eines Dokuments, für alle Vorhaben in derselben Form.

Fundament F3 der Vorverarbeitung 2026-11 (``docs/plan-vorverarbeitung-2026-11.md``, § 7). Abschnitte
(Vorhaben 11), Kennungen und Beträge (12), Verweise auf Drucksachen (14), Ortsbezüge (16) und
Abstimmungsformeln (28) bezeichnen je eine Stelle im Text. Sie teilen ein Schema, damit die
Kodieraufträge von F4 jede Spanne gleich anzeigen und ein Vorhaben die Spannen eines anderen lesen
kann, ohne dessen Code zu kennen.

Eine Zeile ist eine Spanne:

* ``id`` -- die Korpus-ID des Dokuments (wie in ``interim/papers.parquet``);
* ``start``, ``end`` -- Zeichenpositionen im Text, halboffen (``text[start:end]``);
* ``kind`` -- die Art, etwa ``abschnitt``, ``betrag``, ``drucksache``;
* ``value`` -- der Text an der Stelle, wörtlich;
* ``norm`` -- der normalisierte Wert als Text (Betrag in Euro als Dezimalzahl mit Punkt, Datum
  ISO, Drucksachennummer kanonisch); leer, wo die Art keinen kennt;
* ``section`` -- der Abschnitt aus Vorhaben 11, in dem die Spanne liegt; leer, solange es ihn
  nicht gibt;
* ``extractor`` -- welcher Text gemeint ist (der Extraktorname aus dem Textstore, etwa der des
  Rohtexts) und welches Verfahren die Spanne fand, damit Positionen nie auf den falschen Text
  zeigen.

Die Folge ist fest: sortiert nach ``id``, ``start``, ``end``, ``kind`` und bei Gleichstand nach den
übrigen vier (CLAUDE.md: die Zeilenfolge nach einem Join nie dem Zufall überlassen). Zwei Spannen
an derselben Stelle, etwa aus zwei Extraktoren, stehen so in derselben Folge, wie auch immer sie
kamen (Review F7, N2).

Ein Vorhaben darf **hinter** den acht weitere Spalten tragen (Nachzug F3, Entscheidung des
Supervisors vom 2026-11-23, ``docs/plans/00-synergien-2026-11.md``, Konflikt 3): Vorhaben 12 etwa
``attr``, die Form eines Betrags oder Termins. ``check_spans`` prüft die acht in ihrer Folge und mit
ihren Typen und lässt die weiteren unberührt -- was sie bedeuten und ob sie leer sein dürfen, weiß
ihr Vorhaben. ``sort_spans`` behält sie, in ihrer Folge, hinter den acht.

Eine Schema-Version steht hier nicht: sie gehört dem Modul, das eine Spannen-Datei schreibt, und
steht an dessen Schritt (CLAUDE.md, „Jeder ``Step`` bekommt seine Schema-Version aus der Konstante
des Moduls, das die Datei schreibt").
"""

from __future__ import annotations

from collections.abc import Mapping

import deal
import polars as pl

from georep.errors import SchemaError

SPAN_SCHEMA: dict[str, pl.DataType] = {
    "id": pl.String(),
    "start": pl.Int64(),
    "end": pl.Int64(),
    "kind": pl.String(),
    "value": pl.String(),
    "norm": pl.String(),
    "section": pl.String(),
    "extractor": pl.String(),
}
# Review F7, N2: alle acht, die ersten vier vorn; die Folge hängt nicht an der Eingabe
ORDER = ("id", "start", "end", "kind", "value", "norm", "section", "extractor")


def empty_spans(extra: Mapping[str, pl.DataType] | None = None) -> pl.DataFrame:
    """Ein leerer Frame im Schema der Spannen, mit den Zusatzspalten ``extra`` dahinter.

    Ein Vorhaben mit Zusatzspalte (12: ``attr``) schreibt ohne Treffer dasselbe Schema wie mit
    (Review F7, N3). Eine Zusatzspalte mit dem Namen einer der acht ist ein ``SchemaError``.
    """
    clash = sorted(set(extra or {}) & set(SPAN_SCHEMA))
    if clash:
        raise SchemaError(f"Spannen: Zusatzspalten tragen Namen der acht: {', '.join(clash)}")
    return pl.DataFrame(schema={**SPAN_SCHEMA, **(extra or {})})


def sort_spans(spans: pl.DataFrame) -> pl.DataFrame:
    """Die acht Spalten in Schemafolge, dahinter die weiteren in ihrer Folge; Zeilen in der festen
    Folge."""
    extra = [name for name in spans.columns if name not in SPAN_SCHEMA]
    return spans.select([*SPAN_SCHEMA, *extra]).sort(list(ORDER), maintain_order=True)


def check_spans(spans: pl.DataFrame, lengths: Mapping[str, int]) -> None:
    """``SchemaError``, wenn eine Spanne das Schema, die Folge oder ihren Text verletzt.

    ``lengths`` nennt je Dokument-ID die Länge des Texts, auf den die Positionen zeigen. Geprüft
    werden die acht Spalten vorn in ihrer Folge und mit ihren Typen, ``0 <= start < end <=
    len(text)``, eine bekannte ID je Zeile, kein leeres ``kind`` und die feste Folge. Spalten
    dahinter gehören dem Vorhaben und sind frei. Die Meldung nennt die erste verletzende Zeile.
    """
    # als Liste, nicht als dict: zwei dicts sind gleich, auch wenn ihre Schlüssel anders stehen
    # (Review F7, K1)
    head = list(spans.schema.items())[: len(SPAN_SCHEMA)]
    if head != list(SPAN_SCHEMA.items()):
        raise SchemaError(f"Spannen: Schema {dict(spans.schema)} beginnt nicht mit {SPAN_SCHEMA}")
    core = spans.select(list(SPAN_SCHEMA))
    if core.select(pl.all().is_null().any()).select(pl.any_horizontal(pl.all())).item():
        raise SchemaError(
            "Spannen: leere Werte; norm und section sind leere Zeichenketten, nie null"
        )
    known = pl.DataFrame(
        {"id": list(lengths), "length": list(lengths.values())},
        schema={"id": pl.String(), "length": pl.Int64()},
    )
    # über die acht allein: eine Zusatzspalte darf ``zeile`` oder ``length`` heißen
    checked = core.with_row_index("zeile").join(known, on="id", how="left")
    bad = checked.filter(
        pl.col("length").is_null()
        | (pl.col("start") < 0)
        | (pl.col("start") >= pl.col("end"))
        | (pl.col("end") > pl.col("length"))
        | (pl.col("kind") == "")
    ).sort("zeile")
    if bad.height:
        first = bad.row(0, named=True)
        raise SchemaError(
            f"Spannen: {bad.height} Zeilen außerhalb ihres Texts, erste Zeile {first['zeile']}: "
            f"id={first['id']!r} start={first['start']} end={first['end']} "
            f"Textlänge={first['length']} kind={first['kind']!r}"
        )
    if not spans.equals(sort_spans(spans)):
        raise SchemaError(
            f"Spannen: nicht nach {', '.join(ORDER[:4])} sortiert (bei Gleichstand nach "
            f"{', '.join(ORDER[4:])})"
        )


def _within_text(text: str, start: int, end: int, context: int = 200) -> bool:
    return 0 <= start < end <= len(text) and context >= 0


def _middle_is_the_span(
    text: str, start: int, end: int, context: int = 200, result: tuple[str, str, str] = ("", "", "")
) -> bool:
    return result[1] == text[start:end] and "".join(result) in text


# Benannte Validatoren vor dem Stapel: das deal-Plugin für mypy kennt keine Lambdas mit Vorgaben
# (CLAUDE.md, „Arbeitsweise", deal).
@deal.ensure(
    _middle_is_the_span, message="die Mitte ist die Spanne, alle drei Teile am Stück im Text"
)
@deal.pre(_within_text, message="0 <= start < end <= len(text), context >= 0")
@deal.pure
def excerpt(text: str, start: int, end: int, context: int = 200) -> tuple[str, str, str]:
    """Die Spanne mit Kontext: (davor, die Spanne selbst, danach), je höchstens ``context`` Zeichen.

    Für die Kodieraufträge (F4) und für Beispiele in Messdokumenten; die Mitte ist genau
    ``text[start:end]``.
    """
    return text[max(0, start - context) : start], text[start:end], text[end : end + context]
