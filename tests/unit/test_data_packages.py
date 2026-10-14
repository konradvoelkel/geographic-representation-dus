"""Die Datenpakete im Repo: was drin sein darf, wie groß sie sein dürfen, was ihr README sagt.

Vier Pakete sind die Eingaben, aus denen GitHub Pages jede Seite ohne Netz baut (Punkt 56):
``reference/`` (der Datensatz der Arbeit, Altformat), ``reference/moenchengladbach/`` und
``snapshots/<periode>/`` (das eigene Format: ``raw/papers.jsonl`` und ``cache/text/texts.parquet``)
sowie ``context/`` (Fremddaten, Punkt 26). Geprüft wird hier nicht, was die Kette daraus rechnet --
das tun ``tests/golden/test_second_city.py`` und ``test_period_pipeline.py`` an den Mini-Fixturen --
sondern **dass die Pakete sind, was ihr README behauptet**, und dass nichts hineingerät, was nicht
hineingehört: PDFs (233 MB, 3,9 GB, 585 MB), Stamps, Manifeste, der HTTP-Cache.

Die Obergrenzen sind grob und sollen nicht am Alltag reiben; der scharfe Wächter gegen einen
versehentlich mitcommitteten PDF-Ordner ist ``FORBIDDEN`` und die Dateiliste aus dem README. Die
``slow``-Tests rechnen die SHA-256 jeder Datei nach und zählen die Zeilen der Stores.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import pytest

from georep.pack import RUN_SOURCES, paper_file_names
from tests.conftest import REPO

MIB = 1024 * 1024


@dataclass(frozen=True)
class Package:
    path: str
    limit: int  # Obergrenze in Bytes, grob: rund ein Drittel Luft über dem Stand vom 2026-10-14
    native: bool  # eigenes Format (raw/papers.jsonl plus Textstore) statt Altformat der Arbeit
    readme: bool  # trägt eine Tabelle mit Bytes und SHA-256 je Datei

    @property
    def root(self) -> Path:
        return REPO / self.path


# Die Pakete mit ihrem Stand vom 2026-10-14 im Kommentar; die Grenze ist nicht der Stand.
PACKAGES = (
    # 85 771 896 Bytes, eingefroren seit v0.2.0 und ohne README-Tabelle (Golden Master der Arbeit)
    Package("reference", limit=120 * MIB, native=False, readme=False),
    Package("reference/moenchengladbach", limit=8 * MIB, native=True, readme=True),  # 3 980 958
    Package("snapshots/2014-2020", limit=48 * MIB, native=True, readme=True),  # 37 875 851
    Package("snapshots/2025", limit=20 * MIB, native=True, readme=True),  # 13 894 254
    Package("context", limit=4 * MIB, native=False, readme=True),  # 2 245 401
)
# Alle zusammen, als zweite grobe Schranke: 137,1 MiB am 2026-10-14. Ein einziger PDF-Ordner einer
# Periode (585 MB bis 3,9 GB) reißt sie um ein Mehrfaches, und genau davor schützt sie.
TOTAL_LIMIT = 180 * MIB

# Was in keinem Paket liegen darf, mit dem Grund. Endungen werden gegen das Suffix geprüft, Namen
# gegen den Dateinamen, Teile gegen den Pfad unter der Paketwurzel.
FORBIDDEN_SUFFIXES = {
    ".pdf": "die PDFs sind urheberrechtlich ungeklärt und zu groß; nur ihre Texte kommen ins Paket",
    ".sqlite": "der HTTP-Cache gehört in cache_root, nicht ins Repo",
    ".prof": "cProfile-Ausgaben sind rechnerspezifisch",
}
FORBIDDEN_NAMES = {
    "manifest.jsonl": "das PDF-Manifest beschreibt einen Cache, keine Eingabe",
    "papers.progress.json": "der Netz-Cursor eines Abrufs gehört nicht in ein eingefrorenes Paket",
    "http.sqlite": "der HTTP-Cache gehört in cache_root",
}
STAMP = ".stamp.json"  # beschreibt einen Lauf, nicht seine Eingaben
# Zeile der README-Tabelle: erste Zelle der Pfad in Backticks, letzte die SHA-256, davor die Bytes.
# context/README.md hat eine Spalte mehr (die Datei im Portal), darum die Mitte als beliebig.
ROW = re.compile(r"^\|\s*`(?P<name>[^`]+)`\s*\|(?P<middle>.*)\|\s*`(?P<sha>[0-9a-f]{64})`\s*\|\s*$")
BYTES_IN_MIDDLE = re.compile(r"([\d  ]+)\s*\|\s*$")


def files_of(package: Package) -> list[Path]:
    """Alle Dateien des Pakets, ohne sein README und ohne die Dateien eines Pakets darin."""
    inner = [
        p.root for p in PACKAGES if p.path != package.path and p.root.is_relative_to(package.root)
    ]
    return sorted(
        path
        for path in package.root.rglob("*")
        if path.is_file()
        and path.name != "README.md"
        and not any(path.is_relative_to(other) for other in inner)
    )


def readme_rows(package: Package) -> dict[str, tuple[int, str]]:
    """Die Tabelle „Datei, Bytes, SHA-256" des READMEs als Abbildung Pfad -> (Bytes, SHA-256)."""
    rows: dict[str, tuple[int, str]] = {}
    for line in (package.root / "README.md").read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match is None:
            continue
        size = BYTES_IN_MIDDLE.search(match["middle"] + "|")
        assert size is not None, line
        rows[match["name"]] = (int(size[1].replace(" ", "").replace(" ", "")), match["sha"])
    return rows


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.path)
def test_every_package_exists_and_is_not_empty(package: Package) -> None:
    assert package.root.is_dir(), (
        f"{package.path} fehlt; ohne das Paket baut Pages diese Seite nicht"
    )
    assert files_of(package)


@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.path)
def test_no_package_carries_pdfs_stamps_or_caches(package: Package) -> None:
    """Der scharfe Wächter: ein ``cp -r`` zu viel bringt sonst Hunderte MB PDFs in die Historie."""
    for path in files_of(package):
        relative = path.relative_to(package.root)
        assert path.suffix not in FORBIDDEN_SUFFIXES, (
            f"{relative}: {FORBIDDEN_SUFFIXES[path.suffix]}"
        )
        assert path.name not in FORBIDDEN_NAMES, f"{relative}: {FORBIDDEN_NAMES[path.name]}"
        assert not path.name.endswith(STAMP), f"{relative}: ein Stamp beschreibt einen Lauf"


@pytest.mark.parametrize("package", PACKAGES, ids=lambda p: p.path)
def test_every_package_stays_under_its_limit(package: Package) -> None:
    total = sum(path.stat().st_size for path in files_of(package))
    assert total <= package.limit, f"{package.path}: {total} Bytes über {package.limit}"


def test_all_packages_together_stay_under_the_total_limit() -> None:
    total = sum(path.stat().st_size for package in PACKAGES for path in files_of(package))
    assert total <= TOTAL_LIMIT, f"{total} Bytes über {TOTAL_LIMIT}"


@pytest.mark.parametrize("package", [p for p in PACKAGES if p.readme], ids=lambda p: p.path)
def test_the_readme_lists_every_file_with_its_size(package: Package) -> None:
    """Das README ist die Beschreibung des Pakets; was es nicht nennt, gehört nicht dazu."""
    rows = readme_rows(package)
    on_disk = {
        str(path.relative_to(package.root)): path.stat().st_size for path in files_of(package)
    }
    assert set(rows) == set(on_disk), f"{package.path}: README und Dateien weichen ab"
    assert {name: size for name, (size, _) in rows.items()} == on_disk


@pytest.mark.parametrize("package", [p for p in PACKAGES if p.native], ids=lambda p: p.path)
def test_a_native_package_has_the_shape_bootstrap_reads(package: Package) -> None:
    """``seed_stores_from_native`` liest genau diese zwei Pfade; ``external/`` sind die Eingaben.

    Der Textstore liegt unter ``cache/text/``, weil ``Layout.reference_view`` ``cache_root`` auf
    ``<reference_root>/cache`` setzt -- derselbe Pfad wie in ``tests/fixtures/mg/``.
    """
    assert (package.root / "raw" / "papers.jsonl").is_file()
    assert (package.root / "cache" / "text" / "texts.parquet").is_file()
    assert any(path.is_file() for path in (package.root / "external").iterdir())


def test_the_profiles_point_at_the_packages_in_the_repo() -> None:
    """Jedes Paketprofil mit eigener Referenz findet sie; sonst meldet ``bootstrap`` nur Fehlendes."""
    from georep.settings import load_settings

    nowhere = Path("/nonexistent")
    expected = {
        "moenchengladbach": "reference/moenchengladbach",
        "duesseldorf-2014": "snapshots/2014-2020",
        "duesseldorf-2025": "snapshots/2025",
        "duesseldorf": "reference",
    }
    for profile, path in expected.items():
        settings = load_settings(profile=profile, cwd=nowhere)
        assert (REPO / settings.reference_root).resolve() == (REPO / path).resolve(), profile
        assert (REPO / settings.reference_root).is_dir(), profile


# --- slow: Prüfsummen und Zeilenzahlen der echten Pakete ---------------------------------------

# Die Zahlen der Läufe vom 2026-10-13, wie sie in den READMEs stehen: Paper, Texte, Texte mit
# Inhalt. Hier als Konstanten und nicht aus dem README geparst -- die Tabelle der Prüfsummen ist
# maschinenlesbar, die Zahlen des Laufs sind Prosa.
ROW_COUNTS = {
    "reference/moenchengladbach": (2895, 658, 650),
    "snapshots/2014-2020": (22215, 22116, 21838),
    "snapshots/2025": (4095, 4088, 4075),
}


@pytest.mark.slow
@pytest.mark.parametrize("package", [p for p in PACKAGES if p.readme], ids=lambda p: p.path)
def test_the_checksums_in_the_readme_match_the_files(package: Package) -> None:
    rows = readme_rows(package)
    for name, (_, expected) in sorted(rows.items()):
        assert sha256_of(package.root / name) == expected, f"{package.path}/{name}"


@pytest.mark.slow
@pytest.mark.parametrize("path", sorted(ROW_COUNTS), ids=lambda p: p)
def test_the_stores_of_a_package_have_the_rows_its_readme_claims(path: str) -> None:
    root = REPO / path
    papers, texts, with_text = ROW_COUNTS[path]
    lines = (root / "raw" / "papers.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == papers
    assert all(json.loads(line)["id"] for line in lines[:5])
    store = pl.read_parquet(root / "cache" / "text" / "texts.parquet")
    assert store.height == texts
    assert int((store.get_column("chars") > 0).sum()) == with_text
    # Ein Paket trägt nur, was abgerufen wurde: keine Zeile aus einer Fixture oder Stichprobe.
    # Erlaubt wäre auch "reference" (ein aus dem Datensatz gebootstrappter Lauf, pack.RUN_SOURCES);
    # diese drei kommen aus echten Abrufen, und das ist die scharfere Aussage.
    assert set(store.get_column("source")) == {"pdf"} <= RUN_SOURCES
    # Review-Befund 7: jeder Text gehört zu einem Paper des Pakets. Ein verwaister Text fiele im
    # Schritt ``corpus`` heraus und wäre Ballast, der niemandem auffällt -- genau wie die 100
    # synthetischen Zeilen, die am 2026-10-13 im Store des Laufs lagen.
    names = set(store.get_column("name"))
    known = paper_file_names(root / "raw" / "papers.jsonl")
    assert names <= known, sorted(names - known)[:5]
    # Umgekehrt gilt keine Gleichheit: ein Paper ohne Hauptdatei trägt keinen Namen, und eines,
    # dessen PDF der Server nicht ausliefert (Mönchengladbach: 2 213), hat keinen Text.
    assert texts <= len(known) <= papers
