"""Kommandozeile: ``georep run|steps|status|bootstrap|export|regress``.

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
from georep.errors import GeorepError
from georep.export import export_csv
from georep.layout import Layout
from georep.pipeline import build_steps, freshness, run_pipeline
from georep.settings import Settings, load_settings, settings_files
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

    sub.add_parser("steps", help="Schritte mit Eingaben und Ausgaben")
    sub.add_parser("status", help="Settings, Pfade, Frische jedes Schritts")

    boot = sub.add_parser("bootstrap", help="Referenzdatensatz nach data_root übernehmen")
    boot.add_argument("--force", action="store_true", help="vorhandene Dateien überschreiben")

    sub.add_parser("export", help="Parquet-Ergebnisse als CSV neben die Parquet-Dateien schreiben")

    reg = sub.add_parser("regress", help="Regression Trefferquote -> Wahlbeteiligung")
    reg.add_argument("--exclude", type=int, nargs="*", default=[], help="Wahlbezirke auslassen")
    return parser


def _cmd_run(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    layout.ensure_dirs()
    outcomes = run_pipeline(
        build_steps(settings, layout), settings, args.steps, force=args.force, dry_run=args.dry_run
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
        print(f"{step.name:<12} <- {', '.join(p.name for p in step.inputs)}")
        print(f"{'':<12} -> {', '.join(p.name for p in step.outputs)}")
    return 0


def _cmd_status(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    print(f"georep {__version__}, Settings-Fingerprint {settings.fingerprint()}")
    files = settings_files(args.settings)
    print("Settings:   defaults.toml" + "".join(f" < {p}" for p in files))
    print(f"data_root:  {layout.data_root.resolve()}")
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
        print(f"{step.name:<12} {'aktuell' if fresh else 'offen':<8} {reason}")
    return 0


def _cmd_bootstrap(args: argparse.Namespace, layout: Layout) -> int:
    report = bootstrap(layout, force=args.force)
    print(report.summary())
    return 0


def _cmd_export(layout: Layout) -> int:
    written = export_csv(layout)
    for path in written:
        print(path)
    print(f"{len(written)} CSV-Dateien geschrieben")
    return 0


def _cmd_regress(args: argparse.Namespace, layout: Layout) -> int:
    results = pl.read_parquet(layout.results)
    print("alle:", regress(results).summary())
    if args.exclude:
        print(f"ohne {args.exclude}:", regress(results, exclude=args.exclude).summary())
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = load_settings(explicit=args.settings)
        _setup_logging(settings.log_level)
        layout = Layout.from_settings(settings)
        if args.command == "run":
            return _cmd_run(args, settings, layout)
        if args.command == "steps":
            return _cmd_steps(settings, layout)
        if args.command == "status":
            return _cmd_status(args, settings, layout)
        if args.command == "bootstrap":
            return _cmd_bootstrap(args, layout)
        if args.command == "export":
            return _cmd_export(layout)
        if args.command == "regress":
            return _cmd_regress(args, layout)
    except (GeorepError, FileNotFoundError) as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
