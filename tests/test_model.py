import datetime as dt

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shiftfair.model import MINUTES_PER_DAY, format_minutes
from tests.helpers import person, problem, shift


def test_duration_and_overnight_shifts():
    assert shift("a", "09:00", "12:30").duration == 210
    assert shift("b", "22:00", "01:00").duration == 180          # ends the next day
    assert shift("c", "00:00", "23:59").duration == MINUTES_PER_DAY - 1
    late = shift("d", "22:00", "01:00")
    assert late.ends - late.begins == 180


def test_back_to_back_shifts_do_not_overlap_but_shared_minutes_do():
    assert not shift("a", "09:00", "12:00").overlaps(shift("b", "12:00", "15:00"))
    assert shift("a", "09:00", "12:00").overlaps(shift("b", "11:59", "15:00"))
    night = shift("n", "22:00", "02:00")
    assert night.overlaps(shift("m", "01:00", "03:00", date=dt.date(2026, 12, 6)))
    assert not night.overlaps(shift("m", "01:00", "03:00"))          # same date: that is the morning before


times = st.builds(lambda h, m: f"{h:02d}:{m:02d}", st.integers(0, 23), st.sampled_from([0, 15, 30, 45, 59]))
shifts = st.builds(lambda se, d: shift("x", *se, date=dt.date(2026, 12, 5) + dt.timedelta(days=d)),
                   st.tuples(times, times).filter(lambda se: se[0] != se[1]), st.integers(0, 2))


@given(shifts, shifts)
def test_overlap_means_sharing_a_minute(a, b):
    minutes = lambda s: set(range(s.begins, s.ends))              # noqa: E731
    assert a.overlaps(b) == b.overlaps(a) == bool(minutes(a) & minutes(b))


def test_a_problem_refuses_duplicates_and_unknown_shifts():
    with pytest.raises(ValueError, match="shift ids"):
        problem([shift("a"), shift("a")], [])
    with pytest.raises(ValueError, match="names"):
        problem([shift("a")], [person("Ana"), person("Ana")])
    with pytest.raises(ValueError, match="Ana is available for unknown shifts: b"):
        problem([shift("a")], [person("Ana", b="yes")])


def test_lookups_and_needed_minutes():
    p = problem([shift("a", needed=2), shift("b", "22:00", "01:00")], [person("Ana", a="yes"), person("Ben")])
    assert p.shift("b").duration == 180 and p.person("Ben").max_minutes == 2400
    assert [x.name for x in p.available_for("a")] == ["Ana"] and p.available_for("b") == []
    assert p.needed_minutes == 2 * 180 + 180


@pytest.mark.parametrize("minutes, text", [(0, "0 h"), (120, "2 h"), (90, "1.5 h"), (100, "1 h 40 min"),
                                           (45, "45 min")])
def test_format_minutes(minutes, text):
    assert format_minutes(minutes) == text


def test_a_shift_must_have_a_length_and_need_someone():
    with pytest.raises(ValueError, match="starts and ends at the same time"):
        shift("a", "09:00", "09:00")
    with pytest.raises(ValueError, match="at least 1 person"):
        shift("a", needed=0)
