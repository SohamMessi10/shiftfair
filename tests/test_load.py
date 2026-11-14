import datetime as dt

import pytest

from shiftfair.load import InputError, load_problem, load_schedule
from shiftfair.model import Willingness
from tests.helpers import write_csv

SHIFTS = [["shift", "date", "start", "end", "needed"],
          ["sat-am", "2026-12-05", "09:00", "12:00", "2"],
          ["sat-late", "2026-12-05", "22:00", "01:00", "1"]]
PEOPLE = [["person", "max_hours", "sat-am", "sat-late"],
          ["Ana", "6", "prefer", "no"],
          ["Ben", "4.5", "Yes", ""],
          ["Cy", "0", "avoid", "yes"]]


def files(tmp_path, shifts=SHIFTS, people=PEOPLE):
    return write_csv(tmp_path / "shifts.csv", shifts), write_csv(tmp_path / "people.csv", people)


def issues(tmp_path, shifts=SHIFTS, people=PEOPLE):
    with pytest.raises(InputError) as info:
        load_problem(*files(tmp_path, shifts, people))
    return [str(issue) for issue in info.value.issues]


def test_valid_files_load_exactly(tmp_path):
    p = load_problem(*files(tmp_path))
    assert [(s.id, s.date, s.start, s.end, s.needed, s.duration) for s in p.shifts] == [
        ("sat-am", dt.date(2026, 12, 5), dt.time(9), dt.time(12), 2, 180),
        ("sat-late", dt.date(2026, 12, 5), dt.time(22), dt.time(1), 1, 180)]
    assert [(x.name, x.max_minutes, dict(x.availability)) for x in p.people] == [
        ("Ana", 360, {"sat-am": Willingness.PREFER}),
        ("Ben", 270, {"sat-am": Willingness.YES}),
        ("Cy", 0, {"sat-am": Willingness.AVOID, "sat-late": Willingness.YES})]


def test_spreadsheet_habits_are_tolerated(tmp_path):
    shifts = [["Shift ", " DATE", "start", "End", "needed"], *SHIFTS[1:], ["", "", "", "", ""]]
    shifts_path, people_path = files(tmp_path, shifts)
    people_path.write_bytes(b"\xef\xbb\xbf" + people_path.read_bytes().replace(b"\n", b"\r\n"))   # BOM, CRLF
    p = load_problem(shifts_path, people_path)
    assert len(p.shifts) == 2 and [x.name for x in p.people] == ["Ana", "Ben", "Cy"]


def test_quoted_cells_with_commas_are_one_cell(tmp_path):
    shifts_path, people_path = files(tmp_path)
    people_path.write_text('person,max_hours,sat-am,sat-late\n"Lee, Jo",2,yes,no\n', encoding="utf-8")
    assert load_problem(shifts_path, people_path).people[0].name == "Lee, Jo"


@pytest.mark.parametrize("row, message", [
    (["", "2026-12-05", "09:00", "12:00", "1"], "row 4, column 'shift': is empty"),
    (["SAT-AM", "2026-12-05", "09:00", "12:00", "1"], "row 4, column 'shift': 'SAT-AM' is already used on row 2"),
    (["x", "2026-12-5", "09:00", "12:00", "1"], "row 4, column 'date': '2026-12-5' isn't a date like 2026-12-05"),
    (["x", "2026-02-30", "09:00", "12:00", "1"], "row 4, column 'date': '2026-02-30' isn't a date"),
    (["x", "05/12/2026", "09:00", "12:00", "1"], "row 4, column 'date': '05/12/2026' isn't a date"),
    (["x", "2026-12-05", "9am", "12:00", "1"], "row 4, column 'start': '9am' isn't a 24-hour time"),
    (["x", "2026-12-05", "09:00", "24:00", "1"], "row 4, column 'end': '24:00' isn't a 24-hour time"),
    (["x", "2026-12-05", "09:00", "12:60", "1"], "row 4, column 'end': '12:60' isn't a 24-hour time"),
    (["x", "2026-12-05", "09:00", "09:00", "1"], "row 4, column 'end': is the same as the start (09:00)"),
    (["x", "2026-12-05", "09:00", "12:00", "0"], "row 4, column 'needed': '0' isn't a whole number of people"),
    (["x", "2026-12-05", "09:00", "12:00", "1.5"], "row 4, column 'needed': '1.5' isn't a whole number"),
    (["x", "2026-12-05", "09:00", "12:00"], "row 4: has 4 cells but the header has 5"),
])
def test_each_bad_shift_value_is_named(tmp_path, row, message):
    found = issues(tmp_path, SHIFTS + [row])
    assert [f"shifts.csv, {message}" in issue for issue in found].count(True) == 1, found


@pytest.mark.parametrize("row, message", [
    (["", "3", "yes", "no"], "row 5, column 'person': is empty"),
    (["ANA", "3", "yes", "no"], "row 5, column 'person': 'ANA' is already on row 2"),
    (["Di", "-1", "yes", "no"], "row 5, column 'max_hours': '-1' isn't a number of hours"),
    (["Di", "four", "yes", "no"], "row 5, column 'max_hours': 'four' isn't a number of hours"),
    (["Di", "1.01", "yes", "no"], "row 5, column 'max_hours': '1.01' isn't a number of hours"),
    (["Di", "nan", "yes", "no"], "row 5, column 'max_hours': 'nan' isn't a number of hours"),
    (["Di", "3", "maybe", "no"], "row 5, column 'sat-am': 'maybe' isn't one of: prefer, yes, avoid, no"),
])
def test_each_bad_availability_value_is_named(tmp_path, row, message):
    found = issues(tmp_path, people=PEOPLE + [row])
    assert [f"people.csv, {message}" in issue for issue in found].count(True) == 1, found


def test_columns_must_match_the_shifts(tmp_path):
    assert issues(tmp_path, people=[["person", "max_hours", "Sat-am", "sun", "sat-late"], ["Ana", "1", "", "", ""]]) == [
        "people.csv, row 1, column 'Sat-am': doesn't match the shift id 'sat-am' in shifts.csv exactly: "
        "check its capitals",
        "people.csv, row 1, column 'sun': isn't a shift in shifts.csv"]
    assert issues(tmp_path, people=[["person", "max_hours", "sat-am"], ["Ana", "1", ""]]) == [
        "people.csv, row 1: has no column for the shift 'sat-late': add one, even if nobody can do it"]


def test_a_shift_row_with_its_own_error_doesnt_also_fail_its_availability_column(tmp_path):
    shifts = SHIFTS + [["sun", "2026-12-06", "9", "12:00", "1"]]
    people = [["person", "max_hours", "sat-am", "sat-late", "sun"], ["Ana", "1", "", "", "yes"]]
    assert issues(tmp_path, shifts, people) == [
        "shifts.csv, row 4, column 'start': '9' isn't a 24-hour time like 09:00 or 21:30"]


@pytest.mark.parametrize("header, message", [
    (["shift", "date", "start", "end"], "row 1: has no 'needed' column (it has: shift, date, start, end)"),
    (["shift", "date", "start", "end", "needed", "notes"], "row 1, column 'notes': isn't a column this file has"),
    (["shift", "date", "start", "end", "needed", "Date"], "row 1, column 'Date': appears twice"),
    (["shift", "date", "start", "end", "needed", ""], "row 1: has a column with no name"),
])
def test_bad_shift_headers(tmp_path, header, message):
    found = issues(tmp_path, [header])
    assert any(f"shifts.csv, {message}" in issue for issue in found), found


def test_missing_empty_and_unreadable_files(tmp_path):
    shifts_path, people_path = files(tmp_path)
    with pytest.raises(InputError, match="nope.csv: no such file"):
        load_problem(tmp_path / "nope.csv", people_path)
    (tmp_path / "empty.csv").write_text("")
    with pytest.raises(InputError, match="empty.csv: is empty: the first row must name the columns"):
        load_problem(tmp_path / "empty.csv", people_path)
    assert issues(tmp_path, SHIFTS[:1], PEOPLE[:1]) == [
        "shifts.csv: has no shifts: add one row per shift under the header",
        "people.csv, row 1, column 'sat-am': isn't a shift in shifts.csv",
        "people.csv, row 1, column 'sat-late': isn't a shift in shifts.csv",
        "people.csv: has no people: add one row per person under the header"]
    (tmp_path / "latin.csv").write_bytes("person,max_hours\nJosé,3\n".encode("latin-1"))
    with pytest.raises(InputError, match="latin.csv: isn't UTF-8 text"):
        load_problem(shifts_path, tmp_path / "latin.csv")
    (tmp_path / "quote.csv").write_text('person,max_hours\n"Ana,3\n', encoding="utf-8")
    with pytest.raises(InputError, match="quote.csv, row .*: isn't valid CSV"):
        load_problem(shifts_path, tmp_path / "quote.csv")


def test_problems_in_both_files_are_reported_together(tmp_path):
    found = issues(tmp_path, SHIFTS + [["x", "2026-12-05", "09:00", "12:00", "none"]],
                   PEOPLE + [["Di", "lots", "yes", "no"]])
    assert len(found) == 2 and found[0].startswith("shifts.csv") and found[-1].startswith("people.csv")


def test_load_schedule(tmp_path):
    p = load_problem(*files(tmp_path))
    path = write_csv(tmp_path / "s.csv", [["shift", "person", "date"], ["sat-am", "Ana", "x"], ["sat-am", "Ben", "x"]])
    assert load_schedule(path, p) == {"sat-am": frozenset({"Ana", "Ben"}), "sat-late": frozenset()}
    bad = write_csv(tmp_path / "b.csv", [["shift", "person"], ["sun", "Ana"], ["sat-am", "Zed"],
                                         ["sat-am", "Ana"], ["sat-am", "Ana"]])
    with pytest.raises(InputError) as info:
        load_schedule(bad, p)
    assert [str(i) for i in info.value.issues] == [
        "b.csv, row 2, column 'shift': 'sun' isn't a shift in the problem",
        "b.csv, row 3, column 'person': 'Zed' isn't anyone in the availability file",
        "b.csv, row 5: repeats Ana on sat-am"]
    with pytest.raises(InputError, match="has no 'person' column"):
        load_schedule(write_csv(tmp_path / "c.csv", [["shift", "who"]]), p)
