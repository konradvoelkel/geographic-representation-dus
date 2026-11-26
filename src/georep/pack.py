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

from georep.enrich.embeddings import embedding_files
from georep.errors import GeorepError
from georep.io import atomic_path, digest, write_parquet, write_text
from georep.layout import Layout
from georep.prep.bodies import CONSULTATION
from georep.prep.raw_texts import RAW_SUFFIX
from georep.prep.references import MASK, ReferenceRules, mask_person_names
from georep.search.vectors import NEIGHBORS_SCHEMA, NEIGHBORS_SCHEMA_VERSION
from georep.settings import Settings
from georep.stores import RAW_TEXT_SCHEMA_VERSION, RawTextStore, TextStore

README_NAME = "README.md"
# Herkünfte, die ein Lauf wirklich erzeugt: ``pdf`` ist eine eigene Extraktion, ``reference`` die
# Übernahme aus dem Datensatz, auf den ``reference_root`` zeigt (so steht der Korpus der Arbeit im
# Store). ``fixture`` und ``stichprobe`` kommen aus ``tests/fixtures/`` und sind genau das, was am
# 2026-10-13 fast mitgepackt worden wäre.
RUN_SOURCES = frozenset({"pdf", "reference"})
# Die Grenze, bis zu der ein Abbruch Beispiele nennt; mehr liest niemand.
EXAMPLES = 5
# Punkt 58: die Schema-Version von ``raw/beratungsfolge.parquet``. Eigene Konstante und nicht
# ``BODIES_SCHEMA_VERSION``: das ist die Version der **Ausgabe** des Schritts ``bodies``, und die
# steigt, wenn dort eine Spalte dazukommt -- das Paket hat davon keine (Review 2026-10-14).
CONSULTATIONS_SCHEMA_VERSION = 1


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
    # Punkt 58: der Organisationskatalog, wenn der Netzschritt lief. Er ist der Beleg für die
    # Namen und Kürzel in ``[bodies]`` und ``[originators]``; ohne ihn stünden sie ohne Quelle da.
    if layout.organizations.is_file():
        pairs.append((layout.organizations, "raw/organizations.json"))
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
    with_folge = int((frame.get_column(CONSULTATION).list.len() > 0).sum())
    if not with_folge:
        # Review 2026-10-14: ein Paket ohne eine einzige Beratungsfolge ist kein Paket, sondern
        # eine Liste von IDs -- und es entsteht genau dann, wenn jemand aus der Datenwurzel eines
        # Laufs packt, der die Metadaten aus dem Altformat der Arbeit gebootstrappt hat.
        raise PackError(
            f"{layout.papers}: keines der {frame.height} Dokumente trägt eine Beratungsfolge; "
            "das Paket wäre leer. Gepackt wird aus einem Metadatenabruf (`georep fetch papers`), "
            "nicht aus einem Lauf, dessen papers.jsonl aus dem Altformat der Arbeit kommt."
        )
    name = f"raw/{layout.consultations.name}"
    destination = target / name
    skipped: list[str] = []
    if destination.exists() and not force:
        skipped.append(name)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_parquet(frame, destination, schema_version=CONSULTATIONS_SCHEMA_VERSION)
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


# --- Punkt 68: ein Paket, das nur den Textstore trägt -------------------------------------------

TEXTS_NAME = "cache/text/texts.parquet"


def pack_texts(
    layout: Layout,
    settings: Settings,
    target: Path,
    *,
    force: bool = False,
    today: dt.date | None = None,
) -> PackReport:
    """Nur den Textstore packen: ``cache/text/texts.parquet`` (Punkt 68).

    Gedacht für die Periode, deren Metadaten aus dem Altformat der Arbeit kommen und deren Texte
    ein eigener Lauf aus den PDFs neu gelesen hat (die Hauptperiode Düsseldorfs seit pypdf
    7.1.0): die Paper bleiben die der Referenz, ``[bootstrap].texts`` legt nur die Texte darüber.
    Geprüft wird wie bei ``pack`` (jede Zeile aus einem Lauf, jeder Name ein Paper) und dazu, dass
    überhaupt ein Text aus einem PDF kommt -- sonst wäre das Paket der Textstore der Referenz
    ein zweites Mal.
    """
    claim_target(layout, target)
    missing = [str(path) for path in (layout.papers, layout.texts) if not path.is_file()]
    if missing:
        raise PackError(f"{missing} fehlen; lief `georep run texts` für dieses Profil?")
    texts = check_text_store(layout)
    from_pdf = sum(1 for row in TextStore(layout.texts).rows.values() if row["source"] == "pdf")
    if not from_pdf:
        raise PackError(
            f"{layout.texts}: keiner der {texts} Texte ist aus einem PDF gelesen; das Paket wäre "
            "der Textstore der Referenz. Gepackt wird nach einem Lauf mit den PDFs der Periode."
        )
    destination = target / TEXTS_NAME
    skipped: list[str] = []
    if destination.exists() and not force:
        skipped.append(TEXTS_NAME)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with atomic_path(destination) as tmp:
            shutil.copyfile(layout.texts, tmp)
    report = PackReport(
        target=target,
        files=(
            PackedFile(
                name=TEXTS_NAME, bytes=destination.stat().st_size, sha256=sha256_of(destination)
            ),
        ),
        skipped=tuple(skipped),
        figures=(("Texte", texts), ("aus PDFs", from_pdf), ("übernommen", texts - from_pdf)),
        readme_written=not (target / README_NAME).exists(),
    )
    return _with_readme(report, settings, today, command="pack --texts")


# --- Fundament F1: ein Paket, das nur den Rohtextstore trägt -------------------------------------

RAW_TEXTS_NAME = "cache/text/rohtexte.parquet"
# Review F1, M4: das Rohtextpaket liegt im Repo, und jedes Byte steht in jedem Klon. zstd auf Stufe
# 19 macht es 17 % kleiner als die Vorgabe von Polars (gemessen am Paket der Hauptperiode,
# 2026-11-23); das Schreiben dauert Sekunden statt Bruchteilen, und das zahlt nur ``pack``, nie ein
# Lauf. Der Cache bleibt bei der Vorgabe, denn ``raw_texts`` schreibt ihn bei jeder Änderung neu.
RAW_TEXTS_ZSTD_LEVEL = 19


def check_raw_bridge(layout: Layout, store: RawTextStore) -> None:
    """Jeder Rohtext gehört zu einem Text des Textstores: gleicher PDF-Hash, gleicher Extraktor.

    Review F1, N2. Nur dann plättet der Rohtext zum Text, den die Suche liest, und das Paket hält,
    was die Eigenschaft von Fundament F1 verspricht. Ein Rohtext, dessen PDF sich seit dem Text
    geändert hat (anderer Hash), oder der mit einem anderen pypdf gelesen ist, bricht ab -- mit
    Zahl und Beispielen; der Handgriff ist ein neuer Lauf von ``texts`` und ``raw_texts``.
    """
    texts = TextStore(layout.texts).rows
    problems: dict[str, list[str]] = {
        "keinen Text": [],
        "einen anderen PDF-Hash": [],
        "einen anderen Extraktor": [],
    }
    for name, row in sorted(store.rows.items()):
        text = texts.get(name)
        if text is None:
            problems["keinen Text"].append(name)
        elif text["pdf_sha256"] != row["pdf_sha256"]:
            problems["einen anderen PDF-Hash"].append(name)
        elif f"{text['extractor']}{RAW_SUFFIX}" != row["extractor"]:
            problems["einen anderen Extraktor"].append(name)
    found = [(what, names) for what, names in problems.items() if names]
    if found:
        said = "; ".join(
            f"{len(names)} haben im Textstore {what} ({', '.join(names[:EXAMPLES])})"
            for what, names in found
        )
        raise PackError(f"{layout.raw_texts}: Rohtexte ohne Brücke zum Textstore: {said}")


def pack_raw_texts(
    layout: Layout,
    settings: Settings,
    target: Path,
    *,
    force: bool = False,
    today: dt.date | None = None,
    level: int = RAW_TEXTS_ZSTD_LEVEL,
) -> PackReport:
    """Nur den Rohtextstore packen: ``cache/text/rohtexte.parquet`` (Fundament F1).

    Wie ``pack_texts`` für den zweiten Store: GitHub Pages hat keine PDFs, also kommt der Rohtext
    dorthin nur als Paket, und ``[bootstrap].raw_texts`` legt es an. Geprüft wird, dass jeder Name
    ein Paper dieser Periode ist und dass es überhaupt einen Rohtext gibt -- ohne PDFs schreibt
    der Schritt ``raw_texts`` einen leeren Store, und der wäre kein Paket, sondern ein Irrtum.
    Ein Name ohne Rohtext ist dagegen erlaubt (ein defektes PDF); die Zahl steht im README.
    Dazu die Brücke zum Textstore (``check_raw_bridge``, Review F1, N2). Das Paket ist keine
    Kopie, sondern derselbe Frame, mit zstd auf Stufe ``level`` neu geschrieben (Review F1, M4).
    """
    claim_target(layout, target)
    paths = (layout.papers, layout.texts, layout.raw_texts)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise PackError(f"{missing} fehlen; lief `georep run raw_texts` für dieses Profil?")
    store = RawTextStore(layout.raw_texts)
    if store.stale:  # Review F1, dritte Runde: eine alte Version liest der Store als leer
        raise PackError(
            f"{layout.raw_texts}: {store.stale}; erst `georep run raw_texts` mit den PDFs der "
            "Periode, dann packen"
        )
    if not len(store):
        raise PackError(
            f"{layout.raw_texts}: kein einziger Rohtext; der Schritt raw_texts lief ohne PDFs. "
            "Gepackt wird nach einem Lauf mit den PDFs der Periode."
        )
    known = paper_file_names(layout.papers)
    orphans = sorted(name for name in store.rows if name not in known)
    if orphans:
        raise PackError(
            f"{layout.raw_texts}: {len(orphans)} Rohtexte haben kein Paper in "
            f"{layout.papers.name} ({', '.join(orphans[:EXAMPLES])})"
        )
    check_raw_bridge(layout, store)
    destination = target / RAW_TEXTS_NAME
    skipped: list[str] = []
    if destination.exists() and not force:
        skipped.append(RAW_TEXTS_NAME)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_parquet(
            pl.read_parquet(layout.raw_texts),
            destination,
            schema_version=RAW_TEXT_SCHEMA_VERSION,
            compression_level=level,
        )
    pages = sum(int(row["pages"]) for row in store.rows.values())  # type: ignore[call-overload]
    report = PackReport(
        target=target,
        files=(
            PackedFile(
                name=RAW_TEXTS_NAME,
                bytes=destination.stat().st_size,
                sha256=sha256_of(destination),
            ),
        ),
        skipped=tuple(skipped),
        figures=(
            ("Rohtexte", len(store)),
            ("Seiten", pages),
            ("Hauptdateien ohne Rohtext", len(known - set(store.rows))),
        ),
        readme_written=not (target / README_NAME).exists(),
    )
    return _with_readme(report, settings, today, command="pack --raw-texts")


# --- Vorhaben 14: ein Paket mit den Anlagen je Drucksache ----------------------------------------

ATTACHMENTS_NAME = "raw/anlagen.parquet"
# Die Schema-Version des Pakets, eigen wie ``CONSULTATIONS_SCHEMA_VERSION``: die Ausgaben des
# Vorhabens zählen ``PROCEDURES_SCHEMA_VERSION`` hoch, das Paket nicht mit.
ATTACHMENTS_SCHEMA_VERSION = 1


def cached_pages(cache: Path, endpoint: str) -> list[tuple[dt.date, bytes]]:
    """Die Seiten der Paper-Liste im HTTP-Cache, nur lesend: (Abrufdatum, Antwort), in Speicherfolge.

    Gelesen wird die SQLite-Datei von requests-cache direkt und ohne Schreibrecht
    (``mode=ro``), nicht über eine Session: eine Session legte Tabellen an und räumte
    abgelaufene Einträge weg, und genau die alten Seiten eines abgeschlossenen Abrufs sind hier
    die Quelle. Gezählt wird jede Antwort 200, deren Pfad der Endpunkt ist (mit jeder Abfrage
    dahinter: Seite, ``modified_since``).
    """
    import sqlite3
    from contextlib import closing

    from requests_cache.serializers import SERIALIZERS

    if not cache.is_file():
        raise PackError(f"{cache} fehlt; die Anlagen kommen aus dem HTTP-Cache eines Abrufs")
    serializer = SERIALIZERS["pickle"]
    pages: list[tuple[dt.date, bytes]] = []
    # ``closing``: der Kontext einer sqlite3-Verbindung beendet nur die Transaktion, nicht sie
    with closing(sqlite3.connect(f"file:{cache}?mode=ro", uri=True)) as connection:
        for (value,) in connection.execute("select value from responses order by rowid"):
            response = serializer.loads(value)
            if response.status_code == 200 and response.url.split("?", 1)[0] == endpoint:
                pages.append((response.created_at.date(), response.content))
    return pages


def attachment_rows(
    pages: list[tuple[dt.date, bytes]], ids: set[str], rules: ReferenceRules
) -> pl.DataFrame:
    """Je Drucksache in ``ids`` ihre Anlagen (Name, Datum) aus dem jüngsten Stand im Cache.

    Eine Drucksache kann auf mehreren Seiten stehen (zwei Abrufe, ``modified_since``); es gilt
    das Objekt mit dem jüngsten ``modified``, bei Gleichstand das zuerst gespeicherte. Das Datum
    einer Anlage ist ihr ``date``, sonst der Tag von ``created``; die Folge ist die des Servers.
    Ein Name hinter einer Anrede oder einem Titel wird zu „…" (Review K1,
    ``prep.references.mask_person_names``): das Paket liegt im Repo.
    """
    from georep.analysis.procedures import ATTACHMENT_SCHEMA
    from georep.oparl import PaperPage

    newest: dict[str, tuple[dt.datetime | None, dt.date, list[dict[str, object]]]] = {}
    for fetched, content in pages:
        for paper in PaperPage.model_validate_json(content).data:
            if paper.id not in ids:
                continue
            seen = newest.get(paper.id)
            if seen is not None and (
                paper.modified is None or (seen[0] and seen[0] >= paper.modified)
            ):
                continue
            files: list[dict[str, object]] = [
                {
                    "name": mask_person_names(f.name or "", rules),
                    "datum": f.date or (f.created.date() if f.created else None),
                }
                for f in paper.auxiliary_file
            ]
            newest[paper.id] = (paper.modified, fetched, files)
    rows = [(doc_id, fetched, files) for doc_id, (_, fetched, files) in sorted(newest.items())]
    return pl.DataFrame(rows, schema=ATTACHMENT_SCHEMA, orient="row")


def pack_attachments(
    layout: Layout,
    settings: Settings,
    target: Path,
    *,
    force: bool = False,
    today: dt.date | None = None,
) -> PackReport:
    """Nur die Anlagen je Drucksache packen: ``raw/anlagen.parquet`` (Vorhaben 14).

    Die Anlagen stehen weder im Korpus noch in einem Paket, nur in den OParl-Objekten, die ein
    Metadatenabruf im HTTP-Cache hinterlässt (``auxiliaryFile``: Name und Datum; darin die
    „Antwort der Verwaltung" auf eine Anfrage, Messdokument § 3.6). Gepackt werden die
    Drucksachen des eigenen Korpus und der Nachbarperioden aus ``procedures.related``, damit ein
    Paket alle Perioden einer Stadt trägt. Eine Drucksache, die der Cache nicht kennt, fehlt im
    Paket (unbekannt); eine mit leerer Liste hat keine Anlage.
    """
    from georep.enrich.procedures import neighbours, read_papers

    claim_target(layout, target)
    if not layout.corpus.is_file():
        raise PackError(f"{layout.corpus} fehlt; lief `georep run corpus` für dieses Profil?")
    ids = set(pl.read_parquet(layout.corpus, columns=["id"]).get_column("id").to_list())
    for period in neighbours(settings):
        ids |= {record.id for record in read_papers(period.papers)}
    rules = ReferenceRules.from_settings(settings.procedures)
    pages = cached_pages(layout.http_cache, settings.sources.oparl.endpoint)
    frame = attachment_rows(pages, ids, rules)
    masked = int(
        frame.get_column("anlagen")
        .list.eval(pl.element().struct.field("name").str.contains(MASK, literal=True))
        .list.sum()
        .sum()
    )
    if not frame.height:
        raise PackError(
            f"{layout.http_cache}: keine der {len(ids)} Drucksachen steht auf einer Seite von "
            f"{settings.sources.oparl.endpoint}; das Paket wäre leer"
        )
    destination = target / ATTACHMENTS_NAME
    skipped: list[str] = []
    if destination.exists() and not force:
        skipped.append(ATTACHMENTS_NAME)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_parquet(
            frame,
            destination,
            schema_version=ATTACHMENTS_SCHEMA_VERSION,
            compression_level=RAW_TEXTS_ZSTD_LEVEL,
        )
    counts = frame.get_column("anlagen").list.len()
    report = PackReport(
        target=target,
        files=(
            PackedFile(
                name=ATTACHMENTS_NAME,
                bytes=destination.stat().st_size,
                sha256=sha256_of(destination),
            ),
        ),
        skipped=tuple(skipped),
        figures=(
            ("Drucksachen", frame.height),
            ("mit Anlage", int((counts > 0).sum())),
            ("Anlagen", int(counts.sum())),
            ("nicht im Cache", len(ids) - frame.height),
            ("Anlagennamen mit maskiertem Personennamen", masked),
        ),
        readme_written=not (target / README_NAME).exists(),
    )
    return _with_readme(report, settings, today, command="pack --attachments")


# --- Vorhaben 18: ein Paket, das nur die ähnlichen Dokumente trägt ------------------------------

NEIGHBORS_NAME = "raw/aehnliche_dokumente_paket.parquet"


def _stamp_of(path: Path) -> dict[str, object]:
    stamp = path.with_name(path.name + ".stamp.json")
    if not stamp.is_file():
        raise PackError(f"{stamp.name} fehlt; lief `georep run --models embeddings neighbors`?")
    loaded = json.loads(stamp.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def neighbors_identity(layout: Layout) -> dict[str, object]:
    """Modell, Digest und Prompt-Version der Vektoren, aus denen die Nachbartabelle stammt.

    Geprüft wird die Kette: die Tabelle ist aus genau den Dokumentvektoren gerechnet, die jetzt
    neben ihr liegen (ihr Hash steht im Stamp von ``neighbors``), und die Vektoren aus einem
    vollständigen Lauf (kein ``open`` im Stamp von ``embeddings``). Eine Tabelle, die selbst aus
    einem Paket kam, packt dieser Befehl nicht noch einmal.
    """
    files = embedding_files(layout)
    for path in (files.neighbors, files.documents, layout.papers):
        if not path.is_file():
            raise PackError(f"{path} fehlt; lief `georep run --models` für dieses Profil?")
    inputs = _stamp_of(files.neighbors).get("inputs")
    recorded = inputs.get(files.documents.name) if isinstance(inputs, dict) else None
    if recorded != digest(files.documents):
        raise PackError(
            f"{files.neighbors.name} ist nicht aus den Dokumentvektoren daneben gerechnet (aus "
            "dem Paket oder einem älteren Stand); erst `georep run neighbors`"
        )
    models = _stamp_of(files.chunks).get("models")
    if not isinstance(models, dict) or models.get("open"):
        open_ = models.get("open") if isinstance(models, dict) else "?"
        raise PackError(
            f"die Einbettungen sind unvollständig ({open_} Eingaben offen); erst ein ganzer Lauf "
            "`georep run --models embeddings neighbors`"
        )
    return {key: models.get(key) for key in ("model", "digest", "prompt", "options", "rejected")}


def pack_neighbors(
    layout: Layout,
    settings: Settings,
    target: Path,
    *,
    force: bool = False,
    today: dt.date | None = None,
    level: int = RAW_TEXTS_ZSTD_LEVEL,
) -> PackReport:
    """Nur die ähnlichen Dokumente packen: ``raw/aehnliche_dokumente_paket.parquet`` (Vorhaben 18).

    Auf GitHub Pages rechnet kein Modell; die Nachbarn kommen dorthin nur als Paket, und
    ``[embeddings].neighbors_package`` legt es beim Bootstrap nach ``raw/``. Die Vektoren kommen
    nicht ins Repo (Messdokument § 3.4, Frage 9.1). Geprüft werden die Herkunft
    (``neighbors_identity``) und dass jede ID und jeder Nachbar ein Paper dieser Periode ist; das
    Paket ist derselbe Frame, mit zstd auf Stufe ``level`` neu geschrieben. Das README nennt Modell,
    Digest und Prompt-Version.
    """
    claim_target(layout, target)
    identity = neighbors_identity(layout)
    frame = pl.read_parquet(embedding_files(layout).neighbors)
    if dict(frame.schema) != NEIGHBORS_SCHEMA or not frame.height:
        raise PackError(f"die Nachbartabelle ist leer oder hat andere Spalten: {frame.schema}")
    papers = {
        str(json.loads(line)["id"])
        for line in layout.papers.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    strangers = sorted((set(frame.get_column("id")) | set(frame.get_column("nachbar"))) - papers)
    if strangers:
        raise PackError(
            f"{len(strangers)} IDs der Nachbartabelle sind kein Paper in {layout.papers.name} "
            f"({', '.join(strangers[:EXAMPLES])})"
        )
    destination = target / NEIGHBORS_NAME
    skipped: list[str] = []
    if destination.exists() and not force:
        skipped.append(NEIGHBORS_NAME)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_parquet(
            frame, destination, schema_version=NEIGHBORS_SCHEMA_VERSION, compression_level=level
        )
    ids = frame.get_column("id").n_unique()
    report = PackReport(
        target=target,
        files=(
            PackedFile(
                name=NEIGHBORS_NAME,
                bytes=destination.stat().st_size,
                sha256=sha256_of(destination),
            ),
        ),
        skipped=tuple(skipped),
        figures=(
            ("Zeilen", frame.height),
            ("Korpus-IDs", ids),
            ("Nachbarn je ID", frame.height // ids),
        ),
        readme_written=not (target / README_NAME).exists(),
    )
    if report.readme_written:
        skeleton = readme_skeleton(
            report,
            profile=settings.default_profile,
            city=settings.city.name,
            today=today or dt.date.today(),
            command="pack --neighbors",
        )
        rows = "\n".join(f"| {key} | `{value}` |" for key, value in identity.items())
        write_text(
            target / README_NAME,
            skeleton + f"\n## Modell der Vektoren\n\n| Angabe | Wert |\n|---|---|\n{rows}\n",
        )
    return report


# --- Vorhaben 26: die Tabelle „Paper × Tagesordnungspunkt" für die Beschlusslage ---------------

# Wie beim Rohtextpaket (Review F1, M4): das Paket liegt im Repo, also zstd auf Stufe 19.
OUTCOMES_ZSTD_LEVEL = RAW_TEXTS_ZSTD_LEVEL


def pack_outcomes(
    layout: Layout,
    settings: Settings,
    target: Path,
    *,
    force: bool = False,
    today: dt.date | None = None,
) -> PackReport:
    """Nur die Tabelle „Paper × Tagesordnungspunkt" packen (Vorhaben 26).

    GitHub Pages hat kein Netz und damit keinen Netzlauf von Fundament F6; die Beschlusslage
    braucht aus ihm nur diese Tabelle (Messdokument ``docs/plans/26-beschluesse.md``, § 6 und
    § 10). Gepackt wird aus ``raw/*.jsonl`` dieses Laufs für die Korpus-IDs dieses Laufs, unter dem
    Dateinamen aus ``[outcomes].package`` (sonst ``tagesordnungspunkte-<profil>.parquet``), damit
    Profil und Paket zusammenpassen. Geprüft wird: der Netzlauf ist vollständig (kein offener
    Abruf), jeder Eintrag steht im Wortschatz des Profils, und mindestens ein Punkt trägt einen
    -- sonst wäre das Paket eine Liste von IDs. Namen von Personen trägt die Tabelle keine: nur
    IDs, Schlüssel der Organisationen, Rolle, Beginn, Nummer, Folge und den Eintrag.
    """
    # Im Aufruf importiert wie das Register in ``pipeline``: ``enrich.outcomes`` baut Schritte und
    # zieht die Kette nach; ``georep pack`` ohne diese Option soll sie nicht laden.
    from georep.analysis.outcomes import AGENDA_SCHEMA_VERSION, progress
    from georep.enrich.outcomes import agenda_from_network, network_inputs, unfinished_fetches

    claim_target(layout, target)
    missing = [str(p) for p in (*network_inputs(layout), layout.corpus) if not p.is_file()]
    if missing:
        raise PackError(
            f"{missing} fehlen; lief der Netzlauf (`georep fetch meetings consultations`) und "
            "`georep run` für dieses Profil?"
        )
    unfinished = [str(path) for path in unfinished_fetches(layout)]
    if unfinished:
        raise PackError(f"Abruf unvollständig ({', '.join(unfinished)}); erst zu Ende abrufen")
    papers = pl.read_parquet(layout.corpus, columns=["id"]).get_column("id").to_list()
    frame = agenda_from_network(layout, papers)
    progress(frame, dict(settings.bodies.organizations), dict(settings.outcomes.results))
    entered = int(frame.get_column("result").is_not_null().sum())
    if not entered:
        raise PackError(
            f"{layout.raw}: kein Tagesordnungspunkt der {len(papers)} Dokumente trägt einen "
            "Eintrag; das Paket wäre leer"
        )
    package = settings.outcomes.package
    name = f"raw/{package.name if package else f'tagesordnungspunkte-{settings.profile}.parquet'}"
    destination = target / name
    skipped: list[str] = []
    if destination.exists() and not force:
        skipped.append(name)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_parquet(
            frame,
            destination,
            schema_version=AGENDA_SCHEMA_VERSION,
            compression_level=OUTCOMES_ZSTD_LEVEL,
        )
    report = PackReport(
        target=target,
        files=(
            PackedFile(name=name, bytes=destination.stat().st_size, sha256=sha256_of(destination)),
        ),
        skipped=tuple(skipped),
        figures=(
            ("Dokumente mit Beratung", frame.get_column("id").n_unique()),
            ("Zeilen", frame.height),
            ("Tagesordnungspunkte", int(frame.get_column("top").is_not_null().sum())),
            ("mit Eintrag", entered),
        ),
        readme_written=not (target / README_NAME).exists(),
    )
    return _with_readme(report, settings, today, command="pack --outcomes")
