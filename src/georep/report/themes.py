"""Die Unterseite ``themen.html``: Politikfelder nach dem CAP (Vorhaben 19, Stufe 3).

Messdokument ``docs/plans/19-politikfelder.md``, § 7 mit § 10, im Muster von ``akteure.html`` und
``bedarf.html`` (Punkte 88 und 95), ohne Karte (§ 10, Punkt 5). Fünf Abschnitte:

1. *Politikfelder in dieser Periode*: je Feld der Anteil an den Dokumenten von Rat und Ausschüssen
   und an denen der Bezirksvertretungen, getrennt, dazu alle Dokumente;
2. *Je Fraktion*: die Anteile an den Dokumenten mit Antragsteller (Vorhaben 15, Punkt 75),
   gemeinsame Anträge für jede beteiligte Fraktion, für alle Fraktionen gleich, ab 30 Dokumenten;
3. *Je Wahlbezirk*: dieselben Anteile an den Dokumenten mit Treffer im Wahlbezirk, als Tabelle,
   mit dem Hinweis auf den ökologischen Fehlschluss;
4. *Vergleich mit dem Bundestag*: Anteile an den Anfragen des Bundestags 1976–2005, abgeleitet aus
   den Codes des German Policy Agendas Project, mit Quelle;
5. *Wie die Felder entstehen*: der Satz aus ``guete.json``, Makro-F1 und die Prüfung an menschlich
   kodierten Bundestagstiteln als geprüfte Konstanten (``MEASURED``), die Destillation von Weg 1.

**Gestapelte Leiste oder Zeile je Feld.** § 7 nennt eine gestapelte Leiste je Periode mit 21 Feldern
und „nicht bestimmt". 22 Farben trennt niemand; die Seite zeigt darum je Feld eine Zeile mit einem
Balken je Gremiengruppe (Länge statt Farbe), und die Zahl steht daneben.

**Lizenz.** Die Codes und alles, was aus ihnen abgeleitet ist (die ganze Seite und ihre beiden
Tabellen), stehen unter CC BY-NC-SA 4.0 (Frage 37), getrennt vom Rest der Seite (CC0): der Vermerk
steht oben und im Fuß (``Page.license``).

Rein bis auf ``read_check`` und ``themes_data``, die Dateien lesen; kein Stadtwort im Code.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import deal
import polars as pl

from georep.enrich.policy_areas import (
    CC_BY_NC_SA,
    CODES,
    NAMES,
    NO_AREA,
    SHORT_NAMES,
    UNDETERMINED,
    policy_area_files,
)
from georep.errors import MissingInputError, SchemaError
from georep.layout import Layout
from georep.settings import Settings, load_settings, profile_folder

PAGE_NAME = "themen"
VALIDATION_PROJECT = "19-politikfelder"  # die Prüfung unter ``validation.root`` (Messdokument § 4)
QUESTION = "politikfeld"
MEASUREMENT = "docs/plans/19-politikfelder.md"  # Messdokument, relativ zum Repository
MIN_DOCUMENTS = 30  # § 10, Punkt 3: eine Fraktion darunter steht ohne Anteile da
MIN_GOLD = (
    5  # Felder mit so vielen Gold-Dokumenten nennt die Seite beim F1 je Feld (Nebenmaß § 8.5)
)
LOW_CONFIDENCE = (
    0.5  # die Seite zählt, wie oft das gewählte Thema unter dieser Wahrscheinlichkeit liegt
)
CAP_SITE = "https://www.comparativeagendas.net/"
CAP_GERMANY = "https://www.comparativeagendas.net/germany/datasets"
CAP_DOI = "https://doi.org/10.1080/13572334.2021.2010395"
CAP_ATTRIBUTION = (
    "Codes nach dem Comparative Agendas Project (CAP); German Policy Agendas Project, Breunig, "
    "Guinaudeau und Schnatterer (2021)"
)
COUNCIL_KINDS = ("rat", "ausschuss")  # Rat und Ausschüsse, eine Gruppe (§ 7)
DISTRICT_KINDS = ("bezirksvertretung",)
Status = Literal["gemessen", "periode", "explorativ"]


@dataclass(frozen=True)
class MeasuredCheck:
    """Was die Messung über Weg 3b sagt und ``guete.json`` nicht trägt (Messdokument § 3.6, § 4.2, § 5).

    Das Intervall ist der gepaarte Bootstrap des Messskripts (2 000 Ziehungen, Seed 20261123), die
    zweite Prüfung lief an den Anfragentiteln aus den Fremddaten; beides liegt nicht im Repo und
    wird darum nicht nachgerechnet, sondern mit Verweis auf § 4.2 und § 3.6 genannt. Makro-F1 und
    Genauigkeit trägt ``guete.json``; ``read_check`` bricht ab, wenn sie dort andere sind oder
    die Kodierung eine andere ist (Codebuchversion, Einheiten): sonst stünde ein neuer Satz neben
    alten Zahlen (Muster ``RULE_CHECK`` in ``report.actors``, Punkt 88).
    """

    codebook_version: str = "2026-11-23.1"
    units: int = 300
    macro_f1: float = 0.704  # Hauptmaß, auf drei Stellen wie in § 4.2
    interval: tuple[float, float] = (0.620, 0.807)
    bundestag_f1: float = 0.688  # 200 von Menschen kodierte Anfragentitel (§ 3.6)
    bundestag_interval: tuple[float, float] = (0.596, 0.758)
    bundestag_units: int = 200
    teacher: str = "qwen3.6:27b"  # Weg 1, der Lehrer der Silberlabels
    teacher_agreement: int = 270  # Weg 1 und 3b einig auf der Testmenge (§ 5)
    silver: int = 4200  # Ratsdokumente mit Silberlabels von Weg 1 (§ 3.4)


MEASURED = MeasuredCheck()

# Abschnitt 4: Große und Kleine Anfragen des Bundestags 1976–2005 (8. bis 15. Wahlperiode) je
# Hauptthema, gezählt aus ``anfrage_1976-2005_website-release_2.5.csv`` des German Policy Agendas
# Project (Spalte ``cap_topic``; 10 033 Anfragen, alle mit einem Hauptthema, keine 99; SHA-256
# 98be16fc…, Abruf 2026-11-23, Messdokument § 2). Abgeleitete Zahlen aus CAP-Codes, darum wie die
# Seite unter CC BY-NC-SA 4.0. Die Datei liegt nicht im Repo; die Zählung steht im Commit, der diese
# Konstante einführt, und ein Test hält die Summe.
BUNDESTAG_QUERIES: dict[str, int] = {
    "1": 339, "2": 978, "3": 418, "4": 292, "5": 344, "6": 183, "7": 845, "8": 424, "9": 376,
    "10": 800, "12": 492, "13": 253, "14": 178, "15": 382, "16": 1099, "17": 252, "18": 139,
    "19": 1126, "20": 989, "21": 55, "23": 69,
}  # fmt: skip
BUNDESTAG_TOTAL = 10033
BUNDESTAG_SOURCE = (
    "Großen und Kleinen Anfragen des Bundestags 1976 bis 2005 (8. bis 15. Wahlperiode) aus dem "
    "German Policy Agendas Project, Datensatz 2.5"
)


# --- Die Prüfung (F4, Messdokument § 4) -----------------------------------------------------------
@dataclass(frozen=True)
class Check:
    """Was ``guete.json`` sagt, und ob dieser Datensatz der gemessene ist."""

    sentence: str  # ``satz``: Modelle, Einheiten, „nicht von Menschen"
    models: tuple[str, str, str]  # Kodierer A, Kodierer B, Schlichtung
    units: int
    agreed: int
    alpha: float
    accuracy: float
    macro_f1: float
    status: Status  # gemessen, eine andere Periode derselben Stadt, eine andere Stadt
    measured_dataset: str  # „Stadt, Wahlperiode …" der Stichprobe
    weakest: tuple[tuple[str, float], ...]  # die zwei Felder mit dem kleinsten F1 (≥ 5 Gold)
    confusion: tuple[str, str, int, int]  # häufigste Verwechslung: Gold, vorhergesagt, Zahl, Gold

    @property
    def same_model(self) -> bool:
        return self.models[0] == self.models[1]


def check_files(settings: Settings) -> tuple[Path, Path]:
    """``guete.json`` und ``stichprobe.json`` der Prüfung im Repo."""
    folder = settings.validation.root / VALIDATION_PROJECT
    return (folder / "guete.json", folder / "stichprobe.json")


def _status(settings: Settings, sample_profile: str) -> tuple[Status, str]:
    """Gemessen ist der Ordner der Stichprobe; dieselbe Stadt in einer anderen Periode nicht."""
    from georep.report.model import period_info

    try:
        sample = load_settings(profile=sample_profile, cwd=Path("/nonexistent"))
        folder = profile_folder(sample_profile)
    except OSError, ValueError, SchemaError:
        return "explorativ", sample_profile
    name = f"{sample.city.name}, {period_info(sample).title}"
    if settings.profile == folder:
        return "gemessen", name
    return ("periode" if settings.city.slug == sample.city.slug else "explorativ"), name


@deal.raises(MissingInputError, SchemaError)
def read_check(settings: Settings, measured: MeasuredCheck = MEASURED) -> Check:
    """Die Prüfung aus ``guete.json`` und ``stichprobe.json``; ``SchemaError`` bei anderer Kodierung."""
    quality_path, sample_path = check_files(settings)
    for path in (quality_path, sample_path):
        if not path.is_file():
            raise MissingInputError(f"{path} fehlt; die Seite {PAGE_NAME}.html nennt ihre Prüfung")
    quality: dict[str, Any] = json.loads(quality_path.read_text(encoding="utf-8"))
    sample: dict[str, Any] = json.loads(sample_path.read_text(encoding="utf-8"))
    try:
        entry = dict(quality["fragen"][QUESTION])
        method = dict(entry["verfahren"])
        models = dict(quality["modelle"])
        version = str(quality["codebuch_version"])
        units = int(entry["n"])
        macro = float(method["makro"]["f1"])
        status, name = _status(settings, str(sample["profil"]).split(",")[0].strip())
        classes = [dict(row) for row in method["klassen"]]
        weakest = sorted(
            (float(row["f1"]), CODES.index(str(row["label"])), str(row["label"]))
            for row in classes
            if int(row["gold"]) >= MIN_GOLD
        )[:2]
        confusion = dict(method["konfusion"])
        labels = [str(label) for label in confusion["labels"]]
        pairs = sorted(
            (-int(n), i, j)
            for i, row in enumerate(confusion["zeilen_gold"])
            for j, n in enumerate(row)
            if i != j and int(n)
        )
        top = pairs[0]
        gold_of = {str(row["label"]): int(row["gold"]) for row in classes}
        check = Check(
            sentence=str(quality["satz"]),
            models=(
                str(models["kodierer_a"]),
                str(models["kodierer_b"]),
                str(models["schlichtung"]),
            ),
            units=units,
            agreed=int(entry["einig"]),
            alpha=float(entry["krippendorff_alpha"]),
            accuracy=float(method["genauigkeit"]),
            macro_f1=macro,
            status=status,
            measured_dataset=name,
            weakest=tuple((SHORT_NAMES[code], f1) for f1, _, code in weakest),
            confusion=(
                SHORT_NAMES[labels[top[1]]],
                SHORT_NAMES[labels[top[2]]],
                -top[0],
                gold_of.get(labels[top[1]], 0),
            ),
        )
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise SchemaError(f"{quality_path} oder {sample_path}: Feld fehlt ({error})") from error
    if (version, units) != (measured.codebook_version, measured.units) or round(macro, 3) != (
        measured.macro_f1
    ):
        raise SchemaError(
            f"{quality_path}: Codebuch {version}, {units} Einheiten, Makro-F1 {macro:.3f}; die "
            f"Konstanten der Messung (MEASURED) sagen {measured.codebook_version}, "
            f"{measured.units}, {measured.macro_f1}. Nach einer neuen Kodierung beide nachziehen"
        )
    return check


# --- Zeilen der Seite -----------------------------------------------------------------------------
@dataclass(frozen=True)
class AreaRow:
    """Ein Feld in Abschnitt 1 (und 4): Zahl und Anteil je Gremiengruppe, Anteil im Bundestag."""

    code: str
    name: str
    short: str
    council: int  # Rat und Ausschüsse
    district: int  # Bezirksvertretungen
    total: int  # alle Dokumente mit Feld
    council_share: float
    district_share: float
    total_share: float
    bundestag_share: float | None  # None für 99


@dataclass(frozen=True)
class Group:
    """Eine Gremiengruppe in Abschnitt 1: Dokumente mit Feld, ohne Rohtext, mit 99."""

    label: str
    documents: int
    with_area: int
    undetermined: int
    no_area: int


@dataclass(frozen=True)
class ShareRow:
    """Eine Fraktion oder ein Wahlbezirk: Anteile in der Folge der Spalten, oder keine."""

    key: str
    label: str
    documents: int  # mit Feld
    undetermined: int  # ohne Rohtext
    shares: tuple[float, ...] | None  # None unter ``MIN_DOCUMENTS`` (nur Fraktionen)
    top: str  # Kurzname des häufigsten Felds


@dataclass(frozen=True)
class ThemesModel:
    check: Check
    measured: MeasuredCheck
    period: str
    documents: int
    with_area: int
    undetermined: int
    no_area: int
    cut: int  # abgeschnitten
    low_confidence: int  # gewähltes Thema mit Wahrscheinlichkeit unter LOW_CONFIDENCE
    groups: tuple[Group, ...]
    areas: tuple[AreaRow, ...]  # nach Zahl absteigend, 99 zuletzt
    columns: tuple[tuple[str, str], ...]  # (Code, Kurzname) der breiten Tabellen
    fractions: tuple[ShareRow, ...] | None  # None ohne Antragsteller (Vorhaben 15 aus)
    districts: tuple[ShareRow, ...]
    district_documents: int  # Dokumente mit Treffer in mindestens einem Wahlbezirk und Feld

    @property
    def explorative(self) -> bool:
        return self.check.status == "explorativ"


def _counts(frame: pl.DataFrame) -> dict[str, int]:
    return {str(k): int(v) for k, v in frame.group_by("politikfeld").len().iter_rows()}


def _share(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def _shares_sum_to_one(rows: Sequence[ShareRow]) -> bool:
    return all(r.shares is None or abs(sum(r.shares) - 1.0) < 1e-9 for r in rows if r.documents)


@deal.ensure(lambda areas, keyed, columns, labels, minimum, result: _shares_sum_to_one(result),
             message="die Anteile einer Zeile ergeben zusammen eins")  # fmt: skip
def share_rows(
    areas: pl.DataFrame,
    keyed: pl.DataFrame,
    columns: Sequence[str],
    labels: Mapping[str, str],
    minimum: int,
) -> tuple[ShareRow, ...]:
    """Je Schlüssel (Fraktion, Wahlbezirk) die Anteile der Felder an seinen Dokumenten mit Feld.

    ``keyed`` trägt ``id`` und ``schluessel``, eine Zeile je Paar: ein gemeinsamer Antrag zählt für
    jede beteiligte Fraktion, ein Dokument mit Treffer in zwei Wahlbezirken für beide. ``columns``
    sind alle Codes, die in der Periode vorkommen, darum summieren die Anteile zu eins. Unter
    ``minimum`` Dokumenten mit Feld stehen keine Anteile da. Sortiert nach Dokumenten absteigend,
    dann nach Bezeichnung: dieselbe Regel für jeden Schlüssel.
    """
    joined = keyed.join(areas.select("id", "politikfeld"), on="id", how="inner").sort("id")
    rows = []
    for key in sorted(set(joined.get_column("schluessel").to_list())):
        part = joined.filter(pl.col("schluessel") == key)
        counts = _counts(part)
        filled = part.height - counts.get(UNDETERMINED, 0)
        shares = tuple(_share(counts.get(code, 0), filled) for code in columns)
        top = max(columns, key=lambda c: (counts.get(c, 0), -columns.index(c)))
        rows.append(
            ShareRow(
                key=str(key),
                label=labels.get(str(key), str(key)),
                documents=filled,
                undetermined=counts.get(UNDETERMINED, 0),
                shares=shares if filled >= minimum and filled else None,
                top=SHORT_NAMES[top] if filled else "",
            )
        )
    return tuple(sorted(rows, key=lambda r: (-r.documents, r.label)))


@dataclass(frozen=True)
class ThemesInputs:
    areas: pl.DataFrame  # politikfelder.parquet
    bodies: pl.DataFrame  # id, gremium_art
    cosponsors: pl.DataFrame | None  # id, fraktionen; None ohne Vorhaben 15
    results: pl.DataFrame  # wahlkreis_id, paper_ids
    district_names: Mapping[int, str]


def build_themes(
    inputs: ThemesInputs,
    settings: Settings,
    check: Check,
    fraction_labels: Mapping[str, str],
) -> ThemesModel:
    """Das Modell der Seite aus den Tabellen; liest keine Datei."""
    from georep.report.model import period_info

    areas = inputs.areas.sort("id")
    joined = (
        areas.select("id", "politikfeld", "wahrscheinlichkeit", "abgeschnitten")
        .join(inputs.bodies.select("id", "gremium_art"), on="id", how="left")
        .with_columns(pl.col("gremium_art").fill_null("unbekannt"))
        .sort("id")
    )
    everything = _counts(joined)
    council = _counts(joined.filter(pl.col("gremium_art").is_in(COUNCIL_KINDS)))
    district = _counts(joined.filter(pl.col("gremium_art").is_in(DISTRICT_KINDS)))
    rest = _counts(joined.filter(~pl.col("gremium_art").is_in((*COUNCIL_KINDS, *DISTRICT_KINDS))))

    def filled(counts: Mapping[str, int]) -> int:
        return sum(n for code, n in counts.items() if code != UNDETERMINED)

    def group(label: str, counts: Mapping[str, int]) -> Group:
        return Group(
            label=label,
            documents=sum(counts.values()),
            with_area=filled(counts),
            undetermined=counts.get(UNDETERMINED, 0),
            no_area=counts.get(NO_AREA, 0),
        )

    total_filled, council_filled, district_filled = (
        filled(everything),
        filled(council),
        filled(district),
    )
    present = [code for code in CODES if everything.get(code, 0)]
    ordered = sorted(present, key=lambda c: (c == NO_AREA, -everything.get(c, 0), CODES.index(c)))
    rows = tuple(
        AreaRow(
            code=code,
            name=NAMES[code],
            short=SHORT_NAMES[code],
            council=council.get(code, 0),
            district=district.get(code, 0),
            total=everything.get(code, 0),
            council_share=_share(council.get(code, 0), council_filled),
            district_share=_share(district.get(code, 0), district_filled),
            total_share=_share(everything.get(code, 0), total_filled),
            bundestag_share=(
                BUNDESTAG_QUERIES.get(code, 0) / BUNDESTAG_TOTAL if code != NO_AREA else None
            ),
        )
        for code in ordered
    )
    fractions = None
    if inputs.cosponsors is not None:
        keyed = (
            inputs.cosponsors.select("id", "fraktionen")
            .explode("fraktionen")
            .drop_nulls("fraktionen")
            .rename({"fraktionen": "schluessel"})
        )
        fractions = share_rows(areas, keyed, ordered, fraction_labels, MIN_DOCUMENTS)
    hits = (
        inputs.results.select(pl.col("wahlkreis_id").cast(pl.String).alias("schluessel"),
                              pl.col("paper_ids").alias("id"))
        .explode("id")
        .drop_nulls("id")
    )  # fmt: skip
    names = {str(k): f"{k} {v}" for k, v in inputs.district_names.items()}
    districts = share_rows(areas, hits, ordered, names, 1)
    with_hit = areas.filter(
        pl.col("id").is_in(hits.get_column("id").unique().to_list())
        & (pl.col("politikfeld") != UNDETERMINED)
    ).height
    return ThemesModel(
        check=check,
        measured=MEASURED,
        period=period_info(settings).title,
        documents=areas.height,
        with_area=total_filled,
        undetermined=everything.get(UNDETERMINED, 0),
        no_area=everything.get(NO_AREA, 0),
        cut=int(areas.get_column("abgeschnitten").fill_null(False).sum()),
        low_confidence=int((areas.get_column("wahrscheinlichkeit") < LOW_CONFIDENCE).sum()),
        groups=(
            group("Rat und Ausschüsse", council),
            group("Bezirksvertretungen", district),
            group("Beiräte und ohne erkanntes Gremium", rest),
        ),
        areas=rows,
        columns=tuple((code, SHORT_NAMES[code]) for code in ordered),
        fractions=fractions,
        districts=tuple(sorted(districts, key=lambda r: int(r.key))),
        district_documents=with_hit,
    )


# --- Register: Schalter, Eingaben, Daten, Links ---------------------------------------------------
def _with_fractions(settings: Settings) -> bool:
    from georep.enrich.functions import functions_enabled

    return functions_enabled(settings)


def themes_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """Was ``page_themen`` liest: die Politikfelder, Gremien, Antragsteller, Treffer, Prüfung."""
    from georep.enrich.functions import functions_files

    return (
        policy_area_files(layout).areas,
        layout.papers_bodies,
        *((functions_files(layout).cosponsors,) if _with_fractions(settings) else ()),
        layout.results,
        # Option 02: eine Periode mit Crosswalk rechnet auf den Wahlbezirken der Hauptperiode, und
        # ihre Namen kommen aus deren Stimmbezirken (wie Karte und Bezirkstabelle der Auswertung)
        layout.target_view(settings).precincts_geojson,
        *check_files(settings),
    )


def read_inputs(layout: Layout, settings: Settings) -> ThemesInputs:
    """Die Dateien der Seite aus dem Layout."""
    from georep.enrich.functions import functions_files
    from georep.geo import read_canonical_precincts
    from georep.report.model import district_names

    precincts = read_canonical_precincts(
        layout.target_view(settings).precincts_geojson, settings.geo.working_crs
    )
    return ThemesInputs(
        areas=pl.read_parquet(policy_area_files(layout).areas),
        bodies=pl.read_parquet(layout.papers_bodies, columns=["id", "gremium_art"]),
        cosponsors=(
            pl.read_parquet(functions_files(layout).cosponsors, columns=["id", "fraktionen"])
            if _with_fractions(settings)
            else None
        ),
        results=pl.read_parquet(layout.results, columns=["wahlkreis_id", "paper_ids"]),
        district_names=district_names(precincts),
    )


def repository_links(settings: Settings) -> dict[str, str]:
    """Messdokument, Codebuch, README der Prüfung; Vorlage und Allowlist lesen dieselben."""
    from georep.report.render import REPOSITORY

    folder = settings.validation.root.name
    return {
        "measurement": f"{REPOSITORY}/blob/main/{MEASUREMENT}",
        "codebook": f"{REPOSITORY}/blob/main/{folder}/{VALIDATION_PROJECT}/codebuch.toml",
        "check": f"{REPOSITORY}/blob/main/{folder}/{VALIDATION_PROJECT}/README.md",
        "license": CC_BY_NC_SA,
        "cap": CAP_SITE,
        "cap_germany": CAP_GERMANY,
        "doi": CAP_DOI,
    }


def themes_data(layout: Layout, settings: Settings) -> Mapping[str, object]:
    """``Page.data``: die Dateien lesen, das Modell bauen."""
    from georep.report.actors import labels_of

    model = build_themes(
        read_inputs(layout, settings), settings, read_check(settings), labels_of(settings)[0]
    )
    return {
        "themen": model,
        "urls": repository_links(settings),
        "min_documents": MIN_DOCUMENTS,
        "low_confidence": LOW_CONFIDENCE,
        "bundestag_source": BUNDESTAG_SOURCE,
        "bundestag_total": BUNDESTAG_TOTAL,
        "attribution": CAP_ATTRIBUTION,
    }


def themes_links(layout: Layout, settings: Settings) -> frozenset[str]:
    """Die Links nach außen: Repository-Dateien, Lizenz, die Seiten des CAP."""
    return frozenset(repository_links(settings).values())
