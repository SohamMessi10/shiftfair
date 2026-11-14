"""An independent check of a schedule against the hard rules, and its score.

This module doesn't use OR-Tools on purpose. Every schedule the solver returns is checked here, so a
mistake in how the solver model is written shows up as a violation instead of a silently wrong
schedule. The score is recomputed here too, and compared with what the solver reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from shiftfair.model import Assignment, Problem, Willingness, format_minutes


class Rule(StrEnum):
    UNKNOWN = "unknown"              # a shift or person that isn't in the problem
    AVAILABILITY = "availability"
    STAFFING = "staffing"
    MAX_HOURS = "max hours"
    OVERLAP = "overlap"


@dataclass(frozen=True, order=True)
class Violation:
    rule: Rule
    message: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.message}"


@dataclass(frozen=True)
class Score:
    """What the solver optimizes, in order: fairness first, then preferences."""
    squared_minutes: int      # sum over people of (minutes worked)^2; lower is fairer
    prefer: int               # assignments to shifts the person marked `prefer`
    avoid: int                # assignments to shifts the person marked `avoid`


def minutes_worked(problem: Problem, assignment: Assignment) -> dict[str, int]:
    """Minutes per person (everyone, including people with no shifts), ignoring unknown names."""
    worked = {p.name: 0 for p in problem.people}
    for shift_id, names in assignment.items():
        if problem.has_shift(shift_id):
            for name in names:
                if name in worked:
                    worked[name] += problem.shift(shift_id).duration
    return worked


def check(problem: Problem, assignment: Assignment) -> list[Violation]:
    """Every broken hard rule, sorted. An empty list means the schedule is valid. A shift missing
    from `assignment` counts as having nobody."""
    found: list[Violation] = []
    for shift_id in sorted(assignment):
        if not problem.has_shift(shift_id):
            found.append(Violation(Rule.UNKNOWN, f"{shift_id!r} isn't a shift in the problem"))
            continue
        for name in sorted(assignment[shift_id]):
            if not problem.has_person(name):
                found.append(Violation(Rule.UNKNOWN, f"{name!r} on {shift_id} isn't anyone in the problem"))
            elif not problem.person(name).can_do(shift_id):
                found.append(Violation(Rule.AVAILABILITY,
                                       f"{name} isn't available for {problem.shift(shift_id).label()}"))
    for shift in problem.shifts:
        count = len(assignment.get(shift.id, ()))
        if count != shift.needed:
            found.append(Violation(Rule.STAFFING, f"{shift.label()} has {count} of the {shift.needed} people it needs"
                                   if count < shift.needed else
                                   f"{shift.label()} has {count} people but needs {shift.needed}"))
    worked = minutes_worked(problem, assignment)
    for person in problem.people:
        if worked[person.name] > person.max_minutes:
            found.append(Violation(Rule.MAX_HOURS, f"{person.name} works {format_minutes(worked[person.name])}, "
                                                   f"over their limit of {format_minutes(person.max_minutes)}"))
    for person in problem.people:
        mine = sorted((problem.shift(s) for s, names in assignment.items()
                       if person.name in names and problem.has_shift(s)), key=lambda s: (s.begins, s.id))
        for i, first in enumerate(mine):
            for second in mine[i + 1:]:
                if first.overlaps(second):
                    found.append(Violation(Rule.OVERLAP,
                                           f"{person.name} is on {first.label()} and {second.label()}, which overlap"))
    return sorted(found)


def score(problem: Problem, assignment: Assignment) -> Score:
    """The objective of a schedule, computed from scratch. Assumes it is valid (see `check`)."""
    worked = minutes_worked(problem, assignment)
    prefer = avoid = 0
    for shift_id, names in assignment.items():
        for name in names:
            if problem.has_person(name):
                willingness = problem.person(name).availability.get(shift_id)
                prefer += willingness == Willingness.PREFER
                avoid += willingness == Willingness.AVOID
    return Score(sum(m * m for m in worked.values()), prefer, avoid)
