"""Reading shifts, availability and schedules from CSV files, strictly.

Every problem is reported with its file, row and column, and all of them are collected before
giving up, so one run shows everything to fix. Nothing is guessed: an unknown availability value,
a time like `9am`, or a duplicate name is an error, not a best effort. Row numbers are the
spreadsheet's: the header is row 1.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from shiftfair.model import Assignment, Person, Problem, Shift, Willingness

SHIFT_COLUMNS = ("shift", "date", "start", "end", "needed")
PERSON_COLUMNS = ("person", "max_hours")
SCHEDULE_COLUMNS = ("shift", "person")
UNAVAILABLE = {"", "no"}
WILLINGNESS = {w.value: w for w in Willingness}
TIME = re.compile(r"(\d{1,2}):(\d{2})")


@dataclass(frozen=True)
class Issue:
    file: str
    row: int | None           # None: about the whole file
    column: str | None
    message: str

    def __str__(self) -> str:
        where = self.file + (f", row {self.row}" if self.row is not None else "")
        where += f", column {self.column!r}" if self.column is not None else ""
        return f"{where}: {self.message}"


class InputError(Exception):
    """The inputs can't be used. `issues` lists every problem found."""

    def __init__(self, issues: list[Issue]):
        self.issues = issues
        super().__init__("\n".join(str(issue) for issue in issues))


def _rows(path: Path, issues: list[Issue]) -> tuple[list[str], Iterator[tuple[int, dict[str, str]]]] | None:
    """The normalized header (stripped, lowercase except shift ids) and the data rows with their
    line numbers. None if the file is unusable; the reason is in `issues`."""
    name = path.name
    try:
        text = path.read_text(encoding="utf-8-sig")       # tolerate the byte-order mark Excel writes
    except FileNotFoundError:
        issues.append(Issue(name, None, None, f"no such file: {path}"))
        return None
    except UnicodeDecodeError:
        issues.append(Issue(name, None, None, "isn't UTF-8 text: save it from your spreadsheet as CSV UTF-8"))
        return None
    except OSError as exc:
        issues.append(Issue(name, None, None, f"can't be read: {exc.strerror or exc}"))
        return None
    reader = csv.reader(text.splitlines(keepends=True), strict=True)
    try:
        header = next(reader, None)
    except csv.Error as exc:
        issues.append(Issue(name, 1, None, f"isn't valid CSV: {exc}"))
        return None
    if header is None or not any(cell.strip() for cell in header):
        issues.append(Issue(name, None, None, "is empty: the first row must name the columns"))
        return None
    header = [cell.strip() for cell in header]

    def rows():
        while True:
            try:
                cells = next(reader)
            except StopIteration:
                return
            except csv.Error as exc:
                issues.append(Issue(name, reader.line_num, None, f"isn't valid CSV: {exc}"))
                return
            line = reader.line_num
            if not any(cell.strip() for cell in cells):
                continue                                  # spreadsheets leave blank rows at the end
            if len(cells) != len(header):
                issues.append(Issue(name, line, None, f"has {len(cells)} cells but the header has {len(header)}"))
                continue
            yield line, dict(zip(header, (cell.strip() for cell in cells), strict=True))
    return header, rows()


def _check_columns(name: str, header: list[str], required: tuple[str, ...], issues: list[Issue],
                   extra_allowed: bool) -> bool:
    """Whether the header has exactly the required columns (case-insensitively), in any order."""
    lowered = [cell.lower() for cell in header]
    ok = True
    for column in required:
        if column not in lowered:
            issues.append(Issue(name, 1, None, f"has no {column!r} column (it has: {', '.join(header)})"))
            ok = False
    seen: set[str] = set()
    for cell in header:
        if not cell:
            issues.append(Issue(name, 1, None, "has a column with no name"))
            ok = False
        elif cell.lower() in seen:
            issues.append(Issue(name, 1, cell, "appears twice"))
            ok = False
        seen.add(cell.lower())
    if not extra_allowed:
        for cell in header:
            if cell and cell.lower() not in required:
                issues.append(Issue(name, 1, cell, f"isn't a column this file has (expected: {', '.join(required)})"))
                ok = False
    return ok


def _get(row: dict[str, str], column: str) -> str:
    """The value of a column found case-insensitively."""
    for key, value in row.items():
        if key.lower() == column:
            return value
    raise KeyError(column)


def _time(text: str) -> dt.time | None:
    match = TIME.fullmatch(text)
    if match is None:
        return None
    hour, minute = int(match[1]), int(match[2])
    return dt.time(hour, minute) if hour < 24 and minute < 60 else None


def _minutes_from_hours(text: str) -> int | None:
    """`4` -> 240, `2.5` -> 150, `1.25` -> 75. None unless it is a whole number of minutes >= 0."""
    try:
        hours = Decimal(text)
    except InvalidOperation:
        return None
    if not hours.is_finite() or hours < 0:
        return None
    minutes = hours * 60
    return int(minutes) if minutes == minutes.to_integral_value() else None


def load_shifts(path: Path, issues: list[Issue], ids: set[str] | None = None) -> list[Shift]:
    """The valid shifts. `ids`, if given, receives every shift id in the file, valid row or not, so
    the availability file isn't also blamed for a column whose shift row has its own error."""
    name = path.name
    loaded = _rows(path, issues)
    if loaded is None:
        return []
    header, rows = loaded
    if not _check_columns(name, header, SHIFT_COLUMNS, issues, extra_allowed=False):
        return []
    shifts: list[Shift] = []
    seen: dict[str, int] = {}
    count_rows = 0
    for line, row in rows:
        count_rows += 1
        shift_id, date, start, end, needed = (_get(row, c) for c in SHIFT_COLUMNS)
        bad = False
        if not shift_id:
            issues.append(Issue(name, line, "shift", "is empty: every shift needs an id"))
            bad = True
        elif shift_id.lower() in seen:
            issues.append(Issue(name, line, "shift", f"{shift_id!r} is already used on row {seen[shift_id.lower()]} "
                                                     "(ids are compared ignoring case)"))
            bad = True
        else:
            seen[shift_id.lower()] = line
        if ids is not None and shift_id:
            ids.add(shift_id)
        try:
            day = dt.date.fromisoformat(date) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) else None
        except ValueError:
            day = None
        if day is None:
            issues.append(Issue(name, line, "date", f"{date!r} isn't a date like 2026-12-05"))
            bad = True
        begins, finishes = _time(start), _time(end)
        for column, text, value in (("start", start, begins), ("end", end, finishes)):
            if value is None:
                issues.append(Issue(name, line, column, f"{text!r} isn't a 24-hour time like 09:00 or 21:30"))
                bad = True
        if begins is not None and begins == finishes:
            issues.append(Issue(name, line, "end", f"is the same as the start ({start}); "
                                                   "an end before the start means the next day"))
            bad = True
        count = int(needed) if re.fullmatch(r"\d+", needed) else None
        if count is None or count < 1:
            issues.append(Issue(name, line, "needed", f"{needed!r} isn't a whole number of people, 1 or more"))
            bad = True
        if not bad:
            shifts.append(Shift(shift_id, day, begins, finishes, count))
    if count_rows == 0:
        issues.append(Issue(name, None, None, "has no shifts: add one row per shift under the header"))
    return shifts


def load_people(path: Path, shifts: list[Shift], issues: list[Issue], shifts_name: str,
                all_ids: set[str] | None = None) -> list[Person]:
    name = path.name
    loaded = _rows(path, issues)
    if loaded is None:
        return []
    header, rows = loaded
    if not _check_columns(name, header, PERSON_COLUMNS, issues, extra_allowed=True):
        return []
    ids = {s.id: s.id for s in shifts}
    folded = {s.id.lower(): s.id for s in shifts}
    shift_columns: dict[str, str] = {}               # header cell -> shift id
    for cell in header:
        if cell.lower() in PERSON_COLUMNS:
            continue
        if cell in ids:
            shift_columns[cell] = cell
        elif cell.lower() in folded:
            issues.append(Issue(name, 1, cell, f"doesn't match the shift id {folded[cell.lower()]!r} in {shifts_name} "
                                               "exactly: check its capitals"))
        elif all_ids is None or cell not in all_ids:     # a shift whose row has an error is reported there
            issues.append(Issue(name, 1, cell, f"isn't a shift in {shifts_name}"))
    lowered = {cell.lower() for cell in header}
    for shift in shifts:
        if shift.id not in shift_columns and shift.id.lower() not in lowered:     # a capitals mismatch is reported above
            issues.append(Issue(name, 1, None, f"has no column for the shift {shift.id!r}: add one, even if "
                                               "nobody can do it"))
    people: list[Person] = []
    seen: dict[str, int] = {}
    count_rows = 0
    for line, row in rows:
        count_rows += 1
        person, max_hours = _get(row, "person"), _get(row, "max_hours")
        bad = False
        if not person:
            issues.append(Issue(name, line, "person", "is empty: every row needs a name"))
            bad = True
        elif person.lower() in seen:
            issues.append(Issue(name, line, "person", f"{person!r} is already on row {seen[person.lower()]} "
                                                      "(names are compared ignoring case)"))
            bad = True
        else:
            seen[person.lower()] = line
        limit = _minutes_from_hours(max_hours)
        if limit is None:
            issues.append(Issue(name, line, "max_hours", f"{max_hours!r} isn't a number of hours like 6 or 4.5, "
                                                         "0 or more, in whole minutes"))
            bad = True
        availability = {}
        for cell, shift_id in shift_columns.items():
            value = row[cell].lower()
            if value in UNAVAILABLE:
                continue
            if value not in WILLINGNESS:
                issues.append(Issue(name, line, cell, f"{row[cell]!r} isn't one of: prefer, yes, avoid, no "
                                                      "(or blank for no)"))
                bad = True
                continue
            availability[shift_id] = WILLINGNESS[value]
        if not bad:
            people.append(Person(person, limit, availability))
    if count_rows == 0:
        issues.append(Issue(name, None, None, "has no people: add one row per person under the header"))
    return people


def load_problem(shifts_path: Path, availability_path: Path) -> Problem:
    """Both files, checked together. Raises InputError listing every problem in either file."""
    issues: list[Issue] = []
    ids: set[str] = set()
    shifts = load_shifts(Path(shifts_path), issues, ids)
    people = load_people(Path(availability_path), shifts, issues, Path(shifts_path).name, ids)
    if issues:
        raise InputError(issues)
    return Problem(tuple(shifts), tuple(people))


def load_schedule(path: Path, problem: Problem) -> Assignment:
    """A schedule as rows of `shift,person` (other columns are ignored, so a schedule this tool
    wrote can be read back). Unknown shifts or people and repeated rows are input errors; whether
    the schedule obeys the rules is for check.py."""
    path = Path(path)
    name = path.name
    issues: list[Issue] = []
    loaded = _rows(path, issues)
    if loaded is None:
        raise InputError(issues)
    header, rows = loaded
    if not _check_columns(name, header, SCHEDULE_COLUMNS, issues, extra_allowed=True):
        raise InputError(issues)
    assignment: dict[str, set[str]] = {s.id: set() for s in problem.shifts}
    for line, row in rows:
        shift_id, person = _get(row, "shift"), _get(row, "person")
        if not problem.has_shift(shift_id):
            issues.append(Issue(name, line, "shift", f"{shift_id!r} isn't a shift in the problem"))
        elif not problem.has_person(person):
            issues.append(Issue(name, line, "person", f"{person!r} isn't anyone in the availability file"))
        elif person in assignment[shift_id]:
            issues.append(Issue(name, line, None, f"repeats {person} on {shift_id}"))
        else:
            assignment[shift_id].add(person)
    if issues:
        raise InputError(issues)
    return {shift_id: frozenset(names) for shift_id, names in assignment.items()}
