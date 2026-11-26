"""Rechnet die Zahlen von `22-bedarf.md` nach (Vorhaben 22 „Bedarf und Aufmerksamkeit", Stufe 1).

    uv run python -I docs/plans/22-bedarf-messung.py [--teil bestand|bedarf|aufmerksamkeit|hypothesen|explorativ|alle]

Liest, was `georep run` für das Profil `duesseldorf` schreibt (Stimmbezirke aus `interim/`,
`processed/wahlbezirke_auswertung.parquet`, `papers_ausschuss.parquet`,
`wahlbezirke_kontext.parquet`, `wahlbezirke_crosswalk.parquet`; Pfade aus `georep paths`), dazu
Fremddaten, die am 2026-11-23 von der Quelle geladen wurden und **nicht** im Repo liegen:
`$GEOREP_FREMDDATEN` (Standard `/media/konrad/xtraspace/georep/fremddaten/opendata`), je Quelle ein
Unterordner mit README (Quelle, Abrufdatum, Größe, SHA-256, Lizenz). Das Skript prüft die
Prüfsummen, bevor es etwas liest, und führt nichts aus, was es geladen hat. Die Auszüge für
Düsseldorf (Unfälle, Zensus-Gitter, Gebäudereferenzen) legt es beim ersten Lauf unter
`$GEOREP_MESSDATEN/22-bedarf/` ab und liest danach nur sie.

Die Teile: `bestand` (Dateien und Prüfsummen, Unfälle Mönchengladbach), `bedarf` (Bedarf je
Wahlbezirk mit Abdeckung und Unsicherheit), `aufmerksamkeit` (Dokumente je Wahlbezirk und Klasse),
`hypothesen` (die drei vorab festgelegten Tests aus § 8, festgelegt in Commit 67f7250, bevor dieser
Teil zum ersten Mal lief), `explorativ` (alles andere, darunter Moran's I und die Rechnung innerhalb
der Stadtbezirke, nachgetragen nach dem ersten Lauf). Laufzeit rund eine Minute mehr beim ersten Lauf
(Auszüge aus den bundesweiten Archiven), danach 10 bis 40 s je nach Last; Polars auf vier Threads.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import math
import os
import subprocess
import sys
import zipfile
from pathlib import Path

os.environ.setdefault("POLARS_MAX_THREADS", "4")
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
import shapely  # noqa: E402
from scipy import stats  # noqa: E402

from georep.geo import read_canonical_precincts, transformer  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FREMD = Path(
    os.environ.get("GEOREP_FREMDDATEN", "/media/konrad/xtraspace/georep/fremddaten/opendata")
)
MESSDATEN = Path(os.environ.get("GEOREP_MESSDATEN", "/media/konrad/xtraspace/georep/messdaten"))
AUSZUG = MESSDATEN / "22-bedarf"
PROFIL = "duesseldorf"
SEED = 22
PERMUTATIONEN = 10_000
BOOTSTRAP = 2_000
ALPHA = 0.05
WORKING_CRS = "EPSG:25832"  # defaults.toml, geo.working_crs
ZENSUS_CRS = "EPSG:3035"  # Gitter-ID CRS3035RES100m…
# Hauptperiode 2020-09-14 bis 2025-09-12 (docs/plans/14-vorgaenge.md, § 2); Unfälle haben nur Monate,
# also 2020-09 bis 2025-09 einschließlich, 61 Monate wie die Monatsreihe der Seite.
PERIODE = ((2020, 9), (2025, 9))
# Amtlicher Gemeindeschlüssel Düsseldorf 05 1 11 000 (Land, Regierungsbezirk, Kreis, Gemeinde).
AGS = ("05", "1", "11", "000")
AGS_MG = ("05", "1", "16", "000")  # Mönchengladbach, nur für den Bestand
RANDBAND_M = 20.0  # Unfälle so nah an einer Wahlbezirksgrenze gelten als unsicher zugeordnet
LAERM_TAG_DB = 65  # Schwelle der Lärmaktionsplanung NRW (L_DEN 65 dB(A), L_Night 55 dB(A))
LAERM_NACHT_DB = 55

# Dateien unter FREMD: (Unterordner, Datei) -> (Bytes, SHA-256). Aus dem Ladeprotokoll vom 2026-11-23.
DATEIEN: dict[tuple[str, str], tuple[int, str]] = {
    ("unfallatlas", "DSB_Unfallatlas.pdf"): (
        405394,
        "3afe9d303e8c508bd5ff6f0be313eda38abeaaedf889ee5c0c8e468e3011c519",
    ),
    ("unfallatlas", "Unfallorte2020_EPSG25832_CSV.zip"): (
        12612904,
        "cc7133694fbe144d3e26fc724bea1e266a4f933ba85dcc410ac94aa1205e8f88",
    ),
    ("unfallatlas", "Unfallorte2021_EPSG25832_CSV.zip"): (
        12496020,
        "7133b8a0bb34e6b4b86db8b1bb3f5df801898b9dc4826bd94e46b4fccffde879",
    ),
    ("unfallatlas", "Unfallorte2022_EPSG25832_CSV.zip"): (
        13303418,
        "7f47e432db4d570a168152264178316974c87c51411338dcb95d0f664c298219",
    ),
    ("unfallatlas", "Unfallorte2023_EPSG25832_CSV.zip"): (
        12702950,
        "e8c7dccf343284f42c2bf3b8c5a23d62fe440f557082b17b7c0c788cc3b5bc65",
    ),
    ("unfallatlas", "Unfallorte2024_EPSG25832_CSV.zip"): (
        12681950,
        "4a321fbde7cac6344a6ee1f8926ceb2a585b2adb3bcf301ad4fb85bb9abb4813",
    ),
    ("unfallatlas", "Unfallorte2025_EPSG25832_CSV.zip"): (
        12598619,
        "f4b11dba79abaa8d14dd780a5e7f4e504454946f784d2236ef79607e2ec58dac",
    ),
    ("zensus2022", "Zensus2022_Bevoelkerungszahl.zip"): (
        18501524,
        "1a8428d31eab264c8717bfdcbf40fbd66c217edb2e2a98d0e67741bd8a1a941a",
    ),
    ("zensus2022", "Zensus2022_Durchschn_Nettokaltmiete.zip"): (
        9379249,
        "8b8f2f548e88fecb0d5aa47492fd9b64d683f9a3e4da9d89d0d0a172462482fd",
    ),
    ("duesseldorf-verkehrslaerm", "Strassenverkehrslaerm_Gebaeudedatei_2018.csv"): (
        3433600,
        "6c7674ae4ccf20a7222aaf38b11e058f1949b30de40884a5b35bb7bfb2ce1ab9",
    ),
    ("duesseldorf-kitas", "Tageseinrichtungen_fuer_Kinder.csv"): (
        57590,
        "6c018a8ce2c3125de0145e0cd4213e8c8583ac980971fc84cc6ce12eb53d639f",
    ),
    ("nrw-gebaeudereferenzen", "gebref_EPSG25832_ASCII.zip"): (
        90258596,
        "ff62bfc23a798f67a2371fa241ceec716a2275297a2706f88e94912a28043fce",
    ),
    ("nrw-schuldaten", "schuldaten.csv"): (
        1790359,
        "ecdf6f746e42c317d158aab81f66327d97d4ed238e4900d3bd669fb14f6a051f",
    ),
    ("nrw-schulsozialindex", "schulliste_sj_25_26_open_data.csv"): (
        311017,
        "49a25e0cf32d47bc71958cb3c914236b4319bec9703091324b395674db4ae32d",
    ),
}


# --- Hilfen ----------------------------------------------------------------------------------------
def fmt(x: float, nachkomma: int = 3) -> str:
    """Deutsch: Komma als Dezimaltrenner, schmales Leerzeichen als Tausendertrenner (wie die Seite)."""
    s = f"{x:,.{nachkomma}f}"
    return s.replace(",", " ").replace(".", ",")


def paths(profile: str) -> dict[str, str]:
    exe = Path(sys.executable).parent / "georep"
    out = subprocess.run(
        [str(exe), "--profile", profile, "paths"], check=True, capture_output=True, text=True
    ).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def datei(ordner: str, name: str) -> Path:
    return FREMD / ordner / name


def im_zeitraum(jahr: pl.Expr, monat: pl.Expr) -> pl.Expr:
    (j0, m0), (j1, m1) = PERIODE
    schluessel = jahr * 100 + monat
    return (schluessel >= j0 * 100 + m0) & (schluessel <= j1 * 100 + m1)


class Stimmbezirke:
    """Die 306 Stimmbezirke mit Wahlbezirk, im Arbeits-CRS, als STRtree für Punkt-in-Fläche."""

    def __init__(self, root: Path) -> None:
        self.precincts = read_canonical_precincts(
            root / "interim" / "stimmbezirke.geojson", WORKING_CRS
        )
        self.geoms = [p.geometry for p in self.precincts]
        self.tree = shapely.STRtree(self.geoms)
        self.wb = np.array([p.district_id for p in self.precincts])
        # Grenzen zwischen Wahlbezirken: Vereinigung je Wahlbezirk, dann deren Ränder.
        unions = [
            shapely.union_all([g for g, w in zip(self.geoms, self.wb, strict=True) if w == d])
            for d in sorted(set(self.wb))
        ]
        self.grenzen = shapely.union_all([u.boundary for u in unions])
        self.stadt = shapely.union_all(unions)
        self.flaeche_km2 = {
            d: u.area / 1e6 for d, u in zip(sorted(set(self.wb)), unions, strict=True)
        }
        # Nachbarschaft (gemeinsame Grenze, nicht nur ein Punkt) für Moran's I in `explorativ`.
        self.nachbarn = np.array(
            [
                [a is not b and a.buffer(1.0).intersection(b).length > 50.0 for b in unions]
                for a in unions
            ],
            dtype=float,
        )

    def wahlbezirk(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Wahlbezirk je Punkt (Arbeits-CRS), 0 außerhalb aller Stimmbezirke."""
        punkte = shapely.points(x, y)
        idx_punkt, idx_flaeche = self.tree.query(punkte, predicate="within")
        out = np.zeros(len(punkte), dtype=np.int64)
        out[idx_punkt] = self.wb[idx_flaeche]
        return out

    def am_rand(self, x: np.ndarray, y: np.ndarray, band: float) -> np.ndarray:
        punkte = shapely.points(x, y)
        return np.asarray(shapely.dwithin(punkte, self.grenzen, band))

    def anteile(self, x: np.ndarray, y: np.ndarray, band: float) -> pl.DataFrame:
        """Unscharfe Zuordnung: jeder Punkt zu gleichen Teilen an alle Wahlbezirke im Band.

        Grenzen der Wahlbezirke laufen oft auf Straßenmitten, und der Unfallatlas legt einen
        Unfall auf die Straßenachse: welcher Seite er zufällt, ist dann Zufall der Digitalisierung.
        Ausgabe: punkt, wahlkreis_id, anteil (summiert je Punkt zu 1); Punkte ohne Wahlbezirk im
        Band fehlen.
        """
        punkte = shapely.points(x, y)
        idx_punkt, idx_flaeche = self.tree.query(punkte, predicate="dwithin", distance=band)
        paare = (
            pl.DataFrame({"punkt": idx_punkt, "wahlkreis_id": self.wb[idx_flaeche]})
            .unique()
            .with_columns((1.0 / pl.len().over("punkt")).alias("anteil"))
            .sort("punkt", "wahlkreis_id")
        )
        return paare


def zahl(spalte: str) -> pl.Expr:
    return pl.col(spalte).str.replace(",", ".").cast(pl.Float64)


# --- Bestand -----------------------------------------------------------------------------------------
def bestand() -> None:
    print("## Bestand: Fremddaten unter", FREMD)
    fehler = 0
    for (ordner, name), (groesse, summe) in DATEIEN.items():
        p = datei(ordner, name)
        if not p.exists():
            print(f"  FEHLT  {ordner}/{name}")
            fehler += 1
            continue
        ok = p.stat().st_size == groesse and sha256(p) == summe
        fehler += 0 if ok else 1
        print(f"  {'ok    ' if ok else 'ANDERS'} {ordner}/{name} {fmt(groesse, 0)} Bytes")
    if fehler:
        sys.exit(f"{fehler} Dateien fehlen oder weichen ab; README unter {FREMD} lesen")
    # Mönchengladbach, kurz: dieselben bundesweiten Quellen tragen auch die zweite Stadt.
    mg = unfaelle_auszug(AGS_MG, "moenchengladbach")
    print(
        "  Mönchengladbach (05 1 16 000), Unfälle mit Personenschaden je Jahr: "
        f"{mg.group_by('jahr').len().sort('jahr').rows()}"
    )


# --- Auszüge -------------------------------------------------------------------------------------------
def unfaelle_auszug(
    ags: tuple[str, str, str, str] = AGS, stadt: str = "duesseldorf"
) -> pl.DataFrame:
    """Unfälle mit Personenschaden einer Gemeinde aus den bundesweiten Jahresdateien."""
    ziel = AUSZUG / f"unfaelle_{stadt}.parquet"
    if ziel.exists():
        return pl.read_parquet(ziel)
    teile = []
    for jahr in range(PERIODE[0][0], PERIODE[1][0] + 1):
        with zipfile.ZipFile(datei("unfallatlas", f"Unfallorte{jahr}_EPSG25832_CSV.zip")) as z:
            # Die Jahrgänge heißen verschieden (csv/…_LinRef.csv, …/Unfallorte_2021_LinRef.txt,
            # …_LR_BasisDLM.csv): die größte Datei neben schema.ini ist die Tabelle.
            name = max(
                (i for i in z.infolist() if not i.filename.endswith(("/", "schema.ini"))),
                key=lambda i: i.file_size,
            ).filename
            roh = pl.read_csv(io.BytesIO(z.read(name)), separator=";", infer_schema=False)
        roh = roh.rename({c: c.lstrip("\ufeff") for c in roh.columns})
        gemeinde = [
            pl.col(c).cast(pl.Int64) == int(v)
            for c, v in zip(["ULAND", "UREGBEZ", "UKREIS", "UGEMEINDE"], ags, strict=True)
        ]
        teil = roh.filter(*gemeinde).select(
            pl.col("UJAHR").cast(pl.Int64).alias("jahr"),
            pl.col("UMONAT").cast(pl.Int64).alias("monat"),
            pl.col("UKATEGORIE").cast(pl.Int64).alias("kategorie"),
            pl.col("IstRad").cast(pl.Int64).alias("rad"),
            pl.col("IstFuss").cast(pl.Int64).alias("fuss"),
            zahl("LINREFX").alias("x"),
            zahl("LINREFY").alias("y"),
        )
        teile.append(teil)
    df = pl.concat(teile).sort("jahr", "monat", "x", "y")
    AUSZUG.mkdir(parents=True, exist_ok=True)
    df.write_parquet(ziel)
    return df


def zensus_auszug(stadt: shapely.Geometry) -> pl.DataFrame:
    """100-m-Zellen des Zensus 2022 im Rechteck um die Stadt: Einwohner und Nettokaltmiete je m²."""
    ziel = AUSZUG / "zensus2022_duesseldorf.parquet"
    if ziel.exists():
        return pl.read_parquet(ziel)
    to3035 = transformer(WORKING_CRS, ZENSUS_CRS)
    minx, miny, maxx, maxy = stadt.bounds
    xs, ys = to3035.transform([minx, maxx, minx, maxx], [miny, miny, maxy, maxy])
    box = (min(xs) - 200, min(ys) - 200, max(xs) + 200, max(ys) + 200)

    def lies(zipname: str, csvname: str) -> pl.DataFrame:
        with zipfile.ZipFile(datei("zensus2022", zipname)) as z:
            roh = pl.read_csv(io.BytesIO(z.read(csvname)), separator=";", infer_schema=False)
        return roh.with_columns(
            pl.col("x_mp_100m").cast(pl.Int64), pl.col("y_mp_100m").cast(pl.Int64)
        ).filter(
            pl.col("x_mp_100m").is_between(box[0], box[2]),
            pl.col("y_mp_100m").is_between(box[1], box[3]),
        )

    ew = lies("Zensus2022_Bevoelkerungszahl.zip", "Zensus2022_Bevoelkerungszahl_100m-Gitter.csv")
    miete = lies(
        "Zensus2022_Durchschn_Nettokaltmiete.zip",
        "Zensus2022_Durchschn_Nettokaltmiete_100m-Gitter.csv",
    )
    df = (
        ew.select("GITTER_ID_100m", "x_mp_100m", "y_mp_100m", pl.col("Einwohner").alias("ew_roh"))
        .join(
            miete.select(
                "GITTER_ID_100m",
                pl.col("durchschnMieteQM").alias("miete_roh"),
                pl.col("werterlaeuternde_Zeichen").alias("miete_zeichen"),
            ),
            on="GITTER_ID_100m",
            how="full",
            coalesce=True,
        )
        .sort("GITTER_ID_100m")
    )
    AUSZUG.mkdir(parents=True, exist_ok=True)
    df.write_parquet(ziel)
    return df


GEBREF_SPALTEN = [
    "nba", "oid", "qua", "land", "land_name", "rbz", "rbz_name", "krs", "krs_name", "gmd",
    "gmd_name", "ott", "ott_name", "sss", "stn", "hnr", "adz", "zone", "east", "north", "datum",
]  # fmt: skip


def gebref_auszug() -> pl.DataFrame:
    """Gebäudereferenzen NRW (Hauskoordinaten) der Stadt: Straßenschlüssel, Hausnummer, Punkt."""
    ziel = AUSZUG / "gebref_duesseldorf.parquet"
    if ziel.exists():
        return pl.read_parquet(ziel)
    with zipfile.ZipFile(datei("nrw-gebaeudereferenzen", "gebref_EPSG25832_ASCII.zip")) as z:
        roh = pl.read_csv(
            io.BytesIO(z.read("gebref.txt")),
            separator=";",
            has_header=False,
            new_columns=GEBREF_SPALTEN,
            infer_schema=False,
            quote_char=None,
        )
    df = (
        roh.filter(
            pl.col("land") == AGS[0],
            pl.col("rbz") == AGS[1],
            pl.col("krs") == AGS[2],
            pl.col("gmd") == AGS[3],
        )
        .select(
            pl.col("sss").cast(pl.Int64).alias("strasse"),
            "stn",
            pl.col("hnr").cast(pl.Int64, strict=False).alias("hnr"),
            pl.col("adz").fill_null("").str.to_lowercase().alias("adz"),
            pl.col("east").cast(pl.Float64).alias("x"),
            pl.col("north").cast(pl.Float64).alias("y"),
        )
        .sort("strasse", "hnr", "adz", "x", "y")
    )
    AUSZUG.mkdir(parents=True, exist_ok=True)
    df.write_parquet(ziel)
    return df


# --- Bedarf je Wahlbezirk ------------------------------------------------------------------------------
def bedarf(root: Path, sb: Stimmbezirke) -> pl.DataFrame:
    print("\n## Bedarf je Wahlbezirk")
    wbs = sorted(set(sb.wb))
    basis = pl.DataFrame({"wahlkreis_id": wbs}, schema={"wahlkreis_id": pl.Int64})
    proc = root / "processed"
    auswertung = pl.read_parquet(
        proc / "wahlbezirke_auswertung.parquet",
        columns=["wahlkreis_id", "Wahlberechtigte_insgesamt", "wahlbeteiligung", "trefferquote"],
    )

    # Zensus 2022: Einwohner und Miete über den Mittelpunkt jeder 100-m-Zelle.
    z = zensus_auszug(sb.stadt)
    to_work = transformer(ZENSUS_CRS, WORKING_CRS)
    zx, zy = to_work.transform(z["x_mp_100m"].to_numpy(), z["y_mp_100m"].to_numpy())
    z = z.with_columns(pl.Series("wahlkreis_id", sb.wahlbezirk(np.asarray(zx), np.asarray(zy))))
    ew_neg = z.filter(pl.col("ew_roh").cast(pl.Int64, strict=False) < 0).height
    z = z.with_columns(
        pl.col("ew_roh").cast(pl.Int64, strict=False).clip(lower_bound=0).fill_null(0).alias("ew"),
        pl.col("miete_roh").str.replace(",", ".").cast(pl.Float64, strict=False).alias("miete"),
    )
    innen = z.filter(pl.col("wahlkreis_id") > 0)
    print(
        f"  Zensus 2022: {fmt(z.height, 0)} Zellen im Rechteck, {fmt(innen.height, 0)} mit Mittelpunkt in "
        f"einem Stimmbezirk; Einwohner in der Stadt {fmt(innen['ew'].sum(), 0)}; negative Werte "
        f"(Geheimhaltung) {ew_neg}; Zellen mit Miete {fmt(innen['miete'].is_not_null().sum(), 0)}, "
        f"Zeichen {innen['miete_zeichen'].drop_nulls().value_counts().sort('miete_zeichen').rows()}"
    )
    zensus = (
        innen.group_by("wahlkreis_id")
        .agg(
            pl.col("ew").sum().alias("einwohner_zensus"),
            # Miete: Mittel der Zellen mit Wert, gewogen mit ihren Einwohnern (Wohnungen fehlen
            # im Gitter); Abdeckung = Anteil der Einwohner in Zellen mit Wert.
            (
                (pl.col("miete") * pl.col("ew")).sum()
                / pl.col("ew").filter(pl.col("miete").is_not_null()).sum()
            ).alias("miete_qm"),
            (pl.col("ew").filter(pl.col("miete").is_not_null()).sum() / pl.col("ew").sum()).alias(
                "miete_abdeckung"
            ),
        )
        .sort("wahlkreis_id")
    )

    # Quartiersatlas 2024 (Stand 31.12.2021): die Variablen je Wahlbezirk aus dem Schritt context,
    # dazu die Einwohner 2021 über den Crosswalk zurückgerechnet (Anteil des Sozialraums am
    # Wahlbezirk aus Wahlberechtigten), als Gegenprobe zum Zensus.
    kontext = pl.read_parquet(proc / "wahlbezirke_kontext.parquet").select(
        "wahlkreis_id", "hb_score", "anteil_u18", "anteil_65plus", "mindestsicherung", "fluktuation"
    )
    cw = pl.read_parquet(proc / "wahlbezirke_crosswalk.parquet")
    qa = pl.read_csv(
        root / "external" / "quartiersatlas_2024.csv",
        separator=";",
        infer_schema=False,
        encoding="utf8",
    ).select(
        pl.col("SRG_2021_Nr").alias("einheit"),
        pl.col("Bevoelkerung_abs").cast(pl.Int64, strict=False).alias("bev"),
        pl.col("u6_abs").cast(pl.Int64, strict=False).alias("u6"),
    )
    paar = (
        cw.join(auswertung.select("wahlkreis_id", "Wahlberechtigte_insgesamt"), on="wahlkreis_id")
        .with_columns((pl.col("gewicht") * pl.col("Wahlberechtigte_insgesamt")).alias("wb_paar"))
        .with_columns(
            (pl.col("wb_paar") / pl.col("wb_paar").sum().over("einheit")).alias("anteil_sr")
        )
        .join(qa, on="einheit", how="left")
        .sort("wahlkreis_id", "einheit")
    )
    qa_ew = paar.group_by("wahlkreis_id").agg(
        (pl.col("anteil_sr") * pl.col("bev")).sum().alias("einwohner_qa2021"),
        (pl.col("anteil_sr") * pl.col("u6")).sum().alias("u6_qa2021"),
    )

    # Unfälle mit Personenschaden, 2020-09 bis 2025-09, Punkt-in-Fläche.
    u = unfaelle_auszug()
    jahre = u.group_by("jahr").len().sort("jahr").rows()
    u = u.filter(im_zeitraum(pl.col("jahr"), pl.col("monat")))
    ux, uy = u["x"].to_numpy(), u["y"].to_numpy()
    u = u.with_columns(
        pl.Series("wahlkreis_id", sb.wahlbezirk(ux, uy)),
        pl.Series("am_rand", sb.am_rand(ux, uy, RANDBAND_M)),
    )
    aussen = u.filter(pl.col("wahlkreis_id") == 0).height
    rand = u.filter(pl.col("am_rand")).height
    print(
        f"  Unfälle mit Personenschaden in der Stadt je Jahr (ganze Jahre): {jahre}; "
        f"im Zeitraum {PERIODE}: {fmt(u.height, 0)}, außerhalb aller Stimmbezirke {aussen}, "
        f"näher als {RANDBAND_M:.0f} m an einer Wahlbezirksgrenze {fmt(rand, 0)} "
        f"({fmt(100 * rand / u.height, 1)} %); Getötete/Schwer/Leicht "
        f"{u.group_by('kategorie').len().sort('kategorie').rows()}"
    )
    # Primär die unscharfe Zuordnung (Randband), daneben die scharfe Punkt-in-Fläche.
    u = u.with_row_index("punkt")
    anteile = sb.anteile(ux, uy, RANDBAND_M).join(
        u.select("punkt", "kategorie", "rad", "fuss"), on="punkt"
    )
    geteilt = anteile.filter(pl.col("anteil") < 1).select("punkt").n_unique()
    print(
        f"  unscharf zugeordnet (Band {RANDBAND_M:.0f} m): {fmt(geteilt, 0)} Unfälle auf zwei oder mehr "
        f"Wahlbezirke geteilt, {u.height - anteile.select('punkt').n_unique()} ohne Wahlbezirk"
    )
    unfaelle = (
        anteile.group_by("wahlkreis_id")
        .agg(
            pl.col("anteil").sum().alias("unfaelle"),
            pl.col("anteil").filter(pl.col("kategorie") <= 2).sum().alias("unfaelle_schwer"),
            pl.col("anteil")
            .filter((pl.col("rad") == 1) | (pl.col("fuss") == 1))
            .sum()
            .alias("unfaelle_rad_fuss"),
        )
        .join(
            u.filter(pl.col("wahlkreis_id") > 0)
            .group_by("wahlkreis_id")
            .agg(
                pl.len().alias("unfaelle_scharf"), pl.col("am_rand").sum().alias("unfaelle_am_rand")
            ),
            on="wahlkreis_id",
            how="full",
            coalesce=True,
        )
        .sort("wahlkreis_id")
    )

    # Straßenverkehrslärm 2018 je Gebäude, über die Hauskoordinaten NRW verortet.
    laerm = pl.read_csv(
        datei("duesseldorf-verkehrslaerm", "Strassenverkehrslaerm_Gebaeudedatei_2018.csv"),
        separator=";",
        infer_schema=False,
        encoding="utf8",
    )
    teile = pl.col("STRASCHL-HSNR").str.extract_groups(r"^(\d+)-(\d+)\s*([A-Za-z]*)")
    laerm = laerm.with_columns(
        teile.struct.field("1").cast(pl.Int64).alias("strasse"),
        teile.struct.field("2").cast(pl.Int64).alias("hnr"),
        teile.struct.field("3").str.to_lowercase().fill_null("").alias("adz"),
        pl.col("DB_TAG").cast(pl.Int64, strict=False).alias("db_tag"),
        pl.col("DB_NACHT").cast(pl.Int64, strict=False).alias("db_nacht"),
        (pl.col("WOHNGEBAEUDE") == "ja").alias("wohnen"),
    )
    g = (
        gebref_auszug()
        .group_by("strasse", "hnr", "adz")
        .agg(pl.col("x").mean(), pl.col("y").mean())
    )
    lj = laerm.join(g, on=["strasse", "hnr", "adz"], how="left").sort("ID")
    getroffen = lj.filter(pl.col("x").is_not_null())
    lx, ly = getroffen["x"].to_numpy(), getroffen["y"].to_numpy()
    getroffen = getroffen.with_columns(pl.Series("wahlkreis_id", sb.wahlbezirk(lx, ly)))
    wohn = laerm.filter(pl.col("wohnen")).height
    wohn_ok = getroffen.filter(pl.col("wohnen")).height
    print(
        f"  Lärm 2018: {fmt(laerm.height, 0)} Gebäude, davon {fmt(wohn, 0)} Wohngebäude; verortet über "
        f"Straßenschlüssel und Hausnummer {fmt(getroffen.height, 0)} ({fmt(100 * getroffen.height / laerm.height, 1)} %), "
        f"Wohngebäude {fmt(100 * wohn_ok / wohn, 1)} %; außerhalb der Stimmbezirke "
        f"{getroffen.filter(pl.col('wahlkreis_id') == 0).height}; Wertebereich Tag "
        f"{laerm['db_tag'].min()}–{laerm['db_tag'].max()}, Nacht {laerm['db_nacht'].min()}–{laerm['db_nacht'].max()}"
    )
    laerm_wb = (
        getroffen.filter(pl.col("wohnen"), pl.col("wahlkreis_id") > 0)
        .group_by("wahlkreis_id")
        .agg(
            pl.len().alias("wohngebaeude_laerm"),
            (pl.col("db_tag") >= LAERM_TAG_DB).mean().alias("anteil_laerm_tag"),
            (pl.col("db_nacht") >= LAERM_NACHT_DB).mean().alias("anteil_laerm_nacht"),
        )
        .sort("wahlkreis_id")
    )

    # Kitas (Stand der CSV 2024-07): Punkte; ein Angebot, kein Bedarf.
    kita = pl.read_csv(
        datei("duesseldorf-kitas", "Tageseinrichtungen_fuer_Kinder.csv"),
        separator=";",
        infer_schema=False,
        encoding="utf8",
    )
    kita = kita.with_columns(
        pl.col("LONGITUDE").cast(pl.Float64, strict=False).alias("lon"),
        pl.col("LATITUDE").cast(pl.Float64, strict=False).alias("lat"),
    )
    kaputt = kita.filter(
        pl.col("lon").is_null() | pl.col("lat").is_null() | ~pl.col("lat").is_between(50, 52)
    ).height
    kita = kita.filter(pl.col("lon").is_not_null(), pl.col("lat").is_between(50, 52))
    to_work_ll = transformer("EPSG:4326", WORKING_CRS)
    kx, ky = to_work_ll.transform(kita["lon"].to_numpy(), kita["lat"].to_numpy())
    kita = kita.with_columns(
        pl.Series("wahlkreis_id", sb.wahlbezirk(np.asarray(kx), np.asarray(ky)))
    )
    print(
        f"  Kitas: {kita.height + kaputt} Einrichtungen, {kaputt} ohne lesbare Koordinate, außerhalb der Stimmbezirke "
        f"{kita.filter(pl.col('wahlkreis_id') == 0).height}; keine Platzzahl in der Datei"
    )
    kitas = (
        kita.filter(pl.col("wahlkreis_id") > 0)
        .group_by("wahlkreis_id")
        .agg(pl.len().alias("kitas"))
    )

    # Schulsozialindex NRW (Schuljahr 2025/26, Stufe 1 bis 9) der Grundschulen, über die
    # Koordinaten der amtlichen Schuldaten verortet: ein zweiter, unabhängiger Bedarfsindex.
    roh = datei("nrw-schuldaten", "schuldaten.csv").read_text(encoding="utf-8").split("\n", 1)[1]
    schulen = pl.read_csv(io.StringIO(roh), separator=";", infer_schema=False).filter(
        pl.col("Gemeindeschluessel") == "".join(AGS)
    )
    # Die Liste des Sozialindex ist in Codepage 850 gespeichert (ß als 0xE1, ü als 0x81).
    si = pl.read_csv(
        io.StringIO(
            datei("nrw-schulsozialindex", "schulliste_sj_25_26_open_data.csv")
            .read_bytes()
            .decode("cp850")
        ),
        separator=";",
        infer_schema=False,
    ).select(
        "Schulnummer",
        # "ohne": Schulen ohne Stufe (zu klein oder neu), sie fallen heraus
        pl.col("Sozialindexstufe").cast(pl.Int64, strict=False).alias("sozialindex"),
    )
    gs = (
        schulen.filter(pl.col("Schulform") == "02")
        .join(si, on="Schulnummer", how="left")
        .with_columns(
            pl.col("UTMRechtswert").cast(pl.Float64).alias("x"),
            pl.col("UTMHochwert").cast(pl.Float64).alias("y"),
        )
        .sort("Schulnummer")
    )
    gs = gs.with_columns(
        pl.Series("wahlkreis_id", sb.wahlbezirk(gs["x"].to_numpy(), gs["y"].to_numpy()))
    )
    print(
        f"  Schulsozialindex: {schulen.height} Schulen der Stadt, {gs.height} Grundschulen, davon mit "
        f"Index {gs['sozialindex'].is_not_null().sum()}, außerhalb der Stimmbezirke "
        f"{gs.filter(pl.col('wahlkreis_id') == 0).height}"
    )
    schulindex = (
        gs.filter(pl.col("wahlkreis_id") > 0, pl.col("sozialindex").is_not_null())
        .group_by("wahlkreis_id")
        .agg(pl.col("sozialindex").mean().alias("sozialindex_gs"), pl.len().alias("grundschulen"))
    )

    stadtbezirk = (
        pl.read_parquet(proc / "wahlbezirke_stadtbezirke.parquet")
        .sort("wahlkreis_id", "gewicht", "stadtbezirk", descending=[False, True, False])
        .group_by("wahlkreis_id", maintain_order=True)
        .first()
        .select("wahlkreis_id", "stadtbezirk")
    )

    df = (
        basis.join(auswertung, on="wahlkreis_id", how="left")
        .join(stadtbezirk, on="wahlkreis_id", how="left")
        .join(zensus, on="wahlkreis_id", how="left")
        .join(qa_ew, on="wahlkreis_id", how="left")
        .join(kontext, on="wahlkreis_id", how="left")
        .join(unfaelle, on="wahlkreis_id", how="left")
        .join(laerm_wb, on="wahlkreis_id", how="left")
        .join(kitas, on="wahlkreis_id", how="left")
        .join(schulindex, on="wahlkreis_id", how="left")
        .with_columns(
            pl.col(
                "unfaelle",
                "unfaelle_schwer",
                "unfaelle_rad_fuss",
                "unfaelle_scharf",
                "unfaelle_am_rand",
                "kitas",
            ).fill_null(0),
            pl.Series("flaeche_km2", [sb.flaeche_km2[w] for w in wbs]),
        )
        .with_columns(
            (pl.col("unfaelle") / pl.col("einwohner_zensus") * 1000).alias("unfaelle_je_1000"),
            (pl.col("unfaelle") / pl.col("flaeche_km2")).alias("unfaelle_je_km2"),
            (pl.col("kitas") / pl.col("u6_qa2021") * 1000).alias("kitas_je_1000_u6"),
        )
        .sort("wahlkreis_id")
    )

    # Gegenprobe der Umrechnung: Einwohner Zensus (Punkt) gegen Quartiersatlas (Crosswalk).
    r = stats.pearsonr(df["einwohner_zensus"], df["einwohner_qa2021"])
    rel = (df["einwohner_zensus"] / df["einwohner_qa2021"] - 1).abs()
    print(
        f"  Einwohner je Wahlbezirk: Zensus 2022 {fmt(df['einwohner_zensus'].min(), 0)} bis "
        f"{fmt(df['einwohner_zensus'].max(), 0)} (Summe {fmt(df['einwohner_zensus'].sum(), 0)}); "
        f"Quartiersatlas 2021 über den Crosswalk Summe {fmt(df['einwohner_qa2021'].sum(), 0)}; "
        f"r = {fmt(r.statistic)}, Median |Abweichung| {fmt(100 * rel.median(), 1)} %, größte "
        f"{fmt(100 * rel.max(), 1)} % (Wahlbezirk {df['wahlkreis_id'][int(rel.arg_max())]})"
    )
    for spalte in [
        "einwohner_zensus", "unfaelle", "unfaelle_je_1000", "unfaelle_je_km2", "unfaelle_rad_fuss",
        "anteil_laerm_tag", "anteil_laerm_nacht", "miete_qm", "miete_abdeckung", "hb_score",
        "anteil_u18", "mindestsicherung", "kitas", "kitas_je_1000_u6", "sozialindex_gs",
        "grundschulen",
    ]:  # fmt: skip
        s = df[spalte]
        print(
            f"  {spalte:20s} min {fmt(s.min(), 3):>10s}  median {fmt(s.median(), 3):>10s}  "
            f"max {fmt(s.max(), 3):>10s}  fehlend {s.null_count()}"
        )
    am_rand = (df["unfaelle_am_rand"] / df["unfaelle_scharf"]).to_numpy()
    rs = stats.spearmanr(df["unfaelle"], df["unfaelle_scharf"]).statistic
    print(f"  Unfälle unscharf gegen scharf je Wahlbezirk: Spearman {fmt(rs)}")
    print(
        f"  Unfälle am Rand je Wahlbezirk: Median {fmt(100 * float(np.median(am_rand)), 1)} %, "
        f"größter Anteil {fmt(100 * float(am_rand.max()), 1)} %"
    )
    return df


# --- Aufmerksamkeit je Wahlbezirk --------------------------------------------------------------------
KLASSE_VERKEHR = ["OVA"]  # Ordnungs- und Verkehrsausschuss (Ausschussklassifikator, Option 05)
KLASSE_JUGEND = ["JHA", "SCHUA"]  # Jugendhilfeausschuss, Schulausschuss


def aufmerksamkeit(root: Path) -> pl.DataFrame:
    print("\n## Aufmerksamkeit je Wahlbezirk")
    proc = root / "processed"
    ausw = pl.read_parquet(
        proc / "wahlbezirke_auswertung.parquet",
        columns=["wahlkreis_id", "suchbegriffe", "paper_ids", "anzahl_treffer"],
    )
    klasse = pl.read_parquet(proc / "papers_ausschuss.parquet", columns=["id", "ausschuss"])
    lang = (
        ausw.select("wahlkreis_id", pl.col("paper_ids").alias("id"))
        .explode("id")
        .drop_nulls("id")
        .unique()
        .join(klasse, on="id", how="left")
        .sort("wahlkreis_id", "id")
    )
    df = (
        lang.group_by("wahlkreis_id")
        .agg(
            pl.len().alias("dok"),
            pl.col("ausschuss").is_not_null().sum().alias("dok_mit_text"),
            pl.col("ausschuss").is_in(KLASSE_VERKEHR).sum().alias("dok_verkehr"),
            pl.col("ausschuss").is_in(KLASSE_JUGEND).sum().alias("dok_jugend"),
        )
        .join(
            ausw.select(
                "wahlkreis_id",
                pl.col("suchbegriffe").list.len().alias("begriffe"),
                "anzahl_treffer",
            ),
            on="wahlkreis_id",
        )
        .with_columns(
            (pl.col("dok_verkehr") / pl.col("dok_mit_text")).alias("anteil_verkehr"),
            (pl.col("dok_jugend") / pl.col("dok_mit_text")).alias("anteil_jugend"),
        )
        .sort("wahlkreis_id")
    )
    gesamt = klasse.height
    print(
        f"  Korpus mit Text {fmt(gesamt, 0)}; Klasse Verkehr {klasse.filter(pl.col('ausschuss').is_in(KLASSE_VERKEHR)).height}, "
        f"Jugend und Schule {klasse.filter(pl.col('ausschuss').is_in(KLASSE_JUGEND)).height}, "
        f"Restklasse {klasse.filter(pl.col('ausschuss') == '').height}"
    )
    assert (df["dok"] == df["anzahl_treffer"]).all(), "paper_ids und anzahl_treffer passen nicht"
    for spalte in [
        "dok",
        "dok_mit_text",
        "begriffe",
        "dok_verkehr",
        "anteil_verkehr",
        "dok_jugend",
        "anteil_jugend",
    ]:
        s = df[spalte]
        print(
            f"  {spalte:15s} min {fmt(s.min()):>9s}  median {fmt(s.median()):>9s}  max {fmt(s.max()):>9s}"
        )
    return df


# --- Tests -----------------------------------------------------------------------------------------------
def spearman_test(
    x: np.ndarray, y: np.ndarray, *, einseitig: bool, rng: np.random.Generator
) -> tuple[float, float, tuple[float, float]]:
    """Spearman ρ, p aus Permutationen (einseitig: ρ > 0), Perzentil-Bootstrap-Intervall 95 %."""
    rx, ry = stats.rankdata(x), stats.rankdata(y)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    perm = np.array([np.corrcoef(rx, rng.permutation(ry))[0, 1] for _ in range(PERMUTATIONEN)])
    if einseitig:
        p = (1 + int((perm >= rho - 1e-12).sum())) / (PERMUTATIONEN + 1)
    else:
        p = (1 + int((np.abs(perm) >= abs(rho) - 1e-12).sum())) / (PERMUTATIONEN + 1)
    n = len(x)
    boot = []
    for _ in range(BOOTSTRAP):
        i = rng.integers(0, n, n)
        a, b = stats.rankdata(x[i]), stats.rankdata(y[i])
        if a.std() > 0 and b.std() > 0:
            boot.append(np.corrcoef(a, b)[0, 1])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return rho, p, (float(lo), float(hi))


def partial_spearman(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> float:
    """Partielle Rangkorrelation von x und y bei festem z (Residuen der Ränge)."""
    rx, ry, rz = stats.rankdata(x), stats.rankdata(y), stats.rankdata(z)
    A = np.column_stack([np.ones_like(rz), rz])
    ex = rx - A @ np.linalg.lstsq(A, rx, rcond=None)[0]
    ey = ry - A @ np.linalg.lstsq(A, ry, rcond=None)[0]
    return float(np.corrcoef(ex, ey)[0, 1])


def holm(pwerte: list[float]) -> list[float]:
    m = len(pwerte)
    order = sorted(range(m), key=lambda i: pwerte[i])
    adj = [0.0] * m
    laufend = 0.0
    for rang, i in enumerate(order):
        laufend = max(laufend, min(1.0, (m - rang) * pwerte[i]))
        adj[i] = laufend
    return adj


HYPOTHESEN = [
    # (Name, Bedarf, Aufmerksamkeit, einseitig, Kontrolle für die Robustheit)
    ("H1 Unfälle → Verkehr", "unfaelle_je_1000", "anteil_verkehr", True, None),
    ("H2 Handlungsbedarf → Aufmerksamkeit", "hb_score", "dok_je_1000_ew", False, "log_begriffe"),
    ("H3 Anteil unter 18 → Jugend und Schule", "anteil_u18", "anteil_jugend", True, None),
]


def hypothesen(df: pl.DataFrame) -> None:
    print("\n## Vorab festgelegte Hypothesen (22-bedarf.md, § 8)")
    rng = np.random.default_rng(SEED)
    ergebnisse = []
    for name, x_spalte, y_spalte, einseitig, _ in HYPOTHESEN:
        x, y = df[x_spalte].to_numpy(), df[y_spalte].to_numpy()
        rho, p, ci = spearman_test(x, y, einseitig=einseitig, rng=rng)
        ergebnisse.append((name, rho, p, ci))
    angepasst = holm([e[2] for e in ergebnisse])
    for (name, rho, p, ci), p_holm, h in zip(ergebnisse, angepasst, HYPOTHESEN, strict=True):
        if p_holm >= ALPHA:
            urteil = "nicht bestätigt (kein Zusammenhang nachweisbar)"
        elif h[3]:
            urteil = "bestätigt"
        else:  # H2 zweiseitig: die Richtung entscheidet die Deutung (§ 8)
            urteil = "Aufmerksamkeit folgt dem Bedarf" if rho > 0 else "ungleiche Aufmerksamkeit"
        print(
            f"  {name}: ρ = {fmt(rho)} [{fmt(ci[0])}; {fmt(ci[1])}], p = {fmt(p, 4)} "
            f"({'einseitig' if h[3] else 'zweiseitig'}), Holm {fmt(p_holm, 4)} -> {urteil}"
        )
    # Kontrolle, nachgetragen nach dem ersten Lauf (entscheidet nicht): der Monte-Carlo-Fehler der
    # Permutations-p und das asymptotische p von scipy für denselben Test.
    for (name, _, p, _), h in zip(ergebnisse, HYPOTHESEN, strict=True):
        asym = stats.spearmanr(
            df[h[1]], df[h[2]], alternative="greater" if h[3] else "two-sided"
        ).pvalue
        se = math.sqrt(p * (1 - p) / PERMUTATIONEN)
        print(
            f"  Kontrolle {name.split()[0]}: p asymptotisch {fmt(asym, 4)}, Monte-Carlo-Fehler ± {fmt(se, 4)}"
        )
    n = df.height
    # Kleinstes ρ, das ein Test mit 80 % Power fände (Fisher-z, Varianz der Spearman-z 1,06/(n-3)).
    for a, text in [
        (ALPHA, "α = 0,05 einseitig"),
        (ALPHA / 3, "α = 0,05/3 einseitig (Holm, erster Schritt)"),
    ]:
        z = (stats.norm.ppf(1 - a) + stats.norm.ppf(0.8)) * math.sqrt(1.06 / (n - 3))
        print(f"  erkennbar mit 80 % Power bei n = {n}, {text}: |ρ| ≥ {fmt(math.tanh(z), 2)}")
    # Robustheit (vorab genannt, nicht entscheidend)
    rob = df.filter(~pl.col("wahlkreis_id").is_in([1, 10]))
    for name, x_spalte, y_spalte, _, kontrolle in HYPOTHESEN:
        r_ohne = stats.spearmanr(rob[x_spalte], rob[y_spalte]).statistic
        teil = f"ohne 1 und 10 ρ = {fmt(r_ohne)}"
        if kontrolle:
            teil += f"; partiell bei {kontrolle} ρ = {fmt(partial_spearman(df[x_spalte].to_numpy(), df[y_spalte].to_numpy(), df[kontrolle].to_numpy()))}"
        print(f"  Robustheit {name.split()[0]}: {teil}")
    rs = stats.spearmanr(
        df["unfaelle_scharf"] / df["einwohner_zensus"], df["anteil_verkehr"]
    ).statistic
    print(f"  Robustheit H1 mit scharfer Zuordnung (Punkt in Fläche): ρ = {fmt(rs)}")
    rx = stats.spearmanr(df["unfaelle"], df["anteil_verkehr"]).statistic
    rk = stats.spearmanr(df["unfaelle_je_km2"], df["anteil_verkehr"]).statistic
    rw = stats.spearmanr(df["hb_score"], df["trefferquote"]).statistic
    print(
        f"  Robustheit H1 mit anderen Nennern: Unfälle absolut ρ = {fmt(rx)}, je km² ρ = {fmt(rk)}; "
        f"H2 mit der Trefferquote der Seite (je Wahlberechtigtem) ρ = {fmt(rw)}"
    )


def morans_i(werte: np.ndarray, w: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    """Moran's I mit zeilennormierten Gewichten, p aus 9 999 Permutationen (einseitig, I > E[I])."""
    w = w / w.sum(axis=1, keepdims=True)
    z = werte - werte.mean()

    def i_von(v: np.ndarray) -> float:
        return float(len(v) * (v @ w @ v) / (w.sum() * (v @ v)))

    i = i_von(z)
    perm = np.array([i_von(rng.permutation(z)) for _ in range(9_999)])
    return i, (1 + int((perm >= i).sum())) / 10_000


def explorativ(df: pl.DataFrame, sb: Stimmbezirke) -> None:
    print("\n## Explorativ (nicht vorab festgelegt)")
    rng = np.random.default_rng(SEED + 1)
    print(
        f"  Nachbarschaft: {int(sb.nachbarn.sum() / 2)} Paare, je Wahlbezirk "
        f"{int(sb.nachbarn.sum(axis=1).min())} bis {int(sb.nachbarn.sum(axis=1).max())} Nachbarn"
    )
    # Innerhalb der Stadtbezirke: Ränge von x und y je Stadtbezirk (der mit den meisten
    # Wahlberechtigten des Wahlbezirks) um den Mittelwert bereinigt, dann korreliert. Fragt, ob der
    # Zusammenhang auch zwischen Nachbarn derselben Bezirksvertretung gilt.
    sbz = df.get_column("stadtbezirk").to_numpy()
    dummies = np.column_stack([(sbz == k).astype(float) for k in np.unique(sbz)])
    je_bezirk = (
        df.group_by("stadtbezirk")
        .agg(
            pl.len().alias("wb"),
            pl.col("unfaelle_je_1000").median(),
            pl.col("anteil_verkehr").median(),
            pl.col("anteil_u18").median(),
            pl.col("anteil_jugend").median(),
        )
        .sort("stadtbezirk")
    )
    print(
        "  je Stadtbezirk (Mediane der Wahlbezirke): Stadtbezirk, Wahlbezirke, Unfälle je 1 000, Anteil Verkehr, Anteil u18, Anteil Jugend"
    )
    for row in je_bezirk.iter_rows():
        print("   ", row[0], row[1], *(fmt(v) for v in row[2:]))
    for name, x_spalte, y_spalte, _, _ in HYPOTHESEN:
        rx = stats.rankdata(df[x_spalte].to_numpy())
        ry = stats.rankdata(df[y_spalte].to_numpy())
        ex = rx - dummies @ np.linalg.lstsq(dummies, rx, rcond=None)[0]
        ey = ry - dummies @ np.linalg.lstsq(dummies, ry, rcond=None)[0]
        r = float(np.corrcoef(ex, ey)[0, 1])
        perm = np.array([np.corrcoef(ex, rng.permutation(ey))[0, 1] for _ in range(9_999)])
        pp = (1 + int((np.abs(perm) >= abs(r)).sum())) / 10_000
        print(
            f"  innerhalb der {dummies.shape[1]} Stadtbezirke {name.split()[0]}: ρ = {fmt(r)} "
            f"(zweiseitig p = {fmt(pp, 4)})"
        )
    for name, x_spalte, y_spalte, _, _ in HYPOTHESEN:
        rx = stats.rankdata(df[x_spalte].to_numpy())
        ry = stats.rankdata(df[y_spalte].to_numpy())
        a = np.column_stack([np.ones_like(rx), rx])
        resid = ry - a @ np.linalg.lstsq(a, ry, rcond=None)[0]
        i, p = morans_i(resid, sb.nachbarn, rng)
        ix, px = morans_i(rx, sb.nachbarn, rng)
        iy, py = morans_i(ry, sb.nachbarn, rng)
        print(
            f"  Moran's I {name.split()[0]}: Residuen der Ränge I = {fmt(i)} (p = {fmt(p, 4)}); "
            f"x I = {fmt(ix)} (p = {fmt(px, 4)}), y I = {fmt(iy)} (p = {fmt(py, 4)}); E[I] = {fmt(-1 / (df.height - 1))}"
        )
    paare = [
        ("anteil_laerm_tag", "anteil_verkehr"),
        ("anteil_laerm_nacht", "anteil_verkehr"),
        ("unfaelle_rad_fuss", "anteil_verkehr"),
        ("unfaelle_je_1000", "dok_verkehr_je_1000_ew"),
        ("mindestsicherung", "dok_je_1000_ew"),
        ("miete_qm", "dok_je_1000_ew"),
        ("hb_score", "wahlbeteiligung"),
        ("kitas_je_1000_u6", "anteil_jugend"),
        ("hb_score", "anteil_verkehr"),
        ("hb_score", "sozialindex_gs"),
        ("sozialindex_gs", "dok_je_1000_ew"),
        ("unfaelle_je_1000", "hb_score"),
    ]
    for a, b in paare:
        sub = df.drop_nulls([a, b])
        r = stats.spearmanr(sub[a], sub[b])
        print(
            f"  {a:22s} ~ {b:22s} ρ = {fmt(r.statistic):>7s}  p = {fmt(r.pvalue, 3)}  n = {sub.height}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--teil",
        default="alle",
        choices=["bestand", "bedarf", "aufmerksamkeit", "hypothesen", "explorativ", "alle"],
    )
    teil = ap.parse_args().teil
    bestand()
    if teil == "bestand":
        return
    root = Path(paths(PROFIL)["root"])
    sb = Stimmbezirke(root)
    print(
        f"\nStimmbezirke {len(sb.precincts)}, Wahlbezirke {len(set(sb.wb))}, "
        f"Fläche {fmt(sb.stadt.area / 1e6, 1)} km²"
    )
    df = None
    if teil in ("bedarf", "hypothesen", "explorativ", "alle"):
        df = bedarf(root, sb)
    if teil in ("aufmerksamkeit", "hypothesen", "explorativ", "alle"):
        auf = aufmerksamkeit(root)
        if df is not None:
            df = df.join(auf, on="wahlkreis_id", how="left").with_columns(
                (pl.col("dok") / pl.col("einwohner_zensus") * 1000).alias("dok_je_1000_ew"),
                (pl.col("dok_verkehr") / pl.col("einwohner_zensus") * 1000).alias(
                    "dok_verkehr_je_1000_ew"
                ),
                pl.col("begriffe").cast(pl.Float64).log().alias("log_begriffe"),
            )
    if df is not None and teil in ("hypothesen", "alle"):
        hypothesen(df)
    if df is not None and teil in ("explorativ", "alle"):
        explorativ(df, sb)
    if df is not None and teil == "alle":
        # Größen der Auszüge (§ 2.3): so viel müsste ein Paket unter context/ tragen.
        for name in ["unfaelle_duesseldorf", "zensus2022_duesseldorf", "gebref_duesseldorf"]:
            f = AUSZUG / f"{name}.parquet"
            puffer = io.BytesIO()
            pl.read_parquet(f).write_csv(puffer)
            print(
                f"  Auszug {name}: {fmt(pl.read_parquet(f).height, 0)} Zeilen, Parquet "
                f"{fmt(f.stat().st_size / 1000, 0)} KB, als CSV {fmt(len(puffer.getvalue()) / 1000, 0)} KB"
            )
        ziel = AUSZUG / "wahlbezirke_bedarf.parquet"
        df.drop("suchbegriffe", strict=False).write_parquet(ziel)
        print(f"\nTabelle je Wahlbezirk: {ziel}")


if __name__ == "__main__":
    t0 = __import__("time").perf_counter()
    main()
    print(f"\nLaufzeit {fmt(__import__('time').perf_counter() - t0, 1)} s")
