from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from syrupy.assertion import SnapshotAssertion

from georep.cli import main
from georep.layout import Layout
from georep.pipeline import build_steps
from georep.report.tables import csv_plan
from georep.settings import load_settings


@pytest.fixture
def project(tmp_path: Path, mini_root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "settings.toml").write_text(
        # Punktschlüssel statt einer [context]-Tabelle: Tests hängen weitere Schlüssel an, und die
        # landeten nach einer Tabellenkopfzeile in ihr.
        f'data_root = "{tmp_path / "data"}"\nreference_root = "{mini_root}"\n'
        f'context.root = "{mini_root / "context"}"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_steps_lists_the_chain(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["steps"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("opendata") and "[Netz]" in out
    assert "results" in out and "inverted_index.parquet" in out


def _step_counts(project: Path) -> tuple[int, int]:
    """(Offline-Schritte, Netzschritte) aus dem Register, damit neue Schritte keine Literale brechen."""
    settings = load_settings(cwd=project)
    steps = build_steps(settings, Layout.from_settings(settings))
    network = sum(1 for s in steps if s.network)
    return len(steps) - network, network


def test_bootstrap_run_status_export_regress(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["bootstrap"]) == 0
    assert "200 Paper und 200 Texte" in capsys.readouterr().out
    offline, network = _step_counts(project)
    assert main(["run", "--dry-run"]) == 0
    assert f"{network} übersprungen, {offline} geplant" in capsys.readouterr().out
    assert main(["run"]) == 0
    out = capsys.readouterr().out
    assert f"{offline} ausgeführt, {network} übersprungen" in out
    assert "report       ausgeführt" in out
    assert (project / "data" / "site" / "index.html").exists()
    assert main(["status"]) == 0
    status = capsys.readouterr().out
    assert status.count("aktuell") >= 7 and "200 Dokumente" in status and "[Netz]" in status
    assert main(["export"]) == 0
    # Eine CSV je vorhandener Tabelle des Registers (F6-Konvention: kein Literal), denn
    # optionale Tabellen ohne Datei schreibt `georep export` nicht.
    expected = sum(
        1
        for path, _, _ in csv_plan(Layout.from_settings(load_settings(cwd=project)))
        if path.exists()
    )
    assert f"{expected} CSV-Dateien" in capsys.readouterr().out
    assert (project / "data" / "processed" / "wahlbezirke_auswertung.csv").exists()
    assert main(["regress"]) == 0
    assert capsys.readouterr().out.startswith("alle: n=3")
    assert main(["regress", "--exclude", "1"]) == 1  # zwei Bezirke reichen nicht
    assert "mindestens 3" in capsys.readouterr().err


def test_domain_errors_exit_with_one(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "index"]) == 1
    assert "bootstrap" in capsys.readouterr().err


def test_unknown_step_is_a_domain_error(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "gibtsnicht"]) == 1
    assert "Unbekannte Schritte" in capsys.readouterr().err


def test_missing_settings_file_exits_with_one(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--settings", "fehlt.toml", "steps"]) == 1
    assert "fehlt.toml" in capsys.readouterr().err


def test_usage_errors_exit_with_two(project: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--nope"])
    assert exit_info.value.code == 2


def test_fetch_plans_network_steps_and_texts(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["bootstrap"])
    capsys.readouterr()
    assert main(["run", "--dry-run", "--online", "opendata", "papers"]) == 0
    out = capsys.readouterr().out
    assert out.rstrip().endswith("2 geplant") and "Netz aus" not in out


def test_steps_output_is_stable(
    project: Path, capsys: pytest.CaptureFixture[str], snapshot: SnapshotAssertion
) -> None:
    assert main(["steps"]) == 0
    assert capsys.readouterr().out == snapshot


def test_fetch_with_limit_runs_only_the_named_step(
    project: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import requests

    from georep.settings import Settings, load_settings
    from tests.fakes import FakeSession, response

    src = load_settings(cwd=project).sources
    routes: dict[str, requests.Response | Exception] = {
        src.opendata.results_url: response(src.opendata.results_url, content=b"a;b\n1;2\n"),
        src.opendata.districts_url: response(
            src.opendata.districts_url, payload={"type": "FeatureCollection", "features": [{}]}
        ),
    }
    seen: list[int] = []

    def fake_session(settings: Settings, path: Path) -> FakeSession:
        seen.append(settings.sources.oparl.pdf_limit)
        return FakeSession(routes)

    monkeypatch.setattr("georep.pipeline.cached_session", fake_session)
    assert main(["fetch", "opendata", "--limit", "7"]) == 0
    out = capsys.readouterr().out
    assert "opendata     ausgeführt" in out and "1 ausgeführt" in out
    assert seen == [7]


def test_regress_without_results_is_a_domain_error(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["regress"]) == 1
    assert "wahlbezirke_auswertung.parquet" in capsys.readouterr().err


def test_profile_writes_one_file_per_offline_step(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["bootstrap"])
    capsys.readouterr()
    assert main(["profile", "--out", "prof", "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "voters       ausgeführt    erzwungen; 3 Wahlbezirke, 3 Paare mit Stadtbezirk" in out
    offline, _ = _step_counts(project)
    assert out.count("function calls") == offline
    assert out.count("Anzeige: uv run snakeviz") == offline
    assert len(list((project / "prof").glob("*.prof"))) == offline
    assert main(["profile", "opendata", "--out", "prof"]) == 0
    assert "Netz aus" in capsys.readouterr().out
    assert len(list((project / "prof").glob("*.prof"))) == offline


def test_contracts_setting_reaches_deal(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import deal

    @deal.pre(lambda x: x > 0)
    def positive(x: int) -> int:
        return x

    settings = project / "settings.toml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + 'contracts = "off"\n', encoding="utf-8"
    )
    assert main(["status"]) == 0
    assert "Verträge off" in capsys.readouterr().out
    assert positive(-1) == -1
    settings.write_text(
        settings.read_text(encoding="utf-8").replace('"off"', '"on"'), encoding="utf-8"
    )
    assert main(["status"]) == 0
    assert "Verträge on" in capsys.readouterr().out
    with pytest.raises(deal.PreContractError):
        positive(-1)


def test_regress_prints_a_line_per_weighting_variant(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Option 06: ``--varianten`` druckt die Sensitivitätstabelle als Text, ohne die Seite zu bauen."""
    main(["bootstrap"])
    main(["run"])
    capsys.readouterr()
    assert main(["regress", "--varianten"]) == 0
    out = capsys.readouterr().out
    variants = pl.read_parquet(
        Layout.from_settings(load_settings(cwd=project)).weighted
    ).get_column("variante")
    for name in variants.unique().to_list():
        assert f"{name} " in out
    assert out.count("Summe") == variants.n_unique()
    assert "rho=1.000" in out  # die Einheitsvariante ordnet wie die ungewichtete Quote


# --- Option 03 ------------------------------------------------------------------------------------


def test_regress_controls_prints_table_six_after_the_run(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["regress", "--controls"]) == 1
    assert "regression_kontrollen.parquet" in capsys.readouterr().err
    assert main(["bootstrap"]) == 0 and main(["run"]) == 0
    capsys.readouterr()
    assert main(["regress", "--controls"]) == 0
    out = capsys.readouterr().out
    # Auf der Mini-Fixture (n = 3) bleibt Modell A; die Zeilen nennen Konstante und Trefferquote
    assert "A (alle): n=3, k=1" in out and "trefferquote" in out and "(Konstante)" in out
    assert "VIF=1.00" in out


def test_fetch_max_pages_is_the_originator_probe(
    project: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Option 04: ``fetch papers --max-pages 1`` liest eine Seite und sagt, wie viele der
    gesehenen Paper ein Urheberfeld tragen; am 2026-10-09 war das keines."""
    import requests

    from georep.settings import Settings, load_settings
    from tests.fakes import FakeSession, response

    src = load_settings(cwd=project).sources
    page = {
        "data": [
            {
                "id": f"https://ris.invalid/papers/{i}",
                "name": f"P{i}",
                "date": "2024-05-01",
                "paperType": "Antrag",
            }
            for i in range(3)
        ],
        "links": {"self": src.oparl.endpoint, "next": f"{src.oparl.endpoint}?page=2"},
    }
    routes: dict[str, requests.Response | Exception] = {
        src.oparl.endpoint: response(src.oparl.endpoint, payload=page),
        f"{src.oparl.endpoint}?page=2": requests.ConnectionError("Seite 2 darf nicht kommen"),
    }
    seen: list[int] = []

    def fake_session(settings: Settings, path: Path) -> FakeSession:
        seen.append(settings.sources.oparl.max_pages)
        return FakeSession(routes)

    monkeypatch.setattr("georep.pipeline.cached_session", fake_session)
    assert main(["fetch", "papers", "--max-pages", "1"]) == 0
    out = capsys.readouterr().out
    assert "1 Seiten, 3 Paper gesehen, 3 im Zeitraum, davon 0 mit Urheberfeld" in out
    assert seen == [1]
    # Die zweite Seite ist eine ConnectionError-Route: --max-pages 1 darf sie nicht anfragen


def test_max_pages_changes_the_fingerprint(project: Path) -> None:
    """Die Grenze zählt zum Fingerprint; ``georep status`` zeigt den Schritt danach als offen."""
    from georep.cli import _with_fetch_limits
    from georep.settings import load_settings

    base = load_settings(cwd=project)
    assert _with_fetch_limits(base, None, None) is base
    assert _with_fetch_limits(base, None, 1).fingerprint() != base.fingerprint()
    assert _with_fetch_limits(base, 5, None).sources.oparl.pdf_limit == 5
    both = _with_fetch_limits(base, 5, 2).sources.oparl
    assert (both.pdf_limit, both.max_pages) == (5, 2)


# --- Option 01: Profile -------------------------------------------------------------------------


def test_unknown_profile_exits_with_one_and_lists_the_profiles(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--profile", "gibtsnicht", "status"]) == 1
    err = capsys.readouterr().err
    assert "gibtsnicht" in err and "duesseldorf" in err


def test_profiles_command_lists_the_package_profiles(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["profiles"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("duesseldorf") and "Düsseldorf" in out and "Standard" in out


def test_status_names_profile_and_city(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--profile", "duesseldorf", "status"]) == 0
    out = capsys.readouterr().out
    assert "Profil:     duesseldorf (Düsseldorf)" in out and "flach" in out


# --- Option 07: Monitoring -------------------------------------------------------------------


def test_profile_2025_bootstraps_without_a_corpus_and_shows_its_root(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tests.conftest import REPO

    profile = str(REPO / "settings.2025.toml")
    assert main(["--settings", profile, "status"]) == 0
    status = capsys.readouterr().out
    # Option 01 druckt den Namen des Paketprofils; der Ordner kommt aus dem Schlüssel profile
    assert "Daten unter" in status and str(project / "data" / "2025") in status
    assert "Periode:    Wahlperiode seit 2025, 2025-09-15 bis offen" in status
    assert main(["--settings", profile, "bootstrap"]) == 0
    out = capsys.readouterr().out
    assert "Stores nicht aus der Referenz gefüllt" in out and "nicht gefunden" in out
    root = project / "data" / "2025"
    external = {p.name for p in (root / "external").iterdir()}
    assert {"Stimmbezirk_Wahlergebnis.csv", "Stimmbezirke_2025.geojson"} <= external
    assert {"streets_per_district.json", "wikipedia_dict.json"} <= {
        p.name for p in (root / "raw").iterdir()
    }
    assert not (root / "raw" / "papers.jsonl").exists()  # kein Korpus der Hauptperiode
    assert not (project / "data" / "raw").exists()  # die Hauptperiode bleibt unberuehrt
    # Ohne Store plant der Metadatenschritt einen vollstaendigen Abruf; kein echter Abruf
    assert main(["--settings", profile, "run", "--dry-run", "--online", "papers"]) == 0
    assert "papers       geplant" in capsys.readouterr().out


def test_paths_prints_the_layout_for_scripts(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``georep paths`` ist die Quelle für deploy/; nur das Profil darf leer sein."""
    from tests.conftest import REPO

    assert main(["paths"]) == 0
    main_profile = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines() if line)
    assert main_profile["profile"] == ""
    assert main_profile["root"] == str(project / "data")
    assert main_profile["site"] == str(project / "data" / "site")
    assert all(v.startswith("/") for k, v in main_profile.items() if k != "profile")

    assert main(["--settings", str(REPO / "settings.2025.toml"), "paths"]) == 0
    profile = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines() if line)
    assert profile["profile"] == "2025"
    assert profile["root"] == str(project / "data" / "2025")
    assert profile["site_index"] == str(project / "data" / "2025" / "site" / "index.html")
    assert profile["papers"] == str(project / "data" / "2025" / "raw" / "papers.jsonl")
    assert profile["pdf_dir"].endswith("/2025/pdf")
    assert profile["text_store"].endswith("/2025/text/texts.parquet")
    assert set(profile) == set(main_profile) and len(profile) == 11
    # Jeder Wert ohne Leerzeichen am Rand: das Skript liest sie als key=wert
    assert all(v == v.strip() for v in profile.values())
