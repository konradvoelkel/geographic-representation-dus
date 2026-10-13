"""Zerlegt ``site/index.html`` in ihre Posten (`seitengroesse-2026-10.md`, § 1 und § 5).

    uv run python docs/seitengroesse-2026-10-messung.py [pfad/zur/index.html]

Ohne Argument nimmt das Skript ``site/index.html`` unter dem ``data_root`` der Settings. Liest
nur, schreibt nichts, braucht weniger als eine Sekunde.

Die Zahlen des Dokuments stehen damit zum Nachrechnen bereit: Bytes je ``<section>``, je
``<table>``, je ``<svg>``, je ``<script>``, dazu die Hebel, über die § 5 entscheidet (doppelte
Pfade, Nachkommastellen, Leerraum zwischen Tags). Was ein Test festhält, steht im Test (das Budget
der Seite in ``tests/golden/test_pipeline.py``); dieses Skript ist für die Zerlegung daneben, die
kein Test tragen soll -- sie ändert sich mit jedem Abschnitt.
"""

from __future__ import annotations

import gzip
import re
import sys
from collections import Counter
from pathlib import Path

from georep.settings import load_settings


def spans(text: str, tag: str) -> list[tuple[int, int, str]]:
    """Alle ``(Anfang, Ende, Kopf)`` eines Tags; verschachtelte zählen zum äußeren."""
    opener = re.compile(rf"<{tag}\b[^>]*>")
    closer = f"</{tag}>"
    found: list[tuple[int, int, str]] = []
    position = 0
    while True:
        start = opener.search(text, position)
        if start is None:
            return found
        depth, cursor = 1, start.end()
        while depth:
            nested = opener.search(text, cursor)
            closing = text.find(closer, cursor)
            if closing == -1:
                return found
            if nested is not None and nested.start() < closing:
                depth, cursor = depth + 1, nested.end()
            else:
                depth, cursor = depth - 1, closing + len(closer)
        found.append((start.start(), cursor, start.group(0)))
        position = cursor


def size(text: str) -> int:
    return len(text.encode("utf-8"))


def ident(head: str) -> str:
    found = re.search(r'id="([^"]+)"', head)
    return found.group(1) if found else "?"


def report_sections(text: str) -> None:
    sections = spans(text, "section")
    print(f"\n== {len(sections)} Abschnitte (Bytes, davon Tabellen/SVG/Skript)")
    rest = size(text)
    for start, end, head in sections:
        inner = text[start:end]
        parts = {
            tag: sum(size(inner[s:e]) for s, e, _ in spans(inner, tag))
            for tag in ("table", "svg", "script")
        }
        rest -= size(inner)
        detail = ", ".join(f"{tag} {value}" for tag, value in parts.items() if value)
        print(f"  {ident(head):22s} {size(inner):8d}  {detail}")
    print(f"  {'(Rahmen, Kopf, Fuß)':22s} {rest:8d}")


def report_elements(text: str) -> None:
    for tag in ("svg", "script", "style"):
        found = spans(text, tag)
        total = sum(size(text[s:e]) for s, e, _ in found)
        print(f"\n== {len(found)} <{tag}>: {total} Byte")
        for s, e, head in sorted(found, key=lambda f: -size(text[f[0] : f[1]])):
            print(f"  {size(text[s:e]):8d}  {head[:76]}")
    tables = spans(text, "table")
    print(f"\n== {len(tables)} <table>: {sum(size(text[s:e]) for s, e, _ in tables)} Byte")
    sections = [(s, e, ident(h)) for s, e, h in spans(text, "section")]
    for s, e, head in tables:
        rows = text[s:e].count("<tr")
        if rows > 10:  # die Kandidaten für die Vorschau
            where = next((name for a, b, name in sections if a < s < b), "?")
            print(f"  {where:20s} {rows:4d} Zeilen {size(text[s:e]):8d} Byte  {ident(head)}")


def report_levers(text: str) -> None:
    """Die Hebel aus § 5: doppelte Pfade, Nachkommastellen, Leerraum zwischen Tags."""
    print("\n== Hebel")
    paths = Counter(re.findall(r'\sd="([^"]*)"', text))
    twice = sum(size(d) * (n - 1) for d, n in paths.items() if n > 1)
    print(f"  doppelte d-Attribute: {sum(1 for n in paths.values() if n > 1)} Pfade, {twice} Byte")
    decimals = Counter(len(d) for d in re.findall(r"-?\d+\.(\d+)", " ".join(paths)))
    print(f"  Nachkommastellen in den Pfaden: {dict(sorted(decimals.items()))}")
    coordinates = sum(n for places, n in decimals.items() if places >= 2)
    print(f"  eine Stelle weniger je Koordinate: {coordinates} Byte je Vorkommen")
    values = re.findall(r'data-value(?:-[a-z]+)?="([^"]*)"', text)
    long = [v for v in values if len(v) > 10]
    cut = sum(len(v) - 10 for v in long)
    print(
        f"  {len(values)} data-value, {sum(size(v) for v in values)} Byte; "
        f"{len(long)} länger als zehn Zeichen, zusammen {cut} Byte darüber"
    )
    circles = re.findall(r"<circle\b[^>]*>(?:<title>[^<]*</title></circle>)?", text)
    titles = re.findall(r"<circle\b[^>]*><title>([^<]*)</title></circle>", text)
    print(
        f"  {len(circles)} <circle> der Orte: {sum(size(c) for c in circles)} Byte, "
        f"davon {sum(size(t) + len('<title></title>') for t in titles)} die <title>"
    )
    markup = []
    blocked = sorted((s, e) for tag in ("script", "style") for s, e, _ in spans(text, tag))
    position = 0
    for s, e in blocked:
        markup.append(text[position:s])
        position = e
    markup.append(text[position:])
    between = re.findall(r">(\s+)<", "".join(markup))
    whitespace = sum(size(w) for w in between)
    print(
        f"  Leerraum zwischen Tags (ohne script/style): {whitespace} Byte in "
        f"{len(between)} Stellen, {whitespace / size(text):.2%} der Seite"
    )


def main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    packed = len(gzip.compress(text.encode("utf-8"), 9))
    print(f"{path}: {size(text)} Byte, gzip {packed} Byte")
    report_sections(text)
    report_elements(text)
    report_levers(text)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(Path(sys.argv[1]))
    else:
        settings = load_settings()
        main(settings.data_root / settings.profile / "site" / "index.html")
