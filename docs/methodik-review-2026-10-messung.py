"""Rechnet die Kennzahlen des Methodik-Reviews nach (`methodik-review-2026-10.md`, § 1 und § 4).

    uv run python docs/methodik-review-2026-10-messung.py

Liest nur, schreibt nichts: ``reference/`` ist der Stand der Arbeit (Regeln aus, die Zahlen von
§ 1), ``data_root/processed/`` der gerechnete Stand, falls ein Lauf vorliegt (Regeln an, die
Zahlen von § 4). Rund vier Sekunden; den größten Teil braucht der Matcher über die
Ausschlussliste.

Tabelle 5 und die Wirkung der Regeln frieren die slow-Tests in ``tests/golden/test_pipeline.py``
ein. Dieses Skript ist für die Kennzahlen daneben, die kein Test trägt — vor allem die
Korrelationen aus § 1, die wichtigste Grenze der Methode.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from georep.layout import Layout
from georep.search.index import build_index
from georep.settings import Settings, load_settings

CORRELATIONS = {
    "Treffer gegen Zahl der Begriffe": ("anzahl_treffer", "begriffe"),
    "Treffer gegen Wahlberechtigte": ("anzahl_treffer", "Wahlberechtigte_insgesamt"),
    "Trefferquote gegen Zahl der Begriffe": ("trefferquote", "begriffe"),
    "Trefferquote gegen Wahlberechtigte": ("trefferquote", "Wahlberechtigte_insgesamt"),
}


def report(name: str, results: pl.DataFrame, dictionary: pl.DataFrame, index: pl.DataFrame) -> None:
    """Die Maßzahlen eines Stands: Größen, Korrelationen, Faktor der Zählung je Dokument."""
    sizes = dictionary.select("wahlkreis_id", pl.col("suchbegriffe").list.len().alias("begriffe"))
    joined = results.join(sizes, on="wahlkreis_id")
    size, frequency = sizes.get_column("begriffe"), index.get_column("anzahl_treffer")
    eligible = results.get_column("Wahlberechtigte_insgesamt")
    hits = int(results.get_column("anzahl_treffer").sum())
    print(f"\n=== {name} ===")
    print(f"  {results.height} Wahlbezirke, {index.height} Begriffe, {hits} Treffer")
    print(f"  Begriffe je Wahlbezirk: Median {size.median():.0f}, {size.min()} bis {size.max()}")
    print(
        f"  Dokumenthäufigkeit: Median {frequency.median():.0f}, 90 % {frequency.quantile(0.9):.0f}"
        f", 99 % {frequency.quantile(0.99):.0f}, Maximum {frequency.max()}, "
        f"Summe {frequency.sum()} Begriff-Dokument-Paare"
    )
    print(
        f"  Wahlberechtigte: {eligible.min()} bis {eligible.max()}, Median {eligible.median():.0f}"
    )
    for label, (left, right) in CORRELATIONS.items():
        print(f"  r({label}) = {joined.select(pl.corr(left, right)).item():.3f}")
    # Ein Tripel ist (Wahlbezirk, Begriff, Dokument): die Dokumenthäufigkeit jedes Begriffs, über
    # alle Wörterbücher summiert, die ihn führen.
    frequencies = dict(
        zip(
            index.get_column("suchbegriffe"),
            index.get_column("anzahl_treffer").to_list(),
            strict=True,
        )
    )
    triples = sum(
        frequencies.get(term, 0)
        for row in dictionary.get_column("suchbegriffe").to_list()
        for term in row
    )
    print(
        f"  {triples} Bezirk-Begriff-Dokument-Tripel, Faktor {triples / hits:.2f} zu den Treffern"
    )


def thesis_state(layout: Layout) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Die drei CSV-Ausgaben der Arbeit; Listenspalten stehen dort mit Trennzeichen."""
    processed = layout.reference_root / "processed"
    results = pl.read_csv(processed / "wahlbezirke_auswertung.csv", infer_schema_length=None)
    dictionary = pl.read_csv(processed / "combined_searchdict.csv", separator=";").with_columns(
        pl.col("suchbegriffe").str.split(", ")
    )
    index = pl.read_csv(
        processed / "inverted_index.csv",
        infer_schema_length=None,
        schema_overrides={"paper_ids": pl.String},
    )
    return results, dictionary, index


def excluded_names(layout: Layout, settings: Settings) -> None:
    """§ 2.2: was die Ausschlussliste fernhält. Der Matcher läuft dafür einmal über den Korpus."""
    corpus = pl.read_parquet(layout.corpus, columns=["id", "text"])
    names = sorted({name.strip().lower() for name in settings.search.exclude})
    found = build_index(corpus, names).sort("anzahl_treffer", descending=True)
    print(f"\n=== Ausschlussliste über {corpus.height} Dokumente ===")
    print(
        f"  {len(names)} Namen, zusammen {int(found.get_column('anzahl_treffer').sum())} "
        "Begriff-Dokument-Paare"
    )
    for row in found.head(5).iter_rows(named=True):
        print(f"    {row['anzahl_treffer']:5d}  {row['suchbegriffe']}")


def main() -> None:
    settings = load_settings(cwd=Path.cwd())
    layout = Layout(settings.data_root, settings.cache_dir, settings.reference_root)
    report("Stand der Arbeit (reference/, Regeln aus)", *thesis_state(layout))
    if layout.results.is_file() and layout.index.is_file():
        report(
            f"Gerechneter Stand ({layout.results.parent}, Regeln wie in den Settings)",
            pl.read_parquet(layout.results),
            pl.read_parquet(layout.dictionary),
            pl.read_parquet(layout.index),
        )
    else:
        print(f"\n(kein Lauf unter {layout.results.parent}: `uv run georep run`)")
    if layout.corpus.is_file():
        excluded_names(layout, settings)


if __name__ == "__main__":
    main()
