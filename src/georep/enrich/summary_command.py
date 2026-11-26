"""``georep summary``: Kurzfassungen lokal lesen, je Dokument oder als Liste für einen Vorlagenspiegel.

Vorhaben 20 (Messdokument § 6 „CLI", § 10 Punkt 5). Zwei Formen eines Befehls:

* ``georep summary <drucksache|id>``: die Kurzfassung eines Dokuments mit Modell, Digest,
  Prompt-Version und Treue (Zahl der Angaben, unbelegte je Klasse);
* ``georep summary --body <kürzel> --since <datum> [--html]``: alle Dokumente, die das Gremium
  beraten hat oder deren Nummer es nennt, ab dem Datum, nach Datum geordnet; mit ``--html`` als
  Datei unter ``cache_root/<profil>/summaries/``, **nie** unter ``site/`` (Frage 6 und 20.3).

Gelesen werden nur die Ausgaben des Schritts ``summaries``, der Korpus und die Gremien je Dokument;
der Befehl ruft kein Modell. Fehlt die Ausgabe, sagt er, wie sie entsteht.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import sys
from collections.abc import Sequence
from pathlib import Path

import polars as pl

from georep.enrich.fidelity import CLASSES, check, evidence
from georep.enrich.summaries import lexicon_for, summaries_dir, summaries_files, summary_inputs
from georep.errors import MissingInputError
from georep.layout import Layout
from georep.prep.bodies import BodyRules, merge_consultations, resolve_organizations
from georep.settings import Settings

CONSULTATION = "consultation_organizations"


def _date(text: str) -> dt.date:
    try:
        return dt.date.fromisoformat(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"kein Datum JJJJ-MM-TT: {text}") from error


def add_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    summary = sub.add_parser(
        "summary",
        help="Kurzfassungen lokal lesen: eines Dokuments, oder als Liste je Gremium (nie veröffentlicht)",
    )
    summary.add_argument("key", nargs="?", help="Drucksachennummer oder ID eines Dokuments")
    summary.add_argument("--body", help="Liste: Gremienkürzel, etwa BV6 oder RAT")
    summary.add_argument(
        "--since", type=_date, help="Liste: Dokumente ab diesem Datum (JJJJ-MM-TT)"
    )
    summary.add_argument(
        "--html",
        action="store_true",
        help="Liste zusätzlich als HTML-Datei unter cache_root/<profil>/summaries/",
    )


def _read_outputs(layout: Layout) -> pl.DataFrame:
    """Kurzfassungen und Treue je Dokument, über ``id`` verbunden; Bedienfehler, wenn sie fehlen."""
    files = summaries_files(layout)
    if not files.summaries.is_file():
        raise MissingInputError(
            f"{files.summaries} fehlt; die Kurzfassungen rechnet `georep run summaries --models`"
        )
    summaries = pl.read_parquet(files.summaries)
    fidelity = (
        pl.read_parquet(files.fidelity)
        if files.fidelity.is_file()
        else pl.DataFrame(schema={"id": pl.String})
    )
    return summaries.join(fidelity, on="id", how="left").sort("id")


def _corpus(layout: Layout) -> pl.DataFrame:
    return pl.read_parquet(
        layout.corpus, columns=["id", "reference", "date", "name", "paper_type", CONSULTATION]
    )


def _fidelity_line(row: dict[str, object]) -> str:
    if row.get("angaben") is None:
        return "Treue: nicht geprüft"
    parts = [f"{cls} {row[f'unbelegt_{cls}']}" for cls in CLASSES if row.get(f"unbelegt_{cls}")]
    found = f"{row['angaben']} Angaben"
    names = f"; Personennamen {row['personennamen']} (Regel 5)" if row.get("personennamen") else ""
    if not parts:
        ok = "ohne unbelegte Angabe" if row.get("ok") else "nicht bestanden (abgeschnitten)"
        return f"Treue: {found}, {ok}{names}"
    return f"Treue: {found}, unbelegt: {', '.join(parts)}{names}"


def _summary_text(row: dict[str, object]) -> str:
    text = row.get("text")
    if isinstance(text, str):
        return text + (" [abgeschnitten]" if row.get("abgeschnitten") else "")
    return f"(keine Kurzfassung: {row.get('grund') or 'nicht gerechnet'})"


def _head(row: dict[str, object]) -> str:
    day = row.get("date")
    when = day.strftime("%d.%m.%Y") if isinstance(day, dt.date) else "ohne Datum"
    return f"{row.get('reference') or row['id']} vom {when}: {row.get('name') or 'ohne Titel'}"


def flagged_lines(
    doc: str, row: dict[str, object], settings: Settings, layout: Layout
) -> list[str]:
    """Die beanstandeten Angaben und Personennamen, nachgerechnet aus Eingabe und Kurzfassung.

    Sie liegen in keiner Datei (sie sind Text der Kurzfassung, Messdokument § 6); die Eingabe
    entsteht wie im Schritt neu, das Lexikon aus dem Korpus (einige Sekunden).
    """
    text = row.get("text")
    flagged = any(row.get(f"unbelegt_{cls}") for cls in CLASSES) or row.get("personennamen")
    if not isinstance(text, str) or not flagged:
        return []
    try:
        entry = summary_inputs(settings, layout, [doc]).get(doc)
        lexicon = lexicon_for(settings, layout)
    except (FileNotFoundError, MissingInputError) as error:
        return [f"  Angaben nicht nachrechenbar: {error}"]
    if entry is None:
        return ["  Angaben nicht nachrechenbar: keine Eingabe"]
    result = check(text, bool(row.get("abgeschnitten")), evidence(entry.text, lexicon), lexicon)
    lines = [f"  unbelegt ({c.cls}/{c.kind}): {c.text}" for c in result.unsupported]
    return lines + [f"  Personenname (Regel 5): {name}" for name in result.persons]


def one_document(key: str, layout: Layout, settings: Settings) -> list[str]:
    """Die Zeilen zu einem Dokument, gefunden über die ID oder die Drucksachennummer."""
    corpus = _corpus(layout)
    wanted = key.strip()
    found = corpus.filter(
        (pl.col("id") == wanted)
        | (pl.col("reference").str.strip_chars().str.to_uppercase() == wanted.upper())
    )
    if found.is_empty():
        raise MissingInputError(f"kein Dokument mit ID oder Drucksache {key!r} im Korpus")
    rows = found.join(_read_outputs(layout), on="id", how="left").sort("date", "id")
    lines: list[str] = []
    for row in rows.iter_rows(named=True):
        lines.append(_head(row))
        if row.get("modell"):
            lines.append(
                f"Modell {row['modell']}, Digest {str(row.get('digest') or '')[:12]}, "
                f"Prompt {row.get('prompt')}"
            )
        lines.append(_summary_text(row))
        lines.append(_fidelity_line(row))
        lines += flagged_lines(row["id"], row, settings, layout)
        lines.append("")
    return lines[:-1]


def body_documents(
    body: str, since: dt.date | None, layout: Layout, settings: Settings
) -> pl.DataFrame:
    """Die Dokumente eines Gremiums: Gremium der Nummer oder in der Beratungsfolge, ab ``since``."""
    corpus = _corpus(layout)
    extra = (
        pl.read_parquet(layout.consultations, columns=["id", CONSULTATION])
        if settings.bodies.consultations is not None and layout.consultations.is_file()
        else None
    )
    folge = dict(merge_consultations(corpus.select("id", CONSULTATION), extra).iter_rows())
    own = (
        dict(pl.read_parquet(layout.papers_bodies, columns=["id", "gremium"]).iter_rows())
        if layout.papers_bodies.is_file()
        else {}
    )
    mapping = BodyRules.from_settings(settings.bodies).organizations
    code = body.strip().upper()
    ids = [
        doc
        for doc in corpus.get_column("id").to_list()
        if own.get(doc) == code or code in resolve_organizations(folge.get(doc) or [], mapping)
    ]
    chosen = corpus.filter(pl.col("id").is_in(ids))
    if since is not None:
        chosen = chosen.filter(pl.col("date") >= since)
    return chosen.join(_read_outputs(layout), on="id", how="left").sort("date", "reference", "id")


def list_lines(frame: pl.DataFrame) -> list[str]:
    lines: list[str] = []
    for row in frame.iter_rows(named=True):
        lines += [_head(row), "  " + _summary_text(row), "  " + _fidelity_line(row)]
    return lines


def _html_item(row: dict[str, object]) -> str:
    head, text, check = (html.escape(f(row)) for f in (_head, _summary_text, _fidelity_line))
    return f"<li><p><strong>{head}</strong></p><p>{text}</p><p><small>{check}</small></p></li>"


def list_html(frame: pl.DataFrame, body: str, since: dt.date | None) -> str:
    """Eine Seite ohne Fremdressourcen; sie bleibt lokal und nennt das im Kopf."""
    title = f"Kurzfassungen {body}" + (f" ab {since.strftime('%d.%m.%Y')}" if since else "")
    items = "\n".join(_html_item(row) for row in frame.iter_rows(named=True))
    return (
        '<!doctype html>\n<html lang="de">\n<head><meta charset="utf-8">'
        f"<title>{html.escape(title)}</title></head>\n<body>\n<h1>{html.escape(title)}</h1>\n"
        "<p>Lokal erzeugt mit einem Sprachmodell, nicht geprüft und nicht zur Veröffentlichung "
        "bestimmt.</p>\n"
        f"<ol>\n{items}\n</ol>\n</body>\n</html>\n"
    )


def html_path(layout: Layout, body: str, since: dt.date | None) -> Path:
    stamp = since.isoformat() if since else "alle"
    return summaries_dir(layout) / f"vorlagenspiegel-{body.strip().upper()}-{stamp}.html"


def run(args: argparse.Namespace, settings: Settings, layout: Layout) -> int:
    if (args.key is None) == (args.body is None):
        print("Fehler: entweder <drucksache|id> oder --body", file=sys.stderr)
        return 2
    if args.key is not None:
        print("\n".join(one_document(args.key, layout, settings)))
        return 0
    frame = body_documents(args.body, args.since, layout, settings)
    lines: Sequence[str] = list_lines(frame)
    print("\n".join(lines) if lines else f"keine Dokumente für {args.body}")
    if args.html:
        target = html_path(layout, args.body, args.since)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(list_html(frame, args.body, args.since), encoding="utf-8")
        print(f"HTML: {target}")
    return 0
