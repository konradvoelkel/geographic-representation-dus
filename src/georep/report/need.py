"""Die Unterseite ``bedarf.html``: Bedarf und Aufmerksamkeit je Wahlbezirk (Vorhaben 22, Stufe 3).

Stufe 3 von Vorhaben 22 (Messdokument ``docs/plans/22-bedarf.md``, § 7 mit § 10) im Muster von
``akteure.html`` (Punkt 88). Vier Abschnitte:

1. *Quellen und Stand*: je Bedarfsquelle Bereitsteller, Lizenz, Namensnennung mit
   Veränderungshinweis (V5), Stand, Raumeinheit, Umrechnung und Abdeckung, dazu der Satz zum
   Randband und die Gegenproben, die sich aus den Tabellen nachrechnen lassen.
2. *Bedarf je Wahlbezirk*: kleine Karten (Unfälle je 1 000 Einwohner, sozialer Handlungsbedarf,
   Anteil unter 18; ohne Fremddaten der Schulsozialindex statt des Handlungsbedarfs) und dieselben
   Zahlen als sortierbare Tabelle.
3. *Bedarf und Nennung*: die vorab festgelegten Tests als Tabelle mit Tag und Commit der
   Festlegung, je Test ein Streudiagramm mit dem Stadtbezirk als Schicht, Robustheit, die Rechnung
   innerhalb der Stadtbezirke und Moran's I; die übrigen Paare unter „explorativ".
4. *Was das nicht sagt*, mit dem Ergebnis der Prüfung der Klasse (``validierung/22-bedarf-ova``,
   Messdokument § 4.1): je nach Übereinstimmung und unterer Grenze die Präzision mit Prüfsatz,
   „unscharf" oder, wie gemessen, keine Präzision und der Satz, was beobachtet wurde.

**Stadtbezirk statt Farbe.** § 7 nennt den Stadtbezirk als Farbe der Streudiagramme. Zehn
Stadtbezirke sind zehn Kategorien, und ein Streudiagramm trägt nach der Skill ``dataviz`` höchstens
drei unterscheidbare Farben (alle Paare liegen nebeneinander). Darum trägt jeder Stadtbezirk seine
Nummer im Mittelpunkt seiner Wahlbezirke, und eine dünne Linie verbindet jeden Wahlbezirk mit ihm:
liegt der Zusammenhang zwischen den Stadtbezirken, steigen die Mittelpunkte, und die Linien
darum herum zeigen keine Richtung.

Was die Seite nicht zeigt (§ 7): keine Rangfolge „Bedarf minus Aufmerksamkeit", nichts je
Partei, keine Personen, keine Zeitreihe. Rein bis auf ``read_inputs``, ``read_check`` und
``need_data``, die Dateien lesen; kein Stadtwort im Code: Quellen, Klassen und Hypothesen kommen aus
den Settings.
"""

from __future__ import annotations

import html
import json
import math
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import deal
import polars as pl

from georep.analysis.need import (
    MAIN,
    MORAN_ATTENTION,
    MORAN_NEED,
    MORAN_RESIDUALS,
    PAIR,
    ROBUST,
    WITHIN,
)
from georep.errors import MissingInputError, SchemaError
from georep.geo import read_canonical_precincts
from georep.layout import Layout
from georep.report.charts import Axes, classify, legend
from georep.report.geometry import SIMPLIFY_M, bounds_of, district_shapes, fit, svg_path
from georep.report.model import format_de, percent_de
from georep.settings import NeedAttribution, Settings, load_settings, profile_folder

PAGE_NAME = "bedarf"
VALIDATION_PROJECT = "22-bedarf-ova"  # die Prüfung der Klasse unter ``validation.root`` (§ 4.1)
QUESTION = "ordnung_verkehr"  # die Frage des Codebuchs
MEASUREMENT = "docs/plans/22-bedarf.md"  # Messdokument, relativ zum Repository
# Frage 22.11: die Klasse des Ordnungs- und Verkehrsausschusses heißt auf der Seite so, weil
# Ordnungsthemen (Sondernutzung, Sauberkeit, Märkte) mitzählen; die Jugendklasse nach § 3.3.
TRAFFIC = "Ordnung und Verkehr"
YOUTH = "Jugend und Schule"
# Messdokument § 4.1: die untere Grenze, ab der die Seite die Präzision mit Prüfsatz nennt.
PRECISION_FLOOR = 0.8
# Messdokument § 8: Power 80 % für einen einseitigen Test bei α und im ersten Holm-Schritt (α/m).
# Fisher-z mit dem Faktor 1,06 für Spearman (Fieller, Hartley und Pearson 1957).
POWER = 0.8
SPEARMAN_VARIANCE = 1.06
EXPLORATIVE_ALPHA = 0.05  # die Schwelle der Sätze zu „innerhalb" und Moran's I, unkorrigiert
SMALL_MAP_WIDTH = 320.0  # drei Karten nebeneinander, auf schmalem Bildschirm untereinander
SCATTER_WIDTH = 520.0
SCATTER_HEIGHT = 340.0
SCATTER_MARGIN = (16.0, 16.0, 48.0, 60.0)
CLASS_CHECK_ACCURACY = (
    0.941  # Punkt 45: Kreuzvalidierung an Ausschussdokumenten (statistik.md § 10)
)
NO_VALUE = "ohne Wert"

# Spalten der Tabellen in Worten; die Variablen der Fremddaten tragen ihre Namen in den Settings.
COLUMN_LABELS: dict[str, str] = {
    "einwohner_zensus": "Einwohner (Zensus 2022)",
    "unfaelle": "Unfälle mit Personenschaden",
    "unfaelle_scharf": "Unfälle, scharf zugeordnet",
    "unfaelle_je_1000": "Unfälle mit Personenschaden je 1 000 Einwohner",
    "unfaelle_scharf_je_1000": "Unfälle je 1 000 Einwohner, scharf zugeordnet",
    "unfaelle_je_km2": "Unfälle je km²",
    "unfaelle_rad_fuss": "Unfälle mit Rad- oder Fußbeteiligung",
    "unfaelle_schwer": "Unfälle mit Getöteten oder Schwerverletzten",
    "miete_qm": "Nettokaltmiete je m² (Zensus 2022)",
    "sozialindex_schulen": "Schulsozialindex der Schulen (Mittel)",
    "dok": "Dokumente mit Treffer",
    "dok_je_1000_ew": "Dokumente mit Treffer je 1 000 Einwohner",
    "dok_verkehr_je_1000_ew": f"Dokumente {TRAFFIC} je 1 000 Einwohner",
    "anteil_verkehr": f"Anteil {TRAFFIC}",
    "anteil_jugend": f"Anteil {YOUTH}",
    "trefferquote": "Trefferquote (je Wahlberechtigtem)",
    "wahlbeteiligung": "Wahlbeteiligung",
    "log_begriffe": "log(Zahl der Begriffe im Wörterbuch)",
}


# --- Die Prüfung der Klasse (F4, Messdokument § 4.1) ------------------------------------------------
@dataclass(frozen=True)
class ClassCheck:
    """Was ``guete.json`` der Prüfung sagt und welcher Fall aus § 4.1 gilt."""

    sentence: str  # ``satz``: Modelle, Einheiten, „nicht von Menschen"
    models: tuple[str, str, str]  # Kodierer A, Kodierer B, Schlichtung
    units: int
    both: int  # von beiden beurteilt
    agreed: int
    alpha: float | None
    alpha_ok: bool
    note: str  # ``alpha_vermerk``, etwa „volle Einigkeit, α nicht definiert"
    labels: tuple[tuple[str, int], ...]  # Endlabel -> Zahl, in der Folge des Codebuchs
    positive: int  # Endlabels ``ja``
    judged: int  # ``ja`` und ``nein``
    weighted: float | None  # gewichteter Anteil ``ja`` für die Grundgesamtheit
    interval: tuple[float, float] | None  # Wilson bei Kishs n_eff
    population: int  # Dokumente in der Grundgesamtheit
    measured: bool  # dieser Datensatz ist der der Stichprobe
    measured_datasets: tuple[str, ...]

    @property
    def case(self) -> int:
        """§ 4.1: 1 Präzision mit Prüfsatz, 2 „unscharf", 3 kein verlässliches Maß."""
        if not self.alpha_ok or self.interval is None:
            return 3
        return 1 if self.interval[0] >= PRECISION_FLOOR else 2

    def count(self, label: str) -> int:
        return dict(self.labels).get(label, 0)


def check_files(settings: Settings) -> tuple[Path, Path]:
    """``guete.json`` und ``stichprobe.json`` der Prüfung im Repo."""
    folder = settings.validation.root / VALIDATION_PROJECT
    return (folder / "guete.json", folder / "stichprobe.json")


def _dataset_name(profile: str) -> str:
    """„Stadt, Wahlperiode …" eines Paketprofils; ein unbekanntes bleibt sein Name."""
    from georep.report.model import period_info

    try:
        settings = load_settings(profile=profile, cwd=Path("/nonexistent"))
    except OSError, ValueError, SchemaError:
        return profile
    return f"{settings.city.name}, {period_info(settings).title}"


def _folder(profile: str) -> str | None:
    try:
        return profile_folder(profile)
    except OSError, ValueError, SchemaError:
        return None


@deal.raises(MissingInputError, SchemaError)
def read_check(settings: Settings) -> ClassCheck:
    """Die Prüfung aus ``guete.json`` und ``stichprobe.json``; ``SchemaError`` bei fehlendem Feld."""
    quality_path, sample_path = check_files(settings)
    for path in (quality_path, sample_path):
        if not path.is_file():
            raise MissingInputError(f"{path} fehlt; die Seite {PAGE_NAME}.html nennt ihre Prüfung")
    quality: dict[str, Any] = json.loads(quality_path.read_text(encoding="utf-8"))
    sample: dict[str, Any] = json.loads(sample_path.read_text(encoding="utf-8"))
    try:
        entry = dict(quality["fragen"][QUESTION])
        models = dict(quality["modelle"])
        counts = {str(k): int(v) for k, v in dict(entry["labels"]).items()}
        hits = entry.get("treffer")
        population = dict(hits["grundgesamtheit"]) if hits else {}
        drawn = dict(hits["stichprobe"]) if hits else {}
        interval = (
            (float(population["wilson95_kish"][0]), float(population["wilson95_kish"][1]))
            if population
            else None
        )
        alpha = entry.get("krippendorff_alpha")
        profiles = tuple(p.strip() for p in str(sample["profil"]).split(",") if p.strip())
        check = ClassCheck(
            sentence=str(quality["satz"]),
            models=(
                str(models["kodierer_a"]),
                str(models["kodierer_b"]),
                str(models["schlichtung"]),
            ),
            units=int(entry["n"]),
            both=int(entry["beide"]),
            agreed=int(entry["einig"]),
            alpha=None if alpha is None else float(alpha),
            alpha_ok=bool(entry["alpha_genuegt"]),
            note=str(entry.get("alpha_vermerk") or ""),
            labels=tuple(counts.items()),
            positive=int(drawn.get("treffer", counts.get("ja", 0))),
            judged=int(drawn.get("gewertet", counts.get("ja", 0) + counts.get("nein", 0))),
            weighted=float(population["schaetzer"]) if population else None,
            interval=interval,
            population=int(population.get("n", sample["einheiten"])),
            measured=settings.profile in {f for f in map(_folder, profiles) if f},
            measured_datasets=tuple(_dataset_name(p) for p in profiles),
        )
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise SchemaError(f"{quality_path} oder {sample_path}: Feld fehlt ({error})") from error
    return check


# --- Quellen und Stand ------------------------------------------------------------------------------
@dataclass(frozen=True)
class Source:
    """Eine Zeile von „Quellen und Stand"."""

    title: str
    url: str
    publisher: str
    license: str
    license_url: str
    stand: str
    unit: str  # Raumeinheit der Quelle
    transform: str  # Umrechnung auf die Wahlbezirke
    coverage: str  # Abdeckung in Zahlen
    modified: str  # Veränderungshinweis (dl-de/by-2-0, V5); leer heißt unverändert

    @property
    def attribution(self) -> str:
        """Die Namensnennung, wie die Lizenz sie verlangt: wer, was, Lizenz, was verändert ist."""
        base = f"{self.publisher}, {self.title}, {self.license}"
        return f"{base}; {self.modified}" if self.modified else base


def _source(attribution: NeedAttribution, unit: str, transform: str, coverage: str) -> Source:
    return Source(
        title=attribution.title,
        url=attribution.url,
        publisher=attribution.publisher,
        license=attribution.license,
        license_url=attribution.license_url,
        stand=attribution.stand,
        unit=unit,
        transform=transform,
        coverage=coverage,
        modified=attribution.modified,
    )


def _share_range(values: Sequence[float]) -> str:
    low, high = min(values), max(values)
    return percent_de(low, 1) if low == high else f"{percent_de(low, 1)} bis {percent_de(high, 1)}"


@dataclass(frozen=True)
class Accidents:
    """Die Unfälle der Periode: im Auszug, einem Wahlbezirk zugeordnet, im Randband geteilt."""

    total: int
    located: float  # Summe der Anteile, also die Unfälle mit mindestens einem Wahlbezirk im Band
    shared: float  # Unfälle, die auf mehrere Wahlbezirke gehen
    sharp_rank: float | None  # Spearman der absoluten Zahlen, scharf gegen unscharf

    @property
    def outside(self) -> int:
        return self.total - round(self.located)

    @property
    def shared_share(self) -> float:
        return self.shared / self.total if self.total else 0.0


def sources(
    settings: Settings,
    table: pl.DataFrame,
    accidents: Accidents,
    context_units: int,
) -> tuple[Source, ...]:
    """Die Quellen der Seite in der Folge der Tabelle; der Quartiersatlas nur mit Fremddaten."""
    need = settings.context.need
    band = format_de(need.band_m)
    residents = float(table.get_column("einwohner_zensus").sum())
    rent = [float(v) for v in table.get_column("miete_abdeckung").drop_nulls().to_list()]
    schools = int(table.get_column("schulen").sum())
    with_index = int(table.get_column("schulen_mit_index").sum())
    per_district = [int(v) for v in table.get_column("schulen").to_list()]
    period = settings.period
    months = f"{period.start.month:02d}/{period.start.year}" + (
        f" bis {period.end.month:02d}/{period.end.year}" if period.end else " bis heute"
    )
    found = [
        _source(
            need.accidents.attribution,
            "Punkt auf der Straßenachse",
            f"Punkt in Fläche; näher als {band} m an mehreren Wahlbezirken zu gleichen Teilen an "
            "jeden",
            f"{format_de(accidents.total)} Unfälle der Monate {months}, "
            f"{format_de(accidents.located)} davon in einem Wahlbezirk, "
            f"{format_de(accidents.shared)} geteilt",
        ),
        _source(
            need.grid.attribution,
            "100-m-Gitterzelle",
            "Mittelpunkt der Zelle in Fläche; die Miete gewogen mit den Einwohnern der Zellen",
            f"{format_de(residents)} Einwohner; Miete je Wahlbezirk für "
            f"{_share_range(rent) if rent else '–'} der Einwohner",
        ),
        _source(
            need.schools.attribution,
            "Schule (Punkt über die Schulnummer)",
            "Punkt in Fläche; Mittel der Stufen der Schulen je Wahlbezirk",
            f"{format_de(schools)} Schulen, {format_de(with_index)} mit Stufe; "
            f"{min(per_district)} bis {max(per_district)} je Wahlbezirk",
        ),
    ]
    context = settings.context
    if context_units:
        dataset = context.dataset
        found.append(
            Source(
                title=dataset.title,
                url=dataset.url,
                publisher=dataset.publisher,
                license=dataset.license,
                license_url=dataset.license_url,
                stand=f"Datenstand {dataset.stand:%d.%m.%Y}" if dataset.stand else "",
                unit=context.units.label,
                transform="über Flächenanteile und Wahlberechtigte je Stimmbezirk (Crosswalk), "
                "gewichtetes Mittel je Wahlbezirk",
                coverage=f"{format_de(context_units)} {context.units.label}",
                modified=f"verändert: {context.units.label} auf Wahlbezirke umgerechnet",
            )
        )
    return tuple(found)


# --- Bedarf je Wahlbezirk -----------------------------------------------------------------------------
@dataclass(frozen=True)
class District:
    """Eine Zeile der Tabelle je Wahlbezirk; ``None`` heißt ohne Wert in diesem Profil."""

    id: int
    name: str
    stratum: int | None
    residents: float
    accidents: float
    accidents_rate: float | None
    accidents_vulnerable: float
    rent: float | None
    school_index: float | None
    schools: int
    need_score: float | None
    youth: float | None
    documents: int
    documents_rate: float | None
    traffic: float | None
    youth_docs: float | None


@dataclass(frozen=True)
class MapPanel:
    """Eine kleine Karte: Titel, SVG, Legende als (Klasse, Text)."""

    key: str
    title: str
    svg: str
    legend: tuple[tuple[str, str], ...]


def _value(row: Mapping[str, Any], column: str) -> float | None:
    value = row.get(column)
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def districts_of(
    table: pl.DataFrame, context: pl.DataFrame | None, names: Mapping[int, str]
) -> tuple[District, ...]:
    """Die Zeilen je Wahlbezirk aus ``wahlbezirke_bedarf`` und, wo es sie gibt, den Fremddaten."""
    frame = table
    if context is not None:
        keep = [c for c in ("hb_score", "anteil_u18") if c in context.columns]
        frame = frame.join(context.select("wahlkreis_id", *keep), on="wahlkreis_id", how="left")
    frame = frame.sort("wahlkreis_id")  # ein Join legt die Zeilenfolge nicht fest (CLAUDE.md)
    rows = []
    for row in frame.iter_rows(named=True):
        district = int(row["wahlkreis_id"])
        rows.append(
            District(
                id=district,
                name=names.get(district, ""),
                stratum=None if row.get("stadtbezirk") is None else int(row["stadtbezirk"]),
                residents=float(row["einwohner_zensus"] or 0.0),
                accidents=float(row["unfaelle"] or 0.0),
                accidents_rate=_value(row, "unfaelle_je_1000"),
                accidents_vulnerable=float(row["unfaelle_rad_fuss"] or 0.0),
                rent=_value(row, "miete_qm"),
                school_index=_value(row, "sozialindex_schulen"),
                schools=int(row["schulen"] or 0),
                need_score=_value(row, "hb_score"),
                youth=_value(row, "anteil_u18"),
                documents=int(row["dok"] or 0),
                documents_rate=_value(row, "dok_je_1000_ew"),
                traffic=_value(row, "anteil_verkehr"),
                youth_docs=_value(row, "anteil_jugend"),
            )
        )
    return tuple(rows)


def small_map(
    key: str,
    title: str,
    values: Mapping[int, float | None],
    shapes: Mapping[int, Any],
    names: Mapping[int, str],
    fmt: Callable[[float], str],
) -> MapPanel:
    """Eine kleine Choroplethe mit Quantilklassen; ein Wahlbezirk ohne Wert ist grau.

    Jede Fläche trägt ``data-id`` und ``data-district``: der Rahmen (``frame/script.js.j2``)
    zeigt dann Tooltip und Markierung wie auf den Details, und ein Klick markiert denselben
    Wahlbezirk in allen Karten, im Streudiagramm und in der Tabelle (``#districts``).
    """
    present = {d: v for d, v in values.items() if v is not None}
    classes = classify(present) if present else None
    projection = fit(bounds_of(shapes), SMALL_MAP_WIDTH)
    ident = f"karte-{key}"
    parts = [
        f'<svg class="map small-map" viewBox="{projection.view_box}" role="img" '
        f'aria-labelledby="{ident}" xmlns="http://www.w3.org/2000/svg">',
        f'<title id="{ident}">{html.escape(title)} je Wahlbezirk</title>',
        '<g class="districts" fill-rule="evenodd">',
    ]
    for district, geometry in sorted(shapes.items()):
        value = present.get(district)
        klass = f"q{classes.classes[district]}" if classes and value is not None else "ohne"
        shown = fmt(value) if value is not None else NO_VALUE
        label = f"{title}: {shown}"
        parts.append(
            f'<path class="district {klass}" data-id="{district}" data-district="{district}" '
            f'data-name="{html.escape(label, quote=True)}" tabindex="0" '
            f'd="{svg_path(geometry, projection)}"><title>'
            f"{html.escape(f'Wahlbezirk {district} {names.get(district, "")}: {shown}')}"
            "</title></path>"
        )
    parts.append("</g></svg>")
    entries = [(f"q{e.klass}", e.label) for e in legend(classes, fmt)] if classes else []
    if len(present) < len(shapes):
        entries.append(("ohne", NO_VALUE))
    return MapPanel(key, title, "".join(parts), tuple(entries))


def _fmt(decimals: int, unit: str = "") -> Callable[[float], str]:
    def label(value: float) -> str:
        return f"{format_de(value, decimals)}{unit}"

    return label


def _percent(value: float) -> str:
    return percent_de(value, 1)


# --- Bedarf und Nennung ------------------------------------------------------------------------------
@dataclass(frozen=True)
class Robustness:
    label: str
    rho: float
    n: int


@dataclass(frozen=True)
class Moran:
    label: str
    value: float
    p: float | None


@dataclass(frozen=True)
class Test:
    """Ein vorab festgelegter Test mit allem, was neben ihm steht."""

    name: str
    need: str  # Bedarf (x) in Worten
    attention: str  # Aufmerksamkeit (y) in Worten
    attention_key: str  # die Spalte der Aufmerksamkeit (``anteil_verkehr`` trägt die Prüfung)
    alternative: str  # „einseitig, ρ > 0" oder „zweiseitig"
    rho: float | None
    interval: tuple[float, float] | None
    p: float | None
    p_holm: float | None
    result: str | None  # bestätigt, nicht bestätigt; None ohne Werte in diesem Lauf
    reading: str | None  # die Deutung aus § 8
    n: int
    commit: str
    fixed_on: str  # Tag der Festlegung, deutsch; leer, wenn das Profil ihn nicht nennt
    robustness: tuple[Robustness, ...]
    within: tuple[float, float | None] | None  # ρ und p innerhalb der Stadtbezirke
    moran: tuple[Moran, ...]
    scatter: str  # SVG; leer ohne Werte
    notes: tuple[str, ...]  # die Sätze zu innerhalb und Moran's I, aus den Zahlen

    @property
    def confirmed(self) -> bool:
        return self.result == "bestätigt"


@dataclass(frozen=True)
class Pair:
    need: str
    attention: str
    rho: float
    p: float | None
    n: int


def p_text(p: float | None) -> str:
    """Ein p-Wert deutsch: drei Stellen, darunter zwei gültige Ziffern; unter 0,0001 „< 0,0001"."""
    if p is None:
        return "–"
    if p < 0.0001:
        return f"< {format_de(0.0001, 4)}"
    if p >= 0.001:
        return format_de(p, 3)
    return format_de(p, -math.floor(math.log10(p)) + 1)


def power_threshold(n: int, alpha: float) -> float:
    """Das kleinste |ρ|, das ein einseitiger Test mit 80 % Power bei ``n`` und ``alpha`` erkennt."""
    normal = statistics.NormalDist()
    z = normal.inv_cdf(1 - alpha) + normal.inv_cdf(POWER)
    return math.tanh(z * math.sqrt(SPEARMAN_VARIANCE / (n - 3)))


def column_labels(settings: Settings) -> dict[str, str]:
    """Spalte -> Wort: die Tabellen von 22 und die Variablen der Fremddaten aus den Settings."""
    found = dict(COLUMN_LABELS)
    for variable in settings.context.variables:
        found.setdefault(variable.name, variable.label or variable.name)
    return found


@dataclass(frozen=True)
class ScatterPoint:
    district: int
    name: str
    stratum: int | None
    x: float
    y: float


def _num(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def need_scatter(
    ident: str,
    points: Sequence[ScatterPoint],
    x_title: str,
    y_title: str,
    x_fmt: Callable[[float], str],
    y_fmt: Callable[[float], str],
) -> str:
    """Bedarf (x) gegen Aufmerksamkeit (y) je Wahlbezirk, mit dem Mittelpunkt jedes Stadtbezirks.

    Jeder Wahlbezirk ist ein Punkt (``.point`` mit ``data-id``, wie auf den Details: Tooltip und
    Markierung kommen aus dem Rahmen), eine dünne Linie führt zum Mittelpunkt seines Stadtbezirks,
    und der Mittelpunkt trägt die Nummer des Stadtbezirks. Ohne Punkte ist das Diagramm leer.
    """
    if not points:
        return ""
    axes = Axes.fit(
        [p.x for p in points],
        [p.y for p in points],
        width=SCATTER_WIDTH,
        height=SCATTER_HEIGHT,
        margin=SCATTER_MARGIN,
    )
    centres: dict[int, tuple[float, float]] = {}
    for stratum in sorted({p.stratum for p in points if p.stratum is not None}):
        members = [p for p in points if p.stratum == stratum]
        centres[stratum] = (
            statistics.fmean(p.x for p in members),
            statistics.fmean(p.y for p in members),
        )
    parts = [
        f'<svg class="scatter need-scatter" viewBox="0 0 {_num(SCATTER_WIDTH)} '
        f'{_num(SCATTER_HEIGHT)}" role="img" aria-labelledby="{ident}-title" '
        'xmlns="http://www.w3.org/2000/svg">',
        f'<title id="{ident}-title">{html.escape(f"{x_title} gegen {y_title} je Wahlbezirk")}'
        "</title>",
        axes.clip_path(f"{ident}-plot"),
        axes.grid(),
        axes.axis_lines(),
        axes.tick_labels(),
        axes.axis_titles(x_title, y_title),
        f'<g class="spokes" clip-path="url(#{ident}-plot)" aria-hidden="true">',
    ]
    for p in points:
        if p.stratum is None:
            continue
        cx, cy = centres[p.stratum]
        parts.append(
            f'<line x1="{_num(axes.sx(p.x))}" y1="{_num(axes.sy(p.y))}" '
            f'x2="{_num(axes.sx(cx))}" y2="{_num(axes.sy(cy))}"/>'
        )
    parts.append('</g><g class="dots">')
    for p in points:
        x, y = _num(axes.sx(p.x)), _num(axes.sy(p.y))
        where = f" (Stadtbezirk {p.stratum})" if p.stratum is not None else ""
        label = f"{x_fmt(p.x)}; {y_fmt(p.y)}"
        title = f"Wahlbezirk {p.district} {p.name}{where}: {label}"
        parts.append(
            f'<g class="point" data-id="{p.district}" data-district="{p.district}" '
            f'data-name="{html.escape(label, quote=True)}" tabindex="0">'
            f"<title>{html.escape(title)}</title>"
            f'<circle class="hit" cx="{x}" cy="{y}" r="12"/>'
            f'<circle class="dot" cx="{x}" cy="{y}" r="4"/></g>'
        )
    parts.append('</g><g class="centres" aria-hidden="true">')
    for stratum, (cx, cy) in centres.items():
        x, y = _num(axes.sx(cx)), _num(axes.sy(cy))
        parts.append(
            f'<circle class="centre" cx="{x}" cy="{y}" r="9"/>'
            f'<text class="centre-label" x="{x}" y="{y}">{stratum}</text>'
        )
    parts.append("</g></svg>")
    return "".join(parts)


def _robust_label(
    row: Mapping[str, Any], main: Mapping[str, Any], labels: Mapping[str, str]
) -> str:
    """Was eine Robustheitsrechnung anders macht als der Haupttest, in Worten."""
    if row["ohne"]:
        listed = " und ".join(str(d) for d in row["ohne"])
        return f"ohne die Wahlbezirke {listed}"
    if row["kontrolle"]:
        return f"partiell, bei festem {labels.get(row['kontrolle'], row['kontrolle'])}"
    if row["bedarf"] != main["bedarf"]:
        return f"Bedarf: {labels.get(row['bedarf'], row['bedarf'])}"
    return f"Aufmerksamkeit: {labels.get(row['aufmerksamkeit'], row['aufmerksamkeit'])}"


def _float(value: object) -> float | None:
    if value is None:
        return None
    number = float(str(value))
    return number if math.isfinite(number) else None


def _test_notes(
    confirmed: bool, within: tuple[float, float | None] | None, residuals: Moran | None
) -> tuple[str, ...]:
    """Die Sätze neben einem Test, aus den Zahlen (explorativ, ohne Korrektur, § 3.5)."""
    notes: list[str] = []
    rho, p = within if within is not None else (0.0, None)
    if p is not None:
        shown = f"ρ innerhalb {format_de(rho, 3)}, p {p_text(p)}"
        if confirmed and p >= EXPLORATIVE_ALPHA:
            notes.append(
                "Der Zusammenhang besteht zwischen den Stadtbezirken, nicht innerhalb: innerhalb "
                "eines Stadtbezirks bekommt der Wahlbezirk mit mehr Bedarf keinen größeren Wert "
                f"({shown})."
            )
        elif not confirmed and p < EXPLORATIVE_ALPHA:
            notes.append(
                "Innerhalb der Stadtbezirke zeigt sich ein Zusammenhang, den die Unterschiede "
                f"zwischen ihnen verdecken ({shown}); als These ist er erst an neuen Daten zu "
                "prüfen."
            )
    if residuals is not None and residuals.p is not None and residuals.p < EXPLORATIVE_ALPHA:
        notes.append(
            "Die Residuen sind räumlich korreliert (Moran's I "
            f"{format_de(residuals.value, 3)}, p {p_text(residuals.p)}): der Permutationstest "
            "nimmt an, dass die Wahlbezirke austauschbar sind, und sein p-Wert unterschätzt die "
            "räumliche Abhängigkeit."
        )
    return tuple(notes)


def tests_of(
    tests: pl.DataFrame,
    settings: Settings,
    analysis: pl.DataFrame,
    names: Mapping[int, str],
) -> tuple[tuple[Test, ...], tuple[Pair, ...]]:
    """Die vorab festgelegten Tests in der Folge des Profils und die explorativen Paare."""
    labels = column_labels(settings)
    rows = tests.to_dicts()
    found: list[Test] = []
    for hypothesis in settings.context.need.hypotheses:
        own = [r for r in rows if r["hypothese"] == hypothesis.name]
        main = next((r for r in own if r["rechnung"] == MAIN), None)
        if main is None:
            raise SchemaError(f"bedarf_hypothesen: kein Haupttest für {hypothesis.name}")
        within = next((r for r in own if r["rechnung"] == WITHIN), None)
        moran = {
            r["rechnung"]: Moran(label, float(r["wert"]), _float(r["p"]))
            for r in own
            for key, label in (
                (MORAN_RESIDUALS, "Residuen der Rangregression"),
                (MORAN_NEED, "Bedarf"),
                (MORAN_ATTENTION, "Aufmerksamkeit"),
            )
            if r["rechnung"] == key and r["wert"] is not None
        }
        within_pair = (
            (float(within["wert"]), _float(within["p"]))
            if within is not None and within["wert"] is not None
            else None
        )
        rho = _float(main["wert"])
        need_label = labels.get(hypothesis.need, hypothesis.need)
        attention_label = labels.get(hypothesis.attention, hypothesis.attention)
        points = [
            ScatterPoint(int(r["wahlkreis_id"]), names.get(int(r["wahlkreis_id"]), ""),
                         None if r.get("stadtbezirk") is None else int(r["stadtbezirk"]),
                         float(r[hypothesis.need]), float(r[hypothesis.attention]))
            for r in analysis.iter_rows(named=True)
            if _float(r.get(hypothesis.need)) is not None
            and _float(r.get(hypothesis.attention)) is not None
        ]  # fmt: skip
        found.append(
            Test(
                name=hypothesis.name,
                need=need_label,
                attention=attention_label,
                attention_key=hypothesis.attention,
                alternative="einseitig, ρ\u00a0>\u00a00"
                if hypothesis.alternative == "greater"
                else "zweiseitig",
                rho=rho,
                interval=(float(main["ci_lo"]), float(main["ci_hi"]))
                if main["ci_lo"] is not None and main["ci_hi"] is not None
                else None,
                p=_float(main["p"]),
                p_holm=_float(main["p_holm"]),
                result=main["ergebnis"],
                reading=main["deutung"],
                n=int(main["n"]),
                commit=hypothesis.fixed,
                fixed_on=hypothesis.fixed_on.strftime("%d.%m.%Y") if hypothesis.fixed_on else "",
                robustness=tuple(
                    Robustness(_robust_label(r, main, labels), float(r["wert"]), int(r["n"]))
                    for r in own
                    if r["rechnung"] == ROBUST and r["wert"] is not None
                ),
                within=within_pair,
                moran=tuple(
                    moran[k] for k in (MORAN_NEED, MORAN_ATTENTION, MORAN_RESIDUALS) if k in moran
                ),
                scatter=need_scatter(
                    f"streu-{hypothesis.name.lower()}",
                    points,
                    need_label,
                    attention_label,
                    _axis_format(hypothesis.need),
                    _axis_format(hypothesis.attention),
                ),
                notes=_test_notes(
                    main["ergebnis"] == "bestätigt", within_pair, moran.get(MORAN_RESIDUALS)
                ),
            )
        )
    pairs = tuple(
        Pair(
            labels.get(r["bedarf"], r["bedarf"]),
            labels.get(r["aufmerksamkeit"], r["aufmerksamkeit"]),
            float(r["wert"]),
            _float(r["p"]),
            int(r["n"]),
        )
        for r in rows
        if r["rechnung"] == PAIR and r["wert"] is not None
    )
    return tuple(found), pairs


def _axis_format(column: str) -> Callable[[float], str]:
    if column.startswith("anteil_") and column not in ("anteil_u18",):
        return _percent
    if column in ("wahlbeteiligung",):
        return _percent
    if column in ("anteil_u18", "mindestsicherung"):
        return _fmt(1, " %")
    return _fmt(2)


# --- Das Modell der Seite -----------------------------------------------------------------------------
@dataclass(frozen=True)
class ClassFacts:
    """Wie viele Dokumente der Klasse mit Treffer zählen und wie viele davon nie im Ausschuss waren."""

    traffic_codes: tuple[str, ...]  # die Klassen der Verkehrsdokumente (Profil)
    with_hit: int  # Dokumente der Klasse mit Treffer in mindestens einem Wahlbezirk


@dataclass(frozen=True)
class NeedModel:
    """Alles, was ``bedarf.html`` braucht."""

    districts: tuple[District, ...]
    maps: tuple[MapPanel, ...]
    sources: tuple[Source, ...]
    accidents: Accidents
    band_m: float
    residents: float
    tests: tuple[Test, ...]
    pairs: tuple[Pair, ...]
    alpha: float  # Schwelle nach Holm
    power: tuple[float, float] | None  # |ρ| mit 80 % Power bei α und α/m; None ohne Tests
    classes: ClassFacts | None  # None ohne Klassen in diesem Profil
    check: ClassCheck | None  # None ohne Klassen: dann gibt es nichts zu prüfen
    with_context: bool
    school_need: tuple[float, float | None] | None  # ρ und p Handlungsbedarf gegen Schulsozialindex
    missing: tuple[str, ...]  # was in diesem Profil fehlt, je ein Satz
    period_start: str
    period_end: str

    @property
    def commits(self) -> tuple[tuple[str, str], ...]:
        """(Commit, Tag) der Festlegungen, jede einmal, in der Folge der Tests."""
        return tuple(dict.fromkeys((t.commit, t.fixed_on) for t in self.tests))


def _missing(
    settings: Settings, with_context: bool, with_classes: bool, with_tests: bool
) -> tuple[str, ...]:
    lines = []
    if not with_context:
        lines.append(
            "Keine Fremddaten zur sozialen Lage (kein Quartiersatlas oder ähnlicher Datensatz der "
            "Stadt): sozialer Handlungsbedarf und Anteil unter 18 fehlen; die Karten zeigen statt "
            "des Handlungsbedarfs den Schulsozialindex des Landes."
        )
    if not with_classes:
        lines.append(
            "Kein Ausschussklassifikator: die Drucksachennummern tragen kein Ausschusskürzel, also "
            f"gibt es keine Klassen. Die Anteile {TRAFFIC} und {YOUTH} fehlen und mit ihnen die "
            "Tests, die sie brauchen."
        )
    if not with_tests:
        lines.append(
            "Keine vorab festgelegten Hypothesen für diesen Datensatz: es gibt keine Tests und "
            "keine explorativen Paare; der Abschnitt „Bedarf und Nennung“ beschreibt nur."
        )
    return tuple(lines)


def class_facts(settings: Settings, committees: pl.DataFrame, results: pl.DataFrame) -> ClassFacts:
    """Die Dokumente der Verkehrsklasse mit Treffer (der Zähler von ``anteil_verkehr``, § 4.1)."""
    traffic = tuple(settings.context.need.classes.traffic)
    hits = results.select(pl.col("paper_ids").explode().drop_nulls().unique())
    with_hit = committees.filter(pl.col("ausschuss").is_in(list(traffic))).join(
        hits.rename({"paper_ids": "id"}), on="id", how="inner"
    )
    return ClassFacts(traffic, with_hit.height)


def rank_correlation(a: Sequence[float], b: Sequence[float]) -> float | None:
    """Spearmans ρ mit mittleren Rängen; ``None`` ohne Streuung oder unter drei Werten."""
    if len(a) < 3 or len(a) != len(b):
        return None
    frame = pl.DataFrame({"a": list(a), "b": list(b)}).with_columns(
        pl.col("a").rank("average"), pl.col("b").rank("average")
    )
    value = frame.select(pl.corr("a", "b")).item()
    return None if value is None or not math.isfinite(float(value)) else float(value)


@dataclass(frozen=True)
class NeedInputs:
    """Die Dateien der Seite, gelesen; ``None`` heißt in diesem Profil nicht da."""

    table: pl.DataFrame
    tests: pl.DataFrame | None
    context: pl.DataFrame | None
    accidents_in_period: int
    committees: pl.DataFrame | None
    results: pl.DataFrame
    names: dict[int, str]
    shapes: dict[int, Any]
    context_units: int


def build_need(inputs: NeedInputs, settings: Settings, check: ClassCheck | None) -> NeedModel:
    """Das Modell aus den gelesenen Tabellen; rein."""
    need = settings.context.need
    table = inputs.table.sort("wahlkreis_id")
    districts = districts_of(table, inputs.context, inputs.names)
    with_context = inputs.context is not None and any(d.need_score is not None for d in districts)
    with_classes = inputs.committees is not None and need.with_classes()
    with_tests = inputs.tests is not None and bool(need.hypotheses)
    accidents = Accidents(
        total=inputs.accidents_in_period,
        located=float(table.get_column("unfaelle").sum()),
        shared=float(table.get_column("unfaelle_geteilt").sum()),
        sharp_rank=rank_correlation(
            table.get_column("unfaelle").to_list(), table.get_column("unfaelle_scharf").to_list()
        ),
    )
    maps = [
        small_map(
            "unfaelle",
            "Unfälle je 1 000 Einwohner",
            {d.id: d.accidents_rate for d in districts},
            inputs.shapes,
            inputs.names,
            _fmt(1),
        )
    ]
    if with_context:
        maps.append(
            small_map(
                "handlungsbedarf",
                column_labels(settings).get("hb_score", "Sozialer Handlungsbedarf"),
                {d.id: d.need_score for d in districts},
                inputs.shapes,
                inputs.names,
                _fmt(2),
            )
        )
        maps.append(
            small_map(
                "unter18",
                column_labels(settings).get("anteil_u18", "Anteil unter 18 Jahren"),
                {d.id: d.youth for d in districts},
                inputs.shapes,
                inputs.names,
                _fmt(1, " %"),
            )
        )
    else:
        maps.append(
            small_map(
                "schulsozialindex",
                COLUMN_LABELS["sozialindex_schulen"],
                {d.id: d.school_index for d in districts},
                inputs.shapes,
                inputs.names,
                _fmt(1),
            )
        )
    tests: tuple[Test, ...] = ()
    pairs: tuple[Pair, ...] = ()
    if inputs.tests is not None:
        analysis = table
        if inputs.context is not None:
            analysis = analysis.join(inputs.context, on="wahlkreis_id", how="left")
        analysis = analysis.join(
            inputs.results.select("wahlkreis_id", "trefferquote", "wahlbeteiligung"),
            on="wahlkreis_id",
            how="left",
        ).sort("wahlkreis_id")
        tests, pairs = tests_of(inputs.tests, settings, analysis, inputs.names)
    school_need = None
    if inputs.tests is not None:
        for row in inputs.tests.filter(
            (pl.col("rechnung") == PAIR)
            & (pl.col("bedarf") == "hb_score")
            & (pl.col("aufmerksamkeit") == "sozialindex_schulen")
        ).iter_rows(named=True):
            if row["wert"] is not None:  # ohne Fremddaten bleibt die Zeile ohne Wert
                school_need = (float(row["wert"]), _float(row["p"]))
    n = len(districts)
    m = len(need.hypotheses)
    power = (
        (power_threshold(n, need.alpha), power_threshold(n, need.alpha / m))
        if tests and n > 3
        else None
    )
    period = settings.period
    return NeedModel(
        districts=districts,
        maps=tuple(maps),
        sources=sources(settings, table, accidents, inputs.context_units),
        accidents=accidents,
        band_m=need.band_m,
        residents=float(table.get_column("einwohner_zensus").sum()),
        tests=tests,
        pairs=pairs,
        alpha=need.alpha,
        power=power,
        classes=class_facts(settings, inputs.committees, inputs.results)
        if with_classes and inputs.committees is not None
        else None,
        check=check if with_classes else None,
        with_context=with_context,
        school_need=school_need,
        missing=_missing(settings, with_context, with_classes, with_tests),
        period_start=period.start.strftime("%d.%m.%Y"),
        period_end=period.end.strftime("%d.%m.%Y") if period.end else "",
    )


# --- Register: Schalter, Eingaben, Daten, Links -------------------------------------------------------
def need_enabled(settings: Settings) -> bool:
    """Der Schalter der Seite und der Tabellen: der Schritt ``need`` läuft (``context.need.enabled``)."""
    return settings.context.need.enabled


def _with_classes(settings: Settings) -> bool:
    return settings.context.need.with_classes() and settings.classify.enabled


def _with_tests(settings: Settings) -> bool:
    need = settings.context.need
    return bool(need.hypotheses or need.explore)


def need_inputs(layout: Layout, settings: Settings) -> tuple[Path, ...]:
    """Was ``page_bedarf`` liest: die Tabellen von 22, Unfälle, Flächen, Treffer, Klassen, Prüfung."""
    from georep.enrich.need import need_files

    files = need_files(layout)
    with_classes = _with_classes(settings)
    return (
        files.table,
        *((files.tests,) if _with_tests(settings) else ()),
        files.accidents,
        layout.precincts_geojson,
        layout.results,
        *((layout.papers_committee,) if with_classes else ()),
        *((layout.context_table, layout.crosswalk) if layout.context_root is not None else ()),
        *(check_files(settings) if with_classes else ()),
    )


def read_inputs(layout: Layout, settings: Settings) -> NeedInputs:
    """Die Dateien der Seite aus dem Layout."""
    from georep.enrich.need import need_files
    from georep.prep.context import in_period
    from georep.report.model import crosswalk_units, district_names

    files = need_files(layout)
    precincts = read_canonical_precincts(layout.precincts_geojson, settings.geo.working_crs)
    period = settings.period
    with_context = layout.context_root is not None and layout.context_table.is_file()
    return NeedInputs(
        table=pl.read_parquet(files.table),
        tests=pl.read_parquet(files.tests)
        if _with_tests(settings) and files.tests.is_file()
        else None,
        context=pl.read_parquet(layout.context_table) if with_context else None,
        accidents_in_period=in_period(
            pl.read_parquet(files.accidents, columns=["jahr", "monat"]), period.start, period.end
        ).height,
        committees=pl.read_parquet(layout.papers_committee, columns=["id", "ausschuss"])
        if _with_classes(settings)
        else None,
        results=pl.read_parquet(
            layout.results, columns=["wahlkreis_id", "paper_ids", "trefferquote", "wahlbeteiligung"]
        ),
        names=district_names(precincts),
        shapes=district_shapes(precincts, SIMPLIFY_M),
        context_units=crosswalk_units(layout) if with_context else 0,
    )


def repository_links(settings: Settings) -> dict[str, str]:
    """Messdokument, README der Prüfung, Commits der Festlegung; Vorlage und Allowlist lesen dieselben."""
    from georep.report.render import DECISIONS, REPOSITORY

    folder = settings.validation.root.name
    links = {
        "measurement": f"{REPOSITORY}/blob/main/{MEASUREMENT}",
        "decisions": DECISIONS,
        "check": f"{REPOSITORY}/blob/main/{folder}/{VALIDATION_PROJECT}/README.md",
        "check_folder": f"{folder}/{VALIDATION_PROJECT}",
    }
    for hypothesis in settings.context.need.hypotheses:
        links[f"commit-{hypothesis.fixed}"] = f"{REPOSITORY}/commit/{hypothesis.fixed}"
    return links


def need_data(layout: Layout, settings: Settings) -> Mapping[str, object]:
    """``Page.data``: die Dateien lesen, das Modell bauen."""
    check = read_check(settings) if _with_classes(settings) else None
    model = build_need(read_inputs(layout, settings), settings, check)
    return {
        "bedarf": model,
        "urls": repository_links(settings),
        "traffic": TRAFFIC,
        "youth": YOUTH,
        "accuracy": CLASS_CHECK_ACCURACY,
        "precision_floor": PRECISION_FLOOR,
        "p_text": p_text,
    }


def need_links(layout: Layout, settings: Settings) -> frozenset[str]:
    """Die Links nach außen: Messdokument, Prüfung, Commits, Datensätze und Lizenzen der Quellen."""
    need = settings.context.need
    links = {v for k, v in repository_links(settings).items() if k != "check_folder"}
    for attribution in (
        need.accidents.attribution,
        need.grid.attribution,
        need.schools.attribution,
    ):
        links |= {attribution.url, attribution.license_url}
    if layout.context_root is not None:
        links |= {settings.context.dataset.url, settings.context.dataset.license_url}
    return frozenset(link for link in links if link)
