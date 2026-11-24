# checks/

Deterministic checks (guardrail 4): Python code that reads a snapshot and returns `met`,
`partial` or `not_met` for each check, with the evidence that proves it (guardrail 5).

```bash
python -m checks run requirements/<project>.yaml snapshots/<alias>/<timestamp>
python -m checks report reports/<alias>/<timestamp>/results.json   # rebuild the reports only
```

`run` writes, in `reports/<alias>/<timestamp>/`: `results.json`, `client-summary.md` (one line per
business rule, in the client's words), `consultant-detail.md` (every check, its evidence and a
recommended fix) and `gaps.json` (what is not met, for the future development pipeline).

| File | What it does |
| --- | --- |
| `requirements.py` | Loads a requirements file and refuses it unless `status: approved` with `approved_by` and `approved_on` (guardrail 3) |
| `snapshot.py` | Reads the snapshot; a file that is missing, `failed`, `skipped` or holds an `sf` error gives `error`, never a verdict |
| `rules.py` | The six rule types (see `requirements/README.md`) |
| `runner.py` | Runs every check, keeps the link to its business rule, counts the results |
| `report.py` | The three reports, built by code from `results.json`; fixes come from fixed templates per rule type |
| `__main__.py` | The command line; everything goes to `reports/<alias>/<timestamp>/` (git-ignored) |

Tests: `tests/test_checks.py`, on the fictional snapshot in `tests/fixtures/` only.
