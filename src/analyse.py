from __future__ import annotations

import pandas as pd

import src.config as cfg
from georep.io import atomic_path


def build_hits_per_wahlkreis() -> pd.DataFrame:
    df_index = pd.read_csv(cfg.INVERTED_INDEX_PATH)
    df_suche = pd.read_csv(cfg.COMBINED_SEARCHDICT_PATH, sep=";")

    # Suchbegriffe von String -> Liste (", " als Trennzeichen)
    df_suche["suchbegriffe"] = df_suche["suchbegriffe"].str.split(", ")

    # Jede Kombination (wahlkreis_id, suchbegriff) als eigene Zeile
    df_suche_exploded = df_suche.explode(column="suchbegriffe")

    # Merge mit invertiertem Index
    df = df_suche_exploded.merge(df_index, on="suchbegriffe", how="inner")

    # Aggregation pro Wahlkreis
    df_hits = (
        df.groupby("wahlkreis_id")
        .agg(
            {
                "suchbegriffe": (
                    lambda x: "; ".join(
                        sorted(set(val for val in x if pd.notna(val) and val != "schulweg"))
                    )
                ),
                "paper_ids": (
                    lambda x: ";".join(
                        sorted(
                            set(
                                pid
                                for val in x
                                if pd.notna(val)
                                for pid in str(val).split(";")
                                if pid
                            )
                        )
                    )
                ),
            }
        )
        .reset_index()
    )

    # Anzahl der eindeutigen Dokumente pro Wahlkreis
    df_hits["anzahl_treffer"] = df_hits["paper_ids"].apply(
        lambda s: len(s.split(";")) if isinstance(s, str) and s else 0
    )

    return df_hits


def join_with_voter_data(df_hits: pd.DataFrame) -> pd.DataFrame:
    df_votes = pd.read_csv(cfg.AGG_VOTERS_PER_WAHLBEZIRK_PATH)

    df = df_hits.merge(df_votes, on="wahlkreis_id", how="inner")

    # Treffequote (Treffer pro Wahlberechtigtem)
    df["trefferquote"] = df["anzahl_treffer"] / df["Wahlberechtigte_insgesamt"]

    return df


def main() -> None:
    df_hits = build_hits_per_wahlkreis()
    df_final = join_with_voter_data(df_hits)

    with atomic_path(cfg.AUSWERTUNG_PATH) as tmp:
        df_final.to_csv(tmp, index=False)

    print(f"Ergebnis gespeichert unter: {cfg.AUSWERTUNG_PATH}")


if __name__ == "__main__":
    main()
