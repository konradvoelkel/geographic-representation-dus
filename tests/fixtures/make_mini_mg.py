"""Erzeugt die Mini-Fixture ``tests/fixtures/mg/`` aus der Netzstichprobe vom 2026-10-12.

Aufruf aus dem Repo-Wurzelverzeichnis::

    uv run python -m tests.fixtures.make_mini_mg

Auswahl: die drei Wahlbezirke 04, 09 und 23 Mönchengladbachs. Sie sind die, deren Straßennamen
in der PDF-Stichprobe überhaupt vorkommen (Vorster Straße, Winkeln, Brandenberger Straße,
Hauptstraße); mit drei beliebigen Bezirken fände die Kette keinen einzigen Treffer. Die Eingaben kommen aus den
aufgezeichneten Antworten (``tests/fixtures/http/``, ``tests/fixtures/oparl/``,
``tests/fixtures/pdf/mg/``) und aus den vier öffentlichen votemanager-Dateien samt Shapefile-Zip,
die am 2026-10-12 einmal geladen wurden; das Skript schneidet sie auf die drei Wahlbezirke zu.

Erwartung (``mg/expected/`` gibt es noch nicht): bis zum echten Lauf (Stufe G) ist der Golden
Master dieser Stadt eine Charakterisierung der eigenen Kette, kein unabhängiges Orakel.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import polars as pl
import shapefile

from georep.geo import PrecinctIndex, read_canonical_precincts
from georep.layout import Layout
from georep.prep.precincts import canonical_precincts, read_source
from georep.records import PaperRecord
from georep.settings import load_settings
from georep.sources.overpass import street_names
from georep.sources.wiki import fetch_geosearch_pois, fetch_sparql_pois, sparql_query
from georep.stores import PaperStore, TextMeta, TextStore

REPO = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent
MG = FIXTURES / "mg"
HTTP = FIXTURES / "http"
PDFS = FIXTURES / "pdf" / "mg"
DISTRICTS = (4, 9, 23)  # Wahlbezirke; die Stimmbezirksnummer trägt sie an Stelle 1 und 2
SAMPLE_PRECINCTS = ("10404", "10906", "32301")  # die drei mit aufgezeichneter Overpass-Antwort
EXTRACTOR = "pypdf (Stichprobe, Oktober 2026)"


def _rows_of(path: Path, column: str, sep: str = ";") -> pl.DataFrame:
    frame = pl.read_csv(path, separator=sep, infer_schema=False, encoding="utf8")
    return frame.filter(
        pl.col(column)
        .str.strip_chars()
        .str.slice(1, 2)
        .cast(pl.Int64, strict=False)
        .is_in(list(DISTRICTS))
    )


def write_results(source: Path) -> None:
    """Stimmbezirks-CSV: die Zeilen der drei Wahlbezirke, Urnen- und Briefwahlbezirke."""
    rows = _rows_of(source, "gebiet-nr")
    rows.write_csv(MG / "external" / source.name, separator=";")
    print(f"  {source.name}: {rows.height} Zeilen")


def write_district_names(source: Path) -> None:
    frame = pl.read_csv(source, separator=";", infer_schema=False, encoding="utf8")
    rows = frame.filter(
        pl.col("gebiet-nr").str.strip_chars().cast(pl.Int64, strict=False).is_in(list(DISTRICTS))
    )
    rows.write_csv(MG / "external" / source.name, separator=";")
    print(f"  {source.name}: {rows.height} Zeilen ({rows.get_column('gebiet-name').to_list()})")


def write_streets_directory(source: Path) -> None:
    """Straßenverzeichnis: nur die Zeilen der Stimmbezirke der drei Wahlbezirke."""
    rows = _rows_of(source, "Bezirk-Nr")
    rows.write_csv(MG / "external" / source.name, separator=";")
    print(f"  {source.name}: {rows.height} Zeilen")


def write_shapefile_zip(source: Path, target: Path, keep: set[str]) -> None:
    """Ein Zip mit demselben Aufbau, aber nur den Polygonen der drei Wahlbezirke."""
    with zipfile.ZipFile(source) as archive:
        member = "Wahlen_EPSG25832_SHAPE/Stimmbezirke_MG"
        reader = shapefile.Reader(
            shp=io.BytesIO(archive.read(f"{member}.shp")),
            shx=io.BytesIO(archive.read(f"{member}.shx")),
            dbf=io.BytesIO(archive.read(f"{member}.dbf")),
            encoding="latin-1",
            encodingErrors="replace",
        )
        prj = archive.read(f"{member}.prj")
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    kept = 0
    with shapefile.Writer(shp=shp, shx=shx, dbf=dbf) as writer:
        writer.fields = [f for f in reader.fields if f[0] != "DeletionFlag"]
        for record in reader.iterShapeRecords():
            if str(record.record["Nummer"]).strip() not in keep:
                continue
            writer.shape(record.shape)
            writer.record(*record.record)
            kept += 1
    reader.close()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
        out.writestr(f"{member}.shp", shp.getvalue())
        out.writestr(f"{member}.shx", shx.getvalue())
        out.writestr(f"{member}.dbf", dbf.getvalue())
        out.writestr(f"{member}.prj", prj)
    print(f"  {target.name}: {kept} Polygone, {target.stat().st_size} Bytes")


def write_streets_json(precincts: list[Any]) -> None:
    """``raw/streets_per_district.json`` aus den drei aufgezeichneten Overpass-Antworten."""
    by_number = {p.precinct_id: p for p in precincts}
    entries = []
    for number in SAMPLE_PRECINCTS:
        payload = json.loads((HTTP / f"overpass_mg_{number}.json").read_text(encoding="utf-8"))
        precinct = by_number[number]
        entries.append(
            {
                "stimmbezirks_id": number,
                "stimmbezirks_name": precinct.district_name,
                "wahlbezirk_id": precinct.district_id,
                "straßen": street_names(payload),
            }
        )
    (MG / "raw" / "streets_per_district.json").write_text(
        json.dumps(entries, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  streets_per_district.json: {sum(len(e['straßen']) for e in entries)} Straßennamen")


class _Recorded:
    """Transport über die aufgezeichneten Antworten; eine Antwort je Aufruf, in Reihenfolge."""

    def __init__(self, answers: list[dict[str, Any]]) -> None:
        self.answers = list(answers)

    def get(self, url: str, *, params: Any = None, headers: Any = None) -> Any:
        import requests

        resp = requests.Response()
        resp.status_code = 200
        resp.url = url
        resp._content = json.dumps(self.answers.pop(0)).encode()
        return resp

    def post(self, url: str, *, data: Any = None, headers: Any = None) -> Any:
        raise AssertionError("GeoSearch und SPARQL sprechen GET")


def write_pois_json(precincts: list[Any], settings: Any) -> None:
    """``raw/wikipedia_dict.json`` aus der SPARQL-Antwort und den drei GeoSearch-Antworten."""
    index = PrecinctIndex(precincts, settings.geo.working_crs)
    wiki = settings.sources.wikidata
    sparql_payload = json.loads((HTTP / "wikidata_sparql_mg.json").read_text(encoding="utf-8"))
    sparql = fetch_sparql_pois(
        _Recorded([sparql_payload]),
        wiki.sparql_endpoint,
        sparql_query(wiki.entity, wiki.language),
        index,
    )
    sampled = [p for p in precincts if p.precinct_id in SAMPLE_PRECINCTS]
    answers = [
        json.loads((HTTP / f"wikipedia_geosearch_mg_{p.precinct_id}.json").read_text("utf-8"))
        for p in sampled
    ]
    geosearch = fetch_geosearch_pois(
        _Recorded(answers),
        wiki.wikipedia_api,
        sampled,
        index,
        settings.geo.working_crs,
        limit=wiki.geosearch_limit,
        delay_s=0.0,
        sleep=lambda _: None,
    )
    entries = sparql + geosearch
    (MG / "raw" / "wikipedia_dict.json").write_text(
        json.dumps(entries, ensure_ascii=False), encoding="utf-8"
    )
    assigned = sum(1 for e in entries if e["wahlkreis_id"] is not None)
    print(f"  wikipedia_dict.json: {len(entries)} Orte, {assigned} zugeordnet")


def write_corpus(settings: Any) -> None:
    """``raw/papers.jsonl`` und ``cache/text/texts.parquet`` aus der OParl-Seite und den PDFs."""
    from georep.oparl import PaperPage
    from georep.prep.extract import extract_text, normalise_text

    raw = json.loads((FIXTURES / "oparl" / "papers_page_0011.json").read_text(encoding="utf-8"))
    records = [PaperRecord.from_oparl(p) for p in PaperPage.model_validate(raw).data]
    store = PaperStore(MG / "raw" / "papers.jsonl")
    store.save(records)
    texts = TextStore(MG / "cache" / "text" / "texts.parquet")
    stored = 0
    for pdf in sorted(PDFS.glob("*.pdf")):
        texts.put(
            pdf.name,
            normalise_text(extract_text(pdf)),
            TextMeta(extractor=EXTRACTOR, source="stichprobe"),
        )
        stored += 1
    texts.save()
    print(f"  papers.jsonl: {len(records)} Paper; texts.parquet: {stored} Texte")


def main() -> None:
    settings = load_settings(profile="moenchengladbach")
    layout = Layout.from_settings(settings)
    for folder in ("external", "raw", "cache/text"):
        (MG / folder).mkdir(parents=True, exist_ok=True)
    external = layout.external
    print("Eingaben aus", external)
    write_results(external / settings.sources.opendata.results_file)
    write_district_names(external / settings.sources.opendata.district_names_file)
    write_streets_directory(external / settings.sources.opendata.streets_file)

    source = read_source(layout.districts_geojson, settings.precincts)
    keep = {
        str(f["properties"][settings.precincts.id_property]).strip()
        for f in source.features
        if str(f["properties"][settings.precincts.id_property]).strip()[1:3].isdigit()
        and int(str(f["properties"][settings.precincts.id_property]).strip()[1:3]) in DISTRICTS
    }
    write_shapefile_zip(
        layout.districts_geojson,
        MG / "external" / settings.sources.opendata.districts_file,
        keep,
    )

    # Die kanonischen Stimmbezirke der Fixture, einmal gelesen: Namen und Wahlbezirke je Nummer
    from georep.prep.precincts import district_names_from_csv

    mini_source = read_source(
        MG / "external" / settings.sources.opendata.districts_file, settings.precincts
    )
    names = district_names_from_csv(
        MG / "external" / settings.sources.opendata.district_names_file,
        settings.precincts,
        settings.columns.results,
    )
    canonical = canonical_precincts(mini_source, settings.precincts, names)
    tmp = MG / "raw" / "_stimmbezirke.geojson"
    tmp.write_text(json.dumps(canonical, ensure_ascii=False), encoding="utf-8")
    precincts = read_canonical_precincts(tmp, settings.geo.working_crs)
    tmp.unlink()
    print(
        f"  Stimmbezirke der Fixture: {len(precincts)} in {len({p.district_id for p in precincts})} Wahlbezirken"
    )

    write_streets_json(precincts)
    write_pois_json(precincts, settings)
    write_corpus(settings)


if __name__ == "__main__":
    main()
