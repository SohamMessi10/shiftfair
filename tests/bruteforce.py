"""An exhaustive reference solver for tiny problems: try every assignment, keep the valid ones.

It shares nothing with solve.py except the problem and the independent checker, so agreement
between the two on many random problems is evidence that the CP-SAT model is right."""

import itertools

from shiftfair.check import check, score


def schedules(problem):
    """Every assignment that gives each shift exactly `needed` available people, valid or not on
    the other rules. The checker then decides."""
    choices = [[frozenset(c) for c in itertools.combinations([p.name for p in problem.available_for(s.id)], s.needed)]
               for s in problem.shifts]
    for combination in itertools.product(*choices):
        yield dict(zip((s.id for s in problem.shifts), combination, strict=True))


def valid_schedules(problem):
    return [a for a in schedules(problem) if not check(problem, a)]


def best_scores(problem):
    """The valid schedules' scores, sorted best first: fairness, then preferences."""
    return sorted((score(problem, a) for a in valid_schedules(problem)),
                  key=lambda s: (s.squared_minutes, -s.prefer, s.avoid))
