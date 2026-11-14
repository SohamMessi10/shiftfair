"""Finding a schedule with CP-SAT.

The model has one Boolean per (person, shift) the person can do, true when they are assigned.
Availability is therefore enforced by construction: there is no variable to set for a shift
someone can't do. The other hard rules are linear constraints:

- staffing: the people on a shift add up to exactly `needed`;
- hour limit: the minutes a person works add up to at most their limit;
- no overlap: at any moment, a person is on at most one shift. Shifts are intervals, so it is
  enough to say this at each shift's start time: if two shifts overlap, one of them starts while
  the other is in progress. That gives one "at most one" constraint per start time and person,
  instead of one per pair of overlapping shifts.

Every schedule found is re-checked by `check.py`, which doesn't use any of this.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ortools.sat.python import cp_model

from shiftfair.check import Score, check, score
from shiftfair.model import Assignment, Problem


class Status(StrEnum):
    OPTIMAL = "optimal"          # a schedule, proven best under the objective
    FEASIBLE = "feasible"        # a schedule; no objective yet, or the time limit came before a proof
    INFEASIBLE = "infeasible"    # proven: no schedule satisfies the hard rules
    UNKNOWN = "unknown"          # the time limit came before either a schedule or a proof


class SolverBug(RuntimeError):
    """The solver returned a schedule the independent checker rejects: a bug in the model."""


@dataclass(frozen=True)
class Result:
    status: Status
    assignment: Assignment | None
    score: Score | None
    wall_time: float             # seconds the solver ran
    conflicts: int
    branches: int

    @property
    def found(self) -> bool:
        return self.assignment is not None


@dataclass
class Model:
    """A CP-SAT model of the problem's hard rules, and its assignment variables."""
    problem: Problem
    cp: cp_model.CpModel
    x: dict[tuple[str, str], cp_model.IntVar]       # (person, shift id) -> assigned

    def minutes(self, name: str):
        """The minutes a person works, as a linear expression."""
        return sum(self.problem.shift(s).duration * var for (p, s), var in self.x.items() if p == name)


def build(problem: Problem) -> Model:
    cp = cp_model.CpModel()
    x = {(person.name, shift_id): cp.new_bool_var(f"{person.name}@{shift_id}")
         for person in problem.people for shift_id in person.availability}
    model = Model(problem, cp, x)
    for shift in problem.shifts:
        cp.add(sum(x[p.name, shift.id] for p in problem.available_for(shift.id)) == shift.needed)
    for person in problem.people:
        cp.add(model.minutes(person.name) <= person.max_minutes)
        mine = [problem.shift(s) for s in person.availability]
        for start in sorted({s.begins for s in mine}):
            in_progress = [x[person.name, s.id] for s in mine if s.begins <= start < s.ends]
            if len(in_progress) > 1:
                cp.add_at_most_one(in_progress)
    return model


STATUSES = {cp_model.OPTIMAL: Status.FEASIBLE, cp_model.FEASIBLE: Status.FEASIBLE,
            cp_model.INFEASIBLE: Status.INFEASIBLE, cp_model.UNKNOWN: Status.UNKNOWN}


def solve(problem: Problem, *, time_limit: float = 10.0, workers: int = 8, seed: int = 0) -> Result:
    """A schedule satisfying every hard rule, if one exists. `time_limit` is in seconds."""
    model = build(problem)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    code = solver.solve(model.cp)
    if code not in STATUSES:              # MODEL_INVALID: also a bug in how the model is built
        raise SolverBug(f"CP-SAT returned {solver.status_name(code)}: {model.cp.validate()}")
    status = STATUSES[code]
    assignment = None
    if status in (Status.OPTIMAL, Status.FEASIBLE):
        chosen: dict[str, set[str]] = {s.id: set() for s in problem.shifts}
        for (name, shift_id), var in model.x.items():
            if solver.boolean_value(var):
                chosen[shift_id].add(name)
        assignment = {s: frozenset(names) for s, names in chosen.items()}
        violations = check(problem, assignment)
        if violations:
            raise SolverBug("the solver's schedule breaks rules: " + "; ".join(map(str, violations)))
    return Result(status, assignment, score(problem, assignment) if assignment is not None else None,
                  solver.wall_time, solver.num_conflicts, solver.num_branches)
