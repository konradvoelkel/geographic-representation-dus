"""Fremddaten je Raumeinheit zu Kontrollvariablen je Wahlbezirk.

Drei Schritte, alle rein und Frame zu Frame: ``precinct_table`` verbindet Stimmbezirksflächen mit
den Wahlberechtigten der Wahlergebnis-CSV und ist die Eingabe des Crosswalks
(``georep.crosswalk``); ``read_context_table`` liest die Tabelle der Quelle (Dezimalkomma,
Vorzeichen, Fehlwertmarker, ordinale Stufen über eine Skala) und ``aggregate_context`` mittelt sie
mit den Gewichten des Crosswalks auf die Wahlbezirke.

Nichts hier kennt die Stadt: Spalten, Skalen, Variablen und Schwellen stehen in
``settings.context`` (docs/architecture.md, „Kontextdaten"; docs/plans/03-kontrollvariablen.md).
"""

from __future__ import annotations

import io
import math
import zipfile
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import deal
import polars as pl

from georep.contracts import has_columns, is_municipality_key, keys_sorted_unique, sorted_unique
from georep.crosswalk import (
    DISTRICT,
    ELIGIBLE,
    POINT,
    POINT_SHARE,
    PRECINCT,
    UNIT,
    UNIT_NAME,
    WEIGHT,
)
from georep.errors import EmptyResultError, SchemaError
from georep.geo import Precinct
from georep.prep.voters import ELIGIBLE_TOTAL
from georep.settings import ContextSettings, ContextTable, ContextVariable, ResultsColumns


def _one_row_per_precinct(result: pl.DataFrame) -> bool:
    return sorted_unique(result, PRECINCT) and bool((result.get_column(ELIGIBLE) > 0).all())


@deal.pre(
    lambda precincts, results, columns: (
        len(precincts) > 0
        and bool(columns.precinct)
        and has_columns(results, columns.precinct, columns.district, ELIGIBLE_TOTAL)
    ),
    message="Stimmbezirke, die CSV-Spalten des Wahlergebnisses und ein Spaltenname für den Stimmbezirk",
)
@deal.post(_one_row_per_precinct, message="eine Zeile je Stimmbezirk, Wahlberechtigte positiv")
@deal.ensure(
    lambda precincts, results, columns, result: result.height <= len(precincts),
    message="höchstens so viele Zeilen wie Stimmbezirke mit Fläche",
)
@deal.raises(SchemaError)
def precinct_table(
    precincts: Sequence[Precinct], results: pl.DataFrame, columns: ResultsColumns
) -> pl.DataFrame:
    """Eine Zeile je Stimmbezirk mit Fläche: ``stimmbezirk_id``, ``wahlkreis_id``, ``wahlberechtigte``.

    Der Wahlbezirk kommt aus dem GeoJSON (es trägt die Fläche, Frage 3.7), die Wahlberechtigten aus
    der CSV. Zeilen der CSV ohne Fläche fallen weg: Briefwahlbezirke sind keine Gebiete, ihre
    Stimmen gehören zu keinem Ort. Fehlt ein Stimmbezirk der Fläche in der CSV, ist das ein
    ``SchemaError`` -- dann passen die beiden Dateien nicht zusammen.
    """
    geometry = pl.DataFrame(
        {
            PRECINCT: [p.precinct_id for p in precincts],
            DISTRICT: [p.district_id for p in precincts],
        },
        schema={PRECINCT: pl.String, DISTRICT: pl.Int64},
    )
    counts = results.select(
        pl.col(columns.precinct).str.strip_chars().alias(PRECINCT),
        pl.col(ELIGIBLE_TOTAL)
        .str.strip_chars()
        .cast(pl.Int64, strict=False)
        .fill_null(0)
        .alias(ELIGIBLE),
    )
    joined = geometry.join(counts, on=PRECINCT, how="left")
    missing = joined.filter(pl.col(ELIGIBLE).is_null()).get_column(PRECINCT).to_list()
    if missing:
        raise SchemaError(
            f"Stimmbezirke mit Fläche, aber ohne Zeile im Wahlergebnis: {sorted(missing)}"
        )
    empty = joined.filter(pl.col(ELIGIBLE) <= 0).get_column(PRECINCT).to_list()
    if empty:
        raise SchemaError(f"Stimmbezirke ohne Wahlberechtigte: {sorted(empty)}")
    return joined.sort(PRECINCT)


# Erhoehen, wenn sich Spalten, Typen oder die **Zeilenfolge** von wahlbezirke_kontext.parquet
# oder wahlbezirke_crosswalk.parquet aendern. 2: beide Dateien sind seit dem 2026-10-13 nach
# ihrem Schluessel sortiert (Punkt 53) -- ein Lauf von vorher liegt unsortiert da, und nur
# ueber die Version merkt der Stamp das (CLAUDE.md, "Jeder Step bekommt seine Schema-Version
# aus der Konstante des Moduls").
CONTEXT_SCHEMA_VERSION = 2
MISSING_SUFFIX = "_fehlgewicht"  # Anteil des Gewichts eines Wahlbezirks auf Einheiten ohne Wert


@deal.pure
@deal.pre(lambda value, scale: len(scale) > 0, message="die Skala nennt mindestens eine Stufe")
@deal.ensure(
    lambda value, scale, result: result is None or result in scale.values(),
    message="das Ergebnis ist ein Wert der Skala oder None",
)
def ordinal_score(value: str, scale: Mapping[str, int]) -> int | None:
    """Die Stufe eines ordinalen Index als Zahl; ``None``, wenn der Text keine Stufe benennt.

    Rein und darum in ``noxfile.VERIFY_TARGETS``. Aufgerufen wird sie je *verschiedener* Stufe
    einer Spalte (eine Handvoll), nicht je Zelle: ``deal.pure`` patcht prozessweit und gehört in
    keine heiße Schleife (CLAUDE.md).
    """
    return scale.get(value.strip())


def _numeric(column: str, table: ContextTable) -> pl.Expr:
    """Text der Quelle zu Float64: Dezimalkomma, Vorzeichen ``+``, Fehlwertmarker zu null."""
    cleaned = pl.col(column).str.strip_chars()
    return (
        pl.when(cleaned.is_in(list(table.missing)) | (cleaned == ""))
        .then(None)
        .otherwise(cleaned.str.strip_prefix("+").str.replace(table.decimal, ".", literal=True))
        .cast(pl.Float64, strict=False)
        .alias(column)
    )


def _ordinal(column: str, levels: dict[str, int | None]) -> pl.Expr:
    return (
        pl.col(column)
        .str.strip_chars()
        .replace_strict(levels, default=None, return_dtype=pl.Float64)
    )


def _variable_expression(
    variable: ContextVariable, frame: pl.DataFrame, context: ContextSettings
) -> pl.Expr:
    table = context.table
    if variable.kind == "ordinal":
        assert variable.scale is not None  # der Settings-Validator verlangt sie
        scale = context.scales[variable.scale]
        column = variable.columns[0]
        # Getrimmt schlüsseln: ``_ordinal`` trimmt vor dem Nachschlagen, und eine Stufe mit
        # Leerzeichen fiele sonst still auf null statt auf ihren Wert (Review 2026-10-12).
        seen = {v.strip() for v in frame.get_column(column).unique().to_list() if v is not None}
        levels: dict[str, int | None] = {v: ordinal_score(v, scale) for v in sorted(seen)}
        unknown = sorted(
            v for v, score in levels.items() if score is None and v not in table.missing
        )
        if unknown:
            raise SchemaError(
                f"{column}: Stufen ohne Eintrag in context.scales.{variable.scale}: {unknown}; "
                f"bekannt sind {sorted(scale)}"
            )
        return (_ordinal(column, levels) * variable.factor).alias(variable.name)
    numbers = [_numeric(c, table) for c in variable.columns]
    # ignore_nulls=False: fehlt ein Summand, ist die Summe unbekannt und nicht der Rest.
    total = numbers[0] if len(numbers) == 1 else pl.sum_horizontal(*numbers, ignore_nulls=False)
    return (total * variable.factor).alias(variable.name)


def _one_row_per_unit(result: pl.DataFrame) -> bool:
    return sorted_unique(result, UNIT) and result.columns[:2] == [UNIT, UNIT_NAME]


@deal.post(_one_row_per_unit, message="eine Zeile je Raumeinheit, Schlüssel und Name zuerst")
@deal.raises(SchemaError)
def read_context_table(path: Path, context: ContextSettings) -> pl.DataFrame:
    """Die Tabelle der Quelle als eine Float64-Spalte je Variable, Schlüssel und Name als Text.

    Alles wird als Text gelesen und dann umgerechnet: Dezimalkomma, das ``+`` positiver Salden,
    die Fehlwertmarker der Quelle (anonymisierte Werte unter 3, leere Einheiten) und die Stufen
    der ordinalen Spalten über ``context.scales``. Eine fehlende Spalte oder eine unbekannte Stufe
    ist ein ``SchemaError``: die Settings und die Datei passen dann nicht zusammen.
    """
    table = context.table
    text = path.read_bytes().decode(table.encoding)
    frame = pl.read_csv(io.BytesIO(text.encode("utf-8")), separator=table.sep, infer_schema=False)
    wanted = [table.key, table.name, *(c for v in context.unit_variables() for c in v.columns)]
    missing = [c for c in dict.fromkeys(wanted) if c not in frame.columns]
    if missing:
        raise SchemaError(f"{path.name}: Spalten fehlen: {missing}")
    return frame.select(
        pl.col(table.key).str.strip_chars().alias(UNIT),
        pl.col(table.name).str.strip_chars().alias(UNIT_NAME),
        *(_variable_expression(v, frame, context) for v in context.unit_variables()),
    ).sort(UNIT)


@deal.raises(SchemaError)
def read_indicators(path: Path, context: ContextSettings) -> dict[str, str]:
    """Indikator -> Definition aus der Erläuterungsdatei der Quelle, Leerraum normalisiert.

    Die Definitionen stehen auf der Seite im Abschnitt „Abgeleitete Daten"; nennt eine Variable in
    den Settings einen Indikator, den die Datei nicht führt, ist das ein ``SchemaError`` -- so
    fällt ein Tippfehler auf und eine neue Fassung der Datei ebenso.
    """
    table = context.table
    text = path.read_bytes().decode(table.encoding)
    frame = pl.read_csv(io.BytesIO(text.encode("utf-8")), separator=table.sep, infer_schema=False)
    missing = [c for c in (table.indicator, table.definition) if c not in frame.columns]
    if missing:
        raise SchemaError(f"{path.name}: Spalten fehlen: {missing}")
    found = {
        str(row[table.indicator]).strip(): " ".join(str(row[table.definition] or "").split())
        for row in frame.iter_rows(named=True)
    }
    wanted = {v.indicator.strip() for v in context.variables if v.indicator}
    absent = sorted(wanted - set(found))
    if absent:
        raise SchemaError(f"{path.name}: Indikatoren der Settings fehlen in der Datei: {absent}")
    return found


def _weighted_mean(name: str) -> list[pl.Expr]:
    """Mittel über die Einheiten mit Wert und das Gewicht der Einheiten ohne.

    Liegt das ganze Gewicht auf Einheiten ohne Wert, ist das Mittel ``null`` und nicht ``NaN``:
    unbekannt ist kein Zahlenwert, und NaN stünde sonst in Parquet und auf der Seite.
    """
    present = pl.col(name).is_not_null()
    weight = pl.col(WEIGHT)
    known = weight.filter(present).sum()
    return [
        pl.when(known > 0)
        .then((pl.col(name) * weight).filter(present).sum() / known)
        .otherwise(None)
        .alias(name),
        weight.filter(~present).sum().alias(f"{name}{MISSING_SUFFIX}"),
    ]


def _scores_within_their_scale(
    weights: pl.DataFrame,
    values: pl.DataFrame,
    context: ContextSettings,
    result: pl.DataFrame | None = None,
) -> bool:
    assert result is not None
    for variable in context.unit_variables():
        if variable.scale is None:
            continue
        scale = context.scales[variable.scale]
        low, high = min(scale.values()) * variable.factor, max(scale.values()) * variable.factor
        column = result.get_column(variable.name).drop_nulls()
        if column.len() and not bool(((column >= low) & (column <= high)).all()):
            return False
    return True


@deal.pre(
    lambda weights, values, context: (
        has_columns(weights, DISTRICT, UNIT, WEIGHT)
        and has_columns(values, UNIT, *(v.name for v in context.unit_variables()))
    ),
    message="Gewichte je Wahlbezirk und Einheit, Werte je Einheit",
)
@deal.post(lambda result: sorted_unique(result, DISTRICT), message="eine Zeile je Wahlbezirk")
@deal.ensure(
    lambda weights, values, context, result: (
        set(result.get_column(DISTRICT)) == set(weights.get_column(DISTRICT))
    ),
    message="genau die Wahlbezirke der Gewichte",
)
@deal.ensure(_scores_within_their_scale, message="ordinale Mittel liegen in ihrer Skala")
@deal.raises(EmptyResultError)
def aggregate_context(
    weights: pl.DataFrame, values: pl.DataFrame, context: ContextSettings
) -> pl.DataFrame:
    """Gewichtetes Mittel je Wahlbezirk, plus je Variable den Anteil des Gewichts ohne Wert.

    Einheiten ohne Wert fallen aus dem Mittel heraus, und die übrigen Gewichte werden renormiert;
    stilles Auffüllen mit 0 verfälschte Anteile. Liegt mehr als ``context.max_missing_weight`` des
    Gewichts eines Wahlbezirks auf Einheiten ohne Wert, ist das Mittel nichts wert:
    ``EmptyResultError`` mit Variable und Wahlbezirk.
    """
    names = [v.name for v in context.unit_variables()]
    # Sortieren und maintain_order: ein Join liefert die Zeilen in keiner festgelegten Reihenfolge,
    # und eine Fließkommasumme hängt von ihr im letzten Bit ab. Zwei Läufe sollen dieselbe
    # Parquet-Datei schreiben (2026-10-12).
    joined = weights.join(values.select(UNIT, *names), on=UNIT, how="left").sort([DISTRICT, UNIT])
    frame = joined.group_by(DISTRICT, maintain_order=True).agg(
        *(expr for name in names for expr in _weighted_mean(name))
    )
    for name in names:
        too_much = frame.filter(pl.col(f"{name}{MISSING_SUFFIX}") > context.max_missing_weight)
        if not too_much.is_empty():
            worst = too_much.sort(f"{name}{MISSING_SUFFIX}", descending=True).row(0, named=True)
            raise EmptyResultError(
                f"Variable {name!r}: in Wahlbezirk {worst[DISTRICT]} liegen "
                f"{worst[f'{name}{MISSING_SUFFIX}']:.3f} des Gewichts auf Einheiten ohne Wert "
                f"(erlaubt {context.max_missing_weight}); context.max_missing_weight anheben "
                "oder die Variable streichen"
            )
    return frame.select(DISTRICT, *names, *(f"{n}{MISSING_SUFFIX}" for n in names))


def _named_weights_are_ordered(result: pl.DataFrame) -> bool:
    keys = list(result.select(DISTRICT, UNIT).iter_rows())
    return result.columns == [DISTRICT, UNIT, UNIT_NAME, WEIGHT] and keys == sorted(keys)


@deal.pre(
    lambda weights, values: (
        has_columns(weights, DISTRICT, UNIT, WEIGHT) and has_columns(values, UNIT, UNIT_NAME)
    ),
    message="Gewichte je Wahlbezirk und Einheit, Namen je Einheit",
)
@deal.post(_named_weights_are_ordered, message="Spalten und Folge der veröffentlichten Tabelle")
def named_weights(weights: pl.DataFrame, values: pl.DataFrame) -> pl.DataFrame:
    """Die Gewichte mit dem Namen der Einheit: ``wahlbezirke_crosswalk.parquet``.

    Die Tabelle wird veröffentlicht, und zwei Läufe auf denselben Eingaben sollen sie
    byteidentisch schreiben (docs/architecture.md, „Datenhaltung"). Der Join auf ``einheit`` legt
    die Zeilenfolge aber nicht fest -- bis zum 2026-10-13 stand hier keine Sortierung, und die
    Zusage galt nur zufällig. Sortiert wird nach Wahlbezirk und Einheit, nicht nach Gewicht: die
    Datei ist zum Nachschlagen da, nicht zum Ranking.
    """
    return (
        weights.join(values.select(UNIT, UNIT_NAME), on=UNIT, how="left")
        .select(DISTRICT, UNIT, UNIT_NAME, WEIGHT)
        .sort([DISTRICT, UNIT])
    )


@deal.pre(
    lambda voters, context: has_columns(voters, DISTRICT),
    message="die Wählertabelle mit dem Wahlbezirk",
)
@deal.post(lambda result: sorted_unique(result, DISTRICT))
@deal.raises(SchemaError)
def district_variables(voters: pl.DataFrame, context: ContextSettings) -> pl.DataFrame:
    """Variablen, die schon je Wahlbezirk vorliegen (Stimmenanteile), mit ihrem Faktor skaliert."""
    variables = context.district_variables()
    missing = [c for v in variables for c in v.columns if c not in voters.columns]
    if missing:
        raise SchemaError(f"Wählertabelle: Spalten der Kontrollvariablen fehlen: {missing}")
    return voters.select(
        pl.col(DISTRICT),
        *((pl.col(v.columns[0]) * v.factor).alias(v.name) for v in variables),
    ).sort(DISTRICT)


# --- Vorhaben 22: Bedarf aus Punkten und Gitterzellen (docs/plans/22-bedarf.md, § 6) ----------
#
# Die Leser nehmen die Archive, wie die Quellen sie liefern (ein Zip mit einer CSV, eine CSV), und
# schneiden die Gemeinde heraus; was sie lesen, ist die Form der bundes- oder landesweiten Datei und
# steht darum als Konstante hier, die Gemeinde kommt als ``city.ags``. Die Aggregate je Wahlbezirk
# nehmen die Anteile aus ``crosswalk.point_shares``: Unfälle mit Randband, Gitterzellen und
# Schulen scharf (Band 0, Frage 22.4). Alles Frame zu Frame, sortiert, mit Verträgen hier an der
# Batch-Grenze und nicht in den Schleifen.

# Erhöhen, wenn sich Spalten, Typen oder die Zeilenfolge der Stadtauszüge unter external/bedarf/
# (need_data) oder von wahlbezirke_bedarf.parquet und bedarf_hypothesen.parquet (need) ändern
# (CLAUDE.md: die Schema-Version aus der Konstante des Moduls).
NEED_SCHEMA_VERSION = 1  # Schritt need: wahlbezirke_bedarf und bedarf_hypothesen
NEED_DATA_SCHEMA_VERSION = 1  # Schritt need_data: die Stadtauszüge unter external/bedarf/
NEED_DIR = "bedarf"  # unter external/ im Lauf und im Paket
ACCIDENTS_FILE = "unfaelle.parquet"
GRID_FILE = "zensus2022.parquet"
SCHOOLS_FILE = "schulen.parquet"
SOURCES_FILE = "quellen.json"
NEED_FILES = (ACCIDENTS_FILE, GRID_FILE, SCHOOLS_FILE, SOURCES_FILE)

ACCIDENTS_SCHEMA: dict[str, pl.DataType] = {
    "jahr": pl.Int64(),
    "monat": pl.Int64(),
    "kategorie": pl.Int64(),  # 1 Getötete, 2 Schwerverletzte, 3 Leichtverletzte
    "rad": pl.Int64(),
    "fuss": pl.Int64(),
    "x": pl.Float64(),
    "y": pl.Float64(),
}
GRID_SCHEMA: dict[str, pl.DataType] = {
    "x": pl.Int64(),  # Mittelpunkt der Zelle im CRS der Quelle
    "y": pl.Int64(),
    "einwohner": pl.Int64(),
    "miete": pl.Float64(),  # durchschnittliche Nettokaltmiete je m²
    "miete_zeichen": pl.String(),  # werterläuterndes Zeichen der Quelle (KLAMMERN: unsicher)
}
SCHOOLS_SCHEMA: dict[str, pl.DataType] = {
    "schulnummer": pl.String(),
    "schulform": pl.String(),
    "x": pl.Float64(),
    "y": pl.Float64(),
    "sozialindex": pl.Int64(),  # Stufe 1 bis 9; null: die Liste nennt „ohne" oder die Schule nicht
}

# Die Spalten des Unfallatlas, die jeder Jahrgang trägt; der Rest wechselt (OBJECTID, OID_, …).
_ACCIDENT_KEYS = ("ULAND", "UREGBEZ", "UKREIS", "UGEMEINDE")
_ACCIDENT_COLUMNS = (
    *_ACCIDENT_KEYS,
    "UJAHR",
    "UMONAT",
    "UKATEGORIE",
    "IstRad",
    "IstFuss",
    "LINREFX",
    "LINREFY",
)
_GRID_POPULATION = ("x_mp_100m", "y_mp_100m", "Einwohner")
_GRID_RENT = ("x_mp_100m", "y_mp_100m", "durchschnMieteQM", "werterlaeuternde_Zeichen")
_SCHOOL_COLUMNS = (
    "Schulnummer",
    "Schulform",
    "Gemeindeschluessel",
    "EPSG",
    "UTMRechtswert",
    "UTMHochwert",
)
_INDEX_COLUMNS = ("Schulnummer", "Sozialindexstufe")
UNSPECIFIED_CRS = "null"  # so stehen Schulen ohne CRS-Angabe in den Schuldaten


@deal.pure
@deal.pre(lambda ags: is_municipality_key(ags), message="acht ASCII-Ziffern")
@deal.ensure(
    lambda ags, result: f"{result[0]:02d}{result[1]}{result[2]:02d}{result[3]:03d}" == ags,
    message="die Teile ergeben den Schlüssel",
)
def ags_parts(ags: str) -> tuple[int, int, int, int]:
    """Land, Regierungsbezirk, Kreis, Gemeinde aus dem achtstelligen Schlüssel (``05 1 11 000``).

    Als Zahlen, denn der Unfallatlas schreibt sie je Jahrgang verschieden: ``05`` oder ``5``.
    """
    return int(ags[:2]), int(ags[2]), int(ags[3:5]), int(ags[5:])


def _strip_bom(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.rename({c: c.lstrip("﻿") for c in frame.columns})


def _require(frame: pl.DataFrame, columns: Sequence[str], where: str) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise SchemaError(f"{where}: Spalten fehlen: {missing}")


def _decimal(column: str) -> pl.Expr:
    """Text mit Dezimalkomma zu Float64; Leeres und Unlesbares zu null."""
    return (
        pl.col(column)
        .str.strip_chars()
        .str.replace(",", ".", literal=True)
        .cast(pl.Float64, strict=False)
    )


def _integer(column: str) -> pl.Expr:
    return pl.col(column).str.strip_chars().cast(pl.Int64, strict=False)


def _table_member(archive: zipfile.ZipFile, path: Path) -> str:
    """Die Tabelle eines Jahresarchivs: die größte Datei, die kein Ordner und kein ``schema.ini`` ist.

    Die Jahrgänge heißen verschieden (``csv/Unfallorte2020_LinRef.csv``,
    ``Unfallorte2021_EPSG25832_CSV/Unfallorte_2021_LinRef.txt``, ``csv/…_LR_BasisDLM.csv``).
    """
    members = [
        info
        for info in archive.infolist()
        if not info.is_dir() and not info.filename.lower().endswith("schema.ini")
    ]
    if not members:
        raise SchemaError(f"{path.name}: keine Tabelle im Archiv")
    return max(members, key=lambda info: (info.file_size, info.filename)).filename


def _open_zip(path: Path) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise SchemaError(f"{path.name}: kein Zip ({error})") from error


@deal.pre(lambda path, ags: is_municipality_key(ags), message="acht ASCII-Ziffern")
@deal.post(lambda result: result.schema == pl.Schema(ACCIDENTS_SCHEMA))
@deal.raises(SchemaError)
def read_accidents(path: Path, ags: str) -> pl.DataFrame:
    """Die Unfälle einer Gemeinde aus einem Jahresarchiv des Unfallatlas, sortiert.

    Gelesen wird alles als Text: die Schlüssel tragen führende Nullen oder nicht, die Koordinaten
    ein Dezimalkomma, und der Kopf manches Jahrgangs ein BOM vor der ersten Spalte.
    """
    with _open_zip(path) as archive:
        member = _table_member(archive, path)
        raw = _strip_bom(pl.read_csv(archive.read(member), separator=";", infer_schema=False))
    _require(raw, _ACCIDENT_COLUMNS, f"{path.name}/{member}")
    keys = [_integer(c) == v for c, v in zip(_ACCIDENT_KEYS, ags_parts(ags), strict=True)]
    return (
        raw.filter(*keys)
        .select(
            _integer("UJAHR").alias("jahr"),
            _integer("UMONAT").alias("monat"),
            _integer("UKATEGORIE").alias("kategorie"),
            _integer("IstRad").alias("rad"),
            _integer("IstFuss").alias("fuss"),
            _decimal("LINREFX").alias("x"),
            _decimal("LINREFY").alias("y"),
        )
        .sort("jahr", "monat", "x", "y")
    )


def _grid_part(
    path: Path, member: str, columns: Sequence[str], box: tuple[int, int, int, int]
) -> pl.DataFrame:
    with _open_zip(path) as archive:
        if member not in archive.namelist():
            raise SchemaError(f"{path.name}: {member} fehlt im Archiv")
        raw = _strip_bom(pl.read_csv(archive.read(member), separator=";", infer_schema=False))
    _require(raw, columns, f"{path.name}/{member}")
    return raw.select(
        _integer("x_mp_100m").alias("x"), _integer("y_mp_100m").alias("y"), *columns[2:]
    ).filter(pl.col("x").is_between(box[0], box[2]), pl.col("y").is_between(box[1], box[3]))


@deal.pre(
    lambda population, population_member, rent, rent_member, box: (
        box[0] <= box[2] and box[1] <= box[3]
    ),
    message="ein Rechteck (minx, miny, maxx, maxy)",
)
@deal.post(lambda result: result.schema == pl.Schema(GRID_SCHEMA))
@deal.post(lambda result: keys_sorted_unique(result, "x", "y"), message="eine Zeile je Zelle")
@deal.raises(SchemaError)
def read_grid(
    population: Path,
    population_member: str,
    rent: Path,
    rent_member: str,
    box: tuple[int, int, int, int],
) -> pl.DataFrame:
    """Die Zellen des Zensus-Gitters im Rechteck: Einwohner und Miete, eine Zeile je Mittelpunkt.

    Zwei Dateien, über den Mittelpunkt verbunden; eine Zelle, die nur eine von beiden kennt, bleibt
    mit null auf der anderen Seite. Werte wie ``–`` (gesperrt) werden null; das werterläuternde
    Zeichen der Miete bleibt als Text dabei.
    """
    people = _grid_part(population, population_member, _GRID_POPULATION, box).select(
        "x", "y", _integer("Einwohner").alias("einwohner")
    )
    rents = _grid_part(rent, rent_member, _GRID_RENT, box).select(
        "x",
        "y",
        _decimal("durchschnMieteQM").alias("miete"),
        pl.col("werterlaeuternde_Zeichen")
        .str.strip_chars()
        .replace("", None)
        .alias("miete_zeichen"),
    )
    return (
        people.join(rents, on=["x", "y"], how="full", coalesce=True)
        .select(list(GRID_SCHEMA))
        .cast(GRID_SCHEMA)  # type: ignore[arg-type]
        .sort("x", "y")
    )


def _csv_text(path: Path, encoding: str) -> pl.DataFrame:
    """Eine CSV als Text; eine erste Zeile ``sep=;`` (Excel-Hinweis der Schuldaten) fällt weg."""
    text = path.read_bytes().decode(encoding)
    if text.startswith("sep="):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    return _strip_bom(
        pl.read_csv(io.BytesIO(text.encode("utf-8")), separator=";", infer_schema=False)
    )


@deal.pre(
    lambda schools, index, ags, *, crs, index_encoding="cp850": is_municipality_key(ags),
    message="acht ASCII-Ziffern",
)
@deal.post(lambda result: result.schema == pl.Schema(SCHOOLS_SCHEMA))
@deal.post(lambda result: sorted_unique(result, "schulnummer"), message="eine Zeile je Schule")
@deal.raises(SchemaError)
def read_schools(
    schools: Path, index: Path, ags: str, *, crs: str, index_encoding: str = "cp850"
) -> pl.DataFrame:
    """Die Schulen einer Gemeinde mit Koordinate und Sozialindexstufe, nach Schulnummer sortiert.

    Die Schuldaten nennen das CRS je Zeile; nennt eine Schule der Gemeinde ein anderes als ``crs``,
    ist das ein ``SchemaError`` und keine stille Umrechnung. ``null`` oder leer heißt „nicht
    angegeben" und gilt als ``crs``. Die Liste des Sozialindex ist in
    ``index_encoding`` gespeichert und nennt Schulen ohne Stufe „ohne"; die werden null.
    """
    frame = _csv_text(schools, "utf-8")
    _require(frame, _SCHOOL_COLUMNS, schools.name)
    own = frame.filter(pl.col("Gemeindeschluessel").str.strip_chars() == ags)
    # ``null`` (und leer) heißt „nicht angegeben", nicht „anders": bei zehn Schulen der Hauptstadt
    # (Seminare, neue Schulen) liegen die Koordinaten im selben Bereich wie die übrigen (2026-11-24).
    named = {str(value) for value in own.get_column("EPSG").str.strip_chars().to_list() if value}
    other = sorted(named - {crs, UNSPECIFIED_CRS})
    if other:
        raise SchemaError(f"{schools.name}: Schulen der Gemeinde {ags} in {other}, erwartet {crs}")
    stufen = _csv_text(index, index_encoding)
    _require(stufen, _INDEX_COLUMNS, index.name)
    stufen = stufen.select(
        pl.col("Schulnummer").str.strip_chars().alias("schulnummer"),
        _integer("Sozialindexstufe").alias("sozialindex"),
    ).unique("schulnummer", keep="first", maintain_order=True)
    return (
        own.select(
            pl.col("Schulnummer").str.strip_chars().alias("schulnummer"),
            pl.col("Schulform").str.strip_chars().alias("schulform"),
            _decimal("UTMRechtswert").alias("x"),
            _decimal("UTMHochwert").alias("y"),
        )
        .join(stufen, on="schulnummer", how="left")
        # Ein Join legt die Folge nicht fest; erst sortieren, dann je Nummer die erste Zeile.
        .sort("schulnummer", "schulform", "x", "y", nulls_last=True)
        .unique("schulnummer", keep="first", maintain_order=True)
    )


# --- je Wahlbezirk ---


def in_period(accidents: pl.DataFrame, start: date, end: date | None) -> pl.DataFrame:
    """Die Unfälle der Monate von ``start`` bis ``end`` einschließlich; ohne Ende bis zum letzten.

    Der Unfallatlas kennt nur Monate: eine Periode vom 13.09.2020 bis zum 14.09.2025 zählt die
    Monate 2020-09 bis 2025-09 (61, wie die Monatsreihe der Seite).
    """
    month = pl.col("jahr") * 100 + pl.col("monat")
    keep = month >= start.year * 100 + start.month
    if end is not None:
        keep = keep & (month <= end.year * 100 + end.month)
    return accidents.filter(keep)


def _per(numerator: pl.Expr, denominator: pl.Expr, factor: float = 1.0) -> pl.Expr:
    """Ein Verhältnis, null ohne Nenner (nicht NaN und nicht unendlich)."""
    return pl.when(denominator > 0).then(numerator / denominator * factor).otherwise(None)


@deal.pre(
    lambda accidents, fuzzy, sharp: (
        has_columns(accidents, POINT, "kategorie", "rad", "fuss")
        and has_columns(fuzzy, POINT, DISTRICT, POINT_SHARE)
        and has_columns(sharp, POINT, DISTRICT, POINT_SHARE)
    )
)
@deal.post(lambda result: sorted_unique(result, DISTRICT))
@deal.ensure(
    lambda accidents, fuzzy, sharp, result: math.isclose(
        float(result.get_column("unfaelle").sum()),
        float(fuzzy.get_column(POINT_SHARE).sum()),
        rel_tol=1e-9,
        abs_tol=1e-9,
    ),
    message="die Unfälle je Wahlbezirk summieren zu den zugeordneten",
)
def accidents_by_district(
    accidents: pl.DataFrame, fuzzy: pl.DataFrame, sharp: pl.DataFrame
) -> pl.DataFrame:
    """Unfälle je Wahlbezirk aus den Anteilen mit Band (``fuzzy``) und ohne (``sharp``).

    ``unfaelle`` und seine Teile (mit Getöteten oder Schwerverletzten, mit Rad- oder
    Fußbeteiligung) summieren die Anteile im Band; ``unfaelle_geteilt`` den Teil davon, der von
    geteilten Unfällen kommt; ``unfaelle_scharf`` die Anteile ohne Band (Punkt in Fläche).
    """
    traits = accidents.select(POINT, "kategorie", "rad", "fuss")
    share = pl.col(POINT_SHARE)
    banded = (
        fuzzy.join(traits, on=POINT, how="left")
        .sort(DISTRICT, POINT)
        .group_by(DISTRICT, maintain_order=True)
        .agg(
            share.sum().alias("unfaelle"),
            share.filter(pl.col("kategorie") <= 2).sum().alias("unfaelle_schwer"),
            share.filter((pl.col("rad") == 1) | (pl.col("fuss") == 1))
            .sum()
            .alias("unfaelle_rad_fuss"),
            share.filter(share < 1.0).sum().alias("unfaelle_geteilt"),
        )
    )
    crisp = (
        sharp.sort(DISTRICT, POINT)
        .group_by(DISTRICT, maintain_order=True)
        .agg(share.sum().alias("unfaelle_scharf"))
    )
    columns = [
        "unfaelle",
        "unfaelle_schwer",
        "unfaelle_rad_fuss",
        "unfaelle_scharf",
        "unfaelle_geteilt",
    ]
    return (
        banded.join(crisp, on=DISTRICT, how="full", coalesce=True)
        .with_columns(pl.col(columns).fill_null(0.0).cast(pl.Float64))
        .select(DISTRICT, *columns)
        .sort(DISTRICT)
    )


@deal.pre(
    lambda cells, shares: (
        has_columns(cells, POINT, "einwohner", "miete")
        and has_columns(shares, POINT, DISTRICT, POINT_SHARE)
    )
)
@deal.post(lambda result: sorted_unique(result, DISTRICT))
def grid_by_district(cells: pl.DataFrame, shares: pl.DataFrame) -> pl.DataFrame:
    """Einwohner und Miete je Wahlbezirk aus den Gitterzellen (Mittelpunkt in Fläche).

    Einwohner summieren die Zellen (eine gesperrte oder negative Zahl zählt als 0, Messdokument
    § 3.1); die Miete ist das Mittel der Zellen mit Wert, gewogen mit ihren Einwohnern, und
    ``miete_abdeckung`` der Anteil der Einwohner in Zellen mit Wert (Frage 22.7: Einwohner statt
    Wohnungen).
    """
    weight = pl.col(POINT_SHARE) * pl.col("einwohner").clip(lower_bound=0).fill_null(0)
    known = pl.col("miete").is_not_null()
    return (
        shares.join(cells.select(POINT, "einwohner", "miete"), on=POINT, how="left")
        .sort(DISTRICT, POINT)
        .with_columns(weight.cast(pl.Float64).alias("_w"))
        .group_by(DISTRICT, maintain_order=True)
        .agg(
            pl.col("_w").sum().alias("einwohner_zensus"),
            (pl.col("_w") * pl.col("miete")).filter(known).sum().alias("_wm"),
            pl.col("_w").filter(known).sum().alias("_wk"),
        )
        .select(
            DISTRICT,
            "einwohner_zensus",
            _per(pl.col("_wm"), pl.col("_wk")).alias("miete_qm"),
            _per(pl.col("_wk"), pl.col("einwohner_zensus")).alias("miete_abdeckung"),
        )
        .sort(DISTRICT)
    )


@deal.pre(
    lambda schools, shares, forms: (
        has_columns(schools, POINT, "schulform", "sozialindex")
        and has_columns(shares, POINT, DISTRICT, POINT_SHARE)
    )
)
@deal.post(lambda result: sorted_unique(result, DISTRICT))
def schools_by_district(
    schools: pl.DataFrame, shares: pl.DataFrame, forms: Sequence[str]
) -> pl.DataFrame:
    """Schulen der Formen ``forms`` je Wahlbezirk und das Mittel ihrer Sozialindexstufe.

    Eine Schule ist kein Gebiet: ihr Einzugsgebiet reicht über Wahlbezirksgrenzen, und bei einer
    Schule je Wahlbezirk ist das Mittel eine Einzelzahl (Messdokument § 3.1).
    """
    kept = schools.filter(pl.col("schulform").is_in(list(forms))).select(POINT, "sozialindex")
    known = pl.col("sozialindex").is_not_null()
    return (
        shares.join(kept, on=POINT, how="inner")
        .sort(DISTRICT, POINT)
        .group_by(DISTRICT, maintain_order=True)
        .agg(
            pl.col(POINT_SHARE).sum().alias("schulen"),
            pl.col(POINT_SHARE).filter(known).sum().alias("schulen_mit_index"),
            (pl.col(POINT_SHARE) * pl.col("sozialindex")).filter(known).sum().alias("_si"),
        )
        .select(
            DISTRICT,
            pl.col("schulen").cast(pl.Float64),
            pl.col("schulen_mit_index").cast(pl.Float64),
            _per(pl.col("_si"), pl.col("schulen_mit_index")).alias("sozialindex_schulen"),
        )
        .sort(DISTRICT)
    )


@deal.pre(
    lambda results, committees, traffic, youth: (
        has_columns(results, DISTRICT, "suchbegriffe", "paper_ids")
        and (committees is None or has_columns(committees, "id", "ausschuss"))
    )
)
@deal.post(lambda result: sorted_unique(result, DISTRICT))
def attention_by_district(
    results: pl.DataFrame,
    committees: pl.DataFrame | None,
    traffic: Sequence[str],
    youth: Sequence[str],
) -> pl.DataFrame:
    """Dokumente mit Treffer je Wahlbezirk und die Teile der Klassen Verkehr und Jugend.

    Ein Dokument „nennt" einen Wahlbezirk, wenn es einen Treffer in dessen Wörterbuch hat
    (``paper_ids``, wie die Trefferquote der Seite). Die Klasse kommt aus dem passenden Ausschuss;
    der Nenner der Anteile sind die Dokumente mit einer Klasse oder der Restklasse, also mit Text
    (``dok_mit_text``). Ohne Klassifikator oder ohne Klassen im Profil sind diese Spalten null.
    """
    terms = results.select(
        DISTRICT, pl.col("suchbegriffe").list.len().cast(pl.Int64).alias("begriffe")
    )
    pairs = (
        results.select(DISTRICT, pl.col("paper_ids").alias("id"))
        .explode("id")
        .drop_nulls("id")
        .unique()
    )
    nothing = pl.lit(None, dtype=pl.Int64)
    if committees is not None:
        pairs = pairs.join(committees.select("id", "ausschuss"), on="id", how="left")
        with_text = pl.col("ausschuss").is_not_null().sum().cast(pl.Int64)
        klass = pl.col("ausschuss")
    else:
        with_text, klass = nothing, pl.lit(None, dtype=pl.String)
    counts = (
        pairs.sort(DISTRICT, "id")
        .group_by(DISTRICT, maintain_order=True)
        .agg(
            pl.len().cast(pl.Int64).alias("dok"),
            with_text.alias("dok_mit_text"),
            (
                klass.is_in(list(traffic)).sum().cast(pl.Int64)
                if traffic and committees is not None
                else nothing
            ).alias("dok_verkehr"),
            (
                klass.is_in(list(youth)).sum().cast(pl.Int64)
                if youth and committees is not None
                else nothing
            ).alias("dok_jugend"),
        )
    )
    return (
        terms.join(counts, on=DISTRICT, how="left")
        .with_columns(pl.col("dok").fill_null(0))
        .with_columns(
            _per(pl.col("dok_verkehr"), pl.col("dok_mit_text")).alias("anteil_verkehr"),
            _per(pl.col("dok_jugend"), pl.col("dok_mit_text")).alias("anteil_jugend"),
        )
        .sort(DISTRICT)
    )


NEED_TABLE_SCHEMA: dict[str, pl.DataType] = {
    DISTRICT: pl.Int64(),
    "stadtbezirk": pl.Int64(),  # der mit den meisten Wahlberechtigten des Wahlbezirks: die Schicht
    "flaeche_km2": pl.Float64(),
    "einwohner_zensus": pl.Float64(),
    "unfaelle": pl.Float64(),
    "unfaelle_schwer": pl.Float64(),
    "unfaelle_rad_fuss": pl.Float64(),
    "unfaelle_scharf": pl.Float64(),
    "unfaelle_geteilt": pl.Float64(),
    "unfaelle_je_1000": pl.Float64(),
    "unfaelle_scharf_je_1000": pl.Float64(),
    "unfaelle_je_km2": pl.Float64(),
    "miete_qm": pl.Float64(),
    "miete_abdeckung": pl.Float64(),
    "schulen": pl.Float64(),
    "schulen_mit_index": pl.Float64(),
    "sozialindex_schulen": pl.Float64(),
    "begriffe": pl.Int64(),
    "dok": pl.Int64(),
    "dok_mit_text": pl.Int64(),
    "dok_verkehr": pl.Int64(),
    "dok_jugend": pl.Int64(),
    "anteil_verkehr": pl.Float64(),
    "anteil_jugend": pl.Float64(),
    "dok_je_1000_ew": pl.Float64(),
    "dok_verkehr_je_1000_ew": pl.Float64(),
}
_COUNTS = (
    "einwohner_zensus",
    "unfaelle",
    "unfaelle_schwer",
    "unfaelle_rad_fuss",
    "unfaelle_scharf",
    "unfaelle_geteilt",
    "schulen",
    "schulen_mit_index",
)


def _no_nan(result: pl.DataFrame) -> bool:
    floats = [c for c, t in result.schema.items() if t == pl.Float64]
    return not any(bool(result.get_column(c).is_nan().any()) for c in floats)


@deal.pre(
    lambda base, accidents, grid, schools, attention: (
        has_columns(base, DISTRICT, "flaeche_km2", "stadtbezirk") and sorted_unique(base, DISTRICT)
    )
)
@deal.post(lambda result: result.schema == pl.Schema(NEED_TABLE_SCHEMA))
@deal.post(lambda result: sorted_unique(result, DISTRICT), message="eine Zeile je Wahlbezirk")
@deal.post(_no_nan, message="kein NaN: ein Verhältnis ohne Nenner ist null")
@deal.ensure(
    lambda base, accidents, grid, schools, attention, result: result.height == base.height,
    message="genau die Wahlbezirke der Flächen",
)
def need_table(
    base: pl.DataFrame,
    accidents: pl.DataFrame,
    grid: pl.DataFrame,
    schools: pl.DataFrame,
    attention: pl.DataFrame,
) -> pl.DataFrame:
    """``wahlbezirke_bedarf.parquet``: Bedarf und Aufmerksamkeit, eine Zeile je Wahlbezirk.

    ``base`` nennt die Wahlbezirke mit Fläche und Stadtbezirk; die übrigen Frames sind die
    Aggregate oben. Ein Wahlbezirk ohne Unfall, Zelle oder Schule hat dort 0; ein Verhältnis ohne
    Nenner (keine Einwohner, kein Dokument mit Text) ist null, nicht NaN.
    """
    frame = base.select(DISTRICT, "stadtbezirk", "flaeche_km2")
    for part in (accidents, grid, schools, attention):
        frame = frame.join(part, on=DISTRICT, how="left")
    people = pl.col("einwohner_zensus")
    return (
        frame.sort(DISTRICT)
        .with_columns(
            pl.col(*_COUNTS).cast(pl.Float64).fill_null(0.0),
            pl.col("begriffe", "dok").cast(pl.Int64).fill_null(0),
        )
        .with_columns(
            _per(pl.col("unfaelle"), people, 1000.0).alias("unfaelle_je_1000"),
            _per(pl.col("unfaelle_scharf"), people, 1000.0).alias("unfaelle_scharf_je_1000"),
            _per(pl.col("unfaelle"), pl.col("flaeche_km2")).alias("unfaelle_je_km2"),
            _per(pl.col("dok"), people, 1000.0).alias("dok_je_1000_ew"),
            _per(pl.col("dok_verkehr"), people, 1000.0).alias("dok_verkehr_je_1000_ew"),
        )
        .select([pl.col(name).cast(dtype) for name, dtype in NEED_TABLE_SCHEMA.items()])
    )
