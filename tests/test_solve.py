import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from shiftfair.check import check, score
from shiftfair.solve import STATUSES, SolverBug, Status, build, solve
from tests.bruteforce import valid_schedules
from tests.helpers import person, problem, shift
from tests.strategies import tiny_problems


def test_a_simple_problem_gets_a_valid_schedule():
    p = problem([shift("am", "09:00", "12:00", needed=2), shift("pm", "12:00", "15:00")],
                [person("Ana", 6, am="yes", pm="yes"), person("Ben", 3, am="yes"), person("Cy", 3, pm="avoid")])
    result = solve(p)
    assert result.status == Status.FEASIBLE and result.found
    assert check(p, result.assignment) == [] and result.score == score(p, result.assignment)
    assert result.assignment["am"] == {"Ana", "Ben"}            # the only way to staff am


@pytest.mark.parametrize("people, why", [
    ([person("Ana", 6, am="yes")], "am needs 2 people, only Ana can"),
    ([person("Ana", 2, am="yes"), person("Ben", 6, am="yes")], "Ana's limit is below one shift"),
])
def test_proven_infeasible(people, why):
    result = solve(problem([shift("am", "09:00", "12:00", needed=2)], people))
    assert result.status == Status.INFEASIBLE and not result.found and result.score is None, why


def test_overlapping_shifts_are_never_both_given_to_one_person():
    # Ana is the only one who can do either shift, and they overlap by one minute.
    p = problem([shift("a", "09:00", "12:00"), shift("b", "11:59", "15:00")], [person("Ana", a="yes", b="yes")])
    assert solve(p).status == Status.INFEASIBLE
    p = problem([shift("a", "09:00", "12:00"), shift("b", "12:00", "15:00")], [person("Ana", a="yes", b="yes")])
    assert solve(p).status == Status.FEASIBLE                    # back to back is fine


def test_an_overnight_shift_overlaps_the_next_mornings_early_shift():
    import datetime as dt
    p = problem([shift("night", "22:00", "02:00"), shift("dawn", "01:00", "05:00", date=dt.date(2026, 12, 6))],
                [person("Ana", night="yes", dawn="yes")])
    assert solve(p).status == Status.INFEASIBLE


def test_one_constraint_per_start_time_covers_a_chain_of_overlaps():
    # a-b and b-c overlap, a and c don't: Ana may take a and c, never b with either.
    p = problem([shift("a", "09:00", "11:00"), shift("b", "10:00", "13:00"), shift("c", "12:00", "14:00")],
                [person("Ana", a="yes", b="yes", c="yes"), person("Ben", b="yes")])
    result = solve(p)
    assert result.assignment == {"a": {"Ana"}, "b": {"Ben"}, "c": {"Ana"}}


def test_variables_exist_only_for_available_pairs():
    p = problem([shift("a"), shift("b", "13:00", "14:00")], [person("Ana", a="yes"), person("Ben", a="no" and "yes")])
    assert set(build(p).x) == {("Ana", "a"), ("Ben", "a")}


def test_every_cp_sat_status_is_mapped_and_a_bad_schedule_is_caught(monkeypatch):
    from ortools.sat.python import cp_model
    assert set(STATUSES) == {cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.INFEASIBLE, cp_model.UNKNOWN}
    p = problem([shift("a")], [person("Ana", a="yes"), person("Ben", a="yes")])
    monkeypatch.setattr(cp_model.CpSolver, "boolean_value", lambda self, var: True)    # both on a shift needing 1
    with pytest.raises(SolverBug, match="a .* has 2 people but needs 1"):
        solve(p)


def test_running_out_of_time_is_unknown_not_infeasible():
    result = solve(problem([shift("a")], [person("Ana", a="yes")]), time_limit=0)
    assert result.status == Status.UNKNOWN and not result.found


@settings(deadline=None)
@given(tiny_problems())
def test_the_solver_agrees_with_brute_force(p):
    valid = valid_schedules(p)
    result = solve(p, workers=1)
    assert result.status == (Status.FEASIBLE if valid else Status.INFEASIBLE)
    if valid:
        assert check(p, result.assignment) == [] and result.assignment in valid


def test_a_schedule_found_before_the_time_limit_without_a_proof_is_still_used(monkeypatch):
    from ortools.sat.python import cp_model
    real = cp_model.CpSolver.solve
    monkeypatch.setattr(cp_model.CpSolver, "solve", lambda self, model: (real(self, model), cp_model.FEASIBLE)[1])
    result = solve(problem([shift("a")], [person("Ana", a="yes")]))
    assert result.status == Status.FEASIBLE and result.assignment == {"a": {"Ana"}}


@settings(deadline=None)
@given(st.data())
def test_the_model_accepts_exactly_the_schedules_the_checker_accepts(data):
    # Fix every variable to a drawn schedule and ask CP-SAT whether the model allows it. Drawn
    # schedules are random, or a valid one with one assignment flipped, so both answers are common.
    from ortools.sat.python import cp_model
    p = data.draw(tiny_problems())
    model = build(p)
    keys = sorted(model.x)
    valid = valid_schedules(p)
    if valid and data.draw(st.booleans()):
        base = data.draw(st.sampled_from(valid))
        on = {(name, s) for s, names in base.items() for name in names}
        flip = data.draw(st.sampled_from([None, *keys]))
        on ^= {flip} if flip is not None else set()
    else:
        on = {key for key in keys if data.draw(st.booleans())}
    for key in keys:
        model.cp.add(model.x[key] == int(key in on))
    allowed = cp_model.CpSolver().solve(model.cp) in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assignment = {s.id: frozenset(name for name, shift_id in on if shift_id == s.id) for s in p.shifts}
    assert allowed == (check(p, assignment) == [])
