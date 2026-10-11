"""Interne Datensätze: was aus den Quellen gespeichert wird, als Vertrag.

``PaperRecord`` ist die Zeile in ``raw/papers.jsonl`` und die Metadatenhälfte von ``papers.parquet``;
sie entsteht aus einem OParl-Paper (``from_oparl``) oder aus dem Altformat der Arbeit (``from_legacy``).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict

from georep.oparl import OparlPaper


class PaperRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str | None = None
    reference: str | None = None
    date: dt.date | None = None
    paper_type: str | None = None
    main_file: str | None = None
    file_name: str | None = None
    download_url: str | None = None
    modified: dt.datetime | None = None

    @classmethod
    def from_oparl(cls, paper: OparlPaper) -> PaperRecord:
        primary = paper.primary_file
        return cls(
            id=paper.id,
            name=paper.name,
            reference=paper.reference,
            date=paper.date,
            paper_type=paper.paper_type,
            main_file=primary.id if primary else None,
            file_name=file_name_from(
                primary.download_url if primary else None, primary.file_name if primary else None
            ),
            download_url=primary.download_url if primary else None,
            modified=paper.modified,
        )

    @classmethod
    def from_legacy(cls, item: dict[str, Any]) -> PaperRecord:
        """Eintrag aus ``paper_objects.json`` oder ``paper_with_text.json`` der Arbeit."""
        url = item.get("download_url") or None
        return cls(
            id=str(item["id"]),
            name=item.get("name") or None,
            reference=item.get("reference") or None,
            date=dt.date.fromisoformat(item["date"]) if item.get("date") else None,
            paper_type=item.get("paperType") or None,
            main_file=item.get("mainFile") or None,
            file_name=file_name_from(url, None),
            download_url=url,
        )


def file_name_from(download_url: str | None, file_name: str | None) -> str | None:
    """Der Dateiname, unter dem PDF und Text liegen: wie die Arbeit der letzte Teil der URL."""
    if download_url:
        tail = download_url.rsplit("/", 1)[-1]
        if tail:
            return tail
    return file_name or None
