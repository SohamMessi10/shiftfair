# Progress

## Status

**Milestone 2 of 6 complete: a valid schedule from CP-SAT.** Next: milestone 3, the fairest
schedule, then preferences, with optimality claimed only when proven. The plan is in
[`docs/design.md`](docs/design.md).

## Milestones

### Milestone 2: a valid schedule

- **The model (`solve.py`):** one Boolean per (person, shift) the person can do, so availability is
  enforced by construction. Then:
  - staffing: exactly `needed` per shift;
  - hour limits: total minutes at most the limit;
  - no overlaps: at each shift's start time, a person is on at most one of the shifts in progress.
    If two intervals overlap, one starts while the other is in progress, so these constraints
    cover every overlapping pair with one constraint per start time instead of one per pair.
- **Statuses:** feasible, infeasible (proven) or unknown (the time limit came before an answer;
  never reported as infeasible).
- **Every schedule the solver returns goes through the independent checker.** A rejected one is a
  bug in the model: it is raised as an internal error (exit code 3), never printed as a schedule.
- **`shiftfair solve SHIFTS AVAILABILITY [--out CSV] [--time-limit S] [--workers N]`** prints the
  schedule by day with each person's hours, and writes a CSV that `shiftfair check` reads back.

**Tests (75):**
- **The solver against brute force.** Hypothesis generates tiny problems: up to 4 shifts over two
  days on a half-hour grid, up to 4 people. An exhaustive search enumerates every staffing. The
  solver must agree on feasibility, and its schedule must be one of the valid ones. About 40% of
  the generated problems are feasible.
- **The model against the checker.** Each variable is fixed to a drawn schedule (random, or a valid
  one with one assignment flipped). CP-SAT must accept it exactly when the checker does. This
  tests every constraint directly, not only the ones a search happens to touch.
- Overnight overlaps, chains of overlaps, and the unknown, feasible and internal-error paths.
- The CLI end to end.

**Mutation-checked:** 15 deliberate bugs. 13 were caught at once, and the 2 survivors are now
caught:
- **Staffing written as "at least `needed`":** a search with no objective never added extra people,
  so no test noticed. The model-against-checker property catches it.
- **A schedule found before the time limit treated as unknown:** without an objective, CP-SAT
  proves the first schedule it finds. A test now simulates the time-limited case.


### Milestone 1: inputs and the checker

- **`model.py`:** shifts, people and problems as immutable data. Times are whole minutes on the
  local wall clock, so overnight shifts (`22:00` to `01:00`) and overlaps are integer comparisons.
  Back-to-back shifts don't overlap.
- **`load.py`:** strict CSV loading of `shifts.csv` and `availability.csv`.
  - **Every problem is reported at once,** with file, row (as the spreadsheet numbers it) and
    column.
  - **Errors:** unknown availability values; times like `9am` or `24:00`; impossible dates;
    zero-length shifts; `needed` below 1; hours that aren't whole minutes; duplicate shifts or
    people (ignoring case); ragged rows; invalid CSV.
  - **Cross-file errors:** a column that isn't a shift, one whose capitals don't match, or a shift
    with no column.
  - **Tolerated:** Excel's byte-order mark, Windows line endings, blank rows, header capitals, and
    quoted cells with commas.
  - **No double blame:** a shift whose own row is invalid isn't also reported as an unknown column
    in the availability file.
- **`check.py`:** an independent checker, deliberately without OR-Tools. It reports availability,
  staffing, hour-limit and overlap violations in plain words, and recomputes the score (sum of
  squared minutes, preferred and avoided assignments).
- **`shiftfair check SHIFTS AVAILABILITY [SCHEDULE]`:** summarizes valid inputs, or checks a
  schedule. Exit codes: 0 valid, 1 a broken rule, 2 unusable input.

**Tests (53):**
- every loader error, by message;
- a Hypothesis property: two shifts overlap exactly when they share a minute, including overnight
  shifts and shifts on different days;
- each checker rule;
- the CLI end to end.

**Mutation-checked:** 28 deliberate bugs.
- 25 were caught at once.
- **One test gap:** the duplicate-name test used "ana" against "Ana", so a case-sensitive check also
  passed it. It now uses "ANA".
- **One dead branch,** found and removed.
- **One equivalent mutant:** a zero-length shift's duration. The model now refuses zero-length
  shifts outright.


### Milestone 0: repository and design

- `docs/design.md`: the problem, inputs, hard and soft rules, outcomes and exit codes, how
  infeasibility is explained, architecture, testing strategy, milestones.
- Package skeleton with `shiftfair --version`; OR-Tools pinned to 9.15 (checked on PyPI: wheels for
  Python 3.12–3.14 on Linux and macOS, Intel and Apple Silicon).
- CI on Python 3.12, 3.13 and 3.14 (Linux) and 3.13 (macOS).
- **Checked before designing around it:** in OR-Tools 9.15, CP-SAT's Python API uses snake_case
  names (`new_bool_var`, `add_assumptions`, `sufficient_assumptions_for_infeasibility`). A small
  infeasible model returned the expected conflicting requirements with 1 and with 8 workers.

## Commands verified

```text
pip install -e ".[dev]"
ruff check src tests
pytest                      (75 passed at milestone 2)
shiftfair --version         (shiftfair 0.1.0)
shiftfair check shifts.csv availability.csv [schedule.csv]
shiftfair solve shifts.csv availability.csv --out schedule.csv
```

## Concepts to review

- Constraint programming vs. integer linear programming; what CP-SAT is.
- Hard vs. soft constraints; lexicographic (staged) optimization vs. weighted sums.
- Why minimizing the sum of squares spreads load when the total is fixed.
- Infeasible cores, assumption literals, and why a core isn't always minimal.
- Half-open intervals: why `[start, end)` makes back-to-back shifts not overlap.
- Why the checker is independent of the solver.
- Clique constraints for interval overlaps (why checking at start times is enough).
- Testing a model by fixing its variables vs. testing a search by its answers.
