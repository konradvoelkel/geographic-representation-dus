"""Winzige Archive in der Form der Bedarfsquellen von Vorhaben 22, für Tests ohne Netz.

Die Kopfzeilen, Mitgliedsnamen, Trennzeichen, BOMs und Kodierungen sind die der echten Dateien,
abgelesen am 2026-11-24 an den Archiven unter ``fremddaten/opendata/`` (Quellen und Prüfsummen dort
im README): drei Namensformen der Unfallatlas-Jahrgänge (``csv/…_LinRef.csv`` ohne BOM,
``…_EPSG25832_CSV/Unfallorte_2021_LinRef.txt`` mit BOM, ``csv/…_LR_BasisDLM.csv`` mit BOM), das
100-m-Gitter des Zensus mit Dezimalkomma und werterläuterndem Zeichen, die Schuldaten mit ihrer
Zeile ``sep=;`` und der Sozialindex in Codepage 850 mit „ohne". Die Zeilen sind erfunden; ihre
Koordinaten gibt der Test vor.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Sequence
from pathlib import Path

# (Jahr, Mitglied, BOM, Kopf); die Zeile darunter füllt ``accident_row`` in derselben Spaltenfolge.
ACCIDENT_FORMS = (
    (
        2020,
        "csv/Unfallorte2020_LinRef.csv",
        False,
        "OBJECTID;UIDENTSTLAE;ULAND;UREGBEZ;UKREIS;UGEMEINDE;UJAHR;UMONAT;USTUNDE;UWOCHENTAG;"
        "UKATEGORIE;UART;UTYP1;ULICHTVERH;IstRad;IstPKW;IstFuss;IstKrad;IstGkfz;IstSonstige;"
        "LINREFX;LINREFY;XGCSWGS84;YGCSWGS84;STRZUSTAND",
    ),
    (
        2021,
        "Unfallorte2021_EPSG25832_CSV/Unfallorte_2021_LinRef.txt",
        True,
        "OID_;ULAND;UREGBEZ;UKREIS;UGEMEINDE;UJAHR;UMONAT;USTUNDE;UWOCHENTAG;UKATEGORIE;UART;"
        "UTYP1;IstRad;IstPKW;IstFuss;IstKrad;IstSonstige;ULICHTVERH;IstGkfz;LINREFX;LINREFY;"
        "XGCSWGS84;YGCSWGS84;UIDENTSTLAE;IstStrassenzustand",
    ),
    (
        2025,
        "csv/Unfallorte_2025_LR_BasisDLM.csv",
        True,
        "UIDENTSTLAE;ULAND;UREGBEZ;UKREIS;UGEMEINDE;UJAHR;UMONAT;USTUNDE;UWOCHENTAG;UKATEGORIE;"
        "UART;UTYP1;ULICHTVERH;IstStrassenzustand;IstRad;IstPKW;IstFuss;IstKrad;IstGkfz;"
        "IstSonstige;LINREFX;LINREFY;XGCSWGS84;YGCSWGS84;PLST",
    ),
)
SCHEMA_INI = "[schema]\r\nColNameHeader=True\r\n"


def _comma(value: float) -> str:
    return f"{value:.6f}".replace(".", ",")


def accident_row(
    header: str,
    *,
    ags: str,
    year: int,
    month: int,
    category: int,
    bike: int,
    foot: int,
    x: float | None,
    y: float | None,
    leading_zero: bool = True,
) -> str:
    """Eine Zeile zum Kopf ``header``; die Schlüssel mit oder ohne führende Null wie im Jahrgang.

    ``None`` als Koordinate lässt das Feld leer.
    """
    land = ags[:2] if leading_zero else str(int(ags[:2]))
    values = {
        "ULAND": land,
        "UREGBEZ": ags[2],
        "UKREIS": ags[3:5],
        "UGEMEINDE": ags[5:],
        "UJAHR": str(year),
        "UMONAT": f"{month:02d}",
        "UKATEGORIE": str(category),
        "IstRad": str(bike),
        "IstFuss": str(foot),
        "LINREFX": "" if x is None else _comma(x),
        "LINREFY": "" if y is None else _comma(y),
    }
    return ";".join(values.get(column, "0") for column in header.split(";"))


def write_accident_archive(
    path: Path, form: int, rows: Sequence[dict[str, object]], *, ags_other: str = "05911000"
) -> Path:
    """Ein Jahresarchiv in der Form ``ACCIDENT_FORMS[form]``; dazu eine Zeile einer anderen Gemeinde."""
    year, member, bom, header = ACCIDENT_FORMS[form]
    lines = [accident_row(header, year=year, **row) for row in rows]  # type: ignore[arg-type]
    lines.append(
        accident_row(
            header, ags=ags_other, year=year, month=1, category=3, bike=0, foot=0, x=1.0, y=2.0
        )
    )
    text = ("﻿" if bom else "") + header + "\r\n" + "\r\n".join(lines) + "\r\n"
    folder = member.rsplit("/", 1)[0] + "/" if "/" in member else ""
    with zipfile.ZipFile(path, "w") as archive:
        if folder:
            archive.writestr(folder, b"")
            archive.writestr(f"{folder}schema.ini", SCHEMA_INI)
        archive.writestr(member, text.encode("utf-8"))
    return path


GRID_POPULATION_MEMBER = "Zensus2022_Bevoelkerungszahl_100m-Gitter.csv"
GRID_RENT_MEMBER = "Zensus2022_Durchschn_Nettokaltmiete_100m-Gitter.csv"


def write_grid_archives(
    folder: Path, cells: Sequence[tuple[int, int, str, str, str]]
) -> tuple[Path, Path]:
    """Die zwei Gitterarchive aus Zellen (x, y, Einwohner, Miete, Zeichen); leere Miete fehlt dort.

    Wie in der Quelle: ein Zip mit mehreren Gittern und einer Beschreibung, das 100-m-Gitter mit
    ``\\n`` als Zeilenende, die Miete mit Dezimalkomma.
    """
    population = "GITTER_ID_100m;x_mp_100m;y_mp_100m;Einwohner\n" + "".join(
        f"CRS3035RES100mN{y - 50}E{x - 50};{x};{y};{people}\n" for x, y, people, _, _ in cells
    )
    rent = (
        "GITTER_ID_100m;x_mp_100m;y_mp_100m;durchschnMieteQM;werterlaeuternde_Zeichen\n"
        + "".join(
            f"CRS3035RES100mN{y - 50}E{x - 50};{x};{y};{value};{sign}\n"
            for x, y, _, value, sign in cells
            if value
        )
    )
    paths = (
        folder / "Zensus2022_Bevoelkerungszahl.zip",
        folder / "Zensus2022_Durchschn_Nettokaltmiete.zip",
    )
    for path, member, text in zip(
        paths, (GRID_POPULATION_MEMBER, GRID_RENT_MEMBER), (population, rent), strict=True
    ):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("Datensatzbeschreibung.xlsx", b"PK")
            archive.writestr(member, text.encode("utf-8"))
            archive.writestr(member.replace("100m", "1km"), b"GITTER_ID_1km;x;y\n")
    return paths


SCHOOLS_HEADER = (
    "Schulnummer;Schulform;Schulbezeichnung_1;Schulbezeichnung_2;Schulbezeichnung_3;"
    "Kurzbezeichnung;Bezirksregierung;PLZ;Ort;Strasse;Telefonvorwahl;Telefon;Faxvorwahl;Fax;"
    "E-Mail;Homepage;Rechtsform;Traegernummer;Gemeindeschluessel;Schulbetriebsschluessel;"
    "Schulbetriebsdatum;EPSG;UTMRechtswert;UTMHochwert;"
)


def write_school_files(
    folder: Path, schools: Sequence[tuple[str, str, str, int | None, int | None, str]]
) -> tuple[Path, Path]:
    """Schuldaten (Nummer, Form, Gemeinde, x, y, Stufe) und die Liste des Sozialindex in cp850.

    ``None`` als Koordinate lässt das Feld leer.
    """
    rows = []
    for number, form, ags, x, y, _ in schools:
        values = [
            number,
            form,
            "Schule",
            "",
            "",
            "Kurz",
            "1",
            "40000",
            "Ort",
            "Weg 1",
            "",
            "",
            "",
            "",
        ]
        values += ["", "", "1", "100", ags, "1", "01.08.1970", "EPSG:25832"]
        values += ["" if x is None else str(x), "" if y is None else str(y)]
        rows.append(";".join(f'"{v}"' for v in values))
    schools_csv = folder / "schuldaten.csv"
    schools_csv.write_bytes(
        ("sep=;\n" + SCHOOLS_HEADER + "\n" + "\n".join(rows) + "\n").encode("utf-8")
    )
    index = (
        "Schulnummer;Kurzbezeichnung;Bezirksregierung;Kreis;Gemeinde;Sozialindexstufe\r\n"
        + "".join(
            f"{number};Grünstadt, GG Großstraße;BR Köln;Stadt;Grünstadt;{stufe}\r\n"
            for number, _, _, _, _, stufe in schools
        )
    )
    index_csv = folder / "schulliste_sj_25_26_open_data.csv"
    index_csv.write_bytes(index.encode("cp850"))
    return schools_csv, index_csv


def zipped(path: Path) -> bytes:
    """Die Bytes einer Datei, wie ein Server sie ausliefert."""
    return path.read_bytes()


def broken_zip() -> bytes:
    """Eine Antwort, die kein Zip ist (eine Fehlerseite mit Status 200)."""
    buffer = io.BytesIO(b"<html>Wartung</html>")
    return buffer.getvalue()
