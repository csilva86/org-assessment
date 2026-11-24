---
name: salesforce-readonly-collection
description: The read-only sf CLI commands and SOQL query files the Org Assessment collectors use, area by area. Read before collecting any data from a Salesforce org.
user-invocable: false
---

# Read-only collection from a Salesforce org

Every command below only reads. They are the same commands the guardrail hook allows.
Always add `--target-org <alias> --json`.

## SOQL lives in `queries/`, never on the command line

Run each query from its file:

```
sf data query --file queries/<area>/<name>.soql --target-org <alias> --json > <snapshot>/<area>/<name>.json
```

- Files ending in `.tooling.soql` also take `--use-tooling-api`, and are saved as `<name>.json`
  without `.tooling` (e.g. `workflow-rules.json`).
- **Never use `--query "..."`.** On Windows, `sf` is a `.cmd` script and `cmd.exe` strips the
  outer quotes of a command line with several quotes, which breaks the path
  `C:\Program Files\sf\...` (`'C:\Program' is not recognized`). Files avoid quotes entirely.
- With `--json`, `sf` prints JSON even when a query fails. A file counts as collected only if it
  is valid JSON with `"status": 0`. Anything else is recorded as failed in the manifest.
- To add a query, add a `.soql` file to the area's folder. Do not invent queries at run time.

> Status: the `licenses-users` query on `UserLicense` was confirmed on a Developer Edition org
> (2026-11-23). The rest were written from the Salesforce object reference and are confirmed on
> the first full run.

## Per area

| Area | Query files | Other commands (no quotes needed) |
| --- | --- | --- |
| `licenses-users` | every file in `queries/licenses-users/` | — |
| `permissions` | every file in `queries/permissions/` | — |
| `objects-config` | every file in `queries/objects-config/` | `sf sobject list --sobject all` → `sobjects.json`; `sf sobject describe --sobject <Object>` → `describe-<Object>.json` for each object the approved requirements name |
| `automations` | every file in `queries/automations/` | — |
| `limits` | — | `sf org list limits` → `limits.json` |

Notes:
- Process Builder processes appear in `flows.json` with `ProcessType = 'Workflow'`.
- `ObjectPermissions` can pass 2,000 rows in large orgs; add `--bulk` only if the CLI asks.

## Never

- `sf project deploy`, `sf apex run`, `sf data create/update/delete/upsert/import`, `sf org assign`.
- `--query` with an inline SOQL string (see above).
- Writing outside `snapshots/<alias>/<timestamp>/`.
- Pasting records into chat, commits or `brain/`.
