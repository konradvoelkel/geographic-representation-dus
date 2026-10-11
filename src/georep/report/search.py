"""Sucheinträge der Berichtsseite: ein Eintrag je kanonischem Begriff, mit Bezirken und Dokumenten.

Reine Funktionen von Frames zu ``SearchEntry``; kein HTML, kein Dateizugriff, kein Stadtwissen.
``render.py`` kennt nur das Schema von ``search_payload``, das Abschnitts-Skript nur dieses JSON und
die DOM-Verträge der Seite (docs/plans/08-suche.md, § 9).

Ein Begriff mit Abkürzung (``münchener str.``) und seine Langform (``münchener straße``) stehen beide
im Wörterbuch, meinen aber dieselbe Straße: die Suche zieht sie zum kanonischen Begriff zusammen und
vereinigt die Dokumente beider Schreibweisen, damit ein Dokument mit beiden Schreibweisen einmal
zählt. Die Paare kommen aus ``STREET_ABBREVIATIONS`` (``georep.search.dictionary``), aus denen auch
das Wörterbuch selbst liest; so steht die Regel an einer Stelle und das JavaScript bekommt sie als
Daten (``abbreviations`` im Payload).

Schema von ``search_payload``::

    {"version": "0.10.0", "abbreviations": [["straße", "str."]],
     "kinds": {"s": "Straße", "o": "Ort", "w": "Wahlbezirk"},
     "entries": [["aachener straße", [14, 15, 16, 18], 61, "so"],
                 ["Altstadt, Carlstadt, Hofgarten", [1], 1894, "w"]]}

``fold`` und ``fold_ascii`` spiegeln die Normalisierung des Abschnitts-Skripts (``15-suche.js``):
sie stehen hier, damit ein Test beide Seiten vergleichen kann (``tests/unit/test_report_js_fold.py``)
und damit die Kollisionsprüfung (keine zwei Einträge derselben Art fallen zusammen) in Python läuft.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import deal
import polars as pl

from georep import __version__
from georep.contracts import has_columns
from georep.errors import SchemaError
from georep.search.dictionary import DISTRICT, STREET_ABBREVIATIONS
from georep.search.index import HITS, PAPER_IDS, TERM

LABEL = "label"  # Spalte der Ortstabelle (wikidata_vis.parquet)
KINDS = ("s", "o", "w")  # Straße, Ort, Wahlbezirk: diese Reihenfolge trägt jeder Eintrag
# Die einzigen deutschen Strings dieses Moduls; mit Option 10 wandern sie in die Vorlage.
KIND_LABELS = {"s": "Straße", "o": "Ort", "w": "Wahlbezirk"}
# Umlaute als zwei Buchstaben, für Tastaturen ohne Umlaute (zweiter Schlüssel je Eintrag).
UMLAUTS = (("ä", "ae"), ("ö", "oe"), ("ü", "ue"))
Abbreviations = Sequence[tuple[str, str]]


@dataclass(frozen=True)
class SearchEntry:
    """Ein Vorschlag der Suche: Begriff, Wahlbezirke, Dokumente mit Treffer, Art."""

    term: str
    districts: tuple[int, ...]
    documents: int
    kind: str  # Buchstaben aus KINDS in dieser Reihenfolge, etwa "s", "o", "so" oder "w"


# --- Kanonischer Begriff ------------------------------------------------------------------------


def _usable_pairs(abbreviations: Abbreviations) -> bool:
    """Beide Formen nicht leer, und die Abkürzung steckt nicht in ihrer Langform.

    ``("strasse", "str")`` wäre unbrauchbar: das Ersetzen der Abkürzung durch die Langform träfe
    die Langform selbst und liefe bei jedem Durchlauf weiter (``strasse`` → ``strassease``).
    """
    return all(
        long and short and short not in long and long not in short for long, short in abbreviations
    )


def _pairs_usable(term: str, abbreviations: Abbreviations = STREET_ABBREVIATIONS) -> bool:
    return _usable_pairs(abbreviations)


@deal.pre(
    _pairs_usable,
    message="Abkürzung und Langform nicht leer, und keine steckt in der anderen",
)
@deal.safe
def canonical_term(term: str, abbreviations: Abbreviations = STREET_ABBREVIATIONS) -> str:
    """Der Begriff mit jeder Abkürzung zurück in der Langform (``münchener str.`` → ``…straße``).

    Kein ``deal.pure``: die Funktion läuft über jeden Begriff des Wörterbuchs, und der Patcher von
    ``deal.pure`` ist prozessweit und nicht reentrant (CLAUDE.md, „Nie").
    """
    for long, short in abbreviations:
        term = term.replace(short, long)
    return term


# --- Faltung für den Abgleich (Spiegel von 15-suche.js) ------------------------------------------


def _plain(text: str, *, umlauts: bool) -> str:
    """Kleinschreiben, Umlaute oder Akzente auflösen, ``ß`` zu ``ss``, Whitespace bündeln.

    Reihenfolge wie im JavaScript: erst NFC, damit zerlegte Umlaute als ein Zeichen vorliegen, dann
    die Umlaut-Variante, dann NFD und alle Marken weg (``\\p{M}`` im JavaScript entspricht der
    Unicode-Kategorie ``M`` hier; ``unicodedata.combining`` wäre eine andere Menge).
    """
    folded = unicodedata.normalize("NFC", text.lower())
    if umlauts:
        for mark, pair in UMLAUTS:
            folded = folded.replace(mark, pair)
    folded = "".join(
        ch for ch in unicodedata.normalize("NFD", folded) if unicodedata.category(ch)[0] != "M"
    )
    return " ".join(folded.replace("ß", "ss").split())


def _fold(text: str, abbreviations: Abbreviations, *, umlauts: bool) -> str:
    """``_plain`` und danach jede Abkürzung durch die gefaltete Langform, auch ohne Punkt am Wortende."""
    folded = _plain(text, umlauts=umlauts)
    for long, short in abbreviations:
        target = _plain(long, umlauts=umlauts)
        folded = folded.replace(_plain(short, umlauts=umlauts), target)
        stem = short.rstrip(".")
        if stem != short:
            # „münchener str" ohne Punkt: nur am Wortende, damit „strandbad" unberührt bleibt.
            folded = re.sub(
                re.escape(_plain(stem, umlauts=umlauts)) + r"(?![0-9a-z])", target, folded
            )
    return folded


def fold(text: str, abbreviations: Abbreviations = STREET_ABBREVIATIONS) -> str:
    """Der Schlüssel für den Abgleich: ``Münchener Str.`` und ``münchener straße`` werden gleich."""
    return _fold(text, abbreviations, umlauts=False)


def fold_ascii(text: str, abbreviations: Abbreviations = STREET_ABBREVIATIONS) -> str:
    """Wie ``fold``, aber mit ``ä`` → ``ae``: der zweite Schlüssel für Tastaturen ohne Umlaute."""
    return _fold(text, abbreviations, umlauts=True)


# --- Sucheinträge -------------------------------------------------------------------------------


def _lowered(frame: pl.DataFrame, column: str) -> set[str]:
    """Die Werte einer Spalte (Liste oder String) kleingeschrieben und getrimmt wie im Wörterbuch."""
    series = frame.get_column(column)
    if series.dtype == pl.List(pl.String):
        series = series.explode()
    return {value.strip().lower() for value in series.drop_nulls().to_list() if value.strip()}


def _member(terms: set[str]) -> pl.Expr:
    """Ob der Begriff in einer Quellmenge steckt (Straßennamen oder Ortslabels, kleingeschrieben)."""
    return pl.col(TERM).is_in(pl.Series(TERM, sorted(terms), dtype=pl.String).implode())


def _canonical_expr(abbreviations: Abbreviations) -> pl.Expr:
    """Der kanonische Begriff als Polars-Ausdruck, wie ``canonical_term`` ihn rechnet."""
    canonical = pl.col(TERM)
    for long, short in abbreviations:
        canonical = canonical.str.replace_all(short, long, literal=True)
    return canonical


def _entry_order(result: tuple[SearchEntry, ...]) -> bool:
    keys = [(entry.term, entry.kind) for entry in result]
    return keys == sorted(keys) and len(set(keys)) == len(keys)


def _entry_shape(result: tuple[SearchEntry, ...]) -> bool:
    """Bezirke sortiert und nicht leer, Dokumente nicht negativ, Art eine Teilfolge von KINDS."""
    return all(
        entry.term
        and entry.districts == tuple(sorted(set(entry.districts)))
        and entry.documents >= 0
        and entry.kind
        and "".join(k for k in KINDS if k in entry.kind) == entry.kind
        for entry in result
    )


def _targets(terms: Sequence[str], abbreviations: Abbreviations) -> dict[str, str]:
    """Begriff → Eintrag, unter dem er liegt: die Langform, wenn sie selbst ein Begriff ist."""
    shown = set(terms)
    canonical = {term: canonical_term(term, abbreviations) for term in terms}
    return {term: long if long in shown else term for term, long in canonical.items()}


def _covers_every_term(
    dictionary: pl.DataFrame,
    index: pl.DataFrame,
    streets: pl.DataFrame,
    pois: pl.DataFrame,
    results: pl.DataFrame,
    names: Mapping[int, str],
    hidden: Sequence[str],
    abbreviations: Abbreviations = STREET_ABBREVIATIONS,
    result: tuple[SearchEntry, ...] = (),
) -> bool:
    """Jeder nicht versteckte Begriff liegt unter genau einem Eintrag, und die Zahl ist plausibel.

    Zweite Rechnung von Hand (``_targets``) gegen die Polars-Gruppierung der Funktion; dazu die
    Schranken der Vereinigung: zwischen dem Maximum einer Schreibweise und der Summe aller.
    """
    terms = [t for t in _displayed(dictionary, hidden) if t]
    entries = {entry.term: entry for entry in result if entry.kind != "w"}
    hits = dict(zip(*index.select(TERM, HITS).get_columns(), strict=True))
    members: dict[str, list[int]] = {}
    for term, target in _targets(terms, abbreviations).items():
        members.setdefault(target, []).append(int(hits.get(term, 0) or 0))
    if set(members) != set(entries):
        return False
    return all(
        max(counts) <= entries[target].documents <= sum(counts)
        for target, counts in members.items()
    )


def _displayed(dictionary: pl.DataFrame, hidden: Sequence[str]) -> list[str]:
    """Alle Begriffe des Wörterbuchs ohne die versteckten, eindeutig und sortiert."""
    return sorted(set(dictionary.get_column(TERM).explode().drop_nulls().to_list()) - set(hidden))


@deal.pre(
    lambda dictionary, index, streets, pois, results, names, hidden, abbreviations=STREET_ABBREVIATIONS: (
        has_columns(dictionary, DISTRICT, TERM)
        and has_columns(index, TERM, PAPER_IDS, HITS)
        and has_columns(streets, TERM)
        and has_columns(pois, LABEL)
        and has_columns(results, DISTRICT, HITS)
        and _usable_pairs(abbreviations)
    ),
    message="Wörterbuch, Index, Straßen, Orte und Auswertung mit ihren Spalten",
)
@deal.post(_entry_order, message="Einträge nach Begriff und Art sortiert, jedes Paar einmal")
@deal.post(_entry_shape, message="Bezirke sortiert und nicht leer, Art aus s, o, w in dieser Folge")
@deal.ensure(
    _covers_every_term, message="jeder Begriff unter genau einem Eintrag, Zahl in Schranken"
)
@deal.raises(SchemaError)
def search_entries(
    dictionary: pl.DataFrame,
    index: pl.DataFrame,
    streets: pl.DataFrame,
    pois: pl.DataFrame,
    results: pl.DataFrame,
    names: Mapping[int, str],
    hidden: Sequence[str],
    abbreviations: Abbreviations = STREET_ABBREVIATIONS,
) -> tuple[SearchEntry, ...]:
    """Die Vorschläge der Suche: je kanonischem Begriff einer, dazu einer je Wahlbezirksname.

    ``dictionary`` ist ``combined_searchdict.parquet`` (eine Zeile je Wahlbezirk), ``index`` der
    invertierte Index mit ``paper_ids``, ``streets`` und ``pois`` die Quellen der Art (``s``, ``o``),
    ``results`` liefert ``anzahl_treffer`` je Bezirk für die Namenseinträge, ``names`` die Namen aus
    dem GeoJSON. ``hidden`` sind die Begriffe, die die Seite nicht anzeigt (``schulweg``).
    """
    seen = set(results.get_column(DISTRICT).to_list()) | set(
        dictionary.get_column(DISTRICT).to_list()
    )
    unnamed = sorted(int(district) for district in seen if int(district) not in names)
    if unnamed:
        raise SchemaError(f"Wahlbezirke ohne Namen: {unnamed}")
    pairs = (
        dictionary.select(DISTRICT, TERM)
        .explode(TERM)
        .drop_nulls(TERM)
        .filter(~pl.col(TERM).is_in(pl.Series(TERM, list(hidden), dtype=pl.String).implode()))
    )
    shown = pl.Series(TERM, _displayed(dictionary, hidden), dtype=pl.String)
    street_terms = _lowered(streets, TERM)
    poi_terms = _lowered(pois, LABEL)
    canonical = _canonical_expr(abbreviations)
    grouped = (
        pairs.with_columns(
            pl.when(canonical.is_in(shown.implode()))
            .then(canonical)
            .otherwise(pl.col(TERM))
            .alias("ziel"),
            _member(street_terms).alias("s"),
            _member(poi_terms).alias("o"),
        )
        .join(index.select(TERM, PAPER_IDS), on=TERM, how="left")
        .group_by("ziel")
        .agg(
            pl.col(DISTRICT).unique().sort(),
            pl.col(PAPER_IDS).explode().drop_nulls().n_unique().alias("dokumente"),
            pl.col("s").any(),
            pl.col("o").any(),
        )
    )
    entries = [
        SearchEntry(
            row["ziel"],
            tuple(int(d) for d in row[DISTRICT]),
            int(row["dokumente"]),
            "".join(kind for kind in ("s", "o") if row[kind]),
        )
        for row in grouped.iter_rows(named=True)
    ]
    sourceless = sorted(entry.term for entry in entries if not entry.kind)
    if sourceless:
        raise SchemaError(f"Begriffe ohne Quelle in Straßen oder Orten: {sourceless[:10]}")
    entries.extend(_name_entries(results, names))
    return tuple(sorted(entries, key=lambda entry: (entry.term, entry.kind)))


def _name_entries(results: pl.DataFrame, names: Mapping[int, str]) -> list[SearchEntry]:
    """Je Wahlbezirksname ein Eintrag der Art ``w``: „Benrath" steht in keinem Wörterbuch.

    Tragen zwei Wahlbezirke denselben Namen (in den Referenzdaten keiner), fasst der Eintrag sie
    zusammen; ``documents`` ist dann das Maximum, weil sich die Vereinigung der Dokumente aus
    ``anzahl_treffer`` allein nicht rechnen lässt.
    """
    merged: dict[str, tuple[list[int], int]] = {}
    for district, hits in results.select(DISTRICT, HITS).sort(DISTRICT).iter_rows():
        name = names[int(district)]
        districts, best = merged.setdefault(name, ([], 0))
        districts.append(int(district))
        merged[name] = (districts, max(best, int(hits)))
    return [
        SearchEntry(name, tuple(sorted(districts)), hits, "w")
        for name, (districts, hits) in merged.items()
    ]


def _payload_shape(result: dict[str, object]) -> bool:
    return list(result) == ["version", "abbreviations", "kinds", "entries"]


@deal.post(_payload_shape, message="version, abbreviations, kinds, entries in dieser Folge")
def search_payload(
    entries: Sequence[SearchEntry],
    abbreviations: Abbreviations = STREET_ABBREVIATIONS,
    *,
    version: str = __version__,
) -> dict[str, object]:
    """Das JSON für den Block ``<script id="suche-daten">``: kompakt, ein Eintrag je Zeile."""
    return {
        "version": version,
        "abbreviations": [list(pair) for pair in abbreviations],
        "kinds": dict(KIND_LABELS),
        "entries": [
            [entry.term, list(entry.districts), entry.documents, entry.kind] for entry in entries
        ],
    }
