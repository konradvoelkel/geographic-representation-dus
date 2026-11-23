"""``georep validate sample|tasks|merge|score <vorhaben>``: die Befehlszeile von F4.

Unterbefehle und Ausgabe stehen hier; ``cli.py`` hängt den Parser ein und ruft ``run``. So berührt
das Fundament die gemeinsame Datei nur mit drei Zeilen (plan-vorverarbeitung-2026-11.md, § 2.3).
Den Ablauf mit den Aufträgen an die Agenten beschreibt docs/validierung.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from georep.layout import Layout
from georep.settings import Settings
from georep.validation.sample import sample_project

PROJECT_HELP = "Ordner unter validation.root mit codebuch.toml, etwa 11-struktur"


def add_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    validate = sub.add_parser(
        "validate",
        help="Validierung mit zwei KI-Kodierern: Stichprobe, Kodierauftrag, Zusammenführen, "
        "Maße (Fundament F4, docs/validierung.md)",
    )
    actions = validate.add_subparsers(dest="action", required=True)

    sample = actions.add_parser(
        "sample", help="geschichtete Stichprobe nach dem Codebuch ziehen (stichprobe.csv)"
    )
    sample.add_argument("project", metavar="vorhaben", help=PROJECT_HELP)
    sample.add_argument(
        "--population",
        type=Path,
        help="Parquet der Grundgesamtheit statt sample.population aus dem Codebuch",
    )
    sample.add_argument(
        "--force", action="store_true", help="eine vorhandene Stichprobe neu ziehen"
    )


def run(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    """Einen Unterbefehl ausführen; Domänenfehler fängt ``cli.main``."""
    if args.action == "sample":
        report = sample_project(
            settings,
            layout,
            args.project,
            today=dt.date.today(),
            population=args.population,
            force=args.force,
        )
        print(report.line())
        for name, (total, drawn) in report.sample.strata.items():
            print(f"  {name or '(ohne Schicht)'}: {drawn} von {total}")
        return 0
    return 2
