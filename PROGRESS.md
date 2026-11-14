# Progress

## Status

**Milestone 1 of 6 complete: inputs and the checker.** Next: milestone 2, a feasible schedule from
CP-SAT, checked against a brute-force solver. The plan is in [`docs/design.md`](docs/design.md).

## Milestones

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
pytest                      (53 passed at milestone 1)
shiftfair --version         (shiftfair 0.1.0)
shiftfair check shifts.csv availability.csv [schedule.csv]
```

## Concepts to review

- Constraint programming vs. integer linear programming; what CP-SAT is.
- Hard vs. soft constraints; lexicographic (staged) optimization vs. weighted sums.
- Why minimizing the sum of squares spreads load when the total is fixed.
- Infeasible cores, assumption literals, and why a core isn't always minimal.
- Half-open intervals: why `[start, end)` makes back-to-back shifts not overlap.
- Why the checker is independent of the solver.
