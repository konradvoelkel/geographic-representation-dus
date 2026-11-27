"""``georep validate sample|tasks|import|merge|score <vorhaben>``: die Befehlszeile von F4.

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
from georep.validation.importer import import_project
from georep.validation.merge import Models, merge_project
from georep.validation.paths import CODERS
from georep.validation.sample import sample_project
from georep.validation.score import score_project
from georep.validation.tasks import task_project

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

    tasks = actions.add_parser(
        "tasks",
        help="Kodierauftrag, leere Antworten und Codebuch eines Kodierers schreiben "
        "(lokal unter validation.coding_root, nie im Repo)",
    )
    tasks.add_argument("project", metavar="vorhaben", help=PROJECT_HELP)
    tasks.add_argument("--coder", choices=CODERS, required=True, help="Kodierer A oder B")
    tasks.add_argument(
        "--texts",
        type=Path,
        help="Rohtextstore (Spalten name, text) statt rohtexte.parquet neben dem Textstore; "
        'nur bei text.source = "raw"',
    )
    tasks.add_argument(
        "--spans", type=Path, help="Spannen nach F3 als Parquet statt text.spans aus dem Codebuch"
    )
    tasks.add_argument(
        "--population",
        type=Path,
        help="Grundgesamtheit wie bei sample (bei der Einheit span für value und extractor)",
    )
    tasks.add_argument(
        "--force", action="store_true", help="auch über begonnene Antworten schreiben"
    )

    merge = actions.add_parser(
        "merge",
        help="Antworten von A und B zusammenführen: Auftrag der Schlichtung für die "
        "Uneinigkeiten, danach labels.csv, README.md und guete.json",
    )
    merge.add_argument("project", metavar="vorhaben", help=PROJECT_HELP)
    add_model_options(merge)
    merge.add_argument("--force", action="store_true", help="vorhandene Labels neu schreiben")

    imported = actions.add_parser(
        "import",
        help="vorläufige Antwortdateien (antworten-A.jsonl, antworten-B.jsonl, schlichtung.jsonl) "
        "nach [provisional] im Codebuch übernehmen",
    )
    imported.add_argument("project", metavar="vorhaben", help=PROJECT_HELP)
    imported.add_argument(
        "--from", dest="source", type=Path, required=True, help="Ordner mit den Antwortdateien"
    )
    imported.add_argument("--force", action="store_true", help="vorhandene Antworten ersetzen")

    score = actions.add_parser(
        "score",
        help="Übereinstimmung der Kodierer und, mit --pred, die Güte eines Verfahrens gegen die "
        "Labels (guete.json)",
    )
    score.add_argument("project", metavar="vorhaben", help=PROJECT_HELP)
    score.add_argument(
        "--pred",
        type=Path,
        help="Ausgabe des Verfahrens als Parquet: id und label, bei query_document query, id, score",
    )


def add_model_options(parser: argparse.ArgumentParser) -> None:
    """``--model`` für alle drei Rollen, ``--model-a``, ``--model-b``, ``--model-adjudicator`` je Rolle."""
    parser.add_argument(
        "--model",
        help="Modell aller drei Rollen, wo keine eigene Angabe steht, wie es im README steht "
        "(etwa claude-opus-5-5)",
    )
    parser.add_argument("--model-a", help="Modell von Kodierer A")
    parser.add_argument(
        "--model-b",
        help="Modell von Kodierer B; für neue Messungen ein anderes als A (docs/validierung.md, § 3)",
    )
    parser.add_argument("--model-adjudicator", help="Modell der Schlichtung")
    parser.set_defaults(model_parser=parser)


def models_of(args: argparse.Namespace) -> Models:
    """Das Modell je Rolle; fehlt eines, ist es ein Bedienfehler (Exit 2 wie bei argparse)."""
    found = [args.model_a or args.model, args.model_b or args.model]
    found.append(args.model_adjudicator or args.model)
    if not all(found):
        args.model_parser.error(
            "jede Rolle braucht ein Modell: --model für alle oder --model-a, --model-b und "
            "--model-adjudicator"
        )
    return Models(*found)


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
    if args.action == "tasks":
        written = task_project(
            settings,
            layout,
            args.project,
            args.coder,
            texts=args.texts,
            spans=args.spans,
            population=args.population,
            force=args.force,
        )
        print(written.line())
        return 0
    if args.action == "merge":
        merged = merge_project(
            settings,
            layout,
            args.project,
            models=models_of(args),
            today=dt.date.today(),
            force=args.force,
        )
        print("\n".join(merged.lines()))
        return 0
    if args.action == "import":
        taken = import_project(settings, layout, args.project, args.source, force=args.force)
        print("\n".join(taken.lines()))
        return 0
    if args.action == "score":
        scored = score_project(settings, layout, args.project, pred=args.pred)
        print("\n".join(scored.lines()))
        return 0
    return 2
