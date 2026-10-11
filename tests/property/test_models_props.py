from __future__ import annotations

import datetime as dt
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from georep.oparl import OparlFile, OparlPaper
from georep.records import PaperRecord
from georep.settings import deep_merge
from georep.stores import PaperStore

text = st.text(alphabet="abcäöß /:.-_0123456789", min_size=0, max_size=20)
opt_text = st.one_of(st.none(), text)
aware = st.datetimes(
    min_value=dt.datetime(2000, 1, 1), max_value=dt.datetime(2030, 1, 1), timezones=st.just(dt.UTC)
)
files = st.builds(
    OparlFile,
    id=st.text(alphabet="abc/0123456789", min_size=1, max_size=15),
    file_name=opt_text,
    download_url=st.one_of(st.none(), text.map(lambda s: f"https://x/{s}.pdf")),
)
urls = st.lists(
    st.text(alphabet="abc/0123456789", min_size=1, max_size=12).map(lambda s: f"https://x/{s}"),
    max_size=3,
).map(tuple)
papers = st.builds(
    OparlPaper,
    id=st.text(alphabet="abc/0123456789", min_size=1, max_size=15),
    name=opt_text,
    reference=opt_text,
    date=st.one_of(st.none(), st.dates(dt.date(2000, 1, 1), dt.date(2030, 1, 1))),
    paper_type=opt_text,
    main_file=st.one_of(st.none(), files),
    auxiliary_file=st.lists(files, max_size=2),
    consultation=st.lists(
        st.fixed_dictionaries({}, optional={"organization": urls.map(list), "role": text}),
        max_size=3,
    ),
    originator_person=urls,
    originator_organization=urls,
    under_direction_of=urls,
    modified=st.one_of(st.none(), aware),
)


@given(paper=papers)
def test_oparl_paper_survives_a_json_roundtrip(paper: OparlPaper) -> None:
    again = OparlPaper.model_validate_json(paper.model_dump_json(by_alias=True))
    assert again == paper
    record = PaperRecord.from_oparl(paper)
    assert record.id == paper.id and record.date == paper.date
    assert record.has_originator == paper.has_originator
    assert record.consultation_organizations == paper.consultation_organizations
    assert PaperRecord.model_validate_json(record.model_dump_json()) == record
    primary = paper.main_file or (paper.auxiliary_file[0] if paper.auxiliary_file else None)
    assert record.download_url == (primary.download_url if primary else None)
    if record.download_url:
        assert record.file_name == record.download_url.rsplit("/", 1)[-1]
    # Option 04: die Urheberfelder bleiben Tupel, consultation wird zur sortierten URL-Menge
    assert again.originator_organization == paper.originator_organization
    assert paper.has_originator == bool(
        paper.originator_person or paper.originator_organization or paper.under_direction_of
    )
    expected = sorted({u for c in paper.consultation for u in c.get("organization", [])})
    assert list(paper.consultation_organizations) == expected


@given(
    records=st.lists(
        st.builds(
            PaperRecord,
            id=st.text(alphabet="abc0123456789", min_size=1, max_size=8),
            name=opt_text,
            modified=st.one_of(st.none(), aware),
            # Option 04: die vier URL-Tupel gehen durch JSONL und zurück, ohne Gleichheit zu verlieren
            originator_person=urls,
            originator_organization=urls,
            under_direction_of=urls,
            consultation_organizations=urls,
        ),
        max_size=12,
    )
)
def test_paper_store_roundtrip_and_idempotent_upsert(
    records: list[PaperRecord], tmp_path_factory: object
) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = PaperStore(Path(tmp) / "papers.jsonl")
        by_id = {r.id: r for r in records}  # spätere gewinnen, wie save() mit dict
        store.save(by_id.values())
        assert store.load() == dict(sorted(by_id.items()))
        again = store.upsert(by_id.values())
        assert (again.added, again.updated, again.unchanged) == (0, 0, len(by_id))
        assert store.load() == dict(sorted(by_id.items()))


ids = st.text(alphabet="abc0123456789", min_size=1, max_size=4)
records_st = st.lists(
    st.builds(PaperRecord, id=ids, name=opt_text, modified=st.one_of(st.none(), aware)), max_size=8
)


@given(before=records_st, incoming=records_st, deleted=st.lists(ids, max_size=6))
def test_upsert_keys_are_old_and_new_minus_deleted(
    before: list[PaperRecord], incoming: list[PaperRecord], deleted: list[str]
) -> None:
    """Option 07: nach ``upsert(records, deleted)`` ist der Schlüsselsatz ``(alt ∪ neu) \\ gelöscht``."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = PaperStore(Path(tmp) / "papers.jsonl")
        store.save(before)
        old_keys = {r.id for r in before}
        report = store.upsert(incoming, deleted=deleted)
        expected = (old_keys | {r.id for r in incoming}) - set(deleted)
        assert set(store.load()) == expected
        assert report.total == len(expected)
        assert report.removed == len((old_keys | {r.id for r in incoming}) & set(deleted))
        assert report.added + report.updated + report.unchanged == len(incoming)
        assert report.added <= report.total + report.removed


json_scalars = st.one_of(st.integers(), st.text(max_size=5), st.booleans())
json_dicts = st.recursive(
    st.dictionaries(st.text(alphabet="abc", min_size=1, max_size=2), json_scalars, max_size=3),
    lambda children: st.dictionaries(
        st.text(alphabet="abc", min_size=1, max_size=2), children, max_size=3
    ),
    max_leaves=12,
)


@given(a=json_dicts, b=json_dicts)
def test_deep_merge_laws(a: dict[str, object], b: dict[str, object]) -> None:
    assert deep_merge(a, {}) == a and deep_merge({}, b) == b
    merged = deep_merge(a, b)
    assert set(merged) == set(a) | set(b)
    for key, value in b.items():
        if not (isinstance(value, dict) and isinstance(a.get(key), dict)):
            assert merged[key] == value
    assert deep_merge(a, b) == deep_merge(deep_merge(a, b), b)  # idempotent in b


@given(
    paper=papers,
    start=st.dates(dt.date(2000, 1, 1), dt.date(2030, 1, 1)),
    end=st.one_of(st.none(), st.dates(dt.date(2000, 1, 1), dt.date(2030, 1, 1))),
)
def test_in_period_without_end_means_from_start_on(
    paper: OparlPaper, start: dt.date, end: dt.date | None
) -> None:
    """Ohne Ende zählt alles ab start; mit Ende genau das Intervall; ohne Datum nie (Fundament F4)."""
    inside = paper.in_period(start, end)
    if paper.date is None:
        assert not inside
    elif end is None:
        assert inside == (paper.date >= start)
    else:
        assert inside == (start <= paper.date <= end)
