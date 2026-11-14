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
