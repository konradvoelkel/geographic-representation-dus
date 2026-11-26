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
* ``value`` -- der Text an der Stelle, wörtlich (``text[start:end]``), oder leer bei einer
  **Positionsspanne**: einer Stelle, deren Text man über ``read_span`` liest, etwa einem Abschnitt
  aus Vorhaben 11. Nie eine bearbeitete Form -- die steht in ``norm`` (Entscheidung des Eigentümers
  von F3, 2026-11-24, Review von Vorhaben 11, K1);
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

import re
from collections.abc import Collection, Mapping, Sequence

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


def check_spans(
    spans: pl.DataFrame,
    lengths: Mapping[str, int],
    *,
    texts: Mapping[str, str] | None = None,
    positions: Collection[str] | None = None,
) -> None:
    """``SchemaError``, wenn eine Spanne das Schema, die Folge oder ihren Text verletzt.

    ``lengths`` nennt je Dokument-ID die Länge des Texts, auf den die Positionen zeigen. Geprüft
    werden die acht Spalten vorn in ihrer Folge und mit ihren Typen, ``0 <= start < end <=
    len(text)``, eine bekannte ID je Zeile, kein leeres ``kind`` und die feste Folge. Spalten
    dahinter gehören dem Vorhaben und sind frei. Wer die Texte selbst zur Hand hat, gibt sie als
    ``texts`` mit; dann ist jedes ``value`` wörtlich ``text[start:end]`` oder leer (eine
    Positionsspanne), und wer ``positions`` nennt, erlaubt das leere ``value`` nur diesen Arten
    (Vorhaben 11: nur den Abschnitten). Die Meldung nennt die erste verletzende Zeile.
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
    if texts is not None:
        _check_values(core, texts, positions)


def _check_values(
    core: pl.DataFrame, texts: Mapping[str, str], positions: Collection[str] | None
) -> None:
    """Jedes ``value`` ist wörtlich der Text an der Stelle oder leer (F3, 2026-11-24); eine ID ohne
    Text in ``texts`` bleibt ungeprüft. Mit ``positions`` ist leer nur bei diesen Arten erlaubt."""
    # je Zeile in Python, nicht als Join: der Join trüge jeden Text einmal je Spanne
    rows = core.select("id", "start", "end", "kind", "value").iter_rows()
    for row, (doc_id, start, end, kind, value) in enumerate(rows):
        if not value and positions is not None and kind not in positions:
            raise SchemaError(
                f"Spannen: value leer, aber {kind!r} ist keine Positionsspanne, erste Zeile {row}: "
                f"id={doc_id!r} start={start} end={end}"
            )
        text = texts.get(doc_id)
        if value and text is not None and text[start:end] != value:
            raise SchemaError(
                f"Spannen: value nicht wörtlich und nicht leer, erste Zeile {row}: "
                f"id={doc_id!r} start={start} end={end} value={value[:40]!r}"
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


# --- Vorhaben 11 (docs/plans/11-struktur.md, § 10, Punkt 3): der Abschnitt einer Spanne und das
# Lesen einer Spanne ohne Seitenkopfzeilen. Beide für alle, die Spannen auf dem Rohtext schreiben
# oder lesen (12, 16, 17, 20), statt eines eigenen Joins oder einer eigenen Lesefunktion je Vorhaben.

SECTION_KIND = "abschnitt"  # ``kind`` der Abschnittsspannen aus Vorhaben 11
_PAGE_BREAK = "\f"  # stores.PAGE_BREAK; hier literal, damit dieses Modul nichts aus den Stores lädt


def _section_rows(spans: pl.DataFrame, sections: pl.DataFrame, result: pl.DataFrame) -> bool:
    return result.height == spans.height and result.columns == spans.columns


@deal.ensure(_section_rows, message="dieselben Zeilen und Spalten, nur section neu")
def section_of(spans: pl.DataFrame, sections: pl.DataFrame) -> pl.DataFrame:
    """Je Spanne der Abschnitt der Ebene 1, in dem ihr **Anfang** liegt, in ``section``; sonst leer.

    ``sections`` sind die Abschnittsspannen aus Vorhaben 11 (``dokumente_abschnitte.parquet``):
    eine Zeile der Ebene 1 hat ``kind == "abschnitt"`` und ``section == norm`` (Betreff,
    Beschlussvorschlag, Sachdarstellung, Rumpf, ``kopf_amt`` …). Eine Zeile der Ebene 2 (Finanzen,
    Klima) nennt in ``section`` den Abschnitt der Ebene 1 um sie herum und bestimmt hier nichts:
    die Abschnitte der Ebene 1 überlappen sich nicht, also gibt es je Stelle höchstens einen.
    Die Kopffelder (``kind`` = ``amt``, ``beratung`` …) zählen ebenfalls nicht.

    Zeilen, Folge und alle anderen Spalten, auch Zusatzspalten hinter den acht (Punkt 74), bleiben,
    wie sie sind; ein ``section`` der Eingabe wird überschrieben. Beide Tabellen müssen ihre
    Positionen auf **denselben** Text beziehen (den Rohtext aus F1; ``extractor`` sagt es).
    """
    level1 = sections.filter(
        (pl.col("kind") == SECTION_KIND)
        & (pl.col("section") == pl.col("norm"))
        & (pl.col("norm") != "")
    ).select(
        "id",
        pl.col("start").alias("_von"),
        pl.col("end").alias("_bis"),
        pl.col("norm").alias("_abschnitt"),
    )
    rows = spans.select("id", "start").with_row_index("_zeile")
    # je Spanne die Abschnitte desselben Dokuments, dann der eine, in dem der Anfang liegt; eine
    # Eingabe mit überlappenden Abschnitten nähme den vordersten (Folge nach dem Anfang, fest)
    found = (
        rows.join(level1, on="id", how="inner")
        .filter((pl.col("start") >= pl.col("_von")) & (pl.col("start") < pl.col("_bis")))
        .sort("_zeile", "_von")
        .unique("_zeile", keep="first", maintain_order=True)
        .select("_zeile", "_abschnitt")
    )
    named = (
        rows.join(found, on="_zeile", how="left")
        .sort("_zeile")
        .get_column("_abschnitt")
        .fill_null("")
    )
    return spans.with_columns(named.alias("section"))


def _span_within_text(text: str, start: int, end: int, noise: Sequence[str] = ()) -> bool:
    return 0 <= start <= end <= len(text)


def _noise_compiles(text: str, start: int, end: int, noise: Sequence[str] = ()) -> bool:
    try:
        for pattern in noise:
            re.compile(pattern)
    except re.error:
        return False
    return True


def _read_without_page_breaks(
    text: str, start: int, end: int, noise: Sequence[str] = (), result: str = ""
) -> bool:
    return (
        _PAGE_BREAK not in result
        and len(result) <= end - start
        and (bool(noise) or result == text[start:end].replace(_PAGE_BREAK, "\n"))
    )


# Benannte Validatoren vor dem Stapel: das deal-Plugin für mypy kennt keine Lambdas mit Vorgaben
# (CLAUDE.md, „Arbeitsweise", deal). ``deal.safe``, nicht ``deal.pure``: die Funktion läuft je
# Abschnitt und Dokument (CLAUDE.md, „Nie").
@deal.pre(_span_within_text, message="0 <= start <= end <= len(text)")
@deal.pre(_noise_compiles, message="jedes Muster in noise ist ein gültiger regulärer Ausdruck")
@deal.ensure(
    _read_without_page_breaks,
    message="ohne Seitenwechsel, nie länger als die Spanne; ohne Muster genau die Spanne",
)
@deal.safe
def read_span(text: str, start: int, end: int, noise: Sequence[str] = ()) -> str:
    """Der Text der Spanne ``text[start:end]``, ohne die Zeilen, die ein Muster aus ``noise`` ganz
    trifft (Seitenkopfzeilen wie „Seite 2" oder „Sitzung des … am … Vorlage …", Frage 9.6).

    Die Spannen behalten die rohen Offsets; wer ihren Text liest (16, 20), liest ihn hier. Eine
    Zeile zählt als Rauschen, wenn ein Muster sie ohne Leerraum an den Rändern ganz trifft
    (``re.fullmatch``); Zeilen sind durch Zeilenumbruch und Seitenwechsel getrennt, wie
    ``prep.raw_texts.split_lines``, und kommen mit ``\\n`` verbunden zurück. Eine Zeile, die
    die Spanne nur zum Teil trifft, wird nach dem Teil in der Spanne beurteilt. Die Muster
    stehen im Profil (``structure.page_noise``).
    """
    piece = text[start:end].replace(_PAGE_BREAK, "\n")
    if not noise:
        return piece
    return "\n".join(
        line
        for line in piece.split("\n")
        if not any(re.fullmatch(pattern, line.strip()) for pattern in noise)
    )
