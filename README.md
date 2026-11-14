# ShiftFair

Schedule volunteers to shifts so that every hard rule holds (availability, staffing, hour limits,
no double-booking), hours are spread as evenly as availability allows, and an impossible schedule
comes with the reason: the smallest set of requirements that can't all be met.

**Work in progress.** The design is in [docs/design.md](docs/design.md) and progress in
[PROGRESS.md](PROGRESS.md).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

MIT licensed.
