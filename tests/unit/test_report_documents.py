"""dokumente.json: Dokumente mit Treffer ohne Texte, Begriffe als Indizes, versteckte Begriffe fehlen."""

from __future__ import annotations

import datetime as dt
import json

import polars as pl

from georep.layout import Layout
from georep.report.build import DOCUMENTS_NAME
from georep.report.documents import DOCUMENT_COLUMNS, documents_payload, download_base

NOW = dt.datetime(2026, 10, 11, tzinfo=dt.UTC)


def _corpus() -> pl.DataFrame:
    base = "http://ris.example/Oparl/bodies/0015/downloadfiles/"
    return pl.DataFrame(
        {
            "id": ["p1", "p2", "p3", "p4"],
            "name": ["Alt", "Neu", "Mitte", "Ohne Treffer"],
            "reference": ["R1", "R2", "R3", "R4"],
            "date": [
                dt.date(2021, 1, 1),
                dt.date(2024, 5, 5),
                dt.date(2023, 3, 3),
                dt.date(2022, 2, 2),
            ],
            "paper_type": ["Antrag", "Anfrage", None, "Antrag"],
            "download_url": [base + "1.pdf", base + "2.pdf", base + "3.pdf", base + "4.pdf"],
        }
    )


def _index() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "suchbegriffe": ["allee", "schulweg", "weg", "nichts"],
            "paper_ids": [["p1", "p2"], ["p4"], ["p3", "p2"], []],
            "anzahl_treffer": [2, 1, 2, 0],
        }
    )


def test_payload_orders_newest_first_and_indexes_terms() -> None:
    payload = documents_payload(_corpus(), _index(), ("schulweg",), version="x", generated_at=NOW)
    assert payload["base"] == "https://ris.example/Oparl/bodies/0015/downloadfiles/"
    assert payload["documents"] == [
        # das sechste Feld ist der Urheber (Option 04), hier ohne Zuordnung leer
        ["2.pdf", "2024-05-05", "R2", "Neu", "Anfrage", ""],
        ["3.pdf", "2023-03-03", "R3", "Mitte", "", ""],
        ["1.pdf", "2021-01-01", "R1", "Alt", "Antrag", ""],
    ]  # p4 hat nur den versteckten Begriff und fehlt
    assert payload["terms"] == {"allee": [0, 2], "weg": [0, 1]}
    assert payload["fields"] == ["link", "datum", "drucksache", "titel", "art", "urheber"]
    assert payload["version"] == "x" and payload["generated_at"] == NOW.isoformat()


def test_download_base_needs_a_common_directory() -> None:
    assert download_base(["http://a/x/1.pdf", "http://a/x/2.pdf"]) == "https://a/x/"
    assert download_base(["http://a/x/1.pdf", "http://b/y/2.pdf"]) == ""
    assert download_base([]) == ""
    payload = documents_payload(
        _corpus().with_columns(
            pl.Series("download_url", ["http://a/1", "http://b/2", "http://c/3", "http://d/4"])
        ),
        _index(),
        (),
        version="x",
        generated_at=NOW,
    )
    documents = payload["documents"]
    assert isinstance(documents, list)
    assert payload["base"] == "" and documents[0][0] == "https://b/2"


def test_site_documents_match_index_and_corpus(mini_run: Layout) -> None:
    payload = json.loads((mini_run.site_data / DOCUMENTS_NAME).read_text(encoding="utf-8"))
    index = pl.read_parquet(mini_run.index)
    corpus = pl.read_parquet(mini_run.corpus, columns=DOCUMENT_COLUMNS)
    visible = index.filter((pl.col("suchbegriffe") != "schulweg") & (pl.col("anzahl_treffer") > 0))
    expected_ids = set(visible.get_column("paper_ids").explode().to_list())
    assert len(payload["documents"]) == len(expected_ids)
    assert set(payload["terms"]) == set(visible.get_column("suchbegriffe").to_list())
    assert all(0 <= i < len(payload["documents"]) for ids in payload["terms"].values() for i in ids)
    assert payload["base"].startswith("https://")
    titles = set(corpus.get_column("name").to_list())
    assert all(doc[3] in titles for doc in payload["documents"])
    for term, ids in payload["terms"].items():
        hits = visible.filter(pl.col("suchbegriffe") == term).get_column("anzahl_treffer")[0]
        assert len(ids) == hits


# --- Option 04: der Urheber als sechstes Feld -----------------------------------------------------


def test_the_sixth_field_is_the_originator() -> None:
    """``FIELDS`` wächst am Ende; das JavaScript des Rahmens liest ``doc[5]`` hinter der Art."""
    from georep.report.documents import FIELDS, originator_labels

    assert FIELDS == ("link", "datum", "drucksache", "titel", "art", "urheber")
    attribution = pl.DataFrame(
        {
            "id": ["p1", "p2", "p3"],
            "urheber_art": ["Fraktion", "Verwaltung", "Fraktion"],
            "parteien": [["CDU"], [], ["CDU", "GRUENE"]],
        },
        schema={"id": pl.String, "urheber_art": pl.String, "parteien": pl.List(pl.String)},
    )
    labels = originator_labels(attribution, {"CDU": "CDU", "GRUENE": "Bündnis 90/Die Grünen"})
    assert labels == {
        "p1": "CDU",
        "p2": "Verwaltung",  # ohne Partei steht die Klasse da
        "p3": "CDU, Bündnis 90/Die Grünen",
    }
    assert originator_labels(None, {}) == {}  # ohne den Schritt parties bleibt das Feld leer


def test_the_payload_carries_the_originator_per_document() -> None:
    from georep.report.documents import documents_payload as payload_with

    found = payload_with(
        _corpus(),
        _index(),
        [],
        version="0",
        generated_at=NOW,
        originators={"p1": "SPD", "p2": "Verwaltung"},
    )
    documents = found["documents"]
    assert isinstance(documents, list)
    rows = {doc[2]: doc for doc in documents}  # nach Drucksache
    assert len(rows["R1"]) == 6 and rows["R1"][5] == "SPD"
    assert rows["R2"][5] == "Verwaltung"
    assert rows["R3"][5] == ""  # unbekannte ID: leeres Feld, keine Ausnahme
    # Ohne Zuordnung bleibt jedes Feld leer, die Struktur aber gleich
    plain = payload_with(_corpus(), _index(), [], version="0", generated_at=NOW)["documents"]
    assert isinstance(plain, list)
    assert all(doc[5] == "" and len(doc) == 6 for doc in plain)
