"""The `shiftfair` command.

Exit codes: 0 done (inputs valid, a valid schedule given or found); 1 the schedule breaks a rule,
or no schedule was found; 2 the inputs can't be used (a missing file, a malformed value) or the
command line is wrong; 3 an internal error: the solver's schedule failed the independent check.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shiftfair import __version__

EXIT_OK, EXIT_INVALID, EXIT_USAGE, EXIT_BUG = 0, 1, 2, 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shiftfair",
        description="Schedule volunteers to shifts: every hard rule holds, hours are spread as evenly as possible, "
                    "and an impossible schedule comes with the reason.")
    parser.add_argument("--version", action="version", version=f"shiftfair {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    check = commands.add_parser("check", help="check the input files, and a schedule if given",
                                description="Check that the shifts and availability files can be used and, given a "
                                            "schedule (rows of shift,person), that it breaks no rule.")
    check.add_argument("shifts", type=Path, help="shifts CSV: shift,date,start,end,needed")
    check.add_argument("availability", type=Path, help="availability CSV: person,max_hours and a column per shift")
    check.add_argument("schedule", type=Path, nargs="?", help="a schedule CSV with shift and person columns")

    solve = commands.add_parser("solve", help="find a schedule that breaks no rule",
                                description="Find a schedule that meets every hard rule: availability, exact "
                                            "staffing, hour limits, no overlapping shifts.")
    solve.add_argument("shifts", type=Path, help="shifts CSV: shift,date,start,end,needed")
    solve.add_argument("availability", type=Path, help="availability CSV: person,max_hours and a column per shift")
    solve.add_argument("--out", type=Path, metavar="CSV", help="also write the schedule here")
    solve.add_argument("--time-limit", type=float, default=10.0, metavar="SECONDS",
                       help="stop searching after this long (default 10)")
    solve.add_argument("--workers", type=int, default=8, metavar="N", help="solver threads (default 8)")
    return parser


def check_command(args) -> int:
    from shiftfair.check import check, minutes_worked, score
    from shiftfair.load import InputError, load_problem, load_schedule
    from shiftfair.model import format_minutes

    try:
        problem = load_problem(args.shifts, args.availability)
        assignment = load_schedule(args.schedule, problem) if args.schedule is not None else None
    except InputError as exc:
        _print_issues(exc)
        return EXIT_USAGE
    days = len({s.date for s in problem.shifts})
    capacity = sum(p.max_minutes for p in problem.people)
    print(f"{args.shifts.name}: {len(problem.shifts)} shifts over {days} day{'s' * (days != 1)}, "
          f"needing {format_minutes(problem.needed_minutes)} of work in total")
    print(f"{args.availability.name}: {len(problem.people)} people, willing to work up to "
          f"{format_minutes(capacity)} in total")
    if assignment is None:
        return EXIT_OK
    violations = check(problem, assignment)
    if violations:
        print(f"{args.schedule.name}: breaks {len(violations)} rule{'s' * (len(violations) != 1)}:")
        for violation in violations:
            print(f"  {violation}")
        return EXIT_INVALID
    result = score(problem, assignment)
    worked = minutes_worked(problem, assignment)
    print(f"{args.schedule.name}: valid. Hours from {format_minutes(min(worked.values()))} to "
          f"{format_minutes(max(worked.values()))}; {result.prefer} preferred and {result.avoid} avoided "
          f"assignment{'s' * (result.avoid != 1)}")
    return EXIT_OK


def _load(args):
    """The problem, or None after printing why it can't be used."""
    from shiftfair.load import InputError, load_problem
    try:
        return load_problem(args.shifts, args.availability)
    except InputError as exc:
        _print_issues(exc)
        return None


def _print_issues(exc) -> None:
    print(f"shiftfair: the input can't be used ({len(exc.issues)} problem{'s' * (len(exc.issues) != 1)}):",
          file=sys.stderr)
    for issue in exc.issues:
        print(f"  {issue}", file=sys.stderr)


def solve_command(args) -> int:
    from shiftfair.report import schedule_lines, write_schedule
    from shiftfair.solve import SolverBug, Status, solve

    if not args.time_limit > 0:
        print("shiftfair: --time-limit must be a positive number of seconds", file=sys.stderr)
        return EXIT_USAGE
    if args.workers < 1:
        print("shiftfair: --workers must be 1 or more", file=sys.stderr)
        return EXIT_USAGE
    problem = _load(args)
    if problem is None:
        return EXIT_USAGE
    try:
        result = solve(problem, time_limit=args.time_limit, workers=args.workers)
    except SolverBug as exc:
        print(f"shiftfair: internal error, please report it: {exc}", file=sys.stderr)
        return EXIT_BUG
    took = f"{result.wall_time:.2f} s"
    if result.status == Status.INFEASIBLE:
        print(f"infeasible: no schedule can meet every rule (proven in {took})")
        return EXIT_INVALID
    if result.status == Status.UNKNOWN:
        print(f"unknown: no schedule found within {args.time_limit:g} s, and no proof that none exists; "
              "try a longer --time-limit")
        return EXIT_INVALID
    print(f"{result.status}: a schedule that breaks no rule (found in {took}; checked independently)")
    for line in schedule_lines(problem, result.assignment):
        print(line)
    if args.out is not None:
        try:
            write_schedule(args.out, problem, result.assignment)
        except OSError as exc:
            print(f"shiftfair: can't write {args.out}: {exc.strerror or exc}", file=sys.stderr)
            return EXIT_USAGE
        print(f"wrote {args.out}")
    return EXIT_OK


COMMANDS = {"check": check_command, "solve": solve_command}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
