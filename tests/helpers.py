"""Building problems and CSV files for tests."""

import datetime as dt

from shiftfair.model import Person, Problem, Shift, Willingness

DAY = dt.date(2026, 12, 5)        # a Saturday


def shift(id, start="09:00", end="12:00", needed=1, date=DAY):
    return Shift(id, date, dt.time.fromisoformat(start), dt.time.fromisoformat(end), needed)


def person(name, max_hours=40, **availability):
    """`person("Ana", 6, sat_am="prefer")`: keyword names use _ for -."""
    return Person(name, round(max_hours * 60), {k.replace("_", "-"): Willingness(v) for k, v in availability.items()})


def problem(shifts, people):
    return Problem(tuple(shifts), tuple(people))


def write_csv(path, rows):
    path.write_text("".join(",".join(row) + "\n" for row in rows), encoding="utf-8")
    return path
