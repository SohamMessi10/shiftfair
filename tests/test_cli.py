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


# --- solve --------------------------------------------------------------------------------------

def test_solve_prints_and_writes_a_schedule_that_check_accepts(tmp_path, capsys):
    out = tmp_path / "schedule.csv"
    assert main(["solve", *inputs(tmp_path), "--out", str(out)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("feasible: a schedule that breaks no rule (found in ")
    assert lines[0].endswith(" s; checked independently)")
    assert lines[1] == "Sat 2026-12-05" and lines[4] == "Sun 2026-12-06" and lines[-1] == f"wrote {out}"
    assert main(["check", *inputs(tmp_path), str(out)]) == 0
    assert "schedule.csv: valid." in capsys.readouterr().out


def test_solve_reports_a_proven_infeasible_problem(tmp_path, capsys):
    shifts, _ = inputs(tmp_path)
    people = write_csv(tmp_path / "few.csv", [PEOPLE[0], PEOPLE[1]])        # only Ana: sat-am needs 2
    assert main(["solve", shifts, str(people), "--out", str(tmp_path / "x.csv")]) == 1
    assert capsys.readouterr().out.startswith("infeasible: no schedule can meet every rule (proven in ")
    assert not (tmp_path / "x.csv").exists()


@pytest.mark.parametrize("extra, message", [(["--time-limit", "0"], "--time-limit must be a positive number"),
                                            (["--workers", "0"], "--workers must be 1 or more")])
def test_solve_refuses_bad_options(tmp_path, capsys, extra, message):
    assert main(["solve", *inputs(tmp_path), *extra]) == 2
    assert message in capsys.readouterr().err


def test_solve_exits_2_for_bad_input_and_an_unwritable_output(tmp_path, capsys):
    shifts, people = inputs(tmp_path)
    assert main(["solve", shifts, str(tmp_path / "nope.csv")]) == 2
    assert "nope.csv: no such file" in capsys.readouterr().err
    assert main(["solve", shifts, people, "--out", str(tmp_path / "no-such-dir" / "s.csv")]) == 2
    assert "can't write" in capsys.readouterr().err


def test_solve_exits_3_if_the_checker_rejects_the_solvers_schedule(tmp_path, capsys, monkeypatch):
    from ortools.sat.python import cp_model
    monkeypatch.setattr(cp_model.CpSolver, "boolean_value", lambda self, var: True)
    assert main(["solve", *inputs(tmp_path)]) == 3
    assert "internal error, please report it: the solver's schedule breaks rules" in capsys.readouterr().err


def test_solve_says_unknown_when_time_runs_out(tmp_path, capsys):
    assert main(["solve", *inputs(tmp_path), "--time-limit", "1e-9"]) == 1
    assert capsys.readouterr().out == ("unknown: no schedule found within 1e-09 s, and no proof that none exists; "
                                       "try a longer --time-limit\n")
