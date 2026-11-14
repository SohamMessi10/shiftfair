import pytest

from shiftfair import __version__
from shiftfair.cli import main


def test_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"shiftfair {__version__}\n"


def test_the_solver_is_installed():
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    x = model.new_bool_var("x")
    model.add(x == 1)
    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.OPTIMAL and solver.boolean_value(x)


# --- check --------------------------------------------------------------------------------------

from tests.helpers import write_csv  # noqa: E402

SHIFTS = [["shift", "date", "start", "end", "needed"],
          ["sat-am", "2026-12-05", "09:00", "12:00", "2"],
          ["sat-late", "2026-12-05", "22:00", "01:00", "1"],
          ["sun-am", "2026-12-06", "00:30", "03:00", "1"]]
PEOPLE = [["person", "max_hours", "sat-am", "sat-late", "sun-am"],
          ["Ana", "6", "prefer", "no", "yes"],
          ["Ben", "4.5", "yes", "avoid", ""],
          ["Cy", "3", "yes", "yes", "prefer"]]


def inputs(tmp_path):
    return str(write_csv(tmp_path / "shifts.csv", SHIFTS)), str(write_csv(tmp_path / "people.csv", PEOPLE))


def test_check_summarizes_valid_inputs(tmp_path, capsys):
    assert main(["check", *inputs(tmp_path)]) == 0
    assert capsys.readouterr().out == ("shifts.csv: 3 shifts over 2 days, needing 11.5 h of work in total\n"
                                       "people.csv: 3 people, willing to work up to 13.5 h in total\n")


def test_check_accepts_a_valid_schedule(tmp_path, capsys):
    schedule = write_csv(tmp_path / "s.csv", [["shift", "person"], ["sat-am", "Ana"], ["sat-am", "Ben"],
                                              ["sat-late", "Cy"], ["sun-am", "Ana"]])
    assert main(["check", *inputs(tmp_path), str(schedule)]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == (
        "s.csv: valid. Hours from 3 h to 5.5 h; 1 preferred and 0 avoided assignments")


def test_check_lists_every_broken_rule_and_exits_1(tmp_path, capsys):
    schedule = write_csv(tmp_path / "s.csv", [["shift", "person"], ["sat-am", "Ana"], ["sat-am", "Cy"],
                                              ["sat-late", "Cy"], ["sun-am", "Cy"]])
    assert main(["check", *inputs(tmp_path), str(schedule)]) == 1
    assert capsys.readouterr().out.splitlines()[2:] == [
        "s.csv: breaks 2 rules:",
        "  max hours: Cy works 8.5 h, over their limit of 3 h",
        "  overlap: Cy is on sat-late (Sat 2026-12-05 22:00–01:00) and sun-am (Sun 2026-12-06 00:30–03:00), "
        "which overlap"]


def test_check_exits_2_listing_every_input_problem(tmp_path, capsys):
    shifts, people = inputs(tmp_path)
    write_csv(tmp_path / "people.csv", PEOPLE + [["Di", "x", "maybe", "", ""]])
    assert main(["check", shifts, people]) == 2
    err = capsys.readouterr().err.splitlines()
    assert err == ["shiftfair: the input can't be used (2 problems):",
                   "  people.csv, row 5, column 'max_hours': 'x' isn't a number of hours like 6 or 4.5, 0 or more, "
                   "in whole minutes",
                   "  people.csv, row 5, column 'sat-am': 'maybe' isn't one of: prefer, yes, avoid, no "
                   "(or blank for no)"]
    write_csv(tmp_path / "people.csv", PEOPLE)
    assert main(["check", shifts, people, str(tmp_path / "missing.csv")]) == 2
    assert "missing.csv: no such file" in capsys.readouterr().err


def test_a_command_is_required(capsys):
    with pytest.raises(SystemExit) as info:
        main([])
    assert info.value.code == 2 and "COMMAND" in capsys.readouterr().err
