# checks/

Deterministic checks (guardrail 4): Python code that reads a snapshot and returns
`met`, `partial` or `not_met` with the evidence (snapshot file + path).

**Not built yet.** This is the next step of the project:

1. a loader for the snapshot folder and the approved requirements file;
2. one function per check type, starting with the checks in `requirements/example-support-sla.yaml`;
3. `python -m checks run <requirements-file> <snapshot>` writing `results.json`;
4. tests with a small fake snapshot in `tests/fixtures/` (fictional data only).
