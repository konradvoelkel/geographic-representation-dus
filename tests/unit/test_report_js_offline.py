"""``offlineNote`` im Rahmen: der Satz über `file://` nur dort, wo er stimmt.

Review vom 2026-10-13, Befund 11: dieselbe Erklärung stand auch hinter einem 404 oder einem halben
JSON über http -- dann schickt sie den Leser auf eine falsche Fährte. Der Satz hängt jetzt an
``location.protocol``, und weil das eine Verzweigung im JavaScript ist, prüft der Test sie mit
``node`` (wie ``test_report_js_fold.py`` die Faltung prüft) und nicht am HTML-Text.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from importlib import resources
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node fehlt")

HARNESS = """
const location = {protocol: process.argv[2]};
SOURCE
console.log(offlineNote("Die Begriffsliste", "data/begriffe.json"));
"""


def _offline_note_source() -> str:
    """Nur ``function offlineNote`` aus dem Rahmen, ohne den Rest des Skripts."""
    frame = (resources.files("georep.report") / "templates" / "report.html.j2").read_text(
        encoding="utf-8"
    )
    start = frame.index("  function offlineNote(")
    end = frame.index("\n  }\n", start) + len("\n  }\n")
    return frame[start:end]


def _note(protocol: str, tmp_path: Path) -> str:
    script = tmp_path / f"note-{protocol.strip(':')}.js"
    script.write_text(HARNESS.replace("SOURCE", _offline_note_source()), encoding="utf-8")
    run = subprocess.run(  # noqa: S603  # node aus PATH, Eingaben aus dem Paket
        ["node", str(script), protocol],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return run.stdout.strip()


def test_the_file_system_gets_the_file_url_explanation(tmp_path: Path) -> None:
    note = _note("file:", tmp_path)
    assert note.startswith("Die Begriffsliste (data/begriffe.json) ließ sich nicht nachladen.")
    assert "Dateisystem" in note and "Webserver" in note


def test_a_web_server_gets_an_explanation_that_can_be_true(tmp_path: Path) -> None:
    note = _note("https:", tmp_path)
    assert note.startswith("Die Begriffsliste (data/begriffe.json) ließ sich nicht nachladen.")
    assert "Dateisystem" not in note  # über http ist das nie der Grund
    assert "fehlt" in note


def test_both_sentences_stand_in_the_frame_once() -> None:
    """Eine Formulierung je Fall, und keine zweite Kopie in einem Abschnitts-Skript."""
    frame = (resources.files("georep.report") / "templates" / "report.html.j2").read_text(
        encoding="utf-8"
    )
    assert frame.count("ließ sich nicht nachladen.") == 1
    assert frame.count('location.protocol === "file:"') == 1
    sections = resources.files("georep.report") / "templates" / "sections"
    sentence = "Aus dem Dateisystem geöffnet erlaubt der Browser"
    for entry in sections.iterdir():
        if entry.name.endswith(".js"):
            # Im Kommentar darf das Dateisystem vorkommen, der Satz für den Leser nicht zweimal.
            assert sentence not in entry.read_text(encoding="utf-8"), entry.name


def test_the_rendered_page_carries_the_branch(mini_page: str) -> None:
    found = re.search(r"function offlineNote\(what, path\) \{(.*?)\n  \}", mini_page, re.S)
    assert found is not None and 'location.protocol === "file:"' in found.group(1)
