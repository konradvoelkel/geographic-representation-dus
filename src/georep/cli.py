"""Kommandozeile: ``georep run|fetch|steps|status|bootstrap|export|regress|profile``.

``main(argv)`` ist testbar ohne Prozess; Exit-Codes: 0 gut, 1 Domänenfehler (eine Zeile auf
stderr), 2 Bedienfehler (argparse).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import polars as pl
from loguru import logger

from georep import __version__
from georep.analysis.regression import regress
from georep.bootstrap import bootstrap
from georep.contracts import configure as configure_contracts
from georep.errors import GeorepError, MissingInputError
from georep.export import export_csv
from georep.layout import Layout
from georep.pipeline import build_steps, freshness, run_pipeline, select_steps
from georep.profiling import profile_step
from georep.report.model import sensitivity_rows
from georep.settings import Settings, load_settings, settings_files
from georep.sources.pdfs import PdfStore
from georep.stores import PaperStore, TextStore


def _setup_logging(level: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level, format="<level>{level: <8}</level> {message}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="georep", description=__doc__.splitlines()[0])
    parser.add_argument(
        "--settings", type=Path, help="zusätzliche TOML-Datei, gewinnt über ./settings*.toml"
    )
    parser.add_argument("--version", action="version", version=f"georep {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Schritte ausführen, aktuelle überspringen")
    run.add_argument("steps", nargs="*", help="Namen (Standard: alle)")
    run.add_argument("--force", action="store_true", help="auch aktuelle Schritte ausführen")
    run.add_argument("--dry-run", action="store_true", help="nur zeigen, was liefe")
    run.add_argument("--online", action="store_true", help="Netzschritte mitlaufen lassen")

    fetch = sub.add_parser(
        "fetch", help="Netzschritte ausführen (opendata, papers, pdfs), dann texts"
    )
    fetch.add_argument("steps", nargs="*", help="Namen (Standard: alle Netzschritte und texts)")
    fetch.add_argument("--force", action="store_true", help="auch aktuelle Schritte ausführen")
    fetch.add_argument("--limit", type=int, help="höchstens so viele neue PDFs in diesem Lauf")
    fetch.add_argument(
        "--max-pages",
        type=int,
        help="höchstens so viele Metadatenseiten; `fetch papers --max-pages 1` ist die Probe, "
        "ob der Server Urheberfelder liefert (rund 90 s)",
    )

    sub.add_parser("steps", help="Schritte mit Eingaben und Ausgaben")
    sub.add_parser("status", help="Settings, Pfade, Frische jedes Schritts")

    boot = sub.add_parser("bootstrap", help="Referenzdatensatz nach data_root übernehmen")
    boot.add_argument("--force", action="store_true", help="vorhandene Dateien überschreiben")

    sub.add_parser("export", help="Parquet-Ergebnisse als CSV neben die Parquet-Dateien schreiben")

    reg = sub.add_parser("regress", help="Regression Trefferquote -> Wahlbeteiligung")
    reg.add_argument("--exclude", type=int, nargs="*", default=[], help="Wahlbezirke auslassen")
    reg.add_argument(
        "--varianten",
        action="store_true",
        help="dieselbe Regression je Gewichtungsvariante aus wahlbezirke_gewichtet.parquet",
    )
    reg.add_argument(
        "--controls", action="store_true", help="Tabelle 6: Modelle mit Kontrollvariablen"
    )

    prof = sub.add_parser(
        "profile", help="Schritte erzwungen unter cProfile ausführen; .prof-Datei für snakeviz"
    )
    prof.add_argument("steps", nargs="*", help="Namen (Standard: alle Offline-Schritte)")
    prof.add_argument(
        "--out", type=Path, default=Path("docs/profiling"), help="Verzeichnis der .prof-Dateien"
    )
    prof.add_argument("--top", type=int, default=25, help="Zeilen der Tabelle je Schritt")
    prof.add_argument(
        "--sort", choices=["cumulative", "tottime"], default="cumulative", help="Sortierung"
    )
    prof.add_argument("--online", action="store_true", help="auch Netzschritte profilieren")
    return parser


def _with_fetch_limits(settings: Settings, limit: int | None, max_pages: int | None) -> Settings:
    """``--limit`` und ``--max-pages`` als Settings-Override für einen Lauf.

    Beide zählen zum Fingerprint: ein Lauf mit Grenze hat ein anderes Ergebnis als einer ohne, und
    ``georep status`` soll den betroffenen Schritt danach als „Settings geändert" zeigen.
    """
    update = {
        key: value
        for key, value in (("pdf_limit", limit), ("max_pages", max_pages))
        if value is not None
    }
    if not update:
        return settings
    oparl = settings.sources.oparl.model_copy(update=update)
    sources = settings.sources.model_copy(update={"oparl": oparl})
    return settings.model_copy(update={"sources": sources})


def _cmd_run(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    layout.ensure_dirs()
    PdfStore(layout.pdf_dir).ensure()
    fetching = args.command == "fetch"
    if fetching:
        settings = _with_fetch_limits(settings, args.limit, args.max_pages)
    steps = build_steps(settings, layout)
    default_names = [s.name for s in steps if s.network or s.name == "texts"] if fetching else None
    outcomes = run_pipeline(
        steps,
        settings,
        args.steps or default_names,
        force=args.force,
        dry_run=getattr(args, "dry_run", False),
        online=fetching or args.online,
    )
    for outcome in outcomes:
        print(outcome.line())
    counts = {
        s: sum(1 for o in outcomes if o.status == s)
        for s in ("ausgeführt", "übersprungen", "geplant")
    }
    print(", ".join(f"{n} {s}" for s, n in counts.items() if n))
    return 0


def _cmd_steps(settings: Settings, layout: Layout) -> int:
    for step in build_steps(settings, layout):
        tag = " [Netz]" if step.network else ""
        print(f"{step.name:<12} <- {', '.join(p.name for p in step.inputs) or '(nichts)'}{tag}")
        print(f"{'':<12} -> {', '.join(p.name for p in step.outputs)}")
    return 0


def _cmd_status(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    print(
        f"georep {__version__}, Settings-Fingerprint {settings.fingerprint()}, "
        f"Verträge {settings.contracts}"
    )
    files = settings_files(args.settings)
    print("Settings:   defaults.toml" + "".join(f" < {p}" for p in files))
    print(f"data_root:  {layout.data_root.resolve()}")
    print(
        f"Profil:     {layout.profile or '(keines, Hauptperiode)'}; Daten unter {layout.root.resolve()}"
    )
    period = settings.period
    print(
        f"Periode:    {period.title}, {period.start} bis {period.end or 'offen'}; "
        f"Wahltag {period.election_day}"
    )
    print(f"cache_root: {layout.cache_root.resolve()}")
    print(f"reference:  {layout.reference_root.resolve()}")
    pdfs = len(list(layout.pdf_dir.glob("*.pdf"))) if layout.pdf_dir.is_dir() else 0
    texts = len(TextStore(layout.texts))
    papers = len(PaperStore(layout.papers).load())
    corpus = (
        pl.scan_parquet(layout.corpus).select(pl.len()).collect().item()
        if layout.corpus.exists()
        else 0
    )
    print(f"Stores:     {papers} Paper, {pdfs} PDFs, {texts} Texte; Korpus: {corpus} Dokumente")
    for step in build_steps(settings, layout):
        fresh, reason = freshness(step, settings)
        tag = " [Netz]" if step.network else ""
        print(f"{step.name:<12} {'aktuell' if fresh else 'offen':<8} {reason}{tag}")
    return 0


def _cmd_bootstrap(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    report = bootstrap(
        layout,
        force=args.force,
        context_files=settings.context.files.names(),
        # Option 02: mit dem Wörterbuch der Hauptperiode gehören Straßen und Orte nicht hierher
        needs_dictionary=settings.period.dictionary == "own",
    )
    print(report.summary())
    return 0


def _cmd_export(layout: Layout) -> int:
    written = export_csv(layout)
    for path in written:
        print(path)
    print(f"{len(written)} CSV-Dateien geschrieben")
    return 0


def _cmd_profile(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    layout.ensure_dirs()
    PdfStore(layout.pdf_dir).ensure()
    steps = build_steps(settings, layout)
    names = args.steps or [s.name for s in steps if not s.network]
    for step in select_steps(steps, names):
        result = profile_step(
            step, settings, args.out, online=args.online, top=args.top, sort=args.sort
        )
        print(result.outcome.line())
        if result.path is not None:
            print(result.table, end="")
            print(f"Profil: {result.path}; Anzeige: uv run snakeviz {result.path}")
    return 0


def _print_controls(layout: Layout) -> int:
    """Tabelle 6 aus ``processed/regression_kontrollen.parquet``, je Modell und Stichprobe."""
    if not layout.controls.exists():
        raise MissingInputError(
            f"{layout.controls} fehlt; `georep run context controls` rechnet die Modelle."
        )
    table = pl.read_parquet(layout.controls)
    for (model, sample), rows in table.group_by(["modell", "stichprobe"], maintain_order=True):
        first = rows.row(0, named=True)
        print(
            f"{model} ({sample}): n={first['n']}, k={first['k']}, R²={first['r2']:.4f}, "
            f"korrigiert {first['r2_adj']:.4f}, F-p={first['f_p']:.5f}"
        )
        for row in rows.iter_rows(named=True):
            vif = "" if row["vif"] is None else f" VIF={row['vif']:.2f}"
            print(
                f"  {row['term']:<22} {row['koeffizient']:>12.4f} {row['standardfehler']:>10.4f}"
                f" p={row['p']:.5f}{vif}"
            )
    return 0


def _cmd_regress(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    if args.controls:
        return _print_controls(layout)
    results = pl.read_parquet(layout.results)
    print("alle:", regress(results).summary())
    exclude = args.exclude or list(settings.analysis.exclude_districts)
    if args.exclude:
        print(f"ohne {args.exclude}:", regress(results, exclude=args.exclude).summary())
    if args.varianten:
        # Option 06: die Sensitivitätstabelle der Berichtsseite als Text, ohne die Seite zu bauen.
        rows = sensitivity_rows(
            pl.read_parquet(layout.weighted),
            results,
            settings.weights,
            exclude,
            settings.topics.k > 0,
        )
        width = max((len(row.name) for row in rows), default=0)
        for row in rows:
            both = [
                f"{name}: {part.summary()}" if part else f"{name}: ohne Streuung"
                for name, part in (
                    ("alle", row.pair.all if row.pair else None),
                    (f"ohne {exclude}", row.pair.without if row.pair else None),
                )
                if part or name == "alle"
            ]
            rho = f", rho={row.rho:.3f}" if row.rho is not None else ""
            print(f"{row.name:<{width}} Summe {row.total:>9.1f}; " + "; ".join(both) + rho)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = load_settings(explicit=args.settings)
        _setup_logging(settings.log_level)
        configure_contracts(settings.contracts)
        layout = Layout.from_settings(settings)
        if args.command in ("run", "fetch"):
            return _cmd_run(args, settings, layout)
        if args.command == "steps":
            return _cmd_steps(settings, layout)
        if args.command == "status":
            return _cmd_status(args, settings, layout)
        if args.command == "bootstrap":
            return _cmd_bootstrap(args, settings, layout)
        if args.command == "export":
            return _cmd_export(layout)
        if args.command == "regress":
            return _cmd_regress(args, settings, layout)
        if args.command == "profile":
            return _cmd_profile(args, settings, layout)
    except (GeorepError, FileNotFoundError) as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
