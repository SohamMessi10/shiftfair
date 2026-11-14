"""Showing and saving a schedule."""

from __future__ import annotations

import csv
import io
from itertools import groupby
from pathlib import Path

from shiftfair.check import minutes_worked
from shiftfair.model import Assignment, Problem, format_minutes

SCHEDULE_HEADER = ["shift", "date", "start", "end", "person"]


def schedule_lines(problem: Problem, assignment: Assignment) -> list[str]:
    """The schedule by day, then each person's hours."""
    lines = []
    shifts = sorted(problem.shifts, key=lambda s: (s.begins, s.id))
    width = max(len(s.id) for s in shifts)
    for day, todays in groupby(shifts, key=lambda s: s.date):
        lines.append(f"{day:%a %Y-%m-%d}")
        for shift in todays:
            names = ", ".join(sorted(assignment.get(shift.id, ()))) or "(nobody)"
            lines.append(f"  {shift.start:%H:%M}–{shift.end:%H:%M}  {shift.id:<{width}}  {names}")
    worked = minutes_worked(problem, assignment)
    lines.append("hours: " + "  ".join(f"{name} {format_minutes(minutes)}"
                                       for name, minutes in sorted(worked.items(), key=lambda kv: (-kv[1], kv[0]))))
    return lines


def schedule_csv(problem: Problem, assignment: Assignment) -> str:
    """One row per person per shift, in time order. `shiftfair check` reads it back."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(SCHEDULE_HEADER)
    for shift in sorted(problem.shifts, key=lambda s: (s.begins, s.id)):
        for name in sorted(assignment.get(shift.id, ())):
            writer.writerow([shift.id, shift.date.isoformat(), f"{shift.start:%H:%M}", f"{shift.end:%H:%M}", name])
    return out.getvalue()


def write_schedule(path: Path, problem: Problem, assignment: Assignment) -> None:
    Path(path).write_text(schedule_csv(problem, assignment), encoding="utf-8")
