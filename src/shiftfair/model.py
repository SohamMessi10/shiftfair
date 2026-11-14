"""The scheduling problem as plain, immutable data.

Times are whole minutes on the local wall clock, counted from a fixed origin (day 1 of the
proleptic Gregorian calendar), so comparing and subtracting them is integer arithmetic. There are no
time zones: a club's schedule is local, and a shift that spans a daylight-saving change is measured
on the wall clock (documented as a limitation).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

MINUTES_PER_DAY = 24 * 60


class Willingness(StrEnum):
    """How a person marked a shift. Not marking it, or marking `no`, means unavailable."""
    PREFER = "prefer"
    YES = "yes"
    AVOID = "avoid"


@dataclass(frozen=True)
class Shift:
    id: str
    date: dt.date
    start: dt.time
    end: dt.time
    needed: int

    def __post_init__(self) -> None:
        if self.start == self.end:
            raise ValueError(f"shift {self.id} starts and ends at the same time")
        if self.needed < 1:
            raise ValueError(f"shift {self.id} must need at least 1 person")

    @property
    def duration(self) -> int:
        """Minutes. An end at or before the start is on the next day."""
        minutes = (self.end.hour * 60 + self.end.minute) - (self.start.hour * 60 + self.start.minute)
        return minutes if minutes > 0 else minutes + MINUTES_PER_DAY

    @property
    def begins(self) -> int:
        """The start, in minutes from the origin."""
        return self.date.toordinal() * MINUTES_PER_DAY + self.start.hour * 60 + self.start.minute

    @property
    def ends(self) -> int:
        return self.begins + self.duration

    def overlaps(self, other: Shift) -> bool:
        """Whether the two share any time. Back-to-back shifts (one ends as the other begins) don't."""
        return self.begins < other.ends and other.begins < self.ends

    def label(self) -> str:
        """For people: `sat-am (Sat 2026-12-05 09:00–12:00)`."""
        return f"{self.id} ({self.date:%a %Y-%m-%d} {self.start:%H:%M}–{self.end:%H:%M})"


@dataclass(frozen=True)
class Person:
    name: str
    max_minutes: int
    availability: Mapping[str, Willingness]      # shift id -> willingness, only for shifts they can do

    def can_do(self, shift_id: str) -> bool:
        return shift_id in self.availability


@dataclass(frozen=True)
class Problem:
    shifts: tuple[Shift, ...]
    people: tuple[Person, ...]
    _shifts: dict[str, Shift] = field(init=False, repr=False, compare=False)
    _people: dict[str, Person] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_shifts", {s.id: s for s in self.shifts})
        object.__setattr__(self, "_people", {p.name: p for p in self.people})
        if len(self._shifts) != len(self.shifts):
            raise ValueError("shift ids must be unique")
        if len(self._people) != len(self.people):
            raise ValueError("people's names must be unique")
        for person in self.people:
            unknown = sorted(set(person.availability) - set(self._shifts))
            if unknown:
                raise ValueError(f"{person.name} is available for unknown shifts: {', '.join(unknown)}")

    def shift(self, shift_id: str) -> Shift:
        return self._shifts[shift_id]

    def person(self, name: str) -> Person:
        return self._people[name]

    def has_shift(self, shift_id: str) -> bool:
        return shift_id in self._shifts

    def has_person(self, name: str) -> bool:
        return name in self._people

    def available_for(self, shift_id: str) -> list[Person]:
        return [p for p in self.people if p.can_do(shift_id)]

    @property
    def needed_minutes(self) -> int:
        """Total person-minutes the shifts need."""
        return sum(s.needed * s.duration for s in self.shifts)


Assignment = Mapping[str, frozenset[str]]      # shift id -> the names of the people working it


def format_minutes(minutes: int) -> str:
    """`90` -> `1.5 h`, `120` -> `2 h`, `100` -> `1 h 40 min`."""
    hours, rest = divmod(minutes, 60)
    if rest == 0:
        return f"{hours} h"
    if rest == 30:
        return f"{hours}.5 h"
    return f"{hours} h {rest} min" if hours else f"{rest} min"
