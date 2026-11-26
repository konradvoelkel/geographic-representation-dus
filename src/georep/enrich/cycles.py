"""Beitrag von Vorhaben 17: Rhythmus der Ratsarbeit, bundespolitisches Vokabular, Neuigkeiten je Wahlbezirk.

Messdokument ``docs/plans/17-zeit.md`` (§ 6, § 8 und § 10). Vier Schritte, alle offline; sie lesen,
was ``bodies``, ``parties``, ``timeline``, ``dictionary`` und ``index`` schreiben, und stehen darum mit
den übrigen Beiträgen vor ``report``. ``http`` (Fundament F7) bleibt ungenutzt.

* ``cycles`` (mit ``cycles.enabled`` und Urhebern aus Option 04): ``processed/zeit_monate.parquet``,
  Dokumente je Monat, Gremienart, Urheberklasse und Instrument mit Wahljahr und Haushaltsanträgen,
  und ``processed/haushaltsmonate.parquet``, der Haushaltsmonat je vollständigem Wahljahr. Je Monat
  summiert die Tabelle zur Monatsreihe aus ``timeline``.
* ``vocabulary`` (mit ``cycles.enabled``): ``processed/dokumente_bundesvokabular.parquet`` mit den
  Kategorien des Lexikons je Korpus-ID, wie gemessen auf dem kleingeschriebenen Text, und die
  Treffer im Text als Spannen nach F3 **auf dem Rohtext** (``processed/bundesvokabular_spannen.parquet``,
  über ``prep.raw_texts.flatten_with_offsets``, Synergien 2026-11, Konflikt 1). Ohne Rohtext eines
  Dokuments fehlen nur seine Spannen.
* ``cycle_tests`` (nur mit ``cycles.periods``): die vorab festgelegten Tests über die Perioden einer
  Stadt, ``processed/zeit_hypothesen.parquet``. Liest die Ausgaben der Perioden über
  ``layout.for_profile`` wie ``compare``; fehlt eine, bricht ``run`` mit ihrem Pfad ab, also laufen
  die anderen Perioden vorher (Synergien 2026-11, Konflikt 13).
* ``feeds`` (mit ``feeds.enabled``): ein Atom-Feed je Wahlbezirk des Wörterbuchs unter
  ``site/feeds/``, ohne Treffer leer, mit den Dokumenten, die die Seite zeigt (ohne
  ``search.hide_in_display``), und deren Liste ``processed/wahlbezirke_feeds.parquet`` (die erste
  Ausgabe des Schritts, darum der Stamp dort). Feeds von Wahlbezirken, die das Wörterbuch nicht
  mehr kennt, nimmt der Schritt weg.

Die Pfade gehören diesem Modul (Synergien 2026-11, § 2.1): wer die Tabellen liest, nimmt sie aus
``time_files``; die Wahltage liest jedes Vorhaben aus ``cycles.elections`` (Konflikt 16).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo

import polars as pl

from georep import __version__
from georep.analysis.cycles import (
    CYCLE_TESTS_SCHEMA_VERSION,
    CYCLES_SCHEMA_VERSION,
    CycleRules,
    PeriodData,
    budget_months,
    complete_years,
    cycle_hypotheses,
    month_table,
    months_match_timeline,
)
from georep.analysis.hits import DISTRICT, hits_by_district
from georep.analysis.lexicon import (
    STRUCTURE,
    VOCABULARY_SCHEMA_VERSION,
    Lexicon,
    document_categories,
    load_lexicon,
    validated_precision,
    vocabulary_spans,
)
from georep.enrich import Contribution
from georep.errors import EmptyResultError, SchemaError
from georep.http import Transport
from georep.io import write_parquet, write_text
from georep.layout import Layout
from georep.pipeline import Step
from georep.report.feeds import (
    EMPTY_UPDATED,
    FEEDS_SCHEMA,
    FEEDS_SCHEMA_VERSION,
    SUBTITLE,
    FeedDocument,
    FeedHead,
    atom_problems,
    feed_id,
    feed_name,
    newest_entries,
    render_feed,
    timestamp,
)
from georep.search.index import PAPER_IDS, TERM
from georep.settings import Settings
from georep.spans import check_spans, sort_spans
from georep.stores import PaperStore, RawTextStore

MONTHS = ("Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez")


class TimeFiles(NamedTuple):
    months: Path
    budget: Path
    vocabulary: Path
    spans: Path
    hypotheses: Path
    feeds: Path  # die Liste der Feeds; die Feeds selbst liegen unter ``feed_dir``


def time_files(layout: Layout) -> TimeFiles:
    """Die Tabellen des Vorhabens unter ``processed/``."""
    return TimeFiles(
        layout.processed / "zeit_monate.parquet",
        layout.processed / "haushaltsmonate.parquet",
        layout.processed / "dokumente_bundesvokabular.parquet",
        layout.processed / "bundesvokabular_spannen.parquet",
        layout.processed / "zeit_hypothesen.parquet",
        layout.processed / "wahlbezirke_feeds.parquet",
    )


def feed_dir(layout: Layout) -> Path:
    """Wo die Feeds liegen: neben der Seite, also mit ihr veröffentlicht (``site/feeds/``)."""
    return layout.site / "feeds"


def cycle_rules(settings: Settings) -> CycleRules:
    cycles = settings.cycles
    return CycleRules.of(
        start_month=cycles.year_start_month,
        elections=cycles.elections,
        budget_pattern=cycles.budget_pattern,
        budget_minimum=cycles.budget_minimum,
        instrument_types=cycles.instrument_types,
        instrument_titles=[(t.pattern, t.instrument) for t in cycles.instrument_titles],
        head_chars=cycles.head_chars,
    )


def _lexicon_stamp(lexicon: Lexicon) -> str:
    """Name, Version, Prüfsumme und validierte Präzision: ändert sich eines, rechnet der Schritt neu."""
    return f"{lexicon.label} {lexicon.digest[:16]} {validated_precision(lexicon)}"


def _wahljahr(year: int, start_month: int) -> str:
    return f"{year}/{(year + 1) % 100:02d}" if start_month > 1 else str(year)


def time_steps(settings: Settings, layout: Layout, http: Transport) -> list[Step]:
    """Die Schritte von Vorhaben 17, je nach Schalter im Profil; offline, ``http`` bleibt ungenutzt."""
    files = time_files(layout)
    steps: list[Step] = []
    cycles_on = settings.cycles.enabled
    with_originators = bool(settings.originators.parties)
    lexicon = load_lexicon(settings.cycles.lexicon) if cycles_on else None

    def cycles() -> str:
        rules = cycle_rules(settings)
        corpus = pl.read_parquet(
            layout.corpus, columns=["id", "date", "paper_type", "name", "text"]
        )
        originators = pl.read_parquet(layout.document_originators, columns=["id", "urheber_art"])
        bodies = pl.read_parquet(layout.papers_bodies, columns=["id", "gremium_art"])
        last = settings.period.end or corpus.get_column("date").max()
        years = (
            complete_years(settings.period.start, last, rules.start_month)  # type: ignore[arg-type]
            if last is not None
            else ()
        )
        months = month_table(corpus, originators, bodies, rules, years)
        timeline = pl.read_parquet(layout.timeline)
        if not months_match_timeline(months, timeline):
            raise SchemaError(
                f"cycles: {files.months.name} zählt je Monat anders als {layout.timeline.name}"
            )
        budget = budget_months(months, rules)
        write_parquet(months, files.months, schema_version=CYCLES_SCHEMA_VERSION)
        write_parquet(budget, files.budget, schema_version=CYCLES_SCHEMA_VERSION)
        named = [
            MONTHS[int(m) - 1] if m is not None else "-"
            for m in budget.get_column("monat_kalender").to_list()
        ]
        names = [_wahljahr(w, rules.start_month) for w in years]
        if len(names) > 1:
            span = f"{len(names)} vollständige Wahljahre {names[0]} bis {names[-1]}"
        else:
            span = f"vollständiges Wahljahr {names[0]}" if names else "kein vollständiges Wahljahr"
        return (
            f"{months.get_column('monat').drop_nulls().n_unique()} Monate, {span}; "
            f"Haushaltsmonate: {', '.join(named) or 'keine'}"
        )

    def vocabulary() -> str:
        assert lexicon is not None
        corpus = pl.read_parquet(layout.corpus, columns=["id", "name", "text", "file_name"])
        found = document_categories(corpus, lexicon, settings.cycles.head_chars)
        store = RawTextStore(layout.raw_texts)
        spans, lengths, without = vocabulary_spans(
            corpus.join(found.select("id", "kategorien"), on="id", how="left").sort("id"),
            store.rows,
            settings.search.text_split_marker,
            lexicon,
        )
        spans = sort_spans(spans)
        check_spans(spans, lengths)
        write_parquet(found, files.vocabulary, schema_version=VOCABULARY_SCHEMA_VERSION)
        write_parquet(spans, files.spans, schema_version=VOCABULARY_SCHEMA_VERSION)
        structural = set(lexicon.of_kind(STRUCTURE))
        hits = found.filter(pl.col("kategorien").list.len() > 0).height
        with_structure = found.filter(
            pl.col("kategorien").list.set_intersection(pl.lit(sorted(structural))).list.len() > 0
        ).height
        return (
            f"{found.height} Dokumente, {hits} mit Treffer, {with_structure} in einer "
            f"Strukturkategorie; {spans.height} Spannen auf dem Rohtext, {without} Dokumente mit "
            f"Treffer ohne passenden Rohtext ({lexicon.label})"
        )

    def period_inputs(folder: str) -> tuple[Path, ...]:
        other = layout.for_profile(folder)
        theirs = time_files(other)
        return (
            theirs.months,
            theirs.budget,
            theirs.vocabulary,
            other.corpus,
            other.document_originators,
        )

    def cycle_tests() -> str:
        assert lexicon is not None
        periods = []
        for folder in settings.cycles.periods:
            other = layout.for_profile(folder)
            theirs = time_files(other)
            vocabulary = pl.read_parquet(theirs.vocabulary)
            labels = set(vocabulary.get_column("lexikon").unique().to_list())
            if labels - {lexicon.label}:
                raise SchemaError(
                    f"cycle_tests: {theirs.vocabulary} trägt {sorted(labels)}, gerechnet wird mit "
                    f"{lexicon.label}; erst das Profil dieses Ordners neu rechnen"
                )
            documents = (
                pl.read_parquet(other.corpus, columns=["id", "date", "text"])
                .select("id", "date", (pl.col("text").fill_null("") != "").alias("mit_text"))
                .join(
                    pl.read_parquet(other.document_originators, columns=["id", "urheber_art"]),
                    on="id",
                    how="left",
                )
                .join(vocabulary.select("id", "kategorien", "kopf"), on="id", how="left")
                .sort("id")
            )
            period = PeriodData(
                folder,
                pl.read_parquet(theirs.months),
                pl.read_parquet(theirs.budget),
                documents,
            )
            if not period.years:
                raise SchemaError(
                    f"cycle_tests: {theirs.months} hat kein vollständiges Wahljahr; erst das "
                    "Profil dieses Ordners rechnen"
                )
            periods.append(period)
        table = cycle_hypotheses(periods, cycle_rules(settings), lexicon)
        write_parquet(table, files.hypotheses, schema_version=CYCLE_TESTS_SCHEMA_VERSION)
        main = table.filter(pl.col("rolle") == "Haupttest")
        days = table.get_column("daten_bis").drop_nulls().to_list()
        return (
            "; ".join(
                f"{r['hypothese']} {r['ergebnis']} (p = {r['p']:.4f}, Holm {r['p_holm']:.4f})"
                for r in main.iter_rows(named=True)
            )
            + f"; {table.height} Zeilen, Daten bis {max(days) if days else '-'}"
        )

    def feeds() -> str:
        zone = ZoneInfo(settings.feeds.timezone)
        corpus = pl.read_parquet(
            layout.corpus, columns=["id", "name", "reference", "date", "download_url"]
        )
        modified = (
            {record.id: record.modified for record in PaperStore(layout.papers).load().values()}
            if layout.papers.exists()
            else {}
        )
        documents = {
            row["id"]: FeedDocument(
                id=row["id"],
                reference=row["reference"] or "",
                name=row["name"] or "",
                day=row["date"],
                modified=modified.get(row["id"]),
                link=row["download_url"] or "",
            )
            for row in corpus.iter_rows(named=True)
            if row["date"] is not None
        }
        stand = max((d.day for d in documents.values()), default=None)
        # Review N1: ein Begriff aus ``hide_in_display`` zählt auf der Seite, zeigt aber kein
        # Dokument (``report.documents``); der Feed nennt nur, was die Seite zeigt
        visible = pl.read_parquet(layout.index).filter(
            ~pl.col(TERM).is_in(list(settings.search.hide_in_display))
        )
        dictionary = pl.read_parquet(layout.dictionary)
        try:
            hits = dict(
                hits_by_district(dictionary, visible).select(DISTRICT, PAPER_IDS).iter_rows()
            )
        except EmptyResultError:
            hits = {}
        # Review N2: jeder Wahlbezirk des Wörterbuchs bekommt einen Feed, auch ohne Treffer; ein
        # leerer trägt den Stand der Daten (das letzte Vorlagendatum, 00:00 Ortszeit)
        districts = sorted(int(d) for d in dictionary.get_column(DISTRICT).drop_nulls().unique())
        empty_updated = (
            timestamp(dt.datetime.combine(stand, dt.time(0, 0), tzinfo=zone))
            if stand is not None
            else EMPTY_UPDATED
        )
        target = layout.guard_writable(feed_dir(layout))
        target.mkdir(parents=True, exist_ok=True)
        slug = f"{settings.city.slug}/{layout.root.name}"
        rows: list[dict[str, object]] = []
        changed = 0
        for district in districts:
            chosen = [documents[p] for p in hits.get(district, []) if p in documents]
            entries = newest_entries(chosen, settings.feeds.entries, zone)
            name = feed_name(int(district))
            head = FeedHead(
                id=feed_id(slug, name.removesuffix(".xml")),
                title=f"Ratsdokumente im Wahlbezirk {int(district)} ({settings.city.name}, "
                f"{settings.period.title})",
                subtitle=SUBTITLE,
                generator_version=__version__,
            )
            text = render_feed(head, entries, empty_updated=empty_updated)
            problems = atom_problems(text)
            if problems:
                raise SchemaError(
                    f"feeds: {name} ist kein gültiges Atom: {'; '.join(problems[:3])}"
                )
            path = target / name
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                write_text(path, text)
                changed += 1
            rows.append(
                {
                    DISTRICT: int(district),
                    "datei": f"{target.name}/{name}",
                    "eintraege": len(entries),
                    "dokumente": len(chosen),
                    "neu_30_tage": sum(
                        1 for d in chosen if stand is not None and (stand - d.day).days < 30
                    ),
                    "aktualisiert": timestamp(max(e.updated for e in entries))
                    if entries
                    else empty_updated,
                    "bytes": len(text.encode("utf-8")),
                }
            )
        kept = {Path(str(r["datei"])).name for r in rows}
        stale = [p for p in sorted(target.glob("wahlbezirk-*.xml")) if p.name not in kept]
        for path in stale:
            path.unlink()
        manifest = pl.DataFrame(rows, schema=FEEDS_SCHEMA)
        write_parquet(manifest, files.feeds, schema_version=FEEDS_SCHEMA_VERSION)
        return (
            f"{manifest.height} Feeds, {changed} geändert, {len(stale)} entfernt; "
            f"{int(manifest.get_column('eintraege').sum() or 0)} Einträge, "
            f"{int(manifest.get_column('bytes').sum() or 0) // 1024} KB, Stand {stand}"
        )

    if cycles_on and lexicon is not None:
        if with_originators:
            steps.append(
                Step(
                    "cycles",
                    (
                        layout.corpus,
                        layout.document_originators,
                        layout.papers_bodies,
                        layout.timeline,
                    ),
                    (files.months, files.budget),
                    cycles,
                    CYCLES_SCHEMA_VERSION,
                )
            )
        steps.append(
            Step(
                "vocabulary",
                (layout.corpus,),
                (files.vocabulary, files.spans),
                vocabulary,
                VOCABULARY_SCHEMA_VERSION,
                extra=_lexicon_stamp(lexicon),
                optional=(layout.raw_texts,),
            )
        )
        if settings.cycles.periods and with_originators:
            # Die Perioden tragen Dateien gleichen Namens; der Stamp führt sie mit ihrem Pfad
            # (``pipeline.input_key``, Punkt 76), eine Änderung in jeder macht den Schritt veraltet.
            steps.append(
                Step(
                    "cycle_tests",
                    tuple(p for folder in settings.cycles.periods for p in period_inputs(folder)),
                    (files.hypotheses,),
                    cycle_tests,
                    CYCLE_TESTS_SCHEMA_VERSION,
                    extra=_lexicon_stamp(lexicon),
                )
            )
    if settings.feeds.enabled:
        steps.append(
            Step(
                "feeds",
                (layout.corpus, layout.dictionary, layout.index),
                (files.feeds,),
                feeds,
                FEEDS_SCHEMA_VERSION,
                optional=(layout.papers,),
            )
        )
    return steps


CONTRIBUTION = Contribution("17-zeit", steps=time_steps)
