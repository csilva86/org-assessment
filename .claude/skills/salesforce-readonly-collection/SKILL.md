---
name: salesforce-readonly-collection
description: How the Org Assessment collects data from a Salesforce org, area by area, read-only, through python -m collect. Read before collecting.
user-invocable: false
---

# Read-only collection from a Salesforce org

Collection is done by **one script per area**, never by hand:

```
python -m collect area <area> --alias <alias> --snapshot snapshots/<alias>/<YYYY-MM-DD_HHMM> [--objects A,B] [--describe-custom]
```

Areas: `licenses-users`, `permissions`, `objects-config`, `automations`, `limits`.

## What the script does (`collect/`)

- Runs a **fixed list** of read-only `sf` commands for the area (`collect/plan.py`):
  every SOQL file in `queries/<area>/` with `sf data query --file` (files ending in `.tooling.soql`
  add `--use-tooling-api`); `sf sobject list` and `sf sobject describe` for the listed objects
  (objects-config), plus every custom object found in the org with `--describe-custom`;
  `sf org list limits` (limits). Nothing else can run.
  objects-config also queries `OpportunityStage` (stage flags: closed, won, active, order) into
  `opportunity-stages.json`. In an org without Opportunities that query fails: the area exits with
  code 1 and a `FAILED opportunity-stages.json` line, which only matters if a check needs that file.
- **Checks every command with the read-only guardrail** (`check_command` in
  `.claude/hooks/guard_readonly.py`) before running any of them. `sf` runs inside the script, where
  Claude Code's hook cannot see it, so the script applies the same rules itself.
- Writes `<name>.json` (raw `sf` output), `<name>.stderr.log` (sf's error output, often empty) and
  `_manifest.json`, all inside `<snapshot>/<area>/`.
- Retries a command **once**, after 5 seconds, only if it failed without writing anything (several
  `sf` processes starting together on Windows can fail once).
- Refuses to reuse a snapshot: if the area already has a manifest, start a new snapshot.

Why `--file` and never `--query "..."`: on Windows, `sf` is a `.cmd` script and `cmd.exe` strips the
outer quotes of a command line with several quotes, which breaks the path `C:\Program Files\sf\...`.

## Manifest (written by the script)

```json
{
  "area": "permissions",
  "org_alias": "<alias>",
  "snapshot": "snapshots/<alias>/<timestamp>",
  "collected_by": "python -m collect",
  "files": [
    {"file": "permission-sets.json", "command": "sf data query --file ...", "ran_at": "2026-11-24T18:12:13Z",
     "status": "ok", "records": 192, "attempts": 1, "error": null}
  ]
}
```

`status` is `ok` (valid JSON with `"status": 0`), `failed` or `skipped`. A check that needs a
`failed` or `skipped` file reports `error`, never a verdict.

## To add or change what is collected

Add a `.soql` file to `queries/<area>/` (it is picked up automatically), or change
`collect/plan.py`, and add a test in `tests/test_collect.py`. Never collect anything at run time
that is not in the plan.

## Never

- Run `sf` by hand to collect, or edit a file the script wrote.
- `sf project deploy`, `sf apex run`, `sf data create/update/delete/upsert/import`, `sf org assign`,
  `sf org display`.
- Paste records into chat, commits or `brain/`.
