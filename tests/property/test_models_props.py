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
papers = st.builds(
    OparlPaper,
    id=st.text(alphabet="abc/0123456789", min_size=1, max_size=15),
    name=opt_text,
    reference=opt_text,
    date=st.one_of(st.none(), st.dates(dt.date(2000, 1, 1), dt.date(2030, 1, 1))),
    paper_type=opt_text,
    main_file=st.one_of(st.none(), files),
    auxiliary_file=st.lists(files, max_size=2),
    modified=st.one_of(st.none(), aware),
)


@given(paper=papers)
def test_oparl_paper_survives_a_json_roundtrip(paper: OparlPaper) -> None:
    again = OparlPaper.model_validate_json(paper.model_dump_json(by_alias=True))
    assert again == paper
    record = PaperRecord.from_oparl(paper)
    assert record.id == paper.id and record.date == paper.date
    primary = paper.main_file or (paper.auxiliary_file[0] if paper.auxiliary_file else None)
    assert record.download_url == (primary.download_url if primary else None)
    if record.download_url:
        assert record.file_name == record.download_url.rsplit("/", 1)[-1]


@given(
    records=st.lists(
        st.builds(
            PaperRecord,
            id=st.text(alphabet="abc0123456789", min_size=1, max_size=8),
            name=opt_text,
            modified=st.one_of(st.none(), aware),
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
