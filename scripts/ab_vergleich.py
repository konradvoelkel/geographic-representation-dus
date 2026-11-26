"""A/B-Vergleich zweier Seitenbauten wie in docs/decisions.md, Punkt 66 (Anleitung: scripts/README.md).

Aufruf: ``uv run python -I scripts/ab_vergleich.py <a> <b>``, je ein Ordner, etwa die beiden
``data/site`` oder die beiden ``data`` aus ``scripts/ab_bau.sh``. Exit 0, wenn alles gleich ist,
sonst 1 und je Abweichung eine Zeile.

Parquet wird als Frame verglichen (die Bytes tragen den Schreiber), alles andere byteweise;
herausgerechnet sind ``generated_at`` und ``generated`` in JSON, die Zeile „Erzeugt am" in HTML und
die SHA-256-Spalte der Download-Tabelle (sie hängt an ``generated_at``). Ein Stamp trägt seine
Schreibzeit und weicht im Vergleich zweier Datenwurzeln darum immer ab.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import polars as pl

HASH = re.compile(r"<code>[0-9a-f]{64}</code>")


def _json(data: bytes) -> object:
    def strip(node: object) -> object:
        if isinstance(node, dict):
            return {k: strip(v) for k, v in node.items() if k not in ("generated_at", "generated")}
        if isinstance(node, list):
            return [strip(v) for v in node]
        return node

    return strip(json.loads(data))


def _html(data: bytes) -> list[str]:
    lines = data.decode("utf-8").split("\n")
    return [HASH.sub("<code>HASH</code>", line) for line in lines if "Erzeugt am" not in line]


def _same(a: Path, b: Path, rel: Path) -> bool:
    da, db = (a / rel).read_bytes(), (b / rel).read_bytes()
    if da == db:
        return True
    if rel.suffix == ".parquet":
        return pl.read_parquet(a / rel).equals(pl.read_parquet(b / rel))
    if rel.suffix == ".json":
        return _json(da) == _json(db)
    if rel.suffix == ".html":
        return _html(da) == _html(db)
    return False


def main(a: Path, b: Path) -> int:
    files_a = {p.relative_to(a) for p in a.rglob("*") if p.is_file()}
    files_b = {p.relative_to(b) for p in b.rglob("*") if p.is_file()}
    differ = [
        f"nur in {'A' if rel in files_a else 'B'}: {rel}" for rel in sorted(files_a ^ files_b)
    ]
    differ += [f"anders: {rel}" for rel in sorted(files_a & files_b) if not _same(a, b, rel)]
    print(f"{len(files_a)} Dateien in A, {len(files_b)} in B, {len(differ)} Abweichungen")
    for line in differ:
        print(line)
    return 1 if differ else 0


if __name__ == "__main__":
    if len(sys.argv) != 3 or not all(Path(arg).is_dir() for arg in sys.argv[1:]):
        print(f"Aufruf: {sys.argv[0]} <ordner_a> <ordner_b>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
