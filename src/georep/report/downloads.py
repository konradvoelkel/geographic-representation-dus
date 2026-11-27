"""Downloads der Vorverarbeitung mit Prüfsatz und ohne Namen (Vorhaben 11 und 12, Stufe 3).

Stufe 3 von Vorhaben 11 (Kopf je Dokument) und 12 (Kennungen und Beträge) ist je eine Zeile in den
Downloads der Hauptseite, keine Unterseite (Messdokumente ``docs/plans/11-struktur.md`` und
``docs/plans/12-kennungen.md``, § 7). Was beide brauchen, steht hier; was jede Tabelle zeigt und
sagt, steht bei ihrem Beitrag (``enrich.sections``, ``enrich.identifiers``).

* **Wo.** Ein Download erscheint nur in einem Datensatz, an dem gemessen ist (``measured``: sein
  Ordner ist der eines Profils aus ``stichprobe.json``, wie bei ``akteure.html``), und nur, wenn
  die Tabelle Zeilen aus einem Rohtext hat (``has_extracted_rows``). Auf GitHub Pages ist das die
  Hauptperiode; die anderen Profile haben dort keinen Rohtext (``docs/plan-zeigen-2026-11.md``,
  § 6). Lokal haben sie ihn, aber ihr Kopf ist nicht gemessen, und in 2014 bis 2020 läuft er oft in
  das Feld der Dezernentin oder des Dezernenten und in Textreste hinein.
* **Ohne Namen.** ``named`` erkennt einen Wert, in dem hinter einem Titel aus
  ``report.names.person_titles`` ein groß geschriebenes Wort beginnt. Die Sicht einer Tabelle
  leert solche Werte oder lässt solche Spannen weg; eine Nachbedingung prüft, dass danach keiner
  mehr übrig ist.
* **Der Prüfsatz.** Der Satz aus ``guete.json`` (Modelle, Einheiten, „nicht von Menschen") und die
  Zahlen des Regelwerks gegen die Endlabels, die ``guete.json`` nicht trägt (``LabelCheck``, wie
  ``RULE_CHECK`` von 15). ``read_quality`` bricht ab, wenn ``guete.json`` eine andere Kodierung
  beschreibt als die, an der die Zahlen gemessen sind; die slow-Tests rechnen sie aus den Labels
  im Repo nach.

Kein Stadtwort im Code: Titel, Muster und Profile kommen aus den Settings und aus ``validierung/``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from georep.errors import MissingInputError, SchemaError
from georep.settings import Settings, profile_folder
from georep.validation.measures import wilson_interval

QUALITY = "guete.json"
SAMPLE = "stichprobe.json"


# --- Wo ein Download erscheint ------------------------------------------------------------------
def measured(settings: Settings, project: str) -> bool:
    """Ob dieser Datensatz zur Stichprobe von ``project`` gehört (ihr Profil oder sein Ordner).

    Das Vergleichsprofil rechnet im Ordner der Hauptperiode und ist damit gemessen, eine Periode
    oder eine zweite Stadt nicht. ``MissingInputError``, wenn ``stichprobe.json`` fehlt; ein
    Profil, das es im Paket nicht gibt, ist ein Fehler (``UnknownProfileError``), kein stilles
    „nicht gemessen": sonst verschwände ein Download nach einem Tippfehler ohne Meldung.
    """
    path = settings.validation.root / project / SAMPLE
    if not path.is_file():
        raise MissingInputError(f"{path} fehlt; ein Download nennt, wo er gemessen ist")
    sample: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    try:
        profiles = [p.strip() for p in str(sample["profil"]).split(",") if p.strip()]
    except KeyError as error:
        raise SchemaError(f"{path}: Feld profil fehlt") from error
    return settings.profile in {profile_folder(name) for name in profiles}


def has_extracted_rows(path: Path) -> bool:
    """Ob die Tabelle eine Zeile aus einem Rohtext hat (``extractor`` gesetzt); ohne Rohtext nicht."""
    found = pl.scan_parquet(path).select(pl.col("extractor").is_not_null().any()).collect()
    return bool(found.item())


# --- Ohne Namen ---------------------------------------------------------------------------------
def named(settings: Settings) -> str:
    """Das Muster eines Werts mit Namen: ein Titel, Leerraum oder ein Doppelpunkt, ein Großbuchstabe.

    „Beigeordneter Hans …", „Stadtkämmerin…" ohne Leerraum, „Dezernentin: …", „Frau …"; nicht
    „Büro Oberbürgermeister" (nichts dahinter) und nicht „Stadtdirektor und Dezernat …".
    """
    return rf"(?:{settings.report.names.person_titles})\s*(?::\s*)?[A-ZÄÖÜ]"


def is_named(column: pl.Expr, pattern: str) -> pl.Expr:
    """Wahr, wo der Text einen Namen trägt; ein leerer Wert trägt keinen."""
    return column.str.contains(pattern).fill_null(False)


def without_name(column: str, pattern: str) -> pl.Expr:
    """Die Spalte, leer, wo ihr Wert einen Namen trägt."""
    return (
        pl.when(is_named(pl.col(column), pattern))
        .then(None)
        .otherwise(pl.col(column))
        .alias(column)
    )


def names_in(frame: pl.DataFrame, pattern: str) -> list[str]:
    """Die Spalten mit Text (auch in Listen von Strukturen), in denen noch ein Wert einen Namen trägt."""

    def any_named(table: pl.DataFrame, column: str) -> bool:
        return bool(table.select(is_named(pl.col(column), pattern).any()).item())

    found: list[str] = []
    for column, dtype in frame.schema.items():
        if dtype == pl.String:
            found += [column] if any_named(frame, column) else []
        elif isinstance(dtype, pl.List) and isinstance(dtype.inner, pl.Struct):
            inner = frame.select(pl.col(column).explode()).unnest(column)
            found += [
                f"{column}.{c}"
                for c, inner_type in inner.schema.items()
                if inner_type == pl.String and any_named(inner, c)
            ]
    return found


# --- Der Prüfsatz -------------------------------------------------------------------------------
def _de(share: float) -> str:
    return f"{share:.3f}".replace(".", ",")


@dataclass(frozen=True)
class Measure:
    """Ein Maß des Regelwerks gegen die Endlabels: ein Anteil mit 95-%-Intervall an ``units``.

    Ungewichtet trägt es seine Treffer (``hits``), und das Intervall ist das nach Wilson; gewichtet
    (nach Schicht, Wilson mit dem effektiven n nach Kish) trägt es Anteil und Intervall, wie das
    Messskript sie rechnet.
    """

    label: str
    units: int
    hits: int | None = None
    share: float | None = None
    interval: tuple[float, float] | None = None

    def bounds(self) -> tuple[float, float, float]:
        """Anteil, untere und obere Grenze."""
        if self.hits is not None:
            low, high = wilson_interval(self.hits, self.units)
            return self.hits / self.units, low, high
        if self.share is None or self.interval is None:
            raise SchemaError(f"{self.label}: ein gewichtetes Maß braucht Anteil und Intervall")
        return self.share, *self.interval

    def text(self) -> str:
        """„Amt 125 von 125 (0,970–1,000)" oder „Betrag 0,962 (0,885–0,988; n 100)"."""
        share, low, high = self.bounds()
        if self.hits is not None:
            return f"{self.label} {self.hits} von {self.units} ({_de(low)}–{_de(high)})"
        return f"{self.label} {_de(share)} ({_de(low)}–{_de(high)}; n {self.units})"


@dataclass(frozen=True)
class LabelCheck:
    """Die Zahlen einer Kodierung, die ``guete.json`` nicht trägt, und an welcher sie gemessen sind."""

    project: str  # der Ordner unter ``validation.root``
    codebook_version: str  # beide vergleicht ``read_quality`` mit ``guete.json``
    units: int
    measures: tuple[Measure, ...]


@dataclass(frozen=True)
class Quality:
    """Was ``guete.json`` über die Kodierung sagt, soweit der Prüfsatz es braucht."""

    sentence: str  # ``satz``: Modelle, Einheiten, „nicht von Menschen"
    one_model: bool  # Kodierer A, B und die Schlichtung sind dasselbe Modell
    disputed: int  # Einheiten, bei denen A und B uneinig waren

    def text(self) -> str:
        """Der Satz, und wo es eine Schlichtung gab und ``satz`` sie nicht nennt, wer schlichtete.

        ``validation.merge.sentence`` nennt die Schlichtung nur, wenn ihr Modell ein anderes ist;
        das Messdokument 12 will an der Tabelle auch sagen, dass es dasselbe war (§ 7).
        """
        if self.one_model and self.disputed:
            return f"{self.sentence}, geschlichtet von demselben Modell"
        return self.sentence


def check_files(settings: Settings, *checks: LabelCheck) -> tuple[Path, ...]:
    """``guete.json`` und ``stichprobe.json`` je Kodierung, im Repo unter ``validation.root``."""
    return tuple(
        settings.validation.root / check.project / name
        for check in checks
        for name in (QUALITY, SAMPLE)
    )


def read_quality(settings: Settings, check: LabelCheck) -> Quality:
    """Satz und Modelle aus ``guete.json``; ``SchemaError``, wenn sie eine andere Kodierung beschreibt.

    Wie ``report.actors.read_check`` (Review 2026-11-27, N1): eine neue Kodierung mit anderem
    Codebuch oder anderer Zahl der Einheiten macht die Zahlen in ``check`` ungültig, und die Seite
    schriebe sonst einen neuen Satz neben alte Zahlen.
    """
    path = settings.validation.root / check.project / QUALITY
    if not path.is_file():
        raise MissingInputError(f"{path} fehlt; ein Download nennt seine Prüfung")
    quality: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    try:
        sentence = str(quality["satz"])
        models = dict(quality["modelle"])
        disputed = int(quality["uneinig"])
        measured_on = (str(quality["codebuch_version"]), int(quality["einheiten"]))
        roles = {models["kodierer_a"], models["kodierer_b"], models["schlichtung"]}
    except (KeyError, TypeError, ValueError) as error:
        raise SchemaError(f"{path}: Feld fehlt ({error})") from error
    if measured_on != (check.codebook_version, check.units):
        raise SchemaError(
            f"{path}: Codebuch {measured_on[0]} an {measured_on[1]} Einheiten, die Zahlen gelten "
            f"für {check.codebook_version} an {check.units}; das Regelwerk ist gegen die neue "
            "Kodierung nachzurechnen"
        )
    return Quality(sentence, len(roles) == 1, disputed)


def capitalized(text: str) -> str:
    """Der Satz aus ``guete.json`` beginnt klein („geprüft von …"); unter den Downloads groß."""
    return text[:1].upper() + text[1:]
