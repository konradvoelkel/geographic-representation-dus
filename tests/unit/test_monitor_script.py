"""Das Lauf-Skript (Option 07) gegen einen Stub: Reihenfolge, Sperre, Fehler, Trockenlauf.

Kein Netz, kein systemd, kein georep: ``uv`` ist ein Stub am Anfang von ``PATH``, der jeden
Aufruf protokolliert und die Dateien anlegt, die das Skript erwartet. Geprüft wird, was das
Skript selbst verantwortet: die Reihenfolge der Schritte, die Sperre, der Abbruch bei einem
Fehler, der Veröffentlichungsordner mit Schnappschuss und ``stand.json``, und dass ohne Ziel
weder rclone noch rsync nach außen laufen.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REPO

SCRIPT = REPO / "deploy" / "bin" / "georep-monitor.sh"

# Der Stub ahmt die Zeilen nach, die das Skript auswertet (Zahlen vor „neu", „geladen",
# „extrahiert") und legt die Seiten an, die es danach einsammelt.
UV_STUB = """#!/usr/bin/env bash
echo "uv $*" >> "$STUB_LOG"
if [ -n "${STUB_FAIL:-}" ] && [[ "$*" == *"$STUB_FAIL"* ]]; then
  echo "Abruf gescheitert" >&2
  exit 1
fi
if [ "${1:-}" = "sync" ]; then
  echo "Resolved 1 package"
  exit 0
fi
shift 2   # "run georep"
case "$*" in
  *"--settings "*bootstrap*) echo "4 Dateien kopiert, 0 übersprungen; Stores nicht gefüllt" ;;
  *bootstrap*) echo "4 Dateien kopiert; 200 Paper und 200 Texte aus der Referenz" ;;
  *papers*) echo "papers       ausgeführt    seit 2026-10-01; Store 3 neu, 1 aktualisiert" ;;
  *pdfs*) echo "pdfs 2 geladen, 0 übersprungen; texts 2 extrahiert, 1 aktuell" ;;
  *)
    if [ -n "${STUB_PROFILE_SITE:-}" ]; then
      mkdir -p "$STUB_PROFILE_SITE/data"
      echo "<html>Profil</html>" > "$STUB_PROFILE_SITE/index.html"
      echo "spalte" > "$STUB_PROFILE_SITE/data/monatsreihe.csv"
    fi
    mkdir -p "$STUB_MAIN_SITE/data"
    echo "<html>Haupt ${GEOREP_REPORT__MONITORING_URL:-}</html>" > "$STUB_MAIN_SITE/index.html"
    echo "14 ausgeführt, 1 übersprungen"
    ;;
esac
exit 0
"""

RCLONE_STUB = """#!/usr/bin/env bash
echo "rclone $*" >> "$STUB_LOG"
echo "Transferred: 3 / 3, 100%"
"""


@pytest.fixture
def sandbox(tmp_path: Path) -> dict[str, str]:
    """Eine Umgebung für das Skript: Stubs in PATH, Datenwurzel und Ziel in ``tmp_path``."""
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for name, body in (("uv", UV_STUB), ("rclone", RCLONE_STUB)):
        path = binaries / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    data = tmp_path / "data"
    env = dict(os.environ)
    env.update(
        PATH=f"{binaries}:{env['PATH']}",
        MONITOR_REPO=str(tmp_path),
        MONITOR_SETTINGS="settings.2025.toml",
        MONITOR_PROFILE="2025",
        MONITOR_PUBLISH_DIR=str(tmp_path / "publish"),
        MONITOR_R2_REMOTE="",
        MONITOR_VPS_HOST="",
        MONITOR_HEALTHCHECK_URL="",
        GEOREP_DATA_ROOT=str(data),
        GEOREP_CACHE_ROOT=str(tmp_path / "cache"),
        DRY_RUN="1",
        STUB_LOG=str(tmp_path / "calls.log"),
        STUB_MAIN_SITE=str(data / "site"),
        STUB_PROFILE_SITE=str(data / "2025" / "site"),
    )
    env.pop("STUB_FAIL", None)
    return env


def _run(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=120
    )


def test_bash_accepts_the_script() -> None:
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0


def test_a_dry_run_walks_the_steps_in_order_and_writes_the_stand(sandbox: dict[str, str]) -> None:
    result = _run(sandbox)
    assert result.returncode == 0, result.stdout + result.stderr
    calls = Path(sandbox["STUB_LOG"]).read_text(encoding="utf-8").splitlines()
    assert calls[0] == "uv sync --locked"
    assert calls[1] == "uv run georep --settings settings.2025.toml bootstrap"
    assert calls[2] == "uv run georep --settings settings.2025.toml run --dry-run --online papers"
    assert (
        calls[3] == "uv run georep --settings settings.2025.toml run --dry-run --online pdfs texts"
    )
    assert calls[4] == "uv run georep --settings settings.2025.toml run --dry-run"
    assert calls[5] == "uv run georep bootstrap" and calls[6] == "uv run georep run"
    assert len(calls) == 7  # kein rclone, kein weiterer Aufruf

    out = Path(sandbox["MONITOR_PUBLISH_DIR"]) / "out"
    assert (out / "index.html").read_text(encoding="utf-8").strip() == "<html>Haupt 2025/</html>"
    assert (out / "2025" / "index.html").is_file()
    stand = json.loads((out / "2025" / "stand.json").read_text(encoding="utf-8"))
    assert stand["profil"] == "2025" and stand["ergebnis"] == "trocken"
    assert (stand["neue_paper"], stand["pdfs"], stand["texte"]) == (3, 2, 2)
    assert re.fullmatch(r"\d{4}-\d{2}", stand["schnappschuss"])  # der Monat dieses Laufs
    assert stand["seite_kb"] >= 0 and stand["dauer_s"] >= 0
    assert len(stand["schritte"]) == 7 and all(stand["schritte"])
    assert "ohne MONITOR_R2_REMOTE" in result.stdout and "ohne MONITOR_VPS_HOST" in result.stdout
    assert "georep-monitor: 3 neue Paper, 2 PDFs, 2 Texte" in result.stdout

    # Der Schnappschuss des Monats liegt neben der Seite, mit Prüfsummen
    snapshots = sorted((out / "2025" / "snapshots").iterdir())
    assert len(snapshots) == 1 and (snapshots[0] / "SHA256SUMS").is_file()
    assert (snapshots[0] / "monatsreihe.csv").is_file()

    # Ein zweiter Lauf im selben Monat legt keinen zweiten Schnappschuss an (idempotent)
    again = _run(sandbox)
    assert again.returncode == 0 and "Schnappschuss nein" in again.stdout
    assert sorted((out / "2025" / "snapshots").iterdir()) == snapshots


def test_a_held_lock_ends_the_run_without_work(sandbox: dict[str, str], tmp_path: Path) -> None:
    lock = Path(sandbox["GEOREP_DATA_ROOT"])
    lock.mkdir(parents=True, exist_ok=True)
    holder = subprocess.Popen(
        ["flock", "-x", str(lock / ".monitor.lock"), "sleep", "20"],
    )
    try:
        result = _run(sandbox)
    finally:
        holder.terminate()
        holder.wait(timeout=10)
    assert result.returncode == 0 and "läuft bereits" in result.stdout
    assert not Path(sandbox["STUB_LOG"]).exists()  # kein einziger Schritt lief


def test_a_failing_step_stops_the_run_with_exit_one(sandbox: dict[str, str]) -> None:
    sandbox["STUB_FAIL"] = "papers"
    result = _run(sandbox)
    assert result.returncode == 1
    assert "FEHLER: papers (Exit 1)" in result.stdout
    assert "Abruf gescheitert" in result.stdout  # die Ausgabe des Schritts steht im Journal
    calls = Path(sandbox["STUB_LOG"]).read_text(encoding="utf-8").splitlines()
    assert len(calls) == 3  # sync, bootstrap, papers; danach nichts mehr
    assert not (Path(sandbox["MONITOR_PUBLISH_DIR"]) / "out" / "2025" / "stand.json").exists()


def test_missing_configuration_is_named(sandbox: dict[str, str]) -> None:
    del sandbox["MONITOR_PROFILE"]
    result = _run(sandbox)
    assert result.returncode == 1 and "MONITOR_PROFILE ist nicht gesetzt" in result.stdout


def test_with_a_remote_the_five_rclone_calls_run_in_order(sandbox: dict[str, str]) -> None:
    sandbox["MONITOR_R2_REMOTE"] = "georep:georep"
    result = _run(sandbox)
    assert result.returncode == 0, result.stdout + result.stderr
    calls = [c for c in Path(sandbox["STUB_LOG"]).read_text(encoding="utf-8").splitlines()]
    rclone = [c for c in calls if c.startswith("rclone ")]
    assert len(rclone) == 5
    assert all("--dry-run" in c for c in rclone)  # Trockenlauf überträgt nichts
    assert rclone[0].startswith("rclone sync") and "cache/2025/pdf" in rclone[0]
    assert "manifest.jsonl" in rclone[1] and "texts.parquet" in rclone[2]
    assert "2025/raw/papers.jsonl" in rclone[3]
    assert rclone[4].startswith("rclone copy ") and "2025/processed" in rclone[4]
