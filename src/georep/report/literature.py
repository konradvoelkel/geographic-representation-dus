"""Die Literaturübersicht der Seite: stadtneutrale Einträge aus ``literatur.toml``, Stadt aus dem Profil.

``docs/todo.md``, Punkt 5; Gründe in ``docs/decisions.md``, Punkt 47. Die Einträge sind Daten, nicht
Vorlage: ``literatur.toml`` liegt neben diesem Modul im Paket und trägt, was für jede Kommune gilt
(der Standard, über den die Dokumente kommen, und die Projekte, die kommunale Ratsdokumente vor
diesem Vorhaben durchsuchbar gemacht haben). Was nur für eine Stadt zählt -- die Arbeit, auf der ihre
Seite aufsetzt -- steht als ``[[report.literature]]`` in ihrem Profil, damit eine zweite Stadt die
allgemeinen Einträge erbt, ohne sie zu kopieren.
"""

from __future__ import annotations

import tomllib
from importlib import resources
from importlib.resources.abc import Traversable
from typing import Any

import deal
from pydantic import ValidationError

from georep.errors import SchemaError
from georep.settings import LiteratureEntry, Settings

FILE = "literatur.toml"
TABLE = "literature"


def _keys_are_unique(result: tuple[LiteratureEntry, ...]) -> bool:
    return len({entry.key for entry in result}) == len(result)


@deal.post(_keys_are_unique, message="jeder Schlüssel einmal; er wird zur Anker-ID der Seite")
@deal.raises(SchemaError)
def package_literature(folder: Traversable | None = None) -> tuple[LiteratureEntry, ...]:
    """Die stadtneutralen Einträge in der Reihenfolge der Datei. ``folder`` ist die Testnaht."""
    if folder is None:
        folder = resources.files("georep.report")
    try:
        payload = tomllib.loads((folder / FILE).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SchemaError(f"{FILE} nicht lesbar: {error}") from error
    rows: Any = payload.get(TABLE, [])
    if not isinstance(rows, list):
        raise SchemaError(f"{FILE}: [[{TABLE}]] muss eine Liste von Tabellen sein")
    try:
        return tuple(LiteratureEntry.model_validate(row) for row in rows)
    except ValidationError as error:
        raise SchemaError(f"{FILE}: {error}") from error


@deal.raises(SchemaError)
def literature(
    settings: Settings, folder: Traversable | None = None
) -> tuple[LiteratureEntry, ...]:
    """Erst die Einträge des Profils, dann die der Paketdatei, je in ihrer eigenen Reihenfolge.

    Die Arbeit zur Stadt ist der Ursprung dieser Seite und steht darum oben; die allgemeinen
    Einträge folgen. Ein doppelter Schlüssel ist ein Fehler, denn er wird zur Anker-ID: ein Profil,
    das einen Paketeintrag ersetzen will, braucht einen eigenen Schlüssel.
    """
    found = tuple(settings.report.literature) + package_literature(folder)
    keys = [entry.key for entry in found]
    if len(set(keys)) != len(keys):
        doubled = sorted({key for key in keys if keys.count(key) > 1})
        raise SchemaError(f"literature: Schlüssel doppelt in Profil und {FILE}: {doubled}")
    return found
