"""Die Datenpakete im Repo: was drin sein darf, wie groß sie sein dürfen, was ihr README sagt.

Sechs Pakete sind die Eingaben, aus denen GitHub Pages jede Seite ohne Netz baut (Punkt 56):
``reference/`` (der Datensatz der Arbeit, Altformat), ``reference/moenchengladbach/`` und
``snapshots/<periode>/`` (das eigene Format: ``raw/papers.jsonl`` und ``cache/text/texts.parquet``),
``snapshots/duesseldorf-beratungsfolge/`` (nur die Beratungsfolge je Dokument, Punkt 58) sowie
``context/`` (Fremddaten, Punkt 26). **Gezählt werden die Datendateien ohne das README**:
es beschreibt das Paket und ist nicht sein Inhalt, darum lässt ``files_of`` es aus und darum nennt
jede Zahl in den Dokumenten dieselbe Menge (Review-Befund 14). Geprüft wird hier nicht, was die
Kette daraus rechnet --
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
    limit: int  # Obergrenze in Bytes, grob: ein Drittel bis das Mehrfache Luft über dem Stand
    native: bool  # eigenes Format (raw/papers.jsonl plus Textstore) statt Altformat der Arbeit
    readme: bool  # trägt eine Tabelle mit Bytes und SHA-256 je Datei

    @property
    def root(self) -> Path:
        return REPO / self.path


# Die Pakete mit ihrem Stand vom 2026-11-16 im Kommentar; die Grenze ist nicht der Stand.
PACKAGES = (
    # 85 771 896 Bytes, eingefroren seit v0.2.0 und ohne README-Tabelle (Golden Master der Arbeit)
    Package("reference", limit=120 * MIB, native=False, readme=False),
    Package("reference/moenchengladbach", limit=8 * MIB, native=True, readme=True),  # 5 213 942
    Package("snapshots/2014-2020", limit=48 * MIB, native=True, readme=True),  # 37 625 770
    Package("snapshots/2025", limit=20 * MIB, native=True, readme=True),  # 13 889 015
    # Punkt 58: nur die Beratungsfolge je Dokument, kein Store und keine Eingabe (90 455 Bytes)
    Package("snapshots/duesseldorf-beratungsfolge", limit=1 * MIB, native=False, readme=True),
    # Punkt 68: nur der Textstore der Hauptperiode aus pypdf 7.1.0 (15 563 293 Bytes)
    Package("snapshots/duesseldorf-texte", limit=20 * MIB, native=False, readme=True),
    # Fundament F1: nur der Rohtextstore der Hauptperiode aus pypdf 7.1.0, Schema-Version 2, zstd
    # auf Stufe 19 (14 183 802 Bytes; mit der Vorgabe von Polars waren es 17 044 579)
    Package("snapshots/duesseldorf-rohtexte", limit=20 * MIB, native=False, readme=True),
    Package("context", limit=4 * MIB, native=False, readme=True),  # 2 242 316
    # Vorhaben 14: die Anlagen je Drucksache aller drei Perioden, aus dem HTTP-Cache, Personennamen maskiert (303 400)
    Package("snapshots/duesseldorf-anlagen", limit=1 * MIB, native=False, readme=True),
    # Vorhaben 14: dasselbe für die zweite Stadt, neben reference/moenchengladbach/ (63 910)
    Package("snapshots/moenchengladbach-anlagen", limit=1 * MIB, native=False, readme=True),
    # Vorhaben 26: die Tabelle Paper x Tagesordnungspunkt der drei Perioden, je eine Datei (631 944)
    Package("snapshots/duesseldorf-beschluesse", limit=2 * MIB, native=False, readme=True),
)
# Alle zusammen, als zweite grobe Schranke: 174 580 489 Bytes = 166,49 MiB am 2026-11-23 (92,5 %
# der Grenze; Mönchengladbach wuchs mit Punkt 65 um 819 292 Bytes, die drei Textstores sind seit
# Punkt 67 zusammen 266 295 Bytes kleiner, das Textpaket der Hauptperiode kam mit Punkt 68 dazu und
# das Rohtextpaket mit Fundament F1); mit den beiden Anlagenpaketen von Vorhaben 14 174 947 799
# Bytes = 166,84 MiB (92,7 %, 2026-11-24). Ein einziger PDF-Ordner einer Periode (585 MB bis
# 3,9 GB) reißt sie um ein Mehrfaches, und genau davor schützt sie. Mit dem Beschlusspaket von
# Vorhaben 26 175 579 743 Bytes = 167,45 MiB (93,0 %, 2026-11-24).
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


def test_every_folder_under_snapshots_is_a_known_package() -> None:
    """Review F1, M4: ein Ordner unter ``snapshots/`` ohne Eintrag hier entginge jeder Prüfung.

    Die Grenzen, das README und die Liste verbotener Dateien gelten nur für ``PACKAGES``; ein neues
    Paket, das dort fehlt, wüchse unbemerkt (und zählte auch nicht in ``TOTAL_LIMIT``).
    """
    known = {p.path for p in PACKAGES}
    folders = {f"snapshots/{d.name}" for d in (REPO / "snapshots").iterdir() if d.is_dir()}
    assert folders <= known, sorted(folders - known)


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


def test_gitattributes_keeps_the_package_bytes_untouched() -> None:
    """Review-Befund 15: ohne ``-text`` entscheidet eine Heuristik, ob ein Checkout LF umschreibt.

    Dann wäre jede Prüfsumme einer CSV oder eines GeoJSON im README falsch, und zwar nur auf dem
    Rechner, der es anders auscheckt. Geprüft wird die Zeile, nicht die Wirkung: ``git`` hier zu
    rufen wäre ein Test über git, und die Wirkung sieht man mit ``git check-attr -a``.
    """
    lines = (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines()
    rules = [line.split() for line in lines if line.strip() and not line.startswith("#")]
    for package in PACKAGES:
        top = package.path.split("/")[0]
        assert [f"{top}/**", "-text"] in rules, f"{top} fehlt in .gitattributes"
    # Die READMEs bleiben gewöhnlicher Text; die Zeile muss nach der Paketzeile stehen
    readmes = [index for index, rule in enumerate(rules) if rule[0].endswith("README.md")]
    assert readmes and min(readmes) > max(
        index for index, rule in enumerate(rules) if rule[-1] == "-text"
    )


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


def test_the_package_with_the_consultation_is_declared_by_exactly_one_profile() -> None:
    """Punkt 58: die Hauptperiode liest es, jede Periode mit eigener Folge nimmt es zurück.

    Ohne den leeren Schlüssel in den Periodenprofilen kopierte ``bootstrap`` dort die Folge der
    Hauptperiode in ein ``raw/``, in dem sie nichts zu tun hat (die IDs sind disjunkt).
    """
    from georep.settings import load_settings

    nowhere = Path("/nonexistent")
    main = load_settings(profile="duesseldorf", cwd=nowhere).bodies
    assert main.consultations is not None
    assert (REPO / main.consultations).is_file(), main.consultations
    assert main.consultations.parts[:2] == ("snapshots", "duesseldorf-beratungsfolge")
    for profile in ("duesseldorf-2014", "duesseldorf-2025", "moenchengladbach"):
        assert load_settings(profile=profile, cwd=nowhere).bodies.consultations is None, profile
    # Der Vergleich *ist* die Hauptperiode und liest dieselbe Datei (Punkt 52)
    assert load_settings(profile="duesseldorf-vergleich", cwd=nowhere).bodies.consultations == (
        main.consultations
    )


def test_the_raw_text_package_is_read_by_the_main_period_alone() -> None:
    """Fundament F1: dieselbe Regel wie für das Textpaket, für den Rohtextstore der Hauptperiode."""
    from georep.settings import load_settings

    nowhere = Path("/nonexistent")
    main = load_settings(profile="duesseldorf", cwd=nowhere).bootstrap.raw_texts
    assert main is not None and (REPO / main).is_file(), main
    assert main.parts[:2] == ("snapshots", "duesseldorf-rohtexte")
    assert load_settings(profile="duesseldorf-vergleich", cwd=nowhere).bootstrap.raw_texts == main
    for profile in ("duesseldorf-2014", "duesseldorf-2025", "moenchengladbach"):
        assert load_settings(profile=profile, cwd=nowhere).bootstrap.raw_texts is None, profile


def test_the_text_package_is_read_by_the_main_period_alone() -> None:
    """Punkt 68: dieselbe Regel wie für die Beratungsfolge, für den Textstore der Hauptperiode.

    ``bootstrap`` übernähme das Paket in einer anderen Periode ohnehin nicht (die Dateien sind
    andere), aber ein geerbter Pfad, der nie gilt, ist eine Angabe, die niemand prüft.
    """
    from georep.settings import load_settings

    nowhere = Path("/nonexistent")
    main = load_settings(profile="duesseldorf", cwd=nowhere).bootstrap.texts
    assert main is not None and (REPO / main).is_file(), main
    assert main.parts[:2] == ("snapshots", "duesseldorf-texte")
    assert load_settings(profile="duesseldorf-vergleich", cwd=nowhere).bootstrap.texts == main
    for profile in ("duesseldorf-2014", "duesseldorf-2025", "moenchengladbach"):
        assert load_settings(profile=profile, cwd=nowhere).bootstrap.texts is None, profile


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


@pytest.mark.slow
def test_the_text_package_carries_exactly_the_files_of_the_thesis_corpus() -> None:
    """Punkt 68: 19 092 Texte für die 19 092 Hauptdateien der 19 108 Paper der Arbeit.

    Nur unter dieser Bedingung übernimmt ``bootstrap`` das Paket (``overlay_texts``); ein Text zu
    viel oder zu wenig, und die Hauptseite rechnete still mit den Texten der Arbeit weiter. 59
    PDFs haben keine Textschicht (dieselben 75 Dokumente ohne Text wie in der Arbeit, mit den 16
    ohne Hauptdatei), und eines weist pypdf 7.1.0 ab: es behält den Text der Arbeit.
    """
    from georep.records import PaperRecord
    from georep.stores import REFERENCE_EXTRACTOR

    items = json.loads(
        (REPO / "reference" / "interim" / "paper_with_text.json").read_text(encoding="utf-8")
    )
    files = {r.file_name for r in map(PaperRecord.from_legacy, items) if r.file_name}
    assert (len(items), len(files)) == (19108, 19092)
    store = pl.read_parquet(REPO / "snapshots" / "duesseldorf-texte" / "cache/text/texts.parquet")
    assert set(store.get_column("name")) == files
    assert int((store.get_column("chars") > 0).sum()) == 19033
    kinds = store.group_by("source", "extractor").len().sort("source").rows()
    assert kinds == [("pdf", "pypdf-7.1.0", 19091), ("reference", REFERENCE_EXTRACTOR, 1)]


@pytest.mark.slow
def test_the_raw_text_package_flattens_to_the_text_package() -> None:
    """Fundament F1, die Abnahme über die ganze Hauptperiode: Rohtext geplättet = Text, ohne Ausnahme.

    Beide Pakete kommen aus denselben 19 092 PDFs (gleicher PDF-Hash je Name, Extraktor mit
    ``+roh``). Für jeden Rohtext ist ``flatten`` genau der Text des Textpakets -- auch für
    ``00532917.pdf``, das in einer Seite 41 ``\\f`` aus einer defekten Schriftkodierung trägt: der
    Rohtext führt sie als Leerzeichen und ihre Offsets in ``form_feeds`` (Review F1, M3). Ohne
    Rohtext ist allein der Text, den das Textpaket aus der Arbeit übernommen hat (``00403713.pdf``,
    AES-verschlüsselt, Punkt 68).
    """
    from georep.prep.raw_texts import PAGE_BREAK, flatten
    from georep.stores import RAW_TEXT_SCHEMA_VERSION, REFERENCE_EXTRACTOR, stored_schema_version

    texts = pl.read_parquet(REPO / "snapshots" / "duesseldorf-texte" / "cache/text/texts.parquet")
    path = REPO / "snapshots" / "duesseldorf-rohtexte" / "cache/text/rohtexte.parquet"
    assert stored_schema_version(path) == str(RAW_TEXT_SCHEMA_VERSION)
    raw = pl.read_parquet(path)
    assert set(raw.get_column("extractor")) == {"pypdf-7.1.0+roh"}
    by_name = {
        row[0]: row for row in texts.select("name", "text", "pdf_sha256", "extractor").rows()
    }
    assert (
        set(by_name) - set(raw.get_column("name"))
        == {name for name, row in by_name.items() if row[3] == REFERENCE_EXTRACTOR}
        == {"00403713.pdf"}
    )
    deviations = []
    for name, text, sha, feeds in raw.select("name", "text", "pdf_sha256", "form_feeds").rows():
        assert by_name[name][2] == sha, name
        if flatten(text, "betrifft", feeds or ()) != by_name[name][1]:
            deviations.append(name)
    assert deviations == []
    with_feeds = raw.filter(pl.col("form_feeds").is_not_null())
    assert with_feeds.get_column("name").to_list() == ["00532917.pdf"]
    assert with_feeds.get_column("form_feeds").list.len().to_list() == [41]
    assert by_name["00532917.pdf"][1].count(PAGE_BREAK) == 41


@pytest.mark.slow
def test_the_raw_text_package_places_every_character_of_the_text_package() -> None:
    """Nachzug F1 (Synergien 2026-11, Konflikt 1): ``flatten_with_offsets`` über die Hauptperiode.

    Für jeden Rohtext ist der Text genau der des Textpakets, ohne Abweichung wie bei ``flatten``,
    und jedes Zeichen hat seine Stelle im Rohtext: aufsteigend, und das Rohtextzeichen dort ergibt
    kleingeschrieben das Zeichen. Die 41 ``\\f`` aus dem Seitentext von ``00532917.pdf`` zeigen
    auf genau die gespeicherten Offsets (``form_feeds``).
    """
    from georep.prep.raw_texts import PAGE_BREAK, flatten_with_offsets, restore_form_feeds
    from tests.property.test_raw_text_props import each_character_is_its_source_lowercased

    texts = pl.read_parquet(REPO / "snapshots" / "duesseldorf-texte" / "cache/text/texts.parquet")
    by_name = dict(texts.select("name", "text").rows())
    raw = pl.read_parquet(
        REPO / "snapshots" / "duesseldorf-rohtexte" / "cache/text/rohtexte.parquet"
    )
    deviations, inner = [], {}
    for name, text, stored in raw.select("name", "text", "form_feeds").rows():
        feeds = tuple(stored or ())
        flat, offsets = flatten_with_offsets(text, "betrifft", feeds)
        if (
            flat != by_name[name]
            or list(offsets) != sorted(offsets)
            or not each_character_is_its_source_lowercased(
                flat, offsets, restore_form_feeds(text, feeds)
            )
        ):
            deviations.append(name)
        if feeds:
            inner[name] = (feeds, [offsets[i] for i, c in enumerate(flat) if c == PAGE_BREAK])
    assert raw.height == 19091
    assert deviations == []
    assert list(inner) == ["00532917.pdf"]
    feeds, mapped = inner["00532917.pdf"]
    assert len(feeds) == 41 and mapped == list(feeds)


# --- M1: die Flächen im Paket sind die der Stadt -----------------------------------------------


@pytest.mark.slow
def test_the_packed_areas_are_the_whole_second_city() -> None:
    """Die Stadt im Paket ist vollständig: 179 Stimmbezirke, 170,47 km², 25 187 Stützpunkte.

    Bis zum Review vom 2026-10-15 hielt **kein** Test diese Zahlen am echten Paket fest. Nur der
    Fetcher prüfte auf eine abgeschnittene Dienstantwort, und GitHub Pages ruft ihn nie auf: es
    liest diese Datei. Eine hier gekürzte Antwort hätte eine kleinere Stadt mit Exit 0 ergeben --
    die Flächensumme ist die Zahl, an der das auffällt (`docs/decisions.md`, Punkt 65).
    """
    from shapely.geometry import shape

    from georep.prep.precincts import read_source_esri_identify

    datei = (
        REPO / "reference" / "moenchengladbach" / "external" / "Stimmbezirke_Kommunalwahl_2025.json"
    )
    quelle = read_source_esri_identify(datei, id_property="Nummer")
    assert len(quelle.features) == 179 and quelle.crs == "EPSG:25832"
    nummern = {str(f["properties"]["Nummer"]) for f in quelle.features}
    assert len(nummern) == 179
    assert {"11006", "21406", "32906", "40106"} <= nummern  # 2022 fehlten sie
    assert not {"10506", "11204", "21505", "32405", "32805"} & nummern  # 2022 gab es sie noch

    flaeche = sum(shape(f["geometry"]).area for f in quelle.features)
    assert flaeche == pytest.approx(170_469_644.10, abs=0.1)  # m², die Stadtfläche
    punkte = sum(
        len(ring)
        for entry in json.loads(datei.read_text(encoding="utf-8"))["results"]
        for ring in entry["geometry"]["rings"]
    )
    assert punkte == 25_187  # maxAllowableOffset=0; mit =1 wären es 17 326


# --- Vorhaben 14: die Anlagenpakete -----------------------------------------------------------


def test_each_city_reads_its_own_attachment_package() -> None:
    """Die drei Düsseldorfer Perioden teilen ein Paket, Mönchengladbach hat seins neben
    ``reference/moenchengladbach/`` (Synergie 2026-11, Konflikt 11: nichts nach ``reference/``)."""
    from georep.settings import load_settings

    nowhere = Path("/nonexistent")
    expected = {
        "duesseldorf": "snapshots/duesseldorf-anlagen",
        "duesseldorf-2014": "snapshots/duesseldorf-anlagen",
        "duesseldorf-2025": "snapshots/duesseldorf-anlagen",
        "moenchengladbach": "snapshots/moenchengladbach-anlagen",
    }
    for profile, package in expected.items():
        found = load_settings(profile=profile, cwd=nowhere).procedures.attachments
        assert found is not None and found.parent.parent == Path(package), profile
        assert (REPO / found).is_file(), profile


def test_each_period_reads_its_own_table_of_the_outcomes_package() -> None:
    """Vorhaben 26: jede Düsseldorfer Periode nennt ihre Datei, und sie liegt im Repo."""
    from georep.settings import load_settings

    nowhere = Path("/nonexistent")
    found = {}
    for profile in ("duesseldorf", "duesseldorf-2014", "duesseldorf-2025", "duesseldorf-vergleich"):
        package = load_settings(profile=profile, cwd=nowhere).outcomes.package
        assert package is not None and (REPO / package).is_file(), (profile, package)
        assert package.parts[:2] == ("snapshots", "duesseldorf-beschluesse"), profile
        found[profile] = package.name
    assert len(set(found.values())) == 3  # der Vergleich ist die Hauptperiode (Punkt 52)
    assert found["duesseldorf-vergleich"] == found["duesseldorf"]
    assert load_settings(profile="moenchengladbach", cwd=nowhere).outcomes.package is None
