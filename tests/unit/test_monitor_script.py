"""Das Lauf-Skript (Option 07) gegen einen Stub: Reihenfolge, Sperre, Fehler, Trockenlauf.

Kein Netz, kein systemd, kein georep: ``uv`` ist ein Stub am Anfang von ``PATH``, der jeden
Aufruf protokolliert und die Dateien anlegt, die das Skript erwartet. Geprüft wird, was das
Skript selbst verantwortet: die Reihenfolge der Schritte, die Sperre, der Abbruch bei einem
Fehler, der Veröffentlichungsordner mit Schnappschuss und ``stand.json``, und dass ohne Ziel
weder rclone noch rsync nach außen laufen.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
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
if [[ "$*" == *paths* ]]; then
  if [[ "$*" == *--settings* ]]; then
    echo "profile=2025"; root="$GEOREP_DATA_ROOT/2025"; cache="$GEOREP_CACHE_ROOT/2025"
  else
    echo "profile="; root="$GEOREP_DATA_ROOT"; cache="$GEOREP_CACHE_ROOT"
  fi
  echo "data_root=$GEOREP_DATA_ROOT"
  echo "root=$root"
  echo "site=$root/site"
  echo "site_index=$root/site/index.html"
  echo "cache=$cache"
  echo "pdf_dir=$cache/pdf"
  echo "pdf_manifest=$cache/pdf/manifest.jsonl"
  echo "text_store=$cache/text/texts.parquet"
  echo "papers=$root/raw/papers.jsonl"
  echo "processed=$root/processed"
  exit 0
fi
case "$*" in
  *"--settings "*bootstrap*) echo "4 Dateien kopiert, 0 übersprungen; Stores nicht gefüllt" ;;
  *bootstrap*) echo "4 Dateien kopiert; 200 Paper und 200 Texte aus der Referenz" ;;
  *papers*) echo "papers       ausgeführt    seit 2026-10-01; Store 3 neu, 1 aktualisiert" ;;
  *pdfs*) echo "pdfs 2 geladen, 0 übersprungen; texts 2 extrahiert, 1 aktuell" ;;
  *)
    if [ -n "${STUB_PROFILE_SITE:-}" ]; then
      mkdir -p "$STUB_PROFILE_SITE/data"
      echo "<html>Profil</html>" > "$STUB_PROFILE_SITE/index.html"
      echo "{}" > "$STUB_PROFILE_SITE/index.html.stamp.json"
      echo "spalte" > "$STUB_PROFILE_SITE/data/monatsreihe.csv"
    fi
    mkdir -p "$STUB_MAIN_SITE/data"
    echo "<html>Haupt ${GEOREP_REPORT__MONITORING_URL:-}</html>" > "$STUB_MAIN_SITE/index.html"
    echo "{}" > "$STUB_MAIN_SITE/index.html.stamp.json"
    echo "14 ausgeführt, 1 übersprungen"
    ;;
esac
exit 0
"""

RCLONE_STUB = """#!/usr/bin/env bash
echo "rclone $*" >> "$STUB_LOG"
echo "Transferred: 3 / 3, 100%"
"""

# Der rsync-Stub kopiert lokal wirklich (das Skript stellt damit out/ zusammen) und schreibt nur
# für die Übertragung zum VPS (Ziel mit Doppelpunkt) auf, was im Quellbaum liegt.
RSYNC_STUB = """#!/usr/bin/env bash
echo "rsync $*" >> "$STUB_LOG"
target=${@: -1}
source=${@: -2:1}
if [[ "$target" == *:* ]]; then
  (cd "$source" && find . -type f) > "$STUB_TRANSFER"
  exit 0
fi
exec /usr/bin/rsync "$@"
"""

# Bricht den Schnappschuss mitten im Bauen ab (Strom weg, Platte voll, Lauf abgewuergt).
SHA256SUM_STUB = """#!/usr/bin/env bash
if [ -n "${STUB_FAIL_SHA:-}" ]; then
  echo "sha256sum abgebrochen" >&2
  exit 1
fi
exec /usr/bin/sha256sum "$@"
"""


@pytest.fixture
def sandbox(tmp_path: Path) -> dict[str, str]:
    """Eine Umgebung für das Skript: Stubs in PATH, Datenwurzel und Ziel in ``tmp_path``."""
    binaries = tmp_path / "bin"
    binaries.mkdir()
    stubs = (
        ("uv", UV_STUB),
        ("rclone", RCLONE_STUB),
        ("rsync", RSYNC_STUB),
        ("sha256sum", SHA256SUM_STUB),
    )
    for name, body in stubs:
        path = binaries / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    data = tmp_path / "data"
    env = dict(os.environ)
    env.update(
        PATH=f"{binaries}:{env['PATH']}",
        MONITOR_REPO=str(tmp_path),
        MONITOR_SETTINGS="settings.2025.toml",
        MONITOR_PUBLISH_DIR=str(tmp_path / "publish"),
        MONITOR_R2_REMOTE="",
        MONITOR_VPS_HOST="",
        MONITOR_HEALTHCHECK_URL="",
        GEOREP_DATA_ROOT=str(data),
        GEOREP_CACHE_ROOT=str(tmp_path / "cache"),
        DRY_RUN="1",
        STUB_LOG=str(tmp_path / "calls.log"),
        STUB_TRANSFER=str(tmp_path / "transfer.list"),
        STUB_MAIN_SITE=str(data / "site"),
        STUB_PROFILE_SITE=str(data / "2025" / "site"),
    )
    env.pop("STUB_FAIL", None)
    env.pop("STUB_FAIL_SHA", None)
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
    logged = Path(sandbox["STUB_LOG"]).read_text(encoding="utf-8").splitlines()
    calls = [line for line in logged if line.startswith("uv ")]
    assert calls == [
        "uv sync --locked",
        "uv run georep --settings settings.2025.toml paths",  # Profil und Pfade aus dem Paket
        "uv run georep paths",
        "uv run georep --settings settings.2025.toml bootstrap",
        "uv run georep --settings settings.2025.toml run --dry-run --online papers",
        "uv run georep --settings settings.2025.toml run --dry-run --online pdfs texts",
        "uv run georep --settings settings.2025.toml run --dry-run",
        "uv run georep bootstrap",
        "uv run georep run",
    ]
    assert not [line for line in logged if line.startswith("rclone ")]  # ohne Remote kein Upload

    out = Path(sandbox["MONITOR_PUBLISH_DIR"]) / "out"
    assert (out / "index.html").read_text(encoding="utf-8").strip() == "<html>Haupt 2025/</html>"
    assert (out / "2025" / "index.html").is_file()
    stand = json.loads((out / "2025" / "stand.json").read_text(encoding="utf-8"))
    assert stand["profil"] == "2025" and stand["ergebnis"] == "trocken"
    assert (stand["neue_paper"], stand["pdfs"], stand["texte"]) == (3, 2, 2)
    assert re.fullmatch(r"\d{4}-\d{2}", stand["schnappschuss"])  # der Monat dieses Laufs
    assert stand["seite_kb"] >= 0 and stand["dauer_s"] >= 0
    assert len(stand["schritte"]) == 7 and all(stand["schritte"])  # paths steht nicht im Stand
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
    assert calls == [
        "uv sync --locked",
        "uv run georep --settings settings.2025.toml paths",
        "uv run georep paths",
        "uv run georep --settings settings.2025.toml bootstrap",
        "uv run georep --settings settings.2025.toml run --dry-run --online papers",
    ]  # danach nichts mehr
    assert not (Path(sandbox["MONITOR_PUBLISH_DIR"]) / "out" / "2025" / "stand.json").exists()


def test_missing_configuration_is_named(sandbox: dict[str, str]) -> None:
    del sandbox["MONITOR_SETTINGS"]
    result = _run(sandbox)
    assert result.returncode == 1 and "MONITOR_SETTINGS ist nicht gesetzt" in result.stdout
    assert not Path(sandbox["STUB_LOG"]).exists()  # kein Aufruf vor der Prüfung


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


UNITS = REPO / "deploy" / "systemd"


def _systemd_analyze(paths: list[Path]) -> subprocess.CompletedProcess[str]:
    """``systemd-analyze --user verify`` braucht ein Laufzeitverzeichnis, sonst bricht es früh ab."""
    env = dict(os.environ)
    runtime = env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    env["XDG_RUNTIME_DIR"] = runtime
    return subprocess.run(
        ["systemd-analyze", "--user", "verify", *[str(p) for p in paths]],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_systemd_accepts_the_units() -> None:
    """Die Einheiten müssen startbar sein; ein Fehler darin fällt sonst erst im Betrieb auf.

    ``WorkingDirectory=${MONITOR_REPO}`` war so ein Fall: systemd ersetzt Variablen nur in
    ``ExecStart=`` und Verwandten, sonst ist der Pfad einfach nicht absolut und die Einheit
    startet nie (gefunden im Review am 2026-10-12).
    """
    if shutil.which("systemd-analyze") is None:
        pytest.skip("systemd-analyze nicht vorhanden")
    units = [UNITS / "georep-monitor.service", UNITS / "georep-monitor.timer"]
    result = _systemd_analyze(units)
    if "Failed to initialize manager" in result.stderr:
        pytest.skip(f"kein Nutzer-systemd in dieser Umgebung: {result.stderr.strip()}")
    output = result.stdout + result.stderr
    assert "not absolute" not in output, output
    assert "fatal error" not in output, output
    assert result.returncode == 0, output


def test_the_transferred_tree_carries_the_current_stand(sandbox: dict[str, str]) -> None:
    """stand.json entstand früher erst nach der Übertragung und fehlte deshalb auf dem Server;
    der rsync davor hatte ihn mit --delete auch noch entfernt (Review 2026-10-12)."""
    sandbox["MONITOR_VPS_HOST"] = "server.invalid"
    sandbox["MONITOR_VPS_WWW"] = "/var/www/georep"
    result = _run(sandbox)
    assert result.returncode == 0, result.stdout + result.stderr
    transferred = Path(sandbox["STUB_TRANSFER"]).read_text(encoding="utf-8").split()
    assert "./2025/stand.json" in transferred
    assert "./index.html" in transferred and "./2025/index.html" in transferred
    assert any(name.startswith("./2025/snapshots/") for name in transferred)
    # Der übertragene Stand ist der dieses Laufs, nicht der des vorigen
    stand = json.loads(
        (Path(sandbox["MONITOR_PUBLISH_DIR"]) / "out" / "2025" / "stand.json").read_text(
            encoding="utf-8"
        )
    )
    assert stand["beginn"] and stand["ende"] >= stand["beginn"]
    calls = Path(sandbox["STUB_LOG"]).read_text(encoding="utf-8").splitlines()
    assert calls[-1].startswith("rsync ") and "server.invalid:/var/www/georep/" in calls[-1]
    assert "--dry-run" in calls[-1]  # Trockenlauf überträgt nichts

    # Ein zweiter Lauf findet den Stand des ersten vor und ersetzt ihn, statt ihn zu verlieren
    again = _run(sandbox)
    assert again.returncode == 0
    assert "./2025/stand.json" in Path(sandbox["STUB_TRANSFER"]).read_text(encoding="utf-8").split()


def test_an_aborted_snapshot_does_not_block_the_next_run(sandbox: dict[str, str]) -> None:
    """Ein halber Schnappschuss darf nicht stehen bleiben: der Monatsordner ist die Sperre, und
    jeder spätere Lauf hätte ihn übersprungen (Review 2026-10-12)."""
    sandbox["STUB_FAIL_SHA"] = "1"
    broken = _run(sandbox)
    assert broken.returncode == 1 and "FEHLER: SHA256SUMS" in broken.stdout
    snapshots = Path(sandbox["MONITOR_PUBLISH_DIR"]) / "out" / "2025" / "snapshots"
    month = dt.date.today().strftime("%Y-%m")
    assert not (snapshots / month).exists()  # nichts Halbes unter dem Monatsnamen

    del sandbox["STUB_FAIL_SHA"]
    good = _run(sandbox)
    assert good.returncode == 0 and f"Schnappschuss {month}" in good.stdout
    assert (snapshots / month / "SHA256SUMS").is_file()
    assert (snapshots / month / "monatsreihe.csv").is_file()
    # Der Arbeitsordner bleibt nicht liegen und zählt nicht als Schnappschuss
    assert [p.name for p in snapshots.iterdir()] == [month]


def test_the_profile_name_comes_from_the_package(sandbox: dict[str, str]) -> None:
    """Das Skript fragt Profil und Pfade bei georep ab, statt sie in monitor.env zu wiederholen."""
    assert "MONITOR_PROFILE" not in sandbox
    result = _run(sandbox)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Profil 2025, Seite unter" in result.stdout
    assert (Path(sandbox["MONITOR_PUBLISH_DIR"]) / "out" / "2025" / "index.html").is_file()


def test_a_real_run_without_a_profile_page_fails(sandbox: dict[str, str]) -> None:
    """Im echten Lauf ist eine fehlende Profilseite ein Fehler, kein stilles Exit 0."""
    sandbox["DRY_RUN"] = ""
    del sandbox["STUB_PROFILE_SITE"]  # der Stub legt keine Profilseite an
    result = _run(sandbox)
    assert result.returncode == 1
    assert "FEHLER: Profilseite fehlt unter" in result.stdout
    assert "/2025/site" in result.stdout


def test_the_published_tree_has_no_step_stamps(sandbox: dict[str, str]) -> None:
    """Der Stamp des Schritts report liegt neben index.html; veröffentlicht gehört er nicht."""
    result = _run(sandbox)
    assert result.returncode == 0, result.stdout + result.stderr
    out = Path(sandbox["MONITOR_PUBLISH_DIR"]) / "out"
    stamps = [p.name for p in out.rglob("*.stamp.json")]
    assert stamps == []
    assert (out / "index.html").is_file() and (out / "2025" / "index.html").is_file()
