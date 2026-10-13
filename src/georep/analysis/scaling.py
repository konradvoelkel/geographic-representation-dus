"""Normierte Kennzahlen je Wahlbezirk: Treffer je Begriff, je 1000 Wahlberechtigte, Abweichung.

Die Trefferzahl eines Wahlbezirks hängt an der Größe seines Wörterbuchs (r = 0,7595 auf der
Referenz), nicht an seiner Einwohnerzahl (r = 0,1734): das ist die stärkste Verzerrung der Methode
(``docs/methodik-review-2026-10.md``, § 1). Dieses Modul rechnet die Kennzahlen, mit denen die Seite
sie sichtbar macht — die Entscheidungen dazu stehen in ``docs/decisions.md``, Punkt 46, die Messungen
in ``docs/skalierung-2026-10.md``.

Zwei Regeln gelten hier für die ganze Seite:

* **Ein Mittel ist das ungewichtete Mittel der Einheiten** (``unweighted_mean``): das Stadtmittel ist
  das Mittel der 41 Bezirksquoten, nicht die gepoolte Quote aus allen Treffern und allen
  Wahlberechtigten; das Parteimittel (``analysis.parties``) ist das Mittel der Parteianteile, nicht
  der nach Dokumentzahl gewichtete Durchschnitt.
* **Ein Verhältnis zu einem Mittel von 0 ist 0, nicht unendlich** (``relative_to``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import deal
import polars as pl

from georep.analysis.hits import DISTRICT, RATE, TERMS
from georep.contracts import all_nonnegative, has_columns, sorted_unique
from georep.errors import SchemaError
from georep.prep.voters import ELIGIBLE_TOTAL
from georep.search.index import HITS

TERM_COUNT = "begriffe"
PER_TERM = "treffer_je_begriff"
PER_1000 = "treffer_je_1000"
CITY_MEAN = "stadtmittel"
DEVIATION = "abweichung_stadtmittel"
PER_1000_FACTOR = 1000.0

METRIC_COLUMNS = (
    DISTRICT,
    HITS,
    TERM_COUNT,
    PER_TERM,
    RATE,
    PER_1000,
    CITY_MEAN,
    DEVIATION,
)


def unweighted_mean(value: str, by: Sequence[str] = ()) -> pl.Expr:
    """Das ungewichtete Mittel der Einheiten, je Gruppe oder über den ganzen Frame.

    Jede Einheit zählt gleich: ein Wahlbezirk ist ein Gebiet und keine Menge Personen, eine Partei
    ist eine Stimme und kein Stapel Dokumente (``docs/decisions.md``, Punkt 46). Die gewichteten
    Varianten sind gemessen und verworfen, nicht vergessen.
    """
    mean = pl.col(value).mean()
    return mean.over(list(by)) if by else mean


def relative_to(value: str, mean: str) -> pl.Expr:
    """Verhältnis zum Mittel; 1 heißt „genau im Mittel", 0 heißt „die Gruppe hat kein Mittel".

    Ohne den Zweig wäre das Verhältnis dort, wo keine Partei des Wahlbezirks ein Dokument hat,
    eine Division durch 0 und damit unendlich oder NaN; Klassengrenzen und Legende könnten damit
    nichts anfangen. **Achtung bei der Abweichung:** ``relative_to(...) - 1`` ist ohne Mittel
    nicht 0, sondern -1 -- „kein Mittel" hieße dann „ganz unten statt genau in der Mitte". Wer
    eine Abweichung will, nimmt ``deviation_from``.
    """
    return pl.when(pl.col(mean) > 0).then(pl.col(value) / pl.col(mean)).otherwise(0.0)


def deviation_from(value: str, mean: str) -> pl.Expr:
    """Relative Abweichung vom Mittel: 0 heißt „genau im Mittel", +0,5 „50 Prozent darüber".

    Ohne Mittel (keine Einheit der Gruppe hat einen Wert) ist die Abweichung 0 und nicht -1: es
    gibt dann nichts, wovon etwas abweichen könnte, und jede andere Zahl wäre eine Behauptung.
    Der Fall ist nicht theoretisch -- eine Stichprobe ohne extrahierte Texte hat ihn (``fetch
    pdfs --limit N``, ein frisches Profil), und mit -1,0 je Bezirk bräche die Nachbedingung
    „die Abweichungen summieren sich auf 0" und mit ihr der ganze Lauf.
    """
    return pl.when(pl.col(mean) > 0).then(pl.col(value) / pl.col(mean) - 1.0).otherwise(0.0)


def _every_district_has_a_dictionary(
    results: pl.DataFrame, dictionary: pl.DataFrame, result: pl.DataFrame | None = None
) -> bool:
    assert result is not None
    return result.height == results.height


def _the_deviations_add_up_to_zero(
    results: pl.DataFrame, dictionary: pl.DataFrame, result: pl.DataFrame | None = None
) -> bool:
    """Die Abweichungen vom Mittel heben sich auf — der Beweis, dass es das Mittel dieser Zahlen ist."""
    assert result is not None
    total = result.get_column(DEVIATION).sum()
    return total is not None and abs(float(total)) < 1e-9 * max(result.height, 1)


@deal.pre(
    lambda results, dictionary: (
        has_columns(results, DISTRICT, HITS, RATE, ELIGIBLE_TOTAL)
        and has_columns(dictionary, DISTRICT, TERMS)
    )
)
@deal.post(lambda result: list(result.columns) == list(METRIC_COLUMNS))
@deal.post(lambda result: sorted_unique(result, DISTRICT))
@deal.post(lambda result: all_nonnegative(result, TERM_COUNT, PER_TERM, PER_1000))
@deal.ensure(_every_district_has_a_dictionary, message="jeder Wahlbezirk hat ein Wörterbuch")
@deal.ensure(_the_deviations_add_up_to_zero, message="die Abweichungen summieren sich auf 0")
@deal.raises(SchemaError)
def district_metrics(results: pl.DataFrame, dictionary: pl.DataFrame) -> pl.DataFrame:
    """Je Wahlbezirk die vier Lesarten derselben Treffer: roh, je Begriff, je 1000, relativ.

    ``treffer_je_1000`` ist die Trefferquote mit einem Faktor und darum dieselbe Rangfolge;
    ``treffer_je_begriff`` ordnet die Bezirke neu (auf der Referenz 28 von 41 Quantilklassen
    anders), ``abweichung_stadtmittel`` ist eine streng monotone Umrechnung der Quote und bekommt
    auf der Seite darum feste Klassengrenzen statt Quantile.

    Sonderfälle, beide mit 0 beantwortet statt mit einem Fehler: ein Wörterbuch ohne Begriffe hat
    keine Treffer je Begriff, und eine Stadt ohne einen einzigen Treffer hat kein Stadtmittel und
    damit keine Abweichung davon (``deviation_from``). Beides kommt in einer Stichprobe vor.
    """
    sizes = dictionary.select(DISTRICT, pl.col(TERMS).list.len().cast(pl.Int64).alias(TERM_COUNT))
    missing = sorted(set(results.get_column(DISTRICT)) - set(sizes.get_column(DISTRICT)))
    if missing:
        raise SchemaError(f"Wahlbezirke ohne Wörterbuch: {missing}")
    return (
        results.select(DISTRICT, HITS, RATE)
        .join(sizes, on=DISTRICT, how="inner")
        .with_columns(
            pl.when(pl.col(TERM_COUNT) > 0)
            .then(pl.col(HITS) / pl.col(TERM_COUNT))
            .otherwise(0.0)
            .alias(PER_TERM),
            (pl.col(RATE) * PER_1000_FACTOR).alias(PER_1000),
            unweighted_mean(RATE).alias(CITY_MEAN),
        )
        .with_columns(deviation_from(RATE, CITY_MEAN).alias(DEVIATION))
        .select(*METRIC_COLUMNS)
        .sort(DISTRICT)
    )


@dataclass(frozen=True)
class DictionaryBias:
    """Wie stark die Größe des Wörterbuchs die Trefferzahl treibt (Punkt 46).

    Die Zahlen des Methodenabsatzes der Seite. Sie stehen nicht im Text, weil eine zweite Stadt
    andere hat: ``r`` ist Pearson über die Wahlbezirke.
    """

    districts: int
    hits_terms: float  # Treffer gegen Zahl der Begriffe -- die Verzerrung
    hits_eligible: float  # Treffer gegen Wahlberechtigte -- die Normierung der Arbeit
    per_term_terms: float  # Treffer je Begriff gegen Zahl der Begriffe -- die Überkorrektur
    terms_min: int
    terms_max: int
    eligible_spread: float  # größte durch kleinste Wahlberechtigtenzahl


def _pearson(frame: pl.DataFrame, left: str, right: str) -> float | None:
    """Pearson zweier Spalten; ``None``, wenn eine keine Streuung hat (wie ``regression.spearman``)."""
    from scipy.stats import pearsonr

    if frame.height < 3:
        return None
    if frame.get_column(left).n_unique() < 2 or frame.get_column(right).n_unique() < 2:
        return None
    found = float(
        pearsonr(frame.get_column(left).to_numpy(), frame.get_column(right).to_numpy()).statistic
    )
    return None if math.isnan(found) else found


@deal.pre(
    lambda metrics, results, eligible_column=ELIGIBLE_TOTAL: (
        has_columns(metrics, DISTRICT, HITS, TERM_COUNT, PER_TERM)
        and has_columns(results, DISTRICT, eligible_column)
    )
)
def dictionary_bias(
    metrics: pl.DataFrame, results: pl.DataFrame, eligible_column: str = ELIGIBLE_TOTAL
) -> DictionaryBias | None:
    """Die drei Korrelationen des Methodenabsatzes; ``None``, wenn eine Spalte keine Streuung hat.

    Ohne Streuung gibt es keine Korrelation, und ein Absatz, der „r = nan" sagt, ist schlechter
    als keiner: die Seite lässt ihn dann weg (eine Mini-Fixture oder eine Stichprobe hat den Fall).
    """
    frame = metrics.join(results.select(DISTRICT, eligible_column), on=DISTRICT, how="inner")
    pairs = (
        _pearson(frame, HITS, TERM_COUNT),
        _pearson(frame, HITS, eligible_column),
        _pearson(frame, PER_TERM, TERM_COUNT),
    )
    if any(value is None for value in pairs):
        return None
    terms = [int(value) for value in frame.get_column(TERM_COUNT).to_list()]
    eligible = [int(value) for value in frame.get_column(eligible_column).to_list()]
    hits_terms, hits_eligible, per_term_terms = (value for value in pairs if value is not None)
    return DictionaryBias(
        districts=frame.height,
        hits_terms=hits_terms,
        hits_eligible=hits_eligible,
        per_term_terms=per_term_terms,
        terms_min=min(terms),
        terms_max=max(terms),
        eligible_spread=max(eligible) / min(eligible) if min(eligible) > 0 else 0.0,
    )


def _de(value: float) -> str:
    """Drei Stellen mit Komma; ``report.model.format_de`` gehört zur Seite, nicht zur Analyse."""
    return f"{value:.3f}".replace(".", ",")


def summary(frame: pl.DataFrame) -> str:
    """Die Zeile, die der Schritt ``metrics`` ausgibt."""
    per_term = [float(value) for value in frame.get_column(PER_TERM).to_list()]
    terms = int(frame.get_column(TERM_COUNT).sum())
    return (
        f"{frame.height} Wahlbezirke, {terms} Begriffe, "
        f"{_de(min(per_term, default=0.0))} bis "
        f"{_de(max(per_term, default=0.0))} Treffer je Begriff"
    )
