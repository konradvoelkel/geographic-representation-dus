"""Die Unterseite ``akteure.html``: Funktionen, Instrumente je Fraktion, wer mit wem (Vorhaben 15).

Stufe 3 von Vorhaben 15 (Messdokument ``docs/plans/15-funktion.md``, § 7 und § 10, Punkt 8), die
erste Unterseite nach F2 (Punkt 69). Fünf Abschnitte, **für alle Fraktionen gleich gebaut**:

1. *Funktionen der Dokumente*: je Urheberklasse eine gestapelte Leiste über die sechs Klassen, dazu
   die Tabelle der Zahlen und die Instrumente;
2. *Instrumente je Fraktion*: Dokumente, davon gemeinsam, Kontrolle, Initiative, Erklärung, der
   Kontrollanteil roh und **beobachtet gegen erwartet** gegen die Praxis der Gremien
   (``analysis.practice``), „explorativ"; unter ``MIN_DOCUMENTS`` Dokumenten kein Verhältnis;
3. *Wer mit wem*: je Ebene (Rat und Ausschüsse, Bezirksvertretungen) eine Matrix Fraktion ×
   Fraktion mit den gemeinsamen Dokumenten; nur auf der Ebene, auf der die Ratsmehrheit gilt,
   tragen die Zellen ein Lager;
4. *Konkordanz*: K3 (wie oft trägt eine Fraktion der Mehrheit eine Initiative mit, an der die
   Opposition beteiligt ist) mit Wilson-Intervall und n, die Mehrheiten mit ihrer Quelle, die
   Dokumente über die Grenze; nur, wenn das Profil eine Mehrheit kennt;
5. *Erklärungen und Appelle*: die Klasse ``erklaerung`` als Liste, ohne Rangfolge je Fraktion,
   mit ihrer Definition wörtlich aus dem Codebuch (dort heißt sie ``symbol``; Konrad, 2026-11-27:
   kein Leser sieht das Wort „Symbolpolitik", es ist wertend).

Die Prüfung steht oben auf der Seite: der Satz und die Übereinstimmung der Kodierer aus
``guete.json`` (F4, Punkt 87), die Treffer des Regelwerks gegen die Labels aus ``RULE_CHECK``. Ein
Datensatz, an dem nicht gemessen ist, heißt auf der ganzen Seite „explorativ"
(``docs/plan-zeigen-2026-11.md``, § 8). Was einem Profil fehlt, sagt die Seite (§ 6).

Rein bis auf ``actors_data`` und ``read_check``, die die Dateien lesen; kein Stadtwort, keine
Partei im Code: Namen und Mehrheiten kommen aus den Settings.
"""

from __future__ import annotations

import datetime as dt
import itertools
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import deal
import polars as pl

from georep.analysis.cosponsors import (
    ACROSS,
    ALONE_OPPOSITION,
    JOINT_MAJORITY,
    JOINT_OPPOSITION,
    NO_CAMP,
    NO_PARTY,
    camp,
    fractions_on,
)
from georep.analysis.functions import STATEMENT
from georep.analysis.parties import URHEBER_ARTEN
from georep.analysis.practice import RATIO, observed_expected
from georep.errors import MissingInputError, SchemaError
from georep.layout import Layout
from georep.prep.bodies import KIND_LABELS, BodyRules
from georep.settings import (
    CODEBOOK_FUNCTIONS,
    FUNCTION_CLASSES,
    Fraction,
    Majorities,
    Settings,
    load_settings,
    profile_folder,
)
from georep.validation.codebook import load_codebook
from georep.validation.measures import wilson_interval

PAGE_NAME = "akteure"
VALIDATION_PROJECT = "15-funktion-f4"  # der Ordner unter ``validation.root`` mit ``guete.json``
MIN_DOCUMENTS = 30  # darunter kein Verhältnis je Fraktion (Messdokument § 7, Abschnitt 2)
MANY_FRACTIONS = 4  # „Allparteienantrag": mindestens so viele Fraktionen (Messdokument § 3.11)
POLITICAL = ("kontrolle", "initiative", STATEMENT)  # die Funktionen der Fraktionsdokumente
# K3 zählt Initiativen (Anfragen stellt man selten gemeinsam)
INITIATIVES = ("initiative", STATEMENT)
DISTRICT_LEVEL = "bezirksvertretung"  # die Gremienart der zweiten Matrix
OPPOSITION_TAKES_PART = (ALONE_OPPOSITION, JOINT_OPPOSITION, ACROSS)
# Das Lager eines Paars zweier Fraktionen; ``camp`` gibt für zwei verschiedene genau eines davon.
PAIR_CAMPS = (JOINT_MAJORITY, ACROSS, JOINT_OPPOSITION)

# Die Funktionen in Worten: lang im Text, kurz in Leisten, Legenden und Spalten (Konrad, 2026-11-27).
FUNCTION_LABELS: dict[str, str] = {
    "kontrolle": "Kontrolle",
    "information": "Information",
    "initiative": "Initiative",
    STATEMENT: "Erklärung oder Appell",
    "vollzug": "Vollzug",
    "rest": "Funktion nicht erkannt",  # Messdokument § 4.2: kein Dokument ohne Funktion
}
FUNCTION_SHORT: dict[str, str] = FUNCTION_LABELS | {STATEMENT: "Erklärung/Appell"}
# Die Instrumente aus ``settings.FUNCTION_INSTRUMENTS`` in Worten; ein Test hält beide gleich.
INSTRUMENT_LABELS: dict[str, str] = {
    "anfrage": "Anfrage",
    "nachfrage": "Nachfrage",
    "berichtsantrag": "Berichtsantrag",
    "informationsvorlage": "Informationsvorlage",
    "berichtsvorlage": "Berichtsvorlage",
    "antrag": "Antrag",
    "aenderungsantrag": "Änderungs- oder Ergänzungsantrag",
    "haushaltsantrag": "Haushaltsantrag",
    "pruefauftrag": "Prüfauftrag",
    "eingabe": "Eingabe von Bürgerinnen und Bürgern",
    "resolution": "Resolution, Appell (aus dem Titel)",
    "erklaerung_text": "Erklärung im Beschlusstext",
    "beschlussvorlage": "Beschlussvorlage",
    "satzung": "Satzung, Ordnung",
    "haushalt": "Haushalt, Abschlüsse, Wirtschaftspläne",
    "bauleitplanung": "Bauleitplanung",
    "besetzung": "Wahl, Bestellung, Besetzung",
    "dringlichkeit": "Dringlichkeitsentscheidung",
    "bau": "Bauvorhaben",
    "rechnungspruefung": "Rechnungsprüfung",
    "sammelart_ohne_merkmal": "Sammelart ohne Merkmal in Titel und Textkopf",
    "art_unbekannt": "Dokumentart ohne Eintrag in den Tabellen",
}
# Die Urheberklassen (Option 04) als Leisten; dieselbe Folge wie ``URHEBER_ARTEN``.
ORIGINATOR_LABELS: dict[str, str] = {
    "Verwaltung": "Verwaltung",
    "Fraktion": "Fraktionen",
    "Person": "einzelne Mandatsträger",
    "Eingabe": "Eingaben von Bürgerinnen und Bürgern",
    "unbekannt": "Urheber nicht erkannt",
}
CAMP_LABELS: dict[str, str] = {
    JOINT_MAJORITY: "beide in der Mehrheit",
    ACROSS: "über die Grenze",
    JOINT_OPPOSITION: "beide in der Opposition",
}
# Ein sichtbares Kürzel je Lager in der Zelle (Review 2026-11-27, K2): die drei Tönungen sind unter
# Rot-Grün-Schwäche nicht sicher zu trennen, die Farbe trägt das Lager also nicht allein.
CAMP_SHORT: dict[str, str] = {JOINT_MAJORITY: "M", ACROSS: "Ü", JOINT_OPPOSITION: "O"}
DOCUMENT_COLUMNS = (
    "id",
    "name",
    "reference",
    "date",
    "download_url",
    "funktion",
    "instrument",
    "antragsteller",
    "fraktionen",
    "gemeinsam",
    "lager",
    "urheber_art",
    "parteien",
    "gremium",
    "gremium_art",
    "stadtbezirk",
)


# --- Die Prüfung (F4, Punkt 87) ------------------------------------------------------------------
@dataclass(frozen=True)
class VariantCheck:
    """Das Regelwerk einer Variante gegen die Labels: Treffer, κ mit Bootstrap-95-%-Intervall."""

    hits: int
    basis: int  # Dokumente, denen das Regelwerk eine Funktion gibt und das Label nicht „unklar"
    kappa: float
    interval: tuple[float, float]


@dataclass(frozen=True)
class RuleCheck:
    """Was ``guete.json`` nicht trägt: das Regelwerk gegen die Endlabels (Messdokument § 4.1).

    ``guete.json`` beschreibt die Kodierung (Satz, Modelle, Übereinstimmung der Kodierer); wie oft
    das Regelwerk mit den Labels übereinstimmt, rechnet das Messskript, und der slow-Test
    ``tests/golden/test_functions_numbers.py`` rechnet Treffer und κ aus
    ``validierung/15-funktion/labels.csv`` gegen diese Konstante nach. Das Intervall ist der
    Perzentil-Bootstrap des Messskripts (2 000 Ziehungen, Seed 15).
    """

    variants: Mapping[str, VariantCheck]
    fraction_hits: int  # Fraktionen, die Regelwerk und Label beide nennen
    fraction_named: int  # Fraktionen, die das Regelwerk nennt (Präzision)
    fraction_labelled: int  # Fraktionen, die die Labels nennen (Recall)
    # Die Variante, die an denselben Labels gewählt ist, an denen sie gemessen ist (§ 5): ihre Zahl
    # ist optimistisch, die der anderen die vorsichtige (Synergien § 10, Punkt 8).
    selected_on_labels: str
    # Die Kodierung, an der diese Zahlen gemessen sind; ``read_check`` vergleicht sie mit
    # ``guete.json`` (Review 2026-11-27, N1): eine neue Kodierung macht die Konstante ungültig.
    codebook_version: str
    units: int


RULE_CHECK = RuleCheck(
    variants={
        "B": VariantCheck(125, 135, 0.905, (0.840, 0.960)),
        "A": VariantCheck(117, 135, 0.829, (0.748, 0.900)),
    },
    fraction_hits=119,
    fraction_named=119,
    fraction_labelled=138,
    selected_on_labels="B",
    codebook_version="2026-11-23.1",
    units=150,
)


@dataclass(frozen=True)
class Check:
    """Der Prüfsatz der Seite: aus ``guete.json``, dazu ``RULE_CHECK`` für die gebaute Variante."""

    sentence: str  # ``satz`` aus ``guete.json``: Modelle, Einheiten, „nicht von Menschen"
    agreed: int  # Kodierer A und B gleich bei ``funktion``
    units: int
    same_model: (
        bool  # Kodierer A und B dasselbe Modell: ihre Übereinstimmung ist ein schwacher Beleg
    )
    variant: str
    chosen: VariantCheck
    other_variant: str
    other: VariantCheck
    fraction_hits: int
    fraction_named: int
    fraction_labelled: int
    selected_on_labels: str
    measured: bool  # dieser Datensatz gehört zur Stichprobe; sonst ist die ganze Seite explorativ
    measured_profiles: tuple[
        str, ...
    ]  # die Profile der Stichprobe, wie ``stichprobe.json`` sie nennt
    statement_definition: str  # die Definition der Klasse ``erklaerung``, wörtlich aus dem Codebuch
    measured_datasets: tuple[str, ...]  # Stadt und Periode je Profil der Stichprobe (Review N5)


def check_files(settings: Settings) -> tuple[Path, Path, Path]:
    """``guete.json``, ``stichprobe.json`` und ``codebuch.toml`` im Repo unter ``validation.root``."""
    folder = settings.validation.root / VALIDATION_PROJECT
    return folder / "guete.json", folder / "stichprobe.json", folder / "codebuch.toml"


def statement_definition(codebook_path: Path) -> str:
    """Die Definition der Klasse ``erklaerung`` aus dem Codebuch, wo sie ``symbol`` heißt."""
    codebook = load_codebook(codebook_path, VALIDATION_PROJECT)
    names = {data: label for label, data in CODEBOOK_FUNCTIONS.items()}
    try:
        question = codebook.question("funktion")
        option = next(o for o in question.options if o.value == names.get(STATEMENT, STATEMENT))
    except (KeyError, StopIteration) as error:
        raise SchemaError(f"{codebook_path}: keine Option für {STATEMENT}") from error
    return option.definition.strip()


def _profile_folders(names: Sequence[str]) -> set[str]:
    """Die Ordner unter ``data_root`` der Profile; ein unbekanntes Profil zählt nicht."""
    found: set[str] = set()
    for name in names:
        try:
            found.add(profile_folder(name))
        except OSError, ValueError, SchemaError:
            continue
    return found


def _dataset_name(profile: str) -> str:
    """„Stadt, Wahlperiode …" eines Paketprofils; ein unbekanntes bleibt sein Name."""
    from georep.report.model import period_info

    try:
        settings = load_settings(profile=profile, cwd=Path("/nonexistent"))
    except OSError, ValueError, SchemaError:
        return profile
    return f"{settings.city.name}, {period_info(settings).title}"


@deal.raises(MissingInputError, SchemaError)
def read_check(settings: Settings, rule: RuleCheck = RULE_CHECK) -> Check:
    """Der Prüfsatz aus ``guete.json`` und ``stichprobe.json``; ``SchemaError`` bei fehlendem Feld.

    Gemessen ist ein Datensatz, wenn sein Ordner (``settings.profile``) der Ordner eines der
    Profile ist, aus denen die Stichprobe gezogen ist: das Vergleichsprofil rechnet im Ordner der
    Hauptperiode und ist damit gemessen, eine zweite Stadt nicht.
    """
    quality_path, sample_path, codebook_path = check_files(settings)
    for path in (quality_path, sample_path, codebook_path):
        if not path.is_file():
            raise MissingInputError(f"{path} fehlt; die Seite {PAGE_NAME}.html nennt ihre Prüfung")
    quality: dict[str, Any] = json.loads(quality_path.read_text(encoding="utf-8"))
    sample: dict[str, Any] = json.loads(sample_path.read_text(encoding="utf-8"))
    try:
        sentence = str(quality["satz"])
        models = dict(quality["modelle"])
        function = dict(quality["fragen"]["funktion"])
        agreed, units = int(function["einig"]), int(function["n"])
        profiles = tuple(p.strip() for p in str(sample["profil"]).split(",") if p.strip())
        measured_on = (str(quality["codebuch_version"]), int(quality["einheiten"]))
    except (KeyError, TypeError, ValueError) as error:
        raise SchemaError(f"{quality_path} oder {sample_path}: Feld fehlt ({error})") from error
    if measured_on != (rule.codebook_version, rule.units):
        raise SchemaError(
            f"{quality_path}: Codebuch {measured_on[0]} an {measured_on[1]} Einheiten, RULE_CHECK "
            f"gilt für {rule.codebook_version} an {rule.units}; das Regelwerk ist gegen die neue "
            "Kodierung nachzurechnen"
        )
    variant = settings.functions.variant
    other = "A" if variant == "B" else "B"
    return Check(
        sentence=sentence,
        agreed=agreed,
        units=units,
        same_model=models.get("kodierer_a") == models.get("kodierer_b"),
        variant=variant,
        chosen=rule.variants[variant],
        other_variant=other,
        other=rule.variants[other],
        fraction_hits=rule.fraction_hits,
        fraction_named=rule.fraction_named,
        fraction_labelled=rule.fraction_labelled,
        selected_on_labels=rule.selected_on_labels,
        measured=settings.profile in _profile_folders(profiles),
        measured_profiles=profiles,
        statement_definition=statement_definition(codebook_path),
        measured_datasets=tuple(_dataset_name(p) for p in profiles),
    )


# --- Abschnitt 1: Funktionen ---------------------------------------------------------------------
@dataclass(frozen=True)
class Segment:
    """Ein Stück einer Leiste; ``x`` und ``width`` als Anteil 0 bis 1 der ganzen Leiste."""

    function: str
    label: str
    count: int
    share: float
    x: float
    width: float


@dataclass(frozen=True)
class FunctionBar:
    """Eine Urheberklasse über die sechs Funktionen."""

    originator: str
    label: str
    total: int
    segments: tuple[Segment, ...]  # nur Funktionen mit mindestens einem Dokument


@dataclass(frozen=True)
class FunctionRow:
    """Eine Zeile der Tabelle zu den Leisten: eine Funktion, je Urheberklasse die Dokumente."""

    function: str
    label: str
    counts: tuple[int, ...]  # in der Folge von ``FunctionTable.originators``
    total: int


@dataclass(frozen=True)
class FunctionTable:
    originators: tuple[tuple[str, str], ...]  # (Klasse, Bezeichnung), nur Klassen mit Dokumenten
    rows: tuple[FunctionRow, ...]
    totals: tuple[int, ...]
    documents: int


@dataclass(frozen=True)
class InstrumentRow:
    function: str
    function_label: str
    instrument: str
    label: str
    count: int
    share: float  # Anteil an den Dokumenten der Funktion


def _bars_partition(documents: pl.DataFrame, result: tuple[FunctionBar, ...] | None = None) -> bool:
    """Jede Leiste summiert zu ihrer Klasse, und alle zusammen zum Korpus."""
    assert result is not None
    return sum(b.total for b in result) == documents.height and all(
        sum(s.count for s in b.segments) == b.total
        and abs(sum(s.width for s in b.segments) - 1.0) < 1e-9
        for b in result
    )


@deal.ensure(_bars_partition, message="jede Leiste summiert zu ihrer Klasse, alle zum Korpus")
def function_bars(documents: pl.DataFrame) -> tuple[FunctionBar, ...]:
    """Je Urheberklasse mit Dokumenten eine Leiste, die Funktionen in fester Folge."""
    counts = {
        (str(art), str(function)): int(n)
        for art, function, n in documents.group_by("urheber_art", "funktion").len().iter_rows()
    }
    bars = []
    for art in URHEBER_ARTEN:
        total = sum(n for (a, _), n in counts.items() if a == art)
        if not total:
            continue
        segments, x = [], 0.0
        for function in FUNCTION_CLASSES:
            n = counts.get((art, function), 0)
            if n:
                segments.append(
                    Segment(function, FUNCTION_SHORT[function], n, n / total, x, n / total)
                )
                x += n / total
        bars.append(FunctionBar(art, ORIGINATOR_LABELS[art], total, tuple(segments)))
    return tuple(bars)


def function_table(documents: pl.DataFrame) -> FunctionTable:
    """Die Zahlen der Leisten als Tabelle: Funktion × Urheberklasse (die Tabellensicht)."""
    counts = Counter(
        (str(art), str(function))
        for art, function in documents.select("urheber_art", "funktion").iter_rows()
    )
    arts = tuple(a for a in URHEBER_ARTEN if any(k[0] == a for k in counts))
    rows = tuple(
        FunctionRow(
            function,
            FUNCTION_SHORT[function],
            tuple(counts.get((a, function), 0) for a in arts),
            sum(counts.get((a, function), 0) for a in arts),
        )
        for function in FUNCTION_CLASSES
    )
    totals = tuple(sum(counts.get((a, f), 0) for f in FUNCTION_CLASSES) for a in arts)
    return FunctionTable(
        tuple((a, ORIGINATOR_LABELS[a]) for a in arts), rows, totals, documents.height
    )


def instruments(documents: pl.DataFrame) -> tuple[InstrumentRow, ...]:
    """Je Funktion ihre Instrumente, nach Dokumenten absteigend; die Folge der Funktionen ist fest."""
    counts = Counter(
        (str(f), str(i)) for f, i in documents.select("funktion", "instrument").iter_rows()
    )
    per_function = Counter(f for f, _ in counts.elements())
    rows: list[InstrumentRow] = []
    for function in FUNCTION_CLASSES:
        found = sorted(
            ((i, n) for (f, i), n in counts.items() if f == function), key=lambda x: (-x[1], x[0])
        )
        rows.extend(
            InstrumentRow(
                function,
                FUNCTION_SHORT[function],
                instrument,
                INSTRUMENT_LABELS.get(instrument, instrument),
                n,
                n / per_function[function],
            )
            for instrument, n in found
        )
    return tuple(rows)


# --- Abschnitt 2: Instrumente je Fraktion ---------------------------------------------------------
@dataclass(frozen=True)
class FractionRow:
    key: str
    label: str
    documents: int  # Fraktionsdokumente der Funktionen Kontrolle, Initiative und Erklärung
    joint: int
    control: int
    initiative: int
    statement: int
    control_share: float  # roh: Kontrolle durch Dokumente
    ratio: (
        float | None
    )  # beobachtet durch erwartet; None unter ``MIN_DOCUMENTS`` oder ohne Erwartung


@dataclass(frozen=True)
class SplitFraction:
    """Eine Partei allein neben der Fraktion, zu der sie erst ab einem Tag gehört (Review N2).

    In der Hauptperiode stehen „SPD" (bis zum 31.10.2020, Fraktion des alten Rates) und „SPD/Volt"
    (ab dem 01.11.2020) als zwei Zeilen da; ohne Satz sähe das wie eine doppelte Fraktion aus.
    """

    alone: str
    joint: str
    since: dt.date
    documents: int  # Fraktionsdokumente der Partei allein, alle vor ``since``


def split_fractions(
    documents: pl.DataFrame, rows: Sequence[FractionRow], settings: Settings
) -> tuple[SplitFraction, ...]:
    """Je Fraktion aus mehreren Parteien, deren Partei allein vor ihrem Beginn Zeilen hat."""
    by_key = {r.key: r for r in rows}
    found = []
    for fraction in settings.functions.fractions:
        if fraction.key not in by_key:
            continue
        for party in fraction.parties:
            if party not in by_key:
                continue
            dates = (
                _political_fraction_documents(documents)
                .filter(pl.col("fraktionen").list.contains(party))
                .get_column("date")
                .drop_nulls()
            )
            latest = dates.max()
            if isinstance(latest, dt.date) and latest < fraction.valid_from:
                found.append(
                    SplitFraction(
                        by_key[party].label,
                        by_key[fraction.key].label,
                        fraction.valid_from,
                        by_key[party].documents,
                    )
                )
    return tuple(found)


@dataclass(frozen=True)
class PracticeRow:
    """Der Kontrollanteil der Fraktionsdokumente je Gremienart: die Praxis, gegen die gemessen wird."""

    kind: str
    label: str
    documents: int
    share: float


@dataclass(frozen=True)
class CountingDifference:
    """Frage 25: diese Seite zählt Antragsteller, die Hauptseite ``parteien`` (erste Quelle)."""

    documents: int  # Fraktionsdokumente
    different: int
    more: int  # die Antragsteller nennen mehr Parteien
    fewer: int
    other: int  # gleich viele, aber andere


def _political_fraction_documents(documents: pl.DataFrame) -> pl.DataFrame:
    return documents.filter(
        (pl.col("urheber_art") == "Fraktion")
        & pl.col("funktion").is_in(POLITICAL)
        & (pl.col("fraktionen").list.len() > 0)
    )


def fraction_rows(documents: pl.DataFrame, labels: Mapping[str, str]) -> tuple[FractionRow, ...]:
    """Je Fraktion die Instrumente und die Kontrolle gegen die Praxis der Gremien (explorativ).

    Ein gemeinsames Dokument zählt für jede beteiligte Fraktion. „Erwartet" ist die Summe der
    Kontrollanteile des Gremiums über die Dokumente der Fraktion (``observed_expected``, Schicht
    das Gremium; ein Dokument ohne Gremium bildet eine eigene Schicht). Sortiert nach Dokumenten
    absteigend, bei Gleichstand nach Bezeichnung: dieselbe Regel für jede Fraktion.
    """
    political = _political_fraction_documents(documents).with_columns(
        (pl.col("funktion") == "kontrolle").alias("kontrolle")
    )
    if political.is_empty():
        return ()
    ratios = observed_expected(
        political.select("fraktionen", "kontrolle", "gremium"),
        unit="fraktionen",
        outcome="kontrolle",
        strata=("gremium",),
    )
    ratio_of = {str(k): r for k, r in ratios.select("fraktionen", RATIO).iter_rows()}
    counts = (
        political.explode("fraktionen")
        .group_by("fraktionen")
        .agg(
            pl.len().alias("n"),
            pl.col("gemeinsam").sum().alias("joint"),
            (pl.col("funktion") == "kontrolle").sum().alias("control"),
            (pl.col("funktion") == "initiative").sum().alias("initiative"),
            (pl.col("funktion") == STATEMENT).sum().alias("statement"),
        )
    )
    rows = [
        FractionRow(
            key=str(key),
            label=labels.get(str(key), str(key)),
            documents=int(n),
            joint=int(joint),
            control=int(control),
            initiative=int(initiative),
            statement=int(statement),
            control_share=int(control) / int(n),
            ratio=ratio_of.get(str(key)) if int(n) >= MIN_DOCUMENTS else None,
        )
        for key, n, joint, control, initiative, statement in counts.iter_rows()
    ]
    return tuple(sorted(rows, key=lambda r: (-r.documents, r.label)))


def practice_rows(documents: pl.DataFrame) -> tuple[PracticeRow, ...]:
    """Der Kontrollanteil der Fraktionsdokumente (Kontrolle, Initiative, Erklärung) je Gremienart."""
    political = _political_fraction_documents(documents)
    found = (
        political.with_columns(pl.col("gremium_art").fill_null("unbekannt"))
        .group_by("gremium_art")
        .agg(pl.len().alias("n"), (pl.col("funktion") == "kontrolle").mean().alias("share"))
    )
    rows = {str(kind): (int(n), float(share)) for kind, n, share in found.iter_rows()}
    # Review N7: „unbekannt" allein liest sich in der Aufzählung wie ein Gremium dieses Namens
    labels = KIND_LABELS | {"unbekannt": "Gremium unbekannt"}
    return tuple(
        PracticeRow(kind, labels[kind], *rows[kind]) for kind in KIND_LABELS if kind in rows
    )


def counting_difference(documents: pl.DataFrame) -> CountingDifference:
    """Wie oft die Antragsteller dieser Seite andere Parteien nennen als ``parteien``."""
    fraction = documents.filter(pl.col("urheber_art") == "Fraktion")
    more = fewer = other = 0
    for named, first in fraction.select("antragsteller", "parteien").iter_rows():
        a, b = set(named or ()), set(first or ())
        if a == b:
            continue
        if len(a) > len(b):
            more += 1
        elif len(a) < len(b):
            fewer += 1
        else:
            other += 1
    return CountingDifference(fraction.height, more + fewer + other, more, fewer, other)


# --- Abschnitt 3: Wer mit wem ----------------------------------------------------------------------
@dataclass(frozen=True)
class Cell:
    count: int
    camp: str | None  # das häufigste Lager des Paars; None ohne Mehrheit oder ohne Dokument
    camps: tuple[tuple[str, int], ...]  # alle Lager mit Zahl, wenn es mehr als eines gibt


@dataclass(frozen=True)
class Matrix:
    """Die gemeinsamen Dokumente je Paar von Fraktionen auf einer Ebene; symmetrisch."""

    key: str  # Anker und Wert des Umschalters
    label: str
    label_dative: str  # „in Rat und Ausschüssen"
    fractions: tuple[tuple[str, str], ...]  # (Schlüssel, Bezeichnung): Zeilen und Spalten
    cells: tuple[tuple[Cell | None, ...], ...]  # None auf der Diagonale
    joint: tuple[int, ...]  # je Fraktion ihre gemeinsamen Dokumente auf dieser Ebene
    documents: int  # gemeinsame Dokumente auf dieser Ebene
    with_camps: bool
    mixed: tuple[
        tuple[str, str, tuple[tuple[str, int], ...]], ...
    ]  # Paare mit mehr als einem Lager


@dataclass(frozen=True)
class MajorityContext:
    """Was ein Lager braucht: Mehrheiten, Fraktionen aus mehreren Parteien, die Folge der Parteien."""

    majorities: Majorities
    fractions: tuple[Fraction, ...]
    order: Mapping[str, int]

    def majority_on(self, day: dt.date | None) -> tuple[str, ...] | None:
        term = self.majorities.on(day)
        if term is None:
            return None
        return fractions_on(term.parties, day, self.fractions, self.order)


def fraction_axis(
    documents: pl.DataFrame, labels: Mapping[str, str]
) -> tuple[tuple[str, str], ...]:
    """Die Fraktionen der Fraktionsdokumente, nach Dokumenten absteigend, dann nach Bezeichnung."""
    counts = Counter(
        str(f)
        for fractions in documents.filter(pl.col("urheber_art") == "Fraktion")
        .get_column("fraktionen")
        .to_list()
        for f in fractions or ()
    )
    keys = sorted(counts, key=lambda k: (-counts[k], labels.get(k, k)))
    return tuple((k, labels.get(k, k)) for k in keys)


def _matrix_is_symmetric(result: Matrix) -> bool:
    n = len(result.fractions)
    return len(result.cells) == n and all(
        len(row) == n
        and row[i] is None
        and all(
            (c is None) == (i == j)
            and (c is None or (other := result.cells[j][i]) is None or other.count == c.count)
            for j, c in enumerate(row)
        )
        for i, row in enumerate(result.cells)
    )


@deal.post(_matrix_is_symmetric, message="symmetrisch, die Diagonale leer")
def cosponsor_matrix(
    documents: pl.DataFrame,
    axis: Sequence[tuple[str, str]],
    *,
    key: str,
    kinds: Sequence[str],
    context: MajorityContext | None,
) -> Matrix:
    """Die gemeinsamen Dokumente der Gremienarten ``kinds`` je Paar; Lager nur mit ``context``.

    Das Lager eines Paars kommt je Dokument aus der Mehrheit an dessen Datum (``camp`` mit genau
    den beiden Fraktionen): ein Dokument von vier Fraktionen über die Grenze ist für das Paar
    zweier Mehrheitsfraktionen darin „beide in der Mehrheit". Wechselt die Mehrheit im Datensatz,
    kann ein Paar zwei Lager haben; die Zelle trägt das häufigere, ``mixed`` nennt alle.
    """
    keys = [k for k, _ in axis]
    position = {k: i for i, k in enumerate(keys)}
    joint = documents.filter(pl.col("gemeinsam") & pl.col("gremium_art").is_in(list(kinds)))
    counts: Counter[tuple[str, str]] = Counter()
    camps: dict[tuple[str, str], Counter[str]] = {}
    per_fraction: Counter[str] = Counter()
    for fractions, day in joint.select("fraktionen", "date").iter_rows():
        present = sorted(
            {str(f) for f in fractions or () if f in position}, key=position.__getitem__
        )
        per_fraction.update(present)
        majority = context.majority_on(day) if context is not None else None
        for a, b in itertools.combinations(present, 2):
            counts[(a, b)] += 1
            if majority is not None:
                camps.setdefault((a, b), Counter())[camp([a, b], majority)] += 1
    cells: list[tuple[Cell | None, ...]] = []
    mixed: list[tuple[str, str, tuple[tuple[str, int], ...]]] = []
    for a in keys:
        row: list[Cell | None] = []
        for b in keys:
            if a == b:
                row.append(None)
                continue
            pair = (a, b) if position[a] < position[b] else (b, a)
            found = camps.get(pair, Counter())
            ordered = tuple(sorted(found.items(), key=lambda x: (-x[1], PAIR_CAMPS.index(x[0]))))
            row.append(
                Cell(
                    counts[pair],
                    ordered[0][0] if ordered else None,
                    ordered if len(ordered) > 1 else (),
                )
            )
            if len(ordered) > 1 and position[a] < position[b]:
                mixed.append((a, b, ordered))
        cells.append(tuple(row))
    label, label_dative = _level_label(kinds)
    return Matrix(
        key=key,
        label=label,
        label_dative=label_dative,
        fractions=tuple(axis),
        cells=tuple(cells),
        joint=tuple(per_fraction[k] for k in keys),
        documents=joint.height,
        with_camps=context is not None and bool(camps),
        mixed=tuple(mixed),
    )


# --- Abschnitt 4 und 5: Konkordanz, Resolutionen -------------------------------------------------
@dataclass(frozen=True)
class DocumentRow:
    """Ein Dokument einer Liste: Datum, Drucksache mit Link, Titel, Antragsteller, Gremium."""

    date: dt.date | None
    reference: str
    title: str
    url: str  # die PDF-Datei im Ratsinformationssystem; leer ohne
    authors: str  # die Fraktionen in Worten, sonst die Urheberklasse
    fractions: int
    body: str
    instrument: str


@dataclass(frozen=True)
class Share:
    """Ein Anteil mit Wilson-95-%-Intervall."""

    hits: int
    n: int

    @property
    def share(self) -> float:
        return self.hits / self.n if self.n else 0.0

    @property
    def interval(self) -> tuple[float, float]:
        return wilson_interval(self.hits, self.n) if self.n else (0.0, 0.0)


@dataclass(frozen=True)
class Evidence:
    reference: str
    url: str  # leer, wenn die Drucksache nicht in diesem Datensatz liegt


@dataclass(frozen=True)
class MajorityRow:
    """Eine Ratsmehrheit, die im Datensatz gilt, mit ihrer Quelle."""

    period: str
    parties: str  # in Worten
    valid_from: dt.date
    valid_to: dt.date | None
    agreement: str
    agreement_date: str
    evidence: tuple[Evidence, ...]
    documents: (
        int  # Fraktionsdokumente dieses Datensatzes in den Gremien der Mehrheit, in ihrer Zeit
    )


@dataclass(frozen=True)
class Concordance:
    """K3 in Rat und Ausschüssen (Messdokument § 3.11), die Mehrheiten und die Dokumente über die Grenze."""

    initiatives: Share  # K3: über die Grenze / Initiativen mit Beteiligung der Opposition
    all_functions: Share  # dasselbe über Kontrolle, Initiative und Erklärung
    majorities: tuple[MajorityRow, ...]
    across: tuple[DocumentRow, ...]  # alle Dokumente über die Grenze, nach Datum
    many: int  # davon mit mindestens ``MANY_FRACTIONS`` Fraktionen
    level: str  # die Gremien, in denen die Mehrheit gilt, in Worten („Rat und Ausschüsse")
    level_dative: str  # dieselben im Dativ („in Rat und Ausschüssen")


def _https(url: str | None) -> str:
    if not url:
        return ""
    return "https://" + url[len("http://") :] if url.startswith("http://") else url


def _authors(row: Mapping[str, Any], labels: Mapping[str, str]) -> str:
    fractions = [str(f) for f in row["fraktionen"] or ()]
    if fractions:
        return ", ".join(labels.get(f, f) for f in fractions)
    if row["urheber_art"] == "Fraktion":
        return "Fraktion nicht erkannt"  # Review N5: eine Fraktion ohne Namen, nicht „Fraktionen"
    return ORIGINATOR_LABELS.get(str(row["urheber_art"]), str(row["urheber_art"]))


def body_name(row: Mapping[str, Any], rules: BodyRules) -> str:
    """Das Gremium beim Namen aus ``[bodies]``, sonst sein Kürzel (Review N5), wie die Hauptseite."""
    code = str(row["gremium"] or "")
    if row["gremium_art"] == DISTRICT_LEVEL:
        named = rules.district_body_names.get(code)
        if named:
            return named
        if row.get("stadtbezirk") is not None:
            return rules.district_body_name.format(n=row["stadtbezirk"])
        return code
    return rules.names.get(code) or code or "Gremium nicht erkannt"


def document_rows(
    documents: pl.DataFrame, labels: Mapping[str, str], rules: BodyRules
) -> tuple[DocumentRow, ...]:
    """Die Dokumente als Zeilen einer Liste, nach Datum, dann Drucksache (fest in jeder Folge)."""
    rows = [
        DocumentRow(
            date=row["date"],
            reference=str(row["reference"] or ""),
            title=str(row["name"] or ""),
            url=_https(row["download_url"]),
            authors=_authors(row, labels),
            fractions=len(row["fraktionen"] or ()),
            body=body_name(row, rules),
            instrument=INSTRUMENT_LABELS.get(str(row["instrument"]), str(row["instrument"])),
        )
        for row in documents.iter_rows(named=True)
    ]
    return tuple(sorted(rows, key=lambda r: (r.date or dt.date.min, r.reference, r.title)))


def _k3(documents: pl.DataFrame, functions: Sequence[str]) -> Share:
    chosen = documents.filter(pl.col("funktion").is_in(list(functions)))
    lager = chosen.get_column("lager")
    return Share(int((lager == ACROSS).sum()), int(lager.is_in(OPPOSITION_TAKES_PART).sum()))


def concordance(
    documents: pl.DataFrame,
    settings: Settings,
    labels: Mapping[str, str],
    party_labels: Mapping[str, str],
    level: tuple[str, str],
) -> Concordance | None:
    """K3 und die Mehrheiten; ``None``, wenn kein Dokument ein Lager hat (keine Mehrheit im Profil)."""
    if set(documents.get_column("lager").unique().to_list()) <= {NO_CAMP, NO_PARTY}:
        return None
    kinds = tuple(settings.majorities.body_kinds)
    dates = documents.get_column("date").drop_nulls()
    first, last = dates.min(), dates.max()
    by_reference = {
        str(r): _https(u)
        for r, u in documents.select("reference", "download_url").iter_rows()
        if r is not None
    }
    city = documents.filter(
        (pl.col("urheber_art") == "Fraktion") & pl.col("gremium_art").is_in(list(kinds))
    )
    majorities = []
    for term in settings.majorities.terms:
        if not isinstance(first, dt.date) or not isinstance(last, dt.date):
            break
        if term.valid_from > last or (term.valid_to is not None and term.valid_to < first):
            continue
        within = city.filter(pl.col("date") >= term.valid_from)
        if term.valid_to is not None:
            within = within.filter(pl.col("date") <= term.valid_to)
        majorities.append(
            MajorityRow(
                period=term.period,
                parties=", ".join(party_labels.get(p, p) for p in term.parties),
                valid_from=term.valid_from,
                valid_to=term.valid_to,
                agreement=term.agreement,
                agreement_date=term.agreement_date,
                evidence=tuple(Evidence(r, by_reference.get(r, "")) for r in term.evidence),
                documents=within.height,
            )
        )
    across = documents.filter(pl.col("lager") == ACROSS)
    return Concordance(
        initiatives=_k3(documents, INITIATIVES),
        all_functions=_k3(documents, POLITICAL),
        majorities=tuple(majorities),
        across=document_rows(across, labels, BodyRules.from_settings(settings.bodies)),
        many=int((across.get_column("fraktionen").list.len() >= MANY_FRACTIONS).sum()),
        level=level[0],
        level_dative=level[1],
    )


# Gremienarten als Ebene einer Matrix, im Nominativ und im Dativ („in Rat und Ausschüssen").
LEVEL_WORDS: dict[str, tuple[str, str]] = {
    "rat": ("Rat", "Rat"),
    "ausschuss": ("Ausschüsse", "Ausschüssen"),
    "bezirksvertretung": ("Bezirksvertretungen", "Bezirksvertretungen"),
    "beirat": ("Beiräte", "Beiräten"),
    "unbekannt": ("Gremien unbekannt", "Gremien unbekannt"),
}


def _level_label(kinds: Sequence[str]) -> tuple[str, str]:
    words = [LEVEL_WORDS.get(k, (k, k)) for k in kinds]
    return " und ".join(w[0] for w in words), " und ".join(w[1] for w in words)


# --- Die ganze Seite -------------------------------------------------------------------------------
@dataclass(frozen=True)
class ActorsModel:
    """Was ``templates/pages/akteure.html.j2`` als ``data.akteure`` sieht."""

    documents: int
    fraction_documents: int
    unrecognised: int  # Restklasse, „Funktion nicht erkannt"
    first: dt.date | None
    last: dt.date | None
    check: Check
    bars: tuple[FunctionBar, ...]
    table: FunctionTable
    instruments: tuple[InstrumentRow, ...]
    fractions: tuple[FractionRow, ...]
    split: tuple[SplitFraction, ...]  # eine Partei neben ihrer späteren Fraktion (Review N2)
    practice: tuple[PracticeRow, ...]
    difference: CountingDifference
    matrices: tuple[Matrix, ...]
    other_joint: int  # gemeinsame Dokumente außerhalb beider Matrizen (Beiräte, Gremium unbekannt)
    concordance: Concordance | None
    statements: tuple[DocumentRow, ...]
    missing: tuple[str, ...]  # was diesem Profil fehlt, je ein Satz (Plan § 6)
    variant: str
    running: bool  # laufende Periode (``period.end`` leer): ein kleines K3 ist noch kein Befund
    min_documents: int = MIN_DOCUMENTS
    many_fractions: int = MANY_FRACTIONS

    @property
    def explorative(self) -> bool:
        return not self.check.measured


def labels_of(settings: Settings) -> tuple[dict[str, str], dict[str, str]]:
    """Kurznamen der Fraktionen (auch der aus mehreren Parteien, „SPD/Volt") und Namen der Parteien."""
    named = [*settings.originators.parties, *settings.originators.groups]
    short = {p.key: p.short or p.label or p.key for p in named}
    long = {p.key: p.label or p.short or p.key for p in named}
    fractions = {
        f.key: "/".join(short.get(p, p) for p in f.parties) for f in settings.functions.fractions
    }
    return {**short, **fractions}, long


def build_actors(documents: pl.DataFrame, settings: Settings, check: Check) -> ActorsModel:
    """Das Modell der Seite aus einer Zeile je Korpus-ID (``DOCUMENT_COLUMNS``)."""
    missing_columns = sorted(set(DOCUMENT_COLUMNS) - set(documents.columns))
    if missing_columns:
        raise SchemaError(f"{PAGE_NAME}.html: Spalten fehlen: {missing_columns}")
    documents = documents.sort("id")
    labels, party_labels = labels_of(settings)
    from georep.analysis.parties import Patterns

    order = {k: i for i, (k, _) in enumerate(Patterns.from_settings(settings.originators).parties)}
    context = MajorityContext(settings.majorities, tuple(settings.functions.fractions), order)
    has_majority = bool(settings.majorities.terms)
    axis = fraction_axis(documents, labels)
    city_kinds = tuple(settings.majorities.body_kinds)
    city_label = _level_label(city_kinds)
    matrices = (
        cosponsor_matrix(
            documents,
            axis,
            key="stadt",
            kinds=city_kinds,
            context=context if has_majority else None,
        ),
        cosponsor_matrix(
            documents,
            axis,
            key="bezirke",
            kinds=(DISTRICT_LEVEL,),
            context=None,
        ),
    )
    joint_total = int(documents.get_column("gemeinsam").sum())
    concordance_model = concordance(documents, settings, labels, party_labels, city_label)
    dates = documents.get_column("date").drop_nulls()
    missing = [
        *(
            []
            if concordance_model is not None
            else [
                "Ratsmehrheit: das Profil nennt keine, darum tragen die Dokumente kein Lager, und "
                "die Konkordanz fehlt."
            ]
        ),
        *(
            []
            if matrices[1].documents
            else ["Bezirksvertretungen: keine gemeinsamen Dokumente in diesem Datensatz."]
        ),
    ]
    first, last = dates.min(), dates.max()
    rows = fraction_rows(documents, labels)
    return ActorsModel(
        documents=documents.height,
        fraction_documents=int((documents.get_column("urheber_art") == "Fraktion").sum()),
        unrecognised=int((documents.get_column("funktion") == "rest").sum()),
        first=first if isinstance(first, dt.date) else None,
        last=last if isinstance(last, dt.date) else None,
        check=check,
        bars=function_bars(documents),
        table=function_table(documents),
        instruments=instruments(documents),
        fractions=rows,
        split=split_fractions(documents, rows, settings),
        practice=practice_rows(documents),
        difference=counting_difference(documents),
        matrices=matrices,
        other_joint=joint_total - sum(m.documents for m in matrices),
        concordance=concordance_model,
        statements=document_rows(
            documents.filter(pl.col("funktion") == STATEMENT),
            labels,
            BodyRules.from_settings(settings.bodies),
        ),
        missing=tuple(missing),
        variant=settings.functions.variant,
        running=settings.period.end is None,
    )


# --- Dateien -----------------------------------------------------------------------------------
def _files(layout: Layout) -> tuple[Path, Path]:
    from georep.enrich.functions import functions_files

    files = functions_files(layout)
    return files.functions, files.cosponsors


def actors_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """Was der Schritt ``page_akteure`` liest: die beiden Tabellen von 15, Korpus, Urheber, Gremien, Prüfung."""
    return (
        *_files(layout),
        layout.corpus,
        layout.document_originators,
        layout.papers_bodies,
        *check_files(settings),
    )


def read_documents(layout: Layout) -> pl.DataFrame:
    """Eine Zeile je Korpus-ID mit allem, was die Seite braucht; nach ``id`` sortiert."""
    functions, cosponsors = _files(layout)
    corpus = pl.read_parquet(
        layout.corpus, columns=["id", "name", "reference", "date", "download_url"]
    )
    return (
        corpus.join(pl.read_parquet(functions, columns=["id", "funktion", "instrument"]), on="id")
        .join(
            pl.read_parquet(
                cosponsors, columns=["id", "antragsteller", "fraktionen", "gemeinsam", "lager"]
            ),
            on="id",
        )
        .join(
            pl.read_parquet(layout.document_originators, columns=["id", "urheber_art", "parteien"]),
            on="id",
            how="left",
        )
        .join(
            pl.read_parquet(
                layout.papers_bodies, columns=["id", "gremium", "gremium_art", "stadtbezirk"]
            ),
            on="id",
            how="left",
        )
        .with_columns(pl.col("urheber_art").fill_null("unbekannt"))
        .sort("id")  # ein Join legt die Zeilenfolge nicht fest (CLAUDE.md)
    )


def page_data(model: ActorsModel, settings: Settings) -> Mapping[str, object]:
    """Was die Vorlage als ``data`` sieht: das Modell als ``akteure``, dazu die Wörter der Legenden."""
    labels, _ = labels_of(settings)
    return {
        "akteure": model,
        "functions": tuple(FUNCTION_SHORT.items()),
        "camps": tuple((c, CAMP_LABELS[c]) for c in PAIR_CAMPS),
        "camp_names": CAMP_LABELS,
        "camp_short": CAMP_SHORT,
        "labels": labels,
        "urls": repository_links(settings),
    }


def actors_data(layout: Layout, settings: Settings) -> Mapping[str, object]:
    """``Page.data``: die Dateien lesen, das Modell bauen (``page_data``)."""
    return page_data(build_actors(read_documents(layout), settings, read_check(settings)), settings)


MEASUREMENT = "docs/plans/15-funktion.md"  # Messdokument, relativ zum Repository


def repository_links(settings: Settings) -> dict[str, str]:
    """Messdokument und README der Prüfung im Repository; Vorlage und Allowlist lesen dieselben.

    Der Ordner der Prüfung heißt im Repository wie der letzte Teil von ``validation.root``; der
    Wert selbst ist relativ zum Arbeitsverzeichnis und kann auf einem Rechner absolut sein.
    """
    from georep.report.render import REPOSITORY

    folder = settings.validation.root.name
    return {
        "measurement": f"{REPOSITORY}/blob/main/{MEASUREMENT}",
        "check": f"{REPOSITORY}/blob/main/{folder}/{VALIDATION_PROJECT}/README.md",
        "check_folder": f"{folder}/{VALIDATION_PROJECT}",
    }


def actors_links(layout: Layout, settings: Settings) -> frozenset[str]:
    """Die Links nach außen: die PDF-Dateien des Korpus im Ratsinformationssystem, das Messdokument
    und die Prüfung im Repository. Ohne Korpus keine Dokumentlinks (dann gibt es keine Seite)."""
    links = repository_links(settings)
    repository = {links["measurement"], links["check"]}
    if not layout.corpus.is_file():
        return frozenset(repository)
    urls = pl.read_parquet(layout.corpus, columns=["download_url"]).get_column("download_url")
    return frozenset(repository | {_https(u) for u in urls.to_list() if u})
