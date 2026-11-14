# Progress

## Status

**Milestone 0 of 6 complete: repository and design.** Next: milestone 1, the model, a strict CSV
loader and an independent schedule checker. The plan is in [`docs/design.md`](docs/design.md).

## Milestones

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
pytest                      (2 passed)
shiftfair --version         (shiftfair 0.1.0)
```

## Concepts to review

- Constraint programming vs. integer linear programming; what CP-SAT is.
- Hard vs. soft constraints; lexicographic (staged) optimization vs. weighted sums.
- Why minimizing the sum of squares spreads load when the total is fixed.
- Infeasible cores, assumption literals, and why a core isn't always minimal.
