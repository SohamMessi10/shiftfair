"""The `shiftfair` command.

Exit codes: 0 done (inputs valid, schedule valid); 1 the schedule breaks a rule; 2 the inputs can't
be used (a missing file, a malformed value) or the command line is wrong.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shiftfair import __version__

EXIT_OK, EXIT_INVALID, EXIT_USAGE = 0, 1, 2


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
    return parser


def check_command(args) -> int:
    from shiftfair.check import check, minutes_worked, score
    from shiftfair.load import InputError, load_problem, load_schedule
    from shiftfair.model import format_minutes

    try:
        problem = load_problem(args.shifts, args.availability)
        assignment = load_schedule(args.schedule, problem) if args.schedule is not None else None
    except InputError as exc:
        print(f"shiftfair: the input can't be used ({len(exc.issues)} problem{'s' * (len(exc.issues) != 1)}):",
              file=sys.stderr)
        for issue in exc.issues:
            print(f"  {issue}", file=sys.stderr)
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


COMMANDS = {"check": check_command}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
