"""Rechnet jede Zahl von `befunde-2026-10-14.md` aus den Läufen der vier Netzabrufe nach.

    uv run python docs/befunde-2026-10-14-messung.py [--perioden] [--staedte] [--laufend]
                                                     [--vollabruf] [--qualitaet]

Ohne Schalter läuft alles (rund zwei Sekunden; § 4 liest zwei JSONL-Dateien mit zusammen 28 MB).
Die Pfade kommen je Profil aus `load_settings(profile=...)` und `Layout.from_settings`, gelesen
wird nur: `processed/*.parquet`, `interim/papers.parquet`, `site/data/summary.json`,
`site/data/wahlbezirke.geojson`, der Vollabruf der Metadaten unter
`<data_root>/../data-vollabruf/duesseldorf/raw/papers.jsonl` und `snapshots/2014-2020/raw/
papers.jsonl` im Repo. Geschrieben wird nichts.

Was hier steht und nicht in einem Test: alles, was an Konrads vier Netzläufen hängt und darum
weder in `reference/` noch in einem Paket liegt — die Beratungsfolge des Vollabrufs, die
Rangkorrelation zwischen den Perioden, die Monatsvergleiche der laufenden Periode. Die
Tabellenwerte selbst friert `tests/golden/test_pipeline.py` ein.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import polars as pl

from georep.analysis.regression import regress, regression_pair, spearman
from georep.layout import Layout
from georep.settings import load_settings

# Paketprofil -> Ordner unter data_root; die Hauptperiode trägt den Slug der Stadt (Punkt 52).
MAIN = "duesseldorf"
OLD = "duesseldorf-2014"
RUNNING = "duesseldorf-2025"
MG = "moenchengladbach"
# Der Vollabruf lief am 2026-10-14 in eine eigene Datenwurzel neben der gewöhnlichen.
FULL_FETCH = Path("data-vollabruf") / "duesseldorf" / "raw" / "papers.jsonl"
# Die Metadaten der alten Periode liegen als Paket im Repo (Punkt 56).
OLD_PACKAGE = Path("snapshots/2014-2020/raw/papers.jsonl")
# Die laufende Periode ist am Abrufdatum angeschnitten; verglichen werden die vollen Monate.
FULL_MONTHS = 13


def layout_for(profile: str) -> Layout:
    """Das Layout eines Paketprofils; `settings.local.toml` zeigt data_root auf xtraspace."""
    return Layout.from_settings(load_settings(profile=profile))


def summary_of(layout: Layout) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        (layout.site_data / "summary.json").read_text(encoding="utf-8")
    )
    return payload


def figures_of(layout: Layout) -> dict[str, float]:
    figures = summary_of(layout)["figures"]
    assert isinstance(figures, dict)
    return figures


def names_of(layout: Layout) -> dict[int, str]:
    """Wahlbezirksnamen aus dem veröffentlichten GeoJSON; die Tabellen führen nur Nummern."""
    collection = json.loads((layout.site_data / "wahlbezirke.geojson").read_text(encoding="utf-8"))
    return {
        int(f["properties"]["wahlkreis_id"]): str(f["properties"]["name"])
        for f in collection["features"]
    }


def read_papers(path: Path) -> list[dict[str, Any]]:
    """Eine `papers.jsonl` als Liste; die Datei ist eine Zeile je Dokument (``PaperRecord``)."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def consultation_of(path: Path) -> dict[str, tuple[str, ...]]:
    """Beratungsfolge je Dokument-ID aus einer `papers.jsonl`; leer heißt: keine im Datensatz."""
    return {
        str(r["id"]): tuple(str(o) for o in (r.get("consultation_organizations") or ()))
        for r in read_papers(path)
    }


def short(org: str) -> str:
    """Die Organisation als `gr/37`; einen Namen hat sie ohne `raw/organizations.json` nicht."""
    return "/".join(org.rsplit("/", 2)[-2:])


def de(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def number(value: Any) -> float:
    """Ein Polars-Aggregat als Zahl; die Stubs liefern dort eine breite Union."""
    return float(value)


def head(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def spread(series: pl.Series) -> str:
    return (
        f"Median {de(number(series.median()))}, "
        f"{de(number(series.min()))} bis {de(number(series.max()))}"
    )


# --- 1. Zwei Wahlperioden ---------------------------------------------------------------------


def perioden() -> None:
    head("1. Zwei Wahlperioden (Profil duesseldorf-vergleich)")
    main, old = layout_for(MAIN), layout_for(OLD)
    comparison = pl.read_parquet(main.processed / "wahlbezirke_vergleich.parquet")
    names = names_of(main)
    print(f"Zeilen in wahlbezirke_vergleich.parquet: {comparison.height}")
    print(f"Perioden: {comparison['periode_alt'][0]!r} gegen {comparison['periode_neu'][0]!r}")

    for label, suffix in (("2014 bis 2020", "_alt"), ("2020 bis 2025", "_neu")):
        hits = int(comparison[f"anzahl_treffer{suffix}"].sum())
        print(f"\n{label}: Treffer {hits}")
        print(f"  Trefferquote    {spread(comparison[f'trefferquote{suffix}'])}")
        print(f"  Wahlbeteiligung {spread(comparison[f'wahlbeteiligung{suffix}'])}")

    # Tabelle 5 je Periode aus derselben Funktion wie die Seite; die Ausreißer stehen in den
    # Settings der Hauptperiode (analysis.exclude_districts = [1, 10]).
    excluded = tuple(load_settings(profile=MAIN).analysis.exclude_districts)
    print(f"\nTabelle 5 je Periode (x = Trefferquote, y = Wahlbeteiligung in %, ohne {excluded}):")
    for label, suffix in (("2014 bis 2020", "_alt"), ("2020 bis 2025", "_neu")):
        frame = comparison.select(
            pl.col("wahlkreis_id"),
            pl.col(f"trefferquote{suffix}").alias("trefferquote"),
            pl.col(f"wahlbeteiligung{suffix}").alias("wahlbeteiligung"),
        )
        pair = regression_pair(frame, excluded)
        print(f"  {label}, alle 41: {pair.all.summary()}")
        if pair.without is not None:
            print(f"  {label}, ohne 1 und 10: {pair.without.summary()}")

    # Gegenprobe: dieselben Zahlen stehen in summary.json beider Profile.
    for profile, layout in ((MAIN, main), (OLD, old)):
        regression = summary_of(layout)["regression"]
        assert isinstance(regression, dict)
        entry = regression["all"]
        assert isinstance(entry, dict)
        print(
            f"  summary.json {profile}: r = {de(number(entry['r']))}, "
            f"p = {de(number(entry['p']), 5)}, n = {entry['n']}"
        )

    delta = regress(comparison, x="d_trefferquote", y="d_wahlbeteiligung")
    print(f"\nRegression der Differenzen (Δ Quote -> Δ Beteiligung in pp): {delta.summary()}")
    print(f"  Δ Trefferquote    {spread(comparison['d_trefferquote'])}")
    print(f"  Δ Wahlbeteiligung {spread(comparison['d_wahlbeteiligung'])}")

    ordered = comparison.sort("d_trefferquote", descending=True)
    for label, rows in (
        ("größten Zunahme", ordered.head(5)),
        ("größten Abnahme", ordered.tail(5)),
    ):
        print(f"\nFünf Wahlbezirke mit der {label} der Trefferquote:")
        for row in rows.iter_rows(named=True):
            district = int(row["wahlkreis_id"])
            print(
                f"  {district:>2} {names.get(district, '?'):<42} "
                f"{de(row['trefferquote_alt'])} -> {de(row['trefferquote_neu'])} "
                f"(Δ {de(row['d_trefferquote'])}, Treffer {row['anzahl_treffer_alt']} -> "
                f"{row['anzahl_treffer_neu']})"
            )

    # Die beiden Sensitivitätszahlen der Umrechnung, wie `report.model.period_comparison` sie
    # rechnet: wie viele Stimmbezirke von 2020 auf mehr als einen Wahlbezirk von 2025 fallen und
    # wie vollständig die Zielbezirke die kleinste Quellfläche bedecken.
    assignment = pl.read_parquet(old.processed / "stimmbezirke_zuordnung.parquet")
    per_precinct = assignment.group_by("stimmbezirk_id").agg(
        pl.len(), pl.col("abdeckung").min().alias("abdeckung")
    )
    split = per_precinct.filter(pl.col("len") > 1).height
    print(
        f"\nUmrechnung der Wahlzahlen 2020: {assignment.height} Zeilen über "
        f"{per_precinct.height} Stimmbezirke, davon {split} auf mehr als einen Wahlbezirk "
        f"({split / per_precinct.height:.1%}); kleinste Abdeckung einer Quellfläche "
        f"{de(number(per_precinct['abdeckung'].min()))}"
    )

    rate_rho = spearman(comparison, "trefferquote_neu", "trefferquote_alt")
    turnout_rho = spearman(comparison, "wahlbeteiligung_neu", "wahlbeteiligung_alt")
    print(f"\nSpearman der Trefferquoten zwischen den Perioden: {de(rate_rho or 0.0)}")
    print(f"Spearman der Wahlbeteiligungen:                   {de(turnout_rho or 0.0)}")
    print(
        f"Bezirke mit gestiegener Quote: {int((comparison['d_trefferquote'] > 0).sum())} "
        f"von {comparison.height}; mit gestiegener Beteiligung: "
        f"{int((comparison['d_wahlbeteiligung'] > 0).sum())}"
    )


# --- 2. Städtevergleich -----------------------------------------------------------------------


def staedte() -> None:
    head("2. Städtevergleich (Düsseldorf gegen Mönchengladbach)")
    for profile in (MAIN, MG):
        layout = layout_for(profile)
        summary = summary_of(layout)
        figures = figures_of(layout)
        city = summary["city"]
        assert isinstance(city, dict)
        results = pl.read_parquet(layout.results)
        rates, eligible = results["trefferquote"], results["Wahlberechtigte_insgesamt"]
        documents = number(figures["documents"])
        print(f"\n{city['name']} ({profile})")
        print(
            f"  Wahlbezirke {figures['districts']}, Stimmbezirke {figures['precincts']}, "
            f"Begriffe {figures['terms']}"
        )
        print(
            f"  Dokumente {figures['documents']}, davon mit Text "
            f"{figures['documents_with_text']} "
            f"({number(figures['documents_with_text']) / documents:.1%}), "
            f"mit Treffer {figures['documents_hit']} "
            f"({number(figures['documents_hit']) / number(figures['documents_with_text']):.1%} "
            "der Dokumente mit Text)"
        )
        print(f"  Treffer über alle Wahlbezirke: {int(number(results['anzahl_treffer'].sum()))}")
        print(
            f"  Trefferquote: {spread(rates)}; Quartile {de(number(rates.quantile(0.25)))} / "
            f"{de(number(rates.median()))} / {de(number(rates.quantile(0.75)))}; "
            f"Verhältnis max/min {de(number(rates.max()) / number(rates.min()), 2)}"
        )
        print(f"  Wahlbeteiligung: {spread(results['wahlbeteiligung'])}")
        print(
            f"  Wahlberechtigte je Wahlbezirk: Mittel {de(number(eligible.mean()), 0)}, "
            f"{int(number(eligible.min()))} bis {int(number(eligible.max()))}"
        )
        regression = summary["regression"]
        if isinstance(regression, dict):
            for key in ("all", "without"):
                entry = regression.get(key)
                if isinstance(entry, dict):
                    print(
                        f"  Tabelle 5 ({key}): n = {entry['n']}, "
                        f"Steigung {de(number(entry['slope']))}, r = {de(number(entry['r']))}, "
                        f"R² = {de(number(entry['r2']))}, p = {de(number(entry['p']), 5)}"
                    )
        bodies = pl.read_parquet(layout.processed / "gremien.parquet")
        unknown = int(
            number(bodies.filter(pl.col("gremium_art") == "unbekannt")["dokumente"].sum())
        )
        print(
            f"  Gremien: {bodies.height} Zeilen, unbekannt {unknown} Dokumente "
            f"({unknown / documents:.1%})"
        )
        originators = layout.processed / "dokumente_urheber.parquet"
        if originators.is_file():
            counts = (
                pl.read_parquet(originators)
                .group_by("urheber_art")
                .len()
                .sort("len", descending=True)
            )
            print(
                "  Urheber: "
                + ", ".join(f"{art} {n} ({n / documents:.1%})" for art, n in counts.iter_rows())
            )
        else:
            print(
                "  Urheber: der Schritt `parties` fehlt, weil `[originators]` im Profil leer "
                "ist (keine Muster für dieses Ratsinformationssystem)"
            )
        types = (
            pl.read_parquet(layout.corpus).group_by("paper_type").len().sort("len", descending=True)
        )
        print(f"  Dokumentarten: {types.height}; die fünf häufigsten:")
        for art, count in types.head(5).iter_rows():
            print(f"    {art[:52]:<54} {count:>6}  {count / documents:.1%}")


# --- 3. Laufende Wahlperiode ------------------------------------------------------------------


def laufend() -> None:
    head("3. Laufende Wahlperiode seit dem 14.09.2025 (Profil duesseldorf-2025)")
    running, main = layout_for(RUNNING), layout_for(MAIN)
    summary = summary_of(running)
    figures, stand = figures_of(running), summary["stand"]
    assert isinstance(stand, dict)
    print(
        f"Periode ab {stand['period_start']}, Ende {stand['period_end']}; "
        f"Dokumente {figures['documents']}, mit Text {figures['documents_with_text']}, "
        f"mit Treffer {figures['documents_hit']}, Begriffe {figures['terms']} "
        f"(das Wörterbuch der Hauptperiode)"
    )
    print(f"Regression: {summary['regression']} — keine Wahlbeteiligung zur laufenden Periode")

    months = pl.read_parquet(running.processed / "monatsreihe.parquet")
    print(f"\nMonatsreihe ({months.height} Monate):")
    for row in months.iter_rows(named=True):
        print(
            f"  {row['monat']}  Dokumente {row['dokumente']:>4}  mit Text {row['mit_text']:>4}  "
            f"mit Treffer {row['mit_treffer']:>4}"
        )
    documents, hit = int(months["dokumente"].sum()), int(months["mit_treffer"].sum())
    print(f"  Summe: {documents} Dokumente, {hit} mit Treffer ({hit / documents:.1%})")

    district_months = pl.read_parquet(running.processed / "wahlbezirke_monate.parquet")
    names = names_of(running)
    per_district = (
        district_months.group_by("wahlkreis_id")
        .agg(pl.col("anzahl_treffer").sum().alias("treffer"))
        .sort("treffer", descending=True)
    )
    print(f"\nWahlbezirke mit den meisten Erwähnungen ({district_months.height} Zeilen):")
    for row in per_district.head(8).iter_rows(named=True):
        district = int(row["wahlkreis_id"])
        print(f"  {district:>2} {names.get(district, '?'):<46} {row['treffer']:>5}")
    print("  …")
    for row in per_district.tail(3).iter_rows(named=True):
        district = int(row["wahlkreis_id"])
        print(f"  {district:>2} {names.get(district, '?'):<46} {row['treffer']:>5}")

    # Dieselbe Rangfolge in der Hauptperiode: ändert die laufende Periode die Reihenfolge?
    main_results = pl.read_parquet(main.results).select("wahlkreis_id", "anzahl_treffer")
    joined = per_district.join(
        main_results.rename({"anzahl_treffer": "treffer_hauptperiode"}), on="wahlkreis_id"
    )
    rho = spearman(joined, "treffer", "treffer_hauptperiode")
    print(f"Spearman der Treffer gegen die Hauptperiode: {de(float(rho or 0.0))}")

    originators = (
        pl.read_parquet(running.processed / "dokumente_urheber.parquet")
        .group_by("urheber_art")
        .len()
        .sort("len", descending=True)
    )
    total = int(originators["len"].sum())
    print("\nUrheber der laufenden Periode:")
    for art, count in originators.iter_rows():
        print(f"  {art or '(leer)':<12} {count:>5}  {count / total:.1%}")
    main_originators = (
        pl.read_parquet(main.processed / "dokumente_urheber.parquet")
        .group_by("urheber_art")
        .len()
        .sort("len", descending=True)
    )
    main_total = int(main_originators["len"].sum())
    print("Zum Vergleich die Hauptperiode:")
    for art, count in main_originators.iter_rows():
        print(f"  {art or '(leer)':<12} {count:>5}  {count / main_total:.1%}")

    main_months = pl.read_parquet(main.processed / "monatsreihe.parquet")
    print(f"\nDie ersten {FULL_MONTHS} Monate beider Perioden (der 14. der laufenden ist offen):")
    for label, frame in (
        ("2020 bis 2025", main_months.head(FULL_MONTHS)),
        ("laufend ab 2025-09", months.head(FULL_MONTHS)),
    ):
        count, hits = int(frame["dokumente"].sum()), int(frame["mit_treffer"].sum())
        print(
            f"  {label:<20} {frame['monat'][0]} bis {frame['monat'][-1]}: "
            f"{count} Dokumente, {hits} mit Treffer ({hits / count:.1%}), "
            f"Median je Monat {int(number(frame['dokumente'].median()))}"
        )
    print(
        f"  Der angeschnittene Monat ({months['monat'][-1]}): "
        f"{int(months['dokumente'][-1])} Dokumente"
    )


# --- 4. Vollabruf der Metadaten ---------------------------------------------------------------


def organization_to_body(
    bodies: pl.DataFrame, consultation: dict[str, tuple[str, ...]]
) -> tuple[dict[str, str], int, int]:
    """Organisation -> Gremiumskürzel, gelernt an den Dokumenten mit **genau einer** Organisation.

    Die Beratungsfolge nennt IDs, die Drucksachennummer Kürzel; einen Namen hat die Organisation
    ohne `raw/organizations.json` (Netzschritt) nicht. Wo die Folge nur ein Gremium nennt, ist
    die Zuordnung eindeutig, und das Kürzel der Nummer sagt, welches es ist. Die Richtung
    Kürzel -> Organisation taugt nicht: drei Kürzel zeigen mehrheitlich auf dieselbe Organisation
    (RAT, GLA, RPAU auf `gr/6`), die Abbildung wäre also nicht umkehrbar. Geliefert werden die
    Abbildung und, als Maß ihrer Reinheit, Mehrheit und Gesamtzahl der gelernten Dokumente.
    """
    votes: dict[str, Counter[str]] = {}
    for row in bodies.iter_rows(named=True):
        organizations = consultation.get(str(row["id"]), ())
        if len(organizations) == 1 and row["gremium"]:
            votes.setdefault(organizations[0], Counter())[str(row["gremium"])] += 1
    mapping = {org: counter.most_common(1)[0][0] for org, counter in votes.items()}
    pure = sum(counter.most_common(1)[0][1] for counter in votes.values())
    total = sum(sum(counter.values()) for counter in votes.values())
    return mapping, pure, total


def vollabruf() -> None:
    head("4. Vollabruf der Metadaten der Hauptperiode (2026-10-14, 01:40 bis 02:16)")
    main = layout_for(MAIN)
    path = main.data_root.parent / FULL_FETCH
    rows = read_papers(path)
    print(f"{path}: {len(rows)} Dokumente")

    sizes = Counter(len(r.get("consultation_organizations") or ()) for r in rows)
    with_folge = len(rows) - sizes[0]
    print(
        f"\nconsultation_organizations: {with_folge} von {len(rows)} "
        f"({with_folge / len(rows):.1%}) tragen mindestens ein Gremium"
    )
    print("Gremien je Dokument:")
    for size in sorted(sizes):
        if sizes[size] >= 10 or size <= 4:
            print(f"  {size:>2}: {sizes[size]:>6}  {sizes[size] / len(rows):.1%}")
    pairs = sum(size * count for size, count in sizes.items())
    print(f"  Mehr als eines: {with_folge - sizes[1]}; Maximum {max(sizes)}; {pairs} Paare")

    organizations = Counter(
        org for r in rows for org in (r.get("consultation_organizations") or ())
    )
    print(f"\nVerschiedene Gremien in der Beratungsfolge: {len(organizations)}")
    print("Die zehn häufigsten (die IDs sind ohne `raw/organizations.json` keine Namen):")
    consultation = {str(r["id"]): tuple(r.get("consultation_organizations") or ()) for r in rows}
    by_number = pl.read_parquet(main.papers_bodies)
    mapping, pure, learned = organization_to_body(by_number, consultation)
    for org, count in organizations.most_common(10):
        print(
            f"  {short(org):<12} {count:>6}  {count / len(rows):>5.1%}  "
            f"aufgelöst als {mapping.get(org, '—')}"
        )

    print(f"\npapers_gremien.parquet: {by_number.height} Dokumente der Referenz")
    found = by_number.filter(pl.col("id").is_in(list(consultation)))
    print(f"  davon im Vollabruf wiedergefunden: {found.height}")
    print(
        f"  Abbildung Organisation -> Kürzel: {len(mapping)} Organisationen, gelernt an "
        f"{learned} Dokumenten mit genau einem Gremium, Reinheit {pure}/{learned} "
        f"= {pure / learned:.1%}"
    )
    agreed = missing = 0
    per_code: dict[str, list[int]] = {}
    for row in found.iter_rows(named=True):
        organizations_of_row = consultation.get(str(row["id"]), ())
        codes = {mapping[o] for o in organizations_of_row if o in mapping}
        hit = int(str(row["gremium"]) in codes)
        agreed += hit
        missing += not organizations_of_row
        bucket = per_code.setdefault(str(row["gremium"]), [0, 0])
        bucket[0] += 1
        bucket[1] += hit
    print(
        f"  Das Gremium der Nummer steht in der Beratungsfolge: {agreed} von {found.height} "
        f"({agreed / found.height:.1%}); unter den {found.height - missing} mit Folge "
        f"{agreed / (found.height - missing):.1%}"
    )
    print("  Je Kürzel, nach Dokumenten:")
    for code, (total, hits) in sorted(per_code.items(), key=lambda kv: -kv[1][0]):
        print(f"    {code:<8} {total:>5} Dokumente, bestätigt {hits:>5} ({hits / total:>6.1%})")
    # Wo die Abbildung systematisch danebenliegt: ein kleines Kürzel, dessen Dokumente auf die
    # Organisation eines größeren zeigen (GLA und RPAU auf die des Rates, BAU auf die von SEBD),
    # bekommt von ihr nie sein eigenes Kürzel zurück.
    blind = {code: total for code, (total, hits) in per_code.items() if hits == 0}
    print(
        f"  Kürzel ohne eine einzige Bestätigung: {len(blind)} "
        f"({', '.join(f'{c} {n}' for c, n in sorted(blind.items(), key=lambda kv: -kv[1]))}), "
        f"zusammen {sum(blind.values())} Dokumente"
    )

    # Der Klassifikator (Punkt 45): trifft der vorhergesagte Ausschuss eines der Beratungsgremien?
    predicted = pl.read_parquet(main.processed / "papers_ausschuss.parquet")
    threshold = load_settings(profile=MAIN).classify.min_probability
    assigned = predicted.filter(pl.col("ausschuss") != "")
    print(
        f"\npapers_ausschuss.parquet: {predicted.height} Dokumente mit Text, "
        f"{assigned.height} über der Schwelle {threshold} "
        f"({assigned.height / predicted.height:.1%})"
    )
    checked = agree = 0
    for row in assigned.iter_rows(named=True):
        codes = {mapping[o] for o in consultation.get(str(row["id"]), ()) if o in mapping}
        if not codes:
            continue
        checked += 1
        agree += str(row["ausschuss"]) in codes
    print(
        f"  mit auflösbarer Beratungsfolge: {checked}; der vorhergesagte Ausschuss steht "
        f"darin: {agree} ({agree / checked:.1%})"
    )
    joined = predicted.join(by_number, on="id", how="inner").filter(pl.col("ausschuss") != "")
    same = int((joined["ausschuss"] == joined["gremium"]).sum())
    print(
        f"  Gegenprobe: der vorhergesagte Ausschuss gleicht dem Gremium der Nummer in "
        f"{same} von {joined.height} Fällen ({same / joined.height:.1%})"
    )

    # Was die Folge für die alte Periode hergibt, wo die Nummer kein Kürzel trägt (Punkt 57).
    old = layout_for(OLD)
    old_consultation = consultation_of(Path(OLD_PACKAGE))
    old_bodies = pl.read_parquet(old.papers_bodies)
    buckets: Counter[str] = Counter()
    unknown_buckets: Counter[str] = Counter()
    checked_old = agreed_old = 0
    for row in old_bodies.iter_rows(named=True):
        organizations_of_row = old_consultation.get(str(row["id"]), ())
        codes = {mapping[o] for o in organizations_of_row if o in mapping}
        key = (
            "ohne Folge"
            if not organizations_of_row
            else ("auflösbar" if codes else "Folge, Organisation unbekannt")
        )
        buckets[key] += 1
        if row["gremium_art"] == "unbekannt":
            unknown_buckets[key] += 1
        elif codes:
            checked_old += 1
            agreed_old += str(row["gremium"]) in codes
    print(f"\nDieselbe Abbildung auf der Periode 2014 bis 2020 ({old_bodies.height} Dokumente):")
    for key, count in buckets.most_common():
        print(f"  {key:<32} {count:>6}  {count / old_bodies.height:.1%}")
    unknown_total = sum(unknown_buckets.values())
    print(f"  Davon die heute unbekannten ({unknown_total}):")
    for key, count in unknown_buckets.most_common():
        print(f"    {key:<30} {count:>6}  {count / unknown_total:.1%}")
    print(
        f"  Gegenprobe bei bekanntem Kürzel: {agreed_old} von {checked_old} "
        f"({agreed_old / checked_old:.1%}) stimmen überein"
    )

    modified = Counter(str(r.get("modified", ""))[:7] for r in rows)
    print(f"\n`modified`: {sum(1 for r in rows if r.get('modified'))} von {len(rows)} gesetzt")
    print("Die acht häufigsten Monate:")
    for month, count in modified.most_common(8):
        print(f"  {month or '(leer)'}  {count:>6}  {count / len(rows):.1%}")
    stamps = sorted(str(r.get("modified", "")) for r in rows if r.get("modified"))
    print(f"  Spanne {stamps[0][:10]} bis {stamps[-1][:10]}")

    for field in ("originator_person", "originator_organization", "under_direction_of"):
        print(f"{field}: {sum(1 for r in rows if r.get(field))} von {len(rows)} gefüllt")


# --- 5. Datenqualität über alle vier Läufe ----------------------------------------------------


def qualitaet() -> None:
    head("5. Datenqualität über alle vier Läufe")
    print(
        f"{'Profil':<22}{'Dokumente':>10}{'mit Text':>10}{'Gremium unbekannt':>20}{'Urheber unbekannt':>20}"
    )
    for profile in (MAIN, OLD, RUNNING, MG):
        layout = layout_for(profile)
        figures = figures_of(layout)
        documents = float(figures["documents"])
        bodies = pl.read_parquet(layout.processed / "gremien.parquet")
        unknown = int(bodies.filter(pl.col("gremium_art") == "unbekannt")["dokumente"].sum())
        path = layout.processed / "dokumente_urheber.parquet"
        if path.is_file():
            count = pl.read_parquet(path).filter(pl.col("urheber_art") == "unbekannt").height
            originator = f"{count} ({count / documents:.1%})"
        else:
            originator = "kein Schritt"
        print(
            f"{profile:<22}{int(documents):>10}{int(figures['documents_with_text']):>10}"
            f"{f'{unknown} ({unknown / documents:.1%})':>20}{originator:>20}"
        )

    # Woran die fehlenden Texte liegen: an den Metadaten (keine Hauptdatei) oder am Abruf.
    print("\nDokumente ohne Text, zerlegt (die Zahl der gescheiterten Abrufe steht im README")
    print("des jeweiligen Pakets, nicht in den Tabellen):")
    for profile in (MAIN, OLD, RUNNING, MG):
        layout = layout_for(profile)
        corpus = pl.read_parquet(layout.corpus)
        no_main = int((corpus["main_file"].fill_null("") == "").sum())
        empty = int((corpus["text"].fill_null("").str.len_chars() == 0).sum())
        print(
            f"  {profile:<22} {corpus.height:>6} Dokumente, ohne Hauptdatei {no_main:>4}, "
            f"ohne Text {empty:>5} ({empty / corpus.height:.1%}), "
            f"davon mit Hauptdatei {empty - no_main:>5}"
        )

    # Warum die Urheber der alten Periode häufiger unbekannt sind: an Dokumentart und Titel.
    for profile in (OLD, MAIN):
        layout = layout_for(profile)
        corpus = pl.read_parquet(layout.corpus).select("id", "name", "paper_type")
        joined = corpus.join(
            pl.read_parquet(layout.processed / "dokumente_urheber.parquet"), on="id", how="inner"
        )
        nameless = joined.filter(pl.col("urheber_art") == "unbekannt")
        print(f"\n{profile}: {joined.height} Dokumente, {nameless.height} ohne Urheber")
        types = (
            joined.group_by("paper_type")
            .agg(
                pl.len().alias("dokumente"),
                (pl.col("urheber_art") == "unbekannt").sum().alias("unbekannt"),
            )
            .sort("dokumente", descending=True)
        )
        print(f"  Dokumentarten: {types.height}; die sechs häufigsten:")
        for row in types.head(6).iter_rows(named=True):
            print(
                f"    {str(row['paper_type'])[:44]:<46} {row['dokumente']:>6}, "
                f"ohne Urheber {row['unbekannt']:>6} "
                f"({row['unbekannt'] / row['dokumente']:.1%})"
            )
        # Die Muster in `[originators]` beschreiben die Benennung der Hauptperiode; welche
        # Dokumentarten der Periode darin überhaupt vorkommen, ist die halbe Antwort.
        rules = load_settings(profile=profile).originators
        known = {*rules.admin_types, *rules.citizen_types}
        covered = types.filter(pl.col("paper_type").is_in(list(known)))
        print(
            f"  Dokumentarten, die `[originators].admin_types`/`citizen_types` nennen: "
            f"{covered.height} von {types.height}, zusammen "
            f"{int(number(covered['dokumente'].sum()))} Dokumente "
            f"({number(covered['dokumente'].sum()) / joined.height:.1%})"
        )
        if nameless.height:
            print("  Nennt der Titel die Fraktion, die die Dokumentart verschweigt?")
            for word in ("CDU", "SPD", "GRÜNE", "FDP", "LINKE", "AfD", "Fraktion", "Antrag"):
                found = int(number(nameless["name"].str.contains(word, literal=True).sum()))
                print(f"    {word!r:<12} {found:>6}  {found / nameless.height:.1%}")
        quelle = (
            pl.read_parquet(layout.processed / "dokumente_urheber.parquet")
            .group_by("quelle")
            .len()
            .sort("len", descending=True)
        )
        print(
            "  Quelle der Zuordnung: "
            + ", ".join(f"{q or '(keine)'} {n}" for q, n in quelle.iter_rows())
        )


SECTIONS = {
    "--perioden": perioden,
    "--staedte": staedte,
    "--laufend": laufend,
    "--vollabruf": vollabruf,
    "--qualitaet": qualitaet,
}


def main(argv: list[str]) -> int:
    unknown = [a for a in argv if a not in SECTIONS]
    if unknown:
        print(f"Unbekannte Schalter: {unknown}; bekannt sind {sorted(SECTIONS)}")
        return 2
    for flag, function in SECTIONS.items():
        if not argv or flag in argv:
            function()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
