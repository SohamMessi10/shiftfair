# ShiftFair: design

## Problem

Student clubs, food banks and small teams staff recurring shifts with volunteers. The usual tool is
a sign-up form and a spreadsheet, and the usual results are:

- someone scheduled at a time they said they couldn't do;
- a few reliable people carrying most of the hours;
- a shift left short-staffed with nobody sure whether a full schedule was even possible.

The last one is the hardest to see. When the constraints can't all be met, a spreadsheet just looks
unfinished; nothing says *which* requirements conflict.

## Target user and value

An organizer with a list of shifts and a form export of who can do what. ShiftFair gives them:

1. **A schedule that provably respects every hard rule:** availability, staffing, hour limits, no
   double-booking. An independent checker re-verifies every schedule the solver returns.
2. **The fairest such schedule,** with a precise meaning of "fair" (below). "Optimal" is printed only
   when the solver has proven it.
3. **When no schedule exists, the reason:** a smallest set of requirements that can't all hold
   together, in plain words ("Saturday 09:00–12:00 needs 3 people, but only Ana and Ben are
   available").
4. **The trade-off between fairness and preferences,** measured: how many "prefer" wishes each extra
   hour of imbalance buys.

## Inputs

Two CSV files, the shape a spreadsheet or form export already has.

`shifts.csv`:

| shift | date | start | end | needed |
|---|---|---|---|---|
| sat-am | 2026-12-05 | 09:00 | 12:00 | 3 |
| sat-late | 2026-12-05 | 22:00 | 01:00 | 2 |

- Times are local wall-clock `HH:MM`. An end at or before the start means the next day, so
  overnight shifts work.
- There are no time zones: a club schedule is local. Daylight-saving transitions inside a shift are
  a documented limitation: durations are computed on the wall clock.

`availability.csv`:

| person | max_hours | sat-am | sat-late |
|---|---|---|---|
| Ana | 6 | prefer | no |
| Ben | 4 | yes | avoid |

- Each cell is one of these:
  - `prefer`: happy to;
  - `yes`: can;
  - `avoid`: can, but would rather not;
  - `no` or blank: can't.
- Unknown values, unknown shift ids, duplicate people or shifts, and malformed numbers or times are
  errors naming the file, row and column. Nothing is guessed.

## Rules

**Hard: always enforced; a schedule breaking one is never returned.**

- A person is assigned only to shifts they marked `prefer`, `yes` or `avoid`.
- Each shift gets exactly `needed` people.
- Nobody exceeds `max_hours` in total.
- Nobody works two shifts that overlap in time.

**Soft: optimized, in this order.**

1. **Fairness:** minimize the sum of squared hours per person. The total hours are fixed by the
   shifts, so this is the same as minimizing the variance of hours across people. It spreads work
   as evenly as availability and limits allow. Someone available for one shift can only get one;
   everyone else is evened out.
2. **Preferences:** with fairness held at its optimum (or within a chosen slack), maximize the number
   of `prefer` assignments and minimize the number of `avoid` ones.

Optimizing in stages (lexicographically) instead of a weighted sum means no weight needs tuning.
The `--fairness-slack` option and the trade-off table expose the choice instead of hiding it.

## Outcomes

| Status | Meaning | Exit code |
|---|---|---|
| optimal | a schedule, proven best under the objective | 0 |
| feasible | a schedule, but the time limit came before a proof; the gap to the best bound is reported | 0 |
| infeasible | proven: no schedule satisfies the hard rules; a minimal conflict is shown | 1 |
| unknown | the time limit came before either a schedule or a proof | 1 |
| input error | a file can't be read or is invalid | 2 |

## Explaining infeasibility

- **Cheap checks first:**
  - a shift needs more people than are available for it;
  - total needed hours exceed total available capacity.
  These name the problem directly.
- **Otherwise, a minimal conflict:**
  - Each requirement group becomes switchable by an assumption literal: one shift's staffing, one
    person's hour limit, one person's availability.
  - CP-SAT returns a subset of assumptions that is sufficient for infeasibility (a "core"). It isn't
    always minimal.
  - A deletion filter then drops each element in turn and keeps it out if the rest is still
    infeasible. The result is minimal: removing any one requirement from it makes a schedule
    possible, and tests check exactly that.

## Architecture

```text
shifts.csv ─┐                    ┌──────────► schedule.csv / report.html / schedule.ics
            ├─► load (strict) ─► Problem ─► model (CP-SAT) ─► Solution ─► check (independent)
avail.csv  ─┘                    └──► explain (pre-checks, minimal conflict) when infeasible
```

- **`model.py`:** frozen dataclasses: Shift, Person, Availability, Problem, Solution. Minutes are
  integers everywhere.
- **`load.py`:** strict CSV parsing with located errors.
- **`check.py`:** an independent verifier written without OR-Tools. It checks the hard rules and
  recomputes the objective. Every solver result goes through it, in the CLI and in the tests.
- **`solve.py`:** builds the CP-SAT model and optimizes in stages; reports status, objective, bound
  and solver statistics.
- **`explain.py`:** the pre-checks and the minimal conflict.
- **`report.py`:** a terminal table, CSV, a static HTML schedule (no JavaScript, CSP), and an ICS
  calendar per person.
- **`cli.py`:** commands `solve`, `check`, `explain`, `tradeoff`, `demo`.

No database: the inputs are two small files and the outputs are files. Persistence would add
nothing a club needs.

## Tech stack

- **Python 3.12–3.14:** consistent with the rest of the portfolio.
- **OR-Tools CP-SAT 9.15:** a free, actively maintained constraint solver that proves optimality
  and infeasibility. It takes Boolean assignment variables and a quadratic objective (via product
  variables) natively, and returns infeasible cores from assumptions. Pinned to `9.15.*`: its
  Python API has changed between minor versions.
- **pytest and Hypothesis:** property tests against a brute-force solver.
- **ruff.**
- **GitHub Actions** on Linux and macOS.

## Testing strategy

- **The loader:** every error path names the file, row and column; plus overnight shifts.
- **The checker:** a hand-built violation of each rule is detected exactly.
- **The solver against brute force.** Hypothesis generates tiny problems (up to 4 people and 4
  shifts) that a brute force can enumerate completely. Feasibility must agree, and the optimal
  objective must be equal. Every solver schedule must pass the checker.
- **Explanations:** the conflict is infeasible, and removing any one element makes it feasible.
- **The CLI end to end:** exit codes, files written, the demo.
- **Mutation testing** by hand, as in earlier projects.
- **Measurements:** solve time against problem size on generated instances; the fairness and
  preference trade-off on the demo; and how often parallel search returns a different (but equally
  optimal) schedule.

## Security and privacy

- Local files only; no network, no accounts.
- The HTML report escapes every value and allows no scripts.
- Names are personal data: the demo uses invented names, and the README says not to commit real
  availability files.

## Demo

A fictional club with about 15 people and about 20 shifts a week, invented names, availability
generated with a fixed seed and labeled as synthetic. A second demo is deliberately infeasible, to
show the explanation.

## Milestones

0. Repository, this design, CI.
1. Model, strict loader, independent checker.
2. A feasible schedule with CP-SAT; statuses; brute-force property tests.
3. Fairness, then preferences; optimality claims; the trade-off table.
4. Explaining infeasibility: pre-checks and a minimal conflict.
5. Output: HTML report, CSV and ICS export; the demo command.
6. Measurements, README, final audit.

**Stretch:**
- roles and qualifications;
- minimum rest between shifts;
- multiple weeks with carry-over fairness;
- "why can't Ana have Saturday?", by forcing an assignment and reporting what it costs.
