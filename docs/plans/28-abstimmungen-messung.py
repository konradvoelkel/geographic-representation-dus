"""Vorhaben 28, Stufe 1: was die Texte über Abstimmungen hergeben (docs/plans/28-abstimmungen.md).

Aufrufe, im Worktree mit seinem Venv (UV_PROJECT_ENVIRONMENT) und dem Profil der Hauptperiode:

    uv run python docs/plans/28-abstimmungen-messung.py abruf      # die 50 Niederschriften, einmal, Netz
    uv run python docs/plans/28-abstimmungen-messung.py messen     # alle Zahlen des Messdokuments, offline
    uv run python docs/plans/28-abstimmungen-messung.py population # Grundgesamtheit der Kodierung
    uv run python docs/plans/28-abstimmungen-messung.py auftraege  # Aufträge A und B nach F4, lokal
    uv run python docs/plans/28-abstimmungen-messung.py guete      # Präzision gegen die Labels

Liest die F6-Dateien unter ``data_root/<profil>/raw/`` (``georep.council.council_files``), den Korpus
und ``dokumente_urheber.parquet`` des Laufs und die Niederschriften unter ``MESSDATEN``. Schreibt nichts
ins Repo außer, mit ``population``, die Grundgesamtheit der Kodierung in den Profilordner (gitignored).
Die Niederschriften selbst, ihr Text und die Aufträge bleiben auf xtraspace (Plan, § 4).

Vorab festgelegt (Commit 97ebb52, 2026-11-24 00:41): Klassen, Kriterium, Rückfallregel und
Hypothesen in § 8 des Messdokuments. Dieses Skript rechnet **keine** Hypothese, nur ihre Prüfbarkeit.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from georep.council import JsonlStore, council_files
from georep.http import make_session
from georep.layout import Layout
from georep.oparl import OparlAgendaItem, OparlConsultation, OparlFile, OparlMeeting
from georep.prep.bodies import organization_key
from georep.prep.raw_texts import DEFAULT_PAGE_EXTRACTOR, raw_extractor_name, raw_from_pages
from georep.settings import Settings, load_settings
from georep.validation.sample import rank

SEED = 20261124
MESSDATEN = Path("/media/konrad/xtraspace/georep/messdaten/28-abstimmungen")
NIEDERSCHRIFTEN = MESSDATEN / "niederschriften"
LISTE = NIEDERSCHRIFTEN / "liste.csv"
TEXTE = MESSDATEN / "niederschriften_text.parquet"
KODIERUNG = Path("/media/konrad/xtraspace/georep/messdaten/kodierung")
PROJEKT = "28-abstimmungen"
USER_AGENT = "georep-messung/28 (Stichprobe Niederschriften, Stufe 1)"
PAUSE_S = 1.2
STICHTAG = dt.datetime(2026, 11, 23, tzinfo=dt.UTC)  # Sitzungen davor gelten als vergangen
# Stichprobe der Niederschriften, geschichtet nach Gremiumsart; der Rat bekommt mehr, als sein Anteil
# wäre (47 von rund 1 000), weil H28.1 und H28.3 im Rat gelten.
QUOTEN = {"rat": 12, "ausschuss": 22, "bv": 16}


# --------------------------------------------------------------------------------------------- Daten


@dataclass
class Daten:
    settings: Settings
    layout: Layout
    meetings: dict[str, OparlMeeting]
    items: dict[str, OparlAgendaItem]
    consultations: dict[str, OparlConsultation]


def laden() -> Daten:
    settings = load_settings()
    layout = Layout.from_settings(settings)
    files = council_files(layout)
    return Daten(
        settings,
        layout,
        dict(JsonlStore(files.meetings, OparlMeeting).load()),
        dict(JsonlStore(files.agenda_items, OparlAgendaItem).load()),
        dict(JsonlStore(files.consultations, OparlConsultation).load()),
    )


def gremium(settings: Settings, meeting: OparlMeeting) -> tuple[str, str]:
    """Kürzel und Art (rat, ausschuss, bv, beirat, unbekannt) des Gremiums einer Sitzung."""
    if not meeting.organization:
        return "", "unbekannt"
    code = settings.bodies.organizations.get(organization_key(meeting.organization[0]), "")
    if code in settings.bodies.council:
        return code, "rat"
    if (
        code.startswith(settings.bodies.district_body)
        and code[len(settings.bodies.district_body) :].isdigit()
    ):
        return code, "bv"
    if code in settings.bodies.committees:
        return code, "ausschuss"
    if code in settings.bodies.advisory:
        return code, "beirat"
    return code, "unbekannt"


def in_periode(settings: Settings, meeting: OparlMeeting) -> bool:
    if meeting.start is None or meeting.start >= STICHTAG:
        return False
    day = meeting.start.date()
    end = settings.period.end
    return settings.period.start <= day and (not end or day <= end)


def niederschrift(meeting: OparlMeeting) -> OparlFile | None:
    """Die Niederschrift des öffentlichen Teils, wenn die Sitzung eine hat (Runbook § 7)."""

    def vorrang(f: OparlFile) -> tuple[int, str]:
        name = (f.name or "").strip()
        if name == "Niederschrift Ö":
            return 0, f.id
        if name.startswith("Niederschrift Ö"):
            return 1, f.id
        return 2, f.id

    found = [
        f
        for f in meeting.auxiliary_file
        if (f.name or "").startswith("Niederschrift") and "nicht" not in (f.name or "").lower()
    ]
    return min(found, key=vorrang) if found else None


# ------------------------------------------------------------------------- Ergebnis (Ebene A, § 8.1)

ERGEBNIS_REGELN: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("zurueckgezogen", ("zurückgezogen",)),
    ("vertagt", ("vertagt", "zurückgestellt", "abgesetzt")),
    ("verwiesen", ("verwiesen",)),
    ("abgelehnt", ("abgelehnt",)),
    ("angenommen", ("beschlossen", "zugestimmt", "angenommen", "passieren lassen")),
    ("kenntnis", ("kenntnis", "beantwortet")),
    ("erledigt", ("erledigt",)),
)
ENTSCHIEDEN = ("angenommen", "abgelehnt")


def ergebnis(result: str | None) -> str:
    text = (result or "").lower()
    for klasse, woerter in ERGEBNIS_REGELN:
        if any(w in text for w in woerter):
            return klasse
    return "sonstiges"


def form_aus_result(result: str | None) -> str | None:
    if ergebnis(result) not in ENTSCHIEDEN:
        return None
    text = (result or "").lower()
    if "einstimmig" in text:
        return "einstimmig"
    if "mehrheitlich" in text:
        return "mehrheitlich"
    return "ohne_angabe"


def geaendert(result: str | None) -> bool:
    text = (result or "").lower()
    return "abweichend" in text or "geändert" in text


# ------------------------------------------------------------------------------------------ Abruf


def sitzungen_der_stichprobe(d: Daten) -> list[tuple[OparlMeeting, OparlFile, str, str]]:
    """50 Sitzungen mit Niederschrift, je Art reihum über die Gremien, Rang SHA-256(Seed, ID)."""
    je_gremium: dict[tuple[str, str], list[tuple[OparlMeeting, OparlFile]]] = defaultdict(list)
    for m in d.meetings.values():
        if not in_periode(d.settings, m):
            continue
        code, art = gremium(d.settings, m)
        f = niederschrift(m)
        if art in QUOTEN and f is not None:
            je_gremium[(art, code)].append((m, f))
    chosen: list[tuple[OparlMeeting, OparlFile, str, str]] = []
    for art, quote in QUOTEN.items():
        codes = sorted((c for a, c in je_gremium if a == art), key=lambda c: rank(SEED, c))
        queues = {
            c: sorted(je_gremium[(art, c)], key=lambda mf: rank(SEED, mf[0].id)) for c in codes
        }
        taken = 0
        while taken < quote and any(queues.values()):
            for c in codes:
                if taken < quote and queues[c]:
                    m, f = queues[c].pop(0)
                    chosen.append((m, f, art, c))
                    taken += 1
    return chosen


def abruf(d: Daten) -> None:
    NIEDERSCHRIFTEN.mkdir(parents=True, exist_ok=True)
    known: dict[str, dict[str, str]] = {}
    if LISTE.is_file():
        with LISTE.open(encoding="utf-8") as fh:
            known = {row["datei"]: row for row in csv.DictReader(fh)}
    session = make_session(user_agent=USER_AGENT)
    rows: list[dict[str, str]] = []
    began = time.monotonic()
    for m, f, art, code in sitzungen_der_stichprobe(d):
        key = f.id.rsplit("/", 1)[-1]
        path = NIEDERSCHRIFTEN / f"{key}.pdf"
        url = f.download_url or f.access_url or ""
        if (
            key in known
            and path.is_file()
            and hashlib.sha256(path.read_bytes()).hexdigest() == known[key]["sha256"]
        ):
            rows.append(known[key])
            continue
        when = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        response = session.get(url)
        response.raise_for_status()
        data = response.content
        if not data.startswith(b"%PDF"):
            raise SystemExit(f"{url}: keine PDF-Datei ({data[:40]!r})")
        path.write_bytes(data)
        rows.append(
            {
                "sitzung": m.id.rsplit("/", 1)[-1],
                "datum": m.start.date().isoformat() if m.start else "",
                "art": art,
                "gremium": code,
                "datei": key,
                "name": f.name or "",
                "url": url,
                "abrufzeit": when,
                "bytes": str(len(data)),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        print(f"{len(rows):2d} {art:9s} {code:6s} {key} {len(data):>9,d} B", flush=True)
        time.sleep(PAUSE_S)
    with LISTE.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    total = sum(int(r["bytes"]) for r in rows)
    print(f"{len(rows)} Niederschriften, {total:,d} Bytes, {time.monotonic() - began:.0f} s")


def texte() -> pl.DataFrame:
    """Rohtext der Niederschriften (pypdf 7.1.0 wie F1), einmal extrahiert, dann gelesen."""
    with LISTE.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if TEXTE.is_file():
        frame = pl.read_parquet(TEXTE)
        if sorted(frame.get_column("datei").to_list()) == sorted(r["datei"] for r in rows):
            return frame
    out = []
    for r in rows:
        path = NIEDERSCHRIFTEN / f"{r['datei']}.pdf"
        if hashlib.sha256(path.read_bytes()).hexdigest() != r["sha256"]:
            raise SystemExit(f"{path}: Prüfsumme weicht von der Liste ab")
        pages = DEFAULT_PAGE_EXTRACTOR.pages(path)
        text, _ = raw_from_pages(pages)
        out.append(
            {"datei": r["datei"], "sitzung": r["sitzung"], "seiten": len(pages), "text": text}
        )
    frame = pl.DataFrame(out).sort("datei")
    frame = frame.with_columns(
        pl.lit(raw_extractor_name(DEFAULT_PAGE_EXTRACTOR)).alias("extractor")
    )
    frame.write_parquet(TEXTE)
    return frame


# ------------------------------------------------------------------------------- Punkte und Ebene A

PERIODEN = {
    "duesseldorf-2014": "2014-2020",
    "duesseldorf": "2020-2025",
    "duesseldorf-2025": "ab 2025",
}


def punkte(d: Daten, *, mit_niederschrift: set[str] | None = None) -> pl.DataFrame:
    """Je Tagesordnungspunkt mit Beratung einer vergangenen Sitzung der Periode eine Zeile."""
    nieder = {m.id for m in d.meetings.values() if niederschrift(m) is not None}
    rows = []
    for i in d.items.values():
        m = d.meetings.get(i.meeting or "")
        if m is None or not i.consultation or not in_periode(d.settings, m):
            continue
        code, art = gremium(d.settings, m)
        cons = d.consultations.get(i.consultation)
        rows.append(
            {
                "top": i.id,
                "sitzung": m.id,
                "datum": m.start.date() if m.start else None,
                "gremium": code,
                "art": art,
                "nummer": i.number or "",
                "name": i.name or "",
                "beratung": i.consultation,
                "paper": cons.paper if cons is not None else None,
                "result": (i.result or "").strip(),
                "ergebnis": ergebnis(i.result),
                "form": form_aus_result(i.result),
                "geaendert": geaendert(i.result),
                "niederschrift": m.id in nieder,
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None).sort("top")


def anteil(k: int, n: int) -> str:
    return f"{k} / {n} ({100 * k / n:.1f} %)" if n else f"{k} / 0"


def ebene_a(frame: pl.DataFrame, titel: str) -> dict[str, Any]:
    entschieden = frame.filter(pl.col("ergebnis").is_in(ENTSCHIEDEN))
    mit_form = entschieden.filter(pl.col("form") != "ohne_angabe")
    out = {
        "punkte_mit_beratung": frame.height,
        "ohne_result": frame.filter(pl.col("result") == "").height,
        "beschluesse": entschieden.height,
        "mit_form": mit_form.height,
        "einstimmig": entschieden.filter(pl.col("form") == "einstimmig").height,
        "mehrheitlich": entschieden.filter(pl.col("form") == "mehrheitlich").height,
        "mit_niederschrift": entschieden.filter(pl.col("niederschrift")).height,
    }
    print(
        f"{titel:28s} Punkte {out['punkte_mit_beratung']:6d}, ohne result {out['ohne_result']:5d}, "
        f"Beschlüsse {out['beschluesse']:6d}, Form bekannt {anteil(out['mit_form'], out['beschluesse'])}, "
        f"einstimmig {anteil(out['einstimmig'], out['mit_form'])}, "
        f"Sitzung mit Niederschrift {anteil(out['mit_niederschrift'], out['beschluesse'])}"
    )
    return out


def messen_ebene_a() -> dict[str, Any]:
    print(
        "== Ebene A: Ergebnis und Mehrheitsform aus result (§ 8.1), vergangene Sitzungen bis 2026-11-23"
    )
    result: dict[str, Any] = {}
    for profil, label in PERIODEN.items():
        settings = load_settings(profile=profil)
        layout = Layout.from_settings(settings)
        files = council_files(layout)
        if not files.meetings.is_file():
            print(f"{label}: keine Sitzungen unter {files.meetings}")
            continue
        consultations = (
            dict(JsonlStore(files.consultations, OparlConsultation).load())
            if files.consultations.is_file()
            else {}
        )
        d = Daten(
            settings,
            layout,
            dict(JsonlStore(files.meetings, OparlMeeting).load()),
            dict(JsonlStore(files.agenda_items, OparlAgendaItem).load()),
            consultations,
        )
        frame = punkte(d)
        result[label] = {"alle": ebene_a(frame, f"{label}, alle")}
        for art in ("rat", "ausschuss", "bv", "beirat", "unbekannt"):
            result[label][art] = ebene_a(frame.filter(pl.col("art") == art), f"{label}, {art}")
        if label == "2020-2025":
            werte = frame.group_by("result", "ergebnis", "form").len().sort("len", descending=True)
            print("   Wortschatz von result an Punkten mit Beratung (Hauptperiode):")
            for row in werte.iter_rows(named=True):
                print(
                    f"   {row['len']:6d}  {row['ergebnis']:15s} {row['form'] or '-':12s} {row['result']!r}"
                )
    return result


# ------------------------------------------------------------- Niederschriften: Schnitt je Punkt

# Seitenkopf der Niederschriften: er steht mitten im Satz und muss vor dem Lesen heraus.
KOPF_START = re.compile(r"^\s*Niederschrift (des öffentlichen Teils|über die Sitzung)\b")
KOPF_ENDE = re.compile(r"^\s*Seite \d+\s*$")
NUMMER = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3})*)\.?\s*$")


def ohne_kopf(text: str) -> list[str]:
    """Zeilen ohne Seitenköpfe (Niederschrift …, Sitzungsdatum, SI-…, Seite n) und ohne Formfeeds."""
    lines = text.replace("\f", "\n").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if KOPF_START.match(lines[i]):
            j = i
            while j < len(lines) and j - i < 6 and not KOPF_ENDE.match(lines[j]):
                j += 1
            if j < len(lines) and KOPF_ENDE.match(lines[j]):
                i = j + 1
                continue
        out.append(lines[i])
        i += 1
    return out


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


@dataclass
class Abschnitt:
    top: str
    teile: list[
        tuple[int, int]
    ]  # Zeilen [start, ende) je Aufruf; der Rat ruft manche Punkte zweimal auf


def schnitt(lines: Sequence[str], tops: Sequence[tuple[str, str, str]]) -> dict[str, Abschnitt]:
    """Je Tagesordnungspunkt (ID, Nummer, Drucksache oder Name) seine Abschnitte im Text.

    Ein Aufruf beginnt an einer Zeile, die nur die Nummer trägt und der binnen acht Zeilen die
    Drucksachennummer oder der Anfang des Namens folgt (die Tagesordnung vorn hat Nummer und Text in
    einer Zeile und trifft darum nicht). Rückfall: die Drucksachennummer allein auf einer Zeile (die
    Niederschrift nummeriert manchmal anders als die Tagesordnung im System), Beginn an der
    Nummernzeile höchstens sechs davor. Jeder Aufruf endet am nächsten Aufruf irgendeines Punktes;
    der Rat ruft Punkte im Schnelldurchgang auf und später zur Debatte noch einmal.
    """
    starts: dict[str, list[int]] = defaultdict(list)
    nummern = [NUMMER.match(line) for line in lines]
    for top, number, key in tops:
        number = number.strip().rstrip(".")
        want = norm(key)[:25]
        for i, m in enumerate(nummern):
            if m is None or m.group(1) != number:
                continue
            following = " ".join(norm(lines[j]) for j in range(i + 1, min(i + 9, len(lines))))
            if want and want in following:
                starts[top].append(i)
    taken = {i for v in starts.values() for i in v}
    for top, _number, key in tops:
        if top in starts or not re.match(r"^[A-ZÄÖÜ]+\d{0,2}/\d+/\d{4}", key):
            continue
        k = norm(key)
        for i, line in enumerate(lines):
            n = norm(line)
            if n.startswith(k) and len(n) <= len(k) + 14:
                begin = next((j for j in range(i - 1, max(-1, i - 7), -1) if nummern[j]), i)
                if begin not in taken:
                    starts[top].append(begin)
                    taken.add(begin)
    alle = sorted((i, top) for top, v in starts.items() for i in v)
    out: dict[str, Abschnitt] = {}
    for k, (start, top) in enumerate(alle):
        ende = alle[k + 1][0] if k + 1 < len(alle) else len(lines)
        out.setdefault(top, Abschnitt(top, [])).teile.append((start, ende))
    return out


# ------------------------------------------------------------ Niederschriften: Stimmen (Ebene B)

# Parteien, kleingeschrieben; eine Fraktion aus mehreren Parteien gibt allen dieselbe Position (§ 8.1).
PARTEIMUSTER: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"spd\s*/\s*volt", ("SPD", "VOLT")),
    (r"partei[\s/-]*klima|klima[\s-]*fraktion", ("PARTEI", "KLIMA")),
    (r"klimaliste", ("KLIMA",)),
    (
        r"tierschutz\s*/\s*freie\s*wähler|ts\s*/\s*fw|freie wähler\s*/\s*tierschutz",
        ("TIERSCHUTZ", "FW"),
    ),
    (r"\bcdu\b", ("CDU",)),
    (r"bündnis\s*90|bü\s*90|\bgrüne[n]?\b|\bgrü\b|\bgruene\b", ("GRUENE",)),
    (r"\bspd\b", ("SPD",)),
    (r"\bfdp\b", ("FDP",)),
    (r"\blinke[n]?\b", ("LINKE",)),
    (r"\bafd\b", ("AFD",)),
    (r"\bdie partei\b|\bpartei\b", ("PARTEI",)),
    (r"\btierschutz\b", ("TIERSCHUTZ",)),
    (r"freie\s*wähler", ("FW",)),
    (r"\bvolt\b", ("VOLT",)),
    (r"\bbsw\b", ("BSW",)),
)
PARTEI_RE = re.compile("|".join(f"(?P<p{i}>{p})" for i, (p, _) in enumerate(PARTEIMUSTER)))
PERSON_RE = re.compile(
    r"\b(?:ratsfrau|ratsherrn?|herrn?|frau|rh|rf|bezirksvertreter(?:in)?)\.?\s+(?:dr\.\s+)?([a-zäöüß][\wäöüß-]+)"
)
ZAHL_VOR = re.compile(r"(\d+)\s*$")

# Marken eines Stimmfachs; was danach bis zur nächsten Marke steht, gehört in dieses Fach.
FACH_RE = re.compile(
    r"(?P<ja>\bwer ist für\b|\bwer stimmt (?:dafür|zu)\b|\bmit den stimmen (?:der|von|des)\b|"
    r"\bja\s*:|\d+\s*ja\b|\bja\s+\d|\bja-stimmen?\b|\bwer ist dafür\b)|"
    r"(?P<nein>\bwer ist dagegen\b|\bwer stimmt dagegen\b|\bgegen die stimmen? (?:der|von|des)\b|"
    r"\bgegenstimmen?\b|\bnein\s*:|\d+\s*nein\b|\bnein\s+\d|\bnein-stimmen?\b)|"
    r"(?P<enth>\bwer enthält sich\b|\benthält sich\b|\bstimmenthaltungen?\b|\benthaltungen?\b|\benth\.)|"
    r"(?P<stop>\bdann\b|\bdamit\b|beschlussdarstellung|\bbeschluss\s*:|\bbeschluss\b(?!s))"
)
ANKER_RE = re.compile(
    r"abstimmungsergebnis|\babstimmung\s*:|\bbeschluss\s*[:(]|\beinstimmig|\bmehrheitlich|mit (?:großer )?mehrheit|"
    r"gegenstimmen\s*\?|wer ist für|\bja\s*:\s*\d|\d+\s+ja\b|ja-stimmen"
)
FORM_RE = re.compile(r"einstimmig|mehrheitlich|mit (?:großer )?mehrheit|stimmenmehrheit")
ERG_RE = re.compile(
    r"abgelehnt|lehnt\b|beschlossen|beschließt|angenommen|zugestimmt|stimmt\b|empfiehlt|genehmigt|"
    r"zur kenntnis genommen"
)
SCHLUSS_RE = re.compile(
    r"\b(?:damit|dann)\b[^.?!]{0,140}?\b(?:abgelehnt|beschlossen|angenommen|genehmigt|zugestimmt|gewählt)\b"
)
AENDERUNG_RE = re.compile(
    r"änderungsantrag|ergänzungsantrag|zusatzantrag|änderungs- und ergänzungsantrag"
)
REST_RE = re.compile(r"\brest\b|\bübrigen\b|alle anderen|alle weiteren|\balle bis auf\b|fast alle")


@dataclass
class Stimmen:
    ergebnis: str | None = None  # angenommen, abgelehnt, kenntnis
    form: str | None = None  # einstimmig, mehrheitlich
    faecher: dict[str, set[str]] = field(
        default_factory=lambda: {"ja": set(), "nein": set(), "enth": set()}
    )
    genannt: dict[str, bool] = field(
        default_factory=lambda: {"ja": False, "nein": False, "enth": False}
    )
    rest: str | None = None  # Fach, das die nicht genannten bekommen
    einzeln: int = 0  # Personen ohne zuordenbare Partei
    stelle: int = -1  # Anfang des Fensters im Abschnitt

    def positionen(self, gremium_parteien: Iterable[str]) -> dict[str, str]:
        out: dict[str, set[str]] = defaultdict(set)
        for fach, parteien in self.faecher.items():
            for p in parteien:
                out[p].add(fach)
        if self.rest is not None:
            for p in gremium_parteien:
                if p not in out:
                    out[p].add(self.rest)
        name = {"ja": "ja", "nein": "nein", "enth": "enthaltung"}
        return {
            p: (name[next(iter(f))] if len(f) == 1 else "geteilt") for p, f in sorted(out.items())
        }

    def genannte(self) -> dict[str, str]:
        return self.positionen(())


def parteien_in(s: str, personen: Mapping[str, str]) -> tuple[set[str], int]:
    """Parteien in einem Stück Text, dazu die Zahl der Personen ohne Partei."""
    found: set[str] = set()
    spans = []
    for m in PARTEI_RE.finditer(s):
        idx = next(int(k[1:]) for k, v in m.groupdict().items() if v is not None)
        found.update(PARTEIMUSTER[idx][1])
        spans.append((m.start(), m.end()))
    einzeln = 0
    for m in PERSON_RE.finditer(s):
        after = s[m.end() : m.end() + 40]
        if PARTEI_RE.match(after.lstrip(" ([")):  # „Ratsfrau X (Die Linke)": die Partei steht dabei
            continue
        party = personen.get(m.group(1))
        if party:
            found.add(party)
        else:
            einzeln += 1
    return found, einzeln


def stimmen(
    abschnitt: str, personen: Mapping[str, str], hinweis: str | None = None, aenderung: bool = False
) -> Stimmen | None:
    """Die letzte Abstimmung eines Abschnitts (§ 8.1): Ergebnis, Form, Fächer, Ergänzungsregel.

    ``hinweis`` ist das Ergebnis aus ``result`` (Rückfallregel 1: es gilt, wenn es entschieden ist).
    """
    low = abschnitt.lower()
    anker = list(ANKER_RE.finditer(low))
    if not anker:
        return None
    # Die maßgebliche Abstimmung endet an einem Schluss („Damit ist der Antrag … abgelehnt"): beim
    # Änderungsantrag am letzten, vor dem er genannt ist, sonst am letzten des Abschnitts. Ohne Schluss
    # (Blockform „Abstimmungsergebnis: …") gilt der letzte Anker.
    schluesse = list(SCHLUSS_RE.finditer(low))
    if schluesse:
        ziel = schluesse[-1]
        if aenderung:
            treffer = [
                c for c in schluesse if AENDERUNG_RE.search(low[max(0, c.start() - 400) : c.end()])
            ]
            ziel = treffer[-1] if treffer else ziel
        vor = [a for a in anker if a.start() < ziel.end()]
        last = vor[-1].start() if vor else ziel.start()
        ende = ziel.end() + 60
    else:
        vor = anker
        last = anker[-1].start()
        ende = last + 500
    begin = last
    for a in reversed([a for a in vor if a.start() < last]):
        if a.start() >= begin - 500:
            begin = a.start()
        else:
            break
    start = max(0, begin - 200)
    fenster = low[start:ende]
    st = Stimmen(stelle=start)
    kern = low[begin : last + 300]
    formen = list(FORM_RE.finditer(kern)) or list(FORM_RE.finditer(fenster))
    if formen:
        st.form = "einstimmig" if formen[-1].group() == "einstimmig" else "mehrheitlich"
    if hinweis in ENTSCHIEDEN:
        st.ergebnis = hinweis
    else:
        ergs = list(ERG_RE.finditer(kern))
        if ergs:
            e = ergs[-1].group()
            st.ergebnis = (
                "abgelehnt"
                if e in ("abgelehnt", "lehnt")
                else "kenntnis"
                if "kenntnis" in e
                else "angenommen"
            )
    fach = None
    pos = 0
    counted: dict[str, int] = {}
    rest_fach = None

    def fuellen(fach: str, stueck: str) -> None:
        nonlocal rest_fach
        teil = stueck.split("bis auf")[0] if "bis auf" in stueck else stueck
        parties, einzeln = parteien_in(teil, personen)
        st.faecher[fach] |= parties
        st.einzeln += einzeln
        zahl = re.match(r"[\s:–-]*(\d+|--|-|keine|niemand)", stueck)
        if REST_RE.search(stueck):
            rest_fach = fach
            st.genannt[fach] = True
        if zahl or parties or einzeln:
            st.genannt[fach] = True
        if (
            zahl
            and not parties
            and not einzeln
            and zahl.group(1).isdigit()
            and int(zahl.group(1)) > 0
        ):
            counted[fach] = int(zahl.group(1))

    markiert: set[str] = set()
    for f in FACH_RE.finditer(fenster):
        if fach is not None:
            fuellen(fach, fenster[pos : f.start()])
        kind = f.lastgroup
        if kind is not None:
            markiert.add(kind)
        fach = None if kind == "stop" else kind
        pos = f.end()
    if fach is not None:
        fuellen(fach, fenster[pos : pos + 200])
    # Form aus den Fächern, wenn der Text sie nicht nennt; und nach der Definition (§ 8.1: keine
    # Gegenstimme heißt einstimmig), wenn nach Gegenstimmen gefragt und keine genannt wurde.
    gegen = bool(st.faecher["nein"] or counted.get("nein") or rest_fach == "nein")
    if st.form is None and st.ergebnis in ENTSCHIEDEN:
        if gegen:
            st.form = "mehrheitlich"
        elif re.search(r"\bja\s*:\s*\d|\d+\s*ja\b", fenster) and "nein" not in fenster:
            st.form = "einstimmig"
        elif "nein" in markiert and not st.genannt["nein"]:
            st.form = "einstimmig"
    elif st.form == "mehrheitlich" and "nein" in markiert and not st.genannt["nein"] and not gegen:
        st.form = "einstimmig"
    # Ergänzungsregel (§ 8.1): ein Fach, das „den Rest" nennt, oder ein Fach mit Zahl ohne Parteien,
    # bekommt die nicht genannten; sonst die Seite des Ergebnisses, wenn ihr Fach leer ist und die
    # Formel die Form nennt (dann nennt sie nur die Abweichenden).
    if rest_fach is not None:
        st.rest = rest_fach
    elif counted:
        st.rest = max(counted, key=lambda k: counted[k])
    elif st.ergebnis in ENTSCHIEDEN:
        seite = "ja" if st.ergebnis == "angenommen" else "nein"
        if not st.faecher[seite] and st.form is not None:
            st.rest = seite
        elif st.form == "einstimmig" and not st.faecher["nein"]:
            st.rest = seite
    return st


def personen_der_niederschrift(lines: Sequence[str]) -> dict[str, str]:
    """Familienname → Partei aus der Anwesenheitsliste und aus „Ratsherr X (Partei)" im Text.

    Nur zur Zuordnung einzeln genannter Mitglieder; die Namen verlassen das Skript nicht.
    """
    out: dict[str, str] = {}
    text = "\n".join(lines)
    low = text.lower()
    for m in PERSON_RE.finditer(low):
        after = low[m.end() : m.end() + 40].lstrip(" ([")
        pm = PARTEI_RE.match(after)
        if pm:
            idx = next(int(k[1:]) for k, v in pm.groupdict().items() if v is not None)
            out.setdefault(m.group(1), PARTEIMUSTER[idx][1][0])
    start = next(
        (i for i, line in enumerate(lines) if line.strip().lower().startswith("anwesend")), None
    )
    if start is not None:
        for line in lines[start : start + 120]:
            zeile = line.lower()
            if re.match(r"\s*(weitere|sonstige) teilnehm|\s*entschuldigt|\s*es fehlt", zeile):
                break
            pm = PARTEI_RE.search(zeile)
            if not pm:
                continue
            words = re.findall(r"[a-zäöüß][\wäöüß-]+", zeile[: pm.start()])
            if words:
                idx = next(int(k[1:]) for k, v in pm.groupdict().items() if v is not None)
                out.setdefault(words[-1], PARTEIMUSTER[idx][1][0])
    return out


# --------------------------------------------------------- Niederschriften: je Punkt eine Zeile

RAT_PARTEIEN_2020 = (
    "CDU",
    "GRUENE",
    "SPD",
    "VOLT",
    "FDP",
    "LINKE",
    "AFD",
    "PARTEI",
    "KLIMA",
    "TIERSCHUTZ",
    "FW",
)
FRAKTIONEN_2020 = (  # Fraktionen und Gruppen aus mehreren Parteien in Rat und Ausschüssen, Plan § 8.5
    ("SPD", "VOLT"),
    ("PARTEI", "KLIMA"),
    ("TIERSCHUTZ", "FW"),
)
NEUER_RAT = dt.date(2020, 11, 1)


def erweitert(parteien: Iterable[str], art: str, datum: dt.date) -> set[str]:
    """In Rat und Ausschüssen ab 2020-11-01 steht eine Fraktion aus mehreren Parteien für alle."""
    out = set(parteien)
    if art in ("rat", "ausschuss") and datum >= NEUER_RAT:
        for gruppe in FRAKTIONEN_2020:
            if out & set(gruppe):
                out |= set(gruppe)
    return out


def positionen_erweitert(
    st: Stimmen, art: str, datum: dt.date, gremium: Iterable[str]
) -> dict[str, str]:
    copy = Stimmen(
        st.ergebnis,
        st.form,
        {k: erweitert(v, art, datum) for k, v in st.faecher.items()},
        dict(st.genannt),
        st.rest,
        st.einzeln,
        st.stelle,
    )
    return copy.positionen(gremium)


@dataclass
class Punkt:
    top: str
    sitzung: str
    datei: str
    art: str
    gremium: str
    datum: dt.date
    nummer: str
    name: str
    paper: str | None
    result: str
    abschnitt: str | None  # Text des Abschnitts oder None, wenn nicht gefunden
    stimmen: Stimmen | None
    gremium_parteien: tuple[str, ...]


def niederschrift_punkte(d: Daten) -> list[Punkt]:
    """Je Tagesordnungspunkt mit Beratung in den 50 Niederschriften: Abschnitt und letzte Abstimmung."""
    with LISTE.open(encoding="utf-8") as fh:
        liste = {r["datei"]: r for r in csv.DictReader(fh)}
    textframe = texte()
    corpus = pl.read_parquet(d.layout.corpus, columns=["id", "reference"])
    refs = dict(
        zip(
            corpus.get_column("id").to_list(), corpus.get_column("reference").to_list(), strict=True
        )
    )
    by_meeting: dict[str, list[OparlAgendaItem]] = defaultdict(list)
    for i in d.items.values():
        if i.meeting:
            by_meeting[i.meeting].append(i)
    out: list[Punkt] = []
    for row in textframe.sort("datei").iter_rows(named=True):
        meta = liste[row["datei"]]
        meeting = next(m for m in d.meetings.values() if m.id.rsplit("/", 1)[-1] == meta["sitzung"])
        datum = meeting.start.date() if meeting.start else dt.date.min
        art = meta["art"]
        lines = ohne_kopf(row["text"])
        personen = personen_der_niederschrift(lines)
        items = sorted(by_meeting[meeting.id], key=lambda i: (i.order or 0, i.id))
        tops = []
        for i in items:
            cons = d.consultations.get(i.consultation or "")
            ref = refs.get(cons.paper) if cons is not None and cons.paper else None
            tops.append((i.id, i.number or "", ref or (i.name or "")))
        found = schnitt(lines, tops)
        punkte_hier: list[Punkt] = []
        for i in items:
            if not i.consultation:
                continue
            cons = d.consultations.get(i.consultation)
            ab = found.get(i.id)
            text = "\n".join("\n".join(lines[a:e]) for a, e in ab.teile) if ab else None
            aenderung = bool(AENDERUNG_RE.match((i.name or "").lower().strip()))
            st = stimmen(text, personen, ergebnis(i.result), aenderung) if text else None
            punkte_hier.append(
                Punkt(
                    i.id,
                    meeting.id,
                    row["datei"],
                    art,
                    meta["gremium"],
                    datum,
                    i.number or "",
                    i.name or "",
                    cons.paper if cons else None,
                    (i.result or "").strip(),
                    text,
                    st,
                    (),
                )
            )
        # Parteien des Gremiums: im Rat die Sitzverteilung, sonst was die Niederschrift nennt.
        if art == "rat" and datum >= NEUER_RAT:
            gremium_parteien = set(RAT_PARTEIEN_2020)
        else:
            gremium_parteien = set()
            for p in punkte_hier:
                if p.stimmen:
                    for v in p.stimmen.faecher.values():
                        gremium_parteien |= v
            gremium_parteien |= set(personen.values())
            gremium_parteien = erweitert(gremium_parteien, art, datum)
        for p in punkte_hier:
            p.gremium_parteien = tuple(sorted(gremium_parteien))
        out.extend(punkte_hier)
    return out


def hochrechnung() -> None:
    """Der volle Abruf der Niederschriften je Periode: Zahl, Größe (Mittel je Art aus der Stichprobe), Dauer."""
    with LISTE.open(encoding="utf-8") as fh:
        liste = list(csv.DictReader(fh))
    mittel = {
        a: sum(int(r["bytes"]) for r in liste if r["art"] == a) / sum(r["art"] == a for r in liste)
        for a in QUOTEN
    }
    alle = sum(int(r["bytes"]) for r in liste) / len(liste)
    print(
        "== Hochrechnung des vollen Abrufs (1,5 s je Datei mit Pause wie in der Stichprobe; pypdf rund 4,6 s je Datei)"
    )
    for profil, label in PERIODEN.items():
        settings = load_settings(profile=profil)
        files = council_files(Layout.from_settings(settings))
        if not files.meetings.is_file():
            continue
        zahl: Counter[str] = Counter()
        for m in JsonlStore(files.meetings, OparlMeeting).load().values():
            if in_periode(settings, m) and niederschrift(m) is not None:
                zahl[gremium(settings, m)[1]] += 1
        n = sum(zahl.values())
        groesse = sum(v * mittel.get(a, alle) for a, v in zahl.items())
        print(
            f"   {label:10s} {n:5d} Niederschriften ({', '.join(f'{a} {v}' for a, v in sorted(zahl.items()))}), "
            f"rund {groesse / 1e9:.2f} GB, Abruf rund {n * 1.5 / 60:.0f} min, Text rund {n * 4.6 / 60:.0f} min auf einem Kern"
        )


def stile() -> None:
    """Welche Form der Abstimmungsangabe eine Niederschrift überwiegend hat (je Dokument gezählt)."""
    with LISTE.open(encoding="utf-8") as fh:
        art = {r["datei"]: r["art"] for r in csv.DictReader(fh)}
    zaehl: Counter[tuple[str, str]] = Counter()
    for row in texte().iter_rows(named=True):
        low = row["text"].lower()
        if len(low.strip()) < 200:
            stil = "ohne Textebene (Scan)"
        elif len(re.findall(r"gegenstimmen\s*\?|wer ist für", low)) > 5:
            stil = "Wortprotokoll mit Fragen (Gegenstimmen? – …)"
        elif len(re.findall(r"\bja\s*:\s*\d|\d+\s*ja\b|ja-stimmen", low)) >= 3:
            stil = "Stimmenzahlen mit Fraktionen (Ja: n (…))"
        elif len(re.findall(r"abstimmungsergebnis|beschluss\s*[:(]|abstimmung\s*:", low)) >= 3:
            stil = "Block nur mit Form (Abstimmungsergebnis: einstimmig)"
        else:
            stil = "Fließtext (… beschließt mehrheitlich …)"
        zaehl[(stil, art[row["datei"]])] += 1
    print("== Formen der Abstimmungsangabe je Niederschrift")
    for stil in sorted({s for s, _ in zaehl}):
        teile = ", ".join(
            f"{a} {zaehl[(stil, a)]}" for a in ("rat", "ausschuss", "bv") if zaehl[(stil, a)]
        )
        print(f"   {stil:55s} {sum(v for (s, _), v in zaehl.items() if s == stil):3d}  ({teile})")


def vollstaendig(p: Punkt) -> bool:
    if p.stimmen is None or p.stimmen.ergebnis not in ENTSCHIEDEN or p.stimmen.form is None:
        return False
    pos = positionen_erweitert(p.stimmen, p.art, p.datum, p.gremium_parteien)
    return bool(p.gremium_parteien) and all(q in pos for q in p.gremium_parteien)


def messen_niederschriften(d: Daten) -> dict[str, Any]:
    pts = niederschrift_punkte(d)
    with LISTE.open(encoding="utf-8") as fh:
        liste = list(csv.DictReader(fh))
    textframe = texte()
    ohne_text = [
        r["datei"] for r in textframe.iter_rows(named=True) if len(r["text"].strip()) < 200
    ]
    print("== Niederschriften: Stichprobe, Text, Schnitt, Stimmen")
    total = sum(int(r["bytes"]) for r in liste)
    print(
        f"   {len(liste)} Niederschriften, {total:,d} Bytes; ohne Textebene: {len(ohne_text)} "
        f"({', '.join(r['gremium'] for r in liste if r['datei'] in ohne_text)})"
    )
    res: dict[str, Any] = {
        "niederschriften": len(liste),
        "bytes": total,
        "ohne_text": len(ohne_text),
    }
    for art in ("rat", "ausschuss", "bv", "alle"):
        sel = [p for p in pts if art == "alle" or p.art == art]
        mit_text = [p for p in sel if p.datei not in ohne_text]
        gefunden = [p for p in mit_text if p.abschnitt is not None]
        beschl = [p for p in sel if ergebnis(p.result) in ENTSCHIEDEN]
        beschl_text = [p for p in beschl if p.datei not in ohne_text]
        mit_stimme = [p for p in beschl if p.stimmen is not None and p.stimmen.ergebnis is not None]
        a2 = [
            p
            for p in beschl
            if (p.stimmen and p.stimmen.form)
            or form_aus_result(p.result) in ("einstimmig", "mehrheitlich")
        ]
        a2_nieder = [p for p in beschl if p.stimmen and p.stimmen.form]
        b = [p for p in beschl if vollstaendig(p)]
        widerspruch = [
            p
            for p in beschl
            if p.stimmen
            and p.stimmen.form
            and form_aus_result(p.result) in ("einstimmig", "mehrheitlich")
            and p.stimmen.form != form_aus_result(p.result)
        ]
        vergleichbar = [
            p
            for p in beschl
            if p.stimmen
            and p.stimmen.form
            and form_aus_result(p.result) in ("einstimmig", "mehrheitlich")
        ]
        einzeln = [p for p in beschl if p.stimmen and p.stimmen.einzeln]
        beschl_gefunden = [p for p in beschl_text if p.abschnitt is not None]
        print(
            f"   {art:9s} Punkte {len(sel):4d}; Abschnitt gefunden {anteil(len(gefunden), len(mit_text))} (mit Text), "
            f"bei Beschlüssen {anteil(len(beschl_gefunden), len(beschl_text))}; "
            f"Beschlüsse {len(beschl)}, davon im Text {len(beschl_text)}; Abstimmung gelesen {anteil(len(mit_stimme), len(beschl))}; "
            f"Form A2 {anteil(len(a2), len(beschl))} (aus Niederschrift {len(a2_nieder)}); "
            f"B vollständig {anteil(len(b), len(beschl))}; Form result≠Niederschrift {len(widerspruch)} von {len(vergleichbar)}; "
            f"mit Einzelpersonen ohne Partei {len(einzeln)}"
        )
        res[art] = {
            "punkte": len(sel),
            "mit_text": len(mit_text),
            "gefunden": len(gefunden),
            "beschluesse": len(beschl),
            "abstimmung_gelesen": len(mit_stimme),
            "a2": len(a2),
            "a2_niederschrift": len(a2_nieder),
            "b_vollstaendig": len(b),
            "widerspruch": len(widerspruch),
            "vergleichbar": len(vergleichbar),
            "einzelpersonen": len(einzeln),
        }
    # Prüfbarkeit der Hypothesen in der Stichprobe (nicht ihr Ausgang).
    corpus = pl.read_parquet(d.layout.corpus, columns=["id", "paper_type"])
    urheber = pl.read_parquet(d.layout.processed / "dokumente_urheber.parquet")
    info = {r["id"]: r for r in corpus.join(urheber, on="id", how="left").iter_rows(named=True)}
    rat = [p for p in pts if p.art == "rat" and ergebnis(p.result) in ENTSCHIEDEN]
    strittig = [
        p
        for p in rat
        if (p.stimmen and p.stimmen.form == "mehrheitlich")
        or form_aus_result(p.result) == "mehrheitlich"
    ]
    beide = []
    for p in strittig:
        if p.stimmen is None:
            continue
        pos = positionen_erweitert(p.stimmen, p.art, p.datum, p.gremium_parteien)
        if pos.get("CDU") in ("ja", "nein", "enthaltung") and pos.get("GRUENE") in (
            "ja",
            "nein",
            "enthaltung",
        ):
            beide.append(p)
    afd = []
    for p in rat:
        meta = info.get(p.paper or "")
        if meta is None:
            continue
        art_ = (meta["paper_type"] or "").lower()
        if "antrag" in art_ and "anfrage" not in art_ and "AfD" in (meta["parteien"] or []):
            afd.append(p)
    afd_bestimmt = [p for p in afd if vollstaendig(p)]
    print(
        f"   H28.1 Prüfbarkeit: strittige Ratsbeschlüsse in der Stichprobe {len(strittig)}, "
        f"davon CDU und GRÜNE beide bekannt {anteil(len(beide), len(strittig))}"
    )
    print(
        f"   H28.3 Prüfbarkeit: AfD-Anträge mit Ratsbeschluss in der Stichprobe {len(afd)}, "
        f"davon Positionen vollständig {anteil(len(afd_bestimmt), len(afd))}"
    )
    res["h1_strittig"], res["h1_beide"] = len(strittig), len(beide)
    res["h3_afd"], res["h3_bestimmt"] = len(afd), len(afd_bestimmt)
    return res


# ------------------------------------------------------------------------- Validierung (F4, § 4)

POPULATION = "validierung-28/population.parquet"  # relativ zum Profilordner (gitignored)
VORHERSAGE = (
    MESSDATEN / "vorhersage.parquet"
)  # Ausgabe des Verfahrens, eingefroren vor der Kodierung
MAX_ABSCHNITT = 9000


def schluessel(top: str) -> str:
    return top.rsplit("/", 1)[-1]


def population_schreiben(d: Daten, pts: Sequence[Punkt]) -> pl.DataFrame:
    """Grundgesamtheit der Kodierung: Beschlüsse (nach result) mit gefundenem Abschnitt, Schicht = Form aus result."""
    rows = [
        {"id": schluessel(p.top), "schicht": form_aus_result(p.result)}
        for p in pts
        if ergebnis(p.result) in ENTSCHIEDEN and p.abschnitt is not None and p.abschnitt.strip()
    ]
    frame = pl.DataFrame(rows).sort("id")
    path = d.layout.root / POPULATION
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path)
    print(f"   Grundgesamtheit {frame.height} Punkte -> {path}")
    sizes = frame.group_by("schicht").len().sort("schicht")
    print("   " + ", ".join(f"{r['schicht']} {r['len']}" for r in sizes.iter_rows(named=True)))
    return frame


def anwesenheit(lines: Sequence[str]) -> str:
    start = next(
        (i for i, line in enumerate(lines) if line.strip().lower().startswith("anwesend")), None
    )
    if start is None:
        return ""
    out: list[str] = []
    for line in lines[start : start + 80]:
        if (
            re.match(r"\s*(weitere|sonstige) teilnehm|\s*entschuldigt|\s*es fehlt", line.lower())
            and out
        ):
            break
        out.append(line.rstrip())
    return "\n".join(out)[:2500]


def ausschnitt(p: Punkt, anwesend: str) -> str:
    sec = (p.abschnitt or "").strip("\n")
    if len(sec) > MAX_ABSCHNITT:
        sec = sec[:1500] + "\n[… Mitte ausgelassen …]\n" + sec[-7500:]
    head = f"[Anwesenheitsliste, gekürzt]\n{anwesend}\n\n" if anwesend else ""
    return head + "[Tagesordnungspunkt]\n" + sec


ART_NAME = {"rat": "Rat", "ausschuss": "Ausschuss", "bv": "Bezirksvertretung"}


def vorhersage(pts: Sequence[Punkt]) -> pl.DataFrame:
    """Was das Verfahren je Punkt sagt (Ebene A1, A2, B); eingefroren, bevor die Kodierer laufen."""
    rows = []
    for p in pts:
        st = p.stimmen
        pos = positionen_erweitert(st, p.art, p.datum, p.gremium_parteien) if st else {}
        form_n = st.form if st else None
        rows.append(
            {
                "id": schluessel(p.top),
                "art": p.art,
                "ergebnis_result": ergebnis(p.result),
                "form_result": form_aus_result(p.result),
                "ergebnis_a2": st.ergebnis if st and st.ergebnis else ergebnis(p.result),
                "form_a2": form_n or form_aus_result(p.result),
                "form_aus_niederschrift": form_n is not None,
                "positionen": json.dumps(pos, sort_keys=True),
                "gremium_parteien": json.dumps(list(p.gremium_parteien)),
                "vollstaendig": vollstaendig(p),
            }
        )
    return pl.DataFrame(rows).sort("id")


def auftraege(d: Daten) -> None:
    from georep.validation.codebook import load_codebook
    from georep.validation.paths import validation_paths
    from georep.validation.sample import read_sample
    from georep.validation.tasks import Document, build_task, write_assignment

    pts = niederschrift_punkte(d)
    pred = vorhersage(pts)
    pred.write_parquet(VORHERSAGE)
    sha = hashlib.sha256(VORHERSAGE.read_bytes()).hexdigest()
    print(f"   Vorhersage {pred.height} Punkte -> {VORHERSAGE}, sha256 {sha}")
    paths = validation_paths(d.settings, PROJEKT)
    codebook = load_codebook(paths.codebook, PROJEKT)
    sample = read_sample(paths, codebook)
    lines_by_file = {r["datei"]: ohne_kopf(r["text"]) for r in texte().iter_rows(named=True)}
    by_key = {schluessel(p.top): p for p in pts}
    documents = {}
    for key in sample.get_column("id").to_list():
        p = by_key[key]
        titel = (
            f"TOP {p.nummer}: {p.name} — {ART_NAME.get(p.art, p.art)} {p.gremium}, "
            f"Sitzung vom {p.datum:%d.%m.%Y}"
        )
        documents[key] = Document(key, titel, ausschnitt(p, anwesenheit(lines_by_file[p.datei])))
    for coder in ("A", "B"):
        tasks = [
            build_task(row, codebook, documents, {})[0] for row in sample.iter_rows(named=True)
        ]
        tasks.sort(key=lambda t: rank(codebook.sample.seed, f"{coder}|{t['id']}"))
        write_assignment(paths, coder, tasks, codebook, force=False)
        print(f"   Auftrag {coder}: {len(tasks)} Einheiten -> {paths.role(coder)}")
    laengen = sorted(len(doc.text) for doc in documents.values())
    print(f"   Ausschnitt: Median {laengen[len(laengen) // 2]} Zeichen, Maximum {laengen[-1]}")


def wilson(p: float, n: float, z: float = 1.959964) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def gewichtet(
    einheiten: Sequence[tuple[str, bool]],
    groessen: Mapping[str, int],
    stichprobe: Mapping[str, int],
) -> str:
    """Präzision in einer Teilmenge (Domäne) der geschichteten Stichprobe: Σ w·richtig / Σ w, w = N_h/n_h,
    Wilson bei Kishs n_eff (wie F4, docs/validierung.md § 5)."""
    if not einheiten:
        return "—"
    w = [groessen[h] / stichprobe[h] for h, _ in einheiten]
    p = sum(wi for wi, (_, ok) in zip(w, einheiten, strict=True) if ok) / sum(w)
    n_eff = sum(w) ** 2 / sum(wi * wi for wi in w)
    lo, hi = wilson(p, n_eff)
    roh = sum(ok for _, ok in einheiten)
    return f"{p:.3f} (Wilson {lo:.3f}–{hi:.3f}, n_eff {n_eff:.1f}; roh {roh}/{len(einheiten)})"


def guete(d: Daten) -> None:
    """Präzision A1, A2 und B gegen die geschlichteten Labels (validierung/28-abstimmungen/labels.csv)."""
    from georep.validation.paths import validation_paths

    paths = validation_paths(d.settings, PROJEKT)
    if not paths.labels.is_file():
        raise SystemExit(
            f"{paths.labels} fehlt: erst kodieren, dann `georep validate merge {PROJEKT}`"
        )
    labels: dict[str, dict[str, Any]] = defaultdict(dict)
    with paths.labels.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            labels[row["id"]][row["frage"]] = row["label"] or None
    with paths.sample.open(encoding="utf-8") as fh:
        sample = list(csv.DictReader(fh))
    groessen = {r["schicht"]: int(r["schicht_n"]) for r in sample}
    stichprobe = Counter(r["schicht"] for r in sample)
    pred = {r["id"]: r for r in pl.read_parquet(VORHERSAGE).iter_rows(named=True)}
    a1, a2, b, abschnitt_nein = [], [], [], 0
    for r in sample:
        key, h = r["id"], r["schicht"]
        lab, pr = labels.get(key, {}), pred[key]
        passt = lab.get("abschnitt") == "ja"
        abschnitt_nein += not passt
        erg, form = lab.get("ergebnis"), lab.get("form")
        if pr["form_result"] in ("einstimmig", "mehrheitlich") and passt:
            a1.append((h, pr["ergebnis_result"] == erg and pr["form_result"] == form))
        if pr["form_aus_niederschrift"]:
            a2.append((h, passt and pr["ergebnis_a2"] == erg and pr["form_a2"] == form))
        if pr["vollstaendig"]:
            ok = passt and pr["ergebnis_a2"] == erg and pr["form_a2"] == form
            if ok:
                genannt = json.loads(lab.get("stimmen") or "{}")
                genannt.pop("ANDERE", None)
                seite = "ja" if erg == "angenommen" else "nein"
                gremium = set(json.loads(pr["gremium_parteien"])) | set(genannt)
                soll = {
                    p: genannt.get(p) or (seite if lab.get("uebrige") == "mit_mehrheit" else None)
                    for p in gremium
                }
                ist = json.loads(pr["positionen"])
                ok = all(soll[p] is not None and soll[p] == ist.get(p) for p in gremium)
            b.append((h, ok))
    print(
        f"== Güte gegen {paths.labels} ({len(sample)} Einheiten, Abschnitt nicht passend: {abschnitt_nein})"
    )
    print(f"   A1 (Form aus result)              {gewichtet(a1, groessen, stichprobe)}")
    print(f"   A2 (Form aus der Niederschrift)   {gewichtet(a2, groessen, stichprobe)}")
    print(f"   B  (alle Positionen, vollständig) {gewichtet(b, groessen, stichprobe)}")


# ------------------------------------------------------------------- Fallzahlen der Hypothesen (§ 8.6)

MEHRHEIT = {"CDU", "GRUENE"}  # 2020-2025 und ab 2025, Plan § 8.4; Schlüssel wie Option 04
H1_VON, H1_BIS = dt.date(2021, 1, 1), dt.date(2025, 9, 14)


def antraege(d: Daten, frame: pl.DataFrame) -> pl.DataFrame:
    """Je Antrag (Dokumentart mit „antrag", ohne „anfrage") sein letzter entschiedener Ratsbeschluss."""
    corpus = pl.read_parquet(d.layout.corpus, columns=["id", "paper_type", "reference"])
    urheber = pl.read_parquet(d.layout.processed / "dokumente_urheber.parquet")
    art = pl.col("paper_type").str.to_lowercase()
    papers = corpus.filter(art.str.contains("antrag") & ~art.str.contains("anfrage")).join(
        urheber.select("id", "urheber_art", "parteien"), on="id", how="left"
    )
    rat = (
        frame.filter((pl.col("art") == "rat") & pl.col("ergebnis").is_in(ENTSCHIEDEN))
        .sort("datum", "top")
        .group_by("paper", maintain_order=True)
        .last()
    )
    return papers.join(rat, left_on="id", right_on="paper", how="inner").sort("id")


def fallzahlen(d: Daten, frame: pl.DataFrame) -> dict[str, int]:
    """Nur wie viele Einheiten die Hypothesen hätten, nicht ihr Ausgang (Plan § 8)."""
    a = antraege(d, frame)
    parteien = pl.col("parteien").list
    opposition = (
        (pl.col("urheber_art") == "Fraktion")
        & (parteien.len() > 0)
        & ~parteien.contains("CDU")
        & ~parteien.contains("GRUENE")
        & ~parteien.contains("AfD")
    )
    fenster = pl.col("datum").is_between(H1_VON, H1_BIS)
    h2 = a.filter(opposition & fenster)
    afd = a.filter(parteien.contains("AfD"))
    mehrheitlich_rat = frame.filter(
        (pl.col("art") == "rat")
        & (pl.col("form") == "mehrheitlich")
        & pl.col("datum").is_between(H1_VON, H1_BIS)
    )
    out = {
        "antraege_mit_ratsbeschluss": a.height,
        "h1_strittige_ratsbeschluesse": mehrheitlich_rat.height,
        "h1_davon_mit_niederschrift": mehrheitlich_rat.filter(pl.col("niederschrift")).height,
        "h2_oppositionsantraege": h2.height,
        "h3_afd_antraege_2020_2025": afd.height,
        "h3_afd_davon_mit_niederschrift": afd.filter(pl.col("niederschrift")).height,
    }
    for k, v in out.items():
        print(f"   {k:36s} {v:6d}")
    return out


# -------------------------------------------------------------------------------------- Hauptteil

BEFEHLE = {"abruf"}


def main(argv: Sequence[str]) -> None:
    befehl = argv[1] if len(argv) > 1 else "messen"
    d = laden()
    if befehl == "abruf":
        abruf(d)
        texte()
        return
    if befehl == "ebene-a":
        messen_ebene_a()
        return
    if befehl == "niederschriften":
        messen_niederschriften(d)
        return
    if befehl == "population":
        population_schreiben(d, niederschrift_punkte(d))
        return
    if befehl == "auftraege":
        auftraege(d)
        return
    if befehl == "guete":
        guete(d)
        return
    if befehl == "messen":
        a = messen_ebene_a()
        n = messen_niederschriften(d)
        stile()
        print(
            "== Abdeckung B für die ganze Hauptperiode (§ 8.2): B in den Niederschriften je Art × Anteil mit Niederschrift"
        )
        haupt = a["2020-2025"]
        summe = 0.0
        for art in ("rat", "ausschuss", "bv"):
            quote = n[art]["b_vollstaendig"] / n[art]["beschluesse"]
            mit = haupt[art]["mit_niederschrift"] / haupt[art]["beschluesse"]
            summe += haupt[art]["beschluesse"] * quote * mit
            print(
                f"   {art:9s} B {quote:.3f} × mit Niederschrift {mit:.3f} × {haupt[art]['beschluesse']} Beschlüsse"
            )
        print(
            f"   B gesamt {summe:.0f} / {haupt['alle']['beschluesse']} = {summe / haupt['alle']['beschluesse']:.3f} "
            "(Beiräte und Gremien ohne Zuordnung zählen mit 0)"
        )
        print("== Fallzahlen der Hypothesen (nur n, nicht ihr Ausgang)")
        fallzahlen(d, punkte(d))
        hochrechnung()
        return
    if befehl == "fallzahlen":
        print("== Fallzahlen der Hypothesen (nur n, nicht ihr Ausgang), Hauptperiode")
        fallzahlen(d, punkte(d))
        settings = load_settings(profile="duesseldorf-2025")
        layout = Layout.from_settings(settings)
        files = council_files(layout)
        d25 = Daten(
            settings,
            layout,
            dict(JsonlStore(files.meetings, OparlMeeting).load()),
            dict(JsonlStore(files.agenda_items, OparlAgendaItem).load()),
            d.consultations,  # die Beratungen sind je Body, nicht je Periode (Runbook § 1)
        )
        print("== dasselbe ab 2025 (Profil duesseldorf-2025; H28.1/H28.2 dort erst ab 2025-12-01)")
        fallzahlen(d25, punkte(d25))
        return
    raise SystemExit(f"unbekannter Befehl {befehl!r}")


if __name__ == "__main__":
    main(sys.argv)
