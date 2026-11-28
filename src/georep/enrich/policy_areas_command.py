"""``georep policy-areas export <profil>``: die Eingabe des Klassifikators von Vorhaben 19 schreiben.

Messdokument ``docs/plans/19-politikfelder.md``, § 6 und § 10, Punkt 3. Der Klassifikator (Weg 3b)
läuft außerhalb des Pakets im Trainings-Venv; er liest nur diese Datei, je Korpus-ID eine Zeile mit
Titel und Textanfang (``georep.enrich.policy_areas.classifier_input``). Das Profil steht als
Argument, weil die Datei genau zu seinem Korpus gehört; ``--profile`` davor darf nur dasselbe sagen.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from georep.enrich.policy_areas import INPUT_SCHEMA_VERSION, export_input, export_path
from georep.io import write_parquet
from georep.layout import Layout
from georep.settings import Settings

COMMAND = "policy-areas"


def add_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    areas = sub.add_parser(
        COMMAND, help="Politikfelder (Vorhaben 19): die Eingabe des Klassifikators schreiben"
    )
    actions = areas.add_subparsers(dest="areas_action", required=True)
    export = actions.add_parser(
        "export",
        help="je Korpus-ID Titel und Textanfang des Rohtexts als Parquet, für das Trainingsskript",
    )
    export.add_argument(
        "areas_profile", metavar="profil", help="Paketprofil (`georep profiles` listet sie)"
    )
    export.add_argument(
        "--out",
        type=Path,
        help="Zieldatei; sonst <data_root>/<profil>/messung/19-politikfelder-eingabe.parquet",
    )


def profile_of(args: argparse.Namespace) -> str | None:
    """Das Profil, mit dem ``main`` die Settings lädt; ``None``, wenn ``--profile`` widerspricht."""
    if args.profile and args.profile != args.areas_profile:
        return None
    return str(args.areas_profile)


def run(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    frame = export_input(layout, settings)
    target = layout.guard_writable(args.out or export_path(layout))
    target.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(frame, target, schema_version=INPUT_SCHEMA_VERSION)
    with_text = int(frame.get_column("mit_text").sum())
    cut = int(frame.get_column("gekuerzt").sum())
    print(
        f"{target}: {frame.height} Dokumente, {with_text} mit Rohtext, davon {cut} länger als "
        f"{settings.policy_areas.chars} Zeichen"
    )
    return 0
