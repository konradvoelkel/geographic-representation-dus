"""``georep publish``: die Stadtseiten zusammentragen und den Städtevergleich bauen (Option 01).

Je Stadt aus ``publish.cities`` wird der veröffentlichte Ordner ``data/<profil>/site/`` gelesen
und nach ``data/site/`` kopiert: die erste Stadt an die Wurzel, jede weitere nach
``data/site/<slug>/``. Seit Punkt 52 liegt auch die erste Stadt unter ihrem Slug, wird also
kopiert; damit bleibt ihre veröffentlichte Adresse die Wurzel, obwohl ihr Lauf einen Ordner
tiefer rechnet. Eine Stadt, deren Ordner ausnahmsweise schon die Wurzel ist (``profile`` von Hand
geleert), wird nicht kopiert. Aus ``summary.json``, ``wahlbezirke.geojson`` und
``wahlbezirke_auswertung.parquet`` beider Städte entsteht ``vergleich.html``; fehlt der Lauf
einer Stadt, sagt die Zusammenfassung das und der Vergleich entfällt.

Der Befehl ist wiederholbar: Zeit und Commit sind Eingaben, kopiert wird atomar über ein
temporäres Verzeichnis (mit einem Namen, den es noch nicht gibt), die Stamps der Schritte bleiben
dabei in der Datenwurzel, und nichts außerhalb des Zielordners wird angefasst. Weil er beim Kopieren
löscht, nimmt er nur einen Ordner an, der ihm gehört: die Standardwurzel ``<data_root>/site``, ein
leeres Verzeichnis oder eines mit seiner Markerdatei. Alles andere ist ein ``PublishTargetError``,
und `guard_writable` hält ihn von der Referenz fern.
"""

from __future__ import annotations

import datetime as dt
import html
import re
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import deal

from georep import __version__
from georep.errors import GeorepError
from georep.io import write_text
from georep.layout import Layout, ReferenceWriteError
from georep.report.comparison import (
    CitySite,
    ComparisonModel,
    build_comparison,
    read_city_site,
    table_rows,
)
from georep.report.model import format_de
from georep.report.render import CC0, GPL, REPOSITORY, environment, external_links
from georep.settings import Settings, load_settings

COMPARISON_NAME = "vergleich.html"
# Legt publish in seinen Zielordner, damit der nächste Lauf ihn als seinen erkennt und darin
# löschen darf (Review 2026-10-12: --out zeigt leicht auf einen Ordner, in dem anderes liegt).
MARKER_NAME = ".georep-publish"
# Präfix des Arbeitsordners, in den kopiert wird, bevor er an die Stelle des Ziels rutscht; den
# Namen dahinter vergibt mkdtemp, damit nie ein fremder Ordner im Weg steht (Review 2026-10-13).
STAGING_PREFIX = ".georep-publish-neu-"
# Der Schritt ``report`` legt seinen Stamp neben seine Ausgabe, also in die Stadtseite. Dort gehört
# er hin (er beschreibt den Lauf), im veröffentlichten Ordner ist er Ballast -- die rsync-Zeilen in
# deploy/bin/georep-monitor.sh lassen ihn seit Option 07 aus, die Kopie tat es nicht.
STAMPS = "*.stamp.json"
# Die Stadtseite lässt die Stelle frei, an der die Nachbarstädte stehen; erst ``publish`` weiß,
# welche Seiten wirklich daneben liegen, und setzt die Zeile (Review 2026-10-12: sonst trüge die
# veröffentlichte Seite Links auf Städte, deren Lauf noch fehlt).
NEIGHBOURS_MARKER = "<!--georep:weitere-staedte-->"
# Die Zeile steht vor der Marke; die Marke bleibt stehen, damit ein zweiter Lauf sie wieder
# ersetzen kann (die Seite der ersten Stadt wird nicht neu kopiert).
_NEIGHBOURS = re.compile(
    r'(?:<p class="meta" data-neighbours="1">.*?</p>\n?)?' + re.escape(NEIGHBOURS_MARKER),
    re.DOTALL,
)
# Die Vergleichsseite verlinkt nach außen nur das Repository und die Lizenz; die Städte liegen
# relativ daneben, die Quellen und Lizenzen der Daten nennt jede Stadtseite in ihrem Fuß.
COMPARISON_LINKS = frozenset({REPOSITORY, CC0, GPL})


class PublishTargetError(GeorepError):
    """Der Zielordner gehört nicht ``georep publish``; es löscht dort nichts."""


@dataclass(frozen=True)
class PublishSummary:
    cities: tuple[str, ...]  # Städte mit Lauf, in der Reihenfolge von publish.cities
    missing: tuple[str, ...]  # Städte ohne Lauf
    files: int
    bytes: int
    comparison: bool
    # Punkt 50: die veröffentlichten Seiten über dem Budget, als Pfad unter der Wurzel. Hier und
    # nicht nur im Schritt ``report``, weil erst ``publish`` die Zeile „Weitere Städte" in jede
    # Seite setzt und die Vergleichsseite dazulegt -- und weil die Seite mit dem Abschnitt „Zwei
    # Wahlperioden" durch diese Hand geht (Review 2026-10-13). Leer heißt: alle passen.
    over_budget: tuple[str, ...] = ()

    def line(self) -> str:
        parts = [f"{len(self.cities)} Städte" if len(self.cities) != 1 else "1 Stadt"]
        parts.append("1 Vergleich" if self.comparison else "kein Vergleich")
        parts.append(f"{self.files} Dateien, {format_de(self.bytes / 1e6, 1)} MB")
        line = ", ".join(parts)
        if self.missing:
            line += "; kein Lauf: " + ", ".join(self.missing)
        if self.over_budget:
            line += "; über dem Budget: " + ", ".join(self.over_budget)
        return line


def city_layout(settings: Settings, root: Layout, slug: str) -> Layout:
    """Das Layout einer Stadt unter derselben Datenwurzel; ihr Profil bestimmt den Unterordner.

    Die Dateinamen und der Unterordner kommen aus dem Profil der anderen Stadt, die Wurzeln aus
    dem Lauf, der veröffentlicht: so liest ``publish`` genau das, was ``georep run`` dort schrieb.
    """
    if slug == settings.city.slug:
        return root
    other = load_settings(profile=slug, cwd=Path("/nonexistent"))
    return replace(
        Layout.from_settings(other),
        data_root=root.data_root,
        cache_root=root.cache_root,
        reference_root=root.reference_root,
    )


# guard_writable wirft ReferenceWriteError; deal vergleicht exakte Typen, darum beide.
@deal.raises(PublishTargetError, ReferenceWriteError)
def claim_target(layout: Layout, out: Path | None) -> Path:
    """Der Zielordner, in dem publish löschen darf; legt ihn an und setzt die Markerdatei.

    Erlaubt sind die Standardwurzel ``<data_root>/site`` (dorthin gehört die Seite der ersten
    Stadt), ein leeres Verzeichnis und jedes, das die Markerdatei trägt.
    """
    default = layout.data_root / "site"
    root = default if out is None else out
    layout.guard_writable(root)
    if root.exists() and root.resolve() != default.resolve():
        known = (root / MARKER_NAME).is_file()
        if not known and any(root.iterdir()):
            raise PublishTargetError(
                f"{root} ist nicht leer und nicht von georep publish angelegt; "
                f"ein eigener Ordner oder einer mit {MARKER_NAME} darf es sein"
            )
    root.mkdir(parents=True, exist_ok=True)
    _mark(root)
    return root


def _mark(root: Path) -> None:
    """Die Markerdatei, an der ``claim_target`` einen eigenen Zielordner erkennt."""
    write_text(root / MARKER_NAME, f"georep publish {__version__}\n")


def _copy_tree(layout: Layout, source: Path, target: Path) -> None:
    """Atomar genug: erst neben das Ziel schreiben, dann tauschen.

    Der Arbeitsordner entsteht mit ``mkdtemp`` neben dem Ziel: dasselbe Dateisystem (``rename``
    ist dort ein Rename) und ein Name, den es noch nicht gibt. Vorher hieß er ``<ziel>.neu`` und
    wurde vor dem Kopieren weggeräumt -- das war harmlos, solange das Ziel ein Unterordner der
    beanspruchten Wurzel war. Seit Punkt 52 wird auch die erste Stadt kopiert, das Ziel ist dann
    die Wurzel selbst, und ihr Nachbar gehört publish nicht (Review 2026-10-13: ein fremder
    ``out.neu`` war weg). ``guard_writable`` hält beide aus der Referenz heraus; scheitert das
    Kopieren, bleibt das Ziel, wie es war, und der Arbeitsordner wird abgeräumt. Die Stamps der
    Schritte bleiben in der Datenwurzel (``STAMPS``).
    """
    parent = layout.guard_writable(target.parent)
    staging = Path(tempfile.mkdtemp(dir=parent, prefix=STAGING_PREFIX))
    try:
        layout.guard_writable(staging)
        # dirs_exist_ok: mkdtemp hat den Ordner schon angelegt. copytree setzt danach die Rechte
        # der Quelle auf ihn, sonst trüge der veröffentlichte Ordner die 0700 von mkdtemp.
        shutil.copytree(source, staging, dirs_exist_ok=True, ignore=shutil.ignore_patterns(STAMPS))
        if target.exists():
            shutil.rmtree(layout.guard_writable(target))
        staging.rename(target)
    finally:
        if staging.is_dir():
            shutil.rmtree(staging)


def neighbour_line(cities: Sequence[CitySite], index: int) -> str:
    """Die Zeile „Weitere Städte" für die Seite der Stadt ``index``; leer bei nur einer Stadt."""
    if len(cities) < 2:
        return ""
    up = "" if index == 0 else "../"
    links = [
        f'<a href="{html.escape(up + other.href, quote=True)}">{html.escape(other.name)}</a>'
        for position, other in enumerate(cities)
        if position != index
    ]
    return (
        '<p class="meta" data-neighbours="1">Weitere Städte: '
        + " · ".join(links)
        + f' · <a href="{up}{COMPARISON_NAME}">Städtevergleich</a></p>\n'
    )


def _replacement(text: str) -> Callable[[re.Match[str]], str]:
    return lambda _: text


def write_neighbours(cities: Sequence[CitySite], root: Path) -> None:
    """Setzt die Zeile in jede veröffentlichte Stadtseite und räumt die Marke weg."""
    for index, city in enumerate(cities):
        page = root / city.href / "index.html"
        text = page.read_text(encoding="utf-8")
        # Ersatz als Funktion, damit Backslashes und Gruppenzeichen im Text nichts bedeuten
        filled = neighbour_line(cities, index) + NEIGHBOURS_MARKER
        write_text(page, _NEIGHBOURS.sub(_replacement(filled), text, count=1))


def _tree_size(folder: Path) -> tuple[int, int]:
    files = [p for p in folder.rglob("*") if p.is_file() and p.name != MARKER_NAME]
    return len(files), sum(p.stat().st_size for p in files)


@deal.post(
    lambda result: set(external_links(result)) <= COMPARISON_LINKS,
    message="der Vergleich verlinkt nur Repository und Lizenz nach außen",
)
def render_comparison(model: ComparisonModel) -> str:
    template = environment().get_template("vergleich.html.j2")
    return template.render(
        model=model,
        rows=table_rows(model),
        links={"repository": REPOSITORY, "cc0": CC0, "gpl": GPL},
    )


def _over_budget(root: Path, budget: int) -> tuple[str, ...]:
    """Die veröffentlichten HTML-Seiten über dem Budget, als Pfad unter der Wurzel (Punkt 50).

    ``budget`` von 0 schaltet die Prüfung ab, wie überall. Geprüft werden die Seiten und nicht die
    Downloads: das Budget ist eine Verabredung über die Seite, die ein Leser lädt.
    """
    if not budget:
        return ()
    found = sorted(
        str(path.relative_to(root)) for path in root.rglob("*.html") if path.stat().st_size > budget
    )
    return tuple(found)


def publish_sites(
    settings: Settings,
    layout: Layout,
    *,
    now: dt.datetime,
    commit: str | None = None,
    out: Path | None = None,
) -> PublishSummary:
    """Kopiert die Stadtseiten in den Veröffentlichungsordner und baut den Vergleich."""
    slugs = list(settings.publish.cities) or [settings.city.slug]
    root = claim_target(layout, out)
    found: list[CitySite] = []
    missing: list[str] = []
    for index, slug in enumerate(slugs):
        source = city_layout(settings, layout, slug).site
        target = root if index == 0 else root / slug
        if not (source / "index.html").is_file():
            missing.append(slug)
            # Ein Stadtordner ohne Lauf wäre tote Last: kein Link zeigt hin, die Zahlen sind alt
            if index > 0 and target.is_dir():
                shutil.rmtree(target)
            continue
        href = "" if index == 0 else f"{slug}/"
        if source.resolve() != target.resolve():
            _copy_tree(layout, source, target)
        found.append(read_city_site(target, href, settings.geo.working_crs))
    # Die Kopie der ersten Stadt ersetzt den ganzen Zielordner, mit ihm den Marker aus claim_target;
    # ohne ihn verweigerte der zweite Lauf in denselben Ordner (2026-10-12)
    _mark(root)
    write_neighbours(found, root)
    comparison = len(found) >= 2
    if comparison:
        model = build_comparison(tuple(found), now=now, version=__version__, commit=commit)
        write_text(root / COMPARISON_NAME, render_comparison(model))
    elif (root / COMPARISON_NAME).exists():
        # Eine Stadt weniger als beim letzten Mal: der alte Vergleich wäre eine Lüge
        (root / COMPARISON_NAME).unlink()
    files, size = _tree_size(root)
    return PublishSummary(
        cities=tuple(city.slug for city in found),
        missing=tuple(missing),
        files=files,
        bytes=size,
        comparison=comparison,
        over_budget=_over_budget(root, settings.report.page_budget_bytes),
    )
