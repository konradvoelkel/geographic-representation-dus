"""``georep pack``: aus einem gelaufenen Profil ein Datenpaket für das Repo machen (Punkt 56).

Die Gegenrichtung von ``bootstrap``: dieses Modul schreibt genau die Dateien, die jenes liest,
unter die Pfade, unter denen jenes sie sucht (``external/``, ``raw/``, ``cache/text/`` --
``Layout.reference_view`` setzt ``cache_root`` auf ``<reference_root>/cache``, darum der letzte).
Vorher stand das Rezept als sechs ``cp``-Zeilen im Runbook, und genau daran ist es schiefgegangen:
der Textstore auf dem Rechner des Laufs trug fünf Zeilen aus einer Stichprobe und 100 aus einer
synthetischen Fixture, und nur weil jemand nachgesehen hat, kamen sie nicht ins Repo.

Darum prüft ``pack`` und kopiert nicht blind. Zwei Zusicherungen über den Textstore, beide als
Abbruch mit Zahlen und Beispielen (``PackError``, ein Domänenfehler: eine Zeile auf stderr und
Exit 1):

1. **Jede Zeile kommt aus einem Lauf** (Spalte ``source`` in ``RUN_SOURCES``): aus einem PDF
   extrahiert (``pdf``) oder aus dem eingefrorenen Datensatz übernommen, aus dem dieses Profil
   bootstrappt (``reference``). Eine Fixture oder eine Stichprobe (``fixture``, ``stichprobe``)
   ist Testmaterial und gehört nicht in ein Paket, das sagt „so sah der Abruf aus".
2. **Jeder Name steht in ``papers.jsonl``** (als ``file_name`` eines Papers der Periode). Ein Text
   ohne Paper ist Ballast: die Kette fände ihn nie, der Join in ``corpus`` lässt ihn fallen.

Die PDFs bleiben draußen, ebenso Stamps, ``manifest.jsonl``, ``papers.progress.json`` und alles
Abgeleitete; was ein Paket tragen darf, hält ``tests/unit/test_data_packages.py`` fest. Zum Schluss
schreibt ``pack`` ein README-Gerüst mit der Prüfsummentabelle, die jener Test gegen die Dateien
hält -- und rührt ein vorhandenes README nicht an, denn die drei im Repo tragen mehr Prosa, als ein
Gerüst haben kann. Die Tabelle steht trotzdem immer auf stdout, zum Einsetzen von Hand.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from georep.errors import GeorepError
from georep.io import atomic_path, write_parquet, write_text
from georep.layout import Layout
from georep.prep.bodies import BODIES_SCHEMA_VERSION, CONSULTATION
from georep.settings import Settings
from georep.stores import TextStore

README_NAME = "README.md"
# Herkünfte, die ein Lauf wirklich erzeugt: ``pdf`` ist eine eigene Extraktion, ``reference`` die
# Übernahme aus dem Datensatz, auf den ``reference_root`` zeigt (so steht der Korpus der Arbeit im
# Store). ``fixture`` und ``stichprobe`` kommen aus ``tests/fixtures/`` und sind genau das, was am
# 2026-10-13 fast mitgepackt worden wäre.
RUN_SOURCES = frozenset({"pdf", "reference"})
# Die Grenze, bis zu der ein Abbruch Beispiele nennt; mehr liest niemand.
EXAMPLES = 5


class PackError(GeorepError):
    """Das Paket wäre nicht das, was es behauptet: fehlende Eingabe oder Fremdzeile im Store."""


@dataclass(frozen=True)
class PackedFile:
    """Eine Datei des Pakets: ihr Pfad darin, ihre Größe und ihre Prüfsumme."""

    name: str  # relativ zur Paketwurzel, mit "/" als Trenner
    bytes: int
    sha256: str


@dataclass(frozen=True)
class PackReport:
    target: Path
    files: tuple[PackedFile, ...]
    skipped: tuple[str, ...]  # vorhanden und ohne --force nicht überschrieben
    # Die Zahlen des Laufs als (Bezeichnung, Wert): „Paper", „Texte" beim Paket der Eingaben,
    # „Dokumente", „mit Beratungsfolge", „Organisationen" beim Paket der Folge (Punkt 58). Sie
    # stehen in der Zeile des Befehls und in der Tabelle des READMEs, und zwar genau einmal.
    figures: tuple[tuple[str, int], ...]
    readme_written: bool

    @property
    def total_bytes(self) -> int:
        return sum(entry.bytes for entry in self.files)

    def line(self) -> str:
        parts = [f"{len(self.files)} Dateien, {self.total_bytes} Bytes"]
        parts.append(", ".join(f"{value} {label}" for label, value in self.figures))
        if self.skipped:
            parts.append(f"{len(self.skipped)} vorhanden (nicht überschrieben)")
        parts.append(README_NAME if self.readme_written else f"{README_NAME} vorhanden")
        return f"{self.target}: " + ", ".join(parts)

    def table(self) -> str:
        """Die Tabelle „Datei, Bytes, SHA-256", wie sie in ein Paket-README gehört."""
        head = "| Datei | Bytes | SHA-256 |\n|---|---|---|\n"
        rows = [
            f"| `{entry.name}` | {_thousands(entry.bytes)} | `{entry.sha256}` |"
            for entry in self.files
        ]
        return head + "\n".join(rows) + "\n"


def _thousands(value: int) -> str:
    """``3980958`` als ``3 980 958``: dieselbe Schreibweise wie in den READMEs der Pakete."""
    return f"{value:,}".replace(",", " ")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def package_files(layout: Layout, settings: Settings) -> list[tuple[Path, str]]:
    """(Quelle, Pfad im Paket) für jede Eingabe, die ``bootstrap`` später sucht.

    Genau die Paare aus ``bootstrap``, nur umgekehrt: die Wahl-Eingaben und, wo das Profil sein
    Wörterbuch selbst holt (``period.dictionary = "own"``), Straßen und Orte. Was es für diese
    Stadt nicht gibt (Straßenverzeichnis, Wahlbezirksnamen, ein älterer Zuschnitt), fehlt hier,
    statt als leerer Pfad mitzufahren.
    """
    pairs: list[tuple[Path, str]] = [
        (layout.results_csv, f"external/{layout.results_file}"),
        (layout.districts_geojson, f"external/{layout.districts_file}"),
    ]
    if settings.period.dictionary == "own":
        pairs += [
            (layout.streets, "raw/streets_per_district.json"),
            (layout.pois, "raw/wikipedia_dict.json"),
        ]
    for source in (layout.streets_directory, layout.district_names_csv):
        if source is not None and source.is_file():
            pairs.append((source, f"external/{source.name}"))
    # Option 02: die zwei Eingaben des Crosswalks, wenn diese Periode einen eigenen Zuschnitt hat
    for source in (layout.district_shapes_geojson, layout.district_results_csv):
        if source.is_file():
            pairs.append((source, f"external/{source.name}"))
    pairs += [(layout.papers, "raw/papers.jsonl"), (layout.texts, "cache/text/texts.parquet")]
    return pairs


def paper_file_names(papers: Path) -> set[str]:
    """Die Dateinamen der Paper in ``papers.jsonl``; eine JSON-Zeile je Paper."""
    names: set[str] = set()
    for line in papers.read_text(encoding="utf-8").splitlines():
        if line.strip():
            name = json.loads(line).get("file_name")
            if name:
                names.add(str(name))
    return names


def check_text_store(layout: Layout) -> int:
    """Der Textstore trägt nur Texte aus PDFs dieser Periode; liefert ihre Zahl.

    Beide Abbrüche nennen Zahl und Beispiele, damit der Handgriff klar ist: eine Fremdzeile
    entfernt man im Store (STATUS.md, „Nächster Schritt"), ein verwaister Text verschwindet mit
    einem neuen ``run texts``.
    """
    store = TextStore(layout.texts)
    foreign = sorted(
        (name, str(row["source"]))
        for name, row in store.rows.items()
        if row["source"] not in RUN_SOURCES
    )
    if foreign:
        shown = ", ".join(f"{name} ({source})" for name, source in foreign[:EXAMPLES])
        raise PackError(
            f"{layout.texts}: {len(foreign)} von {len(store.rows)} Texten kommen nicht aus einem "
            f"Lauf dieses Profils ({shown}); erlaubt ist {sorted(RUN_SOURCES)}, ein Paket trägt "
            f"nur Abgerufenes"
        )
    known = paper_file_names(layout.papers)
    orphans = sorted(name for name in store.rows if name not in known)
    if orphans:
        raise PackError(
            f"{layout.texts}: {len(orphans)} Texte haben kein Paper in {layout.papers.name} "
            f"({', '.join(orphans[:EXAMPLES])}); sie fallen im Schritt corpus ohnehin heraus"
        )
    return len(store.rows)


def claim_target(layout: Layout, target: Path) -> Path:
    """Der Zielordner; er darf nicht in der Datenwurzel oder im Cache dieses Laufs liegen.

    ``Layout.guard_writable`` ist hier nicht zuständig und wäre falsch: das Ziel **ist** eine
    Referenzwurzel, und genau dorthin schreibt dieser Befehl -- als einziger, von Hand gerufen,
    nie aus einem Schritt. Was er verhindern muss, ist das Gegenteil: ein Paket über die Daten des
    Laufs zu legen, aus dem es entsteht.
    """
    resolved = target.resolve()
    for name, root in (("data_root", layout.data_root), ("cache_root", layout.cache_root)):
        other = root.resolve()
        if resolved == other or other in resolved.parents or resolved in other.parents:
            raise PackError(
                f"{target} liegt in {name} {root}; ein Paket gehört daneben, nicht hinein"
            )
    return target


def readme_skeleton(
    report: PackReport, *, profile: str, city: str, today: dt.date, command: str = "pack"
) -> str:
    """Das Gerüst eines Paket-READMEs: Tabelle fertig, Prosa als Platzhalter.

    Was nur ein Mensch weiß, steht als ``[…]`` da: woher die Dateien kommen, unter welcher Lizenz,
    was am Lauf auffiel. Was die Maschine weiß, steht fertig drin -- Größen, Prüfsummen, die
    Zahlen des Laufs, das Profil, das es liest.
    """
    rows = "\n".join(f"| {label} | {_thousands(value)} |" for label, value in report.figures)
    return f"""# Datenpaket {report.target.name} ({city}, gepackt am {today.isoformat()})

Die eingefrorenen **Eingaben** eines Laufs, damit GitHub Pages seine Seite ohne Netz baut
(`docs/decisions.md`, Punkt 56). Erzeugt mit
`georep --profile {profile} {command} {report.target}`;
`reference_root` des Profils `{profile}` zeigt hierher, und `bootstrap` kopiert nur.

Der Ordner wird **nur gelesen**: `Layout.guard_writable` verweigert jeden Schreibvorgang darunter,
die pre-commit-Hooks lassen ihn aus. Die PDFs liegen **nicht** im Paket, nur die Texte daraus.

## Inhalt mit Prüfsummen (SHA-256)

{report.table()}
Zusammen {_thousands(report.total_bytes)} Bytes. `tests/unit/test_data_packages.py` hält diese
Tabelle gegen die Dateien im Repo.

## Zahlen des Laufs

| Größe | Wert |
|---|---|
{rows}
| Abrufdatum | [nachzutragen] |

## Herkunft und Lizenz

[Je Datei: Quelle, Abrufdatum, Lizenz wörtlich. Muster: `reference/moenchengladbach/README.md`.]

## Was im Paket **nicht** liegt

- die PDFs und ihr `manifest.jsonl`,
- die Stamps (`*.stamp.json`) und `raw/papers.progress.json`,
- der HTTP-Cache (`http.sqlite`),
- alles Abgeleitete (`interim/`, `processed/`, `site/`).

## Was am Lauf auffiel

[Was ein Leser wissen muss, um die Zahlen nicht falsch zu lesen; sonst diesen Abschnitt löschen.]
"""


def pack(
    layout: Layout,
    settings: Settings,
    target: Path,
    *,
    force: bool = False,
    today: dt.date | None = None,
) -> PackReport:
    """Das Paket schreiben; fehlt eine Eingabe oder trägt der Store Fremdes, bricht es ab."""
    claim_target(layout, target)
    pairs = package_files(layout, settings)
    missing = [str(source) for source, _ in pairs if not source.is_file()]
    if missing:
        raise PackError(f"Eingaben fehlen, lief `georep run` für dieses Profil? {missing}")
    texts = check_text_store(layout)
    papers = sum(
        1 for line in layout.papers.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    files: list[PackedFile] = []
    skipped: list[str] = []
    for source, name in sorted(pairs, key=lambda pair: pair[1]):
        destination = target / name
        if destination.exists() and not force:
            skipped.append(name)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with atomic_path(destination) as tmp:
                shutil.copyfile(source, tmp)
        files.append(
            PackedFile(name=name, bytes=destination.stat().st_size, sha256=sha256_of(destination))
        )
    report = PackReport(
        target=target,
        files=tuple(files),
        skipped=tuple(skipped),
        figures=(("Paper", papers), ("Texte", texts)),
        readme_written=not (target / README_NAME).exists(),
    )
    return _with_readme(report, settings, today)


def _with_readme(
    report: PackReport, settings: Settings, today: dt.date | None, command: str = "pack"
) -> PackReport:
    """Das README-Gerüst schreiben, wenn keines liegt; die drei im Repo tragen mehr Prosa."""
    if report.readme_written:
        write_text(
            report.target / README_NAME,
            readme_skeleton(
                report,
                profile=settings.default_profile,
                city=settings.city.name,
                today=today or dt.date.today(),
                command=command,
            ),
        )
    return report


# --- Punkt 58: ein Paket, das nur die Beratungsfolge je Dokument trägt --------------------------


def consultation_rows(papers: Path) -> pl.DataFrame:
    """``id``, ``consultation_organizations`` und ``modified`` aus einer ``papers.jsonl``.

    Genau die drei Felder, die die zweite Quelle des Gremiums braucht (Punkt 58): die
    Dokument-ID als Schlüssel in den Korpus, die beratenden Gremien als Organisations-URLs und,
    weil es 15 KB kostet, der Stand des Datensatzes je Dokument. Alles andere -- Titel,
    Dokumentart, Hauptdatei -- steht schon im Paket der Periode oder in ihrer Referenz.
    """
    rows = [
        json.loads(line) for line in papers.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return pl.DataFrame(
        {
            "id": [str(row["id"]) for row in rows],
            CONSULTATION: [[str(url) for url in (row.get(CONSULTATION) or ())] for row in rows],
            "modified": [row.get("modified") for row in rows],
        },
        schema={"id": pl.String, CONSULTATION: pl.List(pl.String), "modified": pl.String},
    ).sort("id")


def pack_consultations(
    layout: Layout,
    settings: Settings,
    target: Path,
    *,
    force: bool = False,
    today: dt.date | None = None,
) -> PackReport:
    """Nur die Beratungsfolge je Dokument packen: ``raw/beratungsfolge.parquet`` (Punkt 58).

    Gedacht für die Periode, deren Korpus die Folge nicht trägt (die Hauptperiode Düsseldorfs
    kommt aus dem Altformat der Arbeit) und für die ein eigener Metadatenabruf sie geholt hat.
    Gepackt wird aus ``raw/papers.jsonl`` dieses Laufs -- wer den Vollabruf in einer eigenen
    Datenwurzel liegen hat, zeigt ``data_root`` mit ``--settings`` darauf.
    """
    claim_target(layout, target)
    if not layout.papers.is_file():
        raise PackError(f"{layout.papers} fehlt; lief `georep fetch papers` für dieses Profil?")
    frame = consultation_rows(layout.papers)
    name = f"raw/{layout.consultations.name}"
    destination = target / name
    skipped: list[str] = []
    if destination.exists() and not force:
        skipped.append(name)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_parquet(frame, destination, schema_version=BODIES_SCHEMA_VERSION)
    with_folge = int((frame.get_column(CONSULTATION).list.len() > 0).sum())
    organizations = frame.get_column(CONSULTATION).explode().drop_nulls().n_unique()
    report = PackReport(
        target=target,
        files=(
            PackedFile(
                name=name,
                bytes=destination.stat().st_size,
                sha256=sha256_of(destination),
            ),
        ),
        skipped=tuple(skipped),
        figures=(
            ("Dokumente", frame.height),
            ("mit Beratungsfolge", with_folge),
            ("verschiedene Organisationen", organizations),
        ),
        readme_written=not (target / README_NAME).exists(),
    )
    return _with_readme(report, settings, today, command="pack --consultations")
