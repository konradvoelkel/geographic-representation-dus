"""Vorhaben 18: der Rohtext eines Dokuments in Stücke, die in das Fenster des Einbettungsmodells passen.

Fassung ``18-stuecke-1`` aus der Messung (``docs/plans/18-einbettungen.md``, § 3.1 und § 3.2): die
Zeilen des Rohtexts (ohne Zeilen aus Leerraum) werden der Reihe nach zu Stücken gepackt, deren
Rumpf höchstens ``chunk_chars − len(Titel) − 2`` Zeichen hat; eine Zeile über diesem Budget wird an
der letzten Leerstelle davor geteilt, ohne Leerstelle hart. Das nächste Stück beginnt mit den
letzten Zeilen des vorigen, die zusammen höchstens ``overlap_chars`` Zeichen haben, und nimmt
mindestens eine neue Zeile auf. Ein Seitenwechsel (``\\f``) trennt Zeilen wie ein Zeilenumbruch.

``split_chunks`` ist das ``zerteile`` des Messskripts (``docs/plans/18-einbettungen-messung.py``)
mit denselben Schleifen; die Rümpfe sind Zeichen für Zeichen dieselben, und darum trifft ein Lauf
die Vektoren der Messung im Modellcache. Neu ist nur, dass jedes Stück seine Stelle im Rohtext
kennt (``start``, ``end``): jede Zeile ist ein zusammenhängendes Stück des Rohtexts, also auch der
Bereich von der ersten bis zur letzten Zeile eines Stücks. Gegen eine wörtliche Kopie des
Messskripts geprüft (``tests/property/oracle_chunks.py``, hypothesis) und über die Hauptperiode
(47 407 Stücke, ``tests/unit/test_search_slow.py``).

Alles hier ist rein und kennt keine Settings; die Budgets kommen als Zahlen.
"""

from __future__ import annotations

from typing import NamedTuple

import deal

# Das Trennzeichen zwischen Titel und Rumpf eines Stücks; die Messung zählt es als zwei Zeichen.
TITLE_SEPARATOR = "\n\n"


class Chunk(NamedTuple):
    """Ein Stück: der Rumpf (Zeilen mit ``\\n`` verbunden) und sein Bereich im Rohtext, halboffen."""

    body: str
    start: int
    end: int


@deal.pre(lambda name, title_chars: title_chars >= 0)
@deal.ensure(lambda name, title_chars, result: len(result) <= title_chars)
@deal.ensure(lambda name, title_chars, result: "  " not in result and result == result.lstrip())
@deal.safe
def chunk_title(name: str | None, title_chars: int) -> str:
    """Der Titel eines Stücks: OParl ``name``, Leerraum zusammengezogen, höchstens ``title_chars``.

    Wie ``titel_von`` der Messung: abgeschnitten wird nach dem Zusammenziehen, ein Leerzeichen am
    Schnitt bleibt stehen (es steht so in den Stücken, deren Vektoren im Modellcache liegen).
    """
    return " ".join((name or "").split())[:title_chars]


def _lines_hold(raw: str, budget: int, result: list[tuple[int, int]]) -> bool:
    """Jede Zeile liegt im Rohtext, ist nicht leer, höchstens ``budget`` lang, und sie folgen aufeinander."""
    ends = [0, *(end for _, end in result)]
    return all(
        prev <= start < end <= len(raw) and end - start <= budget and raw[start:end].strip() != ""
        for prev, (start, end) in zip(ends, result, strict=False)
    )


@deal.pre(lambda raw, budget: budget >= 1, message="ein Budget von mindestens einem Zeichen")
@deal.ensure(_lines_hold, message="Zeilen im Rohtext, nicht leer, im Budget, in Folge")
@deal.safe
def chunk_lines(raw: str, budget: int) -> list[tuple[int, int]]:
    """Die Zeilen des Rohtexts als Bereiche ``(start, end)``, je höchstens ``budget`` Zeichen.

    Das ``zeilen_von`` der Messung: ``\\f`` und ``\\n`` trennen, rechts gekürzt, Zeilen aus Leerraum
    fallen weg, und eine Zeile über dem Budget wird an der letzten Leerstelle vor dem Budget geteilt
    (ohne Leerstelle hart); das Stück davor wird rechts, der Rest links gekürzt. ``raw[start:end]``
    ist genau die Zeile, die die Messung bildet.
    """
    spans: list[tuple[int, int]] = []
    position = 0
    for piece in raw.replace("\f", "\n").split("\n"):
        begin = position
        position += len(piece) + 1
        line = piece.rstrip()
        if not line.strip():
            continue
        while len(line) > budget:
            cut = line.rfind(" ", 0, budget + 1)
            if cut <= 0:
                cut = budget
            head = line[:cut].rstrip()
            if head.strip():
                spans.append((begin, begin + len(head)))
            rest = line[cut:]
            line = rest.lstrip()
            begin += cut + len(rest) - len(line)
        if line.strip():
            spans.append((begin, begin + len(line)))
    return spans


def _budget(title: str, chunk_chars: int) -> int:
    return chunk_chars - len(title) - len(TITLE_SEPARATOR)


def _chunks_hold(
    title: str, raw: str, chunk_chars: int, overlap_chars: int, result: list[Chunk]
) -> bool:
    """Jeder Rumpf im Budget, Bereiche im Rohtext, Anfänge und Enden streng steigend."""
    budget = _budget(title, chunk_chars)
    return (
        all(0 <= c.start < c.end <= len(raw) and len(c.body) <= budget for c in result)
        and all(
            a.start < b.start and a.end < b.end for a, b in zip(result, result[1:], strict=False)
        )
        and (len(result) > 0) == (raw.strip() != "")
    )


@deal.pre(
    lambda title, raw, chunk_chars, overlap_chars: (
        _budget(title, chunk_chars) >= 1 and overlap_chars >= 0
    ),
    message="der Titel lässt dem Rumpf mindestens ein Zeichen, die Überlappung ist nicht negativ",
)
@deal.ensure(_chunks_hold, message="Rümpfe im Budget, Bereiche im Rohtext und in Folge")
@deal.safe
def split_chunks(title: str, raw: str, chunk_chars: int, overlap_chars: int) -> list[Chunk]:
    """Die Stücke eines Rohtexts nach ``18-stuecke-1``; leer genau dann, wenn er nur Leerraum ist.

    Die Schleifen des ``zerteile`` der Messung; ``size`` ist ihr ``_laenge`` (Zeichen der Zeilen
    plus je ein Zeilenumbruch dazwischen), über Präfixsummen statt Teilsummen gerechnet.
    """
    budget = _budget(title, chunk_chars)
    spans = chunk_lines(raw, budget)
    prefix = [0]
    for start, end in spans:
        prefix.append(prefix[-1] + end - start)

    def size(first: int, stop: int) -> int:
        return prefix[stop] - prefix[first] + max(0, stop - first - 1)

    chunks: list[Chunk] = []
    first = 0
    while first < len(spans):
        stop = first + 1
        while stop < len(spans) and size(first, stop + 1) <= budget:
            stop += 1
        body = "\n".join(raw[start:end] for start, end in spans[first:stop])
        chunks.append(Chunk(body, spans[first][0], spans[stop - 1][1]))
        if stop >= len(spans):
            break
        again = stop
        while again - 1 > first and size(again - 1, stop) <= overlap_chars:
            again -= 1
        while size(again, stop + 1) > budget:
            again += 1
        first = again
    return chunks


@deal.ensure(lambda prefix, title, body, result: result.endswith(body))
@deal.ensure(
    lambda prefix, title, body, result: len(result) == len(prefix) + len(title) + 2 + len(body)
)
@deal.safe
def chunk_text(prefix: str, title: str, body: str) -> str:
    """Was das Modell von einem Stück sieht: Präfix des Modells, Titel, Leerzeile, Rumpf."""
    return prefix + title + TITLE_SEPARATOR + body
