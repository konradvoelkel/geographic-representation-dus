"""Die Faltung der Suche in JavaScript gegen den Python-Spiegel, über alle Begriffe der Fixture.

Die Regel ``straße``/``str.`` steht einmal (``STREET_ABBREVIATIONS``) und wandert über den Payload
ins Abschnitts-Skript; der Abgleich der Seite steht und fällt damit, dass ``fold`` dort dasselbe
rechnet wie hier. Ohne ``node`` läuft der Test nicht (``skip``); er ist auf Konrads Rechner (v22)
und auf ``ubuntu-latest`` vorhanden.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from importlib import resources
from pathlib import Path

import polars as pl
import pytest

from georep.layout import Layout
from georep.report.search import fold, fold_ascii
from georep.search.dictionary import STREET_ABBREVIATIONS

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node fehlt")

# Der Abschnitt läuft als IIFE und hängt an #suche-daten; für den Test werden die beiden
# Faltungen herausgeschnitten und mit demselben Payload wie auf der Seite aufgerufen.
HARNESS = """
const data = {"abbreviations": ABBREVIATIONS};
const abbreviations = data.abbreviations;
SOURCE
const terms = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
console.log(JSON.stringify(terms.map((t) => [foldWith(t, false), foldWith(t, true)])));
"""


def _folding_source() -> str:
    """``plain``, ``quoted`` und ``foldWith`` aus ``sections/15-suche.js``, ohne den Rest."""
    script = (
        resources.files("georep.report") / "templates" / "sections" / "15-suche.js"
    ).read_text(encoding="utf-8")
    start = script.index("  function plain(")
    end = script.index("  function fold(text)")
    return script[start:end]


def _folded_in_node(terms: list[str], tmp_path: Path) -> list[list[str]]:
    source = HARNESS.replace("SOURCE", _folding_source()).replace(
        "ABBREVIATIONS", json.dumps([list(p) for p in STREET_ABBREVIATIONS], ensure_ascii=False)
    )
    script = tmp_path / "fold.js"
    script.write_text(source, encoding="utf-8")
    data = tmp_path / "terms.json"
    data.write_text(json.dumps(terms, ensure_ascii=False), encoding="utf-8")
    run = subprocess.run(  # noqa: S603  # node aus PATH, Eingaben aus der Fixture
        ["node", str(script), str(data)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    result: list[list[str]] = json.loads(run.stdout)
    return result


EXAMPLES = [
    "Münchener Str.",
    "münchener str",
    "südstr",
    "SÜDSTRASSE",
    "  auf'm   hennekamp ",
    "café ōsaka",
    "straße",
    "strandbad",
    "Königsallee",
    "Rather Broich / Rather Kreuzweg",
    'x"&<b>',
    "",
]


def test_node_and_python_fold_the_examples_alike(tmp_path: Path) -> None:
    got = _folded_in_node(EXAMPLES, tmp_path)
    assert got == [[fold(t), fold_ascii(t)] for t in EXAMPLES]


def test_node_and_python_fold_every_term_of_the_fixture_alike(
    mini_run: Layout, tmp_path: Path
) -> None:
    dictionary = pl.read_parquet(mini_run.dictionary)
    terms = sorted(set(dictionary.get_column("suchbegriffe").explode().to_list()))
    assert len(terms) > 500
    assert _folded_in_node(terms, tmp_path) == [[fold(t), fold_ascii(t)] for t in terms]
