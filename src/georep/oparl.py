"""OParl 1.1 als Vertrag: die Objekte, die wir vom Ratsinformationssystem lesen.

Spezifikation: https://oparl.org/spezifikation/online-ansicht/ (Paper, File, Paginierung).
Validiert an der Systemgrenze, damit der Rest des Codes mit Typen statt mit ``.get()``-Ketten
arbeitet. Felder, die wir nicht brauchen, werden ignoriert; ``tests/fixtures/oparl`` hält eine
echte Antwort vom 2026-10-09 fest, und ein Test schlägt an, sobald der Server Schlüssel liefert,
die das Modell nicht kennt.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Oparl(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class OparlFile(_Oparl):
    """oparl:File. ``download_url`` ist der direkte Download, ``access_url`` die Ansicht."""

    id: str
    type: str | None = None
    name: str | None = None
    file_name: str | None = Field(default=None, alias="fileName")
    mime_type: str | None = Field(default=None, alias="mimeType")
    date: dt.date | None = None
    size: int | None = None
    sha1_checksum: str | None = Field(default=None, alias="sha1Checksum")
    sha512_checksum: str | None = Field(default=None, alias="sha512Checksum")
    access_url: str | None = Field(default=None, alias="accessUrl")
    download_url: str | None = Field(default=None, alias="downloadUrl")
    created: dt.datetime | None = None
    modified: dt.datetime | None = None
    deleted: bool = False


class OparlPaper(_Oparl):
    """oparl:Paper: Vorlage, Antrag, Anfrage. ``date`` ist das Datum der Vorlage."""

    id: str
    type: str | None = None
    body: str | None = None
    name: str | None = None
    reference: str | None = None
    date: dt.date | None = None
    paper_type: str | None = Field(default=None, alias="paperType")
    main_file: OparlFile | None = Field(default=None, alias="mainFile")
    auxiliary_file: list[OparlFile] = Field(default_factory=list, alias="auxiliaryFile")
    consultation: list[dict[str, Any]] = Field(default_factory=list)
    web: str | None = None
    created: dt.datetime | None = None
    modified: dt.datetime | None = None
    deleted: bool = False

    @property
    def primary_file(self) -> OparlFile | None:
        """``mainFile``, sonst die erste ``auxiliaryFile``; so hat es die Arbeit gehalten."""
        if self.main_file is not None:
            return self.main_file
        return self.auxiliary_file[0] if self.auxiliary_file else None

    @property
    def download_url(self) -> str | None:
        primary = self.primary_file
        return primary.download_url if primary is not None else None

    def in_period(self, start: dt.date, end: dt.date | None) -> bool:
        """Beide Grenzen einschließlich; ohne Ende (laufende Periode) ab ``start``; ohne Datum nie."""
        if self.date is None:
            return False
        return start <= self.date and (end is None or self.date <= end)


class Pagination(_Oparl):
    total_elements: int | None = Field(default=None, alias="totalElements")
    elements_per_page: int | None = Field(default=None, alias="elementsPerPage")
    current_page: int | None = Field(default=None, alias="currentPage")
    total_pages: int | None = Field(default=None, alias="totalPages")


class Links(_Oparl):
    first: str | None = None
    self_: str | None = Field(default=None, alias="self")
    next: str | None = None
    last: str | None = None


class PaperPage(_Oparl):
    """Eine Seite der Paper-Liste; ``links.next`` fehlt auf der letzten."""

    data: list[OparlPaper]
    pagination: Pagination | None = None
    links: Links = Links()


def known_aliases(model: type[BaseModel]) -> set[str]:
    """Die JSON-Schlüssel, die ein Modell versteht (Alias oder Feldname)."""
    return {field.alias or name for name, field in model.model_fields.items()}
