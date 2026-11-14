"""Hypothesis strategies for tiny problems that a brute force can solve completely."""

import datetime as dt

from hypothesis import strategies as st

from shiftfair.model import Person, Problem, Shift, Willingness

DAY = dt.date(2026, 12, 5)


@st.composite
def tiny_problems(draw, max_shifts=4, max_people=4):
    """Up to 4 shifts on one or two days (so they often overlap) and up to 4 people with random
    availability and hour limits."""
    shifts = []
    for i in range(draw(st.integers(1, max_shifts))):
        start = draw(st.integers(0, 47)) * 30            # minutes, on a half-hour grid over two days
        length = draw(st.sampled_from([60, 90, 120, 180, 240]))
        day = DAY + dt.timedelta(days=start // 1440)
        start %= 1440
        end = (start + length) % 1440
        shifts.append(Shift(f"s{i}", day, dt.time(start // 60, start % 60), dt.time(end // 60, end % 60),
                            draw(st.integers(1, 2))))
    people = []
    for i in range(draw(st.integers(1, max_people))):
        availability = {}
        for s in shifts:
            mark = draw(st.sampled_from([None, "yes", "prefer", "avoid"]))
            if mark is not None:
                availability[s.id] = Willingness(mark)
        people.append(Person(f"p{i}", draw(st.sampled_from([0, 120, 240, 360, 480, 600, 6000, 6000])), availability))
    return Problem(tuple(shifts), tuple(people))
